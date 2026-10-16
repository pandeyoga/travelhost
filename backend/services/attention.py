"""services/attention.py — mesin "PERLU PERHATIAN" untuk Kalender Keberangkatan.

Kenapa ada?
-----------
Sesi lalu kalender hanya punya 1 kelas peringatan: *bentrok armada*. POC
(`test_core_conflict.py`) membuktikan kelas itu HAMPIR MUSTAHIL terjadi karena INV-4
sudah dikunci di semua jalur tulis (create/reschedule/approve/confirm/dispatch/convert).
Akibatnya banner selalu 0 → fitur terlihat "mati" padahal risiko operasional NYATA lain
justru tidak terlihat sama sekali.

Modul ini menjadi SATU SUMBER KEBENARAN (server-side) untuk semua kelas risiko pada
rentang tanggal kalender, sehingga FE tidak lagi menghitung ulang (dan tidak lagi salah
memakai `vehicle_name` sebagai identitas armada).

Kelas risiko:
  vehicle_conflict      2 keberangkatan AKTIF pada armada yang sama, waktu beririsan (jaring
                        pengaman INV-4 untuk data lama/impor/drift).
  driver_conflict       1 sopir dipakai 2 keberangkatan beririsan (termasuk `pending`, karena
                        pending tidak mereservasi tapi tetap menjanjikan sopir ke pelanggan).
  maintenance_conflict  Window perawatan (scheduled/in_progress) menabrak keberangkatan aktif
                        (INV-21). Sejak fix A, jalur POST/PATCH /maintenance menolak ini —
                        kelas ini kini murni jaring pengaman untuk data lama.
  no_driver             Keberangkatan aktif di masa depan belum punya sopir.
  pending_request       Permintaan publik `pending` belum diproses ops.
  hold_expired          Reservasi `hold` lewat batas DP (`hold_expires_at`) — jaring pengaman
                        bila scheduler auto-expire tidak berjalan.
  hold_expiring         Tenggat DP `hold` < 24 jam → ops harus mengejar DP sebelum armada
                        dilepas otomatis oleh scheduler.
  unpaid_soon           Keberangkatan aktif <= 3 hari lagi tapi belum ada pembayaran.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from services.availability import ACTIVE_BOOKING_STATUSES, MAINT_BLOCKING_STATUSES, overlaps
from services.geo import parse_iso

# Statuses yang relevan untuk dimensi sopir (pending ikut: sopir sudah dijanjikan).
DRIVER_SCOPE_STATUSES = set(ACTIVE_BOOKING_STATUSES) | {"pending"}

SOON_HOURS = 48          # ambang "segera berangkat" untuk eskalasi severity
UNPAID_SOON_DAYS = 3     # ambang risiko pembayaran
HOLD_SOON_HOURS = 24     # ambang "tenggat DP mendekat"
CANDIDATE_PAD_DAYS = 31  # buffer agar perjalanan multi-hari lintas bulan tetap terdeteksi

RISK_META = {
    "vehicle_conflict": ("Bentrok armada", "high"),
    "driver_conflict": ("Bentrok sopir", "high"),
    "maintenance_conflict": ("Tabrakan perawatan", "high"),
    "hold_expired": ("Hold DP kedaluwarsa", "high"),
    "no_driver": ("Belum ada sopir", "medium"),
    "hold_expiring": ("Tenggat DP mendekat", "medium"),
    "pending_request": ("Permintaan menunggu", "medium"),
    "unpaid_soon": ("Belum dibayar", "medium"),
}
RISK_ORDER = ["vehicle_conflict", "driver_conflict", "maintenance_conflict", "hold_expired",
              "no_driver", "hold_expiring", "pending_request", "unpaid_soon"]
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}

_MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
           "September", "Oktober", "November", "Desember"]

# Label ramah-manusia untuk tipe armada (sinkron services/pricing.VEHICLE_TYPES).
VEHICLE_TYPE_LABEL = {
    "hiace_premio": "Hiace Premio", "hiace": "Hiace Commuter", "elf": "Isuzu Elf",
    "bus": "Medium Bus", "avanza": "Avanza / MPV",
}


def _vtype_label(key: str) -> str:
    return VEHICLE_TYPE_LABEL.get(key or "", (key or "").replace("_", " ").strip().title())


def _last_day(year: int, month: int) -> str:
    nxt = datetime(year + (month // 12), (month % 12) + 1, 1, tzinfo=timezone.utc)
    return (nxt - timedelta(days=1)).date().isoformat()


def resolve_window(month: Optional[str] = None, start: Optional[str] = None,
                   end: Optional[str] = None, now: Optional[datetime] = None):
    """Kembalikan (start_date, end_date, label) — keduanya 'YYYY-MM-DD'."""
    now = now or datetime.now(timezone.utc)
    if start and end:
        s, e = start[:10], end[:10]
        if e < s:
            s, e = e, s
        return s, e, f"{s} s/d {e}"
    ym = (month or f"{now.year}-{now.month:02d}")[:7]
    try:
        y, m = int(ym[:4]), int(ym[5:7])
        if not 1 <= m <= 12:
            raise ValueError
    except (ValueError, IndexError):
        y, m = now.year, now.month
    return f"{y}-{m:02d}-01", _last_day(y, m), f"Bulan {_MONTHS[m - 1]} {y}"


def _fmt(iso: str) -> str:
    dt = parse_iso(iso)
    if not dt:
        return "-"
    return f"{dt.day} {_MONTHS[dt.month - 1][:3]} {dt.strftime('%H:%M')}"


def _fmt_date(d: str) -> str:
    dt = parse_iso(d)
    if not dt:
        return str(d or "-")
    return f"{dt.day} {_MONTHS[dt.month - 1][:3]}"


def _pairwise_overlaps(groups):
    """groups: {key: [booking,...]} -> {booking_id: [booking lain yang beririsan]}"""
    hits = {}
    for lst in groups.values():
        items = [b for b in lst if b.get("start_datetime") and b.get("end_datetime")]
        items.sort(key=lambda b: b["start_datetime"])
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, c = items[i], items[j]
                if not overlaps(a["start_datetime"], a["end_datetime"],
                                c["start_datetime"], c["end_datetime"]):
                    continue
                hits.setdefault(a["id"], []).append(c)
                hits.setdefault(c["id"], []).append(a)
    return hits


async def departure_attention(db, month: Optional[str] = None, start: Optional[str] = None,
                              end: Optional[str] = None, now: Optional[datetime] = None) -> dict:
    """Hitung semua risiko keberangkatan pada rentang tampilan kalender."""
    now = now or datetime.now(timezone.utc)
    w_start, w_end, label = resolve_window(month, start, end, now)

    lo = (parse_iso(w_start) - timedelta(days=CANDIDATE_PAD_DAYS)).date().isoformat()
    hi = (parse_iso(w_end) + timedelta(days=CANDIDATE_PAD_DAYS)).date().isoformat()
    candidates = await db.bookings.find(
        {"start_datetime": {"$gte": lo, "$lte": f"{hi}T23:59:59.999999+00:00"},
         "status": {"$ne": "cancelled"}},
        {"_id": 0, "id": 1, "code": 1, "status": 1, "payment_status": 1, "customer_name": 1,
         "vehicle_id": 1, "vehicle_name": 1, "driver_id": 1, "driver_name": 1, "source": 1,
         "start_datetime": 1, "end_datetime": 1, "hold_expires_at": 1, "total_amount": 1,
         "paid_amount": 1, "requested_vehicle_type": 1, "pax": 1},
    ).to_list(3000)

    vehicle_ids = sorted({b["vehicle_id"] for b in candidates if b.get("vehicle_id")})
    maint = []
    if vehicle_ids:
        maint = await db.maintenance_records.find(
            {"vehicle_id": {"$in": vehicle_ids}, "status": {"$in": list(MAINT_BLOCKING_STATUSES)}},
            {"_id": 0, "id": 1, "vehicle_id": 1, "vehicle_name": 1, "type": 1, "title": 1,
             "status": 1, "start_date": 1, "end_date": 1},
        ).to_list(2000)

    # --- Kelompokkan untuk deteksi beririsan --------------------------------------
    by_vehicle, by_driver, maint_by_vehicle = {}, {}, {}
    for b in candidates:
        if b.get("vehicle_id") and b.get("status") in ACTIVE_BOOKING_STATUSES:
            by_vehicle.setdefault(b["vehicle_id"], []).append(b)
        if b.get("driver_id") and b.get("status") in DRIVER_SCOPE_STATUSES:
            by_driver.setdefault(b["driver_id"], []).append(b)
    for m in maint:
        if m.get("start_date") and m.get("end_date"):
            maint_by_vehicle.setdefault(m["vehicle_id"], []).append(m)

    veh_hits = _pairwise_overlaps(by_vehicle)
    drv_hits = _pairwise_overlaps(by_driver)

    items = []
    for b in candidates:
        # Hanya laporkan keberangkatan yang JATUH di rentang tampilan.
        day = (b.get("start_datetime") or "")[:10]
        if not (w_start <= day <= w_end):
            continue
        risks = []
        s_dt = parse_iso(b.get("start_datetime"))
        hours_to_go = ((s_dt - now).total_seconds() / 3600.0) if s_dt else None

        def add(rtype, message, related=None, severity=None):
            lbl, sev = RISK_META[rtype]
            risks.append({"type": rtype, "label": lbl, "severity": severity or sev,
                          "message": message, "related": related or []})

        for other in veh_hits.get(b["id"], []):
            add("vehicle_conflict",
                f"Armada {b.get('vehicle_name') or '-'} juga dipakai {other.get('code')} "
                f"({_fmt(other.get('start_datetime'))}–{_fmt(other.get('end_datetime'))})",
                [{"id": other["id"], "code": other.get("code")}])
        for other in drv_hits.get(b["id"], []):
            add("driver_conflict",
                f"Sopir {b.get('driver_name') or '-'} juga ditugaskan di {other.get('code')} "
                f"({_fmt(other.get('start_datetime'))})",
                [{"id": other["id"], "code": other.get("code")}])
        if b.get("status") in ACTIVE_BOOKING_STATUSES:
            for m in maint_by_vehicle.get(b.get("vehicle_id"), []):
                if overlaps(m["start_date"], m["end_date"], b.get("start_datetime"), b.get("end_datetime")):
                    add("maintenance_conflict",
                        f"Armada masuk perawatan “{m.get('title') or m.get('type')}” "
                        f"({_fmt_date(m.get('start_date'))}–{_fmt_date(m.get('end_date'))})")
        if b.get("status") == "hold":
            exp = parse_iso(b.get("hold_expires_at"))
            if exp and exp < now:
                add("hold_expired", f"Batas DP lewat {_fmt(b.get('hold_expires_at'))} — "
                                    f"reservasi armada perlu dilepas atau diperpanjang")
            elif exp and (exp - now).total_seconds() / 3600.0 <= HOLD_SOON_HOURS:
                jam = max(int((exp - now).total_seconds() // 3600), 0)
                add("hold_expiring",
                    f"DP belum masuk — hold armada berakhir {_fmt(b.get('hold_expires_at'))} "
                    f"(±{jam} jam lagi)",
                    severity="high" if jam <= 6 else "medium")
        if b.get("status") in ACTIVE_BOOKING_STATUSES and not b.get("driver_id"):
            if hours_to_go is None or hours_to_go > -24:
                add("no_driver", "Belum ada sopir yang ditugaskan",
                    severity="high" if (hours_to_go is not None and hours_to_go <= SOON_HOURS) else "medium")
        if b.get("status") == "pending":
            late = hours_to_go is not None and hours_to_go <= SOON_HOURS
            add("pending_request",
                ("Permintaan belum diproses dan keberangkatan sudah dekat"
                 if late else "Permintaan pelanggan menunggu persetujuan ops")
                + (f" · minta {_vtype_label(b.get('requested_vehicle_type'))}"
                   if b.get("requested_vehicle_type") else "")
                + (f" · {b.get('pax')} pax" if b.get("pax") else ""),
                severity="high" if late else "medium")
        if (b.get("status") in ACTIVE_BOOKING_STATUSES
                and (b.get("payment_status") or "belum_bayar") == "belum_bayar"
                and hours_to_go is not None and -24 <= hours_to_go <= UNPAID_SOON_DAYS * 24):
            add("unpaid_soon", f"Belum ada pembayaran, berangkat {_fmt(b.get('start_datetime'))}")

        if not risks:
            continue
        risks.sort(key=lambda r: (SEVERITY_RANK.get(r["severity"], 9), RISK_ORDER.index(r["type"])))
        items.append({
            "booking_id": b["id"], "code": b.get("code"), "status": b.get("status"),
            "payment_status": b.get("payment_status"), "customer_name": b.get("customer_name"),
            "vehicle_id": b.get("vehicle_id"), "vehicle_name": b.get("vehicle_name"),
            "driver_name": b.get("driver_name"), "start_datetime": b.get("start_datetime"),
            "end_datetime": b.get("end_datetime"), "source": b.get("source"),
            "severity": risks[0]["severity"], "risk_types": [r["type"] for r in risks],
            "risks": risks,
        })

    items.sort(key=lambda it: (SEVERITY_RANK.get(it["severity"], 9), it.get("start_datetime") or ""))
    counts = {k: 0 for k in RISK_ORDER}
    for it in items:
        for t in set(it["risk_types"]):
            counts[t] = counts.get(t, 0) + 1
    return {
        "period": {"start": w_start, "end": w_end, "label": label},
        "generated_at": now.isoformat(),
        "summary": {
            "total": len(items),
            "high": sum(1 for it in items if it["severity"] == "high"),
            "medium": sum(1 for it in items if it["severity"] == "medium"),
            "by_type": counts,
        },
        "meta": [{"type": t, "label": RISK_META[t][0], "severity": RISK_META[t][1]} for t in RISK_ORDER],
        "items": items,
    }

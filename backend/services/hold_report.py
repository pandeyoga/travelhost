"""services/hold_report.py — LAPORAN "HOLD HANGUS" (reservasi batal karena DP tak masuk).

Kenapa modul ini ada
--------------------
Penjadwal (`services/notifications.scan` butir 6) sudah MEMBATALKAN otomatis pesanan berstatus
`hold` yang lewat batas DP dan menandainya `hold_expired_at`. Yang belum ada: cara ops/owner
MELIHAT kejadian itu sebagai angka. Akibatnya kerugian paling mahal di bisnis rental — unit
terkunci berjam-jam untuk pesanan yang akhirnya batal — hanya lewat sebagai notifikasi satuan
lalu hilang dari ingatan. Tidak ada yang bisa menjawab: "bulan ini berapa unit-hari yang
terbuang?", "apakah batas 2 jam terlalu pendek?", "berapa tamu yang SUDAH transfer tapi
terlambat kami verifikasi?".

Tiga angka yang dirancang untuk MENGUBAH KEPUTUSAN (bukan sekadar hiasan dasbor):

1. `with_proof` — hold hangus PADAHAL bukti transfer sudah diunggah. Ini BUKAN kesalahan tamu,
   melainkan verifikasi ops yang terlambat. Satu kejadian pun berarti uang tamu sudah masuk
   tetapi pesanannya dibatalkan sistem → wajib ditindak hari itu.
2. `expiry_rate` — porsi hold yang berakhir hangus dibanding seluruh hold yang dimulai pada
   periode sama. Kalau tinggi, `hold_hours` di Pengaturan → Alur Booking memang terlalu pendek
   (tamu perlu waktu ke ATM/m-banking), bukan tamunya yang "tidak serius".
3. `recovered` — tamu yang memesan LAGI setelah hold-nya hangus. Menandai bahwa niat belinya
   masih ada; daftar sisanya (`rows`) layak ditelepon/di-WhatsApp ulang, bukan dibuang.

Read-only: modul ini TIDAK PERNAH mengubah data. Pembatalan tetap milik penjadwal supaya
membuka laporan tidak punya efek samping.
"""
from datetime import datetime, timedelta, timezone

from core_utils import money, safe_doc
from services.geo import parse_iso

MAX_ROWS = 300
MAX_DAYS = 365
SERVICE_LABELS = {
    "daily_rental": "Sewa Harian + Driver",
    "airport_transfer": "Antar-Jemput Bandara",
    "request_only": "Permintaan Penawaran",
}
SOURCE_LABELS = {
    "web_booking": "Pemesanan online",
    "web_request": "Formulir web",
    "manual": "Dibuat ops",
}


def _norm_phone(value) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())[-9:]


def _hours_between(a, b):
    da, dbb = parse_iso(a), parse_iso(b)
    if not da or not dbb:
        return None
    return round((dbb - da).total_seconds() / 3600.0, 1)


def _rp(amount) -> str:
    return f"Rp {int(money(amount)):,}".replace(",", ".")


async def build(db, days: int = 30) -> dict:
    """Rekap hold hangus `days` hari terakhir + baris untuk tindak lanjut ops."""
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 30
    days = max(1, min(days, MAX_DAYS))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    # Ambil kandidat lalu saring di Python: `created_at`/`hold_expired_at` disimpan sebagai
    # STRING ISO, dan perbandingan string hanya aman bila seluruh dokumen memakai format &
    # offset yang identik. Data lama/impor tidak menjamin itu, jadi bandingkan sebagai waktu.
    candidates = await db.bookings.find(
        {"hold_expired_at": {"$nin": [None, ""]}}, {"_id": 0},
    ).sort("hold_expired_at", -1).to_list(2000)
    expired = [b for b in candidates
               if (parse_iso(b.get("hold_expired_at")) or cutoff) >= cutoff]

    # Pembanding: seluruh hold yang DIMULAI pada periode sama (dipakai menghitung rasio).
    started_docs = await db.bookings.find(
        {"hold_expires_at": {"$nin": [None, ""]}},
        {"_id": 0, "created_at": 1, "hold_expires_at": 1},
    ).to_list(3000)
    holds_started = sum(
        1 for b in started_docs
        if (parse_iso(b.get("created_at")) or cutoff) >= cutoff) or 0

    ids = [b["id"] for b in expired if b.get("id")]
    proofs_by_booking = {}
    if ids:
        proofs = await db.payment_proofs.find(
            {"booking_id": {"$in": ids}},
            {"_id": 0, "booking_id": 1, "status": 1, "amount_claimed": 1, "created_at": 1},
        ).to_list(2000)
        for p in proofs:
            proofs_by_booking.setdefault(p["booking_id"], []).append(p)

    # Nomor telepon: pesanan online menyimpan `contact_phone`; pesanan buatan ops mengambil
    # dari kartu pelanggan. Tanpa nomor, baris ini tidak bisa ditindaklanjuti — jadi dicari.
    cust_ids = [b.get("customer_id") for b in expired if b.get("customer_id")]
    phone_by_customer = {}
    if cust_ids:
        for c in await db.customers.find(
                {"id": {"$in": cust_ids}}, {"_id": 0, "id": 1, "phone": 1}).to_list(1000):
            phone_by_customer[c["id"]] = c.get("phone") or ""

    # "Kembali memesan": pesanan lain dari nomor yang sama, dibuat SETELAH hold hangus.
    phones = {}
    for b in expired:
        ph = _norm_phone(b.get("contact_phone") or phone_by_customer.get(b.get("customer_id")))
        if ph:
            phones.setdefault(ph, []).append(b)
    later_bookings = []
    if phones:
        later_bookings = await db.bookings.find(
            {"created_at": {"$nin": [None, ""]}},
            {"_id": 0, "code": 1, "created_at": 1, "contact_phone": 1, "customer_id": 1,
             "status": 1},
        ).sort("created_at", -1).to_list(3000)

    def _recovered(booking, phone) -> str:
        """Kode pesanan susulan dari nomor sama sesudah hangus (atau string kosong)."""
        if not phone:
            return ""
        exp_at = parse_iso(booking.get("hold_expired_at"))
        if not exp_at:
            return ""
        for other in later_bookings:
            if other.get("code") == booking.get("code"):
                continue
            other_phone = _norm_phone(
                other.get("contact_phone") or phone_by_customer.get(other.get("customer_id")))
            if other_phone != phone:
                continue
            made = parse_iso(other.get("created_at"))
            if made and made > exp_at and other.get("status") != "cancelled":
                return other.get("code") or ""
        return ""

    rows, by_vehicle, by_service, by_day = [], {}, {}, {}
    hold_hours_seen, with_proof, recovered_n = [], 0, 0
    for b in expired:
        phone = _norm_phone(b.get("contact_phone") or phone_by_customer.get(b.get("customer_id")))
        plist = sorted(proofs_by_booking.get(b.get("id"), []),
                       key=lambda p: str(p.get("created_at") or ""), reverse=True)
        last_proof = plist[0] if plist else None
        if plist:
            with_proof += 1
        service = str(b.get("service") or "")
        total = money(b.get("total_amount"))
        dp = money(b.get("dp_amount"))
        expired_at = b.get("hold_expired_at")
        day = str(expired_at or "")[:10]
        hold_span = _hours_between(b.get("created_at"), b.get("hold_expires_at"))
        # Jendela DP yang dijanjikan ke tamu: pakai `hold_hours` yang TERSIMPAN di pesanan
        # (nilai Pengaturan saat pesanan dibuat). Selisih waktu hanya dipakai bila field itu
        # kosong (data lama), dan tidak boleh negatif — batas yang digeser manual/administratif
        # pernah membuat rata-rata jadi minus dan angka itu tidak berarti apa pun bagi ops.
        window_hours = money(b.get("hold_hours"))
        if window_hours <= 0:
            window_hours = max(hold_span or 0, 0)
        if window_hours > 0:
            hold_hours_seen.append(window_hours)
        rebooked = _recovered(b, phone)
        if rebooked:
            recovered_n += 1

        vkey = b.get("vehicle_id") or "-"
        v = by_vehicle.setdefault(vkey, {"vehicle_id": vkey,
                                        "vehicle_name": b.get("vehicle_name") or "Tanpa unit",
                                        "count": 0, "value": 0})
        v["count"] += 1
        v["value"] += total
        s = by_service.setdefault(service, {"service": service,
                                           "label": b.get("service_label")
                                           or SERVICE_LABELS.get(service, service or "Lainnya"),
                                           "count": 0, "value": 0})
        s["count"] += 1
        s["value"] += total
        d = by_day.setdefault(day, {"date": day, "count": 0, "value": 0})
        d["count"] += 1
        d["value"] += total

        rows.append({
            "id": b.get("id"), "code": b.get("code"),
            "customer_name": b.get("customer_name") or "-",
            "phone": b.get("contact_phone") or phone_by_customer.get(b.get("customer_id")) or "",
            "vehicle_name": b.get("vehicle_name") or "-",
            "service": service,
            "service_label": b.get("service_label") or SERVICE_LABELS.get(service, "-"),
            "route_name": b.get("route_name") or "",
            "start_datetime": b.get("start_datetime"),
            "created_at": b.get("created_at"),
            "hold_expires_at": b.get("hold_expires_at"),
            "hold_expired_at": expired_at,
            "hold_hours": window_hours,
            "total_amount": total, "dp_amount": dp,
            "source": b.get("source") or "manual",
            "source_label": SOURCE_LABELS.get(b.get("source") or "manual", "Lainnya"),
            "proofs": len(plist),
            "last_proof_status": (last_proof or {}).get("status") or "",
            "rebooked_code": rebooked,
        })

    count = len(rows)
    potential = sum(r["total_amount"] for r in rows)
    dp_value = sum(r["dp_amount"] for r in rows)
    expiry_rate = round(count * 100.0 / holds_started, 1) if holds_started else 0.0
    avg_hold = round(sum(hold_hours_seen) / len(hold_hours_seen), 1) if hold_hours_seen else 0.0

    insights = []
    if with_proof:
        insights.append({
            "tone": "danger",
            "text": f"{with_proof} pesanan hangus PADAHAL bukti transfer sudah diunggah — "
                    f"ini keterlambatan verifikasi di sisi kita, bukan tamu. Periksa antrean "
                    f"“Bukti Transfer Menunggu Verifikasi” setiap hari.",
        })
    if count and expiry_rate >= 40:
        insights.append({
            "tone": "warning",
            "text": f"{expiry_rate}% hold berakhir hangus (rata-rata jendela {avg_hold} jam). "
                    f"Pertimbangkan menambah batas jam DP di Pengaturan → Alur Pemesanan "
                    f"Online agar tamu punya waktu ke m-banking.",
        })
    if recovered_n:
        insights.append({
            "tone": "info",
            "text": f"{recovered_n} tamu memesan lagi setelah hold-nya hangus — niat belinya "
                    f"masih ada. Sisanya layak dihubungi ulang lewat WhatsApp.",
        })
    top = sorted(by_vehicle.values(), key=lambda x: (-x["count"], -x["value"]))
    if top and top[0]["count"] >= 2:
        insights.append({
            "tone": "info",
            "text": f"Unit paling sering terkunci sia-sia: {top[0]['vehicle_name']} "
                    f"({top[0]['count']}×, potensi {_rp(top[0]['value'])}).",
        })
    if not count:
        insights.append({
            "tone": "success",
            "text": f"Tidak ada hold yang hangus dalam {days} hari terakhir — seluruh reservasi "
                    f"web berlanjut atau dibatalkan secara sadar.",
        })

    return {
        "period_days": days,
        "from": cutoff.isoformat(), "to": now.isoformat(),
        "summary": {
            "count": count, "potential_value": potential, "dp_value": dp_value,
            "with_proof": with_proof, "recovered": recovered_n,
            "holds_started": holds_started, "expiry_rate": expiry_rate,
            "avg_hold_hours": avg_hold,
        },
        "by_vehicle": top[:8],
        "by_service": sorted(by_service.values(), key=lambda x: -x["count"]),
        "daily": sorted(by_day.values(), key=lambda x: x["date"]),
        "rows": safe_doc(rows[:MAX_ROWS]),
        "truncated": count > MAX_ROWS,
        "insights": insights,
    }


def to_csv(data: dict) -> str:
    """CSV untuk tindak lanjut ops (dibuka di Excel/Sheets). Titik-koma = pemisah id-ID."""
    head = ["Kode", "Pelanggan", "WhatsApp", "Unit", "Layanan", "Jadwal jalan", "Dibuat",
            "Batas DP", "Hangus pada", "Total", "DP", "Sumber", "Bukti diunggah",
            "Status bukti", "Pesan lagi"]
    lines = [";".join(head)]
    for r in data.get("rows") or []:
        cells = [r.get("code", ""), r.get("customer_name", ""), r.get("phone", ""),
                 r.get("vehicle_name", ""), r.get("service_label", ""),
                 str(r.get("start_datetime") or ""), str(r.get("created_at") or ""),
                 str(r.get("hold_expires_at") or ""), str(r.get("hold_expired_at") or ""),
                 str(int(money(r.get("total_amount")))), str(int(money(r.get("dp_amount")))),
                 r.get("source_label", ""), str(r.get("proofs") or 0),
                 r.get("last_proof_status", ""), r.get("rebooked_code", "")]
        lines.append(";".join('"' + str(c).replace('"', "'") + '"' for c in cells))
    return "\n".join(lines)

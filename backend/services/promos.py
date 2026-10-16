"""services/promos.py — validasi & pemakaian KODE PROMO yang bisa ditegakkan.

Masalah yang diperbaiki
-----------------------
Koleksi `promos` dulu hanya menyimpan `code`, `discount_type`, `discount_value`,
`valid_until`, `active`. Syarat pemakaian ditulis di DESKRIPSI untuk dibaca manusia
("minimal 2 hari", "khusus Hiace Premio akhir pekan") sehingga tidak ada satu pun aturan
yang bisa dijalankan komputer. Begitu kode promo dipakai di checkout online, diskon akan
bocor di luar niat pemilik (mis. potongan rombongan dipakai untuk sewa 1 hari) dan tidak
ada kuota yang membatasi kerugian.

Modul ini menambah SYARAT SEBAGAI DATA dan memvalidasinya di SERVER:
  valid_from / valid_until  — jendela berlaku (tanggal, inklusif)
  min_days                  — durasi minimal sewa
  min_amount                — nilai transaksi minimal (sebelum potongan)
  vehicle_types[]           — hanya tipe armada tertentu
  services[]                — hanya layanan tertentu (daily_rental / airport_transfer)
  weekend_only              — hanya keberangkatan Sabtu/Minggu
  max_uses + used_count     — kuota pemakaian (dikonsumsi ATOMIK saat booking jadi)

Semua penolakan memakai alasan berbahasa Indonesia yang bisa ditampilkan apa adanya ke
pelanggan — pesan "kode tidak valid" tanpa sebab membuat orang batal memesan.
"""
import re
from datetime import datetime, timezone

from pymongo import ReturnDocument

from core_utils import money

DISCOUNT_TYPES = ("percent", "amount")


class PromoError(ValueError):
    """Kode promo ditolak — WAJIB dilaporkan 4xx berALASAN, bukan 5xx."""


def norm_code(code) -> str:
    return re.sub(r"[^A-Z0-9_-]", "", str(code or "").strip().upper())[:32]


def _as_list(value) -> list:
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v or "").strip()]
    text = str(value or "").strip()
    return [p.strip() for p in text.split(",") if p.strip()] if text else []


def _date_only(value):
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else None


def _rp(amount) -> str:
    return f"Rp {int(amount):,}".replace(",", ".")


async def find_promo(db, code):
    clean = norm_code(code)
    if not clean:
        return None
    return await db.promos.find_one({"code": clean}, {"_id": 0})


def evaluate(promo, *, subtotal, days, vehicle_type, service, start_dt=None, now=None) -> int:
    """Hitung potongan (int rupiah) atau `raise PromoError` dengan alasan jelas."""
    if not promo:
        raise PromoError("Kode promo tidak ditemukan.")
    if promo.get("active") is False:
        raise PromoError("Kode promo sudah tidak aktif.")
    today = (now or datetime.now(timezone.utc)).date().isoformat()
    vf, vu = _date_only(promo.get("valid_from")), _date_only(promo.get("valid_until"))
    if vf and today < vf:
        raise PromoError(f"Kode promo baru berlaku mulai {vf}.")
    if vu and today > vu:
        raise PromoError(f"Kode promo sudah kedaluwarsa ({vu}).")
    max_uses = int(money(promo.get("max_uses")))
    if max_uses > 0 and int(money(promo.get("used_count"))) >= max_uses:
        raise PromoError("Kuota kode promo sudah habis.")
    min_days = int(money(promo.get("min_days")))
    if min_days > 0 and int(days or 0) < min_days:
        raise PromoError(f"Kode promo hanya untuk sewa minimal {min_days} hari.")
    min_amount = money(promo.get("min_amount"))
    if min_amount > 0 and money(subtotal) < min_amount:
        raise PromoError(f"Kode promo berlaku untuk transaksi minimal {_rp(min_amount)}.")
    types = _as_list(promo.get("vehicle_types"))
    if types and str(vehicle_type or "") not in types:
        raise PromoError("Kode promo tidak berlaku untuk tipe armada yang dipilih.")
    services = _as_list(promo.get("services"))
    if services and str(service or "") not in services:
        raise PromoError("Kode promo tidak berlaku untuk layanan yang dipilih.")
    if promo.get("weekend_only"):
        if not start_dt or start_dt.weekday() < 5:
            raise PromoError("Kode promo hanya untuk keberangkatan akhir pekan (Sabtu/Minggu).")
    dtype = str(promo.get("discount_type") or "amount").strip().lower()
    if dtype not in DISCOUNT_TYPES:
        raise PromoError("Jenis diskon kode promo tidak dikenal.")
    value = money(promo.get("discount_value"))
    if value <= 0:
        raise PromoError("Nilai diskon kode promo tidak valid.")
    gross = money(subtotal)
    disc = int(round(gross * min(value, 100) / 100.0)) if dtype == "percent" else value
    disc = min(disc, gross)
    if disc <= 0:
        raise PromoError("Kode promo tidak memberi potongan untuk pesanan ini.")
    return disc


def label_for(promo, discount) -> str:
    dtype = str((promo or {}).get("discount_type") or "").lower()
    code = (promo or {}).get("code") or "PROMO"
    if dtype == "percent":
        return f"Promo {code} (−{int(money(promo.get('discount_value')))}%)"
    return f"Promo {code} (−{_rp(discount)})"


async def validate(db, code, *, subtotal, days, vehicle_type, service, start_dt=None) -> dict:
    """Validasi lengkap → {promo, discount, label}. `raise PromoError` bila ditolak."""
    promo = await find_promo(db, code)
    discount = evaluate(promo, subtotal=subtotal, days=days, vehicle_type=vehicle_type,
                        service=service, start_dt=start_dt)
    return {"promo": promo, "discount": discount, "label": label_for(promo, discount)}


def terms_text(promo) -> list:
    """Syarat promo dalam bahasa manusia (dipakai daftar promo di wizard publik).

    Diturunkan dari FIELD yang benar-benar ditegakkan `evaluate()` — bukan dari `description`
    yang ditulis bebas. Kalau syaratnya berubah di Pengaturan, teks ini ikut berubah sendiri,
    sehingga tidak mungkin lagi ada janji promo yang tidak dijalankan server.
    """
    out = []
    min_days = int(money((promo or {}).get("min_days")))
    if min_days > 1:
        out.append(f"min. {min_days} hari")
    min_amount = money((promo or {}).get("min_amount"))
    if min_amount > 0:
        out.append(f"min. {_rp(min_amount)}")
    services = _as_list((promo or {}).get("services"))
    if services:
        labels = {"daily_rental": "sewa harian", "airport_transfer": "antar-jemput bandara",
                  "request_only": "permintaan khusus"}
        out.append("layanan " + ", ".join(labels.get(s, str(s).replace("_", " ")) for s in services[:2]))
    types = _as_list((promo or {}).get("vehicle_types"))
    if types:
        # Label manusia, bukan kunci database: tamu tidak tahu apa itu "hiace_premio".
        from services.pricing import type_label  # impor lokal: hindari lingkar impor
        names = [type_label(t) for t in types]
        out.append(f"khusus {names[0]}" if len(names) == 1
                   else f"khusus {', '.join(names[:2])}{' dll.' if len(names) > 2 else ''}")
    if (promo or {}).get("weekend_only"):
        out.append("akhir pekan")
    vf = _date_only((promo or {}).get("valid_from"))
    if vf:
        out.append(f"mulai {vf}")
    vu = _date_only((promo or {}).get("valid_until"))
    if vu:
        out.append(f"s/d {vu}")
    max_uses = int(money((promo or {}).get("max_uses")))
    if max_uses > 0:
        left = max(max_uses - int(money((promo or {}).get("used_count"))), 0)
        out.append(f"sisa {left} kuota")
    return out


def public_view(promo, *, eligible, discount=0, reason="") -> dict:
    """Bentuk promo untuk konsumsi publik. `used_count`/`id` internal TIDAK dibocorkan."""
    return {
        "code": (promo or {}).get("code") or "",
        "title": (promo or {}).get("title") or (promo or {}).get("code") or "Promo",
        "description": (promo or {}).get("description") or "",
        "discount_type": str((promo or {}).get("discount_type") or "amount"),
        "discount_value": money((promo or {}).get("discount_value")),
        "valid_until": _date_only((promo or {}).get("valid_until")) or "",
        "terms": terms_text(promo),
        "eligible": bool(eligible),
        "discount": int(money(discount)),
        "reason": reason or "",
    }


async def list_for_context(db, *, subtotal, days, vehicle_type, service, start_dt=None,
                           limit: int = 12) -> list:
    """Daftar promo aktif + status kelayakannya UNTUK pesanan yang sedang disusun.

    Sumber kebenaran tetap satu: setiap promo dinilai lewat `evaluate()` yang sama dengan
    checkout. Promo yang belum memenuhi syarat TIDAK disembunyikan — alasan penolakannya
    ikut dikirim supaya tamu tahu apa yang perlu diubah (mis. menambah 1 hari sewa).
    Promo yang sudah kedaluwarsa tidak diikutkan (itu sisa materi pemasaran, bukan tawaran).
    """
    today = (datetime.now(timezone.utc)).date().isoformat()
    query = {"active": {"$ne": False}, "$or": [
        {"valid_until": {"$gte": today}}, {"valid_until": {"$in": [None, ""]}},
        {"valid_until": {"$exists": False}},
    ]}
    docs = await db.promos.find(query, {"_id": 0}).sort(
        [("position", 1), ("created_at", -1)]).to_list(60)
    items = []
    for promo in docs:
        if not norm_code(promo.get("code")):
            continue  # promo tanpa kode = materi pemasaran, tidak bisa dipakai di checkout
        try:
            disc = evaluate(promo, subtotal=subtotal, days=days, vehicle_type=vehicle_type,
                            service=service, start_dt=start_dt)
            items.append(public_view(promo, eligible=True, discount=disc))
        except PromoError as exc:
            items.append(public_view(promo, eligible=False, reason=str(exc)))
    items.sort(key=lambda x: (0 if x["eligible"] else 1, -x["discount"]))
    return items[:max(1, int(limit))]


async def consume(db, promo) -> bool:
    """Pakai satu kuota promo secara ATOMIK (kuota habis → False, bukan minus).

    Guard `used_count < max_uses` di dalam query: dua pemesan yang menekan "Pesan"
    bersamaan pada promo sisa 1 kuota tidak bisa keduanya lolos.
    """
    if not promo or not promo.get("id"):
        return False
    query = {"id": promo["id"]}
    max_uses = int(money(promo.get("max_uses")))
    if max_uses > 0:
        query["used_count"] = {"$lt": max_uses}
    res = await db.promos.find_one_and_update(
        query, {"$inc": {"used_count": 1}}, return_document=ReturnDocument.AFTER)
    return bool(res)


async def release(db, promo_id: str) -> None:
    """Kembalikan kuota (dipakai bila booking gagal/dibatalkan tepat setelah dikonsumsi)."""
    if not promo_id:
        return
    await db.promos.update_one({"id": promo_id, "used_count": {"$gt": 0}},
                              {"$inc": {"used_count": -1}})

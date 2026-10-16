"""services/booking_search.py — PENCARIAN KETERSEDIAAN untuk pemesanan online.

Apa yang diperbaiki
-------------------
1. `GET /api/public/fleet` dulu mengembalikan SELURUH isi koleksi `vehicles`: termasuk unit
   MITRA (`ownership='partner'`, yang bukan milik sendiri), unit yang statusnya `maintenance`,
   dan sisa data uji. Website memajang unit yang tidak bisa dijual.
2. Formulir publik dulu tidak pernah memeriksa ketersediaan, sehingga tamu bisa "memesan"
   tanggal yang armadanya sudah penuh dan baru ditolak manual lewat WhatsApp.

Modul ini menyatukan aturan "unit apa yang boleh dijual online" (`publishable_filter`) dan
"unit apa yang benar-benar bebas pada rentang waktu ini" (`search`) — dipakai halaman katalog,
pencarian booking, dan validasi ulang saat pesanan dibuat, sehingga ketiganya tidak mungkin
berbeda pendapat.

Ketersediaan memakai mesin yang SUDAH ADA & sudah diuji (services/availability.py):
bentrok booking aktif (hold/confirmed/ongoing) + jendela perawatan. Query dilakukan SEKALI
untuk semua kandidat (bukan per unit) supaya pencarian tetap cepat.
"""
from services.availability import ACTIVE_BOOKING_STATUSES, MAINT_BLOCKING_STATUSES, overlaps
from services.pricing import (compute_quote, get_dp_percent, get_pricing_rules,
                              resolve_day_rate, span_days, type_label)

# Status armada yang TIDAK boleh dijual online SAMA SEKALI (keluar dari daftar jual, bukan
# sekadar sibuk hari itu). `maintenance` & `on_trip` SENGAJA TIDAK termasuk: keduanya adalah
# keadaan HARI INI, bukan keputusan penjualan — unit yang hari ini di bengkel tetap boleh
# dipesan untuk bulan depan, dan tanggal yang benar-benar terpakai sudah dijaga oleh
# jendela `maintenance_records` + bentrok booking. Menyaring pakai status harian akan membuat
# katalog berubah-ubah tanpa alasan yang bisa dijelaskan ke pengunjung.
BLOCKED_VEHICLE_STATUS = {"inactive", "nonaktif", "sold", "terjual", "retired", "dijual"}


def publishable_filter() -> dict:
    """Query Mongo: unit yang PANTAS tayang & dijual di website.

    - milik sendiri (`ownership` kosong dianggap 'owned' agar data lama tetap tayang),
    - ditandai tayang di web: `publish_to_web` HARUS bernilai True secara EKSPLISIT,
    - status bukan "keluar dari daftar jual" (lihat BLOCKED_VEHICLE_STATUS).

    Kenapa `publish_to_web` wajib eksplisit (bukan "≠ false" seperti versi pertama)?
    Karena "tayang di website dengan harga" adalah KEPUTUSAN PENJUALAN, bukan nilai bawaan.
    Selama field itu boleh kosong, setiap dokumen `vehicles` yang lahir dari jalur non-form
    (skrip uji, impor data, integrasi pihak ketiga) langsung dijual ke tamu tanpa seorang pun
    memutuskannya — dan itu BUKAN teori: unit "Smoke Vehicle" milik `scripts/mutation_smoke.py`
    benar-benar muncul sebagai unit yang bisa dipesan di /booking.
    Formulir armada ERP mengirim nilai ini secara eksplisit (default tercentang), dan database
    lama diselaraskan sekali oleh `scripts/migrate_booking_v1.py` langkah 2 — jadi pengetatan
    ini tidak menyembunyikan armada nyata siapa pun.
    """
    return {
        "$and": [
            {"$or": [{"ownership": "owned"}, {"ownership": {"$in": [None, ""]}},
                     {"ownership": {"$exists": False}}]},
            {"publish_to_web": True},
            {"$or": [{"status": {"$nin": list(BLOCKED_VEHICLE_STATUS)}},
                     {"status": {"$exists": False}}]},
        ]
    }


def public_vehicle(v: dict, *, rate=0, basis="") -> dict:
    """Bentuk armada untuk konsumsi publik (tanpa data internal seperti plat/odometer)."""
    return {
        "id": v.get("id"), "code": v.get("code"), "name": v.get("name"),
        "type": v.get("type"), "type_label": type_label(v.get("type")),
        "capacity": int(v.get("capacity") or 0),
        "features": v.get("features") or [], "photos": v.get("photos") or [],
        "gallery": v.get("gallery") or [], "highlights": v.get("highlights") or [],
        "specs": v.get("specs") or [], "year": v.get("year"), "color": v.get("color"),
        "day_rate": int(rate or 0), "rate_basis": basis,
        "price_from": int(rate or 0),  # harga tampil = harga mesin (tak ada dua angka lagi)
    }


async def publishable_vehicles(db, *, pax=0, vehicle_type=None, vehicle_id=None) -> list:
    query = dict(publishable_filter())
    if vehicle_id:
        query["id"] = str(vehicle_id)
    if vehicle_type:
        query["type"] = str(vehicle_type)
    if pax and int(pax) > 0:
        query["capacity"] = {"$gte": int(pax)}
    return await db.vehicles.find(query, {"_id": 0}).sort("code", 1).to_list(200)


async def busy_map(db, start_iso, end_iso) -> dict:
    """{vehicle_id: alasan sibuk} untuk rentang waktu — satu query per sumber bentrok."""
    busy = {}
    bookings = await db.bookings.find(
        {"status": {"$in": list(ACTIVE_BOOKING_STATUSES)}},
        {"_id": 0, "vehicle_id": 1, "code": 1, "start_datetime": 1, "end_datetime": 1},
    ).to_list(3000)
    for b in bookings:
        vid = b.get("vehicle_id")
        if not vid or vid in busy:
            continue
        if b.get("start_datetime") and b.get("end_datetime") and overlaps(
                start_iso, end_iso, b["start_datetime"], b["end_datetime"]):
            busy[vid] = "Sudah dipesan pada tanggal itu"
    maints = await db.maintenance_records.find(
        {"status": {"$in": list(MAINT_BLOCKING_STATUSES)}},
        {"_id": 0, "vehicle_id": 1, "title": 1, "type": 1, "start_date": 1, "end_date": 1},
    ).to_list(2000)
    for m in maints:
        vid = m.get("vehicle_id")
        if not vid or vid in busy:
            continue
        if m.get("start_date") and m.get("end_date") and overlaps(
                start_iso, end_iso, m["start_date"], m["end_date"]):
            busy[vid] = "Masuk jadwal perawatan"
    return busy


async def quote_for_vehicle(db, vehicle, *, start_iso, end_iso, service="daily_rental",
                            route=None, add_ons=None, discount=0, discount_label="",
                            rules=None, holidays=None, dp_percent=None) -> dict:
    """Harga satu unit — SELALU dihitung server (klien tidak pernah mengirim total)."""
    rules = rules if rules is not None else await get_pricing_rules(db)
    if holidays is None:
        op = await db.settings.find_one({"key": "operational"}, {"_id": 0})
        holidays = ((op or {}).get("value") or {}).get("holidays") or []
    if dp_percent is None:
        dp_percent = await get_dp_percent(db)
    rate, basis = resolve_day_rate(rules, vehicle=vehicle)
    if service == "airport_transfer":
        flat = flat_rate_for(route, vehicle.get("type"))
        if flat is None:
            return {}
        quote = compute_quote(rules, vehicle_type=vehicle.get("type"), days=1,
                             when=start_iso, holidays=holidays, include_travel=False,
                             flat_amount=flat, service=service, add_ons=add_ons,
                             discount=discount, discount_label=discount_label,
                             dp_percent=dp_percent)
    else:
        quote = compute_quote(rules, vehicle_type=vehicle.get("type"),
                             days=span_days(start_iso, end_iso), when=start_iso,
                             holidays=holidays, include_travel=True, day_rate=rate,
                             service=service, add_ons=add_ons, discount=discount,
                             discount_label=discount_label, dp_percent=dp_percent)
    quote["rate_basis"] = basis
    return quote


def flat_rate_for(route, vehicle_type):
    """Tarif flat rute bandara untuk satu tipe armada; None = tipe itu TIDAK dilayani.

    Sengaja mengembalikan None (bukan tarif default): menawarkan unit tanpa tarif berarti
    mengarang harga — cacat yang persis kita berantas di sisa sistem.
    """
    rates = ((route or {}).get("rates") or {})
    raw = rates.get(str(vehicle_type or "").strip())
    try:
        value = int(round(float(raw)))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


async def search(db, *, service="daily_rental", start_iso="", end_iso="", pax=0,
                 vehicle_type=None, route=None, add_ons=None, discount=0,
                 discount_label="") -> dict:
    """Daftar unit yang BEBAS + harga masing-masing (urut termurah)."""
    candidates = await publishable_vehicles(db, pax=pax, vehicle_type=vehicle_type)
    busy = await busy_map(db, start_iso, end_iso)
    rules = await get_pricing_rules(db)
    op = await db.settings.find_one({"key": "operational"}, {"_id": 0})
    holidays = ((op or {}).get("value") or {}).get("holidays") or []
    dp_percent = await get_dp_percent(db)
    options, unavailable = [], []
    for v in candidates:
        rate, basis = resolve_day_rate(rules, vehicle=v)
        card = public_vehicle(v, rate=rate, basis=basis)
        if v["id"] in busy:
            unavailable.append({**card, "reason": busy[v["id"]]})
            continue
        quote = await quote_for_vehicle(
            db, v, start_iso=start_iso, end_iso=end_iso, service=service, route=route,
            add_ons=add_ons, discount=discount, discount_label=discount_label,
            rules=rules, holidays=holidays, dp_percent=dp_percent)
        if not quote:
            unavailable.append({**card, "reason": "Tidak melayani rute ini"})
            continue
        options.append({"vehicle": card, "quote": quote, "available": True})
    options.sort(key=lambda o: (o["quote"]["total"], o["vehicle"]["capacity"]))
    return {"options": options, "unavailable": unavailable,
            "count": len(options), "checked": len(candidates)}

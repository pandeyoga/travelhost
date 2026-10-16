#!/usr/bin/env python3
"""
seed_data.py — Seed akun demo + data minimal realistis (generic naming)
=======================================================================
Mengisi MongoDB dengan: 3 akun demo (owner/ops_admin/driver), beberapa vehicles,
drivers, customers, dan booking contoh yang LULUS invarian (lihat verify_data_integrity).
Mengikuti KONTRAK API (bukan sebaliknya). Idempotent: clear lalu isi ulang.

Usage: cd /app && python scripts/seed_data.py
"""
import asyncio, os, secrets, sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / "backend" / ".env")
except Exception: pass

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "app_db")
G, R, Y, X = "\033[92m", "\033[91m", "\033[93m", "\033[0m"

# Pakai helper backend bila tersedia (single source of truth)
try:
    from core_utils import new_id, now_iso, hash_password
except Exception:
    import hashlib, uuid
    _SALT = "travel-fleet::"
    def new_id(prefix="id"): return f"{prefix}_{uuid.uuid4().hex[:16]}"
    def now_iso(): return datetime.now(timezone.utc).isoformat()
    def hash_password(pw): return hashlib.sha256((_SALT + pw).encode()).hexdigest()


def iso(dt): return dt.astimezone(timezone.utc).isoformat()


def _norm_phone(phone):  # B4: normalisasi ke +62 (mirror services.identity)
    import re
    d = re.sub(r"[^0-9]", "", str(phone or ""))
    if not d:
        return ""
    if d.startswith("62"):
        return "+" + d
    if d.startswith("0"):
        return "+62" + d[1:]
    if d.startswith("8"):
        return "+62" + d
    return "+" + d


async def run():
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
    except ImportError:
        os.system("pip install motor -q")
        from motor.motor_asyncio import AsyncIOMotorClient
    db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]

    COLLECTIONS = ["users", "sessions", "vehicles", "drivers", "customers", "leads",
                   "lead_activities", "conversations", "messages", "bookings", "trips", "locations",
                   "trip_shares", "payments", "expenses", "invoices", "notification_tasks", "broadcasts",
                   "maintenance_records", "destinations", "articles", "testimonials",
                   "workshops", "service_types",
                   "driver_payouts",
                   "audit_logs", "settings", "user_onboarding", "counters",
                   "quotations", "packages", "promos",
                   "events", "automation_rules", "automation_runs",
                   "segments", "sequences", "sequence_enrollments", "campaigns", "campaign_recipients",
                   "geocode_cache", "partners", "subcharters", "partner_settlements",
                   # `conversion_events` = outbox konversi iklan (Meta/Google). WAJIB di-reset:
                   # koleksi ini TIDAK pernah dibersihkan siapa pun, sehingga setiap kali gate /
                   # POC menembak endpoint publik, angka konversi demo membengkak permanen dan
                   # dasbor pemasaran melaporkan konversi yang tak pernah terjadi (BUG-0127).
                   "conversion_events",
                   # Halaman iklan demo + statistik A/B-nya di-reset supaya data demo konsisten.
                   # `media_assets`/`media_folders` SENGAJA TIDAK di-reset: berkas fisiknya ada di
                   # disk, jadi menghapus dokumennya akan meninggalkan berkas yatim yang tak bisa
                   # dijangkau siapa pun (dan aset yang diunggah pengguna hilang tanpa sebab).
                   "landing_pages", "landing_stats",
                   # CMS-05/07/08: token pratinjau, permintaan ulasan, & statistik konten
                   # WAJIB di-reset bersama konten demo — kalau tidak, panel Analitik &
                   # halaman Ulasan menampilkan angka/riwayat untuk konten yang sudah hilang.
                   "content_previews", "review_requests", "content_stats",
                   # CMS-CW3: riwayat versi, tempat sampah, & pengalihan URL milik konten demo.
                   # Kalau tidak di-reset: Tempat Sampah berisi konten yang id-nya sudah tak ada
                   # dan tabel pengalihan menunjuk slug yang sudah lenyap.
                   "content_versions", "content_trash", "content_redirects",
                   # Pemesanan online publik (rute antar-jemput + bukti transfer pelanggan)
                   "transfer_routes", "payment_proofs", "pickup_points",
                   # INV-REF-02 batch 5: master kota (relasi customers.city & partners.city)
                   "cities"]
    for c in COLLECTIONS:
        await db[c].delete_many({})

    pw = hash_password("demo12345")
    users = [
        {"id": new_id("usr"), "name": "Pemilik", "email": "owner@demo.local", "password_hash": pw,
         "role": "owner", "phone": "0811000001", "status": "active", "created_at": now_iso()},
        {"id": new_id("usr"), "name": "Admin Operasional", "email": "ops@demo.local", "password_hash": pw,
         "role": "ops_admin", "phone": "0811000002", "status": "active", "created_at": now_iso()},
        {"id": new_id("usr"), "name": "Driver Satu", "email": "driver@demo.local", "password_hash": pw,
         "role": "driver", "phone": "0811000003", "status": "active", "created_at": now_iso()},
        # FASE F (E29): peran baru marketing_admin — pemilik kanal akuisisi (iklan, landing page, lead).
        # CATATAN: jangan menyisipkan sebelum indeks 2; users[2] dipakai sebagai driver di bawah.
        {"id": new_id("usr"), "name": "Admin Marketing", "email": "marketing@demo.local", "password_hash": pw,
         "role": "marketing_admin", "phone": "0811000005", "status": "active", "created_at": now_iso()},
    ]
    await db.users.insert_many(users)

    # E16: Master Mitra Travel (partner) — dibuat SEBELUM vehicles (FK vehicles.partner_id).
    partners = [
        {"id": new_id("ptn"), "name": "Travel Mitra Sejahtera", "pic": "Pak Budi",
         "phone": "0812555111", "email": "ops@mitrasejahtera.id", "city": "Bandung",
         "address": "Jl. Soekarno Hatta 210", "rating": 4.6,
         "notes": "Mitra utama unit Hiace & Elf.", "status": "active", "created_at": now_iso()},
        {"id": new_id("ptn"), "name": "CV Armada Nusantara", "pic": "Bu Sari",
         "phone": "0813777222", "email": "cs@armadanusantara.id", "city": "Jakarta",
         "address": "Jl. Gatot Subroto 45", "rating": 4.3,
         "notes": "Cadangan armada besar (bus medium).", "status": "active", "created_at": now_iso()},
    ]
    await db.partners.insert_many(partners)

    BASE_PANO = "https://photo-sphere-viewer-data.netlify.app/assets/tour/"
    cabin_tour = [
        {"id": "depan", "label": "Kabin Depan", "panorama": BASE_PANO + "key-biscayne-1.jpg",
         "thumbnail": BASE_PANO + "key-biscayne-1-thumb.jpg",
         "links": [{"nodeId": "tengah", "yaw": 0, "pitch": 0}]},
        {"id": "tengah", "label": "Kabin Tengah", "panorama": BASE_PANO + "key-biscayne-2.jpg",
         "thumbnail": BASE_PANO + "key-biscayne-2-thumb.jpg",
         "links": [{"nodeId": "depan", "yaw": 180, "pitch": 0}, {"nodeId": "belakang", "yaw": 0, "pitch": 0}]},
        {"id": "belakang", "label": "Kabin Belakang", "panorama": BASE_PANO + "key-biscayne-3.jpg",
         "thumbnail": BASE_PANO + "key-biscayne-3-thumb.jpg",
         "links": [{"nodeId": "tengah", "yaw": 180, "pitch": 0}]},
    ]
    # Eksterior 360°: frame berurutan self-host (jumlah bebas per unit; demo = 36 frame).
    SPIN_HIACE = [f"/api/uploads/spin360/hiace/frame-{i}.jpg" for i in range(1, 37)]
    RENTAL_TERMS = [
        "Harga sudah termasuk jasa pengemudi profesional.",
        "Sewa dihitung per hari kalender (bukan per 24 jam).",
        "Pelunasan maksimal H-1 sebelum tanggal keberangkatan.",
        "Pembatalan atau perubahan jadwal maksimal H-3.",
        "Overtime pemakaian di atas pukul 23.00 dikenakan biaya per jam.",
        "Ketersediaan unit akhir pekan / libur nasional wajib dikonfirmasi ke tim sales.",
    ]
    premio_specs = [
        {"key": "capacity", "label": "Kapasitas", "value": "14 Kursi"},
        {"key": "transmission", "label": "Transmisi", "value": "Manual"},
        {"key": "fuel", "label": "Bahan Bakar", "value": "Diesel"},
        {"key": "entertainment", "label": "Hiburan", "value": "TV & Karaoke"},
        {"key": "safety", "label": "Keselamatan", "value": "APAR & P3K"},
        {"key": "ac", "label": "Pendingin", "value": "Double Blower AC"},
    ]
    elf_specs = [
        {"key": "capacity", "label": "Kapasitas", "value": "19 Kursi"},
        {"key": "transmission", "label": "Transmisi", "value": "Manual"},
        {"key": "fuel", "label": "Bahan Bakar", "value": "Diesel"},
        {"key": "entertainment", "label": "Hiburan", "value": "Audio System"},
        {"key": "safety", "label": "Keselamatan", "value": "APAR & P3K"},
        {"key": "ac", "label": "Pendingin", "value": "AC Sentral"},
    ]
    IMG = {
        "front": "https://images.unsplash.com/photo-1485182708500-e8f1f318ba72?q=80&w=1400&auto=format&fit=crop",
        "side": "https://images.unsplash.com/photo-1464219789935-c2d9d9aba644?q=80&w=1400&auto=format&fit=crop",
        "road": "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?q=80&w=1400&auto=format&fit=crop",
        "scenic": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?q=80&w=1400&auto=format&fit=crop",
        "elf": "https://images.unsplash.com/photo-1559416523-140ddc3d238c?q=80&w=1400&auto=format&fit=crop",
    }
    gallery_premio = [
        {"url": IMG["front"], "caption": "Tampak depan"},
        {"url": IMG["side"], "caption": "Eksterior samping"},
        {"url": IMG["road"], "caption": "Siap di perjalanan"},
        {"url": IMG["scenic"], "caption": "Menuju destinasi"},
    ]
    gallery_elf = [
        {"url": IMG["elf"], "caption": "Tampak depan"},
        {"url": IMG["road"], "caption": "Di perjalanan"},
        {"url": IMG["scenic"], "caption": "Menuju destinasi"},
    ]
    hl_premio = ["Kursi reclining premium", "Captain seat opsional", "Bagasi luas & USB charging", "Driver berpengalaman + CHSE"]
    hl_elf = ["Kabin lega 19 kursi", "Cocok rombongan besar", "Pushback seat", "Driver berpengalaman"]
    veh = [
        {"id": new_id("veh"), "code": "V-01", "name": "Hiace Premio 01", "plate_number": "D 1234 AA",
         "type": "hiace_premio", "capacity": 14, "status": "available",
         "kir_expiry": iso(datetime.now(timezone.utc) + timedelta(days=120)),
         "tax_expiry": iso(datetime.now(timezone.utc) + timedelta(days=40)),
         "next_service_date": iso(datetime.now(timezone.utc) + timedelta(days=15)),
         "odometer": 84000, "features": ["AC", "Reclining", "USB", "TV", "Karaoke"],
         "service_interval_km": 4000, "service_interval_days": 180, "last_service_odometer": 80000,
         "last_service_date": iso(datetime.now(timezone.utc) - timedelta(days=19)),
         "photos": [IMG["front"], IMG["side"]], "gallery": gallery_premio, "tour_scenes": cabin_tour,
         "specs": premio_specs, "highlights": hl_premio, "year": 2023, "color": "Putih Mutiara",
         "exterior_frames": SPIN_HIACE, "rental_terms": RENTAL_TERMS,
         "price_from": 1500000, "day_rate": 1500000, "publish_to_web": True,
         "created_at": now_iso()},
        {"id": new_id("veh"), "code": "V-02", "name": "Hiace Premio 02", "plate_number": "D 5678 BB",
         "type": "hiace_premio", "capacity": 14, "status": "available",
         "kir_expiry": iso(datetime.now(timezone.utc) + timedelta(days=200)),
         "tax_expiry": iso(datetime.now(timezone.utc) + timedelta(days=10)),
         "next_service_date": iso(datetime.now(timezone.utc) + timedelta(days=60)),
         "odometer": 42000, "features": ["AC", "Captain Seat", "USB", "TV"],
         "service_interval_km": 10000, "service_interval_days": 180, "last_service_odometer": 33000,
         "last_service_date": iso(datetime.now(timezone.utc) - timedelta(days=60)),
         "photos": [IMG["side"], IMG["front"]], "gallery": gallery_premio, "tour_scenes": cabin_tour,
         "specs": premio_specs, "highlights": hl_premio, "year": 2024, "color": "Hitam Metalik",
         "exterior_frames": SPIN_HIACE, "rental_terms": RENTAL_TERMS,
         "price_from": 1650000, "day_rate": 1650000, "publish_to_web": True,
         "created_at": now_iso()},
        {"id": new_id("veh"), "code": "V-03", "name": "Isuzu Elf Long 01", "plate_number": "D 9012 CC",
         "type": "elf", "capacity": 19, "status": "available",
         "kir_expiry": iso(datetime.now(timezone.utc) + timedelta(days=8)),
         "tax_expiry": iso(datetime.now(timezone.utc) + timedelta(days=160)),
         "next_service_date": iso(datetime.now(timezone.utc) + timedelta(days=90)),
         "odometer": 121000, "features": ["AC", "Pushback", "Audio"],
         "service_interval_km": 15000, "service_interval_days": 365, "last_service_odometer": 110000,
         "last_service_date": iso(datetime.now(timezone.utc) - timedelta(days=10)),
         "photos": [IMG["elf"]], "gallery": gallery_elf, "tour_scenes": cabin_tour,
         "specs": elf_specs, "highlights": hl_elf, "year": 2022, "color": "Putih",
         "rental_terms": RENTAL_TERMS,
         "price_from": 2500000, "day_rate": 2500000, "publish_to_web": True,
         "created_at": now_iso()},
    ]
    await db.vehicles.insert_many(veh)

    # E16: satu unit MILIK MITRA (ownership=partner) untuk demo Pinjam Armada.
    pveh = {"id": new_id("veh"), "code": "VP-01", "name": "Hiace Commuter Mitra (Sejahtera)",
            "plate_number": "D 7777 MT", "type": "hiace", "capacity": 15, "status": "available",
            "odometer": 96000, "features": ["AC", "Audio"], "ownership": "partner",
            "partner_id": partners[0]["id"], "publish_to_web": False, "created_at": now_iso()}
    await db.vehicles.insert_one(pveh)

    drv = [
        {"id": new_id("drv"), "name": "Driver Satu", "phone": "0811000003", "sim_number": "B1-001",
         "sim_expiry": iso(datetime.now(timezone.utc) + timedelta(days=300)), "status": "online",
         "current_vehicle_id": veh[0]["id"], "rating": 4.8, "created_at": now_iso(),
         "comp": {"base_salary_monthly": 4000000.0, "commission_per_trip": 50000.0,
                  "commission_pct_revenue": 0.0, "allowance_per_km": 500.0, "revenue_base": "trip",
                  "enable_base": True, "enable_commission_trip": True,
                  "enable_commission_pct": False, "enable_allowance_km": True}},
        {"id": new_id("drv"), "name": "Driver Dua", "phone": "0811000004", "sim_number": "B1-002",
         "sim_expiry": iso(datetime.now(timezone.utc) + timedelta(days=20)), "status": "offline",
         "current_vehicle_id": None, "rating": 4.6, "created_at": now_iso(),
         "comp": {"base_salary_monthly": 3500000.0, "commission_per_trip": 0.0,
                  "commission_pct_revenue": 0.0, "allowance_per_km": 0.0, "revenue_base": "trip",
                  "enable_base": True, "enable_commission_trip": False,
                  "enable_commission_pct": False, "enable_allowance_km": False}},
    ]
    await db.drivers.insert_many(drv)

    cus = [
        {"id": new_id("cus"), "name": "PT Maju Jaya", "phone": "022111222", "email": "pic@majujaya.id",
         "type": "corporate", "city": "Bandung", "address": "Jl. Asia Afrika 1",
         "total_trips": 3, "lifetime_value": 10500000, "notes": "", "created_at": now_iso(),
         # FASE F6: izin pemasaran = syarat WAJIB agar kontak boleh masuk audiens iklan
         # (Custom Audience / Customer Match). Tanpa flag ini kontak SELALU tersaring.
         "marketing_consent": True, "consent_at": now_iso()},
        {"id": new_id("cus"), "name": "Keluarga Andi", "phone": "0813222333", "email": "andi@mail.com",
         "type": "individual", "city": "Jakarta", "address": "Jl. Sudirman 5",
         "total_trips": 1, "lifetime_value": 3500000, "notes": "", "created_at": now_iso(),
         "marketing_consent": True, "consent_at": now_iso()},
        {"id": new_id("cus"), "name": "CV Sentosa Wisata", "phone": "0227778889", "email": "ops@sentosa.id",
         "type": "corporate", "city": "Cimahi", "address": "Jl. Raya Cimahi 88",
         "total_trips": 0, "lifetime_value": 0, "notes": "", "created_at": now_iso(),
         # sengaja TANPA izin -> membuktikan filter consent bekerja & terlihat di UI
         "marketing_consent": False},
    ]
    for c in cus:
        c["phone_normalized"] = _norm_phone(c["phone"])
    await db.customers.insert_many(cus)

    # Booking contoh — dibuat LULUS invarian (no overlap; total = base + addons; status derivable)
    base = 3000000; addons = [{"label": "Overtime", "amount": 500000}]
    total = base + sum(a["amount"] for a in addons)
    bk = {"id": new_id("bk"), "code": "BK-0001", "customer_id": cus[0]["id"], "vehicle_id": veh[0]["id"],
          "driver_id": drv[0]["id"], "origin": "Bandung", "destination": "Gunung Bromo",
          "start_datetime": iso(datetime.now(timezone.utc) + timedelta(days=3)),
          "end_datetime": iso(datetime.now(timezone.utc) + timedelta(days=5)),
          "base_price": base, "add_ons": addons, "total_amount": total, "paid_amount": 1000000,
          "payment_status": "dp", "status": "confirmed",
          "customer_name": cus[0]["name"], "vehicle_name": veh[0]["name"], "driver_name": drv[0]["name"],
          "notes": "", "created_at": now_iso()}
    await db.bookings.insert_one(bk)
    await db.payments.insert_one({"id": new_id("pay"), "booking_id": bk["id"], "amount": 1000000,
                                  "type": "dp", "method": "transfer", "recorded_by": users[1]["id"],
                                  "paid_at": now_iso()})

    # Booking kedua — armada berbeda (tanpa overlap), status confirmed + DP (INV-2/INV-3).
    base2 = 4000000; addons2 = [{"label": "Tol & Parkir", "amount": 350000}]
    total2 = base2 + sum(a["amount"] for a in addons2)
    bk2 = {"id": new_id("bk"), "code": "BK-0002", "customer_id": cus[1]["id"], "vehicle_id": veh[1]["id"],
           "driver_id": drv[1]["id"], "origin": "Jakarta", "destination": "Bandung",
           "start_datetime": iso(datetime.now(timezone.utc) + timedelta(days=8)),
           "end_datetime": iso(datetime.now(timezone.utc) + timedelta(days=9)),
           "base_price": base2, "add_ons": addons2, "total_amount": total2, "paid_amount": 1500000,
           "payment_status": "dp", "status": "confirmed",
           "customer_name": cus[1]["name"], "vehicle_name": veh[1]["name"], "driver_name": drv[1]["name"],
           "notes": "", "created_at": now_iso()}
    await db.bookings.insert_one(bk2)
    await db.payments.insert_one({"id": new_id("pay"), "booking_id": bk2["id"], "amount": 1500000,
                                  "type": "dp", "method": "transfer", "recorded_by": users[1]["id"],
                                  "paid_at": now_iso()})

    # E16: contoh Sub-charter untuk BK-0002 (status confirmed) + COGS 'sewa_mitra' (AP mitra terbentuk).
    sc_cost = 2200000
    sc_exp = {"id": new_id("exp"), "booking_id": bk2["id"], "trip_id": None, "category": "sewa_mitra",
              "amount": sc_cost, "note": f"Sewa armada mitra {partners[0]['name']} - SC-0001",
              "subcharter_id": None, "recorded_by": users[1]["id"], "created_at": now_iso()}
    await db.expenses.insert_one(sc_exp)
    subc = {"id": new_id("sbc"), "code": "SC-0001", "booking_id": bk2["id"], "booking_code": bk2["code"],
            "partner_id": partners[0]["id"], "partner_name": partners[0]["name"],
            "vehicle_id": pveh["id"], "vehicle_label": pveh["name"],
            "start_datetime": bk2["start_datetime"], "end_datetime": bk2["end_datetime"],
            "cost": float(sc_cost), "status": "confirmed", "note": "Unit sendiri penuh; pinjam unit mitra.",
            "expense_id": sc_exp["id"], "confirmed_at": now_iso(), "settled_at": None, "created_at": now_iso()}
    await db.subcharters.insert_one(subc)
    await db.expenses.update_one({"id": sc_exp["id"]}, {"$set": {"subcharter_id": subc["id"]}})
    await db.counters.update_one({"id": "subcharter"}, {"$set": {"seq": 1}}, upsert=True)

    # === Phase 1: trip aktif + jejak GPS (untuk live map, ETA, INV-6) ===
    # Tautkan akun user driver ke record driver (untuk surface /api/driver/*).
    await db.drivers.update_one({"id": drv[0]["id"]}, {"$set": {"user_id": users[2]["id"]}})

    trip = {"id": new_id("trp"), "booking_id": bk["id"], "vehicle_id": veh[0]["id"], "driver_id": drv[0]["id"],
            "status": "on_trip", "start_at": now_iso(), "end_at": None,
            "revenue": float(total), "profit": None, "distance_km": 0.0,
            "dest_name": "Bromo", "dest_lat": -7.9425, "dest_lng": 112.9530,
            "origin_lat": -6.9147, "origin_lng": 107.6098, "created_at": now_iso()}
    await db.trips.insert_one(trip)
    # Armada sedang dipakai trip.
    await db.vehicles.update_one({"id": veh[0]["id"]}, {"$set": {"status": "on_trip"}})

    # E9/E11: satu trip SELESAI (untuk statistik driver + akrual payroll) — periode berjalan.
    _tnow = datetime.now(timezone.utc)
    trip_done = {"id": new_id("trp"), "booking_id": bk2["id"], "vehicle_id": veh[1]["id"], "driver_id": drv[0]["id"],
                 "status": "completed", "start_at": iso(_tnow - timedelta(days=1)), "end_at": iso(_tnow),
                 "revenue": 2500000.0, "profit": 2500000.0, "distance_km": 250.0, "distance_basis": "odometer",
                 "dest_name": "Pangandaran", "dest_lat": -7.6883, "dest_lng": 108.6531,
                 "origin_lat": -6.9147, "origin_lng": 107.6098, "created_at": iso(_tnow - timedelta(days=1))}
    await db.trips.insert_one(trip_done)

    # Jejak lokasi: Bandung menuju timur (monotonik naik, koordinat valid).
    track = [(-6.9147, 107.6098), (-6.9020, 107.6300), (-6.8800, 107.6600),
             (-6.8500, 107.7000), (-6.8200, 107.7600)]
    base_t = datetime.now(timezone.utc) - timedelta(minutes=8)
    locs = []
    for i, (la, ln) in enumerate(track):
        locs.append({"id": new_id("loc"), "trip_id": trip["id"], "driver_id": drv[0]["id"],
                     "vehicle_id": veh[0]["id"], "lat": la, "lng": ln,
                     "speed": 42.0 + i * 3, "heading": 78.0,
                     "timestamp": iso(base_t + timedelta(minutes=2 * i))})
    await db.locations.insert_many(locs)

    # === Phase 6: Maintenance armada + share-link tracking ===
    _n = datetime.now(timezone.utc)
    # E8: Master Vendor/Bengkel (workshops) — dipakai maintenance_records.workshop_id.
    workshops = [
        {"id": new_id("wsh"), "name": "Auto2000 Pasteur", "phone": "022-2000111",
         "address": "Jl. Dr. Djunjunan 192", "city": "Bandung",
         "specialties": ["servis", "berkala", "ac"], "note": "Bengkel resmi — servis berkala.",
         "active": True, "created_at": now_iso()},
        {"id": new_id("wsh"), "name": "Bengkel Mitra Jaya", "phone": "022-7788990",
         "address": "Jl. Soekarno-Hatta 45", "city": "Bandung",
         "specialties": ["perbaikan", "rem", "mesin"], "note": "Spesialis kaki-kaki & rem.",
         "active": True, "created_at": now_iso()},
        {"id": new_id("wsh"), "name": "Karoseri Sinar Logam", "phone": "022-5566778",
         "address": "Jl. Raya Cibeureum 9", "city": "Cimahi",
         "specialties": ["body", "interior"], "note": "Body repair & interior.",
         "active": False, "created_at": now_iso()},
    ]
    await db.workshops.insert_many(workshops)
    _wsh_auto = workshops[0]["id"]
    _wsh_mitra = workshops[1]["id"]
    # E10: Master Jenis Service configurable (selain jenis bawaan).
    service_types = [
        {"id": new_id("svt"), "key": "ganti_oli", "name": "Ganti Oli",
         "default_interval_km": 5000, "default_interval_days": 90, "active": True, "created_at": now_iso()},
        {"id": new_id("svt"), "key": "ganti_ban", "name": "Ganti Ban",
         "default_interval_km": 40000, "default_interval_days": 730, "active": True, "created_at": now_iso()},
        {"id": new_id("svt"), "key": "spooring_balancing", "name": "Spooring & Balancing",
         "default_interval_km": 10000, "default_interval_days": 180, "active": True, "created_at": now_iso()},
    ]
    await db.service_types.insert_many(service_types)
    maintenance = [
        # Window in_progress → MEMBLOK availability veh[2] (INV-21; tanpa overlap booking aktif).
        {"id": new_id("mnt"), "vehicle_id": veh[2]["id"], "vehicle_name": veh[2]["name"],
         "type": "perbaikan", "title": "Perbaikan AC & rem", "description": "Servis besar AC + ganti kampas rem.",
         "scheduled_date": iso(_n - timedelta(days=1)), "start_date": iso(_n - timedelta(days=1)),
         "end_date": iso(_n + timedelta(days=2)), "odometer": 121000, "cost": 2500000.0,
         "workshop": "Bengkel Mitra Jaya", "workshop_id": _wsh_mitra, "status": "in_progress", "note": "Unit tidak tersedia sementara.",
         "completed_at": None, "created_by": users[1]["id"], "created_at": now_iso()},
        # Servis terjadwal mendatang veh[1] (window jauh dari booking → tak overlap).
        {"id": new_id("mnt"), "vehicle_id": veh[1]["id"], "vehicle_name": veh[1]["name"],
         "type": "servis", "title": "Servis berkala 40.000 km", "description": "Ganti oli + filter + tune up.",
         "scheduled_date": iso(_n + timedelta(days=20)), "start_date": iso(_n + timedelta(days=20)),
         "end_date": iso(_n + timedelta(days=21)), "odometer": 42000, "cost": 0.0,
         "workshop": "Auto2000 Pasteur", "workshop_id": _wsh_auto, "status": "scheduled", "note": "",
         "completed_at": None, "created_by": users[1]["id"], "created_at": now_iso()},
        # Riwayat servis selesai veh[0] (status done → tak memblok).
        {"id": new_id("mnt"), "vehicle_id": veh[0]["id"], "vehicle_name": veh[0]["name"],
         "type": "servis", "title": "Servis berkala 80.000 km", "description": "Ganti oli, filter udara, cek kaki-kaki.",
         "scheduled_date": iso(_n - timedelta(days=20)), "start_date": iso(_n - timedelta(days=20)),
         "end_date": iso(_n - timedelta(days=20)), "odometer": 80000, "cost": 1850000.0,
         "workshop": "Auto2000 Pasteur", "workshop_id": _wsh_auto, "status": "done", "note": "Selesai tepat waktu.",
         "completed_at": iso(_n - timedelta(days=19)), "created_by": users[0]["id"], "created_at": now_iso()},
    ]
    await db.maintenance_records.insert_many(maintenance)
    # Armada dalam window in_progress ditandai 'maintenance'.
    await db.vehicles.update_one({"id": veh[2]["id"]}, {"$set": {"status": "maintenance"}})

    # Share-link tracking korporat untuk trip aktif (aktif 7 hari).
    await db.trip_shares.insert_one({
        "id": new_id("shr"), "token": secrets.token_urlsafe(24), "trip_id": trip["id"],
        "vehicle_id": veh[0]["id"], "vehicle_name": veh[0]["name"],
        "label": f"Tracking {veh[0]['name']} — PT Maju Jaya",
        "expires_at": iso(_n + timedelta(days=7)), "revoked": False, "revoked_at": None,
        "last_accessed_at": None, "access_count": 0,
        "created_by": users[0]["id"], "created_at": now_iso(),
    })

    # === Phase 5: Keuangan — expenses + invoices (jaga INV-5 & INV-8) ===
    # Pengeluaran trip aktif (terkait trip → mempengaruhi trip.profit, INV-5).
    trip_expenses = [
        {"id": new_id("exp"), "booking_id": bk["id"], "trip_id": trip["id"], "category": "bbm",
         "amount": 600000.0, "note": "Solar Bandung-Bromo PP", "booking_code": bk["code"],
         "recorded_by": users[1]["id"], "created_at": now_iso()},
        {"id": new_id("exp"), "booking_id": bk["id"], "trip_id": trip["id"], "category": "tol",
         "amount": 150000.0, "note": "Tol & parkir", "booking_code": bk["code"],
         "recorded_by": users[1]["id"], "created_at": now_iso()},
        {"id": new_id("exp"), "booking_id": bk["id"], "trip_id": trip["id"], "category": "uang_jalan",
         "amount": 450000.0, "note": "Uang jalan driver 3 hari", "booking_code": bk["code"],
         "recorded_by": users[1]["id"], "created_at": now_iso()},
    ]
    # Pengeluaran booking kedua (belum jadi trip → tanpa trip_id).
    booking_expenses = [
        {"id": new_id("exp"), "booking_id": bk2["id"], "trip_id": None, "category": "bbm",
         "amount": 500000.0, "note": "Estimasi BBM Jakarta-Bandung", "booking_code": bk2["code"],
         "recorded_by": users[1]["id"], "created_at": now_iso()},
        {"id": new_id("exp"), "booking_id": bk2["id"], "trip_id": None, "category": "other",
         "amount": 120000.0, "note": "Snack & air mineral", "booking_code": bk2["code"],
         "recorded_by": users[1]["id"], "created_at": now_iso()},
    ]
    await db.expenses.insert_many(trip_expenses + booking_expenses)

    # INV-5: trip.profit == revenue - Σ expenses(trip).
    trip_exp_total = sum(e["amount"] for e in trip_expenses)
    await db.trips.update_one(
        {"id": trip["id"]},
        {"$set": {"profit": round(float(trip["revenue"]) - trip_exp_total, 2)}},
    )

    # === E11: Driver Payroll — contoh payout (draft periode berjalan + approved periode lalu) ===
    from services.payroll import build_accrual, create_payout_expense
    _tday = datetime.now(timezone.utc)
    _cur_start = _tday.replace(day=1).strftime("%Y-%m-%d")
    _cur_end = _tday.strftime("%Y-%m-%d")
    _prev_last = _tday.replace(day=1) - timedelta(days=1)
    _prev_start = _prev_last.replace(day=1).strftime("%Y-%m-%d")
    _prev_end = _prev_last.strftime("%Y-%m-%d")
    _drv0 = await db.drivers.find_one({"id": drv[0]["id"]}, {"_id": 0})
    _p_draft = await build_accrual(db, _drv0, "monthly", _cur_start, _cur_end)
    await db.driver_payouts.insert_one(dict(_p_draft))
    _p_appr = await build_accrual(db, _drv0, "monthly", _prev_start, _prev_end,
                                  bonuses=[{"label": "Bonus kehadiran", "amount": 200000.0}])
    _exp_id = await create_payout_expense(db, _p_appr)
    _p_appr.update({"status": "approved", "approver_id": users[0]["id"],
                    "approver_name": users[0]["name"], "approved_at": now_iso(),
                    "expense_id": _exp_id, "updated_at": now_iso()})
    await db.driver_payouts.insert_one(dict(_p_appr))

    # Invoice dari booking (INV-8: number unik berurutan, reset tahunan A2).
    _now = datetime.now(timezone.utc)
    _yr = now_iso()[:4]
    await db.invoices.insert_many([
        {"id": new_id("inv"), "number": f"INV-{_yr}-0001", "booking_id": bk["id"], "customer_id": cus[0]["id"],
         "customer_name": cus[0]["name"], "booking_code": bk["code"], "amount": float(total),
         "status": "sent", "issued_at": now_iso(), "due_at": iso(_now + timedelta(days=7)),
         "notes": "Pembayaran via transfer BCA", "created_by": users[0]["id"], "created_at": now_iso()},
        {"id": new_id("inv"), "number": f"INV-{_yr}-0002", "booking_id": bk2["id"], "customer_id": cus[1]["id"],
         "customer_name": cus[1]["name"], "booking_code": bk2["code"], "amount": float(total2),
         "status": "draft", "issued_at": now_iso(), "due_at": iso(_now + timedelta(days=10)),
         "notes": "", "created_by": users[0]["id"], "created_at": now_iso()},
    ])

    # A2: inisialisasi counter atomik agar nomor berikutnya tak menabrak seed.
    await db.counters.insert_many([
        {"id": "booking", "seq": 2},          # seed: BK-0001, BK-0002 -> next BK-0003
        {"id": f"invoice:{_yr}", "seq": 2},   # seed: INV-<yr>-0001/0002 -> next 0003
        {"id": f"quotation:{_yr}", "seq": 1}, # seed: QUO-<yr>-0001 -> next 0002
    ])


    # === Phase 4: CRM pipeline — leads lintas tahap + timeline + broadcast contoh ===
    ops_id, owner_id = users[1]["id"], users[0]["id"]

    def _lead(name, phone, email, source, stage, agent, dest, days, pax, msg, value, extra=None):
        d = {"id": new_id("led"), "customer_name": name, "phone": phone,
             "phone_normalized": _norm_phone(phone), "email": email,
             "source": source, "stage": stage, "assigned_to": agent, "destination": dest,
             "trip_date": iso(datetime.now(timezone.utc) + timedelta(days=days)) if days is not None else None,
             "pax": pax, "message": msg, "value": float(value), "quotation_amount": float(value),
             "converted_customer_id": None, "linked_customer_id": None,
             "created_at": now_iso(), "last_activity_at": now_iso()}
        if extra:
            d.update(extra)
        return d

    leads = [
        _lead("Budi Santoso", "08150001111", "budi@mail.com", "website", "new", ops_id, "Bali", 20, 10,
              "Mau sewa Hiace untuk wisata keluarga", 0),
        _lead("PT Sinar Event", "08151002222", "event@sinar.id", "manual", "contacted", ops_id, "Yogyakarta", 6, 25,
              "Gathering kantor 25 orang", 12000000, {"contacted_at": now_iso()}),
        _lead("Rina Wedding Organizer", "08152003333", "rina@wo.id", "whatsapp", "quoted", ops_id, "Gunung Bromo", 3, 14,
              "Antar-jemput tamu acara", 8500000, {"contacted_at": now_iso()}),
        _lead("Komunitas Goes Bandung", "08153004444", "goes@komunitas.id", "website", "negotiation", owner_id, "Dataran Tinggi Dieng", 1, 30,
              "Trip komunitas sepeda, butuh 2 unit", 15000000, {"contacted_at": now_iso()}),
        _lead("CV Sentosa Wisata", "08154005555", "sales@sentosa.id", "manual", "won", ops_id, "Bandung", 12, 19,
              "Repeat order rombongan", 20000000,
              {"contacted_at": now_iso(), "won_at": now_iso(),
               "converted_customer_id": cus[2]["id"], "linked_customer_id": cus[2]["id"]}),
        _lead("Andre Backpacker", "08155006666", "andre@mail.com", "website", "lost", ops_id, "Bali", None, 6,
              "Cari yang termurah", 5000000, {"lost_at": now_iso(), "lost_reason": "Budget tidak sesuai"}),
    ]
    await db.leads.insert_many(leads)

    await db.lead_activities.insert_many([
        {"id": new_id("lac"), "lead_id": leads[0]["id"], "user_id": None, "type": "created",
         "text": "Lead masuk dari website (form penawaran)", "from_stage": None, "to_stage": None, "created_at": now_iso()},
        {"id": new_id("lac"), "lead_id": leads[1]["id"], "user_id": ops_id, "type": "created",
         "text": "Lead dibuat manual oleh admin", "from_stage": None, "to_stage": None, "created_at": now_iso()},
        {"id": new_id("lac"), "lead_id": leads[1]["id"], "user_id": ops_id, "type": "stage_change",
         "text": None, "from_stage": "new", "to_stage": "contacted", "created_at": now_iso()},
        {"id": new_id("lac"), "lead_id": leads[1]["id"], "user_id": ops_id, "type": "note",
         "text": "Sudah dihubungi via WA, menunggu konfirmasi tanggal.", "from_stage": None, "to_stage": None, "created_at": now_iso()},
    ])

    _quoted = sum(1 for x in leads if x["stage"] == "quoted")
    await db.broadcasts.insert_one({"id": new_id("brd"), "title": "Promo Akhir Pekan",
        "message": "Diskon 10% untuk sewa Hiace Premio akhir pekan ini. Balas YA untuk penawaran.",
        "segment": {"stage": "quoted", "source": None}, "scheduled_at": None, "status": "draft",
        "recipients_count": _quoted, "created_by": ops_id, "created_at": now_iso()})

    # === Phase 9 / B2: contoh penawaran (QUO) berstatus 'sent' terhubung lead 'quoted' ===
    _rina = leads[2]
    _quo_items = [
        {"label": "Sewa unit (3 hari)", "amount": 4500000},
        {"label": "Jasa driver (3 hari)", "amount": 750000},
        {"label": "Tol & parkir (estimasi)", "amount": 600000},
    ]
    _quo_total = sum(i["amount"] for i in _quo_items)
    await db.quotations.insert_one({
        "id": new_id("quo"), "number": f"QUO-{_yr}-0001",
        "lead_id": _rina["id"], "customer_id": None,
        "customer_name": _rina["customer_name"], "phone": _rina["phone"],
        "phone_normalized": "+62" + _rina["phone"][1:], "email": _rina["email"],
        "destination": _rina["destination"], "trip_date": _rina["trip_date"], "pax": _rina["pax"],
        "items": _quo_items, "subtotal": _quo_total, "total": _quo_total,
        "status": "sent", "valid_until": iso(datetime.now(timezone.utc) + timedelta(days=7)),
        "notes": "Termasuk driver & tol. Belum termasuk BBM luar kota.", "booking_id": None,
        "sent_at": now_iso(), "created_by": ops_id, "created_at": now_iso(), "updated_at": now_iso()})


    # === Phase 3 / P10-FASE 3: konten destinasi immersif (scroll-story + peta rute) ===
    def _dest(slug, name, region, desc, img, hotels, *, intro="", gallery=None, highlights=None,
              itinerary=None, route_points=None, faqs=None, best_time="", lat=None, lng=None, popular=True):
        return {"id": new_id("dst"), "slug": slug, "name": name, "region": region,
                "description": desc, "intro": intro or desc, "hero_image": img,
                "gallery": gallery or [img], "hotel_recommendations": hotels,
                "highlights": highlights or [], "itinerary": itinerary or [],
                "route_points": route_points or [], "faqs": faqs or [],
                "best_time": best_time, "lat": lat, "lng": lng, "tour_scenes": [],
                "popular": popular, "created_at": now_iso()}

    await db.pickup_points.insert_many([
        # INV-REF-02 batch 2: master TITIK JEMPUT (relasi bookings.origin — bukan teks bebas).
        {"id": new_id("pkp"), "name": "Bandung", "created_at": now_iso()},
        {"id": new_id("pkp"), "name": "Jakarta", "created_at": now_iso()},
        {"id": new_id("pkp"), "name": "Bandara Soekarno-Hatta", "created_at": now_iso()},
        {"id": new_id("pkp"), "name": "Stasiun Bandung", "created_at": now_iso()},
    ])
    await db.cities.insert_many([
        # INV-REF-02 batch 5: master KOTA (relasi customers.city & partners.city).
        # WAJIB mencakup semua nilai city yang dipakai seed customers/partners.
        {"id": new_id("cty"), "name": n, "active": True, "created_at": now_iso()}
        for n in ("Bandung", "Jakarta", "Cimahi", "Bekasi", "Bogor", "Surabaya")
    ])
    await db.destinations.insert_many([
        # INV-REF-02: destinasi OPERASIONAL (master utk booking ERP) — status 'draft' agar
        # TIDAK tayang di situs publik (visibility_filter menuntut 'published').
        {"id": new_id("dst"), "slug": "bandung", "name": "Bandung", "region": "jawa_barat",
         "status": "draft", "source": "ops", "description": "Destinasi operasional (antar-kota).",
         "created_at": now_iso()},
        {"id": new_id("dst"), "slug": "jakarta", "name": "Jakarta", "region": "dki",
         "status": "draft", "source": "ops", "description": "Destinasi operasional (antar-kota).",
         "created_at": now_iso()},
    ])
    await db.destinations.insert_many([
        _dest("bali", "Bali", "bali",
              "Pulau Dewata: pura ikonik, pantai sunset, dan budaya yang hidup. Cocok untuk wisata keluarga & korporat.",
              "https://images.unsplash.com/photo-1537996194471-e657df975ab4?q=80&w=1600&auto=format&fit=crop",
              [{"name": "The Anvaya Beach Resort", "rating": 4.7, "price_range": "Rp 1,2jt-2,5jt"},
               {"name": "Padma Resort Legian", "rating": 4.6, "price_range": "Rp 1,5jt-3jt"}],
              intro="Dari Bandung menuju Pulau Dewata: perjalanan lintas Jawa yang dirancang nyaman dengan rehat terjadwal dan driver berpengalaman.",
              best_time="April – Oktober (musim kemarau)", lat=-8.4095, lng=115.1889,
              highlights=[{"title": "Pura & Budaya", "desc": "Tanah Lot, Uluwatu, dan upacara adat yang hidup."},
                          {"title": "Pantai & Sunset", "desc": "Kuta, Seminyak, hingga tebing Nusa Penida."},
                          {"title": "Kuliner & MICE", "desc": "Venue korporat, beach club, dan kuliner kelas dunia."}],
              itinerary=[{"day": "Hari 1", "title": "Bandung → Penyeberangan", "desc": "Berangkat malam, rehat & makan di Jawa Tengah/Timur."},
                         {"day": "Hari 2", "title": "Tiba di Bali", "desc": "Check-in, Tanah Lot, sunset di pantai selatan."},
                         {"day": "Hari 3", "title": "Eksplorasi", "desc": "Ubud, pura, atau aktivitas air sesuai minat."},
                         {"day": "Hari 4", "title": "Kembali", "desc": "Oleh-oleh & perjalanan pulang yang nyaman."}],
              route_points=[{"name": "Bandung", "lat": -6.9147, "lng": 107.6098, "desc": "Titik kumpul & keberangkatan. Briefing rute dan kebutuhan rombongan."},
                            {"name": "Yogyakarta", "lat": -7.7956, "lng": 110.3695, "desc": "Rehat & makan, opsi mampir Malioboro sebelum lanjut ke timur."},
                            {"name": "Surabaya", "lat": -7.2575, "lng": 112.7521, "desc": "Transit Kota Pahlawan, cek armada & istirahat driver."},
                            {"name": "Gilimanuk", "lat": -8.1626, "lng": 114.4341, "desc": "Menyeberang Selat Bali dengan ferry (±1 jam)."},
                            {"name": "Denpasar, Bali", "lat": -8.6705, "lng": 115.2126, "desc": "Tiba di Pulau Dewata, mulai eksplorasi pura & pantai."}],
              faqs=[{"q": "Berapa lama perjalanan Bandung–Bali?", "a": "Rata-rata 16–20 jam termasuk penyeberangan, biasanya berangkat malam agar pagi sudah tiba."},
                    {"q": "Apakah tiket ferry termasuk?", "a": "Ferry penyeberangan dapat kami uruskan dan dimasukkan dalam penawaran sesuai kebutuhan."},
                    {"q": "Cocok untuk rombongan berapa orang?", "a": "Hiace 14 kursi untuk keluarga/korporat kecil; tersedia Elf 19 & bus untuk rombongan besar."}]),
        _dest("bromo", "Gunung Bromo", "jawa_timur",
              "Negeri di atas awan dengan sunrise legendaris di Penanjakan. Perjalanan favorit dari Malang & Surabaya.",
              "https://images.unsplash.com/photo-1589182337358-2cb63099350c?q=80&w=1600&auto=format&fit=crop",
              [{"name": "Jiwa Jawa Resort Bromo", "rating": 4.5, "price_range": "Rp 900rb-1,8jt"},
               {"name": "Lava View Lodge", "rating": 4.2, "price_range": "Rp 700rb-1,2jt"}],
              intro="Berburu sunrise di negeri atas awan. Rute dirancang agar tiba menjelang dini hari untuk momen matahari terbit terbaik.",
              best_time="Mei – September (langit cerah)", lat=-7.9425, lng=112.9530,
              highlights=[{"title": "Sunrise Penanjakan", "desc": "Panorama matahari terbit di antara lautan awan."},
                          {"title": "Lautan Pasir", "desc": "Berkuda menuju kawah & Pura Luhur Poten."},
                          {"title": "Bukit Teletubbies", "desc": "Padang savana hijau yang ikonik."}],
              itinerary=[{"day": "Hari 1", "title": "Bandung → Probolinggo", "desc": "Perjalanan malam, rehat di rest area utama."},
                         {"day": "Hari 2", "title": "Sunrise Bromo", "desc": "Dini hari menuju Penanjakan, lanjut kawah & savana."},
                         {"day": "Hari 3", "title": "Kembali", "desc": "Sarapan, oleh-oleh, perjalanan pulang."}],
              route_points=[{"name": "Bandung", "lat": -6.9147, "lng": 107.6098, "desc": "Keberangkatan & briefing rute."},
                            {"name": "Yogyakarta", "lat": -7.7956, "lng": 110.3695, "desc": "Rehat & makan tengah perjalanan."},
                            {"name": "Surabaya", "lat": -7.2575, "lng": 112.7521, "desc": "Transit & istirahat driver."},
                            {"name": "Probolinggo", "lat": -7.7543, "lng": 113.2159, "desc": "Gerbang menuju kawasan Bromo."},
                            {"name": "Gunung Bromo", "lat": -7.9425, "lng": 112.9530, "desc": "Tiba menjelang dini hari untuk sunrise."}],
              faqs=[{"q": "Jam berapa berangkat untuk sunrise?", "a": "Umumnya dari penginapan ±03.00 dini hari menuju titik Penanjakan."},
                    {"q": "Apakah jeep ke kawah termasuk?", "a": "Jeep 4x4 lokal dapat kami koordinasikan dan masuk penawaran bila diminta."},
                    {"q": "Perlu bawa apa?", "a": "Jaket tebal, sarung tangan, dan sepatu nyaman — suhu bisa di bawah 10°C."}]),
        _dest("yogyakarta", "Yogyakarta", "jawa_tengah",
              "Borobudur, Prambanan, Malioboro, dan kuliner gudeg. Kota budaya yang ramah keluarga & rombongan.",
              "https://images.unsplash.com/photo-1596402184320-417e7178b2cd?q=80&w=1600&auto=format&fit=crop",
              [{"name": "Phoenix Hotel Yogyakarta", "rating": 4.6, "price_range": "Rp 800rb-1,6jt"},
               {"name": "Greenhost Boutique Hotel", "rating": 4.4, "price_range": "Rp 600rb-1,2jt"}],
              intro="Kota budaya yang lengkap: candi warisan dunia, keraton, dan kuliner legendaris — nyaman dijangkau dari Bandung.",
              best_time="Sepanjang tahun (favorit Apr–Okt)", lat=-7.7956, lng=110.3695,
              highlights=[{"title": "Candi Warisan Dunia", "desc": "Borobudur & Prambanan, megah dan ikonik."},
                          {"title": "Malioboro & Keraton", "desc": "Belanja, kuliner, dan budaya keraton."},
                          {"title": "Kuliner Gudeg", "desc": "Cita rasa khas yang wajib dicoba."}],
              itinerary=[{"day": "Hari 1", "title": "Bandung → Yogyakarta", "desc": "Perjalanan siang/malam, tiba & check-in."},
                         {"day": "Hari 2", "title": "Candi & Kota", "desc": "Borobudur pagi, Prambanan sore, Malioboro malam."},
                         {"day": "Hari 3", "title": "Kembali", "desc": "Belanja oleh-oleh bakpia & gudeg, pulang."}],
              route_points=[{"name": "Bandung", "lat": -6.9147, "lng": 107.6098, "desc": "Keberangkatan & briefing."},
                            {"name": "Purwokerto", "lat": -7.4216, "lng": 109.2345, "desc": "Rehat & makan di jalur selatan."},
                            {"name": "Magelang", "lat": -7.4706, "lng": 110.2178, "desc": "Mendekati kawasan Borobudur."},
                            {"name": "Yogyakarta", "lat": -7.7956, "lng": 110.3695, "desc": "Tiba di kota budaya, mulai eksplorasi."}],
              faqs=[{"q": "Borobudur dan Prambanan bisa sehari?", "a": "Bisa — Borobudur pagi dan Prambanan sore, dengan pengaturan waktu yang efisien."},
                    {"q": "Apakah cocok untuk study tour?", "a": "Sangat cocok. Tersedia armada besar dan koordinasi jadwal untuk rombongan sekolah/kampus."},
                    {"q": "Berapa lama dari Bandung?", "a": "Sekitar 8–10 jam tergantung kondisi lalu lintas dan titik rehat."}]),
        _dest("dieng", "Dataran Tinggi Dieng", "jawa_tengah",
              "Telaga Warna, kompleks candi tertua, dan negeri di atas awan Sikunir. Sejuk sepanjang tahun.",
              "https://images.unsplash.com/photo-1591019479261-1a103585c559?q=80&w=1600&auto=format&fit=crop",
              [{"name": "Dieng Plateau Homestay", "rating": 4.1, "price_range": "Rp 300rb-700rb"}],
              intro="Negeri di atas awan yang sejuk: golden sunrise Sikunir, telaga warna-warni, dan candi tertua di Jawa.",
              best_time="Juni – Agustus (dingin & cerah)", lat=-7.2059, lng=109.9079, popular=False,
              highlights=[{"title": "Golden Sunrise Sikunir", "desc": "Matahari terbit keemasan di atas lautan awan."},
                          {"title": "Telaga Warna", "desc": "Danau dengan gradasi warna yang memukau."},
                          {"title": "Candi Arjuna", "desc": "Kompleks candi Hindu tertua di Jawa."}],
              itinerary=[{"day": "Hari 1", "title": "Bandung → Wonosobo", "desc": "Perjalanan menuju dataran tinggi, check-in."},
                         {"day": "Hari 2", "title": "Sunrise & Telaga", "desc": "Sikunir dini hari, Telaga Warna & Candi Arjuna."},
                         {"day": "Hari 3", "title": "Kembali", "desc": "Oleh-oleh carica & purwaceng, pulang."}],
              route_points=[{"name": "Bandung", "lat": -6.9147, "lng": 107.6098, "desc": "Keberangkatan & briefing."},
                            {"name": "Purwokerto", "lat": -7.4216, "lng": 109.2345, "desc": "Rehat di jalur selatan."},
                            {"name": "Wonosobo", "lat": -7.3598, "lng": 109.9000, "desc": "Gerbang menuju Dieng."},
                            {"name": "Dataran Tinggi Dieng", "lat": -7.2059, "lng": 109.9079, "desc": "Tiba di negeri atas awan."}],
              faqs=[{"q": "Sedingin apa Dieng?", "a": "Suhu malam bisa 5–10°C, bahkan mendekati 0°C di musim kemarau. Bawa pakaian hangat."},
                    {"q": "Sikunir jauh dari penginapan?", "a": "Sekitar 30–45 menit; berangkat dini hari untuk golden sunrise."},
                    {"q": "Cocok untuk keluarga?", "a": "Cocok, namun perhatikan suhu dingin untuk anak-anak dan lansia."}]),
    ])

    def _art(slug, title, excerpt, cover, body, *, category="Tips", featured=False,
             read_minutes=5, tags=None, days_ago=0):
        return {"id": new_id("art"), "slug": slug, "title": title, "excerpt": excerpt,
                "cover_image": cover, "body": body, "author": "Tim RahazaTrans",
                "category": category, "featured": bool(featured), "read_minutes": int(read_minutes),
                "tags": tags or ["tips", "wisata"], "published": True,
                "published_at": iso(_now - timedelta(days=days_ago)), "created_at": now_iso()}

    await db.articles.insert_many([
        _art("panduan-lengkap-wisata-jawa-bali", "Panduan Lengkap Wisata Jawa–Bali dengan Hiace Premium",
             "Dari menyusun itinerary, memilih armada, hingga mengatur anggaran — semua yang perlu Anda tahu sebelum berangkat.",
             "https://images.unsplash.com/photo-1537996194471-e657df975ab4?q=80&w=1600&auto=format&fit=crop",
             "Merencanakan perjalanan lintas Jawa hingga Bali terasa rumit bila dilakukan sendiri. Namun dengan persiapan yang tepat, "
             "liburan rombongan bisa berjalan mulus, hemat, dan berkesan.\n\n"
             "Mulailah dari menentukan destinasi utama dan titik singgah. Rute Bandung–Yogyakarta–Bromo–Bali memiliki banyak rest area "
             "dan kuliner khas yang sayang dilewatkan. Bagi perjalanan menjadi etape harian agar driver tetap bugar dan penumpang nyaman.\n\n"
             "Pilih armada sesuai jumlah penumpang: Hiace Premio 14 kursi ideal untuk keluarga atau korporat kecil, sementara Elf 19 kursi "
             "cocok untuk rombongan besar. Pastikan fitur AC double blower, kursi reclining, dan hiburan tersedia untuk perjalanan jarak jauh.\n\n"
             "Terakhir, susun anggaran transparan: sewa unit, jasa driver, BBM, tol, dan penyeberangan ferry bila ke Bali. Gunakan kalkulator "
             "estimasi kami untuk gambaran biaya, lalu ajukan penawaran agar tim kami menyiapkan rincian final.",
             category="Itinerary", featured=True, read_minutes=8, tags=["panduan", "jawa-bali"], days_ago=0),
        _art("tips-sewa-hiace-keluarga", "5 Tips Sewa Hiace untuk Liburan Keluarga",
             "Agar perjalanan keluarga nyaman dan hemat, perhatikan kapasitas, fitur, dan jadwal driver.",
             "https://images.unsplash.com/photo-1488646953014-85cb44e25828?q=80&w=1600&auto=format&fit=crop",
             "Memilih armada yang tepat membuat liburan jauh lebih nyaman.\n\n"
             "Pastikan kapasitas sesuai jumlah penumpang, fitur seperti AC double blower & kursi reclining tersedia, dan driver beristirahat cukup.\n\n"
             "Rencanakan rute dengan buffer waktu, dan konfirmasi titik jemput sehari sebelumnya agar tidak ada penumpang yang tertinggal.",
             category="Tips", read_minutes=4, tags=["tips", "keluarga"], days_ago=4),
        _art("rute-bandung-bromo", "Itinerary 3 Hari Bandung–Bromo yang Efisien",
             "Susun rute Bandung–Bromo agar tiba tepat untuk sunrise tanpa kelelahan di jalan.",
             "https://images.unsplash.com/photo-1604999333679-b86d54738315?q=80&w=1600&auto=format&fit=crop",
             "Hari 1: berangkat sore dari Bandung, istirahat di rest area strategis di jalur selatan.\n\n"
             "Hari 2: tiba dini hari di Penanjakan untuk sunrise, lanjut kawah & Pasir Berbisik, kemudian Bukit Teletubbies.\n\n"
             "Hari 3: perjalanan pulang dengan singgah kuliner. Gunakan armada ber-AC dengan driver berpengalaman medan pegunungan.",
             category="Itinerary", read_minutes=6, tags=["itinerary", "bromo"], days_ago=8),
        _art("korporat-transport-aman", "Transportasi Korporat: Standar Keamanan yang Wajib Ada",
             "Untuk perjalanan dinas & gathering kantor, keselamatan dan ketepatan waktu adalah prioritas.",
             "https://images.unsplash.com/photo-1556122071-e404eaedb77f?q=80&w=1600&auto=format&fit=crop",
             "Armada korporat wajib memiliki dokumen KIR & pajak aktif, driver ber-SIM valid, serta pelacakan GPS real-time.\n\n"
             "Pelacakan perjalanan memudahkan koordinator memantau rombongan dan tiba tepat waktu di setiap agenda.\n\n"
             "RahazaTrans menyediakan laporan perjalanan dan invoice resmi untuk kebutuhan reimbursement perusahaan.",
             category="Korporat", read_minutes=5, tags=["korporat", "keamanan"], days_ago=12),
        _art("memilih-destinasi-musim-liburan", "Memilih Destinasi Tepat di Musim Liburan",
             "Hindari padatnya wisata dengan memilih waktu dan tujuan yang pas — dari Dieng yang sejuk hingga Yogyakarta yang ramah keluarga.",
             "https://images.unsplash.com/photo-1591019479261-1a103585c559?q=80&w=1600&auto=format&fit=crop",
             "Musim liburan identik dengan keramaian. Memilih destinasi dan waktu yang tepat membuat pengalaman lebih nyaman.\n\n"
             "Dataran Tinggi Dieng menawarkan suasana sejuk dan golden sunrise Sikunir, cocok untuk yang ingin menghindari hiruk-pikuk.\n\n"
             "Yogyakarta tetap menjadi favorit keluarga dengan candi warisan dunia, Malioboro, dan kuliner gudeg yang melegenda.",
             category="Destinasi", read_minutes=5, tags=["destinasi", "liburan"], days_ago=16),
        _art("estimasi-biaya-sewa-transparan", "Cara Membaca Estimasi Biaya Sewa yang Transparan",
             "Pahami komponen biaya sewa — unit, driver, BBM, tol — agar tidak ada kejutan saat penawaran final.",
             "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?q=80&w=1600&auto=format&fit=crop",
             "Harga sewa yang transparan terdiri dari beberapa komponen yang jelas.\n\n"
             "Sewa unit dihitung per hari sesuai tipe armada, ditambah jasa driver dan estimasi BBM berdasarkan jarak tempuh.\n\n"
             "Komponen tol, parkir, dan penyeberangan ditampilkan terpisah. Gunakan kalkulator kami untuk gambaran awal sebelum penawaran resmi.",
             category="Tips", read_minutes=4, tags=["tips", "biaya"], days_ago=20),
    ])

    await db.testimonials.insert_many([
        {"id": new_id("tst"), "name": "Andi Pratama", "role": "HR Manager, PT Maju Jaya",
         "quote": "Armada bersih, driver ramah, dan pelacakan real-time sangat membantu memantau rombongan kantor.",
         "rating": 5, "avatar": "https://i.pravatar.cc/120?img=12", "created_at": now_iso()},
        {"id": new_id("tst"), "name": "Sinta Dewi", "role": "Travel Organizer",
         "quote": "Booking gampang, harga transparan lewat kalkulator, dan tim responsif. Langganan untuk trip Jawa–Bali.",
         "rating": 5, "avatar": "https://i.pravatar.cc/120?img=45", "created_at": now_iso()},
        {"id": new_id("tst"), "name": "Keluarga Wijaya", "role": "Wisata Keluarga",
         "quote": "Hiace Premio-nya nyaman untuk anak-anak. Sunrise Bromo jadi pengalaman tak terlupakan.",
         "rating": 4, "avatar": "https://i.pravatar.cc/120?img=33", "created_at": now_iso()},
    ])

    # === Phase 9 / B3: Light CMS — paket wisata & promo (dikelola via menu Konten) ===
    # Relasi paket → destinasi memakai ID (bukan mencocokkan nama): mengganti nama destinasi
    # tidak boleh memutus relasi. Field `destination` (teks) dipertahankan untuk tampilan.
    _dst_by_name = {d.get("name"): d.get("id") for d in
                    await db.destinations.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(100)}
    await db.packages.insert_many([
        {"id": new_id("pkg"), "slug": "bromo-sunrise-3h2m", "name": "Bromo Sunrise 3H2M",
         "destination": "Gunung Bromo", "destination_id": _dst_by_name.get("Gunung Bromo", ""),
         "description": "Paket sunrise Penanjakan + kawah, termasuk Hiace & driver.",
         "days": 3, "price_from": 4500000, "vehicle_type": "hiace_premio",
         "pax_min": 6, "pax_max": 14,
         "includes": ["Hiace Premio", "Driver berpengalaman", "BBM dalam kota"],
         "image_url": "https://images.unsplash.com/photo-1589182337358-2cb63099350c?q=80&w=1600&auto=format&fit=crop",
         "active": True, "created_at": now_iso()},
        {"id": new_id("pkg"), "slug": "jogja-city-tour-2h1m", "name": "Jogja City Tour 2H1M",
         "destination": "Yogyakarta", "destination_id": _dst_by_name.get("Yogyakarta", ""),
         "description": "Borobudur, Prambanan, Malioboro dengan armada nyaman.",
         "days": 2, "price_from": 2800000, "vehicle_type": "hiace",
         "pax_min": 4, "pax_max": 19,
         "includes": ["Elf/Hiace", "Driver", "Tol & parkir"],
         "image_url": "https://images.unsplash.com/photo-1596402184320-417e7178b2cd?q=80&w=1600&auto=format&fit=crop",
         "active": True, "created_at": now_iso()},
    ])
    # Syarat promo disimpan sebagai DATA (min_days/min_amount/vehicle_types/weekend_only/max_uses)
    # supaya server bisa menegakkannya di checkout — dulu syarat hanya tertulis di deskripsi.
    await db.promos.insert_many([
        {"id": new_id("pro"), "code": "AKHIRPEKAN10", "title": "Diskon Akhir Pekan 10%",
         "description": "Potongan 10% untuk sewa Hiace Premio keberangkatan Sabtu/Minggu.",
         "discount_type": "percent", "discount_value": 10,
         "valid_from": iso(datetime.now(timezone.utc) - timedelta(days=1))[:10],
         "valid_until": iso(datetime.now(timezone.utc) + timedelta(days=30))[:10],
         "min_days": 1, "min_amount": 0, "vehicle_types": ["hiace_premio"],
         "services": ["daily_rental"], "weekend_only": True, "max_uses": 100, "used_count": 0,
         "active": True, "position": 1, "created_at": now_iso()},
        {"id": new_id("pro"), "code": "GATHERING500", "title": "Cashback Gathering Rp500rb",
         "description": "Cashback Rp500.000 untuk sewa rombongan minimal 2 hari.",
         "discount_type": "amount", "discount_value": 500000,
         "valid_from": iso(datetime.now(timezone.utc) - timedelta(days=1))[:10],
         "valid_until": iso(datetime.now(timezone.utc) + timedelta(days=45))[:10],
         "min_days": 2, "min_amount": 3000000, "vehicle_types": [], "services": ["daily_rental"],
         "weekend_only": False, "max_uses": 50, "used_count": 0,
         "active": True, "position": 2, "created_at": now_iso()},
        {"id": new_id("pro"), "code": "BANDARA50", "title": "Potongan Antar-Jemput Rp50rb",
         "description": "Potongan Rp50.000 untuk antar-jemput bandara.",
         "discount_type": "amount", "discount_value": 50000,
         "valid_from": iso(datetime.now(timezone.utc) - timedelta(days=1))[:10],
         "valid_until": iso(datetime.now(timezone.utc) + timedelta(days=60))[:10],
         "min_days": 0, "min_amount": 0, "vehicle_types": [], "services": ["airport_transfer"],
         "weekend_only": False, "max_uses": 200, "used_count": 0,
         "active": True, "position": 3, "created_at": now_iso()},
    ])

    # === CMS-10: riwayat versi AWAL untuk konten demo ===
    # Tanpa ini panel "Riwayat versi" kosong di instalasi baru dan pemilik menyangka fiturnya
    # tidak bekerja. Snapshot diambil dari dokumen demo YANG BENAR-BENAR ADA (bukan data
    # karangan), dengan aksi `create` — persis seperti yang ditulis API saat konten dibuat.
    for _res in ("destinations", "packages", "articles", "testimonials", "promos"):
        _docs = await db[_res].find({}, {"_id": 0}).to_list(500)
        _rows = [{
            "id": new_id("cvr"), "resource": _res, "item_id": _d["id"], "action": "create",
            "version": 1, "snapshot": _d, "changed_fields": [],
            "label": _d.get("name") or _d.get("title") or _d.get("code") or _d["id"],
            "actor_id": "", "actor_name": "Data demo",
            "created_at": _d.get("created_at") or now_iso(),
        } for _d in _docs if _d.get("id")]
        if _rows:
            await db.content_versions.insert_many(_rows)

    # === Rute ANTAR-JEMPUT BANDARA + tarif FLAT per tipe armada (koleksi transfer_routes) ===
    # Tarif contoh; owner mengubahnya di Pengaturan → Alur Booking → Rute Antar-Jemput.
    # Tipe armada yang TIDAK tercantum di `rates` memang tidak dilayani pada rute itu
    # (mesin harga menolak, bukan mengarang tarif).
    await db.transfer_routes.insert_many([
        {"id": new_id("trt"), "code": "BDO-CGK", "name": "Bandung → Soekarno-Hatta (CGK)",
         "from_label": "Bandung", "to_label": "Bandara Soekarno-Hatta (CGK)",
         "airport_code": "CGK", "duration_minutes": 240,
         "rates": {"avanza": 950000, "hiace": 1400000, "hiace_premio": 1700000},
         "notes": "Termasuk driver, tol, dan parkir bandara.", "active": True, "position": 1,
         "created_at": now_iso(), "updated_at": now_iso()},
        {"id": new_id("trt"), "code": "CGK-BDO", "name": "Soekarno-Hatta (CGK) → Bandung",
         "from_label": "Bandara Soekarno-Hatta (CGK)", "to_label": "Bandung",
         "airport_code": "CGK", "duration_minutes": 240,
         "rates": {"avanza": 950000, "hiace": 1400000, "hiace_premio": 1700000},
         "notes": "Penjemputan di Terminal kedatangan, termasuk tunggu 60 menit.",
         "active": True, "position": 2, "created_at": now_iso(), "updated_at": now_iso()},
        {"id": new_id("trt"), "code": "BDO-KJT", "name": "Bandung → Kertajati (KJT)",
         "from_label": "Bandung", "to_label": "Bandara Kertajati (KJT)",
         "airport_code": "KJT", "duration_minutes": 150,
         "rates": {"avanza": 700000, "hiace": 1100000, "hiace_premio": 1350000,
                   "elf": 1500000},
         "notes": "Rute via Cisumdawu.", "active": True, "position": 3,
         "created_at": now_iso(), "updated_at": now_iso()},
    ])

    await db.settings.insert_one({"key": "company_info", "value": {
        "name": "RahazaTrans", "city": "Bandung", "phone": "0811-2000-300",
        "whatsapp": "6281120003000", "email": "halo@rahazatrans.id",
        "address": "Jl. Asia Afrika No. 1, Bandung", "service_area": "Jawa & Bali"}})
    await db.settings.insert_one({"key": "theme_config", "value": {"preset": "azure", "mode": "light"}})
    await db.settings.insert_one({"key": "map_provider", "value": "leaflet_osm"})
    await db.settings.insert_one({"key": "pricing_defaults", "value": {
        "dp_percent": 30, "cancellation_policy": "Pembatalan H-3 dikenakan 50% DP; H-1 hangus.",
        "min_rental_hours": 12}})
    await db.settings.insert_one({"key": "operational", "value": {
        "work_hours": {"open": "08:00", "close": "17:00"},
        "holidays": [iso(_now + timedelta(days=30))[:10], iso(_now + timedelta(days=31))[:10]]}})
    # B1 — Pricing Engine: tarif/surcharge/DP konfigurabel (diedit di Pengaturan).
    await db.settings.insert_one({"key": "pricing_rules", "value": {
        "day_rates": {"hiace_premio": 1500000, "hiace": 1200000, "elf": 2000000,
                      "bus": 2500000, "avanza": 900000},
        # fuel_per_km DIHAPUS: komponen berbasis jarak tidak lagi memengaruhi harga
        # (jarak dulu diisi pengunjung lewat penggeser → harga tak bisa dipertanggungjawabkan).
        "default_day_rate": 1200000, "driver_fee_per_day": 250000,
        "toll_parking_per_day": 200000, "weekend_surcharge_percent": 20,
        "holiday_surcharge_percent": 30, "dp_percent": 30, "rounding": 1000}})

    # === Alur PEMESANAN ONLINE (mode + batas waktu DP + instruksi transfer) ===
    # mode 'hold_dp'      : pesanan tamu langsung menahan unit, DP dalam `hold_hours` jam.
    # mode 'ops_approval' : pesanan masuk 'pending', ops ACC dulu → baru hold + minta DP.
    await db.settings.insert_one({"key": "booking_flow", "value": {
        "mode": "hold_dp", "hold_hours": 2, "approval_hold_hours": 24, "approval_sla_hours": 6,
        "min_lead_hours": 4, "max_advance_days": 180, "min_days": 1, "max_days": 30,
        "transfer_buffer_minutes": 120,
        "enabled_services": ["daily_rental", "airport_transfer"],
        "payment": {
            "bank_accounts": [
                {"bank": "BCA", "number": "1234567890", "holder": "PT RahazaTrans"},
                {"bank": "Mandiri", "number": "9876543210", "holder": "PT RahazaTrans"},
            ],
            "qris_media_id": "",
            "instructions": ("Transfer DP sesuai nominal ke salah satu rekening di atas, lalu "
                             "unggah bukti transfer pada halaman status pesanan. Tim kami "
                             "memverifikasi maksimal 1x24 jam kerja."),
        },
        "cancellation_policy": "Pembatalan H-3 dikenakan 50% DP; H-1 hangus.",
        "terms": ("Harga sudah termasuk driver, tol, dan parkir sesuai rincian. BBM luar kota, "
                  "tiket masuk wisata, dan penginapan driver ditanggung penyewa."),
    }})

    # === E1 — Event Bus + Automation + WhatsApp Adapter (mock-first) ===
    from services.whatsapp import DEFAULT_CONFIG, DEFAULT_TEMPLATES
    from services.automation import default_rules
    await db.settings.insert_one({"key": "wa_config", "value": dict(DEFAULT_CONFIG)})
    await db.settings.insert_one({"key": "wa_templates", "value": dict(DEFAULT_TEMPLATES)})
    # E4 BI Cockpit: ad-spend per channel (manual) untuk metrik CPL/CAC/ROAS.
    await db.settings.insert_one({"key": "marketing_spend", "value": {
        "items": [
            {"channel": "website", "amount": 1500000.0},
            {"channel": "whatsapp", "amount": 800000.0},
            {"channel": "meta_ads", "amount": 1200000.0},
            {"channel": "google_ads", "amount": 1000000.0},
        ],
        "note": "Estimasi belanja iklan bulan berjalan (contoh seed).",
        "updated_at": now_iso(),
    }})
    rules = default_rules()  # 8 aturan contoh AKTIF (lead-ack, booking, payment, dst)
    await db.automation_rules.insert_many(rules)

    # === Phase 7: CRM Inbox (conversations + messages) + notifikasi awal ===
    cnv1 = {"id": new_id("cnv"), "channel": "web", "contact_name": "Rina (Web)",
            "contact_phone": "0812-7788-9900", "subject": "Tanya sewa Hiace ke Bromo",
            "customer_id": cus[0]["id"], "lead_id": None, "status": "open", "assigned_to": None,
            "labels": ["web"], "unread": 1, "chat_token": secrets.token_urlsafe(18),
            "last_message_at": now_iso(), "last_message_preview": "Halo, sewa Hiace ke Bromo tgl 20?",
            "snooze_until": None, "created_at": now_iso()}
    cnv2 = {"id": new_id("cnv"), "channel": "whatsapp", "contact_name": "PT Maju Jaya",
            "contact_phone": "6281120003000", "subject": "Penjadwalan rombongan kantor",
            "customer_id": cus[1]["id"] if len(cus) > 1 else None, "lead_id": None, "status": "open",
            "assigned_to": users[1]["id"], "labels": ["wa"], "unread": 0,
            "chat_token": None, "last_message_at": now_iso(),
            "last_message_preview": "Baik pak, kami siapkan unitnya.", "snooze_until": None,
            "created_at": now_iso()}
    await db.conversations.insert_many([cnv1, cnv2])
    await db.messages.insert_many([
        {"id": new_id("msg"), "conversation_id": cnv1["id"], "sender": "customer", "author_id": None,
         "body": "Halo, sewa Hiace ke Bromo tgl 20 berapa ya?", "internal": False,
         "status": "delivered", "created_at": now_iso()},
        {"id": new_id("msg"), "conversation_id": cnv2["id"], "sender": "customer", "author_id": None,
         "body": "Pak, untuk rombongan 14 orang minggu depan ready?", "internal": False,
         "status": "read", "created_at": now_iso()},
        {"id": new_id("msg"), "conversation_id": cnv2["id"], "sender": "agent", "author_id": users[1]["id"],
         "body": "Baik pak, kami siapkan unitnya.", "internal": False,
         "status": "delivered", "created_at": now_iso()},
        {"id": new_id("msg"), "conversation_id": cnv2["id"], "sender": "agent", "author_id": users[1]["id"],
         "body": "Catatan: minta DP 30% dulu sebelum lock unit.", "internal": True,
         "status": "sent", "created_at": now_iso()},
    ])
    # Notifikasi awal (scheduler akan menambah lagi saat runtime)
    await db.notification_tasks.insert_many([
        {"id": new_id("ntf"), "dedupe_key": f"doc:{veh[2]['id']}:kir_expiry:seed", "type": "document_reminder",
         "title": "KIR V-03 segera jatuh tempo", "body": "KIR Isuzu Elf perlu diperpanjang.",
         "ref_type": "vehicle", "ref_id": veh[2]["id"], "booking_id": None, "lead_id": None,
         "due_at": iso(_now + timedelta(days=7)), "scheduled_at": now_iso(), "status": "pending",
         "target_role": "manager", "target_user_id": None, "channel": "in_app",
         "read_at": None, "created_at": now_iso()},
        {"id": new_id("ntf"), "dedupe_key": f"lead:{leads[0]['id']}:seed", "type": "lead_followup",
         "title": f"Follow-up lead: {leads[0]['customer_name']}", "body": "Lead website menunggu penawaran.",
         "ref_type": "lead", "ref_id": leads[0]["id"], "booking_id": None, "lead_id": leads[0]["id"],
         "due_at": now_iso(), "scheduled_at": now_iso(), "status": "pending",
         "target_role": "manager", "target_user_id": None, "channel": "in_app",
         "read_at": None, "created_at": now_iso()},
    ])

    await db.audit_logs.insert_many([
        {"id": new_id("aud"), "actor_id": users[0]["id"], "actor_name": users[0]["name"],
         "actor_role": users[0]["role"], "action": "update", "entity_type": "settings",
         "entity_id": "pricing_defaults", "before": {"pricing_defaults": {"dp_percent": 30}},
         "after": {"pricing_defaults": {"dp_percent": 30}},
         "summary": "Ubah pengaturan: pricing_defaults", "timestamp": now_iso()},
        {"id": new_id("aud"), "actor_id": users[1]["id"], "actor_name": users[1]["name"],
         "actor_role": users[1]["role"], "action": "create", "entity_type": "payment",
         "entity_id": "(seed)", "before": None, "after": {"amount": 1000000},
         "summary": "Catat pembayaran Rp 1.000.000 untuk booking BK-0001", "timestamp": now_iso()},
    ])

    # E1 demo: hasilkan event + run + pesan WA mock autentik dari data seed
    try:
        from services.events import emit
        from services.whatsapp import handle_inbound
        await emit(db, "lead.created", {
            "lead_id": leads[0]["id"], "customer_name": leads[0]["customer_name"],
            "phone": leads[0].get("phone"), "destination": leads[0].get("destination"),
            "source": leads[0].get("source"), "assigned_to": leads[0].get("assigned_to"),
        }, source="seed", ref_type="lead", ref_id=leads[0]["id"],
            dedupe_key=f"lead.created:{leads[0]['id']}")
        await handle_inbound(db, "081299885577",
                             "Halo, saya mau tanya paket wisata Bromo untuk 10 orang.",
                             name="Calon Pelanggan")
    except Exception as _e:  # noqa: BLE001
        print(f"{Y}[SEED] demo otomasi dilewati: {_e}{X}")

    # E2 demo: CRM Growth Engine — segmen, sequence, dan kampanye terkirim (WA mock)
    seg_count = seq_count = cmp_count = 0
    try:
        from services import campaigns as cmp_svc
        from services import growth as growth_svc
        _e2_now = now_iso()
        segments = [
            {"id": new_id("seg"), "name": "Semua Pelanggan", "audience": "customer",
             "criteria": {}, "description": "Seluruh pelanggan terdaftar (ber-WhatsApp).",
             "system": True, "created_at": _e2_now, "updated_at": _e2_now},
            {"id": new_id("seg"), "name": "Lead Hot", "audience": "lead",
             "criteria": {"score_band": "hot"}, "description": "Lead dengan skor tertinggi (prioritas tindak lanjut).",
             "system": True, "created_at": _e2_now, "updated_at": _e2_now},
            {"id": new_id("seg"), "name": "Pelanggan Bernilai Tinggi", "audience": "customer",
             "criteria": {"min_value": 1000000}, "description": "LTV >= Rp 1.000.000.",
             "system": False, "created_at": _e2_now, "updated_at": _e2_now},
        ]
        await db.segments.insert_many(segments)
        seg_count = len(segments)

        sequences = [
            {"id": new_id("seq"), "name": "Nurturing Lead Baru", "description": "Drip 3 langkah untuk lead baru dari website.",
             "audience": "lead", "enabled": True,
             "steps": [
                 {"delay_hours": 0, "action": "send_wa", "text": "Halo {name}, terima kasih sudah menghubungi kami. Ada yang bisa kami bantu untuk rencana perjalanan Anda?"},
                 {"delay_hours": 24, "action": "send_wa", "text": "Hai {name}, kami punya promo armada Hiace Premium minggu ini. Mau kami kirim detailnya?"},
                 {"delay_hours": 72, "action": "create_task", "text": "Telepon lead untuk follow-up penawaran."},
             ],
             "stats": {"enrolled": 0, "completed": 0}, "created_at": _e2_now, "updated_at": _e2_now},
        ]
        await db.sequences.insert_many(sequences)
        seq_count = len(sequences)

        # Hitung skor lead + RFM agar Scoreboard/RFM & segmen 'Lead Hot' bermakna saat dibuka
        try:
            await growth_svc.recompute_all(db)
            await growth_svc.scan_rfm(db)
        except Exception as _ge:  # noqa: BLE001
            print(f"{Y}[SEED] recompute growth dilewati: {_ge}{X}")

        # Satu kampanye contoh yang SUDAH terkirim (stats + recipients terisi) ke 'Semua Pelanggan'
        camp = {"id": new_id("cmp"), "name": "Promo Akhir Pekan", "channel": "whatsapp", "audience": "customer",
                "segment_id": segments[0]["id"],
                "segment_snapshot": {"audience": "customer", "criteria": {}},
                "template_key": None,
                "message": "Halo {name}! Promo akhir pekan: diskon 10% sewa Hiace Premium untuk keberangkatan minggu ini. Balas pesan ini untuk info lengkap.",
                "scheduled_at": None, "status": "draft", "stats": {},
                "created_by": users[1]["id"], "created_at": _e2_now, "sent_at": None}
        await db.campaigns.insert_one(camp)
        cmp_count = 1
        try:
            await cmp_svc.send_campaign(db, camp)
        except Exception as _ce:  # noqa: BLE001
            print(f"{Y}[SEED] kirim kampanye demo dilewati: {_ce}{X}")
    except Exception as _e2:  # noqa: BLE001
        print(f"{Y}[SEED] demo E2 (growth) dilewati: {_e2}{X}")

    # E3 demo: Dispatch & Komunikasi Operasi — keberangkatan HARI INI & BESOK (Ops Cockpit)
    dispatch_count = 0
    try:
        _t0 = datetime.now(timezone.utc)
        _day = datetime(_t0.year, _t0.month, _t0.day, tzinfo=timezone.utc)  # anchor kalender (deterministik)
        _DEST_COORDS = {"Bromo": (-7.9425, 112.9530), "Dieng": (-7.2056, 109.9078),
                        "Bali": (-8.7230, 115.1680), "Yogyakarta": (-7.7956, 110.3695)}

        def _disp_bk(code, cust, veh_obj, drv_obj, origin, destination, start_dt, end_dt,
                     paid=0, pay_status="unpaid"):
            _base = 3500000
            _addons = [{"label": "Tol & Parkir", "amount": 300000}]
            _total = _base + sum(a["amount"] for a in _addons)
            return {
                "id": new_id("bk"), "code": code, "customer_id": cust["id"],
                "vehicle_id": veh_obj["id"],
                "driver_id": (drv_obj["id"] if drv_obj else None),
                "origin": origin, "destination": destination,
                "start_datetime": iso(start_dt), "end_datetime": iso(end_dt),
                "base_price": _base, "add_ons": _addons, "total_amount": _total,
                "paid_amount": paid, "payment_status": pay_status, "status": "confirmed",
                "customer_name": cust["name"], "vehicle_name": veh_obj["name"],
                "driver_name": (drv_obj["name"] if drv_obj else None),
                "departure_confirmed_at": None, "notes": "", "created_at": now_iso(),
            }

        # Jendela waktu dipilih agar TIDAK bentrok (INV-4) & hindari window maintenance V-03 (INV-21).
        # D1: HARI INI, sudah di-assign + dikonfirmasi → trip standby + koordinat tujuan (veh[0]).
        d1 = _disp_bk("BK-0003", cus[0], veh[0], drv[1], "Bandung", "Bromo",
                      _day + timedelta(hours=9), _day + timedelta(hours=17), paid=1000000, pay_status="dp")
        d1["departure_confirmed_at"] = now_iso()
        # D2: HARI INI, BELUM di-assign (perlu assign driver) — veh[1], driver kosong, belum bayar.
        d2 = _disp_bk("BK-0004", cus[1], veh[1], None, "Jakarta", "Dieng",
                      _day + timedelta(hours=14), _day + timedelta(hours=22), paid=0, pay_status="belum_bayar")
        # D3: BESOK, sudah di-assign tapi BELUM dikonfirmasi (perlu konfirmasi) — veh[0] besok.
        d3 = _disp_bk("BK-0005", cus[2], veh[0], drv[0], "Bandung", "Yogyakarta",
                      _day + timedelta(days=1, hours=9), _day + timedelta(days=1, hours=17),
                      paid=1500000, pay_status="dp")
        await db.bookings.insert_many([d1, d2, d3])
        dispatch_count = 3
        await db.counters.update_one({"id": "booking"}, {"$set": {"seq": 5}}, upsert=True)
        # Pembayaran DP utk D1 & D3 (INV-2/INV-3 konsisten).
        await db.payments.insert_many([
            {"id": new_id("pay"), "booking_id": d1["id"], "amount": 1000000, "type": "dp",
             "method": "transfer", "recorded_by": users[1]["id"], "paid_at": now_iso()},
            {"id": new_id("pay"), "booking_id": d3["id"], "amount": 1500000, "type": "dp",
             "method": "transfer", "recorded_by": users[1]["id"], "paid_at": now_iso()},
        ])

        # Trip terjadwal (standby) utk booking yang sudah di-assign (D1, D3) + koordinat tujuan.
        for _bk in (d1, d3):
            lat, lng = _DEST_COORDS.get(_bk["destination"], (None, None))
            await db.trips.insert_one({
                "id": new_id("trp"), "booking_id": _bk["id"], "vehicle_id": _bk["vehicle_id"],
                "driver_id": _bk["driver_id"], "status": "standby", "start_at": None, "end_at": None,
                "revenue": float(_bk["total_amount"]), "profit": None, "distance_km": 0.0,
                "dest_name": _bk["destination"], "dest_lat": lat, "dest_lng": lng,
                "dest_display": f"{_bk['destination']}, Indonesia", "assigned_at": now_iso(),
                "created_at": now_iso(),
            })

        # POD ringan pada trip utama (bk on_trip) sbg contoh bukti layanan.
        await db.trips.update_one({"booking_id": bk["id"]}, {"$set": {"pod": {
            "photo_url": None, "recipient_name": cus[0]["name"],
            "note": "Diterima di lobi hotel, kondisi baik.", "at": now_iso(), "by": users[2]["id"]}}})

        # Pancarkan WA (mock) utk D1: trip.assigned + booking.departure_confirmed (aturan E3 aktif).
        try:
            from services.events import emit as _emit
            _pay1 = {"booking_id": d1["id"], "code": d1["code"], "customer_name": cus[0]["name"],
                     "phone": cus[0].get("phone"), "destination": d1["destination"],
                     "origin": d1["origin"], "pickup": d1["origin"],
                     "start_datetime": d1["start_datetime"], "vehicle_name": veh[0]["name"],
                     "driver_name": drv[1]["name"], "driver_phone": drv[1].get("phone"),
                     "company": "RahazaTrans"}
            await _emit(db, "trip.assigned", _pay1, source="seed", ref_type="booking",
                        ref_id=d1["id"], dedupe_key=f"trip.assigned:{d1['id']}")
            await _emit(db, "booking.departure_confirmed", _pay1, source="seed", ref_type="booking",
                        ref_id=d1["id"], dedupe_key=f"booking.departure_confirmed:{d1['id']}")
        except Exception as _we:  # noqa: BLE001
            print(f"{Y}[SEED] WA dispatch demo dilewati: {_we}{X}")
    except Exception as _e3:  # noqa: BLE001
        print(f"{Y}[SEED] demo E3 (dispatch) dilewati: {_e3}{X}")



    # E27 demo: lapisan "PERLU PERHATIAN" di Kalender Keberangkatan.
    # Semua skenario di bawah SAH menurut invarian (INV-1/3/4/10/21) — sengaja HANYA kelas
    # risiko yang memang bisa terjadi di operasional nyata:
    #   - permintaan publik `pending` (tak mereservasi armada) yang belum diproses ops
    #   - sopir "dipesan lisan" pada permintaan pending padahal jadwalnya beririsan (bentrok sopir)
    #   - reservasi `hold` yang DP-nya belum masuk dan tenggatnya mendekat
    # Kelas bentrok ARMADA & tabrakan PERAWATAN sengaja TIDAK di-seed: keduanya melanggar
    # invariant dan sudah ditolak keras backend; deteksinya di kalender murni jaring pengaman
    # untuk data lama/impor.
    attention_count = 0
    try:
        _at_now = datetime.now(timezone.utc)
        _at_day = datetime(_at_now.year, _at_now.month, _at_now.day, tzinfo=timezone.utc)

        _pub_cust = {"id": new_id("cus"), "name": "Keluarga Hendra", "phone": "081355566677",
                     "email": "hendra.fam@mail.com", "type": "individual", "city": "Bekasi",
                     "address": "Jl. Ahmad Yani 12", "total_trips": 0, "lifetime_value": 0,
                     "notes": "Dibuat dari permintaan booking publik (self-service)",
                     "created_at": now_iso()}
        _pub_cust["phone_normalized"] = _norm_phone(_pub_cust["phone"])
        await db.customers.insert_one(_pub_cust)

        def _req_bk(code, cust, start_dt, end_dt, dest, pax, vtype, msg, driver_obj=None):
            """Permintaan self-service situs publik → 'pending', armada ditetapkan saat approve."""
            return {
                "id": new_id("bk"), "code": code, "customer_id": cust["id"],
                "vehicle_id": None, "driver_id": (driver_obj["id"] if driver_obj else None),
                "origin": "Bandung", "destination": dest,
                "start_datetime": iso(start_dt), "end_datetime": iso(end_dt),
                "base_price": 0, "add_ons": [], "total_amount": 0, "paid_amount": 0,
                "payment_status": "belum_bayar", "status": "pending",
                "customer_name": cust["name"], "vehicle_name": None,
                "driver_name": (driver_obj["name"] if driver_obj else None),
                "requested_vehicle_type": vtype, "pax": pax, "source": "public",
                "notes": msg, "created_at": now_iso(),
            }

        # A1: permintaan H-1 (mendesak) — belum diproses ops, armada belum ditetapkan.
        a1 = _req_bk("BK-0006", _pub_cust, _at_day + timedelta(days=1, hours=6),
                     _at_day + timedelta(days=1, hours=20), "Pangandaran", 40, "bus",
                     "Ziarah keluarga, mohon konfirmasi ketersediaan bus besar.")
        # A2: permintaan besok + sopir sudah "dipesan lisan" padahal drv[0] terjadwal di BK-0005
        #     pada jam yang beririsan → kelas bentrok SOPIR yang NYATA (pending tak divalidasi).
        a2 = _req_bk("BK-0007", cus[2], _at_day + timedelta(days=1, hours=10),
                     _at_day + timedelta(days=1, hours=18), "Garut", 12, "hiace_premio",
                     "Rapat direksi, minta sopir yang sama seperti sebelumnya.", driver_obj=drv[0])
        await db.bookings.insert_many([a1, a2])

        # A3: reservasi `hold` — DP belum masuk & tenggat hold tinggal ~4 jam (harus dikejar ops).
        _h_base, _h_addons = 4200000, [{"label": "Tol & Parkir", "amount": 300000}]
        _h_total = _h_base + sum(x["amount"] for x in _h_addons)
        hold_bk = {
            "id": new_id("bk"), "code": "BK-0008", "customer_id": cus[1]["id"],
            "vehicle_id": veh[1]["id"], "driver_id": None, "origin": "Bandung",
            "destination": "Karimunjawa",
            "start_datetime": iso(_at_day + timedelta(days=4, hours=7)),
            "end_datetime": iso(_at_day + timedelta(days=5, hours=21)),
            "base_price": _h_base, "add_ons": _h_addons, "total_amount": _h_total,
            "paid_amount": 0, "payment_status": "belum_bayar", "status": "hold",
            "customer_name": cus[1]["name"], "vehicle_name": veh[1]["name"], "driver_name": None,
            "hold_expires_at": iso(_at_now + timedelta(hours=4)), "hold_hours": 24,
            "dp_percent": 30.0, "dp_amount": float(round(_h_total * 0.3)),
            "notes": "Menunggu transfer DP dari pelanggan.", "created_at": now_iso(),
        }
        await db.bookings.insert_one(hold_bk)

        # A4+A5: HOLD YANG SUDAH HANGUS — bahan nyata untuk laporan "Hold Hangus"
        # (`/app/reports` → panel Hold Hangus, `services/hold_report.py`).
        #
        # Kenapa di-seed: kejadian ini hanya lahir setelah penjadwal membatalkan reservasi yang
        # DP-nya tak masuk — pada data demo yang baru dibuat, peristiwa itu belum pernah terjadi,
        # sehingga laporan (dan pelajaran terpentingnya) tampil KOSONG dan pemilik tidak pernah
        # tahu fitur itu ada. Salah satunya SENGAJA punya bukti transfer berstatus `pending`:
        # itulah kasus paling mahal — tamu sudah bayar, ops terlambat memverifikasi, sistem
        # membatalkan. Angka itu yang memicu peringatan merah di laporan.
        _exp_rows, _exp_proofs = [], []
        for _i, (_code, _cust, _vehicle, _total, _hours_ago, _with_proof, _phone) in enumerate([
            ("BK-0009", _pub_cust, veh[0], 2250000, 26, True, "081399000011"),
            ("BK-0010", cus[2], veh[0], 1950000, 74, False, "081399000022"),
        ]):
            _exp_at = _at_now - timedelta(hours=_hours_ago)
            _bk = {
                "id": new_id("bk"), "code": _code, "customer_id": _cust["id"],
                "vehicle_id": _vehicle["id"], "driver_id": None, "origin": "Bandung",
                "destination": "Dieng" if _i else "Bromo",
                "start_datetime": iso(_at_day + timedelta(days=20 + _i * 5, hours=7)),
                "end_datetime": iso(_at_day + timedelta(days=21 + _i * 5, hours=20)),
                "base_price": _total, "add_ons": [], "total_amount": _total, "paid_amount": 0,
                "payment_status": "belum_bayar", "status": "cancelled",
                "customer_name": _cust["name"], "vehicle_name": _vehicle["name"],
                "driver_name": None, "service": "daily_rental",
                "service_label": "Sewa Harian + Driver", "pax": 12 + _i,
                "source": "web_booking", "contact_phone": _phone,
                "hold_expires_at": iso(_exp_at), "hold_hours": 2,
                "hold_expired_at": iso(_exp_at),
                "dp_percent": 30.0, "dp_amount": float(round(_total * 0.3)),
                "notes": "Dibatalkan otomatis: DP tidak masuk sebelum batas waktu.",
                "created_at": iso(_exp_at - timedelta(hours=2)),
            }
            _exp_rows.append(_bk)
            if _with_proof:
                _exp_proofs.append({
                    "id": new_id("ppf"), "booking_id": _bk["id"], "booking_code": _code,
                    "customer_name": _cust["name"], "media_id": "", "media_url": "",
                    "amount_claimed": float(round(_total * 0.3)),
                    "sender_name": _cust["name"], "bank": "BCA",
                    "note": "Transfer sudah dilakukan, mohon dicek.", "status": "pending",
                    "verified_by": "", "verified_at": None, "reject_reason": "",
                    "created_at": iso(_exp_at - timedelta(minutes=30)),
                })
        await db.bookings.insert_many(_exp_rows)
        if _exp_proofs:
            await db.payment_proofs.insert_many(_exp_proofs)
        await db.counters.update_one({"id": "booking"}, {"$set": {"seq": 10}}, upsert=True)
        attention_count = 3
    except Exception as _e27:  # noqa: BLE001
        print(f"{Y}[SEED] demo E27 (perlu perhatian) dilewati: {_e27}{X}")

    # ---------------------------------------------------------------- Halaman iklan demo (F8/F8b)
    # KENAPA di-seed: halaman iklan demo sebelumnya dibuat MANUAL lewat UI, sehingga pada pod baru
    # (clone bersih + seed) halaman itu hilang — `/lp/...` 404, dan POC F8b tidak bisa menguji
    # jalur "lead dari halaman iklan → outbox konversi" karena tak ada halaman published sama sekali.
    # Data demo wajib bisa direproduksi tanpa mengklik UI.
    landing_count = 0
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
        from services import landing_blocks as _lb
        from services import landing_templates as _lt

        _blocks, _theme, _segment = _lt.build("armada-konversi")
        _clean, _ = _lb.validate_blocks(_blocks)
        _lp = {
            "id": new_id("lp"), "title": "Sewa Hiace Jakarta — Driver Berpengalaman",
            "slug": "sewa-hiace-jakarta", "segment": _segment, "template": "armada-konversi",
            "status": "published", "blocks": _clean, "theme": _lb.sanitize_theme(_theme),
            "seo": {"title": "Sewa Hiace Jakarta + Driver | RahazaTrans",
                    "description": "Sewa Hiace Premio & Commuter di Jakarta dengan driver "
                                   "berpengalaman. Harga transparan, unit terawat, siap 24 jam.",
                    "og_image": "", "noindex": True},
            "tracking": {"utm_default": "utm_source=google&utm_medium=cpc", "conversion_label": ""},
            "ab": _lb.default_ab(),
            "published_at": now_iso(), "created_by": "owner@demo.local",
            "created_at": now_iso(), "updated_at": now_iso(),
        }
        _errs = _lb.publish_errors(_lp)
        if _errs:
            # Jangan pura-pura terbit: kalau gate INV-LP-01 menolak, simpan sebagai draf dan
            # katakan alasannya, bukan menaruh status 'published' yang tidak sah di database.
            _lp["status"], _lp["published_at"] = "draft", None
            print(f"{Y}[SEED] halaman iklan demo disimpan sebagai DRAF: {_errs}{X}")
        await db.landing_pages.insert_one(_lp)
        landing_count = 1
    except Exception as _elp:  # noqa: BLE001
        print(f"{Y}[SEED] halaman iklan demo dilewati: {_elp}{X}")

    # INV-CLEAN-01 — `media_assets`/`media_folders` SENGAJA tidak di-reset di atas (berkas fisik
    # milik pengguna tak boleh jadi yatim). Konsekuensinya aset uji `guard-media-*` dari penjaga
    # bisa menumpuk di Media Library. Reseed = titik yang tepat untuk memastikan data demo yang
    # dilihat pengguna 100% bersih dari artefak uji (BUG-0127).
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent / "guardrails"))
        from _common import purge_guard_artifacts  # noqa: PLC0415
        _purged = purge_guard_artifacts()
        if _purged:
            print(f"{Y}[SEED] {_purged} artefak data uji (guardrail/smoke) dibersihkan.{X}")
    except Exception as _epg:  # noqa: BLE001
        print(f"{Y}[SEED] bersih-bersih artefak uji dilewati: {_epg}{X}")

    print(f"{G}[SEED OK]{X} users={len(users)} vehicles={len(veh)} drivers={len(drv)} "
          f"customers={len(cus)} bookings=2 payments=2 trips=2 locations={len(locs)} "
          f"leads={len(leads)} lead_activities=4 broadcasts=1 maintenance={len(maintenance)} workshops={len(workshops)} service_types={len(service_types)} driver_payouts=2 trip_shares=1 "
          f"conversations=2 messages=4 notification_tasks=2 "
          f"destinations=4 articles=6 testimonials=3 quotations=1 packages=2 promos=3 "
          f"transfer_routes=3 "
          f"segments={seg_count} sequences={seq_count} campaigns={cmp_count} dispatch_bookings={dispatch_count} "
          f"attention_demo={attention_count} landing_pages={landing_count}")
    print(f"{Y}Akun demo (password: demo12345):{X} owner@demo.local | ops@demo.local | marketing@demo.local | driver@demo.local")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))

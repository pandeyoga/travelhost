"""services/onboarding.py — Checklist onboarding pengguna (Phase 8 / A5).

Membantu pengguna baru memahami alur inti. Status tiap tugas bisa:
  - DERIVED otomatis dari data nyata (mis. 'tambah_armada' selesai bila ada armada), atau
  - DITANDAI manual (disimpan di koleksi `user_onboarding.completed[]`).
Checklist bisa di-dismiss (disembunyikan) per pengguna.
"""

# Definisi tugas per peran. derive=kunci auto-check (None = manual saja).
TASKS = {
    "owner": [
        {"key": "lengkapi_profil", "label": "Lengkapi profil perusahaan",
         "desc": "Isi nama, kontak, dan logo di Pengaturan.", "link": "/app/settings", "derive": "profile"},
        {"key": "tambah_armada", "label": "Tambah armada pertama",
         "desc": "Daftarkan kendaraan beserta dokumen (KIR/pajak).", "link": "/app/vehicles", "derive": "vehicles"},
        {"key": "tambah_driver", "label": "Tambah driver",
         "desc": "Daftarkan pengemudi untuk ditugaskan ke trip.", "link": "/app/drivers", "derive": "drivers"},
        {"key": "buat_booking", "label": "Buat booking pertama",
         "desc": "Catat pesanan — sistem cegah jadwal bentrok otomatis.", "link": "/app/bookings", "derive": "bookings"},
        {"key": "terbitkan_invoice", "label": "Terbitkan invoice",
         "desc": "Buat tagihan PDF/Excel dari booking.", "link": "/app/finance", "derive": "invoices"},
        {"key": "tinjau_inbox", "label": "Tinjau Inbox & balas chat",
         "desc": "Pantau percakapan pelanggan dari satu tempat.", "link": "/app/inbox", "derive": None},
    ],
    "ops_admin": [
        {"key": "tambah_armada", "label": "Tambah armada",
         "desc": "Daftarkan kendaraan beserta dokumen.", "link": "/app/vehicles", "derive": "vehicles"},
        {"key": "tambah_driver", "label": "Tambah driver",
         "desc": "Daftarkan pengemudi untuk ditugaskan.", "link": "/app/drivers", "derive": "drivers"},
        {"key": "buat_booking", "label": "Buat booking",
         "desc": "Catat pesanan & cek anti double-booking.", "link": "/app/bookings", "derive": "bookings"},
        {"key": "tinjau_crm", "label": "Kelola pipeline CRM",
         "desc": "Tindak lanjuti lead dari website.", "link": "/app/crm", "derive": None},
        {"key": "tinjau_inbox", "label": "Tinjau Inbox",
         "desc": "Balas chat pelanggan & assign agen.", "link": "/app/inbox", "derive": None},
    ],
    "driver": [
        {"key": "pantau_armada", "label": "Pantau posisi armada",
         "desc": "Lihat peta live & ETA perjalanan.", "link": "/app/gps", "derive": None},
        {"key": "cek_jadwal", "label": "Cek jadwal booking",
         "desc": "Lihat daftar perjalanan terjadwal.", "link": "/app/bookings", "derive": None},
    ],
}


async def _derive(db) -> dict:
    """Status auto-check dari data nyata."""
    profile = await db.settings.find_one({"key": "company_info"}, {"_id": 0})
    has_profile = bool(((profile or {}).get("value") or {}).get("name"))
    return {
        "vehicles": (await db.vehicles.count_documents({})) > 0,
        "drivers": (await db.drivers.count_documents({})) > 0,
        "bookings": (await db.bookings.count_documents({})) > 0,
        "invoices": (await db.invoices.count_documents({})) > 0,
        "profile": has_profile,
    }


async def build_state(db, user) -> dict:
    """Bangun checklist untuk `user` (gabungan derived + completed manual)."""
    role = user.get("role", "ops_admin")
    defs = TASKS.get(role) or TASKS["ops_admin"]
    saved = await db.user_onboarding.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
    completed = set(saved.get("completed", []))
    derived = await _derive(db)
    items = []
    for t in defs:
        done = (t["key"] in completed) or bool(t.get("derive") and derived.get(t["derive"]))
        items.append({**t, "done": done})
    done_count = sum(1 for i in items if i["done"])
    return {
        "role": role,
        "dismissed": bool(saved.get("dismissed")),
        "total": len(items),
        "done": done_count,
        "complete": done_count == len(items),
        "tasks": items,
    }

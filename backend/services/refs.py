"""services/refs.py — SATU PINTU validasi REFERENSI (FK) & PILIHAN (enum) dari luar.

Kenapa modul ini ada (audit 2026-08-12, permintaan user)
--------------------------------------------------------
Formulir ERP sudah memakai dropdown yang mengambil isinya dari koleksi (tipe armada, bengkel,
mitra, sopir). Tetapi API-nya TIDAK memeriksa apa pun: `POST /api/maintenance` menerima
`workshop_id="wrk_tidak_ada"`, `PATCH /api/vehicles` menerima `type="ngawur"`, dan
`POST /api/conversations` menerima `customer_id` hantu — semuanya HTTP 200 lalu TERSIMPAN.

Akibat nyata dari data seperti itu (bukan teori):
  * `type="ngawur"` → mesin harga tidak menemukan `day_rates["ngawur"]`, unit jadi tak punya
    harga; label di UI menampilkan "Ngawur"; unit ikut tayang di web tanpa tarif.
  * `status="ngawur"` → penyaring "Tersedia/Perawatan" bocor, badge status kosong, dan
    keputusan operasional dibuat atas keadaan yang tidak pernah ada.
  * `ownership="ngawur"` → `booking_search.publishable_filter()` menuntut `owned` (atau kosong),
    jadi unit itu HILANG dari katalog publik tanpa satu pun pesan galat: "bug" yang tak
    terlacak selamanya.
  * `workshop_id`/`customer_id`/`lead_id`/`segment_id` hantu → dokumen YATIM; tabel & laporan
    menampilkan "-" abadi, dan ops mengira datanya hilang.

Aturan modul ini:
  1. Referensi WAJIB divalidasi ke koleksinya (`must_exist`) dengan pesan berbahasa Indonesia.
     Nilai kosong/None untuk field opsional = SAH (artinya "tidak ditautkan").
  2. Pilihan WAJIB berasal dari SSOT yang benar-benar dipakai runtime — tipe armada diambil
     dari `services/pricing.VEHICLE_TYPE_LABELS` (yang dipakai mesin harga & label UI),
     BUKAN daftar tandingan yang ditulis ulang di sini.
  3. Penolakan selalu 400 berALASAN + menyebut pilihan yang sah, sehingga integrasi/agen luar
     bisa memperbaiki dirinya sendiri.

Dijaga guardrail INV-REF-01 (`scripts/guardrails/verify_reference_integrity.py`).
"""
from fastapi import HTTPException

from services.pricing import VEHICLE_TYPE_LABELS

# --- SSOT PILIHAN -----------------------------------------------------------------------
# Nilai-nilai ini HARUS sama dengan opsi dropdown di frontend (VehicleFormDialog,
# DriverFormDialog, CustomerFormDialog) dan dengan yang dibaca penyaring/laporan.
VEHICLE_STATUSES = ("available", "on_trip", "maintenance", "inactive", "sold")
VEHICLE_OWNERSHIPS = ("owned", "partner")
DRIVER_STATUSES = ("online", "resting", "offline", "on_trip")
CUSTOMER_TYPES = ("individual", "corporate")
PAYMENT_TYPES = ("dp", "settlement", "refund", "penalty")
PAYMENT_METHODS = ("transfer", "cash", "qris", "card", "other")
MAINTENANCE_STATUSES = ("scheduled", "in_progress", "done", "cancelled")
EXPENSE_CATEGORIES = ("bbm", "tol", "uang_jalan", "gaji_driver", "other")

# label koleksi → pesan yang bisa dibaca pengguna
COLLECTION_LABELS = {
    "vehicles": "Armada", "drivers": "Sopir", "customers": "Pelanggan",
    "bookings": "Pesanan", "trips": "Trip", "workshops": "Bengkel",
    "partners": "Mitra", "segments": "Segmen", "leads": "Lead",
    "transfer_routes": "Rute antar-jemput", "users": "Pengguna",
    "subcharters": "Sub-charter", "payment_proofs": "Bukti transfer",
}


def _bad(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)


async def must_exist(db, collection: str, doc_id, *, field: str = "", required: bool = False):
    """Pastikan `doc_id` benar-benar ada di `collection`.

    - Nilai kosong → dianggap "tidak ditautkan": SAH bila `required=False`.
    - Nilai ada tetapi dokumennya tidak → 400 berALASAN (bukan dokumen yatim yang diam-diam
      tersimpan lalu tampil sebagai "-" di tabel).
    """
    value = str(doc_id or "").strip()
    label = COLLECTION_LABELS.get(collection, collection)
    if not value:
        if required:
            raise _bad(f"{label} wajib dipilih")
        return None
    if not await db[collection].find_one({"id": value}, {"_id": 1}):
        raise _bad(f"{label} tidak ditemukan (id '{value[:32]}')")
    return value


def must_be_choice(value, allowed, *, field_label: str, default=None, allow_empty: bool = True):
    """Kembalikan nilai yang SAH atau tolak 400 dengan menyebut daftar pilihannya.

    `default` dipakai bila nilai kosong (mis. field opsional yang tidak dikirim).
    """
    raw = str(value if value is not None else "").strip()
    if not raw:
        if allow_empty:
            return default
        raise _bad(f"{field_label} wajib dipilih. Pilihan: {', '.join(allowed)}")
    if raw not in allowed:
        raise _bad(f"{field_label} '{raw[:24]}' tidak dikenal. Pilihan: {', '.join(allowed)}")
    return raw


def vehicle_type_or_400(value, *, default="hiace", field_label="Tipe armada"):
    """Tipe armada dari SSOT mesin harga (`VEHICLE_TYPE_LABELS`) — bukan daftar terpisah."""
    return must_be_choice(value, tuple(VEHICLE_TYPE_LABELS.keys()),
                          field_label=field_label, default=default)


def vehicle_rates_or_400(raw, *, field_label="Tarif per tipe armada") -> dict:
    """Peta {tipe_armada: nominal} — kunci WAJIB tipe armada yang dikenal.

    Tanpa ini, rute antar-jemput bisa menyimpan tarif untuk tipe unit yang tidak pernah ada
    (mis. `{"ngawur": 500000}`): rute tampak "sudah ada tarifnya" di Pengaturan, tetapi mesin
    harga tidak pernah bisa menjualnya — dan tidak ada satu pun pesan yang menjelaskan itu.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _bad("Tarif harus berupa objek {tipe_armada: nominal}")
    allowed = tuple(VEHICLE_TYPE_LABELS.keys())
    out = {}
    for key, value in raw.items():
        vt = str(key or "").strip()
        if not vt:
            continue
        if vt not in allowed:
            raise _bad(f"{field_label}: tipe '{vt[:24]}' tidak dikenal. "
                       f"Pilihan: {', '.join(allowed)}")
        if isinstance(value, bool):
            raise _bad(f"Tarif '{vt}' harus berupa angka")
        if value in (None, ""):
            continue
        try:
            amount = int(round(float(value)))
        except (TypeError, ValueError):
            raise _bad(f"Tarif '{vt}' harus berupa angka") from None
        if amount < 0:
            raise _bad(f"Tarif '{vt}' tidak boleh negatif")
        if amount:
            out[vt] = amount
    return out


async def destination_or_400(db, value, *, field_label: str = "Destinasi"):
    """INV-REF-02: destinasi booking ERP WAJIB dari master `destinations` (bukan teks bebas).

    Nilai kosong = SAH (belum ditautkan). Pencocokan case-insensitive terhadap `name`/`slug`,
    dan nilai yang tersimpan SELALU nama kanonik master — bukan ejaan bebas pengguna.
    """
    raw = str(value or "").strip()
    if not raw:
        return ""
    low = raw.lower()
    rows = await db.destinations.find(
        {"deleted": {"$ne": True}, "ops_active": {"$ne": False}},
        {"_id": 0, "name": 1, "slug": 1}).to_list(500)
    for d in rows:
        if str(d.get("name") or "").strip().lower() == low or str(d.get("slug") or "").strip().lower() == low:
            return str(d.get("name") or raw).strip()
    names = sorted({str(d.get("name") or "").strip() for d in rows if d.get("name")})
    contoh = ", ".join(names[:8]) or "-"
    raise _bad(f"{field_label} '{raw[:40]}' tidak ada di master destinasi. "
               f"Pilih dari master (mis. {contoh}) atau tambahkan dulu di master destinasi.")


async def origin_or_400(db, value, *, field_label: str = "Titik jemput"):
    """INV-REF-02 batch 2: titik jemput booking ERP WAJIB dari master `pickup_points`.

    Kosong = sah. Cocok case-insensitive vs `name`; tersimpan NAMA KANONIK master.
    Ops bisa menambah titik baru lewat POST /api/pickup-points (quick-add) — tetap satu pintu.
    """
    raw = str(value or "").strip()
    if not raw:
        return ""
    low = raw.lower()
    rows = await db.pickup_points.find(
        {"deleted": {"$ne": True}, "active": {"$ne": False}}, {"_id": 0, "name": 1}).to_list(500)
    for p in rows:
        if str(p.get("name") or "").strip().lower() == low:
            return str(p.get("name")).strip()
    names = sorted({str(p.get("name") or "").strip() for p in rows if p.get("name")})
    contoh = ", ".join(names[:8]) or "-"
    raise _bad(f"{field_label} '{raw[:40]}' tidak ada di master titik jemput. "
               f"Pilih dari master (mis. {contoh}) atau tambahkan lewat tombol + di form.")


async def destination_normalize(db, value):
    """Normalisasi LUNAK utk jalur PUBLIK (lead web/landing): cocok master → nama kanonik;
    tidak cocok → simpan apa adanya. Lead inbound eksternal TIDAK BOLEH ditolak — batas
    validasi keras (destination_or_400) hanya utk jalur tulis internal ERP."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    low = raw.lower()
    rows = await db.destinations.find(
        {"deleted": {"$ne": True}}, {"_id": 0, "name": 1, "slug": 1}).to_list(500)
    for d in rows:
        if str(d.get("name") or "").strip().lower() == low or str(d.get("slug") or "").strip().lower() == low:
            return str(d.get("name") or raw).strip()
    return raw


async def origin_normalize(db, value):
    """INV-REF-02 batch 4: normalisasi LUNAK titik jemput utk jalur PUBLIK/inbound
    (pemesanan online, lead landing): cocok master `pickup_points` → nama kanonik;
    tidak cocok → simpan apa adanya (pengunjung TIDAK BOLEH ditolak karena ejaan)."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    low = raw.lower()
    rows = await db.pickup_points.find(
        {"deleted": {"$ne": True}}, {"_id": 0, "name": 1}).to_list(500)
    for p in rows:
        if str(p.get("name") or "").strip().lower() == low:
            return str(p.get("name")).strip()
    return raw


async def city_or_400(db, value, *, field_label: str = "Kota"):
    """INV-REF-02 batch 5: kota pelanggan/mitra WAJIB dari master `cities` (jalur ERP).

    Kosong = sah. Cocok case-insensitive vs `name`; tersimpan NAMA KANONIK master.
    Ops bisa menambah kota baru lewat POST /api/cities (quick-add) — tetap satu pintu.
    """
    raw = str(value or "").strip()
    if not raw:
        return ""
    low = raw.lower()
    rows = await db.cities.find(
        {"deleted": {"$ne": True}, "active": {"$ne": False}}, {"_id": 0, "name": 1}).to_list(500)
    for c in rows:
        if str(c.get("name") or "").strip().lower() == low:
            return str(c.get("name")).strip()
    names = sorted({str(c.get("name") or "").strip() for c in rows if c.get("name")})
    contoh = ", ".join(names[:8]) or "-"
    raise _bad(f"{field_label} '{raw[:40]}' tidak ada di master kota. "
               f"Pilih dari master (mis. {contoh}) atau tambahkan lewat tombol + di form.")


def vehicle_type_normalize(value):
    """INV-REF-02 batch 5: normalisasi LUNAK tipe armada utk jalur PUBLIK/inbound
    (lead landing, permintaan booking publik): cocok kunci/label SSOT
    `pricing.VEHICLE_TYPE_LABELS` → kunci kanonik; tidak cocok → apa adanya."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    low = raw.lower()
    for key, label in VEHICLE_TYPE_LABELS.items():
        if low == key.lower() or low == str(label).strip().lower():
            return key
    return raw

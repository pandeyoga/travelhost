"""schemas.py — Pydantic request models (kontrak input API).

RC-11 hardening (Putaran 11): SEMUA field numerik uang/kuantitas dibatasi `ge=0`
(tak menerima nilai negatif) di layer schema. Ini menutup kelas "negative-value"
yang dipetakan di scripts/audit_r11/root_cause_matrix.txt. `ge=0` (bukan `gt=0`)
dipilih agar 0 tetap valid (banyak default = 0) sekaligus menolak nilai minus.
"""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    email: str = Field(max_length=160)
    password: str = Field(max_length=200)


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=6, max_length=200)
    role: str = Field(default="ops_admin", max_length=32)
    phone: Optional[str] = Field(default="", max_length=24)


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=24)
    role: Optional[str] = Field(default=None, max_length=32)
    status: Optional[str] = Field(default=None, max_length=32)
    password: Optional[str] = Field(default=None, max_length=200)


# === Phase 1: GPS / Trips / Bookings ===
class LocationCreate(BaseModel):
    """Ingest titik GPS dari driver. timestamp diisi server (monotonik, INV-6)."""
    trip_id: Optional[str] = None
    driver_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    lat: float
    lng: float
    speed: Optional[float] = Field(default=0, ge=0)
    heading: Optional[float] = 0


class GpsDeviceAssign(BaseModel):
    """E15: pasang IMEI device GPS fisik (Traccar) ke sebuah armada."""
    imei: str = Field(min_length=3)
    enabled: Optional[bool] = True
    note: Optional[str] = Field(default="", max_length=1000)


class AddOn(BaseModel):
    label: str = Field(default="", max_length=120)
    amount: float = Field(default=0, ge=0)  # tak boleh negatif → cegah total_amount negatif (INV-1 tetap, tapi nilai jujur)


class BookingCreate(BaseModel):
    customer_id: str
    vehicle_id: str
    driver_id: Optional[str] = None
    origin: Optional[str] = Field(default="", max_length=160)
    destination: Optional[str] = Field(default="", max_length=160)
    start_datetime: str
    end_datetime: str
    base_price: float = Field(default=0, ge=0)
    add_ons: Optional[List[AddOn]] = None
    notes: Optional[str] = Field(default="", max_length=2000)
    require_dp: Optional[bool] = False   # E18: buat sebagai 'hold' (menunggu DP) + auto-expire
    hold_hours: Optional[int] = Field(default=None, ge=0)     # E18: batas waktu DP (jam); default dari settings


class BookingUpdate(BaseModel):
    """Edit booking ringan (Phase 2). Tanggal/harga tidak diubah di sini agar
    INV-1/INV-4 tetap stabil; gunakan pembatalan + booking baru bila perlu jadwal ulang."""
    driver_id: Optional[str] = None
    origin: Optional[str] = Field(default=None, max_length=160)
    destination: Optional[str] = Field(default=None, max_length=160)
    notes: Optional[str] = Field(default=None, max_length=2000)


class BookingReschedule(BaseModel):
    """E17: jadwal ulang booking (ubah tanggal &/atau armada) dgn re-cek ketersediaan
    (INV-4 armada + INV-21 perawatan + RC-07 driver). Emit `booking.rescheduled` → WA."""
    start_datetime: str
    end_datetime: str
    vehicle_id: Optional[str] = None  # opsional: pindah armada saat jadwal ulang
    reason: Optional[str] = Field(default="", max_length=400)


class BookingApprove(BaseModel):
    """E19: setujui booking `pending` (permintaan publik) → assign armada + confirmed."""
    vehicle_id: str = Field(min_length=1)
    driver_id: Optional[str] = None
    base_price: Optional[float] = Field(default=None, ge=0)  # override harga bila perlu; default: pakai yg ada


class GroupUnit(BaseModel):
    """E20: satu unit/leg dalam booking rombongan (1 unit armada atau 1 segmen rute)."""
    vehicle_id: str = Field(min_length=1)
    driver_id: Optional[str] = None
    origin: Optional[str] = Field(default="", max_length=160)
    destination: Optional[str] = Field(default="", max_length=160)
    start_datetime: str
    end_datetime: str
    base_price: float = Field(default=0, ge=0)
    add_ons: Optional[List[AddOn]] = None


class GroupBookingCreate(BaseModel):
    """E20: booking rombongan — banyak unit serentak dan/atau beberapa leg/rute.
    Tiap unit jadi 1 booking anak (group_id sama) → reuse dispatch/pembayaran/INV-4."""
    customer_id: str = Field(min_length=1)
    note: Optional[str] = Field(default="", max_length=1000)
    require_dp: Optional[bool] = False
    units: List[GroupUnit] = Field(min_length=1)


class CancelBooking(BaseModel):
    """E21: pembatalan dgn kebijakan denda MANUAL + refund (nominal diisi ops).
    Akuntansi kas refund/denda: lihat memory/HANDOFF_E21_REFUND.md (di-handoff)."""
    reason: Optional[str] = Field(default="", max_length=400)
    cancellation_fee: Optional[float] = Field(default=0, ge=0)   # denda ditahan sbg pendapatan (manual)
    refund_amount: Optional[float] = Field(default=0, ge=0)       # dana dikembalikan ke pelanggan (manual)


class TripStatusUpdate(BaseModel):
    status: str = Field(max_length=32)


class CheckinRequest(BaseModel):
    trip_id: Optional[str] = None
    booking_id: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    odometer_start: Optional[float] = Field(default=None, ge=0)  # E9: odometer awal (saat Mulai)
    odometer_end: Optional[float] = Field(default=None, ge=0)    # E9: odometer akhir (saat Selesai)


class AssignTripRequest(BaseModel):
    driver_id: str
    vehicle_id: str
    # Fee driver /hari utk keberangkatan ini (boleh beda tiap keberangkatan; None = tanpa fee).
    driver_fee_rate: Optional[float] = Field(default=None, ge=0)


# === Phase 2: Master Data CRUD ===
class VehicleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    plate_number: str = Field(min_length=1, max_length=24)
    code: Optional[str] = Field(default=None, max_length=32)
    type: Optional[str] = Field(default="hiace", max_length=40)
    capacity: int = Field(default=0, ge=0)
    status: Optional[str] = Field(default="available", max_length=32)
    kir_expiry: Optional[str] = None
    tax_expiry: Optional[str] = None
    last_service_date: Optional[str] = None
    next_service_date: Optional[str] = None
    odometer: Optional[float] = Field(default=0, ge=0)
    service_interval_km: Optional[float] = Field(default=None, ge=0)     # E8: interval servis preventif (km)
    service_interval_days: Optional[int] = Field(default=None, ge=0)     # E8: interval servis preventif (hari)
    last_service_odometer: Optional[float] = Field(default=None, ge=0)   # E8: odometer saat servis terakhir
    features: Optional[List[str]] = None
    notes: Optional[str] = Field(default="", max_length=2000)
    photos: Optional[List[str]] = None
    gallery: Optional[List[dict]] = None        # [{url, caption}]
    tour_scenes: Optional[List[dict]] = None    # [{id,label,panorama,thumbnail,links:[{nodeId,yaw,pitch}]}]
    exterior_frames: Optional[List[str]] = None  # frame 360 eksterior berurutan (jumlah bebas)
    rental_terms: Optional[List[str]] = None     # syarat & ketentuan sewa (tab publik)
    specs: Optional[List[dict]] = None          # [{key,label,value}]
    highlights: Optional[List[str]] = None
    year: Optional[int] = None
    color: Optional[str] = None
    # RC-B (INV-PRICE-02): `price_from`/`day_rate` DIHAPUS dari jalur tulis armada —
    # tarif per unit HANYA lewat Master Harga (PATCH /api/pricing/unit-rates/{id}).
    publish_to_web: Optional[bool] = True    # tayang & bisa dipesan di situs publik
    ownership: Optional[str] = "owned"       # E16: owned | partner
    partner_id: Optional[str] = None         # E16: tautan mitra bila ownership=partner


class VehicleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    plate_number: Optional[str] = Field(default=None, max_length=24)
    type: Optional[str] = Field(default=None, max_length=40)
    capacity: Optional[int] = Field(default=None, ge=0)
    status: Optional[str] = Field(default=None, max_length=32)
    kir_expiry: Optional[str] = None
    tax_expiry: Optional[str] = None
    last_service_date: Optional[str] = None
    next_service_date: Optional[str] = None
    odometer: Optional[float] = Field(default=None, ge=0)
    service_interval_km: Optional[float] = Field(default=None, ge=0)     # E8: interval servis preventif (km)
    service_interval_days: Optional[int] = Field(default=None, ge=0)     # E8: interval servis preventif (hari)
    last_service_odometer: Optional[float] = Field(default=None, ge=0)   # E8: odometer saat servis terakhir
    features: Optional[List[str]] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    photos: Optional[List[str]] = None
    gallery: Optional[List[dict]] = None
    tour_scenes: Optional[List[dict]] = None
    exterior_frames: Optional[List[str]] = None  # frame 360 eksterior berurutan (jumlah bebas)
    rental_terms: Optional[List[str]] = None     # syarat & ketentuan sewa (tab publik)
    specs: Optional[List[dict]] = None
    highlights: Optional[List[str]] = None
    year: Optional[int] = None
    color: Optional[str] = None
    # RC-B (INV-PRICE-02): tarif unit tidak bisa ditulis dari sini — pakai Master Harga.
    publish_to_web: Optional[bool] = None                    # tayang di situs publik
    ownership: Optional[str] = None          # E16: owned | partner
    partner_id: Optional[str] = None         # E16: tautan mitra


class DriverCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: Optional[str] = Field(default="", max_length=24)
    sim_number: Optional[str] = ""
    sim_expiry: Optional[str] = None
    status: Optional[str] = Field(default="offline", max_length=32)
    current_vehicle_id: Optional[str] = None
    rating: Optional[float] = Field(default=0, ge=0)
    # Rate fee /hari andalan — prefill otomatis di dialog Assign dispatch (tetap bisa diubah per keberangkatan).
    default_fee_rate: Optional[float] = Field(default=None, ge=0)
    # Akun login (Ruang Kerja Driver): tautkan user role=driver yang sudah ada ("" = lepas)
    # ATAU buat akun baru dari email+sandi. Pemetaan disimpan di drivers.user_id.
    user_id: Optional[str] = Field(default=None, max_length=60)
    account_email: Optional[str] = Field(default=None, max_length=160)
    account_password: Optional[str] = Field(default=None, max_length=200)


class DriverUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=24)
    sim_number: Optional[str] = None
    sim_expiry: Optional[str] = None
    status: Optional[str] = Field(default=None, max_length=32)
    current_vehicle_id: Optional[str] = None
    rating: Optional[float] = Field(default=None, ge=0)
    default_fee_rate: Optional[float] = Field(default=None, ge=0)
    user_id: Optional[str] = Field(default=None, max_length=60)
    account_email: Optional[str] = Field(default=None, max_length=160)
    account_password: Optional[str] = Field(default=None, max_length=200)


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: Optional[str] = Field(default="", max_length=24)
    email: Optional[str] = Field(default="", max_length=160)
    type: Optional[str] = Field(default="individual", max_length=40)
    city: Optional[str] = Field(default="", max_length=80)
    address: Optional[str] = Field(default="", max_length=300)
    notes: Optional[str] = Field(default="", max_length=2000)


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=24)
    email: Optional[str] = Field(default=None, max_length=160)
    type: Optional[str] = Field(default=None, max_length=40)
    city: Optional[str] = Field(default=None, max_length=80)
    address: Optional[str] = Field(default=None, max_length=300)
    notes: Optional[str] = Field(default=None, max_length=2000)


class PaymentCreate(BaseModel):
    booking_id: str
    amount: float = Field(gt=0)
    type: Optional[str] = Field(default="settlement", max_length=40)  # dp | settlement
    method: Optional[str] = "transfer"
    note: Optional[str] = Field(default="", max_length=1000)
    idempotency_key: Optional[str] = None  # anti double-submit: retry/klik-ganda dgn key sama → 1 pembayaran


# === Phase 3: Public website + lead capture ===
class QuotationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=3, max_length=24)
    email: Optional[str] = Field(default="", max_length=160)
    destination: Optional[str] = Field(default="", max_length=160)
    trip_date: Optional[str] = None
    pax: Optional[int] = Field(default=1, ge=0)
    message: Optional[str] = Field(default="", max_length=4000)
    hp: Optional[str] = ""  # honeypot anti-spam (harus kosong utk manusia)
    attribution: Optional[dict] = None  # E-ADS: {first_touch, last_touch, landing_page, referrer}
    marketing_consent: Optional[bool] = False  # E-ADS: persetujuan dihubungi promosi (WA/email)


class LeadAdsPayload(BaseModel):
    """Payload Lead Ads (mock-first) — fleksibel. Diterima apa adanya lalu dinormalisasi services/ads.py."""
    model_config = {"extra": "allow"}


class TripEstimateRequest(BaseModel):
    origin: Optional[str] = Field(default="", max_length=160)
    destination: Optional[str] = Field(default="", max_length=160)
    vehicle_type: Optional[str] = "hiace_premio"
    pax: Optional[int] = Field(default=1, ge=0)
    days: Optional[int] = Field(default=1, ge=0)
    distance_km: Optional[float] = Field(default=0, ge=0)
    trip_date: Optional[str] = None  # ISO; bila ada → surcharge weekend/libur (B1)
    hp: Optional[str] = ""  # honeypot anti-spam


class PublicBookingCreate(BaseModel):
    """E19: permintaan booking self-service dari situs publik → booking status 'pending'
    (menunggu persetujuan ops). Honeypot `hp` anti-spam; harga final ditentukan ops saat approve."""
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=3, max_length=24)
    email: Optional[str] = Field(default="", max_length=160)
    origin: Optional[str] = Field(default="", max_length=160)
    destination: Optional[str] = Field(default="", max_length=160)
    start_datetime: str
    end_datetime: str
    pax: Optional[int] = Field(default=1, ge=0)
    vehicle_type: Optional[str] = ""   # preferensi tipe armada (opsional)
    message: Optional[str] = Field(default="", max_length=4000)
    hp: Optional[str] = ""             # honeypot
    attribution: Optional[dict] = None
    marketing_consent: Optional[bool] = False


# === Phase 9 / Tahap B · B1: Pricing Engine ===
class PickupPointCreate(BaseModel):
    """INV-REF-02 batch 2: master titik jemput (quick-add dari form booking = tetap satu pintu master)."""
    name: str = Field(min_length=2, max_length=120)


class PickupPointUpdate(BaseModel):
    """Master Data: rename (cascade ke bookings.origin) / aktif-nonaktif."""
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    active: Optional[bool] = None


class MasterDestinationUpdate(BaseModel):
    """Master Data: rename destinasi (cascade booking/lead/penawaran) / toggle ops_active."""
    name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    ops_active: Optional[bool] = None


class CityCreate(BaseModel):
    """INV-REF-02 batch 5: master KOTA (customers.city & partners.city) — quick-add satu pintu."""
    name: str = Field(min_length=2, max_length=120)


class MasterCityUpdate(BaseModel):
    """Master Data: rename kota (cascade customers/partners) / aktif-nonaktif."""
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    active: Optional[bool] = None


class DestinationMergeRequest(BaseModel):
    """Gabung destinasi kembar: seluruh booking/lead/penawaran sumber pindah ke nama target."""
    target_id: str = Field(min_length=1, max_length=60)


class UnitDayRateUpdate(BaseModel):
    """Master Harga (RC-B): tulis tarif per unit. 0 = hapus override (pakai tarif tipe)."""
    day_rate: float = Field(default=0, ge=0, le=100_000_000)  # batas atas anti salah ketik


class PricingQuoteRequest(BaseModel):
    """Permintaan hitung harga internal (Booking wizard)."""
    vehicle_type: Optional[str] = None
    vehicle_id: Optional[str] = None
    days: Optional[int] = Field(default=1, ge=0)
    distance_km: Optional[float] = Field(default=0, ge=0)
    start_date: Optional[str] = None  # ISO; utk surcharge akhir pekan/hari libur


# === Phase 9 / Tahap B · B2: Quotation Lifecycle ===
class QuotationItemIn(BaseModel):
    label: str = Field(default="", max_length=120)
    amount: float = Field(default=0, ge=0)  # tak boleh negatif → cegah subtotal/total penawaran negatif


class QuotationDraftCreate(BaseModel):
    """Buat penawaran (QUO-xxxx) — dari lead/customer atau manual.
    Bila `items` kosong → dibangun otomatis dari Pricing Engine (B1)."""
    lead_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = ""
    phone: Optional[str] = Field(default="", max_length=24)
    email: Optional[str] = Field(default="", max_length=160)
    destination: Optional[str] = Field(default="", max_length=160)
    trip_date: Optional[str] = None
    pax: Optional[int] = Field(default=None, ge=0)
    vehicle_type: Optional[str] = None
    days: Optional[int] = Field(default=1, ge=0)
    distance_km: Optional[float] = Field(default=0, ge=0)
    items: Optional[List[QuotationItemIn]] = None
    notes: Optional[str] = Field(default="", max_length=2000)
    valid_days: Optional[int] = Field(default=7, ge=0)


class QuotationDraftUpdate(BaseModel):
    customer_name: Optional[str] = None
    phone: Optional[str] = Field(default=None, max_length=24)
    email: Optional[str] = Field(default=None, max_length=160)
    destination: Optional[str] = Field(default=None, max_length=160)
    trip_date: Optional[str] = None
    pax: Optional[int] = Field(default=None, ge=0)
    items: Optional[List[QuotationItemIn]] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    valid_until: Optional[str] = None


class QuotationConvert(BaseModel):
    """Konversi penawaran diterima → booking (butuh armada + jadwal)."""
    vehicle_id: str = Field(min_length=1)
    driver_id: Optional[str] = None
    start_datetime: str
    end_datetime: str


# === Phase 4: CRM Internal (pipeline, assignment, activities, broadcast) ===
class LeadCreate(BaseModel):
    customer_name: str = Field(min_length=1)
    phone: Optional[str] = Field(default="", max_length=24)
    email: Optional[str] = Field(default="", max_length=160)
    source: Optional[str] = "manual"  # website | whatsapp | manual
    destination: Optional[str] = Field(default="", max_length=160)
    trip_date: Optional[str] = None
    pax: Optional[int] = Field(default=1, ge=0)
    message: Optional[str] = Field(default="", max_length=4000)
    value: Optional[float] = Field(default=0, ge=0)
    stage: Optional[str] = "new"
    assigned_to: Optional[str] = None


class LeadUpdate(BaseModel):
    customer_name: Optional[str] = None
    phone: Optional[str] = Field(default=None, max_length=24)
    email: Optional[str] = Field(default=None, max_length=160)
    destination: Optional[str] = Field(default=None, max_length=160)
    trip_date: Optional[str] = None
    pax: Optional[int] = Field(default=None, ge=0)
    message: Optional[str] = Field(default=None, max_length=4000)
    value: Optional[float] = Field(default=None, ge=0)
    assigned_to: Optional[str] = None


class LeadStageUpdate(BaseModel):
    stage: str
    lost_reason: Optional[str] = ""


class LeadAssign(BaseModel):
    assigned_to: Optional[str] = None  # None → auto round-robin


class LeadActivityCreate(BaseModel):
    type: Optional[str] = Field(default="note", max_length=40)  # note | call
    text: str = Field(min_length=1)


class LeadConvert(BaseModel):
    note: Optional[str] = Field(default="", max_length=1000)


class BroadcastCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4000)
    segment_stage: Optional[str] = None
    segment_source: Optional[str] = None
    scheduled_at: Optional[str] = None



# === Phase 5: Keuangan & Laporan (expenses, invoices, finance, reports) ===
class ExpenseCreate(BaseModel):
    booking_id: Optional[str] = None
    trip_id: Optional[str] = None
    category: str = "other"  # bbm | tol | uang_jalan | other
    amount: float = Field(gt=0)
    note: Optional[str] = Field(default="", max_length=1000)


class ExpenseUpdate(BaseModel):
    booking_id: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = Field(default=None, gt=0)
    note: Optional[str] = Field(default=None, max_length=1000)


class InvoiceCreate(BaseModel):
    booking_id: str = Field(min_length=1)
    kind: Optional[str] = Field(default="full", max_length=20)  # dp | settlement | full
    dp_percent: Optional[float] = Field(default=None, ge=0, le=100)
    dp_amount: Optional[float] = Field(default=None, ge=0)
    amount: Optional[float] = Field(default=None, ge=0)  # override nominal (pelunasan/penuh)
    due_at: Optional[str] = None
    notes: Optional[str] = Field(default="", max_length=2000)
    terms: Optional[str] = Field(default=None, max_length=3000)
    bank_account_ids: Optional[list[str]] = None


class InvoiceStatusUpdate(BaseModel):
    status: Optional[str] = Field(default=None, max_length=32)  # draft | sent | partial | paid | void
    amount: Optional[float] = Field(default=None, ge=0)
    due_at: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    terms: Optional[str] = Field(default=None, max_length=3000)


class BroadcastUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    message: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    segment_stage: Optional[str] = None
    segment_source: Optional[str] = None


# === Phase 6: Maintenance + GPS lengkap (share-link) ===
class MaintenanceCreate(BaseModel):
    vehicle_id: str = Field(min_length=1)
    type: Optional[str] = Field(default="servis", max_length=40)  # servis | kir | pajak | perbaikan | lainnya
    title: Optional[str] = Field(default="", max_length=200)
    description: Optional[str] = ""
    scheduled_date: Optional[str] = None
    start_date: Optional[str] = None  # window mulai (memblok availability)
    end_date: Optional[str] = None    # window selesai
    odometer: Optional[float] = Field(default=0, ge=0)
    cost: Optional[float] = Field(default=0, ge=0)
    workshop: Optional[str] = ""
    workshop_id: Optional[str] = None  # E8: ref ke koleksi workshops (master vendor/bengkel)
    status: Optional[str] = Field(default="scheduled", max_length=32)  # scheduled | in_progress | done | cancelled
    note: Optional[str] = Field(default="", max_length=1000)


class MaintenanceUpdate(BaseModel):
    type: Optional[str] = Field(default=None, max_length=40)
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    scheduled_date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    odometer: Optional[float] = Field(default=None, ge=0)
    cost: Optional[float] = Field(default=None, ge=0)
    workshop: Optional[str] = None
    workshop_id: Optional[str] = None  # E8: ref ke koleksi workshops
    status: Optional[str] = Field(default=None, max_length=32)
    note: Optional[str] = Field(default=None, max_length=1000)


class MaintenanceComplete(BaseModel):
    completed_at: Optional[str] = None
    odometer: Optional[float] = Field(default=None, ge=0)
    cost: Optional[float] = Field(default=None, ge=0)
    note: Optional[str] = Field(default="", max_length=1000)


class ShareCreate(BaseModel):
    trip_id: str = Field(min_length=1)
    label: Optional[str] = Field(default="", max_length=120)
    hours: Optional[int] = Field(default=72, ge=0)  # masa berlaku tautan (jam)


# === Phase 7: CRM Inbox + Settings ===
class ConversationCreate(BaseModel):
    channel: Optional[str] = "internal"  # web | whatsapp | internal
    contact_name: Optional[str] = ""
    contact_phone: Optional[str] = ""
    subject: Optional[str] = Field(default="", max_length=200)
    customer_id: Optional[str] = None
    lead_id: Optional[str] = None
    assigned_to: Optional[str] = None
    message: Optional[str] = Field(default="", max_length=4000)  # pesan pembuka (opsional)


class ConversationUpdate(BaseModel):
    status: Optional[str] = Field(default=None, max_length=32)  # open | snoozed | closed
    assigned_to: Optional[str] = None   # "" untuk lepas assign
    snooze_until: Optional[str] = None


class MessageCreate(BaseModel):
    body: Optional[str] = ""
    internal: Optional[bool] = False  # True = catatan internal (tak terkirim ke kontak)
    template_key: Optional[str] = None  # E1: kirim via template WA (di luar window 24 jam)


class PublicChatCreate(BaseModel):
    name: Optional[str] = Field(default="", max_length=120)
    phone: Optional[str] = Field(default="", max_length=24)
    message: str = Field(min_length=1, max_length=4000)
    token: Optional[str] = None  # lanjutkan percakapan yang sama
    hp: Optional[str] = ""  # honeypot anti-spam


class SettingsUpdate(BaseModel):
    company_info: Optional[dict] = None
    pricing_defaults: Optional[dict] = None
    pricing_rules: Optional[dict] = None  # B1: Pricing Engine (tarif/surcharge/DP)
    operational: Optional[dict] = None
    map_provider: Optional[str] = None
    theme_config: Optional[dict] = None  # P10: tema situs publik {preset, mode}
    booking_flow: Optional[dict] = None  # alur pemesanan online (mode, batas DP, instruksi bayar)


# === E1: Event Bus + Automation Engine + WhatsApp Adapter ===
class AutomationCondition(BaseModel):
    field: str
    op: Optional[str] = "eq"  # eq|ne|in|contains|exists|gt|lt
    value: Optional[object] = None


class AutomationAction(BaseModel):
    type: str = Field(max_length=40)  # send_wa|create_notification|create_task|assign_agent|schedule_followup
    params: Optional[dict] = None


class AutomationRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = ""
    event_type: str = Field(min_length=1)
    enabled: Optional[bool] = True
    conditions: Optional[List[AutomationCondition]] = None
    actions: Optional[List[AutomationAction]] = None


class AutomationRuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = None
    event_type: Optional[str] = None
    enabled: Optional[bool] = None
    conditions: Optional[List[AutomationCondition]] = None
    actions: Optional[List[AutomationAction]] = None


class WaConfigUpdate(BaseModel):
    provider: Optional[str] = None  # mock|meta_cloud|partner
    business_phone: Optional[str] = None
    price_per_message: Optional[float] = Field(default=None, ge=0)
    session_hours: Optional[int] = Field(default=None, ge=0)
    auto_reply_enabled: Optional[bool] = None
    auto_reply_text: Optional[str] = None
    away_reply_text: Optional[str] = None
    meta: Optional[dict] = None  # {phone_number_id, access_token, verify_token, app_secret}


class WaTemplateUpsert(BaseModel):
    name: Optional[str] = Field(default="", max_length=120)
    language: Optional[str] = "id"
    category: Optional[str] = "utility"
    body: str = Field(min_length=1)


class WaSimulateInbound(BaseModel):
    from_phone: str = Field(min_length=3)
    text: str = Field(min_length=1)
    name: Optional[str] = Field(default=None, max_length=120)
    # FASE F5 — simulasi Klik-ke-WhatsApp: {source_type:'ad', source_id:'<ad_id>', ctwa_clid, headline}
    referral: Optional[dict] = None


class WaTestSend(BaseModel):
    to_phone: str = Field(min_length=3)
    text: Optional[str] = "Tes koneksi WhatsApp dari RAHAZA ERP. ✅"


# === E2: CRM Growth Engine (scoring/SLA/RFM, segments, sequences, campaigns) ===
class SegmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    audience: Optional[str] = "customer"  # lead | customer
    criteria: Optional[dict] = None
    description: Optional[str] = ""


class SegmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    audience: Optional[str] = None
    criteria: Optional[dict] = None
    description: Optional[str] = None


class SequenceStep(BaseModel):
    delay_hours: Optional[float] = Field(default=0, ge=0)
    action: Optional[str] = "send_wa"  # send_wa | create_task | create_notification
    template_key: Optional[str] = None
    text: Optional[str] = None


class SequenceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = ""
    audience: Optional[str] = "lead"
    enabled: Optional[bool] = True
    steps: Optional[List[SequenceStep]] = None


class SequenceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = None
    audience: Optional[str] = None
    enabled: Optional[bool] = None
    steps: Optional[List[SequenceStep]] = None


class SequenceEnrollRequest(BaseModel):
    target_id: Optional[str] = None
    segment_id: Optional[str] = None


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    audience: Optional[str] = "customer"
    segment_id: Optional[str] = None
    criteria: Optional[dict] = None
    template_key: Optional[str] = None
    message: Optional[str] = Field(default=None, max_length=4000)
    scheduled_at: Optional[str] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    segment_id: Optional[str] = None
    criteria: Optional[dict] = None
    template_key: Optional[str] = None
    message: Optional[str] = Field(default=None, max_length=4000)
    scheduled_at: Optional[str] = None


class GrowthConfigUpdate(BaseModel):
    sla_first_response_hours: Optional[float] = Field(default=None, ge=0)
    at_risk_days: Optional[int] = Field(default=None, ge=0)
    churn_days: Optional[int] = Field(default=None, ge=0)
    hot_threshold: Optional[int] = Field(default=None, ge=0)
    warm_threshold: Optional[int] = Field(default=None, ge=0)
    source_weights: Optional[dict] = None


# --- E4 BI & Management Cockpit ---
class MarketingSpendItem(BaseModel):
    channel: str = Field(min_length=1)
    amount: float = Field(default=0.0, ge=0)


class MarketingSpendUpdate(BaseModel):
    items: List[MarketingSpendItem] = []
    note: Optional[str] = Field(default="", max_length=1000)


# === E8: Master Vendor/Bengkel (workshops) ===
class WorkshopCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: Optional[str] = Field(default="", max_length=24)
    address: Optional[str] = Field(default="", max_length=300)
    city: Optional[str] = Field(default="", max_length=80)
    specialties: Optional[List[str]] = None  # mis. ["servis","rem","ac","body"]
    note: Optional[str] = Field(default="", max_length=1000)
    active: Optional[bool] = True


class WorkshopUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=24)
    address: Optional[str] = Field(default=None, max_length=300)
    city: Optional[str] = Field(default=None, max_length=80)
    specialties: Optional[List[str]] = None
    note: Optional[str] = Field(default=None, max_length=1000)
    active: Optional[bool] = None


# === E10: Master Jenis Service (service_types) ===
class ServiceTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    default_interval_km: Optional[float] = Field(default=None, ge=0)
    default_interval_days: Optional[int] = Field(default=None, ge=0)
    active: Optional[bool] = True


class ServiceTypeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    default_interval_km: Optional[float] = Field(default=None, ge=0)
    default_interval_days: Optional[int] = Field(default=None, ge=0)
    active: Optional[bool] = None


# === E11: Driver Payroll / HR Lite (kompensasi + payouts) ===
class DriverCompUpdate(BaseModel):
    """Konfigurasi kompensasi per driver (embedded drivers.comp)."""
    base_salary_monthly: Optional[float] = Field(default=None, ge=0)
    commission_per_trip: Optional[float] = Field(default=None, ge=0)
    commission_pct_revenue: Optional[float] = Field(default=None, ge=0)  # persen
    allowance_per_km: Optional[float] = Field(default=None, ge=0)
    revenue_base: Optional[str] = None  # trip | booking
    enable_base: Optional[bool] = None
    enable_commission_trip: Optional[bool] = None
    enable_commission_pct: Optional[bool] = None
    enable_allowance_km: Optional[bool] = None


class PayoutLineIn(BaseModel):
    label: str = Field(default="", max_length=120)
    amount: float = Field(default=0, ge=0)


class PayoutGenerate(BaseModel):
    driver_id: str = Field(min_length=1)
    period_type: str = "monthly"  # monthly | weekly | per_trip
    period_start: str = Field(min_length=8)  # YYYY-MM-DD
    period_end: str = Field(min_length=8)    # YYYY-MM-DD


class PayoutBulkGenerate(BaseModel):
    period_type: str = "monthly"
    period_start: str = Field(min_length=8)
    period_end: str = Field(min_length=8)
    driver_ids: Optional[List[str]] = None  # None = semua driver


class PayoutUpdate(BaseModel):
    bonuses: Optional[List[PayoutLineIn]] = None
    deductions: Optional[List[PayoutLineIn]] = None
    notes: Optional[str] = Field(default=None, max_length=2000)

"""schemas_booking.py — kontrak permintaan untuk PEMESANAN ONLINE + rute antar-jemput.

Dipisah dari `schemas.py` (yang sudah mendekati batas 800 baris) mengikuti pola
`schemas_landing.py`. Semua nominal uang = integer rupiah; harga TIDAK PERNAH diterima
dari klien — field harga sengaja tidak ada di skema ini (dijaga INV-BOOK-02).
"""
from typing import List, Optional

from pydantic import BaseModel, Field

SERVICE_PATTERN = r"^(daily_rental|airport_transfer)$"


class AddOnItem(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    amount: float = Field(default=0, ge=0)


class BookingSearchRequest(BaseModel):
    """Cari unit yang bebas + harga (tanpa menulis apa pun ke database)."""
    service: str = Field(default="daily_rental", pattern=SERVICE_PATTERN)
    start_datetime: str = Field(min_length=4)
    end_datetime: Optional[str] = ""
    days: Optional[int] = Field(default=None, ge=1, le=90)
    pax: Optional[int] = Field(default=1, ge=0, le=100)
    vehicle_type: Optional[str] = ""
    route_id: Optional[str] = ""
    promo_code: Optional[str] = ""
    origin: Optional[str] = Field(default="", max_length=160)
    destination: Optional[str] = Field(default="", max_length=160)


class BookingQuoteRequest(BaseModel):
    """Rincian harga satu unit untuk langkah tinjau (server yang menghitung)."""
    service: str = Field(default="daily_rental", pattern=SERVICE_PATTERN)
    vehicle_id: str = Field(min_length=1)
    start_datetime: str = Field(min_length=4)
    end_datetime: Optional[str] = ""
    route_id: Optional[str] = ""
    pax: Optional[int] = Field(default=1, ge=0, le=100)
    promo_code: Optional[str] = ""
    add_ons: Optional[List[AddOnItem]] = None


class BookingPromoListRequest(BaseModel):
    """Daftar promo yang berlaku untuk konteks pesanan (tanpa satu pun angka harga dari klien).

    Sengaja meminta `vehicle_id` + tanggal, BUKAN subtotal: subtotal dihitung ulang server
    memakai mesin harga yang sama dengan checkout (INV-BOOK-02). Kalau subtotal boleh dikirim
    klien, siapa pun bisa memalsukan angka agar promo bersyarat "min. Rp 3 juta" ikut lolos.
    """
    service: str = Field(default="daily_rental", pattern=SERVICE_PATTERN)
    vehicle_id: str = Field(min_length=1)
    start_datetime: str = Field(min_length=4)
    end_datetime: Optional[str] = ""
    route_id: Optional[str] = ""
    pax: Optional[int] = Field(default=1, ge=0, le=100)


class PublicBookingSubmit(BaseModel):
    """Buat pesanan sungguhan dari situs publik (unit + harga nyata)."""
    service: str = Field(default="daily_rental", pattern=SERVICE_PATTERN)
    vehicle_id: str = Field(min_length=1)
    route_id: Optional[str] = ""
    start_datetime: str = Field(min_length=4)
    end_datetime: Optional[str] = ""
    pax: Optional[int] = Field(default=1, ge=0, le=100)
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=6, max_length=24)
    email: Optional[str] = Field(default="", max_length=160)
    origin: Optional[str] = Field(default="", max_length=160)
    destination: Optional[str] = Field(default="", max_length=160)
    pickup_address: Optional[str] = ""
    message: Optional[str] = Field(default="", max_length=4000)
    promo_code: Optional[str] = ""
    add_ons: Optional[List[AddOnItem]] = None
    marketing_consent: Optional[bool] = False
    attribution: Optional[dict] = None
    idempotency_key: Optional[str] = ""
    hp: Optional[str] = ""  # honeypot anti-bot


class BookingLookupRequest(BaseModel):
    code: str = Field(min_length=3, max_length=20)
    phone: str = Field(min_length=6, max_length=24)


class BookingCancelRequest(BaseModel):
    token: str = Field(min_length=8, max_length=80)
    reason: Optional[str] = Field(default="", max_length=400)


class TransferRouteUpsert(BaseModel):
    """Rute antar-jemput bandara + tarif FLAT per tipe armada."""
    code: Optional[str] = Field(default="", max_length=24)
    name: str = Field(min_length=2, max_length=120)
    from_label: str = Field(min_length=2, max_length=120)
    to_label: str = Field(min_length=2, max_length=120)
    airport_code: Optional[str] = Field(default="", max_length=8)
    rates: dict = Field(default_factory=dict)   # {vehicle_type: rupiah}
    duration_minutes: Optional[int] = Field(default=180, ge=30, le=1440)
    notes: Optional[str] = Field(default="", max_length=400)
    active: Optional[bool] = True
    position: Optional[int] = Field(default=0, ge=0, le=999)


class ProofVerifyRequest(BaseModel):
    """Verifikasi bukti transfer oleh ops → catat pembayaran (hold otomatis → confirmed)."""
    amount: Optional[float] = Field(default=None, ge=0)
    method: Optional[str] = Field(default="transfer", max_length=24)
    note: Optional[str] = Field(default="", max_length=400)


class ProofRejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=240)


class ApproveHoldRequest(BaseModel):
    """Mode ops_approval: setujui permintaan → tahan unit + minta DP (pending → hold)."""
    vehicle_id: Optional[str] = ""
    hold_hours: Optional[int] = Field(default=None, ge=1, le=168)
    recompute_price: Optional[bool] = True

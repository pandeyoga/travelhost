"""services/booking_flow.py — konfigurasi ALUR PEMESANAN ONLINE (settings.booking_flow).

Kenapa modul ini ada
--------------------
Permintaan pemilik: pemesanan dari website harus bisa dijalankan dengan DUA cara, dan
lamanya batas waktu harus bisa diatur sendiri (bukan angka mati di kode):

  mode = "hold_dp"       → pesanan tamu LANGSUNG menahan unit (`status='hold'`) dengan
                            batas waktu DP; lewat batas, hold dilepas otomatis oleh
                            penjadwal (services/notifications.py) dan unit kembali dijual.
  mode = "ops_approval"  → pesanan masuk sebagai `pending`; ops menyetujui dulu, baru
                            unit ditahan (`hold`) dan tamu diminta membayar DP.

Pembayaran DP = TRANSFER MANUAL + UNGGAH BUKTI (tanpa payment gateway). Karena itu
instruksi pembayaran (rekening/QRIS/catatan) juga tersimpan di sini supaya halaman status
pesanan menampilkan data yang sama dengan yang dipakai ops saat verifikasi.

Semua batas waktu punya PAGAR nilai (mis. hold 1–168 jam): angka 0 atau negatif akan
membuat pesanan kedaluwarsa sebelum tamu selesai membaca instruksi, dan angka raksasa
membuat unit terkunci berbulan-bulan tanpa uang masuk.
"""
import secrets
from datetime import datetime, timedelta, timezone

from core_utils import money

MODES = ("hold_dp", "ops_approval")

# Layanan yang boleh dipesan ONLINE. Sengaja TIDAK memakai koleksi `service_types` —
# koleksi itu berisi jenis servis BENGKEL (ganti oli, ganti ban, spooring), bukan produk
# perjalanan. Memakainya akan jadi contoh sempurna "mengambil collection yang salah".
SERVICES = {
    "daily_rental": {
        "value": "daily_rental",
        "label": "Sewa Harian + Driver",
        "tagline": "Unit lengkap dengan driver, dihitung per hari",
        "price_basis": "per hari",
    },
    "airport_transfer": {
        "value": "airport_transfer",
        "label": "Antar-Jemput Bandara",
        "tagline": "Tarif flat per rute, sekali jalan",
        "price_basis": "flat per rute",
    },
}
# Permintaan tanpa unit (paket wisata/lepas kunci/kebutuhan khusus) tetap lewat jalur
# penawaran: dicatat sebagai booking `pending` tanpa armada, harga ditetapkan ops.
SERVICE_REQUEST_ONLY = "request_only"

DEFAULT_FLOW = {
    "mode": "hold_dp",
    "hold_hours": 2,               # batas DP untuk pesanan mode hold_dp
    "approval_hold_hours": 24,     # batas DP setelah ops menyetujui (mode ops_approval)
    "approval_sla_hours": 6,       # janji lama ops meninjau (ditampilkan ke tamu)
    "min_lead_hours": 4,           # jarak minimal dari sekarang ke jam keberangkatan
    "max_advance_days": 180,       # sejauh mana ke depan boleh dipesan
    "min_days": 1,
    "max_days": 30,
    "transfer_buffer_minutes": 120,  # jeda unit kembali setelah antar-jemput bandara
    "enabled_services": ["daily_rental", "airport_transfer"],
    "payment": {
        "bank_accounts": [],
        "qris_media_id": "",
        "instructions": ("Transfer DP sesuai nominal, lalu unggah bukti pada halaman status "
                         "pesanan. Tim kami memverifikasi maksimal 1×24 jam kerja."),
    },
    "cancellation_policy": "",
    "terms": "",
}

_BOUNDS = {
    "hold_hours": (1, 168),
    "approval_hold_hours": (1, 168),
    "approval_sla_hours": (1, 168),
    "min_lead_hours": (0, 168),
    "max_advance_days": (1, 730),
    "min_days": (1, 30),
    "max_days": (1, 90),
    "transfer_buffer_minutes": (0, 720),
}


class FlowError(ValueError):
    """Konfigurasi/permintaan alur booking ditolak → 4xx berALASAN."""


def merge_flow(value) -> dict:
    out = {k: (dict(v) if isinstance(v, dict) else (list(v) if isinstance(v, list) else v))
           for k, v in DEFAULT_FLOW.items()}
    if isinstance(value, dict):
        for key, val in value.items():
            if val is None:
                continue
            if key == "payment" and isinstance(val, dict):
                pay = dict(DEFAULT_FLOW["payment"])
                pay.update({k: v for k, v in val.items() if v is not None})
                accounts = pay.get("bank_accounts")
                pay["bank_accounts"] = [a for a in (accounts or []) if isinstance(a, dict)][:6]
                out["payment"] = pay
            else:
                out[key] = val
    out["mode"] = out.get("mode") if out.get("mode") in MODES else DEFAULT_FLOW["mode"]
    services = [s for s in (out.get("enabled_services") or []) if s in SERVICES]
    out["enabled_services"] = services or list(DEFAULT_FLOW["enabled_services"])
    for key, (lo, hi) in _BOUNDS.items():
        out[key] = int(max(lo, min(hi, money(out.get(key)) or DEFAULT_FLOW[key])))
    if out["max_days"] < out["min_days"]:
        out["max_days"] = out["min_days"]
    return out


def validate_patch(value):
    """Validasi input PATCH /api/settings → pesan 400 yang bisa dibaca owner."""
    if not isinstance(value, dict):
        raise FlowError("Konfigurasi alur booking harus berupa objek")
    if value.get("mode") is not None and value.get("mode") not in MODES:
        raise FlowError("Mode alur booking harus 'hold_dp' atau 'ops_approval'")
    for key, (lo, hi) in _BOUNDS.items():
        if value.get(key) is None:
            continue
        raw = value.get(key)
        if isinstance(raw, bool):
            raise FlowError(f"Nilai '{key}' harus berupa angka")
        try:
            num = float(raw)
        except (TypeError, ValueError):
            raise FlowError(f"Nilai '{key}' harus berupa angka") from None
        if not (lo <= num <= hi):
            raise FlowError(f"Nilai '{key}' harus antara {lo}–{hi}")
    services = value.get("enabled_services")
    if services is not None:
        if not isinstance(services, list) or any(s not in SERVICES for s in services):
            raise FlowError("Layanan online hanya boleh: " + ", ".join(SERVICES))
    pay = value.get("payment")
    if pay is not None:
        if not isinstance(pay, dict):
            raise FlowError("Instruksi pembayaran harus berupa objek")
        accounts = pay.get("bank_accounts")
        if accounts is not None and (not isinstance(accounts, list)
                                     or any(not isinstance(a, dict) for a in accounts)):
            raise FlowError("Daftar rekening harus berupa daftar objek {bank, number, holder}")


async def get_flow(db) -> dict:
    doc = await db.settings.find_one({"key": "booking_flow"}, {"_id": 0})
    flow = merge_flow(doc.get("value") if doc else None)
    if not flow.get("cancellation_policy"):
        legacy = await db.settings.find_one({"key": "pricing_defaults"}, {"_id": 0})
        flow["cancellation_policy"] = ((legacy or {}).get("value") or {}).get(
            "cancellation_policy") or ""
    return flow


def new_public_token() -> str:
    """Token rahasia halaman status pesanan (tanpa akun pelanggan)."""
    return secrets.token_urlsafe(24)


def hold_fields(*, total, dp_percent, hold_hours, now=None) -> dict:
    """Field reservasi DP (dipakai jalur publik & persetujuan ops) — SSOT bentuknya."""
    base = now or datetime.now(timezone.utc)
    hours = int(max(1, min(168, money(hold_hours) or 2)))
    pct = float(max(0, min(100, money(dp_percent))))
    return {
        "hold_expires_at": (base + timedelta(hours=hours)).isoformat(),
        "hold_hours": hours,
        "dp_percent": pct,
        "dp_amount": money(money(total) * pct / 100.0),
    }


def validate_window(flow, *, start_dt, end_dt, now=None, service="daily_rental"):
    """Aturan jendela waktu pemesanan online. `raise FlowError` dgn alasan yang jelas."""
    base = now or datetime.now(timezone.utc)
    if not start_dt:
        raise FlowError("Tanggal & jam mulai wajib diisi")
    if end_dt and end_dt <= start_dt:
        raise FlowError("Waktu selesai harus setelah waktu mulai")
    lead_hours = (start_dt - base).total_seconds() / 3600.0
    min_lead = int(flow.get("min_lead_hours", 4))
    if lead_hours < min_lead:
        raise FlowError(f"Pemesanan online minimal {min_lead} jam sebelum keberangkatan. "
                        f"Untuk keberangkatan lebih cepat, hubungi kami via WhatsApp.")
    max_adv = int(flow.get("max_advance_days", 180))
    if (start_dt - base).days > max_adv:
        raise FlowError(f"Pemesanan online paling jauh {max_adv} hari ke depan.")
    if service == "daily_rental" and end_dt:
        from services.pricing import span_days
        days = span_days(start_dt, end_dt)
        if days < int(flow.get("min_days", 1)):
            raise FlowError(f"Durasi minimal {int(flow.get('min_days', 1))} hari.")
        if days > int(flow.get("max_days", 30)):
            raise FlowError(f"Durasi maksimal {int(flow.get('max_days', 30))} hari untuk "
                            f"pemesanan online. Sewa lebih lama? Minta penawaran khusus.")


def service_meta(service) -> dict:
    return SERVICES.get(str(service or "").strip(), {
        "value": SERVICE_REQUEST_ONLY, "label": "Permintaan Khusus",
        "tagline": "Harga & unit ditetapkan tim kami", "price_basis": "penawaran"})

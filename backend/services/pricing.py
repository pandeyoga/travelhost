"""services/pricing.py — Pricing Engine v2 (Fase B1 → B2 “harga digerakkan HARI”).

Satu sumber harga dipakai bersama SEMUA permukaan: estimator publik
(`/api/public/trip-estimate`), pencarian & checkout pemesanan online
(`/api/public/booking/*`), quote internal (`/api/pricing/quote`), penawaran
(`/api/quotations`), dan auto-isi `base_price` saat ops membuat booking.
Aturan tersimpan di koleksi `settings` (key='pricing_rules'); `DEFAULT_PRICING_RULES`
menjaga sistem tetap jalan sebelum owner mengisi apa pun.

PERUBAHAN PENTING v2 — KOMPONEN BERBASIS JARAK DIHAPUS
------------------------------------------------------
Dulu total memuat baris "Estimasi BBM (x km)" = `fuel_per_km × distance_km`, sementara
`distance_km` DIISI PENGUNJUNG lewat penggeser di kalkulator publik (nilai awal 300 km).
Artinya angka rupiah yang ditawarkan ke pelanggan bergantung pada tebakan pengunjung —
tidak bisa dipertanggungjawabkan, dan tidak mungkin identik dengan harga di ERP.
Sejak v2 penggerak harga sewa harian hanya: JUMLAH HARI × tarif harian (+ surcharge
tanggal + jasa driver/hari + tol-parkir/hari + add-on − promo). Parameter `distance_km`
MASIH diterima agar pemanggil lama tidak pecah, tetapi TIDAK memengaruhi total sama
sekali (dikunci guardrail INV-PRICE-01). Jarak tetap dipakai di tempat yang benar:
pelacakan GPS/ETA (services/osrm.py) — bukan untuk menghitung tagihan.

TARIF RESMI (SSOT) — urutan penentu tarif harian:
  1. `vehicles.day_rate`  → tarif resmi PER UNIT (mis. Premio 2023 lebih mahal),
  2. `pricing_rules.day_rates[<tipe>]` → tarif per TIPE armada,
  3. `pricing_rules.default_day_rate`  → jaring terakhir.
Dulu situs memakai `vehicles.price_from` (angka pemasaran, sering kosong) sementara
mesin memakai tarif tipe → "harga tampil ≠ harga tagih". Sekarang harga yang TAMPIL
di katalog/pencarian berasal dari fungsi ini juga, jadi tidak bisa berbeda lagi.

Uang = INTEGER rupiah (RC-11). Semua nominal keluaran sudah dibulatkan.
"""
from datetime import datetime, timezone  # noqa: F401  (timezone dipakai konsumen)

# Default contoh agar sistem langsung jalan; owner ubah via Pengaturan tanpa deploy.
DEFAULT_PRICING_RULES = {
    "day_rates": {
        "hiace_premio": 1500000,
        "hiace": 1200000,
        "elf": 1600000,
        "bus": 2500000,
        "avanza": 900000,
    },
    "default_day_rate": 1200000,
    "driver_fee_per_day": 250000,
    "toll_parking_per_day": 200000,
    "weekend_surcharge_percent": 20,
    "holiday_surcharge_percent": 30,
    "dp_percent": 30,
    "rounding": 1000,
}

# Kunci aturan yang SUDAH TIDAK DIPAKAI menghitung harga (dipertahankan agar dokumen
# `settings` lama tetap termuat & validasi lama tetap berlaku, tapi diabaikan mesin).
DEPRECATED_RULE_KEYS = ("fuel_per_km",)

# Tipe armada yang dikenal editor aturan harga. Untuk PILIHAN di UI publik jangan pakai
# daftar statis ini — pakai `available_vehicle_types(db)` supaya pengunjung tidak pernah
# ditawari tipe yang tak punya tarif & tak punya unit (bug lama: "Alphard" di form web).
VEHICLE_TYPES = ["hiace_premio", "hiace", "elf", "bus", "avanza"]

VEHICLE_TYPE_LABELS = {
    "hiace_premio": "Hiace Premio",
    "hiace": "Hiace Commuter",
    "elf": "Elf / Microbus",
    "bus": "Bus Besar",
    "avanza": "Avanza / MPV",
}


def type_label(vehicle_type) -> str:
    key = str(vehicle_type or "").strip()
    return VEHICLE_TYPE_LABELS.get(key, key.replace("_", " ").title() or "Armada")


def _num(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _int(value, default=0):
    return int(round(_num(value, default)))


def merge_rules(rules):
    """Gabungkan aturan tersimpan dengan default (default mengisi field yang hilang)."""
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULT_PRICING_RULES.items()}
    if isinstance(rules, dict):
        for key, val in rules.items():
            if key == "day_rates" and isinstance(val, dict):
                merged = dict(DEFAULT_PRICING_RULES["day_rates"])
                merged.update({k: v for k, v in val.items() if v is not None})
                out["day_rates"] = merged
            elif val is not None:
                out[key] = val
    return out


async def get_pricing_rules(db):
    """Ambil aturan harga aktif (DB → default)."""
    doc = await db.settings.find_one({"key": "pricing_rules"}, {"_id": 0})
    return merge_rules(doc.get("value") if doc else None)


async def get_dp_percent(db) -> int:
    """SATU-SATUNYA sumber persentase DP (0–100).

    Dulu ada DUA sumber: `pricing_rules.dp_percent` (dipakai estimator web) dan
    `pricing_defaults.dp_percent` (dipakai ERP saat membuat hold + pesan WA). Owner yang
    mengubah salah satu saja membuat DP di website berbeda dari DP yang ditagih ops —
    selisih uang yang tidak bisa dijelaskan ke pelanggan. Sekarang seluruh kode WAJIB
    lewat fungsi ini (dijaga guardrail INV-PRICE-01); `pricing_defaults.dp_percent`
    hanya dibaca sebagai cadangan untuk data lama.
    """
    doc = await db.settings.find_one({"key": "pricing_rules"}, {"_id": 0})
    val = (doc.get("value") or {}).get("dp_percent") if doc else None
    if val is None:
        legacy = await db.settings.find_one({"key": "pricing_defaults"}, {"_id": 0})
        val = (legacy.get("value") or {}).get("dp_percent") if legacy else None
    if val is None:
        val = DEFAULT_PRICING_RULES["dp_percent"]
    return int(max(0.0, min(100.0, _num(val, 30))))


async def available_vehicle_types(db, only_published: bool = True) -> list:
    """Tipe armada yang BENAR-BENAR ada unitnya (opsional: hanya yang tayang di web).

    Dipakai untuk mengisi pilihan tipe di UI publik & ERP. Ini menutup cacat lama di mana
    form publik menawarkan tipe yang tidak ada tarifnya (harga jatuh senyap ke default)
    dan tidak ada unitnya (ops tak bisa memenuhi pesanan).
    """
    query = {}
    if only_published:
        from services import booking_search as bs
        query = bs.publishable_filter()
    rules = await get_pricing_rules(db)
    rows = await db.vehicles.find(query, {"_id": 0, "type": 1, "capacity": 1, "day_rate": 1}).to_list(500)
    seen = {}
    for v in rows:
        vt = str(v.get("type") or "").strip()
        if not vt:
            continue
        rate, _basis = resolve_day_rate(rules, vehicle=v, vehicle_type=vt)
        cur = seen.get(vt)
        cap = _int(v.get("capacity"))
        if not cur:
            seen[vt] = {"value": vt, "label": type_label(vt), "from_price": rate,
                        "max_capacity": cap, "units": 1}
        else:
            cur["from_price"] = min(cur["from_price"], rate) if cur["from_price"] else rate
            cur["max_capacity"] = max(cur["max_capacity"], cap)
            cur["units"] += 1
    return sorted(seen.values(), key=lambda x: (x["from_price"], x["label"]))


def resolve_day_rate(rules, *, vehicle=None, vehicle_type=None):
    """Tarif harian resmi + dasar penetapannya → (int rupiah, label dasar).

    Urutan: tarif unit (`vehicles.day_rate`) → tarif tipe → tarif default.
    """
    rules = merge_rules(rules)
    vtype = str((vehicle or {}).get("type") or vehicle_type or "").strip()
    unit_rate = _num((vehicle or {}).get("day_rate"), 0)
    if unit_rate > 0:
        return int(round(unit_rate)), "tarif unit"
    day_rates = rules.get("day_rates") or {}
    if vtype and day_rates.get(vtype) is not None:
        return _int(day_rates.get(vtype)), "tarif tipe"
    return _int(rules.get("default_day_rate")), "tarif default"


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def span_days(start, end) -> int:
    """Jumlah hari tagihan dari rentang waktu (SSOT — dipakai web & ERP).

    Dibulatkan KE ATAS dan minimal 1: pemakaian 26 jam = 2 hari, sesuai praktik sewa
    harian. Rumus ini sengaja satu tempat agar harga di web tidak pernah beda dari ERP.
    """
    s, e = _parse_dt(start), _parse_dt(end)
    if not s or not e:
        return 1
    import math
    return max(math.ceil((e - s).total_seconds() / 86400), 1)


def _surcharge_for_date(rules, when, holidays):
    """(persen, label) surcharge untuk tanggal `when`. Hari libur diutamakan > akhir pekan."""
    if not when:
        return 0, None
    day_key = when.date().isoformat()
    hol = {str(h)[:10] for h in (holidays or []) if h}
    if day_key in hol:
        return _num(rules.get("holiday_surcharge_percent")), "Surcharge hari libur"
    if when.weekday() >= 5:  # 5=Sabtu, 6=Minggu
        return _num(rules.get("weekend_surcharge_percent")), "Surcharge akhir pekan"
    return 0, None


def _round(amount, rounding):
    step = int(_num(rounding) or 0)
    if step > 0:
        return int(round(amount / step) * step)
    return int(round(amount))


def compute_quote(rules, *, vehicle_type=None, days=1, distance_km=0,
                  when=None, holidays=None, include_travel=True,
                  day_rate=None, flat_amount=None, service="daily_rental",
                  add_ons=None, discount=0, discount_label="", dp_percent=None):
    """Hitung rincian harga ber-item (semua nominal = integer rupiah).

    include_travel=True  → sertakan jasa driver + tol/parkir per hari (sewa harian).
    include_travel=False → hanya komponen inti + surcharge (mis. tarif flat bandara).
    day_rate             → tarif harian resmi hasil `resolve_day_rate` (menimpa tarif tipe).
    flat_amount          → tarif FLAT (antar-jemput bandara); mengabaikan tarif harian.
    add_ons              → [{label, amount}] layanan tambahan yang dipilih pelanggan.
    discount             → potongan (mis. promo) yang SUDAH divalidasi server.
    distance_km          → DIABAIKAN (lihat docstring modul; parameter dipertahankan
                           hanya agar pemanggil lama tidak pecah).

    Return: {breakdown[], subtotal, surcharge_percent, discount, total, dp_percent,
             dp_amount, days, vehicle_type, service, day_rate}
    """
    rules = merge_rules(rules)
    days = max(_int(days, 1), 1)
    vtype = vehicle_type or "hiace_premio"
    breakdown = []

    if flat_amount is not None:
        core = max(_int(flat_amount), 0)
        breakdown.append({"label": "Tarif antar-jemput (flat per rute)", "amount": core})
    else:
        rate = _num(day_rate) if _num(day_rate) > 0 else _num(
            (rules.get("day_rates") or {}).get(vtype, rules.get("default_day_rate")))
        core = int(round(rate * days))
        breakdown.append({"label": f"Sewa unit ({days} hari)", "amount": core})

    pct, label = _surcharge_for_date(rules, _parse_dt(when), holidays)
    if pct:
        breakdown.append({"label": f"{label} (+{int(pct)}%)", "amount": int(round(core * pct / 100.0))})

    if include_travel:
        breakdown.append({"label": f"Jasa driver ({days} hari)",
                          "amount": int(round(_num(rules.get("driver_fee_per_day")) * days))})
        breakdown.append({"label": "Tol & parkir (estimasi)",
                          "amount": int(round(_num(rules.get("toll_parking_per_day")) * days))})

    for extra in (add_ons or []):
        amount = _int((extra or {}).get("amount"))
        if amount:
            breakdown.append({"label": str((extra or {}).get("label") or "Layanan tambahan")[:80],
                              "amount": amount})

    gross = sum(b["amount"] for b in breakdown)
    disc = max(_int(discount), 0)
    disc = min(disc, gross)  # potongan tidak boleh membuat total negatif
    if disc:
        breakdown.append({"label": discount_label or "Potongan promo", "amount": -disc})

    subtotal = gross - disc
    total = max(_round(subtotal, rules.get("rounding")), 0)
    dp_pct = _num(dp_percent) if dp_percent is not None else _num(rules.get("dp_percent"))
    dp_pct = max(0.0, min(100.0, dp_pct))
    dp_amount = _round(total * dp_pct / 100.0, rules.get("rounding")) if dp_pct else 0
    dp_amount = min(dp_amount, total)
    return {
        "breakdown": breakdown,
        "subtotal": subtotal,
        "surcharge_percent": int(pct),
        "discount": disc,
        "discount_label": discount_label if disc else "",
        "total": total,
        "dp_percent": int(dp_pct),
        "dp_amount": dp_amount,
        "days": days,
        "vehicle_type": vtype,
        "service": service,
        "day_rate": _int(day_rate) if flat_amount is None else 0,
    }

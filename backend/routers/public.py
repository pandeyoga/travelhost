"""routers/public.py — endpoint publik (TANPA auth) untuk website marketing + lead capture.

Prefix `/api/public`. Read-only katalog (fleet/destinations/articles/testimonials) +
trip-estimate (hitung server-side, tanpa tulis DB) + quotation (buat `leads` → muncul di CRM).
Koleksi yang dipakai kanonik (vehicles/destinations/articles/testimonials/leads/settings).
"""
from fastapi import APIRouter, Body, HTTPException, Query, Request, Response

import hashlib
import re
import secrets
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from schemas import (LeadAdsPayload, PublicBookingCreate, PublicChatCreate, QuotationCreate,
                     TripEstimateRequest)
from schemas_landing import LandingLeadCreate, LandingTrackEvent
from services import ads as ads_service
from services import attribution as attr
from services import content_publish as cp
from services import content_redirects as credirects
from services import content_stats as cstats
from services import i18n
from services.refs import destination_normalize, origin_normalize, vehicle_type_normalize
from services import landing_stats
from services import reviews as review_svc
from services.crm import auto_assign_agent, log_activity
from services.events import emit
from services.geo import parse_iso
from services.maps import fallback_eta, route_eta
from services.pricing import compute_quote, get_pricing_rules
from services.ratelimit import allow, client_ip

router = APIRouter(prefix="/api/public", tags=["public"])

STALE_SECONDS = 300


def _rate_guard(request: Request, bucket: str, limit: int, window: int):
    """Lindungi endpoint publik dari spam (sliding-window per IP)."""
    if not allow(f"{bucket}:{client_ip(request)}", limit, window):
        raise HTTPException(status_code=429, detail="Terlalu banyak permintaan. Mohon coba lagi sebentar lagi.")


def _fleet_public(v, *, rate=0, basis=""):
    return {
        "id": v.get("id"), "code": v.get("code"), "name": v.get("name"),
        "type": v.get("type"), "capacity": v.get("capacity"),
        "features": v.get("features", []), "photos": v.get("photos", []),
        "gallery": v.get("gallery", []), "tour_scenes": v.get("tour_scenes", []),
        "exterior_frames": v.get("exterior_frames", []), "rental_terms": v.get("rental_terms", []),
        "specs": v.get("specs", []), "highlights": v.get("highlights", []),
        "year": v.get("year"), "color": v.get("color"),
        # Harga yang TAMPIL = harga yang DIHITUNG mesin (tarif unit → tarif tipe → default).
        # Dulu di sini dipakai `vehicles.price_from` (angka pemasaran, 2 dari 5 unit kosong)
        # sementara tagihan memakai tarif tipe → pelanggan melihat angka yang tidak pernah
        # ditagihkan. Lihat services/pricing.resolve_day_rate + INV-PRICE-01.
        "price_from": int(rate or 0), "day_rate": int(rate or 0), "rate_basis": basis,
        "status": v.get("status"),
    }


@router.get("/fleet")
async def public_fleet(limit: int = Query(default=60, le=100)):
    """Katalog armada yang PANTAS dijual online.

    Dulu endpoint ini mengembalikan seluruh koleksi `vehicles` — termasuk unit MITRA
    (bukan milik sendiri), unit yang sedang di perawatan, dan sisa data uji. Sekarang
    memakai penyaring bersama `services/booking_search.publishable_filter()` yang SAMA
    dengan yang dipakai pencarian & pembuatan booking, sehingga katalog tidak mungkin
    memajang unit yang tak bisa dipesan.
    """
    from services import booking_search as bs
    from services.pricing import get_pricing_rules, resolve_day_rate
    db = get_db()
    docs = await db.vehicles.find(bs.publishable_filter(), {"_id": 0}).sort("code", 1).to_list(limit)
    rules = await get_pricing_rules(db)
    out = []
    for v in safe_doc(docs):
        rate, basis = resolve_day_rate(rules, vehicle=v)
        out.append(_fleet_public(v, rate=rate, basis=basis))
    return out


@router.get("/fleet/{vehicle_id}")
async def public_fleet_detail(vehicle_id: str):
    from services import booking_search as bs
    from services.pricing import get_pricing_rules, resolve_day_rate
    db = get_db()
    query = dict(bs.publishable_filter())
    query["id"] = vehicle_id
    v = await db.vehicles.find_one(query, {"_id": 0})
    if not v:
        raise HTTPException(status_code=404, detail="Armada tidak ditemukan")
    rate, basis = resolve_day_rate(await get_pricing_rules(db), vehicle=v)
    return _fleet_public(safe_doc(v), rate=rate, basis=basis)


@router.get("/destination-options")
async def public_destination_options():
    """INV-REF-02 batch 3: pilihan destinasi utk FORM publik (penawaran) — dari master.
    Tanpa auth; hanya nama (bukan data sensitif). Nonaktif-ops disembunyikan."""
    rows = await get_db().destinations.find(
        {"deleted": {"$ne": True}, "ops_active": {"$ne": False}},
        {"_id": 0, "name": 1, "slug": 1}).sort("name", 1).to_list(500)
    return [{"value": r.get("name"), "label": r.get("name"), "slug": r.get("slug")}
            for r in rows if r.get("name")]


@router.get("/destinations")
async def public_destinations(limit: int = Query(default=60, le=100),
                             lang: str = Query(default=i18n.DEFAULT_LANG)):
    """Katalog destinasi TAYANG (CMS-05) dalam bahasa yang diminta (CMS-06)."""
    docs = await get_db().destinations.find(
        cp.visibility_filter("destinations"), {"_id": 0}
    ).sort([("position", 1), ("name", 1)]).to_list(limit)
    return i18n.localize_many("destinations", safe_doc(docs), lang)


@router.get("/destinations/{slug}")
async def public_destination(slug: str, lang: str = Query(default=i18n.DEFAULT_LANG),
                            preview: str = Query(default="")):
    """Detail destinasi. Konten draft/terjadwal hanya terbuka dengan token pratinjau sah."""
    db = get_db()
    d = await db.destinations.find_one({"slug": slug}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Destinasi tidak ditemukan")
    is_preview = False
    if not cp.is_visible("destinations", d):
        is_preview = await cp.resolve_preview(db, preview, "destinations", d.get("id"), slug)
        if not is_preview:
            raise HTTPException(status_code=404, detail="Destinasi tidak ditemukan")
    out = i18n.localize("destinations", safe_doc(d), lang)
    out["preview"] = bool(is_preview)
    out["status"] = cp.derive_status("destinations", d)
    return out


@router.get("/articles")
async def public_articles(limit: int = Query(default=60, le=100),
                          lang: str = Query(default=i18n.DEFAULT_LANG)):
    """Daftar artikel TAYANG — termasuk yang terjadwal & waktunya sudah lewat (CMS-05)."""
    docs = await get_db().articles.find(
        cp.visibility_filter("articles"), {"_id": 0}
    ).sort([("position", 1), ("published_at", -1)]).to_list(limit)
    return i18n.localize_many("articles", safe_doc(docs), lang)


@router.get("/articles/{slug}")
async def public_article(slug: str, lang: str = Query(default=i18n.DEFAULT_LANG),
                        preview: str = Query(default="")):
    """Detail artikel.

    BUG DITUTUP (CMS-05): dulu endpoint ini TIDAK memeriksa `published`, jadi artikel draft
    bocor ke publik lewat URL langsung (dan bisa terindeks mesin pencari). Sekarang draft
    HANYA terbuka lewat token pratinjau milik editor.
    """
    db = get_db()
    a = await db.articles.find_one({"slug": slug}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Artikel tidak ditemukan")
    is_preview = False
    if not cp.is_visible("articles", a):
        is_preview = await cp.resolve_preview(db, preview, "articles", a.get("id"), slug)
        if not is_preview:
            raise HTTPException(status_code=404, detail="Artikel tidak ditemukan")
    out = i18n.localize("articles", safe_doc(a), lang)
    out["preview"] = bool(is_preview)
    out["status"] = cp.derive_status("articles", a)
    return out


@router.get("/testimonials")
async def public_testimonials(limit: int = Query(default=60, le=100)):
    # G9: hanya tampilkan testimoni yg sudah di-approve (moderasi manual di CMS).
    # Kompat data lama: jika field `approved` belum ada, anggap disetujui (agar tak kosong tiba-tiba).
    q = {"$or": [{"approved": True}, {"approved": {"$exists": False}}]}
    docs = await get_db().testimonials.find(q, {"_id": 0}).sort([("position", 1), ("created_at", -1)]).to_list(limit)
    return safe_doc(docs)


@router.get("/testimonials/summary")
async def public_testimonials_summary():
    """CMS-07: rata-rata rating dari ulasan TAYANG (dipakai AggregateRating & bukti sosial)."""
    return await review_svc.summary(get_db())


@router.get("/packages")
async def public_packages(limit: int = Query(default=60, le=100),
                          lang: str = Query(default=i18n.DEFAULT_LANG)):
    docs = await get_db().packages.find(
        cp.visibility_filter("packages"), {"_id": 0}
    ).sort([("position", 1), ("name", 1)]).to_list(limit)
    return i18n.localize_many("packages", safe_doc(docs), lang)


@router.get("/packages/{slug}")
async def public_package(slug: str, lang: str = Query(default=i18n.DEFAULT_LANG),
                        preview: str = Query(default="")):
    """Detail paket wisata — halaman publik `/packages/{slug}` (A1: dulu tak ada sama sekali)."""
    db = get_db()
    p = await db.packages.find_one({"slug": slug}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Paket tidak ditemukan")
    is_preview = False
    if not cp.is_visible("packages", p):
        is_preview = await cp.resolve_preview(db, preview, "packages", p.get("id"), slug)
        if not is_preview:
            raise HTTPException(status_code=404, detail="Paket tidak ditemukan")
    out = i18n.localize("packages", safe_doc(p), lang)
    out["preview"] = bool(is_preview)
    out["status"] = cp.derive_status("packages", p)
    # Destinasi terkait (bila diisi) supaya halaman paket punya kedalaman & tautan internal.
    if p.get("destination_id"):
        dest = await db.destinations.find_one({"id": p["destination_id"]},
                                             {"_id": 0, "slug": 1, "name": 1, "hero_image": 1})
        out["destination_ref"] = i18n.localize("destinations", safe_doc(dest), lang) if dest else None
    return out


@router.get("/promos")
async def public_promos(limit: int = Query(default=30, le=100),
                       lang: str = Query(default=i18n.DEFAULT_LANG)):
    """Promo aktif + SYARAT yang dibaca dari data (A3: dipakai halaman publik `/promo`).

    Syarat ditampilkan dari field yang benar-benar ditegakkan server saat checkout
    (`services/promos.validate`) — bukan dari teks deskripsi. Jadi yang dibaca pelanggan
    persis sama dengan yang dijalankan komputer.
    """
    from services import promos as promo_svc
    # G2: sembunyikan promo yg sudah kadaluarsa (`valid_until < today`).
    # Promo tanpa valid_until dianggap berlaku selamanya.
    today = datetime.utcnow().date().isoformat()
    q = {"active": True, "$or": [
        {"valid_until": {"$gte": today}}, {"valid_until": {"$in": [None, ""]}}, {"valid_until": {"$exists": False}},
    ]}
    docs = await get_db().promos.find(q, {"_id": 0}).sort([("position", 1), ("created_at", -1)]).to_list(limit)
    rows = i18n.localize_many("promos", safe_doc(docs), lang)
    out = []
    for row in rows:
        quota = int(row.get("max_uses") or 0)
        used = int(row.get("used_count") or 0)
        row["terms"] = promo_svc.terms_text(row)
        row["quota_left"] = max(0, quota - used) if quota else None
        row["sold_out"] = bool(quota and used >= quota)
        # Jangan bocorkan internal (id dokumen, hitungan pemakaian mentah, kantong terjemahan).
        for hidden in ("id", "used_count", "translations", "created_at", "updated_at"):
            row.pop(hidden, None)
        out.append(row)
    return out


@router.get("/company")
async def public_company():
    s = await get_db().settings.find_one({"key": "company_info"}, {"_id": 0})
    return safe_doc(s.get("value")) if s and s.get("value") else {}


@router.get("/theme")
async def public_theme():
    """Konfigurasi tema aktif situs publik (preset + mode), dikontrol dari CMS/Pengaturan."""
    s = await get_db().settings.find_one({"key": "theme_config"}, {"_id": 0})
    cfg = (s.get("value") if s and isinstance(s.get("value"), dict) else None) or {}
    preset = cfg.get("preset") if cfg.get("preset") in {"azure", "midnight", "sunrise", "harbor"} else "azure"
    mode = cfg.get("mode") if cfg.get("mode") in {"light", "dark"} else "light"
    return {"preset": preset, "mode": mode}


@router.get("/stats")
async def public_stats():
    """Angka ringkas untuk counter di Home — bersumber data NYATA (armada/destinasi/rating)."""
    db = get_db()
    fleet_n = await db.vehicles.count_documents({})
    dest_n = await db.destinations.count_documents({})
    testi = await db.testimonials.find({}, {"_id": 0, "rating": 1}).to_list(500)
    ratings = [t.get("rating") for t in testi if isinstance(t.get("rating"), (int, float))]
    avg = round(sum(ratings) / len(ratings), 1) if ratings else 4.9
    return {
        "stats": [
            {"key": "fleet", "label": "Unit Armada Siap Jalan", "value": fleet_n, "suffix": "", "decimals": 0},
            {"key": "destinations", "label": "Destinasi Jawa–Bali", "value": dest_n, "suffix": "", "decimals": 0},
            {"key": "rating", "label": "Rating Kepuasan Tamu", "value": avg, "suffix": "/5", "decimals": 1},
            {"key": "service", "label": "Pendampingan Perjalanan", "value": 24, "suffix": "/7", "decimals": 0},
        ]
    }


@router.post("/quotation")
async def public_quotation(body: QuotationCreate, request: Request):
    """Form penawaran publik → buat lead (source=website, stage=new) → tampil di CRM.
    Auto-assignment round-robin (least-loaded) + catat aktivitas 'created'.
    A3: rate-limit per IP + honeypot anti-spam (silent drop)."""
    _rate_guard(request, "quotation", 8, 60)
    db = get_db()
    if (body.hp or "").strip():  # bot terdeteksi → diam-diam tolak (tak tulis DB)
        return {"id": new_id("led"), "status": "received",
                "message": "Permintaan penawaran diterima. Tim kami akan menghubungi Anda segera."}
    assigned = await auto_assign_agent(db)
    built = attr.build_attribution(body.attribution, fallback_source="website")
    consent = bool(body.marketing_consent)
    doc = {
        "id": new_id("led"), "customer_name": body.name.strip(),
        "phone": body.phone or "", "email": body.email or "",
        "source": "website", "stage": "new", "assigned_to": assigned,
        "destination": await destination_normalize(db, body.destination), "trip_date": body.trip_date,
        "pax": int(body.pax or 0), "message": body.message or "",
        "value": 0.0, "quotation_amount": 0, "converted_customer_id": None,
        "marketing_consent": consent, "consent_at": now_iso() if consent else None,
        "created_at": now_iso(), "last_activity_at": now_iso(),
        **built,
    }
    # CMS-08: jejak KONTEN terakhir yang dibaca sebelum mengisi form (artikel/destinasi/paket).
    # Tanpa ini tak ada cara mengetahui konten mana yang benar-benar menghasilkan lead.
    content_ref = attr.content_ref(body.attribution)
    if content_ref:
        doc["content_ref"] = content_ref
    await db.leads.insert_one(doc)
    await log_activity(db, doc["id"], None, "created",
                       text=f"Lead masuk dari website (form penawaran) · channel {attr.channel_label(built['channel'])}")
    await emit(db, "lead.created", {
        "lead_id": doc["id"], "customer_name": doc["customer_name"], "phone": doc["phone"],
        "destination": doc["destination"], "source": "website", "channel": built["channel"],
        "assigned_to": assigned,
    }, source="public", ref_type="lead", ref_id=doc["id"], dedupe_key=f"lead.created:{doc['id']}")
    return {"id": doc["id"], "status": "received",
            "message": "Permintaan penawaran diterima. Tim kami akan menghubungi Anda segera."}


@router.post("/booking")
async def public_booking_request(body: PublicBookingCreate, request: Request):
    """PERMINTAAN booking tanpa unit (paket wisata / lepas kunci / kebutuhan khusus).

    Sejak alur pemesanan online hadir (`/api/public/booking/submit`), endpoint ini TIDAK
    lagi menulis booking sendiri: ia memanggil `services.booking_public.create_booking`
    dengan `service='request_only'` supaya HANYA ADA SATU jalur pembuatan booking dari
    publik (pelajaran dari penyatuan Media Library: dua jalur = dua perilaku = bug senyap).
    Hasilnya tetap `pending` tanpa armada — harga & unit ditetapkan ops saat menyetujui.
    Rate-limit per IP + honeypot anti-spam tetap berlaku.
    """
    _rate_guard(request, "public-booking", 6, 60)
    if (body.hp or "").strip():  # bot → silent drop (tak tulis DB)
        return {"status": "received", "message": "Permintaan pesanan diterima. Tim kami akan mengonfirmasi."}
    from services import booking_public as bp
    from services.ratelimit import client_ip as _ip
    payload = {
        "service": "request_only", "name": body.name, "phone": body.phone, "email": body.email,
        "origin": body.origin, "destination": body.destination,
        "start_datetime": body.start_datetime, "end_datetime": body.end_datetime,
        "pax": body.pax, "vehicle_type": body.vehicle_type, "message": body.message,
        "attribution": body.attribution, "marketing_consent": body.marketing_consent,
    }
    try:
        res = await bp.create_booking(get_db(), payload, ip=_ip(request))
    except bp.BookingPublicError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {"id": res["id"], "code": res["code"], "status": "received", "token": res.get("token", ""),
            "message": "Permintaan pesanan diterima. Tim kami akan mengonfirmasi ketersediaan & harga via WhatsApp."}


@router.post("/lead-ads/{provider}")
async def public_lead_ads(provider: str, body: LeadAdsPayload, request: Request):
    """Webhook Lead Ads (Meta/Google/TikTok) — MOCK-FIRST. Terima payload → buat lead ber-atribusi.

    Channel dipaksa `{provider}_ads`; auto-assign agent + emit lead.created (memicu otomasi E1/E2).
    """
    _rate_guard(request, "lead-ads", 60, 60)
    if provider.lower() not in ads_service.PROVIDERS:
        raise HTTPException(status_code=400, detail="Provider tidak didukung (meta|google|tiktok)")
    payload = body.model_dump()
    res = await ads_service.create_ad_lead(get_db(), provider.lower(), payload)
    return res


# Tarif estimator publik kini dari Pricing Engine (settings.pricing_rules), BUKAN hardcode.
# Lihat services/pricing.py (B1) — angka identik dengan ERP & dapat diedit di Pengaturan.


@router.post("/trip-estimate")
async def public_trip_estimate(body: TripEstimateRequest, request: Request):
    """Estimasi harga indikatif untuk kalkulator publik.

    `distance_km` masih diterima (klien lama), tetapi TIDAK dipakai: harga digerakkan
    JUMLAH HARI + tarif armada + surcharge tanggal. Lihat services/pricing.py.
    """
    _rate_guard(request, "trip-estimate", 30, 60)
    db = get_db()
    rules = await get_pricing_rules(db)
    holidays = []
    if body.trip_date:
        op = await db.settings.find_one({"key": "operational"}, {"_id": 0})
        if op and isinstance(op.get("value"), dict):
            holidays = op["value"].get("holidays", []) or []
    from services.pricing import get_dp_percent
    q = compute_quote(
        rules,
        vehicle_type=body.vehicle_type or "hiace_premio",
        days=body.days,
        when=body.trip_date,
        holidays=holidays,
        include_travel=True,
        dp_percent=await get_dp_percent(db),
    )
    return {
        "breakdown": q["breakdown"], "total": q["total"], "days": q["days"],
        "vehicle_type": q["vehicle_type"], "dp_amount": q["dp_amount"], "dp_percent": q["dp_percent"],
        "note": "Estimasi indikatif. Harga final menyesuaikan rute, musim, dan ketersediaan armada.",
    }


@router.get("/track/{token}")
async def public_track(token: str):
    """Tracking publik korporat via share-link (TANPA auth). Validasi token + expiry + revoke.

    Mengembalikan posisi terkini, ETA, dan jejak (polyline) untuk peta read-only.
    """
    db = get_db()
    share = await db.trip_shares.find_one({"token": token}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Tautan pelacakan tidak ditemukan")
    if share.get("revoked"):
        raise HTTPException(status_code=403, detail="Tautan pelacakan telah dinonaktifkan")
    exp = parse_iso(share.get("expires_at"))
    if exp and exp <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Tautan pelacakan telah kedaluwarsa")
    trip = await db.trips.find_one({"id": share.get("trip_id")}, {"_id": 0})
    if not trip:
        raise HTTPException(status_code=404, detail="Perjalanan tidak ditemukan")

    await db.trip_shares.update_one(
        {"id": share["id"]},
        {"$set": {"last_accessed_at": now_iso()}, "$inc": {"access_count": 1}},
    )

    pts = await db.locations.find({"trip_id": trip["id"]}, {"_id": 0}).sort("timestamp", 1).to_list(2000)
    cur = pts[-1] if pts else None
    veh = None
    if trip.get("vehicle_id"):
        veh = await db.vehicles.find_one({"id": trip["vehicle_id"]}, {"_id": 0})

    eta = None
    if cur and trip.get("dest_lat") is not None and trip.get("dest_lng") is not None:
        res = await route_eta(cur["lat"], cur["lng"], trip["dest_lat"], trip["dest_lng"])
        if res is None:
            res = fallback_eta(cur["lat"], cur["lng"], trip["dest_lat"], trip["dest_lng"])
        eta = {"eta_minutes": res["eta_minutes"], "distance_km": res["distance_km"],
               "approx": res.get("approx", False)}

    stale = True
    if cur:
        ts = parse_iso(cur.get("timestamp"))
        stale = (datetime.now(timezone.utc) - ts).total_seconds() > STALE_SECONDS if ts else True

    return {
        "label": share.get("label"),
        "vehicle_name": (veh.get("name") if veh else share.get("vehicle_name")),
        "plate_number": veh.get("plate_number") if veh else None,
        "status": trip.get("status"),
        "dest_name": trip.get("dest_name"),
        "destination": ({"lat": trip.get("dest_lat"), "lng": trip.get("dest_lng")}
                        if trip.get("dest_lat") is not None else None),
        "current": ({"lat": cur["lat"], "lng": cur["lng"], "speed": cur.get("speed"),
                     "timestamp": cur.get("timestamp")} if cur else None),
        "stale": stale,
        "eta": eta,
        "track": [{"lat": p["lat"], "lng": p["lng"]} for p in pts],
        "expires_at": share.get("expires_at"),
    }


@router.post("/chat")
async def public_chat(body: PublicChatCreate, request: Request):
    """Web-chat publik (tanpa login). Buat/lanjut percakapan kanal 'web' → masuk Inbox agen.
    A3: rate-limit per IP + honeypot anti-spam (silent drop)."""
    _rate_guard(request, "chat", 20, 60)
    db = get_db()
    if (body.hp or "").strip():  # bot terdeteksi → balas token throwaway tanpa tulis DB
        return {"token": secrets.token_urlsafe(18), "status": "received"}
    conv = None
    if body.token:
        conv = await db.conversations.find_one({"chat_token": body.token}, {"_id": 0})
    if not conv:
        conv = {
            "id": new_id("cnv"), "channel": "web",
            "contact_name": (body.name or "").strip() or "Pengunjung Web",
            "contact_phone": body.phone or "", "subject": "Chat dari website",
            "customer_id": None, "lead_id": None, "status": "open", "assigned_to": None,
            "labels": ["web"], "unread": 0, "chat_token": secrets.token_urlsafe(18),
            "last_message_at": now_iso(), "last_message_preview": "", "snooze_until": None,
            "created_at": now_iso(),
        }
        await db.conversations.insert_one(conv)
    body_text = body.message.strip()
    msg = {
        "id": new_id("msg"), "conversation_id": conv["id"], "sender": "customer",
        "author_id": None, "body": body_text, "internal": False,
        "status": "delivered", "created_at": now_iso(),
    }
    await db.messages.insert_one(msg)
    await db.conversations.update_one({"id": conv["id"]}, {
        "$set": {"last_message_at": msg["created_at"], "last_message_preview": body_text[:120]},
        "$inc": {"unread": 1}})
    return {"token": conv["chat_token"], "status": "received"}


@router.get("/chat/{token}")
async def public_chat_thread(token: str):
    """Thread chat untuk pengunjung (polling). Sembunyikan catatan internal agen."""
    db = get_db()
    conv = await db.conversations.find_one({"chat_token": token}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Percakapan tidak ditemukan")
    msgs = await db.messages.find(
        {"conversation_id": conv["id"], "internal": {"$ne": True}}, {"_id": 0}
    ).sort("created_at", 1).to_list(2000)
    return {
        "token": token, "status": conv.get("status"),
        "messages": [{"sender": m.get("sender"), "body": m.get("body"),
                      "created_at": m.get("created_at")} for m in msgs],
    }

# ----------------------------------------------------------------- Landing page iklan (F8)
def _visitor_seed(request: Request, vid: str = "") -> str:
    """Benih pemilihan varian A/B. Pakai id pengunjung dari localStorage bila ada; kalau tidak,
    IP+user-agent. Tujuannya: pengunjung yang me-refresh halaman harus melihat versi yang SAMA,
    kalau tidak angka tampilan-vs-lead per varian jadi tidak bisa dipercaya."""
    if (vid or "").strip():
        return (vid or "").strip()[:64]
    return f"{client_ip(request)}|{(request.headers.get('user-agent') or '')[:120]}"


async def _landing_media_map(db, blocks):
    from services import landing_blocks as lb
    ids = lb.media_ids(blocks)
    if not ids:
        return {}
    rows = await db.media_assets.find({"id": {"$in": ids}, "deleted": {"$ne": True}},
                                      {"_id": 0}).to_list(len(ids))
    return {r["id"]: {**r, "url": f"/api/public/media/{r['id']}"} for r in rows}


def _lead_form_props(page: dict) -> dict:
    for b in page.get("blocks") or []:
        if b.get("type") == "lead_form" and not b.get("hidden"):
            return b.get("props") or {}
    return {}


@router.get("/landing/{slug}")
async def public_landing(slug: str, request: Request, vid: str = Query(default=""),
                         variant: str = Query(default="")):
    """Render halaman iklan yang SUDAH diterbitkan. Draft -> 404 (jangan bocorkan draf).

    `variant` memaksa versi tertentu (untuk pratinjau tim marketing); tanpa itu varian dipilih
    deterministik dari `vid`.
    """
    from services import landing_blocks as lb
    db = get_db()
    doc = await db.landing_pages.find_one({"slug": slug, "status": "published"}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Halaman tidak ditemukan")
    ab = lb.sanitize_ab(doc.get("ab") or {})
    forced = (variant or "").strip().upper()[:4]
    chosen = next((v for v in ab.get("variants") or [] if v.get("id") == forced), None) if forced else None
    if not chosen:
        chosen = lb.pick_variant(ab, seed=_visitor_seed(request, vid))
    payload = lb.public_payload(doc, await _landing_media_map(db, doc.get("blocks")), variant=chosen)
    payload["page_id"] = doc.get("id")
    return payload


@router.post("/landing/{slug}/track")
async def public_landing_track(slug: str, body: LandingTrackEvent, request: Request):
    """Catat tampilan / klik CTA halaman iklan (agregat harian per varian, tanpa PII)."""
    _rate_guard(request, "landing-track", 90, 60)
    db = get_db()
    page = await db.landing_pages.find_one({"slug": slug, "status": "published"}, {"_id": 0, "id": 1})
    if not page:
        raise HTTPException(status_code=404, detail="Halaman tidak ditemukan")
    metric = {"view": "views", "cta_click": "cta_clicks"}.get((body.type or "").strip().lower())
    if not metric:
        raise HTTPException(status_code=400, detail="Jenis peristiwa tidak dikenal (view|cta_click)")
    await landing_stats.bump(db, page["id"], (body.variant_id or "A"), metric)
    return {"ok": True, "metric": metric}


@router.post("/landing/{slug}/lead")
async def public_landing_lead(slug: str, body: LandingLeadCreate, request: Request):
    """Form lead DI HALAMAN IKLAN → lead CRM ber-atribusi + event `lead.created` (memicu outbox
    konversi Meta/Google lewat satu pintu `services.events.emit`).

    Idempoten per (halaman + nomor + hari): pengunjung yang menekan "Kirim" dua kali atau
    jaringan yang mengulang permintaan TIDAK membuat lead ganda — tim sales tidak boleh
    menelepon orang yang sama dua kali karena bug klik ganda. Balapan ditutup unique index
    `lp_dedupe_key` (bukan hanya cek-lalu-tulis).

    Batas laju dibuat 30/menit per IP (lebih longgar dari form web biasa) DENGAN SENGAJA:
    pengunjung seluler Indonesia berbagi satu IP publik lewat CGNAT operator, sehingga ambang
    ketat akan menolak lead SAH dari orang berbeda — itu berarti uang iklan hangus. Pengaman
    utama anti-spam di sini bukan IP, melainkan honeypot + dedup per nomor + persetujuan.
    """
    _rate_guard(request, "landing-lead", 30, 60)
    db = get_db()
    page = await db.landing_pages.find_one({"slug": slug, "status": "published"}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404,
                            detail="Halaman iklan tidak ditemukan atau belum diterbitkan")
    form = _lead_form_props(page)
    success_text = form.get("success_text") or "Terima kasih! Tim kami segera menghubungi Anda."
    if (body.hp or "").strip():  # bot terdeteksi → diam-diam tolak (tak tulis DB)
        return {"id": new_id("led"), "status": "received", "message": success_text, "duplicate": False}

    name = (body.name or "").strip()[:120]
    phone = re.sub(r"[^0-9+]", "", body.phone or "")[:24]
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Nama wajib diisi (minimal 2 huruf).")
    if len(re.sub(r"\D", "", phone)) < 8:
        raise HTTPException(status_code=400, detail="Nomor WhatsApp tidak valid (minimal 8 angka).")
    consent = bool(body.marketing_consent)
    if form.get("require_consent", True) and not consent:
        raise HTTPException(status_code=400,
                            detail="Mohon centang persetujuan agar kami boleh menghubungi Anda.")

    raw_attr = dict(body.attribution or {})
    raw_attr.setdefault("landing_page", f"/lp/{slug}")
    click_ids = {k: str(v)[:200] for k, v in (body.click_ids or {}).items()
                 if k in ("gclid", "fbclid", "ttclid", "ctwa_clid", "wbraid", "gbraid") and v}
    for key in ("gclid", "fbclid", "ttclid"):
        if click_ids.get(key) and not raw_attr.get(key):
            raw_attr[key] = click_ids[key]
    built = attr.build_attribution(raw_attr, fallback_source="website")

    variant_id = (body.variant_id or "A").strip().upper()[:4] or "A"
    dedupe_seed = f"{page['id']}|{phone}|{now_iso()[:10]}|{(body.idempotency_key or '').strip()[:64]}"
    dedupe_key = hashlib.sha256(dedupe_seed.encode("utf-8")).hexdigest()[:32]

    existing = await db.leads.find_one({"lp_dedupe_key": dedupe_key}, {"_id": 0, "id": 1})
    if existing:
        return {"id": existing["id"], "status": "received", "message": success_text, "duplicate": True}

    assigned = await auto_assign_agent(db)
    doc = {
        "id": new_id("led"), "customer_name": name, "phone": phone, "email": (body.email or "")[:160],
        "source": "landing_page", "stage": "new", "assigned_to": assigned,
        "origin": await origin_normalize(db, (body.origin or "")[:200]),
        "destination": await destination_normalize(db, (body.destination or "")[:200]),
        "trip_date": (body.start or None), "trip_end_date": (body.end or None),
        "pax": int(body.pax or 0), "vehicle_type": vehicle_type_normalize((body.vehicle_type or "")[:60]),
        "message": (body.message or "")[:1000],
        "value": 0.0, "quotation_amount": 0, "converted_customer_id": None,
        "marketing_consent": consent, "consent_at": now_iso() if consent else None,
        "landing_page_id": page["id"], "landing_slug": slug, "landing_variant": variant_id,
        "landing_block_id": (body.block_id or "")[:40], "click_ids": click_ids,
        "lp_dedupe_key": dedupe_key,
        "created_at": now_iso(), "last_activity_at": now_iso(),
        **built,
    }
    try:
        await db.leads.insert_one(dict(doc))
    except DuplicateKeyError:  # balapan submit ganda → kembalikan lead yang sudah ada
        again = await db.leads.find_one({"lp_dedupe_key": dedupe_key}, {"_id": 0, "id": 1})
        return {"id": (again or {}).get("id") or doc["id"], "status": "received",
                "message": success_text, "duplicate": True}

    await landing_stats.bump(db, page["id"], variant_id, "leads")
    await log_activity(db, doc["id"], None, "created",
                       text=f"Lead masuk dari halaman iklan /lp/{slug} (versi {variant_id}) · "
                            f"channel {attr.channel_label(built['channel'])}")
    await emit(db, "lead.created", {
        "lead_id": doc["id"], "customer_name": doc["customer_name"], "phone": doc["phone"],
        "destination": doc["destination"], "source": "landing_page", "channel": built["channel"],
        "assigned_to": assigned, "landing_slug": slug, "landing_variant": variant_id,
    }, source="landing_page", ref_type="lead", ref_id=doc["id"],
        dedupe_key=f"lead.created:{doc['id']}")
    return {"id": doc["id"], "status": "received", "message": success_text, "duplicate": False}


@router.get("/media/{media_id}")
async def public_media(media_id: str, request: Request, thumb: int = Query(default=0),
                       v: str = Query(default="")):
    """Sajikan aset media halaman iklan & konten website (publik & read-only).

    `thumb=1` mengembalikan versi kecil (grid Media Library & kartu galeri) supaya halaman
    iklan tidak menarik gambar 3 MB hanya untuk kotak 120px.

    **Cache sadar-versi (Media Manager v2).** Dulu header selalu `max-age=86400`, jadi setelah
    fitur "Ganti berkas" dipakai, pengunjung & admin tetap melihat foto LAMA sampai sehari penuh —
    keluhan "sudah saya ganti kok tidak berubah" yang mustahil didiagnosis. Sekarang:
      * URL yang menyertakan `?v=<versi terkini>` = konten kekal → boleh di-cache 1 tahun;
      * URL tanpa versi (mis. URL yang sudah lama tersimpan di dokumen CMS) hanya di-cache singkat
        dan divalidasi ulang lewat **ETag**, sehingga penggantian berkas langsung terlihat tanpa
        mengorbankan kecepatan (304 Not Modified = nyaris tanpa biaya transfer).
    """
    from services import media_store as ms
    doc = await get_db().media_assets.find_one({"id": media_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Media tidak ditemukan")
    version = int(doc.get("version") or 1)
    want_thumb = bool(thumb and doc.get("thumb_path"))
    etag = f'W/"{media_id}-{version}-{"t" if want_thumb else "o"}"'
    if (request.headers.get("if-none-match") or "").strip() == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "public, max-age=60"})
    path = (doc.get("thumb_path") if want_thumb else doc.get("storage_path")) or ""
    try:
        data, ctype = ms.fetch(path, backend=doc.get("storage_backend") or "")
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="Media tidak tersedia") from None
    fresh = str(v or "").strip() == str(version)
    cache = "public, max-age=31536000, immutable" if fresh else "public, max-age=60, must-revalidate"
    return Response(content=data, media_type=ctype or doc.get("content_type") or "application/octet-stream",
                    headers={"Cache-Control": cache, "ETag": etag})


# ── CMS-12: pengalihan URL saat slug konten berubah (anti 404 & anti kehilangan SEO) ──
@router.get("/redirect")
async def public_redirect(path: str = Query(default=""), request: Request = None):
    """Cari tujuan pengalihan untuk satu path publik.

    Dipakai halaman detail di frontend: bila slug tidak ditemukan (404), halaman menanyakan
    path-nya ke sini lalu pindah ke URL baru — jadi tautan lama dari Google, WhatsApp, atau
    blog pihak lain tidak menjadi jalan buntu. Jawaban memuat `status: 301` sebagai niat
    semantiknya (SPA tidak bisa mengirim 301 sungguhan; lihat catatan di
    `services/content_redirects.py`).
    """
    _rate_guard(request, "redirect", 120, 60)
    hit = await credirects.resolve(get_db(), path)
    if not hit:
        raise HTTPException(status_code=404, detail="Tidak ada pengalihan untuk URL ini")
    return hit


# ── CMS-08: penghitung tampilan konten (tanpa PII, anti-inflasi) ─────────────
@router.post("/content-view")
async def public_content_view(body: dict = Body(default={}), request: Request = None):
    """Catat SATU tampilan konten (artikel/destinasi/paket).

    - Tidak menyimpan IP/identitas: alamat hanya jadi kunci hitung di memori supaya satu
      pengunjung tidak menggelembungkan angka (1 hitungan / 30 menit / konten).
    - Rate-limit per IP agar endpoint publik tak bisa dipakai membanjiri database.
    """
    _rate_guard(request, "content-view", 120, 60)
    kind = cstats.normalize_kind(body.get("kind"))
    slug = str(body.get("slug") or "").strip()
    if not kind or not slug:
        raise HTTPException(status_code=400, detail="Jenis & slug konten wajib diisi")
    ip = client_ip(request) if request else ""
    dedupe = hashlib.sha256(f"{ip}".encode()).hexdigest()[:16] if ip else ""
    out = await cstats.record_view(get_db(), kind, slug,
                                   title=str(body.get("title") or "")[:200], dedupe_key=dedupe)
    return {"ok": True, **out}


# ── CMS-07: funnel ulasan pelanggan (token) → testimoni (moderasi) ───────────
@router.get("/reviews/{token}")
async def public_review_context(token: str, request: Request):
    """Konteks halaman ulasan: nama pelanggan + kode pesanan (tanpa data sensitif lain)."""
    _rate_guard(request, "review-context", 30, 60)
    try:
        return await review_svc.get_context(get_db(), token)
    except review_svc.ReviewError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.post("/reviews/{token}")
async def public_review_submit(token: str, body: dict = Body(...), request: Request = None):
    """Kirim ulasan (rating 1–5 + kutipan) → masuk antrean moderasi CMS, belum tayang."""
    _rate_guard(request, "review-submit", 10, 300)
    try:
        doc = await review_svc.submit(
            get_db(), token,
            rating=body.get("rating"), quote=body.get("quote") or "",
            name=body.get("name") or "", role=body.get("role") or "",
            consent=bool(body.get("consent", True)))
    except review_svc.ReviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {"status": "received", "moderation": "pending", "rating": doc.get("rating"),
            "message": "Terima kasih! Ulasan Anda kami tinjau sebelum tayang di situs."}

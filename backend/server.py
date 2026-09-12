"""server.py — app factory + registrasi router (thin).
Semua endpoint berprefiks /api. CORS dari env. Bind 0.0.0.0:8001 (supervisor).
"""
import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI
from starlette.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).parent / ".env")

from db import close, get_db  # noqa: E402
from routers import (  # noqa: E402
    addons,
    driver_fees,
    ads,
    ads_manage,
    analytics,
    marketing,
    audit_logs,
    auth,
    automation,
    bookings,
    booking_admin,
    booking_public,
    pickup_points,
    transfer_routes,
    broadcasts,
    campaigns,
    content,
    customers,
    dashboard,
    departures,
    dispatch,
    documents,
    driver,
    drivers,
    expenses,
    finance,
    gps,
    growth,
    invoices,
    landing,
    leads,
    media,
    locations,
    maintenance,
    notifications,
    inbox,
    onboarding,
    payments,
    pricing,
    public,
    quotations,
    reports,
    reviews,
    seo,
    settings,
    site_pages,
    shares,
    trips,
    users,
    vehicles,
    whatsapp,
    workshops,
    service_types,
    payroll,
    partners,
    subcharters,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("travel_fleet")

app = FastAPI(title="Travel & Fleet Management Ecosystem")

# Health root (infra) — dikecualikan dari cek orphan endpoint.
infra_router = APIRouter(prefix="/api", tags=["infra"])


@infra_router.get("/")
async def root():
    return {"status": "ok", "service": "travel-fleet", "phase": "2"}


app.include_router(infra_router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(dashboard.router)
app.include_router(vehicles.router)
app.include_router(drivers.router)
app.include_router(customers.router)
# PENTING (urutan rute): booking_admin WAJIB didaftarkan SEBELUM bookings, karena bookings
# punya `/bookings/{booking_id}` yang akan menelan literal `/bookings/payment-proofs`
# (FastAPI memakai kecocokan PERTAMA) sehingga antrean bukti bayar balas 404 — ditemukan POC.
app.include_router(booking_admin.router)    # verifikasi bukti DP + ACC permintaan web (ops)
app.include_router(bookings.router)
app.include_router(pickup_points.router)    # master titik jemput (INV-REF-02 batch 2)
app.include_router(booking_public.router)   # pemesanan online publik (cari > pesan > bayar DP)
app.include_router(transfer_routes.router)  # rute antar-jemput bandara + tarif flat
app.include_router(departures.router)  # lapisan risiko kalender keberangkatan
app.include_router(marketing.router)  # FASE F: integrasi API iklan + pelacakan + kesehatan konversi
app.include_router(ads.router)         # FASE F4: dashboard iklan + sinkron metrik platform
app.include_router(ads_manage.router)  # FASE F5-F7: Lead Ads, audiens, campaign builder
app.include_router(landing.router)      # FASE F8: Landing Page Builder (armada & destinasi)
app.include_router(media.router)        # Media Manager v2: satu library media (CMS + halaman iklan)
app.include_router(payments.router)
app.include_router(expenses.router)
app.include_router(invoices.router)
app.include_router(documents.router)  # konfigurasi dokumen (tampilan/naskah/penomoran/rekening) — gaya SIPRO
app.include_router(finance.router)
app.include_router(reports.router)
app.include_router(leads.router)
app.include_router(broadcasts.router)
app.include_router(locations.router)
app.include_router(gps.router)
app.include_router(trips.router)
app.include_router(driver.router)
app.include_router(dispatch.router)
app.include_router(analytics.router)
app.include_router(maintenance.router)
app.include_router(workshops.router)
app.include_router(service_types.router)
app.include_router(payroll.router)
app.include_router(addons.router)
app.include_router(driver_fees.router)
app.include_router(partners.router)
app.include_router(subcharters.router)
app.include_router(shares.router)
app.include_router(notifications.router)
app.include_router(inbox.router)
app.include_router(settings.router)
app.include_router(site_pages.router)  # Page builder halaman situs + Pengaturan Situs (CMS)
app.include_router(pricing.router)
app.include_router(quotations.router)
app.include_router(content.router)
app.include_router(reviews.router)  # CMS-07: funnel ulasan pelanggan → testimoni (moderasi)
app.include_router(audit_logs.router)
app.include_router(onboarding.router)
app.include_router(automation.router)
app.include_router(whatsapp.router)
app.include_router(growth.router)
app.include_router(campaigns.router)
app.include_router(public.router)
app.include_router(seo.router)  # CMS-02 SEO Toolkit: /api/sitemap.xml + /api/robots.txt

# E3: POD (Proof of Delivery) lokal — sajikan file unggahan via /api/uploads (mount sebelum CORS).
from pathlib import Path as _Path  # noqa: E402
from starlette.staticfiles import StaticFiles  # noqa: E402
_UPLOAD_DIR = _Path(os.environ.get("UPLOAD_DIR", str(_Path(__file__).parent / "uploads")))
(_UPLOAD_DIR / "pod").mkdir(parents=True, exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=str(_UPLOAD_DIR)), name="uploads")

# RC-08: wildcard origin '*' + allow_credentials=True TIDAK sah menurut spec CORS (browser
# menolak kredensial dgn '*'). App memakai Bearer header (bukan cookie) → matikan credentials
# saat origin '*' agar konfigurasi spec-compliant & tidak menyesatkan. Set CORS_ORIGINS ke
# origin spesifik utk mengaktifkan credentials (JANGAN ubah REACT_APP_BACKEND_URL/MONGO_URL).
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
_cors_allow_credentials = "*" not in _cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_credentials=_cors_allow_credentials,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    # CMS-D3: expose pagination headers ke browser (default CORS menyembunyikan header kustom).
    expose_headers=["X-Total-Count", "X-Limit", "X-Offset"],
)


@app.on_event("startup")
async def _startup():
    db = get_db()
    try:
        await db.users.create_index("email", unique=True)
        await db.sessions.create_index("token", unique=True)
        await db.sessions.create_index("user_id")
        # RC-09: TTL index — sesi kedaluwarsa dibersihkan otomatis Mongo (field Date `expires_dt`).
        await db.sessions.create_index("expires_dt", expireAfterSeconds=0)
        # RC-10: TTL index utk pelacakan kegagalan login persisten (anti brute-force lintas-worker).
        await db.login_failures.create_index("expire_at", expireAfterSeconds=0)
        await db.login_failures.create_index([("key", 1), ("ts", 1)])
        await db.locations.create_index([("trip_id", 1), ("timestamp", -1)])
        await db.locations.create_index([("vehicle_id", 1), ("timestamp", -1)])
        await db.bookings.create_index([("vehicle_id", 1), ("status", 1)])
        await db.bookings.create_index("start_datetime")
        # RC-16: TTL jaring pengaman utk mutex booking (booking_locks) — lock yatim (holder crash)
        # dibersihkan otomatis. Lock normal dilepas dlm <1s; TTL 60s hanya fallback.
        await db.booking_locks.create_index("acquired_at", expireAfterSeconds=60)
        await db.payments.create_index("booking_id")
        # Idempotency pembayaran: unik-parsial pada idempotency_key (null diabaikan) → retry/klik-ganda
        # dgn key sama tak bisa membuat catatan pembayaran ganda (anti double-charge/over-record).
        await db.payments.create_index(
            "idempotency_key", unique=True,
            partialFilterExpression={"idempotency_key": {"$type": "string"}})
        await db.maintenance_records.create_index([("vehicle_id", 1), ("status", 1)])
        await db.trip_shares.create_index("token", unique=True)
        await db.trip_shares.create_index("trip_id")
        await db.notification_tasks.create_index("dedupe_key", unique=True, sparse=True)
        await db.notification_tasks.create_index([("status", 1), ("created_at", -1)])
        await db.conversations.create_index("chat_token", sparse=True)
        await db.conversations.create_index([("status", 1), ("last_message_at", -1)])
        await db.messages.create_index([("conversation_id", 1), ("created_at", 1)])
        await db.settings.create_index("key", unique=True)
        # ID-RACE: unik-parsial pada nomor ter-normalisasi (non-kosong) → cegah customer GANDA
        # saat pembuatan paralel (dua request kontak sama lolos TOCTOU find-then-insert). Nilai
        # kosong/tak-ada diabaikan (tak bisa dedupe tanpa kontak). $gt "" = string non-kosong.
        await db.customers.create_index(
            "phone_normalized", unique=True,
            partialFilterExpression={"phone_normalized": {"$gt": ""}})
        # E1: Event Bus + Automation Engine
        await db.events.create_index("dedupe_key", unique=True, sparse=True)
        await db.events.create_index([("type", 1), ("created_at", -1)])
        await db.automation_rules.create_index([("event_type", 1), ("enabled", 1)])
        await db.automation_runs.create_index("dedupe_key", unique=True, sparse=True)
        await db.automation_runs.create_index([("rule_id", 1), ("created_at", -1)])
        await db.conversations.create_index([("channel", 1), ("contact_phone", 1)])
        # E2: CRM Growth
        await db.leads.create_index([("score", -1)])
        await db.leads.create_index("sla_status")
        await db.sequence_enrollments.create_index([("status", 1), ("next_run_at", 1)])
        await db.sequence_enrollments.create_index([("sequence_id", 1), ("target_id", 1)])
        await db.campaigns.create_index([("status", 1), ("scheduled_at", 1)])
        await db.campaign_recipients.create_index("campaign_id")
        # FASE F3/F4/F5/F6: outbox konversi, metrik iklan, lead platform, sinkron audiens
        from services import ads_metrics as _am
        from services import audiences as _aud
        from services import conversions as _cv
        from services import lead_ads as _la
        await _cv.ensure_indexes(db)
        await _am.ensure_indexes(db)
        await _la.ensure_indexes(db)
        await _aud.ensure_indexes(db)
        await db.leads.create_index([("ad_campaign_id", 1)], sparse=True)
        await db.leads.create_index([("ad_id", 1)], sparse=True)
        await db.landing_pages.create_index("slug", unique=True)
        await db.landing_pages.create_index([("status", 1), ("updated_at", -1)])
        await db.media_assets.create_index([("created_at", -1)])
        # FASE F8 — Landing Page Builder: statistik A/B + anti-duplikat lead dari halaman iklan.
        # Unique index (bukan sekadar cek-lalu-tulis) supaya dua submit paralel dari klik ganda
        # tetap menghasilkan SATU lead — sales tidak boleh menelepon orang yang sama dua kali.
        from services import landing_stats as _lst
        await _lst.ensure_indexes(db)
        await db.media_assets.create_index([("kind", 1), ("deleted", 1), ("created_at", -1)])
        # Media Manager v2 — folder + impor aset lama idempoten (unik-parsial legacy_key).
        from services import media_lib as _mlib
        await _mlib.ensure_indexes(db)
        await db.leads.create_index("lp_dedupe_key", unique=True, sparse=True)
        await db.leads.create_index([("landing_page_id", 1), ("created_at", -1)], sparse=True)
        # Pemesanan online publik: token halaman status + idempotensi submit + antrean bukti bayar.
        from services import booking_public as _bpub
        await _bpub.ensure_indexes(db)
        # CMS-05/07/08 — siklus terbit konten, funnel ulasan, statistik konten.
        from services import content_publish as _cp
        from services import content_stats as _cst
        from services import reviews as _rv
        await _cp.ensure_indexes(db)
        await _rv.ensure_indexes(db)
        await _cst.ensure_indexes(db)
        # CMS-10/11/12 — riwayat versi, tempat sampah, pengalihan URL.
        from services import content_redirects as _crd
        from services import content_trash as _ctr
        from services import content_versions as _cvr
        await _cvr.ensure_indexes(db)
        await _ctr.ensure_indexes(db)
        await _crd.ensure_indexes(db)
    except Exception as exc:  # index opsional; jangan gagalkan boot
        logger.warning("index init skip: %s", exc)
    # Scheduler reminder (Phase 7): scan periodik idempotent di background.
    try:
        app.state.scheduler_task = asyncio.create_task(_scheduler_loop())
    except Exception as exc:
        logger.warning("scheduler start skip: %s", exc)
    # Sidecar OpenWA: auto-hidupkan bila provider WA aktif = openwa (sesi tahan restart backend).
    try:
        from services.openwa import autostart as _openwa_autostart
        app.state.openwa_task = asyncio.create_task(_openwa_autostart(get_db()))
    except Exception as exc:  # noqa: BLE001
        logger.warning("openwa autostart skip: %s", exc)
    # Broadcast 'sending' yatim (worker hilang saat restart) → failed agar bisa Kirim Ulang.
    try:
        from routers.broadcasts import reap_stale_sending
        await reap_stale_sending()
    except Exception as exc:  # noqa: BLE001
        logger.warning("broadcast reaper skip: %s", exc)


async def _scheduler_loop():
    from services.notifications import scan as notif_scan
    from services.growth import scan_sla, scan_rfm
    from services.sequences import process_due as seq_process
    from services.campaigns import process_scheduled as cmp_process
    from services.conversions import dispatch_pending as conv_dispatch
    from services.integrations import active_configs
    from core_utils import now_iso
    await asyncio.sleep(8)  # beri waktu boot selesai
    while True:
        db = get_db()
        try:
            created = await notif_scan(db)
            if created:
                logger.info("scheduler: %d notifikasi baru", created)
        except Exception as exc:  # jangan biarkan loop mati
            logger.warning("scheduler scan error: %s", exc)
        for name, fn in (("sla", scan_sla), ("rfm", scan_rfm),
                         ("sequences", seq_process), ("campaigns", cmp_process)):
            try:
                await fn(db)
            except Exception as exc:  # noqa: BLE001
                logger.warning("scheduler %s error: %s", name, exc)
        # CMS-05 — terbitkan konten yang jadwalnya sudah lewat (artikel musiman/paket promo).
        # Visibilitas publik sudah menghitung jadwal secara langsung; langkah ini merapikan
        # status di database supaya admin & laporan tidak melihat "Terjadwal" abadi.
        try:
            from services.content_publish import publish_due
            published = await publish_due(db)
            if published:
                logger.info("scheduler: %d konten terbit sesuai jadwal", published)
        except Exception as exc:  # noqa: BLE001
            logger.warning("scheduler publish error: %s", exc)
        # CMS-07 — jaring pengaman funnel ulasan: pesanan selesai yang belum diminta ulasan.
        try:
            from services.reviews import scan_due as review_scan
            asked = await review_scan(db)
            if asked:
                logger.info("scheduler: %d permintaan ulasan dikirim (WA MOCK)", asked)
        except Exception as exc:  # noqa: BLE001
            logger.warning("scheduler review error: %s", exc)
        # CMS-11 — Tempat Sampah konten: buang otomatis yang melewati retensi (30 hari).
        # Tanpa langkah ini konten terhapus tersimpan selamanya (termasuk salinan gambar &
        # teks yang mungkin sengaja ingin dihilangkan pemiliknya).
        try:
            from services.content_trash import purge_expired as trash_purge
            purged = await trash_purge(db)
            if purged:
                logger.info("scheduler: %d konten di tempat sampah dibuang permanen", purged)
        except Exception as exc:  # noqa: BLE001
            logger.warning("scheduler trash purge error: %s", exc)
        # FASE F3 — pekerja outbox konversi: kirim yang pending + retry yang jatuh tempo.
        # Tanpa ini konversi yang gagal sekali akan hilang selamanya (rugi diam-diam).
        try:
            out = await conv_dispatch(db, await active_configs(db), limit=50)
            if any(out.values()):
                await db.settings.update_one(
                    {"key": "conversion_worker_state"},
                    {"$set": {"key": "conversion_worker_state",
                              "value": {"last_run_at": now_iso(), "source": "scheduler", **out}}},
                    upsert=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("scheduler konversi error: %s", exc)
        await asyncio.sleep(120)


@app.on_event("shutdown")
async def _shutdown():
    close()

"""routers/marketing.py — Integrasi API (Meta/Google/WhatsApp) + konfigurasi pelacakan publik.

MENGAPA: user meminta "pastikan di pengaturan saya bisa input api ini jadi tidak hardcoded".
Semua kredensial diisi lewat UI, disimpan TERENKRIPSI di koleksi `settings`
(`services/secrets_vault.py`), dan respons API hanya memuat bentuk ter-mask.
SSOT bentuk konfigurasi ada di `services/integrations.py` (dipakai bersama router Ads).

Endpoint:
  GET   /api/integrations/config            -> semua provider (ter-mask) + status kesiapan
  PATCH /api/integrations/config/{provider} -> simpan (owner/marketing_admin) + audit
  POST  /api/integrations/test/{provider}   -> uji kesiapan (dry-run; tanpa mengirim data nyata)
  GET   /api/public/tracking-config         -> PUBLIK, hanya ID publik (JANGAN pernah token)
  GET   /api/tracking/health                -> ringkasan outbox konversi
  POST  /api/tracking/test-event            -> kirim event uji (test_event_code/validateOnly)
  POST  /api/tracking/retry/{event_id}      -> coba ulang satu percobaan
  POST  /api/tracking/dispatch              -> jalankan pekerja outbox sekarang (manual)
"""
from fastapi import APIRouter, Body, Depends, HTTPException

from core_utils import now_iso
from db import get_db
from dependencies import require_role, require_section
from services import conversions as cv
from services import secrets_vault as vault
from services.audit import record
from services.integrations import (CONSENT_KEY, DEFAULT_CONSENT, PROVIDERS, active_configs,
                                   consent_cfg, load_provider, readiness)

router = APIRouter(prefix="/api", tags=["marketing"])
READ = require_section("integrations")            # owner + marketing_admin
WRITE = require_role("owner", "marketing_admin")  # mutasi kredensial
TRACK = require_section("tracking")


@router.get("/integrations/config")
async def integrations_config(user=Depends(READ)):
    """Bentuk aman: tidak ada token/ciphertext, hanya flag `*_set` + `*_masked`."""
    db = get_db()
    out = {"vault_ready": vault.vault_ready(), "providers": {}, "consent": await consent_cfg(db)}
    for provider, spec in PROVIDERS.items():
        _, cfg = await load_provider(db, provider)
        out["providers"][provider] = {
            "label": spec["label"],
            "config": vault.public_view(cfg, spec["secrets"]),
            "status": readiness(spec, cfg),
            "ads_status": readiness(spec, cfg, requirement="ads_required"),
            "secret_fields": list(spec["secrets"]),
        }
    return out


@router.patch("/integrations/config/{provider}")
async def update_integration(provider: str, body: dict = Body(default={}), user=Depends(WRITE)):
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail="Provider tidak dikenal")
    if not vault.vault_ready():
        raise HTTPException(status_code=400, detail="Kunci enkripsi (SETTINGS_ENCRYPTION_KEY_B64) "
                                                   "belum diset — kredensial tidak dapat disimpan dengan aman.")
    db = get_db()
    spec, cfg = await load_provider(db, provider)
    incoming = body or {}
    for field, default in spec["public"].items():
        if field not in incoming:
            continue
        val = incoming[field]
        if isinstance(default, bool):
            cfg[field] = bool(val)
        elif isinstance(default, int):
            # plafon budget: bilangan bulat non-negatif (0 = tanpa plafon)
            try:
                cfg[field] = max(0, int(float(val or 0)))
            except (TypeError, ValueError):
                raise HTTPException(status_code=400,
                                    detail=f"Nilai '{field}' harus berupa angka.") from None
        elif isinstance(default, dict):
            merged = dict(cfg.get(field) or {})
            if isinstance(val, dict):
                merged.update({k: str(v or "").strip()[:120] for k, v in val.items() if k in default})
            cfg[field] = merged
        elif isinstance(default, list):
            cfg[field] = [str(v).strip()[:64] for v in (val or [])][:20]
        else:
            cfg[field] = str(val or "").strip()[:200]
    cfg = vault.store_secrets(cfg, incoming, spec["secrets"])
    cfg["updated_at"] = now_iso()
    cfg["updated_by"] = user.get("email")
    await db.settings.update_one({"key": spec["key"]}, {"$set": {"key": spec["key"], "value": cfg}}, upsert=True)
    changed = [k for k in incoming if k in spec["public"]] + \
              [f"{k}(rahasia)" for k in incoming if k in spec["secrets"] and str(incoming[k] or "").strip()]
    await record(db, actor=user, action="update", entity_type="settings", entity_id=spec["key"],
                 summary=f"Ubah integrasi {spec['label']}: {', '.join(changed) or 'tanpa perubahan'}")
    return {"config": vault.public_view(cfg, spec["secrets"]), "status": readiness(spec, cfg),
            "ads_status": readiness(spec, cfg, requirement="ads_required")}


@router.patch("/integrations/consent")
async def update_consent(body: dict = Body(default={}), user=Depends(WRITE)):
    db = get_db()
    cfg = await consent_cfg(db)
    for k, default in DEFAULT_CONSENT.items():
        if k not in (body or {}):
            continue
        cfg[k] = bool(body[k]) if isinstance(default, bool) else str(body[k] or "").strip()[:400]
    if cfg.get("consent_mode") not in ("advanced", "basic"):
        cfg["consent_mode"] = "advanced"
    await db.settings.update_one({"key": CONSENT_KEY}, {"$set": {"key": CONSENT_KEY, "value": cfg}}, upsert=True)
    await record(db, actor=user, action="update", entity_type="settings", entity_id=CONSENT_KEY,
                 summary="Ubah pengaturan persetujuan pelacakan (consent)")
    return cfg


@router.post("/integrations/test/{provider}")
async def test_integration(provider: str, user=Depends(WRITE)):
    """Uji kesiapan TANPA mengirim data pelanggan: cek kelengkapan + tukar token (Google)."""
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail="Provider tidak dikenal")
    db = get_db()
    spec, cfg = await load_provider(db, provider)
    status = readiness(spec, cfg)
    if status["missing"]:
        return {"ok": False, "mode": "mock",
                "message": "Belum lengkap: " + ", ".join(status["missing_labels"])}
    secrets = vault.secrets_bundle(cfg, spec["secrets"])
    if provider == "google_ads":
        token = await cv.google_access_token(cfg, secrets)
        if not token:
            return {"ok": False, "mode": "live",
                    "message": "Refresh token ditolak Google (cek client id/secret & refresh token)."}
        return {"ok": True, "mode": "live", "message": "OAuth Google berhasil ditukar menjadi access token."}
    return {"ok": True, "mode": "live",
            "message": "Konfigurasi Meta lengkap. Gunakan 'Kirim event uji' di Kesehatan Pelacakan "
                       "untuk memverifikasi di Events Manager."}


@router.get("/public/tracking-config")
async def public_tracking_config():
    """PUBLIK & tanpa auth: HANYA identitas publik yang memang dikirim ke browser.

    Allowlist field bersifat KETAT (dijaga INV-TRACK-01) — token/app secret tidak boleh ikut.
    """
    db = get_db()
    _, meta = await load_provider(db, "meta_ads")
    _, goog = await load_provider(db, "google_ads")
    consent = await consent_cfg(db)
    return {
        "consent": consent,
        "meta": {"enabled": bool(meta.get("enabled")) and bool(meta.get("pixel_id")),
                 "pixel_id": meta.get("pixel_id") or ""},
        "google": {"enabled": bool(goog.get("enabled")) and bool(goog.get("ga4_measurement_id") or goog.get("ads_conversion_id")),
                   "ga4_measurement_id": goog.get("ga4_measurement_id") or "",
                   "ads_conversion_id": goog.get("ads_conversion_id") or "",
                   "conversion_labels": goog.get("conversion_labels") or {}},
    }


@router.get("/tracking/health")
async def tracking_health(limit: int = 30, status: str = "", provider: str = "",
                          user=Depends(TRACK)):
    db = get_db()
    summary = await cv.health_summary(db)
    query = {}
    if status in ("pending", "success", "failed", "skipped", "dead"):
        query["status"] = status
    if provider in cv.PROVIDERS:
        query["provider"] = provider
    rows = await db[cv.COLL].find(query, {"_id": 0}).sort("created_at", -1).to_list(max(1, min(limit, 100)))
    ready = {}
    for prov, mapped in (("meta_ads", "meta"), ("google_ads", "google")):
        spec, cfg = await load_provider(db, prov)
        ready[mapped] = readiness(spec, cfg)
    worker = await db.settings.find_one({"key": "conversion_worker_state"}, {"_id": 0}) or {}
    return {"summary": summary, "attempts": rows, "readiness": ready,
            "max_attempts": cv.MAX_ATTEMPTS, "worker": worker.get("value") or {},
            "filter": {"status": status, "provider": provider}}


@router.post("/tracking/test-event")
async def tracking_test_event(body: dict = Body(default={}), user=Depends(require_role("owner", "marketing_admin"))):
    """Kirim event uji (Meta: test_event_code, Google: validateOnly) lalu laporkan hasil per provider."""
    db = get_db()
    kind = str((body or {}).get("kind") or "lead")
    if kind not in cv.EVENT_MAP:
        raise HTTPException(status_code=400, detail="Jenis event uji tidak dikenal")
    ref = f"uji-{now_iso().replace(':', '').replace('.', '')[:17]}"
    ident = {"email": "uji@rahazatrans.test", "phone": "081200000000", "user_agent": "RahazaTransERP-TestEvent"}
    if (body or {}).get("ctwa"):
        ident["ctwa_clid"] = "UJI-CTWA-CLID"
    await cv.enqueue(db, kind, ref, value=int((body or {}).get("value") or 0), identifiers=ident,
                     source_url=(body or {}).get("source_url") or "", consent_granted=True)
    cfgs = await active_configs(db)
    results = {}
    for provider in cv.PROVIDERS:
        ev = await db[cv.COLL].find_one({"event_key": cv.event_key(kind, ref), "provider": provider}, {"_id": 0})
        if not ev:
            continue
        status, detail = await cv.dispatch_one(db, ev, cfgs, test=True)
        results[provider] = {"status": status, "detail": str(detail)[:240]}
    ringkas = ", ".join(f"{k}={v['status']}" for k, v in results.items())
    await record(db, actor=user, action="create", entity_type="tracking", entity_id=ref,
                 summary=f"Kirim event uji {kind} ({ringkas})")
    return {"event_key": cv.event_key(kind, ref), "results": results}


@router.post("/tracking/retry/{event_id}")
async def tracking_retry(event_id: str, user=Depends(require_role("owner", "marketing_admin"))):
    db = get_db()
    ev = await db[cv.COLL].find_one({"id": event_id}, {"_id": 0})
    if not ev:
        raise HTTPException(status_code=404, detail="Percobaan konversi tidak ditemukan")
    await db[cv.COLL].update_one({"id": event_id}, {"$set": {"status": "pending", "next_retry_at": None}})
    ev = await db[cv.COLL].find_one({"id": event_id}, {"_id": 0})
    status, detail = await cv.dispatch_one(db, ev, await active_configs(db))
    return {"status": status, "detail": str(detail)[:240]}


@router.post("/tracking/dispatch")
async def tracking_dispatch(user=Depends(require_role("owner", "marketing_admin"))):
    """Jalankan pekerja outbox SEKARANG (normalnya otomatis tiap 2 menit oleh scheduler)."""
    db = get_db()
    out = await cv.dispatch_pending(db, await active_configs(db), limit=100)
    await db.settings.update_one(
        {"key": "conversion_worker_state"},
        {"$set": {"key": "conversion_worker_state",
                  "value": {"last_run_at": now_iso(), "source": "manual", **out}}}, upsert=True)
    return {"processed": out}

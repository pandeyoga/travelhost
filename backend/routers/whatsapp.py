"""routers/whatsapp.py — WhatsApp Adapter API (E1, mock-first).

Konfigurasi provider (owner), manajemen template, simulasi inbound (uji tanpa kredensial),
dan webhook publik (verifikasi + ingest). Webhook TANPA auth (kontrak Meta Cloud).
Provider nyata `meta_cloud` diaktifkan di E6.
"""
import asyncio
import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from db import get_db
from dependencies import require_role, require_section
from schemas import WaConfigUpdate, WaSimulateInbound, WaTemplateUpsert, WaTestSend
from services import openwa as openwa_svc
from services import whatsapp as wa
from services.audit import record

logger = logging.getLogger("travel_fleet.wa_router")
router = APIRouter(prefix="/api", tags=["whatsapp"])
OWNER = require_role("owner")
# FASE F: konfigurasi WA adalah bagian halaman "Integrasi API" -> owner + marketing_admin.
INTEGRATIONS = require_section("integrations")
CRM = require_section("crm")


def _mask_config(cfg):
    """Sembunyikan rahasia; tampilkan status terkonfigurasi."""
    out = dict(cfg)
    meta = dict(out.get("meta") or {})
    out["meta"] = {
        "phone_number_id": meta.get("phone_number_id", ""),
        "verify_token": meta.get("verify_token", ""),
        "api_version": meta.get("api_version", "v21.0"),
        "access_token_set": bool(meta.get("access_token")),
        "app_secret_set": bool(meta.get("app_secret")),
    }
    out["meta_cloud_ready"] = bool(meta.get("phone_number_id") and meta.get("access_token"))
    return out


@router.get("/wa/config")
async def get_wa_config(user=Depends(INTEGRATIONS)):
    return _mask_config(await wa.get_config(get_db()))


@router.patch("/wa/config")
async def update_wa_config(body: WaConfigUpdate, user=Depends(require_role("owner", "marketing_admin"))):
    db = get_db()
    cfg = await wa.get_config(db)
    updates = body.model_dump(exclude_unset=True)
    if "provider" in updates and updates["provider"] not in ("mock", "meta_cloud", "partner", "openwa"):
        raise HTTPException(status_code=400, detail="Provider tidak valid")
    meta_update = updates.pop("meta", None)
    cfg.update({k: v for k, v in updates.items() if v is not None})
    if isinstance(meta_update, dict):
        merged = dict(cfg.get("meta") or {})
        merged.update({k: v for k, v in meta_update.items() if v is not None and v != ""})
        cfg["meta"] = merged
    await db.settings.update_one({"key": "wa_config"}, {"$set": {"key": "wa_config", "value": cfg}}, upsert=True)
    await record(db, actor=user, action="update", entity_type="settings", entity_id="wa_config",
                 summary=f"Ubah konfigurasi WhatsApp (provider={cfg.get('provider')})")
    if cfg.get("provider") == "openwa":
        # hidupkan sidecar di background — respons UI tetap cepat, panel mem-poll status.
        asyncio.create_task(openwa_svc.ensure_running())
    return _mask_config(cfg)


@router.get("/wa/templates")
async def list_templates(user=Depends(CRM)):
    tpls = await wa.get_templates(get_db())
    return [{"key": k, **v} for k, v in tpls.items()]


@router.put("/wa/templates/{key}")
async def upsert_template(key: str, body: WaTemplateUpsert, user=Depends(OWNER)):
    db = get_db()
    tpls = dict(await wa.get_templates(db))
    tpls[key] = {"name": body.name or key, "language": body.language or "id",
                 "category": body.category or "utility", "body": body.body or ""}
    await db.settings.update_one({"key": "wa_templates"}, {"$set": {"key": "wa_templates", "value": tpls}}, upsert=True)
    await record(db, actor=user, action="update", entity_type="settings", entity_id=f"wa_template:{key}",
                 summary=f"Simpan template WA '{key}'")
    return {"key": key, **tpls[key]}


@router.delete("/wa/templates/{key}")
async def delete_template(key: str, user=Depends(OWNER)):
    db = get_db()
    tpls = dict(await wa.get_templates(db))
    if key not in tpls:
        raise HTTPException(status_code=404, detail="Template tidak ditemukan")
    tpls.pop(key)
    await db.settings.update_one({"key": "wa_templates"}, {"$set": {"key": "wa_templates", "value": tpls}}, upsert=True)
    return {"deleted": True, "key": key}


@router.post("/wa/simulate-inbound")
async def simulate_inbound(body: WaSimulateInbound, user=Depends(CRM)):
    """Uji end-to-end inbound WA tanpa kredensial (mock): membuat lead/percakapan + memicu otomasi.

    Sertakan `referral` untuk menguji jalur iklan Klik-ke-WhatsApp (CTWA) tanpa kredensial Meta.
    """
    res = await wa.handle_inbound(get_db(), body.from_phone, body.text, name=body.name,
                                  referral=body.referral)
    return res


@router.post("/wa/test-send")
async def wa_test_send(body: WaTestSend, user=Depends(OWNER)):
    """Kirim pesan tes via provider AKTIF. Mock → 'sent'; meta_cloud tanpa kredensial → 'failed' (pesan jelas)."""
    db = get_db()
    res = await wa.send_wa(db, body.to_phone, text=body.text, source="test", author_id=user.get("id"))
    cfg = await wa.get_config(db)
    res["provider"] = res.get("provider") or cfg.get("provider")
    res["ok"] = res.get("status") in ("sent", "delivered", "read")
    await record(db, actor=user, action="test", entity_type="settings", entity_id="wa_config",
                 summary=f"Tes kirim WhatsApp ke {body.to_phone} (provider={res['provider']}, status={res.get('status')})")
    return res


@router.get("/wa/webhook")
async def wa_webhook_verify(request: Request):
    """Verifikasi webhook Meta Cloud (hub.challenge). Publik, tanpa auth."""
    params = request.query_params
    cfg = await wa.get_config(get_db())
    token = (cfg.get("meta") or {}).get("verify_token")
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == token:
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verifikasi webhook gagal")


@router.post("/wa/webhook")
async def wa_webhook_receive(request: Request):
    """Terima pesan WA inbound (publik). Verifikasi signature bila meta_cloud + app_secret."""
    db = get_db()
    cfg = await wa.get_config(db)
    raw = await request.body()
    if cfg.get("provider") == "meta_cloud":
        secret = (cfg.get("meta") or {}).get("app_secret")
        if secret and not wa.verify_signature(secret, raw, request.headers.get("X-Hub-Signature-256")):
            raise HTTPException(status_code=403, detail="Signature tidak valid")
    try:
        payload = json.loads(raw or b"{}")
    except Exception:
        payload = {}
    provider = wa._provider_for(cfg)
    msgs = provider.parse_webhook(payload)
    received = 0
    for m in msgs:
        if m.get("from") and m.get("text"):
            await wa.handle_inbound(db, m["from"], m["text"], name=m.get("name"),
                                    provider_msg_id=m.get("wa_message_id"),
                                    referral=m.get("referral"))
            received += 1
    return {"status": "ok", "received": received}


# ---------------------------------------------------------------------------
# OpenWA sidecar (provider unofficial, scan QR) — kelola & pantau dari UI admin.
# ---------------------------------------------------------------------------
@router.get("/wa/openwa/status")
async def openwa_status(user=Depends(INTEGRATIONS)):
    """Status sidecar OpenWA (auto-spawn bila mati). Dipoll panel Integrasi API."""
    return await openwa_svc.ensure_running(wait_seconds=3)


@router.get("/wa/openwa/qr")
async def openwa_qr(user=Depends(INTEGRATIONS)):
    """Data QR mentah untuk dirender & discan dari halaman admin (kosong bila belum siap)."""
    return {"qr": await openwa_svc.get_qr()}


@router.post("/wa/openwa/restart")
async def openwa_restart(fresh: bool = Query(default=False),
                         user=Depends(require_role("owner", "marketing_admin"))):
    """Restart sidecar. fresh=true → hapus sesi (WAJIB scan QR ulang)."""
    if fresh:
        await asyncio.to_thread(openwa_svc.reset_session)
    else:
        await asyncio.to_thread(openwa_svc.stop)
    res = await openwa_svc.ensure_running(wait_seconds=10)
    await record(get_db(), actor=user, action="update", entity_type="settings", entity_id="openwa",
                 summary=f"Restart sidecar OpenWA (fresh={fresh})")
    return res


@router.post("/wa/openwa-webhook")
async def openwa_webhook(request: Request):
    """Callback sidecar OpenWA LOKAL (bukan publik luar) — dijaga key rahasia di query.

    Fail-closed: tanpa OPENWA_API_KEY di env atau key salah → 403.
    """
    expected = (os.environ.get("OPENWA_API_KEY") or "").strip()
    if not expected or request.query_params.get("key") != expected:
        raise HTTPException(status_code=403, detail="Key tidak valid")
    try:
        payload = json.loads((await request.body()) or b"{}")
    except Exception:  # noqa: BLE001
        payload = {}
    db = get_db()
    msgs = wa._parse_openwa_event(payload)
    received = 0
    for m in msgs:
        await wa.handle_inbound(db, m["from"], m["text"], name=m.get("name"),
                                provider_msg_id=m.get("wa_message_id"), referral=m.get("referral"))
        received += 1
    return {"status": "ok", "received": received}

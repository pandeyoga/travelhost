"""routers/gps.py — GPS dual-source (E15).

Endpoint:
  POST   /api/gps/webhook               ← Traccar position-forward (device fisik). PUBLIK,
                                          diamankan dgn shared secret (header X-Gps-Token /
                                          Authorization: Bearer / query ?token=). Bukan JWT
                                          karena Traccar tak bisa login sesi.
  GET    /api/gps/live                  → posisi live per armada (failover device>phone)
  GET    /api/gps/devices               → daftar armada + status device (online/voltase/alarm)
  GET    /api/gps/summary               → KPI device (terpasang/online/offline/alarm)
  POST   /api/gps/devices/{vid}/assign  → pasang IMEI ke armada (manager)
  DELETE /api/gps/devices/{vid}         → lepas device dari armada (manager)

Webhook TIDAK yatim (D2): frontend memanggil /gps/live & /gps/devices.
"""
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from db import get_db
from dependencies import require_role, require_section
from schemas import GpsDeviceAssign
from services import gps as gps_svc
from services.audit import record

router = APIRouter(prefix="/api/gps", tags=["gps"])
MANAGER = require_role("owner", "ops_admin")
# RBAC-SECT-01: permukaan BACA modul ini WAJIB lewat pintu section, bukan sekadar "sudah login".
# Sebelum perbaikan ini `marketing_admin` mendapat HTTP 200 di seluruh GET di bawah (nama
# pelanggan, nominal booking, telepon sopir, posisi GPS) padahal menunya memang tidak
# pernah ditampilkan untuk peran itu — SSOT `permissions_config.SECTION_ACCESS` + FE
# `ROLE_MENU_ALLOWLIST` sama-sama mengecualikannya. Kelas bug BUG-0107 terulang: peran BARU
# (marketing_admin, lahir di FASE F) tidak pernah diuji ulang terhadap endpoint BACA LAMA.
GPS_SEC = require_section("gps")


def _webhook_secret():
    return os.environ.get("GPS_WEBHOOK_SECRET", "")


@router.post("/webhook")
async def gps_webhook(request: Request, token: str = Query(default=None),
                      x_gps_token: str = Header(default=None)):
    """Terima position-forward dari Traccar. Verifikasi shared secret → ingest device."""
    secret = _webhook_secret()
    provided = x_gps_token or token
    if not provided:
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            provided = auth[7:].strip()
    if not secret or provided != secret:
        raise HTTPException(status_code=401, detail="Token webhook GPS tidak valid")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Payload JSON tidak valid")
    norm = gps_svc.parse_traccar(payload)
    return await gps_svc.ingest_device(get_db(), norm)


@router.get("/live")
async def gps_live(user=Depends(GPS_SEC)):
    return await gps_svc.live_positions(get_db())


@router.get("/devices")
async def gps_devices(user=Depends(GPS_SEC)):
    return await gps_svc.list_devices(get_db())


@router.get("/summary")
async def gps_summary(user=Depends(GPS_SEC)):
    return await gps_svc.summary(get_db())


@router.post("/devices/{vehicle_id}/assign")
async def gps_assign(vehicle_id: str, body: GpsDeviceAssign, user=Depends(MANAGER)):
    db = get_db()
    veh, err = await gps_svc.assign_device(db, vehicle_id, body.imei, body.enabled, body.note or "")
    if err:
        raise HTTPException(status_code=400, detail=err)
    await record(db, actor=user, action="update", entity_type="vehicle", entity_id=vehicle_id,
                 summary=f"Pasang device GPS (IMEI {body.imei}) ke {veh.get('name')}")
    return {"ok": True, "vehicle_id": vehicle_id, "gps": veh.get("gps")}


@router.delete("/devices/{vehicle_id}")
async def gps_unassign(vehicle_id: str, user=Depends(MANAGER)):
    db = get_db()
    ok = await gps_svc.unassign_device(db, vehicle_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Kendaraan tidak ditemukan")
    await record(db, actor=user, action="update", entity_type="vehicle", entity_id=vehicle_id,
                 summary="Lepas device GPS dari armada")
    return {"ok": True, "vehicle_id": vehicle_id}

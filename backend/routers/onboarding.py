"""routers/onboarding.py — Checklist onboarding pengguna (Phase 8 / A5).

GET  /api/onboarding              → checklist peran pengguna (derived + manual)
POST /api/onboarding/complete     ← {task} tandai satu tugas selesai
POST /api/onboarding/dismiss      → sembunyikan checklist untuk pengguna ini
POST /api/onboarding/reset        → tampilkan & reset penyelesaian manual
Semua untuk pengguna yang sedang login (semua peran).
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core_utils import now_iso
from db import get_db
from dependencies import get_current_user
from services.onboarding import build_state

router = APIRouter(prefix="/api", tags=["onboarding"])


class CompleteBody(BaseModel):
    task: str


@router.get("/onboarding")
async def get_onboarding(user=Depends(get_current_user)):
    return await build_state(get_db(), user)


@router.post("/onboarding/complete")
async def complete_task(body: CompleteBody, user=Depends(get_current_user)):
    db = get_db()
    await db.user_onboarding.update_one(
        {"user_id": user["id"]},
        {"$addToSet": {"completed": body.task},
         "$setOnInsert": {"user_id": user["id"], "created_at": now_iso()},
         "$set": {"updated_at": now_iso()}},
        upsert=True,
    )
    return await build_state(db, user)


@router.post("/onboarding/dismiss")
async def dismiss(user=Depends(get_current_user)):
    db = get_db()
    await db.user_onboarding.update_one(
        {"user_id": user["id"]},
        {"$set": {"dismissed": True, "updated_at": now_iso()},
         "$setOnInsert": {"user_id": user["id"], "created_at": now_iso()}},
        upsert=True,
    )
    return {"dismissed": True}


@router.post("/onboarding/reset")
async def reset(user=Depends(get_current_user)):
    db = get_db()
    await db.user_onboarding.update_one(
        {"user_id": user["id"]},
        {"$set": {"dismissed": False, "completed": [], "updated_at": now_iso()},
         "$setOnInsert": {"user_id": user["id"], "created_at": now_iso()}},
        upsert=True,
    )
    return await build_state(db, user)

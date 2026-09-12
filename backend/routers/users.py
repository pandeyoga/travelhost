"""routers/users.py — manajemen user (RBAC: owner). Respons telanjang (tanpa envelope).

E0/G8: guard 'minimal 1 owner aktif' + larang ubah-peran/nonaktifkan diri sendiri.
E0/G3: audit create/update user (password TIDAK pernah masuk audit).
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from core_utils import hash_password, new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_role
from permissions_config import ROLES
from schemas import UserCreate, UserUpdate
from services.audit import record

router = APIRouter(prefix="/api", tags=["users"])


def _no_pw(doc):
    """Salinan dokumen tanpa field sensitif untuk snapshot audit."""
    return {k: v for k, v in (doc or {}).items() if k not in ("password_hash", "_id")}


@router.get("/users")
async def list_users(limit: int = Query(default=200, le=500), skip: int = Query(default=0, ge=0),
                     user=Depends(require_role("owner"))):
    docs = await get_db().users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).skip(skip).to_list(limit)
    return safe_doc(docs)


@router.post("/users")
async def create_user(body: UserCreate, user=Depends(require_role("owner"))):
    db = get_db()
    email = body.email.lower().strip()
    if body.role not in ROLES:
        raise HTTPException(status_code=400, detail="Peran tidak valid")
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    doc = {
        "id": new_id("usr"),
        "name": body.name.strip(),
        "email": email,
        "password_hash": hash_password(body.password),
        "role": body.role,
        "phone": body.phone or "",
        "status": "active",
        "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    await record(db, actor=user, action="create", entity_type="user", entity_id=doc["id"],
                 after=_no_pw(doc), summary=f"Tambah user {doc.get('name')} ({doc.get('role')})")
    return safe_doc(doc)


@router.get("/users/{user_id}")
async def get_user(user_id: str, user=Depends(require_role("owner"))):
    doc = await get_db().users.find_one({"id": user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    return safe_doc(doc)


@router.patch("/users/{user_id}")
async def update_user(user_id: str, body: UserUpdate, user=Depends(require_role("owner"))):
    db = get_db()
    existing = await db.users.find_one({"id": user_id})
    if not existing:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    is_self = (user_id == user.get("id"))
    # G8a: tidak boleh menurunkan peran / menonaktifkan akun sendiri (anti self-lockout).
    if is_self:
        if body.role is not None and body.role != existing.get("role"):
            raise HTTPException(status_code=400, detail="Tidak dapat mengubah peran akun sendiri")
        if body.status is not None and body.status != "active":
            raise HTTPException(status_code=400, detail="Tidak dapat menonaktifkan akun sendiri")

    # G8b: jaga minimal 1 owner aktif (jangan turunkan/nonaktifkan owner terakhir).
    removing_owner = (
        existing.get("role") == "owner" and existing.get("status") == "active"
        and (
            (body.role is not None and body.role != "owner")
            or (body.status is not None and body.status != "active")
        )
    )
    if removing_owner:
        active_owners = await db.users.count_documents({"role": "owner", "status": "active"})
        if active_owners <= 1:
            raise HTTPException(status_code=400, detail="Minimal harus ada 1 owner aktif")

    updates = {}
    if body.name is not None:
        updates["name"] = body.name.strip()
    if body.phone is not None:
        updates["phone"] = body.phone
    if body.role is not None:
        if body.role not in ROLES:
            raise HTTPException(status_code=400, detail="Peran tidak valid")
        updates["role"] = body.role
    if body.status is not None:
        updates["status"] = body.status
    if body.password:
        updates["password_hash"] = hash_password(body.password)
    if updates:
        await db.users.update_one({"id": user_id}, {"$set": updates})
    doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    await record(db, actor=user, action="update", entity_type="user", entity_id=user_id,
                 before=_no_pw(existing), after=_no_pw(doc),
                 summary=f"Ubah user {doc.get('name')}"
                 + (" (reset sandi)" if body.password else ""))
    return safe_doc(doc)


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, user=Depends(require_role("owner"))):
    """Hapus permanen. Guard: bukan diri sendiri, bukan owner aktif terakhir."""
    db = get_db()
    existing = await db.users.find_one({"id": user_id})
    if not existing:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    if user_id == user.get("id"):
        raise HTTPException(status_code=400, detail="Tidak dapat menghapus akun sendiri")
    if existing.get("role") == "owner" and existing.get("status") == "active":
        active_owners = await db.users.count_documents({"role": "owner", "status": "active"})
        if active_owners <= 1:
            raise HTTPException(status_code=400, detail="Minimal harus ada 1 owner aktif")
    await db.users.delete_one({"id": user_id})
    await record(db, actor=user, action="delete", entity_type="user", entity_id=user_id,
                 before=_no_pw(existing), summary=f"Hapus user {existing.get('name')}")
    return {"ok": True, "id": user_id}

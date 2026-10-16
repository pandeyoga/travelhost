"""routers/auth.py — autentikasi (login/me/logout).
Kontrak: POST /api/auth/login -> {"token":"sess_...","user":{...}} (field = `token`).

E0/G7: rate-limit kegagalan login (anti brute-force) + migrasi transparan hash
legacy SHA256 -> bcrypt saat login berhasil.
E0/G3: audit login berhasil/gagal/diblokir/ditolak + logout.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from core_utils import hash_password, needs_rehash, new_token, now_iso, safe_doc, verify_password
from db import get_db
from dependencies import get_current_user
from schemas import LoginRequest
from services import ratelimit
from services.audit import record

router = APIRouter(prefix="/api", tags=["auth"])

_SESSION_DAYS = 7
_LOGIN_FAIL_LIMIT = 8          # maksimum kegagalan per (ip+email)
_LOGIN_FAIL_WINDOW = 300.0     # dalam 5 menit (sliding)


def _actor(user):
    return {"id": user.get("id"), "name": user.get("name"), "role": user.get("role")}


@router.post("/auth/login")
async def login(body: LoginRequest, request: Request):
    db = get_db()
    email = (body.email or "").lower().strip()
    ip = ratelimit.client_ip(request)
    fkey = f"login:{ip}:{email}"

    # Rate-limit: blokir sementara bila kegagalan beruntun melampaui ambang (RC-10: persisten).
    if await ratelimit.failure_count_db(db, fkey, _LOGIN_FAIL_WINDOW) >= _LOGIN_FAIL_LIMIT:
        await record(db, actor={"name": email}, action="login_blocked", entity_type="auth",
                     entity_id=email, summary=f"Login diblokir sementara (rate-limit): {email} @ {ip}")
        raise HTTPException(status_code=429,
                            detail="Terlalu banyak percobaan masuk. Coba lagi beberapa menit.")

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        await ratelimit.note_failure_db(db, fkey, _LOGIN_FAIL_WINDOW)
        await record(db, actor={"name": email}, action="login_failed", entity_type="auth",
                     entity_id=email, summary=f"Login GAGAL: {email} @ {ip}")
        raise HTTPException(status_code=401, detail="Email atau kata sandi salah")

    if user.get("status") != "active":
        await record(db, actor=_actor(user), action="login_denied", entity_type="auth",
                     entity_id=user.get("id"), summary=f"Login ditolak (akun nonaktif): {email}")
        raise HTTPException(status_code=403, detail="Akun nonaktif, hubungi admin")

    # G7: migrasi transparan hash legacy -> bcrypt saat verifikasi berhasil.
    if needs_rehash(user.get("password_hash", "")):
        try:
            await db.users.update_one(
                {"id": user["id"]}, {"$set": {"password_hash": hash_password(body.password)}})
        except Exception:
            pass  # migrasi opsional; jangan gagalkan login

    await ratelimit.clear_failures_db(db, fkey)
    token = new_token()
    expires_dt = datetime.now(timezone.utc) + timedelta(days=_SESSION_DAYS)
    expires_at = expires_dt.isoformat()
    await db.sessions.insert_one(
        {"token": token, "user_id": user["id"], "created_at": now_iso(),
         "expires_at": expires_at, "expires_dt": expires_dt}  # RC-09: field Date utk TTL index
    )
    await record(db, actor=_actor(user), action="login", entity_type="auth",
                 entity_id=user.get("id"), summary=f"Login berhasil: {email} @ {ip}")
    user.pop("password_hash", None)  # jangan pernah kirim hash ke klien
    return {"token": token, "user": safe_doc(user)}


@router.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return user


@router.post("/auth/logout")
async def logout(authorization: str = Header(default=None)):
    db = get_db()
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        session = await db.sessions.find_one({"token": token})
        await db.sessions.delete_one({"token": token})
        if session:
            u = await db.users.find_one({"id": session.get("user_id")}, {"_id": 0})
            if u:
                await record(db, actor=_actor(u), action="logout", entity_type="auth",
                             entity_id=u.get("id"), summary=f"Logout: {u.get('email')}")
    return {"ok": True}

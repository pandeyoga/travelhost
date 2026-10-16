"""Buat/perbarui akun owner dari env OWNER_EMAIL/OWNER_PASSWORD (dijalankan di container backend).
Idempoten: bila email sudah ada, kata sandi & role diperbarui."""
import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from core_utils import hash_password, new_id, now_iso  # noqa: E402


async def main():
    email = (os.environ.get("OWNER_EMAIL") or "").strip().lower()
    password = os.environ.get("OWNER_PASSWORD") or ""
    if not email or len(password) < 8:
        print("OWNER_EMAIL/OWNER_PASSWORD belum diisi (min 8 karakter) — dilewati.")
        return 0
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    doc = {"name": os.environ.get("OWNER_NAME") or "Pemilik", "email": email,
           "password_hash": hash_password(password), "role": "owner", "status": "active"}
    existing = await db.users.find_one({"email": email})
    if existing:
        await db.users.update_one({"email": email}, {"$set": doc})
        print(f"Akun owner diperbarui: {email}")
    else:
        await db.users.insert_one({"id": new_id("usr"), "phone": "", "created_at": now_iso(), **doc})
        print(f"Akun owner dibuat: {email}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

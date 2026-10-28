"""services/share_links.py — siklus hidup tautan publik bertoken (SATU sumber kebenaran).

Dipakai oleh dua jenis share-link:
  * `trip_shares`     — tracking posisi armada 1 trip (/track/:token)
  * `schedule_shares` — jadwal keberangkatan read-only (/schedule/:token)

Aturan yang sama untuk keduanya (INV-22): token acak 24 byte, unik; tautan sah dipakai
publik hanya bila `revoked == false` dan belum kedaluwarsa (`expires_at` kosong = tanpa
batas waktu, hanya untuk jenis yang mengizinkannya). Status HTTP konsisten:
404 = token tak dikenal, 403 = dinonaktifkan, 410 = kedaluwarsa.
"""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from core_utils import now_iso
from services.geo import parse_iso


def new_token() -> str:
    return secrets.token_urlsafe(24)


def expiry_from_hours(hours, default: int, max_hours: int, allow_never: bool = False):
    """ISO kedaluwarsa dari jumlah jam (dibatasi 1..max_hours).

    `hours == 0` berarti TANPA batas waktu → None, hanya bila `allow_never`; selain itu
    kosong/0 memakai `default` (perilaku lama trip_shares).
    """
    if allow_never and hours is not None and int(hours) <= 0:
        return None
    h = min(max(int(hours or default), 1), max_hours)
    return (datetime.now(timezone.utc) + timedelta(hours=h)).isoformat()


def share_state(doc: dict) -> dict:
    """Tambahkan `expired` + `is_active` (dihitung, tidak disimpan)."""
    exp = parse_iso(doc.get("expires_at"))
    doc["expired"] = bool(exp and exp <= datetime.now(timezone.utc))
    doc["is_active"] = (not doc.get("revoked")) and not doc["expired"]
    return doc


async def resolve_public_share(collection, token: str, noun: str) -> dict:
    """Ambil tautan berdasarkan token untuk konsumsi publik; tolak bila tak sah.

    `noun` = kata benda di pesan galat (mis. "pelacakan", "jadwal").
    Akses yang lolos dicatat (`last_accessed_at`, `access_count`).
    """
    share = await collection.find_one({"token": token}, {"_id": 0}) if token else None
    if not share:
        raise HTTPException(status_code=404, detail=f"Tautan {noun} tidak ditemukan")
    if share.get("revoked"):
        raise HTTPException(status_code=403, detail=f"Tautan {noun} telah dinonaktifkan")
    if share_state(dict(share))["expired"]:
        raise HTTPException(status_code=410, detail=f"Tautan {noun} telah kedaluwarsa")
    await collection.update_one(
        {"id": share["id"]},
        {"$set": {"last_accessed_at": now_iso()}, "$inc": {"access_count": 1}},
    )
    return share


async def revoke(collection, share_id: str) -> dict:
    if not await collection.find_one({"id": share_id}, {"_id": 0, "id": 1}):
        raise HTTPException(status_code=404, detail="Tautan tidak ditemukan")
    await collection.update_one({"id": share_id}, {"$set": {"revoked": True, "revoked_at": now_iso()}})
    return share_state(await collection.find_one({"id": share_id}, {"_id": 0}))


async def delete(collection, share_id: str) -> dict:
    if not await collection.find_one({"id": share_id}, {"_id": 0, "id": 1}):
        raise HTTPException(status_code=404, detail="Tautan tidak ditemukan")
    await collection.delete_one({"id": share_id})
    return {"deleted": True, "id": share_id}

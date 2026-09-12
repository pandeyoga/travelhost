"""services/identity.py — Identity & Dedupe (Phase 9 / B4).

Normalisasi nomor telepon ke +62 (E.164 ringkas) + deduplikasi kontak.
Dipakai saat: pembuatan customer (manual), konversi lead/penawaran → customer,
dan auto-link lead ke customer yang sudah ada.

Aturan normalisasi:
  08xxxx        → +628xxxx
  62xxxx / 8xxx → +62xxxx
  selainnya     → "+" + digit
Kunci dedupe: phone_normalized (utama) → phone mentah → email.
"""
import re

from pymongo.errors import DuplicateKeyError

from core_utils import new_id, now_iso


def normalize_phone(phone) -> str:
    """Kembalikan nomor ter-normalisasi (+62…) atau "" bila tak valid."""
    if not phone:
        return ""
    digits = re.sub(r"[^0-9]", "", str(phone))
    if not digits:
        return ""
    if digits.startswith("62"):
        return "+" + digits
    if digits.startswith("0"):
        return "+62" + digits[1:]
    if digits.startswith("8"):
        return "+62" + digits
    return "+" + digits


async def find_customer_by_identity(db, phone=None, email=None):
    """Cari customer berdasarkan identitas (normalized → mentah → email)."""
    norm = normalize_phone(phone)
    if norm:
        c = await db.customers.find_one({"phone_normalized": norm}, {"_id": 0})
        if c:
            return c
    if phone:
        c = await db.customers.find_one({"phone": phone}, {"_id": 0})
        if c:
            return c
    if email:
        c = await db.customers.find_one({"email": email}, {"_id": 0})
        if c:
            return c
    return None


async def ensure_customer(db, *, name, phone="", email="", type="individual",
                          city="", address="", notes=""):
    """Dedupe-or-create. Return (customer, created: bool).

    Bila kontak sudah ada → kembalikan yang ada (backfill phone_normalized/email
    bila masih kosong). Bila belum → buat baru dengan phone_normalized terisi.
    """
    existing = await find_customer_by_identity(db, phone=phone, email=email)
    if existing:
        patch = {}
        norm = existing.get("phone_normalized") or normalize_phone(existing.get("phone") or phone)
        if norm and not existing.get("phone_normalized"):
            patch["phone_normalized"] = norm
        if email and not existing.get("email"):
            patch["email"] = email
        if patch:
            await db.customers.update_one({"id": existing["id"]}, {"$set": patch})
            existing.update(patch)
        return existing, False

    doc = {
        "id": new_id("cus"), "name": (name or "Customer").strip(),
        "phone": phone or "", "phone_normalized": normalize_phone(phone),
        "email": email or "", "type": type or "individual", "city": city or "",
        "address": address or "", "total_trips": 0, "lifetime_value": 0.0,
        "notes": notes or "", "created_at": now_iso(),
    }
    try:
        await db.customers.insert_one(doc)
    except DuplicateKeyError:
        # ID-RACE: request paralel lain memenangkan pembuatan utk nomor ter-normalisasi yang sama.
        # Ambil pemenangnya (idempoten dedupe) alih-alih membuat duplikat / melempar 500.
        norm = normalize_phone(phone)
        winner = await db.customers.find_one({"phone_normalized": norm}, {"_id": 0}) if norm else None
        if winner:
            return winner, False
        raise
    return doc, True

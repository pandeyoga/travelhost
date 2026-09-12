"""core_utils.py — helper bersama (single source of truth).

- new_id(prefix)   : UUID string berprefiks (usr_, veh_, bk_, ...).
- now_iso()        : timestamp ISO-8601 UTC.
- new_token()      : session token berprefiks 'sess_'.
- hash_password()  : bcrypt (E0/G7). verify_password() mendukung bcrypt + legacy SHA256.
- needs_rehash()   : True bila hash lama (non-bcrypt) -> migrasi transparan saat login.
- safe_doc()       : strip _id + password_hash, koersi ObjectId/datetime -> string.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timezone

import bcrypt

try:
    from bson import ObjectId
except Exception:  # pragma: no cover
    ObjectId = None

# Dipakai HANYA untuk verifikasi hash LEGACY (pra-E0) saat migrasi transparan.
_SALT = "travel-fleet::"
_SENSITIVE = {"password_hash", "_id"}
_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def new_id(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def money(value) -> int:
    """Normalisasi nilai uang ke INTEGER rupiah (RC-11).

    Rupiah (IDR) tak punya sub-satuan; menyimpan bilangan bulat menghilangkan drift
    akumulasi float (mis. 0.1+0.2). None/''/invalid -> 0. Pembulatan ke rupiah terdekat.
    """
    try:
        return int(round(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def new_token() -> str:
    return f"sess_{secrets.token_hex(24)}"


def _pw_bytes(password: str) -> bytes:
    # bcrypt membatasi 72 byte input; truncate aman & deterministik.
    return (password or "").encode("utf-8")[:72]


def is_bcrypt_hash(hashed: str) -> bool:
    return isinstance(hashed, str) and hashed.startswith(_BCRYPT_PREFIXES)


def hash_password(password: str) -> str:
    """Hash kata sandi dengan bcrypt (cost default)."""
    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt()).decode("utf-8")


def _legacy_sha256(password: str) -> str:
    return hashlib.sha256((_SALT + (password or "")).encode("utf-8")).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """Verifikasi terhadap hash bcrypt; fallback ke hash legacy SHA256 (migrasi)."""
    if not hashed:
        return False
    if is_bcrypt_hash(hashed):
        try:
            return bcrypt.checkpw(_pw_bytes(password), hashed.encode("utf-8"))
        except Exception:
            return False
    # Legacy (pra-E0): SHA256 + salt statis. compare_digest = anti timing-attack.
    return secrets.compare_digest(_legacy_sha256(password), str(hashed))


def needs_rehash(hashed: str) -> bool:
    """True bila hash bukan bcrypt -> perlu di-upgrade saat login berhasil."""
    return not is_bcrypt_hash(hashed or "")


def _coerce(value):
    if ObjectId is not None and isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, dict):
        return {k: _coerce(v) for k, v in value.items() if k not in _SENSITIVE}
    if isinstance(value, list):
        return [_coerce(v) for v in value]
    return value


def safe_doc(doc):
    """Bersihkan dokumen Mongo agar JSON-serializable & tanpa field sensitif."""
    if doc is None:
        return None
    if isinstance(doc, list):
        return [safe_doc(d) for d in doc]
    if not isinstance(doc, dict):
        return _coerce(doc)
    return {k: _coerce(v) for k, v in doc.items() if k not in _SENSITIVE}

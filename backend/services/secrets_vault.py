"""services/secrets_vault.py — penyimpanan RAHASIA integrasi (Meta/Google/WhatsApp) yang aman.

Kenapa modul ini ada (keputusan user, fase F/E29): "saya belum ada apinya namun pastikan di
pengaturan saya bisa input api ini jadi tidak hardcoded termasuk juga untuk whatsapp".
Jadi kredensial TIDAK boleh berada di .env per-tenant maupun di kode; semuanya diisi dari UI
Pengaturan dan disimpan di koleksi `settings`.

Aturan yang dipaksa modul ini:
  1. Nilai rahasia SELALU disimpan terenkripsi (AES-256-GCM, envelope: nonce||ciphertext, base64)
     pada field bersufiks `_enc`. Plaintext tidak pernah ditulis ke MongoDB.
  2. Respons API TIDAK PERNAH memuat plaintext — hanya `<field>_set` (bool) + `<field>_masked`.
  3. Mengosongkan input di UI TIDAK menghapus rahasia (biarkan kosong = tetap pakai yang lama);
     penghapusan eksplisit memakai sentinel `__HAPUS__`.
  4. Kunci master dibaca dari env `SETTINGS_ENCRYPTION_KEY_B64` (32 byte base64). Bila belum ada,
     modul JELAS-JELAS gagal saat menyimpan (bukan menyimpan plaintext diam-diam).

Dijaga guardrail INV-SEC-01 (lihat memory/INVARIANTS.md).
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ENC_SUFFIX = "_enc"
DELETE_SENTINEL = "__HAPUS__"
_AAD = b"rahaza-settings-secret-v1"


class VaultError(RuntimeError):
    """Kunci enkripsi tidak tersedia / rusak — jangan pernah jatuh ke plaintext."""


def _key() -> bytes:
    raw = (os.environ.get("SETTINGS_ENCRYPTION_KEY_B64") or "").strip()
    if not raw:
        raise VaultError(
            "SETTINGS_ENCRYPTION_KEY_B64 belum diset di backend/.env — kredensial integrasi "
            "tidak dapat disimpan dengan aman. Buat kunci: python -c \"import base64,os;"
            "print(base64.b64encode(os.urandom(32)).decode())\""
        )
    try:
        key = base64.b64decode(raw)
    except Exception as exc:  # noqa: BLE001
        raise VaultError("SETTINGS_ENCRYPTION_KEY_B64 bukan base64 yang sah.") from exc
    if len(key) != 32:
        raise VaultError(f"SETTINGS_ENCRYPTION_KEY_B64 harus 32 byte (dapat {len(key)} byte).")
    return key


def vault_ready() -> bool:
    try:
        _key()
        return True
    except VaultError:
        return False


def encrypt(plain: str) -> str:
    nonce = os.urandom(12)
    blob = AESGCM(_key()).encrypt(nonce, (plain or "").encode(), _AAD)
    return base64.b64encode(nonce + blob).decode()


def decrypt(cipher_b64: str) -> str:
    if not cipher_b64:
        return ""
    raw = base64.b64decode(cipher_b64)
    return AESGCM(_key()).decrypt(raw[:12], raw[12:], _AAD).decode()


def mask(value: str) -> str:
    """Tampilkan bukti 'tersimpan' tanpa membocorkan nilai (aman untuk token pendek)."""
    v = value or ""
    if not v:
        return ""
    if len(v) <= 8:
        return "•" * len(v)
    return "••••••" + v[-4:]


def store_secrets(existing: dict, incoming: dict, fields) -> dict:
    """Gabungkan rahasia baru ke dokumen settings.

    - nilai kosong / tidak dikirim  -> pertahankan yang lama (UI menampilkan '••••' saja)
    - nilai DELETE_SENTINEL         -> hapus rahasia
    - selain itu                    -> enkripsi & simpan
    """
    out = dict(existing or {})
    for f in fields:
        if f not in (incoming or {}):
            continue
        raw = incoming.get(f)
        val = "" if raw is None else str(raw).strip()
        if not val:
            continue
        if val == DELETE_SENTINEL:
            out.pop(f + ENC_SUFFIX, None)
            continue
        out[f + ENC_SUFFIX] = encrypt(val)
    # jaring pengaman: jangan pernah biarkan plaintext ikut tersimpan
    for f in fields:
        out.pop(f, None)
    return out


def read_secret(doc: dict, field: str) -> str:
    enc = (doc or {}).get(field + ENC_SUFFIX)
    if not enc:
        return ""
    try:
        return decrypt(enc)
    except Exception:  # noqa: BLE001
        # kunci berubah / data rusak: laporkan kosong agar pemanggil menandai integrasi non-aktif,
        # JANGAN melempar agar endpoint tidak 5xx (INV-5XX-01).
        return ""


def public_view(doc: dict, fields) -> dict:
    """Bentuk aman untuk dikirim ke frontend: tanpa ciphertext, tanpa plaintext."""
    out = {k: v for k, v in (doc or {}).items() if not k.endswith(ENC_SUFFIX)}
    out.pop("_id", None)
    for f in fields:
        secret = read_secret(doc, f)
        out[f + "_set"] = bool((doc or {}).get(f + ENC_SUFFIX))
        out[f + "_masked"] = mask(secret)
        out.pop(f, None)
    return out


def secrets_bundle(doc: dict, fields) -> dict:
    """Plaintext untuk dipakai INTERNAL backend saja (memanggil API platform)."""
    return {f: read_secret(doc, f) for f in fields}

"""services/pii.py — normalisasi & hashing data pribadi untuk platform iklan (SSOT tunggal).

Mengapa modul terpisah: Meta dan Google MEMINTA bentuk yang BERBEDA untuk data yang sama, dan
salah normalisasi = match rate jeblok tanpa error apa pun (gagal senyap paling mahal di iklan).

  - Email  : trim + lowercase, lalu SHA-256 hex. Kanonikalisasi Gmail (buang titik & +tag)
             OPSIONAL karena bukan aturan wajib Google/Meta; dipakai hanya bila diminta.
  - Telepon: Meta  -> digit E.164 TANPA '+'  (mis. 6281234567890)
             Google -> E.164 DENGAN '+'      (mis. +6281234567890)
             Nomor Indonesia '08xx' dinormalkan ke '62 8xx' lebih dulu.
  - Click ID (gclid/fbclid/ctwa_clid) TIDAK BOLEH di-hash — itu penanda klik, bukan PII.

Dipakai oleh `services/conversions.py` (CAPI + Data Manager) dan `services/audiences.py`
(Custom Audience + Customer Match). Dijaga guardrail INV-SEC-02.
"""
import hashlib
import re

DEFAULT_CC = "62"  # Indonesia
_GMAIL = ("gmail.com", "googlemail.com")


def sha256_hex(value: str) -> str:
    """SHA-256 hex dari string yang SUDAH dinormalkan (jangan panggil pada nilai mentah)."""
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def normalize_email(value: str, *, canonicalize_gmail: bool = False) -> str:
    email = (value or "").strip().lower()
    if not email or "@" not in email:
        return ""
    if canonicalize_gmail:
        local, _, domain = email.partition("@")
        if domain in _GMAIL:
            local = local.split("+", 1)[0].replace(".", "")
            email = f"{local}@{domain}"
    return email


def phone_digits(value: str, *, cc: str = DEFAULT_CC) -> str:
    """Digit E.164 tanpa '+'. '' bila tidak mungkin dinormalkan (jangan kirim sampah)."""
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = cc + digits[1:]
    elif not digits.startswith(cc) and len(digits) <= 11:
        # nomor lokal tanpa awalan 0 (mis. 81234567890) -> tambahkan kode negara
        digits = cc + digits
    return digits if 8 <= len(digits) <= 15 else ""


def phone_e164(value: str, *, cc: str = DEFAULT_CC) -> str:
    digits = phone_digits(value, cc=cc)
    return f"+{digits}" if digits else ""


def hash_email(value: str, *, canonicalize_gmail: bool = False) -> str:
    email = normalize_email(value, canonicalize_gmail=canonicalize_gmail)
    return sha256_hex(email) if email else ""


def hash_phone_meta(value: str, *, cc: str = DEFAULT_CC) -> str:
    digits = phone_digits(value, cc=cc)
    return sha256_hex(digits) if digits else ""


def hash_phone_google(value: str, *, cc: str = DEFAULT_CC) -> str:
    e164 = phone_e164(value, cc=cc)
    return sha256_hex(e164) if e164 else ""


def digits_only(value: str) -> str:
    """Customer ID Google Ads WAJIB tanpa tanda hubung (123-456-7890 -> 1234567890)."""
    return re.sub(r"\D", "", str(value or ""))

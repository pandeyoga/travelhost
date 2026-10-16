#!/usr/bin/env python3
"""INV-SEC-02 — Rahasia integrasi & PII tidak boleh bocor keluar server.

Kelas bug yang dicegah: token iklan bernilai uang (bisa dipakai membelanjakan budget) dan data
pelanggan. Kebocoran biasanya terjadi karena kelalaian kecil: mengembalikan dict konfigurasi
mentah dari endpoint, menuliskan payload berisi token ke log, atau menaruh ID/kunci di kode.

Penjaga STATIK memastikan:
  1. Router TIDAK mengembalikan bundel rahasia (`secrets_bundle(...)`, `_secrets`) ke klien.
  2. Endpoint konfigurasi memakai `vault.public_view` (bentuk ter-mask `••••1234`).
  3. Endpoint publik pelacakan hanya memuat allowlist ID publik (tidak menyebut token/secret).
  4. Tidak ada `logger.*` yang mencetak `access_token`/`app_secret`/`refresh_token`.
  5. Rahasia tidak di-hardcode di services iklan (harus dari vault/UI).
  6. PII yang dikirim ke platform selalu lewat helper hash `services/pii.py`
     (kecuali click id — memang bukan PII dan tidak boleh di-hash).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, Guard  # noqa: E402

SECRET_WORDS = ("access_token", "app_secret", "oauth_refresh_token", "developer_token",
                "system_user_token", "page_access_token")
HARDCODE_PATTERNS = (
    (r'access_token\s*=\s*["\'][A-Za-z0-9_\-]{20,}["\']', "access_token hardcoded"),
    (r'EAA[A-Za-z0-9]{20,}', "token Meta (EAA...) hardcoded"),
    (r'["\']1//[A-Za-z0-9_\-]{20,}["\']', "refresh token Google (1//...) hardcoded"),
)


def read(path):
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def main() -> int:
    g = Guard("INV-SEC-02", "Rahasia integrasi & PII tidak bocor (respons, log, hardcode)")
    routers = sorted((BACKEND / "routers").glob("*.py"))
    services = sorted((BACKEND / "services").glob("*.py"))

    # (1) router tidak mengembalikan bundel rahasia
    for path in routers:
        text = read(path)
        for line_no, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if re.match(r"return\b", stripped) and ("secrets_bundle" in stripped or '"_secrets"' in stripped
                                                    or "_secrets}" in stripped):
                g.bump()
                g.add(f"routers/{path.name}:{line_no} mengembalikan bundel rahasia ke klien → "
                      f"token bocor ke browser.")
        g.bump()

    # (2) endpoint konfigurasi memakai bentuk ter-mask
    marketing = read(BACKEND / "routers" / "marketing.py")
    g.bump()
    if "vault.public_view" not in marketing:
        g.add("routers/marketing.py tidak memakai vault.public_view untuk respons konfigurasi → "
              "risiko mengirim ciphertext/plaintext rahasia ke browser.")

    # (3) endpoint publik pelacakan bebas kata rahasia
    public_block = ""
    if "public_tracking_config" in marketing:
        public_block = marketing.split("async def public_tracking_config", 1)[1].split("\nasync def", 1)[0]
    g.bump()
    for word in SECRET_WORDS:
        if word in public_block:
            g.add(f"/api/public/tracking-config menyebut '{word}' → endpoint publik tidak boleh "
                  f"memuat rahasia (allowlist field wajib ketat).")

    # (4) log tidak mencetak rahasia
    for path in routers + services:
        text = read(path)
        for line_no, line in enumerate(text.splitlines(), 1):
            if "logger." not in line:
                continue
            for word in SECRET_WORDS:
                if word in line:
                    g.bump()
                    g.add(f"{path.parent.name}/{path.name}:{line_no} mencetak '{word}' ke log → "
                          f"rahasia berpotensi tersimpan di berkas log.")
        g.bump()

    # (5) tidak ada rahasia hardcoded di modul iklan
    for name in ("meta_ads.py", "google_ads.py", "conversions.py", "integrations.py",
                 "audiences.py", "lead_ads.py"):
        text = read(BACKEND / "services" / name)
        for pattern, label in HARDCODE_PATTERNS:
            g.bump()
            if re.search(pattern, text):
                g.add(f"services/{name}: {label} → kredensial WAJIB dari vault/UI, bukan kode.")

    # (6) PII ke platform lewat helper hash; click id TIDAK di-hash
    conversions = read(BACKEND / "services" / "conversions.py")
    g.bump()
    if not re.search(r"pii\.hash_email", conversions):
        g.add("services/conversions.py tidak memakai pii.hash_email → email berisiko dikirim mentah.")
    g.bump()
    if re.search(r"hash_\w*\(\s*ident\[[\"']ctwa_clid", conversions) or \
       re.search(r"sha256_hex\(\s*ident\[[\"']ctwa_clid", conversions):
        g.add("services/conversions.py men-hash ctwa_clid → click id BUKAN PII dan bila di-hash "
              "atribusi Klik-ke-WhatsApp jadi tidak cocok (konversi tidak terhitung).")
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())

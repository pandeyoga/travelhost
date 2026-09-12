#!/usr/bin/env python3
"""INV-AUTH-01 — Setiap endpoint router WAJIB menegakkan autentikasi (via FastAPI Depends).

Kelas bug dicegah: **endpoint bocor tanpa login** (mis. data bisnis/master terekspos publik,
atau aksi mutasi tanpa auth). Di stack ini auth ditegakkan DEKLARATIF lewat dependency:
  - `Depends(get_current_user)`                 → minimal login
  - `Depends(require_role(...))` / `require_section(...)` → login + otorisasi
  - `Depends(<VAR>)` dgn `VAR = require_role(...)`/`require_section(...)` di level modul

STATIK (tak butuh backend): tiap `@router.<m>("path")` harus punya salah satu enforcer di
signature-nya. Endpoint yang benar-benar publik didaftar EKSPLISIT di PUBLIC_ENDPOINTS /
PUBLIC_FILES + alasan (allowlist ber-justifikasi) — tak ada yang lolos diam-diam.

Melanggar → MERAH: sebut file, `METHOD /path`, dan sarannya.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, Guard  # noqa: E402

ROUTERS = BACKEND / "routers"
AUTH_FUNCS = ("get_current_user", "require_role", "require_section")

# Endpoint publik SAH (file, METHOD, path-decorator) → alasan.
PUBLIC_ENDPOINTS = {
    ("auth.py", "POST", "/auth/login"): "gerbang login — wajib publik",
    ("auth.py", "POST", "/auth/logout"): "idempotent; hanya hapus sesi milik token yang dibawa",
    ("gps.py", "POST", "/webhook"): "ingest GPS device (auth via device/IP, bukan sesi)",
    ("whatsapp.py", "GET", "/wa/webhook"): "verifikasi webhook Meta (hub.challenge)",
    ("whatsapp.py", "POST", "/wa/webhook"): "callback Meta (diverifikasi via verify_token/signature)",
    ("whatsapp.py", "POST", "/wa/openwa-webhook"):
        "callback sidecar OpenWA LOKAL (proses Node di mesin sama, tanpa sesi user) — dijaga "
        "perbandingan key rahasia (env OPENWA_API_KEY) pada query string; fail-closed bila env "
        "kosong/key salah -> 403. Payload hanya memicu handle_inbound (jalur sama dgn webhook Meta).",
    ("seo.py", "GET", "/sitemap.xml"): "artefak SEO — WAJIB terbaca crawler (Google/Bing) tanpa login; hanya URL publik",
    ("seo.py", "GET", "/robots.txt"): "artefak SEO — WAJIB terbaca crawler tanpa login; tak memuat data privat",
    ("site_pages.py", "GET", "/public/pages/{slug}"):
        "dibaca browser pengunjung ANONIM untuk merakit halaman publik (home/about/contact) dari "
        "Page Builder CMS. Hanya mengembalikan section ENABLED + override teks/gambar yang memang "
        "ditayangkan; slug di luar PAGE_DEFS → 404. Tidak ada data privat/kredensial di dokumen ini.",
    ("marketing.py", "GET", "/public/tracking-config"):
        "dibaca browser pengunjung ANONIM untuk memuat Pixel/Google tag. Allowlist field KETAT: hanya "
        "ID publik (pixel_id, ga4_measurement_id, ads_conversion_id, label konversi) + setelan banner "
        "consent. Token/app secret TIDAK PERNAH disertakan (dijaga INV-TRACK-01 + POC test_core_ads).",
    ("ads_manage.py", "GET", "/public/webhooks/meta/leads"):
        "verifikasi langganan webhook Meta Lead Ads (hub.challenge) — Meta memanggil tanpa sesi; "
        "dijaga perbandingan `hub.verify_token` terhadap rahasia tersimpan (fail-closed bila kosong).",
    ("ads_manage.py", "POST", "/public/webhooks/meta/leads"):
        "callback Meta Lead Ads — Meta memanggil tanpa sesi. WAJIB lolos HMAC X-Hub-Signature-256 "
        "atas RAW body memakai app secret tersimpan (tanpa app secret / tanda tangan salah -> 403), "
        "lalu dideduplikasi via unique index leadgen_id (services/lead_ads.py, POC test_core_ads_f3).",
}
# File yang SELURUH endpoint-nya publik by design → alasan.
PUBLIC_FILES = {
    "public.py": "API situs publik (fleet/destinasi/artikel/quotation/booking/track/chat)",
    "booking_public.py":
        "alur PEMESANAN ONLINE untuk pengunjung anonim (cari ketersediaan → harga server → "
        "buat pesanan → unggah bukti DP → cek status). Tidak ada akun pelanggan by design; "
        "akses per-pesanan dijaga token acak 24 byte (`bookings.public_token`) atau kombinasi "
        "kode booking + nomor WhatsApp, plus rate-limit per IP & honeypot. Tidak satu pun "
        "endpoint di sini membaca data pelanggan lain atau menerima harga dari klien "
        "(harga selalu dihitung ulang server — dijaga INV-BOOK-02).",
}

DEC_RE = re.compile(r'@router\.(get|post|patch|put|delete)\(\s*["\']([^"\']*)["\']')
DEF_RE = re.compile(r'^\s*(?:async\s+)?def\s')


def _signature(lines, dec_idx):
    """Teks decorator + header fungsi (params multiline via balancing kurung)."""
    n = len(lines)
    j = dec_idx
    while j < n and not DEF_RE.match(lines[j]):
        j += 1
        if j - dec_idx > 12:
            return "\n".join(lines[dec_idx:j])
    seg, depth, started, k = list(lines[dec_idx:j]), 0, False, j
    while k < n:
        seg.append(lines[k])
        depth += lines[k].count("(") - lines[k].count(")")
        if "(" in lines[k]:
            started = True
        if started and depth <= 0:
            break
        k += 1
        if k - j > 100:
            break
    return "\n".join(seg)


def _auth_names(text):
    names = set(AUTH_FUNCS)
    for m in re.finditer(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:require_role|require_section)\s*\(', text, re.M):
        names.add(m.group(1))
    return names


def _enforced(sig, names):
    return any(m.group(1) in names for m in re.finditer(r'Depends\(\s*([A-Za-z_][A-Za-z0-9_]*)', sig))


def main() -> int:
    g = Guard("INV-AUTH-01", "Tiap endpoint router menegakkan auth (kecuali PUBLIC allowlist)")
    n_endpoints = n_public = 0
    for fp in sorted(ROUTERS.glob("*.py")):
        if fp.name == "__init__.py":
            continue
        text = fp.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        names = _auth_names(text)
        public_file = fp.name in PUBLIC_FILES
        for i, ln in enumerate(lines):
            m = DEC_RE.search(ln)
            if not m:
                continue
            method, path = m.group(1).upper(), m.group(2)
            n_endpoints += 1
            if public_file or (fp.name, method, path) in PUBLIC_ENDPOINTS:
                n_public += 1
                continue
            g.bump()
            if not _enforced(_signature(lines, i), names):
                g.add(f"{fp.name}: `{method} {path}` TIDAK menegakkan auth "
                      f"(Depends get_current_user/require_role/require_section) → dapat diakses TANPA login. "
                      f"Tambah dependency auth, atau daftarkan di PUBLIC_ENDPOINTS/PUBLIC_FILES bila memang publik.")
    print(f"    Endpoint dipindai: {n_endpoints} | publik (allowlist): {n_public} | ber-auth wajib: {n_endpoints - n_public}")
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())

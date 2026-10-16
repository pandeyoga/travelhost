#!/usr/bin/env python3
"""INV-QUALITY-01 — Kualitas kerja minimal AI (anti "low-effort / lapisan luar saja").

Kelas masalah dicegah: AI/kontributor menganggap ringan instruksi lalu meninggalkan kerja
DANGKAL yang lolos ke produksi: endpoint stub, error ditelan senyap, rahasia hardcoded, URL
backend hardcoded (bikin deploy jebol), atau sisa debug. Gate ini memaksa bukti kerja nyata.

Kebijakan (keputusan owner):
  • BLOCKING (MERAH) untuk pelanggaran BERAT:
      - `raise NotImplementedError` di ENDPOINT router (route belum diimplementasi = fitur bohong).
      - Penelan error senyap: `except ...: pass` (tanpa log/handle) di kode produksi.
      - Rahasia hardcoded (sk-, AKIA, AIza, ghp_, xox?-, PRIVATE KEY) di kode.
      - URL backend hardcoded di frontend/src (`http://localhost`, `*.preview.emergentagent.com`,
        `127.0.0.1`) atau `mongodb://` literal di backend (harus dari ENV).
  • ADVISORY (tak mem-fail, hanya laporan): TODO/FIXME/XXX/HACK, `console.log`/`debugger`,
      `print(` di router/service, `NotImplementedError` di luar router (mis. abstract base — sah).

Pengecualian sah didaftar EKSPLISIT di SEVERE_ALLOW + alasan (allowlist ber-justifikasi).
STATIK murni (tak butuh backend). Melanggar berat → MERAH: sebut file:baris + sinyalnya.
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from _common import Guard, ROOT, BACKEND, G, Y, X  # noqa: E402

FRONTEND_SRC = ROOT / "frontend" / "src"

# Pengecualian BERAT yang sah: (substring-relpath, signal_id) -> alasan.
SEVERE_ALLOW = {
    # (contoh) ("services/foo.py", "swallow"): "alasan…",
}

SECRET_RES = [
    (re.compile(r'sk-[A-Za-z0-9]{16,}'), "OpenAI-style key"),
    (re.compile(r'AKIA[0-9A-Z]{16}'), "AWS access key"),
    (re.compile(r'AIza[0-9A-Za-z_\-]{30,}'), "Google API key"),
    (re.compile(r'ghp_[A-Za-z0-9]{30,}'), "GitHub token"),
    (re.compile(r'xox[baprs]-[A-Za-z0-9-]{10,}'), "Slack token"),
    (re.compile(r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----'), "private key"),
]
FE_URL_RE = re.compile(r'https?://localhost|https?://127\.0\.0\.1|https?://[a-z0-9-]+\.preview\.emergentagent\.com')
MONGO_LITERAL_RE = re.compile(r'["\']mongodb(?:\+srv)?://')
# SEVERE swallow = bare/`Exception`/`BaseException` (telan SEMUA). Specific-exception → advisory.
BARE_SWALLOW_RE = re.compile(r'^\s*except\s*(?:Exception|BaseException)?\s*(?:as\s+\w+)?\s*:\s*$')
TEST_NAME_RE = re.compile(r'(^|_)test|_test\.py$|^conftest\.py$|^backend_test', re.I)


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def _allowed(rel: str, sig: str) -> bool:
    return any(sub in rel and s == sig for (sub, s), _ in SEVERE_ALLOW.items())


def _backend_prod_files():
    for p in BACKEND.rglob("*.py"):
        parts = set(p.parts)
        if "__pycache__" in parts or "tests" in parts or "scripts" in parts:
            continue
        if TEST_NAME_RE.search(p.name):  # kecualikan file test walau di backend/ (bukan produksi)
            continue
        yield p


def _frontend_prod_files():
    if not FRONTEND_SRC.exists():
        return
    for ext in ("*.js", "*.jsx"):
        for p in FRONTEND_SRC.rglob(ext):
            if ".test." in p.name or "__tests__" in str(p):
                continue
            yield p


def main() -> int:
    g = Guard("INV-QUALITY-01", "Kualitas kerja minimal AI (anti low-effort)")
    advisories = []

    # ---------- BACKEND produksi ----------
    for p in _backend_prod_files():
        rel = _rel(p)
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        in_router = ("routers" in p.parts)
        for i, ln in enumerate(lines):
            # SEVERE: NotImplementedError di endpoint router
            if "NotImplementedError" in ln:
                if in_router and not _allowed(rel, "not_impl"):
                    g.bump(); g.add(f"{rel}:{i+1} — `NotImplementedError` di router (endpoint belum diimplementasi). Implementasikan atau hapus route.")
                elif not in_router:
                    advisories.append(f"{rel}:{i+1} NotImplementedError (di luar router — cek apakah abstract base yg sah)")
            # penelan error: bare / `Exception` / `BaseException` + pass = SEVERE; specific = advisory
            if i + 1 < len(lines) and lines[i + 1].strip() == "pass" and re.match(r'^\s*except\b', ln):
                if BARE_SWALLOW_RE.match(ln):
                    if not _allowed(rel, "swallow"):
                        g.bump(); g.add(f"{rel}:{i+1} — `{ln.strip()}` + `pass`: menelan SEMUA error senyap. Log/handle/naikkan error yang tepat.")
                else:
                    advisories.append(f"{rel}:{i+1} `{ln.strip()}` + pass (specific — pastikan memang sengaja diabaikan)")
            # SEVERE: rahasia hardcoded
            for rx, what in SECRET_RES:
                if rx.search(ln):
                    g.bump(); g.add(f"{rel}:{i+1} — rahasia hardcoded ({what}). Pindahkan ke ENV/secret manager.")
            # SEVERE: mongodb:// literal (harus dari ENV)
            if MONGO_LITERAL_RE.search(ln) and "os.environ" not in ln and "getenv" not in ln:
                g.bump(); g.add(f"{rel}:{i+1} — koneksi `mongodb://` literal. Ambil dari `os.environ['MONGO_URL']`.")
            # ADVISORY
            if re.search(r'\b(TODO|FIXME|XXX|HACK)\b', ln):
                advisories.append(f"{rel}:{i+1} {re.search(r'(TODO|FIXME|XXX|HACK)', ln).group(1)}")
            if in_router and re.match(r'^\s*print\(', ln):
                advisories.append(f"{rel}:{i+1} print() debug di router")

    # ---------- FRONTEND produksi ----------
    for p in _frontend_prod_files():
        rel = _rel(p)
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, ln in enumerate(lines):
            if FE_URL_RE.search(ln) and not _allowed(rel, "fe_url"):
                g.bump(); g.add(f"{rel}:{i+1} — URL backend hardcoded di frontend. Pakai `process.env.REACT_APP_BACKEND_URL`.")
            for rx, what in SECRET_RES:
                if rx.search(ln):
                    g.bump(); g.add(f"{rel}:{i+1} — rahasia hardcoded ({what}) di frontend.")
            if re.search(r'\bconsole\.(log|debug)\(|\bdebugger\b', ln):
                advisories.append(f"{rel}:{i+1} console.log/debugger (sisa debug)")
            if re.search(r'\b(TODO|FIXME|XXX|HACK)\b', ln):
                advisories.append(f"{rel}:{i+1} {re.search(r'(TODO|FIXME|XXX|HACK)', ln).group(1)}")

    # ---------- ringkas advisory (tak mem-fail) ----------
    if advisories:
        print(f"    {Y}ADVISORY (tak mem-fail): {len(advisories)} catatan kerja-ringan{X}")
        for a in advisories[:15]:
            print(f"      · {a}")
        if len(advisories) > 15:
            print(f"      · … +{len(advisories) - 15} lagi")
    else:
        print(f"    {G}Advisory bersih (0 TODO/console.log/print debug).{X}")
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""selftest_media_runtime.py — SELF-TEST penjaga RUNTIME INV-MEDIA-04.

Penjaga runtime punya dua cara khas untuk berhenti melindungi TANPA satu pun error:

  1. **Lolos diam-diam saat backend tak terjangkau.** Kalau login gagal lalu penjaga
     `return 0` (atau di-SKIP oleh gate), hasilnya HIJAU untuk sesuatu yang tidak pernah diuji.
     Itu "hijau-palsu" paling mahal: dipercaya penuh, membuktikan nol.
  2. **Assertion yang tak pernah dijalankan.** Karena semua pemeriksaan bergantung respons HTTP,
     satu perubahan bentuk respons bisa membuat seluruh badan pemeriksaan dilewati (mis. keluar
     lebih awal) sementara penjaga tetap mencetak PASS.

Cara membuktikan keduanya TANPA merusak server nyata: jalankan penjaga terhadap **server tiruan**
yang dibuat di dalam proses ini.

  * Kasus A — alamat mati (port tertutup) → penjaga WAJIB MERAH dengan alasan "tidak bisa login",
    bukan hijau, bukan crash.
  * Kasus B — server tiruan yang **mengizinkan segalanya** (semua permintaan 200, tanpa RBAC,
    tanpa ETag, folder & impor palsu): ini persis rupa backend yang rusak total. Penjaga WAJIB
    MERAH dan menyebut kebocoran RBAC driver — bukti bahwa pemeriksaannya benar-benar dieksekusi.
  * Kasus C — server tiruan yang menolak SEMUA peran (403 untuk owner juga) → penjaga WAJIB MERAH
    (over-block juga kerusakan: pengguna yang berhak kehilangan akses).

Keluar 0 = penjaga runtime terbukti tak bisa hijau tanpa bukti.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(__file__))
from _common import B, C, G, R, ROOT, X, Y  # noqa: E402

GUARD = ROOT / "scripts" / "guardrails" / "verify_media_runtime.py"
ANSI = re.compile(r"\x1b\[[0-9;]*m")

OPENAPI = {"paths": {
    "/api/media": {"get": {}, "post": {}},
    "/api/media/folders": {"get": {}, "post": {}},
    "/api/media/folders/{folder_id}": {"patch": {}, "delete": {}},
    "/api/media/bulk-move": {"post": {}},
    "/api/media/bulk-delete": {"post": {}},
    "/api/media/import-legacy": {"post": {}},
    "/api/media/health": {"get": {}},
    "/api/media/{media_id}": {"get": {}, "patch": {}, "delete": {}},
    "/api/media/{media_id}/usage": {"get": {}},
    "/api/media/{media_id}/download": {"get": {}},
    "/api/media/{media_id}/replace": {"post": {}},
    "/api/media/{media_id}/crop": {"post": {}},
}}


class _Handler(BaseHTTPRequestHandler):
    """Server tiruan. `mode` diambil dari atribut kelas agar bisa diganti per kasus."""

    mode = "permissive"

    def log_message(self, *_a):  # senyapkan log HTTP
        return

    def _send(self, code, payload, extra=None):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _route(self):
        path = self.path.split("?")[0]
        if path == "/openapi.json":
            return self._send(200, OPENAPI)
        if path == "/api/auth/login":
            return self._send(200, {"token": "stub-token"})
        if self.mode == "deny_all":
            return self._send(403, {"detail": "ditolak"})
        # permissive: apa pun 200 — tanpa RBAC, tanpa ETag, tanpa data yang benar
        return self._send(200, {"id": "med_stub", "version": 1, "assets": [], "folders": [],
                                "imported": 1, "skipped": 0, "failed": 0, "moved": 1,
                                "moved_assets": 0, "deleted": 1, "total": 0})

    def do_GET(self):  # noqa: N802
        self._route()

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self._route()

    do_PATCH = do_POST
    do_PUT = do_POST
    do_DELETE = do_GET


def serve(mode):
    handler = type("H", (_Handler,), {"mode": mode})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def run_guard(base_url, timeout=180):
    env = dict(os.environ, GUARD_BASE_URL=base_url)
    proc = subprocess.run([sys.executable, str(GUARD)], capture_output=True, text=True,
                          env=env, timeout=timeout, cwd=str(ROOT))
    return proc.returncode, ANSI.sub("", proc.stdout + proc.stderr)


def main() -> int:
    print(f"{C}{B}== SELF-TEST INV-MEDIA-04 — penjaga runtime tak boleh hijau tanpa bukti =={X}")
    failures = []
    t0 = time.time()

    cases = [
        ("A alamat backend mati (port tertutup)", "http://127.0.0.1:9", None,
         "Tidak bisa login",
         "penjaga runtime HIJAU walau backend tak terjangkau = gate memberi izin lolos untuk "
         "sesuatu yang tidak pernah diuji."),
        ("B backend serba-izin (semua 200, tanpa RBAC)", None, "permissive",
         "BOCOR RBAC",
         "penjaga tidak benar-benar menguji penolakan driver → RBAC media bisa bocor total tanpa "
         "gate berubah warna."),
        ("C backend menolak semua peran (over-block)", None, "deny_all",
         "REGRESI: ops_admin",
         "penjaga tidak membedakan 'aman' dari 'semua orang terblokir' → pengguna yang berhak "
         "kehilangan Media Library tanpa gate menyadarinya."),
    ]

    for label, url, mode, expect, why in cases:
        srv = None
        try:
            if mode:
                srv, url = serve(mode)
            rc, out = run_guard(url)
            if rc == 0:
                failures.append(f"{label}: penjaga runtime TETAP HIJAU. Akibatnya: {why}")
                print(f"  {R}✗{X} {label} — penjaga HIJAU (lubang)")
            elif expect not in out:
                snippet = " | ".join(x.strip() for x in out.splitlines() if "✗" in x)[:260]
                failures.append(f"{label}: MERAH tetapi pesan tak memuat `{expect}` → sesi "
                                f"berikutnya bisa mengejar penyebab yang salah. Pesan: {snippet}")
                print(f"  {Y}~{X} {label} — MERAH tapi pesan tidak spesifik")
            else:
                print(f"  {G}✓{X} {label} — MERAH sesuai harapan")
        finally:
            if srv:
                srv.shutdown()

    print(f"{C}{B}-- ringkasan self-test INV-MEDIA-04 ({len(cases)} kasus, {time.time() - t0:.1f}s) --{X}")
    if not failures:
        print(f"{G}[PASS]{X} penjaga runtime terbukti MERAH pada backend mati, backend serba-izin, "
              f"dan backend yang memblokir semua peran.")
        return 0
    print(f"{R}[FAIL]{X} {len(failures)} lubang pada penjaga runtime INV-MEDIA-04:")
    for f in failures:
        print(f"  {R}✗{X} {f}")
    print(f"{Y}→ Perbaiki scripts/guardrails/verify_media_runtime.py; JANGAN melunakkan self-test.{X}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

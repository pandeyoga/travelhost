#!/usr/bin/env python3
"""INV-META-01 — Integritas registri guardrail (meta-penjaga anti "guardrail hilang antar-sesi").

Root cause utama bug berulang = konteks hilang antar-sesi + kode tumbuh. Guardrail hanya berguna
bila (a) BENAR-BENAR dijalankan gate, dan (b) TERDAFTAR di SSOT `memory/INVARIANTS.md`. Meta-penjaga
ini memaksa keduanya secara STATIK: setiap `scripts/guardrails/verify_*.py` WAJIB
  1) direferensikan di `scripts/gate.sh` (kalau tidak → tak pernah jalan = perlindungan mati diam-diam),
  2) mendeklarasikan INV-ID (via `Guard("INV-...")`),
  3) INV-ID-nya tercatat di tabel `memory/INVARIANTS.md`.
Juga sebaliknya: tiap INV-ID di INVARIANTS.md yang mengklaim punya penjaga file → file-nya harus ada.

Dengan begitu, sesi AI/kontributor baru TAK BISA menambah penjaga tanpa mendaftarkannya, atau
menghapus penjaga dari gate tanpa gate langsung MERAH.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import Guard, ROOT  # noqa: E402

GUARD_DIR = ROOT / "scripts" / "guardrails"
GATE = ROOT / "scripts" / "gate.sh"
INVARIANTS = ROOT / "memory" / "INVARIANTS.md"

# Penjaga yang sengaja TIDAK di-gate (mis. meta-penjaga eksperimental) — harus eksplisit + beralasan.
ALLOW_UNWIRED = set()  # kosong: semua penjaga wajib ter-wire.


def main() -> int:
    g = Guard("INV-META-01", "Integritas registri guardrail (semua penjaga ter-wire + terdaftar)")
    gate_txt = GATE.read_text(encoding="utf-8", errors="ignore") if GATE.exists() else ""
    inv_txt = INVARIANTS.read_text(encoding="utf-8", errors="ignore") if INVARIANTS.exists() else ""

    files = sorted(p for p in GUARD_DIR.glob("verify_*.py"))
    if not files:
        g.add("Tak ada file guardrail `verify_*.py` ditemukan — registri kosong (regresi?).")
        return g.finish()

    inv_ids_in_files = set()
    for f in files:
        name = f.name
        text = f.read_text(encoding="utf-8", errors="ignore")

        # (1) ter-wire di gate.sh?
        g.bump()
        if name not in gate_txt and name not in ALLOW_UNWIRED:
            g.add(f"{name}: TIDAK direferensikan di scripts/gate.sh → penjaga tak pernah dijalankan (perlindungan mati diam-diam).")

        # (2) deklarasikan INV-ID? (well-formed: INV-<X>-<digit>...; toleran "INV-RBAC-01/02/03").
        # Regex ketat agar tak tertipu teks contoh spt `Guard("INV-...")` di docstring.
        ids = re.findall(r'Guard\(\s*["\'](INV-[A-Z0-9]+-\d[0-9A-Z/\-]*)["\']', text)
        if not ids:
            ids = re.findall(r'\b(INV-[A-Z0-9]+-\d[0-9A-Z/\-]*)\b', text)
        raw_id = ids[0] if ids else None
        g.bump()
        if not raw_id:
            g.add(f"{name}: tak mendeklarasikan INV-ID via `Guard(\"INV-XXX-NN\")` (tak bisa dilacak ke SSOT).")
            continue
        # ambil komponen ID utama utk cek registrasi (mis. "INV-RBAC-01/02/03" -> "INV-RBAC-01").
        pm = re.match(r'(INV-[A-Z0-9]+-\d+)', raw_id)
        inv_id = pm.group(1) if pm else raw_id
        inv_ids_in_files.add(inv_id)

        # (3) INV-ID tercatat di INVARIANTS.md?
        g.bump()
        if inv_id not in inv_txt:
            g.add(f"{name}: INV-ID `{inv_id}` TIDAK terdaftar di memory/INVARIANTS.md (SSOT invariant).")

    # (4) sebaliknya: tiap INV-ID di INVARIANTS yang menyebut file guardrail → file harus ada.
    for inv_id, guard_file in re.findall(r'(INV-[A-Z0-9\-]+).*?`scripts/guardrails/(verify_[a-z0-9_]+\.py)`', inv_txt):
        g.bump()
        if not (GUARD_DIR / guard_file).exists():
            g.add(f"INVARIANTS.md: `{inv_id}` mengacu `scripts/guardrails/{guard_file}` yang TIDAK ada (file hilang?).")

    # (5) SELF-TEST penjaga juga wajib ter-wire + menyebut penjaga yang diuji.
    # Alasan: sejak Fase 3 self-test penjaga dibuat OTOMATIS (`selftest_*.py`) — bukti "penjaga ini
    # benar-benar MERAH saat bug disuntikkan". Bukti itu hanya bernilai bila ikut dijalankan gate.
    # Tanpa aturan ini, seseorang bisa menghapus satu baris di gate.sh dan seluruh pembuktian
    # anti-hijau-palsu lenyap tanpa jejak — persis pola kegagalan yang dilawan INV-META-01.
    selftests = sorted(GUARD_DIR.glob("selftest_*.py"))
    for f in selftests:
        g.bump()
        if f.name not in gate_txt:
            g.add(f"{f.name}: TIDAK direferensikan di scripts/gate.sh → pembuktian bahwa penjaga "
                  f"masih 'menggigit' tak pernah dijalankan (perlindungan terasa ada, sebenarnya tak teruji).")
        # Self-test boleh menguji BEBERAPA penjaga sekaligus (mis. satu ronde fitur yang
        # melahirkan 3 invariant). Bila begitu, file WAJIB mendeklarasikan `COVERS = [...]`
        # berisi nama berkas penjaga yang benar-benar diuji; tanpa deklarasi itu, aturan
        # penamaan 1:1 (`selftest_X.py` ↔ `verify_X.py`) tetap berlaku. Yang TIDAK berubah:
        # setiap penjaga yang diklaim diuji harus ADA dan harus ter-wire di gate.
        block = re.search(r"^COVERS\s*=\s*\[(.*?)\]",
                          f.read_text(encoding="utf-8", errors="ignore"), re.S | re.M)
        targets = re.findall(r'["\']([\w.]+\.py)["\']', block.group(1)) if block else []
        if not targets:
            targets = ["verify_" + f.name[len("selftest_"):]]
        for target in targets:
            g.bump()
            if not (GUARD_DIR / target).exists():
                g.add(f"{f.name}: penjaga yang diuji (`{target}`) tidak ada → self-test "
                      f"menguji berkas hantu.")
                continue
            g.bump()
            if target not in gate_txt:
                g.add(f"{f.name}: penjaga yang diuji (`{target}`) tidak ter-wire di gate.sh "
                      f"→ pembuktian ada, penjaganya tidak pernah jalan.")

    print(f"    Terpindai: {len(files)} penjaga + {len(selftests)} self-test | INV-ID: {sorted(inv_ids_in_files)}")
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
verify_delivery.py — ANTI-UNDER-DELIVERY GATE (Definition of Done)
==================================================================
Menagih JANJI di memory/DELIVERY_MANIFEST.md untuk fase AKTIF:
  D1  Tiap deliverable (doc/script/page/endpoint/collection) BENAR-BENAR ada.
  D2  ORPHAN ENDPOINT: backend punya endpoint tapi TIDAK dipakai frontend (fitur "yatim").
  D3  COMPLETENESS %: hitung P0 yang ada / total P0. Exit!=0 bila ada P0 kurang.
Resilient: endpoint/orphan di-skip rapi bila backend belum bisa di-import (Phase 0).
Usage: cd /app && python scripts/verify_delivery.py
Exit 0 = lengkap/skip. !=0 = UNDER-DELIVERY.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "memory" / "DELIVERY_MANIFEST.md"
FRONTEND_SRC = ROOT / "frontend" / "src"
DATA_MODEL = ROOT / "docs" / "03_DATA_MODEL.md"
G, Y, R, C, B, X = "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[1m", "\033[0m"
sys.path.insert(0, str(ROOT / "backend"))
state = {"p0_total": 0, "p0_ok": 0, "fail": 0, "warn": 0, "skip": 0}

# Endpoint yang SAH tidak pernah dipanggil kode frontend (BUKAN under-deliver) → alasan.
# Dikonsumsi langsung oleh agen eksternal (crawler/webhook), jadi heuristik "orphan" tak berlaku.
NON_FE_ENDPOINTS = {
    "/api/sitemap.xml": "artefak SEO dikonsumsi crawler (Google/Bing), bukan kode FE",
    "/api/robots.txt": "artefak SEO dikonsumsi crawler, bukan kode FE",
}


def parse_active_phase():
    if not MANIFEST.exists():
        return None, []
    text = MANIFEST.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"ACTIVE_PHASE:\s*(\S+)", text)
    active = m.group(1) if m else None
    items, capture = [], False
    for ln in text.splitlines():
        s = ln.strip()
        h = re.match(r"^#{2,4}\s+PHASE\s+(\S+)", s)
        if h:
            capture = (active is not None and h.group(1) == active)
            continue
        # batas section lain (heading non-phase atau pemisah) menghentikan capture
        if s.startswith("#") or s == "---" or s.startswith(">"):
            if capture:
                capture = False
            continue
        if capture:
            im = re.match(r"^- \[(P0|P1)\]\s+(\w+):\s+(.+?)\s*$", s)
            if im:
                items.append((im.group(1), im.group(2), im.group(3).strip()))
    return active, items


def file_exists(rel):
    return (ROOT / rel).exists()


def page_exists(identifier):
    # identifier mis. "features/app/Dashboard" → cari .jsx/.js
    for ext in (".jsx", ".js"):
        if (FRONTEND_SRC / f"{identifier}{ext}").exists():
            return True
    if FRONTEND_SRC.exists():
        stem = identifier.split("/")[-1].lower()
        for f in FRONTEND_SRC.rglob("*.jsx"):
            if f.stem.lower() == stem:
                return True
    return False


def canonical_collections():
    cols = set()
    if DATA_MODEL.exists():
        for ln in DATA_MODEL.read_text(errors="ignore").splitlines():
            h = re.match(r"^###\s+([a-z_]+)\s*$", ln.strip())
            if h:
                cols.add(h.group(1))
    return cols


def load_app():
    try:
        from server import app
        return app
    except Exception:
        return None


def backend_get_routes(app):
    out = []
    for r in app.routes:
        methods = getattr(r, "methods", set()) or set()
        path = getattr(r, "path", "")
        if path.startswith("/api") and methods:
            out.append(path)
    return sorted(set(out))


def fe_text():
    if not FRONTEND_SRC.exists():
        return ""
    buf = []
    for f in list(FRONTEND_SRC.rglob("*.jsx")) + list(FRONTEND_SRC.rglob("*.js")):
        if "/ui/" in str(f).replace("\\", "/"):
            continue
        buf.append(f.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(buf)


def mark(p, ok, kind, ident, note=""):
    if p == "P0":
        state["p0_total"] += 1
        if ok:
            state["p0_ok"] += 1
    if ok:
        print(f"  {G}[OK]{X}   [{p}] {kind}: {ident}")
    else:
        state["fail"] += 1 if p == "P0" else 0
        state["warn"] += 1 if p != "P0" else 0
        color = R if p == "P0" else Y
        print(f"  {color}[{'MISSING' if p=='P0' else 'todo'}]{X} [{p}] {kind}: {ident}  {color}{note}{X}")


def main():
    print(f"{B}{C}{'='*64}{X}\n{B}  DELIVERY GATE — anti under-deliver{X}\n{B}{C}{'='*64}{X}")
    active, items = parse_active_phase()
    if active is None and not items:
        print(f"{Y}  Manifest kosong / fase aktif tak ditemukan — skip.{X}")
        return 0
    if active is not None and not items:
        # ANTI FALSE-GREEN: dulu kondisi ini di-skip diam-diam (exit 0) sehingga SELURUH gate
        # delivery (D1/D1b/D2) tidak pernah jalan. Contoh nyata: ACTIVE_PHASE 'CMS-G10' tak pernah
        # cocok dgn heading '### PHASE CMS-G1..G10' → gate hijau tanpa memeriksa apa pun.
        print(f"{R}  DRIFT MANIFEST: ACTIVE_PHASE '{active}' tidak cocok dengan heading "
              f"'### PHASE <token>' mana pun (atau fase itu tak punya deliverable).{X}")
        print(f"{Y}  Perbaiki: samakan token ACTIVE_PHASE dengan token pada heading fase, "
              f"atau isi daftar deliverable fase tsb. SKIP bukan PASS.{X}")
        return 1
    print(f"  Fase aktif: {B}{active}{X}  —  {len(items)} deliverable\n")
    app = load_app()
    cols = canonical_collections()
    fe = fe_text()

    # D1 — existence
    print(f"{B}D1 — Deliverable ada?{X}")
    endpoint_items = []
    for p, kind, ident in items:
        if kind == "doc" or kind == "script":
            mark(p, file_exists(ident), kind, ident, "file tidak ada")
        elif kind == "page":
            if not FRONTEND_SRC.exists():
                state["skip"] += 1
                print(f"  {Y}[SKIP]{X} [{p}] page: {ident}  (frontend belum ada)")
                if p == "P0":
                    state["p0_total"] += 1  # tetap dihitung; kurang = under-deliver saat fase butuh FE
            else:
                mark(p, page_exists(ident), kind, ident, "halaman tidak ditemukan")
        elif kind == "collection":
            mark(p, ident in cols, kind, ident, "tidak terdaftar di 03_DATA_MODEL")
        elif kind == "endpoint":
            endpoint_items.append((p, ident))
        elif kind == "invariant":
            print(f"  {C}[note]{X} [{p}] invariant: {ident}  → ditegakkan verify_data_integrity.py")
        elif kind == "screenshot":
            print(f"  {C}[note]{X} [{p}] screenshot: {ident}  → verifikasi manual via preview URL")
        else:
            print(f"  {Y}[?]{X} [{p}] {kind}: {ident}")

    # endpoint existence
    if endpoint_items:
        print(f"\n{B}D1b — Endpoint terdaftar?{X}")
        if app is None:
            for p, ident in endpoint_items:
                state["skip"] += 1
                print(f"  {Y}[SKIP]{X} [{p}] endpoint: {ident}  (backend belum bisa di-import — Phase 0)")
        else:
            routes = backend_get_routes(app)
            for p, ident in endpoint_items:
                rx = re.compile("^" + re.sub(r"\{[^}]+\}", r"[^/]+", ident) + "$")
                ok = any(rx.match(rt) for rt in routes)
                mark(p, ok, "endpoint", ident, "route tidak terdaftar")

    # D2 — orphan endpoints (BE tanpa FE)
    print(f"\n{B}D2 — Orphan endpoint (backend tanpa UI)?{X}")
    routers_dir = ROOT / "backend" / "routers"
    INFRA_ROUTES = {"/api/", "/api/status"}
    if app is None:
        print(f"  {Y}[SKIP]{X} backend belum bisa di-import (Phase 0).")
    elif not routers_dir.exists():
        print(f"  {Y}[SKIP]{X} backend/routers belum ada (belum ada endpoint fitur).")
    elif not FRONTEND_SRC.exists():
        print(f"  {Y}[SKIP]{X} frontend belum ada.")
    else:
        routes = backend_get_routes(app)
        orphans = []
        for rt in routes:
            if rt in INFRA_ROUTES or rt in NON_FE_ENDPOINTS:
                continue
            # ambil segmen literal pertama setelah /api utk pencocokan kasar
            segs = [s for s in rt.split("/") if s and not s.startswith("{")]
            key = segs[1] if len(segs) > 1 else (segs[0] if segs else "")
            if key in ("auth", "status", ""):
                continue
            if key and key not in fe:
                orphans.append(rt)
        orphans = sorted(set(orphans))
        if orphans:
            state["fail"] += 1
            print(f"  {R}[FAIL]{X} {len(orphans)} endpoint tak dipakai FE (under-deliver):")
            for o in orphans[:20]:
                print(f"        {R}{o}{X}")
        else:
            print(f"  {G}[OK]{X} Tidak ada orphan endpoint.")

    # D3 — completeness
    pct = (state["p0_ok"] / state["p0_total"] * 100) if state["p0_total"] else 100.0
    print(f"\n{B}{'='*64}{X}")
    print(f"  P0 completeness: {B}{state['p0_ok']}/{state['p0_total']} ({pct:.0f}%){X}  | "
          f"{Y}WARN(P1) {state['warn']}{X} | {C}SKIP {state['skip']}{X} | {R}FAIL {state['fail']}{X}")
    if state["fail"] or pct < 100.0:
        print(f"  {R}{B}UNDER-DELIVERY — lengkapi deliverable P0 / hapus orphan sebelum klaim selesai.{X}\n")
        return 1
    print(f"  {G}{B}Delivery lengkap untuk fase aktif.{X}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
verify_api_contract.py — FE↔BE Contract Gate
=============================================
CHECK A: duplicate route (FastAPI pakai definisi TERAKHIR).
CHECK B: FE call → route backend terdaftar (cegah 404 senyap).
CHECK C: field yang DIBACA FE ada di respons BE (cegah label kosong tanpa error).
Resilient: skip dengan rapi bila backend belum bisa di-import / FE belum ada.
Usage: cd /app && python scripts/verify_api_contract.py
Exit 0 = lulus/skip. !=0 = ada ERROR.
"""
import argparse, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / "backend" / ".env")
except Exception: pass
sys.path.insert(0, str(ROOT / "backend"))
SRC = ROOT / "frontend" / "src"
API = os.environ.get("API_BASE", "http://localhost:8001").rstrip("/")
ADMIN = {"email": os.environ.get("ADMIN_EMAIL", "owner@demo.local"),
         "password": os.environ.get("ADMIN_PASS", "demo12345")}
G, Y, R, C, B, X = "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[1m", "\033[0m"
errors = 0; warns = 0


def err(m, d=""):
    global errors; errors += 1
    print(f"  {R}[ERROR]{X} {m}" + (f"\n          {R}{d}{X}" if d else ""))


def warn(m, d=""):
    global warns; warns += 1
    print(f"  {Y}[WARN]{X} {m}" + (f"  {Y}{d}{X}" if d else ""))


def ok(m): print(f"  {G}[OK]{X} {m}")


def load_app():
    try:
        from server import app
        return app
    except Exception as e:
        print(f"{Y}server.app belum bisa di-import ({e}) — skip (Phase 0).{X}")
        return None


def check_duplicate_routes(app):
    print(f"\n{C}{B}CHECK A — Duplicate route{X}")
    from collections import Counter, defaultdict
    seen = Counter(); names = defaultdict(list)
    for r in app.routes:
        for m in (getattr(r, "methods", set()) or set()):
            if m in ("HEAD", "OPTIONS"): continue
            key = (m, getattr(r, "path", "")); seen[key] += 1
            names[key].append(getattr(r, "name", "?"))
    dups = [(k, v) for k, v in seen.items() if v > 1]
    if dups:
        for (m, p), c in dups:
            err(f"Duplicate route {m} {p} (x{c}) — handler: {names[(m, p)]}",
                "Definisi pertama TIDAK dipanggil (filter bisa mati).")
    else:
        ok(f"Tidak ada duplicate route ({len(seen)} unik).")


def backend_routes(app):
    out = []
    for r in app.routes:
        methods = {m for m in (getattr(r, "methods", set()) or set()) if m not in ("HEAD", "OPTIONS")}
        path = getattr(r, "path", "")
        if path.startswith("/api") and methods: out.append((methods, path))
    return out


def route_regex(path):
    # toleran trailing-slash: '/api' dan '/api/' dianggap sama (hindari false-positive)
    base = re.sub(r"\{[^}]+\}", r"[^/]+", path).rstrip("/")
    return re.compile("^" + base + "/?$")


# M1 fix: FE memanggil API via `apiClient.<m>(...)` (axios instance, baseURL=`${BACKEND_URL}/api`),
# BUKAN `axios.<m>(...)`/`fetch(...)` langsung. Regex lama hanya menangkap axios/fetch backtick →
# 0 call terdeteksi → CHECK B lolos "palsu". Sekarang tangkap apiClient/axios (semua gaya kutip:
# `backtick`, "double", 'single') + fetch. Path apiClient relatif → di-prefix `/api` saat normalisasi.
FE_CALL_RE = re.compile(
    r'''(?P<client>apiClient|axios)\.(?P<method>get|post|patch|put|delete)\(\s*'''
    r'''(?P<q>[`"'])(?P<path>[^`"']*)(?P=q)'''
    r'''|(?P<fetch>fetch)\(\s*(?P<fq>[`"'])(?P<fpath>[^`"']*)(?P=fq)'''
)
QUERY_VAR_RE = re.compile(r'\$\{[a-zA-Z_]*(?:params|query|qs|search)\}', re.I)


def normalize_fe_path(raw, *, relative=False):
    p = QUERY_VAR_RE.sub("", raw.strip()).split("?")[0]
    p = p.replace("${API}", "/api").replace("${BACKEND_URL}/api", "/api").replace("${BACKEND_URL}", "")
    # M1: interpolasi yang MENEMPEL pada segmen (didahului non-'/') = query string yang dirakit
    # (mis. `const q = range ? \`?range=${range}\` : ""` → `/crm/rfm${q}`) → buang; sisakan base path.
    p = re.sub(r'(?<=[^/])\$\{[^}]+\}', '', p)
    # sisanya (didahului '/') = path-param dinamis → jadi {p}.
    p = re.sub(r"\$\{[^}]+\}", "{p}", p)
    p = re.sub(r"/{2,}", "/", p).rstrip("/") or "/"
    # apiClient baseURL sudah mengandung `/api` → path relatif ('/bookings') harus di-prefix.
    if relative and not p.startswith("/api"):
        p = "/api" + (p if p.startswith("/") else "/" + p)
    return p


def fe_calls():
    calls = []
    if not SRC.exists(): return calls
    for f in list(SRC.rglob("*.jsx")) + list(SRC.rglob("*.js")):
        if "/ui/" in str(f): continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in FE_CALL_RE.finditer(text):
            if m.group("client"):
                client = m.group("client")
                method = (m.group("method") or "get").upper()
                raw = m.group("path") or ""
            else:
                client = "fetch"
                method = "GET"
                raw = m.group("fpath") or ""
            if client == "apiClient":
                # path relatif ke baseURL `${BACKEND_URL}/api` → selalu API call.
                fe_path = normalize_fe_path(raw, relative=True)
            else:
                # axios/fetch langsung: hanya relevan bila menyebut /api atau ${API}.
                if "/api" not in raw and "${API}" not in raw:
                    continue
                fe_path = normalize_fe_path(raw)
            calls.append((method, fe_path, raw.strip(), f.relative_to(SRC)))
    return calls


def _segs(path):
    return [s for s in path.strip("/").split("/") if s != ""]


def seg_match(fe_path, be_path):
    """Cocokkan berbasis-segmen. `{p}` (var FE) atau `{param}` (var BE) = wildcard 1 segmen.
    Arity harus sama & segmen literal harus identik → tetap menangkap 404/typo pada prefix statik
    & panggilan salah-arity, tapi toleran pada segmen aksi dinamis (mis. `/{id}/${action}`)."""
    fe = _segs(fe_path); be = _segs(be_path)
    if len(fe) != len(be):
        return False
    for fseg, bseg in zip(fe, be):
        if fseg == "{p}":
            continue
        if bseg.startswith("{") and bseg.endswith("}"):
            continue
        if fseg != bseg:
            return False
    return True


def check_fe_routes(app):
    print(f"\n{C}{B}CHECK B — FE call → route backend terdaftar?{X}")
    be_paths = [p for _, p in backend_routes(app)]
    calls = fe_calls()
    if not calls:
        warn("Tidak ada FE call terdeteksi (frontend belum dibangun?)"); return
    bad = 0; seen = set()
    for method, fe_path, raw, src in calls:
        if fe_path in seen: continue
        if not any(seg_match(fe_path, bp) for bp in be_paths):
            seen.add(fe_path); bad += 1
            err(f"FE {fe_path} → TIDAK ada route backend cocok", f"src: {src} raw: {raw[:60]}")
    if bad == 0:
        ok(f"Semua {len(set(c[1] for c in calls))} path API FE cocok dengan backend ({len(calls)} call terdeteksi).")


# BINDINGS: file FE → endpoint → variabel objek. Tambah saat komponen membaca data API.
BINDINGS = []  # diisi seiring frontend dibangun (lihat docs/08 §1.5)


async def check_field_contract():
    print(f"\n{C}{B}CHECK C — Field FE ⊆ respons BE?{X}")
    if not BINDINGS:
        warn("Belum ada BINDINGS (frontend belum membaca data API) — skip."); return
    try:
        import httpx
    except ImportError:
        os.system("pip install httpx -q"); import httpx
    async with httpx.AsyncClient(follow_redirects=True) as client:
        r = await client.post(f"{API}/api/auth/login", json=ADMIN, timeout=20)
        token = r.json().get("token"); h = {"Authorization": f"Bearer {token}"}
        for bnd in BINDINGS:
            fpath = SRC / bnd["file"]
            if not fpath.exists(): warn(f"skip, file tak ada: {bnd['file']}"); continue
            text = fpath.read_text(errors="ignore")
            resp = await client.get(f"{API}{bnd['endpoint']}", headers=h, timeout=25)
            data = resp.json(); items = data if isinstance(data, list) else data.get("items", [])
            if not items: warn(f"{bnd['file']}: endpoint kosong — skip"); continue
            n = len(items); fields = set()
            for v in bnd["obj_vars"]:
                for m in re.finditer(rf"\b{re.escape(v)}\??\.([A-Za-z_][A-Za-z0-9_]*)", text):
                    fields.add(m.group(1))
            for fld in sorted(fields):
                if fld in {"map","filter","find","length","id","data"}: continue
                present = sum(1 for it in items if isinstance(it, dict) and fld in it)
                if present == 0:
                    (warn if fld in bnd.get("conditional", set()) else err)(
                        f"{bnd['file']}: FE baca `{bnd['obj_vars'][0]}.{fld}` tapi 0/{n} item BE punya")


async def amain(which):
    app = load_app()
    if app is None: return
    if which in (None, "A"): check_duplicate_routes(app)
    if which in (None, "B"): check_fe_routes(app)
    if which in (None, "C"): await check_field_contract()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--check", choices=["A", "B", "C"])
    args = ap.parse_args()
    print(f"{B}{C}{'='*64}{X}\n{B}  FE↔BE CONTRACT GATE  (API={API}){X}\n{B}{C}{'='*64}{X}")
    import asyncio; asyncio.run(amain(args.check))
    print(f"\n{B}{'='*64}{X}\n  {R}ERROR {errors}{X} | {Y}WARN {warns}{X}")
    if errors:
        print(f"  {R}{B}CONTRACT VIOLATION — FE & BE tidak sinkron.{X}\n"); return 1
    print(f"  {G}{B}FE↔BE CONTRACT OK.{X}\n"); return 0


if __name__ == "__main__":
    sys.exit(main())

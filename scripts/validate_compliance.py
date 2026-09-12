#!/usr/bin/env python3
"""
validate_compliance.py — Compliance Validator
=============================================
Jalankan sebelum mark task DONE. PASS/FAIL per check dengan detail actionable.
Usage:
  python3 scripts/validate_compliance.py
  python3 scripts/validate_compliance.py --quick
Exit 1 bila ada FAIL kritis.
"""
import re, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path("/app")
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend" / "src"
MAX_ROUTER, MAX_COMPONENT, MAX_UTILITY, MAX_CSS = 800, 500, 300, 400
G, Y, R, C, B, X = "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[1m", "\033[0m"
results = []


def ok(c, m): results.append(("PASS", c, m))
def warn(c, m): results.append(("WARN", c, m))
def fail(c, m): results.append(("FAIL", c, m))
def section(t): results.append(("INFO", "", f"{'='*58}")); results.append(("INFO", "", f"  {t}"))

CANONICAL = {"users","sessions","vehicles","drivers","customers","leads","conversations",
    "messages","bookings","trips","locations","trip_shares","payments","expenses","invoices",
    "notification_tasks","broadcasts","maintenance_records","destinations","articles",
    "testimonials","audit_logs","settings","user_onboarding","lead_activities","counters",
    "quotations","packages","promos","events","automation_rules","automation_runs",
    "segments","sequences","sequence_enrollments","campaigns","campaign_recipients","workshops","service_types","driver_payouts",
    "partners","subcharters","partner_settlements","booking_locks",
    # FASE F (E29+) Marketing & Ads — lihat docs/03_DATA_MODEL.md § Marketing
    "conversion_events","ads_accounts","ads_entities","ads_metrics_daily","ads_sync_runs",
    "ad_touches","audience_syncs","platform_leads","media_assets","landing_pages",
    # Pemesanan online publik — lihat docs/03_DATA_MODEL.md § Pemesanan Online
    "transfer_routes","payment_proofs",
    # INV-REF-02 batch 2: master titik jemput (relasi bookings.origin)
    "pickup_points",
    # INV-REF-02 batch 5: master kota (relasi customers.city & partners.city)
    "cities",
    # Page builder situs: urutan & override section halaman publik (home/about/contact)
    "site_pages",
    # CMS-CW2 (draft/jadwal, funnel ulasan, analitik konten) — docs/03_DATA_MODEL.md §7
    "content_previews","review_requests","content_stats",
    # CMS-CW3 (riwayat versi, tempat sampah, pengalihan URL) — docs/03_DATA_MODEL.md §8
    "content_versions","content_trash","content_redirects"}
FORBIDDEN = {"cars","armada","kendaraan","sopir","clients","pelanggan","orders","pesanan",
    "prospects","chats","gps","positions","cost","biaya","bills","tagihan","faktur",
    "reminders","blog","posts","config","staff","karyawan"}


def check_file_sizes():
    section("CHECK 1: FILE SIZE")
    any_fail = False
    rd = BACKEND / "routers"
    if rd.exists():
        for f in sorted(rd.glob("*.py")):
            n = len(f.read_text().splitlines())
            if n > MAX_ROUTER: fail("FILE_SIZE", f"{f.relative_to(ROOT)}: {n} > {MAX_ROUTER}"); any_fail = True
            elif n > MAX_ROUTER*0.8: warn("FILE_SIZE", f"{f.relative_to(ROOT)}: {n} (mendekati)")
    for fn in ["server.py","core_utils.py","dependencies.py","schemas.py",
               "schemas_landing.py","permissions_config.py"]:
        f = BACKEND / fn
        if f.exists() and len(f.read_text().splitlines()) > MAX_ROUTER:
            fail("FILE_SIZE", f"backend/{fn}: melebihi {MAX_ROUTER}"); any_fail = True
    if FRONTEND.exists():
        for f in sorted(list(FRONTEND.rglob("*.jsx")) + list(FRONTEND.rglob("*.js"))):
            if "node_modules" in str(f) or "/ui/" in str(f): continue
            n = len(f.read_text().splitlines())
            if n > MAX_COMPONENT: fail("FILE_SIZE", f"{f.relative_to(ROOT)}: {n} > {MAX_COMPONENT}"); any_fail = True
            elif n > MAX_COMPONENT*0.85: warn("FILE_SIZE", f"{f.relative_to(ROOT)}: {n} (mendekati)")
        for f in FRONTEND.glob("*.css"):
            if len(f.read_text().splitlines()) > MAX_CSS: warn("FILE_SIZE", f"{f.relative_to(ROOT)}: css > {MAX_CSS}")
    if not any_fail: ok("FILE_SIZE", "Semua file dalam batas")


def check_debug():
    section("CHECK 2: DEBUG STATEMENTS")
    found = []
    if FRONTEND.exists():
        for f in list(FRONTEND.rglob("*.js")) + list(FRONTEND.rglob("*.jsx")):
            if "node_modules" in str(f): continue
            for i, ln in enumerate(f.read_text(errors="ignore").splitlines(), 1):
                s = ln.strip()
                if s.startswith("//") or s.startswith("*"): continue
                if "console.log" in ln and "// ok" not in ln.lower():
                    found.append(f"{f.relative_to(ROOT)}:{i}")
    rd = BACKEND / "routers"
    if rd.exists():
        for f in rd.glob("*.py"):
            for i, ln in enumerate(f.read_text(errors="ignore").splitlines(), 1):
                if ln.strip().startswith("#"): continue
                if re.match(r"\s*print\s*\(", ln) and "# ok" not in ln.lower():
                    found.append(f"{f.relative_to(ROOT)}:{i}")
    if found:
        for it in found[:30]: warn("DEBUG", it)
    else: ok("DEBUG", "Tidak ada console.log/print debug")


def check_duplicate_endpoints():
    section("CHECK 3: DUPLICATE ENDPOINTS")
    emap = defaultdict(list)
    pat = re.compile(r'@router\.(get|post|put|patch|delete)\([\'"](.*?)[\'"]')
    # Prefix router WAJIB ikut dihitung. Tanpa itu pemeriksa ini memberi TEMUAN PALSU: rute admin
    # `/api/media/{id}` (routers/media.py, prefix "/api") dianggap sama dengan rute publik
    # `/api/public/media/{id}` (routers/public.py, prefix "/api/public") padahal keduanya URL yang
    # berbeda dengan aturan auth yang berbeda. Temuan palsu pada gate melatih orang mengabaikan
    # gate — itu lebih berbahaya daripada tidak punya gate.
    prefix_pat = re.compile(r'APIRouter\(\s*prefix\s*=\s*[\'"]([^\'"]*)[\'"]')
    rd = BACKEND / "routers"
    if rd.exists():
        for f in rd.glob("*.py"):
            src = f.read_text(errors="ignore")
            pm = prefix_pat.search(src)
            prefix = pm.group(1) if pm else ""
            for m in pat.finditer(src):
                emap[f"{m.group(1).upper()} {prefix}{m.group(2)}"].append(f.name)
    dups = {k: v for k, v in emap.items() if len(v) > 1}
    if dups:
        for e, fs in dups.items(): fail("DUPLICATE_ENDPOINT", f"{e} → {', '.join(fs)}")
    else: ok("DUPLICATE_ENDPOINT", f"Tidak ada duplikat ({len(emap)} endpoint)")


def check_forbidden_collections():
    section("CHECK 4: FORBIDDEN COLLECTION NAMES")
    found = []
    pat = re.compile(r'db\.([a-z_]+)')
    rd = BACKEND / "routers"
    if rd.exists():
        for f in rd.glob("*.py"):
            for col in set(pat.findall(f.read_text(errors="ignore"))):
                if col in FORBIDDEN: found.append((f.name, col))
    if found:
        for fn, col in found: fail("FORBIDDEN_COLLECTION", f"{fn}: db.{col} (lihat 03_DATA_MODEL.md)")
    else: ok("FORBIDDEN_COLLECTION", "Tidak ada nama koleksi terlarang")


def check_hardcoded():
    section("CHECK 5: HARDCODED VALUES")
    pats = [(r'localhost:8001', "localhost:8001"), (r'localhost:3000', "localhost:3000"),
            (r'[\'"]demo12345[\'"]', "password hardcoded")]
    found = []
    rd = BACKEND / "routers"
    if rd.exists():
        for f in rd.glob("*.py"):
            c = f.read_text(errors="ignore")
            for pat, desc in pats:
                if re.search(pat, c): found.append(f"{f.name}: {desc}")
    if found:
        for it in found: warn("HARDCODED", it)
    else: ok("HARDCODED", "Tidak ada hardcoded ID/URL di router")


def check_testids():
    section("CHECK 6: DATA-TESTID COVERAGE")
    if not FRONTEND.exists(): ok("TESTID", "frontend belum ada (skip)"); return
    total = 0; missing = []
    for f in FRONTEND.rglob("*.jsx"):
        if "/ui/" in str(f): continue
        c = f.read_text(errors="ignore"); n = c.count("data-testid"); total += n
        if "features/" in str(f) and n == 0 and ("<button" in c or "<Button" in c):
            missing.append(str(f.relative_to(ROOT)))
    if missing:
        for fn in missing: warn("TESTID", f"{fn}: tidak ada data-testid")
    else: ok("TESTID", f"Coverage OK (total {total} testid)")


def check_registry_sync():
    section("CHECK 7: ENTITY REGISTRY SYNC")
    pat = re.compile(r'db\.([a-z_]+)')
    actual = set()
    for d in [BACKEND / "routers", BACKEND / "services"]:
        if d.exists():
            for f in d.rglob("*.py"):
                actual |= set(pat.findall(f.read_text(errors="ignore")))
    sv = BACKEND / "server.py"
    if sv.exists(): actual |= set(pat.findall(sv.read_text(errors="ignore")))
    unreg = actual - CANONICAL - {"client", "command"}
    if unreg:
        for c in sorted(unreg): warn("REGISTRY", f"db.{c} dipakai tapi tak ada di 03_DATA_MODEL.md")
    else: ok("REGISTRY", f"Semua koleksi terdaftar ({len(actual)} dipakai)")


def check_required_docs():
    section("CHECK 8: REQUIRED DOCS")
    req = [ROOT/"plan.md", ROOT/"design_guidelines.md",
           ROOT/"memory"/"SESSION_LOG.md", ROOT/"memory"/"SESSION_HANDOFF.md"]
    for i in range(13):
        req.append(ROOT/"docs"/f"{i:02d}_*")
    docs_dir = ROOT / "docs"
    expected = ["00_INDEX","01_PRD","02_ARCHITECTURE","03_DATA_MODEL","04_API_CONTRACT",
                "05_NAVIGATION_MAP","06_UIUX_STANDARDS","07_ENGINEERING_GUARDRAILS",
                "08_FRONTEND_GUARDRAILS","09_ROADMAP","10_CODEBASE_MAP",
                "11_AGENT_OPERATING_PROTOCOL","12_SOP_AND_DELIVERY"]
    for name in expected:
        if docs_dir.exists() and list(docs_dir.glob(f"{name}.md")): ok("DOCS", f"docs/{name}.md")
        else: fail("DOCS", f"docs/{name}.md TIDAK ADA")
    for d in [ROOT/"plan.md", ROOT/"design_guidelines.md", ROOT/"memory"/"SESSION_LOG.md"]:
        if d.exists(): ok("DOCS", str(d.relative_to(ROOT)))
        else: warn("DOCS", f"{d.relative_to(ROOT)} belum ada")


def check_api_prefix():
    section("CHECK 9: API PREFIX (/api)")
    rd = BACKEND / "routers"
    if not rd.exists(): ok("API_PREFIX", "routers belum ada (skip)"); return
    issues = []
    pr = re.compile(r'APIRouter\(prefix=["\']([^\'"]+)["\']')
    for f in rd.glob("*.py"):
        c = f.read_text(errors="ignore")
        for m in pr.finditer(c):
            if not m.group(1).startswith("/api"): issues.append(f"{f.name}: prefix '{m.group(1)}'")
    if issues:
        for it in issues: warn("API_PREFIX", it)
    else: ok("API_PREFIX", "Semua router prefix /api")


def check_env():
    section("CHECK 10: ENV VARS")
    be = BACKEND / ".env"; fe = ROOT / "frontend" / ".env"
    if be.exists():
        c = be.read_text()
        ok("ENV", "backend/.env MONGO_URL") if "MONGO_URL" in c else fail("ENV", "backend/.env tanpa MONGO_URL")
    if fe.exists():
        c = fe.read_text()
        ok("ENV", "frontend/.env REACT_APP_BACKEND_URL") if "REACT_APP_BACKEND_URL" in c else fail("ENV", "frontend/.env tanpa REACT_APP_BACKEND_URL")


def main():
    quick = "--quick" in sys.argv
    check_file_sizes(); check_debug(); check_duplicate_endpoints(); check_forbidden_collections()
    if not quick:
        check_hardcoded(); check_testids(); check_registry_sync(); check_required_docs()
        check_api_prefix(); check_env()
    np = sum(1 for s,_,_ in results if s=="PASS"); nw = sum(1 for s,_,_ in results if s=="WARN")
    nf = sum(1 for s,_,_ in results if s=="FAIL")
    for s, c, m in results:
        if s == "INFO": print(f"{C}{m}{X}")
        elif s == "PASS": print(f"  {G}[PASS]{X} {m}")
        elif s == "WARN": print(f"  {Y}[WARN]{X} {m}")
        else: print(f"  {R}[FAIL]{X} {m}")
    print(f"\n{B}SUMMARY:{X} {G}PASS {np}{X} | {Y}WARN {nw}{X} | {R}FAIL {nf}{X}")
    return 1 if nf else 0


if __name__ == "__main__":
    sys.exit(main())

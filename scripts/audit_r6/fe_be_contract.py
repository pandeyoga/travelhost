#!/usr/bin/env python3
"""Round 6D — CORRECTED FE<->BE contract scanner.
The repo's verify_api_contract.py only matches `axios.<m>(` but the FE uses
`apiClient.<m>(` — so it detects 0 calls (false-green). This scanner detects
apiClient calls (template literals AND plain strings) and validates each path
against actual backend routes. Reports silent-404 risks (FE calls with no BE route).
READ-ONLY.
"""
import re, sys
from pathlib import Path
ROOT = Path("/app")
sys.path.insert(0, str(ROOT / "backend"))
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / "backend" / ".env")
except Exception: pass
from server import app
SRC = ROOT / "frontend" / "src"

def backend_routes():
    out = []
    for r in app.routes:
        methods = {m for m in (getattr(r, "methods", set()) or set()) if m not in ("HEAD", "OPTIONS")}
        path = getattr(r, "path", "")
        if path.startswith("/api") and methods:
            out.append((methods, path))
    return out

def route_regex(path):
    base = re.sub(r"\{[^}]+\}", r"[^/]+", path).rstrip("/")
    return re.compile("^" + base + "/?$")

# match apiClient.<method>(`...`) or apiClient.<method>("...") or ('...')
CALL_RE = re.compile(r'''apiClient\.(get|post|put|patch|delete)\(\s*([`"'])([^`"']+)\2''')

def normalize(raw):
    p = raw.strip().split("?")[0]
    p = re.sub(r"\$\{[^}]+\}", "X", p)   # template vars -> X
    if not p.startswith("/api"):
        if p.startswith("/"):
            p = "/api" + p if not p.startswith("/api") else p
    p = re.sub(r"/{2,}", "/", p).rstrip("/") or "/"
    return p

def main():
    routes = backend_routes()
    compiled = [(route_regex(p), m, p) for m, p in routes]
    calls = []
    for f in list(SRC.rglob("*.jsx")) + list(SRC.rglob("*.js")):
        if "/ui/" in str(f): continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in CALL_RE.finditer(text):
            method = m.group(1).upper()
            raw = m.group(3)
            calls.append((method, normalize(raw), raw, f.relative_to(SRC)))
    print(f"Detected {len(calls)} apiClient calls across FE.")
    # unique paths
    uniq = {}
    for method, path, raw, src in calls:
        uniq.setdefault((method, path), (raw, src))
    print(f"Unique (method,path): {len(uniq)}")
    bad = []
    for (method, path), (raw, src) in sorted(uniq.items()):
        test = path.replace("X", "SAMPLE")
        # match path against ANY backend route (method-agnostic first, then method)
        path_match = [(mm, pp) for rx, mm, pp in compiled if rx.match(test)]
        if not path_match:
            bad.append((method, path, raw, src, "NO_PATH"))
        else:
            # method check
            methods_ok = any(method in mm for mm, pp in path_match)
            if not methods_ok:
                bad.append((method, path, raw, src, f"METHOD_MISMATCH(have {[list(mm) for mm,pp in path_match]})"))
    print(f"\n{'='*60}\nDRIFT / SILENT-404 candidates: {len(bad)}")
    for method, path, raw, src, why in bad:
        print(f"  [{why}] FE {method} {path}   (raw='{raw}')  src={src}")
    if not bad:
        print("  none — all FE apiClient paths resolve to a backend route.")
    return 0

if __name__ == "__main__":
    sys.exit(main())

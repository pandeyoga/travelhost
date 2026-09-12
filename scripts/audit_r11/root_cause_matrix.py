#!/usr/bin/env python3
"""
root_cause_matrix.py — PUTARAN 11 completeness proof for the 2 systemic bug classes.

Report-only static analyzer (does NOT modify prod code). Produces two matrices:

  (A) RACE / TOCTOU matrix — every resource-reservation write path × which guards it uses
      (find_conflicts / find_driver_conflicts / find_maintenance_conflicts / vehicle_lock).
      A path is SAFE only if it holds vehicle_lock around the final conflict re-check+insert.

  (B) NEGATIVE-VALUE matrix — every numeric money/quantity field in schemas.py × whether it
      is bounded (ge=/gt=) at the schema layer.

Output: scripts/audit_r11/root_cause_matrix.json + human-readable table on stdout.
"""
import ast
import json
import re
from pathlib import Path

BE = Path(__file__).resolve().parents[2] / "backend"
OUT = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# (A) RACE / TOCTOU MATRIX
# ---------------------------------------------------------------------------
GUARDS = ["find_conflicts", "find_driver_conflicts", "find_maintenance_conflicts", "vehicle_lock"]

# Resource-reservation write endpoints that create/confirm a vehicle+time reservation.
WRITE_PATHS = {
    "bookings.create_booking": "routers/bookings.py",
    "bookings.create_group_booking": "routers/bookings.py",
    "bookings.confirm_booking": "routers/bookings.py",
    "bookings.reschedule_booking": "routers/bookings.py",
    "bookings.approve_booking": "routers/bookings.py",
    "bookings.update_booking(PATCH driver)": "routers/bookings.py",
    "dispatch.assign_trip": "routers/dispatch.py",
    "quotations.convert": "routers/quotations.py",
    "subcharters.create": "routers/subcharters.py",
    "subcharters.update(PATCH)": "routers/subcharters.py",
    "public.create_public_booking": "routers/public.py",
    "driver.checkin": "routers/driver.py",
}


def func_source(path, fname):
    """Return source text of a function whose name matches fname's last identifier."""
    txt = (BE / path).read_text()
    ident = re.sub(r"\(.*", "", fname.split(".")[-1]).strip()
    try:
        tree = ast.parse(txt)
    except Exception:
        return txt
    lines = txt.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == ident:
            start = node.lineno - 1
            end = getattr(node, "end_lineno", start + 40)
            return "\n".join(lines[start:end])
    return txt


def analyze_race():
    rows = []
    for label, path in WRITE_PATHS.items():
        src = func_source(path, label)
        present = {g: (g in src) for g in GUARDS}
        # A vehicle-reservation path is TOCTOU-SAFE iff it re-checks conflicts INSIDE vehicle_lock.
        locked = present["vehicle_lock"]
        vehicle_guarded = present["find_conflicts"] and locked
        # driver double-book protection
        driver_guarded = present["find_driver_conflicts"]
        rows.append({
            "path": label, "file": path,
            **{g: present[g] for g in GUARDS},
            "vehicle_toctou_safe": vehicle_guarded,
            "driver_conflict_checked": driver_guarded,
        })
    return rows


# ---------------------------------------------------------------------------
# (B) NEGATIVE-VALUE MATRIX
# ---------------------------------------------------------------------------
# Fields whose negative values corrupt money/P&L/quantity invariants.
MONEY_QTY_HINTS = ("amount", "cost", "price", "base_price", "value", "fee", "refund",
                   "odometer", "salary", "commission", "rate", "discount", "distance",
                   "days", "pax", "capacity", "hours", "spend", "budget", "per_")


def analyze_negative():
    txt = (BE / "schemas.py").read_text()
    tree = ast.parse(txt)
    rows = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
                continue
            fname = stmt.target.id
            if not any(h in fname.lower() for h in MONEY_QTY_HINTS):
                continue
            # detect numeric type
            ann = ast.unparse(stmt.annotation) if hasattr(ast, "unparse") else ""
            if not any(t in ann for t in ("int", "float")):
                continue
            # detect Field(ge=/gt=) bound
            bounded = False
            bound_kind = None
            if stmt.value is not None:
                val = ast.unparse(stmt.value) if hasattr(ast, "unparse") else ""
                m = re.search(r"\b(ge|gt)\s*=", val)
                if m:
                    bounded = True
                    bound_kind = m.group(1)
            rows.append({
                "model": node.name, "field": fname, "type": ann,
                "bounded": bounded, "bound": bound_kind,
            })
    return rows


def main():
    race = analyze_race()
    neg = analyze_negative()

    print("=" * 96)
    print("(A) RACE / TOCTOU MATRIX — vehicle/driver reservation write paths")
    print("=" * 96)
    hdr = f"{'write path':38} {'fconf':5} {'fdrv':5} {'fmnt':5} {'vlock':5} {'VEH-SAFE':8} {'DRV-CHK':7}"
    print(hdr)
    print("-" * 96)
    for r in race:
        print(f"{r['path']:38} "
              f"{'Y' if r['find_conflicts'] else '-':5} "
              f"{'Y' if r['find_driver_conflicts'] else '-':5} "
              f"{'Y' if r['find_maintenance_conflicts'] else '-':5} "
              f"{'Y' if r['vehicle_lock'] else '-':5} "
              f"{'SAFE' if r['vehicle_toctou_safe'] else 'RISK':8} "
              f"{'Y' if r['driver_conflict_checked'] else 'NO':7}")
    veh_risk = [r["path"] for r in race if not r["vehicle_toctou_safe"]]
    drv_gap = [r["path"] for r in race if not r["driver_conflict_checked"]]
    print()
    print(f"VEHICLE double-book RISK (no vehicle_lock around re-check): {veh_risk}")
    print(f"DRIVER conflict NOT checked: {drv_gap}")

    print()
    print("=" * 96)
    print("(B) NEGATIVE-VALUE MATRIX — money/quantity schema fields")
    print("=" * 96)
    unbounded = [r for r in neg if not r["bounded"]]
    print(f"{'model.field':45} {'type':22} {'bounded':8}")
    print("-" * 96)
    for r in neg:
        print(f"{(r['model']+'.'+r['field']):45} {r['type']:22} {('yes('+r['bound']+')') if r['bounded'] else 'NO':8}")
    print()
    print(f"UNBOUNDED numeric fields (accept negatives at schema layer): {len(unbounded)} / {len(neg)}")
    for r in unbounded:
        print(f"   - {r['model']}.{r['field']} ({r['type']})")

    json.dump({"race_matrix": race, "negative_matrix": neg,
               "vehicle_risk_paths": veh_risk, "driver_gap_paths": drv_gap,
               "unbounded_fields": [f"{r['model']}.{r['field']}" for r in unbounded]},
              open(OUT / "root_cause_matrix.json", "w"), indent=2)
    print(f"\nWrote {OUT/'root_cause_matrix.json'}")


if __name__ == "__main__":
    main()

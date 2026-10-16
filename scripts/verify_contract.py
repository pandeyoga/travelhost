#!/usr/bin/env python3
"""
verify_contract.py — Collection Contract Verifier
=================================================
Verifikasi kode (seed/router/service) memakai nama koleksi MongoDB KANONIK
sesuai docs/03_DATA_MODEL.md — mencegah RC-1 (Collection Name Drift) SEBELUM runtime.
Mendeteksi KEDUA bentuk: db.<name> DAN db["<name>"].

Usage:
  cd /app && python scripts/verify_contract.py --all
  python scripts/verify_contract.py --list-canonical
  python scripts/verify_contract.py --find bookings
Exit 0 = bersih. 1 = ada koleksi terlarang (drift).
"""
import argparse, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
ROUTERS = BACKEND / "routers"
SERVICES = BACKEND / "services"
G, Y, R, C, B, X = "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[1m", "\033[0m"

# Sinkron dengan docs/03_DATA_MODEL.md
CANONICAL_COLLECTIONS = {
    "users", "sessions", "vehicles", "drivers", "customers", "leads",
    "conversations", "messages", "bookings", "trips", "locations", "trip_shares",
    "payments", "expenses", "invoices", "notification_tasks", "broadcasts",
    "maintenance_records", "destinations", "articles", "testimonials",
    "audit_logs", "settings", "user_onboarding", "lead_activities",
    "counters", "quotations", "packages", "promos",
    "events", "automation_rules", "automation_runs",
    "segments", "sequences", "sequence_enrollments", "campaigns", "campaign_recipients",
    "geocode_cache", "workshops", "service_types",
    "driver_payouts",
    "partners", "subcharters", "partner_settlements",
    "booking_locks",  # RC-16: mutex per-armada anti-TOCTOU (lock-free, TTL-guarded)
    # FASE F (E29+) Marketing/Ads & Landing Page — lihat docs/03_DATA_MODEL.md §5
    "conversion_events", "ads_accounts", "ads_entities", "ads_metrics_daily",
    "ads_sync_runs", "ad_touches", "audience_syncs", "platform_leads",
    "media_assets", "media_folders", "landing_pages", "landing_stats", "ga4_identities",
    # Pemesanan online v1 — lihat docs/03_DATA_MODEL.md §6
    "transfer_routes", "payment_proofs",
    # CMS-CW2 (CMS-05/07/08) — lihat docs/03_DATA_MODEL.md §7
    "content_previews", "review_requests", "content_stats",
    # CMS-CW3 (CMS-10/11/12) — riwayat versi, tempat sampah, pengalihan URL. Lihat §8.
    "content_versions", "content_trash", "content_redirects",
    "login_failures",  # anti brute-force login (TTL), bukan data domain
}

DANGEROUS_ALIASES = {
    "cars": "vehicles", "armada": "vehicles", "kendaraan": "vehicles", "vehicle": "vehicles", "fleet": "vehicles",
    "sopir": "drivers", "driver": "drivers",
    "clients": "customers", "pelanggan": "customers", "client": "customers", "customer": "customers",
    "orders": "bookings", "pesanan": "bookings", "booking": "bookings", "reservations": "bookings", "reservation": "bookings",
    "prospects": "leads", "lead": "leads", "prospek": "leads",
    "chats": "messages", "chat": "messages", "message": "messages",
    "gps": "locations", "positions": "locations", "tracking": "locations", "position": "locations", "location": "locations",
    "payment": "payments", "pembayaran": "payments",
    "cost": "expenses", "costs": "expenses", "biaya": "expenses", "expense": "expenses",
    "bills": "invoices", "faktur": "invoices", "tagihan": "invoices", "invoice": "invoices",
    "reminders": "notification_tasks", "reminder": "notification_tasks", "notifications": "notification_tasks",
    "broadcast": "broadcasts",
    "maintenance": "maintenance_records", "servis": "maintenance_records", "service_records": "maintenance_records",
    "destination": "destinations", "destinasi": "destinations",
    "blog": "articles", "posts": "articles", "article": "articles", "post": "articles",
    "testimonial": "testimonials", "ulasan": "testimonials", "reviews": "testimonials",
    "config": "settings", "configuration": "settings", "setting": "settings",
    "staff": "users", "karyawan": "users", "user": "users", "employees": "users",
    "audit_log": "audit_logs", "audits": "audit_logs",
}

NON_COLLECTION = {"get_db", "command", "ping", "list_collection_names", "client",
                  "name", "drop", "create_collection", "with_options", "list_collections"}


def extract_collections(filepath):
    pattern = re.compile(r'''db(?:\.([a-z][a-z0-9_]*)|\[\s*['"]([a-z][a-z0-9_]*)['"]\s*\])''')
    cols = {}
    try:
        for i, line in enumerate(filepath.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for m in pattern.finditer(line):
                col = m.group(1) or m.group(2)
                if col and col not in NON_COLLECTION:
                    cols.setdefault(col, []).append(i)
    except Exception as e:
        print(f"  ERROR membaca {filepath}: {e}")
    return cols


def classify(col):
    if col in CANONICAL_COLLECTIONS:
        return "KANONIK"
    if col in DANGEROUS_ALIASES:
        return "TERLARANG"
    return "TIDAK_DIKENAL"


def scan_all():
    print(f"\n{C}{B}{'='*64}{X}\n{B}  CONTRACT SCAN: router + service{X}\n{C}{B}{'='*64}{X}")
    files = []
    for d in (ROUTERS, SERVICES):
        if d.exists():
            files += list(d.rglob("*.py"))
    dangerous, unknown = [], []
    for f in sorted(files):
        if "__pycache__" in str(f):
            continue
        for col, lines in extract_collections(f).items():
            k = classify(col)
            if k == "TERLARANG":
                dangerous.append((f.name, col, DANGEROUS_ALIASES[col], lines[:3]))
            elif k == "TIDAK_DIKENAL" and not col.startswith("_") and len(col) > 3:
                unknown.append((f.name, col, lines[:3]))
    if dangerous:
        print(f"\n{R}{B}[DRIFT] Koleksi TERLARANG (RC-1):{X}")
        for fn, col, correct, lines in dangerous:
            print(f"  {R}{fn}: '{col}' → seharusnya '{correct}' (baris {lines}){X}")
    else:
        print(f"\n{G}[OK] Tidak ada koleksi terlarang.{X}")
    if unknown:
        print(f"\n{Y}[INFO] Koleksi tidak dikenal (daftarkan di 03_DATA_MODEL bila domain baru):{X}")
        for fn, col, lines in unknown[:40]:
            print(f"  {Y}{fn}: '{col}' (baris {lines}){X}")
    print(f"\n{B}{'='*64}{X}")
    if dangerous:
        print(f"  {R}{B}CONTRACT VIOLATION — perbaiki nama koleksi.{X}\n"); return 1
    print(f"  {G}{B}CONTRACT OK.{X}\n"); return 0


def find_collection(name):
    pat = re.compile(rf'''db(?:\.{re.escape(name)}\b|\[\s*['"]{re.escape(name)}['"]\s*\])''')
    found = []
    if BACKEND.exists():
        for py in sorted(BACKEND.rglob("*.py")):
            if "__pycache__" in str(py):
                continue
            for i, line in enumerate(py.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if pat.search(line):
                    found.append((str(py.relative_to(ROOT)), i, line.strip()[:100]))
    for fp, ln, txt in found:
        print(f"  {fp}:{ln}  {txt}")
    if not found:
        print("  (tidak ditemukan)")
    if name in DANGEROUS_ALIASES:
        print(f"  {R}PERINGATAN: '{name}' TERLARANG! Gunakan '{DANGEROUS_ALIASES[name]}'.{X}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--find")
    ap.add_argument("--list-canonical", action="store_true")
    args = ap.parse_args()
    if args.list_canonical:
        print("\nKoleksi Kanonik:")
        for c in sorted(CANONICAL_COLLECTIONS):
            print(f"  - {c}")
        return 0
    if args.find:
        return find_collection(args.find)
    return scan_all()


if __name__ == "__main__":
    sys.exit(main())

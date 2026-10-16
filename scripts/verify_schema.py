#!/usr/bin/env python3
"""
verify_schema.py — FIELD-LEVEL + FK REFERENTIAL INTEGRITY + ID-PREFIX GATE
==========================================================================
Menutup lubang yang TIDAK ditangkap verify_contract (cuma nama koleksi):
  S1  ID-PREFIX: tiap dokumen punya `id` berprefiks benar (usr_, veh_, bk_, ...).
  S2  FK INTEGRITY: referensi antar-koleksi menunjuk dokumen yang BENAR-BENAR ada
      (cegah "menggantung" → render 500 / data hantu).
  S3  TYPE SANITY: field numerik benar-benar numerik (amount, capacity, dst).
WAJIB jalan di DB clean-seed (sesudah seed). Skip rapi bila koleksi kosong (Phase 0 tanpa seed).
Usage: cd /app && python scripts/verify_schema.py
Exit 0 = valid/skip. !=0 = SCHEMA/FK VIOLATION.
"""
import asyncio
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
except Exception:
    pass
G, Y, R, C, B, X = "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[1m", "\033[0m"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "app_db")
results = {"pass": 0, "warn": 0, "fail": 0}

# id-prefix kanonik (sinkron docs/03_DATA_MODEL.md). None = tak memakai pola id berprefiks.
PREFIX = {
    "users": "usr_", "vehicles": "veh_", "drivers": "drv_", "customers": "cus_",
    "leads": "led_", "conversations": "cnv_", "messages": "msg_", "bookings": "bk_",
    "trips": "trp_", "locations": "loc_", "payments": "pay_", "expenses": "exp_",
    "invoices": "inv_", "notification_tasks": "ntf_", "broadcasts": "brd_",
    "maintenance_records": "mnt_", "destinations": "dst_", "articles": "art_",
    "pickup_points": "pkp_",
    "cities": "cty_",
    "site_pages": "pge_",
    "testimonials": "tst_", "lead_activities": "lac_", "trip_shares": "shr_",
    "quotations": "quo_", "packages": "pkg_", "promos": "pro_",
    "events": "evt_", "automation_rules": "aur_", "automation_runs": "arn_",
    "segments": "seg_", "sequences": "seq_", "sequence_enrollments": "enr_",
    "campaigns": "cmp_", "campaign_recipients": "cre_",
    "workshops": "wsh_",
    "service_types": "svt_",
    "driver_payouts": "dpo_",
    # Pemesanan online publik: rute antar-jemput bandara + bukti transfer pelanggan.
    "transfer_routes": "trt_",
    "payment_proofs": "ppf_",
    # CMS-CW2: token pratinjau konten (CMS-05) + permintaan ulasan pelanggan (CMS-07).
    "content_previews": "cpv_",
    "review_requests": "rvq_",
    # CMS-CW3: riwayat versi (CMS-10), tempat sampah (CMS-11), pengalihan URL (CMS-12).
    "content_versions": "cvr_",
    "content_trash": "ctr_",
    "content_redirects": "crd_",
}
# koleksi yang TIDAK pakai id berprefiks (punya kunci sendiri)
# `content_stats` dikunci pasangan (kind, slug) — bukan id berprefiks (lihat BUG-0128:
# mesin bersih-bersih WAJIB bisa menghapus dokumen tanpa field `id`).
NO_PREFIX = {"sessions", "settings", "user_onboarding", "audit_logs", "content_stats"}

# FK: (koleksi, field, koleksi_referensi, wajib_ada?)  wajib=False artinya nullable
FK = [
    ("bookings", "customer_id", "customers", True),
    ("bookings", "vehicle_id", "vehicles", True),
    ("bookings", "driver_id", "drivers", False),
    ("payments", "booking_id", "bookings", True),
    ("trips", "booking_id", "bookings", True),
    ("trips", "vehicle_id", "vehicles", False),
    ("trips", "driver_id", "drivers", False),
    ("locations", "trip_id", "trips", False),
    ("expenses", "booking_id", "bookings", False),
    ("expenses", "trip_id", "trips", False),
    ("invoices", "booking_id", "bookings", True),
    ("invoices", "customer_id", "customers", False),
    ("leads", "assigned_to", "users", False),
    ("messages", "conversation_id", "conversations", True),
    ("maintenance_records", "vehicle_id", "vehicles", True),
    ("maintenance_records", "workshop_id", "workshops", False),
    ("trip_shares", "trip_id", "trips", True),
    ("trip_shares", "vehicle_id", "vehicles", False),
    ("trip_shares", "created_by", "users", False),
    ("messages", "conversation_id", "conversations", True),
    ("conversations", "assigned_to", "users", False),
    ("notification_tasks", "booking_id", "bookings", False),
    ("lead_activities", "lead_id", "leads", True),
    ("lead_activities", "user_id", "users", False),
    ("leads", "converted_customer_id", "customers", False),
    ("leads", "linked_customer_id", "customers", False),
    ("quotations", "lead_id", "leads", False),
    ("quotations", "customer_id", "customers", False),
    ("quotations", "booking_id", "bookings", False),
    ("driver_payouts", "driver_id", "drivers", True),
    ("driver_payouts", "approver_id", "users", False),
    ("driver_payouts", "expense_id", "expenses", False),
    ("subcharters", "booking_id", "bookings", True),
    ("subcharters", "partner_id", "partners", True),
    ("subcharters", "vehicle_id", "vehicles", False),
    ("subcharters", "expense_id", "expenses", False),
    ("partner_settlements", "partner_id", "partners", True),
    ("partner_settlements", "subcharter_id", "subcharters", False),
    ("vehicles", "partner_id", "partners", False),
    # Bukti transfer pelanggan web → booking-nya WAJIB ada (tanpa itu uang tak bisa dicocokkan).
    ("payment_proofs", "booking_id", "bookings", True),
    ("payment_proofs", "media_id", "media_assets", False),
    ("bookings", "route_id", "transfer_routes", False),
]
# Pengecualian "wajib" BER-KONDISI (bukan bypass): FK boleh kosong bila dokumen memenuhi
# predikat di bawah. Sumber kebenaran = docs/03_DATA_MODEL.md.
#
# bookings.vehicle_id → docs/03_DATA_MODEL.md menulis eksplisit "nullable saat status=pending":
# permintaan self-service dari situs publik (routers/public.py::public_booking_request, E19)
# masuk sebagai `pending` TANPA armada; armada baru ditetapkan ops saat approve
# (routers/bookings.py::approve_booking). Aturan lama (wajib tanpa syarat) MERAH begitu ada
# satu permintaan publik nyata — jadi aturannya yang salah, bukan datanya.
REQUIRED_EXEMPT = {
    ("bookings", "vehicle_id"): (
        lambda d: d.get("status") in ("pending", "draft", "cancelled"),
        "status pending/draft/cancelled — armada ditetapkan saat approve (E19)",
    ),
}
# field yang harus numerik bila ada
NUMERIC = {
    "vehicles": ["capacity", "odometer"],
    "bookings": ["base_price", "total_amount", "paid_amount"],
    "payments": ["amount"],
    "expenses": ["amount"],
    "trips": ["revenue", "profit", "distance_km"],
    "locations": ["lat", "lng"],
    "quotations": ["subtotal", "total"],
    "packages": ["days", "price_from"],
    "promos": ["discount_value"],
    "driver_payouts": ["gross", "total"],
    "subcharters": ["cost"],
    "partner_settlements": ["amount"],
}


def line(tag, color, msg, detail=""):
    print(f"  {color}[{tag}]{X} {msg}" + (f"  {color}{detail}{X}" if detail else ""))


async def get_ids(db, col):
    return {d.get("id") for d in await db[col].find({}, {"_id": 0, "id": 1}).to_list(50000) if d.get("id")}


async def run():
    print(f"\n{B}{'='*60}{X}\n  SCHEMA + FK INTEGRITY GATE  (DB: {DB_NAME})\n{B}{'='*60}{X}")
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
    except ImportError:
        os.system("pip install motor -q")
        from motor.motor_asyncio import AsyncIOMotorClient
    db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]

    counts = {}
    for col in list(PREFIX.keys()) + list(NO_PREFIX):
        counts[col] = await db[col].count_documents({})
    if sum(counts.values()) == 0:
        print(f"{Y}  DB kosong — belum di-seed. Skip schema gate (Phase 0).{X}\n")
        return 0

    # S1 — id-prefix
    print(f"\n{C}{B}S1 — ID-PREFIX{X}")
    for col, pfx in PREFIX.items():
        if counts.get(col, 0) == 0:
            continue
        docs = await db[col].find({}, {"_id": 0, "id": 1}).to_list(50000)
        bad = [d.get("id") for d in docs if not (isinstance(d.get("id"), str) and d.get("id", "").startswith(pfx))]
        if bad:
            results["fail"] += 1
            line("FAIL", R, f"{col}: {len(bad)} id tanpa prefiks '{pfx}'", str(bad[:3]))
        else:
            results["pass"] += 1
            line("PASS", G, f"{col}: semua id berprefiks '{pfx}' ({counts[col]} dok)")

    # S2 — FK integrity
    print(f"\n{C}{B}S2 — FK REFERENTIAL INTEGRITY{X}")
    ids_cache = {}
    for col, field, ref, required in FK:
        if counts.get(col, 0) == 0:
            continue
        if ref not in ids_cache:
            ids_cache[ref] = await get_ids(db, ref)
        ref_ids = ids_cache[ref]
        docs = await db[col].find({}, {"_id": 0}).to_list(50000)
        exempt = REQUIRED_EXEMPT.get((col, field))
        dangling, missing_required, n_exempt = [], [], 0
        for d in docs:
            val = d.get(field)
            if val in (None, "", []):
                if required:
                    if exempt and exempt[0](d):
                        n_exempt += 1
                    else:
                        missing_required.append(d.get("id"))
                continue
            if val not in ref_ids:
                dangling.append(f"{d.get('id')}.{field}={val}")
        if dangling:
            results["fail"] += 1
            line("FAIL", R, f"{col}.{field} → {ref}: {len(dangling)} referensi MENGGANTUNG", str(dangling[:3]))
        elif missing_required:
            results["fail"] += 1
            line("FAIL", R, f"{col}.{field} (→{ref}) wajib tapi kosong: {len(missing_required)}", str(missing_required[:3]))
        else:
            results["pass"] += 1
            note = f" [{n_exempt} dikecualikan: {exempt[1]}]" if n_exempt else ""
            line("PASS", G, f"{col}.{field} → {ref} valid{note}")

    # S3 — numeric sanity
    print(f"\n{C}{B}S3 — TYPE SANITY (numerik){X}")
    for col, fields in NUMERIC.items():
        if counts.get(col, 0) == 0:
            continue
        docs = await db[col].find({}, {"_id": 0}).to_list(50000)
        bad = []
        for d in docs:
            for fld in fields:
                if fld in d and d[fld] is not None and not isinstance(d[fld], (int, float)):
                    bad.append(f"{d.get('id')}.{fld}={d[fld]!r}")
        if bad:
            results["fail"] += 1
            line("FAIL", R, f"{col}: field numerik bertipe salah ({len(bad)})", str(bad[:3]))
        else:
            results["pass"] += 1
            line("PASS", G, f"{col}: tipe numerik OK")

    print(f"\n{B}{'='*60}{X}\n  {G}PASS {results['pass']}{X} | {Y}WARN {results['warn']}{X} | {R}FAIL {results['fail']}{X}\n{B}{'='*60}{X}")
    if results["fail"]:
        print(f"{R}{B}  SCHEMA/FK VIOLATION — perbaiki sebelum lanjut.{X}\n")
        return 1
    print(f"{G}{B}  Skema & FK valid.{X}\n")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))

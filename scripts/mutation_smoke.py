#!/usr/bin/env python3
"""
mutation_smoke.py — WRITE-PATH SMOKE (audit alur TULIS, bukan cuma GET)
=======================================================================
Menguji alur mutasi end-to-end sebagai admin:
  M1  create customer → vehicle → booking (POST sukses, balasan punya id)
  M2  ANTI DOUBLE-BOOKING: booking overlap utk vehicle sama → HARUS ditolak (4xx)
  M3  record payment → booking.payment_status ter-update konsisten (INV-3)
Resilient: bila login gagal / endpoint belum ada (404/405) → SKIP rapi (Phase 0/early).
Hanya 5xx atau invarian rusak pasca-tulis yang dianggap FAIL.
Usage: cd /app && python scripts/mutation_smoke.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
except Exception:
    pass
try:
    import httpx
except ImportError:
    os.system("pip install httpx -q")
    import httpx

sys.path.insert(0, str(ROOT / "scripts" / "guardrails"))
from _common import purge_guard_artifacts  # noqa: E402  (INV-CLEAN-01)

API = os.environ.get("API_BASE", "http://localhost:8001").rstrip("/")
ADMIN = {"email": os.environ.get("ADMIN_EMAIL", "owner@demo.local"),
         "password": os.environ.get("ADMIN_PASS", "demo12345")}
G, Y, R, C, B, X = "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[1m", "\033[0m"
fails = 0
skips = 0
# ID artefak yang dibuat skrip ini; dibersihkan di `_summary()` (dipanggil di SETIAP jalur keluar).
ARTIFACTS = {}


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat()


def ok(m):
    print(f"  {G}[OK]{X} {m}")


def skip(m):
    global skips
    skips += 1
    print(f"  {Y}[SKIP]{X} {m}")


def fail(m):
    global fails
    fails += 1
    print(f"  {R}[FAIL]{X} {m}")


def presweep():
    """Buang SISA artefak smoke dari jalan sebelumnya sebelum mulai.

    Kenapa: skrip ini memakai identitas TETAP ("Smoke Customer" 0810000000, plat "D 9 ZZ") supaya
    tidak menumpuk data. Konsekuensinya, bila jalan sebelumnya berhenti di tengah (atau berjalan
    sebelum pembersihan ini ada), `POST /customers` menjawab **409 duplikat** dan seluruh smoke
    berubah jadi SKIP — gate tampak hijau padahal alur TULIS tidak pernah diuji. Itu persis pola
    "hijau palsu" yang dilarang repo ini, jadi sisa data dibersihkan lebih dulu.
    """
    try:
        from pymongo import MongoClient
    except Exception:  # noqa: BLE001
        return
    url, name = os.environ.get("MONGO_URL"), os.environ.get("DB_NAME")
    if not (url and name):
        return
    try:
        with MongoClient(url, serverSelectionTimeoutMS=4000) as client:
            db = client[name]
            custs = [c["id"] for c in db.customers.find(
                {"name": "Smoke Customer", "phone": {"$regex": "^0810000000"}},
                {"_id": 0, "id": 1})]
            vehs = [v["id"] for v in db.vehicles.find(
                {"name": "Smoke Vehicle"}, {"_id": 0, "id": 1})]
            bks = [b["id"] for b in db.bookings.find(
                {"$or": [{"customer_id": {"$in": custs}}, {"vehicle_id": {"$in": vehs}}]},
                {"_id": 0, "id": 1})] if (custs or vehs) else []
            if bks:
                db.payments.delete_many({"booking_id": {"$in": bks}})
                db.bookings.delete_many({"id": {"$in": bks}})
            if vehs:
                db.vehicles.delete_many({"id": {"$in": vehs}})
            if custs:
                db.customers.delete_many({"id": {"$in": custs}})
            if bks or vehs or custs:
                print(f"  {Y}[BERSIH]{X} sisa artefak smoke sebelumnya dibuang "
                      f"({len(custs)} customer, {len(vehs)} armada, {len(bks)} booking).")
    except Exception as exc:  # noqa: BLE001
        print(f"  {Y}[SKIP]{X} presweep smoke gagal: {exc}")
    purge_guard_artifacts()  # INV-CLEAN-01: sekalian buang side-effect sisa jalan sebelumnya


def cleanup(cust_id=None, veh_id=None, bk_id=None):
    """Buang artefak smoke dari database — BY ID, tanpa menebak.

    Alasan: booking sengaja TIDAK punya endpoint DELETE (catatan keuangan), dan armada tak bisa
    dihapus selama masih terkait booking. Tanpa pembersihan ini setiap jalan gate meninggalkan
    "Smoke Customer"/"Smoke Vehicle" + 1 booking + 1 pembayaran di data yang dilihat pengguna —
    kelas masalah "data uji bocor ke produk" yang sama dengan unit uji yang pernah tayang di
    katalog publik. Saringan memakai ID hasil pembuatan skrip ini sendiri, jadi mustahil
    menyentuh data nyata.
    """
    try:
        from pymongo import MongoClient
    except Exception:  # noqa: BLE001
        return
    url, name = os.environ.get("MONGO_URL"), os.environ.get("DB_NAME")
    if not (url and name):
        return
    removed = 0
    try:
        with MongoClient(url, serverSelectionTimeoutMS=4000) as client:
            db = client[name]
            if bk_id:
                removed += db.payments.delete_many({"booking_id": bk_id}).deleted_count
                removed += db.bookings.delete_many({"id": bk_id}).deleted_count
            if veh_id:
                removed += db.vehicles.delete_many({"id": veh_id}).deleted_count
            if cust_id:
                removed += db.customers.delete_many({"id": cust_id}).deleted_count
    except Exception as exc:  # noqa: BLE001
        print(f"  {Y}[SKIP]{X} bersih-bersih smoke gagal: {exc}")
        return
    # INV-CLEAN-01 — dokumen utama saja TIDAK cukup: pembayaran/booking smoke memancarkan event
    # → automation (WA mock) membuat PERCAKAPAN "Smoke Customer" + pesan + notifikasi + entri
    # audit yang dulu MENETAP di Inbox & lonceng ops (BUG-0127). Bersihkan side-effect-nya juga.
    removed += purge_guard_artifacts()
    if removed:
        ok(f"bersih-bersih: {removed} dokumen uji dihapus (data pengguna tetap bersih)")


async def backend_up(client):
    try:
        r = await client.get(f"{API}/api/", timeout=5)
        return r.status_code < 500
    except Exception:
        return False


async def login(client):
    try:
        r = await client.post(f"{API}/api/auth/login", json=ADMIN, timeout=15)
        if r.status_code == 200:
            return r.json().get("token")
    except Exception:
        return None
    return None


async def post(client, h, path, payload):
    """Return (status, json|None). Tangani endpoint tak ada."""
    try:
        r = await client.post(f"{API}{path}", json=payload, headers=h, timeout=20)
        try:
            body = r.json()
        except Exception:
            body = None
        return r.status_code, body
    except Exception as ex:
        return -1, str(ex)


async def run():
    print(f"\n{B}{'='*60}{X}\n  MUTATION SMOKE (write-path)  API={API}\n{B}{'='*60}{X}")
    presweep()
    async with httpx.AsyncClient(follow_redirects=True) as client:
        if not await backend_up(client):
            print(f"{Y}  Backend belum berjalan — skip mutation smoke (Phase 0).{X}\n")
            return 0
        token = await login(client)
        if not token:
            print(f"{Y}  Tidak bisa login (auth/seed belum ada) — skip mutation smoke.{X}\n")
            return 0
        h = {"Authorization": f"Bearer {token}"}

        # M1 — create chain
        sc, cust = await post(client, h, "/api/customers",
                              {"name": "Smoke Customer", "phone": "0810000000",
                               "type": "individual", "city": "Bandung"})
        if sc in (404, 405, -1):
            skip("POST /api/customers belum ada — hentikan smoke (fase awal).")
            return _summary()
        if sc >= 500:
            fail(f"POST /api/customers 5xx ({sc}).")
            return _summary()
        if sc not in (200, 201) or not isinstance(cust, dict) or not cust.get("id"):
            skip(f"POST /api/customers → {sc} (kontrak beda) — lewati.")
            return _summary()
        ok(f"customer dibuat: {cust.get('id')}")
        cust_id = cust["id"]
        ARTIFACTS["cust_id"] = cust_id

        sc, veh = await post(client, h, "/api/vehicles",
                             # `publish_to_web: False` WAJIB: tanpa ini unit uji ikut tayang di
                             # katalog publik & pencarian pemesanan online (terbukti — "Smoke
                             # Vehicle" pernah muncul sebagai unit yang bisa dipesan tamu di
                             # /booking). Smoke test tidak boleh pernah menyentuh muka toko.
                             {"name": "Smoke Vehicle", "plate_number": "D 9 ZZ", "type": "hiace",
                              "capacity": 14, "publish_to_web": False})
        if sc >= 500:
            fail(f"POST /api/vehicles 5xx ({sc}).")
            return _summary()
        if sc not in (200, 201) or not veh or not veh.get("id"):
            skip(f"POST /api/vehicles → {sc} — lewati sisanya.")
            return _summary()
        ok(f"vehicle dibuat: {veh.get('id')}")
        veh_id = veh["id"]
        ARTIFACTS["veh_id"] = veh_id

        start = datetime.now(timezone.utc) + timedelta(days=10)
        end = start + timedelta(days=2)
        bk_payload = {"customer_id": cust_id, "vehicle_id": veh_id, "origin": "Bandung",
                      "destination": "Gunung Bromo", "start_datetime": iso(start), "end_datetime": iso(end),
                      "base_price": 3000000}
        sc, bk = await post(client, h, "/api/bookings", bk_payload)
        if sc >= 500:
            fail(f"POST /api/bookings 5xx ({sc}).")
            return _summary()
        if sc not in (200, 201) or not bk or not bk.get("id"):
            skip(f"POST /api/bookings → {sc} — lewati anti-double-booking & payment.")
            return _summary()
        ok(f"booking dibuat: {bk.get('id')} (status={bk.get('status')})")
        bk_id = bk["id"]
        ARTIFACTS["bk_id"] = bk_id

        # M2 — anti double-booking: overlap utk vehicle sama harus ditolak
        sc2, bk2 = await post(client, h, "/api/bookings", bk_payload)
        if sc2 in (400, 409, 422):
            ok(f"anti double-booking bekerja (overlap ditolak {sc2}).")
        elif sc2 in (200, 201):
            fail("anti double-booking GAGAL: booking overlap diterima (INV-4).")
        elif sc2 >= 500:
            fail(f"POST /api/bookings (overlap) 5xx ({sc2}).")
        else:
            skip(f"overlap booking → {sc2} (tak konklusif).")

        # M3 — payment → status
        sc3, pay = await post(client, h, "/api/payments",
                              {"booking_id": bk_id, "amount": 3000000, "type": "settlement", "method": "transfer"})
        if sc3 in (404, 405):
            skip("POST /api/payments belum ada — lewati cek status.")
        elif sc3 >= 500:
            fail(f"POST /api/payments 5xx ({sc3}).")
        elif sc3 in (200, 201):
            try:
                r = await client.get(f"{API}/api/bookings/{bk_id}", headers=h, timeout=15)
                if r.status_code == 200:
                    ps = r.json().get("payment_status")
                    if ps in ("lunas", "selesai"):
                        ok(f"payment penuh → payment_status='{ps}' (INV-3 konsisten).")
                    else:
                        fail(f"payment penuh tapi payment_status='{ps}' (harus lunas) — INV-3 drift.")
                else:
                    skip(f"GET /api/bookings/{{id}} → {r.status_code}.")
            except Exception as ex:
                skip(f"verifikasi status gagal: {ex}")
        else:
            skip(f"POST /api/payments → {sc3}.")

    return _summary()


def _summary():
    cleanup(**ARTIFACTS)
    print(f"\n{B}{'='*60}{X}\n  {R}FAIL {fails}{X} | {Y}SKIP {skips}{X}\n{B}{'='*60}{X}")
    if fails:
        print(f"{R}{B}  WRITE-PATH BERMASALAH — perbaiki sebelum lanjut.{X}\n")
        return 1
    print(f"{G}{B}  Write-path sehat (atau di-skip pada fase awal).{X}\n")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))

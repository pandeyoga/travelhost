"""Iteration 104 — Broadcast WA nyata (routers/broadcasts.py) + regresi INV-BOOK-02.

Cakupan:
- RBAC broadcast (owner/ops boleh, driver 403)
- Create broadcast + list persistence
- Send broadcast (provider mock) → progres sent_count, klaim atomik (400 saat kirim ulang), 404
- Pesan tercatat di Inbox (messages, channel whatsapp) dgn variabel {customer_name}/{company} dirender
- Regresi INV-BOOK-02: total_amount di body /api/public/booking/submit diabaikan
Data uji: lead 'Penjaga INV-BC Lead' (phone 08000001234, stage=lost, source=manual) — dihapus di teardown.
"""
import os
import time
import uuid
from datetime import datetime, timedelta

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base.rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {
    "owner": ("owner@demo.local", "demo12345"),
    "ops": ("ops@demo.local", "demo12345"),
    "driver": ("driver@demo.local", "demo12345"),
}

SEG_STAGE, SEG_SOURCE = "lost", "manual"   # kombinasi yang TIDAK dipakai lead seed
TEST_PHONE = "08000001234"


def login(role):
    email, pwd = CREDS[role]
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"Login {role} gagal {r.status_code}: {r.text[:300]}")
    data = r.json()
    token = data.get("token")
    assert token, f"token tidak ada di respons login: {data}"
    return token


@pytest.fixture(scope="module")
def owner():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {login('owner')}"})
    return s


@pytest.fixture(scope="module")
def driver():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {login('driver')}"})
    return s


@pytest.fixture(scope="module")
def test_lead(owner):
    """Lead uji tunggal pada segmen yang terisolasi."""
    r = owner.post(f"{API}/leads", json={
        "customer_name": "Penjaga INV-BC Lead", "phone": TEST_PHONE,
        "source": SEG_SOURCE, "stage": SEG_STAGE, "message": "Penjaga INV-BC",
    }, timeout=30)
    assert r.status_code in (200, 201), f"buat lead gagal: {r.status_code} {r.text[:300]}"
    lead = r.json()
    assert lead.get("id")
    # stage bisa di-default 'new' oleh server → paksa ke segmen uji
    if lead.get("stage") != SEG_STAGE:
        owner.post(f"{API}/leads/{lead['id']}/stage", json={"stage": SEG_STAGE}, timeout=30)
    yield lead
    # tidak ada endpoint DELETE /api/leads/{id} → bersihkan langsung di Mongo
    import asyncio

    from motor.motor_asyncio import AsyncIOMotorClient
    env = dotenv_values("/app/backend/.env")

    async def _clean_lead():
        db = AsyncIOMotorClient(env["MONGO_URL"])[env["DB_NAME"]]
        await db.leads.delete_many({"phone": {"$regex": "^0800000"}})
    asyncio.run(_clean_lead())


@pytest.fixture(scope="module")
def created_broadcasts():
    return []


@pytest.fixture(scope="module", autouse=True)
def cleanup(created_broadcasts):
    yield
    # bersihkan dokumen uji langsung di Mongo (tak ada endpoint DELETE broadcast)
    import asyncio

    from motor.motor_asyncio import AsyncIOMotorClient
    env = dotenv_values("/app/backend/.env")

    async def _clean():
        db = AsyncIOMotorClient(env["MONGO_URL"])[env["DB_NAME"]]
        if created_broadcasts:
            await db.broadcasts.delete_many({"id": {"$in": created_broadcasts}})
        convs = await db.conversations.find({"contact_phone": {"$regex": "^0800000"}},
                                            {"_id": 0, "id": 1}).to_list(50)
        ids = [c["id"] for c in convs]
        if ids:
            await db.messages.delete_many({"conversation_id": {"$in": ids}})
            await db.conversations.delete_many({"id": {"$in": ids}})
    asyncio.run(_clean())


class TestRbac:
    def test_driver_denied_list(self, driver):
        r = driver.get(f"{API}/broadcasts", timeout=30)
        assert r.status_code == 403, f"driver seharusnya 403, dapat {r.status_code}"

    def test_driver_denied_create(self, driver):
        r = driver.post(f"{API}/broadcasts", json={"title": "Penjaga INV-BC X",
                                                   "message": "hai"}, timeout=30)
        assert r.status_code == 403

    def test_unauthenticated_denied(self):
        r = requests.get(f"{API}/broadcasts", timeout=30)
        assert r.status_code in (401, 403)

    def test_ops_allowed(self):
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {login('ops')}"})
        r = s.get(f"{API}/broadcasts", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestBroadcastCrud:
    def test_list_contains_seed(self, owner):
        r = owner.get(f"{API}/broadcasts", timeout=30)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list) and rows
        assert all("_id" not in b for b in rows), "ObjectId _id bocor di respons"
        seed = [b for b in rows if b.get("title") == "Promo Akhir Pekan"]
        assert seed, "broadcast seed 'Promo Akhir Pekan' tidak ditemukan"
        assert seed[0]["status"] == "draft"

    def test_create_and_persist(self, owner, test_lead, created_broadcasts):
        payload = {
            "title": "Penjaga INV-BC Promo",
            "message": "Halo {customer_name}, promo dari {company}!",
            "segment_stage": SEG_STAGE, "segment_source": SEG_SOURCE,
        }
        r = owner.post(f"{API}/broadcasts", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        b = r.json()
        created_broadcasts.append(b["id"])
        assert b["title"] == payload["title"]
        assert b["message"] == payload["message"]
        assert b["status"] == "draft"
        assert b["segment"] == {"stage": SEG_STAGE, "source": SEG_SOURCE}
        assert b["recipients_count"] == 1, f"harus 1 penerima (lead uji), dapat {b['recipients_count']}"
        # GET verifikasi persistensi
        rows = owner.get(f"{API}/broadcasts", timeout=30).json()
        got = [x for x in rows if x["id"] == b["id"]]
        assert got and got[0]["status"] == "draft"

    def test_create_validation(self, owner):
        r = owner.post(f"{API}/broadcasts", json={"title": "", "message": ""}, timeout=30)
        assert r.status_code == 422, f"validasi kosong harus 422, dapat {r.status_code}"

    def test_send_unknown_404(self, owner):
        r = owner.post(f"{API}/broadcasts/brd_tidak_ada/send", timeout=30)
        assert r.status_code == 404
        assert "tidak ditemukan" in r.json().get("detail", "").lower()


class TestBroadcastSend:
    bid = None

    def test_send_flow(self, owner, test_lead, created_broadcasts):
        r = owner.post(f"{API}/broadcasts", json={
            "title": "Penjaga INV-BC Kirim",
            "message": "Hai {customer_name}, salam dari {company}.",
            "segment_stage": SEG_STAGE, "segment_source": SEG_SOURCE}, timeout=30)
        assert r.status_code in (200, 201)
        b = r.json()
        TestBroadcastSend.bid = b["id"]
        created_broadcasts.append(b["id"])

        s = owner.post(f"{API}/broadcasts/{b['id']}/send", timeout=60)
        assert s.status_code == 200, s.text[:300]
        started = s.json()
        assert started["status"] in ("sending", "sent")
        assert started["recipients_count"] == 1

        final = None
        for _ in range(20):
            time.sleep(1)
            rows = owner.get(f"{API}/broadcasts", timeout=30).json()
            cur = next(x for x in rows if x["id"] == b["id"])
            if cur["status"] in ("sent", "failed"):
                final = cur
                break
        assert final, "broadcast tidak selesai dalam 20s"
        assert final["status"] == "sent", f"status akhir {final['status']} error={final.get('error')}"
        assert final.get("sent_count") == 1, f"sent_count={final.get('sent_count')} failed={final.get('failed_count')}"
        assert final.get("failed_count", 0) == 0
        assert final.get("sent_at")

    def test_resend_blocked_atomic_claim(self, owner):
        assert TestBroadcastSend.bid, "test sebelumnya gagal"
        r = owner.post(f"{API}/broadcasts/{TestBroadcastSend.bid}/send", timeout=30)
        assert r.status_code == 400, f"kirim ulang harus 400, dapat {r.status_code}"
        assert "sudah/sedang dikirim" in r.json().get("detail", "")

    def test_message_logged_in_inbox_with_rendered_vars(self, owner):
        """Pesan broadcast harus muncul di Inbox dgn variabel sudah dirender."""
        assert TestBroadcastSend.bid
        r = owner.get(f"{API}/conversations", params={"limit": 100}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        payload = r.json()
        convs = payload if isinstance(payload, list) else payload.get("items", payload.get("data", []))
        target = [c for c in convs if (c.get("contact_phone") or "").startswith("0800000")
                  or "Penjaga INV-BC" in (c.get("contact_name") or "")]
        assert target, "percakapan WA untuk lead uji tidak dibuat oleh broadcast"
        conv = target[0]
        assert conv.get("channel") == "whatsapp"
        m = owner.get(f"{API}/conversations/{conv['id']}", timeout=30)
        assert m.status_code == 200, m.text[:200]
        msgs = m.json().get("messages") or []
        out = [x for x in msgs if x.get("direction") == "out" or x.get("sender") == "agent"]
        assert out, f"tidak ada pesan keluar: {msgs}"
        bodies = " | ".join(x.get("body") or "" for x in out)
        assert "{customer_name}" not in bodies and "{company}" not in bodies, \
            f"variabel tidak dirender: {bodies}"
        assert "Penjaga INV-BC Lead" in bodies, f"customer_name tidak tersisip: {bodies}"
        assert any(x.get("source") == "broadcast" for x in out), "source 'broadcast' tidak tercatat"
        assert any(x.get("channel") == "whatsapp" for x in out)


class TestBookingInv02:
    """Regresi INV-BOOK-02: harga tidak boleh datang dari klien."""

    @staticmethod
    def _window():
        start = (datetime.now() + timedelta(days=6)).replace(hour=9, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=2)
        return start.isoformat(), end.isoformat()

    def test_submit_ignores_total_amount(self):
        start, end = self._window()
        se = requests.post(f"{API}/public/booking/search", json={
            "service": "daily_rental", "start_datetime": start, "end_datetime": end, "pax": 2},
            timeout=60)
        assert se.status_code == 200, se.text[:300]
        opts = se.json().get("options") or []
        if not opts:
            pytest.skip("tidak ada unit tersedia untuk jendela uji")
        opt = opts[0]
        server_total = opt["quote"]["total"]
        payload = {
            "service": "daily_rental", "vehicle_id": opt["vehicle"]["id"],
            "start_datetime": start, "end_datetime": end, "pax": 2,
            "name": "Penjaga INV Booking", "phone": "08000009911",
            "pickup_address": "Jl. Uji 1", "idempotency_key": f"invbc-{uuid.uuid4().hex[:10]}",
            "total_amount": 1,  # nilai palsu dari klien — HARUS diabaikan
        }
        r = requests.post(f"{API}/public/booking/submit", json=payload, timeout=60)
        assert r.status_code in (200, 201), f"submit gagal: {r.status_code} {r.text[:400]}"
        data = r.json()
        bk = data.get("booking") or data
        total = bk.get("total_amount", bk.get("total"))
        assert total not in (1, 1.0), "harga klien (total_amount=1) TERPAKAI — INV-BOOK-02 bocor"
        assert abs(float(total) - float(server_total)) < 1.0, \
            f"total server {total} != quote {server_total}"
        # bersihkan pesanan uji
        import asyncio

        from motor.motor_asyncio import AsyncIOMotorClient
        env = dotenv_values("/app/backend/.env")
        code = bk.get("code") or bk.get("booking_code")

        async def _clean():
            db = AsyncIOMotorClient(env["MONGO_URL"])[env["DB_NAME"]]
            q = {"code": code} if code else {"customer_name": "Penjaga INV Booking"}
            await db.bookings.delete_many(q)
        asyncio.run(_clean())

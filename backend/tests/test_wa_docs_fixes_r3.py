"""Regresi audit ronde 3 (2026-10-28): pengiriman dokumen + otomasi WhatsApp (OpenWA).

Bagian atas = fungsi murni. Tengah = layanan async pada database Mongo SEMENTARA (dihapus di
akhir) dengan provider WA palsu. Bawah = API (backend hidup + seed demo).
"""
import asyncio
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from services import whatsapp as wa  # noqa: E402
from services.automation import default_rules, sync_system_rules  # noqa: E402
from services.booking_flow import payment_note  # noqa: E402
from services.calendar_export import calendar_pdf, _fmt_dt  # noqa: E402
from services.documents import fdate, invoice_items, kind_label  # noqa: E402
from services.events import render_template  # noqa: E402
from services.notifications import overdue_reminder_due  # noqa: E402

ENV = {**dotenv_values(ROOT / "backend" / ".env"), **os.environ}
API = (ENV.get("REACT_APP_BACKEND_URL") or "http://127.0.0.1:8001").rstrip("/") + "/api"


# ------------------------------------------------------------------ fungsi murni
def test_phone_variants_cover_local_and_international_forms():
    v = set(wa.phone_variants("0812-3456-7890"))
    assert {"+6281234567890", "6281234567890", "081234567890"} <= v
    assert set(wa.phone_variants("6281234567890")) >= {"+6281234567890", "081234567890"}


def test_retry_only_for_failed_system_text():
    failed = {"status": "failed", "error": "Session not connected"}
    assert wa._first_retry_at(failed, "automation", None)  # otomasi teks gagal → dicoba ulang
    assert wa._first_retry_at({"status": "sent"}, "automation", None) is None
    assert wa._first_retry_at(failed, "agent", None) is None  # agen melihat galat sendiri
    assert wa._first_retry_at(failed, "automation", "data:application/pdf;base64,AA") is None
    assert wa._first_retry_at({"status": "failed", "error": "Nomor tujuan tidak valid"}, "automation", None) is None


def test_payment_note_follows_what_was_paid():
    assert payment_note({"total_amount": 1000000, "paid_amount": 1000000}, 30) == "Pembayaran sudah lunas."
    assert payment_note({"total_amount": 1000000, "paid_amount": 300000}, 30) == \
        "Pembayaran Rp 300.000 sudah kami terima; sisa Rp 700.000."
    assert payment_note({"total_amount": 1000000, "paid_amount": 0}, 30).startswith("Mohon DP 30% (Rp 300.000)")


def test_confirmed_wa_uses_wib_and_payment_note():
    rule = next(r for r in default_rules() if r["event_type"] == "booking.confirmed"
                and any(a["type"] == "send_wa" for a in r["actions"]))
    text = next(a for a in rule["actions"] if a["type"] == "send_wa")["params"]["text"]
    out = render_template(text, {"code": "BK-1", "start_datetime": "2026-10-28T09:00:00+00:00",
                                 "vehicle_name": "Hiace", "total_amount": 1000000,
                                 "payment_note": "Pembayaran sudah lunas."})
    assert "28 Okt 2026 16.00 WIB" in out and "lunas" in out and "Mohon DP" not in out


def test_overdue_customer_reminders_are_spaced():
    due = [d for d in range(1, 60) if overdue_reminder_due(d)]
    assert due == [1, 3, 7, 14, 28, 42, 56]


def test_cancellation_fee_invoice_prints_as_fee():
    inv = {"type": "cancellation_fee", "amount": 300000, "booking_code": "BK-9"}
    assert kind_label(inv) == "Denda Pembatalan"
    items = invoice_items(inv, {"code": "BK-9", "total_amount": 2000000})
    assert items == [{"label": "Denda Pembatalan booking BK-9", "qty": 1, "unit_price": 300000, "amount": 300000}]
    assert kind_label({"kind": "dp"}) == "Uang Muka (DP)"


def test_document_dates_are_wib():
    # Berangkat 10 Nov 2031 06.00 WIB = 9 Nov 23.00 UTC.
    assert fdate("2031-11-09T23:00:00+00:00") == "10 November 2031"
    assert fdate("2031-11-10") == "10 November 2031"  # tanggal murni tak digeser
    assert _fmt_dt("2031-11-09T23:00:00+00:00") == "10 Nov 2031 06:00"


def test_calendar_pdf_escapes_markup_in_names():
    row = {"code": "BK-1", "customer_name": "Budi <VIP", "vehicle_name": "Hiace <A>",
           "start_datetime": "2031-11-09T23:00:00+00:00", "end_datetime": "2031-11-10T23:00:00+00:00"}
    assert calendar_pdf("November 2031", [row], grouped=True, org="PT <Uji>")[:4] == b"%PDF"


# ------------------------------------------------------------------ layanan (Mongo sementara)
class FakeProvider:
    name = "fake"
    fail = False
    sent = []

    def __init__(self, cfg=None):
        pass

    async def send_text(self, to, text):
        FakeProvider.sent.append((to, text))
        if FakeProvider.fail:
            return {"status": "failed", "error": "Session not connected"}
        return {"status": "sent", "wa_message_id": f"wamid.fake{len(FakeProvider.sent)}"}

    async def send_template(self, to, template_key, variables, body=None):
        return await self.send_text(to, body or template_key)


@pytest.fixture()
def tmpdb(monkeypatch):
    if not ENV.get("MONGO_URL"):
        pytest.skip("MONGO_URL tidak tersedia")
    from motor.motor_asyncio import AsyncIOMotorClient
    name = f"tmp_wa_r3_{random.randint(10000, 99999)}"
    FakeProvider.sent, FakeProvider.fail = [], False
    monkeypatch.setattr(wa, "_provider_for", lambda cfg: FakeProvider(cfg))

    async def _no_emit(*a, **k):
        return None
    import services.events as ev
    monkeypatch.setattr(ev, "emit", _no_emit)

    def run(fn):
        async def go():
            client = AsyncIOMotorClient(ENV["MONGO_URL"])
            try:
                return await fn(client[name])
            finally:
                client.close()
        return asyncio.run(go())
    yield run
    from pymongo import MongoClient
    MongoClient(ENV["MONGO_URL"]).drop_database(name)


def test_inbound_same_number_one_conversation_dedupe_and_cooldown(tmpdb):
    async def body(db):
        conv = await wa.ensure_conversation(db, "081234500001", name="Uji")
        r1 = await wa.handle_inbound(db, "6281234500001", "halo", provider_msg_id="wamid.in1")
        r2 = await wa.handle_inbound(db, "6281234500001", "halo", provider_msg_id="wamid.in1")  # retry webhook
        await wa.handle_inbound(db, "6281234500001", "ada armada?", provider_msg_id="wamid.in2")
        convs = await db.conversations.count_documents({})
        inbound = await db.messages.count_documents({"direction": "in"})
        auto = await db.messages.count_documents({"source": "auto_reply"})
        return conv, r1, r2, convs, inbound, auto
    conv, r1, r2, convs, inbound, auto = tmpdb(body)
    assert r1["conversation_id"] == conv["id"] and convs == 1  # 0812… & 62812… = satu percakapan
    assert r2["status"] == "duplicate" and inbound == 2
    assert auto == 1  # dua pesan beruntun → satu balasan otomatis (cooldown)


def test_failed_automation_message_is_retried_then_cleared(tmpdb):
    async def body(db):
        FakeProvider.fail = True
        res = await wa.send_wa(db, "081234500002", text="Booking dikonfirmasi", source="automation")
        msg = await db.messages.find_one({"direction": "out"}, {"_id": 0})
        # jadwal coba-ulang tiba → scheduler mengirim ulang
        await db.messages.update_one({"id": msg["id"]}, {"$set": {"retry_at": "2000-01-01T00:00:00+00:00"}})
        FakeProvider.fail = False
        sent = await wa.retry_failed(db)
        after = await db.messages.find_one({"id": msg["id"]}, {"_id": 0})
        again = await wa.retry_failed(db)
        return res, msg, sent, after, again
    res, msg, sent, after, again = tmpdb(body)
    assert res["status"] == "failed" and msg["retry_at"]
    assert sent == 1 and after["status"] == "sent" and after["retry_at"] is None and after["retry_count"] == 1
    assert again == 0 and len(FakeProvider.sent) == 2  # tidak terkirim dobel


def test_agent_message_failure_not_auto_retried(tmpdb):
    async def body(db):
        FakeProvider.fail = True
        await wa.send_wa(db, "081234500003", text="balasan agen", source="agent")
        return await db.messages.find_one({"direction": "out"}, {"_id": 0})
    assert tmpdb(body)["retry_at"] is None


def test_sync_system_rules_adds_new_but_respects_deleted(tmpdb):
    async def body(db):
        old = [r for r in default_rules() if r["name"] not in
               {"Info hold hangus ke pelanggan", "Instruksi DP setelah disetujui", "Bukti DP masuk", "Bukti DP ditolak"}]
        await db.automation_rules.insert_many([dict(r) for r in old[1:]])  # old[0] dihapus admin dulu
        first = await sync_system_rules(db)
        names = {r["name"] async for r in db.automation_rules.find({}, {"name": 1})}
        await db.automation_rules.delete_one({"name": "Bukti DP masuk"})  # admin menghapus rule baru
        second = await sync_system_rules(db)
        names2 = {r["name"] async for r in db.automation_rules.find({}, {"name": 1})}
        return old[0]["name"], first, names, second, names2
    deleted_old, first, names, second, names2 = tmpdb(body)
    assert first["added"] == 4 and "Instruksi DP setelah disetujui" in names
    assert deleted_old not in names  # rule lama yang sudah dihapus tidak dihidupkan lagi
    assert second["added"] == 0 and "Bukti DP masuk" not in names2


def test_invoice_caption_reflects_payment_state(tmpdb):
    from routers.invoices import _invoice_caption

    async def body(db):
        await db.bookings.insert_one({"id": "bk_cap", "paid_amount": 300000})
        base = {"booking_id": "bk_cap", "number": "INV-1", "booking_code": "BK-1", "customer_name": "Budi",
                "kind": "full", "amount": 1000000, "paid_before": 0, "due_at": "2031-01-05T00:00:00+00:00"}
        partial = await _invoice_caption(db, {**base, "status": "partial"})
        fee = await _invoice_caption(db, {**base, "kind": None, "type": "cancellation_fee", "amount": 300000,
                                          "status": "paid"})
        return partial, fee
    partial, fee = tmpdb(body)
    assert "Sudah dibayar Rp 300.000, sisa Rp 700.000" in partial
    assert "invoice denda pembatalan INV-1" in fee and "LUNAS" in fee and "Jatuh tempo" not in fee


def test_numbering_skips_numbers_already_used(tmpdb):
    from services import numbering as nb

    async def body(db):
        await db.invoices.insert_one({"id": "inv_old", "number": "INV-2026-0001"})
        await db.invoices.insert_one({"id": "inv_old2", "number": "INV-2026-0002"})
        # aturan diubah ke reset "tidak pernah" → scope counter baru mulai dari 1
        await db.numbering_rules.insert_one({"key": "invoice", "reset": "never", "pattern": "{PREFIX}-2026-{SEQ}"})
        return await nb.generate(db, "invoice")
    assert tmpdb(body) == "INV-2026-0003"


def test_receipt_totals_frozen_at_that_payment(tmpdb):
    from services.documents import paid_upto

    async def body(db):
        await db.payments.insert_many([
            {"id": "p1", "booking_id": "b", "amount": 450000, "paid_at": "2031-01-01T01:00:00+00:00"},
            {"id": "p2", "booking_id": "b", "amount": 1050000, "paid_at": "2031-01-05T01:00:00+00:00"}])
        return await paid_upto(db, {"id": "p1", "booking_id": "b"}), await paid_upto(db, {"id": "p2", "booking_id": "b"})
    assert tmpdb(body) == (450000, 1500000)


def test_bi_kpis_include_realized_maintenance(tmpdb):
    from services.analytics import _kpis_for

    async def body(db):
        await db.payments.insert_one({"id": "p", "amount": 1000000, "paid_at": "2031-01-10T03:00:00+00:00"})
        await db.maintenance_records.insert_many([
            {"id": "m1", "status": "done", "cost": 400000, "completed_at": "2031-01-12T03:00:00+00:00"},
            {"id": "m2", "status": "scheduled", "cost": 999999, "scheduled_date": "2031-01-15"}])
        return await _kpis_for(db, "2031-01-01", "2031-02-01")
    k = tmpdb(body)
    assert k["expenses"] == 400000 and k["profit"] == 600000  # sama dgn Laporan Keuangan


# ------------------------------------------------------------------ API
def _login(email):
    try:
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": "demo12345"}, timeout=20)
    except requests.RequestException:
        pytest.skip("backend tidak hidup")
    if r.status_code != 200:
        pytest.skip(f"login {email} gagal ({r.status_code})")
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def owner():
    return _login("owner@demo.local")


@pytest.fixture(scope="module")
def db():
    if not ENV.get("MONGO_URL"):
        pytest.skip("MONGO_URL tidak tersedia")
    from pymongo import MongoClient
    return MongoClient(ENV["MONGO_URL"])[ENV.get("DB_NAME", "test_database")]


def test_public_meta_webhook_rejects_when_provider_not_meta(owner, db):
    cfg = (db.settings.find_one({"key": "wa_config"}) or {}).get("value") or {}
    if cfg.get("provider") == "meta_cloud":
        pytest.skip("provider aktif meta_cloud")
    r = requests.post(f"{API}/wa/webhook", json={"from": "6281299999999", "text": "palsu"}, timeout=20)
    assert r.status_code == 403
    assert not db.messages.find_one({"body": "palsu", "direction": "in"})


def test_cancelled_booking_invoice_icon_only_for_open_fee(owner, db):
    tag = f"r3{random.randint(10000, 99999)}"
    cust = f"cus_{tag}"
    now = datetime.now(timezone.utc)
    bks = [{"id": f"bk_{tag}{i}", "code": f"TST-{tag}{i}", "customer_id": cust, "status": "cancelled",
            "start_datetime": (now + timedelta(days=2000 + i)).isoformat(), "total_amount": 1000000,
            "paid_amount": 300000, "created_at": now.isoformat()} for i in (1, 2)]
    invs = [{"id": f"inv_{tag}a", "booking_id": bks[0]["id"], "kind": "dp", "status": "paid", "amount": 300000},
            {"id": f"inv_{tag}b", "booking_id": bks[1]["id"], "kind": "dp", "status": "paid", "amount": 300000},
            {"id": f"inv_{tag}c", "booking_id": bks[1]["id"], "type": "cancellation_fee", "status": "sent",
             "amount": 500000, "created_at": now.isoformat()}]
    db.bookings.insert_many([dict(b) for b in bks])
    db.invoices.insert_many([dict(i) for i in invs])
    try:
        r = requests.get(f"{API}/bookings", headers=owner, params={"customer_id": cust}, timeout=20)
        assert r.status_code == 200
        flags = {b["id"]: b["has_invoice"] for b in r.json()}
        assert flags == {bks[0]["id"]: False, bks[1]["id"]: True}
        r = requests.post(f"{API}/bookings/{bks[0]['id']}/send-invoice-wa", headers=owner, timeout=20)
        assert r.status_code == 404 and "tagihan terbuka" in r.json()["detail"]
    finally:
        db.bookings.delete_many({"customer_id": cust})
        db.invoices.delete_many({"id": {"$in": [i["id"] for i in invs]}})


def test_retry_endpoint_rejects_non_failed_message(owner, db):
    tag = f"r3{random.randint(10000, 99999)}"
    db.conversations.insert_one({"id": f"cnv_{tag}", "channel": "whatsapp", "contact_phone": "081299900077"})
    db.messages.insert_one({"id": f"msg_{tag}", "conversation_id": f"cnv_{tag}", "direction": "out",
                            "status": "sent", "body": "ok"})
    try:
        r = requests.post(f"{API}/conversations/cnv_{tag}/messages/msg_{tag}/retry", headers=owner, timeout=20)
        assert r.status_code == 400
    finally:
        db.conversations.delete_one({"id": f"cnv_{tag}"})
        db.messages.delete_one({"id": f"msg_{tag}"})


def test_layout_rejects_values_that_break_pdf(owner):
    for bad in ({"table": {"alignment": "diagonal"}}, {"table": {"grid_color": "zzz"}},
                {"sections": [{"key": "ngawur", "visible": True}]}):
        r = requests.put(f"{API}/doc-layouts/INVOICE", headers=owner, json=bad, timeout=20)
        assert r.status_code == 422, (bad, r.text)


def test_refund_has_no_receipt_and_void_invoice_not_sent(owner, db):
    tag = f"r3{random.randint(10000, 99999)}"
    db.payments.insert_one({"id": f"pay_{tag}", "booking_id": f"bk_{tag}", "amount": -150000, "type": "refund",
                            "method": "refund", "paid_at": datetime.now(timezone.utc).isoformat()})
    db.invoices.insert_one({"id": f"inv_{tag}", "booking_id": f"bk_{tag}", "number": f"TST-{tag}", "status": "void",
                            "kind": "full", "amount": 100000})
    try:
        r = requests.post(f"{API}/payments/pay_{tag}/receipt", headers=owner, timeout=20)
        assert r.status_code == 400 and "Refund" in r.json()["detail"]
        assert all(p["id"] != f"pay_{tag}" for p in requests.get(f"{API}/receipts", headers=owner, timeout=20).json())
        r = requests.post(f"{API}/invoices/inv_{tag}/send-wa", headers=owner, timeout=20)
        assert r.status_code == 400 and "dibatalkan" in r.json()["detail"]
    finally:
        db.payments.delete_one({"id": f"pay_{tag}"})
        db.invoices.delete_one({"id": f"inv_{tag}"})

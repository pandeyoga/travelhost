"""Tests for iteration_104:
- Real broadcast via mock provider (background sender + progress polling)
- Anti-double-send guard
- Broadcast message appears in Inbox conversations with rendered {customer_name}
- Inbox wa-media (upload PNG, caption, size/mime validation, channel guard)
- Invoice send-wa (finance) + booking send-invoice-wa; auth/role guards
"""
import base64
import io
import os
import time

import pytest
import requests

def _get_base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    # Fallback: read from frontend/.env
    try:
        with open("/app/frontend/.env") as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE = _get_base()
OWNER = {"email": "owner@demo.local", "password": "demo12345"}
DRIVER = {"email": "driver@demo.local", "password": "demo12345"}


def _login(creds):
    r = requests.post(f"{BASE}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def owner_headers():
    return {"Authorization": f"Bearer {_login(OWNER)}"}


@pytest.fixture(scope="module")
def driver_headers():
    return {"Authorization": f"Bearer {_login(DRIVER)}"}


@pytest.fixture(scope="module", autouse=True)
def wa_provider_mock(owner_headers):
    # Switch to mock provider for fast, deterministic sends
    r = requests.patch(f"{BASE}/api/wa/config", json={"provider": "mock"},
                       headers=owner_headers, timeout=15)
    assert r.status_code == 200, r.text
    yield
    # IMPORTANT: restore to openwa at the end
    requests.patch(f"{BASE}/api/wa/config", json={"provider": "openwa"},
                   headers=owner_headers, timeout=15)


# ---------- Broadcast ----------
class TestBroadcast:
    def test_create_and_send_broadcast_mock(self, owner_headers):
        title = f"TEST_bc_{int(time.time())}"
        body = {"title": title, "message": "Halo {customer_name}, promo akhir pekan!",
                "segment_stage": None, "segment_source": None}
        r = requests.post(f"{BASE}/api/broadcasts", json=body, headers=owner_headers, timeout=15)
        assert r.status_code == 200, r.text
        bc = r.json()
        assert bc["status"] == "draft"
        assert bc["recipients_count"] >= 1, "seed harus punya lead ber-phone"
        bc_id = bc["id"]

        r = requests.post(f"{BASE}/api/broadcasts/{bc_id}/send", headers=owner_headers, timeout=15)
        assert r.status_code == 200, r.text
        started = r.json()
        assert started["status"] == "sending"
        assert started["recipients_count"] > 0
        recips = started["recipients_count"]

        # Poll for completion
        final = None
        for _ in range(30):
            time.sleep(0.5)
            lst = requests.get(f"{BASE}/api/broadcasts", headers=owner_headers, timeout=15).json()
            match = [x for x in lst if x["id"] == bc_id]
            if match and match[0].get("status") == "sent":
                final = match[0]
                break
        assert final is not None, f"broadcast tidak selesai dalam 15s: last={match if match else None}"
        assert final["sent_count"] > 0
        assert final.get("failed_count", 0) == 0
        pytest.bc_id = bc_id
        pytest.bc_msg = body["message"]
        pytest.bc_recips = recips

    def test_anti_double_send(self, owner_headers):
        bc_id = getattr(pytest, "bc_id", None)
        assert bc_id
        r = requests.post(f"{BASE}/api/broadcasts/{bc_id}/send", headers=owner_headers, timeout=15)
        assert r.status_code == 400
        assert "sudah" in r.text.lower() or "sedang" in r.text.lower()

    def test_broadcast_reaches_inbox_with_rendered_var(self, owner_headers):
        # After broadcast, at least one conversation should have the broadcast preview
        r = requests.get(f"{BASE}/api/conversations?channel=whatsapp", headers=owner_headers, timeout=15)
        assert r.status_code == 200
        convs = r.json()
        assert len(convs) > 0
        # Find one whose preview contains 'promo akhir pekan' and rendered name (no literal {customer_name})
        found = None
        for c in convs:
            prev = c.get("last_message_preview") or ""
            if "promo akhir pekan" in prev.lower():
                found = c
                break
        assert found is not None, "Tidak ada conversation WA berisi pesan broadcast"
        assert "{customer_name}" not in (found.get("last_message_preview") or ""), \
            "variabel harus ter-render, bukan literal"

    def test_send_broadcast_unauth(self):
        # Some random id — the auth check must trigger before existence check.
        r = requests.post(f"{BASE}/api/broadcasts/xxx/send", timeout=15)
        assert r.status_code in (401, 403)


# ---------- Inbox wa-media ----------
class TestInboxWaMedia:
    def _get_wa_conv(self, owner_headers):
        r = requests.get(f"{BASE}/api/conversations?channel=whatsapp", headers=owner_headers, timeout=15)
        assert r.status_code == 200
        convs = r.json()
        assert convs, "Butuh setidaknya 1 WA conversation"
        return convs[0]["id"]

    def _tiny_png(self):
        # 1x1 transparent PNG
        return base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4"
            "nGNgAAIAAAUAAeImBZsAAAAASUVORK5CYII="
        )

    def test_upload_png_success(self, owner_headers):
        cid = self._get_wa_conv(owner_headers)
        files = {"file": ("test.png", self._tiny_png(), "image/png")}
        data = {"caption": "tes gambar"}
        r = requests.post(f"{BASE}/api/conversations/{cid}/wa-media",
                          files=files, data=data, headers=owner_headers, timeout=20)
        assert r.status_code == 200, r.text
        msg = r.json()
        assert msg.get("body") == "tes gambar"
        assert (msg.get("attachment") or {}).get("filename") == "test.png"

    def test_reject_txt(self, owner_headers):
        cid = self._get_wa_conv(owner_headers)
        files = {"file": ("bad.txt", b"hello", "text/plain")}
        r = requests.post(f"{BASE}/api/conversations/{cid}/wa-media",
                          files=files, headers=owner_headers, timeout=15)
        assert r.status_code == 400

    def test_reject_oversize(self, owner_headers):
        cid = self._get_wa_conv(owner_headers)
        big = b"\x89PNG\r\n\x1a\n" + b"0" * (9 * 1024 * 1024)
        files = {"file": ("big.png", big, "image/png")}
        r = requests.post(f"{BASE}/api/conversations/{cid}/wa-media",
                          files=files, headers=owner_headers, timeout=30)
        assert r.status_code == 400

    def test_non_whatsapp_channel_400(self, owner_headers):
        # Create an internal conversation
        r = requests.post(f"{BASE}/api/conversations",
                          json={"channel": "internal", "contact_name": "TEST_intern",
                                "subject": "test"},
                          headers=owner_headers, timeout=15)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        files = {"file": ("test.png", self._tiny_png(), "image/png")}
        r = requests.post(f"{BASE}/api/conversations/{cid}/wa-media",
                          files=files, headers=owner_headers, timeout=15)
        assert r.status_code == 400
        assert "whatsapp" in r.text.lower()

    def test_unauth(self):
        r = requests.post(f"{BASE}/api/conversations/xxx/wa-media", timeout=15)
        assert r.status_code in (401, 403, 422)  # 422 acceptable if requires file — but before auth? check


# ---------- Invoice send-wa ----------
class TestInvoiceWa:
    def _pick_booking(self, owner_headers):
        r = requests.get(f"{BASE}/api/bookings", headers=owner_headers, timeout=15)
        assert r.status_code == 200
        bookings = r.json()
        for b in bookings:
            if b.get("status") in ("confirmed", "completed"):
                return b
        pytest.skip("Tidak ada booking confirmed/completed")

    def test_create_invoice_and_send_wa(self, owner_headers):
        booking = self._pick_booking(owner_headers)
        r = requests.post(f"{BASE}/api/invoices", json={"booking_id": booking["id"]},
                          headers=owner_headers, timeout=15)
        assert r.status_code == 200, r.text
        inv = r.json()
        assert inv["status"] == "draft"
        inv_id = inv["id"]

        r = requests.post(f"{BASE}/api/invoices/{inv_id}/send-wa",
                          headers=owner_headers, timeout=30)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out.get("ok") is True
        assert out.get("number") == inv["number"]
        assert out.get("status") in ("sent", "delivered", "read")

        # GET → status now 'sent'
        r = requests.get(f"{BASE}/api/invoices/{inv_id}", headers=owner_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "sent"
        pytest.inv_id = inv_id
        pytest.booking_id = booking["id"]

    def test_booking_send_invoice_wa(self, owner_headers):
        bid = getattr(pytest, "booking_id", None)
        assert bid
        r = requests.post(f"{BASE}/api/bookings/{bid}/send-invoice-wa",
                          headers=owner_headers, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_booking_without_invoice_404(self, owner_headers):
        # find a booking that has NO invoice
        bookings = requests.get(f"{BASE}/api/bookings", headers=owner_headers, timeout=15).json()
        invs = requests.get(f"{BASE}/api/invoices?limit=1000", headers=owner_headers, timeout=15).json()
        with_inv = {i.get("booking_id") for i in invs}
        target = None
        for b in bookings:
            if b["id"] not in with_inv:
                target = b["id"]
                break
        if not target:
            pytest.skip("Semua booking sudah punya invoice")
        r = requests.post(f"{BASE}/api/bookings/{target}/send-invoice-wa",
                          headers=owner_headers, timeout=15)
        assert r.status_code == 404
        assert "belum ada invoice" in r.text.lower()

    def test_send_wa_no_token(self):
        r = requests.post(f"{BASE}/api/invoices/xxx/send-wa", timeout=15)
        assert r.status_code in (401, 403)

    def test_driver_forbidden(self, driver_headers, owner_headers):
        inv_id = getattr(pytest, "inv_id", None)
        assert inv_id
        r = requests.post(f"{BASE}/api/invoices/{inv_id}/send-wa",
                          headers=driver_headers, timeout=15)
        assert r.status_code == 403


# ---------- Regression ----------
class TestRegression:
    def test_wa_test_send_mock(self, owner_headers):
        r = requests.post(f"{BASE}/api/wa/test-send",
                          json={"to_phone": "+628123456789", "text": "ping"},
                          headers=owner_headers, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_openwa_status_running(self, owner_headers):
        r = requests.get(f"{BASE}/api/wa/openwa/status", headers=owner_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # running=true EXPECTED, connected=false EXPECTED (QR not scanned)
        assert "running" in data

"""Backend tests for OpenWA WhatsApp integration (iteration).

Covers:
- Auth (owner login)
- /api/wa/config GET+PATCH (provider validation)
- /api/wa/openwa/status, /qr auth+shape
- /api/wa/openwa/restart (fresh=false only)
- /api/wa/test-send fail-gracefully when session not linked
- /api/wa/openwa-webhook: auth key, inbound msg → lead+inbox, group ignored,
  non-message event ignored, regression provider mock send
"""
import os
import time
import uuid

import pytest
import requests

def _load_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.strip().startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        return None
    return None


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
API = f"{BASE_URL}/api"
OPENWA_KEY = "rahaza-openwa-key-2026"


@pytest.fixture(scope="module")
def owner_token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": "owner@demo.local", "password": "demo12345"},
                      timeout=15)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def auth(owner_token):
    return {"Authorization": f"Bearer {owner_token}"}


# --- Auth login ------------------------------------------------------------
def test_login_owner(owner_token):
    assert isinstance(owner_token, str) and len(owner_token) > 10


# --- WA config -------------------------------------------------------------
def test_get_wa_config(auth):
    r = requests.get(f"{API}/wa/config", headers=auth, timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "provider" in d


def test_patch_wa_config_openwa(auth):
    r = requests.patch(f"{API}/wa/config", headers=auth,
                       json={"provider": "openwa"}, timeout=15)
    assert r.status_code == 200
    assert r.json().get("provider") == "openwa"


def test_patch_wa_config_invalid(auth):
    r = requests.patch(f"{API}/wa/config", headers=auth,
                       json={"provider": "xyz"}, timeout=15)
    assert r.status_code == 400


# --- OpenWA sidecar status/qr ---------------------------------------------
def test_openwa_status_requires_auth():
    r = requests.get(f"{API}/wa/openwa/status", timeout=15)
    assert r.status_code in (401, 403)


def test_openwa_status(auth):
    # allow sidecar boot time
    running = False
    data = {}
    deadline = time.time() + 40
    while time.time() < deadline:
        r = requests.get(f"{API}/wa/openwa/status", headers=auth, timeout=20)
        assert r.status_code == 200
        data = r.json()
        if data.get("running"):
            running = True
            break
        time.sleep(3)
    assert data.get("installed") is True, data
    assert running, f"sidecar not running: {data}"
    # connected must not be true (no scan)
    assert data.get("connected") is False
    assert data.get("state") in (None, "STARTING", "AUTHENTICATING", "UNPAIRED", "UNPAIRED_IDLE", "CONFLICT", "OPENING", "PAIRING", "TIMEOUT")


def test_openwa_qr_requires_auth():
    r = requests.get(f"{API}/wa/openwa/qr", timeout=15)
    assert r.status_code in (401, 403)


def test_openwa_qr(auth):
    qr = ""
    deadline = time.time() + 40
    while time.time() < deadline:
        r = requests.get(f"{API}/wa/openwa/qr", headers=auth, timeout=15)
        assert r.status_code == 200
        qr = r.json().get("qr") or ""
        if qr:
            break
        time.sleep(3)
    assert qr, "QR did not become available in time"


# --- Restart (fresh=false only) -------------------------------------------
def test_openwa_restart(auth):
    r = requests.post(f"{API}/wa/openwa/restart?fresh=false", headers=auth, timeout=45)
    assert r.status_code == 200
    d = r.json()
    assert d.get("installed") is True
    # give it a moment then check status
    time.sleep(2)
    r2 = requests.get(f"{API}/wa/openwa/status", headers=auth, timeout=20)
    assert r2.status_code == 200


# --- Test send fails gracefully when not connected ------------------------
def test_wa_test_send_openwa_fail_gracefully(auth):
    # ensure provider is openwa
    requests.patch(f"{API}/wa/config", headers=auth,
                   json={"provider": "openwa"}, timeout=15)
    r = requests.post(f"{API}/wa/test-send", headers=auth,
                      json={"to_phone": "6281234567890", "text": "tes"}, timeout=45)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is False
    assert d.get("status") == "failed"
    assert d.get("error")


# --- Webhook auth ----------------------------------------------------------
def test_openwa_webhook_no_key():
    r = requests.post(f"{API}/wa/openwa-webhook",
                      json={"event": "onMessage", "data": {}}, timeout=10)
    assert r.status_code == 403


def test_openwa_webhook_wrong_key():
    r = requests.post(f"{API}/wa/openwa-webhook?key=WRONG",
                      json={"event": "onMessage", "data": {}}, timeout=10)
    assert r.status_code == 403


# --- Webhook inbound → lead + inbox ---------------------------------------
def test_openwa_webhook_inbound_creates_lead_and_conversation(auth):
    unique_phone = "628111222" + str(uuid.uuid4().int)[:3]
    unique_name = f"Bu Sari {uuid.uuid4().hex[:4]}"
    payload = {
        "event": "onMessage",
        "data": {
            "from": f"{unique_phone}@c.us",
            "body": "Halo mau sewa bus",
            "sender": {"pushname": unique_name},
            "id": f"false_{unique_phone}@c.us_XYZ",
        },
    }
    r = requests.post(f"{API}/wa/openwa-webhook?key={OPENWA_KEY}",
                      json=payload, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "ok"
    assert body.get("received") == 1

    # verify lead exists
    time.sleep(1.5)
    lr = requests.get(f"{API}/leads", headers=auth,
                      params={"q": unique_phone}, timeout=15)
    assert lr.status_code == 200, lr.text
    leads = lr.json()
    leads_list = leads if isinstance(leads, list) else leads.get("items") or leads.get("data") or []
    matched = [l for l in leads_list if unique_phone in (l.get("phone") or "")]
    assert matched, f"lead not found for phone {unique_phone}: got {leads_list[:2]}"
    assert (matched[0].get("source") or "").lower() == "whatsapp"

    # verify inbox conversation with at least inbound + auto-reply
    cr = requests.get(f"{API}/conversations", headers=auth, timeout=15)
    assert cr.status_code == 200
    convs = cr.json()
    convs_list = convs if isinstance(convs, list) else convs.get("items") or []
    # find conversation matching phone
    found = None
    for c in convs_list:
        phone = (c.get("contact_phone") or "")
        if unique_phone in phone or unique_name in (c.get("contact_name") or ""):
            found = c
            break
    assert found, f"conversation not found for {unique_phone}/{unique_name}"
    assert (found.get("channel") or "").lower() == "whatsapp"
    # check message count if provided
    mc = found.get("message_count") or found.get("messages_count")
    if mc is not None:
        assert mc >= 2, f"expected >=2 messages, got {mc}"


def test_openwa_webhook_non_message_event_ignored():
    r = requests.post(f"{API}/wa/openwa-webhook?key={OPENWA_KEY}",
                      json={"event": "qr", "data": {"qr": "abc"}}, timeout=10)
    assert r.status_code == 200
    assert r.json().get("received") == 0


def test_openwa_webhook_group_message_ignored():
    r = requests.post(f"{API}/wa/openwa-webhook?key={OPENWA_KEY}",
                      json={"event": "onMessage",
                            "data": {"from": "12036302@g.us", "body": "x"}},
                      timeout=10)
    assert r.status_code == 200
    assert r.json().get("received") == 0


# --- Regression: mock provider still works --------------------------------
def test_wa_send_mock_still_works(auth):
    r = requests.patch(f"{API}/wa/config", headers=auth,
                       json={"provider": "mock"}, timeout=15)
    assert r.status_code == 200
    try:
        s = requests.post(f"{API}/wa/test-send", headers=auth,
                          json={"to_phone": "6281234567890", "text": "tes mock"},
                          timeout=15)
        assert s.status_code == 200
        d = s.json()
        assert d.get("ok") is True
        assert d.get("status") == "sent"
    finally:
        # reset provider back to openwa per instructions
        requests.patch(f"{API}/wa/config", headers=auth,
                       json={"provider": "openwa"}, timeout=15)

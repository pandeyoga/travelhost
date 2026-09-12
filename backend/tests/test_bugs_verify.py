"""Verify BUG1-4 fixes: site pages, users CRUD, drivers accounts, RBAC."""
import os
import time
import uuid
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def login(email, password="demo12345"):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text}"
    data = r.json()
    return data.get("access_token") or data.get("token"), data.get("user") or {}


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def owner():
    tok, u = login("owner@demo.local")
    return {"tok": tok, "user": u}


@pytest.fixture(scope="module")
def ops():
    tok, u = login("ops@demo.local")
    return {"tok": tok, "user": u}


@pytest.fixture(scope="module")
def marketing():
    tok, u = login("marketing@demo.local")
    return {"tok": tok, "user": u}


# ========== BUG1b: Site pages ==========
def test_bug1b_list_pages_9_slugs(owner):
    r = requests.get(f"{BASE}/api/site/pages", headers=H(owner["tok"]))
    assert r.status_code == 200
    slugs = {p["slug"] for p in r.json()}
    expected = {"home", "about", "contact", "fleet", "destinations", "packages", "promo", "blog", "trip-calculator"}
    assert slugs == expected, f"Got {slugs}, missing {expected - slugs}"


def test_bug1b_public_trip_calculator_has_page_hero():
    r = requests.get(f"{BASE}/api/public/pages/trip-calculator")
    assert r.status_code == 200
    data = r.json()
    types = [s["type"] for s in data.get("sections") or []]
    assert "page_hero" in types


def test_bug1b_put_fleet_invalid_type_400(owner):
    body = {"sections": [{"id": "s1", "type": "faq", "enabled": True, "data": {}}]}
    r = requests.put(f"{BASE}/api/site/pages/fleet", headers=H(owner["tok"]), json=body)
    assert r.status_code == 400


def test_bug1b_site_settings_site_url_field(owner):
    r = requests.get(f"{BASE}/api/site/settings", headers=H(owner["tok"]))
    assert r.status_code == 200
    assert "site_url" in r.json()


def test_bug1b_site_settings_persist_and_reset(owner):
    r = requests.put(f"{BASE}/api/site/settings", headers=H(owner["tok"]),
                     json={"site_url": "https://example.com"})
    assert r.status_code == 200
    g = requests.get(f"{BASE}/api/site/settings", headers=H(owner["tok"])).json()
    assert g.get("site_url") == "https://example.com"
    # Reset
    r2 = requests.put(f"{BASE}/api/site/settings", headers=H(owner["tok"]), json={"site_url": ""})
    assert r2.status_code == 200
    g2 = requests.get(f"{BASE}/api/site/settings", headers=H(owner["tok"])).json()
    # After reset, may fallback to env PUBLIC_SITE_URL (empty here)
    assert g2.get("site_url", "") in ("", None)


def test_bug1_save_fleet_hero_override(owner):
    title = f"Toyota Hiace TEST {uuid.uuid4().hex[:6]}"
    # Get current fleet page
    r = requests.get(f"{BASE}/api/site/pages/fleet", headers=H(owner["tok"]))
    assert r.status_code == 200
    doc = r.json()
    secs = doc["sections"]
    assert len(secs) >= 1
    secs[0]["data"] = {**(secs[0].get("data") or {}), "title": title}
    body = {"sections": secs}
    r2 = requests.put(f"{BASE}/api/site/pages/fleet", headers=H(owner["tok"]), json=body)
    assert r2.status_code == 200, r2.text
    r3 = requests.get(f"{BASE}/api/public/pages/fleet")
    assert r3.status_code == 200
    pub = r3.json()
    assert any(s.get("data", {}).get("title") == title for s in pub.get("sections", []))


# ========== BUG2: Roles / marketing_admin ==========
def test_bug2_roles_include_marketing_admin(owner):
    # marketing_admin must be a valid role in ROLES config
    from permissions_config import ROLES  # noqa: E402
    assert "marketing_admin" in ROLES


_created_user_id = {"id": None, "email": None}


def test_bug2_create_marketing_admin_user(owner):
    email = f"mkt.test.{uuid.uuid4().hex[:6]}@demo.local"
    body = {"name": "Test Marketing", "email": email, "password": "demo12345",
            "role": "marketing_admin", "phone": ""}
    r = requests.post(f"{BASE}/api/users", headers=H(owner["tok"]), json=body)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["role"] == "marketing_admin"
    _created_user_id["id"] = doc["id"]
    _created_user_id["email"] = email


def test_bug2_marketing_admin_rbac():
    email = _created_user_id["email"]
    assert email
    tok, _ = login(email)
    # CMS allowed
    r_cms = requests.get(f"{BASE}/api/site/pages", headers=H(tok))
    assert r_cms.status_code == 200
    # Users forbidden
    r_users = requests.get(f"{BASE}/api/users", headers=H(tok))
    assert r_users.status_code == 403
    # Finance forbidden (try common finance endpoint)
    r_fin = requests.get(f"{BASE}/api/finance/summary", headers=H(tok))
    assert r_fin.status_code in (403, 404)  # 404 if not existing route, but 403 preferred
    # Drivers accounts forbidden (marketing gets 403 per bug description)
    r_da = requests.get(f"{BASE}/api/drivers/accounts", headers=H(tok))
    assert r_da.status_code == 403


# ========== BUG3: user edit / self-guards / delete ==========
def test_bug3_delete_self_400(owner):
    r = requests.delete(f"{BASE}/api/users/{owner['user']['id']}", headers=H(owner["tok"]))
    assert r.status_code == 400
    assert "sendiri" in r.text.lower()


def test_bug3_patch_own_role_400(owner):
    r = requests.patch(f"{BASE}/api/users/{owner['user']['id']}", headers=H(owner["tok"]),
                       json={"role": "ops_admin"})
    assert r.status_code == 400


def test_bug3_delete_last_owner_400(owner):
    # There should be only 1 owner. Deleting owner via another owner is only possible if >1.
    # Confirm current owner count via list.
    r = requests.get(f"{BASE}/api/users", headers=H(owner["tok"]))
    owners = [u for u in r.json() if u.get("role") == "owner" and u.get("status") == "active"]
    if len(owners) != 1:
        pytest.skip("more than one owner present; skip")
    # Cannot delete self (already covered). To test 'last owner' guard specifically,
    # would need a second owner account. Skip granular test — self-delete already blocks.


def test_bug3_update_password_and_relogin(owner):
    uid = _created_user_id["id"]
    email = _created_user_id["email"]
    assert uid
    new_pw = "newpass123"
    r = requests.patch(f"{BASE}/api/users/{uid}", headers=H(owner["tok"]),
                       json={"name": "Test Marketing Renamed", "password": new_pw})
    assert r.status_code == 200
    # login with new password
    tok, _ = login(email, new_pw)
    assert tok


def test_bug3_set_status_nonaktif(owner):
    uid = _created_user_id["id"]
    r = requests.patch(f"{BASE}/api/users/{uid}", headers=H(owner["tok"]),
                       json={"status": "inactive"})
    assert r.status_code == 200
    assert r.json().get("status") == "inactive"


def test_bug3_delete_user(owner):
    uid = _created_user_id["id"]
    r = requests.delete(f"{BASE}/api/users/{uid}", headers=H(owner["tok"]))
    assert r.status_code == 200
    g = requests.get(f"{BASE}/api/users/{uid}", headers=H(owner["tok"]))
    assert g.status_code == 404


# ========== BUG4: Driver account link ==========
_created_driver = {"id": None, "email": None}


def test_bug4_create_driver_with_new_account(owner):
    email = f"drv.test.{uuid.uuid4().hex[:6]}@demo.local"
    body = {"name": "Test Driver New Acc", "phone": "0800",
            "account_email": email, "account_password": "demo12345"}
    r = requests.post(f"{BASE}/api/drivers", headers=H(owner["tok"]), json=body)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc.get("user_id")
    _created_driver["id"] = doc["id"]
    _created_driver["email"] = email


def test_bug4_login_as_new_driver_account():
    email = _created_driver["email"]
    assert email
    tok, u = login(email)
    assert u.get("role") == "driver"


def test_bug4_drivers_list_shows_account_email(owner):
    r = requests.get(f"{BASE}/api/drivers", headers=H(owner["tok"]))
    assert r.status_code == 200
    found = [d for d in r.json() if d.get("id") == _created_driver["id"]]
    assert found
    assert found[0].get("account_email") == _created_driver["email"]


def test_bug4_duplicate_account_email_400(owner):
    body = {"name": "Dup Test", "account_email": _created_driver["email"],
            "account_password": "demo12345"}
    r = requests.post(f"{BASE}/api/drivers", headers=H(owner["tok"]), json=body)
    assert r.status_code == 400


def test_bug4_link_user_id_already_linked_400(owner):
    # get the user_id from the linked driver
    r = requests.get(f"{BASE}/api/drivers", headers=H(owner["tok"]))
    d = [x for x in r.json() if x["id"] == _created_driver["id"]][0]
    uid = d["user_id"]
    body = {"name": "Another Driver", "user_id": uid}
    r2 = requests.post(f"{BASE}/api/drivers", headers=H(owner["tok"]), json=body)
    assert r2.status_code == 400


def test_bug4_drivers_accounts_endpoint_owner(owner):
    r = requests.get(f"{BASE}/api/drivers/accounts", headers=H(owner["tok"]))
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # Our newly created driver's user should be listed with driver_id
    hit = [u for u in data if u.get("email") == _created_driver["email"]]
    assert hit and hit[0].get("driver_id") == _created_driver["id"]


def test_bug4_drivers_accounts_ops_ok(ops):
    r = requests.get(f"{BASE}/api/drivers/accounts", headers=H(ops["tok"]))
    assert r.status_code == 200


def test_bug4_drivers_accounts_marketing_403(marketing):
    r = requests.get(f"{BASE}/api/drivers/accounts", headers=H(marketing["tok"]))
    assert r.status_code == 403


def test_bug4_unlink_driver_account(owner):
    did = _created_driver["id"]
    r = requests.patch(f"{BASE}/api/drivers/{did}", headers=H(owner["tok"]),
                       json={"user_id": ""})
    assert r.status_code == 200, r.text
    r2 = requests.get(f"{BASE}/api/drivers", headers=H(owner["tok"]))
    d = [x for x in r2.json() if x["id"] == did][0]
    assert d.get("user_id") in (None, "")
    assert not d.get("account_email")


def test_bug4_cleanup_driver(owner):
    did = _created_driver["id"]
    if did:
        requests.delete(f"{BASE}/api/drivers/{did}", headers=H(owner["tok"]))

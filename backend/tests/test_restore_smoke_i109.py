"""Restore smoke tests (iteration 109) — health, public booking config, ERP auth, public pages."""
import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --- module: health ---
def test_root_health(api):
    r = api.get(f"{BASE_URL}/api/", timeout=30)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert data.get("status") == "ok"


# --- module: public booking config (airport transfer routes) ---
def test_public_booking_config_routes(api):
    r = api.get(f"{BASE_URL}/api/public/booking/config", timeout=30)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    routes = data.get("routes")
    assert isinstance(routes, list)
    assert len(routes) == 3, f"expected 3 seeded transfer routes, got {len(routes)}"
    codes = sorted(x["code"] for x in routes)
    assert codes == ["BDO-CGK", "BDO-KJT", "CGK-BDO"], codes
    for x in routes:
        assert x["id"] and x["from_label"] and x["to_label"]
        assert isinstance(x["from_price"], (int, float)) and x["from_price"] > 0
        assert "_id" not in x
    services = [s["value"] for s in data.get("services", [])]
    assert "airport_transfer" in services


# --- module: ERP auth ---
def test_login_owner_and_me(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": "owner@demo.local", "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text[:400]
    body = r.json()
    token = body.get("access_token") or body.get("token")
    assert token, body
    me = api.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    assert me.status_code == 200, me.text[:300]
    assert me.json().get("email") == "owner@demo.local"


def test_login_wrong_password(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": "owner@demo.local", "password": "wrong"}, timeout=30)
    assert r.status_code in (400, 401), r.status_code


# --- module: public content endpoints used by public pages ---
@pytest.mark.parametrize("path", [
    "/api/public/company",
    "/api/public/theme",
    "/api/public/fleet",
    "/api/public/destinations",
    "/api/public/packages",
    "/api/public/promos",
    "/api/public/articles",
    "/api/public/testimonials",
    "/api/public/stats",
])
def test_public_endpoints_ok(api, path):
    r = api.get(f"{BASE_URL}{path}", timeout=30)
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"


# --- module: public availability search (free date outside seeded-full window) ---
def test_public_availability_search_daily(api):
    payload = {"service": "daily_rental", "start_datetime": "2026-10-05T08:00",
               "end_datetime": "2026-10-06T08:00", "pax": 6}
    r = api.post(f"{BASE_URL}/api/public/booking/search", json=payload, timeout=40)
    assert r.status_code == 200, r.text[:400]
    data = r.json()
    assert isinstance(data.get("options"), list), data
    assert len(data["options"]) > 0, "no available units on a free date"
    assert data["search"]["service"] == "daily_rental"


def test_public_availability_search_airport_route(api):
    cfg = api.get(f"{BASE_URL}/api/public/booking/config", timeout=30).json()
    route = cfg["routes"][0]
    payload = {"service": "airport_transfer", "start_datetime": "2026-10-05T08:00",
               "route_id": route["id"], "pax": 4}
    r = api.post(f"{BASE_URL}/api/public/booking/search", json=payload, timeout=40)
    assert r.status_code == 200, r.text[:400]
    data = r.json()
    assert data["search"]["route"]["id"] == route["id"]
    assert isinstance(data.get("options"), list) and len(data["options"]) > 0

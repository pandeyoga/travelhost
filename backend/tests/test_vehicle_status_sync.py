"""E2E backend tests for Vehicle status auto-sync (lifecycle vs operational).

Scenarios covered:
- POST /api/vehicles saves status "available" and "inactive" (lifecycle-only field from UI).
- PATCH /api/vehicles/{id} status transitions (available <-> inactive).
- Trip lifecycle syncs vehicle & driver status (on_trip / available / online / offline).
- Maintenance in_progress sets vehicle "maintenance"; complete/done -> "available".
- PATCH without status field does NOT clobber operational status (on_trip).
- Public /api/public/fleet respects publishable_filter (owned + available + publish_to_web).
- /api/public/booking/quote reports available=false when vehicle is busy in window.
"""
import uuid
import os
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests

def _load_frontend_env():
    path = "/app/frontend/.env"
    if os.path.exists(path):
        with open(path) as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    return ""


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_env()).rstrip("/")
API = f"{BASE_URL}/api"

OWNER = {"email": "owner@demo.local", "password": "demo12345"}
DRIVER = {"email": "driver@demo.local", "password": "demo12345"}

TEST_TAG = f"TEST_{int(time.time())}"


# ---------- helpers ----------
def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def owner_headers():
    return {"Authorization": f"Bearer {_login(OWNER)}"}


@pytest.fixture(scope="module")
def driver_headers():
    return {"Authorization": f"Bearer {_login(DRIVER)}"}


@pytest.fixture(scope="module")
def created(owner_headers):
    """Create vehicle + customer + driver-record; cleanup at end."""
    state = {"vehicle_id": None, "customer_id": None, "driver_id": None,
             "booking_ids": [], "trip_ids": [], "maintenance_ids": []}
    # Vehicle
    tag = uuid.uuid4().hex[:6].upper()
    body = {
        "name": f"{TEST_TAG}_{tag}", "plate_number": f"D {tag} TS",
        "type": "hiace_premio", "capacity": 12, "status": "available",
        "ownership": "owned", "publish_to_web": True, "year": 2023, "color": "Putih",
    }
    r = requests.post(f"{API}/vehicles", json=body, headers=owner_headers, timeout=30)
    assert r.status_code == 200, r.text
    state["vehicle_id"] = r.json()["id"]

    # Customer (phone must be unique across parallel workers)
    phone_suffix = uuid.uuid4().hex[:8]
    r = requests.post(f"{API}/customers",
                      json={"name": f"{TEST_TAG}_cust_{tag}",
                            "phone": f"0812{phone_suffix}"},
                      headers=owner_headers, timeout=30)
    assert r.status_code == 200, r.text
    state["customer_id"] = r.json()["id"]

    # Fresh driver record so we can assert on/offline transitions cleanly.
    r = requests.post(f"{API}/drivers",
                      json={"name": f"{TEST_TAG}_drv_{tag}",
                            "phone": f"08120{tag[:6]}"},
                      headers=owner_headers, timeout=30)
    assert r.status_code == 200, r.text
    state["driver_id"] = r.json()["id"]

    yield state

    # Cleanup
    for tid in state["trip_ids"]:
        requests.delete(f"{API}/trips/{tid}", headers=owner_headers, timeout=10)
    for bid in state["booking_ids"]:
        # cancel/delete
        requests.post(f"{API}/bookings/{bid}/cancel", headers=owner_headers,
                      json={"reason": "test cleanup"}, timeout=10)
        requests.delete(f"{API}/bookings/{bid}", headers=owner_headers, timeout=10)
    for mid in state["maintenance_ids"]:
        requests.delete(f"{API}/maintenance/{mid}", headers=owner_headers, timeout=10)
    if state["vehicle_id"]:
        requests.delete(f"{API}/vehicles/{state['vehicle_id']}",
                        headers=owner_headers, timeout=10)
    if state.get("driver_id"):
        requests.delete(f"{API}/drivers/{state['driver_id']}",
                        headers=owner_headers, timeout=10)
    if state.get("customer_id"):
        requests.delete(f"{API}/customers/{state['customer_id']}",
                        headers=owner_headers, timeout=10)


def _get_vehicle(vid, headers):
    r = requests.get(f"{API}/vehicles/{vid}", headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


def _create_booking(headers, state, start_offset_days=1, dur_hours=6):
    start = datetime.now(timezone.utc) + timedelta(days=start_offset_days)
    end = start + timedelta(hours=dur_hours)
    body = {
        "customer_id": state["customer_id"],
        "vehicle_id": state["vehicle_id"],
        "driver_id": state["driver_id"],
        "start_datetime": start.isoformat(),
        "end_datetime": end.isoformat(),
        "origin": "Bandung", "destination": "Jakarta",
        "base_price": 1500000,
    }
    r = requests.post(f"{API}/bookings", json=body, headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    bk = r.json()
    state["booking_ids"].append(bk["id"])
    return bk


# ---------- tests ----------
class TestVehicleLifecycle:
    def test_create_vehicle_default_available(self, created):
        v = _get_vehicle(created["vehicle_id"],
                         {"Authorization": f"Bearer {_login(OWNER)}"})
        assert v["status"] == "available"
        assert v["ownership"] == "owned"
        assert v["publish_to_web"] is True

    def test_patch_lifecycle_inactive_then_active(self, owner_headers, created):
        vid = created["vehicle_id"]
        r = requests.patch(f"{API}/vehicles/{vid}", json={"status": "inactive"},
                           headers=owner_headers, timeout=20)
        assert r.status_code == 200, r.text
        assert _get_vehicle(vid, owner_headers)["status"] == "inactive"
        r = requests.patch(f"{API}/vehicles/{vid}", json={"status": "available"},
                           headers=owner_headers, timeout=20)
        assert r.status_code == 200
        assert _get_vehicle(vid, owner_headers)["status"] == "available"


class TestTripSync:
    def test_full_trip_lifecycle_updates_statuses(self, owner_headers, created):
        vid = created["vehicle_id"]
        # Create booking (auto-confirmed since vehicle_id given & no DP required)
        bk = _create_booking(owner_headers, created)
        assert bk["status"] in ("confirmed", "hold")

        # Assign via dispatch -> vehicle status on_trip
        r = requests.post(f"{API}/dispatch/{bk['id']}/assign",
                          json={"driver_id": created["driver_id"],
                                "vehicle_id": vid},
                          headers=owner_headers, timeout=30)
        assert r.status_code == 200, r.text
        trip = r.json()["trip"]
        created["trip_ids"].append(trip["id"])
        assert _get_vehicle(vid, owner_headers)["status"] == "on_trip"

        # Move trip to on_trip explicitly (also confirms driver online)
        r = requests.post(f"{API}/trips/{trip['id']}/status",
                          json={"status": "on_trip"},
                          headers=owner_headers, timeout=20)
        assert r.status_code == 200, r.text
        assert _get_vehicle(vid, owner_headers)["status"] == "on_trip"

        # Driver should be online
        r = requests.get(f"{API}/drivers/{created['driver_id']}",
                         headers=owner_headers, timeout=20)
        assert r.status_code == 200
        assert r.json().get("status") == "online"

        # === Edit vehicle WITHOUT status field while on_trip -> must NOT clobber ===
        r = requests.patch(f"{API}/vehicles/{vid}",
                           json={"notes": "edited during trip"},
                           headers=owner_headers, timeout=20)
        assert r.status_code == 200, r.text
        assert _get_vehicle(vid, owner_headers)["status"] == "on_trip", \
            "PATCH without status must NOT reset operational status"

        # Complete trip -> vehicle available, booking completed, driver offline
        r = requests.post(f"{API}/trips/{trip['id']}/status",
                          json={"status": "completed"},
                          headers=owner_headers, timeout=30)
        assert r.status_code == 200, r.text
        assert _get_vehicle(vid, owner_headers)["status"] == "available"
        r = requests.get(f"{API}/bookings/{bk['id']}", headers=owner_headers, timeout=10)
        assert r.json()["status"] == "completed"
        r = requests.get(f"{API}/drivers/{created['driver_id']}",
                         headers=owner_headers, timeout=10)
        assert r.json().get("status") == "offline"


class TestMaintenanceSync:
    def test_maintenance_in_progress_then_done(self, owner_headers, created):
        vid = created["vehicle_id"]
        today = datetime.now(timezone.utc).date().isoformat()
        end = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
        r = requests.post(f"{API}/maintenance",
                          json={"vehicle_id": vid, "type": "servis",
                                "title": f"{TEST_TAG} servis",
                                "start_date": today, "end_date": end,
                                "status": "in_progress"},
                          headers=owner_headers, timeout=20)
        assert r.status_code == 200, r.text
        mid = r.json()["id"]
        created["maintenance_ids"].append(mid)
        assert _get_vehicle(vid, owner_headers)["status"] == "maintenance"

        # Complete via PATCH status=done
        r = requests.patch(f"{API}/maintenance/{mid}", json={"status": "done"},
                           headers=owner_headers, timeout=20)
        assert r.status_code == 200, r.text
        assert _get_vehicle(vid, owner_headers)["status"] == "available"


class TestPublicSurfaces:
    def test_public_fleet_publishing_toggle(self, owner_headers, created):
        vid = created["vehicle_id"]
        # Ensure available + published
        requests.patch(f"{API}/vehicles/{vid}",
                       json={"status": "available", "publish_to_web": True},
                       headers=owner_headers, timeout=10)
        r = requests.get(f"{API}/public/fleet", timeout=20)
        assert r.status_code == 200
        ids = [v.get("id") for v in r.json()]
        assert vid in ids, "Published owned vehicle must appear in public fleet"

        # Set inactive -> should disappear
        requests.patch(f"{API}/vehicles/{vid}", json={"status": "inactive"},
                       headers=owner_headers, timeout=10)
        r = requests.get(f"{API}/public/fleet", timeout=20)
        assert vid not in [v.get("id") for v in r.json()]

        # Back to available; unpublish -> should disappear
        requests.patch(f"{API}/vehicles/{vid}",
                       json={"status": "available", "publish_to_web": False},
                       headers=owner_headers, timeout=10)
        r = requests.get(f"{API}/public/fleet", timeout=20)
        assert vid not in [v.get("id") for v in r.json()]

        # Restore for other tests
        requests.patch(f"{API}/vehicles/{vid}",
                       json={"publish_to_web": True},
                       headers=owner_headers, timeout=10)
        r = requests.get(f"{API}/public/fleet", timeout=20)
        assert vid in [v.get("id") for v in r.json()]

    def test_public_quote_marks_busy_vehicle_unavailable(self, owner_headers, created):
        vid = created["vehicle_id"]
        # Create a confirmed booking in a fresh window
        start = datetime.now(timezone.utc) + timedelta(days=5)
        end = start + timedelta(hours=8)
        r = requests.post(f"{API}/bookings",
                          json={"customer_id": created["customer_id"],
                                "vehicle_id": vid,
                                "driver_id": created["driver_id"],
                                "start_datetime": start.isoformat(),
                                "end_datetime": end.isoformat(),
                                "origin": "Bandung", "destination": "Jakarta",
                                "base_price": 1000000},
                          headers=owner_headers, timeout=30)
        assert r.status_code == 200, r.text
        bk = r.json()
        created["booking_ids"].append(bk["id"])

        # Query public quote for overlapping window
        r = requests.post(f"{API}/public/booking/quote",
                          json={"service": "daily_rental",
                                "vehicle_id": vid,
                                "start_datetime": start.isoformat(),
                                "end_datetime": end.isoformat(),
                                "pax": 4},
                          timeout=30)
        # Accept 200 with available=false OR 404 if unit hidden (publish must be True)
        if r.status_code == 200:
            data = r.json()
            assert data.get("available") is False, \
                f"Busy vehicle must be unavailable: {data}"
        else:
            pytest.fail(f"Unexpected quote status {r.status_code}: {r.text}")

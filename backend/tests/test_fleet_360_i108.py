"""Iteration 108 — Fleet detail 360 (exterior_frames + rental_terms) backend tests."""
import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

OWNER = {"email": "owner@demo.local", "password": "demo12345"}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def fleet(client):
    r = client.get(f"{BASE_URL}/api/public/fleet", timeout=30)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    assert len(items) > 0
    return items


@pytest.fixture(scope="module")
def token(client):
    r = client.post(f"{BASE_URL}/api/auth/login", json=OWNER, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"owner login failed {r.status_code}: {r.text[:300]}")
    t = r.json().get("token")
    assert t
    return t


def _find(items, needle):
    for it in items:
        if needle.lower() in str(it.get("name", "")).lower():
            return it
    return None


# --- public fleet list ---
class TestPublicFleet:
    def test_hiace_has_36_frames_and_6_terms(self, fleet):
        h = _find(fleet, "premio") or _find(fleet, "hiace")
        assert h, f"Hiace unit not found: {[i.get('name') for i in fleet]}"
        assert isinstance(h.get("exterior_frames"), list)
        assert len(h["exterior_frames"]) == 36, len(h.get("exterior_frames", []))
        assert h["exterior_frames"][0] == "/api/uploads/spin360/hiace/frame-1.jpg"
        assert len(h.get("rental_terms", [])) == 6
        assert all(isinstance(t, str) and t for t in h["rental_terms"])

    def test_elf_has_empty_frames(self, fleet):
        e = _find(fleet, "elf")
        assert e, "Isuzu Elf not found"
        assert e.get("exterior_frames", []) == []

    def test_no_mongo_id_leak(self, fleet):
        assert all("_id" not in i for i in fleet)

    def test_detail_endpoint(self, client, fleet):
        h = _find(fleet, "premio") or _find(fleet, "hiace")
        r = client.get(f"{BASE_URL}/api/public/fleet/{h['id']}", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "_id" not in d
        assert len(d.get("exterior_frames", [])) == 36
        assert len(d.get("rental_terms", [])) == 6
        assert isinstance(d.get("tour_scenes", []), list) and len(d["tour_scenes"]) >= 1

    def test_detail_404_unknown(self, client):
        r = client.get(f"{BASE_URL}/api/public/fleet/does-not-exist-xyz", timeout=30)
        assert r.status_code == 404, r.status_code


# --- static frame asset ---
def test_static_frame_image(client):
    r = client.get(f"{BASE_URL}/api/uploads/spin360/hiace/frame-1.jpg", timeout=30)
    assert r.status_code == 200, r.status_code
    assert r.headers.get("content-type", "").startswith("image/"), r.headers.get("content-type")
    assert len(r.content) > 1000


def test_static_frame_36(client):
    r = client.get(f"{BASE_URL}/api/uploads/spin360/hiace/frame-36.jpg", timeout=30)
    assert r.status_code == 200


# --- PATCH vehicle round trip (restores original values) ---
def test_patch_vehicle_frames_roundtrip(client, fleet, token):
    h = _find(fleet, "premio") or _find(fleet, "hiace")
    vid = h["id"]
    original_frames = list(h["exterior_frames"])
    original_terms = list(h["rental_terms"])
    hdr = {"Authorization": f"Bearer {token}"}
    try:
        payload = {
            "exterior_frames": ["https://x.com/1.jpg", "https://x.com/2.jpg"],
            "rental_terms": ["TEST_Tes syarat"],
        }
        r = client.patch(f"{BASE_URL}/api/vehicles/{vid}", json=payload, headers=hdr, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        g = client.get(f"{BASE_URL}/api/public/fleet/{vid}", timeout=30)
        assert g.status_code == 200
        d = g.json()
        assert d["exterior_frames"] == payload["exterior_frames"]
        assert d["rental_terms"] == payload["rental_terms"]
    finally:
        rb = client.patch(
            f"{BASE_URL}/api/vehicles/{vid}",
            json={"exterior_frames": original_frames, "rental_terms": original_terms},
            headers=hdr, timeout=30,
        )
        assert rb.status_code == 200, rb.text[:300]
        back = client.get(f"{BASE_URL}/api/public/fleet/{vid}", timeout=30).json()
        assert len(back["exterior_frames"]) == 36
        assert len(back["rental_terms"]) == 6


def test_patch_requires_auth(client, fleet):
    h = _find(fleet, "premio") or _find(fleet, "hiace")
    r = client.patch(f"{BASE_URL}/api/vehicles/{h['id']}", json={"rental_terms": ["x"]}, timeout=30)
    assert r.status_code in (401, 403), r.status_code

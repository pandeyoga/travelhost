"""Share-link JADWAL KEBERANGKATAN (schedule_shares) — RBAC, cakupan, privasi, siklus hidup.

Butuh backend hidup + seed demo (owner/ops/marketing/driver @demo.local, pass demo12345).
Semua tautan yang dibuat test dihapus lagi di akhir (tanpa polusi data ERP).
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi import HTTPException  # noqa: E402

from services import share_links  # noqa: E402
from services.schedule_share import build_query, normalize_scope, period_bounds, scope_label  # noqa: E402


def _base_url():
    env = os.environ.get("REACT_APP_BACKEND_URL")
    if not env:
        fe = ROOT / "frontend" / ".env"
        if fe.exists():
            for line in fe.read_text().splitlines():
                if line.startswith("REACT_APP_BACKEND_URL="):
                    env = line.split("=", 1)[1].strip()
    return (env or "http://127.0.0.1:8001").rstrip("/")


API = _base_url() + "/api"
PASS = "demo12345"
FORBIDDEN_KEYS = {"id", "customer_id", "vehicle_id", "driver_id", "total_amount", "paid_amount",
                  "base_price", "add_ons", "payments", "customer_phone", "phone", "public_token",
                  "hold_expires_at", "created_by"}
CREATED = []


def _login(email):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": PASS}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"login {email} gagal: {r.status_code} (seed demo belum ada?)")
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def owner():
    return _login("owner@demo.local")


@pytest.fixture(scope="module")
def ops():
    return _login("ops@demo.local")


@pytest.fixture(scope="module", autouse=True)
def _cleanup(owner):
    yield
    for sid in CREATED:
        requests.delete(f"{API}/schedule-shares/{sid}", headers=owner, timeout=20)


def _create(headers, **body):
    body.setdefault("label", "TEST_SS jadwal")
    r = requests.post(f"{API}/schedule-shares", json=body, headers=headers, timeout=20)
    if r.status_code == 200:
        CREATED.append(r.json()["id"])
    return r


def _public(token):
    return requests.get(f"{API}/public/schedule/{token}", timeout=20)


# ------------------------------------------------------------------ unit (tanpa jaringan)
def test_month_bounds_use_wib():
    lo, hi = period_bounds({"type": "month", "month": "2026-11"})
    assert lo.isoformat() == "2026-10-31T17:00:00+00:00"   # 1 Nov 00:00 WIB
    assert hi.isoformat() == "2026-11-30T17:00:00+00:00"   # 1 Des 00:00 WIB (eksklusif)
    lo, hi = period_bounds({"type": "month", "month": "2026-12"})
    assert hi.isoformat() == "2026-12-31T17:00:00+00:00"   # lintas tahun


def test_scope_validation_rejects_bad_input():
    for kwargs in ({"scope_type": "range", "start": "2026-11-10", "end": "2026-11-01"},
                   {"scope_type": "range", "start": "2026-01-01", "end": "2027-06-01"},
                   {"scope_type": "month", "month": "2026-13"},
                   {"scope_type": "month"},
                   {"scope_type": "nope"}):
        with pytest.raises(HTTPException) as e:
            normalize_scope(**kwargs)
        assert e.value.status_code == 400


def test_upcoming_scope_rolls_from_today():
    now = datetime(2026, 11, 3, 20, 0, tzinfo=timezone.utc)  # 4 Nov 03:00 WIB
    lo, hi = period_bounds({"type": "upcoming", "days": 7}, now)
    assert lo.isoformat() == "2026-11-03T17:00:00+00:00" and hi - lo == timedelta(days=7)
    assert "7 hari ke depan" in scope_label({"type": "upcoming", "days": 7}, now)
    lo, hi = period_bounds({"type": "upcoming", "days": None}, now)
    assert hi is None
    q = build_query({"scope": {"type": "all"}, "statuses": ["confirmed"], "vehicle_ids": ["veh_x"]})
    assert q == {"status": {"$in": ["confirmed"]}, "vehicle_id": {"$in": ["veh_x"]}}


def test_expiry_rules_shared_by_both_share_kinds():
    assert share_links.expiry_from_hours(0, default=720, max_hours=8760, allow_never=True) is None
    # trip share lama: 0/None = default 72 jam (bukan "tanpa batas", bukan 1 jam)
    exp = datetime.fromisoformat(share_links.expiry_from_hours(0, default=72, max_hours=720))
    assert timedelta(hours=71) < exp - datetime.now(timezone.utc) <= timedelta(hours=72)
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    assert share_links.share_state({"expires_at": past})["is_active"] is False
    assert share_links.share_state({"expires_at": None})["is_active"] is True


def test_resolve_public_share_status_codes():
    class Col:
        def __init__(self, doc):
            self.doc = doc

        async def find_one(self, q, proj=None):
            return dict(self.doc) if self.doc and q.get("token") == self.doc["token"] else None

        async def update_one(self, q, u):
            self.doc["access_count"] = self.doc.get("access_count", 0) + 1

    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    cases = [(None, 404), ({"id": "x", "token": "t", "revoked": True}, 403),
             ({"id": "x", "token": "t", "revoked": False, "expires_at": past}, 410)]
    for doc, code in cases:
        with pytest.raises(HTTPException) as e:
            asyncio.run(share_links.resolve_public_share(Col(doc), "t", "jadwal"))
        assert e.value.status_code == code
    ok = Col({"id": "x", "token": "t", "revoked": False, "expires_at": None})
    asyncio.run(share_links.resolve_public_share(ok, "t", "jadwal"))
    assert ok.doc["access_count"] == 1


# ------------------------------------------------------------------ API (backend hidup)
def test_rbac_only_calendar_roles_can_manage():
    assert requests.get(f"{API}/schedule-shares", timeout=20).status_code == 401
    for email in ("driver@demo.local", "marketing@demo.local"):
        h = _login(email)
        assert requests.get(f"{API}/schedule-shares", headers=h, timeout=20).status_code == 403
        assert _create(h, scope="all").status_code == 403


def test_public_link_is_read_only_and_private(ops):
    r = _create(ops, scope="all")
    assert r.status_code == 200, r.text
    share = r.json()
    assert share["id"].startswith("ssh_") and share["is_active"] and share["expires_at"]
    assert share["statuses"] == ["hold", "confirmed", "ongoing", "completed"]

    pub = _public(share["token"])
    assert pub.status_code == 200, pub.text
    assert "no-store" in pub.headers.get("cache-control", "")
    assert "noindex" in pub.headers.get("x-robots-tag", "")
    data = pub.json()
    assert data["total"] == len(data["items"]) and data["total"] == share["departure_count"]
    assert data["items"], "seed demo seharusnya punya keberangkatan terkonfirmasi"
    for it in data["items"]:
        assert not (FORBIDDEN_KEYS & set(it)), f"field privat bocor: {FORBIDDEN_KEYS & set(it)}"
        assert it["status"] in share["statuses"]
        assert "customer_name" in it and "driver_name" in it          # default visibilitas
        assert "driver_phone" not in it and "payment_status" not in it and "notes" not in it
    for path in ("/bookings", f"/schedule-shares/{share['id']}/revoke"):  # token publik ≠ sesi
        assert requests.post(f"{API}{path}", headers={"Authorization": f"Bearer {share['token']}"},
                             json={}, timeout=20).status_code == 401


def test_visibility_flags_are_respected(owner):
    hidden = _create(owner, scope="all", visibility={"customer": False, "driver": False})
    assert hidden.status_code == 200, hidden.text
    for it in _public(hidden.json()["token"]).json()["items"]:
        assert "customer_name" not in it and "driver_name" not in it and "driver_phone" not in it
    full = _create(owner, scope="all", visibility={"customer": True, "driver": True, "driver_phone": True,
                                                   "payment": True, "notes": True})
    items = _public(full.json()["token"]).json()["items"]
    assert items and all({"driver_phone", "payment_status", "notes"} <= set(it) for it in items)


def test_filters_vehicle_status_and_month(owner):
    vehicles = requests.get(f"{API}/vehicles", headers=owner, timeout=20).json()
    vid = vehicles[0]["id"]
    one = _create(owner, scope="all", vehicle_ids=[vid], statuses=["confirmed", "completed", "pending"])
    assert one.status_code == 200, one.text
    for it in _public(one.json()["token"]).json()["items"]:
        assert it["vehicle_name"] == vehicles[0]["name"]
        assert it["status"] in ("confirmed", "completed", "pending")

    month = datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m")
    m = _create(owner, scope="month", month=month)
    assert m.status_code == 200, m.text
    data = _public(m.json()["token"]).json()
    lo, hi = period_bounds({"type": "month", "month": month})
    for it in data["items"]:
        start = datetime.fromisoformat(it["start_datetime"].replace("Z", "+00:00"))
        assert lo <= start < hi

    assert _create(owner, scope="all", vehicle_ids=["veh_tidak_ada"]).status_code == 400
    assert _create(owner, scope="range", start="2026-11-10", end="2026-11-01").status_code == 400
    assert _create(owner, scope="all", statuses=["ngawur"]).status_code == 422
    assert _create(owner, scope="all", label="A" * 60000).status_code == 422


def test_lifecycle_revoke_delete_and_access_count(owner):
    s = _create(owner, scope="upcoming", days=0, hours=0).json()
    assert s["expires_at"] is None and s["period_label"].startswith("Semua jadwal mendatang")
    assert _public(s["token"]).status_code == 200
    assert _public(s["token"]).status_code == 200
    listed = {x["id"]: x for x in requests.get(f"{API}/schedule-shares", headers=owner, timeout=20).json()}
    assert listed[s["id"]]["access_count"] == 2

    assert requests.post(f"{API}/schedule-shares/{s['id']}/revoke", headers=owner, timeout=20).json()["revoked"]
    assert _public(s["token"]).status_code == 403
    assert requests.delete(f"{API}/schedule-shares/{s['id']}", headers=owner, timeout=20).status_code == 200
    assert _public(s["token"]).status_code == 404
    assert _public("token-ngawur").status_code == 404


def test_trip_share_public_track_still_works(owner):
    """Regresi refactor services/share_links: tautan tracking lama tetap 200/404 seperti dulu."""
    active = [s for s in requests.get(f"{API}/shares", headers=owner, timeout=20).json() if s["is_active"]]
    if not active:
        pytest.skip("seed tanpa trip share aktif")
    assert requests.get(f"{API}/public/track/{active[0]['token']}", timeout=30).status_code == 200
    assert requests.get(f"{API}/public/track/token-ngawur", timeout=20).status_code == 404

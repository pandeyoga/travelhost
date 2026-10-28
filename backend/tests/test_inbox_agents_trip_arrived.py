"""Keputusan 2026-10-28: (1) agen Inbox = peran section 'inbox' (SSOT permissions_config),
(2) "tiba di tujuan" satu jalur (services/trips.mark_trip_arrived) — tombol Dispatch + tombol
Ruang Kerja Driver + geofence tidak boleh mengirim WA `trip.arrived` dua kali.

Butuh backend hidup + seed demo. Perubahan data dipulihkan di akhir.
"""
import os
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
ENV = {**dotenv_values(ROOT / "backend" / ".env"), **os.environ}
API = (ENV.get("REACT_APP_BACKEND_URL") or "http://127.0.0.1:8001").rstrip("/") + "/api"


def _login(email):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": "demo12345"}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"login {email} gagal ({r.status_code}) — seed demo belum ada?")
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def db():
    if not ENV.get("MONGO_URL"):
        pytest.skip("MONGO_URL tidak tersedia")
    return MongoClient(ENV["MONGO_URL"])[ENV.get("DB_NAME", "test_database")]


def test_inbox_agents_follow_section_access():
    ops = _login("ops@demo.local")
    r = requests.get(f"{API}/conversations/agents", headers=ops, timeout=20)
    assert r.status_code == 200, r.text
    roles = {a["role"] for a in r.json()}
    assert roles <= {"owner", "ops_admin", "marketing_admin"} and "marketing_admin" in roles
    assert requests.get(f"{API}/conversations/agents", headers=_login("marketing@demo.local"),
                        timeout=20).status_code == 200
    assert requests.get(f"{API}/conversations/agents", headers=_login("driver@demo.local"),
                        timeout=20).status_code == 403


def test_assign_rejects_user_without_inbox_access(db):
    owner = _login("owner@demo.local")
    convs = requests.get(f"{API}/conversations", headers=owner, timeout=20).json()
    if not convs:
        pytest.skip("seed tanpa percakapan")
    conv = convs[0]
    driver_user = db.users.find_one({"role": "driver"}, {"_id": 0, "id": 1})
    marketing = db.users.find_one({"role": "marketing_admin"}, {"_id": 0, "id": 1})
    try:
        r = requests.patch(f"{API}/conversations/{conv['id']}", headers=owner,
                           json={"assigned_to": driver_user["id"]}, timeout=20)
        assert r.status_code == 400, r.text
        r = requests.patch(f"{API}/conversations/{conv['id']}", headers=owner,
                           json={"assigned_to": marketing["id"]}, timeout=20)
        assert r.status_code == 200, r.text
    finally:
        db.conversations.update_one({"id": conv["id"]}, {"$set": {"assigned_to": conv.get("assigned_to")}})


def test_arrived_is_single_path_and_deduped(db):
    trip = db.trips.find_one({"status": "on_trip", "booking_id": {"$ne": None}}, {"_id": 0})
    if not trip:
        pytest.skip("seed tanpa trip on_trip")
    owner = _login("owner@demo.local")
    before = db.events.count_documents({"type": "trip.arrived", "ref_id": trip["booking_id"]})
    try:
        r1 = requests.post(f"{API}/dispatch/trips/{trip['id']}/arrived", headers=owner, timeout=20)
        assert r1.status_code == 200, r1.text
        first = r1.json()["arrived_at"]
        r2 = requests.post(f"{API}/driver/tasks/{trip['id']}/arrived", headers=owner, timeout=20)
        assert r2.status_code == 200, r2.text
        assert r2.json()["arrived_at"] == first, "arrived_at tertimpa oleh tombol kedua"
        assert r2.json()["status"] == "on_trip", "tiba di tujuan tidak boleh menyelesaikan trip"
        after = db.events.count_documents({"type": "trip.arrived", "ref_id": trip["booking_id"]})
        assert after - before == (0 if before else 1), "WA trip.arrived terkirim lebih dari sekali"
    finally:
        db.trips.update_one({"id": trip["id"]}, {"$set": {"arrived_at": trip.get("arrived_at")}})
        if not before:
            db.events.delete_many({"type": "trip.arrived", "ref_id": trip["booking_id"]})

"""Backend tests SSOT Batch 7 — GABUNG + BATALKAN GABUNGAN untuk TITIK JEMPUT kembar.

Pola persis sama dgn destinasi (batch 5/6):
  (A) MERGE titik jemput sumber → target:
      - bookings.origin sumber pindah ke nama target
      - source active=false, merged_into=<target.id>, merged_moved.bookings=[<ids>]
      - GET /api/master/pickup-points: baris sumber punya merged_into_name & merged_moved_count>=1
  (B) UNMERGE: booking dikembalikan ke nama sumber (bila origin masih nama target),
      dokumen yang telah diubah manual → skipped; source active=true, merged_into hilang.
      Re-unmerge → 400; merge ke diri sendiri → 400; merge dgn target nonaktif → 400.
  (C) Selector `/api/pickup-points`: titik jemput digabung HILANG (active=false) dan muncul
      kembali setelah unmerge.

Kebersihan: nama uji prefix 'Penjaga INV-' + phone '0800000xxx'; purge_guard_artifacts().
"""
import os
import sys
from datetime import datetime, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {"owner": ("owner@demo.local", "demo12345")}
GUARD_PHONE_PREFIX = "0800000"
GUARD_NAME_PREFIX = "Penjaga INV-"


def _login(email, pwd):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def owner_h():
    return _login(*CREDS["owner"])


@pytest.fixture(scope="module")
def mongo():
    from pymongo import MongoClient
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        try:
            with open("/app/backend/.env") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("MONGO_URL="):
                        mongo_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif line.startswith("DB_NAME="):
                        db_name = line.split("=", 1)[1].strip().strip('"').strip("'")
        except FileNotFoundError:
            pass
    assert mongo_url and db_name, "MONGO_URL / DB_NAME tidak tersedia"
    return MongoClient(mongo_url)[db_name]


SRC_ID = "pkp_test_b7"
SRC_NAME = f"{GUARD_NAME_PREFIX}Stasiun Kembar TEST"
BK_ID = "bkg_test_b7"


def _seed(mongo):
    mongo.pickup_points.update_one(
        {"id": SRC_ID},
        {"$set": {"id": SRC_ID, "name": SRC_NAME, "active": True,
                  "created_at": datetime.now(timezone.utc).isoformat()},
         "$unset": {"merged_into": "", "merged_into_name": "", "merged_moved": ""}},
        upsert=True)
    mongo.bookings.update_one(
        {"id": BK_ID},
        {"$set": {"id": BK_ID, "booking_no": "BK-TEST-B7",
                  "customer_id": "cust_seed_x", "vehicle_id": "veh_seed_x",
                  "origin": SRC_NAME, "destination": "Bali",
                  "pickup_datetime": datetime.now(timezone.utc).isoformat(),
                  "status": "draft",
                  "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True)


def _cleanup(mongo):
    mongo.pickup_points.delete_one({"id": SRC_ID})
    mongo.bookings.delete_one({"id": BK_ID})


def _get_target_id(mongo, name="Stasiun Bandung"):
    d = mongo.pickup_points.find_one({"name": name, "deleted": {"$ne": True}}, {"_id": 0, "id": 1})
    assert d, f"seed titik jemput '{name}' tidak ada"
    return d["id"]


# ============ (A) MERGE titik jemput ============
class TestMergePickupPoint:
    def test_merge_cascades_bookings(self, owner_h, mongo):
        _seed(mongo)
        try:
            tgt_id = _get_target_id(mongo)
            r = requests.post(f"{API}/master/pickup-points/{SRC_ID}/merge",
                              json={"target_id": tgt_id}, headers=owner_h, timeout=20)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body.get("merged") is True
            assert body["cascade"]["bookings"] == 1, body

            # Verify booking dipindah
            bk = mongo.bookings.find_one({"id": BK_ID}, {"_id": 0})
            assert bk["origin"] == "Stasiun Bandung"

            # Verify source: active=False + merged_into + merged_moved.bookings=[BK_ID]
            src = mongo.pickup_points.find_one({"id": SRC_ID}, {"_id": 0})
            assert src["active"] is False
            assert src["merged_into"] == tgt_id
            assert src["merged_into_name"] == "Stasiun Bandung"
            assert BK_ID in (src.get("merged_moved") or {}).get("bookings", []), src

            # GET /master/pickup-points: baris sumber punya merged_into_name & merged_moved_count=1
            rows = requests.get(f"{API}/master/pickup-points", headers=owner_h, timeout=15).json()
            row = [x for x in rows if x.get("id") == SRC_ID]
            assert row, "sumber hilang dari master list"
            assert row[0].get("merged_into_name") == "Stasiun Bandung"
            assert row[0].get("merged_moved_count") == 1, row[0]
        finally:
            _cleanup(mongo)

    def test_merge_to_self_400(self, owner_h, mongo):
        _seed(mongo)
        try:
            r = requests.post(f"{API}/master/pickup-points/{SRC_ID}/merge",
                              json={"target_id": SRC_ID}, headers=owner_h, timeout=15)
            assert r.status_code == 400, r.text
        finally:
            _cleanup(mongo)

    def test_merge_target_inactive_400(self, owner_h, mongo):
        _seed(mongo)
        tgt_inactive_id = "pkp_test_b7_inactive"
        mongo.pickup_points.update_one(
            {"id": tgt_inactive_id},
            {"$set": {"id": tgt_inactive_id,
                      "name": f"{GUARD_NAME_PREFIX}InactivePkp",
                      "active": False,
                      "created_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True)
        try:
            r = requests.post(f"{API}/master/pickup-points/{SRC_ID}/merge",
                              json={"target_id": tgt_inactive_id}, headers=owner_h, timeout=15)
            assert r.status_code == 400, r.text
        finally:
            mongo.pickup_points.delete_one({"id": tgt_inactive_id})
            _cleanup(mongo)


# ============ (B) UNMERGE titik jemput ============
class TestUnmergePickupPoint:
    def test_unmerge_restores_bookings(self, owner_h, mongo):
        _seed(mongo)
        try:
            tgt_id = _get_target_id(mongo)
            # merge
            r = requests.post(f"{API}/master/pickup-points/{SRC_ID}/merge",
                              json={"target_id": tgt_id}, headers=owner_h, timeout=20)
            assert r.status_code == 200, r.text

            # unmerge
            r = requests.post(f"{API}/master/pickup-points/{SRC_ID}/unmerge",
                              headers=owner_h, timeout=20)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body.get("unmerged") is True
            assert body["restored"]["bookings"] == 1, body
            assert body["skipped"] == 0, body

            # booking kembali
            assert mongo.bookings.find_one({"id": BK_ID})["origin"] == SRC_NAME
            src = mongo.pickup_points.find_one({"id": SRC_ID}, {"_id": 0})
            assert src["active"] is True
            assert "merged_into" not in src or not src.get("merged_into")

            # Re-unmerge → 400
            r = requests.post(f"{API}/master/pickup-points/{SRC_ID}/unmerge",
                              headers=owner_h, timeout=15)
            assert r.status_code == 400, r.text
            assert "gabung" in (r.json().get("detail") or "").lower()
        finally:
            _cleanup(mongo)

    def test_unmerge_with_skipped(self, owner_h, mongo):
        """Booking diubah manual ke titik lain sesudah merge → skipped=1."""
        _seed(mongo)
        try:
            tgt_id = _get_target_id(mongo)
            r = requests.post(f"{API}/master/pickup-points/{SRC_ID}/merge",
                              json={"target_id": tgt_id}, headers=owner_h, timeout=20)
            assert r.status_code == 200, r.text

            # manual override booking.origin → 'Bandung'
            mongo.bookings.update_one({"id": BK_ID}, {"$set": {"origin": "Bandung"}})

            r = requests.post(f"{API}/master/pickup-points/{SRC_ID}/unmerge",
                              headers=owner_h, timeout=20)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["restored"]["bookings"] == 0, body
            assert body["skipped"] == 1, body

            # booking tetap 'Bandung' (tidak disentuh)
            assert mongo.bookings.find_one({"id": BK_ID})["origin"] == "Bandung"
        finally:
            _cleanup(mongo)


# ============ (C) Selector /api/pickup-points ============
class TestSelectorHiddenWhenMerged:
    def test_merged_pickup_hidden_from_selector(self, owner_h, mongo):
        _seed(mongo)
        try:
            # Sebelum merge, sumber MUNCUL di selector
            sel = requests.get(f"{API}/pickup-points", headers=owner_h, timeout=15).json()
            names_before = {x.get("name") for x in sel}
            assert SRC_NAME in names_before, "sumber tidak muncul sebelum merge"

            tgt_id = _get_target_id(mongo)
            r = requests.post(f"{API}/master/pickup-points/{SRC_ID}/merge",
                              json={"target_id": tgt_id}, headers=owner_h, timeout=20)
            assert r.status_code == 200, r.text

            # Sesudah merge → HILANG
            sel = requests.get(f"{API}/pickup-points", headers=owner_h, timeout=15).json()
            names_after = {x.get("name") for x in sel}
            assert SRC_NAME not in names_after, "sumber masih tampak sesudah merge"

            # Unmerge → MUNCUL kembali
            r = requests.post(f"{API}/master/pickup-points/{SRC_ID}/unmerge",
                              headers=owner_h, timeout=20)
            assert r.status_code == 200, r.text
            sel = requests.get(f"{API}/pickup-points", headers=owner_h, timeout=15).json()
            names_restored = {x.get("name") for x in sel}
            assert SRC_NAME in names_restored, "sumber tidak kembali sesudah unmerge"
        finally:
            _cleanup(mongo)


# ============ Regresi tipis: merge/unmerge destinasi masih jalan ============
class TestRegressionMergeDestination:
    DST_ID = "dst_test_b7_reg"
    DST_NAME = f"{GUARD_NAME_PREFIX}RegDest B7"

    def test_dest_merge_unmerge_round_trip(self, owner_h, mongo):
        mongo.destinations.update_one(
            {"id": self.DST_ID},
            {"$set": {"id": self.DST_ID, "name": self.DST_NAME,
                      "slug": "penjaga-regdest-b7",
                      "status": "draft", "ops_active": True,
                      "created_at": datetime.now(timezone.utc).isoformat()},
             "$unset": {"merged_into": "", "merged_into_name": "", "merged_moved": ""}},
            upsert=True)
        try:
            tgt = mongo.destinations.find_one({"name": "Bali"}, {"_id": 0, "id": 1})
            assert tgt
            r = requests.post(f"{API}/master/destinations/{self.DST_ID}/merge",
                              json={"target_id": tgt["id"]}, headers=owner_h, timeout=20)
            assert r.status_code == 200, r.text
            assert r.json().get("merged") is True

            r = requests.post(f"{API}/master/destinations/{self.DST_ID}/unmerge",
                              headers=owner_h, timeout=20)
            assert r.status_code == 200, r.text
            assert r.json().get("unmerged") is True
        finally:
            mongo.destinations.delete_one({"id": self.DST_ID})


# ============ zzz: purge artefacts ============
class TestZZZCleanup:
    def test_purge(self):
        sys.path.insert(0, "/app")
        from scripts.guardrails._common import purge_guard_artifacts
        n = purge_guard_artifacts()
        print(f"purge_guard_artifacts removed: {n}")

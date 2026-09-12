"""Iteration 111 — dua fitur baru:
(1) drivers.default_fee_rate (rate fee default per driver, prefill dialog Assign)
(2) master Add-on: PATCH label/nominal/aktif-nonaktif + DELETE + include_inactive

Berkas ini berbagi STATE antar-kelas → jalankan SERIAL: `pytest tests/test_i111_... -n 0`.
Juga menyiapkan SEED untuk uji UI (2 booking Nov 2026: satu belum ada fee, satu fee 120000).
"""
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL")).rstrip("/")
PASS = "demo12345"
STATE = {}


def _login(email):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": PASS}, timeout=60)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token: {r.text[:200]}"
    s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def owner():
    return _login("owner@demo.local")


@pytest.fixture(scope="module")
def marketing():
    return _login("marketing@demo.local")


# ==================================================== 1) FEE DEFAULT driver (backend)
class TestDriverDefaultFeeRate:
    def test_list_drivers_memuat_field(self, owner):
        r = owner.get(f"{BASE}/api/drivers", timeout=60)
        assert r.status_code == 200, r.text[:300]
        rows = r.json()
        assert isinstance(rows, list) and rows, "driver master kosong"
        assert all("_id" not in d for d in rows), "ObjectId _id bocor di response"
        assert "default_fee_rate" in rows[0], f"field default_fee_rate hilang: {rows[0].keys()}"
        STATE["driver_id"] = rows[0]["id"]
        STATE["driver_name"] = rows[0]["name"]

    def test_patch_set_175000_persist(self, owner):
        did = STATE["driver_id"]
        r = owner.patch(f"{BASE}/api/drivers/{did}", json={"default_fee_rate": 175000}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("default_fee_rate") == 175000
        g = owner.get(f"{BASE}/api/drivers/{did}", timeout=60)
        assert g.status_code == 200
        assert g.json().get("default_fee_rate") == 175000, "tidak persist di DB"

    def test_patch_nol_mereset_ke_null(self, owner):
        did = STATE["driver_id"]
        r = owner.patch(f"{BASE}/api/drivers/{did}", json={"default_fee_rate": 0}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("default_fee_rate") is None, f"0 harus jadi null, dapat {r.json().get('default_fee_rate')}"
        g = owner.get(f"{BASE}/api/drivers/{did}", timeout=60)
        assert g.json().get("default_fee_rate") is None

    def test_negatif_ditolak_422(self, owner):
        r = owner.patch(f"{BASE}/api/drivers/{STATE['driver_id']}",
                        json={"default_fee_rate": -5000}, timeout=60)
        assert r.status_code == 422, f"nilai negatif harus 422, dapat {r.status_code}"

    def test_restore_175000_untuk_uji_ui(self, owner):
        r = owner.patch(f"{BASE}/api/drivers/{STATE['driver_id']}",
                        json={"default_fee_rate": 175000}, timeout=60)
        assert r.status_code == 200 and r.json().get("default_fee_rate") == 175000

    def test_create_driver_dengan_default_fee(self, owner):
        uniq = uuid.uuid4().hex[:5]
        r = owner.post(f"{BASE}/api/drivers", json={"name": f"TEST_Driver {uniq}",
                                                   "phone": f"08110000{uniq[:3]}",
                                                   "default_fee_rate": 150000}, timeout=60)
        assert r.status_code in (200, 201), r.text[:300]
        doc = r.json()
        assert doc.get("default_fee_rate") == 150000
        STATE["tmp_driver_id"] = doc["id"]
        d = owner.delete(f"{BASE}/api/drivers/{doc['id']}", timeout=60)
        assert d.status_code in (200, 204), d.text[:200]

    def test_rbac_marketing_patch_driver_403(self, marketing):
        r = marketing.patch(f"{BASE}/api/drivers/{STATE['driver_id']}",
                            json={"default_fee_rate": 999000}, timeout=60)
        assert r.status_code == 403, f"marketing harus 403, dapat {r.status_code} {r.text[:200]}"


# ==================================================== 2) MASTER ADD-ON
class TestAddonMaster:
    def test_create(self, owner):
        label = f"TEST_Addon {uuid.uuid4().hex[:5]}"
        r = owner.post(f"{BASE}/api/addons", json={"label": label, "default_amount": 25000}, timeout=60)
        assert r.status_code in (200, 201), r.text[:300]
        doc = r.json()
        assert doc["label"] == label and doc["default_amount"] == 25000 and doc["active"] is True
        STATE["addon_id"] = doc["id"]
        STATE["addon_label"] = label

    def test_duplikat_409(self, owner):
        r = owner.post(f"{BASE}/api/addons",
                       json={"label": STATE["addon_label"].lower(), "default_amount": 1000}, timeout=60)
        assert r.status_code == 409, f"duplikat harus 409, dapat {r.status_code}"

    def test_patch_label_dan_nominal(self, owner):
        new_label = STATE["addon_label"] + " Edit"
        r = owner.patch(f"{BASE}/api/addons/{STATE['addon_id']}",
                        json={"label": new_label, "default_amount": 45000}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["default_amount"] == 45000 and r.json()["label"] == new_label
        rows = owner.get(f"{BASE}/api/addons", timeout=60).json()
        got = [x for x in rows if x["id"] == STATE["addon_id"]]
        assert got and got[0]["default_amount"] == 45000, "edit tidak persist"
        STATE["addon_label"] = new_label

    def test_nonaktifkan_hilang_dari_list_aktif(self, owner):
        r = owner.patch(f"{BASE}/api/addons/{STATE['addon_id']}", json={"active": False}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["active"] is False, f"active tidak jadi False: {r.json()}"
        active_ids = [x["id"] for x in owner.get(f"{BASE}/api/addons", timeout=60).json()]
        assert STATE["addon_id"] not in active_ids, "add-on nonaktif masih muncul di list default"
        all_ids = [x["id"] for x in owner.get(f"{BASE}/api/addons?include_inactive=true", timeout=60).json()]
        assert STATE["addon_id"] in all_ids, "include_inactive tidak memuat add-on nonaktif"

    def test_aktifkan_kembali(self, owner):
        r = owner.patch(f"{BASE}/api/addons/{STATE['addon_id']}", json={"active": True}, timeout=60)
        assert r.status_code == 200 and r.json()["active"] is True
        active_ids = [x["id"] for x in owner.get(f"{BASE}/api/addons", timeout=60).json()]
        assert STATE["addon_id"] in active_ids

    def test_rbac_marketing_patch_delete_403(self, marketing):
        p = marketing.patch(f"{BASE}/api/addons/{STATE['addon_id']}", json={"active": False}, timeout=60)
        assert p.status_code == 403, f"PATCH marketing harus 403, dapat {p.status_code}"
        d = marketing.delete(f"{BASE}/api/addons/{STATE['addon_id']}", timeout=60)
        assert d.status_code == 403, f"DELETE marketing harus 403, dapat {d.status_code}"

    def test_delete_dan_404_berikutnya(self, owner):
        r = owner.delete(f"{BASE}/api/addons/{STATE['addon_id']}", timeout=60)
        assert r.status_code in (200, 204), r.text[:300]
        all_ids = [x["id"] for x in owner.get(f"{BASE}/api/addons?include_inactive=true", timeout=60).json()]
        assert STATE["addon_id"] not in all_ids, "add-on masih ada setelah delete"
        again = owner.delete(f"{BASE}/api/addons/{STATE['addon_id']}", timeout=60)
        assert again.status_code == 404


# ==================================================== 3) SEED + prefill priority (trip rate > default)
class TestAssignFeePrefillData:
    def test_siapkan_dua_booking_nov_2026(self, owner):
        cust = owner.get(f"{BASE}/api/customers", timeout=60).json()
        veh = owner.get(f"{BASE}/api/vehicles", timeout=60).json()
        assert cust and veh, "master customer/vehicle kosong"
        STATE["vehicle_ids"] = [v["id"] for v in veh]
        made = []
        # tanggal acak Des 2026 agar tidak bentrok armada dgn data uji run sebelumnya
        import random
        day = random.randint(1, 20)
        STATE["dispatch_date"] = f"2026-12-{day:02d}"
        for i in range(2):
            payload = {"customer_id": cust[0]["id"], "vehicle_id": veh[i % len(veh)]["id"],
                       "origin": "Bandung", "destination": "Yogyakarta",
                       "start_datetime": f"2026-12-{day:02d}T07:00:00",
                       "end_datetime": f"2026-12-{day + 1:02d}T18:00:00", "base_price": 3500000,
                       "notes": f"TEST_i111 prefill {i}"}
            r = owner.post(f"{BASE}/api/bookings", json=payload, timeout=60)
            assert r.status_code in (200, 201), f"booking {i}: {r.status_code} {r.text[:300]}"
            made.append(r.json()["id"])
            STATE.setdefault("codes", []).append(r.json().get("code"))
        STATE["bk_no_fee"], STATE["bk_with_fee"] = made

    def test_assign_dengan_rate_120000_snapshot_di_trip(self, owner):
        r = owner.post(f"{BASE}/api/dispatch/{STATE['bk_with_fee']}/assign",
                       json={"driver_id": STATE["driver_id"],
                             "vehicle_id": STATE["vehicle_ids"][1 % len(STATE["vehicle_ids"])],
                             "driver_fee_rate": 120000}, timeout=90)
        assert r.status_code == 200, r.text[:400]
        d = owner.get(f"{BASE}/api/dispatch/{STATE['bk_with_fee']}/detail", timeout=60)
        assert d.status_code == 200, d.text[:300]
        rate = d.json().get("trip", {}).get("driver_fee_rate")
        assert rate == 120000, f"rate trip harus 120000 (menang atas default 175000), dapat {rate}"

    def test_booking_tanpa_fee_detail_kosong(self, owner):
        d = owner.get(f"{BASE}/api/dispatch/{STATE['bk_no_fee']}/detail", timeout=60)
        assert d.status_code == 200, d.text[:300]
        trip = d.json().get("trip") or {}
        assert not trip.get("driver_fee_rate"), f"trip belum di-assign harus tanpa rate: {trip.get('driver_fee_rate')}"

    def test_assign_manual_rate_berbeda_tersimpan(self, owner):
        # regresi: rate manual (beda dari default 175000) tersimpan sesuai ketikan; lalu
        # dipulihkan ke 120000 agar seed uji UI (prioritas rate trip) tetap valid.
        bid = STATE["bk_with_fee"]
        veh = STATE["vehicle_ids"][1 % len(STATE["vehicle_ids"])]
        r = owner.post(f"{BASE}/api/dispatch/{bid}/assign",
                       json={"driver_id": STATE["driver_id"], "vehicle_id": veh,
                             "driver_fee_rate": 99000}, timeout=90)
        assert r.status_code == 200, r.text[:400]
        d = owner.get(f"{BASE}/api/dispatch/{bid}/detail", timeout=60)
        assert d.json().get("trip", {}).get("driver_fee_rate") == 99000, "rate manual tidak tersimpan sesuai ketikan"
        back = owner.post(f"{BASE}/api/dispatch/{bid}/assign",
                          json={"driver_id": STATE["driver_id"], "vehicle_id": veh,
                                "driver_fee_rate": 120000}, timeout=90)
        assert back.status_code == 200, back.text[:400]
        assert owner.get(f"{BASE}/api/dispatch/{bid}/detail", timeout=60).json()["trip"]["driver_fee_rate"] == 120000
        print(f"SEED UI: date={STATE['dispatch_date']} codes={STATE.get('codes')} "
              f"no_fee={STATE['bk_no_fee']} with_fee={STATE['bk_with_fee']} driver={STATE['driver_name']}")

"""Iteration 110 — regresi 7 perbaikan: quick-add customer, master add-on, pesanan online,
dispatch detail, fee driver E2E + pencairan finance, maintenance multi in_progress, RBAC.

PENTING: berkas ini berbagi STATE antar-kelas (booking/trip/driver uji) sehingga HARUS
dijalankan SERIAL: `pytest tests/test_i110_features.py -n 0`. Dengan `-n 2 --dist loadscope`
(default pytest.ini) tiap kelas jatuh ke worker berbeda → STATE hilang (KeyError palsu).
"""
import os
import time
import uuid

import pytest
import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL")).rstrip("/")
PASS = "demo12345"
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
       b"\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00"
       b"\x00\x00IEND\xaeB`\x82")
STATE = {}


def _login(email):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": PASS}, timeout=40)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token in login response: {r.text[:200]}"
    s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def owner():
    return _login("owner@demo.local")


@pytest.fixture(scope="module")
def driver_s():
    return _login("driver@demo.local")


@pytest.fixture(scope="module")
def marketing():
    return _login("marketing@demo.local")


# ============================================================ 1) customer + add-on master
class TestBookingMasters:
    def test_quick_add_customer_masuk_master(self, owner):
        uniq = uuid.uuid4().hex[:6]
        payload = {"name": f"Penjaga INV-{uniq}", "phone": f"0800000{uniq[:4]}",
                   "type": "individual", "city": "Bandung"}
        r = owner.post(f"{BASE}/api/customers", json=payload, timeout=40)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:300]}"
        cust = r.json()
        assert cust.get("id") and cust["name"] == payload["name"]
        STATE["customer_id"] = cust["id"]
        lst = owner.get(f"{BASE}/api/customers?limit=500", timeout=40)
        assert lst.status_code == 200
        rows = lst.json() if isinstance(lst.json(), list) else lst.json().get("items", [])
        assert any(c["id"] == cust["id"] for c in rows), "customer baru tidak muncul di master data"
        assert all("_id" not in c for c in rows)

    def test_create_addon_master_and_duplicate_409(self, owner):
        label = f"TEST_Parkir Bandara {uuid.uuid4().hex[:5]}"
        r = owner.post(f"{BASE}/api/addons", json={"label": label, "default_amount": 50000}, timeout=40)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:300]}"
        doc = r.json()
        assert doc["label"] == label and doc["default_amount"] == 50000
        STATE["addon_id"] = doc["id"]
        STATE["addon_label"] = label
        dup = owner.post(f"{BASE}/api/addons", json={"label": label.lower(), "default_amount": 1}, timeout=40)
        assert dup.status_code == 409, f"duplikat harus 409, dapat {dup.status_code}"
        lst = owner.get(f"{BASE}/api/addons", timeout=40)
        assert lst.status_code == 200
        assert any(a["id"] == doc["id"] for a in lst.json())

    def test_addon_mutasi_ditolak_untuk_marketing(self, marketing):
        r = marketing.post(f"{BASE}/api/addons", json={"label": "TEST_x", "default_amount": 1}, timeout=40)
        assert r.status_code == 403, f"marketing harus 403 di POST /api/addons, dapat {r.status_code}"

    def test_booking_dengan_multi_addon(self, owner):
        vehs = owner.get(f"{BASE}/api/vehicles?limit=200", timeout=40).json()
        vehs = vehs if isinstance(vehs, list) else vehs.get("items", [])
        assert vehs, "tidak ada armada"
        add_ons = [{"label": STATE["addon_label"], "amount": 50000},
                   {"label": "TEST_Tol", "amount": 25000}]
        base_price = 2000000
        created = None
        for veh in vehs:
            for day in (4, 6, 9, 12, 16, 19, 23, 26):
                body = {"customer_id": STATE["customer_id"], "vehicle_id": veh["id"],
                        "origin": "Bandung", "destination": "Jakarta",
                        "start_datetime": f"2026-11-{day:02d}T08:00:00",
                        "end_datetime": f"2026-11-{day + 2:02d}T17:00:00",
                        "base_price": base_price, "add_ons": add_ons,
                        "notes": "Penjaga INV-110"}
                r = owner.post(f"{BASE}/api/bookings", json=body, timeout=60)
                if r.status_code in (200, 201):
                    created = (r.json(), veh, day)
                    break
                assert r.status_code == 400, f"unexpected {r.status_code}: {r.text[:300]}"
            if created:
                break
        assert created, "gagal membuat booking uji di seluruh armada/tanggal Nov 2026"
        bk, veh, day = created
        STATE.update({"booking_id": bk["id"], "booking_code": bk.get("code"),
                      "vehicle_id": veh["id"], "day": day})
        assert bk["total_amount"] == base_price + 75000, f"total salah: {bk['total_amount']}"
        got = owner.get(f"{BASE}/api/bookings/{bk['id']}", timeout=40)
        assert got.status_code == 200
        doc = got.json()
        assert len(doc.get("add_ons") or []) == 2, f"add_ons tidak tersimpan: {doc.get('add_ons')}"
        assert {a["label"] for a in doc["add_ons"]} == {STATE["addon_label"], "TEST_Tol"}
        assert "_id" not in doc


# ============================================================ 2) dispatch + fee driver E2E
class TestDispatchFeeE2E:
    def test_prepare_ids(self, owner, driver_s):
        f = driver_s.get(f"{BASE}/api/driver/fees", timeout=40)
        assert f.status_code == 200, f"{f.status_code} {f.text[:200]}"
        data = f.json()
        assert data.get("is_driver") is True, f"akun driver tidak tertaut: {data}"
        STATE["driver_id"] = data["driver_id"]
        STATE["earned_before"] = data["earned_total"]
        STATE["available_before"] = data["available"]

    def test_assign_dengan_fee_rate(self, owner):
        assert STATE.get("booking_id"), "booking uji belum dibuat"
        r = owner.post(f"{BASE}/api/dispatch/{STATE['booking_id']}/assign",
                       json={"driver_id": STATE["driver_id"], "vehicle_id": STATE["vehicle_id"],
                             "driver_fee_rate": 150000}, timeout=90)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        trip = r.json()["trip"]
        STATE["trip_id"] = trip["id"]
        assert trip["driver_fee_rate"] == 150000
        assert trip["driver_fee_days"] == 3, f"hari fee salah: {trip['driver_fee_days']}"
        assert trip["driver_fee_total"] == 450000

    def test_dispatch_detail_timeline(self, owner):
        r = owner.get(f"{BASE}/api/dispatch/{STATE['booking_id']}/detail", timeout=40)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        d = r.json()
        assert d["booking"]["id"] == STATE["booking_id"]
        assert d["trip"]["id"] == STATE["trip_id"]
        assert d["driver"] and d["driver"].get("name")
        labels = [t["label"] for t in d["timeline"]]
        assert any("assign" in x.lower() for x in labels), f"timeline tanpa assign: {labels}"
        assert d["timeline"] == sorted(d["timeline"], key=lambda x: x["at"])

    def test_dispatch_board_menampilkan_baris(self, owner):
        date = f"2026-11-{STATE['day']:02d}"
        r = owner.get(f"{BASE}/api/dispatch/today?date={date}", timeout=60)
        assert r.status_code == 200
        rows = r.json()["departures"]
        mine = [x for x in rows if x["id"] == STATE["booking_id"]]
        assert mine, f"booking uji tidak ada di papan dispatch {date}"
        assert mine[0]["assigned"] is True and mine[0]["trip_status"] == "standby"

    def test_driver_melihat_tugas_sama(self, driver_s):
        r = driver_s.get(f"{BASE}/api/driver/tasks", timeout=40)
        assert r.status_code == 200
        tasks = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        ids = [t.get("trip_id") or t.get("id") for t in tasks]
        assert STATE["trip_id"] in ids, f"trip tidak tampil di ruang kerja driver: {ids[:10]}"

    def test_driver_ack_lalu_terlihat_di_dispatch(self, driver_s, owner):
        r = driver_s.post(f"{BASE}/api/driver/tasks/{STATE['trip_id']}/ack", timeout=40)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        d = owner.get(f"{BASE}/api/dispatch/{STATE['booking_id']}/detail", timeout=40).json()
        assert d["trip"].get("driver_ack_at"), "ack driver tidak terbaca di dispatch detail"
        assert any("mengonfirmasi" in t["label"].lower() for t in d["timeline"])

    def test_checkin_checkout_kredit_fee(self, driver_s, owner):
        ci = driver_s.post(f"{BASE}/api/driver/checkin",
                           json={"trip_id": STATE["trip_id"], "odometer_start": 10000}, timeout=60)
        assert ci.status_code == 200, f"checkin {ci.status_code} {ci.text[:300]}"
        co = driver_s.post(f"{BASE}/api/driver/checkout",
                           json={"trip_id": STATE["trip_id"], "odometer_end": 10420}, timeout=90)
        assert co.status_code == 200, f"checkout {co.status_code} {co.text[:300]}"
        time.sleep(1)
        f = driver_s.get(f"{BASE}/api/driver/fees", timeout=40).json()
        assert f["earned_total"] == STATE["earned_before"] + 450000, \
            f"earned tidak bertambah 450000: {STATE['earned_before']} -> {f['earned_total']}"
        entry = [e for e in f["entries"] if e["trip_id"] == STATE["trip_id"]]
        assert entry and entry[0]["rate"] == 150000 and entry[0]["days"] == 3
        STATE["available_after_earn"] = f["available"]
        # idempotensi: checkout ulang tidak boleh dobel kredit
        driver_s.post(f"{BASE}/api/driver/checkout",
                      json={"trip_id": STATE["trip_id"], "odometer_end": 10420}, timeout=90)
        f2 = driver_s.get(f"{BASE}/api/driver/fees", timeout=40).json()
        assert f2["earned_total"] == f["earned_total"], "fee dobel kredit saat checkout diulang"

    def test_withdraw_validasi_dan_reservasi(self, driver_s):
        avail = STATE["available_after_earn"]
        bad = driver_s.post(f"{BASE}/api/driver/fees/withdraw",
                            json={"amount": avail + 1, "bank_name": "BCA",
                                  "account_number": "1234567", "account_name": "Driver Satu"},
                            timeout=40)
        assert bad.status_code == 400, f"nominal > saldo harus 400, dapat {bad.status_code}"
        ok = driver_s.post(f"{BASE}/api/driver/fees/withdraw",
                           json={"amount": 200000, "bank_name": "BCA", "account_number": "1234567",
                                 "account_name": "Driver Satu", "note": "Penjaga INV-110"}, timeout=40)
        assert ok.status_code in (200, 201), f"{ok.status_code} {ok.text[:300]}"
        wd = ok.json()
        assert wd["status"] == "requested" and wd["amount"] == 200000
        STATE["wd_id"] = wd["id"]
        f = driver_s.get(f"{BASE}/api/driver/fees", timeout=40).json()
        assert f["requested_total"] >= 200000
        assert f["available"] == avail - 200000, "saldo tidak direservasi setelah pengajuan"

    def test_finance_pay_wajib_bukti(self, owner):
        bal = owner.get(f"{BASE}/api/payroll/fee-balances", timeout=40)
        assert bal.status_code == 200
        assert any(b["driver_id"] == STATE["driver_id"] for b in bal.json())
        lst = owner.get(f"{BASE}/api/payroll/withdrawals?status=requested", timeout=40)
        assert lst.status_code == 200
        assert any(w["id"] == STATE["wd_id"] for w in lst.json())
        url = f"{BASE}/api/payroll/withdrawals/{STATE['wd_id']}/pay"
        h = {"Authorization": owner.headers["Authorization"]}
        no_proof = requests.post(url, headers=h, data={"note": "x"}, timeout=40)
        assert no_proof.status_code == 422, f"tanpa bukti harus 422, dapat {no_proof.status_code}"
        pdf = requests.post(url, headers=h, files={"proof": ("b.pdf", b"%PDF-1.4 x", "application/pdf")},
                            timeout=60)
        assert pdf.status_code == 400, f"PDF harus ditolak 400, dapat {pdf.status_code} {pdf.text[:200]}"
        paid = requests.post(url, headers=h, files={"proof": ("bukti.png", PNG, "image/png")},
                             data={"note": "Penjaga INV-110"}, timeout=90)
        assert paid.status_code == 200, f"{paid.status_code} {paid.text[:300]}"
        doc = paid.json()
        assert doc["status"] == "paid" and doc["proof_url"], doc
        assert doc.get("expense_id")
        exps = owner.get(f"{BASE}/api/expenses?category=gaji_driver&limit=200", timeout=40)
        assert exps.status_code == 200
        rows = exps.json() if isinstance(exps.json(), list) else exps.json().get("items", [])
        mine = [e for e in rows if e.get("id") == doc["expense_id"]]
        assert mine, "expense gaji_driver tidak tercipta"
        assert mine[0]["amount"] == 200000 and mine[0]["paid"] is True
        again = requests.post(url, headers=h, files={"proof": ("b.png", PNG, "image/png")}, timeout=60)
        assert again.status_code == 400, "pembayaran ganda harus ditolak"

    def test_reject_mengembalikan_saldo(self, driver_s, owner):
        f0 = driver_s.get(f"{BASE}/api/driver/fees", timeout=40).json()
        req = driver_s.post(f"{BASE}/api/driver/fees/withdraw",
                            json={"amount": 100000, "bank_name": "BCA", "account_number": "1234567",
                                  "account_name": "Driver Satu"}, timeout=40)
        assert req.status_code in (200, 201), req.text[:200]
        wid = req.json()["id"]
        f1 = driver_s.get(f"{BASE}/api/driver/fees", timeout=40).json()
        assert f1["available"] == f0["available"] - 100000
        rej = owner.post(f"{BASE}/api/payroll/withdrawals/{wid}/reject",
                         json={"reason": "Data rekening salah"}, timeout=40)
        assert rej.status_code == 200, f"{rej.status_code} {rej.text[:300]}"
        assert rej.json()["status"] == "rejected"
        f2 = driver_s.get(f"{BASE}/api/driver/fees", timeout=40).json()
        assert f2["available"] == f0["available"], "saldo tidak kembali setelah tolak"

    def test_assign_tanpa_fee_tetap_jalan(self, owner):
        """Regresi: assign tanpa driver_fee_rate tidak error & tidak menimbulkan fee."""
        r = owner.post(f"{BASE}/api/dispatch/{STATE['booking_id']}/assign",
                       json={"driver_id": STATE["driver_id"], "vehicle_id": STATE["vehicle_id"]},
                       timeout=90)
        assert r.status_code in (200, 400), f"{r.status_code} {r.text[:300]}"
        if r.status_code == 400:
            assert "selesai" in r.text.lower() or "dibatalkan" in r.text.lower(), r.text[:200]


# ============================================================ 3) admin override driver workspace
class TestAdminOverride:
    def test_owner_lihat_sebagai_driver(self, owner):
        drivers = owner.get(f"{BASE}/api/drivers?limit=100", timeout=40).json()
        drivers = drivers if isinstance(drivers, list) else drivers.get("items", [])
        assert drivers, "tidak ada driver"
        did = STATE.get("driver_id") or drivers[0]["id"]
        t = owner.get(f"{BASE}/api/driver/tasks?driver_id={did}", timeout=40)
        assert t.status_code == 200, f"{t.status_code} {t.text[:200]}"
        s = owner.get(f"{BASE}/api/driver/summary?driver_id={did}", timeout=40)
        assert s.status_code == 200, f"{s.status_code} {s.text[:200]}"
        f = owner.get(f"{BASE}/api/driver/fees?driver_id={did}", timeout=40)
        assert f.status_code == 200 and f.json().get("driver_id") == did
        mt = owner.get(f"{BASE}/api/driver/my-trips?driver_id={did}", timeout=40)
        assert mt.status_code == 200
        assert all(x.get("driver_id") == did for x in mt.json()), "my-trips bocor driver lain"

    def test_owner_tanpa_driver_id_tidak_tertaut(self, owner):
        f = owner.get(f"{BASE}/api/driver/fees", timeout=40)
        assert f.status_code == 200
        assert f.json().get("is_driver") is False, "owner tanpa pilihan driver seharusnya kosong"

    def test_driver_tidak_bisa_override(self, driver_s, owner):
        drivers = owner.get(f"{BASE}/api/drivers?limit=100", timeout=40).json()
        drivers = drivers if isinstance(drivers, list) else drivers.get("items", [])
        other = [d for d in drivers if d["id"] != STATE.get("driver_id")]
        if not other:
            pytest.skip("hanya satu driver di seed")
        f = driver_s.get(f"{BASE}/api/driver/fees?driver_id={other[0]['id']}", timeout=40)
        assert f.status_code == 200
        assert f.json().get("driver_id") == STATE["driver_id"], "driver bisa melihat saldo driver lain!"


# ============================================================ 4) maintenance logic
class TestMaintenanceLogic:
    def test_dua_in_progress_satu_selesai(self, owner):
        vehs = owner.get(f"{BASE}/api/vehicles?limit=200", timeout=40).json()
        vehs = vehs if isinstance(vehs, list) else vehs.get("items", [])
        veh = next((v for v in vehs if v["id"] != STATE.get("vehicle_id")), vehs[0])
        STATE["mnt_vehicle"] = veh["id"]
        STATE["mnt_vehicle_status0"] = veh.get("status")
        ids = []
        for i in (1, 2):
            r = owner.post(f"{BASE}/api/maintenance",
                           json={"vehicle_id": veh["id"], "type": "servis",
                                 "title": f"Penjaga INV-110 kerja {i}", "status": "in_progress",
                                 "workshop": "Bengkel Uji"}, timeout=60)
            assert r.status_code in (200, 201), f"{r.status_code} {r.text[:300]}"
            ids.append(r.json()["id"])
        STATE["mnt_ids"] = ids
        v = owner.get(f"{BASE}/api/vehicles/{veh['id']}", timeout=40).json()
        assert v["status"] == "maintenance", f"armada harus maintenance, dapat {v['status']}"
        c1 = owner.post(f"{BASE}/api/maintenance/{ids[0]}/complete", json={"cost": 100000}, timeout=60)
        assert c1.status_code == 200, f"{c1.status_code} {c1.text[:300]}"
        v = owner.get(f"{BASE}/api/vehicles/{veh['id']}", timeout=40).json()
        assert v["status"] == "maintenance", \
            f"BUG: armada pulih '{v['status']}' padahal masih ada 1 perawatan in_progress"
        c2 = owner.post(f"{BASE}/api/maintenance/{ids[1]}/complete", json={"cost": 50000}, timeout=60)
        assert c2.status_code == 200, f"{c2.status_code} {c2.text[:300]}"
        v = owner.get(f"{BASE}/api/vehicles/{veh['id']}", timeout=40).json()
        assert v["status"] == "available", f"armada harus available, dapat {v['status']}"

    def test_maintenance_punya_kolom_workshop_terpisah(self, owner):
        rec = owner.get(f"{BASE}/api/maintenance/{STATE['mnt_ids'][0]}", timeout=40).json()
        assert rec["workshop"] == "Bengkel Uji"
        assert "Bengkel Uji" not in (rec.get("title") or ""), "nama bengkel dobel di judul pekerjaan"

    def test_cleanup_maintenance(self, owner):
        for mid in STATE.get("mnt_ids", []):
            r = owner.delete(f"{BASE}/api/maintenance/{mid}", timeout=40)
            assert r.status_code in (200, 204, 404)


# ============================================================ 5) pesanan online + RBAC
class TestOnlineOrdersAndRbac:
    def test_public_submit_membuat_pesanan_online(self):
        cfg = requests.get(f"{BASE}/api/public/booking/config", timeout=40)
        assert cfg.status_code == 200, f"{cfg.status_code} {cfg.text[:200]}"
        conf = cfg.json()
        service = (conf.get("enabled_services") or ["daily_rental"])[0]
        found = None
        for day in (5, 8, 11, 14, 18, 21, 25):
            s = requests.post(f"{BASE}/api/public/booking/search",
                              json={"service": service, "start_datetime": f"2026-11-{day:02d}T08:00:00",
                                    "end_datetime": f"2026-11-{day:02d}T18:00:00", "pax": 4}, timeout=60)
            if s.status_code != 200:
                continue
            opts = [o for o in s.json().get("options", []) if o.get("available") is not False]
            if opts:
                found = (day, opts[0], s.json()["search"])
                break
        if not found:
            pytest.skip(f"tidak ada unit publik tersedia Nov 2026 (search: {s.status_code} {s.text[:200]})")
        day, opt, search = found
        uniq = uuid.uuid4().hex[:5]
        sub = requests.post(f"{BASE}/api/public/booking/submit",
                            json={"service": service, "vehicle_id": opt["vehicle"]["id"],
                                  "start_datetime": search["start_datetime"],
                                  "end_datetime": search["end_datetime"], "pax": 4,
                                  "name": f"Penjaga INV-{uniq}", "phone": f"08000009{uniq[:3]}",
                                  "origin": "Bandung", "destination": "Jakarta",
                                  "message": "uji iterasi 110",
                                  "idempotency_key": uuid.uuid4().hex}, timeout=90)
        assert sub.status_code == 200, f"submit {sub.status_code} {sub.text[:300]}"
        data = sub.json()
        assert data.get("code"), data
        STATE["online_code"] = data["code"]

    def test_booking_list_menandai_source_online(self, owner):
        if not STATE.get("online_code"):
            pytest.skip("pesanan online tidak terbuat")
        r = owner.get(f"{BASE}/api/bookings?limit=300", timeout=60)
        assert r.status_code == 200
        rows = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        mine = [b for b in rows if b.get("code") == STATE["online_code"]]
        assert mine, "pesanan online tidak muncul di GET /api/bookings"
        assert mine[0].get("source") == "web_booking", f"source salah: {mine[0].get('source')}"
        manual = [b for b in rows if b.get("id") == STATE.get("booking_id")]
        assert manual and manual[0].get("source") != "web_booking", "booking manual bertanda online"

    def test_rbac_marketing_403(self, marketing):
        for path in ("/api/driver/tasks", "/api/payroll/withdrawals", "/api/driver/fees",
                     "/api/payroll/fee-balances"):
            r = marketing.get(f"{BASE}{path}", timeout=40)
            assert r.status_code == 403, f"{path} harus 403 utk marketing, dapat {r.status_code}"

    def test_rbac_driver_tidak_akses_payroll(self, driver_s):
        r = driver_s.get(f"{BASE}/api/payroll/withdrawals", timeout=40)
        assert r.status_code == 403, f"driver harus 403 di /api/payroll/withdrawals, dapat {r.status_code}"

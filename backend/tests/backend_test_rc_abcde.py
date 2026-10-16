"""RC-A..RC-E regression tests (session: booking manual quote parity, master harga,
media health tri-state, destinasi relasi master)."""
import os
from datetime import datetime, timedelta

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
CREDS = {"email": "owner@demo.local", "password": "demo12345"}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json=CREDS, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"Login owner gagal: {r.status_code} {r.text[:300]}")
    token = r.json().get("token")
    assert token
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def vehicles(client):
    r = client.get(f"{BASE_URL}/api/vehicles", timeout=30)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    rows = data.get("items") if isinstance(data, dict) else data
    assert rows, "tidak ada armada di seed"
    return rows


def _find(rows, needle):
    for v in rows:
        if needle.lower() in (v.get("name", "") or "").lower():
            return v
    return None


@pytest.fixture(scope="module")
def created_bookings():
    return []


@pytest.fixture(scope="module", autouse=True)
def cleanup(client, created_bookings):
    yield
    for bid in created_bookings:
        client.post(f"{BASE_URL}/api/bookings/{bid}/cancel",
                    json={"reason": "TEST_cleanup"}, timeout=30)


def _future_weekday(offset_days=400):
    d = datetime.utcnow() + timedelta(days=offset_days)
    while d.weekday() >= 5:  # hindari surcharge akhir pekan
        d += timedelta(days=1)
    return d.replace(hour=8, minute=0, second=0, microsecond=0)


# ---------- RC-A: quote parity ----------
class TestRCAQuoteParity:
    def test_quote_uses_unit_day_rate(self, client, vehicles):
        v = _find(vehicles, "Premio 02")
        assert v, "unit Hiace Premio 02 tidak ditemukan"
        assert v.get("day_rate") == 1650000, f"seed day_rate berubah: {v.get('day_rate')}"
        start = _future_weekday()
        r = client.post(f"{BASE_URL}/api/pricing/quote", json={
            "vehicle_id": v["id"], "days": 1, "start_date": start.date().isoformat()}, timeout=30)
        assert r.status_code == 200, r.text[:400]
        q = r.json()
        assert q.get("total") == 2100000, f"quote total={q.get('total')} items={q.get('items')}"

    def test_booking_base_price_matches_quote(self, client, vehicles, created_bookings):
        v = _find(vehicles, "Premio 02")
        cust = client.get(f"{BASE_URL}/api/customers", timeout=30).json()
        cust_rows = cust.get("items") if isinstance(cust, dict) else cust
        cid = cust_rows[0]["id"]
        start = _future_weekday(420)
        end = start + timedelta(hours=8)
        qr = client.post(f"{BASE_URL}/api/pricing/quote", json={
            "vehicle_id": v["id"], "days": 1, "start_date": start.date().isoformat()}, timeout=30)
        expected = qr.json()["total"]
        r = client.post(f"{BASE_URL}/api/bookings", json={
            "customer_id": cid, "vehicle_id": v["id"],
            "start_datetime": start.isoformat(), "end_datetime": end.isoformat(),
            "base_price": 0, "destination": "Bali", "notes": "TEST_rc_a"}, timeout=40)
        assert r.status_code in (200, 201), r.text[:400]
        b = r.json()
        created_bookings.append(b["id"])
        assert b.get("base_price") == expected, f"base_price={b.get('base_price')} quote={expected}"
        g = client.get(f"{BASE_URL}/api/bookings/{b['id']}", timeout=30)
        assert g.status_code == 200
        assert g.json().get("base_price") == expected

    def test_overlap_rejected(self, client, vehicles, created_bookings):
        v = _find(vehicles, "Premio 02")
        cust = client.get(f"{BASE_URL}/api/customers", timeout=30).json()
        cust_rows = cust.get("items") if isinstance(cust, dict) else cust
        start = _future_weekday(420)
        end = start + timedelta(hours=8)
        r = client.post(f"{BASE_URL}/api/bookings", json={
            "customer_id": cust_rows[0]["id"], "vehicle_id": v["id"],
            "start_datetime": (start + timedelta(hours=2)).isoformat(),
            "end_datetime": end.isoformat(), "base_price": 0,
            "destination": "Bali", "notes": "TEST_overlap"}, timeout=40)
        if r.status_code in (200, 201):
            created_bookings.append(r.json().get("id"))
        assert r.status_code == 400, f"overlap tidak ditolak: {r.status_code} {r.text[:300]}"

    def test_unit_without_day_rate_uses_type_rate(self, client, vehicles, created_bookings):
        v = _find(vehicles, "Commuter Mitra")
        assert v, "unit Hiace Commuter Mitra tidak ditemukan"
        assert not v.get("day_rate"), f"unit ini seharusnya tanpa day_rate: {v.get('day_rate')}"
        rules = client.get(f"{BASE_URL}/api/pricing/rules", timeout=30).json()
        start = _future_weekday(440)
        q = client.post(f"{BASE_URL}/api/pricing/quote", json={
            "vehicle_id": v["id"], "days": 1, "start_date": start.date().isoformat()}, timeout=30)
        assert q.status_code == 200, q.text[:300]
        total = q.json()["total"]
        assert total > 0
        # basis harus tarif tipe
        ur = client.get(f"{BASE_URL}/api/pricing/unit-rates", timeout=30).json()
        row = [x for x in ur if x["id"] == v["id"]][0]
        assert "unit" not in row["rate_basis"], f"rate_basis={row['rate_basis']}"
        assert isinstance(rules, dict)


# ---------- RC-B: master harga ----------
class TestRCBMasterHarga:
    def test_list_unit_rates(self, client, vehicles):
        r = client.get(f"{BASE_URL}/api/pricing/unit-rates", timeout=30)
        assert r.status_code == 200, r.text[:300]
        rows = r.json()
        assert len(rows) == len(vehicles), f"{len(rows)} vs {len(vehicles)} armada"
        for row in rows:
            assert "effective_rate" in row and "rate_basis" in row
            assert isinstance(row["effective_rate"], (int, float))
            assert "_id" not in row

    def test_patch_unit_rate(self, client, vehicles):
        v = _find(vehicles, "Premio 01") or vehicles[0]
        orig = v.get("day_rate") or 0
        try:
            r = client.patch(f"{BASE_URL}/api/pricing/unit-rates/{v['id']}",
                             json={"day_rate": 1300000}, timeout=30)
            assert r.status_code == 200, r.text[:300]
            assert r.json()["day_rate"] == 1300000
            assert r.json()["effective_rate"] == 1300000
            rows = client.get(f"{BASE_URL}/api/pricing/unit-rates", timeout=30).json()
            row = [x for x in rows if x["id"] == v["id"]][0]
            assert row["effective_rate"] == 1300000
            assert "unit" in row["rate_basis"], row["rate_basis"]
        finally:
            client.patch(f"{BASE_URL}/api/pricing/unit-rates/{v['id']}",
                         json={"day_rate": orig}, timeout=30)

    def test_patch_unit_rate_404(self, client):
        r = client.patch(f"{BASE_URL}/api/pricing/unit-rates/nope-xyz",
                         json={"day_rate": 1000}, timeout=30)
        assert r.status_code == 404, r.status_code

    def test_vehicle_patch_ignores_price_fields(self, client, vehicles):
        v = _find(vehicles, "Premio 02")
        before = client.get(f"{BASE_URL}/api/vehicles/{v['id']}", timeout=30).json()
        r = client.patch(f"{BASE_URL}/api/vehicles/{v['id']}",
                         json={"day_rate": 9999999, "price_from": 8888888}, timeout=30)
        assert r.status_code in (200, 422), r.text[:300]
        after = client.get(f"{BASE_URL}/api/vehicles/{v['id']}", timeout=30).json()
        assert after.get("day_rate") == before.get("day_rate") == 1650000, after.get("day_rate")
        assert after.get("price_from") == before.get("price_from")


# ---------- RC-E: destinasi = relasi master ----------
class TestRCEDestination:
    def test_destination_options(self, client):
        r = client.get(f"{BASE_URL}/api/bookings/destination-options", timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        names = data.get("items") if isinstance(data, dict) else data
        flat = [(n.get("value") or n.get("name")) if isinstance(n, dict) else n for n in names]
        assert "Bali" in flat and "Bandung" in flat, flat

    def test_invalid_destination_rejected(self, client, vehicles):
        cust = client.get(f"{BASE_URL}/api/customers", timeout=30).json()
        cust_rows = cust.get("items") if isinstance(cust, dict) else cust
        v = _find(vehicles, "Premio 02")
        start = _future_weekday(460)
        r = client.post(f"{BASE_URL}/api/bookings", json={
            "customer_id": cust_rows[0]["id"], "vehicle_id": v["id"],
            "start_datetime": start.isoformat(),
            "end_datetime": (start + timedelta(hours=6)).isoformat(),
            "base_price": 0, "destination": "Planet Mars"}, timeout=30)
        assert r.status_code == 400, f"{r.status_code} {r.text[:300]}"
        assert "destinasi" in r.text.lower(), r.text[:300]

    def test_destination_canonicalized(self, client, vehicles, created_bookings):
        cust = client.get(f"{BASE_URL}/api/customers", timeout=30).json()
        cust_rows = cust.get("items") if isinstance(cust, dict) else cust
        v = _find(vehicles, "Premio 02")
        start = _future_weekday(470)
        r = client.post(f"{BASE_URL}/api/bookings", json={
            "customer_id": cust_rows[0]["id"], "vehicle_id": v["id"],
            "start_datetime": start.isoformat(),
            "end_datetime": (start + timedelta(hours=6)).isoformat(),
            "base_price": 0, "destination": "bali", "notes": "TEST_rc_e"}, timeout=40)
        assert r.status_code in (200, 201), r.text[:300]
        created_bookings.append(r.json()["id"])
        assert r.json().get("destination") == "Bali", r.json().get("destination")

    def test_empty_destination_allowed(self, client, vehicles, created_bookings):
        cust = client.get(f"{BASE_URL}/api/customers", timeout=30).json()
        cust_rows = cust.get("items") if isinstance(cust, dict) else cust
        v = _find(vehicles, "Premio 02")
        start = _future_weekday(480)
        r = client.post(f"{BASE_URL}/api/bookings", json={
            "customer_id": cust_rows[0]["id"], "vehicle_id": v["id"],
            "start_datetime": start.isoformat(),
            "end_datetime": (start + timedelta(hours=6)).isoformat(),
            "base_price": 0, "destination": "", "notes": "TEST_rc_e_empty"}, timeout=40)
        assert r.status_code in (200, 201), r.text[:300]
        created_bookings.append(r.json()["id"])

    def test_update_destination_validated(self, client, created_bookings):
        assert created_bookings, "butuh booking dari test sebelumnya"
        bid = created_bookings[0]
        bad = client.patch(f"{BASE_URL}/api/bookings/{bid}",
                           json={"destination": "Kota Antah Berantah"}, timeout=30)
        assert bad.status_code == 400, bad.status_code
        ok = client.patch(f"{BASE_URL}/api/bookings/{bid}",
                          json={"destination": "bandung"}, timeout=30)
        assert ok.status_code == 200, ok.text[:300]
        g = client.get(f"{BASE_URL}/api/bookings/{bid}", timeout=30).json()
        assert g.get("destination") == "Bandung", g.get("destination")


# ---------- RC-C: media health tri-state ----------
class TestRCCMediaHealth:
    def test_media_health_fields(self, client):
        r = client.get(f"{BASE_URL}/api/media/health", timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for f in ("missing_count", "missing", "unknown_count", "unknown", "storage"):
            assert f in d, f"field {f} hilang: {list(d.keys())}"
        assert d["missing_count"] == 0, d["missing"][:5]
        assert d["unknown_count"] == 0, d["unknown"][:5]

"""SSOT Batch 2 + Alarm Harga (iterasi 95).

Cakupan:
- master pickup_points (GET/POST idempotent)
- bookings.origin relasi master (create/update, warisan)
- leads.destination relasi master (create/update, destination-options)
- jalur publik LUNAK (public_quotation tidak menolak)
- Alarm Harga di /api/pricing/unit-rates (deviation_pct + warning)
"""
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
OWNER = {"email": "owner@demo.local", "password": "demo12345"}
MARKETING = {"email": "marketing@demo.local", "password": "demo12345"}


def _login(creds):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"Login {creds['email']} gagal: {r.status_code} {r.text[:300]}")
    token = r.json().get("token")
    assert token, "token kosong"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def client():
    return _login(OWNER)


@pytest.fixture(scope="module")
def marketing_client():
    return _login(MARKETING)


@pytest.fixture(scope="module")
def created_bookings():
    return []


@pytest.fixture(scope="module", autouse=True)
def cleanup(client, created_bookings):
    yield
    for bid in created_bookings:
        client.post(f"{BASE_URL}/api/bookings/{bid}/cancel",
                    json={"reason": "TEST_cleanup"}, timeout=30)


def _rows(data):
    return data.get("items") if isinstance(data, dict) else data


# --- Master titik jemput ------------------------------------------------------------
class TestPickupPoints:
    def test_list_seed(self, client):
        r = client.get(f"{BASE_URL}/api/pickup-points", timeout=30)
        assert r.status_code == 200, r.text[:300]
        rows = _rows(r.json())
        names = {x["name"] for x in rows}
        for expected in ["Bandara Soekarno-Hatta", "Bandung", "Jakarta", "Stasiun Bandung"]:
            assert expected in names, f"{expected} tidak ada di master: {sorted(names)}"
        assert all(str(x.get("id", "")).startswith("pkp") for x in rows), rows

    def test_create_and_idempotent(self, client):
        r1 = client.post(f"{BASE_URL}/api/pickup-points",
                         json={"name": "Terminal Uji X"}, timeout=30)
        assert r1.status_code == 200, r1.text[:300]
        d1 = r1.json()
        assert d1["name"] == "Terminal Uji X"
        assert d1["id"].startswith("pkp")

        r2 = client.post(f"{BASE_URL}/api/pickup-points",
                         json={"name": "terminal UJI x"}, timeout=30)
        assert r2.status_code == 200, r2.text[:300]
        assert r2.json()["id"] == d1["id"], "POST nama sama (beda kapital) membuat duplikat"

        rows = _rows(client.get(f"{BASE_URL}/api/pickup-points", timeout=30).json())
        dup = [x for x in rows if x["name"].lower() == "terminal uji x"]
        assert len(dup) == 1, dup


# --- bookings.origin ----------------------------------------------------------------
@pytest.fixture(scope="module")
def booking_payload(client):
    cust = _rows(client.get(f"{BASE_URL}/api/customers", timeout=30).json())
    veh = _rows(client.get(f"{BASE_URL}/api/vehicles", timeout=30).json())
    assert cust and veh
    start = (datetime.utcnow() + timedelta(days=400)).strftime("%Y-%m-%dT08:00:00")
    end = (datetime.utcnow() + timedelta(days=401)).strftime("%Y-%m-%dT17:00:00")
    return {"customer_id": cust[0]["id"], "vehicle_id": veh[0]["id"],
            "start_datetime": start, "end_datetime": end,
            "destination": "Bali", "base_price": 2000000, "notes": "TEST_ssot_batch2"}


class TestBookingOrigin:
    def test_create_invalid_origin_rejected(self, client, booking_payload):
        body = dict(booking_payload, origin="Rumah Antah")
        r = client.post(f"{BASE_URL}/api/bookings", json=body, timeout=30)
        assert r.status_code == 400, f"{r.status_code} {r.text[:300]}"
        detail = str(r.json().get("detail", "")).lower()
        assert "titik jemput" in detail, detail

    def test_create_lowercase_origin_canonical(self, client, booking_payload, created_bookings):
        body = dict(booking_payload, origin="bandung")
        body["start_datetime"] = (datetime.utcnow() + timedelta(days=402)).strftime("%Y-%m-%dT08:00:00")
        body["end_datetime"] = (datetime.utcnow() + timedelta(days=403)).strftime("%Y-%m-%dT17:00:00")
        r = client.post(f"{BASE_URL}/api/bookings", json=body, timeout=30)
        assert r.status_code in (200, 201), r.text[:400]
        bid = r.json()["id"]
        created_bookings.append(bid)
        got = client.get(f"{BASE_URL}/api/bookings/{bid}", timeout=30)
        assert got.status_code == 200
        assert got.json()["origin"] == "Bandung", got.json().get("origin")

    def test_create_empty_origin_allowed(self, client, booking_payload, created_bookings):
        body = dict(booking_payload, origin="")
        body["start_datetime"] = (datetime.utcnow() + timedelta(days=404)).strftime("%Y-%m-%dT08:00:00")
        body["end_datetime"] = (datetime.utcnow() + timedelta(days=405)).strftime("%Y-%m-%dT17:00:00")
        r = client.post(f"{BASE_URL}/api/bookings", json=body, timeout=30)
        assert r.status_code in (200, 201), r.text[:400]
        bid = r.json()["id"]
        created_bookings.append(bid)
        assert (client.get(f"{BASE_URL}/api/bookings/{bid}", timeout=30).json().get("origin") or "") == ""

    def test_patch_origin(self, client, booking_payload, created_bookings):
        body = dict(booking_payload, origin="Jakarta")
        body["start_datetime"] = (datetime.utcnow() + timedelta(days=406)).strftime("%Y-%m-%dT08:00:00")
        body["end_datetime"] = (datetime.utcnow() + timedelta(days=407)).strftime("%Y-%m-%dT17:00:00")
        r = client.post(f"{BASE_URL}/api/bookings", json=body, timeout=30)
        assert r.status_code in (200, 201), r.text[:400]
        bid = r.json()["id"]
        created_bookings.append(bid)

        bad = client.patch(f"{BASE_URL}/api/bookings/{bid}", json={"origin": "Ngawur Sekali"}, timeout=30)
        assert bad.status_code == 400, f"{bad.status_code} {bad.text[:300]}"
        assert "titik jemput" in str(bad.json().get("detail", "")).lower()

        ok = client.patch(f"{BASE_URL}/api/bookings/{bid}",
                          json={"origin": "stasiun bandung"}, timeout=30)
        assert ok.status_code == 200, ok.text[:300]
        assert client.get(f"{BASE_URL}/api/bookings/{bid}", timeout=30).json()["origin"] == "Stasiun Bandung"

    def test_legacy_origin_booking_notes_editable(self, client):
        """Booking dgn origin warisan (di luar master) tetap bisa edit notes."""
        rows = _rows(client.get(f"{BASE_URL}/api/bookings?limit=100", timeout=30).json())
        master = {x["name"].lower() for x in _rows(
            client.get(f"{BASE_URL}/api/pickup-points", timeout=30).json())}
        legacy = next((b for b in rows if (b.get("origin") or "").strip()
                       and (b.get("origin") or "").strip().lower() not in master
                       and b.get("status") not in ("cancelled", "completed")), None)
        if not legacy:
            pytest.skip("tidak ada booking warisan dgn origin di luar master")
        r = client.patch(f"{BASE_URL}/api/bookings/{legacy['id']}",
                         json={"notes": "TEST_legacy_edit"}, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        after = client.get(f"{BASE_URL}/api/bookings/{legacy['id']}", timeout=30).json()
        assert after["notes"] == "TEST_legacy_edit"
        assert after["origin"] == legacy["origin"], "origin warisan berubah tanpa diminta"


# --- leads.destination --------------------------------------------------------------
class TestLeadDestination:
    def test_destination_options_owner_and_marketing(self, client, marketing_client):
        for c, who in ((client, "owner"), (marketing_client, "marketing")):
            r = c.get(f"{BASE_URL}/api/leads/destination-options", timeout=30)
            assert r.status_code == 200, f"{who}: {r.status_code} {r.text[:300]}"
            rows = _rows(r.json())
            assert rows, f"{who}: opsi destinasi kosong"
            labels = [x if isinstance(x, str) else (x.get("label") or x.get("name") or x.get("value"))
                      for x in rows]
            assert any("Bali" in str(x) for x in labels), labels

    def test_create_invalid_destination_rejected(self, client):
        r = client.post(f"{BASE_URL}/api/leads", json={
            "customer_name": "TEST_lead_invalid", "phone": "08123400001",
            "destination": "Antah Berantah"}, timeout=30)
        assert r.status_code == 400, f"{r.status_code} {r.text[:300]}"
        assert "destinasi" in str(r.json().get("detail", "")).lower()

    def test_create_lowercase_destination_canonical(self, client):
        r = client.post(f"{BASE_URL}/api/leads", json={
            "customer_name": "TEST_lead_bali", "phone": "08123400002",
            "destination": "bali"}, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        lead = r.json()
        assert lead["destination"] == "Bali", lead.get("destination")
        got = client.get(f"{BASE_URL}/api/leads/{lead['id']}", timeout=30)
        assert got.status_code == 200
        assert got.json()["destination"] == "Bali"

        bad = client.patch(f"{BASE_URL}/api/leads/{lead['id']}",
                           json={"destination": "Tempat Ngawur"}, timeout=30)
        assert bad.status_code == 400, f"{bad.status_code} {bad.text[:300]}"

    def test_create_empty_destination_allowed(self, client):
        r = client.post(f"{BASE_URL}/api/leads", json={
            "customer_name": "TEST_lead_empty", "phone": "08123400003",
            "destination": ""}, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        assert (r.json().get("destination") or "") == ""


# --- jalur publik (lunak) -----------------------------------------------------------
class TestPublicQuotationSoft:
    def test_unknown_destination_accepted_as_is(self):
        r = requests.post(f"{BASE_URL}/api/public/quotation", json={
            "name": "TEST_publik_aneh", "phone": "08123400010",
            "destination": "Tempat Aneh Sekali", "pax": 4,
            "message": "TEST_ssot_batch2"}, timeout=30)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:300]}"
        body = r.json()
        assert body.get("ok") is not False, body
        dest = body.get("destination") or (body.get("lead") or {}).get("destination")
        if dest is not None:
            assert dest == "Tempat Aneh Sekali", body

    def test_known_slug_normalized(self, client):
        r = requests.post(f"{BASE_URL}/api/public/quotation", json={
            "name": "TEST_publik_bromo", "phone": "08123400011",
            "destination": "bromo", "pax": 2, "message": "TEST_ssot_batch2"}, timeout=30)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:300]}"
        leads = _rows(client.get(f"{BASE_URL}/api/leads?q=TEST_publik_bromo", timeout=30).json())
        assert leads, "lead publik tidak terbuat"
        assert leads[0]["destination"] == "Gunung Bromo", leads[0].get("destination")


# --- Alarm Harga --------------------------------------------------------------------
@pytest.fixture(scope="module")
def unit_rates(client):
    r = client.get(f"{BASE_URL}/api/pricing/unit-rates", timeout=30)
    assert r.status_code == 200, r.text[:300]
    return _rows(r.json())


class TestPriceAlarm:
    def test_list_has_alarm_fields(self, unit_rates):
        assert unit_rates
        for row in unit_rates:
            assert "type_rate" in row and "deviation_pct" in row and "warning" in row, row

    def test_premio_deviation_alarm(self, client, unit_rates):
        premio = next((v for v in unit_rates if "premio" in (v.get("name") or "").lower()), None)
        assert premio, [v.get("name") for v in unit_rates]
        original = premio.get("day_rate") or 0
        try:
            r = client.patch(f"{BASE_URL}/api/pricing/unit-rates/{premio['id']}",
                             json={"day_rate": 5000000}, timeout=30)
            assert r.status_code == 200, r.text[:300]
            d = r.json()
            assert d["deviation_pct"] is not None and abs(d["deviation_pct"] - 233) <= 2, d
            assert "menyimpang" in (d.get("warning") or "").lower(), d

            rows = _rows(client.get(f"{BASE_URL}/api/pricing/unit-rates", timeout=30).json())
            row = next(v for v in rows if v["id"] == premio["id"])
            assert "menyimpang" in (row.get("warning") or "").lower(), row

            r2 = client.patch(f"{BASE_URL}/api/pricing/unit-rates/{premio['id']}",
                              json={"day_rate": 1600000}, timeout=30)
            assert r2.status_code == 200, r2.text[:300]
            d2 = r2.json()
            assert (d2.get("warning") or "") == "", d2
            assert abs(d2["deviation_pct"]) < 50, d2
        finally:
            back = client.patch(f"{BASE_URL}/api/pricing/unit-rates/{premio['id']}",
                                json={"day_rate": original}, timeout=30)
            assert back.status_code == 200, back.text[:300]
            assert back.json()["day_rate"] == int(original)

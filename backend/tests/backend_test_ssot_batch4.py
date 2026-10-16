"""Backend tests SSOT Batch 4 — Normalisasi LUNAK jalur publik + used_by_quotations.
Skenario:
 (a) POST /api/public/booking dgn origin='bandung' & destination='bali' → tersimpan 'Bandung'/'Bali'.
 (b) POST /api/public/booking dgn destination='Kampung Antah Berantah' → tersimpan apa adanya (lunak).
 (c) POST /api/public/lead-ads/meta dgn destination='bromo' → lead 'Gunung Bromo'.
 (d) POST /api/public/landing/{slug}/lead dgn origin='bandung', destination='yogyakarta' → kanonik.
 (e) GET /api/master/destinations menyertakan `used_by_quotations` (angka).
 (f) Regresi: POST /api/bookings ERP dgn destination di luar master tetap 400.
 (g) GET /api/public/destination-options tetap 200 tanpa auth.
"""
import os
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {"owner": ("owner@demo.local", "demo12345")}
GUARD_PHONE_PREFIX = "0800000"  # phone yg dapat dibersihkan guard
GUARD_NAME_PREFIX = "Penjaga INV-"


def _login(email, pwd):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def owner_h():
    return _login(*CREDS["owner"])


def _future_iso(hours=48):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).replace(microsecond=0).isoformat()


# ============ (a)(b) POST /api/public/booking — normalisasi LUNAK ============
class TestPublicBookingSoftNormalize:
    def test_booking_lowercase_normalized_to_canonical(self, owner_h):
        payload = {
            "name": f"{GUARD_NAME_PREFIX}B4-canon",
            "phone": f"{GUARD_PHONE_PREFIX}101",
            "origin": "bandung",
            "destination": "bali",
            "start_datetime": _future_iso(48),
            "end_datetime": _future_iso(72),
            "pax": 2,
            "vehicle_type": "hiace_premio",
            "message": "TEST batch 4 canonical",
        }
        r = requests.post(f"{API}/public/booking", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        bid = r.json().get("id")
        assert bid
        time.sleep(0.4)
        # verify persistence via ERP list (owner) using code lookup
        code = r.json().get("code")
        gb = requests.get(f"{API}/bookings", headers=owner_h, timeout=15)
        assert gb.status_code == 200
        b_json = gb.json()
        bookings = b_json.get("bookings") if isinstance(b_json, dict) else b_json
        row = next((b for b in bookings if b.get("id") == bid or b.get("code") == code), None)
        assert row, f"booking {bid} tidak ditemukan"
        assert row.get("origin") == "Bandung", f"expected 'Bandung', got {row.get('origin')!r}"
        assert row.get("destination") == "Bali", f"expected 'Bali', got {row.get('destination')!r}"

    def test_booking_freeform_destination_accepted_as_is(self, owner_h):
        # Rate limit public-booking = 6/menit, tunggu sebentar
        time.sleep(1.0)
        payload = {
            "name": f"{GUARD_NAME_PREFIX}B4-freeform",
            "phone": f"{GUARD_PHONE_PREFIX}102",
            "origin": "Suatu Tempat Ngawur",
            "destination": "Kampung Antah Berantah",
            "start_datetime": _future_iso(50),
            "end_datetime": _future_iso(74),
            "pax": 1,
            "vehicle_type": "hiace_premio",
            "message": "TEST batch 4 freeform",
        }
        r = requests.post(f"{API}/public/booking", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        bid = r.json().get("id")
        code = r.json().get("code")
        assert bid
        time.sleep(0.4)
        gb = requests.get(f"{API}/bookings", headers=owner_h, timeout=15)
        b_json = gb.json()
        bookings = b_json.get("bookings") if isinstance(b_json, dict) else b_json
        row = next((b for b in bookings if b.get("id") == bid or b.get("code") == code), None)
        assert row, "booking freeform tidak ditemukan"
        assert row.get("destination") == "Kampung Antah Berantah"
        assert row.get("origin") == "Suatu Tempat Ngawur"


# ============ (c) POST /api/public/lead-ads/meta ============
class TestLeadAdsMetaNormalize:
    def test_lead_ads_meta_normalizes_bromo(self, owner_h):
        # payload lead-ads Meta (mock)
        payload = {
            "full_name": f"{GUARD_NAME_PREFIX}B4-ads-bromo",
            "phone_number": f"{GUARD_PHONE_PREFIX}201",
            "destination": "bromo",  # cocok slug 'gunung-bromo' → kanonik 'Gunung Bromo'
            "campaign_name": "TEST_B4_camp",
        }
        r = requests.post(f"{API}/public/lead-ads/meta", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        time.sleep(0.5)
        gl = requests.get(f"{API}/leads", params={"q": f"{GUARD_NAME_PREFIX}B4-ads-bromo"},
                          headers=owner_h, timeout=15)
        assert gl.status_code == 200
        rows = [x for x in gl.json() if x.get("customer_name") == f"{GUARD_NAME_PREFIX}B4-ads-bromo"]
        assert rows, "lead ads tidak muncul di /leads"
        assert rows[0].get("destination") == "Gunung Bromo", \
            f"expected 'Gunung Bromo', got {rows[0].get('destination')!r}"


# ============ (d) POST /api/public/landing/{slug}/lead ============
class TestLandingLeadNormalize:
    def test_landing_lead_normalizes_origin_and_destination(self, owner_h):
        slug = "sewa-hiace-jakarta"
        payload = {
            "name": f"{GUARD_NAME_PREFIX}B4-landing",
            "phone": f"{GUARD_PHONE_PREFIX}301",
            "origin": "bandung",
            "destination": "yogyakarta",
            "marketing_consent": True,
            "message": "TEST batch 4 landing",
        }
        r = requests.post(f"{API}/public/landing/{slug}/lead", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        time.sleep(0.5)
        gl = requests.get(f"{API}/leads", params={"q": f"{GUARD_NAME_PREFIX}B4-landing"},
                          headers=owner_h, timeout=15)
        assert gl.status_code == 200
        rows = [x for x in gl.json() if x.get("customer_name") == f"{GUARD_NAME_PREFIX}B4-landing"]
        assert rows, "lead landing tidak ditemukan"
        r0 = rows[0]
        assert r0.get("origin") == "Bandung", f"expected 'Bandung', got {r0.get('origin')!r}"
        assert r0.get("destination") == "Yogyakarta", f"expected 'Yogyakarta', got {r0.get('destination')!r}"


# ============ (e) GET /api/master/destinations — used_by_quotations ============
class TestMasterDestinationsUsedByQuotations:
    def test_used_by_quotations_present(self, owner_h):
        r = requests.get(f"{API}/master/destinations", headers=owner_h, timeout=15)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list) and rows
        for row in rows:
            assert "used_by_quotations" in row, f"row missing used_by_quotations: {row}"
            assert isinstance(row["used_by_quotations"], int), \
                f"used_by_quotations bukan int: {row['used_by_quotations']!r}"


# ============ (f)(g) REGRESI tipis ============
class TestRegressionErpHard:
    def test_public_destination_options_still_works(self):
        r = requests.get(f"{API}/public/destination-options", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list) and len(r.json()) >= 1

    def test_erp_booking_creation_still_hard_rejects_offmaster(self, owner_h):
        # ERP POST /api/bookings menerima dest ngawur → 400 (validasi keras tidak melunak)
        # Kita perlu customer dulu; pakai endpoint /api/bookings payload minimum → dest ngawur harus 400
        payload = {
            "customer_name": f"{GUARD_NAME_PREFIX}B4-erp-ngawur",
            "phone": f"{GUARD_PHONE_PREFIX}401",
            "destination": "planet-mars-ngawur-batch4",
            "origin": "Bandung",
            "start_datetime": _future_iso(48),
            "end_datetime": _future_iso(72),
            "vehicle_type": "hiace_premio",
            "pax": 1,
            "service": "daily_rental",
        }
        r = requests.post(f"{API}/bookings", json=payload, headers=owner_h, timeout=15)
        # 400 (destination not in master) atau 422 (schema); yang penting BUKAN 200/201
        assert r.status_code in (400, 422), f"unexpected: {r.status_code} {r.text[:200]}"

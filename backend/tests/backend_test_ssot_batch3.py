"""Backend tests SSOT Batch 3 — Master Data + Lead→Booking + destination gate.
Skenario: quotations destination_or_400, public/destination-options, /public/quotation lunak,
RBAC /master/destinations, rename+cascade+toggle, prepare-booking dari lead.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {
    "owner": ("owner@demo.local", "demo12345"),
    "ops": ("ops@demo.local", "demo12345"),
    "mkt": ("marketing@demo.local", "demo12345"),
    "drv": ("driver@demo.local", "demo12345"),
}


def _login(email, pwd):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def owner_h():
    return _login(*CREDS["owner"])


@pytest.fixture(scope="module")
def ops_h():
    return _login(*CREDS["ops"])


@pytest.fixture(scope="module")
def mkt_h():
    return _login(*CREDS["mkt"])


@pytest.fixture(scope="module")
def drv_h():
    return _login(*CREDS["drv"])


# ============ (a) POST/PATCH /api/quotations dgn destination_or_400 ============
class TestQuotationDestinationGate:
    def test_public_destination_options_no_auth(self):
        r = requests.get(f"{API}/public/destination-options", timeout=10)
        assert r.status_code == 200
        opts = r.json()
        assert isinstance(opts, list) and len(opts) >= 1
        keys = set(opts[0].keys())
        assert {"value", "label", "slug"}.issubset(keys)
        names = [o["value"] for o in opts]
        assert "Bali" in names or any(n.lower() == "bali" for n in names)

    def test_create_quotation_ngawur_rejected(self, owner_h):
        payload = {"customer_name": "TEST_QuoNgawur", "phone": "081200011111",
                   "destination": "ngawur-tidak-ada", "pax": 2, "days": 1,
                   "vehicle_type": "hiace_premio"}
        r = requests.post(f"{API}/quotations", json=payload, headers=owner_h, timeout=15)
        assert r.status_code == 400, r.text
        assert "master" in r.text.lower() or "tidak ada" in r.text.lower()

    def test_create_quotation_bali_lowercase_normalized(self, owner_h):
        payload = {"customer_name": "TEST_QuoBali", "phone": "081200022222",
                   "destination": "bali", "pax": 2, "days": 1,
                   "vehicle_type": "hiace_premio"}
        r = requests.post(f"{API}/quotations", json=payload, headers=owner_h, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["destination"] == "Bali", f"expected canonical 'Bali', got {data['destination']!r}"
        # verify persistence
        qid = data["id"]
        g = requests.get(f"{API}/quotations/{qid}", headers=owner_h, timeout=10)
        assert g.status_code == 200
        assert g.json()["destination"] == "Bali"
        # keep id for patch tests
        pytest.quo_bali_id = qid

    def test_patch_quotation_destination_ngawur_rejected(self, owner_h):
        qid = getattr(pytest, "quo_bali_id", None)
        assert qid, "prerequisite failed"
        r = requests.patch(f"{API}/quotations/{qid}",
                           json={"destination": "planet-mars-ngawur"},
                           headers=owner_h, timeout=15)
        assert r.status_code == 400, r.text

    def test_patch_quotation_no_destination_change_ok(self, owner_h):
        qid = getattr(pytest, "quo_bali_id", None)
        assert qid
        r = requests.patch(f"{API}/quotations/{qid}",
                           json={"notes": "TEST_notes_only"},
                           headers=owner_h, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["destination"] == "Bali"
        assert r.json()["notes"] == "TEST_notes_only"


# ============ (b) Public quotation LUNAK: teks warisan diterima ============
class TestPublicQuotationLunak:
    def test_public_quotation_accepts_legacy_free_text(self):
        payload = {"name": "TEST_publik_legacy_b3", "phone": "081277788899",
                   "destination": "Kampung Halaman Nenek",  # tidak di master
                   "message": "test batch3", "marketing_consent": True}
        r = requests.post(f"{API}/public/quotation", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "received"

    def test_public_quotation_normalizes_master_match(self):
        payload = {"name": "TEST_publik_bali_b3", "phone": "081277788800",
                   "destination": "bali",  # cocok master → dinormalkan
                   "marketing_consent": True}
        r = requests.post(f"{API}/public/quotation", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        # verify lead saved with canonical name
        h = _login(*CREDS["owner"])
        time.sleep(0.4)
        gl = requests.get(f"{API}/leads", params={"q": "TEST_publik_bali_b3"}, headers=h, timeout=10)
        assert gl.status_code == 200
        rows = [x for x in gl.json() if x.get("customer_name") == "TEST_publik_bali_b3"]
        assert rows and rows[0]["destination"] == "Bali", f"expected Bali, got {rows and rows[0].get('destination')}"


# ============ RBAC (c) /api/master/destinations ============
class TestMasterRBAC:
    def test_owner_ok(self, owner_h):
        r = requests.get(f"{API}/master/destinations", headers=owner_h, timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_ops_admin_ok(self, ops_h):
        r = requests.get(f"{API}/master/destinations", headers=ops_h, timeout=10)
        assert r.status_code == 200

    def test_marketing_403(self, mkt_h):
        r = requests.get(f"{API}/master/destinations", headers=mkt_h, timeout=10)
        assert r.status_code == 403, r.text

    def test_driver_403(self, drv_h):
        r = requests.get(f"{API}/master/destinations", headers=drv_h, timeout=10)
        assert r.status_code == 403, r.text


# ============ (c) Rename+cascade + toggle nonaktif ============
class TestMasterRenameAndToggle:
    def test_rename_bandung_cascade_then_restore(self, owner_h):
        # find Bandung
        r = requests.get(f"{API}/master/destinations", headers=owner_h, timeout=10)
        assert r.status_code == 200
        rows = r.json()
        bd = next((x for x in rows if x["name"] == "Bandung"), None)
        assert bd, f"Bandung not present in master. Names: {[x['name'] for x in rows]}"
        dest_id = bd["id"]
        # rename Bandung -> Bandung Kota
        pr = requests.patch(f"{API}/master/destinations/{dest_id}",
                            json={"name": "Bandung Kota"}, headers=owner_h, timeout=15)
        assert pr.status_code == 200, pr.text
        cascade = pr.json().get("cascade", {})
        assert isinstance(cascade, dict)
        # cascade check via GET bookings
        gb = requests.get(f"{API}/bookings", headers=owner_h, timeout=15)
        assert gb.status_code == 200
        b_json = gb.json()
        bookings = b_json.get("bookings") if isinstance(b_json, dict) else b_json
        bandung_old = [b for b in bookings if b.get("destination") == "Bandung"]
        assert not bandung_old, f"still have bookings with old name 'Bandung': {len(bandung_old)}"
        # RESTORE
        rr = requests.patch(f"{API}/master/destinations/{dest_id}",
                            json={"name": "Bandung"}, headers=owner_h, timeout=15)
        assert rr.status_code == 200, rr.text

    def test_toggle_destination_hides_from_selector_then_restore(self, owner_h):
        # pick any active destination we can toggle safely (bukan Bandung yg baru direname)
        r = requests.get(f"{API}/master/destinations", headers=owner_h, timeout=10)
        rows = r.json()
        target = next((x for x in rows if x["name"] not in ("Bandung",) and x.get("ops_active", True)), None)
        assert target, "no togglable destination"
        did = target["id"]
        nm = target["name"]
        # deactivate
        pr = requests.patch(f"{API}/master/destinations/{did}",
                            json={"ops_active": False}, headers=owner_h, timeout=15)
        assert pr.status_code == 200
        # check selector public options no longer has it
        po = requests.get(f"{API}/public/destination-options", timeout=10).json()
        assert nm not in [o["value"] for o in po], f"{nm} still visible in public options"
        # check /api/bookings/destination-options too (owner)
        bo = requests.get(f"{API}/bookings/destination-options", headers=owner_h, timeout=10)
        assert bo.status_code == 200
        assert nm not in [o.get("value") for o in bo.json()]
        # ATTEMPT to create quotation with that name → must reject
        rej = requests.post(f"{API}/quotations",
                            json={"customer_name": "TEST_inactive_dest", "phone": "081200099999",
                                  "destination": nm, "pax": 1, "days": 1,
                                  "vehicle_type": "hiace_premio"}, headers=owner_h, timeout=15)
        assert rej.status_code == 400
        # RESTORE active
        rr = requests.patch(f"{API}/master/destinations/{did}",
                            json={"ops_active": True}, headers=owner_h, timeout=15)
        assert rr.status_code == 200


# ============ (d) prepare-booking dari lead ============
class TestPrepareBookingFromLead:
    def test_prepare_booking_returns_prefill(self, owner_h):
        # find a lead with name+phone+destination
        r = requests.get(f"{API}/leads", headers=owner_h, timeout=10)
        assert r.status_code == 200
        leads = r.json()
        cand = next((L for L in leads if L.get("customer_name") and L.get("phone")
                     and L.get("destination")), None)
        assert cand, "no suitable lead"
        pr = requests.post(f"{API}/leads/{cand['id']}/prepare-booking",
                           headers=owner_h, timeout=15)
        assert pr.status_code == 200, pr.text
        data = pr.json()
        assert data.get("customer_id")
        assert data.get("customer_name")
        assert data.get("destination")  # dari lead


# ============ RBAC pickup master (bonus) ============
class TestPickupRBAC:
    def test_marketing_forbidden_master(self, mkt_h):
        r = requests.get(f"{API}/master/pickup-points", headers=mkt_h, timeout=10)
        assert r.status_code == 403

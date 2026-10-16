"""Backend tests for Leads/Quotations/Expenses edit+delete (iteration 5)."""
import os
import pytest
import requests

def _load_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert v, "REACT_APP_BACKEND_URL missing"
    return v.rstrip("/")


BASE_URL = _load_url()
OWNER = {"email": "owner@demo.local", "password": "demo12345"}
MARKETING = {"email": "marketing@demo.local", "password": "demo12345"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def owner_headers():
    return {"Authorization": f"Bearer {_login(OWNER)}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def marketing_headers():
    return {"Authorization": f"Bearer {_login(MARKETING)}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def a_destination(owner_headers):
    r = requests.get(f"{BASE_URL}/api/leads/destination-options", headers=owner_headers, timeout=30)
    assert r.status_code == 200, r.text
    opts = r.json()
    assert opts, "no destinations seeded"
    return opts[0]["value"]


# -------------------- LEADS --------------------
class TestLeads:
    def test_create_patch_delete(self, owner_headers, a_destination):
        payload = {"customer_name": "TEST_Del Lead", "phone": "081200000001",
                   "destination": a_destination, "pax": 2, "value": 100000, "source": "manual"}
        r = requests.post(f"{BASE_URL}/api/leads", json=payload, headers=owner_headers, timeout=30)
        assert r.status_code == 200, r.text
        lead = r.json()
        lid = lead["id"]

        # PATCH
        r = requests.patch(f"{BASE_URL}/api/leads/{lid}",
                           json={"customer_name": "TEST_Del Lead 2", "pax": 5, "value": 250000,
                                 "message": "note"}, headers=owner_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["customer_name"] == "TEST_Del Lead 2"
        assert d["pax"] == 5
        assert float(d["value"]) == 250000.0

        # Add an activity so lead_activities exists
        requests.post(f"{BASE_URL}/api/leads/{lid}/activities",
                      json={"type": "note", "text": "hello"}, headers=owner_headers, timeout=30)

        # DELETE
        r = requests.delete(f"{BASE_URL}/api/leads/{lid}", headers=owner_headers, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        # GET -> 404
        r = requests.get(f"{BASE_URL}/api/leads/{lid}", headers=owner_headers, timeout=30)
        assert r.status_code == 404

    def test_delete_won_lead_400(self, owner_headers, a_destination):
        payload = {"customer_name": "TEST_Won Lead", "phone": "081200000002",
                   "destination": a_destination, "pax": 1, "value": 50000}
        r = requests.post(f"{BASE_URL}/api/leads", json=payload, headers=owner_headers, timeout=30)
        assert r.status_code == 200
        lid = r.json()["id"]
        r = requests.post(f"{BASE_URL}/api/leads/{lid}/stage",
                          json={"stage": "won"}, headers=owner_headers, timeout=30)
        assert r.status_code == 200
        r = requests.delete(f"{BASE_URL}/api/leads/{lid}", headers=owner_headers, timeout=30)
        assert r.status_code == 400, r.text
        # Cleanup: reset back to 'quoted' then patch DB isn't accessible; leave as-is (test data)

    def test_delete_nonexistent_lead_404(self, owner_headers):
        r = requests.delete(f"{BASE_URL}/api/leads/led_nonexistent_xxx", headers=owner_headers, timeout=30)
        assert r.status_code == 404


# -------------------- QUOTATIONS --------------------
class TestQuotations:
    def _create(self, owner_headers, a_destination, name="TEST_Quo"):
        body = {
            "customer_name": name, "phone": "081200000010",
            "destination": a_destination, "pax": 2, "valid_days": 7,
            "items": [{"label": "Sewa", "amount": 1000000},
                      {"label": "BBM", "amount": 200000}],
        }
        r = requests.post(f"{BASE_URL}/api/quotations", json=body, headers=owner_headers, timeout=30)
        assert r.status_code == 200, r.text
        return r.json()

    def test_edit_and_delete_draft(self, owner_headers, a_destination):
        q = self._create(owner_headers, a_destination, "TEST_Quo Edit")
        qid = q["id"]
        # PATCH: change name & items
        new_items = [{"label": "Sewa", "amount": 1500000},
                     {"label": "BBM", "amount": 250000},
                     {"label": "Tol", "amount": 75000}]
        r = requests.patch(f"{BASE_URL}/api/quotations/{qid}",
                           json={"customer_name": "TEST_Quo Edited", "items": new_items},
                           headers=owner_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["customer_name"] == "TEST_Quo Edited"
        assert d["total"] == 1825000
        assert d["subtotal"] == 1825000
        assert len(d["items"]) == 3

        # DELETE draft
        r = requests.delete(f"{BASE_URL}/api/quotations/{qid}", headers=owner_headers, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        # 404 after
        r = requests.get(f"{BASE_URL}/api/quotations/{qid}", headers=owner_headers, timeout=30)
        assert r.status_code == 404

    def test_delete_accepted_400(self, owner_headers, a_destination):
        q = self._create(owner_headers, a_destination, "TEST_Quo Accept")
        qid = q["id"]
        r = requests.post(f"{BASE_URL}/api/quotations/{qid}/accept",
                          json={}, headers=owner_headers, timeout=30)
        assert r.status_code == 200, r.text
        # PATCH accepted -> 400
        r = requests.patch(f"{BASE_URL}/api/quotations/{qid}",
                           json={"customer_name": "X"}, headers=owner_headers, timeout=30)
        assert r.status_code == 400
        # DELETE accepted -> 400
        r = requests.delete(f"{BASE_URL}/api/quotations/{qid}", headers=owner_headers, timeout=30)
        assert r.status_code == 400
        # Cleanup: reject then delete
        requests.post(f"{BASE_URL}/api/quotations/{qid}/reject", json={}, headers=owner_headers, timeout=30)
        requests.delete(f"{BASE_URL}/api/quotations/{qid}", headers=owner_headers, timeout=30)

    def test_delete_nonexistent_quotation_404(self, owner_headers):
        r = requests.delete(f"{BASE_URL}/api/quotations/quo_nonexistent", headers=owner_headers, timeout=30)
        assert r.status_code == 404


# -------------------- EXPENSES --------------------
class TestExpenses:
    def test_edit_delete_expense_and_booking_link(self, owner_headers):
        # Create expense w/o booking
        body = {"category": "bbm", "amount": 50000, "note": "TEST_exp"}
        r = requests.post(f"{BASE_URL}/api/expenses", json=body, headers=owner_headers, timeout=30)
        assert r.status_code == 200, r.text
        exp = r.json()
        eid = exp["id"]
        assert exp["amount"] == 50000

        # Find a booking to link
        rb = requests.get(f"{BASE_URL}/api/bookings", headers=owner_headers, timeout=30)
        assert rb.status_code == 200
        bookings = rb.json()
        assert bookings, "no bookings seeded"
        b = bookings[0]

        # PATCH: change amount + link to booking
        r = requests.patch(f"{BASE_URL}/api/expenses/{eid}",
                           json={"amount": 75000, "note": "TEST_updated", "category": "tol",
                                 "booking_id": b["id"]},
                           headers=owner_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["amount"] == 75000
        assert d["note"] == "TEST_updated"
        assert d["category"] == "tol"
        assert d["booking_id"] == b["id"]
        assert d["booking_code"] == b.get("code")

        # Invalid booking_id -> 400
        r = requests.patch(f"{BASE_URL}/api/expenses/{eid}",
                           json={"booking_id": "bk_does_not_exist"},
                           headers=owner_headers, timeout=30)
        assert r.status_code == 400

        # DELETE
        r = requests.delete(f"{BASE_URL}/api/expenses/{eid}", headers=owner_headers, timeout=30)
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_delete_nonexistent_expense_404(self, owner_headers):
        r = requests.delete(f"{BASE_URL}/api/expenses/exp_none", headers=owner_headers, timeout=30)
        assert r.status_code == 404

    def test_marketing_admin_forbidden(self, marketing_headers):
        r = requests.get(f"{BASE_URL}/api/expenses", headers=marketing_headers, timeout=30)
        assert r.status_code == 403

"""
E16 Backend Testing: Pinjam Armada / Sub-charter
Tests RBAC, Partner CRUD, Sub-charter lifecycle, AP calculations, COGS, and WhatsApp notifications.
"""
import requests
import sys
from typing import Dict, Any
from datetime import datetime, timedelta

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

class E16TestRunner:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.tokens = {}
        self.errors = []
        self.test_data = {}

    def log(self, msg: str, level: str = "INFO"):
        prefix = {
            "INFO": "ℹ️",
            "PASS": "✅",
            "FAIL": "❌",
            "WARN": "⚠️",
        }.get(level, "•")
        print(f"{prefix} {msg}")

    def test(self, name: str, condition: bool, error_msg: str = ""):
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            self.log(f"{name}: PASS", "PASS")
            return True
        else:
            self.tests_failed += 1
            self.log(f"{name}: FAIL - {error_msg}", "FAIL")
            self.errors.append(f"{name}: {error_msg}")
            return False

    def login(self, email: str, password: str) -> Dict[str, Any]:
        """Login and store token"""
        self.log(f"Logging in as {email}...")
        try:
            resp = requests.post(
                f"{BASE_URL}/auth/login",
                json={"email": email, "password": password},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("token")
                if token:
                    self.tokens[email] = token
                    self.log(f"Login successful for {email}", "PASS")
                    return data
                else:
                    self.log(f"Login response missing token for {email}", "FAIL")
                    return {}
            else:
                self.log(f"Login failed for {email}: {resp.status_code}", "FAIL")
                return {}
        except Exception as e:
            self.log(f"Login exception for {email}: {e}", "FAIL")
            return {}

    def get(self, endpoint: str, email: str, params: Dict = None) -> requests.Response:
        """GET request with auth"""
        token = self.tokens.get(email)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return requests.get(f"{BASE_URL}{endpoint}", headers=headers, params=params, timeout=10)

    def post(self, endpoint: str, email: str, data: Dict = None) -> requests.Response:
        """POST request with auth"""
        token = self.tokens.get(email)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return requests.post(f"{BASE_URL}{endpoint}", headers=headers, json=data, timeout=10)

    def patch(self, endpoint: str, email: str, data: Dict = None) -> requests.Response:
        """PATCH request with auth"""
        token = self.tokens.get(email)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return requests.patch(f"{BASE_URL}{endpoint}", headers=headers, json=data, timeout=10)

    def delete(self, endpoint: str, email: str) -> requests.Response:
        """DELETE request with auth"""
        token = self.tokens.get(email)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return requests.delete(f"{BASE_URL}{endpoint}", headers=headers, timeout=10)

    def test_rbac(self):
        """Test RBAC: section 'partners' only for owner/ops_admin"""
        self.log("\n=== Testing RBAC for Partners Section ===")
        
        # Driver should get 403 on /api/partners
        resp = self.get("/partners", "driver@demo.local")
        self.test(
            "RBAC: Driver GET /api/partners returns 403",
            resp.status_code == 403,
            f"Expected 403, got {resp.status_code}"
        )
        
        # Driver should get 403 on /api/subcharters
        resp = self.get("/subcharters", "driver@demo.local")
        self.test(
            "RBAC: Driver GET /api/subcharters returns 403",
            resp.status_code == 403,
            f"Expected 403, got {resp.status_code}"
        )
        
        # Owner should get 200 on /api/partners
        resp = self.get("/partners", "owner@demo.local")
        self.test(
            "RBAC: Owner GET /api/partners returns 200",
            resp.status_code == 200,
            f"Expected 200, got {resp.status_code}"
        )
        
        # Ops admin should get 200 on /api/subcharters
        resp = self.get("/subcharters", "ops@demo.local")
        self.test(
            "RBAC: Ops Admin GET /api/subcharters returns 200",
            resp.status_code == 200,
            f"Expected 200, got {resp.status_code}"
        )

    def test_partner_crud(self):
        """Test Partner CRUD with AP summary"""
        self.log("\n=== Testing Partner CRUD ===")
        
        # List partners
        resp = self.get("/partners", "owner@demo.local")
        self.test(
            "GET /api/partners returns 200",
            resp.status_code == 200,
            f"Expected 200, got {resp.status_code}"
        )
        
        if resp.status_code == 200:
            partners = resp.json()
            self.test(
                "Partners list is array",
                isinstance(partners, list),
                f"Expected list, got {type(partners)}"
            )
            
            # Check seed data: should have at least 1 partner
            self.test(
                "Seed data: At least 1 partner exists",
                len(partners) >= 1,
                f"Expected >= 1 partner, got {len(partners)}"
            )
            
            if len(partners) > 0:
                partner = partners[0]
                # Check AP fields
                self.test(
                    "Partner has ap_total field",
                    "ap_total" in partner,
                    "Missing ap_total field"
                )
                self.test(
                    "Partner has ap_paid field",
                    "ap_paid" in partner,
                    "Missing ap_paid field"
                )
                self.test(
                    "Partner has ap_outstanding field",
                    "ap_outstanding" in partner,
                    "Missing ap_outstanding field"
                )
                self.test(
                    "Partner has subcharter_count field",
                    "subcharter_count" in partner,
                    "Missing subcharter_count field"
                )
                self.test(
                    "Partner has vehicle_count field",
                    "vehicle_count" in partner,
                    "Missing vehicle_count field"
                )
                
                # Store first partner for detail test
                self.test_data["partner_id"] = partner.get("id")
        
        # Create new partner
        new_partner = {
            "name": "Test Mitra E16",
            "pic": "Pak Test",
            "phone": "081234567890",
            "email": "test@mitra.id",
            "city": "Jakarta",
            "address": "Jl. Test 123",
            "rating": 4.5,
            "notes": "Test partner for E16",
            "status": "active"
        }
        resp = self.post("/partners", "owner@demo.local", new_partner)
        self.test(
            "POST /api/partners creates partner",
            resp.status_code == 200,
            f"Expected 200, got {resp.status_code}: {resp.text if resp.status_code != 200 else ''}"
        )
        
        if resp.status_code == 200:
            created = resp.json()
            self.test_data["test_partner_id"] = created.get("id")
            self.test(
                "Created partner has ID",
                "id" in created and created["id"],
                "Missing or empty ID"
            )
            self.test(
                "Created partner has correct name",
                created.get("name") == "Test Mitra E16",
                f"Expected 'Test Mitra E16', got {created.get('name')}"
            )
            # New partner should have zero AP
            self.test(
                "New partner has zero ap_outstanding",
                created.get("ap_outstanding") == 0,
                f"Expected 0, got {created.get('ap_outstanding')}"
            )
        
        # Get partner detail
        if "partner_id" in self.test_data:
            partner_id = self.test_data["partner_id"]
            resp = self.get(f"/partners/{partner_id}", "owner@demo.local")
            self.test(
                f"GET /api/partners/{partner_id} returns 200",
                resp.status_code == 200,
                f"Expected 200, got {resp.status_code}"
            )
            
            if resp.status_code == 200:
                detail = resp.json()
                self.test(
                    "Partner detail has subcharters array",
                    "subcharters" in detail and isinstance(detail["subcharters"], list),
                    "Missing or invalid subcharters field"
                )
                self.test(
                    "Partner detail has settlements array",
                    "settlements" in detail and isinstance(detail["settlements"], list),
                    "Missing or invalid settlements field"
                )
                self.test(
                    "Partner detail has vehicles array",
                    "vehicles" in detail and isinstance(detail["vehicles"], list),
                    "Missing or invalid vehicles field"
                )
        
        # Update partner
        if "test_partner_id" in self.test_data:
            partner_id = self.test_data["test_partner_id"]
            update_data = {"rating": 5.0, "notes": "Updated notes"}
            resp = self.patch(f"/partners/{partner_id}", "owner@demo.local", update_data)
            self.test(
                f"PATCH /api/partners/{partner_id} returns 200",
                resp.status_code == 200,
                f"Expected 200, got {resp.status_code}"
            )
            
            if resp.status_code == 200:
                updated = resp.json()
                self.test(
                    "Updated partner has new rating",
                    updated.get("rating") == 5.0,
                    f"Expected 5.0, got {updated.get('rating')}"
                )

    def test_subcharter_lifecycle(self):
        """Test Sub-charter lifecycle: requested -> confirmed -> settled/cancelled"""
        self.log("\n=== Testing Sub-charter Lifecycle ===")
        
        # Get a booking for testing
        resp = self.get("/bookings?limit=10", "owner@demo.local")
        if resp.status_code != 200 or not resp.json():
            self.log("No bookings available for sub-charter test", "WARN")
            return
        
        bookings = resp.json()
        booking = bookings[0]
        booking_id = booking.get("id")
        
        # Get a partner
        resp = self.get("/partners", "owner@demo.local")
        if resp.status_code != 200 or not resp.json():
            self.log("No partners available for sub-charter test", "WARN")
            return
        
        partners = resp.json()
        partner = partners[0]
        partner_id = partner.get("id")
        
        # Create sub-charter (status: requested)
        start = (datetime.now() + timedelta(days=10)).isoformat()
        end = (datetime.now() + timedelta(days=12)).isoformat()
        
        sc_data = {
            "booking_id": booking_id,
            "partner_id": partner_id,
            "vehicle_label": "Test Unit E16",
            "start_datetime": start,
            "end_datetime": end,
            "cost": 2500000,
            "note": "Test sub-charter"
        }
        
        resp = self.post("/subcharters", "owner@demo.local", sc_data)
        self.test(
            "POST /api/subcharters creates sub-charter",
            resp.status_code == 200,
            f"Expected 200, got {resp.status_code}: {resp.text if resp.status_code != 200 else ''}"
        )
        
        if resp.status_code != 200:
            return
        
        sc = resp.json()
        sc_id = sc.get("id")
        self.test_data["test_sc_id"] = sc_id
        
        self.test(
            "Created sub-charter has status 'requested'",
            sc.get("status") == "requested",
            f"Expected 'requested', got {sc.get('status')}"
        )
        self.test(
            "Created sub-charter has code",
            "code" in sc and sc["code"].startswith("SC-"),
            f"Missing or invalid code: {sc.get('code')}"
        )
        self.test(
            "Created sub-charter has expense_id None",
            sc.get("expense_id") is None,
            f"Expected None, got {sc.get('expense_id')}"
        )
        
        # Confirm sub-charter
        resp = self.post(f"/subcharters/{sc_id}/confirm", "owner@demo.local")
        self.test(
            f"POST /api/subcharters/{sc_id}/confirm returns 200",
            resp.status_code == 200,
            f"Expected 200, got {resp.status_code}: {resp.text if resp.status_code != 200 else ''}"
        )
        
        if resp.status_code == 200:
            confirmed = resp.json()
            self.test(
                "Confirmed sub-charter has status 'confirmed'",
                confirmed.get("status") == "confirmed",
                f"Expected 'confirmed', got {confirmed.get('status')}"
            )
            self.test(
                "Confirmed sub-charter has expense_id",
                confirmed.get("expense_id") is not None and confirmed.get("expense_id") != "",
                f"Missing expense_id: {confirmed.get('expense_id')}"
            )
            self.test(
                "Confirmed sub-charter has confirmed_at",
                confirmed.get("confirmed_at") is not None,
                "Missing confirmed_at"
            )
            
            expense_id = confirmed.get("expense_id")
            self.test_data["test_expense_id"] = expense_id
            
            # Verify COGS expense was created
            if expense_id:
                resp = self.get(f"/expenses?booking_id={booking_id}", "owner@demo.local")
                if resp.status_code == 200:
                    expenses = resp.json()
                    cogs_expense = next((e for e in expenses if e.get("id") == expense_id), None)
                    self.test(
                        "COGS expense exists in expenses",
                        cogs_expense is not None,
                        f"Expense {expense_id} not found"
                    )
                    if cogs_expense:
                        self.test(
                            "COGS expense has category 'sewa_mitra'",
                            cogs_expense.get("category") == "sewa_mitra",
                            f"Expected 'sewa_mitra', got {cogs_expense.get('category')}"
                        )
                        self.test(
                            "COGS expense amount matches sub-charter cost",
                            cogs_expense.get("amount") == 2500000,
                            f"Expected 2500000, got {cogs_expense.get('amount')}"
                        )
                        self.test(
                            "COGS expense linked to booking",
                            cogs_expense.get("booking_id") == booking_id,
                            f"Expected {booking_id}, got {cogs_expense.get('booking_id')}"
                        )
        
        # Settle sub-charter
        resp = self.post(f"/subcharters/{sc_id}/settle", "owner@demo.local")
        self.test(
            f"POST /api/subcharters/{sc_id}/settle returns 200",
            resp.status_code == 200,
            f"Expected 200, got {resp.status_code}: {resp.text if resp.status_code != 200 else ''}"
        )
        
        if resp.status_code == 200:
            settled = resp.json()
            self.test(
                "Settled sub-charter has status 'settled'",
                settled.get("status") == "settled",
                f"Expected 'settled', got {settled.get('status')}"
            )
            self.test(
                "Settled sub-charter has settled_at",
                settled.get("settled_at") is not None,
                "Missing settled_at"
            )
            
            # Verify settlement was created
            resp = self.get(f"/partners/{partner_id}/settlements", "owner@demo.local")
            if resp.status_code == 200:
                settlements = resp.json()
                sc_settlement = next((s for s in settlements if s.get("subcharter_id") == sc_id), None)
                self.test(
                    "Settlement created for sub-charter",
                    sc_settlement is not None,
                    f"Settlement for {sc_id} not found"
                )
                if sc_settlement:
                    self.test(
                        "Settlement amount matches sub-charter cost",
                        sc_settlement.get("amount") == 2500000,
                        f"Expected 2500000, got {sc_settlement.get('amount')}"
                    )

    def test_cancel_subcharter(self):
        """Test cancelling sub-charter removes COGS"""
        self.log("\n=== Testing Sub-charter Cancellation ===")
        
        # Get a booking and partner
        resp = self.get("/bookings?limit=10", "owner@demo.local")
        if resp.status_code != 200 or not resp.json():
            self.log("No bookings available", "WARN")
            return
        
        bookings = resp.json()
        booking = bookings[0]
        booking_id = booking.get("id")
        
        resp = self.get("/partners", "owner@demo.local")
        if resp.status_code != 200 or not resp.json():
            self.log("No partners available", "WARN")
            return
        
        partners = resp.json()
        partner_id = partners[0].get("id")
        
        # Create and confirm a sub-charter
        start = (datetime.now() + timedelta(days=20)).isoformat()
        end = (datetime.now() + timedelta(days=22)).isoformat()
        
        sc_data = {
            "booking_id": booking_id,
            "partner_id": partner_id,
            "vehicle_label": "Cancel Test Unit",
            "start_datetime": start,
            "end_datetime": end,
            "cost": 1800000,
            "note": "Test cancel"
        }
        
        resp = self.post("/subcharters", "owner@demo.local", sc_data)
        if resp.status_code != 200:
            self.log("Failed to create sub-charter for cancel test", "WARN")
            return
        
        sc = resp.json()
        sc_id = sc.get("id")
        
        # Confirm it
        resp = self.post(f"/subcharters/{sc_id}/confirm", "owner@demo.local")
        if resp.status_code != 200:
            self.log("Failed to confirm sub-charter for cancel test", "WARN")
            return
        
        confirmed = resp.json()
        expense_id = confirmed.get("expense_id")
        
        # Cancel it
        resp = self.post(f"/subcharters/{sc_id}/cancel", "owner@demo.local")
        self.test(
            f"POST /api/subcharters/{sc_id}/cancel returns 200",
            resp.status_code == 200,
            f"Expected 200, got {resp.status_code}"
        )
        
        if resp.status_code == 200:
            cancelled = resp.json()
            self.test(
                "Cancelled sub-charter has status 'cancelled'",
                cancelled.get("status") == "cancelled",
                f"Expected 'cancelled', got {cancelled.get('status')}"
            )
            self.test(
                "Cancelled sub-charter has expense_id None",
                cancelled.get("expense_id") is None,
                f"Expected None, got {cancelled.get('expense_id')}"
            )
            
            # Verify COGS expense was deleted
            if expense_id:
                resp = self.get(f"/expenses?booking_id={booking_id}", "owner@demo.local")
                if resp.status_code == 200:
                    expenses = resp.json()
                    deleted_expense = next((e for e in expenses if e.get("id") == expense_id), None)
                    self.test(
                        "COGS expense deleted after cancel",
                        deleted_expense is None,
                        f"Expense {expense_id} still exists"
                    )
        
        # Test: Cannot cancel settled sub-charter
        # Create another one and settle it
        start2 = (datetime.now() + timedelta(days=30)).isoformat()
        end2 = (datetime.now() + timedelta(days=32)).isoformat()
        
        sc_data2 = {
            "booking_id": booking_id,
            "partner_id": partner_id,
            "vehicle_label": "Settled Test",
            "start_datetime": start2,
            "end_datetime": end2,
            "cost": 2000000,
            "note": "Test settled cancel"
        }
        
        resp = self.post("/subcharters", "owner@demo.local", sc_data2)
        if resp.status_code == 200:
            sc2 = resp.json()
            sc2_id = sc2.get("id")
            
            # Confirm and settle
            self.post(f"/subcharters/{sc2_id}/confirm", "owner@demo.local")
            self.post(f"/subcharters/{sc2_id}/settle", "owner@demo.local")
            
            # Try to cancel
            resp = self.post(f"/subcharters/{sc2_id}/cancel", "owner@demo.local")
            self.test(
                "Cannot cancel settled sub-charter (400)",
                resp.status_code == 400,
                f"Expected 400, got {resp.status_code}"
            )

    def test_ap_calculations(self):
        """Test AP (Accounts Payable) accuracy"""
        self.log("\n=== Testing AP Calculations ===")
        
        # Get seed partner with confirmed sub-charter
        resp = self.get("/partners", "owner@demo.local")
        if resp.status_code != 200 or not resp.json():
            self.log("No partners available", "WARN")
            return
        
        partners = resp.json()
        
        # Find partner with sub-charters
        partner_with_sc = None
        for p in partners:
            if p.get("subcharter_count", 0) > 0:
                partner_with_sc = p
                break
        
        if not partner_with_sc:
            self.log("No partner with sub-charters found", "WARN")
            return
        
        partner_id = partner_with_sc.get("id")
        
        # Get partner detail
        resp = self.get(f"/partners/{partner_id}", "owner@demo.local")
        if resp.status_code != 200:
            self.log("Failed to get partner detail", "WARN")
            return
        
        detail = resp.json()
        subcharters = detail.get("subcharters", [])
        settlements = detail.get("settlements", [])
        
        # Calculate expected AP
        expected_total = sum(
            sc.get("cost", 0) for sc in subcharters 
            if sc.get("status") in ["confirmed", "settled"]
        )
        expected_paid = sum(s.get("amount", 0) for s in settlements)
        expected_outstanding = expected_total - expected_paid
        
        actual_total = detail.get("ap_total", 0)
        actual_paid = detail.get("ap_paid", 0)
        actual_outstanding = detail.get("ap_outstanding", 0)
        
        self.test(
            "AP total matches sum of confirmed/settled sub-charter costs",
            abs(actual_total - expected_total) < 0.01,
            f"Expected {expected_total}, got {actual_total}"
        )
        self.test(
            "AP paid matches sum of settlements",
            abs(actual_paid - expected_paid) < 0.01,
            f"Expected {expected_paid}, got {actual_paid}"
        )
        self.test(
            "AP outstanding = total - paid",
            abs(actual_outstanding - expected_outstanding) < 0.01,
            f"Expected {expected_outstanding}, got {actual_outstanding}"
        )
        
        # Test manual settlement
        if actual_outstanding > 0:
            settlement_amount = min(500000, actual_outstanding)
            settlement_data = {
                "amount": settlement_amount,
                "method": "transfer",
                "note": "Test manual settlement"
            }
            
            resp = self.post(f"/partners/{partner_id}/settlements", "owner@demo.local", settlement_data)
            self.test(
                "POST /api/partners/{id}/settlements creates settlement",
                resp.status_code == 200,
                f"Expected 200, got {resp.status_code}"
            )
            
            if resp.status_code == 200:
                result = resp.json()
                new_ap = result.get("ap", {})
                new_outstanding = new_ap.get("ap_outstanding", 0)
                
                self.test(
                    "Manual settlement reduces AP outstanding",
                    abs(new_outstanding - (actual_outstanding - settlement_amount)) < 0.01,
                    f"Expected {actual_outstanding - settlement_amount}, got {new_outstanding}"
                )

    def test_whatsapp_notifications(self):
        """Test WhatsApp notifications (MOCKED)"""
        self.log("\n=== Testing WhatsApp Notifications (MOCKED) ===")
        
        # Get automation runs
        resp = self.get("/automation/runs?limit=50", "owner@demo.local")
        self.test(
            "GET /api/automation/runs returns 200",
            resp.status_code == 200,
            f"Expected 200, got {resp.status_code}"
        )
        
        if resp.status_code != 200:
            return
        
        runs = resp.json()
        
        # Check for subcharter.requested events
        requested_runs = [r for r in runs if r.get("event_type") == "subcharter.requested"]
        self.test(
            "Found subcharter.requested automation runs",
            len(requested_runs) > 0,
            f"Expected > 0, got {len(requested_runs)}"
        )
        
        if len(requested_runs) > 0:
            run = requested_runs[0]
            self.test(
                "subcharter.requested run has status 'success'",
                run.get("status") == "success",
                f"Expected 'success', got {run.get('status')}"
            )
            
            actions = run.get("actions", [])
            wa_action = next((a for a in actions if a.get("type") == "send_wa"), None)
            self.test(
                "subcharter.requested has send_wa action",
                wa_action is not None,
                "No send_wa action found"
            )
            
            if wa_action:
                self.test(
                    "send_wa action has status 'success'",
                    wa_action.get("status") == "success",
                    f"Expected 'success', got {wa_action.get('status')}"
                )
        
        # Check for subcharter.confirmed events
        confirmed_runs = [r for r in runs if r.get("event_type") == "subcharter.confirmed"]
        self.test(
            "Found subcharter.confirmed automation runs",
            len(confirmed_runs) > 0,
            f"Expected > 0, got {len(confirmed_runs)}"
        )

    def test_anti_overlap(self):
        """Test anti-overlap validation for partner vehicles"""
        self.log("\n=== Testing Anti-overlap Validation ===")
        
        # Get a partner vehicle
        resp = self.get("/vehicles?ownership=partner&limit=10", "owner@demo.local")
        if resp.status_code != 200 or not resp.json():
            self.log("No partner vehicles available", "WARN")
            return
        
        vehicles = resp.json()
        if len(vehicles) == 0:
            self.log("No partner vehicles found", "WARN")
            return
        
        vehicle = vehicles[0]
        vehicle_id = vehicle.get("id")
        partner_id = vehicle.get("partner_id")
        
        # Get a booking
        resp = self.get("/bookings?limit=10", "owner@demo.local")
        if resp.status_code != 200 or not resp.json():
            self.log("No bookings available", "WARN")
            return
        
        booking_id = resp.json()[0].get("id")
        
        # Create first sub-charter
        start1 = (datetime.now() + timedelta(days=40)).isoformat()
        end1 = (datetime.now() + timedelta(days=42)).isoformat()
        
        sc_data1 = {
            "booking_id": booking_id,
            "partner_id": partner_id,
            "vehicle_id": vehicle_id,
            "start_datetime": start1,
            "end_datetime": end1,
            "cost": 2000000,
            "note": "First overlap test"
        }
        
        resp = self.post("/subcharters", "owner@demo.local", sc_data1)
        if resp.status_code != 200:
            self.log("Failed to create first sub-charter", "WARN")
            return
        
        sc1 = resp.json()
        sc1_id = sc1.get("id")
        
        # Try to create overlapping sub-charter (should fail)
        start2 = (datetime.now() + timedelta(days=41)).isoformat()
        end2 = (datetime.now() + timedelta(days=43)).isoformat()
        
        sc_data2 = {
            "booking_id": booking_id,
            "partner_id": partner_id,
            "vehicle_id": vehicle_id,
            "start_datetime": start2,
            "end_datetime": end2,
            "cost": 2000000,
            "note": "Overlapping test"
        }
        
        resp = self.post("/subcharters", "owner@demo.local", sc_data2)
        self.test(
            "Cannot create overlapping sub-charter (400)",
            resp.status_code == 400,
            f"Expected 400, got {resp.status_code}"
        )
        
        if resp.status_code == 400:
            error = resp.json()
            self.test(
                "Error message mentions conflict",
                "bentrok" in error.get("detail", "").lower() or "conflict" in error.get("detail", "").lower(),
                f"Error message: {error.get('detail')}"
            )
        
        # Clean up
        self.post(f"/subcharters/{sc1_id}/cancel", "owner@demo.local")

    def test_available_partners(self):
        """Test available-partners endpoint"""
        self.log("\n=== Testing Available Partners Endpoint ===")
        
        start = (datetime.now() + timedelta(days=50)).isoformat()
        end = (datetime.now() + timedelta(days=52)).isoformat()
        
        resp = self.get("/subcharters/available-partners", "owner@demo.local", {
            "start": start,
            "end": end
        })
        
        self.test(
            "GET /api/subcharters/available-partners returns 200",
            resp.status_code == 200,
            f"Expected 200, got {resp.status_code}"
        )
        
        if resp.status_code == 200:
            available = resp.json()
            self.test(
                "Available partners is array",
                isinstance(available, list),
                f"Expected list, got {type(available)}"
            )
            
            if len(available) > 0:
                vehicle = available[0]
                self.test(
                    "Available vehicle has partner_name",
                    "partner_name" in vehicle,
                    "Missing partner_name field"
                )
                self.test(
                    "Available vehicle has partner_phone",
                    "partner_phone" in vehicle,
                    "Missing partner_phone field"
                )

    def test_delete_partner_validation(self):
        """Test partner deletion validation"""
        self.log("\n=== Testing Partner Deletion Validation ===")
        
        # Create a partner
        partner_data = {
            "name": "Delete Test Partner",
            "phone": "081299999999",
            "status": "active"
        }
        
        resp = self.post("/partners", "owner@demo.local", partner_data)
        if resp.status_code != 200:
            self.log("Failed to create test partner", "WARN")
            return
        
        partner = resp.json()
        partner_id = partner.get("id")
        
        # Create a sub-charter for this partner
        resp = self.get("/bookings?limit=10", "owner@demo.local")
        if resp.status_code != 200 or not resp.json():
            self.log("No bookings available", "WARN")
            return
        
        booking_id = resp.json()[0].get("id")
        
        start = (datetime.now() + timedelta(days=60)).isoformat()
        end = (datetime.now() + timedelta(days=62)).isoformat()
        
        sc_data = {
            "booking_id": booking_id,
            "partner_id": partner_id,
            "vehicle_label": "Delete test unit",
            "start_datetime": start,
            "end_datetime": end,
            "cost": 2000000,
            "note": "Delete test"
        }
        
        resp = self.post("/subcharters", "owner@demo.local", sc_data)
        if resp.status_code != 200:
            self.log("Failed to create sub-charter", "WARN")
            return
        
        # Try to delete partner (should fail)
        resp = self.delete(f"/partners/{partner_id}", "owner@demo.local")
        self.test(
            "Cannot delete partner with active sub-charter (400)",
            resp.status_code == 400,
            f"Expected 400, got {resp.status_code}"
        )
        
        if resp.status_code == 400:
            error = resp.json()
            self.test(
                "Error message mentions active sub-charter",
                "sub-charter" in error.get("detail", "").lower(),
                f"Error message: {error.get('detail')}"
            )

    def test_regression(self):
        """Light regression: check other endpoints still work"""
        self.log("\n=== Light Regression Testing ===")
        
        endpoints = [
            "/dashboard",
            "/vehicles",
            "/drivers",
            "/customers",
            "/bookings",
            "/trips"
        ]
        
        for endpoint in endpoints:
            resp = self.get(endpoint, "owner@demo.local")
            self.test(
                f"GET {endpoint} returns 200",
                resp.status_code == 200,
                f"Expected 200, got {resp.status_code}"
            )

    def run_all_tests(self):
        """Run all E16 tests"""
        self.log("=" * 60)
        self.log("E16 BACKEND TESTING: Pinjam Armada / Sub-charter")
        self.log("=" * 60)
        
        # Login
        self.login("owner@demo.local", "demo12345")
        self.login("ops@demo.local", "demo12345")
        self.login("driver@demo.local", "demo12345")
        
        if not self.tokens.get("owner@demo.local"):
            self.log("Failed to login as owner, aborting tests", "FAIL")
            return 1
        
        # Run tests
        self.test_rbac()
        self.test_partner_crud()
        self.test_subcharter_lifecycle()
        self.test_cancel_subcharter()
        self.test_ap_calculations()
        self.test_whatsapp_notifications()
        self.test_anti_overlap()
        self.test_available_partners()
        self.test_delete_partner_validation()
        self.test_regression()
        
        # Summary
        self.log("\n" + "=" * 60)
        self.log(f"TESTS RUN: {self.tests_run}")
        self.log(f"TESTS PASSED: {self.tests_passed}", "PASS")
        self.log(f"TESTS FAILED: {self.tests_failed}", "FAIL" if self.tests_failed > 0 else "INFO")
        self.log("=" * 60)
        
        if self.errors:
            self.log("\nFailed Tests:")
            for error in self.errors:
                self.log(f"  - {error}", "FAIL")
        
        return 0 if self.tests_failed == 0 else 1


if __name__ == "__main__":
    runner = E16TestRunner()
    sys.exit(runner.run_all_tests())

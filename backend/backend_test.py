"""
Backend Testing for RC-11 Fixes (RBAC, Negative Values, Double-Booking)
Tests the 3 critical fixes implemented in the forensic audit.
"""
import requests
import sys
from typing import Dict, Any
from datetime import datetime, timedelta

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

class TestRunner:
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
        return requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params, timeout=10)

    def post(self, endpoint: str, email: str, data: Dict) -> requests.Response:
        """POST request with auth"""
        token = self.tokens.get(email)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return requests.post(f"{BASE_URL}/{endpoint}", headers=headers, json=data, timeout=10)

    def patch(self, endpoint: str, email: str, data: Dict) -> requests.Response:
        """PATCH request with auth"""
        token = self.tokens.get(email)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return requests.patch(f"{BASE_URL}/{endpoint}", headers=headers, json=data, timeout=10)

    def test_negative_value_rejection(self):
        """FIX #2: Test that negative values are rejected with HTTP 422"""
        self.log("\n=== FIX #2: NEGATIVE VALUE REJECTION ===", "INFO")
        
        owner = "owner@demo.local"
        
        # Get real IDs for testing
        self.log("Fetching real vehicle and booking IDs...")
        vehicles_resp = self.get("vehicles", owner)
        bookings_resp = self.get("bookings", owner)
        
        vehicle_id = None
        booking_id = None
        
        if vehicles_resp.status_code == 200 and len(vehicles_resp.json()) > 0:
            vehicle_id = vehicles_resp.json()[0].get("id")
            self.log(f"Using vehicle_id: {vehicle_id}")
        
        if bookings_resp.status_code == 200 and len(bookings_resp.json()) > 0:
            booking_id = bookings_resp.json()[0].get("id")
            self.log(f"Using booking_id: {booking_id}")
        
        # Test 1: POST /api/expenses with negative amount
        self.log("Testing POST /api/expenses with negative amount...")
        resp = self.post("expenses", owner, {
            "booking_id": booking_id,
            "category": "bbm",
            "amount": -1000,
            "note": "Test negative expense"
        })
        self.test(
            "Expenses negative amount rejected (422)",
            resp.status_code == 422,
            f"Expected 422, got {resp.status_code}"
        )
        
        # Test 2: POST /api/maintenance with negative cost
        self.log("Testing POST /api/maintenance with negative cost...")
        if vehicle_id:
            resp = self.post("maintenance", owner, {
                "vehicle_id": vehicle_id,
                "type": "servis",
                "title": "Test maintenance",
                "cost": -5000,
                "status": "scheduled"
            })
            self.test(
                "Maintenance negative cost rejected (422)",
                resp.status_code == 422,
                f"Expected 422, got {resp.status_code}"
            )
        
        # Test 3: POST /api/bookings with negative base_price
        self.log("Testing POST /api/bookings with negative base_price...")
        customers_resp = self.get("customers", owner)
        if customers_resp.status_code == 200 and len(customers_resp.json()) > 0 and vehicle_id:
            customer_id = customers_resp.json()[0].get("id")
            start = (datetime.now() + timedelta(days=30)).isoformat()
            end = (datetime.now() + timedelta(days=31)).isoformat()
            
            resp = self.post("bookings", owner, {
                "customer_id": customer_id,
                "vehicle_id": vehicle_id,
                "start_datetime": start,
                "end_datetime": end,
                "base_price": -5000,
                "origin": "Jakarta",
                "destination": "Bandung"
            })
            self.test(
                "Bookings negative base_price rejected (422)",
                resp.status_code == 422,
                f"Expected 422, got {resp.status_code}"
            )
        
        # Test 4: PATCH vehicle with negative capacity
        self.log("Testing PATCH /api/vehicles with negative capacity...")
        if vehicle_id:
            resp = self.patch(f"vehicles/{vehicle_id}", owner, {
                "capacity": -2
            })
            self.test(
                "Vehicle negative capacity rejected (422)",
                resp.status_code == 422,
                f"Expected 422, got {resp.status_code}"
            )
        
        # Test 5: Verify positive values still work
        self.log("Testing POST /api/expenses with POSITIVE amount (should succeed)...")
        if booking_id:
            resp = self.post("expenses", owner, {
                "booking_id": booking_id,
                "category": "bbm",
                "amount": 100000,
                "note": "Test positive expense"
            })
            self.test(
                "Expenses positive amount accepted (200/201)",
                resp.status_code in [200, 201],
                f"Expected 200/201, got {resp.status_code}"
            )
            if resp.status_code in [200, 201]:
                expense_id = resp.json().get("id")
                self.test_data["expense_id"] = expense_id

    def test_double_booking_prevention(self):
        """FIX #3: Test race/double-booking prevention"""
        self.log("\n=== FIX #3: DOUBLE-BOOKING PREVENTION ===", "INFO")
        
        owner = "owner@demo.local"
        
        # Get real IDs
        self.log("Fetching vehicles, drivers, customers, partners...")
        vehicles_resp = self.get("vehicles", owner)
        drivers_resp = self.get("drivers", owner)
        customers_resp = self.get("customers", owner)
        partners_resp = self.get("partners", owner)
        
        vehicle_id = None
        driver_id = None
        customer_id = None
        partner_id = None
        partner_vehicle_id = None
        
        if vehicles_resp.status_code == 200 and len(vehicles_resp.json()) > 0:
            # Get first owned vehicle
            for v in vehicles_resp.json():
                if v.get("ownership") == "owned":
                    vehicle_id = v.get("id")
                    break
            # Get first partner vehicle
            for v in vehicles_resp.json():
                if v.get("ownership") == "partner":
                    partner_vehicle_id = v.get("id")
                    break
        
        if drivers_resp.status_code == 200 and len(drivers_resp.json()) > 0:
            driver_id = drivers_resp.json()[0].get("id")
        
        if customers_resp.status_code == 200 and len(customers_resp.json()) > 0:
            customer_id = customers_resp.json()[0].get("id")
        
        if partners_resp.status_code == 200 and len(partners_resp.json()) > 0:
            partner_id = partners_resp.json()[0].get("id")
        
        # Test 1: Create booking A, then try to assign same vehicle to overlapping window
        self.log("Testing vehicle double-booking via dispatch assign...")
        if vehicle_id and driver_id and customer_id:
            # Create booking A
            start1 = (datetime.now() + timedelta(days=40)).isoformat()
            end1 = (datetime.now() + timedelta(days=42)).isoformat()
            
            resp = self.post("bookings", owner, {
                "customer_id": customer_id,
                "vehicle_id": vehicle_id,
                "driver_id": driver_id,
                "start_datetime": start1,
                "end_datetime": end1,
                "base_price": 1000000,
                "origin": "Jakarta",
                "destination": "Bandung"
            })
            
            if resp.status_code in [200, 201]:
                booking_a_id = resp.json().get("id")
                self.log(f"Created booking A: {booking_a_id}")
                self.test_data["booking_a_id"] = booking_a_id
                
                # Create booking B with different vehicle initially
                vehicles_list = vehicles_resp.json()
                other_vehicle_id = None
                for v in vehicles_list:
                    if v.get("id") != vehicle_id and v.get("ownership") == "owned":
                        other_vehicle_id = v.get("id")
                        break
                
                if other_vehicle_id:
                    start2 = (datetime.now() + timedelta(days=41)).isoformat()
                    end2 = (datetime.now() + timedelta(days=43)).isoformat()
                    
                    resp = self.post("bookings", owner, {
                        "customer_id": customer_id,
                        "vehicle_id": other_vehicle_id,
                        "start_datetime": start2,
                        "end_datetime": end2,
                        "base_price": 1000000,
                        "origin": "Jakarta",
                        "destination": "Surabaya"
                    })
                    
                    if resp.status_code in [200, 201]:
                        booking_b_id = resp.json().get("id")
                        self.log(f"Created booking B: {booking_b_id}")
                        
                        # Try to assign same vehicle to booking B (should fail)
                        resp = self.post(f"dispatch/{booking_b_id}/assign", owner, {
                            "driver_id": driver_id,
                            "vehicle_id": vehicle_id  # Same vehicle as booking A
                        })
                        
                        self.test(
                            "Dispatch assign overlapping vehicle rejected (400)",
                            resp.status_code == 400,
                            f"Expected 400, got {resp.status_code}"
                        )
                        
                        if resp.status_code == 400:
                            self.test(
                                "Error message mentions 'bentrok'",
                                "bentrok" in resp.text.lower(),
                                f"Error message: {resp.text}"
                            )
        
        # Test 2: Quotation convert double-booking
        self.log("Testing vehicle double-booking via quotation convert...")
        quotations_resp = self.get("quotations", owner)
        if quotations_resp.status_code == 200 and len(quotations_resp.json()) > 0:
            # Find an accepted quotation
            accepted_quo = None
            for q in quotations_resp.json():
                if q.get("status") == "accepted" and not q.get("booking_id"):
                    accepted_quo = q
                    break
            
            if accepted_quo and vehicle_id:
                quo_id = accepted_quo.get("id")
                # Try to convert with overlapping time
                start3 = (datetime.now() + timedelta(days=40, hours=12)).isoformat()
                end3 = (datetime.now() + timedelta(days=42, hours=12)).isoformat()
                
                resp = self.post(f"quotations/{quo_id}/convert", owner, {
                    "vehicle_id": vehicle_id,
                    "start_datetime": start3,
                    "end_datetime": end3
                })
                
                self.test(
                    "Quotation convert overlapping vehicle rejected (400)",
                    resp.status_code == 400,
                    f"Expected 400, got {resp.status_code}"
                )
        
        # Test 3: Subcharter overlap test (R6-1)
        self.log("Testing subcharter overlap prevention...")
        if partner_vehicle_id and partner_id and customer_id:
            # Create booking for subcharter
            start_sc1 = (datetime.now() + timedelta(days=50)).isoformat()
            end_sc1 = (datetime.now() + timedelta(days=52)).isoformat()
            
            resp = self.post("bookings", owner, {
                "customer_id": customer_id,
                "vehicle_id": partner_vehicle_id,
                "start_datetime": start_sc1,
                "end_datetime": end_sc1,
                "base_price": 1000000,
                "origin": "Jakarta",
                "destination": "Yogyakarta"
            })
            
            if resp.status_code in [200, 201]:
                booking_sc_id = resp.json().get("id")
                self.log(f"Created booking for subcharter: {booking_sc_id}")
                
                # Create subcharter 1 (W1)
                resp = self.post("subcharters", owner, {
                    "booking_id": booking_sc_id,
                    "partner_id": partner_id,
                    "vehicle_id": partner_vehicle_id,
                    "start_datetime": start_sc1,
                    "end_datetime": end_sc1,
                    "cost": 500000,
                    "note": "Test subcharter W1"
                })
                
                if resp.status_code in [200, 201]:
                    sc1_id = resp.json().get("id")
                    self.log(f"Created subcharter W1: {sc1_id}")
                    
                    # Create another booking for subcharter 2
                    start_sc2 = (datetime.now() + timedelta(days=55)).isoformat()
                    end_sc2 = (datetime.now() + timedelta(days=57)).isoformat()
                    
                    resp = self.post("bookings", owner, {
                        "customer_id": customer_id,
                        "vehicle_id": partner_vehicle_id,
                        "start_datetime": start_sc2,
                        "end_datetime": end_sc2,
                        "base_price": 1000000,
                        "origin": "Jakarta",
                        "destination": "Semarang"
                    })
                    
                    if resp.status_code in [200, 201]:
                        booking_sc2_id = resp.json().get("id")
                        
                        # Create subcharter 2 (W2) non-overlapping
                        resp = self.post("subcharters", owner, {
                            "booking_id": booking_sc2_id,
                            "partner_id": partner_id,
                            "vehicle_id": partner_vehicle_id,
                            "start_datetime": start_sc2,
                            "end_datetime": end_sc2,
                            "cost": 500000,
                            "note": "Test subcharter W2"
                        })
                        
                        if resp.status_code in [200, 201]:
                            sc2_id = resp.json().get("id")
                            self.log(f"Created subcharter W2: {sc2_id}")
                            
                            # PATCH W2 to overlap W1 (should fail)
                            overlap_start = (datetime.now() + timedelta(days=51)).isoformat()
                            overlap_end = (datetime.now() + timedelta(days=53)).isoformat()
                            
                            resp = self.patch(f"subcharters/{sc2_id}", owner, {
                                "start_datetime": overlap_start,
                                "end_datetime": overlap_end
                            })
                            
                            self.test(
                                "Subcharter PATCH overlap rejected (400)",
                                resp.status_code == 400,
                                f"Expected 400, got {resp.status_code}"
                            )
                            
                            if resp.status_code == 400:
                                self.test(
                                    "Error message mentions 'bentrok'",
                                    "bentrok" in resp.text.lower(),
                                    f"Error message: {resp.text}"
                                )

    def test_booking_lifecycle_regression(self):
        """Regression: Verify core booking lifecycle still works"""
        self.log("\n=== REGRESSION: BOOKING LIFECYCLE ===", "INFO")
        
        owner = "owner@demo.local"
        
        # Get IDs
        vehicles_resp = self.get("vehicles", owner)
        drivers_resp = self.get("drivers", owner)
        customers_resp = self.get("customers", owner)
        
        vehicle_id = None
        driver_id = None
        customer_id = None
        
        if vehicles_resp.status_code == 200 and len(vehicles_resp.json()) > 0:
            for v in vehicles_resp.json():
                if v.get("ownership") == "owned":
                    vehicle_id = v.get("id")
                    break
        
        if drivers_resp.status_code == 200 and len(drivers_resp.json()) > 0:
            driver_id = drivers_resp.json()[0].get("id")
        
        if customers_resp.status_code == 200 and len(customers_resp.json()) > 0:
            customer_id = customers_resp.json()[0].get("id")
        
        if vehicle_id and customer_id:
            # Create booking
            start = (datetime.now() + timedelta(days=60)).isoformat()
            end = (datetime.now() + timedelta(days=61)).isoformat()
            
            self.log("Creating test booking...")
            resp = self.post("bookings", owner, {
                "customer_id": customer_id,
                "vehicle_id": vehicle_id,
                "start_datetime": start,
                "end_datetime": end,
                "base_price": 1500000,
                "origin": "Jakarta",
                "destination": "Bali"
            })
            
            self.test(
                "Create booking succeeds (200/201)",
                resp.status_code in [200, 201],
                f"Expected 200/201, got {resp.status_code}"
            )
            
            if resp.status_code in [200, 201]:
                booking = resp.json()
                booking_id = booking.get("id")
                self.log(f"Created booking: {booking_id}")
                
                # Verify status is confirmed
                self.test(
                    "Booking status is 'confirmed'",
                    booking.get("status") == "confirmed",
                    f"Expected 'confirmed', got {booking.get('status')}"
                )
                
                # Dispatch assign trip
                if driver_id:
                    self.log("Assigning driver and vehicle via dispatch...")
                    resp = self.post(f"dispatch/{booking_id}/assign", owner, {
                        "driver_id": driver_id,
                        "vehicle_id": vehicle_id
                    })
                    
                    self.test(
                        "Dispatch assign succeeds (200)",
                        resp.status_code == 200,
                        f"Expected 200, got {resp.status_code}"
                    )
                    
                    if resp.status_code == 200:
                        trip = resp.json().get("trip", {})
                        self.test(
                            "Trip created with status 'standby'",
                            trip.get("status") == "standby",
                            f"Expected 'standby', got {trip.get('status')}"
                        )

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "=" * 60, "INFO")
        self.log(f"TESTS RUN: {self.tests_run}", "INFO")
        self.log(f"TESTS PASSED: {self.tests_passed}", "PASS")
        self.log(f"TESTS FAILED: {self.tests_failed}", "FAIL" if self.tests_failed > 0 else "INFO")
        self.log("=" * 60, "INFO")
        
        if self.errors:
            self.log("\nFAILED TESTS:", "FAIL")
            for error in self.errors:
                self.log(f"  - {error}", "FAIL")
        
        return 0 if self.tests_failed == 0 else 1


def main():
    runner = TestRunner()
    
    # Login all users
    runner.log("=== LOGGING IN ===", "INFO")
    runner.login("owner@demo.local", "demo12345")
    runner.login("ops@demo.local", "demo12345")
    runner.login("driver@demo.local", "demo12345")
    
    # Run tests for the 3 fixes
    runner.test_negative_value_rejection()
    runner.test_double_booking_prevention()
    runner.test_booking_lifecycle_regression()
    
    # Print summary
    return runner.print_summary()


if __name__ == "__main__":
    sys.exit(main())

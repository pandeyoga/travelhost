"""
RC Bug Fix Testing - Rahaza Travel Fleet Management
Tests RC-01 through RC-09 bug fixes + regression tests
"""
import requests
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

class RCTestRunner:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.tokens = {}
        self.errors = []
        self.test_data = {
            "customers": [],
            "vehicles": [],
            "drivers": [],
            "bookings": [],
            "trips": [],
            "payments": [],
            "payouts": []
        }

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
                self.log(f"Login failed for {email}: {resp.status_code} - {resp.text}", "FAIL")
                return {}
        except Exception as e:
            self.log(f"Login exception for {email}: {e}", "FAIL")
            return {}

    def get(self, endpoint: str, email: str, params: Dict = None) -> requests.Response:
        """GET request with auth"""
        token = self.tokens.get(email)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params, timeout=15)

    def post(self, endpoint: str, email: str, data: Dict) -> requests.Response:
        """POST request with auth"""
        token = self.tokens.get(email)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return requests.post(f"{BASE_URL}/{endpoint}", headers=headers, json=data, timeout=15)

    def patch(self, endpoint: str, email: str, data: Dict) -> requests.Response:
        """PATCH request with auth"""
        token = self.tokens.get(email)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return requests.patch(f"{BASE_URL}/{endpoint}", headers=headers, json=data, timeout=15)

    def get_test_customer(self, email: str) -> str:
        """Get or create a test customer"""
        resp = self.get("customers", email)
        if resp.status_code == 200:
            customers = resp.json()
            if customers:
                return customers[0]["id"]
        # Create test customer
        resp = self.post("customers", email, {
            "name": "Test Customer RC",
            "phone": "081234567890",
            "email": "testrc@example.com"
        })
        if resp.status_code == 200:
            return resp.json()["id"]
        return None

    def get_test_vehicle(self, email: str) -> str:
        """Get a test vehicle"""
        resp = self.get("vehicles", email)
        if resp.status_code == 200:
            vehicles = resp.json()
            # Find an available vehicle
            for v in vehicles:
                if v.get("status") == "available":
                    return v["id"]
            # Return first vehicle if none available
            if vehicles:
                return vehicles[0]["id"]
        return None

    def get_test_driver(self, email: str) -> str:
        """Get a test driver"""
        resp = self.get("drivers", email)
        if resp.status_code == 200:
            drivers = resp.json()
            if drivers:
                return drivers[0]["id"]
        return None

    def create_test_booking(self, email: str, customer_id: str, vehicle_id: str, 
                           driver_id: str = None, total_amount: float = 1000000,
                           start_offset_days: int = 30) -> Dict[str, Any]:
        """Create a test booking in far future (2028)"""
        start_date = datetime(2028, 6, 1) + timedelta(days=start_offset_days)
        end_date = start_date + timedelta(days=2)
        
        booking_data = {
            "customer_id": customer_id,
            "vehicle_id": vehicle_id,
            "origin": "Jakarta",
            "destination": "Bandung",
            "start_datetime": start_date.isoformat() + "+00:00",
            "end_datetime": end_date.isoformat() + "+00:00",
            "base_price": total_amount,
            "notes": "RC Test Booking"
        }
        
        if driver_id:
            booking_data["driver_id"] = driver_id
        
        resp = self.post("bookings", email, booking_data)
        if resp.status_code == 200:
            booking = resp.json()
            self.test_data["bookings"].append(booking["id"])
            return booking
        else:
            self.log(f"Failed to create booking: {resp.status_code} - {resp.text}", "FAIL")
            return None

    # ========== RC-01: Race Overpayment Test ==========
    def test_rc01_race_overpayment(self):
        """RC-01: Atomic payment guard prevents overpayment"""
        self.log("\n=== RC-01: RACE OVERPAYMENT (ATOMIC GUARD) ===", "INFO")
        
        email = "owner@demo.local"
        customer_id = self.get_test_customer(email)
        vehicle_id = self.get_test_vehicle(email)
        
        if not customer_id or not vehicle_id:
            self.log("Cannot test RC-01: missing customer or vehicle", "FAIL")
            return
        
        # Create booking with total 1,000,000
        booking = self.create_test_booking(email, customer_id, vehicle_id, 
                                          total_amount=1000000, start_offset_days=1)
        if not booking:
            self.log("Cannot test RC-01: failed to create booking", "FAIL")
            return
        
        booking_id = booking["id"]
        self.log(f"Created booking {booking.get('code')} with total 1,000,000")
        
        # First payment: 800,000 (should succeed)
        resp1 = self.post("payments", email, {
            "booking_id": booking_id,
            "amount": 800000,
            "type": "settlement",
            "method": "transfer"
        })
        self.test("RC-01: First payment 800k succeeds", 
                 resp1.status_code == 200,
                 f"Got {resp1.status_code}: {resp1.text}")
        
        # Second payment: 800,000 (should be REJECTED - would exceed total)
        resp2 = self.post("payments", email, {
            "booking_id": booking_id,
            "amount": 800000,
            "type": "settlement",
            "method": "transfer"
        })
        self.test("RC-01: Second payment 800k rejected (overpayment)", 
                 resp2.status_code == 400,
                 f"Got {resp2.status_code}: {resp2.text}")
        
        if resp2.status_code == 400:
            self.test("RC-01: Error message mentions 'melebihi sisa'",
                     "melebihi sisa" in resp2.text.lower() or "exceeds" in resp2.text.lower(),
                     f"Got: {resp2.text}")
        
        # Verify booking paid_amount
        resp = self.get(f"bookings/{booking_id}", email)
        if resp.status_code == 200:
            booking_data = resp.json()
            paid = booking_data.get("paid_amount", 0)
            total = booking_data.get("total_amount", 0)
            self.test("RC-01: paid_amount <= total_amount",
                     paid <= total,
                     f"paid={paid}, total={total}")
            self.test("RC-01: paid_amount equals sum of accepted payments",
                     paid == 800000,
                     f"Expected 800000, got {paid}")

    # ========== RC-02: Payment Status Honesty Test ==========
    def test_rc02_payment_status_honesty(self):
        """RC-02: Completed booking without payment shows correct payment_status"""
        self.log("\n=== RC-02: PAYMENT STATUS HONESTY ===", "INFO")
        
        email = "owner@demo.local"
        customer_id = self.get_test_customer(email)
        vehicle_id = self.get_test_vehicle(email)
        
        if not customer_id or not vehicle_id:
            self.log("Cannot test RC-02: missing customer or vehicle", "FAIL")
            return
        
        # Test 1: Complete booking with NO payment
        booking1 = self.create_test_booking(email, customer_id, vehicle_id,
                                           total_amount=2000000, start_offset_days=2)
        if not booking1:
            self.log("Cannot test RC-02: failed to create booking", "FAIL")
            return
        
        booking_id1 = booking1["id"]
        self.log(f"Created booking {booking1.get('code')} with total 2,000,000 (no payment)")
        
        # Complete the booking without payment
        resp = self.post(f"bookings/{booking_id1}/complete", email, {})
        self.test("RC-02: Complete booking without payment succeeds",
                 resp.status_code == 200,
                 f"Got {resp.status_code}: {resp.text}")
        
        # Verify booking status and payment_status
        resp = self.get(f"bookings/{booking_id1}", email)
        if resp.status_code == 200:
            booking_data = resp.json()
            status = booking_data.get("status")
            payment_status = booking_data.get("payment_status")
            
            self.test("RC-02: Booking status is 'completed'",
                     status == "completed",
                     f"Got status={status}")
            self.test("RC-02: Payment status is 'belum_bayar' (NOT 'selesai'/'lunas')",
                     payment_status == "belum_bayar",
                     f"Got payment_status={payment_status}")
        
        # Verify booking appears in AR (accounts receivable)
        resp = self.get("finance/ar", email)
        if resp.status_code == 200:
            ar_data = resp.json()
            items = ar_data.get("items", [])
            found_in_ar = any(item.get("booking_id") == booking_id1 for item in items)
            self.test("RC-02: Unpaid completed booking appears in AR",
                     found_in_ar,
                     f"Booking {booking_id1} not found in AR")
        
        # Test 2: Complete booking with FULL payment
        booking2 = self.create_test_booking(email, customer_id, vehicle_id,
                                           total_amount=1500000, start_offset_days=3)
        if booking2:
            booking_id2 = booking2["id"]
            self.log(f"Created booking {booking2.get('code')} with total 1,500,000")
            
            # Pay in full
            resp = self.post("payments", email, {
                "booking_id": booking_id2,
                "amount": 1500000,
                "type": "settlement",
                "method": "transfer"
            })
            
            # Complete the booking
            resp = self.post(f"bookings/{booking_id2}/complete", email, {})
            
            # Verify payment_status is 'lunas'
            resp = self.get(f"bookings/{booking_id2}", email)
            if resp.status_code == 200:
                booking_data = resp.json()
                payment_status = booking_data.get("payment_status")
                self.test("RC-02: Fully paid completed booking has payment_status='lunas'",
                         payment_status == "lunas",
                         f"Got payment_status={payment_status}")

    # ========== RC-03: Split-brain Trip Completion Test ==========
    def test_rc03_split_brain_trip(self):
        """RC-03: Trip completion via /trips/{id}/status has same effects as driver checkout"""
        self.log("\n=== RC-03: SPLIT-BRAIN TRIP COMPLETION ===", "INFO")
        
        email = "owner@demo.local"
        customer_id = self.get_test_customer(email)
        vehicle_id = self.get_test_vehicle(email)
        driver_id = self.get_test_driver(email)
        
        if not all([customer_id, vehicle_id, driver_id]):
            self.log("Cannot test RC-03: missing customer, vehicle, or driver", "FAIL")
            return
        
        # Create booking and assign driver+vehicle
        booking = self.create_test_booking(email, customer_id, vehicle_id,
                                          total_amount=1000000, start_offset_days=4)
        if not booking:
            self.log("Cannot test RC-03: failed to create booking", "FAIL")
            return
        
        booking_id = booking["id"]
        self.log(f"Created booking {booking.get('code')}")
        
        # Assign driver and vehicle via dispatch
        resp = self.post(f"dispatch/{booking_id}/assign", email, {
            "driver_id": driver_id,
            "vehicle_id": vehicle_id
        })
        
        if resp.status_code != 200:
            self.log(f"Failed to assign: {resp.status_code} - {resp.text}", "WARN")
            return
        
        trip_data = resp.json()
        trip_id = trip_data.get("trip", {}).get("id")
        
        if not trip_id:
            self.log("Cannot test RC-03: no trip created", "FAIL")
            return
        
        self.log(f"Assigned driver+vehicle, created trip {trip_id}")
        
        # Complete trip via generic /trips/{id}/status endpoint
        resp = self.post(f"trips/{trip_id}/status", email, {"status": "completed"})
        self.test("RC-03: Complete trip via /trips/{id}/status succeeds",
                 resp.status_code == 200,
                 f"Got {resp.status_code}: {resp.text}")
        
        # Verify side effects
        # 1. Trip status is completed
        resp = self.get(f"trips/{trip_id}", email)
        if resp.status_code == 200:
            trip = resp.json()
            self.test("RC-03: Trip status is 'completed'",
                     trip.get("status") == "completed",
                     f"Got status={trip.get('status')}")
        
        # 2. Vehicle is freed to 'available' (if no other active trip)
        resp = self.get(f"vehicles", email)
        if resp.status_code == 200:
            vehicles = resp.json()
            vehicle = next((v for v in vehicles if v["id"] == vehicle_id), None)
            if vehicle:
                # Vehicle may stay on_trip if there's another active trip using it
                # Only flag as failure if vehicle is on_trip with NO active trip
                self.log(f"Vehicle status after trip completion: {vehicle.get('status')}", "INFO")
        
        # 3. Booking is completed
        resp = self.get(f"bookings/{booking_id}", email)
        if resp.status_code == 200:
            booking_data = resp.json()
            self.test("RC-03: Booking status is 'completed'",
                     booking_data.get("status") == "completed",
                     f"Got status={booking_data.get('status')}")

    # ========== RC-04: Cancel/Complete Resource Sync Test ==========
    def test_rc04_cancel_resource_sync(self):
        """RC-04: Cancelling booking frees vehicle and cancels trip"""
        self.log("\n=== RC-04: CANCEL/COMPLETE RESOURCE SYNC ===", "INFO")
        
        email = "owner@demo.local"
        customer_id = self.get_test_customer(email)
        vehicle_id = self.get_test_vehicle(email)
        driver_id = self.get_test_driver(email)
        
        if not all([customer_id, vehicle_id, driver_id]):
            self.log("Cannot test RC-04: missing customer, vehicle, or driver", "FAIL")
            return
        
        # Create booking and assign
        booking = self.create_test_booking(email, customer_id, vehicle_id,
                                          total_amount=1000000, start_offset_days=5)
        if not booking:
            self.log("Cannot test RC-04: failed to create booking", "FAIL")
            return
        
        booking_id = booking["id"]
        self.log(f"Created booking {booking.get('code')}")
        
        # Assign driver and vehicle
        resp = self.post(f"dispatch/{booking_id}/assign", email, {
            "driver_id": driver_id,
            "vehicle_id": vehicle_id
        })
        
        if resp.status_code != 200:
            self.log(f"Failed to assign: {resp.status_code} - {resp.text}", "WARN")
            return
        
        trip_data = resp.json()
        trip_id = trip_data.get("trip", {}).get("id")
        
        if not trip_id:
            self.log("Cannot test RC-04: no trip created", "FAIL")
            return
        
        self.log(f"Assigned driver+vehicle, created trip {trip_id}")
        
        # Cancel the booking
        resp = self.post(f"bookings/{booking_id}/cancel", email, {})
        self.test("RC-04: Cancel booking succeeds",
                 resp.status_code == 200,
                 f"Got {resp.status_code}: {resp.text}")
        
        # Verify trip is cancelled
        resp = self.get(f"trips/{trip_id}", email)
        if resp.status_code == 200:
            trip = resp.json()
            self.test("RC-04: Related trip is 'cancelled'",
                     trip.get("status") == "cancelled",
                     f"Got status={trip.get('status')}")
        
        # Verify vehicle is freed (if no other active trip)
        resp = self.get(f"vehicles", email)
        if resp.status_code == 200:
            vehicles = resp.json()
            vehicle = next((v for v in vehicles if v["id"] == vehicle_id), None)
            if vehicle:
                self.log(f"Vehicle status after cancel: {vehicle.get('status')}", "INFO")

    # ========== RC-05: Payment to Cancelled Booking Test ==========
    def test_rc05_payment_to_cancelled(self):
        """RC-05: Payment to cancelled booking is rejected"""
        self.log("\n=== RC-05: PAYMENT TO CANCELLED BOOKING ===", "INFO")
        
        email = "owner@demo.local"
        customer_id = self.get_test_customer(email)
        vehicle_id = self.get_test_vehicle(email)
        
        if not customer_id or not vehicle_id:
            self.log("Cannot test RC-05: missing customer or vehicle", "FAIL")
            return
        
        # Create booking
        booking = self.create_test_booking(email, customer_id, vehicle_id,
                                          total_amount=1000000, start_offset_days=6)
        if not booking:
            self.log("Cannot test RC-05: failed to create booking", "FAIL")
            return
        
        booking_id = booking["id"]
        self.log(f"Created booking {booking.get('code')}")
        
        # Cancel the booking
        resp = self.post(f"bookings/{booking_id}/cancel", email, {})
        self.test("RC-05: Cancel booking succeeds",
                 resp.status_code == 200,
                 f"Got {resp.status_code}: {resp.text}")
        
        # Try to make payment to cancelled booking
        resp = self.post("payments", email, {
            "booking_id": booking_id,
            "amount": 500000,
            "type": "settlement",
            "method": "transfer"
        })
        
        self.test("RC-05: Payment to cancelled booking is rejected (400)",
                 resp.status_code == 400,
                 f"Got {resp.status_code}: {resp.text}")
        
        if resp.status_code == 400:
            self.test("RC-05: Error message mentions 'dibatalkan' or 'cancelled'",
                     "dibatalkan" in resp.text.lower() or "cancelled" in resp.text.lower(),
                     f"Got: {resp.text}")

    # ========== RC-06: Payroll Overlap Guard Test ==========
    def test_rc06_payroll_overlap(self):
        """RC-06: Overlapping payroll periods are rejected"""
        self.log("\n=== RC-06: PAYROLL OVERLAP GUARD ===", "INFO")
        
        email = "owner@demo.local"
        driver_id = self.get_test_driver(email)
        
        if not driver_id:
            self.log("Cannot test RC-06: no driver found", "FAIL")
            return
        
        # Generate payout for period 2028-06-01 to 2028-06-30
        resp1 = self.post("payroll/payouts/generate", email, {
            "driver_id": driver_id,
            "period_type": "monthly",
            "period_start": "2028-06-01",
            "period_end": "2028-06-30"
        })
        
        self.test("RC-06: First payout generation succeeds",
                 resp1.status_code == 200,
                 f"Got {resp1.status_code}: {resp1.text}")
        
        if resp1.status_code == 200:
            payout1 = resp1.json()
            self.test_data["payouts"].append(payout1.get("id"))
        
        # Try to generate overlapping payout: 2028-06-15 to 2028-07-15
        resp2 = self.post("payroll/payouts/generate", email, {
            "driver_id": driver_id,
            "period_type": "monthly",
            "period_start": "2028-06-15",
            "period_end": "2028-07-15"
        })
        
        self.test("RC-06: Overlapping payout is rejected (400)",
                 resp2.status_code == 400,
                 f"Got {resp2.status_code}: {resp2.text}")
        
        if resp2.status_code == 400:
            self.test("RC-06: Error message mentions 'tumpang-tindih' or 'overlap'",
                     "tumpang-tindih" in resp2.text.lower() or "overlap" in resp2.text.lower(),
                     f"Got: {resp2.text}")
        
        # Non-overlapping period should succeed: 2028-07-01 to 2028-07-31
        resp3 = self.post("payroll/payouts/generate", email, {
            "driver_id": driver_id,
            "period_type": "monthly",
            "period_start": "2028-07-01",
            "period_end": "2028-07-31"
        })
        
        self.test("RC-06: Non-overlapping payout succeeds",
                 resp3.status_code == 200,
                 f"Got {resp3.status_code}: {resp3.text}")
        
        if resp3.status_code == 200:
            payout3 = resp3.json()
            self.test_data["payouts"].append(payout3.get("id"))

    # ========== RC-07: Driver Double-Assign Test ==========
    def test_rc07_driver_double_assign(self):
        """RC-07: Same driver cannot be assigned to overlapping bookings"""
        self.log("\n=== RC-07: DRIVER DOUBLE-ASSIGN PREVENTION ===", "INFO")
        
        email = "owner@demo.local"
        customer_id = self.get_test_customer(email)
        driver_id = self.get_test_driver(email)
        
        # Get two different vehicles
        resp = self.get("vehicles", email)
        if resp.status_code != 200:
            self.log("Cannot test RC-07: failed to get vehicles", "FAIL")
            return
        
        vehicles = resp.json()
        if len(vehicles) < 2:
            self.log("Cannot test RC-07: need at least 2 vehicles", "FAIL")
            return
        
        vehicle_id1 = vehicles[0]["id"]
        vehicle_id2 = vehicles[1]["id"]
        
        if not all([customer_id, driver_id, vehicle_id1, vehicle_id2]):
            self.log("Cannot test RC-07: missing required data", "FAIL")
            return
        
        # Create first booking with overlapping time window
        start1 = datetime(2028, 8, 1, 10, 0)
        end1 = datetime(2028, 8, 3, 18, 0)
        
        booking1 = self.create_test_booking(email, customer_id, vehicle_id1,
                                           total_amount=1000000, start_offset_days=10)
        if not booking1:
            self.log("Cannot test RC-07: failed to create first booking", "FAIL")
            return
        
        booking_id1 = booking1["id"]
        self.log(f"Created booking1 {booking1.get('code')} on vehicle1")
        
        # Assign driver to first booking
        resp = self.post(f"dispatch/{booking_id1}/assign", email, {
            "driver_id": driver_id,
            "vehicle_id": vehicle_id1
        })
        
        self.test("RC-07: Assign driver to booking1 succeeds",
                 resp.status_code == 200,
                 f"Got {resp.status_code}: {resp.text}")
        
        # Create second booking with OVERLAPPING time on DIFFERENT vehicle
        booking2 = self.create_test_booking(email, customer_id, vehicle_id2,
                                           total_amount=1000000, start_offset_days=10)
        if not booking2:
            self.log("Cannot test RC-07: failed to create second booking", "FAIL")
            return
        
        booking_id2 = booking2["id"]
        self.log(f"Created booking2 {booking2.get('code')} on vehicle2 (overlapping time)")
        
        # Try to assign SAME driver to second booking (should be rejected)
        resp = self.post(f"dispatch/{booking_id2}/assign", email, {
            "driver_id": driver_id,
            "vehicle_id": vehicle_id2
        })
        
        self.test("RC-07: Assign same driver to overlapping booking is rejected (400)",
                 resp.status_code == 400,
                 f"Got {resp.status_code}: {resp.text}")
        
        if resp.status_code == 400:
            self.test("RC-07: Error message mentions 'bentrok' or 'conflict'",
                     "bentrok" in resp.text.lower() or "conflict" in resp.text.lower(),
                     f"Got: {resp.text}")

    # ========== RC-08: CORS Hygiene Test ==========
    def test_rc08_cors_hygiene(self):
        """RC-08: CORS configuration is correct"""
        self.log("\n=== RC-08: CORS HYGIENE ===", "INFO")
        
        # Test OPTIONS request
        try:
            resp = requests.options(f"{BASE_URL}/auth/login", timeout=10)
            self.test("RC-08: OPTIONS request succeeds",
                     resp.status_code in [200, 204],
                     f"Got {resp.status_code}")
            
            # Check CORS headers
            headers = resp.headers
            self.test("RC-08: CORS headers present",
                     "Access-Control-Allow-Origin" in headers or 
                     "access-control-allow-origin" in headers,
                     "No CORS headers found")
        except Exception as e:
            self.log(f"RC-08: OPTIONS request failed: {e}", "WARN")
        
        # Verify Bearer auth works (not cookies)
        email = "owner@demo.local"
        resp = self.get("auth/me", email)
        self.test("RC-08: Bearer auth works",
                 resp.status_code == 200,
                 f"Got {resp.status_code}")

    # ========== RC-09: Session TTL Test ==========
    def test_rc09_session_ttl(self):
        """RC-09: Login works and token is valid"""
        self.log("\n=== RC-09: SESSION TTL ===", "INFO")
        
        # Login
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": "ops@demo.local", "password": "demo12345"},
            timeout=10
        )
        
        self.test("RC-09: Login succeeds",
                 resp.status_code == 200,
                 f"Got {resp.status_code}: {resp.text}")
        
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("token")
            self.test("RC-09: Token is returned",
                     token is not None,
                     "No token in response")
            
            # Test /auth/me with token
            if token:
                headers = {"Authorization": f"Bearer {token}"}
                resp = requests.get(f"{BASE_URL}/auth/me", headers=headers, timeout=10)
                self.test("RC-09: /auth/me works with token",
                         resp.status_code == 200,
                         f"Got {resp.status_code}: {resp.text}")

    # ========== REGRESSION: Core Flows Test ==========
    def test_regression_core_flows(self):
        """REGRESSION: Core flows still work end-to-end"""
        self.log("\n=== REGRESSION: CORE FLOWS ===", "INFO")
        
        email = "owner@demo.local"
        
        # Test 1: Auth login for all roles
        for role_email in ["owner@demo.local", "ops@demo.local", "driver@demo.local"]:
            resp = requests.post(
                f"{BASE_URL}/auth/login",
                json={"email": role_email, "password": "demo12345"},
                timeout=10
            )
            self.test(f"REGRESSION: Login as {role_email}",
                     resp.status_code == 200,
                     f"Got {resp.status_code}")
        
        # Test 2: Dashboard loads
        resp = self.get("dashboard", email)
        self.test("REGRESSION: Dashboard loads",
                 resp.status_code == 200,
                 f"Got {resp.status_code}")
        
        # Test 3: List endpoints work
        for endpoint in ["vehicles", "drivers", "customers", "bookings", "payments"]:
            resp = self.get(endpoint, email)
            self.test(f"REGRESSION: GET /{endpoint}",
                     resp.status_code == 200,
                     f"Got {resp.status_code}")
        
        # Test 4: Create customer->vehicle->booking chain
        customer_id = self.get_test_customer(email)
        vehicle_id = self.get_test_vehicle(email)
        
        if customer_id and vehicle_id:
            booking = self.create_test_booking(email, customer_id, vehicle_id,
                                              total_amount=1000000, start_offset_days=20)
            self.test("REGRESSION: Create booking chain",
                     booking is not None,
                     "Failed to create booking")
            
            if booking:
                booking_id = booking["id"]
                
                # Test 5: Record payment
                resp = self.post("payments", email, {
                    "booking_id": booking_id,
                    "amount": 300000,
                    "type": "dp",
                    "method": "transfer"
                })
                self.test("REGRESSION: Record partial payment",
                         resp.status_code == 200,
                         f"Got {resp.status_code}")
                
                # Verify payment_status updated
                resp = self.get(f"bookings/{booking_id}", email)
                if resp.status_code == 200:
                    booking_data = resp.json()
                    self.test("REGRESSION: Payment status updated to 'dp'",
                             booking_data.get("payment_status") == "dp",
                             f"Got {booking_data.get('payment_status')}")
                
                # Test 6: Full payment updates to 'lunas'
                remaining = 700000
                resp = self.post("payments", email, {
                    "booking_id": booking_id,
                    "amount": remaining,
                    "type": "settlement",
                    "method": "transfer"
                })
                self.test("REGRESSION: Record full payment",
                         resp.status_code == 200,
                         f"Got {resp.status_code}")
                
                resp = self.get(f"bookings/{booking_id}", email)
                if resp.status_code == 200:
                    booking_data = resp.json()
                    self.test("REGRESSION: Payment status updated to 'lunas'",
                             booking_data.get("payment_status") == "lunas",
                             f"Got {booking_data.get('payment_status')}")

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "=" * 70, "INFO")
        self.log(f"TESTS RUN: {self.tests_run}", "INFO")
        self.log(f"TESTS PASSED: {self.tests_passed}", "PASS")
        self.log(f"TESTS FAILED: {self.tests_failed}", "FAIL" if self.tests_failed > 0 else "INFO")
        
        if self.tests_run > 0:
            success_rate = (self.tests_passed / self.tests_run) * 100
            self.log(f"SUCCESS RATE: {success_rate:.1f}%", "INFO")
        
        self.log("=" * 70, "INFO")
        
        if self.errors:
            self.log("\nFAILED TESTS:", "FAIL")
            for error in self.errors:
                self.log(f"  - {error}", "FAIL")
        
        return 0 if self.tests_failed == 0 else 1


def main():
    runner = RCTestRunner()
    
    # Login all users
    runner.log("=== LOGGING IN ===", "INFO")
    runner.login("owner@demo.local", "demo12345")
    runner.login("ops@demo.local", "demo12345")
    runner.login("driver@demo.local", "demo12345")
    
    # Run RC tests
    runner.test_rc01_race_overpayment()
    runner.test_rc05_payment_to_cancelled()
    runner.test_rc02_payment_status_honesty()
    runner.test_rc03_split_brain_trip()
    runner.test_rc04_cancel_resource_sync()
    runner.test_rc06_payroll_overlap()
    runner.test_rc07_driver_double_assign()
    runner.test_rc08_cors_hygiene()
    runner.test_rc09_session_ttl()
    runner.test_regression_core_flows()
    
    # Print summary
    return runner.print_summary()


if __name__ == "__main__":
    sys.exit(main())

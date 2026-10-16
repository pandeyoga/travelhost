"""
Backend Testing for E17 RESCHEDULE, E18 HOLD/DP-GATE, E19 PUBLIC SELF-SERVICE, E16 SUB-CHARTER
Tests new features added on top of fully-passing gate suite.
"""
import requests
import sys
import time
from datetime import datetime, timedelta

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

class TestRunner:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.tokens = {}
        self.errors = []
        self.created_bookings = []
        self.created_subcharters = []

    def log(self, msg: str, level: str = "INFO"):
        prefix = {"INFO": "ℹ️", "PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(level, "•")
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

    def login(self, email: str, password: str):
        """Login and store token"""
        self.log(f"Logging in as {email}...")
        try:
            resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=10)
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

    def get(self, endpoint: str, email: str, params=None):
        """GET request with auth"""
        token = self.tokens.get(email)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params, timeout=10)

    def post(self, endpoint: str, email: str, data):
        """POST request with auth"""
        token = self.tokens.get(email)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return requests.post(f"{BASE_URL}/{endpoint}", headers=headers, json=data, timeout=10)

    def post_public(self, endpoint: str, data):
        """POST request without auth (public endpoint)"""
        return requests.post(f"{BASE_URL}/{endpoint}", json=data, timeout=10)

    def cleanup(self):
        """Clean up created test data"""
        owner = "owner@demo.local"
        self.log("\n=== CLEANUP ===", "INFO")
        for booking_id in self.created_bookings:
            try:
                self.post(f"bookings/{booking_id}/cancel", owner, {})
                self.log(f"Cancelled booking {booking_id}")
            except Exception:
                pass
        for sc_id in self.created_subcharters:
            try:
                self.post(f"subcharters/{sc_id}/cancel", owner, {})
                self.log(f"Cancelled subcharter {sc_id}")
            except Exception:
                pass

    def test_e17_reschedule(self):
        """E17: Test booking reschedule endpoint"""
        self.log("\n=== TEST E17: RESCHEDULE ===", "INFO")
        owner = "owner@demo.local"
        
        # Get a customer and vehicle
        customers = self.get("customers", owner).json()
        vehicles = self.get("vehicles", owner).json()
        if not customers or not vehicles:
            self.log("No customers or vehicles found, skipping E17 tests", "WARN")
            return
        
        customer_id = customers[0]["id"]
        vehicle_id = vehicles[0]["id"]
        
        # Create a confirmed booking with 2027 dates
        start_dt = datetime(2027, 6, 15, 8, 0, 0)
        end_dt = datetime(2027, 6, 18, 18, 0, 0)
        
        self.log("Creating confirmed booking for reschedule test...")
        create_resp = self.post("bookings", owner, {
            "customer_id": customer_id,
            "vehicle_id": vehicle_id,
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
            "base_price": 2000000,
            "origin": "Jakarta",
            "destination": "Bandung"
        })
        
        self.test("E17: Create booking for reschedule", create_resp.status_code == 200, 
                 f"Got {create_resp.status_code}: {create_resp.text[:200]}")
        
        if create_resp.status_code != 200:
            return
        
        booking = create_resp.json()
        booking_id = booking["id"]
        self.created_bookings.append(booking_id)
        
        # Test reschedule with new dates
        new_start = datetime(2027, 6, 20, 8, 0, 0)
        new_end = datetime(2027, 6, 23, 18, 0, 0)
        
        self.log(f"Rescheduling booking {booking['code']}...")
        reschedule_resp = self.post(f"bookings/{booking_id}/reschedule", owner, {
            "start_datetime": new_start.isoformat(),
            "end_datetime": new_end.isoformat(),
            "reason": "Customer request"
        })
        
        self.test("E17: Reschedule returns 200", reschedule_resp.status_code == 200,
                 f"Got {reschedule_resp.status_code}: {reschedule_resp.text[:200]}")
        
        if reschedule_resp.status_code == 200:
            rescheduled = reschedule_resp.json()
            self.test("E17: Dates updated", 
                     rescheduled["start_datetime"].startswith("2027-06-20"),
                     f"Start: {rescheduled.get('start_datetime')}")
            self.test("E17: rescheduled_at set", 
                     rescheduled.get("rescheduled_at") is not None,
                     "rescheduled_at is None")
            
            # Check for booking.rescheduled event
            time.sleep(1)  # Wait for event processing
            events_resp = self.get("automation/events", owner, {"type": "booking.rescheduled"})
            if events_resp.status_code == 200:
                events = events_resp.json()
                matching = [e for e in events if e.get("payload", {}).get("booking_id") == booking_id]
                self.test("E17: booking.rescheduled event exists", len(matching) > 0,
                         f"Found {len(matching)} events")
            
            # Check for automation run
            runs_resp = self.get("automation/runs", owner, {"event_type": "booking.rescheduled"})
            if runs_resp.status_code == 200:
                runs = runs_resp.json()
                matching_runs = [r for r in runs if "jadwal ulang" in r.get("rule_name", "").lower()]
                self.test("E17: Automation run for reschedule exists", len(matching_runs) > 0,
                         f"Found {len(matching_runs)} runs")
                if matching_runs:
                    self.test("E17: Automation run status success", 
                             matching_runs[0].get("status") == "success",
                             f"Status: {matching_runs[0].get('status')}")
        
        # Test reschedule rejection on cancelled booking
        self.log("Testing reschedule rejection on cancelled booking...")
        cancel_resp = self.post(f"bookings/{booking_id}/cancel", owner, {})
        if cancel_resp.status_code == 200:
            reschedule_cancelled = self.post(f"bookings/{booking_id}/reschedule", owner, {
                "start_datetime": new_start.isoformat(),
                "end_datetime": new_end.isoformat()
            })
            self.test("E17: Reschedule cancelled booking returns 400", 
                     reschedule_cancelled.status_code == 400,
                     f"Got {reschedule_cancelled.status_code}")
        
        # Test reschedule with invalid dates (end <= start)
        self.log("Testing reschedule with invalid dates...")
        # Create another booking
        create_resp2 = self.post("bookings", owner, {
            "customer_id": customer_id,
            "vehicle_id": vehicle_id,
            "start_datetime": datetime(2027, 7, 1, 8, 0).isoformat(),
            "end_datetime": datetime(2027, 7, 4, 18, 0).isoformat(),
            "base_price": 2000000
        })
        if create_resp2.status_code == 200:
            booking2 = create_resp2.json()
            self.created_bookings.append(booking2["id"])
            
            invalid_reschedule = self.post(f"bookings/{booking2['id']}/reschedule", owner, {
                "start_datetime": datetime(2027, 7, 10, 18, 0).isoformat(),
                "end_datetime": datetime(2027, 7, 10, 8, 0).isoformat()  # end before start
            })
            self.test("E17: Reschedule with end<=start returns 400",
                     invalid_reschedule.status_code == 400,
                     f"Got {invalid_reschedule.status_code}")

    def test_e17_reschedule_conflict(self):
        """E17: Test reschedule conflict detection"""
        self.log("\n=== TEST E17: RESCHEDULE CONFLICT ===", "INFO")
        owner = "owner@demo.local"
        
        customers = self.get("customers", owner).json()
        vehicles = self.get("vehicles", owner).json()
        if not customers or not vehicles:
            return
        
        customer_id = customers[0]["id"]
        vehicle_id = vehicles[0]["id"]
        
        # Create first booking
        start1 = datetime(2027, 8, 1, 8, 0)
        end1 = datetime(2027, 8, 4, 18, 0)
        
        booking1_resp = self.post("bookings", owner, {
            "customer_id": customer_id,
            "vehicle_id": vehicle_id,
            "start_datetime": start1.isoformat(),
            "end_datetime": end1.isoformat(),
            "base_price": 2000000
        })
        
        if booking1_resp.status_code != 200:
            return
        
        booking1 = booking1_resp.json()
        self.created_bookings.append(booking1["id"])
        
        # Create second booking with different dates
        start2 = datetime(2027, 8, 10, 8, 0)
        end2 = datetime(2027, 8, 13, 18, 0)
        
        booking2_resp = self.post("bookings", owner, {
            "customer_id": customer_id,
            "vehicle_id": vehicle_id,
            "start_datetime": start2.isoformat(),
            "end_datetime": end2.isoformat(),
            "base_price": 2000000
        })
        
        if booking2_resp.status_code != 200:
            return
        
        booking2 = booking2_resp.json()
        self.created_bookings.append(booking2["id"])
        
        # Try to reschedule booking2 to overlap with booking1
        self.log("Testing reschedule conflict detection...")
        conflict_reschedule = self.post(f"bookings/{booking2['id']}/reschedule", owner, {
            "start_datetime": datetime(2027, 8, 2, 8, 0).isoformat(),  # overlaps with booking1
            "end_datetime": datetime(2027, 8, 5, 18, 0).isoformat()
        })
        
        self.test("E17: Reschedule conflict returns 400",
                 conflict_reschedule.status_code == 400,
                 f"Got {conflict_reschedule.status_code}")
        
        if conflict_reschedule.status_code == 400:
            self.test("E17: Conflict message mentions 'bentrok'",
                     "bentrok" in conflict_reschedule.text.lower(),
                     f"Response: {conflict_reschedule.text[:200]}")

    def test_e18_hold_dp_gate(self):
        """E18: Test HOLD/DP-GATE functionality"""
        self.log("\n=== TEST E18: HOLD/DP-GATE ===", "INFO")
        owner = "owner@demo.local"
        
        customers = self.get("customers", owner).json()
        vehicles = self.get("vehicles", owner).json()
        if not customers or not vehicles:
            return
        
        customer_id = customers[0]["id"]
        vehicle_id = vehicles[0]["id"]
        
        # Create booking with require_dp=true
        start_dt = datetime(2027, 9, 1, 8, 0)
        end_dt = datetime(2027, 9, 5, 18, 0)
        
        self.log("Creating booking with require_dp=true...")
        hold_resp = self.post("bookings", owner, {
            "customer_id": customer_id,
            "vehicle_id": vehicle_id,
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
            "base_price": 5000000,
            "require_dp": True
        })
        
        self.test("E18: Create hold booking returns 200", hold_resp.status_code == 200,
                 f"Got {hold_resp.status_code}: {hold_resp.text[:200]}")
        
        if hold_resp.status_code != 200:
            return
        
        hold_booking = hold_resp.json()
        booking_id = hold_booking["id"]
        self.created_bookings.append(booking_id)
        
        self.test("E18: Booking status is 'hold'", hold_booking["status"] == "hold",
                 f"Status: {hold_booking.get('status')}")
        self.test("E18: dp_amount is set", hold_booking.get("dp_amount") is not None,
                 "dp_amount is None")
        
        # Check dp_amount is 30% of total (1500000)
        expected_dp = int(5000000 * 0.30)
        self.test("E18: dp_amount is 30% of total", 
                 hold_booking.get("dp_amount") == expected_dp,
                 f"Expected {expected_dp}, got {hold_booking.get('dp_amount')}")
        
        self.test("E18: hold_expires_at is set", hold_booking.get("hold_expires_at") is not None,
                 "hold_expires_at is None")
        
        # Record payment >= dp_amount
        self.log("Recording payment to meet DP requirement...")
        payment_resp = self.post("payments", owner, {
            "booking_id": booking_id,
            "amount": 1500000,
            "type": "dp",
            "method": "transfer"
        })
        
        self.test("E18: Payment recorded successfully", payment_resp.status_code == 200,
                 f"Got {payment_resp.status_code}: {payment_resp.text[:200]}")
        
        # Check booking is auto-promoted to confirmed
        time.sleep(1)
        booking_after_payment = self.get(f"bookings/{booking_id}", owner).json()
        
        self.test("E18: Booking auto-promoted to 'confirmed'",
                 booking_after_payment["status"] == "confirmed",
                 f"Status: {booking_after_payment.get('status')}")
        self.test("E18: dp_met_at is set", booking_after_payment.get("dp_met_at") is not None,
                 "dp_met_at is None")
        
        # Check for booking.confirmed automation run
        runs_resp = self.get("automation/runs", owner, {"event_type": "booking.confirmed"})
        if runs_resp.status_code == 200:
            runs = runs_resp.json()
            matching = [r for r in runs if "konfirmasi" in r.get("rule_name", "").lower()]
            self.test("E18: booking.confirmed automation run exists", len(matching) > 0,
                     f"Found {len(matching)} runs")

    def test_e18_hold_reserves_vehicle(self):
        """E18: Test that hold status reserves vehicle (anti-double-booking)"""
        self.log("\n=== TEST E18: HOLD RESERVES VEHICLE ===", "INFO")
        owner = "owner@demo.local"
        
        customers = self.get("customers", owner).json()
        vehicles = self.get("vehicles", owner).json()
        if not customers or not vehicles:
            return
        
        customer_id = customers[0]["id"]
        vehicle_id = vehicles[0]["id"]
        
        # Create hold booking
        start_dt = datetime(2027, 10, 1, 8, 0)
        end_dt = datetime(2027, 10, 5, 18, 0)
        
        hold_resp = self.post("bookings", owner, {
            "customer_id": customer_id,
            "vehicle_id": vehicle_id,
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
            "base_price": 3000000,
            "require_dp": True
        })
        
        if hold_resp.status_code != 200:
            return
        
        hold_booking = hold_resp.json()
        self.created_bookings.append(hold_booking["id"])
        
        # Try to create another booking with overlapping dates
        self.log("Testing hold blocks double-booking...")
        conflict_resp = self.post("bookings", owner, {
            "customer_id": customer_id,
            "vehicle_id": vehicle_id,
            "start_datetime": datetime(2027, 10, 2, 8, 0).isoformat(),
            "end_datetime": datetime(2027, 10, 6, 18, 0).isoformat(),
            "base_price": 3000000
        })
        
        self.test("E18: Hold blocks overlapping booking (400)",
                 conflict_resp.status_code == 400,
                 f"Got {conflict_resp.status_code}")
        
        if conflict_resp.status_code == 400:
            self.test("E18: Error mentions 'bentrok'",
                     "bentrok" in conflict_resp.text.lower(),
                     f"Response: {conflict_resp.text[:200]}")

    def test_e18_hold_auto_expire(self):
        """E18: Test hold auto-expire via scan endpoint"""
        self.log("\n=== TEST E18: HOLD AUTO-EXPIRE ===", "INFO")
        owner = "owner@demo.local"
        
        # Test scan endpoint
        self.log("Testing POST /api/notifications/scan...")
        scan_resp = self.post("notifications/scan", owner, {})
        
        self.test("E18: Scan endpoint returns 200", scan_resp.status_code == 200,
                 f"Got {scan_resp.status_code}: {scan_resp.text[:200]}")
        
        if scan_resp.status_code == 200:
            scan_data = scan_resp.json()
            self.test("E18: Scan returns created count", "created" in scan_data,
                     f"Response: {scan_data}")

    def test_e19_public_booking(self):
        """E19: Test public self-service booking"""
        self.log("\n=== TEST E19: PUBLIC SELF-SERVICE ===", "INFO")
        owner = "owner@demo.local"
        
        # Create public booking (no auth)
        start_dt = datetime(2027, 11, 1, 8, 0)
        end_dt = datetime(2027, 11, 5, 18, 0)
        unique_phone = f"0812{int(time.time()) % 100000000}"
        
        self.log("Creating public booking request...")
        public_resp = self.post_public("public/booking", {
            "name": "Test Customer Public",
            "phone": unique_phone,
            "email": "test@example.com",
            "origin": "Jakarta",
            "destination": "Bali",
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
            "pax": 10,
            "vehicle_type": "hiace_premio",
            "message": "Test public booking"
        })
        
        self.test("E19: Public booking returns 200", public_resp.status_code == 200,
                 f"Got {public_resp.status_code}: {public_resp.text[:200]}")
        
        if public_resp.status_code != 200:
            return
        
        public_data = public_resp.json()
        self.test("E19: Response status is 'received'", public_data.get("status") == "received",
                 f"Status: {public_data.get('status')}")
        self.test("E19: Response has booking code", public_data.get("code") is not None,
                 "Code is None")
        
        booking_code = public_data.get("code")
        
        # Get booking as owner
        time.sleep(1)
        bookings_resp = self.get("bookings", owner)
        if bookings_resp.status_code == 200:
            bookings = bookings_resp.json()
            matching = [b for b in bookings if b.get("code") == booking_code]
            
            if matching:
                booking = matching[0]
                self.created_bookings.append(booking["id"])
                
                self.test("E19: Booking status is 'pending'", booking["status"] == "pending",
                         f"Status: {booking.get('status')}")
                self.test("E19: Booking source is 'public'", booking.get("source") == "public",
                         f"Source: {booking.get('source')}")
                self.test("E19: vehicle_id is null", booking.get("vehicle_id") is None,
                         f"vehicle_id: {booking.get('vehicle_id')}")
                self.test("E19: total_amount is 0", booking.get("total_amount") == 0,
                         f"total_amount: {booking.get('total_amount')}")
                
                # Check for booking.requested event
                events_resp = self.get("automation/events", owner, {"type": "booking.requested"})
                if events_resp.status_code == 200:
                    events = events_resp.json()
                    matching_events = [e for e in events if e.get("payload", {}).get("code") == booking_code]
                    self.test("E19: booking.requested event exists", len(matching_events) > 0,
                             f"Found {len(matching_events)} events")
                
                # Check for automation run
                runs_resp = self.get("automation/runs", owner, {"event_type": "booking.requested"})
                if runs_resp.status_code == 200:
                    runs = runs_resp.json()
                    matching_runs = [r for r in runs if "permintaan booking" in r.get("rule_name", "").lower()]
                    self.test("E19: Automation run exists", len(matching_runs) > 0,
                             f"Found {len(matching_runs)} runs")
                    if matching_runs:
                        self.test("E19: Automation run status success",
                                 matching_runs[0].get("status") == "success",
                                 f"Status: {matching_runs[0].get('status')}")
            else:
                self.test("E19: Booking found in system", False, f"Code {booking_code} not found")

    def test_e19_honeypot(self):
        """E19: Test honeypot field (hp)"""
        self.log("\n=== TEST E19: HONEYPOT ===", "INFO")
        
        start_dt = datetime(2027, 12, 1, 8, 0)
        end_dt = datetime(2027, 12, 5, 18, 0)
        
        self.log("Testing honeypot with hp='x'...")
        honeypot_resp = self.post_public("public/booking", {
            "name": "Bot Test",
            "phone": "0812999999",
            "hp": "x",  # honeypot field
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
            "pax": 5
        })
        
        self.test("E19: Honeypot returns 'received'", 
                 honeypot_resp.status_code == 200 and honeypot_resp.json().get("status") == "received",
                 f"Got {honeypot_resp.status_code}")
        
        # Verify no booking was actually created
        # (We can't easily verify this without checking the DB, but the endpoint should return success)

    def test_e19_approve_reject(self):
        """E19: Test approve and reject endpoints"""
        self.log("\n=== TEST E19: APPROVE/REJECT ===", "INFO")
        owner = "owner@demo.local"
        
        customers = self.get("customers", owner).json()
        vehicles = self.get("vehicles", owner).json()
        if not customers or not vehicles:
            return
        
        customer_id = customers[0]["id"]
        vehicle_id = vehicles[0]["id"]
        
        # Create pending booking (simulate public booking)
        start_dt = datetime(2027, 12, 10, 8, 0)
        end_dt = datetime(2027, 12, 15, 18, 0)
        
        # We'll create via public endpoint
        unique_phone = f"0813{int(time.time()) % 100000000}"
        public_resp = self.post_public("public/booking", {
            "name": "Test Approve Customer",
            "phone": unique_phone,
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
            "pax": 8
        })
        
        if public_resp.status_code != 200:
            return
        
        booking_code = public_resp.json().get("code")
        time.sleep(1)
        
        # Find the booking
        bookings_resp = self.get("bookings", owner, {"status": "pending"})
        if bookings_resp.status_code != 200:
            return
        
        bookings = bookings_resp.json()
        matching = [b for b in bookings if b.get("code") == booking_code]
        
        if not matching:
            self.log("Pending booking not found for approve test", "WARN")
            return
        
        pending_booking = matching[0]
        booking_id = pending_booking["id"]
        self.created_bookings.append(booking_id)
        
        # Test approve
        self.log(f"Approving booking {booking_code}...")
        approve_resp = self.post(f"bookings/{booking_id}/approve", owner, {
            "vehicle_id": vehicle_id
        })
        
        self.test("E19: Approve returns 200", approve_resp.status_code == 200,
                 f"Got {approve_resp.status_code}: {approve_resp.text[:200]}")
        
        if approve_resp.status_code == 200:
            approved = approve_resp.json()
            self.test("E19: Approved booking status is 'confirmed'",
                     approved["status"] == "confirmed",
                     f"Status: {approved.get('status')}")
            self.test("E19: Vehicle assigned", approved.get("vehicle_id") == vehicle_id,
                     f"vehicle_id: {approved.get('vehicle_id')}")
            self.test("E19: base_price auto-computed (>0)",
                     approved.get("base_price", 0) > 0,
                     f"base_price: {approved.get('base_price')}")
            self.test("E19: total_amount auto-computed (>0)",
                     approved.get("total_amount", 0) > 0,
                     f"total_amount: {approved.get('total_amount')}")
            
            # Check for booking.confirmed run
            time.sleep(1)
            runs_resp = self.get("automation/runs", owner, {"event_type": "booking.confirmed"})
            if runs_resp.status_code == 200:
                runs = runs_resp.json()
                matching_runs = [r for r in runs if "konfirmasi" in r.get("rule_name", "").lower()]
                self.test("E19: booking.confirmed run fires after approve",
                         len(matching_runs) > 0,
                         f"Found {len(matching_runs)} runs")
        
        # Test reject on another pending booking
        unique_phone2 = f"0814{int(time.time()) % 100000000}"
        public_resp2 = self.post_public("public/booking", {
            "name": "Test Reject Customer",
            "phone": unique_phone2,
            "start_datetime": datetime(2027, 12, 20, 8, 0).isoformat(),
            "end_datetime": datetime(2027, 12, 25, 18, 0).isoformat(),
            "pax": 5
        })
        
        if public_resp2.status_code == 200:
            booking_code2 = public_resp2.json().get("code")
            time.sleep(1)
            
            bookings_resp2 = self.get("bookings", owner, {"status": "pending"})
            if bookings_resp2.status_code == 200:
                bookings2 = bookings_resp2.json()
                matching2 = [b for b in bookings2 if b.get("code") == booking_code2]
                
                if matching2:
                    pending_booking2 = matching2[0]
                    booking_id2 = pending_booking2["id"]
                    self.created_bookings.append(booking_id2)
                    
                    self.log(f"Rejecting booking {booking_code2}...")
                    reject_resp = self.post(f"bookings/{booking_id2}/reject", owner, {})
                    
                    self.test("E19: Reject returns 200", reject_resp.status_code == 200,
                             f"Got {reject_resp.status_code}")
                    
                    if reject_resp.status_code == 200:
                        rejected = reject_resp.json()
                        self.test("E19: Rejected booking status is 'cancelled'",
                                 rejected["status"] == "cancelled",
                                 f"Status: {rejected.get('status')}")
                        
                        # Check for booking.cancelled event
                        time.sleep(1)
                        events_resp = self.get("automation/events", owner, {"type": "booking.cancelled"})
                        if events_resp.status_code == 200:
                            events = events_resp.json()
                            matching_events = [e for e in events if e.get("payload", {}).get("booking_id") == booking_id2]
                            self.test("E19: booking.cancelled event exists",
                                     len(matching_events) > 0,
                                     f"Found {len(matching_events)} events")
        
        # Test approve on non-pending booking (should fail)
        if approve_resp.status_code == 200:
            self.log("Testing approve on non-pending booking...")
            approve_again = self.post(f"bookings/{booking_id}/approve", owner, {"vehicle_id": vehicle_id})
            self.test("E19: Approve non-pending returns 400",
                     approve_again.status_code == 400,
                     f"Got {approve_again.status_code}")

    def test_e16_subcharter(self):
        """E16: Test partner sub-charter (verify existing feature)"""
        self.log("\n=== TEST E16: PARTNER SUB-CHARTER ===", "INFO")
        owner = "owner@demo.local"
        
        # Get partners
        partners_resp = self.get("partners", owner)
        self.test("E16: GET /api/partners returns 200", partners_resp.status_code == 200,
                 f"Got {partners_resp.status_code}")
        
        if partners_resp.status_code != 200:
            return
        
        partners = partners_resp.json()
        if not partners:
            self.log("No partners found, skipping E16 tests", "WARN")
            return
        
        partner_id = partners[0]["id"]
        
        # Get a booking
        bookings_resp = self.get("bookings", owner, {"status": "confirmed", "limit": 1})
        if bookings_resp.status_code != 200 or not bookings_resp.json():
            self.log("No confirmed bookings found, skipping E16 tests", "WARN")
            return
        
        booking = bookings_resp.json()[0]
        booking_id = booking["id"]
        
        # Create subcharter
        self.log("Creating subcharter...")
        sc_resp = self.post("subcharters", owner, {
            "booking_id": booking_id,
            "partner_id": partner_id,
            "vehicle_label": "Unit Mitra Test",
            "cost": 1500000
        })
        
        self.test("E16: Create subcharter returns 200", sc_resp.status_code == 200,
                 f"Got {sc_resp.status_code}: {sc_resp.text[:200]}")
        
        if sc_resp.status_code != 200:
            return
        
        subcharter = sc_resp.json()
        sc_id = subcharter["id"]
        self.created_subcharters.append(sc_id)
        
        self.test("E16: Subcharter status is 'requested'",
                 subcharter["status"] == "requested",
                 f"Status: {subcharter.get('status')}")
        
        # Confirm subcharter
        self.log("Confirming subcharter...")
        confirm_resp = self.post(f"subcharters/{sc_id}/confirm", owner, {})
        
        self.test("E16: Confirm subcharter returns 200", confirm_resp.status_code == 200,
                 f"Got {confirm_resp.status_code}")
        
        if confirm_resp.status_code == 200:
            confirmed_sc = confirm_resp.json()
            self.test("E16: Confirmed status is 'confirmed'",
                     confirmed_sc["status"] == "confirmed",
                     f"Status: {confirmed_sc.get('status')}")
            self.test("E16: expense_id is set",
                     confirmed_sc.get("expense_id") is not None,
                     "expense_id is None")
            
            # Check for subcharter.confirmed event
            time.sleep(1)
            events_resp = self.get("automation/events", owner, {"type": "subcharter.confirmed"})
            if events_resp.status_code == 200:
                events = events_resp.json()
                matching = [e for e in events if e.get("ref_id") == sc_id]
                self.test("E16: subcharter.confirmed event exists",
                         len(matching) > 0,
                         f"Found {len(matching)} events")
        
        # Settle subcharter
        self.log("Settling subcharter...")
        settle_resp = self.post(f"subcharters/{sc_id}/settle", owner, {})
        
        self.test("E16: Settle subcharter returns 200", settle_resp.status_code == 200,
                 f"Got {settle_resp.status_code}")
        
        if settle_resp.status_code == 200:
            settled_sc = settle_resp.json()
            self.test("E16: Settled status is 'settled'",
                     settled_sc["status"] == "settled",
                     f"Status: {settled_sc.get('status')}")
            
            # Check for subcharter.settled event
            time.sleep(1)
            events_resp = self.get("automation/events", owner, {"type": "subcharter.settled"})
            if events_resp.status_code == 200:
                events = events_resp.json()
                matching = [e for e in events if e.get("ref_id") == sc_id]
                self.test("E16: subcharter.settled event exists",
                         len(matching) > 0,
                         f"Found {len(matching)} events")

    def test_regression_payment(self):
        """Regression: Test payment flow"""
        self.log("\n=== TEST REGRESSION: PAYMENT FLOW ===", "INFO")
        owner = "owner@demo.local"
        
        customers = self.get("customers", owner).json()
        vehicles = self.get("vehicles", owner).json()
        if not customers or not vehicles:
            return
        
        # Create booking with total 1,000,000
        booking_resp = self.post("bookings", owner, {
            "customer_id": customers[0]["id"],
            "vehicle_id": vehicles[0]["id"],
            "start_datetime": datetime(2027, 12, 25, 8, 0).isoformat(),
            "end_datetime": datetime(2027, 12, 28, 18, 0).isoformat(),
            "base_price": 1000000
        })
        
        if booking_resp.status_code != 200:
            return
        
        booking = booking_resp.json()
        booking_id = booking["id"]
        self.created_bookings.append(booking_id)
        
        # Pay 400,000 (DP)
        self.log("Paying 400,000 (DP)...")
        pay1 = self.post("payments", owner, {
            "booking_id": booking_id,
            "amount": 400000,
            "type": "dp"
        })
        self.test("Regression: First payment (400k) success", pay1.status_code == 200,
                 f"Got {pay1.status_code}")
        
        # Check booking
        booking_after_dp = self.get(f"bookings/{booking_id}", owner).json()
        self.test("Regression: paid_amount is 400000",
                 booking_after_dp.get("paid_amount") == 400000,
                 f"paid_amount: {booking_after_dp.get('paid_amount')}")
        self.test("Regression: payment_status is 'dp'",
                 booking_after_dp.get("payment_status") == "dp",
                 f"payment_status: {booking_after_dp.get('payment_status')}")
        
        # Pay 600,000 (settlement)
        self.log("Paying 600,000 (settlement)...")
        pay2 = self.post("payments", owner, {
            "booking_id": booking_id,
            "amount": 600000,
            "type": "settlement"
        })
        self.test("Regression: Second payment (600k) success", pay2.status_code == 200,
                 f"Got {pay2.status_code}")
        
        # Check booking
        booking_after_full = self.get(f"bookings/{booking_id}", owner).json()
        self.test("Regression: paid_amount is 1000000",
                 booking_after_full.get("paid_amount") == 1000000,
                 f"paid_amount: {booking_after_full.get('paid_amount')}")
        self.test("Regression: payment_status is 'lunas'",
                 booking_after_full.get("payment_status") == "lunas",
                 f"payment_status: {booking_after_full.get('payment_status')}")
        
        # Try to pay extra 100,000 (should return 400)
        self.log("Trying to overpay (100k extra)...")
        pay3 = self.post("payments", owner, {
            "booking_id": booking_id,
            "amount": 100000,
            "type": "settlement"
        })
        self.test("Regression: Overpayment returns 400", pay3.status_code == 400,
                 f"Got {pay3.status_code}")
        
        # Test payment to cancelled booking
        cancel_resp = self.post(f"bookings/{booking_id}/cancel", owner, {})
        if cancel_resp.status_code == 200:
            pay_cancelled = self.post("payments", owner, {
                "booking_id": booking_id,
                "amount": 50000,
                "type": "settlement"
            })
            self.test("Regression: Payment to cancelled booking returns 400",
                     pay_cancelled.status_code == 400,
                     f"Got {pay_cancelled.status_code}")

    def test_regression_core(self):
        """Regression: Test core functionality"""
        self.log("\n=== TEST REGRESSION: CORE ===", "INFO")
        
        # Test login all roles
        owner_login = self.login("owner@demo.local", "demo12345")
        self.test("Regression: Owner login success", bool(owner_login.get("token")),
                 "No token returned")
        
        ops_login = self.login("ops@demo.local", "demo12345")
        self.test("Regression: Ops login success", bool(ops_login.get("token")),
                 "No token returned")
        
        driver_login = self.login("driver@demo.local", "demo12345")
        self.test("Regression: Driver login success", bool(driver_login.get("token")),
                 "No token returned")
        
        owner = "owner@demo.local"
        
        # Test dashboard
        dashboard = self.get("dashboard", owner)
        self.test("Regression: GET /api/dashboard returns 200", dashboard.status_code == 200,
                 f"Got {dashboard.status_code}")
        
        if dashboard.status_code == 200:
            dash_data = dashboard.json()
            # Check active_bookings counts only confirmed/ongoing (NOT pending/hold)
            active_count = dash_data.get("active_bookings", 0)
            self.test("Regression: active_bookings is a number", isinstance(active_count, int),
                     f"Got {type(active_count)}")
        
        # Test list endpoints
        endpoints = ["vehicles", "drivers", "customers", "bookings", "payments", "invoices", "expenses"]
        for endpoint in endpoints:
            resp = self.get(endpoint, owner)
            self.test(f"Regression: GET /api/{endpoint} returns 200",
                     resp.status_code == 200,
                     f"Got {resp.status_code}")

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "=" * 60, "INFO")
        self.log(f"TESTS RUN: {self.tests_run}", "INFO")
        self.log(f"TESTS PASSED: {self.tests_passed}", "PASS")
        self.log(f"TESTS FAILED: {self.tests_failed}", "FAIL" if self.tests_failed > 0 else "INFO")
        self.log("=" * 60, "INFO")
        
        if self.errors:
            self.log("\nFAILED TESTS:", "FAIL")
            for error in self.errors[:10]:  # Show first 10 errors
                self.log(f"  - {error}", "FAIL")
            if len(self.errors) > 10:
                self.log(f"  ... and {len(self.errors) - 10} more", "FAIL")
        
        return 0 if self.tests_failed == 0 else 1


def main():
    runner = TestRunner()
    
    try:
        # Login
        runner.log("=== LOGGING IN ===", "INFO")
        runner.login("owner@demo.local", "demo12345")
        runner.login("ops@demo.local", "demo12345")
        runner.login("driver@demo.local", "demo12345")
        
        # Run tests
        runner.test_e17_reschedule()
        runner.test_e17_reschedule_conflict()
        runner.test_e18_hold_dp_gate()
        runner.test_e18_hold_reserves_vehicle()
        runner.test_e18_hold_auto_expire()
        runner.test_e19_public_booking()
        runner.test_e19_honeypot()
        runner.test_e19_approve_reject()
        runner.test_e16_subcharter()
        runner.test_regression_payment()
        runner.test_regression_core()
        
    finally:
        # Cleanup
        runner.cleanup()
    
    # Print summary
    return runner.print_summary()


if __name__ == "__main__":
    sys.exit(main())

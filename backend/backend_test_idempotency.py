"""backend_test_idempotency.py — Test idempotency fix for POST /api/payments.

PRIMARY: 6 parallel payments with SAME idempotency_key -> exactly 1 payment record.
REGRESSION: overpay guard, cancelled booking, payment_status, DP-gate, anti double-booking.
"""
import requests
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

class IdempotencyTester:
    def __init__(self):
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.customer_id = None
        self.vehicle_id = None
        self.driver_id = None

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def test(self, name, condition, details=""):
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            self.log(f"✅ {name}")
            if details:
                self.log(f"   {details}")
        else:
            self.log(f"❌ {name}")
            if details:
                self.log(f"   {details}")
        return condition

    def login(self, email="owner@demo.local", password="demo12345"):
        self.log(f"Logging in as {email}...")
        r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
        if r.status_code == 200:
            data = r.json()
            self.token = data.get("token")
            self.log(f"✅ Login successful, token: {self.token[:20]}...")
            return True
        else:
            self.log(f"❌ Login failed: {r.status_code} {r.text}")
            return False

    def headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def setup_master_data(self):
        """Create customer, vehicle, driver for testing."""
        self.log("Setting up master data...")
        
        # Create customer with unique phone
        unique_suffix = uuid.uuid4().hex[:8]
        r = requests.post(f"{BASE_URL}/customers", json={
            "name": f"Test Customer Idem {unique_suffix}",
            "phone": f"0812{unique_suffix[:8]}",
            "email": f"test.idem.{unique_suffix}@test.com"
        }, headers=self.headers())
        if r.status_code in (200, 201):
            self.customer_id = r.json().get("id")
            self.log(f"✅ Customer created: {self.customer_id}")
        else:
            self.log(f"❌ Customer creation failed: {r.status_code} {r.text}")
            return False

        # Create vehicle
        r = requests.post(f"{BASE_URL}/vehicles", json={
            "name": f"Test Vehicle Idem {unique_suffix}",
            "plate_number": f"B{unique_suffix[:4].upper()}TEST",
            "type": "hiace",
            "capacity": 14,
            "status": "available"
        }, headers=self.headers())
        if r.status_code in (200, 201):
            self.vehicle_id = r.json().get("id")
            self.log(f"✅ Vehicle created: {self.vehicle_id}")
        else:
            self.log(f"❌ Vehicle creation failed: {r.status_code} {r.text}")
            return False

        # Create driver with unique phone
        r = requests.post(f"{BASE_URL}/drivers", json={
            "name": f"Test Driver Idem {unique_suffix}",
            "phone": f"0813{unique_suffix[:8]}",
            "status": "available"
        }, headers=self.headers())
        if r.status_code in (200, 201):
            self.driver_id = r.json().get("id")
            self.log(f"✅ Driver created: {self.driver_id}")
        else:
            self.log(f"❌ Driver creation failed: {r.status_code} {r.text}")
            return False

        return True

    def create_booking(self, total_amount=2000000, require_dp=False, use_new_vehicle=False, use_new_driver=False):
        """Create a booking with specified total_amount."""
        # Use different time slots to avoid conflicts
        import random
        days_offset = random.randint(5, 30)
        start = (datetime.now() + timedelta(days=days_offset)).strftime("%Y-%m-%dT10:00:00")
        end = (datetime.now() + timedelta(days=days_offset+1)).strftime("%Y-%m-%dT18:00:00")
        
        # Create new vehicle if requested to avoid conflicts
        vehicle_id = self.vehicle_id
        if use_new_vehicle:
            r_veh = requests.post(f"{BASE_URL}/vehicles", json={
                "name": f"Test Vehicle {uuid.uuid4().hex[:6]}",
                "plate_number": f"B{uuid.uuid4().hex[:4].upper()}TST",
                "type": "hiace",
                "capacity": 14,
                "status": "available"
            }, headers=self.headers())
            if r_veh.status_code in (200, 201):
                vehicle_id = r_veh.json().get("id")
        
        # Create new driver if requested to avoid conflicts
        driver_id = self.driver_id
        if use_new_driver:
            unique_suffix = uuid.uuid4().hex[:8]
            r_drv = requests.post(f"{BASE_URL}/drivers", json={
                "name": f"Test Driver {unique_suffix}",
                "phone": f"0815{unique_suffix[:8]}",
                "status": "available"
            }, headers=self.headers())
            if r_drv.status_code in (200, 201):
                driver_id = r_drv.json().get("id")
        
        r = requests.post(f"{BASE_URL}/bookings", json={
            "customer_id": self.customer_id,
            "vehicle_id": vehicle_id,
            "driver_id": driver_id,
            "origin": "Jakarta",
            "destination": "Bandung",
            "start_datetime": start,
            "end_datetime": end,
            "base_price": total_amount,
            "require_dp": require_dp,
            "notes": "Idempotency test booking"
        }, headers=self.headers())
        
        if r.status_code in (200, 201):
            booking = r.json()
            self.log(f"✅ Booking created: {booking.get('id')} (code: {booking.get('code')}, total: {booking.get('total_amount')})")
            return booking
        else:
            self.log(f"❌ Booking creation failed: {r.status_code} {r.text}")
            return None

    def make_payment(self, booking_id, amount, idempotency_key=None, payment_type="settlement"):
        """Make a single payment."""
        payload = {
            "booking_id": booking_id,
            "amount": amount,
            "type": payment_type,
            "method": "transfer",
            "note": "Test payment"
        }
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        
        r = requests.post(f"{BASE_URL}/payments", json=payload, headers=self.headers())
        return r

    def get_payments(self, booking_id):
        """Get all payments for a booking."""
        r = requests.get(f"{BASE_URL}/payments?booking_id={booking_id}", headers=self.headers())
        if r.status_code == 200:
            return r.json()
        return []

    def get_booking(self, booking_id):
        """Get booking details."""
        r = requests.get(f"{BASE_URL}/bookings/{booking_id}", headers=self.headers())
        if r.status_code == 200:
            return r.json()
        return None

    def test_parallel_idempotency(self):
        """PRIMARY TEST: 6 parallel payments with SAME idempotency_key -> exactly 1 payment record."""
        self.log("\n" + "="*80)
        self.log("PRIMARY TEST: Parallel Idempotency (6 concurrent requests)")
        self.log("="*80)
        
        # Create booking with total 2,000,000
        booking = self.create_booking(total_amount=2000000)
        if not booking:
            return False
        
        booking_id = booking.get("id")
        idempotency_key = str(uuid.uuid4())
        amount = 300000
        
        self.log(f"Firing 6 PARALLEL payments with SAME idempotency_key: {idempotency_key}")
        self.log(f"Amount per request: {amount:,}")
        
        # Fire 6 parallel requests
        responses = []
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [
                executor.submit(self.make_payment, booking_id, amount, idempotency_key)
                for _ in range(6)
            ]
            for future in as_completed(futures):
                try:
                    r = future.result()
                    responses.append(r)
                    self.log(f"  Response: {r.status_code}")
                except Exception as e:
                    self.log(f"  Exception: {e}")
        
        # Check all responses are 2xx
        all_success = all(r.status_code in (200, 201) for r in responses)
        self.test("All 6 parallel requests returned 2xx", all_success,
                  f"Status codes: {[r.status_code for r in responses]}")
        
        # Check exactly 1 payment record created
        payments = self.get_payments(booking_id)
        self.test("Exactly 1 payment record created", len(payments) == 1,
                  f"Found {len(payments)} payment(s)")
        
        # Check booking.paid_amount == 300000 (NOT 1,800,000)
        booking_after = self.get_booking(booking_id)
        paid_amount = booking_after.get("paid_amount", 0) if booking_after else 0
        self.test("Booking paid_amount == 300000 (not 1,800,000)", paid_amount == 300000,
                  f"paid_amount: {paid_amount:,}")
        
        # Check payment_status is 'dp' (0 < 300000 < 2000000)
        payment_status = booking_after.get("payment_status") if booking_after else None
        self.test("Payment status is 'dp'", payment_status == "dp",
                  f"payment_status: {payment_status}")
        
        return booking_id, idempotency_key

    def test_sequential_replay(self, booking_id, idempotency_key):
        """Test sequential replay with SAME idempotency_key -> still 1 record."""
        self.log("\n" + "="*80)
        self.log("TEST: Sequential Replay (same idempotency_key)")
        self.log("="*80)
        
        # Make another payment with SAME idempotency_key
        r = self.make_payment(booking_id, 300000, idempotency_key)
        self.test("Sequential replay returns 200", r.status_code == 200,
                  f"Status: {r.status_code}")
        
        # Check still only 1 payment record
        payments = self.get_payments(booking_id)
        self.test("Still only 1 payment record", len(payments) == 1,
                  f"Found {len(payments)} payment(s)")
        
        # Check paid_amount unchanged (300000)
        booking_after = self.get_booking(booking_id)
        paid_amount = booking_after.get("paid_amount", 0) if booking_after else 0
        self.test("Paid amount unchanged (300000)", paid_amount == 300000,
                  f"paid_amount: {paid_amount:,}")

    def test_backward_compat_no_key(self):
        """Test backward compatibility: POST without idempotency_key creates distinct records."""
        self.log("\n" + "="*80)
        self.log("TEST: Backward Compatibility (no idempotency_key)")
        self.log("="*80)
        
        # Create new booking with new vehicle and driver to avoid conflicts
        booking = self.create_booking(total_amount=1000000, use_new_vehicle=True, use_new_driver=True)
        if not booking:
            return
        
        booking_id = booking.get("id")
        
        # Make 2 payments WITHOUT idempotency_key
        r1 = self.make_payment(booking_id, 200000, idempotency_key=None)
        r2 = self.make_payment(booking_id, 300000, idempotency_key=None)
        
        self.test("First payment without key returns 2xx", r1.status_code in (200, 201),
                  f"Status: {r1.status_code}")
        self.test("Second payment without key returns 2xx", r2.status_code in (200, 201),
                  f"Status: {r2.status_code}")
        
        # Check 2 payment records created
        payments = self.get_payments(booking_id)
        self.test("Two payment records created", len(payments) == 2,
                  f"Found {len(payments)} payment(s)")
        
        # Check paid_amount == 500000
        booking_after = self.get_booking(booking_id)
        paid_amount = booking_after.get("paid_amount", 0) if booking_after else 0
        self.test("Paid amount == 500000", paid_amount == 500000,
                  f"paid_amount: {paid_amount:,}")

    def test_distinct_keys(self):
        """Test different idempotency_keys -> 2 records."""
        self.log("\n" + "="*80)
        self.log("TEST: Distinct Idempotency Keys")
        self.log("="*80)
        
        # Create new booking with new vehicle and driver to avoid conflicts
        booking = self.create_booking(total_amount=1000000, use_new_vehicle=True, use_new_driver=True)
        if not booking:
            return
        
        booking_id = booking.get("id")
        
        # Make 2 payments with DIFFERENT idempotency_keys
        key1 = str(uuid.uuid4())
        key2 = str(uuid.uuid4())
        r1 = self.make_payment(booking_id, 200000, idempotency_key=key1)
        r2 = self.make_payment(booking_id, 300000, idempotency_key=key2)
        
        self.test("First payment with key1 returns 2xx", r1.status_code in (200, 201),
                  f"Status: {r1.status_code}")
        self.test("Second payment with key2 returns 2xx", r2.status_code in (200, 201),
                  f"Status: {r2.status_code}")
        
        # Check 2 payment records created
        payments = self.get_payments(booking_id)
        self.test("Two payment records created", len(payments) == 2,
                  f"Found {len(payments)} payment(s)")
        
        # Check paid_amount == 500000
        booking_after = self.get_booking(booking_id)
        paid_amount = booking_after.get("paid_amount", 0) if booking_after else 0
        self.test("Paid amount == 500000", paid_amount == 500000,
                  f"paid_amount: {paid_amount:,}")

    def test_overpay_guard(self):
        """REGRESSION: Overpay guard returns 400 'melebihi sisa'."""
        self.log("\n" + "="*80)
        self.log("REGRESSION TEST: Overpay Guard")
        self.log("="*80)
        
        # Create booking with total 500000 with new vehicle and driver to avoid conflicts
        booking = self.create_booking(total_amount=500000, use_new_vehicle=True, use_new_driver=True)
        if not booking:
            return
        
        booking_id = booking.get("id")
        
        # Pay 300000 first
        r1 = self.make_payment(booking_id, 300000)
        self.test("First payment 300000 succeeds", r1.status_code in (200, 201),
                  f"Status: {r1.status_code}")
        
        # Try to pay 300000 again (total would be 600000 > 500000)
        r2 = self.make_payment(booking_id, 300000)
        self.test("Overpay returns 400", r2.status_code == 400,
                  f"Status: {r2.status_code}")
        
        # Check error message contains 'melebihi sisa'
        if r2.status_code == 400:
            error_msg = r2.json().get("detail", "")
            self.test("Error message contains 'melebihi sisa'", "melebihi sisa" in error_msg.lower(),
                      f"Error: {error_msg}")

    def test_cancelled_booking_payment(self):
        """REGRESSION: Payment on cancelled booking returns 400."""
        self.log("\n" + "="*80)
        self.log("REGRESSION TEST: Cancelled Booking Payment")
        self.log("="*80)
        
        # Create booking with new vehicle and driver to avoid conflicts
        booking = self.create_booking(total_amount=500000, use_new_vehicle=True, use_new_driver=True)
        if not booking:
            return
        
        booking_id = booking.get("id")
        
        # Cancel booking
        r_cancel = requests.post(f"{BASE_URL}/bookings/{booking_id}/cancel", json={
            "reason": "Test cancellation",
            "cancellation_fee": 0,
            "refund_amount": 0
        }, headers=self.headers())
        self.test("Booking cancellation succeeds", r_cancel.status_code in (200, 201),
                  f"Status: {r_cancel.status_code}")
        
        # Try to make payment on cancelled booking
        r_pay = self.make_payment(booking_id, 100000)
        self.test("Payment on cancelled booking returns 400", r_pay.status_code == 400,
                  f"Status: {r_pay.status_code}")
        
        if r_pay.status_code == 400:
            error_msg = r_pay.json().get("detail", "")
            self.test("Error message mentions cancellation", "batal" in error_msg.lower(),
                      f"Error: {error_msg}")

    def test_payment_status_derivation(self):
        """REGRESSION: Payment status derivation (belum_bayar/dp/lunas)."""
        self.log("\n" + "="*80)
        self.log("REGRESSION TEST: Payment Status Derivation")
        self.log("="*80)
        
        # Create booking with total 1000000 with new vehicle and driver to avoid conflicts
        booking = self.create_booking(total_amount=1000000, use_new_vehicle=True, use_new_driver=True)
        if not booking:
            return
        
        booking_id = booking.get("id")
        
        # Check initial status is 'belum_bayar'
        booking_initial = self.get_booking(booking_id)
        initial_status = booking_initial.get("payment_status") if booking_initial else None
        self.test("Initial payment_status is 'belum_bayar'", initial_status == "belum_bayar",
                  f"payment_status: {initial_status}")
        
        # Pay 300000 (partial) -> should be 'dp'
        r1 = self.make_payment(booking_id, 300000)
        booking_after_dp = self.get_booking(booking_id)
        dp_status = booking_after_dp.get("payment_status") if booking_after_dp else None
        self.test("After partial payment, status is 'dp'", dp_status == "dp",
                  f"payment_status: {dp_status}")
        
        # Pay remaining 700000 -> should be 'lunas'
        r2 = self.make_payment(booking_id, 700000)
        booking_after_full = self.get_booking(booking_id)
        full_status = booking_after_full.get("payment_status") if booking_after_full else None
        self.test("After full payment, status is 'lunas'", full_status == "lunas",
                  f"payment_status: {full_status}")

    def test_dp_gate(self):
        """REGRESSION: DP-gate (hold->confirmed on DP with require_dp)."""
        self.log("\n" + "="*80)
        self.log("REGRESSION TEST: DP Gate (hold->confirmed)")
        self.log("="*80)
        
        # Create booking with require_dp=True (should be 'hold' status) with new vehicle and driver to avoid conflicts
        booking = self.create_booking(total_amount=1000000, require_dp=True, use_new_vehicle=True, use_new_driver=True)
        if not booking:
            return
        
        booking_id = booking.get("id")
        
        # Check initial status is 'hold'
        booking_initial = self.get_booking(booking_id)
        initial_status = booking_initial.get("status") if booking_initial else None
        self.test("Initial booking status is 'hold'", initial_status == "hold",
                  f"status: {initial_status}")
        
        # Pay DP (30% of 1000000 = 300000)
        r_dp = self.make_payment(booking_id, 300000, payment_type="dp")
        self.test("DP payment succeeds", r_dp.status_code in (200, 201),
                  f"Status: {r_dp.status_code}")
        
        # Check status changed to 'confirmed'
        booking_after_dp = self.get_booking(booking_id)
        after_status = booking_after_dp.get("status") if booking_after_dp else None
        self.test("After DP, booking status is 'confirmed'", after_status == "confirmed",
                  f"status: {after_status}")

    def test_negative_addon(self):
        """REGRESSION: Negative add_on returns 422."""
        self.log("\n" + "="*80)
        self.log("REGRESSION TEST: Negative Add-on")
        self.log("="*80)
        
        start = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT10:00:00")
        end = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%dT18:00:00")
        
        # Try to create booking with negative add_on
        r = requests.post(f"{BASE_URL}/bookings", json={
            "customer_id": self.customer_id,
            "vehicle_id": self.vehicle_id,
            "driver_id": self.driver_id,
            "origin": "Jakarta",
            "destination": "Bandung",
            "start_datetime": start,
            "end_datetime": end,
            "base_price": 1000000,
            "add_ons": [{"label": "Discount", "amount": -100000}],
            "notes": "Negative add-on test"
        }, headers=self.headers())
        
        self.test("Negative add_on returns 422", r.status_code == 422,
                  f"Status: {r.status_code}")

    def run_all_tests(self):
        """Run all tests."""
        self.log("\n" + "="*80)
        self.log("IDEMPOTENCY FIX TEST SUITE")
        self.log("="*80)
        
        if not self.login():
            self.log("❌ Login failed, aborting tests")
            return False
        
        if not self.setup_master_data():
            self.log("❌ Master data setup failed, aborting tests")
            return False
        
        # PRIMARY TESTS
        result = self.test_parallel_idempotency()
        if result:
            booking_id, idempotency_key = result
            self.test_sequential_replay(booking_id, idempotency_key)
        
        self.test_backward_compat_no_key()
        self.test_distinct_keys()
        
        # REGRESSION TESTS
        self.test_overpay_guard()
        self.test_cancelled_booking_payment()
        self.test_payment_status_derivation()
        self.test_dp_gate()
        self.test_negative_addon()
        
        # Summary
        self.log("\n" + "="*80)
        self.log(f"SUMMARY: {self.tests_passed}/{self.tests_run} tests passed")
        self.log("="*80)
        
        return self.tests_passed == self.tests_run


def main():
    tester = IdempotencyTester()
    success = tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

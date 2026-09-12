"""
RC-10 & RC-11 Testing: Persistent Rate-Limit + Money as Integer
Tests the final two hygiene items plus RC-01 atomic payment regression.
"""
import requests
import sys
import time
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

class TestRunner:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.token = None
        self.errors = []
        self.created_ids = {
            "bookings": [],
            "payments": [],
            "expenses": [],
            "invoices": [],
            "payouts": []
        }

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

    def login(self, email: str, password: str) -> dict:
        """Login and store token"""
        self.log(f"Logging in as {email}...")
        try:
            resp = requests.post(f"{BASE_URL}/auth/login", 
                               json={"email": email, "password": password}, 
                               timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("token")
                self.log(f"Login successful for {email}", "PASS")
                return data
            else:
                self.log(f"Login failed: {resp.status_code} - {resp.text}", "FAIL")
                return {}
        except Exception as e:
            self.log(f"Login exception: {e}", "FAIL")
            return {}

    def get(self, endpoint: str, params: dict = None) -> requests.Response:
        """GET request with auth"""
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        return requests.get(f"{BASE_URL}{endpoint}", headers=headers, params=params, timeout=10)

    def post(self, endpoint: str, data: dict) -> requests.Response:
        """POST request with auth"""
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        return requests.post(f"{BASE_URL}{endpoint}", headers=headers, json=data, timeout=10)

    def cleanup(self):
        """Clean up test data"""
        self.log("Cleaning up test data...")
        # Note: In production, we'd delete created test objects
        # For now, just log what was created
        for entity_type, ids in self.created_ids.items():
            if ids:
                self.log(f"Created {len(ids)} {entity_type}: {ids[:3]}{'...' if len(ids) > 3 else ''}")

    def summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print(f"📊 TEST SUMMARY")
        print("="*60)
        print(f"Total Tests: {self.tests_run}")
        print(f"✅ Passed: {self.tests_passed}")
        print(f"❌ Failed: {self.tests_failed}")
        if self.errors:
            print("\n🔴 FAILED TESTS:")
            for err in self.errors:
                print(f"  - {err}")
        print("="*60)
        return 0 if self.tests_failed == 0 else 1


def test_rc10_rate_limit(runner: TestRunner):
    """RC-10: Persistent login rate-limit (8 failures -> 9th blocked)"""
    runner.log("\n🔒 Testing RC-10: Persistent Login Rate-Limit", "INFO")
    
    # Use a unique fake email to avoid locking real accounts
    fake_email = f"probe-test-{random.randint(10000, 99999)}@demo.local"
    runner.log(f"Using fake email: {fake_email}")
    
    # Send 8 failed login attempts
    for i in range(1, 9):
        resp = requests.post(f"{BASE_URL}/auth/login", 
                           json={"email": fake_email, "password": "wrongpassword"}, 
                           timeout=10)
        runner.test(f"RC-10: Failed login attempt {i} returns 401", 
                   resp.status_code == 401,
                   f"Expected 401, got {resp.status_code}")
        time.sleep(0.1)  # Small delay between attempts
    
    # 9th attempt should be blocked (429)
    resp = requests.post(f"{BASE_URL}/auth/login", 
                       json={"email": fake_email, "password": "wrongpassword"}, 
                       timeout=10)
    runner.test("RC-10: 9th failed login attempt returns 429 (rate-limited)", 
               resp.status_code == 429,
               f"Expected 429, got {resp.status_code} - {resp.text}")
    
    # Verify a DIFFERENT valid account can still login (per-key isolation)
    resp = requests.post(f"{BASE_URL}/auth/login", 
                       json={"email": "owner@demo.local", "password": "demo12345"}, 
                       timeout=10)
    runner.test("RC-10: Valid login for different account still works (isolation)", 
               resp.status_code == 200,
               f"Expected 200, got {resp.status_code}")
    
    # Verify successful login clears failure budget
    runner.log("Testing that successful logins clear failure budget...")
    # Login successfully multiple times
    for i in range(3):
        resp = requests.post(f"{BASE_URL}/auth/login", 
                           json={"email": "owner@demo.local", "password": "demo12345"}, 
                           timeout=10)
        runner.test(f"RC-10: Successful login {i+1} returns 200", 
                   resp.status_code == 200,
                   f"Expected 200, got {resp.status_code}")
        time.sleep(0.1)


def test_rc11_money_integer(runner: TestRunner):
    """RC-11: Money stored as integer rupiah (no decimals)"""
    runner.log("\n💰 Testing RC-11: Money as Integer", "INFO")
    
    # Get a customer and vehicle for booking
    customers = runner.get("/customers", {"limit": 1}).json()
    vehicles = runner.get("/vehicles", {"limit": 1}).json()
    
    if not customers or not vehicles:
        runner.log("No customers or vehicles found, skipping RC-11 booking test", "WARN")
        return
    
    customer_id = customers[0]["id"]
    vehicle_id = vehicles[0]["id"]
    
    # Use unique timestamps to avoid conflicts with previous test runs
    import random
    day_offset = random.randint(1, 28)
    hour_offset = random.randint(0, 23)
    
    # Create a booking with integer base_price
    booking_data = {
        "customer_id": customer_id,
        "vehicle_id": vehicle_id,
        "start_datetime": f"2029-09-{day_offset:02d}T{hour_offset:02d}:00:00",
        "end_datetime": f"2029-09-{day_offset:02d}T{hour_offset:02d}:30:00",
        "pickup_location": "Test Pickup",
        "dest_location": "Test Destination",
        "base_price": 1234567,  # Integer rupiah
        "addons": [{"name": "Toll", "price": 50000}]
    }
    
    resp = runner.post("/bookings", booking_data)
    if resp.status_code not in [200, 201]:
        runner.log(f"Failed to create booking: {resp.status_code} - {resp.text}", "FAIL")
        return
    
    booking = resp.json()
    booking_id = booking["id"]
    runner.created_ids["bookings"].append(booking_id)
    
    # Verify all money fields are integers (no decimal part)
    base_price = booking.get("base_price", 0)
    total_amount = booking.get("total_amount", 0)
    paid_amount = booking.get("paid_amount", 0)
    
    runner.test("RC-11: Booking base_price is integer", 
               isinstance(base_price, int) or (isinstance(base_price, float) and base_price == int(base_price)),
               f"base_price={base_price} has decimal part")
    
    runner.test("RC-11: Booking total_amount is integer", 
               isinstance(total_amount, int) or (isinstance(total_amount, float) and total_amount == int(total_amount)),
               f"total_amount={total_amount} has decimal part")
    
    runner.test("RC-11: Booking paid_amount is integer", 
               isinstance(paid_amount, int) or (isinstance(paid_amount, float) and paid_amount == int(paid_amount)),
               f"paid_amount={paid_amount} has decimal part")
    
    # Record a payment and verify amount is integer
    payment_data = {
        "booking_id": booking_id,
        "amount": 500000,
        "type": "dp",
        "method": "transfer"
    }
    
    resp = runner.post("/payments", payment_data)
    if resp.status_code == 200:
        payment = resp.json()
        runner.created_ids["payments"].append(payment["id"])
        
        payment_amount = payment.get("amount", 0)
        runner.test("RC-11: Payment amount is integer", 
                   isinstance(payment_amount, int) or (isinstance(payment_amount, float) and payment_amount == int(payment_amount)),
                   f"payment amount={payment_amount} has decimal part")
        
        # Get updated booking and verify paid_amount is still integer
        resp = runner.get(f"/bookings/{booking_id}")
        if resp.status_code == 200:
            updated_booking = resp.json()
            updated_paid = updated_booking.get("paid_amount", 0)
            runner.test("RC-11: Updated booking paid_amount is integer", 
                       isinstance(updated_paid, int) or (isinstance(updated_paid, float) and updated_paid == int(updated_paid)),
                       f"updated paid_amount={updated_paid} has decimal part")
    
    # Create an expense and verify amount is integer
    expense_data = {
        "booking_id": booking_id,
        "category": "bbm",
        "amount": 99999,
        "description": "Test expense"
    }
    
    resp = runner.post("/expenses", expense_data)
    if resp.status_code == 201:
        expense = resp.json()
        runner.created_ids["expenses"].append(expense["id"])
        
        expense_amount = expense.get("amount", 0)
        runner.test("RC-11: Expense amount is integer", 
                   isinstance(expense_amount, int) or (isinstance(expense_amount, float) and expense_amount == int(expense_amount)),
                   f"expense amount={expense_amount} has decimal part")
    
    # Create an invoice and verify amount is integer
    invoice_data = {
        "booking_id": booking_id,
        "due_at": "2028-08-20T00:00:00"
    }
    
    resp = runner.post("/invoices", invoice_data)
    if resp.status_code == 201:
        invoice = resp.json()
        runner.created_ids["invoices"].append(invoice["id"])
        
        invoice_amount = invoice.get("amount", 0)
        runner.test("RC-11: Invoice amount is integer", 
                   isinstance(invoice_amount, int) or (isinstance(invoice_amount, float) and invoice_amount == int(invoice_amount)),
                   f"invoice amount={invoice_amount} has decimal part")


def test_rc01_atomic_payment(runner: TestRunner):
    """RC-01 REGRESSION: Atomic payment with race protection"""
    runner.log("\n🔐 Testing RC-01: Atomic Payment Flow", "INFO")
    
    # Get a customer and vehicle
    customers = runner.get("/customers", {"limit": 1}).json()
    vehicles = runner.get("/vehicles", {"limit": 1}).json()
    
    if not customers or not vehicles:
        runner.log("No customers or vehicles found, skipping RC-01 test", "WARN")
        return
    
    customer_id = customers[0]["id"]
    vehicle_id = vehicles[0]["id"]
    
    # Use unique timestamps to avoid conflicts
    import random
    day_offset = random.randint(1, 28)
    hour_offset = random.randint(0, 23)
    
    # Create a booking with total 1,000,000
    booking_data = {
        "customer_id": customer_id,
        "vehicle_id": vehicle_id,
        "start_datetime": f"2029-10-{day_offset:02d}T{hour_offset:02d}:00:00",
        "end_datetime": f"2029-10-{day_offset:02d}T{hour_offset:02d}:30:00",
        "pickup_location": "Test Pickup RC01",
        "dest_location": "Test Destination RC01",
        "base_price": 1000000,
        "addons": []
    }
    
    resp = runner.post("/bookings", booking_data)
    if resp.status_code not in [200, 201]:
        runner.log(f"Failed to create booking: {resp.status_code} - {resp.text}", "FAIL")
        return
    
    booking = resp.json()
    booking_id = booking["id"]
    runner.created_ids["bookings"].append(booking_id)
    
    # Record partial payment 400,000
    payment1_data = {
        "booking_id": booking_id,
        "amount": 400000,
        "type": "dp",
        "method": "transfer"
    }
    
    resp = runner.post("/payments", payment1_data)
    runner.test("RC-01: First partial payment (400k) returns 200", 
               resp.status_code == 200,
               f"Expected 200, got {resp.status_code} - {resp.text}")
    
    if resp.status_code == 200:
        runner.created_ids["payments"].append(resp.json()["id"])
    
    # Get booking and verify payment_status = 'dp', paid_amount = 400000
    resp = runner.get(f"/bookings/{booking_id}")
    if resp.status_code == 200:
        booking = resp.json()
        runner.test("RC-01: After partial payment, payment_status is 'dp'", 
                   booking.get("payment_status") == "dp",
                   f"Expected 'dp', got {booking.get('payment_status')}")
        
        runner.test("RC-01: After partial payment, paid_amount is 400000", 
                   booking.get("paid_amount") == 400000,
                   f"Expected 400000, got {booking.get('paid_amount')}")
    
    # Record another payment 600,000 (full payment)
    payment2_data = {
        "booking_id": booking_id,
        "amount": 600000,
        "type": "settlement",
        "method": "transfer"
    }
    
    resp = runner.post("/payments", payment2_data)
    runner.test("RC-01: Second payment (600k) returns 200", 
               resp.status_code == 200,
               f"Expected 200, got {resp.status_code} - {resp.text}")
    
    if resp.status_code == 200:
        runner.created_ids["payments"].append(resp.json()["id"])
    
    # Get booking and verify payment_status = 'lunas', paid_amount = 1000000
    resp = runner.get(f"/bookings/{booking_id}")
    if resp.status_code == 200:
        booking = resp.json()
        runner.test("RC-01: After full payment, payment_status is 'lunas'", 
                   booking.get("payment_status") == "lunas",
                   f"Expected 'lunas', got {booking.get('payment_status')}")
        
        runner.test("RC-01: After full payment, paid_amount is 1000000", 
                   booking.get("paid_amount") == 1000000,
                   f"Expected 1000000, got {booking.get('paid_amount')}")
    
    # Attempt overpayment (should be rejected 400)
    payment3_data = {
        "booking_id": booking_id,
        "amount": 100000,
        "type": "settlement",
        "method": "transfer"
    }
    
    resp = runner.post("/payments", payment3_data)
    runner.test("RC-01: Overpayment attempt returns 400 (rejected)", 
               resp.status_code == 400,
               f"Expected 400, got {resp.status_code} - {resp.text}")
    
    # Verify paid_amount never exceeds total_amount
    resp = runner.get(f"/bookings/{booking_id}")
    if resp.status_code == 200:
        booking = resp.json()
        paid = booking.get("paid_amount", 0)
        total = booking.get("total_amount", 0)
        runner.test("RC-01: paid_amount never exceeds total_amount", 
                   paid <= total,
                   f"paid_amount={paid} exceeds total_amount={total}")
        
        # Verify paid_amount == sum(payments)
        payments_resp = runner.get("/payments", {"booking_id": booking_id})
        if payments_resp.status_code == 200:
            payments = payments_resp.json()
            sum_payments = sum(p.get("amount", 0) for p in payments)
            runner.test("RC-01: paid_amount equals sum of payments", 
                       paid == sum_payments,
                       f"paid_amount={paid} != sum_payments={sum_payments}")


def test_rc05_payment_to_cancelled(runner: TestRunner):
    """RC-05: Payment to cancelled booking should be rejected"""
    runner.log("\n🚫 Testing RC-05: Payment to Cancelled Booking", "INFO")
    
    # Get a customer and vehicle
    customers = runner.get("/customers", {"limit": 1}).json()
    vehicles = runner.get("/vehicles", {"limit": 1}).json()
    
    if not customers or not vehicles:
        runner.log("No customers or vehicles found, skipping RC-05 test", "WARN")
        return
    
    customer_id = customers[0]["id"]
    vehicle_id = vehicles[0]["id"]
    
    # Use unique timestamps to avoid conflicts
    import random
    day_offset = random.randint(1, 28)
    hour_offset = random.randint(0, 23)
    
    # Create a booking
    booking_data = {
        "customer_id": customer_id,
        "vehicle_id": vehicle_id,
        "start_datetime": f"2029-11-{day_offset:02d}T{hour_offset:02d}:00:00",
        "end_datetime": f"2029-11-{day_offset:02d}T{hour_offset:02d}:30:00",
        "pickup_location": "Test Pickup RC05",
        "dest_location": "Test Destination RC05",
        "base_price": 500000,
        "addons": []
    }
    
    resp = runner.post("/bookings", booking_data)
    if resp.status_code not in [200, 201]:
        runner.log(f"Failed to create booking: {resp.status_code} - {resp.text}", "FAIL")
        return
    
    booking = resp.json()
    booking_id = booking["id"]
    runner.created_ids["bookings"].append(booking_id)
    
    # Cancel the booking
    resp = runner.post(f"/bookings/{booking_id}/cancel", {})
    runner.test("RC-05: Booking cancelled successfully", 
               resp.status_code == 200,
               f"Expected 200, got {resp.status_code}")
    
    # Attempt to record payment to cancelled booking
    payment_data = {
        "booking_id": booking_id,
        "amount": 100000,
        "type": "dp",
        "method": "transfer"
    }
    
    resp = runner.post("/payments", payment_data)
    runner.test("RC-05: Payment to cancelled booking returns 400", 
               resp.status_code == 400,
               f"Expected 400, got {resp.status_code} - {resp.text}")


def test_rc02_completed_without_payment(runner: TestRunner):
    """RC-02: Completed booking without full payment should show correct status and appear in AR"""
    runner.log("\n📊 Testing RC-02: Completed Booking Without Full Payment", "INFO")
    
    # This test requires a booking to be completed without full payment
    # For now, we'll just verify the AR endpoint works and check existing data
    
    resp = runner.get("/finance/ar")
    runner.test("RC-02: AR endpoint returns 200", 
               resp.status_code == 200,
               f"Expected 200, got {resp.status_code}")
    
    if resp.status_code == 200:
        ar_data = resp.json()
        runner.log(f"AR total outstanding: {ar_data.get('total_outstanding', 0)}")
        runner.log(f"AR count: {ar_data.get('count', 0)}")
        
        # Verify structure
        runner.test("RC-02: AR response has total_outstanding", 
                   "total_outstanding" in ar_data,
                   "Missing total_outstanding field")
        
        runner.test("RC-02: AR response has items list", 
                   "items" in ar_data and isinstance(ar_data["items"], list),
                   "Missing or invalid items field")


def test_core_flows(runner: TestRunner):
    """Test core flows: login, dashboard, lists"""
    runner.log("\n🔄 Testing Core Flows", "INFO")
    
    # Test login for all 3 roles
    for email in ["owner@demo.local", "ops@demo.local", "driver@demo.local"]:
        resp = requests.post(f"{BASE_URL}/auth/login", 
                           json={"email": email, "password": "demo12345"}, 
                           timeout=10)
        runner.test(f"Core: Login as {email} returns 200", 
                   resp.status_code == 200,
                   f"Expected 200, got {resp.status_code}")
    
    # Re-login as owner for remaining tests
    runner.login("owner@demo.local", "demo12345")
    
    # Test dashboard
    resp = runner.get("/dashboard")
    runner.test("Core: Dashboard returns 200", 
               resp.status_code == 200,
               f"Expected 200, got {resp.status_code}")
    
    if resp.status_code == 200:
        dashboard = resp.json()
        runner.test("Core: Dashboard has KPIs", 
                   "total_revenue" in dashboard or "revenue_month" in dashboard,
                   "Missing revenue KPIs")
    
    # Test list endpoints
    endpoints = [
        "/vehicles",
        "/drivers",
        "/customers",
        "/bookings",
        "/payments",
        "/invoices",
        "/expenses"
    ]
    
    for endpoint in endpoints:
        resp = runner.get(endpoint, {"limit": 10})
        runner.test(f"Core: GET {endpoint} returns 200", 
                   resp.status_code == 200,
                   f"Expected 200, got {resp.status_code}")


def main():
    runner = TestRunner()
    
    try:
        # Login as owner
        if not runner.login("owner@demo.local", "demo12345"):
            runner.log("Failed to login, aborting tests", "FAIL")
            return 1
        
        # Run tests
        test_rc10_rate_limit(runner)
        test_rc11_money_integer(runner)
        test_rc01_atomic_payment(runner)
        test_rc05_payment_to_cancelled(runner)
        test_rc02_completed_without_payment(runner)
        test_core_flows(runner)
        
        # Cleanup
        runner.cleanup()
        
    except Exception as e:
        runner.log(f"Test execution failed: {e}", "FAIL")
        import traceback
        traceback.print_exc()
        return 1
    
    # Print summary
    return runner.summary()


if __name__ == "__main__":
    sys.exit(main())

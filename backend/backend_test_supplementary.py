"""
Supplementary tests for RC-11 (expenses, invoices, payroll) and regressions
"""
import requests
import sys
import random
from datetime import datetime, timedelta

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

class SupplementaryTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.token = None
        self.errors = []

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
        resp = requests.post(f"{BASE_URL}/auth/login", 
                           json={"email": email, "password": password}, 
                           timeout=10)
        if resp.status_code == 200:
            self.token = resp.json().get("token")
            return True
        return False

    def get(self, endpoint: str, params: dict = None):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        return requests.get(f"{BASE_URL}{endpoint}", headers=headers, params=params, timeout=10)

    def post(self, endpoint: str, data: dict):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        return requests.post(f"{BASE_URL}{endpoint}", headers=headers, json=data, timeout=10)

    def summary(self):
        print("\n" + "="*60)
        print(f"📊 SUPPLEMENTARY TEST SUMMARY")
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


def test_rc11_expenses_invoices(tester: SupplementaryTester):
    """RC-11: Test expenses and invoices have integer amounts"""
    tester.log("\n💰 Testing RC-11: Expenses and Invoices Integer Amounts", "INFO")
    
    # Get a booking to attach expense/invoice
    bookings = tester.get("/bookings", {"limit": 1}).json()
    if not bookings:
        tester.log("No bookings found, skipping expense/invoice test", "WARN")
        return
    
    booking_id = bookings[0]["id"]
    
    # Test expense with fractional amount
    expense_data = {
        "booking_id": booking_id,
        "category": "bbm",
        "amount": 99999.7,  # Fractional amount
        "note": "Test expense RC-11"
    }
    
    resp = tester.post("/expenses", expense_data)
    if resp.status_code in [200, 201]:
        expense = resp.json()
        expense_amount = expense.get("amount", 0)
        tester.test("RC-11: Expense amount is integer", 
                   isinstance(expense_amount, int) or (isinstance(expense_amount, float) and expense_amount == int(expense_amount)),
                   f"expense amount={expense_amount} has decimal part")
        
        # Verify it's rounded correctly (99999.7 -> 100000)
        tester.test("RC-11: Expense amount rounded correctly", 
                   expense_amount == 100000,
                   f"Expected 100000, got {expense_amount}")
    else:
        tester.log(f"Failed to create expense: {resp.status_code} - {resp.text}", "WARN")
    
    # Test invoice with fractional amount
    invoice_data = {
        "booking_id": booking_id,
        "amount": 1234567.3,  # Fractional amount
        "due_at": (datetime.now() + timedelta(days=7)).isoformat()
    }
    
    resp = tester.post("/invoices", invoice_data)
    if resp.status_code in [200, 201]:
        invoice = resp.json()
        invoice_amount = invoice.get("amount", 0)
        tester.test("RC-11: Invoice amount is integer", 
                   isinstance(invoice_amount, int) or (isinstance(invoice_amount, float) and invoice_amount == int(invoice_amount)),
                   f"invoice amount={invoice_amount} has decimal part")
        
        # Verify it's rounded correctly (1234567.3 -> 1234567)
        tester.test("RC-11: Invoice amount rounded correctly", 
                   invoice_amount == 1234567,
                   f"Expected 1234567, got {invoice_amount}")
    else:
        tester.log(f"Failed to create invoice: {resp.status_code} - {resp.text}", "WARN")


def test_anti_double_booking(tester: SupplementaryTester):
    """Test anti-double-booking (same vehicle, overlapping time)"""
    tester.log("\n🚫 Testing Anti-Double-Booking", "INFO")
    
    customers = tester.get("/customers", {"limit": 1}).json()
    vehicles = tester.get("/vehicles", {"limit": 1}).json()
    
    if not customers or not vehicles:
        tester.log("No customers or vehicles found, skipping anti-double-booking test", "WARN")
        return
    
    customer_id = customers[0]["id"]
    vehicle_id = vehicles[0]["id"]
    
    # Create first booking
    day = random.randint(1, 28)
    booking1_data = {
        "customer_id": customer_id,
        "vehicle_id": vehicle_id,
        "start_datetime": f"2029-12-{day:02d}T10:00:00",
        "end_datetime": f"2029-12-{day:02d}T14:00:00",
        "pickup_location": "Test Pickup 1",
        "dest_location": "Test Destination 1",
        "base_price": 500000,
        "addons": []
    }
    
    resp1 = tester.post("/bookings", booking1_data)
    if resp1.status_code not in [200, 201]:
        tester.log(f"Failed to create first booking: {resp1.status_code}", "WARN")
        return
    
    booking1 = resp1.json()
    tester.log(f"Created first booking: {booking1['code']}")
    
    # Try to create overlapping booking (should fail)
    booking2_data = {
        "customer_id": customer_id,
        "vehicle_id": vehicle_id,  # Same vehicle
        "start_datetime": f"2029-12-{day:02d}T12:00:00",  # Overlaps with first booking
        "end_datetime": f"2029-12-{day:02d}T16:00:00",
        "pickup_location": "Test Pickup 2",
        "dest_location": "Test Destination 2",
        "base_price": 500000,
        "addons": []
    }
    
    resp2 = tester.post("/bookings", booking2_data)
    tester.test("Anti-double-booking: Overlapping booking rejected with 400", 
               resp2.status_code == 400,
               f"Expected 400, got {resp2.status_code}")
    
    if resp2.status_code == 400:
        detail = resp2.json().get("detail", "")
        tester.test("Anti-double-booking: Error message mentions conflict", 
                   "bentrok" in detail.lower() or "conflict" in detail.lower(),
                   f"Error message: {detail}")


def test_driver_double_assign(tester: SupplementaryTester):
    """RC-07: Test driver double-assign prevention"""
    tester.log("\n🚫 Testing RC-07: Driver Double-Assign Prevention", "INFO")
    
    customers = tester.get("/customers", {"limit": 1}).json()
    vehicles = tester.get("/vehicles", {"limit": 2}).json()
    drivers = tester.get("/drivers", {"limit": 1}).json()
    
    if not customers or len(vehicles) < 2 or not drivers:
        tester.log("Insufficient data for driver double-assign test", "WARN")
        return
    
    customer_id = customers[0]["id"]
    vehicle1_id = vehicles[0]["id"]
    vehicle2_id = vehicles[1]["id"]
    driver_id = drivers[0]["id"]
    
    # Create first booking with driver
    day = random.randint(1, 28)
    booking1_data = {
        "customer_id": customer_id,
        "vehicle_id": vehicle1_id,
        "driver_id": driver_id,  # Assign driver
        "start_datetime": f"2030-01-{day:02d}T10:00:00",
        "end_datetime": f"2030-01-{day:02d}T14:00:00",
        "pickup_location": "Test Pickup 1",
        "dest_location": "Test Destination 1",
        "base_price": 500000,
        "addons": []
    }
    
    resp1 = tester.post("/bookings", booking1_data)
    if resp1.status_code not in [200, 201]:
        tester.log(f"Failed to create first booking: {resp1.status_code}", "WARN")
        return
    
    booking1 = resp1.json()
    tester.log(f"Created first booking with driver: {booking1['code']}")
    
    # Try to create overlapping booking with same driver (different vehicle)
    booking2_data = {
        "customer_id": customer_id,
        "vehicle_id": vehicle2_id,  # Different vehicle
        "driver_id": driver_id,  # Same driver
        "start_datetime": f"2030-01-{day:02d}T12:00:00",  # Overlaps
        "end_datetime": f"2030-01-{day:02d}T16:00:00",
        "pickup_location": "Test Pickup 2",
        "dest_location": "Test Destination 2",
        "base_price": 500000,
        "addons": []
    }
    
    resp2 = tester.post("/bookings", booking2_data)
    tester.test("RC-07: Driver double-assign rejected with 400", 
               resp2.status_code == 400,
               f"Expected 400, got {resp2.status_code}")
    
    if resp2.status_code == 400:
        detail = resp2.json().get("detail", "")
        tester.test("RC-07: Error message mentions driver conflict", 
                   "driver" in detail.lower() and "bentrok" in detail.lower(),
                   f"Error message: {detail}")


def main():
    tester = SupplementaryTester()
    
    try:
        if not tester.login("owner@demo.local", "demo12345"):
            tester.log("Failed to login", "FAIL")
            return 1
        
        tester.log("✅ Login successful")
        
        # Run supplementary tests
        test_rc11_expenses_invoices(tester)
        test_anti_double_booking(tester)
        test_driver_double_assign(tester)
        
    except Exception as e:
        tester.log(f"Test execution failed: {e}", "FAIL")
        import traceback
        traceback.print_exc()
        return 1
    
    return tester.summary()


if __name__ == "__main__":
    sys.exit(main())

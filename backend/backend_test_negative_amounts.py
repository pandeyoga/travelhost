"""
Backend Test: Negative Amount Fix Verification (INV-1 Data Integrity)

Tests the schema-level fix (Field ge=0) that prevents negative line-item amounts
from producing negative total_amount on bookings/quotations.

Fix: schemas.py AddOn.amount and QuotationItemIn.amount now use Field(ge=0)
Expected: Negative amounts rejected with HTTP 422 (pydantic validation)
"""
import requests
import sys
from datetime import datetime, timedelta

class NegativeAmountTester:
    def __init__(self, base_url="https://trip-route-buttons.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failed_tests = []
        
        # Test data IDs (will be populated during setup)
        self.customer_id = None
        self.vehicle_id = None
        self.driver_id = None

    def log(self, message, level="INFO"):
        """Log test messages"""
        prefix = {
            "INFO": "ℹ️",
            "PASS": "✅",
            "FAIL": "❌",
            "WARN": "⚠️"
        }.get(level, "•")
        print(f"{prefix} {message}")

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        if headers is None:
            headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        self.log(f"Testing: {name}", "INFO")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=headers, timeout=10)
            else:
                self.log(f"Unsupported method: {method}", "FAIL")
                self.tests_failed += 1
                self.failed_tests.append(name)
                return False, {}

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"PASS - Status: {response.status_code}", "PASS")
            else:
                self.tests_failed += 1
                self.failed_tests.append(name)
                self.log(f"FAIL - Expected {expected_status}, got {response.status_code}", "FAIL")
                try:
                    self.log(f"Response: {response.json()}", "FAIL")
                except Exception:
                    self.log(f"Response text: {response.text[:200]}", "FAIL")

            try:
                return success, response.json() if response.text else {}
            except Exception:
                return success, {}

        except Exception as e:
            self.tests_failed += 1
            self.failed_tests.append(name)
            self.log(f"FAIL - Error: {str(e)}", "FAIL")
            return False, {}

    def test_login(self):
        """Test login and get token"""
        self.log("\n=== SETUP: Authentication ===", "INFO")
        success, response = self.run_test(
            "Login as owner",
            "POST",
            "auth/login",
            200,
            data={"email": "owner@demo.local", "password": "demo12345"}
        )
        if success and 'token' in response:
            self.token = response['token']
            self.log(f"Token obtained: {self.token[:20]}...", "PASS")
            return True
        self.log("Login failed - cannot proceed", "FAIL")
        return False

    def setup_test_data(self):
        """Get existing customer, vehicle, driver IDs for testing"""
        self.log("\n=== SETUP: Get Test Data IDs ===", "INFO")
        
        # Get a customer
        success, response = self.run_test(
            "Get customers list",
            "GET",
            "customers?limit=1",
            200
        )
        if success and response and len(response) > 0:
            self.customer_id = response[0]['id']
            self.log(f"Using customer_id: {self.customer_id}", "PASS")
        else:
            self.log("No customers found - cannot proceed", "FAIL")
            return False

        # Get a vehicle
        success, response = self.run_test(
            "Get vehicles list",
            "GET",
            "vehicles?limit=1",
            200
        )
        if success and response and len(response) > 0:
            self.vehicle_id = response[0]['id']
            self.log(f"Using vehicle_id: {self.vehicle_id}", "PASS")
        else:
            self.log("No vehicles found - cannot proceed", "FAIL")
            return False

        # Get a driver (optional)
        success, response = self.run_test(
            "Get drivers list",
            "GET",
            "drivers?limit=1",
            200
        )
        if success and response and len(response) > 0:
            self.driver_id = response[0]['id']
            self.log(f"Using driver_id: {self.driver_id}", "PASS")

        return True

    def test_negative_booking_addon(self):
        """PRIMARY FIX: POST /api/bookings with negative add_on → 422"""
        self.log("\n=== PRIMARY FIX: Negative Booking Add-on ===", "INFO")
        
        start = (datetime.now() + timedelta(days=10)).isoformat()
        end = (datetime.now() + timedelta(days=12)).isoformat()
        
        data = {
            "customer_id": self.customer_id,
            "vehicle_id": self.vehicle_id,
            "start_datetime": start,
            "end_datetime": end,
            "base_price": 2000000,
            "add_ons": [
                {"label": "Malicious negative addon", "amount": -99000000}
            ]
        }
        
        success, response = self.run_test(
            "Booking with NEGATIVE add_on (should reject with 422)",
            "POST",
            "bookings",
            422,  # Expected: validation error
            data=data
        )
        
        if success:
            self.log("✓ Negative add_on correctly rejected", "PASS")
        else:
            self.log("✗ CRITICAL: Negative add_on was NOT rejected!", "FAIL")
        
        return success

    def test_negative_group_booking_addon(self):
        """PRIMARY FIX: POST /api/bookings/group with negative add_on → 422"""
        self.log("\n=== PRIMARY FIX: Negative Group Booking Add-on ===", "INFO")
        
        start = (datetime.now() + timedelta(days=15)).isoformat()
        end = (datetime.now() + timedelta(days=17)).isoformat()
        
        data = {
            "customer_id": self.customer_id,
            "units": [
                {
                    "vehicle_id": self.vehicle_id,
                    "start_datetime": start,
                    "end_datetime": end,
                    "base_price": 2000000,
                    "add_ons": [
                        {"label": "Negative addon in group", "amount": -50000000}
                    ]
                }
            ]
        }
        
        success, response = self.run_test(
            "Group booking with NEGATIVE add_on (should reject with 422)",
            "POST",
            "bookings/group",
            422,
            data=data
        )
        
        if success:
            self.log("✓ Negative group add_on correctly rejected", "PASS")
        else:
            self.log("✗ CRITICAL: Negative group add_on was NOT rejected!", "FAIL")
        
        return success

    def test_negative_quotation_item(self):
        """PRIMARY FIX: POST /api/quotations with negative item → 422"""
        self.log("\n=== PRIMARY FIX: Negative Quotation Item ===", "INFO")
        
        data = {
            "customer_name": "Test Customer",
            "phone": "081234567890",
            "destination": "Bandung",
            "items": [
                {"label": "Base fare", "amount": 2000000},
                {"label": "Negative item", "amount": -1000000}
            ]
        }
        
        success, response = self.run_test(
            "Quotation with NEGATIVE item (should reject with 422)",
            "POST",
            "quotations",
            422,
            data=data
        )
        
        if success:
            self.log("✓ Negative quotation item correctly rejected", "PASS")
        else:
            self.log("✗ CRITICAL: Negative quotation item was NOT rejected!", "FAIL")
        
        return success

    def test_negative_quotation_update(self):
        """PRIMARY FIX: PATCH /api/quotations/{id} with negative item → 422"""
        self.log("\n=== PRIMARY FIX: Negative Quotation Update ===", "INFO")
        
        # First create a valid quotation
        create_data = {
            "customer_name": "Test Customer Update",
            "phone": "081234567891",
            "destination": "Jakarta",
            "items": [
                {"label": "Base fare", "amount": 2000000}
            ]
        }
        
        success, response = self.run_test(
            "Create quotation for update test",
            "POST",
            "quotations",
            200,
            data=create_data
        )
        
        if not success or 'id' not in response:
            self.log("Failed to create quotation for update test", "FAIL")
            return False
        
        quotation_id = response['id']
        self.log(f"Created quotation {quotation_id} for update test", "PASS")
        
        # Now try to update with negative item
        update_data = {
            "items": [
                {"label": "Base fare", "amount": 2000000},
                {"label": "Negative update", "amount": -500000}
            ]
        }
        
        success, response = self.run_test(
            "Update quotation with NEGATIVE item (should reject with 422)",
            "PATCH",
            f"quotations/{quotation_id}",
            422,
            data=update_data
        )
        
        if success:
            self.log("✓ Negative quotation update correctly rejected", "PASS")
        else:
            self.log("✗ CRITICAL: Negative quotation update was NOT rejected!", "FAIL")
        
        return success

    def test_positive_booking_addon(self):
        """REGRESSION: POST /api/bookings with POSITIVE add_on → 200 with correct total"""
        self.log("\n=== REGRESSION: Positive Booking Add-on ===", "INFO")
        
        start = (datetime.now() + timedelta(days=20)).isoformat()
        end = (datetime.now() + timedelta(days=22)).isoformat()
        
        base_price = 2000000
        addon_amount = 150000
        expected_total = base_price + addon_amount
        
        data = {
            "customer_id": self.customer_id,
            "vehicle_id": self.vehicle_id,
            "start_datetime": start,
            "end_datetime": end,
            "base_price": base_price,
            "add_ons": [
                {"label": "Airport pickup", "amount": addon_amount}
            ]
        }
        
        success, response = self.run_test(
            "Booking with POSITIVE add_on (should succeed with 200)",
            "POST",
            "bookings",
            200,
            data=data
        )
        
        if success:
            actual_total = response.get('total_amount', 0)
            if actual_total == expected_total:
                self.log(f"✓ Total amount correct: {actual_total} == {expected_total}", "PASS")
            else:
                self.log(f"✗ Total amount INCORRECT: {actual_total} != {expected_total}", "FAIL")
                self.tests_failed += 1
                self.failed_tests.append("Positive booking total calculation")
                success = False
        
        return success

    def test_zero_amount_addon(self):
        """REGRESSION: Zero amount add_on is allowed (ge=0 permits 0)"""
        self.log("\n=== REGRESSION: Zero Amount Add-on ===", "INFO")
        
        start = (datetime.now() + timedelta(days=25)).isoformat()
        end = (datetime.now() + timedelta(days=27)).isoformat()
        
        data = {
            "customer_id": self.customer_id,
            "vehicle_id": self.vehicle_id,
            "start_datetime": start,
            "end_datetime": end,
            "base_price": 2000000,
            "add_ons": [
                {"label": "Free service", "amount": 0}
            ]
        }
        
        success, response = self.run_test(
            "Booking with ZERO add_on (should succeed with 200)",
            "POST",
            "bookings",
            200,
            data=data
        )
        
        if success:
            self.log("✓ Zero amount add_on correctly allowed", "PASS")
        
        return success

    def test_booking_without_addons(self):
        """REGRESSION: Booking without add_ons works"""
        self.log("\n=== REGRESSION: Booking Without Add-ons ===", "INFO")
        
        start = (datetime.now() + timedelta(days=30)).isoformat()
        end = (datetime.now() + timedelta(days=32)).isoformat()
        
        data = {
            "customer_id": self.customer_id,
            "vehicle_id": self.vehicle_id,
            "start_datetime": start,
            "end_datetime": end,
            "base_price": 2000000
        }
        
        success, response = self.run_test(
            "Booking WITHOUT add_ons (should succeed with 200)",
            "POST",
            "bookings",
            200,
            data=data
        )
        
        return success

    def test_expense_negative_amount(self):
        """SANITY: POST /api/expenses still rejects amount<=0 with 422"""
        self.log("\n=== SANITY: Expense Negative Amount ===", "INFO")
        
        data = {
            "category": "bbm",
            "amount": -50000,
            "note": "Test negative expense"
        }
        
        success, response = self.run_test(
            "Expense with NEGATIVE amount (should reject with 422)",
            "POST",
            "expenses",
            422,
            data=data
        )
        
        if success:
            self.log("✓ Negative expense correctly rejected (Field gt=0 unchanged)", "PASS")
        
        return success

    def test_expense_zero_amount(self):
        """SANITY: POST /api/expenses rejects amount=0 with 422 (Field gt=0)"""
        self.log("\n=== SANITY: Expense Zero Amount ===", "INFO")
        
        data = {
            "category": "bbm",
            "amount": 0,
            "note": "Test zero expense"
        }
        
        success, response = self.run_test(
            "Expense with ZERO amount (should reject with 422, Field gt=0)",
            "POST",
            "expenses",
            422,
            data=data
        )
        
        if success:
            self.log("✓ Zero expense correctly rejected (Field gt=0 unchanged)", "PASS")
        
        return success

    def test_payment_negative_amount(self):
        """SANITY: POST /api/payments rejects amount<=0 with 422"""
        self.log("\n=== SANITY: Payment Negative Amount ===", "INFO")
        
        # First create a booking to get a booking_id
        start = (datetime.now() + timedelta(days=35)).isoformat()
        end = (datetime.now() + timedelta(days=37)).isoformat()
        
        booking_data = {
            "customer_id": self.customer_id,
            "vehicle_id": self.vehicle_id,
            "start_datetime": start,
            "end_datetime": end,
            "base_price": 2000000
        }
        
        success, response = self.run_test(
            "Create booking for payment test",
            "POST",
            "bookings",
            200,
            data=booking_data
        )
        
        if not success or 'id' not in response:
            self.log("Failed to create booking for payment test", "FAIL")
            return False
        
        booking_id = response['id']
        
        # Try to create payment with negative amount
        payment_data = {
            "booking_id": booking_id,
            "amount": -100000,
            "type": "dp"
        }
        
        success, response = self.run_test(
            "Payment with NEGATIVE amount (should reject with 422)",
            "POST",
            "payments",
            422,
            data=payment_data
        )
        
        if success:
            self.log("✓ Negative payment correctly rejected (Field gt=0 unchanged)", "PASS")
        
        return success

    def test_payment_zero_amount(self):
        """SANITY: POST /api/payments rejects amount=0 with 422 (Field gt=0)"""
        self.log("\n=== SANITY: Payment Zero Amount ===", "INFO")
        
        # Create a booking
        start = (datetime.now() + timedelta(days=40)).isoformat()
        end = (datetime.now() + timedelta(days=42)).isoformat()
        
        booking_data = {
            "customer_id": self.customer_id,
            "vehicle_id": self.vehicle_id,
            "start_datetime": start,
            "end_datetime": end,
            "base_price": 2000000
        }
        
        success, response = self.run_test(
            "Create booking for zero payment test",
            "POST",
            "bookings",
            200,
            data=booking_data
        )
        
        if not success or 'id' not in response:
            self.log("Failed to create booking for zero payment test", "FAIL")
            return False
        
        booking_id = response['id']
        
        # Try to create payment with zero amount
        payment_data = {
            "booking_id": booking_id,
            "amount": 0,
            "type": "dp"
        }
        
        success, response = self.run_test(
            "Payment with ZERO amount (should reject with 422, Field gt=0)",
            "POST",
            "payments",
            422,
            data=payment_data
        )
        
        if success:
            self.log("✓ Zero payment correctly rejected (Field gt=0 unchanged)", "PASS")
        
        return success

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "="*60, "INFO")
        self.log("TEST SUMMARY", "INFO")
        self.log("="*60, "INFO")
        self.log(f"Total tests run: {self.tests_run}", "INFO")
        self.log(f"Tests passed: {self.tests_passed}", "PASS")
        self.log(f"Tests failed: {self.tests_failed}", "FAIL" if self.tests_failed > 0 else "INFO")
        
        if self.tests_failed > 0:
            self.log("\nFailed tests:", "FAIL")
            for test in self.failed_tests:
                self.log(f"  - {test}", "FAIL")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\nSuccess rate: {success_rate:.1f}%", "INFO")
        
        return self.tests_failed == 0


def main():
    tester = NegativeAmountTester()
    
    print("\n" + "="*60)
    print("NEGATIVE AMOUNT FIX VERIFICATION TEST")
    print("Testing schema-level validation (Field ge=0)")
    print("="*60)
    
    # Setup
    if not tester.test_login():
        return 1
    
    if not tester.setup_test_data():
        return 1
    
    # PRIMARY FIX TESTS (negative amounts must be rejected with 422)
    tester.test_negative_booking_addon()
    tester.test_negative_group_booking_addon()
    tester.test_negative_quotation_item()
    tester.test_negative_quotation_update()
    
    # REGRESSION TESTS (positive paths must still work)
    tester.test_positive_booking_addon()
    tester.test_zero_amount_addon()
    tester.test_booking_without_addons()
    
    # SANITY TESTS (other validations unchanged)
    tester.test_expense_negative_amount()
    tester.test_expense_zero_amount()
    tester.test_payment_negative_amount()
    tester.test_payment_zero_amount()
    
    # Print summary
    all_passed = tester.print_summary()
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

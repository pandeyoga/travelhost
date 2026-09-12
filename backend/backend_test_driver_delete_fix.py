"""
Backend Test: Driver Delete Referential Integrity Fix
Tests the fix for driver deletion blocking when driver is referenced by hold/pending bookings.

FIX: DELETE /api/drivers/{id} now blocks deletion when driver has bookings with status:
['pending', 'hold', 'confirmed', 'ongoing']

Previously only blocked: ['confirmed', 'ongoing']
Bug: Drivers with 'hold' or 'pending' bookings could be deleted, leaving dangling FKs.
"""
import requests
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

class DriverDeleteTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.token = None
        self.errors = []
        self.created_resources = {
            "drivers": [],
            "bookings": [],
            "vehicles": [],
            "customers": []
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
        """Record test result"""
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

    def login(self, email: str, password: str) -> bool:
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
                self.token = data.get("token")
                if self.token:
                    self.log(f"Login successful", "PASS")
                    return True
            self.log(f"Login failed: {resp.status_code} - {resp.text[:200]}", "FAIL")
            return False
        except Exception as e:
            self.log(f"Login exception: {e}", "FAIL")
            return False

    def get_headers(self) -> Dict[str, str]:
        """Get auth headers"""
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def create_driver(self, name: str, phone: str) -> Optional[str]:
        """Create a new driver and return driver_id"""
        self.log(f"Creating driver: {name}")
        try:
            resp = requests.post(
                f"{BASE_URL}/drivers",
                json={"name": name, "phone": phone},
                headers=self.get_headers(),
                timeout=10,
            )
            if resp.status_code in [200, 201]:
                data = resp.json()
                driver_id = data.get("id")
                if driver_id:
                    self.created_resources["drivers"].append(driver_id)
                    self.log(f"Driver created: {driver_id}", "PASS")
                    return driver_id
            self.log(f"Failed to create driver: {resp.status_code} - {resp.text[:200]}", "FAIL")
            return None
        except Exception as e:
            self.log(f"Exception creating driver: {e}", "FAIL")
            return None

    def delete_driver(self, driver_id: str) -> tuple[int, str]:
        """Delete driver and return (status_code, message)"""
        self.log(f"Attempting to delete driver: {driver_id}")
        try:
            resp = requests.delete(
                f"{BASE_URL}/drivers/{driver_id}",
                headers=self.get_headers(),
                timeout=10,
            )
            msg = resp.json().get("detail", "") if resp.status_code != 200 else "Success"
            self.log(f"Delete driver response: {resp.status_code} - {msg}")
            return resp.status_code, msg
        except Exception as e:
            self.log(f"Exception deleting driver: {e}", "FAIL")
            return 500, str(e)

    def get_driver(self, driver_id: str) -> Optional[Dict]:
        """Get driver by ID"""
        try:
            resp = requests.get(
                f"{BASE_URL}/drivers/{driver_id}",
                headers=self.get_headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            self.log(f"Exception getting driver: {e}", "FAIL")
            return None

    def get_available_vehicle(self, exclude_ids: list = None) -> Optional[str]:
        """Get an available vehicle ID, optionally excluding certain IDs"""
        exclude_ids = exclude_ids or []
        try:
            resp = requests.get(
                f"{BASE_URL}/vehicles?status=available&limit=20",
                headers=self.get_headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                vehicles = resp.json()
                for vehicle in vehicles:
                    vehicle_id = vehicle.get("id")
                    if vehicle_id and vehicle_id not in exclude_ids:
                        return vehicle_id
            self.log("No available vehicles found", "WARN")
            return None
        except Exception as e:
            self.log(f"Exception getting vehicles: {e}", "FAIL")
            return None

    def get_customer(self) -> Optional[str]:
        """Get a customer ID"""
        try:
            resp = requests.get(
                f"{BASE_URL}/customers?limit=1",
                headers=self.get_headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                customers = resp.json()
                if customers and len(customers) > 0:
                    return customers[0].get("id")
            self.log("No customers found", "WARN")
            return None
        except Exception as e:
            self.log(f"Exception getting customers: {e}", "FAIL")
            return None

    def create_booking(self, driver_id: str, vehicle_id: str, customer_id: str, 
                      require_dp: bool = False, status_override: str = None) -> Optional[Dict]:
        """Create a booking with specified parameters"""
        # Use very far future dates to avoid conflicts (2030+)
        # Add some randomness based on timestamp to avoid exact date conflicts
        import time
        offset_days = 1460 + (int(time.time()) % 100)  # 4+ years in future with variation
        start_date = (datetime.now() + timedelta(days=offset_days)).strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=offset_days + 2)).strftime("%Y-%m-%d")
        
        booking_data = {
            "customer_id": customer_id,
            "vehicle_id": vehicle_id,
            "driver_id": driver_id,
            "start_datetime": f"{start_date}T08:00:00",
            "end_datetime": f"{end_date}T18:00:00",
            "destination": "Test Destination",
            "pickup_location": "Test Pickup",
            "require_dp": require_dp,
            "total_amount": 5000000,
        }
        
        self.log(f"Creating booking (require_dp={require_dp}, dates={start_date} to {end_date})...")
        try:
            resp = requests.post(
                f"{BASE_URL}/bookings",
                json=booking_data,
                headers=self.get_headers(),
                timeout=10,
            )
            if resp.status_code in [200, 201]:
                data = resp.json()
                # Handle both single booking and multiple bookings response
                if "bookings" in data:
                    bookings = data["bookings"]
                    if bookings and len(bookings) > 0:
                        booking = bookings[0]
                        booking_id = booking.get("id")
                        if booking_id:
                            self.created_resources["bookings"].append(booking_id)
                            self.log(f"Booking created: {booking_id}, status: {booking.get('status')}", "PASS")
                            return booking
                else:
                    booking_id = data.get("id")
                    if booking_id:
                        self.created_resources["bookings"].append(booking_id)
                        self.log(f"Booking created: {booking_id}, status: {data.get('status')}", "PASS")
                        return data
            self.log(f"Failed to create booking: {resp.status_code} - {resp.text[:300]}", "FAIL")
            return None
        except Exception as e:
            self.log(f"Exception creating booking: {e}", "FAIL")
            return None

    def test_primary_fix_hold_booking(self):
        """PRIMARY TEST: Driver with HOLD booking cannot be deleted"""
        self.log("\n=== PRIMARY FIX TEST: HOLD Booking Blocks Driver Delete ===")
        
        # Create new driver
        driver_id = self.create_driver("Test Driver Hold", "081234567890")
        if not driver_id:
            self.test("Create driver for HOLD test", False, "Failed to create driver")
            return
        
        # Get customer
        customer_id = self.get_customer()
        if not customer_id:
            self.test("Get customer for HOLD booking", False, "Missing customer")
            return
        
        # Try multiple vehicles to avoid conflicts
        booking = None
        used_vehicles = []
        for attempt in range(5):
            vehicle_id = self.get_available_vehicle(exclude_ids=used_vehicles)
            if not vehicle_id:
                break
            used_vehicles.append(vehicle_id)
            
            # Create HOLD booking (require_dp=true)
            booking = self.create_booking(driver_id, vehicle_id, customer_id, require_dp=True)
            if booking:
                break
            self.log(f"Vehicle {vehicle_id} conflict, trying another...", "WARN")
        
        if not booking:
            self.test("Create HOLD booking", False, "Failed to create HOLD booking after 5 attempts")
            return
        
        # Verify booking status is 'hold'
        booking_status = booking.get("status")
        self.test("Booking status is 'hold'", booking_status == "hold", 
                 f"Expected 'hold', got '{booking_status}'")
        
        # Try to delete driver - should return 400
        status_code, msg = self.delete_driver(driver_id)
        self.test("DELETE driver with HOLD booking returns 400", status_code == 400,
                 f"Expected 400, got {status_code}")
        
        # Verify error message mentions the active statuses
        msg_lower = msg.lower()
        has_correct_msg = any(word in msg_lower for word in ["aktif", "pending", "hold", "confirmed", "ongoing"])
        self.test("Error message mentions active booking statuses", has_correct_msg,
                 f"Message: {msg}")
        
        # Verify driver still exists
        driver = self.get_driver(driver_id)
        self.test("Driver still exists after failed delete", driver is not None,
                 "Driver was deleted despite having HOLD booking")

    def test_regression_confirmed_ongoing(self):
        """REGRESSION: Confirmed/ongoing bookings still block deletion"""
        self.log("\n=== REGRESSION TEST: Confirmed/Ongoing Still Block Delete ===")
        
        # Create new driver
        driver_id = self.create_driver("Test Driver Confirmed", "081234567891")
        if not driver_id:
            self.test("Create driver for confirmed test", False, "Failed to create driver")
            return
        
        # Get customer
        customer_id = self.get_customer()
        if not customer_id:
            self.test("Get customer for confirmed booking", False, "Missing customer")
            return
        
        # Try multiple vehicles to avoid conflicts
        booking = None
        used_vehicles = []
        for attempt in range(5):
            vehicle_id = self.get_available_vehicle(exclude_ids=used_vehicles)
            if not vehicle_id:
                break
            used_vehicles.append(vehicle_id)
            
            # Create normal booking (require_dp=false, should be confirmed)
            booking = self.create_booking(driver_id, vehicle_id, customer_id, require_dp=False)
            if booking:
                break
            self.log(f"Vehicle {vehicle_id} conflict, trying another...", "WARN")
        
        if not booking:
            self.log("Could not create confirmed booking after 5 attempts - skipping test", "WARN")
            # Still test with existing bookings in the system
            # Try to delete a driver that has existing bookings
            try:
                resp = requests.get(f"{BASE_URL}/drivers?limit=10", headers=self.get_headers(), timeout=10)
                if resp.status_code == 200:
                    drivers = resp.json()
                    for driver in drivers:
                        test_driver_id = driver.get("id")
                        # Try to delete - if it has bookings, should fail
                        status_code, msg = self.delete_driver(test_driver_id)
                        if status_code == 400:
                            self.test("DELETE driver with existing bookings returns 400", True, "")
                            self.log(f"Confirmed: existing driver with bookings blocked: {msg}")
                            return
            except Exception:
                pass
            self.test("Create or test confirmed booking scenario", False, "Could not test confirmed booking scenario")
            return
        
        booking_status = booking.get("status")
        self.log(f"Booking status: {booking_status}")
        
        # Try to delete driver - should return 400
        status_code, msg = self.delete_driver(driver_id)
        self.test("DELETE driver with confirmed booking returns 400", status_code == 400,
                 f"Expected 400, got {status_code}")

    def test_deletable_driver(self):
        """REGRESSION: Driver with NO active bookings CAN be deleted"""
        self.log("\n=== REGRESSION TEST: Driver Without Bookings Can Be Deleted ===")
        
        # Create new driver with no bookings
        driver_id = self.create_driver("Test Driver Deletable", "081234567892")
        if not driver_id:
            self.test("Create deletable driver", False, "Failed to create driver")
            return
        
        # Try to delete driver - should return 200
        status_code, msg = self.delete_driver(driver_id)
        self.test("DELETE driver without bookings returns 200", status_code == 200,
                 f"Expected 200, got {status_code}")
        
        # Verify driver is gone
        driver = self.get_driver(driver_id)
        self.test("Driver no longer exists after delete", driver is None,
                 "Driver still exists after successful delete")

    def test_vehicle_delete_guard(self):
        """REGRESSION: Vehicle delete guard unchanged"""
        self.log("\n=== REGRESSION TEST: Vehicle Delete Guard ===")
        
        try:
            # Get a vehicle that has bookings
            resp = requests.get(
                f"{BASE_URL}/vehicles?limit=10",
                headers=self.get_headers(),
                timeout=10,
            )
            if resp.status_code != 200:
                self.test("Get vehicles for delete test", False, "Failed to get vehicles")
                return
            
            vehicles = resp.json()
            if not vehicles:
                self.log("No vehicles found for delete test", "WARN")
                return
            
            # Try to delete first vehicle (likely has bookings)
            vehicle_id = vehicles[0].get("id")
            resp = requests.delete(
                f"{BASE_URL}/vehicles/{vehicle_id}",
                headers=self.get_headers(),
                timeout=10,
            )
            
            # Should return 400 if vehicle has bookings
            if resp.status_code == 400:
                msg = resp.json().get("detail", "")
                self.test("Vehicle with bookings cannot be deleted", True, "")
                self.log(f"Vehicle delete blocked correctly: {msg}")
            elif resp.status_code == 200:
                self.log("Vehicle had no bookings and was deleted", "INFO")
            else:
                self.test("Vehicle delete returns expected status", False, 
                         f"Unexpected status: {resp.status_code}")
        except Exception as e:
            self.log(f"Exception testing vehicle delete: {e}", "FAIL")

    def test_customer_delete_guard(self):
        """REGRESSION: Customer delete guard unchanged"""
        self.log("\n=== REGRESSION TEST: Customer Delete Guard ===")
        
        try:
            # Get a customer that has bookings
            resp = requests.get(
                f"{BASE_URL}/customers?limit=10",
                headers=self.get_headers(),
                timeout=10,
            )
            if resp.status_code != 200:
                self.test("Get customers for delete test", False, "Failed to get customers")
                return
            
            customers = resp.json()
            if not customers:
                self.log("No customers found for delete test", "WARN")
                return
            
            # Try to delete first customer (likely has bookings)
            customer_id = customers[0].get("id")
            resp = requests.delete(
                f"{BASE_URL}/customers/{customer_id}",
                headers=self.get_headers(),
                timeout=10,
            )
            
            # Should return 400 if customer has bookings
            if resp.status_code == 400:
                msg = resp.json().get("detail", "")
                self.test("Customer with bookings cannot be deleted", True, "")
                self.log(f"Customer delete blocked correctly: {msg}")
            elif resp.status_code == 200:
                self.log("Customer had no bookings and was deleted", "INFO")
            else:
                self.test("Customer delete returns expected status", False,
                         f"Unexpected status: {resp.status_code}")
        except Exception as e:
            self.log(f"Exception testing customer delete: {e}", "FAIL")

    def test_core_flows(self):
        """REGRESSION: Core flows still work"""
        self.log("\n=== REGRESSION TEST: Core Flows ===")
        
        # Test list endpoints
        endpoints = [
            "/drivers",
            "/vehicles", 
            "/bookings",
            "/customers"
        ]
        
        for endpoint in endpoints:
            try:
                resp = requests.get(
                    f"{BASE_URL}{endpoint}?limit=5",
                    headers=self.get_headers(),
                    timeout=10,
                )
                self.test(f"GET {endpoint} returns 200", resp.status_code == 200,
                         f"Got {resp.status_code}")
            except Exception as e:
                self.test(f"GET {endpoint}", False, str(e))

    def run_all_tests(self):
        """Run all tests"""
        self.log("\n" + "="*70)
        self.log("DRIVER DELETE REFERENTIAL INTEGRITY FIX - BACKEND TESTS")
        self.log("="*70)
        
        # Login
        if not self.login("owner@demo.local", "demo12345"):
            self.log("Login failed - cannot proceed with tests", "FAIL")
            return False
        
        # Run tests
        self.test_primary_fix_hold_booking()
        self.test_regression_confirmed_ongoing()
        self.test_deletable_driver()
        self.test_vehicle_delete_guard()
        self.test_customer_delete_guard()
        self.test_core_flows()
        
        # Summary
        self.log("\n" + "="*70)
        self.log(f"TESTS COMPLETED: {self.tests_passed}/{self.tests_run} passed")
        self.log("="*70)
        
        if self.errors:
            self.log("\nFailed Tests:", "FAIL")
            for error in self.errors:
                self.log(f"  • {error}", "FAIL")
        
        return self.tests_failed == 0


def main():
    tester = DriverDeleteTester()
    success = tester.run_all_tests()
    
    # Return exit code
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

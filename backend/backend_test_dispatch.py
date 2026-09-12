"""
E3 Dispatch & Komunikasi Operasi - Backend API Testing
Tests all dispatch endpoints, RBAC, and integration flows.
"""
import requests
import sys
from datetime import datetime, timedelta

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

# Test credentials
CREDENTIALS = {
    "owner": {"email": "owner@demo.local", "password": "demo12345"},
    "ops_admin": {"email": "ops@demo.local", "password": "demo12345"},
    "driver": {"email": "driver@demo.local", "password": "demo12345"},
}


class DispatchTester:
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

    def login(self, role: str):
        """Login with role credentials"""
        creds = CREDENTIALS.get(role)
        if not creds:
            self.log(f"Unknown role: {role}", "FAIL")
            return False

        self.log(f"Logging in as {role} ({creds['email']})...")
        try:
            resp = requests.post(
                f"{BASE_URL}/auth/login",
                json=creds,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("token")
                if token:
                    self.tokens[role] = token
                    self.log(f"Login successful for {role}", "PASS")
                    return True
                else:
                    self.log(f"Login response missing token for {role}", "FAIL")
                    return False
            else:
                self.log(f"Login failed for {role}: {resp.status_code} - {resp.text}", "FAIL")
                return False
        except Exception as e:
            self.log(f"Login exception for {role}: {e}", "FAIL")
            return False

    def get(self, endpoint: str, role: str, params=None):
        """GET request with auth"""
        token = self.tokens.get(role)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers, params=params, timeout=30)
            return resp
        except requests.exceptions.Timeout:
            self.log(f"GET {endpoint} timeout", "WARN")
            return None
        except Exception as e:
            self.log(f"GET {endpoint} exception: {e}", "WARN")
            return None

    def post(self, endpoint: str, role: str, json=None, data=None, files=None):
        """POST request with auth"""
        token = self.tokens.get(role)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            resp = requests.post(
                f"{BASE_URL}{endpoint}",
                headers=headers,
                json=json,
                data=data,
                files=files,
                timeout=30,
            )
            return resp
        except requests.exceptions.Timeout:
            self.log(f"POST {endpoint} timeout", "WARN")
            return None
        except Exception as e:
            self.log(f"POST {endpoint} exception: {e}", "WARN")
            return None

    def test_health(self):
        """Test backend health"""
        self.log("\n=== Testing Backend Health ===")
        try:
            resp = requests.get(f"{BASE_URL}/", timeout=10)
            self.test(
                "Backend health check",
                resp.status_code == 200 and resp.json().get("status") == "ok",
                f"Status: {resp.status_code}, Response: {resp.text[:100]}",
            )
        except Exception as e:
            self.test("Backend health check", False, str(e))

    def test_login_flow(self):
        """Test login for all roles"""
        self.log("\n=== Testing Login Flow ===")
        for role in ["owner", "ops_admin", "driver"]:
            self.login(role)

    def test_dispatch_today(self):
        """Test GET /dispatch/today endpoint"""
        self.log("\n=== Testing GET /dispatch/today ===")

        # Test with owner role
        resp = self.get("/dispatch/today", "owner")
        if resp and resp.status_code == 200:
            data = resp.json()
            self.test(
                "GET /dispatch/today returns 200",
                True,
                "",
            )
            self.test(
                "Response has 'date' field",
                "date" in data,
                f"Missing 'date' in response: {list(data.keys())}",
            )
            self.test(
                "Response has 'summary' field",
                "summary" in data,
                f"Missing 'summary' in response: {list(data.keys())}",
            )
            self.test(
                "Response has 'departures' field",
                "departures" in data,
                f"Missing 'departures' in response: {list(data.keys())}",
            )

            if "summary" in data:
                summary = data["summary"]
                self.test(
                    "Summary has required fields",
                    all(k in summary for k in ["date", "total", "to_assign", "to_confirm", "ongoing", "completed"]),
                    f"Missing fields in summary: {list(summary.keys())}",
                )

            if "departures" in data:
                departures = data["departures"]
                self.test(
                    "Departures is a list",
                    isinstance(departures, list),
                    f"Departures is not a list: {type(departures)}",
                )
                if departures:
                    first = departures[0]
                    required_fields = [
                        "id", "code", "customer_name", "origin", "destination",
                        "assigned", "departure_confirmed", "trip_id", "trip_status",
                        "dest_geocoded", "pod",
                    ]
                    self.test(
                        "Departure has required fields",
                        all(k in first for k in required_fields),
                        f"Missing fields: {[k for k in required_fields if k not in first]}",
                    )
                    # Store test data for later tests
                    self.test_data["departures"] = departures
        else:
            self.test(
                "GET /dispatch/today returns 200",
                False,
                f"Status: {resp.status_code if resp else 'None'}, Response: {resp.text[:200] if resp else 'No response'}",
            )

    def test_dispatch_date_navigation(self):
        """Test date parameter for /dispatch/today"""
        self.log("\n=== Testing Date Navigation ===")

        # Test with tomorrow's date
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        resp = self.get("/dispatch/today", "owner", params={"date": tomorrow})
        if resp and resp.status_code == 200:
            data = resp.json()
            self.test(
                "GET /dispatch/today with date parameter",
                data.get("date") == tomorrow,
                f"Expected date {tomorrow}, got {data.get('date')}",
            )
        else:
            self.test(
                "GET /dispatch/today with date parameter",
                False,
                f"Status: {resp.status_code if resp else 'None'}",
            )

    def test_assign_trip(self):
        """Test POST /dispatch/{booking_id}/assign"""
        self.log("\n=== Testing Assign Trip ===")

        # Find an unassigned booking
        departures = self.test_data.get("departures", [])
        unassigned = next((d for d in departures if not d.get("assigned")), None)

        if not unassigned:
            self.log("No unassigned bookings found, skipping assign test", "WARN")
            return

        # Get drivers and vehicles
        drivers_resp = self.get("/drivers", "owner")
        vehicles_resp = self.get("/vehicles", "owner")

        if not drivers_resp or drivers_resp.status_code != 200:
            self.log("Failed to fetch drivers", "FAIL")
            return
        if not vehicles_resp or vehicles_resp.status_code != 200:
            self.log("Failed to fetch vehicles", "FAIL")
            return

        drivers = drivers_resp.json()
        vehicles = vehicles_resp.json()

        if not isinstance(drivers, list) or not isinstance(vehicles, list):
            self.log("Invalid drivers/vehicles response", "FAIL")
            return

        if not drivers or not vehicles:
            self.log("No drivers or vehicles available", "WARN")
            return

        # Try to assign with different vehicles until one succeeds (to avoid conflicts)
        booking_id = unassigned["id"]
        success = False
        
        for vehicle in vehicles:
            for driver in drivers:
                resp = self.post(
                    f"/dispatch/{booking_id}/assign",
                    "owner",
                    json={"driver_id": driver["id"], "vehicle_id": vehicle["id"]},
                )
                
                if resp and resp.status_code == 200:
                    data = resp.json()
                    self.test("POST /dispatch/{booking_id}/assign returns 200", True, "")
                    self.test(
                        "Response has 'trip' field",
                        "trip" in data,
                        f"Missing 'trip' in response: {list(data.keys())}",
                    )
                    self.test(
                        "Response has 'geocode' field",
                        "geocode" in data,
                        f"Missing 'geocode' in response: {list(data.keys())}",
                    )
                    self.test(
                        "Response has 'booking' field",
                        "booking" in data,
                        f"Missing 'booking' in response: {list(data.keys())}",
                    )

                    if "trip" in data:
                        trip = data["trip"]
                        self.test_data["assigned_trip"] = trip
                        self.test_data["assigned_booking_id"] = booking_id
                        self.log(f"Successfully assigned to vehicle {vehicle.get('code')} and driver {driver.get('name')}")
                    success = True
                    break
                elif resp and resp.status_code == 400:
                    # Try next combination (likely vehicle conflict)
                    continue
            if success:
                break
        
        if not success:
            self.test(
                "POST /dispatch/{booking_id}/assign returns 200",
                False,
                "All vehicle/driver combinations failed (conflicts or errors)",
            )

    def test_confirm_departure(self):
        """Test POST /dispatch/{booking_id}/confirm-departure"""
        self.log("\n=== Testing Confirm Departure ===")

        booking_id = self.test_data.get("assigned_booking_id")
        if not booking_id:
            self.log("No assigned booking found, skipping confirm test", "WARN")
            return

        resp = self.post(f"/dispatch/{booking_id}/confirm-departure", "owner")

        if resp and resp.status_code == 200:
            data = resp.json()
            self.test("POST /dispatch/{booking_id}/confirm-departure returns 200", True, "")
            self.test(
                "Response has 'ok' field",
                data.get("ok") is True,
                f"Response: {data}",
            )
        else:
            self.test(
                "POST /dispatch/{booking_id}/confirm-departure returns 200",
                False,
                f"Status: {resp.status_code if resp else 'None'}, Response: {resp.text[:200] if resp else 'No response'}",
            )

    def test_trip_enroute(self):
        """Test POST /dispatch/trips/{trip_id}/enroute"""
        self.log("\n=== Testing Trip Enroute ===")

        trip = self.test_data.get("assigned_trip")
        if not trip:
            self.log("No assigned trip found, skipping enroute test", "WARN")
            return

        trip_id = trip.get("id")
        resp = self.post(f"/dispatch/trips/{trip_id}/enroute", "owner")

        if resp and resp.status_code == 200:
            data = resp.json()
            self.test("POST /dispatch/trips/{trip_id}/enroute returns 200", True, "")
            self.test(
                "Trip status updated to 'to_pickup'",
                data.get("status") == "to_pickup",
                f"Expected status 'to_pickup', got {data.get('status')}",
            )
            self.test(
                "Trip has 'enroute_at' timestamp",
                "enroute_at" in data,
                f"Missing 'enroute_at' in response",
            )
        else:
            self.test(
                "POST /dispatch/trips/{trip_id}/enroute returns 200",
                False,
                f"Status: {resp.status_code if resp else 'None'}, Response: {resp.text[:200] if resp else 'No response'}",
            )

    def test_trip_arrived(self):
        """Test POST /dispatch/trips/{trip_id}/arrived"""
        self.log("\n=== Testing Trip Arrived ===")

        trip = self.test_data.get("assigned_trip")
        if not trip:
            self.log("No assigned trip found, skipping arrived test", "WARN")
            return

        trip_id = trip.get("id")
        resp = self.post(f"/dispatch/trips/{trip_id}/arrived", "owner")

        if resp and resp.status_code == 200:
            data = resp.json()
            self.test("POST /dispatch/trips/{trip_id}/arrived returns 200", True, "")
            self.test(
                "Trip has 'arrived_at' timestamp",
                "arrived_at" in data,
                f"Missing 'arrived_at' in response",
            )
        else:
            self.test(
                "POST /dispatch/trips/{trip_id}/arrived returns 200",
                False,
                f"Status: {resp.status_code if resp else 'None'}, Response: {resp.text[:200] if resp else 'No response'}",
            )

    def test_pod_upload(self):
        """Test POST /dispatch/trips/{trip_id}/pod (without photo)"""
        self.log("\n=== Testing POD Upload (recipient + note only) ===")

        trip = self.test_data.get("assigned_trip")
        if not trip:
            self.log("No assigned trip found, skipping POD test", "WARN")
            return

        trip_id = trip.get("id")
        resp = self.post(
            f"/dispatch/trips/{trip_id}/pod",
            "owner",
            data={"recipient_name": "Pak Budi", "note": "Diterima dengan baik"},
        )

        if resp and resp.status_code == 200:
            data = resp.json()
            self.test("POST /dispatch/trips/{trip_id}/pod returns 200", True, "")
            self.test(
                "Trip has 'pod' field",
                "pod" in data,
                f"Missing 'pod' in response",
            )
            if "pod" in data:
                pod = data["pod"]
                self.test(
                    "POD has recipient_name",
                    pod.get("recipient_name") == "Pak Budi",
                    f"Expected 'Pak Budi', got {pod.get('recipient_name')}",
                )
                self.test(
                    "POD has note",
                    pod.get("note") == "Diterima dengan baik",
                    f"Expected 'Diterima dengan baik', got {pod.get('note')}",
                )
        else:
            self.test(
                "POST /dispatch/trips/{trip_id}/pod returns 200",
                False,
                f"Status: {resp.status_code if resp else 'None'}, Response: {resp.text[:200] if resp else 'No response'}",
            )

    def test_rbac_driver_blocked(self):
        """Test that driver role cannot access dispatch endpoints"""
        self.log("\n=== Testing RBAC: Driver Role Blocked ===")

        # Verify driver token exists
        if "driver" not in self.tokens:
            self.log("Driver token not found, skipping RBAC test", "WARN")
            return

        self.log(f"Driver token exists: {self.tokens['driver'][:20]}...")
        resp = self.get("/dispatch/today", "driver")
        
        if resp is None:
            self.test(
                "Driver role blocked from GET /dispatch/today",
                False,
                "No response received (timeout or exception)",
            )
        elif resp.status_code == 403:
            self.test(
                "Driver role blocked from GET /dispatch/today",
                True,
                "",
            )
        else:
            self.test(
                "Driver role blocked from GET /dispatch/today",
                False,
                f"Expected 403, got {resp.status_code}",
            )

    def test_rbac_ops_admin_allowed(self):
        """Test that ops_admin role can access dispatch endpoints"""
        self.log("\n=== Testing RBAC: Ops Admin Allowed ===")

        resp = self.get("/dispatch/today", "ops_admin")
        self.test(
            "Ops admin role allowed to GET /dispatch/today",
            resp and resp.status_code == 200,
            f"Expected 200, got {resp.status_code if resp else 'None'}",
        )

    def print_summary(self):
        """Print test summary"""
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


def main():
    tester = DispatchTester()

    # Run all tests
    tester.test_health()
    tester.test_login_flow()
    tester.test_dispatch_today()
    tester.test_dispatch_date_navigation()
    tester.test_assign_trip()
    tester.test_confirm_departure()
    tester.test_trip_enroute()
    tester.test_trip_arrived()
    tester.test_pod_upload()
    tester.test_rbac_driver_blocked()
    tester.test_rbac_ops_admin_allowed()

    return tester.print_summary()


if __name__ == "__main__":
    sys.exit(main())

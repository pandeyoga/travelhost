"""
Backend Test Suite for Phase 8 / A1 - Audit Log Engine
Tests RBAC, filters, audit generation, safety, and regression.
"""
import requests
import sys
from datetime import datetime

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

class AuditLogTester:
    def __init__(self):
        self.tokens = {}
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, passed, details=""):
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name}")
            if details:
                print(f"   Details: {details}")
        self.test_results.append({"name": name, "passed": passed, "details": details})

    def login(self, email, password):
        """Login and store token"""
        try:
            resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("token")
                if token:
                    self.tokens[email] = token
                    print(f"✅ Login successful: {email}")
                    return True
                else:
                    print(f"❌ Login failed: {email} - no token in response")
                    return False
            else:
                print(f"❌ Login failed: {email} - status {resp.status_code}")
                return False
        except Exception as e:
            print(f"❌ Login error: {email} - {str(e)}")
            return False

    def get_headers(self, email):
        """Get auth headers for user"""
        token = self.tokens.get(email)
        if not token:
            return {"Content-Type": "application/json"}
        return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    # ========== RBAC TESTS ==========
    def test_audit_rbac(self):
        """Test GET /api/audit-logs RBAC: owner 200, ops_admin 403, driver 403, no auth 401/403"""
        print("\n=== AUDIT BACKEND RBAC TESTS ===")
        
        # Owner should get 200
        resp = requests.get(f"{BASE_URL}/audit-logs", headers=self.get_headers("owner@demo.local"), timeout=10)
        self.log_test("RBAC: owner GET /api/audit-logs returns 200", resp.status_code == 200, f"Got {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            self.log_test("RBAC: owner response is array", isinstance(data, list), f"Got {type(data)}")
        
        # ops_admin should get 403
        resp = requests.get(f"{BASE_URL}/audit-logs", headers=self.get_headers("ops@demo.local"), timeout=10)
        self.log_test("RBAC: ops_admin GET /api/audit-logs returns 403", resp.status_code == 403, f"Got {resp.status_code}")
        
        # driver should get 403
        resp = requests.get(f"{BASE_URL}/audit-logs", headers=self.get_headers("driver@demo.local"), timeout=10)
        self.log_test("RBAC: driver GET /api/audit-logs returns 403", resp.status_code == 403, f"Got {resp.status_code}")
        
        # No auth should get 401 or 403
        resp = requests.get(f"{BASE_URL}/audit-logs", timeout=10)
        self.log_test("RBAC: no auth GET /api/audit-logs returns 401/403", resp.status_code in [401, 403], f"Got {resp.status_code}")

    # ========== FILTER TESTS ==========
    def test_audit_filters(self):
        """Test GET /api/audit-logs filters: entity_type, action, q, limit, sorting"""
        print("\n=== AUDIT BACKEND FILTER TESTS ===")
        
        headers = self.get_headers("owner@demo.local")
        
        # Get all audit logs first
        resp = requests.get(f"{BASE_URL}/audit-logs", headers=headers, timeout=10)
        if resp.status_code != 200:
            self.log_test("FILTER: Get all audit logs", False, f"Status {resp.status_code}")
            return
        all_logs = resp.json()
        self.log_test("FILTER: Get all audit logs", True, f"Got {len(all_logs)} entries")
        
        # Test entity_type filter
        resp = requests.get(f"{BASE_URL}/audit-logs?entity_type=vehicle", headers=headers, timeout=10)
        if resp.status_code == 200:
            vehicle_logs = resp.json()
            all_vehicle = all(log.get("entity_type") == "vehicle" for log in vehicle_logs)
            self.log_test("FILTER: entity_type=vehicle returns only vehicle entries", all_vehicle, f"Got {len(vehicle_logs)} entries")
        else:
            self.log_test("FILTER: entity_type=vehicle", False, f"Status {resp.status_code}")
        
        # Test action filter
        resp = requests.get(f"{BASE_URL}/audit-logs?action=create", headers=headers, timeout=10)
        if resp.status_code == 200:
            create_logs = resp.json()
            all_create = all(log.get("action") == "create" for log in create_logs)
            self.log_test("FILTER: action=create returns only create entries", all_create, f"Got {len(create_logs)} entries")
        else:
            self.log_test("FILTER: action=create", False, f"Status {resp.status_code}")
        
        # Test search filter (q)
        if all_logs:
            # Search for a term that should exist
            search_term = "armada" if any("armada" in log.get("summary", "").lower() for log in all_logs) else "booking"
            resp = requests.get(f"{BASE_URL}/audit-logs?q={search_term}", headers=headers, timeout=10)
            if resp.status_code == 200:
                search_logs = resp.json()
                self.log_test(f"FILTER: q={search_term} returns matching entries", len(search_logs) > 0, f"Got {len(search_logs)} entries")
            else:
                self.log_test(f"FILTER: q={search_term}", False, f"Status {resp.status_code}")
        
        # Test limit filter
        resp = requests.get(f"{BASE_URL}/audit-logs?limit=5", headers=headers, timeout=10)
        if resp.status_code == 200:
            limited_logs = resp.json()
            self.log_test("FILTER: limit=5 caps results", len(limited_logs) <= 5, f"Got {len(limited_logs)} entries")
        else:
            self.log_test("FILTER: limit=5", False, f"Status {resp.status_code}")
        
        # Test sorting (newest first)
        if len(all_logs) >= 2:
            timestamps = [log.get("timestamp") for log in all_logs[:10]]
            sorted_desc = timestamps == sorted(timestamps, reverse=True)
            self.log_test("FILTER: results sorted newest-first by timestamp", sorted_desc, f"First 10 timestamps: {timestamps[:3]}...")
        else:
            self.log_test("FILTER: results sorted newest-first", True, "Not enough entries to verify sorting")

    # ========== AUDIT GENERATION TESTS ==========
    def test_audit_generation(self):
        """Test that CRUD operations create audit log entries"""
        print("\n=== AUDIT GENERATION TESTS ===")
        
        headers = self.get_headers("owner@demo.local")
        
        # Get initial count
        resp = requests.get(f"{BASE_URL}/audit-logs", headers=headers, timeout=10)
        if resp.status_code != 200:
            print("❌ Cannot get initial audit log count")
            return
        initial_count = len(resp.json())
        print(f"Initial audit log count: {initial_count}")
        
        # (a) PATCH /api/settings
        print("\n--- Testing settings update audit ---")
        resp = requests.patch(f"{BASE_URL}/settings", 
                            json={"pricing_defaults": {"dp_percent": 35, "min_rental_hours": 12, "cancellation_policy": "test"}},
                            headers=headers, timeout=10)
        self.log_test("GEN: PATCH /api/settings returns 200", resp.status_code == 200, f"Got {resp.status_code}")
        
        # (b) POST /api/vehicles (create)
        print("\n--- Testing vehicle create audit ---")
        vehicle_data = {
            "name": f"Test Vehicle {datetime.now().strftime('%H%M%S')}",
            "plate_number": f"TEST-{datetime.now().strftime('%H%M%S')}",
            "type": "hiace",
            "capacity": 14,
            "status": "available"
        }
        resp = requests.post(f"{BASE_URL}/vehicles", json=vehicle_data, headers=headers, timeout=10)
        self.log_test("GEN: POST /api/vehicles returns 200/201", resp.status_code in [200, 201], f"Got {resp.status_code}")
        vehicle_id = None
        if resp.status_code in [200, 201]:
            vehicle_id = resp.json().get("id")
            print(f"Created vehicle: {vehicle_id}")
        
        # (c) PATCH /api/vehicles/{id} (update)
        if vehicle_id:
            print("\n--- Testing vehicle update audit ---")
            resp = requests.patch(f"{BASE_URL}/vehicles/{vehicle_id}", 
                                json={"notes": "Updated for audit test"}, 
                                headers=headers, timeout=10)
            self.log_test("GEN: PATCH /api/vehicles returns 200", resp.status_code == 200, f"Got {resp.status_code}")
        
        # (e) POST /api/payments (need a booking first)
        print("\n--- Testing payment create audit ---")
        # Get an existing booking
        resp = requests.get(f"{BASE_URL}/bookings?limit=1", headers=headers, timeout=10)
        if resp.status_code == 200 and len(resp.json()) > 0:
            booking = resp.json()[0]
            booking_id = booking.get("id")
            payment_data = {
                "booking_id": booking_id,
                "amount": 100000,
                "type": "dp",
                "method": "transfer",
                "note": "Test payment for audit"
            }
            resp = requests.post(f"{BASE_URL}/payments", json=payment_data, headers=headers, timeout=10)
            self.log_test("GEN: POST /api/payments returns 200/201", resp.status_code in [200, 201], f"Got {resp.status_code}")
        else:
            self.log_test("GEN: POST /api/payments", False, "No booking available for payment test")
        
        # (f) POST /api/expenses
        print("\n--- Testing expense create audit ---")
        expense_data = {
            "category": "fuel",
            "amount": 50000,
            "note": "Test expense for audit"
        }
        resp = requests.post(f"{BASE_URL}/expenses", json=expense_data, headers=headers, timeout=10)
        self.log_test("GEN: POST /api/expenses returns 200/201", resp.status_code in [200, 201], f"Got {resp.status_code}")
        
        # (g) POST /api/invoices then PATCH
        print("\n--- Testing invoice create and update audit ---")
        resp = requests.get(f"{BASE_URL}/bookings?limit=1", headers=headers, timeout=10)
        if resp.status_code == 200 and len(resp.json()) > 0:
            booking = resp.json()[0]
            booking_id = booking.get("id")
            invoice_data = {
                "booking_id": booking_id,
                "amount": 1000000,
                "notes": "Test invoice for audit"
            }
            resp = requests.post(f"{BASE_URL}/invoices", json=invoice_data, headers=headers, timeout=10)
            self.log_test("GEN: POST /api/invoices returns 200/201", resp.status_code in [200, 201], f"Got {resp.status_code}")
            
            if resp.status_code in [200, 201]:
                invoice_id = resp.json().get("id")
                resp = requests.patch(f"{BASE_URL}/invoices/{invoice_id}", 
                                    json={"status": "sent"}, 
                                    headers=headers, timeout=10)
                self.log_test("GEN: PATCH /api/invoices returns 200", resp.status_code == 200, f"Got {resp.status_code}")
        else:
            self.log_test("GEN: POST /api/invoices", False, "No booking available for invoice test")
        
        # (h) Booking actions (confirm/cancel/complete)
        print("\n--- Testing booking action audits ---")
        resp = requests.get(f"{BASE_URL}/bookings?limit=1", headers=headers, timeout=10)
        if resp.status_code == 200 and len(resp.json()) > 0:
            booking = resp.json()[0]
            booking_id = booking.get("id")
            
            # Try confirm
            resp = requests.post(f"{BASE_URL}/bookings/{booking_id}/confirm", headers=headers, timeout=10)
            self.log_test("GEN: POST /api/bookings/{id}/confirm returns 200", resp.status_code == 200, f"Got {resp.status_code}")
            
            # Try cancel
            resp = requests.post(f"{BASE_URL}/bookings/{booking_id}/cancel", headers=headers, timeout=10)
            self.log_test("GEN: POST /api/bookings/{id}/cancel returns 200", resp.status_code == 200, f"Got {resp.status_code}")
        else:
            self.log_test("GEN: Booking actions", False, "No booking available for action tests")
        
        # (d) DELETE /api/vehicles (if vehicle has no bookings)
        if vehicle_id:
            print("\n--- Testing vehicle delete audit ---")
            resp = requests.delete(f"{BASE_URL}/vehicles/{vehicle_id}", headers=headers, timeout=10)
            self.log_test("GEN: DELETE /api/vehicles returns 200", resp.status_code == 200, f"Got {resp.status_code}")
        
        # Verify audit count increased
        print("\n--- Verifying audit log count increased ---")
        resp = requests.get(f"{BASE_URL}/audit-logs", headers=headers, timeout=10)
        if resp.status_code == 200:
            final_count = len(resp.json())
            increased = final_count > initial_count
            self.log_test("GEN: Audit log count increased", increased, f"Initial: {initial_count}, Final: {final_count}, Diff: {final_count - initial_count}")
            
            # Check newest entry has correct fields
            if final_count > 0:
                newest = resp.json()[0]
                has_action = "action" in newest and newest["action"]
                has_entity_type = "entity_type" in newest and newest["entity_type"]
                has_actor_name = "actor_name" in newest
                has_summary = "summary" in newest and newest["summary"]
                self.log_test("GEN: Newest entry has action", has_action, f"action={newest.get('action')}")
                self.log_test("GEN: Newest entry has entity_type", has_entity_type, f"entity_type={newest.get('entity_type')}")
                self.log_test("GEN: Newest entry has actor_name", has_actor_name, f"actor_name={newest.get('actor_name')}")
                self.log_test("GEN: Newest entry has summary", has_summary, f"summary={newest.get('summary')[:50]}...")
        else:
            self.log_test("GEN: Verify audit count", False, f"Status {resp.status_code}")

    # ========== AUDIT SAFETY TESTS ==========
    def test_audit_safety(self):
        """Test that audit logs don't leak password_hash and business actions still work"""
        print("\n=== AUDIT SAFETY TESTS ===")
        
        headers = self.get_headers("owner@demo.local")
        
        # Check no password_hash in audit logs
        resp = requests.get(f"{BASE_URL}/audit-logs", headers=headers, timeout=10)
        if resp.status_code == 200:
            logs = resp.json()
            has_password_hash = any(
                "password_hash" in str(log.get("before", "")) or 
                "password_hash" in str(log.get("after", ""))
                for log in logs
            )
            self.log_test("SAFETY: No password_hash in audit logs", not has_password_hash, "Checked all entries")
        else:
            self.log_test("SAFETY: Check password_hash", False, f"Status {resp.status_code}")
        
        # Test that business actions still return correct responses
        vehicle_data = {
            "name": f"Safety Test Vehicle {datetime.now().strftime('%H%M%S')}",
            "plate_number": f"SAFE-{datetime.now().strftime('%H%M%S')}",
            "type": "hiace",
            "capacity": 14,
            "status": "available"
        }
        resp = requests.post(f"{BASE_URL}/vehicles", json=vehicle_data, headers=headers, timeout=10)
        if resp.status_code in [200, 201]:
            data = resp.json()
            has_id = "id" in data
            has_name = "name" in data
            self.log_test("SAFETY: Business action returns correct body", has_id and has_name, f"Has id={has_id}, name={has_name}")
            
            # Clean up
            if "id" in data:
                requests.delete(f"{BASE_URL}/vehicles/{data['id']}", headers=headers, timeout=10)
        else:
            self.log_test("SAFETY: Business action", False, f"Status {resp.status_code}")

    # ========== REGRESSION TESTS ==========
    def test_regression(self):
        """Test that existing APIs still work correctly"""
        print("\n=== REGRESSION TESTS ===")
        
        headers_owner = self.get_headers("owner@demo.local")
        headers_ops = self.get_headers("ops@demo.local")
        headers_driver = self.get_headers("driver@demo.local")
        
        # Test various endpoints
        endpoints = [
            ("GET /api/dashboard", f"{BASE_URL}/dashboard", headers_owner),
            ("GET /api/vehicles", f"{BASE_URL}/vehicles", headers_owner),
            ("GET /api/bookings", f"{BASE_URL}/bookings", headers_owner),
            ("GET /api/maintenance", f"{BASE_URL}/maintenance", headers_owner),
            ("GET /api/conversations", f"{BASE_URL}/conversations", headers_owner),
            ("GET /api/notifications/unread_count", f"{BASE_URL}/notifications/unread_count", headers_owner),
            ("GET /api/settings", f"{BASE_URL}/settings", headers_owner),
        ]
        
        for name, url, headers in endpoints:
            resp = requests.get(url, headers=headers, timeout=10)
            self.log_test(f"REGRESSION: {name} returns 200", resp.status_code == 200, f"Got {resp.status_code}")
        
        # Test anti-double-booking (INV-4)
        print("\n--- Testing anti-double-booking (INV-4) ---")
        resp = requests.get(f"{BASE_URL}/bookings?limit=1", headers=headers_owner, timeout=10)
        if resp.status_code == 200 and len(resp.json()) > 0:
            existing_booking = resp.json()[0]
            vehicle_id = existing_booking.get("vehicle_id")
            start = existing_booking.get("start_datetime")
            end = existing_booking.get("end_datetime")
            
            if vehicle_id and start and end:
                # Try to create overlapping booking
                resp = requests.get(f"{BASE_URL}/customers?limit=1", headers=headers_owner, timeout=10)
                if resp.status_code == 200 and len(resp.json()) > 0:
                    customer_id = resp.json()[0].get("id")
                    overlap_booking = {
                        "customer_id": customer_id,
                        "vehicle_id": vehicle_id,
                        "start_datetime": start,
                        "end_datetime": end,
                        "base_price": 1000000,
                        "origin": "Test Origin",
                        "destination": "Test Destination"
                    }
                    resp = requests.post(f"{BASE_URL}/bookings", json=overlap_booking, headers=headers_owner, timeout=10)
                    self.log_test("REGRESSION: Anti-double-booking rejects overlap with 400", resp.status_code == 400, f"Got {resp.status_code}")
                else:
                    self.log_test("REGRESSION: Anti-double-booking", False, "No customer available")
            else:
                self.log_test("REGRESSION: Anti-double-booking", False, "Incomplete booking data")
        else:
            self.log_test("REGRESSION: Anti-double-booking", False, "No existing booking to test overlap")

    def run_all_tests(self):
        """Run all test suites"""
        print("=" * 60)
        print("PHASE 8 / A1 - AUDIT LOG ENGINE TEST SUITE")
        print("=" * 60)
        
        # Login all users
        print("\n=== AUTHENTICATION ===")
        if not self.login("owner@demo.local", "demo12345"):
            print("❌ Cannot login as owner - stopping tests")
            return False
        if not self.login("ops@demo.local", "demo12345"):
            print("❌ Cannot login as ops_admin - stopping tests")
            return False
        if not self.login("driver@demo.local", "demo12345"):
            print("❌ Cannot login as driver - stopping tests")
            return False
        
        # Run test suites
        self.test_audit_rbac()
        self.test_audit_filters()
        self.test_audit_generation()
        self.test_audit_safety()
        self.test_regression()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"TESTS PASSED: {self.tests_passed}/{self.tests_run}")
        print("=" * 60)
        
        return self.tests_passed == self.tests_run

def main():
    tester = AuditLogTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())

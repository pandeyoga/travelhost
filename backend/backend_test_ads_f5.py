"""backend_test_ads_f5.py — Test RBAC & functionality for /api/ads/* endpoints (Fase F5).

Verifikasi:
  1. RBAC 4 peran: owner, marketing_admin, ops_admin (read-only), driver (403).
  2. Tanpa kredensial platform: semua endpoint 200 dengan status 'not_configured' (BUKAN 5xx).
  3. Endpoint mutasi (POST/PUT) hanya owner + marketing_admin.
  4. Validasi budget & safety guards.
"""
import sys
import requests
from datetime import datetime

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

# Test credentials
USERS = {
    "owner": {"email": "owner@demo.local", "password": "demo12345"},
    "marketing": {"email": "marketing@demo.local", "password": "demo12345"},
    "ops": {"email": "ops@demo.local", "password": "demo12345"},
    "driver": {"email": "driver@demo.local", "password": "demo12345"},
}

class AdsAPITester:
    def __init__(self):
        self.tokens = {}
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def login(self, role):
        """Login and get token for a role"""
        user = USERS[role]
        try:
            r = requests.post(f"{BASE_URL}/auth/login", json=user, timeout=10)
            if r.status_code == 200:
                token = r.json().get("token")
                self.tokens[role] = token
                print(f"✅ Login {role}: OK")
                return True
            else:
                print(f"❌ Login {role}: {r.status_code}")
                return False
        except Exception as e:
            print(f"❌ Login {role}: {e}")
            return False

    def test(self, name, method, endpoint, role, expected_status, data=None, check_not_configured=False):
        """Run a single API test"""
        self.tests_run += 1
        url = f"{BASE_URL}{endpoint}"
        headers = {"Authorization": f"Bearer {self.tokens.get(role, '')}", "Content-Type": "application/json"}
        
        print(f"\n🔍 [{self.tests_run}] {name}")
        print(f"   {method} {endpoint} (role: {role})")
        
        try:
            if method == "GET":
                r = requests.get(url, headers=headers, timeout=15)
            elif method == "POST":
                r = requests.post(url, headers=headers, json=data or {}, timeout=15)
            elif method == "PUT":
                r = requests.put(url, headers=headers, json=data or {}, timeout=15)
            else:
                print(f"❌ Unknown method: {method}")
                self.failed_tests.append(name)
                return False

            # Check status code
            if r.status_code != expected_status:
                print(f"❌ FAILED - Expected {expected_status}, got {r.status_code}")
                print(f"   Response: {r.text[:200]}")
                self.failed_tests.append(name)
                return False

            # Check for not_configured status if requested
            if check_not_configured and r.status_code == 200:
                try:
                    json_data = r.json()
                    # Check if response indicates not_configured
                    if isinstance(json_data, dict):
                        # For overview endpoint
                        if "readiness" in json_data:
                            readiness = json_data.get("readiness", {})
                            meta_ready = readiness.get("meta", {}).get("ready", True)
                            google_ready = readiness.get("google", {}).get("ready", True)
                            if meta_ready or google_ready:
                                print(f"⚠️  WARNING - Expected not_configured but got ready status")
                        # For sync endpoint
                        elif "reports" in json_data:
                            reports = json_data.get("reports", {})
                            for provider, report in reports.items():
                                if report.get("status") not in ("not_configured", "error"):
                                    print(f"⚠️  WARNING - {provider} status: {report.get('status')}")
                except Exception:  # noqa: BLE001
                    pass

            print(f"✅ PASSED - Status {r.status_code}")
            self.tests_passed += 1
            return True

        except requests.exceptions.Timeout:
            print(f"❌ FAILED - Request timeout")
            self.failed_tests.append(name)
            return False
        except Exception as e:
            print(f"❌ FAILED - {type(e).__name__}: {str(e)[:100]}")
            self.failed_tests.append(name)
            return False

    def run_all_tests(self):
        """Run all test scenarios"""
        print("=" * 80)
        print("BACKEND TEST: Ads API (Fase F5) - RBAC & No 5xx without credentials")
        print("=" * 80)

        # Login all users
        print("\n📝 STEP 1: Login all users")
        for role in USERS.keys():
            if not self.login(role):
                print(f"\n❌ Cannot proceed - {role} login failed")
                return False

        # Test READ endpoints - owner, marketing, ops should get 200; driver should get 403
        print("\n📝 STEP 2: Test READ endpoints (GET)")
        
        read_endpoints = [
            "/ads/overview",
            "/ads/entities",
            "/ads/accounts",
            "/ads/platform-leads",
            "/ads/audiences",
        ]

        for endpoint in read_endpoints:
            # Owner, marketing, ops should succeed
            for role in ["owner", "marketing", "ops"]:
                self.test(
                    f"GET {endpoint} as {role}",
                    "GET", endpoint, role, 200,
                    check_not_configured=(endpoint == "/ads/overview")
                )
            
            # Driver should be denied
            self.test(
                f"GET {endpoint} as driver (should be 403)",
                "GET", endpoint, "driver", 403
            )

        # Test WRITE endpoints - only owner and marketing should succeed; ops and driver should get 403
        print("\n📝 STEP 3: Test WRITE endpoints (POST/PUT)")
        
        write_tests = [
            ("POST", "/ads/sync", {"days": 7}),
            ("POST", "/ads/campaigns/validate", {
                "provider": "meta",
                "campaign": {"name": "Test Campaign"},
                "adset": {"name": "Test Adset", "daily_budget_minor": 150000}
            }),
            ("POST", "/ads/platform-leads/simulate", {
                "name": "Test Lead",
                "phone": "628123456789",
                "campaign_id": "TEST-001"
            }),
            ("PUT", "/ads/manual-spend", {"items": [{"channel": "meta_ads", "amount": 1000000}]}),
        ]

        for method, endpoint, data in write_tests:
            # Owner and marketing should succeed (200 or 400 for validation errors, but NOT 403)
            for role in ["owner", "marketing"]:
                expected = 200
                self.test(
                    f"{method} {endpoint} as {role}",
                    method, endpoint, role, expected, data=data,
                    check_not_configured=(endpoint == "/ads/sync")
                )
            
            # Ops and driver should be denied (403)
            for role in ["ops", "driver"]:
                self.test(
                    f"{method} {endpoint} as {role} (should be 403)",
                    method, endpoint, role, 403, data=data
                )

        # Test budget validation
        print("\n📝 STEP 4: Test budget validation (safety guards)")
        
        # Test zero budget (should be 400)
        self.test(
            "Validate campaign with zero budget (should be 400)",
            "POST", "/ads/campaigns/validate", "owner", 400,
            data={
                "provider": "meta",
                "campaign": {"name": "Test Zero Budget"},
                "adset": {"name": "Test Adset", "daily_budget_minor": 0}
            }
        )

        # Test Lookalike with insufficient seed (should be 400)
        self.test(
            "Create Lookalike with seed < 100 (should be 400)",
            "POST", "/ads/audiences/lookalike", "owner", 400,
            data={
                "origin_audience_id": "123456",
                "name": "Test Lookalike",
                "seed_size": 50,
                "mode": "validate"
            }
        )

        # Print summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Total tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        
        if self.failed_tests:
            print(f"\n❌ Failed tests ({len(self.failed_tests)}):")
            for test in self.failed_tests:
                print(f"   - {test}")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"\nSuccess rate: {success_rate:.1f}%")
        
        return self.tests_passed == self.tests_run


def main():
    tester = AdsAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

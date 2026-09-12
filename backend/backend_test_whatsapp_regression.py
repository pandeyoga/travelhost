"""
WhatsApp Module Regression Test (QUAL-1 fix verification)
Tests the WhatsApp module after changing exception handler in auto-reply work-hours check.
Changed: services/whatsapp.py line ~317 - bare `except Exception: pass` -> `except Exception as exc: logger.debug(...)`
Expected: NO regression, NO 5xx errors, behavior unchanged except logging on rare failure path.
"""
import requests
import sys
import json
from datetime import datetime

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com"
TEST_USER = "owner@demo.local"
TEST_PASSWORD = "demo12345"

class WhatsAppRegressionTester:
    def __init__(self):
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []
        self.five_xx_errors = []

    def log(self, msg, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {msg}")

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, params=None, allow_4xx=False):
        """Run a single API test and track 5xx errors"""
        url = f"{BASE_URL}{endpoint}"
        req_headers = {'Content-Type': 'application/json'}
        if self.token:
            req_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            req_headers.update(headers)

        self.tests_run += 1
        self.log(f"Test #{self.tests_run}: {name}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=req_headers, params=params, timeout=15)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=req_headers, timeout=15)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=req_headers, timeout=15)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=req_headers, timeout=15)
            elif method == 'DELETE':
                response = requests.delete(url, headers=req_headers, timeout=15)
            else:
                self.log(f"❌ FAILED - Unknown method: {method}", "ERROR")
                self.tests_failed += 1
                self.failures.append({"test": name, "reason": f"Unknown method: {method}"})
                return False, {}

            # Check for 5xx errors (critical for this regression test)
            if 500 <= response.status_code < 600:
                self.log(f"🚨 5XX ERROR - Status: {response.status_code}", "CRITICAL")
                self.five_xx_errors.append({
                    "test": name,
                    "endpoint": endpoint,
                    "status": response.status_code,
                    "response": response.text[:500]
                })
                self.tests_failed += 1
                self.failures.append({"test": name, "reason": f"5xx error: {response.status_code}"})
                return False, {}

            # Check expected status
            if isinstance(expected_status, list):
                success = response.status_code in expected_status
            else:
                success = response.status_code == expected_status

            # For adversarial tests, we expect 4xx (not 5xx)
            if allow_4xx and 400 <= response.status_code < 500:
                success = True

            if success:
                self.tests_passed += 1
                self.log(f"✅ PASSED - Status: {response.status_code}")
                try:
                    return True, response.json() if response.content else {}
                except Exception:
                    return True, {}
            else:
                self.tests_failed += 1
                self.log(f"❌ FAILED - Expected {expected_status}, got {response.status_code}", "ERROR")
                self.failures.append({
                    "test": name,
                    "reason": f"Expected {expected_status}, got {response.status_code}",
                    "response": response.text[:300]
                })
                return False, {}

        except requests.exceptions.Timeout:
            self.log(f"❌ FAILED - Request timeout", "ERROR")
            self.tests_failed += 1
            self.failures.append({"test": name, "reason": "Request timeout"})
            return False, {}
        except Exception as e:
            self.log(f"❌ FAILED - Exception: {str(e)}", "ERROR")
            self.tests_failed += 1
            self.failures.append({"test": name, "reason": str(e)})
            return False, {}

    def test_login(self):
        """Test login to get auth token"""
        self.log("\n=== AUTHENTICATION ===", "SECTION")
        success, response = self.run_test(
            "Login as owner",
            "POST",
            "/api/auth/login",
            200,
            data={"email": TEST_USER, "password": TEST_PASSWORD}
        )
        if success and 'token' in response:
            self.token = response['token']
            self.log(f"Token obtained: {self.token[:20]}...")
            return True
        self.log("Login failed - cannot proceed with authenticated tests", "ERROR")
        return False

    def test_wa_config(self):
        """Test WhatsApp config GET and PATCH"""
        self.log("\n=== WA CONFIG TESTS ===", "SECTION")
        
        # GET config
        success, config = self.run_test(
            "GET /api/wa/config",
            "GET",
            "/api/wa/config",
            200
        )
        if success:
            self.log(f"Config retrieved: provider={config.get('provider')}, auto_reply_enabled={config.get('auto_reply_enabled')}")
        
        # PATCH config - enable auto_reply and set work hours
        success, updated = self.run_test(
            "PATCH /api/wa/config (enable auto_reply + work hours)",
            "PATCH",
            "/api/wa/config",
            200,
            data={
                "auto_reply_enabled": True,
                "auto_reply_text": "Test auto reply message",
                "away_reply_text": "Test away message (outside work hours)"
            }
        )
        if success:
            self.log(f"Config updated: auto_reply_enabled={updated.get('auto_reply_enabled')}")
        
        # GET config again to verify changes
        success, verify = self.run_test(
            "GET /api/wa/config (verify changes)",
            "GET",
            "/api/wa/config",
            200
        )
        if success and verify.get('auto_reply_enabled') == True:
            self.log("Config changes verified successfully")

    def test_wa_simulate_inbound(self):
        """Test WhatsApp simulate-inbound (CRITICAL - contains the changed code)"""
        self.log("\n=== WA SIMULATE-INBOUND TESTS (TOUCHED CODE PATH) ===", "SECTION")
        
        # Test 1: Normal inbound message with auto-reply enabled
        success, response = self.run_test(
            "POST /api/wa/simulate-inbound (normal message)",
            "POST",
            "/api/wa/simulate-inbound",
            200,
            data={
                "from_phone": "+628123456789",
                "text": "Hello, I need a travel booking",
                "name": "Test Customer"
            }
        )
        if success:
            self.log(f"Inbound processed: conversation_id={response.get('conversation_id')}, lead_created={response.get('lead_created')}")
        
        # Test 2: Another message to same number (should update existing conversation)
        success, response = self.run_test(
            "POST /api/wa/simulate-inbound (same number, update conversation)",
            "POST",
            "/api/wa/simulate-inbound",
            200,
            data={
                "from_phone": "+628123456789",
                "text": "Follow-up message",
                "name": "Test Customer"
            }
        )
        
        # Test 3: Different number
        success, response = self.run_test(
            "POST /api/wa/simulate-inbound (different number)",
            "POST",
            "/api/wa/simulate-inbound",
            200,
            data={
                "from_phone": "+628987654321",
                "text": "Another customer inquiry",
                "name": "Another Customer"
            }
        )
        
        # Test 4: Minimal payload (test edge case)
        success, response = self.run_test(
            "POST /api/wa/simulate-inbound (minimal payload)",
            "POST",
            "/api/wa/simulate-inbound",
            200,
            data={
                "from_phone": "+628111222333",
                "text": "Minimal"
            }
        )

    def test_wa_test_send(self):
        """Test WhatsApp test-send (mock send)"""
        self.log("\n=== WA TEST-SEND TESTS (MOCK) ===", "SECTION")
        
        success, response = self.run_test(
            "POST /api/wa/test-send (mock send)",
            "POST",
            "/api/wa/test-send",
            200,
            data={
                "to_phone": "+628123456789",
                "text": "Test message from regression test"
            }
        )
        if success:
            self.log(f"Test send result: status={response.get('status')}, provider={response.get('provider')}, ok={response.get('ok')}")
            if response.get('provider') == 'mock':
                self.log("✓ WhatsApp send is MOCK as expected (by design)")

    def test_wa_templates(self):
        """Test WhatsApp templates CRUD"""
        self.log("\n=== WA TEMPLATES TESTS ===", "SECTION")
        
        # GET templates
        success, templates = self.run_test(
            "GET /api/wa/templates",
            "GET",
            "/api/wa/templates",
            200
        )
        if success:
            self.log(f"Templates retrieved: {len(templates)} templates")
        
        # PUT new template
        test_template_key = f"test_template_{datetime.now().strftime('%H%M%S')}"
        success, template = self.run_test(
            f"PUT /api/wa/templates/{test_template_key}",
            "PUT",
            f"/api/wa/templates/{test_template_key}",
            200,
            data={
                "name": "Test Template",
                "language": "id",
                "category": "utility",
                "body": "This is a test template body with {variable}"
            }
        )
        if success:
            self.log(f"Template created: key={template.get('key')}")
        
        # DELETE template
        success, response = self.run_test(
            f"DELETE /api/wa/templates/{test_template_key}",
            "DELETE",
            f"/api/wa/templates/{test_template_key}",
            [200, 204]
        )
        if success:
            self.log(f"Template deleted: {test_template_key}")

    def test_wa_webhook(self):
        """Test WhatsApp webhook verification and receive"""
        self.log("\n=== WA WEBHOOK TESTS ===", "SECTION")
        
        # GET webhook verification (with correct token)
        success, response = self.run_test(
            "GET /api/wa/webhook (verification with correct token)",
            "GET",
            "/api/wa/webhook",
            200,
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "rahaza-wa-verify",
                "hub.challenge": "test_challenge_123"
            }
        )
        
        # GET webhook verification (with wrong token - should be 403, not 500)
        success, response = self.run_test(
            "GET /api/wa/webhook (verification with wrong token)",
            "GET",
            "/api/wa/webhook",
            403,
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token",
                "hub.challenge": "test_challenge_123"
            }
        )
        
        # POST webhook (minimal inbound payload)
        success, response = self.run_test(
            "POST /api/wa/webhook (minimal inbound)",
            "POST",
            "/api/wa/webhook",
            200,
            data={
                "entry": [{
                    "changes": [{
                        "value": {
                            "messages": [{
                                "from": "628123456789",
                                "type": "text",
                                "text": {"body": "Test webhook message"}
                            }],
                            "contacts": [{
                                "wa_id": "628123456789",
                                "profile": {"name": "Webhook Test"}
                            }]
                        }
                    }]
                }]
            }
        )
        if success:
            self.log(f"Webhook processed: received={response.get('received')}")

    def test_adversarial(self):
        """Test adversarial cases - should return 4xx, NOT 5xx"""
        self.log("\n=== ADVERSARIAL TESTS (NO 5XX) ===", "SECTION")
        
        # Malformed simulate-inbound payloads
        self.run_test(
            "POST /api/wa/simulate-inbound (empty payload)",
            "POST",
            "/api/wa/simulate-inbound",
            [400, 422],
            data={},
            allow_4xx=True
        )
        
        self.run_test(
            "POST /api/wa/simulate-inbound (missing text)",
            "POST",
            "/api/wa/simulate-inbound",
            [200, 400, 422],  # May return 200 with ignored status
            data={"from_phone": "+628123456789"},
            allow_4xx=True
        )
        
        self.run_test(
            "POST /api/wa/simulate-inbound (invalid phone type)",
            "POST",
            "/api/wa/simulate-inbound",
            [200, 400, 422],
            data={"from_phone": 12345, "text": "test"},
            allow_4xx=True
        )
        
        # Malformed config update
        self.run_test(
            "PATCH /api/wa/config (invalid provider)",
            "PATCH",
            "/api/wa/config",
            400,
            data={"provider": "invalid_provider"},
            allow_4xx=True
        )
        
        self.run_test(
            "PATCH /api/wa/config (bad type)",
            "PATCH",
            "/api/wa/config",
            [400, 422],
            data={"auto_reply_enabled": "not_a_boolean"},
            allow_4xx=True
        )
        
        # Malformed test-send
        self.run_test(
            "POST /api/wa/test-send (empty payload)",
            "POST",
            "/api/wa/test-send",
            [400, 422],
            data={},
            allow_4xx=True
        )

    def test_general_smoke(self):
        """General smoke tests - no wider regression"""
        self.log("\n=== GENERAL SMOKE TESTS ===", "SECTION")
        
        self.run_test(
            "GET /api/ (health check)",
            "GET",
            "/api/",
            200
        )
        
        self.run_test(
            "GET /api/dashboard",
            "GET",
            "/api/dashboard",
            200
        )
        
        self.run_test(
            "GET /api/bookings",
            "GET",
            "/api/bookings",
            200
        )
        
        self.run_test(
            "GET /api/customers",
            "GET",
            "/api/customers",
            200
        )

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "="*80, "SECTION")
        self.log("TEST SUMMARY", "SECTION")
        self.log("="*80, "SECTION")
        self.log(f"Total tests run: {self.tests_run}")
        self.log(f"Tests passed: {self.tests_passed}")
        self.log(f"Tests failed: {self.tests_failed}")
        self.log(f"Success rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.five_xx_errors:
            self.log(f"\n🚨 CRITICAL: {len(self.five_xx_errors)} 5XX ERRORS DETECTED!", "CRITICAL")
            for err in self.five_xx_errors:
                self.log(f"  - {err['test']}: {err['endpoint']} -> {err['status']}", "CRITICAL")
        else:
            self.log("\n✅ NO 5XX ERRORS - Regression test PASSED!", "SUCCESS")
        
        if self.failures:
            self.log(f"\nFailed tests ({len(self.failures)}):", "ERROR")
            for fail in self.failures:
                self.log(f"  - {fail['test']}: {fail['reason']}", "ERROR")
        
        return 0 if not self.five_xx_errors and self.tests_passed == self.tests_run else 1

def main():
    tester = WhatsAppRegressionTester()
    
    # Run all tests
    if not tester.test_login():
        return 1
    
    tester.test_wa_config()
    tester.test_wa_simulate_inbound()  # CRITICAL - contains the changed code
    tester.test_wa_test_send()
    tester.test_wa_templates()
    tester.test_wa_webhook()
    tester.test_adversarial()
    tester.test_general_smoke()
    
    return tester.print_summary()

if __name__ == "__main__":
    sys.exit(main())

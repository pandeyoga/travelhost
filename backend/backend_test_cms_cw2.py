"""
Backend API Testing for CMS CW2 Features
Tests CMS-05 through CMS-09 plus defects A1, A2, A3
"""
import requests
import sys
from datetime import datetime, timedelta
from typing import Dict, Any

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

class CMSTestRunner:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.token = None
        self.errors = []
        self.test_artifacts = []

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

    def login(self, email: str = "owner@demo.local", password: str = "demo12345"):
        """Login as owner"""
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
                self.log(f"Login successful", "PASS")
                return True
            else:
                self.log(f"Login failed: {resp.status_code} - {resp.text}", "FAIL")
                return False
        except Exception as e:
            self.log(f"Login exception: {e}", "FAIL")
            return False

    def get_headers(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def test_cms_05_draft_status(self):
        """CMS-05: Test draft status and preview tokens"""
        self.log("\n=== CMS-05: DRAFT STATUS & PREVIEW TOKENS ===", "INFO")
        
        # Get an existing article
        resp = requests.get(f"{BASE_URL}/content/articles", headers=self.get_headers(), timeout=10)
        self.test("Get articles list", resp.status_code == 200, f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            articles = resp.json()
            if len(articles) > 0:
                article_id = articles[0].get("id")
                article_slug = articles[0].get("slug")
                
                # Test changing status to draft
                update_resp = requests.put(
                    f"{BASE_URL}/content/articles/{article_id}",
                    headers=self.get_headers(),
                    json={"status": "draft"},
                    timeout=10
                )
                self.test("Update article to draft", update_resp.status_code == 200, f"Status: {update_resp.status_code}")
                
                # Verify article is NOT in public list
                public_resp = requests.get(f"{BASE_URL}/public/articles/{article_slug}", timeout=10)
                self.test("Draft article not in public", public_resp.status_code == 404, f"Status: {public_resp.status_code}")
                
                # Test preview token generation
                token_resp = requests.post(
                    f"{BASE_URL}/content/articles/{article_id}/preview-token",
                    headers=self.get_headers(),
                    timeout=10
                )
                self.test("Generate preview token", token_resp.status_code == 200, f"Status: {token_resp.status_code}")
                
                if token_resp.status_code == 200:
                    preview_token = token_resp.json().get("token")
                    # Test preview access with token
                    preview_resp = requests.get(
                        f"{BASE_URL}/public/articles/{article_slug}",
                        params={"preview": preview_token},
                        timeout=10
                    )
                    self.test("Access draft with preview token", preview_resp.status_code == 200, f"Status: {preview_resp.status_code}")
                
                # Restore to published
                requests.put(
                    f"{BASE_URL}/content/articles/{article_id}",
                    headers=self.get_headers(),
                    json={"status": "published"},
                    timeout=10
                )

    def test_cms_05_scheduled_publish(self):
        """CMS-05: Test scheduled publishing"""
        self.log("\n=== CMS-05: SCHEDULED PUBLISHING ===", "INFO")
        
        # Get an article
        resp = requests.get(f"{BASE_URL}/content/articles", headers=self.get_headers(), timeout=10)
        if resp.status_code == 200:
            articles = resp.json()
            if len(articles) > 0:
                article_id = articles[0].get("id")
                
                # Test scheduled status without publish_at (should fail)
                future_time = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
                
                update_resp = requests.put(
                    f"{BASE_URL}/content/articles/{article_id}",
                    headers=self.get_headers(),
                    json={"status": "scheduled", "publish_at": future_time},
                    timeout=10
                )
                self.test("Schedule article for future", update_resp.status_code == 200, f"Status: {update_resp.status_code}")
                
                # Restore
                requests.put(
                    f"{BASE_URL}/content/articles/{article_id}",
                    headers=self.get_headers(),
                    json={"status": "published"},
                    timeout=10
                )

    def test_cms_06_i18n(self):
        """CMS-06: Test bilingual content"""
        self.log("\n=== CMS-06: BILINGUAL CONTENT (ID/EN) ===", "INFO")
        
        # Get articles with lang=en
        resp = requests.get(f"{BASE_URL}/public/articles", params={"lang": "en"}, timeout=10)
        self.test("Get articles with lang=en", resp.status_code == 200, f"Status: {resp.status_code}")
        
        # Get destinations with lang=en
        resp = requests.get(f"{BASE_URL}/public/destinations", params={"lang": "en"}, timeout=10)
        self.test("Get destinations with lang=en", resp.status_code == 200, f"Status: {resp.status_code}")

    def test_a1_packages_public(self):
        """A1: Test public package pages"""
        self.log("\n=== A1: PUBLIC PACKAGE PAGES ===", "INFO")
        
        # Get packages list
        resp = requests.get(f"{BASE_URL}/public/packages", timeout=10)
        self.test("Get public packages list", resp.status_code == 200, f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            packages = resp.json()
            if len(packages) > 0:
                package_slug = packages[0].get("slug")
                # Get package detail
                detail_resp = requests.get(f"{BASE_URL}/public/packages/{package_slug}", timeout=10)
                self.test("Get package detail by slug", detail_resp.status_code == 200, f"Status: {detail_resp.status_code}")

    def test_a3_promos_public(self):
        """A3: Test public promo page"""
        self.log("\n=== A3: PUBLIC PROMO PAGE ===", "INFO")
        
        # Get promos list
        resp = requests.get(f"{BASE_URL}/public/promos", timeout=10)
        self.test("Get public promos list", resp.status_code == 200, f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            promos = resp.json()
            self.test("Promos list not empty", len(promos) > 0, "No promos found")
            
            if len(promos) > 0:
                promo = promos[0]
                self.test("Promo has code", "code" in promo, "Missing code field")
                self.test("Promo has discount", "discount_percent" in promo or "discount_amount" in promo, "Missing discount")

    def test_cms_07_reviews(self):
        """CMS-07: Test review funnel"""
        self.log("\n=== CMS-07: REVIEW FUNNEL ===", "INFO")
        
        # Get review requests
        resp = requests.get(f"{BASE_URL}/reviews/requests", headers=self.get_headers(), timeout=10)
        self.test("Get review requests", resp.status_code == 200, f"Status: {resp.status_code}")
        
        # Get pending reviews
        resp = requests.get(f"{BASE_URL}/reviews/pending", headers=self.get_headers(), timeout=10)
        self.test("Get pending reviews", resp.status_code == 200, f"Status: {resp.status_code}")

    def test_cms_08_analytics(self):
        """CMS-08: Test content analytics"""
        self.log("\n=== CMS-08: CONTENT ANALYTICS ===", "INFO")
        
        # Get content analytics
        resp = requests.get(f"{BASE_URL}/content/analytics/top", headers=self.get_headers(), timeout=10)
        self.test("Get content analytics", resp.status_code == 200, f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            self.test("Analytics has summary", "summary" in data, "Missing summary")

    def test_cms_09_richtext(self):
        """CMS-09: Test rich text sanitization"""
        self.log("\n=== CMS-09: RICH TEXT SANITIZATION ===", "INFO")
        
        # Get an article with body
        resp = requests.get(f"{BASE_URL}/public/articles", timeout=10)
        if resp.status_code == 200:
            articles = resp.json()
            if len(articles) > 0:
                article = articles[0]
                body = article.get("body", "")
                self.test("Article has body", len(body) > 0, "Empty body")
                self.test("Body does not contain script tags", "<script" not in body.lower(), "Script tag found in body")

    def test_a2_promo_rules(self):
        """A2: Test promo rules fields"""
        self.log("\n=== A2: PROMO RULES FIELDS ===", "INFO")
        
        # Get promos from admin
        resp = requests.get(f"{BASE_URL}/content/promos", headers=self.get_headers(), timeout=10)
        self.test("Get admin promos list", resp.status_code == 200, f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            promos = resp.json()
            if len(promos) > 0:
                promo = promos[0]
                # Check for rule fields
                rule_fields = ["valid_from", "valid_until", "min_days", "min_amount", "max_uses", "used_count"]
                for field in rule_fields:
                    has_field = field in promo
                    self.test(f"Promo has {field} field", has_field, f"Missing {field}")

    def test_rbac_cms_access(self):
        """Test RBAC for CMS access"""
        self.log("\n=== RBAC: CMS ACCESS CONTROL ===", "INFO")
        
        # Test driver should NOT access CMS
        driver_resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": "driver@demo.local", "password": "demo12345"},
            timeout=10
        )
        
        if driver_resp.status_code == 200:
            driver_token = driver_resp.json().get("token")
            cms_resp = requests.get(
                f"{BASE_URL}/content/articles",
                headers={"Authorization": f"Bearer {driver_token}"},
                timeout=10
            )
            self.test("Driver blocked from CMS", cms_resp.status_code == 403, f"Status: {cms_resp.status_code}")
        
        # Test marketing should access CMS
        marketing_resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": "marketing@demo.local", "password": "demo12345"},
            timeout=10
        )
        
        if marketing_resp.status_code == 200:
            marketing_token = marketing_resp.json().get("token")
            cms_resp = requests.get(
                f"{BASE_URL}/content/articles",
                headers={"Authorization": f"Bearer {marketing_token}"},
                timeout=10
            )
            self.test("Marketing can access CMS", cms_resp.status_code == 200, f"Status: {cms_resp.status_code}")

    def run_all_tests(self):
        """Run all CMS tests"""
        self.log("=" * 60, "INFO")
        self.log("STARTING CMS CW2 BACKEND API TESTS", "INFO")
        self.log("=" * 60, "INFO")
        
        if not self.login():
            self.log("Login failed, cannot continue tests", "FAIL")
            return False
        
        # Run all test suites
        self.test_cms_05_draft_status()
        self.test_cms_05_scheduled_publish()
        self.test_cms_06_i18n()
        self.test_a1_packages_public()
        self.test_a3_promos_public()
        self.test_cms_07_reviews()
        self.test_cms_08_analytics()
        self.test_cms_09_richtext()
        self.test_a2_promo_rules()
        self.test_rbac_cms_access()
        
        # Print summary
        self.log("\n" + "=" * 60, "INFO")
        self.log("TEST SUMMARY", "INFO")
        self.log("=" * 60, "INFO")
        self.log(f"Total Tests: {self.tests_run}", "INFO")
        self.log(f"Passed: {self.tests_passed}", "PASS")
        self.log(f"Failed: {self.tests_failed}", "FAIL" if self.tests_failed > 0 else "INFO")
        
        if self.errors:
            self.log("\nFailed Tests:", "FAIL")
            for error in self.errors:
                self.log(f"  - {error}", "FAIL")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\nSuccess Rate: {success_rate:.1f}%", "PASS" if success_rate >= 80 else "FAIL")
        
        return self.tests_failed == 0

def main():
    runner = CMSTestRunner()
    success = runner.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

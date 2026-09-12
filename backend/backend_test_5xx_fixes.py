"""
Backend Testing for 5xx-Robustness Fixes (EXPORT-1, R6-4, R6-5)
Tests that bad input returns 4xx (client error), NOT 500 (server crash).
Also verifies normal usage still works (no regression).
"""
import requests
import sys
from typing import Dict, Any

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

class TestRunner:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.token = None
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
                token = data.get("token")
                if token:
                    self.token = token
                    self.log(f"Login successful", "PASS")
                    return True
                else:
                    self.log(f"Login response missing token", "FAIL")
                    return False
            else:
                self.log(f"Login failed: {resp.status_code} - {resp.text}", "FAIL")
                return False
        except Exception as e:
            self.log(f"Login exception: {e}", "FAIL")
            return False

    def get(self, endpoint: str, params: Dict = None) -> requests.Response:
        """GET request with auth"""
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        return requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params, timeout=10)

    def post(self, endpoint: str, data: Dict) -> requests.Response:
        """POST request with auth"""
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        return requests.post(f"{BASE_URL}/{endpoint}", headers=headers, json=data, timeout=10)

    def patch(self, endpoint: str, data: Dict) -> requests.Response:
        """PATCH request with auth"""
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        return requests.patch(f"{BASE_URL}/{endpoint}", headers=headers, json=data, timeout=10)

    def test_export1_fix(self):
        """EXPORT-1 FIX: Quotation PDF with special/markup characters should return 200, NOT 500"""
        self.log("\n=== EXPORT-1 FIX: QUOTATION PDF WITH SPECIAL CHARACTERS ===", "INFO")
        
        # Create quotation with special characters in fields
        self.log("Creating quotation with special/markup characters...")
        resp = self.post("quotations", {
            "customer_name": "A<b>&</b>",
            "destination": "Bali <&>",
            "trip_date": "2025-09-15",
            "pax": 10,
            "notes": "a & b < c",
            "items": [
                {"label": "Sewa <&>", "amount": 100000}
            ],
            "valid_days": 7
        })
        
        if resp.status_code not in [200, 201]:
            self.log(f"Failed to create quotation: {resp.status_code} - {resp.text}", "FAIL")
            self.test("EXPORT-1: Create quotation with special chars", False, 
                     f"Failed to create quotation: {resp.status_code}")
            return
        
        quo = resp.json()
        quo_id = quo.get("id")
        self.log(f"Created quotation: {quo_id}")
        self.test_data["export1_quo_id"] = quo_id
        
        # Now try to get PDF - should return 200 with valid PDF, NOT 500
        self.log(f"Getting PDF for quotation {quo_id}...")
        resp = self.get(f"quotations/{quo_id}/pdf")
        
        self.test(
            "EXPORT-1: PDF generation returns 200 (not 500)",
            resp.status_code == 200,
            f"Expected 200, got {resp.status_code}. Response: {resp.text[:200]}"
        )
        
        if resp.status_code == 200:
            # Verify it's actually a PDF
            content_type = resp.headers.get("Content-Type", "")
            self.test(
                "EXPORT-1: Response is application/pdf",
                "application/pdf" in content_type,
                f"Expected application/pdf, got {content_type}"
            )
            
            # Verify PDF has content
            self.test(
                "EXPORT-1: PDF has content (>1KB)",
                len(resp.content) > 1024,
                f"PDF size: {len(resp.content)} bytes"
            )

    def test_export1_regression(self):
        """EXPORT-1 REGRESSION: Normal quotation PDF should still work"""
        self.log("\n=== EXPORT-1 REGRESSION: NORMAL QUOTATION PDF ===", "INFO")
        
        # Create normal quotation with plain text
        self.log("Creating normal quotation with plain text...")
        resp = self.post("quotations", {
            "customer_name": "John Doe",
            "destination": "Bandung",
            "trip_date": "2025-09-20",
            "pax": 5,
            "notes": "Regular trip to Bandung",
            "items": [
                {"label": "Sewa Bus", "amount": 500000}
            ],
            "valid_days": 7
        })
        
        if resp.status_code not in [200, 201]:
            self.log(f"Failed to create normal quotation: {resp.status_code} - {resp.text}", "FAIL")
            self.test("EXPORT-1 REGRESSION: Create normal quotation", False, 
                     f"Failed: {resp.status_code}")
            return
        
        quo = resp.json()
        quo_id = quo.get("id")
        self.log(f"Created normal quotation: {quo_id}")
        
        # Get PDF - should work fine
        self.log(f"Getting PDF for normal quotation {quo_id}...")
        resp = self.get(f"quotations/{quo_id}/pdf")
        
        self.test(
            "EXPORT-1 REGRESSION: Normal PDF returns 200",
            resp.status_code == 200,
            f"Expected 200, got {resp.status_code}"
        )
        
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "")
            self.test(
                "EXPORT-1 REGRESSION: Response is valid PDF",
                "application/pdf" in content_type and len(resp.content) > 1024,
                f"Content-Type: {content_type}, Size: {len(resp.content)}"
            )

    def test_r6_4_fix(self):
        """R6-4 FIX: Segment preview with malformed criteria should return 400/200, NOT 500"""
        self.log("\n=== R6-4 FIX: SEGMENT PREVIEW WITH MALFORMED CRITERIA ===", "INFO")
        
        # Create segment with malformed criteria
        self.log("Creating segment with malformed criteria...")
        resp = self.post("crm/segments", {
            "name": "Bad Segment Test",
            "audience": "customer",
            "criteria": {
                "and": "not-a-list",  # Should be a list
                "$weird": {
                    "op": "??",  # Invalid operator
                    "value": [1, 2]
                }
            },
            "description": "Test segment with malformed criteria"
        })
        
        if resp.status_code not in [200, 201]:
            self.log(f"Failed to create segment: {resp.status_code} - {resp.text}", "FAIL")
            self.test("R6-4: Create segment with malformed criteria", False, 
                     f"Failed: {resp.status_code}")
            return
        
        seg = resp.json()
        seg_id = seg.get("id")
        self.log(f"Created segment: {seg_id}")
        self.test_data["r6_4_seg_id"] = seg_id
        
        # Try to preview - should NOT return 500
        self.log(f"Getting preview for segment {seg_id}...")
        resp = self.get(f"crm/segments/{seg_id}/preview")
        
        self.test(
            "R6-4: Preview returns 200 or 400 (not 500)",
            resp.status_code in [200, 400],
            f"Expected 200 or 400, got {resp.status_code}. Response: {resp.text[:200]}"
        )
        
        if resp.status_code == 400:
            # If 400, should have clear error message
            resp_text = resp.text.lower()
            self.test(
                "R6-4: Error message mentions 'kriteria' or 'tidak valid'",
                "kriteria" in resp_text or "tidak valid" in resp_text or "invalid" in resp_text,
                f"Response: {resp.text[:200]}"
            )

    def test_r6_4_regression(self):
        """R6-4 REGRESSION: Normal segment preview should still work"""
        self.log("\n=== R6-4 REGRESSION: NORMAL SEGMENT PREVIEW ===", "INFO")
        
        # Create normal segment with valid criteria
        self.log("Creating normal segment with valid criteria...")
        resp = self.post("crm/segments", {
            "name": "Normal Segment Test",
            "audience": "customer",
            "criteria": {
                "and": [
                    {"field": "name", "op": "contains", "value": "test"}
                ]
            },
            "description": "Test segment with valid criteria"
        })
        
        if resp.status_code not in [200, 201]:
            self.log(f"Failed to create normal segment: {resp.status_code} - {resp.text}", "FAIL")
            self.test("R6-4 REGRESSION: Create normal segment", False, 
                     f"Failed: {resp.status_code}")
            return
        
        seg = resp.json()
        seg_id = seg.get("id")
        self.log(f"Created normal segment: {seg_id}")
        
        # Get preview - should work fine
        self.log(f"Getting preview for normal segment {seg_id}...")
        resp = self.get(f"crm/segments/{seg_id}/preview")
        
        self.test(
            "R6-4 REGRESSION: Normal preview returns 200",
            resp.status_code == 200,
            f"Expected 200, got {resp.status_code}. Response: {resp.text[:200]}"
        )
        
        if resp.status_code == 200:
            data = resp.json()
            self.test(
                "R6-4 REGRESSION: Preview has count and sample fields",
                "count" in data and "sample" in data,
                f"Response keys: {list(data.keys())}"
            )

    def test_r6_5_fix_destinations(self):
        """R6-5 FIX: Destinations with non-numeric lat/lng should return 400, NOT 500"""
        self.log("\n=== R6-5 FIX: DESTINATIONS WITH NON-NUMERIC LAT/LNG ===", "INFO")
        
        # Try to create destination with non-numeric lat/lng
        self.log("Creating destination with non-numeric lat/lng...")
        resp = self.post("content/destinations", {
            "name": "Test Destination",
            "slug": "t-adv-x-test",
            "lat": "abc",  # Non-numeric
            "lng": "xyz"   # Non-numeric
        })
        
        self.test(
            "R6-5: Non-numeric lat/lng returns 400 (not 500)",
            resp.status_code == 400,
            f"Expected 400, got {resp.status_code}. Response: {resp.text[:200]}"
        )
        
        if resp.status_code == 400:
            resp_text = resp.text.lower()
            self.test(
                "R6-5: Error message mentions field and 'angka' or 'numeric'",
                ("lat" in resp_text or "lng" in resp_text) and ("angka" in resp_text or "numeric" in resp_text),
                f"Response: {resp.text[:200]}"
            )

    def test_r6_5_fix_packages(self):
        """R6-5 FIX: Packages with non-numeric price should return 400, NOT 500"""
        self.log("\n=== R6-5 FIX: PACKAGES WITH NON-NUMERIC PRICE ===", "INFO")
        
        # Try to create package with non-numeric price
        self.log("Creating package with non-numeric price...")
        resp = self.post("content/packages", {
            "name": "Test Package",
            "slug": "test-pkg-adv",
            "price_from": "gratis",  # Non-numeric
            "destination": "Bali"
        })
        
        self.test(
            "R6-5: Non-numeric price returns 400 (not 500)",
            resp.status_code == 400,
            f"Expected 400, got {resp.status_code}. Response: {resp.text[:200]}"
        )
        
        if resp.status_code == 400:
            resp_text = resp.text.lower()
            self.test(
                "R6-5: Error message mentions field and 'angka' or 'numeric'",
                "price" in resp_text and ("angka" in resp_text or "numeric" in resp_text),
                f"Response: {resp.text[:200]}"
            )

    def test_r6_5_regression(self):
        """R6-5 REGRESSION: Normal destinations/packages with valid numeric values should work"""
        self.log("\n=== R6-5 REGRESSION: NORMAL DESTINATIONS WITH VALID LAT/LNG ===", "INFO")
        
        # Create destination with valid numeric lat/lng
        self.log("Creating destination with valid numeric lat/lng...")
        resp = self.post("content/destinations", {
            "name": "Jakarta Test",
            "slug": "jakarta-test-valid",
            "lat": -6.9,
            "lng": 107.6,
            "description": "Test destination with valid coordinates"
        })
        
        self.test(
            "R6-5 REGRESSION: Valid lat/lng returns 200/201",
            resp.status_code in [200, 201],
            f"Expected 200/201, got {resp.status_code}. Response: {resp.text[:200]}"
        )
        
        if resp.status_code in [200, 201]:
            dest = resp.json()
            self.test(
                "R6-5 REGRESSION: Destination has correct lat/lng",
                dest.get("lat") == -6.9 and dest.get("lng") == 107.6,
                f"lat: {dest.get('lat')}, lng: {dest.get('lng')}"
            )
        
        # Create package with valid numeric price
        self.log("\n=== R6-5 REGRESSION: NORMAL PACKAGES WITH VALID PRICE ===", "INFO")
        self.log("Creating package with valid numeric price...")
        resp = self.post("content/packages", {
            "name": "Bali Package Test",
            "slug": "bali-pkg-test-valid",
            "price_from": 5000000,
            "destination": "Bali",
            "days": 3
        })
        
        self.test(
            "R6-5 REGRESSION: Valid price returns 200/201",
            resp.status_code in [200, 201],
            f"Expected 200/201, got {resp.status_code}. Response: {resp.text[:200]}"
        )
        
        if resp.status_code in [200, 201]:
            pkg = resp.json()
            self.test(
                "R6-5 REGRESSION: Package has correct price",
                pkg.get("price_from") == 5000000,
                f"price_from: {pkg.get('price_from')}"
            )

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "=" * 60, "INFO")
        self.log(f"TESTS RUN: {self.tests_run}", "INFO")
        self.log(f"TESTS PASSED: {self.tests_passed}", "PASS")
        self.log(f"TESTS FAILED: {self.tests_failed}", "FAIL" if self.tests_failed > 0 else "INFO")
        
        if self.tests_run > 0:
            success_rate = (self.tests_passed / self.tests_run) * 100
            self.log(f"SUCCESS RATE: {success_rate:.1f}%", "INFO")
        
        self.log("=" * 60, "INFO")
        
        if self.errors:
            self.log("\nFAILED TESTS:", "FAIL")
            for error in self.errors:
                self.log(f"  - {error}", "FAIL")
        
        return 0 if self.tests_failed == 0 else 1


def main():
    runner = TestRunner()
    
    # Login as owner
    runner.log("=== LOGGING IN ===", "INFO")
    if not runner.login("owner@demo.local", "demo12345"):
        runner.log("Login failed - cannot proceed with tests", "FAIL")
        return 1
    
    # Run tests for the 3 fixes + regressions
    runner.test_export1_fix()
    runner.test_export1_regression()
    runner.test_r6_4_fix()
    runner.test_r6_4_regression()
    runner.test_r6_5_fix_destinations()
    runner.test_r6_5_fix_packages()
    runner.test_r6_5_regression()
    
    # Print summary
    return runner.print_summary()


if __name__ == "__main__":
    sys.exit(main())

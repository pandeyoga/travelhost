"""
Backend Testing for RahazaTrans ERP - Calendar Export Feature

Tests calendar export enhancements:
- Export to Excel (xlsx)
- Export to PDF
- Auth protection
- Response validation (content-type, size)

Demo credentials: owner@demo.local / demo12345
Backend URL: https://trip-route-buttons.preview.emergentagent.com/api
"""

import requests
import sys
from datetime import datetime

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

class CalendarExportTester:
    def __init__(self):
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []
        
    def login(self, email="owner@demo.local", password="demo12345"):
        """Authenticate and get token"""
        print(f"\n{Colors.BLUE}=== AUTHENTICATION ==={Colors.END}")
        try:
            response = requests.post(
                f"{BASE_URL}/auth/login",
                json={"email": email, "password": password},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("token")
                if self.token:
                    print(f"{Colors.GREEN}✓ Login successful as {email}{Colors.END}")
                    return True
                else:
                    print(f"{Colors.RED}✗ Login failed: No token in response{Colors.END}")
                    return False
            else:
                print(f"{Colors.RED}✗ Login failed: {response.status_code} - {response.text[:200]}{Colors.END}")
                return False
        except Exception as e:
            print(f"{Colors.RED}✗ Login error: {str(e)}{Colors.END}")
            return False
    
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}"
        }
    
    def test_export_excel(self):
        """Test Excel export"""
        self.tests_run += 1
        print(f"\n{Colors.BLUE}Test #{self.tests_run}: Export to Excel{Colors.END}")
        
        try:
            response = requests.get(
                f"{BASE_URL}/bookings/calendar/export?month=2026-08&format=excel",
                headers=self.headers(),
                timeout=15
            )
            
            if response.status_code != 200:
                print(f"{Colors.RED}✗ FAILED - Expected 200, got {response.status_code}{Colors.END}")
                print(f"  Response: {response.text[:300]}")
                self.tests_failed += 1
                self.failures.append(f"Excel export: Expected 200, got {response.status_code}")
                return False
            
            # Check content-type
            content_type = response.headers.get("content-type", "")
            if "spreadsheet" not in content_type and "excel" not in content_type and "xlsx" not in content_type:
                print(f"{Colors.RED}✗ FAILED - Invalid content-type: {content_type}{Colors.END}")
                self.tests_failed += 1
                self.failures.append(f"Excel export: Invalid content-type {content_type}")
                return False
            
            # Check size
            size = len(response.content)
            if size == 0:
                print(f"{Colors.RED}✗ FAILED - Empty response (size=0){Colors.END}")
                self.tests_failed += 1
                self.failures.append(f"Excel export: Empty response")
                return False
            
            print(f"{Colors.GREEN}✓ PASSED - Excel export successful{Colors.END}")
            print(f"  Content-Type: {content_type}")
            print(f"  Size: {size} bytes")
            self.tests_passed += 1
            return True
            
        except Exception as e:
            print(f"{Colors.RED}✗ FAILED - Error: {str(e)}{Colors.END}")
            self.tests_failed += 1
            self.failures.append(f"Excel export: {str(e)}")
            return False
    
    def test_export_pdf(self):
        """Test PDF export"""
        self.tests_run += 1
        print(f"\n{Colors.BLUE}Test #{self.tests_run}: Export to PDF{Colors.END}")
        
        try:
            response = requests.get(
                f"{BASE_URL}/bookings/calendar/export?month=2026-08&format=pdf",
                headers=self.headers(),
                timeout=15
            )
            
            if response.status_code != 200:
                print(f"{Colors.RED}✗ FAILED - Expected 200, got {response.status_code}{Colors.END}")
                print(f"  Response: {response.text[:300]}")
                self.tests_failed += 1
                self.failures.append(f"PDF export: Expected 200, got {response.status_code}")
                return False
            
            # Check content-type
            content_type = response.headers.get("content-type", "")
            if "pdf" not in content_type.lower():
                print(f"{Colors.RED}✗ FAILED - Invalid content-type: {content_type}{Colors.END}")
                self.tests_failed += 1
                self.failures.append(f"PDF export: Invalid content-type {content_type}")
                return False
            
            # Check size
            size = len(response.content)
            if size == 0:
                print(f"{Colors.RED}✗ FAILED - Empty response (size=0){Colors.END}")
                self.tests_failed += 1
                self.failures.append(f"PDF export: Empty response")
                return False
            
            # Check PDF magic bytes
            if not response.content.startswith(b'%PDF'):
                print(f"{Colors.RED}✗ FAILED - Not a valid PDF file{Colors.END}")
                self.tests_failed += 1
                self.failures.append(f"PDF export: Invalid PDF format")
                return False
            
            print(f"{Colors.GREEN}✓ PASSED - PDF export successful{Colors.END}")
            print(f"  Content-Type: {content_type}")
            print(f"  Size: {size} bytes")
            self.tests_passed += 1
            return True
            
        except Exception as e:
            print(f"{Colors.RED}✗ FAILED - Error: {str(e)}{Colors.END}")
            self.tests_failed += 1
            self.failures.append(f"PDF export: {str(e)}")
            return False
    
    def test_export_auth_protection(self):
        """Test that export endpoint requires authentication"""
        self.tests_run += 1
        print(f"\n{Colors.BLUE}Test #{self.tests_run}: Export Auth Protection{Colors.END}")
        
        try:
            response = requests.get(
                f"{BASE_URL}/bookings/calendar/export?month=2026-08&format=excel",
                timeout=10
            )
            
            if response.status_code in [401, 403]:
                print(f"{Colors.GREEN}✓ PASSED - Endpoint protected (status {response.status_code}){Colors.END}")
                self.tests_passed += 1
                return True
            else:
                print(f"{Colors.RED}✗ FAILED - Expected 401/403, got {response.status_code}{Colors.END}")
                print(f"  Response: {response.text[:300]}")
                self.tests_failed += 1
                self.failures.append(f"Auth protection: Expected 401/403, got {response.status_code}")
                return False
            
        except Exception as e:
            print(f"{Colors.RED}✗ FAILED - Error: {str(e)}{Colors.END}")
            self.tests_failed += 1
            self.failures.append(f"Auth protection: {str(e)}")
            return False
    
    def test_calendar_endpoint(self):
        """Test basic calendar endpoint still works"""
        self.tests_run += 1
        print(f"\n{Colors.BLUE}Test #{self.tests_run}: Calendar Endpoint (Regression){Colors.END}")
        
        try:
            response = requests.get(
                f"{BASE_URL}/bookings/calendar?month=2026-08",
                headers=self.headers(),
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"{Colors.RED}✗ FAILED - Expected 200, got {response.status_code}{Colors.END}")
                print(f"  Response: {response.text[:300]}")
                self.tests_failed += 1
                self.failures.append(f"Calendar endpoint: Expected 200, got {response.status_code}")
                return False
            
            data = response.json()
            if not isinstance(data, list):
                print(f"{Colors.RED}✗ FAILED - Expected list, got {type(data)}{Colors.END}")
                self.tests_failed += 1
                self.failures.append(f"Calendar endpoint: Invalid response type")
                return False
            
            print(f"{Colors.GREEN}✓ PASSED - Calendar endpoint working{Colors.END}")
            print(f"  Returned {len(data)} bookings")
            self.tests_passed += 1
            return True
            
        except Exception as e:
            print(f"{Colors.RED}✗ FAILED - Error: {str(e)}{Colors.END}")
            self.tests_failed += 1
            self.failures.append(f"Calendar endpoint: {str(e)}")
            return False
    
    def print_summary(self):
        """Print test summary"""
        print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BLUE}TEST SUMMARY{Colors.END}")
        print(f"{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"Total Tests: {self.tests_run}")
        print(f"{Colors.GREEN}Passed: {self.tests_passed}{Colors.END}")
        print(f"{Colors.RED}Failed: {self.tests_failed}{Colors.END}")
        
        if self.failures:
            print(f"\n{Colors.RED}FAILURES:{Colors.END}")
            for i, failure in enumerate(self.failures, 1):
                print(f"  {i}. {failure}")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"\nSuccess Rate: {success_rate:.1f}%")
        
        if self.tests_failed == 0:
            print(f"\n{Colors.GREEN}🎉 ALL TESTS PASSED!{Colors.END}")
            return 0
        else:
            print(f"\n{Colors.RED}❌ SOME TESTS FAILED{Colors.END}")
            return 1


def main():
    """Main test runner"""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}RahazaTrans ERP - Calendar Export Test Suite{Colors.END}")
    print(f"{Colors.BLUE}Testing: Export to Excel, PDF, Auth Protection{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    
    tester = CalendarExportTester()
    
    # Login
    if not tester.login():
        print(f"\n{Colors.RED}Failed to authenticate. Exiting.{Colors.END}")
        return 1
    
    # Run tests
    try:
        # Test auth protection first (without token)
        tester.test_export_auth_protection()
        
        # Test calendar endpoint (regression)
        tester.test_calendar_endpoint()
        
        # Test exports
        tester.test_export_excel()
        tester.test_export_pdf()
        
    except Exception as e:
        print(f"\n{Colors.RED}Test suite error: {str(e)}{Colors.END}")
        import traceback
        traceback.print_exc()
    
    # Print summary
    return tester.print_summary()


if __name__ == "__main__":
    sys.exit(main())

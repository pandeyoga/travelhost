"""
E4 BI & Management Cockpit Backend Testing
Tests all analytics endpoints, RBAC, range parameters, ad-spend, and exports.
"""
import requests
import sys
from datetime import datetime, timedelta

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

class E4AnalyticsTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.tokens = {}
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
        """Login and store token"""
        self.log(f"Logging in as {email}...")
        try:
            resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("token")
                if token:
                    self.tokens[email] = token
                    self.log(f"Login successful for {email}", "PASS")
                    return True
                else:
                    self.log(f"Login missing token for {email}", "FAIL")
                    return False
            else:
                self.log(f"Login failed for {email}: {resp.status_code} - {resp.text[:200]}", "FAIL")
                return False
        except Exception as e:
            self.log(f"Login exception for {email}: {e}", "FAIL")
            return False

    def get(self, endpoint: str, email: str, params: dict = None):
        """GET request with auth"""
        token = self.tokens.get(email)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers, params=params, timeout=15)
            return resp
        except Exception as e:
            self.log(f"GET {endpoint} exception: {e}", "FAIL")
            return None

    def put(self, endpoint: str, email: str, data: dict):
        """PUT request with auth"""
        token = self.tokens.get(email)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            resp = requests.put(f"{BASE_URL}{endpoint}", headers=headers, json=data, timeout=15)
            return resp
        except Exception as e:
            self.log(f"PUT {endpoint} exception: {e}", "FAIL")
            return None

    def test_summary(self, email: str):
        """Test GET /analytics/summary with different ranges"""
        self.log(f"\n--- Testing /analytics/summary as {email} ---")
        
        # Test default (30 days)
        resp = self.get("/analytics/summary", email)
        if not resp:
            self.test("Summary API reachable", False, "No response")
            return
        
        self.test("Summary returns 200", resp.status_code == 200, f"Got {resp.status_code}")
        if resp.status_code != 200:
            return
        
        data = resp.json()
        self.test("Summary has range", "range" in data, "Missing range")
        self.test("Summary has metrics", "metrics" in data, "Missing metrics")
        
        if "metrics" in data:
            m = data["metrics"]
            required = ["revenue", "profit", "bookings", "leads", "conversion_rate", "outstanding_ar"]
            for key in required:
                has_key = key in m
                self.test(f"Summary has {key}", has_key, f"Missing {key}")
                if has_key:
                    metric = m[key]
                    self.test(f"Summary {key} has value", "value" in metric, f"Missing value in {key}")
                    if key != "outstanding_ar":  # AR doesn't have delta
                        self.test(f"Summary {key} has delta_pct", "delta_pct" in metric, f"Missing delta_pct in {key}")
        
        # Test 90 days
        resp90 = self.get("/analytics/summary", email, params={"days": 90})
        self.test("Summary 90 days returns 200", resp90 and resp90.status_code == 200, f"Got {resp90.status_code if resp90 else 'None'}")
        
        # Test custom range
        today = datetime.now().date()
        start = (today - timedelta(days=60)).isoformat()
        end = today.isoformat()
        resp_custom = self.get("/analytics/summary", email, params={"start": start, "end": end})
        self.test("Summary custom range returns 200", resp_custom and resp_custom.status_code == 200, f"Got {resp_custom.status_code if resp_custom else 'None'}")

    def test_funnel(self, email: str):
        """Test GET /analytics/funnel"""
        self.log(f"\n--- Testing /analytics/funnel as {email} ---")
        resp = self.get("/analytics/funnel", email, params={"days": 90})
        
        if not resp:
            self.test("Funnel API reachable", False, "No response")
            return
        
        self.test("Funnel returns 200", resp.status_code == 200, f"Got {resp.status_code}")
        if resp.status_code != 200:
            return
        
        data = resp.json()
        self.test("Funnel has stages", "stages" in data, "Missing stages")
        self.test("Funnel has overall_conversion", "overall_conversion" in data, "Missing overall_conversion")
        
        if "stages" in data:
            stages = data["stages"]
            self.test("Funnel stages is array", isinstance(stages, list), "Stages not array")
            if stages:
                s = stages[0]
                self.test("Funnel stage has label", "label" in s, "Missing label")
                self.test("Funnel stage has count", "count" in s, "Missing count")
                self.test("Funnel stage has rate", "rate" in s, "Missing rate")

    def test_channels(self, email: str):
        """Test GET /analytics/channels"""
        self.log(f"\n--- Testing /analytics/channels as {email} ---")
        resp = self.get("/analytics/channels", email, params={"days": 90})
        
        if not resp:
            self.test("Channels API reachable", False, "No response")
            return
        
        self.test("Channels returns 200", resp.status_code == 200, f"Got {resp.status_code}")
        if resp.status_code != 200:
            return
        
        data = resp.json()
        self.test("Channels has channels array", "channels" in data, "Missing channels")
        self.test("Channels has totals", "totals" in data, "Missing totals")
        
        if "channels" in data:
            channels = data["channels"]
            self.test("Channels is array", isinstance(channels, list), "Channels not array")
            if channels:
                c = channels[0]
                required = ["channel", "leads", "won", "revenue", "spend", "cpl", "roas"]
                for key in required:
                    self.test(f"Channel has {key}", key in c, f"Missing {key}")
        
        if "totals" in data:
            t = data["totals"]
            self.test("Totals has leads", "leads" in t, "Missing leads in totals")
            self.test("Totals has spend", "spend" in t, "Missing spend in totals")
            self.test("Totals has roas", "roas" in t, "Missing roas in totals")

    def test_fleet(self, email: str):
        """Test GET /analytics/fleet"""
        self.log(f"\n--- Testing /analytics/fleet as {email} ---")
        resp = self.get("/analytics/fleet", email, params={"days": 90})
        
        if not resp:
            self.test("Fleet API reachable", False, "No response")
            return
        
        self.test("Fleet returns 200", resp.status_code == 200, f"Got {resp.status_code}")
        if resp.status_code != 200:
            return
        
        data = resp.json()
        self.test("Fleet has vehicles", "vehicles" in data, "Missing vehicles")
        self.test("Fleet has active_units", "active_units" in data, "Missing active_units")
        self.test("Fleet has idle_units", "idle_units" in data, "Missing idle_units")
        
        if "vehicles" in data:
            vehicles = data["vehicles"]
            self.test("Fleet vehicles is array", isinstance(vehicles, list), "Vehicles not array")
            if vehicles:
                v = vehicles[0]
                required = ["vehicle_id", "vehicle_name", "trips", "revenue", "expenses", "profit", "roi_pct"]
                for key in required:
                    self.test(f"Vehicle has {key}", key in v, f"Missing {key}")

    def test_drivers(self, email: str):
        """Test GET /analytics/drivers"""
        self.log(f"\n--- Testing /analytics/drivers as {email} ---")
        resp = self.get("/analytics/drivers", email, params={"days": 90})
        
        if not resp:
            self.test("Drivers API reachable", False, "No response")
            return
        
        self.test("Drivers returns 200", resp.status_code == 200, f"Got {resp.status_code}")
        if resp.status_code != 200:
            return
        
        data = resp.json()
        self.test("Drivers has drivers array", "drivers" in data, "Missing drivers")
        
        if "drivers" in data:
            drivers = data["drivers"]
            self.test("Drivers is array", isinstance(drivers, list), "Drivers not array")
            if drivers:
                d = drivers[0]
                required = ["driver_id", "driver_name", "trips", "completed", "completion_rate", "revenue", "distance_km"]
                for key in required:
                    self.test(f"Driver has {key}", key in d, f"Missing {key}")

    def test_ar_aging(self, email: str):
        """Test GET /analytics/ar-aging"""
        self.log(f"\n--- Testing /analytics/ar-aging as {email} ---")
        resp = self.get("/analytics/ar-aging", email)
        
        if not resp:
            self.test("AR Aging API reachable", False, "No response")
            return
        
        self.test("AR Aging returns 200", resp.status_code == 200, f"Got {resp.status_code}")
        if resp.status_code != 200:
            return
        
        data = resp.json()
        self.test("AR Aging has total_outstanding", "total_outstanding" in data, "Missing total_outstanding")
        self.test("AR Aging has buckets", "buckets" in data, "Missing buckets")
        
        if "buckets" in data:
            buckets = data["buckets"]
            self.test("AR Aging buckets is array", isinstance(buckets, list), "Buckets not array")
            if buckets:
                b = buckets[0]
                self.test("Bucket has bucket", "bucket" in b, "Missing bucket")
                self.test("Bucket has label", "label" in b, "Missing label")
                self.test("Bucket has amount", "amount" in b, "Missing amount")
                self.test("Bucket has count", "count" in b, "Missing count")
            
            # Verify sum of buckets equals total
            if "total_outstanding" in data:
                total = data["total_outstanding"]
                bucket_sum = sum(b.get("amount", 0) for b in buckets)
                self.test("AR Aging buckets sum equals total", abs(total - bucket_sum) < 0.01, f"Total {total} != sum {bucket_sum}")

    def test_retention(self, email: str):
        """Test GET /analytics/retention"""
        self.log(f"\n--- Testing /analytics/retention as {email} ---")
        resp = self.get("/analytics/retention", email, params={"days": 90})
        
        if not resp:
            self.test("Retention API reachable", False, "No response")
            return
        
        self.test("Retention returns 200", resp.status_code == 200, f"Got {resp.status_code}")
        if resp.status_code != 200:
            return
        
        data = resp.json()
        required = ["total_customers", "returning_customers", "one_time_customers", "repeat_rate", "by_rfm"]
        for key in required:
            self.test(f"Retention has {key}", key in data, f"Missing {key}")
        
        if "repeat_rate" in data:
            rr = data["repeat_rate"]
            self.test("Retention repeat_rate is 0-1", 0 <= rr <= 1, f"repeat_rate {rr} out of range")

    def test_forecast(self, email: str):
        """Test GET /analytics/forecast"""
        self.log(f"\n--- Testing /analytics/forecast as {email} ---")
        resp = self.get("/analytics/forecast", email)
        
        if not resp:
            self.test("Forecast API reachable", False, "No response")
            return
        
        self.test("Forecast returns 200", resp.status_code == 200, f"Got {resp.status_code}")
        if resp.status_code != 200:
            return
        
        data = resp.json()
        self.test("Forecast has history", "history" in data, "Missing history")
        self.test("Forecast has forecast", "forecast" in data, "Missing forecast")
        
        if "history" in data:
            history = data["history"]
            self.test("Forecast history is array", isinstance(history, list), "History not array")
            if history:
                h = history[0]
                self.test("History has month", "month" in h, "Missing month")
                self.test("History has value", "value" in h, "Missing value")
        
        if "forecast" in data:
            forecast = data["forecast"]
            self.test("Forecast forecast is array", isinstance(forecast, list), "Forecast not array")
            if forecast:
                f = forecast[0]
                self.test("Forecast has month", "month" in f, "Missing month")
                self.test("Forecast has value", "value" in f, "Missing value")

    def test_ad_spend(self, email: str):
        """Test GET and PUT /analytics/ad-spend"""
        self.log(f"\n--- Testing /analytics/ad-spend as {email} ---")
        
        # GET
        resp = self.get("/analytics/ad-spend", email)
        if not resp:
            self.test("Ad-spend GET reachable", False, "No response")
            return
        
        self.test("Ad-spend GET returns 200", resp.status_code == 200, f"Got {resp.status_code}")
        if resp.status_code != 200:
            return
        
        data = resp.json()
        self.test("Ad-spend has items", "items" in data, "Missing items")
        self.test("Ad-spend has spend_map", "spend_map" in data, "Missing spend_map")
        
        # PUT - update one channel
        new_items = [
            {"channel": "meta_ads", "amount": 2000000},
            {"channel": "google_ads", "amount": 1500000},
        ]
        put_resp = self.put("/analytics/ad-spend", email, {"items": new_items, "note": "Test update"})
        
        if not put_resp:
            self.test("Ad-spend PUT reachable", False, "No response")
            return
        
        self.test("Ad-spend PUT returns 200", put_resp.status_code == 200, f"Got {put_resp.status_code}")
        
        # GET again to verify
        resp2 = self.get("/analytics/ad-spend", email)
        if resp2 and resp2.status_code == 200:
            data2 = resp2.json()
            spend_map = data2.get("spend_map", {})
            self.test("Ad-spend updated meta_ads", spend_map.get("meta_ads") == 2000000, f"Got {spend_map.get('meta_ads')}")
            self.test("Ad-spend updated google_ads", spend_map.get("google_ads") == 1500000, f"Got {spend_map.get('google_ads')}")

    def test_export(self, email: str):
        """Test GET /analytics/export"""
        self.log(f"\n--- Testing /analytics/export as {email} ---")
        
        # Test Excel export
        resp_excel = self.get("/analytics/export", email, params={"format": "excel", "days": 90})
        if not resp_excel:
            self.test("Export Excel reachable", False, "No response")
        else:
            self.test("Export Excel returns 200", resp_excel.status_code == 200, f"Got {resp_excel.status_code}")
            if resp_excel.status_code == 200:
                content_type = resp_excel.headers.get("Content-Type", "")
                self.test("Export Excel has correct content-type", "spreadsheet" in content_type or "excel" in content_type, f"Got {content_type}")
                self.test("Export Excel has content", len(resp_excel.content) > 0, "Empty content")
        
        # Test PDF export
        resp_pdf = self.get("/analytics/export", email, params={"format": "pdf", "days": 90})
        if not resp_pdf:
            self.test("Export PDF reachable", False, "No response")
        else:
            self.test("Export PDF returns 200", resp_pdf.status_code == 200, f"Got {resp_pdf.status_code}")
            if resp_pdf.status_code == 200:
                content_type = resp_pdf.headers.get("Content-Type", "")
                self.test("Export PDF has correct content-type", "pdf" in content_type, f"Got {content_type}")
                self.test("Export PDF has content", len(resp_pdf.content) > 0, "Empty content")

    def test_rbac_driver(self, email: str):
        """Test that driver role gets 403 on analytics endpoints"""
        self.log(f"\n--- Testing RBAC (driver should get 403) ---")
        
        endpoints = [
            "/analytics/summary",
            "/analytics/funnel",
            "/analytics/channels",
            "/analytics/fleet",
            "/analytics/drivers",
            "/analytics/ar-aging",
            "/analytics/retention",
            "/analytics/forecast",
            "/analytics/ad-spend",
            "/analytics/export",
        ]
        
        for endpoint in endpoints:
            resp = self.get(endpoint, email)
            if resp:
                self.test(f"Driver 403 on {endpoint}", resp.status_code == 403, f"Got {resp.status_code}")
            else:
                self.test(f"Driver 403 on {endpoint}", False, "No response")

    def run_all(self):
        """Run all E4 analytics tests"""
        self.log("\n" + "="*60)
        self.log("E4 BI & Management Cockpit Backend Tests")
        self.log("="*60)
        
        # Login all users
        owner_ok = self.login("owner@demo.local", "demo12345")
        ops_ok = self.login("ops@demo.local", "demo12345")
        driver_ok = self.login("driver@demo.local", "demo12345")
        
        if not owner_ok:
            self.log("CRITICAL: Owner login failed, cannot proceed", "FAIL")
            return self.summary()
        
        # Test all endpoints with owner
        self.test_summary("owner@demo.local")
        self.test_funnel("owner@demo.local")
        self.test_channels("owner@demo.local")
        self.test_fleet("owner@demo.local")
        self.test_drivers("owner@demo.local")
        self.test_ar_aging("owner@demo.local")
        self.test_retention("owner@demo.local")
        self.test_forecast("owner@demo.local")
        self.test_ad_spend("owner@demo.local")
        self.test_export("owner@demo.local")
        
        # Test RBAC with driver
        if driver_ok:
            self.test_rbac_driver("driver@demo.local")
        
        # Test with ops_admin (should work)
        if ops_ok:
            self.log("\n--- Quick test with ops_admin (should work) ---")
            resp = self.get("/analytics/summary", "ops@demo.local", params={"days": 90})
            self.test("Ops_admin can access analytics", resp and resp.status_code == 200, f"Got {resp.status_code if resp else 'None'}")
        
        return self.summary()

    def summary(self):
        """Print summary and return exit code"""
        self.log("\n" + "="*60)
        self.log(f"TESTS RUN: {self.tests_run}")
        self.log(f"PASSED: {self.tests_passed}", "PASS")
        self.log(f"FAILED: {self.tests_failed}", "FAIL" if self.tests_failed > 0 else "INFO")
        self.log("="*60)
        
        if self.errors:
            self.log("\nFailed Tests:", "FAIL")
            for err in self.errors[:10]:  # Show first 10 errors
                self.log(f"  - {err}", "FAIL")
            if len(self.errors) > 10:
                self.log(f"  ... and {len(self.errors) - 10} more", "FAIL")
        
        return 0 if self.tests_failed == 0 else 1


if __name__ == "__main__":
    tester = E4AnalyticsTester()
    exit_code = tester.run_all()
    sys.exit(exit_code)

"""
Backend Testing for Booking Flow (Public + Ops)
Tests all user stories from the review request for booking functionality.
"""
import requests
import sys
import io
from typing import Dict, Any
from datetime import datetime, timedelta

# Use public endpoint from frontend/.env
BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

# Test dates: 25-27 days from now (to avoid seed data conflicts)
TODAY = datetime.utcnow()
START_DATE = (TODAY + timedelta(days=25)).strftime("%Y-%m-%dT10:00:00Z")
END_DATE = (TODAY + timedelta(days=27)).strftime("%Y-%m-%dT10:00:00Z")
AIRPORT_DATE = (TODAY + timedelta(days=26)).strftime("%Y-%m-%dT14:00:00Z")

class TestRunner:
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

    def login(self, email: str, password: str) -> Dict[str, Any]:
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
                    self.tokens[email] = token
                    self.log(f"Login successful for {email}", "PASS")
                    return data
                else:
                    self.log(f"Login response missing token for {email}", "FAIL")
                    return {}
            else:
                self.log(f"Login failed for {email}: {resp.status_code} - {resp.text[:200]}", "FAIL")
                return {}
        except Exception as e:
            self.log(f"Login exception for {email}: {e}", "FAIL")
            return {}

    def get(self, endpoint: str, email: str = None, params: Dict = None) -> requests.Response:
        """GET request with optional auth"""
        headers = {}
        if email:
            token = self.tokens.get(email)
            if token:
                headers["Authorization"] = f"Bearer {token}"
        return requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params, timeout=10)

    def post(self, endpoint: str, email: str = None, data: Dict = None) -> requests.Response:
        """POST request with optional auth"""
        headers = {}
        if email:
            token = self.tokens.get(email)
            if token:
                headers["Authorization"] = f"Bearer {token}"
        return requests.post(f"{BASE_URL}/{endpoint}", headers=headers, json=data, timeout=10)

    def test_public_booking_config(self):
        """Test GET /api/public/booking/config"""
        self.log("\n=== PUBLIC STORY: Booking Config ===", "INFO")
        
        resp = self.get("public/booking/config")
        self.test("Config endpoint returns 200", resp.status_code == 200,
                 f"Got {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            self.test("Config has services", "services" in data and len(data["services"]) > 0,
                     "No services found")
            self.test("Config has vehicle_types", "vehicle_types" in data and len(data["vehicle_types"]) > 0,
                     "No vehicle types found")
            self.test("Config has routes", "routes" in data,
                     "No routes field")
            self.test("Config has dp_percent", "dp_percent" in data and data["dp_percent"] > 0,
                     f"DP percent: {data.get('dp_percent')}")
            self.test("Config has payment info", "payment" in data,
                     "No payment info")
            
            # Store for later use
            self.test_data["config"] = data
            self.log(f"Found {len(data.get('services', []))} services, {len(data.get('vehicle_types', []))} vehicle types, {len(data.get('routes', []))} routes")

    def test_public_booking_search_daily(self):
        """Test POST /api/public/booking/search for daily rental"""
        self.log("\n=== PUBLIC STORY 1: Search Daily Rental ===", "INFO")
        
        resp = self.post("public/booking/search", data={
            "service": "daily_rental",
            "start_datetime": START_DATE,
            "end_datetime": END_DATE,
            "pax": 4
        })
        
        self.test("Search returns 200", resp.status_code == 200,
                 f"Got {resp.status_code}: {resp.text[:200]}")
        
        if resp.status_code == 200:
            data = resp.json()
            self.test("Search has options", "options" in data,
                     "No options field")
            self.test("Search has unavailable list", "unavailable" in data,
                     "No unavailable field")
            
            options = data.get("options", [])
            if len(options) > 0:
                self.log(f"Found {len(options)} available vehicles")
                first = options[0]
                self.test("Option has vehicle", "vehicle" in first,
                         "No vehicle in option")
                self.test("Option has quote", "quote" in first,
                         "No quote in option")
                
                if "quote" in first:
                    quote = first["quote"]
                    self.test("Quote has total", "total" in quote and quote["total"] > 0,
                             f"Total: {quote.get('total')}")
                    self.test("Quote has dp_amount", "dp_amount" in quote and quote["dp_amount"] > 0,
                             f"DP: {quote.get('dp_amount')}")
                    self.test("Quote has breakdown", "breakdown" in quote and len(quote["breakdown"]) > 0,
                             "No breakdown")
                    
                    # Store for later use
                    self.test_data["daily_vehicle"] = first["vehicle"]
                    self.test_data["daily_quote"] = quote
                    self.log(f"Vehicle: {first['vehicle'].get('name')}, Total: Rp {quote['total']:,}, DP: Rp {quote['dp_amount']:,}")
            else:
                self.test("At least one vehicle available", False,
                         "No vehicles available - check seed data or date range")

    def test_public_booking_search_airport(self):
        """Test POST /api/public/booking/search for airport transfer"""
        self.log("\n=== PUBLIC STORY 6: Search Airport Transfer ===", "INFO")
        
        config = self.test_data.get("config", {})
        routes = config.get("routes", [])
        
        if not routes:
            self.log("No airport routes configured, skipping airport transfer test", "WARN")
            return
        
        route = routes[0]
        self.log(f"Testing route: {route.get('name')}")
        
        resp = self.post("public/booking/search", data={
            "service": "airport_transfer",
            "route_id": route.get("id"),
            "start_datetime": AIRPORT_DATE,
            "pax": 2
        })
        
        self.test("Airport search returns 200", resp.status_code == 200,
                 f"Got {resp.status_code}: {resp.text[:200]}")
        
        if resp.status_code == 200:
            data = resp.json()
            options = data.get("options", [])
            if len(options) > 0:
                self.log(f"Found {len(options)} vehicles for airport transfer")
                first = options[0]
                quote = first.get("quote", {})
                
                # Airport transfer should have flat rate
                breakdown = quote.get("breakdown", [])
                flat_rate_found = any("flat" in str(item.get("label", "")).lower() or 
                                     "antar-jemput" in str(item.get("label", "")).lower() 
                                     for item in breakdown)
                self.test("Airport transfer has flat rate in breakdown", flat_rate_found,
                         f"Breakdown: {breakdown}")
                
                # Store for later
                self.test_data["airport_route"] = route
                self.test_data["airport_vehicle"] = first["vehicle"]
                self.test_data["airport_quote"] = quote

    def test_public_booking_quote(self):
        """Test POST /api/public/booking/quote"""
        self.log("\n=== PUBLIC STORY 1: Get Quote ===", "INFO")
        
        vehicle = self.test_data.get("daily_vehicle")
        if not vehicle:
            self.log("No vehicle from search, skipping quote test", "WARN")
            return
        
        resp = self.post("public/booking/quote", data={
            "service": "daily_rental",
            "vehicle_id": vehicle.get("id"),
            "start_datetime": START_DATE,
            "end_datetime": END_DATE,
            "pax": 4
        })
        
        self.test("Quote returns 200", resp.status_code == 200,
                 f"Got {resp.status_code}: {resp.text[:200]}")
        
        if resp.status_code == 200:
            data = resp.json()
            self.test("Quote has vehicle", "vehicle" in data,
                     "No vehicle in response")
            self.test("Quote has quote", "quote" in data,
                     "No quote in response")
            self.test("Quote has available flag", "available" in data,
                     "No available flag")
            
            quote = data.get("quote", {})
            self.test_data["quote_response"] = data

    def test_public_booking_submit_daily(self):
        """Test POST /api/public/booking/submit for daily rental"""
        self.log("\n=== PUBLIC STORY 2: Submit Daily Booking ===", "INFO")
        
        vehicle = self.test_data.get("daily_vehicle")
        if not vehicle:
            self.log("No vehicle from search, skipping submit test", "WARN")
            return
        
        # Use unique phone for this test
        test_phone = f"081277{datetime.utcnow().strftime('%H%M%S')}"
        
        resp = self.post("public/booking/submit", data={
            "service": "daily_rental",
            "vehicle_id": vehicle.get("id"),
            "start_datetime": START_DATE,
            "end_datetime": END_DATE,
            "pax": 4,
            "name": "Test Booking User",
            "phone": test_phone,
            "email": "test@example.com",
            "pickup_address": "Jl. Test No. 123",
            "consent": True,
            "idempotency_key": f"test-{datetime.utcnow().timestamp()}"
        })
        
        self.test("Submit returns 200", resp.status_code == 200,
                 f"Got {resp.status_code}: {resp.text[:200]}")
        
        if resp.status_code == 200:
            data = resp.json()
            self.test("Submit has code", "code" in data and data["code"],
                     "No booking code")
            self.test("Submit has token", "token" in data and data["token"],
                     "No token")
            self.test("Submit has status", "status" in data,
                     "No status")
            
            # Store for later tests
            self.test_data["booking_code"] = data.get("code")
            self.test_data["booking_token"] = data.get("token")
            self.test_data["booking_phone"] = test_phone
            self.test_data["booking_total"] = data.get("total_amount")
            self.test_data["booking_dp"] = data.get("dp_amount")
            
            self.log(f"Booking created: {data.get('code')}, Status: {data.get('status')}, Total: Rp {data.get('total_amount', 0):,}, DP: Rp {data.get('dp_amount', 0):,}")

    def test_public_booking_lookup(self):
        """Test POST /api/public/booking/lookup"""
        self.log("\n=== PUBLIC STORY 5: Lookup Booking ===", "INFO")
        
        code = self.test_data.get("booking_code")
        phone = self.test_data.get("booking_phone")
        
        if not code or not phone:
            self.log("No booking code/phone, skipping lookup test", "WARN")
            return
        
        resp = self.post("public/booking/lookup", data={
            "code": code,
            "phone": phone
        })
        
        self.test("Lookup returns 200", resp.status_code == 200,
                 f"Got {resp.status_code}: {resp.text[:200]}")
        
        if resp.status_code == 200:
            data = resp.json()
            self.test("Lookup has code", data.get("code") == code,
                     f"Expected {code}, got {data.get('code')}")
            self.test("Lookup has token", "token" in data and data["token"],
                     "No token")
            self.test("Lookup has status", "status" in data,
                     "No status")

    def test_public_booking_status(self):
        """Test GET /api/public/booking/{code}?token="""
        self.log("\n=== PUBLIC STORY 2: Get Booking Status ===", "INFO")
        
        code = self.test_data.get("booking_code")
        token = self.test_data.get("booking_token")
        
        if not code or not token:
            self.log("No booking code/token, skipping status test", "WARN")
            return
        
        resp = self.get(f"public/booking/{code}", params={"token": token})
        
        self.test("Status returns 200", resp.status_code == 200,
                 f"Got {resp.status_code}: {resp.text[:200]}")
        
        if resp.status_code == 200:
            data = resp.json()
            self.test("Status has code", data.get("code") == code,
                     f"Expected {code}, got {data.get('code')}")
            self.test("Status has payment info", "payment" in data,
                     "No payment info")
            self.test("Status has dp_amount", "dp_amount" in data,
                     f"DP amount: {data.get('dp_amount')}")
            self.test("Status has total_amount", "total_amount" in data,
                     f"Total: {data.get('total_amount')}")
            
            # PUBLIC STORY 3: Price consistency check
            stored_total = data.get("total_amount")
            stored_dp = data.get("dp_amount")
            expected_total = self.test_data.get("booking_total")
            expected_dp = self.test_data.get("booking_dp")
            
            if expected_total and expected_dp:
                self.test("Total amount matches", stored_total == expected_total,
                         f"Expected {expected_total}, got {stored_total}")
                self.test("DP amount matches", stored_dp == expected_dp,
                         f"Expected {expected_dp}, got {stored_dp}")
            
            # Check for bank accounts
            payment = data.get("payment", {})
            bank_accounts = payment.get("bank_accounts", [])
            self.test("Payment has bank accounts", len(bank_accounts) > 0,
                     "No bank accounts configured")
            
            if bank_accounts:
                self.log(f"Found {len(bank_accounts)} bank accounts")
                for acc in bank_accounts:
                    self.log(f"  - {acc.get('bank_name')}: {acc.get('account_number')}")
            
            self.test_data["booking_status"] = data

    def test_public_booking_proof_upload(self):
        """Test POST /api/public/booking/{code}/proof"""
        self.log("\n=== PUBLIC STORY 4: Upload Payment Proof ===", "INFO")
        
        code = self.test_data.get("booking_code")
        token = self.test_data.get("booking_token")
        dp_amount = self.test_data.get("booking_dp")
        
        if not code or not token:
            self.log("No booking code/token, skipping proof upload test", "WARN")
            return
        
        # Create a small PNG file (1x1 pixel)
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        
        files = {
            'image': ('bukti-bayar.png', io.BytesIO(png_data), 'image/png')
        }
        data = {
            'token': token,
            'amount': str(dp_amount or 0),
            'sender_name': 'Test User',
            'bank': 'BCA',
            'note': 'Test payment proof'
        }
        
        try:
            resp = requests.post(
                f"{BASE_URL}/public/booking/{code}/proof",
                files=files,
                data=data,
                timeout=15
            )
            
            self.test("Proof upload returns 200", resp.status_code == 200,
                     f"Got {resp.status_code}: {resp.text[:200]}")
            
            if resp.status_code == 200:
                result = resp.json()
                self.test("Proof upload confirmed", result.get("uploaded") == True,
                         "Upload not confirmed")
                self.test("Proof has ID", "proof" in result and result["proof"].get("id"),
                         "No proof ID")
                
                # Store proof ID for ops tests
                if "proof" in result:
                    self.test_data["proof_id"] = result["proof"].get("id")
                    self.log(f"Proof uploaded: {result['proof'].get('id')}")
        except Exception as e:
            self.test("Proof upload exception", False, str(e))

    def test_public_validation_errors(self):
        """Test PUBLIC STORY 8: Validation & anti-tamper"""
        self.log("\n=== PUBLIC STORY 8: Validation Errors ===", "INFO")
        
        vehicle = self.test_data.get("daily_vehicle")
        if not vehicle:
            self.log("No vehicle, skipping validation tests", "WARN")
            return
        
        # Test 1: Submit without name
        resp = self.post("public/booking/submit", data={
            "service": "daily_rental",
            "vehicle_id": vehicle.get("id"),
            "start_datetime": START_DATE,
            "end_datetime": END_DATE,
            "phone": "081234567890"
        })
        self.test("Submit without name returns 400", resp.status_code == 400,
                 f"Got {resp.status_code}")
        if resp.status_code == 400:
            self.test("Error message in Indonesian", "wajib" in resp.text.lower() or "nama" in resp.text.lower(),
                     f"Response: {resp.text[:100]}")
        
        # Test 2: Submit without phone
        resp = self.post("public/booking/submit", data={
            "service": "daily_rental",
            "vehicle_id": vehicle.get("id"),
            "start_datetime": START_DATE,
            "end_datetime": END_DATE,
            "name": "Test User"
        })
        self.test("Submit without phone returns 400", resp.status_code == 400,
                 f"Got {resp.status_code}")
        
        # Test 3: End date before start date
        resp = self.post("public/booking/submit", data={
            "service": "daily_rental",
            "vehicle_id": vehicle.get("id"),
            "start_datetime": END_DATE,
            "end_datetime": START_DATE,
            "name": "Test User",
            "phone": "081234567890"
        })
        self.test("End before start returns 400", resp.status_code == 400,
                 f"Got {resp.status_code}")
        if resp.status_code == 400:
            self.test("Error explains date issue", "tanggal" in resp.text.lower() or "setelah" in resp.text.lower(),
                     f"Response: {resp.text[:100]}")
        
        # Test 4: Past date
        past_date = (TODAY - timedelta(days=1)).strftime("%Y-%m-%dT10:00:00Z")
        resp = self.post("public/booking/submit", data={
            "service": "daily_rental",
            "vehicle_id": vehicle.get("id"),
            "start_datetime": past_date,
            "end_datetime": START_DATE,
            "name": "Test User",
            "phone": "081234567890"
        })
        self.test("Past date returns 400", resp.status_code == 400,
                 f"Got {resp.status_code}")

    def test_ops_payment_proofs_list(self):
        """Test GET /api/bookings/payment-proofs (OPS STORY 1)"""
        self.log("\n=== OPS STORY 1: List Payment Proofs ===", "INFO")
        
        owner = "owner@demo.local"
        if owner not in self.tokens:
            self.log("Owner not logged in, skipping", "WARN")
            return
        
        resp = self.get("bookings/payment-proofs", email=owner, params={"status": "pending"})
        
        self.test("Payment proofs list returns 200", resp.status_code == 200,
                 f"Got {resp.status_code}: {resp.text[:200]}")
        
        if resp.status_code == 200:
            data = resp.json()
            self.test("Response has proofs", "proofs" in data,
                     "No proofs field")
            self.test("Response has pending count", "pending" in data,
                     "No pending count")
            
            proofs = data.get("proofs", [])
            self.log(f"Found {len(proofs)} pending proofs")
            
            # Check if our uploaded proof is in the list
            proof_id = self.test_data.get("proof_id")
            if proof_id:
                found = any(p.get("id") == proof_id for p in proofs)
                self.test("Uploaded proof in list", found,
                         f"Proof {proof_id} not found in list")
                
                if found:
                    proof = next(p for p in proofs if p.get("id") == proof_id)
                    self.test("Proof has booking info", "booking" in proof,
                             "No booking info")
                    self.test("Proof has media_url", "media_url" in proof and proof["media_url"],
                             "No media URL")
                    self.log(f"Proof {proof_id}: {proof.get('amount_claimed')} - {proof.get('status')}")

    def test_ops_verify_proof(self):
        """Test POST /api/bookings/{id}/proofs/{proof_id}/verify (OPS STORY 2)"""
        self.log("\n=== OPS STORY 2: Verify Payment Proof ===", "INFO")
        
        owner = "owner@demo.local"
        if owner not in self.tokens:
            self.log("Owner not logged in, skipping", "WARN")
            return
        
        proof_id = self.test_data.get("proof_id")
        booking_code = self.test_data.get("booking_code")
        
        if not proof_id or not booking_code:
            self.log("No proof ID or booking code, skipping verify test", "WARN")
            return
        
        # Get booking ID from code
        bookings_resp = self.get("bookings", email=owner, params={"code": booking_code})
        if bookings_resp.status_code != 200:
            self.log("Failed to get booking ID", "WARN")
            return
        
        bookings = bookings_resp.json()
        if not bookings:
            self.log("Booking not found", "WARN")
            return
        
        booking_id = bookings[0].get("id")
        dp_amount = self.test_data.get("booking_dp")
        
        resp = self.post(f"bookings/{booking_id}/proofs/{proof_id}/verify", email=owner, data={
            "amount": dp_amount,
            "method": "transfer",
            "note": "Test verification"
        })
        
        self.test("Verify proof returns 200", resp.status_code == 200,
                 f"Got {resp.status_code}: {resp.text[:200]}")
        
        if resp.status_code == 200:
            data = resp.json()
            self.test("Verification confirmed", data.get("verified") == True,
                     "Not verified")
            self.test("Payment created", "payment" in data and data["payment"],
                     "No payment created")
            self.test("Booking updated", "booking" in data and data["booking"],
                     "No booking info")
            
            # Check booking status changed
            booking = data.get("booking", {})
            self.test("Booking status is confirmed", booking.get("status") == "confirmed",
                     f"Status: {booking.get('status')}")
            self.test("Payment status updated", booking.get("payment_status") in ["dp", "lunas"],
                     f"Payment status: {booking.get('payment_status')}")
            
            self.log(f"Booking {booking_code} verified and confirmed")

    def test_ops_reject_proof(self):
        """Test POST /api/bookings/{id}/proofs/{proof_id}/reject (OPS STORY 3)"""
        self.log("\n=== OPS STORY 3: Reject Payment Proof ===", "INFO")
        
        # Create a new booking for rejection test
        vehicle = self.test_data.get("daily_vehicle")
        if not vehicle:
            self.log("No vehicle, skipping reject test", "WARN")
            return
        
        owner = "owner@demo.local"
        if owner not in self.tokens:
            self.log("Owner not logged in, skipping", "WARN")
            return
        
        # Create booking
        test_phone = f"081277{datetime.utcnow().strftime('%H%M%S')}"
        resp = self.post("public/booking/submit", data={
            "service": "daily_rental",
            "vehicle_id": vehicle.get("id"),
            "start_datetime": START_DATE,
            "end_datetime": END_DATE,
            "pax": 4,
            "name": "Test Reject User",
            "phone": test_phone,
            "consent": True,
            "idempotency_key": f"test-reject-{datetime.utcnow().timestamp()}"
        })
        
        if resp.status_code != 200:
            self.log("Failed to create booking for reject test", "WARN")
            return
        
        booking_data = resp.json()
        code = booking_data.get("code")
        token = booking_data.get("token")
        
        # Upload proof
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        files = {'image': ('bukti-reject.png', io.BytesIO(png_data), 'image/png')}
        data = {'token': token, 'amount': '100000', 'sender_name': 'Test', 'bank': 'BCA'}
        
        try:
            proof_resp = requests.post(f"{BASE_URL}/public/booking/{code}/proof", files=files, data=data, timeout=15)
            if proof_resp.status_code != 200:
                self.log("Failed to upload proof for reject test", "WARN")
                return
            
            proof_id = proof_resp.json().get("proof", {}).get("id")
            
            # Get booking ID
            bookings_resp = self.get("bookings", email=owner, params={"code": code})
            if bookings_resp.status_code != 200:
                self.log("Failed to get booking for reject", "WARN")
                return
            
            bookings = bookings_resp.json()
            if not bookings:
                self.log("Booking not found for reject", "WARN")
                return
            
            booking_id = bookings[0].get("id")
            
            # Reject proof
            reject_resp = self.post(f"bookings/{booking_id}/proofs/{proof_id}/reject", email=owner, data={
                "reason": "Nominal tidak sesuai dengan bukti transfer"
            })
            
            self.test("Reject proof returns 200", reject_resp.status_code == 200,
                     f"Got {reject_resp.status_code}: {reject_resp.text[:200]}")
            
            if reject_resp.status_code == 200:
                result = reject_resp.json()
                self.test("Rejection confirmed", result.get("rejected") == True,
                         "Not rejected")
                
                # Check status page shows rejection reason
                status_resp = self.get(f"public/booking/{code}", params={"token": token})
                if status_resp.status_code == 200:
                    status = status_resp.json()
                    proofs = status.get("proofs", [])
                    rejected_proof = next((p for p in proofs if p.get("id") == proof_id), None)
                    if rejected_proof:
                        self.test("Rejection reason visible", rejected_proof.get("reject_reason"),
                                 "No rejection reason")
                        self.test("Can still upload", status.get("can_upload_proof") == True,
                                 "Cannot upload after rejection")
        except Exception as e:
            self.test("Reject proof exception", False, str(e))

    def test_rbac_driver(self):
        """Test RBAC 1: Driver permissions"""
        self.log("\n=== RBAC 1: Driver Permissions ===", "INFO")
        
        driver = "driver@demo.local"
        if driver not in self.tokens:
            self.log("Driver not logged in, skipping", "WARN")
            return
        
        # Driver should NOT see payment proofs
        resp = self.get("bookings/payment-proofs", email=driver)
        self.test("Driver cannot access payment proofs", resp.status_code == 403,
                 f"Got {resp.status_code} (expected 403)")
        
        # Driver CAN access bookings (but scoped)
        resp = self.get("bookings", email=driver)
        self.test("Driver can access bookings", resp.status_code == 200,
                 f"Got {resp.status_code}")

    def test_rbac_marketing(self):
        """Test RBAC 2: Marketing admin permissions"""
        self.log("\n=== RBAC 2: Marketing Admin Permissions ===", "INFO")
        
        marketing = "marketing@demo.local"
        if marketing not in self.tokens:
            self.log("Marketing not logged in, skipping", "WARN")
            return
        
        # Marketing should NOT access bookings
        resp = self.get("bookings", email=marketing)
        self.test("Marketing cannot access bookings", resp.status_code == 403,
                 f"Got {resp.status_code} (expected 403)")
        
        # Marketing CAN access media
        resp = self.get("media/assets", email=marketing)
        self.test("Marketing can access media", resp.status_code == 200,
                 f"Got {resp.status_code}")

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "="*60, "INFO")
        self.log(f"TESTS RUN: {self.tests_run}", "INFO")
        self.log(f"PASSED: {self.tests_passed}", "PASS")
        self.log(f"FAILED: {self.tests_failed}", "FAIL" if self.tests_failed > 0 else "INFO")
        
        if self.errors:
            self.log("\nFailed Tests:", "FAIL")
            for error in self.errors:
                self.log(f"  - {error}", "FAIL")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\nSUCCESS RATE: {success_rate:.1f}%", "INFO")
        self.log("="*60, "INFO")
        
        return 0 if self.tests_failed == 0 else 1

def main():
    runner = TestRunner()
    
    # Login all users
    runner.log("=== LOGGING IN USERS ===", "INFO")
    runner.login("owner@demo.local", "demo12345")
    runner.login("ops@demo.local", "demo12345")
    runner.login("marketing@demo.local", "demo12345")
    runner.login("driver@demo.local", "demo12345")
    
    # Public booking tests
    runner.test_public_booking_config()
    runner.test_public_booking_search_daily()
    runner.test_public_booking_search_airport()
    runner.test_public_booking_quote()
    runner.test_public_booking_submit_daily()
    runner.test_public_booking_lookup()
    runner.test_public_booking_status()
    runner.test_public_booking_proof_upload()
    runner.test_public_validation_errors()
    
    # Ops tests
    runner.test_ops_payment_proofs_list()
    runner.test_ops_verify_proof()
    runner.test_ops_reject_proof()
    
    # RBAC tests
    runner.test_rbac_driver()
    runner.test_rbac_marketing()
    
    return runner.print_summary()

if __name__ == "__main__":
    sys.exit(main())

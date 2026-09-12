#!/usr/bin/env python3
"""
Backend Test Suite for RBAC & SSOT WhatsApp Payload Security Hardening
=======================================================================
Tests:
- P0: RBAC bookings (driver 403 on mutations, 200 on reads)
- P0: Ownership driver checkin/checkout (403 for other driver's trips)
- P1: SSOT wa_payload (verify event payloads have complete WA variables)
- P1: Ownership locations (403 for other driver's trips)
- P2: Notifications visibility (404 for invisible notifications)
- Regression: Full booking flow, anti double-booking, critical endpoints
"""
import requests
import sys
import json
from datetime import datetime, timedelta

class RBACTestSuite:
    def __init__(self, base_url="https://trip-route-buttons.preview.emergentagent.com"):
        self.base_url = base_url
        self.tokens = {}
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []
        self.booking_id = None
        self.trip_id = None
        self.driver_trip_id = None
        self.other_driver_trip_id = None
        
    def log(self, msg, status="info"):
        symbols = {"pass": "✅", "fail": "❌", "info": "🔍", "warn": "⚠️"}
        print(f"{symbols.get(status, '•')} {msg}")
    
    def test(self, name, condition, details=""):
        """Record test result"""
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            self.log(f"PASS: {name}", "pass")
            return True
        else:
            self.tests_failed += 1
            self.failures.append(f"{name}: {details}")
            self.log(f"FAIL: {name} - {details}", "fail")
            return False
    
    def login(self, email, password):
        """Login and store token"""
        try:
            url = f"{self.base_url}/api/auth/login"
            response = requests.post(url, json={"email": email, "password": password}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                token = data.get("token")
                if token:
                    self.tokens[email] = token
                    self.log(f"Login successful: {email}", "pass")
                    return True
            self.log(f"Login failed for {email}: {response.status_code}", "fail")
            return False
        except Exception as e:
            self.log(f"Login error for {email}: {str(e)}", "fail")
            return False
    
    def headers(self, email):
        """Get auth headers for user"""
        token = self.tokens.get(email)
        if not token:
            return {"Content-Type": "application/json"}
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
    
    def test_auth(self):
        """Test authentication for all users"""
        self.log("\n=== Testing Authentication ===", "info")
        
        owner_ok = self.login("owner@demo.local", "demo12345")
        ops_ok = self.login("ops@demo.local", "demo12345")
        driver_ok = self.login("driver@demo.local", "demo12345")
        
        self.test("Owner login", owner_ok)
        self.test("Ops Admin login", ops_ok)
        self.test("Driver login", driver_ok)
        
        return owner_ok and ops_ok and driver_ok
    
    def test_rbac_bookings(self):
        """P0: Test RBAC on bookings endpoints"""
        self.log("\n=== P0: Testing RBAC Bookings ===", "info")
        
        # Get vehicles and customers for booking creation
        vehicles_resp = requests.get(f"{self.base_url}/api/vehicles", headers=self.headers("owner@demo.local"), timeout=10)
        customers_resp = requests.get(f"{self.base_url}/api/customers", headers=self.headers("owner@demo.local"), timeout=10)
        
        if vehicles_resp.status_code != 200 or customers_resp.status_code != 200:
            self.log("Could not fetch vehicles/customers for booking tests", "warn")
            return
        
        vehicles = vehicles_resp.json()
        customers = customers_resp.json()
        
        if not vehicles or not customers:
            self.log("No vehicles or customers found", "warn")
            return
        
        vehicle_id = vehicles[0].get("id")
        customer_id = customers[0].get("id")
        
        # Test 1: Driver should get 403 on POST /api/bookings
        booking_data = {
            "customer_id": customer_id,
            "vehicle_id": vehicle_id,
            "start_datetime": (datetime.now() + timedelta(days=10)).isoformat(),
            "end_datetime": (datetime.now() + timedelta(days=12)).isoformat(),
            "origin": "Jakarta",
            "destination": "Bandung",
            "base_price": 2000000
        }
        
        try:
            response = requests.post(f"{self.base_url}/api/bookings", json=booking_data, 
                                   headers=self.headers("driver@demo.local"), timeout=10)
            self.test(
                "Driver POST /api/bookings returns 403",
                response.status_code == 403,
                f"Expected 403, got {response.status_code}"
            )
        except Exception as e:
            self.test("Driver POST /api/bookings", False, str(e))
        
        # Test 2: Owner should succeed on POST /api/bookings
        try:
            response = requests.post(f"{self.base_url}/api/bookings", json=booking_data, 
                                   headers=self.headers("owner@demo.local"), timeout=10)
            self.test(
                "Owner POST /api/bookings returns 200",
                response.status_code == 200,
                f"Expected 200, got {response.status_code}"
            )
            if response.status_code == 200:
                self.booking_id = response.json().get("id")
                self.log(f"Created booking: {self.booking_id}", "info")
        except Exception as e:
            self.test("Owner POST /api/bookings", False, str(e))
        
        # Test 3: Ops Admin should succeed on POST /api/bookings
        booking_data2 = booking_data.copy()
        booking_data2["start_datetime"] = (datetime.now() + timedelta(days=15)).isoformat()
        booking_data2["end_datetime"] = (datetime.now() + timedelta(days=17)).isoformat()
        
        try:
            response = requests.post(f"{self.base_url}/api/bookings", json=booking_data2, 
                                   headers=self.headers("ops@demo.local"), timeout=10)
            self.test(
                "Ops Admin POST /api/bookings returns 200",
                response.status_code == 200,
                f"Expected 200, got {response.status_code}"
            )
        except Exception as e:
            self.test("Ops Admin POST /api/bookings", False, str(e))
        
        if not self.booking_id:
            self.log("No booking created, skipping mutation tests", "warn")
            return
        
        # Test 4: Driver should get 403 on PATCH /api/bookings/{id}
        try:
            response = requests.patch(f"{self.base_url}/api/bookings/{self.booking_id}", 
                                    json={"notes": "Driver trying to update"}, 
                                    headers=self.headers("driver@demo.local"), timeout=10)
            self.test(
                "Driver PATCH /api/bookings/{id} returns 403",
                response.status_code == 403,
                f"Expected 403, got {response.status_code}"
            )
        except Exception as e:
            self.test("Driver PATCH /api/bookings/{id}", False, str(e))
        
        # Test 5: Owner should succeed on PATCH /api/bookings/{id}
        try:
            response = requests.patch(f"{self.base_url}/api/bookings/{self.booking_id}", 
                                    json={"notes": "Owner update"}, 
                                    headers=self.headers("owner@demo.local"), timeout=10)
            self.test(
                "Owner PATCH /api/bookings/{id} returns 200",
                response.status_code == 200,
                f"Expected 200, got {response.status_code}"
            )
        except Exception as e:
            self.test("Owner PATCH /api/bookings/{id}", False, str(e))
        
        # Test 6: Driver should get 403 on POST /api/bookings/{id}/confirm
        try:
            response = requests.post(f"{self.base_url}/api/bookings/{self.booking_id}/confirm", 
                                   headers=self.headers("driver@demo.local"), timeout=10)
            self.test(
                "Driver POST /api/bookings/{id}/confirm returns 403",
                response.status_code == 403,
                f"Expected 403, got {response.status_code}"
            )
        except Exception as e:
            self.test("Driver POST /api/bookings/{id}/confirm", False, str(e))
        
        # Test 7: Owner should succeed on POST /api/bookings/{id}/confirm
        try:
            response = requests.post(f"{self.base_url}/api/bookings/{self.booking_id}/confirm", 
                                   headers=self.headers("owner@demo.local"), timeout=10)
            self.test(
                "Owner POST /api/bookings/{id}/confirm returns 200",
                response.status_code in [200, 400],  # 400 if already confirmed
                f"Expected 200/400, got {response.status_code}"
            )
        except Exception as e:
            self.test("Owner POST /api/bookings/{id}/confirm", False, str(e))
        
        # Test 8: Driver should get 403 on POST /api/bookings/{id}/cancel
        try:
            response = requests.post(f"{self.base_url}/api/bookings/{self.booking_id}/cancel", 
                                   headers=self.headers("driver@demo.local"), timeout=10)
            self.test(
                "Driver POST /api/bookings/{id}/cancel returns 403",
                response.status_code == 403,
                f"Expected 403, got {response.status_code}"
            )
        except Exception as e:
            self.test("Driver POST /api/bookings/{id}/cancel", False, str(e))
        
        # Test 9: Driver should get 403 on POST /api/bookings/{id}/complete
        try:
            response = requests.post(f"{self.base_url}/api/bookings/{self.booking_id}/complete", 
                                   headers=self.headers("driver@demo.local"), timeout=10)
            # NOTE: This should be 403 but current code has bug (uses get_current_user instead of MANAGER)
            # We'll test what it SHOULD be (403) and report if it's not
            self.test(
                "Driver POST /api/bookings/{id}/complete returns 403 (SHOULD BE 403)",
                response.status_code == 403,
                f"Expected 403, got {response.status_code} - BUG: endpoint uses get_current_user instead of MANAGER"
            )
        except Exception as e:
            self.test("Driver POST /api/bookings/{id}/complete", False, str(e))
        
        # Test 10: Driver CAN read bookings (GET /api/bookings)
        try:
            response = requests.get(f"{self.base_url}/api/bookings", 
                                  headers=self.headers("driver@demo.local"), timeout=10)
            self.test(
                "Driver GET /api/bookings returns 200 (read-only)",
                response.status_code == 200,
                f"Expected 200, got {response.status_code}"
            )
        except Exception as e:
            self.test("Driver GET /api/bookings", False, str(e))
        
        # Test 11: Driver CAN read booking detail (GET /api/bookings/{id})
        try:
            response = requests.get(f"{self.base_url}/api/bookings/{self.booking_id}", 
                                  headers=self.headers("driver@demo.local"), timeout=10)
            self.test(
                "Driver GET /api/bookings/{id} returns 200 (read-only)",
                response.status_code == 200,
                f"Expected 200, got {response.status_code}"
            )
        except Exception as e:
            self.test("Driver GET /api/bookings/{id}", False, str(e))
    
    def test_ownership_driver_checkin_checkout(self):
        """P0: Test driver ownership on checkin/checkout"""
        self.log("\n=== P0: Testing Driver Ownership (Checkin/Checkout) ===", "info")
        
        # Get all trips to find one belonging to driver@demo.local and one belonging to another driver
        try:
            trips_resp = requests.get(f"{self.base_url}/api/trips", 
                                    headers=self.headers("owner@demo.local"), timeout=10)
            if trips_resp.status_code != 200:
                self.log("Could not fetch trips", "warn")
                return
            
            trips = trips_resp.json()
            
            # Get driver IDs
            drivers_resp = requests.get(f"{self.base_url}/api/drivers", 
                                      headers=self.headers("owner@demo.local"), timeout=10)
            if drivers_resp.status_code != 200:
                self.log("Could not fetch drivers", "warn")
                return
            
            drivers = drivers_resp.json()
            driver_satu = next((d for d in drivers if d.get("name") == "Driver Satu"), None)
            other_driver = next((d for d in drivers if d.get("name") != "Driver Satu"), None)
            
            if not driver_satu or not other_driver:
                self.log("Could not find Driver Satu or another driver", "warn")
                return
            
            # Find trips
            driver_satu_trip = next((t for t in trips if t.get("driver_id") == driver_satu.get("id")), None)
            other_driver_trip = next((t for t in trips if t.get("driver_id") == other_driver.get("id")), None)
            
            if not driver_satu_trip:
                self.log("No trip found for Driver Satu, creating one via booking", "info")
                # Create a booking with driver_satu
                vehicles_resp = requests.get(f"{self.base_url}/api/vehicles", 
                                           headers=self.headers("owner@demo.local"), timeout=10)
                customers_resp = requests.get(f"{self.base_url}/api/customers", 
                                            headers=self.headers("owner@demo.local"), timeout=10)
                
                if vehicles_resp.status_code == 200 and customers_resp.status_code == 200:
                    vehicles = vehicles_resp.json()
                    customers = customers_resp.json()
                    
                    if vehicles and customers:
                        booking_data = {
                            "customer_id": customers[0].get("id"),
                            "vehicle_id": vehicles[0].get("id"),
                            "driver_id": driver_satu.get("id"),
                            "start_datetime": (datetime.now() + timedelta(days=1)).isoformat(),
                            "end_datetime": (datetime.now() + timedelta(days=2)).isoformat(),
                            "origin": "Jakarta",
                            "destination": "Bogor",
                            "base_price": 1500000
                        }
                        
                        booking_resp = requests.post(f"{self.base_url}/api/bookings", 
                                                   json=booking_data, 
                                                   headers=self.headers("owner@demo.local"), timeout=10)
                        if booking_resp.status_code == 200:
                            booking = booking_resp.json()
                            self.driver_booking_id = booking.get("id")
                            self.log(f"Created booking for Driver Satu: {self.driver_booking_id}", "info")
            
            # Test 1: Driver can checkin their own trip/booking
            if driver_satu_trip:
                try:
                    response = requests.post(f"{self.base_url}/api/driver/checkin", 
                                           json={"trip_id": driver_satu_trip.get("id")}, 
                                           headers=self.headers("driver@demo.local"), timeout=10)
                    self.test(
                        "Driver can checkin their own trip",
                        response.status_code == 200,
                        f"Expected 200, got {response.status_code}"
                    )
                except Exception as e:
                    self.test("Driver checkin own trip", False, str(e))
            elif hasattr(self, 'driver_booking_id'):
                try:
                    response = requests.post(f"{self.base_url}/api/driver/checkin", 
                                           json={"booking_id": self.driver_booking_id}, 
                                           headers=self.headers("driver@demo.local"), timeout=10)
                    self.test(
                        "Driver can checkin their own booking",
                        response.status_code == 200,
                        f"Expected 200, got {response.status_code}"
                    )
                    if response.status_code == 200:
                        self.driver_trip_id = response.json().get("id")
                except Exception as e:
                    self.test("Driver checkin own booking", False, str(e))
            
            # Test 2: Driver CANNOT checkin another driver's trip
            if other_driver_trip:
                try:
                    response = requests.post(f"{self.base_url}/api/driver/checkin", 
                                           json={"trip_id": other_driver_trip.get("id")}, 
                                           headers=self.headers("driver@demo.local"), timeout=10)
                    self.test(
                        "Driver CANNOT checkin another driver's trip (403)",
                        response.status_code == 403,
                        f"Expected 403, got {response.status_code}"
                    )
                except Exception as e:
                    self.test("Driver checkin other's trip", False, str(e))
            
            # Test 3: Driver can checkout their own trip
            if self.driver_trip_id:
                try:
                    response = requests.post(f"{self.base_url}/api/driver/checkout", 
                                           json={"trip_id": self.driver_trip_id}, 
                                           headers=self.headers("driver@demo.local"), timeout=10)
                    self.test(
                        "Driver can checkout their own trip",
                        response.status_code == 200,
                        f"Expected 200, got {response.status_code}"
                    )
                except Exception as e:
                    self.test("Driver checkout own trip", False, str(e))
            
            # Test 4: Driver CANNOT checkout another driver's trip
            if other_driver_trip:
                try:
                    response = requests.post(f"{self.base_url}/api/driver/checkout", 
                                           json={"trip_id": other_driver_trip.get("id")}, 
                                           headers=self.headers("driver@demo.local"), timeout=10)
                    self.test(
                        "Driver CANNOT checkout another driver's trip (403)",
                        response.status_code == 403,
                        f"Expected 403, got {response.status_code}"
                    )
                except Exception as e:
                    self.test("Driver checkout other's trip", False, str(e))
            
        except Exception as e:
            self.log(f"Error in ownership tests: {str(e)}", "fail")
    
    def test_ssot_wa_payload(self):
        """P1: Test SSOT WhatsApp payload in events"""
        self.log("\n=== P1: Testing SSOT WhatsApp Payload ===", "info")
        
        # Get automation events
        try:
            response = requests.get(f"{self.base_url}/api/automation/events?limit=100", 
                                  headers=self.headers("owner@demo.local"), timeout=10)
            
            if response.status_code != 200:
                self.log(f"Could not fetch events: {response.status_code}", "warn")
                return
            
            events = response.json()
            
            # Find trip.started, trip.arrived, trip.completed events
            trip_events = [e for e in events if e.get("event_type") in ["trip.started", "trip.arrived", "trip.completed"]]
            
            if not trip_events:
                self.log("No trip events found, SSOT payload cannot be verified", "warn")
                return
            
            # Check each trip event has complete WA payload
            required_fields = ["company", "destination", "driver_phone", "pickup", "vehicle_name", "customer_name"]
            
            for event in trip_events[:5]:  # Check first 5 events
                event_type = event.get("event_type")
                payload = event.get("payload", {})
                
                missing_fields = [f for f in required_fields if not payload.get(f)]
                
                self.test(
                    f"Event {event_type} has complete WA payload",
                    len(missing_fields) == 0,
                    f"Missing fields: {missing_fields}" if missing_fields else ""
                )
                
                # Check specific fields are not None/empty
                if payload.get("company"):
                    self.test(
                        f"Event {event_type} has non-empty company",
                        payload.get("company") not in [None, "", "None"],
                        f"company is {payload.get('company')}"
                    )
                
                if payload.get("driver_phone"):
                    self.test(
                        f"Event {event_type} has non-empty driver_phone",
                        payload.get("driver_phone") not in [None, "", "None"],
                        f"driver_phone is {payload.get('driver_phone')}"
                    )
            
            # Compare with dispatch events (trip.enroute) for consistency
            dispatch_events = [e for e in events if e.get("event_type") == "trip.enroute"]
            
            if dispatch_events and trip_events:
                dispatch_payload = dispatch_events[0].get("payload", {})
                trip_payload = trip_events[0].get("payload", {})
                
                # Check if both have same structure
                dispatch_keys = set(dispatch_payload.keys())
                trip_keys = set(trip_payload.keys())
                
                self.test(
                    "Trip events and dispatch events have consistent payload structure",
                    len(dispatch_keys.intersection(trip_keys)) >= 5,  # At least 5 common fields
                    f"Dispatch keys: {dispatch_keys}, Trip keys: {trip_keys}"
                )
            
        except Exception as e:
            self.log(f"Error in SSOT payload tests: {str(e)}", "fail")
    
    def test_ownership_locations(self):
        """P1: Test driver ownership on POST /api/locations"""
        self.log("\n=== P1: Testing Driver Ownership (Locations) ===", "info")
        
        # Get trips
        try:
            trips_resp = requests.get(f"{self.base_url}/api/trips", 
                                    headers=self.headers("owner@demo.local"), timeout=10)
            if trips_resp.status_code != 200:
                self.log("Could not fetch trips", "warn")
                return
            
            trips = trips_resp.json()
            
            # Get driver IDs
            drivers_resp = requests.get(f"{self.base_url}/api/drivers", 
                                      headers=self.headers("owner@demo.local"), timeout=10)
            if drivers_resp.status_code != 200:
                self.log("Could not fetch drivers", "warn")
                return
            
            drivers = drivers_resp.json()
            driver_satu = next((d for d in drivers if d.get("name") == "Driver Satu"), None)
            other_driver = next((d for d in drivers if d.get("name") != "Driver Satu"), None)
            
            if not driver_satu or not other_driver:
                self.log("Could not find drivers", "warn")
                return
            
            driver_satu_trip = next((t for t in trips if t.get("driver_id") == driver_satu.get("id")), None)
            other_driver_trip = next((t for t in trips if t.get("driver_id") == other_driver.get("id")), None)
            
            # Test 1: Driver can POST location for their own trip
            if driver_satu_trip or self.driver_trip_id:
                trip_id = driver_satu_trip.get("id") if driver_satu_trip else self.driver_trip_id
                try:
                    response = requests.post(f"{self.base_url}/api/locations", 
                                           json={
                                               "trip_id": trip_id,
                                               "lat": -6.2088,
                                               "lng": 106.8456,
                                               "speed": 60,
                                               "heading": 90
                                           }, 
                                           headers=self.headers("driver@demo.local"), timeout=10)
                    self.test(
                        "Driver can POST location for their own trip",
                        response.status_code == 200,
                        f"Expected 200, got {response.status_code}"
                    )
                except Exception as e:
                    self.test("Driver POST location own trip", False, str(e))
            
            # Test 2: Driver CANNOT POST location for another driver's trip
            if other_driver_trip:
                try:
                    response = requests.post(f"{self.base_url}/api/locations", 
                                           json={
                                               "trip_id": other_driver_trip.get("id"),
                                               "lat": -6.2088,
                                               "lng": 106.8456,
                                               "speed": 60,
                                               "heading": 90
                                           }, 
                                           headers=self.headers("driver@demo.local"), timeout=10)
                    self.test(
                        "Driver CANNOT POST location for another driver's trip (403)",
                        response.status_code == 403,
                        f"Expected 403, got {response.status_code}"
                    )
                except Exception as e:
                    self.test("Driver POST location other's trip", False, str(e))
            
            # Test 3: Owner/ops_admin can POST location for any trip (unrestricted)
            if other_driver_trip:
                try:
                    response = requests.post(f"{self.base_url}/api/locations", 
                                           json={
                                               "trip_id": other_driver_trip.get("id"),
                                               "lat": -6.2088,
                                               "lng": 106.8456,
                                               "speed": 60,
                                               "heading": 90
                                           }, 
                                           headers=self.headers("owner@demo.local"), timeout=10)
                    self.test(
                        "Owner can POST location for any trip (200)",
                        response.status_code == 200,
                        f"Expected 200, got {response.status_code}"
                    )
                except Exception as e:
                    self.test("Owner POST location any trip", False, str(e))
            
        except Exception as e:
            self.log(f"Error in locations ownership tests: {str(e)}", "fail")
    
    def test_notifications_visibility(self):
        """P2: Test notifications visibility (read/dismiss)"""
        self.log("\n=== P2: Testing Notifications Visibility ===", "info")
        
        # Trigger notification scan as owner
        try:
            response = requests.post(f"{self.base_url}/api/notifications/scan", 
                                   headers=self.headers("owner@demo.local"), timeout=10)
            self.test(
                "Owner can trigger notification scan",
                response.status_code == 200,
                f"Expected 200, got {response.status_code}"
            )
        except Exception as e:
            self.test("Owner trigger notification scan", False, str(e))
        
        # Get notifications as owner
        try:
            response = requests.get(f"{self.base_url}/api/notifications", 
                                  headers=self.headers("owner@demo.local"), timeout=10)
            
            if response.status_code != 200:
                self.log("Could not fetch notifications", "warn")
                return
            
            notifications = response.json()
            
            # Find a notification with target_role='manager'
            manager_notif = next((n for n in notifications if n.get("target_role") == "manager"), None)
            
            if not manager_notif:
                self.log("No manager-targeted notification found", "warn")
                return
            
            manager_notif_id = manager_notif.get("id")
            
            # Test 1: Owner can read manager notification
            try:
                response = requests.post(f"{self.base_url}/api/notifications/{manager_notif_id}/read", 
                                       headers=self.headers("owner@demo.local"), timeout=10)
                self.test(
                    "Owner can read manager notification (200)",
                    response.status_code == 200,
                    f"Expected 200, got {response.status_code}"
                )
            except Exception as e:
                self.test("Owner read manager notification", False, str(e))
            
            # Test 2: Driver CANNOT read manager notification (404)
            try:
                response = requests.post(f"{self.base_url}/api/notifications/{manager_notif_id}/read", 
                                       headers=self.headers("driver@demo.local"), timeout=10)
                self.test(
                    "Driver CANNOT read manager notification (404)",
                    response.status_code == 404,
                    f"Expected 404, got {response.status_code}"
                )
            except Exception as e:
                self.test("Driver read manager notification", False, str(e))
            
            # Test 3: Owner can dismiss manager notification
            try:
                response = requests.post(f"{self.base_url}/api/notifications/{manager_notif_id}/dismiss", 
                                       headers=self.headers("owner@demo.local"), timeout=10)
                self.test(
                    "Owner can dismiss manager notification (200)",
                    response.status_code == 200,
                    f"Expected 200, got {response.status_code}"
                )
            except Exception as e:
                self.test("Owner dismiss manager notification", False, str(e))
            
            # Test 4: Driver CANNOT dismiss manager notification (404)
            # Find another manager notification
            manager_notif2 = next((n for n in notifications if n.get("target_role") == "manager" and n.get("id") != manager_notif_id), None)
            
            if manager_notif2:
                try:
                    response = requests.post(f"{self.base_url}/api/notifications/{manager_notif2.get('id')}/dismiss", 
                                           headers=self.headers("driver@demo.local"), timeout=10)
                    self.test(
                        "Driver CANNOT dismiss manager notification (404)",
                        response.status_code == 404,
                        f"Expected 404, got {response.status_code}"
                    )
                except Exception as e:
                    self.test("Driver dismiss manager notification", False, str(e))
            
        except Exception as e:
            self.log(f"Error in notifications visibility tests: {str(e)}", "fail")
    
    def test_regression(self):
        """Regression: Full booking flow, anti double-booking, critical endpoints"""
        self.log("\n=== Regression Testing ===", "info")
        
        # Test 1: Full booking flow (create -> confirm -> payment -> status)
        try:
            vehicles_resp = requests.get(f"{self.base_url}/api/vehicles", 
                                       headers=self.headers("owner@demo.local"), timeout=10)
            customers_resp = requests.get(f"{self.base_url}/api/customers", 
                                        headers=self.headers("owner@demo.local"), timeout=10)
            
            if vehicles_resp.status_code == 200 and customers_resp.status_code == 200:
                vehicles = vehicles_resp.json()
                customers = customers_resp.json()
                
                if vehicles and customers:
                    # Create booking
                    booking_data = {
                        "customer_id": customers[0].get("id"),
                        "vehicle_id": vehicles[0].get("id"),
                        "start_datetime": (datetime.now() + timedelta(days=20)).isoformat(),
                        "end_datetime": (datetime.now() + timedelta(days=22)).isoformat(),
                        "origin": "Jakarta",
                        "destination": "Yogyakarta",
                        "base_price": 3000000
                    }
                    
                    create_resp = requests.post(f"{self.base_url}/api/bookings", 
                                              json=booking_data, 
                                              headers=self.headers("owner@demo.local"), timeout=10)
                    
                    self.test(
                        "Regression: Create booking",
                        create_resp.status_code == 200,
                        f"Expected 200, got {create_resp.status_code}"
                    )
                    
                    if create_resp.status_code == 200:
                        booking = create_resp.json()
                        booking_id = booking.get("id")
                        
                        # Confirm booking
                        confirm_resp = requests.post(f"{self.base_url}/api/bookings/{booking_id}/confirm", 
                                                   headers=self.headers("owner@demo.local"), timeout=10)
                        
                        self.test(
                            "Regression: Confirm booking",
                            confirm_resp.status_code in [200, 400],  # 400 if already confirmed
                            f"Expected 200/400, got {confirm_resp.status_code}"
                        )
                        
                        # Check status
                        status_resp = requests.get(f"{self.base_url}/api/bookings/{booking_id}", 
                                                 headers=self.headers("owner@demo.local"), timeout=10)
                        
                        if status_resp.status_code == 200:
                            booking_status = status_resp.json().get("status")
                            self.test(
                                "Regression: Booking status is confirmed",
                                booking_status == "confirmed",
                                f"Expected 'confirmed', got {booking_status}"
                            )
        except Exception as e:
            self.test("Regression: Full booking flow", False, str(e))
        
        # Test 2: Anti double-booking (INV-4)
        try:
            vehicles_resp = requests.get(f"{self.base_url}/api/vehicles", 
                                       headers=self.headers("owner@demo.local"), timeout=10)
            customers_resp = requests.get(f"{self.base_url}/api/customers", 
                                        headers=self.headers("owner@demo.local"), timeout=10)
            
            if vehicles_resp.status_code == 200 and customers_resp.status_code == 200:
                vehicles = vehicles_resp.json()
                customers = customers_resp.json()
                
                if vehicles and customers:
                    # Create first booking
                    start_dt = (datetime.now() + timedelta(days=30)).isoformat()
                    end_dt = (datetime.now() + timedelta(days=32)).isoformat()
                    
                    booking_data1 = {
                        "customer_id": customers[0].get("id"),
                        "vehicle_id": vehicles[0].get("id"),
                        "start_datetime": start_dt,
                        "end_datetime": end_dt,
                        "origin": "Jakarta",
                        "destination": "Bali",
                        "base_price": 5000000
                    }
                    
                    create_resp1 = requests.post(f"{self.base_url}/api/bookings", 
                                               json=booking_data1, 
                                               headers=self.headers("owner@demo.local"), timeout=10)
                    
                    if create_resp1.status_code == 200:
                        # Try to create overlapping booking (should fail with 400)
                        booking_data2 = booking_data1.copy()
                        booking_data2["start_datetime"] = (datetime.now() + timedelta(days=31)).isoformat()
                        booking_data2["end_datetime"] = (datetime.now() + timedelta(days=33)).isoformat()
                        
                        create_resp2 = requests.post(f"{self.base_url}/api/bookings", 
                                                   json=booking_data2, 
                                                   headers=self.headers("owner@demo.local"), timeout=10)
                        
                        self.test(
                            "Regression: Anti double-booking rejects overlap (400)",
                            create_resp2.status_code == 400,
                            f"Expected 400, got {create_resp2.status_code}"
                        )
                        
                        if create_resp2.status_code == 400:
                            error_msg = create_resp2.json().get("detail", "")
                            self.test(
                                "Regression: Error message mentions conflict",
                                "bentrok" in error_msg.lower() or "conflict" in error_msg.lower(),
                                f"Error message: {error_msg}"
                            )
        except Exception as e:
            self.test("Regression: Anti double-booking", False, str(e))
        
        # Test 3: Critical endpoints return 200 without 5xx
        critical_endpoints = [
            "/api/dashboard",
            "/api/vehicles",
            "/api/drivers",
            "/api/customers",
            "/api/bookings",
            "/api/trips",
            "/api/notifications"
        ]
        
        for endpoint in critical_endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", 
                                      headers=self.headers("owner@demo.local"), timeout=10)
                self.test(
                    f"Regression: {endpoint} returns 200 (no 5xx)",
                    response.status_code == 200,
                    f"Expected 200, got {response.status_code}"
                )
            except Exception as e:
                self.test(f"Regression: {endpoint}", False, str(e))
    
    def run_all_tests(self):
        """Run all test suites"""
        self.log("\n" + "="*70, "info")
        self.log("RBAC & SSOT WhatsApp Payload Security Hardening Test Suite", "info")
        self.log("="*70, "info")
        
        # Run tests in order
        if not self.test_auth():
            self.log("\n⚠️  Authentication failed. Cannot proceed with other tests.", "warn")
            return False
        
        # P0 tests
        self.test_rbac_bookings()
        self.test_ownership_driver_checkin_checkout()
        
        # P1 tests
        self.test_ssot_wa_payload()
        self.test_ownership_locations()
        
        # P2 tests
        self.test_notifications_visibility()
        
        # Regression tests
        self.test_regression()
        
        # Print summary
        self.log("\n" + "="*70, "info")
        self.log("TEST SUMMARY", "info")
        self.log("="*70, "info")
        self.log(f"Total Tests: {self.tests_run}", "info")
        self.log(f"Passed: {self.tests_passed}", "pass")
        self.log(f"Failed: {self.tests_failed}", "fail" if self.tests_failed > 0 else "info")
        
        if self.tests_failed > 0:
            self.log("\nFailed Tests:", "fail")
            for failure in self.failures:
                self.log(f"  - {failure}", "fail")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\nSuccess Rate: {success_rate:.1f}%", "pass" if success_rate >= 90 else "warn")
        
        return self.tests_failed == 0


def main():
    tester = RBACTestSuite()
    success = tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

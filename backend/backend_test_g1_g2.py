"""
Backend API tests for G1 (booking.cancelled event) and G2 (dispatch POD → trip.completed).

Tests:
- G1: booking.cancelled event emission + automation rule execution
- G1: idempotency (no duplicate runs)
- G1: resource release (vehicle, trip cancellation)
- G2: dispatch POD → trip.completed event + automation
- G2: consistency with driver checkout
- Regression: payment flow, state machine, core endpoints
"""
import requests
import sys
from datetime import datetime, timedelta

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

class TestRunner:
    def __init__(self):
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []

    def log(self, msg):
        print(f"  {msg}")

    def test(self, name, condition, details=""):
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            print(f"✅ {name}")
            if details:
                self.log(details)
        else:
            self.tests_failed += 1
            self.failures.append(f"{name}: {details}")
            print(f"❌ {name}")
            if details:
                self.log(f"FAILED: {details}")

    def api_call(self, method, endpoint, expected_status=200, data=None, files=None, description="", multipart=False):
        url = f"{BASE_URL}/{endpoint}"
        headers = {'Authorization': f'Bearer {self.token}'} if self.token else {}
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                if multipart:
                    # Send as multipart form data (for file uploads or form data)
                    response = requests.post(url, headers={'Authorization': f'Bearer {self.token}'}, data=data, timeout=30)
                elif files:
                    response = requests.post(url, headers={'Authorization': f'Bearer {self.token}'}, data=data, files=files, timeout=30)
                else:
                    headers['Content-Type'] = 'application/json'
                    response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'PATCH':
                headers['Content-Type'] = 'application/json'
                response = requests.patch(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                return None, None

            success = response.status_code == expected_status
            result = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            
            if not success:
                self.log(f"Status: {response.status_code} (expected {expected_status})")
                self.log(f"Response: {result}")
            
            return success, result
        except Exception as e:
            self.log(f"Exception: {str(e)}")
            return False, {}

    def login(self, email, password):
        success, response = self.api_call('POST', 'auth/login', 200, 
                                         data={"email": email, "password": password},
                                         description="Login")
        if success and 'token' in response:
            self.token = response['token']
            return True
        return False

    def summary(self):
        print(f"\n{'='*60}")
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} passed")
        if self.failures:
            print(f"\n❌ Failed tests:")
            for f in self.failures:
                print(f"  - {f}")
        print(f"{'='*60}\n")
        return 0 if self.tests_failed == 0 else 1


def main():
    runner = TestRunner()
    
    print("="*60)
    print("🧪 Testing G1 (booking.cancelled) & G2 (dispatch POD → trip.completed)")
    print("="*60 + "\n")

    # === LOGIN ===
    print("🔐 Login as owner...")
    if not runner.login("owner@demo.local", "demo12345"):
        print("❌ Login failed, stopping tests")
        return 1
    print("✅ Logged in as owner\n")

    # === SETUP: Get required IDs ===
    print("📋 Setup: Getting customer, vehicle, driver IDs...")
    success, customers = runner.api_call('GET', 'customers?limit=1')
    success2, vehicles = runner.api_call('GET', 'vehicles?limit=1')
    success3, drivers = runner.api_call('GET', 'drivers?limit=1')
    
    if not (success and customers and success2 and vehicles and success3 and drivers):
        print("❌ Failed to get required data")
        return 1
    
    customer_id = customers[0]['id']
    vehicle_id = vehicles[0]['id']
    driver_id = drivers[0]['id']
    print(f"✅ Got customer: {customer_id}, vehicle: {vehicle_id}, driver: {driver_id}\n")

    # === G1: TEST booking.cancelled EVENT ===
    print("="*60)
    print("🧪 G1: Testing booking.cancelled event emission")
    print("="*60 + "\n")

    # Create a booking for 2027 (to avoid seed clashes) - use timestamp to avoid conflicts
    import random
    from datetime import datetime as dt, timedelta as td
    base_date = dt(2027, 6, 1)
    day_offset = random.randint(1, 200)
    start_date = base_date + td(days=day_offset)
    end_date = start_date + td(days=1)
    start_dt = start_date.strftime("%Y-%m-%dT08:00:00+00:00")
    end_dt = end_date.strftime("%Y-%m-%dT18:00:00+00:00")
    
    print("1️⃣ Creating booking...")
    success, booking = runner.api_call('POST', 'bookings', 200, data={
        "customer_id": customer_id,
        "vehicle_id": vehicle_id,
        "origin": "Jakarta",
        "destination": "Bandung",
        "start_datetime": start_dt,
        "end_datetime": end_dt,
        "base_price": 2000000,
        "notes": "Test G1 booking.cancelled"
    })
    runner.test("G1.1: Create booking", success and booking.get('id'), 
                f"Booking ID: {booking.get('id')}, Code: {booking.get('code')}")
    
    if not success:
        print("❌ Cannot proceed without booking")
        return runner.summary()
    
    booking_id = booking['id']
    booking_code = booking.get('code')

    # Verify booking.cancelled event type exists in catalog
    print("\n2️⃣ Checking event catalog...")
    success, event_types = runner.api_call('GET', 'automation/event-types')
    has_cancelled_event = any(e.get('key') == 'booking.cancelled' for e in event_types.get('events', []))
    runner.test("G1.2: booking.cancelled in event catalog", has_cancelled_event,
                "Event type 'booking.cancelled' found in catalog")

    # Cancel the booking
    print("\n3️⃣ Cancelling booking...")
    success, cancelled = runner.api_call('POST', f'bookings/{booking_id}/cancel', 200)
    runner.test("G1.3: Cancel booking API", success and cancelled.get('status') == 'cancelled',
                f"Status: {cancelled.get('status')}")

    # Wait a moment for event processing
    import time
    time.sleep(1)

    # Check if booking.cancelled event was emitted
    print("\n4️⃣ Checking booking.cancelled event...")
    success, events = runner.api_call('GET', 'automation/events?type=booking.cancelled&limit=50')
    booking_cancelled_event = None
    if success and events:
        for evt in events:
            payload = evt.get('payload', {})
            if payload.get('booking_id') == booking_id:
                booking_cancelled_event = evt
                break
    
    runner.test("G1.4: booking.cancelled event emitted", booking_cancelled_event is not None,
                f"Event ID: {booking_cancelled_event.get('id') if booking_cancelled_event else 'NOT FOUND'}")

    # Check automation rule exists
    print("\n5️⃣ Checking automation rule...")
    success, rules = runner.api_call('GET', 'automation/rules?event_type=booking.cancelled')
    cancel_rule = None
    if success and rules:
        for rule in rules:
            if 'pembatalan' in rule.get('name', '').lower():
                cancel_rule = rule
                break
    
    runner.test("G1.5: Automation rule exists", cancel_rule is not None,
                f"Rule: {cancel_rule.get('name') if cancel_rule else 'NOT FOUND'}")

    # Check automation run was created
    print("\n6️⃣ Checking automation run...")
    success, runs = runner.api_call('GET', 'automation/runs?event_type=booking.cancelled&limit=50')
    booking_run = None
    if success and runs:
        for run in runs:
            if booking_cancelled_event and run.get('event_id') == booking_cancelled_event.get('id'):
                booking_run = run
                break
    
    runner.test("G1.6: Automation run created", booking_run is not None,
                f"Run ID: {booking_run.get('id') if booking_run else 'NOT FOUND'}, Status: {booking_run.get('status') if booking_run else 'N/A'}")

    # Check actions in the run
    if booking_run:
        actions = booking_run.get('actions', [])
        has_send_wa = any(a.get('type') == 'send_wa' for a in actions)
        has_notification = any(a.get('type') == 'create_notification' for a in actions)
        
        runner.test("G1.7: send_wa action executed", has_send_wa,
                    f"Actions: {[a.get('type') for a in actions]}")
        runner.test("G1.8: create_notification action executed", has_notification,
                    f"Actions: {[a.get('type') for a in actions]}")

    # === G1 IDEMPOTENCY TEST ===
    print("\n7️⃣ Testing idempotency (cancel again)...")
    success, cancelled2 = runner.api_call('POST', f'bookings/{booking_id}/cancel', 200)
    runner.test("G1.9: Idempotent cancel (no crash)", success,
                "Second cancel should not crash")

    time.sleep(1)
    success, runs2 = runner.api_call('GET', 'automation/runs?event_type=booking.cancelled&limit=50')
    run_count = 0
    if success and runs2:
        for run in runs2:
            if booking_cancelled_event and run.get('event_id') == booking_cancelled_event.get('id'):
                run_count += 1
    
    runner.test("G1.10: No duplicate automation run", run_count == 1,
                f"Run count for same event: {run_count} (should be 1)")

    # === G1 RESOURCE RELEASE TEST (RC-04) ===
    print("\n8️⃣ Checking resource release (RC-04)...")
    success, vehicle = runner.api_call('GET', f'vehicles/{vehicle_id}')
    vehicle_status = vehicle.get('status') if success else None
    
    # Check if there are other active trips for this vehicle
    success2, all_trips = runner.api_call('GET', f'trips?vehicle_id={vehicle_id}&limit=50')
    other_active_trips = []
    if success2:
        for trip in all_trips:
            if trip.get('status') in ['standby', 'to_pickup', 'on_trip'] and trip.get('booking_id') != booking_id:
                other_active_trips.append(trip.get('id'))
    
    # Vehicle should be released ONLY if there are no other active trips
    if other_active_trips:
        runner.test("G1.11: Vehicle status (has other active trips)", 
                    vehicle_status == 'on_trip',
                    f"Vehicle correctly remains on_trip (other active trips: {len(other_active_trips)})")
    else:
        runner.test("G1.11: Vehicle released (no other active trips)", 
                    vehicle_status == 'available',
                    f"Vehicle status: {vehicle_status}")

    # === G2: TEST dispatch POD → trip.completed ===
    print("\n" + "="*60)
    print("🧪 G2: Testing dispatch POD → trip.completed")
    print("="*60 + "\n")

    # Create a new booking for G2 test - use different dates
    day_offset2 = random.randint(1, 200)
    start_date2 = base_date + td(days=day_offset2 + 50)
    end_date2 = start_date2 + td(days=1)
    start_dt2 = start_date2.strftime("%Y-%m-%dT09:00:00+00:00")
    end_dt2 = end_date2.strftime("%Y-%m-%dT17:00:00+00:00")
    
    print("1️⃣ Creating booking for G2...")
    success, booking2 = runner.api_call('POST', 'bookings', 200, data={
        "customer_id": customer_id,
        "vehicle_id": vehicle_id,
        "origin": "Surabaya",
        "destination": "Malang",
        "start_datetime": start_dt2,
        "end_datetime": end_dt2,
        "base_price": 1500000,
        "notes": "Test G2 dispatch POD"
    })
    runner.test("G2.1: Create booking", success and booking2.get('id'),
                f"Booking ID: {booking2.get('id')}")
    
    if not success:
        print("❌ Cannot proceed without booking")
        return runner.summary()
    
    booking_id2 = booking2['id']

    # Assign driver and vehicle (creates standby trip)
    print("\n2️⃣ Assigning driver and vehicle...")
    success, assign_result = runner.api_call('POST', f'dispatch/{booking_id2}/assign', 200, data={
        "driver_id": driver_id,
        "vehicle_id": vehicle_id
    })
    runner.test("G2.2: Assign driver/vehicle", success and assign_result.get('trip'),
                f"Trip ID: {assign_result.get('trip', {}).get('id')}")
    
    if not success:
        print("❌ Cannot proceed without trip assignment")
        return runner.summary()
    
    trip_id = assign_result['trip']['id']

    # Upload POD via dispatch path (multipart form)
    print("\n3️⃣ Uploading POD via dispatch...")
    # Note: The endpoint expects Form data, not JSON
    success, pod_result = runner.api_call('POST', f'dispatch/trips/{trip_id}/pod', 200,
                                         data={'recipient_name': 'Budi', 'note': 'Paket diterima'},
                                         multipart=True)
    
    runner.test("G2.3: Upload POD", success,
                f"Trip status: {pod_result.get('status')}")
    runner.test("G2.4: Trip completed after POD", pod_result.get('status') == 'completed',
                f"Expected 'completed', got '{pod_result.get('status')}'")

    # Check booking is completed
    print("\n4️⃣ Checking booking completion...")
    success, booking2_final = runner.api_call('GET', f'bookings/{booking_id2}')
    runner.test("G2.5: Booking completed", booking2_final.get('status') == 'completed',
                f"Booking status: {booking2_final.get('status')}")

    # Wait for event processing
    time.sleep(1)

    # Check trip.completed event was emitted
    print("\n5️⃣ Checking trip.completed event...")
    success, trip_events = runner.api_call('GET', 'automation/events?type=trip.completed&limit=50')
    trip_completed_event = None
    if success and trip_events:
        for evt in trip_events:
            payload = evt.get('payload', {})
            if payload.get('booking_id') == booking_id2:
                trip_completed_event = evt
                break
    
    runner.test("G2.6: trip.completed event emitted", trip_completed_event is not None,
                f"Event ID: {trip_completed_event.get('id') if trip_completed_event else 'NOT FOUND'}")

    # Check automation run for "Terima kasih + ulasan"
    print("\n6️⃣ Checking automation run...")
    success, trip_runs = runner.api_call('GET', 'automation/runs?event_type=trip.completed&limit=50')
    trip_run = None
    if success and trip_runs:
        for run in trip_runs:
            if trip_completed_event and run.get('event_id') == trip_completed_event.get('id'):
                trip_run = run
                break
    
    runner.test("G2.7: Automation run for trip.completed", trip_run is not None,
                f"Run ID: {trip_run.get('id') if trip_run else 'NOT FOUND'}")

    # Check send_wa action
    if trip_run:
        actions = trip_run.get('actions', [])
        has_send_wa = any(a.get('type') == 'send_wa' and a.get('status') == 'success' for a in actions)
        runner.test("G2.8: send_wa action successful", has_send_wa,
                    f"Actions: {[(a.get('type'), a.get('status')) for a in actions]}")

    # Check vehicle released
    print("\n7️⃣ Checking vehicle release...")
    success, vehicle2 = runner.api_call('GET', f'vehicles/{vehicle_id}')
    vehicle_status2 = vehicle2.get('status') if success else None
    
    # Check if there are other active trips
    success2, all_trips2 = runner.api_call('GET', f'trips?vehicle_id={vehicle_id}&limit=50')
    other_active_trips2 = []
    if success2:
        for trip in all_trips2:
            if trip.get('status') in ['standby', 'to_pickup', 'on_trip'] and trip.get('id') != trip_id:
                other_active_trips2.append(trip.get('id'))
    
    if other_active_trips2:
        runner.test("G2.9: Vehicle status (has other active trips)", 
                    vehicle_status2 == 'on_trip',
                    f"Vehicle correctly remains on_trip (other active trips: {len(other_active_trips2)})")
    else:
        runner.test("G2.9: Vehicle released (no other active trips)", 
                    vehicle_status2 == 'available',
                    f"Vehicle status: {vehicle_status2}")

    # === G2 REGRESSION: Driver checkout still works ===
    print("\n" + "="*60)
    print("🧪 G2 REGRESSION: Driver checkout path")
    print("="*60 + "\n")

    # Create another booking
    day_offset3 = random.randint(1, 200)
    start_date3 = base_date + td(days=day_offset3 + 100)
    end_date3 = start_date3 + td(days=1)
    start_dt3 = start_date3.strftime("%Y-%m-%dT10:00:00+00:00")
    end_dt3 = end_date3.strftime("%Y-%m-%dT16:00:00+00:00")
    
    print("1️⃣ Creating booking for driver checkout test...")
    success, booking3 = runner.api_call('POST', 'bookings', 200, data={
        "customer_id": customer_id,
        "vehicle_id": vehicle_id,
        "driver_id": driver_id,
        "origin": "Yogyakarta",
        "destination": "Solo",
        "start_datetime": start_dt3,
        "end_datetime": end_dt3,
        "base_price": 800000
    })
    runner.test("G2.REG.1: Create booking", success and booking3.get('id'))
    
    if success:
        booking_id3 = booking3['id']
        
        # Driver checkin
        print("\n2️⃣ Driver checkin...")
        success, checkin_result = runner.api_call('POST', 'driver/checkin', 200, data={
            "booking_id": booking_id3
        })
        runner.test("G2.REG.2: Driver checkin", success and checkin_result.get('id'))
        
        if success:
            trip_id3 = checkin_result['id']
            
            # Driver checkout
            print("\n3️⃣ Driver checkout...")
            success, checkout_result = runner.api_call('POST', 'driver/checkout', 200, data={
                "trip_id": trip_id3
            })
            runner.test("G2.REG.3: Driver checkout", success and checkout_result.get('status') == 'completed')
            
            # Check trip.completed event
            time.sleep(1)
            success, events3 = runner.api_call('GET', 'automation/events?type=trip.completed&limit=50')
            has_event3 = False
            if success and events3:
                for evt in events3:
                    if evt.get('payload', {}).get('booking_id') == booking_id3:
                        has_event3 = True
                        break
            runner.test("G2.REG.4: trip.completed event from driver checkout", has_event3)

    # === REGRESSION: Payment flow ===
    print("\n" + "="*60)
    print("🧪 REGRESSION: Payment flow (RC-01/RC-11)")
    print("="*60 + "\n")

    # Create booking for payment test
    day_offset4 = random.randint(1, 200)
    start_date4 = base_date + td(days=day_offset4 + 150)
    end_date4 = start_date4 + td(days=1)
    start_dt4 = start_date4.strftime("%Y-%m-%dT08:00:00+00:00")
    end_dt4 = end_date4.strftime("%Y-%m-%dT18:00:00+00:00")
    
    success, booking4 = runner.api_call('POST', 'bookings', 200, data={
        "customer_id": customer_id,
        "vehicle_id": vehicle_id,
        "origin": "Semarang",
        "destination": "Purwokerto",
        "start_datetime": start_dt4,
        "end_datetime": end_dt4,
        "base_price": 1000000
    })
    
    if success and booking4.get('id'):
        booking_id4 = booking4['id']
        
        # Pay DP (400k of 1M)
        print("1️⃣ Paying DP (400k)...")
        success, payment1 = runner.api_call('POST', 'payments', 200, data={
            "booking_id": booking_id4,
            "amount": 400000,
            "type": "transfer"
        })
        runner.test("REG.PAY.1: DP payment", success)
        
        # Check payment_status = 'dp'
        success, bk4 = runner.api_call('GET', f'bookings/{booking_id4}')
        runner.test("REG.PAY.2: Payment status = dp", bk4.get('payment_status') == 'dp',
                    f"Status: {bk4.get('payment_status')}, Paid: {bk4.get('paid_amount')}")
        
        # Pay remaining (600k)
        print("\n2️⃣ Paying remaining (600k)...")
        success, payment2 = runner.api_call('POST', 'payments', 200, data={
            "booking_id": booking_id4,
            "amount": 600000,
            "type": "cash"
        })
        runner.test("REG.PAY.3: Full payment", success)
        
        # Check payment_status = 'lunas'
        success, bk4_final = runner.api_call('GET', f'bookings/{booking_id4}')
        runner.test("REG.PAY.4: Payment status = lunas", bk4_final.get('payment_status') == 'lunas',
                    f"Status: {bk4_final.get('payment_status')}, Paid: {bk4_final.get('paid_amount')}")
        
        # Try overpayment (should be rejected)
        print("\n3️⃣ Trying overpayment (100k)...")
        success, payment3 = runner.api_call('POST', 'payments', 400, data={
            "booking_id": booking_id4,
            "amount": 100000,
            "type": "cash"
        })
        runner.test("REG.PAY.5: Overpayment rejected", success,
                    "Overpayment should return 400")

    # === REGRESSION: State machine ===
    print("\n" + "="*60)
    print("🧪 REGRESSION: State machine validations")
    print("="*60 + "\n")

    # RC-05: Payment to cancelled booking
    if booking_id:  # Use the cancelled booking from G1
        print("1️⃣ Trying payment to cancelled booking...")
        success, payment_fail = runner.api_call('POST', 'payments', 400, data={
            "booking_id": booking_id,
            "amount": 100000,
            "type": "cash"
        })
        runner.test("REG.STATE.1: Payment to cancelled booking rejected (RC-05)", success)

    # === REGRESSION: Core endpoints ===
    print("\n" + "="*60)
    print("🧪 REGRESSION: Core endpoints")
    print("="*60 + "\n")

    # Dashboard
    success, dashboard = runner.api_call('GET', 'dashboard')
    runner.test("REG.CORE.1: GET /dashboard", success and 'vehicles' in dashboard)

    # Lists
    success, vehicles_list = runner.api_call('GET', 'vehicles')
    runner.test("REG.CORE.2: GET /vehicles", success and isinstance(vehicles_list, list))

    success, drivers_list = runner.api_call('GET', 'drivers')
    runner.test("REG.CORE.3: GET /drivers", success and isinstance(drivers_list, list))

    success, customers_list = runner.api_call('GET', 'customers')
    runner.test("REG.CORE.4: GET /customers", success and isinstance(customers_list, list))

    success, bookings_list = runner.api_call('GET', 'bookings')
    runner.test("REG.CORE.5: GET /bookings", success and isinstance(bookings_list, list))

    # Automation stats
    success, auto_stats = runner.api_call('GET', 'automation/stats')
    runner.test("REG.CORE.6: GET /automation/stats", success and 'rules_total' in auto_stats)

    # === Test other roles ===
    print("\n" + "="*60)
    print("🧪 REGRESSION: Login other roles")
    print("="*60 + "\n")

    # Ops login
    if runner.login("ops@demo.local", "demo12345"):
        runner.test("REG.AUTH.1: Login as ops", True)
        runner.login("owner@demo.local", "demo12345")  # Switch back
    else:
        runner.test("REG.AUTH.1: Login as ops", False)

    # Driver login
    if runner.login("driver@demo.local", "demo12345"):
        runner.test("REG.AUTH.2: Login as driver", True)
        runner.login("owner@demo.local", "demo12345")  # Switch back
    else:
        runner.test("REG.AUTH.2: Login as driver", False)

    return runner.summary()


if __name__ == "__main__":
    sys.exit(main())

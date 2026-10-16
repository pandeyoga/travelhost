#!/usr/bin/env python3
"""
Test SSOT WhatsApp Payload by triggering complete driver flow
"""
import requests
import time
from datetime import datetime, timedelta

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com"

def login(email, password):
    response = requests.post(f"{BASE_URL}/api/auth/login", 
                           json={"email": email, "password": password}, timeout=10)
    if response.status_code == 200:
        return response.json().get("token")
    return None

def headers(token):
    return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

def main():
    print("🔍 Testing SSOT WhatsApp Payload")
    print("="*70)
    
    # Login
    owner_token = login("owner@demo.local", "demo12345")
    driver_token = login("driver@demo.local", "demo12345")
    
    if not owner_token or not driver_token:
        print("❌ Login failed")
        return 1
    
    print("✅ Logged in as owner and driver")
    
    # Get vehicles, customers, drivers
    vehicles_resp = requests.get(f"{BASE_URL}/api/vehicles", headers=headers(owner_token), timeout=10)
    customers_resp = requests.get(f"{BASE_URL}/api/customers", headers=headers(owner_token), timeout=10)
    drivers_resp = requests.get(f"{BASE_URL}/api/drivers", headers=headers(owner_token), timeout=10)
    
    if vehicles_resp.status_code != 200 or customers_resp.status_code != 200 or drivers_resp.status_code != 200:
        print("❌ Could not fetch data")
        return 1
    
    vehicles = vehicles_resp.json()
    customers = customers_resp.json()
    drivers = drivers_resp.json()
    
    driver_satu = next((d for d in drivers if d.get("name") == "Driver Satu"), None)
    
    if not vehicles or not customers or not driver_satu:
        print("❌ Missing data")
        return 1
    
    print(f"✅ Found vehicle, customer, and Driver Satu (ID: {driver_satu.get('id')})")
    
    # Create booking with driver
    booking_data = {
        "customer_id": customers[0].get("id"),
        "vehicle_id": vehicles[0].get("id"),
        "driver_id": driver_satu.get("id"),
        "start_datetime": (datetime.now() + timedelta(hours=1)).isoformat(),
        "end_datetime": (datetime.now() + timedelta(hours=3)).isoformat(),
        "origin": "Jakarta Pusat",
        "destination": "Bandung",
        "base_price": 2000000
    }
    
    booking_resp = requests.post(f"{BASE_URL}/api/bookings", json=booking_data, 
                                headers=headers(owner_token), timeout=10)
    
    if booking_resp.status_code != 200:
        print(f"❌ Could not create booking: {booking_resp.status_code}")
        return 1
    
    booking = booking_resp.json()
    booking_id = booking.get("id")
    print(f"✅ Created booking: {booking_id}")
    
    # Confirm booking
    confirm_resp = requests.post(f"{BASE_URL}/api/bookings/{booking_id}/confirm", 
                                headers=headers(owner_token), timeout=10)
    
    if confirm_resp.status_code not in [200, 400]:
        print(f"❌ Could not confirm booking: {confirm_resp.status_code}")
        return 1
    
    print(f"✅ Confirmed booking")
    
    # Driver checkin (triggers trip.started event)
    checkin_resp = requests.post(f"{BASE_URL}/api/driver/checkin", 
                                json={"booking_id": booking_id, "odometer_start": 10000}, 
                                headers=headers(driver_token), timeout=10)
    
    if checkin_resp.status_code != 200:
        print(f"❌ Could not checkin: {checkin_resp.status_code}")
        return 1
    
    trip = checkin_resp.json()
    trip_id = trip.get("id")
    print(f"✅ Driver checked in, trip created: {trip_id}")
    
    # Wait a bit for event to be processed
    time.sleep(2)
    
    # Driver arrived (triggers trip.arrived event)
    arrived_resp = requests.post(f"{BASE_URL}/api/driver/tasks/{trip_id}/arrived", 
                                headers=headers(driver_token), timeout=10)
    
    if arrived_resp.status_code == 200:
        print(f"✅ Driver marked as arrived")
    else:
        print(f"⚠️  Could not mark arrived: {arrived_resp.status_code}")
    
    # Wait a bit
    time.sleep(2)
    
    # Driver checkout (triggers trip.completed event)
    checkout_resp = requests.post(f"{BASE_URL}/api/driver/checkout", 
                                 json={"trip_id": trip_id, "odometer_end": 10150}, 
                                 headers=headers(driver_token), timeout=10)
    
    if checkout_resp.status_code != 200:
        print(f"❌ Could not checkout: {checkout_resp.status_code}")
        return 1
    
    print(f"✅ Driver checked out")
    
    # Wait for events to be processed
    time.sleep(3)
    
    # Get automation events
    events_resp = requests.get(f"{BASE_URL}/api/automation/events?limit=200", 
                              headers=headers(owner_token), timeout=10)
    
    if events_resp.status_code != 200:
        print(f"❌ Could not fetch events: {events_resp.status_code}")
        return 1
    
    events = events_resp.json()
    
    # Find trip events for this booking
    trip_started = next((e for e in events if e.get("event_type") == "trip.started" and 
                        e.get("payload", {}).get("booking_id") == booking_id), None)
    trip_arrived = next((e for e in events if e.get("event_type") == "trip.arrived" and 
                        e.get("payload", {}).get("booking_id") == booking_id), None)
    trip_completed = next((e for e in events if e.get("event_type") == "trip.completed" and 
                          e.get("payload", {}).get("booking_id") == booking_id), None)
    
    print("\n" + "="*70)
    print("SSOT WhatsApp Payload Verification")
    print("="*70)
    
    required_fields = ["company", "destination", "driver_phone", "pickup", "vehicle_name", "customer_name"]
    
    all_passed = True
    
    for event_name, event in [("trip.started", trip_started), ("trip.arrived", trip_arrived), 
                              ("trip.completed", trip_completed)]:
        print(f"\n🔍 Checking {event_name} event:")
        
        if not event:
            print(f"  ❌ Event not found")
            all_passed = False
            continue
        
        payload = event.get("payload", {})
        
        for field in required_fields:
            value = payload.get(field)
            if value and value not in [None, "", "None"]:
                print(f"  ✅ {field}: {value}")
            else:
                print(f"  ❌ {field}: MISSING or EMPTY (value: {value})")
                all_passed = False
    
    # Compare with dispatch event (trip.enroute) if exists
    dispatch_event = next((e for e in events if e.get("event_type") == "trip.enroute"), None)
    
    if dispatch_event and trip_started:
        print(f"\n🔍 Comparing with dispatch event (trip.enroute):")
        dispatch_payload = dispatch_event.get("payload", {})
        trip_payload = trip_started.get("payload", {})
        
        common_fields = set(dispatch_payload.keys()).intersection(set(trip_payload.keys()))
        print(f"  ✅ Common fields: {len(common_fields)}")
        print(f"  📋 Dispatch fields: {set(dispatch_payload.keys())}")
        print(f"  📋 Trip fields: {set(trip_payload.keys())}")
        
        if len(common_fields) >= 5:
            print(f"  ✅ Payload structure is consistent (≥5 common fields)")
        else:
            print(f"  ❌ Payload structure inconsistent (<5 common fields)")
            all_passed = False
    
    print("\n" + "="*70)
    if all_passed:
        print("✅ SSOT WhatsApp Payload: ALL CHECKS PASSED")
        return 0
    else:
        print("❌ SSOT WhatsApp Payload: SOME CHECKS FAILED")
        return 1

if __name__ == "__main__":
    exit(main())

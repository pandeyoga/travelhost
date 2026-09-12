"""
Specific test for RC-02: Payment Status Honesty
"""
import requests
import sys
from datetime import datetime, timedelta

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com/api"

def login(email, password):
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=10)
    if resp.status_code == 200:
        return resp.json().get("token")
    return None

def main():
    print("=== RC-02: PAYMENT STATUS HONESTY TEST ===\n")
    
    token = login("owner@demo.local", "demo12345")
    if not token:
        print("❌ Login failed")
        return 1
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get available vehicles
    resp = requests.get(f"{BASE_URL}/vehicles", headers=headers, timeout=10)
    vehicles = resp.json()
    available_vehicles = [v for v in vehicles if v.get("status") == "available"]
    
    if len(available_vehicles) < 1:
        print("❌ No available vehicles")
        return 1
    
    vehicle_id = available_vehicles[0]["id"]
    print(f"✅ Using vehicle: {available_vehicles[0].get('name')}")
    
    # Get customer
    resp = requests.get(f"{BASE_URL}/customers", headers=headers, timeout=10)
    customers = resp.json()
    if not customers:
        print("❌ No customers")
        return 1
    customer_id = customers[0]["id"]
    
    # Create booking with far future date to avoid conflicts
    start_date = datetime(2028, 9, 15, 10, 0)
    end_date = start_date + timedelta(days=2)
    
    booking_data = {
        "customer_id": customer_id,
        "vehicle_id": vehicle_id,
        "origin": "Jakarta",
        "destination": "Surabaya",
        "start_datetime": start_date.isoformat() + "+00:00",
        "end_datetime": end_date.isoformat() + "+00:00",
        "base_price": 2000000,
        "notes": "RC-02 Test"
    }
    
    resp = requests.post(f"{BASE_URL}/bookings", headers=headers, json=booking_data, timeout=10)
    if resp.status_code != 200:
        print(f"❌ Failed to create booking: {resp.status_code} - {resp.text}")
        return 1
    
    booking = resp.json()
    booking_id = booking["id"]
    print(f"✅ Created booking {booking.get('code')} with total 2,000,000 (NO payment)")
    
    # Complete booking WITHOUT payment
    resp = requests.post(f"{BASE_URL}/bookings/{booking_id}/complete", headers=headers, json={}, timeout=10)
    if resp.status_code != 200:
        print(f"❌ Failed to complete booking: {resp.status_code} - {resp.text}")
        return 1
    
    print("✅ Completed booking without payment")
    
    # Check booking status and payment_status
    resp = requests.get(f"{BASE_URL}/bookings/{booking_id}", headers=headers, timeout=10)
    if resp.status_code != 200:
        print(f"❌ Failed to get booking: {resp.status_code}")
        return 1
    
    booking_data = resp.json()
    status = booking_data.get("status")
    payment_status = booking_data.get("payment_status")
    
    print(f"\nBooking status: {status}")
    print(f"Payment status: {payment_status}")
    
    # Verify
    tests_passed = 0
    tests_total = 3
    
    if status == "completed":
        print("✅ TEST 1: Booking status is 'completed'")
        tests_passed += 1
    else:
        print(f"❌ TEST 1: Expected status='completed', got '{status}'")
    
    if payment_status == "belum_bayar":
        print("✅ TEST 2: Payment status is 'belum_bayar' (NOT 'selesai'/'lunas')")
        tests_passed += 1
    else:
        print(f"❌ TEST 2: Expected payment_status='belum_bayar', got '{payment_status}'")
    
    # Check if appears in AR
    resp = requests.get(f"{BASE_URL}/finance/ar", headers=headers, timeout=10)
    if resp.status_code == 200:
        ar_data = resp.json()
        items = ar_data.get("items", [])
        found_in_ar = any(item.get("booking_id") == booking_id for item in items)
        
        if found_in_ar:
            print("✅ TEST 3: Unpaid completed booking appears in AR (accounts receivable)")
            tests_passed += 1
        else:
            print(f"❌ TEST 3: Booking not found in AR")
    else:
        print(f"❌ TEST 3: Failed to get AR: {resp.status_code}")
    
    print(f"\n{'='*60}")
    print(f"RC-02 TESTS: {tests_passed}/{tests_total} passed")
    print(f"{'='*60}")
    
    return 0 if tests_passed == tests_total else 1

if __name__ == "__main__":
    sys.exit(main())

"""services/wa_payload.py — SSOT payload event booking/trip untuk WA/CRM.

Sebelumnya payload dibangun terpisah:
- routers/dispatch.py `_wa_payload()` → LENGKAP (customer, driver+phone, company, destination, dsb).
- routers/driver.py `_emit_trip()` → MINIM (tanpa company/destination/driver_phone).
Akibatnya event `trip.started`/`trip.completed` (dipancarkan dari driver) menghasilkan variabel
WA yang kosong (mis. {company}) — DRIFT. Modul ini menyatukan pembangun payload agar SEMUA
event trip.* memakai variabel yang sama & lengkap (SSOT).
"""


async def customer_phone(db, booking):
    if not booking:
        return None
    c = await db.customers.find_one({"id": booking.get("customer_id")}, {"_id": 0, "phone": 1}) or {}
    return c.get("phone")


async def build_wa_payload(db, booking, trip=None):
    """Bangun payload variabel WA dari booking (+trip opsional). Dipakai dispatch & driver."""
    if not booking:
        return {}
    drv = await db.drivers.find_one(
        {"id": booking.get("driver_id")}, {"_id": 0, "name": 1, "phone": 1}) or {}
    cfg = await db.settings.find_one({"key": "company_info"}, {"_id": 0, "value": 1}) or {}
    company = (cfg.get("value") or {}).get("name") or "Tim Travel"
    return {
        "booking_id": booking.get("id"), "code": booking.get("code"),
        "customer_name": booking.get("customer_name"),
        "phone": await customer_phone(db, booking),
        "destination": booking.get("destination"), "origin": booking.get("origin"),
        "pickup": booking.get("origin"),
        "start_datetime": booking.get("start_datetime"),
        "vehicle_name": booking.get("vehicle_name"),
        "driver_name": drv.get("name") or booking.get("driver_name"),
        "driver_phone": drv.get("phone"),
        "company": company,
    }

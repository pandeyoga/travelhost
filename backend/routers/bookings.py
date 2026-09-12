"""routers/bookings.py — booking: list/calendar/detail + availability + create + edit + transisi.

Anti double-booking (INV-4) via services.availability.find_conflicts.
INV-1 total=base+Σaddons; INV-3 payment_status derivasi; INV-10 snapshot nama.
Urutan rute: literal (/calendar, /availability) sebelum /{booking_id}.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from contextlib import AsyncExitStack
from io import BytesIO
from typing import Optional

from core_utils import money, new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_role, require_section
from schemas import BookingApprove, BookingCreate, BookingReschedule, BookingUpdate, CancelBooking, GroupBookingCreate
from services.availability import find_conflicts, find_driver_conflicts, find_maintenance_conflicts, vehicle_lock, driver_lock
from services.rbac_scope import can_view_booking, scope_bookings_query
from services.audit import record
from services.counters import next_booking_code
from services.events import emit
from services.geo import parse_iso
from services.pricing import compute_quote, get_dp_percent, get_pricing_rules, span_days
from services.refs import destination_or_400, origin_or_400

router = APIRouter(prefix="/api", tags=["bookings"])
# RBAC: mutasi booking hanya untuk manajemen (owner/ops_admin). Driver read-only.
MANAGER = require_role("owner", "ops_admin")
# RBAC-SECT-01: permukaan BACA modul ini WAJIB lewat pintu section, bukan sekadar "sudah login".
# Sebelum perbaikan ini `marketing_admin` mendapat HTTP 200 di seluruh GET di bawah (nama
# pelanggan, nominal booking, telepon sopir, posisi GPS) padahal menunya memang tidak
# pernah ditampilkan untuk peran itu — SSOT `permissions_config.SECTION_ACCESS` + FE
# `ROLE_MENU_ALLOWLIST` sama-sama mengecualikannya. Kelas bug BUG-0107 terulang: peran BARU
# (marketing_admin, lahir di FASE F) tidak pernah diuji ulang terhadap endpoint BACA LAMA.
BOOKINGS = require_section("bookings")
# RBAC-CAL-01: endpoint kalender keberangkatan (grid + ekspor) = section "calendar" (owner/ops_admin).
CALENDAR = require_section("calendar")


async def _emit_booking_confirmed(db, booking, source="bookings"):
    """Pancarkan booking.confirmed (idempotent per booking) dgn telepon pelanggan utk WA."""
    cust = await db.customers.find_one({"id": booking.get("customer_id")}, {"_id": 0, "phone": 1}) or {}
    # SATU SUMBER DP (services.pricing.get_dp_percent) — dulu router ini membaca
    # `pricing_defaults.dp_percent` sendiri sehingga DP di WhatsApp bisa berbeda dari DP
    # yang ditampilkan situs (yang memakai `pricing_rules`). Lihat INV-PRICE-01.
    dp = await get_dp_percent(db)
    await emit(db, "booking.confirmed", {
        "booking_id": booking["id"], "code": booking.get("code"),
        "customer_name": booking.get("customer_name"), "phone": cust.get("phone"),
        "total_amount": float(booking.get("total_amount", 0) or 0), "dp_percent": dp,
        "vehicle_name": booking.get("vehicle_name"),
        "start_datetime": (booking.get("start_datetime") or "")[:16].replace("T", " "),
    }, source=source, ref_type="booking", ref_id=booking["id"],
        dedupe_key=f"booking.confirmed:{booking['id']}")


def _slim_conflict(c):
    return {"id": c.get("id"), "code": c.get("code"), "status": c.get("status"),
            "start_datetime": c.get("start_datetime"), "end_datetime": c.get("end_datetime")}


def _slim_maint(m):
    return {"id": m.get("id"), "type": m.get("type"), "title": m.get("title"),
            "status": m.get("status"), "start_date": m.get("start_date"), "end_date": m.get("end_date")}


async def _next_code(db):
    """Kode booking atomik (A2) — anti-balapan via counters ($inc)."""
    return await next_booking_code(db)


@router.get("/bookings")
async def list_bookings(status: str = Query(default=None), vehicle_id: str = Query(default=None),
                        customer_id: str = Query(default=None), limit: int = Query(default=500, le=1000),
                        skip: int = Query(default=0, ge=0), user=Depends(BOOKINGS)):
    query = {}
    if status:
        query["status"] = status
    if vehicle_id:
        query["vehicle_id"] = vehicle_id
    if customer_id:
        query["customer_id"] = customer_id
    # INV-RBAC-05: driver hanya melihat trip miliknya (SSOT docs/05_NAVIGATION_MAP.md §3).
    query = await scope_bookings_query(get_db(), user, query)
    docs = await get_db().bookings.find(query, {"_id": 0}).sort("start_datetime", -1).skip(skip).to_list(limit)
    return safe_doc(docs)


@router.get("/bookings/calendar")
async def bookings_calendar(month: str = Query(default=None), user=Depends(CALENDAR)):
    query = {}
    if month:
        query["start_datetime"] = {"$regex": f"^{month}"}
    docs = await get_db().bookings.find(
        query,
        {"_id": 0, "id": 1, "code": 1, "customer_name": 1, "vehicle_id": 1, "vehicle_name": 1,
         "driver_id": 1, "driver_name": 1, "start_datetime": 1, "end_datetime": 1,
         "payment_status": 1, "status": 1, "hold_expires_at": 1, "source": 1,
         "requested_vehicle_type": 1, "pax": 1},
    ).sort("start_datetime", 1).to_list(1000)
    return safe_doc(docs)


@router.get("/bookings/calendar/export")
async def bookings_calendar_export(month: str = Query(default=None), start: str = Query(default=None),
                                   end: str = Query(default=None), format: str = Query(default="excel"),
                                   group: str = Query(default=None), user=Depends(CALENDAR)):
    """Ekspor jadwal keberangkatan ke PDF / Excel (siap cetak & dibagikan).

    Cakupan: `month=YYYY-MM` ATAU rentang `start=YYYY-MM-DD&end=YYYY-MM-DD`.
    `group=vehicle` -> dikelompokkan per armada (bagian/sheet terpisah).
    """
    from services.calendar_export import calendar_pdf, calendar_xlsx, period_label
    query = {}
    if start and end:
        query["start_datetime"] = {"$gte": start, "$lte": f"{end}T23:59:59.999999+00:00"}
    elif month:
        query["start_datetime"] = {"$regex": f"^{month}"}
    rows = await get_db().bookings.find(query, {"_id": 0}).sort("start_datetime", 1).to_list(3000)
    rows = safe_doc(rows)
    label = period_label(month=month, start=start, end=end)
    grouped = (group or "").lower() == "vehicle"
    tag = (start or month or "semua")
    if (format or "").lower() == "pdf":
        blob = calendar_pdf(label, rows, grouped=grouped)
        return StreamingResponse(
            BytesIO(blob), media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="kalender-keberangkatan-{tag}.pdf"'},
        )
    blob = calendar_xlsx(label, rows, grouped=grouped)
    return StreamingResponse(
        BytesIO(blob),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="kalender-keberangkatan-{tag}.xlsx"'},
    )


@router.get("/bookings/availability")
async def check_availability(vehicle_id: str = Query(default=None), start: str = Query(default=None),
                             end: str = Query(default=None), exclude_id: str = Query(default=None),
                             user=Depends(BOOKINGS)):
    if not vehicle_id or not start or not end:
        return {"available": None, "conflicts": [], "maintenance": [], "reason": "Lengkapi vehicle_id, start, end"}
    conflicts = await find_conflicts(get_db(), vehicle_id, start, end, exclude_id)
    maint = await find_maintenance_conflicts(get_db(), vehicle_id, start, end)
    return {"available": len(conflicts) == 0 and len(maint) == 0,
            "conflicts": [_slim_conflict(c) for c in conflicts],
            "maintenance": [_slim_maint(m) for m in maint]}


@router.post("/bookings")
async def create_booking(body: BookingCreate, user=Depends(MANAGER)):
    db = get_db()
    customer = await db.customers.find_one({"id": body.customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=400, detail="Customer tidak ditemukan")
    vehicle = await db.vehicles.find_one({"id": body.vehicle_id}, {"_id": 0})
    if not vehicle:
        raise HTTPException(status_code=400, detail="Armada tidak ditemukan")
    driver = None
    if body.driver_id:
        driver = await db.drivers.find_one({"id": body.driver_id}, {"_id": 0})
        if not driver:
            raise HTTPException(status_code=400, detail="Driver tidak ditemukan")
    if not body.start_datetime or not body.end_datetime:
        raise HTTPException(status_code=400, detail="Tanggal mulai & selesai wajib diisi")
    # INV-REF-02 (RC-E): destinasi & titik jemput WAJIB dari master — bukan teks bebas.
    destination = await destination_or_400(db, body.destination)
    origin = await origin_or_400(db, body.origin)
    start_dt = parse_iso(body.start_datetime)
    end_dt = parse_iso(body.end_datetime)
    if not start_dt or not end_dt:
        raise HTTPException(status_code=400, detail="Format tanggal tidak valid")
    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="Tanggal selesai harus setelah tanggal mulai")
    # Normalkan ke ISO UTC kanonik (+00:00) agar konsisten dgn seed & gate INV-4.
    start_iso = start_dt.isoformat()
    end_iso = end_dt.isoformat()
    conflicts = await find_conflicts(db, body.vehicle_id, start_iso, end_iso)
    if conflicts:
        codes = ", ".join(c.get("code", c.get("id")) for c in conflicts)
        raise HTTPException(status_code=400, detail=f"Armada bentrok dengan booking aktif: {codes}")
    maint = await find_maintenance_conflicts(db, body.vehicle_id, start_iso, end_iso)
    if maint:
        titles = ", ".join((m.get("title") or m.get("type") or "perawatan") for m in maint)
        raise HTTPException(status_code=400, detail=f"Armada dalam masa perawatan: {titles}")
    # RC-07: bila driver ikut di-assign saat pembuatan, tolak bila bentrok jadwal driver.
    if body.driver_id:
        dconf = await find_driver_conflicts(db, body.driver_id, start_iso, end_iso)
        if dconf:
            raise HTTPException(status_code=400,
                                detail=f"Driver bentrok dengan booking aktif: {dconf[0].get('code')}")
    add_ons = [a.model_dump() if hasattr(a, "model_dump") else dict(a) for a in (body.add_ons or [])]
    base = money(body.base_price)
    # B1 Pricing Engine: bila harga dasar tak diisi (≤0), hitung otomatis dari pricing_rules
    # (tarif per tipe armada × durasi + surcharge akhir pekan/hari libur). Admin tetap bisa
    # override dengan mengisi base_price manual.
    if base <= 0:
        rules = await get_pricing_rules(db)
        op = await db.settings.find_one({"key": "operational"}, {"_id": 0})
        holidays = (op.get("value") or {}).get("holidays", []) if op else []
        quote = compute_quote(rules, vehicle_type=vehicle.get("type"),
                              days=span_days(start_iso, end_iso),
                              when=start_iso, holidays=holidays, include_travel=True,
                              day_rate=vehicle.get("day_rate"))
        base = money(quote["total"])
    total = money(base + sum(float(a.get("amount", 0) or 0) for a in add_ons))
    # E18: DP-gate — bila require_dp, buat sebagai 'hold' (reservasi menunggu DP) + auto-expire.
    from datetime import datetime as _dt_e18, timedelta as _td_e18, timezone as _tz_e18
    status = "confirmed"
    hold_fields = {}
    if body.require_dp:
        from services import booking_flow as _bf
        _flow = await _bf.get_flow(db)
        dp_percent = float(await get_dp_percent(db))
        hold_hours = int(body.hold_hours or _flow.get("approval_hold_hours") or 24)
        status = "hold"
        hold_fields = {
            "hold_expires_at": (_dt_e18.now(_tz_e18.utc) + _td_e18(hours=hold_hours)).isoformat(),
            "dp_percent": dp_percent, "dp_amount": money(total * dp_percent / 100.0),
            "hold_hours": hold_hours,
        }
    doc = {
        "id": new_id("bk"), "code": await _next_code(db),
        "customer_id": body.customer_id, "vehicle_id": body.vehicle_id, "driver_id": body.driver_id,
        "origin": origin, "destination": destination,
        "start_datetime": start_iso, "end_datetime": end_iso,
        "base_price": base, "add_ons": add_ons, "total_amount": total, "paid_amount": 0,
        "payment_status": "belum_bayar", "status": status,
        "customer_name": customer.get("name"), "vehicle_name": vehicle.get("name"),
        "driver_name": driver.get("name") if driver else None,
        "notes": body.notes or "", "created_at": now_iso(), **hold_fields,
    }
    # RC-16 (anti-TOCTOU): cek-final + insert HARUS serial per armada. Tanpa mutex, N request
    # paralel utk armada+waktu sama bisa sama-sama lolos find_conflicts lalu sama-sama insert
    # (terbukti empiris: 13 dari 16 request paralel membuat double-booking). MongoDB standalone
    # (tanpa transaksi) → pakai mutex per-armada (booking_locks) supaya bagian kritis serial.
    async with vehicle_lock(db, body.vehicle_id):
        conflicts = await find_conflicts(db, body.vehicle_id, start_iso, end_iso)
        if conflicts:
            codes = ", ".join(c.get("code", c.get("id")) for c in conflicts)
            raise HTTPException(status_code=400, detail=f"Armada bentrok dengan booking aktif: {codes}")
        maint = await find_maintenance_conflicts(db, body.vehicle_id, start_iso, end_iso)
        if maint:
            titles = ", ".join((m.get("title") or m.get("type") or "perawatan") for m in maint)
            raise HTTPException(status_code=400, detail=f"Armada dalam masa perawatan: {titles}")
        await db.bookings.insert_one(doc)
    # Hold belum 'confirmed' → jangan emit booking.confirmed (WA konfirmasi menyusul saat DP masuk).
    if status == "confirmed":
        await _emit_booking_confirmed(db, doc)
    return safe_doc(doc)


@router.post("/bookings/group")
async def create_group_booking(body: GroupBookingCreate, user=Depends(MANAGER)):
    """E20: buat booking ROMBONGAN — banyak unit serentak dan/atau beberapa leg/rute.
    Tiap unit divalidasi ketersediaan (INV-4/INV-21/RC-07) + anti-bentrok ANTAR-unit dalam grup,
    lalu jadi 1 booking anak (group_id sama). Semua-atau-tidak: validasi dulu, insert kemudian."""
    db = get_db()
    if not body.units:
        raise HTTPException(status_code=400, detail="Minimal 1 unit/leg untuk rombongan")
    customer = await db.customers.find_one({"id": body.customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=400, detail="Customer tidak ditemukan")
    prepared = []
    for idx, u in enumerate(body.units):
        vehicle = await db.vehicles.find_one({"id": u.vehicle_id}, {"_id": 0})
        if not vehicle:
            raise HTTPException(status_code=400, detail=f"Unit #{idx + 1}: armada tidak ditemukan")
        driver = None
        if u.driver_id:
            driver = await db.drivers.find_one({"id": u.driver_id}, {"_id": 0})
            if not driver:
                raise HTTPException(status_code=400, detail=f"Unit #{idx + 1}: driver tidak ditemukan")
        s_dt, e_dt = parse_iso(u.start_datetime), parse_iso(u.end_datetime)
        if not s_dt or not e_dt:
            raise HTTPException(status_code=400, detail=f"Unit #{idx + 1}: format tanggal tidak valid")
        if e_dt <= s_dt:
            raise HTTPException(status_code=400, detail=f"Unit #{idx + 1}: tanggal selesai harus setelah mulai")
        s_iso, e_iso = s_dt.isoformat(), e_dt.isoformat()
        u_destination = await destination_or_400(db, u.destination,
                                                 field_label=f"Unit #{idx + 1}: destinasi")
        u_origin = await origin_or_400(db, u.origin, field_label=f"Unit #{idx + 1}: titik jemput")
        conflicts = await find_conflicts(db, u.vehicle_id, s_iso, e_iso)
        if conflicts:
            codes = ", ".join(c.get("code", c.get("id")) for c in conflicts)
            raise HTTPException(status_code=400, detail=f"Unit #{idx + 1} ({vehicle.get('name')}): bentrok booking aktif {codes}")
        maint = await find_maintenance_conflicts(db, u.vehicle_id, s_iso, e_iso)
        if maint:
            titles = ", ".join((m.get("title") or m.get("type") or "perawatan") for m in maint)
            raise HTTPException(status_code=400, detail=f"Unit #{idx + 1} ({vehicle.get('name')}): masa perawatan {titles}")
        if u.driver_id:
            dconf = await find_driver_conflicts(db, u.driver_id, s_iso, e_iso)
            if dconf:
                raise HTTPException(status_code=400, detail=f"Unit #{idx + 1}: driver bentrok {dconf[0].get('code')}")
        add_ons = [a.model_dump() if hasattr(a, "model_dump") else dict(a) for a in (u.add_ons or [])]
        base = money(u.base_price)
        if base <= 0:
            rules = await get_pricing_rules(db)
            op = await db.settings.find_one({"key": "operational"}, {"_id": 0})
            holidays = (op.get("value") or {}).get("holidays", []) if op else []
            quote = compute_quote(rules, vehicle_type=vehicle.get("type"),
                                  days=span_days(s_iso, e_iso),
                                  when=s_iso, holidays=holidays, include_travel=True,
                                  day_rate=vehicle.get("day_rate"))
            base = money(quote["total"])
        total = money(base + sum(float(a.get("amount", 0) or 0) for a in add_ons))
        prepared.append({"u": u, "vehicle": vehicle, "driver": driver, "s_iso": s_iso, "e_iso": e_iso,
                         "s_dt": s_dt, "e_dt": e_dt, "add_ons": add_ons, "base": base, "total": total,
                         "destination": u_destination, "origin": u_origin})
    # Anti-bentrok ANTAR-unit dalam grup (armada sama + waktu overlap) — belum ter-insert ke DB.
    for i in range(len(prepared)):
        for j in range(i + 1, len(prepared)):
            a, b = prepared[i], prepared[j]
            if a["u"].vehicle_id == b["u"].vehicle_id and a["s_dt"] < b["e_dt"] and b["s_dt"] < a["e_dt"]:
                raise HTTPException(status_code=400, detail=f"Unit #{i + 1} & #{j + 1} memakai armada sama dgn waktu tumpang tindih")
    from datetime import datetime as _dt_g, timedelta as _td_g, timezone as _tz_g
    group_id = new_id("grp")
    n = len(prepared)
    created, grand_total = [], 0
    # RC-16 (anti-TOCTOU): kunci SEMUA armada berbeda dalam grup (urut → hindari deadlock),
    # re-cek ketersediaan otoritatif DI DALAM kunci, lalu insert semua unit (all-or-nothing).
    async with AsyncExitStack() as _locks:
        for _vid in sorted({p["u"].vehicle_id for p in prepared}):
            await _locks.enter_async_context(vehicle_lock(db, _vid))
        for idx, p in enumerate(prepared):
            conf = await find_conflicts(db, p["u"].vehicle_id, p["s_iso"], p["e_iso"])
            if conf:
                codes = ", ".join(c.get("code", c.get("id")) for c in conf)
                raise HTTPException(status_code=400,
                                    detail=f"Unit #{idx + 1} ({p['vehicle'].get('name')}): bentrok booking aktif {codes}")
        for idx, p in enumerate(prepared):
            status, hold_fields = "confirmed", {}
            if body.require_dp:
                from services import booking_flow as _bfg
                _flowg = await _bfg.get_flow(db)
                dp_percent = float(await get_dp_percent(db))
                hold_hours = int(_flowg.get("approval_hold_hours") or 24)
                status = "hold"
                hold_fields = {"hold_expires_at": (_dt_g.now(_tz_g.utc) + _td_g(hours=hold_hours)).isoformat(),
                               "dp_percent": dp_percent, "dp_amount": money(p["total"] * dp_percent / 100.0),
                               "hold_hours": hold_hours}
            doc = {
                "id": new_id("bk"), "code": await _next_code(db),
                "customer_id": body.customer_id, "vehicle_id": p["u"].vehicle_id, "driver_id": p["u"].driver_id,
                "origin": p["origin"], "destination": p["destination"],
                "start_datetime": p["s_iso"], "end_datetime": p["e_iso"],
                "base_price": p["base"], "add_ons": p["add_ons"], "total_amount": p["total"], "paid_amount": 0,
                "payment_status": "belum_bayar", "status": status,
                "customer_name": customer.get("name"), "vehicle_name": p["vehicle"].get("name"),
                "driver_name": p["driver"].get("name") if p["driver"] else None,
                "notes": body.note or "", "created_at": now_iso(),
                "group_id": group_id, "group_size": n, "group_index": idx + 1, **hold_fields,
            }
            await db.bookings.insert_one(doc)
            created.append(safe_doc(doc))
            grand_total += p["total"]
    await record(db, actor=user, action="create", entity_type="booking", entity_id=group_id,
                 summary=f"Buat rombongan {n} unit ({customer.get('name')}) — total Rp {grand_total:,}".replace(",", "."))
    # Satu WA konfirmasi grup (lead child) bila bukan mode DP (hindari N pesan).
    if not body.require_dp and created:
        lead = created[0]
        cust = await db.customers.find_one({"id": body.customer_id}, {"_id": 0, "phone": 1}) or {}
        dp = await get_dp_percent(db)
        await emit(db, "booking.confirmed", {
            "booking_id": lead["id"], "code": lead["code"], "customer_name": customer.get("name"),
            "phone": cust.get("phone"), "total_amount": float(grand_total), "dp_percent": dp,
            "vehicle_name": f"{n} unit (rombongan)",
            "start_datetime": (lead.get("start_datetime") or "")[:16].replace("T", " "),
        }, source="bookings", ref_type="booking", ref_id=lead["id"], dedupe_key=f"booking.confirmed:group:{group_id}")
    return {"group_id": group_id, "count": n, "grand_total": grand_total,
            "require_dp": bool(body.require_dp), "bookings": created}


@router.get("/bookings/destination-options")
async def booking_destination_options(user=Depends(BOOKINGS)):
    """INV-REF-02: pilihan destinasi utk form booking ERP — dari master `destinations`."""
    rows = await get_db().destinations.find(
        {"deleted": {"$ne": True}, "ops_active": {"$ne": False}},
        {"_id": 0, "name": 1, "slug": 1}).sort("name", 1).to_list(500)
    return [{"value": r.get("name"), "label": r.get("name"), "slug": r.get("slug")}
            for r in rows if r.get("name")]


@router.get("/bookings/{booking_id}")
async def get_booking(booking_id: str, user=Depends(BOOKINGS)):
    db = get_db()
    doc = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    # INV-RBAC-05: driver tak boleh membuka detail booking milik driver lain.
    if not await can_view_booking(db, user, doc):
        raise HTTPException(status_code=403, detail="Akses ditolak: booking ini bukan trip Anda")
    payments = await db.payments.find({"booking_id": booking_id}, {"_id": 0}).sort("paid_at", 1).to_list(500)
    out = safe_doc(doc)
    out["payments"] = safe_doc(payments)
    return out


@router.patch("/bookings/{booking_id}")
async def update_booking(booking_id: str, body: BookingUpdate, user=Depends(MANAGER)):
    db = get_db()
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    updates = {}
    if body.notes is not None:
        updates["notes"] = body.notes
    # INV-REF-02: origin/destinasi hanya divalidasi bila DIUBAH — booking lama (nilai warisan
    # pra-master) tetap bisa diedit field lain tanpa dipaksa ganti.
    if body.destination is not None and body.destination != booking.get("destination"):
        updates["destination"] = await destination_or_400(db, body.destination)
    if body.origin is not None and body.origin != booking.get("origin"):
        updates["origin"] = await origin_or_400(db, body.origin)
    if body.driver_id is not None:
        if body.driver_id:
            driver = await db.drivers.find_one({"id": body.driver_id}, {"_id": 0})
            if not driver:
                raise HTTPException(status_code=400, detail="Driver tidak ditemukan")
            # RC-07 + RC-16 (dimensi driver): cegah 1 sopir di-assign ke 2 booking aktif yang
            # waktunya tumpang-tindih. Celah lama: PATCH ini MELEWATI validasi bentrok driver
            # yang dijaga ketat di create/approve/reschedule/dispatch-assign. Selain itu cek-lalu-tulis
            # kini di-serialkan per-sopir (driver_lock) agar atomik (anti-TOCTOU).
            if booking.get("status") not in ("cancelled", "completed") and body.driver_id != booking.get("driver_id"):
                async with driver_lock(db, body.driver_id):
                    dconf = await find_driver_conflicts(
                        db, body.driver_id, booking.get("start_datetime"),
                        booking.get("end_datetime"), exclude_booking_id=booking_id)
                    if dconf:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Driver bentrok dengan booking aktif: {dconf[0].get('code')}")
                    updates["driver_id"] = body.driver_id
                    updates["driver_name"] = driver.get("name")
                    await db.bookings.update_one({"id": booking_id}, {"$set": updates})
                doc = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
                return safe_doc(doc)
            updates["driver_id"] = body.driver_id
            updates["driver_name"] = driver.get("name")
        else:
            updates["driver_id"] = None
            updates["driver_name"] = None
    if updates:
        await db.bookings.update_one({"id": booking_id}, {"$set": updates})
    doc = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    return safe_doc(doc)


async def _set_status(booking_id, new_status, extra=None):
    db = get_db()
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    updates = {"status": new_status}
    if extra:
        updates.update(extra)
    await db.bookings.update_one({"id": booking_id}, {"$set": updates})
    doc = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    return safe_doc(doc)


@router.post("/bookings/{booking_id}/confirm")
async def confirm_booking(booking_id: str, user=Depends(MANAGER)):
    db = get_db()
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    # RC-16 (anti-TOCTOU): cek-bentrok + set-status harus serial per armada — dua booking
    # BERBEDA utk armada sama bisa dikonfirmasi paralel (status pending tak saling memblok).
    async with vehicle_lock(db, booking.get("vehicle_id")):
        conflicts = await find_conflicts(db, booking.get("vehicle_id"), booking.get("start_datetime"),
                                         booking.get("end_datetime"), exclude_id=booking_id)
        if conflicts:
            codes = ", ".join(c.get("code", c.get("id")) for c in conflicts)
            raise HTTPException(status_code=400, detail=f"Tidak bisa konfirmasi — bentrok: {codes}")
        # Konsistensi dgn create/approve/reschedule: re-cek perawatan (INV-21) & driver (RC-07) juga.
        maint = await find_maintenance_conflicts(db, booking.get("vehicle_id"), booking.get("start_datetime"),
                                                 booking.get("end_datetime"))
        if maint:
            titles = ", ".join((m.get("title") or m.get("type") or "perawatan") for m in maint)
            raise HTTPException(status_code=400, detail=f"Tidak bisa konfirmasi — armada dalam perawatan: {titles}")
        if booking.get("driver_id"):
            dconf = await find_driver_conflicts(db, booking["driver_id"], booking.get("start_datetime"),
                                                booking.get("end_datetime"), exclude_booking_id=booking_id)
            if dconf:
                raise HTTPException(status_code=400,
                                    detail=f"Tidak bisa konfirmasi — driver bentrok: {dconf[0].get('code')}")
        res = await _set_status(booking_id, "confirmed")
    await record(db, actor=user, action="confirm", entity_type="booking", entity_id=booking_id,
                 summary=f"Konfirmasi booking {res.get('code')}")
    await _emit_booking_confirmed(db, res)
    return res


async def _release_booking_resources(db, booking):
    """RC-04 — delegasi ke SSOT services.trips.release_booking_resources (pindah demi batas ukuran file)."""
    from services.trips import release_booking_resources
    await release_booking_resources(db, booking)


@router.post("/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: str, body: Optional[CancelBooking] = None, user=Depends(MANAGER)):
    """E21: batalkan booking + simpan kebijakan denda/refund MANUAL (ops isi nominal).
    Body opsional; bila kosong → cancel tanpa denda/refund (kompat perilaku lama)."""
    db = get_db()
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    # State-machine guard: booking SELESAI tidak boleh dibatalkan (mencegah completed→cancelled
    # yang merusak pengakuan pendapatan/riwayat). Sudah cancelled → idempotent (tanpa refund ganda).
    if booking.get("status") == "completed":
        raise HTTPException(status_code=400, detail="Booking sudah selesai — tidak bisa dibatalkan")
    if booking.get("status") == "cancelled":
        return safe_doc(booking)
    # E21: normalisasi + validasi nilai denda/refund
    reason = ""
    cfee = 0.0
    refund = 0.0
    if body is not None:
        reason = (body.reason or "").strip()
        cfee = float(body.cancellation_fee or 0)
        refund = float(body.refund_amount or 0)
        if cfee < 0 or refund < 0:
            raise HTTPException(status_code=400, detail="Denda/refund tak boleh negatif")
    paid = float(booking.get("paid_amount") or 0)
    if refund > paid:
        raise HTTPException(status_code=400, detail=f"Refund melebihi terbayar (paid={paid:.0f})")
    # Set status + simpan snapshot kebijakan pembatalan.
    # (Perbaikan: pakai now_iso() kanonik — tz-aware UTC. Sebelumnya `datetime.utcnow().isoformat()`
    #  menghasilkan timestamp NAIVE (tanpa +00:00) DAN menimpa/shadow fungsi now_iso di scope ini.)
    ts = now_iso()
    cancel_meta = {
        "status": "cancelled",
        "cancellation_reason": reason,
        "cancellation_fee": cfee,
        "refund_amount": refund,
        "cancelled_at": ts,
        "cancelled_by": (user or {}).get("id"),
    }
    await db.bookings.update_one({"id": booking_id}, {"$set": cancel_meta})
    # E21-Ledger: post REFUND sbg payment negatif (idempotent per booking).
    # Rekomendasi HANDOFF: refund = payments negatif method="refund"; paid_amount otomatis
    # berkurang via recompute (Σ payments incl. negatif). Denda diposting sbg invoice terpisah
    # utk paper trail (revenue sudah terekam via net payments — TIDAK double-count).
    if refund > 0:
        from core_utils import new_id, money as _money
        # Idempotent: cek apakah refund payment utk booking ini sudah ada (mis. retry cancel).
        existing = await db.payments.find_one(
            {"booking_id": booking_id, "type": "refund"}, {"_id": 0}
        )
        if not existing:
            pay_doc = {
                "id": new_id("pay"),
                "booking_id": booking_id,
                "amount": -_money(refund),  # negatif → mengurangi paid_amount
                "type": "refund",
                "method": "refund",
                "note": f"Refund pembatalan: {reason}" if reason else "Refund pembatalan",
                "recorded_by": (user or {}).get("id"),
                "paid_at": ts,
            }
            await db.payments.insert_one(pay_doc)
            # Recompute paid_amount + payment_status (INV-2 & INV-3 tetap konsisten).
            from services.finance import recompute_booking_payment
            await recompute_booking_payment(db, booking_id)
    # E26: auto-invoice DENDA sbg paper trail revenue (idempotent per booking).
    # Revenue sudah terekam via Σ payments (denda = paid_amount - refund_amount setelah cancel);
    # invoice ini murni dokumentasi (status='paid' langsung) — TIDAK double-count di P&L.
    if cfee > 0:
        from core_utils import new_id, money as _money
        existing_inv = await db.invoices.find_one(
            {"booking_id": booking_id, "type": "cancellation_fee"}, {"_id": 0}
        )
        if not existing_inv:
            from services.finance import next_invoice_number
            inv_doc = {
                "id": new_id("inv"),
                "number": await next_invoice_number(db),
                "booking_id": booking_id,
                "customer_id": booking.get("customer_id"),
                "customer_name": booking.get("customer_name"),
                "booking_code": booking.get("code"),
                "amount": _money(cfee),
                "type": "cancellation_fee",  # E26: bedakan dari invoice booking normal
                "status": "paid",  # denda otomatis dianggap terbayar (residual dari paid_amount)
                "issued_at": ts,
                "due_at": ts,
                "paid_at": ts,
                "notes": f"Denda pembatalan: {reason}" if reason else "Denda pembatalan",
                "created_by": (user or {}).get("id"),
                "created_at": ts,
                "reconciled_at": ts,
            }
            await db.invoices.insert_one(inv_doc)
    res = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    await _release_booking_resources(db, booking)  # RC-04: bebaskan armada + batalkan trip yatim
    await record(db, actor=user, action="cancel", entity_type="booking", entity_id=booking_id,
                 summary=f"Batalkan booking {res.get('code')} (denda={cfee:.0f}, refund={refund:.0f})")
    # G1/E21: beri tahu pelanggan via WA/CRM saat booking dibatalkan.
    # Payload SSOT + variabel denda/refund ikut supaya template bisa memakai bila perlu.
    from services.wa_payload import build_wa_payload
    payload = await build_wa_payload(db, booking)
    payload.update({
        "cancellation_reason": reason,
        "cancellation_fee": cfee,
        "refund_amount": refund,
    })
    await emit(db, "booking.cancelled", payload, source="bookings", ref_type="booking",
               ref_id=booking_id, dedupe_key=f"booking.cancelled:{booking_id}")
    return safe_doc(res)


@router.post("/bookings/{booking_id}/complete")
async def complete_booking(booking_id: str, user=Depends(MANAGER)):
    db = get_db()
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    if booking.get("status") == "cancelled":
        raise HTTPException(status_code=400, detail="Booking dibatalkan tidak bisa diselesaikan")
    # RC-03/04: bila ada trip aktif, selesaikan lewat SSOT (bebaskan armada + KM + payment).
    trip = await db.trips.find_one({"booking_id": booking_id, "status": {"$ne": "cancelled"}}, {"_id": 0})
    if trip:
        from services.trips import finalize_trip_completion
        await finalize_trip_completion(db, trip, user)
    else:
        # RC-02: JANGAN paksa payment_status='selesai'; set completed lalu derivasi jujur.
        await db.bookings.update_one({"id": booking_id}, {"$set": {"status": "completed"}})
        from services.finance import recompute_booking_payment
        await recompute_booking_payment(db, booking_id)
        # RC-04: bebaskan armada bila terkunci & tak ada trip aktif lain.
        vid = booking.get("vehicle_id")
        if vid:
            veh = await db.vehicles.find_one({"id": vid}, {"_id": 0, "status": 1})
            if veh and veh.get("status") == "on_trip":
                other_active = await db.trips.find_one(
                    {"vehicle_id": vid, "status": {"$in": ["standby", "to_pickup", "on_trip"]}},
                    {"_id": 0, "id": 1})
                if not other_active:
                    await db.vehicles.update_one({"id": vid}, {"$set": {"status": "available"}})
    res = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    await record(db, actor=user, action="complete", entity_type="booking", entity_id=booking_id,
                 summary=f"Selesaikan booking {res.get('code')}")
    # CMS-07 — pesanan selesai = momen tepat meminta ulasan (idempotent per pesanan).
    # Jalur trip sudah menangani ini di `finalize_trip_completion`; blok ini menutup jalur
    # penyelesaian TANPA trip supaya tak ada pesanan selesai yang terlewat diminta ulasan.
    try:
        from services import reviews as _reviews
        await _reviews.request_and_send(db, res, actor=user, source="booking_completed")
    except Exception:  # noqa: BLE001 — permintaan ulasan tak boleh menggagalkan penyelesaian
        pass
    return safe_doc(res)


@router.post("/bookings/{booking_id}/reschedule")
async def reschedule_booking(booking_id: str, body: BookingReschedule, user=Depends(MANAGER)):
    """E17: jadwal ulang booking (tanggal &/atau armada) dgn RE-CEK ketersediaan penuh
    (INV-4 armada + INV-21 perawatan + RC-07 driver). Emit `booking.rescheduled` → WA."""
    db = get_db()
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    if booking.get("status") in ("cancelled", "completed"):
        raise HTTPException(status_code=400, detail="Booking selesai/dibatalkan tidak bisa dijadwalkan ulang")
    start_dt = parse_iso(body.start_datetime)
    end_dt = parse_iso(body.end_datetime)
    if not start_dt or not end_dt:
        raise HTTPException(status_code=400, detail="Format tanggal tidak valid")
    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="Tanggal selesai harus setelah tanggal mulai")
    start_iso, end_iso = start_dt.isoformat(), end_dt.isoformat()
    vehicle_id = body.vehicle_id or booking.get("vehicle_id")
    vehicle = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0})
    if not vehicle:
        raise HTTPException(status_code=400, detail="Armada tidak ditemukan")
    # RC-16 (anti-TOCTOU): re-cek + update jadwal harus serial per armada tujuan.
    async with vehicle_lock(db, vehicle_id):
        conflicts = await find_conflicts(db, vehicle_id, start_iso, end_iso, exclude_id=booking_id)
        if conflicts:
            codes = ", ".join(c.get("code", c.get("id")) for c in conflicts)
            raise HTTPException(status_code=400, detail=f"Armada bentrok dengan booking aktif: {codes}")
        maint = await find_maintenance_conflicts(db, vehicle_id, start_iso, end_iso)
        if maint:
            titles = ", ".join((m.get("title") or m.get("type") or "perawatan") for m in maint)
            raise HTTPException(status_code=400, detail=f"Armada dalam masa perawatan: {titles}")
        if booking.get("driver_id"):
            dconf = await find_driver_conflicts(db, booking["driver_id"], start_iso, end_iso,
                                                exclude_booking_id=booking_id)
            if dconf:
                raise HTTPException(status_code=400,
                                    detail=f"Driver bentrok dengan booking aktif: {dconf[0].get('code')}")
        old_start, old_end = booking.get("start_datetime"), booking.get("end_datetime")
        updates = {"start_datetime": start_iso, "end_datetime": end_iso, "rescheduled_at": now_iso()}
        if vehicle_id != booking.get("vehicle_id"):
            updates["vehicle_id"] = vehicle_id
            updates["vehicle_name"] = vehicle.get("name")
        await db.bookings.update_one({"id": booking_id}, {"$set": updates})
    # Sinkron trip terkait yang belum berjalan (standby/to_pickup): ikutkan armada baru.
    await db.trips.update_many(
        {"booking_id": booking_id, "status": {"$in": ["standby", "to_pickup"]}},
        {"$set": {"vehicle_id": vehicle_id, "dest_name": booking.get("destination")}})
    from services.trips import recompute_trip_fee
    await recompute_trip_fee(db, booking_id, start_iso, end_iso)  # fee /hari ikut tanggal baru
    res = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    await record(db, actor=user, action="reschedule", entity_type="booking", entity_id=booking_id,
                 summary=f"Jadwal ulang booking {res.get('code')}: {(old_start or '')[:16]} → {start_iso[:16]}")
    from services.wa_payload import build_wa_payload
    payload = await build_wa_payload(db, res)
    payload.update({
        "old_start": (old_start or "")[:16].replace("T", " "), "old_end": (old_end or "")[:16].replace("T", " "),
        "new_start": start_iso[:16].replace("T", " "), "new_end": end_iso[:16].replace("T", " "),
        "reason": body.reason or "",
    })
    await emit(db, "booking.rescheduled", payload, source="bookings", ref_type="booking",
               ref_id=booking_id, dedupe_key=f"booking.rescheduled:{booking_id}:{start_iso}")
    return safe_doc(res)


@router.post("/bookings/{booking_id}/approve")
async def approve_booking(booking_id: str, body: BookingApprove, user=Depends(MANAGER)):
    """E19: setujui permintaan booking `pending` (dari publik) → assign armada + tetapkan
    harga + `confirmed`. Re-cek ketersediaan penuh (INV-4/INV-21/RC-07) sebelum konfirmasi."""
    db = get_db()
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    if booking.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Hanya booking berstatus 'pending' yang bisa disetujui")
    vehicle = await db.vehicles.find_one({"id": body.vehicle_id}, {"_id": 0})
    if not vehicle:
        raise HTTPException(status_code=400, detail="Armada tidak ditemukan")
    driver = None
    if body.driver_id:
        driver = await db.drivers.find_one({"id": body.driver_id}, {"_id": 0})
        if not driver:
            raise HTTPException(status_code=400, detail="Driver tidak ditemukan")
    start_iso, end_iso = booking.get("start_datetime"), booking.get("end_datetime")
    # RC-16 (anti-TOCTOU): re-cek + set confirmed harus serial per armada.
    async with vehicle_lock(db, body.vehicle_id):
        conflicts = await find_conflicts(db, body.vehicle_id, start_iso, end_iso, exclude_id=booking_id)
        if conflicts:
            codes = ", ".join(c.get("code", c.get("id")) for c in conflicts)
            raise HTTPException(status_code=400, detail=f"Armada bentrok dengan booking aktif: {codes}")
        maint = await find_maintenance_conflicts(db, body.vehicle_id, start_iso, end_iso)
        if maint:
            titles = ", ".join((m.get("title") or m.get("type") or "perawatan") for m in maint)
            raise HTTPException(status_code=400, detail=f"Armada dalam masa perawatan: {titles}")
        if body.driver_id:
            dconf = await find_driver_conflicts(db, body.driver_id, start_iso, end_iso, exclude_booking_id=booking_id)
            if dconf:
                raise HTTPException(status_code=400,
                                    detail=f"Driver bentrok dengan booking aktif: {dconf[0].get('code')}")
        base = money(body.base_price if body.base_price is not None else booking.get("base_price", 0))
        if base <= 0:
            rules = await get_pricing_rules(db)
            op = await db.settings.find_one({"key": "operational"}, {"_id": 0})
            holidays = (op.get("value") or {}).get("holidays", []) if op else []
            quote = compute_quote(rules, vehicle_type=vehicle.get("type"),
                                  days=span_days(start_iso, end_iso),
                                  when=start_iso, holidays=holidays, include_travel=True,
                                  day_rate=vehicle.get("day_rate"))
            base = money(quote["total"])
        add_ons = booking.get("add_ons") or []
        total = money(base + sum(float(a.get("amount", 0) or 0) for a in add_ons))
        updates = {
            "vehicle_id": vehicle["id"], "vehicle_name": vehicle.get("name"),
            "base_price": base, "total_amount": total, "status": "confirmed", "approved_at": now_iso(),
        }
        if driver:
            updates["driver_id"] = driver["id"]
            updates["driver_name"] = driver.get("name")
        await db.bookings.update_one({"id": booking_id}, {"$set": updates})
    res = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    await record(db, actor=user, action="approve", entity_type="booking", entity_id=booking_id,
                 summary=f"Setujui permintaan booking {res.get('code')} → confirmed (Rp {total:,})".replace(",", "."))
    await _emit_booking_confirmed(db, res)
    return safe_doc(res)


@router.post("/bookings/{booking_id}/reject")
async def reject_booking(booking_id: str, user=Depends(MANAGER)):
    """E19: tolak permintaan booking `pending`/`hold` → cancelled + WA `booking.cancelled`."""
    db = get_db()
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    if booking.get("status") not in ("pending", "hold"):
        raise HTTPException(status_code=400, detail="Hanya booking 'pending'/'hold' yang bisa ditolak")
    await db.bookings.update_one({"id": booking_id}, {"$set": {"status": "cancelled"}})
    await _release_booking_resources(db, booking)
    res = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    await record(db, actor=user, action="reject", entity_type="booking", entity_id=booking_id,
                 summary=f"Tolak permintaan booking {res.get('code')}")
    from services.wa_payload import build_wa_payload
    payload = await build_wa_payload(db, booking)
    await emit(db, "booking.cancelled", payload, source="bookings", ref_type="booking",
               ref_id=booking_id, dedupe_key=f"booking.cancelled:{booking_id}")
    return safe_doc(res)

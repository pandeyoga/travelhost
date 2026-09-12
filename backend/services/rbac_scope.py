"""services/rbac_scope.py — pembatasan CAKUPAN DATA (row-level) per peran.

INV-RBAC-05 (kelas bug RBAC-SCOPE, ditemukan sesi E28 saat audit RBAC-CAL-01):
`require_section` hanya menjaga **pintu modul**. Setelah pintu terbuka, query masih
mengembalikan SELURUH baris. Akibatnya driver yang sah membuka modul Booking melihat
semua booking armada — lengkap dengan nama pelanggan, nominal total & terbayar —
padahal SSOT `docs/05_NAVIGATION_MAP.md` §3 menyatakan:

  | Booking | ✅ Full | ✅ Full | 👁️ trip miliknya |
  | Driver  | ✅ Full | ✅ Full | 👁️ profil sendiri |

Modul ini SSOT pemetaan user->driver + penyaring query, dipakai oleh
`routers/bookings.py`, `routers/drivers.py`, dan `routers/driver.py` (satu jalur,
tak ada duplikasi logika yang bisa melenceng antar-endpoint).
"""

MANAGER_ROLES = ("owner", "ops_admin")


def is_manager(user) -> bool:
    return (user or {}).get("role") in MANAGER_ROLES


async def resolve_driver(db, user):
    """Cari dokumen `drivers` milik user yang login (user_id, fallback phone lalu nama)."""
    if not user:
        return None
    drv = await db.drivers.find_one({"user_id": user.get("id")}, {"_id": 0})
    if not drv and user.get("phone"):
        drv = await db.drivers.find_one({"phone": user.get("phone")}, {"_id": 0})
    if not drv and user.get("name"):
        drv = await db.drivers.find_one({"name": user.get("name")}, {"_id": 0})
    return drv


async def own_driver_id(db, user):
    drv = await resolve_driver(db, user)
    return drv.get("id") if drv else None


async def scope_bookings_query(db, user, query: dict) -> dict:
    """Batasi query bookings ke trip milik driver yang login.

    Driver tanpa dokumen `drivers` terpaut => sengaja dikunci ke sentinel yang tak
    pernah cocok (fail-closed), BUKAN dibiarkan melihat semuanya.
    """
    if is_manager(user):
        return query
    if (user or {}).get("role") == "driver":
        query = dict(query)
        query["driver_id"] = await own_driver_id(db, user) or "__tanpa_driver__"
    return query


async def can_view_booking(db, user, booking) -> bool:
    if is_manager(user):
        return True
    if (user or {}).get("role") == "driver":
        return bool(booking) and booking.get("driver_id") and booking.get("driver_id") == await own_driver_id(db, user)
    return False


async def scope_drivers_query(db, user, query: dict) -> dict:
    """Driver hanya melihat profilnya sendiri (SSOT: '👁️ profil sendiri')."""
    if is_manager(user):
        return query
    if (user or {}).get("role") == "driver":
        query = dict(query)
        query["id"] = await own_driver_id(db, user) or "__tanpa_driver__"
    return query


async def can_view_driver(db, user, driver_id: str) -> bool:
    if is_manager(user):
        return True
    if (user or {}).get("role") == "driver":
        return driver_id == await own_driver_id(db, user)
    return False

# 02 — ARCHITECTURE & TECH DECISIONS
## Travel & Fleet Management Ecosystem

---

## 1. ARSITEKTUR
```
[ Browser ]
   │  (public site  +  authenticated app  +  driver mobile web)
   ▼  REST /api/*  (Authorization: Bearer sess_...)
[ React 19 + Tailwind + shadcn/ui + Recharts + Leaflet + framer-motion ]
   ▼
[ FastAPI + Pydantic ]  — routers (thin) + services (business logic)
   ▼
[ MongoDB (Motor async) ]  — UUID string ids + ISO timestamps
```
- **Frontend** `/app/frontend/src/` (surface switch via `data-surface`).
- **Backend** `/app/backend/` (routers + services + core_utils + dependencies).
- **DB**: koleksi kanonik (lihat `03_DATA_MODEL.md`). Tanpa duplikat.

## 2. KEPUTUSAN TEKNIS (Architecture Decision Records ringkas)
| # | Keputusan | Alasan | Konsekuensi |
|---|-----------|--------|-------------|
| AD-1 | **Auth = session token (`sess_`) + SHA256+salt** (bukan JWT) | sederhana, konsisten, mudah dites; revocable via koleksi `sessions` | simpan token di koleksi `sessions`; helper `current_user` |
| AD-2 | **Respons API = array/objek telanjang** (tanpa envelope `{success,data}`) | kontrak sederhana, mengurangi drift FE↔BE | FE guard `Array.isArray`; gate `verify_api_contract` |
| AD-3 | **ID = UUID string berprefiks** (`bk_`, `veh_`, `drv_`) via `new_id()` | human-readable, tak bocorkan ObjectId | `safe_doc()` strip `_id` |
| AD-4 | **Map = Leaflet + OSM, abstraksi `mapProvider`** | gratis utk v1, swappable ke Google Maps | adapter pattern; ETA via OSRM publik |
| AD-5 | **CRM internal dulu (WA-ready)** | tanpa WABA berbayar; cepat jalan | `conversations`/`messages` generic channel field |
| AD-6 | **Waktu disimpan ISO 8601 UTC** via `now_iso()` | hindari `datetime not JSON serializable` | format ke `id-ID` di FE |
| AD-7 | **Dual-surface theme** via `data-surface=public|app` | satu produk, dua bahasa visual | token CSS di `index.css` |
| AD-8 | **Router thin + service layer** | file < batas, business logic teruji | service di `services/` |
| AD-9 | **Export PDF (reportlab) + Excel (openpyxl) di backend** | konsisten, tak bergantung browser | endpoint `/api/.../export` |

## 3. STRUKTUR BACKEND (target)
```
backend/
  server.py            ← app factory, lifespan, router registration
  db.py                ← Motor client + get_db()
  core_utils.py        ← now_iso(), new_id(), safe_doc(), hash_password()
  dependencies.py      ← current_user(), require_role(), require_permission(), audit()
  permissions_config.py← DEFAULT_PERMISSIONS matrix
  schemas.py           ← Pydantic request models (split bila > 800 baris)
  routers/             ← auth, users, vehicles, drivers, customers, leads, bookings,
                          trips, locations, payments, expenses, invoices, crm,
                          dashboard, reports, public, maintenance, settings
  services/            ← booking_service (availability), trip_service, finance_service,
                          crm_service, geo_service (ETA/track), seed_service
```

## 4. STRUKTUR FRONTEND (target)
```
frontend/src/
  App.js, index.js, index.css (dual-surface tokens)
  services/apiClient.js
  hooks/useAppActions.js
  config/navigationConfig.js
  utils/formatters.js
  components/  (shared) + components/ui/ (shadcn)
  features/public/   (Home, Fleet, Destinations, TripCalculator, Quotation, ThankYou, Blog, About, Contact)
  features/app/      (Dashboard, Bookings+Calendar, Vehicles, Drivers, Customer360, CRM, Finance, Reports, GpsTracking, DriverCheckin, Maintenance, Users, Settings)
```

## 5. ENVIRONMENT (JANGAN diubah/hardcode)
- backend `.env`: `MONGO_URL`, `DB_NAME`. frontend `.env`: `REACT_APP_BACKEND_URL`.
- Backend bind `0.0.0.0:8001`; semua endpoint prefiks `/api`.
- Kredensial pihak ke-3 (Google Maps key dll) → `.env`, jangan di FE.

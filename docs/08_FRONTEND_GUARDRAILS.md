# 08 — FRONTEND GUARDRAILS (React)
## Travel & Fleet Management Ecosystem

> **Status:** WAJIB. Sejajar `07_ENGINEERING_GUARDRAILS.md`.
> **Prinsip emas:** **KODE MENANG atas DOKUMEN.** Design SSOT = `/app/design_guidelines.md`.

---

## 0. ARSITEKTUR FE
```
src/
  App.js                      ← root: routing + state global (user, token, surface)
  index.js / index.css        ← index.css = token CSS dua surface (public/app)
  components/                 ← komponen SHARED
  components/ui/              ← shadcn (PAKAI INI, bukan elemen native)
  features/<domain>/          ← halaman per domain (public/, bookings/, fleet/, crm/, finance/, gps/, ...)
  hooks/useAppActions.js      ← aksi data SHARED
  services/apiClient.js       ← axios instance + `API` const + setAuthToken
  config/navigationConfig.js  ← menu + PAGE_META + ROLE_MENU_ALLOWLIST
  utils/formatters.js         ← formatCurrency, formatQty, formatDate
```
Stack: **React + axios + Recharts + Leaflet/react-leaflet + Tailwind + shadcn + lucide-react + sonner + framer-motion**. Tanpa Redux/Zustand.

---

## 1. KONTRAK API DI FRONTEND (WAJIB)
1. **Semua call lewat `services/apiClient.js`** → `import axios, { API } from ".../services/apiClient"`. `API = ${REACT_APP_BACKEND_URL}/api`. JANGAN hardcode URL/host. JANGAN `fetch()` mentah.
2. **Respons BE = ARRAY/OBJEK telanjang** (tanpa envelope). Selalu guard: `const rows = Array.isArray(res.data) ? res.data : []`.
3. **Auth**: token field = **`token`** (prefix `sess_`), dipasang global via `setAuthToken` → header `Authorization: Bearer sess_...`. Jangan simpan rahasia/API key di FE.
4. **Path endpoint literal** (segmen akhir literal) agar lolos `verify_api_contract` CHECK B. ✅ `axios.post(\`${API}/bookings/${id}/confirm\`)`  ❌ `${API}/bookings/${id}/${action}`.
5. Tiap field yang DIBACA FE harus ADA di respons BE (CHECK C). Tambah binding saat menambah komponen pembaca data.

---

## 2. UI / UX (WAJIB — ditegakkan `ux_audit.py`, target 0 ERROR)
- **Komponen shadcn** dari `components/ui`. **Hindari `<select>` native** (W2) → pakai `Select`. Hindari `<button>`/`<input>` telanjang.
- **Ikon HANYA `lucide-react`.** Tanpa emoji sebagai ikon UI.
- **Uang & qty**: kelas `tabular-nums` + `formatCurrency`/`formatQty` (jangan format manual) (W1).
- **Chart Recharts** wajib `<Tooltip>` + empty-state guard (E3/W4).
- **State data wajib**: tiap view yang fetch HARUS punya **loading** (Skeleton), **empty state** (ikon+pesan+aksi), **error state** (pesan+retry). Tanpa ketiganya = pelanggaran (E1/E2).
- **Tema dua surface**: set `data-surface="public"` atau `data-surface="app"` di root → token dari `index.css`. JANGAN campur token public di halaman app.
- **Warna**: pakai token design system (navy `--primary`, icy-blue `--accent`, status pill). DILARANG merah/hijau/biru mentah (`#FF0000`) & gradien berlebihan (>20% viewport, lihat gradient policy).
- **JANGAN background transparan dengan teks gelap.** Kontras AA. Responsif. Hover/focus/disabled state.

---

## 3. TESTABILITY (WAJIB)
- **`data-testid` di SETIAP** elemen interaktif (button/input/link/select/dialog/calendar-day/table-row/map-control) **dan** info kritis (saldo, total, status, pesan error).
- Penamaan **kebab-case berbasis peran**, unik: `app-bookings-create-button`, `public-trip-finder-submit-button`, `app-gps-driver-list`.
- Jangan duplikat / hapus testid yang dipakai test.

---

## 4. NAVIGASI (config-driven)
- Tambah menu HANYA via `config/navigationConfig.js` (`PAGE_META`, `items`, `ROLE_MENU_ALLOWLIST`) lalu render di shell.
- Ikuti `05_NAVIGATION_MAP.md`. Jangan tambah view di luar map tanpa STOP & ASK.

---

## 5. EXPORT, UKURAN FILE, ENV
- **Komponen** → named export; **Halaman/Page** → default export.
- **Batas baris**: `.jsx`/`.js` komponen ≤ **500**; hooks/services/utils/config `.js` ≤ **300**; `.css` ≤ **400**. Lewat batas ⇒ refactor (dipecah). (`validate_compliance.py`)
- **ENV**: hanya `REACT_APP_BACKEND_URL` (+ `/api`). Jangan ubah `.env`. **Paket**: `yarn add` — JANGAN `npm`.

---

## 6. ROOT CAUSE TAXONOMY (FE)
| Kode | Gejala | Akar | Cegah |
|------|--------|------|-------|
| RC-F1 | Layar putih | import komponen/ikon hilang | cek import; esbuild |
| RC-F2 | `.map is not a function` | asumsi array padahal undefined/objek | `Array.isArray()` guard |
| RC-F3 | 401/403 beruntun | token tak ter-set / role tak punya izin | `setAuthToken`; cek allowlist |
| RC-F4 | FE↔BE drift | path/field FE ≠ route/respons BE | `verify_api_contract.py`; path literal |
| RC-F5 | `body stream already read` | double-fetch StrictMode | async IIFE + cleanup |
| RC-F6 | URL salah di prod | hardcode host | selalu `${API}` dari env |
| RC-F7 | Test rapuh | testid hilang/duplikat | testid unik wajib |
| RC-F8 | UI "datar"/jelek | abaikan token & state data | ikuti §2; loading/empty/error |
| RC-F9 | Map error/blank | lupa import leaflet CSS / marker tanpa koordinat valid | import CSS di entry; guard lat/lng |

---

## 7. ALUR KERJA WAJIB SEBELUM "DONE" (FE)
1. `npx esbuild src/index.js --loader:.js=jsx --bundle --outfile=/dev/null` → 0 error.
2. `python scripts/ux_audit.py --strict` → 0 ERROR (WARN ke backlog).
3. `python scripts/verify_api_contract.py` → FE↔BE OK.
4. `python scripts/check_nav_map.py` bila menyentuh navigasi.
5. `python scripts/validate_compliance.py` → 0 FAIL.
6. Screenshot via **preview URL** (bukan localhost) + login pakai `data-testid`.
7. Verifikasi visual: loading/empty/error tampil, angka rapi (`tabular-nums`), tidak ada console error, kontras cukup.

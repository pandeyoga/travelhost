# 06 — UI/UX STANDARDS (Minimum Usability)
## Travel & Fleet Management Ecosystem

> **Design SSOT lengkap** = `/app/design_guidelines.md` (token, tipografi, komponen, blueprint per halaman). Dokumen ini = **baseline usability yang BISA GAGAL** (di-enforce `scripts/ux_audit.py`).

---

## 1. PRINSIP DASAR
1. **Selalu jujur soal status data.** Tiap area yang memuat data dari API WAJIB punya 3 keadaan eksplisit: **loading**, **empty**, **error**. Layar kosong tanpa penjelasan = bug UX.
2. **Angka presisi & sejajar.** Uang/kuantitas pakai `tabular-nums` + format `id-ID` (`formatCurrency`, `formatQty`).
3. **Tahan-salah (forgiving).** Aksi destruktif (hapus/batal/dispatch) butuh konfirmasi (`AlertDialog`); aksi panjang butuh indikator progress.
4. **Dapat dites.** Elemen interaktif penting punya `data-testid` stabil.
5. **Konsisten.** Pakai komponen shadcn (`components/ui/`), bukan elemen HTML mentah.
6. **Dua bahasa visual, satu produk.** Public = sinematik premium (66nord-inspired). App = data-dense fungsional. Switch via `data-surface`.

---

## 2. ATURAN PER-KOMPONEN (dicek `ux_audit.py`)

### Tabel data — `[ERROR]` bila dilanggar
- **E1** WAJIB **loading state** (Skeleton) saat fetch.
- **E2** WAJIB **empty state** (ikon + "Belum ada ..." + aksi) saat 0 baris.
- Kolom angka uang/qty **WAJIB** `tabular-nums` (W1).
- Baris klik → buka right detail panel.

### Chart (Recharts) — `[ERROR]` bila dilanggar
- **E3** WAJIB empty-state guard. **W4** sebaiknya ada `<Tooltip>`.

### Form / Modal / Dialog
- Validasi inline + pesan error spesifik. Tombol submit disable saat proses + loading. Native `<select>` dilarang → `Select` (W2).
  - **Pakai `@/components/shared/SelectField`** (pembungkus tipis shadcn Select) daripada memanggil
    `Select/SelectTrigger/SelectContent/SelectItem` berulang. Alasan: (a) Radix melarang `SelectItem`
    bernilai string kosong — SelectField memetakan opsi "tanpa pilihan" ke sentinel internal lalu
    mengembalikan `""` ke pemanggil, sehingga kontrak state halaman tetap sederhana; (b) tiap opsi
    otomatis diberi `data-testid` `<testId>-opt-<slug>` supaya otomasi UI stabil (tak bergantung teks).
    Untuk otomasi: **klik trigger dulu, lalu klik item** — `select_option()` tidak berlaku lagi.

### KPI / Metric card
- Angka `tabular-nums` + label & satuan jelas. Sumber kosong → `0` benar, bukan blank/NaN.

### Calendar Booking (khusus domain)
- Color-coded status pembayaran WAJIB: **hijau=lunas, kuning=DP, merah=belum bayar, biru=selesai**. Legend selalu tampil. Cell keyboard-accessible.

### GPS Map (khusus domain)
- Marker warna by status driver. Loading state peta. Guard koordinat valid. Polyline history opacity ≤ 0.6.

### Aksesibilitas & testability
- Elemen interaktif punya `data-testid` (W3 bila ≥3 tombol tanpa testid). Kontras AA. Focus ring terlihat. Touch target ≥ 44px. **JANGAN background transparan dengan teks gelap.**

---

## 3. SEVERITAS & PEMBERLAKUAN
| Kode | Severitas | Arti | Pemberlakuan |
|------|-----------|------|--------------|
| E1–E3 | **ERROR** | loading/empty/chart hilang | File baru/disentuh WAJIB lolos |
| W1 | WARN | uang tanpa `tabular-nums` | Backlog presisi |
| W2 | WARN | `<select>` native | Ganti ke shadcn Select |
| W3 | WARN | interaktif tanpa `data-testid` | Tambah testid |
| W4 | WARN | chart tanpa Tooltip | Tambah Tooltip |

**Aturan emas:** boleh punya backlog (file lama), tetapi **dilarang menambah ERROR baru**. File yang disentuh harus keluar ≥ sama baiknya.
```bash
python scripts/ux_audit.py            # ringkasan
python scripts/ux_audit.py --strict   # exit 1 bila ada ERROR (gate pre-finish)
```

---

## 4. CHECKLIST KUALITAS PER KOMPONEN (sebelum "DONE")
- [ ] Pakai shadcn/ui (tanpa reinvent), ikon lucide.
- [ ] Loading + empty + error state lengkap.
- [ ] Semua elemen interaktif punya `data-testid` unik kebab-case.
- [ ] Label jelas (ikon tanpa teks → `aria-label`).
- [ ] Angka `tabular-nums` + `formatCurrency`/`formatQty`.
- [ ] Token warna dari design system (tanpa warna mentah / gradien berlebih).
- [ ] Kontras AA, focus ring terlihat, keyboard navigable, responsif.
- [ ] `data-surface` benar (public vs app).
- [ ] Tidak ada `console.log` tersisa.

---

## 5. ANTI-PATTERNS (JANGAN)
1. Center-align body content (`.App { text-align:center }`) — ganggu alur baca.
2. Empty state generik (`<p>No data</p>`) — pakai ikon+judul+deskripsi+aksi.
3. `transition: all` — pakai `transition-colors/opacity/shadow` spesifik.
4. Modal di atas modal.
5. Animasi berlebihan / emoji sebagai ikon.
6. Gradien gelap/saturated (purple→pink dll) atau menutupi >20% viewport.

---

## 6. KONTRAK KETERBACAAN DI ATAS KACA & FOTO — `[ERROR]` (dijaga `INV-THEME-01`)

> Ditambahkan 2026-08-12 setelah keluhan user: *"kalau fontnya warna putih maka elemen visual
> background-nya harus disesuaikan agar readability-nya baik."* Semua aturan di bawah
> **eksekutabel** lewat `scripts/guardrails/verify_theme_contrast.py` (+ self-test 7 mutasi),
> karena seluruh kelas bug ini **gagal SENYAP**: tidak ada error konsol, tidak ada tes runtime
> yang merah — halaman hanya "terlihat rusak".

### 6.1 Warna WAJIB lewat token, dan token ini berisi TRIPLET HSL
`--primary: 220 45% 14%` (tanpa `hsl()`). Konsekuensinya:
- ❌ `from-primary to-[color:var(--primary)]`, ❌ `bg-[var(--card)]` → **INVALID**; browser
  membuang seluruh deklarasi → panel jadi transparan & teksnya hilang (BUG-0121 di `/blog/:slug`).
- ✅ utilitas Tailwind bawaan (`bg-primary`, `text-muted-foreground`), ✅
  `style={{ background: "var(--gradient-cta)" }}`, ✅ `hsla(var(--card) / .93)` di CSS,
  ✅ komponen **`CtaBand`** untuk semua panel ajakan-bertindak.

### 6.2 Permukaan kaca harus IKUT MODE
- Latar `.glass`, `.glass-strong`, `.glass-3d`, `.glass-modal`, `.glass-on-hero` — termasuk
  fallback `@supports not (backdrop-filter)` — **dilarang** memaku `hsl(0 0% 100%)`.
  Pakai `--glass-bg`/`--glass-bg-strong`/`--card` yang di-override per preset & mode.
- Surface di ATAS FOTO wajib `.glass-on-hero` (base pekat ±0.93) atau diberi scrim
  (`.hero-scrim`) lebih dulu. Jangan bergantung pada kebetulan warna fotonya.

### 6.3 Refraksi/sheen tidak boleh menyapu teks
- Wajib lewat token `--refraction-opacity` (**≤ 0.30**), `--refraction-blend`
  (`soft-light` di light, `normal` di dark), dan `--refraction-mask` (dibatasi ke tepi atas).
- `mix-blend-mode: screen` hardcode **DILARANG** — di atas foto terang ia menghapus
  label/placeholder (BUG-0122 pada kartu estimator hero).

### 6.4 Jebakan CSS custom property (WAJIB DIINGAT)
`var()` di dalam custom property disubstitusi **di elemen tempat property itu dideklarasikan**,
lalu HASILNYA yang diwariskan. Karena itu `--x: var(--card) / .93` di `:root` = warna tema ERP
terang **selamanya**, walau dipakai di halaman mode gelap (BUG-0125). Tulis ekspresi warnanya
**langsung di kelas pemakainya**.

### 6.5 Konten yang di-PORTAL wajib ikut bertema
Radix menempelkan `DialogContent`/`SelectContent`/`Popover` ke `<body>` — di luar
`div[data-surface="public"][data-theme]`. Karena itu `ThemeContext` memasang
`data-surface`/`data-theme` di **`<html>`** (dan membersihkannya saat unmount agar konsol ERP
tidak ketularan). Konsekuensi yang mudah terlewat: selector `.dark X` hanya cocok untuk
**descendant**, jadi setiap blok preset gelap wajib punya kembaran `X.dark` (BUG-0124).

### 6.6 Elemen mengapung: satu SSOT offset
`--header-h`, `--sticky-cta-h` (0 di desktop, 72px di bawah `lg`), `--fab-gap`, `--fab-bottom`,
`--panel-bottom` + `z-index`: sticky-cta 40 · header 50 · chat 60 · consent 70.
- Panel mengapung wajib punya `maxHeight` berbasis viewport (`100dvh - --header-h - …`).
- ❌ `bottom-24`/`bottom-40` + tinggi tetap → panel menembus header di viewport pendek
  (BUG-0126, keluhan user "posisi chat terlalu di atas").
- Uji WAJIB dengan pengukuran: `panel.y >= header.bottom`, `panel.bottom <= fab.top`,
  `fab.bottom <= stickyCta.top` pada 1920×800 **dan** 390×640.

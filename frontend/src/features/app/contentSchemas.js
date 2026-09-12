// contentSchemas.js — SSOT konfigurasi field per resource untuk Light CMS (ContentManager).
//
// Diekstrak dari ContentManager.jsx (menjaga file komponen < 500 baris sesuai guardrail
// arsitektur). Berisi HANYA data konfigurasi (bukan JSX) supaya mudah diuji & dipakai ulang.
//
// CMS-05: resource dengan halaman publik TIDAK punya toggle `published`/`active` di sini —
// status terbit (draft/terjadwal/tayang) dikelola panel "Terbit" di dialog supaya tidak ada dua
// sumber kebenaran yang bisa berbeda (boolean lama tetap disinkronkan oleh server).
//
// A1: `publicPath` menunjuk route yang BENAR-BENAR ada di `App.js`.

// SEO field group (G6 + CMS-02) — dipakai destinations/packages/articles/promos.
export const SEO_FIELDS = [
  { k: "meta_title", label: "SEO — Meta Title", type: "text", section: "seo", hint: "Judul di hasil pencarian (≤60 karakter)" },
  { k: "meta_description", label: "SEO — Meta Description", type: "textarea", section: "seo", hint: "Ringkasan (≤160 karakter)" },
  { k: "og_image", label: "SEO — OG Image (share sosmed)", type: "image", section: "seo" },
  { k: "canonical", label: "SEO — URL Kanonik (opsional)", type: "text", section: "seo", hint: "Kosongkan bila memakai URL default" },
];

// Konfigurasi field per resource (SSOT form CMS).
export const SCHEMAS = {
  destinations: {
    label: "Destinasi", title: (d) => d.name, sub: (d) => String(d.region || "-").replace(/_/g, " "),
    publicPath: "/destinations/", publicSlugField: "slug",
    fields: [
      { k: "name", label: "Nama", type: "text", req: true },
      { k: "slug", label: "Slug (URL)", type: "text", req: true },
      { k: "region", label: "Region", type: "select", options: [["bali", "Bali"], ["jawa_timur", "Jawa Timur"], ["jawa_tengah", "Jawa Tengah"], ["jawa_barat", "Jawa Barat"], ["yogyakarta", "Yogyakarta"]] },
      { k: "hero_image", label: "Gambar Hero", type: "image" },
      { k: "intro", label: "Intro (kalimat pembuka)", type: "textarea" },
      { k: "description", label: "Deskripsi", type: "textarea" },
      { k: "highlights", label: "Highlight (JSON: title + desc)", type: "json", hint: '[{"title":"Pura & Budaya","desc":"Tanah Lot, Uluwatu..."}]' },
      { k: "best_time", label: "Waktu Terbaik Berkunjung", type: "text" },
      { k: "gallery", label: "Galeri Foto", type: "gallery", galleryMode: "urls" },
      { k: "tour_scenes", label: "Tur 360°", type: "tour" },
      { k: "hotel_recommendations", label: "Rekomendasi Hotel (JSON array)", type: "json", hint: '[{"name":"Hotel","rating":4.5,"price_range":"Rp 1jt"}]' },
      // G4: expose field backend yang belum ada di FE sebelumnya
      { k: "route_points", label: "Rute Perjalanan (JSON array titik)", type: "json", hint: '[{"name":"Bandung","lat":-6.9,"lng":107.6}]' },
      { k: "faqs", label: "FAQ (JSON array q&a)", type: "json", hint: '[{"q":"Apakah aman?","a":"Ya, ..."}]' },
      { k: "position", label: "Urutan tampil (kecil dulu)", type: "number" },
      { k: "popular", label: "Populer", type: "bool" },
      ...SEO_FIELDS,
    ],
  },
  packages: {
    label: "Paket", title: (d) => d.name, sub: (d) => d.destination || "-",
    publicPath: "/packages/", publicSlugField: "slug",
    fields: [
      { k: "name", label: "Nama Paket", type: "text", req: true },
      { k: "slug", label: "Slug (URL)", type: "text", req: true },
      { k: "destination", label: "Destinasi", type: "text" },
      { k: "description", label: "Deskripsi", type: "textarea" },
      { k: "days", label: "Durasi (hari)", type: "number" },
      { k: "pax_min", label: "Peserta minimal", type: "number" },
      { k: "pax_max", label: "Peserta maksimal", type: "number" },
      { k: "price_from", label: "Harga Mulai (Rp)", type: "number" },
      { k: "includes", label: "Termasuk (1 item per baris)", type: "list" },
      { k: "image_url", label: "Gambar (URL)", type: "text" },
      { k: "position", label: "Urutan tampil", type: "number" },
      ...SEO_FIELDS,
    ],
  },
  articles: {
    label: "Artikel", title: (d) => d.title, sub: (d) => `${d.category || "Tips"} · ${d.author || "-"}`,
    publicPath: "/blog/", publicSlugField: "slug",
    fields: [
      { k: "title", label: "Judul", type: "text", req: true },
      { k: "slug", label: "Slug (URL)", type: "text", req: true },
      { k: "category", label: "Kategori", type: "select", options: [["Tips", "Tips"], ["Itinerary", "Itinerary"], ["Korporat", "Korporat"], ["Destinasi", "Destinasi"]] },
      { k: "excerpt", label: "Ringkasan", type: "textarea" },
      { k: "cover_image", label: "Gambar Sampul", type: "image" },
      // CMS-09: isi artikel kini rich text (HTML) — dibersihkan server dengan allowlist ketat.
      { k: "body", label: "Isi Artikel", type: "richtext" },
      { k: "author", label: "Penulis", type: "text" },
      { k: "read_minutes", label: "Waktu Baca (menit)", type: "number" },
      { k: "tags", label: "Tag (pisah koma)", type: "tags" },
      { k: "position", label: "Urutan tampil", type: "number" },
      { k: "featured", label: "Sorotan (tampil besar di Blog)", type: "bool" },
      ...SEO_FIELDS,
    ],
  },
  testimonials: {
    label: "Testimoni", title: (d) => d.name, sub: (d) => d.role || (d.booking_code ? `Pesanan ${d.booking_code}` : "-"),
    fields: [
      { k: "name", label: "Nama", type: "text", req: true },
      { k: "role", label: "Peran / Jabatan", type: "text" },
      { k: "quote", label: "Kutipan", type: "textarea", req: true },
      { k: "rating", label: "Rating (1-5)", type: "number" },
      { k: "avatar", label: "Avatar (URL/upload)", type: "image" },
      { k: "position", label: "Urutan tampil", type: "number" },
      { k: "approved", label: "Disetujui (tampil di publik)", type: "bool" },
    ],
  },
  promos: {
    label: "Promo", title: (d) => d.title || d.code, sub: (d) => d.code,
    fields: [
      { k: "code", label: "Kode Promo", type: "text", req: true, hint: "Huruf & angka, dipakai pelanggan saat checkout" },
      { k: "title", label: "Judul", type: "text" },
      { k: "description", label: "Deskripsi", type: "textarea" },
      { k: "discount_type", label: "Tipe Diskon", type: "select", options: [["percent", "Persen (%)"], ["amount", "Nominal (Rp)"]] },
      { k: "discount_value", label: "Nilai Diskon", type: "number" },
      // A2 — SYARAT PROMO sebagai DATA (bukan kalimat di deskripsi). Semua field di bawah
      // ditegakkan server saat checkout (`services/promos.evaluate`), jadi tidak ada diskon
      // yang lolos di luar niat pemilik.
      { k: "valid_from", label: "Berlaku Mulai", type: "date", hint: "Kosongkan = berlaku sejak sekarang" },
      { k: "valid_until", label: "Berlaku Sampai", type: "date", hint: "Kosongkan = tanpa batas akhir" },
      { k: "min_days", label: "Minimal durasi sewa (hari)", type: "number", hint: "0 / 1 = tanpa syarat durasi" },
      { k: "min_amount", label: "Minimal nilai transaksi (Rp)", type: "number", hint: "Dihitung dari subtotal sebelum potongan" },
      { k: "vehicle_types", label: "Hanya untuk tipe armada", type: "multi", optionsKey: "vehicle_types", allLabel: "Semua tipe", hint: "Kosong = semua tipe armada" },
      { k: "services", label: "Hanya untuk layanan", type: "multi", optionsKey: "services", allLabel: "Semua layanan", hint: "Kosong = semua layanan" },
      { k: "weekend_only", label: "Hanya keberangkatan akhir pekan (Sab/Min)", type: "bool" },
      { k: "max_uses", label: "Kuota pemakaian (0 = tanpa batas)", type: "number", hint: "Dikonsumsi atomik saat pesanan jadi — tidak bisa kelebihan kuota" },
      { k: "used_count", label: "Sudah dipakai", type: "readonly", hint: "Angka dari sistem (tidak bisa diedit manual)" },
      { k: "position", label: "Urutan tampil", type: "number" },
      { k: "active", label: "Aktif", type: "bool" },
      ...SEO_FIELDS,
    ],
  },
};

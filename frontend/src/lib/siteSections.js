// siteSections.js — SSOT meta section utk Page Builder (label + spesifikasi field editor).
// Harus SINKRON dgn whitelist backend routers/site_pages.SECTION_FIELDS.
// Semua field adalah OVERRIDE: kosong = teks bawaan dua-bahasa situs tetap dipakai.

const TXT = (key, label) => ({ key, label, kind: "text" });
const TA = (key, label) => ({ key, label, kind: "textarea" });

export const PAGES = [
  { slug: "home", label: "Beranda" },
  { slug: "about", label: "Tentang Kami" },
  { slug: "contact", label: "Kontak" },
  { slug: "fleet", label: "Armada" },
  { slug: "destinations", label: "Destinasi" },
  { slug: "packages", label: "Paket Wisata" },
  { slug: "promo", label: "Promo" },
  { slug: "blog", label: "Blog / Artikel" },
  { slug: "trip-calculator", label: "Kalkulator Trip" },
];

// URL halaman publik per slug — dipakai tombol "buka di tab baru" + iframe pratinjau.
export const PAGE_URL = {
  home: "/", about: "/about", contact: "/contact", fleet: "/fleet", destinations: "/destinations",
  packages: "/packages", promo: "/promo", blog: "/blog", "trip-calculator": "/trip-calculator",
};

export const SECTION_META = {
  hero: {
    label: "Hero Utama", desc: "Judul besar + gambar latar + tombol aksi di paling atas beranda.",
    fields: [TXT("eyebrow", "Label kecil (eyebrow)"), TXT("title", "Judul besar"), TA("subtitle", "Subjudul"),
      { key: "image", label: "Gambar/video latar", kind: "image" }, { key: "chips", label: "Chip keunggulan (satu per baris)", kind: "lines" },
      TXT("primary_label", "Tombol utama — teks"), TXT("primary_href", "Tombol utama — tautan"),
      TXT("secondary_label", "Tombol kedua — teks"), TXT("secondary_href", "Tombol kedua — tautan")],
  },
  booking_steps: { label: "Langkah Pemesanan", desc: "3 langkah pesan online — kontennya otomatis.", fields: [] },
  value_props: {
    label: "Keunggulan Layanan", desc: "Kartu 'Kenapa memilih kami'.",
    fields: [TXT("eyebrow", "Eyebrow"), TXT("title", "Judul"), TA("subtitle", "Subjudul"),
      { key: "items", label: "Kartu keunggulan", kind: "items", itemFields: [TXT("tag", "Tag kecil"), TXT("title", "Judul kartu"), TA("text", "Deskripsi")] }],
  },
  stats_band: { label: "Statistik Performa", desc: "Angka diambil otomatis dari data operasional.", fields: [TXT("eyebrow", "Eyebrow"), TXT("title", "Judul")] },
  fleet_featured: { label: "Armada Unggulan", desc: "3 unit teratas dari CMS Armada.", fields: [TXT("title", "Judul"), TA("subtitle", "Subjudul")] },
  destinations_featured: { label: "Destinasi Populer", desc: "Destinasi ber-tanda populer dari CMS.", fields: [TXT("title", "Judul"), TA("subtitle", "Subjudul")] },
  testimonials: { label: "Testimoni", desc: "Testimoni tersetujui dari CMS.", fields: [TXT("title", "Judul"), TA("subtitle", "Subjudul")] },
  gallery: {
    label: "Galeri Momen Tamu", desc: "Grid foto & video perjalanan tamu (video diputar otomatis; klik untuk memperbesar).",
    fields: [TXT("eyebrow", "Eyebrow"), TXT("title", "Judul"), TA("subtitle", "Subjudul"),
      { key: "items", label: "Foto / video", kind: "items", itemFields: [{ key: "url", label: "Foto/video (Media Library)", kind: "image" }, TXT("caption", "Keterangan")] }],
  },
  trust: {
    label: "Sinyal Kepercayaan", desc: "4 kartu kecil (CHSE, KIR, servis, GPS).",
    fields: [{ key: "items", label: "Kartu kepercayaan", kind: "items", itemFields: [TXT("title", "Judul"), TA("text", "Deskripsi")] }],
  },
  faq: {
    label: "FAQ", desc: "Pertanyaan yang sering diajukan.",
    fields: [TXT("title", "Judul"), { key: "items", label: "Daftar tanya-jawab", kind: "items", itemFields: [TXT("q", "Pertanyaan"), TA("a", "Jawaban")] }],
  },
  cta_band: {
    label: "Ajakan Penutup (CTA)", desc: "Band biru berisi ajakan minta penawaran.",
    fields: [TXT("title", "Judul"), TA("text", "Teks"), TXT("primary_label", "Tombol utama — teks"), TXT("primary_href", "Tombol utama — tautan"),
      TXT("secondary_label", "Tombol kedua — teks"), TXT("secondary_href", "Tombol kedua — tautan")],
  },
  page_hero: {
    label: "Hero Halaman", desc: "Judul + gambar/video pembuka halaman.",
    fields: [TXT("eyebrow", "Eyebrow"), TXT("title", "Judul"), TA("subtitle", "Subjudul"), { key: "image", label: "Gambar/video latar", kind: "image" }],
  },
  stat_cards: {
    label: "Kartu Statistik", desc: "Angka pencapaian (mis. 500+ trip).",
    fields: [{ key: "items", label: "Kartu angka", kind: "items", itemFields: [TXT("value", "Angka/nilai"), TXT("label", "Keterangan")] }],
  },
  about_story: {
    label: "Cerita & Nilai", desc: "Narasi perusahaan + 4 kartu nilai.",
    fields: [TXT("eyebrow", "Eyebrow"), TXT("title", "Judul"), TA("body", "Narasi"), TXT("cta_label", "Tombol — teks"), TXT("cta_href", "Tombol — tautan"),
      { key: "items", label: "Kartu nilai", kind: "items", itemFields: [TXT("title", "Judul"), TA("text", "Deskripsi")] }],
  },
  contact_channels: { label: "Kanal Kontak", desc: "Kartu telepon/WA/email/alamat — datanya dari Pengaturan Situs.", fields: [TXT("eyebrow", "Eyebrow"), TXT("title", "Judul"), TA("subtitle", "Subjudul")] },
  contact_cta: { label: "Ajakan Penawaran", desc: "Band ajakan minta penawaran cepat.", fields: [TXT("title", "Judul"), TA("note", "Catatan respon")] },
};

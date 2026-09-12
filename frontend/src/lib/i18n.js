// lib/i18n.js — CMS-06: label ANTARMUKA situs publik dalam 2 bahasa.
//
// Isi konten (destinasi/artikel/paket/promo) diterjemahkan di CMS & dikirim server
// (`?lang=`). File ini hanya untuk label tetap di kerangka halaman: menu, tombol, dan
// judul bagian yang tidak berasal dari database — supaya pengunjung English tidak melihat
// campuran dua bahasa di navigasi.
import { DEFAULT_LANG, getLang } from "@/lib/lang";

const STRINGS = {
  id: {
    "nav.home": "Beranda",
    "nav.fleet": "Armada",
    "nav.destinations": "Destinasi",
    "nav.packages": "Paket",
    "nav.calculator": "Kalkulator",
    "nav.blog": "Blog",
    "nav.promo": "Promo",
    "nav.booking": "Pesan Online",
    "nav.booking_status": "Cek Pesanan",
    "nav.quotation": "Minta Penawaran",
    "nav.about": "Tentang",
    "nav.contact": "Kontak",
    "nav.login": "Masuk ERP",
    "nav.help_group": "Layanan & Bantuan",
    "lang.switch": "Ganti bahasa",
    "packages.title": "Paket wisata siap jalan",
    "packages.subtitle": "Rangkaian perjalanan yang sudah kami susun — armada, sopir, dan rute dalam satu harga.",
    "packages.from": "Mulai",
    "packages.days": "hari",
    "packages.includes": "Termasuk",
    "packages.cta": "Pesan paket ini",
    "packages.ask": "Tanya lewat WhatsApp",
    "packages.empty": "Belum ada paket yang tayang.",
    "promo.title": "Promo & penawaran berjalan",
    "promo.subtitle": "Kode di bawah ini berlaku otomatis saat memesan online — syaratnya dijalankan sistem, bukan janji sepihak.",
    "promo.copy": "Salin kode",
    "promo.copied": "Kode disalin",
    "promo.use": "Pakai kode ini",
    "promo.terms": "Syarat",
    "promo.empty": "Belum ada promo aktif saat ini.",
    "promo.sold_out": "Kuota habis",
    "promo.quota_left": "sisa kuota",
    "review.title": "Bagikan pengalaman perjalanan Anda",
    "review.rating": "Seberapa puas Anda?",
    "review.quote": "Cerita singkat perjalanan Anda",
    "review.name": "Nama tampil",
    "review.role": "Peran (mis. Keluarga, HRD PT ...)",
    "review.consent": "Saya setuju ulasan ini ditampilkan di situs RahazaTrans.",
    "review.submit": "Kirim ulasan",
    "review.thanks": "Terima kasih! Ulasan Anda kami tinjau sebelum tayang.",
    "common.loading": "Memuat…",
    "common.back": "Kembali",
    "common.not_found": "Konten tidak ditemukan.",
  },
  en: {
    "nav.home": "Home",
    "nav.fleet": "Fleet",
    "nav.destinations": "Destinations",
    "nav.packages": "Packages",
    "nav.calculator": "Calculator",
    "nav.blog": "Blog",
    "nav.promo": "Deals",
    "nav.booking": "Book online",
    "nav.booking_status": "Track booking",
    "nav.quotation": "Request a quote",
    "nav.about": "About",
    "nav.contact": "Contact",
    "nav.login": "Staff login",
    "nav.help_group": "Services & help",
    "lang.switch": "Change language",
    "packages.title": "Ready-to-go tour packages",
    "packages.subtitle": "Curated journeys — vehicle, driver and route in one transparent price.",
    "packages.from": "From",
    "packages.days": "days",
    "packages.includes": "Included",
    "packages.cta": "Book this package",
    "packages.ask": "Ask on WhatsApp",
    "packages.empty": "No published packages yet.",
    "promo.title": "Live deals & promo codes",
    "promo.subtitle": "These codes are applied automatically at checkout — the rules are enforced by the system.",
    "promo.copy": "Copy code",
    "promo.copied": "Code copied",
    "promo.use": "Use this code",
    "promo.terms": "Terms",
    "promo.empty": "No active deals right now.",
    "promo.sold_out": "Fully claimed",
    "promo.quota_left": "left",
    "review.title": "Share your travel experience",
    "review.rating": "How satisfied were you?",
    "review.quote": "Tell us briefly about your trip",
    "review.name": "Display name",
    "review.role": "Role (e.g. Family, HR of ...)",
    "review.consent": "I agree this review may be shown on the RahazaTrans website.",
    "review.submit": "Send review",
    "review.thanks": "Thank you! We review submissions before publishing.",
    "common.loading": "Loading…",
    "common.back": "Back",
    "common.not_found": "Content not found.",
  },
};

/** Ambil label UI. Fallback: bahasa default → kunci mentah (biar ketahuan kalau lupa isi). */
export function t(key, lang) {
  const code = lang || getLang();
  return (STRINGS[code] && STRINGS[code][key]) || STRINGS[DEFAULT_LANG][key] || key;
}

/**
 * `bi(id, en, lang)` — pasangan teks Indonesia/English DI TEMPAT PEMAKAIANNYA.
 *
 * Dipakai untuk kalimat pemasaran yang hanya muncul di SATU halaman (judul hero, judul
 * section, subjudul, label tombol). Kenapa tidak semuanya masuk `STRINGS` di atas?
 * Karena kalimat sekali-pakai yang dipindah ke kamus terpisah membuat penyuntingnya harus
 * membuka dua berkas dan mudah menjadi kunci yatim saat halaman berubah. Kamus `STRINGS`
 * tetap dipakai untuk label yang DIPAKAI ULANG lintas halaman (menu, tombol umum).
 *
 * Aturan: `id` WAJIB diisi (bahasa dasar), `en` opsional — bila kosong, teks Indonesia dipakai
 * sehingga halaman tak pernah kosong.
 */
export function bi(id, en, lang) {
  const code = lang || getLang();
  if (code === DEFAULT_LANG) return id;
  return en || id;
}

export default t;

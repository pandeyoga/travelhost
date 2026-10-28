import { apiErrorMessage } from "@/lib/apiError";

/**
 * docErrors.js — pesan galat panel Dokumen (tampilan, penomoran, invoice) dengan label kolom
 * yang SAMA dengan label di form, supaya pengguna tahu persis isian mana yang harus dibetulkan.
 * Kunci = nama kolom API (atau "induk.kolom" untuk isian di dalam daftar).
 */
export const DOC_FIELD_LABELS = {
  // penomoran
  pattern: "Pola nomor", prefix: "Awalan", width: "Lebar digit", reset: "Reset urutan", start: "Nomor awal",
  // kop & identitas
  company_name: "Nama perusahaan", tagline: "Tagline", address: "Alamat", phone: "Telepon / WhatsApp",
  email: "Email", website: "Website", npwp: "NPWP", header_mode: "Mode kop surat", footer_mode: "Mode footer",
  accent_color: "Warna aksen", text_color: "Warna teks", footer_text: "Teks footer", paper: "Kertas",
  watermark_text: "Teks watermark", watermark_opacity: "Kepekatan watermark (%)",
  margin_top_mm: "Margin atas (mm)", margin_bottom_mm: "Margin bawah (mm)",
  margin_left_mm: "Margin kiri (mm)", margin_right_mm: "Margin kanan (mm)",
  // gaya tabel
  grid: "Garis tabel", font_size: "Ukuran huruf tabel", grid_color: "Warna garis", width_pct: "Lebar tabel (%)",
  alignment: "Posisi tabel",
  // baris biaya, bagian, tanda tangan, opsi
  sections: "Bagian dokumen", money_rows: "Baris biaya", "money_rows.label": "Nama baris biaya",
  "money_rows.amount": "Nilai baris manual", signatures: "Kolom tanda tangan",
  "signatures.title": "Judul kolom tanda tangan", materai_note: "Teks materai", place: "Tempat (kota) tanda tangan",
  closing_note: "Catatan penutup", content: "Naskah", script: "Naskah",
  // pengaturan invoice
  dp_percent_default: "DP bawaan (%)", dp_due_days: "Jatuh tempo DP (hari)",
  settlement_due_before_start_days: "Pelunasan: H- sebelum berangkat",
  settlement_due_days: "Pelunasan: jatuh tempo (hari)", payment_terms: "Syarat & ketentuan pembayaran",
  footer_note: "Catatan kaki dokumen", bank_accounts: "Rekening", "bank_accounts.bank": "Nama bank",
  "bank_accounts.account_no": "Nomor rekening", "bank_accounts.account_name": "Atas nama rekening",
};

/** Galat axios biasa → string Indonesia. */
export const docErr = (e, fallback) => apiErrorMessage(e, fallback, DOC_FIELD_LABELS);

/** Sama, untuk permintaan `responseType: "blob"` (pratinjau PDF): badan galat JSON-nya berupa Blob. */
export async function docBlobErr(e, fallback) {
  const data = e?.response?.data;
  if (data && typeof data.text === "function") {
    try { return docErr({ response: { data: JSON.parse(await data.text()) } }, fallback); } catch { /* bukan JSON */ }
  }
  return docErr(e, fallback);
}

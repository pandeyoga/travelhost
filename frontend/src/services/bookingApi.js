// bookingApi.js — SATU PINTU pemanggilan API pemesanan online untuk seluruh frontend.
//
// Alasan modul ini ada: sebelumnya setiap halaman publik memanggil endpoint-nya sendiri
// dengan bentuk payload berbeda, sehingga satu perubahan kontrak backend harus dikejar di
// banyak berkas (dan selalu ada satu yang terlewat). Semua pemanggil WAJIB lewat sini.
//
// Catatan penting: TIDAK ADA field harga yang dikirim dari klien. Harga selalu dihitung
// server (lihat services/pricing.py + guardrail INV-BOOK-02) — kalau ada kode frontend yang
// mencoba mengirim total, itu bug, bukan fitur.
import apiClient from "@/services/apiClient";

export const SERVICE_DAILY = "daily_rental";
export const SERVICE_TRANSFER = "airport_transfer";

// Konfigurasi (layanan aktif, tipe armada yang NYATA ada, rute bandara, DP%, kebijakan).
export async function getBookingConfig() {
  const { data } = await apiClient.get("/public/booking/config");
  return data;
}

export async function searchUnits(payload) {
  const { data } = await apiClient.post("/public/booking/search", payload);
  return data;
}

export async function getQuote(payload) {
  const { data } = await apiClient.post("/public/booking/quote", payload);
  return data;
}

export async function submitBooking(payload) {
  const { data } = await apiClient.post("/public/booking/submit", payload);
  return data;
}

// Daftar promo aktif + kelayakannya UNTUK konteks pesanan yang sedang disusun.
// Perhatikan: tidak ada satu pun angka harga yang dikirim — server menghitung ulang subtotal
// lalu menilai tiap promo dengan aturan yang sama seperti saat pesanan dibuat.
export async function listBookingPromos({ service, vehicle_id, start_datetime, end_datetime,
                                         route_id, pax }) {
  const { data } = await apiClient.post("/public/booking/promos", {
    service, vehicle_id, start_datetime, end_datetime: end_datetime || "",
    route_id: route_id || "", pax: Number(pax) || 1,
  });
  return data;
}

export async function lookupBooking({ code, phone }) {
  const { data } = await apiClient.post("/public/booking/lookup", { code, phone });
  return data;
}

export async function getBookingStatus(code, token) {
  const { data } = await apiClient.get(`/public/booking/${encodeURIComponent(code)}`, {
    params: { token },
  });
  return data;
}

export async function uploadPaymentProof(code, { token, file, amount, senderName, bank, note }) {
  const form = new FormData();
  form.append("image", file);
  form.append("token", token || "");
  form.append("amount", String(amount || 0));
  form.append("sender_name", senderName || "");
  form.append("bank", bank || "");
  form.append("note", note || "");
  const { data } = await apiClient.post(
    `/public/booking/${encodeURIComponent(code)}/proof`, form,
    { headers: { "Content-Type": "multipart/form-data" } });
  return data;
}

export async function cancelBooking(code, { token, reason }) {
  const { data } = await apiClient.post(
    `/public/booking/${encodeURIComponent(code)}/cancel`, { token, reason: reason || "" });
  return data;
}

// --- penyimpanan lokal pesanan terakhir (tanpa akun pelanggan) -------------------------
// Tamu tidak punya akun, jadi tautan status ber-token disimpan di peramban agar tombol
// "Pesanan saya" tetap bekerja setelah halaman ditutup. Ini kenyamanan, bukan otentikasi:
// kehilangan localStorage tetap bisa dipulihkan lewat kode booking + nomor WhatsApp.
const LS_KEY = "rahaza_bookings";

export function rememberBooking({ code, token }) {
  if (!code || !token) return;
  try {
    const prev = JSON.parse(localStorage.getItem(LS_KEY) || "[]").filter((b) => b.code !== code);
    localStorage.setItem(LS_KEY, JSON.stringify([{ code, token, at: Date.now() }, ...prev].slice(0, 8)));
  } catch (e) { /* peramban tanpa storage: fitur ini opsional */ }
}

export function rememberedBookings() {
  try {
    return JSON.parse(localStorage.getItem(LS_KEY) || "[]");
  } catch (e) {
    return [];
  }
}

// Buang satu pesanan dari ingatan peramban. Dipakai saat token TIDAK berlaku lagi (404):
// tanpa ini, chip "Lanjutkan pesanan" akan terus menunjuk tautan mati selamanya.
export function forgetBooking(code) {
  if (!code) return;
  try {
    const prev = JSON.parse(localStorage.getItem(LS_KEY) || "[]").filter((b) => b.code !== code);
    localStorage.setItem(LS_KEY, JSON.stringify(prev));
  } catch (e) { /* peramban tanpa storage: fitur ini opsional */ }
}

// Kunci idempotensi: klik ganda / retry jaringan tidak boleh membuat dua pesanan.
export function newIdempotencyKey() {
  const rnd = Math.random().toString(36).slice(2, 10);
  return `web-${Date.now().toString(36)}-${rnd}`;
}

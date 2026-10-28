// bookingRules.js — aturan tampilan aksi booking di ERP (Booking, Kalender, panel pesanan web).
// Cermin aturan backend (routers/booking_lifecycle.py, bookings.cancel/reschedule) supaya tombol
// yang PASTI ditolak server tidak ditawarkan. Server tetap otoritatif: pesan `detail`-nya selalu
// ditampilkan apa adanya bila aturan di sini tertinggal (mis. aturan baru di server).

// Sumber pesanan dari situs publik: wizard pesan online (`web_booking`) & permintaan khusus
// (`public`, formulir /booking/permintaan). Dulu hanya `web_booking` yang dianggap online, jadi
// permintaan khusus tampil "Manual" dan tidak masuk panel "Pesanan Website Masuk".
export const WEB_SOURCES = ["web_booking", "public", "website"];
export const isWebSource = (source) => WEB_SOURCES.includes(source);

export const COMPLETABLE = ["confirmed", "ongoing"];
export const EDITABLE = ["hold", "confirmed", "ongoing"];
export const REJECTABLE = ["pending", "hold"];

const startMs = (b) => {
  const t = new Date(b?.start_datetime || "").getTime();
  return Number.isNaN(t) ? null : t;
};

// Selesai: hanya terkonfirmasi/berjalan yang jadwal mulainya sudah lewat (server: 400 selain itu).
export const canComplete = (b, now = Date.now()) => {
  if (!b || !COMPLETABLE.includes(b.status)) return false;
  const s = startMs(b);
  return s !== null && s <= now;
};

export const canPay = (b) => Boolean(b)
  && !["cancelled", "pending"].includes(b.status) && !["lunas", "selesai"].includes(b.payment_status);

export const canSendInvoiceWa = (b) => Boolean(b?.has_invoice);

// DP yang masih kurang: status hold (DP wajib) atau DP tercatat tapi belum tertutup.
export function dpShortfall(b) {
  const dp = Number(b?.dp_amount || 0);
  const paid = Number(b?.paid_amount || 0);
  if (dp <= 0 || paid >= dp) return 0;
  return dp - paid;
}

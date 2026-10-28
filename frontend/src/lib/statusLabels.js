// statusLabels.js — SSOT label & warna status BOOKING dan TRIP untuk semua layar
// (Booking, Kalender, Dispatch, GPS, Ruang Kerja Driver, halaman publik). Dulu tiap layar punya
// peta sendiri: "to_pickup" tampil sebagai "Berangkat Jemput" / "Menjemput" / "Menuju
// Penjemputan", status hold tampil mentah "hold" di Dispatch. Ubah label HANYA di sini.

export const BOOKING_STATUS = {
  draft: { label: "Draft", short: "Draft", en: "Draft", tone: "neutral" },
  pending: { label: "Menunggu Persetujuan", short: "Menunggu ACC", en: "Awaiting approval", tone: "warning" },
  hold: { label: "Menunggu DP", short: "Menunggu DP", en: "Awaiting deposit", tone: "warning" },
  confirmed: { label: "Terkonfirmasi", short: "Terkonfirmasi", en: "Confirmed", tone: "info" },
  ongoing: { label: "Berjalan", short: "Berjalan", en: "On the road", tone: "warning" },
  completed: { label: "Selesai", short: "Selesai", en: "Completed", tone: "success" },
  cancelled: { label: "Dibatalkan", short: "Dibatalkan", en: "Cancelled", tone: "danger" },
};

// Urutan fase trip: Terjadwal → Menjemput → Dalam Perjalanan → Selesai (backend: services/trips.py TRIP_LABEL).
export const TRIP_STATUS = {
  standby: { label: "Terjadwal", en: "Scheduled", tone: "neutral" },
  to_pickup: { label: "Menjemput", en: "Picking up", tone: "warning" },
  on_trip: { label: "Dalam Perjalanan", en: "On the way", tone: "info" },
  completed: { label: "Selesai", en: "Completed", tone: "success" },
  cancelled: { label: "Dibatalkan", en: "Cancelled", tone: "danger" },
};

export const bookingStatusLabel = (s, { short = false, lang = "id" } = {}) => {
  const m = BOOKING_STATUS[s];
  if (!m) return s || "-";
  return lang === "en" ? m.en : short ? m.short : m.label;
};
export const bookingStatusTone = (s) => (BOOKING_STATUS[s] || {}).tone || "neutral";
export const tripStatusLabel = (s, lang = "id") => {
  const m = TRIP_STATUS[s];
  return m ? (lang === "en" ? m.en : m.label) : s || "-";
};
export const tripStatusTone = (s) => (TRIP_STATUS[s] || {}).tone || "neutral";

// Pembayaran booking. "DP kurang" = sudah bayar tapi belum menutup DP wajib (status hold) —
// dulu tampil "DP" seolah DP sudah terpenuhi.
export const PAYMENT_STATUS = {
  belum_bayar: { label: "Belum Bayar", tone: "danger" },
  dp: { label: "DP", tone: "warning" },
  lunas: { label: "Lunas", tone: "success" },
  selesai: { label: "Selesai", tone: "info" },
};
export function paymentState(booking) {
  const b = booking || {};
  const paid = Number(b.paid_amount || 0);
  const dp = Number(b.dp_amount || 0);
  if (b.status === "cancelled") return paid > 0 ? { label: "Denda ditahan", tone: "neutral" } : { label: "—", tone: "neutral" };
  if (b.status === "hold" && paid > 0 && dp > 0 && paid < dp) return { label: "DP kurang", tone: "danger" };
  return PAYMENT_STATUS[b.payment_status || "belum_bayar"] || { label: b.payment_status || "-", tone: "neutral" };
}

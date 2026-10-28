import { BOOKING_STATUS, PAYMENT_STATUS, TRIP_STATUS } from "@/lib/statusLabels";

const PAYMENT_LABEL = Object.fromEntries(Object.entries(PAYMENT_STATUS).map(([k, v]) => [k, v.label]));
const PAYMENT_TONE = Object.fromEntries(Object.entries(PAYMENT_STATUS).map(([k, v]) => [k, v.tone]));

// Label status booking & trip dari SSOT lib/statusLabels; sisanya status master data.
const STATUS_LABEL = {
  ...Object.fromEntries(Object.entries(TRIP_STATUS).map(([k, v]) => [k, v.label])),
  ...Object.fromEntries(Object.entries(BOOKING_STATUS).map(([k, v]) => [k, v.label])),
  available: "Tersedia", on_trip: "Dalam Perjalanan", maintenance: "Perawatan",
  online: "Online", resting: "Istirahat", offline: "Offline",
  active: "Aktif", inactive: "Nonaktif",
  new: "Baru", contacted: "Dihubungi", quoted: "Penawaran", negotiation: "Negosiasi", won: "Menang", lost: "Hilang",
  retail: "Retail", corporate: "Korporat",
  requested: "Diminta", settled: "Lunas",
};

export function PaymentPill({ value, testId }) {
  const key = value || "belum_bayar";
  return (
    <span className={`status-pill tone-${PAYMENT_TONE[key] || "neutral"}`} data-testid={testId}>
      {PAYMENT_LABEL[key] || key}
    </span>
  );
}

export function StatusPill({ value, tone = "neutral", testId }) {
  return (
    <span className={`status-pill tone-${tone}`} data-testid={testId}>
      {STATUS_LABEL[value] || value || "-"}
    </span>
  );
}

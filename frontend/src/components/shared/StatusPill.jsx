const PAYMENT_LABEL = { lunas: "Lunas", dp: "DP", belum_bayar: "Belum Bayar", selesai: "Selesai" };
const PAYMENT_TONE = { lunas: "success", dp: "warning", belum_bayar: "danger", selesai: "info" };

const STATUS_LABEL = {
  draft: "Draft", pending: "Menunggu Persetujuan", hold: "Hold (Menunggu DP)",
  confirmed: "Terkonfirmasi", ongoing: "Berjalan", completed: "Selesai", cancelled: "Dibatalkan",
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

// calendarCore.js — konstanta + helper MURNI untuk Kalender Keberangkatan.
// Dipakai bersama oleh grid bulan, timeline minggu, day-list, panel detail, dan
// panel "Perlu Perhatian". Tidak ada dependensi React di sini (mudah diuji).

export const STATUS_TONE = {
  pending: "warning", hold: "warning", confirmed: "info", ongoing: "warning",
  completed: "success", cancelled: "danger", draft: "neutral",
};
export const TONE_DOT = { success: "#34C759", info: "#007AFF", warning: "#FF9500", danger: "#FF3B30", neutral: "#8E8E93" };
export const STATUS_SHORT = {
  pending: "Menunggu", hold: "Hold", confirmed: "Terkonfirmasi", ongoing: "Berjalan",
  completed: "Selesai", cancelled: "Dibatalkan", draft: "Draft",
};
export const STATUS_LEGEND = [
  { tone: "info", label: "Terkonfirmasi" },
  { tone: "warning", label: "Hold / Berjalan / Menunggu" },
  { tone: "success", label: "Selesai" },
  { tone: "danger", label: "Dibatalkan" },
];
export const VEHICLE_PALETTE = ["#007AFF", "#34C759", "#FF9500", "#AF52DE", "#FF2D55", "#00C7BE", "#FFCC00", "#5856D6", "#FF6482", "#30B0C7"];
export const WEEKDAYS = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"];
export const MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];
export const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
export const STATUS_FILTERS = [
  { v: "all", l: "Semua status" }, { v: "pending", l: "Menunggu" }, { v: "hold", l: "Hold" },
  { v: "confirmed", l: "Terkonfirmasi" }, { v: "ongoing", l: "Berjalan" },
  { v: "completed", l: "Selesai" }, { v: "cancelled", l: "Dibatalkan" },
];
export const ACTIVE = ["hold", "confirmed", "ongoing"];
export const HOUR_PX = 46;

// Label tipe armada (sinkron backend services/pricing.VEHICLE_TYPES).
export const VEHICLE_TYPE_LABEL = {
  hiace_premio: "Hiace Premio", hiace: "Hiace Commuter", elf: "Isuzu Elf",
  bus: "Medium Bus", avanza: "Avanza / MPV",
};
export const vtypeLabel = (k) => VEHICLE_TYPE_LABEL[k] || (k || "").replace(/_/g, " ");

// --- Lapisan risiko ("Perlu Perhatian") -------------------------------------
// Sumber kebenaran ada di backend (services/attention.py). Di sini hanya gaya visual.
export const RISK_STYLE = {
  vehicle_conflict: { label: "Bentrok armada", fg: "#A8221A", bg: "#FFECE9", border: "#FFC4BD" },
  driver_conflict: { label: "Bentrok sopir", fg: "#A8221A", bg: "#FFECE9", border: "#FFC4BD" },
  maintenance_conflict: { label: "Tabrakan perawatan", fg: "#6B219A", bg: "#F6ECFD", border: "#E0C8F7" },
  hold_expired: { label: "Hold DP kedaluwarsa", fg: "#A8221A", bg: "#FFECE9", border: "#FFC4BD" },
  no_driver: { label: "Belum ada sopir", fg: "#8C4A00", bg: "#FFF4E5", border: "#FFDDAD" },
  hold_expiring: { label: "Tenggat DP mendekat", fg: "#8C4A00", bg: "#FFF4E5", border: "#FFDDAD" },
  pending_request: { label: "Permintaan menunggu", fg: "#0058CC", bg: "#EAF2FF", border: "#C7DCFF" },
  unpaid_soon: { label: "Belum dibayar", fg: "#8C4A00", bg: "#FFF4E5", border: "#FFDDAD" },
};
export const SEVERITY_STYLE = {
  high: { ring: "#FF3B30", fg: "#A8221A", bg: "#FFF3F1", border: "#FFD1CC", label: "Mendesak" },
  medium: { ring: "#FF9500", fg: "#8C4A00", bg: "#FFF8EC", border: "#FFE3B8", label: "Pantau" },
  low: { ring: "#8E8E93", fg: "#3C3C43", bg: "#F5F5F7", border: "#E5E5EA", label: "Info" },
};
export const riskLabel = (type) => (RISK_STYLE[type] || {}).label || type;
export const riskStyleOf = (type) => RISK_STYLE[type] || RISK_STYLE.no_driver;
export const severityStyleOf = (sev) => SEVERITY_STYLE[sev] || SEVERITY_STYLE.low;
export const CONFLICT_TYPES = ["vehicle_conflict", "driver_conflict", "maintenance_conflict"];

// --- Helper tanggal ---------------------------------------------------------
export const pad = (n) => String(n).padStart(2, "0");
export const ymOf = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}`;
export const dayKey = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const dayKeyOfIso = (iso) => { const d = new Date(iso); return Number.isNaN(d.getTime()) ? null : dayKey(d); };
export const timeOfIso = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
};
export const startOfDay = (d) => { const x = new Date(d); x.setHours(0, 0, 0, 0); return x; };
export const startOfWeek = (d) => { const x = startOfDay(d); const off = (x.getDay() + 6) % 7; x.setDate(x.getDate() - off); return x; };

export function buildGrid(viewDate) {
  const first = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1);
  const offset = (first.getDay() + 6) % 7;
  const start = new Date(first);
  start.setDate(first.getDate() - offset);
  return Array.from({ length: 42 }, (_, i) => { const d = new Date(start); d.setDate(start.getDate() + i); return d; });
}

// Susun event dalam satu hari ke lajur (lane) agar jadwal beririsan tampak berdampingan.
export function packLanes(segs) {
  const sorted = [...segs].sort((a, b) => a.startH - b.startH || a.endH - b.endH);
  const laneEnds = [];
  sorted.forEach((s) => {
    let lane = laneEnds.findIndex((end) => s.startH >= end - 0.001);
    if (lane === -1) { lane = laneEnds.length; laneEnds.push(s.endH); } else { laneEnds[lane] = s.endH; }
    s.lane = lane;
  });
  const laneCount = Math.max(laneEnds.length, 1);
  sorted.forEach((s) => { s.laneCount = laneCount; });
  return sorted;
}

export function weekLabelOf(days) {
  if (!days || !days.length) return "";
  const a = days[0]; const b = days[days.length - 1];
  return `${a.getDate()} ${MONTHS_SHORT[a.getMonth()]} – ${b.getDate()} ${MONTHS_SHORT[b.getMonth()]} ${b.getFullYear()}`;
}

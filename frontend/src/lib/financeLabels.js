// financeLabels.js — label & helper Keuangan yang dipakai BERSAMA halaman Keuangan & Laporan.
// Dulu `CAT_LABEL` + `lastMonths` disalin persis di Finance.jsx & Reports.jsx dan keduanya lupa
// `sewa_mitra` (biaya sewa unit mitra dari settlement sub-charter) → laporan menampilkan kunci mentah.
// Sinkron backend services/finance.EXPENSE_CATEGORIES.
export const CAT_LABEL = {
  bbm: "BBM / Solar", tol: "Tol & Parkir", uang_jalan: "Uang Jalan", gaji_driver: "Gaji/Komisi Driver",
  sewa_mitra: "Sewa Unit Mitra", other: "Lainnya",
};

/** [[YYYY-MM, "Oktober 2026"], …] untuk n bulan terakhir (bulan berjalan lebih dulu). */
export function lastMonths(n = 6) {
  const out = [];
  const d = new Date();
  for (let i = 0; i < n; i += 1) {
    const dt = new Date(d.getFullYear(), d.getMonth() - i, 1);
    const key = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}`;
    out.push([key, dt.toLocaleDateString("id-ID", { month: "long", year: "numeric" })]);
  }
  return out;
}

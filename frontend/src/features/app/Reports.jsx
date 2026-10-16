import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { toast } from "sonner";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from "recharts";
import {
  Banknote, Receipt, TrendingUp, Wallet, Calendar, FileSpreadsheet, Users2, Bus, PieChart, Coins, FileText, Trophy, Gauge, Route,
} from "lucide-react";
import apiClient from "@/services/apiClient";
import HoldExpiredReport from "@/components/app/HoldExpiredReport";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { StatusPill } from "@/components/shared/StatusPill";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCurrency, formatQty } from "@/utils/formatters";
import { useAuth } from "@/context/AuthContext";
import { canAccess } from "@/config/navigationConfig";

const STATUS_TONE = { confirmed: "info", ongoing: "warning", completed: "success", cancelled: "danger", draft: "neutral" };
const CAT_LABEL = { bbm: "BBM / Solar", tol: "Tol & Parkir", uang_jalan: "Uang Jalan", gaji_driver: "Gaji/Komisi Driver", other: "Lainnya" };
const MONTHS_ID = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

function lastMonths(n = 6) {
  const out = [];
  const d = new Date();
  for (let i = 0; i < n; i += 1) {
    const dt = new Date(d.getFullYear(), d.getMonth() - i, 1);
    const key = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}`;
    out.push([key, dt.toLocaleDateString("id-ID", { month: "long", year: "numeric" })]);
  }
  return out;
}

function monthShort(key) {
  const m = Number(String(key).slice(5, 7));
  return MONTHS_ID[m - 1] || key;
}

function Kpi({ icon: Icon, label, value, color }) {
  return (
    <div className="kpi-card" data-testid={`rep-kpi-${label}`}>
      <div className="kpi-top">
        <span className="kpi-icon" style={{ background: `${color}18` }}><Icon size={16} style={{ color }} /></span>
        <span className="kpi-label">{label}</span>
      </div>
      <p className="kpi-value tabular-nums">{formatCurrency(value || 0)}</p>
    </div>
  );
}

export default function Reports() {
  const { user } = useAuth();
  const months = lastMonths(6);
  const [period, setPeriod] = useState(months[0][0]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get(`/reports/summary?period=${period}`)
      .then((r) => { setData(r.data); setError(null); })
      .catch(() => setError("Gagal memuat laporan"))
      .finally(() => setLoading(false));
  }, [period]);
  useEffect(() => { load(); }, [load]);

  const exportExcel = async () => {
    setExporting(true);
    try {
      const res = await apiClient.get(`/reports/export?format=excel&period=${period}`, { responseType: "blob" });
      const url = window.URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `laporan-${period}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Laporan diunduh");
    } catch (e) {
      toast.error("Gagal mengunduh laporan");
    } finally {
      setExporting(false);
    }
  };

  const exportPayroll = async (format) => {
    try {
      const res = await apiClient.get(`/reports/payroll/export?format=${format}&period=${period}`, { responseType: "blob" });
      const url = window.URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `rekap-payroll-${period}.${format === "pdf" ? "pdf" : "xlsx"}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Rekap payroll diunduh");
    } catch (e) {
      toast.error("Gagal mengunduh rekap payroll");
    }
  };

  const exportDrivers = async (format) => {
    try {
      const res = await apiClient.get(`/reports/drivers/export?format=${format}&period=${period}`, { responseType: "blob" });
      const url = window.URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `laporan-driver-${period}.${format === "pdf" ? "pdf" : "xlsx"}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Laporan driver diunduh");
    } catch (e) {
      toast.error("Gagal mengunduh laporan driver");
    }
  };

  if (user && !canAccess(user.role, "reports")) return <Navigate to="/app/dashboard" replace />;
  if (loading) return <LoadingState rows={4} testId="reports-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <EmptyState title="Belum ada data" description="Laporan belum tersedia." testId="reports-empty" />;

  const chartData = (data.revenue_by_month || []).map((m) => ({
    name: monthShort(m.month), Pemasukan: m.revenue, Pengeluaran: m.expenses,
  }));
  const hasTrend = chartData.some((m) => m.Pemasukan > 0 || m.Pengeluaran > 0);
  const maxCat = Math.max(1, ...(data.expense_by_category || []).map((c) => c.amount));
  const statuses = (data.bookings_by_status || []).filter((b) => b.count > 0);
  const topCustomers = data.top_customers || [];
  const fleet = data.fleet_utilization || [];
  const payroll = data.payroll || {};
  const pdRows = payroll.per_driver || [];
  const pbs = payroll.by_status || {};
  const psr = payroll.sdm_vs_revenue || {};
  const driversReport = data.drivers_report || {};
  const drRows = driversReport.drivers || [];
  const drFleet = driversReport.fleet || {};
  const rankTone = (rank) => (rank === 1 ? "#FFB800" : rank === 2 ? "#8E8E93" : rank === 3 ? "#CD7F32" : "#0058CC");

  return (
    <div className="space-y-4" data-testid="reports-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="grid flex-1 grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi icon={Banknote} label="Total Pemasukan" value={data.revenue_total} color="#0058CC" />
          <Kpi icon={Receipt} label="Total Pengeluaran" value={data.expense_total} color="#FF3B30" />
          <Kpi icon={TrendingUp} label="Laba Bersih" value={data.profit_total} color="#34C759" />
          <Kpi icon={Wallet} label="Piutang (AR)" value={data.outstanding_ar} color="#FF9500" />
        </div>
        <div className="flex items-center gap-2">
          <Calendar size={15} className="text-[#8E8E93]" />
          <Select value={period} onValueChange={setPeriod}>
            <SelectTrigger className="w-[160px]" data-testid="reports-period"><SelectValue /></SelectTrigger>
            <SelectContent>{months.map(([k, l]) => <SelectItem key={k} value={k}>{l}</SelectItem>)}</SelectContent>
          </Select>
          <button className="primary-button" disabled={exporting} onClick={exportExcel} data-testid="reports-export">
            <FileSpreadsheet size={14} /> Export Excel
          </button>
        </div>
      </div>

      {/* Hold hangus: ditaruh TINGGI di halaman karena isinya menuntut tindakan hari ini
          (tamu yang sudah transfer tapi bukti belum diverifikasi), bukan sekadar rekap. */}
      <HoldExpiredReport />

      <section className="section-card">
        <div className="section-head"><div className="flex items-center gap-2"><TrendingUp size={16} className="text-[#007AFF]" /><h2>Tren Pemasukan vs Pengeluaran (6 bulan)</h2></div></div>
        <div className="section-body">
          {!hasTrend ? (
            <p className="py-10 text-center text-[13px] text-[#6B6B73]" data-testid="reports-trend-empty">Belum ada transaksi pada rentang ini.</p>
          ) : (
            <div className="h-72 w-full" data-testid="reports-trend-chart">
              <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 300 }}>
                <BarChart data={chartData} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EFF0F2" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="#8E8E93" />
                  <YAxis tick={{ fontSize: 11 }} stroke="#8E8E93" tickFormatter={(v) => `${Math.round(v / 1000000)}jt`} />
                  <Tooltip formatter={(v) => formatCurrency(v)} contentStyle={{ borderRadius: 12, border: "1px solid #E5E5EA", fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="Pemasukan" fill="#007AFF" radius={[6, 6, 0, 0]} maxBarSize={36} />
                  <Bar dataKey="Pengeluaran" fill="#FF3B30" radius={[6, 6, 0, 0]} maxBarSize={36} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section className="section-card">
          <div className="section-head"><div className="flex items-center gap-2"><PieChart size={16} className="text-[#FF3B30]" /><h2>Pengeluaran per Kategori</h2></div></div>
          <div className="section-body">
            {data.expense_total === 0 ? (
              <p className="py-8 text-center text-[13px] text-[#6B6B73]" data-testid="reports-cat-empty">Belum ada pengeluaran.</p>
            ) : (
              <div className="space-y-3" data-testid="reports-cat-list">
                {(data.expense_by_category || []).map((c) => (
                  <div key={c.category}>
                    <div className="mb-1 flex items-center justify-between text-[12.5px]">
                      <span className="text-[#3C3C43]">{CAT_LABEL[c.category] || c.category}</span>
                      <span className="font-semibold tabular-nums text-[#1C1C1E]">{formatCurrency(c.amount)}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-[#F0F1F4]">
                      <div className="h-full rounded-full bg-[#FF3B30]" style={{ width: `${(c.amount / maxCat) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="section-card">
          <div className="section-head"><div className="flex items-center gap-2"><Calendar size={16} className="text-[#5856D6]" /><h2>Booking per Status</h2></div></div>
          <div className="section-body">
            {statuses.length === 0 ? (
              <p className="py-8 text-center text-[13px] text-[#6B6B73]" data-testid="reports-status-empty">Belum ada booking.</p>
            ) : (
              <div className="space-y-2" data-testid="reports-status-list">
                {statuses.map((b) => (
                  <div key={b.status} className="flex items-center justify-between rounded-[10px] border border-[#F2F2F5] px-3 py-2.5">
                    <StatusPill value={b.status} tone={STATUS_TONE[b.status] || "neutral"} />
                    <span className="text-[14px] font-bold tabular-nums text-[#1C1C1E]">{formatQty(b.count)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="section-card">
          <div className="section-head"><div className="flex items-center gap-2"><Users2 size={16} className="text-[#AF52DE]" /><h2>Top Customer</h2></div></div>
          <div className="section-body">
            {topCustomers.length === 0 ? (
              <p className="py-8 text-center text-[13px] text-[#6B6B73]" data-testid="reports-cust-empty">Belum ada customer.</p>
            ) : (
              <div className="divide-y divide-[#F2F2F5]" data-testid="reports-cust-list">
                {topCustomers.map((c, i) => (
                  <div key={c.name} className="flex items-center justify-between gap-3 py-2.5">
                    <span className="flex min-w-0 items-center gap-2">
                      <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[#AF52DE]/12 text-[11px] font-bold text-[#6B219A]">{i + 1}</span>
                      <span className="truncate text-[13px] font-semibold text-[#1C1C1E]">{c.name}</span>
                    </span>
                    <span className="flex flex-shrink-0 items-center gap-3 text-[12.5px]">
                      <span className="text-[#6B6B73]">{formatQty(c.total_trips)} trip</span>
                      <span className="font-bold tabular-nums text-[#1C1C1E]">{formatCurrency(c.lifetime_value)}</span>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="section-card">
          <div className="section-head"><div className="flex items-center gap-2"><Bus size={16} className="text-[#34C759]" /><h2>Utilisasi Armada</h2></div></div>
          <div className="section-body">
            {fleet.length === 0 ? (
              <p className="py-8 text-center text-[13px] text-[#6B6B73]" data-testid="reports-fleet-empty">Belum ada data utilisasi.</p>
            ) : (
              <div className="space-y-2" data-testid="reports-fleet-list">
                {fleet.map((v) => (
                  <div key={v.vehicle_name} className="flex items-center justify-between rounded-[10px] border border-[#F2F2F5] px-3 py-2.5">
                    <span className="truncate text-[13px] font-semibold text-[#1C1C1E]">{v.vehicle_name}</span>
                    <span className="text-[12.5px] text-[#6B6B73]">{formatQty(v.bookings)} booking</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>

      <section className="section-card" data-testid="reports-payroll">
        <div className="section-head">
          <div className="flex items-center gap-2"><Coins size={16} className="text-[#5856D6]" /><h2>Rekap Payroll Driver</h2></div>
          <div className="flex items-center gap-2">
            <button className="secondary-button !h-8" onClick={() => exportPayroll("excel")} data-testid="reports-payroll-excel"><FileSpreadsheet size={13} /> Excel</button>
            <button className="secondary-button !h-8" onClick={() => exportPayroll("pdf")} data-testid="reports-payroll-pdf"><FileText size={13} /> PDF</button>
          </div>
        </div>
        <div className="section-body space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Kpi icon={Banknote} label="Total Net Periode" value={payroll.total_net} color="#5856D6" />
            <Kpi icon={Coins} label="Biaya SDM (periode)" value={psr.payroll_cost} color="#FF9500" />
            <div className="kpi-card" data-testid="rep-kpi-Rasio SDM/Revenue">
              <div className="kpi-top"><span className="kpi-icon" style={{ background: "#34C75918" }}><PieChart size={16} style={{ color: "#34C759" }} /></span><span className="kpi-label">Rasio SDM/Revenue</span></div>
              <p className="kpi-value tabular-nums">{formatQty(psr.ratio_pct || 0)}%</p>
            </div>
            <div className="kpi-card" data-testid="rep-kpi-Status Payout">
              <div className="kpi-top"><span className="kpi-icon" style={{ background: "#007AFF18" }}><Users2 size={16} style={{ color: "#007AFF" }} /></span><span className="kpi-label">Payout (D/S/B)</span></div>
              <p className="kpi-value tabular-nums">{formatQty(pbs.draft || 0)}/{formatQty(pbs.approved || 0)}/{formatQty(pbs.paid || 0)}</p>
            </div>
          </div>

          {pdRows.length === 0 ? (
            <p className="py-8 text-center text-[13px] text-[#6B6B73]" data-testid="reports-payroll-empty">Belum ada payout pada periode ini. Buat di Keuangan → Payroll.</p>
          ) : (
            <div className="overflow-x-auto rounded-[12px] border border-[#EFF0F2]" data-testid="reports-payroll-table">
              <table className="w-full text-[12px]">
                <thead className="bg-[#FAFAFB] text-[10px] uppercase tracking-wide text-[#6B6B73]">
                  <tr>
                    <th className="px-3 py-2 text-left">Driver</th>
                    <th className="px-3 py-2 text-right">Trip</th>
                    <th className="px-3 py-2 text-right">KM</th>
                    <th className="px-3 py-2 text-right">Gross</th>
                    <th className="px-3 py-2 text-right">Bonus</th>
                    <th className="px-3 py-2 text-right">Potongan</th>
                    <th className="px-3 py-2 text-right">Total</th>
                    <th className="px-3 py-2 text-right">YTD</th>
                    <th className="px-3 py-2 text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {pdRows.map((r) => (
                    <tr key={r.driver_id} className="border-t border-[#F2F2F5]" data-testid={`reports-payroll-row-${r.driver_id}`}>
                      <td className="px-3 py-2 font-semibold text-[#1C1C1E]">{r.driver_name}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatQty(r.trips)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatQty(r.km)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.gross)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#126E2C]">{formatCurrency(r.bonus)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#A8221A]">{formatCurrency(r.deduction)}</td>
                      <td className="px-3 py-2 text-right font-bold tabular-nums text-[#1C1C1E]">{formatCurrency(r.total)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#6B6B73]">{formatCurrency(r.ytd)}</td>
                      <td className="px-3 py-2 text-[11px] text-[#6B6B73]">{(r.statuses || []).join(", ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      <section className="section-card" data-testid="reports-drivers">
        <div className="section-head">
          <div className="flex items-center gap-2"><Trophy size={16} className="text-[#FFB800]" /><h2>Laporan Driver (Leaderboard)</h2></div>
          <div className="flex items-center gap-2">
            <button className="secondary-button !h-8" onClick={() => exportDrivers("excel")} data-testid="reports-drivers-excel"><FileSpreadsheet size={13} /> Excel</button>
            <button className="secondary-button !h-8" onClick={() => exportDrivers("pdf")} data-testid="reports-drivers-pdf"><FileText size={13} /> PDF</button>
          </div>
        </div>
        <div className="section-body space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Kpi icon={Gauge} label="Revenue per Trip" value={drFleet.revenue_per_trip} color="#0058CC" />
            <div className="kpi-card" data-testid="rep-kpi-Total Trip">
              <div className="kpi-top"><span className="kpi-icon" style={{ background: "#5856D618" }}><Bus size={16} style={{ color: "#5856D6" }} /></span><span className="kpi-label">Total Trip</span></div>
              <p className="kpi-value tabular-nums">{formatQty(drFleet.trips || 0)}</p>
            </div>
            <div className="kpi-card" data-testid="rep-kpi-Trip Selesai">
              <div className="kpi-top"><span className="kpi-icon" style={{ background: "#34C75918" }}><TrendingUp size={16} style={{ color: "#34C759" }} /></span><span className="kpi-label">Trip Selesai</span></div>
              <p className="kpi-value tabular-nums">{formatQty(drFleet.completed || 0)} <span className="text-[12px] font-medium text-[#6B6B73]">({formatQty(drFleet.completion_rate || 0)}%)</span></p>
            </div>
            <div className="kpi-card" data-testid="rep-kpi-Total KM">
              <div className="kpi-top"><span className="kpi-icon" style={{ background: "#FF950018" }}><Route size={16} style={{ color: "#FF9500" }} /></span><span className="kpi-label">Total KM</span></div>
              <p className="kpi-value tabular-nums">{formatQty(drFleet.km || 0)} <span className="text-[12px] font-medium text-[#6B6B73]">km</span></p>
            </div>
          </div>

          {drRows.length === 0 ? (
            <p className="py-8 text-center text-[13px] text-[#6B6B73]" data-testid="reports-drivers-empty">Belum ada trip pada periode ini. Data trip berasal dari Dispatch & Driver Workspace.</p>
          ) : (
            <div className="overflow-x-auto rounded-[12px] border border-[#EFF0F2]" data-testid="reports-drivers-table">
              <table className="w-full text-[12px]">
                <thead className="bg-[#FAFAFB] text-[10px] uppercase tracking-wide text-[#6B6B73]">
                  <tr>
                    <th className="px-3 py-2 text-left">#</th>
                    <th className="px-3 py-2 text-left">Driver</th>
                    <th className="px-3 py-2 text-right">Trip</th>
                    <th className="px-3 py-2 text-right">Selesai</th>
                    <th className="px-3 py-2 text-right">% Selesai</th>
                    <th className="px-3 py-2 text-right">Total KM</th>
                    <th className="px-3 py-2 text-right">Revenue</th>
                    <th className="px-3 py-2 text-right">Revenue/Trip</th>
                    <th className="px-3 py-2 text-right">KM/Trip</th>
                  </tr>
                </thead>
                <tbody>
                  {drRows.map((r) => (
                    <tr key={r.driver_id} className="border-t border-[#F2F2F5]" data-testid={`reports-drivers-row-${r.driver_id}`}>
                      <td className="px-3 py-2">
                        <span className="flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold text-white" style={{ background: rankTone(r.rank) }}>{r.rank}</span>
                      </td>
                      <td className="px-3 py-2 font-semibold text-[#1C1C1E]">{r.driver_name}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatQty(r.trips)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#126E2C]">{formatQty(r.completed)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#6B6B73]">{formatQty(r.completion_rate)}%</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatQty(r.km)}</td>
                      <td className="px-3 py-2 text-right font-bold tabular-nums text-[#1C1C1E]">{formatCurrency(r.revenue)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#0058CC]">{formatCurrency(r.revenue_per_trip)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#6B6B73]">{formatQty(r.avg_km_per_trip)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

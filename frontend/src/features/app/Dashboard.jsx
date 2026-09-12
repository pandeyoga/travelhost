import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import {
  CalendarRange, Bus, IdCard, Contact, Banknote, Wallet, MessageSquare, Receipt,
  RefreshCw, BellRing, AlertTriangle, Inbox, LayoutDashboard, BarChart3,
} from "lucide-react";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/context/AuthContext";
import { LoadingState, ErrorState, EmptyState } from "@/components/shared/DataStates";
import OnboardingChecklist from "@/components/app/OnboardingChecklist";
import InfoTip from "@/components/shared/InfoTip";
import { StatusPill, PaymentPill } from "@/components/shared/StatusPill";
import BiCockpit from "@/components/app/BiCockpit";
import { formatCurrency, formatQty, formatDate, formatDateTime } from "@/utils/formatters";

const STATUS_TONE = { confirmed: "info", ongoing: "warning", completed: "success", cancelled: "danger", draft: "neutral" };

function Kpi({ icon: Icon, label, value, sub, color = "#007AFF", currency, testId, tip }) {
  return (
    <div className="kpi-card" data-testid={testId}>
      <div className="kpi-top">
        <span className="kpi-icon" style={{ background: `${color}18` }}><Icon size={16} style={{ color }} /></span>
        <span className="kpi-label">{label}</span>
        {tip ? <InfoTip text={tip} className="ml-auto" /> : null}
      </div>
      <p className="kpi-value tabular-nums">{currency ? formatCurrency(value) : formatQty(value)}</p>
      {sub ? <p className="kpi-sub">{sub}</p> : null}
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const canBi = user && (user.role === "owner" || user.role === "ops_admin");
  const [tab, setTab] = useState("overview");

  if (!canBi) return <DashboardOverview />;

  return (
    <div data-testid="dashboard-page">
      <div className="tab-bar mb-4">
        <button className={`tab-button ${tab === "overview" ? "active" : ""}`} onClick={() => setTab("overview")} data-testid="tab-dashboard-overview">
          <LayoutDashboard size={14} /> Ringkasan
        </button>
        <button className={`tab-button ${tab === "bi" ? "active" : ""}`} onClick={() => setTab("bi")} data-testid="tab-dashboard-bi">
          <BarChart3 size={14} /> BI Cockpit
        </button>
      </div>
      {tab === "overview" ? <DashboardOverview /> : <BiCockpit />}
    </div>
  );
}

function DashboardOverview() {
  const { data, loading, error, reload } = useResource("/dashboard");

  if (loading) return <LoadingState rows={4} testId="dashboard-loading" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return <EmptyState title="Belum ada data" description="Metrik belum tersedia." />;

  const role = data.role;
  const reminders = Array.isArray(data.reminders) ? data.reminders : [];
  const recent = Array.isArray(data.recent_bookings) ? data.recent_bookings : [];
  const chartData = [
    { name: "Armada", value: data.vehicles || 0 },
    { name: "Driver", value: data.drivers || 0 },
    { name: "Customer", value: data.customers || 0 },
    { name: "Booking", value: data.bookings || 0 },
    { name: "Lead", value: data.leads || 0 },
  ];

  return (
    <div className="space-y-4" data-testid="dashboard-overview">
      <OnboardingChecklist />
      <section className="section-card">
        <div className="section-head">
          <p className="min-w-0 truncate text-[12.5px] text-[#6B6B73]">
            Halo, <span className="font-semibold text-[#1C1C1E]">{data.user_name}</span> · pantauan armada, booking &amp; piutang — real-time
          </p>
          <button className="secondary-button flex-shrink-0" onClick={reload} data-testid="dashboard-refresh"><RefreshCw size={13} /> Muat ulang</button>
        </div>
        <div className="section-body">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Kpi icon={CalendarRange} label="Booking Aktif" value={data.active_bookings} sub="Terkonfirmasi / berjalan" color="#007AFF" testId="kpi-active-bookings" tip="Jumlah booking berstatus terkonfirmasi atau sedang berjalan." />
            <Kpi icon={Bus} label="Armada" value={data.vehicles} sub="Total unit" color="#34C759" testId="kpi-vehicles" />
            <Kpi icon={IdCard} label="Driver" value={data.drivers} sub="Terdaftar" color="#30B0C7" testId="kpi-drivers" />
            <Kpi icon={Contact} label="Customer" value={data.customers} sub="Total pelanggan" color="#AF52DE" testId="kpi-customers" />
            {role !== "driver" ? (
              <>
                <Kpi icon={Banknote} label="Pemasukan Bulan Ini" value={data.revenue_month} currency sub="Pembayaran masuk" color="#0058CC" testId="kpi-revenue-month" tip="Total pembayaran yang masuk pada bulan berjalan." />
                <Kpi icon={Wallet} label="Piutang (AR)" value={data.outstanding_ar} currency sub="Belum tertagih" color="#FF3B30" testId="kpi-ar" tip="Piutang: total tagihan booking yang belum dibayar pelanggan." />
              </>
            ) : null}
            <Kpi icon={Receipt} label="Total Booking" value={data.bookings} sub="Sepanjang waktu" color="#5856D6" testId="kpi-bookings" />
            <Kpi icon={MessageSquare} label="Lead Baru" value={data.leads_new} sub="Perlu ditindak" color="#FF9500" testId="kpi-leads-new" tip="Lead baru dari website yang belum ditindaklanjuti." />
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section className="section-card" data-testid="dashboard-reminders">
          <div className="section-head"><div className="flex items-center gap-2"><BellRing size={16} className="text-[#FF9500]" /><h2>Pengingat Dokumen Armada</h2></div></div>
          <div className="section-body">
            {reminders.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center" data-testid="dashboard-reminders-empty">
                <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-[#F0F1F4]"><Inbox className="h-5 w-5 text-[#8E8E93]" /></div>
                <p className="text-[13px] text-[#6B6B73]">Tidak ada KIR/pajak/servis jatuh tempo dalam 30 hari.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {reminders.map((r, i) => (
                  <div key={i} className="flex items-center justify-between gap-3 rounded-[10px] border border-[#F2F2F5] px-3 py-2.5" data-testid={`reminder-row-${i}`}>
                    <div className="flex items-center gap-2.5">
                      <AlertTriangle size={15} className={r.overdue ? "text-[#FF3B30]" : "text-[#FF9500]"} />
                      <div>
                        <p className="text-[13px] font-semibold text-[#1C1C1E]">{r.code} · {r.vehicle_name}</p>
                        <p className="text-[11.5px] text-[#6B6B73]">{r.type} jatuh tempo {formatDate(r.due_date)}</p>
                      </div>
                    </div>
                    <span className={`status-pill ${r.overdue ? "tone-danger" : "tone-warning"}`}>{r.overdue ? "Terlewat" : r.type}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="section-card" data-testid="dashboard-recent">
          <div className="section-head"><div className="flex items-center gap-2"><CalendarRange size={16} className="text-[#007AFF]" /><h2>Booking Terbaru</h2></div></div>
          <div className="section-body">
            {recent.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center" data-testid="dashboard-recent-empty">
                <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-[#F0F1F4]"><Inbox className="h-5 w-5 text-[#8E8E93]" /></div>
                <p className="text-[13px] text-[#6B6B73]">Belum ada booking.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {recent.map((b) => (
                  <div key={b.id} className="flex items-center justify-between gap-3 rounded-[10px] border border-[#F2F2F5] px-3 py-2.5" data-testid={`recent-booking-${b.id}`}>
                    <div className="min-w-0">
                      <p className="truncate text-[13px] font-semibold text-[#1C1C1E]">{b.code} · {b.customer_name}</p>
                      <p className="text-[11.5px] text-[#6B6B73]">{b.vehicle_name} · {formatDateTime(b.start_datetime)}</p>
                    </div>
                    <div className="flex flex-shrink-0 items-center gap-2">
                      <span className="text-[13px] font-bold tabular-nums text-[#1C1C1E]">{formatCurrency(b.total_amount)}</span>
                      <PaymentPill value={b.payment_status} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>

      <section className="section-card">
        <div className="section-head"><h2>Ringkasan Entitas</h2></div>
        <div className="section-body">
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 300 }}>
              <BarChart data={chartData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EFF0F2" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="#8E8E93" />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} stroke="#8E8E93" />
                <Tooltip cursor={{ fill: "#F5F6F8" }} contentStyle={{ borderRadius: 12, border: "1px solid #E5E5EA", fontSize: 12 }} />
                <Bar dataKey="value" fill="#007AFF" radius={[6, 6, 0, 0]} maxBarSize={56} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>
    </div>
  );
}


import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Banknote, TrendingUp, CalendarRange, Users2, Target, Wallet,
  ArrowUpRight, ArrowDownRight, FileSpreadsheet, FileText, Loader2,
} from "lucide-react";
import apiClient from "@/services/apiClient";
import { LoadingState, ErrorState } from "@/components/shared/DataStates";
import { Input } from "@/components/ui/input";
import { formatCurrency, formatQty } from "@/utils/formatters";
import AdSpendDialog from "@/components/app/AdSpendDialog";
import { FunnelCard, ChannelsCard, ForecastCard } from "@/components/app/BiCharts";
import { FleetCard, DriverCard, ArAgingCard, RetentionCard } from "@/components/app/BiTables";

const PRESETS = [["30", "30 Hari"], ["90", "90 Hari"], ["365", "1 Tahun"]];

function Delta({ pct }) {
  if (pct == null) return null;
  const up = pct >= 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span className="inline-flex items-center gap-0.5 text-[11px] font-semibold" style={{ color: up ? "#127A36" : "#C0271E" }}>
      <Icon size={12} /> {Math.abs(pct)}%
    </span>
  );
}

function Kpi({ icon: Icon, label, metric, color, currency, testId }) {
  const v = metric?.value ?? 0;
  return (
    <div className="kpi-card" data-testid={testId}>
      <div className="kpi-top">
        <span className="kpi-icon" style={{ background: `${color}18` }}><Icon size={16} style={{ color }} /></span>
        <span className="kpi-label">{label}</span>
        <span className="ml-auto"><Delta pct={metric?.delta_pct} /></span>
      </div>
      <p className="kpi-value tabular-nums">{currency ? formatCurrency(v) : (label.includes("%") || label === "Konversi" ? `${v}%` : formatQty(v))}</p>
    </div>
  );
}

export default function BiCockpit() {
  const [mode, setMode] = useState("90");
  const [cStart, setCStart] = useState("");
  const [cEnd, setCEnd] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [exporting, setExporting] = useState("");
  const [spendOpen, setSpendOpen] = useState(false);

  const query = useCallback(() => {
    if (mode === "custom" && cStart && cEnd) return `start=${cStart}&end=${cEnd}`;
    const days = mode === "custom" ? 90 : mode;
    return `days=${days}`;
  }, [mode, cStart, cEnd]);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    const q = query();
    try {
      const [summary, funnel, channels, fleet, drivers, aging, retention, forecast] = await Promise.all([
        apiClient.get(`/analytics/summary?${q}`),
        apiClient.get(`/analytics/funnel?${q}`),
        apiClient.get(`/analytics/channels?${q}`),
        apiClient.get(`/analytics/fleet?${q}`),
        apiClient.get(`/analytics/drivers?${q}`),
        apiClient.get(`/analytics/ar-aging`),
        apiClient.get(`/analytics/retention?${q}`),
        apiClient.get(`/analytics/forecast`),
      ]);
      setData({
        summary: summary.data, funnel: funnel.data, channels: channels.data, fleet: fleet.data,
        drivers: drivers.data, aging: aging.data, retention: retention.data, forecast: forecast.data,
      });
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat BI Cockpit");
    } finally { setLoading(false); }
  }, [query]);

  useEffect(() => {
    if (mode === "custom" && (!cStart || !cEnd)) { setLoading(false); return; }
    load();
  }, [load, mode, cStart, cEnd]);

  const exportFile = async (fmt) => {
    setExporting(fmt);
    try {
      const res = await apiClient.get(`/analytics/export?format=${fmt}&${query()}`, { responseType: "blob" });
      const url = window.URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = `bi-cockpit.${fmt === "pdf" ? "pdf" : "xlsx"}`;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`Cockpit diekspor (${fmt.toUpperCase()})`);
    } catch (e) {
      toast.error("Gagal mengekspor cockpit");
    } finally { setExporting(""); }
  };

  const m = data?.summary?.metrics || {};
  const rangeLabel = data?.summary?.range?.label;

  return (
    <div className="space-y-4" data-testid="bi-cockpit">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          {PRESETS.map(([k, l]) => (
            <button key={k} className={`secondary-button ${mode === k ? "!border-[#007AFF] !text-[#007AFF]" : ""}`}
              onClick={() => setMode(k)} data-testid={`bi-range-${k}`}>{l}</button>
          ))}
          <button className={`secondary-button ${mode === "custom" ? "!border-[#007AFF] !text-[#007AFF]" : ""}`}
            onClick={() => setMode("custom")} data-testid="bi-range-custom"><CalendarRange size={13} /> Kustom</button>
          {mode === "custom" ? (
            <div className="flex items-center gap-1.5">
              <Input type="date" className="!h-9 !w-[148px]" value={cStart} onChange={(e) => setCStart(e.target.value)} data-testid="bi-custom-start" />
              <span className="text-[#8E8E93]">→</span>
              <Input type="date" className="!h-9 !w-[148px]" value={cEnd} onChange={(e) => setCEnd(e.target.value)} data-testid="bi-custom-end" />
            </div>
          ) : null}
        </div>
        <div className="flex items-center gap-1.5">
          {rangeLabel ? <span className="hidden text-[11.5px] text-[#8E8E93] sm:inline">{rangeLabel}</span> : null}
          <button className="secondary-button" disabled={exporting === "pdf"} onClick={() => exportFile("pdf")} data-testid="bi-export-pdf">
            {exporting === "pdf" ? <Loader2 size={13} className="animate-spin" /> : <FileText size={13} />} PDF
          </button>
          <button className="primary-button" disabled={exporting === "excel"} onClick={() => exportFile("excel")} data-testid="bi-export-excel">
            {exporting === "excel" ? <Loader2 size={13} className="animate-spin" /> : <FileSpreadsheet size={14} />} Excel
          </button>
        </div>
      </div>

      {mode === "custom" && (!cStart || !cEnd) ? (
        <div className="section-card"><div className="section-body"><p className="py-10 text-center text-[13px] text-[#6B6B73]" data-testid="bi-custom-hint">Pilih tanggal mulai &amp; akhir untuk menampilkan cockpit.</p></div></div>
      ) : loading ? <LoadingState rows={4} testId="bi-loading" /> :
        error ? <ErrorState message={error} onRetry={load} /> : (
        <>
          {/* KPI eksekutif */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-6" data-testid="bi-kpis">
            <Kpi icon={Banknote} label="Pendapatan" metric={m.revenue} color="#0058CC" currency testId="bi-kpi-revenue" />
            <Kpi icon={TrendingUp} label="Laba" metric={m.profit} color="#34C759" currency testId="bi-kpi-profit" />
            <Kpi icon={CalendarRange} label="Booking" metric={m.bookings} color="#5856D6" testId="bi-kpi-bookings" />
            <Kpi icon={Users2} label="Lead" metric={m.leads} color="#FF9500" testId="bi-kpi-leads" />
            <Kpi icon={Target} label="Konversi" metric={m.conversion_rate} color="#30B0C7" testId="bi-kpi-conversion" />
            <Kpi icon={Wallet} label="Piutang" metric={m.outstanding_ar} color="#FF3B30" currency testId="bi-kpi-ar" />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <FunnelCard funnel={data.funnel} />
            <ChannelsCard channels={data.channels} onEditSpend={() => setSpendOpen(true)} />
          </div>

          <ForecastCard forecast={data.forecast} />

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <FleetCard fleet={data.fleet} />
            <DriverCard drivers={data.drivers} />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <ArAgingCard aging={data.aging} />
            <RetentionCard retention={data.retention} />
          </div>
        </>
      )}

      <AdSpendDialog open={spendOpen} onOpenChange={setSpendOpen} onSaved={load} />
    </div>
  );
}

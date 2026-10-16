import { useCallback, useEffect, useMemo, useState } from "react";
import { GaugeCircle, AlertTriangle, CheckCircle2, CalendarPlus, Settings2, ClipboardList } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { useAuth } from "@/context/AuthContext";
import DataTable from "@/components/shared/DataTable";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { formatDate, formatQty } from "@/utils/formatters";
import PreventiveConfigDialog from "@/components/app/PreventiveConfigDialog";

const STATUS = {
  overdue: { label: "Terlewat", tone: "danger" },
  due_soon: { label: "Segera", tone: "warning" },
  ok: { label: "Aman", tone: "success" },
};

function StatCard({ icon: Icon, label, value, tone, testId }) {
  return (
    <div className="rounded-[14px] border border-[#EFF0F2] bg-white p-4 shadow-sm" data-testid={testId}>
      <div className="flex items-center gap-2 text-[12px] font-semibold text-[#6B6B73]"><Icon size={14} style={{ color: tone }} /> {label}</div>
      <div className="mt-1 text-[24px] font-bold tabular-nums text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>{value}</div>
    </div>
  );
}

function kmText(km) {
  if (!km) return "—";
  return `${formatQty(km.remaining_km)} km lagi`;
}
function dateText(d) {
  if (!d) return "—";
  return d.remaining_days < 0 ? `${formatQty(Math.abs(d.remaining_days))} hari lewat` : `${formatQty(d.remaining_days)} hari lagi`;
}

export default function MaintenancePreventive() {
  const { user } = useAuth();
  const canManage = user && (user.role === "owner" || user.role === "ops_admin");
  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [cfgVehicle, setCfgVehicle] = useState(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await apiClient.get("/maintenance/preventive");
      setItems(r.data?.items || []);
      setSummary(r.data?.summary || null);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat servis preventif");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const schedule = async (row) => {
    setBusyId(row.vehicle_id);
    try {
      await apiClient.post(`/maintenance/preventive/${row.vehicle_id}/schedule`);
      toast.success(`Servis ${row.vehicle_name} dijadwalkan`);
      await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menjadwalkan"); }
    finally { setBusyId(null); }
  };

  const columns = useMemo(() => {
    const cols = [
      { key: "vehicle_name", label: "Armada", render: (r) => <span className="font-semibold text-[#1C1C1E]">{r.vehicle_name}{r.code ? <span className="block text-[11px] text-[#8E8E93]">{r.code}</span> : null}</span> },
      { key: "odometer", label: "Odometer", align: "right", mono: true, render: (r) => <span className="tabular-nums">{r.odometer != null ? `${formatQty(r.odometer)} km` : "—"}</span> },
      { key: "km", label: "Basis Jarak", render: (r) => <span className="tabular-nums text-[12.5px]">{kmText(r.km)}</span> },
      { key: "date", label: "Basis Waktu", render: (r) => <span className="tabular-nums text-[12.5px]">{dateText(r.date)}{r.date ? <span className="block text-[11px] text-[#8E8E93]">{formatDate(r.date.due_date)}</span> : null}</span> },
      { key: "status", label: "Status", render: (r) => { const s = STATUS[r.status] || { label: r.status, tone: "neutral" }; return <span className={`status-pill tone-${s.tone}`} data-testid={`mp-status-${r.vehicle_id}`}>{s.label}</span>; } },
    ];
    if (canManage) {
      cols.push({
        key: "aksi", label: "Aksi", align: "right",
        render: (r) => (
          <div className="flex justify-end gap-1.5">
            <button className="icon-button !h-8 !w-8" title="Atur interval" onClick={() => setCfgVehicle(r)} data-testid={`mp-config-${r.vehicle_id}`}><Settings2 size={14} /></button>
            <button className="secondary-button !h-8" disabled={busyId === r.vehicle_id} title="Jadwalkan servis" onClick={() => schedule(r)} data-testid={`mp-schedule-${r.vehicle_id}`}><CalendarPlus size={13} /> Jadwalkan</button>
          </div>
        ),
      });
    }
    return cols;
  }, [canManage, busyId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <LoadingState testId="maintenance-preventive-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="space-y-4" data-testid="maintenance-preventive">
      {summary ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="mp-summary">
          <StatCard icon={ClipboardList} label="Armada Ber-interval" value={formatQty(summary.total)} tone="#007AFF" testId="mp-stat-total" />
          <StatCard icon={AlertTriangle} label="Terlewat" value={formatQty(summary.overdue)} tone="#FF3B30" testId="mp-stat-overdue" />
          <StatCard icon={GaugeCircle} label="Segera Servis" value={formatQty(summary.due_soon)} tone="#FF9500" testId="mp-stat-soon" />
          <StatCard icon={CheckCircle2} label="Aman" value={formatQty(summary.ok)} tone="#34C759" testId="mp-stat-ok" />
        </div>
      ) : null}

      {items.length === 0 ? (
        <EmptyState title="Belum ada interval servis" description="Atur interval km/waktu pada armada (tombol Atur Interval) agar servis preventif terpantau otomatis." testId="mp-empty" />
      ) : (
        <DataTable title="Servis Preventif Terjadwal" icon={GaugeCircle} columns={columns} rows={items}
          footer={`${formatQty(items.length)} armada dipantau`} testId="mp-table" />
      )}

      <PreventiveConfigDialog open={Boolean(cfgVehicle)} vehicle={cfgVehicle} onOpenChange={(v) => !v && setCfgVehicle(null)} onSaved={load} />
    </div>
  );
}

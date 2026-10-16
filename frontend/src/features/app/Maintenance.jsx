import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Wrench, Plus, Pencil, Trash2, CheckCircle2, BellRing, CalendarClock, Activity, ClipboardList, AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { useAuth } from "@/context/AuthContext";
import DataTable from "@/components/shared/DataTable";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import MaintenanceFormDialog from "@/components/app/MaintenanceFormDialog";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import MaintenancePreventive from "@/components/app/MaintenancePreventive";
import WorkshopsManager from "@/components/app/WorkshopsManager";
import ServiceTypesManager from "@/components/app/ServiceTypesManager";
import { formatCurrency, formatDate, formatQty } from "@/utils/formatters";

const TABS = [
  { id: "schedule", label: "Jadwal & Riwayat" },
  { id: "preventive", label: "Servis Preventif" },
  { id: "workshops", label: "Vendor / Bengkel" },
  { id: "types", label: "Jenis Service" },
];

const TYPE_LABEL = { servis: "Servis", kir: "KIR", pajak: "Pajak", perbaikan: "Perbaikan", lainnya: "Lainnya" };
const TYPE_TONE = { servis: "info", kir: "warning", pajak: "warning", perbaikan: "danger", lainnya: "neutral" };
const STATUS_LABEL = { scheduled: "Terjadwal", in_progress: "Berlangsung", done: "Selesai", cancelled: "Dibatalkan" };
const STATUS_TONE = { scheduled: "info", in_progress: "warning", done: "success", cancelled: "neutral" };
const BUCKET_TONE = { overdue: "danger", h7: "danger", h14: "warning", h30: "neutral" };

function Pill({ label, tone }) {
  return <span className={`status-pill tone-${tone || "neutral"}`}>{label}</span>;
}

function StatCard({ icon: Icon, label, value, tone = "#007AFF", testId }) {
  return (
    <div className="rounded-[14px] border border-[#EFF0F2] bg-white p-4 shadow-sm" data-testid={testId}>
      <div className="flex items-center gap-2 text-[12px] font-semibold text-[#6B6B73]">
        <Icon size={14} style={{ color: tone }} /> {label}
      </div>
      <div className="mt-1 text-[24px] font-bold tabular-nums text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>
        {value}
      </div>
    </div>
  );
}

export default function Maintenance() {
  const { user } = useAuth();
  const canManage = user && (user.role === "owner" || user.role === "ops_admin");
  const [tab, setTab] = useState("schedule");
  const [records, setRecords] = useState([]);
  const [reminders, setReminders] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [delTarget, setDelTarget] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [r1, r2, r3] = await Promise.all([
        apiClient.get("/maintenance"),
        apiClient.get("/maintenance/reminders"),
        apiClient.get("/maintenance/summary"),
      ]);
      setRecords(Array.isArray(r1.data) ? r1.data : []);
      setReminders(r2.data?.reminders || []);
      setSummary(r3.data || null);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat data perawatan");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => { setEditing(null); setFormOpen(true); };
  const openEdit = (r) => { setEditing(r); setFormOpen(true); };

  const complete = async (r) => {
    try {
      await apiClient.post(`/maintenance/${r.id}/complete`, {});
      toast.success("Perawatan ditandai selesai");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal memperbarui"); }
  };

  const doDelete = async () => {
    if (!delTarget) return; setBusy(true);
    try {
      await apiClient.delete(`/maintenance/${delTarget.id}`);
      toast.success("Catatan perawatan dihapus");
      setDelTarget(null); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menghapus"); }
    finally { setBusy(false); }
  };

  const scheduleLabel = (r) => {
    if (r.start_date && r.end_date) return `${formatDate(r.start_date)} → ${formatDate(r.end_date)}`;
    return formatDate(r.scheduled_date);
  };

  const columns = useMemo(() => {
    const cols = [
      { key: "vehicle_name", label: "Armada", render: (r) => <span className="font-semibold text-[#1C1C1E]">{r.vehicle_name || r.vehicle_id}</span> },
      { key: "type", label: "Jenis", render: (r) => <Pill label={TYPE_LABEL[r.type] || r.type} tone={TYPE_TONE[r.type]} /> },
      { key: "title", label: "Pekerjaan", render: (r) => <span>{r.title}</span> },
      { key: "sched", label: "Jadwal", render: (r) => scheduleLabel(r) },
          { key: "workshop", label: "Bengkel", render: (r) => (
      r.workshop ? <span className="truncate" title={r.workshop}>{r.workshop}</span>
                 : <span className="text-[#8E8E93]">—</span>
    ) },
{ key: "cost", label: "Biaya", align: "right", mono: true, render: (r) => formatCurrency(r.cost) },
      { key: "status", label: "Status", render: (r) => <Pill label={STATUS_LABEL[r.status] || r.status} tone={STATUS_TONE[r.status]} /> },
    ];
    if (canManage) {
      cols.push({
        key: "aksi", label: "Aksi", align: "right",
        render: (r) => (
          <div className="flex justify-end gap-1.5">
            {r.status !== "done" && r.status !== "cancelled" ? (
              <button className="icon-button !h-8 !w-8 !text-[#127A36]" title="Tandai selesai" onClick={() => complete(r)} data-testid={`maintenance-complete-${r.id}`}><CheckCircle2 size={15} /></button>
            ) : null}
            <button className="icon-button !h-8 !w-8" title="Edit" onClick={() => openEdit(r)} data-testid={`maintenance-edit-${r.id}`}><Pencil size={14} /></button>
            <button className="icon-button !h-8 !w-8 !text-[#A8221A]" title="Hapus" onClick={() => setDelTarget(r)} data-testid={`maintenance-delete-${r.id}`}><Trash2 size={14} /></button>
          </div>
        ),
      });
    }
    return cols;
  }, [canManage]);

  const addBtn = canManage ? (
    <button className="primary-button" onClick={openCreate} data-testid="maintenance-add-button"><Plus size={14} /> Jadwalkan Perawatan</button>
  ) : null;

  return (
    <div className="space-y-4" data-testid="maintenance-page">
      <div className="tab-bar" data-testid="maintenance-tabs">
        {TABS.map((t) => (
          <button key={t.id} className={`tab-button ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)} data-testid={`maintenance-tab-${t.id}`}>{t.label}</button>
        ))}
      </div>

      {tab === "preventive" ? <MaintenancePreventive /> : null}
      {tab === "workshops" ? <WorkshopsManager /> : null}
      {tab === "types" ? <ServiceTypesManager /> : null}

      {tab === "schedule" ? (
        loading ? <LoadingState testId="maintenance-loading" /> :
        error ? <ErrorState message={error} onRetry={load} /> : (
        <div className="space-y-4">
      {/* KPI */}
      {summary ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="maintenance-summary">
          <StatCard icon={ClipboardList} label="Total Catatan" value={formatQty(summary.total)} testId="mt-stat-total" />
          <StatCard icon={CalendarClock} label="Terjadwal" value={formatQty(summary.scheduled)} tone="#007AFF" testId="mt-stat-scheduled" />
          <StatCard icon={Activity} label="Sedang Berlangsung" value={formatQty(summary.in_progress)} tone="#FF9500" testId="mt-stat-progress" />
          <StatCard icon={AlertTriangle} label="Dokumen Due/Overdue" value={`${formatQty(summary.due_soon)} / ${formatQty(summary.overdue)}`} tone="#FF3B30" testId="mt-stat-due" />
        </div>
      ) : null}

      {/* Reminder dokumen armada (KIR/pajak/servis) */}
      {reminders.length > 0 ? (
        <div className="rounded-[14px] border border-[#FFE6B0] bg-[#FFF8EC] px-4 py-3" data-testid="maintenance-reminders">
          <div className="mb-2 flex items-center gap-2">
            <BellRing size={16} className="text-[#C25400]" />
            <span className="text-[13px] font-semibold text-[#8C4A00]">{formatQty(reminders.length)} dokumen armada perlu perhatian (≤ 30 hari)</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {reminders.map((d, i) => (
              <span key={i} className={`status-pill tone-${BUCKET_TONE[d.bucket] || "neutral"}`} data-testid={`reminder-${i}`}>
                {d.code} · {d.type} · {d.overdue ? "Lewat tempo" : `${formatQty(d.days_left)} hari`}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {/* Tabel jadwal & riwayat servis */}
      {records.length === 0 ? (
        <div className="space-y-3">
          <div className="flex justify-end">{addBtn}</div>
          <EmptyState title="Belum ada catatan perawatan" description="Jadwalkan servis berkala, KIR, pajak, atau perbaikan armada." action={addBtn} testId="maintenance-empty" />
        </div>
      ) : (
        <DataTable title="Jadwal & Riwayat Perawatan" icon={Wrench} columns={columns} rows={records}
          actions={addBtn} footer={`${formatQty(records.length)} catatan perawatan`} testId="maintenance-table" />
      )}
        </div>
        )
      ) : null}

      <MaintenanceFormDialog open={formOpen} onOpenChange={setFormOpen} initial={editing} onSaved={load} />
      <ConfirmDialog
        open={Boolean(delTarget)} onOpenChange={(v) => !v && setDelTarget(null)}
        title="Hapus catatan perawatan?" description={delTarget ? `"${delTarget.title}" (${delTarget.vehicle_name}) akan dihapus.` : ""}
        busy={busy} onConfirm={doDelete} testId="maintenance-delete-confirm"
      />
    </div>
  );
}

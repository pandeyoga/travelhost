import { useCallback, useEffect, useMemo, useState } from "react";
import { Wallet, Plus, FileText, CheckCircle2, Clock, BadgeCheck, Coins, Users } from "lucide-react";
import apiClient from "@/services/apiClient";
import { useAuth } from "@/context/AuthContext";
import DataTable from "@/components/shared/DataTable";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCurrency, formatDate, formatQty } from "@/utils/formatters";
import PayoutFormDialog from "@/components/app/PayoutFormDialog";
import PayoutDetailDialog from "@/components/app/PayoutDetailDialog";
import PayoutBulkDialog from "@/components/app/PayoutBulkDialog";

const STATUS = {
  draft: { l: "Draft", tone: "neutral" },
  approved: { l: "Disetujui", tone: "info" },
  paid: { l: "Dibayar", tone: "success" },
};
const PERIOD_LABEL = { monthly: "Bulanan", weekly: "Mingguan", per_trip: "Per Trip" };

function Kpi({ icon: Icon, label, value, color }) {
  return (
    <div className="kpi-card" data-testid={`payroll-kpi-${label}`}>
      <div className="kpi-top">
        <span className="kpi-icon" style={{ background: `${color}18` }}><Icon size={16} style={{ color }} /></span>
        <span className="kpi-label">{label}</span>
      </div>
      <p className="kpi-value tabular-nums">{value}</p>
    </div>
  );
}

export default function PayrollManager() {
  const { user } = useAuth();
  const canManage = user && (user.role === "owner" || user.role === "ops_admin");
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [formOpen, setFormOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [detailId, setDetailId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [r1, r2] = await Promise.all([
        apiClient.get("/payroll/payouts", { params: statusFilter === "all" ? {} : { status: statusFilter } }),
        apiClient.get("/payroll/summary"),
      ]);
      setRows(Array.isArray(r1.data) ? r1.data : []);
      setSummary(r2.data || null);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat data payroll");
    } finally { setLoading(false); }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  const columns = useMemo(() => [
    { key: "driver", label: "Driver", render: (r) => <span className="font-semibold text-[#1C1C1E]">{r.driver_name}</span> },
    { key: "period", label: "Periode", render: (r) => (
      <span className="text-[12px] text-[#3C3C43]">{formatDate(r.period_start)} → {formatDate(r.period_end)}<span className="block text-[10.5px] text-[#8E8E93]">{PERIOD_LABEL[r.period_type] || r.period_type}</span></span>
    ) },
    { key: "trips", label: "Trip / KM", align: "right", render: (r) => <span className="tabular-nums text-[12px]">{formatQty(r.trips_count || 0)} · {formatQty(r.total_km || 0)} km</span> },
    { key: "total", label: "Total", align: "right", mono: true, render: (r) => <span className="font-bold tabular-nums text-[#1C1C1E]">{formatCurrency(r.total)}</span> },
    { key: "status", label: "Status", render: (r) => <span className={`status-pill tone-${(STATUS[r.status] || {}).tone || "neutral"}`}>{(STATUS[r.status] || {}).l || r.status}</span> },
    { key: "aksi", label: "Aksi", align: "right", render: (r) => (
      <button className="secondary-button !h-8" onClick={() => setDetailId(r.id)} data-testid={`payout-view-${r.id}`}><FileText size={13} /> Detail</button>
    ) },
  ], []);

  const addBtn = canManage ? (
    <div className="flex items-center gap-2">
      <button className="secondary-button" onClick={() => setBulkOpen(true)} data-testid="payout-bulk-btn"><Users size={14} /> Generate Massal</button>
      <button className="primary-button" onClick={() => setFormOpen(true)} data-testid="payout-generate-btn"><Plus size={14} /> Generate Payout</button>
    </div>
  ) : null;

  const filterBar = (
    <div className="flex items-center gap-2">
      <Select value={statusFilter} onValueChange={setStatusFilter}>
        <SelectTrigger className="h-9 w-[150px]" data-testid="payroll-status-filter"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Semua Status</SelectItem>
          <SelectItem value="draft">Draft</SelectItem>
          <SelectItem value="approved">Disetujui</SelectItem>
          <SelectItem value="paid">Dibayar</SelectItem>
        </SelectContent>
      </Select>
      {addBtn}
    </div>
  );

  const s = summary || { by_status: {} };

  return (
    <div className="space-y-4" data-testid="payroll-manager">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi icon={Coins} label="Total Akrual" value={formatCurrency(s.accrued_total || 0)} color="#5856D6" />
        <Kpi icon={BadgeCheck} label="Total Dibayar" value={formatCurrency(s.paid_total || 0)} color="#34C759" />
        <Kpi icon={Clock} label="Draft" value={formatQty((s.by_status || {}).draft || 0)} color="#8E8E93" />
        <Kpi icon={CheckCircle2} label="Disetujui / Dibayar" value={`${formatQty((s.by_status || {}).approved || 0)} / ${formatQty((s.by_status || {}).paid || 0)}`} color="#0058CC" />
      </div>

      {loading ? <LoadingState testId="payroll-loading" /> :
        error ? <ErrorState message={error} onRetry={load} /> :
        rows.length === 0 ? (
          <div className="space-y-3">
            <div className="flex justify-end">{filterBar}</div>
            <EmptyState title="Belum ada payout" description="Generate payout per periode dari trip selesai + gaji pokok & komponen kompensasi driver." action={addBtn} testId="payroll-empty" />
          </div>
        ) : (
          <DataTable title="Payroll Driver" icon={Wallet} columns={columns} rows={rows}
            actions={filterBar} footer={`${formatQty(rows.length)} payout`} testId="payroll-table" />
        )}

      <PayoutFormDialog open={formOpen} onOpenChange={setFormOpen} onSaved={(id) => { load(); if (id) setDetailId(id); }} />
      <PayoutBulkDialog open={bulkOpen} onOpenChange={setBulkOpen} onSaved={load} />
      <PayoutDetailDialog payoutId={detailId} onOpenChange={(v) => { if (!v) setDetailId(null); }} onChanged={load} canManage={canManage} />
    </div>
  );
}

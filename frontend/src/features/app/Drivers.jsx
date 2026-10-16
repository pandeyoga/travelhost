import { useState } from "react";
import { IdCard, Plus, Pencil, Trash2, Eye } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/context/AuthContext";
import DataTable from "@/components/shared/DataTable";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { StatusPill } from "@/components/shared/StatusPill";
import DriverFormDialog from "@/components/app/DriverFormDialog";
import DriverDetailDrawer from "@/components/app/DriverDetailDrawer";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import { formatDate, formatQty } from "@/utils/formatters";

const DRIVER_TONE = { online: "success", resting: "warning", offline: "neutral" };

export default function Drivers() {
  const { user } = useAuth();
  const { data, loading, error, reload } = useResource("/drivers");
  const rows = Array.isArray(data) ? data : [];
  const canManage = user && (user.role === "owner" || user.role === "ops_admin");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [delTarget, setDelTarget] = useState(null);
  const [busy, setBusy] = useState(false);
  const [detail, setDetail] = useState(null);

  const openCreate = () => { setEditing(null); setFormOpen(true); };
  const openEdit = (r) => { setEditing(r); setFormOpen(true); };

  const doDelete = async () => {
    if (!delTarget) return;
    setBusy(true);
    try {
      await apiClient.delete(`/drivers/${delTarget.id}`);
      toast.success("Driver dihapus");
      setDelTarget(null);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus driver");
    } finally { setBusy(false); }
  };

  const columns = [
    { key: "name", label: "Nama", render: (r) => <span className="font-semibold text-[#1C1C1E]">{r.name}</span> },
    { key: "phone", label: "Telepon", mono: true },
    { key: "sim_number", label: "No. SIM", mono: true },
    { key: "sim_expiry", label: "SIM Berlaku", render: (r) => formatDate(r.sim_expiry) },
    { key: "status", label: "Status Kerja", render: (r) => <StatusPill value={r.status} tone={DRIVER_TONE[r.status] || "neutral"} /> },
    { key: "account_email", label: "Akun Login", render: (r) => (r.account_email
      ? <span className="font-mono text-[12px]" data-testid={`driver-account-${r.id}`}>{r.account_email}</span>
      : <span className="text-[12px] text-[#A8221A]" data-testid={`driver-account-${r.id}`}>Belum ada akun</span>) },
  ];
  if (canManage) {
    columns.push({
      key: "aksi", label: "Aksi", align: "right",
      render: (r) => (
        <div className="flex justify-end gap-1.5">
          <button className="icon-button !h-8 !w-8" title="Detail kinerja" onClick={(e) => { e.stopPropagation(); setDetail(r); }} data-testid={`driver-detail-${r.id}`}><Eye size={14} /></button>
          <button className="icon-button !h-8 !w-8" onClick={(e) => { e.stopPropagation(); openEdit(r); }} data-testid={`driver-edit-${r.id}`}><Pencil size={14} /></button>
          <button className="icon-button !h-8 !w-8 !text-[#A8221A]" onClick={(e) => { e.stopPropagation(); setDelTarget(r); }} data-testid={`driver-delete-${r.id}`}><Trash2 size={14} /></button>
        </div>
      ),
    });
  } else {
    columns.push({
      key: "aksi", label: "", align: "right",
      render: (r) => (
        <button className="icon-button !h-8 !w-8" title="Detail kinerja" onClick={(e) => { e.stopPropagation(); setDetail(r); }} data-testid={`driver-detail-${r.id}`}><Eye size={14} /></button>
      ),
    });
  }

  const addBtn = canManage ? (
    <button className="primary-button" onClick={openCreate} data-testid="drivers-add-button"><Plus size={14} /> Tambah Driver</button>
  ) : null;

  return (
    <div className="space-y-4" data-testid="drivers-page">
      {loading ? (
        <LoadingState testId="drivers-loading" />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : rows.length === 0 ? (
        <div className="space-y-3">
          <div className="flex justify-end">{addBtn}</div>
          <EmptyState title="Belum ada driver" description="Tambahkan pengemudi pertama Anda." action={addBtn} testId="drivers-empty" />
        </div>
      ) : (
        <DataTable title="Driver" icon={IdCard} columns={columns} rows={rows} actions={addBtn} onRowClick={setDetail} footer={`${formatQty(rows.length)} driver terdaftar`} testId="drivers-table" />
      )}

      <DriverDetailDrawer open={Boolean(detail)} driver={detail} onOpenChange={(v) => !v && setDetail(null)} />
      <DriverFormDialog open={formOpen} onOpenChange={setFormOpen} initial={editing} onSaved={reload} />
      <ConfirmDialog
        open={Boolean(delTarget)} onOpenChange={(v) => !v && setDelTarget(null)}
        title="Hapus driver?" description={delTarget ? `"${delTarget.name}" akan dihapus permanen.` : ""}
        busy={busy} onConfirm={doDelete} testId="driver-delete-confirm"
      />
    </div>
  );
}

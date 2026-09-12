import { useCallback, useEffect, useMemo, useState } from "react";
import { Wrench, Plus, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { useAuth } from "@/context/AuthContext";
import DataTable from "@/components/shared/DataTable";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { formatQty } from "@/utils/formatters";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import ServiceTypeFormDialog from "@/components/app/ServiceTypeFormDialog";

export default function ServiceTypesManager() {
  const { user } = useAuth();
  const canManage = user && (user.role === "owner" || user.role === "ops_admin");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [delTarget, setDelTarget] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await apiClient.get("/service-types");
      setRows(Array.isArray(r.data) ? r.data : []);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat jenis service");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const doDelete = async () => {
    if (!delTarget) return; setBusy(true);
    try {
      await apiClient.delete(`/service-types/${delTarget.id}`);
      toast.success("Jenis service dihapus"); setDelTarget(null); await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menghapus"); }
    finally { setBusy(false); }
  };

  const columns = useMemo(() => {
    const cols = [
      { key: "name", label: "Jenis Service", render: (r) => <span className="font-semibold text-[#1C1C1E]">{r.name}</span> },
      { key: "key", label: "Kunci", render: (r) => <span className="status-pill tone-neutral">{r.key}</span> },
      { key: "default_interval_km", label: "Interval (km)", align: "right", render: (r) => <span className="tabular-nums">{r.default_interval_km != null ? formatQty(r.default_interval_km) : "—"}</span> },
      { key: "default_interval_days", label: "Interval (hari)", align: "right", render: (r) => <span className="tabular-nums">{r.default_interval_days != null ? formatQty(r.default_interval_days) : "—"}</span> },
      { key: "active", label: "Status", render: (r) => <span className={`status-pill tone-${r.active ? "success" : "neutral"}`}>{r.active ? "Aktif" : "Nonaktif"}</span> },
    ];
    if (canManage) {
      cols.push({
        key: "aksi", label: "Aksi", align: "right",
        render: (r) => (
          <div className="flex justify-end gap-1.5">
            <button className="icon-button !h-8 !w-8" title="Edit" onClick={() => { setEditing(r); setFormOpen(true); }} data-testid={`svt-edit-${r.id}`}><Pencil size={14} /></button>
            <button className="icon-button !h-8 !w-8 !text-[#A8221A]" title="Hapus" onClick={() => setDelTarget(r)} data-testid={`svt-del-${r.id}`}><Trash2 size={14} /></button>
          </div>
        ),
      });
    }
    return cols;
  }, [canManage]);

  const addBtn = canManage ? (
    <button className="primary-button" onClick={() => { setEditing(null); setFormOpen(true); }} data-testid="svt-add"><Plus size={14} /> Tambah Jenis Service</button>
  ) : null;

  if (loading) return <LoadingState testId="service-types-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="space-y-3" data-testid="service-types-manager">
      {rows.length === 0 ? (
        <div className="space-y-3">
          <div className="flex justify-end">{addBtn}</div>
          <EmptyState title="Belum ada jenis service custom" description="Tambahkan jenis service (mis. Ganti Oli, Ganti Ban) + interval default. Jenis bawaan (Servis/KIR/Pajak/Perbaikan) tetap tersedia." action={addBtn} testId="svt-empty" />
        </div>
      ) : (
        <DataTable title="Master Jenis Service" icon={Wrench} columns={columns} rows={rows}
          actions={addBtn} footer={`${formatQty(rows.length)} jenis service custom`} testId="svt-table" />
      )}
      <ServiceTypeFormDialog open={formOpen} onOpenChange={setFormOpen} initial={editing} onSaved={load} />
      <ConfirmDialog open={Boolean(delTarget)} onOpenChange={(v) => !v && setDelTarget(null)}
        title="Hapus jenis service?" description={delTarget ? `"${delTarget.name}" akan dihapus.` : ""}
        busy={busy} onConfirm={doDelete} testId="svt-del-confirm" />
    </div>
  );
}

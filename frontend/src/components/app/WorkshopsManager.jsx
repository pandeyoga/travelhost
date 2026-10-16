import { useCallback, useEffect, useMemo, useState } from "react";
import { Wrench, Plus, Pencil, Trash2, MapPin, Phone } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { useAuth } from "@/context/AuthContext";
import DataTable from "@/components/shared/DataTable";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { formatQty } from "@/utils/formatters";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import WorkshopFormDialog from "@/components/app/WorkshopFormDialog";

export default function WorkshopsManager() {
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
      const r = await apiClient.get("/workshops");
      setRows(Array.isArray(r.data) ? r.data : []);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat vendor/bengkel");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const doDelete = async () => {
    if (!delTarget) return; setBusy(true);
    try {
      await apiClient.delete(`/workshops/${delTarget.id}`);
      toast.success("Vendor/bengkel dihapus");
      setDelTarget(null); await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menghapus"); }
    finally { setBusy(false); }
  };

  const columns = useMemo(() => {
    const cols = [
      { key: "name", label: "Nama", render: (r) => <span className="font-semibold text-[#1C1C1E]">{r.name}</span> },
      { key: "city", label: "Lokasi", render: (r) => <span className="flex items-center gap-1 text-[12.5px] text-[#3A3A3C]"><MapPin size={13} className="text-[#8E8E93]" />{r.city || "—"}</span> },
      { key: "phone", label: "Telepon", render: (r) => r.phone ? <span className="flex items-center gap-1 tabular-nums text-[12.5px]"><Phone size={13} className="text-[#8E8E93]" />{r.phone}</span> : <span className="text-[#C7C7CC]">—</span> },
      { key: "specialties", label: "Spesialisasi", render: (r) => <div className="flex flex-wrap gap-1">{(r.specialties || []).map((s, i) => <span key={i} className="status-pill tone-neutral">{s}</span>)}</div> },
      { key: "active", label: "Status", render: (r) => <span className={`status-pill tone-${r.active ? "success" : "neutral"}`}>{r.active ? "Aktif" : "Nonaktif"}</span> },
    ];
    if (canManage) {
      cols.push({
        key: "aksi", label: "Aksi", align: "right",
        render: (r) => (
          <div className="flex justify-end gap-1.5">
            <button className="icon-button !h-8 !w-8" title="Edit" onClick={() => { setEditing(r); setFormOpen(true); }} data-testid={`wsh-edit-${r.id}`}><Pencil size={14} /></button>
            <button className="icon-button !h-8 !w-8 !text-[#A8221A]" title="Hapus" onClick={() => setDelTarget(r)} data-testid={`wsh-del-${r.id}`}><Trash2 size={14} /></button>
          </div>
        ),
      });
    }
    return cols;
  }, [canManage]);

  const addBtn = canManage ? (
    <button className="primary-button" onClick={() => { setEditing(null); setFormOpen(true); }} data-testid="wsh-add"><Plus size={14} /> Tambah Vendor/Bengkel</button>
  ) : null;

  if (loading) return <LoadingState testId="workshops-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="space-y-3" data-testid="workshops-manager">
      {rows.length === 0 ? (
        <div className="space-y-3">
          <div className="flex justify-end">{addBtn}</div>
          <EmptyState title="Belum ada vendor/bengkel" description="Daftarkan bengkel langganan untuk dipilih saat menjadwalkan perawatan." action={addBtn} testId="wsh-empty" />
        </div>
      ) : (
        <DataTable title="Master Vendor / Bengkel" icon={Wrench} columns={columns} rows={rows}
          actions={addBtn} footer={`${formatQty(rows.length)} vendor/bengkel`} testId="wsh-table" />
      )}
      <WorkshopFormDialog open={formOpen} onOpenChange={setFormOpen} initial={editing} onSaved={load} />
      <ConfirmDialog open={Boolean(delTarget)} onOpenChange={(v) => !v && setDelTarget(null)}
        title="Hapus vendor/bengkel?" description={delTarget ? `"${delTarget.name}" akan dihapus.` : ""}
        busy={busy} onConfirm={doDelete} testId="wsh-del-confirm" />
    </div>
  );
}

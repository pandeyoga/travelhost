import { useState } from "react";
import { Contact, Plus, Pencil, Trash2, Eye } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { useResource } from "@/hooks/useResource";
import DataTable from "@/components/shared/DataTable";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { StatusPill } from "@/components/shared/StatusPill";
import CustomerFormDialog from "@/components/app/CustomerFormDialog";
import CustomerDetailDialog from "@/components/app/CustomerDetailDialog";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import { formatCurrency, formatQty } from "@/utils/formatters";

export default function Customers() {
  const { data, loading, error, reload } = useResource("/customers");
  const rows = Array.isArray(data) ? data : [];
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [detailId, setDetailId] = useState(null);
  const [delTarget, setDelTarget] = useState(null);
  const [busy, setBusy] = useState(false);

  const openCreate = () => { setEditing(null); setFormOpen(true); };
  const openEdit = (r) => { setEditing(r); setFormOpen(true); };

  const doDelete = async () => {
    if (!delTarget) return;
    setBusy(true);
    try {
      await apiClient.delete(`/customers/${delTarget.id}`);
      toast.success("Customer dihapus");
      setDelTarget(null);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus customer");
    } finally { setBusy(false); }
  };

  const columns = [
    { key: "name", label: "Nama", render: (r) => <span className="font-semibold text-[#1C1C1E]">{r.name}</span> },
    { key: "type", label: "Segmen", render: (r) => <StatusPill value={r.type} tone={r.type === "corporate" ? "info" : "neutral"} /> },
    { key: "city", label: "Kota" },
    { key: "phone", label: "Telepon", mono: true },
    { key: "email", label: "Email", render: (r) => (
      r.email ? <span className="truncate" title={r.email}>{r.email}</span>
              : <span className="text-[#8E8E93]">—</span>
    ) },
    { key: "total_trips", label: "Total Trip", align: "right", mono: true, render: (r) => formatQty(r.total_trips) },
    { key: "lifetime_value", label: "Lifetime Value", align: "right", mono: true, render: (r) => <span className="tabular-nums">{formatCurrency(r.lifetime_value)}</span> },
    {
      key: "aksi", label: "Aksi", align: "right",
      render: (r) => (
        <div className="flex justify-end gap-1.5">
          <button className="icon-button !h-8 !w-8" onClick={(e) => { e.stopPropagation(); setDetailId(r.id); }} data-testid={`customer-view-${r.id}`}><Eye size={14} /></button>
          <button className="icon-button !h-8 !w-8" onClick={(e) => { e.stopPropagation(); openEdit(r); }} data-testid={`customer-edit-${r.id}`}><Pencil size={14} /></button>
          <button className="icon-button !h-8 !w-8 !text-[#A8221A]" onClick={(e) => { e.stopPropagation(); setDelTarget(r); }} data-testid={`customer-delete-${r.id}`}><Trash2 size={14} /></button>
        </div>
      ),
    },
  ];

  const addBtn = (
    <button className="primary-button" onClick={openCreate} data-testid="customers-add-button"><Plus size={14} /> Tambah Customer</button>
  );

  return (
    <div className="space-y-4" data-testid="customers-page">
      {loading ? (
        <LoadingState testId="customers-loading" />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : rows.length === 0 ? (
        <div className="space-y-3">
          <div className="flex justify-end">{addBtn}</div>
          <EmptyState title="Belum ada customer" description="Tambahkan pelanggan pertama Anda." action={addBtn} testId="customers-empty" />
        </div>
      ) : (
        <DataTable
          title="Customer 360" icon={Contact} columns={columns} rows={rows} actions={addBtn}
          onRowClick={(r) => setDetailId(r.id)} footer={`${formatQty(rows.length)} customer terdaftar · klik baris untuk detail`} testId="customers-table"
        />
      )}

      <CustomerFormDialog open={formOpen} onOpenChange={setFormOpen} initial={editing} onSaved={reload} />
      <CustomerDetailDialog open={Boolean(detailId)} onOpenChange={(v) => !v && setDetailId(null)} customerId={detailId} />
      <ConfirmDialog
        open={Boolean(delTarget)} onOpenChange={(v) => !v && setDelTarget(null)}
        title="Hapus customer?" description={delTarget ? `"${delTarget.name}" akan dihapus permanen.` : ""}
        busy={busy} onConfirm={doDelete} testId="customer-delete-confirm"
      />
    </div>
  );
}

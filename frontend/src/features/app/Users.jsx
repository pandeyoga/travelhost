import { useState } from "react";
import { toast } from "sonner";
import { UserCog, Plus, Pencil, Trash2 } from "lucide-react";
import apiClient from "@/services/apiClient";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/context/AuthContext";
import DataTable from "@/components/shared/DataTable";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { StatusPill } from "@/components/shared/StatusPill";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import UserFormDialog from "@/components/app/UserFormDialog";
import { formatDate } from "@/utils/formatters";

const ROLE_LABEL = { owner: "Pemilik", ops_admin: "Admin Operasional", marketing_admin: "Admin Marketing", driver: "Driver" };

export default function Users() {
  const { user: me } = useAuth();
  const { data, loading, error, reload } = useResource("/users");
  const rows = Array.isArray(data) ? data : [];
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [delTarget, setDelTarget] = useState(null);
  const [busy, setBusy] = useState(false);

  const openAdd = () => { setEditing(null); setFormOpen(true); };
  const openEdit = (r) => { setEditing(r); setFormOpen(true); };

  const doDelete = async () => {
    if (!delTarget) return;
    setBusy(true);
    try {
      await apiClient.delete(`/users/${delTarget.id}`);
      toast.success("User dihapus");
      setDelTarget(null);
      reload();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal menghapus user");
    } finally { setBusy(false); }
  };

  const columns = [
    { key: "name", label: "Nama", render: (r) => <span className="font-semibold text-[#1C1C1E]">{r.name}{me?.id === r.id ? <span className="ml-1.5 text-[11px] font-normal text-[#8E8E93]">(Anda)</span> : null}</span> },
    { key: "email", label: "Email", mono: true },
    { key: "role", label: "Peran", render: (r) => ROLE_LABEL[r.role] || r.role },
    { key: "phone", label: "Telepon", mono: true },
    { key: "status", label: "Status", render: (r) => <StatusPill value={r.status} tone={r.status === "active" ? "success" : "neutral"} /> },
    { key: "created_at", label: "Dibuat", render: (r) => formatDate(r.created_at) },
    {
      key: "actions", label: "", render: (r) => (
        <div className="flex items-center justify-end gap-1">
          <button className="icon-button !h-8 !w-8" title="Edit / reset sandi" onClick={(e) => { e.stopPropagation(); openEdit(r); }} data-testid={`user-edit-${r.id}`}><Pencil size={14} /></button>
          <button className="icon-button !h-8 !w-8 !text-[#A8221A] disabled:opacity-40" title="Hapus" disabled={me?.id === r.id}
            onClick={(e) => { e.stopPropagation(); setDelTarget(r); }} data-testid={`user-delete-${r.id}`}><Trash2 size={14} /></button>
        </div>
      ),
    },
  ];

  const AddButton = (
    <button className="primary-button" onClick={openAdd} data-testid="users-add-button"><Plus size={15} /> Tambah User</button>
  );

  if (loading) return <LoadingState testId="users-loading" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;

  return (
    <div data-testid="users-page">
      {rows.length === 0 ? (
        <EmptyState title="Belum ada user" description="Tambahkan akun pengguna baru." action={AddButton} testId="users-empty" />
      ) : (
        <DataTable title="Daftar User" icon={UserCog} actions={AddButton} columns={columns} rows={rows}
          footer={`${rows.length} user terdaftar`} testId="users-table" />
      )}
      <UserFormDialog open={formOpen} onOpenChange={setFormOpen} initial={editing} isSelf={Boolean(editing && me?.id === editing.id)} onSaved={reload} />
      <ConfirmDialog
        open={Boolean(delTarget)} onOpenChange={(v) => !v && setDelTarget(null)}
        title="Hapus user?" description={delTarget ? `"${delTarget.name}" (${delTarget.email}) akan dihapus permanen dan tidak bisa login lagi.` : ""}
        busy={busy} onConfirm={doDelete} testId="user-delete-confirm"
      />
    </div>
  );
}

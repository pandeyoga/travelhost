import { useMemo, useState } from "react";
import { Bus, Plus, Pencil, Trash2, BellRing, Eye } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/context/AuthContext";
import DataTable from "@/components/shared/DataTable";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { StatusPill } from "@/components/shared/StatusPill";
import VehicleFormDialog from "@/components/app/VehicleFormDialog";
import VehicleDetailDrawer from "@/components/app/VehicleDetailDrawer";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import { formatCurrency, formatDate, formatQty } from "@/utils/formatters";

const VEHICLE_TONE = { available: "success", maintenance: "warning", on_trip: "info" };
const DAY = 86400000;

function dueItems(v) {
  const now = Date.now();
  const horizon = now + 30 * DAY;
  const out = [];
  [["kir_expiry", "KIR"], ["tax_expiry", "Pajak"], ["next_service_date", "Servis"]].forEach(([f, l]) => {
    if (!v[f]) return;
    const t = new Date(v[f]).getTime();
    if (!Number.isNaN(t) && t <= horizon) out.push({ label: l, overdue: t < now, code: v.code, name: v.name });
  });
  return out;
}

const TYPE_LABEL = {
  hiace_premio: "Hiace Premio", hiace: "Hiace Commuter", elf: "Elf / Microbus",
  bus: "Bus Besar", avanza: "Avanza / MPV",
};

export default function Vehicles() {
  const { user } = useAuth();
  const { data, loading, error, reload } = useResource("/vehicles");
  const rows = Array.isArray(data) ? data : [];
  const canManage = user && (user.role === "owner" || user.role === "ops_admin");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [delTarget, setDelTarget] = useState(null);
  const [busy, setBusy] = useState(false);
  const [detail, setDetail] = useState(null);

  const reminders = useMemo(() => rows.flatMap(dueItems), [rows]);

  const openCreate = () => { setEditing(null); setFormOpen(true); };
  const openEdit = (r) => { setEditing(r); setFormOpen(true); };

  const doDelete = async () => {
    if (!delTarget) return;
    setBusy(true);
    try {
      await apiClient.delete(`/vehicles/${delTarget.id}`);
      toast.success("Armada dihapus");
      setDelTarget(null);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus armada");
    } finally { setBusy(false); }
  };

  // Kolom tabel WAJIB memuat data yang dipakai untuk mengambil keputusan atas unit itu.
  // Sebelumnya tabel hanya menampilkan kode/nama/plat/kapasitas/status/KIR/pajak — sehingga
  // tiga keputusan penting TIDAK terlihat sama sekali dan harus dibuka satu-satu:
  //   • tipe armada (menentukan tarif per tipe di Pengaturan),
  //   • tarif resmi per hari (yang benar-benar ditagihkan & ditampilkan di web),
  //   • status tayang web + kepemilikan (unit mitra tidak dijual online).
  const columns = [
    { key: "code", label: "Kode", mono: true, render: (r) => <span className="font-semibold text-[#1C1C1E]">{r.code}</span> },
    {
      key: "name",
      label: "Nama",
      render: (r) => (
        <div className="min-w-0">
          <span className="block truncate text-[#1C1C1E]" title={r.name}>{r.name}</span>
          {r.ownership === "partner" ? (
            <span className="block text-[11px] text-[#8E8E93]">
              Mitra{r.partner_name ? ` · ${r.partner_name}` : ""}
            </span>
          ) : null}
        </div>
      ),
    },
    { key: "plate_number", label: "Plat", mono: true },
    { key: "type", label: "Tipe", render: (r) => TYPE_LABEL[r.type] || r.type || "-" },
    { key: "capacity", label: "Kapasitas", align: "right", mono: true, render: (r) => `${formatQty(r.capacity)} pax` },
    {
      key: "day_rate",
      label: "Tarif/hari",
      align: "right",
      mono: true,
      render: (r) => (r.day_rate
        ? <span className="tabular-nums">{formatCurrency(r.day_rate)}</span>
        : <span className="text-[#8E8E93]" title="Belum ada tarif khusus unit — memakai tarif per tipe di Pengaturan">Tarif tipe</span>),
    },
    { key: "status", label: "Status", render: (r) => <StatusPill value={r.status} tone={VEHICLE_TONE[r.status] || "neutral"} /> },
    {
      key: "publish_to_web",
      label: "Web",
      render: (r) => (r.publish_to_web
        ? <span className="rounded-full bg-[#E8F7EC] px-2 py-0.5 text-[11px] font-semibold text-[#1B7F3B]">Tayang</span>
        : <span className="rounded-full bg-[#F2F2F5] px-2 py-0.5 text-[11px] font-semibold text-[#6B6B73]">Tidak</span>),
    },
    { key: "kir_expiry", label: "KIR", render: (r) => formatDate(r.kir_expiry) },
    { key: "tax_expiry", label: "Pajak", render: (r) => formatDate(r.tax_expiry) },
  ];
  if (canManage) {
    columns.push({
      key: "aksi", label: "Aksi", align: "right",
      render: (r) => (
        <div className="flex justify-end gap-1.5">
          <button className="icon-button !h-8 !w-8" title="Detail & riwayat trip" onClick={(e) => { e.stopPropagation(); setDetail(r); }} data-testid={`vehicle-detail-${r.id}`}><Eye size={14} /></button>
          <button className="icon-button !h-8 !w-8" onClick={(e) => { e.stopPropagation(); openEdit(r); }} data-testid={`vehicle-edit-${r.id}`}><Pencil size={14} /></button>
          <button className="icon-button !h-8 !w-8 !text-[#A8221A]" onClick={(e) => { e.stopPropagation(); setDelTarget(r); }} data-testid={`vehicle-delete-${r.id}`}><Trash2 size={14} /></button>
        </div>
      ),
    });
  } else {
    columns.push({
      key: "aksi", label: "", align: "right",
      render: (r) => (
        <button className="icon-button !h-8 !w-8" title="Detail & riwayat trip" onClick={(e) => { e.stopPropagation(); setDetail(r); }} data-testid={`vehicle-detail-${r.id}`}><Eye size={14} /></button>
      ),
    });
  }

  const addBtn = canManage ? (
    <button className="primary-button" onClick={openCreate} data-testid="vehicles-add-button"><Plus size={14} /> Tambah Armada</button>
  ) : null;

  return (
    <div className="space-y-4" data-testid="vehicles-page">
      {reminders.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2 rounded-[14px] border border-[#FFE6B0] bg-[#FFF8EC] px-4 py-3" data-testid="vehicles-reminders">
          <BellRing size={16} className="text-[#C25400]" />
          <span className="text-[13px] font-semibold text-[#8C4A00]">{formatQty(reminders.length)} dokumen armada perlu perhatian (≤ 30 hari):</span>
          <div className="flex flex-wrap gap-1.5">
            {reminders.slice(0, 8).map((d, i) => (
              <span key={i} className={`status-pill ${d.overdue ? "tone-danger" : "tone-warning"}`}>{d.code} · {d.label}</span>
            ))}
          </div>
        </div>
      ) : null}

      {loading ? (
        <LoadingState testId="vehicles-loading" />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : rows.length === 0 ? (
        <div className="space-y-3">
          <div className="flex justify-end">{addBtn}</div>
          <EmptyState title="Belum ada armada" description="Tambahkan kendaraan pertama Anda." action={addBtn} testId="vehicles-empty" />
        </div>
      ) : (
        <DataTable title="Armada" icon={Bus} columns={columns} rows={rows} actions={addBtn} onRowClick={setDetail} footer={`${formatQty(rows.length)} kendaraan terdaftar`} testId="vehicles-table" />
      )}

      <VehicleDetailDrawer open={Boolean(detail)} vehicle={detail} onOpenChange={(v) => !v && setDetail(null)} />
      <VehicleFormDialog open={formOpen} onOpenChange={setFormOpen} initial={editing} onSaved={reload} />
      <ConfirmDialog
        open={Boolean(delTarget)} onOpenChange={(v) => !v && setDelTarget(null)}
        title="Hapus armada?" description={delTarget ? `"${delTarget.name}" (${delTarget.plate_number}) akan dihapus permanen.` : ""}
        busy={busy} onConfirm={doDelete} testId="vehicle-delete-confirm"
      />
    </div>
  );
}

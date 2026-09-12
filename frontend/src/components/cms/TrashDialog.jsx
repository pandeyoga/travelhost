import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, RotateCcw, Trash2 } from "lucide-react";
import apiClient from "@/services/apiClient";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import { formatDateTime } from "@/utils/formatters";

const RESOURCE_LABEL = {
  destinations: "Destinasi", packages: "Paket", articles: "Artikel",
  testimonials: "Testimoni", promos: "Promo",
};

/** Sisa hari sebelum dibuang otomatis — informasi yang menentukan tindakan editor. */
function daysLeft(expiresAt) {
  const exp = Date.parse(String(expiresAt || ""));
  if (!exp) return null;
  return Math.ceil((exp - Date.now()) / 86400000);
}

/**
 * CMS-11 — Tempat Sampah konten.
 *
 * Hapus di CMS kini memindahkan konten ke sini (retensi 30 hari) alih-alih memusnahkannya.
 * Panel ini adalah jalan pulangnya: pulihkan (selalu kembali sebagai draft supaya tidak ada
 * halaman yang diam-diam tayang lagi) atau buang permanen secara sadar.
 */
export default function TrashDialog({ open, onOpenChange, resource = "", onChanged }) {
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState({ retention_days: 30 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState("");
  const [purgeItem, setPurgeItem] = useState(null);
  const [purging, setPurging] = useState(false);
  const [scope, setScope] = useState("tab");   // tab = hanya jenis konten aktif, all = semua

  const load = useCallback(() => {
    if (!open) return;
    setLoading(true);
    const params = { limit: 200 };
    if (scope === "tab" && resource) params.resource = resource;
    apiClient.get("/content/trash", { params })
      .then((r) => {
        setRows(Array.isArray(r.data?.rows) ? r.data.rows : []);
        setStats(r.data?.stats || { retention_days: 30 });
        setError(null);
      })
      .catch((e) => setError(e?.response?.data?.detail || "Gagal memuat tempat sampah"))
      .finally(() => setLoading(false));
  }, [open, resource, scope]);

  useEffect(() => { load(); }, [load]);

  const restore = async (row, rename = false) => {
    setBusyId(row.id);
    try {
      const { data } = await apiClient.post(`/content/trash/${row.id}/restore`,
        null, { params: rename ? { rename: true } : {} });
      const notes = (data.notes || []).join(" · ");
      toast.success(`“${row.label}” dipulihkan sebagai draft${notes ? ` — ${notes}` : ""}`);
      load();
      onChanged && onChanged();
    } catch (e) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail || "Gagal memulihkan";
      if (status === 409 && !rename) {
        // Bentrok slug: tawarkan jalan keluar yang jelas, jangan hanya menampilkan error.
        toast.error(detail, {
          duration: 12000,
          action: { label: "Pulihkan + ganti nama", onClick: () => restore(row, true) },
        });
      } else {
        toast.error(detail);
      }
    } finally { setBusyId(""); }
  };

  const purge = async () => {
    if (!purgeItem) return;
    setPurging(true);
    try {
      await apiClient.delete(`/content/trash/${purgeItem.id}`);
      toast.success(`“${purgeItem.label}” dibuang permanen`);
      setPurgeItem(null);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuang permanen");
    } finally { setPurging(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[90vh] max-w-3xl flex-col overflow-hidden" data-testid="content-trash-dialog">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            <Trash2 size={16} /> Tempat Sampah
            <span className="text-[12px] font-normal text-[#6B6B73]">
              konten terhapus disimpan {stats.retention_days || 30} hari
            </span>
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-wrap items-center gap-2 pb-1">
          <button className={`tab-button ${scope === "tab" ? "active" : ""}`} onClick={() => setScope("tab")}
            data-testid="trash-scope-tab">Jenis ini ({RESOURCE_LABEL[resource] || resource || "—"})</button>
          <button className={`tab-button ${scope === "all" ? "active" : ""}`} onClick={() => setScope("all")}
            data-testid="trash-scope-all">Semua jenis</button>
        </div>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto">
          {loading ? <LoadingState rows={3} testId="trash-loading" />
            : error ? <ErrorState message={error} onRetry={load} testId="trash-error" />
            : rows.length === 0 ? (
              <EmptyState title="Tempat sampah kosong" testId="trash-empty"
                description="Konten yang Anda hapus dari CMS muncul di sini dan masih bisa dipulihkan sebelum tenggat retensi." />
            ) : (
              <div className="section-card divide-y divide-[#F2F2F5]" data-testid="trash-list">
                {rows.map((row) => {
                  const left = daysLeft(row.expires_at);
                  return (
                    <div key={row.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                      data-testid={`trash-row-${row.id}`}>
                      <div className="min-w-0 flex-1">
                        <p className="flex flex-wrap items-center gap-2 text-[13px] font-bold text-[#1C1C1E]">
                          {row.label || "(tanpa judul)"}
                          <span className="status-pill tone-neutral">{RESOURCE_LABEL[row.resource] || row.resource}</span>
                          {row.expired ? <span className="status-pill tone-warning"><AlertTriangle size={10} /> Lewat tenggat</span> : null}
                        </p>
                        <p className="truncate text-[11.5px] tabular-nums text-[#6B6B73]">
                          {row.slug ? `${row.slug} · ` : ""}dihapus {formatDateTime(row.deleted_at)}
                          {row.deleted_by_name ? ` oleh ${row.deleted_by_name}` : ""}
                          {left !== null ? ` · ${left > 0 ? `sisa ${left} hari` : "akan dibuang otomatis"}` : ""}
                        </p>
                      </div>
                      <div className="flex flex-shrink-0 items-center gap-1.5">
                        <button className="secondary-button !h-8 !px-2.5 !text-[11.5px]" disabled={busyId === row.id}
                          onClick={() => restore(row)} data-testid={`trash-restore-${row.id}`}>
                          <RotateCcw size={12} /> Pulihkan
                        </button>
                        <button className="icon-button !h-8 !w-8 !text-[#A8221A]" title="Buang permanen"
                          onClick={() => setPurgeItem(row)} data-testid={`trash-purge-${row.id}`}>
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

          <p className="rounded-[12px] border border-[#E5E5EA] bg-[#F7F8FA] px-3 py-2.5 text-[11.5px] leading-relaxed text-[#6B6B73]">
            Konten yang dipulihkan kembali sebagai <span className="font-semibold text-[#1C1C1E]">draft</span> —
            periksa dulu, lalu tayangkan dari tab Terbit. Bila slug-nya sudah dipakai konten lain, sistem
            menolak menimpa dan menawarkan penggantian nama otomatis. Setelah {stats.retention_days || 30} hari,
            isi tempat sampah dibuang permanen oleh penjadwal.
          </p>
        </div>

        <ConfirmDialog open={Boolean(purgeItem)} onOpenChange={(v) => !v && setPurgeItem(null)} busy={purging}
          title="Buang permanen?"
          description={`“${purgeItem?.label || ""}” akan hilang untuk selamanya beserta riwayat versinya. Tindakan ini tidak bisa dibatalkan.`}
          confirmLabel="Buang permanen" onConfirm={purge} testId="trash-confirm-purge" />
      </DialogContent>
    </Dialog>
  );
}

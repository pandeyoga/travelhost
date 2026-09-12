import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { History, Loader2, RotateCcw, Undo2, User } from "lucide-react";
import apiClient from "@/services/apiClient";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import { formatDateTime } from "@/utils/formatters";

const ACTION_LABEL = {
  create: { label: "Dibuat", tone: "tone-info" },
  update: { label: "Disunting", tone: "tone-neutral" },
  restore: { label: "Dipulihkan", tone: "tone-warning" },
};

/** Potongan isi agar editor bisa mengenali versi tanpa membuka satu per satu. */
function previewOf(snap) {
  const raw = String(snap?.excerpt || snap?.description || snap?.quote || snap?.body || "");
  const text = raw.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  return text.length > 180 ? `${text.slice(0, 180)}…` : text;
}

/**
 * CMS-10 — Riwayat versi & pemulihan satu konten.
 *
 * Kenapa penting: sebelum ini satu kali salah tempel (atau menghapus separuh isi lalu
 * menyimpan) berarti isi lama hilang selamanya. Sekarang setiap penyimpanan punya jejak,
 * bisa dibaca, dan bisa dikembalikan — tanpa menyentuh status terbit halaman.
 */
export default function VersionHistoryDialog({ resource, item, open, onOpenChange, onRestored }) {
  const [rows, setRows] = useState([]);
  const [maxVersions, setMaxVersions] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [detail, setDetail] = useState(null);      // versi yang dibuka
  const [detailBusy, setDetailBusy] = useState(false);
  const [confirm, setConfirm] = useState(null);    // versi yang akan dipulihkan
  const [busy, setBusy] = useState(false);

  const itemId = item?.id || "";

  const load = useCallback(() => {
    if (!open || !itemId) return;
    setLoading(true);
    apiClient.get(`/content/${resource}/${itemId}/versions`, { params: { limit: 100 } })
      .then((r) => {
        setRows(Array.isArray(r.data?.rows) ? r.data.rows : []);
        setMaxVersions(Number(r.data?.max_versions || 0));
        setError(null);
      })
      .catch((e) => setError(e?.response?.data?.detail || "Gagal memuat riwayat versi"))
      .finally(() => setLoading(false));
  }, [open, resource, itemId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (!open) { setDetail(null); setConfirm(null); } }, [open]);

  const openDetail = async (row) => {
    setDetailBusy(true);
    try {
      const { data } = await apiClient.get(`/content/${resource}/${itemId}/versions/${row.id}`);
      setDetail({ ...(data.version || {}), changed_vs_current: data.changed_vs_current || [] });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuka versi");
    } finally { setDetailBusy(false); }
  };

  const doRestore = async () => {
    if (!confirm) return;
    setBusy(true);
    try {
      const { data } = await apiClient.post(
        `/content/${resource}/${itemId}/versions/${confirm.id}/restore`);
      toast.success(`Isi dipulihkan ke versi ${data.restored_from} (${(data.fields || []).length} field)`);
      setConfirm(null);
      setDetail(null);
      load();
      onRestored && onRestored();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memulihkan versi");
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[90vh] max-w-3xl flex-col overflow-hidden" data-testid="version-history-dialog">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            <History size={16} /> Riwayat versi
            <span className="text-[12px] font-normal text-[#6B6B73]">
              {item?.title || item?.name || item?.code || itemId}
            </span>
          </DialogTitle>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto">
          {loading ? <LoadingState rows={3} testId="version-loading" />
            : error ? <ErrorState message={error} onRetry={load} testId="version-error" />
            : rows.length === 0 ? (
              <EmptyState title="Belum ada riwayat versi" testId="version-empty"
                description="Riwayat mulai terisi pada penyimpanan berikutnya. Konten yang dibuat sebelum fitur ini ada belum punya jejak versi." />
            ) : (
              <div className="section-card divide-y divide-[#F2F2F5]" data-testid="version-list">
                {rows.map((row, idx) => {
                  const meta = ACTION_LABEL[row.action] || ACTION_LABEL.update;
                  const changed = row.changed_fields || [];
                  return (
                    <div key={row.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                      data-testid={`version-row-${row.version}`}>
                      <div className="min-w-0 flex-1">
                        <p className="flex flex-wrap items-center gap-2 text-[13px] font-bold text-[#1C1C1E]">
                          Versi {row.version}
                          <span className={`status-pill ${meta.tone}`}>{meta.label}</span>
                          {idx === 0 ? <span className="status-pill tone-success">Isi sekarang</span> : null}
                        </p>
                        <p className="truncate text-[11.5px] text-[#6B6B73]">
                          {formatDateTime(row.created_at)} · <User size={10} className="inline" /> {row.actor_name || "sistem"}
                          {changed.length ? ` · ubah: ${changed.slice(0, 4).join(", ")}${changed.length > 4 ? `, +${changed.length - 4}` : ""}` : ""}
                        </p>
                      </div>
                      <div className="flex flex-shrink-0 items-center gap-1.5">
                        <button className="secondary-button !h-8 !px-2.5 !text-[11.5px]" onClick={() => openDetail(row)}
                          disabled={detailBusy} data-testid={`version-open-${row.version}`}>Lihat isi</button>
                        {idx === 0 ? null : (
                          <button className="secondary-button !h-8 !px-2.5 !text-[11.5px]" onClick={() => setConfirm(row)}
                            data-testid={`version-restore-${row.version}`}>
                            <RotateCcw size={12} /> Pulihkan
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

          {detail ? (
            <section className="section-card" data-testid="version-detail">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#F2F2F5] px-4 py-2.5">
                <p className="text-[12.5px] font-bold text-[#1C1C1E]">
                  Isi versi {detail.version}
                  {detail.changed_vs_current?.length
                    ? <span className="ml-2 text-[11px] font-normal text-[#8A5A00]">
                        berbeda dari isi sekarang pada {detail.changed_vs_current.length} field
                      </span>
                    : <span className="ml-2 text-[11px] font-normal text-[#0A7A34]">sama dengan isi sekarang</span>}
                </p>
                <button className="secondary-button !h-7 !px-2 !text-[11px]" onClick={() => setDetail(null)}
                  data-testid="version-detail-close">Tutup</button>
              </div>
              <div className="space-y-2 px-4 py-3">
                <p className="text-[12px] font-semibold text-[#1C1C1E]">{detail.snapshot?.title || detail.snapshot?.name || detail.snapshot?.code || "(tanpa judul)"}</p>
                <p className="whitespace-pre-wrap text-[12px] leading-relaxed text-[#3A3A3C]" data-testid="version-detail-preview">
                  {previewOf(detail.snapshot) || "(tidak ada teks untuk dipratinjau)"}
                </p>
                {detail.changed_vs_current?.length ? (
                  <p className="text-[11px] text-[#6B6B73]">
                    Field berbeda: <span className="font-semibold text-[#1C1C1E]">{detail.changed_vs_current.join(", ")}</span>
                  </p>
                ) : null}
              </div>
            </section>
          ) : null}

          <p className="rounded-[12px] border border-[#E5E5EA] bg-[#F7F8FA] px-3 py-2.5 text-[11.5px] leading-relaxed text-[#6B6B73]">
            Memulihkan versi lama <span className="font-semibold text-[#1C1C1E]">tidak menghapus</span> isi sekarang:
            isi sekarang tetap tersimpan sebagai versi tersendiri, jadi pemulihan pun bisa dibatalkan.
            Status terbit (draft/terjadwal/tayang) <span className="font-semibold text-[#1C1C1E]">tidak ikut berubah</span>.
            {maxVersions ? ` Sistem menyimpan ${maxVersions} versi terakhir per konten.` : ""}
          </p>
        </div>

        <ConfirmDialog open={Boolean(confirm)} onOpenChange={(v) => !v && setConfirm(null)} busy={busy}
          title={`Pulihkan ke versi ${confirm?.version || ""}?`}
          description="Isi konten akan diganti dengan isi versi tersebut. Isi sekarang tetap tersimpan sebagai versi baru sehingga bisa dikembalikan lagi."
          confirmLabel="Pulihkan" onConfirm={doRestore} testId="version-confirm-restore" />
      </DialogContent>
    </Dialog>
  );
}

export function RestoreHint() {
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-[#6B6B73]">
      <Undo2 size={11} /> bisa dipulihkan
    </span>
  );
}

export function VersionBusy() {
  return <Loader2 size={13} className="animate-spin" />;
}

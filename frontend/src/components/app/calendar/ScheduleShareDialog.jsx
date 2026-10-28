// ScheduleShareDialog.jsx — kelola share-link jadwal keberangkatan dari Kalender (owner/ops).
// Penerima membuka /schedule/:token TANPA login: hanya bisa melihat jadwal & detail (read-only).
import { useCallback, useEffect, useState } from "react";
import { Ban, CalendarRange, Clock, Copy, ExternalLink, Eye, Link2, Share2, Trash2 } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import { formatDateTime, formatQty } from "@/utils/formatters";
import ScheduleShareForm from "./ScheduleShareForm";

export const scheduleShareUrl = (token) => `${window.location.origin}/schedule/${token}`;

function StatePill({ s }) {
  if (s.revoked) return <span className="status-pill tone-neutral">Dinonaktifkan</span>;
  if (s.expired) return <span className="status-pill tone-danger">Kedaluwarsa</span>;
  return <span className="status-pill tone-success">Aktif</span>;
}

export default function ScheduleShareDialog({ open, onOpenChange, defaultMonth, vehicles = [] }) {
  const [shares, setShares] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [toDelete, setToDelete] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(false);
    try {
      const r = await apiClient.get("/schedule-shares");
      setShares(Array.isArray(r.data) ? r.data : []);
    } catch { setShares([]); setError(true); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { if (open) load(); }, [open, load]);

  const copy = async (token) => {
    const url = scheduleShareUrl(token);
    try { await navigator.clipboard.writeText(url); toast.success("Tautan disalin ke clipboard"); }
    catch { toast.message(url); }
  };
  const onCreated = (s) => { load(); if (s?.token) copy(s.token); };
  const revoke = async (s) => {
    try { await apiClient.post(`/schedule-shares/${s.id}/revoke`, {}); toast.success("Tautan dinonaktifkan"); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Gagal menonaktifkan"); }
  };
  const remove = async () => {
    if (!toDelete) return;
    setBusy(true);
    try { await apiClient.delete(`/schedule-shares/${toDelete.id}`); toast.success("Tautan dihapus"); setToDelete(null); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Gagal menghapus"); }
    finally { setBusy(false); }
  };
  const vehicleName = (id) => (vehicles.find((v) => v.id === id) || {}).name || id;

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[640px]" data-testid="dshare-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Share2 size={17} className="text-[#007AFF]" /> Bagikan Jadwal Keberangkatan</DialogTitle>
            <DialogDescription>
              Tautan bisa dibuka tanpa login. Penerima hanya melihat jadwal &amp; detailnya — tidak bisa mengubah apa pun.
              Isinya selalu mengikuti data terbaru dan tautan bisa dinonaktifkan kapan saja.
            </DialogDescription>
          </DialogHeader>

          <ScheduleShareForm defaultMonth={defaultMonth} vehicles={vehicles} onCreated={onCreated} />

          <div className="space-y-2" data-testid="dshare-list-wrap">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-[#9A9AA0]">Tautan yang sudah dibuat</p>
            {loading ? (
              <p className="py-5 text-center text-[12px] text-[#8E8E93]" data-testid="dshare-loading">Memuat tautan…</p>
            ) : error ? (
              <div className="flex items-center justify-between rounded-xl border border-[#FFD0CC] bg-[#FFF5F4] px-3 py-2.5 text-[12.5px] text-[#A8221A]" data-testid="dshare-error">
                Gagal memuat daftar tautan.
                <button className="secondary-button !h-8" onClick={load} data-testid="dshare-retry">Coba lagi</button>
              </div>
            ) : shares.length === 0 ? (
              <p className="rounded-xl border border-dashed border-[#E5E5EA] py-5 text-center text-[12px] text-[#8E8E93]" data-testid="dshare-empty">
                Belum ada tautan jadwal.
              </p>
            ) : (
              <ul className="divide-y divide-[#F2F2F5] rounded-xl border border-[#EFF0F2]" data-testid="dshare-list">
                {shares.map((s) => (
                  <li key={s.id} className="flex flex-col gap-2 px-3.5 py-3" data-testid={`dshare-item-${s.id}`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <Link2 size={14} className="text-[#007AFF]" />
                      <span className="min-w-0 truncate text-[13px] font-semibold text-[#1C1C1E]">{s.label}</span>
                      <StatePill s={s} />
                    </div>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px] text-[#6B6B73]">
                      <span className="inline-flex items-center gap-1"><CalendarRange size={11} /> {s.period_label}</span>
                      <span data-testid={`dshare-count-${s.id}`}>{formatQty(s.departure_count || 0)} keberangkatan</span>
                      <span>{s.vehicle_ids?.length ? s.vehicle_ids.map(vehicleName).join(", ") : "Semua armada"}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[#8E8E93]">
                      <span className="inline-flex items-center gap-1"><Clock size={11} /> {s.expires_at ? `Berlaku s/d ${formatDateTime(s.expires_at)}` : "Tanpa batas waktu"}</span>
                      <span className="inline-flex items-center gap-1"><Eye size={11} /> {formatQty(s.access_count || 0)}× dibuka</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      <button className="secondary-button !h-8" onClick={() => copy(s.token)} data-testid={`dshare-copy-${s.id}`}><Copy size={13} /> Salin</button>
                      {s.is_active ? (
                        <a className="secondary-button !h-8" href={scheduleShareUrl(s.token)} target="_blank" rel="noopener noreferrer" data-testid={`dshare-open-${s.id}`}>
                          <ExternalLink size={13} /> Buka
                        </a>
                      ) : null}
                      {!s.revoked ? (
                        <button className="secondary-button !h-8 !text-[#C25400]" onClick={() => revoke(s)} data-testid={`dshare-revoke-${s.id}`}><Ban size={13} /> Nonaktifkan</button>
                      ) : null}
                      <button className="icon-button !h-8 !w-8 !text-[#A8221A]" title="Hapus" aria-label="Hapus tautan"
                        onClick={() => setToDelete(s)} data-testid={`dshare-delete-${s.id}`}><Trash2 size={14} /></button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </DialogContent>
      </Dialog>
      <ConfirmDialog open={Boolean(toDelete)} onOpenChange={(v) => !v && setToDelete(null)} busy={busy} onConfirm={remove}
        title="Hapus tautan jadwal?" testId="dshare-delete-confirm"
        description={`Tautan "${toDelete?.label || ""}" akan berhenti berfungsi untuk semua penerima dan tidak bisa dipulihkan.`} />
    </>
  );
}

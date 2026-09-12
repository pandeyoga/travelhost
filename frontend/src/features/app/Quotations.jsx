import { useCallback, useEffect, useState } from "react";
import { FileText, Plus, Eye, ShieldAlert, Trash2 } from "lucide-react";
import { toast } from "sonner";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import apiClient from "@/services/apiClient";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { formatCurrency, formatDate } from "@/utils/formatters";
import QuotationFormDialog from "@/components/app/QuotationFormDialog";
import QuotationDetailDialog, { QUO } from "@/components/app/QuotationDetailDialog";

const FILTERS = [
  ["all", "Semua"], ["draft", "Draft"], ["sent", "Terkirim"],
  ["accepted", "Diterima"], ["converted", "Jadi Booking"], ["rejected", "Ditolak"],
];

// Halaman Penawaran (Quotation Lifecycle · B2). Funnel: lead → penawaran → booking.
export default function Quotations() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [denied, setDenied] = useState(false);
  const [filter, setFilter] = useState("all");
  const [formOpen, setFormOpen] = useState(false);
  const [detailId, setDetailId] = useState(null);
  const [delTarget, setDelTarget] = useState(null);
  const [busy, setBusy] = useState(false);
  const canDelete = (q) => ["draft", "sent", "rejected", "expired"].includes(q.status) && !q.booking_id;
  const doDelete = async () => {
    if (!delTarget) return;
    setBusy(true);
    try { await apiClient.delete(`/quotations/${delTarget.id}`); toast.success("Penawaran dihapus"); setDelTarget(null); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Gagal menghapus penawaran"); }
    finally { setBusy(false); }
  };

  const load = useCallback(() => {
    setLoading(true);
    const qs = filter === "all" ? "" : `?status=${filter}`;
    apiClient.get(`/quotations${qs}`)
      .then((r) => { setRows(Array.isArray(r.data) ? r.data : []); setError(null); setDenied(false); })
      .catch((e) => { if (e?.response?.status === 403) setDenied(true); else setError("Gagal memuat penawaran"); })
      .finally(() => setLoading(false));
  }, [filter]);
  useEffect(() => { load(); }, [load]);

  const addBtn = (
    <button className="primary-button" onClick={() => setFormOpen(true)} data-testid="quotation-add"><Plus size={14} /> Penawaran Baru</button>
  );

  if (denied) {
    return (
      <div className="flex flex-col items-center rounded-[14px] border border-[#FFE0DC] bg-[#FFF5F4] px-6 py-16 text-center" data-testid="quotations-denied">
        <ShieldAlert size={28} className="mb-3 text-[#FF3B30]" />
        <h3 className="text-base font-bold text-[#1C1C1E]">Akses terbatas</h3>
        <p className="mt-1 max-w-sm text-sm text-[#6B6B73]">Halaman Penawaran hanya dapat diakses oleh Pemilik & Admin Operasional.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="quotations-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="tab-bar">
          {FILTERS.map(([k, l]) => (
            <button key={k} className={`tab-button ${filter === k ? "active" : ""}`} onClick={() => setFilter(k)} data-testid={`quo-filter-${k}`}>{l}</button>
          ))}
        </div>
        {addBtn}
      </div>

      {loading ? <LoadingState testId="quotations-loading" />
        : error ? <ErrorState message={error} onRetry={load} />
        : rows.length === 0 ? <EmptyState title="Belum ada penawaran" description="Buat penawaran dari lead atau secara manual." testId="quotations-empty" action={addBtn} />
        : (
          <section className="section-card">
            <div className="section-head"><div className="flex items-center gap-2"><FileText size={16} className="text-[#007AFF]" /><h2>Daftar Penawaran</h2></div></div>
            <div className="divide-y divide-[#F2F2F5]" data-testid="quotations-list">
              {rows.map((q) => {
                const st = QUO[q.status] || { l: q.status, tone: "neutral" };
                return (
                  <div key={q.id} role="button" tabIndex={0} onClick={() => setDetailId(q.id)} onKeyDown={(e) => e.key === "Enter" && setDetailId(q.id)} className="flex w-full cursor-pointer flex-wrap items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-[#FAFAFB]" data-testid={`quotation-${q.id}`}>
                    <div className="min-w-0">
                      <p className="flex items-center gap-2 text-[13px] font-bold text-[#1C1C1E]">{q.number} <span className={`status-pill tone-${st.tone}`}>{st.l}</span></p>
                      <p className="truncate text-[11.5px] text-[#6B6B73]">{q.customer_name} · {q.destination || "?"} · {formatDate(q.trip_date)}</p>
                    </div>
                    <div className="flex flex-shrink-0 items-center gap-3">
                      <span className="text-[14px] font-bold tabular-nums text-[#1C1C1E]">{formatCurrency(q.total)}</span>
                      <Eye size={15} className="text-[#8E8E93]" />
                      {canDelete(q) ? <button className="icon-button !h-8 !w-8 !text-[#A8221A]" title="Hapus" onClick={(e) => { e.stopPropagation(); setDelTarget(q); }} data-testid={`quotation-delete-${q.id}`}><Trash2 size={14} /></button> : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

      <QuotationFormDialog open={formOpen} onOpenChange={setFormOpen} onSaved={(d) => { load(); if (d?.id) setDetailId(d.id); }} />
      <QuotationDetailDialog quotationId={detailId} open={Boolean(detailId)} onOpenChange={(v) => !v && setDetailId(null)} onChanged={load} />
      <ConfirmDialog open={Boolean(delTarget)} onOpenChange={(v) => !v && setDelTarget(null)} title="Hapus penawaran?"
        description={delTarget ? `Penawaran ${delTarget.number} untuk "${delTarget.customer_name}" akan dihapus permanen.` : ""}
        busy={busy} onConfirm={doDelete} testId="quotation-delete-confirm-list" />
    </div>
  );
}

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { RefreshCw, GitCompareArrows, Loader2, CheckCircle2, AlertTriangle } from "lucide-react";
import apiClient from "@/services/apiClient";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { formatCurrency } from "@/utils/formatters";

const RECON = {
  lunas: { l: "Lunas", tone: "success" },
  sebagian: { l: "Sebagian", tone: "warning" },
  belum: { l: "Belum Bayar", tone: "danger" },
  lebih: { l: "Lebih Bayar", tone: "info" },
};

// FinanceReconciliation — E5 (G5): bandingkan invoice vs pembayaran booking + sinkronkan status.
export default function FinanceReconciliation({ onChanged }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/finance/reconciliation")
      .then((r) => { setData(r.data); setError(null); })
      .catch(() => setError("Gagal memuat rekonsiliasi"))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const sync = async () => {
    setSyncing(true);
    try {
      const r = await apiClient.post("/finance/reconciliation/sync");
      const n = r.data?.updated_count ?? 0;
      toast.success(n > 0 ? `${n} status invoice diselaraskan` : "Status invoice sudah selaras");
      load();
      onChanged && onChanged();
    } catch (e) {
      toast.error("Gagal menyinkronkan status");
    } finally { setSyncing(false); }
  };

  if (loading) return <LoadingState rows={3} testId="recon-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  const items = data?.items || [];
  const s = data?.summary || {};

  return (
    <div className="space-y-3" data-testid="reconcile-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2" data-testid="recon-summary">
          <Chip tone="success" icon={CheckCircle2} label="Lunas" value={s.lunas} />
          <Chip tone="warning" label="Sebagian" value={s.sebagian} />
          <Chip tone="danger" icon={AlertTriangle} label="Belum" value={s.belum} />
          <Chip tone="info" label="Lebih" value={s.lebih} />
        </div>
        <button className="primary-button" disabled={syncing} onClick={sync} data-testid="recon-sync">
          {syncing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} Sinkronkan Status
        </button>
      </div>

      <div className="flex items-center justify-between rounded-[12px] bg-[#FAFAFB] px-4 py-2.5 text-[12.5px]">
        <span className="text-[#6B6B73]">Total ditagih <b className="tabular-nums text-[#1C1C1E]">{formatCurrency(s.total_invoiced)}</b></span>
        <span className="text-[#6B6B73]">Total terbayar <b className="tabular-nums text-[#127A36]">{formatCurrency(s.total_paid)}</b></span>
        <span className="text-[#6B6B73]">Selisih <b className="tabular-nums text-[#C0271E]">{formatCurrency((s.total_invoiced || 0) - (s.total_paid || 0))}</b></span>
      </div>

      {items.length === 0 ? (
        <EmptyState title="Belum ada invoice" description="Terbitkan invoice untuk direkonsiliasi." testId="recon-empty" />
      ) : (
        <section className="section-card">
          <div className="section-head"><div className="flex items-center gap-2"><GitCompareArrows size={16} className="text-[#5856D6]" /><h2>Rekonsiliasi Invoice ↔ Pembayaran</h2></div></div>
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead><tr className="border-b border-[#EFF0F2] text-left text-[10.5px] uppercase tracking-wide text-[#8E8E93]">
                <th className="px-4 py-2.5">Invoice</th><th className="px-3 py-2.5">Pelanggan</th>
                <th className="px-3 py-2.5 text-right">Ditagih</th><th className="px-3 py-2.5 text-right">Terbayar</th>
                <th className="px-3 py-2.5 text-right">Selisih</th><th className="px-3 py-2.5">Status</th></tr></thead>
              <tbody data-testid="recon-list">
                {items.map((i) => {
                  const st = RECON[i.recon_status] || { l: i.recon_status, tone: "neutral" };
                  return (
                    <tr key={i.invoice_id} className="border-b border-[#F6F6F8] hover:bg-[#FAFAFB]" data-testid={`recon-row-${i.invoice_id}`}>
                      <td className="px-4 py-3"><div className="font-bold text-[#1C1C1E]">{i.number}</div><div className="text-[11px] text-[#6B6B73]">{i.booking_code}</div></td>
                      <td className="px-3 py-3 text-[#3C3C43]">{i.customer_name || "-"}</td>
                      <td className="px-3 py-3 text-right tabular-nums">{formatCurrency(i.invoice_amount)}</td>
                      <td className="px-3 py-3 text-right tabular-nums text-[#127A36]">{formatCurrency(i.paid)}</td>
                      <td className="px-3 py-3 text-right tabular-nums font-semibold" style={{ color: i.diff < 0 ? "#C0271E" : i.diff > 0 ? "#0058CC" : "#127A36" }}>{formatCurrency(i.diff)}</td>
                      <td className="px-3 py-3"><span className={`status-pill tone-${st.tone}`}>{st.l}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

function Chip({ tone, icon: Icon, label, value }) {
  return (
    <span className={`status-pill tone-${tone}`} data-testid={`recon-chip-${label}`}>
      {Icon ? <Icon size={11} /> : null} {label}: <b className="tabular-nums">{value ?? 0}</b>
    </span>
  );
}

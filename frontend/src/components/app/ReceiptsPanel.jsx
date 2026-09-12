import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Download, Eye, Loader2, ReceiptText, Send } from "lucide-react";
import apiClient from "@/services/apiClient";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { formatCurrency, formatDate } from "@/utils/formatters";

const TYPE = { dp: "DP", settlement: "Pelunasan", full: "Penuh" };

export async function openPdf(url) {
  try {
    const res = await apiClient.get(url, { responseType: "blob" });
    window.open(window.URL.createObjectURL(res.data), "_blank", "noopener");
  } catch (e) { toast.error("Gagal membuka PDF"); }
}

export async function downloadPdf(url, filename) {
  try {
    const res = await apiClient.get(url, { responseType: "blob" });
    const a = document.createElement("a");
    a.href = window.URL.createObjectURL(res.data); a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  } catch (e) { toast.error("Gagal mengunduh PDF"); }
}

export default function ReceiptsPanel() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/receipts").then((r) => { setRows(Array.isArray(r.data) ? r.data : []); setError(null); })
      .catch(() => setError("Gagal memuat pembayaran")).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const issue = async (id) => {
    setBusy(id);
    try { const r = await apiClient.post(`/payments/${id}/receipt`); toast.success(`Kwitansi ${r.data.receipt_no} diterbitkan`); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Gagal menerbitkan kwitansi"); }
    finally { setBusy(""); }
  };
  const sendWa = async (id) => {
    setBusy(`wa-${id}`);
    try { const r = await apiClient.post(`/payments/${id}/receipt/send-wa`); toast.success(`Kwitansi ${r.data.number} terkirim via WhatsApp`); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Gagal mengirim kwitansi"); }
    finally { setBusy(""); }
  };

  if (loading) return <LoadingState testId="receipts-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (rows.length === 0) return <EmptyState title="Belum ada pembayaran" description="Kwitansi diterbitkan dari pembayaran yang tercatat (tab Piutang › Bayar)." testId="receipts-empty" />;

  return (
    <section className="section-card" data-testid="receipts-panel">
      <div className="section-head"><div className="flex items-center gap-2"><ReceiptText size={16} className="text-[#34C759]" /><h2>Kwitansi Pembayaran</h2></div></div>
      <div className="divide-y divide-[#F2F2F5]" data-testid="receipts-list">
        {rows.map((p) => (
          <div key={p.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3" data-testid={`receipt-${p.id}`}>
            <div className="min-w-0">
              <p className="flex items-center gap-2 text-[13px] font-bold text-[#1C1C1E]">
                {p.receipt_no ? <span className="font-mono" data-testid={`receipt-no-${p.id}`}>{p.receipt_no}</span> : <span className="text-[#8E8E93]">Belum ada kwitansi</span>}
                <span className={`status-pill ${p.type === "dp" ? "tone-warning" : "tone-success"}`}>{TYPE[p.type] || p.type}</span>
              </p>
              <p className="truncate text-[11.5px] text-[#6B6B73]">{p.customer_name} · {p.booking_code} · {p.method} · {formatDate(p.paid_at)}</p>
            </div>
            <div className="flex flex-shrink-0 items-center gap-2">
              <span className="text-[14px] font-bold tabular-nums text-[#126E2C]">{formatCurrency(p.amount)}</span>
              {!p.receipt_no ? (
                <button className="primary-button !h-8" disabled={busy === p.id} onClick={() => issue(p.id)} data-testid={`receipt-issue-${p.id}`}>{busy === p.id ? <Loader2 size={13} className="animate-spin" /> : <ReceiptText size={13} />} Terbitkan</button>
              ) : (
                <>
                  <button className="icon-button !h-8 !w-8" title="Lihat PDF" onClick={() => openPdf(`/payments/${p.id}/receipt/pdf`)} data-testid={`receipt-view-${p.id}`}><Eye size={14} /></button>
                  <button className="icon-button !h-8 !w-8" title="Unduh PDF" onClick={() => downloadPdf(`/payments/${p.id}/receipt/pdf?download=true`, `${p.receipt_no.replaceAll("/", "-")}.pdf`)} data-testid={`receipt-pdf-${p.id}`}><Download size={14} /></button>
                  <button className="icon-button !h-8 !w-8 !text-[#127A36]" title="Kirim via WhatsApp" disabled={busy === `wa-${p.id}`} onClick={() => sendWa(p.id)} data-testid={`receipt-wa-${p.id}`}>{busy === `wa-${p.id}` ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}</button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

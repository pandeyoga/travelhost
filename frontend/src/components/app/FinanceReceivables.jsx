// FinanceReceivables.jsx — tab "Piutang" Keuangan (dipisah dari features/app/Finance.jsx agar
// halaman < 500 baris): daftar AR + usia tagihan + reminder WA (satuan & massal) + catat bayar.
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { BellRing, Loader2, Send, Wallet } from "lucide-react";
import apiClient from "@/services/apiClient";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { PaymentPill } from "@/components/shared/StatusPill";
import PaymentDialog from "@/components/app/PaymentDialog";
import { formatCurrency, formatDate } from "@/utils/formatters";

function daysSince(value) {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return Math.floor((Date.now() - d.getTime()) / 86400000);
}

export default function Receivables({ onChanged }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [payBooking, setPayBooking] = useState(null);
  const [remindingAll, setRemindingAll] = useState(false);
  const [remindingId, setRemindingId] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/finance/ar")
      .then((r) => { setData(r.data); setError(null); })
      .catch(() => setError("Gagal memuat piutang"))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const remindOne = async (bookingId) => {
    setRemindingId(bookingId);
    try {
      const r = await apiClient.post(`/finance/ar/${bookingId}/remind`);
      toast.success(r.data?.sent ? `Reminder WA terkirim ke ${r.data.customer_name || "pelanggan"}` : "Reminder diproses");
    } catch (e) {
      toast.error("Gagal mengirim reminder");
    } finally { setRemindingId(""); }
  };

  const remindAll = async () => {
    setRemindingAll(true);
    try {
      const r = await apiClient.post("/finance/ar/remind-all");
      const sent = r.data?.sent ?? 0;
      toast.success(sent > 0 ? `${sent} reminder WA terkirim` : "Tidak ada piutang jatuh tempo untuk diingatkan");
    } catch (e) {
      toast.error("Gagal mengirim reminder massal");
    } finally { setRemindingAll(false); }
  };

  if (loading) return <LoadingState testId="ar-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  const rows = data?.items || [];
  if (rows.length === 0) return <EmptyState title="Tidak ada piutang" description="Semua tagihan sudah lunas." testId="ar-empty" />;

  return (
    <div className="space-y-3" data-testid="ar-panel">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-[12px] bg-[rgba(255,149,0,0.10)] px-4 py-3">
        <span className="text-[13px] font-semibold text-[#8C4A00]">Total Piutang ({data.count} booking)</span>
        <div className="flex items-center gap-3">
          <span className="text-[16px] font-bold tabular-nums text-[#8C4A00]">{formatCurrency(data.total_outstanding)}</span>
          <button className="primary-button" disabled={remindingAll} onClick={remindAll} data-testid="ar-remind-all">
            {remindingAll ? <Loader2 size={14} className="animate-spin" /> : <BellRing size={14} />} Ingatkan Semua (WA)
          </button>
        </div>
      </div>
      <section className="section-card">
        <div className="section-head"><div className="flex items-center gap-2"><Wallet size={16} className="text-[#FF9500]" /><h2>Daftar Piutang</h2></div></div>
        <div className="divide-y divide-[#F2F2F5]" data-testid="ar-list">
          {rows.map((r) => {
            const age = daysSince(r.start_datetime);
            return (
              <div key={r.booking_id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3" data-testid={`ar-${r.booking_id}`}>
                <div className="min-w-0">
                  <p className="flex items-center gap-2 text-[13px] font-bold text-[#1C1C1E]">
                    {r.code} · {r.customer_name}
                    {age != null && age > 0 ? <span className="status-pill tone-danger" data-testid={`ar-age-${r.booking_id}`}>{age} hari</span> : null}
                  </p>
                  <p className="text-[11.5px] text-[#6B6B73]">Total {formatCurrency(r.total_amount)} · terbayar {formatCurrency(r.paid_amount)} · mulai {formatDate(r.start_datetime)}</p>
                </div>
                <div className="flex flex-shrink-0 items-center gap-3">
                  <div className="text-right">
                    <p className="text-[10.5px] uppercase text-[#8E8E93]">Sisa</p>
                    <p className="text-[14px] font-bold tabular-nums text-[#A8221A]">{formatCurrency(r.outstanding)}</p>
                  </div>
                  <PaymentPill value={r.payment_status} />
                  <button className="secondary-button" disabled={remindingId === r.booking_id} onClick={() => remindOne(r.booking_id)} data-testid={`ar-remind-${r.booking_id}`}>
                    {remindingId === r.booking_id ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />} Ingatkan
                  </button>
                  <button className="secondary-button" onClick={() => setPayBooking({ id: r.booking_id, code: r.code, customer_name: r.customer_name, total_amount: r.total_amount, paid_amount: r.paid_amount })} data-testid={`ar-pay-${r.booking_id}`}><Wallet size={13} /> Bayar</button>
                </div>
              </div>
            );
          })}
        </div>
      </section>
      <PaymentDialog open={Boolean(payBooking)} onOpenChange={(v) => !v && setPayBooking(null)} booking={payBooking} onSaved={() => { load(); onChanged && onChanged(); }} />
    </div>
  );
}

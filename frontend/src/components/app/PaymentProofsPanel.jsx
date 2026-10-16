import { useCallback, useEffect, useState } from "react";
import { BadgeCheck, Loader2, Receipt, ThumbsDown, ExternalLink, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { formatCurrency, formatDateTime } from "@/utils/formatters";

// PaymentProofsPanel — antrean BUKTI TRANSFER dari pelanggan web (kanal utama DP masuk).
//
// Verifikasi di sini TIDAK menulis pembayaran sendiri: backend memanggil jalur pembayaran
// resmi (routers/payments) sehingga semua jaminan tetap berlaku — tak bisa overpay, idempoten,
// status pembayaran diturunkan otomatis, dan booking `hold` otomatis menjadi `confirmed`
// begitu DP tercukupi.
export default function PaymentProofsPanel({ onChanged }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [amounts, setAmounts] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await apiClient.get("/bookings/payment-proofs", { params: { status: "pending" } });
      setRows(data?.proofs || []);
      setAmounts(Object.fromEntries((data?.proofs || []).map((p) => [p.id, p.amount_claimed || 0])));
    } catch (e) {
      if (e?.response?.status === 403) setError("");
      else setError(e?.response?.data?.detail || "Gagal memuat bukti pembayaran");
      setRows([]);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const verify = async (p) => {
    setBusy(p.id);
    try {
      const { data } = await apiClient.post(
        `/bookings/${p.booking_id}/proofs/${p.id}/verify`, { amount: Number(amounts[p.id]) || 0 });
      const st = data?.booking?.status;
      toast.success(st === "confirmed"
        ? `Pembayaran tercatat — ${p.booking_code} otomatis dikonfirmasi`
        : "Pembayaran tercatat");
      load();
      onChanged?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memverifikasi bukti");
    } finally { setBusy(""); }
  };

  const reject = async (p) => {
    const reason = window.prompt("Alasan penolakan (tampil ke pelanggan):",
      "Nominal transfer tidak sesuai");
    if (!reason || reason.trim().length < 3) return;
    setBusy(p.id);
    try {
      await apiClient.post(`/bookings/${p.booking_id}/proofs/${p.id}/reject`, { reason: reason.trim() });
      toast.success("Bukti ditolak — pelanggan diberi tahu alasannya");
      load();
      onChanged?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menolak bukti");
    } finally { setBusy(""); }
  };

  if (!loading && !error && rows.length === 0) return null;  // sembunyikan bila antrean kosong

  return (
    <section className="section-card" data-testid="payment-proofs-panel">
      <div className="section-head">
        <div className="flex min-w-0 items-center gap-2">
          <Receipt size={16} className="text-[#007AFF]" />
          <h2 className="truncate">Bukti Transfer Menunggu Verifikasi</h2>
          {rows.length ? (
            <span className="rounded-full bg-[#FFF4E5] px-2 py-0.5 text-[11.5px] font-semibold text-[#A85B00]"
              data-testid="proofs-count">{rows.length}</span>
          ) : null}
        </div>
        <button className="secondary-button flex-shrink-0" onClick={load} data-testid="proofs-refresh">
          <RefreshCw size={13} /> Muat ulang
        </button>
      </div>
      <div className="section-body space-y-2">
        {loading ? (
          <div className="flex items-center gap-2 py-6 text-[13px] text-[#6B6B73]" data-testid="proofs-loading">
            <Loader2 size={15} className="animate-spin" /> Memuat antrean…
          </div>
        ) : error ? (
          <div className="rounded-[12px] border border-[#FFE0DC] bg-[#FFF5F4] p-4 text-[13px] text-[#A8221A]"
            data-testid="proofs-error">{error}</div>
        ) : (
          rows.map((p) => {
            const bk = p.booking || {};
            return (
              <div key={p.id} className="rounded-[12px] border border-[#E5E5EA] p-3.5" data-testid={`proof-${p.id}`}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[13.5px] font-semibold text-[#1C1C1E]">
                      {p.booking_code} · {p.customer_name}
                    </p>
                    <p className="text-[12px] text-[#6B6B73]">
                      {bk.vehicle_name || "—"} · {formatDateTime(bk.start_datetime)} · total{" "}
                      <span className="tabular-nums">{formatCurrency(bk.total_amount)}</span>
                      {bk.dp_amount ? <> · DP diminta <span className="tabular-nums">{formatCurrency(bk.dp_amount)}</span></> : null}
                    </p>
                    <p className="mt-1 text-[12px] text-[#6B6B73]">
                      Pengirim: {p.sender_name || "—"} {p.bank ? `(${p.bank})` : ""} · diunggah {formatDateTime(p.created_at)}
                    </p>
                  </div>
                  {p.media_url ? (
                    <a href={p.media_url} target="_blank" rel="noreferrer"
                      className="secondary-button !px-2.5 !py-1 !text-[12px]" data-testid={`proof-view-${p.id}`}>
                      <ExternalLink size={12} /> Lihat bukti
                    </a>
                  ) : null}
                </div>
                <div className="mt-3 flex flex-wrap items-end gap-2">
                  <div>
                    <span className="block text-[11.5px] text-[#6B6B73]">Nominal diterima (Rp)</span>
                    <input type="number" value={amounts[p.id] ?? ""}
                      onChange={(e) => setAmounts((a) => ({ ...a, [p.id]: e.target.value }))}
                      className="mt-1 w-40 rounded-[10px] border border-[#E5E5EA] px-3 py-2 text-[13px] tabular-nums outline-none"
                      data-testid={`proof-amount-${p.id}`} />
                  </div>
                  <button className="primary-button" disabled={busy === p.id} onClick={() => verify(p)}
                    data-testid={`proof-verify-${p.id}`}>
                    {busy === p.id ? <Loader2 size={13} className="animate-spin" /> : <BadgeCheck size={13} />}
                    Verifikasi &amp; Catat
                  </button>
                  <button className="secondary-button !text-[#A8221A]" disabled={busy === p.id}
                    onClick={() => reject(p)} data-testid={`proof-reject-${p.id}`}>
                    <ThumbsDown size={13} /> Tolak
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}

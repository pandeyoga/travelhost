import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, Loader2, XCircle } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { formatCurrency } from "@/utils/formatters";

/**
 * E21 — Dialog batalkan booking dgn kebijakan denda + refund MANUAL.
 * Denda ditahan sbg pendapatan; refund = dana dikembalikan.
 * Aturan (cermin routers/bookings.cancel_booking): refund ≤ terbayar, dan uang yang DITAHAN
 * (terbayar − refund) ≤ denda — uang tertahan wajib punya dasar denda. Saran refund otomatis
 * = max(terbayar − denda, 0) tiap kali denda diubah (tetap bisa diedit).
 */
const rp = (n) => formatCurrency(n);

export default function CancelBookingDialog({ open, onOpenChange, booking, onSaved }) {
  const [reason, setReason] = useState("");
  const [fee, setFee] = useState("");
  const [refund, setRefund] = useState("");
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState("");

  const paid = Number(booking?.paid_amount || 0);
  const total = Number(booking?.total_amount || 0);

  useEffect(() => {
    if (!open) return;
    // Default aman: tanpa denda → seluruh uang terbayar dikembalikan (lolos aturan server).
    setReason(""); setFee(""); setRefund(paid > 0 ? String(paid) : ""); setSaving(false); setServerError("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, booking?.id]);

  const feeNum = Number(fee) || 0;
  const refundNum = Number(refund) || 0;
  const retained = paid - refundNum; // uang yang tetap di perusahaan
  const suggestedRefund = Math.max(paid - feeNum, 0);

  const onFeeChange = (v) => {
    setFee(v);
    setServerError("");
    if (paid > 0) setRefund(String(Math.max(paid - (Number(v) || 0), 0)));
  };

  const error = useMemo(() => {
    if (feeNum < 0) return "Denda tidak boleh negatif.";
    if (refundNum < 0) return "Refund tidak boleh negatif.";
    if (refundNum > paid) return `Refund melebihi uang yang sudah dibayar (${rp(paid)}).`;
    if (retained > feeNum) {
      return `Uang yang ditahan ${rp(retained)} melebihi denda ${rp(feeNum)} — naikkan refund menjadi ${rp(suggestedRefund)} atau naikkan denda menjadi ${rp(retained)}.`;
    }
    return "";
  }, [feeNum, refundNum, paid, retained, suggestedRefund]);

  // Info (bukan error): denda > uang ditahan → sisa denda ditagihkan lewat invoice denda.
  const feeUnpaid = feeNum > Math.max(retained, 0) ? feeNum - Math.max(retained, 0) : 0;
  const proofPending = booking?.proof_status === "pending";

  const submit = useCallback(async () => {
    if (!booking?.id || error) return;
    setSaving(true);
    setServerError("");
    try {
      await apiClient.post(`/bookings/${booking.id}/cancel`, {
        reason: reason.trim(),
        cancellation_fee: feeNum,
        refund_amount: refundNum,
      });
      toast.success(`Booking ${booking.code || booking.id} dibatalkan`);
      onOpenChange(false);
      if (onSaved) onSaved();
    } catch (e) {
      const msg = e?.response?.data?.detail;
      const text = typeof msg === "string" ? msg : "Gagal membatalkan booking";
      setServerError(text);
      toast.error(text);
    } finally {
      setSaving(false);
    }
  }, [booking, reason, feeNum, refundNum, error, onOpenChange, onSaved]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-md" data-testid="cancel-booking-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-[#A8221A]"><XCircle size={18} /> Batalkan Booking</DialogTitle>
          <DialogDescription>
            {booking?.code ? <>Booking <span className="font-semibold text-[#1C1C1E]">{booking.code}</span> — </> : null}
            isi alasan + kebijakan denda &amp; refund (manual).
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="flex items-center justify-between rounded-lg bg-[#F7F8FA] px-3 py-2 text-[12px]">
            <span className="text-[#6B6B73]">Total booking</span>
            <span className="tabular-nums font-semibold text-[#1C1C1E]">{rp(total)}</span>
          </div>

          {proofPending ? (
            <div className="flex items-start gap-2 rounded-lg border border-[#FFDDAD] bg-[#FFF4E5] px-3 py-2 text-[12px] text-[#8C4A00]" data-testid="cb-proof-warning">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              Ada bukti transfer yang menunggu verifikasi — verifikasi (catat pembayarannya) atau tolak buktinya dulu.
            </div>
          ) : null}

          <div>
            <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Alasan</label>
            <Input value={reason} maxLength={400} onChange={(e) => setReason(e.target.value)} placeholder="Pelanggan pindah tanggal, force majeure, …" data-testid="cb-reason" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Denda (Rp)</label>
              <Input type="number" min="0" value={fee} onChange={(e) => onFeeChange(e.target.value)} placeholder="0" data-testid="cb-fee" />
              <p className="mt-1 text-[11px] text-[#8A8A8F]">Ditahan sebagai pendapatan.</p>
            </div>
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Refund (Rp)</label>
              <Input type="number" min="0" max={paid} value={refund} disabled={paid <= 0}
                onChange={(e) => { setRefund(e.target.value); setServerError(""); }} placeholder="0" data-testid="cb-refund" />
              <p className="mt-1 text-[11px] text-[#8A8A8F]">
                {paid > 0 ? <>Saran: <button type="button" className="font-semibold text-[#007AFF]" onClick={() => setRefund(String(suggestedRefund))} data-testid="cb-refund-suggest">{rp(suggestedRefund)}</button></> : "Belum ada uang masuk."}
              </p>
            </div>
          </div>

          <div className="divide-y divide-[#EFF0F2] rounded-lg border border-[#EFF0F2] text-[12.5px]" data-testid="cb-summary">
            <div className="flex items-center justify-between px-3 py-1.5">
              <span className="text-[#6B6B73]">Terbayar</span>
              <span className="tabular-nums font-semibold text-[#1C1C1E]" data-testid="cb-sum-paid">{rp(paid)}</span>
            </div>
            <div className="flex items-center justify-between px-3 py-1.5">
              <span className="text-[#6B6B73]">Refund ke pelanggan</span>
              <span className="tabular-nums font-semibold text-[#A8221A]" data-testid="cb-sum-refund">− {rp(refundNum)}</span>
            </div>
            <div className="flex items-center justify-between px-3 py-1.5">
              <span className="font-semibold text-[#3C3C43]">Ditahan sebagai denda</span>
              <span className="tabular-nums font-bold text-[#1C1C1E]" data-testid="cb-sum-retained">{rp(Math.max(retained, 0))}</span>
            </div>
          </div>

          {!error && feeUnpaid > 0 ? (
            <p className="text-[11.5px] text-[#6B6B73]" data-testid="cb-fee-unpaid">
              Denda {rp(feeNum)} belum tertutup uang yang ditahan — sisa {rp(feeUnpaid)} ditagihkan lewat invoice denda.
            </p>
          ) : null}

          {error ? (
            <div className="rounded-lg border border-[#F0C4C0] bg-[#FDECEA] px-3 py-2 text-[12px] text-[#A8221A]" data-testid="cb-error">
              {error}
            </div>
          ) : null}
          {serverError ? (
            <div className="rounded-lg border border-[#F0C4C0] bg-[#FDECEA] px-3 py-2 text-[12px] text-[#A8221A]" data-testid="cb-server-error">
              {serverError}
            </div>
          ) : null}
        </div>

        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="cb-close">Batal</button>
          <button className="primary-button !bg-[#A8221A] hover:!bg-[#8F1A14]" disabled={saving || Boolean(error) || !booking?.id} onClick={submit} data-testid="cb-submit">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Konfirmasi Batalkan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

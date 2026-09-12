import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Loader2, XCircle } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { formatCurrency } from "@/utils/formatters";

/**
 * E21 — Dialog batalkan booking dgn kebijakan denda + refund MANUAL.
 * Denda ditahan sbg pendapatan; refund = dana dikembalikan.
 * Akuntansi kas jurnal (opsional) di-defer — lihat memory/HANDOFF_E21_REFUND.md.
 */
export default function CancelBookingDialog({ open, onOpenChange, booking, onSaved }) {
  const [reason, setReason] = useState("");
  const [fee, setFee] = useState("");
  const [refund, setRefund] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setReason(""); setFee(""); setRefund(""); setSaving(false);
  }, [open, booking?.id]);

  const paid = Number(booking?.paid_amount || 0);
  const total = Number(booking?.total_amount || 0);
  const feeNum = Number(fee) || 0;
  const refundNum = Number(refund) || 0;

  const error = useMemo(() => {
    if (feeNum < 0) return "Denda tidak boleh negatif.";
    if (refundNum < 0) return "Refund tidak boleh negatif.";
    if (refundNum > paid) return `Refund melebihi terbayar (Rp ${paid.toLocaleString("id-ID")}).`;
    return "";
  }, [feeNum, refundNum, paid]);

  const submit = useCallback(async () => {
    if (!booking?.id || error) return;
    setSaving(true);
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
      toast.error(e?.response?.data?.detail || "Gagal membatalkan booking");
    } finally {
      setSaving(false);
    }
  }, [booking, reason, feeNum, refundNum, error, onOpenChange, onSaved]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="cancel-booking-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-[#A8221A]"><XCircle size={18} /> Batalkan Booking</DialogTitle>
          <DialogDescription>
            {booking?.code ? <>Booking <span className="font-semibold text-[#1C1C1E]">{booking.code}</span> — </> : null}
            Isi alasan + kebijakan denda &amp; refund (manual). Kas jurnal akuntansi menyusul.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 rounded-lg bg-[#F7F8FA] px-3 py-2 text-[12px]">
            <div className="flex items-center justify-between">
              <span className="text-[#6B6B73]">Total</span>
              <span className="tabular-nums font-semibold text-[#1C1C1E]">{formatCurrency(total)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[#6B6B73]">Terbayar</span>
              <span className="tabular-nums font-semibold text-[#1C1C1E]">{formatCurrency(paid)}</span>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Alasan</label>
            <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Pelanggan pindah tanggal, force majeure, …" data-testid="cb-reason" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Denda (Rp)</label>
              <Input type="number" min="0" value={fee} onChange={(e) => setFee(e.target.value)} placeholder="0" data-testid="cb-fee" />
              <p className="mt-1 text-[11px] text-[#8A8A8F]">Ditahan sebagai pendapatan (manual).</p>
            </div>
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Refund (Rp)</label>
              <Input type="number" min="0" value={refund} onChange={(e) => setRefund(e.target.value)} placeholder="0" data-testid="cb-refund" />
              <p className="mt-1 text-[11px] text-[#8A8A8F]">Dikembalikan ke pelanggan.</p>
            </div>
          </div>

          {error ? (
            <div className="rounded-lg border border-[#F0C4C0] bg-[#FDECEA] px-3 py-2 text-[12px] text-[#A8221A]" data-testid="cb-error">
              {error}
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

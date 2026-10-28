import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, Loader2, XCircle } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { formatCurrency, formatDateTime } from "@/utils/formatters";

const MAX_REASON = 400; // sinkron schemas_booking.RejectBooking.reason

/**
 * Tolak permintaan booking (pending/hold) — SATU dialog untuk daftar Booking, panel Pesanan
 * Website Masuk, dan Kalender. Dulu "Tolak" langsung menembak API tanpa konfirmasi & tanpa
 * alasan; sekarang alasan (opsional) tersimpan dan tampil ke pelanggan di halaman status.
 */
export default function RejectBookingDialog({ open, onOpenChange, booking, onSaved }) {
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setReason(""); setSaving(false); setError("");
  }, [open, booking?.id]);

  const paid = Number(booking?.paid_amount || 0);
  const proofPending = booking?.proof_status === "pending";

  const submit = async () => {
    if (!booking?.id) return;
    setSaving(true);
    setError("");
    try {
      await apiClient.post(`/bookings/${booking.id}/reject`, { reason: reason.trim() });
      toast.success(`Permintaan ${booking.code || ""} ditolak`);
      onOpenChange(false);
      if (onSaved) onSaved();
    } catch (e) {
      const msg = e?.response?.data?.detail || "Gagal menolak permintaan";
      setError(typeof msg === "string" ? msg : "Gagal menolak permintaan");
      toast.error(typeof msg === "string" ? msg : "Gagal menolak permintaan");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="reject-booking-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-[#A8221A]"><XCircle size={18} /> Tolak Permintaan Booking</DialogTitle>
          <DialogDescription>
            {booking?.code ? <><span className="font-semibold text-[#1C1C1E]">{booking.code}</span> · {booking.customer_name} — </> : null}
            pesanan dibatalkan (unit yang ditahan dilepas) dan pelanggan diberi tahu via WhatsApp.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          {booking ? (
            <div className="rounded-lg bg-[#F7F8FA] px-3 py-2 text-[12.5px] text-[#6B6B73]" data-testid="rj-summary">
              Jadwal: <span className="font-semibold text-[#1C1C1E]">{formatDateTime(booking.start_datetime)}</span>
              {Number(booking.total_amount) > 0 ? <> · Total <span className="font-semibold tabular-nums text-[#1C1C1E]">{formatCurrency(booking.total_amount)}</span></> : null}
            </div>
          ) : null}
          {paid > 0 || proofPending ? (
            <div className="flex items-start gap-2 rounded-lg border border-[#FFDDAD] bg-[#FFF4E5] px-3 py-2 text-[12px] text-[#8C4A00]" data-testid="rj-warning">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              <span>
                {paid > 0
                  ? `Pesanan ini sudah menerima pembayaran ${formatCurrency(paid)} — gunakan "Batal" (dengan denda/refund) agar uangnya tercatat.`
                  : "Ada bukti transfer DP yang menunggu verifikasi — verifikasi atau tolak buktinya dulu."}
              </span>
            </div>
          ) : null}
          <div>
            <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]" htmlFor="rj-reason">Alasan penolakan (opsional)</label>
            <Textarea id="rj-reason" rows={3} maxLength={MAX_REASON} value={reason} onChange={(e) => setReason(e.target.value)}
              placeholder="Unit penuh di tanggal tersebut, rute di luar layanan, …" data-testid="rj-reason" />
            <p className="mt-1 flex justify-between text-[11px] text-[#8A8A8F]">
              <span>Ditampilkan ke pelanggan di halaman status pesanan.</span>
              <span className="tabular-nums">{reason.length}/{MAX_REASON}</span>
            </p>
          </div>
          {error ? (
            <div className="rounded-lg border border-[#F0C4C0] bg-[#FDECEA] px-3 py-2 text-[12px] text-[#A8221A]" data-testid="rj-error">{error}</div>
          ) : null}
        </div>

        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="rj-close">Batal</button>
          <button className="primary-button !bg-[#A8221A] hover:!bg-[#8F1A14]" disabled={saving || !booking?.id} onClick={submit} data-testid="rj-submit">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Tolak Permintaan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

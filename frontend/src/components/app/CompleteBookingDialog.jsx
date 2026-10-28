import { useEffect, useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, Loader2, Star } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { formatCurrency, formatDateTime } from "@/utils/formatters";

/**
 * Konfirmasi "Selesai" oleh ops. Menyelesaikan booking menutup trip, membebaskan armada, dan
 * MENGIRIM permintaan ulasan ke pelanggan — tak bisa ditarik, jadi wajib konfirmasi. Tombol
 * hanya ditawarkan untuk booking terkonfirmasi/berjalan yang jadwalnya sudah mulai
 * (lib/bookingRules.canComplete); penolakan server tetap ditampilkan apa adanya.
 */
export default function CompleteBookingDialog({ open, onOpenChange, booking, onSaved }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { if (open) { setSaving(false); setError(""); } }, [open, booking?.id]);

  const outstanding = Math.max(Number(booking?.total_amount || 0) - Number(booking?.paid_amount || 0), 0);

  const submit = async () => {
    if (!booking?.id) return;
    setSaving(true);
    setError("");
    try {
      await apiClient.post(`/bookings/${booking.id}/complete`);
      toast.success(`Booking ${booking.code || ""} diselesaikan — permintaan ulasan dikirim ke pelanggan`);
      onOpenChange(false);
      if (onSaved) onSaved();
    } catch (e) {
      const msg = e?.response?.data?.detail;
      const text = typeof msg === "string" ? msg : "Gagal menyelesaikan booking";
      setError(text);
      toast.error(text);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="complete-booking-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><CheckCircle2 size={18} className="text-[#34C759]" /> Selesaikan Booking?</DialogTitle>
          <DialogDescription>
            {booking?.code ? <><span className="font-semibold text-[#1C1C1E]">{booking.code}</span> · {booking.customer_name} — </> : null}
            trip ditutup dan armada kembali tersedia.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2.5 text-[12.5px]">
          {booking ? (
            <div className="rounded-lg bg-[#F7F8FA] px-3 py-2 text-[#6B6B73]" data-testid="cp-summary">
              Jadwal: <span className="font-semibold text-[#1C1C1E]">{formatDateTime(booking.start_datetime)}</span> → {formatDateTime(booking.end_datetime)}
            </div>
          ) : null}
          <p className="flex items-start gap-2 rounded-lg border border-[#C7DCFF] bg-[#EAF2FF] px-3 py-2 text-[#0B3B82]" data-testid="cp-review-note">
            <Star size={14} className="mt-0.5 shrink-0" />
            Pelanggan akan menerima permintaan ulasan via WhatsApp setelah booking diselesaikan.
          </p>
          {outstanding > 0 ? (
            <p className="rounded-lg border border-[#FFDDAD] bg-[#FFF4E5] px-3 py-2 text-[#8C4A00]" data-testid="cp-outstanding">
              Masih ada sisa tagihan <span className="font-semibold tabular-nums">{formatCurrency(outstanding)}</span> — tetap tercatat sebagai piutang.
            </p>
          ) : null}
          {error ? (
            <div className="rounded-lg border border-[#F0C4C0] bg-[#FDECEA] px-3 py-2 text-[12px] text-[#A8221A]" data-testid="cp-error">{error}</div>
          ) : null}
        </div>
        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="cp-close">Batal</button>
          <button className="primary-button" disabled={saving || !booking?.id} onClick={submit} data-testid="cp-submit">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />} Ya, Selesaikan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

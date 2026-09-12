import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Wallet } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PaymentPill } from "@/components/shared/StatusPill";
import { formatCurrency, formatDateTime } from "@/utils/formatters";

const METHODS = [{ v: "transfer", l: "Transfer" }, { v: "cash", l: "Tunai" }, { v: "qris", l: "QRIS" }];
const TYPES = [{ v: "dp", l: "DP / Uang Muka" }, { v: "settlement", l: "Pelunasan" }];

export default function PaymentDialog({ open, onOpenChange, booking, onSaved }) {
  const [amount, setAmount] = useState("");
  const [type, setType] = useState("settlement");
  const [method, setMethod] = useState("transfer");
  const [payments, setPayments] = useState([]);
  const [saving, setSaving] = useState(false);
  const [idemKey, setIdemKey] = useState("");

  const total = Number(booking?.total_amount || 0);
  const paid = Number(booking?.paid_amount || 0);
  const remaining = Math.max(total - paid, 0);

  useEffect(() => {
    if (!open || !booking?.id) return;
    setAmount(""); setType("settlement"); setMethod("transfer");
    // Kunci idempotensi baru per sesi dialog → retry/klik-ganda submit yang sama tidak dobel.
    setIdemKey((crypto?.randomUUID?.() || `${booking.id}-${Date.now()}-${Math.random()}`));
    let active = true;
    apiClient.get(`/payments?booking_id=${booking.id}`)
      .then((r) => { if (active) setPayments(Array.isArray(r.data) ? r.data : []); })
      .catch(() => { if (active) setPayments([]); });
    return () => { active = false; };
  }, [open, booking]);

  const submit = async () => {
    const amt = Number(amount);
    if (!amt || amt <= 0) { toast.error("Nominal pembayaran tidak valid"); return; }
    setSaving(true);
    try {
      await apiClient.post("/payments", {
        booking_id: booking.id, amount: amt, type, method, idempotency_key: idemKey,
      });
      toast.success("Pembayaran tercatat");
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat pembayaran");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-md" data-testid="payment-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Wallet size={17} className="text-[#007AFF]" /> Catat Pembayaran</DialogTitle>
          <DialogDescription>{booking?.code} · {booking?.customer_name}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-[10px] bg-[#F7F8FA] p-2.5 text-center">
              <p className="text-[10.5px] font-semibold uppercase text-[#6B6B73]">Total</p>
              <p className="text-[13.5px] font-bold tabular-nums text-[#1C1C1E]" data-testid="pay-total">{formatCurrency(total)}</p>
            </div>
            <div className="rounded-[10px] bg-[#F7F8FA] p-2.5 text-center">
              <p className="text-[10.5px] font-semibold uppercase text-[#6B6B73]">Terbayar</p>
              <p className="text-[13.5px] font-bold tabular-nums text-[#126E2C]" data-testid="pay-paid">{formatCurrency(paid)}</p>
            </div>
            <div className="rounded-[10px] bg-[#F7F8FA] p-2.5 text-center">
              <p className="text-[10.5px] font-semibold uppercase text-[#6B6B73]">Sisa</p>
              <p className="text-[13.5px] font-bold tabular-nums text-[#A8221A]" data-testid="pay-remaining">{formatCurrency(remaining)}</p>
            </div>
          </div>

          {payments.length > 0 ? (
            <div className="rounded-[10px] border border-[#EFF0F2]" data-testid="pay-history">
              {payments.map((p) => (
                <div key={p.id} className="flex items-center justify-between border-b border-[#F2F2F5] px-3 py-2 text-[12.5px] last:border-0">
                  <span className="text-[#6B6B73]">{formatDateTime(p.paid_at)} · {p.method}</span>
                  <span className="font-semibold tabular-nums text-[#1C1C1E]">{formatCurrency(p.amount)}</span>
                </div>
              ))}
            </div>
          ) : null}

          {remaining <= 0 ? (
            <div className="flex items-center justify-center gap-2 rounded-[10px] bg-[rgba(52,199,89,0.12)] py-3 text-[13px] font-semibold text-[#126E2C]">
              <PaymentPill value="lunas" /> Tagihan sudah lunas
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Jenis</Label>
                  <Select value={type} onValueChange={setType}>
                    <SelectTrigger data-testid="pay-type"><SelectValue /></SelectTrigger>
                    <SelectContent>{TYPES.map((t) => <SelectItem key={t.v} value={t.v}>{t.l}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Metode</Label>
                  <Select value={method} onValueChange={setMethod}>
                    <SelectTrigger data-testid="pay-method"><SelectValue /></SelectTrigger>
                    <SelectContent>{METHODS.map((m) => <SelectItem key={m.v} value={m.v}>{m.l}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-1.5">
                <Label>Nominal (Rp)</Label>
                <Input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder={String(remaining)} data-testid="pay-amount" />
                <button type="button" className="text-[12px] font-semibold text-[#007AFF]" onClick={() => setAmount(String(remaining))} data-testid="pay-fill-remaining">
                  Isi sisa tagihan ({formatCurrency(remaining)})
                </button>
              </div>
            </>
          )}
        </div>
        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="pay-cancel">Tutup</button>
          {remaining > 0 ? (
            <button className="primary-button" disabled={saving} onClick={submit} data-testid="pay-submit">
              {saving ? <Loader2 size={14} className="animate-spin" /> : null} Catat Pembayaran
            </button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

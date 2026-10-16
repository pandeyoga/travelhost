import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { formatCurrency } from "@/utils/formatters";

const toDateInput = (v) => (v ? String(v).slice(0, 10) : "");

export default function InvoiceEditDialog({ open, onOpenChange, invoice, onSaved }) {
  const [form, setForm] = useState({ amount: "", due_at: "", notes: "", terms: "" });
  const [busy, setBusy] = useState(false);
  const locked = invoice && ["paid", "void"].includes(invoice.status);

  useEffect(() => {
    if (open && invoice) {
      setForm({ amount: String(invoice.amount ?? ""), due_at: toDateInput(invoice.due_at), notes: invoice.notes || "", terms: invoice.terms || "" });
    }
  }, [open, invoice]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async () => {
    if (!invoice) return;
    const amount = Number(form.amount);
    if (!locked && (!Number.isFinite(amount) || amount <= 0)) { toast.error("Nominal harus lebih dari 0"); return; }
    setBusy(true);
    try {
      const payload = { due_at: form.due_at || null, notes: form.notes, terms: form.terms };
      if (!locked) payload.amount = amount;
      await apiClient.patch(`/invoices/${invoice.id}`, payload);
      toast.success(`Invoice ${invoice.number} diperbarui`);
      onOpenChange(false); onSaved && onSaved();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan invoice"); }
    finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg" data-testid="invoice-edit-dialog">
        <DialogHeader>
          <DialogTitle>Edit Invoice {invoice?.number}</DialogTitle>
          <DialogDescription>
            {invoice?.customer_name} · {invoice?.booking_code} · subtotal {formatCurrency(invoice?.subtotal)}
            {locked ? " — nominal invoice lunas/batal tidak dapat diubah." : ""}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5"><Label>Nominal (Rp)</Label>
              <Input type="number" min="1" value={form.amount} onChange={set("amount")} disabled={locked} data-testid="ie-amount" /></div>
            <div className="space-y-1.5"><Label>Jatuh tempo</Label>
              <Input type="date" value={form.due_at} onChange={set("due_at")} data-testid="ie-due" /></div>
          </div>
          <div className="space-y-1.5"><Label>Catatan</Label>
            <Textarea rows={2} value={form.notes} onChange={set("notes")} data-testid="ie-notes" /></div>
          <div className="space-y-1.5"><Label>Syarat pembayaran</Label>
            <Textarea rows={3} value={form.terms} onChange={set("terms")} data-testid="ie-terms" /></div>
        </div>
        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="ie-cancel">Batal</button>
          <button className="primary-button" disabled={busy} onClick={submit} data-testid="ie-submit">
            {busy ? <Loader2 size={14} className="animate-spin" /> : null} Simpan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

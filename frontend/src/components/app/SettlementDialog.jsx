import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCurrency } from "@/utils/formatters";

export default function SettlementDialog({ open, onOpenChange, partner, onSaved }) {
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("transfer");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && partner) {
      setAmount(partner.ap_outstanding > 0 ? String(partner.ap_outstanding) : "");
      setMethod("transfer"); setNote("");
    }
  }, [open, partner]);

  const submit = async () => {
    if (!partner) return;
    if (!(Number(amount) > 0)) { toast.error("Nominal pelunasan harus lebih dari 0"); return; }
    setSaving(true);
    try {
      await apiClient.post(`/partners/${partner.id}/settlements`, {
        amount: Number(amount), method, note,
      });
      toast.success("Pelunasan ke mitra tercatat");
      onOpenChange(false); onSaved && onSaved();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal mencatat pelunasan"); }
    finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="settlement-dialog">
        <DialogHeader>
          <DialogTitle>Catat Pelunasan ke Mitra</DialogTitle>
          <DialogDescription>{partner ? `${partner.name} · Utang saat ini ${formatCurrency(partner.ap_outstanding)}` : ""}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5"><Label>Nominal</Label>
            <Input type="number" min="0" step="50000" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="2200000" className="tabular-nums" data-testid="settle-amount" />
            {Number(amount) > 0 ? <p className="text-xs tabular-nums text-[#8A8A8E]">{formatCurrency(amount)}</p> : null}</div>
          <div className="space-y-1.5"><Label>Metode</Label>
            <Select value={method} onValueChange={setMethod}>
              <SelectTrigger data-testid="settle-method"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="transfer">Transfer</SelectItem>
                <SelectItem value="cash">Tunai</SelectItem>
                <SelectItem value="other">Lainnya</SelectItem>
              </SelectContent>
            </Select></div>
          <div className="space-y-1.5"><Label>Catatan</Label>
            <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="No. referensi transfer…" data-testid="settle-note" /></div>
        </div>
        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="settle-cancel">Batal</button>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="settle-submit">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Catat Pelunasan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

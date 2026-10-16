import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Receipt } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCurrency } from "@/utils/formatters";

const CATEGORIES = [
  ["bbm", "BBM / Solar"],
  ["tol", "Tol & Parkir"],
  ["uang_jalan", "Uang Jalan Driver"],
  ["other", "Lainnya"],
];

export default function ExpenseFormDialog({ open, onOpenChange, onSaved, initial = null }) {
  const editing = Boolean(initial && initial.id);
  const [bookings, setBookings] = useState([]);
  const [form, setForm] = useState({ booking_id: "none", category: "bbm", amount: "", note: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(editing
      ? { booking_id: initial.booking_id || "none", category: initial.category || "other", amount: initial.amount ?? "", note: initial.note || "" }
      : { booking_id: "none", category: "bbm", amount: "", note: "" });
    apiClient.get("/bookings").then((r) => setBookings(Array.isArray(r.data) ? r.data : [])).catch(() => setBookings([]));
  }, [open, editing, initial]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    const amt = Number(form.amount);
    if (!amt || amt <= 0) { toast.error("Nominal pengeluaran tidak valid"); return; }
    setSaving(true);
    try {
      const payload = { booking_id: form.booking_id === "none" ? null : form.booking_id, category: form.category, amount: amt, note: form.note };
      if (editing) await apiClient.patch(`/expenses/${initial.id}`, payload);
      else await apiClient.post("/expenses", payload);
      toast.success(editing ? "Pengeluaran diperbarui" : "Pengeluaran tercatat");
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan pengeluaran");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-md" data-testid="expense-form-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Receipt size={17} className="text-[#007AFF]" /> {editing ? "Edit Pengeluaran" : "Catat Pengeluaran"}</DialogTitle>
          <DialogDescription>Pengeluaran operasional trip/booking (BBM, tol, uang jalan, dll).</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label>Booking (opsional)</Label>
            <Select value={form.booking_id} onValueChange={(v) => set("booking_id", v)}>
              <SelectTrigger data-testid="exp-booking"><SelectValue placeholder="Pilih booking" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Tanpa booking (umum)</SelectItem>
                {bookings.map((b) => <SelectItem key={b.id} value={b.id}>{b.code} · {b.customer_name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Kategori</Label>
              <Select value={form.category} onValueChange={(v) => set("category", v)}>
                <SelectTrigger data-testid="exp-category"><SelectValue /></SelectTrigger>
                <SelectContent>{CATEGORIES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Nominal (Rp)</Label>
              <Input type="number" min="1" value={form.amount} onChange={(e) => set("amount", e.target.value)} placeholder="0" data-testid="exp-amount" />
            </div>
          </div>
          {form.amount ? <p className="text-[12px] text-[#6B6B73]">Jumlah: <span className="font-semibold tabular-nums text-[#1C1C1E]">{formatCurrency(form.amount)}</span></p> : null}
          <div className="space-y-1.5">
            <Label>Catatan</Label>
            <Textarea value={form.note} onChange={(e) => set("note", e.target.value)} rows={2} placeholder="Keterangan pengeluaran…" data-testid="exp-note" />
          </div>
        </div>
        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="exp-cancel">Batal</button>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="exp-submit">{saving ? <Loader2 size={14} className="animate-spin" /> : null} Simpan</button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

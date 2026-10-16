import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Plus, Trash2, Save } from "lucide-react";
import apiClient from "@/services/apiClient";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import DestinationSelect from "@/components/app/DestinationSelect";
import { formatCurrency } from "@/utils/formatters";

function Fld({ label, children }) {
  return <div className="space-y-1"><Label className="text-[12px]">{label}</Label>{children}</div>;
}

// Edit penawaran draft/terkirim (PATCH /quotations/{id}): data pelanggan, jadwal, item harga, catatan.
export default function QuotationEditDialog({ quo, open, onOpenChange, onSaved }) {
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    if (!open || !quo) return;
    setForm({
      customer_name: quo.customer_name || "", phone: quo.phone || "", email: quo.email || "",
      destination: quo.destination || "", trip_date: (quo.trip_date || "").slice(0, 10), pax: quo.pax || 1,
      valid_until: (quo.valid_until || "").slice(0, 10), notes: quo.notes || "",
      items: (quo.items || []).map((i) => ({ label: i.label || "", amount: i.amount ?? 0 })),
    });
  }, [open, quo]);

  const setItem = (idx, k, v) => set("items", form.items.map((it, i) => (i === idx ? { ...it, [k]: v } : it)));
  const total = (form?.items || []).reduce((s, i) => s + (Number(i.amount) || 0), 0);

  const submit = async () => {
    if (!form.customer_name.trim()) { toast.error("Nama pelanggan wajib diisi"); return; }
    const items = form.items.filter((i) => i.label.trim());
    if (!items.length) { toast.error("Minimal satu item harga"); return; }
    setSaving(true);
    try {
      await apiClient.patch(`/quotations/${quo.id}`, {
        customer_name: form.customer_name.trim(), phone: form.phone, email: form.email,
        destination: form.destination, trip_date: form.trip_date || null, pax: Number(form.pax) || 1,
        valid_until: form.valid_until ? new Date(form.valid_until).toISOString() : null, notes: form.notes,
        items: items.map((i) => ({ label: i.label.trim(), amount: Number(i.amount) || 0 })),
      });
      toast.success("Penawaran diperbarui");
      onOpenChange(false); onSaved && onSaved();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan penawaran"); }
    finally { setSaving(false); }
  };

  if (!form) return null;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto" data-testid="quotation-edit-dialog">
        <DialogHeader>
          <DialogTitle>Edit Penawaran {quo?.number}</DialogTitle>
          <DialogDescription>Hanya penawaran Draft / Terkirim yang bisa diubah. Total dihitung ulang dari item.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Fld label="Nama Pelanggan"><Input value={form.customer_name} onChange={(e) => set("customer_name", e.target.value)} data-testid="qe-name" /></Fld>
            <Fld label="Telepon"><Input value={form.phone} onChange={(e) => set("phone", e.target.value)} data-testid="qe-phone" /></Fld>
            <Fld label="Email"><Input value={form.email} onChange={(e) => set("email", e.target.value)} data-testid="qe-email" /></Fld>
            <Fld label="Destinasi (master)"><DestinationSelect value={form.destination} onChange={(v) => set("destination", v)} testId="qe-destination" optionsPath="/leads/destination-options" /></Fld>
            <Fld label="Tanggal Trip"><Input type="date" value={form.trip_date} onChange={(e) => set("trip_date", e.target.value)} data-testid="qe-trip-date" /></Fld>
            <Fld label="Pax"><Input type="number" min="1" value={form.pax} onChange={(e) => set("pax", e.target.value)} data-testid="qe-pax" /></Fld>
            <Fld label="Berlaku s/d"><Input type="date" value={form.valid_until} onChange={(e) => set("valid_until", e.target.value)} data-testid="qe-valid" /></Fld>
          </div>
          <div className="rounded-lg border border-[#E5E5EA]" data-testid="qe-items">
            {form.items.map((it, i) => (
              <div key={i} className="flex items-center gap-2 border-b border-[#F2F2F5] px-2 py-1.5 last:border-0">
                <Input className="!h-8 flex-1 text-[12.5px]" value={it.label} onChange={(e) => setItem(i, "label", e.target.value)} placeholder="Nama item" data-testid={`qe-item-label-${i}`} />
                <Input className="!h-8 w-[150px] text-[12.5px]" type="number" min="0" value={it.amount} onChange={(e) => setItem(i, "amount", e.target.value)} data-testid={`qe-item-amount-${i}`} />
                <button type="button" className="icon-button !h-8 !w-8 !text-[#A8221A]" onClick={() => set("items", form.items.filter((_, j) => j !== i))} data-testid={`qe-item-del-${i}`}><Trash2 size={13} /></button>
              </div>
            ))}
            <div className="flex items-center justify-between bg-[#FAFAFC] px-3 py-2">
              <button type="button" className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#007AFF]" onClick={() => set("items", [...form.items, { label: "", amount: 0 }])} data-testid="qe-item-add"><Plus size={12} /> Tambah item</button>
              <span className="text-[13px] font-bold tabular-nums" data-testid="qe-total">Total: {formatCurrency(total)}</span>
            </div>
          </div>
          <Fld label="Catatan"><Textarea value={form.notes} onChange={(e) => set("notes", e.target.value)} rows={2} data-testid="qe-notes" /></Fld>
        </div>
        <DialogFooter>
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="qe-cancel">Batal</button>
          <button className="primary-button" onClick={submit} disabled={saving} data-testid="qe-submit">{saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Simpan</button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

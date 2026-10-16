import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import apiClient from "@/services/apiClient";
import CitySelect from "@/components/app/CitySelect";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const EMPTY = { name: "", pic: "", phone: "", email: "", city: "", address: "", rating: "", notes: "", status: "active" };

export default function PartnerFormDialog({ open, onOpenChange, initial, onSaved }) {
  const editing = Boolean(initial && initial.id);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(editing ? {
      name: initial.name || "", pic: initial.pic || "", phone: initial.phone || "",
      email: initial.email || "", city: initial.city || "", address: initial.address || "",
      rating: initial.rating ?? "", notes: initial.notes || "", status: initial.status || "active",
    } : EMPTY);
  }, [open, editing, initial]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.name.trim()) { toast.error("Nama mitra wajib diisi"); return; }
    setSaving(true);
    const payload = {
      name: form.name.trim(), pic: form.pic, phone: form.phone, email: form.email,
      city: form.city, address: form.address, rating: Number(form.rating) || 0,
      notes: form.notes, status: form.status,
    };
    try {
      if (editing) await apiClient.patch(`/partners/${initial.id}`, payload);
      else await apiClient.post("/partners", payload);
      toast.success(editing ? "Mitra diperbarui" : "Mitra ditambahkan");
      onOpenChange(false); onSaved && onSaved();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan mitra"); }
    finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg" data-testid="partner-form-dialog">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit Mitra" : "Tambah Mitra"}</DialogTitle>
          <DialogDescription>Data travel mitra untuk sumber armada (pinjam armada / sub-charter).</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5"><Label>Nama Mitra</Label>
              <Input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="Travel Mitra Sejahtera" data-testid="pf-name" /></div>
            <div className="space-y-1.5"><Label>PIC / Kontak</Label>
              <Input value={form.pic} onChange={(e) => set("pic", e.target.value)} placeholder="Pak Budi" data-testid="pf-pic" /></div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5"><Label>Telepon (WA)</Label>
              <Input value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="0812xxxx" data-testid="pf-phone" /></div>
            <div className="space-y-1.5"><Label>Email</Label>
              <Input value={form.email} onChange={(e) => set("email", e.target.value)} placeholder="ops@mitra.id" data-testid="pf-email" /></div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5"><Label>Kota</Label>
              <CitySelect value={form.city} onChange={(v) => set("city", v)} testId="pf-city" /></div>
            <div className="space-y-1.5"><Label>Rating (0-5)</Label>
              <Input type="number" step="0.1" min="0" max="5" value={form.rating} onChange={(e) => set("rating", e.target.value)} placeholder="4.6" data-testid="pf-rating" /></div>
          </div>
          <div className="space-y-1.5"><Label>Alamat</Label>
            <Input value={form.address} onChange={(e) => set("address", e.target.value)} placeholder="Jl. Soekarno Hatta 210" data-testid="pf-address" /></div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5"><Label>Status</Label>
              <Select value={form.status} onValueChange={(v) => set("status", v)}>
                <SelectTrigger data-testid="pf-status"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="active">Aktif</SelectItem><SelectItem value="inactive">Nonaktif</SelectItem></SelectContent>
              </Select></div>
          </div>
          <div className="space-y-1.5"><Label>Catatan</Label>
            <Textarea value={form.notes} onChange={(e) => set("notes", e.target.value)} placeholder="Catatan mitra…" data-testid="pf-notes" /></div>
        </div>
        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="pf-cancel">Batal</button>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="pf-submit">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Simpan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

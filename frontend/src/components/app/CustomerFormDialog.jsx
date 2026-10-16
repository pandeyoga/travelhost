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
import CitySelect from "@/components/app/CitySelect";

const TYPES = [{ v: "individual", l: "Individu" }, { v: "corporate", l: "Korporat" }];
const EMPTY = { name: "", phone: "", email: "", type: "individual", city: "", address: "", notes: "" };

export default function CustomerFormDialog({ open, onOpenChange, initial, onSaved }) {
  const editing = Boolean(initial && initial.id);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(editing ? {
      name: initial.name || "", phone: initial.phone || "", email: initial.email || "",
      type: initial.type || "individual", city: initial.city || "", address: initial.address || "",
      notes: initial.notes || "",
    } : EMPTY);
  }, [open, editing, initial]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.name.trim()) {
      toast.error("Nama customer wajib diisi");
      return;
    }
    setSaving(true);
    const payload = {
      name: form.name.trim(), phone: form.phone, email: form.email, type: form.type,
      city: form.city, address: form.address, notes: form.notes,
    };
    try {
      if (editing) await apiClient.patch(`/customers/${initial.id}`, payload);
      else await apiClient.post("/customers", payload);
      toast.success(editing ? "Customer diperbarui" : "Customer ditambahkan");
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan customer");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg" data-testid="customer-form-dialog">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit Customer" : "Tambah Customer"}</DialogTitle>
          <DialogDescription>Data pelanggan untuk Customer 360 & booking.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Nama</Label>
              <Input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="PT / Nama" data-testid="cf-name" />
            </div>
            <div className="space-y-1.5">
              <Label>Segmen</Label>
              <Select value={form.type} onValueChange={(v) => set("type", v)}>
                <SelectTrigger data-testid="cf-type"><SelectValue /></SelectTrigger>
                <SelectContent>{TYPES.map((t) => <SelectItem key={t.v} value={t.v}>{t.l}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Telepon</Label>
              <Input value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="0812xxxx" data-testid="cf-phone" />
            </div>
            <div className="space-y-1.5">
              <Label>Email</Label>
              <Input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} placeholder="email@domain.id" data-testid="cf-email" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Kota</Label>
            <CitySelect value={form.city} onChange={(v) => set("city", v)} testId="cf-city" />
          </div>
          <div className="space-y-1.5">
            <Label>Alamat</Label>
            <Textarea value={form.address} onChange={(e) => set("address", e.target.value)} placeholder="Alamat lengkap" data-testid="cf-address" />
          </div>
          <div className="space-y-1.5">
            <Label>Catatan</Label>
            <Textarea value={form.notes} onChange={(e) => set("notes", e.target.value)} placeholder="Preferensi / catatan" data-testid="cf-notes" />
          </div>
        </div>
        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="cf-cancel">Batal</button>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="cf-submit">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Simpan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

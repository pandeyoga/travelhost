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
import { Switch } from "@/components/ui/switch";

const EMPTY = { name: "", phone: "", city: "", address: "", specialties: "", note: "", active: true };

export default function WorkshopFormDialog({ open, onOpenChange, initial, onSaved }) {
  const editing = Boolean(initial && initial.id);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(editing ? {
      name: initial.name || "", phone: initial.phone || "", city: initial.city || "",
      address: initial.address || "", specialties: (initial.specialties || []).join(", "),
      note: initial.note || "", active: initial.active !== false,
    } : EMPTY);
  }, [open, editing, initial]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.name.trim()) { toast.error("Nama vendor/bengkel wajib diisi"); return; }
    setSaving(true);
    const payload = {
      name: form.name.trim(), phone: form.phone, city: form.city, address: form.address,
      specialties: form.specialties.split(",").map((s) => s.trim()).filter(Boolean),
      note: form.note, active: form.active,
    };
    try {
      if (editing) await apiClient.patch(`/workshops/${initial.id}`, payload);
      else await apiClient.post("/workshops", payload);
      toast.success(editing ? "Vendor/bengkel diperbarui" : "Vendor/bengkel ditambahkan");
      onSaved?.();
      onOpenChange(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan");
    } finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="wsh-form">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit Vendor/Bengkel" : "Tambah Vendor/Bengkel"}</DialogTitle>
          <DialogDescription>Master bengkel langganan untuk penjadwalan perawatan.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label className="text-[12px]">Nama *</Label>
            <Input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="mis. Auto2000 Pasteur" data-testid="wsh-name" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-[12px]">Telepon</Label><Input value={form.phone} onChange={(e) => set("phone", e.target.value)} data-testid="wsh-phone" /></div>
            <div><Label className="text-[12px]">Kota</Label><CitySelect value={form.city} onChange={(v) => set("city", v)} testId="wsh-city" /></div>
          </div>
          <div><Label className="text-[12px]">Alamat</Label><Input value={form.address} onChange={(e) => set("address", e.target.value)} data-testid="wsh-address" /></div>
          <div><Label className="text-[12px]">Spesialisasi (pisahkan koma)</Label><Input value={form.specialties} onChange={(e) => set("specialties", e.target.value)} placeholder="servis, rem, ac" data-testid="wsh-spec" /></div>
          <div><Label className="text-[12px]">Catatan</Label><Textarea value={form.note} onChange={(e) => set("note", e.target.value)} rows={2} data-testid="wsh-note" /></div>
          <div className="flex items-center justify-between rounded-[10px] border border-[#EFF0F2] px-3 py-2">
            <Label className="text-[12.5px]">Aktif (bisa dipilih)</Label>
            <Switch checked={form.active} onCheckedChange={(v) => set("active", v)} data-testid="wsh-active" />
          </div>
        </div>
        <DialogFooter>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="wsh-save">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} {editing ? "Simpan" : "Tambah"}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

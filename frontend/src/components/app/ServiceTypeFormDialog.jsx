import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

const EMPTY = { name: "", default_interval_km: "", default_interval_days: "", active: true };

export default function ServiceTypeFormDialog({ open, onOpenChange, initial, onSaved }) {
  const editing = Boolean(initial && initial.id);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(editing ? {
      name: initial.name || "",
      default_interval_km: initial.default_interval_km ?? "",
      default_interval_days: initial.default_interval_days ?? "",
      active: initial.active !== false,
    } : EMPTY);
  }, [open, editing, initial]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.name.trim()) { toast.error("Nama jenis service wajib diisi"); return; }
    setSaving(true);
    const payload = {
      name: form.name.trim(),
      default_interval_km: form.default_interval_km === "" ? null : Number(form.default_interval_km),
      default_interval_days: form.default_interval_days === "" ? null : Number(form.default_interval_days),
      active: form.active,
    };
    try {
      if (editing) await apiClient.patch(`/service-types/${initial.id}`, payload);
      else await apiClient.post("/service-types", payload);
      toast.success(editing ? "Jenis service diperbarui" : "Jenis service ditambahkan");
      onSaved?.();
      onOpenChange(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan");
    } finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="svt-form">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit Jenis Service" : "Tambah Jenis Service"}</DialogTitle>
          <DialogDescription>Jenis service custom + interval default (km/hari) untuk servis preventif.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label className="text-[12px]">Nama *</Label>
            <Input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="mis. Ganti Oli" data-testid="svt-name" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-[12px]">Interval default (km)</Label>
              <Input type="number" value={form.default_interval_km} onChange={(e) => set("default_interval_km", e.target.value)} placeholder="5000" data-testid="svt-km" />
            </div>
            <div>
              <Label className="text-[12px]">Interval default (hari)</Label>
              <Input type="number" value={form.default_interval_days} onChange={(e) => set("default_interval_days", e.target.value)} placeholder="90" data-testid="svt-days" />
            </div>
          </div>
          <div className="flex items-center justify-between rounded-[10px] border border-[#EFF0F2] px-3 py-2">
            <Label className="text-[12.5px]">Aktif (bisa dipilih di form perawatan)</Label>
            <Switch checked={form.active} onCheckedChange={(v) => set("active", v)} data-testid="svt-active" />
          </div>
        </div>
        <DialogFooter>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="svt-save">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} {editing ? "Simpan" : "Tambah"}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

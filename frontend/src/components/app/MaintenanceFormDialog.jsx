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

const TYPES = [
  { v: "servis", l: "Servis Berkala" }, { v: "perbaikan", l: "Perbaikan" },
  { v: "kir", l: "KIR" }, { v: "pajak", l: "Pajak" }, { v: "lainnya", l: "Lainnya" },
];
const STATUSES = [
  { v: "scheduled", l: "Terjadwal" }, { v: "in_progress", l: "Sedang Berlangsung" },
  { v: "done", l: "Selesai" }, { v: "cancelled", l: "Dibatalkan" },
];
const toDateInput = (v) => (v ? String(v).slice(0, 10) : "");
const EMPTY = {
  vehicle_id: "", type: "servis", title: "", description: "", scheduled_date: "",
  start_date: "", end_date: "", odometer: "", cost: "", workshop: "", workshop_id: "", status: "scheduled", note: "",
};
const MANUAL = "__manual__";

export default function MaintenanceFormDialog({ open, onOpenChange, initial, onSaved }) {
  const editing = Boolean(initial && initial.id);
  const [form, setForm] = useState(EMPTY);
  const [vehicles, setVehicles] = useState([]);
  const [workshops, setWorkshops] = useState([]);
  const [svcTypes, setSvcTypes] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    apiClient.get("/vehicles").then((r) => setVehicles(Array.isArray(r.data) ? r.data : [])).catch(() => {});
    apiClient.get("/workshops", { params: { active: true } }).then((r) => setWorkshops(Array.isArray(r.data) ? r.data : [])).catch(() => {});
    apiClient.get("/service-types", { params: { active: true } }).then((r) => setSvcTypes(Array.isArray(r.data) ? r.data : [])).catch(() => {});
    setForm(editing ? {
      vehicle_id: initial.vehicle_id || "", type: initial.type || "servis",
      title: initial.title || "", description: initial.description || "",
      scheduled_date: toDateInput(initial.scheduled_date), start_date: toDateInput(initial.start_date),
      end_date: toDateInput(initial.end_date), odometer: initial.odometer ?? "",
      cost: initial.cost ?? "", workshop: initial.workshop || "", workshop_id: initial.workshop_id || "",
      status: initial.status || "scheduled", note: initial.note || "",
    } : EMPTY);
  }, [open, editing, initial]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const pickWorkshop = (val) => {
    if (val === MANUAL) { setForm((f) => ({ ...f, workshop_id: "" })); return; }
    const w = workshops.find((x) => x.id === val);
    setForm((f) => ({ ...f, workshop_id: val, workshop: w ? w.name : f.workshop }));
  };

  const submit = async () => {
    if (!form.vehicle_id) { toast.error("Pilih armada terlebih dahulu"); return; }
    if (!form.title.trim()) { toast.error("Judul perawatan wajib diisi"); return; }
    if (form.start_date && form.end_date && form.end_date < form.start_date) {
      toast.error("Tanggal selesai window harus ≥ tanggal mulai"); return;
    }
    setSaving(true);
    const payload = {
      vehicle_id: form.vehicle_id, type: form.type, title: form.title.trim(),
      description: form.description, scheduled_date: form.scheduled_date || null,
      start_date: form.start_date || null, end_date: form.end_date || null,
      odometer: Number(form.odometer) || 0, cost: Number(form.cost) || 0,
      workshop: form.workshop, workshop_id: form.workshop_id || null, status: form.status, note: form.note,
    };
    try {
      if (editing) await apiClient.patch(`/maintenance/${initial.id}`, payload);
      else await apiClient.post("/maintenance", payload);
      toast.success(editing ? "Perawatan diperbarui" : "Perawatan ditambahkan");
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan perawatan");
    } finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg" data-testid="maintenance-form-dialog">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit Perawatan" : "Jadwalkan Perawatan"}</DialogTitle>
          <DialogDescription>Jadwal/riwayat servis. Window (mulai–selesai) memblok ketersediaan armada.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Armada</Label>
              <Select value={form.vehicle_id} onValueChange={(v) => set("vehicle_id", v)} disabled={editing}>
                <SelectTrigger data-testid="mf-vehicle"><SelectValue placeholder="Pilih armada" /></SelectTrigger>
                <SelectContent>
                  {vehicles.map((v) => <SelectItem key={v.id} value={v.id}>{v.code} · {v.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Jenis</Label>
              <Select value={form.type} onValueChange={(v) => set("type", v)}>
                <SelectTrigger data-testid="mf-type"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TYPES.map((t) => <SelectItem key={t.v} value={t.v}>{t.l}</SelectItem>)}
                  {svcTypes.map((s) => <SelectItem key={s.id} value={s.key}>{s.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Judul</Label>
            <Input value={form.title} onChange={(e) => set("title", e.target.value)} placeholder="Servis berkala 40.000 km" data-testid="mf-title" />
          </div>
          <div className="space-y-1.5">
            <Label>Deskripsi</Label>
            <Textarea value={form.description} onChange={(e) => set("description", e.target.value)} placeholder="Detail pekerjaan / sparepart" data-testid="mf-description" />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label>Tgl Jadwal</Label>
              <Input type="date" value={form.scheduled_date} onChange={(e) => set("scheduled_date", e.target.value)} data-testid="mf-scheduled" />
            </div>
            <div className="space-y-1.5">
              <Label>Window Mulai</Label>
              <Input type="date" value={form.start_date} onChange={(e) => set("start_date", e.target.value)} data-testid="mf-start" />
            </div>
            <div className="space-y-1.5">
              <Label>Window Selesai</Label>
              <Input type="date" value={form.end_date} onChange={(e) => set("end_date", e.target.value)} data-testid="mf-end" />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label>Odometer (km)</Label>
              <Input type="number" value={form.odometer} onChange={(e) => set("odometer", e.target.value)} placeholder="84000" data-testid="mf-odometer" />
            </div>
            <div className="space-y-1.5">
              <Label>Biaya (Rp)</Label>
              <Input type="number" value={form.cost} onChange={(e) => set("cost", e.target.value)} placeholder="1850000" data-testid="mf-cost" />
            </div>
            <div className="space-y-1.5">
              <Label>Status</Label>
              <Select value={form.status} onValueChange={(v) => set("status", v)}>
                <SelectTrigger data-testid="mf-status"><SelectValue /></SelectTrigger>
                <SelectContent>{STATUSES.map((s) => <SelectItem key={s.v} value={s.v}>{s.l}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Vendor / Bengkel</Label>
            <Select value={form.workshop_id || MANUAL} onValueChange={pickWorkshop}>
              <SelectTrigger data-testid="mf-workshop-select"><SelectValue placeholder="Pilih bengkel terdaftar" /></SelectTrigger>
              <SelectContent>
                {workshops.map((w) => <SelectItem key={w.id} value={w.id}>{w.name}{w.city ? ` · ${w.city}` : ""}</SelectItem>)}
                <SelectItem value={MANUAL}>(Ketik manual / Lainnya)</SelectItem>
              </SelectContent>
            </Select>
            <Input value={form.workshop} onChange={(e) => set("workshop", e.target.value)} placeholder="Nama bengkel (otomatis dari pilihan, bisa diedit)" data-testid="mf-workshop" />
          </div>
        </div>
        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="mf-cancel">Batal</button>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="mf-submit">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Simpan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

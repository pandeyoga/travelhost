import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const PERIODS = [
  { v: "monthly", l: "Bulanan" },
  { v: "weekly", l: "Mingguan" },
  { v: "per_trip", l: "Per Trip" },
];

function firstOfMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}
function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function PayoutFormDialog({ open, onOpenChange, onSaved, presetDriverId }) {
  const [drivers, setDrivers] = useState([]);
  const [form, setForm] = useState({ driver_id: "", period_type: "monthly", period_start: firstOfMonth(), period_end: today() });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    apiClient.get("/drivers").then((r) => setDrivers(Array.isArray(r.data) ? r.data : [])).catch(() => {});
    setForm({ driver_id: presetDriverId || "", period_type: "monthly", period_start: firstOfMonth(), period_end: today() });
  }, [open, presetDriverId]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.driver_id) { toast.error("Pilih driver terlebih dahulu"); return; }
    if (!form.period_start || !form.period_end || form.period_end < form.period_start) {
      toast.error("Periode tidak valid (mulai ≤ selesai)"); return;
    }
    setSaving(true);
    try {
      const r = await apiClient.post("/payroll/payouts/generate", form);
      toast.success("Payout draft dibuat dari akrual periode");
      onOpenChange(false);
      onSaved && onSaved(r.data?.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal generate payout");
    } finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="payout-form">
        <DialogHeader>
          <DialogTitle>Generate Payout Driver</DialogTitle>
          <DialogDescription>Hitung akrual dari trip SELESAI dalam periode + gaji pokok & komponen kompensasi driver.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label className="text-[12px]">Driver</Label>
            <Select value={form.driver_id} onValueChange={(v) => set("driver_id", v)} disabled={Boolean(presetDriverId)}>
              <SelectTrigger data-testid="payout-driver"><SelectValue placeholder="Pilih driver" /></SelectTrigger>
              <SelectContent>{drivers.map((d) => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-[12px]">Tipe Periode</Label>
            <Select value={form.period_type} onValueChange={(v) => set("period_type", v)}>
              <SelectTrigger data-testid="payout-period-type"><SelectValue /></SelectTrigger>
              <SelectContent>{PERIODS.map((p) => <SelectItem key={p.v} value={p.v}>{p.l}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-[12px]">Mulai</Label>
              <Input type="date" value={form.period_start} onChange={(e) => set("period_start", e.target.value)} data-testid="payout-start" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-[12px]">Selesai</Label>
              <Input type="date" value={form.period_end} onChange={(e) => set("period_end", e.target.value)} data-testid="payout-end" />
            </div>
          </div>
        </div>
        <DialogFooter>
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="payout-form-cancel">Batal</button>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="payout-form-submit">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Generate
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

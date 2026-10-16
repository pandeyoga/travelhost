import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Users } from "lucide-react";
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

export default function PayoutBulkDialog({ open, onOpenChange, onSaved }) {
  const [form, setForm] = useState({ period_type: "monthly", period_start: firstOfMonth(), period_end: today() });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) setForm({ period_type: "monthly", period_start: firstOfMonth(), period_end: today() });
  }, [open]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.period_start || !form.period_end || form.period_end < form.period_start) {
      toast.error("Periode tidak valid (mulai ≤ selesai)"); return;
    }
    setSaving(true);
    try {
      const r = await apiClient.post("/payroll/payouts/generate-bulk", form);
      const { created_count = 0, skipped_count = 0 } = r.data || {};
      toast.success(`${created_count} payout dibuat · ${skipped_count} dilewati (sudah ada)`);
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal generate massal");
    } finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="payout-bulk-form">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Users size={16} /> Generate Payout Massal</DialogTitle>
          <DialogDescription>Buat payout draft untuk SEMUA driver sekaligus pada periode ini. Driver yang sudah punya payout periode sama akan dilewati.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label className="text-[12px]">Tipe Periode</Label>
            <Select value={form.period_type} onValueChange={(v) => set("period_type", v)}>
              <SelectTrigger data-testid="bulk-period-type"><SelectValue /></SelectTrigger>
              <SelectContent>{PERIODS.map((p) => <SelectItem key={p.v} value={p.v}>{p.l}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-[12px]">Mulai</Label>
              <Input type="date" value={form.period_start} onChange={(e) => set("period_start", e.target.value)} data-testid="bulk-start" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-[12px]">Selesai</Label>
              <Input type="date" value={form.period_end} onChange={(e) => set("period_end", e.target.value)} data-testid="bulk-end" />
            </div>
          </div>
        </div>
        <DialogFooter>
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="bulk-cancel">Batal</button>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="bulk-submit">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Users size={14} />} Generate Massal
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

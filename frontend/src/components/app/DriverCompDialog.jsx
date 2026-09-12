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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const EMPTY = {
  base_salary_monthly: "", commission_per_trip: "", commission_pct_revenue: "", allowance_per_km: "",
  revenue_base: "trip", enable_base: true, enable_commission_trip: false,
  enable_commission_pct: false, enable_allowance_km: false,
};

function CompRow({ label, hint, enabled, onToggle, children, testId }) {
  return (
    <div className="rounded-[10px] border border-[#EFF0F2] px-3 py-2.5">
      <div className="flex items-center justify-between">
        <div>
          <Label className="text-[12.5px] font-semibold">{label}</Label>
          {hint ? <p className="text-[11px] text-[#8E8E93]">{hint}</p> : null}
        </div>
        <Switch checked={enabled} onCheckedChange={onToggle} data-testid={testId} />
      </div>
      {enabled ? <div className="mt-2">{children}</div> : null}
    </div>
  );
}

export default function DriverCompDialog({ open, onOpenChange, driverId, driverName, onSaved }) {
  const [form, setForm] = useState(EMPTY);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !driverId) return;
    setLoading(true);
    apiClient.get(`/drivers/${driverId}/compensation`)
      .then((r) => {
        const c = r.data?.comp || {};
        setForm({
          base_salary_monthly: c.base_salary_monthly ?? "",
          commission_per_trip: c.commission_per_trip ?? "",
          commission_pct_revenue: c.commission_pct_revenue ?? "",
          allowance_per_km: c.allowance_per_km ?? "",
          revenue_base: c.revenue_base || "trip",
          enable_base: c.enable_base !== false,
          enable_commission_trip: Boolean(c.enable_commission_trip),
          enable_commission_pct: Boolean(c.enable_commission_pct),
          enable_allowance_km: Boolean(c.enable_allowance_km),
        });
      })
      .catch(() => toast.error("Gagal memuat kompensasi"))
      .finally(() => setLoading(false));
  }, [open, driverId]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    setSaving(true);
    const payload = {
      base_salary_monthly: Number(form.base_salary_monthly) || 0,
      commission_per_trip: Number(form.commission_per_trip) || 0,
      commission_pct_revenue: Number(form.commission_pct_revenue) || 0,
      allowance_per_km: Number(form.allowance_per_km) || 0,
      revenue_base: form.revenue_base,
      enable_base: form.enable_base,
      enable_commission_trip: form.enable_commission_trip,
      enable_commission_pct: form.enable_commission_pct,
      enable_allowance_km: form.enable_allowance_km,
    };
    try {
      await apiClient.patch(`/drivers/${driverId}/compensation`, payload);
      toast.success("Kompensasi driver disimpan");
      onSaved && onSaved();
      onOpenChange(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan kompensasi");
    } finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] max-w-md overflow-y-auto" data-testid="driver-comp-form">
        <DialogHeader>
          <DialogTitle>Kompensasi Driver</DialogTitle>
          <DialogDescription>{driverName ? `${driverName} · ` : ""}atur gaji pokok + komponen (bisa aktif/nonaktif per komponen).</DialogDescription>
        </DialogHeader>
        {loading ? (
          <div className="py-10 text-center text-[13px] text-[#8E8E93]" data-testid="driver-comp-loading">Memuat…</div>
        ) : (
          <div className="space-y-2.5">
            <CompRow label="Gaji Pokok (bulanan)" hint="Diprorata untuk periode mingguan; 0 untuk per-trip." enabled={form.enable_base} onToggle={(v) => set("enable_base", v)} testId="comp-toggle-base">
              <Input type="number" value={form.base_salary_monthly} onChange={(e) => set("base_salary_monthly", e.target.value)} placeholder="4000000" data-testid="comp-base" />
            </CompRow>
            <CompRow label="Komisi per Trip" hint="Nominal per trip selesai." enabled={form.enable_commission_trip} onToggle={(v) => set("enable_commission_trip", v)} testId="comp-toggle-trip">
              <Input type="number" value={form.commission_per_trip} onChange={(e) => set("commission_per_trip", e.target.value)} placeholder="50000" data-testid="comp-trip" />
            </CompRow>
            <CompRow label="Komisi % Revenue" hint="Persen dari revenue trip pada periode." enabled={form.enable_commission_pct} onToggle={(v) => set("enable_commission_pct", v)} testId="comp-toggle-pct">
              <div className="space-y-2">
                <Input type="number" value={form.commission_pct_revenue} onChange={(e) => set("commission_pct_revenue", e.target.value)} placeholder="5 (%)" data-testid="comp-pct" />
                <div>
                  <Label className="text-[11px] text-[#6B6B73]">Dasar revenue</Label>
                  <Select value={form.revenue_base} onValueChange={(v) => set("revenue_base", v)}>
                    <SelectTrigger data-testid="comp-revenue-base"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="trip">Revenue Trip</SelectItem>
                      <SelectItem value="booking">Total Booking terkait</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CompRow>
            <CompRow label="Uang Jalan per KM" hint="Nominal per km tempuh (odometer/OSRM)." enabled={form.enable_allowance_km} onToggle={(v) => set("enable_allowance_km", v)} testId="comp-toggle-km">
              <Input type="number" value={form.allowance_per_km} onChange={(e) => set("allowance_per_km", e.target.value)} placeholder="500" data-testid="comp-km" />
            </CompRow>
          </div>
        )}
        <DialogFooter>
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="driver-comp-cancel">Batal</button>
          <button className="primary-button" disabled={saving || loading} onClick={submit} data-testid="driver-comp-save">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Simpan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

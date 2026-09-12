import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const toDateInput = (v) => (v ? String(v).slice(0, 10) : "");

export default function PreventiveConfigDialog({ open, vehicle, onOpenChange, onSaved }) {
  const [km, setKm] = useState("");
  const [days, setDays] = useState("");
  const [lastOdo, setLastOdo] = useState("");
  const [lastDate, setLastDate] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && vehicle) {
      setKm(vehicle?.km?.interval_km ?? "");
      setDays(vehicle?.date?.interval_days ?? "");
      setLastOdo(vehicle?.last_service_odometer ?? "");
      setLastDate(toDateInput(vehicle?.last_service_date));
    }
  }, [open, vehicle]);

  const submit = async () => {
    setSaving(true);
    try {
      await apiClient.patch(`/vehicles/${vehicle.vehicle_id}`, {
        service_interval_km: km === "" ? null : Number(km),
        service_interval_days: days === "" ? null : Number(days),
        last_service_odometer: lastOdo === "" ? null : Number(lastOdo),
        last_service_date: lastDate || null,
      });
      toast.success("Interval servis disimpan");
      onSaved?.();
      onOpenChange(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan interval");
    } finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="mp-config-dialog">
        <DialogHeader>
          <DialogTitle>Atur Interval Servis</DialogTitle>
          <DialogDescription>{vehicle?.vehicle_name || "Armada"} — servis preventif berdasarkan jarak & waktu.</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label className="text-[12px]">Interval (km)</Label>
            <Input type="number" value={km} onChange={(e) => setKm(e.target.value)} placeholder="10000" data-testid="mp-cfg-km" />
          </div>
          <div>
            <Label className="text-[12px]">Interval (hari)</Label>
            <Input type="number" value={days} onChange={(e) => setDays(e.target.value)} placeholder="180" data-testid="mp-cfg-days" />
          </div>
          <div>
            <Label className="text-[12px]">Odometer Servis Terakhir</Label>
            <Input type="number" value={lastOdo} onChange={(e) => setLastOdo(e.target.value)} placeholder="80000" data-testid="mp-cfg-odo" />
          </div>
          <div>
            <Label className="text-[12px]">Tanggal Servis Terakhir</Label>
            <Input type="date" value={lastDate} onChange={(e) => setLastDate(e.target.value)} data-testid="mp-cfg-date" />
          </div>
        </div>
        <DialogFooter>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="mp-cfg-save">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Simpan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

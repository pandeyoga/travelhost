import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, MapPin, User2, Bus, Wallet } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCurrency } from "@/utils/formatters";

// AssignTripDialog — E3: pilih driver + unit untuk sebuah booking; tujuan di-geocode otomatis (Nominatim).
// Fee driver /hari opsional per keberangkatan (masuk saldo driver saat trip selesai).
export default function AssignTripDialog({ open, onOpenChange, booking, onSaved }) {
  const [drivers, setDrivers] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [driverId, setDriverId] = useState("");
  const [vehicleId, setVehicleId] = useState("");
  const [feeRate, setFeeRate] = useState("");
  const [tripHasFee, setTripHasFee] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    Promise.all([apiClient.get("/drivers"), apiClient.get("/vehicles")])
      .then(([d, v]) => {
        setDrivers(Array.isArray(d.data) ? d.data : []);
        setVehicles(Array.isArray(v.data) ? v.data : []);
      })
      .catch(() => {});
    setDriverId(booking?.driver_id || "");
    setVehicleId(booking?.vehicle_id || "");
    setFeeRate("");
    setTripHasFee(false);
    // Prefill rate fee yang sudah tersimpan (re-assign) — kosong = fee dihapus, jadi harus
    // terlihat nilai lamanya agar tidak terhapus tanpa sadar.
    if (booking?.id) {
      apiClient.get(`/dispatch/${booking.id}/detail`)
        .then((r) => {
          const rate = r.data?.trip?.driver_fee_rate;
          if (rate) { setFeeRate(String(rate)); setTripHasFee(true); }
        })
        .catch(() => {});
    }
  }, [open, booking]);

  // Prefill dari FEE DEFAULT driver terpilih (master Driver) — hanya bila trip belum punya
  // rate & field masih kosong; tetap bisa diubah per keberangkatan.
  useEffect(() => {
    if (tripHasFee || !driverId) return;
    const d = drivers.find((x) => x.id === driverId);
    if (d && Number(d.default_fee_rate) > 0) setFeeRate((cur) => cur || String(d.default_fee_rate));
  }, [driverId, drivers, tripHasFee]);

  const feeDays = (() => {
    const s = new Date(booking?.start_datetime || "").getTime();
    const e = new Date(booking?.end_datetime || "").getTime();
    if (!s || !e || e <= s) return 1;
    return Math.max(1, Math.ceil((e - s) / 86400000));
  })();

  const submit = async () => {
    if (!driverId) { toast.error("Pilih driver terlebih dahulu"); return; }
    if (!vehicleId) { toast.error("Pilih armada terlebih dahulu"); return; }
    setSaving(true);
    try {
      const r = await apiClient.post(`/dispatch/${booking.id}/assign`, {
        driver_id: driverId, vehicle_id: vehicleId,
        driver_fee_rate: Number(feeRate) > 0 ? Number(feeRate) : 0,
      });
      const geo = r.data?.geocode;
      toast.success(geo ? `Trip dijadwalkan · tujuan terpetakan: ${geo.display_name}`
        : "Trip dijadwalkan (koordinat tujuan belum ditemukan)");
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal meng-assign trip");
    } finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="assign-dialog">
        <DialogHeader>
          <DialogTitle>Assign &amp; Jadwalkan Trip</DialogTitle>
          <DialogDescription>
            {booking ? `${booking.code} · ${booking.customer_name}` : ""} — tujuan akan dipetakan otomatis.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="rounded-[12px] border border-[#EFF0F2] bg-[#FAFAFB] px-3 py-2.5 text-[12.5px] text-[#3C3C43]">
            <div className="flex items-center gap-1.5"><MapPin size={13} className="text-[#007AFF]" />
              <span className="font-semibold text-[#1C1C1E]">{booking?.origin || "-"}</span>
              <span className="text-[#8E8E93]">→</span>
              <span className="font-semibold text-[#1C1C1E]">{booking?.destination || "-"}</span>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label><User2 size={12} className="mr-1 inline" /> Driver</Label>
            <Select value={driverId} onValueChange={setDriverId}>
              <SelectTrigger data-testid="assign-driver"><SelectValue placeholder="Pilih driver" /></SelectTrigger>
              <SelectContent>
                {drivers.map((d) => <SelectItem key={d.id} value={d.id}>{d.name}{d.phone ? ` · ${d.phone}` : ""}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label><Bus size={12} className="mr-1 inline" /> Armada</Label>
            <Select value={vehicleId} onValueChange={setVehicleId}>
              <SelectTrigger data-testid="assign-vehicle"><SelectValue placeholder="Pilih armada" /></SelectTrigger>
              <SelectContent>
                {vehicles.map((v) => <SelectItem key={v.id} value={v.id}>{v.code ? `${v.code} · ` : ""}{v.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label><Wallet size={12} className="mr-1 inline" /> Fee Driver /hari (Rp) — opsional</Label>
            <Input type="number" min="0" value={feeRate} onChange={(e) => setFeeRate(e.target.value)}
              placeholder="mis. 150000 (kosong = tanpa fee)" data-testid="assign-fee-rate" />
            {Number(feeRate) > 0 ? (
              <p className="text-[11.5px] text-[#6B6B73]" data-testid="assign-fee-estimate">
                Estimasi fee: <b className="tabular-nums text-[#0F5227]">{formatCurrency(Number(feeRate) * feeDays)}</b> ({formatCurrency(Number(feeRate))} × {feeDays} hari) — masuk saldo driver saat trip selesai.
              </p>
            ) : null}
          </div>
        </div>
        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="assign-cancel">Batal</button>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="assign-save">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Jadwalkan Trip
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

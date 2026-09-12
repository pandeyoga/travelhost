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
import DestinationSelect from "@/components/app/DestinationSelect";
import PickupPointSelect from "@/components/app/PickupPointSelect";

// Edit ringan booking (driver/asal/tujuan/catatan). Tanggal & harga tidak diubah di sini
// agar invarian INV-1/INV-4 stabil (gunakan batal + booking baru untuk reschedule).
export default function BookingEditDialog({ open, onOpenChange, booking, onSaved }) {
  const [drivers, setDrivers] = useState([]);
  const [form, setForm] = useState({ driver_id: "none", origin: "", destination: "", notes: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !booking) return;
    setForm({
      driver_id: booking.driver_id || "none", origin: booking.origin || "",
      destination: booking.destination || "", notes: booking.notes || "",
    });
    apiClient.get("/drivers").then((r) => setDrivers(Array.isArray(r.data) ? r.data : [])).catch(() => {});
  }, [open, booking]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    setSaving(true);
    try {
      await apiClient.patch(`/bookings/${booking.id}`, {
        driver_id: form.driver_id === "none" ? null : form.driver_id,
        origin: form.origin, destination: form.destination, notes: form.notes,
      });
      toast.success("Booking diperbarui");
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memperbarui booking");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-md" data-testid="booking-edit-dialog">
        <DialogHeader>
          <DialogTitle>Edit Booking</DialogTitle>
          <DialogDescription>{booking?.code} · {booking?.customer_name}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label>Driver</Label>
            <Select value={form.driver_id} onValueChange={(v) => set("driver_id", v)}>
              <SelectTrigger data-testid="be-driver"><SelectValue placeholder="Pilih driver" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Tanpa driver</SelectItem>
                {drivers.map((d) => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Titik Jemput (master)</Label>
              <PickupPointSelect value={form.origin} onChange={(v) => set("origin", v)} testId="be-origin" />
            </div>
            <div className="space-y-1.5">
              <Label>Tujuan (master destinasi)</Label>
              <DestinationSelect value={form.destination} onChange={(v) => set("destination", v)} testId="be-destination" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Catatan</Label>
            <Textarea value={form.notes} onChange={(e) => set("notes", e.target.value)} data-testid="be-notes" />
          </div>
        </div>
        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="be-cancel">Batal</button>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="be-submit">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Simpan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

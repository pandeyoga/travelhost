import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, Loader2, ShieldCheck, XCircle, Calculator } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { formatCurrency, formatDateTime } from "@/utils/formatters";

export default function BookingApproveDialog({ open, onOpenChange, booking, onSaved }) {
  const [opts, setOpts] = useState({ vehicles: [], drivers: [] });
  const [form, setForm] = useState({ vehicle_id: "", driver_id: "", base_price: "" });
  const [avail, setAvail] = useState(null);
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !booking) return;
    setForm({ vehicle_id: "", driver_id: "", base_price: "" });
    setAvail(null);
    Promise.all([apiClient.get("/vehicles"), apiClient.get("/drivers")])
      .then(([v, d]) => setOpts({
        vehicles: Array.isArray(v.data) ? v.data : [],
        drivers: Array.isArray(d.data) ? d.data : [],
      })).catch(() => {});
  }, [open, booking]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    if (!open || !booking || !form.vehicle_id) { setAvail(null); return; }
    let active = true;
    setChecking(true);
    const params = new URLSearchParams({
      vehicle_id: form.vehicle_id, start: booking.start_datetime, end: booking.end_datetime, exclude_id: booking.id,
    });
    apiClient.get(`/bookings/availability?${params.toString()}`)
      .then((r) => { if (active) setAvail(r.data); })
      .catch(() => { if (active) setAvail(null); })
      .finally(() => { if (active) setChecking(false); });
    return () => { active = false; };
  }, [form.vehicle_id, open, booking]);

  const submit = useCallback(async () => {
    if (!form.vehicle_id) { toast.error("Pilih armada dulu"); return; }
    setSaving(true);
    try {
      const body = { vehicle_id: form.vehicle_id, driver_id: form.driver_id || null };
      if (Number(form.base_price) > 0) body.base_price = Number(form.base_price);
      const res = await apiClient.post(`/bookings/${booking.id}/approve`, body);
      toast.success(`Booking ${res.data.code} disetujui → ${formatCurrency(res.data.total_amount)}`);
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyetujui booking");
    } finally {
      setSaving(false);
    }
  }, [form, booking, onOpenChange, onSaved]);

  const canSubmit = form.vehicle_id && !saving && (!avail || avail.available !== false);
  if (!booking) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg" data-testid="booking-approve-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><ShieldCheck size={17} className="text-[#34C759]" /> Setujui Permintaan Booking</DialogTitle>
          <DialogDescription>{booking.code} · {booking.customer_name} — assign armada &amp; tetapkan harga.</DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="rounded-lg bg-[#F7F8FA] px-3 py-2 text-[12.5px] text-[#6B6B73] space-y-0.5" data-testid="approve-summary">
            <div>Rute: <span className="font-semibold text-[#1C1C1E]">{booking.origin || "-"} → {booking.destination || "-"}</span></div>
            <div>Jadwal: <span className="font-semibold text-[#1C1C1E]">{formatDateTime(booking.start_datetime)}</span> → {formatDateTime(booking.end_datetime)}</div>
            {booking.requested_vehicle_type ? <div>Preferensi unit: <span className="font-semibold text-[#1C1C1E]">{booking.requested_vehicle_type}</span></div> : null}
            {booking.pax ? <div>Pax: <span className="font-semibold text-[#1C1C1E]">{booking.pax}</span></div> : null}
            {booking.notes ? <div>Catatan: <span className="text-[#1C1C1E]">{booking.notes}</span></div> : null}
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Armada *</label>
              <Select value={form.vehicle_id} onValueChange={(v) => set("vehicle_id", v)}>
                <SelectTrigger data-testid="ap-vehicle"><SelectValue placeholder="Pilih armada" /></SelectTrigger>
                <SelectContent>{opts.vehicles.map((v) => <SelectItem key={v.id} value={v.id}>{v.name} ({v.plate_number})</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Driver (opsional)</label>
              <Select value={form.driver_id} onValueChange={(v) => set("driver_id", v)}>
                <SelectTrigger data-testid="ap-driver"><SelectValue placeholder="Pilih driver" /></SelectTrigger>
                <SelectContent>{opts.drivers.map((d) => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Harga Dasar (Rp) — kosongkan = hitung otomatis</label>
            <Input type="number" value={form.base_price} onChange={(e) => set("base_price", e.target.value)} placeholder="Auto dari Pricing Engine" className="tabular-nums" data-testid="ap-base-price" />
            <p className="mt-1 flex items-center gap-1 text-[11px] text-[#8A8A8E]"><Calculator size={11} /> Dikosongkan → harga dihitung dari tarif armada &amp; durasi.</p>
          </div>
          <div className="min-h-[28px]" data-testid="ap-availability">
            {checking ? (
              <span className="inline-flex items-center gap-1 text-[12px] text-[#6B6B73]"><Loader2 size={13} className="animate-spin" /> Memeriksa ketersediaan…</span>
            ) : avail && avail.available === true ? (
              <span className="status-pill tone-success"><CheckCircle2 size={12} /> Armada tersedia</span>
            ) : avail && avail.available === false ? (
              <span className="status-pill tone-danger"><XCircle size={12} /> Bentrok: {(avail.conflicts || []).map((c) => c.code).join(", ")}</span>
            ) : null}
          </div>
        </div>

        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="ap-cancel">Batal</button>
          <button className="primary-button" disabled={!canSubmit} onClick={submit} data-testid="ap-submit">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Setujui &amp; Konfirmasi
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

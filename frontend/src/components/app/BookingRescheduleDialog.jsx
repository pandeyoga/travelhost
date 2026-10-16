import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { CalendarClock, CheckCircle2, Loader2, XCircle } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { formatDateTime } from "@/utils/formatters";

function toIso(localValue) {
  if (!localValue) return "";
  const d = new Date(localValue);
  return Number.isNaN(d.getTime()) ? "" : d.toISOString();
}

// ISO (UTC) -> nilai untuk <input type=datetime-local> (waktu lokal browser).
function toLocalInput(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

export default function BookingRescheduleDialog({ open, onOpenChange, booking, onSaved }) {
  const [vehicles, setVehicles] = useState([]);
  const [form, setForm] = useState({ start: "", end: "", vehicle_id: "", reason: "" });
  const [avail, setAvail] = useState(null);
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !booking) return;
    setForm({
      start: toLocalInput(booking.start_datetime), end: toLocalInput(booking.end_datetime),
      vehicle_id: booking.vehicle_id || "", reason: "",
    });
    setAvail(null);
    apiClient.get("/vehicles").then((r) => setVehicles(Array.isArray(r.data) ? r.data : [])).catch(() => {});
  }, [open, booking]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    if (!open || !booking) return;
    const vid = form.vehicle_id || booking.vehicle_id;
    if (!vid || !form.start || !form.end) { setAvail(null); return; }
    let active = true;
    setChecking(true);
    const params = new URLSearchParams({
      vehicle_id: vid, start: toIso(form.start), end: toIso(form.end), exclude_id: booking.id,
    });
    apiClient.get(`/bookings/availability?${params.toString()}`)
      .then((r) => { if (active) setAvail(r.data); })
      .catch(() => { if (active) setAvail(null); })
      .finally(() => { if (active) setChecking(false); });
    return () => { active = false; };
  }, [form.vehicle_id, form.start, form.end, open, booking]);

  const submit = useCallback(async () => {
    if (!form.start || !form.end) { toast.error("Lengkapi tanggal mulai & selesai"); return; }
    setSaving(true);
    try {
      const res = await apiClient.post(`/bookings/${booking.id}/reschedule`, {
        start_datetime: toIso(form.start), end_datetime: toIso(form.end),
        vehicle_id: form.vehicle_id || null, reason: form.reason,
      });
      toast.success(`Booking ${res.data.code} dijadwalkan ulang`);
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menjadwalkan ulang");
    } finally {
      setSaving(false);
    }
  }, [form, booking, onOpenChange, onSaved]);

  const canSubmit = form.start && form.end && !saving && (!avail || avail.available !== false);
  if (!booking) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg" data-testid="booking-reschedule-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><CalendarClock size={17} className="text-[#007AFF]" /> Jadwal Ulang Booking</DialogTitle>
          <DialogDescription>{booking.code} · {booking.customer_name} — sistem cek ulang bentrok armada.</DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="rounded-lg bg-[#F7F8FA] px-3 py-2 text-[12.5px] text-[#6B6B73]" data-testid="reschedule-current">
            Jadwal saat ini: <span className="font-semibold text-[#1C1C1E]">{formatDateTime(booking.start_datetime)}</span> → {formatDateTime(booking.end_datetime)}
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Mulai (baru)</label>
              <Input type="datetime-local" value={form.start} onChange={(e) => set("start", e.target.value)} data-testid="rs-start" />
            </div>
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Selesai (baru)</label>
              <Input type="datetime-local" value={form.end} onChange={(e) => set("end", e.target.value)} data-testid="rs-end" />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Armada (opsional — kosongkan = tetap)</label>
            <Select value={form.vehicle_id} onValueChange={(v) => set("vehicle_id", v)}>
              <SelectTrigger data-testid="rs-vehicle"><SelectValue placeholder="Pilih armada" /></SelectTrigger>
              <SelectContent>{vehicles.map((v) => <SelectItem key={v.id} value={v.id}>{v.name} ({v.plate_number})</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Alasan (opsional)</label>
            <Input value={form.reason} onChange={(e) => set("reason", e.target.value)} placeholder="Permintaan pelanggan / armada bermasalah" data-testid="rs-reason" />
          </div>
          <div className="min-h-[28px]" data-testid="rs-availability">
            {checking ? (
              <span className="inline-flex items-center gap-1 text-[12px] text-[#6B6B73]"><Loader2 size={13} className="animate-spin" /> Memeriksa ketersediaan…</span>
            ) : avail && avail.available === true ? (
              <span className="status-pill tone-success"><CheckCircle2 size={12} /> Armada tersedia di jadwal baru</span>
            ) : avail && avail.available === false ? (
              <span className="status-pill tone-danger"><XCircle size={12} /> Bentrok: {(avail.conflicts || []).map((c) => c.code).join(", ")}</span>
            ) : null}
          </div>
        </div>

        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="rs-cancel">Batal</button>
          <button className="primary-button" disabled={!canSubmit} onClick={submit} data-testid="rs-submit">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Simpan Jadwal Baru
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

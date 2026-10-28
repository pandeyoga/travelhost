import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, CalendarClock, CheckCircle2, Loader2, XCircle } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { formatCurrency, formatDateTime } from "@/utils/formatters";

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
  const [form, setForm] = useState({ start: "", end: "", vehicle_id: "", reason: "", reprice: true });
  const [avail, setAvail] = useState(null);
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState(null); // hasil GET /reprice-preview
  const [previewing, setPreviewing] = useState(false);

  useEffect(() => {
    if (!open || !booking) return;
    setForm({
      start: toLocalInput(booking.start_datetime), end: toLocalInput(booking.end_datetime),
      vehicle_id: booking.vehicle_id || "", reason: "", reprice: true,
    });
    setAvail(null);
    setPreview(null);
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

  // Jadwal/armada berubah? Server hanya menghitung ulang harga bila ada perubahan.
  const newStart = toIso(form.start), newEnd = toIso(form.end);
  const vid = form.vehicle_id || booking?.vehicle_id || "";
  const changed = Boolean(booking) && Boolean(newStart && newEnd) && (
    new Date(newStart).getTime() !== new Date(booking.start_datetime).getTime()
    || new Date(newEnd).getTime() !== new Date(booking.end_datetime).getTime()
    || vid !== (booking.vehicle_id || ""));

  // Pratinjau harga baru (angka yang SAMA dengan yang disimpan reschedule reprice=true) —
  // debounce 400ms agar mengetik tanggal tidak memicu banyak permintaan.
  useEffect(() => {
    if (!open || !booking || !form.reprice || !changed || !vid || new Date(newEnd) <= new Date(newStart)) {
      setPreview(null); setPreviewing(false); return undefined;
    }
    let active = true;
    setPreviewing(true);
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ start: newStart, end: newEnd, vehicle_id: vid });
      apiClient.get(`/bookings/${booking.id}/reprice-preview?${params.toString()}`)
        .then((r) => { if (active) setPreview(r.data); })
        .catch((e) => { if (active) setPreview({ error: e?.response?.data?.detail || "Gagal menghitung pratinjau harga" }); })
        .finally(() => { if (active) setPreviewing(false); });
    }, 400);
    return () => { active = false; clearTimeout(timer); };
  }, [open, booking, form.reprice, changed, vid, newStart, newEnd]);

  // Server menolak harga baru < terbayar → cegah dari sini dengan pesan yang sama jelasnya.
  const belowPaid = Boolean(form.reprice && preview?.available && Number(preview.new_total) < Number(preview.paid_amount || 0));

  const submit = useCallback(async () => {
    if (!form.start || !form.end) { toast.error("Lengkapi tanggal mulai & selesai"); return; }
    setSaving(true);
    try {
      const res = await apiClient.post(`/bookings/${booking.id}/reschedule`, {
        start_datetime: toIso(form.start), end_datetime: toIso(form.end),
        vehicle_id: form.vehicle_id || null, reason: form.reason, reprice: form.reprice,
      });
      const oldTotal = Number(booking.total_amount || 0), newTotal = Number(res.data.total_amount || 0);
      toast.success(`Booking ${res.data.code} dijadwalkan ulang`, oldTotal !== newTotal
        ? { description: `Harga ${formatCurrency(oldTotal)} → ${formatCurrency(newTotal)}` } : undefined);
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menjadwalkan ulang");
    } finally {
      setSaving(false);
    }
  }, [form, booking, onOpenChange, onSaved]);

  const canSubmit = form.start && form.end && !saving && !belowPaid && (!avail || avail.available !== false);
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
          <label className="flex items-start gap-2 text-[12.5px] text-[#1C1C1E]">
            <input type="checkbox" className="mt-0.5" checked={form.reprice}
              onChange={(e) => set("reprice", e.target.checked)} data-testid="rs-reprice" />
            <span>Hitung ulang harga sesuai tarif untuk jadwal/armada baru
              <span className="block text-[11.5px] text-[#8E8E93]">Matikan untuk mempertahankan harga lama ({formatCurrency(booking.total_amount || 0)}), mis. harga nego.</span>
            </span>
          </label>
          {form.reprice && changed ? (
            <div className="rounded-lg border border-[#EFF0F2] px-3 py-2 text-[12.5px]" data-testid="rs-price-preview">
              {previewing ? (
                <span className="inline-flex items-center gap-1 text-[#6B6B73]"><Loader2 size={13} className="animate-spin" /> Menghitung harga baru…</span>
              ) : preview?.error ? (
                <span className="text-[#A8221A]" data-testid="rs-preview-error">{preview.error}</span>
              ) : preview && preview.available === false ? (
                <span className="text-[#8C4A00]" data-testid="rs-preview-unavailable">{preview.reason || "Harga otomatis tidak tersedia"} — harga lama {formatCurrency(preview.old_total)} dipertahankan.</span>
              ) : preview ? (
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[#6B6B73]">Harga lama</span>
                    <span className="tabular-nums text-[#1C1C1E]">{formatCurrency(preview.old_total)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-[#3C3C43]">Harga baru</span>
                    <span className="font-bold tabular-nums text-[#1C1C1E]" data-testid="rs-new-total">{formatCurrency(preview.new_total)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[#6B6B73]">Selisih</span>
                    <span className={`font-semibold tabular-nums ${preview.difference > 0 ? "text-[#A8221A]" : preview.difference < 0 ? "text-[#126E2C]" : "text-[#6B6B73]"}`} data-testid="rs-difference">
                      {preview.difference > 0 ? "+" : preview.difference < 0 ? "−" : ""}{formatCurrency(Math.abs(preview.difference || 0))}
                    </span>
                  </div>
                  {(preview.breakdown || []).length ? (
                    <div className="border-t border-[#F2F2F5] pt-1 text-[11.5px] text-[#8E8E93]" data-testid="rs-breakdown">
                      {preview.breakdown.map((b, i) => (
                        <div key={i} className="flex justify-between gap-2"><span className="truncate">{b.label}</span><span className="shrink-0 tabular-nums">{formatCurrency(b.amount)}</span></div>
                      ))}
                    </div>
                  ) : null}
                  {preview.promo_dropped ? (
                    <p className="text-[11.5px] text-[#8C4A00]" data-testid="rs-promo-dropped">Promo {booking.promo_code || ""} gugur — tidak berlaku untuk jadwal/unit baru.</p>
                  ) : null}
                  {belowPaid ? (
                    <p className="flex items-start gap-1.5 rounded-md bg-[#FDECEA] px-2 py-1.5 text-[11.5px] text-[#A8221A]" data-testid="rs-below-paid">
                      <AlertTriangle size={13} className="mt-[1px] shrink-0" />
                      Harga baru lebih kecil dari yang sudah dibayar ({formatCurrency(preview.paid_amount)}) — proses refund dulu atau matikan "Hitung ulang harga".
                    </p>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
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

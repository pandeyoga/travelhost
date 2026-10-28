import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, Clock, Loader2, ShieldCheck, XCircle, Calculator } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { vtypeLabel } from "@/components/app/calendar/calendarCore";
import { formatCurrency, formatDateTime } from "@/utils/formatters";

// Dua keputusan untuk permintaan `pending` — ditawarkan SAMA di daftar Booking, panel Pesanan
// Website Masuk, dan Kalender (dulu Kalender hanya punya "Setujui"):
//   confirm → POST /approve       : langsung terkonfirmasi, tanpa gerbang DP.
//   hold    → POST /approve-hold  : unit ditahan, pelanggan wajib bayar DP sebelum batas waktu.
const MODES = [
  { v: "confirm", l: "Setujui (langsung terkonfirmasi)", d: "Pesanan langsung berlaku tanpa menunggu DP.", icon: ShieldCheck },
  { v: "hold", l: "ACC + Minta DP", d: "Unit ditahan; pelanggan wajib membayar DP sebelum batas waktu.", icon: Clock },
];

export default function BookingApproveDialog({ open, onOpenChange, booking, onSaved, mode: initialMode = "confirm" }) {
  const [opts, setOpts] = useState({ vehicles: [], drivers: [] });
  const [mode, setMode] = useState(initialMode);
  const [form, setForm] = useState({ vehicle_id: "", driver_id: "", base_price: "", hold_hours: "" });
  const [avail, setAvail] = useState(null);
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !booking) return;
    setMode(initialMode === "hold" ? "hold" : "confirm");
    // Pesanan wizard sudah membawa unit pilihan pelanggan → jadikan default (bisa diganti).
    setForm({ vehicle_id: booking.vehicle_id || "", driver_id: "", base_price: "", hold_hours: "" });
    setAvail(null);
    Promise.all([apiClient.get("/vehicles"), apiClient.get("/drivers")])
      .then(([v, d]) => setOpts({
        vehicles: Array.isArray(v.data) ? v.data : [],
        drivers: Array.isArray(d.data) ? d.data : [],
      })).catch(() => {});
  }, [open, booking, initialMode]);

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
      if (mode === "hold") {
        const body = { vehicle_id: form.vehicle_id, recompute_price: true };
        if (Number(form.hold_hours) > 0) body.hold_hours = Math.round(Number(form.hold_hours));
        const { data } = await apiClient.post(`/bookings/${booking.id}/approve-hold`, body);
        toast.success(`Unit ditahan — DP ${formatCurrency(data?.dp_amount)} diminta ke pelanggan`,
          { description: `${data?.code || booking.code} · total ${formatCurrency(data?.total_amount)}` });
      } else {
        const body = { vehicle_id: form.vehicle_id, driver_id: form.driver_id || null };
        if (Number(form.base_price) > 0) body.base_price = Number(form.base_price);
        const { data } = await apiClient.post(`/bookings/${booking.id}/approve`, body);
        toast.success(`Booking ${data.code} disetujui → ${formatCurrency(data.total_amount)}`);
      }
      onOpenChange(false);
      if (onSaved) onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || (mode === "hold" ? "Gagal menahan unit" : "Gagal menyetujui booking"));
    } finally {
      setSaving(false);
    }
  }, [form, mode, booking, onOpenChange, onSaved]);

  const holdHoursValid = !form.hold_hours || (Number(form.hold_hours) >= 1 && Number(form.hold_hours) <= 168);
  const canSubmit = form.vehicle_id && !saving && holdHoursValid && (!avail || avail.available !== false);
  if (!booking) return null;

  const addOns = Array.isArray(booking.add_ons) ? booking.add_ons : [];
  const addOnSum = addOns.reduce((s, a) => s + (Number(a.amount) || 0), 0);
  const manualPrice = Number(form.base_price) > 0;
  const route = booking.route_name
    || (booking.origin || booking.destination ? `${booking.origin || "-"} → ${booking.destination || "-"}` : (booking.pickup_address || "-"));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg" data-testid="booking-approve-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><ShieldCheck size={17} className="text-[#34C759]" /> Setujui Permintaan Booking</DialogTitle>
          <DialogDescription>{booking.code} · {booking.customer_name} — pilih keputusan &amp; armada.</DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-0.5 rounded-lg bg-[#F7F8FA] px-3 py-2 text-[12.5px] text-[#6B6B73]" data-testid="approve-summary">
            <div>Rute: <span className="font-semibold text-[#1C1C1E]">{route}</span></div>
            <div>Jadwal: <span className="font-semibold text-[#1C1C1E]">{formatDateTime(booking.start_datetime)}</span> → {formatDateTime(booking.end_datetime)}</div>
            {booking.requested_vehicle_type ? <div>Preferensi unit: <span className="font-semibold text-[#1C1C1E]" data-testid="approve-vtype">{vtypeLabel(booking.requested_vehicle_type)}</span></div> : null}
            {booking.pax ? <div>Pax: <span className="font-semibold text-[#1C1C1E]">{booking.pax}</span></div> : null}
            {Number(booking.total_amount) > 0 ? (
              <div>Harga saat ini: <span className="font-semibold tabular-nums text-[#1C1C1E]">{formatCurrency(booking.total_amount)}</span>
                {booking.promo_code ? <> · promo <span className="font-semibold">{booking.promo_code}</span></> : null}</div>
            ) : null}
            {booking.notes ? <div>Catatan: <span className="text-[#1C1C1E]">{booking.notes}</span></div> : null}
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Keputusan" data-testid="ap-mode">
            {MODES.map((m) => {
              const on = mode === m.v;
              return (
                <button key={m.v} type="button" role="radio" aria-checked={on} onClick={() => setMode(m.v)}
                  data-testid={`ap-mode-${m.v}`}
                  className={`rounded-lg border px-3 py-2 text-left transition-colors ${on ? "border-[#007AFF] bg-[#EAF2FF]" : "border-[#E2E3E7] bg-white hover:border-[#B9D5FF]"}`}>
                  <span className={`flex items-center gap-1.5 text-[12.5px] font-bold ${on ? "text-[#0058CC]" : "text-[#1C1C1E]"}`}><m.icon size={13} /> {m.l}</span>
                  <span className="mt-0.5 block text-[11px] leading-snug text-[#6B6B73]">{m.d}</span>
                </button>
              );
            })}
          </div>

          <div className={`grid grid-cols-1 gap-3 ${mode === "confirm" ? "sm:grid-cols-2" : ""}`}>
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Armada *</label>
              <Select value={form.vehicle_id} onValueChange={(v) => set("vehicle_id", v)}>
                <SelectTrigger data-testid="ap-vehicle"><SelectValue placeholder="Pilih armada" /></SelectTrigger>
                <SelectContent>{opts.vehicles.map((v) => (
                  <SelectItem key={v.id} value={v.id}>{v.name} ({v.plate_number}){v.type ? ` · ${vtypeLabel(v.type)}` : ""}</SelectItem>
                ))}</SelectContent>
              </Select>
            </div>
            {mode === "confirm" ? (
              <div>
                <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Driver (opsional)</label>
                <Select value={form.driver_id} onValueChange={(v) => set("driver_id", v)}>
                  <SelectTrigger data-testid="ap-driver"><SelectValue placeholder="Pilih driver" /></SelectTrigger>
                  <SelectContent>{opts.drivers.map((d) => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            ) : null}
          </div>

          {mode === "confirm" ? (
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]" htmlFor="ap-base-price">
                Harga Dasar (Rp) — Kosongkan = dihitung otomatis dari tarif unit terpilih (add-on &amp; promo tetap)
              </label>
              <Input id="ap-base-price" type="number" min="0" value={form.base_price} onChange={(e) => set("base_price", e.target.value)} placeholder="Otomatis dari tarif unit" className="tabular-nums" data-testid="ap-base-price" />
              <p className="mt-1 flex items-start gap-1 text-[11px] text-[#8A8A8E]" data-testid="ap-price-hint">
                <Calculator size={11} className="mt-[2px] shrink-0" />
                {manualPrice
                  ? <span>Harga nego: total = {formatCurrency(Number(form.base_price) + addOnSum)}{addOnSum ? ` (termasuk add-on ${formatCurrency(addOnSum)})` : ""}{booking.promo_code ? ` · promo ${booking.promo_code} gugur` : ""}.</span>
                  : <span>Diisi = harga nego manual (promo gugur){addOnSum ? `; add-on ${formatCurrency(addOnSum)} tetap ditambahkan` : ""}.</span>}
              </p>
            </div>
          ) : (
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]" htmlFor="ap-hold-hours">Batas waktu bayar DP (jam, opsional)</label>
              <Input id="ap-hold-hours" type="number" min="1" max="168" value={form.hold_hours} onChange={(e) => set("hold_hours", e.target.value)} placeholder="Default dari pengaturan alur" className="tabular-nums" data-testid="ap-hold-hours" />
              <p className={`mt-1 text-[11px] ${holdHoursValid ? "text-[#8A8A8E]" : "text-[#A8221A]"}`} data-testid="ap-hold-hint">
                {holdHoursValid
                  ? `Harga dihitung otomatis dari tarif unit terpilih (add-on & promo tetap); DP ${booking.dp_percent ? `${Number(booking.dp_percent)}% ` : ""}diminta ke pelanggan.`
                  : "Batas waktu 1–168 jam."}
              </p>
            </div>
          )}

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
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} {mode === "hold" ? "ACC + Minta DP" : "Setujui & Konfirmasi"}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

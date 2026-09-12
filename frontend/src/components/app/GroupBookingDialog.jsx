import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, XCircle, Loader2, Plus, Trash2, Calculator, Users } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { formatCurrency } from "@/utils/formatters";
import DestinationSelect from "@/components/app/DestinationSelect";
import PickupPointSelect from "@/components/app/PickupPointSelect";

function toIso(localValue) {
  if (!localValue) return "";
  const d = new Date(localValue);
  return Number.isNaN(d.getTime()) ? "" : d.toISOString();
}
function emptyUnit() {
  return {
    vehicle_id: "", driver_id: "", origin: "", destination: "",
    start: "", end: "", base_price: "",
    avail: null, checking: false, pricing: false,
  };
}

export default function GroupBookingDialog({ open, onOpenChange, onCreated }) {
  const [opts, setOpts] = useState({ customers: [], vehicles: [], drivers: [] });
  const [customerId, setCustomerId] = useState("");
  const [note, setNote] = useState("");
  const [requireDp, setRequireDp] = useState(false);
  const [units, setUnits] = useState([emptyUnit(), emptyUnit()]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setCustomerId(""); setNote(""); setRequireDp(false);
    setUnits([emptyUnit(), emptyUnit()]);
    Promise.all([
      apiClient.get("/customers"), apiClient.get("/vehicles"), apiClient.get("/drivers"),
    ]).then(([c, v, d]) => setOpts({
      customers: Array.isArray(c.data) ? c.data : [],
      vehicles: Array.isArray(v.data) ? v.data : [],
      drivers: Array.isArray(d.data) ? d.data : [],
    })).catch(() => {});
  }, [open]);

  const setUnit = (idx, patch) => {
    setUnits((arr) => arr.map((u, i) => (i === idx ? { ...u, ...patch } : u)));
  };
  const addUnit = () => setUnits((arr) => [...arr, emptyUnit()]);
  const removeUnit = (idx) => setUnits((arr) => (arr.length > 1 ? arr.filter((_, i) => i !== idx) : arr));

  // Per-unit availability check (debounced via useEffect on identity).
  useEffect(() => {
    units.forEach((u, idx) => {
      if (!u.vehicle_id || !u.start || !u.end) return;
      // Skip re-check if avail already computed for current triple.
      if (u.avail && u.avail._key === `${u.vehicle_id}|${u.start}|${u.end}`) return;
      setUnit(idx, { checking: true });
      const params = new URLSearchParams({ vehicle_id: u.vehicle_id, start: toIso(u.start), end: toIso(u.end) });
      apiClient.get(`/bookings/availability?${params.toString()}`)
        .then((r) => setUnit(idx, {
          checking: false,
          avail: { ...r.data, _key: `${u.vehicle_id}|${u.start}|${u.end}` },
        }))
        .catch(() => setUnit(idx, { checking: false, avail: null }));
    });
  }, [units.map((u) => `${u.vehicle_id}|${u.start}|${u.end}`).join("~")]);

  // Intra-group conflict: 2 unit di dalam form pakai armada sama + waktu overlap.
  const intraConflicts = useMemo(() => {
    const conflicts = new Set();
    for (let i = 0; i < units.length; i++) {
      for (let j = i + 1; j < units.length; j++) {
        const a = units[i]; const b = units[j];
        if (!a.vehicle_id || !b.vehicle_id) continue;
        if (a.vehicle_id !== b.vehicle_id) continue;
        if (!a.start || !a.end || !b.start || !b.end) continue;
        const as = new Date(a.start).getTime(); const ae = new Date(a.end).getTime();
        const bs = new Date(b.start).getTime(); const be = new Date(b.end).getTime();
        if (as < be && bs < ae) { conflicts.add(i); conflicts.add(j); }
      }
    }
    return conflicts;
  }, [units]);

  const autoPrice = async (idx) => {
    const u = units[idx];
    if (!u.vehicle_id || !u.start || !u.end) { toast.message("Lengkapi armada & tanggal unit dulu."); return; }
    setUnit(idx, { pricing: true });
    const days = Math.max(Math.ceil((new Date(u.end).getTime() - new Date(u.start).getTime()) / 86400000) || 1, 1);
    try {
      const { data } = await apiClient.post("/pricing/quote", {
        vehicle_id: u.vehicle_id, days, start_date: toIso(u.start),
      });
      setUnit(idx, { pricing: false, base_price: String(data.total) });
      toast.success(`Unit #${idx + 1}: ${formatCurrency(data.total)} (${days} hari)`);
    } catch (e) {
      setUnit(idx, { pricing: false });
      toast.error(e?.response?.data?.detail || "Gagal menghitung harga");
    }
  };

  const grandTotal = units.reduce((sum, u) => sum + (Number(u.base_price) || 0), 0);
  const allUnitsValid = units.every((u, i) =>
    u.vehicle_id && u.start && u.end
    && u.avail && u.avail.available === true && !intraConflicts.has(i));
  const canSubmit = customerId && units.length >= 1 && allUnitsValid && !saving;

  const submit = useCallback(async () => {
    setSaving(true);
    try {
      const payload = {
        customer_id: customerId,
        note,
        require_dp: Boolean(requireDp),
        units: units.map((u) => ({
          vehicle_id: u.vehicle_id,
          driver_id: u.driver_id || null,
          origin: u.origin || "",
          destination: u.destination || "",
          start_datetime: toIso(u.start),
          end_datetime: toIso(u.end),
          base_price: Number(u.base_price) || 0,
        })),
      };
      const res = await apiClient.post("/bookings/group", payload);
      toast.success(`Rombongan dibuat: ${res.data.count} booking · Total ${formatCurrency(res.data.grand_total)}`);
      onOpenChange(false);
      if (onCreated) onCreated();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat booking rombongan");
    } finally {
      setSaving(false);
    }
  }, [customerId, note, requireDp, units, onOpenChange, onCreated]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl" data-testid="group-booking-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Users size={18} /> Buat Booking Rombongan</DialogTitle>
          <DialogDescription>
            Beberapa unit armada atau leg rute dalam satu grup. Cek ketersediaan per unit + anti-bentrok dalam grup.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="sm:col-span-1">
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Customer</label>
              <Select value={customerId} onValueChange={setCustomerId}>
                <SelectTrigger data-testid="gb-customer"><SelectValue placeholder="Pilih customer" /></SelectTrigger>
                <SelectContent>{opts.customers.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Catatan (opsional)</label>
              <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Kelompok tur/keluarga …" data-testid="gb-note" />
            </div>
          </div>

          <label className="flex cursor-pointer items-center gap-2 text-[12.5px] text-[#3a3f4a]">
            <input type="checkbox" checked={requireDp} onChange={(e) => setRequireDp(e.target.checked)} className="h-4 w-4 accent-[#007AFF]" data-testid="gb-require-dp" />
            <span><span className="font-semibold text-[#1C1C1E]">Wajib DP</span> — semua unit dibuat sebagai <em>hold</em> menunggu DP.</span>
          </label>

          <div className="rounded-xl border border-[#E5E5EA] bg-white">
            <div className="flex items-center justify-between border-b border-[#E5E5EA] px-3 py-2">
              <div className="text-[13px] font-semibold text-[#1C1C1E]">Unit dalam Grup ({units.length})</div>
              <button type="button" className="secondary-button !py-1 !text-[12px]" onClick={addUnit} data-testid="gb-add-unit">
                <Plus size={12} /> Tambah Unit
              </button>
            </div>
            <div className="divide-y divide-[#E5E5EA]">
              {units.map((u, idx) => {
                const intra = intraConflicts.has(idx);
                return (
                  <div key={idx} className="space-y-2 p-3" data-testid={`gb-unit-${idx}`}>
                    <div className="flex items-center justify-between">
                      <div className="text-[12px] font-semibold text-[#6B6B73]">Unit #{idx + 1}</div>
                      {units.length > 1 ? (
                        <button type="button" className="icon-button !h-7 !w-7 !text-[#A8221A]" onClick={() => removeUnit(idx)} title="Hapus unit" data-testid={`gb-remove-${idx}`}>
                          <Trash2 size={12} />
                        </button>
                      ) : null}
                    </div>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Armada</label>
                        <Select value={u.vehicle_id} onValueChange={(v) => setUnit(idx, { vehicle_id: v, avail: null })}>
                          <SelectTrigger data-testid={`gb-veh-${idx}`}><SelectValue placeholder="Pilih armada" /></SelectTrigger>
                          <SelectContent>{opts.vehicles.map((v) => <SelectItem key={v.id} value={v.id}>{v.name} ({v.plate_number})</SelectItem>)}</SelectContent>
                        </Select>
                      </div>
                      <div>
                        <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Driver (opsional)</label>
                        <Select value={u.driver_id} onValueChange={(v) => setUnit(idx, { driver_id: v })}>
                          <SelectTrigger data-testid={`gb-drv-${idx}`}><SelectValue placeholder="Pilih driver" /></SelectTrigger>
                          <SelectContent>{opts.drivers.map((d) => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}</SelectContent>
                        </Select>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Mulai</label>
                        <Input type="datetime-local" value={u.start} onChange={(e) => setUnit(idx, { start: e.target.value, avail: null })} data-testid={`gb-start-${idx}`} />
                      </div>
                      <div>
                        <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Selesai</label>
                        <Input type="datetime-local" value={u.end} onChange={(e) => setUnit(idx, { end: e.target.value, avail: null })} data-testid={`gb-end-${idx}`} />
                      </div>
                    </div>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Titik Jemput (master)</label>
                        <PickupPointSelect value={u.origin} onChange={(v) => setUnit(idx, { origin: v })} testId={`gb-origin-${idx}`} />
                      </div>
                      <div>
                        <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Tujuan (master destinasi)</label>
                        <DestinationSelect value={u.destination} onChange={(v) => setUnit(idx, { destination: v })} testId={`gb-destination-${idx}`} />
                      </div>
                    </div>
                    <div>
                      <div className="mb-1 flex items-center justify-between">
                        <label className="block text-[11px] font-semibold text-[#6B6B73]">Harga Dasar (Rp)</label>
                        <button type="button" onClick={() => autoPrice(idx)} disabled={u.pricing}
                          className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#007AFF] hover:underline disabled:opacity-50"
                          data-testid={`gb-auto-price-${idx}`}>
                          {u.pricing ? <Loader2 size={11} className="animate-spin" /> : <Calculator size={11} />} Hitung Otomatis
                        </button>
                      </div>
                      <Input type="number" value={u.base_price} onChange={(e) => setUnit(idx, { base_price: e.target.value })} placeholder="0" data-testid={`gb-price-${idx}`} />
                    </div>
                    <div className="min-h-[24px]" data-testid={`gb-avail-${idx}`}>
                      {intra ? (
                        <span className="status-pill tone-danger"><XCircle size={12} /> Bentrok dalam grup (armada sama waktu overlap)</span>
                      ) : u.checking ? (
                        <span className="inline-flex items-center gap-1 text-[12px] text-[#6B6B73]"><Loader2 size={12} className="animate-spin" /> Memeriksa…</span>
                      ) : u.avail && u.avail.available === true ? (
                        <span className="status-pill tone-success"><CheckCircle2 size={12} /> Tersedia</span>
                      ) : u.avail && u.avail.available === false ? (
                        <span className="status-pill tone-danger"><XCircle size={12} /> Bentrok: {(u.avail.conflicts || []).map((c) => c.code).join(", ") || "—"}</span>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="flex items-center justify-between rounded-lg bg-[#F7F8FA] px-3 py-2">
            <span className="text-[12px] text-[#6B6B73]">Grand Total ({units.length} unit)</span>
            <span className="text-[15px] font-bold tabular-nums text-[#1C1C1E]" data-testid="gb-grand-total">{formatCurrency(grandTotal)}</span>
          </div>
        </div>

        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="gb-cancel">Batal</button>
          <button className="primary-button" disabled={!canSubmit} onClick={submit} data-testid="gb-submit">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Simpan Rombongan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

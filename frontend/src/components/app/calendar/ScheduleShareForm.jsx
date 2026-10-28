// ScheduleShareForm.jsx — form pembuatan share-link jadwal keberangkatan (read-only publik).
// Kontrak: POST /api/schedule-shares (services/schedule_share.py = sumber aturan cakupan).
import { useMemo, useState } from "react";
import { Loader2, Plus, EyeOff } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import SelectField from "@/components/shared/SelectField";
import { Input } from "@/components/ui/input";
import { MONTHS, SHARE_DEFAULT_STATUSES, SHARE_STATUSES, STATUS_SHORT, pad } from "./calendarCore";

const SCOPES = [
  { v: "upcoming", l: "Jadwal mendatang", hint: "Mulai hari ini — selalu bergulir mengikuti tanggal" },
  { v: "month", l: "Bulan tertentu", hint: "Satu bulan kalender penuh" },
  { v: "range", l: "Rentang tanggal", hint: "Tanggal mulai s/d selesai (maks. 366 hari)" },
  { v: "all", l: "Semua keberangkatan", hint: "Termasuk riwayat yang sudah lewat" },
];
const DAY_OPTS = [
  { value: "7", label: "7 hari ke depan" }, { value: "14", label: "14 hari ke depan" },
  { value: "30", label: "1 bulan ke depan" }, { value: "60", label: "2 bulan ke depan" },
  { value: "90", label: "3 bulan ke depan" }, { value: "0", label: "Tanpa batas akhir" },
];
const EXPIRY_OPTS = [
  { value: "168", label: "7 hari" }, { value: "720", label: "30 hari" }, { value: "2160", label: "90 hari" },
  { value: "8760", label: "1 tahun" }, { value: "0", label: "Tanpa batas waktu" },
];
const VISIBILITY = [
  { k: "customer", l: "Nama pelanggan" },
  { k: "driver", l: "Nama sopir" },
  { k: "driver_phone", l: "Telepon sopir", needs: "driver" },
  { k: "payment", l: "Status pembayaran (tanpa nominal)" },
  { k: "notes", l: "Catatan booking" },
];

function monthOptions() {
  const now = new Date();
  return Array.from({ length: 19 }, (_, i) => {
    const d = new Date(now.getFullYear(), now.getMonth() - 6 + i, 1);
    return { value: `${d.getFullYear()}-${pad(d.getMonth() + 1)}`, label: `${MONTHS[d.getMonth()]} ${d.getFullYear()}` };
  });
}

const chip = (on) => `rounded-full border px-2.5 py-1 text-[11.5px] font-semibold transition ${on
  ? "border-[#007AFF] bg-[#EAF2FF] text-[#0058CC]" : "border-[#E5E5EA] bg-white text-[#6B6B73] hover:border-[#C7D6F5]"}`;
const label = "mb-1 block text-[11px] font-semibold uppercase tracking-wide text-[#9A9AA0]";

export default function ScheduleShareForm({ defaultMonth, vehicles = [], onCreated }) {
  const months = useMemo(monthOptions, []);
  const [form, setForm] = useState(() => ({
    label: "", scope: "upcoming", days: "30", month: defaultMonth, start: "", end: "",
    vehicle_ids: [], statuses: [...SHARE_DEFAULT_STATUSES], hours: "720",
    visibility: { customer: true, driver: true, driver_phone: false, payment: false, notes: false },
  }));
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const toggleIn = (k, v) => setForm((f) => ({ ...f, [k]: f[k].includes(v) ? f[k].filter((x) => x !== v) : [...f[k], v] }));
  const toggleVis = (k) => setForm((f) => {
    const vis = { ...f.visibility, [k]: !f.visibility[k] };
    if (k === "driver" && !vis.driver) vis.driver_phone = false;
    return { ...f, visibility: vis };
  });

  const submit = async () => {
    if (form.scope === "range" && (!form.start || !form.end)) { toast.error("Lengkapi tanggal mulai & selesai"); return; }
    if (!form.statuses.length) { toast.error("Pilih minimal satu status"); return; }
    setSaving(true);
    try {
      const body = {
        label: form.label.trim(), scope: form.scope, vehicle_ids: form.vehicle_ids,
        statuses: form.statuses, visibility: form.visibility, hours: Number(form.hours),
      };
      if (form.scope === "upcoming") body.days = Number(form.days);
      if (form.scope === "month") body.month = form.month;
      if (form.scope === "range") { body.start = form.start; body.end = form.end; }
      const res = await apiClient.post("/schedule-shares", body);
      toast.success("Tautan jadwal dibuat");
      set("label", "");
      onCreated && onCreated(res.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat tautan");
    } finally { setSaving(false); }
  };

  return (
    <div className="space-y-3.5 rounded-xl border border-[#EFF0F2] bg-[#FAFAFB] p-3.5" data-testid="dshare-form">
      <div>
        <label className={label} htmlFor="dshare-label">Nama tautan (opsional)</label>
        <Input id="dshare-label" value={form.label} maxLength={120} onChange={(e) => set("label", e.target.value)}
          placeholder="mis. Jadwal untuk Mitra Bandung" data-testid="dshare-label" />
      </div>

      <div>
        <span className={label}>Keberangkatan yang dibagikan</span>
        <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2" role="radiogroup" aria-label="Cakupan jadwal">
          {SCOPES.map((s) => (
            <label key={s.v} data-testid={`dshare-scope-${s.v}`}
              className={`flex cursor-pointer items-start gap-2 rounded-lg border bg-white p-2.5 ${form.scope === s.v ? "border-[#007AFF] ring-1 ring-[#007AFF]" : "border-[#E5E5EA]"}`}>
              <input type="radio" name="dshare-scope" className="mt-0.5" checked={form.scope === s.v} onChange={() => set("scope", s.v)} />
              <span>
                <span className="block text-[12.5px] font-semibold text-[#1C1C1E]">{s.l}</span>
                <span className="block text-[11px] text-[#8E8E93]">{s.hint}</span>
              </span>
            </label>
          ))}
        </div>
        <div className="mt-2">
          {form.scope === "upcoming" ? (
            <SelectField value={form.days} onChange={(v) => set("days", v)} options={DAY_OPTS}
              testId="dshare-days" className="w-full sm:w-[220px]" ariaLabel="Jangka waktu" />
          ) : null}
          {form.scope === "month" ? (
            <SelectField value={form.month} onChange={(v) => set("month", v)} options={months}
              testId="dshare-month" className="w-full sm:w-[220px]" ariaLabel="Bulan" />
          ) : null}
          {form.scope === "range" ? (
            <div className="flex items-center gap-1.5">
              <input type="date" value={form.start} onChange={(e) => set("start", e.target.value)} data-testid="dshare-start" aria-label="Tanggal mulai"
                className="h-9 w-[150px] rounded-lg border border-[#E5E5EA] bg-white px-2 text-[12.5px] outline-none focus:border-[#007AFF]" />
              <span className="text-[#8E8E93]">–</span>
              <input type="date" value={form.end} min={form.start || undefined} onChange={(e) => set("end", e.target.value)} data-testid="dshare-end" aria-label="Tanggal selesai"
                className="h-9 w-[150px] rounded-lg border border-[#E5E5EA] bg-white px-2 text-[12.5px] outline-none focus:border-[#007AFF]" />
            </div>
          ) : null}
        </div>
      </div>

      <div>
        <span className={label}>Armada</span>
        <div className="flex flex-wrap gap-1.5" data-testid="dshare-vehicles">
          <button type="button" className={chip(!form.vehicle_ids.length)} onClick={() => set("vehicle_ids", [])} data-testid="dshare-vehicle-all">Semua armada</button>
          {vehicles.map((v) => (
            <button key={v.id} type="button" className={chip(form.vehicle_ids.includes(v.id))}
              onClick={() => toggleIn("vehicle_ids", v.id)} data-testid={`dshare-vehicle-${v.id}`}>{v.name}</button>
          ))}
        </div>
      </div>

      <div>
        <span className={label}>Status yang ditampilkan</span>
        <div className="flex flex-wrap gap-1.5" data-testid="dshare-statuses">
          {SHARE_STATUSES.map((s) => (
            <button key={s} type="button" className={chip(form.statuses.includes(s))}
              onClick={() => toggleIn("statuses", s)} data-testid={`dshare-status-${s}`}>{STATUS_SHORT[s]}</button>
          ))}
        </div>
      </div>

      <div>
        <span className={label}>Yang boleh dilihat penerima</span>
        <div className="grid grid-cols-1 gap-1 sm:grid-cols-2" data-testid="dshare-visibility">
          {VISIBILITY.map((v) => {
            const disabled = v.needs && !form.visibility[v.needs];
            return (
              <label key={v.k} className={`flex items-center gap-2 text-[12.5px] ${disabled ? "text-[#B0B1B8]" : "text-[#1C1C1E]"}`}>
                <input type="checkbox" checked={Boolean(form.visibility[v.k])} disabled={disabled}
                  onChange={() => toggleVis(v.k)} data-testid={`dshare-vis-${v.k}`} />
                {v.l}
              </label>
            );
          })}
        </div>
        <p className="mt-1.5 flex items-start gap-1.5 text-[11px] text-[#8E8E93]">
          <EyeOff size={12} className="mt-[1px] shrink-0" />
          Tanggal, rute, armada &amp; status selalu tampil. Harga/nominal, kontak pelanggan, dan tombol aksi tidak pernah ditampilkan.
        </p>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <span className={label}>Masa berlaku tautan</span>
          <SelectField value={form.hours} onChange={(v) => set("hours", v)} options={EXPIRY_OPTS}
            testId="dshare-hours" className="w-full sm:w-[200px]" ariaLabel="Masa berlaku" />
        </div>
        <button className="primary-button justify-center" disabled={saving} onClick={submit} data-testid="dshare-create">
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />} Buat Tautan
        </button>
      </div>
    </div>
  );
}

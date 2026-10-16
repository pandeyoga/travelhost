import { useCallback, useEffect, useState } from "react";
import {
  Building2, Wallet, CalendarDays, Save, Plus, Trash2, Loader2, ShieldAlert, Calculator,
} from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { useAuth } from "@/context/AuthContext";
import { LoadingState } from "@/components/shared/DataStates";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import AutomationSettings from "@/components/app/AutomationSettings";
import BookingFlowPanel from "@/components/app/BookingFlowPanel";
import TransferRoutesPanel from "@/components/app/TransferRoutesPanel";
import WhatsAppSettings from "@/components/app/WhatsAppSettings";
import UnitRatesPanel from "@/components/app/UnitRatesPanel";

function Section({ icon: Icon, title, desc, children, onSave, saving, testId }) {
  return (
    <section className="section-card" data-testid={testId}>
      <div className="section-head">
        <div className="flex min-w-0 items-center gap-2">
          <Icon size={16} className="text-[#007AFF]" />
          <h2 className="truncate">{title}</h2>
        </div>
        <button className="primary-button flex-shrink-0" onClick={onSave} disabled={saving} data-testid={`${testId}-save`}>
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Simpan
        </button>
      </div>
      <div className="section-body space-y-3">
        {desc ? <p className="text-[12px] text-[#6B6B73]">{desc}</p> : null}
        {children}
      </div>
    </section>
  );
}

function Field({ label, children }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

// Tipe armada yang punya tarif harian (sinkron dgn services/pricing.VEHICLE_TYPES).
const VEHICLE_TYPES = [
  { k: "hiace_premio", l: "Hiace Premio" },
  { k: "hiace", l: "Hiace Commuter" },
  { k: "elf", l: "Isuzu Elf" },
  { k: "bus", l: "Medium Bus" },
  { k: "avanza", l: "Avanza / MPV" },
];

export default function Settings() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [denied, setDenied] = useState(false);
  const [company, setCompany] = useState({});
  const [pricing, setPricing] = useState({});
  const [rules, setRules] = useState({ day_rates: {} });
  const [ops, setOps] = useState({ work_hours: { open: "08:00", close: "17:00" }, holidays: [] });
  const [flow, setFlow] = useState({});
  const [newHoliday, setNewHoliday] = useState("");
  const [saving, setSaving] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await apiClient.get("/settings");
      setCompany(r.data?.company_info || {});
      setPricing(r.data?.pricing_defaults || {});
      setRules(r.data?.pricing_rules || { day_rates: {} });
      setOps(r.data?.operational || { work_hours: { open: "08:00", close: "17:00" }, holidays: [] });
      setFlow(r.data?.booking_flow || {});
      setDenied(false);
    } catch (e) {
      if (e?.response?.status === 403) setDenied(true);
      else toast.error("Gagal memuat pengaturan");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async (key, value) => {
    setSaving(key);
    try {
      await apiClient.patch("/settings", { [key]: value });
      toast.success("Pengaturan disimpan");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan");
    } finally { setSaving(""); }
  };

  const addHoliday = () => {
    if (!newHoliday) return;
    if ((ops.holidays || []).includes(newHoliday)) { toast.message("Tanggal sudah ada"); return; }
    setOps((o) => ({ ...o, holidays: [...(o.holidays || []), newHoliday].sort() }));
    setNewHoliday("");
  };
  const removeHoliday = (d) => setOps((o) => ({ ...o, holidays: (o.holidays || []).filter((x) => x !== d) }));

  if (loading) return <LoadingState testId="settings-loading" />;
  if (denied) {
    return (
      <div className="flex flex-col items-center rounded-[14px] border border-[#FFE0DC] bg-[#FFF5F4] px-6 py-16 text-center" data-testid="settings-denied">
        <ShieldAlert size={28} className="mb-3 text-[#FF3B30]" />
        <h3 className="text-base font-bold text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>Akses terbatas</h3>
        <p className="mt-1 max-w-sm text-sm text-[#6B6B73]">Halaman Pengaturan hanya dapat diakses oleh Pemilik (owner).</p>
      </div>
    );
  }

  const cf = (k, v) => setCompany((c) => ({ ...c, [k]: v }));
  const pf = (k, v) => setPricing((p) => ({ ...p, [k]: v }));
  const rf = (k, v) => setRules((r) => ({ ...r, [k]: v }));
  const drf = (type, v) => setRules((r) => ({ ...r, day_rates: { ...(r.day_rates || {}), [type]: v } }));

  const saveRules = () => {
    const dr = {};
    for (const t of VEHICLE_TYPES) dr[t.k] = Number(rules.day_rates?.[t.k]) || 0;
    save("pricing_rules", {
      day_rates: dr,
      default_day_rate: Number(rules.default_day_rate) || 0,
      driver_fee_per_day: Number(rules.driver_fee_per_day) || 0,
      toll_parking_per_day: Number(rules.toll_parking_per_day) || 0,
      weekend_surcharge_percent: Number(rules.weekend_surcharge_percent) || 0,
      holiday_surcharge_percent: Number(rules.holiday_surcharge_percent) || 0,
      dp_percent: Number(rules.dp_percent) || 0,
      rounding: Number(rules.rounding) || 0,
    });
  };

  return (
    <div className="space-y-4" data-testid="settings-page">
      <Section icon={Building2} title="Profil Perusahaan" testId="settings-company"
        saving={saving === "company_info"} onSave={() => save("company_info", company)}
        desc="Tampil di website publik (header, footer, halaman kontak) & dokumen.">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Nama Perusahaan"><Input value={company.name || ""} onChange={(e) => cf("name", e.target.value)} data-testid="set-company-name" /></Field>
          <Field label="Kota"><Input value={company.city || ""} onChange={(e) => cf("city", e.target.value)} data-testid="set-company-city" /></Field>
          <Field label="Telepon"><Input value={company.phone || ""} onChange={(e) => cf("phone", e.target.value)} data-testid="set-company-phone" /></Field>
          <Field label="WhatsApp (62...)"><Input value={company.whatsapp || ""} onChange={(e) => cf("whatsapp", e.target.value)} data-testid="set-company-wa" /></Field>
          <Field label="Email"><Input value={company.email || ""} onChange={(e) => cf("email", e.target.value)} data-testid="set-company-email" /></Field>
          <Field label="Area Layanan"><Input value={company.service_area || ""} onChange={(e) => cf("service_area", e.target.value)} data-testid="set-company-area" /></Field>
        </div>
        <Field label="Alamat"><Textarea value={company.address || ""} onChange={(e) => cf("address", e.target.value)} data-testid="set-company-address" /></Field>
      </Section>

      <Section icon={Wallet} title="Harga & Kebijakan" testId="settings-pricing"
        saving={saving === "pricing_defaults"} onSave={() => save("pricing_defaults", { ...pricing, dp_percent: Number(pricing.dp_percent) || 0, min_rental_hours: Number(pricing.min_rental_hours) || 0 })}
        desc="Default DP, durasi minimum sewa, dan kebijakan pembatalan.">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="DP Default (%) — satu sumber dgn Aturan Harga"><Input type="number" value={pricing.dp_percent ?? ""} onChange={(e) => pf("dp_percent", e.target.value)} data-testid="set-dp" /></Field>
          <Field label="Minimum Sewa (jam)"><Input type="number" value={pricing.min_rental_hours ?? ""} onChange={(e) => pf("min_rental_hours", e.target.value)} data-testid="set-minhours" /></Field>
        </div>
        <Field label="Kebijakan Pembatalan"><Textarea value={pricing.cancellation_policy || ""} onChange={(e) => pf("cancellation_policy", e.target.value)} placeholder="Mis. Pembatalan H-3 dikenakan 50% DP…" data-testid="set-cancellation" /></Field>
      </Section>

      <Section icon={Calculator} title="Aturan Harga (Pricing Engine)" testId="settings-pricing-rules"
        saving={saving === "pricing_rules"} onSave={saveRules}
        desc="Tarif dasar per tipe armada, jasa driver & tol/parkir per hari, surcharge akhir pekan & hari libur. SATU sumber harga untuk kalkulator publik, pemesanan online, penawaran, dan auto-hitung booking. Tarif KHUSUS per unit hanya diubah lewat panel Master Harga di bawah (form Armada read-only — tidak ada pintu tulis kedua).">
        <div>
          <Label>Tarif Sewa per Hari (Rp)</Label>
          <div className="mt-1.5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {VEHICLE_TYPES.map((t) => (
              <div className="space-y-1.5" key={t.k}>
                <span className="text-[12px] text-[#6B6B73]">{t.l}</span>
                <Input type="number" value={rules.day_rates?.[t.k] ?? ""} onChange={(e) => drf(t.k, e.target.value)} placeholder="0" data-testid={`set-rate-${t.k}`} />
              </div>
            ))}
            <div className="space-y-1.5">
              <span className="text-[12px] text-[#6B6B73]">Tarif Default (fallback)</span>
              <Input type="number" value={rules.default_day_rate ?? ""} onChange={(e) => rf("default_day_rate", e.target.value)} placeholder="0" data-testid="set-rate-default" />
            </div>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Jasa Driver / hari (Rp)"><Input type="number" value={rules.driver_fee_per_day ?? ""} onChange={(e) => rf("driver_fee_per_day", e.target.value)} data-testid="set-driver-fee" /></Field>
          <Field label="Tol & Parkir / hari (Rp)"><Input type="number" value={rules.toll_parking_per_day ?? ""} onChange={(e) => rf("toll_parking_per_day", e.target.value)} data-testid="set-toll-day" /></Field>
          <Field label="Surcharge Akhir Pekan (%)"><Input type="number" value={rules.weekend_surcharge_percent ?? ""} onChange={(e) => rf("weekend_surcharge_percent", e.target.value)} data-testid="set-weekend-surcharge" /></Field>
          <Field label="Surcharge Hari Libur (%)"><Input type="number" value={rules.holiday_surcharge_percent ?? ""} onChange={(e) => rf("holiday_surcharge_percent", e.target.value)} data-testid="set-holiday-surcharge" /></Field>
          <Field label="DP Saran (%)"><Input type="number" value={rules.dp_percent ?? ""} onChange={(e) => rf("dp_percent", e.target.value)} data-testid="set-rules-dp" /></Field>
          <Field label="Pembulatan (Rp)"><Input type="number" value={rules.rounding ?? ""} onChange={(e) => rf("rounding", e.target.value)} placeholder="1000" data-testid="set-rounding" /></Field>
        </div>
        <UnitRatesPanel />
      </Section>

      <Section icon={CalendarDays} title="Kalender Operasional" testId="settings-operational"
        saving={saving === "operational"} onSave={() => save("operational", ops)}
        desc="Jam operasional & hari libur (memengaruhi ketersediaan & komunikasi).">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Jam Buka"><Input type="time" value={ops.work_hours?.open || ""} onChange={(e) => setOps((o) => ({ ...o, work_hours: { ...o.work_hours, open: e.target.value } }))} data-testid="set-open" /></Field>
          <Field label="Jam Tutup"><Input type="time" value={ops.work_hours?.close || ""} onChange={(e) => setOps((o) => ({ ...o, work_hours: { ...o.work_hours, close: e.target.value } }))} data-testid="set-close" /></Field>
        </div>
        <div>
          <Label>Hari Libur</Label>
          <div className="mt-1.5 flex gap-2">
            <Input type="date" value={newHoliday} onChange={(e) => setNewHoliday(e.target.value)} className="max-w-[200px]" data-testid="set-holiday-input" />
            <button className="secondary-button" onClick={addHoliday} data-testid="set-holiday-add"><Plus size={14} /> Tambah</button>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5" data-testid="set-holiday-list">
            {(ops.holidays || []).length === 0 ? (
              <span className="text-[12px] text-[#8E8E93]">Belum ada hari libur.</span>
            ) : (ops.holidays || []).map((d) => (
              <span key={d} className="flex items-center gap-1 rounded-full bg-[#F2F2F5] px-2.5 py-1 text-[12px] text-[#1C1C1E]">
                {d}
                <button onClick={() => removeHoliday(d)} className="text-[#A0A0A8] hover:text-[#FF3B30]" data-testid={`set-holiday-del-${d}`}><Trash2 size={11} /></button>
              </span>
            ))}
          </div>
        </div>
      </Section>

      <BookingFlowPanel value={flow} onSaved={(v) => setFlow(v || {})} />
      <TransferRoutesPanel />

      <AutomationSettings />
      <WhatsAppSettings />
    </div>
  );
}

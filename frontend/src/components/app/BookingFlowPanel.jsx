import { useEffect, useState } from "react";
import { Loader2, Plus, Save, ShoppingCart, Trash2, Landmark } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

// BookingFlowPanel — pengaturan ALUR PEMESANAN ONLINE (settings.booking_flow).
//
// Dua mode sengaja disediakan karena kebiasaan tiap operator berbeda:
//   • "Tahan unit + minta DP"  → pesanan tamu langsung mengunci unit, DP dalam X jam,
//                               lewat batas otomatis dilepas (paling cepat menutup penjualan).
//   • "ACC ops dulu"          → pesanan masuk sebagai permintaan; unit baru dikunci setelah
//                               tim menyetujui (aman untuk armada yang sering dipakai kontrak).
// Semua batas waktu bisa diatur di sini — tidak ada angka mati di dalam kode.
const MODES = [
  { key: "hold_dp", title: "Tahan unit + minta DP", desc: "Pesanan tamu langsung menahan unit. Lewat batas waktu DP, hold dilepas otomatis." },
  { key: "ops_approval", title: "ACC ops dulu", desc: "Pesanan masuk sebagai permintaan. Unit dikunci & DP diminta setelah tim menyetujui." },
];

const SERVICES = [
  { key: "daily_rental", label: "Sewa harian + driver" },
  { key: "airport_transfer", label: "Antar-jemput bandara" },
];

export default function BookingFlowPanel({ value, onSaved }) {
  const [flow, setFlow] = useState(value || {});
  const [saving, setSaving] = useState(false);
  useEffect(() => { setFlow(value || {}); }, [value]);

  const set = (k, v) => setFlow((f) => ({ ...f, [k]: v }));
  const setPay = (k, v) => setFlow((f) => ({ ...f, payment: { ...(f.payment || {}), [k]: v } }));
  const accounts = flow.payment?.bank_accounts || [];
  const setAcc = (i, k, v) => setPay("bank_accounts", accounts.map((a, idx) => (idx === i ? { ...a, [k]: v } : a)));
  const addAcc = () => setPay("bank_accounts", [...accounts, { bank: "", number: "", holder: "" }]);
  const delAcc = (i) => setPay("bank_accounts", accounts.filter((_, idx) => idx !== i));

  const toggleService = (key) => {
    const cur = flow.enabled_services || [];
    const next = cur.includes(key) ? cur.filter((s) => s !== key) : [...cur, key];
    if (!next.length) { toast.error("Minimal satu layanan harus aktif"); return; }
    set("enabled_services", next);
  };

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        mode: flow.mode || "hold_dp",
        hold_hours: Number(flow.hold_hours) || 2,
        approval_hold_hours: Number(flow.approval_hold_hours) || 24,
        approval_sla_hours: Number(flow.approval_sla_hours) || 6,
        min_lead_hours: Number(flow.min_lead_hours) || 0,
        max_advance_days: Number(flow.max_advance_days) || 180,
        min_days: Number(flow.min_days) || 1,
        max_days: Number(flow.max_days) || 30,
        transfer_buffer_minutes: Number(flow.transfer_buffer_minutes) || 0,
        enabled_services: flow.enabled_services || ["daily_rental"],
        payment: {
          bank_accounts: accounts.filter((a) => (a.bank || "").trim() && (a.number || "").trim()),
          qris_media_id: flow.payment?.qris_media_id || "",
          instructions: flow.payment?.instructions || "",
        },
        cancellation_policy: flow.cancellation_policy || "",
        terms: flow.terms || "",
      };
      const { data } = await apiClient.patch("/settings", { booking_flow: payload });
      toast.success("Alur pemesanan disimpan");
      onSaved?.(data?.booking_flow);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan alur pemesanan");
    } finally { setSaving(false); }
  };

  return (
    <section className="section-card" data-testid="settings-booking-flow">
      <div className="section-head">
        <div className="flex min-w-0 items-center gap-2">
          <ShoppingCart size={16} className="text-[#007AFF]" />
          <h2 className="truncate">Alur Pemesanan Online</h2>
        </div>
        <button className="primary-button flex-shrink-0" onClick={save} disabled={saving}
          data-testid="settings-booking-flow-save">
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Simpan
        </button>
      </div>
      <div className="section-body space-y-4">
        <p className="text-[12px] text-[#6B6B73]">
          Menentukan apa yang terjadi saat pengunjung website menekan “Pesan”: unit langsung
          ditahan dengan batas waktu DP, atau menunggu persetujuan tim lebih dulu.
        </p>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {MODES.map((m) => {
            const active = (flow.mode || "hold_dp") === m.key;
            return (
              <button key={m.key} type="button" onClick={() => set("mode", m.key)}
                data-testid={`booking-mode-${m.key}`}
                className={`rounded-[12px] border p-3.5 text-left transition ${
                  active ? "border-[#007AFF] bg-[#F0F7FF]" : "border-[#E5E5EA] bg-white hover:border-[#C7C7CC]"}`}>
                <p className="text-[13.5px] font-semibold text-[#1C1C1E]">{m.title}</p>
                <p className="mt-1 text-[12px] leading-relaxed text-[#6B6B73]">{m.desc}</p>
              </button>
            );
          })}
        </div>

        <div>
          <Label>Layanan yang dibuka online</Label>
          <div className="mt-1.5 flex flex-wrap gap-2">
            {SERVICES.map((s) => {
              const on = (flow.enabled_services || []).includes(s.key);
              return (
                <button key={s.key} type="button" onClick={() => toggleService(s.key)}
                  data-testid={`booking-service-toggle-${s.key}`}
                  className={`rounded-full border px-3.5 py-1.5 text-[12.5px] font-medium transition ${
                    on ? "border-[#007AFF] bg-[#F0F7FF] text-[#0A5BD3]" : "border-[#E5E5EA] text-[#6B6B73]"}`}>
                  {s.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-1.5"><Label>Batas DP mode tahan (jam)</Label>
            <Input type="number" min="1" max="168" value={flow.hold_hours ?? ""}
              onChange={(e) => set("hold_hours", e.target.value)} data-testid="bf-hold-hours" /></div>
          <div className="space-y-1.5"><Label>Batas DP setelah ACC (jam)</Label>
            <Input type="number" min="1" max="168" value={flow.approval_hold_hours ?? ""}
              onChange={(e) => set("approval_hold_hours", e.target.value)} data-testid="bf-approval-hold" /></div>
          <div className="space-y-1.5"><Label>Janji waktu ACC (jam)</Label>
            <Input type="number" min="1" max="168" value={flow.approval_sla_hours ?? ""}
              onChange={(e) => set("approval_sla_hours", e.target.value)} data-testid="bf-approval-sla" /></div>
          <div className="space-y-1.5"><Label>Minimal pesan sebelum jalan (jam)</Label>
            <Input type="number" min="0" max="168" value={flow.min_lead_hours ?? ""}
              onChange={(e) => set("min_lead_hours", e.target.value)} data-testid="bf-min-lead" /></div>
          <div className="space-y-1.5"><Label>Maksimal pesan ke depan (hari)</Label>
            <Input type="number" min="1" max="730" value={flow.max_advance_days ?? ""}
              onChange={(e) => set("max_advance_days", e.target.value)} data-testid="bf-max-advance" /></div>
          <div className="space-y-1.5"><Label>Durasi minimal (hari)</Label>
            <Input type="number" min="1" max="30" value={flow.min_days ?? ""}
              onChange={(e) => set("min_days", e.target.value)} data-testid="bf-min-days" /></div>
          <div className="space-y-1.5"><Label>Durasi maksimal (hari)</Label>
            <Input type="number" min="1" max="90" value={flow.max_days ?? ""}
              onChange={(e) => set("max_days", e.target.value)} data-testid="bf-max-days" /></div>
          <div className="space-y-1.5"><Label>Jeda unit setelah antar-jemput (menit)</Label>
            <Input type="number" min="0" max="720" value={flow.transfer_buffer_minutes ?? ""}
              onChange={(e) => set("transfer_buffer_minutes", e.target.value)} data-testid="bf-buffer" /></div>
        </div>

        <div className="rounded-[12px] border border-[#E5E5EA] p-3.5">
          <div className="flex items-center justify-between">
            <Label className="flex items-center gap-1.5"><Landmark size={13} /> Rekening penerima DP</Label>
            <button className="secondary-button !px-2.5 !py-1 !text-[12px]" onClick={addAcc}
              data-testid="bf-add-account"><Plus size={12} /> Tambah</button>
          </div>
          {accounts.length === 0 ? (
            <p className="mt-2 text-[12px] text-[#8E8E93]" data-testid="bf-accounts-empty">
              Belum ada rekening — halaman status pesanan akan meminta pelanggan menghubungi WhatsApp.
            </p>
          ) : (
            <div className="mt-2 space-y-2" data-testid="bf-accounts">
              {accounts.map((a, i) => (
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_1.2fr_1.4fr_auto]" key={i}>
                  <Input placeholder="Bank" value={a.bank || ""} onChange={(e) => setAcc(i, "bank", e.target.value)}
                    data-testid={`bf-acc-bank-${i}`} />
                  <Input placeholder="Nomor rekening" value={a.number || ""}
                    onChange={(e) => setAcc(i, "number", e.target.value)} data-testid={`bf-acc-number-${i}`} />
                  <Input placeholder="Atas nama" value={a.holder || ""}
                    onChange={(e) => setAcc(i, "holder", e.target.value)} data-testid={`bf-acc-holder-${i}`} />
                  <button className="icon-button !h-9 !w-9" onClick={() => delAcc(i)} title="Hapus"
                    data-testid={`bf-acc-del-${i}`}><Trash2 size={13} /></button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-1.5"><Label>Instruksi pembayaran (tampil ke pelanggan)</Label>
          <Textarea value={flow.payment?.instructions || ""} onChange={(e) => setPay("instructions", e.target.value)}
            data-testid="bf-instructions" /></div>
        <div className="space-y-1.5"><Label>Kebijakan pembatalan</Label>
          <Textarea value={flow.cancellation_policy || ""} onChange={(e) => set("cancellation_policy", e.target.value)}
            data-testid="bf-cancellation" /></div>
        <div className="space-y-1.5"><Label>Ketentuan layanan (ringkas)</Label>
          <Textarea value={flow.terms || ""} onChange={(e) => set("terms", e.target.value)}
            data-testid="bf-terms" /></div>
      </div>
    </section>
  );
}

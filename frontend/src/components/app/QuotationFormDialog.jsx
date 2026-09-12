import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Calculator, Loader2, FileText } from "lucide-react";
import apiClient from "@/services/apiClient";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import DestinationSelect from "@/components/app/DestinationSelect";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCurrency } from "@/utils/formatters";

// Tipe armada (sinkron dgn backend services/pricing.VEHICLE_TYPES).
const VEHICLE_TYPES = [
  { k: "hiace_premio", l: "Hiace Premio" },
  { k: "hiace", l: "Hiace Commuter" },
  { k: "elf", l: "Isuzu Elf" },
  { k: "bus", l: "Medium Bus" },
  { k: "avanza", l: "Avanza / MPV" },
];
const EMPTY = {
  lead_id: "", customer_name: "", phone: "", email: "", destination: "", trip_date: "",
  pax: 1, vehicle_type: "hiace_premio", days: 1, distance_km: 0, notes: "", valid_days: 7,
};

function Fld({ label, children }) {
  return <div className="space-y-1"><Label className="text-[12px]">{label}</Label>{children}</div>;
}

// Dialog buat penawaran (B2). `lead` opsional → prefill & kunci pilihan lead (dipakai dari LeadDetailDrawer).
export default function QuotationFormDialog({ open, onOpenChange, onSaved, lead = null }) {
  const [form, setForm] = useState(EMPTY);
  const [leads, setLeads] = useState([]);
  const [preview, setPreview] = useState(null);
  const [pricing, setPricing] = useState(false);
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    if (!open) return;
    setPreview(null);
    if (lead) {
      setForm({
        ...EMPTY, lead_id: lead.id, customer_name: lead.customer_name || "", phone: lead.phone || "",
        email: lead.email || "", destination: lead.destination || "", pax: lead.pax || 1,
        trip_date: (lead.trip_date || "").slice(0, 10),
      });
      return;
    }
    setForm(EMPTY);
    apiClient.get("/leads").then((r) => {
      const arr = Array.isArray(r.data) ? r.data : (r.data?.items || []);
      setLeads(arr.filter((l) => !["won", "lost"].includes(l.stage)));
    }).catch(() => setLeads([]));
  }, [open, lead]);

  const pickLead = (id) => {
    if (id === "none") { setForm((f) => ({ ...f, lead_id: "" })); return; }
    const l = leads.find((x) => x.id === id);
    if (!l) return;
    setForm((f) => ({
      ...f, lead_id: id, customer_name: l.customer_name || "", phone: l.phone || "",
      email: l.email || "", destination: l.destination || "", pax: l.pax || 1,
      trip_date: (l.trip_date || "").slice(0, 10),
    }));
  };

  const doPreview = useCallback(async () => {
    setPricing(true);
    try {
      const { data } = await apiClient.post("/pricing/quote", {
        vehicle_type: form.vehicle_type, days: Number(form.days) || 1,
        distance_km: Number(form.distance_km) || 0, start_date: form.trip_date || null,
      });
      setPreview(data);
    } catch (e) { toast.error("Gagal menghitung harga"); }
    finally { setPricing(false); }
  }, [form.vehicle_type, form.days, form.distance_km, form.trip_date]);

  const submit = async () => {
    if (!form.lead_id && !form.customer_name.trim()) { toast.message("Pilih lead atau isi nama pelanggan."); return; }
    setSaving(true);
    try {
      const { data } = await apiClient.post("/quotations", {
        lead_id: form.lead_id || null, customer_name: form.customer_name, phone: form.phone, email: form.email,
        destination: form.destination, trip_date: form.trip_date || null, pax: Number(form.pax) || 1,
        vehicle_type: form.vehicle_type, days: Number(form.days) || 1, distance_km: Number(form.distance_km) || 0,
        notes: form.notes, valid_days: Number(form.valid_days) || 7,
      });
      toast.success(`Penawaran ${data.number} dibuat`);
      onOpenChange(false);
      onSaved && onSaved(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal membuat penawaran"); }
    finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto" data-testid="quotation-form-dialog">
        <DialogHeader><DialogTitle className="flex items-center gap-2"><FileText size={18} /> Penawaran Baru</DialogTitle></DialogHeader>
        <div className="space-y-3">
          {!lead ? (
            <Fld label="Dari Lead (opsional)">
              <Select value={form.lead_id || "none"} onValueChange={pickLead}>
                <SelectTrigger data-testid="qf-lead"><SelectValue placeholder="Pilih lead…" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">— Tanpa lead (manual) —</SelectItem>
                  {leads.map((l) => <SelectItem key={l.id} value={l.id}>{l.customer_name} · {l.destination || "?"}</SelectItem>)}
                </SelectContent>
              </Select>
            </Fld>
          ) : (
            <p className="rounded-lg bg-[#007AFF08] px-3 py-2 text-[12px] text-[#0058CC]" data-testid="qf-lead-locked">Penawaran untuk lead: <b>{lead.customer_name}</b></p>
          )}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Fld label="Nama Pelanggan"><Input value={form.customer_name} onChange={(e) => set("customer_name", e.target.value)} data-testid="qf-name" /></Fld>
            <Fld label="Telepon"><Input value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="0812…" data-testid="qf-phone" /></Fld>
            <Fld label="Email"><Input value={form.email} onChange={(e) => set("email", e.target.value)} data-testid="qf-email" /></Fld>
            <Fld label="Destinasi (master)"><DestinationSelect value={form.destination} onChange={(v) => set("destination", v)} testId="qf-destination" optionsPath="/leads/destination-options" /></Fld>
            <Fld label="Tanggal Trip"><Input type="date" value={form.trip_date} onChange={(e) => set("trip_date", e.target.value)} data-testid="qf-trip-date" /></Fld>
            <Fld label="Pax"><Input type="number" value={form.pax} onChange={(e) => set("pax", e.target.value)} data-testid="qf-pax" /></Fld>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Fld label="Tipe Armada">
              <Select value={form.vehicle_type} onValueChange={(v) => set("vehicle_type", v)}>
                <SelectTrigger data-testid="qf-vehicle-type"><SelectValue /></SelectTrigger>
                <SelectContent>{VEHICLE_TYPES.map((t) => <SelectItem key={t.k} value={t.k}>{t.l}</SelectItem>)}</SelectContent>
              </Select>
            </Fld>
            <Fld label="Durasi (hari)"><Input type="number" value={form.days} onChange={(e) => set("days", e.target.value)} data-testid="qf-days" /></Fld>
            <Fld label="Jarak (km)"><Input type="number" value={form.distance_km} onChange={(e) => set("distance_km", e.target.value)} data-testid="qf-distance" /></Fld>
          </div>
          <div className="flex items-center justify-between">
            <button type="button" onClick={doPreview} disabled={pricing} className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#007AFF] hover:underline disabled:opacity-50" data-testid="qf-preview">
              {pricing ? <Loader2 size={12} className="animate-spin" /> : <Calculator size={12} />} Pratinjau Harga
            </button>
            {preview ? <span className="text-[13px] font-bold tabular-nums text-[#1C1C1E]" data-testid="qf-preview-total">Total: {formatCurrency(preview.total)}</span> : null}
          </div>
          {preview && Array.isArray(preview.breakdown) ? (
            <div className="rounded-lg border border-[#E5E5EA] bg-[#FAFAFC] px-3 py-2 text-[12px]" data-testid="qf-breakdown">
              {preview.breakdown.map((b, i) => (
                <div key={i} className="flex justify-between py-0.5"><span className="text-[#6B6B73]">{b.label}</span><span className="tabular-nums">{formatCurrency(b.amount)}</span></div>
              ))}
            </div>
          ) : null}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Fld label="Berlaku (hari)"><Input type="number" value={form.valid_days} onChange={(e) => set("valid_days", e.target.value)} data-testid="qf-valid" /></Fld>
          </div>
          <Fld label="Catatan"><Textarea value={form.notes} onChange={(e) => set("notes", e.target.value)} placeholder="Termasuk driver & tol…" data-testid="qf-notes" /></Fld>
        </div>
        <DialogFooter>
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="qf-cancel">Batal</button>
          <button className="primary-button" onClick={submit} disabled={saving} data-testid="qf-submit">{saving ? <Loader2 size={14} className="animate-spin" /> : <FileText size={14} />} Buat Penawaran</button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

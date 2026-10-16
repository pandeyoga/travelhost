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
import { formatCurrency } from "@/utils/formatters";

const toDT = (v) => (v ? String(v).slice(0, 16) : "");
const EMPTY = { booking_id: "", partner_id: "", vehicle_id: "", vehicle_label: "", start_datetime: "", end_datetime: "", cost: "", note: "" };

export default function SubcharterFormDialog({ open, onOpenChange, initial, onSaved }) {
  const editing = Boolean(initial && initial.id);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [bookings, setBookings] = useState([]);
  const [partners, setPartners] = useState([]);
  const [partnerVehicles, setPartnerVehicles] = useState([]);

  useEffect(() => {
    if (!open) return;
    apiClient.get("/partners").then((r) => setPartners(Array.isArray(r.data) ? r.data : [])).catch(() => setPartners([]));
    apiClient.get("/bookings?limit=200").then((r) => setBookings(Array.isArray(r.data) ? r.data : [])).catch(() => setBookings([]));
    setForm(editing ? {
      booking_id: initial.booking_id || "", partner_id: initial.partner_id || "",
      vehicle_id: initial.vehicle_id || "", vehicle_label: initial.vehicle_label || "",
      start_datetime: toDT(initial.start_datetime), end_datetime: toDT(initial.end_datetime),
      cost: initial.cost ?? "", note: initial.note || "",
    } : EMPTY);
  }, [open, editing, initial]);

  // Muat unit milik mitra terpilih (untuk saran unit).
  useEffect(() => {
    if (!open || !form.partner_id) { setPartnerVehicles([]); return; }
    apiClient.get(`/partners/${form.partner_id}`).then((r) => setPartnerVehicles(r.data?.vehicles || [])).catch(() => setPartnerVehicles([]));
  }, [open, form.partner_id]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const onPickBooking = (id) => {
    const bk = bookings.find((b) => b.id === id);
    setForm((f) => ({
      ...f, booking_id: id,
      start_datetime: f.start_datetime || toDT(bk?.start_datetime),
      end_datetime: f.end_datetime || toDT(bk?.end_datetime),
    }));
  };

  const submit = async () => {
    if (!form.booking_id) { toast.error("Pilih booking terlebih dahulu"); return; }
    if (!form.partner_id) { toast.error("Pilih mitra terlebih dahulu"); return; }
    if (!(Number(form.cost) > 0)) { toast.error("Biaya sewa ke mitra harus lebih dari 0"); return; }
    setSaving(true);
    const payload = {
      booking_id: form.booking_id, partner_id: form.partner_id,
      vehicle_id: form.vehicle_id || null, vehicle_label: form.vehicle_label,
      start_datetime: form.start_datetime ? new Date(form.start_datetime).toISOString() : null,
      end_datetime: form.end_datetime ? new Date(form.end_datetime).toISOString() : null,
      cost: Number(form.cost), note: form.note,
    };
    try {
      if (editing) await apiClient.patch(`/subcharters/${initial.id}`, payload);
      else await apiClient.post("/subcharters", payload);
      toast.success(editing ? "Order diperbarui" : "Order sub-charter dibuat — WA permintaan dikirim ke mitra");
      onOpenChange(false); onSaved && onSaved();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan order"); }
    finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg" data-testid="subcharter-form-dialog">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit Order Sub-charter" : "Buat Order Sub-charter"}</DialogTitle>
          <DialogDescription>Pinjam unit dari travel mitra untuk sebuah booking. Biaya menjadi COGS booking.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5"><Label>Booking</Label>
            <Select value={form.booking_id} onValueChange={onPickBooking} disabled={editing}>
              <SelectTrigger data-testid="scf-booking"><SelectValue placeholder="Pilih booking…" /></SelectTrigger>
              <SelectContent>{bookings.map((b) => <SelectItem key={b.id} value={b.id}>{b.code} — {b.customer_name} ({b.destination})</SelectItem>)}</SelectContent>
            </Select></div>
          <div className="space-y-1.5"><Label>Mitra</Label>
            <Select value={form.partner_id} onValueChange={(v) => set("partner_id", v)}>
              <SelectTrigger data-testid="scf-partner"><SelectValue placeholder="Pilih mitra…" /></SelectTrigger>
              <SelectContent>{partners.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}{p.phone ? ` · ${p.phone}` : ""}</SelectItem>)}</SelectContent>
            </Select></div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5"><Label>Unit Mitra (opsional)</Label>
              <Select value={form.vehicle_id || "none"} onValueChange={(v) => set("vehicle_id", v === "none" ? "" : v)}>
                <SelectTrigger data-testid="scf-vehicle"><SelectValue placeholder="Pilih unit…" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">— Isi manual di bawah —</SelectItem>
                  {partnerVehicles.map((v) => <SelectItem key={v.id} value={v.id}>{v.name} ({v.plate_number})</SelectItem>)}
                </SelectContent>
              </Select></div>
            <div className="space-y-1.5"><Label>Label Unit (manual)</Label>
              <Input value={form.vehicle_label} onChange={(e) => set("vehicle_label", e.target.value)} placeholder="Hiace Commuter Mitra" data-testid="scf-vehicle-label" /></div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5"><Label>Mulai</Label>
              <Input type="datetime-local" value={form.start_datetime} onChange={(e) => set("start_datetime", e.target.value)} data-testid="scf-start" /></div>
            <div className="space-y-1.5"><Label>Selesai</Label>
              <Input type="datetime-local" value={form.end_datetime} onChange={(e) => set("end_datetime", e.target.value)} data-testid="scf-end" /></div>
          </div>
          <div className="space-y-1.5"><Label>Biaya Sewa ke Mitra (COGS)</Label>
            <Input type="number" min="0" step="50000" value={form.cost} onChange={(e) => set("cost", e.target.value)} placeholder="2200000" className="tabular-nums" data-testid="scf-cost" />
            {Number(form.cost) > 0 ? <p className="text-xs tabular-nums text-[#8A8A8E]">{formatCurrency(form.cost)}</p> : null}</div>
          <div className="space-y-1.5"><Label>Catatan</Label>
            <Textarea value={form.note} onChange={(e) => set("note", e.target.value)} placeholder="Alasan pinjam / kesepakatan…" data-testid="scf-note" /></div>
        </div>
        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="scf-cancel">Batal</button>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="scf-submit">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Simpan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

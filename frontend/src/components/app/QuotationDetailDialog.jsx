import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Send, CheckCircle2, XCircle, Download, ArrowRightCircle, FileText, Pencil, Trash2 } from "lucide-react";
import QuotationEditDialog from "@/components/app/QuotationEditDialog";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import apiClient from "@/services/apiClient";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCurrency, formatDate } from "@/utils/formatters";

export const QUO = {
  draft: { l: "Draft", tone: "neutral" },
  sent: { l: "Terkirim", tone: "info" },
  accepted: { l: "Diterima", tone: "success" },
  rejected: { l: "Ditolak", tone: "danger" },
  expired: { l: "Kedaluwarsa", tone: "warning" },
  converted: { l: "Jadi Booking", tone: "purple" },
};

const toIso = (v) => (v ? new Date(v).toISOString() : null);

function Info({ label, value }) {
  return <div><p className="text-[10.5px] uppercase text-[#8E8E93]">{label}</p><p className="font-semibold text-[#1C1C1E]">{value}</p></div>;
}
function Fld({ label, children }) {
  return <div className="space-y-1"><Label className="text-[12px]">{label}</Label>{children}</div>;
}

// Detail penawaran + aksi siklus hidup (B2): kirim/terima/tolak/konversi/PDF.
export default function QuotationDetailDialog({ quotationId, open, onOpenChange, onChanged }) {
  const [quo, setQuo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [convertOpen, setConvertOpen] = useState(false);
  const [vehicles, setVehicles] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [cv, setCv] = useState({ vehicle_id: "", driver_id: "", start: "", end: "" });
  const [editOpen, setEditOpen] = useState(false);
  const [delOpen, setDelOpen] = useState(false);

  const doDelete = async () => {
    setBusy(true);
    try {
      await apiClient.delete(`/quotations/${quotationId}`);
      toast.success("Penawaran dihapus");
      setDelOpen(false); onOpenChange(false); onChanged && onChanged();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menghapus penawaran"); }
    finally { setBusy(false); }
  };

  const load = useCallback(() => {
    if (!quotationId) return;
    setLoading(true);
    apiClient.get(`/quotations/${quotationId}`).then((r) => setQuo(r.data)).catch(() => setQuo(null)).finally(() => setLoading(false));
  }, [quotationId]);
  useEffect(() => {
    if (open) { load(); setConvertOpen(false); setCv({ vehicle_id: "", driver_id: "", start: "", end: "" }); }
  }, [open, load]);
  useEffect(() => {
    if (!convertOpen) return;
    apiClient.get("/vehicles").then((r) => setVehicles((Array.isArray(r.data) ? r.data : []).filter((v) => v.status === "available"))).catch(() => {});
    apiClient.get("/drivers").then((r) => setDrivers(Array.isArray(r.data) ? r.data : [])).catch(() => {});
  }, [convertOpen]);

  const action = async (path, label) => {
    setBusy(true);
    try { await apiClient.post(`/quotations/${quotationId}/${path}`); toast.success(label); load(); onChanged && onChanged(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Aksi gagal"); }
    finally { setBusy(false); }
  };

  const downloadPdf = async () => {
    try {
      const res = await apiClient.get(`/quotations/${quotationId}/pdf`, { responseType: "blob" });
      const url = window.URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = `${quo?.number || "penawaran"}.pdf`;
      document.body.appendChild(a); a.click(); a.remove(); window.URL.revokeObjectURL(url);
    } catch (e) { toast.error("Gagal mengunduh PDF"); }
  };

  const convert = async () => {
    if (!cv.vehicle_id || !cv.start || !cv.end) { toast.message("Pilih armada & jadwal."); return; }
    setBusy(true);
    try {
      const { data } = await apiClient.post(`/quotations/${quotationId}/convert`, {
        vehicle_id: cv.vehicle_id, driver_id: cv.driver_id || null,
        start_datetime: toIso(cv.start), end_datetime: toIso(cv.end),
      });
      toast.success(`Booking ${data.booking.code} dibuat dari penawaran`);
      load(); onChanged && onChanged();
    } catch (e) { toast.error(e?.response?.data?.detail || "Konversi gagal"); }
    finally { setBusy(false); }
  };

  const st = quo ? (QUO[quo.status] || { l: quo.status, tone: "neutral" }) : null;

  return (
    <>
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto" data-testid="quotation-detail-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText size={18} /> {quo?.number || "Penawaran"}
            {st ? <span className={`status-pill tone-${st.tone}`} data-testid="qd-status">{st.l}</span> : null}
          </DialogTitle>
        </DialogHeader>
        {loading || !quo ? (
          <div className="py-10 text-center text-[13px] text-[#6B6B73]"><Loader2 className="mx-auto animate-spin" /></div>
        ) : (
          <div className="space-y-3" data-testid="qd-body">
            <div className="grid grid-cols-2 gap-2 text-[13px]">
              <Info label="Pelanggan" value={quo.customer_name} />
              <Info label="Telepon" value={quo.phone_normalized || quo.phone || "-"} />
              <Info label="Destinasi" value={quo.destination || "-"} />
              <Info label="Tanggal Trip" value={formatDate(quo.trip_date)} />
              <Info label="Pax" value={String(quo.pax || "-")} />
              <Info label="Berlaku s/d" value={formatDate(quo.valid_until)} />
            </div>
            <div className="rounded-lg border border-[#E5E5EA]">
              {(quo.items || []).map((it, i) => (
                <div key={i} className="flex justify-between border-b border-[#F2F2F5] px-3 py-2 text-[13px] last:border-0">
                  <span className="text-[#3C3C43]">{it.label}</span><span className="tabular-nums">{formatCurrency(it.amount)}</span>
                </div>
              ))}
              <div className="flex justify-between bg-[#FAFAFC] px-3 py-2 text-[14px] font-bold">
                <span>Total</span><span className="tabular-nums" data-testid="qd-total">{formatCurrency(quo.total)}</span>
              </div>
            </div>
            {quo.notes ? <p className="text-[12px] text-[#6B6B73]">Catatan: {quo.notes}</p> : null}
            {quo.booking_id ? <p className="text-[12px] font-semibold text-[#34C759]" data-testid="qd-booking-linked">Sudah dikonversi menjadi booking.</p> : null}

            <div className="flex flex-wrap gap-2">
              <button className="secondary-button" onClick={downloadPdf} data-testid="qd-pdf"><Download size={14} /> PDF</button>
              {["draft", "sent"].includes(quo.status) ? <button className="secondary-button" onClick={() => setEditOpen(true)} disabled={busy} data-testid="qd-edit"><Pencil size={14} /> Edit</button> : null}
              {["draft", "sent", "rejected", "expired"].includes(quo.status) && !quo.booking_id ? <button className="secondary-button !text-[#A8221A]" onClick={() => setDelOpen(true)} disabled={busy} data-testid="qd-delete"><Trash2 size={14} /> Hapus</button> : null}
              {["draft", "sent"].includes(quo.status) ? <button className="secondary-button" onClick={() => action("send", "Penawaran ditandai terkirim")} disabled={busy} data-testid="qd-send"><Send size={14} /> Kirim</button> : null}
              {["draft", "sent"].includes(quo.status) ? <button className="secondary-button" onClick={() => action("accept", "Penawaran diterima")} disabled={busy} data-testid="qd-accept"><CheckCircle2 size={14} /> Tandai Diterima</button> : null}
              {["draft", "sent", "accepted"].includes(quo.status) ? <button className="secondary-button" onClick={() => action("reject", "Penawaran ditolak")} disabled={busy} data-testid="qd-reject"><XCircle size={14} /> Tolak</button> : null}
              {quo.status === "accepted" && !quo.booking_id ? <button className="primary-button" onClick={() => setConvertOpen((v) => !v)} data-testid="qd-convert-toggle"><ArrowRightCircle size={14} /> Konversi ke Booking</button> : null}
            </div>

            {convertOpen && quo.status === "accepted" ? (
              <div className="space-y-2 rounded-lg border border-[#007AFF33] bg-[#007AFF08] p-3" data-testid="qd-convert-form">
                <p className="text-[12px] font-semibold text-[#0058CC]">Detail Booking</p>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <Fld label="Armada">
                    <Select value={cv.vehicle_id} onValueChange={(v) => setCv((s) => ({ ...s, vehicle_id: v }))}>
                      <SelectTrigger data-testid="qd-cv-vehicle"><SelectValue placeholder="Pilih armada…" /></SelectTrigger>
                      <SelectContent>{vehicles.map((v) => <SelectItem key={v.id} value={v.id}>{v.name} · {v.plate}</SelectItem>)}</SelectContent>
                    </Select>
                  </Fld>
                  <Fld label="Driver (opsional)">
                    <Select value={cv.driver_id || "none"} onValueChange={(v) => setCv((s) => ({ ...s, driver_id: v === "none" ? "" : v }))}>
                      <SelectTrigger data-testid="qd-cv-driver"><SelectValue placeholder="Pilih driver…" /></SelectTrigger>
                      <SelectContent><SelectItem value="none">— Tanpa driver —</SelectItem>{drivers.map((d) => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}</SelectContent>
                    </Select>
                  </Fld>
                  <Fld label="Mulai"><Input type="datetime-local" value={cv.start} onChange={(e) => setCv((s) => ({ ...s, start: e.target.value }))} data-testid="qd-cv-start" /></Fld>
                  <Fld label="Selesai"><Input type="datetime-local" value={cv.end} onChange={(e) => setCv((s) => ({ ...s, end: e.target.value }))} data-testid="qd-cv-end" /></Fld>
                </div>
                <button className="primary-button w-full" onClick={convert} disabled={busy} data-testid="qd-cv-submit">{busy ? <Loader2 size={14} className="animate-spin" /> : <ArrowRightCircle size={14} />} Buat Booking</button>
              </div>
            ) : null}
          </div>
        )}
      </DialogContent>
    </Dialog>
    <QuotationEditDialog quo={quo} open={editOpen} onOpenChange={setEditOpen} onSaved={() => { load(); onChanged && onChanged(); }} />
    <ConfirmDialog open={delOpen} onOpenChange={setDelOpen} title="Hapus penawaran?"
      description={quo ? `Penawaran ${quo.number} untuk "${quo.customer_name}" akan dihapus permanen.` : ""}
      busy={busy} onConfirm={doDelete} testId="quotation-delete-confirm" />
    </>
  );
}

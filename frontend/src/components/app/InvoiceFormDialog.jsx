import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, FileText } from "lucide-react";
import apiClient from "@/services/apiClient";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCurrency } from "@/utils/formatters";

const KINDS = [["dp", "Uang Muka (DP)"], ["settlement", "Pelunasan"], ["full", "Tagihan Penuh"]];

export default function InvoiceFormDialog({ open, onOpenChange, onSaved, presetBookingId }) {
  const [bookings, setBookings] = useState([]);
  const [bookingId, setBookingId] = useState("");
  const [kind, setKind] = useState("dp");
  const [dpPercent, setDpPercent] = useState("");
  const [dpAmount, setDpAmount] = useState("");
  const [amount, setAmount] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [notes, setNotes] = useState("");
  const [terms, setTerms] = useState(null);
  const [quote, setQuote] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setBookingId(presetBookingId || ""); setKind("dp"); setDpPercent(""); setDpAmount(""); setAmount(""); setDueAt(""); setNotes(""); setTerms(null); setQuote(null);
    apiClient.get("/bookings").then((r) => { const d = Array.isArray(r.data) ? r.data : (r.data?.items || []); setBookings(d.filter((b) => b.status !== "cancelled")); }).catch(() => setBookings([]));
  }, [open, presetBookingId]);

  useEffect(() => {
    if (!bookingId) { setQuote(null); return; }
    const q = new URLSearchParams({ booking_id: bookingId, kind });
    if (dpPercent !== "") q.set("dp_percent", dpPercent);
    apiClient.get(`/invoices/quote?${q}`).then((r) => {
      setQuote(r.data);
      if (kind === "dp" && dpAmount === "") setDpAmount("");
      setDueAt((r.data.due_at || "").slice(0, 10));
      if (kind !== "dp") setAmount(String(r.data.amount || 0));
    }).catch(() => setQuote(null));
  }, [bookingId, kind, dpPercent]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async () => {
    if (!bookingId) { toast.error("Pilih booking terlebih dahulu"); return; }
    setSaving(true);
    try {
      const body = { booking_id: bookingId, kind, due_at: dueAt ? new Date(`${dueAt}T17:00:00`).toISOString() : null, notes };
      if (kind === "dp") { if (dpPercent !== "") body.dp_percent = Number(dpPercent); if (dpAmount !== "") body.dp_amount = Number(dpAmount); }
      else if (amount !== "") body.amount = Number(amount);
      if (terms !== null) body.terms = terms;
      await apiClient.post("/invoices", body);
      toast.success("Invoice dibuat");
      onOpenChange(false); onSaved && onSaved();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal membuat invoice"); }
    finally { setSaving(false); }
  };

  const previewAmount = kind === "dp" ? (dpAmount !== "" ? Math.max(Number(dpAmount) - (quote?.paid_before || 0), 0) : quote?.amount) : (amount !== "" ? Number(amount) : quote?.amount);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg" data-testid="invoice-form-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><FileText size={17} className="text-[#007AFF]" /> Buat Invoice</DialogTitle>
          <DialogDescription>Invoice DP, pelunasan, atau tagihan penuh. Angka dihitung dari booking & pembayaran yang sudah masuk.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label>Booking</Label>
            <Select value={bookingId} onValueChange={setBookingId}>
              <SelectTrigger data-testid="inv-booking"><SelectValue placeholder="Pilih booking" /></SelectTrigger>
              <SelectContent>{bookings.map((b) => <SelectItem key={b.id} value={b.id}>{b.code} · {b.customer_name} · {formatCurrency(b.total_amount)}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Jenis invoice</Label>
            <div className="grid grid-cols-3 gap-2">
              {KINDS.map(([k, l]) => (
                <button key={k} type="button" onClick={() => setKind(k)} data-testid={`inv-kind-${k}`}
                  className={`rounded-[10px] border px-2 py-2 text-[12.5px] font-semibold transition-colors ${kind === k ? "border-[#007AFF] bg-[rgba(0,122,255,0.08)] text-[#0058CC]" : "border-[#E5E5EA] text-[#3C3C43] hover:border-[#C7C7CC]"}`}>{l}</button>
              ))}
            </div>
          </div>
          {kind === "dp" ? (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5"><Label>Persen DP (%)</Label><Input type="number" min={0} max={100} value={dpPercent} onChange={(e) => { setDpPercent(e.target.value); setDpAmount(""); }} placeholder={quote ? String(quote.dp_percent) : "30"} data-testid="inv-dp-percent" /></div>
              <div className="space-y-1.5"><Label>atau Nominal DP (Rp)</Label><Input type="number" value={dpAmount} onChange={(e) => setDpAmount(e.target.value)} placeholder={quote ? String(quote.dp_amount) : ""} data-testid="inv-dp-amount" /></div>
            </div>
          ) : (
            <div className="space-y-1.5"><Label>Nominal tagihan (Rp)</Label><Input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} data-testid="inv-amount" /></div>
          )}
          <div className="space-y-1.5"><Label>Jatuh tempo</Label><Input type="date" value={dueAt} onChange={(e) => setDueAt(e.target.value)} data-testid="inv-due" /></div>
          {quote ? (
            <div className="rounded-[10px] bg-[#F5F7FB] px-3 py-2.5 text-[12.5px]" data-testid="inv-quote">
              <div className="flex justify-between"><span className="text-[#6B6B73]">Total booking</span><span className="font-semibold tabular-nums">{formatCurrency(quote.subtotal)}</span></div>
              <div className="flex justify-between"><span className="text-[#6B6B73]">Sudah dibayar</span><span className="font-semibold tabular-nums">{formatCurrency(quote.paid_before)}</span></div>
              <div className="mt-1 flex justify-between border-t border-[#E5E5EA] pt-1"><span className="font-semibold">Tagihan ini</span><span className="text-[14px] font-bold tabular-nums text-[#0058CC]" data-testid="inv-quote-amount">{formatCurrency(previewAmount || 0)}</span></div>
              {quote.bank_accounts?.length === 0 ? <p className="mt-1 text-[11px] text-[#FF9500]">Belum ada rekening pembayaran — atur di Dokumen › DP & Rekening.</p> : null}
            </div>
          ) : null}
          <div className="space-y-1.5"><Label>Syarat pembayaran (kosongkan = bawaan konfigurasi)</Label><Textarea rows={2} value={terms ?? ""} onChange={(e) => setTerms(e.target.value)} placeholder={quote?.terms || ""} data-testid="inv-terms" /></div>
          <div className="space-y-1.5"><Label>Catatan</Label><Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="inv-notes" /></div>
        </div>
        <DialogFooter>
          <button className="secondary-button" onClick={() => onOpenChange(false)}>Batal</button>
          <button className="primary-button" onClick={submit} disabled={saving} data-testid="inv-submit">{saving ? <Loader2 size={14} className="animate-spin" /> : <FileText size={14} />} Terbitkan Invoice</button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

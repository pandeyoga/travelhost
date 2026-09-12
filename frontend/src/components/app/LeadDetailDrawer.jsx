import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Phone, Mail, MapPin, Users, CalendarDays, MessageCircle, UserCheck, ArrowRightLeft, StickyNote, CheckCircle2, FileText, Megaphone, BadgeCheck, ShieldOff, LayoutTemplate, Pencil, Trash2 } from "lucide-react";
import apiClient from "@/services/apiClient";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatusPill } from "@/components/shared/StatusPill";
import { formatDate, formatDateTime } from "@/utils/formatters";
import QuotationFormDialog from "@/components/app/QuotationFormDialog";
import BookingFormDialog from "@/components/app/BookingFormDialog";
import LeadFormDialog from "@/components/app/LeadFormDialog";
import ConfirmDialog from "@/components/shared/ConfirmDialog";

const STAGES = [["new", "Baru"], ["contacted", "Dihubungi"], ["quoted", "Penawaran"], ["negotiation", "Negosiasi"], ["won", "Menang"], ["lost", "Hilang"]];
const STAGE_TONE = { new: "info", contacted: "info", quoted: "warning", negotiation: "purple", won: "success", lost: "danger" };
const ACT_LABEL = { created: "Dibuat", note: "Catatan", call: "Telepon", stage_change: "Pindah tahap", assignment: "Penugasan", converted: "Konversi" };
const CH_LABEL = { google_ads: "Google Ads", meta_ads: "Meta Ads", tiktok_ads: "TikTok Ads", google: "Google", meta: "Meta", instagram: "Instagram", tiktok: "TikTok", whatsapp: "WhatsApp", email: "Email", referral: "Referral", website: "Website", organic: "Organik", direct: "Langsung", ads: "Iklan" };
// Sumber lead ditulis apa adanya oleh backend (mis. `landing_page`); tanpa peta label, UI
// menampilkan "Landing_page" yang terbaca seperti bug bagi pengguna.
const SRC_LABEL = { website: "Website", whatsapp: "WhatsApp", manual: "Manual", landing_page: "Halaman Iklan", public: "Situs Publik", meta_ads: "Meta Lead Ads", google_ads: "Google Lead Form", tiktok_ads: "TikTok Lead Ads" };
const srcLabel = (s) => SRC_LABEL[s] || (s ? String(s).replace(/_/g, " ") : "-");
const chLabel = (c) => CH_LABEL[c] || (c ? c.replace(/_/g, " ") : "-");
const waOf = (p) => (p ? `https://wa.me/${String(p).replace(/[^0-9]/g, "").replace(/^0/, "62")}` : null);

function Meta({ icon: Icon, label, value }) {
  return (
    <div className="rounded-[10px] border border-[#EFF0F2] bg-white p-2.5">
      <p className="flex items-center gap-1 text-[10.5px] font-semibold uppercase tracking-wide text-[#8E8E93]">{Icon ? <Icon size={11} /> : null}{label}</p>
      <p className="mt-0.5 truncate text-[13px] font-semibold capitalize text-[#1C1C1E]">{value}</p>
    </div>
  );
}

export default function LeadDetailDrawer({ leadId, open, onOpenChange, agents, onChanged }) {
  const [lead, setLead] = useState(null);
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [quoOpen, setQuoOpen] = useState(false);
  const [bookOpen, setBookOpen] = useState(false);
  const [bookPrefill, setBookPrefill] = useState(null);
  const [editOpen, setEditOpen] = useState(false);
  const [delOpen, setDelOpen] = useState(false);

  const doDelete = async () => {
    setBusy(true);
    try {
      await apiClient.delete(`/leads/${lead.id}`);
      toast.success("Lead dihapus");
      setDelOpen(false); onOpenChange(false); onChanged && onChanged();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menghapus lead"); }
    finally { setBusy(false); }
  };

  const load = () => {
    if (!leadId) return;
    setLoading(true);
    apiClient.get(`/leads/${leadId}`).then((r) => setLead(r.data)).catch(() => setLead(null)).finally(() => setLoading(false));
  };
  useEffect(() => {
    if (open && leadId) { setLead(null); setNote(""); load(); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, leadId]);

  const after = (msg) => { toast.success(msg); load(); onChanged && onChanged(); };
  const moveStage = async (stage) => {
    if (!lead || stage === lead.stage) return;
    const lost_reason = stage === "lost" ? (window.prompt("Alasan kehilangan lead?") || "") : "";
    setBusy(true);
    try { await apiClient.post(`/leads/${lead.id}/stage`, { stage, lost_reason }); after("Tahap diperbarui"); }
    catch (e) { toast.error("Gagal memperbarui tahap"); } finally { setBusy(false); }
  };
  const assign = async (uid) => {
    setBusy(true);
    try { await apiClient.post(`/leads/${lead.id}/assign`, { assigned_to: uid === "auto" ? null : uid }); after("Penugasan diperbarui"); }
    catch (e) { toast.error("Gagal menugaskan"); } finally { setBusy(false); }
  };
  const addNote = async () => {
    if (!note.trim()) return;
    setBusy(true);
    try { await apiClient.post(`/leads/${lead.id}/activities`, { type: "note", text: note.trim() }); setNote(""); after("Catatan ditambahkan"); }
    catch (e) { toast.error("Gagal menambah catatan"); } finally { setBusy(false); }
  };
  const convert = async () => {
    setBusy(true);
    try { const r = await apiClient.post(`/leads/${lead.id}/convert`, {}); after(`Dikonversi ke customer: ${r.data.customer.name}`); }
    catch (e) { toast.error(e?.response?.data?.detail || "Gagal konversi"); } finally { setBusy(false); }
  };
  const saveValue = async (v) => {
    if (!lead || Number(v) === Number(lead.value || 0)) return;
    setBusy(true);
    try { await apiClient.patch(`/leads/${lead.id}`, { value: Number(v) || 0 }); after("Nilai diperbarui"); }
    catch (e) { toast.error("Gagal menyimpan"); } finally { setBusy(false); }
  };
  // Lead → Booking: backend memastikan customer (dedupe) & mengembalikan prefill form.
  const startBooking = async () => {
    setBusy(true);
    try {
      const { data } = await apiClient.post(`/leads/${lead.id}/prepare-booking`);
      const start = data.trip_date ? `${String(data.trip_date).slice(0, 10)}T08:00` : "";
      setBookPrefill({
        initial: { customer_id: data.customer_id, destination: data.destination || "", notes: data.notes || "" },
        start,
      });
      setBookOpen(true);
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyiapkan booking"); }
    finally { setBusy(false); }
  };
  const onBookingCreated = async (bk) => {
    try {
      await apiClient.post(`/leads/${lead.id}/activities`, { type: "note", text: `Booking ${bk?.code || ""} dibuat dari lead ini` });
      if (lead.stage !== "won") await apiClient.post(`/leads/${lead.id}/stage`, { stage: "won", lost_reason: "" });
    } catch { /* aktivitas gagal bukan penghalang */ }
    setBookOpen(false);
    after(`Lead menjadi booking ${bk?.code || ""}`);
  };

  const acts = Array.isArray(lead?.activities) ? lead.activities : [];
  const wa = waOf(lead?.phone);

  return (
    <>
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-2xl" data-testid="lead-detail-drawer">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 pr-6">
            <span className="flex-1 truncate">{lead?.customer_name || "Detail Lead"}</span>
            {lead ? (
              <>
                <button className="icon-button !h-8 !w-8" title="Edit lead" onClick={() => setEditOpen(true)} data-testid="lead-edit"><Pencil size={14} /></button>
                <button className="icon-button !h-8 !w-8 !text-[#A8221A]" title="Hapus lead" onClick={() => setDelOpen(true)} data-testid="lead-delete"><Trash2 size={14} /></button>
              </>
            ) : null}
          </DialogTitle>
          <DialogDescription>Kelola tahap, penugasan, catatan & konversi lead.</DialogDescription>
        </DialogHeader>
        {loading ? (
          <div className="flex items-center justify-center py-12 text-[13px] text-[#6B6B73]" data-testid="lead-detail-loading"><Loader2 size={16} className="mr-2 animate-spin" /> Memuat lead…</div>
        ) : !lead ? (
          <div className="py-12 text-center text-[13px] text-[#6B6B73]">Gagal memuat lead.</div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-[13px] text-[#3C3C43]">
              <StatusPill value={lead.stage} tone={STAGE_TONE[lead.stage] || "neutral"} />
              {lead.phone ? <span className="inline-flex items-center gap-1.5"><Phone size={13} className="text-[#8E8E93]" />{lead.phone}</span> : null}
              {lead.email ? <span className="inline-flex items-center gap-1.5"><Mail size={13} className="text-[#8E8E93]" />{lead.email}</span> : null}
              {wa ? <a href={wa} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-md bg-[#25D366] px-2 py-1 text-[11.5px] font-semibold text-white" data-testid="lead-wa"><MessageCircle size={12} /> WhatsApp</a> : null}
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Meta icon={MapPin} label="Destinasi" value={lead.destination || "-"} />
              <Meta icon={Users} label="Pax" value={lead.pax || 0} />
              <Meta icon={CalendarDays} label="Tanggal" value={formatDate(lead.trip_date)} />
              <Meta icon={null} label="Sumber" value={srcLabel(lead.source)} />
            </div>
            <div className="rounded-[12px] border border-[#EFE6FB] bg-[#FBF8FF] p-3" data-testid="lead-attribution">
              <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-[#7A4FD0]"><Megaphone size={12} /> Atribusi Akuisisi</div>
              <div className="flex flex-wrap items-center gap-2 text-[12px]">
                <span className="rounded-full bg-[#5856D6] px-2.5 py-1 font-semibold text-white" data-testid="lead-channel">{chLabel(lead.channel || lead.source)}</span>
                {lead.utm_campaign ? <span className="rounded-full bg-white px-2.5 py-1 text-[#3C3C43] ring-1 ring-[#E6DCF7]" data-testid="lead-campaign">Kampanye: {lead.utm_campaign}</span> : null}
                {lead.attribution?.first_touch?.channel && lead.attribution.first_touch.channel !== (lead.channel || lead.source)
                  ? <span className="rounded-full bg-white px-2.5 py-1 text-[#6B6B73] ring-1 ring-[#E6DCF7]">First-touch: {chLabel(lead.attribution.first_touch.channel)}</span> : null}
                {lead.marketing_consent
                  ? <span className="inline-flex items-center gap-1 rounded-full bg-[#34C759]/12 px-2.5 py-1 font-semibold text-[#126E2C]" data-testid="lead-consent"><BadgeCheck size={12} /> Consent promosi</span>
                  : <span className="inline-flex items-center gap-1 rounded-full bg-[#FF3B30]/10 px-2.5 py-1 font-semibold text-[#A8221A]" data-testid="lead-consent"><ShieldOff size={12} /> Tanpa consent</span>}
                {/* F8: lead dari halaman iklan — tim sales perlu tahu halaman & versi A/B mana yang
                    menghasilkannya, karena itu yang menentukan halaman mana layak dibiayai lagi. */}
                {lead.landing_slug ? (
                  <a href={`/lp/${lead.landing_slug}`} target="_blank" rel="noreferrer"
                    className="inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-1 font-semibold text-[#0B57D0] ring-1 ring-[#CFE0FF] hover:underline"
                    data-testid="lead-landing">
                    <LayoutTemplate size={12} /> /lp/{lead.landing_slug}
                    {lead.landing_variant ? ` · versi ${lead.landing_variant}` : ""}
                  </a>
                ) : null}
                {/* CMS-08: KONTEN terakhir yang dibaca sebelum mengisi form. Ini yang menjawab
                    "artikel/destinasi mana yang benar-benar menghasilkan lead", bukan sekadar
                    channel iklan. Jejaknya diambil dari peramban pengunjung (tanpa data pribadi). */}
                {lead.content_ref?.slug ? (
                  <a href={lead.content_ref.path || "#"} target="_blank" rel="noreferrer"
                    className="inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-1 font-semibold text-[#0B57D0] ring-1 ring-[#CFE0FF] hover:underline"
                    data-testid="lead-content-ref">
                    <FileText size={12} /> Konten: {lead.content_ref.title || lead.content_ref.slug}
                  </a>
                ) : null}
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 rounded-[12px] border border-[#EFF0F2] bg-[#FAFAFB] p-3 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label className="text-[11px]"><ArrowRightLeft size={12} className="mr-1 inline" />Tahap</Label>
                <Select value={lead.stage} onValueChange={moveStage}>
                  <SelectTrigger data-testid="lead-stage-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{STAGES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-[11px]"><UserCheck size={12} className="mr-1 inline" />Ditugaskan</Label>
                <Select value={lead.assigned_to || "auto"} onValueChange={assign}>
                  <SelectTrigger data-testid="lead-assign-select"><SelectValue placeholder="Pilih agen" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto">Otomatis (round-robin)</SelectItem>
                    {(agents || []).map((a) => <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-[11px]">Nilai (Rp)</Label>
                <Input type="number" defaultValue={lead.value || 0} onBlur={(e) => saveValue(e.target.value)} data-testid="lead-value-input" />
              </div>
            </div>
            {lead.converted_customer_id ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2 rounded-[12px] border border-[#34C759]/40 bg-[#34C759]/10 px-3 py-2.5 text-[13px] font-semibold text-[#126E2C]" data-testid="lead-converted"><CheckCircle2 size={15} /> Sudah dikonversi ke customer.</div>
                <button className="primary-button w-full" disabled={busy} onClick={startBooking} data-testid="lead-to-booking"><CalendarDays size={14} /> Jadikan Booking</button>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                <button className="secondary-button w-full" disabled={busy} onClick={() => setQuoOpen(true)} data-testid="lead-make-quotation"><FileText size={14} /> Buat Penawaran</button>
                <button className="secondary-button w-full" disabled={busy} onClick={convert} data-testid="lead-convert"><UserCheck size={14} /> Konversi ke Customer</button>
                <button className="primary-button w-full" disabled={busy} onClick={startBooking} data-testid="lead-to-booking"><CalendarDays size={14} /> Jadikan Booking</button>
              </div>
            )}
            <div>
              <Label className="text-[12px]"><StickyNote size={13} className="mr-1 inline" />Tambah Catatan</Label>
              <div className="mt-1.5 flex gap-2">
                <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder="Hasil follow-up, info tambahan…" data-testid="lead-note-input" />
                <button className="secondary-button self-end" disabled={busy || !note.trim()} onClick={addNote} data-testid="lead-note-submit">Simpan</button>
              </div>
            </div>
            <div>
              <h3 className="mb-2 text-[13px] font-bold text-[#1C1C1E]">Linimasa Aktivitas</h3>
              {acts.length === 0 ? (
                <p className="rounded-[12px] border border-dashed border-[#D9DADF] px-3 py-6 text-center text-[12.5px] text-[#6B6B73]" data-testid="lead-timeline-empty">Belum ada aktivitas.</p>
              ) : (
                <ol className="space-y-2" data-testid="lead-timeline">
                  {acts.map((a) => (
                    <li key={a.id} className="flex gap-2.5 rounded-[10px] border border-[#F2F2F5] bg-white px-3 py-2">
                      <span className="mt-1 h-2 w-2 flex-shrink-0 rounded-full bg-[#007AFF]" />
                      <div className="min-w-0">
                        <p className="text-[12.5px] text-[#1C1C1E]"><b>{ACT_LABEL[a.type] || a.type}</b>{a.from_stage ? ` · ${a.from_stage} → ${a.to_stage}` : ""}{a.text ? ` — ${a.text}` : ""}</p>
                        <p className="text-[11px] text-[#8E8E93]">{formatDateTime(a.created_at)}{a.user_name ? ` · ${a.user_name}` : ""}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
    <QuotationFormDialog open={quoOpen} onOpenChange={setQuoOpen} lead={lead}
      onSaved={() => { setQuoOpen(false); after("Penawaran dibuat"); }} />
    <BookingFormDialog open={bookOpen} onOpenChange={setBookOpen}
      initial={bookPrefill?.initial || null} initialStart={bookPrefill?.start || ""}
      onCreated={onBookingCreated} />
    <LeadFormDialog open={editOpen} onOpenChange={setEditOpen} agents={agents} initial={lead}
      onSaved={() => after("Lead diperbarui")} />
    <ConfirmDialog open={delOpen} onOpenChange={setDelOpen} title="Hapus lead?"
      description={lead ? `Lead "${lead.customer_name}" beserta riwayat aktivitasnya akan dihapus permanen. Lead yang sudah menang (won) tidak bisa dihapus.` : ""}
      busy={busy} onConfirm={doDelete} testId="lead-delete-confirm" />
    </>
  );
}

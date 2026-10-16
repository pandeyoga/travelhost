import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Megaphone, Send, Plus, CheckCircle2, XCircle, Pencil, Trash2 } from "lucide-react";
import apiClient from "@/services/apiClient";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatusPill } from "@/components/shared/StatusPill";
import { formatQty, formatDateTime } from "@/utils/formatters";

const STAGES = [["all", "Semua tahap"], ["new", "Baru"], ["contacted", "Dihubungi"], ["quoted", "Penawaran"], ["negotiation", "Negosiasi"], ["won", "Menang"], ["lost", "Hilang"]];
const SRC = [["all", "Semua sumber"], ["website", "Website"], ["whatsapp", "WhatsApp"], ["manual", "Manual"]];

export default function CrmBroadcast() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [delTarget, setDelTarget] = useState(null);
  const [busy, setBusy] = useState(false);
  const EMPTY = { title: "", message: "", segment_stage: "all", segment_source: "all" };
  const [form, setForm] = useState(EMPTY);

  const openCreate = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = (b) => {
    setEditing(b);
    setForm({ title: b.title || "", message: b.message || "", segment_stage: b.segment?.stage || "all", segment_source: b.segment?.source || "all" });
    setOpen(true);
  };

  const load = () => {
    setLoading(true);
    apiClient.get("/broadcasts").then((r) => { setRows(r.data || []); setError(null); }).catch(() => setError("Gagal memuat broadcast")).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const anySending = rows.some((b) => b.status === "sending");
  useEffect(() => {
    if (!anySending) return undefined;
    const t = setInterval(() => {
      apiClient.get("/broadcasts").then((r) => setRows(r.data || [])).catch(() => {});
    }, 4000);
    return () => clearInterval(t);
  }, [anySending]);

  const create = async () => {
    if (!form.title.trim() || !form.message.trim()) { toast.error("Judul & pesan wajib diisi"); return; }
    setBusy(true);
    const payload = {
      title: form.title.trim(), message: form.message.trim(),
      segment_stage: form.segment_stage === "all" ? null : form.segment_stage,
      segment_source: form.segment_source === "all" ? null : form.segment_source,
    };
    try {
      if (editing) {
        await apiClient.patch(`/broadcasts/${editing.id}`, payload);
        toast.success("Broadcast diperbarui");
      } else {
        await apiClient.post("/broadcasts", payload);
        toast.success("Broadcast dibuat (draft)");
      }
      setOpen(false); setEditing(null); setForm(EMPTY); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan broadcast"); } finally { setBusy(false); }
  };
  const doDelete = async () => {
    if (!delTarget) return;
    setBusy(true);
    try {
      await apiClient.delete(`/broadcasts/${delTarget.id}`);
      toast.success("Broadcast dihapus");
      setDelTarget(null); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menghapus broadcast"); } finally { setBusy(false); }
  };
  const send = async (id) => {
    setBusy(true);
    try { const r = await apiClient.post(`/broadcasts/${id}/send`); toast.success(`Broadcast dimulai — ${r.data.recipients_count} penerima (jeda otomatis antar pesan)`); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Gagal mengirim"); } finally { setBusy(false); }
  };

  return (
    <div data-testid="broadcast-panel">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-[12.5px] text-[#6B6B73]">Kirim pesan WhatsApp ke segmen lead via provider aktif. Jeda acak antar pesan otomatis (anti-banned). Dukung variabel {"{customer_name}"} & {"{company}"}.</p>
        <button className="primary-button" onClick={openCreate} data-testid="broadcast-new"><Plus size={14} /> Broadcast Baru</button>
      </div>

      {loading ? <div className="flex items-center justify-center py-16 text-[13px] text-[#6B6B73]" data-testid="broadcast-loading"><Loader2 className="mr-2 animate-spin" /> Memuat…</div>
        : error ? <div className="py-16 text-center" data-testid="broadcast-error"><p className="text-[#6B6B73]">{error}</p><button className="secondary-button mt-3" onClick={load}>Coba lagi</button></div>
        : rows.length === 0 ? <div className="rounded-[14px] border border-dashed border-[#D9DADF] bg-white py-16 text-center text-[13px] text-[#6B6B73]" data-testid="broadcast-empty">Belum ada broadcast.</div>
        : <div className="space-y-2" data-testid="broadcast-list">
            {rows.map((b) => (
              <div key={b.id} className="rounded-[12px] border border-[#EFF0F2] bg-white px-4 py-3" data-testid={`broadcast-${b.id}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="flex items-center gap-2 text-[13px] font-bold text-[#1C1C1E]"><Megaphone size={14} className="text-[#007AFF]" />{b.title} <StatusPill value={{ draft: "Draf", sending: "mengirim…", sent: "Terkirim", failed: "Gagal" }[b.status] || b.status} tone={b.status === "sent" ? "success" : b.status === "sending" ? "info" : b.status === "failed" ? "danger" : "neutral"} /></p>
                    <p className="mt-1 line-clamp-2 text-[12.5px] text-[#6B6B73]">{b.message}</p>
                    <p className="mt-1 text-[11px] text-[#8E8E93]">Segmen: {b.segment?.stage || "semua tahap"} / {b.segment?.source || "semua sumber"} · <span className="tabular-nums">{formatQty(b.recipients_count)}</span> penerima{b.sent_at ? ` · terkirim ${formatDateTime(b.sent_at)}` : ""}</p>
                    {b.status === "sending" || b.sent_count != null ? (
                      <p className="mt-1 flex flex-wrap items-center gap-2 text-[11px]" data-testid={`broadcast-progress-${b.id}`}>
                        {b.status === "sending" ? <Loader2 size={11} className="animate-spin text-[#007AFF]" /> : null}
                        <span className="flex items-center gap-1 font-semibold text-[#127A36]"><CheckCircle2 size={11} /> {formatQty(b.sent_count || 0)} terkirim</span>
                        {b.failed_count ? <span className="flex items-center gap-1 font-semibold text-[#A8221A]"><XCircle size={11} /> {formatQty(b.failed_count)} gagal</span> : null}
                        {b.skipped_count ? <span className="text-[#8E8E93]">{formatQty(b.skipped_count)} opt-out</span> : null}
                        {b.error ? <span className="text-[#A8221A]">{b.error}</span> : null}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-1.5">
                    {b.status !== "sent" && b.status !== "sending" ? <button className="secondary-button" disabled={busy} onClick={() => send(b.id)} data-testid={`broadcast-send-${b.id}`}><Send size={13} /> {b.status === "failed" ? "Kirim Ulang" : "Kirim"}</button> : null}
                    {b.status === "draft" || b.status === "failed" ? <button className="icon-button !h-8 !w-8" title="Edit" disabled={busy} onClick={() => openEdit(b)} data-testid={`broadcast-edit-${b.id}`}><Pencil size={14} /></button> : null}
                    {b.status !== "sending" ? <button className="icon-button !h-8 !w-8 !text-[#A8221A]" title="Hapus" disabled={busy} onClick={() => setDelTarget(b)} data-testid={`broadcast-delete-${b.id}`}><Trash2 size={14} /></button> : null}
                  </div>
                </div>
              </div>
            ))}
          </div>}

      <ConfirmDialog open={Boolean(delTarget)} onOpenChange={(v) => !v && setDelTarget(null)} title="Hapus broadcast?"
        description={delTarget ? `"${delTarget.title}" akan dihapus permanen${delTarget.status === "sent" ? " (riwayat pengiriman ikut hilang)" : ""}.` : ""}
        busy={busy} onConfirm={doDelete} testId="broadcast-delete-confirm" />

      <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) setEditing(null); }}>
        <DialogContent className="sm:max-w-lg" data-testid="broadcast-dialog">
          <DialogHeader><DialogTitle>{editing ? "Edit Broadcast" : "Broadcast Baru"}</DialogTitle><DialogDescription>Pesan dikirim satu-per-satu ke lead segmen terpilih dengan jeda otomatis. Gunakan {"{customer_name}"} untuk personalisasi.</DialogDescription></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5"><Label>Judul</Label><Input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} placeholder="mis. Promo Akhir Pekan" data-testid="bc-title" /></div>
            <div className="space-y-1.5"><Label>Pesan</Label><Textarea value={form.message} onChange={(e) => setForm((f) => ({ ...f, message: e.target.value }))} rows={3} placeholder="Isi pesan WhatsApp…" data-testid="bc-message" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5"><Label>Segmen tahap</Label>
                <Select value={form.segment_stage} onValueChange={(v) => setForm((f) => ({ ...f, segment_stage: v }))}>
                  <SelectTrigger data-testid="bc-stage"><SelectValue /></SelectTrigger>
                  <SelectContent>{STAGES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
                </Select></div>
              <div className="space-y-1.5"><Label>Segmen sumber</Label>
                <Select value={form.segment_source} onValueChange={(v) => setForm((f) => ({ ...f, segment_source: v }))}>
                  <SelectTrigger data-testid="bc-source"><SelectValue /></SelectTrigger>
                  <SelectContent>{SRC.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
                </Select></div>
            </div>
          </div>
          <DialogFooter className="mt-2">
            <button className="secondary-button" onClick={() => setOpen(false)} data-testid="bc-cancel">Batal</button>
            <button className="primary-button" disabled={busy} onClick={create} data-testid="bc-submit">{busy ? <Loader2 size={14} className="animate-spin" /> : null} {editing ? "Simpan" : "Buat"}</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

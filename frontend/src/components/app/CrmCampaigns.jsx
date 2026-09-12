import { useCallback, useEffect, useState } from "react";
import { Megaphone, Plus, Trash2, Send, Loader2, Eye, Users2, MessageSquare, FileText, Clock } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { LoadingState, EmptyState } from "@/components/shared/DataStates";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { formatCurrency, formatQty, formatDateTime } from "@/utils/formatters";

const CST = {
  draft: ["Draft", "#6B6B73", "#F2F2F5"], scheduled: ["Terjadwal", "#0058CC", "#E5F0FF"],
  sending: ["Mengirim", "#C25400", "#FFF1D6"], sent: ["Terkirim", "#126E2C", "#E3F7E8"],
};
const RST = {
  sent: ["Terkirim", "#126E2C", "#E3F7E8"], failed: ["Gagal", "#FF3B30", "#FFE5E2"],
  skipped_optout: ["Dilewati", "#8E8E93", "#F2F2F5"],
};

function emptyCampaign() {
  return { name: "", segment_id: "", method: "manual", template_key: "", message: "", scheduled_at: "" };
}
function toLocalInput(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function Pill({ map, value }) {
  const v = map[value] || ["—", "#8E8E93", "#F2F2F5"];
  return <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold" style={{ color: v[1], background: v[2] }}>{v[0]}</span>;
}

export default function CrmCampaigns() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [segments, setSegments] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(null);
  const [sendingId, setSendingId] = useState(null);
  const [detail, setDetail] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/crm/campaigns").then((r) => setRows(Array.isArray(r.data) ? r.data : []))
      .catch(() => setRows([])).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    apiClient.get("/crm/segments").then((r) => setSegments(r.data || [])).catch(() => {});
    apiClient.get("/wa/templates").then((r) => setTemplates(r.data || [])).catch(() => {});
  }, []);

  const segOf = (id) => segments.find((s) => s.id === id);
  const doPreview = useCallback((segId) => {
    setPreview(null);
    if (!segId) return;
    apiClient.get(`/crm/segments/${segId}/preview`).then((r) => setPreview(r.data)).catch(() => setPreview(null));
  }, []);

  const onPickSegment = (segId) => {
    setEditing((e) => ({ ...e, segment_id: segId }));
    doPreview(segId);
  };

  const openCreate = () => { setPreview(null); setEditing(emptyCampaign()); };
  const openEdit = (c) => {
    setEditing({
      id: c.id, name: c.name, segment_id: c.segment_id || "",
      method: c.template_key ? "template" : "manual",
      template_key: c.template_key || "", message: c.message || "",
      scheduled_at: toLocalInput(c.scheduled_at),
    });
    doPreview(c.segment_id);
  };

  const save = async () => {
    if (!editing.name.trim()) { toast.error("Nama kampanye wajib diisi"); return; }
    if (!editing.segment_id) { toast.error("Pilih segmen target"); return; }
    if (editing.method === "template" && !editing.template_key) { toast.error("Pilih template WhatsApp"); return; }
    if (editing.method === "manual" && !editing.message.trim()) { toast.error("Pesan wajib diisi"); return; }
    const seg = segOf(editing.segment_id);
    const payload = {
      name: editing.name.trim(),
      audience: seg?.audience || "customer",
      segment_id: editing.segment_id,
      template_key: editing.method === "template" ? editing.template_key : null,
      message: editing.method === "manual" ? editing.message.trim() : null,
      scheduled_at: editing.scheduled_at ? new Date(editing.scheduled_at).toISOString() : null,
    };
    setBusy(true);
    try {
      if (editing.id) await apiClient.patch(`/crm/campaigns/${editing.id}`, payload);
      else await apiClient.post("/crm/campaigns", payload);
      toast.success(editing.scheduled_at ? "Kampanye dijadwalkan" : "Kampanye disimpan (draft)");
      setEditing(null); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan kampanye"); } finally { setBusy(false); }
  };

  const send = async (c) => {
    if (!window.confirm(`Kirim kampanye "${c.name}" sekarang? (simulasi WhatsApp)`)) return;
    setSendingId(c.id);
    try {
      const r = await apiClient.post(`/crm/campaigns/${c.id}/send`);
      const s = r.data || {};
      toast.success(`Terkirim ke ${formatQty(s.sent || 0)}/${formatQty(s.total || 0)} kontak · biaya ${formatCurrency(s.cost || 0)}`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal mengirim kampanye"); } finally { setSendingId(null); }
  };

  const remove = async (c) => {
    if (!window.confirm(`Hapus kampanye "${c.name}"?`)) return;
    try { await apiClient.delete(`/crm/campaigns/${c.id}`); toast.success("Kampanye dihapus"); load(); }
    catch (e) { toast.error("Gagal menghapus"); }
  };

  const openDetail = async (c) => {
    try { const r = await apiClient.get(`/crm/campaigns/${c.id}`); setDetail(r.data); }
    catch (e) { toast.error("Gagal memuat detail"); }
  };

  const tplBody = templates.find((t) => t.key === editing?.template_key)?.body;

  return (
    <div className="space-y-3" data-testid="crm-campaigns">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[12.5px] text-[#6B6B73]">Broadcast WhatsApp tersegmentasi ke lead/pelanggan. <b>Simulasi</b> — integrasi WA nyata di fase lanjutan.</p>
        <button className="primary-button" onClick={openCreate} data-testid="campaign-add"><Plus size={14} /> Kampanye Baru</button>
      </div>

      {loading ? <LoadingState testId="campaigns-loading" /> : rows.length === 0 ? (
        <EmptyState title="Belum ada kampanye" description="Buat kampanye WhatsApp tersegmentasi untuk lead atau pelanggan." testId="campaigns-empty" />
      ) : (
        <div className="space-y-2" data-testid="campaigns-list">
          {rows.map((c) => {
            const st = c.stats || {};
            return (
              <section key={c.id} className="section-card" data-testid={`campaign-${c.id}`}>
                <div className="flex flex-wrap items-start justify-between gap-3 p-4">
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-2 text-[13px] font-bold text-[#1C1C1E]">
                      <Megaphone size={15} className="text-[#5856D6]" /> {c.name}
                      <Pill map={CST} value={c.status} />
                      <span className="rounded-full bg-[#F2F2F5] px-2 py-0.5 text-[10.5px] font-semibold text-[#6B6B73]">{c.audience === "lead" ? "Lead" : "Pelanggan"}</span>
                    </p>
                    <p className="mt-1 line-clamp-2 text-[12px] text-[#6B6B73]">
                      {c.template_key ? <span className="inline-flex items-center gap-1"><FileText size={12} /> Template: {c.template_key}</span> : (c.message || "—")}
                    </p>
                    <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-[#8E8E93]">
                      {c.scheduled_at && c.status === "scheduled" ? <span className="inline-flex items-center gap-1"><Clock size={11} /> Jadwal {formatDateTime(c.scheduled_at)}</span> : null}
                      {c.status === "sent" ? (
                        <span className="tabular-nums">Terkirim <b className="text-[#126E2C]">{formatQty(st.sent || 0)}</b> · Gagal <b className="text-[#FF3B30]">{formatQty(st.failed || 0)}</b> · Dilewati {formatQty(st.skipped || 0)} · Biaya {formatCurrency(st.cost || 0)}</span>
                      ) : null}
                      {c.sent_at ? <span>· dikirim {formatDateTime(c.sent_at)}</span> : null}
                    </p>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-2">
                    {c.status === "sent" ? (
                      <button className="secondary-button !h-8" onClick={() => openDetail(c)} data-testid={`campaign-detail-${c.id}`}><Eye size={13} /> Penerima</button>
                    ) : (
                      <>
                        <button className="secondary-button !h-8" onClick={() => send(c)} disabled={sendingId === c.id || c.status === "sending"} data-testid={`campaign-send-${c.id}`}>
                          {sendingId === c.id ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />} Kirim
                        </button>
                        <button className="secondary-button !h-8" onClick={() => openEdit(c)} data-testid={`campaign-edit-${c.id}`}>Ubah</button>
                      </>
                    )}
                    <button className="icon-button !h-8 !w-8" onClick={() => remove(c)} data-testid={`campaign-del-${c.id}`}><Trash2 size={14} /></button>
                  </div>
                </div>
              </section>
            );
          })}
        </div>
      )}

      {/* Create / Edit dialog */}
      <Dialog open={!!editing} onOpenChange={(v) => { if (!v) { setEditing(null); setPreview(null); } }}>
        <DialogContent className="max-w-lg" data-testid="campaign-dialog">
          <DialogHeader>
            <DialogTitle>{editing?.id ? "Ubah Kampanye" : "Kampanye Baru"}</DialogTitle>
            <DialogDescription>Pilih segmen target lalu susun pesan WhatsApp (simulasi).</DialogDescription>
          </DialogHeader>
          {editing ? (
            <div className="max-h-[62vh] space-y-3 overflow-y-auto pr-1">
              <div className="space-y-1.5"><Label>Nama Kampanye</Label>
                <Input value={editing.name} onChange={(e) => setEditing((s) => ({ ...s, name: e.target.value }))} placeholder="mis. Promo Akhir Tahun" data-testid="campaign-name" />
              </div>
              <div className="space-y-1.5"><Label>Segmen Target</Label>
                <Select value={editing.segment_id} onValueChange={onPickSegment}>
                  <SelectTrigger data-testid="campaign-segment"><SelectValue placeholder="Pilih segmen…" /></SelectTrigger>
                  <SelectContent>
                    {segments.length === 0 ? <div className="px-2 py-3 text-center text-[12px] text-[#8E8E93]">Belum ada segmen. Buat di tab Segmen.</div>
                      : segments.map((s) => <SelectItem key={s.id} value={s.id}>{s.name} · {s.audience === "lead" ? "Lead" : "Pelanggan"}</SelectItem>)}
                  </SelectContent>
                </Select>
                {preview ? (
                  <p className="flex items-center gap-1 text-[11.5px] font-semibold text-[#126E2C]" data-testid="campaign-preview">
                    <Users2 size={12} /> {formatQty(preview.count || 0)} anggota · {formatQty(preview.reachable || 0)} ber-WA
                  </p>
                ) : null}
              </div>
              <div className="space-y-1.5"><Label>Metode Pesan</Label>
                <Select value={editing.method} onValueChange={(v) => setEditing((s) => ({ ...s, method: v }))}>
                  <SelectTrigger data-testid="campaign-method"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="manual">Tulis pesan manual</SelectItem>
                    <SelectItem value="template">Pakai template WhatsApp</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {editing.method === "template" ? (
                <div className="space-y-1.5"><Label>Template</Label>
                  <Select value={editing.template_key} onValueChange={(v) => setEditing((s) => ({ ...s, template_key: v }))}>
                    <SelectTrigger data-testid="campaign-template"><SelectValue placeholder="Pilih template…" /></SelectTrigger>
                    <SelectContent>{templates.map((t) => <SelectItem key={t.key} value={t.key}>{t.name || t.key}</SelectItem>)}</SelectContent>
                  </Select>
                  {tplBody ? <p className="rounded-[8px] bg-[#FAFAFB] p-2.5 text-[11.5px] text-[#3C3C43]"><MessageSquare size={12} className="mr-1 inline" />{tplBody}</p> : null}
                </div>
              ) : (
                <div className="space-y-1.5"><Label>Pesan</Label>
                  <Textarea rows={3} value={editing.message} onChange={(e) => setEditing((s) => ({ ...s, message: e.target.value }))} placeholder="Isi pesan WhatsApp… ({name} tersedia)" data-testid="campaign-message" />
                </div>
              )}
              <div className="space-y-1.5"><Label>Jadwal kirim (opsional)</Label>
                <Input type="datetime-local" value={editing.scheduled_at} onChange={(e) => setEditing((s) => ({ ...s, scheduled_at: e.target.value }))} data-testid="campaign-schedule" />
                <p className="text-[11px] text-[#8E8E93]">Kosongkan untuk menyimpan sebagai draft dan kirim manual.</p>
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <button className="secondary-button" onClick={() => { setEditing(null); setPreview(null); }} data-testid="campaign-cancel">Batal</button>
            <button className="primary-button" onClick={save} disabled={busy} data-testid="campaign-save">{busy ? <Loader2 size={14} className="animate-spin" /> : null} Simpan</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Detail / recipients dialog */}
      <Dialog open={!!detail} onOpenChange={(v) => !v && setDetail(null)}>
        <DialogContent className="max-w-xl" data-testid="campaign-detail-dialog">
          <DialogHeader><DialogTitle>Penerima “{detail?.name}”</DialogTitle></DialogHeader>
          {detail ? (
            <>
              <div className="flex flex-wrap gap-2 text-[11.5px]">
                <span className="rounded-full bg-[#E3F7E8] px-2.5 py-1 font-semibold text-[#126E2C]">Terkirim {formatQty(detail.stats?.sent || 0)}</span>
                <span className="rounded-full bg-[#FFE5E2] px-2.5 py-1 font-semibold text-[#FF3B30]">Gagal {formatQty(detail.stats?.failed || 0)}</span>
                <span className="rounded-full bg-[#F2F2F5] px-2.5 py-1 font-semibold text-[#6B6B73]">Dilewati {formatQty(detail.stats?.skipped || 0)}</span>
                <span className="rounded-full bg-[#EAEAFF] px-2.5 py-1 font-semibold text-[#5856D6]">Biaya {formatCurrency(detail.stats?.cost || 0)}</span>
              </div>
              <div className="max-h-[52vh] space-y-1.5 overflow-y-auto" data-testid="campaign-recipients">
                {(detail.recipients || []).length === 0 ? <p className="py-6 text-center text-[13px] text-[#8E8E93]">Belum ada penerima.</p>
                  : (detail.recipients || []).map((r) => (
                    <div key={r.id} className="flex items-center justify-between rounded-[8px] bg-[#FAFAFB] px-3 py-2 text-[12px]" data-testid={`recipient-${r.id}`}>
                      <div className="min-w-0"><b className="text-[#1C1C1E]">{r.name || "—"}</b><span className="ml-2 text-[#8E8E93]">{r.phone || "tanpa telepon"}</span></div>
                      <div className="flex items-center gap-2"><Pill map={RST} value={r.status} />{r.cost ? <span className="tabular-nums text-[10.5px] text-[#8E8E93]">{formatCurrency(r.cost)}</span> : null}</div>
                    </div>
                  ))}
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

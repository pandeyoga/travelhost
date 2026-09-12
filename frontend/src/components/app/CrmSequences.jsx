import { useCallback, useEffect, useState } from "react";
import { Workflow, Plus, Trash2, Loader2, X, UserPlus, ListChecks } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { LoadingState, EmptyState } from "@/components/shared/DataStates";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { formatDateTime } from "@/utils/formatters";

function emptySeq() { return { name: "", description: "", audience: "lead", enabled: true, steps: [{ delay_hours: 0, action: "send_wa", text: "" }] }; }
const ST = { active: ["Aktif", "#0058CC", "#E5F0FF"], completed: ["Selesai", "#126E2C", "#E3F7E8"], stopped: ["Dihentikan", "#8E8E93", "#F2F2F5"] };

export default function CrmSequences() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [segments, setSegments] = useState([]);
  const [enrollFor, setEnrollFor] = useState(null);
  const [enrollSeg, setEnrollSeg] = useState("");
  const [viewEnr, setViewEnr] = useState(null);
  const [enrollments, setEnrollments] = useState([]);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/crm/sequences").then((r) => setRows(Array.isArray(r.data) ? r.data : []))
      .catch(() => setRows([])).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { apiClient.get("/crm/segments").then((r) => setSegments(r.data || [])).catch(() => {}); }, []);

  const addStep = () => setEditing((s) => ({ ...s, steps: [...(s.steps || []), { delay_hours: 24, action: "send_wa", text: "" }] }));
  const updStep = (i, st) => setEditing((s) => ({ ...s, steps: s.steps.map((x, idx) => (idx === i ? st : x)) }));
  const delStep = (i) => setEditing((s) => ({ ...s, steps: s.steps.filter((_, idx) => idx !== i) }));
  const toggle = async (seq, enabled) => { try { await apiClient.patch(`/crm/sequences/${seq.id}`, { enabled }); load(); } catch (e) { toast.error("Gagal"); } };

  const save = async () => {
    if (!editing.name.trim()) { toast.error("Nama wajib diisi"); return; }
    setBusy(true);
    try {
      if (editing.id) await apiClient.patch(`/crm/sequences/${editing.id}`, editing);
      else await apiClient.post("/crm/sequences", editing);
      toast.success("Sequence disimpan"); setEditing(null); load();
    } catch (e) { toast.error("Gagal menyimpan"); } finally { setBusy(false); }
  };
  const remove = async (seq) => { if (!window.confirm(`Hapus sequence "${seq.name}"?`)) return;
    try { await apiClient.delete(`/crm/sequences/${seq.id}`); toast.success("Dihapus"); load(); } catch (e) { toast.error("Gagal"); } };
  const doEnroll = async () => {
    if (!enrollSeg) { toast.error("Pilih segmen"); return; }
    try { const r = await apiClient.post(`/crm/sequences/${enrollFor.id}/enroll`, { segment_id: enrollSeg });
      toast.success(`${r.data.enrolled} kontak didaftarkan`); setEnrollFor(null); setEnrollSeg(""); load(); }
    catch (e) { toast.error("Gagal enroll"); }
  };
  const openEnr = async (seq) => { setViewEnr(seq);
    try { const r = await apiClient.get(`/crm/sequences/${seq.id}/enrollments`); setEnrollments(r.data || []); } catch (e) { setEnrollments([]); } };

  const matchSeg = segments.filter((s) => !editing || s.audience === (enrollFor?.audience || s.audience));
  return (
    <div className="space-y-3" data-testid="crm-sequences">
      <div className="flex items-center justify-between">
        <p className="text-[12.5px] text-[#6B6B73]">Nurturing drip otomatis (WhatsApp/tugas) bertahap via mesin otomasi.</p>
        <button className="primary-button" onClick={() => setEditing(emptySeq())} data-testid="sequence-add"><Plus size={14} /> Sequence Baru</button>
      </div>
      {loading ? <LoadingState testId="sequences-loading" /> : rows.length === 0 ? (
        <EmptyState title="Belum ada sequence" description="Buat alur nurturing bertahap untuk lead/pelanggan." testId="sequences-empty" />
      ) : (
        <div className="space-y-2" data-testid="sequences-list">
          {rows.map((seq) => (
            <section key={seq.id} className="section-card" data-testid={`sequence-${seq.id}`}>
              <div className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 text-[13px] font-bold text-[#1C1C1E]"><Workflow size={15} className="text-[#5856D6]" /> {seq.name}
                    <span className="rounded-full bg-[#F2F2F5] px-2 py-0.5 text-[10.5px] text-[#6B6B73]">{seq.audience === "lead" ? "Lead" : "Pelanggan"}</span></p>
                  <p className="mt-0.5 text-[11.5px] text-[#6B6B73]">{(seq.steps || []).length} langkah · {seq.stats?.enrolled || 0} terdaftar · {seq.stats?.completed || 0} selesai</p>
                </div>
                <div className="flex flex-shrink-0 items-center gap-2">
                  <Switch checked={!!seq.enabled} onCheckedChange={(v) => toggle(seq, v)} data-testid={`sequence-toggle-${seq.id}`} />
                  <button className="secondary-button !h-8" onClick={() => { setEnrollFor(seq); setEnrollSeg(""); }} data-testid={`sequence-enroll-${seq.id}`}><UserPlus size={13} /> Enroll</button>
                  <button className="secondary-button !h-8" onClick={() => openEnr(seq)} data-testid={`sequence-view-${seq.id}`}><ListChecks size={13} /></button>
                  <button className="secondary-button !h-8" onClick={() => setEditing({ ...seq })} data-testid={`sequence-edit-${seq.id}`}>Ubah</button>
                  <button className="icon-button !h-8 !w-8" onClick={() => remove(seq)} data-testid={`sequence-del-${seq.id}`}><Trash2 size={14} /></button>
                </div>
              </div>
            </section>
          ))}
        </div>
      )}

      <Dialog open={!!editing} onOpenChange={(v) => !v && setEditing(null)}>
        <DialogContent className="max-w-2xl" data-testid="sequence-dialog">
          <DialogHeader><DialogTitle>{editing?.id ? "Ubah Sequence" : "Sequence Baru"}</DialogTitle></DialogHeader>
          {editing ? (
            <div className="max-h-[65vh] space-y-3 overflow-y-auto pr-1">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5"><Label>Nama</Label><Input value={editing.name} onChange={(e) => setEditing((s) => ({ ...s, name: e.target.value }))} data-testid="sequence-name" /></div>
                <div className="space-y-1.5"><Label>Audiens</Label>
                  <Select value={editing.audience} onValueChange={(v) => setEditing((s) => ({ ...s, audience: v }))}>
                    <SelectTrigger data-testid="sequence-audience"><SelectValue /></SelectTrigger>
                    <SelectContent><SelectItem value="lead">Lead</SelectItem><SelectItem value="customer">Pelanggan</SelectItem></SelectContent>
                  </Select></div>
              </div>
              <Input placeholder="Deskripsi" value={editing.description || ""} onChange={(e) => setEditing((s) => ({ ...s, description: e.target.value }))} data-testid="sequence-desc" />
              <label className="flex items-center gap-2 text-[13px]"><Switch checked={!!editing.enabled} onCheckedChange={(v) => setEditing((s) => ({ ...s, enabled: v }))} data-testid="sequence-enabled" /> Aktif</label>
              <div className="rounded-[10px] border border-[#EFF0F2] p-3">
                <div className="mb-2 flex items-center justify-between"><Label>Langkah</Label><button className="secondary-button !h-7 !text-[11px]" onClick={addStep} data-testid="sequence-step-add"><Plus size={12} /> Langkah</button></div>
                <div className="space-y-2">
                  {(editing.steps || []).map((st, i) => (
                    <div key={i} className="rounded-[8px] bg-[#FAFAFB] p-2.5" data-testid={`sequence-step-${i}`}>
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-bold text-[#8E8E93]">#{i + 1}</span>
                        <div className="flex items-center gap-1"><Input type="number" className="h-8 w-20" value={st.delay_hours} onChange={(e) => updStep(i, { ...st, delay_hours: e.target.value })} data-testid={`sequence-delay-${i}`} /><span className="text-[11px] text-[#8E8E93]">jam</span></div>
                        <Select value={st.action} onValueChange={(v) => updStep(i, { ...st, action: v })}>
                          <SelectTrigger className="h-8 flex-1" data-testid={`sequence-action-${i}`}><SelectValue /></SelectTrigger>
                          <SelectContent><SelectItem value="send_wa">Kirim WhatsApp</SelectItem><SelectItem value="create_task">Buat tugas</SelectItem><SelectItem value="create_notification">Notifikasi</SelectItem></SelectContent>
                        </Select>
                        <button className="icon-button !h-8 !w-8" onClick={() => delStep(i)} data-testid={`sequence-step-del-${i}`}><X size={14} /></button>
                      </div>
                      <Textarea rows={2} className="mt-2" placeholder="Pesan / teks ({name} tersedia)" value={st.text || ""} onChange={(e) => updStep(i, { ...st, text: e.target.value })} data-testid={`sequence-text-${i}`} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <button className="secondary-button" onClick={() => setEditing(null)} data-testid="sequence-cancel">Batal</button>
            <button className="primary-button" onClick={save} disabled={busy} data-testid="sequence-save">{busy ? <Loader2 size={14} className="animate-spin" /> : null} Simpan</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!enrollFor} onOpenChange={(v) => !v && setEnrollFor(null)}>
        <DialogContent data-testid="enroll-dialog">
          <DialogHeader><DialogTitle>Enroll “{enrollFor?.name}” dari Segmen</DialogTitle></DialogHeader>
          <div className="space-y-2">
            <Label>Pilih Segmen ({enrollFor?.audience === "lead" ? "lead" : "pelanggan"})</Label>
            <Select value={enrollSeg} onValueChange={setEnrollSeg}>
              <SelectTrigger data-testid="enroll-segment"><SelectValue placeholder="Pilih segmen…" /></SelectTrigger>
              <SelectContent>{matchSeg.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <button className="secondary-button" onClick={() => setEnrollFor(null)}>Batal</button>
            <button className="primary-button" onClick={doEnroll} data-testid="enroll-submit">Enroll</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!viewEnr} onOpenChange={(v) => !v && setViewEnr(null)}>
        <DialogContent data-testid="enrollments-dialog">
          <DialogHeader><DialogTitle>Peserta “{viewEnr?.name}”</DialogTitle></DialogHeader>
          <div className="max-h-[55vh] space-y-1.5 overflow-y-auto">
            {enrollments.length === 0 ? <p className="py-4 text-center text-[13px] text-[#8E8E93]">Belum ada peserta.</p>
              : enrollments.map((e) => { const s = ST[e.status] || ST.active; return (
                <div key={e.id} className="flex items-center justify-between rounded-[8px] bg-[#FAFAFB] px-3 py-2 text-[12px]">
                  <div><b>{e.name}</b><span className="ml-2 text-[#8E8E93]">langkah {(e.step_index || 0) + 1}</span></div>
                  <div className="flex items-center gap-2"><span className="rounded-full px-2 py-0.5 text-[10.5px] font-semibold" style={{ color: s[1], background: s[2] }}>{s[0]}</span>
                    {e.next_run_at ? <span className="text-[10.5px] text-[#8E8E93]">{formatDateTime(e.next_run_at)}</span> : null}</div>
                </div>
              ); })}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

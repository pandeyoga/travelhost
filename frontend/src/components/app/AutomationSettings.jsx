import { useCallback, useEffect, useState } from "react";
import { Zap, Plus, Pencil, Trash2, RotateCcw, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";

const OPS = [["eq", "sama dengan"], ["ne", "tidak sama"], ["contains", "mengandung"],
  ["in", "salah satu dari"], ["exists", "ada isinya"], ["gt", "lebih dari"], ["lt", "kurang dari"]];

function emptyRule() {
  return { name: "", description: "", event_type: "lead.created", enabled: true, conditions: [], actions: [] };
}

export default function AutomationSettings() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [catalog, setCatalog] = useState({ events: [], actions: [] });
  const [templates, setTemplates] = useState([]);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/automation/rules").then((r) => setRules(Array.isArray(r.data) ? r.data : []))
      .catch(() => setRules([])).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    apiClient.get("/automation/event-types").then((r) => setCatalog(r.data || { events: [], actions: [] })).catch(() => {});
    apiClient.get("/wa/templates").then((r) => setTemplates(Array.isArray(r.data) ? r.data : [])).catch(() => {});
  }, []);

  const eventLabel = (k) => (catalog.events.find((e) => e.key === k) || {}).label || k;

  const toggle = async (rule, enabled) => {
    try { await apiClient.patch(`/automation/rules/${rule.id}`, { enabled }); load(); }
    catch (e) { toast.error("Gagal mengubah status"); }
  };
  const remove = async (rule) => {
    if (!window.confirm(`Hapus aturan "${rule.name}"?`)) return;
    try { await apiClient.delete(`/automation/rules/${rule.id}`); toast.success("Aturan dihapus"); load(); }
    catch (e) { toast.error("Gagal menghapus"); }
  };
  const resetDefaults = async () => {
    if (!window.confirm("Pasang ulang aturan sistem default? Aturan kustom tidak terhapus.")) return;
    try { const r = await apiClient.post("/automation/rules/reset-defaults"); toast.success(`${r.data.installed} aturan default dipasang`); load(); }
    catch (e) { toast.error("Gagal reset default"); }
  };

  const save = async () => {
    if (!editing.name.trim()) { toast.error("Nama aturan wajib diisi"); return; }
    setBusy(true);
    const payload = {
      name: editing.name, description: editing.description, event_type: editing.event_type,
      enabled: editing.enabled, conditions: editing.conditions, actions: editing.actions,
    };
    try {
      if (editing.id) await apiClient.patch(`/automation/rules/${editing.id}`, payload);
      else await apiClient.post("/automation/rules", payload);
      toast.success("Aturan disimpan"); setEditing(null); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan aturan"); }
    finally { setBusy(false); }
  };

  return (
    <section className="section-card" data-testid="settings-automation">
      <div className="section-head">
        <div className="flex min-w-0 items-center gap-2"><Zap size={16} className="text-[#0058CC]" /><h2 className="truncate">Otomasi (Event → Aksi)</h2></div>
        <div className="flex flex-shrink-0 items-center gap-2">
          <button className="secondary-button" onClick={resetDefaults} data-testid="auto-reset-defaults"><RotateCcw size={14} /> Reset Default</button>
          <button className="primary-button" onClick={() => setEditing(emptyRule())} data-testid="auto-add-rule"><Plus size={14} /> Tambah Aturan</button>
        </div>
      </div>
      <div className="section-body">
        <p className="mb-2 text-[12px] text-[#6B6B73]">Saat sebuah event terjadi (lead masuk, booking, pembayaran, WA masuk…), aksi otomatis dijalankan (kirim WhatsApp, notifikasi, tugaskan agen). Mock-first — tanpa kredensial.</p>
        {loading ? <p className="py-6 text-center text-[13px] text-[#8E8E93]">Memuat…</p>
          : rules.length === 0 ? <p className="py-6 text-center text-[13px] text-[#8E8E93]" data-testid="auto-rules-empty">Belum ada aturan. Klik “Reset Default” untuk memasang contoh.</p>
          : (
            <div className="divide-y divide-[#F2F2F5]" data-testid="auto-rules-list">
              {rules.map((r) => (
                <div key={r.id} className="flex flex-wrap items-center justify-between gap-3 py-3" data-testid={`auto-rule-${r.id}`}>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-bold text-[#1C1C1E]">{r.name}</p>
                    <p className="truncate text-[11.5px] text-[#6B6B73]">Pemicu: <b>{eventLabel(r.event_type)}</b> · {(r.actions || []).length} aksi · {(r.conditions || []).length} kondisi</p>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-2">
                    <Switch checked={!!r.enabled} onCheckedChange={(v) => toggle(r, v)} data-testid={`auto-rule-toggle-${r.id}`} />
                    <button className="icon-button !h-8 !w-8" title="Ubah" onClick={() => setEditing({ ...r })} data-testid={`auto-rule-edit-${r.id}`}><Pencil size={14} /></button>
                    <button className="icon-button !h-8 !w-8" title="Hapus" onClick={() => remove(r)} data-testid={`auto-rule-del-${r.id}`}><Trash2 size={14} /></button>
                  </div>
                </div>
              ))}
            </div>
          )}
      </div>

      <Dialog open={!!editing} onOpenChange={(v) => !v && setEditing(null)}>
        <DialogContent className="max-w-2xl" data-testid="auto-rule-dialog">
          <DialogHeader><DialogTitle>{editing?.id ? "Ubah Aturan" : "Aturan Baru"}</DialogTitle></DialogHeader>
          {editing ? (
            <div className="max-h-[65vh] space-y-3 overflow-y-auto pr-1">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="space-y-1.5"><Label>Nama Aturan</Label>
                  <Input value={editing.name} onChange={(e) => setEditing((s) => ({ ...s, name: e.target.value }))} data-testid="auto-rule-name" /></div>
                <div className="space-y-1.5"><Label>Event Pemicu</Label>
                  <Select value={editing.event_type} onValueChange={(v) => setEditing((s) => ({ ...s, event_type: v }))}>
                    <SelectTrigger data-testid="auto-rule-event"><SelectValue /></SelectTrigger>
                    <SelectContent>{catalog.events.map((e) => <SelectItem key={e.key} value={e.key}>{e.label}</SelectItem>)}</SelectContent>
                  </Select></div>
              </div>
              <div className="space-y-1.5"><Label>Deskripsi</Label>
                <Input value={editing.description || ""} onChange={(e) => setEditing((s) => ({ ...s, description: e.target.value }))} data-testid="auto-rule-desc" /></div>
              <label className="flex items-center gap-2 text-[13px] text-[#3C3C43]">
                <Switch checked={!!editing.enabled} onCheckedChange={(v) => setEditing((s) => ({ ...s, enabled: v }))} data-testid="auto-rule-enabled" /> Aktifkan aturan
              </label>

              <ActionsEditor editing={editing} setEditing={setEditing} actionTypes={catalog.actions} templates={templates} />
              <ConditionsEditor editing={editing} setEditing={setEditing} />
              <p className="rounded-[8px] bg-[#F7F7F9] px-3 py-2 text-[11px] text-[#6B6B73]">Variabel template tersedia: <code>{"{customer_name} {phone} {destination} {code} {total_amount} {amount} {number} {company}"}</code></p>
            </div>
          ) : null}
          <DialogFooter>
            <button className="secondary-button" onClick={() => setEditing(null)} data-testid="auto-rule-cancel">Batal</button>
            <button className="primary-button" onClick={save} disabled={busy} data-testid="auto-rule-save">{busy ? <Loader2 size={14} className="animate-spin" /> : null} Simpan</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

function ActionsEditor({ editing, setEditing, actionTypes, templates }) {
  const add = () => setEditing((s) => ({ ...s, actions: [...(s.actions || []), { type: "send_wa", params: {} }] }));
  const upd = (i, action) => setEditing((s) => ({ ...s, actions: s.actions.map((a, idx) => (idx === i ? action : a)) }));
  const del = (i) => setEditing((s) => ({ ...s, actions: s.actions.filter((_, idx) => idx !== i) }));
  return (
    <div className="rounded-[10px] border border-[#EFF0F2] p-3">
      <div className="mb-2 flex items-center justify-between"><Label>Aksi</Label>
        <button className="secondary-button !h-7 !text-[11px]" onClick={add} data-testid="auto-action-add"><Plus size={12} /> Tambah Aksi</button></div>
      {(editing.actions || []).length === 0 ? <p className="text-[12px] text-[#8E8E93]">Belum ada aksi.</p> : null}
      <div className="space-y-2">
        {(editing.actions || []).map((a, i) => {
          const p = a.params || {};
          const setP = (k, v) => upd(i, { ...a, params: { ...p, [k]: v } });
          return (
            <div key={i} className="rounded-[8px] bg-[#FAFAFB] p-2.5" data-testid={`auto-action-${i}`}>
              <div className="flex items-center gap-2">
                <Select value={a.type} onValueChange={(v) => upd(i, { type: v, params: {} })}>
                  <SelectTrigger className="h-8 flex-1" data-testid={`auto-action-type-${i}`}><SelectValue /></SelectTrigger>
                  <SelectContent>{actionTypes.map((t) => <SelectItem key={t.key} value={t.key}>{t.label}</SelectItem>)}</SelectContent>
                </Select>
                <button className="icon-button !h-8 !w-8" onClick={() => del(i)} data-testid={`auto-action-del-${i}`}><X size={14} /></button>
              </div>
              {a.type === "send_wa" ? (
                <div className="mt-2 space-y-2">
                  <Textarea rows={2} placeholder="Teks WhatsApp (boleh pakai {variabel})" value={p.text || ""} onChange={(e) => setP("text", e.target.value)} data-testid={`auto-action-text-${i}`} />
                  <Select value={p.template_key || "none"} onValueChange={(v) => setP("template_key", v === "none" ? "" : v)}>
                    <SelectTrigger className="h-8" data-testid={`auto-action-tpl-${i}`}><SelectValue placeholder="Template (opsional)" /></SelectTrigger>
                    <SelectContent><SelectItem value="none">Tanpa template (pakai teks)</SelectItem>
                      {templates.map((t) => <SelectItem key={t.key} value={t.key}>{t.name}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              ) : a.type === "schedule_followup" ? (
                <div className="mt-2 grid grid-cols-2 gap-2">
                  <Input type="number" placeholder="Hari ke depan" value={p.days ?? ""} onChange={(e) => setP("days", e.target.value)} data-testid={`auto-action-days-${i}`} />
                  <Input placeholder="Judul follow-up" value={p.title || ""} onChange={(e) => setP("title", e.target.value)} data-testid={`auto-action-futitle-${i}`} />
                </div>
              ) : (a.type === "create_notification" || a.type === "create_task") ? (
                <div className="mt-2 space-y-2">
                  <Input placeholder="Judul notifikasi" value={p.title || ""} onChange={(e) => setP("title", e.target.value)} data-testid={`auto-action-title-${i}`} />
                  <Input placeholder="Isi (opsional)" value={p.body || ""} onChange={(e) => setP("body", e.target.value)} data-testid={`auto-action-body-${i}`} />
                </div>
              ) : (
                <p className="mt-1 text-[11px] text-[#8E8E93]">Aksi ini otomatis menugaskan agen aktif (round-robin).</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ConditionsEditor({ editing, setEditing }) {
  const add = () => setEditing((s) => ({ ...s, conditions: [...(s.conditions || []), { field: "", op: "eq", value: "" }] }));
  const upd = (i, c) => setEditing((s) => ({ ...s, conditions: s.conditions.map((x, idx) => (idx === i ? c : x)) }));
  const del = (i) => setEditing((s) => ({ ...s, conditions: s.conditions.filter((_, idx) => idx !== i) }));
  return (
    <div className="rounded-[10px] border border-[#EFF0F2] p-3">
      <div className="mb-2 flex items-center justify-between"><Label>Kondisi (opsional, semua harus terpenuhi)</Label>
        <button className="secondary-button !h-7 !text-[11px]" onClick={add} data-testid="auto-cond-add"><Plus size={12} /> Tambah Kondisi</button></div>
      {(editing.conditions || []).length === 0 ? <p className="text-[12px] text-[#8E8E93]">Tanpa kondisi = selalu jalan.</p> : null}
      <div className="space-y-2">
        {(editing.conditions || []).map((c, i) => (
          <div key={i} className="flex items-center gap-2" data-testid={`auto-cond-${i}`}>
            <Input className="h-8 flex-1" placeholder="field (mis. source)" value={c.field} onChange={(e) => upd(i, { ...c, field: e.target.value })} data-testid={`auto-cond-field-${i}`} />
            <Select value={c.op} onValueChange={(v) => upd(i, { ...c, op: v })}>
              <SelectTrigger className="h-8 w-[140px]" data-testid={`auto-cond-op-${i}`}><SelectValue /></SelectTrigger>
              <SelectContent>{OPS.map(([k, l]) => <SelectItem key={k} value={k}>{l}</SelectItem>)}</SelectContent>
            </Select>
            <Input className="h-8 flex-1" placeholder="nilai" value={c.value ?? ""} onChange={(e) => upd(i, { ...c, value: e.target.value })} data-testid={`auto-cond-value-${i}`} />
            <button className="icon-button !h-8 !w-8" onClick={() => del(i)} data-testid={`auto-cond-del-${i}`}><X size={14} /></button>
          </div>
        ))}
      </div>
    </div>
  );
}

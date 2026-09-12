import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Hash, Loader2, Pencil, RotateCcw, Save } from "lucide-react";
import apiClient from "@/services/apiClient";
import { LoadingState, ErrorState } from "@/components/shared/DataStates";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Field } from "@/components/documents/BrandForm";

function RuleDialog({ rule, meta, onClose, onSaved }) {
  const [form, setForm] = useState({ pattern: rule.pattern, prefix: rule.prefix || "", width: rule.width, reset: rule.reset, start: rule.start || 1 });
  const [preview, setPreview] = useState(rule.preview);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    const t = setTimeout(async () => {
      try { const r = await apiClient.post(`/numbering/${rule.key}/preview`, form); setPreview(r.data.data.preview); setError(""); }
      catch (e) { setError(e?.response?.data?.detail || "Pola tidak sah"); }
    }, 350);
    return () => clearTimeout(t);
  }, [form, rule.key]);

  const save = async () => {
    setSaving(true);
    try { await apiClient.put(`/numbering/${rule.key}`, form); toast.success("Aturan penomoran disimpan"); onSaved(); onClose(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan"); }
    finally { setSaving(false); }
  };
  const tokens = [...(meta.global_tokens || []), ...(meta.context_tokens || [])];
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl" data-testid="numbering-dialog">
        <DialogHeader><DialogTitle className="flex items-center gap-2"><Hash size={16} className="text-[#007AFF]" /> {rule.label}</DialogTitle>
          <DialogDescription>Nomor yang sudah terbit tidak berubah. Aturan berlaku untuk nomor berikutnya.</DialogDescription></DialogHeader>
        <div className="space-y-3">
          <Field label="Pola nomor"><Input value={form.pattern} onChange={(e) => set("pattern", e.target.value)} className="font-mono" data-testid="num-pattern" /></Field>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Field label="Awalan {PREFIX}"><Input value={form.prefix} onChange={(e) => set("prefix", e.target.value)} data-testid="num-prefix" /></Field>
            <Field label="Lebar digit"><Input type="number" min={1} max={8} value={form.width} onChange={(e) => set("width", Number(e.target.value))} data-testid="num-width" /></Field>
            <Field label="Reset urutan">
              <Select value={form.reset} onValueChange={(v) => set("reset", v)}><SelectTrigger data-testid="num-reset"><SelectValue /></SelectTrigger>
                <SelectContent>{(meta.reset_options || []).map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent></Select>
            </Field>
            <Field label="Nomor awal"><Input type="number" min={1} value={form.start} onChange={(e) => set("start", Number(e.target.value))} data-testid="num-start" /></Field>
          </div>
          <div className="rounded-[10px] bg-[#F5F7FB] px-3 py-2.5">
            <p className="text-[10.5px] uppercase tracking-wide text-[#8E8E93]">Contoh nomor berikutnya</p>
            <p className="font-mono text-[15px] font-bold text-[#1C1C1E]" data-testid="num-preview">{error ? "—" : preview}</p>
            {error ? <p className="text-[11.5px] text-[#FF3B30]" data-testid="num-error">{error}</p> : null}
          </div>
          <div>
            <p className="mb-1.5 text-[11px] uppercase tracking-wide text-[#8E8E93]">Token yang bisa dipakai (klik untuk sisip)</p>
            <div className="flex flex-wrap gap-1.5">
              {tokens.map((t) => (
                <button key={t.token} type="button" onClick={() => set("pattern", `${form.pattern}{${t.token}}`)} title={t.desc}
                  className="rounded-full border border-[#E5E5EA] bg-white px-2.5 py-1 font-mono text-[11px] hover:border-[#007AFF] hover:text-[#007AFF]" data-testid={`tok-${t.token}`}>
                  {`{${t.token}}`} <span className="font-sans text-[#8E8E93]">{t.example}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter>
          <button className="secondary-button" onClick={onClose}>Batal</button>
          <button className="primary-button" onClick={save} disabled={saving || Boolean(error)} data-testid="num-save">{saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Simpan</button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function NumberingPanel() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [edit, setEdit] = useState(null);
  const load = useCallback(() => {
    apiClient.get("/numbering").then((r) => { setData(r.data); setError(""); }).catch(() => setError("Gagal memuat aturan penomoran"));
  }, []);
  useEffect(() => { load(); }, [load]);
  const reset = async (key) => {
    if (!window.confirm("Kembalikan aturan ini ke bawaan?")) return;
    await apiClient.delete(`/numbering/${key}`); toast.success("Aturan dikembalikan ke bawaan"); load();
  };
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <LoadingState testId="numbering-loading" />;
  return (
    <section className="section-card" data-testid="numbering-panel">
      <div className="section-head"><div className="flex items-center gap-2"><Hash size={16} className="text-[#007AFF]" /><h2>Aturan penomoran dokumen</h2></div></div>
      <div className="divide-y divide-[#F2F2F5]">
        {data.data.map((r) => (
          <div key={r.key} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3" data-testid={`rule-${r.key}`}>
            <div className="min-w-0">
              <p className="flex items-center gap-2 text-[13px] font-semibold text-[#1C1C1E]">{r.label}{r.overridden ? <span className="status-pill tone-info">disesuaikan</span> : <span className="status-pill tone-neutral">bawaan</span>}</p>
              <p className="font-mono text-[11.5px] text-[#6B6B73]">{r.pattern} · reset {(data.reset_options.find((o) => o.value === r.reset) || {}).label?.toLowerCase()} · lebar {r.width}</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right"><p className="text-[10.5px] uppercase text-[#8E8E93]">Berikutnya</p><p className="font-mono text-[13px] font-bold" data-testid={`rule-preview-${r.key}`}>{r.preview}</p></div>
              <button className="secondary-button" onClick={() => setEdit(r)} data-testid={`rule-edit-${r.key}`}><Pencil size={13} /> Ubah</button>
              {r.overridden ? <button className="icon-button !h-8 !w-8" title="Kembalikan bawaan" onClick={() => reset(r.key)} data-testid={`rule-reset-${r.key}`}><RotateCcw size={13} /></button> : null}
            </div>
          </div>
        ))}
      </div>
      {edit ? <RuleDialog rule={edit} meta={data} onClose={() => setEdit(null)} onSaved={load} /> : null}
    </section>
  );
}

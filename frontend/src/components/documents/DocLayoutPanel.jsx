import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Eye, Loader2, RotateCcw, Save, FileText, Palette, Rows3, Table2, PenLine, SlidersHorizontal } from "lucide-react";
import apiClient from "@/services/apiClient";
import { LoadingState, ErrorState } from "@/components/shared/DataStates";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import ScriptForm from "@/components/documents/ScriptForm";
import BrandForm from "@/components/documents/BrandForm";
import RowsForm from "@/components/documents/RowsForm";
import TableForm from "@/components/documents/TableForm";
import SignaturesForm from "@/components/documents/SignaturesForm";
import OptionsForm from "@/components/documents/OptionsForm";

const SUB = [
  ["script", "Naskah", FileText], ["brand", "Kop & Identitas", Palette], ["rows", "Baris Biaya", Rows3],
  ["table", "Gaya Tabel", Table2], ["sign", "Tanda Tangan", PenLine], ["options", "Opsi", SlidersHorizontal],
];

function pick(layout) {
  if (!layout) return {};
  const { brand, table, sections, money_rows, signatures, options } = layout;
  return { brand, table, sections, money_rows, signatures, options };
}

export default function DocLayoutPanel() {
  const [targets, setTargets] = useState([]);
  const [code, setCode] = useState("INVOICE_DP");
  const [layout, setLayout] = useState(null);
  const [script, setScript] = useState(null);
  const [naskah, setNaskah] = useState("");
  const [sub, setSub] = useState("script");
  const [state, setState] = useState({ loading: true, error: "" });
  const [preview, setPreview] = useState({ url: "", busy: false });
  const [saving, setSaving] = useState("");
  const [dirty, setDirty] = useState(false);
  const timer = useRef(null);

  const load = useCallback(async () => {
    setState({ loading: true, error: "" });
    try {
      const [t, l, s] = await Promise.all([
        apiClient.get("/doc-layouts"), apiClient.get(`/doc-layouts/${code}`), apiClient.get(`/doc-layouts/${code}/script`)]);
      setTargets(t.data.data || []); setLayout(l.data.data); setScript(s.data.data); setNaskah(s.data.data?.content || "");
      setDirty(false); setState({ loading: false, error: "" });
    } catch (e) { setState({ loading: false, error: e?.response?.data?.detail || "Gagal memuat konfigurasi dokumen." }); }
  }, [code]);
  useEffect(() => { load(); }, [load]);

  const doPreview = useCallback(async (lay, text) => {
    setPreview((p) => ({ ...p, busy: true }));
    try {
      const r = await apiClient.post(`/doc-layouts/${code}/preview`, { ...pick(lay), script: text }, { responseType: "blob" });
      setPreview((p) => { if (p.url) window.URL.revokeObjectURL(p.url); return { url: window.URL.createObjectURL(r.data), busy: false }; });
    } catch (e) { setPreview((p) => ({ ...p, busy: false })); toast.error("Pratinjau gagal — periksa placeholder naskah."); }
  }, [code]);

  useEffect(() => {
    if (!layout) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(() => doPreview(layout, naskah), 600);
    return () => clearTimeout(timer.current);
  }, [layout, naskah, doPreview]);

  const patch = (key, value) => { setLayout((l) => ({ ...l, [key]: value })); setDirty(true); };

  const saveLayout = async () => {
    setSaving("layout");
    try { const r = await apiClient.put(`/doc-layouts/${code}`, pick(layout)); setLayout(r.data.data); setDirty(false); toast.success("Tampilan dokumen disimpan"); }
    catch (e) { toast.error(e?.response?.data?.detail?.[0]?.msg || e?.response?.data?.detail || "Gagal menyimpan"); }
    finally { setSaving(""); }
  };
  const saveScript = async () => {
    setSaving("script");
    try { const r = await apiClient.put(`/doc-layouts/${code}/script`, { content: naskah }); setScript(r.data.data); toast.success("Naskah dokumen disimpan"); }
    catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan naskah"); }
    finally { setSaving(""); }
  };
  const resetLayout = async () => {
    if (!window.confirm("Kembalikan tampilan dokumen ini ke bawaan?")) return;
    await apiClient.delete(`/doc-layouts/${code}`); toast.success("Dikembalikan ke bawaan"); load();
  };
  const resetScript = async () => {
    if (!window.confirm("Kembalikan naskah ke bawaan?")) return;
    await apiClient.delete(`/doc-layouts/${code}/script`); toast.success("Naskah dikembalikan ke bawaan"); load();
  };

  if (state.loading) return <LoadingState testId="doclayout-loading" />;
  if (state.error) return <ErrorState message={state.error} onRetry={load} />;
  const cur = targets.find((t) => t.code === code);

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_460px]" data-testid="doclayout-panel">
      <div className="space-y-3">
        <section className="section-card">
          <div className="section-body flex flex-wrap items-center gap-3">
            <div className="min-w-[260px] flex-1 space-y-1">
              <p className="text-[11px] uppercase tracking-wide text-[#8E8E93]">Jenis dokumen</p>
              <Select value={code} onValueChange={setCode}>
                <SelectTrigger data-testid="doclayout-code"><SelectValue /></SelectTrigger>
                <SelectContent>{targets.map((t) => <SelectItem key={t.code} value={t.code}>{t.label}{t.customized ? " •" : ""}</SelectItem>)}</SelectContent>
              </Select>
              <p className="text-[11.5px] text-[#6B6B73]">
                {code === "__default__" ? "Identitas & gaya di sini dipakai SEMUA dokumen; jenis lain hanya menyimpan yang berbeda." : cur?.customized ? `Tampilan disesuaikan (v${cur.version}) oleh ${cur.updated_by || "-"}` : "Memakai bawaan + identitas perusahaan."}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button className="secondary-button" onClick={() => doPreview(layout, naskah)} disabled={preview.busy} data-testid="doclayout-preview"><Eye size={14} /> Pratinjau</button>
              <button className="secondary-button" onClick={sub === "script" ? resetScript : resetLayout} data-testid="doclayout-reset"><RotateCcw size={14} /> Bawaan</button>
              <button className="primary-button" onClick={sub === "script" ? saveScript : saveLayout} disabled={Boolean(saving)} data-testid="doclayout-save">
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} {sub === "script" ? "Simpan Naskah" : `Simpan Tampilan${dirty ? " *" : ""}`}
              </button>
            </div>
          </div>
        </section>
        <div className="tab-bar">
          {SUB.map(([k, l, Icon]) => (
            <button key={k} className={`tab-button ${sub === k ? "active" : ""}`} onClick={() => setSub(k)} data-testid={`doclayout-sub-${k}`}><Icon size={13} /> {l}</button>
          ))}
        </div>
        {sub === "script" && <ScriptForm script={script} value={naskah} onChange={setNaskah} />}
        {sub === "brand" && <BrandForm brand={layout.brand} onChange={(b) => patch("brand", b)} />}
        {sub === "rows" && <RowsForm rows={layout.money_rows} sections={layout.sections} onRows={(r) => patch("money_rows", r)} onSections={(s) => patch("sections", s)} />}
        {sub === "table" && <TableForm table={layout.table} onChange={(t) => patch("table", t)} />}
        {sub === "sign" && <SignaturesForm signatures={layout.signatures} onChange={(s) => patch("signatures", s)} />}
        {sub === "options" && <OptionsForm options={layout.options} onChange={(o) => patch("options", o)} />}
      </div>
      <section className="section-card xl:sticky xl:top-4 xl:self-start" data-testid="doclayout-preview-pane">
        <div className="section-head"><div className="flex items-center gap-2"><Eye size={15} className="text-[#007AFF]" /><h2>Pratinjau PDF (data contoh)</h2></div>
          <div className="flex items-center gap-2">{preview.busy ? <Loader2 size={14} className="animate-spin text-[#8E8E93]" /> : null}
            {preview.url ? <button className="secondary-button !h-7 !text-[11.5px]" onClick={() => window.open(preview.url, "_blank", "noopener")} data-testid="doclayout-preview-open">Buka di tab baru</button> : null}</div></div>
        <div className="bg-[#E9EAEE] p-2">
          {preview.url ? <iframe title="pratinjau" src={`${preview.url}#toolbar=0&view=FitH`} className="h-[72vh] w-full rounded-[8px] bg-white" data-testid="doclayout-preview-frame" />
            : <div className="flex h-[72vh] items-center justify-center text-[12.5px] text-[#6B6B73]">Menyiapkan pratinjau…</div>}
        </div>
      </section>
    </div>
  );
}

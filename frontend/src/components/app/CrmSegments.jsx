import { useCallback, useEffect, useState } from "react";
import { Filter, Plus, Trash2, Eye, Loader2, Users2 } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { LoadingState, EmptyState } from "@/components/shared/DataStates";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";

const LEAD_SRC = ["website", "whatsapp", "referral", "instagram", "ads", "manual"];
const BANDS = ["hot", "warm", "cold"];
const RFM = ["Champions", "Loyal", "Pelanggan Baru", "Potensial", "Berisiko (At Risk)", "Hibernasi/Hilang"];
const LIFE = ["aktif", "at_risk", "churned", "prospek"];

function emptySeg() { return { name: "", audience: "customer", description: "", criteria: {} }; }

export default function CrmSegments() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState({});

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/crm/segments").then((r) => setRows(Array.isArray(r.data) ? r.data : []))
      .catch(() => setRows([])).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const setC = (k, v) => setEditing((s) => ({ ...s, criteria: { ...(s.criteria || {}), [k]: v || undefined } }));
  const save = async () => {
    if (!editing.name.trim()) { toast.error("Nama segmen wajib diisi"); return; }
    setBusy(true);
    try {
      if (editing.id) await apiClient.patch(`/crm/segments/${editing.id}`, editing);
      else await apiClient.post("/crm/segments", editing);
      toast.success("Segmen disimpan"); setEditing(null); load();
    } catch (e) { toast.error("Gagal menyimpan segmen"); } finally { setBusy(false); }
  };
  const remove = async (s) => { if (!window.confirm(`Hapus segmen "${s.name}"?`)) return;
    try { await apiClient.delete(`/crm/segments/${s.id}`); toast.success("Segmen dihapus"); load(); } catch (e) { toast.error("Gagal"); } };
  const doPreview = async (s) => {
    try { const r = await apiClient.get(`/crm/segments/${s.id}/preview`); setPreview((p) => ({ ...p, [s.id]: r.data })); }
    catch (e) { toast.error("Gagal pratinjau"); }
  };

  const audience = editing?.audience || "customer";
  return (
    <div className="space-y-3" data-testid="crm-segments">
      <div className="flex items-center justify-between">
        <p className="text-[12.5px] text-[#6B6B73]">Segmen audiens dinamis untuk kampanye & nurturing.</p>
        <button className="primary-button" onClick={() => setEditing(emptySeg())} data-testid="segment-add"><Plus size={14} /> Segmen Baru</button>
      </div>
      {loading ? <LoadingState testId="segments-loading" /> : rows.length === 0 ? (
        <EmptyState title="Belum ada segmen" description="Buat segmen pelanggan/lead untuk menarget kampanye WhatsApp." testId="segments-empty" />
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2" data-testid="segments-list">
          {rows.map((s) => (
            <section key={s.id} className="section-card" data-testid={`segment-${s.id}`}>
              <div className="section-head"><div className="flex min-w-0 items-center gap-2"><Filter size={15} className="text-[#5856D6]" /><h2 className="truncate">{s.name}</h2></div>
                <span className="rounded-full bg-[#F2F2F5] px-2 py-0.5 text-[10.5px] font-semibold text-[#6B6B73]">{s.audience === "lead" ? "Lead" : "Pelanggan"}</span></div>
              <div className="section-body">
                <p className="mb-2 text-[12px] text-[#6B6B73]">{s.description || "—"}</p>
                <div className="mb-2 flex flex-wrap gap-1">
                  {Object.entries(s.criteria || {}).map(([k, v]) => <span key={k} className="rounded bg-[#F2F2F5] px-1.5 py-0.5 text-[10.5px] text-[#3C3C43]">{k}: {String(v)}</span>)}
                  {Object.keys(s.criteria || {}).length === 0 ? <span className="text-[11px] text-[#A0A0A8]">Semua {s.audience}</span> : null}
                </div>
                {preview[s.id] ? (
                  <p className="mb-2 flex items-center gap-1 text-[12px] font-semibold text-[#126E2C]"><Users2 size={13} /> {preview[s.id].count} anggota · {preview[s.id].reachable} ber-WA</p>
                ) : null}
                <div className="flex items-center gap-2">
                  <button className="secondary-button !h-8" onClick={() => doPreview(s)} data-testid={`segment-preview-${s.id}`}><Eye size={13} /> Pratinjau</button>
                  <button className="secondary-button !h-8" onClick={() => setEditing({ ...s })} data-testid={`segment-edit-${s.id}`}>Ubah</button>
                  <button className="icon-button !h-8 !w-8" onClick={() => remove(s)} data-testid={`segment-del-${s.id}`}><Trash2 size={14} /></button>
                </div>
              </div>
            </section>
          ))}
        </div>
      )}

      <Dialog open={!!editing} onOpenChange={(v) => !v && setEditing(null)}>
        <DialogContent data-testid="segment-dialog">
          <DialogHeader><DialogTitle>{editing?.id ? "Ubah Segmen" : "Segmen Baru"}</DialogTitle></DialogHeader>
          {editing ? (
            <div className="max-h-[60vh] space-y-3 overflow-y-auto pr-1">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5"><Label>Nama</Label><Input value={editing.name} onChange={(e) => setEditing((s) => ({ ...s, name: e.target.value }))} data-testid="segment-name" /></div>
                <div className="space-y-1.5"><Label>Audiens</Label>
                  <Select value={editing.audience} onValueChange={(v) => setEditing((s) => ({ ...s, audience: v, criteria: {} }))}>
                    <SelectTrigger data-testid="segment-audience"><SelectValue /></SelectTrigger>
                    <SelectContent><SelectItem value="customer">Pelanggan</SelectItem><SelectItem value="lead">Lead</SelectItem></SelectContent>
                  </Select></div>
              </div>
              <div className="space-y-1.5"><Label>Deskripsi</Label><Input value={editing.description || ""} onChange={(e) => setEditing((s) => ({ ...s, description: e.target.value }))} data-testid="segment-desc" /></div>
              <div className="rounded-[10px] border border-[#EFF0F2] p-3 space-y-2">
                <Label>Kriteria (kosongkan = semua)</Label>
                <Input placeholder="Cari nama/telepon (q)" value={editing.criteria?.q || ""} onChange={(e) => setC("q", e.target.value)} data-testid="segment-q" />
                {audience === "lead" ? (
                  <div className="grid grid-cols-2 gap-2">
                    <Select value={editing.criteria?.source || "any"} onValueChange={(v) => setC("source", v === "any" ? "" : v)}>
                      <SelectTrigger data-testid="segment-source"><SelectValue placeholder="Sumber" /></SelectTrigger>
                      <SelectContent><SelectItem value="any">Semua sumber</SelectItem>{LEAD_SRC.map((x) => <SelectItem key={x} value={x}>{x}</SelectItem>)}</SelectContent>
                    </Select>
                    <Select value={editing.criteria?.score_band || "any"} onValueChange={(v) => setC("score_band", v === "any" ? "" : v)}>
                      <SelectTrigger data-testid="segment-band"><SelectValue placeholder="Band skor" /></SelectTrigger>
                      <SelectContent><SelectItem value="any">Semua band</SelectItem>{BANDS.map((x) => <SelectItem key={x} value={x}>{x}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2">
                    <Select value={editing.criteria?.rfm_segment || "any"} onValueChange={(v) => setC("rfm_segment", v === "any" ? "" : v)}>
                      <SelectTrigger data-testid="segment-rfm"><SelectValue placeholder="Segmen RFM" /></SelectTrigger>
                      <SelectContent><SelectItem value="any">Semua RFM</SelectItem>{RFM.map((x) => <SelectItem key={x} value={x}>{x}</SelectItem>)}</SelectContent>
                    </Select>
                    <Select value={editing.criteria?.lifecycle || "any"} onValueChange={(v) => setC("lifecycle", v === "any" ? "" : v)}>
                      <SelectTrigger data-testid="segment-lifecycle"><SelectValue placeholder="Lifecycle" /></SelectTrigger>
                      <SelectContent><SelectItem value="any">Semua lifecycle</SelectItem>{LIFE.map((x) => <SelectItem key={x} value={x}>{x}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                )}
                <Input type="number" placeholder={audience === "lead" ? "Nilai minimum (Rp)" : "LTV minimum (Rp)"} value={editing.criteria?.min_value || ""} onChange={(e) => setC("min_value", e.target.value)} data-testid="segment-minval" />
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <button className="secondary-button" onClick={() => setEditing(null)} data-testid="segment-cancel">Batal</button>
            <button className="primary-button" onClick={save} disabled={busy} data-testid="segment-save">{busy ? <Loader2 size={14} className="animate-spin" /> : null} Simpan</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

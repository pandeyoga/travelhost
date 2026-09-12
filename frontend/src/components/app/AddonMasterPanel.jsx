import { useCallback, useEffect, useState } from "react";
import { PackagePlus, Plus, Pencil, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { Input } from "@/components/ui/input";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import { formatCurrency } from "@/utils/formatters";

// AddonMasterPanel — kelola master Add-on booking (label + nominal default + aktif/nonaktif).
// Nonaktif = hilang dari pilihan form booking; booking lama tetap utuh (snapshot label+amount).
export default function AddonMasterPanel() {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState({ label: "", amount: "" });
  const [editId, setEditId] = useState(null);
  const [edit, setEdit] = useState({ label: "", amount: "" });
  const [delTarget, setDelTarget] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await apiClient.get("/addons?include_inactive=true");
      setRows(Array.isArray(r.data) ? r.data : []);
    } catch {
      setRows([]);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const act = async (fn, okMsg) => {
    setBusy(true);
    try { await fn(); toast.success(okMsg); await load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan"); }
    finally { setBusy(false); }
  };

  const create = () => {
    if (!draft.label.trim()) { toast.error("Nama add-on wajib diisi"); return; }
    act(async () => {
      await apiClient.post("/addons", { label: draft.label.trim(), default_amount: Number(draft.amount) || 0 });
      setDraft({ label: "", amount: "" }); setAdding(false);
    }, `Add-on "${draft.label.trim()}" ditambahkan`);
  };
  const saveEdit = (r) => {
    if (!edit.label.trim()) { toast.error("Nama add-on wajib diisi"); return; }
    act(async () => {
      await apiClient.patch(`/addons/${r.id}`, { label: edit.label.trim(), default_amount: Number(edit.amount) || 0 });
      setEditId(null);
    }, `Add-on "${edit.label.trim()}" diperbarui`);
  };
  const toggle = (r) => act(async () => {
    await apiClient.patch(`/addons/${r.id}`, { active: !(r.active !== false) });
  }, r.active !== false ? `"${r.label}" dinonaktifkan (hilang dari form booking)` : `"${r.label}" diaktifkan`);
  const doDelete = () => act(async () => {
    await apiClient.delete(`/addons/${delTarget.id}`);
    setDelTarget(null);
  }, `Add-on "${delTarget?.label}" dihapus`);

  return (
    <section className="rounded-[14px] border border-[#EFF0F2] bg-white shadow-sm" data-testid="md-addon-panel">
      <div className="flex items-start justify-between gap-2 border-b border-[#EFF0F2] px-4 py-3">
        <div>
          <h2 className="flex items-center gap-2 text-[14px] font-bold text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>
            <PackagePlus size={15} className="text-[#007AFF]" /> Add-on Booking
            <span className="rounded-full bg-[#EAF2FF] px-2 py-0.5 text-[11px] font-semibold text-[#0058CC]">{rows.length}</span>
          </h2>
          <p className="mt-0.5 text-[12px] text-[#6B6B73]">Dipakai form booking (Tol, parkir, penginapan driver, dll.). Nonaktif menyembunyikan dari form; booking lama tetap utuh.</p>
        </div>
        <button className="secondary-button !h-8 !px-2.5 !text-[12px]" onClick={() => setAdding((v) => !v)} data-testid="md-addon-add-toggle">
          <Plus size={13} /> {adding ? "Batal" : "Tambah"}
        </button>
      </div>
      {adding ? (
        <div className="grid grid-cols-[1fr_140px_auto] gap-2 border-b border-[#F6F6F8] bg-[#F5F9FF] px-4 py-2.5" data-testid="md-addon-add-form">
          <Input value={draft.label} onChange={(e) => setDraft((d) => ({ ...d, label: e.target.value }))} placeholder="Nama add-on" className="!h-8" data-testid="md-addon-new-label" />
          <Input type="number" value={draft.amount} onChange={(e) => setDraft((d) => ({ ...d, amount: e.target.value }))} placeholder="Default Rp" className="!h-8" data-testid="md-addon-new-amount" />
          <button className="primary-button !h-8 !px-3 !text-[12px]" disabled={busy} onClick={create} data-testid="md-addon-new-save">
            {busy ? <Loader2 size={12} className="animate-spin" /> : "Simpan"}
          </button>
        </div>
      ) : null}
      <div>
        {rows.length === 0 ? (
          <p className="px-4 py-5 text-[12.5px] text-[#8E8E93]" data-testid="md-addon-empty">Belum ada master add-on — tambah di sini atau langsung dari form booking.</p>
        ) : rows.map((r) => {
          const active = r.active !== false;
          return (
            <div key={r.id} className="border-b border-[#F6F6F8] px-4 py-2.5" data-testid={`md-addon-row-${r.id}`}>
              {editId === r.id ? (
                <div className="grid grid-cols-[1fr_140px_auto_auto] items-center gap-2">
                  <Input value={edit.label} onChange={(e) => setEdit((d) => ({ ...d, label: e.target.value }))} className="!h-8" data-testid={`md-addon-edit-label-${r.id}`} />
                  <Input type="number" value={edit.amount} onChange={(e) => setEdit((d) => ({ ...d, amount: e.target.value }))} className="!h-8" data-testid={`md-addon-edit-amount-${r.id}`} />
                  <button className="primary-button !h-8 !px-3 !text-[12px]" disabled={busy} onClick={() => saveEdit(r)} data-testid={`md-addon-edit-save-${r.id}`}>Simpan</button>
                  <button className="secondary-button !h-8 !px-3 !text-[12px]" onClick={() => setEditId(null)} data-testid={`md-addon-edit-cancel-${r.id}`}>Batal</button>
                </div>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <div className="min-w-[160px]">
                    <span className={`font-semibold ${active ? "text-[#1C1C1E]" : "text-[#B0B1B8] line-through"}`}>{r.label}</span>
                    {!active ? <span className="ml-1.5 rounded-full bg-[#F1F1F4] px-1.5 py-0.5 text-[10px] font-semibold text-[#6B6B73]">Nonaktif</span> : null}
                  </div>
                  <span className="tabular-nums text-[12.5px] text-[#6B6B73]">Default: {formatCurrency(r.default_amount || 0)}</span>
                  <div className="ml-auto flex items-center gap-1.5">
                    <button className="icon-button !h-8 !w-8" title="Edit"
                      onClick={() => { setEditId(r.id); setEdit({ label: r.label, amount: String(r.default_amount || "") }); }}
                      data-testid={`md-addon-edit-${r.id}`}><Pencil size={13} /></button>
                    <button className={`secondary-button !h-8 !px-2.5 !text-[12px] ${active ? "!text-[#A8221A]" : "!text-[#126E2C]"}`}
                      disabled={busy} onClick={() => toggle(r)} data-testid={`md-addon-toggle-${r.id}`}>
                      {active ? "Nonaktifkan" : "Aktifkan"}
                    </button>
                    <button className="icon-button !h-8 !w-8 !text-[#A8221A]" title="Hapus" onClick={() => setDelTarget(r)} data-testid={`md-addon-delete-${r.id}`}><Trash2 size={13} /></button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <ConfirmDialog
        open={Boolean(delTarget)} onOpenChange={(v) => !v && setDelTarget(null)}
        title="Hapus master add-on?" description={delTarget ? `"${delTarget.label}" dihapus dari master. Booking lama tidak terpengaruh (menyimpan salinan sendiri).` : ""}
        busy={busy} onConfirm={doDelete} testId="md-addon-delete-confirm"
      />
    </section>
  );
}

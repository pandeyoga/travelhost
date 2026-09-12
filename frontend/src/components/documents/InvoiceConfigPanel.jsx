import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Landmark, Loader2, Plus, Save, Trash2 } from "lucide-react";
import apiClient from "@/services/apiClient";
import { LoadingState } from "@/components/shared/DataStates";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "@/components/documents/BrandForm";

export default function InvoiceConfigPanel() {
  const [cfg, setCfg] = useState(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { apiClient.get("/invoice-config").then((r) => setCfg(r.data)).catch(() => toast.error("Gagal memuat pengaturan invoice")); }, []);
  if (!cfg) return <LoadingState testId="invcfg-loading" />;
  const set = (k, v) => setCfg((c) => ({ ...c, [k]: v }));
  const banks = cfg.bank_accounts || [];
  const setBank = (i, patch) => set("bank_accounts", banks.map((b, idx) => (idx === i ? { ...b, ...patch } : b)));
  const save = async () => {
    setSaving(true);
    try {
      const r = await apiClient.put("/invoice-config", { ...cfg, bank_accounts: banks.filter((b) => b.bank && b.account_no && b.account_name) });
      setCfg(r.data); toast.success("Pengaturan invoice disimpan");
    } catch (e) { toast.error(e?.response?.data?.detail?.[0]?.msg || e?.response?.data?.detail || "Gagal menyimpan"); }
    finally { setSaving(false); }
  };
  return (
    <div className="space-y-3" data-testid="invoice-config-panel">
      <section className="section-card">
        <div className="section-head"><div className="flex items-center gap-2"><Landmark size={16} className="text-[#007AFF]" /><h2>Uang muka & jatuh tempo</h2></div>
          <button className="primary-button" onClick={save} disabled={saving} data-testid="invcfg-save">{saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Simpan</button></div>
        <div className="section-body grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Field label="DP bawaan (%)"><Input type="number" min={0} max={100} value={cfg.dp_percent_default ?? 30} onChange={(e) => set("dp_percent_default", Number(e.target.value))} data-testid="invcfg-dp_percent" /></Field>
          <Field label="Jatuh tempo DP (hari)"><Input type="number" min={0} value={cfg.dp_due_days ?? 3} onChange={(e) => set("dp_due_days", Number(e.target.value))} data-testid="invcfg-dp_due" /></Field>
          <Field label="Pelunasan: H- sebelum berangkat"><Input type="number" min={0} value={cfg.settlement_due_before_start_days ?? 1} onChange={(e) => set("settlement_due_before_start_days", Number(e.target.value))} data-testid="invcfg-settle_before" /></Field>
          <Field label="Pelunasan: jatuh tempo (hari) bila jadwal lewat"><Input type="number" min={0} value={cfg.settlement_due_days ?? 7} onChange={(e) => set("settlement_due_days", Number(e.target.value))} data-testid="invcfg-settle_days" /></Field>
          <div className="col-span-2 sm:col-span-4"><Field label="Syarat & ketentuan pembayaran (placeholder {{terms}})"><Textarea rows={3} value={cfg.payment_terms || ""} onChange={(e) => set("payment_terms", e.target.value)} data-testid="invcfg-terms" /></Field></div>
          <div className="col-span-2 sm:col-span-4"><Field label="Catatan kaki dokumen"><Input value={cfg.footer_note || ""} onChange={(e) => set("footer_note", e.target.value)} data-testid="invcfg-footer" /></Field></div>
        </div>
      </section>
      <section className="section-card">
        <div className="section-head"><h2>Rekening pembayaran (tercetak di invoice)</h2>
          <button className="secondary-button !h-8" onClick={() => set("bank_accounts", [...banks, { bank: "", account_no: "", account_name: "" }])} data-testid="invcfg-bank-add"><Plus size={13} /> Tambah rekening</button></div>
        <div className="section-body space-y-2">
          {banks.length === 0 ? <p className="text-[12.5px] text-[#6B6B73]">Belum ada rekening. Tambahkan minimal satu agar pelanggan tahu ke mana harus transfer.</p> : null}
          {banks.map((b, i) => (
            <div key={b.id || i} className="grid grid-cols-1 gap-2 rounded-[10px] border border-[#F2F2F5] p-2 sm:grid-cols-[1fr_1fr_1.4fr_auto]" data-testid={`bank-${i}`}>
              <Input placeholder="Bank (BCA/Mandiri/BRI)" value={b.bank} onChange={(e) => setBank(i, { bank: e.target.value })} data-testid={`bank-name-${i}`} />
              <Input placeholder="Nomor rekening" value={b.account_no} onChange={(e) => setBank(i, { account_no: e.target.value })} data-testid={`bank-no-${i}`} />
              <Input placeholder="Atas nama" value={b.account_name} onChange={(e) => setBank(i, { account_name: e.target.value })} data-testid={`bank-owner-${i}`} />
              <button className="icon-button !h-9 !w-9 !text-[#FF3B30]" onClick={() => set("bank_accounts", banks.filter((_, idx) => idx !== i))} data-testid={`bank-remove-${i}`}><Trash2 size={13} /></button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

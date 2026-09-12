import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Plus, Trash2, Download, FileSpreadsheet, BadgeCheck, Wallet } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { formatCurrency, formatDate, formatQty } from "@/utils/formatters";

const STATUS = {
  draft: { l: "Draft", tone: "neutral" },
  approved: { l: "Disetujui", tone: "info" },
  paid: { l: "Dibayar", tone: "success" },
};
const PERIOD_LABEL = { monthly: "Bulanan", weekly: "Mingguan", per_trip: "Per Trip" };

async function downloadFile(url, filename) {
  try {
    const res = await apiClient.get(url, { responseType: "blob" });
    const blobUrl = window.URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = blobUrl; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    window.URL.revokeObjectURL(blobUrl);
  } catch (e) { toast.error("Gagal mengunduh slip"); }
}

function Row({ label, value, strong, negative }) {
  return (
    <div className="flex items-center justify-between rounded-[10px] border border-[#F2F2F5] px-3 py-2">
      <span className="text-[12.5px] text-[#3C3C43]">{label}</span>
      <span className={`tabular-nums ${strong ? "text-[14px] font-bold" : "text-[13px]"}`} style={{ color: negative ? "#A8221A" : "#1C1C1E" }}>
        {negative ? "-" : ""}{formatCurrency(value)}
      </span>
    </div>
  );
}

export default function PayoutDetailDialog({ payoutId, onOpenChange, onChanged, canManage }) {
  const open = Boolean(payoutId);
  const [p, setP] = useState(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState("");
  const [bonuses, setBonuses] = useState([]);
  const [deductions, setDeductions] = useState([]);
  const [notes, setNotes] = useState("");

  const load = useCallback(async () => {
    if (!payoutId) return;
    setLoading(true);
    try {
      const r = await apiClient.get(`/payroll/payouts/${payoutId}`);
      setP(r.data);
      setBonuses(r.data.bonuses || []);
      setDeductions(r.data.deductions || []);
      setNotes(r.data.notes || "");
    } catch (e) { toast.error("Gagal memuat payout"); }
    finally { setLoading(false); }
  }, [payoutId]);

  useEffect(() => { if (open) load(); }, [open, load]);

  const isDraft = p && p.status === "draft";
  const addLine = (setter, list) => setter([...(list || []), { label: "", amount: 0 }]);
  const editLine = (setter, list, i, k, v) => setter(list.map((x, idx) => (idx === i ? { ...x, [k]: k === "amount" ? v : v } : x)));
  const rmLine = (setter, list, i) => setter(list.filter((_, idx) => idx !== i));

  const saveDraft = async () => {
    setBusy("save");
    try {
      const payload = {
        bonuses: bonuses.map((b) => ({ label: b.label || "", amount: Number(b.amount) || 0 })),
        deductions: deductions.map((d) => ({ label: d.label || "", amount: Number(d.amount) || 0 })),
        notes,
      };
      const r = await apiClient.patch(`/payroll/payouts/${payoutId}`, payload);
      setP(r.data); toast.success("Payout diperbarui"); onChanged && onChanged();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan"); }
    finally { setBusy(""); }
  };

  const doAction = async (action) => {
    setBusy(action);
    try {
      const r = await apiClient.post(`/payroll/payouts/${payoutId}/${action}`);
      setP(r.data);
      toast.success(action === "approve" ? "Payout disetujui + dicatat ke Finance (akrual)" : "Payout dibayar + expense ditandai lunas");
      onChanged && onChanged();
    } catch (e) { toast.error(e?.response?.data?.detail || "Aksi gagal"); }
    finally { setBusy(""); }
  };

  const del = async () => {
    setBusy("delete");
    try {
      await apiClient.delete(`/payroll/payouts/${payoutId}`);
      toast.success("Payout draft dihapus"); onChanged && onChanged(); onOpenChange(false);
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menghapus"); }
    finally { setBusy(""); }
  };

  const st = p ? (STATUS[p.status] || { l: p.status, tone: "neutral" }) : {};

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] max-w-lg overflow-y-auto" data-testid="payout-detail">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            Slip Payout {p ? <span className={`status-pill tone-${st.tone}`}>{st.l}</span> : null}
          </DialogTitle>
          <DialogDescription>
            {p ? `${p.driver_name} · ${formatDate(p.period_start)} → ${formatDate(p.period_end)} · ${PERIOD_LABEL[p.period_type] || p.period_type}` : "Memuat…"}
          </DialogDescription>
        </DialogHeader>

        {loading || !p ? (
          <div className="py-10 text-center text-[13px] text-[#8E8E93]" data-testid="payout-detail-loading">Memuat…</div>
        ) : (
          <div className="space-y-3" data-testid="payout-detail-body">
            <div className="grid grid-cols-2 gap-2 text-[12px]">
              <div className="rounded-[10px] bg-[#FAFAFB] px-3 py-2">Trip selesai: <span className="font-semibold tabular-nums">{formatQty(p.trips_count || 0)}</span></div>
              <div className="rounded-[10px] bg-[#FAFAFB] px-3 py-2">Total KM: <span className="font-semibold tabular-nums">{formatQty(p.total_km || 0)}</span></div>
            </div>

            <Row label={`Gaji Pokok (${PERIOD_LABEL[p.period_type] || "-"})`} value={p.base_salary} />
            <Row label={`Komisi per Trip (${formatQty(p.trips_count || 0)} trip)`} value={p.commission_trip} />
            <Row label={`Komisi % Revenue (${formatCurrency(p.total_revenue)})`} value={p.commission_pct} />
            <Row label={`Uang Jalan (${formatQty(p.total_km || 0)} km)`} value={p.allowance_km} />
            <Row label="Subtotal (Gross)" value={p.gross} strong />

            {/* Bonus */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Bonus</span>
                {isDraft && canManage ? <button className="secondary-button !h-7" onClick={() => addLine(setBonuses, bonuses)} data-testid="payout-add-bonus"><Plus size={12} /> Baris</button> : null}
              </div>
              {(isDraft ? bonuses : (p.bonuses || [])).length === 0 ? <p className="text-[12px] text-[#8E8E93]">—</p> : null}
              {isDraft && canManage ? bonuses.map((b, i) => (
                <div key={i} className="flex items-center gap-2">
                  <Input value={b.label} onChange={(e) => editLine(setBonuses, bonuses, i, "label", e.target.value)} placeholder="Label bonus" data-testid={`payout-bonus-label-${i}`} />
                  <Input type="number" className="w-32" value={b.amount} onChange={(e) => editLine(setBonuses, bonuses, i, "amount", e.target.value)} placeholder="0" data-testid={`payout-bonus-amt-${i}`} />
                  <button className="icon-button !h-8 !w-8 !text-[#A8221A]" onClick={() => rmLine(setBonuses, bonuses, i)} data-testid={`payout-bonus-rm-${i}`}><Trash2 size={14} /></button>
                </div>
              )) : (p.bonuses || []).map((b, i) => <Row key={i} label={`Bonus · ${b.label || "Bonus"}`} value={b.amount} />)}
            </div>

            {/* Potongan */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Potongan</span>
                {isDraft && canManage ? <button className="secondary-button !h-7" onClick={() => addLine(setDeductions, deductions)} data-testid="payout-add-deduction"><Plus size={12} /> Baris</button> : null}
              </div>
              {(isDraft ? deductions : (p.deductions || [])).length === 0 ? <p className="text-[12px] text-[#8E8E93]">—</p> : null}
              {isDraft && canManage ? deductions.map((d, i) => (
                <div key={i} className="flex items-center gap-2">
                  <Input value={d.label} onChange={(e) => editLine(setDeductions, deductions, i, "label", e.target.value)} placeholder="Label potongan" data-testid={`payout-ded-label-${i}`} />
                  <Input type="number" className="w-32" value={d.amount} onChange={(e) => editLine(setDeductions, deductions, i, "amount", e.target.value)} placeholder="0" data-testid={`payout-ded-amt-${i}`} />
                  <button className="icon-button !h-8 !w-8 !text-[#A8221A]" onClick={() => rmLine(setDeductions, deductions, i)} data-testid={`payout-ded-rm-${i}`}><Trash2 size={14} /></button>
                </div>
              )) : (p.deductions || []).map((d, i) => <Row key={i} label={`Potongan · ${d.label || "Potongan"}`} value={d.amount} negative />)}
            </div>

            {isDraft && canManage ? (
              <div className="space-y-1.5">
                <span className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Catatan</span>
                <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Catatan payout (opsional)" data-testid="payout-notes" />
              </div>
            ) : (p.notes ? <p className="text-[12px] text-[#6B6B73]">Catatan: {p.notes}</p> : null)}

            <div className="flex items-center justify-between rounded-[10px] px-3 py-3" style={{ background: "rgba(52,199,89,0.10)" }}>
              <span className="text-[13px] font-semibold text-[#126E2C]">Total Diterima</span>
              <span className="text-[18px] font-bold tabular-nums text-[#126E2C]" data-testid="payout-total">{formatCurrency(p.total)}</span>
            </div>

            {p.status !== "draft" ? (
              <p className="text-[11.5px] text-[#8E8E93]">
                {p.approver_name ? `Disetujui oleh ${p.approver_name}` : ""}{p.approved_at ? ` · ${formatDate(p.approved_at)}` : ""}{p.paid_at ? ` · dibayar ${formatDate(p.paid_at)}` : ""}
              </p>
            ) : null}

            {isDraft && canManage ? (
              <button className="secondary-button w-full" disabled={busy === "save"} onClick={saveDraft} data-testid="payout-save-draft">
                {busy === "save" ? <Loader2 size={14} className="animate-spin" /> : null} Simpan Perubahan (bonus/potongan)
              </button>
            ) : null}
          </div>
        )}

        <DialogFooter className="flex-wrap gap-2">
          {p ? (
            <>
              <button className="secondary-button" onClick={() => downloadFile(`/payroll/payouts/${p.id}/slip?format=pdf`, `slip-${p.driver_name}.pdf`)} data-testid="payout-slip-pdf"><Download size={13} /> Slip PDF</button>
              <button className="secondary-button" onClick={() => downloadFile(`/payroll/payouts/${p.id}/slip?format=excel`, `slip-${p.driver_name}.xlsx`)} data-testid="payout-slip-excel"><FileSpreadsheet size={13} /> Excel</button>
              {canManage && p.status === "draft" ? (
                <>
                  <button className="icon-button !text-[#A8221A]" title="Hapus draft" disabled={busy === "delete"} onClick={del} data-testid="payout-delete"><Trash2 size={15} /></button>
                  <button className="primary-button" disabled={busy === "approve"} onClick={() => doAction("approve")} data-testid="payout-approve">
                    {busy === "approve" ? <Loader2 size={14} className="animate-spin" /> : <BadgeCheck size={14} />} Setujui
                  </button>
                </>
              ) : null}
              {canManage && p.status === "approved" ? (
                <button className="primary-button" disabled={busy === "pay"} onClick={() => doAction("pay")} data-testid="payout-pay">
                  {busy === "pay" ? <Loader2 size={14} className="animate-spin" /> : <Wallet size={14} />} Tandai Dibayar
                </button>
              ) : null}
            </>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

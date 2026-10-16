import { useEffect, useState } from "react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { StatusPill } from "@/components/shared/StatusPill";
import { Loader2, Handshake } from "lucide-react";
import { formatCurrency, formatDate } from "@/utils/formatters";

const SC_TONE = { requested: "warning", confirmed: "info", settled: "success", cancelled: "neutral" };

function Metric({ label, value, danger }) {
  return (
    <div className="rounded-lg border border-[#E5E5EA] bg-[#F9F9FB] p-3">
      <p className="text-[11px] font-medium uppercase tracking-wide text-[#8A8A8E]">{label}</p>
      <p className={`mt-0.5 text-lg font-bold tabular-nums ${danger ? "text-[#A8221A]" : "text-[#1C1C1E]"}`}>{value}</p>
    </div>
  );
}

export default function PartnerDetailDrawer({ open, partner, onOpenChange }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !partner?.id) { setDetail(null); return; }
    setLoading(true);
    apiClient.get(`/partners/${partner.id}`)
      .then((r) => setDetail(r.data))
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, [open, partner]);

  const d = detail || partner || {};
  const subs = d.subcharters || [];
  const setts = d.settlements || [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl" data-testid="partner-detail-drawer">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Handshake size={18} className="text-[#007AFF]" /> {d.name || "Mitra"}</DialogTitle>
          <DialogDescription>{d.pic ? `PIC ${d.pic}` : ""}{d.phone ? ` · ${d.phone}` : ""}{d.city ? ` · ${d.city}` : ""}</DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-10 text-[#8A8A8E]"><Loader2 className="animate-spin" size={20} /></div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <Metric label="Total COGS" value={formatCurrency(d.ap_total)} />
              <Metric label="Sudah Dibayar" value={formatCurrency(d.ap_paid)} />
              <Metric label="Sisa Utang" value={formatCurrency(d.ap_outstanding)} danger={Number(d.ap_outstanding) > 0} />
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-[#1C1C1E]">Order Sub-charter ({subs.length})</h3>
              {subs.length === 0 ? <p className="text-sm text-[#8A8A8E]">Belum ada order.</p> : (
                <div className="overflow-hidden rounded-lg border border-[#E5E5EA]">
                  <table className="w-full text-sm" data-testid="partner-detail-subcharters">
                    <thead className="bg-[#F9F9FB] text-left text-xs text-[#8A8A8E]"><tr>
                      <th className="px-3 py-2">Kode</th><th className="px-3 py-2">Unit</th>
                      <th className="px-3 py-2">Periode</th><th className="px-3 py-2 text-right">Biaya</th><th className="px-3 py-2">Status</th>
                    </tr></thead>
                    <tbody>{subs.map((s) => (
                      <tr key={s.id} className="border-t border-[#F0F0F2]">
                        <td className="px-3 py-2 font-mono">{s.code}</td>
                        <td className="px-3 py-2">{s.vehicle_label || "—"}</td>
                        <td className="px-3 py-2">{formatDate(s.start_datetime)} → {formatDate(s.end_datetime)}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(s.cost)}</td>
                        <td className="px-3 py-2"><StatusPill value={s.status} tone={SC_TONE[s.status] || "neutral"} /></td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              )}
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-[#1C1C1E]">Riwayat Pelunasan ({setts.length})</h3>
              {setts.length === 0 ? <p className="text-sm text-[#8A8A8E]">Belum ada pelunasan.</p> : (
                <ul className="space-y-1.5" data-testid="partner-detail-settlements">{setts.map((s) => (
                  <li key={s.id} className="flex items-center justify-between rounded-lg border border-[#E5E5EA] px-3 py-2 text-sm">
                    <span className="text-[#8A8A8E]">{formatDate(s.paid_at || s.created_at)} · {s.method}</span>
                    <span className="font-semibold tabular-nums text-[#34C759]">{formatCurrency(s.amount)}</span>
                  </li>
                ))}</ul>
              )}
            </div>

            {d.notes ? <p className="rounded-lg bg-[#F9F9FB] p-3 text-sm text-[#48484A]">{d.notes}</p> : null}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

import { useCallback, useEffect, useState } from "react";
import apiClient from "@/services/apiClient";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCurrency } from "@/utils/formatters";

const SEG_COLOR = { "Champions": "#126E2C", "Loyal": "#0058CC", "Pelanggan Baru": "#5856D6",
  "Potensial": "#AF52DE", "Berisiko (At Risk)": "#C25400", "Hibernasi/Hilang": "#FF3B30", "Perlu Perhatian": "#8E8E93" };
const LC = { aktif: ["Aktif", "#126E2C", "#E3F7E8"], at_risk: ["Berisiko", "#C25400", "#FFF1D6"],
  churned: ["Churn", "#FF3B30", "#FFE5E2"], prospek: ["Prospek", "#6B6B73", "#F2F2F5"] };

export default function CrmRfm() {
  const [data, setData] = useState(null);
  const [lifecycle, setLifecycle] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    const q = lifecycle === "all" ? "" : `?lifecycle=${lifecycle}`;
    apiClient.get(`/crm/rfm${q}`).then((r) => { setData(r.data); setError(null); })
      .catch(() => setError("Gagal memuat RFM")).finally(() => setLoading(false));
  }, [lifecycle]);
  useEffect(() => { load(); }, [load]);

  if (loading) return <LoadingState testId="rfm-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  const rows = data?.customers || []; const segs = data?.segments || {}; const lcs = data?.lifecycles || {};
  return (
    <div className="space-y-3" data-testid="crm-rfm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          {Object.entries(segs).map(([k, v]) => (
            <span key={k} className="flex items-center gap-1 rounded-full bg-[#F7F7F9] px-2.5 py-1 text-[11.5px] font-semibold" style={{ color: SEG_COLOR[k] || "#3C3C43" }}>{k}: <b className="tabular-nums">{v}</b></span>
          ))}
        </div>
        <Select value={lifecycle} onValueChange={setLifecycle}>
          <SelectTrigger className="w-[160px]" data-testid="rfm-lifecycle"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Semua lifecycle</SelectItem>
            <SelectItem value="aktif">Aktif ({lcs.aktif || 0})</SelectItem>
            <SelectItem value="at_risk">Berisiko ({lcs.at_risk || 0})</SelectItem>
            <SelectItem value="churned">Churn ({lcs.churned || 0})</SelectItem>
            <SelectItem value="prospek">Prospek ({lcs.prospek || 0})</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {rows.length === 0 ? <EmptyState title="Belum ada data pelanggan" description="RFM/LTV dihitung dari riwayat booking & pembayaran." testId="rfm-empty" /> : (
        <section className="section-card">
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead><tr className="border-b border-[#EFF0F2] text-left text-[11px] uppercase tracking-wide text-[#8E8E93]">
                <th className="px-4 py-2.5">Pelanggan</th><th className="px-3 py-2.5">Segmen RFM</th><th className="px-3 py-2.5">Lifecycle</th>
                <th className="px-3 py-2.5 text-center">R/F/M</th><th className="px-3 py-2.5 text-right">Recency</th><th className="px-3 py-2.5 text-right">Transaksi</th><th className="px-3 py-2.5 text-right">LTV</th></tr></thead>
              <tbody data-testid="rfm-list">
                {rows.map((c) => { const lc = LC[c.lifecycle] || LC.prospek;
                  return (
                    <tr key={c.id} className="border-b border-[#F6F6F8] hover:bg-[#FAFAFB]" data-testid={`rfm-row-${c.id}`}>
                      <td className="px-4 py-2.5"><div className="font-semibold text-[#1C1C1E]">{c.name}</div><div className="text-[11px] text-[#8E8E93]">{c.phone || "-"}</div></td>
                      <td className="px-3 py-2.5 font-semibold" style={{ color: SEG_COLOR[c.rfm_segment] || "#3C3C43" }}>{c.rfm_segment}</td>
                      <td className="px-3 py-2.5"><span className="rounded-full px-2 py-0.5 text-[11px] font-semibold" style={{ color: lc[1], background: lc[2] }}>{lc[0]}</span></td>
                      <td className="px-3 py-2.5 text-center tabular-nums text-[#3C3C43]">{c.r}/{c.f}/{c.m}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{c.recency_days}h</td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{c.frequency}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums font-semibold">{formatCurrency(c.ltv || 0)}</td>
                    </tr>
                  ); })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

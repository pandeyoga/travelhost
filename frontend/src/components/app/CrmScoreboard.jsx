import { useCallback, useEffect, useState } from "react";
import { Flame, RefreshCw, Clock, AlertTriangle, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCurrency } from "@/utils/formatters";

const BAND = { hot: ["Hot", "#FF3B30", "#FFE5E2"], warm: ["Warm", "#C25400", "#FFF1D6"], cold: ["Cold", "#6B6B73", "#F2F2F5"] };
const SLA = { breached: ["SLA Terlewati", "#FF3B30", "#FFE5E2"], at_risk: ["Berisiko", "#C25400", "#FFF1D6"],
  on_track: ["Aman", "#126E2C", "#E3F7E8"], responded: ["Direspon", "#0058CC", "#E5F0FF"] };

function Chip({ label, value, color, bg }) {
  return <span className="flex items-center gap-1 rounded-full px-2.5 py-1 text-[11.5px] font-semibold" style={{ color, background: bg }}>{label}: <b className="tabular-nums">{value}</b></span>;
}

export default function CrmScoreboard({ onOpen }) {
  const [data, setData] = useState(null);
  const [aging, setAging] = useState(null);
  const [band, setBand] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    const q = band === "all" ? "" : `?band=${band}`;
    Promise.all([apiClient.get(`/crm/scoreboard${q}`), apiClient.get("/crm/aging")])
      .then(([s, a]) => { setData(s.data); setAging(a.data); setError(null); })
      .catch(() => setError("Gagal memuat scoreboard"))
      .finally(() => setLoading(false));
  }, [band]);
  useEffect(() => { load(); }, [load]);

  const recompute = async () => {
    setBusy(true);
    try { const r = await apiClient.post("/crm/recompute"); toast.success(`Skor ${r.data.leads_scored} lead & RFM ${r.data.customers_rfm} pelanggan diperbarui`); load(); }
    catch (e) { toast.error("Gagal menghitung ulang"); } finally { setBusy(false); }
  };

  if (loading) return <LoadingState testId="scoreboard-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  const leads = data?.leads || [];
  const bands = data?.bands || {}; const ac = aging?.counts || {};
  return (
    <div className="space-y-3" data-testid="crm-scoreboard">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Chip label="Hot" value={bands.hot || 0} color="#FF3B30" bg="#FFE5E2" />
          <Chip label="Warm" value={bands.warm || 0} color="#C25400" bg="#FFF1D6" />
          <Chip label="Cold" value={bands.cold || 0} color="#6B6B73" bg="#F2F2F5" />
          <span className="mx-1 h-4 w-px bg-[#E5E5EA]" />
          <Chip label="SLA Telat" value={ac.breached || 0} color="#FF3B30" bg="#FFE5E2" />
          <Chip label="Berisiko" value={ac.at_risk || 0} color="#C25400" bg="#FFF1D6" />
          <Chip label="Direspon" value={ac.responded || 0} color="#0058CC" bg="#E5F0FF" />
        </div>
        <div className="flex items-center gap-2">
          <Select value={band} onValueChange={setBand}>
            <SelectTrigger className="w-[130px]" data-testid="scoreboard-band"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">Semua band</SelectItem><SelectItem value="hot">Hot</SelectItem><SelectItem value="warm">Warm</SelectItem><SelectItem value="cold">Cold</SelectItem></SelectContent>
          </Select>
          <button className="secondary-button" onClick={recompute} disabled={busy} data-testid="scoreboard-recompute"><RefreshCw size={14} className={busy ? "animate-spin" : ""} /> Hitung Ulang</button>
        </div>
      </div>
      {leads.length === 0 ? <EmptyState title="Belum ada lead" description="Lead terbuka akan diberi skor & SLA otomatis." testId="scoreboard-empty" /> : (
        <section className="section-card">
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead><tr className="border-b border-[#EFF0F2] text-left text-[11px] uppercase tracking-wide text-[#8E8E93]">
                <th className="px-4 py-2.5">Lead</th><th className="px-3 py-2.5">Skor</th><th className="px-3 py-2.5">Sumber</th>
                <th className="px-3 py-2.5 text-right">Nilai</th><th className="px-3 py-2.5">Agen</th><th className="px-3 py-2.5">SLA</th></tr></thead>
              <tbody data-testid="scoreboard-list">
                {leads.map((l) => { const b = BAND[l.score_band] || BAND.cold; const s = SLA[l.first_response_at ? "responded" : (l.sla_status || "on_track")] || SLA.on_track;
                  return (
                    <tr key={l.id} className="cursor-pointer border-b border-[#F6F6F8] hover:bg-[#FAFAFB]" onClick={() => onOpen && onOpen(l.id)} data-testid={`scoreboard-row-${l.id}`}>
                      <td className="px-4 py-2.5"><div className="font-semibold text-[#1C1C1E]">{l.customer_name}</div><div className="text-[11px] text-[#8E8E93]">{l.destination || "-"}</div></td>
                      <td className="px-3 py-2.5"><div className="flex items-center gap-2"><div className="h-1.5 w-16 overflow-hidden rounded-full bg-[#EFEFF2]"><div className="h-full rounded-full" style={{ width: `${l.score || 0}%`, background: b[1] }} /></div><span className="tabular-nums font-bold" style={{ color: b[1] }}>{l.score || 0}</span></div></td>
                      <td className="px-3 py-2.5 capitalize text-[#3C3C43]">{l.source || "-"}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{formatCurrency(l.value || 0)}</td>
                      <td className="px-3 py-2.5 text-[#3C3C43]">{l.assignee_name || "—"}</td>
                      <td className="px-3 py-2.5"><span className="rounded-full px-2 py-0.5 text-[11px] font-semibold" style={{ color: s[1], background: s[2] }}>{s[0]}</span></td>
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

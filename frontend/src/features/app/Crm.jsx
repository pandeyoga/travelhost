import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Plus, LayoutGrid, AlarmClock, Megaphone, TrendingUp, Users2, Banknote, Target, Flame, Filter, Workflow, Radio } from "lucide-react";
import apiClient from "@/services/apiClient";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { formatCurrency, formatQty } from "@/utils/formatters";
import CrmKanban from "@/components/app/CrmKanban";
import LeadDetailDrawer from "@/components/app/LeadDetailDrawer";
import CrmReminders from "@/components/app/CrmReminders";
import CrmScoreboard from "@/components/app/CrmScoreboard";
import CrmRfm from "@/components/app/CrmRfm";
import CrmSegments from "@/components/app/CrmSegments";
import CrmSequences from "@/components/app/CrmSequences";
import CrmCampaigns from "@/components/app/CrmCampaigns";
import CrmBroadcast from "@/components/app/CrmBroadcast";
import LeadFormDialog from "@/components/app/LeadFormDialog";

const TABS = [
  ["pipeline", "Pipeline", LayoutGrid],
  ["scoreboard", "Skor & SLA", Flame],
  ["rfm", "RFM/LTV", TrendingUp],
  ["segments", "Segmen", Filter],
  ["sequences", "Sequence", Workflow],
  ["campaigns", "Campaign", Megaphone],
  ["broadcast", "Broadcast", Radio],
  ["reminder", "Reminder", AlarmClock],
];

function Kpi({ icon: Icon, label, value, tone }) {
  return (
    <div className="kpi-card">
      <div className="kpi-top"><span className="kpi-icon" style={{ background: tone.bg, color: tone.fg }}><Icon size={15} /></span><span className="kpi-label">{label}</span></div>
      <span className="kpi-value tabular-nums">{value}</span>
    </div>
  );
}

export default function Crm() {
  // Tab hidup di URL (?tab=) supaya heading Topbar ikut tab aktif dan tab bisa di-deep-link.
  const [searchParams, setSearchParams] = useSearchParams();
  const validTabs = TABS.map(([k]) => k);
  const raw = searchParams.get("tab") || "pipeline";
  const tab = validTabs.includes(raw) ? raw : "pipeline";
  const setTab = (k) => setSearchParams(k === "pipeline" ? {} : { tab: k }, { replace: true });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [agents, setAgents] = useState([]);
  const [drawerId, setDrawerId] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [remCount, setRemCount] = useState(0);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/leads/pipeline")
      .then((r) => { setData(r.data); setError(null); })
      .catch(() => setError("Gagal memuat pipeline CRM"))
      .finally(() => setLoading(false));
  }, []);

  const loadReminders = useCallback(() => {
    apiClient.get("/leads/reminders").then((r) => setRemCount((r.data || []).length)).catch(() => {});
  }, []);

  useEffect(() => {
    load();
    loadReminders();
    apiClient.get("/leads/agents").then((r) => setAgents(r.data || [])).catch(() => {});
  }, [load, loadReminders]);

  const openLead = (id) => { setDrawerId(id); setDrawerOpen(true); };
  const move = async (id, stage) => { try { await apiClient.post(`/leads/${id}/stage`, { stage }); load(); } catch (e) { /* state revert on reload */ } };
  const refresh = () => { load(); loadReminders(); };

  const s = data?.summary || {};
  return (
    <div data-testid="crm-page">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="grid flex-1 grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi icon={Users2} label="Total Lead" value={formatQty(s.total || 0)} tone={{ bg: "rgba(0,122,255,0.12)", fg: "#0058CC" }} />
          <Kpi icon={Target} label="Lead Aktif" value={formatQty(s.open || 0)} tone={{ bg: "rgba(255,149,0,0.14)", fg: "#8C4A00" }} />
          <Kpi icon={TrendingUp} label="Konversi" value={`${s.conversion || 0}%`} tone={{ bg: "rgba(52,199,89,0.15)", fg: "#126E2C" }} />
          <Kpi icon={Banknote} label="Nilai Pipeline" value={formatCurrency(s.pipeline_value || 0)} tone={{ bg: "rgba(175,82,222,0.13)", fg: "#6B219A" }} />
        </div>
        <button className="primary-button" onClick={() => setFormOpen(true)} data-testid="crm-add-lead"><Plus size={15} /> Tambah Lead</button>
      </div>

      <div className="tab-bar mb-4">
        {TABS.map(([k, l, Icon]) => (
          <button key={k} className={`tab-button ${tab === k ? "active" : ""}`} onClick={() => setTab(k)} data-testid={`tab-crm-${k}`}>
            <Icon size={14} /> {l}
            {k === "reminder" && remCount > 0 ? <span className="ml-1 rounded-full bg-[#FF3B30] px-1.5 text-[10px] font-bold text-white">{remCount}</span> : null}
          </button>
        ))}
      </div>

      {tab === "pipeline" && (
        loading ? <LoadingState testId="crm-loading" /> :
        error ? <ErrorState message={error} onRetry={load} /> :
        (s.total === 0) ? <EmptyState title="Belum ada lead" description="Lead dari website & input manual akan tampil di pipeline." testId="crm-empty" /> :
        <CrmKanban stages={data.stages} loading={false} onOpen={openLead} onMove={move} />
      )}
      {tab === "scoreboard" && <CrmScoreboard onOpen={openLead} />}
      {tab === "rfm" && <CrmRfm />}
      {tab === "segments" && <CrmSegments />}
      {tab === "sequences" && <CrmSequences />}
      {tab === "campaigns" && <CrmCampaigns />}
      {tab === "broadcast" && <CrmBroadcast />}
      {tab === "reminder" && <CrmReminders onOpen={openLead} />}

      <LeadDetailDrawer leadId={drawerId} open={drawerOpen} onOpenChange={setDrawerOpen} agents={agents} onChanged={refresh} />
      <LeadFormDialog open={formOpen} onOpenChange={setFormOpen} agents={agents} onSaved={refresh} />
    </div>
  );
}

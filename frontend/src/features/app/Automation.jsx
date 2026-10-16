import { useCallback, useEffect, useState } from "react";
import {
  Zap, Activity, Send, Wallet, Radio, ListChecks, CheckCircle2, XCircle, MinusCircle,
  RefreshCw, Power,
} from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCurrency, formatDateTime } from "@/utils/formatters";

const TABS = [
  ["rules", "Aturan", ListChecks],
  ["runs", "Riwayat Eksekusi", Activity],
  ["events", "Event Stream", Radio],
];
const RUN_TONE = { success: "success", failed: "danger", skipped: "neutral" };
const RUN_LABEL = { success: "Sukses", failed: "Gagal", skipped: "Dilewati" };
const ACT_ICON = { success: CheckCircle2, failed: XCircle, skipped: MinusCircle };
const ACT_COLOR = { success: "#34C759", failed: "#FF3B30", skipped: "#8E8E93" };

function Kpi({ icon: Icon, label, value, color, money }) {
  return (
    <div className="kpi-card" data-testid={`auto-kpi-${label}`}>
      <div className="kpi-top">
        <span className="kpi-icon" style={{ background: `${color}18` }}><Icon size={16} style={{ color }} /></span>
        <span className="kpi-label">{label}</span>
      </div>
      <p className="kpi-value tabular-nums">{money ? formatCurrency(value || 0) : (value ?? 0)}</p>
    </div>
  );
}

export default function Automation() {
  const [tab, setTab] = useState("rules");
  const [stats, setStats] = useState(null);
  const [catalog, setCatalog] = useState({ events: [], actions: [] });

  const loadStats = useCallback(() => {
    apiClient.get("/automation/stats").then((r) => setStats(r.data)).catch(() => setStats(null));
  }, []);
  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => {
    apiClient.get("/automation/event-types").then((r) => setCatalog(r.data || { events: [], actions: [] })).catch(() => {});
  }, []);

  const eventLabel = (k) => (catalog.events.find((e) => e.key === k) || {}).label || k;
  const s = stats || {};

  return (
    <div className="space-y-4" data-testid="automation-page">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Kpi icon={Power} label="Aturan Aktif" value={s.rules_active} color="#0058CC" />
        <Kpi icon={Activity} label="Eksekusi Hari Ini" value={s.runs_today} color="#34C759" />
        <Kpi icon={ListChecks} label="Total Eksekusi" value={s.runs_total} color="#AF52DE" />
        <Kpi icon={Send} label="WA Terkirim" value={s.wa_sent} color="#25D366" />
        <Kpi icon={Radio} label="WA Masuk" value={s.wa_inbound} color="#FF9500" />
        <Kpi icon={Wallet} label="Estimasi Biaya WA" value={s.wa_cost} color="#FF3B30" money />
      </div>

      <div className="tab-bar">
        {TABS.map(([k, l, Icon]) => (
          <button key={k} className={`tab-button ${tab === k ? "active" : ""}`} onClick={() => setTab(k)} data-testid={`tab-auto-${k}`}>
            <Icon size={14} /> {l}
          </button>
        ))}
      </div>

      {tab === "rules" && <RulesTab onChanged={loadStats} eventLabel={eventLabel} />}
      {tab === "runs" && <RunsTab eventLabel={eventLabel} />}
      {tab === "events" && <EventsTab catalog={catalog} eventLabel={eventLabel} />}
    </div>
  );
}

function RulesTab({ onChanged, eventLabel }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/automation/rules")
      .then((r) => { setRows(Array.isArray(r.data) ? r.data : []); setError(null); })
      .catch(() => setError("Gagal memuat aturan otomasi"))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const toggle = async (rule, enabled) => {
    try {
      await apiClient.patch(`/automation/rules/${rule.id}`, { enabled });
      toast.success(enabled ? `Aturan "${rule.name}" diaktifkan` : `Aturan "${rule.name}" dinonaktifkan`);
      load(); onChanged && onChanged();
    } catch (e) { toast.error("Gagal mengubah status aturan"); }
  };

  if (loading) return <LoadingState testId="rules-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (rows.length === 0) {
    return <EmptyState title="Belum ada aturan otomasi"
      description="Buat & konfigurasikan aturan di menu Pengaturan › Otomasi & WhatsApp." testId="rules-empty" />;
  }

  return (
    <section className="section-card" data-testid="rules-panel">
      <div className="section-head"><div className="flex items-center gap-2"><Zap size={16} className="text-[#0058CC]" /><h2>Aturan Otomasi</h2></div>
        <span className="text-[11.5px] text-[#8E8E93]">Konfigurasi penuh di Pengaturan</span></div>
      <div className="divide-y divide-[#F2F2F5]" data-testid="rules-list">
        {rows.map((r) => (
          <div key={r.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3" data-testid={`rule-${r.id}`}>
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-2 text-[13px] font-bold text-[#1C1C1E]">
                {r.name}
                <span className={`status-pill tone-${r.enabled ? "success" : "neutral"}`}>{r.enabled ? "Aktif" : "Nonaktif"}</span>
              </p>
              <p className="truncate text-[11.5px] text-[#6B6B73]">
                Pemicu: <b>{eventLabel(r.event_type)}</b> · {(r.actions || []).length} aksi · {r.run_count || 0}× dijalankan
                {r.last_run_at ? ` · terakhir ${formatDateTime(r.last_run_at)}` : ""}
              </p>
            </div>
            <Switch checked={!!r.enabled} onCheckedChange={(v) => toggle(r, v)} data-testid={`rule-toggle-${r.id}`} />
          </div>
        ))}
      </div>
    </section>
  );
}

function RunsTab({ eventLabel }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState("all");

  const load = useCallback(() => {
    setLoading(true);
    const q = status === "all" ? "" : `?status=${status}`;
    apiClient.get(`/automation/runs${q}`)
      .then((r) => { setRows(Array.isArray(r.data) ? r.data : []); setError(null); })
      .catch(() => setError("Gagal memuat riwayat eksekusi"))
      .finally(() => setLoading(false));
  }, [status]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-3" data-testid="runs-panel">
      <div className="flex items-center justify-between gap-2">
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-[160px]" data-testid="runs-filter"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Semua status</SelectItem>
            <SelectItem value="success">Sukses</SelectItem>
            <SelectItem value="failed">Gagal</SelectItem>
            <SelectItem value="skipped">Dilewati</SelectItem>
          </SelectContent>
        </Select>
        <button className="secondary-button" onClick={load} data-testid="runs-refresh"><RefreshCw size={14} /> Muat ulang</button>
      </div>
      {loading ? <LoadingState testId="runs-loading" />
        : error ? <ErrorState message={error} onRetry={load} />
        : rows.length === 0 ? <EmptyState title="Belum ada eksekusi" description="Eksekusi otomasi akan muncul saat ada event yang cocok dengan aturan aktif." testId="runs-empty" />
        : (
          <section className="section-card">
            <div className="divide-y divide-[#F2F2F5]" data-testid="runs-list">
              {rows.map((r) => (
                <div key={r.id} className="px-4 py-3" data-testid={`run-${r.id}`}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="flex items-center gap-2 text-[13px] font-bold text-[#1C1C1E]">
                      {r.rule_name}
                      <span className={`status-pill tone-${RUN_TONE[r.status] || "neutral"}`}>{RUN_LABEL[r.status] || r.status}</span>
                    </p>
                    <span className="text-[11px] text-[#8E8E93] tabular-nums">{formatDateTime(r.created_at)}</span>
                  </div>
                  <p className="mt-0.5 text-[11.5px] text-[#6B6B73]">Pemicu: {eventLabel(r.event_type)}</p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {(r.actions || []).length === 0 ? <span className="text-[11px] text-[#A0A0A8]">{r.message}</span>
                      : (r.actions || []).map((a, i) => {
                        const AI = ACT_ICON[a.status] || MinusCircle;
                        return (
                          <span key={i} className="flex items-center gap-1 rounded-full bg-[#F7F7F9] px-2 py-0.5 text-[11px] text-[#3C3C43]" title={a.detail || ""}>
                            <AI size={12} style={{ color: ACT_COLOR[a.status] || "#8E8E93" }} /> {a.type}
                          </span>
                        );
                      })}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
    </div>
  );
}

function EventsTab({ catalog, eventLabel }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [type, setType] = useState("all");

  const load = useCallback(() => {
    setLoading(true);
    const q = type === "all" ? "" : `?event_type=${type}`;
    apiClient.get(`/automation/events${q}`)
      .then((r) => { setRows(Array.isArray(r.data) ? r.data : []); setError(null); })
      .catch(() => setError("Gagal memuat event"))
      .finally(() => setLoading(false));
  }, [type]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-3" data-testid="events-panel">
      <div className="flex items-center justify-between gap-2">
        <Select value={type} onValueChange={setType}>
          <SelectTrigger className="w-[220px]" data-testid="events-filter"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Semua jenis event</SelectItem>
            {catalog.events.map((e) => <SelectItem key={e.key} value={e.key}>{e.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <button className="secondary-button" onClick={load} data-testid="events-refresh"><RefreshCw size={14} /> Muat ulang</button>
      </div>
      {loading ? <LoadingState testId="events-loading" />
        : error ? <ErrorState message={error} onRetry={load} />
        : rows.length === 0 ? <EmptyState title="Belum ada event" description="Event domain (lead masuk, booking, pembayaran, dll) akan muncul di sini." testId="events-empty" />
        : (
          <section className="section-card">
            <div className="divide-y divide-[#F2F2F5]" data-testid="events-list">
              {rows.map((e) => (
                <div key={e.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3" data-testid={`event-${e.id}`}>
                  <div className="min-w-0">
                    <p className="flex items-center gap-2 text-[13px] font-semibold text-[#1C1C1E]">
                      <Radio size={13} className="text-[#0058CC]" /> {eventLabel(e.type)}
                      <span className="rounded-full bg-[#F2F2F5] px-2 py-0.5 text-[10.5px] text-[#6B6B73]">{e.source}</span>
                    </p>
                    <p className="truncate text-[11px] text-[#8E8E93]">{e.type}{e.ref_id ? ` · ${e.ref_id}` : ""}</p>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-2 text-[11px]">
                    <span className={`status-pill tone-${e.runs_created > 0 ? "success" : "neutral"}`}>{e.runs_created || 0} aksi</span>
                    <span className="text-[#8E8E93] tabular-nums">{formatDateTime(e.created_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
    </div>
  );
}

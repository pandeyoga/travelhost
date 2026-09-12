import { useCallback, useEffect, useState } from "react";
import { Megaphone, RefreshCw, BarChart3, Users2, Wrench, Inbox, Wallet } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { LoadingState, ErrorState } from "@/components/shared/DataStates";
import SelectField from "@/components/shared/SelectField";
import { formatQty } from "@/utils/formatters";
import AdsSummary from "@/components/app/ads/AdsSummary";
import AdsPerformance from "@/components/app/ads/AdsPerformance";
import AdsManualSpend from "@/components/app/ads/AdsManualSpend";
import AdsPlatformLeads from "@/components/app/ads/AdsPlatformLeads";
import AdsAudiences from "@/components/app/ads/AdsAudiences";
import AdsBuilder from "@/components/app/ads/AdsBuilder";

/**
 * Ads.jsx — "Dashboard Iklan" (owner, marketing_admin, ops_admin read-only).
 *
 * Pertanyaan yang dijawab halaman ini: *iklan mana yang benar-benar menghasilkan booking?*
 * Karena itu biaya dari platform (Meta Ads / Google Ads) disandingkan dengan booking &
 * pembayaran NYATA dari ERP pada level yang sama (kampanye → adset → iklan).
 *
 * Selama kredensial belum diisi, halaman tetap berguna: biaya bisa diisi manual per channel,
 * dan setiap blok menjelaskan APA yang belum lengkap (bukan sekadar kosong).
 */
const TABS = [
  ["ringkasan", "Ringkasan & ROAS", BarChart3],
  ["kampanye", "Per Kampanye", Megaphone],
  ["leads", "Lead Iklan", Inbox],
  ["audiens", "Audiens & Retargeting", Users2],
  ["builder", "Buat Kampanye", Wrench],
];
const RANGES = [
  { value: "7", label: "7 hari terakhir" },
  { value: "30", label: "30 hari terakhir" },
  { value: "90", label: "90 hari terakhir" },
];
const LEVELS = [
  { value: "campaign", label: "Level: Kampanye" },
  { value: "adset", label: "Level: Adset / Ad Group" },
  { value: "ad", label: "Level: Iklan" },
];
const PROVIDERS = [
  { value: "", label: "Semua platform" },
  { value: "meta", label: "Meta Ads" },
  { value: "google", label: "Google Ads" },
];

export function moneyText(value, currency) {
  const num = Number(value || 0);
  const label = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 }).format(Math.round(num));
  if (!currency || currency === "IDR") return `Rp ${label}`;
  return `${currency} ${label}`;
}

function Kpi({ icon: Icon, label, value, hint, tone, testId }) {
  return (
    <div className="kpi-card" data-testid={testId}>
      <div className="kpi-top">
        <span className="kpi-icon" style={{ background: tone.bg, color: tone.fg }}><Icon size={15} /></span>
        <span className="kpi-label">{label}</span>
      </div>
      <span className="kpi-value tabular-nums">{value}</span>
      {hint ? <span className="mt-0.5 block text-[11px] text-[#8E8E93]">{hint}</span> : null}
    </div>
  );
}

export default function Ads() {
  const [tab, setTab] = useState("ringkasan");
  const [days, setDays] = useState("30");
  const [level, setLevel] = useState("campaign");
  const [provider, setProvider] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [firstLoad, setFirstLoad] = useState(true);
  const [error, setError] = useState(null);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    const q = `?days=${days}&level=${level}${provider ? `&provider=${provider}` : ""}`;
    apiClient.get(`/ads/overview${q}`)
      .then((r) => { setData(r.data); setError(null); })
      .catch((e) => setError(e?.response?.data?.detail || "Gagal memuat dashboard iklan"))
      .finally(() => { setLoading(false); setFirstLoad(false); });
  }, [days, level, provider]);
  useEffect(load, [load]);

  const sync = async () => {
    setSyncing(true);
    try {
      const { data: res } = await apiClient.post("/ads/sync", { days: Number(days) });
      const lines = Object.values(res.reports || {}).map((r) => (
        r.status === "ok" ? `${r.provider}: ${r.rows} baris (${r.currency || "-"})`
          : `${r.provider}: ${r.reason || r.status}`));
      if (res.rows > 0) toast.success(`Tarik selesai — ${lines.join(" · ")}`);
      else toast.warning(lines.join(" · ") || "Tidak ada data ditarik");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menarik metrik iklan");
    } finally { setSyncing(false); }
  };

  // Pemuatan PERTAMA menampilkan skeleton penuh; pergantian filter hanya memuat area isi
  // supaya header + KPI tidak berkedip hilang (UX lebih tenang saat mengganti rentang tanggal).
  if (loading && firstLoad) return <LoadingState testId="ads-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const totals = data?.performance?.totals || {};
  const currency = (data?.performance?.currencies || [])[0] || "IDR";
  const canManage = Boolean(data?.can_manage);

  return (
    <div className="space-y-4" data-testid="ads-page">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <div className="w-[168px]"><SelectField value={days} onChange={setDays} options={RANGES} testId="ads-range" className="w-full" /></div>
          <div className="w-[190px]"><SelectField value={level} onChange={setLevel} options={LEVELS} testId="ads-level" className="w-full" /></div>
          <div className="w-[160px]"><SelectField value={provider} onChange={setProvider} options={PROVIDERS} testId="ads-provider" className="w-full" /></div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="secondary-button" onClick={load} data-testid="ads-refresh"><RefreshCw size={14} /> Muat ulang</button>
          {canManage ? (
            <button className="primary-button" onClick={sync} disabled={syncing} data-testid="ads-sync">
              <RefreshCw size={14} /> {syncing ? "Menarik…" : "Tarik Sekarang"}
            </button>
          ) : null}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Kpi icon={Wallet} label="Biaya Iklan" testId="ads-kpi-spend" value={moneyText(totals.spend, currency)}
          hint={`${formatQty(totals.clicks || 0)} klik`} tone={{ bg: "rgba(255,59,48,0.12)", fg: "#A8221A" }} />
        <Kpi icon={Inbox} label="Lead" testId="ads-kpi-leads" value={formatQty(totals.leads || 0)}
          hint={totals.cpl != null ? `CPL ${moneyText(totals.cpl, currency)}` : "CPL menunggu data biaya"}
          tone={{ bg: "rgba(0,122,255,0.12)", fg: "#0058CC" }} />
        <Kpi icon={Megaphone} label="Booking" testId="ads-kpi-bookings" value={formatQty(totals.bookings || 0)}
          hint={totals.cac != null ? `CAC ${moneyText(totals.cac, currency)}` : "CAC menunggu data biaya"}
          tone={{ bg: "rgba(255,149,0,0.14)", fg: "#8C4A00" }} />
        <Kpi icon={Wallet} label="Pendapatan Nyata" testId="ads-kpi-revenue" value={moneyText(totals.revenue, "IDR")}
          hint="dari booking & DP di ERP" tone={{ bg: "rgba(52,199,89,0.15)", fg: "#126E2C" }} />
        <Kpi icon={BarChart3} label="ROAS" testId="ads-kpi-roas" value={totals.roas != null ? `${totals.roas}×` : "—"}
          hint={totals.roas == null ? "butuh biaya iklan" : "pendapatan ÷ biaya"}
          tone={{ bg: "rgba(175,82,222,0.13)", fg: "#6B219A" }} />
      </div>

      <div className="tab-bar">
        {TABS.map(([key, label, Icon]) => (
          <button key={key} className={`tab-button ${tab === key ? "active" : ""}`} onClick={() => setTab(key)}
            data-testid={`tab-ads-${key}`}><Icon size={14} /> {label}</button>
        ))}
      </div>

      {tab === "ringkasan" && (
        <div className="space-y-4">
          <AdsSummary data={data} currency={currency} loading={loading} />
          <AdsManualSpend spend={data?.manual_spend} canManage={canManage} onSaved={load} loading={loading} />
        </div>
      )}
      {tab === "kampanye" && (
        <AdsPerformance performance={data?.performance} currency={currency} canManage={canManage} onChanged={load} loading={loading} />
      )}
      {tab === "leads" && <AdsPlatformLeads canManage={canManage} />}
      {tab === "audiens" && <AdsAudiences canManage={canManage} />}
      {tab === "builder" && <AdsBuilder canManage={canManage} readiness={data?.readiness} />}
    </div>
  );
}

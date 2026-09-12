import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from "recharts";
import { AlertTriangle, CheckCircle2, Activity, Info } from "lucide-react";
import { EmptyState, LoadingState } from "@/components/shared/DataStates";
import { formatDateTime, formatQty } from "@/utils/formatters";
import { moneyText } from "@/features/app/Ads";

/**
 * AdsSummary — kesiapan integrasi + tren biaya/klik harian + jejak tarikan data.
 * Jujur soal status: bila platform belum aktif, blok ini menyebut kolom apa yang belum diisi.
 */
const PROVIDER_LABEL = { meta: "Meta Ads", google: "Google Ads" };

function ReadinessCard({ provider, status, account }) {
  const live = status?.mode === "live";
  return (
    <div className="rounded-xl border border-[#EFF0F2] bg-white p-3.5" data-testid={`ads-ready-${provider}`}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-[12.5px] font-bold text-[#1C1C1E]">{PROVIDER_LABEL[provider] || provider}</p>
        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-bold uppercase ${
          live ? "bg-[#E7F7EC] text-[#12703A]" : "bg-[#FFF3E0] text-[#8A5300]"}`}>
          {live ? <CheckCircle2 size={11} /> : <AlertTriangle size={11} />}
          {live ? "AKTIF" : "BELUM AKTIF · MOCK"}
        </span>
      </div>
      {account ? (
        <p className="mt-1.5 text-[11.5px] text-[#6B6B73]">
          {account.name || account.account_id} · mata uang <b>{account.currency || "-"}</b>
          {account.timezone ? ` · ${account.timezone}` : ""}
        </p>
      ) : (
        <p className="mt-1.5 text-[11.5px] text-[#8E8E93]">Akun iklan belum tersinkron.</p>
      )}
      {status?.missing_labels?.length ? (
        <p className="mt-1.5 text-[11.5px] text-[#8A5300]">Belum lengkap: {status.missing_labels.join(", ")}</p>
      ) : null}
    </div>
  );
}

export default function AdsSummary({ data, currency, loading }) {
  if (loading) return <LoadingState testId="ads-summary-loading" />;
  const series = data?.series || [];
  const runs = data?.runs || [];
  const accounts = data?.accounts || [];
  const accountOf = (provider) => accounts.find((a) => a.provider === provider);
  const chartData = series.map((s) => ({ ...s, label: String(s.date).slice(5) }));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <ReadinessCard provider="meta" status={data?.readiness?.meta} account={accountOf("meta")} />
        <ReadinessCard provider="google" status={data?.readiness?.google} account={accountOf("google")} />
      </div>

      <section className="section-card">
        <div className="section-head">
          <h2 className="flex items-center gap-2"><Activity size={15} /> Tren Biaya &amp; Klik Harian</h2>
          <p className="mt-0.5 text-[12px] font-normal text-[#6B6B73]">
            Angka diambil langsung dari platform (bukan perkiraan). Mata uang mengikuti akun iklan: <b>{currency}</b>.
          </p>
        </div>
        <div className="section-body">
          {!chartData.length ? (
            <EmptyState title="Belum ada data biaya dari platform" testId="ads-series-empty"
              description="Isi kredensial di Integrasi API lalu tekan Tarik Sekarang. Sementara itu Anda tetap bisa mengisi biaya iklan manual di bawah." />
          ) : (
            <div className="h-[280px] w-full" data-testid="ads-series-chart">
              <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 280 }}>
                <ComposedChart data={chartData} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F0F1F3" />
                  <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#8E8E93" }} />
                  <YAxis yAxisId="left" tick={{ fontSize: 11, fill: "#8E8E93" }} width={70} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fill: "#8E8E93" }} width={44} />
                  <Tooltip formatter={(value, name) => (name === "Biaya" ? moneyText(value, currency) : formatQty(value))} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar yAxisId="left" dataKey="spend" name="Biaya" fill="#007AFF" radius={[4, 4, 0, 0]} />
                  <Line yAxisId="right" type="monotone" dataKey="clicks" name="Klik" stroke="#FF9500" strokeWidth={2} dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </section>

      <section className="section-card">
        <div className="section-head">
          <h2 className="flex items-center gap-2"><Info size={15} /> Riwayat Tarikan Data</h2>
          <p className="mt-0.5 text-[12px] font-normal text-[#6B6B73]">
            Setiap percobaan tarik dicatat beserta alasan gagalnya — tidak ada kegagalan yang disembunyikan.
          </p>
        </div>
        <div className="section-body">
          {!runs.length ? (
            <EmptyState title="Belum pernah menarik data" testId="ads-runs-empty"
              description="Tekan Tarik Sekarang untuk mengambil biaya & klik dari platform." />
          ) : (
            <div className="divide-y divide-[#F0F1F3]" data-testid="ads-runs-list">
              {runs.map((r) => (
                <div key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                  <div className="min-w-0">
                    <p className="text-[12.5px] font-semibold text-[#1C1C1E]">
                      {PROVIDER_LABEL[r.provider] || r.provider} · {r.level} · {r.since} → {r.until}
                    </p>
                    <p className="text-[11.5px] text-[#8E8E93]">{formatDateTime(r.created_at)}</p>
                    {r.reason ? <p className="mt-0.5 text-[11.5px] text-[#8A5300]">{r.reason}</p> : null}
                  </div>
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums ${
                    r.status === "ok" ? "bg-[#E7F7EC] text-[#12703A]" : "bg-[#FFF3E0] text-[#8A5300]"}`}>
                    {r.status === "ok" ? `${formatQty(r.rows)} baris` : r.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

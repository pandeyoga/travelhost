import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Cell, LabelList,
} from "recharts";
import { Filter, Megaphone, TrendingUp } from "lucide-react";
import { formatCurrency, formatQty } from "@/utils/formatters";

const MONTHS_ID = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const FUNNEL_COLORS = ["#007AFF", "#5856D6", "#FF9500", "#34C759"];
const CH_LABEL = { website: "Website", whatsapp: "WhatsApp", manual: "Manual", meta_ads: "Meta Ads", google_ads: "Google Ads", instagram: "Instagram", tiktok: "TikTok", lainnya: "Lainnya" };

function monthShort(key) {
  const m = Number(String(key).slice(5, 7));
  return `${MONTHS_ID[m - 1] || key}`;
}
const chName = (c) => CH_LABEL[c] || c;

function Card({ icon: Icon, title, color, action, children, loading, testId }) {
  return (
    <section className="section-card" data-testid={testId}>
      <div className="section-head">
        <div className="flex items-center gap-2"><Icon size={16} style={{ color }} /><h2>{title}</h2></div>
        {action}
      </div>
      <div className="section-body">
        {loading ? <div className="h-56 w-full animate-pulse rounded-[12px] bg-[#F0F1F4]" data-testid="bi-card-loading" /> : children}
      </div>
    </section>
  );
}

export function FunnelCard({ funnel }) {
  const stages = funnel?.stages || [];
  const data = stages.map((s) => ({ name: s.label, value: s.count, rate: s.rate }));
  const has = data.some((d) => d.value > 0);
  return (
    <Card icon={Filter} title="Sales Funnel" color="#5856D6" testId="bi-funnel" loading={!funnel}
      action={<span className="text-[12px] text-[#6B6B73]">Konversi <b className="text-[#127A36]">{funnel?.overall_conversion ?? 0}%</b></span>}>
      {!has ? (
        <p className="py-10 text-center text-[13px] text-[#6B6B73]" data-testid="bi-funnel-empty">Belum ada lead pada rentang ini.</p>
      ) : (
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 300 }}>
            <BarChart layout="vertical" data={data} margin={{ top: 4, right: 40, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#EFF0F2" horizontal={false} />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} stroke="#8E8E93" />
              <YAxis type="category" dataKey="name" width={92} tick={{ fontSize: 11.5 }} stroke="#8E8E93" />
              <Tooltip cursor={{ fill: "#F5F6F8" }} formatter={(v, n, p) => [`${formatQty(v)} (${p.payload.rate}%)`, "Jumlah"]}
                contentStyle={{ borderRadius: 12, border: "1px solid #E5E5EA", fontSize: 12 }} />
              <Bar dataKey="value" radius={[0, 6, 6, 0]} maxBarSize={34}>
                {data.map((d, i) => <Cell key={i} fill={FUNNEL_COLORS[i % FUNNEL_COLORS.length]} />)}
                <LabelList dataKey="value" position="right" style={{ fontSize: 11, fill: "#6B6B73" }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

export function ChannelsCard({ channels, onEditSpend }) {
  const rows = channels?.channels || [];
  const totals = channels?.totals || {};
  const data = rows.map((c) => ({ name: c.label || chName(c.channel), Lead: c.leads, Menang: c.won }));
  const has = data.some((d) => d.Lead > 0 || d.Menang > 0);
  return (
    <Card icon={Megaphone} title="Channel Mix & ROAS" color="#AF52DE" testId="bi-channels" loading={!channels}
      action={<button className="secondary-button !h-8 !px-2.5" onClick={onEditSpend} data-testid="bi-adspend-btn"><Megaphone size={13} /> Atur Belanja Iklan</button>}>
      {!has ? (
        <p className="py-8 text-center text-[13px] text-[#6B6B73]" data-testid="bi-channels-empty">Belum ada lead per channel.</p>
      ) : (
        <>
          <div className="h-52 w-full">
            <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 300 }}>
              <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EFF0F2" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="#8E8E93" />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} stroke="#8E8E93" />
                <Tooltip cursor={{ fill: "#F5F6F8" }} contentStyle={{ borderRadius: 12, border: "1px solid #E5E5EA", fontSize: 12 }} />
                <Bar dataKey="Lead" fill="#007AFF" radius={[5, 5, 0, 0]} maxBarSize={30} />
                <Bar dataKey="Menang" fill="#34C759" radius={[5, 5, 0, 0]} maxBarSize={30} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead><tr className="border-b border-[#EFF0F2] text-left text-[10.5px] uppercase tracking-wide text-[#8E8E93]">
                <th className="px-2 py-2">Channel</th><th className="px-2 py-2 text-right">Lead</th><th className="px-2 py-2 text-right">Menang</th><th className="px-2 py-2 text-right">Spend</th>
                <th className="px-2 py-2 text-right">CPL</th><th className="px-2 py-2 text-right">CAC</th><th className="px-2 py-2 text-right">ROAS</th></tr></thead>
              <tbody data-testid="bi-channels-table">
                {rows.map((c) => (
                  <tr key={c.channel} className="border-b border-[#F6F6F8]" data-testid={`bi-channel-row-${c.channel}`}>
                    <td className="px-2 py-2 font-medium text-[#1C1C1E]">{c.label || chName(c.channel)}</td>
                    <td className="px-2 py-2 text-right tabular-nums">{formatQty(c.leads)}</td>
                    <td className="px-2 py-2 text-right tabular-nums text-[#127A36]">{formatQty(c.won)}</td>
                    <td className="px-2 py-2 text-right tabular-nums">{c.spend > 0 ? formatCurrency(c.spend) : "\u2014"}</td>
                    <td className="px-2 py-2 text-right tabular-nums">{c.cpl != null ? formatCurrency(c.cpl) : "\u2014"}</td>
                    <td className="px-2 py-2 text-right tabular-nums">{c.cac != null ? formatCurrency(c.cac) : "\u2014"}</td>
                    <td className="px-2 py-2 text-right tabular-nums font-semibold" style={{ color: c.roas == null ? "#8E8E93" : c.roas >= 1 ? "#127A36" : "#C0271E" }}>{c.roas != null ? `${c.roas}x` : "\u2014"}</td>
                  </tr>
                ))}
                <tr className="bg-[#FAFAFB] font-semibold">
                  <td className="px-2 py-2">Total</td>
                  <td className="px-2 py-2 text-right tabular-nums">{formatQty(totals.leads)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-[#127A36]">{formatQty(totals.won)}</td>
                  <td className="px-2 py-2 text-right tabular-nums">{formatCurrency(totals.spend)}</td>
                  <td className="px-2 py-2 text-right tabular-nums">{totals.cpl != null ? formatCurrency(totals.cpl) : "\u2014"}</td>
                  <td className="px-2 py-2 text-right tabular-nums">{totals.cac != null ? formatCurrency(totals.cac) : "\u2014"}</td>
                  <td className="px-2 py-2 text-right tabular-nums" style={{ color: totals.roas == null ? "#8E8E93" : totals.roas >= 1 ? "#127A36" : "#C0271E" }}>{totals.roas != null ? `${totals.roas}x` : "\u2014"}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}

export function ForecastCard({ forecast }) {
  const hist = forecast?.history || [];
  const fc = forecast?.forecast || [];
  const series = hist.map((h) => ({ month: monthShort(h.month), aktual: h.value, prediksi: null }));
  if (hist.length && fc.length) series[hist.length - 1].prediksi = hist[hist.length - 1].value;
  fc.forEach((f) => series.push({ month: monthShort(f.month), aktual: null, prediksi: f.value }));
  const has = series.some((s) => (s.aktual || 0) > 0 || (s.prediksi || 0) > 0);
  return (
    <Card icon={TrendingUp} title="Forecast Pendapatan (moving-average)" color="#007AFF" testId="bi-forecast" loading={!forecast}>
      {!has ? (
        <p className="py-10 text-center text-[13px] text-[#6B6B73]" data-testid="bi-forecast-empty">Belum cukup data untuk proyeksi.</p>
      ) : (
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 300 }}>
            <LineChart data={series} margin={{ top: 8, right: 12, left: -6, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#EFF0F2" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} stroke="#8E8E93" />
              <YAxis tick={{ fontSize: 11 }} stroke="#8E8E93" tickFormatter={(v) => `${Math.round(v / 1000000)}jt`} />
              <Tooltip formatter={(v) => formatCurrency(v)} contentStyle={{ borderRadius: 12, border: "1px solid #E5E5EA", fontSize: 12 }} />
              <Line type="monotone" dataKey="aktual" name="Aktual" stroke="#007AFF" strokeWidth={2.5} dot={{ r: 3 }} connectNulls />
              <Line type="monotone" dataKey="prediksi" name="Prediksi" stroke="#FF9500" strokeWidth={2.5} strokeDasharray="5 4" dot={{ r: 3 }} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

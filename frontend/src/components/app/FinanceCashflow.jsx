import { useCallback, useEffect, useState } from "react";
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from "recharts";
import { Waves } from "lucide-react";
import apiClient from "@/services/apiClient";
import { LoadingState, ErrorState } from "@/components/shared/DataStates";
import { formatCurrency } from "@/utils/formatters";

const MONTHS_ID = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const mlabel = (k) => { try { return `${MONTHS_ID[Number(String(k).slice(5, 7)) - 1]}`; } catch { return String(k); } };

// FinanceCashflow — E5: arus kas bulanan (masuk vs keluar incl. maintenance) + proyeksi MA + saldo.
export default function FinanceCashflow() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/finance/cashflow?months=6&horizon=3")
      .then((r) => { setData(r.data); setError(null); })
      .catch(() => setError("Gagal memuat arus kas"))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  if (loading) return <LoadingState rows={3} testId="cashflow-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const months = data?.months || [];
  const proj = data?.projection || [];
  const series = months.map((m) => ({ month: mlabel(m.month), Masuk: m.cash_in, Keluar: m.cash_out, Saldo: m.balance, Proyeksi: null }));
  if (months.length && proj.length) series[months.length - 1].Proyeksi = months[months.length - 1].balance;
  proj.forEach((p) => series.push({ month: `${mlabel(p.month)}*`, Masuk: null, Keluar: null, Saldo: null, Proyeksi: p.balance }));
  const hasData = months.some((m) => m.cash_in > 0 || m.cash_out > 0);

  return (
    <div className="space-y-3" data-testid="cashflow-panel">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Mini label="Kas Masuk (6 bln)" value={months.reduce((a, m) => a + m.cash_in, 0)} tone="#0058CC" testId="cf-in" />
        <Mini label="Kas Keluar (6 bln)" value={months.reduce((a, m) => a + m.cash_out, 0)} tone="#FF3B30" testId="cf-out" />
        <Mini label="Saldo Akhir" value={data?.ending_balance} tone={(data?.ending_balance || 0) >= 0 ? "#127A36" : "#C0271E"} testId="cf-balance" />
      </div>

      <section className="section-card">
        <div className="section-head"><div className="flex items-center gap-2"><Waves size={16} className="text-[#007AFF]" /><h2>Arus Kas &amp; Proyeksi</h2></div><span className="text-[11.5px] text-[#8E8E93]">* proyeksi moving-average</span></div>
        <div className="section-body">
          {!hasData ? (
            <p className="py-10 text-center text-[13px] text-[#6B6B73]" data-testid="cashflow-empty">Belum ada transaksi kas.</p>
          ) : (
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 300 }}>
                <ComposedChart data={series} margin={{ top: 8, right: 10, left: -4, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EFF0F2" vertical={false} />
                  <XAxis dataKey="month" tick={{ fontSize: 11 }} stroke="#8E8E93" />
                  <YAxis tick={{ fontSize: 11 }} stroke="#8E8E93" tickFormatter={(v) => `${Math.round(v / 1000000)}jt`} />
                  <Tooltip formatter={(v) => (v == null ? "-" : formatCurrency(v))} contentStyle={{ borderRadius: 12, border: "1px solid #E5E5EA", fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="Masuk" fill="#34C759" radius={[5, 5, 0, 0]} maxBarSize={26} />
                  <Bar dataKey="Keluar" fill="#FF3B30" radius={[5, 5, 0, 0]} maxBarSize={26} />
                  <Line type="monotone" dataKey="Saldo" stroke="#007AFF" strokeWidth={2.5} dot={{ r: 3 }} connectNulls />
                  <Line type="monotone" dataKey="Proyeksi" stroke="#FF9500" strokeWidth={2.5} strokeDasharray="5 4" dot={{ r: 3 }} connectNulls />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </section>

      <section className="section-card">
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px]">
            <thead><tr className="border-b border-[#EFF0F2] text-left text-[10.5px] uppercase tracking-wide text-[#8E8E93]">
              <th className="px-4 py-2.5">Bulan</th><th className="px-3 py-2.5 text-right">Kas Masuk</th>
              <th className="px-3 py-2.5 text-right">Kas Keluar</th><th className="px-3 py-2.5 text-right">Net</th>
              <th className="px-3 py-2.5 text-right">Saldo</th></tr></thead>
            <tbody data-testid="cashflow-table">
              {months.map((m) => (
                <tr key={m.month} className="border-b border-[#F6F6F8]" data-testid={`cf-row-${m.month}`}>
                  <td className="px-4 py-2.5 font-medium text-[#1C1C1E]">{mlabel(m.month)} {String(m.month).slice(0, 4)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-[#127A36]">{formatCurrency(m.cash_in)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-[#C0271E]">{formatCurrency(m.cash_out)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums font-semibold" style={{ color: m.net >= 0 ? "#127A36" : "#C0271E" }}>{formatCurrency(m.net)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums font-bold">{formatCurrency(m.balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Mini({ label, value, tone, testId }) {
  return (
    <div className="rounded-[12px] border border-[#EFF0F2] bg-white p-3 shadow-sm" data-testid={testId}>
      <p className="text-[11px] text-[#6B6B73]">{label}</p>
      <p className="mt-0.5 text-[18px] font-bold tabular-nums" style={{ color: tone, fontFamily: "Outfit, sans-serif" }}>{formatCurrency(value)}</p>
    </div>
  );
}

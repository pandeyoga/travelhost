import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Download, ExternalLink, Eye, RefreshCw, TrendingUp } from "lucide-react";
import apiClient from "@/services/apiClient";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCurrency, formatDateTime } from "@/utils/formatters";

/**
 * ContentAnalyticsPanel — CMS-08: konten mana yang MENGHASILKAN, bukan cuma yang dibaca.
 *
 * Angka di sini menjawab pertanyaan yang mengubah keputusan menulis:
 *  - `views`      — tampilan halaman konten (satu IP dihitung sekali per 30 menit; IP TIDAK disimpan).
 *  - `leads`      — permintaan penawaran yang jejak kontennya menunjuk halaman ini.
 *  - `bookings`   — pesanan dengan jejak konten yang sama.
 *  - `revenue`    — nilai pesanan itu (pesanan batal/hangus tidak dihitung).
 *  - `lead_rate`  — rasio tampilan→lead; artikel dengan banyak view tapi 0 lead = judul menarik,
 *                   isi/CTA belum bekerja.
 *
 * Semua dihitung saat diminta dari data nyata (tanpa tabel ringkasan kedua yang bisa desinkron).
 */
const KIND_TONE = { article: "tone-info", destination: "tone-purple", package: "tone-success" };

function Kpi({ label, value, hint, tone = "#0058CC", testId }) {
  return (
    <div className="rounded-[12px] border border-[#E5E5EA] bg-white p-3.5" data-testid={testId}>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-[#8E8E93]">{label}</p>
      <p className="mt-1 text-[19px] font-bold tabular-nums" style={{ color: tone }}>{value}</p>
      {hint ? <p className="mt-0.5 text-[11.5px] text-[#6B6B73]">{hint}</p> : null}
    </div>
  );
}

export default function ContentAnalyticsPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [kind, setKind] = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data: res } = await apiClient.get("/content/analytics/top?limit=100");
      setData(res);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat analitik konten");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const rows = useMemo(() => {
    const all = Array.isArray(data?.rows) ? data.rows : [];
    return kind === "all" ? all : all.filter((r) => r.kind === kind);
  }, [data, kind]);

  const exportCsv = () => {
    if (!rows.length) { toast.message("Belum ada data untuk diunduh"); return; }
    const head = ["jenis", "judul", "path", "tampilan", "lead", "rasio_lead_persen", "pesanan", "omzet", "tampilan_terakhir"];
    const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const body = rows.map((r) => [r.kind_label, r.title, r.path, r.views, r.leads, r.lead_rate, r.bookings, r.revenue, r.last_view_at].map(esc).join(","));
    const blob = new Blob(["\uFEFF" + [head.join(","), ...body].join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `analitik-konten-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  if (loading) return <LoadingState testId="content-analytics-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} testId="content-analytics-error" />;

  const o = data?.overview || {};
  const kinds = Array.isArray(data?.kinds) ? data.kinds : [];

  return (
    <div className="space-y-4" data-testid="content-analytics-panel">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Kpi label="Konten terlacak" value={o.tracked ?? 0} hint="punya tampilan / lead" testId="ca-kpi-tracked" />
        <Kpi label="Total tampilan" value={(o.views ?? 0).toLocaleString("id-ID")} hint="1 IP / 30 menit" testId="ca-kpi-views" />
        <Kpi label="Lead teratribusi" value={o.leads ?? 0} hint="dari halaman konten" tone="#8A5A00" testId="ca-kpi-leads" />
        <Kpi label="Pesanan" value={o.bookings ?? 0} hint="jejak konten sama" tone="#1B7F3B" testId="ca-kpi-bookings" />
        <Kpi label="Omzet teratribusi" value={formatCurrency(o.revenue ?? 0)} hint="tanpa pesanan batal" tone="#1B7F3B" testId="ca-kpi-revenue" />
      </div>

      <section className="section-card">
        <div className="section-head">
          <div className="flex min-w-0 items-center gap-2">
            <TrendingUp size={16} className="text-[#0058CC]" />
            <h2 className="truncate">Peringkat konten → lead → pesanan</h2>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Select value={kind} onValueChange={setKind}>
              <SelectTrigger className="h-9 w-[150px]" data-testid="ca-kind-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all" data-testid="ca-kind-opt-all">Semua jenis</SelectItem>
                {kinds.map((k) => (
                  <SelectItem key={k.value} value={k.value} data-testid={`ca-kind-opt-${k.value}`}>{k.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <button className="secondary-button" onClick={exportCsv} data-testid="ca-export"><Download size={14} /> CSV</button>
            <button className="secondary-button" onClick={load} data-testid="ca-refresh"><RefreshCw size={14} /> Muat ulang</button>
          </div>
        </div>
        <div className="section-body">
          {rows.length === 0 ? (
            <EmptyState title="Belum ada tampilan konten tercatat" testId="ca-empty"
              description="Angka mulai terisi begitu pengunjung membuka halaman artikel, destinasi, atau paket. Pastikan konten sudah tayang (bukan draft)." />
          ) : (
            <div className="kn-table-wrap" data-testid="ca-table">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="kn-th">Konten</th>
                    <th className="kn-th text-right">Tampilan</th>
                    <th className="kn-th text-right">Lead</th>
                    <th className="kn-th text-right">Rasio lead</th>
                    <th className="kn-th text-right">Pesanan</th>
                    <th className="kn-th text-right">Omzet</th>
                    <th className="kn-th">Terakhir dibuka</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={`${r.kind}:${r.slug}`} className="kn-row" data-testid={`ca-row-${r.kind}-${r.slug}`}>
                      <td className="kn-td">
                        <span className="flex flex-wrap items-center gap-1.5">
                          <span className={`status-pill ${KIND_TONE[r.kind] || "tone-neutral"}`}>{r.kind_label}</span>
                          <span className="font-semibold text-[#1C1C1E]">{r.title || r.slug}</span>
                        </span>
                        <a href={r.path} target="_blank" rel="noreferrer"
                          className="mt-0.5 inline-flex items-center gap-1 text-[11px] text-[#0058CC] hover:underline"
                          data-testid={`ca-open-${r.slug}`}>
                          {r.path} <ExternalLink size={10} />
                        </a>
                      </td>
                      <td className="kn-td text-right tabular-nums">
                        <span className="inline-flex items-center gap-1"><Eye size={11} className="text-[#8E8E93]" />{r.views}</span>
                      </td>
                      <td className="kn-td text-right tabular-nums">{r.leads}</td>
                      <td className="kn-td text-right tabular-nums">{r.views ? `${r.lead_rate}%` : "—"}</td>
                      <td className="kn-td text-right tabular-nums">{r.bookings}</td>
                      <td className="kn-td text-right font-semibold tabular-nums">{formatCurrency(r.revenue || 0)}</td>
                      <td className="kn-td text-[11.5px] tabular-nums text-[#6B6B73]">{r.last_view_at ? formatDateTime(r.last_view_at) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-3 text-[11px] leading-relaxed text-[#8A8A8F]">
            Atribusi memakai jejak konten TERAKHIR yang dibaca pengunjung sebelum mengirim form/pesanan
            (disimpan di perambannya, tanpa data pribadi). Karena itu satu pesanan hanya dihitung untuk satu konten —
            angkanya konservatif, bukan dilebihkan.
          </p>
        </div>
      </section>
    </div>
  );
}

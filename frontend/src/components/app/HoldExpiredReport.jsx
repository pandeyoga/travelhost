import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle, CalendarX2, Download, Info, Loader2, MessageCircle, RefreshCw,
  ShieldCheck, TrendingDown,
} from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCurrency, formatDateTime } from "@/utils/formatters";

// HoldExpiredReport — laporan "Hold Hangus" untuk ops/owner.
//
// Sistem SUDAH membatalkan otomatis reservasi yang DP-nya tak masuk (penjadwal), tapi sebelum
// ini tidak ada tempat untuk MELIHAT akibatnya. Panel ini menjawab 3 pertanyaan yang mengubah
// keputusan: berapa unit-hari terbuang, apakah batas jam DP terlalu pendek, dan — paling
// penting — apakah ada tamu yang sudah transfer tapi terlambat kita verifikasi (baris merah).
//
// Tombol WhatsApp memakai tautan wa.me (nyata, bukan mock): ops bisa langsung menawarkan
// ulang tanggal yang sama sebelum unitnya dijual ke orang lain.
const RANGES = [[7, "7 hari terakhir"], [30, "30 hari terakhir"], [90, "90 hari terakhir"], [365, "1 tahun terakhir"]];
const TONE = {
  danger: { bg: "#FFF5F4", border: "#FFD0CC", fg: "#A8221A", Icon: AlertTriangle },
  warning: { bg: "#FFF8EC", border: "#FFE6B0", fg: "#8A5A00", Icon: TrendingDown },
  info: { bg: "#F4F8FF", border: "#D5E4FF", fg: "#0058CC", Icon: Info },
  success: { bg: "#F1FCF4", border: "#CBEFD5", fg: "#1B7F3B", Icon: ShieldCheck },
};

function Kpi({ label, value, hint, testId, tone = "#0058CC" }) {
  return (
    <div className="rounded-[12px] border border-[#E5E5EA] bg-white p-3.5" data-testid={testId}>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-[#8E8E93]">{label}</p>
      <p className="mt-1 text-[19px] font-bold tabular-nums" style={{ color: tone }}>{value}</p>
      {hint ? <p className="mt-0.5 text-[11.5px] text-[#6B6B73]">{hint}</p> : null}
    </div>
  );
}

export default function HoldExpiredReport() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data: res } = await apiClient.get(`/reports/hold-expired?days=${days}`);
      setData(res);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat laporan hold hangus");
    } finally { setLoading(false); }
  }, [days]);

  useEffect(() => { load(); }, [load]);

  const exportCsv = async () => {
    setDownloading(true);
    try {
      const res = await apiClient.get(`/reports/hold-expired/export?days=${days}`, { responseType: "blob" });
      const url = window.URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `hold-hangus-${days}hari.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      toast.error("Gagal mengunduh CSV");
    } finally { setDownloading(false); }
  };

  const s = data?.summary || {};
  const rows = data?.rows || [];

  const waLink = (row) => {
    const phone = String(row.phone || "").replace(/\D/g, "").replace(/^0/, "62");
    const text = `Halo ${row.customer_name}, pesanan ${row.code} (${row.vehicle_name}) batal otomatis karena DP belum masuk sebelum batas waktu. Bila masih berminat, kami bisa bantu pesan ulang tanggal yang sama.`;
    return `https://wa.me/${phone}?text=${encodeURIComponent(text)}`;
  };

  return (
    <section className="section-card" data-testid="reports-hold-expired">
      <div className="section-head">
        <div className="flex min-w-0 items-center gap-2">
          <CalendarX2 size={16} className="text-[#FF9500]" />
          <h2 className="truncate">Hold Hangus (DP tidak masuk)</h2>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
            <SelectTrigger className="w-[168px]" data-testid="hold-range"><SelectValue /></SelectTrigger>
            <SelectContent>
              {RANGES.map(([v, l]) => (
                <SelectItem key={v} value={String(v)} data-testid={`hold-range-opt-${v}`}>{l}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <button className="secondary-button" onClick={load} data-testid="hold-reload">
            <RefreshCw size={14} /> Muat ulang
          </button>
          <button className="primary-button" onClick={exportCsv} disabled={downloading || !rows.length}
            data-testid="hold-export">
            {downloading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />} CSV
          </button>
        </div>
      </div>

      <div className="section-body space-y-3">
        {loading ? (
          <div className="flex items-center gap-2 py-10 text-[13px] text-[#6B6B73]" data-testid="hold-loading">
            <Loader2 size={15} className="animate-spin" /> Memuat laporan…
          </div>
        ) : error ? (
          <div className="rounded-[12px] border border-[#FFD0CC] bg-[#FFF5F4] p-4 text-[13px] text-[#A8221A]" data-testid="hold-error">
            {error}{" "}
            <button onClick={load} className="ml-1 underline" data-testid="hold-retry">Coba lagi</button>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Kpi label="Hold hangus" value={s.count ?? 0} testId="hold-kpi-count"
                hint={`dari ${s.holds_started ?? 0} hold dimulai`} tone="#FF9500" />
              <Kpi label="Potensi hilang" value={formatCurrency(s.potential_value)} testId="hold-kpi-value"
                hint={`DP tak tertagih ${formatCurrency(s.dp_value)}`} tone="#FF3B30" />
              <Kpi label="Sudah unggah bukti" value={s.with_proof ?? 0} testId="hold-kpi-proof"
                hint="telat diverifikasi ops" tone={s.with_proof ? "#A8221A" : "#34C759"} />
              <Kpi label="Tingkat hangus" value={`${s.expiry_rate ?? 0}%`} testId="hold-kpi-rate"
                hint={`jendela rata-rata ${s.avg_hold_hours ?? 0} jam`} tone="#0058CC" />
            </div>

            {(data?.insights || []).map((ins, i) => {
              const t = TONE[ins.tone] || TONE.info;
              return (
                <div key={i} className="flex items-start gap-2 rounded-[12px] border px-3.5 py-2.5 text-[12.5px]"
                  style={{ background: t.bg, borderColor: t.border, color: t.fg }}
                  data-testid={`hold-insight-${ins.tone}`}>
                  <t.Icon size={14} className="mt-0.5 shrink-0" /> <span>{ins.text}</span>
                </div>
              );
            })}

            {rows.length === 0 ? (
              <p className="rounded-[12px] border border-dashed border-[#E5E5EA] px-4 py-10 text-center text-[13px] text-[#8E8E93]"
                data-testid="hold-empty">
                Belum ada hold yang hangus pada rentang ini.
              </p>
            ) : (
              <div className="overflow-x-auto" data-testid="hold-table">
                <table className="w-full min-w-[900px] border-collapse">
                  <thead>
                    <tr className="bg-[#FAFAFB] text-left text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">
                      <th className="whitespace-nowrap px-3 py-2.5">Kode</th>
                      <th className="whitespace-nowrap px-3 py-2.5">Pelanggan</th>
                      <th className="whitespace-nowrap px-3 py-2.5">Unit &amp; layanan</th>
                      <th className="whitespace-nowrap px-3 py-2.5">Jadwal jalan</th>
                      <th className="whitespace-nowrap px-3 py-2.5">Hangus pada</th>
                      <th className="whitespace-nowrap px-3 py-2.5 text-right">Total</th>
                      <th className="whitespace-nowrap px-3 py-2.5">Bukti</th>
                      <th className="whitespace-nowrap px-3 py-2.5">Tindak lanjut</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.id} className="border-t border-[#F2F2F5] align-top hover:bg-[#FAFAFB]"
                        data-testid={`hold-row-${r.code}`}>
                        <td className="whitespace-nowrap px-3 py-2.5 text-[12.5px] font-semibold text-[#1C1C1E]">
                          {r.code}
                          <span className="ml-1.5 rounded-full bg-[#F2F2F5] px-2 py-0.5 text-[10.5px] font-medium text-[#6B6B73]">
                            {r.source_label}
                          </span>
                        </td>
                        <td className="max-w-[190px] truncate px-3 py-2.5 text-[12.5px] text-[#1F1F25]" title={r.customer_name}>
                          {r.customer_name}
                          <span className="block text-[11.5px] text-[#8E8E93] tabular-nums">{r.phone || "tanpa nomor"}</span>
                        </td>
                        <td className="max-w-[210px] truncate px-3 py-2.5 text-[12.5px] text-[#1F1F25]">
                          {r.vehicle_name}
                          <span className="block text-[11.5px] text-[#8E8E93]">{r.route_name || r.service_label}</span>
                        </td>
                        <td className="whitespace-nowrap px-3 py-2.5 text-[12px] text-[#3C3C43]">{formatDateTime(r.start_datetime)}</td>
                        <td className="whitespace-nowrap px-3 py-2.5 text-[12px] text-[#3C3C43]">
                          {formatDateTime(r.hold_expired_at)}
                          <span className="block text-[11.5px] text-[#8E8E93]">jendela {r.hold_hours} jam</span>
                        </td>
                        <td className="whitespace-nowrap px-3 py-2.5 text-right text-[12.5px] font-semibold tabular-nums text-[#1C1C1E]">
                          {formatCurrency(r.total_amount)}
                          <span className="block text-[11.5px] font-normal text-[#8E8E93]">DP {formatCurrency(r.dp_amount)}</span>
                        </td>
                        <td className="whitespace-nowrap px-3 py-2.5 text-[12px]">
                          {r.proofs ? (
                            <span className="rounded-full bg-[#FFE0DC] px-2 py-0.5 text-[11px] font-semibold text-[#A8221A]"
                              data-testid={`hold-proof-flag-${r.code}`}>
                              {r.proofs} bukti · {r.last_proof_status || "?"}
                            </span>
                          ) : (
                            <span className="text-[#8E8E93]">—</span>
                          )}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2.5 text-[12px]">
                          {r.rebooked_code ? (
                            <span className="rounded-full bg-[#E8F7EC] px-2 py-0.5 text-[11px] font-semibold text-[#1B7F3B]">
                              pesan lagi {r.rebooked_code}
                            </span>
                          ) : r.phone ? (
                            <a href={waLink(r)} target="_blank" rel="noreferrer"
                              className="inline-flex items-center gap-1 rounded-full bg-[#25D366] px-2.5 py-1 text-[11.5px] font-semibold text-white"
                              data-testid={`hold-wa-${r.code}`}>
                              <MessageCircle size={12} /> Hubungi
                            </a>
                          ) : (
                            <span className="text-[#8E8E93]">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {data?.truncated ? (
                  <p className="px-3 py-2 text-[11.5px] text-[#8E8E93]">
                    Hanya {rows.length} baris terbaru ditampilkan — unduh CSV untuk data lengkap.
                  </p>
                ) : null}
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}

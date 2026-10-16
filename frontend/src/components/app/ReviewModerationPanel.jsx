import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Check, Copy, ExternalLink, Loader2, MessageCircle, RefreshCw, Send, Star, X,
} from "lucide-react";
import apiClient from "@/services/apiClient";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { formatDateTime } from "@/utils/formatters";

/**
 * ReviewModerationPanel — CMS-07: ulasan NYATA pelanggan → testimoni situs.
 *
 * Sebelum ini testimoni diketik sendiri oleh admin: bagus untuk tata letak, buruk untuk
 * kepercayaan (dan tidak bisa dibuktikan). Sekarang alurnya:
 *
 *   pesanan `completed` → tautan ulasan bertoken (WhatsApp **MOCK**, tercatat di Inbox)
 *   → pelanggan mengisi rating + cerita → masuk sini sebagai MENUNGGU MODERASI
 *   → disetujui → tayang di situs + ikut rata-rata rating (JSON-LD AggregateRating).
 *
 * Penolakan tidak menghapus jejak: dokumen tetap ada dengan `moderation: rejected` supaya
 * keputusan bisa ditelusuri di Audit Log.
 */
function Kpi({ label, value, hint, tone = "#0058CC", testId }) {
  return (
    <div className="rounded-[12px] border border-[#E5E5EA] bg-white p-3.5" data-testid={testId}>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-[#8E8E93]">{label}</p>
      <p className="mt-1 text-[19px] font-bold tabular-nums" style={{ color: tone }}>{value}</p>
      {hint ? <p className="mt-0.5 text-[11.5px] text-[#6B6B73]">{hint}</p> : null}
    </div>
  );
}

function Stars({ value = 0, testId }) {
  return (
    <span className="inline-flex items-center gap-0.5" data-testid={testId}>
      {[1, 2, 3, 4, 5].map((s) => (
        <Star key={s} size={12} className={s <= Number(value || 0) ? "fill-[#F5A524] text-[#F5A524]" : "text-[#D1D1D6]"} />
      ))}
    </span>
  );
}

const REQ_TONE = {
  submitted: { label: "Sudah diisi", cls: "tone-success" },
  sent: { label: "Menunggu diisi", cls: "tone-warning" },
  expired: { label: "Kedaluwarsa", cls: "tone-neutral" },
};

export default function ReviewModerationPanel() {
  const [summary, setSummary] = useState(null);
  const [pending, setPending] = useState([]);
  const [requests, setRequests] = useState([]);
  const [eligible, setEligible] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");
  const [copiedId, setCopiedId] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [s, p, r, e] = await Promise.all([
        apiClient.get("/reviews/summary"),
        apiClient.get("/reviews/pending?limit=50"),
        apiClient.get("/reviews/requests?limit=50"),
        apiClient.get("/reviews/eligible-bookings?limit=30"),
      ]);
      setSummary(s.data || {});
      setPending(Array.isArray(p.data) ? p.data : []);
      setRequests(Array.isArray(r.data) ? r.data : []);
      setEligible(Array.isArray(e.data) ? e.data : []);
    } catch (err) {
      setError(err?.response?.data?.detail || "Gagal memuat data ulasan");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const moderate = async (row, action) => {
    setBusyId(row.id);
    try {
      await apiClient.post(`/reviews/${row.id}/moderate`, { action });
      toast.success(action === "approve" ? "Ulasan tayang di situs" : "Ulasan ditolak (tidak tayang)");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memoderasi ulasan");
    } finally { setBusyId(""); }
  };

  const sendRequest = async (booking) => {
    setBusyId(booking.id);
    try {
      const { data } = await apiClient.post("/reviews/requests", { booking_id: booking.id });
      toast.success(`Tautan ulasan dibuat untuk ${booking.code} — WhatsApp MOCK (tercatat di Inbox)`);
      if (data?.request?.link) setCopiedId("");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengirim permintaan ulasan");
    } finally { setBusyId(""); }
  };

  const absLink = (link) => {
    const raw = String(link || "");
    if (!raw) return "";
    if (/^https?:/i.test(raw)) return raw;
    return `${window.location.origin}${raw.startsWith("/") ? "" : "/"}${raw}`;
  };

  const copyLink = async (row) => {
    const href = absLink(row.link);
    try { await navigator.clipboard.writeText(href); setCopiedId(row.id); setTimeout(() => setCopiedId(""), 2000); toast.success("Tautan ulasan disalin"); }
    catch { toast.message(href); }
  };

  if (loading) return <LoadingState testId="reviews-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} testId="reviews-error" />;

  const s = summary || {};

  return (
    <div className="space-y-4" data-testid="reviews-panel">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Tayang di situs" value={s.count ?? 0} hint="testimoni disetujui" tone="#1B7F3B" testId="reviews-kpi-published" />
        <Kpi label="Rata-rata rating" value={s.average ? Number(s.average).toFixed(2) : "—"} hint="dipakai AggregateRating" tone="#8A5A00" testId="reviews-kpi-average" />
        <Kpi label="Menunggu moderasi" value={s.pending ?? 0} hint="belum tayang" tone={Number(s.pending) > 0 ? "#A8221A" : "#0058CC"} testId="reviews-kpi-pending" />
        <Kpi label="Tingkat respons" value={`${s.response_rate ?? 0}%`} hint={`${s.submitted ?? 0} dari ${s.requests ?? 0} permintaan`} testId="reviews-kpi-response" />
      </div>

      <section className="section-card" data-testid="reviews-pending-card">
        <div className="section-head">
          <h2 className="truncate">Menunggu moderasi</h2>
          <button className="secondary-button" onClick={load} data-testid="reviews-refresh"><RefreshCw size={14} /> Muat ulang</button>
        </div>
        <div className="section-body">
          {pending.length === 0 ? (
            <EmptyState title="Tidak ada ulasan menunggu" testId="reviews-pending-empty"
              description="Ulasan baru muncul di sini setelah pelanggan mengisi tautan yang dikirim saat pesanan selesai." />
          ) : (
            <div className="space-y-2.5" data-testid="reviews-pending-list">
              {pending.map((row) => (
                <div key={row.id} className="rounded-[12px] border border-[#FFE6B0] bg-[#FFF8EC] p-3.5" data-testid={`review-pending-${row.id}`}>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="flex flex-wrap items-center gap-2 text-[13px] font-bold text-[#1C1C1E]">
                        {row.name || "Pelanggan"}
                        <Stars value={row.rating} testId={`review-stars-${row.id}`} />
                        {row.booking_code ? <span className="status-pill tone-info">{row.booking_code}</span> : null}
                        {row.source === "review" ? <span className="status-pill tone-purple">dari pelanggan</span> : null}
                      </p>
                      <p className="mt-0.5 text-[11.5px] text-[#6B6B73]">
                        {row.role || "—"}{row.submitted_at ? ` · ${formatDateTime(row.submitted_at)}` : ""}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                      <button className="primary-button !h-8" disabled={busyId === row.id}
                        onClick={() => moderate(row, "approve")} data-testid={`review-approve-${row.id}`}>
                        {busyId === row.id ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />} Setujui
                      </button>
                      <button className="secondary-button !h-8" disabled={busyId === row.id}
                        onClick={() => moderate(row, "reject")} data-testid={`review-reject-${row.id}`}>
                        <X size={13} /> Tolak
                      </button>
                    </div>
                  </div>
                  <p className="mt-2 whitespace-pre-line rounded-[10px] bg-white px-3 py-2 text-[12.5px] leading-relaxed text-[#3A3A3C]"
                    data-testid={`review-quote-${row.id}`}>{row.quote}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="section-card" data-testid="reviews-eligible-card">
        <div className="section-head">
          <h2 className="truncate">Pesanan selesai yang belum diminta ulasan</h2>
          <span className="status-pill tone-warning"><MessageCircle size={10} /> WhatsApp MOCK</span>
        </div>
        <div className="section-body">
          {eligible.length === 0 ? (
            <EmptyState title="Semua pesanan selesai sudah diminta ulasan" testId="reviews-eligible-empty"
              description="Penjadwal juga mengirim otomatis setiap pesanan berubah menjadi selesai." />
          ) : (
            <div className="kn-table-wrap" data-testid="reviews-eligible-list">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="kn-th">Kode</th>
                    <th className="kn-th">Pelanggan</th>
                    <th className="kn-th">Rute</th>
                    <th className="kn-th">Selesai</th>
                    <th className="kn-th text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {eligible.map((b) => (
                    <tr key={b.id} className="kn-row" data-testid={`review-eligible-${b.id}`}>
                      <td className="kn-td font-semibold">{b.code}</td>
                      <td className="kn-td">{b.customer_name || "—"}</td>
                      <td className="kn-td text-[11.5px] text-[#6B6B73]">{[b.origin, b.destination].filter(Boolean).join(" → ") || "—"}</td>
                      <td className="kn-td text-[11.5px] tabular-nums text-[#6B6B73]">{b.end_datetime ? formatDateTime(b.end_datetime) : "—"}</td>
                      <td className="kn-td text-right">
                        <button className="secondary-button !h-8" disabled={busyId === b.id}
                          onClick={() => sendRequest(b)} data-testid={`review-send-${b.id}`}>
                          {busyId === b.id ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />} Kirim tautan
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      <section className="section-card" data-testid="reviews-requests-card">
        <div className="section-head"><h2 className="truncate">Permintaan ulasan terkirim</h2></div>
        <div className="section-body">
          {requests.length === 0 ? (
            <EmptyState title="Belum ada permintaan ulasan" testId="reviews-requests-empty"
              description="Permintaan dibuat otomatis saat pesanan selesai, atau manual dari daftar di atas." />
          ) : (
            <div className="kn-table-wrap" data-testid="reviews-requests-list">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="kn-th">Pesanan</th>
                    <th className="kn-th">Pelanggan</th>
                    <th className="kn-th">Status</th>
                    <th className="kn-th">Dibuat</th>
                    <th className="kn-th text-right">Tautan</th>
                  </tr>
                </thead>
                <tbody>
                  {requests.map((row) => {
                    const tone = REQ_TONE[row.status] || REQ_TONE.sent;
                    return (
                      <tr key={row.id} className="kn-row" data-testid={`review-request-${row.id}`}>
                        <td className="kn-td font-semibold">{row.booking_code || "—"}</td>
                        <td className="kn-td">
                          {row.customer_name || "—"}
                          <span className="block text-[11px] text-[#8A8A8F]">{row.route || ""}</span>
                        </td>
                        <td className="kn-td">
                          <span className={`status-pill ${tone.cls}`}>{tone.label}</span>
                          {row.rating ? <Stars value={row.rating} /> : null}
                        </td>
                        <td className="kn-td text-[11.5px] tabular-nums text-[#6B6B73]">{row.created_at ? formatDateTime(row.created_at) : "—"}</td>
                        <td className="kn-td">
                          <div className="flex items-center justify-end gap-1">
                            <button className="icon-button !h-8 !w-8" title="Salin tautan ulasan"
                              onClick={() => copyLink(row)} data-testid={`review-copy-${row.id}`}>
                              {copiedId === row.id ? <Check size={13} /> : <Copy size={13} />}
                            </button>
                            <a className="icon-button !h-8 !w-8" title="Buka halaman ulasan" href={absLink(row.link)}
                              target="_blank" rel="noreferrer" data-testid={`review-open-${row.id}`}>
                              <ExternalLink size={13} />
                            </a>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-3 text-[11px] leading-relaxed text-[#8A8A8F]">
            Kanal pengiriman saat ini <span className="font-semibold">WhatsApp MOCK</span>: pesan tercatat di
            Inbox &amp; Audit Log, belum benar-benar terkirim ke ponsel pelanggan. Tautan di atas tetap NYATA —
            bisa disalin dan dikirim manual sekarang.
          </p>
        </div>
      </section>
    </div>
  );
}

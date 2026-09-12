import { useCallback, useEffect, useState } from "react";
import { Inbox, RefreshCw, FlaskConical, DownloadCloud, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { LoadingState, ErrorState, EmptyState } from "@/components/shared/DataStates";
import { formatDateTime } from "@/utils/formatters";

/**
 * AdsPlatformLeads — lead yang masuk LANGSUNG dari platform:
 *   (a) Meta Lead Ads via webhook (diverifikasi X-Hub-Signature-256, dedup leadgen_id)
 *   (b) Klik-ke-WhatsApp (CTWA) — masuk lewat webhook WhatsApp dan tercatat di CRM
 *
 * Karena kredensial belum tentu ada, halaman menyediakan **Simulator** yang membentuk payload
 * webhook resmi + menandatanganinya, sehingga alur bisa diuji sekarang tanpa akun Meta.
 */
const STATUS_CLS = {
  ok: "bg-[#E7F7EC] text-[#12703A]",
  skipped: "bg-[#F2F2F5] text-[#6B6B73]",
  not_configured: "bg-[#FFF3E0] text-[#8A5300]",
  error: "bg-[#FDECEA] text-[#A8221A]",
};

export default function AdsPlatformLeads({ canManage }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState("");
  const [form, setForm] = useState({ name: "", phone: "", email: "", destination: "", campaign_id: "", ad_id: "" });
  const [ctwa, setCtwa] = useState({ from_phone: "", text: "Halo, saya lihat iklan Anda", ad_id: "", ctwa_clid: "" });
  const [formId, setFormId] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/ads/platform-leads?limit=50")
      .then((r) => { setRows(r.data?.rows || []); setError(null); })
      .catch((e) => setError(e?.response?.data?.detail || "Gagal memuat lead iklan"))
      .finally(() => setLoading(false));
  }, []);
  useEffect(load, [load]);

  const simulateLeadAds = async () => {
    setBusy("lead");
    try {
      const { data } = await apiClient.post("/ads/platform-leads/simulate", form);
      const res = data?.result || {};
      if (res.status === "received") toast.success("Lead iklan diterima & masuk CRM");
      else if (res.status === "duplicate") toast.warning("Lead ini sudah pernah masuk (dedup bekerja)");
      else toast.warning(res.reason || "Lead tidak diproses");
      setForm({ name: "", phone: "", email: "", destination: "", campaign_id: "", ad_id: "" });
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menjalankan simulasi Lead Ads");
    } finally { setBusy(""); }
  };

  const simulateCtwa = async () => {
    setBusy("ctwa");
    try {
      const { data } = await apiClient.post("/wa/simulate-inbound", {
        from_phone: ctwa.from_phone, text: ctwa.text, name: "Calon dari Iklan WA",
        referral: { source_type: "ad", source_id: ctwa.ad_id, ctwa_clid: ctwa.ctwa_clid,
                    headline: "Iklan Klik-ke-WhatsApp" },
      });
      if (data?.from_ad) toast.success(`Chat dari iklan terdeteksi (iklan ${data.ad_id || "-"}) & lead dibuat`);
      else toast.warning("Pesan diterima tetapi tidak terdeteksi berasal dari iklan");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menjalankan simulasi Klik-ke-WhatsApp");
    } finally { setBusy(""); }
  };

  const backfill = async () => {
    setBusy("backfill");
    try {
      const { data } = await apiClient.post("/ads/platform-leads/backfill", { form_id: formId });
      if (data?.status === "ok") toast.success(`Backfill selesai — ${data.ingested} baru, ${data.duplicates} duplikat`);
      else toast.warning(data?.reason || "Backfill belum bisa dijalankan");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal backfill lead");
    } finally { setBusy(""); }
  };

  if (loading) return <LoadingState testId="ads-leads-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="space-y-4" data-testid="ads-leads">
      <section className="section-card">
        <div className="section-head flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="flex items-center gap-2"><Inbox size={15} /> Lead dari Iklan</h2>
            <p className="mt-0.5 text-[12px] font-normal text-[#6B6B73]">
              Lead Ads &amp; Klik-ke-WhatsApp masuk otomatis ke CRM lengkap dengan kampanye/iklan sumbernya.
            </p>
          </div>
          <button className="secondary-button" onClick={load} data-testid="ads-leads-refresh">
            <RefreshCw size={14} /> Muat ulang
          </button>
        </div>
        <div className="section-body">
          {!rows.length ? (
            <EmptyState title="Belum ada lead dari platform" testId="ads-leads-empty"
              description="Setelah webhook Lead Ads aktif, setiap pengisian formulir iklan langsung muncul di sini. Coba dulu dengan simulator di bawah." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[12.5px]">
                <thead>
                  <tr className="border-b border-[#EFF0F2] text-left text-[11px] uppercase tracking-wide text-[#8E8E93]">
                    <th className="px-4 py-2.5">Lead</th>
                    <th className="px-3 py-2.5">Kampanye / Iklan</th>
                    <th className="px-3 py-2.5">Form</th>
                    <th className="px-3 py-2.5">Isi diambil</th>
                    <th className="px-3 py-2.5">Waktu</th>
                  </tr>
                </thead>
                <tbody data-testid="ads-leads-list">
                  {rows.map((r) => (
                    <tr key={r.id} className="border-b border-[#F6F6F8] hover:bg-[#FAFAFB]" data-testid={`ads-lead-row-${r.id}`}>
                      <td className="px-4 py-2.5">
                        <div className="font-semibold text-[#1C1C1E]">
                          {r.lead?.customer_name || r.fields?.name || "(menunggu isi form)"}
                        </div>
                        <div className="text-[11px] text-[#8E8E93]">{r.lead?.phone || r.fields?.phone || "-"}</div>
                      </td>
                      <td className="px-3 py-2.5">
                        <div>{r.campaign_id || "—"}</div>
                        <div className="text-[11px] text-[#8E8E93]">iklan {r.ad_id || "—"}</div>
                      </td>
                      <td className="px-3 py-2.5">{r.form_id || "—"}</td>
                      <td className="px-3 py-2.5">
                        <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS_CLS[r.fetch_status] || STATUS_CLS.error}`}>
                          {r.fetch_status === "ok" ? "lengkap" : r.fetch_status}
                        </span>
                        {r.fetch_reason ? <div className="mt-0.5 text-[11px] text-[#8A5300]">{r.fetch_reason}</div> : null}
                      </td>
                      <td className="px-3 py-2.5 text-[11.5px] text-[#6B6B73]">{formatDateTime(r.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      {canManage ? (
        <>
          <section className="section-card">
            <div className="section-head">
              <h2 className="flex items-center gap-2"><FlaskConical size={15} /> Simulator Lead Ads (uji tanpa kredensial)</h2>
              <p className="mt-0.5 text-[12px] font-normal text-[#6B6B73]">
                Membentuk payload webhook resmi Meta, menandatanganinya dengan app secret tersimpan, lalu memprosesnya seperti panggilan sungguhan.
              </p>
            </div>
            <div className="section-body space-y-3">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {[["name", "Nama"], ["phone", "Nomor WhatsApp"], ["email", "Email"],
                  ["destination", "Destinasi diminta"], ["campaign_id", "Campaign ID"], ["ad_id", "Ad ID"]].map(([key, label]) => (
                  <div key={key} className="space-y-1.5">
                    <label className="text-[12px] font-semibold text-[#3a3f4a]" htmlFor={`sim-${key}`}>{label}</label>
                    <input id={`sim-${key}`} value={form[key]} data-testid={`ads-sim-${key}`}
                      onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                      className="h-9 w-full rounded-lg border border-[#E5E5EA] bg-white px-3 text-[13px] outline-none focus:border-[#007AFF]" />
                  </div>
                ))}
              </div>
              <button className="primary-button" onClick={simulateLeadAds}
                disabled={busy === "lead" || (!form.phone && !form.email)} data-testid="ads-sim-submit">
                <FlaskConical size={14} /> {busy === "lead" ? "Memproses…" : "Kirim Lead Uji"}
              </button>
            </div>
          </section>

          <section className="section-card">
            <div className="section-head">
              <h2 className="flex items-center gap-2"><ShieldCheck size={15} /> Simulator Klik-ke-WhatsApp (CTWA)</h2>
              <p className="mt-0.5 text-[12px] font-normal text-[#6B6B73]">
                Meniru pesan WhatsApp masuk yang membawa <b>ctwa_clid</b> dari iklan — jembatan satu-satunya antara chat WA dan iklan yang membayarnya.
              </p>
            </div>
            <div className="section-body space-y-3">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[["from_phone", "Nomor pengirim"], ["text", "Isi pesan"], ["ad_id", "Ad ID (source_id)"], ["ctwa_clid", "ctwa_clid"]].map(([key, label]) => (
                  <div key={key} className="space-y-1.5">
                    <label className="text-[12px] font-semibold text-[#3a3f4a]" htmlFor={`ctwa-${key}`}>{label}</label>
                    <input id={`ctwa-${key}`} value={ctwa[key]} data-testid={`ads-ctwa-${key}`}
                      onChange={(e) => setCtwa((c) => ({ ...c, [key]: e.target.value }))}
                      className="h-9 w-full rounded-lg border border-[#E5E5EA] bg-white px-3 text-[13px] outline-none focus:border-[#007AFF]" />
                  </div>
                ))}
              </div>
              <button className="primary-button" onClick={simulateCtwa}
                disabled={busy === "ctwa" || !ctwa.from_phone} data-testid="ads-ctwa-submit">
                <ShieldCheck size={14} /> {busy === "ctwa" ? "Memproses…" : "Kirim Chat Uji dari Iklan"}
              </button>
            </div>
          </section>

          <section className="section-card">
            <div className="section-head">
              <h2 className="flex items-center gap-2"><DownloadCloud size={15} /> Backfill Lead per Formulir</h2>
              <p className="mt-0.5 text-[12px] font-normal text-[#6B6B73]">
                Jaring pengaman bila webhook pernah gagal: ambil ulang seluruh lead dari satu Form ID (butuh Page Access Token).
              </p>
            </div>
            <div className="section-body flex flex-wrap items-end gap-2">
              <div className="w-[260px] space-y-1.5">
                <label className="text-[12px] font-semibold text-[#3a3f4a]" htmlFor="ads-backfill-form">Form ID</label>
                <input id="ads-backfill-form" value={formId} onChange={(e) => setFormId(e.target.value)}
                  data-testid="ads-backfill-input" placeholder="1234567890"
                  className="h-9 w-full rounded-lg border border-[#E5E5EA] bg-white px-3 text-[13px] outline-none focus:border-[#007AFF]" />
              </div>
              <button className="secondary-button" onClick={backfill} disabled={busy === "backfill" || !formId}
                data-testid="ads-backfill-submit">
                <DownloadCloud size={14} /> {busy === "backfill" ? "Mengambil…" : "Ambil Ulang"}
              </button>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}

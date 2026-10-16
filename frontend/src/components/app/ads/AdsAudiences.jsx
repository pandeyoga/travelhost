import { useCallback, useEffect, useState } from "react";
import { Users2, ShieldAlert, UploadCloud, Sparkles, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { LoadingState, ErrorState, EmptyState } from "@/components/shared/DataStates";
import SelectField from "@/components/shared/SelectField";
import { formatDateTime, formatQty } from "@/utils/formatters";

/**
 * AdsAudiences — segmen CRM → Custom Audience Meta / Customer Match Google (+ Lookalike).
 *
 * Aturan yang terlihat jelas di UI:
 *   • Kontak tanpa izin pemasaran (`marketing_consent`) TIDAK dikirim, dan jumlahnya ditampilkan.
 *   • Mode "Validasi" tidak mengirim data apa pun — untuk memastikan angka & izin sudah benar.
 *   • Identitas di-hash SHA-256 di server; nomor Indonesia dinormalkan per aturan tiap platform.
 */
const PROVIDERS = [
  { value: "meta", label: "Meta — Custom Audience" },
  { value: "google", label: "Google — Customer Match" },
];
const MODES = [
  { value: "validate", label: "Validasi saja (tidak mengirim data)" },
  { value: "publish", label: "Kirim sungguhan ke platform" },
];

export default function AdsAudiences({ canManage }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [segmentId, setSegmentId] = useState("");
  const [provider, setProvider] = useState("meta");
  const [mode, setMode] = useState("validate");
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState("");
  const [look, setLook] = useState({ origin_audience_id: "", ratio: "0.01", seed_size: "" });

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/ads/audiences")
      .then((r) => {
        setData(r.data);
        setSegmentId((prev) => prev || (r.data?.segments || [])[0]?.id || "");
        setError(null);
      })
      .catch((e) => setError(e?.response?.data?.detail || "Gagal memuat data audiens"))
      .finally(() => setLoading(false));
  }, []);
  useEffect(load, [load]);

  const runPreview = async () => {
    setBusy("preview");
    try {
      const { data: res } = await apiClient.post("/ads/audiences/preview", { segment_id: segmentId });
      setPreview(res);
      toast.success(`${res.eligible} kontak layak dikirim · ${res.consent_filtered} tersaring karena tanpa izin`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghitung anggota segmen");
    } finally { setBusy(""); }
  };

  const runSync = async () => {
    setBusy("sync");
    try {
      const { data: res } = await apiClient.post("/ads/audiences/sync", {
        segment_id: segmentId, provider, mode,
      });
      const st = res?.result?.status;
      if (st === "dry_run") toast.success(`Validasi selesai — ${res.stats.eligible} kontak siap, ${res.stats.batches} batch`);
      else if (st === "ok") toast.success(`Terkirim ke ${provider} — ${res.stats.uploaded} kontak`);
      else toast.warning(res?.result?.reason || `Belum bisa dikirim (${st})`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyinkronkan audiens");
    } finally { setBusy(""); }
  };

  const runLookalike = async () => {
    setBusy("lookalike");
    try {
      const { data: res } = await apiClient.post("/ads/audiences/lookalike", {
        origin_audience_id: look.origin_audience_id, ratio: Number(look.ratio) || 0.01,
        seed_size: Number(look.seed_size) || 0, mode,
      });
      const st = res?.result?.status;
      if (st === "dry_run") toast.success("Payload Lookalike tervalidasi (belum dikirim)");
      else if (st === "ok") toast.success("Lookalike Audience dibuat di Meta");
      else toast.warning(res?.result?.reason || `Belum bisa dibuat (${st})`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat Lookalike");
    } finally { setBusy(""); }
  };

  if (loading) return <LoadingState testId="ads-aud-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const segments = data?.segments || [];
  const history = data?.history || [];
  const segOptions = segments.map((s) => ({ value: s.id, label: `${s.name} (${s.audience === "lead" ? "lead" : "pelanggan"})` }));

  return (
    <div className="space-y-4" data-testid="ads-audiences">
      <section className="section-card">
        <div className="section-head">
          <h2 className="flex items-center gap-2"><Users2 size={15} /> Kirim Segmen CRM sebagai Audiens</h2>
          <p className="mt-0.5 text-[12px] font-normal text-[#6B6B73]">
            Retargeting pelanggan lama & lead panas adalah cara termurah menaikkan ROAS. Data dikirim ter-hash, tanpa nama/nomor mentah.
          </p>
        </div>
        <div className="section-body space-y-3">
          {!segments.length ? (
            <EmptyState title="Belum ada segmen CRM" testId="ads-aud-empty"
              description="Buat segmen dulu di CRM → tab Segmen (mis. pelanggan pernah booking, atau lead panas 30 hari)." />
          ) : (
            <>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="space-y-1.5">
                  <label className="text-[12px] font-semibold text-[#3a3f4a]">Segmen</label>
                  <SelectField value={segmentId} onChange={setSegmentId} options={segOptions} testId="ads-aud-segment" className="w-full" />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[12px] font-semibold text-[#3a3f4a]">Tujuan</label>
                  <SelectField value={provider} onChange={setProvider} options={PROVIDERS} testId="ads-aud-provider" className="w-full" />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[12px] font-semibold text-[#3a3f4a]">Mode</label>
                  <SelectField value={mode} onChange={setMode} options={MODES} testId="ads-aud-mode" className="w-full" />
                </div>
              </div>

              {preview ? (
                <div className="space-y-2" data-testid="ads-aud-preview">
                  <div className="grid grid-cols-2 gap-2 rounded-xl bg-[#F7F8FA] p-3 sm:grid-cols-5">
                    {[["Total anggota", preview.total], ["Layak kirim", preview.eligible],
                      ["Tersaring (tanpa izin)", preview.consent_filtered],
                      ["Tanpa email/telepon", preview.skipped_no_identifier], ["Batch", preview.batches]].map(([label, value]) => (
                      <div key={label}>
                        <p className="text-[11px] text-[#8E8E93]">{label}</p>
                        <p className="text-[16px] font-bold tabular-nums text-[#1C1C1E]">{formatQty(value || 0)}</p>
                      </div>
                    ))}
                  </div>
                  {preview.eligible === 0 && preview.consent_filtered > 0 ? (
                    <p className="flex items-start gap-1.5 rounded-lg bg-[#FFF8EC] p-2.5 text-[11.5px] text-[#8A5300]"
                      data-testid="ads-aud-no-consent">
                      <ShieldAlert size={13} className="mt-0.5 shrink-0" />
                      Semua kontak tersaring karena belum ada izin pemasaran. Izin terkumpul otomatis
                      dari centang persetujuan di form situs publik, lead dari iklan (Lead Ads / Klik-ke-WhatsApp),
                      atau bisa Anda tandai manual pada data pelanggan.
                    </p>
                  ) : null}
                </div>
              ) : null}

              <div className="flex flex-wrap gap-2">
                <button className="secondary-button" onClick={runPreview} disabled={!segmentId || busy === "preview"}
                  data-testid="ads-aud-preview-btn">
                  <RefreshCw size={14} /> {busy === "preview" ? "Menghitung…" : "Hitung Anggota"}
                </button>
                {canManage ? (
                  <button className="primary-button" onClick={runSync} disabled={!segmentId || busy === "sync"}
                    data-testid="ads-aud-sync">
                    <UploadCloud size={14} /> {busy === "sync" ? "Memproses…" : mode === "validate" ? "Validasi Sinkron" : "Kirim ke Platform"}
                  </button>
                ) : null}
              </div>
              <p className="flex items-start gap-1.5 text-[11.5px] text-[#8A5300]">
                <ShieldAlert size={13} className="mt-0.5 shrink-0" />
                Kontak tanpa izin pemasaran otomatis disaring dan jumlahnya dilaporkan — jangan pernah unggah kontak tanpa izin.
              </p>
            </>
          )}
        </div>
      </section>

      {canManage ? (
        <section className="section-card">
          <div className="section-head">
            <h2 className="flex items-center gap-2"><Sparkles size={15} /> Lookalike Audience (Meta)</h2>
            <p className="mt-0.5 text-[12px] font-normal text-[#6B6B73]">
              Cari orang baru yang mirip pelanggan terbaik Anda. Meta butuh audiens sumber minimal {data?.min_lookalike_seed || 100} kontak cocok.
            </p>
          </div>
          <div className="section-body space-y-3">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {[["origin_audience_id", "ID audiens sumber"], ["ratio", "Rasio kemiripan (0.01–0.20)"],
                ["seed_size", "Jumlah kontak audiens sumber"]].map(([key, label]) => (
                <div key={key} className="space-y-1.5">
                  <label className="text-[12px] font-semibold text-[#3a3f4a]" htmlFor={`look-${key}`}>{label}</label>
                  <input id={`look-${key}`} value={look[key]} data-testid={`ads-look-${key}`}
                    onChange={(e) => setLook((l) => ({ ...l, [key]: e.target.value }))}
                    className="h-9 w-full rounded-lg border border-[#E5E5EA] bg-white px-3 text-[13px] tabular-nums outline-none focus:border-[#007AFF]" />
                </div>
              ))}
            </div>
            <button className="secondary-button" onClick={runLookalike}
              disabled={!look.origin_audience_id || busy === "lookalike"} data-testid="ads-look-submit">
              <Sparkles size={14} /> {busy === "lookalike" ? "Memproses…" : "Buat Lookalike"}
            </button>
          </div>
        </section>
      ) : null}

      <section className="section-card">
        <div className="section-head"><h2 className="flex items-center gap-2"><UploadCloud size={15} /> Riwayat Sinkron Audiens</h2></div>
        <div className="section-body">
          {!history.length ? (
            <EmptyState title="Belum ada riwayat sinkron" testId="ads-aud-history-empty"
              description="Setiap sinkron dicatat: berapa dikirim, berapa tersaring karena tanpa izin, dan hasil dari platform." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[12.5px]">
                <thead>
                  <tr className="border-b border-[#EFF0F2] text-left text-[11px] uppercase tracking-wide text-[#8E8E93]">
                    <th className="px-4 py-2.5">Segmen</th>
                    <th className="px-3 py-2.5">Tujuan</th>
                    <th className="px-3 py-2.5">Mode</th>
                    <th className="px-3 py-2.5 text-right">Layak</th>
                    <th className="px-3 py-2.5 text-right">Tersaring</th>
                    <th className="px-3 py-2.5">Hasil</th>
                    <th className="px-3 py-2.5">Waktu</th>
                  </tr>
                </thead>
                <tbody data-testid="ads-aud-history">
                  {history.map((h) => (
                    <tr key={h.id} className="border-b border-[#F6F6F8]">
                      <td className="px-4 py-2.5 font-semibold text-[#1C1C1E]">{h.segment_name || h.segment_id}</td>
                      <td className="px-3 py-2.5">{h.provider}</td>
                      <td className="px-3 py-2.5">{h.mode === "validate" ? "validasi" : "kirim"}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{formatQty(h.eligible || 0)}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{formatQty(h.consent_filtered || 0)}</td>
                      <td className="px-3 py-2.5">
                        <span className="rounded-full bg-[#F2F2F5] px-2 py-0.5 text-[11px] font-semibold text-[#3C3C43]">{h.status}</span>
                        {h.reason ? <div className="mt-0.5 text-[11px] text-[#8A5300]">{h.reason}</div> : null}
                      </td>
                      <td className="px-3 py-2.5 text-[11.5px] text-[#6B6B73]">{formatDateTime(h.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

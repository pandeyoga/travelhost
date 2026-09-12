import { useCallback, useEffect, useState } from "react";
import { FlaskConical, Trophy, RefreshCw, Loader2, Info } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import SelectField from "@/components/shared/SelectField";
import { Switch } from "@/components/ui/switch";

/**
 * LandingAbPanel.jsx — uji A/B halaman iklan: dua versi headline/CTA + laporan pemenang.
 *
 * Keputusan desain penting: yang diuji SENGAJA dibatasi pada judul, sub-judul, label kecil, dan
 * label tombol. Itu bagian dengan pengaruh terbesar pada konversi dan paling murah diuji; menguji
 * seluruh halaman sekaligus membuat hasilnya tak bisa ditafsirkan ("menang karena apa?").
 * Varian A selalu "asli" tanpa perubahan supaya perbandingannya punya titik nol yang jujur.
 *
 * Pemenang hanya diumumkan bila tiap versi sudah mencapai sampel minimum DAN selisihnya di atas
 * 10% — pengumuman prematur akan membuat pemilik memindahkan anggaran iklan berdasarkan kebetulan.
 */
const OVERRIDES = [
  ["title", "Judul hero"],
  ["subtitle", "Sub-judul hero"],
  ["eyebrow", "Label kecil di atas judul"],
  ["cta_label", "Label tombol utama"],
];

const pct = (n) => `${Number(n || 0).toFixed(2)}%`;

export default function LandingAbPanel({ page, ab, onChange, publicUrl }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const pageId = page?.id;

  const load = useCallback(() => {
    if (!pageId) return;
    setLoading(true);
    apiClient.get(`/landing/pages/${pageId}/ab`)
      .then(({ data }) => setReport(data))
      .catch(() => toast.error("Gagal memuat laporan A/B"))
      .finally(() => setLoading(false));
  }, [pageId]);
  useEffect(load, [load]);

  const variants = ab?.variants?.length ? ab.variants : [
    { id: "A", name: "Asli", weight: 50, overrides: {} },
    { id: "B", name: "Varian B", weight: 50, overrides: {} },
  ];
  const setVariant = (i, next) => onChange({ ...ab, variants: variants.map((v, j) => (j === i ? next : v)) });

  return (
    <section className="section-card" data-testid="lp-ab-panel">
      <div className="section-head flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-[13px]"><FlaskConical size={14} /> Uji A/B</h2>
        <Switch checked={!!ab?.enabled} data-testid="lp-ab-enabled"
          onCheckedChange={(v) => onChange({ ...ab, enabled: v, variants })} />
      </div>
      <div className="section-body space-y-2.5">
        <p className="text-[11.5px] text-[#6B6B73]">
          Saat aktif, pengunjung dibagi otomatis ke dua versi. Versi yang dilihat seseorang tidak
          berubah walau halaman di-refresh, supaya angkanya bisa dipercaya.
        </p>

        {variants.map((v, i) => (
          <div key={v.id} className="space-y-1.5 rounded-lg bg-[#F7F8FA] p-2.5" data-testid={`lp-ab-variant-${v.id}`}>
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#1C1C1E] text-[11px] font-bold text-white">
                {v.id}
              </span>
              <input value={v.name || ""} onChange={(e) => setVariant(i, { ...v, name: e.target.value })}
                data-testid={`lp-ab-name-${v.id}`} placeholder="Nama versi"
                className="h-8 flex-1 rounded-lg border border-[#E5E5EA] bg-white px-2.5 text-[12.5px] outline-none focus:border-[#007AFF]" />
              <div className="w-[104px]">
                <SelectField value={String(v.weight ?? 50)} testId={`lp-ab-weight-${v.id}`} className="w-full"
                  onChange={(val) => setVariant(i, { ...v, weight: Number(val) })}
                  options={[10, 20, 30, 40, 50, 60, 70, 80, 90].map((n) => ({ value: String(n), label: `${n}% trafik` }))} />
              </div>
            </div>
            {i === 0 ? (
              <p className="flex items-start gap-1.5 text-[11px] text-[#8E8E93]">
                <Info size={11} className="mt-0.5 shrink-0" /> Versi asli — dipakai sebagai pembanding,
                isinya mengikuti blok halaman.
              </p>
            ) : (
              OVERRIDES.map(([key, label]) => (
                <div key={key} className="space-y-1">
                  <label className="text-[11px] font-semibold text-[#3a3f4a]" htmlFor={`ab-${v.id}-${key}`}>
                    {label}
                  </label>
                  <input id={`ab-${v.id}-${key}`} value={(v.overrides || {})[key] || ""}
                    data-testid={`lp-ab-${v.id}-${key}`} placeholder="Kosongkan = sama dengan versi asli"
                    onChange={(e) => setVariant(i, { ...v, overrides: { ...(v.overrides || {}), [key]: e.target.value } })}
                    className="h-8 w-full rounded-lg border border-[#E5E5EA] bg-white px-2.5 text-[12px] outline-none focus:border-[#007AFF]" />
                </div>
              ))
            )}
            {publicUrl && i > 0 ? (
              <a href={`${publicUrl}?variant=${v.id}`} target="_blank" rel="noreferrer"
                data-testid={`lp-ab-preview-${v.id}`}
                className="inline-block text-[11.5px] font-bold text-[#007AFF] underline-offset-2 hover:underline">
                Lihat versi {v.id} di halaman publik
              </a>
            ) : null}
          </div>
        ))}

        <div className="grid grid-cols-2 gap-2">
          <SelectField value={ab?.goal || "lead"} onChange={(v) => onChange({ ...ab, goal: v })}
            testId="lp-ab-goal" className="w-full"
            options={[{ value: "lead", label: "Target: lead terkirim" },
              { value: "cta_click", label: "Target: klik tombol" }]} />
          <SelectField value={String(ab?.min_sample || 30)} onChange={(v) => onChange({ ...ab, min_sample: Number(v) })}
            testId="lp-ab-minsample" className="w-full"
            options={[30, 50, 100, 200, 500].map((n) => ({ value: String(n), label: `Min. ${n} tampilan` }))} />
        </div>

        <div className="rounded-lg border border-[#EFF0F2] p-2.5">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-[11.5px] font-bold uppercase tracking-wide text-[#6B6B73]">Hasil</p>
            <button type="button" className="icon-button !h-6 !w-6" onClick={load} aria-label="Muat ulang hasil"
              data-testid="lp-ab-refresh">
              {loading ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
            </button>
          </div>
          {loading && !report ? (
            <div className="space-y-1.5" data-testid="lp-ab-loading">
              {[0, 1].map((i) => <div key={i} className="h-9 animate-pulse rounded bg-[#EEF1F5]" />)}
            </div>
          ) : !report || !report.variants?.length ? (
            <p className="text-[11.5px] text-[#8E8E93]" data-testid="lp-ab-empty">
              Belum ada data. Angka muncul setelah halaman diterbitkan dan dikunjungi.
            </p>
          ) : (
            <div className="space-y-1.5" data-testid="lp-ab-report">
              {report.variants.map((v) => (
                <div key={v.id} className={`rounded-lg px-2.5 py-2 ${
                  report.winner === v.id ? "bg-[#E7F7EC] ring-1 ring-[#9BD8B0]" : "bg-[#F7F8FA]"}`}
                  data-testid={`lp-ab-row-${v.id}`}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-[12px] font-bold text-[#1C1C1E]">
                      {report.winner === v.id ? <Trophy size={11} className="mr-1 inline text-[#12703A]" /> : null}
                      {v.id} · {v.name}
                    </p>
                    <p className="shrink-0 text-[12px] font-bold tabular-nums text-[#1C1C1E]">
                      {pct(report.goal === "lead" ? v.lead_rate : v.cta_rate)}
                    </p>
                  </div>
                  <p className="mt-0.5 text-[10.5px] tabular-nums text-[#6B6B73]">
                    {v.views} tampilan · {v.cta_clicks} klik · {v.leads} lead
                  </p>
                </div>
              ))}
              <p className={`text-[11px] ${report.winner ? "font-semibold text-[#12703A]" : "text-[#8E8E93]"}`}
                data-testid="lp-ab-verdict">
                {report.winner_reason}
                {report.winner && report.uplift_percent ? ` Selisih ${report.uplift_percent}%.` : ""}
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

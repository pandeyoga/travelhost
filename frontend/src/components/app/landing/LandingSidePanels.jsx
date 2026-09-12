import { Palette, Search as SearchIcon, Users, Target, CheckCircle2, AlertTriangle, Copy,
  Megaphone, ImageOff } from "lucide-react";
import { toast } from "sonner";
import { Switch } from "@/components/ui/switch";
import SelectField from "@/components/shared/SelectField";
import { formatDateTime } from "@/utils/formatters";

/**
 * LandingSidePanels.jsx — panel pendukung editor: tema, SEO, dan lead yang masuk dari halaman ini.
 *
 * Panel SEO bukan pelengkap: `publish_errors` (INV-LP-01) MENOLAK penerbitan bila judul SEO kosong,
 * karena judul & deskripsi itulah yang tampil di pratinjau tautan saat iklan dibagikan. Panel lead
 * ada di sini supaya penyusun halaman melihat hasil nyata (nama & nomor yang masuk), bukan hanya
 * angka agregat.
 */
export function ThemePanel({ theme, presets, onChange }) {
  const t = theme || {};
  const set = (k, v) => onChange({ ...t, [k]: v });
  return (
    <section className="section-card" data-testid="lp-theme-panel">
      <div className="section-head">
        <h2 className="flex items-center gap-2 text-[13px]"><Palette size={14} /> Warna &amp; Gaya</h2>
      </div>
      <div className="section-body space-y-2.5">
        <SelectField value={t.preset || "biru-laut"} testId="lp-theme-preset" className="w-full"
          onChange={(v) => onChange({ ...t, preset: v, ...(presets[v] || {}) })}
          options={Object.keys(presets || {}).map((k) => ({ value: k, label: `Preset: ${k.replace(/-/g, " ")}` }))} />
        {[["primary", "Warna utama"], ["accent", "Warna tombol aksi"], ["text", "Warna teks"],
          ["bg", "Warna latar"]].map(([k, label]) => (
          <div key={k} className="flex items-center justify-between gap-2">
            <span className="text-[12px] text-[#3a3f4a]">{label}</span>
            <div className="flex items-center gap-1.5">
              <span className="text-[10.5px] uppercase tabular-nums text-[#8E8E93]">{t[k] || "—"}</span>
              <input type="color" value={t[k] || "#0B7BD3"} data-testid={`lp-color-${k}`}
                onChange={(e) => set(k, e.target.value)} aria-label={label}
                className="h-8 w-12 cursor-pointer rounded border border-[#E5E5EA] bg-white" />
            </div>
          </div>
        ))}
        <SelectField value={t.button_shape || "rounded"} testId="lp-btn-shape" className="w-full"
          onChange={(v) => set("button_shape", v)}
          options={[{ value: "rounded", label: "Tombol sudut membulat" }, { value: "pill", label: "Tombol bentuk pil" }]} />
        <div className="space-y-1">
          <label className="text-[11.5px] font-semibold text-[#3a3f4a]" htmlFor="lp-radius">
            Kelengkungan sudut kartu ({t.radius ?? 16}px)
          </label>
          <input id="lp-radius" type="range" min="0" max="32" value={t.radius ?? 16}
            onChange={(e) => set("radius", Number(e.target.value))} data-testid="lp-theme-radius"
            className="w-full accent-[#007AFF]" />
        </div>
        <div className="space-y-1">
          <label className="text-[11.5px] font-semibold text-[#3a3f4a]" htmlFor="lp-font">
            Skala huruf ({t.font_scale ?? 100}%)
          </label>
          <input id="lp-font" type="range" min="85" max="120" value={t.font_scale ?? 100}
            onChange={(e) => set("font_scale", Number(e.target.value))} data-testid="lp-theme-font"
            className="w-full accent-[#007AFF]" />
        </div>
      </div>
    </section>
  );
}

export function SeoPanel({ seo, tracking, slug, onSeo, onTracking }) {
  const s = seo || {};
  const tr = tracking || {};
  const titleLeft = 60 - String(s.title || "").length;
  const descLeft = 160 - String(s.description || "").length;
  return (
    <section className="section-card" data-testid="lp-seo-panel">
      <div className="section-head">
        <h2 className="flex items-center gap-2 text-[13px]"><SearchIcon size={14} /> SEO &amp; Pratinjau Tautan</h2>
      </div>
      <div className="section-body space-y-2.5">
        <div className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-2.5">
          <p className="truncate text-[11px] text-[#12703A]">rahazatrans.id/lp/{slug}</p>
          <p className="mt-0.5 truncate text-[13px] font-semibold text-[#1A0DAB]">
            {s.title || "Judul untuk hasil pencarian"}
          </p>
          <p className="mt-0.5 line-clamp-2 text-[11.5px] text-[#4D5156]">
            {s.description || "Deskripsi singkat yang muncul di bawah judul saat tautan dibagikan."}
          </p>
        </div>
        <div className="space-y-1">
          <label className="text-[11.5px] font-semibold text-[#3a3f4a]" htmlFor="lp-seo-title">
            Judul SEO <span className="font-normal text-[#8E8E93]">(wajib untuk terbit)</span>
          </label>
          <input id="lp-seo-title" value={s.title || ""} data-testid="lp-seo-title"
            onChange={(e) => onSeo({ ...s, title: e.target.value })}
            className="h-8 w-full rounded-lg border border-[#E5E5EA] bg-white px-2.5 text-[12.5px] outline-none focus:border-[#007AFF]" />
          <p className={`text-[10.5px] ${titleLeft < 0 ? "font-semibold text-[#C2261C]" : "text-[#8E8E93]"}`}>
            {titleLeft < 0 ? `${-titleLeft} karakter melebihi batas nyaman (60).` : `${titleLeft} karakter tersisa.`}
          </p>
        </div>
        <div className="space-y-1">
          <label className="text-[11.5px] font-semibold text-[#3a3f4a]" htmlFor="lp-seo-desc">Deskripsi SEO</label>
          <textarea id="lp-seo-desc" rows={2} value={s.description || ""} data-testid="lp-seo-desc"
            onChange={(e) => onSeo({ ...s, description: e.target.value })}
            className="w-full rounded-lg border border-[#E5E5EA] bg-white px-2.5 py-1.5 text-[12.5px] outline-none focus:border-[#007AFF]" />
          <p className={`text-[10.5px] ${descLeft < 0 ? "font-semibold text-[#C2261C]" : "text-[#8E8E93]"}`}>
            {descLeft < 0 ? `${-descLeft} karakter melebihi batas nyaman (160).` : `${descLeft} karakter tersisa.`}
          </p>
        </div>
        <div className="space-y-1">
          <label className="text-[11.5px] font-semibold text-[#3a3f4a]" htmlFor="lp-seo-og">
            Gambar pratinjau tautan (URL)
          </label>
          <input id="lp-seo-og" value={s.og_image || ""} data-testid="lp-seo-og"
            placeholder="https://… atau /api/public/media/…"
            onChange={(e) => onSeo({ ...s, og_image: e.target.value })}
            className="h-8 w-full rounded-lg border border-[#E5E5EA] bg-white px-2.5 text-[12.5px] outline-none focus:border-[#007AFF]" />
        </div>
        <div className="flex items-start justify-between gap-2 rounded-lg bg-[#F7F8FA] px-2.5 py-2">
          <div className="min-w-0">
            <p className="text-[12px] font-semibold text-[#3a3f4a]">Sembunyikan dari Google (noindex)</p>
            <p className="text-[10.5px] text-[#8E8E93]">
              Disarankan AKTIF untuk halaman iklan berbayar agar tidak berebut kata kunci dengan
              halaman utama. Matikan bila halaman ini juga dikejar secara organik (otomatis masuk sitemap).
            </p>
          </div>
          <Switch checked={s.noindex !== false} data-testid="lp-seo-noindex"
            onCheckedChange={(v) => onSeo({ ...s, noindex: v })} />
        </div>
        <div className="space-y-1 border-t border-[#F0F1F3] pt-2.5">
          <label className="text-[11.5px] font-semibold text-[#3a3f4a]" htmlFor="lp-utm">
            UTM bawaan untuk tautan iklan
          </label>
          <input id="lp-utm" value={tr.utm_default || ""} data-testid="lp-tracking-utm"
            placeholder="utm_source=google&utm_medium=cpc"
            onChange={(e) => onTracking({ ...tr, utm_default: e.target.value })}
            className="h-8 w-full rounded-lg border border-[#E5E5EA] bg-white px-2.5 text-[12.5px] outline-none focus:border-[#007AFF]" />
          <p className="text-[10.5px] text-[#8E8E93]">
            Catatan untuk tim: parameter ini yang ditempel di URL iklan agar lead terhubung ke kampanye.
          </p>
        </div>
      </div>
    </section>
  );
}

export function PageLeadsPanel({ leads, loading }) {
  return (
    <section className="section-card" data-testid="lp-leads-panel">
      <div className="section-head">
        <h2 className="flex items-center gap-2 text-[13px]"><Users size={14} /> Lead dari halaman ini</h2>
      </div>
      <div className="section-body">
        {loading ? (
          <div className="space-y-1.5" data-testid="lp-leads-loading">
            {[0, 1, 2].map((i) => <div key={i} className="h-10 animate-pulse rounded bg-[#EEF1F5]" />)}
          </div>
        ) : !leads?.length ? (
          <p className="text-[11.5px] text-[#8E8E93]" data-testid="lp-leads-empty">
            Belum ada lead dari halaman ini. Lead akan muncul di sini dan di menu CRM.
          </p>
        ) : (
          <div className="max-h-[220px] divide-y divide-[#F0F1F3] overflow-y-auto" data-testid="lp-leads-list">
            {leads.map((l) => (
              <div key={l.id} className="py-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-[12.5px] font-semibold text-[#1C1C1E]">{l.customer_name}</p>
                  <span className="shrink-0 rounded-full bg-[#F2F2F5] px-2 py-0.5 text-[10px] font-bold uppercase text-[#6B6B73]">
                    {l.landing_variant || "A"}
                  </span>
                </div>
                <p className="mt-0.5 truncate text-[11px] text-[#8E8E93]">
                  {l.phone}{l.destination ? ` · ${l.destination}` : ""}
                  {l.utm_campaign ? ` · ${l.utm_campaign}` : ""} · {formatDateTime(l.created_at)}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

/**
 * AdReadinessPanel — skor kesiapan iklan + pemulih media + URL iklan siap pakai.
 *
 * Dibuat karena urutan kejadian yang paling merugikan di iklan berbayar adalah: halaman dipasang
 * sebagai tujuan iklan → iklan tayang → baru ketahuan formulirnya belum ada / gambarnya hilang /
 * halamannya masih draf. Semua itu terlihat di sini SEBELUM uang dibelanjakan.
 */
export function AdReadinessPanel({ report, loading, onRefresh, onUseForAds, onOpenMedia }) {
  const level = report?.level;
  const tone = level === "siap" ? { bg: "#E7F7EC", fg: "#12703A" }
    : level === "hampir" ? { bg: "#FFF8EC", fg: "#8A5300" }
    : { bg: "#FDF2F1", fg: "#C2261C" };
  const copyUrl = (url) => {
    const abs = `${window.location.origin}${url}`;
    try { navigator.clipboard.writeText(abs); toast.success("URL iklan disalin"); }
    catch (e) { window.prompt("Salin URL iklan:", abs); }
  };
  return (
    <section className="section-card" data-testid="lp-readiness-panel">
      <div className="section-head flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-[13px]"><Target size={14} /> Kesiapan Iklan</h2>
        <button type="button" className="secondary-button !h-7" onClick={onRefresh} data-testid="lp-readiness-refresh">
          Periksa ulang
        </button>
      </div>
      <div className="section-body space-y-2.5">
        {loading && !report ? (
          <div className="space-y-1.5" data-testid="lp-readiness-loading">
            {[0, 1, 2].map((i) => <div key={i} className="h-8 animate-pulse rounded bg-[#EEF1F5]" />)}
          </div>
        ) : !report ? (
          <p className="text-[11.5px] text-[#8E8E93]" data-testid="lp-readiness-empty">
            Belum ada hasil pemeriksaan. Tekan “Periksa ulang”.
          </p>
        ) : (
          <>
            <div className="rounded-lg px-2.5 py-2" style={{ background: tone.bg }}>
              <div className="flex items-center justify-between gap-2">
                <p className="text-[12px] font-bold uppercase tracking-wide" style={{ color: tone.fg }}>
                  {level === "siap" ? "Siap diiklankan" : level === "hampir" ? "Hampir siap" : "Belum siap"}
                </p>
                <p className="text-[16px] font-extrabold tabular-nums" style={{ color: tone.fg }}>
                  {report.score}/100
                </p>
              </div>
              <p className="mt-0.5 text-[11.5px]" style={{ color: tone.fg }}>{report.verdict}</p>
            </div>

            {(report.missing_media || []).length ? (
              <div className="rounded-lg bg-[#FDF2F1] p-2.5" data-testid="lp-missing-media">
                <p className="flex items-center gap-1.5 text-[11.5px] font-bold text-[#C2261C]">
                  <ImageOff size={12} /> {report.missing_media.length} media hilang
                </p>
                <ul className="mt-1 space-y-0.5">
                  {report.missing_media.map((m) => (
                    <li key={m.media_id} className="text-[11px] text-[#8A3A33]">
                      {m.filename} — {m.reason}
                    </li>
                  ))}
                </ul>
                <button type="button" className="secondary-button !h-7 mt-1.5 w-full"
                  onClick={onOpenMedia} data-testid="lp-missing-media-fix">
                  Unggah ulang di Media Library
                </button>
              </div>
            ) : null}

            <ul className="space-y-1" data-testid="lp-readiness-checks">
              {(report.checks || []).map((c, i) => (
                <li key={i} className="flex items-start gap-1.5 text-[11.5px]">
                  {c.ok ? <CheckCircle2 size={12} className="mt-0.5 shrink-0 text-[#12703A]" />
                    : <AlertTriangle size={12} className="mt-0.5 shrink-0 text-[#C2261C]" />}
                  <span className={c.ok ? "text-[#6B6B73]" : "text-[#1C1C1E]"}>
                    {c.ok ? c.label : c.fix}
                  </span>
                </li>
              ))}
            </ul>

            <div className="space-y-1.5 border-t border-[#F0F1F3] pt-2.5">
              <p className="text-[11.5px] font-semibold text-[#3a3f4a]">URL iklan siap pakai (UTM otomatis)</p>
              {Object.entries(report.ad_urls || {}).map(([prov, url]) => (
                <button key={prov} type="button" onClick={() => copyUrl(url)}
                  data-testid={`lp-adurl-${prov}`}
                  className="flex w-full items-center justify-between gap-2 rounded-lg bg-[#F7F8FA] px-2.5 py-1.5 text-left hover:bg-[#EFF3F8]">
                  <span className="min-w-0 flex-1 truncate text-[11px] text-[#3a3f4a]">{url}</span>
                  <Copy size={11} className="shrink-0 text-[#6B6B73]" />
                </button>
              ))}
            </div>

            <button type="button" className="primary-button !h-9 w-full" onClick={onUseForAds}
              data-testid="lp-use-for-ads">
              <Megaphone size={13} /> Pakai halaman ini untuk iklan
            </button>
          </>
        )}
      </div>
    </section>
  );
}

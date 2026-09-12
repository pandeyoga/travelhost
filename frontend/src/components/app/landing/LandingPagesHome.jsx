import { LayoutTemplate, Eye, Trash2, Copy, Plus, Search, FlaskConical, Images } from "lucide-react";
import SelectField from "@/components/shared/SelectField";
import { EmptyState } from "@/components/shared/DataStates";
import { formatDateTime } from "@/utils/formatters";

/**
 * LandingPagesHome.jsx — beranda Landing Page Builder: galeri template + daftar halaman.
 *
 * Daftar halaman sengaja menampilkan ANGKA (tampilan / klik / lead), bukan hanya nama & tanggal.
 * Halaman iklan adalah tempat uang iklan mendarat; pertanyaan pertama pemilik selalu "halaman mana
 * yang menghasilkan?", dan jawabannya harus terlihat tanpa membuka halaman satu per satu.
 */
const SEGMENTS = [
  { value: "", label: "Semua segmen" },
  { value: "armada", label: "Segmen: Armada" },
  { value: "destinasi", label: "Segmen: Destinasi" },
];
const STATUSES = [
  { value: "", label: "Semua status" },
  { value: "published", label: "Sudah terbit" },
  { value: "draft", label: "Masih draf" },
];

export default function LandingPagesHome({
  pages, templates, filters, onFilter, busy, loading, onCreate, onOpen, onDuplicate, onDelete, onOpenMedia,
}) {
  const armada = templates.filter((t) => t.segment === "armada");
  const destinasi = templates.filter((t) => t.segment === "destinasi");

  const card = (t) => (
    <button key={t.key} type="button" onClick={() => onCreate(t.key)} disabled={busy === "create"}
      data-testid={`lp-template-${t.key}`}
      className="rounded-xl border border-[#E5E5EA] bg-white p-3.5 text-left transition-colors hover:border-[#007AFF] disabled:opacity-60">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[13.5px] font-bold text-[#1C1C1E]">{t.name}</p>
        <span className="shrink-0 rounded-full bg-[#F2F2F5] px-2 py-0.5 text-[10.5px] font-bold uppercase text-[#6B6B73]">
          {t.blocks} blok
        </span>
      </div>
      <p className="mt-1 text-[12px] leading-relaxed text-[#6B6B73]">{t.description}</p>
      {t.highlights?.length ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {t.highlights.map((h) => (
            <span key={h} className="rounded-full bg-[#F7F8FA] px-2 py-0.5 text-[10px] font-semibold text-[#6B6B73]">{h}</span>
          ))}
        </div>
      ) : null}
      <span className="mt-2.5 inline-flex items-center gap-1 text-[11.5px] font-bold text-[#007AFF]">
        <Plus size={11} /> Pakai template ini
      </span>
    </button>
  );

  return (
    <div className="space-y-4" data-testid="landing-page">
      <section className="section-card">
        <div className="section-head flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="flex items-center gap-2"><LayoutTemplate size={15} /> Template per Segmen Iklan</h2>
            <p className="mt-0.5 text-[12px] font-normal text-[#6B6B73]">
              Pilih titik awal. Semua teks, tombol, warna, foto &amp; video bisa diubah setelahnya.
            </p>
          </div>
          <button type="button" className="secondary-button" onClick={onOpenMedia} data-testid="lp-open-media">
            <Images size={14} /> Kelola Media
          </button>
        </div>
        <div className="section-body space-y-3">
          <div>
            <p className="mb-2 text-[11.5px] font-bold uppercase tracking-wide text-[#8E8E93]">
              Segmen Armada · orang mencari unit
            </p>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">{armada.map(card)}</div>
          </div>
          <div>
            <p className="mb-2 text-[11.5px] font-bold uppercase tracking-wide text-[#8E8E93]">
              Segmen Destinasi · orang mencari pengalaman
            </p>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">{destinasi.map(card)}</div>
          </div>
        </div>
      </section>

      <section className="section-card">
        <div className="section-head flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2"><Eye size={15} /> Halaman Anda</h2>
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative w-[180px]">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#8E8E93]" />
              <input value={filters.q} onChange={(e) => onFilter({ ...filters, q: e.target.value })}
                placeholder="Cari judul / slug…" data-testid="lp-search"
                className="h-9 w-full rounded-lg border border-[#E5E5EA] bg-white pl-8 pr-2.5 text-[12.5px] outline-none focus:border-[#007AFF]" />
            </div>
            <div className="w-[150px]">
              <SelectField value={filters.segment} onChange={(v) => onFilter({ ...filters, segment: v })}
                options={SEGMENTS} testId="lp-filter-segment" className="w-full" />
            </div>
            <div className="w-[140px]">
              <SelectField value={filters.status} onChange={(v) => onFilter({ ...filters, status: v })}
                options={STATUSES} testId="lp-filter-status" className="w-full" />
            </div>
          </div>
        </div>
        <div className="section-body">
          {loading ? (
            <div className="space-y-2" data-testid="lp-list-loading">
              {[0, 1, 2].map((i) => <div key={i} className="h-14 animate-pulse rounded-lg bg-[#EEF1F5]" />)}
            </div>
          ) : !pages.length ? (
            <EmptyState title="Belum ada halaman iklan" testId="lp-empty"
              description="Pilih salah satu template di atas untuk mulai membuat halaman tujuan iklan." />
          ) : (
            <div className="divide-y divide-[#F0F1F3]" data-testid="lp-list">
              {pages.map((p) => (
                <div key={p.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div className="min-w-[220px] flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <p className="text-[13.5px] font-semibold text-[#1C1C1E]">{p.title}</p>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                        p.status === "published" ? "bg-[#E7F7EC] text-[#12703A]" : "bg-[#F2F2F5] text-[#6B6B73]"}`}>
                        {p.status === "published" ? "Terbit" : "Draf"}
                      </span>
                      {p.ab_enabled ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-[#EEF3FF] px-2 py-0.5 text-[10px] font-bold uppercase text-[#2B4FCB]">
                          <FlaskConical size={9} /> A/B
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-0.5 text-[11.5px] text-[#8E8E93]">
                      /lp/{p.slug} · {p.segment} · diperbarui {formatDateTime(p.updated_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 text-center">
                    {[["Tampilan", p.stats?.views], ["Klik", p.stats?.cta_clicks], ["Lead", p.stats?.leads]]
                      .map(([label, value]) => (
                        <div key={label} className="min-w-[52px]">
                          <p className="text-[14px] font-bold tabular-nums text-[#1C1C1E]">{value ?? 0}</p>
                          <p className="text-[9.5px] font-semibold uppercase tracking-wide text-[#8E8E93]">{label}</p>
                        </div>
                      ))}
                  </div>
                  <div className="flex items-center gap-2">
                    {p.status === "published" ? (
                      <a className="secondary-button !h-8" href={`/lp/${p.slug}`} target="_blank" rel="noreferrer"
                        data-testid={`lp-visit-${p.id}`}><Eye size={13} /> Lihat</a>
                    ) : null}
                    <button type="button" className="secondary-button !h-8" onClick={() => onOpen(p.id)}
                      data-testid={`lp-edit-${p.id}`}>Edit</button>
                    <button type="button" className="icon-button !h-8 !w-8" aria-label="Duplikat halaman"
                      onClick={() => onDuplicate(p.id)} data-testid={`lp-duplicate-${p.id}`}>
                      <Copy size={13} />
                    </button>
                    <button type="button" className="icon-button !h-8 !w-8" aria-label="Hapus halaman"
                      onClick={() => onDelete(p)} data-testid={`lp-delete-${p.id}`}>
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

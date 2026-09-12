import { HeroMedia, SearchHero } from "@/components/app/landing/blocks/HeroBlocks";
import { CtaBand, LeadForm, PriceEstimator, WaCta } from "@/components/app/landing/blocks/ConversionBlocks";
import { Countdown, Faq, Gallery, RichText, TrustBadges, ValueProps, VideoBlock }
  from "@/components/app/landing/blocks/ContentBlocks";
import { DestinationGrid, FleetGrid, RouteGrid, Testimonials } from "@/components/app/landing/blocks/EntityBlocks";
import { themeOf } from "@/components/app/landing/shared";

/**
 * LandingRender.jsx — SATU renderer dipakai dua tempat: pratinjau di editor (`mode="preview"`)
 * dan halaman publik `/lp/:slug` (`mode="public"`). Alasan: apa yang dilihat marketing admin
 * saat menyusun = apa yang dilihat pengunjung iklan (tidak ada kejutan setelah terbit).
 *
 * Berkas ini SENGAJA hanya berisi pengiriman blok (switch). Implementasi tiap blok ada di
 * `blocks/*` agar setiap file tetap kecil & mudah ditinjau — dan agar penambahan blok baru
 * memaksa penambahan `case` di sini (dijaga guardrail INV-LP-02: blok tanpa `case` berarti
 * blok bisa ditambahkan di editor tetapi menghasilkan area KOSONG di halaman iklan).
 *
 * Perbedaan mode:
 *  - preview: formulir & kalkulator tampil penuh tapi tidak mengirim data / berpindah halaman.
 *  - public : semua interaksi nyata (lead tersimpan, atribusi iklan diteruskan).
 */
export default function LandingRender({
  page,
  fleet = [],
  destinations = [],
  routes = [],
  testimonials = [],
  refsLoading = false,
  loading = false,
  mode = "public",
  onCta,
  onSearch,
  onLeadSubmit,
}) {
  const theme = themeOf(page);
  const blocks = (page?.blocks || []).filter((b) => !b.hidden);
  const go = (cta) => onCta?.(cta);

  if (loading) {
    return (
      <div className="space-y-3 p-6" data-testid="lp-render-loading">
        {[0, 1, 2].map((i) => <div key={i} className="h-24 animate-pulse rounded-xl bg-[#EEF1F5]" />)}
      </div>
    );
  }
  if (!blocks.length) {
    return (
      <p className="p-8 text-center text-[13px] text-[#6B7280]" data-testid="lp-render-empty">
        Belum ada blok pada halaman ini. Tambahkan blok dari panel kiri.
      </p>
    );
  }

  return (
    <div data-testid="lp-render" style={{ fontSize: `${theme.font_scale || 100}%`, background: theme.bg }}>
      {/* Halaman publik: bila blok pertama BUKAN hero, sediakan bilah warna merek setinggi header
          agar logo & tombol di header (yang transparan di puncak) tetap terbaca. */}
      {mode === "public" && !["search_hero", "hero_media"].includes(blocks[0]?.type) ? (
        <div style={{ height: 92, background: theme.primary }} data-testid="lp-header-spacer" />
      ) : null}
      {blocks.map((b, index) => {
        const p = b.props || {};
        switch (b.type) {
          case "search_hero":
            return <SearchHero key={b.id} p={p} theme={theme} mode={mode} first={index === 0}
              onSearch={(values, tab, cta) => onSearch?.(values, tab, cta || p.cta)} />;
          case "hero_media":
            return <HeroMedia key={b.id} p={p} theme={theme} mode={mode} first={index === 0} onCta={go} />;
          case "value_props":
            return <ValueProps key={b.id} p={p} theme={theme} />;
          case "fleet_grid":
            return <FleetGrid key={b.id} p={p} theme={theme} fleet={fleet} loading={refsLoading} onCta={go} />;
          case "destination_grid":
            return <DestinationGrid key={b.id} p={p} theme={theme} destinations={destinations}
              loading={refsLoading} onCta={go} />;
          case "route_grid":
            return <RouteGrid key={b.id} p={p} theme={theme} routes={routes}
              loading={refsLoading} onCta={go} />;
          case "gallery":
            return <Gallery key={b.id} p={p} theme={theme} />;
          case "video":
            return <VideoBlock key={b.id} p={p} theme={theme} />;
          case "testimonials":
            return <Testimonials key={b.id} p={p} theme={theme} testimonials={testimonials} loading={refsLoading} />;
          case "price_estimator":
            return <PriceEstimator key={b.id} p={p} theme={theme} mode={mode} fleet={fleet} />;
          case "faq":
            return <Faq key={b.id} p={p} theme={theme} />;
          case "cta_band":
            return <CtaBand key={b.id} p={p} theme={theme} onCta={go} />;
          case "wa_cta":
            return <WaCta key={b.id} p={p} theme={theme} onCta={go} />;
          case "lead_form":
            return <LeadForm key={b.id} p={p} theme={theme} mode={mode} fleet={fleet}
              onSubmit={(values) => onLeadSubmit?.(values, b.id)} />;
          case "countdown":
            return <Countdown key={b.id} p={p} theme={theme} />;
          case "trust_badges":
            return <TrustBadges key={b.id} p={p} theme={theme} />;
          case "rich_text":
            return <RichText key={b.id} p={p} theme={theme} />;
          case "spacer":
            return <div key={b.id} style={{ height: p.size || 32, background: theme.bg }} data-testid="lp-spacer" />;
          default:
            return <div key={b.id} style={{ height: 24, background: theme.bg }} />;
        }
      })}
    </div>
  );
}

import { Sparkles, CalendarRange, Map, Route } from "lucide-react";
import SectionHeading from "@/components/public/SectionHeading";
import Reveal from "@/components/public/Reveal";
import GlassCard from "@/components/public/GlassCard";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

// DestinationFacts.jsx — "fun fact" wisata yang DITURUNKAN dari data destinasi.
//
// Aturan yang dipegang (design_guidelines: "fun fact harus berasal dari highlight/itinerary/
// best_time; jangan bikin fakta baru"): tidak ada satu pun kalimat fakta yang dikarang di
// frontend. Semua isi kartu diambil dari `GET /api/public/destinations` — `highlights[]`,
// `best_time`, dan jumlah tahap `itinerary[]` — sehingga saat pemilik menyunting konten di
// CMS, section ini ikut berubah dan tidak pernah berbohong.
const REGION_LABEL = {
  bali: "Bali",
  jawa_timur: "Jawa Timur",
  jawa_tengah: "Jawa Tengah",
  jawa_barat: "Jawa Barat",
};

export default function DestinationFacts({ destinations, loading, limit = 6 }) {
  const lang = useLangValue();
  const all = Array.isArray(destinations) ? destinations : [];

  // Destinasi populer didahulukan; tiap destinasi menyumbang 1 fakta terkuat (highlight #1).
  const ordered = [...all].sort((a, b) => Number(Boolean(b.popular)) - Number(Boolean(a.popular)));
  const facts = ordered
    .map((d) => {
      const hl = (Array.isArray(d.highlights) ? d.highlights : [])[0];
      const days = Array.isArray(d.itinerary) ? d.itinerary.length : 0;
      if (!hl && !d.best_time && !days) return null;
      return {
        slug: d.slug,
        name: d.name,
        region: REGION_LABEL[d.region] || d.region,
        title: hl?.title || d.name,
        desc: hl?.desc || d.description,
        bestTime: d.best_time,
        days,
      };
    })
    .filter(Boolean)
    .slice(0, limit);

  return (
    <section className="section-tint relative overflow-hidden" data-testid="destination-facts">
      <div className="glow-orb h-72 w-72 -left-16 top-12" style={{ background: "hsla(var(--ring) / 0.12)" }} aria-hidden="true" />
      <div className="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <SectionHeading
          eyebrow={bi("Tahukah Anda", "Did you know", lang)}
          title={bi("Fakta singkat sebelum memilih tujuan", "Quick facts before picking a destination", lang)}
          subtitle={bi("Dirangkum dari panduan tiap destinasi — termasuk waktu terbaik berkunjung dan lama perjalanan yang kami sarankan.", "Summarised from each destination guide — including the best time to visit and the trip length we recommend.", lang)}
        />

        {loading ? (
          <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3" data-testid="dfact-loading">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-44 animate-pulse rounded-2xl bg-muted" data-testid="dfact-skeleton" />
            ))}
          </div>
        ) : facts.length === 0 ? (
          <p className="mt-10 rounded-2xl border border-dashed border-border bg-card px-5 py-10 text-center text-[13.5px] text-muted-foreground" data-testid="dfact-empty">
            {bi("Belum ada panduan destinasi yang bisa dirangkum.", "No destination guides to summarise yet.", lang)}
          </p>
        ) : (
          <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3" data-testid="dfact-grid">
            {facts.map((f, i) => (
              <Reveal key={f.slug} delay={i * 0.06}>
                <GlassCard variant="premium" className="flex h-full flex-col p-6" data-testid={`dfact-item-${f.slug}`}>
                  <div className="flex items-center justify-between gap-3">
                    <span className="icon-chip h-11 w-11 shrink-0"><Sparkles size={18} strokeWidth={1.8} /></span>
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2.5 py-1 text-[11px] font-semibold text-secondary-foreground">
                      <Map size={12} /> {f.region}
                    </span>
                  </div>
                  <p className="mt-4 text-[11px] font-semibold uppercase tracking-wider text-primary">{f.name}</p>
                  <h3 className="mt-1 font-fraunces text-lg leading-snug text-foreground">{f.title}</h3>
                  <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">{f.desc}</p>
                  <div className="mt-auto flex flex-wrap gap-2 pt-5 text-[11.5px] font-medium">
                    {f.bestTime ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2.5 py-1 text-secondary-foreground" data-testid={`dfact-besttime-${f.slug}`}>
                        <CalendarRange size={12} /> {f.bestTime}
                      </span>
                    ) : null}
                    {f.days ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2.5 py-1 tabular-nums text-secondary-foreground">
                        <Route size={12} /> {bi(`Saran ${f.days} tahap perjalanan`, `Suggested ${f.days} trip stages`, lang)}
                      </span>
                    ) : null}
                  </div>
                </GlassCard>
              </Reveal>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

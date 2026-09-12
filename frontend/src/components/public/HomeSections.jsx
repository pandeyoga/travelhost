import { Link } from "react-router-dom";
import {
  ArrowRight, ShieldCheck, MapPin, Headset, Star, Bus, BadgeCheck,
  Wrench, Navigation, Calculator, Globe2, Clock, Quote, Sparkles, Check,
} from "lucide-react";
import { bi, t as tr } from "@/lib/i18n";
import { ov } from "@/hooks/useSitePage";
import ParallaxHero from "@/components/public/ParallaxHero";
import TripEstimatorInline from "@/components/public/TripEstimatorInline";
import { useSiteFeatures } from "@/hooks/useSiteFeatures";
import Reveal from "@/components/public/Reveal";
import GlassCard from "@/components/public/GlassCard";
import SectionHeading from "@/components/public/SectionHeading";
import StatCounter from "@/components/public/StatCounter";
import FleetCard from "@/components/public/FleetCard";
import DestCard from "@/components/public/DestCard";
import BookingStepsSection from "@/components/public/BookingStepsSection";
import PhotoGalleryGrid from "@/components/public/PhotoGalleryGrid";
import {
  Accordion, AccordionItem, AccordionTrigger, AccordionContent,
} from "@/components/ui/accordion";

// Section beranda yang bisa diatur dari CMS Page Builder (urutan, aktif/nonaktif, override
// teks & gambar). Override kosong = teks bawaan dua-bahasa di bawah tetap dipakai.
export const HOME_HERO_DEFAULT = "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?q=80&w=2000&auto=format&fit=crop";

const VALUE_ICONS = [ShieldCheck, MapPin, Headset];
const STAT_ICONS = { fleet: Bus, destinations: Globe2, rating: Star, service: Clock };
const TRUST_ICONS = [BadgeCheck, ShieldCheck, Wrench, Navigation];

function defaultValueProps(lang) {
  return [
    { tag: bi("Kelaikan terjaga", "Always roadworthy", lang), title: bi("Armada Terawat", "Well-Maintained Fleet", lang), text: bi("KIR, pajak, dan servis terjadwal. Setiap unit dipantau kelaikannya sebelum jalan.", "Inspection, taxes and scheduled servicing. Every unit's roadworthiness is checked before it departs.", lang) },
    { tag: bi("GPS live", "Live GPS", lang), title: bi("Pelacakan Real-time", "Real-time Tracking", lang), text: bi("Pantau posisi & estimasi tiba perjalanan Anda langsung dari peta, kapan saja.", "Track your trip's position & ETA straight from the map, anytime.", lang) },
    { tag: bi("Support 24/7", "24/7 support", lang), title: bi("Layanan Responsif", "Responsive Service", lang), text: bi("Tim operasional siap membantu penawaran, penjadwalan, dan kebutuhan trip Anda.", "Our operations team is ready to help with quotes, scheduling and your trip needs.", lang) },
  ];
}

function defaultTrust(lang) {
  return [
    { title: bi("Sertifikasi CHSE", "CHSE Certified", lang), text: bi("Protokol kebersihan & keselamatan", "Cleanliness & safety protocols", lang) },
    { title: bi("KIR & Pajak Aktif", "Valid Inspection & Tax", lang), text: bi("Legalitas unit selalu diperbarui", "Vehicle legality always up to date", lang) },
    { title: bi("Servis Terjadwal", "Scheduled Servicing", lang), text: bi("Perawatan berkala tiap armada", "Regular maintenance for every unit", lang) },
    { title: bi("GPS Tracking", "GPS Tracking", lang), text: bi("Pelacakan rute & ETA real-time", "Real-time route & ETA tracking", lang) },
  ];
}

function defaultFaqs(lang) {
  return [
    { q: bi("Apa saja yang termasuk dalam harga sewa?", "What's included in the rental price?", lang), a: bi("Harga mencakup unit armada, driver berpengalaman, dan fee operasional dasar. Komponen BBM, tol, dan parkir dihitung sesuai rute pada estimasi.", "The price covers the vehicle, an experienced driver and basic operational fees. Fuel, tolls and parking are calculated by route in the estimate.", lang) },
    { q: bi("Bagaimana cara memesan armada?", "How do I book a vehicle?", lang), a: bi("Hitung estimasi di halaman ini atau di Kalkulator, lalu klik Minta Penawaran. Tim kami akan mengirim penawaran final & konfirmasi ketersediaan via WhatsApp.", "Estimate the cost on this page or the Calculator, then click Request a Quote. Our team sends the final offer & confirms availability via WhatsApp.", lang) },
    { q: bi("Apakah tersedia pelacakan perjalanan?", "Is trip tracking available?", lang), a: bi("Ya. Untuk perjalanan korporat kami sediakan tautan pelacakan real-time sehingga posisi dan estimasi tiba dapat dipantau.", "Yes. For corporate trips we provide a real-time tracking link so position and ETA can be monitored.", lang) },
    { q: bi("Area layanan mana saja?", "Which areas do you serve?", lang), a: bi("Kami berbasis di Bandung dan melayani perjalanan ke seluruh Jawa hingga Bali, untuk keluarga, korporat, maupun institusi.", "We're based in Bandung and serve trips across Java to Bali — for families, companies and institutions.", lang) },
  ];
}

function Stars({ n = 5 }) {
  const rating = Math.min(5, Math.max(0, Number(n) || 0));
  return (
    <span className="inline-flex items-center gap-0.5">
      {Array.from({ length: 5 }).map((_, i) => (
        <Star key={i} size={16} className={i < Math.round(rating) ? "fill-amber-400 text-amber-400 drop-shadow-[0_1px_2px_rgba(245,158,11,0.35)]" : "text-border"} />
      ))}
      <span className="ml-1.5 font-mono text-[12px] font-semibold tabular-nums text-muted-foreground">{rating.toFixed(1)}</span>
    </span>
  );
}

function HeroSection({ lang, d }) {
  const { tripCalculator } = useSiteFeatures();
  const chips = ov(d, "chips", [bi("Driver berpengalaman", "Experienced drivers", lang), bi("CHSE / KIR", "CHSE / inspection", lang), bi("Harga transparan", "Transparent pricing", lang)]);
  return (
    <ParallaxHero image={ov(d, "image", HOME_HERO_DEFAULT)}>
      <div className="grid grid-cols-1 items-center gap-10 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/10 px-3.5 py-1.5 text-[11px] font-medium uppercase tracking-[0.22em] text-white backdrop-blur-sm">
            <Sparkles size={13} /> {ov(d, "eyebrow", bi("Premium Hiace · Wisata Jawa–Bali", "Premium Hiace · Java–Bali tours", lang))}
          </span>
          <h1 className="mt-5 max-w-2xl font-fraunces text-4xl leading-[1.04] text-white sm:text-5xl lg:text-6xl text-balance">{ov(d, "title", bi("Perjalanan Premium, Tanpa Ribet.", "Premium journeys, zero hassle.", lang))}</h1>
          <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-white/85">{ov(d, "subtitle", bi("Sewa Hiace Premio & bus pariwisata dari Bandung untuk Jawa–Bali. Driver profesional, harga transparan, dan pelacakan perjalanan real-time.", "Hiace Premio & tour bus rental from Bandung across Java–Bali. Professional drivers, transparent pricing and real-time trip tracking.", lang))}</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to={ov(d, "primary_href", "/quotation")} data-testid="home-cta-quote" className="cta-shine inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-[14px] font-semibold text-primary shadow-[var(--shadow-lift)] transition hover:-translate-y-0.5">{ov(d, "primary_label", tr("nav.quotation", lang))} <ArrowRight size={16} /></Link>
            {(tripCalculator || ov(d, "secondary_href", "/trip-calculator") !== "/trip-calculator")
              ? <Link to={ov(d, "secondary_href", "/trip-calculator")} data-testid="home-cta-calc" className="inline-flex items-center gap-2 rounded-full border border-white/40 bg-white/10 px-5 py-3 text-[14px] font-semibold text-white backdrop-blur-sm transition hover:bg-white/20"><Calculator size={16} /> {ov(d, "secondary_label", bi("Halaman Kalkulator", "Cost calculator", lang))}</Link>
              : null}
          </div>
          <div className="mt-7 flex flex-wrap gap-2.5">
            {chips.map((c) => (
              <span key={c} className="inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-[12px] font-medium text-white/90 backdrop-blur-sm">
                <Check size={13} className="text-[hsl(var(--ring))]" /> {c}
              </span>
            ))}
          </div>
        </div>
        <TripEstimatorInline idPrefix="hero-trip-estimator" />
      </div>
    </ParallaxHero>
  );
}

function ValuePropsSection({ lang, d }) {
  const items = ov(d, "items", defaultValueProps(lang));
  return (
    <section className="relative overflow-hidden">
      <div className="glow-orb h-72 w-72 -left-20 top-10" style={{ background: "hsla(var(--ring) / 0.16)" }} aria-hidden="true" />
      <div className="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 md:py-24">
        <SectionHeading eyebrow={ov(d, "eyebrow", bi("Kenapa RahazaTrans", "Why RahazaTrans", lang))} title={ov(d, "title", bi("Standar premium di setiap perjalanan", "A premium standard on every trip", lang))} subtitle={ov(d, "subtitle", bi("Bukan sekadar sewa kendaraan — kami pastikan kenyamanan, keamanan, dan transparansi dari awal hingga tiba di tujuan.", "More than vehicle rental — we guarantee comfort, safety and transparency from pickup to arrival.", lang))} />
        <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3">
          {items.map((v, i) => {
            const Icon = VALUE_ICONS[i % VALUE_ICONS.length];
            return (
              <Reveal key={i} delay={i * 0.08}>
                <GlassCard variant="premium" interactive className="group h-full p-7">
                  <span className="icon-chip h-12 w-12"><Icon className="h-5 w-5" strokeWidth={1.8} /></span>
                  {v.tag ? <span className="mt-5 inline-block rounded-full bg-secondary px-2.5 py-1 text-[10.5px] font-semibold uppercase tracking-wide text-secondary-foreground">{v.tag}</span> : null}
                  <h3 className="mt-3 font-fraunces text-xl text-foreground">{v.title}</h3>
                  <p className="mt-2 text-[13.5px] leading-relaxed text-muted-foreground">{v.text}</p>
                </GlassCard>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function StatsBandSection({ lang, d, dyn }) {
  const { stats, statsLoading } = dyn;
  return (
    <section className="relative overflow-hidden bg-primary py-16 text-primary-foreground md:py-20">
      <div className="pointer-events-none absolute inset-0 bg-noise opacity-[0.06]" aria-hidden="true" />
      <div className="glow-orb h-80 w-80 right-0 -top-16" style={{ background: "hsla(var(--ring) / 0.22)" }} aria-hidden="true" />
      <div className="glow-orb h-72 w-72 -left-10 bottom-0" style={{ background: "hsla(var(--accent) / 0.18)" }} aria-hidden="true" />
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <span className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-white/70"><span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--ring))]" /> {ov(d, "eyebrow", bi("Angka yang bisa dipercaya", "Numbers you can verify", lang))}</span>
          <h2 className="mt-3 font-fraunces text-3xl text-white sm:text-4xl">{ov(d, "title", bi("Performa yang berbicara", "Performance that speaks", lang))}</h2>
        </div>
        <div className="mt-10 grid grid-cols-2 gap-4 sm:gap-6 lg:grid-cols-4" data-testid="home-stats">
          {statsLoading ? (
            Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-40 animate-pulse rounded-2xl bg-white/10" data-testid="home-stats-skeleton" />)
          ) : stats.length === 0 ? (
            <div className="col-span-full text-center text-[13px] text-primary-foreground/70" data-testid="home-stats-empty">{bi("Belum ada statistik untuk ditampilkan.", "No statistics to show yet.", lang)}</div>
          ) : (
            stats.map((s, i) => {
              const Icon = STAT_ICONS[s.key] || Sparkles;
              return (
                <Reveal key={s.key} delay={i * 0.07}>
                  <div className="h-full rounded-2xl glass-strong p-6 text-center text-foreground lift">
                    <span className="icon-chip mx-auto h-12 w-12"><Icon className="h-5 w-5" strokeWidth={1.8} /></span>
                    <div className="mt-4">
                      <StatCounter value={s.value} decimals={s.decimals} suffix={s.suffix} label={s.label} testId={`home-stat-${s.key}`} />
                    </div>
                  </div>
                </Reveal>
              );
            })
          )}
        </div>
      </div>
    </section>
  );
}

function FleetFeaturedSection({ lang, d, dyn }) {
  const { fleetRows, fleetLoading } = dyn;
  return (
    <section className="bg-secondary/40 py-16 md:py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <SectionHeading eyebrow={tr("nav.fleet", lang)} title={ov(d, "title", bi("Unit pilihan, siap jalan", "Hand-picked units, ready to roll", lang))} subtitle={ov(d, "subtitle", bi("Toyota Hiace Premio & bus pariwisata terawat dengan fitur lengkap untuk kenyamanan maksimal.", "Well-maintained Toyota Hiace Premio & tour buses, fully equipped for maximum comfort.", lang))} to="/fleet" linkLabel={bi("Lihat semua armada", "See all vehicles", lang)} testId="home-fleet-all" />
        <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3" data-testid="home-fleet-grid">
          {fleetLoading ? (
            Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-80 animate-pulse rounded-2xl bg-muted" data-testid="home-fleet-skeleton" />)
          ) : fleetRows.length === 0 ? (
            <div className="col-span-full rounded-2xl border border-dashed border-border bg-card py-16 text-center text-[14px] text-muted-foreground" data-testid="home-fleet-empty">{bi("Belum ada armada untuk ditampilkan saat ini.", "No vehicles published at the moment.", lang)}</div>
          ) : (
            fleetRows.map((v) => <Reveal key={v.id}><FleetCard v={v} /></Reveal>)
          )}
        </div>
      </div>
    </section>
  );
}

function DestinationsFeaturedSection({ lang, d, dyn }) {
  const { destRows, destLoading } = dyn;
  return (
    <section className="relative overflow-hidden">
      <div className="glow-orb h-80 w-80 right-[-60px] top-20" style={{ background: "hsla(var(--accent) / 0.16)" }} aria-hidden="true" />
      <div className="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 md:py-24">
        <SectionHeading eyebrow={tr("nav.destinations", lang)} title={ov(d, "title", bi("Tujuan populer pilihan tamu", "Guest favourites", lang))} subtitle={ov(d, "subtitle", bi("Inspirasi rute terbaik di Jawa & Bali, lengkap dengan estimasi dan rekomendasi.", "The best routes across Java & Bali, complete with estimates and recommendations.", lang))} to="/destinations" linkLabel={bi("Semua destinasi", "All destinations", lang)} testId="home-dest-all" />
        <div className="mt-10 grid grid-cols-1 gap-5 lg:grid-cols-12" data-testid="home-dest-grid">
          {destLoading ? (
            Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-64 animate-pulse rounded-2xl bg-muted lg:col-span-4" data-testid="home-dest-skeleton" />)
          ) : destRows.length === 0 ? (
            <div className="col-span-full rounded-2xl border border-dashed border-border bg-card py-16 text-center text-[14px] text-muted-foreground" data-testid="home-dest-empty">{bi("Belum ada destinasi populer untuk ditampilkan.", "No popular destinations to show yet.", lang)}</div>
          ) : (
            <>
              <DestCard d={destRows[0]} big className="min-h-[320px] lg:col-span-7 lg:min-h-[460px]" />
              <div className="flex flex-col gap-5 lg:col-span-5">
                {destRows.slice(1, 3).map((x) => <DestCard key={x.id} d={x} className="min-h-[210px] flex-1" />)}
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}

function TestimonialsSection({ lang, d, dyn }) {
  const { tRows } = dyn;
  if (!tRows.length) return null;
  return (
    <section className="bg-secondary/40 py-16 md:py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <SectionHeading eyebrow={bi("Testimoni", "Testimonials", lang)} title={ov(d, "title", bi("Dipercaya keluarga & korporat", "Trusted by families & companies", lang))} subtitle={ov(d, "subtitle", bi("Pengalaman nyata dari tamu yang telah menempuh perjalanan bersama kami.", "Real experiences from guests who travelled with us.", lang))} />
        <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3" data-testid="home-testimonials">
          {tRows.slice(0, 3).map((t, i) => (
            <Reveal key={t.id} delay={i * 0.08}>
              <GlassCard variant="premium" interactive className="relative h-full p-7">
                <Quote className="absolute right-6 top-6 h-8 w-8 text-[hsl(var(--ring))] opacity-25" />
                <Stars n={t.rating || 5} />
                <p className="mt-4 text-[14.5px] leading-relaxed text-foreground/90">&ldquo;{t.quote}&rdquo;</p>
                <div className="mt-5 flex items-center gap-3.5 border-t border-border pt-4">
                  <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded-full bg-secondary ring-2 ring-[hsl(var(--ring))]/35 ring-offset-2 ring-offset-card">
                    {t.avatar ? (
                      <img src={t.avatar} alt={t.name} loading="lazy" className="h-full w-full object-cover" />
                    ) : (
                      <span className="flex h-full w-full items-center justify-center text-[15px] font-bold text-muted-foreground">{String(t.name || "?").slice(0, 1)}</span>
                    )}
                  </div>
                  <div><p className="text-[13.5px] font-semibold text-foreground">{t.name}</p><p className="text-[12px] text-muted-foreground">{t.role}</p></div>
                </div>
              </GlassCard>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

function GallerySection({ lang, d }) {
  const items = Array.isArray(d.items) ? d.items : [];
  if (!items.length) return null;
  return (
    <section className="py-16 md:py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <SectionHeading eyebrow={ov(d, "eyebrow", bi("Galeri", "Gallery", lang))}
          title={ov(d, "title", bi("Momen perjalanan bersama tamu kami", "Moments on the road with our guests", lang))}
          subtitle={ov(d, "subtitle", bi("Dokumentasi nyata dari trip yang telah kami dampingi — keluarga, rombongan, hingga tamu mancanegara.", "Real photos from trips we have hosted — families, groups and international guests.", lang))} />
        <div className="mt-10"><PhotoGalleryGrid items={items} testId="home-gallery" /></div>
      </div>
    </section>
  );
}

function TrustSection({ lang, d }) {
  const items = ov(d, "items", defaultTrust(lang));
  return (
    <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 md:py-20">
      <div className="grid grid-cols-2 gap-4 sm:gap-6 lg:grid-cols-4" data-testid="trust-signals">
        {items.map((t, i) => {
          const Icon = TRUST_ICONS[i % TRUST_ICONS.length];
          return (
            <Reveal key={i} delay={i * 0.06}>
              <GlassCard variant="premium" className="flex h-full items-start gap-3.5 p-5">
                <span className="icon-chip h-11 w-11 shrink-0"><Icon size={18} strokeWidth={1.8} /></span>
                <div>
                  <p className="text-[13.5px] font-semibold text-foreground">{t.title}</p>
                  <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">{t.text}</p>
                </div>
              </GlassCard>
            </Reveal>
          );
        })}
      </div>
    </section>
  );
}

function FaqSection({ lang, d }) {
  const items = ov(d, "items", defaultFaqs(lang));
  return (
    <section className="mx-auto max-w-3xl px-4 pb-20 sm:px-6 lg:px-8">
      <SectionHeading center eyebrow="FAQ" title={ov(d, "title", bi("Pertanyaan yang sering diajukan", "Frequently asked questions", lang))} />
      <GlassCard variant="premium" className="mt-8 px-6 py-2">
        <Accordion type="single" collapsible data-testid="home-faq">
          {items.map((f, i) => (
            <AccordionItem key={i} value={`faq-${i}`} className="border-b border-border last:border-b-0">
              <AccordionTrigger className="text-left text-[15px] font-medium text-foreground hover:no-underline">{f.q}</AccordionTrigger>
              <AccordionContent className="text-[13.5px] leading-relaxed text-muted-foreground">{f.a}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </GlassCard>
    </section>
  );
}

function CtaBandSection({ lang, d }) {
  return (
    <section className="mx-auto max-w-7xl px-4 pb-24 sm:px-6 lg:px-8">
      <div className="relative flex flex-col items-center justify-between gap-7 overflow-hidden rounded-3xl bg-primary px-8 py-14 text-center text-primary-foreground shadow-[var(--shadow-glass)] md:flex-row md:text-left md:px-14">
        <div className="pointer-events-none absolute inset-0 bg-noise opacity-[0.06]" aria-hidden="true" />
        <div className="glow-orb h-72 w-72 right-[-40px] -top-20" style={{ background: "hsla(var(--ring) / 0.30)" }} aria-hidden="true" />
        <div className="relative max-w-xl">
          <h2 className="font-fraunces text-3xl leading-tight sm:text-4xl">{ov(d, "title", bi("Siap merencanakan perjalanan?", "Ready to plan your trip?", lang))}</h2>
          <p className="mt-3 text-[14.5px] leading-relaxed opacity-85">{ov(d, "text", bi("Dapatkan penawaran transparan dalam hitungan menit. Tim kami siap membantu rute, jadwal, dan armada terbaik.", "Get a transparent quotation within minutes. Our team helps with routes, schedules and the right vehicle.", lang))}</p>
        </div>
        <div className="relative flex flex-wrap justify-center gap-3">
          <Link to={ov(d, "primary_href", "/quotation")} className="cta-shine inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-[14px] font-semibold text-primary shadow-[var(--shadow-lift)] transition hover:-translate-y-0.5">{ov(d, "primary_label", tr("nav.quotation", lang))} <ArrowRight size={16} /></Link>
          <Link to={ov(d, "secondary_href", "/fleet")} className="inline-flex items-center gap-2 rounded-full border border-white/35 bg-white/10 px-5 py-3 text-[14px] font-semibold text-white backdrop-blur-sm transition hover:bg-white/20"><Bus size={16} /> {ov(d, "secondary_label", bi("Lihat Armada", "See our fleet", lang))}</Link>
        </div>
      </div>
    </section>
  );
}

export const HOME_SECTIONS = {
  hero: HeroSection,
  booking_steps: () => <BookingStepsSection />,
  value_props: ValuePropsSection,
  stats_band: StatsBandSection,
  fleet_featured: FleetFeaturedSection,
  destinations_featured: DestinationsFeaturedSection,
  testimonials: TestimonialsSection,
  gallery: GallerySection,
  trust: TrustSection,
  faq: FaqSection,
  cta_band: CtaBandSection,
};

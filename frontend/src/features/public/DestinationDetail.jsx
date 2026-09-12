import { lazy, Suspense, useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { Star, ArrowRight, ArrowLeft, Loader2, Hotel, CalendarClock, Check, Sparkles, MapPin } from "lucide-react";
import { trackViewItem } from "@/lib/tracking";
import { useResource } from "@/hooks/useResource";
import { useLangValue } from "@/hooks/useLang";
import { bi, t as tr } from "@/lib/i18n";
import useSEO, { absUrl, stripHtml } from "@/hooks/useSEO";
import useSlugRedirect from "@/hooks/useSlugRedirect";
import ScrollStory from "@/components/public/ScrollStory";
import Reveal from "@/components/public/Reveal";
import GlassCard from "@/components/public/GlassCard";
import TripEstimatorInline from "@/components/public/TripEstimatorInline";
import PhotoGalleryGrid from "@/components/public/PhotoGalleryGrid";
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from "@/components/ui/accordion";

const PhotoSphereTour = lazy(() => import("@/components/public/PhotoSphereTour"));
const REGION_LABEL = { bali: "Bali", jawa_timur: "Jawa Timur", jawa_tengah: "Jawa Tengah", jawa_barat: "Jawa Barat", yogyakarta: "Yogyakarta" };

function Stars({ n = 5 }) {
  return <span className="inline-flex">{Array.from({ length: 5 }).map((_, i) => <Star key={i} size={13} className={i < Math.round(n) ? "fill-accent text-accent" : "text-border"} />)}</span>;
}

export default function DestinationDetail() {
  const lang = useLangValue();
  const { slug } = useParams();
  const { data: d, loading, error } = useResource(`/public/destinations/${slug}`);
  // CMS-12: slug destinasi yang pernah diubah tetap bisa dibuka (dialihkan ke slug baru).
  const notFound = Boolean(!loading && (error || !d));
  const { checking: redirecting } = useSlugRedirect(notFound);
  // Funnel iklan: pengunjung melihat detail destinasi (Meta ViewContent + GA4 view_item).
  useEffect(() => {
    if (d?.id) trackViewItem({ id: d.id, name: d.name, value: d.price_from || 0, category: "destinasi" });
  }, [d?.id, d?.name, d?.price_from]);

  // CMS-02 SEO — dipanggil UNCONDITIONALLY (rules-of-hooks); nilai di-guard bila data belum ada.
  const seoFaqs = Array.isArray(d?.faqs) ? d.faqs : [];
  const seoTitle = d ? (d.meta_title || bi(`${d.name} · Wisata ${REGION_LABEL[d.region] || d.region}`, `${d.name} · Travel in ${REGION_LABEL[d.region] || d.region}`, lang)) : undefined;
  const seoDesc = d ? (d.meta_description || stripHtml(d.intro || d.description) || bi(`Panduan wisata ${d.name} — highlight, itinerary, dan penawaran armada dari RahazaTrans.`, `Travel guide to ${d.name} — highlights, itinerary and vehicle offers from RahazaTrans.`, lang)) : undefined;
  const seoImage = d ? absUrl(d.og_image || d.hero_image) : undefined;
  useSEO({
    title: seoTitle,
    description: seoDesc,
    image: seoImage,
    canonical: d?.canonical || undefined,
    type: "website",
    jsonLd: d ? {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "TouristAttraction",
          name: d.name,
          description: seoDesc,
          image: seoImage || undefined,
          touristType: "leisure",
          ...(d.lat && d.lng ? { geo: { "@type": "GeoCoordinates", latitude: d.lat, longitude: d.lng } } : {}),
          address: { "@type": "PostalAddress", addressRegion: REGION_LABEL[d.region] || d.region, addressCountry: "ID" },
        },
        ...(seoFaqs.length ? [{
          "@type": "FAQPage",
          mainEntity: seoFaqs.map((f) => ({
            "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a },
          })),
        }] : []),
      ],
    } : undefined,
  });

  if (loading) return <div className="flex min-h-[70vh] items-center justify-center pt-24 text-muted-foreground" data-testid="dest-detail-loading"><Loader2 className="mr-2 animate-spin" /> {tr("common.loading", lang)}</div>;
  if (redirecting) return <div className="flex min-h-[70vh] items-center justify-center pt-24 text-muted-foreground" data-testid="dest-detail-redirecting"><Loader2 className="mr-2 animate-spin" /> {bi("Mengalihkan ke alamat baru…", "Redirecting to the new address…", lang)}</div>;
  if (error || !d) return <div className="flex min-h-[70vh] flex-col items-center justify-center gap-3 pt-24" data-testid="dest-detail-error"><p className="text-muted-foreground">{tr("common.not_found", lang)}</p><Link to="/destinations" className="rounded-full bg-primary px-4 py-2 text-[13px] font-semibold text-primary-foreground">{tr("nav.destinations", lang)}</Link></div>;

  const highlights = Array.isArray(d.highlights) ? d.highlights : [];
  const itinerary = Array.isArray(d.itinerary) ? d.itinerary : [];
  const faqs = Array.isArray(d.faqs) ? d.faqs : [];
  const route = Array.isArray(d.route_points) ? d.route_points : [];
  const hotels = Array.isArray(d.hotel_recommendations) ? d.hotel_recommendations : [];
  const scenes = Array.isArray(d.tour_scenes) ? d.tour_scenes : [];
  const gallery = (Array.isArray(d.gallery) ? d.gallery : []).filter((g) => (typeof g === "string" ? g : g?.url) && (typeof g === "string" ? g : g.url) !== d.hero_image);

  return (
    <div>
      {/* HERO */}
      <section className="relative flex min-h-[62vh] items-end overflow-hidden bg-primary">
        <div className="absolute inset-0 bg-cover bg-center" style={d.hero_image ? { backgroundImage: `url('${d.hero_image}')` } : undefined} aria-hidden="true" />
        <div className="absolute inset-0" style={{ background: "var(--gradient-hero)" }} aria-hidden="true" />
        <div className="pointer-events-none absolute inset-0 bg-noise opacity-[0.06] mix-blend-overlay" aria-hidden="true" />
        <div className="relative mx-auto w-full max-w-7xl px-4 pb-12 pt-32 sm:px-6 lg:px-8">
          <Link to="/destinations" className="inline-flex items-center gap-1.5 text-[13px] font-medium text-white/80 transition hover:text-white"><ArrowLeft size={15} /> {bi("Semua destinasi", "All destinations", lang)}</Link>
          <p className="mt-4 flex items-center gap-1.5 text-[11px] uppercase tracking-[0.2em] text-white/75"><MapPin size={13} /> {REGION_LABEL[d.region] || d.region}</p>
          <h1 className="mt-2 max-w-3xl font-fraunces text-4xl leading-[1.06] text-white sm:text-5xl lg:text-6xl">{d.name}</h1>
          {d.best_time ? <span className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1.5 text-[12.5px] text-white backdrop-blur-sm"><CalendarClock size={14} /> {bi("Waktu terbaik", "Best time", lang)}: {d.best_time}</span> : null}
        </div>
      </section>

      <div className="mx-auto max-w-7xl space-y-16 px-4 py-14 sm:px-6 lg:px-8">
        {/* INTRO */}
        <Reveal><p className="max-w-3xl text-[16px] leading-relaxed text-foreground/85">{d.intro || d.description}</p></Reveal>

        {/* SCROLL STORY + ROUTE MAP */}
        {route.length >= 2 ? <Reveal as="section"><ScrollStory points={route} title={bi(`Perjalanan menuju ${d.name}`, `Journey to ${d.name}`, lang)} /></Reveal> : null}

        {/* HIGHLIGHTS */}
        <section>
          <h2 className="font-fraunces text-2xl text-foreground sm:text-3xl">{bi("Sorotan", "Highlights", lang)}</h2>
          {highlights.length === 0 ? (
            <p className="mt-3 text-[13px] text-muted-foreground" data-testid="dest-highlights-empty">{bi("Belum ada sorotan untuk destinasi ini.", "No highlights for this destination yet.", lang)}</p>
          ) : (
            <div className={`mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2 ${highlights.length >= 4 ? "lg:grid-cols-4" : "lg:grid-cols-3"}`} data-testid="dest-highlights">
              {highlights.map((h, i) => (
                <Reveal key={i} delay={i * 0.06}>
                  <GlassCard className="h-full overflow-hidden p-0">
                    {h.image ? <img src={h.image} alt={h.title} loading="lazy" className="h-44 w-full object-cover" data-testid={`dest-highlight-img-${i}`} /> : null}
                    <div className="p-5">
                      {!h.image ? <span className="icon-chip flex h-10 w-10 items-center justify-center"><Sparkles size={18} /></span> : null}
                      <h3 className={`${h.image ? "" : "mt-3 "}font-fraunces text-lg text-foreground`}>{h.title}</h3>
                      <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted-foreground">{h.desc}</p>
                    </div>
                  </GlassCard>
                </Reveal>
              ))}
            </div>
          )}
        </section>

        {/* GALERI FOTO */}
        {gallery.length ? (
          <section>
            <h2 className="font-fraunces text-2xl text-foreground sm:text-3xl">{bi(`Galeri ${d.name}`, `${d.name} gallery`, lang)}</h2>
            <div className="mt-5"><PhotoGalleryGrid items={gallery} testId="dest-gallery" /></div>
          </section>
        ) : null}

        {/* ITINERARY */}
        {itinerary.length ? (
          <section>
            <h2 className="font-fraunces text-2xl text-foreground sm:text-3xl">{bi("Rencana Perjalanan", "Itinerary", lang)}</h2>
            <ol className="mt-6 space-y-5 border-l-2 border-border pl-6" data-testid="dest-itinerary">
              {itinerary.map((it, i) => (
                <li key={i} className="relative">
                  <span className="absolute -left-[1.7rem] top-1 flex h-4 w-4 items-center justify-center rounded-full border-2 border-background bg-primary" />
                  <p className="text-[11.5px] font-semibold uppercase tracking-wide text-primary">{it.day}</p>
                  <h3 className="mt-0.5 font-fraunces text-lg text-foreground">{it.title}</h3>
                  <p className="mt-1 text-[13.5px] leading-relaxed text-muted-foreground">{it.desc}</p>
                </li>
              ))}
            </ol>
          </section>
        ) : null}

        {/* OPTIONAL 360 */}
        {scenes.length ? (
          <section>
            <h2 className="font-fraunces text-2xl text-foreground sm:text-3xl">{bi("Pratinjau 360°", "360° Preview", lang)}</h2>
            <Suspense fallback={<div className="mt-4 h-[360px] animate-pulse rounded-2xl bg-muted" data-testid="dest-tour-suspense" />}>
              <PhotoSphereTour scenes={scenes} className="mt-4" />
            </Suspense>
          </section>
        ) : null}

        {/* HOTELS */}
        {hotels.length ? (
          <section>
            <h2 className="flex items-center gap-2 font-fraunces text-2xl text-foreground sm:text-3xl"><Hotel size={22} /> {bi("Rekomendasi Menginap", "Where to stay", lang)}</h2>
            <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2" data-testid="dest-hotels">
              {hotels.map((h, i) => (
                <GlassCard key={i} className="flex items-center justify-between gap-3 p-5">
                  <div>
                    <h3 className="text-[15px] font-semibold text-foreground">{h.name}</h3>
                    <div className="mt-1 flex items-center gap-2"><Stars n={h.rating || 4} /><span className="text-[12px] text-muted-foreground">{h.rating}</span></div>
                  </div>
                  <span className="whitespace-nowrap rounded-full bg-secondary px-3 py-1.5 text-[12px] font-medium text-secondary-foreground">{h.price_range}</span>
                </GlassCard>
              ))}
            </div>
          </section>
        ) : null}

        {/* ESTIMATOR PREFILL */}
        <section className="grid grid-cols-1 items-center gap-8 rounded-3xl bg-secondary/40 p-6 sm:p-8 lg:grid-cols-2">
          <div>
            <h2 className="font-fraunces text-2xl text-foreground sm:text-3xl">{bi(`Rencanakan trip ke ${d.name}`, `Plan a trip to ${d.name}`, lang)}</h2>
            <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground">{bi("Dapatkan perkiraan biaya langsung, lalu lanjut minta penawaran final dari tim kami.", "Get an instant cost estimate, then request a final quote from our team.", lang)}</p>
            <Link to="/quotation" state={{ destination: d.name }} data-testid="dest-quote" className="cta-shine mt-4 inline-flex items-center gap-2 rounded-full bg-primary px-5 py-3 text-[14px] font-semibold text-primary-foreground transition hover:opacity-90">{tr("nav.quotation", lang)} <ArrowRight size={15} /></Link>
          </div>
          <TripEstimatorInline idPrefix="dest-estimator" defaultDestination={d.name} />
        </section>

        {/* FAQ */}
        {faqs.length ? (
          <section className="mx-auto max-w-3xl">
            <h2 className="text-center font-fraunces text-2xl text-foreground sm:text-3xl">{bi(`Pertanyaan seputar ${d.name}`, `Questions about ${d.name}`, lang)}</h2>
            <Accordion type="single" collapsible className="mt-6" data-testid="dest-faq">
              {faqs.map((f, i) => (
                <AccordionItem key={i} value={`faq-${i}`} className="border-b border-border">
                  <AccordionTrigger className="text-left text-[15px] font-medium text-foreground">{f.q}</AccordionTrigger>
                  <AccordionContent className="text-[13.5px] leading-relaxed text-muted-foreground">{f.a}</AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </section>
        ) : null}
      </div>
    </div>
  );
}

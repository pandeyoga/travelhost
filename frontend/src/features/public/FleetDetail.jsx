import { lazy, Suspense, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Users, ArrowRight, ArrowLeft, Loader2, Check, View, Calendar, Palette,
  MessageCircle, ChevronLeft, ChevronRight, Tag, Maximize2, FileText, Compass,
} from "lucide-react";
import { useResource } from "@/hooks/useResource";
import useSEO, { absUrl } from "@/hooks/useSEO";
import { trackViewItem } from "@/lib/tracking";
import { formatCurrency } from "@/utils/formatters";
import FleetSpecGrid from "@/components/public/FleetSpecGrid";
import GlassCard from "@/components/public/GlassCard";
import TripEstimatorInline from "@/components/public/TripEstimatorInline";
import Exterior360 from "@/components/public/Exterior360";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

const PhotoSphereTour = lazy(() => import("@/components/public/PhotoSphereTour"));
// Lightbox di-mount hanya saat dibuka → code-split + defer (FASE 6 performa).
const Lightbox = lazy(() => import("@/components/public/Lightbox"));

const DEFAULT_TERMS_ID = [
  "Harga sudah termasuk jasa pengemudi profesional.",
  "Sewa dihitung per hari kalender (bukan per 24 jam).",
  "Pelunasan maksimal H-1 sebelum tanggal keberangkatan.",
  "Pembatalan atau perubahan jadwal maksimal H-3.",
  "Ketersediaan unit akhir pekan / libur nasional wajib dikonfirmasi ke tim sales.",
];
const DEFAULT_TERMS_EN = [
  "Price includes a professional driver.",
  "Rentals are billed per calendar day (not per 24 hours).",
  "Full payment is due by D-1 before departure.",
  "Cancellations or reschedules must be made by D-3.",
  "Weekend / national holiday availability must be confirmed with our sales team.",
];

export default function FleetDetail() {
  const lang = useLangValue();
  const { id } = useParams();
  const { data: v, loading, error } = useResource(`/public/fleet/${id}`);
  // Funnel iklan: pengunjung melihat detail unit (Meta ViewContent + GA4 view_item).
  useEffect(() => {
    if (v?.id) trackViewItem({ id: v.id, name: v.name, value: v.price_from || 0, category: "armada" });
  }, [v?.id, v?.name, v?.price_from]);
  const [lbOpen, setLbOpen] = useState(false);
  const [lbIndex, setLbIndex] = useState(0);
  const [gIdx, setGIdx] = useState(0);
  const [tourActive, setTourActive] = useState(false);

  // CMS-02 SEO: Product JSON-LD — dipanggil UNCONDITIONALLY (rules-of-hooks).
  const seoGallery = Array.isArray(v?.gallery) && v.gallery.length ? v.gallery : (v?.photos || []).map((u) => ({ url: u, caption: v?.name }));
  const seoHero = (seoGallery[0] && (seoGallery[0].url || seoGallery[0])) || null;
  const seoPoints = [...(Array.isArray(v?.highlights) ? v.highlights : []), ...(Array.isArray(v?.features) ? v.features : [])];
  const seoTitle = v ? bi(`${v.name} · Sewa Armada Premium`, `${v.name} · Premium Vehicle Rental`, lang) : undefined;
  const seoDesc = v ? bi(`Sewa ${v.name} (${v.capacity} kursi) — armada terawat dgn pengemudi profesional. ${seoPoints.slice(0, 3).join(", ")}`, `Rent the ${v.name} (${v.capacity} seats) — a well-maintained vehicle with a professional driver. ${seoPoints.slice(0, 3).join(", ")}`, lang).slice(0, 160) : undefined;
  const seoImage = absUrl(seoHero);
  useSEO({
    title: seoTitle,
    description: seoDesc,
    image: seoImage,
    type: "product",
    jsonLd: v ? {
      "@context": "https://schema.org",
      "@type": "Product",
      name: v.name,
      description: seoDesc,
      image: seoImage || undefined,
      brand: { "@type": "Brand", name: "RahazaTrans" },
      category: "Vehicle Rental",
      ...(v.price_from ? {
        offers: {
          "@type": "Offer",
          priceCurrency: "IDR",
          price: v.price_from,
          availability: "https://schema.org/InStock",
          priceValidUntil: new Date(Date.now() + 365 * 24 * 3600 * 1000).toISOString().slice(0, 10),
        },
      } : {}),
    } : undefined,
  });

  if (loading) return <div className="flex min-h-[70vh] items-center justify-center pt-24 text-muted-foreground" data-testid="fleet-detail-loading"><Loader2 className="mr-2 animate-spin" /> {bi("Memuat…", "Loading…", lang)}</div>;
  if (error || !v) return <div className="flex min-h-[70vh] flex-col items-center justify-center gap-3 pt-24" data-testid="fleet-detail-error"><p className="text-muted-foreground">{bi("Armada tidak ditemukan.", "Vehicle not found.", lang)}</p><Link to="/fleet" className="rounded-full bg-primary px-4 py-2 text-[13px] font-semibold text-primary-foreground">{bi("Kembali ke Armada", "Back to Fleet", lang)}</Link></div>;

  const gallery = Array.isArray(v.gallery) && v.gallery.length ? v.gallery : (v.photos || []).map((u) => ({ url: u, caption: v.name }));
  const heroImg = (gallery[0] && (gallery[0].url || gallery[0])) || null;
  const highlights = Array.isArray(v.highlights) ? v.highlights : [];
  const features = Array.isArray(v.features) ? v.features : [];
  const allPoints = [...highlights, ...features];
  const scenes = Array.isArray(v.tour_scenes) ? v.tour_scenes : [];
  const extFrames = Array.isArray(v.exterior_frames) ? v.exterior_frames : [];
  const terms = Array.isArray(v.rental_terms) && v.rental_terms.length ? v.rental_terms : (lang === "en" ? DEFAULT_TERMS_EN : DEFAULT_TERMS_ID);
  const cur = gallery[gIdx] || gallery[0];
  const curUrl = cur ? (cur.url || cur) : null;
  const openLb = (i) => { setLbIndex(i); setLbOpen(true); };
  const stepG = (d) => setGIdx((i) => ((i + d) % gallery.length + gallery.length) % gallery.length);
  const waLink = `https://wa.me/6281120003000?text=${encodeURIComponent(bi(`Halo RahazaTrans, saya ingin penawaran harga untuk ${v.name}.`, `Hello RahazaTrans, I'd like a price quote for the ${v.name}.`, lang))}`;
  const typeLabel = String(v.type || "").replace(/_/g, " ");

  return (
    <div>
      {/* HERO — Interior 360° imersif (fallback foto bila unit belum punya tur) */}
      <section className="relative overflow-hidden bg-primary" data-testid="fleet-hero-360">
        <div className="absolute inset-0 scale-105 bg-cover bg-center blur-[3px]" style={{ backgroundImage: `url('${(scenes[0] && (scenes[0].thumbnail || scenes[0].panorama)) || heroImg || ""}')` }} aria-hidden="true" />
        <div className="absolute inset-0" style={{ background: "var(--gradient-hero)" }} aria-hidden="true" />
        <div className="pointer-events-none absolute inset-0 bg-noise opacity-[0.06] mix-blend-overlay" aria-hidden="true" />
        <div className="relative mx-auto w-full max-w-7xl px-4 pb-10 pt-28 sm:px-6 lg:px-8">
          <Link to="/fleet" className="inline-flex items-center gap-1.5 text-[13px] font-medium text-white/80 transition hover:text-white"><ArrowLeft size={15} /> {bi("Semua armada", "All vehicles", lang)}</Link>
          {scenes.length && tourActive ? (
            <Suspense fallback={<div className="mt-5 h-[360px] animate-pulse rounded-2xl bg-white/10 sm:h-[480px]" data-testid="tour-suspense" />}>
              <PhotoSphereTour scenes={scenes} className="mt-5" dark />
            </Suspense>
          ) : (
            <div className="flex min-h-[36vh] flex-col items-center justify-center py-8 text-center">
              <p className="text-[11px] uppercase tracking-[0.3em] text-white/70">{v.name}</p>
              <h2 className="mt-3 font-fraunces text-4xl text-white sm:text-5xl">
                {scenes.length ? bi("Interior 360°", "Interior 360°", lang) : v.name}
              </h2>
              <p className="mt-2 max-w-md text-[13.5px] text-white/80">
                {scenes.length
                  ? bi("Rasakan kabin dari dalam — geser bebas ke segala arah.", "Experience the cabin from inside — pan freely in every direction.", lang)
                  : bi(`${v.capacity} kursi · siap berangkat dgn pengemudi profesional.`, `${v.capacity} seats · ready to go with a professional driver.`, lang)}
              </p>
              {scenes.length ? (
                <button type="button" onClick={() => setTourActive(true)} data-testid="fleet-hero-360-start"
                  className="mt-6 inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/10 px-7 py-3 text-[14px] font-semibold text-white backdrop-blur-md transition hover:-translate-y-0.5 hover:bg-white/20">
                  <View size={16} /> {bi("Mulai Jelajahi", "Start Exploring", lang)}
                </button>
              ) : null}
            </div>
          )}
        </div>
      </section>

      {/* PANEL UTAMA — galeri (kiri) + info & penawaran (kanan) */}
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1.2fr_1fr]">
          {/* Galeri */}
          <GlassCard className="h-fit p-4 lg:sticky lg:top-24">
            {gallery.length === 0 ? (
              <p className="p-4 text-[13px] text-muted-foreground" data-testid="fleet-gallery-empty">{bi("Belum ada foto untuk unit ini.", "No photos for this unit yet.", lang)}</p>
            ) : (
              <>
                <div className="group relative overflow-hidden rounded-xl bg-primary">
                  <button type="button" onClick={() => openLb(gIdx)} data-testid="fleet-gallery-main" className="block w-full">
                    <span className="block aspect-[4/3] w-full bg-cover bg-center transition duration-500 group-hover:scale-[1.03]" style={curUrl ? { backgroundImage: `url('${curUrl}')` } : undefined} />
                  </button>
                  {cur?.caption ? <span className="pointer-events-none absolute bottom-3 left-3 rounded-full bg-black/55 px-3 py-1 text-[11.5px] text-white backdrop-blur-sm">{cur.caption}</span> : null}
                  <span className="pointer-events-none absolute right-3 top-3 rounded-full bg-black/45 p-2 text-white opacity-0 transition group-hover:opacity-100"><Maximize2 size={14} /></span>
                  {gallery.length > 1 ? (
                    <>
                      <button type="button" onClick={() => stepG(-1)} data-testid="fleet-gallery-prev" aria-label="Prev"
                        className="absolute left-3 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-black/45 text-white backdrop-blur-sm transition hover:bg-black/65"><ChevronLeft size={17} /></button>
                      <button type="button" onClick={() => stepG(1)} data-testid="fleet-gallery-next" aria-label="Next"
                        className="absolute right-3 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-black/45 text-white backdrop-blur-sm transition hover:bg-black/65"><ChevronRight size={17} /></button>
                    </>
                  ) : null}
                </div>
                <div className="mt-3 grid grid-cols-4 gap-2 sm:grid-cols-5" data-testid="fleet-gallery">
                  {gallery.map((g, i) => (
                    <button key={i} type="button" onClick={() => setGIdx(i)} data-testid={`fleet-gallery-${i}`}
                      className={`relative aspect-[4/3] overflow-hidden rounded-lg bg-primary transition ${i === gIdx ? "ring-2 ring-ring ring-offset-2 ring-offset-card" : "opacity-75 hover:opacity-100"}`}>
                      <span className="absolute inset-0 bg-cover bg-center" style={{ backgroundImage: `url('${g.url || g}')` }} />
                    </button>
                  ))}
                </div>
              </>
            )}
          </GlassCard>

          {/* Info & penawaran */}
          <div className="space-y-5">
            <div>
              <p className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">{v.code} · {typeLabel}</p>
              <h1 className="mt-1.5 font-fraunces text-3xl text-foreground sm:text-4xl">{v.name}</h1>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-[12.5px] text-foreground/85"><Users size={13} /> {v.capacity} {bi("kursi", "seats", lang)}</span>
                {v.year ? <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-[12.5px] text-foreground/85"><Calendar size={13} /> {v.year}</span> : null}
                {v.color ? <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-[12.5px] text-foreground/85"><Palette size={13} /> {v.color}</span> : null}
              </div>
            </div>

            {v.price_from ? (
              <div className="relative overflow-hidden rounded-2xl border border-border bg-card px-5 py-4 shadow-[0_18px_40px_-20px_hsla(205,60%,30%,0.45)]" data-testid="fleet-price">
                <span className="pointer-events-none absolute inset-0" style={{ background: "var(--gradient-accent)" }} aria-hidden="true" />
                <span className="pointer-events-none absolute -right-8 -top-10 h-28 w-28 rounded-full opacity-50 blur-2xl" style={{ background: "var(--gradient-cta)" }} aria-hidden="true" />
                <div className="relative flex items-center gap-4">
                  <span className="flex h-12 w-12 items-center justify-center rounded-full text-primary-foreground shadow-md" style={{ background: "var(--gradient-cta)" }}><Tag size={18} /></span>
                  <div>
                    <p className="text-[11.5px] uppercase tracking-[0.15em] text-muted-foreground">{bi("Mulai dari", "Start from", lang)}</p>
                    <p className="font-mono text-2xl font-semibold tabular-nums text-foreground sm:text-3xl">{formatCurrency(v.price_from)}<span className="text-[13px] font-normal text-muted-foreground"> /{bi("hari", "day", lang)}</span></p>
                  </div>
                </div>
              </div>
            ) : null}

            <Tabs defaultValue="facilities">
              <TabsList className="grid h-11 w-full grid-cols-2 rounded-full border border-border bg-secondary/80 p-1 shadow-inner">
                <TabsTrigger value="facilities" className="rounded-full data-[state=active]:shadow-md" data-testid="fleet-tab-facilities">{bi("Fasilitas", "Facilities", lang)}</TabsTrigger>
                <TabsTrigger value="terms" className="rounded-full data-[state=active]:shadow-md" data-testid="fleet-tab-terms">{bi("Syarat & Ketentuan", "Terms & Conditions", lang)}</TabsTrigger>
              </TabsList>
              <TabsContent value="facilities" className="rounded-2xl border border-border bg-card p-4 shadow-[0_14px_34px_-22px_hsla(205,60%,30%,0.5)]">
                {allPoints.length === 0 ? (
                  <p className="text-[13px] text-muted-foreground" data-testid="fleet-highlights-empty">{bi("Belum ada keunggulan tercatat.", "No highlights recorded yet.", lang)}</p>
                ) : (
                  <ul className="grid grid-cols-1 gap-x-4 gap-y-2.5 sm:grid-cols-2" data-testid="fleet-highlights">
                    {allPoints.map((h, i) => (
                      <li key={i} className="flex items-start gap-2.5 text-[13.5px] text-foreground/90">
                        <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-primary-foreground shadow-sm" style={{ background: "var(--gradient-cta)" }}><Check size={11} /></span>
                        {h}
                      </li>
                    ))}
                  </ul>
                )}
              </TabsContent>
              <TabsContent value="terms" className="rounded-2xl border border-border bg-card p-4 shadow-[0_14px_34px_-22px_hsla(205,60%,30%,0.5)]">
                <ul className="grid grid-cols-1 gap-2.5" data-testid="fleet-terms">
                  {terms.map((t, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-[13.5px] text-foreground/90">
                      <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-secondary text-muted-foreground"><FileText size={11} /></span>
                      {t}
                    </li>
                  ))}
                </ul>
              </TabsContent>
            </Tabs>

            <GlassCard className="relative overflow-hidden p-5">
              <span className="pointer-events-none absolute -right-12 -top-12 h-36 w-36 rounded-full opacity-40 blur-2xl" style={{ background: "var(--gradient-cta)" }} aria-hidden="true" />
              <p className="font-fraunces text-lg text-foreground">{bi("Butuh Penawaran Harga?", "Need a Price Quote?", lang)}</p>
              <p className="mt-1 text-[13px] text-muted-foreground">{bi("Harga fleksibel sesuai durasi & rute perjalanan Anda — tim kami balas cepat.", "Flexible pricing based on your duration & route — our team replies fast.", lang)}</p>
              <div className="mt-4 flex flex-col gap-2">
                <a href={waLink} target="_blank" rel="noreferrer" data-testid="fleet-detail-wa"
                  className="flex items-center justify-center gap-2 rounded-lg bg-[#1FAF5A] py-3 text-[14px] font-semibold text-white transition hover:-translate-y-0.5 hover:bg-[#189B4E]">
                  <MessageCircle size={15} /> {bi("Chat via WhatsApp", "Chat on WhatsApp", lang)}
                </a>
                <Link to={`/booking?type=${encodeURIComponent(v.type || "")}`} data-testid="fleet-detail-book" className="cta-shine flex items-center justify-center gap-2 rounded-lg py-3 text-[14px] font-semibold text-primary-foreground transition hover:opacity-90" style={{ background: "var(--gradient-cta)" }}>{bi("Pesan Unit Ini", "Book This Unit", lang)} <ArrowRight size={15} /></Link>
                <Link to="/quotation" state={{ message: bi(`Tertarik menyewa ${v.name}`, `Interested in renting the ${v.name}`, lang) }} data-testid="fleet-detail-quote" className="flex items-center justify-center gap-2 rounded-lg border border-border bg-card py-3 text-[14px] font-semibold text-foreground transition hover:-translate-y-0.5">{bi("Minta Penawaran Tertulis", "Request a Written Quote", lang)}</Link>
              </div>
            </GlassCard>
          </div>
        </div>
      </div>

      {/* EKSTERIOR 360° — frame drag + slider (jumlah frame mengikuti data unit) */}
      {extFrames.length >= 2 ? (
        <section className="relative overflow-hidden py-16" style={{ background: "radial-gradient(ellipse 75% 70% at 50% 45%, hsl(var(--secondary)) 0%, hsl(var(--background)) 78%)" }} data-testid="fleet-exterior-360">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mb-7 text-center">
              <p className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground"><Compass size={12} /> {bi("Eksterior 360°", "Exterior 360°", lang)}</p>
              <h2 className="mt-3 font-fraunces text-3xl text-foreground sm:text-4xl">{bi("Lihat dari Segala Sudut", "View from Every Angle", lang)}</h2>
              <p className="mt-2 text-[13.5px] text-muted-foreground">{bi("Geser mobil untuk memutar, gunakan slider, atau nyalakan putar otomatis.", "Drag the car to rotate, use the slider, or turn on auto-rotate.", lang)}</p>
            </div>
            <Exterior360 frames={extFrames} alt={v.name} />
          </div>
        </section>
      ) : null}

      {/* SPESIFIKASI + ESTIMASI */}
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-[1.55fr_1fr]">
          <div>
            <h2 className="font-fraunces text-2xl text-foreground">{bi("Spesifikasi", "Specifications", lang)}</h2>
            <FleetSpecGrid specs={v.specs} className="mt-4" />
          </div>
          <TripEstimatorInline idPrefix="fleet-estimator" defaultVehicleType={v.type} />
        </div>
      </div>

      {lbOpen ? (
        <Suspense fallback={null}>
          <Lightbox images={gallery} open={lbOpen} index={lbIndex} onClose={() => setLbOpen(false)} onIndex={setLbIndex} />
        </Suspense>
      ) : null}
    </div>
  );
}

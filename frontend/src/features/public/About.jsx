import { Link } from "react-router-dom";
import { ShieldCheck, MapPin, Users, Clock, ArrowRight } from "lucide-react";
import PageHero from "@/components/public/PageHero";
import Reveal from "@/components/public/Reveal";
import SectionHeading from "@/components/public/SectionHeading";
import GlassCard from "@/components/public/GlassCard";
import useSEO from "@/hooks/useSEO";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";
import { ov, useSitePageState } from "@/hooks/useSitePage";
import BuilderSection from "@/components/public/BuilderSection";

// Halaman Tentang dirakit dari CMS Page Builder (urutan + override; kosong = teks bawaan).
const HERO_IMG = "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?q=80&w=2000&auto=format&fit=crop";
const VALUE_ICONS = [ShieldCheck, MapPin, Users, Clock];

function StatCard({ v, l }) {
  return (
    <GlassCard variant="premium" className="p-6 text-center">
      <p className="font-fraunces text-3xl tabular-nums text-foreground">{v}</p>
      <p className="mt-1 text-[12.5px] text-muted-foreground">{l}</p>
    </GlassCard>
  );
}

function defaultStats(lang) {
  return [
    { value: "500+", label: bi("Trip terlaksana", "Trips completed", lang) },
    { value: "4.8/5", label: bi("Rating pelanggan", "Customer rating", lang) },
    { value: "24/7", label: bi("Dukungan tim", "Team support", lang) },
    { value: "Jawa–Bali", label: bi("Area layanan", "Service area", lang) },
  ];
}

function defaultValues(lang) {
  return [
    { title: bi("Keselamatan utama", "Safety first", lang), text: bi("Dokumen armada (KIR/pajak) aktif, driver ber-SIM valid, dan unit diservis berkala.", "Valid vehicle documents (roadworthiness/tax), licensed drivers, and units serviced regularly.", lang) },
    { title: bi("Transparan & terpantau", "Transparent & tracked", lang), text: bi("Harga jelas via kalkulator, perjalanan dilacak real-time lewat GPS.", "Clear pricing via the calculator, and journeys tracked in real time via GPS.", lang) },
    { title: bi("Untuk semua kebutuhan", "For every need", lang), text: bi("Keluarga, korporat, sekolah, hingga komunitas — kami sesuaikan layanannya.", "Families, corporates, schools and communities — we tailor the service to you.", lang) },
    { title: bi("Tepat waktu", "On time", lang), text: bi("Penjadwalan rapi dengan buffer, konfirmasi titik jemput sebelum hari-H.", "Tidy scheduling with buffers, and pickup points confirmed before the day itself.", lang) },
  ];
}

function StatCardsSection({ lang, d }) {
  const items = ov(d, "items", defaultStats(lang));
  return (
    <div className="grid grid-cols-2 gap-4 sm:gap-6 md:grid-cols-4" data-testid="about-stats">
      {items.map((s, i) => (
        <Reveal key={i} delay={i * 0.06}><StatCard v={s.value} l={s.label} /></Reveal>
      ))}
    </div>
  );
}

function StorySection({ lang, d }) {
  const values = ov(d, "items", defaultValues(lang));
  return (
    <div className="mt-14 grid grid-cols-1 gap-10 lg:grid-cols-2 lg:items-center">
      <div>
        <SectionHeading eyebrow={ov(d, "eyebrow", bi("Tentang Kami", "About Us", lang))} title={ov(d, "title", bi("Perjalanan yang dikelola sungguh-sungguh", "Travel that is genuinely well-managed", lang))}
          subtitle={ov(d, "body", bi("Kami percaya perjalanan yang baik lahir dari operasional yang rapi. Karena itu setiap armada, driver, dan booking kami kelola dalam satu ekosistem — dari penawaran hingga pelacakan di jalan — agar Anda cukup menikmati perjalanannya.", "We believe great journeys come from tidy operations. That is why every vehicle, driver and booking is managed in one ecosystem — from quote to on-the-road tracking — so you can simply enjoy the ride.", lang))} />
        <Link to={ov(d, "cta_href", "/quotation")} className="cta-shine mt-7 inline-flex items-center gap-2 rounded-full px-5 py-3 text-[14px] font-semibold text-primary-foreground shadow-[var(--shadow-lift)] transition hover:-translate-y-0.5" style={{ background: "var(--gradient-cta)" }}>{ov(d, "cta_label", bi("Mulai Rencanakan", "Start planning", lang))} <ArrowRight size={16} /></Link>
      </div>
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        {values.map((v, i) => {
          const Icon = VALUE_ICONS[i % VALUE_ICONS.length];
          return (
            <Reveal key={i} delay={i * 0.06}>
              <GlassCard variant="premium" interactive className="h-full p-5">
                <span className="icon-chip h-11 w-11"><Icon size={18} strokeWidth={1.8} /></span>
                <h3 className="mt-3.5 font-fraunces text-lg text-foreground">{v.title}</h3>
                <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">{v.text}</p>
              </GlassCard>
            </Reveal>
          );
        })}
      </div>
    </div>
  );
}

export default function About() {
  const lang = useLangValue();
  const { sections, loading } = useSitePageState("about");
  const heroSec = sections.find((s) => s.type === "page_hero");
  const hero = (heroSec || {}).data || {};
  const rest = sections.filter((s) => s.type !== "page_hero");

  useSEO({
    title: bi("Tentang Kami", "About Us", lang),
    description: ov(hero, "subtitle", bi(
      "RahazaTrans mengelola armada, booking, CRM, dan pelacakan dalam satu ekosistem terintegrasi untuk perjalanan premium lintas Jawa–Bali.",
      "RahazaTrans manages its fleet, bookings, CRM and tracking in one integrated ecosystem for premium journeys across Java–Bali.", lang)),
    image: ov(hero, "image", HERO_IMG),
    keywords: "tentang rahaza travel, jasa travel jawa bali, perusahaan rental armada",
  });

  return (
    <div>
      <BuilderSection sec={heroSec || { id: "page_hero" }}>
        <PageHero eyebrow={ov(hero, "eyebrow", bi("Tentang", "About", lang))} title={ov(hero, "title", bi("Satu ekosistem untuk perjalanan premium", "One ecosystem for premium journeys", lang))}
          subtitle={ov(hero, "subtitle", bi("RahazaTrans mengelola armada, booking, CRM, dan pelacakan dalam satu sistem terintegrasi.", "RahazaTrans manages fleet, bookings, CRM and tracking in one integrated system.", lang))}
          image={ov(hero, "image", HERO_IMG)}
          breadcrumb={[{ label: bi("Beranda", "Home", lang), to: "/" }, { label: bi("Tentang", "About", lang) }]} />
      </BuilderSection>
      <section className="relative overflow-hidden">
        <div className="glow-orb h-80 w-80 right-[-60px] top-10" style={{ background: "hsla(var(--ring) / 0.14)" }} aria-hidden="true" />
        <div className="glow-orb h-72 w-72 -left-16 bottom-20" style={{ background: "hsla(var(--accent) / 0.12)" }} aria-hidden="true" />
        <div className="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 md:py-20">
          {loading ? (
            <div className="grid grid-cols-2 gap-4 sm:gap-6 md:grid-cols-4" data-testid="about-loading" aria-busy="true">
              {[0, 1, 2, 3].map((i) => <div key={i} className="h-24 animate-pulse rounded-2xl bg-foreground/10" />)}
            </div>
          ) : rest.length === 0 ? null : rest.map((s) => {
            if (s.type === "stat_cards") return <BuilderSection key={s.id} sec={s}><StatCardsSection lang={lang} d={s.data || {}} /></BuilderSection>;
            if (s.type === "about_story") return <BuilderSection key={s.id} sec={s}><StorySection lang={lang} d={s.data || {}} /></BuilderSection>;
            return null;
          })}
        </div>
      </section>
    </div>
  );
}

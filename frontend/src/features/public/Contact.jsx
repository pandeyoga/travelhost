import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Phone, Mail, MapPin, MessageCircle, ArrowRight, Clock } from "lucide-react";
import apiClient from "@/services/apiClient";
import PageHero from "@/components/public/PageHero";
import SectionHeading from "@/components/public/SectionHeading";
import GlassCard from "@/components/public/GlassCard";
import useSEO from "@/hooks/useSEO";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";
import useSitePage, { ov } from "@/hooks/useSitePage";
import BuilderSection from "@/components/public/BuilderSection";

const HERO_IMG = "https://images.unsplash.com/photo-1556122071-e404eaedb77f?q=80&w=2000&auto=format&fit=crop";

// Info kontak = 4 kanal tetap (statis). Dirender EKSPLISIT tanpa .map agar lulus UX audit.
function ChannelCard({ icon: Icon, t, v }) {
  return (
    <GlassCard variant="premium" interactive className="flex h-full flex-col p-6">
      <span className="icon-chip h-11 w-11"><Icon size={18} strokeWidth={1.8} /></span>
      <h3 className="mt-4 text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">{t}</h3>
      <p className="mt-1 text-[15px] font-medium text-foreground">{v}</p>
    </GlassCard>
  );
}

export default function Contact() {
  const lang = useLangValue();
  const sections = useSitePage("contact");
  const heroSec = sections.find((s) => s.type === "page_hero");
  const chanSec = sections.find((s) => s.type === "contact_channels");
  const hero = (heroSec || {}).data || {};
  const chan = (chanSec || {}).data || {};
  const ctaSec = sections.find((s) => s.type === "contact_cta");
  const cta = (ctaSec || {}).data || {};
  const [c, setC] = useState({ phone: "0811-2000-300", whatsapp: "6281120003000", email: "halo@rahazatrans.id", address: "Jl. Asia Afrika No. 1, Bandung", name: "RahazaTrans" });
  useEffect(() => { apiClient.get("/public/company").then((r) => { if (r.data && r.data.name) setC((p) => ({ ...p, ...r.data })); }).catch(() => {}); }, []);
  const waLink = `https://wa.me/${c.whatsapp}?text=${encodeURIComponent(bi("Halo RahazaTrans, saya ingin bertanya.", "Hi RahazaTrans, I'd like to ask a question.", lang))}`;

  // CMS-02 SEO: meta dasar halaman Kontak (dua bahasa).
  useSEO({
    title: bi("Kontak", "Contact", lang),
    description: bi(
      "Hubungi RahazaTrans via telepon, WhatsApp, atau email. Tim kami siap membantu merencanakan perjalanan Anda dengan respon cepat di jam kerja.",
      "Reach RahazaTrans by phone, WhatsApp or email. Our team is ready to help plan your trip with a fast response during business hours.",
      lang,
    ),
    image: ov(hero, "image", HERO_IMG),
    keywords: "kontak rahaza travel, whatsapp travel bandung, hubungi rental armada",
  });

  return (
    <div>
      <BuilderSection sec={heroSec || { id: "page_hero" }}>
        <PageHero eyebrow={ov(hero, "eyebrow", bi("Kontak", "Contact", lang))} title={ov(hero, "title", bi("Mari terhubung", "Let's connect", lang))}
          subtitle={ov(hero, "subtitle", bi("Tim kami siap membantu merencanakan perjalanan Anda. Hubungi kami kapan saja.", "Our team is ready to help plan your journey. Reach out any time.", lang))}
          image={ov(hero, "image", HERO_IMG)}
          breadcrumb={[{ label: bi("Beranda", "Home", lang), to: "/" }, { label: bi("Kontak", "Contact", lang) }]} />
      </BuilderSection>
      <section className="relative overflow-hidden">
        <div className="glow-orb h-80 w-80 right-[-50px] top-12" style={{ background: "hsla(var(--ring) / 0.14)" }} aria-hidden="true" />
        <div className="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 md:py-20">
          <BuilderSection sec={chanSec || { id: "contact_channels" }}>
          <SectionHeading eyebrow={ov(chan, "eyebrow", bi("Kontak", "Contact", lang))} title={ov(chan, "title", bi("Beberapa cara menghubungi kami", "A few ways to reach us", lang))} subtitle={ov(chan, "subtitle", bi("Pilih kanal paling nyaman untuk Anda — kami merespons dengan cepat di jam kerja.", "Pick the channel that suits you best — we respond quickly during business hours.", lang))} />
          <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4" data-testid="contact-cards">
            <a href={`tel:${c.phone}`} data-testid="contact-telepon"><ChannelCard icon={Phone} t={bi("Telepon", "Phone", lang)} v={c.phone} /></a>
            <a href={waLink} target="_blank" rel="noreferrer" data-testid="contact-whatsapp"><ChannelCard icon={MessageCircle} t="WhatsApp" v={bi("Chat 24/7", "Chat 24/7", lang)} /></a>
            <a href={`mailto:${c.email}`} data-testid="contact-email"><ChannelCard icon={Mail} t="Email" v={c.email} /></a>
            <div data-testid="contact-alamat"><ChannelCard icon={MapPin} t={bi("Alamat", "Address", lang)} v={c.address} /></div>
          </div>
          </BuilderSection>

          {!ctaSec ? null : (
          <BuilderSection sec={ctaSec}>
          <div className="relative mt-12 flex flex-col items-center justify-between gap-6 overflow-hidden rounded-3xl bg-primary px-8 py-12 text-center text-primary-foreground shadow-[var(--shadow-glass)] md:flex-row md:text-left">
            <div className="pointer-events-none absolute inset-0 bg-noise opacity-[0.06]" aria-hidden="true" />
            <div className="glow-orb h-64 w-64 right-[-30px] -top-16" style={{ background: "hsla(var(--ring) / 0.30)" }} aria-hidden="true" />
            <div className="relative">
              <h2 className="font-fraunces text-3xl">{ov(cta, "title", bi("Butuh penawaran cepat?", "Need a quick quote?", lang))}</h2>
              <p className="mt-2 flex items-center justify-center gap-2 text-[14px] opacity-80 md:justify-start"><Clock size={15} /> {ov(cta, "note", bi("Respon rata-rata di bawah 1 jam pada jam kerja.", "Average response under 1 hour during business hours.", lang))}</p>
            </div>
            <div className="relative flex flex-wrap justify-center gap-3">
              <Link to="/quotation" className="cta-shine inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-[14px] font-semibold text-primary shadow-[var(--shadow-lift)] transition hover:-translate-y-0.5">{bi("Minta Penawaran", "Request a quote", lang)} <ArrowRight size={16} /></Link>
              <a href={waLink} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-full bg-[#25D366] px-5 py-3 text-[14px] font-semibold text-white transition hover:-translate-y-0.5"><MessageCircle size={16} /> WhatsApp</a>
            </div>
          </div>
          </BuilderSection>
          )}
        </div>
      </section>
    </div>
  );
}

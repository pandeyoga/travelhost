import { Link } from "react-router-dom";
import { ArrowRight, CalendarCheck, Clock, MapPin, Package as PackageIcon, Check } from "lucide-react";
import { useResource } from "@/hooks/useResource";
import { useLangValue } from "@/hooks/useLang";
import { t } from "@/lib/i18n";
import useSEO from "@/hooks/useSEO";
import CmsPageHero from "@/components/public/CmsPageHero";
import SectionHeading from "@/components/public/SectionHeading";
import Reveal from "@/components/public/Reveal";
import CtaBand from "@/components/public/CtaBand";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { formatCurrency } from "@/utils/formatters";

const HERO = "https://images.unsplash.com/photo-1552733407-5d5c46c3bb3b?q=80&w=2000&auto=format&fit=crop";

function PackageCard({ p, lang }) {
  const includes = Array.isArray(p.includes) ? p.includes.slice(0, 3) : [];
  return (
    <Reveal className="h-full">
      <Link to={`/packages/${p.slug}`} data-testid={`package-card-${p.slug}`}
        className="group flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-card transition hover:-translate-y-1 hover:shadow-[var(--shadow-lift)]">
        <div className="relative h-44 overflow-hidden bg-primary">
          <div className="absolute inset-0 bg-cover bg-center transition duration-500 group-hover:scale-105"
            style={p.image_url ? { backgroundImage: `url('${p.image_url}')` } : undefined} aria-hidden="true" />
          {p.days ? (
            <span className="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full bg-black/55 px-2.5 py-1 text-[11px] font-semibold text-white backdrop-blur-sm">
              <Clock size={12} /> {p.days} {t("packages.days", lang)}
            </span>
          ) : null}
        </div>
        <div className="flex flex-1 flex-col p-5">
          {p.destination ? (
            <span className="inline-flex items-center gap-1 text-[11.5px] font-semibold uppercase tracking-wide text-primary">
              <MapPin size={12} /> {p.destination}
            </span>
          ) : null}
          <h3 className="mt-1.5 font-fraunces text-[20px] leading-snug text-foreground">{p.name}</h3>
          {p.description ? (
            <p className="mt-2 line-clamp-2 text-[13.5px] leading-relaxed text-muted-foreground">{p.description}</p>
          ) : null}
          {includes.length ? (
            <ul className="mt-3 space-y-1.5">
              {includes.map((inc, i) => (
                <li key={i} className="flex items-start gap-2 text-[12.5px] text-foreground/80">
                  <Check size={13} className="mt-0.5 shrink-0 text-primary" /> {inc}
                </li>
              ))}
            </ul>
          ) : null}
          <div className="mt-auto flex items-end justify-between gap-3 pt-4">
            <div>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{t("packages.from", lang)}</p>
              <p className="font-fraunces text-[19px] tabular-nums text-foreground">{formatCurrency(p.price_from || 0)}</p>
            </div>
            <span className="inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-primary">
              {t("packages.cta", lang)} <ArrowRight size={13} className="transition group-hover:translate-x-1" />
            </span>
          </div>
        </div>
      </Link>
    </Reveal>
  );
}

export default function Packages() {
  const lang = useLangValue();
  const { data, loading, error, reload } = useResource("/public/packages");
  const rows = Array.isArray(data) ? data : [];

  useSEO({
    title: lang === "en" ? "Tour Packages Java–Bali" : "Paket Wisata Jawa–Bali",
    description: t("packages.subtitle", lang),
    image: HERO,
    keywords: "paket wisata bali, paket tour jawa, sewa hiace paket wisata, tour package bali",
    jsonLd: rows.length ? {
      "@context": "https://schema.org",
      "@type": "ItemList",
      name: t("packages.title", lang),
      itemListElement: rows.slice(0, 20).map((p, i) => ({
        "@type": "ListItem", position: i + 1, name: p.name,
        url: `${window.location.origin}/packages/${p.slug}`,
      })),
    } : undefined,
  });

  return (
    <div>
      <CmsPageHero slug="packages" eyebrow={t("nav.packages", lang)} title={t("packages.title", lang)}
        subtitle={t("packages.subtitle", lang)} image={HERO}
        breadcrumb={[{ label: t("nav.home", lang), to: "/" }, { label: t("nav.packages", lang) }]} />

      <section className="relative overflow-hidden">
        <div className="glow-orb h-80 w-80 left-[-60px] top-24" style={{ background: "hsla(var(--accent) / 0.13)" }} aria-hidden="true" />
        <div className="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
          <SectionHeading eyebrow={lang === "en" ? "Choose" : "Pilih"}
            title={lang === "en" ? "Packages curated by our operations team" : "Paket yang disusun tim operasional kami"}
            subtitle={lang === "en"
              ? "Every package is priced from the same engine used for corporate invoices — no hidden numbers."
              : "Setiap paket dihitung dengan mesin harga yang sama dengan tagihan korporat — tanpa angka tersembunyi."} />

          <div className="mt-8">
            {loading ? <LoadingState testId="packages-loading" />
              : error ? <ErrorState message={error} onRetry={reload} testId="packages-error" />
              : rows.length === 0 ? (
                <EmptyState testId="packages-empty" title={t("packages.empty", lang)}
                  description={lang === "en"
                    ? "Meanwhile, tell us your plan and we will build a custom itinerary."
                    : "Sementara itu, ceritakan rencana Anda dan kami susun rangkaian khusus."}
                  action={<Link to="/quotation" className="primary-button" data-testid="packages-empty-cta">
                    <CalendarCheck size={14} /> {t("nav.quotation", lang)}
                  </Link>} />
              ) : (
                <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3" data-testid="packages-grid">
                  {rows.map((p) => <PackageCard key={p.id || p.slug} p={p} lang={lang} />)}
                </div>
              )}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-20 sm:px-6 lg:px-8">
        <Reveal>
          <CtaBand testId="packages-cta-band"
            eyebrow={lang === "en" ? "Plan" : "Rencanakan"}
            title={lang === "en" ? "Need a package tailored to your group?" : "Butuh paket yang disesuaikan rombongan Anda?"}
            subtitle={lang === "en"
              ? "Send your dates and headcount — we will reply with an official quotation."
              : "Kirim tanggal & jumlah peserta — kami balas dengan penawaran resmi."}
            primary={{ to: "/quotation", label: t("nav.quotation", lang), testId: "packages-cta-quotation" }}
            secondary={{ to: "/booking", label: t("nav.booking", lang), icon: PackageIcon, testId: "packages-cta-booking" }} />
        </Reveal>
      </section>
    </div>
  );
}

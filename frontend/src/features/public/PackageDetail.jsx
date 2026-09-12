import { useEffect } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, Check, Clock, Loader2, MapPin, Users, CalendarCheck, MessageCircle } from "lucide-react";
import { useResource } from "@/hooks/useResource";
import { useLangValue } from "@/hooks/useLang";
import { t } from "@/lib/i18n";
import useSEO, { absUrl, stripHtml } from "@/hooks/useSEO";
import { trackContentView } from "@/lib/contentView";
import useSlugRedirect from "@/hooks/useSlugRedirect";
import PreviewBanner from "@/components/public/PreviewBanner";
import Reveal from "@/components/public/Reveal";
import CtaBand from "@/components/public/CtaBand";
import { formatCurrency } from "@/utils/formatters";

export default function PackageDetail() {
  const { slug } = useParams();
  const [params] = useSearchParams();
  const preview = params.get("preview") || "";
  const lang = useLangValue();
  const path = `/public/packages/${slug}${preview ? `?preview=${encodeURIComponent(preview)}` : ""}`;
  const { data: p, loading, error } = useResource(path);

  // CMS-12: slug bisa berubah. Bila slug ini tidak ditemukan, cari pengalihannya lebih dulu —
  // tautan lama dari Google/WhatsApp tidak boleh menjadi jalan buntu.
  const notFound = Boolean(!loading && (error || !p));
  const { checking: redirecting } = useSlugRedirect(notFound);

  // CMS-08: hitung tampilan + simpan jejak konten (untuk atribusi lead/pesanan).
  useEffect(() => {
    if (p?.slug && !p?.preview) {
      trackContentView({ kind: "package", slug: p.slug, title: p.name, path: `/packages/${p.slug}` });
    }
  }, [p?.slug, p?.preview, p?.name]);

  const seoDesc = p ? (p.meta_description || stripHtml(p.description)) : undefined;
  useSEO({
    title: p ? (p.meta_title || p.name) : undefined,
    description: seoDesc,
    image: p ? absUrl(p.og_image || p.image_url) : undefined,
    canonical: p?.canonical || undefined,
    type: "product",
    jsonLd: p ? {
      "@context": "https://schema.org",
      "@type": "Product",
      name: p.name,
      description: seoDesc,
      image: p.og_image || p.image_url || undefined,
      brand: { "@type": "Brand", name: "RahazaTrans" },
      offers: {
        "@type": "Offer", priceCurrency: "IDR", price: p.price_from || 0,
        availability: "https://schema.org/InStock",
        url: typeof window !== "undefined" ? window.location.href : undefined,
      },
    } : undefined,
  });

  if (loading) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center pt-24 text-muted-foreground" data-testid="package-detail-loading">
        <Loader2 className="mr-2 animate-spin" /> {t("common.loading", lang)}
      </div>
    );
  }
  if (redirecting) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center pt-24 text-muted-foreground" data-testid="package-detail-redirecting">
        <Loader2 className="mr-2 animate-spin" /> {t("common.loading", lang)}
      </div>
    );
  }
  if (error || !p) {
    return (
      <div className="flex min-h-[70vh] flex-col items-center justify-center gap-3 pt-24" data-testid="package-detail-error">
        <p className="text-muted-foreground">{t("common.not_found", lang)}</p>
        <Link to="/packages" className="rounded-full bg-primary px-4 py-2 text-[13px] font-semibold text-primary-foreground" data-testid="package-detail-back">
          {t("nav.packages", lang)}
        </Link>
      </div>
    );
  }

  const includes = Array.isArray(p.includes) ? p.includes : [];
  const bookingHref = `/booking?destination=${encodeURIComponent(p.destination || "")}`;

  return (
    <div>
      {p.preview ? <PreviewBanner status={p.status} testId="package-preview-banner" /> : null}

      <section className="relative flex min-h-[52vh] items-end overflow-hidden bg-primary">
        <div className="absolute inset-0 bg-cover bg-center"
          style={p.image_url ? { backgroundImage: `url('${p.image_url}')` } : undefined} aria-hidden="true" />
        <div className="absolute inset-0" style={{ background: "var(--gradient-hero)" }} aria-hidden="true" />
        <div className="relative mx-auto w-full max-w-5xl px-5 pb-12 pt-32">
          <Link to="/packages" className="inline-flex items-center gap-1.5 text-[12.5px] text-white/75 hover:text-white" data-testid="package-breadcrumb">
            <ArrowLeft size={14} /> {t("nav.packages", lang)}
          </Link>
          <div className="mt-4 flex flex-wrap items-center gap-3 text-[12px] text-white/85">
            {p.destination ? <span className="inline-flex items-center gap-1"><MapPin size={13} /> {p.destination}</span> : null}
            {p.days ? <span className="inline-flex items-center gap-1"><Clock size={13} /> {p.days} {t("packages.days", lang)}</span> : null}
            {p.pax_max ? <span className="inline-flex items-center gap-1"><Users size={13} /> {p.pax_min || 1}–{p.pax_max} pax</span> : null}
          </div>
          <h1 className="mt-3 font-fraunces text-4xl leading-tight text-white sm:text-5xl" data-testid="package-title">{p.name}</h1>
          <p className="mt-4 text-[15px] text-white/85">
            {t("packages.from", lang)} <span className="font-fraunces text-2xl text-white tabular-nums" data-testid="package-price">{formatCurrency(p.price_from || 0)}</span>
          </p>
        </div>
      </section>

      <section className="mx-auto grid w-full max-w-5xl gap-8 px-5 py-12 lg:grid-cols-[1.5fr_1fr]">
        <div>
          {p.description ? (
            <p className="text-[16px] leading-[1.85] text-foreground/85" data-testid="package-description">{p.description}</p>
          ) : null}
          {includes.length ? (
            <div className="mt-8" data-testid="package-includes">
              <h2 className="font-fraunces text-2xl text-foreground">{t("packages.includes", lang)}</h2>
              <ul className="mt-4 grid gap-2.5 sm:grid-cols-2">
                {includes.map((inc, i) => (
                  <li key={i} className="flex items-start gap-2 rounded-xl border border-border bg-card px-3.5 py-2.5 text-[13.5px] text-foreground/85">
                    <Check size={15} className="mt-0.5 shrink-0 text-primary" /> {inc}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            /* EMPTY STATE — paket tanpa rincian "Termasuk" tetap harus menjual: pengunjung
               diarahkan meminta rincian resmi, bukan dibiarkan menebak isi paket. */
            <div className="mt-8 rounded-2xl border border-dashed border-border bg-card p-5" data-testid="package-includes-empty">
              <h2 className="font-fraunces text-2xl text-foreground">{t("packages.includes", lang)}</h2>
              <p className="mt-2 text-[13.5px] leading-relaxed text-muted-foreground">
                {lang === "en"
                  ? "The inclusion list for this package isn't published yet. Request a quotation and our team will send the itemised scope (vehicle, driver, fuel, tolls & parking)."
                  : "Belum ada rincian yang ditayangkan untuk paket ini. Minta penawaran dan tim kami mengirim rincian resminya (unit, sopir, bahan bakar, tol & parkir)."}
              </p>
              <Link to="/quotation" data-testid="package-includes-empty-cta"
                className="mt-3 inline-flex items-center gap-2 rounded-full border border-border px-4 py-2 text-[13px] font-semibold text-foreground transition hover:bg-secondary">
                <MessageCircle size={14} /> {t("nav.quotation", lang)}
              </Link>
            </div>
          )}

          {p.destination_ref ? (
            <Link to={`/destinations/${p.destination_ref.slug}`} data-testid="package-destination-link"
              className="mt-8 flex items-center gap-4 rounded-2xl border border-border bg-card p-4 transition hover:-translate-y-0.5 hover:shadow-md">
              <div className="h-16 w-24 shrink-0 rounded-xl bg-cover bg-center bg-secondary"
                style={p.destination_ref.hero_image ? { backgroundImage: `url('${p.destination_ref.hero_image}')` } : undefined} aria-hidden="true" />
              <div>
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{t("nav.destinations", lang)}</p>
                <p className="font-fraunces text-[17px] text-foreground">{p.destination_ref.name}</p>
              </div>
            </Link>
          ) : null}
        </div>

        <aside className="lg:sticky lg:top-28 lg:self-start">
          <div className="rounded-2xl border border-border bg-card p-5 shadow-[var(--shadow-lift)]">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{t("packages.from", lang)}</p>
            <p className="mt-1 font-fraunces text-3xl tabular-nums text-foreground">{formatCurrency(p.price_from || 0)}</p>
            <Link to={bookingHref} data-testid="package-book-cta"
              className="cta-shine mt-4 flex w-full items-center justify-center gap-2 rounded-full px-4 py-3 text-[13.5px] font-semibold text-primary-foreground"
              style={{ background: "var(--gradient-cta)" }}>
              <CalendarCheck size={16} /> {t("packages.cta", lang)}
            </Link>
            <Link to="/quotation" data-testid="package-quote-cta"
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-full border border-border px-4 py-3 text-[13.5px] font-semibold text-foreground transition hover:bg-secondary">
              <MessageCircle size={15} /> {t("nav.quotation", lang)}
            </Link>
          </div>
        </aside>
      </section>

      <section className="mx-auto w-full max-w-5xl px-5 pb-20">
        <Reveal>
          <CtaBand testId="package-cta-band"
            eyebrow={lang === "en" ? "Ready" : "Siap"}
            title={lang === "en" ? "Lock your dates before the peak season" : "Amankan tanggal sebelum musim padat"}
            subtitle={lang === "en"
              ? "Availability is checked live against our fleet schedule."
              : "Ketersediaan dicek langsung ke jadwal armada kami."}
            primary={{ to: bookingHref, label: t("nav.booking", lang), testId: "package-cta-booking" }}
            secondary={{ to: "/packages", label: t("nav.packages", lang), icon: ArrowLeft, testId: "package-cta-list" }} />
        </Reveal>
      </section>
    </div>
  );
}

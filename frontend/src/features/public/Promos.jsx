import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Copy, Check, Tag, CalendarCheck, Ticket, Info } from "lucide-react";
import { useResource } from "@/hooks/useResource";
import { useLangValue } from "@/hooks/useLang";
import { t, bi } from "@/lib/i18n";
import useSEO from "@/hooks/useSEO";
import CmsPageHero from "@/components/public/CmsPageHero";
import SectionHeading from "@/components/public/SectionHeading";
import Reveal from "@/components/public/Reveal";
import CtaBand from "@/components/public/CtaBand";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { formatCurrency } from "@/utils/formatters";

const HERO = "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?q=80&w=2000&auto=format&fit=crop";

function discountLabel(p, lang) {
  const value = Number(p.discount_value || 0);
  if (String(p.discount_type) === "percent") return `${value}%`;
  return formatCurrency(value);
}

function PromoCard({ p, lang }) {
  const [copied, setCopied] = useState(false);
  const code = String(p.code || "").toUpperCase();
  const terms = Array.isArray(p.terms) ? p.terms : [];

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
    } catch {
      // Fallback browser lama / izin clipboard ditolak: tetap beri tahu kodenya.
    }
    setCopied(true);
    toast.success(`${t("promo.copied", lang)}: ${code}`);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Reveal className="h-full">
      <article className={`flex h-full flex-col overflow-hidden rounded-2xl border bg-card transition hover:-translate-y-1 hover:shadow-[var(--shadow-lift)] ${p.sold_out ? "border-dashed border-border opacity-70" : "border-border"}`}
        data-testid={`promo-card-${code}`}>
        <div className="flex items-start justify-between gap-3 border-b border-dashed border-border bg-secondary/50 px-5 py-4">
          <div>
            <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-primary">
              <Ticket size={12} /> {t("nav.promo", lang)}
            </span>
            <h3 className="mt-1.5 font-fraunces text-[21px] leading-snug text-foreground">{p.title || code}</h3>
          </div>
          <span className="shrink-0 rounded-xl bg-primary px-3 py-2 text-center font-fraunces text-[19px] leading-none text-primary-foreground">
            {discountLabel(p, lang)}
            <span className="mt-0.5 block text-[9.5px] font-semibold uppercase tracking-wider opacity-80">
              {lang === "en" ? "off" : "hemat"}
            </span>
          </span>
        </div>

        <div className="flex flex-1 flex-col px-5 py-4">
          {p.description ? (
            <p className="text-[13.5px] leading-relaxed text-muted-foreground">{p.description}</p>
          ) : null}

          {terms.length ? (
            <div className="mt-3" data-testid={`promo-terms-${code}`}>
              <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-foreground/70">
                <Info size={12} /> {t("promo.terms", lang)}
              </p>
              <ul className="mt-1.5 flex flex-wrap gap-1.5">
                {terms.map((term, i) => (
                  <li key={i} className="rounded-full bg-secondary px-2.5 py-1 text-[11.5px] font-medium text-foreground/85">{term}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="mt-auto pt-5">
            <div className="flex items-center gap-2">
              <code className="flex-1 rounded-xl border border-dashed border-primary/45 bg-primary/5 px-3 py-2.5 text-center font-mono text-[15px] font-bold tracking-[0.14em] text-primary"
                data-testid={`promo-code-${code}`}>{code}</code>
              <button type="button" onClick={copy} disabled={p.sold_out}
                className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-border text-foreground transition hover:bg-secondary disabled:opacity-50"
                title={t("promo.copy", lang)} aria-label={t("promo.copy", lang)}
                data-testid={`promo-copy-${code}`}>
                {copied ? <Check size={16} className="text-[#1E8E5A]" /> : <Copy size={16} />}
              </button>
            </div>

            {p.sold_out ? (
              <p className="mt-3 rounded-xl bg-secondary px-3 py-2 text-center text-[12.5px] font-semibold text-muted-foreground"
                data-testid={`promo-soldout-${code}`}>{t("promo.sold_out", lang)}</p>
            ) : (
              <Link to={`/booking?promo=${encodeURIComponent(code)}`} data-testid={`promo-use-${code}`}
                className="cta-shine mt-3 flex w-full items-center justify-center gap-2 rounded-full px-4 py-2.5 text-[13px] font-semibold text-primary-foreground"
                style={{ background: "var(--gradient-cta)" }}>
                <CalendarCheck size={15} /> {t("promo.use", lang)}
              </Link>
            )}

            <div className="mt-2.5 flex items-center justify-between text-[11.5px] text-muted-foreground">
              {p.valid_until ? <span>{bi("s/d", "until", lang)} {String(p.valid_until).slice(0, 10)}</span> : <span />}
              {typeof p.quota_left === "number" && !p.sold_out ? (
                <span className="tabular-nums" data-testid={`promo-quota-${code}`}>
                  {p.quota_left} {t("promo.quota_left", lang)}
                </span>
              ) : null}
            </div>
          </div>
        </div>
      </article>
    </Reveal>
  );
}

export default function Promos() {
  const lang = useLangValue();
  const { data, loading, error, reload } = useResource("/public/promos");
  const rows = Array.isArray(data) ? data : [];

  useSEO({
    title: lang === "en" ? "Deals & Promo Codes" : "Promo & Penawaran Berjalan",
    description: t("promo.subtitle", lang),
    image: HERO,
    keywords: "promo sewa hiace, diskon sewa mobil bali, kode promo travel, promo paket wisata",
  });

  return (
    <div>
      <CmsPageHero slug="promo" eyebrow={t("nav.promo", lang)} title={t("promo.title", lang)}
        subtitle={t("promo.subtitle", lang)} image={HERO}
        breadcrumb={[{ label: t("nav.home", lang), to: "/" }, { label: t("nav.promo", lang) }]} />

      <section className="relative overflow-hidden">
        <div className="glow-orb h-72 w-72 right-[-40px] top-20" style={{ background: "hsla(var(--accent) / 0.15)" }} aria-hidden="true" />
        <div className="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
          <SectionHeading eyebrow={lang === "en" ? "Save" : "Hemat"}
            title={lang === "en" ? "Codes that really work at checkout" : "Kode yang benar-benar berlaku saat checkout"}
            subtitle={lang === "en"
              ? "Each condition below is enforced by the booking engine — minimum days, quota, vehicle type."
              : "Setiap syarat di bawah ditegakkan mesin pemesanan — minimal hari, kuota, hingga tipe armada."} />

          <div className="mt-8">
            {loading ? <LoadingState testId="promos-loading" />
              : error ? <ErrorState message={error} onRetry={reload} testId="promos-error" />
              : rows.length === 0 ? (
                <EmptyState testId="promos-empty" title={t("promo.empty", lang)}
                  description={lang === "en"
                    ? "Follow our WhatsApp channel to hear about the next deal first."
                    : "Hubungi kami lewat WhatsApp untuk mendapat kabar promo berikutnya lebih dulu."}
                  action={<Link to="/contact" className="primary-button" data-testid="promos-empty-cta">
                    <Tag size={14} /> {t("nav.contact", lang)}
                  </Link>} />
              ) : (
                <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3" data-testid="promos-grid">
                  {rows.map((p) => <PromoCard key={p.code} p={p} lang={lang} />)}
                </div>
              )}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-20 sm:px-6 lg:px-8">
        <Reveal>
          <CtaBand testId="promo-cta-band"
            eyebrow={lang === "en" ? "Book" : "Pesan"}
            title={lang === "en" ? "Apply your code while units are still open" : "Pakai kode selagi unit masih tersedia"}
            subtitle={lang === "en"
              ? "The discount is calculated by the same engine that issues your invoice."
              : "Diskon dihitung mesin yang sama dengan penerbit tagihan Anda."}
            primary={{ to: "/booking", label: t("nav.booking", lang), testId: "promo-cta-booking" }}
            secondary={{ to: "/packages", label: t("nav.packages", lang), icon: Ticket, testId: "promo-cta-packages" }} />
        </Reveal>
      </section>
    </div>
  );
}

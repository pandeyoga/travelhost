import { Link, useParams } from "react-router-dom";
import { Loader2, ArrowLeft, ArrowRight, Clock, CalendarDays, Tag, Bus } from "lucide-react";
import { useResource } from "@/hooks/useResource";
import useSEO, { absUrl, stripHtml } from "@/hooks/useSEO";
import Reveal from "@/components/public/Reveal";
import CtaBand from "@/components/public/CtaBand";
import ArticleBody from "@/components/public/ArticleBody";
import useSlugRedirect from "@/hooks/useSlugRedirect";
import { useLangValue } from "@/hooks/useLang";
import { bi, t as tr } from "@/lib/i18n";
import { formatDate } from "@/utils/formatters";

function RelatedCard({ a }) {
  return (
    <Link to={`/blog/${a.slug}`} data-testid={`related-${a.slug}`}
      className="group flex w-[260px] flex-shrink-0 snap-start flex-col overflow-hidden rounded-2xl border border-border bg-card transition hover:-translate-y-1 hover:shadow-lg sm:w-auto sm:flex-shrink">
      <div className="relative h-36 overflow-hidden bg-primary">
        <div className="absolute inset-0 bg-cover bg-center transition duration-500 group-hover:scale-105"
          style={a.cover_image ? { backgroundImage: `url('${a.cover_image}')` } : undefined} aria-hidden="true" />
      </div>
      <div className="flex flex-1 flex-col p-4">
        {a.category ? <span className="text-[11px] font-semibold uppercase tracking-wide text-primary">{a.category}</span> : null}
        <h3 className="mt-1 font-fraunces text-[17px] leading-snug text-foreground">{a.title}</h3>
        <span className="mt-3 inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-primary">
          {bi("Baca", "Read")} <ArrowRight size={13} className="transition group-hover:translate-x-1" />
        </span>
      </div>
    </Link>
  );
}

export default function BlogDetail() {
  const lang = useLangValue();
  const { slug } = useParams();
  const { data: a, loading, error } = useResource(`/public/articles/${slug}`);
  const { data: allData } = useResource("/public/articles");

  // CMS-12: artikel yang slug-nya pernah diubah TIDAK boleh mati 404 — cari pengalihannya.
  const notFound = Boolean(!loading && (error || !a));
  const { checking: redirecting } = useSlugRedirect(notFound);

  // CMS-02 SEO: Article JSON-LD + OG — dipanggil UNCONDITIONALLY (rules-of-hooks).
  const seoTags = Array.isArray(a?.tags) ? a.tags : [];
  const seoTitle = a ? (a.meta_title || a.title) : undefined;
  const seoDesc = a ? (a.meta_description || stripHtml(a.excerpt || a.body)) : undefined;
  const seoImage = a ? absUrl(a.og_image || a.cover_image) : undefined;
  useSEO({
    title: seoTitle,
    description: seoDesc,
    image: seoImage,
    canonical: a?.canonical || undefined,
    type: "article",
    keywords: seoTags.length ? seoTags.join(", ") : undefined,
    jsonLd: a ? {
      "@context": "https://schema.org",
      "@type": "Article",
      headline: a.title,
      description: seoDesc,
      image: seoImage || undefined,
      datePublished: a.published_at || undefined,
      dateModified: a.updated_at || a.published_at || undefined,
      author: { "@type": "Person", name: a.author || "RahazaTrans" },
      publisher: {
        "@type": "Organization",
        name: "RahazaTrans",
        logo: { "@type": "ImageObject", url: absUrl("/logo.png") },
      },
      articleSection: a.category,
      keywords: seoTags.length ? seoTags.join(", ") : undefined,
    } : undefined,
  });

  if (loading) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center pt-24 text-muted-foreground" data-testid="blog-detail-loading">
        <Loader2 className="mr-2 animate-spin" /> {tr("common.loading", lang)}
      </div>
    );
  }
  if (redirecting) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center pt-24 text-muted-foreground" data-testid="blog-detail-redirecting">
        <Loader2 className="mr-2 animate-spin" /> {bi("Mengalihkan ke alamat baru…", "Redirecting to the new address…", lang)}
      </div>
    );
  }
  if (error || !a) {
    return (
      <div className="flex min-h-[70vh] flex-col items-center justify-center gap-3 pt-24" data-testid="blog-detail-error">
        <p className="text-muted-foreground">{tr("common.not_found", lang)}</p>
        <Link to="/blog" className="rounded-full bg-primary px-4 py-2 text-[13px] font-semibold text-primary-foreground">{bi("Kembali ke Blog", "Back to blog", lang)}</Link>
      </div>
    );
  }

  const related = (Array.isArray(allData) ? allData : [])
    .filter((x) => x.slug !== a.slug && x.category === a.category)
    .slice(0, 3);
  const tags = Array.isArray(a.tags) ? a.tags : [];

  return (
    <div>
      {/* HERO */}
      <section className="relative flex min-h-[52vh] items-end overflow-hidden bg-primary">
        <div className="absolute inset-0 bg-cover bg-center" style={a.cover_image ? { backgroundImage: `url('${a.cover_image}')` } : undefined} aria-hidden="true" />
        <div className="absolute inset-0" style={{ background: "linear-gradient(180deg, rgba(8,14,32,0.45) 0%, rgba(8,14,32,0.35) 40%, rgba(8,14,32,0.92) 100%)" }} aria-hidden="true" />
        <div className="pointer-events-none absolute inset-0 bg-noise opacity-[0.06] mix-blend-overlay" aria-hidden="true" />
        <div className="relative mx-auto w-full max-w-3xl px-5 pb-12 pt-32">
          <Link to="/blog" className="inline-flex items-center gap-1.5 text-[12.5px] text-white/75 hover:text-white">
            <ArrowLeft size={14} /> {bi("Semua artikel", "All articles", lang)}
          </Link>
          <div className="mt-4 flex flex-wrap items-center gap-3 text-[12px] text-white/80">
            {a.category ? <span className="rounded-full bg-accent/90 px-2.5 py-0.5 font-semibold uppercase tracking-wide text-accent-foreground">{a.category}</span> : null}
            <span className="inline-flex items-center gap-1"><CalendarDays size={13} /> {formatDate(a.published_at)}</span>
            {a.read_minutes ? <span className="inline-flex items-center gap-1"><Clock size={13} /> {a.read_minutes} {bi("mnt baca", "min read", lang)}</span> : null}
            <span>· {a.author}</span>
          </div>
          <h1 className="mt-3 font-fraunces text-4xl leading-tight text-white sm:text-5xl">{a.title}</h1>
        </div>
      </section>

      {/* BODY */}
      <article className="mx-auto w-full max-w-[68ch] px-5 py-12" data-testid="blog-detail-body">
        <p className="text-[18px] font-medium leading-relaxed text-foreground">{a.excerpt}</p>
        {/* CMS-09: isi kaya (HTML tersanitasi server) ATAU teks polos artikel lama. */}
        <ArticleBody body={a.body} testId="blog-body" />

        {tags.length ? (
          <div className="mt-8 flex flex-wrap items-center gap-2 border-t border-border pt-6">
            <Tag size={14} className="text-muted-foreground" />
            {tags.map((t) => (
              <span key={t} className="rounded-full bg-secondary px-3 py-1 text-[12px] font-medium text-foreground">#{t}</span>
            ))}
          </div>
        ) : null}

        {/* CTA conversion — dulu memakai `bg-gradient-to-br from-primary to-[color:var(--primary)]`.
            Token tema berisi TRIPLET HSL, jadi `color:var(--primary)` INVALID dan browser
            membuang seluruh `background-image`: panelnya jadi transparan dan teks
            `text-primary-foreground` (putih) hilang di atas kertas putih. Sekarang memakai
            komponen CtaBand (latar solid `bg-primary` + dekorasi radial yang valid). */}
        <Reveal className="mt-10">
          <CtaBand
            testId="blog-cta-band"
            eyebrow={bi("Rencanakan", "Plan", lang)}
            title={bi("Siap merencanakan perjalanan Anda?", "Ready to plan your journey?", lang)}
            subtitle={bi("Dapatkan estimasi biaya transparan dan penawaran resmi dari tim RahazaTrans.", "Get a transparent cost estimate and an official quotation from the RahazaTrans team.", lang)}
            primary={{ to: "/quotation", label: tr("nav.quotation", lang), testId: "blog-cta-quotation" }}
            secondary={{ to: "/fleet", label: bi("Lihat Armada", "See our fleet", lang), icon: Bus, testId: "blog-cta-fleet" }}
          />
        </Reveal>
      </article>

      {/* RELATED */}
      {related.length === 0 ? null : (
        <section className="mx-auto w-full max-w-5xl px-5 pb-16" data-testid="blog-related">
          <h2 className="font-fraunces text-2xl text-foreground">{bi("Artikel terkait", "Related articles", lang)}</h2>
          <div className="mt-5 flex snap-x gap-5 overflow-x-auto pb-2 sm:grid sm:grid-cols-3 sm:overflow-visible">
            {related.map((r) => <RelatedCard key={r.id} a={r} />)}
          </div>
        </section>
      )}
    </div>
  );
}

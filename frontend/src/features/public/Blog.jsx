import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Loader2, Clock, CalendarDays } from "lucide-react";
import { useResource } from "@/hooks/useResource";
import CmsPageHero from "@/components/public/CmsPageHero";
import Reveal from "@/components/public/Reveal";
import SectionHeading from "@/components/public/SectionHeading";
import { formatDate } from "@/utils/formatters";
import useSEO from "@/hooks/useSEO";
import { useLangValue } from "@/hooks/useLang";
import { bi, t as tr } from "@/lib/i18n";

const ALL = "Semua";

function Badge({ children }) {
  return (
    <span className="inline-flex items-center rounded-full bg-accent/90 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-accent-foreground backdrop-blur-sm">
      {children}
    </span>
  );
}

function Meta({ a, tone = "muted" }) {
  const cls = tone === "light" ? "text-white/75" : "text-muted-foreground";
  return (
    <p className={`flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] ${cls}`}>
      <span className="inline-flex items-center gap-1"><CalendarDays size={13} /> {formatDate(a.published_at)}</span>
      {a.read_minutes ? <span className="inline-flex items-center gap-1"><Clock size={13} /> {a.read_minutes} {bi("mnt baca", "min read")}</span> : null}
    </p>
  );
}

function ArticleCard({ a }) {
  return (
    <Link to={`/blog/${a.slug}`} data-testid={`blog-card-${a.slug}`}
      className="group flex h-full flex-col overflow-hidden rounded-2xl card-premium lift">
      <div className="relative h-48 overflow-hidden">
        <div className="absolute inset-0 bg-primary bg-cover bg-center transition duration-700 ease-out group-hover:scale-110"
          style={a.cover_image ? { backgroundImage: `url('${a.cover_image}')` } : undefined} aria-hidden="true" />
        {a.category ? <span className="absolute left-3 top-3"><Badge>{a.category}</Badge></span> : null}
      </div>
      <div className="flex flex-1 flex-col p-5">
        <Meta a={a} />
        <h3 className="mt-2 font-fraunces text-xl leading-snug text-foreground">{a.title}</h3>
        <p className="mt-2 line-clamp-2 text-[13.5px] leading-relaxed text-muted-foreground">{a.excerpt}</p>
        <span className="mt-4 inline-flex items-center gap-1.5 text-[13px] font-semibold text-primary">
          {bi("Baca artikel", "Read article")} <ArrowRight size={14} className="transition group-hover:translate-x-1" />
        </span>
      </div>
    </Link>
  );
}

function FeaturedStory({ a, lang }) {
  return (
    <Reveal>
      <Link to={`/blog/${a.slug}`} data-testid={`blog-featured-${a.slug}`}
        className="group relative grid overflow-hidden rounded-3xl bg-primary text-primary-foreground shadow-[var(--shadow-glass)] lift md:grid-cols-2">
        <div className="relative min-h-[260px] overflow-hidden md:min-h-[400px]">
          <div className="absolute inset-0 bg-cover bg-center transition duration-700 group-hover:scale-105"
            style={a.cover_image ? { backgroundImage: `url('${a.cover_image}')` } : undefined} aria-hidden="true" />
          <div className="absolute inset-0 md:hidden" style={{ background: "linear-gradient(180deg, rgba(8,14,32,0.1) 30%, rgba(8,14,32,0.85) 100%)" }} aria-hidden="true" />
        </div>
        <div className="flex flex-col justify-center gap-3 p-7 md:p-10">
          <div className="flex items-center gap-2">
            <Badge>{bi("Sorotan", "Featured", lang)}</Badge>
            {a.category ? <span className="text-[12px] font-medium text-primary-foreground/70">{a.category}</span> : null}
          </div>
          <h2 className="font-fraunces text-3xl leading-[1.1] text-primary-foreground md:text-4xl">{a.title}</h2>
          <p className="text-[14.5px] leading-relaxed text-primary-foreground/80">{a.excerpt}</p>
          <Meta a={a} tone="light" />
          <span className="mt-2 inline-flex w-fit items-center gap-2 rounded-full bg-primary-foreground px-5 py-2.5 text-[13.5px] font-semibold text-primary transition group-hover:gap-3">
            {bi("Baca cerita", "Read the story", lang)} <ArrowRight size={16} />
          </span>
        </div>
      </Link>
    </Reveal>
  );
}

export default function Blog() {
  const lang = useLangValue();
  const { data, loading, error, reload } = useResource("/public/articles");
  const [cat, setCat] = useState(ALL);
  const all = Array.isArray(data) ? data : [];

  const categories = useMemo(() => {
    const arr = Array.isArray(data) ? data : [];
    const set = new Set(arr.map((a) => a.category).filter(Boolean));
    return [ALL, ...Array.from(set)];
  }, [data]);

  const featured = all.find((a) => a.featured) || all[0] || null;
  const grid = cat === ALL ? all.filter((a) => a.id !== featured?.id) : all.filter((a) => a.category === cat);

  const CatButtons = ({ orientation = "row" }) => (
    <div className={orientation === "row" ? "flex gap-2 overflow-x-auto pb-1" : "flex flex-col gap-1"} data-testid="blog-categories">
      {categories.map((c) => (
        <button key={c} onClick={() => setCat(c)} data-testid={`blog-cat-${c}`}
          className={`whitespace-nowrap rounded-full px-4 py-2 text-left text-[13px] font-semibold transition ${cat === c ? "text-primary-foreground shadow-[var(--shadow-lift)]" : "border border-border bg-card text-foreground hover:border-[hsla(var(--glass-border))]"}`}
          style={cat === c ? { background: "var(--gradient-cta)" } : undefined}>
          {c === ALL ? bi(ALL, "All", lang) : c}
        </button>
      ))}
    </div>
  );

  // CMS-02 SEO: meta dasar halaman index Blog.
  useSEO({
    title: bi("Blog — Tips & Inspirasi Perjalanan", "Blog — Travel Tips & Inspiration", lang),
    description: bi("Panduan praktis menyusun trip keluarga, korporat, dan wisata rombongan lintas Jawa–Bali dari tim RahazaTrans.", "Practical guides for family, corporate and group trips across Java–Bali from the RahazaTrans team.", lang),
    image: "https://images.unsplash.com/photo-1488646953014-85cb44e25828?q=80&w=2000&auto=format&fit=crop",
    keywords: "tips perjalanan, inspirasi wisata, panduan trip jawa bali, blog travel",
  });

  return (
    <div>
      <CmsPageHero slug="blog" eyebrow="Blog" title={bi("Tips & inspirasi perjalanan", "Travel tips & inspiration", lang)}
        subtitle={bi("Panduan praktis menyusun trip keluarga, korporat, dan wisata rombongan lintas Jawa–Bali.", "Practical guides for family, corporate and group trips across Java–Bali.", lang)}
        image="https://images.unsplash.com/photo-1488646953014-85cb44e25828?q=80&w=2000&auto=format&fit=crop"
        breadcrumb={[{ label: tr("nav.home", lang), to: "/" }, { label: "Blog" }]} />

      <section className="relative overflow-hidden">
        <div className="glow-orb h-72 w-72 right-[-50px] top-24" style={{ background: "hsla(var(--ring) / 0.12)" }} aria-hidden="true" />
        <div className="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 md:py-20">
          {loading ? (
            <div className="flex justify-center py-16 text-muted-foreground" data-testid="blog-loading"><Loader2 className="mr-2 animate-spin" /> {bi("Memuat artikel…", "Loading articles…", lang)}</div>
          ) : error ? (
            <div className="py-16 text-center" data-testid="blog-error"><p className="text-muted-foreground">{bi("Gagal memuat artikel.", "Failed to load articles.", lang)}</p><button onClick={reload} data-testid="blog-retry" className="mt-3 rounded-full bg-primary px-4 py-2 text-[13px] font-semibold text-primary-foreground">{bi("Coba lagi", "Try again", lang)}</button></div>
          ) : all.length === 0 ? (
            <div className="py-16 text-center text-muted-foreground" data-testid="blog-empty">{bi("Belum ada artikel.", "No articles yet.", lang)}</div>
          ) : (
            <>
              {cat === ALL && featured ? <FeaturedStory a={featured} lang={lang} /> : null}
              <div className="mt-8 lg:hidden"><CatButtons orientation="row" /></div>
              <div className="mt-8 grid gap-8 lg:mt-10 lg:grid-cols-[200px_1fr]">
                <aside className="hidden lg:block">
                  <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">{bi("Kategori", "Category", lang)}</p>
                  <div className="sticky top-24"><CatButtons orientation="col" /></div>
                </aside>
                <div>
                  {grid.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-border py-16 text-center text-muted-foreground" data-testid="blog-cat-empty">{bi("Belum ada artikel untuk kategori ini.", "No articles in this category yet.", lang)}</div>
                  ) : (
                    <div className="grid grid-cols-1 gap-6 sm:grid-cols-2" data-testid="blog-grid">
                      {grid.map((a, i) => <Reveal key={a.id} delay={i * 0.04}><ArticleCard a={a} /></Reveal>)}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  );
}

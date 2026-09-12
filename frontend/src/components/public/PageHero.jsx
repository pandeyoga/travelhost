import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";

// PageHero — hero band untuk halaman publik bagian dalam (token-based, theme-aware).
export default function PageHero({ title, subtitle, image, eyebrow, breadcrumb = [] }) {
  return (
    <section className="relative flex min-h-[46vh] items-end overflow-hidden bg-primary">
      <div className="absolute inset-0 bg-cover bg-center" style={image ? { backgroundImage: `url('${image}')` } : undefined} aria-hidden="true" />
      <div className="absolute inset-0" style={{ background: "var(--gradient-hero)" }} aria-hidden="true" />
      <div className="pointer-events-none absolute inset-0 bg-noise opacity-[0.06] mix-blend-overlay" aria-hidden="true" />
      <div className="relative mx-auto w-full max-w-7xl px-4 pb-12 pt-32 sm:px-6 lg:px-8">
        {breadcrumb.length ? (
          <nav className="mb-3 flex items-center gap-1.5 text-[12px] text-white/70">
            {breadcrumb.map((b, i) => (
              <span key={i} className="flex items-center gap-1.5">
                {b.to ? <Link to={b.to} className="hover:text-white">{b.label}</Link> : <span className="text-white/90">{b.label}</span>}
                {i < breadcrumb.length - 1 ? <ChevronRight size={13} className="text-white/40" /> : null}
              </span>
            ))}
          </nav>
        ) : null}
        {eyebrow ? <p className="text-[11px] uppercase tracking-[0.22em] text-white/75">{eyebrow}</p> : null}
        <h1 className="mt-2 max-w-3xl font-fraunces text-4xl leading-[1.06] text-white sm:text-5xl">{title}</h1>
        {subtitle ? <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-white/85">{subtitle}</p> : null}
      </div>
    </section>
  );
}

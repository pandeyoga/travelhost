import { Link } from "react-router-dom";
import { CalendarDays, Users, ArrowRight, Check } from "lucide-react";
import { useResource } from "@/hooks/useResource";
import { formatCurrency } from "@/utils/formatters";
import SectionHeading from "@/components/public/SectionHeading";
import Reveal from "@/components/public/Reveal";
import { useLangValue } from "@/hooks/useLang";
import { bi, t as tr } from "@/lib/i18n";

// PackageStrip.jsx — paket wisata siap pakai dari `GET /api/public/packages`.
// `price_from` adalah angka nyata yang diisi pemilik (bukan kalkulasi otomatis), karena itu
// labelnya "mulai dari" dan tetap diarahkan ke penawaran resmi untuk harga final.
export default function PackageStrip({ limit = 3 }) {
  const lang = useLangValue();
  const { data, loading, error } = useResource("/public/packages");
  const rows = (Array.isArray(data) ? data : []).slice(0, limit);

  return (
    <section className="relative overflow-hidden" data-testid="package-strip">
      <div className="glow-orb h-72 w-72 right-[-40px] top-16" style={{ background: "hsla(var(--accent) / 0.14)" }} aria-hidden="true" />
      <div className="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <SectionHeading
          eyebrow={bi("Paket Wisata", "Tour Packages", lang)}
          title={bi("Rencana perjalanan yang sudah tersusun", "Journeys we have already planned", lang)}
          subtitle={bi("Itinerary, unit, dan driver sudah dipaketkan — Anda tinggal memilih tanggal.", "Itinerary, vehicle and driver bundled — you only pick the dates.", lang)}
        />

        {loading ? (
          <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3" data-testid="pkg-loading">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-72 animate-pulse rounded-2xl bg-muted" data-testid="pkg-skeleton" />
            ))}
          </div>
        ) : error || rows.length === 0 ? (
          <div className="mt-10 rounded-2xl border border-dashed border-border bg-card px-5 py-12 text-center" data-testid="pkg-empty">
            <p className="text-[14px] text-muted-foreground">{bi("Belum ada paket wisata yang dipublikasikan.", "No tour packages published yet.", lang)}</p>
            <Link to="/quotation" data-testid="pkg-empty-quote" className="mt-4 inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-[13px] font-semibold text-primary-foreground">
              {bi("Minta itinerary khusus", "Request a custom itinerary", lang)} <ArrowRight size={14} />
            </Link>
          </div>
        ) : (
          <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3" data-testid="pkg-grid">
            {rows.map((p, i) => (
              <Reveal key={p.id} delay={i * 0.07}>
                <div className="card-premium lift flex h-full flex-col overflow-hidden rounded-2xl" data-testid={`pkg-item-${p.slug}`}>
                  <div className="relative h-40 overflow-hidden bg-secondary">
                    <div
                      className="absolute inset-0 bg-cover bg-center transition duration-500 hover:scale-105"
                      style={p.image_url ? { backgroundImage: `url('${p.image_url}')` } : undefined}
                      aria-hidden="true"
                    />
                    <span className="absolute left-3 top-3 rounded-full bg-black/55 px-2.5 py-1 text-[11px] font-semibold text-white backdrop-blur-sm">
                      {p.destination}
                    </span>
                  </div>
                  <div className="flex flex-1 flex-col p-5">
                    {/* A1 — paket kini punya halaman publik sendiri: judul & tautan di bawah
                        membawa pengunjung ke rincian lengkap (`/packages/:slug`), bukan langsung
                        memaksa mengisi formulir penawaran. */}
                    <Link to={`/packages/${p.slug}`} data-testid={`pkg-link-${p.slug}`}
                      className="font-fraunces text-xl leading-snug text-foreground transition hover:text-primary">
                      {p.name}
                    </Link>
                    <div className="mt-2 flex flex-wrap gap-2 text-[11.5px] font-medium text-muted-foreground">
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2.5 py-1"><CalendarDays size={12} /> {p.days} {tr("packages.days", lang)}</span>
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2.5 py-1 tabular-nums"><Users size={12} /> {p.pax_min}–{p.pax_max} pax</span>
                    </div>
                    <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">{p.description}</p>
                    {Array.isArray(p.includes) && p.includes.length ? (
                      <ul className="mt-3 space-y-1.5">
                        {p.includes.slice(0, 3).map((inc) => (
                          <li key={inc} className="flex items-start gap-2 text-[12.5px] text-foreground/80">
                            <Check size={13} className="mt-0.5 shrink-0 text-primary" /> {inc}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    <div className="mt-auto pt-5">
                      <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{tr("packages.from", lang)}</p>
                      <p className="font-mono text-[19px] font-semibold tabular-nums text-foreground" data-testid={`pkg-price-${p.slug}`}>{formatCurrency(p.price_from)}</p>
                      <Link
                        to="/quotation"
                        state={{ destination: p.destination, message: bi(`Saya tertarik paket ${p.name} (${p.days} hari)`, `I'm interested in the ${p.name} package (${p.days} days)`, lang) }}
                        data-testid={`pkg-quote-${p.slug}`}
                        className="cta-shine mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg py-2.5 text-[13px] font-semibold text-primary-foreground"
                        style={{ background: "var(--gradient-cta)" }}
                      >
                        {tr("nav.quotation", lang)} <ArrowRight size={14} />
                      </Link>
                      <Link to={`/packages/${p.slug}`} data-testid={`pkg-detail-${p.slug}`}
                        className="mt-2 inline-flex w-full items-center justify-center gap-1.5 rounded-lg border border-border py-2.5 text-[13px] font-semibold text-foreground transition hover:bg-secondary">
                        {bi("Lihat detail paket", "View package details", lang)}
                      </Link>
                    </div>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        )}

        {rows.length ? (
          <div className="mt-8 text-center">
            <Link to="/packages" data-testid="pkg-strip-all"
              className="inline-flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-[13px] font-semibold text-foreground transition hover:bg-secondary">
              {bi("Lihat semua paket", "See all packages", lang)} <ArrowRight size={14} />
            </Link>
          </div>
        ) : null}
      </div>
    </section>
  );
}

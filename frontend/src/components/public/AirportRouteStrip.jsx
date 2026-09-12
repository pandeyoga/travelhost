import { Link } from "react-router-dom";
import { PlaneTakeoff, Clock, ArrowRight, MoveRight } from "lucide-react";
import { formatCurrency } from "@/utils/formatters";
import SectionHeading from "@/components/public/SectionHeading";
import Reveal from "@/components/public/Reveal";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

// AirportRouteStrip.jsx — rute antar-jemput bandara dengan TARIF FLAT per rute.
// Sumber: `GET /api/public/booking/config` → `routes[]` (tarif diisi pemilik; sistem
// sengaja tidak menebak harga). Tiap kartu menautkan langsung ke wizard dengan layanan
// `airport_transfer` + rute terpilih, jadi pengunjung tidak perlu mencari ulang.
function durationLabel(min, lang) {
  if (!min) return null;
  const h = Math.floor(min / 60);
  const m = min % 60;
  const hr = bi("jam", "h", lang);
  const mn = bi("mnt", "min", lang);
  return h ? `${h} ${hr}${m ? ` ${m} ${mn}` : ""}` : `${m} ${mn}`;
}

export default function AirportRouteStrip({ routes, loading, error, limit = 6 }) {
  const lang = useLangValue();
  const rows = (Array.isArray(routes) ? routes : []).slice(0, limit);

  return (
    <section className="section-tint relative overflow-hidden" data-testid="airport-route-strip">
      <div className="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <SectionHeading
          eyebrow={bi("Antar-Jemput Bandara", "Airport Transfer", lang)}
          title={bi("Tarif flat, sekali jalan", "Flat rate, one way", lang)}
          subtitle={bi("Tidak dihitung per hari — satu harga untuk satu rute, sudah termasuk driver.", "Not charged per day — one price per route, driver included.", lang)}
        />

        {loading ? (
          <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3" data-testid="ars-loading">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-32 animate-pulse rounded-2xl bg-muted" data-testid="ars-skeleton" />
            ))}
          </div>
        ) : error ? (
          <p className="mt-10 rounded-2xl border border-dashed border-border bg-card px-5 py-10 text-center text-[13.5px] text-muted-foreground" data-testid="ars-error">
            {bi("Gagal memuat daftar rute.", "Failed to load the route list.", lang)}
          </p>
        ) : rows.length === 0 ? (
          <div className="mt-10 rounded-2xl border border-dashed border-border bg-card px-5 py-12 text-center" data-testid="ars-empty">
            <p className="text-[14px] text-muted-foreground">{bi("Belum ada rute antar-jemput yang dipublikasikan.", "No airport transfer routes published yet.", lang)}</p>
            <Link to="/quotation" data-testid="ars-empty-quote" className="mt-4 inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-[13px] font-semibold text-primary-foreground">
              {bi("Tanya rute Anda", "Ask about your route", lang)} <ArrowRight size={14} />
            </Link>
          </div>
        ) : (
          <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3" data-testid="ars-grid">
            {rows.map((r, i) => (
              <Reveal key={r.id} delay={i * 0.05}>
                <Link
                  to={`/booking?service=airport_transfer&route=${encodeURIComponent(r.id)}`}
                  data-testid={`ars-item-${r.code}`}
                  className="card-premium lift group flex h-full flex-col rounded-2xl p-5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wider text-primary">
                      <span className="icon-chip h-9 w-9 rounded-xl transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-110"><PlaneTakeoff size={15} /></span>
                      {r.airport_code || bi("Transfer", "Transfer", lang)}
                    </span>
                    {durationLabel(r.duration_minutes, lang) ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-secondary/80 px-2.5 py-1 text-[11.5px] font-medium text-secondary-foreground transition-colors duration-300 group-hover:border-ring/40">
                        <Clock size={12} /> {durationLabel(r.duration_minutes, lang)}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-3 flex flex-wrap items-center gap-1.5 text-[14.5px] font-semibold text-foreground">
                    {r.from_label} <MoveRight size={15} className="text-muted-foreground transition-all duration-300 group-hover:translate-x-1 group-hover:text-primary" /> {r.to_label}
                  </p>
                  <div className="hairline mt-4" aria-hidden="true" />
                  <div className="mt-3 flex items-end justify-between gap-3">
                    <div>
                      <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{bi("Tarif flat", "Flat rate", lang)}</p>
                      <p className="font-mono text-[19px] font-semibold tabular-nums text-foreground transition-colors duration-300 group-hover:text-primary" data-testid={`ars-price-${r.code}`}>
                        {r.from_price ? formatCurrency(r.from_price) : bi("Hubungi kami", "Contact us", lang)}
                      </p>
                    </div>
                    <span className="cta-shine mb-0.5 inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-[12.5px] font-semibold text-primary-foreground shadow-md transition-transform duration-300 group-hover:scale-[1.07]" style={{ background: "var(--gradient-cta)" }}>
                      {bi("Pesan", "Book", lang)} <ArrowRight size={13} className="transition group-hover:translate-x-1" />
                    </span>
                  </div>
                </Link>
              </Reveal>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

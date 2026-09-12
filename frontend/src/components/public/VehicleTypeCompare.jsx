import { Link } from "react-router-dom";
import { Users, ArrowRight, Info, Bus } from "lucide-react";
import { formatCurrency } from "@/utils/formatters";
import SectionHeading from "@/components/public/SectionHeading";
import Reveal from "@/components/public/Reveal";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

// VehicleTypeCompare.jsx — perbandingan TIPE armada (bukan per unit).
//
// Kenapa perlu: katalog `/fleet` menampilkan unit fisik. Kalau pemilik baru punya 3 unit,
// halaman terasa kosong padahal yang dicari pengunjung sebenarnya "tipe apa yang cocok
// untuk 12 orang dan berapa mulai harganya". Semua angka di sini datang dari
// `GET /api/public/booking/config` (tarif nyata yang dipakai mesin harga), BUKAN daftar
// hardcode — dulu kalkulator pernah menawarkan tipe yang tidak punya tarif & tidak punya unit.
const BEST_FOR = {
  hiace_premio: ["Keluarga & korporat yang mengutamakan kenyamanan kabin", "Families & corporates who value cabin comfort"],
  hiace: ["Rombongan hemat dengan kapasitas sama", "Budget groups with the same capacity"],
  elf: ["Rombongan besar, bagasi banyak", "Large groups with plenty of luggage"],
  bus: ["Gathering & study tour skala besar", "Large-scale gatherings & study tours"],
  avanza: ["Grup kecil / antar-jemput bandara", "Small groups / airport transfers"],
};

export default function VehicleTypeCompare({
  types,
  loading,
  error,
  dpPercent,
  eyebrow,
  title,
  subtitle,
}) {
  const lang = useLangValue();
  const rows = Array.isArray(types) ? types : [];
  const eb = eyebrow || bi("Bandingkan", "Compare", lang);
  const ttl = title || bi("Pilih tipe sesuai jumlah penumpang", "Choose a type by passenger count", lang);
  const sub = subtitle || bi("Tarif di bawah adalah tarif nyata yang dipakai sistem saat menghitung pesanan — bukan perkiraan iklan.", "The rates below are the real rates the system uses when pricing a booking — not marketing estimates.", lang);

  return (
    <section className="relative overflow-hidden" data-testid="vehicle-type-compare">
      <div className="glow-orb h-72 w-72 -left-16 top-10" style={{ background: "hsla(var(--ring) / 0.12)" }} aria-hidden="true" />
      <div className="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <SectionHeading eyebrow={eb} title={ttl} subtitle={sub} />

        {loading ? (
          <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3" data-testid="vtc-loading">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-44 animate-pulse rounded-2xl bg-muted" data-testid="vtc-skeleton" />
            ))}
          </div>
        ) : error ? (
          <p className="mt-10 rounded-2xl border border-dashed border-border bg-card px-5 py-10 text-center text-[13.5px] text-muted-foreground" data-testid="vtc-error">
            {bi("Gagal memuat daftar tipe armada.", "Failed to load the vehicle type list.", lang)}
          </p>
        ) : rows.length === 0 ? (
          <div className="mt-10 rounded-2xl border border-dashed border-border bg-card px-5 py-12 text-center" data-testid="vtc-empty">
            <p className="text-[14px] text-muted-foreground">{bi("Belum ada tipe armada dengan tarif aktif.", "No vehicle types with active rates yet.", lang)}</p>
            <Link to="/quotation" data-testid="vtc-empty-quote" className="mt-4 inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-[13px] font-semibold text-primary-foreground">
              {bi("Minta penawaran khusus", "Request a custom quote", lang)} <ArrowRight size={14} />
            </Link>
          </div>
        ) : (
          <>
            <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3" data-testid="vtc-grid">
              {rows.map((t, i) => (
                <Reveal key={t.value} delay={i * 0.06}>
                  <div className="card-premium lift flex h-full flex-col rounded-2xl p-6" data-testid={`vtc-item-${t.value}`}>
                    <div className="flex items-start justify-between gap-3">
                      <span className="icon-chip h-11 w-11 shrink-0"><Bus size={18} strokeWidth={1.8} /></span>
                      <span className="rounded-full bg-secondary px-2.5 py-1 text-[11px] font-semibold text-secondary-foreground" data-testid={`vtc-units-${t.value}`}>
                        {t.units} {bi("unit siap", "units ready", lang)}
                      </span>
                    </div>
                    <h3 className="mt-4 font-fraunces text-xl text-foreground">{t.label}</h3>
                    <p className="mt-1 inline-flex items-center gap-1.5 text-[12.5px] text-muted-foreground">
                      <Users size={13} /> {bi("sampai", "up to", lang)} {t.max_capacity} {bi("penumpang", "passengers", lang)}
                    </p>
                    <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">{BEST_FOR[t.value] ? bi(BEST_FOR[t.value][0], BEST_FOR[t.value][1], lang) : bi("Cocok untuk perjalanan rombongan.", "Great for group journeys.", lang)}</p>
                    <div className="mt-auto pt-5">
                      <p className="text-[11.5px] uppercase tracking-wider text-muted-foreground">{bi("Mulai dari", "From", lang)}</p>
                      <p className="font-mono text-[20px] font-semibold tabular-nums text-foreground" data-testid={`vtc-price-${t.value}`}>
                        {formatCurrency(t.from_price)}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">/{bi("hari", "day", lang)}</span>
                      </p>
                      <Link
                        to={`/booking?type=${encodeURIComponent(t.value)}`}
                        data-testid={`vtc-book-${t.value}`}
                        className="cta-shine mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg py-2.5 text-[13px] font-semibold text-primary-foreground transition hover:-translate-y-0.5"
                        style={{ background: "var(--gradient-cta)" }}
                      >
                        {bi("Cek ketersediaan", "Check availability", lang)} <ArrowRight size={14} />
                      </Link>
                    </div>
                  </div>
                </Reveal>
              ))}
            </div>
            <p className="mt-5 flex items-start gap-2 text-[12.5px] leading-relaxed text-muted-foreground">
              <Info size={14} className="mt-0.5 shrink-0" />
              {bi(
                `Tarif dihitung per hari pemakaian. Pemesanan online cukup DP ${dpPercent || 30}% untuk mengamankan jadwal; sisanya dibayar sebelum keberangkatan.`,
                `Rates are calculated per day of use. Booking online only needs a ${dpPercent || 30}% deposit to secure your schedule; the rest is paid before departure.`,
                lang,
              )}
            </p>
          </>
        )}
      </div>
    </section>
  );
}

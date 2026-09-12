import { Link } from "react-router-dom";
import { Users, ArrowRight, Navigation, View } from "lucide-react";
import { formatCurrency } from "@/utils/formatters";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

// FleetCard — kartu armada premium (dipakai di Home & halaman Armada).
export default function FleetCard({ v }) {
  const lang = useLangValue();
  const img = v.photos && v.photos[0];
  const has360 = Array.isArray(v.tour_scenes) && v.tour_scenes.length > 0;
  return (
    <Link to={`/fleet/${v.id}`} data-testid={`fleet-card-${v.id}`} className="group block h-full overflow-hidden rounded-2xl card-premium lift shimmer-on-hover">
      <div className="relative h-52 overflow-hidden">
        <div className="absolute inset-0 bg-primary bg-cover bg-center transition duration-700 ease-out group-hover:scale-110" style={img ? { backgroundImage: `url('${img}')` } : undefined} />
        <div className="absolute inset-0" style={{ background: "linear-gradient(180deg, rgba(8,14,32,0) 45%, rgba(8,14,32,0.5) 100%)" }} />
        <span className="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full glass-strong px-2.5 py-1 text-[11.5px] font-medium text-foreground"><Users size={12} /> {v.capacity} {bi("kursi", "seats", lang)}</span>
        {has360 ? (
          <span className="absolute right-3 top-3 inline-flex items-center gap-1 rounded-full bg-black/40 px-2.5 py-1 text-[11px] font-medium text-white backdrop-blur-sm"><View size={12} /> {bi("Kabin 360°", "360° Cabin", lang)}</span>
        ) : v.year ? (
          <span className="absolute right-3 top-3 rounded-full bg-black/35 px-2.5 py-1 text-[11px] font-medium text-white backdrop-blur-sm">{v.year}</span>
        ) : null}
      </div>
      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-fraunces text-lg leading-tight text-foreground">{v.name}</h3>
            <p className="mt-0.5 text-[12.5px] capitalize text-muted-foreground">{String(v.type).replace(/_/g, " ")}</p>
          </div>
          {v.price_from ? (
            <div className="shrink-0 text-right">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{bi("Mulai", "From", lang)}</p>
              <p className="font-mono text-[14px] font-semibold tabular-nums text-foreground">{formatCurrency(v.price_from)}</p>
            </div>
          ) : null}
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {(v.features || []).slice(0, 4).map((f, i) => (
            <span key={i} className="rounded-full bg-secondary px-2.5 py-1 text-[11px] font-medium text-secondary-foreground">{f}</span>
          ))}
        </div>
        <div className="mt-4 flex items-center justify-between border-t border-border pt-3.5">
          <span className="inline-flex items-center gap-1 text-[13px] font-semibold text-primary">{bi("Lihat detail", "View details", lang)} <ArrowRight size={14} className="transition group-hover:translate-x-0.5" /></span>
          {has360 ? <span className="inline-flex items-center gap-1 text-[11.5px] text-muted-foreground"><Navigation size={12} /> {bi("Tur 360°", "360° Tour", lang)}</span> : null}
        </div>
      </div>
    </Link>
  );
}

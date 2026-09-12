import { Link } from "react-router-dom";
import { MapPin, ArrowRight } from "lucide-react";

const REGION_LABEL = { bali: "Bali", jawa_timur: "Jawa Timur", jawa_tengah: "Jawa Tengah", jawa_barat: "Jawa Barat", yogyakarta: "Yogyakarta" };
const regionLabel = (r) => REGION_LABEL[r] || String(r || "").replace(/_/g, " ");

// DestCard — kartu destinasi sinematik (dipakai di Home & halaman Destinasi).
export default function DestCard({ d, className = "", big = false, showDesc = false }) {
  return (
    <Link to={`/destinations/${d.slug}`} data-testid={`dest-card-${d.slug}`} className={`group relative block overflow-hidden rounded-2xl bg-primary lift shimmer-on-hover ${className}`}>
      <div className="absolute inset-0 bg-cover bg-center transition duration-700 ease-out group-hover:scale-110" style={d.hero_image ? { backgroundImage: `url('${d.hero_image}')` } : undefined} />
      <div className="absolute inset-0" style={{ background: "linear-gradient(180deg, rgba(8,14,32,0.04) 25%, rgba(8,14,32,0.88) 100%)" }} />
      {d.popular ? <span className="absolute right-3 top-3 rounded-full bg-white/15 px-2.5 py-1 text-[10.5px] font-semibold text-white backdrop-blur-sm">Populer</span> : null}
      <div className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-3 p-5">
        <div>
          {d.region ? <span className="inline-flex items-center gap-1 rounded-full bg-white/15 px-2.5 py-1 text-[10.5px] font-medium uppercase tracking-wide text-white backdrop-blur-sm"><MapPin size={11} /> {regionLabel(d.region)}</span> : null}
          <h3 className={`mt-2 font-fraunces text-white ${big ? "text-3xl" : "text-xl"}`}>{d.name}</h3>
          {showDesc && d.description ? <p className="mt-1.5 line-clamp-2 max-w-md text-[12.5px] text-white/80">{d.description}</p> : null}
        </div>
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/15 text-white backdrop-blur-sm transition group-hover:bg-white group-hover:text-primary"><ArrowRight size={16} /></span>
      </div>
    </Link>
  );
}

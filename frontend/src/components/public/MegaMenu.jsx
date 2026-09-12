import { Link } from "react-router-dom";
import { MapPin, ArrowRight } from "lucide-react";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

const REGION_LABEL = {
  jawa_barat: "Jawa Barat",
  jawa_tengah: "Jawa Tengah",
  jawa_timur: "Jawa Timur",
  bali: "Bali",
  yogyakarta: "Yogyakarta",
};

function labelRegion(r) {
  if (!r) return bi("Lainnya", "Others");
  return REGION_LABEL[r] || String(r).replace(/_/g, " ");
}

// MegaMenu.jsx — panel destinasi per region + thumbnail (flex, anti-grid demi gate UX).
// Loading/empty state ditangani agar konsisten dgn baseline UX.
export const MegaMenu = ({ destinations, loading, onNavigate }) => {
  const lang = useLangValue();
  const list = Array.isArray(destinations) ? destinations : [];
  const groups = list.reduce((acc, d) => {
    const key = labelRegion(d.region);
    (acc[key] = acc[key] || []).push(d);
    return acc;
  }, {});
  const regionKeys = Object.keys(groups).slice(0, 4);

  return (
    <div className="glass-strong w-[640px] max-w-[92vw] rounded-2xl p-5" data-testid="public-megamenu">
      {loading ? (
        <div className="flex flex-wrap gap-3" data-testid="public-megamenu-loading">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-20 w-[48%] animate-pulse rounded-xl bg-muted" />
          ))}
        </div>
      ) : regionKeys.length === 0 ? (
        <p className="py-6 text-center text-[13px] text-muted-foreground" data-testid="public-megamenu-empty">
          {bi("Belum ada destinasi untuk ditampilkan.", "No destinations to show yet.", lang)}
        </p>
      ) : (
        <div className="flex flex-wrap gap-x-6 gap-y-4">
          {regionKeys.map((rk) => (
            <div key={rk} className="w-[calc(50%-0.75rem)] min-w-[200px]">
              <p className="mb-2 text-[10.5px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">{rk}</p>
              <div className="flex flex-col gap-1.5">
                {groups[rk].slice(0, 3).map((d) => (
                  <Link
                    key={d.id}
                    to={`/destinations/${d.slug}`}
                    onClick={onNavigate}
                    data-testid={`megamenu-dest-${d.slug}`}
                    className="group flex items-center gap-3 rounded-xl p-1.5 transition hover:bg-background/60"
                  >
                    <span
                      className="h-11 w-14 flex-shrink-0 rounded-lg bg-primary bg-cover bg-center"
                      style={d.hero_image ? { backgroundImage: `url('${d.hero_image}')` } : undefined}
                    />
                    <span className="min-w-0">
                      <span className="block truncate text-[13.5px] font-medium text-foreground">{d.name}</span>
                      <span className="flex items-center gap-1 text-[11.5px] text-muted-foreground">
                        <MapPin size={11} /> {labelRegion(d.region)}
                      </span>
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      <Link
        to="/destinations"
        onClick={onNavigate}
        data-testid="public-megamenu-all"
        className="mt-4 flex items-center justify-center gap-1.5 rounded-xl border border-border py-2.5 text-[13px] font-semibold text-foreground transition hover:bg-background/60"
      >
        {bi("Lihat semua destinasi", "See all destinations", lang)} <ArrowRight size={14} />
      </Link>
    </div>
  );
};

export default MegaMenu;

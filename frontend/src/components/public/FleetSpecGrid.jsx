import { Users, Cog, Fuel, Tv, ShieldCheck, Snowflake, Calendar, Palette, Gauge, Sparkles } from "lucide-react";
import { bi } from "@/lib/i18n";

// FleetSpecGrid.jsx — bento spesifikasi (flex, glass, ikon per spec). Empty state aman.
const ICONS = {
  capacity: Users, transmission: Cog, fuel: Fuel, entertainment: Tv,
  safety: ShieldCheck, ac: Snowflake, year: Calendar, color: Palette, odometer: Gauge,
};

export default function FleetSpecGrid({ specs = [], className = "" }) {
  const items = Array.isArray(specs) ? specs : [];
  if (!items.length) {
    return (
      <p className={`text-[13px] text-muted-foreground ${className}`} data-testid="fleet-specs-empty">
        {bi("Belum ada spesifikasi tercatat.", "No specifications recorded yet.")}
      </p>
    );
  }
  return (
    <div className={`flex flex-wrap gap-3 ${className}`} data-testid="fleet-specs">
      {items.map((s, i) => {
        const Icon = ICONS[s.key] || Sparkles;
        return (
          <div key={i} className="glass flex w-[calc(50%-0.375rem)] items-center gap-3 rounded-xl p-3.5 sm:w-[calc(33.333%-0.5rem)]">
            <span className="icon-chip flex h-9 w-9 flex-shrink-0 items-center justify-center">
              <Icon size={17} />
            </span>
            <span className="min-w-0">
              <span className="block text-[10.5px] uppercase tracking-wide text-muted-foreground">{s.label}</span>
              <span className="block truncate text-[13.5px] font-semibold text-foreground">{s.value}</span>
            </span>
          </div>
        );
      })}
    </div>
  );
}

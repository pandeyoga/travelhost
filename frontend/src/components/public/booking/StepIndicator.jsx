import { Check } from "lucide-react";

// StepIndicator — penanda langkah wizard pemesanan (Cari → Pilih Unit → Data & Bayar).
// Pengunjung harus selalu tahu ada di langkah berapa dan berapa langkah lagi; tanpa itu
// formulir panjang terasa seperti lubang tanpa dasar dan orang berhenti di tengah jalan.
export default function StepIndicator({ steps = [], current = 0, onJump }) {
  return (
    <ol className="flex flex-wrap items-center gap-2 sm:gap-3" data-testid="booking-steps">
      {steps.map((label, i) => {
        const done = i < current;
        const active = i === current;
        const clickable = done && typeof onJump === "function";
        return (
          <li key={label} className="flex items-center gap-2">
            <button
              type="button"
              disabled={!clickable}
              onClick={() => clickable && onJump(i)}
              data-testid={`booking-step-${i}`}
              className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-[12.5px] font-semibold transition ${
                active
                  ? "border-transparent text-primary-foreground shadow-[var(--shadow-lift)]"
                  : done
                    ? "border-border bg-card text-foreground hover:-translate-y-0.5"
                    : "border-dashed border-border bg-transparent text-muted-foreground"
              } ${clickable ? "cursor-pointer" : "cursor-default"}`}
              style={active ? { background: "var(--gradient-cta)" } : undefined}
            >
              <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[11px] ${
                active ? "bg-white/25" : done ? "bg-primary/10 text-primary" : "bg-secondary"
              }`}>
                {done ? <Check size={12} /> : i + 1}
              </span>
              {label}
            </button>
            {i < steps.length - 1 ? <span className="h-px w-4 bg-border sm:w-8" aria-hidden="true" /> : null}
          </li>
        );
      })}
    </ol>
  );
}

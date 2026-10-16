import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { bi } from "@/lib/i18n";

// SectionHeading — eyebrow + judul + (opsional) subjudul & link "lihat semua".
// Dipakai konsisten di seluruh halaman publik untuk hierarki visual yang rapi.
export const SectionHeading = ({
  eyebrow,
  title,
  subtitle,
  to,
  linkLabel,
  center = false,
  testId,
}) => (
  <div className={center ? "text-center" : "flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"}>
    <div className={center ? "mx-auto max-w-2xl" : "max-w-2xl"}>
      {eyebrow ? (
        <span className={`inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-primary ${center ? "justify-center" : ""}`}>
          <span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--ring))]" /> {eyebrow}
        </span>
      ) : null}
      <h2 className="mt-3 font-fraunces text-3xl leading-[1.1] text-foreground sm:text-4xl text-balance">{title}</h2>
      {subtitle ? (
        <p className="mt-3 text-[14.5px] leading-relaxed text-muted-foreground">{subtitle}</p>
      ) : null}
    </div>
    {to ? (
      <Link
        to={to}
        data-testid={testId}
        className="group inline-flex shrink-0 items-center gap-1.5 rounded-full border border-border bg-card px-4 py-2 text-[13px] font-semibold text-foreground transition hover:border-[hsla(var(--glass-border))] hover:-translate-y-0.5"
      >
        {linkLabel || bi("Lihat semua", "See all")} <ArrowRight size={15} className="transition group-hover:translate-x-0.5" />
      </Link>
    ) : null}
  </div>
);

export default SectionHeading;

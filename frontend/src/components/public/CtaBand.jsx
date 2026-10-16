import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

// CtaBand.jsx — SATU pola panel CTA untuk seluruh situs publik
// (design_guidelines §cta_band_safe_pattern).
//
// Kenapa komponen ini ada (bug nyata, bukan preferensi gaya): panel CTA di `/blog/:slug`
// memakai class Tailwind `bg-gradient-to-br from-primary to-[color:var(--primary)]`.
// Token tema di proyek ini berisi TRIPLET HSL (`--primary: 220 45% 14%`), jadi
// `to-[color:var(--primary)]` menghasilkan `--tw-gradient-to: color:var(--primary)` yang
// INVALID; browser membuang seluruh deklarasi `background-image`, panel jadi transparan,
// dan teks `text-primary-foreground` (putih) berubah menjadi putih-di-atas-kertas-putih —
// persis yang terlihat pada screenshot user ("ada button cta namun uinya rusak").
//
// Aturan yang ditegakkan di sini: warna latar band SELALU `bg-primary` (warna solid dari
// token, aman) dan dekorasi memakai `background-image` inline yang valid.
export default function CtaBand({
  eyebrow,
  title,
  subtitle,
  note,
  primary,
  secondary,
  testId = "cta-band",
  className = "",
}) {
  const Primary = primary?.to ? Link : "a";
  const Secondary = secondary?.to ? Link : "a";

  return (
    <div
      data-testid={testId}
      className={`relative flex flex-col items-start gap-6 overflow-hidden rounded-3xl bg-primary px-6 py-10 text-primary-foreground md:flex-row md:items-center md:justify-between md:px-12 md:py-12 ${className}`}
      style={{
        backgroundImage:
          "radial-gradient(120% 120% at 88% 6%, hsla(var(--ring) / 0.34) 0%, transparent 58%), radial-gradient(90% 90% at 4% 100%, hsla(var(--accent) / 0.22) 0%, transparent 60%)",
      }}
    >
      <div className="pointer-events-none absolute inset-0 bg-noise opacity-[0.06]" aria-hidden="true" />
      <div className="relative max-w-xl">
        {eyebrow ? (
          <span className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-primary-foreground/75">
            <span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--ring))]" /> {eyebrow}
          </span>
        ) : null}
        <h2 className="mt-3 font-fraunces text-3xl leading-tight text-primary-foreground sm:text-4xl">{title}</h2>
        {subtitle ? (
          <p className="mt-3 text-[14.5px] leading-relaxed text-primary-foreground/85">{subtitle}</p>
        ) : null}
        {note ? (
          <p className="mt-3 inline-flex items-center gap-2 rounded-full bg-primary-foreground/10 px-3 py-1.5 text-[12px] font-medium text-primary-foreground/90">
            {note}
          </p>
        ) : null}
      </div>

      <div className="relative flex w-full flex-wrap gap-3 md:w-auto md:justify-end">
        {primary ? (
          <Primary
            {...(primary.to ? { to: primary.to, state: primary.state } : { href: primary.href, target: "_blank", rel: "noreferrer" })}
            data-testid={primary.testId || `${testId}-primary`}
            className="cta-shine glow-focus inline-flex flex-1 items-center justify-center gap-2 rounded-full bg-primary-foreground px-5 py-3 text-[14px] font-semibold text-primary shadow-[var(--shadow-lift)] transition hover:-translate-y-0.5 md:flex-none"
          >
            {primary.icon ? <primary.icon size={16} /> : null} {primary.label}
            {primary.icon ? null : <ArrowRight size={16} />}
          </Primary>
        ) : null}
        {secondary ? (
          <Secondary
            {...(secondary.to ? { to: secondary.to, state: secondary.state } : { href: secondary.href, target: "_blank", rel: "noreferrer" })}
            data-testid={secondary.testId || `${testId}-secondary`}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-full border border-primary-foreground/40 bg-primary-foreground/10 px-5 py-3 text-[14px] font-semibold text-primary-foreground backdrop-blur-sm transition hover:bg-primary-foreground/20 md:flex-none"
          >
            {secondary.icon ? <secondary.icon size={16} /> : null} {secondary.label}
          </Secondary>
        ) : null}
      </div>
    </div>
  );
}

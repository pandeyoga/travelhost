// Logo.jsx — monogram “R” bergaya jalur perjalanan (route line) + titik pin.
// Mark adaptif token (bg-primary / text-primary-foreground). Hindari ikon bus generik.
export const Logo = ({ showWordmark = true, name = "RahazaTrans", className = "", wordmarkClass = "" }) => (
  <span className={`inline-flex items-center gap-2.5 ${className}`} data-testid="brand-logo">
    <span className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-[var(--shadow-lift)]">
      <svg width="22" height="22" viewBox="0 0 32 32" fill="none" aria-hidden="true">
        <path
          d="M11 25 L11 8 H18.5 A5 5 0 0 1 18.5 18 H11 M14.5 18 L21 25"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
        <circle cx="21.4" cy="8.2" r="2" fill="currentColor" />
      </svg>
    </span>
    {showWordmark ? (
      <span className={`font-fraunces text-[18px] font-semibold tracking-tight ${wordmarkClass}`}>{name}</span>
    ) : null}
  </span>
);

export default Logo;

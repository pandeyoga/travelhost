// Logo.jsx — memakai logo unggahan (Pengaturan Situs / Brand dokumen) bila ada;
// jika tidak, monogram “R” bawaan (adaptif token bg-primary / text-primary-foreground).
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const resolveLogoUrl = (u) => {
  const v = String(u || "").trim();
  if (!v) return "";
  return /^(https?:|data:)/.test(v) ? v : `${BACKEND_URL}${v.startsWith("/") ? "" : "/"}${v}`;
};

export const Logo = ({ showWordmark = true, name = "RahazaTrans", logoUrl = "", className = "", wordmarkClass = "" }) => {
  const src = resolveLogoUrl(logoUrl);
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`} data-testid="brand-logo">
      {src ? (
        <img src={src} alt={name} className="h-9 w-9 shrink-0 object-contain" data-testid="brand-logo-img" />
      ) : (
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
      )}
      {showWordmark ? (
        <span className={`font-fraunces text-[18px] font-semibold tracking-tight ${wordmarkClass}`}>{name}</span>
      ) : null}
    </span>
  );
};

export default Logo;

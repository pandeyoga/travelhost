import { MapPin, Calendar, Users, Bus, Map, Plane, Check, Star, ShieldCheck, Clock, Receipt,
  UserCheck, Camera, Search, Sparkles, Phone, Mail, MessageCircle, Building2 } from "lucide-react";

/**
 * components/app/landing/shared.jsx — potongan visual bersama semua blok landing page.
 *
 * Dipisah supaya renderer blok tetap di bawah batas ukuran file (validate_compliance) DAN
 * supaya satu perubahan gaya tombol/heading berlaku serentak di 17 tipe blok — bukan
 * ditulis ulang 17 kali (sumber klasik ketidakkonsistenan visual).
 */
export const ICONS = {
  "map-pin": MapPin, calendar: Calendar, users: Users, bus: Bus, map: Map, plane: Plane,
  check: Check, star: Star, shield: ShieldCheck, clock: Clock, receipt: Receipt,
  "user-check": UserCheck, camera: Camera, search: Search, sparkles: Sparkles,
  phone: Phone, mail: Mail, chat: MessageCircle, building: Building2,
};

export const DEFAULT_THEME = {
  primary: "#0B7BD3", accent: "#FF7A00", text: "#10233A", bg: "#F5F8FC",
  radius: 16, font_scale: 100, button_shape: "rounded",
};

export function themeOf(page) {
  return { ...DEFAULT_THEME, ...(page?.theme || {}) };
}

export function btnRadius(theme) {
  return theme.button_shape === "pill" ? 999 : theme.radius;
}

export function Icon({ name, size = 15 }) {
  const C = ICONS[name] || Check;
  return <C size={size} />;
}

/** Tombol CTA. `disabled` dipakai mode pratinjau editor agar tak memicu navigasi. */
export function Btn({ cta, theme, onClick, testId, block = false }) {
  if (!cta?.label) return null;
  const primary = cta.style !== "secondary";
  return (
    <button type="button" onClick={onClick} data-testid={testId}
      className={`inline-flex h-11 items-center justify-center gap-2 px-5 text-[14px] font-bold transition-opacity hover:opacity-90 ${block ? "w-full" : ""}`}
      style={{
        borderRadius: btnRadius(theme),
        background: primary ? theme.primary : "#FFFFFF",
        color: primary ? "#FFFFFF" : theme.primary,
        border: primary ? "none" : `1.5px solid ${theme.primary}`,
      }}>
      {cta.kind === "whatsapp" ? <MessageCircle size={15} /> : null}
      {cta.label}
    </button>
  );
}

export function Wrap({ children, theme, tight, id }) {
  return (
    <section id={id} className={tight ? "px-5 py-7" : "px-5 py-10"} style={{ background: theme.bg }}>
      <div className="mx-auto max-w-[1120px]">{children}</div>
    </section>
  );
}

export function Heading({ title, subtitle, theme, center }) {
  if (!title && !subtitle) return null;
  return (
    <div className={`mb-5 ${center ? "text-center" : ""}`}>
      {title ? (
        <h2 className="text-[22px] font-extrabold leading-tight" style={{ color: theme.text }}>{title}</h2>
      ) : null}
      {subtitle ? <p className="mt-1 text-[13.5px] text-[#5B6472]">{subtitle}</p> : null}
    </div>
  );
}

/** Kotak input seragam untuk semua formulir di halaman iklan. */
export function Field({ label, hint, error, children, wide }) {
  return (
    <div className={wide ? "sm:col-span-2" : ""}>
      {label ? (
        <label className="mb-1 block text-[11.5px] font-bold text-[#4A5260]">{label}</label>
      ) : null}
      {children}
      {error ? <p className="mt-1 text-[11px] font-semibold text-[#C2261C]">{error}</p> : null}
      {!error && hint ? <p className="mt-1 text-[11px] text-[#8B93A0]">{hint}</p> : null}
    </div>
  );
}

export const inputClass =
  "h-10 w-full rounded-lg border border-[#D9DEE6] bg-white px-3 text-[13px] text-[#1C1C1E] " +
  "outline-none transition-colors placeholder:text-[#9AA1AC] focus:border-[#0B7BD3]";

/** Kartu entitas (armada/destinasi) — satu bentuk untuk semua grid. */
export function EntityCard({ item, theme, onClick, testId }) {
  return (
    <article className="group overflow-hidden bg-white shadow-sm transition-shadow hover:shadow-md"
      style={{ borderRadius: theme.radius }} data-testid={testId}>
      <div className="h-[160px] bg-[#EEF1F5]"
        style={item.image ? { background: `url(${item.image}) center/cover no-repeat` } : undefined} />
      <div className="p-3.5">
        <h3 className="text-[14.5px] font-bold" style={{ color: theme.text }}>{item.name}</h3>
        {item.meta ? <p className="mt-0.5 text-[12px] text-[#6B7280]">{item.meta}</p> : null}
        {item.priceNode ? (
          <p className="mt-1.5 text-[13.5px] font-bold" style={{ color: theme.primary }}>
            {item.priceNode}
          </p>
        ) : null}
        {onClick ? (
          <button type="button" onClick={onClick} data-testid={testId ? `${testId}-cta` : undefined}
            className="mt-2.5 text-[12.5px] font-bold underline-offset-2 hover:underline"
            style={{ color: theme.primary }}>
            Lihat detail &amp; harga
          </button>
        ) : null}
      </div>
    </article>
  );
}

/** Skeleton pemuatan daftar (loading state wajib baseline UX). */
export function CardsSkeleton({ count = 3 }) {
  return (
    <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3" data-testid="lp-cards-loading">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="h-[240px] animate-pulse rounded-xl bg-[#E9EDF2]" />
      ))}
    </div>
  );
}

export function EmptyNote({ children, testId = "lp-cards-empty" }) {
  return (
    <p className="rounded-xl bg-white p-5 text-center text-[13px] text-[#6B7280]" data-testid={testId}>
      {children}
    </p>
  );
}

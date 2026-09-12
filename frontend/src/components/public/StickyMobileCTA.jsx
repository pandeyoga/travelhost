import { Link } from "react-router-dom";
import { Calculator, MessageCircle, CalendarCheck } from "lucide-react";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

// StickyMobileCTA.jsx — bar bawah (mobile). Sesudah navbar dirapikan, aksi UTAMA situs adalah
// satu: "Pesan Online". Karena itu bar ini memajang Pesan Online (utama) + WhatsApp (sekunder),
// dengan kalkulator disusutkan jadi tombol ikon (tautannya tetap ada + testid dipertahankan
// supaya laporan uji lama tidak pecah).
export const StickyMobileCTA = ({ waLink, calcTo = "/trip-calculator", showCalc = true }) => {
  const lang = useLangValue();
  return (
  <div
    className="fixed inset-x-0 bottom-0 z-40 flex gap-2 border-t border-[hsla(var(--glass-border))] bg-[hsla(var(--glass-bg-strong))] p-3 backdrop-blur-xl lg:hidden"
    data-testid="sticky-mobile-cta"
  >
    {showCalc ? <Link
      to={calcTo}
      data-testid="sticky-cta-calc"
      aria-label={bi("Hitung estimasi biaya", "Estimate the cost", lang)}
      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-border bg-background/70 text-foreground"
    >
      <Calculator size={17} />
    </Link> : null}
    <Link
      to="/booking"
      data-testid="sticky-cta-booking"
      className="cta-shine flex flex-1 items-center justify-center gap-1.5 rounded-xl py-3 text-[13.5px] font-semibold text-primary-foreground"
      style={{ background: "var(--gradient-cta)" }}
    >
      <CalendarCheck size={16} /> {bi("Pesan Online", "Book online", lang)}
    </Link>
    <a
      href={waLink}
      target="_blank"
      rel="noreferrer"
      data-testid="sticky-cta-wa"
      className="flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-[#25D366] py-3 text-[13.5px] font-semibold text-white"
    >
      <MessageCircle size={16} /> WhatsApp
    </a>
  </div>
  );
};

export default StickyMobileCTA;

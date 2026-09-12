import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { MessageCircle, Calculator, Sparkles } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

// ExitIntentModal.jsx — recovery saat user hendak pergi (desktop mouseleave / mobile idle).
// Sekali per sesi. Tawaran: konsultasi WA atau hitung estimasi.
const KEY = "rahaza_exit_intent";

export const ExitIntentModal = ({ waLink, calcTo = "/trip-calculator", showCalc = true }) => {
  const lang = useLangValue();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    if (window.sessionStorage.getItem(KEY)) return undefined;
    let done = false;
    const trigger = () => {
      if (done) return;
      // Jangan menumpuk di atas dialog lain yang sedang terbuka (mis. lightbox/galeri).
      if (document.querySelector('[role="dialog"][data-state="open"]')) return;
      done = true;
      window.sessionStorage.setItem(KEY, "1");
      setOpen(true);
    };
    const onMouseOut = (e) => {
      if (!e.relatedTarget && e.clientY <= 0) trigger();
    };
    document.addEventListener("mouseout", onMouseOut);
    const idle = setTimeout(trigger, 35000); // fallback mobile/idle
    return () => {
      document.removeEventListener("mouseout", onMouseOut);
      clearTimeout(idle);
    };
  }, []);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-md glass-modal text-foreground" data-testid="exit-intent-modal">
        <DialogHeader>
          <div className="icon-chip mb-1 inline-flex h-10 w-10 items-center justify-center">
            <Sparkles size={18} />
          </div>
          <DialogTitle className="font-fraunces text-xl text-foreground">{bi("Tunggu — rencanakan dulu trip Anda", "Wait — plan your trip first", lang)}</DialogTitle>
          <DialogDescription className="text-[13px] leading-relaxed text-muted-foreground">
            {showCalc
              ? bi("Konsultasi gratis & penawaran transparan. Hitung estimasi dalam hitungan detik atau ngobrol langsung dengan tim kami.", "Free consultation & transparent quotes. Estimate the cost in seconds or chat directly with our team.", lang)
              : bi("Konsultasi gratis & penawaran transparan. Minta penawaran atau ngobrol langsung dengan tim kami.", "Free consultation & transparent quotes. Request a quote or chat directly with our team.", lang)}
          </DialogDescription>
        </DialogHeader>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
          <Link
            to={showCalc ? calcTo : "/quotation"}
            onClick={() => setOpen(false)}
            data-testid="exit-intent-calc"
            className="cta-shine flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-primary py-3 text-[13.5px] font-semibold text-primary-foreground transition hover:opacity-90"
          >
            <Calculator size={16} /> {showCalc ? bi("Hitung Estimasi", "Calculate Estimate", lang) : bi("Minta Penawaran", "Request a Quote", lang)}
          </Link>
          <a
            href={waLink}
            target="_blank"
            rel="noreferrer"
            onClick={() => setOpen(false)}
            data-testid="exit-intent-wa"
            className="flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-border py-3 text-[13.5px] font-semibold text-foreground transition hover:bg-secondary"
          >
            <MessageCircle size={16} /> {bi("Chat WhatsApp", "Chat on WhatsApp", lang)}
          </a>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ExitIntentModal;

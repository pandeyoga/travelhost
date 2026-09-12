import { useEffect } from "react";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

// Lightbox.jsx — galeri layar penuh (dialog) + crossfade + prev/next + thumbnail strip.
// Keyboard arrows didukung. Controlled: {open,index,onClose,onIndex}.
export default function Lightbox({ images = [], open, index = 0, onClose, onIndex }) {
  const lang = useLangValue();
  const list = Array.isArray(images) ? images : [];
  const cur = list[index];

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === "ArrowRight") onIndex((index + 1) % list.length);
      if (e.key === "ArrowLeft") onIndex((index - 1 + list.length) % list.length);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, index, list.length, onIndex]);

  if (!cur) return null;
  const url = cur.url || cur;
  const prev = () => onIndex((index - 1 + list.length) % list.length);
  const next = () => onIndex((index + 1) % list.length);

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-5xl border-none bg-transparent p-0 shadow-none [&>button]:hidden" data-testid="lightbox">
        <DialogTitle className="sr-only">{bi("Galeri foto armada", "Vehicle photo gallery", lang)}</DialogTitle>
        <div className="relative">
          <div className="relative aspect-[16/10] w-full overflow-hidden rounded-2xl bg-primary">
            <AnimatePresence mode="wait">
              <motion.img
                key={index}
                src={url}
                alt={cur.caption || bi("Foto armada", "Vehicle photo", lang)}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
                className="h-full w-full object-cover"
              />
            </AnimatePresence>
            {list.length > 1 ? (
              <>
                <button onClick={prev} data-testid="lightbox-prev" aria-label={bi("Sebelumnya", "Previous", lang)} className="absolute left-3 top-1/2 -translate-y-1/2 rounded-full bg-black/40 p-2 text-white backdrop-blur transition hover:bg-black/60"><ChevronLeft size={20} /></button>
                <button onClick={next} data-testid="lightbox-next" aria-label={bi("Berikutnya", "Next", lang)} className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full bg-black/40 p-2 text-white backdrop-blur transition hover:bg-black/60"><ChevronRight size={20} /></button>
              </>
            ) : null}
            <button onClick={onClose} data-testid="lightbox-close" aria-label={bi("Tutup", "Close", lang)} className="absolute right-3 top-3 z-10 rounded-full bg-black/40 p-2 text-white backdrop-blur transition hover:bg-black/60"><X size={18} /></button>
            <span className="absolute bottom-3 left-3 rounded-full bg-black/50 px-3 py-1 text-[12px] text-white backdrop-blur">{index + 1} / {list.length}</span>
          </div>
          {cur.caption ? <p className="mt-2 text-center text-[13px] text-white/90">{cur.caption}</p> : null}
          {list.length > 1 ? (
            <div className="mt-3 flex flex-wrap justify-center gap-2" data-testid="lightbox-thumbs">
              {list.map((im, i) => (
                <button
                  key={i}
                  onClick={() => onIndex(i)}
                  aria-label={bi(`Foto ${i + 1}`, `Photo ${i + 1}`, lang)}
                  className={`h-12 w-16 overflow-hidden rounded-lg border-2 bg-cover bg-center transition ${i === index ? "border-white" : "border-transparent opacity-60 hover:opacity-100"}`}
                  style={{ backgroundImage: `url('${im.url || im}')` }}
                />
              ))}
            </div>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}

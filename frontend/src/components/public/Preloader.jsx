import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

// Preloader.jsx — signature first-load (<1s): garis rute menggambar “R” + pin.
// Tampil sekali per sesi; otomatis skip saat prefers-reduced-motion.
const KEY = "rahaza_preloaded";

export const Preloader = () => {
  const reduce = useReducedMotion();
  const [show, setShow] = useState(() => {
    if (typeof window === "undefined") return false;
    return !window.sessionStorage.getItem(KEY);
  });

  useEffect(() => {
    if (!show) return undefined;
    if (reduce) {
      window.sessionStorage.setItem(KEY, "1");
      setShow(false);
      return undefined;
    }
    const t = setTimeout(() => {
      window.sessionStorage.setItem(KEY, "1");
      setShow(false);
    }, 950);
    return () => clearTimeout(t);
  }, [show, reduce]);

  return (
    <AnimatePresence>
      {show ? (
        <motion.div
          className="fixed inset-0 z-[80] flex items-center justify-center bg-background"
          data-testid="public-preloader"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="flex flex-col items-center gap-5">
            <svg width="72" height="72" viewBox="0 0 32 32" fill="none" aria-hidden="true">
              <motion.path
                d="M11 25 L11 8 H18.5 A5 5 0 0 1 18.5 18 H11 M14.5 18 L21 25"
                stroke="hsl(var(--primary))"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
                initial={{ pathLength: 0, opacity: 0.3 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{ duration: 0.8, ease: "easeInOut" }}
              />
              <motion.circle
                cx="21.4"
                cy="8.2"
                r="2"
                fill="hsl(var(--accent))"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.75, duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              />
            </svg>
            <motion.span
              className="font-fraunces text-lg tracking-tight text-foreground"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.4 }}
            >
              RahazaTrans
            </motion.span>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
};

export default Preloader;

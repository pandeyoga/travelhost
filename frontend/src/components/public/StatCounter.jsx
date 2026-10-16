import { useEffect, useRef, useState } from "react";
import { useInView, useReducedMotion } from "framer-motion";

// StatCounter.jsx — angka count-up saat masuk viewport (useInView).
// Reduced-motion: langsung tampil nilai final. Angka pakai tabular-nums + font mono.
export const StatCounter = ({ value = 0, decimals = 0, suffix = "", label, testId }) => {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, amount: 0.5 });
  const reduce = useReducedMotion();
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (!inView) return undefined;
    if (reduce) {
      setDisplay(value);
      return undefined;
    }
    let raf;
    const start = performance.now();
    const dur = 1400;
    const step = (now) => {
      const p = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(value * eased);
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [inView, value, reduce]);

  const shown = decimals > 0 ? Number(display).toFixed(decimals) : Math.round(display).toLocaleString("id-ID");

  return (
    <div ref={ref} data-testid={testId} className="text-center">
      <div className="font-mono text-3xl font-semibold tabular-nums text-current sm:text-[2.6rem] sm:leading-none">
        {shown}
        <span className="opacity-70">{suffix}</span>
      </div>
      <p className="mt-2 text-[12.5px] font-medium text-current opacity-75">{label}</p>
    </div>
  );
};

export default StatCounter;

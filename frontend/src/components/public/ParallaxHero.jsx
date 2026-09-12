import { useRef } from "react";
import { motion, useScroll, useTransform, useReducedMotion } from "framer-motion";

// ParallaxHero.jsx — hero sinematik dgn parallax depth (useScroll/useTransform).
// Overlay --gradient-hero (token) + noise tipis. Reduced-motion: tanpa parallax.
export const ParallaxHero = ({ image, children, className = "", minH = "min-h-[92vh]" }) => {
  const ref = useRef(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], ["0%", "16%"]);
  const scale = useTransform(scrollYProgress, [0, 1], [1, 1.12]);

  return (
    <section ref={ref} className={`relative flex ${minH} items-center overflow-hidden ${className}`}>
      <motion.div
        className="absolute inset-0 bg-primary bg-cover bg-center"
        style={
          reduce
            ? { backgroundImage: image ? `url('${image}')` : undefined }
            : { backgroundImage: image ? `url('${image}')` : undefined, y, scale }
        }
        aria-hidden="true"
      />
      <div className="absolute inset-0" style={{ background: "var(--gradient-hero)" }} aria-hidden="true" />
      <div className="pointer-events-none absolute inset-0 bg-noise opacity-[0.06] mix-blend-overlay" aria-hidden="true" />
      <div className="relative mx-auto w-full max-w-7xl px-4 pt-28 sm:px-6 lg:px-8">{children}</div>
    </section>
  );
};

export default ParallaxHero;

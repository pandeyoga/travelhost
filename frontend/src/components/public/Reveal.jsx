import { motion, useReducedMotion } from "framer-motion";

// Reveal.jsx — scroll-reveal staggered (whileInView). Hormati prefers-reduced-motion.
// Hanya animasi opacity + transform (anti layout thrash).
export const Reveal = ({ children, delay = 0, y = 24, className = "", as = "div", amount = 0.2, once = true }) => {
  const reduce = useReducedMotion();
  if (reduce) {
    const Tag = as;
    return <Tag className={className}>{children}</Tag>;
  }
  const MotionTag = motion[as] || motion.div;
  return (
    <MotionTag
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once, amount }}
      transition={{ duration: 0.6, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </MotionTag>
  );
};

export default Reveal;

import { motion, useReducedMotion } from "framer-motion";

// PageTransition.jsx — transisi antar halaman publik (fade + slide halus).
// Dibungkus AnimatePresence di PublicLayout (key = pathname). Reduced-motion: tanpa animasi.
export const PageTransition = ({ children }) => {
  const reduce = useReducedMotion();
  if (reduce) return <>{children}</>;
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
};

export default PageTransition;

import { cn } from "@/lib/utils";

// GlassCard.jsx — surface untuk PUBLIC (token-based, theme-aware).
//  variant="glass"   : frosted (untuk overlay di atas gambar / section gelap)
//  variant="premium" : kartu konten elevated berlapis (kedalaman nyata)
//  strong            : pakai glass-strong (frosted lebih pekat)
//  interactive       : tambahkan efek lift saat hover
export const GlassCard = ({
  as: Tag = "div",
  variant = "glass",
  strong = false,
  interactive = false,
  className,
  children,
  ...props
}) => {
  const base = variant === "premium" ? "card-premium" : strong ? "glass-strong" : "glass";
  return (
    <Tag className={cn(base, "rounded-2xl", interactive && "lift shimmer-on-hover", className)} {...props}>
      {children}
    </Tag>
  );
};

export default GlassCard;

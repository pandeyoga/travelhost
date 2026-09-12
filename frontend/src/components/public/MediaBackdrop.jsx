import { isVideoUrl } from "@/lib/mediaKind";

// AutoVideo — video latar/galeri yang mulai otomatis: muted + loop + playsInline wajib agar
// autoplay diizinkan browser seluler tanpa interaksi pengguna.
export function AutoVideo({ src, poster, className = "", controls = false, testId, ...rest }) {
  return (
    <video src={src} poster={poster || undefined} className={className} autoPlay muted loop playsInline
      preload="metadata" controls={controls} data-testid={testId} {...rest} />
  );
}

// MediaBackdrop — latar section: <video> autoplay bila URL video, selain itu background-image.
export default function MediaBackdrop({ src, className = "absolute inset-0", style, testId }) {
  if (!src) return <div className={`${className} bg-primary`} style={style} aria-hidden="true" />;
  if (isVideoUrl(src)) {
    return (
      <div className={`${className} overflow-hidden bg-primary`} style={style} aria-hidden="true" data-testid={testId}>
        <AutoVideo src={src} className="h-full w-full object-cover" />
      </div>
    );
  }
  return (
    <div className={`${className} bg-primary bg-cover bg-center`} aria-hidden="true" data-testid={testId}
      style={{ ...(style || {}), backgroundImage: `url('${src}')` }} />
  );
}

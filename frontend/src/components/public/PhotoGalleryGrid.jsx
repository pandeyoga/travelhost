import { useState } from "react";
import { Maximize2, Play } from "lucide-react";
import Lightbox from "@/components/public/Lightbox";
import Reveal from "@/components/public/Reveal";
import { AutoVideo } from "@/components/public/MediaBackdrop";
import { isVideoItem, itemUrl } from "@/lib/mediaKind";

// Grid foto/video responsif + lightbox. `items`: [{url, caption, kind?}] atau string URL.
// Video di kisi diputar otomatis (muted, loop) — klik untuk membuka penampil dengan kontrol.
export default function PhotoGalleryGrid({ items = [], testId = "photo-gallery", limit = 12 }) {
  const [lb, setLb] = useState({ open: false, index: 0 });
  const list = (Array.isArray(items) ? items : [])
    .map((it) => (typeof it === "string" ? { url: it, caption: "" } : it))
    .filter((it) => it && it.url);
  if (!list.length) return null;
  const shown = list.slice(0, limit);
  return (
    <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:gap-4 lg:grid-cols-4" data-testid={testId}>
        {shown.map((it, i) => {
          const video = isVideoItem(it);
          return (
            <Reveal key={`${it.url}-${i}`} delay={(i % 4) * 0.05}>
              <button type="button" onClick={() => setLb({ open: true, index: i })}
                className={`group relative block w-full overflow-hidden rounded-2xl bg-muted ${i % 5 === 0 ? "aspect-[4/5]" : "aspect-square"}`}
                data-testid={`${testId}-item-${i}`} data-kind={video ? "video" : "image"}
                aria-label={it.caption || `${video ? "Video" : "Foto"} ${i + 1}`}>
                {video ? (
                  <AutoVideo src={itemUrl(it)} poster={it.poster}
                    className="h-full w-full object-cover transition duration-700 ease-out group-hover:scale-105" />
                ) : (
                  <img src={it.url} alt={it.caption || ""} loading="lazy"
                    className="h-full w-full object-cover transition duration-700 ease-out group-hover:scale-105" />
                )}
                <span className="absolute inset-0 bg-gradient-to-t from-black/55 via-black/0 to-black/0 opacity-80" aria-hidden="true" />
                {video ? (
                  <span className="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full bg-black/50 px-2 py-0.5 text-[10.5px] font-semibold text-white backdrop-blur-sm">
                    <Play size={10} className="fill-white" /> Video
                  </span>
                ) : null}
                <Maximize2 size={15} className="absolute right-3 top-3 text-white/85 opacity-0 transition group-hover:opacity-100" />
                {it.caption ? <span className="absolute bottom-2.5 left-3 right-3 truncate text-left text-[12px] font-medium text-white">{it.caption}</span> : null}
              </button>
            </Reveal>
          );
        })}
      </div>
      <Lightbox images={list} open={lb.open} index={lb.index}
        onClose={() => setLb((s) => ({ ...s, open: false }))} onIndex={(i) => setLb({ open: true, index: i })} />
    </>
  );
}

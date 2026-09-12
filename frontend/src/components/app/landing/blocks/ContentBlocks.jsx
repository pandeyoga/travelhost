import { useEffect, useState } from "react";
import { Play, X, ChevronDown, Clock } from "lucide-react";
import { Heading, Icon, Wrap, EmptyNote } from "@/components/app/landing/shared";

/**
 * blocks/ContentBlocks.jsx — blok pendukung kepercayaan: keunggulan, lencana, galeri, video,
 * FAQ, hitung mundur, teks bebas, dan jarak.
 *
 * Dua hal yang sengaja dibuat "hidup" karena berpengaruh langsung ke konversi:
 *  - **Hitung mundur** benar-benar berdetak. Angka statis "atur tenggat" (bug lama: renderer
 *    membaca props yang salah nama) membuat promo terasa palsu.
 *  - **Galeri** punya penampil layar penuh. Pengunjung iklan armada ingin melihat kondisi unit
 *    dari dekat; thumbnail 120px tidak menjawab keraguan itu.
 */
export function ValueProps({ p, theme }) {
  return (
    <Wrap theme={theme}>
      <Heading title={p.title} theme={theme} />
      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4" data-testid="lp-value-props">
        {(p.items || []).map((it, i) => (
          <div key={i} className="bg-white p-4 shadow-sm" style={{ borderRadius: theme.radius }}>
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-full"
              style={{ background: `${theme.primary}18`, color: theme.primary }}>
              <Icon name={it.icon} />
            </span>
            <h3 className="mt-2.5 text-[14px] font-bold" style={{ color: theme.text }}>{it.title}</h3>
            {it.text ? <p className="mt-1 text-[12.5px] text-[#5B6472]">{it.text}</p> : null}
          </div>
        ))}
      </div>
    </Wrap>
  );
}

export function TrustBadges({ p, theme }) {
  return (
    <Wrap theme={theme} tight>
      {p.title ? (
        <p className="mb-2.5 text-center text-[12.5px] font-bold uppercase tracking-wide text-[#6B7280]">{p.title}</p>
      ) : null}
      <div className="flex flex-wrap items-center justify-center gap-2.5" data-testid="lp-trust">
        {(p.items || []).map((it, i) => (
          <span key={i}
            className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-[12px] font-semibold text-[#3C4350] shadow-sm">
            <span style={{ color: theme.primary }}><Icon name={it.icon} size={13} /></span> {it.label}
          </span>
        ))}
      </div>
    </Wrap>
  );
}

export function Gallery({ p, theme }) {
  const [open, setOpen] = useState(-1);
  const items = (p.items || []).filter((m) => m.src);
  const cols = { 1: "sm:grid-cols-1", 2: "sm:grid-cols-2", 3: "sm:grid-cols-3", 4: "sm:grid-cols-4" }[p.columns || 3];

  useEffect(() => {
    if (open < 0) return undefined;
    const onKey = (e) => { if (e.key === "Escape") setOpen(-1); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <Wrap theme={theme}>
      <Heading title={p.title} theme={theme} />
      {!items.length ? (
        <EmptyNote testId="lp-gallery-empty">Belum ada foto pada galeri ini.</EmptyNote>
      ) : (
        <div className={`grid grid-cols-2 gap-2.5 ${cols}`} data-testid="lp-gallery">
          {items.map((m, i) => (
            <button key={i} type="button" onClick={() => setOpen(i)} data-testid={`lp-gallery-${i}`}
              className="group relative h-[140px] overflow-hidden bg-[#EEF1F5]" style={{ borderRadius: theme.radius }}>
              <img src={m.src} alt={m.alt || `Foto ${i + 1}`} loading="lazy"
                className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" />
            </button>
          ))}
        </div>
      )}
      {open >= 0 && items[open] ? (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/85 p-4"
          onClick={() => setOpen(-1)} data-testid="lp-gallery-viewer">
          <button type="button" onClick={() => setOpen(-1)} aria-label="Tutup"
            data-testid="lp-gallery-close"
            className="absolute right-4 top-4 rounded-full bg-white/15 p-2 text-white hover:bg-white/25">
            <X size={18} />
          </button>
          <img src={items[open].src} alt={items[open].alt || "Foto"}
            className="max-h-[86vh] max-w-[92vw] rounded-xl object-contain" />
        </div>
      ) : null}
    </Wrap>
  );
}

export function VideoBlock({ p, theme }) {
  const media = p.media || {};
  const embed = media.embed_url;
  return (
    <Wrap theme={theme}>
      <Heading title={p.title} theme={theme} />
      <div className="relative flex h-[300px] items-center justify-center overflow-hidden bg-[#0E1726]"
        style={{ borderRadius: theme.radius }} data-testid="lp-video">
        {embed ? (
          <iframe src={embed} title={p.title || "Video"} allowFullScreen
            className="h-full w-full" style={{ border: 0 }} />
        ) : media.src ? (
          <video src={media.src} controls playsInline poster={media.poster || undefined}
            autoPlay={!!p.autoplay} loop={!!p.loop} muted={!!p.autoplay}
            className="h-full w-full object-cover" data-testid="lp-video-player" />
        ) : (
          <span className="flex items-center gap-2 text-[13px] text-white/80" data-testid="lp-video-empty">
            <Play size={16} /> Belum ada video — unggah berkas atau tempel tautan embed.
          </span>
        )}
      </div>
    </Wrap>
  );
}

export function Faq({ p, theme }) {
  const [open, setOpen] = useState(0);
  const items = p.items || [];
  return (
    <Wrap theme={theme}>
      <Heading title={p.title} theme={theme} />
      {!items.length ? (
        <EmptyNote testId="lp-faq-empty">Belum ada pertanyaan pada blok ini.</EmptyNote>
      ) : (
        <div className="divide-y divide-[#EEF0F3] bg-white" style={{ borderRadius: theme.radius }} data-testid="lp-faq">
          {items.map((it, i) => (
            <div key={i}>
              <button type="button" onClick={() => setOpen(open === i ? -1 : i)}
                data-testid={`lp-faq-${i}`}
                className="flex w-full items-center justify-between gap-3 p-4 text-left">
                <span className="text-[13.5px] font-bold" style={{ color: theme.text }}>{it.q}</span>
                <ChevronDown size={16} className={`shrink-0 transition-transform ${open === i ? "rotate-180" : ""}`}
                  style={{ color: theme.primary }} />
              </button>
              {open === i ? (
                <div className="px-4 pb-4 text-[12.5px] leading-relaxed text-[#5B6472]"
                  // eslint-disable-next-line react/no-danger
                  dangerouslySetInnerHTML={{ __html: it.a || "" }} />
              ) : null}
            </div>
          ))}
        </div>
      )}
    </Wrap>
  );
}

function remaining(deadline) {
  const end = new Date(String(deadline || "").length <= 16 ? `${deadline}:00` : deadline).getTime();
  if (!end || Number.isNaN(end)) return null;
  const diff = end - Date.now();
  if (diff <= 0) return { over: true, d: 0, h: 0, m: 0, s: 0 };
  return {
    over: false,
    d: Math.floor(diff / 86400000),
    h: Math.floor((diff % 86400000) / 3600000),
    m: Math.floor((diff % 3600000) / 60000),
    s: Math.floor((diff % 60000) / 1000),
  };
}

export function Countdown({ p, theme }) {
  const [left, setLeft] = useState(() => remaining(p.deadline));
  useEffect(() => {
    setLeft(remaining(p.deadline));
    const t = setInterval(() => setLeft(remaining(p.deadline)), 1000);
    return () => clearInterval(t);
  }, [p.deadline]);

  const cell = (value, label) => (
    <div className="min-w-[58px] rounded-lg px-2.5 py-1.5 text-center" style={{ background: theme.accent }}>
      <p className="text-[19px] font-extrabold leading-none tabular-nums text-[#1C1C1E]">
        {String(value).padStart(2, "0")}
      </p>
      <p className="mt-0.5 text-[9.5px] font-bold uppercase tracking-wide text-[#1C1C1E]/70">{label}</p>
    </div>
  );

  return (
    <Wrap theme={theme} tight>
      <div className="flex flex-wrap items-center justify-center gap-3 bg-white p-4 text-center shadow-sm"
        style={{ borderRadius: theme.radius }} data-testid="lp-countdown">
        <div>
          <p className="text-[14.5px] font-extrabold" style={{ color: theme.text }}>{p.title}</p>
          {p.subtitle ? <p className="mt-0.5 text-[12px] text-[#5B6472]">{p.subtitle}</p> : null}
        </div>
        {!left ? (
          <span className="inline-flex items-center gap-1.5 rounded-lg bg-[#F2F2F5] px-3 py-2 text-[12.5px] font-semibold text-[#6B6B73]"
            data-testid="lp-countdown-empty">
            <Clock size={13} /> Tenggat promo belum diatur
          </span>
        ) : left.over ? (
          <span className="rounded-lg bg-[#F2F2F5] px-3 py-2 text-[12.5px] font-bold text-[#6B6B73]"
            data-testid="lp-countdown-over">Promo sudah berakhir</span>
        ) : (
          <div className="flex items-center gap-1.5" data-testid="lp-countdown-live">
            {cell(left.d, "hari")}{cell(left.h, "jam")}{cell(left.m, "menit")}{cell(left.s, "detik")}
          </div>
        )}
      </div>
    </Wrap>
  );
}

export function RichText({ p, theme }) {
  return (
    <Wrap theme={theme}>
      <div className={p.width === "narrow" ? "mx-auto max-w-[720px]" : ""}>
        {p.title ? (
          <h2 className="mb-3 text-[20px] font-extrabold" style={{ color: theme.text }}>{p.title}</h2>
        ) : null}
        <div className="lp-rich bg-white p-5 text-[13.5px] leading-relaxed text-[#3C4350] shadow-sm"
          style={{ borderRadius: theme.radius }} data-testid="lp-rich-text"
          // eslint-disable-next-line react/no-danger
          dangerouslySetInnerHTML={{ __html: p.html || "" }} />
      </div>
    </Wrap>
  );
}

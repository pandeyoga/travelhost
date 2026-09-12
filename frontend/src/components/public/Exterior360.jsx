import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Hand, Loader2, Pause, Play } from "lucide-react";
import { Slider } from "@/components/ui/slider";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

// Exterior360 — viewer 360° eksterior berbasis frame (jumlah frame BEBAS, ikut data unit).
// Interaksi: drag (pointer), slider scrub, tombol putar kiri/kanan, auto-rotate play/pause.
export default function Exterior360({ frames = [], alt = "" }) {
  const lang = useLangValue();
  const n = frames.length;
  const [idx, setIdx] = useState(0);
  const [ready, setReady] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [interacted, setInteracted] = useState(false);
  const stageRef = useRef(null);
  const drag = useRef({ active: false, startX: 0, startIdx: 0 });

  useEffect(() => {
    if (!n) return undefined;
    let alive = true;
    let count = 0;
    frames.forEach((src) => {
      const img = new Image();
      img.onload = () => { if (!alive) return; count += 1; if (count >= Math.min(n, 6)) setReady(true); };
      img.onerror = img.onload;
      img.src = src;
    });
    return () => { alive = false; };
  }, [frames, n]);

  useEffect(() => {
    if (!playing || !ready) return undefined;
    const t = setInterval(() => setIdx((i) => (i + 1) % n), 110);
    return () => clearInterval(t);
  }, [playing, ready, n]);

  const step = (d) => { setPlaying(false); setInteracted(true); setIdx((i) => ((i + d) % n + n) % n); };

  const onPointerDown = (e) => {
    setPlaying(false); setInteracted(true); setDragging(true);
    drag.current = { active: true, startX: e.clientX, startIdx: idx };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };
  const onPointerMove = (e) => {
    if (!drag.current.active) return;
    const w = stageRef.current?.clientWidth || 600;
    const per = Math.max(3, w / (n * 1.15));
    const delta = Math.round((e.clientX - drag.current.startX) / per);
    setIdx((((drag.current.startIdx - delta) % n) + n) % n);
  };
  const onPointerUp = () => { drag.current.active = false; setDragging(false); };

  if (n < 2) return null;

  return (
    <div data-testid="ext360-viewer">
      <div
        ref={stageRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        data-testid="ext360-stage"
        className={`relative touch-pan-y select-none ${dragging ? "cursor-grabbing" : "cursor-grab"}`}
      >
        <img
          src={frames[idx]}
          alt={`${alt} 360°`}
          draggable={false}
          className="pointer-events-none mx-auto h-[340px] w-full object-contain drop-shadow-2xl sm:h-[500px] lg:h-[560px]"
        />
        {!interacted && ready ? (
          <div className="pointer-events-none absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-3">
            <ChevronLeft size={20} className="animate-pulse text-muted-foreground" />
            <span className="flex items-center gap-2 rounded-full bg-primary/90 px-5 py-2 text-[12.5px] font-semibold text-primary-foreground shadow-lg backdrop-blur-sm">
              <Hand size={14} className="animate-pulse" /> {bi("Swipe untuk memutar", "Swipe to rotate", lang)}
            </span>
            <ChevronRight size={20} className="animate-pulse text-muted-foreground" />
          </div>
        ) : null}
        {!ready ? (
          <div className="absolute inset-0 flex items-center justify-center" data-testid="ext360-loading">
            <span className="flex items-center gap-2 rounded-full bg-card/80 px-4 py-2 text-[12.5px] text-muted-foreground shadow-sm backdrop-blur-sm">
              <Loader2 size={14} className="animate-spin" /> {bi("Memuat 360°…", "Loading 360°…", lang)}
            </span>
          </div>
        ) : null}
      </div>

      <div className="mx-auto mt-3 flex max-w-md items-center gap-3 px-2">
        <div className="flex items-center gap-1.5">
          <button type="button" onClick={() => step(-1)} data-testid="ext360-prev" aria-label={bi("Putar kiri", "Rotate left", lang)}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-border text-muted-foreground transition hover:-translate-y-0.5 hover:text-foreground">
            <ChevronLeft size={15} />
          </button>
          <button type="button" onClick={() => { setInteracted(true); setPlaying((p) => !p); }} data-testid="ext360-play"
            aria-label={playing ? bi("Jeda", "Pause", lang) : bi("Putar otomatis", "Auto-rotate", lang)}
            className="flex h-9 w-9 items-center justify-center rounded-full text-primary-foreground transition hover:opacity-90" style={{ background: "var(--gradient-cta)" }}>
            {playing ? <Pause size={14} /> : <Play size={14} className="ml-0.5" />}
          </button>
          <button type="button" onClick={() => step(1)} data-testid="ext360-next" aria-label={bi("Putar kanan", "Rotate right", lang)}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-border text-muted-foreground transition hover:-translate-y-0.5 hover:text-foreground">
            <ChevronRight size={15} />
          </button>
        </div>
        <Slider
          value={[idx]}
          min={0}
          max={n - 1}
          step={1}
          onValueChange={(v) => { setPlaying(false); setInteracted(true); setIdx(v[0] ?? 0); }}
          className="flex-1"
          data-testid="ext360-slider"
        />
      </div>
    </div>
  );
}

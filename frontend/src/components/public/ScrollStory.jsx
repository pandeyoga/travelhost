import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { MapPin } from "lucide-react";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

// RouteMapInteractive memuat Leaflet (berat) → code-split via React.lazy (FASE 6 performa).
const RouteMapInteractive = lazy(() => import("@/components/public/RouteMapInteractive"));

// ScrollStory.jsx — narasi perjalanan: peta rute STICKY + langkah-langkah yang men-scroll.
// IntersectionObserver menentukan etape aktif (highlight polyline + pan peta). Tanpa parallax
// berat → ramah reduced-motion. Layout flex (bukan grid) demi konsistensi gate UX.
export default function ScrollStory({ points = [], title, loading = false, testId = "scroll-story" }) {
  const lang = useLangValue();
  const pts = Array.isArray(points) ? points : [];
  const [active, setActive] = useState(0);
  const stepRefs = useRef([]);

  useEffect(() => {
    if (pts.length < 2) return undefined;
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            const idx = Number(e.target.getAttribute("data-step"));
            if (!Number.isNaN(idx)) setActive(idx);
          }
        });
      },
      { rootMargin: "-45% 0px -45% 0px", threshold: 0 }
    );
    stepRefs.current.forEach((el) => el && obs.observe(el));
    return () => obs.disconnect();
  }, [pts.length]);

  // Loading state: tampilkan skeleton saat data rute masih dimuat (animate-pulse).
  if (loading) {
    return (
      <div data-testid={`${testId}-loading`} className="animate-pulse space-y-4">
        <div className="h-8 w-1/3 rounded-lg bg-muted" />
        <div className="h-[420px] rounded-2xl bg-muted" />
      </div>
    );
  }
  // Empty state: narasi rute butuh minimal 2 etape; bila kosong, jangan render section.
  if (!pts.length || pts.length < 2) return null;

  return (
    <div data-testid={testId}>
      <h2 className="font-fraunces text-2xl text-foreground sm:text-3xl">{title || bi("Perjalanan Anda", "Your Journey", lang)}</h2>
      <div className="mt-6 flex flex-col gap-6 lg:flex-row lg:items-start lg:gap-10">
        <div className="lg:sticky lg:top-28 lg:w-[52%]">
          <div className="overflow-hidden rounded-2xl border border-border" style={{ height: 420 }}>
            <Suspense fallback={<div className="h-full w-full animate-pulse bg-muted" data-testid="routemap-suspense" />}>
              <RouteMapInteractive points={pts} activeIndex={active} />
            </Suspense>
          </div>
          <div className="mt-3 flex items-center gap-2 text-[12.5px] text-muted-foreground">
            <MapPin size={14} className="text-primary" /> {pts[active]?.name} · {bi("Etape", "Leg", lang)} {active + 1}/{pts.length}
          </div>
        </div>
        <div className="flex-1 space-y-5">
          {pts.map((p, i) => (
            <div
              key={i}
              ref={(el) => { stepRefs.current[i] = el; }}
              data-step={i}
              data-testid={`story-step-${i}`}
              className={`rounded-2xl border p-5 transition-all duration-300 ${i === active ? "glass border-[hsla(var(--glass-border))] shadow-[var(--shadow-lift)]" : "border-border bg-card/60"}`}
            >
              <span className={`inline-flex h-7 items-center rounded-full px-2.5 text-[11.5px] font-semibold ${i === active ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground"}`}>{bi("Etape", "Leg", lang)} {i + 1}</span>
              <h3 className="mt-2 font-fraunces text-xl text-foreground">{p.name}</h3>
              {p.desc ? <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted-foreground">{p.desc}</p> : null}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

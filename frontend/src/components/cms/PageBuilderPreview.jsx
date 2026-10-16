import { useEffect, useRef, useState } from "react";
import { Monitor, Tablet, Smartphone, RefreshCw, MousePointerClick } from "lucide-react";
import { PAGE_URL } from "@/lib/siteSections";

// Pratinjau LANGSUNG Page Builder: halaman publik asli dimuat di iframe (?pbPreview=1),
// draft section dikirim via postMessage → tampil real-time SEBELUM disimpan.
// Klik section di pratinjau memilihnya di editor (pesan "select" dari iframe).

const DEVICES = [
  ["desktop", "Desktop", Monitor, 1440],
  ["tablet", "Tablet", Tablet, 834],
  ["mobile", "Ponsel", Smartphone, 390],
];
const FRAME_H = 640;

export default function PageBuilderPreview({ slug, base, sections, selectedId, onSelect }) {
  const siteOrigin = new URL(base).origin;
  const frameRef = useRef(null);
  const boxRef = useRef(null);
  const sectionsRef = useRef(sections);
  const [device, setDevice] = useState("desktop");
  const [scale, setScale] = useState(0.5);
  const [nonce, setNonce] = useState(0);
  const [frameLoading, setFrameLoading] = useState(true);
  sectionsRef.current = sections;

  const width = DEVICES.find((d) => d[0] === device)[3];
  const post = (msg) => {
    const win = frameRef.current && frameRef.current.contentWindow;
    if (win) win.postMessage({ __pb: true, ...msg }, siteOrigin);
  };

  useEffect(() => {
    const onMsg = (e) => {
      if (e.origin !== siteOrigin) return;
      const m = e.data;
      if (!m || !m.__pb) return;
      if (m.type === "ready" && m.slug === slug) {
        setFrameLoading(false);
        post({ type: "sections", slug, sections: sectionsRef.current });
      }
      if (m.type === "select" && onSelect) onSelect(m.id);
    };
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
  }, [slug, onSelect]);

  useEffect(() => {
    const t = setTimeout(() => post({ type: "sections", slug, sections }), 200);
    return () => clearTimeout(t);
  }, [sections, slug]);
  useEffect(() => { if (selectedId) post({ type: "highlight", id: selectedId }); }, [selectedId]);
  useEffect(() => { setFrameLoading(true); }, [slug, nonce]);

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return undefined;
    const calc = () => setScale(Math.min(1, Math.max(0.2, (el.clientWidth - 2) / width)));
    calc();
    const ro = new ResizeObserver(calc);
    ro.observe(el);
    return () => ro.disconnect();
  }, [width]);

  return (
    <div className="min-w-0 flex-1" data-testid="pb-preview-panel">
      <div className="flex flex-wrap items-center gap-1.5">
        {DEVICES.map(([key, label, Icon]) => (
          <button key={key} className={`secondary-button !h-8 !px-2.5 !text-[11.5px] ${device === key ? "!border-[#0A84FF] !text-[#0A84FF]" : ""}`}
            onClick={() => setDevice(key)} data-testid={`pb-device-${key}`}>
            <Icon size={12} /> {label}
          </button>
        ))}
        <button className="secondary-button !h-8 !px-2.5 !text-[11.5px]" onClick={() => setNonce((n) => n + 1)} data-testid="pb-preview-reload">
          <RefreshCw size={12} /> Muat ulang
        </button>
        <span className="ml-auto inline-flex items-center gap-1 text-[11.5px] text-[#8E8E93]">
          <MousePointerClick size={12} /> Klik section di pratinjau utk mengeditnya
        </span>
      </div>
      <div ref={boxRef} className="relative mt-2 overflow-hidden rounded-[14px] border border-[#E1E1E6] bg-[#EDEDF2]"
        style={{ height: FRAME_H + 2 }}>
        {frameLoading ? (
          <p className="absolute inset-x-0 top-1/2 -translate-y-1/2 text-center text-[12px] text-[#8E8E93]" data-testid="pb-preview-loading">
            Memuat pratinjau…
          </p>
        ) : null}
        <div style={{ width: width * scale, height: FRAME_H, margin: "0 auto" }}>
          <iframe key={`${slug}-${base}-${nonce}`} ref={frameRef} title="Pratinjau halaman situs"
            src={`${base}${PAGE_URL[slug]}?pbPreview=1&pbOrigin=${encodeURIComponent(window.location.origin)}`}
            style={{ width, height: FRAME_H / scale, transform: `scale(${scale})`, transformOrigin: "top left", border: 0 }}
            data-testid="pb-preview-frame" />
        </div>
      </div>
    </div>
  );
}

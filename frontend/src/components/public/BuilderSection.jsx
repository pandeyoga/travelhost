import { useEffect, useRef, useState } from "react";
import { isBuilderPreview, builderOrigin } from "@/hooks/useSitePage";

// Pembungkus section di mode pratinjau Page Builder: klik = pilih section itu di editor
// (postMessage ke parent), pesan "highlight" dari editor = scroll + sorot section-nya.
// Di luar mode pratinjau: merender children apa adanya, tanpa efek apa pun.
export default function BuilderSection({ sec, children }) {
  const ref = useRef(null);
  const [active, setActive] = useState(false);
  const preview = isBuilderPreview();
  const id = sec && sec.id;

  useEffect(() => {
    if (!preview || !id) return undefined;
    const onMsg = (e) => {
      if (e.origin !== builderOrigin()) return;
      const m = e.data;
      if (m && m.__pb && m.type === "highlight" && m.id === id) {
        if (ref.current) ref.current.scrollIntoView({ behavior: "smooth", block: "center" });
        setActive(true);
        setTimeout(() => setActive(false), 1800);
      }
    };
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
  }, [preview, id]);

  if (!preview) return children;

  const select = (e) => {
    e.preventDefault();
    e.stopPropagation();
    window.parent.postMessage({ __pb: true, type: "select", id }, builderOrigin());
  };
  return (
    <div ref={ref} onClickCapture={select} data-pb-section={id} title="Klik untuk mengedit section ini"
      className={`relative cursor-pointer outline-2 -outline-offset-2 outline-[hsl(var(--ring))] transition-[outline-color] hover:outline ${active ? "outline animate-pulse" : ""}`}>
      {children}
    </div>
  );
}

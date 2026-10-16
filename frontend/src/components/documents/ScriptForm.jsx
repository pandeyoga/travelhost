import { useRef } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Bold, Italic, Underline, Table2, Rows3 } from "lucide-react";

const TOOLS = [
  ["<b>", "</b>", Bold, "Tebal"], ["<i>", "</i>", Italic, "Miring"], ["<u>", "</u>", Underline, "Garis bawah"],
];

export default function ScriptForm({ script, value, onChange }) {
  const ref = useRef(null);

  const insertAt = (before, after = "") => {
    const el = ref.current;
    if (!el) { onChange((value || "") + before + after); return; }
    const s = el.selectionStart ?? value.length, e = el.selectionEnd ?? value.length;
    const next = value.slice(0, s) + before + value.slice(s, e) + after + value.slice(e);
    onChange(next);
    requestAnimationFrame(() => { el.focus(); el.setSelectionRange(s + before.length, e + before.length); });
  };

  return (
    <section className="section-card" data-testid="script-form">
      <div className="section-head"><h2>Naskah dokumen</h2>
        <span className="text-[11.5px] text-[#6B6B73]">{script?.customized ? `Disunting (v${script.version})` : "Naskah bawaan"}</span>
      </div>
      <div className="section-body space-y-3">
        <p className="text-[12px] text-[#6B6B73]">
          Klik placeholder untuk menyisipkan. Baris berbentuk <code>Label : Nilai</code> tercetak sebagai tabel kunci-nilai.
          Marker <code>{"{{tabel_rincian}}"}</code> / <code>{"{{tabel_biaya}}"}</code> menempatkan tabel otomatis di posisi itu.
        </p>
        <div className="flex flex-wrap items-center gap-1.5">
          {TOOLS.map(([b, a, Icon, title]) => (
            <button key={title} type="button" className="icon-button !h-8 !w-8" title={title} onClick={() => insertAt(b, a)} data-testid={`script-tool-${title}`}><Icon size={14} /></button>
          ))}
          <button type="button" className="secondary-button !h-8" onClick={() => insertAt("\n{{tabel_rincian}}\n")} data-testid="script-tool-rincian"><Table2 size={13} /> Tabel rincian</button>
          <button type="button" className="secondary-button !h-8" onClick={() => insertAt("\n{{tabel_biaya}}\n")} data-testid="script-tool-biaya"><Rows3 size={13} /> Tabel biaya</button>
        </div>
        <Textarea ref={ref} value={value} onChange={(e) => onChange(e.target.value)} rows={16} className="font-mono text-[12.5px] leading-relaxed" data-testid="script-editor" />
        <div>
          <p className="mb-1.5 text-[11px] uppercase tracking-wide text-[#8E8E93]">Placeholder yang tersedia</p>
          <div className="flex flex-wrap gap-1.5" data-testid="script-placeholders">
            {(script?.placeholders || []).map((p) => (
              <button key={p.token} type="button" onClick={() => insertAt(`{{${p.token}}}`)} title={p.label}
                className="rounded-full border border-[#E5E5EA] bg-white px-2.5 py-1 text-[11.5px] text-[#1C1C1E] transition-colors hover:border-[#007AFF] hover:text-[#007AFF]" data-testid={`ph-${p.token}`}>
                {`{{${p.token}}}`} <span className="text-[#8E8E93]">· {p.label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

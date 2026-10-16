import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bold, Italic, Heading2, Heading3, List, ListOrdered, Quote, Link2, ImagePlus,
  Minus, Code2, Eraser, WrapText, Check, X,
} from "lucide-react";
import MediaPickerDialog from "@/components/media/MediaPickerDialog";

/**
 * RichTextEditor — CMS-09: penyunting isi artikel.
 *
 * Kenapa bukan textarea lagi
 * -------------------------
 * Sebelumnya isi artikel adalah teks polos yang dipisah baris kosong. Akibatnya editor tidak
 * bisa membuat sub-judul, daftar poin, kutipan, atau menyisipkan gambar di tengah tulisan —
 * padahal itulah bentuk artikel yang dibaca orang (dan yang dipahami mesin pencari lewat
 * struktur heading).
 *
 * Kenapa aman
 * -----------
 * Editor ini TIDAK menjadi satu-satunya pagar. Server tetap membersihkan HTML dengan allowlist
 * ketat (`services/richtext.sanitize`), jadi walaupun seseorang menempelkan `<script>` atau
 * memanggil `PUT /api/content/articles/{id}` lewat curl, yang tersimpan tetap bersih.
 * Di sisi editor kita hanya merapikan keluaran `contenteditable` (mis. `<div>` → `<p>`,
 * atribut `style` dibuang) supaya hasil simpan tidak kehilangan struktur saat dibersihkan.
 *
 * Mode HTML disediakan sengaja: editor yang paham HTML bisa menyunting langsung, dan
 * artikel LAMA berformat teks polos bisa dinaikkan ke format kaya lewat satu tombol
 * (konversi TIDAK otomatis — mengubah konten tayang tanpa perintah adalah hal terakhir
 * yang boleh dilakukan sebuah CMS).
 */
const HTML_TAG_RE = /<\s*(p|h2|h3|h4|ul|ol|li|blockquote|img|figure|hr|strong|em|b|i|a|br)\b/i;

export function looksLikeHtml(value) {
  return HTML_TAG_RE.test(String(value || ""));
}

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/** Teks polos (format lama) → paragraf HTML. Dipakai HANYA saat editor menekan tombol. */
export function textToHtml(value) {
  const blocks = String(value || "").split(/\n{2,}/).map((b) => b.trim()).filter(Boolean);
  if (!blocks.length) return "";
  return blocks.map((b) => `<p>${escapeHtml(b).replace(/\n/g, "<br />")}</p>`).join("\n");
}

/** Rapikan keluaran contenteditable agar selamat melewati allowlist server. */
function normalize(html) {
  return String(html || "")
    .replace(/<div(\s[^>]*)?>/gi, "<p>")
    .replace(/<\/div>/gi, "</p>")
    .replace(/\sstyle="[^"]*"/gi, "")
    .replace(/\sclass="[^"]*"/gi, "")
    .replace(/<font(\s[^>]*)?>/gi, "")
    .replace(/<\/font>/gi, "")
    .replace(/<p><br\s*\/?><\/p>/gi, "")
    .trim();
}

const TOOLS = [
  { id: "h2", title: "Sub-judul (H2)", Icon: Heading2, cmd: ["formatBlock", "<h2>"] },
  { id: "h3", title: "Sub-judul kecil (H3)", Icon: Heading3, cmd: ["formatBlock", "<h3>"] },
  { id: "p", title: "Paragraf biasa", Icon: WrapText, cmd: ["formatBlock", "<p>"] },
  { id: "bold", title: "Tebal", Icon: Bold, cmd: ["bold"] },
  { id: "italic", title: "Miring", Icon: Italic, cmd: ["italic"] },
  { id: "ul", title: "Daftar poin", Icon: List, cmd: ["insertUnorderedList"] },
  { id: "ol", title: "Daftar bernomor", Icon: ListOrdered, cmd: ["insertOrderedList"] },
  { id: "quote", title: "Kutipan", Icon: Quote, cmd: ["formatBlock", "<blockquote>"] },
  { id: "hr", title: "Pemisah", Icon: Minus, cmd: ["insertHorizontalRule"] },
  { id: "clear", title: "Hapus format", Icon: Eraser, cmd: ["removeFormat"] },
];

export default function RichTextEditor({ value, onChange, testId = "rte", placeholder = "Tulis isi artikel…" }) {
  const ref = useRef(null);
  const focused = useRef(false);
  const [mode, setMode] = useState("rich");
  const [linkOpen, setLinkOpen] = useState(false);
  const [linkUrl, setLinkUrl] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);

  const raw = String(value || "");
  const isLegacyPlain = raw.trim().length > 0 && !looksLikeHtml(raw);

  useEffect(() => {
    // Tanpa ini `contenteditable` membuat <div> untuk tiap baris baru; <div> tidak ada di
    // allowlist server sehingga struktur paragraf akan hilang saat disimpan.
    try { document.execCommand("defaultParagraphSeparator", false, "p"); } catch { /* peramban lama */ }
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el || mode !== "rich") return;
    // Jangan sentuh DOM saat sedang diketik — itu memindahkan kursor ke awal.
    if (!focused.current && el.innerHTML !== raw) el.innerHTML = raw;
  }, [raw, mode]);

  const emit = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    onChange(normalize(el.innerHTML));
  }, [onChange]);

  const exec = (cmd, arg) => {
    const el = ref.current;
    if (el) el.focus();
    try { document.execCommand(cmd, false, arg); } catch { /* diabaikan: server tetap pagar akhir */ }
    emit();
  };

  const applyLink = () => {
    const url = linkUrl.trim();
    setLinkOpen(false);
    setLinkUrl("");
    if (!url) return;
    const safe = /^(https?:|mailto:|\/)/i.test(url) ? url : `https://${url}`;
    exec("createLink", safe);
  };

  const onPaste = (e) => {
    // Tempel sebagai TEKS: tempelan dari Word/Docs membawa <span style> & <font> yang semuanya
    // akan dibuang server — lebih jujur membuang formatnya sekarang daripada "hilang misterius".
    e.preventDefault();
    const text = (e.clipboardData || window.clipboardData)?.getData("text/plain") || "";
    exec("insertText", text);
  };

  return (
    <div className="rounded-[12px] border border-[#E5E5EA] bg-white" data-testid={testId}>
      <div className="flex flex-wrap items-center gap-1 border-b border-[#F2F2F5] px-2 py-1.5">
        {mode === "rich" ? (
          <>
            {TOOLS.map(({ id, title, Icon, cmd }) => (
              <button key={id} type="button" title={title} aria-label={title}
                onClick={() => exec(cmd[0], cmd[1])}
                className="flex h-7 w-7 items-center justify-center rounded-md text-[#3A3A3C] transition hover:bg-[#F2F2F5]"
                data-testid={`${testId}-tool-${id}`}>
                <Icon size={14} />
              </button>
            ))}
            <button type="button" title="Tautan" aria-label="Tautan" onClick={() => setLinkOpen((v) => !v)}
              className="flex h-7 w-7 items-center justify-center rounded-md text-[#3A3A3C] transition hover:bg-[#F2F2F5]"
              data-testid={`${testId}-tool-link`}>
              <Link2 size={14} />
            </button>
            <button type="button" title="Sisipkan gambar dari Media Library" aria-label="Sisipkan gambar"
              onClick={() => setPickerOpen(true)}
              className="flex h-7 w-7 items-center justify-center rounded-md text-[#3A3A3C] transition hover:bg-[#F2F2F5]"
              data-testid={`${testId}-tool-image`}>
              <ImagePlus size={14} />
            </button>
          </>
        ) : (
          <span className="px-1 text-[11.5px] text-[#6B6B73]">Mode HTML — tag di luar daftar aman akan dibuang server saat disimpan.</span>
        )}
        <span className="ml-auto" />
        {isLegacyPlain ? (
          <button type="button" onClick={() => onChange(textToHtml(raw))}
            className="rounded-md border border-[#FFE6B0] bg-[#FFF8EC] px-2 py-1 text-[11px] font-semibold text-[#8A5A00]"
            data-testid={`${testId}-convert`}>
            Ubah teks lama → paragraf
          </button>
        ) : null}
        <button type="button" onClick={() => setMode((m) => (m === "rich" ? "html" : "rich"))}
          title="Sunting HTML" aria-label="Sunting HTML"
          className={`flex h-7 items-center gap-1 rounded-md px-2 text-[11px] font-semibold transition ${mode === "html" ? "bg-[#0058CC] text-white" : "text-[#3A3A3C] hover:bg-[#F2F2F5]"}`}
          data-testid={`${testId}-html-toggle`}>
          <Code2 size={13} /> HTML
        </button>
      </div>

      {linkOpen && mode === "rich" ? (
        <div className="flex items-center gap-1.5 border-b border-[#F2F2F5] bg-[#F7F8FA] px-2 py-1.5">
          <input value={linkUrl} onChange={(e) => setLinkUrl(e.target.value)}
            placeholder="https://… atau /packages/bromo-3h2m" data-testid={`${testId}-link-url`}
            className="h-8 flex-1 rounded-md border border-[#E5E5EA] px-2 text-[12px] text-[#1C1C1E] outline-none focus:border-[#0058CC]" />
          <button type="button" onClick={applyLink} title="Terapkan tautan"
            className="flex h-8 w-8 items-center justify-center rounded-md bg-[#0058CC] text-white"
            data-testid={`${testId}-link-apply`}><Check size={14} /></button>
          <button type="button" onClick={() => { setLinkOpen(false); setLinkUrl(""); }} title="Batal"
            className="flex h-8 w-8 items-center justify-center rounded-md border border-[#E5E5EA] text-[#6B6B73]"><X size={14} /></button>
        </div>
      ) : null}

      {mode === "rich" ? (
        <div className="relative">
          <div ref={ref} contentEditable suppressContentEditableWarning
            onInput={emit} onBlur={() => { focused.current = false; emit(); }}
            onFocus={() => { focused.current = true; }} onPaste={onPaste}
            role="textbox" aria-multiline="true" aria-label="Isi artikel"
            className="rte-surface min-h-[220px] max-h-[420px] overflow-y-auto px-3.5 py-3 text-[13.5px] leading-[1.75] text-[#1C1C1E] outline-none"
            data-testid={`${testId}-surface`} />
          {!raw.trim() ? (
            <p className="pointer-events-none absolute left-3.5 top-3 text-[13px] text-[#B0B0B8]">{placeholder}</p>
          ) : null}
        </div>
      ) : (
        <textarea value={raw} onChange={(e) => onChange(e.target.value)} rows={12}
          className="w-full resize-y rounded-b-[12px] px-3.5 py-3 font-mono text-[12px] leading-[1.6] text-[#1C1C1E] outline-none"
          data-testid={`${testId}-html`} />
      )}

      <p className="border-t border-[#F2F2F5] px-3.5 py-2 text-[10.5px] leading-relaxed text-[#8A8A8F]">
        Yang tersimpan: judul H2/H3 · paragraf · tebal/miring · daftar · kutipan · tautan · gambar · pemisah.
        Skrip, iframe, dan atribut gaya selalu dibuang server (anti-XSS) — jadi tampilan di situs mengikuti tema, bukan gaya tempelan.
      </p>

      <MediaPickerDialog open={pickerOpen} onOpenChange={setPickerOpen} pickKind="image"
        title="Sisipkan gambar ke artikel"
        onPick={(asset) => { if (asset?.url) exec("insertImage", asset.url); }} />
    </div>
  );
}

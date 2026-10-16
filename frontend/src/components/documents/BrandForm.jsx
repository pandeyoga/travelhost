import { useRef, useState } from "react";
import { toast } from "sonner";
import { ImagePlus, Loader2, X } from "lucide-react";
import apiClient from "@/services/apiClient";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export function Field({ label, children, hint }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-[12px]">{label}</Label>
      {children}
      {hint ? <p className="text-[11px] text-[#8E8E93]">{hint}</p> : null}
    </div>
  );
}

export function ImagePicker({ label, fileId, onChange, testId }) {
  const ref = useRef(null);
  const [busy, setBusy] = useState(false);
  const [url, setUrl] = useState("");
  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData(); fd.append("file", file);
      const r = await apiClient.post("/doc-assets", fd, { headers: { "Content-Type": "multipart/form-data" } });
      onChange(r.data.id); setUrl(`${process.env.REACT_APP_BACKEND_URL}${r.data.url}`); toast.success("Gambar diunggah");
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal mengunggah gambar"); }
    finally { setBusy(false); }
  };
  return (
    <div className="space-y-1.5">
      <Label className="text-[12px]">{label}</Label>
      <div className="flex items-center gap-2">
        <input ref={ref} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => upload(e.target.files?.[0])} />
        <button type="button" className="secondary-button !h-8" onClick={() => ref.current?.click()} disabled={busy} data-testid={testId}>
          {busy ? <Loader2 size={13} className="animate-spin" /> : <ImagePlus size={13} />} {fileId ? "Ganti" : "Unggah"}
        </button>
        {fileId ? (
          <>
            {url ? <img src={url} alt="" className="h-8 max-w-[90px] rounded border border-[#E5E5EA] object-contain" /> : <span className="truncate text-[11px] text-[#6B6B73]">{fileId}</span>}
            <button type="button" className="icon-button !h-7 !w-7" title="Hapus" onClick={() => { onChange(null); setUrl(""); }} data-testid={`${testId}-clear`}><X size={12} /></button>
          </>
        ) : <span className="text-[11px] text-[#8E8E93]">PNG/JPG, maks 3 MB</span>}
      </div>
    </div>
  );
}

export default function BrandForm({ brand, onChange }) {
  const b = brand || {};
  const set = (k, v) => onChange({ ...b, [k]: v });
  const text = (k, label, hint) => (
    <Field label={label} hint={hint}><Input value={b[k] ?? ""} onChange={(e) => set(k, e.target.value)} data-testid={`brand-${k}`} /></Field>
  );
  const num = (k, label, min, max) => (
    <Field label={label}><Input type="number" min={min} max={max} value={b[k] ?? ""} onChange={(e) => set(k, e.target.value === "" ? null : Number(e.target.value))} data-testid={`brand-${k}`} /></Field>
  );
  const mode = (k, label) => (
    <Field label={label}>
      <Select value={b[k] || "system"} onValueChange={(v) => set(k, v)}>
        <SelectTrigger data-testid={`brand-${k}`}><SelectValue /></SelectTrigger>
        <SelectContent><SelectItem value="system">Dirakit sistem (logo + identitas)</SelectItem><SelectItem value="image">Gambar buatan desainer</SelectItem><SelectItem value="none">Tanpa (kertas berkop cetak)</SelectItem></SelectContent>
      </Select>
    </Field>
  );
  return (
    <div className="space-y-3" data-testid="brand-form">
      <section className="section-card"><div className="section-head"><h2>Identitas perusahaan</h2></div>
        <div className="section-body grid grid-cols-1 gap-3 sm:grid-cols-2">
          {text("company_name", "Nama perusahaan")}{text("tagline", "Tagline")}
          <div className="sm:col-span-2">{text("address", "Alamat")}</div>
          {text("phone", "Telepon / WhatsApp")}{text("email", "Email")}{text("website", "Website")}{text("npwp", "NPWP")}
        </div>
      </section>
      <section className="section-card"><div className="section-head"><h2>Kop, footer & watermark</h2></div>
        <div className="section-body grid grid-cols-1 gap-3 sm:grid-cols-2">
          {mode("header_mode", "Mode kop surat")}{mode("footer_mode", "Mode footer")}
          <ImagePicker label="Logo" fileId={b.logo_file_id} onChange={(v) => set("logo_file_id", v)} testId="brand-logo" />
          <ImagePicker label="Gambar kop (mode gambar)" fileId={b.header_image_file_id} onChange={(v) => set("header_image_file_id", v)} testId="brand-header-image" />
          <ImagePicker label="Gambar footer (mode gambar)" fileId={b.footer_image_file_id} onChange={(v) => set("footer_image_file_id", v)} testId="brand-footer-image" />
          <ImagePicker label="Gambar watermark" fileId={b.watermark_file_id} onChange={(v) => set("watermark_file_id", v)} testId="brand-watermark-image" />
          {text("footer_text", "Teks footer", "Kosong = dirakit dari identitas")}{text("watermark_text", "Teks watermark", 'mis. "LUNAS" atau "SALINAN"')}
          {num("watermark_opacity", "Kepekatan watermark (%)", 0, 60)}
          <div className="flex items-center justify-between rounded-[10px] border border-[#F2F2F5] px-3 py-2"><span className="text-[12.5px]">Nomor halaman</span><Switch checked={b.show_page_numbers !== false} onCheckedChange={(v) => set("show_page_numbers", v)} data-testid="brand-show_page_numbers" /></div>
        </div>
      </section>
      <section className="section-card"><div className="section-head"><h2>Warna & kertas</h2></div>
        <div className="section-body grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Field label="Warna aksen"><div className="flex items-center gap-2"><input type="color" value={b.accent_color || "#007AFF"} onChange={(e) => set("accent_color", e.target.value)} className="h-9 w-10 rounded border border-[#E5E5EA]" data-testid="brand-accent_color" /><Input value={b.accent_color || ""} onChange={(e) => set("accent_color", e.target.value)} /></div></Field>
          <Field label="Warna teks"><div className="flex items-center gap-2"><input type="color" value={b.text_color || "#1C1C1E"} onChange={(e) => set("text_color", e.target.value)} className="h-9 w-10 rounded border border-[#E5E5EA]" data-testid="brand-text_color" /><Input value={b.text_color || ""} onChange={(e) => set("text_color", e.target.value)} /></div></Field>
          <Field label="Kertas">
            <Select value={b.paper || "A4"} onValueChange={(v) => set("paper", v)}><SelectTrigger data-testid="brand-paper"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="A4">A4</SelectItem><SelectItem value="LETTER">Letter</SelectItem><SelectItem value="LEGAL">Legal / F4</SelectItem></SelectContent></Select>
          </Field>
          {num("margin_top_mm", "Margin atas (mm)", 8, 60)}{num("margin_bottom_mm", "Margin bawah (mm)", 8, 60)}
          {num("margin_left_mm", "Margin kiri (mm)", 8, 50)}{num("margin_right_mm", "Margin kanan (mm)", 8, 50)}
        </div>
      </section>
    </div>
  );
}

export { Textarea };

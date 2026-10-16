import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Field } from "@/components/documents/BrandForm";

const Toggle = ({ label, checked, onChange, testId }) => (
  <div className="flex items-center justify-between rounded-[10px] border border-[#F2F2F5] px-3 py-2">
    <span className="text-[12.5px]">{label}</span>
    <Switch checked={checked} onCheckedChange={onChange} data-testid={testId} />
  </div>
);

export default function TableForm({ table, onChange }) {
  const t = table || {};
  const set = (k, v) => onChange({ ...t, [k]: v });
  return (
    <section className="section-card" data-testid="table-form">
      <div className="section-head"><h2>Gaya tabel dokumen</h2></div>
      <div className="section-body grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label="Garis tabel">
          <Select value={t.grid || "full"} onValueChange={(v) => set("grid", v)}><SelectTrigger data-testid="table-grid"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="full">Kotak penuh</SelectItem><SelectItem value="horizontal">Garis mendatar saja</SelectItem><SelectItem value="none">Transparan (tanpa garis)</SelectItem></SelectContent></Select>
        </Field>
        <Field label="Posisi tabel">
          <Select value={t.alignment || "left"} onValueChange={(v) => set("alignment", v)}><SelectTrigger data-testid="table-alignment"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="left">Kiri</SelectItem><SelectItem value="center">Tengah</SelectItem><SelectItem value="right">Kanan</SelectItem></SelectContent></Select>
        </Field>
        <Field label="Ukuran huruf tabel (6–12)"><Input type="number" min={6} max={12} step={0.5} value={t.font_size ?? 8.5} onChange={(e) => set("font_size", Number(e.target.value))} data-testid="table-font_size" /></Field>
        <Field label="Lebar tabel (%)"><Input type="number" min={40} max={100} value={t.width_pct ?? 100} onChange={(e) => set("width_pct", Number(e.target.value))} data-testid="table-width_pct" /></Field>
        <Field label="Warna garis"><div className="flex items-center gap-2"><input type="color" value={t.grid_color || "#E2E8F0"} onChange={(e) => set("grid_color", e.target.value)} className="h-9 w-10 rounded border border-[#E5E5EA]" data-testid="table-grid_color" /><Input value={t.grid_color || ""} onChange={(e) => set("grid_color", e.target.value)} /></div></Field>
        <div className="grid gap-2 sm:col-span-2 sm:grid-cols-2">
          <Toggle label="Tampilkan nama kolom" checked={t.show_header !== false} onChange={(v) => set("show_header", v)} testId="table-show_header" />
          <Toggle label="Kepala tabel berwarna aksen" checked={t.header_fill !== false} onChange={(v) => set("header_fill", v)} testId="table-header_fill" />
          <Toggle label="Baris belang (zebra)" checked={t.zebra !== false} onChange={(v) => set("zebra", v)} testId="table-zebra" />
          <Toggle label="Sorot baris total" checked={t.total_highlight !== false} onChange={(v) => set("total_highlight", v)} testId="table-total_highlight" />
        </div>
      </div>
    </section>
  );
}

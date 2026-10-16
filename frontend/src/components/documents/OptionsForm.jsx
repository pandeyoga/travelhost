import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "@/components/documents/BrandForm";

const Toggle = ({ label, checked, onChange, testId }) => (
  <div className="flex items-center justify-between rounded-[10px] border border-[#F2F2F5] px-3 py-2">
    <span className="text-[12.5px]">{label}</span>
    <Switch checked={checked} onCheckedChange={onChange} data-testid={testId} />
  </div>
);

export default function OptionsForm({ options, onChange }) {
  const o = options || {};
  const set = (k, v) => onChange({ ...o, [k]: v });
  return (
    <section className="section-card" data-testid="options-form">
      <div className="section-head"><h2>Opsi dokumen</h2></div>
      <div className="section-body grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Toggle label="Tampilkan judul dokumen" checked={o.show_title !== false} onChange={(v) => set("show_title", v)} testId="opt-show_title" />
        <Toggle label="Tampilkan nomor dokumen" checked={o.show_doc_number !== false} onChange={(v) => set("show_doc_number", v)} testId="opt-show_doc_number" />
        <Toggle label="Tempat & tanggal di atas tanda tangan" checked={o.show_place_date !== false} onChange={(v) => set("show_place_date", v)} testId="opt-show_place_date" />
        <Toggle label="Sembunyikan baris biaya bernilai 0" checked={o.hide_zero_rows !== false} onChange={(v) => set("hide_zero_rows", v)} testId="opt-hide_zero_rows" />
        <Toggle label="Cetak terbilang" checked={o.show_terbilang !== false} onChange={(v) => set("show_terbilang", v)} testId="opt-show_terbilang" />
        <Toggle label="Catatan 'diterbitkan otomatis'" checked={o.show_generated_note !== false} onChange={(v) => set("show_generated_note", v)} testId="opt-show_generated_note" />
        <Toggle label="Catatan materai" checked={Boolean(o.show_materai)} onChange={(v) => set("show_materai", v)} testId="opt-show_materai" />
        <Field label="Teks materai"><Input value={o.materai_note || ""} onChange={(e) => set("materai_note", e.target.value)} data-testid="opt-materai_note" /></Field>
        <Field label="Tempat (kota) tanda tangan"><Input value={o.place || ""} onChange={(e) => set("place", e.target.value)} placeholder="mis. Bandung" data-testid="opt-place" /></Field>
        <div className="sm:col-span-2"><Field label="Catatan penutup"><Textarea rows={3} value={o.closing_note || ""} onChange={(e) => set("closing_note", e.target.value)} data-testid="opt-closing_note" /></Field></div>
      </div>
    </section>
  );
}

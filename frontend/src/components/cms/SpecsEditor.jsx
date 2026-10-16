import { Plus, Trash2 } from "lucide-react";
import { Input } from "@/components/ui/input";

// SpecsEditor — kelola spesifikasi unit [{key,label,value}] (tampil di halaman detail web).
const slug = (s) => String(s || "").toLowerCase().trim().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "spec";

export default function SpecsEditor({ value = [], onChange }) {
  const rows = Array.isArray(value) ? value : [];
  const update = (i, k, v) => onChange(rows.map((r, j) => (j === i ? { ...r, [k]: v, ...(k === "label" ? { key: slug(v) } : {}) } : r)));
  const remove = (i) => onChange(rows.filter((_, j) => j !== i));
  const add = () => onChange([...rows, { key: "", label: "", value: "" }]);

  return (
    <div className="space-y-2">
      {rows.map((r, i) => (
        <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-2" data-testid={`vf-spec-row-${i}`}>
          <Input value={r.label || ""} onChange={(e) => update(i, "label", e.target.value)} placeholder="Label (mis. Transmisi)" data-testid={`vf-spec-label-${i}`} />
          <Input value={r.value || ""} onChange={(e) => update(i, "value", e.target.value)} placeholder="Nilai (mis. Manual)" data-testid={`vf-spec-value-${i}`} />
          <button type="button" title="Hapus" onClick={() => remove(i)} data-testid={`vf-spec-remove-${i}`}
            className="rounded-md border border-border px-2 text-muted-foreground transition hover:text-[#FF3B30]"><Trash2 size={13} /></button>
        </div>
      ))}
      <button type="button" className="secondary-button" onClick={add} data-testid="vf-spec-add">
        <Plus size={13} /> Tambah Spesifikasi
      </button>
    </div>
  );
}

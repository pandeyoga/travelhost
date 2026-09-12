import { useEffect, useState } from "react";
import {
  ArrowUp, ArrowDown, ChevronDown, ChevronUp, Eye, EyeOff, GripVertical, Images, Plus, Trash2,
} from "lucide-react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import MediaPickerDialog from "@/components/media/MediaPickerDialog";
import { absUrl } from "@/components/media/mediaApi";
import { SECTION_META } from "@/lib/siteSections";

// Kartu section Page Builder: drag & drop (dnd-kit), pilih (sinkron dgn pratinjau),
// editor field per tipe (teks/textarea/daftar/gambar dari Media Library).

function ImageField({ value, onChange, testId }) {
  const [pickerOpen, setPickerOpen] = useState(false);
  return (
    <div className="space-y-1.5">
      <div className="flex gap-1.5">
        <Input className="!h-8 flex-1 text-[12px]" value={value || ""} placeholder="(kosong = gambar bawaan)"
          onChange={(e) => onChange(e.target.value)} data-testid={testId} />
        <button type="button" className="secondary-button !h-8 shrink-0 !px-2.5 !text-[11px]"
          onClick={() => setPickerOpen(true)} data-testid={`${testId}-pick`}>
          <Images size={12} /> Library
        </button>
      </div>
      {value ? (
        <img src={absUrl(value)} alt="Pratinjau gambar section" loading="lazy"
          className="h-16 w-28 rounded-lg border border-[#E9E9EE] object-cover" data-testid={`${testId}-thumb`} />
      ) : null}
      <MediaPickerDialog open={pickerOpen} onOpenChange={setPickerOpen} pickKind="image"
        title="Pilih gambar section" description="Klik satu gambar dari Media Library — bisa juga unggah baru."
        onPick={(a) => onChange((a && a.url) || "")} />
    </div>
  );
}

function FieldEditor({ spec, value, onChange, testId }) {
  if (spec.kind === "image") {
    return <ImageField value={value} onChange={onChange} testId={testId} />;
  }
  if (spec.kind === "textarea") {
    return <Textarea className="min-h-[64px] text-[12.5px]" value={value || ""} placeholder="(kosong = teks bawaan)"
      onChange={(e) => onChange(e.target.value)} data-testid={testId} />;
  }
  if (spec.kind === "lines") {
    return <Textarea className="min-h-[64px] text-[12.5px]" value={Array.isArray(value) ? value.join("\n") : ""}
      placeholder={"(kosong = bawaan)\nSatu item per baris"}
      onChange={(e) => onChange(e.target.value.split("\n").map((x) => x.trim()).filter(Boolean))} data-testid={testId} />;
  }
  return <Input className="!h-8 text-[12.5px]" value={value || ""} placeholder="(kosong = teks bawaan)"
    onChange={(e) => onChange(e.target.value)} data-testid={testId} />;
}

function ItemsEditor({ spec, value, onChange, testId }) {
  const rows = Array.isArray(value) ? value : [];
  const setRow = (i, k, v) => onChange(rows.map((r, idx) => (idx === i ? { ...r, [k]: v } : r)));
  return (
    <div className="space-y-2">
      {rows.length === 0 ? (
        <p className="text-[11.5px] text-[#8E8E93]">Kosong — daftar bawaan situs dipakai.</p>
      ) : rows.map((r, i) => (
        <div key={i} className="rounded-lg border border-[#E9E9EE] bg-[#FAFAFC] p-2.5">
          <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
            {spec.itemFields.map((f) => (
              <div key={f.key} className={f.kind === "textarea" ? "sm:col-span-2" : ""}>
                <label className="text-[10.5px] font-semibold uppercase tracking-wide text-[#8E8E93]">{f.label}</label>
                <FieldEditor spec={f} value={r[f.key]} onChange={(v) => setRow(i, f.key, v)} testId={`${testId}-${i}-${f.key}`} />
              </div>
            ))}
          </div>
          <button className="mt-1.5 inline-flex items-center gap-1 text-[11px] font-semibold text-[#A8221A]"
            onClick={() => onChange(rows.filter((_, idx) => idx !== i))} data-testid={`${testId}-del-${i}`}>
            <Trash2 size={11} /> Hapus item
          </button>
        </div>
      ))}
      <button className="secondary-button !h-7 !px-2.5 !text-[11px]"
        onClick={() => onChange([...rows, {}])} data-testid={`${testId}-add`}>
        <Plus size={11} /> Tambah item
      </button>
    </div>
  );
}

export default function PageBuilderSectionCard({
  sec, idx, total, selected, registerRef, onSelect, onMove, onToggle, onChangeData, onDelete,
}) {
  const [open, setOpen] = useState(false);
  useEffect(() => { if (selected) setOpen(true); }, [selected]);
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: sec.id });
  const meta = SECTION_META[sec.type] || { label: sec.type, desc: "", fields: [] };
  const setField = (key, v) => onChangeData({ ...(sec.data || {}), [key]: v });
  const border = selected
    ? "border-[#0A84FF] ring-1 ring-[#0A84FF]/35"
    : sec.enabled ? "border-[#E9E9EE]" : "border-dashed border-[#D8D8DE] opacity-70";
  return (
    <div ref={(el) => { setNodeRef(el); registerRef(el); }}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`rounded-xl border ${sec.enabled ? "bg-white" : "bg-[#FAFAFC]"} ${border} ${isDragging ? "relative z-10 shadow-lg" : ""}`}
      data-testid={`pb-section-${sec.id}`} data-enabled={sec.enabled ? "1" : "0"}>
      <div className="flex flex-wrap items-center gap-2 px-3 py-2.5">
        <button className="icon-button !h-7 !w-6 cursor-grab touch-none active:cursor-grabbing"
          {...attributes} {...listeners} data-testid={`pb-drag-${sec.id}`} aria-label="Seret utk mengubah urutan">
          <GripVertical size={13} />
        </button>
        <div className="flex flex-col gap-0.5">
          <button className="icon-button !h-5 !w-5" disabled={idx === 0} onClick={() => onMove(idx, -1)} data-testid={`pb-up-${sec.id}`}><ArrowUp size={11} /></button>
          <button className="icon-button !h-5 !w-5" disabled={idx === total - 1} onClick={() => onMove(idx, 1)} data-testid={`pb-down-${sec.id}`}><ArrowDown size={11} /></button>
        </div>
        <button type="button" className="min-w-[120px] flex-1 text-left" onClick={onSelect} data-testid={`pb-title-${sec.id}`}>
          <p className="text-[13px] font-bold text-[#1C1C1E]">{meta.label}</p>
          <p className="text-[11px] text-[#8E8E93]">{meta.desc}</p>
        </button>
        <button className="secondary-button !h-7 !px-2 !text-[11px]" onClick={() => onToggle(!sec.enabled)} data-testid={`pb-toggle-${sec.id}`}>
          {sec.enabled ? <><Eye size={11} /> Tampil</> : <><EyeOff size={11} /> Disembunyikan</>}
        </button>
        {meta.fields.length ? (
          <button className="secondary-button !h-7 !px-2 !text-[11px]" onClick={() => { setOpen((v) => !v); onSelect(); }} data-testid={`pb-edit-${sec.id}`}>
            {open ? <ChevronUp size={11} /> : <ChevronDown size={11} />} Edit isi
          </button>
        ) : null}
        <button className="icon-button !h-7 !w-7 text-[#A8221A]" onClick={onDelete} data-testid={`pb-delete-${sec.id}`}><Trash2 size={12} /></button>
      </div>
      {open ? (
        <div className="grid grid-cols-1 gap-2.5 border-t border-[#F0F0F3] px-3.5 py-3 sm:grid-cols-2">
          {meta.fields.map((f) => (
            <div key={f.key} className={f.kind !== "text" ? "sm:col-span-2" : ""}>
              <label className="text-[11px] font-semibold text-[#6B6B73]">{f.label}</label>
              {f.kind === "items"
                ? <ItemsEditor spec={f} value={(sec.data || {})[f.key]} onChange={(v) => setField(f.key, v)} testId={`pb-items-${sec.id}-${f.key}`} />
                : <FieldEditor spec={f} value={(sec.data || {})[f.key]} onChange={(v) => setField(f.key, v)} testId={`pb-field-${sec.id}-${f.key}`} />}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

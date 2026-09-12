import { useState } from "react";
import {
  DndContext, closestCenter, PointerSensor, KeyboardSensor, useSensor, useSensors,
} from "@dnd-kit/core";
import {
  SortableContext, arrayMove, rectSortingStrategy, sortableKeyboardCoordinates, useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Star, Trash2, Plus, ImageOff, Images } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import MediaPickerDialog from "@/components/media/MediaPickerDialog";

// GalleryManager — kelola array gambar (URL-based, tanpa storage).
// mode "urls"      => value: ["https://...", ...]
// mode "captioned" => value: [{url, caption}, ...]
// Fitur: tambah URL (tunggal/batch newline/koma), reorder dnd-kit, set cover (geser ke depan),
// edit caption (captioned), hapus. Komponen fully controlled via value/onChange.
function normalize(value) {
  return (Array.isArray(value) ? value : []).map((v) =>
    typeof v === "string" ? { url: v, caption: "" } : { url: v?.url || "", caption: v?.caption || "" }
  );
}

function SortableThumb({ id, item, index, mode, onCover, onRemove, onCaption }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 };
  return (
    <div ref={setNodeRef} style={style} data-testid={`gm-item-${index}`}
      className="group relative overflow-hidden rounded-xl border border-border bg-card">
      <div className="relative h-24 w-full bg-muted">
        {item.url ? (
          <img src={item.url} alt="" className="h-full w-full object-cover" loading="lazy"
            onError={(e) => { e.currentTarget.style.display = "none"; }} />
        ) : null}
        {index === 0 ? (
          <span className="absolute left-1.5 top-1.5 rounded-md bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">Cover</span>
        ) : null}
        <button type="button" {...attributes} {...listeners} title="Geser untuk urutkan"
          data-testid={`gm-drag-${index}`}
          className="absolute right-1.5 top-1.5 cursor-grab rounded-md bg-black/55 p-1 text-white opacity-0 transition group-hover:opacity-100">
          <GripVertical size={13} />
        </button>
      </div>
      <div className="flex items-center gap-1 p-1.5">
        {mode === "captioned" ? (
          <Input value={item.caption} onChange={(e) => onCaption(index, e.target.value)}
            placeholder="Keterangan" className="h-7 flex-1 text-[11.5px]" data-testid={`gm-caption-${index}`} />
        ) : <span className="flex-1 truncate px-1 text-[11px] text-muted-foreground">{item.url.split("/").pop()}</span>}
        {index !== 0 ? (
          <button type="button" title="Jadikan cover" onClick={() => onCover(index)} data-testid={`gm-cover-${index}`}
            className="rounded-md p-1 text-muted-foreground hover:text-foreground"><Star size={13} /></button>
        ) : null}
        <button type="button" title="Hapus" onClick={() => onRemove(index)} data-testid={`gm-remove-${index}`}
          className="rounded-md p-1 text-muted-foreground hover:text-[#FF3B30]"><Trash2 size={13} /></button>
      </div>
    </div>
  );
}

export default function GalleryManager({ value = [], onChange, mode = "captioned" }) {
  const items = normalize(value);
  const [draft, setDraft] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const emit = (arr) => onChange(mode === "urls" ? arr.map((x) => x.url) : arr.map((x) => ({ url: x.url, caption: x.caption || "" })));
  const addUrls = () => {
    const urls = draft.split(/\n|,/).map((s) => s.trim()).filter(Boolean);
    if (!urls.length) return;
    emit([...items, ...urls.map((u) => ({ url: u, caption: "" }))]);
    setDraft("");
  };
  const onDragEnd = ({ active, over }) => {
    if (!over || active.id === over.id) return;
    const from = Number(String(active.id).split("-").pop());
    const to = Number(String(over.id).split("-").pop());
    if (Number.isNaN(from) || Number.isNaN(to)) return;
    emit(arrayMove(items, from, to));
  };
  const ids = items.map((_, i) => `gm-${i}`);

  return (
    <div className="space-y-2" data-testid="gallery-manager">
      {items.length === 0 ? (
        <div className="flex flex-col items-center gap-1 rounded-xl border border-dashed border-border py-6 text-muted-foreground" data-testid="gm-empty">
          <ImageOff size={20} /><span className="text-[12px]">Belum ada gambar. Tempel URL di bawah.</span>
        </div>
      ) : (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <SortableContext items={ids} strategy={rectSortingStrategy}>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3" data-testid="gm-grid">
              {items.map((it, i) => (
                <SortableThumb key={ids[i]} id={ids[i]} item={it} index={i} mode={mode}
                  onCover={(idx) => { const a = [...items]; const [m] = a.splice(idx, 1); emit([m, ...a]); }}
                  onRemove={(idx) => emit(items.filter((_, x) => x !== idx))}
                  onCaption={(idx, c) => emit(items.map((x, n) => (n === idx ? { ...x, caption: c } : x)))} />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}
      <div className="flex items-start gap-2">
        <Textarea rows={2} value={draft} onChange={(e) => setDraft(e.target.value)}
          placeholder="Tempel 1+ URL gambar (pisah baris/koma)" className="flex-1 text-[12px]" data-testid="gm-input" />
        <div className="flex shrink-0 flex-col gap-1.5">
          <button type="button" onClick={addUrls} data-testid="gm-add"
            className="primary-button"><Plus size={14} /> Tambah</button>
          <button type="button" onClick={() => setPickerOpen(true)} data-testid="gm-library"
            className="secondary-button"><Images size={14} /> Dari Library</button>
        </div>
      </div>
      <MediaPickerDialog open={pickerOpen} onOpenChange={setPickerOpen} pickKind="image" multiple
        title="Pilih foto galeri"
        description="Centang beberapa foto sekaligus — jauh lebih cepat daripada menempel URL satu per satu."
        onPick={(assets) => {
          // Galeri ini dulunya HANYA menerima tempelan URL manual, jadi foto di komputer pengguna
          // praktis tidak bisa dipakai tanpa mengunggahnya lewat halaman lain lebih dulu.
          const picked = Array.isArray(assets) ? assets : [assets];
          const existing = new Set(items.map((x) => x.url));
          const added = picked
            .filter((a) => a?.url && !existing.has(a.url))
            .map((a) => ({ url: a.url, caption: a.alt || "" }));
          if (added.length) emit([...items, ...added]);
        }} />
    </div>
  );
}

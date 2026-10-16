import { Suspense, lazy, useState } from "react";
import { Plus, Trash2, Link2, Eye, X, Compass, Loader2, Images } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import MediaPickerDialog from "@/components/media/MediaPickerDialog";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

const PhotoSphereTour = lazy(() => import("@/components/public/PhotoSphereTour"));

// TourSceneBuilder — bangun tur 360 multi-scene (URL panorama, tanpa storage).
// value: [{id,label,panorama,thumbnail,links:[{nodeId,yaw,pitch}]}]
// Fully controlled via value/onChange. Hotspot link = arah (yaw/pitch) menuju scene lain.
function slug(s, fallback) {
  const base = String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  return base || fallback;
}

export default function TourSceneBuilder({ value = [], onChange }) {
  const scenes = Array.isArray(value) ? value : [];
  const [preview, setPreview] = useState(false);
  // { index, field } — mana scene & field mana yang sedang memilih gambar dari Media Library.
  const [picker, setPicker] = useState(null);

  const update = (i, patch) => onChange(scenes.map((s, n) => (n === i ? { ...s, ...patch } : s)));
  const addScene = () => {
    const id = `scene-${Date.now().toString(36)}`;
    onChange([...scenes, { id, label: `Scene ${scenes.length + 1}`, panorama: "", thumbnail: "", links: [] }]);
  };
  const removeScene = (i) => {
    const removedId = scenes[i]?.id;
    onChange(scenes
      .filter((_, n) => n !== i)
      .map((s) => ({ ...s, links: (s.links || []).filter((l) => l.nodeId !== removedId) })));
  };
  const addLink = (i) => {
    const others = scenes.filter((_, n) => n !== i);
    const target = others[0]?.id || "";
    update(i, { links: [...(scenes[i].links || []), { nodeId: target, yaw: 0, pitch: 0 }] });
  };
  const updateLink = (i, li, patch) => update(i, {
    links: (scenes[i].links || []).map((l, n) => (n === li ? { ...l, ...patch } : l)),
  });
  const removeLink = (i, li) => update(i, { links: (scenes[i].links || []).filter((_, n) => n !== li) });

  const canPreview = scenes.length > 0 && scenes.every((s) => s.panorama);

  return (
    <div className="space-y-3" data-testid="tour-builder">
      <div className="flex items-center justify-between">
        <p className="text-[12px] text-muted-foreground">{scenes.length} scene · panorama equirectangular (URL)</p>
        <div className="flex gap-2">
          <button type="button" onClick={() => setPreview(true)} disabled={!canPreview} data-testid="tour-preview-open"
            className="secondary-button disabled:opacity-40"><Eye size={14} /> Pratinjau 360</button>
          <button type="button" onClick={addScene} data-testid="tour-add-scene" className="primary-button"><Plus size={14} /> Scene</button>
        </div>
      </div>

      {scenes.length === 0 ? (
        <div className="flex flex-col items-center gap-1 rounded-xl border border-dashed border-border py-6 text-muted-foreground" data-testid="tour-empty">
          <Compass size={20} /><span className="text-[12px]">Belum ada scene 360. Tambahkan scene + URL panorama.</span>
        </div>
      ) : (
        <div className="space-y-3">
          {scenes.map((s, i) => (
            <div key={s.id || i} className="rounded-xl border border-border bg-card p-3" data-testid={`tour-scene-${i}`}>
              <div className="flex items-center gap-2">
                <span className="h-10 w-14 shrink-0 rounded-md bg-muted bg-cover bg-center"
                  style={(s.thumbnail || s.panorama) ? { backgroundImage: `url('${s.thumbnail || s.panorama}')` } : undefined} />
                <Input value={s.label} onChange={(e) => update(i, { label: e.target.value, id: s.id || slug(e.target.value, `scene-${i}`) })}
                  placeholder="Nama scene (mis. Kabin Depan)" className="h-8 flex-1 text-[12.5px]" data-testid={`tour-label-${i}`} />
                <button type="button" onClick={() => removeScene(i)} data-testid={`tour-remove-${i}`}
                  className="rounded-md p-1.5 text-muted-foreground hover:text-[#FF3B30]"><Trash2 size={14} /></button>
              </div>
              <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                <div className="flex gap-1.5">
                  <Input value={s.panorama} onChange={(e) => update(i, { panorama: e.target.value })}
                    placeholder="URL panorama 360°" className="h-8 flex-1 text-[12px]" data-testid={`tour-pano-${i}`} />
                  <button type="button" className="secondary-button !h-8 !px-2 shrink-0"
                    onClick={() => setPicker({ index: i, field: "panorama" })}
                    aria-label="Pilih panorama dari Media Library" data-testid={`tour-pano-library-${i}`}>
                    <Images size={13} />
                  </button>
                </div>
                <div className="flex gap-1.5">
                  <Input value={s.thumbnail} onChange={(e) => update(i, { thumbnail: e.target.value })}
                    placeholder="URL thumbnail (opsional)" className="h-8 flex-1 text-[12px]" data-testid={`tour-thumb-${i}`} />
                  <button type="button" className="secondary-button !h-8 !px-2 shrink-0"
                    onClick={() => setPicker({ index: i, field: "thumbnail" })}
                    aria-label="Pilih thumbnail dari Media Library" data-testid={`tour-thumb-library-${i}`}>
                    <Images size={13} />
                  </button>
                </div>
              </div>
              {/* Hotspot links */}
              <div className="mt-2 space-y-1.5">
                <Label className="text-[11px] text-muted-foreground">Titik pindah (hotspot) ke scene lain</Label>
                {(s.links || []).map((l, li) => (
                  <div key={li} className="flex flex-wrap items-center gap-1.5" data-testid={`tour-link-${i}-${li}`}>
                    <Link2 size={13} className="text-muted-foreground" />
                    <Select value={l.nodeId || ""} onValueChange={(v) => updateLink(i, li, { nodeId: v })}>
                      <SelectTrigger className="h-7 w-40 text-[11.5px]" data-testid={`tour-link-target-${i}-${li}`}><SelectValue placeholder="Scene tujuan" /></SelectTrigger>
                      <SelectContent>
                        {scenes.filter((_, n) => n !== i).map((o) => <SelectItem key={o.id} value={o.id}>{o.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <Input type="number" value={l.yaw} onChange={(e) => updateLink(i, li, { yaw: Number(e.target.value) || 0 })}
                      placeholder="yaw°" className="h-7 w-20 text-[11.5px]" data-testid={`tour-link-yaw-${i}-${li}`} />
                    <Input type="number" value={l.pitch} onChange={(e) => updateLink(i, li, { pitch: Number(e.target.value) || 0 })}
                      placeholder="pitch°" className="h-7 w-20 text-[11.5px]" data-testid={`tour-link-pitch-${i}-${li}`} />
                    <button type="button" onClick={() => removeLink(i, li)} className="rounded p-1 text-muted-foreground hover:text-[#FF3B30]"><X size={13} /></button>
                  </div>
                ))}
                {scenes.length > 1 ? (
                  <button type="button" onClick={() => addLink(i)} data-testid={`tour-add-link-${i}`}
                    className="text-[11.5px] font-semibold text-primary hover:underline">+ Tambah hotspot</button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}

      <MediaPickerDialog open={Boolean(picker)} onOpenChange={(v) => !v && setPicker(null)}
        pickKind="image" title="Pilih gambar dari Media Library"
        description="Panorama 360° memakai foto equirectangular (rasio 2:1). Thumbnail boleh foto biasa."
        onPick={(asset) => {
          if (!picker || !asset?.url) return;
          update(picker.index, { [picker.field]: asset.url });
          setPicker(null);
        }} />

      <Dialog open={preview} onOpenChange={setPreview}>        <DialogContent className="max-w-3xl" data-testid="tour-preview-dialog">
          <DialogHeader><DialogTitle>Pratinjau Tur 360°</DialogTitle></DialogHeader>
          {preview && canPreview ? (
            <Suspense fallback={<div className="flex items-center justify-center py-10 text-muted-foreground"><Loader2 className="mr-2 animate-spin" size={18} /> Memuat 360°…</div>}>
              <PhotoSphereTour scenes={scenes} />
            </Suspense>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

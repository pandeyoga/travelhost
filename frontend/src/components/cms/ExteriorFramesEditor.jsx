import { useState } from "react";
import { Wand2 } from "lucide-react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import GalleryManager from "@/components/cms/GalleryManager";

// ExteriorFramesEditor — kelola frame 360° eksterior (jumlah frame BEBAS: 8, 16, 36, dst).
// Cara isi: manual via GalleryManager, atau generator pola URL ({i} = nomor frame).
export default function ExteriorFramesEditor({ value = [], onChange }) {
  const [pattern, setPattern] = useState("");
  const [count, setCount] = useState(16);
  const [start, setStart] = useState(1);

  const generate = () => {
    if (!pattern.includes("{i}")) { toast.error("Pola URL harus memuat {i} sebagai nomor frame"); return; }
    const n = Math.min(120, Math.max(2, Number(count) || 0));
    const s = Number(start) || 1;
    onChange(Array.from({ length: n }, (_, k) => pattern.replaceAll("{i}", String(s + k))));
    toast.success(`${n} frame dibuat dari pola`);
  };

  return (
    <div className="space-y-2">
      <div className="rounded-xl border border-dashed border-border p-2.5">
        <p className="text-[11.5px] text-muted-foreground">
          Foto unit dari beberapa sudut, urut searah putaran. Jumlah frame <b>bebas</b> (mis. 8/16/36 —
          makin banyak makin halus). Isi manual di bawah, atau buat otomatis dari pola URL:
          tulis <code className="rounded bg-muted px-1">{"{i}"}</code> sebagai nomor frame.
        </p>
        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-[1fr_84px_84px_auto]">
          <Input value={pattern} onChange={(e) => setPattern(e.target.value)}
            placeholder="https://contoh.com/unit/frame-{i}.jpg" data-testid="vf-ext360-pattern" />
          <Input type="number" value={count} onChange={(e) => setCount(e.target.value)}
            placeholder="Jumlah" title="Jumlah frame" data-testid="vf-ext360-count" />
          <Input type="number" value={start} onChange={(e) => setStart(e.target.value)}
            placeholder="Mulai" title="Nomor awal" data-testid="vf-ext360-start" />
          <button type="button" className="secondary-button whitespace-nowrap" onClick={generate} data-testid="vf-ext360-generate">
            <Wand2 size={13} /> Buat Daftar
          </button>
        </div>
      </div>
      <GalleryManager value={value} onChange={onChange} mode="urls" />
      <p className="text-[11.5px] text-muted-foreground" data-testid="vf-ext360-count-info">
        {value.length ? `${value.length} frame terpasang — frame #1 = tampak depan yang tampil pertama.` : "Belum ada frame — bagian Eksterior 360° tidak akan tampil di web."}
      </p>
    </div>
  );
}

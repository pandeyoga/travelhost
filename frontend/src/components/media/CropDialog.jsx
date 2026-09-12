import { useCallback, useEffect, useState } from "react";
import Cropper from "react-easy-crop";
import "react-easy-crop/react-easy-crop.css";
import { Crop as CropIcon, Loader2, ZoomIn } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { absUrl, cropAsset, errMsg } from "@/components/media/mediaApi";

/**
 * CropDialog — potong & ubah ukuran foto DI BROWSER, tetapi piksel dipotong di SERVER.
 *
 * Pembagian kerja ini dipilih dengan sadar: kotak potong hanya 4 angka (murah dikirim, mudah
 * divalidasi server), sementara memotong lewat <canvas> di browser menurunkan kualitas, kehilangan
 * profil warna, dan gagal pada foto besar di ponsel kelas menengah. Jadi pengguna tetap mendapat
 * pengalaman "potong sambil melihat", hasilnya tetap sekualitas aslinya.
 *
 * Preset rasio memakai ukuran yang benar-benar dipakai iklan & website (1:1 feed, 4:5 potret,
 * 16:9 hero, 1.91:1 kartu tautan) supaya foto tidak terpotong aneh setelah tayang.
 */
const RATIOS = [
  ["asli", "Asli", 0],
  ["1-1", "1:1 · Feed", 1],
  ["4-5", "4:5 · Potret", 4 / 5],
  ["3-2", "3:2 · Foto", 3 / 2],
  ["16-9", "16:9 · Hero", 16 / 9],
  ["191-1", "1.91:1 · Kartu tautan", 1.91],
];

export default function CropDialog({ open, onOpenChange, asset, onDone }) {
  const natural = asset?.width && asset?.height ? asset.width / asset.height : 1;
  const [ratioKey, setRatioKey] = useState("asli");
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [areaPixels, setAreaPixels] = useState(null);
  const [targetWidth, setTargetWidth] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    if (!open) return;
    setRatioKey("asli");
    setCrop({ x: 0, y: 0 });
    setZoom(1);
    setAreaPixels(null);
    setTargetWidth("");
  }, [open, asset?.id]);

  const onCropComplete = useCallback((_area, pixels) => setAreaPixels(pixels), []);
  const aspect = (RATIOS.find(([k]) => k === ratioKey) || [])[2] || natural;

  const submit = async (mode) => {
    if (!areaPixels) {
      toast.message("Geser dulu kotak potongnya");
      return;
    }
    setBusy(mode);
    try {
      const payload = {
        x: Math.max(0, Math.round(areaPixels.x)),
        y: Math.max(0, Math.round(areaPixels.y)),
        width: Math.round(areaPixels.width),
        height: Math.round(areaPixels.height),
        mode,
      };
      const tw = Number(targetWidth);
      if (tw > 0) payload.target_width = Math.round(tw);
      const doc = await cropAsset(asset.id, payload);
      toast.success(mode === "replace"
        ? `Aset diganti dengan hasil potong (versi ${doc.version})`
        : `Aset baru dibuat: ${doc.original_filename}`);
      onDone && onDone(doc, mode);
    } catch (e) {
      toast.error(errMsg(e, "Gagal memotong foto"));
    } finally {
      setBusy("");
    }
  };

  const previewSize = areaPixels
    ? `${Math.round(areaPixels.width)}×${Math.round(areaPixels.height)} px`
    : "—";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[720px]" data-testid="media-crop-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-[15px]">
            <CropIcon size={16} /> Potong &amp; ubah ukuran foto
          </DialogTitle>
          <DialogDescription className="text-[12px]">
            Geser dan cubit untuk mengatur bagian yang dipakai. Hasil potong dibuat di server
            sehingga kualitas foto tidak turun.
          </DialogDescription>
        </DialogHeader>

        <div className="relative h-[300px] overflow-hidden rounded-xl bg-[#0E1726]"
          data-testid="media-crop-canvas">
          {asset ? (
            <Cropper image={absUrl(asset.url)} crop={crop} zoom={zoom} aspect={aspect}
              onCropChange={setCrop} onZoomChange={setZoom} onCropComplete={onCropComplete}
              restrictPosition objectFit="contain" />
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {RATIOS.map(([key, label]) => (
            <button key={key} type="button" onClick={() => setRatioKey(key)}
              data-testid={`media-crop-ratio-${key}`}
              className={`rounded-lg border px-2.5 py-1.5 text-[11.5px] font-semibold transition-colors ${
                ratioKey === key ? "border-[#007AFF] bg-[#E8F1FF] text-[#0B57D0]"
                  : "border-[#E5E5EA] bg-white text-[#3a3f4a] hover:bg-[#F7F8FA]"}`}>
              {label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <label className="flex-1">
            <span className="flex items-center gap-1 text-[11px] font-semibold text-[#3a3f4a]">
              <ZoomIn size={11} /> Perbesar
            </span>
            <input type="range" min={1} max={4} step={0.05} value={zoom}
              onChange={(e) => setZoom(Number(e.target.value))}
              className="mt-1 h-1.5 w-full cursor-pointer appearance-none rounded-full bg-[#E5E5EA] accent-[#007AFF]"
              data-testid="media-crop-zoom" aria-label="Perbesar foto" />
          </label>
          <label className="w-[190px]">
            <span className="text-[11px] font-semibold text-[#3a3f4a]">Lebar akhir (px, opsional)</span>
            <Input type="number" min={1} value={targetWidth} placeholder="mis. 1200"
              onChange={(e) => setTargetWidth(e.target.value)} className="mt-1 h-8 text-[12px]"
              data-testid="media-crop-target-width" />
          </label>
          <p className="pb-1.5 text-[11.5px] tabular-nums text-[#6B6B73]" data-testid="media-crop-size">
            Hasil: <span className="font-semibold text-[#1C1C1E]">{previewSize}</span>
          </p>
        </div>

        <DialogFooter className="mt-1 gap-2">
          <button type="button" className="secondary-button" onClick={() => onOpenChange(false)}
            data-testid="media-crop-cancel">Batal</button>
          <button type="button" className="secondary-button" disabled={Boolean(busy) || !areaPixels}
            onClick={() => submit("replace")} data-testid="media-crop-replace">
            {busy === "replace" ? <Loader2 size={13} className="animate-spin" /> : null} Ganti aset asli
          </button>
          <button type="button" className="primary-button" disabled={Boolean(busy) || !areaPixels}
            onClick={() => submit("new")} data-testid="media-crop-save-new">
            {busy === "new" ? <Loader2 size={13} className="animate-spin" /> : <CropIcon size={13} />}
            Simpan sebagai aset baru
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

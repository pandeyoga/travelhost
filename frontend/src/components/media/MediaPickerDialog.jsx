import { Images, X } from "lucide-react";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import MediaBrowser from "@/components/media/MediaBrowser";

/**
 * MediaPickerDialog — SATU pemilih media untuk seluruh aplikasi.
 *
 * Dipakai oleh: editor halaman iklan (blok hero/galeri/video), form CMS website (gambar hero, sampul
 * artikel, avatar testimoni, OG image), galeri destinasi (pilih BANYAK sekaligus), dan tur 360°.
 * Sebelum ronde ini setiap tempat punya cara sendiri — termasuk satu tempat yang hanya menerima
 * tempelan URL manual, sehingga foto dari komputer pengguna praktis tidak bisa dipakai di galeri.
 *
 * `multiple` mengubah kontrak `onPick`: mode tunggal mengirim SATU aset, mode banyak mengirim ARRAY.
 * Pemanggil wajib sadar bentuknya — karena itu tombol aksinya pun berbeda dan diberi testid berbeda.
 */
export default function MediaPickerDialog({
  open, onOpenChange, onPick, pickKind = "", multiple = false, title, description,
}) {
  const handlePick = (payload) => {
    onPick && onPick(payload);
    onOpenChange(false);
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[1080px] p-0" data-testid="media-picker-dialog">
        <DialogHeader className="border-b border-[#EFF0F2] px-5 py-3">
          <DialogTitle className="flex items-center gap-2 text-[15px]">
            <Images size={16} /> {title || (multiple ? "Pilih beberapa media" : "Pilih media")}
          </DialogTitle>
          <DialogDescription className="text-[12px]">
            {description || (multiple
              ? "Centang beberapa aset lalu tekan “Pakai media”. Bisa juga unggah baru — aset masuk ke folder yang sedang dibuka."
              : "Klik satu aset untuk melihat detailnya, lalu tekan “Pakai media ini”.")}
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-[74vh] overflow-y-auto px-4 py-3">
          <MediaBrowser mode="picker" pickKind={pickKind} multiple={multiple} onPick={handlePick}
            showImport={false} />
        </div>
        <div className="flex items-center justify-end border-t border-[#EFF0F2] px-5 py-2.5">
          <button type="button" className="secondary-button !h-8" onClick={() => onOpenChange(false)}
            data-testid="media-picker-close"><X size={12} /> Tutup</button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

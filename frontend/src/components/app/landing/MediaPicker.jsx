import { useState } from "react";
import { Image as ImageIcon, Film, Trash2, Images } from "lucide-react";
import MediaLibrary from "@/components/app/landing/MediaLibrary";

/**
 * MediaPicker.jsx — kolom "pilih media" untuk panel setelan blok.
 *
 * Menampilkan PRATINJAU media yang sedang dipakai (bukan sekadar id) plus tombol ganti/hapus,
 * karena kesalahan paling sering di editor lama adalah tidak tahu media apa yang sedang terpasang.
 */
const BACKEND = process.env.REACT_APP_BACKEND_URL || "";
const absUrl = (u) => (u && u.startsWith("/") ? `${BACKEND}${u}` : u || "");

export default function MediaPicker({ label = "Foto / video", value, onChange, kind = "", testId = "mp" }) {
  const [open, setOpen] = useState(false);
  const media = value || {};
  const hasMedia = !!(media.src || media.media_id);

  const pick = (asset) => {
    onChange({
      ...media,
      media_id: asset.id,
      src: asset.url,
      thumb_url: asset.thumb_url || asset.url,
      kind: asset.kind,
      alt: media.alt || asset.alt || "",
    });
  };

  return (
    <div className="space-y-1.5 rounded-lg bg-[#F7F8FA] p-2.5">
      <p className="text-[11.5px] font-semibold text-[#3a3f4a]">{label}</p>
      {hasMedia ? (
        <div className="flex items-center gap-2 rounded-lg border border-[#E5E5EA] bg-white p-1.5"
          data-testid={`${testId}-current`}>
          <div className="flex h-12 w-16 shrink-0 items-center justify-center overflow-hidden rounded bg-[#EEF1F5]">
            {media.kind === "video" ? <Film size={16} className="text-[#6B6B73]" /> : (
              <img src={absUrl(media.thumb_url || media.src)} alt={media.alt || ""}
                className="h-full w-full object-cover" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[11.5px] font-semibold text-[#1C1C1E]">
              {media.kind === "video" ? "Video terpasang" : "Foto terpasang"}
            </p>
            <p className="truncate text-[10.5px] text-[#8E8E93]">{media.alt || media.media_id || media.src}</p>
          </div>
          <button type="button" className="icon-button !h-7 !w-7" data-testid={`${testId}-remove`}
            aria-label="Lepas media"
            onClick={() => onChange({ ...media, media_id: "", src: "", thumb_url: "" })}>
            <Trash2 size={12} />
          </button>
        </div>
      ) : (
        <p className="rounded-lg border border-dashed border-[#D9DEE6] bg-white px-2.5 py-3 text-center text-[11.5px] text-[#8E8E93]"
          data-testid={`${testId}-empty`}>
          Belum ada media pada blok ini
        </p>
      )}
      <button type="button" className="secondary-button !h-8 w-full" onClick={() => setOpen(true)}
        data-testid={`${testId}-open`}>
        <Images size={13} /> {hasMedia ? "Ganti dari Media Library" : "Pilih dari Media Library"}
      </button>
      <div className="space-y-1">
        <label className="text-[11px] font-semibold text-[#3a3f4a]" htmlFor={`${testId}-alt`}>
          Teks alternatif gambar
        </label>
        <input id={`${testId}-alt`} value={media.alt || ""} data-testid={`${testId}-alt`}
          onChange={(e) => onChange({ ...media, alt: e.target.value })}
          placeholder="Deskripsi singkat gambar"
          className="h-8 w-full rounded-lg border border-[#E5E5EA] bg-white px-2.5 text-[12px] outline-none focus:border-[#007AFF]" />
      </div>
      {media.kind === "video" || kind === "video" ? (
        <div className="space-y-1">
          <label className="text-[11px] font-semibold text-[#3a3f4a]" htmlFor={`${testId}-poster`}>
            URL gambar poster (wajib agar halaman tetap cepat)
          </label>
          <input id={`${testId}-poster`} value={media.poster || ""} data-testid={`${testId}-poster`}
            onChange={(e) => onChange({ ...media, poster: e.target.value })}
            placeholder="https://… atau /api/public/media/…"
            className="h-8 w-full rounded-lg border border-[#E5E5EA] bg-white px-2.5 text-[12px] outline-none focus:border-[#007AFF]" />
          <label className="text-[11px] font-semibold text-[#3a3f4a]" htmlFor={`${testId}-embed`}>
            Atau tautan embed (YouTube/Vimeo) untuk video panjang
          </label>
          <input id={`${testId}-embed`} value={media.embed_url || ""} data-testid={`${testId}-embed`}
            onChange={(e) => onChange({ ...media, embed_url: e.target.value })}
            placeholder="https://www.youtube.com/embed/…"
            className="h-8 w-full rounded-lg border border-[#E5E5EA] bg-white px-2.5 text-[12px] outline-none focus:border-[#007AFF]" />
        </div>
      ) : null}
      <MediaLibrary open={open} onOpenChange={setOpen} onPick={pick} pickKind={kind} />
      <p className="flex items-center gap-1 text-[10.5px] text-[#8E8E93]">
        <ImageIcon size={11} /> Media disimpan di server dan dimuat halaman publik lewat URL publik.
      </p>
    </div>
  );
}

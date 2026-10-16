import { Check, Film, FileWarning, Images } from "lucide-react";
import { EmptyState } from "@/components/shared/DataStates";
import { absUrl, bytesLabel } from "@/components/media/mediaApi";

/**
 * MediaGrid — kisi thumbnail dengan PILIH BANYAK.
 *
 * Dua interaksi dipisahkan dengan sengaja supaya tidak saling menyabotase:
 *  - klik kartu  = jadikan aset AKTIF (panel detail di kanan) — aksi yang paling sering dipakai;
 *  - klik kotak centang = tambah/buang dari pilihan massal.
 * Kalau keduanya digabung (klik = pilih), pengguna tidak bisa melihat detail satu aset tanpa
 * mengubah pilihan massalnya, dan aksi "hapus terpilih" jadi berbahaya.
 */
export function MediaGrid({
  assets = [], loading = false, activeId = "", selected = [], onActivate, onToggleSelect,
  missingIds = [], emptyTitle = "Belum ada media", emptyDescription = "", emptyAction = null,
  columnsClass = "",
}) {
  if (loading) {
    return (
      <div className={`grid gap-2.5 ${columnsClass || "grid-cols-2 sm:grid-cols-3 lg:grid-cols-4"}`}
        data-testid="media-grid-loading">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-[150px] animate-pulse rounded-xl bg-[#EEF1F5]" />
        ))}
      </div>
    );
  }
  if (!assets.length) {
    return <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction}
      testId="media-grid-empty" />;
  }
  const selectedSet = new Set(selected);
  const missingSet = new Set(missingIds);
  return (
    <div className={`grid gap-2.5 ${columnsClass || "grid-cols-2 sm:grid-cols-3 lg:grid-cols-4"}`}
      data-testid="media-grid">
      {assets.map((a) => {
        const picked = selectedSet.has(a.id);
        const active = a.id === activeId;
        return (
          <div key={a.id}
            className={`group relative overflow-hidden rounded-xl border-2 bg-white transition-colors ${
              active ? "border-[#007AFF]" : picked ? "border-[#0B57D0]" : "border-[#EDEEF1] hover:border-[#C7D6E8]"}`}
            data-testid={`media-item-${a.id}`}>
            <button type="button" onClick={() => onActivate && onActivate(a)}
              className="block w-full text-left" data-testid={`media-item-open-${a.id}`}
              aria-label={`Lihat detail ${a.original_filename}`}>
              <span className="flex h-[104px] items-center justify-center overflow-hidden bg-[#EEF1F5]">
                {a.kind === "image" ? (
                  <img src={absUrl(a.thumb_url || a.url)} alt={a.alt || a.original_filename}
                    loading="lazy" className="h-full w-full object-cover" />
                ) : (
                  <span className="flex flex-col items-center gap-1 text-[#6B6B73]">
                    <Film size={20} /><span className="text-[10px] font-bold">VIDEO</span>
                  </span>
                )}
              </span>
              <span className="block p-2">
                <span className="block truncate text-[11.5px] font-semibold text-[#1C1C1E]">
                  {a.original_filename}
                </span>
                <span className="mt-0.5 flex items-center gap-1 text-[10px] tabular-nums text-[#8E8E93]">
                  {bytesLabel(a.size)}
                  {a.width ? ` · ${a.width}×${a.height}` : ""}
                  {a.version > 1 ? (
                    <span className="rounded bg-[#F2F2F5] px-1 font-semibold text-[#6B6B73]">v{a.version}</span>
                  ) : null}
                </span>
              </span>
            </button>
            {onToggleSelect ? (
              <button type="button" onClick={() => onToggleSelect(a.id)}
                aria-label={picked ? `Buang ${a.original_filename} dari pilihan` : `Pilih ${a.original_filename}`}
                data-testid={`media-select-${a.id}`}
                className={`absolute left-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-md border transition-colors ${
                  picked ? "border-[#0B57D0] bg-[#0B57D0] text-white"
                    : "border-white/70 bg-white/85 text-transparent hover:text-[#8E8E93]"}`}>
                <Check size={13} />
              </button>
            ) : null}
            {a.source === "cms" ? (
              <span className="absolute right-1.5 top-1.5 rounded bg-white/90 px-1.5 py-0.5 text-[9.5px] font-bold text-[#6B6B73]">
                CMS
              </span>
            ) : null}
            {missingSet.has(a.id) ? (
              <span className="absolute bottom-9 right-1.5 flex items-center gap-1 rounded bg-[#FFF1F0] px-1.5 py-0.5 text-[9.5px] font-bold text-[#A8221A]">
                <FileWarning size={10} /> berkas hilang
              </span>
            ) : null}
          </div>
        );
      })}
      <span className="hidden"><Images size={1} /></span>
    </div>
  );
}

export default MediaGrid;

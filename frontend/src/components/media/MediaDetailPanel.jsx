import { useEffect, useRef, useState } from "react";
import {
  Copy, Crop, Download, FileWarning, HardDrive, Loader2, Replace, Save, Trash2, Check,
  ExternalLink, LayoutTemplate, FileText,
} from "lucide-react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import SelectField from "@/components/shared/SelectField";
import CropDialog from "@/components/media/CropDialog";
import {
  ROOT_FOLDER, absUrl, acceptFor, bytesLabel, deleteAsset, downloadAsset, errMsg, fetchUsage, folderOptions,
  patchAsset, replaceFile,
} from "@/components/media/mediaApi";
import { formatDateTime } from "@/utils/formatters";

/**
 * MediaDetailPanel — panel kanan: penampil besar + seluruh aksi pada SATU aset.
 *
 * Keputusan UX yang penting: daftar "dipakai di mana" dimuat OTOMATIS begitu aset dipilih, bukan
 * setelah pengguna menekan Hapus. Peringatan yang datang di dialog konfirmasi sering dibaca sebagai
 * formalitas; ditampilkan lebih awal, informasi itu justru mencegah niat menghapus foto yang masih
 * tayang di website atau di halaman iklan yang sedang dibayar.
 */
export default function MediaDetailPanel({
  asset, folders = [], onChanged, onDeleted, onPick, pickLabel = "Pakai media ini", compact = false,
}) {
  const replaceRef = useRef(null);
  const [alt, setAlt] = useState("");
  const [name, setName] = useState("");
  const [savingAlt, setSavingAlt] = useState(false);
  const [savingName, setSavingName] = useState(false);
  const [usage, setUsage] = useState(null);
  const [usageLoading, setUsageLoading] = useState(false);
  const [replacing, setReplacing] = useState(false);
  const [cropOpen, setCropOpen] = useState(false);
  const [confirmDel, setConfirmDel] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    setAlt(asset?.alt || "");
    setName(asset?.original_filename || "");
    setUsage(null);
    if (!asset?.id) return undefined;
    let alive = true;
    setUsageLoading(true);
    fetchUsage(asset.id)
      .then((d) => alive && setUsage(d))
      .catch(() => alive && setUsage({ landing_pages: [], content: [], total: 0, failed: true }))
      .finally(() => alive && setUsageLoading(false));
    return () => { alive = false; };
  }, [asset?.id]);

  if (!asset) {
    return (
      <div className="flex h-full min-h-[260px] flex-col items-center justify-center px-4 text-center"
        data-testid="media-detail-empty">
        <HardDrive size={22} className="text-[#B9BFC9]" />
        <p className="mt-2 text-[12.5px] font-semibold text-[#1C1C1E]">Belum ada aset dipilih</p>
        <p className="mt-1 text-[11.5px] text-[#8E8E93]">
          Klik salah satu media untuk melihat detail, mengunduh, memotong, atau menggantinya.
        </p>
      </div>
    );
  }

  const saveAlt = async () => {
    setSavingAlt(true);
    try {
      const doc = await patchAsset(asset.id, { alt });
      toast.success("Teks alternatif disimpan");
      onChanged && onChanged(doc);
    } catch (e) {
      toast.error(errMsg(e, "Gagal menyimpan teks alternatif"));
    } finally {
      setSavingAlt(false);
    }
  };

  const saveName = async () => {
    if (!name.trim()) { toast.message("Nama berkas tidak boleh kosong"); return; }
    setSavingName(true);
    try {
      const doc = await patchAsset(asset.id, { original_filename: name.trim() });
      toast.success("Nama berkas diperbarui");
      onChanged && onChanged(doc);
    } catch (e) {
      toast.error(errMsg(e, "Gagal mengganti nama berkas"));
    } finally {
      setSavingName(false);
    }
  };

  const moveFolder = async (folderId) => {
    try {
      const doc = await patchAsset(asset.id, { folder_id: folderId });
      toast.success("Aset dipindahkan");
      onChanged && onChanged(doc);
    } catch (e) {
      toast.error(errMsg(e, "Gagal memindahkan aset"));
    }
  };

  const copyUrl = async () => {
    const url = absUrl(asset.url);
    try {
      await navigator.clipboard.writeText(url);
      toast.success("URL disalin");
    } catch {
      window.prompt("Salin URL berikut:", url);
    }
  };

  const doDownload = async () => {
    try {
      const n = await downloadAsset(asset);
      toast.success(`Mengunduh ${n}`);
    } catch (e) {
      toast.error(errMsg(e, "Gagal mengunduh berkas"));
    }
  };

  const doReplace = async (file) => {
    if (!file) return;
    setReplacing(true);
    try {
      const doc = await replaceFile(asset.id, file);
      toast.success(`Berkas diganti (versi ${doc.version}) — semua halaman pemakainya ikut berubah`);
      onChanged && onChanged(doc);
    } catch (e) {
      toast.error(errMsg(e, "Gagal mengganti berkas"));
    } finally {
      setReplacing(false);
      if (replaceRef.current) replaceRef.current.value = "";
    }
  };

  const doDelete = async () => {
    setDeleting(true);
    try {
      await deleteAsset(asset.id);
      toast.success("Aset dihapus dari Media Library");
      setConfirmDel(false);
      onDeleted && onDeleted(asset.id);
    } catch (e) {
      toast.error(errMsg(e, "Gagal menghapus aset"));
    } finally {
      setDeleting(false);
    }
  };

  const usedTotal = usage?.total || 0;

  return (
    <div className="space-y-3" data-testid="media-detail">
      <div className="overflow-hidden rounded-xl border border-[#EDEEF1] bg-[#0E1726]">
        {asset.kind === "image" ? (
          <img src={absUrl(asset.url)} alt={asset.alt || asset.original_filename}
            className={`w-full object-contain ${compact ? "max-h-[190px]" : "max-h-[260px]"}`}
            data-testid="media-detail-image" />
        ) : (
          <video src={absUrl(asset.url)} controls playsInline
            className={`w-full ${compact ? "max-h-[190px]" : "max-h-[260px]"}`}
            data-testid="media-detail-video" />
        )}
      </div>

      {asset.file_exists === false ? (
        <p className="flex items-start gap-1.5 rounded-lg bg-[#FFF1F0] p-2 text-[11.5px] text-[#A8221A]"
          data-testid="media-detail-missing">
          <FileWarning size={13} className="mt-0.5 shrink-0" />
          Berkas fisiknya tidak ada di penyimpanan (dokumen masih tercatat). Pakai <b>Ganti berkas</b>
          &nbsp;untuk mengunggah ulang — semua halaman yang memakainya akan langsung pulih.
        </p>
      ) : null}

      <div>
        <p className="text-[11px] font-semibold text-[#3a3f4a]">Nama berkas</p>
        <div className="mt-1 flex gap-1.5">
          <Input value={name} onChange={(e) => setName(e.target.value)} className="h-8 text-[12px]"
            data-testid="media-detail-name" />
          <button type="button" className="secondary-button !h-8 shrink-0" onClick={saveName}
            disabled={savingName || name === (asset.original_filename || "")}
            data-testid="media-detail-name-save">
            {savingName ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
          </button>
        </div>
        <p className="mt-1 text-[11px] tabular-nums text-[#8E8E93]" data-testid="media-detail-meta">
          {asset.kind === "image" ? "Foto" : "Video"} · {bytesLabel(asset.size)}
          {asset.width ? ` · ${asset.width}×${asset.height} px` : ""}
          {asset.version > 1 ? ` · versi ${asset.version}` : ""}
        </p>
        <p className="text-[11px] text-[#8E8E93]">
          Diunggah {formatDateTime(asset.created_at)}{asset.uploaded_by ? ` oleh ${asset.uploaded_by}` : ""}
        </p>
      </div>

      <div>
        <label className="text-[11px] font-semibold text-[#3a3f4a]" htmlFor="media-alt">
          Teks alternatif (SEO &amp; aksesibilitas)
        </label>
        <textarea id="media-alt" rows={2} value={alt} onChange={(e) => setAlt(e.target.value)}
          data-testid="media-detail-alt" placeholder="mis. Hiace Premio putih di depan Bromo"
          className="mt-1 w-full rounded-lg border border-[#E5E5EA] bg-white px-2.5 py-1.5 text-[12.5px] text-[#1C1C1E] outline-none focus:border-[#007AFF]" />
        <button type="button" className="secondary-button !h-8 mt-1 w-full" onClick={saveAlt}
          disabled={savingAlt || alt === (asset.alt || "")} data-testid="media-detail-alt-save">
          {savingAlt ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />} Simpan teks alternatif
        </button>
      </div>

      <div>
        <p className="mb-1 text-[11px] font-semibold text-[#3a3f4a]">Folder</p>
        <SelectField testId="media-detail-folder" value={asset.folder_id || ROOT_FOLDER}
          onChange={moveFolder} options={folderOptions(folders)} placeholder="Pindahkan ke…" />
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        <button type="button" className="secondary-button !h-8" onClick={copyUrl}
          data-testid="media-detail-copy"><Copy size={12} /> Salin URL</button>
        <button type="button" className="secondary-button !h-8" onClick={doDownload}
          data-testid="media-detail-download"><Download size={12} /> Unduh</button>
        <button type="button" className="secondary-button !h-8" disabled={replacing}
          onClick={() => replaceRef.current?.click()} data-testid="media-detail-replace">
          {replacing ? <Loader2 size={12} className="animate-spin" /> : <Replace size={12} />} Ganti berkas
        </button>
        <button type="button" className="secondary-button !h-8" disabled={asset.kind !== "image"}
          title={asset.kind === "image" ? "Potong / ubah ukuran" : "Hanya untuk foto"}
          onClick={() => setCropOpen(true)} data-testid="media-detail-crop">
          <Crop size={12} /> Potong
        </button>
        <input ref={replaceRef} type="file" className="hidden" accept={acceptFor(asset.kind)}
          onChange={(e) => doReplace(e.target.files?.[0])} data-testid="media-detail-replace-input" />
        <button type="button" className="secondary-button !h-8 col-span-2 !text-[#A8221A]"
          onClick={() => setConfirmDel(true)} data-testid="media-detail-delete">
          <Trash2 size={12} /> Hapus aset
        </button>
      </div>

      <div className="rounded-lg bg-[#F7F8FA] p-2" data-testid="media-detail-usage">
        <p className="text-[11px] font-semibold text-[#3a3f4a]">Dipakai di</p>
        {usageLoading ? (
          <p className="mt-1 flex items-center gap-1 text-[11.5px] text-[#8E8E93]">
            <Loader2 size={11} className="animate-spin" /> Memeriksa pemakaian…
          </p>
        ) : usage?.failed ? (
          <p className="mt-1 text-[11.5px] text-[#A8221A]">Gagal memeriksa pemakaian aset.</p>
        ) : usedTotal === 0 ? (
          <p className="mt-1 text-[11.5px] text-[#8E8E93]">
            Belum dipakai di halaman iklan atau konten website mana pun.
          </p>
        ) : (
          <ul className="mt-1 space-y-1">
            {(usage.landing_pages || []).map((p) => (
              <li key={p.id} className="flex items-center gap-1.5 text-[11.5px] text-[#1C1C1E]">
                <LayoutTemplate size={11} className="shrink-0 text-[#6B6B73]" />
                <span className="truncate">{p.title}</span>
                <a href={`/lp/${p.slug}`} target="_blank" rel="noopener noreferrer"
                  className="shrink-0 text-[#0B57D0]" aria-label={`Buka halaman ${p.title}`}
                  data-testid={`media-usage-lp-${p.id}`}><ExternalLink size={10} /></a>
              </li>
            ))}
            {(usage.content || []).map((c) => (
              <li key={`${c.resource}-${c.id}`} className="flex items-center gap-1.5 text-[11.5px] text-[#1C1C1E]">
                <FileText size={11} className="shrink-0 text-[#6B6B73]" />
                <span className="truncate">{c.resource_label}: {c.title}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {onPick ? (
        <button type="button" className="primary-button !h-10 w-full" data-testid="media-detail-use"
          onClick={() => onPick(asset)}><Check size={14} /> {pickLabel}</button>
      ) : null}

      <CropDialog open={cropOpen} onOpenChange={setCropOpen} asset={asset}
        onDone={(doc, mode) => {
          setCropOpen(false);
          onChanged && onChanged(doc, mode === "new" ? "created" : "updated");
        }} />

      <ConfirmDialog open={confirmDel} onOpenChange={setConfirmDel} busy={deleting}
        title={`Hapus “${asset.original_filename}”?`}
        description={usedTotal
          ? `Aset ini masih dipakai di ${usedTotal} tempat. Setelah dihapus, gambar di sana akan kosong — ganti dulu gambarnya bila halaman itu sedang tayang.`
          : "Aset akan hilang dari Media Library dan URL publiknya berhenti bekerja."}
        onConfirm={doDelete} testId="media-confirm-delete" />
    </div>
  );
}

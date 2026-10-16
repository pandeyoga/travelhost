import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle, ChevronDown, Download, FolderInput, HardDrive, Images, Loader2, RefreshCw,
  Search, Trash2, UploadCloud, X, Check, FileWarning, Archive,
} from "lucide-react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/shared/DataStates";
import SelectField from "@/components/shared/SelectField";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import MediaFolderTree from "@/components/media/MediaFolderTree";
import MediaGrid from "@/components/media/MediaGrid";
import MediaDetailPanel from "@/components/media/MediaDetailPanel";
import {
  ALL_FOLDERS, ROOT_FOLDER, acceptFor, bulkDelete, bulkMove, errMsg, fetchFolders, fetchHealth, fetchMedia,
  folderOptions, importLegacy, uploadFile,
} from "@/components/media/mediaApi";

/**
 * MediaBrowser — INTI bersama Media Library.
 *
 * Dipakai oleh dua permukaan sekaligus: halaman penuh `/app/media` dan dialog pemilih media yang
 * dipanggil dari CMS website, editor halaman iklan, galeri destinasi, dan tur 360°. Satu inti =
 * satu perilaku. Sebelumnya CMS memakai kotak unggah ad-hoc tanpa pencarian sementara editor iklan
 * punya library sendiri; pengguna yang sama harus mempelajari dua cara kerja untuk satu pekerjaan.
 */
const PAGE_SIZE = 48;
const KIND_TABS = [["", "Semua"], ["image", "Foto"], ["video", "Video"]];

export default function MediaBrowser({
  mode = "page", pickKind = "", multiple = false, onPick, showImport = true,
}) {
  const fileRef = useRef(null);
  const [folders, setFolders] = useState([]);
  const [rootCount, setRootCount] = useState(0);
  const [folderLoading, setFolderLoading] = useState(true);
  const [assets, setAssets] = useState([]);
  const [total, setTotal] = useState(0);
  const [counts, setCounts] = useState({ image: 0, video: 0, all: 0 });
  const [storage, setStorage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [kind, setKind] = useState(pickKind || "");
  const [folderId, setFolderId] = useState(ALL_FOLDERS);
  const [activeId, setActiveId] = useState("");
  const [selected, setSelected] = useState([]);
  const [uploading, setUploading] = useState(0);
  const [progress, setProgress] = useState(0);
  const [missingIds, setMissingIds] = useState([]);
  const [unknownAssets, setUnknownAssets] = useState([]);
  const [confirmBulk, setConfirmBulk] = useState(false);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [importing, setImporting] = useState(false);

  const loadFolders = useCallback(async () => {
    setFolderLoading(true);
    try {
      const data = await fetchFolders();
      setFolders(Array.isArray(data.folders) ? data.folders : []);
      setRootCount(Number(data.root_count) || 0);
    } catch (e) {
      setFolders([]);
    } finally {
      setFolderLoading(false);
    }
  }, []);

  const loadAssets = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchMedia({ q, kind, folderId, limit: PAGE_SIZE, offset: 0 });
      setAssets(Array.isArray(data.assets) ? data.assets : []);
      setTotal(Number(data.total) || 0);
      setCounts(data.counts || { image: 0, video: 0, all: 0 });
      setStorage(data.storage || null);
      if (Array.isArray(data.folders)) setFolders(data.folders);
      setError("");
    } catch (e) {
      setError(errMsg(e, "Gagal memuat Media Library"));
    } finally {
      setLoading(false);
    }
  }, [q, kind, folderId]);

  const loadHealth = useCallback(async () => {
    try {
      const data = await fetchHealth();
      setMissingIds((data.missing || []).map((m) => m.id));
      setUnknownAssets(data.unknown || []);
    } catch {
      setMissingIds([]);
      setUnknownAssets([]);
    }
  }, []);

  useEffect(() => { loadFolders(); loadHealth(); }, [loadFolders, loadHealth]);
  useEffect(() => {
    const t = setTimeout(loadAssets, q ? 300 : 0); // debounce pencarian
    return () => clearTimeout(t);
  }, [loadAssets, q]);

  const loadMore = async () => {
    if (loadingMore || assets.length >= total) return;
    setLoadingMore(true);
    try {
      const data = await fetchMedia({ q, kind, folderId, limit: PAGE_SIZE, offset: assets.length });
      setAssets((prev) => [...prev, ...(Array.isArray(data.assets) ? data.assets : [])]);
      setTotal(Number(data.total) || 0);
    } catch (e) {
      toast.error(errMsg(e, "Gagal memuat halaman berikutnya"));
    } finally {
      setLoadingMore(false);
    }
  };

  const active = useMemo(() => assets.find((a) => a.id === activeId) || null, [assets, activeId]);
  const selectedAssets = useMemo(
    () => assets.filter((a) => selected.includes(a.id)), [assets, selected]);

  const doUpload = async (files) => {
    const list = Array.from(files || []);
    if (!list.length) return;
    setUploading(list.length);
    let lastId = "";
    let okCount = 0;
    for (const file of list) {
      setProgress(0);
      try {
        const doc = await uploadFile(file, folderId === ALL_FOLDERS ? ROOT_FOLDER : folderId, setProgress);
        lastId = doc.id;
        okCount += 1;
        setAssets((prev) => [doc, ...prev]);
        setTotal((n) => n + 1);
      } catch (e) {
        toast.error(`${file.name}: ${errMsg(e, "gagal diunggah")}`);
      } finally {
        setUploading((n) => Math.max(0, n - 1));
      }
    }
    if (okCount) toast.success(`${okCount} berkas terunggah`);
    if (lastId) setActiveId(lastId);
    if (fileRef.current) fileRef.current.value = "";
    loadFolders();
  };

  const onFolderChanged = (nextId) => {
    loadFolders();
    if (nextId !== undefined) setFolderId(nextId);
    loadAssets();
  };

  const onAssetChanged = (doc, kindOfChange) => {
    if (kindOfChange === "created") {
      setAssets((prev) => [doc, ...prev]);
      setActiveId(doc.id);
      setTotal((n) => n + 1);
    } else {
      setAssets((prev) => prev.map((a) => (a.id === doc.id ? { ...a, ...doc } : a)));
    }
    loadFolders();
    loadHealth();
  };

  const onAssetDeleted = (id) => {
    setAssets((prev) => prev.filter((a) => a.id !== id));
    setSelected((prev) => prev.filter((x) => x !== id));
    setActiveId("");
    setTotal((n) => Math.max(0, n - 1));
    loadFolders();
  };

  const doBulkMove = async (target) => {
    setBulkBusy(true);
    try {
      const out = await bulkMove(selected, target);
      toast.success(`${out.moved} aset dipindahkan`);
      setSelected([]);
      loadFolders();
      loadAssets();
    } catch (e) {
      toast.error(errMsg(e, "Gagal memindahkan aset"));
    } finally {
      setBulkBusy(false);
    }
  };

  const doBulkDelete = async () => {
    setBulkBusy(true);
    try {
      const out = await bulkDelete(selected);
      toast.success(out.used_by
        ? `${out.deleted} aset dihapus. Perhatian: ${out.used_by} pemakaian terdampak — ganti gambarnya.`
        : `${out.deleted} aset dihapus`);
      setSelected([]);
      setActiveId("");
      setConfirmBulk(false);
      loadFolders();
      loadAssets();
    } catch (e) {
      toast.error(errMsg(e, "Gagal menghapus aset"));
    } finally {
      setBulkBusy(false);
    }
  };

  const doBulkDownload = async () => {
    const { downloadAsset } = await import("@/components/media/mediaApi");
    let ok = 0;
    for (const a of selectedAssets) {
      try {
        await downloadAsset(a);
        ok += 1;
      } catch {
        toast.error(`Gagal mengunduh ${a.original_filename}`);
      }
    }
    if (ok) toast.success(`${ok} berkas diunduh`);
  };

  const doImport = async () => {
    setImporting(true);
    try {
      const out = await importLegacy();
      if (out.imported) {
        toast.success(`${out.imported} aset CMS lama didaftarkan ke Media Library`);
      } else if (out.total_files === 0) {
        toast.message("Tidak ada berkas CMS lama di penyimpanan server");
      } else {
        toast.message(`Semua ${out.skipped} aset lama sudah terdaftar sebelumnya`);
      }
      if (out.failed) toast.error(`${out.failed} berkas gagal diimpor`);
      loadFolders();
      loadAssets();
    } catch (e) {
      toast.error(errMsg(e, "Gagal mengimpor aset lama"));
    } finally {
      setImporting(false);
    }
  };

  const toggleSelect = (id) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const uploadDisabled = uploading > 0 || Boolean(storage && !storage.ready);
  const uploadBtn = (
    <button type="button" className="primary-button !h-9" data-testid="media-upload"
      onClick={() => fileRef.current?.click()} disabled={uploadDisabled}>
      {uploading > 0 ? <Loader2 size={13} className="animate-spin" /> : <UploadCloud size={13} />}
      {uploading > 0 ? `Mengunggah ${uploading}… ${progress}%` : "Unggah"}
    </button>
  );

  const activeFolderLabel = folderId === ALL_FOLDERS ? "Semua media"
    : folderId === ROOT_FOLDER ? "Tanpa folder"
      : (folders.find((f) => f.id === folderId)?.path_label || "Folder");

  return (
    <div className="space-y-3" data-testid="media-browser">
      <div className="flex flex-wrap items-center gap-2">
        {pickKind ? null : (
          <div className="flex items-center gap-1 rounded-lg bg-[#F2F2F5] p-0.5">
            {KIND_TABS.map(([value, label]) => (
              <button key={value || "all"} type="button" onClick={() => setKind(value)}
                data-testid={`media-tab-${value || "all"}`}
                className={`rounded-md px-2.5 py-1.5 text-[12px] font-semibold transition-colors ${
                  kind === value ? "bg-white text-[#1C1C1E] shadow-sm" : "text-[#6B6B73]"}`}>
                {label}
                <span className="ml-1 tabular-nums text-[11px] text-[#8E8E93]">
                  {value === "image" ? counts.image : value === "video" ? counts.video : counts.all}
                </span>
              </button>
            ))}
          </div>
        )}
        <div className="relative min-w-[170px] flex-1">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#8E8E93]" />
          <Input value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Cari nama berkas atau teks alternatif…" className="h-9 pl-8 text-[12.5px]"
            data-testid="media-search" />
        </div>
        <input ref={fileRef} type="file" multiple className="hidden"
          accept={acceptFor(pickKind || kind)}
          onChange={(e) => doUpload(e.target.files)} data-testid="media-file-input" />
        {uploadBtn}
        {showImport ? (
          <button type="button" className="secondary-button !h-9" onClick={doImport} disabled={importing}
            title="Daftarkan gambar CMS lama (/api/uploads/cms) ke Media Library"
            data-testid="media-import-legacy">
            {importing ? <Loader2 size={13} className="animate-spin" /> : <Archive size={13} />}
            <span className="hidden sm:inline">Daftarkan aset CMS lama</span>
          </button>
        ) : null}
        <button type="button" className="icon-button !h-9 !w-9" onClick={() => { loadAssets(); loadFolders(); loadHealth(); }}
          aria-label="Muat ulang" data-testid="media-refresh"><RefreshCw size={13} /></button>
      </div>

      {storage && !storage.ready ? (
        <p className="flex items-start gap-1.5 rounded-lg bg-[#FFF8EC] p-2 text-[12px] text-[#8A5300]"
          data-testid="media-storage-warning">
          <AlertCircle size={13} className="mt-0.5 shrink-0" /> Unggah dinonaktifkan: {storage.reason}
        </p>
      ) : null}
      {missingIds.length ? (
        <p className="flex items-start gap-1.5 rounded-lg bg-[#FFF1F0] p-2 text-[12px] text-[#A8221A]"
          data-testid="media-missing-warning">
          <FileWarning size={13} className="mt-0.5 shrink-0" />
          <span><b className="tabular-nums">{missingIds.length}</b> aset TERBUKTI kehilangan berkas fisiknya
            (ditandai di kisi). Pilih asetnya lalu pakai <b>Ganti berkas</b> untuk memulihkan tanpa
            menyunting ulang halaman yang memakainya.</span>
        </p>
      ) : null}
      {unknownAssets.length ? (
        <p className="flex items-start gap-1.5 rounded-lg bg-[#FFF8EC] p-2 text-[12px] text-[#8A5300]"
          data-testid="media-unknown-warning">
          <AlertCircle size={13} className="mt-0.5 shrink-0" />
          <span><b className="tabular-nums">{unknownAssets.length}</b> aset tidak bisa diverifikasi
            (bukan berarti hilang) — {unknownAssets[0]?.reason || "pengecekan penyimpanan gagal"}.
            Coba muat ulang; bila berulang, periksa konfigurasi penyimpanan.</span>
        </p>
      ) : null}

      {selected.length ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[#CDE0FF] bg-[#F2F7FF] px-3 py-2"
          data-testid="media-selection-bar">
          <span className="text-[12.5px] font-semibold tabular-nums text-[#0B57D0]"
            data-testid="media-selection-count">{selected.length} aset dipilih</span>
          <div className="w-[210px]">
            <SelectField testId="media-bulk-move" value="" onChange={doBulkMove}
              options={folderOptions(folders, { rootLabel: "Akar (tanpa folder)" })}
              placeholder="Pindahkan ke…" disabled={bulkBusy} />
          </div>
          <button type="button" className="secondary-button !h-8" onClick={doBulkDownload}
            data-testid="media-bulk-download"><Download size={12} /> Unduh</button>
          <button type="button" className="secondary-button !h-8 !text-[#A8221A]" disabled={bulkBusy}
            onClick={() => setConfirmBulk(true)} data-testid="media-bulk-delete">
            <Trash2 size={12} /> Hapus
          </button>
          <button type="button" className="secondary-button !h-8" onClick={() => setSelected([])}
            data-testid="media-selection-clear"><X size={12} /> Bersihkan</button>
          {multiple && onPick ? (
            <button type="button" className="primary-button !h-8 ml-auto" data-testid="media-pick-many"
              onClick={() => onPick(selectedAssets)}>
              <Check size={13} /> Pakai {selected.length} media
            </button>
          ) : null}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-0 overflow-hidden rounded-[14px] border border-[#EDEEF1] bg-white lg:grid-cols-[200px_1fr_318px]">
        <aside className="border-b border-[#EFF0F2] p-3 lg:border-b-0 lg:border-r">
          <MediaFolderTree folders={folders} rootCount={rootCount} totalCount={counts.all}
            activeId={folderId} loading={folderLoading} maxDepth={4}
            onSelect={(id) => { setFolderId(id); setSelected([]); }}
            onChanged={onFolderChanged} />
        </aside>

        <section className="min-w-0 border-b border-[#EFF0F2] p-3 lg:border-b-0 lg:border-r">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="truncate text-[12px] font-semibold text-[#1C1C1E]" data-testid="media-folder-label">
              <Images size={12} className="mr-1 inline" /> {activeFolderLabel}
            </p>
            <p className="shrink-0 text-[11px] tabular-nums text-[#8E8E93]" data-testid="media-total">
              {assets.length} dari {total} aset
              {storage ? ` · ${storage.used_mb} MB terpakai` : ""}
            </p>
          </div>
          {error ? (
            <ErrorState message={error} onRetry={loadAssets} testId="media-error" />
          ) : (
            <>
              <div className={mode === "picker" ? "max-h-[380px] overflow-y-auto pr-1" : ""}>
                <MediaGrid assets={assets} loading={loading} activeId={activeId} selected={selected}
                  missingIds={missingIds}
                  onActivate={(a) => setActiveId(a.id)} onToggleSelect={toggleSelect}
                  columnsClass={mode === "picker" ? "grid-cols-2 sm:grid-cols-3" : ""}
                  emptyTitle={q || kind || folderId !== ALL_FOLDERS
                    ? "Tidak ada aset yang cocok" : "Belum ada media"}
                  emptyDescription={q || kind || folderId !== ALL_FOLDERS
                    ? "Ubah kata kunci, jenis, atau folder yang dipilih."
                    : `Unggah foto (maks ${storage?.max_image_mb || 10} MB) atau video (maks ${storage?.max_video_mb || 50} MB). Sudah punya gambar CMS lama? Tekan “Daftarkan aset CMS lama”.`}
                  emptyAction={uploadBtn} />
              </div>
              {assets.length < total ? (
                <div className="flex justify-center pt-3">
                  <button type="button" className="secondary-button !h-8" onClick={loadMore}
                    disabled={loadingMore} data-testid="media-load-more">
                    {loadingMore ? <Loader2 size={12} className="animate-spin" /> : <ChevronDown size={13} />}
                    Muat lebih banyak ({total - assets.length} tersisa)
                  </button>
                </div>
              ) : null}
            </>
          )}
        </section>

        <aside className="min-w-0 p-3" data-testid="media-detail-pane">
          <MediaDetailPanel asset={active} folders={folders} compact={mode === "picker"}
            onChanged={onAssetChanged} onDeleted={onAssetDeleted}
            onPick={onPick && !multiple ? onPick : null} />
        </aside>
      </div>

      <p className="flex items-center gap-1.5 text-[11px] text-[#8E8E93]" data-testid="media-storage-note">
        <HardDrive size={11} />
        Penyimpanan: {storage?.backend_label || "—"}. Format didukung:{" "}
        {(storage?.accepted?.image || []).join("/")} · {(storage?.accepted?.video || []).join("/")}.
      </p>

      <ConfirmDialog open={confirmBulk} onOpenChange={setConfirmBulk} busy={bulkBusy}
        title={`Hapus ${selected.length} aset terpilih?`}
        description="Aset akan hilang dari Media Library dan URL publiknya berhenti bekerja. Halaman/konten yang masih memakainya akan menampilkan gambar kosong."
        onConfirm={doBulkDelete} testId="media-confirm-bulk-delete" />

      <span className="hidden"><FolderInput size={1} /></span>
    </div>
  );
}

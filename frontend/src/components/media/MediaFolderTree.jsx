import { useState } from "react";
import { Folder, FolderOpen, FolderPlus, Images, Loader2, Pencil, Trash2, Check, X } from "lucide-react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import SelectField from "@/components/shared/SelectField";
import {
  ALL_FOLDERS, ROOT_FOLDER, createFolder, deleteFolder, errMsg, folderOptions, updateFolder,
} from "@/components/media/mediaApi";

/**
 * MediaFolderTree — sidebar folder Media Library.
 *
 * Folder di sistem ini adalah LABEL (metadata), bukan direktori disk. Konsekuensi yang disengaja
 * dan ditampilkan jelas ke pengguna: menghapus folder TIDAK menghapus aset — isinya naik ke folder
 * induk. Menghapus 200 foto karena satu klik salah adalah kerusakan yang tak bisa dibatalkan,
 * jadi perilaku "aman" itu ditulis apa adanya di dialog konfirmasi.
 */
export function MediaFolderTree({
  folders = [], rootCount = 0, totalCount = 0, activeId = ALL_FOLDERS, onSelect,
  loading = false, onChanged, maxDepth = 4,
}) {
  const [creatingIn, setCreatingIn] = useState(null); // null = tertutup, "" = akar, id = subfolder
  const [newName, setNewName] = useState("");
  const [renaming, setRenaming] = useState("");
  const [renameVal, setRenameVal] = useState("");
  const [moving, setMoving] = useState("");
  const [busy, setBusy] = useState(false);

  const submitCreate = async () => {
    if (!newName.trim()) {
      toast.message("Nama folder wajib diisi");
      return;
    }
    setBusy(true);
    try {
      const doc = await createFolder(newName.trim(), creatingIn || ROOT_FOLDER);
      toast.success(`Folder "${doc.name}" dibuat`);
      setNewName("");
      setCreatingIn(null);
      onChanged && onChanged(doc.id);
    } catch (e) {
      toast.error(errMsg(e, "Gagal membuat folder"));
    } finally {
      setBusy(false);
    }
  };

  const submitRename = async (id) => {
    if (!renameVal.trim()) return;
    setBusy(true);
    try {
      await updateFolder(id, { name: renameVal.trim() });
      toast.success("Nama folder diperbarui");
      setRenaming("");
      onChanged && onChanged();
    } catch (e) {
      toast.error(errMsg(e, "Gagal mengganti nama folder"));
    } finally {
      setBusy(false);
    }
  };

  const submitMove = async (id, parentId) => {
    setBusy(true);
    try {
      await updateFolder(id, { parent_id: parentId });
      toast.success("Folder dipindahkan");
      setMoving("");
      onChanged && onChanged();
    } catch (e) {
      toast.error(errMsg(e, "Gagal memindahkan folder"));
    } finally {
      setBusy(false);
    }
  };

  const submitDelete = async (folder) => {
    const msg = folder.asset_count
      ? `Hapus folder "${folder.name}"? ${folder.asset_count} aset di dalamnya TIDAK dihapus — akan dipindahkan ke folder induk.`
      : `Hapus folder "${folder.name}"?`;
    if (!window.confirm(msg)) return;
    setBusy(true);
    try {
      const out = await deleteFolder(folder.id);
      toast.success(out.moved_assets
        ? `Folder dihapus. ${out.moved_assets} aset dipindahkan ke induk.`
        : "Folder dihapus");
      onChanged && onChanged(ALL_FOLDERS);
    } catch (e) {
      toast.error(errMsg(e, "Gagal menghapus folder"));
    } finally {
      setBusy(false);
    }
  };

  const rowClass = (active) =>
    `group flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-left text-[12.5px] transition-colors ${
      active ? "bg-[#E8F1FF] font-semibold text-[#0B57D0]" : "text-[#3a3f4a] hover:bg-[#F2F3F6]"}`;

  return (
    <div className="space-y-1" data-testid="media-folder-tree">
      <div className="mb-1 flex items-center justify-between gap-1 px-1">
        <p className="text-[10.5px] font-bold uppercase tracking-wide text-[#8E8E93]">Folder</p>
        <button type="button" className="icon-button !h-7 !w-7" aria-label="Buat folder baru"
          title="Buat folder baru" data-testid="media-folder-new"
          onClick={() => { setCreatingIn(ROOT_FOLDER); setNewName(""); }}>
          <FolderPlus size={13} />
        </button>
      </div>

      <button type="button" className={rowClass(activeId === ALL_FOLDERS)}
        onClick={() => onSelect(ALL_FOLDERS)} data-testid="media-folder-all">
        <Images size={13} /> <span className="flex-1 truncate">Semua media</span>
        <span className="tabular-nums text-[11px] text-[#8E8E93]">{totalCount}</span>
      </button>
      <button type="button" className={rowClass(activeId === ROOT_FOLDER)}
        onClick={() => onSelect(ROOT_FOLDER)} data-testid="media-folder-root">
        <Folder size={13} /> <span className="flex-1 truncate">Tanpa folder</span>
        <span className="tabular-nums text-[11px] text-[#8E8E93]">{rootCount}</span>
      </button>

      {creatingIn !== null ? (
        <div className="flex items-center gap-1 rounded-lg bg-[#F7F8FA] p-1.5" data-testid="media-folder-form">
          <Input autoFocus value={newName} onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submitCreate()}
            placeholder="Nama folder" className="h-8 text-[12px]" data-testid="media-folder-name-input" />
          <button type="button" className="icon-button !h-8 !w-8 !text-[#1E9E5A]" onClick={submitCreate}
            disabled={busy} aria-label="Simpan folder" data-testid="media-folder-save">
            {busy ? <Loader2 size={13} className="animate-spin" /> : <Check size={14} />}
          </button>
          <button type="button" className="icon-button !h-8 !w-8" aria-label="Batal"
            onClick={() => setCreatingIn(null)} data-testid="media-folder-cancel"><X size={14} /></button>
        </div>
      ) : null}

      {loading ? (
        <div className="space-y-1 py-1" data-testid="media-folder-loading">
          {[0, 1, 2].map((i) => <div key={i} className="h-7 animate-pulse rounded-lg bg-[#EEF1F5]" />)}
        </div>
      ) : !folders.length ? (
        <p className="px-2 py-3 text-[11.5px] text-[#8E8E93]" data-testid="media-folder-empty">
          Belum ada folder. Buat folder untuk mengelompokkan aset per kampanye atau per destinasi.
        </p>
      ) : (
        folders.map((f) => (
          <div key={f.id}>
            {renaming === f.id ? (
              <div className="flex items-center gap-1 rounded-lg bg-[#F7F8FA] p-1.5">
                <Input autoFocus value={renameVal} onChange={(e) => setRenameVal(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && submitRename(f.id)}
                  className="h-8 text-[12px]" data-testid={`media-folder-rename-input-${f.id}`} />
                <button type="button" className="icon-button !h-8 !w-8 !text-[#1E9E5A]" disabled={busy}
                  onClick={() => submitRename(f.id)} aria-label="Simpan nama"
                  data-testid={`media-folder-rename-save-${f.id}`}><Check size={14} /></button>
                <button type="button" className="icon-button !h-8 !w-8" aria-label="Batal"
                  onClick={() => setRenaming("")}><X size={14} /></button>
              </div>
            ) : (
              <div className={rowClass(activeId === f.id)} style={{ paddingLeft: 8 + (f.depth || 0) * 12 }}>
                <button type="button" className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
                  onClick={() => onSelect(f.id)} data-testid={`media-folder-${f.id}`}
                  title={f.path_label || f.name}>
                  {activeId === f.id ? <FolderOpen size={13} /> : <Folder size={13} />}
                  <span className="truncate">{f.name}</span>
                  <span className="tabular-nums text-[11px] text-[#8E8E93]">{f.asset_count}</span>
                </button>
                <span className="flex shrink-0 items-center opacity-0 transition-opacity group-hover:opacity-100">
                  <button type="button" className="icon-button !h-6 !w-6" aria-label={`Ganti nama ${f.name}`}
                    title="Ganti nama" data-testid={`media-folder-rename-${f.id}`}
                    onClick={() => { setRenaming(f.id); setRenameVal(f.name); }}><Pencil size={11} /></button>
                  <button type="button" className="icon-button !h-6 !w-6" aria-label={`Buat subfolder di ${f.name}`}
                    title="Buat subfolder" data-testid={`media-folder-sub-${f.id}`}
                    disabled={(f.depth || 0) + 1 >= maxDepth}
                    onClick={() => { setCreatingIn(f.id); setNewName(""); }}><FolderPlus size={11} /></button>
                  <button type="button" className="icon-button !h-6 !w-6 !text-[#A8221A]"
                    aria-label={`Hapus folder ${f.name}`} title="Hapus folder"
                    data-testid={`media-folder-delete-${f.id}`}
                    onClick={() => submitDelete(f)}><Trash2 size={11} /></button>
                </span>
              </div>
            )}
            {moving === f.id ? (
              <div className="mt-1 rounded-lg bg-[#F7F8FA] p-1.5">
                <SelectField testId={`media-folder-move-select-${f.id}`}
                  value={f.parent_id || ROOT_FOLDER}
                  onChange={(v) => submitMove(f.id, v)}
                  options={folderOptions(folders.filter((x) => x.id !== f.id), { rootLabel: "Akar" })}
                  placeholder="Pindahkan ke…" />
              </div>
            ) : (
              <button type="button" className="ml-2 hidden text-[10.5px] text-[#0B57D0] hover:underline group-hover:inline"
                onClick={() => setMoving(f.id)} data-testid={`media-folder-move-${f.id}`}>Pindahkan folder</button>
            )}
          </div>
        ))
      )}
    </div>
  );
}

export default MediaFolderTree;

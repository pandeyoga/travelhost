import apiClient from "@/services/apiClient";

/**
 * mediaApi.js — satu pintu pemanggilan API Media Library untuk SELURUH frontend.
 *
 * Kenapa dipusatkan: sebelum ronde ini ada dua jalur unggah yang berbeda (`/uploads/cms` di CMS dan
 * `/landing/media` di editor iklan) dengan penanganan galat, batas ukuran, dan bentuk URL yang
 * berbeda pula. Satu modul membuat semua permukaan (halaman Media, pemilih CMS, pemilih iklan,
 * galeri) berperilaku identik — termasuk pesan galat yang sudah diterjemahkan ke bahasa manusia.
 */
const BACKEND = process.env.REACT_APP_BACKEND_URL || "";

/** URL absolut untuk <img>/<video> (respons API memakai path relatif agar portabel). */
export const absUrl = (u) => (u && String(u).startsWith("/") ? `${BACKEND}${u}` : u || "");

export const bytesLabel = (n) => {
  const v = Number(n || 0);
  if (v >= 1024 * 1024) return `${(v / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(v / 1024))} KB`;
};

/** Pesan galat yang bisa dibaca pengguna — jangan pernah menampilkan "[object Object]". */
export const errMsg = (e, fallback = "Terjadi kesalahan") => {
  const d = e?.response?.data?.detail;
  if (typeof d === "string" && d.trim()) return d;
  if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg);
  return e?.message ? `${fallback} (${e.message})` : fallback;
};

export const ROOT_FOLDER = "";
export const ALL_FOLDERS = "__all__";

// Daftar `accept` memakai EKSTENSI + MIME eksplisit. Wildcard `video/*` saja bergantung pada
// registri MIME OS — di Windows tanpa QuickTime, .mov/.webm tidak dikenali sehingga file explorer
// menyembunyikan videonya (tidak bisa dipilih). Ekstensi eksplisit membuat filter selalu benar.
export const ACCEPT_IMAGE = ".jpg,.jpeg,.png,.webp,.avif,.gif,image/jpeg,image/png,image/webp,image/avif,image/gif";
export const ACCEPT_VIDEO = ".mp4,.m4v,.webm,.mov,video/mp4,video/webm,video/quicktime";
export const ACCEPT_ALL = `${ACCEPT_IMAGE},${ACCEPT_VIDEO}`;
export const acceptFor = (kind) => (kind === "video" ? ACCEPT_VIDEO : kind === "image" ? ACCEPT_IMAGE : ACCEPT_ALL);

// --------------------------------------------------------------------------- aset
export async function fetchMedia({ q = "", kind = "", folderId = ALL_FOLDERS, limit = 60, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (q.trim()) params.set("q", q.trim());
  if (kind) params.set("kind", kind);
  // Tidak mengirim folder_id = semua folder. Mengirim string kosong = HANYA akar.
  if (folderId !== ALL_FOLDERS) params.set("folder_id", folderId);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  const { data } = await apiClient.get(`/media?${params.toString()}`);
  return data;
}

export async function fetchFolders() {
  const { data } = await apiClient.get("/media/folders");
  return data;
}

export async function uploadFile(file, folderId = ROOT_FOLDER, onProgress) {
  const form = new FormData();
  form.append("file", file);
  form.append("folder_id", folderId === ALL_FOLDERS ? ROOT_FOLDER : folderId);
  const { data } = await apiClient.post("/media", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (evt) => {
      if (onProgress && evt.total) onProgress(Math.round((evt.loaded / evt.total) * 100));
    },
  });
  return data;
}

export async function patchAsset(id, patch) {
  const { data } = await apiClient.patch(`/media/${id}`, patch);
  return data;
}

export async function deleteAsset(id) {
  const { data } = await apiClient.delete(`/media/${id}`);
  return data;
}

export async function bulkDelete(ids) {
  const { data } = await apiClient.post("/media/bulk-delete", { ids });
  return data;
}

export async function bulkMove(ids, folderId) {
  const { data } = await apiClient.post("/media/bulk-move", {
    ids, folder_id: folderId === ALL_FOLDERS ? ROOT_FOLDER : folderId,
  });
  return data;
}

export async function fetchUsage(id) {
  const { data } = await apiClient.get(`/media/${id}/usage`);
  return data;
}

export async function replaceFile(id, file, onProgress) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post(`/media/${id}/replace`, form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (evt) => {
      if (onProgress && evt.total) onProgress(Math.round((evt.loaded / evt.total) * 100));
    },
  });
  return data;
}

export async function cropAsset(id, payload) {
  const { data } = await apiClient.post(`/media/${id}/crop`, payload);
  return data;
}

export async function importLegacy() {
  const { data } = await apiClient.post("/media/import-legacy");
  return data;
}

export async function fetchHealth() {
  const { data } = await apiClient.get("/media/health");
  return data;
}

/**
 * Unduh berkas asli.
 *
 * Tidak memakai `<a download href=...>` biasa karena endpoint unduh BER-AUTH (butuh header
 * Authorization) — tautan langsung akan mendapat 401. Jadi berkas diambil sebagai blob lewat
 * apiClient lalu "diklik" secara terprogram; setelah itu object URL dilepas supaya memori tab
 * tidak menumpuk saat pengguna mengunduh banyak berkas.
 */
export async function downloadAsset(asset) {
  const res = await apiClient.get(`/media/${asset.id}/download`, { responseType: "blob" });
  const disposition = res.headers?.["content-disposition"] || "";
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
  let name = asset.original_filename || asset.id;
  if (match) {
    try {
      name = decodeURIComponent(match[1]);
    } catch {
      name = match[1];
    }
  }
  const url = window.URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
  return name;
}

// --------------------------------------------------------------------------- folder
export async function createFolder(name, parentId = ROOT_FOLDER) {
  const { data } = await apiClient.post("/media/folders", {
    name, parent_id: parentId === ALL_FOLDERS ? ROOT_FOLDER : parentId,
  });
  return data;
}

export async function updateFolder(id, patch) {
  const { data } = await apiClient.patch(`/media/folders/${id}`, patch);
  return data;
}

export async function deleteFolder(id) {
  const { data } = await apiClient.delete(`/media/folders/${id}`);
  return data;
}

/** Opsi SelectField "pindahkan ke" — akar selalu tersedia, folder ditampilkan berjenjang. */
export function folderOptions(folders, { excludeId = "", rootLabel = "Akar (tanpa folder)" } = {}) {
  const opts = [{ value: ROOT_FOLDER, label: rootLabel }];
  (folders || []).forEach((f) => {
    if (f.id === excludeId) return;
    opts.push({ value: f.id, label: f.path_label || f.name });
  });
  return opts;
}

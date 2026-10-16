// mediaKind.js — deteksi video dari URL/item galeri (SSOT untuk semua permukaan publik & CMS).
// URL Media Library tidak berekstensi (/api/public/media/med_x), jadi saat video dipilih dari
// Library kita tambahkan penanda `?kind=video` (diabaikan backend) agar renderer tahu harus
// memakai <video>, apa pun bentuk penyimpanannya (string URL polos atau {url, caption}).
const VIDEO_EXT_RE = /\.(mp4|m4v|webm|mov)(\?|#|$)/i;
const KIND_RE = /[?&#]kind=video\b/i;

export const isVideoUrl = (u) => {
  const s = String(u || "");
  return VIDEO_EXT_RE.test(s) || KIND_RE.test(s);
};

export const isVideoItem = (it) => {
  if (!it) return false;
  if (typeof it === "string") return isVideoUrl(it);
  return it.kind === "video" || isVideoUrl(it.url || it.src);
};

export const itemUrl = (it) => (typeof it === "string" ? it : (it && (it.url || it.src)) || "");

/** URL aset dari Media Library yang membawa penanda jenisnya. */
export const assetUrl = (a) => {
  const u = (a && a.url) || "";
  if (!u || a.kind !== "video" || isVideoUrl(u)) return u;
  return `${u}${u.includes("?") ? "&" : "?"}kind=video`;
};

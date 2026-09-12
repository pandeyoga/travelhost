// lib/lang.js — CMS-06: bahasa aktif situs publik (ID default, EN opsional).
//
// Disimpan di modul (bukan hanya React state) karena `services/apiClient` — yang bukan
// komponen — perlu membaca bahasa aktif untuk menambahkan `?lang=` ke setiap permintaan
// `/public/*`. Sumber prioritas: query URL (`?lang=en`, mudah dibagikan & dipakai crawler)
// → localStorage (preferensi pengunjung) → Indonesia.
export const LANGS = [
  { code: "id", label: "Indonesia", short: "ID", locale: "id_ID" },
  { code: "en", label: "English", short: "EN", locale: "en_US" },
];
export const DEFAULT_LANG = "id";
const KEY = "tf_lang";
const listeners = new Set();

function normalize(value) {
  const code = String(value || "").trim().toLowerCase().split("-")[0];
  return LANGS.some((l) => l.code === code) ? code : "";
}

let current = (() => {
  if (typeof window === "undefined") return DEFAULT_LANG;
  try {
    const fromUrl = normalize(new URLSearchParams(window.location.search).get("lang"));
    if (fromUrl) return fromUrl;
    return normalize(localStorage.getItem(KEY)) || DEFAULT_LANG;
  } catch {
    return DEFAULT_LANG;
  }
})();

export function getLang() {
  return current;
}

export function isDefaultLang() {
  return current === DEFAULT_LANG;
}

export function langMeta(code = current) {
  return LANGS.find((l) => l.code === code) || LANGS[0];
}

/** Ganti bahasa: simpan preferensi, samakan query URL, lalu beri tahu pelanggan (hook). */
export function setLang(value) {
  const next = normalize(value) || DEFAULT_LANG;
  if (next === current) return current;
  current = next;
  try { localStorage.setItem(KEY, next); } catch { /* private mode */ }
  if (typeof window !== "undefined") {
    try {
      const url = new URL(window.location.href);
      if (next === DEFAULT_LANG) url.searchParams.delete("lang");
      else url.searchParams.set("lang", next);
      window.history.replaceState({}, "", url.toString());
    } catch { /* URL tak bisa diubah — tidak fatal */ }
  }
  listeners.forEach((fn) => { try { fn(current); } catch { /* jangan rusak render */ } });
  return current;
}

/** Sinkronkan dari URL saat navigasi SPA (dipanggil PublicLayout tiap perubahan route). */
export function syncLangFromUrl() {
  if (typeof window === "undefined") return current;
  const fromUrl = normalize(new URLSearchParams(window.location.search).get("lang"));
  if (fromUrl && fromUrl !== current) {
    current = fromUrl;
    try { localStorage.setItem(KEY, fromUrl); } catch { /* private mode */ }
    listeners.forEach((fn) => { try { fn(current); } catch { /* noop */ } });
  }
  return current;
}

export function subscribeLang(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

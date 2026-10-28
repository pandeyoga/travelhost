/**
 * layoutDiff.js — muatan simpan "Tampilan dokumen" yang TIDAK membekukan pewarisan.
 *
 * Backend (services/doc_layout.get_layout) merakit layout efektif berlapis:
 *   bawaan kode → identitas perusahaan (settings) → `__default__` → override kode itu sendiri,
 * dan PUT /doc-layouts/{code} menyimpan PERSIS apa yang dikirim sebagai override kode. GET hanya
 * mengembalikan layout EFEKTIF (tanpa penanda mana yang warisan). Dulu panel mengirim layout efektif
 * utuh, sehingga setelah INVOICE_DP disimpan sekali, nama perusahaan dsb. dari `__default__` ikut
 * tersalin dan perubahan `__default__` berikutnya tidak lagi berpengaruh.
 *
 * Sekarang: `__default__` tetap mengirim semuanya; kode lain hanya mengirim nilai yang BERBEDA dari
 * warisannya. Granularitas mengikuti `_merge` backend: brand/table/options digabung per kunci,
 * sections/money_rows/signatures diganti utuh (jadi dibandingkan utuh).
 */
export const DEFAULT_CODE = "__default__";
const MERGED_DICTS = ["brand", "table", "options"];

/** Bagian layout yang bisa disimpan/dipratinjau (tanpa code/label/title/overridden). */
export function pick(layout) {
  if (!layout) return {};
  const { brand, table, sections, money_rows, signatures, options } = layout;
  return { brand, table, sections, money_rows, signatures, options };
}

const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);

/** Sama secara isi; null ≡ tidak ada (backend membuang None: exclude_none + `_merge`). */
export function same(a, b) {
  if (a == null || b == null) return a == null && b == null;
  if (Array.isArray(a) || Array.isArray(b)) {
    return Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((x, i) => same(x, b[i]));
  }
  if (isObj(a) && isObj(b)) return [...new Set([...Object.keys(a), ...Object.keys(b)])].every((k) => same(a[k], b[k]));
  return a === b;
}

/** Hanya bagian `cur` yang berbeda dari `base`; bagian yang sama dihilangkan → tetap mewarisi. */
export function diffOverrides(cur, base) {
  const out = {};
  Object.entries(cur || {}).forEach(([key, val]) => {
    if (val === undefined) return;
    const b = (base || {})[key];
    if (MERGED_DICTS.includes(key) && isObj(val) && isObj(b)) {
      const sub = Object.fromEntries(Object.entries(val).filter(([k, v]) => !same(v, b[k])));
      if (Object.keys(sub).length) out[key] = sub;
    } else if (!same(val, b)) {
      out[key] = val;
    }
  });
  return out;
}

// Kunci yang BAWAANNYA berbeda per jenis dokumen (services/doc_layout.default_layout): baris biaya
// (milik `__default__` sengaja tidak diwariskan) dan kolom tanda tangan kwitansi (+ "Penyetor").
const ownDefaultKeys = (code) => (code === "KWITANSI" ? ["money_rows", "signatures"] : ["money_rows"]);

/**
 * Nilai warisan kode ini = layout efektifnya bila kode itu tidak menyimpan override apa pun.
 * - Belum disesuaikan: layout efektif yang dimuat ADALAH warisannya (persis, untuk semua kunci).
 * - Sudah disesuaikan: pakai layout efektif `__default__` (identik untuk brand/table/options/
 *   sections/signatures). Kunci berbawaan per-jenis tak bisa dipastikan dari frontend → tidak
 *   dibandingkan (selalu dikirim): lebih baik tetap "beku" daripada diam-diam berubah.
 */
export function inheritedBase({ code, own, def, customized }) {
  if (code === DEFAULT_CODE) return null;
  if (!customized) return pick(own);
  if (!def) return null;
  const base = pick(def);
  ownDefaultKeys(code).forEach((k) => { delete base[k]; });
  return base;
}

/** Body PUT /doc-layouts/{code}. Tanpa warisan yang diketahui → kirim utuh (perilaku lama). */
export function layoutPayload(code, layout, base) {
  const full = pick(layout);
  if (code === DEFAULT_CODE || !base) return full;
  return diffOverrides(full, base);
}

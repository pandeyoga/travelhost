/**
 * lib/lpAttribution.js — penangkap atribusi iklan untuk halaman `/lp/:slug`.
 *
 * Masalah bisnis yang diselesaikan: klik iklan membawa parameter (`utm_*`, `gclid`, `fbclid`,
 * `ctwa_clid`) di URL. Kalau pengunjung mengklik tombol ke halaman lain lalu baru mengisi form,
 * parameter itu HILANG dan lead tidak bisa dihubungkan ke iklan yang membayarnya — laporan
 * CPL/ROAS jadi bohong. Modul ini menyimpan sentuhan PERTAMA (localStorage, awet lintas sesi)
 * dan sentuhan TERAKHIR (sessionStorage), lalu mengirim keduanya bersama lead.
 *
 * Semua akses storage dibungkus try/catch: mode privat/incognito bisa melarangnya, dan halaman
 * iklan TIDAK BOLEH gagal render hanya karena pelacakan tidak tersedia.
 */
const VID_KEY = "rz_lp_vid";
const FIRST_KEY = "rz_lp_first_touch";
const LAST_KEY = "rz_lp_last_touch";
const VIEW_KEY = "rz_lp_view";

const UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"];
const CLICK_KEYS = ["gclid", "fbclid", "ttclid", "ctwa_clid", "wbraid", "gbraid", "msclkid"];

function readStore(store, key) {
  try {
    const raw = window[store].getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

function writeStore(store, key, value) {
  try {
    window[store].setItem(key, JSON.stringify(value));
  } catch (e) {
    /* storage diblokir (incognito) — pelacakan berkurang, halaman tetap jalan */
  }
}

/** Id pengunjung acak & stabil. Dipakai server untuk memilih varian A/B secara konsisten. */
export function visitorId() {
  let vid = null;
  try {
    vid = window.localStorage.getItem(VID_KEY);
  } catch (e) {
    vid = null;
  }
  if (!vid) {
    const rand = typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
    vid = rand;
    try {
      window.localStorage.setItem(VID_KEY, vid);
    } catch (e) {
      /* biarkan; per-kunjungan tetap berfungsi */
    }
  }
  return vid;
}

function paramsToTouch(search, landingPath) {
  const qs = new URLSearchParams(search || "");
  const touch = { landing_page: landingPath || "", referrer: document.referrer || "", ts: Date.now() };
  [...UTM_KEYS, ...CLICK_KEYS].forEach((k) => {
    const v = qs.get(k);
    if (v) touch[k] = String(v).slice(0, 200);
  });
  return touch;
}

function hasSignal(touch) {
  return [...UTM_KEYS, ...CLICK_KEYS].some((k) => touch && touch[k]);
}

/**
 * Catat sentuhan dari URL saat ini. Sentuhan pertama hanya ditulis sekali (first-touch),
 * sentuhan terakhir selalu diperbarui bila URL memuat sinyal iklan.
 */
export function captureTouch(landingPath) {
  const now = paramsToTouch(window.location.search, landingPath);
  const first = readStore("localStorage", FIRST_KEY);
  if (!first && hasSignal(now)) writeStore("localStorage", FIRST_KEY, now);
  if (hasSignal(now)) writeStore("sessionStorage", LAST_KEY, now);
  return now;
}

/** Bentuk payload atribusi untuk dikirim ke backend bersama lead. */
export function attributionPayload(landingPath) {
  const now = paramsToTouch(window.location.search, landingPath);
  const first = readStore("localStorage", FIRST_KEY) || (hasSignal(now) ? now : {});
  const last = readStore("sessionStorage", LAST_KEY) || now;
  return {
    first_touch: first,
    last_touch: last,
    landing_page: landingPath || "",
    referrer: document.referrer || "",
  };
}

/** Click-id mentah (TIDAK boleh di-hash di server — dipakai apa adanya oleh Meta/Google). */
export function clickIds() {
  const now = paramsToTouch(window.location.search);
  const first = readStore("localStorage", FIRST_KEY) || {};
  const out = {};
  CLICK_KEYS.forEach((k) => {
    const v = now[k] || first[k];
    if (v) out[k] = v;
  });
  return out;
}

/** Teruskan parameter iklan saat pindah ke halaman internal (mis. /quotation). */
export function withAttribution(target, extra) {
  const [path, ownQuery] = String(target || "/").split("?");
  const qs = new URLSearchParams(ownQuery || "");
  const current = new URLSearchParams(window.location.search || "");
  [...UTM_KEYS, ...CLICK_KEYS].forEach((k) => {
    const v = current.get(k);
    if (v && !qs.get(k)) qs.set(k, v);
  });
  Object.entries(extra || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  });
  const q = qs.toString();
  return q ? `${path}?${q}` : path;
}

/** Penanda agar satu kunjungan tidak menghitung tampilan berkali-kali saat refresh komponen. */
export function markViewOnce(slug, variantId) {
  const key = `${VIEW_KEY}:${slug}:${variantId || "A"}`;
  try {
    if (window.sessionStorage.getItem(key)) return false;
    window.sessionStorage.setItem(key, "1");
    return true;
  } catch (e) {
    return true; // storage diblokir → tetap catat (lebih baik sedikit berlebih daripada nol)
  }
}

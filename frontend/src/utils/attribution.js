// utils/attribution.js — E-ADS: tangkap UTM/click-id (first-touch + last-touch) di localStorage.
// Dipakai form publik (Quotation) untuk mengirim atribusi ke backend → channel CPL/CAC/ROAS.

const FIRST = "tf_attr_first";
const LAST = "tf_attr_last";
const PARAM_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid", "ttclid"];

function readParams() {
  try {
    const sp = new URLSearchParams(window.location.search);
    const out = {};
    PARAM_KEYS.forEach((k) => { const v = sp.get(k); if (v) out[k] = v; });
    return out;
  } catch { return {}; }
}

function hasSignal(obj) {
  return PARAM_KEYS.some((k) => obj[k]);
}

// Simpan first-touch (sekali) & last-touch (saat ada sinyal baru / belum ada). Aman dipanggil tiap route.
export function captureAttribution() {
  try {
    const params = readParams();
    const touch = {
      ...params,
      referrer: document.referrer || "",
      landing_page: (window.location.pathname || "") + (window.location.search || ""),
      ts: new Date().toISOString(),
    };
    if (!localStorage.getItem(FIRST)) {
      localStorage.setItem(FIRST, JSON.stringify(touch));
    }
    if (hasSignal(params) || !localStorage.getItem(LAST)) {
      localStorage.setItem(LAST, JSON.stringify(touch));
    }
  } catch { /* abaikan (private mode / SSR) */ }
}

// Ambil struktur atribusi untuk dikirim bersama form lead.
export function getAttribution() {
  captureAttribution();
  let first = {};
  let last = {};
  try { first = JSON.parse(localStorage.getItem(FIRST) || "{}"); } catch { first = {}; }
  try { last = JSON.parse(localStorage.getItem(LAST) || "{}"); } catch { last = {}; }
  return {
    first_touch: first,
    last_touch: last,
    landing_page: last.landing_page || first.landing_page || "",
    referrer: last.referrer || first.referrer || "",
  };
}

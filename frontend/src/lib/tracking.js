// lib/tracking.js — pelacakan iklan di SITUS PUBLIK: Meta Pixel + Google tag, gerbang CONSENT.
//
// Prinsip (mengikuti dokumentasi resmi Meta & Google, riset Agu 2026):
//  1. ID pixel/tag TIDAK di-hardcode: diambil runtime dari GET /api/public/tracking-config
//     (hanya ID publik; token tetap di server).
//  2. Consent Mode v2 (Google) di-set SEBELUM config, default DENIED; Meta Pixel & CAPI tidak
//     berjalan sebelum pengunjung menyetujui. Satu status persetujuan dipakai kedua platform.
//  3. `page_view` dikirim MANUAL sekali per perubahan URL (`send_page_view:false`) agar SPA tidak
//     menghitung ganda.
//  4. `event_id` memakai ID BISNIS yang sama dengan konversi server-side (Meta men-dedup
//     browser<->server dalam 48 jam).
import apiClient from "@/services/apiClient";

const CONSENT_KEY = "tf_tracking_consent"; // "granted" | "denied"
let cfg = null;
let metaLoaded = false;
let googleLoaded = false;
let lastPath = "";
const readyListeners = new Set();

/** Beri tahu UI (mis. banner consent) saat konfigurasi selesai dimuat / status berubah.
 *  Memakai notifikasi, BUKAN menebak waktu dengan setTimeout — dulu banner tak pernah muncul
 *  karena komponen membaca status sebelum fetch selesai. */
export function onTrackingReady(fn) {
  readyListeners.add(fn);
  if (cfg) fn(trackingStatus());
  return () => readyListeners.delete(fn);
}

function notifyReady() {
  readyListeners.forEach((fn) => {
    try { fn(trackingStatus()); } catch { /* jangan rusak render karena listener */ }
  });
}

export function getConsent() {
  try {
    return localStorage.getItem(CONSENT_KEY) || "";
  } catch {
    return "";
  }
}

export function hasConsent() {
  return getConsent() === "granted";
}

// PENTING: dataLayer WAJIB menerima objek `arguments` (pola resmi Google). Sempat memakai
// array biasa -> gtag.js mencatatnya sebagai entri KOSONG sehingga event page_view/konversi
// tidak pernah terkirim meski tampak "terpush".
function gtag() {
  if (typeof window === "undefined") return;
  window.dataLayer = window.dataLayer || [];
  // eslint-disable-next-line prefer-rest-params
  window.dataLayer.push(arguments);
}

function ensureGtagStub() {
  if (typeof window === "undefined") return;
  if (!window.gtag) window.gtag = gtag;
}

let consentDefaultsSet = false;

/** Consent Mode v2: WAJIB dipanggil sebelum tag Google dimuat (tepat sekali). */
function setConsentDefaults() {
  ensureGtagStub();
  if (consentDefaultsSet) return;
  consentDefaultsSet = true;
  gtag("consent", "default", {
    ad_storage: "denied", analytics_storage: "denied",
    ad_user_data: "denied", ad_personalization: "denied",
    wait_for_update: 500,
  });
}

function loadGoogle(g) {
  if (googleLoaded || !g?.enabled) return;
  const first = g.ga4_measurement_id || g.ads_conversion_id;
  if (!first) return;
  const s = document.createElement("script");
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${first}`;
  document.head.appendChild(s);
  ensureGtagStub();
  gtag("js", new Date());
  if (g.ga4_measurement_id) gtag("config", g.ga4_measurement_id, { send_page_view: false });
  if (g.ads_conversion_id) gtag("config", g.ads_conversion_id);
  googleLoaded = true;
}

function loadMeta(m) {
  if (metaLoaded || !m?.enabled || !m.pixel_id) return;
  if (!window.fbq) {
    const n = (...args) => {
      if (n.callMethod) n.callMethod.apply(n, args);
      else n.queue.push(args);
    };
    n.push = n; n.loaded = true; n.version = "2.0"; n.queue = [];
    window.fbq = n;
    const s = document.createElement("script");
    s.async = true;
    s.src = "https://connect.facebook.net/en_US/fbevents.js";
    document.head.appendChild(s);
  }
  window.fbq("init", m.pixel_id);
  metaLoaded = true;
}

function activate() {
  if (!cfg || !hasConsent()) return;
  loadMeta(cfg.meta);
  loadGoogle(cfg.google);
  gtag("consent", "update", {
    ad_storage: "granted", analytics_storage: "granted",
    ad_user_data: "granted", ad_personalization: "granted",
  });
}

/** Dipanggil sekali dari PublicLayout. Aman bila kredensial belum diisi (mode MOCK). */
export async function initTracking() {
  setConsentDefaults();
  if (cfg) return cfg;
  try {
    const { data } = await apiClient.get("/public/tracking-config");
    cfg = data || null;
  } catch {
    cfg = null; // situs publik TIDAK boleh rusak hanya karena pelacakan gagal dimuat
  }
  if (cfg && !cfg?.consent?.require_consent) {
    try { localStorage.setItem(CONSENT_KEY, "granted"); } catch { /* private mode */ }
  }
  activate();
  notifyReady();
  return cfg;
}

export function grantConsent() {
  try { localStorage.setItem(CONSENT_KEY, "granted"); } catch { /* private mode */ }
  activate();
  notifyReady();
  trackPageView(window.location.pathname + window.location.search, true);
}

export function denyConsent() {
  try { localStorage.setItem(CONSENT_KEY, "denied"); } catch { /* private mode */ }
  gtag("consent", "update", {
    ad_storage: "denied", analytics_storage: "denied",
    ad_user_data: "denied", ad_personalization: "denied",
  });
}

export function trackingStatus() {
  return {
    consent: getConsent(),
    meta: !!(cfg?.meta?.enabled), google: !!(cfg?.google?.enabled),
    requireConsent: cfg?.consent?.require_consent !== false,
    bannerEnabled: cfg?.consent?.banner_enabled !== false,
    bannerText: cfg?.consent?.banner_text || "",
    privacyUrl: cfg?.consent?.privacy_url || "/about",
    loaded: !!cfg,
  };
}

/** page_view manual: satu kali per URL (cegah hitung ganda di SPA). */
export function trackPageView(path, force = false) {
  if (!hasConsent()) return;
  if (!force && path === lastPath) return;
  lastPath = path;
  if (metaLoaded) window.fbq?.("track", "PageView");
  if (googleLoaded && cfg?.google?.ga4_measurement_id) {
    window.gtag?.("event", "page_view", {
      page_location: window.location.href, page_path: path, page_title: document.title,
    });
  }
}

const seenItems = new Set();

/** Lihat detail armada/destinasi (GA4 view_item + Meta ViewContent).
 *  Dijaga anti-ganda: React memanggil effect dua kali di mode dev, dan pengunjung bisa
 *  kembali ke halaman yang sama — keduanya tidak boleh menggandakan konversi. */
export function trackViewItem({ id, name, value = 0, category = "armada" }) {
  if (!hasConsent() || !id) return;
  const key = `${category}:${id}`;
  if (seenItems.has(key)) return;
  seenItems.add(key);
  if (metaLoaded) {
    window.fbq?.("track", "ViewContent", {
      content_ids: [id], content_name: name, content_type: "product",
      content_category: category, value: Number(value) || 0, currency: "IDR",
    });
  }
  if (googleLoaded) {
    window.gtag?.("event", "view_item", {
      currency: "IDR", value: Number(value) || 0,
      items: [{ item_id: id, item_name: name, item_category: category, price: Number(value) || 0, quantity: 1 }],
    });
  }
}

/** Mulai isi formulir pemesanan (begin_checkout / InitiateCheckout). */
export function trackBeginCheckout({ value = 0, items = [] } = {}) {
  if (!hasConsent()) return;
  if (metaLoaded) window.fbq?.("track", "InitiateCheckout", { value: Number(value) || 0, currency: "IDR" });
  if (googleLoaded) window.gtag?.("event", "begin_checkout", { currency: "IDR", value: Number(value) || 0, items });
}

/**
 * Lead terkirim. `eventKey` WAJIB sama dengan yang dipakai konversi server-side
 * (mis. "lead_<lead_id>") agar Meta men-dedup, bukan menghitung dua kali.
 */
export function trackLead({ eventKey, value = 0, source = "form" }) {
  if (!hasConsent()) return;
  if (metaLoaded) {
    window.fbq?.("track", "Lead", { content_name: source, value: Number(value) || 0, currency: "IDR" },
      eventKey ? { eventID: eventKey } : undefined);
  }
  if (googleLoaded) {
    window.gtag?.("event", "generate_lead", { currency: "IDR", value: Number(value) || 0, lead_id: eventKey || "" });
    const label = cfg?.google?.conversion_labels?.lead_submitted;
    if (label) {
      window.gtag?.("event", "conversion", {
        send_to: label, value: Number(value) || 0, currency: "IDR", transaction_id: eventKey || "",
      });
    }
  }
}

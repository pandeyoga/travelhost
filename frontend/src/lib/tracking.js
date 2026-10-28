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
//  5. Google Tag Manager & PostHog (2026-10-28) dulu ditempel di public/index.html → termuat di
//     SEMUA halaman (termasuk ERP /app & halaman bertoken /schedule/:token, /track/:token yang
//     URL-nya memuat token rahasia) dan SEBELUM pengunjung setuju. Kini dimuat dari sini:
//     hanya dari situs publik, hanya setelah consent, tidak pernah di rute privat. Event
//     konversi & page_view SPA ikut dikirim ke `dataLayer` agar bisa dipakai trigger GTM.
import apiClient from "@/services/apiClient";

const GTM_ID = (process.env.REACT_APP_GTM_ID ?? "GTM-M3CZCBPR").trim();
const POSTHOG_KEY = (process.env.REACT_APP_POSTHOG_KEY ?? "phc_xAvL2Iq4tFmANRE7kzbKwaSqp1HJjN7x48s3vr0CMjs").trim();
const POSTHOG_HOST = "https://us.i.posthog.com";
// Rute yang TIDAK boleh dilacak: ERP internal + halaman publik bertoken (token di URL = rahasia).
const PRIVATE_PREFIXES = ["/app", "/track/", "/schedule/", "/review/"];

const CONSENT_KEY = "tf_tracking_consent"; // "granted" | "denied"
let cfg = null;
let metaLoaded = false;
let googleLoaded = false;
let gtmLoaded = false;
let posthogLoaded = false;
let ctaInstalled = false;
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

/** True untuk ERP (/app) dan halaman bertoken — pelacakan pihak ketiga tidak dijalankan di sana. */
export function isPrivatePath(pathname = "", search = "") {
  const p = String(pathname || "");
  if (PRIVATE_PREFIXES.some((x) => (x.endsWith("/") ? p.startsWith(x) : p === x || p.startsWith(`${x}/`)))) return true;
  return /[?&]token=/.test(String(search || ""));
}

const onPrivatePage = () => typeof window === "undefined"
  || isPrivatePath(window.location.pathname, window.location.search);

/** Event untuk trigger GTM (objek `{event: ...}` — format yang dibaca GTM, beda dari gtag()). */
function dlPush(obj) {
  if (!gtmLoaded || typeof window === "undefined") return;
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push(obj);
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

function loadGtm() {
  if (gtmLoaded || !GTM_ID || onPrivatePage()) return;
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push({ "gtm.start": Date.now(), event: "gtm.js" });
  const s = document.createElement("script");
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtm.js?id=${encodeURIComponent(GTM_ID)}`;
  document.head.appendChild(s);
  gtmLoaded = true;
}

function loadPosthog() {
  if (!POSTHOG_KEY || onPrivatePage()) return;
  if (posthogLoaded) { window.posthog?.opt_in_capturing?.(); return; }
  /* eslint-disable */
  // Snippet resmi PostHog (dipindah apa adanya dari public/index.html).
  !(function (t, e) { var o, n, p, r; e.__SV || ((window.posthog = e), (e._i = []), (e.init = function (i, s, a) { function g(t, e) { var o = e.split("."); 2 == o.length && ((t = t[o[0]]), (e = o[1])), (t[e] = function () { t.push([e].concat(Array.prototype.slice.call(arguments, 0))); }); } ((p = t.createElement("script")).type = "text/javascript"), (p.crossOrigin = "anonymous"), (p.async = !0), (p.src = s.api_host.replace(".i.posthog.com", "-assets.i.posthog.com") + "/static/array.js"), (r = t.getElementsByTagName("script")[0]).parentNode.insertBefore(p, r); var u = e; for (void 0 !== a ? (u = e[a] = []) : (a = "posthog"), u.people = u.people || [], u.toString = function (t) { var e = "posthog"; return "posthog" !== a && (e += "." + a), t || (e += " (stub)"), e; }, u.people.toString = function () { return u.toString(1) + ".people (stub)"; }, o = "init capture register register_once unregister identify alias reset opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing set_config startSessionRecording stopSessionRecording get_distinct_id getFeatureFlag isFeatureEnabled onFeatureFlags reloadFeatureFlags group".split(" "), n = 0; n < o.length; n++) g(u, o[n]); e._i.push([i, s, a]); }), (e.__SV = 1)); })(document, window.posthog || []);
  /* eslint-enable */
  window.posthog.init(POSTHOG_KEY, {
    api_host: POSTHOG_HOST,
    person_profiles: "identified_only",
    // page_view dikirim manual per perubahan URL (trackPageView) — SPA tidak dihitung ganda.
    capture_pageview: false,
    session_recording: { recordCrossOriginIframes: true, capturePerformance: false },
  });
  posthogLoaded = true;
}

/** Klik tombol konversi di mana pun di situs publik → `cta_click` (tanpa menyentuh tiap komponen). */
function ctaKind(href) {
  const h = String(href || "");
  if (/^\/quotation|\/booking\/permintaan/.test(h)) return "quotation";
  if (/^\/booking(\?|$|\/?$)/.test(h)) return "booking";
  if (/wa\.me|api\.whatsapp\.com|whatsapp:/.test(h)) return "whatsapp";
  if (/^tel:/.test(h)) return "phone";
  return "";
}

function installCtaTracking() {
  if (ctaInstalled || typeof document === "undefined") return;
  ctaInstalled = true;
  document.addEventListener("click", (e) => {
    if (!gtmLoaded || onPrivatePage()) return;
    const a = e.target?.closest?.("a[href]");
    if (!a) return;
    const raw = a.getAttribute("href") || "";
    const kind = ctaKind(raw.startsWith("http") && raw.includes(window.location.host) ? new URL(raw).pathname : raw);
    if (!kind) return;
    dlPush({
      event: "cta_click", cta_type: kind, cta_text: (a.textContent || "").trim().slice(0, 80),
      page_path: window.location.pathname,
    });
  }, true);
}

function activate() {
  if (!cfg || !hasConsent() || onPrivatePage()) return;
  gtag("consent", "update", {
    ad_storage: "granted", analytics_storage: "granted",
    ad_user_data: "granted", ad_personalization: "granted",
  });
  loadMeta(cfg.meta);
  loadGoogle(cfg.google);
  loadGtm();
  loadPosthog();
  installCtaTracking();
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
  // Pengunjung yang SUDAH setuju sebelumnya: page_view halaman pertama dulu hilang karena
  // trackPageView() jalan sebelum tag termuat (konfigurasi diambil async). Kirim ulang di sini.
  if (hasConsent() && !onPrivatePage()) trackPageView(window.location.pathname + window.location.search, true);
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
  window.posthog?.opt_out_capturing?.();
  gtag("consent", "update", {
    ad_storage: "denied", analytics_storage: "denied",
    ad_user_data: "denied", ad_personalization: "denied",
  });
}

export function trackingStatus() {
  return {
    consent: getConsent(),
    meta: !!(cfg?.meta?.enabled), google: !!(cfg?.google?.enabled),
    gtm: Boolean(GTM_ID), posthog: Boolean(POSTHOG_KEY),
    requireConsent: cfg?.consent?.require_consent !== false,
    bannerEnabled: cfg?.consent?.banner_enabled !== false,
    bannerText: cfg?.consent?.banner_text || "",
    privacyUrl: cfg?.consent?.privacy_url || "/about",
    loaded: !!cfg,
  };
}

/** page_view manual: satu kali per URL (cegah hitung ganda di SPA). */
export function trackPageView(path, force = false) {
  const [pathname, query] = String(path || "").split("?");
  if (!hasConsent() || isPrivatePath(pathname, query ? `?${query}` : "")) return;
  if (!force && path === lastPath) return;
  lastPath = path;
  if (metaLoaded) window.fbq?.("track", "PageView");
  if (googleLoaded && cfg?.google?.ga4_measurement_id) {
    window.gtag?.("event", "page_view", {
      page_location: window.location.href, page_path: path, page_title: document.title,
    });
  }
  dlPush({ event: "page_view", page_path: path, page_location: window.location.href, page_title: document.title });
  if (posthogLoaded) window.posthog?.capture?.("$pageview");
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
  const items = [{ item_id: id, item_name: name, item_category: category, price: Number(value) || 0, quantity: 1 }];
  if (googleLoaded) {
    window.gtag?.("event", "view_item", { currency: "IDR", value: Number(value) || 0, items });
  }
  dlPush({ ecommerce: null });
  dlPush({ event: "view_item", ecommerce: { currency: "IDR", value: Number(value) || 0, items } });
}

/** Mulai isi formulir pemesanan (begin_checkout / InitiateCheckout). */
export function trackBeginCheckout({ value = 0, items = [] } = {}) {
  if (!hasConsent()) return;
  if (metaLoaded) window.fbq?.("track", "InitiateCheckout", { value: Number(value) || 0, currency: "IDR" });
  if (googleLoaded) window.gtag?.("event", "begin_checkout", { currency: "IDR", value: Number(value) || 0, items });
  dlPush({ ecommerce: null });
  dlPush({ event: "begin_checkout", ecommerce: { currency: "IDR", value: Number(value) || 0, items } });
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
  dlPush({ event: "generate_lead", lead_id: eventKey || "", lead_source: source, value: Number(value) || 0, currency: "IDR" });
}

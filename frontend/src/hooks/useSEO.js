/**
 * hooks/useSEO.js — CMS-02 SEO Toolkit
 *
 * Hook ringan untuk inject metadata SEO ke <head> tanpa dependency berat
 * (mis. react-helmet). Menerima objek { title, description, image, url, type,
 * canonical, jsonLd, keywords } dan meng-upsert tag secara idempoten.
 *
 * Prinsip:
 * - Hook aman untuk SSR/SPA (guard `typeof document`).
 * - Cleanup otomatis saat komponen unmount (menghapus tag yang ditambahkan
 *   hook ini agar tidak menumpuk saat navigasi antar halaman).
 * - JSON-LD ditulis sebagai <script type="application/ld+json"> — Google
 *   parses schema.org secara reliable dgn format ini.
 *
 * Pemakaian:
 *   useSEO({
 *     title: "Bali - RahazaTrans",
 *     description: "Wisata Bali dengan armada premium...",
 *     image: "https://.../hero.jpg",
 *     canonical: "https://rahazatrans.id/destinations/bali",
 *     jsonLd: { "@context": "https://schema.org", "@type": "TouristAttraction", ... }
 *   });
 */
import { useEffect } from "react";
import { useLangValue } from "@/hooks/useLang";
import { DEFAULT_LANG, LANGS, langMeta } from "@/lib/lang";

const DEFAULT_SITE = "RahazaTrans";
const DEFAULT_DESC = "Rental armada premium & paket wisata Jawa–Bali dengan pendamping profesional.";
const DATA_ATTR = "data-seo-managed"; // penanda tag yang di-manage hook
const ALT_ATTR = "data-seo-alt";      // penanda link hreflang (dibersihkan tiap halaman)

function upsertMeta(selector, attrs) {
  if (typeof document === "undefined") return null;
  let el = document.head.querySelector(selector);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(DATA_ATTR, "1");
    for (const [k, v] of Object.entries(attrs)) {
      if (k !== "content") el.setAttribute(k, v);
    }
    document.head.appendChild(el);
  }
  if (attrs.content != null) el.setAttribute("content", attrs.content);
  return el;
}

function upsertLink(rel, href) {
  if (typeof document === "undefined") return null;
  let el = document.head.querySelector(`link[rel="${rel}"]`);
  if (!el) {
    el = document.createElement("link");
    el.setAttribute("rel", rel);
    el.setAttribute(DATA_ATTR, "1");
    document.head.appendChild(el);
  }
  el.setAttribute("href", href);
  return el;
}

function upsertJsonLd(json) {
  if (typeof document === "undefined") return null;
  // ID stabil supaya bisa update tanpa duplikasi.
  const ID = "seo-jsonld-managed";
  let el = document.getElementById(ID);
  if (!el) {
    el = document.createElement("script");
    el.type = "application/ld+json";
    el.id = ID;
    el.setAttribute(DATA_ATTR, "1");
    document.head.appendChild(el);
  }
  try {
    el.textContent = JSON.stringify(json);
  } catch {
    /* ignore serialization errors */
  }
  return el;
}

/**
 * CMS-06 — tautan `hreflang` untuk halaman publik dua bahasa.
 *
 * Kenapa penting: konten English disimpan di dokumen yang SAMA dan disajikan lewat `?lang=en`.
 * Tanpa `hreflang`, mesin pencari melihat dua URL berisi teks berbeda tanpa hubungan resmi →
 * versi English praktis tak pernah muncul untuk pencari berbahasa Inggris (dan bisa dinilai
 * duplikat). `x-default` menunjuk versi Indonesia sebagai tujuan bawaan.
 *
 * Alternate SELALU dibersihkan lebih dulu supaya halaman yang menonaktifkan i18n
 * (mis. halaman iklan `/lp/:slug`) tidak mewarisi tag dari halaman sebelumnya.
 */
function syncAlternates(enabled) {
  if (typeof document === "undefined") return;
  document.head.querySelectorAll(`link[${ALT_ATTR}]`).forEach((el) => el.remove());
  if (!enabled || typeof window === "undefined") return;
  let base;
  try {
    const url = new URL(window.location.href);
    url.searchParams.delete("lang");
    base = url.toString();
  } catch {
    return;
  }
  const hrefFor = (code) => {
    try {
      const u = new URL(base);
      if (code !== DEFAULT_LANG) u.searchParams.set("lang", code);
      return u.toString();
    } catch {
      return base;
    }
  };
  const rows = [
    ...LANGS.map((l) => [l.code, hrefFor(l.code)]),
    ["x-default", base],
  ];
  for (const [hreflang, href] of rows) {
    const el = document.createElement("link");
    el.setAttribute("rel", "alternate");
    el.setAttribute("hreflang", hreflang);
    el.setAttribute("href", href);
    el.setAttribute(ALT_ATTR, "1");
    el.setAttribute(DATA_ATTR, "1");
    document.head.appendChild(el);
  }
}

/**
 * @param {object} opts
 * @param {string} [opts.title]        Title tag & og:title
 * @param {string} [opts.description]  meta[name=description] & og:description
 * @param {string} [opts.image]        og:image & twitter:image (absolute URL preferred)
 * @param {string} [opts.url]          og:url (default: window.location.href)
 * @param {string} [opts.type]         og:type (default: "website"; "article" utk artikel)
 * @param {string} [opts.canonical]    <link rel="canonical"> (default: url)
 * @param {string} [opts.keywords]     meta[name=keywords] (opsional)
 * @param {object} [opts.jsonLd]       Objek schema.org (Article/TouristAttraction/Product/dll.)
 * @param {string} [opts.siteName]     og:site_name (default "RahazaTrans")
 * @param {boolean} [opts.i18n]        Set `false` untuk halaman tanpa versi bahasa lain
 *                                     (mis. `/lp/:slug` halaman iklan) — hreflang dilewati.
 */
export default function useSEO(opts = {}) {
  const lang = useLangValue();
  useEffect(() => {
    if (typeof document === "undefined") return;
    const {
      title,
      description = DEFAULT_DESC,
      image,
      url,
      type = "website",
      canonical,
      keywords,
      jsonLd,
      siteName = DEFAULT_SITE,
      i18n = true,
    } = opts || {};

    const pageUrl = url || (typeof window !== "undefined" ? window.location.href : "");
    const fullTitle = title ? (title.includes(siteName) ? title : `${title} · ${siteName}`) : siteName;

    // Set document.title (baca oleh browser tab & mesin pencari)
    const prevTitle = document.title;
    document.title = fullTitle;

    // Basic meta
    upsertMeta('meta[name="description"]', { name: "description", content: description });
    if (keywords) upsertMeta('meta[name="keywords"]', { name: "keywords", content: keywords });

    // Open Graph
    upsertMeta('meta[property="og:title"]', { property: "og:title", content: fullTitle });
    upsertMeta('meta[property="og:description"]', { property: "og:description", content: description });
    upsertMeta('meta[property="og:type"]', { property: "og:type", content: type });
    upsertMeta('meta[property="og:site_name"]', { property: "og:site_name", content: siteName });
    if (pageUrl) upsertMeta('meta[property="og:url"]', { property: "og:url", content: pageUrl });
    if (image) upsertMeta('meta[property="og:image"]', { property: "og:image", content: image });

    // Twitter Card
    upsertMeta('meta[name="twitter:card"]', { name: "twitter:card", content: image ? "summary_large_image" : "summary" });
    upsertMeta('meta[name="twitter:title"]', { name: "twitter:title", content: fullTitle });
    upsertMeta('meta[name="twitter:description"]', { name: "twitter:description", content: description });
    if (image) upsertMeta('meta[name="twitter:image"]', { name: "twitter:image", content: image });

    // Canonical link
    if (canonical || pageUrl) upsertLink("canonical", canonical || pageUrl);

    // CMS-06 — bahasa halaman: `og:locale` dipakai pratinjau media sosial, `hreflang`
    // dipakai mesin pencari untuk memilih versi bahasa yang benar bagi pengunjung.
    const meta = langMeta(lang);
    upsertMeta('meta[property="og:locale"]', { property: "og:locale", content: meta.locale });
    const other = LANGS.find((l) => l.code !== lang);
    if (other) {
      upsertMeta('meta[property="og:locale:alternate"]',
        { property: "og:locale:alternate", content: other.locale });
    }
    syncAlternates(i18n);

    // JSON-LD
    if (jsonLd) upsertJsonLd(jsonLd);

    // Cleanup: restore title bila komponen unmount. Meta tag dibiarkan (akan
    // di-upsert oleh halaman berikutnya). Untuk menghindari nilai basi, halaman
    // dgn `useSEO` idealnya SEMUA halaman publik utama.
    return () => {
      document.title = prevTitle;
    };
  }, [
    opts?.title,
    opts?.description,
    opts?.image,
    opts?.url,
    opts?.type,
    opts?.canonical,
    opts?.keywords,
    opts?.i18n,
    lang,
    // JSON stringify supaya reactive ke perubahan objek jsonLd
    opts?.jsonLd ? JSON.stringify(opts.jsonLd) : null,
  ]);
}

/** Utility: bangun URL absolut dari path relatif memakai window.location.origin. */
export function absUrl(path) {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  if (typeof window === "undefined") return path;
  const origin = window.location.origin.replace(/\/$/, "");
  return `${origin}${path.startsWith("/") ? "" : "/"}${path}`;
}

/** Utility: bersihkan HTML dari string (utk meta description dari body artikel). */
export function stripHtml(s, max = 160) {
  if (!s) return "";
  const clean = String(s).replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  return clean.length > max ? clean.slice(0, max - 1).trimEnd() + "…" : clean;
}

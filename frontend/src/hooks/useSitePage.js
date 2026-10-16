import { useEffect, useState } from "react";
import apiClient from "@/services/apiClient";

// Page builder situs: ambil urutan + override section dari CMS.
// Gagal fetch / kosong → fallback urutan bawaan agar halaman TIDAK pernah blank.
const DEFAULT_ORDER = {
  home: ["hero", "booking_steps", "value_props", "stats_band", "fleet_featured",
    "destinations_featured", "testimonials", "gallery", "trust", "faq", "cta_band"],
  about: ["page_hero", "stat_cards", "about_story"],
  contact: ["page_hero", "contact_channels", "contact_cta"],
  fleet: ["page_hero"], destinations: ["page_hero"], packages: ["page_hero"],
  promo: ["page_hero"], blog: ["page_hero"], "trip-calculator": ["page_hero"],
};

// Mode pratinjau Page Builder: halaman dimuat di dalam IFRAME editor (/app/cms → Halaman)
// dengan ?pbPreview=1. Section datang dari draft editor (postMessage), BUKAN dari API.
export const isBuilderPreview = () =>
  typeof window !== "undefined" &&
  new URLSearchParams(window.location.search).get("pbPreview") === "1";

// Origin editor (parent) — dikirim lewat ?pbOrigin= karena situs publik & ERP bisa beda domain.
export const builderOrigin = () => {
  const o = new URLSearchParams(window.location.search).get("pbOrigin");
  try { return o ? new URL(o).origin : window.location.origin; } catch { return window.location.origin; }
};

export function ov(d, key, fallback) {
  const v = d && d[key];
  return (typeof v === "string" && v.trim()) || (Array.isArray(v) && v.length) ? v : fallback;
}

export default function useSitePage(slug) {
  return useSitePageState(slug).sections;
}

// Varian dengan status loading — utk halaman yang ingin menampilkan skeleton
// selagi override CMS dimuat (hindari "flash" teks bawaan → teks override).
export function useSitePageState(slug) {
  const [sections, setSections] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isBuilderPreview()) return undefined; // draft datang dari editor, bukan API
    let alive = true;
    setLoading(true);
    apiClient.get(`/public/pages/${slug}`)
      .then((r) => {
        if (!alive) return;
        const rows = Array.isArray(r.data?.sections) ? r.data.sections : [];
        setSections(rows.length ? rows : null);
      })
      .catch(() => {})
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [slug]);

  // Jembatan pratinjau: terima draft dari editor + blokir navigasi tautan di dalam iframe.
  useEffect(() => {
    if (!isBuilderPreview()) return undefined;
    const origin = builderOrigin();
    const onMsg = (e) => {
      if (e.origin !== origin) return;
      const m = e.data;
      if (m && m.__pb && m.type === "sections" && m.slug === slug) {
        const rows = (Array.isArray(m.sections) ? m.sections : []).filter((r) => r.enabled);
        setSections(rows);
        setLoading(false);
      }
    };
    const blockNav = (e) => {
      const a = e.target && e.target.closest && e.target.closest("a");
      if (a) e.preventDefault();
    };
    window.addEventListener("message", onMsg);
    document.addEventListener("click", blockNav, true);
    window.parent.postMessage({ __pb: true, type: "ready", slug }, origin);
    return () => {
      window.removeEventListener("message", onMsg);
      document.removeEventListener("click", blockNav, true);
    };
  }, [slug]);

  const fallback = (DEFAULT_ORDER[slug] || []).map((type) => ({ id: type, type, data: {} }));
  return { sections: sections || fallback, loading };
}

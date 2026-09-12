import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import LandingRender from "@/components/app/landing/LandingRender";
import { attributionPayload, captureTouch, clickIds, markViewOnce, visitorId, withAttribution }
  from "@/lib/lpAttribution";
import { trackViewItem } from "@/lib/tracking";
import useSEO from "@/hooks/useSEO";

/**
 * LandingPage.jsx — halaman iklan publik `/lp/:slug`.
 *
 * Memakai renderer yang SAMA dengan pratinjau editor. Tiga hal yang membuat halaman ini
 * berbeda dari halaman marketing biasa:
 *  1. **Atribusi tidak boleh hilang.** Parameter iklan (utm/gclid/fbclid/ctwa_clid) disimpan
 *     saat mendarat, dikirim bersama lead, dan diteruskan ke tujuan CTA internal — kalau tidak,
 *     lead tidak bisa dihubungkan ke iklan yang membayarnya dan laporan ROAS jadi bohong.
 *  2. **Varian uji A/B** dipilih server berdasarkan id pengunjung (`vid`) agar refresh tidak
 *     mengubah tampilan; tampilan & klik dilaporkan per varian.
 *  3. **Lead dikirim di tempat** (tanpa pindah halaman) lewat endpoint publik khusus halaman ini.
 */
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function LandingPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [page, setPage] = useState(null);
  const [refs, setRefs] = useState({ fleet: [], destinations: [], routes: [], testimonials: [] });
  const [refsLoading, setRefsLoading] = useState(true);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const landingPath = `/lp/${slug}`;
  const variantId = page?.variant?.id || "A";

  const load = useCallback(() => {
    setLoading(true);
    setNotFound(false);
    captureTouch(landingPath);
    const vid = visitorId();
    const forced = new URLSearchParams(window.location.search).get("variant") || "";
    const q = `vid=${encodeURIComponent(vid)}${forced ? `&variant=${encodeURIComponent(forced)}` : ""}`;
    axios.get(`${API}/public/landing/${slug}?${q}`)
      .then((r) => setPage(r.data))
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));

    setRefsLoading(true);
    Promise.all([
      axios.get(`${API}/public/fleet`).then((r) => r.data).catch(() => []),
      axios.get(`${API}/public/destinations`).then((r) => r.data).catch(() => []),
      axios.get(`${API}/public/booking/config`).then((r) => r.data).catch(() => ({})),
      axios.get(`${API}/public/testimonials`).then((r) => r.data).catch(() => []),
    ]).then(([fleet, dest, cfg, testi]) => {
      const arr = (v) => (Array.isArray(v) ? v : v?.items || []);
      setRefs({ fleet: arr(fleet), destinations: arr(dest),
        routes: Array.isArray(cfg?.routes) ? cfg.routes : [], testimonials: arr(testi) });
    }).finally(() => setRefsLoading(false));
  }, [slug, landingPath]);
  useEffect(load, [load]);

  // Catat tampilan sekali per kunjungan (statistik A/B) + pelacakan pixel yang sudah ada.
  useEffect(() => {
    if (!page?.slug) return;
    if (markViewOnce(page.slug, variantId)) {
      axios.post(`${API}/public/landing/${page.slug}/track`,
        { type: "view", variant_id: variantId }).catch(() => {});
    }
    try {
      trackViewItem({ id: page.slug, name: page.title, value: 0, category: page.segment || "armada" });
    } catch (e) {
      /* pelacakan tidak boleh menggagalkan render halaman */
    }
  }, [page?.slug, page?.title, page?.segment, variantId]);

  const seo = useMemo(() => {
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    const hero = (page?.blocks || []).find((b) => ["search_hero", "hero_media"].includes(b.type));
    const heroImg = hero?.props?.media?.src || "";
    const img = page?.seo?.og_image || (heroImg && heroImg.startsWith("/") ? `${origin}${heroImg}` : heroImg);
    return {
      title: page?.seo?.title || page?.title || "RahazaTrans",
      description: page?.seo?.description || "",
      image: img || "",
      type: "website",
      // Halaman iklan TIDAK punya versi bahasa lain — hreflang di sini hanya akan mengarahkan
      // mesin pencari ke URL `?lang=en` yang isinya sama (duplikat), jadi i18n dimatikan.
      i18n: false,
      // Canonical WAJIB menunjuk alamat halaman TANPA parameter iklan: tanpa ini setiap variasi
      // utm/gclid dianggap URL berbeda oleh mesin pencari (duplikat konten) dan sinyal SEO terpecah.
      canonical: origin ? `${origin}${landingPath}` : "",
      jsonLd: page ? {
        "@context": "https://schema.org",
        "@type": "Service",
        name: page.title,
        description: page?.seo?.description || "",
        provider: { "@type": "LocalBusiness", name: "RahazaTrans" },
        areaServed: "Indonesia",
        url: origin ? `${origin}${landingPath}` : undefined,
        image: img || undefined,
      } : null,
    };
  }, [page, landingPath]);
  useSEO(seo);

  // Halaman iklan default `noindex`: halaman berbayar tidak boleh berebut kata kunci dengan
  // halaman SEO utama, dan halaman promo kedaluwarsa yang ter-index merusak kesan merek.
  // Bisa dimatikan per halaman dari panel SEO di editor.
  useEffect(() => {
    if (!page) return undefined;
    const noindex = page?.seo?.noindex !== false;
    let tag = document.head.querySelector('meta[name="robots"][data-lp="1"]');
    if (!tag) {
      tag = document.createElement("meta");
      tag.setAttribute("name", "robots");
      tag.setAttribute("data-lp", "1");
      document.head.appendChild(tag);
    }
    tag.setAttribute("content", noindex ? "noindex, nofollow" : "index, follow");
    return () => { tag?.remove(); };
  }, [page]);

  const trackClick = (label) => {
    if (!page?.slug) return;
    axios.post(`${API}/public/landing/${page.slug}/track`,
      { type: "cta_click", variant_id: variantId, label: String(label || "").slice(0, 60) }).catch(() => {});
  };

  const onCta = (cta) => {
    trackClick(cta?.label);
    const target = cta?.target || "/quotation";
    if (cta?.kind === "whatsapp") {
      const text = encodeURIComponent(cta.message || `Halo, saya dari halaman ${page?.title || "iklan"}.`);
      const phone = String(cta.target || "").replace(/\D/g, "");
      window.open(phone ? `https://wa.me/${phone}?text=${text}` : `https://wa.me/?text=${text}`,
        "_blank", "noopener");
      return;
    }
    if (cta?.kind === "anchor") {
      const el = document.getElementById(String(target).replace(/^#/, ""));
      if (el) el.scrollIntoView({ behavior: "smooth" });
      return;
    }
    if (/^https?:/i.test(target)) {
      window.open(target, "_blank", "noopener");
      return;
    }
    navigate(cta?.keep_attribution === false ? target : withAttribution(target, { lp: slug }));
  };

  const onSearch = (values, tab, cta) => {
    trackClick(cta?.label || "pencarian");
    const target = tab?.target || cta?.target || "/quotation";
    if (/^https?:/i.test(target)) {
      window.open(target, "_blank", "noopener");
      return;
    }
    navigate(withAttribution(target, { ...values, lp: slug }));
  };

  const onLeadSubmit = async (values, blockId) => {
    const payload = {
      ...values,
      pax: values.pax ? Number(values.pax) : 0,
      attribution: attributionPayload(landingPath),
      click_ids: clickIds(),
      variant_id: variantId,
      block_id: blockId || "",
      idempotency_key: `${visitorId()}-${blockId || "form"}`,
    };
    const { data } = await axios.post(`${API}/public/landing/${slug}/lead`, payload);
    trackClick("lead_terkirim");
    return data;
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-[1120px] space-y-3 p-8" data-testid="lp-public-loading">
        {[0, 1, 2].map((i) => <div key={i} className="h-28 animate-pulse rounded-xl bg-[#EEF1F5]" />)}
      </div>
    );
  }
  if (notFound || !page) {
    return (
      <div className="p-16 text-center" data-testid="lp-public-404">
        <h1 className="text-[22px] font-extrabold text-[#1C1C1E]">Halaman tidak ditemukan</h1>
        <p className="mt-2 text-[13.5px] text-[#6B6B73]">
          Halaman iklan ini belum diterbitkan atau alamatnya salah.
        </p>
        <button type="button" onClick={() => navigate("/")} data-testid="lp-public-home"
          className="mt-4 rounded-lg bg-[#0B7BD3] px-4 py-2 text-[13px] font-bold text-white">
          Ke halaman utama
        </button>
      </div>
    );
  }

  return (
    <div data-surface="public" data-testid="lp-public" data-variant={variantId}>
      <LandingRender page={page} mode="public" fleet={refs.fleet} destinations={refs.destinations}
        routes={refs.routes} testimonials={refs.testimonials} refsLoading={refsLoading}
        onCta={onCta} onSearch={onSearch} onLeadSubmit={onLeadSubmit} />
    </div>
  );
}

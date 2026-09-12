import { useResource } from "@/hooks/useResource";
import useSEO, { absUrl } from "@/hooks/useSEO";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";
import useSitePage, { ov } from "@/hooks/useSitePage";
import BuilderSection from "@/components/public/BuilderSection";
import { HOME_SECTIONS, HOME_HERO_DEFAULT } from "@/components/public/HomeSections";

// Beranda dirakit dari CMS Page Builder (/app/cms → Halaman Situs): urutan section,
// aktif/nonaktif, dan override teks/gambar datang dari /api/public/pages/home.
export default function Home() {
  const lang = useLangValue();
  const sections = useSitePage("home");
  const { data: fleet, loading: fleetLoading } = useResource("/public/fleet");
  const { data: destinations, loading: destLoading } = useResource("/public/destinations");
  const { data: testimonials } = useResource("/public/testimonials");
  const { data: statsData, loading: statsLoading } = useResource("/public/stats");

  const destAll = Array.isArray(destinations) ? destinations : [];
  const dyn = {
    fleetRows: (Array.isArray(fleet) ? fleet : []).slice(0, 3),
    fleetLoading,
    destRows: (destAll.filter((d) => d.popular).length ? destAll.filter((d) => d.popular) : destAll).slice(0, 3),
    destLoading,
    tRows: Array.isArray(testimonials) ? testimonials : [],
    stats: Array.isArray(statsData?.stats) ? statsData.stats : [],
    statsLoading,
  };

  const heroData = (sections.find((s) => s.type === "hero") || {}).data || {};
  const heroImage = ov(heroData, "image", HOME_HERO_DEFAULT);

  // CMS-02 SEO: meta dasar + Organization JSON-LD (identitas brand utk mesin pencari).
  useSEO({
    title: bi("RahazaTrans — Rental Armada Premium & Paket Wisata Jawa–Bali",
              "RahazaTrans — Premium Vehicle Rental & Java–Bali Tour Packages", lang),
    description: bi("Sewa Hiace Premio & armada premium dengan driver profesional. Paket wisata Jawa–Bali, harga transparan, pelacakan real-time, dan layanan responsif.",
                    "Hiace Premio & premium vehicle rental with professional drivers. Java–Bali tour packages, transparent pricing, real-time tracking and responsive service.", lang),
    image: heroImage,
    keywords: "sewa hiace, rental armada premium, paket wisata jawa bali, sewa mobil bandung, travel bandung",
    jsonLd: {
      "@context": "https://schema.org",
      "@type": "Organization",
      name: "RahazaTrans",
      url: absUrl("/"),
      logo: absUrl("/logo.png"),
      image: heroImage,
      description: "Rental armada premium & paket wisata Jawa–Bali dengan pendamping profesional.",
      email: "halo@rahazatrans.id",
      telephone: "+62-811-2000-300",
      address: {
        "@type": "PostalAddress",
        streetAddress: "Jl. Asia Afrika No. 1",
        addressLocality: "Bandung",
        addressRegion: "Jawa Barat",
        addressCountry: "ID",
      },
      contactPoint: {
        "@type": "ContactPoint",
        telephone: "+62-811-2000-300",
        contactType: "customer service",
        areaServed: "ID",
        availableLanguage: ["id", "en"],
      },
      sameAs: [
        "https://www.instagram.com/rahazatrans",
        "https://www.facebook.com/rahazatrans",
      ],
    },
  });

  return (
    <div>
      {sections.length === 0 ? null : sections.map((s) => {
        const Section = HOME_SECTIONS[s.type];
        if (!Section) return null;
        return (
          <BuilderSection key={s.id} sec={s}>
            <Section lang={lang} d={s.data || {}} dyn={dyn} />
          </BuilderSection>
        );
      })}
    </div>
  );
}

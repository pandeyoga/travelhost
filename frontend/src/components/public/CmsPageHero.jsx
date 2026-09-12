import PageHero from "@/components/public/PageHero";
import BuilderSection from "@/components/public/BuilderSection";
import { ov, useSitePageState } from "@/hooks/useSitePage";

// PageHero yang bisa di-override dari CMS Page Builder (section `page_hero` per slug halaman).
// Field kosong = teks/gambar bawaan dua-bahasa tetap dipakai.
export default function CmsPageHero({ slug, eyebrow, title, subtitle, image, ...rest }) {
  const { sections } = useSitePageState(slug);
  const sec = sections.find((s) => s.type === "page_hero");
  const d = (sec || {}).data || {};
  return (
    <BuilderSection sec={sec || { id: "page_hero" }}>
      <PageHero eyebrow={ov(d, "eyebrow", eyebrow)} title={ov(d, "title", title)}
        subtitle={ov(d, "subtitle", subtitle)} image={ov(d, "image", image)} {...rest} />
    </BuilderSection>
  );
}

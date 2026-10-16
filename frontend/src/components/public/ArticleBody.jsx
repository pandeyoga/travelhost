import { looksLikeHtml } from "@/components/cms/RichTextEditor";

/**
 * ArticleBody — CMS-09: menampilkan isi artikel dengan AMAN.
 *
 * Dua format hidup bersama, dan itu memang disengaja:
 *  1. **HTML kaya** (artikel baru dari editor CMS). Sudah dibersihkan SERVER dengan allowlist
 *     ketat (`services/richtext.sanitize`) sebelum tersimpan, jadi yang sampai ke sini tidak
 *     mungkin memuat `<script>`, `onerror=`, `javascript:`, `<iframe>`, atau atribut `style`.
 *     Karena itu `dangerouslySetInnerHTML` di sini SAH: sumbernya sudah tersanitasi di pagar
 *     yang tak bisa dilewati klien (bahkan lewat curl).
 *  2. **Teks polos** (artikel lama sebelum CMS-09). Tetap dirender sebagai paragraf +
 *     drop-cap seperti sebelumnya — konten lama tidak boleh berubah tampilannya hanya karena
 *     kita mengganti editor.
 *
 * Gaya tipografi diatur kelas `.article-prose` (index.css) memakai token tema, sehingga
 * artikel ikut mode terang/gelap & preset warna situs.
 */
export default function ArticleBody({ body, testId = "article-body" }) {
  const raw = String(body || "");

  if (looksLikeHtml(raw)) {
    return (
      <div className="article-prose mt-6 text-[16px] leading-[1.85] text-foreground/85"
        data-testid={`${testId}-html`}
        // eslint-disable-next-line react/no-danger -- HTML sudah disanitasi server (allowlist ketat)
        dangerouslySetInnerHTML={{ __html: raw }} />
    );
  }

  const paragraphs = raw.split(/\n{2,}/).map((s) => s.trim()).filter(Boolean);
  if (!paragraphs.length) {
    return (
      <p className="mt-6 text-[15px] italic text-muted-foreground" data-testid={`${testId}-empty`}>
        Isi artikel belum ditulis.
      </p>
    );
  }

  return (
    <div className="mt-6 space-y-5 text-[16px] leading-[1.85] text-foreground/80" data-testid={`${testId}-text`}>
      {paragraphs.map((p, i) => (
        <p key={i} className={i === 0
          ? "[&::first-letter]:float-left [&::first-letter]:mr-3 [&::first-letter]:mt-1 [&::first-letter]:font-fraunces [&::first-letter]:text-6xl [&::first-letter]:leading-[0.75] [&::first-letter]:text-primary"
          : ""}>
          {p}
        </p>
      ))}
    </div>
  );
}

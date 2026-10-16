import { Globe } from "lucide-react";
import { useLang } from "@/hooks/useLang";
import { t } from "@/lib/i18n";

// LanguageSwitch — CMS-06: pemilih bahasa ringkas (ID / EN) untuk header publik.
// Bentuk "segmented" 2 tombol: satu klik, tanpa dropdown — pengunjung asing langsung
// melihat bahwa versi English ada (dropdown menyembunyikan informasi itu).
export default function LanguageSwitch({ solid = true, compact = false }) {
  const { lang, setLang, langs } = useLang();
  const shell = solid
    ? "border-border bg-card/80 text-foreground"
    : "border-white/40 bg-white/10 text-white";
  // `compact` dipakai di bar pengumuman: bar itu setinggi satu baris teks 11,5px, jadi
  // tombol harus SETIPIS teks di sebelahnya. Tanpa ini header tumbuh ~14px dan token
  // offset `--header-h` (dipakai ChatWidget) jadi tidak akurat.
  const pad = compact ? "px-1.5 py-0 text-[10.5px]" : "px-2.5 py-1 text-[11.5px]";
  return (
    <div className={`inline-flex items-center gap-0.5 rounded-full border ${compact ? "p-0" : "p-0.5"} ${shell}`}
      role="group" aria-label={t("lang.switch", lang)} data-testid="lang-switch">
      {compact ? null : (
        <Globe size={13} className="ml-1.5 mr-0.5 opacity-70" aria-hidden="true" />
      )}
      {langs.map((l) => {
        const active = l.code === lang;
        return (
          <button key={l.code} type="button" onClick={() => setLang(l.code)}
            aria-pressed={active} title={l.label} data-testid={`lang-switch-${l.code}`}
            className={`rounded-full font-bold tracking-wide transition ${pad} ${
              active
                ? "bg-primary text-primary-foreground shadow-sm"
                : solid ? "text-muted-foreground hover:text-foreground" : "text-white/75 hover:text-white"
            }`}>
            {l.short}
          </button>
        );
      })}
    </div>
  );
}

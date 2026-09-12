#!/usr/bin/env python3
"""INV-THEME-01 — Kontras & pewarisan tema TIDAK boleh bergantung pada kebetulan.

Kelas bug yang dijaga (semuanya NYATA, ditemukan 2026-08-12 dari screenshot user):

1. **Gradient dengan token triplet HSL** — `bg-gradient-to-br from-primary to-[color:var(--primary)]`
   di `/blog/:slug`. Token tema proyek ini berisi TRIPLET (`--primary: 220 45% 14%`), jadi
   `color:var(--primary)` INVALID; browser membuang SELURUH deklarasi `background-image`,
   panel jadi transparan, dan teks `text-primary-foreground` (putih) hilang di kertas putih.
   Gagalnya SENYAP: tidak ada error konsol, tidak ada tes yang merah.

2. **Permukaan kaca memaksa PUTIH untuk semua mode** — `.glass-modal` dulu memakai
   `hsla(0 0% 100% / .94) !important`. Di mode gelap `--foreground` = putih, jadi isi dialog
   menjadi putih-di-atas-putih.

3. **Refraksi/sheen menyapu teks** — `.glass-3d::before` dulu `mix-blend-mode: screen`
   opacity .55 tanpa mask, sehingga label & placeholder di kartu estimator hero tak terbaca
   di atas foto terang.

4. **Token tema tidak diwarisi konten yang di-PORTAL** — Radix menempelkan Dialog/Select ke
   `<body>`, DI LUAR div `[data-surface="public"][data-theme=...]`. Tanpa atribut yang sama di
   `<html>`, seluruh permukaan portal memakai token :root (tema ERP terang) walau situs gelap.
   Ekor masalahnya: selector `.dark [data-surface][data-theme]` hanya cocok untuk DESCENDANT,
   jadi `<html>` sendiri butuh selector kembar `[data-surface][data-theme].dark`.

5. **Jebakan CSS custom property** — `--x: var(--card) / .93` yang dideklarasikan di `:root`
   disubstitusi DI :root (tema ERP terang) lalu HASILNYA yang diwariskan; nilainya tidak
   pernah ikut tema. Kartu tetap terang di mode gelap → teks putih hilang.

6. **Elemen mengapung dengan offset hardcode** — ChatWidget dulu `bottom-24`/`bottom-40` +
   tinggi TETAP 440px, sehingga pada viewport pendek panel menembus header (keluhan user
   "posisi chat terlalu di atas"). Offset wajib diturunkan dari token `--fab-bottom`/
   `--panel-bottom` dan tingginya dibatasi tinggi viewport.

Penjaga ini STATIK (murah, jalan tanpa browser) — pasangan runtime-nya adalah pengukuran
computed style oleh testing agent (iteration_86/87).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import Guard, FRONTEND  # noqa: E402

SRC = FRONTEND / "src"
INDEX_CSS = SRC / "index.css"
THEMES_CSS = SRC / "styles" / "public-themes.css"
THEME_CTX = SRC / "context" / "ThemeContext.js"
CHAT = SRC / "components" / "public" / "ChatWidget.jsx"

# Token WARNA tema: nilainya triplet HSL & di-override per surface/preset/mode.
THEME_COLOR_TOKENS = (
    "background", "foreground", "card", "card-foreground", "popover", "popover-foreground",
    "primary", "primary-foreground", "secondary", "secondary-foreground", "muted",
    "muted-foreground", "accent", "accent-foreground", "border", "input", "ring",
)
TOKEN_ALT = "|".join(THEME_COLOR_TOKENS)

# Class Tailwind arbitrary-value yang MUSTAHIL valid dengan token triplet.
BAD_GRADIENT = re.compile(r'\b(?:from|via|to)-\[color:var\(--(?:' + TOKEN_ALT + r')\)\]')
# `bg-[var(--primary)]` juga invalid (butuh hsl(...)).
BAD_BG_VAR = re.compile(r'\b(?:bg|text|border)-\[var\(--(?:' + TOKEN_ALT + r')\)\]')


def css_block(text: str, selector_start: str) -> str:
    """Ambil isi blok CSS pertama yang selectornya diawali `selector_start`."""
    i = text.find(selector_start)
    if i < 0:
        return ""
    j = text.find("{", i)
    if j < 0:
        return ""
    depth = 0
    for k in range(j, len(text)):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                return text[j + 1:k]
    return ""


def strip_css_comments(text: str) -> str:
    """Buang blok `/* ... */`.

    WAJIB: berkas ini SENGAJA mendokumentasikan bug lama di komentar (mis. menyebut
    `mix-blend-mode: screen` dan `--surface-on-hero: var(--card) / .93` sebagai contoh yang
    DILARANG). Tanpa pelucutan komentar, penjaga menemukan "pelanggaran" pada dokumentasinya
    sendiri — temuan palsu yang sama seperti aturan `ux_audit` W2 dulu.
    """
    return re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)


def strip_js_comments(text: str) -> str:
    """Buang komentar blok dan baris komentar (`//`) dari sumber JS/JSX."""
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    return "\n".join(
        ln for ln in text.splitlines() if not re.match(r'\s*(//|\*)', ln)
    )


def main() -> int:
    g = Guard("INV-THEME-01", "Kontras & pewarisan tema (glass, portal, offset mengapung)")

    # --- 1) Tidak ada class gradient/warna arbitrary yang memakai token triplet ----------
    jsx = sorted(list(SRC.rglob("*.jsx")) + list(SRC.rglob("*.js")))
    for f in jsx:
        txt = strip_js_comments(f.read_text(encoding="utf-8", errors="ignore"))
        g.bump()
        for m in BAD_GRADIENT.finditer(txt):
            rel = f.relative_to(SRC)
            g.add(f"{rel}: `{m.group(0)}` — token tema berisi TRIPLET HSL, `color:var(--x)` "
                  f"INVALID → browser membuang seluruh background-image (panel jadi kosong, "
                  f"teks terang di latar terang). Pakai `bg-primary` / "
                  f"`style={{{{ background: 'var(--gradient-cta)' }}}}` / komponen CtaBand.")
        for m in BAD_BG_VAR.finditer(txt):
            rel = f.relative_to(SRC)
            g.add(f"{rel}: `{m.group(0)}` — token triplet tidak bisa dipakai langsung sebagai "
                  f"warna; bungkus `hsl(var(--x))` atau pakai utilitas Tailwind bawaan.")

    css_raw = INDEX_CSS.read_text(encoding="utf-8", errors="ignore") if INDEX_CSS.exists() else ""
    # Komentar dilucuti: berkas index.css SENGAJA mendokumentasikan pola terlarang sebagai
    # contoh, dan itu bukan pelanggaran.
    css = strip_css_comments(css_raw)
    if not css.strip():
        g.add("frontend/src/index.css tidak ditemukan/kosong — kontrak tema tak bisa diperiksa.")
        return g.finish()

    # --- 2) Permukaan kaca tidak boleh memaksa PUTIH untuk semua mode -------------------
    for sel in (".glass-modal {", ".glass-on-hero {", ".glass-3d {"):
        block = css_block(css, sel)
        g.bump()
        if not block:
            g.add(f"index.css: blok `{sel.strip(' {')}` hilang — kontrak permukaan kaca dibongkar.")
            continue
        if re.search(r'hsla?\(\s*0\s+0%\s+100%', block):
            g.add(f"index.css `{sel.strip(' {')}`: latar dipaku PUTIH (`hsl(0 0% 100%)`) untuk "
                  f"SEMUA mode → di mode gelap `--foreground` putih = putih-di-atas-putih "
                  f"(bug nyata pada modal exit-intent). Pakai token yang ikut mode: "
                  f"`hsla(var(--glass-bg-strong))` / `hsla(var(--card) / …)`.")

    # fallback @supports juga wajib ikut mode
    sup = css_block(css, "@supports not ((-webkit-backdrop-filter")
    g.bump()
    if sup and re.search(r'\.glass-modal\s*\{[^}]*hsla?\(\s*0\s+0%\s+100%', sup):
        g.add("index.css @supports fallback: `.glass-modal` kembali dipaku putih — peramban tanpa "
              "backdrop-filter akan menampilkan dialog putih + teks putih di mode gelap.")

    # --- 3) Refraksi/sheen tidak boleh menyapu area teks ---------------------------------
    g.bump()
    if re.search(r'mix-blend-mode:\s*screen', css):
        g.add("index.css: `mix-blend-mode: screen` dipakai hardcode — di atas foto TERANG ia "
              "menyapu label/placeholder sampai hilang. Pakai `var(--refraction-blend)` "
              "(soft-light di light, normal di dark).")
    m = re.search(r'--refraction-opacity:\s*([0-9.]+)', css)
    g.bump()
    if not m:
        g.add("index.css: token `--refraction-opacity` hilang — kekuatan refraksi kembali "
              "hardcode dan tak bisa diturunkan per mode.")
    elif float(m.group(1)) > 0.30:
        g.add(f"index.css: `--refraction-opacity: {m.group(1)}` > 0.30 — terlalu kuat, teks di "
              f"dalam kartu kaca mulai tersapu (batas aman dari design_guidelines: ≤ 0.28).")
    g.bump()
    if "--refraction-mask" not in css:
        g.add("index.css: token `--refraction-mask` hilang — overlay refraksi menutupi 100% "
              "kartu tanpa mask, termasuk area form/label.")

    # --- 4) Jebakan custom property: jangan komposisi token tema di :root/.dark ----------
    for sel in (":root {", ".dark {"):
        block = css_block(css, sel)
        if not block:
            continue
        g.bump()
        for decl in re.finditer(r'(--[a-z0-9-]+)\s*:\s*([^;]*var\(--(?:' + TOKEN_ALT + r')\)[^;]*);',
                                block):
            g.add(f"index.css `{sel.strip(' {')}`: `{decl.group(1)}` menyusun token TEMA "
                  f"(`{decl.group(2).strip()[:60]}…`). `var()` di dalam custom property "
                  f"disubstitusi DI ELEMEN DEKLARASI (:root = tema ERP terang) lalu HASILNYA "
                  f"diwariskan — nilainya TIDAK akan ikut mode gelap. Tulis ekspresinya "
                  f"langsung di kelas pemakai (mis. `background: hsla(var(--card) / .93)`).")

    # --- 5) Token offset elemen mengapung wajib ada -------------------------------------
    for tok in ("--header-h", "--fab-bottom", "--panel-bottom", "--sticky-cta-h"):
        g.bump()
        if tok not in css:
            g.add(f"index.css: token offset `{tok}` hilang — elemen mengapung kembali memakai "
                  f"angka hardcode dan bisa menabrak header / bar CTA mobile.")

    # --- 6) ChatWidget wajib memakai token offset, bukan angka hardcode -----------------
    if CHAT.exists():
        chat = strip_js_comments(CHAT.read_text(encoding="utf-8", errors="ignore"))
        for tok in ("var(--fab-bottom)", "var(--panel-bottom)"):
            g.bump()
            if tok not in chat:
                g.add(f"ChatWidget.jsx: tidak memakai `{tok}` — offset chat kembali hardcode "
                      f"(dulu `bottom-24`/`bottom-40` + tinggi tetap 440px menembus header "
                      f"pada viewport pendek).")
        g.bump()
        if re.search(r'className="[^"]*\bfixed\b[^"]*\bbottom-\d', chat):
            g.add("ChatWidget.jsx: masih ada `bottom-<n>` Tailwind pada elemen `fixed` — offset "
                  "wajib lewat token `--fab-bottom`/`--panel-bottom` agar ikut tinggi "
                  "StickyMobileCTA + safe-area.")
        g.bump()
        if not re.search(r'maxHeight', chat):
            g.add("ChatWidget.jsx: panel tanpa `maxHeight` — pada viewport pendek panel bisa "
                  "lebih tinggi dari ruang tersisa dan menutupi header.")

    # --- 7) Token tema wajib diwarisi konten yang di-PORTAL -----------------------------
    if THEME_CTX.exists():
        ctx = strip_js_comments(THEME_CTX.read_text(encoding="utf-8", errors="ignore"))
        for needle, why in (
            ('setAttribute("data-surface"',
             "tanpa atribut surface di <html>, Dialog/Select yang di-portal ke <body> memakai "
             "token :root (tema ERP terang) walau situs sedang gelap"),
            ('setAttribute("data-theme"',
             "tanpa atribut preset di <html>, permukaan portal tidak pernah memakai preset tema "
             "yang dipilih pemilik"),
            ('removeAttribute("data-surface")',
             "tanpa pembersihan saat unmount, konsol ERP ikut memakai palet situs publik"),
        ):
            g.bump()
            if needle not in ctx:
                g.add(f"ThemeContext.js: `{needle}…` hilang — {why}.")

    # --- 8) Blok dark per preset wajib punya selector kembar untuk <html> ---------------
    if THEMES_CSS.exists():
        th = strip_css_comments(THEMES_CSS.read_text(encoding="utf-8", errors="ignore"))
        presets = re.findall(r'\.dark (\[data-surface="public"\]\[data-theme="(\w+)"\])', th)
        g.bump()
        if not presets:
            g.add("public-themes.css: tak ada blok `.dark [data-surface=\"public\"][data-theme=…]` "
                  "— mode gelap situs publik hilang.")
        for sel, name in presets:
            g.bump()
            twin = f'{sel}.dark'
            if twin not in th:
                g.add(f"public-themes.css: preset `{name}` punya `.dark {sel}` tetapi TIDAK punya "
                      f"kembarannya `{twin}` — `.dark X` hanya cocok untuk DESCENDANT, sedangkan "
                      f"atribut tema kini juga dipasang di <html> itu sendiri. Akibatnya permukaan "
                      f"portal memakai blok LIGHT saat mode gelap.")

    return g.finish()


if __name__ == "__main__":
    sys.exit(main())

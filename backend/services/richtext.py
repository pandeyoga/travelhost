"""services/richtext.py — CMS-09: isi artikel kaya (HTML) yang DIBERSIHKAN di server.

Mengapa di server
-----------------
Editor blok di browser boleh saja rapi, tetapi endpoint `PUT /api/content/articles/{id}`
tetap bisa dipanggil langsung (curl/Postman). Kalau pembersihan hanya di browser, satu
request berisi `<script>` sudah cukup untuk menanam XSS di halaman blog publik.
Karena itu SEMUA isi artikel dibersihkan di server dengan allowlist ketat memakai
`bleach` (implementasi html5lib, dipakai luas di ekosistem Python).

Aturan
------
- Tag diizinkan: struktur artikel saja (heading, paragraf, list, kutipan, gambar, tautan).
- Atribut diizinkan: minimal (href/title pada tautan; src/alt/dimensi pada gambar).
- Protokol diizinkan: http, https, mailto (URL relatif tetap boleh → aset `/api/...`).
- `style`, `on*`, `<script>`, `<iframe>`, `javascript:` DIBUANG.
"""
import re

try:
    import bleach
except Exception:  # pragma: no cover — degradasi aman bila paket hilang
    bleach = None

ALLOWED_TAGS = [
    "p", "br", "strong", "b", "em", "i", "u", "s", "h2", "h3", "h4",
    "ul", "ol", "li", "blockquote", "a", "img", "figure", "figcaption",
    "hr", "code", "pre",
]
ALLOWED_ATTRS = {
    "a": ["href", "title"],
    "img": ["src", "alt", "width", "height", "loading"],
}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

_TAG_RE = re.compile(r"<\s*(p|h2|h3|h4|ul|ol|li|blockquote|img|figure|hr|strong|em|a|br)\b", re.I)
_STRIP_RE = re.compile(r"<[^>]*>")
_SCRIPTISH_RE = re.compile(r"<\s*(script|style|iframe|object|embed)", re.I)
# Blok berbahaya DIBUANG BERSAMA ISINYA. `bleach` dengan `strip=True` membuang TAG-nya tetapi
# MENYISAKAN teks di dalamnya, sehingga `<script>alert(1)</script>` tersimpan sebagai kalimat
# "alert(1)" yang lalu terbaca pengunjung di tengah artikel — bukan lubang keamanan, tapi
# kotor dan membingungkan. Karena itu isinya dibuang lebih dulu.
_BLOCK_RE = re.compile(
    r"<\s*(script|style|iframe|object|embed|noscript|template)\b[^>]*>.*?<\s*/\s*\1\s*>",
    re.I | re.S)
_SELF_CLOSING_BLOCK_RE = re.compile(
    r"<\s*(script|style|iframe|object|embed|noscript|template)\b[^>]*/?>", re.I)

MAX_HTML_CHARS = 200000


def looks_like_html(value) -> bool:
    """True bila teks memuat markup artikel (dipakai FE memilih cara render)."""
    text = str(value or "")
    return bool(_TAG_RE.search(text))


def sanitize(value) -> str:
    """Bersihkan HTML sesuai allowlist. Tanpa `bleach`, markup dibuang total (fail-safe)."""
    text = str(value or "")[:MAX_HTML_CHARS]
    if not text.strip():
        return ""
    # Buang blok berbahaya BESERTA isinya sebelum allowlist dijalankan (lihat _BLOCK_RE).
    text = _BLOCK_RE.sub("", text)
    text = _SELF_CLOSING_BLOCK_RE.sub("", text)
    if bleach is None:
        # Fail CLOSED: lebih baik kehilangan format daripada menayangkan HTML mentah.
        return _STRIP_RE.sub("", text)
    cleaned = bleach.clean(
        text,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )
    return cleaned.strip()


def is_dangerous(value) -> bool:
    """Deteksi cepat markup berbahaya (dipakai uji & audit)."""
    text = str(value or "")
    if _SCRIPTISH_RE.search(text):
        return True
    if re.search(r"on\w+\s*=", text, re.I):
        return True
    if re.search(r"javascript\s*:", text, re.I):
        return True
    return False


def to_text(value, max_chars: int = 0) -> str:
    """HTML → teks bersih (meta description, ringkasan, hitung waktu baca)."""
    text = _STRIP_RE.sub(" ", str(value or ""))
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    text = re.sub(r"\s+", " ", text).strip()
    if max_chars and len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "…"
    return text


def read_minutes(value, wpm: int = 200) -> int:
    words = len(to_text(value).split())
    return max(1, round(words / max(1, wpm))) if words else 0

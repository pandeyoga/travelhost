"""services/i18n.py — CMS-06: konten dua bahasa (Indonesia + English).

Mengapa
-------
Wisata Jawa–Bali punya pasar turis asing yang besar, tetapi seluruh konten situs hanya
berbahasa Indonesia — segmen bernilai tinggi itu praktis tak tersentuh.

Desain
------
- Terjemahan disimpan DI DALAM dokumen konten: `translations = {"en": {field: teks}}`.
  Satu dokumen = satu sumber kebenaran; tak ada koleksi bayangan yang bisa desinkron.
- Field yang boleh diterjemahkan DIBATASI per-resource (whitelist) — sama disiplinnya
  dengan whitelist field CMS, jadi tak ada penulisan liar.
- `localize()` menimpa field dasar HANYA bila terjemahan tidak kosong → selalu ada
  fallback ke Indonesia (halaman EN tak pernah tampil kosong/berlubang).
"""
LANGS = ("id", "en")
DEFAULT_LANG = "id"
LANG_LABELS = {"id": "Bahasa Indonesia", "en": "English"}
LANG_LOCALES = {"id": "id_ID", "en": "en_US"}

# Field per-resource yang layak diterjemahkan (teks yang dibaca pengunjung).
TRANSLATABLE = {
    "destinations": ["name", "description", "intro", "best_time", "meta_title", "meta_description"],
    "packages": ["name", "description", "includes", "meta_title", "meta_description"],
    "articles": ["title", "excerpt", "body", "meta_title", "meta_description"],
    "promos": ["title", "description", "meta_title", "meta_description"],
}

MAX_FIELD_CHARS = 20000


def normalize_lang(value) -> str:
    lang = str(value or "").strip().lower()[:5]
    if not lang:
        return DEFAULT_LANG
    lang = lang.split("-")[0]
    return lang if lang in LANGS else DEFAULT_LANG


def translatable_fields(resource: str) -> list:
    return list(TRANSLATABLE.get(resource, []))


def clean_translations(resource: str, value) -> dict:
    """Bersihkan payload `translations` — hanya bahasa & field terdaftar, string/list string."""
    allowed = set(TRANSLATABLE.get(resource, []))
    out = {}
    if not isinstance(value, dict):
        return out
    for lang, fields in value.items():
        code = normalize_lang(lang)
        if code == DEFAULT_LANG or not isinstance(fields, dict):
            continue        # bahasa dasar disimpan di field utama, bukan di translations
        bucket = {}
        for key, val in fields.items():
            if key not in allowed:
                continue
            if isinstance(val, list):
                bucket[key] = [str(v)[:MAX_FIELD_CHARS] for v in val if str(v or "").strip()]
            elif val is None:
                continue
            else:
                text = str(val)[:MAX_FIELD_CHARS]
                if text.strip():
                    bucket[key] = text
        if bucket:
            out[code] = bucket
    return out


def has_translation(resource: str, doc: dict, lang: str) -> bool:
    code = normalize_lang(lang)
    if code == DEFAULT_LANG:
        return True
    tr = (doc or {}).get("translations") or {}
    return bool(isinstance(tr, dict) and tr.get(code))


def localize(resource: str, doc: dict, lang: str) -> dict:
    """Kembalikan dokumen dengan field terjemahan ditimpakan (fallback: Indonesia)."""
    if not doc:
        return doc
    code = normalize_lang(lang)
    out = dict(doc)
    out["lang"] = code
    if code == DEFAULT_LANG:
        return out
    tr = (doc.get("translations") or {}).get(code) or {}
    allowed = set(TRANSLATABLE.get(resource, []))
    applied = []
    for key, val in tr.items():
        if key not in allowed:
            continue
        if isinstance(val, list) and val:
            out[key] = val
            applied.append(key)
        elif isinstance(val, str) and val.strip():
            out[key] = val
            applied.append(key)
    out["translated_fields"] = applied
    out["has_translation"] = bool(applied)
    return out


def localize_many(resource: str, docs, lang: str) -> list:
    return [localize(resource, d, lang) for d in (docs or [])]

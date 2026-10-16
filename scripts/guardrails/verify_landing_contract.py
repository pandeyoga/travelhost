#!/usr/bin/env python3
"""INV-LP-02 — Kontrak template Landing Page ↔ skema blok WAJIB selaras (anti "props hilang senyap").

Kelas bug yang ditutup (nyata, ditemukan di fase F8):
  1. `landing_templates.py` mengirim `trust_badges.items` sebagai daftar STRING, sedangkan
     `landing_blocks._trust` memanggil `.get()` → **AttributeError → HTTP 500** saat marketing
     admin menekan satu template tertentu. Fitur mati total, hanya untuk satu template.
  2. Template mengirim `success_text`/`deadline`/`cta` pada blok yang skemanya memakai nama lain
     → nilainya DIBUANG saat `validate_blocks` **tanpa pesan apa pun**. Halaman terlihat
     "kehilangan" tombol/tenggat/pesan sukses, dan tak ada error yang bisa dicari di log.
     Ini yang paling mahal: halaman iklan tetap tayang, tetapi tombolnya salah/hilang.

Penjaga ini bersifat STATIK+EKSEKUSI RINGAN (tanpa DB, tanpa jaringan): ia benar-benar membangun
setiap template lalu melewatkannya ke validator, dan menuntut:
  (1) tiap props template ADA di daftar props kanonik blok tersebut,
  (2) nilai teks/daftar yang terisi TIDAK menyusut/menghilang setelah validasi,
  (3) `validate_blocks` tidak melempar untuk bentuk props aneh (kontrak "editor tak boleh 5xx"),
  (4) tiap tipe blok bisa dibangun dari props KOSONG (tombol "+ Tambah blok" di editor),
  (5) tiap template punya minimal satu blok konversi — kalau tidak, halaman TIDAK BISA diterbitkan
      (INV-LP-01) dan template itu jadi jebakan bagi pengguna,
  (6) renderer frontend menangani semua tipe blok (blok tanpa `case` = area kosong di halaman iklan).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, FRONTEND, Guard  # noqa: E402

sys.path.insert(0, str(BACKEND))

RENDERER = FRONTEND / "src" / "components" / "app" / "landing" / "LandingRender.jsx"


def main() -> int:
    g = Guard("INV-LP-02", "Template landing page selaras skema blok (tak ada props hilang senyap)")
    try:
        from services import landing_blocks as lb
        from services import landing_templates as lt
    except Exception as exc:  # noqa: BLE001
        g.bump()
        g.add(f"tidak bisa mengimpor modul landing ({type(exc).__name__}: {exc}) — fitur mati total.")
        return g.finish()

    templates = lt.list_templates()
    g.bump()
    if len(templates) < 2 or {t["segment"] for t in templates} != {"armada", "destinasi"}:
        g.add("daftar template tidak mencakup kedua segmen iklan (armada & destinasi).")

    for t in templates:
        key = t["key"]
        try:
            blocks, theme, _seg = lt.build(key)
        except Exception as exc:  # noqa: BLE001
            g.bump()
            g.add(f"template '{key}': build() melempar {type(exc).__name__}: {exc} → endpoint 500.")
            continue
        try:
            clean, warns = lb.validate_blocks(blocks)
        except Exception as exc:  # noqa: BLE001
            g.bump()
            g.add(f"template '{key}': validate_blocks MELEMPAR {type(exc).__name__}: {exc} → "
                  f"POST /api/landing/pages balas HTTP 500 (kelas BUG-0111).")
            continue

        g.bump()
        if warns:
            g.add(f"template '{key}': validasi menghasilkan peringatan {warns[:2]} — template bawaan "
                  f"harus 100% valid, bukan menyisakan pekerjaan bagi pengguna.")
        g.bump()
        if len(clean) != len(blocks):
            g.add(f"template '{key}': {len(blocks) - len(clean)} blok dibuang saat validasi → "
                  f"halaman tampil tidak sesuai template yang dijanjikan.")

        for raw, out in zip(blocks, clean):
            btype = raw.get("type")
            canon = lb.canonical_props(btype)
            props_in = raw.get("props") or {}
            props_out = out.get("props") or {}
            for name, value in props_in.items():
                g.bump()
                if name not in canon:
                    g.add(f"template '{key}' blok '{btype}': props '{name}' TIDAK ADA di skema "
                          f"(kanonik: {sorted(canon)}) → isinya dibuang senyap.")
                elif isinstance(value, str) and value.strip() and not str(props_out.get(name) or "").strip():
                    g.add(f"template '{key}' blok '{btype}': props '{name}' terisi di template "
                          f"tetapi KOSONG setelah validasi → hilang senyap.")
                elif isinstance(value, list) and value and len(props_out.get(name) or []) != len(value):
                    g.add(f"template '{key}' blok '{btype}': daftar '{name}' menyusut "
                          f"{len(value)} → {len(props_out.get(name) or [])} item.")

        g.bump()
        if not lb.has_conversion_block(clean):
            g.add(f"template '{key}' tidak punya blok konversi → halaman dari template ini TIDAK "
                  f"BISA diterbitkan (INV-LP-01): template menjadi jebakan.")
        g.bump()
        if not isinstance(theme, dict) or not lb.sanitize_theme(theme).get("primary"):
            g.add(f"template '{key}': tema tidak valid.")

    # (3) bentuk props aneh tidak boleh melempar — kontrak "editor tidak boleh 5xx"
    adversarial = [
        {"type": "trust_badges", "props": {"items": ["string", 1, None, {"label": "ok"}]}},
        {"type": "value_props", "props": {"items": "bukan daftar"}},
        {"type": "faq", "props": {"items": ["bukan objek"]}},
        {"type": "gallery", "props": {"items": {"bukan": "daftar"}}},
        {"type": "search_hero", "props": {"tabs": 5, "fields": [None], "chips": {"a": 1}}},
        {"type": "hero_media", "props": {"title": {"objek": True}, "ctas": "bukan daftar"}},
        {"type": "cta_band", "props": {"ctas": [None, "teks"]}},
        {"type": "lead_form", "props": {"fields": {"bukan": "daftar"}}},
        {"type": "countdown", "props": {"deadline": {"a": 1}}},
        {"type": "rich_text", "props": {"html": ['<script>x</script>']}},
    ]
    g.bump()
    try:
        lb.validate_blocks(adversarial)
    except Exception as exc:  # noqa: BLE001
        g.add(f"validate_blocks MELEMPAR pada props adversarial ({type(exc).__name__}: {exc}) — "
              f"pagar try/except per blok hilang → editor bisa 5xx lagi (INV-5XX-01).")

    # (4) setiap tipe blok bisa dibangun dari kosong (tombol "+ Tambah blok")
    for btype in sorted(lb.BLOCK_TYPES):
        g.bump()
        try:
            clean, _ = lb.validate_blocks([{"type": btype, "props": {}}])
            if not clean:
                g.add(f"tipe blok '{btype}' hilang saat dibuat dari props kosong → tombol "
                      f"'+ Tambah blok' menghasilkan blok yang menguap.")
        except Exception as exc:  # noqa: BLE001
            g.add(f"tipe blok '{btype}' melempar saat props kosong ({type(exc).__name__}: {exc}).")

    # (6) renderer frontend menangani semua tipe blok
    if RENDERER.exists():
        render_txt = RENDERER.read_text(encoding="utf-8", errors="ignore")
        for btype in sorted(lb.BLOCK_TYPES):
            g.bump()
            if f'case "{btype}"' not in render_txt:
                g.add(f"LandingRender.jsx tidak menangani blok '{btype}' → blok bisa ditambahkan "
                      f"di editor tetapi TIDAK TAMPIL di halaman iklan (area kosong).")
    else:
        g.bump()
        g.add("LandingRender.jsx tidak ditemukan — renderer bersama editor & halaman publik hilang.")

    # A/B: bidang override yang diiklankan skema harus benar-benar diterapkan renderer server-side
    g.bump()
    src = (BACKEND / "services" / "landing_blocks.py").read_text(encoding="utf-8", errors="ignore")
    if not re.search(r"def apply_variant", src) or "cta_label" not in src:
        g.add("apply_variant/override A/B tidak lengkap → varian B tampil identik dengan A dan "
              "uji A/B menghasilkan kesimpulan palsu.")

    return g.finish()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""test_core_lp_f8.py — POC FASE F8: membuktikan inti Landing Page Builder SEBELUM UI dibangun.

Filosofi repo: jangan bangun UI di atas fondasi yang belum terbukti. Tujuh hal di bawah adalah
bagian yang paling mudah gagal SENYAP pada fitur halaman iklan, dan semuanya bisa diuji tanpa
kredensial Meta/Google:

  POC-1 Kontrak blok & template (INV-LP-02) : 8 template × 17 tipe blok tidak boleh kehilangan
                                              props senyap; input adversarial tidak boleh 5xx;
                                              rich text XSS harus mati; warna non-hex ditolak.
  POC-2 Media LOKAL (INV-MEDIA-01/02)       : unggah gambar+video → berkas ada di disk → bisa
                                              dibaca PUBLIK tanpa login (URL benar) → thumbnail →
                                              MIME/ukuran ditolak jelas → path traversal ditolak →
                                              soft-delete membuat URL 404 & blok tak render mati.
  POC-3 Layak terbit (INV-LP-01)            : slug unik otomatis; tolak terbit tanpa blok konversi
                                              /SEO; draf tidak bocor ke publik; blok hidden tidak
                                              terkirim ke halaman publik.
  POC-4 Lead dari halaman iklan (INV-CONV-01): submit → lead CRM ber-atribusi (utm/gclid/fbclid/
                                              ctwa) → event lead.created → outbox konversi terisi;
                                              submit ganda TIDAK menggandakan lead; consent &
                                              nomor tak valid ditolak sopan; honeypot senyap.
  POC-5 Uji A/B                              : pemilihan varian deterministik + sebaran sesuai
                                              bobot; override headline/CTA benar-benar tampil;
                                              tampilan/klik/lead tercatat per varian; pemenang
                                              hanya diumumkan bila sampel cukup.
  POC-6 Duplikat halaman                     : jadi DRAF baru, slug baru, blok utuh, statistik
                                              TIDAK terbawa.
  POC-7 RBAC halaman iklan                   : ops_admin & driver 403; publik tanpa login 200.

Jalankan: cd /app && python scripts/test_core_lp_f8.py
Keluar 0 = semua LULUS. Semua data uji dibersihkan di akhir.
"""
import asyncio
import io
import os
import sys
import uuid
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("PYTHONPATH", str(ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / "backend" / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts" / "guardrails"))
from _common import purge_guard_artifacts  # noqa: E402  (INV-CLEAN-01)

G, R, Y, C, B, X = "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[1m", "\033[0m"
API = os.environ.get("POC_API", "http://localhost:8001/api")
RESULTS = []
CREATED_PAGES, CREATED_MEDIA, CREATED_LEADS = [], [], []
# Nomor kontak khusus POC (konvensi INV-CLEAN-01: dipakai mesin bersih-bersih bersama).
POC_PHONES = ("081299998888", "081277776666")


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    icon = f"{G}[OK]{X}" if ok else f"{R}[GAGAL]{X}"
    print(f"  {icon} {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def head(title):
    print(f"\n{C}{B}== {title} =={X}")


def login(email, password="demo12345"):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    r.raise_for_status()
    return r.json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def png_bytes(w=900, h=600, color=(11, 123, 211)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------------------- POC-1
def poc1_contract():
    head("POC-1 · Kontrak blok & template (INV-LP-02) + anti-5xx + anti-XSS")
    from services import landing_blocks as lb
    from services import landing_templates as lt

    templates = lt.list_templates()
    check("template tersedia untuk KEDUA segmen iklan",
          {t["segment"] for t in templates} == {"armada", "destinasi"} and len(templates) >= 6,
          f"{len(templates)} template")

    lost = []
    for t in templates:
        blocks, theme, _seg = lt.build(t["key"])
        clean, warns = lb.validate_blocks(blocks)
        if len(clean) != len(blocks) or warns:
            lost.append(f"{t['key']}: blok hilang/peringatan {warns}")
        for raw, out in zip(blocks, clean):
            canon = set(lb.canonical_props(raw["type"]))
            for key, value in (raw.get("props") or {}).items():
                if key not in canon:
                    lost.append(f"{t['key']}/{raw['type']}: props '{key}' TIDAK ADA di skema")
                elif isinstance(value, str) and value and not out["props"].get(key):
                    lost.append(f"{t['key']}/{raw['type']}: '{key}' hilang saat validasi")
                elif isinstance(value, list) and value and len(out["props"].get(key) or []) != len(value):
                    lost.append(f"{t['key']}/{raw['type']}: daftar '{key}' menyusut")
    check("tidak ada props template yang dibuang senyap oleh skema", not lost,
          "; ".join(lost[:3]) if lost else f"{len(templates)} template diperiksa")

    covered = {b["type"] for t in templates for b in lt.build(t["key"])[0]}
    check("template memakai mayoritas tipe blok (bukti kontrak dipakai nyata)",
          len(covered) >= 12, f"{len(covered)}/{len(lb.BLOCK_TYPES)} tipe blok")

    # setiap tipe blok harus bisa divalidasi dari props KOSONG (dipakai tombol "+ Tambah blok")
    empty_ok = []
    for btype in lb.BLOCK_TYPES:
        try:
            clean, _ = lb.validate_blocks([{"type": btype, "props": {}}])
            empty_ok.append(bool(clean))
        except Exception as exc:  # noqa: BLE001
            empty_ok.append(False)
            print(f"     {R}{btype}: {exc}{X}")
    check("17 tipe blok bisa dibuat dari kosong tanpa melempar", all(empty_ok),
          f"{sum(empty_ok)}/{len(empty_ok)}")

    # input adversarial — dulu bentuk STRING pada trust_badges membuat HTTP 500 (BUG-0109)
    adversarial = [
        {"type": "trust_badges", "props": {"items": ["500+ trip", {"label": "Berasuransi"}]}},
        {"type": "value_props", "props": {"items": ["cuma string", 12345, None]}},
        {"type": "cta_band", "props": {"cta": {"label": "Klik", "target": "/booking"}}},
        {"type": "faq", "props": {"items": ["bukan objek"]}},
        {"type": "gallery", "props": {"items": "bukan daftar"}},
        {"type": "search_hero", "props": {"tabs": "rusak", "fields": [None, {"type": "aneh"}]}},
        {"type": "hero_media", "props": {"title": {"nested": "objek"}, "overlay": "abc"}},
        {"type": "blok_tidak_ada", "props": {}},
        {"type": "", "props": None},
        {"type": "lead_form", "props": {"fields": ["name", "tidak_ada_field", "phone"]}},
    ]
    try:
        clean, warns = lb.validate_blocks(adversarial)
        ok = len(clean) == 8  # dua blok tak dikenal dilewati
    except Exception as exc:  # noqa: BLE001
        clean, warns, ok = [], [], False
        print(f"     {R}melempar: {type(exc).__name__}: {exc}{X}")
    check("input adversarial tidak melempar (turun jadi peringatan)", ok,
          f"{len(clean)} blok bersih, {len(warns)} peringatan")
    if clean:
        trust = next((b for b in clean if b["type"] == "trust_badges"), {})
        items = (trust.get("props") or {}).get("items") or []
        check("trust_badges menerima item STRING maupun objek (BUG-0109 tertutup)",
              len(items) == 2 and all(isinstance(i, dict) and i.get("label") for i in items),
              str(items))
        band = next((b for b in clean if b["type"] == "cta_band"), {})
        check("cta_band tunggal `cta` dinaikkan menjadi daftar `ctas` (tombol tidak hilang)",
              len(((band.get("props") or {}).get("ctas") or [])) == 1)
        form = next((b for b in clean if b["type"] == "lead_form"), {})
        check("lead_form membuang field tak dikenal & menjamin nama+telepon",
              (form.get("props") or {}).get("fields") == ["name", "phone"])

    xss = ('<script>alert(1)</script><p onclick="evil()">Hai <b>tebal</b></p>'
           '<a href="javascript:alert(2)">jahat</a><a href="/booking" target="_blank">aman</a>')
    out = lb.sanitize_html(xss)
    check("XSS rich text dibersihkan (script/onclick/javascript: hilang, isi aman tetap)",
          "script" not in out.lower() and "onclick" not in out.lower()
          and "javascript:" not in out.lower() and "<b>tebal</b>" in out and "/booking" in out,
          out[:80])

    theme = lb.sanitize_theme({"primary": "red; background:url(x)", "accent": "#FF7A00",
                               "radius": 999, "font_scale": 999, "preset": "hijau-tropis"})
    check("warna non-hex ditolak (cegah CSS injection) & angka dijepit",
          theme["primary"].startswith("#") and theme["accent"] == "#FF7A00"
          and theme["radius"] <= 32 and theme["font_scale"] <= 120, str(theme))

    errs = lb.publish_errors({"slug": "", "title": "", "seo": {}, "blocks": []})
    check("publish_errors menyebut SEMUA alasan (bukan hanya yang pertama)", len(errs) >= 4,
          f"{len(errs)} alasan")


# --------------------------------------------------------------------------------------- POC-2
def poc2_media(token):
    head("POC-2 · Media LOKAL: unggah → baca publik → thumbnail → validasi → hapus")
    from services import media_store as ms

    info = ms.storage_info()
    check("penyimpanan media SIAP tanpa kredensial (backend lokal)",
          info["ready"] and info["backend"] == "local", f"{info['backend_label']} · {info['reason']}")

    img = png_bytes()
    r = requests.post(f"{API}/landing/media", headers=auth(token),
                      files={"file": ("foto-hero.png", img, "image/png")}, data={"alt": "Hiace di Bromo"},
                      timeout=60)
    ok = r.status_code == 200
    asset = r.json() if ok else {}
    if asset.get("id"):
        CREATED_MEDIA.append(asset["id"])
    check("unggah GAMBAR berhasil", ok and asset.get("kind") == "image",
          f"HTTP {r.status_code} {str(r.text)[:80]}")
    check("URL aset memakai rute publik yang BENAR (BUG-0110)",
          (asset.get("url") or "").startswith("/api/public/media/"), asset.get("url"))
    check("dimensi gambar terbaca (dipakai viewer Media Library)",
          asset.get("width") == 900 and asset.get("height") == 600,
          f"{asset.get('width')}×{asset.get('height')}")
    check("jalur penyimpanan internal TIDAK dibocorkan ke klien", "storage_path" not in asset)

    doc_path = ""
    if asset.get("id"):
        # berkas benar-benar ada di disk (bukan hanya baris database)
        import pymongo
        cli = pymongo.MongoClient(os.environ["MONGO_URL"])
        row = cli[os.environ["DB_NAME"]].media_assets.find_one({"id": asset["id"]}) or {}
        doc_path = row.get("storage_path") or ""
        cli.close()
        abs_path = ms.LOCAL_DIR / doc_path
        check("berkas fisik tersimpan di disk lokal server", abs_path.is_file(),
              str(abs_path).replace(str(ROOT), "."))
        check("nama berkas TIDAK memakai nama unggahan pengguna (anti tebak/tabrak)",
              "foto-hero" not in doc_path, doc_path)

    # baca PUBLIK tanpa header Authorization — halaman iklan harus bisa memuat gambar
    pr = requests.get(f"http://localhost:8001{asset.get('url')}", timeout=30) if asset.get("url") else None
    check("aset bisa diambil PUBLIK tanpa login", bool(pr) and pr.status_code == 200
          and pr.content == img, f"HTTP {getattr(pr, 'status_code', '-')}")
    check("content-type & cache header benar",
          bool(pr) and pr.headers.get("content-type", "").startswith("image/")
          and "max-age" in (pr.headers.get("cache-control") or ""),
          f"{getattr(pr, 'headers', {}).get('content-type')}")
    tr = requests.get(f"http://localhost:8001{asset.get('thumb_url')}", timeout=30) if asset.get("thumb_url") else None
    check("thumbnail dibuat & lebih kecil dari aslinya (grid tetap ringan)",
          bool(tr) and tr.status_code == 200 and 0 < len(tr.content) < len(img),
          f"{len(getattr(tr, 'content', b''))} vs {len(img)} byte")

    vid = b"\x00\x00\x00\x18ftypmp42" + os.urandom(300_000)
    rv = requests.post(f"{API}/landing/media", headers=auth(token),
                       files={"file": ("cuplikan.mp4", vid, "video/mp4")}, timeout=90)
    vasset = rv.json() if rv.status_code == 200 else {}
    if vasset.get("id"):
        CREATED_MEDIA.append(vasset["id"])
    check("unggah VIDEO berhasil & ditandai kind=video",
          rv.status_code == 200 and vasset.get("kind") == "video", f"HTTP {rv.status_code}")

    bad = requests.post(f"{API}/landing/media", headers=auth(token),
                        files={"file": ("virus.exe", b"MZ" + os.urandom(1000), "application/x-msdownload")},
                        timeout=30)
    check("tipe berkas berbahaya DITOLAK 400 dengan alasan jelas (INV-MEDIA-01)",
          bad.status_code == 400 and "didukung" in bad.text.lower(), f"HTTP {bad.status_code}")
    big = requests.post(f"{API}/landing/media", headers=auth(token),
                        files={"file": ("besar.png", os.urandom(ms.MAX_IMAGE_BYTES + 2048), "image/png")},
                        timeout=120)
    check("gambar melebihi batas ukuran DITOLAK 400 dengan angka batas",
          big.status_code == 400 and "maksimal" in big.text.lower(), f"HTTP {big.status_code}")

    # INV-MEDIA-02 — path traversal tidak boleh keluar dari direktori media
    traversal_blocked = []
    for evil in ("../../../etc/passwd", "/etc/passwd", "landing/../../../../etc/hosts", "", "\x00abc"):
        try:
            ms.fetch(evil, backend="local")
            traversal_blocked.append(False)
        except ms.MediaError:
            traversal_blocked.append(True)
        except Exception:  # noqa: BLE001
            traversal_blocked.append(False)
    check("path traversal & jalur kosong DITOLAK MediaError (INV-MEDIA-02)",
          all(traversal_blocked), f"{sum(traversal_blocked)}/{len(traversal_blocked)} jalur diblokir")

    if asset.get("id"):
        pa = requests.patch(f"{API}/landing/media/{asset['id']}", headers=auth(token),
                            json={"alt": "Hiace Premio di Bromo pagi"}, timeout=30)
        check("teks alternatif (alt) bisa diperbaiki — penting untuk SEO iklan",
              pa.status_code == 200 and pa.json().get("alt") == "Hiace Premio di Bromo pagi",
              f"HTTP {pa.status_code}")
    lst = requests.get(f"{API}/landing/media?kind=image&q=Hiace", headers=auth(token), timeout=30)
    check("Media Library bisa dicari & difilter per tipe",
          lst.status_code == 200 and any(a["id"] == asset.get("id") for a in lst.json().get("assets", [])),
          f"HTTP {lst.status_code}, {len(lst.json().get('assets', []) if lst.ok else [])} aset")
    return asset, vasset


def poc2b_media_deleted(token, asset):
    """Aset yang dihapus tidak boleh meninggalkan tautan mati di halaman iklan."""
    from services import landing_blocks as lb
    doc = {"blocks": [{"id": "b1", "type": "hero_media", "hidden": False, "device": "all",
                       "props": {"media": {"media_id": asset["id"], "src": "", "kind": "image"}}}]}
    payload = lb.public_payload(doc, {asset["id"]: {"url": asset["url"], "kind": "image"}})
    check("media aktif → URL diselesaikan di payload publik",
          payload["blocks"][0]["props"]["media"]["src"] == asset["url"])
    payload2 = lb.public_payload(doc, {})
    check("media terhapus → src dikosongkan (tidak render tautan mati)",
          payload2["blocks"][0]["props"]["media"]["src"] == "")
    d = requests.delete(f"{API}/landing/media/{asset['id']}", headers=auth(token), timeout=30)
    check("hapus aset (soft-delete) berhasil", d.status_code == 200, f"HTTP {d.status_code}")
    pr = requests.get(f"http://localhost:8001{asset['url']}", timeout=30)
    check("aset terhapus TIDAK bisa diakses publik lagi (404)", pr.status_code == 404,
          f"HTTP {pr.status_code}")


# --------------------------------------------------------------------------------------- POC-3
def poc3_publish(token):
    head("POC-3 · Layak terbit (INV-LP-01) + draf tidak bocor + blok hidden tidak terkirim")
    slug = f"poc-armada-{uuid.uuid4().hex[:6]}"
    r = requests.post(f"{API}/landing/pages", headers=auth(token),
                      json={"template": "armada-konversi", "title": "POC Armada", "slug": slug}, timeout=30)
    page = r.json() if r.status_code == 200 else {}
    if page.get("id"):
        CREATED_PAGES.append(page["id"])
    check("buat halaman dari template berhasil", r.status_code == 200 and page.get("slug") == slug,
          f"HTTP {r.status_code}")

    r2 = requests.post(f"{API}/landing/pages", headers=auth(token),
                       json={"template": "armada-konversi", "title": "POC Armada", "slug": slug}, timeout=30)
    page2 = r2.json() if r2.status_code == 200 else {}
    if page2.get("id"):
        CREATED_PAGES.append(page2["id"])
    check("slug bentrok otomatis dibuat unik (tidak melempar 500)",
          r2.status_code == 200 and page2.get("slug") == f"{slug}-2", page2.get("slug"))

    pub404 = requests.get(f"{API}/public/landing/{slug}", timeout=20)
    check("draf TIDAK bocor ke publik (404 sebelum diterbitkan)", pub404.status_code == 404,
          f"HTTP {pub404.status_code}")

    # buang semua blok konversi → harus ditolak terbit dengan alasan
    blocks = [b for b in page.get("blocks", []) if b["type"] not in
              ("lead_form", "cta_band", "wa_cta", "hero_media", "search_hero")]
    requests.patch(f"{API}/landing/pages/{page['id']}", headers=auth(token),
                   json={"blocks": blocks, "seo": {"title": "", "description": ""}}, timeout=30)
    bad = requests.post(f"{API}/landing/pages/{page['id']}/publish", headers=auth(token),
                        json={}, timeout=30)
    detail = (bad.json() or {}).get("detail", "") if bad.status_code == 400 else bad.text
    check("terbit DITOLAK 400 tanpa blok konversi & tanpa SEO, alasan jelas",
          bad.status_code == 400 and "konversi" in detail.lower() and "seo" in detail.lower(),
          f"HTTP {bad.status_code} · {detail[:90]}")

    # pulihkan blok + sembunyikan satu blok untuk membuktikan blok hidden tidak terkirim
    full = page.get("blocks", [])
    for b in full:
        if b["type"] == "faq":
            b["hidden"] = True
    requests.patch(f"{API}/landing/pages/{page['id']}", headers=auth(token),
                   json={"blocks": full, "seo": {"title": "Sewa Hiace Murah", "description": "Uji POC"}},
                   timeout=30)
    good = requests.post(f"{API}/landing/pages/{page['id']}/publish", headers=auth(token), json={}, timeout=30)
    check("halaman layak → TERBIT + URL publik dikembalikan",
          good.status_code == 200 and good.json().get("url") == f"/lp/{slug}",
          f"HTTP {good.status_code} {good.text[:70]}")

    pub = requests.get(f"{API}/public/landing/{slug}", timeout=20)
    body = pub.json() if pub.status_code == 200 else {}
    types = [b["type"] for b in body.get("blocks", [])]
    check("halaman publik bisa diakses TANPA login", pub.status_code == 200, f"HTTP {pub.status_code}")
    check("blok disembunyikan TIDAK terkirim ke publik", "faq" not in types, str(types))
    check("payload publik memuat tema, SEO & id halaman (untuk pelacakan)",
          bool(body.get("theme", {}).get("primary")) and body.get("seo", {}).get("title")
          and body.get("page_id"))

    unpub = requests.post(f"{API}/landing/pages/{page['id']}/publish", headers=auth(token),
                          json={"unpublish": True}, timeout=30)
    after = requests.get(f"{API}/public/landing/{slug}", timeout=20)
    check("tarik dari publikasi → halaman publik langsung 404",
          unpub.status_code == 200 and after.status_code == 404,
          f"HTTP {unpub.status_code}/{after.status_code}")
    requests.post(f"{API}/landing/pages/{page['id']}/publish", headers=auth(token), json={}, timeout=30)
    return page, slug


# --------------------------------------------------------------------------------------- POC-4
async def poc4_lead(db, token, page, slug):
    head("POC-4 · Lead dari halaman iklan → CRM + atribusi + outbox konversi (idempoten)")
    attribution = {"utm_source": "google", "utm_medium": "cpc", "utm_campaign": "sewa-hiace-agustus",
                   "utm_term": "sewa hiace jakarta", "gclid": "TEST-GCLID-123",
                   "referrer": "https://www.google.com/", "landing_page": f"/lp/{slug}"}
    phone = f"0812{uuid.uuid4().int % 90000000 + 10000000}"
    payload = {"name": "Budi Panitia", "phone": phone, "email": "budi@contoh.id",
               "destination": "Bromo", "start": "2026-09-10", "pax": "18",
               "message": "Butuh 2 unit Hiace", "marketing_consent": True,
               "attribution": attribution, "click_ids": {"fbclid": "FB-XYZ", "ctwa_clid": "CTWA-1"},
               "variant_id": "A"}
    r = requests.post(f"{API}/public/landing/{slug}/lead", json=payload, timeout=30)
    body = r.json() if r.status_code == 200 else {}
    if body.get("id"):
        CREATED_LEADS.append(body["id"])
    check("submit form lead di halaman iklan berhasil (tanpa login)",
          r.status_code == 200 and body.get("id"), f"HTTP {r.status_code} {r.text[:90]}")
    check("pesan sukses diambil dari setelan blok (bukan teks generik hardcode)",
          "30 menit" in (body.get("message") or ""), body.get("message"))

    lead = await db.leads.find_one({"id": body.get("id")}, {"_id": 0}) or {}
    check("lead tersimpan di CRM dengan nama & nomor yang benar",
          lead.get("customer_name") == "Budi Panitia" and lead.get("phone") == phone)
    check("atribusi iklan tersimpan: channel google_ads dari gclid",
          lead.get("channel") == "google_ads" and lead.get("utm_campaign") == "sewa-hiace-agustus",
          f"channel={lead.get('channel')}")
    check("click-id lain (fbclid/ctwa_clid) tidak hilang — dibutuhkan atribusi CTWA",
          (lead.get("click_ids") or {}).get("ctwa_clid") == "CTWA-1"
          and (lead.get("click_ids") or {}).get("fbclid") == "FB-XYZ")
    check("halaman & varian sumber tercatat (bisa dilacak halaman mana yang menghasilkan)",
          lead.get("landing_page_id") == page["id"] and lead.get("landing_slug") == slug
          and lead.get("landing_variant") == "A")
    check("lead ditugaskan otomatis ke agen (tidak menganggur di inbox)", bool(lead.get("assigned_to")))
    check("persetujuan pemasaran tercatat beserta waktunya (dasar hukum kirim WA)",
          lead.get("marketing_consent") is True and bool(lead.get("consent_at")))
    check("tahap awal = new (masuk kolom pertama CRM)", lead.get("stage") == "new")

    act = await db.lead_activities.find_one({"lead_id": body.get("id")}, {"_id": 0}) or {}
    check("aktivitas 'created' dicatat dengan asal halaman iklan",
          bool(act) and slug in (act.get("text") or ""), (act.get("text") or "")[:70])

    ev = await db.events.find_one({"dedupe_key": f"lead.created:{body.get('id')}"}, {"_id": 0}) or {}
    check("event lead.created ter-emit (memicu otomasi & konversi)", ev.get("type") == "lead.created")
    outbox = await db.conversion_events.find({"ref_id": body.get("id")}, {"_id": 0}).to_list(10)
    check("outbox konversi terisi untuk provider iklan (INV-CONV-01)", len(outbox) >= 1,
          f"{len(outbox)} entri: {[o.get('provider') + ':' + str(o.get('status')) for o in outbox]}")

    # submit ganda (klik dobel / retry jaringan) TIDAK boleh menggandakan lead
    r2 = requests.post(f"{API}/public/landing/{slug}/lead", json=payload, timeout=30)
    same = r2.status_code == 200 and r2.json().get("id") == body.get("id")
    total = await db.leads.count_documents({"landing_page_id": page["id"], "phone": phone})
    check("submit ganda mengembalikan lead yang SAMA & tetap 1 baris di CRM",
          same and total == 1 and r2.json().get("duplicate") is True, f"{total} lead")

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(requests.post, f"{API}/public/landing/{slug}/lead", json=payload, timeout=30)
                for _ in range(6)]
        codes = [f.result().status_code for f in futs]
    total2 = await db.leads.count_documents({"landing_page_id": page["id"], "phone": phone})
    check("6 submit PARALEL tetap menghasilkan 1 lead (unique index, bukan cek-lalu-tulis)",
          total2 == 1 and all(c == 200 for c in codes), f"{total2} lead · kode {sorted(set(codes))}")

    no_consent = {**payload, "phone": "081299998888", "marketing_consent": False}
    rc = requests.post(f"{API}/public/landing/{slug}/lead", json=no_consent, timeout=30)
    check("tanpa persetujuan → 400 dengan permintaan sopan (bukan 5xx/senyap)",
          rc.status_code == 400 and "persetujuan" in rc.text.lower(), f"HTTP {rc.status_code}")
    bad_phone = {**payload, "phone": "123", "idempotency_key": "x1"}
    rp = requests.post(f"{API}/public/landing/{slug}/lead", json=bad_phone, timeout=30)
    check("nomor tidak valid → 400 dengan alasan yang bisa dipahami pengunjung",
          rp.status_code == 400 and "nomor" in rp.text.lower(), f"HTTP {rp.status_code}")
    hp = {**payload, "phone": "081277776666", "hp": "aku-bot", "idempotency_key": "bot"}
    rh = requests.post(f"{API}/public/landing/{slug}/lead", json=hp, timeout=30)
    spam = await db.leads.count_documents({"phone": "081277776666"})
    check("honeypot: bot dijawab 200 tetapi TIDAK menulis lead",
          rh.status_code == 200 and spam == 0, f"{spam} lead spam")

    missing = requests.post(f"{API}/public/landing/tidak-ada-slug-xyz/lead", json=payload, timeout=20)
    check("submit ke slug tak ada/belum terbit → 404 (bukan 500)", missing.status_code == 404,
          f"HTTP {missing.status_code}")
    return body.get("id")


# --------------------------------------------------------------------------------------- POC-5
async def poc5_ab(db, token, page, slug):
    head("POC-5 · Uji A/B: pemilihan deterministik, override tampil, statistik & pemenang")
    from services import landing_blocks as lb

    ab = {"enabled": True, "goal": "lead", "min_sample": 30, "variants": [
        {"id": "A", "name": "Asli", "weight": 50, "overrides": {}},
        {"id": "B", "name": "Varian B", "weight": 50,
         "overrides": {"title": "Hiace Siap Jalan Hari Ini", "cta_label": "Chat Sekarang"}},
    ]}
    r = requests.patch(f"{API}/landing/pages/{page['id']}", headers=auth(token),
                       json={"ab": ab}, timeout=30)
    saved = (r.json() or {}).get("page", {}).get("ab") or {}
    check("setelan A/B tersimpan & aktif", r.status_code == 200 and saved.get("enabled") is True
          and len(saved.get("variants") or []) == 2, f"HTTP {r.status_code}")

    single = lb.sanitize_ab({"enabled": True, "variants": [{"id": "A", "name": "Asli"}]})
    check("A/B menolak aktif bila hanya ada 1 versi (statistik tak bermakna)",
          single["enabled"] is False)
    forced = lb.sanitize_ab({"enabled": True, "variants": [
        {"id": "A", "name": "Asli", "overrides": {"title": "coba timpa"}},
        {"id": "B", "name": "B", "overrides": {"title": "judul B"}}]})
    check("varian A selalu 'asli' tanpa override (titik nol perbandingan jujur)",
          forced["variants"][0]["overrides"] == {} and forced["variants"][1]["overrides"]["title"] == "judul B")

    seed = "visitor-abc-123"
    picks = {lb.pick_variant(saved, seed=seed)["id"] for _ in range(25)}
    check("pemilihan varian DETERMINISTIK untuk pengunjung yang sama (refresh tidak berubah)",
          len(picks) == 1, str(picks))
    spread = {}
    for i in range(2000):
        vid = lb.pick_variant(saved, seed=f"v{i}")["id"]
        spread[vid] = spread.get(vid, 0) + 1
    balanced = all(700 <= n <= 1300 for n in spread.values()) and len(spread) == 2
    check("sebaran 2000 pengunjung mendekati bobot 50/50", balanced, str(spread))

    pa = requests.get(f"{API}/public/landing/{slug}?variant=A", timeout=20).json()
    pb = requests.get(f"{API}/public/landing/{slug}?variant=B", timeout=20).json()
    hero_a = next((b for b in pa.get("blocks", []) if b["type"] in ("search_hero", "hero_media")), {})
    hero_b = next((b for b in pb.get("blocks", []) if b["type"] in ("search_hero", "hero_media")), {})
    check("varian B benar-benar mengubah judul hero yang dilihat pengunjung",
          (hero_b.get("props") or {}).get("title") == "Hiace Siap Jalan Hari Ini"
          and (hero_a.get("props") or {}).get("title") != "Hiace Siap Jalan Hari Ini",
          f"A='{(hero_a.get('props') or {}).get('title', '')[:30]}' B='{(hero_b.get('props') or {}).get('title', '')[:30]}'")
    check("varian B juga mengubah label tombol aksi",
          ((hero_b.get("props") or {}).get("cta") or {}).get("label") == "Chat Sekarang",
          str(((hero_b.get("props") or {}).get("cta") or {}).get("label")))
    check("payload publik memberi tahu varian mana yang sedang tampil (untuk pelacakan)",
          pb.get("variant", {}).get("id") == "B" and pb.get("ab_enabled") is True)

    v1 = requests.get(f"{API}/public/landing/{slug}?vid=pengunjung-1", timeout=20).json()
    v2 = requests.get(f"{API}/public/landing/{slug}?vid=pengunjung-1", timeout=20).json()
    check("dua kunjungan dengan vid sama mendapat varian sama",
          v1.get("variant", {}).get("id") == v2.get("variant", {}).get("id"))

    for _ in range(3):
        requests.post(f"{API}/public/landing/{slug}/track", json={"type": "view", "variant_id": "B"}, timeout=20)
    tc = requests.post(f"{API}/public/landing/{slug}/track",
                       json={"type": "cta_click", "variant_id": "B"}, timeout=20)
    bad = requests.post(f"{API}/public/landing/{slug}/track",
                        json={"type": "peristiwa-aneh", "variant_id": "B"}, timeout=20)
    stats = await db.landing_stats.find_one({"page_id": page["id"], "variant_id": "B"}, {"_id": 0}) or {}
    check("tampilan & klik CTA tercatat per varian (agregat harian)",
          tc.status_code == 200 and stats.get("views", 0) >= 3 and stats.get("cta_clicks", 0) >= 1,
          f"views={stats.get('views')} clicks={stats.get('cta_clicks')}")
    check("jenis peristiwa tak dikenal ditolak 400 (bukan mencemari statistik)",
          bad.status_code == 400, f"HTTP {bad.status_code}")

    rep = requests.get(f"{API}/landing/pages/{page['id']}/ab", headers=auth(token), timeout=30).json()
    check("laporan A/B menahan pengumuman pemenang saat sampel kurang",
          rep.get("enough_data") is False and not rep.get("winner")
          and "cukup" in (rep.get("winner_reason") or "").lower(), rep.get("winner_reason", "")[:80])

    # isi statistik dengan angka yang jelas berbeda → B harus menang
    day = (await db.landing_stats.find_one({"page_id": page["id"]}, {"_id": 0}) or {}).get("date")
    await db.landing_stats.update_one({"page_id": page["id"], "variant_id": "A", "date": day},
                                      {"$set": {"views": 200, "leads": 4, "cta_clicks": 10}}, upsert=True)
    await db.landing_stats.update_one({"page_id": page["id"], "variant_id": "B", "date": day},
                                      {"$set": {"views": 200, "leads": 16, "cta_clicks": 40}}, upsert=True)
    rep2 = requests.get(f"{API}/landing/pages/{page['id']}/ab", headers=auth(token), timeout=30).json()
    vb = next((v for v in rep2.get("variants", []) if v["id"] == "B"), {})
    check("laporan menghitung conversion rate per varian dengan benar",
          vb.get("lead_rate") == 8.0, f"B lead_rate={vb.get('lead_rate')}%")
    check("pemenang diumumkan setelah sampel cukup & selisih meyakinkan",
          rep2.get("winner") == "B" and rep2.get("enough_data") is True
          and rep2.get("uplift_percent", 0) > 100, f"{rep2.get('winner')} · {rep2.get('winner_reason')[:60]}")

    await db.landing_stats.update_one({"page_id": page["id"], "variant_id": "A", "date": day},
                                      {"$set": {"views": 200, "leads": 16}}, upsert=True)
    rep3 = requests.get(f"{API}/landing/pages/{page['id']}/ab", headers=auth(token), timeout=30).json()
    check("selisih tipis (<10%) TIDAK diklaim sebagai pemenang",
          not rep3.get("winner") and "tipis" in (rep3.get("winner_reason") or "").lower(),
          rep3.get("winner_reason", "")[:70])


# --------------------------------------------------------------------------------------- POC-6
async def poc6_duplicate(db, token, page):
    head("POC-6 · Duplikat halaman (iterasi kampanye cepat)")
    r = requests.post(f"{API}/landing/pages/{page['id']}/duplicate", headers=auth(token),
                      json={}, timeout=30)
    dup = r.json() if r.status_code == 200 else {}
    if dup.get("id"):
        CREATED_PAGES.append(dup["id"])
    src = await db.landing_pages.find_one({"id": page["id"]}, {"_id": 0}) or {}
    check("duplikat dibuat sebagai DRAF (tidak langsung tayang & menghabiskan biaya iklan)",
          r.status_code == 200 and dup.get("status") == "draft", f"HTTP {r.status_code}")
    check("slug & judul duplikat berbeda dari sumbernya",
          dup.get("slug") != src.get("slug") and dup.get("id") != page["id"], dup.get("slug"))
    check("seluruh blok terbawa utuh", len(dup.get("blocks") or []) == len(src.get("blocks") or []),
          f"{len(dup.get('blocks') or [])} blok")
    check("jejak asal duplikat dicatat (audit)", dup.get("duplicated_from") == page["id"])
    stats = await db.landing_stats.count_documents({"page_id": dup.get("id")})
    check("statistik TIDAK terbawa (angka iklan tidak tercampur)", stats == 0, f"{stats} baris")
    dup2 = requests.post(f"{API}/landing/pages/{page['id']}/duplicate", headers=auth(token),
                         json={}, timeout=30).json()
    if dup2.get("id"):
        CREATED_PAGES.append(dup2["id"])
    check("duplikat kedua tetap mendapat slug unik (tidak 500 karena bentrok)",
          dup2.get("slug") and dup2.get("slug") != dup.get("slug"), dup2.get("slug"))


# --------------------------------------------------------------------------------------- POC-7
def poc7_rbac(slug):
    head("POC-7 · RBAC halaman iklan (owner+marketing_admin saja) & akses publik")
    marketing = login("marketing@demo.local")
    ops = login("ops@demo.local")
    driver = login("driver@demo.local")
    m = requests.get(f"{API}/landing/pages", headers=auth(marketing), timeout=20)
    check("marketing_admin BOLEH mengelola halaman iklan", m.status_code == 200, f"HTTP {m.status_code}")
    for role, tok in (("ops_admin", ops), ("driver", driver)):
        a = requests.get(f"{API}/landing/pages", headers=auth(tok), timeout=20)
        b = requests.get(f"{API}/landing/media", headers=auth(tok), timeout=20)
        check(f"{role} DILARANG (403) pada halaman & media iklan",
              a.status_code == 403 and b.status_code == 403, f"HTTP {a.status_code}/{b.status_code}")
    anon = requests.get(f"{API}/landing/pages", timeout=20)
    check("tanpa token → 401 (bukan bocor data)", anon.status_code == 401, f"HTTP {anon.status_code}")
    pub = requests.get(f"{API}/public/landing/{slug}", timeout=20)
    check("halaman iklan PUBLIK tetap bisa dibuka tanpa login", pub.status_code == 200,
          f"HTTP {pub.status_code}")


# --------------------------------------------------------------------------------------- main
async def cleanup(db, token):
    # Kumpulkan ID lead uji LEBIH DULU: setelah dokumennya hilang, side-effect-nya (percakapan
    # Inbox, catatan aktivitas, event, notifikasi, outbox konversi) tak bisa dilacak lagi.
    lead_ids = [d["id"] async for d in db.leads.find(
        {"$or": [{"landing_page_id": {"$in": CREATED_PAGES}},
                 {"phone": {"$in": list(POC_PHONES)}}]}, {"_id": 0, "id": 1})]
    for pid in CREATED_PAGES:
        requests.delete(f"{API}/landing/pages/{pid}", headers=auth(token), timeout=20)
    for mid in CREATED_MEDIA:
        requests.delete(f"{API}/landing/media/{mid}", headers=auth(token), timeout=20)
        await db.media_assets.delete_one({"id": mid})
    await db.leads.delete_many({"landing_page_id": {"$in": CREATED_PAGES}})
    await db.leads.delete_many({"phone": {"$in": list(POC_PHONES)}})
    await db.landing_stats.delete_many({"page_id": {"$in": CREATED_PAGES}})
    # INV-CLEAN-01 — menghapus LEAD saja tidak cukup: satu lead uji memancarkan event →
    # automation (WA mock) → percakapan + pesan Inbox + notifikasi + catatan aktivitas +
    # baris outbox konversi iklan. Semua itu dulu MENETAP di ERP pengguna (BUG-0127).
    purged = purge_guard_artifacts(extra_phones=POC_PHONES,
                                   extra_ids=CREATED_PAGES + CREATED_MEDIA + lead_ids)
    if purged:
        print(f"  {C}Bersih-bersih total: {purged} dokumen uji + side-effect dihapus.{X}")


async def main():
    print(f"{B}{C}POC FASE F8 — Landing Page Builder + Media Library (lokal) + Lead + A/B{X}")
    print(f"{Y}API: {API}{X}")
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    token = login("owner@demo.local")

    poc1_contract()
    asset, _vasset = poc2_media(token)
    page, slug = poc3_publish(token)
    await poc4_lead(db, token, page, slug)
    await poc5_ab(db, token, page, slug)
    await poc6_duplicate(db, token, page)
    poc7_rbac(slug)
    if asset.get("id"):
        head("POC-2b · Aset media terhapus tidak meninggalkan tautan mati")
        poc2b_media_deleted(token, asset)

    await cleanup(db, token)
    client.close()

    ok = sum(1 for _, o, _ in RESULTS if o)
    total = len(RESULTS)
    print(f"\n{C}{B}{'=' * 74}{X}")
    if ok == total:
        print(f"  {G}{B}POC F8 LULUS — {ok}/{total} pemeriksaan.{X}")
    else:
        print(f"  {R}{B}POC F8 GAGAL — {ok}/{total} lolos. Yang gagal:{X}")
        for name, o, detail in RESULTS:
            if not o:
                print(f"   {R}· {name}{X} — {detail}")
    print(f"{C}{B}{'=' * 74}{X}")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

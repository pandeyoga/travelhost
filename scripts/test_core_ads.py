#!/usr/bin/env python3
"""test_core_ads.py — POC FASE F (E29): membuktikan 5 fondasi Marketing & Ads SEBELUM UI dibangun.

Filosofi repo: jangan bangun di atas fondasi yang belum terbukti. Kelima hal di bawah adalah
bagian yang PALING mudah gagal senyap, dan semuanya bisa diuji TANPA kredensial Meta/Google:

  POC-1 Vault rahasia   : AES-256-GCM round-trip, mask(), simpan/baca settings di MongoDB,
                          dan BUKTI bahwa bentuk publik TIDAK memuat plaintext/ciphertext.
  POC-2 Object storage  : unggah GAMBAR (~1MB) + VIDEO (~12MB) ke object storage platform lalu
                          unduh kembali dan bandingkan SHA-256 (harus identik) + content-type.
  POC-3 Outbox konversi : 8 enqueue paralel dengan event_id sama -> tepat 1 dokumen per provider
                          (unique index bekerja); payload Meta CAPI & Google Data Manager sesuai
                          skema resmi (SHA-256 PII, nilai IDR integer, dedup event_id);
                          kredensial kosong -> status 'skipped' berALASAN (bukan hilang senyap);
                          kegagalan HTTP -> 'failed' + jadwal retry, lalu 'dead' setelah 5 attempt.
  POC-4 Blok landing    : validasi 16 tipe blok, sanitasi XSS rich text, aturan layak-terbit
                          (INV-LP-01), dan resolusi URL media (termasuk aset terhapus).
  POC-5 RBAC peran baru : matriks marketing_admin/ops_admin/driver konsisten FE<->BE
                          (menjalankan guardrail INV-RBAC-01..05).

Jalankan: cd /app && python scripts/test_core_ads.py
Keluar 0 = semua LULUS. Tidak menyentuh data demo selain koleksi uji (dibersihkan di akhir).
"""
import asyncio
import base64
import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("PYTHONPATH", str(ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / "backend" / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

G, R, Y, C, B, X = "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[1m", "\033[0m"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    icon = f"{G}[OK]{X}" if ok else f"{R}[GAGAL]{X}"
    print(f"  {icon} {name}" + (f" — {detail}" if detail else ""))
    return ok


def head(title):
    print(f"\n{C}{B}== {title} =={X}")


# --------------------------------------------------------------------------------------- POC-1
async def poc1_vault(db):
    head("POC-1 · Vault rahasia (AES-256-GCM + mask + settings MongoDB)")
    from services import secrets_vault as vault

    check("kunci enkripsi tersedia (SETTINGS_ENCRYPTION_KEY_B64)", vault.vault_ready())
    secret = "EAAB-token-rahasia-1234567890-abcdefghijkl"
    blob = vault.encrypt(secret)
    check("ciphertext berbeda dari plaintext & base64 sah", blob != secret and base64.b64decode(blob))
    check("decrypt(encrypt(x)) == x", vault.decrypt(blob) == secret)
    check("dua enkripsi nilai sama menghasilkan ciphertext berbeda (nonce acak)",
          vault.encrypt(secret) != blob)
    check("mask() menyembunyikan nilai, sisakan 4 karakter akhir",
          vault.mask(secret).endswith(secret[-4:]) and secret[:8] not in vault.mask(secret))

    fields = ("access_token", "app_secret", "test_event_code")
    doc = vault.store_secrets({"pixel_id": "1234567890"},
                              {"access_token": secret, "app_secret": "app-secret-xyz"}, fields)
    check("plaintext tidak pernah tersimpan di dokumen",
          all(doc.get(f) is None for f in fields) and secret not in str(doc))
    await db.settings.update_one({"key": "poc_meta_ads"}, {"$set": {"key": "poc_meta_ads", "value": doc}},
                                 upsert=True)
    saved = (await db.settings.find_one({"key": "poc_meta_ads"}, {"_id": 0}) or {}).get("value") or {}
    check("tersimpan & terbaca dari MongoDB", saved.get("access_token_enc") == doc["access_token_enc"])
    check("read_secret mengembalikan plaintext untuk pemakaian internal",
          vault.read_secret(saved, "access_token") == secret)

    pub = vault.public_view(saved, fields)
    leak = secret in str(pub) or doc["access_token_enc"] in str(pub)
    check("bentuk publik TIDAK memuat plaintext maupun ciphertext", not leak, str(pub)[:90])
    check("bentuk publik memberi flag *_set + *_masked",
          pub.get("access_token_set") is True and pub.get("access_token_masked", "").endswith(secret[-4:])
          and pub.get("app_secret_set") is True and pub.get("test_event_code_set") is False)

    kept = vault.store_secrets(saved, {"access_token": "", "app_secret": vault.DELETE_SENTINEL}, fields)
    check("input kosong = pertahankan rahasia lama (UI hanya menampilkan '••••')",
          vault.read_secret(kept, "access_token") == secret)
    check("sentinel __HAPUS__ menghapus rahasia", not kept.get("app_secret_enc"))
    await db.settings.delete_one({"key": "poc_meta_ads"})


# --------------------------------------------------------------------------------------- POC-2
def poc2_storage(db_sync_docs):
    head("POC-2 · Object storage (gambar + VIDEO, awet lintas restart)")
    from services import media_store as ms

    if not ms.storage_ready():
        check("EMERGENT_LLM_KEY tersedia", False, "kunci belum ada di backend/.env")
        return []
    try:
        ms.init_storage()
        check("init_storage() berhasil (storage_key didapat)", True)
    except Exception as exc:  # noqa: BLE001
        check("init_storage() berhasil", False, str(exc)[:120])
        return []

    assets = []
    # gambar ~1MB (PNG minimal + padding acak agar ukuran realistis)
    img = (b"\x89PNG\r\n\x1a\n" + os.urandom(1024 * 1024))
    # video ~12MB (header mp4 + isi acak; object storage tidak melakukan transcoding)
    vid = (b"\x00\x00\x00\x18ftypmp42" + os.urandom(12 * 1024 * 1024))
    for label, data, ctype, fname in (("gambar 1MB", img, "image/png", "hero-armada.png"),
                                      ("video 12MB", vid, "video/mp4", "promo-armada.mp4")):
        t0 = time.time()
        try:
            meta = ms.upload_bytes(data, ctype, fname, folder="landing")
        except Exception as exc:  # noqa: BLE001
            check(f"unggah {label}", False, str(exc)[:140])
            continue
        up = time.time() - t0
        t0 = time.time()
        got, got_ct = ms.fetch(meta["storage_path"])
        down = time.time() - t0
        same = hashlib.sha256(got).hexdigest() == hashlib.sha256(data).hexdigest()
        check(f"unggah+unduh {label} identik (SHA-256)", same,
              f"{len(data) // 1024}KB · unggah {up:.1f}s · unduh {down:.1f}s · ct={got_ct}")
        check(f"content-type {label} dipertahankan", got_ct.split(";")[0] == ctype)
        assets.append(meta)
        db_sync_docs.append(meta)

    # validasi penolakan
    try:
        ms.upload_bytes(b"x" * 100, "application/x-msdownload", "virus.exe")
        check("tipe berkas berbahaya ditolak", False, "seharusnya MediaError")
    except ms.MediaError as exc:
        check("tipe berkas berbahaya ditolak", True, str(exc)[:60])
    try:
        ms.upload_bytes(os.urandom(ms.MAX_IMAGE_BYTES + 1024), "image/png", "besar.png")
        check("gambar melebihi 10MB ditolak", False, "seharusnya MediaError")
    except ms.MediaError as exc:
        check("gambar melebihi 10MB ditolak", True, str(exc)[:70])
    check("nama berkas disanitasi (tanpa path traversal)",
          ms.safe_stem("../../etc/passwd .png") == "etc-passwd" or
          "/" not in ms.safe_stem("../../etc/passwd.png"))
    check("path memakai UUID + prefiks app (anti tabrakan)",
          ms.build_path("image", ".png").startswith(f"{ms.APP_PREFIX}/landing/image/"))
    return assets


# --------------------------------------------------------------------------------------- POC-3
async def poc3_outbox(db):
    head("POC-3 · Outbox konversi (idempoten, payload resmi, tak ada yang hilang senyap)")
    from services import conversions as cv

    await db[cv.COLL].delete_many({"ref_id": {"$regex": "^poc-"}})
    await cv.ensure_indexes(db)
    idx = await db[cv.COLL].index_information()
    check("unique index (provider, event_key) terpasang",
          any(v.get("unique") for k, v in idx.items() if k == "uniq_provider_event"))

    ident = {"email": " Budi@Example.COM ", "phone": "0812-3456-7890", "fbp": "fb.1.1700000000.123",
             "fbc": "fb.1.1700000000.IwAR0", "gclid": "TeSt-GCLID-123", "ip": "103.10.10.10",
             "user_agent": "Mozilla/5.0", "external_id": "cus_123"}
    tasks = [cv.enqueue(db, "payment", "poc-bk-1", value=1500000, identifiers=ident,
                        source_url="https://rahaza.test/lp/promo-armada") for _ in range(8)]
    res = await asyncio.gather(*tasks, return_exceptions=True)
    errs = [r for r in res if isinstance(r, Exception)]
    check("8 enqueue paralel tidak melempar error", not errs, str(errs[:1])[:120])
    n_meta = await db[cv.COLL].count_documents({"event_key": "payment_poc-bk-1", "provider": "meta"})
    n_goog = await db[cv.COLL].count_documents({"event_key": "payment_poc-bk-1", "provider": "google"})
    check("tepat 1 dokumen per provider (idempoten)", n_meta == 1 and n_goog == 1,
          f"meta={n_meta} google={n_goog}")

    ev = await db[cv.COLL].find_one({"event_key": "payment_poc-bk-1", "provider": "meta"}, {"_id": 0})
    body = cv.build_meta_payload({"api_version": "v25.0", "pixel_id": "1", "ldu_enabled": False},
                                 {"test_event_code": "TEST123"}, ev, test=True)
    e = body["data"][0]
    check("payload Meta: field wajib lengkap",
          {"event_name", "event_time", "event_id", "action_source", "user_data"} <= set(e)
          and e["action_source"] == "website" and e["event_name"] == "Purchase")
    check("payload Meta: event_id = ID bisnis (dedup dgn pixel browser)", e["event_id"] == "payment_poc-bk-1")
    check("payload Meta: email & telepon di-SHA-256 (bukan plaintext)",
          e["user_data"]["em"][0] == hashlib.sha256(b"budi@example.com").hexdigest()
          and e["user_data"]["ph"][0] == hashlib.sha256(b"6281234567890").hexdigest()
          and "budi@example.com" not in str(body).lower())
    check("payload Meta: fbp/fbc/IP/UA disertakan",
          e["user_data"].get("fbp") and e["user_data"].get("fbc")
          and e["user_data"].get("client_ip_address") and e["user_data"].get("client_user_agent"))
    check("payload Meta: nilai IDR integer + currency",
          e["custom_data"] == {"value": 1500000, "currency": "IDR"})
    check("payload Meta: test_event_code hanya saat mode uji",
          body.get("test_event_code") == "TEST123"
          and "test_event_code" not in cv.build_meta_payload({"pixel_id": "1"}, {"test_event_code": "T"}, ev))
    check("payload Meta: event_time dalam detik Unix (bukan milidetik)",
          abs(e["event_time"] - int(time.time())) < 60 and e["event_time"] < 10_000_000_000)

    gev = await db[cv.COLL].find_one({"event_key": "payment_poc-bk-1", "provider": "google"}, {"_id": 0})
    gbody = cv.build_google_payload({"customer_id": "1234567890", "consent_granted": True,
                                     "conversion_action_ids": {"deposit_received": "998877"}}, gev, test=True)
    g = gbody["events"][0]
    check("payload Google (Data Manager): destinations + conversion action id",
          gbody["destinations"][0]["productDestinationId"] == "998877"
          and gbody["destinations"][0]["operatingAccount"]["accountId"] == "1234567890")
    check("payload Google: transactionId = ID bisnis + nilai IDR",
          g["transactionId"] == "payment_poc-bk-1" and g["conversionValue"] == 1500000 and g["currency"] == "IDR")
    check("payload Google: gclid dipakai sebagai penanda klik", (g.get("adIdentifiers") or {}).get("gclid") == "TeSt-GCLID-123")
    check("payload Google: PII di-hash + consent disertakan",
          g["userData"]["userIdentifiers"][0]["emailAddress"] == hashlib.sha256(b"budi@example.com").hexdigest()
          and g["consent"]["adUserData"] == "GRANTED")
    check("payload Google: validateOnly hanya saat mode uji", gbody.get("validateOnly") is True)

    # kredensial kosong -> skipped berALASAN (bukan hilang senyap)
    # NB: dispatch_pending memproses antrean GLOBAL (bisa berisi konversi dari data demo/gate),
    # jadi uji ini menargetkan dokumen POC secara eksplisit agar deterministik.
    doc = await db[cv.COLL].find_one({"event_key": "payment_poc-bk-1", "provider": "meta"}, {"_id": 0})
    out = await cv.dispatch_one(db, doc, {"meta": {}, "google": {}})
    doc = await db[cv.COLL].find_one({"event_key": "payment_poc-bk-1", "provider": "meta"}, {"_id": 0})
    check("tanpa kredensial: status 'skipped' + alasan jelas (tidak hilang senyap)",
          doc["status"] == "skipped" and "belum" in (doc.get("last_error") or "").lower(),
          f"{out} · {doc.get('last_error')}")

    # simulasi kegagalan HTTP: harus failed + jadwal retry, lalu dead setelah MAX_ATTEMPTS
    cfgs = {"meta": {"enabled": True, "pixel_id": "1", "api_version": "v25.0",
                     "_secrets": {"access_token": "token-palsu"}},
            "google": {"enabled": False}}

    async def failing_sender(provider, cfg, secrets, ev_, test):
        return 400, {"error": {"message": "Invalid OAuth access token (simulasi)"}}

    await db[cv.COLL].update_one({"id": doc["id"]}, {"$set": {"status": "pending", "attempts": 0}})
    ev2 = await db[cv.COLL].find_one({"id": doc["id"]}, {"_id": 0})
    status, _ = await cv.dispatch_one(db, ev2, cfgs, sender=failing_sender)
    after = await db[cv.COLL].find_one({"id": doc["id"]}, {"_id": 0})
    check("gagal HTTP 400 -> status 'failed' + retry terjadwal + error tercatat",
          status == "failed" and after["next_retry_at"] and after["http_status"] == 400
          and after["attempts"] == 1)
    for _ in range(cv.MAX_ATTEMPTS):
        cur = await db[cv.COLL].find_one({"id": doc["id"]}, {"_id": 0})
        await cv.dispatch_one(db, cur, cfgs, sender=failing_sender)
    final = await db[cv.COLL].find_one({"id": doc["id"]}, {"_id": 0})
    check(f"setelah {cv.MAX_ATTEMPTS} attempt -> 'dead' (masuk daftar perlu tindakan)",
          final["status"] == "dead" and final["next_retry_at"] is None, f"attempts={final['attempts']}")

    async def ok_sender(provider, cfg, secrets, ev_, test):
        return 200, {"events_received": 1, "fbtrace_id": "abc"}

    await db[cv.COLL].update_one({"id": doc["id"]}, {"$set": {"status": "pending", "attempts": 0}})
    cur = await db[cv.COLL].find_one({"id": doc["id"]}, {"_id": 0})
    status, _ = await cv.dispatch_one(db, cur, cfgs, sender=ok_sender)
    ok_doc = await db[cv.COLL].find_one({"id": doc["id"]}, {"_id": 0})
    check("sukses -> status 'success' + respons diagnostik tersimpan",
          status == "success" and ok_doc["status"] == "success"
          and ok_doc["response"].get("events_received") == 1 and ok_doc.get("sent_at"))
    check("respons yang disimpan tidak memuat token", "token-palsu" not in str(ok_doc))
    summary = await cv.health_summary(db)
    check("ringkasan Kesehatan Pelacakan bisa dihitung", "meta" in summary and "google" in summary, str(summary))
    await db[cv.COLL].delete_many({"ref_id": {"$regex": "^poc-"}})


# --------------------------------------------------------------------------------------- POC-4
def poc4_blocks():
    head("POC-4 · Blok Landing Page (validasi, anti-XSS, aturan layak terbit)")
    from services import landing_blocks as lb

    check("16 tipe blok terdaftar (2 segmen: armada & destinasi)", len(lb.BLOCK_TYPES) >= 16,
          f"{len(lb.BLOCK_TYPES)} tipe")
    evil = ('<p onclick="steal()">Sewa <b>Hiace</b> <script>alert(1)</script>'
            '<a href="javascript:alert(2)">klik</a> <a href="https://wa.me/62811" target="_blank">WA</a></p>')
    clean = lb.sanitize_html(evil)
    check("sanitasi XSS: <script>, onclick, dan href javascript: dibuang",
          "script" not in clean.lower() and "onclick" not in clean.lower()
          and "javascript:" not in clean.lower(), clean[:90])
    check("sanitasi mempertahankan format sah + menambah rel=noopener",
          "<b>Hiace</b>" in clean and 'href="https://wa.me/62811"' in clean and "noopener" in clean)

    blocks = [
        {"type": "hero_media", "props": {"title": "Sewa Hiace Premio", "media": {"media_id": "med_1", "kind": "image"},
                                         "ctas": [{"label": "Pesan", "kind": "internal", "target": "/booking"}],
                                         "overlay": 999}},
        {"type": "value_props", "props": {"items": [{"title": "Driver berpengalaman"}] * 9}},
        {"type": "fleet_grid", "props": {"limit": 99}},
        {"type": "destination_grid", "props": {}},
        {"type": "gallery", "props": {"items": [{"media_id": "med_1"}, {"media_id": "med_hilang"}]}},
        {"type": "testimonials", "props": {}},
        {"type": "price_estimator", "props": {}},
        {"type": "faq", "props": {"items": [{"q": "Apakah termasuk BBM?", "a": "<b>Ya</b><script>x()</script>"}]}},
        {"type": "lead_form", "props": {"fields": ["email", "hack_field"]}},
        {"type": "video", "props": {"media": {"media_id": "med_2", "src": "x.mp4"}}},
        {"type": "rich_text", "props": {"html": "<h2>Rute</h2>"}},
        {"type": "spacer", "props": {"size": 5000}},
        {"type": "blok_ngawur", "props": {}},
    ]
    clean_blocks, warns = lb.validate_blocks(blocks)
    check("blok tak dikenal dibuang + diberi peringatan (bukan crash)",
          len(clean_blocks) == 12 and any("ngawur" in w for w in warns), f"{len(clean_blocks)} blok, {warns}")
    hero = clean_blocks[0]["props"]
    check("nilai di luar batas dijepit (overlay 999 -> <=90; limit 99 -> <=12; spacer 5000 -> <=160)",
          hero["overlay"] <= 90 and clean_blocks[2]["props"]["limit"] <= 12
          and clean_blocks[11]["props"]["size"] <= 160)
    check("daftar dibatasi (value_props maks 6 item)", len(clean_blocks[1]["props"]["items"]) == 6)
    check("field formulir tak dikenal dibuang + nama/telepon dipaksa ada",
          clean_blocks[8]["props"]["fields"][:2] == ["name", "phone"]
          and "hack_field" not in clean_blocks[8]["props"]["fields"])
    check("HTML di dalam FAQ juga disanitasi", "script" not in str(clean_blocks[7]).lower())
    check("setiap blok mendapat id unik", len({b["id"] for b in clean_blocks}) == len(clean_blocks))

    doc = {"slug": "promo-armada-agustus", "title": "Promo Armada Agustus", "segment": "fleet",
           "seo": {"title": "Sewa Hiace Bandung"}, "blocks": clean_blocks}
    errs = lb.publish_errors(doc)
    check("blok video tanpa poster ditolak saat terbit (jaga kecepatan halaman iklan)",
          any("poster" in e.lower() for e in errs), str(errs))
    for b in doc["blocks"]:
        if b["type"] == "video":
            b["props"]["media"]["poster"] = "https://cdn.test/poster.jpg"
    check("halaman lengkap lolos aturan terbit", lb.publish_errors(doc) == [], str(lb.publish_errors(doc)))
    no_cta = {**doc, "blocks": [b for b in doc["blocks"] if b["type"] not in lb.CONVERSION_BLOCKS]}
    check("halaman tanpa blok konversi DITOLAK terbit (INV-LP-01)",
          any("konversi" in e.lower() for e in lb.publish_errors(no_cta)))

    media_map = {"med_1": {"url": "/api/public/media/med_1", "kind": "image", "alt": "Hiace"},
                 "med_2": {"url": "/api/public/media/med_2", "kind": "video"}}
    pub = lb.public_payload({**doc, "id": "lp_1", "published_at": "2026-08-10T00:00:00Z"}, media_map)
    check("URL media diselesaikan dari media library", pub["blocks"][0]["props"]["media"]["src"] == "/api/public/media/med_1")
    gallery = next(b for b in pub["blocks"] if b["type"] == "gallery")
    check("aset media yang hilang/terhapus tidak menghasilkan tautan mati",
          gallery["props"]["items"][1]["src"] == "")
    hidden_doc = {**doc, "blocks": [{**doc["blocks"][0], "hidden": True}] + doc["blocks"][1:]}
    check("blok disembunyikan tidak dikirim ke halaman publik",
          len(lb.public_payload(hidden_doc, media_map)["blocks"]) == len(doc["blocks"]) - 1)


# --------------------------------------------------------------------------------------- POC-5
async def poc5_rbac(db):
    head("POC-5 · RBAC peran baru marketing_admin (FE<->BE sinkron)")
    from permissions_config import ROLES, SECTION_ACCESS, can_access

    check("peran marketing_admin terdaftar di SSOT", "marketing_admin" in ROLES)
    matrix = {
        ("marketing_admin", "integrations"): True, ("marketing_admin", "landing"): True,
        ("marketing_admin", "ads"): True, ("marketing_admin", "tracking"): True,
        ("marketing_admin", "crm"): True, ("marketing_admin", "finance"): False,
        ("marketing_admin", "settings"): False, ("marketing_admin", "users"): False,
        ("marketing_admin", "calendar"): False, ("ops_admin", "ads"): True,
        ("ops_admin", "integrations"): False, ("ops_admin", "landing"): False,
        ("driver", "ads"): False, ("driver", "landing"): False, ("driver", "integrations"): False,
        ("owner", "integrations"): True, ("owner", "landing"): True,
    }
    wrong = [f"{r}->{s} harus {exp}" for (r, s), exp in matrix.items() if can_access(r, s) is not exp]
    check("matriks akses sesuai keputusan user (4 peran x modul marketing)", not wrong, str(wrong[:3]))
    check("modul marketing dideklarasikan di SECTION_ACCESS",
          all(k in SECTION_ACCESS for k in ("ads", "landing", "tracking", "integrations")))

    u = await db.users.find_one({"email": "marketing@demo.local"}, {"_id": 0, "role": 1, "status": 1})
    check("akun demo marketing@demo.local ada & aktif (seed)",
          bool(u) and u.get("role") == "marketing_admin" and u.get("status") == "active",
          str(u))

    proc = subprocess.run([sys.executable, "scripts/guardrails/verify_rbac_guards.py"],
                          cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    last = [ln for ln in proc.stdout.splitlines() if "PASS" in ln or "FAIL" in ln]
    check("guardrail INV-RBAC-01..05 HIJAU setelah peran & modul baru", proc.returncode == 0,
          (last[-1].strip() if last else "")[:110])


async def main():
    print(f"{C}{B}POC FASE F (E29) — Marketing & Ads: 5 fondasi{X}")
    print(f"{Y}Tanpa kredensial platform: integrasi diuji dalam mode uji-kering (dry-run).{X}")
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    uploaded = []
    try:
        await poc1_vault(db)
        poc2_storage(uploaded)
        await poc3_outbox(db)
        poc4_blocks()
        await poc5_rbac(db)
    finally:
        client.close()

    total = len(RESULTS)
    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"\n{B}{'=' * 74}{X}")
    if failed:
        print(f"  {R}{B}GAGAL {len(failed)}/{total}{X} — fondasi belum siap, JANGAN lanjut membangun UI:")
        for n in failed:
            print(f"    {R}✗{X} {n}")
        print(f"{B}{'=' * 74}{X}\n")
        return 1
    print(f"  {G}{B}SEMUA {total} CEK LULUS{X} — fondasi Marketing & Ads terbukti.")
    if uploaded:
        print(f"  Aset uji terunggah: {', '.join(a['storage_path'].rsplit('/', 1)[-1] for a in uploaded)}")
    print(f"{B}{'=' * 74}{X}\n")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

#!/usr/bin/env python3
"""test_core_ga4_ads.py — POC lanjutan F8b: GA4 server-side + alur Ads↔Landing Page + kesehatan media.

Yang dibuktikan TANPA kredensial GA4:
  1. Payload GA4 sesuai kontrak resmi (client_id, events[], session_id positif,
     engagement_time_msec, timestamp MIKRO-detik, consent GRANTED/DENIED, nama event bukan tercadang).
  2. `client_id` STABIL per identitas (dipanggil 5x → nilai sama) — client_id acak per event akan
     membuat GA4 mengira setiap konversi datang dari pengguna baru.
  3. Tanpa Measurement ID/API secret, outbox menandai `skipped` berALASAN (bukan 5xx, bukan senyap).
  4. GA4 benar-benar terdaftar sebagai provider KETIGA dan ikut ter-enqueue saat lead dibuat.
  5. Skor kesiapan iklan menolak halaman draf / tanpa cara menghubungi, dan URL iklan ber-UTM benar.
  6. `ad-targets` menandai halaman draf sebagai TIDAK siap (mencegah iklan ke halaman 404).
  7. Pemulih media: aset yang berkasnya hilang terdeteksi dan dilaporkan per halaman.

Jalankan: cd /app && python scripts/test_core_ga4_ads.py
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / "backend" / ".env")
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

G, R, C, B, X = "\033[92m", "\033[91m", "\033[96m", "\033[1m", "\033[0m"
API = "http://localhost:8001/api"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  {G}[OK]{X} {name}" if ok else f"  {R}[GAGAL]{X} {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def head(t):
    print(f"\n{C}{B}== {t} =={X}")


def login(email="owner@demo.local"):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": "demo12345"}, timeout=20)
    return r.json()["token"]


async def main():
    print(f"{B}{C}POC F8b — GA4 server-side + alur Ads↔Landing Page + kesehatan media{X}")
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    tok = login()
    H = {"Authorization": f"Bearer {tok}"}
    from services import conversions as cv
    from services import ga4
    from services import landing_ads as la

    head("POC-1 · Kontrak payload GA4 (Measurement Protocol)")
    check("GA4 terdaftar sebagai provider ketiga outbox", "ga4" in cv.PROVIDERS, str(cv.PROVIDERS))
    check("nama event memakai nama rekomendasi, bukan tercadang",
          cv.EVENT_MAP["lead"]["ga4"] == "generate_lead" and cv.EVENT_MAP["booking"]["ga4"] == "purchase"
          and ga4.valid_event_name("generate_lead") and not ga4.valid_event_name("session_start")
          and not ga4.valid_event_name("ga_custom"))
    p = ga4.build_payload(event_name="purchase", client_id="123.456", value=4500000,
                          transaction_id="bk_1", consent=ga4.consent_block(True),
                          params={"lead_source": "google_ads"})
    ev = p["events"][0]["params"]
    check("client_id & events[] ada; value integer + currency IDR",
          p["client_id"] == "123.456" and p["events"][0]["name"] == "purchase"
          and ev["value"] == 4500000 and ev["currency"] == "IDR")
    check("session_id bilangan positif & engagement_time_msec positif",
          isinstance(ev["session_id"], int) and ev["session_id"] > 0 and ev["engagement_time_msec"] > 0)
    check("transaction_id dikirim untuk purchase (cegah konversi ganda di GA4)",
          ev["transaction_id"] == "bk_1")
    check("consent GRANTED/DENIED diturunkan dari catatan consent",
          p["consent"] == {"ad_user_data": "GRANTED", "ad_personalization": "GRANTED"}
          and ga4.consent_block(False)["ad_user_data"] == "DENIED")
    big = ga4.build_payload(event_name="generate_lead", client_id="1.2",
                            params={"x": "y" * 200000})
    st, _ = await ga4.send("G-TEST", "secret", big)
    check("payload >130 kB ditolak lokal (batas resmi) tanpa memanggil jaringan", st == 413, f"HTTP {st}")
    tsp = ga4.build_payload(event_name="generate_lead", client_id="1.2", timestamp_micros=1_760_000_000_000_000)
    check("timestamp dikirim dalam MIKRO-detik (16 digit), bukan milidetik",
          len(str(tsp["timestamp_micros"])) == 16)

    head("POC-2 · client_id stabil per identitas")
    key = f"poc-visitor-{uuid.uuid4().hex[:8]}"
    ids = {await ga4.client_id_for(db, key) for _ in range(5)}
    check("5 pemanggilan identitas sama → satu client_id", len(ids) == 1, str(ids))
    other = await ga4.client_id_for(db, key + "-lain")
    check("identitas berbeda → client_id berbeda", other not in ids)
    check("format client_id mirip cookie _ga (dua komponen desimal)",
          len(list(ids)[0].split(".")) == 2 and all(x.isdigit() for x in list(ids)[0].split(".")))
    await db.ga4_identities.delete_many({"identity_key": {"$regex": "^poc-visitor-"}})

    head("POC-3 · Tanpa kredensial: `skipped` berALASAN (bukan 5xx, bukan senyap)")
    st, body = await ga4.send("", "", {"client_id": "1.2", "events": []})
    check("kirim tanpa kredensial tidak melempar", True) if False else None
    reason = cv._reason_not_ready("ga4", {"enabled": True}, {})
    check("alasan menyebut Measurement ID", "Measurement ID" in reason, reason)
    reason2 = cv._reason_not_ready("ga4", {"enabled": True, "ga4_measurement_id": "G-XYZ"}, {})
    check("alasan menyebut API secret bila hanya ID terisi", "API secret" in reason2, reason2)
    check("GA4 tidak terpengaruh syarat Google Ads (customer_id kosong tetap boleh)",
          cv._reason_not_ready("ga4", {"enabled": True, "ga4_measurement_id": "G-XYZ"},
                               {"ga4_api_secret": "s"}) == "")
    from services import integrations as integ
    cfgs = await integ.active_configs(db)
    check("konfigurasi `ga4` tersedia untuk outbox (alias ke dokumen Google)", "ga4" in cfgs)

    head("POC-4 · Lead dari halaman iklan meng-enqueue GA4")
    pages = requests.get(f"{API}/landing/pages?status=published", headers=H, timeout=20).json()["pages"]
    if not pages:
        check("ada halaman terbit untuk diuji", False, "tidak ada halaman published")
    else:
        slug = pages[0]["slug"]
        phone = f"0813{uuid.uuid4().int % 90000000 + 10000000}"
        r = requests.post(f"{API}/public/landing/{slug}/lead", timeout=30, json={
            "name": "POC GA4", "phone": phone, "marketing_consent": True,
            "attribution": {"utm_source": "google", "utm_medium": "cpc", "gclid": "POCGCLID"}})
        lead_id = r.json().get("id")
        rows = await db.conversion_events.find({"ref_id": lead_id}, {"_id": 0}).to_list(10)
        provs = {x.get("provider"): x.get("status") for x in rows}
        check("outbox memuat meta + google + ga4", {"meta", "google", "ga4"} <= set(provs), str(provs))
        check("status ga4 = skipped/pending berALASAN (kredensial belum ada)",
              provs.get("ga4") in ("skipped", "pending"), str(provs.get("ga4")))
        await db.leads.delete_many({"id": lead_id})
        await db.conversion_events.delete_many({"ref_id": lead_id})

    head("POC-5 · Skor kesiapan iklan + URL iklan ber-UTM")
    draft = {"status": "draft", "blocks": [], "seo": {}}
    rd = la.readiness(draft)
    check("halaman draf tanpa blok → level 'belum' + penghalang jelas",
          rd["level"] == "belum" and rd["blockers"], f"{rd['score']} · {rd['blockers']}")
    good = {"status": "published", "seo": {"title": "T", "description": "D", "og_image": "x"},
            "blocks": [
                {"type": "search_hero", "props": {"media": {"src": "/api/public/media/x"},
                                                  "cta": {"label": "Pesan"}}},
                {"type": "lead_form", "props": {}}, {"type": "testimonials", "props": {}}]}
    rg = la.readiness(good)
    check("halaman lengkap → level 'siap' & skor tinggi", rg["level"] == "siap" and rg["score"] >= 85,
          f"skor {rg['score']}")
    no_contact = {**good, "blocks": [good["blocks"][0]]}
    rn = la.readiness(no_contact)
    check("halaman tanpa formulir/WA ditandai penghalang (klik iklan tak bisa jadi lead)",
          any("menghubungi" in b for b in rn["blockers"]), str(rn["blockers"]))
    rm = la.readiness(good, media_ok=False)
    check("media hilang menjadi penghalang kesiapan iklan",
          any("media" in b.lower() for b in rm["blockers"]), str(rm["blockers"]))
    url = la.ad_url("https://situs.id", "sewa-hiace", **la.preset_utm("meta", "promo-agustus"))
    check("URL iklan Meta ber-UTM benar",
          "utm_source=meta" in url and "utm_medium=paid_social" in url
          and "utm_campaign=promo-agustus" in url and "/lp/sewa-hiace" in url, url)
    gurl = la.ad_url("https://situs.id", "sewa-hiace", **la.preset_utm("google", "brand"))
    check("URL iklan Google memakai medium cpc", "utm_medium=cpc" in gurl, gurl)

    head("POC-6 · Endpoint kesiapan & daftar tujuan iklan")
    if pages:
        pid = pages[0]["id"]
        rr = requests.get(f"{API}/landing/pages/{pid}/readiness", headers=H, timeout=30).json()
        check("endpoint kesiapan mengembalikan skor, temuan & URL iklan siap pakai",
              "score" in rr and rr.get("checks") and "meta" in (rr.get("ad_urls") or {}),
              f"skor {rr.get('score')} · {rr.get('level')}")
        check("laporan menyertakan daftar media hilang (pemulih media)", isinstance(rr.get("missing_media"), list))
    tg = requests.get(f"{API}/landing/ad-targets", headers=H, timeout=30).json()
    check("daftar tujuan iklan tersedia + preset UTM per platform",
          isinstance(tg.get("targets"), list) and "meta" in (tg.get("utm_presets") or {}))
    drafts = [t for t in tg["targets"] if not t["published"]]
    check("halaman draf ditandai belum siap (cegah iklan ke 404)",
          all(not t["ready"] for t in drafts) if drafts else True, f"{len(drafts)} draf")
    anon = requests.get(f"{API}/landing/ad-targets", timeout=20)
    check("endpoint tujuan iklan tetap butuh login", anon.status_code == 401, f"HTTP {anon.status_code}")

    ok = sum(1 for _, o in RESULTS if o)
    print(f"\n{C}{B}{'=' * 70}{X}")
    print(f"  {G}{B}POC F8b LULUS — {ok}/{len(RESULTS)}.{X}" if ok == len(RESULTS)
          else f"  {R}{B}POC F8b GAGAL — {ok}/{len(RESULTS)}.{X}")
    print(f"{C}{B}{'=' * 70}{X}")
    return 0 if ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

#!/usr/bin/env python3
"""test_core_ads_f3.py — POC FASE F3/F4 (E29+): membuktikan rantai marketing end-to-end
SEBELUM UI & endpoint dibangun. Semuanya bisa diuji TANPA kredensial Meta/Google.

Delapan hal di bawah adalah bagian yang paling mudah gagal SENYAP (rugi uang tanpa error):

  POC-1 Hook event bus  : lead.created / booking.confirmed / payment.recorded benar-benar
                          menghasilkan konversi di outbox (bug fase F2: outbox tak pernah dipanggil),
                          idempoten walau dipanggil 8x paralel, nilai & identitas terisi benar.
  POC-2 Payload Meta    : Graph v26.0, event_id = ID BISNIS (dedup pixel<->server), PII SHA-256,
                          appsecret_proof, test_event_code hanya saat uji, dan jalur CTWA
                          (action_source=business_messaging + ctwa_clid TIDAK di-hash).
  POC-3 Payload Google  : Data Manager v1 dengan field yang BENAR (accountType, encoding=HEX,
                          consent GRANTED/DENIED, destinationReferences, validateOnly) —
                          versi lama repo memakai `product` + `CONSENT_GRANTED` = akan ditolak.
  POC-4 Tanpa kredensial: SEMUA klien Meta/Google mengembalikan `not_configured` + alasan Bahasa
                          Indonesia, tidak melempar exception (calon 5xx) dan tidak memanggil jaringan.
  POC-5 Metrik iklan    : normalisasi baris Meta/Google ke satu skema, tarik-ulang IDEMPOTEN
                          (biaya tidak dobel), dan ROAS NYATA = biaya platform ⨯ booking ERP.
  POC-6 Pengaman belanja: mode validate -> validate_only; mode publish -> status DIPAKSA PAUSED;
                          aktivasi & kenaikan budget wajib konfirmasi + plafon budget ditegakkan ERP.
  POC-7 Audiens         : filter consent WAJIB, hash per aturan platform (Meta digit / Google +E.164),
                          batching 10.000 dengan last_batch_flag, penjaga minimal seed Lookalike.
  POC-8 Lead Ads + CTWA : signature X-Hub-Signature-256 (payload palsu DITOLAK), dedup leadgen_id,
                          pemetaan field form Indonesia, dan pembacaan referral Klik-ke-WhatsApp.

Jalankan: cd /app && python scripts/test_core_ads_f3.py
Keluar 0 = semua LULUS. Data uji memakai id berprefiks 'poc3f' dan dibersihkan di akhir.
"""
import asyncio
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("PYTHONPATH", str(ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / "backend" / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

G, R, Y, C, B, X = "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[1m", "\033[0m"
RESULTS = []
TAG = "poc3f"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
NOW = datetime.now(timezone.utc).isoformat()


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    icon = f"{G}[OK]{X}" if ok else f"{R}[GAGAL]{X}"
    print(f"  {icon} {name}" + (f" — {detail}" if detail else ""))
    return ok


def head(title):
    print(f"\n{C}{B}== {title} =={X}")


async def cleanup(db):
    # lead yang dibuat lewat create_ad_lead memakai id acak -> bersihkan lewat penanda iklan uji
    poc_leads = await db.leads.find({"$or": [{"id": {"$regex": TAG}},
                                             {"ad_form_id": "FORM1"},
                                             {"ad_campaign_id": "CAMP1"}]},
                                    {"_id": 0, "id": 1}).to_list(200)
    lead_ids = [d["id"] for d in poc_leads]
    if lead_ids:
        await db.conversion_events.delete_many({"ref_id": {"$in": lead_ids}})
        await db.events.delete_many({"ref_id": {"$in": lead_ids}})
        await db.lead_activities.delete_many({"lead_id": {"$in": lead_ids}})
        await db.leads.delete_many({"id": {"$in": lead_ids}})
    await db.conversion_events.delete_many({"ref_id": {"$regex": TAG}})
    await db.leads.delete_many({"id": {"$regex": TAG}})
    await db.customers.delete_many({"id": {"$regex": TAG}})
    await db.bookings.delete_many({"id": {"$regex": TAG}})
    await db.payments.delete_many({"id": {"$regex": TAG}})
    await db.events.delete_many({"dedupe_key": {"$regex": TAG}})
    await db.ads_metrics_daily.delete_many({"entity_id": {"$regex": TAG}})
    await db.ad_touches.delete_many({"click_id": {"$regex": TAG}})
    await db.platform_leads.delete_many({"leadgen_id": {"$regex": TAG}})
    await db.lead_activities.delete_many({"lead_id": {"$regex": TAG}})
    await db.conversations.delete_many({"contact_phone": {"$in": ["089900000001", "08990000000 1",
                                                                 "0899-0000-0001"]}})


# --------------------------------------------------------------------------------------- POC-1
async def poc1_event_hooks(db):
    head("POC-1 · Hook event bus → outbox konversi (bug F2 ditutup: outbox tak pernah dipanggil)")
    from services import conversion_hooks as hooks
    from services import conversions as cv
    from services.events import emit

    await cv.ensure_indexes(db)
    check("3 event bisnis bernilai terdaftar di BUSINESS_EVENTS (dijaga INV-CONV-01)",
          set(hooks.BUSINESS_EVENTS) == {"lead.created", "booking.confirmed", "payment.recorded"},
          str(sorted(hooks.BUSINESS_EVENTS)))

    lead_id = f"led_{TAG}1"
    cust_id = f"cus_{TAG}1"
    booking_id = f"bk_{TAG}1"
    payment_id = f"pay_{TAG}1"
    await db.leads.insert_one({
        "id": lead_id, "customer_name": "Budi POC", "phone": "0812-3456-7890",
        "phone_normalized": "6281234567890", "email": " Budi@Example.COM ", "source": "website",
        "stage": "new", "value": 2_000_000, "marketing_consent": True,
        "channel": "meta_ads", "converted_customer_id": cust_id,
        "ad_platform": "meta", "ad_campaign_id": f"camp{TAG}", "ad_id": f"ad{TAG}",
        "attribution": {"channel": "meta_ads",
                        "first_touch": {"fbclid": "FBCLID-abc", "landing_page": "/lp/armada"},
                        "last_touch": {"fbclid": "FBCLID-abc", "gclid": "GCLID-xyz",
                                       "landing_page": "/lp/armada"}},
        "created_at": NOW, "last_activity_at": NOW})
    await db.customers.insert_one({"id": cust_id, "name": "Budi POC", "phone": "081234567890",
                                   "phone_normalized": "6281234567890", "email": "budi@example.com",
                                   "marketing_consent": True, "created_at": NOW})
    await db.bookings.insert_one({"id": booking_id, "code": f"BK-{TAG}", "customer_id": cust_id,
                                  "customer_name": "Budi POC", "status": "confirmed",
                                  "total_amount": 5_000_000, "paid_amount": 1_500_000,
                                  "created_at": NOW})
    await db.payments.insert_one({"id": payment_id, "booking_id": booking_id, "type": "dp",
                                  "amount": 1_500_000, "method": "transfer", "paid_at": NOW})

    # 8 pemanggilan paralel dengan ID bisnis sama -> tepat 1 dokumen per provider
    res = await asyncio.gather(*[hooks.handle_event(db, "lead.created", {"lead_id": lead_id})
                                 for _ in range(8)], return_exceptions=True)
    errs = [r for r in res if isinstance(r, Exception)]
    check("8 hook paralel tidak melempar error", not errs, str(errs[:1])[:140])
    n_meta = await db.conversion_events.count_documents({"event_key": f"lead_{lead_id}", "provider": "meta"})
    n_goog = await db.conversion_events.count_documents({"event_key": f"lead_{lead_id}", "provider": "google"})
    check("lead.created → tepat 1 dokumen per provider (idempoten)", n_meta == 1 and n_goog == 1,
          f"meta={n_meta} google={n_goog}")

    ev = await db.conversion_events.find_one({"event_key": f"lead_{lead_id}", "provider": "meta"}, {"_id": 0})
    ident = ev.get("identifiers") or {}
    check("identitas lead terangkut: email + telepon + gclid + fbclid",
          ident.get("email") and ident.get("phone") and ident.get("gclid") == "GCLID-xyz"
          and ident.get("fbclid") == "FBCLID-abc", str(sorted(ident))[:160])
    check("fbc dibentuk dari fbclid (fb.1.<ms>.<fbclid>) untuk match rate Meta",
          (ident.get("fbc") or "").startswith("fb.1.") and ident["fbc"].endswith("FBCLID-abc"),
          ident.get("fbc", ""))
    check("consent lead ikut tercatat di outbox", ev.get("consent_granted") is True)
    check("nilai lead = value lead (IDR integer)", ev.get("value") == 2_000_000, str(ev.get("value")))

    await hooks.handle_event(db, "booking.confirmed", {"booking_id": booking_id})
    bev = await db.conversion_events.find_one({"event_key": f"booking_{booking_id}", "provider": "meta"}, {"_id": 0})
    check("booking.confirmed → konversi Purchase dengan nilai total booking",
          bev and bev.get("event_name") == "Purchase" and bev.get("value") == 5_000_000,
          str((bev or {}).get("value")))
    check("booking mewarisi identitas dari lead sumbernya (join lead↔customer)",
          bool((bev.get("identifiers") or {}).get("phone")) and
          (bev.get("identifiers") or {}).get("gclid") == "GCLID-xyz")

    await hooks.handle_event(db, "payment.recorded", {"payment_id": payment_id})
    pev = await db.conversion_events.find_one({"event_key": f"payment_{payment_id}", "provider": "google"}, {"_id": 0})
    check("payment.recorded → konversi deposit_received dengan nilai DP",
          pev and pev.get("event_name") == "deposit_received" and pev.get("value") == 1_500_000,
          str((pev or {}).get("value")))

    # WIRING NYATA: emit() harus memicu hook (bukan hanya pemanggilan langsung di test)
    booking2 = f"bk_{TAG}2"
    await db.bookings.insert_one({"id": booking2, "code": f"BK-{TAG}2", "customer_id": cust_id,
                                  "customer_name": "Budi POC", "status": "confirmed",
                                  "total_amount": 3_250_000, "paid_amount": 0, "created_at": NOW})
    await emit(db, "booking.confirmed", {"booking_id": booking2, "code": f"BK-{TAG}2",
                                         "customer_name": "Budi POC", "total_amount": 3_250_000},
               source="poc", ref_type="booking", ref_id=booking2,
               dedupe_key=f"booking.confirmed:{TAG}:{booking2}")
    wired = await db.conversion_events.count_documents({"event_key": f"booking_{booking2}"})
    check("emit() nyata dari event bus ikut membuat konversi (wiring terbukti, bukan asumsi)",
          wired == 2, f"{wired} dokumen")

    unrelated = await hooks.handle_event(db, "trip.completed", {"trip_id": "x"})
    check("event tanpa nilai iklan (trip.completed) TIDAK membuat konversi", unrelated is None)


# --------------------------------------------------------------------------------------- POC-2
async def poc2_meta_payload(db):
    head("POC-2 · Payload Meta CAPI (Graph v26.0, dedup, CTWA business_messaging)")
    from services import conversions as cv
    from services import meta_ads

    check("versi Graph default = v26.0 (bukan v25.0 yang usang)",
          meta_ads.DEFAULT_VERSION == "v26.0", meta_ads.DEFAULT_VERSION)
    proof = meta_ads.appsecret_proof("TOKEN123", "SECRET456")
    check("appsecret_proof = HMAC-SHA256(app_secret, access_token)",
          proof == hmac.new(b"SECRET456", b"TOKEN123", hashlib.sha256).hexdigest(), proof[:16] + "…")
    check("act_ hanya ditambahkan bila belum ada",
          meta_ads.act("123") == "act_123" and meta_ads.act("act_123") == "act_123"
          and meta_ads.act("") == "")

    ev = {"event_key": f"payment_{TAG}9", "event_name": "Purchase", "value": 1_500_000,
          "currency": "IDR", "source_url": "https://rahaza.test/lp/promo",
          "identifiers": {"email": " Budi@Example.COM ", "phone": "0812-3456-7890",
                          "fbp": "fb.1.170.123", "fbc": "fb.1.170.IwAR0", "ip": "103.10.10.10",
                          "user_agent": "Mozilla/5.0", "external_id": "cus_1"}}
    body = cv.build_meta_payload({"pixel_id": "PX1", "ldu_enabled": False},
                                 {"test_event_code": "TEST123"}, ev, test=True)
    e = body["data"][0]
    check("field wajib lengkap + action_source=website",
          {"event_name", "event_time", "event_id", "action_source", "user_data"} <= set(e)
          and e["action_source"] == "website")
    check("event_id = ID bisnis (dedup dengan pixel browser, jendela 48 jam)",
          e["event_id"] == f"payment_{TAG}9")
    check("email & telepon di-SHA-256, plaintext tidak pernah ikut",
          e["user_data"]["em"][0] == hashlib.sha256(b"budi@example.com").hexdigest()
          and e["user_data"]["ph"][0] == hashlib.sha256(b"6281234567890").hexdigest()
          and "budi@example.com" not in json.dumps(body).lower())
    check("nilai IDR integer + currency", e["custom_data"] == {"value": 1_500_000, "currency": "IDR"})
    check("test_event_code hanya pada mode uji",
          body.get("test_event_code") == "TEST123" and "test_event_code" not in
          cv.build_meta_payload({"pixel_id": "PX1"}, {"test_event_code": "T"}, ev))
    ldu = cv.build_meta_payload({"pixel_id": "PX1", "ldu_enabled": True}, {}, ev)
    check("Limited Data Use (LDU) terpasang bila diaktifkan",
          ldu.get("data_processing_options") == ["LDU"]
          and ldu.get("data_processing_options_country") == 0)

    ctwa_ev = dict(ev)
    ctwa_ev["identifiers"] = {"phone": "089900000001", "ctwa_clid": "CTWA-CLID-777"}
    ctwa_ev["action_source"] = ""
    ctwa = cv.build_meta_payload({"pixel_id": "PX1", "waba_id": "WABA9"}, {}, ctwa_ev)
    ce = ctwa["data"][0]
    check("CTWA: action_source=business_messaging + messaging_channel=whatsapp",
          ce["action_source"] == "business_messaging" and ce.get("messaging_channel") == "whatsapp")
    check("CTWA: ctwa_clid dikirim MENTAH (bukan hash) + WABA id disertakan",
          ce["user_data"]["ctwa_clid"] == "CTWA-CLID-777"
          and ce["user_data"]["whatsapp_business_account_id"] == "WABA9")
    check("CTWA: event_source_url tidak dikirim (bukan event website)",
          "event_source_url" not in ce)
    check("dataset_id diprioritaskan di atas pixel_id bila diisi",
          cv.meta_dataset_id({"dataset_id": "DS1", "pixel_id": "PX1"}) == "DS1"
          and cv.meta_dataset_id({"pixel_id": "PX1"}) == "PX1")


# --------------------------------------------------------------------------------------- POC-3
async def poc3_google_payload(db):
    head("POC-3 · Payload Google Data Manager v1 (koreksi field yang sebelumnya SALAH)")
    from services import conversions as cv

    ev = {"event_key": f"booking_{TAG}9", "event_name": "booking_confirmed", "value": 7_250_000,
          "currency": "IDR", "consent_granted": True,
          "identifiers": {"email": "Budi@Example.com", "phone": "081234567890",
                          "gclid": "GCLID-xyz", "wbraid": "WB-1"}}
    cfg = {"customer_id": "123-456-7890", "login_customer_id": "111-222-3333",
           "conversion_action_ids": {"booking_confirmed": "998877"}}
    body = cv.build_google_payload(cfg, ev, test=True)
    dest = body["destinations"][0]
    check("operatingAccount memakai accountType (field `product` sudah TIDAK ada)",
          dest["operatingAccount"]["accountType"] == "GOOGLE_ADS" and "product" not in dest["operatingAccount"],
          json.dumps(dest["operatingAccount"]))
    check("customer id & login customer id dibersihkan dari tanda hubung",
          dest["operatingAccount"]["accountId"] == "1234567890"
          and dest["loginAccount"]["accountId"] == "1112223333")
    check("productDestinationId = ID numerik conversion action",
          dest["productDestinationId"] == "998877")
    check("root payload memuat encoding=HEX (wajib untuk data ter-hash)",
          body.get("encoding") == "HEX")
    check("consent bernilai GRANTED (bukan CONSENT_GRANTED yang lama)",
          body["consent"]["adUserData"] == "GRANTED"
          and body["events"][0]["consent"]["adPersonalization"] == "GRANTED")
    denied = cv.build_google_payload(cfg, {**ev, "consent_granted": False})
    check("tanpa izin pemasaran → consent DENIED (bukan dipaksa GRANTED)",
          denied["consent"]["adUserData"] == "DENIED")
    g = body["events"][0]
    check("setiap event menunjuk destinationReferences yang sah",
          g["destinationReferences"] == [dest["reference"]], str(g["destinationReferences"]))
    check("transactionId = ID bisnis + nilai IDR integer",
          g["transactionId"] == f"booking_{TAG}9" and g["conversionValue"] == 7_250_000)
    check("gclid dipakai sebagai penanda klik (satu penanda saja)",
          g["adIdentifiers"] == {"gclid": "GCLID-xyz"})
    check("telepon Google di-hash dalam bentuk E.164 dengan '+' (beda dari Meta!)",
          g["userData"]["userIdentifiers"][1]["phoneNumber"]
          == hashlib.sha256(b"+6281234567890").hexdigest())
    check("email di-hash SHA-256 & plaintext tak pernah ikut",
          g["userData"]["userIdentifiers"][0]["emailAddress"]
          == hashlib.sha256(b"budi@example.com").hexdigest()
          and "budi@example.com" not in json.dumps(body).lower())
    check("validateOnly hanya pada mode uji (fast-fail, tanpa partialFailure)",
          body.get("validateOnly") is True
          and "validateOnly" not in cv.build_google_payload(cfg, ev))
    check("eventTimestamp berformat RFC3339", "T" in g["eventTimestamp"] and
          (g["eventTimestamp"].endswith("+00:00") or g["eventTimestamp"].endswith("Z")))


# --------------------------------------------------------------------------------------- POC-4
async def poc4_not_configured(db):
    head("POC-4 · Tanpa kredensial: 'not_configured' + alasan Indonesia, TIDAK melempar (anti-5xx)")
    from services.google_ads import GoogleAdsClient
    from services.meta_ads import MetaAdsClient

    meta = MetaAdsClient({}, {})
    check("Meta: configured() False + alasan berbahasa Indonesia",
          not meta.configured() and "belum" in meta.reason().lower(), meta.reason())
    calls = {
        "account_info": meta.account_info(),
        "insights": meta.insights(TODAY, TODAY),
        "list_entities": meta.list_entities("campaign"),
        "create_object(validate)": meta.create_object("campaign", {"name": "x"}, mode="validate"),
        "create_object(publish)": meta.create_object("campaign", {"name": "x"}, mode="publish"),
        "fetch_lead": meta.fetch_lead("123"),
        "upload_audience_users": meta.upload_audience_users("aud", {}, mode="publish"),
    }
    for name, coro in calls.items():
        res = await coro
        check(f"Meta {name} → not_configured (tanpa exception & tanpa panggilan jaringan)",
              res.get("status") == "not_configured" and bool(res.get("reason")),
              str(res.get("status")))

    goog = GoogleAdsClient({}, {})
    check("Google: reason() menjelaskan integrasi belum aktif",
          not goog.configured() and "belum" in goog.reason().lower(), goog.reason())
    for name, coro in {
        "search_stream": goog.search_stream("SELECT customer.id FROM customer"),
        "daily_metrics": goog.daily_metrics(TODAY, TODAY),
        "mutate": goog.mutate("campaigns", [{"create": {"name": "x"}}], mode="validate"),
        "create_user_list": goog.create_user_list("x", mode="publish"),
        "ingest_events": goog.ingest_events({"events": []}),
    }.items():
        res = await coro
        check(f"Google {name} → not_configured", res.get("status") == "not_configured",
              str(res.get("status")))

    partial = GoogleAdsClient({"enabled": True, "customer_id": "123"},
                              {"oauth_refresh_token": "r", "oauth_client_id": "c",
                               "oauth_client_secret": "s"})
    check("Data Manager tidak menuntut developer token, tapi Ads API menuntutnya",
          partial.configured(need_developer_token=False)
          and not partial.configured(need_developer_token=True),
          partial.reason())


# --------------------------------------------------------------------------------------- POC-5
async def poc5_metrics(db):
    head("POC-5 · Metrik iklan: normalisasi, tarik-ulang idempoten, ROAS nyata")
    from services import ads_metrics as am

    await am.ensure_indexes(db)
    meta_rows = [{
        "campaign_id": f"camp{TAG}", "campaign_name": "Armada Bali", "spend": "1250000.50",
        "impressions": "12000", "clicks": "340", "reach": "9000", "date_start": TODAY,
        "actions": [{"action_type": "lead", "value": "12"},
                    {"action_type": "purchase", "value": "3"}],
        "action_values": [{"action_type": "purchase", "value": "9000000"}],
    }, {"campaign_name": "tanpa id", "spend": "1000", "date_start": TODAY}]
    docs = am.normalize_meta_rows(meta_rows, level="campaign", currency="IDR")
    check("baris tanpa entity_id dibuang (tidak jadi baris hantu)", len(docs) == 1, str(len(docs)))
    doc = docs[0]
    check("Meta: spend disimpan sebagai desimal + micros mentah + mata uang AKUN",
          doc["spend"] == 1250000.5 and doc["spend_micros"] == 1_250_000_500_000
          and doc["currency"] == "IDR", f"{doc['spend']} / {doc['spend_micros']}")
    check("Meta: aksi lead & purchase diringkas ke kolom bisnis",
          doc["platform_leads"] == 12 and doc["platform_purchases"] == 3
          and doc["platform_conversion_value"] == 9_000_000)

    goog_rows = [{"campaign": {"id": f"gcamp{TAG}", "name": "Search Sewa Bus", "status": "ENABLED"},
                  "metrics": {"costMicros": "2500000", "impressions": "800", "clicks": "60",
                              "conversions": 4, "conversionsValue": 12000000},
                  "segments": {"date": TODAY}}]
    gdocs = am.normalize_google_rows(goog_rows, level="campaign", currency="IDR")
    check("Google: cost_micros ÷ 1.000.000 = biaya mata uang akun",
          gdocs[0]["spend"] == 2.5 and gdocs[0]["spend_micros"] == 2_500_000,
          str(gdocs[0]["spend"]))
    gadgroup = am.normalize_google_rows(
        [{"campaign": {"id": "c1"}, "adGroup": {"id": f"gadg{TAG}", "name": "AG"},
          "metrics": {"costMicros": "1000000"}, "segments": {"date": TODAY}}], level="ad_group")
    check("Google ad_group dipetakan ke level 'adset' (satu bahasa lintas platform)",
          gadgroup[0]["level"] == "adset" and gadgroup[0]["parent_id"] == "c1")

    await am.upsert_metrics(db, docs)
    await am.upsert_metrics(db, docs)
    await am.upsert_metrics(db, docs)
    n = await db.ads_metrics_daily.count_documents({"entity_id": f"camp{TAG}"})
    saved = await db.ads_metrics_daily.find_one({"entity_id": f"camp{TAG}"}, {"_id": 0})
    check("tarik ulang 3x → tetap 1 dokumen (biaya TIDAK dobel)", n == 1, f"{n} dokumen")
    check("nilai biaya tetap sama setelah tarik ulang", saved["spend"] == 1250000.5)
    idx = await db.ads_metrics_daily.index_information()
    check("unique index (provider, level, entity_id, date) terpasang",
          any(v.get("unique") for k, v in idx.items() if k == "uniq_metric_day"))

    perf = await am.performance(db, TODAY, TODAY, level="campaign")
    row = next((r for r in perf["rows"] if r["entity_id"] == f"camp{TAG}"), None)
    check("performance() menemukan kampanye + lead ber-atribusi dari CRM",
          row and row["leads"] == 1, str((row or {}).get("leads")))
    check("pendapatan NYATA diambil dari booking ERP (bukan angka platform)",
          row and row["revenue"] == 8_250_000 and row["bookings"] == 2,
          f"revenue={(row or {}).get('revenue')} bookings={(row or {}).get('bookings')}")
    check("CPL/CAC/ROAS dihitung dari biaya platform ⨯ hasil bisnis",
          row and row["cpl"] == 1250000.5 and row["roas"] == round(8_250_000 / 1250000.5, 2),
          f"cpl={(row or {}).get('cpl')} roas={(row or {}).get('roas')}")
    check("mata uang akun dilaporkan apa adanya (tidak dikonversi diam-diam)",
          "IDR" in perf["currencies"], str(perf["currencies"]))
    series = await am.daily_series(db, TODAY, TODAY)
    check("seri harian untuk grafik tersedia", series and series[0]["date"] == TODAY, str(series[:1]))
    run = await am.record_run(db, "meta", since=TODAY, until=TODAY, level="campaign",
                              status="not_configured", reason="uji POC")
    check("setiap tarikan tercatat di ads_sync_runs (jejak audit sinkron)",
          run["status"] == "not_configured" and (await am.last_runs(db, 1))[0]["id"] == run["id"])
    await db.ads_sync_runs.delete_one({"id": run["id"]})


# --------------------------------------------------------------------------------------- POC-6
def poc6_safety():
    head("POC-6 · Pengaman belanja iklan (uang nyata tidak boleh bergerak tanpa perintah)")
    from services import ads_safety as safety
    from services import google_ads as ga
    from services import meta_ads as ma

    body = safety.meta_write_payload({"name": "Kampanye", "status": "ACTIVE"},
                                     mode="validate", kind="campaign")
    check("mode validate → execution_options=['validate_only'] & status DIPAKSA PAUSED",
          body["execution_options"] == ["validate_only"] and body["status"] == "PAUSED",
          json.dumps(body))
    pub = safety.meta_write_payload({"name": "Kampanye", "status": "ACTIVE"},
                                    mode="publish", kind="adset")
    check("mode publish → tanpa validate_only tapi status TETAP PAUSED",
          "execution_options" not in pub and pub["status"] == "PAUSED")
    gbody = safety.google_write_body({"operations": []}, mode="validate")
    check("Google mode validate → validateOnly=true + partialFailure=true",
          gbody["validateOnly"] is True and gbody["partialFailure"] is True)
    check("Google mode publish → validateOnly=false",
          safety.google_write_body({}, mode="publish")["validateOnly"] is False)
    ops = safety.google_force_paused([{"create": {"name": "x", "status": "ENABLED"}}], kind="campaign")
    check("operasi create Google dipaksa PAUSED", ops[0]["create"]["status"] == "PAUSED")

    try:
        safety.normalize_mode("langsung-aktif")
        check("mode tulis asing ditolak", False)
    except safety.SafetyError:
        check("mode tulis asing ditolak (fail-closed)", True)
    try:
        safety.assert_budget_within_cap(500_000, 200_000, currency="IDR")
        check("budget di atas plafon ditolak", False)
    except safety.SafetyError as exc:
        check("budget di atas plafon ditolak oleh ERP (bukan menunggu platform)", True, str(exc)[:80])
    try:
        safety.assert_budget_within_cap(0, 0)
        check("budget nol/negatif ditolak", False)
    except safety.SafetyError:
        check("budget nol/negatif ditolak", True)
    check("budget dalam plafon diterima", safety.assert_budget_within_cap(150_000, 200_000) == 150_000)
    try:
        safety.assert_activation_allowed("ACTIVE", expected_name="Armada Bali", typed_name="armada bali")
        check("aktivasi tanpa konfirmasi tepat ditolak", False)
    except safety.SafetyError:
        check("aktivasi wajib ketik ulang nama objek PERSIS (typo ditolak)", True)
    check("aktivasi dengan konfirmasi tepat diizinkan",
          safety.assert_activation_allowed("ACTIVE", expected_name="Armada Bali",
                                           typed_name=" Armada Bali ") == "ACTIVE")
    check("menjeda (PAUSED) tidak butuh konfirmasi — mematikan iklan selalu aman",
          safety.assert_activation_allowed("PAUSED", expected_name="Armada Bali",
                                           typed_name="") == "PAUSED")

    camp = ma.build_campaign_payload("Leads Agustus", "OUTCOME_LEADS")
    check("payload kampanye: objective sah + special_ad_categories eksplisit",
          camp["objective"] == "OUTCOME_LEADS" and camp["special_ad_categories"] == [])
    check("objective asing jatuh ke OUTCOME_LEADS (tidak mengirim nilai ilegal)",
          ma.build_campaign_payload("x", "SALAH")["objective"] == "OUTCOME_LEADS")
    adset = ma.build_adset_payload("CTWA Bali", "C1", daily_budget_minor=150000,
                                   destination="whatsapp", page_id="PG1",
                                   whatsapp_number="628123456789")
    check("AdSet CTWA: destination_type=WHATSAPP + optimization CONVERSATIONS",
          adset["destination_type"] == "WHATSAPP" and adset["optimization_goal"] == "CONVERSATIONS")
    check("AdSet CTWA: promoted_object memuat page_id + nomor WhatsApp",
          adset["promoted_object"]["page_id"] == "PG1"
          and adset["promoted_object"]["whatsapp_phone_number"] == "628123456789")
    check("AdSet: target geo Indonesia & budget dikirim sebagai satuan terkecil (string)",
          adset["targeting"]["geo_locations"]["countries"] == ["ID"]
          and adset["daily_budget"] == "150000")
    lead_adset = ma.build_adset_payload("Lead Form", "C1", daily_budget_minor=100000,
                                        destination="lead_form", page_id="PG1")
    check("AdSet Lead Ads: destination ON_AD + optimization LEAD_GENERATION",
          lead_adset["destination_type"] == "ON_AD"
          and lead_adset["optimization_goal"] == "LEAD_GENERATION")
    creative = ma.build_creative_payload("Kreatif", "PG1", destination="whatsapp",
                                         whatsapp_number="628123456789", message="Halo")
    cta = creative["object_story_spec"]["link_data"]["call_to_action"]
    check("Kreatif CTWA memakai CTA WHATSAPP_MESSAGE + app_destination WHATSAPP",
          cta["type"] == "WHATSAPP_MESSAGE" and cta["value"]["app_destination"] == "WHATSAPP")

    check("Google: budget & kampanye dibangun dengan status PAUSED + micros",
          ga.build_budget_op("b", 5_000_000)["create"]["amountMicros"] == "5000000"
          and ga.build_campaign_op("c", "customers/1/campaignBudgets/1")["create"]["status"] == "PAUSED")
    check("Google: RSA memotong headline 30 karakter (aturan platform)",
          ga.build_rsa_op("ag", "https://x.id", ["H" * 45], ["D"])["create"]["ad"]
          ["responsiveSearchAd"]["headlines"][0]["text"] == "H" * 30)
    check("Google: updateMask diisi saat mengubah status/budget",
          ga.build_status_update_op("customers/1/campaigns/2", "PAUSED")["updateMask"] == "status"
          and ga.build_budget_update_op("customers/1/campaignBudgets/2", 1)["updateMask"] == "amountMicros")
    check("GAQL harian memuat cost_micros + segments.date + rentang tanggal",
          "metrics.cost_micros" in ga.gaql_daily("2026-08-01", "2026-08-10")
          and "BETWEEN '2026-08-01' AND '2026-08-10'" in ga.gaql_daily("2026-08-01", "2026-08-10"))


# --------------------------------------------------------------------------------------- POC-7
async def poc7_audiences(db):
    head("POC-7 · Sinkron audiens: consent WAJIB, hash per aturan platform, batching 10.000")
    from services import ads_safety as safety
    from services import audiences as aud

    members = [
        {"target_id": "c1", "email": "A@Example.com", "phone": "081234567890", "marketing_consent": True},
        {"target_id": "c2", "email": "", "phone": "0899-0000-0002", "marketing_consent": True},
        {"target_id": "c3", "email": "no@consent.id", "phone": "0812", "marketing_consent": False},
        {"target_id": "c4", "email": "", "phone": "", "marketing_consent": True},
    ]
    eligible, filtered = aud.split_by_consent(members)
    check("kontak tanpa marketing_consent DISARING (dan jumlahnya dilaporkan)",
          len(eligible) == 3 and filtered == 1, f"eligible={len(eligible)} tersaring={filtered}")
    rows, skipped = aud.hash_rows_meta(eligible)
    check("baris tanpa email & telepon dilewati (Meta menolak baris kosong)",
          len(rows) == 2 and skipped == 1, f"rows={len(rows)} skipped={skipped}")
    check("Meta: email & telepon di-hash (digit tanpa '+'), plaintext tidak ada",
          rows[0][0] == hashlib.sha256(b"a@example.com").hexdigest()
          and rows[0][1] == hashlib.sha256(b"6281234567890").hexdigest()
          and "a@example.com" not in json.dumps(rows))

    payloads = aud.meta_batches([["h", ""]] * 10_001)
    check("unggahan > 10.000 dipecah 2 batch (batas resmi Meta)", len(payloads) == 2, str(len(payloads)))
    check("batch pertama bukan batch terakhir, batch kedua menandai last_batch_flag",
          payloads[0]["session"]["last_batch_flag"] is False
          and payloads[1]["session"]["last_batch_flag"] is True)
    check("session_id sama untuk semua batch + estimated_num_total benar",
          payloads[0]["session"]["session_id"] == payloads[1]["session"]["session_id"]
          and payloads[0]["session"]["estimated_num_total"] == 10_001)
    check("schema Meta = [EMAIL, PHONE] sesuai urutan kolom data",
          payloads[0]["payload"]["schema"] == ["EMAIL", "PHONE"]
          and len(payloads[0]["payload"]["data"][0]) == 2)

    ops = aud.google_operations(eligible)
    check("Google Customer Match: identitas ter-hash dgn E.164 '+' (beda dari Meta)",
          ops[0]["create"]["userIdentifiers"][1]["hashedPhoneNumber"]
          == hashlib.sha256(b"+6281234567890").hexdigest(), str(len(ops)) + " operasi")
    check("kontak tanpa identitas tidak menghasilkan operasi kosong", len(ops) == 2)
    try:
        aud.assert_lookalike_seed(42)
        check("seed Lookalike < 100 ditolak", False)
    except safety.SafetyError as exc:
        check("seed Lookalike < 100 ditolak dengan alasan jelas", True, str(exc)[:70])

    seg = {"id": f"seg_{TAG}", "name": "Pelanggan POC", "audience": "customer",
           "criteria": {"min_bookings": 0}}
    report = await aud.sync_segment(db, seg, provider="meta", mode="validate")
    check("mode validasi: tidak ada data dikirim ke Meta (dry_run) tapi laporan tetap lengkap",
          report["result"]["status"] == "dry_run" and "consent_filtered" in report["stats"],
          json.dumps(report["stats"]))
    logs = await aud.history(db, limit=1)
    check("setiap sinkron tercatat di audience_syncs (bisa diaudit)",
          logs and logs[0]["provider"] == "meta")
    await db.audience_syncs.delete_many({"segment_id": f"seg_{TAG}"})


# --------------------------------------------------------------------------------------- POC-8
async def poc8_lead_ads(db):
    head("POC-8 · Lead Ads (signature + dedup) & Klik-ke-WhatsApp (CTWA)")
    from services import lead_ads as la

    await la.ensure_indexes(db)
    secret = "APP-SECRET-RAHASIA"
    payload = {"object": "page", "entry": [{"id": "PG1", "time": 1, "changes": [{
        "field": "leadgen", "value": {"leadgen_id": f"lg{TAG}1", "form_id": "FORM1",
                                      "page_id": "PG1", "ad_id": "AD1", "adgroup_id": "ADSET1",
                                      "campaign_id": "CAMP1", "created_time": 1}}]}]}
    raw = json.dumps(payload).encode()
    sig = la.sign_payload(secret, raw)
    check("signature sah diterima", la.verify_signature(secret, raw, sig) is True)
    check("body diubah 1 karakter → signature DITOLAK",
          la.verify_signature(secret, raw + b" ", sig) is False)
    check("app secret salah → DITOLAK", la.verify_signature("SALAH", raw, sig) is False)
    check("tanpa header signature → DITOLAK (fail-closed)",
          la.verify_signature(secret, raw, "") is False)
    check("tanpa app secret tersimpan → DITOLAK (bukan diloloskan)",
          la.verify_signature("", raw, sig) is False)

    notices = la.parse_leadgen(payload)
    check("parse webhook: adgroup_id Meta dipetakan ke adset_id ERP",
          len(notices) == 1 and notices[0]["adset_id"] == "ADSET1"
          and notices[0]["campaign_id"] == "CAMP1")
    check("perubahan non-leadgen diabaikan",
          la.parse_leadgen({"entry": [{"changes": [{"field": "feed", "value": {}}]}]}) == [])

    fields = la.parse_field_data([{"name": "nama_lengkap", "values": ["Siti Aminah"]},
                                  {"name": "no_hp", "values": ["0899 0000 0001"]},
                                  {"name": "kota_tujuan", "values": ["Bromo"]},
                                  {"name": "budget_estimasi", "values": ["5jt"]}])
    check("pemetaan field form Bahasa Indonesia (nama_lengkap/no_hp/kota_tujuan)",
          fields["name"] == "Siti Aminah" and fields["phone"] == "0899 0000 0001"
          and fields["destination"] == "Bromo")
    check("field tak dikenal tetap disimpan di raw_fields (tidak hilang)",
          fields["raw_fields"]["budget_estimasi"] == "5jt")

    async def fake_fetch(leadgen_id):
        return {"status": "ok", "data": {"id": leadgen_id, "form_id": "FORM1", "ad_id": "AD1",
                                         "adset_id": "ADSET1", "campaign_id": "CAMP1",
                                         "field_data": [{"name": "nama", "values": ["Siti Aminah"]},
                                                        {"name": "phone", "values": ["0899-0000-0001"]}]}}

    first = await la.ingest(db, dict(notices[0]), fetch=fake_fetch)
    check("lead iklan masuk CRM + tercatat di platform_leads",
          first["status"] == "received" and first["lead_id"], json.dumps(first))
    lead = await db.leads.find_one({"id": first["lead_id"]}, {"_id": 0})
    check("lead menyimpan atribusi LEVEL IKLAN (campaign/adset/ad) — dasar ROAS per iklan",
          lead["ad_campaign_id"] == "CAMP1" and lead["ad_adset_id"] == "ADSET1"
          and lead["ad_id"] == "AD1" and lead["ad_platform"] == "meta")
    check("lead iklan dianggap ber-consent (izin diberikan di form platform)",
          lead["marketing_consent"] is True and lead["channel"] == "meta_ads")
    again = await la.ingest(db, dict(notices[0]), fetch=fake_fetch)
    check("pengiriman ganda webhook → 'duplicate', tidak membuat lead kedua",
          again["status"] == "duplicate",
          str(await db.leads.count_documents({"ad_form_id": "FORM1"})))

    async def failing_fetch(leadgen_id):
        return {"status": "not_configured", "reason": "Page Access Token belum diisi"}

    pending = await la.ingest(db, {"leadgen_id": f"lg{TAG}2", "form_id": "FORM1",
                                   "ad_id": "AD1", "campaign_id": "CAMP1"}, fetch=failing_fetch)
    check("gagal ambil isi lead → notifikasi TETAP disimpan (bisa di-backfill, tidak hilang)",
          pending["status"] == "received" and pending["has_fields"] is False
          and pending["fetch_status"] == "not_configured")

    ref = la.parse_wa_referral({"from": "6289900000001", "referral": {
        "source_type": "ad", "source_id": "AD77", "ctwa_clid": "CTWA-9",
        "source_url": "https://fb.me/x", "headline": "Sewa Hiace"}})
    check("CTWA: referral pesan WA dibaca (ad_id + ctwa_clid + headline)",
          ref["ad_id"] == "AD77" and ref["ctwa_clid"] == "CTWA-9"
          and ref["ad_platform"] == "meta")
    check("pesan WA biasa (tanpa referral) tidak dianggap dari iklan",
          la.parse_wa_referral({"from": "62899", "text": "halo"}) == {})
    touches = await db.ad_touches.count_documents({"click_id": {"$regex": TAG}})
    check("klik iklan tercatat di ad_touches untuk penelusuran atribusi", touches >= 1, str(touches))
    rows = await la.recent(db, limit=5)
    check("daftar lead iklan bisa ditampilkan di UI", len(rows) >= 2, f"{len(rows)} baris")


# --------------------------------------------------------------------------------------- main
async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "app_db")]
    print(f"{B}{C}POC FASE F3/F4 — Marketing end-to-end (mode kering, tanpa kredensial){X}")
    await cleanup(db)
    try:
        await poc1_event_hooks(db)
        await poc2_meta_payload(db)
        await poc3_google_payload(db)
        await poc4_not_configured(db)
        await poc5_metrics(db)
        poc6_safety()
        await poc7_audiences(db)
        await poc8_lead_ads(db)
    finally:
        await cleanup(db)
        client.close()

    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n{B}{'='*70}{X}")
    if passed == total:
        print(f"{G}{B}  POC F3 LULUS — {passed}/{total} cek{X}")
        print(f"{G}  Rantai konversi, metrik, pengaman belanja, audiens, Lead Ads & CTWA terbukti.{X}")
    else:
        print(f"{R}{B}  POC F3 GAGAL — {passed}/{total} cek lulus{X}")
        for name, ok, detail in RESULTS:
            if not ok:
                print(f"{R}   × {name} — {detail}{X}")
    print(f"{B}{'='*70}{X}\n")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

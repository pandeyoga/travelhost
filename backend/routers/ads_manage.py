"""routers/ads_manage.py — MUTASI iklan: Lead Ads, audiens, dan campaign builder.

Dipisahkan dari `routers/ads.py` karena semua endpoint di sini menyentuh **uang & data pribadi**,
jadi punya aturan sendiri:

  * Mutasi hanya `owner` + `marketing_admin` (ops_admin read-only di dashboard).
  * Setiap tulis ke platform WAJIB lewat `services/ads_safety.py`:
    mode `validate` (validate_only, tidak ada objek/biaya) → `publish` (dibuat, status PAUSED)
    → `status` ACTIVE hanya dengan konfirmasi ketik nama + plafon budget ditegakkan ERP.
  * `SafetyError` dipetakan ke HTTP 400 (kesalahan pemakaian), BUKAN 5xx.
  * Webhook Lead Ads bersifat PUBLIK (Meta yang memanggil) namun diverifikasi
    `X-Hub-Signature-256` HMAC app secret + `hub.verify_token` — didaftarkan eksplisit di
    allowlist INV-AUTH-01 dengan justifikasi.
"""
import json
import time

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from core_utils import safe_doc
from db import get_db
from dependencies import require_role, require_section
from services import ads_safety as safety
from services import audiences as aud
from services import google_ads as ga
from services import integrations as integ
from services import lead_ads as la
from services import meta_ads as ma
from services.audit import record

router = APIRouter(prefix="/api", tags=["ads-manage"])
READ = require_section("ads")
WRITE = require_role("owner", "marketing_admin")


def _bad(exc: Exception):
    return HTTPException(status_code=400, detail=str(exc))


def _first_resource(result: dict) -> str:
    return (((result or {}).get("data") or {}).get("results") or [{}])[0].get("resourceName", "")


# ============================================================== Lead Ads (F5)
@router.get("/ads/platform-leads")
async def platform_leads(limit: int = Query(default=50, le=200), user=Depends(READ)):
    db = get_db()
    rows = await la.recent(db, limit=limit)
    lead_ids = [r["lead_id"] for r in rows if r.get("lead_id")]
    leads = {}
    if lead_ids:
        docs = await db.leads.find({"id": {"$in": lead_ids}},
                                   {"_id": 0, "id": 1, "customer_name": 1, "stage": 1,
                                    "phone": 1}).to_list(len(lead_ids))
        leads = {d["id"]: d for d in docs}
    for row in rows:
        row["lead"] = leads.get(row.get("lead_id"))
    return {"rows": safe_doc(rows), "total": len(rows)}


@router.post("/ads/platform-leads/simulate")
async def simulate_lead_ads(body: dict = Body(default={}), user=Depends(WRITE)):
    """Uji jalur Lead Ads TANPA kredensial: bentuk payload webhook resmi, tanda tangani dengan
    app secret tersimpan (atau sementara), lalu proses seperti panggilan Meta sungguhan."""
    db = get_db()
    payload = body or {}
    if not (payload.get("phone") or payload.get("email")):
        raise HTTPException(status_code=400,
                            detail="Nomor WhatsApp atau email wajib diisi agar lead bisa dihubungi.")
    notice = {
        "leadgen_id": str(payload.get("leadgen_id") or f"sim-{int(time.time())}"),
        "form_id": str(payload.get("form_id") or "FORM-SIMULASI"),
        "page_id": str(payload.get("page_id") or ""),
        "ad_id": str(payload.get("ad_id") or ""),
        "adset_id": str(payload.get("adset_id") or ""),
        "campaign_id": str(payload.get("campaign_id") or ""),
    }
    fields = [{"name": "full_name", "values": [payload.get("name") or "Calon Pelanggan"]},
              {"name": "phone_number", "values": [payload.get("phone") or ""]},
              {"name": "email", "values": [payload.get("email") or ""]},
              {"name": "destination", "values": [payload.get("destination") or ""]},
              {"name": "message", "values": [payload.get("message") or ""]}]

    async def fetch(_leadgen_id):
        return {"status": "ok", "data": {**notice, "field_data": fields}}

    envelope = {"object": "page", "entry": [{"id": notice["page_id"] or "PAGE", "changes": [
        {"field": "leadgen", "value": {**notice, "adgroup_id": notice["adset_id"]}}]}]}
    raw = json.dumps(envelope).encode()
    secret = await integ.secret_of(db, "meta_ads", "app_secret") or "simulasi-tanpa-app-secret"
    signature = la.sign_payload(secret, raw)
    verified = la.verify_signature(secret, raw, signature)
    result = await la.ingest(db, notice, fetch=fetch)
    await record(db, actor=user, action="create", entity_type="platform_lead",
                 entity_id=notice["leadgen_id"],
                 summary=f"Simulasi Lead Ads {notice['leadgen_id']} ({result.get('status')})")
    return {"signature_verified": verified, "result": result, "notice": notice}


@router.post("/ads/platform-leads/backfill")
async def backfill_lead_ads(body: dict = Body(default={}), user=Depends(WRITE)):
    """Ambil ulang lead dari satu form (jaring pengaman bila webhook pernah gagal)."""
    db = get_db()
    form_id = str((body or {}).get("form_id") or "").strip()
    if not form_id:
        raise HTTPException(status_code=400, detail="form_id wajib diisi.")
    meta_client, _, _ = await integ.clients(db)
    res = await meta_client.list_form_leads(form_id, limit=int((body or {}).get("limit") or 50))
    if res.get("status") != "ok":
        return {"status": res.get("status"), "reason": res.get("reason"), "ingested": 0,
                "duplicates": 0}
    ingested, duplicates = 0, 0
    for row in (res.get("data") or {}).get("data") or []:
        notice = {"leadgen_id": str(row.get("id")), "form_id": str(row.get("form_id") or form_id),
                  "ad_id": str(row.get("ad_id") or ""), "adset_id": str(row.get("adset_id") or ""),
                  "campaign_id": str(row.get("campaign_id") or "")}

        async def fetch(_lid, _row=row):
            return {"status": "ok", "data": _row}

        out = await la.ingest(db, notice, fetch=fetch)
        if out.get("status") == "received":
            ingested += 1
        elif out.get("status") == "duplicate":
            duplicates += 1
    await record(db, actor=user, action="sync", entity_type="platform_lead", entity_id=form_id,
                 summary=f"Backfill Lead Ads form {form_id}: {ingested} baru, {duplicates} duplikat")
    return {"status": "ok", "ingested": ingested, "duplicates": duplicates}


@router.get("/public/webhooks/meta/leads")
async def verify_lead_webhook(request: Request):
    """Verifikasi langganan webhook Meta (hub.challenge). PUBLIK — Meta yang memanggil."""
    params = request.query_params
    token = await integ.secret_of(get_db(), "meta_ads", "lead_verify_token")
    if params.get("hub.mode") == "subscribe" and token and params.get("hub.verify_token") == token:
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verifikasi webhook Lead Ads gagal")


@router.post("/public/webhooks/meta/leads")
async def receive_lead_webhook(request: Request):
    """Terima notifikasi Lead Ads. WAJIB bertanda tangan sah (HMAC app secret atas RAW body)."""
    db = get_db()
    raw = await request.body()
    secret = await integ.secret_of(db, "meta_ads", "app_secret")
    if not la.verify_signature(secret, raw, request.headers.get("X-Hub-Signature-256")):
        # fail-closed: tanpa app secret / tanda tangan salah -> tolak (cegah lead palsu)
        raise HTTPException(status_code=403, detail="Signature tidak valid")
    try:
        payload = json.loads(raw or b"{}")
    except Exception:  # noqa: BLE001
        payload = {}
    meta_client, _, _ = await integ.clients(db)

    async def fetch(leadgen_id):
        return await meta_client.fetch_lead(leadgen_id)

    received, duplicates = 0, 0
    for notice in la.parse_leadgen(payload):
        out = await la.ingest(db, notice, fetch=fetch)
        if out.get("status") == "received":
            received += 1
        elif out.get("status") == "duplicate":
            duplicates += 1
    return {"status": "ok", "received": received, "duplicates": duplicates}


# ============================================================== Audiens (F6)
@router.get("/ads/audiences")
async def list_audiences(user=Depends(READ)):
    db = get_db()
    segments = await db.segments.find({}, {"_id": 0, "id": 1, "name": 1, "audience": 1,
                                          "description": 1}).sort("created_at", -1).to_list(100)
    return {"segments": safe_doc(segments), "history": safe_doc(await aud.history(db, limit=30)),
            "readiness": await integ.ads_readiness(db),
            "min_lookalike_seed": aud.MIN_SEED_FOR_LOOKALIKE}


@router.post("/ads/audiences/preview")
async def preview_audience(body: dict = Body(default={}), user=Depends(READ)):
    """Hitung berapa kontak yang layak dikirim & berapa tersaring karena tanpa izin."""
    db = get_db()
    segment = await db.segments.find_one({"id": (body or {}).get("segment_id")}, {"_id": 0})
    if not segment:
        raise HTTPException(status_code=404, detail="Segmen tidak ditemukan")
    try:
        members = await aud.members_of_segment(db, segment)
    except Exception as exc:  # noqa: BLE001  (kriteria segmen bisa malformed -> 400, bukan 5xx)
        raise HTTPException(status_code=400, detail=f"Kriteria segmen tidak valid: {exc}") from None
    eligible, filtered = aud.split_by_consent(members)
    rows, skipped = aud.hash_rows_meta(eligible)
    return {"segment": {"id": segment["id"], "name": segment.get("name")},
            "total": len(members), "consent_filtered": filtered, "eligible": len(eligible),
            "uploadable": len(rows), "skipped_no_identifier": skipped,
            "batches": len(aud.meta_batches(rows))}


@router.post("/ads/audiences/sync")
async def sync_audience(body: dict = Body(default={}), user=Depends(WRITE)):
    db = get_db()
    payload = body or {}
    provider = payload.get("provider")
    if provider not in ("meta", "google"):
        raise HTTPException(status_code=400, detail="Provider harus 'meta' atau 'google'.")
    segment = await db.segments.find_one({"id": payload.get("segment_id")}, {"_id": 0})
    if not segment:
        raise HTTPException(status_code=404, detail="Segmen tidak ditemukan")
    meta_client, google_client, _ = await integ.clients(db)
    try:
        mode = safety.normalize_mode(payload.get("mode") or "validate")
        out = await aud.sync_segment(db, segment, provider=provider, mode=mode,
                                     meta_client=meta_client, google_client=google_client,
                                     audience_id=str(payload.get("audience_id") or ""),
                                     audience_name=str(payload.get("name") or ""),
                                     actor_email=user.get("email") or "")
    except safety.SafetyError as exc:
        raise _bad(exc) from None
    await record(db, actor=user, action="sync", entity_type="audience", entity_id=segment["id"],
                 summary=f"Sinkron audiens '{segment.get('name')}' ke {provider} "
                         f"(mode {mode}, {out['stats']['eligible']} layak, "
                         f"{out['stats']['consent_filtered']} tersaring consent)")
    return out


@router.post("/ads/audiences/lookalike")
async def create_lookalike(body: dict = Body(default={}), user=Depends(WRITE)):
    db = get_db()
    payload = body or {}
    origin = str(payload.get("origin_audience_id") or "").strip()
    if not origin:
        raise HTTPException(status_code=400, detail="origin_audience_id wajib diisi.")
    try:
        mode = safety.normalize_mode(payload.get("mode") or "validate")
        aud.assert_lookalike_seed(int(payload.get("seed_size") or 0))
    except safety.SafetyError as exc:
        raise _bad(exc) from None
    meta_client, _, _ = await integ.clients(db)
    spec = ma.build_lookalike_payload(payload.get("name") or "Lookalike CRM", origin,
                                      ratio=float(payload.get("ratio") or 0.01),
                                      country=payload.get("country") or "ID")
    res = await meta_client.create_audience_raw(spec, mode=mode)
    await record(db, actor=user, action="create", entity_type="audience", entity_id=origin,
                 summary=f"Buat Lookalike dari audiens {origin} (mode {mode})")
    return {"result": res, "sent_payload": spec}


# ============================================================== Campaign builder (F7)
def _meta_specs(payload: dict, cfg: dict) -> dict:
    """Bangun 4 payload Meta dari satu formulir UI (murni, mudah diuji)."""
    campaign = payload.get("campaign") or {}
    adset = payload.get("adset") or {}
    creative = payload.get("creative") or {}
    ad = payload.get("ad") or {}
    destination = adset.get("destination") or "whatsapp"
    budget = safety.assert_budget_within_cap(
        adset.get("daily_budget_minor"), cfg.get("max_daily_budget_minor"),
        currency=cfg.get("currency") or "")
    return {
        "campaign": ma.build_campaign_payload(campaign.get("name") or "",
                                             campaign.get("objective") or "OUTCOME_LEADS"),
        "adset": ma.build_adset_payload(
            adset.get("name") or "", adset.get("campaign_id") or "{CAMPAIGN_ID}",
            daily_budget_minor=budget, destination=destination,
            page_id=cfg.get("page_id") or "", pixel_id=cfg.get("pixel_id") or "",
            whatsapp_number=cfg.get("whatsapp_number") or "",
            countries=adset.get("countries") or ["ID"],
            age_min=int(adset.get("age_min") or 18), age_max=int(adset.get("age_max") or 65),
            custom_audience_ids=adset.get("custom_audience_ids") or []),
        "creative": ma.build_creative_payload(
            creative.get("name") or f"{campaign.get('name') or ''} · kreatif",
            cfg.get("page_id") or "", destination=destination,
            message=creative.get("message") or "", headline=creative.get("headline") or "",
            description=creative.get("description") or "", link=creative.get("link") or "",
            image_hash=creative.get("image_hash") or "",
            whatsapp_number=cfg.get("whatsapp_number") or ""),
        "ad": ma.build_ad_payload(ad.get("name") or f"{campaign.get('name') or ''} · iklan",
                                  adset.get("adset_id") or "{ADSET_ID}", "{CREATIVE_ID}"),
    }


def _google_ops(payload: dict, cfg: dict) -> dict:
    campaign = payload.get("campaign") or {}
    adgroup = payload.get("adgroup") or {}
    creative = payload.get("creative") or {}
    budget = safety.assert_budget_within_cap(campaign.get("daily_budget_micros"),
                                            cfg.get("max_daily_budget_micros"),
                                            currency=cfg.get("currency") or "")
    return {
        "budget": [ga.build_budget_op(f"{campaign.get('name') or 'Kampanye'} · budget", budget)],
        "campaign": [ga.build_campaign_op(campaign.get("name") or "", "{BUDGET_RESOURCE}",
                                          channel_type=campaign.get("channel_type") or "SEARCH")],
        "adgroup": [ga.build_adgroup_op(adgroup.get("name") or "", "{CAMPAIGN_RESOURCE}")],
        "ad": [ga.build_rsa_op("{ADGROUP_RESOURCE}", creative.get("final_url") or "",
                               creative.get("headlines") or [], creative.get("descriptions") or [])],
        "keywords": ga.build_keyword_ops("{ADGROUP_RESOURCE}", adgroup.get("keywords") or []),
    }


@router.post("/ads/campaigns/validate")
async def validate_campaign(body: dict = Body(default={}), user=Depends(WRITE)):
    """Langkah 1 WAJIB: platform memvalidasi payload TANPA membuat objek & tanpa biaya."""
    db = get_db()
    payload = body or {}
    provider = payload.get("provider")
    meta_client, google_client, cfgs = await integ.clients(db)
    try:
        if provider == "meta":
            specs = _meta_specs(payload, cfgs.get("meta") or {})
            res = await meta_client.create_object("campaign", specs["campaign"], mode="validate")
            return {"provider": "meta", "validated": res, "payloads": specs,
                    "safety": safety.summary("validate")}
        if provider == "google":
            ops = _google_ops(payload, cfgs.get("google") or {})
            res = await google_client.mutate("campaignBudgets", ops["budget"], mode="validate")
            return {"provider": "google", "validated": res, "payloads": ops,
                    "safety": safety.summary("validate")}
    except safety.SafetyError as exc:
        raise _bad(exc) from None
    raise HTTPException(status_code=400, detail="Provider harus 'meta' atau 'google'.")


async def _publish_meta(client, payload, cfg, name):
    specs = _meta_specs(payload, cfg)
    steps = []
    camp = await client.create_object("campaign", specs["campaign"], mode="publish")
    steps.append({"step": "campaign", "result": camp})
    campaign_id = ((camp.get("data") or {}).get("id") or "")
    if not campaign_id:
        return steps
    specs["adset"]["campaign_id"] = campaign_id
    adset = await client.create_object("adset", specs["adset"], mode="publish")
    steps.append({"step": "adset", "result": adset})
    creative = await client.create_object("creative", specs["creative"], mode="publish")
    steps.append({"step": "creative", "result": creative})
    adset_id = ((adset.get("data") or {}).get("id") or "")
    creative_id = ((creative.get("data") or {}).get("id") or "")
    if adset_id and creative_id:
        ad_spec = ma.build_ad_payload((payload.get("ad") or {}).get("name") or f"{name} · iklan",
                                      adset_id, creative_id)
        steps.append({"step": "ad",
                      "result": await client.create_object("ad", ad_spec, mode="publish")})
    return steps


async def _publish_google(client, payload, cfg):
    ops = _google_ops(payload, cfg)
    steps = []
    budget = await client.mutate("campaignBudgets", ops["budget"], mode="publish")
    steps.append({"step": "budget", "result": budget})
    resource = _first_resource(budget)
    if not resource:
        return steps
    ops["campaign"][0]["create"]["campaignBudget"] = resource
    camp = await client.mutate("campaigns", ops["campaign"], mode="publish", kind="campaign")
    steps.append({"step": "campaign", "result": camp})
    camp_resource = _first_resource(camp)
    if not camp_resource:
        return steps
    ops["adgroup"][0]["create"]["campaign"] = camp_resource
    group = await client.mutate("adGroups", ops["adgroup"], mode="publish", kind="adgroup")
    steps.append({"step": "adgroup", "result": group})
    group_resource = _first_resource(group)
    if not group_resource:
        return steps
    ops["ad"][0]["create"]["adGroup"] = group_resource
    steps.append({"step": "ad", "result": await client.mutate("adGroupAds", ops["ad"],
                                                              mode="publish", kind="adgroupad")})
    if ops["keywords"]:
        for op in ops["keywords"]:
            op["create"]["adGroup"] = group_resource
        steps.append({"step": "keywords",
                      "result": await client.mutate("adGroupCriteria", ops["keywords"],
                                                    mode="publish")})
    return steps


@router.post("/ads/campaigns/publish")
async def publish_campaign(body: dict = Body(default={}), user=Depends(WRITE)):
    """Langkah 2: buat objek NYATA namun status DIJEDA. Wajib konfirmasi ketik nama kampanye."""
    db = get_db()
    payload = body or {}
    provider = payload.get("provider")
    if provider not in ("meta", "google"):
        raise HTTPException(status_code=400, detail="Provider harus 'meta' atau 'google'.")
    name = ((payload.get("campaign") or {}).get("name") or "").strip()
    meta_client, google_client, cfgs = await integ.clients(db)
    try:
        safety.assert_confirmation(name, payload.get("confirm_name") or "")
        if provider == "meta":
            steps = await _publish_meta(meta_client, payload, cfgs.get("meta") or {}, name)
        else:
            steps = await _publish_google(google_client, payload, cfgs.get("google") or {})
    except safety.SafetyError as exc:
        raise _bad(exc) from None
    await record(db, actor=user, action="create", entity_type="ads_campaign", entity_id=name,
                 summary=f"Terbitkan kampanye {provider} '{name}' (status DIJEDA)")
    return {"provider": provider, "steps": steps,
            "note": "Semua objek dibuat dengan status DIJEDA — aktifkan manual bila sudah yakin."}


async def _entity_of(db, provider, object_id):
    return await db.ads_entities.find_one({"provider": provider,
                                           "$or": [{"entity_id": object_id},
                                                   {"resource_name": object_id}]}, {"_id": 0})


@router.post("/ads/campaigns/status")
async def change_campaign_status(body: dict = Body(default={}), user=Depends(WRITE)):
    """Jeda / aktifkan objek iklan. ACTIVE wajib konfirmasi ketik nama objek."""
    db = get_db()
    payload = body or {}
    provider = payload.get("provider")
    object_id = str(payload.get("object_id") or "").strip()
    if not object_id:
        raise HTTPException(status_code=400, detail="object_id wajib diisi.")
    if provider not in ("meta", "google"):
        raise HTTPException(status_code=400, detail="Provider harus 'meta' atau 'google'.")
    meta_client, google_client, _ = await integ.clients(db)
    entity = await _entity_of(db, provider, object_id)
    expected = (entity or {}).get("name") or payload.get("expected_name") or ""
    try:
        status = safety.assert_activation_allowed(payload.get("status") or "PAUSED",
                                                  expected_name=expected,
                                                  typed_name=payload.get("confirm_name") or "")
        mode = safety.normalize_mode(payload.get("mode") or "publish")
        if provider == "meta":
            res = await meta_client.update_object(object_id, {"status": status}, mode=mode)
        else:
            resource = (entity or {}).get("resource_name") or object_id
            res = await google_client.mutate("campaigns",
                                             [ga.build_status_update_op(resource, status)],
                                             mode=mode)
    except safety.SafetyError as exc:
        raise _bad(exc) from None
    await record(db, actor=user, action="update", entity_type="ads_campaign", entity_id=object_id,
                 summary=f"Ubah status iklan {provider} {object_id} → {status}")
    return {"status": status, "result": res}


@router.post("/ads/campaigns/budget")
async def change_campaign_budget(body: dict = Body(default={}), user=Depends(WRITE)):
    """Ubah budget harian. Plafon ditegakkan ERP + wajib konfirmasi ketik nama objek."""
    db = get_db()
    payload = body or {}
    provider = payload.get("provider")
    object_id = str(payload.get("object_id") or "").strip()
    if provider not in ("meta", "google"):
        raise HTTPException(status_code=400, detail="Provider harus 'meta' atau 'google'.")
    meta_client, google_client, cfgs = await integ.clients(db)
    entity = await _entity_of(db, provider, object_id)
    expected = (entity or {}).get("name") or payload.get("expected_name") or ""
    try:
        safety.assert_confirmation(expected, payload.get("confirm_name") or "")
        mode = safety.normalize_mode(payload.get("mode") or "publish")
        if provider == "meta":
            amount = safety.assert_budget_within_cap(
                payload.get("daily_budget_minor"),
                (cfgs.get("meta") or {}).get("max_daily_budget_minor"),
                currency=(entity or {}).get("currency") or "")
            res = await meta_client.update_object(object_id, {"daily_budget": str(amount)},
                                                  mode=mode)
        else:
            amount = safety.assert_budget_within_cap(
                payload.get("daily_budget_micros"),
                (cfgs.get("google") or {}).get("max_daily_budget_micros"),
                currency=(entity or {}).get("currency") or "")
            resource = (entity or {}).get("budget_resource") or object_id
            res = await google_client.mutate(
                "campaignBudgets", [ga.build_budget_update_op(resource, amount)], mode=mode)
    except safety.SafetyError as exc:
        raise _bad(exc) from None
    await record(db, actor=user, action="update", entity_type="ads_campaign", entity_id=object_id,
                 summary=f"Ubah budget harian iklan {provider} {object_id} → {amount}")
    return {"daily_budget": amount, "result": res}

"""services/audiences.py — sinkron audiens: segmen CRM -> Meta Custom Audience & Google Customer Match.

Mengapa penting: retargeting & Lookalike adalah cara termurah menaikkan ROAS — memakai data
pelanggan yang SUDAH dimiliki. Tapi ini juga jalur paling mudah melanggar privasi, maka:

  * **Filter consent WAJIB** (`marketing_consent == True`). Kontak tanpa izin TIDAK PERNAH
    dikirim, dan jumlah yang tersaring DILAPORKAN ke UI (bukan dibuang diam-diam). — INV-AUD-01
  * Identitas di-hash SHA-256 setelah dinormalkan sesuai aturan MASING-MASING platform
    (Meta: telepon digit tanpa '+', Google: E.164 dengan '+'), lihat `services/pii.py`.
  * Batch Meta maksimum 10.000 baris/permintaan dengan `session{session_id,batch_seq,
    last_batch_flag,estimated_num_total}` supaya unggahan besar tetap konsisten.
  * Semua penulisan lewat `services/ads_safety.py` (mode validate/publish).
"""
import logging
import random

from core_utils import new_id, now_iso
from services import ads_safety as safety
from services import pii

logger = logging.getLogger("travel_fleet.audiences")

COLL_SYNCS = "audience_syncs"
META_BATCH_SIZE = 10_000
GOOGLE_CHUNK = 100_000
META_SCHEMA = ["EMAIL", "PHONE"]
MIN_SEED_FOR_LOOKALIKE = 100


async def ensure_indexes(db):
    await db[COLL_SYNCS].create_index([("created_at", -1)], name="sync_recent")
    await db[COLL_SYNCS].create_index([("segment_id", 1), ("provider", 1)], name="sync_segment")


def split_by_consent(members):
    """-> (layak_kirim, jumlah_tersaring). Sumber kebenaran: field `marketing_consent`."""
    eligible, filtered = [], 0
    for member in members or []:
        if bool(member.get("marketing_consent")):
            eligible.append(member)
        else:
            filtered += 1
    return eligible, filtered


def hash_rows_meta(members):
    """-> (rows, dilewati). Baris tanpa email & telepon dilewati (Meta menolak baris kosong)."""
    rows, skipped = [], 0
    for member in members or []:
        email = pii.hash_email(member.get("email") or "")
        phone = pii.hash_phone_meta(member.get("phone") or "")
        if not email and not phone:
            skipped += 1
            continue
        rows.append([email, phone])
    return rows, skipped


def meta_batches(rows, *, session_id=None, batch_size=META_BATCH_SIZE):
    """Bentuk daftar payload `/{audience_id}/users` sesuai aturan batching resmi Meta."""
    sid = int(session_id or random.randint(100_000, 999_999_999))
    total = len(rows or [])
    chunks = [rows[i:i + batch_size] for i in range(0, total, batch_size)] or [[]]
    payloads = []
    for index, chunk in enumerate(chunks, start=1):
        payloads.append({
            "payload": {"schema": list(META_SCHEMA), "data": chunk},
            "session": {"session_id": sid, "batch_seq": index,
                        "last_batch_flag": index == len(chunks),
                        "estimated_num_total": total},
        })
    return payloads


def google_operations(members):
    """Operasi `offlineUserDataJobs:addOperations` (Customer Match)."""
    ops = []
    for member in members or []:
        identifiers = []
        email = pii.hash_email(member.get("email") or "")
        phone = pii.hash_phone_google(member.get("phone") or "")
        if email:
            identifiers.append({"hashedEmail": email})
        if phone:
            identifiers.append({"hashedPhoneNumber": phone})
        if identifiers:
            ops.append({"create": {"userIdentifiers": identifiers}})
    return ops[:GOOGLE_CHUNK]


def assert_lookalike_seed(size: int):
    if int(size or 0) < MIN_SEED_FOR_LOOKALIKE:
        raise safety.SafetyError(
            f"Audiens sumber terlalu kecil untuk Lookalike ({size} kontak). "
            f"Meta membutuhkan minimal {MIN_SEED_FOR_LOOKALIKE} kontak yang cocok.")


async def members_of_segment(db, segment):
    """Ambil anggota segmen (memakai resolver segmen CRM yang sudah ada) + status consent."""
    from services import segments as seg_svc
    _, members = await seg_svc.resolve_segment(db, segment, limit=50_000)
    audience = (segment or {}).get("audience") or "customer"
    collection = db.customers if audience == "customer" else db.leads
    ids = [m.get("target_id") for m in members if m.get("target_id")]
    docs = {}
    if ids:
        rows = await collection.find({"id": {"$in": ids}},
                                     {"_id": 0, "id": 1, "email": 1, "phone": 1,
                                      "marketing_consent": 1}).to_list(len(ids))
        docs = {r["id"]: r for r in rows}
    out = []
    for member in members:
        doc = docs.get(member.get("target_id")) or {}
        out.append({
            "target_id": member.get("target_id"), "name": member.get("name"),
            "phone": doc.get("phone") or member.get("phone") or "",
            "email": doc.get("email") or "",
            "marketing_consent": bool(doc.get("marketing_consent")),
        })
    return out


async def record_sync(db, *, segment_id, segment_name, provider, mode, stats, status,
                      audience_id="", reason="", actor_email=""):
    doc = {"id": new_id("aus"), "segment_id": segment_id, "segment_name": segment_name,
           "provider": provider, "mode": mode, "status": status,
           "audience_id": audience_id, "reason": reason or "",
           "actor": actor_email or "", **(stats or {}), "created_at": now_iso()}
    await db[COLL_SYNCS].insert_one(dict(doc))
    return doc


async def history(db, *, limit=30):
    return await db[COLL_SYNCS].find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)


async def sync_segment(db, segment, *, provider, mode="validate", meta_client=None,
                       google_client=None, audience_id="", audience_name="", actor_email=""):
    """Jalankan sinkron satu segmen ke satu provider. Selalu mengembalikan laporan (tak melempar
    kecuali SafetyError yang memang harus terlihat sebagai 400 di router)."""
    members = await members_of_segment(db, segment)
    eligible, filtered = split_by_consent(members)
    stats = {"total": len(members), "consent_filtered": filtered, "eligible": len(eligible),
             "uploaded": 0, "skipped_no_identifier": 0, "batches": 0}
    name = audience_name or f"CRM · {(segment or {}).get('name') or 'Segmen'}"

    if provider == "meta":
        rows, skipped = hash_rows_meta(eligible)
        stats["skipped_no_identifier"] = skipped
        batches = meta_batches(rows)
        stats["batches"] = len(batches)
        stats["uploaded"] = len(rows)
        result = {"status": "dry_run", "reason": "Mode validasi — tidak ada data dikirim ke Meta."}
        target_audience = audience_id
        if not safety.is_dry_run(mode):
            if meta_client is None:
                result = {"status": "not_configured",
                          "reason": "Klien Meta belum terkonfigurasi."}
            else:
                if not target_audience:
                    created = await meta_client.create_audience(
                        name, f"Sinkron dari segmen CRM '{(segment or {}).get('name')}'", mode=mode)
                    if created.get("status") != "ok":
                        await record_sync(db, segment_id=(segment or {}).get("id"),
                                          segment_name=(segment or {}).get("name"),
                                          provider=provider, mode=mode, stats=stats,
                                          status=created.get("status", "error"),
                                          reason=created.get("reason", ""), actor_email=actor_email)
                        return {"stats": stats, "result": created, "audience_id": ""}
                    target_audience = ((created.get("data") or {}).get("id") or "")
                for payload in batches:
                    result = await meta_client.upload_audience_users(target_audience, payload,
                                                                     mode=mode)
                    if result.get("status") not in ("ok", "dry_run"):
                        break
        report = await record_sync(db, segment_id=(segment or {}).get("id"),
                                   segment_name=(segment or {}).get("name"), provider=provider,
                                   mode=mode, stats=stats, status=result.get("status", "error"),
                                   audience_id=target_audience, reason=result.get("reason", ""),
                                   actor_email=actor_email)
        return {"stats": stats, "result": result, "audience_id": target_audience, "log": report}

    ops = google_operations(eligible)
    stats["uploaded"] = len(ops)
    stats["skipped_no_identifier"] = max(0, len(eligible) - len(ops))
    stats["batches"] = 1 if ops else 0
    result = {"status": "dry_run",
              "reason": "Mode validasi — tidak ada data dikirim ke Google."}
    list_resource = audience_id
    if not safety.is_dry_run(mode):
        if google_client is None:
            result = {"status": "not_configured", "reason": "Klien Google belum terkonfigurasi."}
        else:
            if not list_resource:
                created = await google_client.create_user_list(name, "Sinkron segmen CRM", mode=mode)
                if created.get("status") != "ok":
                    await record_sync(db, segment_id=(segment or {}).get("id"),
                                      segment_name=(segment or {}).get("name"), provider=provider,
                                      mode=mode, stats=stats, status=created.get("status", "error"),
                                      reason=created.get("reason", ""), actor_email=actor_email)
                    return {"stats": stats, "result": created, "audience_id": ""}
                results = ((created.get("data") or {}).get("results") or [{}])
                list_resource = results[0].get("resourceName", "")
            job = await google_client.create_offline_job(list_resource, mode=mode)
            job_resource = ((job.get("data") or {}).get("resourceName") or "")
            if job_resource and ops:
                await google_client.add_offline_operations(job_resource, ops, mode=mode)
                result = await google_client.run_offline_job(job_resource, mode=mode)
            else:
                result = job
    report = await record_sync(db, segment_id=(segment or {}).get("id"),
                               segment_name=(segment or {}).get("name"), provider=provider,
                               mode=mode, stats=stats, status=result.get("status", "error"),
                               audience_id=list_resource, reason=result.get("reason", ""),
                               actor_email=actor_email)
    return {"stats": stats, "result": result, "audience_id": list_resource, "log": report}

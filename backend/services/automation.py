"""services/automation.py — Automation Engine (E1).

Rules engine *configurable*: event domain -> kondisi -> aksi. Idempotent & auditable.

Model `automation_rules` (id `aur_`):
  name, description, event_type, enabled(bool), system(bool),
  conditions: [{field, op, value}]  (op: eq|ne|in|contains|exists|gt|lt)
  actions:    [{type, params}]      (type: send_wa|create_notification|create_task|
                                            assign_agent|schedule_followup)
  run_count, last_run_at, created_at, updated_at

Model `automation_runs` (id `arn_`):
  rule_id, rule_name, event_id, event_type, status(success|failed|skipped),
  actions: [{type, status, detail}], dedupe_key, message, created_at

Setiap (rule, event) hanya dieksekusi sekali (dedupe_key = rule_id:event_id).
"""
import logging

from core_utils import new_id, now_iso
from services.events import render_template

logger = logging.getLogger("travel_fleet.automation")

ACTION_TYPES = {
    "send_wa": "Kirim WhatsApp",
    "create_notification": "Buat notifikasi",
    "create_task": "Buat tugas",
    "assign_agent": "Tugaskan agen (auto)",
    "schedule_followup": "Jadwalkan follow-up",
    "enroll_sequence": "Daftarkan ke sequence",
}


def _get(payload, field):
    cur = payload or {}
    for part in str(field).split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _match_one(cond, payload):
    field = cond.get("field")
    op = (cond.get("op") or "eq").lower()
    expected = cond.get("value")
    actual = _get(payload, field)
    if op == "exists":
        return actual not in (None, "", [], {})
    if op == "eq":
        return str(actual) == str(expected)
    if op == "ne":
        return str(actual) != str(expected)
    if op == "contains":
        return expected is not None and str(expected).lower() in str(actual or "").lower()
    if op == "in":
        opts = expected if isinstance(expected, list) else str(expected or "").split(",")
        return str(actual) in [str(o).strip() for o in opts]
    if op in ("gt", "lt"):
        try:
            a, b = float(actual), float(expected)
            return a > b if op == "gt" else a < b
        except (TypeError, ValueError):
            return False
    return True


def match_conditions(conditions, payload):
    """AND atas semua kondisi. Tanpa kondisi = selalu cocok."""
    for c in conditions or []:
        if not _match_one(c, payload):
            return False
    return True


async def _resolve_phone(payload):
    return (payload or {}).get("phone") or (payload or {}).get("contact_phone") or ""


async def _do_send_wa(db, params, payload, rule):
    from services.whatsapp import send_wa
    phone = params.get("to") or await _resolve_phone(payload)
    if not phone:
        return {"type": "send_wa", "status": "skipped", "detail": "Nomor tujuan tidak ada di payload"}
    res = await send_wa(
        db, phone, text=params.get("text"), template_key=params.get("template_key"),
        variables=payload, lead_id=(payload or {}).get("lead_id"),
        customer_id=(payload or {}).get("customer_id"),
        contact_name=(payload or {}).get("customer_name") or (payload or {}).get("contact_name"),
        source=f"automation:{rule.get('id')}",
    )
    status = "success" if res.get("status") in ("sent", "delivered", "read") else (
        "skipped" if res.get("status") == "skipped" else "failed")
    return {"type": "send_wa", "status": status,
            "detail": f"{res.get('status')} → {phone} (Rp {int(res.get('cost') or 0)})",
            "conversation_id": res.get("conversation_id")}


async def _upsert_notification(db, *, dedupe_key, base):
    """SSOT: delegasikan ke services.notifications._upsert (satu implementasi upsert notifikasi).

    Menjaga default `scheduled_at` untuk notifikasi otomasi/sequence.
    """
    from services.notifications import _upsert
    merged = {"scheduled_at": now_iso(), **base}
    return bool(await _upsert(db, dedupe_key, merged))


async def _do_notification(db, params, payload, rule, event, kind="automation"):
    title = render_template(params.get("title") or rule.get("name") or "Otomasi", payload)
    body = render_template(params.get("body") or params.get("text") or "", payload)
    target_user = (payload or {}).get("assigned_to") or params.get("target_user_id")
    created = await _upsert_notification(db, dedupe_key=f"auto:{rule.get('id')}:{event.get('id')}", base={
        "type": kind, "title": title, "body": body,
        "ref_type": event.get("ref_type"), "ref_id": event.get("ref_id"),
        "lead_id": (payload or {}).get("lead_id"), "booking_id": (payload or {}).get("booking_id"),
        "target_role": None if target_user else (params.get("target_role") or "manager"),
        "target_user_id": target_user,
    })
    return {"type": "create_notification" if kind == "automation" else "create_task",
            "status": "success" if created else "skipped",
            "detail": title if created else "sudah ada (dedupe)"}


async def _do_assign_agent(db, params, payload, rule):
    from services.crm import auto_assign_agent
    lead_id = (payload or {}).get("lead_id")
    if not lead_id:
        return {"type": "assign_agent", "status": "skipped", "detail": "Tidak ada lead_id"}
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0, "assigned_to": 1})
    if lead and lead.get("assigned_to"):
        return {"type": "assign_agent", "status": "skipped", "detail": "Lead sudah punya agen"}
    target = await auto_assign_agent(db)
    if not target:
        return {"type": "assign_agent", "status": "failed", "detail": "Tidak ada agen aktif"}
    await db.leads.update_one({"id": lead_id}, {"$set": {"assigned_to": target, "last_activity_at": now_iso()}})
    return {"type": "assign_agent", "status": "success", "detail": f"Lead ditugaskan ke {target}"}


async def _do_schedule_followup(db, params, payload, rule, event):
    try:
        from datetime import datetime, timedelta, timezone
        days = int(params.get("days", 1) or 1)
        due = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    except Exception:
        due = now_iso()
    title = render_template(params.get("title") or "Follow-up terjadwal", payload)
    created = await _upsert_notification(db, dedupe_key=f"auto-fu:{rule.get('id')}:{event.get('id')}", base={
        "type": "lead_followup", "title": title,
        "body": render_template(params.get("body") or "", payload),
        "ref_type": "lead", "ref_id": (payload or {}).get("lead_id"),
        "lead_id": (payload or {}).get("lead_id"), "due_at": due, "scheduled_at": due,
        "target_user_id": (payload or {}).get("assigned_to"),
        "target_role": None if (payload or {}).get("assigned_to") else "manager",
    })
    return {"type": "schedule_followup", "status": "success" if created else "skipped",
            "detail": f"due {due[:10]}" if created else "sudah ada (dedupe)"}


async def _do_enroll_sequence(db, params, payload, rule):
    seq_id = params.get("sequence_id")
    if not seq_id:
        return {"type": "enroll_sequence", "status": "skipped", "detail": "sequence_id kosong"}
    seq = await db.sequences.find_one({"id": seq_id}, {"_id": 0})
    if not seq:
        return {"type": "enroll_sequence", "status": "failed", "detail": "Sequence tidak ditemukan"}
    audience = seq.get("audience", "lead")
    target = (payload or {}).get("lead_id") if audience == "lead" else (payload or {}).get("customer_id")
    if not target:
        return {"type": "enroll_sequence", "status": "skipped", "detail": f"payload tanpa {audience}_id"}
    from services.sequences import enroll
    enr = await enroll(db, seq, target, name=(payload or {}).get("customer_name"),
                       phone=(payload or {}).get("phone"))
    return {"type": "enroll_sequence", "status": "success" if enr else "skipped",
            "detail": seq.get("name") if enr else "sudah aktif"}


async def _execute_action(db, action, payload, rule, event):
    t = (action.get("type") or "").lower()
    params = action.get("params") or {}
    if t == "send_wa":
        return await _do_send_wa(db, params, payload, rule)
    if t == "create_notification":
        return await _do_notification(db, params, payload, rule, event, kind="automation")
    if t == "create_task":
        return await _do_notification(db, params, payload, rule, event, kind="task")
    if t == "assign_agent":
        return await _do_assign_agent(db, params, payload, rule)
    if t == "schedule_followup":
        return await _do_schedule_followup(db, params, payload, rule, event)
    if t == "enroll_sequence":
        return await _do_enroll_sequence(db, params, payload, rule)
    return {"type": t or "unknown", "status": "failed", "detail": "Tipe aksi tidak dikenal"}


async def process_event(db, event):
    """Evaluasi event ke semua rule aktif yang cocok. Return jumlah run baru."""
    etype = event.get("type")
    payload = event.get("payload") or {}
    rules = await db.automation_rules.find(
        {"event_type": etype, "enabled": True}, {"_id": 0}).to_list(200)
    created = 0
    for rule in rules:
        dedupe = f"{rule['id']}:{event['id']}"
        if await db.automation_runs.find_one({"dedupe_key": dedupe}, {"_id": 1}):
            continue
        if not match_conditions(rule.get("conditions"), payload):
            await db.automation_runs.insert_one({
                "id": new_id("arn"), "rule_id": rule["id"], "rule_name": rule.get("name"),
                "event_id": event["id"], "event_type": etype, "status": "skipped",
                "actions": [], "dedupe_key": dedupe, "message": "Kondisi tidak terpenuhi",
                "created_at": now_iso(),
            })
            continue
        results = []
        status = "success"
        for action in rule.get("actions") or []:
            try:
                res = await _execute_action(db, action, payload, rule, event)
            except Exception as exc:  # noqa: BLE001
                res = {"type": action.get("type"), "status": "failed", "detail": str(exc)[:160]}
            results.append(res)
            if res.get("status") == "failed":
                status = "failed"
        await db.automation_runs.insert_one({
            "id": new_id("arn"), "rule_id": rule["id"], "rule_name": rule.get("name"),
            "event_id": event["id"], "event_type": etype, "status": status,
            "actions": results, "dedupe_key": dedupe,
            "message": f"{len(results)} aksi dijalankan", "created_at": now_iso(),
        })
        await db.automation_rules.update_one(
            {"id": rule["id"]}, {"$inc": {"run_count": 1}, "$set": {"last_run_at": now_iso()}})
        created += 1
    return created


def default_rules():
    """Rule contoh AKTIF (mock-first). Dipakai seed & endpoint reset."""
    def rule(name, desc, event_type, actions, conditions=None):
        now = now_iso()
        return {
            "id": new_id("aur"), "name": name, "description": desc, "event_type": event_type,
            "enabled": True, "system": True, "conditions": conditions or [],
            "actions": actions, "run_count": 0, "last_run_at": None,
            "created_at": now, "updated_at": now,
        }
    return [
        rule("Permintaan pinjam armada ke mitra", "WA ke mitra saat order sub-charter dibuat.",
             "subcharter.requested",
             [{"type": "send_wa", "params": {"text": "Halo {partner_name}, {company} ingin menyewa unit {vehicle_label} untuk {start_datetime}-{end_datetime} (rute {origin} - {destination}, ref {booking_code}). Estimasi biaya Rp {cost}. Apakah unit tersedia?"}},
              {"type": "create_notification", "params": {"title": "Sub-charter diminta: {code}", "body": "Mitra {partner_name} - {vehicle_label} - Rp {cost}."}}]),
        rule("Konfirmasi pinjam armada ke mitra", "WA konfirmasi order + notifikasi saat sub-charter dikonfirmasi.",
             "subcharter.confirmed",
             [{"type": "send_wa", "params": {"text": "Terima kasih {partner_name}! Order {code} DIKONFIRMASI: unit {vehicle_label}, {start_datetime}-{end_datetime}, biaya Rp {cost}. Mohon siapkan unit & driver. Salam, {company}."}},
              {"type": "create_notification", "params": {"title": "Sub-charter dikonfirmasi: {code}", "body": "Mitra {partner_name} - COGS Rp {cost}."}}]),
        rule("Auto-ack lead baru", "Sambut lead via WA + tugaskan agen + notifikasi.",
             "lead.created",
             [{"type": "send_wa", "params": {"text": "Halo {customer_name}! Terima kasih telah menghubungi {company}. Tim kami segera membantu rencana perjalanan Anda ke {destination}. 🚐"}},
              {"type": "assign_agent", "params": {}},
              {"type": "create_notification", "params": {"title": "Lead baru: {customer_name}", "body": "Sumber {source} — tujuan {destination}. Segera follow-up."}}]),
        rule("Konfirmasi penawaran terkirim", "Kirim ringkasan penawaran ke pelanggan via WA.",
             "quotation.sent",
             [{"type": "send_wa", "params": {"text": "Halo {customer_name}, penawaran {number} senilai Rp {total} telah kami kirim. Berlaku hingga {valid_until}. Ada yang bisa kami bantu?"}}]),
        rule("Konfirmasi booking + instruksi DP", "WA konfirmasi saat booking dikonfirmasi.",
             "booking.confirmed",
             [{"type": "send_wa", "params": {"text": "Booking {code} dikonfirmasi ✅ Total Rp {total_amount}. Mohon DP {dp_percent}% untuk mengamankan jadwal {start_datetime}. Terima kasih!"}},
              {"type": "create_notification", "params": {"title": "Booking dikonfirmasi: {code}", "body": "{customer_name} — {vehicle_name}."}}]),
        rule("Notifikasi pembatalan booking", "WA info pembatalan + ajakan jadwal ulang ke pelanggan + notifikasi internal (G1).",
             "booking.cancelled",
             [{"type": "send_wa", "params": {"text": "Halo {customer_name}, mohon maaf booking {code} ke {destination} pada {start_datetime} telah DIBATALKAN. Untuk penjadwalan ulang atau bantuan lebih lanjut, silakan balas pesan ini. Terima kasih, {company}. 🙏"}},
              {"type": "create_notification", "params": {"title": "Booking dibatalkan: {code}", "body": "{customer_name} — {vehicle_name}. Trip terkait dibatalkan & armada dibebaskan."}}]),
        rule("Notifikasi jadwal ulang booking", "WA info perubahan jadwal ke pelanggan + notifikasi internal (E17).",
             "booking.rescheduled",
             [{"type": "send_wa", "params": {"text": "Halo {customer_name}, jadwal booking {code} ke {destination} telah DIPERBARUI menjadi {new_start} (sebelumnya {old_start}). Unit: {vehicle_name}. Terima kasih, {company}. 🗓️"}},
              {"type": "create_notification", "params": {"title": "Booking dijadwal ulang: {code}", "body": "{customer_name}: {old_start} → {new_start}."}}]),
        rule("Permintaan booking publik masuk", "Auto-ack WA ke calon pelanggan + notifikasi ops utk approve (E19).",
             "booking.requested",
             [{"type": "send_wa", "params": {"text": "Halo {customer_name}, terima kasih! Permintaan pesanan Anda ke {destination} ({start_datetime}) telah kami terima. Tim {company} akan segera mengonfirmasi ketersediaan & harga. 🚐"}},
              {"type": "create_notification", "params": {"title": "Permintaan booking baru: {code}", "body": "{customer_name} — {destination} · {start_datetime}. Perlu persetujuan ops."}}]),
        rule("Booking hold kedaluwarsa (DP telat)", "Notifikasi internal saat hold dibatalkan otomatis karena DP tak masuk (E18).",
             "booking.hold_expired",
             [{"type": "create_notification", "params": {"title": "Hold kedaluwarsa: {code}", "body": "{customer_name} — DP tidak masuk sebelum batas waktu; booking dibatalkan & armada dibebaskan."}}]),
        rule("Notifikasi driver ditugaskan", "WA ke pelanggan saat driver & unit di-assign (E3 Dispatch).",
             "trip.assigned",
             [{"type": "send_wa", "params": {"text": "Halo {customer_name}, perjalanan {code} Anda ke {destination} ({start_datetime}) telah dijadwalkan. Driver: {driver_name} ({driver_phone}), unit {vehicle_name}. Sampai jumpa! 🚐"}},
              {"type": "create_notification", "params": {"title": "Trip di-assign: {code}", "body": "Driver {driver_name} · unit {vehicle_name}."}}]),
        rule("Konfirmasi keberangkatan", "WA konfirmasi keberangkatan + titik jemput (E3 Dispatch).",
             "booking.departure_confirmed",
             [{"type": "send_wa", "params": {"text": "Keberangkatan {code} dikonfirmasi untuk {start_datetime}. Titik jemput: {pickup}. Driver {driver_name} ({driver_phone}), unit {vehicle_name}. Selamat jalan, {customer_name}! 🙏"}},
              {"type": "create_notification", "params": {"title": "Keberangkatan dikonfirmasi: {code}", "body": "{start_datetime} — {vehicle_name}."}}]),
        rule("Driver dalam perjalanan", "WA ke pelanggan saat driver menuju titik jemput (E3 Dispatch).",
             "trip.enroute",
             [{"type": "send_wa", "params": {"text": "Halo {customer_name}, driver {driver_name} sedang dalam perjalanan menuju titik penjemputan Anda untuk trip {code}. 🚐"}}]),
        rule("Tiba di tujuan", "WA ke pelanggan saat tiba di tujuan (E3 Dispatch).",
             "trip.arrived",
             [{"type": "send_wa", "params": {"text": "Halo {customer_name}, Anda telah tiba di {destination}. Terima kasih telah memilih {company}! Perjalanan aman selalu. 🙏"}}]),
        rule("Terima kasih pembayaran", "WA konfirmasi tiap pembayaran tercatat.",
             "payment.recorded",
             [{"type": "send_wa", "params": {"text": "Pembayaran Rp {amount} ({type}) untuk booking {code} sudah kami terima. Terima kasih, {customer_name}! 🙏"}}]),
        rule("Pengingat keberangkatan H-1", "WA pengingat + notifikasi sebelum berangkat.",
             "booking.departure_due",
             [{"type": "send_wa", "params": {"text": "Pengingat keberangkatan {code} {when}. Driver {driver_name}, unit {vehicle_name}. Selamat jalan, {customer_name}!"}},
              {"type": "create_notification", "params": {"title": "Keberangkatan {code}", "body": "{when} — {vehicle_name}."}}]),
        rule("Terima kasih + ulasan", "WA terima kasih + ajakan ulasan/rebooking saat trip selesai.",
             "trip.completed",
             [{"type": "send_wa", "params": {"text": "Terima kasih telah memilih {company}, {customer_name}! Bagaimana perjalanan Anda? Balas pesan ini untuk ulasan atau pemesanan berikutnya. ⭐"}}]),
        rule("Tagih invoice lewat tempo", "WA reminder + notifikasi saat invoice jatuh tempo.",
             "invoice.overdue",
             [{"type": "send_wa", "params": {"text": "Halo {customer_name}, invoice {number} sebesar Rp {amount} telah jatuh tempo. Mohon segera melakukan pelunasan. Terima kasih."}},
              {"type": "create_notification", "params": {"title": "Invoice lewat tempo: {number}", "body": "Rp {amount} — {customer_name}."}}]),
        rule("Routing WA masuk", "Tugaskan agen + notifikasi saat pesan WA masuk.",
             "wa.inbound",
             [{"type": "assign_agent", "params": {}},
              {"type": "create_notification", "params": {"title": "WA masuk: {contact_name}", "body": "{text}"}}]),
        rule("Eskalasi SLA lead terlewati", "Notifikasi + WA pengingat agen saat SLA respons lead breach.",
             "lead.sla_breached",
             [{"type": "create_notification", "params": {"title": "SLA terlewati: {customer_name}", "body": "Lead {source} belum direspon (jatuh tempo {due_at}). Agen: {agent_name}."}}]),
        rule("Winback pelanggan berisiko", "WA winback + notifikasi saat pelanggan masuk at-risk/churn.",
             "customer.at_risk",
             [{"type": "send_wa", "params": {"text": "Halo {customer_name}, kami rindu melayani perjalanan Anda! Ada promo spesial untuk pemesanan berikutnya bersama {company}. Balas pesan ini ya. 🚗"}},
              {"type": "create_notification", "params": {"title": "Pelanggan berisiko: {customer_name}", "body": "{lifecycle} \u00b7 {recency_days} hari sejak transaksi terakhir (LTV Rp {ltv})."}}]),
    ]

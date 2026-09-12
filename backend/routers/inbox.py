"""routers/inbox.py — CRM Inbox multi-admin (Phase 7).

Koleksi `conversations` + `messages`. Thread chat, status pesan (sent/delivered/read),
assign agen, catatan internal, filter (unassigned/mine/all), web-chat (kanal web) +
WA SIMULASI. Akses owner/ops_admin (section 'crm'). Urutan rute: literal sebelum param.
"""
import base64

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from services.refs import must_exist
from dependencies import require_section
from schemas import ConversationCreate, ConversationUpdate, MessageCreate
from services.geo import parse_iso

router = APIRouter(prefix="/api", tags=["inbox"])
CRM = require_section("crm")

CONV_STATUS = {"open", "snoozed", "closed"}


async def _users_map(db):
    docs = await db.users.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
    return {u["id"]: u.get("name") for u in docs}


def _enrich(c, umap):
    c = safe_doc(c)
    c["assignee_name"] = umap.get(c.get("assigned_to")) if c.get("assigned_to") else None
    if c.get("channel") == "whatsapp":
        exp = parse_iso(c.get("session_expires_at"))
        from datetime import datetime, timezone
        c["wa_within_session"] = bool(exp and exp > datetime.now(timezone.utc))
    return c


@router.get("/conversations")
async def list_conversations(status: str = Query(default=None), assigned: str = Query(default=None),
                             channel: str = Query(default=None), q: str = Query(default=None),
                             limit: int = Query(default=200, le=500), user=Depends(CRM)):
    db = get_db()
    query = {}
    if status:
        query["status"] = status
    if channel:
        query["channel"] = channel
    if assigned == "mine":
        query["assigned_to"] = user.get("id")
    elif assigned == "unassigned":
        query["assigned_to"] = None
    if q:
        query["$or"] = [{"contact_name": {"$regex": q, "$options": "i"}},
                        {"contact_phone": {"$regex": q, "$options": "i"}},
                        {"subject": {"$regex": q, "$options": "i"}}]
    docs = await db.conversations.find(query, {"_id": 0}).sort("last_message_at", -1).to_list(limit)
    umap = await _users_map(db)
    return [_enrich(d, umap) for d in docs]


@router.post("/conversations")
async def create_conversation(body: ConversationCreate, user=Depends(CRM)):
    db = get_db()
    now = now_iso()
    doc = {
        "id": new_id("cnv"), "channel": body.channel or "internal",
        "contact_name": (body.contact_name or "").strip() or "Kontak",
        "contact_phone": body.contact_phone or "", "subject": body.subject or "",
        # INV-REF-01: penautan ke pelanggan/lead WAJIB nyata. Audit menemukan `customer_id`
        # & `lead_id` hantu diterima → percakapan "milik pelanggan" yang tidak ada, sehingga
        # Customer 360 & pipeline CRM kehilangan jejaknya tanpa pesan galat apa pun.
        "customer_id": await must_exist(db, "customers", body.customer_id),
        "lead_id": await must_exist(db, "leads", body.lead_id),
        "status": "open", "assigned_to": body.assigned_to or None, "labels": [],
        "unread": 0, "chat_token": None, "last_message_at": now,
        "last_message_preview": body.subject or "", "snooze_until": None, "created_at": now,
    }
    await db.conversations.insert_one(doc)
    if body.message:
        await _append_message(db, doc, sender="agent", body=body.message,
                              author_id=user.get("id"), internal=False, status="delivered")
    return _enrich(await db.conversations.find_one({"id": doc["id"]}, {"_id": 0}), await _users_map(db))


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, user=Depends(CRM)):
    db = get_db()
    c = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Percakapan tidak ditemukan")
    umap = await _users_map(db)
    out = _enrich(c, umap)
    msgs = await db.messages.find({"conversation_id": conversation_id}, {"_id": 0}).sort("created_at", 1).to_list(2000)
    for m in msgs:
        m["author_name"] = umap.get(m.get("author_id")) if m.get("author_id") else None
    out["messages"] = safe_doc(msgs)
    return out


@router.patch("/conversations/{conversation_id}")
async def update_conversation(conversation_id: str, body: ConversationUpdate, user=Depends(CRM)):
    db = get_db()
    c = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Percakapan tidak ditemukan")
    updates = {}
    if body.status is not None:
        if body.status not in CONV_STATUS:
            raise HTTPException(status_code=400, detail="Status percakapan tidak valid")
        updates["status"] = body.status
    if body.assigned_to is not None:
        target = body.assigned_to or None
        if target and not await db.users.find_one({"id": target}, {"_id": 1}):
            raise HTTPException(status_code=400, detail="Agen tidak ditemukan")
        updates["assigned_to"] = target
    if body.snooze_until is not None:
        updates["snooze_until"] = body.snooze_until
    if updates:
        await db.conversations.update_one({"id": conversation_id}, {"$set": updates})
    return _enrich(await db.conversations.find_one({"id": conversation_id}, {"_id": 0}), await _users_map(db))


async def _append_message(db, conv, sender, body, author_id=None, internal=False, status="sent"):
    msg = {
        "id": new_id("msg"), "conversation_id": conv["id"], "sender": sender,
        "author_id": author_id, "body": body, "internal": bool(internal),
        "status": status, "created_at": now_iso(),
    }
    await db.messages.insert_one(msg)
    conv_updates = {"last_message_at": msg["created_at"]}
    if not internal:
        conv_updates["last_message_preview"] = body[:120]
        if sender == "customer":
            conv_updates["unread"] = int(conv.get("unread", 0)) + 1
    await db.conversations.update_one({"id": conv["id"]}, {"$set": conv_updates})
    return msg


@router.post("/conversations/{conversation_id}/messages")
async def post_message(conversation_id: str, body: MessageCreate, user=Depends(CRM)):
    db = get_db()
    conv = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Percakapan tidak ditemukan")
    text = (body.body or "").strip()
    if not text and not body.template_key:
        raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong")
    # Kanal WhatsApp (bukan catatan internal) → kirim via provider (cost/status/session window).
    if conv.get("channel") == "whatsapp" and not body.internal:
        from services.whatsapp import send_wa
        res = await send_wa(db, conv.get("contact_phone"), text=text or None,
                            template_key=body.template_key, conversation_id=conversation_id,
                            author_id=user.get("id"), source="agent")
        if res.get("status") == "skipped":
            raise HTTPException(status_code=400, detail="Kontak telah memilih berhenti (opt-out) WhatsApp")
        if res.get("status") in (None, "failed"):
            raise HTTPException(status_code=400, detail=res.get("error") or "Gagal mengirim WhatsApp")
        msg = await db.messages.find_one({"id": res.get("message_id")}, {"_id": 0})
        out = safe_doc(msg or {})
        out["author_name"] = user.get("name")
        return out
    # Balasan agen keluar = 'delivered' (web); catatan internal = 'sent' & tak terkirim.
    msg = await _append_message(db, conv, sender="agent", body=text,
                                author_id=user.get("id"), internal=bool(body.internal),
                                status="sent" if body.internal else "delivered")
    out = safe_doc(msg)
    out["author_name"] = user.get("name")
    return out


ALLOWED_MEDIA = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_MEDIA_BYTES = 8 * 1024 * 1024


@router.post("/conversations/{conversation_id}/wa-media")
async def post_wa_media(conversation_id: str, file: UploadFile = File(...),
                        caption: str = Form(default=""), user=Depends(CRM)):
    """Kirim gambar/PDF ke kontak WA dari Inbox (caption opsional). Maks 8 MB."""
    db = get_db()
    conv = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Percakapan tidak ditemukan")
    if conv.get("channel") != "whatsapp":
        raise HTTPException(status_code=400, detail="Lampiran hanya untuk percakapan WhatsApp")
    mime = (file.content_type or "").lower()
    if mime not in ALLOWED_MEDIA:
        raise HTTPException(status_code=400, detail="Tipe file tidak didukung (JPG/PNG/WebP/PDF)")
    raw = await file.read()
    if len(raw) > MAX_MEDIA_BYTES:
        raise HTTPException(status_code=400, detail="Ukuran file maksimal 8 MB")
    data_url = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
    from services.whatsapp import send_wa
    res = await send_wa(db, conv.get("contact_phone"), text=(caption or "").strip() or None,
                        conversation_id=conversation_id, author_id=user.get("id"), source="agent",
                        media_data=data_url, media_filename=file.filename or "lampiran")
    if res.get("status") == "skipped":
        raise HTTPException(status_code=400, detail="Kontak telah memilih berhenti (opt-out) WhatsApp")
    if res.get("status") in (None, "failed"):
        raise HTTPException(status_code=400, detail=res.get("error") or "Gagal mengirim lampiran WhatsApp")
    msg = await db.messages.find_one({"id": res.get("message_id")}, {"_id": 0})
    out = safe_doc(msg or {})
    out["author_name"] = user.get("name")
    return out


@router.post("/conversations/{conversation_id}/wa-optout")
async def wa_optout(conversation_id: str, user=Depends(CRM)):
    db = get_db()
    if not await db.conversations.find_one({"id": conversation_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Percakapan tidak ditemukan")
    await db.conversations.update_one({"id": conversation_id}, {"$set": {"wa_opt_in": False}})
    return {"ok": True, "id": conversation_id, "wa_opt_in": False}


@router.post("/conversations/{conversation_id}/wa-optin")
async def wa_optin(conversation_id: str, user=Depends(CRM)):
    db = get_db()
    if not await db.conversations.find_one({"id": conversation_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Percakapan tidak ditemukan")
    await db.conversations.update_one({"id": conversation_id}, {"$set": {"wa_opt_in": True}})
    return {"ok": True, "id": conversation_id, "wa_opt_in": True}


@router.post("/conversations/{conversation_id}/read")
async def mark_conversation_read(conversation_id: str, user=Depends(CRM)):
    db = get_db()
    if not await db.conversations.find_one({"id": conversation_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Percakapan tidak ditemukan")
    await db.messages.update_many(
        {"conversation_id": conversation_id, "sender": "customer", "status": {"$ne": "read"}},
        {"$set": {"status": "read"}})
    await db.conversations.update_one({"id": conversation_id}, {"$set": {"unread": 0}})
    return {"ok": True, "id": conversation_id}

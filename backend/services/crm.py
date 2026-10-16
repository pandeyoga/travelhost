"""services/crm.py — helper CRM Internal (Phase 4).

- LEAD_STAGES / LEAD_STAGE_SET / OPEN_STAGES : kontrak tahap pipeline (INV-7).
- assignable_agents(db) : user yang boleh dipegang lead (ops_admin, fallback owner).
- auto_assign_agent(db) : round-robin LEAST-LOADED (lead 'open' paling sedikit).
- log_activity(...)     : tulis 1 baris timeline ke koleksi `lead_activities`.
"""
from core_utils import new_id, now_iso

LEAD_STAGES = ["new", "contacted", "quoted", "negotiation", "won", "lost"]
LEAD_STAGE_SET = set(LEAD_STAGES)
OPEN_STAGES = {"new", "contacted", "quoted", "negotiation"}
STAGE_LABEL = {"new": "Baru", "contacted": "Dihubungi", "quoted": "Penawaran",
               "negotiation": "Negosiasi", "won": "Menang", "lost": "Hilang"}


async def assignable_agents(db):
    """Daftar agen yang bisa dipegang lead (ops_admin lebih dulu, lalu owner)."""
    docs = await db.users.find(
        {"role": {"$in": ["ops_admin", "owner"]}, "status": "active"},
        {"_id": 0, "id": 1, "name": 1, "role": 1},
    ).to_list(200)
    docs.sort(key=lambda u: 0 if u.get("role") == "ops_admin" else 1)
    return docs


async def auto_assign_agent(db):
    """Pilih agen dengan beban lead 'open' paling sedikit (round-robin adil)."""
    agents = await db.users.find({"role": "ops_admin", "status": "active"}, {"_id": 0, "id": 1}).to_list(200)
    if not agents:
        agents = await db.users.find({"role": "owner", "status": "active"}, {"_id": 0, "id": 1}).to_list(200)
    if not agents:
        return None
    best, best_load = None, None
    for a in agents:
        load = await db.leads.count_documents({"assigned_to": a["id"], "stage": {"$in": list(OPEN_STAGES)}})
        if best_load is None or load < best_load:
            best, best_load = a["id"], load
    return best


async def log_activity(db, lead_id, user_id, type_, text=None, from_stage=None, to_stage=None):
    """Catat 1 aktivitas timeline. Dipakai create/stage/assign/note/convert."""
    doc = {
        "id": new_id("lac"), "lead_id": lead_id, "user_id": user_id,
        "type": type_, "text": text or "", "from_stage": from_stage,
        "to_stage": to_stage, "created_at": now_iso(),
    }
    await db.lead_activities.insert_one(doc)
    return doc

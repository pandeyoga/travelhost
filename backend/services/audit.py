"""services/audit.py — Audit Log Engine (Phase 8 / A1).

Catat aksi sensitif (CRUD master, keuangan, pengaturan, hapus) ke koleksi
`audit_logs` secara append-only. **Defensif**: kegagalan menulis audit TIDAK
pernah menggagalkan request bisnis (selalu di-try/except).

Skema (sinkron docs/03_DATA_MODEL.md §audit_logs):
  id, actor_id, action, entity_type, entity_id, before, after, timestamp
  (+ actor_name, actor_role, summary untuk keterbacaan di UI).
"""
import logging

from core_utils import new_id, now_iso

logger = logging.getLogger("travel_fleet.audit")

# Field yang tak relevan / sensitif untuk snapshot audit.
_SKIP = {"_id", "password_hash", "updated_at"}

# Batas panjang teks audit (INV-CLEAN-01 / BUG-0127).
# Kenapa: `summary` disusun dari nama entitas yang dikirim pengguna. Saat penjaga adversarial
# (atau penyerang) menembak nama 60.000 karakter, satu baris audit ikut membengkak jadi 60.016
# karakter — tabel Audit Log melebar tak terkendali, ekspor jadi raksasa, dan tak ada satu pun
# error di log. Audit adalah CATATAN, bukan tempat menyimpan payload: cukup dipotong.
_SUMMARY_MAX = 300
_VALUE_MAX = 2000


def _clip(value, limit: int):
    """Potong teks panjang (rekursif untuk dict/list snapshot) + beri penanda jelas."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + f"…[dipotong, {len(value)} karakter]"
    if isinstance(value, dict):
        return {k: _clip(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_clip(v, limit) for v in value[:200]]
    return value


def _clean(doc):
    if not isinstance(doc, dict):
        return doc
    out = {k: v for k, v in doc.items() if k not in _SKIP}
    out.pop("password_hash", None)  # jaminan: hash tak pernah masuk audit
    return out


def _diff(before, after):
    """Hanya field yang berubah (untuk action=update) agar audit ringkas."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        return _clean(before), _clean(after)
    b, a = {}, {}
    for k in (set(before) | set(after)):
        if k in _SKIP:
            continue
        if before.get(k) != after.get(k):
            b[k] = before.get(k)
            a[k] = after.get(k)
    return b, a


async def record(db, *, actor=None, action="", entity_type="", entity_id="",
                 before=None, after=None, summary=None):
    """Tulis satu entri audit. Tidak pernah raise (audit != alur bisnis)."""
    try:
        if action == "update" and before is not None and after is not None:
            before, after = _diff(before, after)
        else:
            before, after = _clean(before), _clean(after)
        actor = actor or {}
        doc = {
            "id": new_id("aud"),
            "actor_id": actor.get("id"),
            "actor_name": _clip(actor.get("name"), 120),
            "actor_role": actor.get("role"),
            "action": action,
            "entity_type": entity_type,
            "entity_id": _clip(entity_id, 120),
            "before": _clip(before, _VALUE_MAX),
            "after": _clip(after, _VALUE_MAX),
            "summary": _clip(summary or f"{action} {entity_type} {entity_id}".strip(),
                             _SUMMARY_MAX),
            "timestamp": now_iso(),
        }
        await db.audit_logs.insert_one(doc)
    except Exception as exc:  # noqa: BLE001 — audit tak boleh menggagalkan bisnis
        logger.warning("audit record skip: %s", exc)

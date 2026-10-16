"""services/landing_stats.py — pencatatan & laporan A/B halaman iklan (F8).

Kenapa agregat harian, bukan satu dokumen per kunjungan: halaman iklan bisa menerima ribuan
kunjungan; menyimpan baris per kunjungan membuat koleksi meledak tanpa nilai analitik tambahan.
Satu dokumen per (page_id, variant_id, tanggal) dengan `$inc` sudah cukup untuk menghitung
conversion rate dan menentukan pemenang, sekaligus IDEMPOTEN saat pekerja retry (upsert).

Metrik: `views` (halaman tampil), `cta_clicks` (tombol aksi diklik), `leads` (form terkirim).
"""
import logging

from core_utils import now_iso

logger = logging.getLogger("travel_fleet.landing")

COLL = "landing_stats"
METRICS = ("views", "cta_clicks", "leads")


async def ensure_indexes(db):
    try:
        await db[COLL].create_index([("page_id", 1), ("variant_id", 1), ("date", 1)], unique=True)
        await db[COLL].create_index([("page_id", 1), ("date", -1)])
    except Exception as exc:  # noqa: BLE001
        logger.warning("index landing_stats skip: %s", exc)


async def bump(db, page_id: str, variant_id: str, metric: str, inc: int = 1):
    """Naikkan satu metrik. TIDAK PERNAH melempar — analitik tak boleh menggagalkan lead."""
    if metric not in METRICS or not page_id:
        return None
    try:
        day = now_iso()[:10]
        await db[COLL].update_one(
            {"page_id": page_id, "variant_id": (variant_id or "A")[:8], "date": day},
            {"$inc": {metric: int(inc)}, "$set": {"updated_at": now_iso()},
             "$setOnInsert": {"created_at": now_iso()}},
            upsert=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("gagal mencatat statistik landing (%s/%s): %s", page_id, metric, exc)
    return None


def _rate(part, whole):
    return round((part / whole) * 100, 2) if whole else 0.0


async def totals(db, page_id: str, since: str = ""):
    q = {"page_id": page_id}
    if since:
        q["date"] = {"$gte": since[:10]}
    rows = await db[COLL].find(q, {"_id": 0}).to_list(2000)
    agg = {}
    for r in rows:
        vid = r.get("variant_id") or "A"
        cur = agg.setdefault(vid, {"views": 0, "cta_clicks": 0, "leads": 0})
        for m in METRICS:
            cur[m] += int(r.get(m) or 0)
    return agg


async def report(db, page: dict, since: str = ""):
    """Laporan A/B siap tampil: per varian + pemenang + alasan yang bisa dibaca manusia.

    Aturan pemenang dibuat KONSERVATIF supaya tidak menyesatkan keputusan belanja iklan:
    setiap varian wajib mencapai `min_sample` tampilan dulu; selisih di bawah 10% relatif
    dianggap belum meyakinkan ("beda tipis").
    """
    ab = page.get("ab") or {}
    variants = ab.get("variants") or [{"id": "A", "name": "Asli", "weight": 100}]
    goal = ab.get("goal") or "lead"
    min_sample = int(ab.get("min_sample") or 30)
    agg = await totals(db, page.get("id"), since)

    rows, best, runner = [], None, None
    for v in variants:
        vid = v.get("id") or "A"
        s = agg.get(vid) or {"views": 0, "cta_clicks": 0, "leads": 0}
        row = {
            "id": vid, "name": v.get("name") or f"Varian {vid}", "weight": v.get("weight", 50),
            "overrides": v.get("overrides") or {},
            "views": s["views"], "cta_clicks": s["cta_clicks"], "leads": s["leads"],
            "lead_rate": _rate(s["leads"], s["views"]),
            "cta_rate": _rate(s["cta_clicks"], s["views"]),
        }
        row["score"] = row["lead_rate"] if goal == "lead" else row["cta_rate"]
        rows.append(row)

    ranked = sorted(rows, key=lambda r: (r["score"], r["views"]), reverse=True)
    if ranked:
        best = ranked[0]
        runner = ranked[1] if len(ranked) > 1 else None

    enough = bool(rows) and all(r["views"] >= min_sample for r in rows) and len(rows) > 1
    winner, reason, uplift = "", "", 0.0
    metric_label = "lead per tampilan" if goal == "lead" else "klik CTA per tampilan"
    if not rows or len(rows) < 2:
        reason = "Uji A/B belum aktif — baru ada satu versi halaman."
    elif not enough:
        kurang = [r["name"] for r in rows if r["views"] < min_sample]
        reason = (f"Belum cukup data. Setiap versi butuh minimal {min_sample} tampilan "
                  f"(belum terpenuhi: {', '.join(kurang)}).")
    elif best and runner and runner["score"] > 0 and (best["score"] - runner["score"]) / runner["score"] < 0.10:
        reason = f"Beda tipis (<10%) pada {metric_label} — lanjutkan uji sebelum memutuskan."
    elif best and best["score"] <= 0:
        reason = f"Belum ada {metric_label} pada versi mana pun."
    elif best:
        winner = best["id"]
        uplift = round(((best["score"] - (runner["score"] if runner else 0)) /
                        (runner["score"] if runner and runner["score"] else 1)) * 100, 1)
        reason = (f"{best['name']} menang pada {metric_label} "
                  f"({best['score']}% vs {runner['score'] if runner else 0}%).")

    grand = {m: sum(r[m] for r in rows) for m in ("views", "cta_clicks", "leads")}
    grand["lead_rate"] = _rate(grand["leads"], grand["views"])
    return {
        "enabled": bool(ab.get("enabled")), "goal": goal, "min_sample": min_sample,
        "variants": rows, "winner": winner, "winner_reason": reason, "uplift_percent": uplift,
        "enough_data": enough, "totals": grand, "since": since[:10],
    }

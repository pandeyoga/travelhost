"""services/ratelimit.py — Rate limiter in-memory (Phase 8 / A3, diperluas E0/G7).

- allow(): sliding-window per-key utk endpoint publik (/api/public/*) dari spam/abuse.
- note_failure()/failure_count()/clear_failures(): pelacakan KEGAGALAN login
  (anti brute-force). Hanya kegagalan yang dihitung; login sukses membersihkan budget,
  sehingga login sah berulang (mis. testing) tidak terkena limit.
In-memory (cukup utk satu instance, tanpa dependency eksternal).
"""
import time
from collections import defaultdict, deque
from threading import Lock

_HITS = defaultdict(deque)
_FAILS = defaultdict(deque)
_LOCK = Lock()


def allow(key: str, limit: int, window: float) -> bool:
    """True bila masih di bawah `limit` request dalam `window` detik (sliding)."""
    now = time.time()
    cutoff = now - window
    with _LOCK:
        dq = _HITS[key]
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        if len(_HITS) > 10000:  # cegah growth tak terbatas utk key idle
            for k in [k for k, v in list(_HITS.items()) if not v]:
                _HITS.pop(k, None)
        return True


def note_failure(key: str, window: float = 300.0) -> None:
    """Catat satu kegagalan login utk `key` (mis. ip+email)."""
    now = time.time()
    cutoff = now - window
    with _LOCK:
        dq = _FAILS[key]
        while dq and dq[0] < cutoff:
            dq.popleft()
        dq.append(now)
        if len(_FAILS) > 10000:
            for k in [k for k, v in list(_FAILS.items()) if not v]:
                _FAILS.pop(k, None)


def failure_count(key: str, window: float = 300.0) -> int:
    """Jumlah kegagalan login dalam `window` detik terakhir."""
    now = time.time()
    cutoff = now - window
    with _LOCK:
        dq = _FAILS[key]
        while dq and dq[0] < cutoff:
            dq.popleft()
        return len(dq)


def clear_failures(key: str) -> None:
    with _LOCK:
        _FAILS.pop(key, None)


def client_ip(request) -> str:
    """IP klien di belakang ingress (ambil hop pertama X-Forwarded-For)."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# === RC-10: pelacakan KEGAGALAN login PERSISTEN (Mongo + TTL) ===
# Versi in-memory di atas hilang saat restart & tak lintas-worker. Untuk anti brute-force
# yang andal (multi-worker / setelah restart), simpan kegagalan di koleksi `login_failures`
# (TTL index dibuat di server startup). Hitungan difilter berdasarkan `ts` dalam window,
# jadi tetap benar walau TTL cleanup Mongo tertunda beberapa detik.
from datetime import datetime as _dt_rl, timedelta as _td_rl, timezone as _tz_rl


async def note_failure_db(db, key: str, window: float = 300.0) -> None:
    """Catat satu kegagalan login (persisten)."""
    now = _dt_rl.now(_tz_rl.utc)
    await db.login_failures.insert_one(
        {"key": key, "ts": now, "expire_at": now + _td_rl(seconds=window)})


async def failure_count_db(db, key: str, window: float = 300.0) -> int:
    """Jumlah kegagalan login dalam `window` detik terakhir (persisten)."""
    cutoff = _dt_rl.now(_tz_rl.utc) - _td_rl(seconds=window)
    return await db.login_failures.count_documents({"key": key, "ts": {"$gte": cutoff}})


async def clear_failures_db(db, key: str) -> None:
    """Bersihkan budget kegagalan (dipanggil saat login sukses)."""
    await db.login_failures.delete_many({"key": key})

"""services/openwa.py — Manajer sidecar OpenWA Easy API (provider WA unofficial, scan QR).

Menjalankan `@open-wa/wa-automate` v5 (Node, /app/openwa) sebagai proses samping:
  - spawn/stop/reset dari backend (pid file, log, session dir persisten di /app/openwa)
  - health & QR di-proxy ke UI admin (halaman Integrasi API)
  - inbound dikirim balik oleh sidecar via --webhook ke /api/wa/openwa-webhook

CATATAN: v4 stable RUSAK dengan WhatsApp Web terkini (issue #3346) — WAJIB v5 alpha (pinned).
"""
import asyncio
import logging
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("travel_fleet.openwa")

OPENWA_DIR = Path(__file__).resolve().parent.parent.parent / "openwa"
BIN = OPENWA_DIR / "node_modules" / ".bin" / "wa-automate"
PID_FILE = OPENWA_DIR / "openwa.pid"
LOG_FILE = OPENWA_DIR / "openwa.log"
SESSION_ID = "rahaza"


def base_url():
    return (os.environ.get("OPENWA_BASE_URL") or "http://localhost:8033").rstrip("/")


def api_key():
    return (os.environ.get("OPENWA_API_KEY") or "").strip()


def headers():
    return {"api_key": api_key(), "x-api-key": api_key()}


def _port():
    return str(urlparse(base_url()).port or 8033)


def external():
    """Sidecar dikelola di luar backend (container `openwa` di docker-compose)."""
    return (os.environ.get("OPENWA_MODE") or "").strip().lower() == "external"


async def _remote(method, timeout=15):
    """Panggil Easy API sidecar eksternal (logout/kill) — best-effort."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(f"{base_url()}/api/messages/{method}", json={"args": {}}, headers=headers())
        return r.status_code < 400
    except Exception as exc:  # noqa: BLE001
        logger.debug("openwa remote %s gagal: %s", method, exc)
        return False


async def health():
    """GET /health sidecar. None bila proses mati/tak terjangkau."""
    try:
        async with httpx.AsyncClient(timeout=4) as c:
            r = await c.get(f"{base_url()}/health", headers=headers())
        if r.status_code < 500:
            data = r.json()
            # pastikan benar-benar OpenWA (hindari salah deteksi service lain di port sama)
            if isinstance(data, dict) and ("session" in data or "host" in data):
                return data
    except Exception:  # noqa: BLE001
        return None
    return None


def _summary(h):
    sess = (h or {}).get("session") or {}
    return {"connected": bool(h.get("connected")), "state": sess.get("state"),
            "ready": bool(sess.get("ready"))}


def _pid_alive():
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return pid
    except Exception:  # noqa: BLE001
        return None


def installed():
    return BIN.exists()


def spawn():
    """Jalankan sidecar (detached, log ke /app/openwa/openwa.log)."""
    # Buang lock profil Chromium yatim (pod lama / crash) — kalau tidak, Chrome menolak
    # start dgn "profile in use by another computer" (exit code 21) dan QR tak pernah muncul.
    for stale in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        try:
            (OPENWA_DIR / f"_IGNORE_{SESSION_ID}" / stale).unlink(missing_ok=True)
        except OSError:
            pass
    key = api_key()
    webhook = f"http://localhost:8001/api/wa/openwa-webhook?key={key}"
    cmd = [str(BIN), "-p", _port(), "--api-key", key, "--session-id", SESSION_ID,
           "--qr-timeout", "86400", "--no-dashboard", "--webhook", webhook]
    logf = open(LOG_FILE, "ab")
    proc = subprocess.Popen(cmd, cwd=str(OPENWA_DIR), stdout=logf, stderr=logf,
                            start_new_session=True, env={**os.environ})
    PID_FILE.write_text(str(proc.pid))
    logger.info("openwa sidecar dijalankan (pid=%s, port=%s)", proc.pid, _port())
    return proc.pid


def _sidecar_pids():
    try:
        out = subprocess.run(["pgrep", "-f", "openwa/node_modules/.bin/wa-automate"],
                             capture_output=True, text=True)
        return [int(p) for p in out.stdout.split()]
    except Exception:  # noqa: BLE001
        return []


def stop():
    if external():
        return
    pids = set(_sidecar_pids())
    p = _pid_alive()
    if p:
        pids.add(p)
    for pid in pids:
        try:
            os.killpg(pid, signal.SIGTERM)
        except Exception:  # noqa: BLE001
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:  # noqa: BLE001
                pass
    time.sleep(1.5)
    for pid in pids:
        try:
            os.kill(pid, 0)  # masih hidup? paksa
            try:
                os.killpg(pid, signal.SIGKILL)
            except Exception:  # noqa: BLE001
                os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    if pids:
        logger.info("openwa sidecar dihentikan (pids=%s)", sorted(pids))
    PID_FILE.unlink(missing_ok=True)


def reset_session():
    """Hentikan + hapus data sesi (wajib scan QR ulang)."""
    if external():
        # Container: logout (hapus sesi di WA) lalu matikan proses; Docker me-restart & QR baru muncul.
        import asyncio as _aio
        _aio.run(_remote("logout"))
        _aio.run(_remote("kill"))
        return
    stop()
    for d in OPENWA_DIR.glob("_IGNORE_*"):
        shutil.rmtree(d, ignore_errors=True)
    for f in OPENWA_DIR.glob("*data.json"):
        f.unlink(missing_ok=True)


async def ensure_running(wait_seconds: float = 8.0):
    """Pastikan sidecar jalan. Non-blocking lama: bila baru spawn, tunggu sebentar lalu
    kembalikan starting=True — UI mem-poll status hingga siap."""
    h = await health()
    if h:
        return {"running": True, "installed": True, **_summary(h)}
    if external():
        return {"running": False, "installed": True, "external": True,
                "error": "Container OpenWA belum siap / tidak terjangkau. Cek: docker compose logs openwa "
                         "(pastikan COMPOSE_PROFILES=wa & OPENWA_API_KEY di deploy/.env)."}
    if not installed():
        return {"running": False, "installed": False,
                "error": "OpenWA belum terpasang. Jalankan: cd /app/openwa && yarn install --ignore-engines"}
    if not api_key():
        return {"running": False, "installed": True, "error": "OPENWA_API_KEY belum di-set di backend/.env"}
    if not _pid_alive():
        try:
            spawn()
        except Exception as exc:  # noqa: BLE001
            logger.warning("spawn openwa gagal: %s", exc)
            return {"running": False, "installed": True, "error": f"Gagal menjalankan sidecar: {str(exc)[:120]}"}
    deadline = asyncio.get_event_loop().time() + wait_seconds
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(1.2)
        h = await health()
        if h:
            return {"running": True, "installed": True, **_summary(h)}
    return {"running": False, "installed": True, "starting": True,
            "error": "Sidecar sedang dimulai — coba beberapa detik lagi."}


async def get_qr():
    """Ambil data QR mentah (string) untuk dirender di UI. Kosong bila belum tersedia."""
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.get(f"{base_url()}/qr", headers=headers())
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                return str(data.get("qr") or "")
    except Exception as exc:  # noqa: BLE001
        logger.debug("openwa qr belum tersedia: %s", exc)
    return ""


async def autostart(db):
    """Dipanggil saat startup backend: hidupkan sidecar bila provider aktif = openwa."""
    try:
        s = await db.settings.find_one({"key": "wa_config"}, {"_id": 0})
        provider = ((s or {}).get("value") or {}).get("provider")
        if provider == "openwa":
            res = await ensure_running(wait_seconds=25)
            logger.info("openwa autostart: %s", res)
    except Exception as exc:  # noqa: BLE001
        logger.warning("openwa autostart gagal: %s", exc)

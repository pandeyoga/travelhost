# Rahaza Travel — Fleet & Travel Management ERP (FARM: FastAPI · React · MongoDB)

## Setup cepat (setelah clone)

`git clone` sendiri **cepat** (repo ~6 MB — `node_modules` & `.git` besar tidak ikut).
Yang memakan waktu hanya **install pertama (cold)**: `yarn install` membangun `node_modules`
(~1.1 GB, CRA + ~78 dependency) + build wheel pip pertama. Reinstall "warm" (cache panas) hanya ~1–2 detik.

Jalankan satu perintah ini (install FE+BE **paralel**, offline-first, restart + health check):

```bash
bash scripts/bootstrap.sh          # install + restart + health check
bash scripts/bootstrap.sh --seed   # + isi data demo (owner/ops/driver @demo.local, pass: demo12345)
bash scripts/bootstrap.sh --gate   # + jalankan guardrail (scripts/gate.sh)
```

> Catatan: `.env` (MONGO_URL, DB_NAME, REACT_APP_BACKEND_URL) disediakan oleh platform —
> jangan diubah/di-overwrite. Optimasi yarn ada di `frontend/.yarnrc` (`prefer-offline`).

## Struktur
- `backend/`  — FastAPI (routers, services, schemas), entrypoint `server.py`.
- `frontend/` — React (CRA) + shadcn/ui; halaman di `src/features`, komponen di `src/components`.
- `scripts/`  — guardrail bash (`gate.sh`, `load_context.sh`, `bootstrap.sh`) + verifier Python (`verify_*.py`).
- `docs/`     — SSOT (data model, API contract, navigation map, invariants).
- `memory/`   — catatan agent (delivery manifest, session handoff, gate receipt, enhancement backlog).

## Perintah harian
```bash
bash scripts/load_context.sh   # snapshot cepat kondisi sistem
bash scripts/gate.sh           # guardrail lengkap — harus "VERDICT: HIJAU"
sudo supervisorctl status      # status service
tail -n 50 /var/log/supervisor/backend.err.log
```

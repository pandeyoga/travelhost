#!/usr/bin/env bash
# =============================================================================
# INSTANT CONTEXT LOADER — Travel & Fleet Ecosystem
# Snapshot kondisi sistem di awal sesi. Usage: bash scripts/load_context.sh [--full]
# =============================================================================
FULL=false
[[ "$1" == "--full" ]] && FULL=true
echo ""
echo "================================================================"
echo "  TRAVEL & FLEET — CONTEXT SNAPSHOT  ($(date '+%Y-%m-%d %H:%M'))"
echo "================================================================"

echo ""
echo "▶ SERVICE STATUS"
if curl -s http://localhost:8001/api/ 2>/dev/null | grep -qi "ok\|aktif\|running\|healthy"; then
  echo "   [OK] Backend RUNNING (http://localhost:8001)"
else
  echo "   [!] Backend belum merespons /api/ (mungkin belum dibuat / restart backend)"
fi
if curl -s http://localhost:3000 > /dev/null 2>&1; then
  echo "   [OK] Frontend RUNNING (http://localhost:3000)"
else
  echo "   [!] Frontend belum merespons"
fi

echo ""
echo "▶ ENV CONFIG"
[ -f /app/backend/.env ] && echo "   DB_NAME:   $(grep DB_NAME /app/backend/.env | cut -d= -f2 | tr -d '\"')"
[ -f /app/backend/.env ] && echo "   MONGO_URL: $(grep MONGO_URL /app/backend/.env | cut -d= -f2 | tr -d '\"')"
[ -f /app/frontend/.env ] && echo "   BACKEND_URL: $(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)"

echo ""
echo "▶ DATABASE STATE (collection counts)"
python3 - << 'PYEOF' 2>/dev/null || echo "   (skip: motor/env belum siap)"
import asyncio, os, sys
sys.path.insert(0, '/app/backend')
try:
    from dotenv import load_dotenv; load_dotenv('/app/backend/.env')
except Exception: pass
async def run():
    from motor.motor_asyncio import AsyncIOMotorClient
    url = os.environ.get('MONGO_URL'); name = os.environ.get('DB_NAME', 'app_db')
    if not url:
        print('   (MONGO_URL kosong)'); return
    db = AsyncIOMotorClient(url)[name]
    cols = ['users','sessions','vehicles','drivers','customers','leads','bookings',
            'trips','locations','payments','expenses','invoices','maintenance_records','destinations']
    for c in cols:
        n = await db[c].count_documents({})
        flag = '' if n>0 else '  [kosong]'
        print(f"   {c:<22}{n:>6}{flag}")
asyncio.run(run())
PYEOF

echo ""
echo "▶ FILE SIZES (limit: router .py <=800, .jsx/.js <=500)"
if [ -d /app/backend/routers ]; then
  for f in /app/backend/routers/*.py; do [ -e "$f" ] || continue; l=$(wc -l < "$f"); [ "$l" -gt 640 ] && echo "   [!] $(basename $f): $l"; done
fi
if [ -d /app/frontend/src ]; then
  for f in $(find /app/frontend/src -name '*.jsx' 2>/dev/null); do l=$(wc -l < "$f"); [ "$l" -gt 425 ] && echo "   [!] ${f#/app/frontend/src/}: $l"; done
fi
echo "   (hanya tampil yang mendekati/melebihi batas)"

echo ""
echo "▶ QUICK COMPLIANCE"
python3 /app/scripts/validate_compliance.py --quick 2>/dev/null | grep -E "FAIL|WARN|SUMMARY" | head -20

echo ""
echo "▶ LAST SESSION HANDOFF"
if [ -f /app/memory/SESSION_HANDOFF.md ]; then
  head -12 /app/memory/SESSION_HANDOFF.md | grep -v '^#' | grep -v '^$' | sed 's/^/   /'
else
  echo "   (SESSION_HANDOFF.md belum ada)"
fi

echo ""
echo "================================================================"
echo "  BACA BERJENJANG (hemat context): docs/00_INDEX.md"
echo "  TIER 0: 07_ENGINEERING_GUARDRAILS, 08_FRONTEND_GUARDRAILS, 11_AGENT_OPERATING_PROTOCOL"
echo "  Verifikasi = GATES (scripts), bukan baca ulang prosa."
echo "================================================================"
echo ""

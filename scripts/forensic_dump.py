#!/usr/bin/env python3
"""Forensic dump: DB reality (D1) + endpoint enumeration + code x DB cross-reference.
Output: /app/SSOT_FORENSIC_RAW_TRAVEL.json
Read-only. Tidak mengubah data apa pun.
"""
import os, re, json, sys
from collections import defaultdict
from pymongo import MongoClient

ROOT = "/app/backend"
sys.path.insert(0, ROOT)

# ---------- D1: DB reality ----------
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
mongo_url = os.environ["MONGO_URL"]
db_name = os.environ.get("DB_NAME", "test_database")
client = MongoClient(mongo_url)
db = client[db_name]

db_report = {}
for name in sorted(db.list_collection_names()):
    coll = db[name]
    cnt = coll.count_documents({})
    sample = coll.find_one({}, {"_id": 0})
    keys = sorted(sample.keys()) if sample else []
    db_report[name] = {"count": cnt, "keys": keys}

# ---------- Endpoint enumeration via FastAPI introspection ----------
endpoints = []
try:
    from server import app  # noqa
    for r in app.routes:
        methods = sorted(m for m in getattr(r, "methods", []) if m not in ("HEAD", "OPTIONS"))
        if not methods:
            continue
        endpoints.append({"path": r.path, "methods": methods, "name": getattr(r, "name", "")})
except Exception as e:
    endpoints = [{"error": str(e)}]

# ---------- D2: static scan db collection access in backend ----------
access = defaultdict(lambda: {"read": [], "write": []})
READ_OPS = r"(find_one|find|count_documents|aggregate|distinct|estimated_document_count)"
WRITE_OPS = r"(insert_one|insert_many|update_one|update_many|replace_one|delete_one|delete_many|bulk_write|find_one_and_update|find_one_and_delete|find_one_and_replace)"
pat_attr = re.compile(r"\bdb\.([a-zA-Z_][a-zA-Z0-9_]*)\.(\w+)\(")
pat_item = re.compile(r"\bdb\[[\"']([a-zA-Z_][a-zA-Z0-9_]*)[\"']\]\.(\w+)\(")

for dirpath, dirs, files in os.walk(ROOT):
    if "__pycache__" in dirpath or "/uploads" in dirpath:
        continue
    for f in files:
        if not f.endswith(".py") or f.startswith("backend_test") or f.startswith("test_") or f == "rbac_ssot_test.py":
            continue
        p = os.path.join(dirpath, f)
        rel = os.path.relpath(p, ROOT)
        with open(p, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh, 1):
                for m in list(pat_attr.finditer(line)) + list(pat_item.finditer(line)):
                    coll, op = m.group(1), m.group(2)
                    loc = f"{rel}:{i}"
                    if re.fullmatch(READ_OPS, op):
                        access[coll]["read"].append(loc)
                    elif re.fullmatch(WRITE_OPS, op):
                        access[coll]["write"].append(loc)

# classify
code_colls = set(access.keys())
db_colls = set(db_report.keys())
phantom_reads = sorted(c for c in code_colls if access[c]["read"] and c not in db_colls)
write_no_read = sorted(c for c in code_colls if access[c]["write"] and not access[c]["read"])
db_only = sorted(c for c in db_colls if c not in code_colls)
empty_colls = sorted(c for c, v in db_report.items() if v["count"] == 0)

out = {
    "db_name": db_name,
    "collections": db_report,
    "endpoints": endpoints,
    "code_access": {k: v for k, v in sorted(access.items())},
    "classification": {
        "phantom_reads_code_only": phantom_reads,
        "written_never_read": write_no_read,
        "db_only_not_in_code": db_only,
        "empty_collections": empty_colls,
    },
}
with open("/app/SSOT_FORENSIC_RAW_TRAVEL.json", "w") as fh:
    json.dump(out, fh, indent=1, default=str)

print(f"DB={db_name} collections={len(db_colls)} endpoints={len(endpoints)}")
print(f"code_collections={len(code_colls)}")
print("PHANTOM_READS (kode baca, koleksi tidak ada di DB):", phantom_reads)
print("WRITTEN_NEVER_READ:", write_no_read)
print("DB_ONLY (ada di DB, tak disentuh kode):", db_only)
print("EMPTY (count=0):", empty_colls)
print("--- counts ---")
for c in sorted(db_colls):
    print(f"{c}: {db_report[c]['count']}")

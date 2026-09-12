"""scripts/guardrails/_common.py — util bersama untuk Guardrail v2.

Guardrail v2 = penjaga PREVENTIF berbasis analisis STATIK + RUNTIME yang memaksa
invariant lintas-kelas-bug (lihat memory/INVARIANTS.md). Dirancang agar sesi AI /
developer baru — TANPA konteks sesi sebelumnya — tetap tertangkap saat memperkenalkan
kembali kelas bug yang sudah pernah ditemukan. Tiap penjaga mencetak: APA yang salah,
DI MANA, dan MENGACU ke INVARIANT-ID.

Berisi juga MESIN BERSIH-BERSIH bersama (`purge_guard_artifacts`) — lihat INV-CLEAN-01.
"""
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; C = "\033[96m"; B = "\033[1m"; X = "\033[0m"


class Guard:
    """Akumulator hasil satu penjaga invariant."""

    def __init__(self, invariant_id: str, title: str):
        self.id = invariant_id
        self.title = title
        self.violations = []
        self.checks = 0

    def add(self, msg: str):
        self.violations.append(msg)

    def bump(self, n: int = 1):
        self.checks += n

    def finish(self) -> int:
        print(f"{C}{B}== {self.id} \u2014 {self.title} =={X}")
        if not self.violations:
            print(f"{G}[PASS]{X} {self.checks} cek lolos, 0 pelanggaran.")
            return 0
        print(f"{R}[FAIL]{X} {len(self.violations)} pelanggaran (dari {self.checks} cek):")
        for v in self.violations:
            print(f"  {R}\u2717{X} {v}")
        print(f"{Y}\u2192 Perbaiki sesuai INVARIANT {self.id} (detail: memory/INVARIANTS.md).{X}")
        return 1


# =====================================================================================
# BERSIH-BERSIH DATA UJI (INV-CLEAN-01)
# =====================================================================================
# Kelas bug yang dicegah (NYATA — keluhan user 2026-08-13, BUG-0127):
#   Penjaga & smoke test MEMBUAT data lewat API sungguhan supaya perilakunya teruji. Yang
#   dulu dibersihkan hanya dokumen UTAMA (booking/customer/vehicle) — SIDE-EFFECT-nya tidak:
#   percakapan WA mock, pesan, notifikasi, event, automation_runs, entri audit, aset media.
#   Akibatnya tiap kali `gate.sh` jalan, ERP pengguna kebanjiran data hantu: customer bernama
#   "AAAA…" (60.000 karakter — dari self-test mutasi INV-STR-01 yang sengaja melepas
#   `max_length`), percakapan "Penjaga INV-BOOK-02" di Inbox, lonceng notifikasi penuh, dan
#   baris Audit Log sepanjang 60.016 karakter. Semua SENYAP: gate tetap HIJAU 40/40.
#
# Aturan yang dikunci: SIAPA PUN yang membuat data uji WAJIB menghapusnya BESERTA
# side-effect-nya. Penanda di bawah ini adalah SSOT konvensi identitas data uji.
# ------------------------------------------------------------------------------------
# Penanda teks yang HANYA dipakai penjaga/smoke (jangan pernah dipakai data nyata/seed).
GUARD_MARKERS = (
    "Penjaga INV-",            # verify_pricing_integrity / verify_booking_public / verify_string_bounds / verify_adversarial_5xx
    "Penjaga Unit",            # verify_booking_public (unit tak-tayang)
    "Smoke Customer",          # scripts/mutation_smoke.py
    "Smoke Vehicle",           # scripts/mutation_smoke.py
    "Guard Lead ",             # verify_reference_integrity
    "Guard Route ",            # verify_reference_integrity
    "Kota Uji",                # verify_reference_integrity (label rute uji)
    "Bandara Uji",             # verify_reference_integrity (label rute uji)
    "guard-media-",            # verify_media_runtime / verify_media_unified
    "bersih-bersih guardrail",  # alasan pembatalan yang ditulis penjaga
    "bersih-bersih POC",       # alasan pembatalan yang ditulis skrip POC (scripts/test_core_*.py)
    "\x00",                    # payload adversarial (NUL) — mustahil dari input manusia
)
# Nomor kontak khusus penjaga (konvensi: 0800000xxx = guardrail, 0810000000 = mutation_smoke).
GUARD_PHONE_PREFIXES = ("0800000", "0810000000")

# Koleksi yang TERLIHAT pengguna di ERP → wajib bersih dari data uji.
PURGE_COLLECTIONS = (
    "customers", "bookings", "payments", "invoices", "expenses", "trips", "locations",
    "trip_shares", "leads", "lead_activities", "quotations", "conversations", "messages",
    "notification_tasks", "events", "automation_runs", "audit_logs", "broadcasts",
    "campaign_recipients", "campaigns", "media_assets", "media_folders", "vehicles", "drivers",
    "subcharters", "partners", "partner_settlements", "driver_payouts", "maintenance_records",
    "segments", "sequences", "destinations", "packages", "articles", "testimonials",
    "transfer_routes", "service_types", "workshops", "promos", "landing_pages",
    # INV-REF-02 batch 5: master kota — quick-add uji dari guard/testing wajib bisa dibersihkan.
    "cities",
    # Bukti transfer DP (panel "Bukti Bayar" ops) + outbox konversi iklan.
    "payment_proofs",
    # Outbox konversi iklan: trafik penjaga ke endpoint publik ikut tercatat di sini dan
    # membengkakkan angka konversi dasbor pemasaran bila tidak dibersihkan.
    "conversion_events",
    # CMS-05/07/08 — artefak baru yang TERLIHAT pengguna: permintaan ulasan (halaman
    # Konten Web → Ulasan), statistik konten (panel Analitik), dan token pratinjau.
    "review_requests", "content_stats", "content_previews",
    # CMS-10/11/12 — riwayat versi, Tempat Sampah, dan tabel pengalihan URL. Semuanya
    # TERLIHAT pengguna di CMS: kalau artefak uji tertinggal, editor melihat riwayat &
    # tempat sampah berisi konten hantu yang tak pernah ia buat.
    # Master add-on booking + fee driver per keberangkatan + pencairan fee.
    "addons", "driver_fee_entries", "driver_withdrawals",
    "content_versions", "content_trash", "content_redirects",
)

# Batas panjang WAJAR per field identitas. Nilai di atas ini = artefak uji adversarial
# (`"A" * 60000`) yang lolos saat penjaga sengaja dilumpuhkan self-test mutasi.
OVERLONG_RULES = {
    "customers": {"name": 200, "address": 400, "notes": 2000},
    "leads": {"name": 200, "customer_name": 200, "message": 2000},
    "bookings": {"customer_name": 200, "contact_name": 200, "origin": 200, "destination": 200},
    "conversations": {"contact_name": 200, "last_message_preview": 500},
    "messages": {"body": 5000},
    "quotations": {"customer_name": 200},
    "audit_logs": {"summary": 1000},
    "notification_tasks": {"title": 300, "body": 1000},
    "vehicles": {"name": 200, "plate_number": 60},
    "drivers": {"name": 200},
}


def _env(key: str):
    """Ambil env; fallback membaca backend/.env (skrip guardrail dijalankan lepas app)."""
    val = os.environ.get(key)
    if val:
        return val
    env = ROOT / "backend" / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
    return None


def mongo_db():
    """(db, client) hidup — atau (None, None) bila pymongo/env tak tersedia."""
    try:
        from pymongo import MongoClient
    except Exception:  # noqa: BLE001
        return None, None
    url, name = _env("MONGO_URL"), _env("DB_NAME")
    if not (url and name):
        return None, None
    try:
        client = MongoClient(url, serverSelectionTimeoutMS=5000)
        return client[name], client
    except Exception:  # noqa: BLE001
        return None, None


def _phone_fields(doc):
    """Semua nilai field bernuansa telepon, termasuk yang BERSARANG.

    Perlu bersarang karena `conversion_events.identifiers.phone` (outbox konversi iklan)
    menyimpan nomor di dalam sub-dokumen. Sengaja TIDAK memakai pencocokan substring pada
    seluruh JSON: nilai uang seperti `10800000` mengandung "0800000" dan akan ikut terhapus.
    """
    out = []
    if isinstance(doc, dict):
        for key, val in doc.items():
            if isinstance(val, str) and ("phone" in key or key in ("contact", "wa")):
                out.append(val)
            elif isinstance(val, (dict, list)):
                out.extend(_phone_fields(val))
    elif isinstance(doc, list):
        for item in doc:
            out.extend(_phone_fields(item))
    return out


def _marker_hit(doc, markers=None, phones=None) -> bool:
    """True bila dokumen memuat penanda data uji.

    Dokumen bersumber `seed` dikecualikan supaya data demo yang sah tak pernah terhapus.
    """
    markers = markers if markers is not None else GUARD_MARKERS
    phones = phones if phones is not None else GUARD_PHONE_PREFIXES
    if isinstance(doc, dict) and doc.get("source") == "seed":
        return False
    blob = json.dumps(doc, default=str)
    if any(m in blob for m in markers):
        return True
    for val in _phone_fields(doc):
        if any(val.startswith(p) for p in phones):
            return True
    return False


def _overlong_hit(collection: str, doc) -> bool:
    for field, limit in OVERLONG_RULES.get(collection, {}).items():
        val = doc.get(field)
        if isinstance(val, str) and len(val) > limit:
            return True
    return False


def scan_test_pollution(extra_markers=(), extra_phones=(), extra_ids=()):
    """Deteksi (TANPA menghapus) artefak data uji di koleksi operasional.

    `extra_markers`/`extra_phones`/`extra_ids` dipakai skrip POC yang memiliki konvensi
    identitas sendiri (mis. `POC_PHONES` di `scripts/test_core_booking_v1.py`) — jadi POC pun
    bisa memakai mesin bersih-bersih yang SAMA, bukan bikin versi sendiri yang tak lengkap.

    Return: list of dict {collection, id, reason, label} — dipakai penjaga INV-CLEAN-01
    untuk MEMERAHKAN gate, dan `purge_test_pollution.py` untuk membersihkan.
    """
    db, client = mongo_db()
    if db is None:
        return None  # tak bisa memeriksa → pemanggil WAJIB memperlakukan sebagai pelanggaran
    markers = tuple(GUARD_MARKERS) + tuple(extra_markers)
    phones = tuple(GUARD_PHONE_PREFIXES) + tuple(extra_phones)
    ids = set(i for i in extra_ids if i)
    found = []
    try:
        existing = set(db.list_collection_names())
        for col in PURGE_COLLECTIONS:
            if col not in existing:
                continue
            for doc in db[col].find({}):
                reason = None
                if doc.get("id") in ids:
                    reason = "dokumen buatan skrip uji (dilacak per-ID)"
                elif _overlong_hit(col, doc):
                    reason = "teks raksasa (artefak uji adversarial)"
                elif _marker_hit(doc, markers, phones):
                    reason = "penanda data uji penjaga/smoke"
                if not reason:
                    continue
                label = ""
                for field in ("name", "customer_name", "contact_name", "title", "summary",
                              "code", "original_filename", "body", "type"):
                    val = doc.get(field)
                    if isinstance(val, str) and val:
                        label = val[:60] + ("…" if len(val) > 60 else "")
                        break
                # BUG-0128 — `_oid` WAJIB dibawa: tidak semua koleksi memakai konvensi field
                # `id` (mis. `content_stats` dikunci oleh pasangan kind+slug). Dulu langkah
                # hapus hanya memakai `id`, sehingga dokumen tanpa `id` LOLOS dari bersih-bersih
                # dan artefak uji tetap tampil di panel Analitik Konten — "gate hijau, produk
                # tidak bersih" (kelas bug yang sama dengan BUG-0127).
                found.append({"collection": col, "id": doc.get("id"),
                              "_oid": doc.get("_id"),
                              "reason": reason, "label": label})
    finally:
        if client is not None:
            client.close()
    return found


def purge_guard_artifacts(verbose: bool = False, extra_markers=(), extra_phones=(),
                          extra_ids=()) -> int:
    """Hapus SEMUA artefak data uji + side-effect-nya. Return jumlah dokumen terhapus.

    Dipakai di blok `finally` setiap penjaga/smoke/POC yang menulis lewat API. Aman dipanggil
    berkali-kali (idempotent) dan tak pernah raise (bersih-bersih != alur uji).
    """
    hits = scan_test_pollution(extra_markers, extra_phones, extra_ids)
    extra_ids = [i for i in (extra_ids or []) if i]
    if not hits and not extra_ids:
        return 0
    hits = hits or []
    db, client = mongo_db()
    if db is None:
        return 0
    removed = 0
    try:
        by_col = {}
        by_col_oid = {}
        for h in hits:
            by_col.setdefault(h["collection"], []).append(h["id"])
            # Dokumen TANPA field `id` (mis. `content_stats`) dihapus lewat `_id` Mongo-nya.
            if not h.get("id") and h.get("_oid") is not None:
                by_col_oid.setdefault(h["collection"], []).append(h["_oid"])
        # `extra_ids` ikut dipakai untuk CASCADE meski dokumen utamanya sudah dihapus pemanggil
        # (mis. POC menghapus lead-nya sendiri lebih dulu) — side-effect-nya tetap harus hilang.
        all_ids = [i for ids in by_col.values() for i in ids if i] + extra_ids
        booking_ids = by_col.get("bookings", []) + extra_ids
        lead_ids = by_col.get("leads", []) + extra_ids
        conv_ids = by_col.get("conversations", []) + extra_ids
        # Percakapan Inbox yang lahir dari lead uji (WA mock auto-ack) ikut dibuang.
        conv_ids += [c["id"] for c in db.conversations.find({"lead_id": {"$in": lead_ids}},
                                                            {"_id": 0, "id": 1})]
        trip_ids = [t["id"] for t in db.trips.find({"booking_id": {"$in": booking_ids}},
                                                   {"_id": 0, "id": 1})] if booking_ids else []
        # Kode pesanan uji (BK-00xx) dipakai untuk membuang pesan WA mock & notifikasi yang
        # MENYEBUT pesanan itu — kalau tidak, Inbox berisi "Booking BK-0029 dikonfirmasi" untuk
        # pesanan yang sudah tak ada (pengguna melihat riwayat yang mustahil ditelusuri).
        codes = [b.get("code") for b in db.bookings.find({"id": {"$in": booking_ids}},
                                                         {"_id": 0, "code": 1})
                 if b.get("code")] if booking_ids else []
        # Bukti transfer + aset medianya (panel "Bukti Bayar" ops harus ikut bersih).
        proof_media = [p.get("media_id") for p in db.payment_proofs.find(
            {"booking_id": {"$in": booking_ids}}, {"_id": 0, "media_id": 1})
            if p.get("media_id")] if booking_ids else []
        cascade = [
            ("payments", {"booking_id": {"$in": booking_ids}}),
            ("invoices", {"booking_id": {"$in": booking_ids}}),
            ("expenses", {"booking_id": {"$in": booking_ids}}),
            ("trips", {"booking_id": {"$in": booking_ids}}),
            ("payment_proofs", {"booking_id": {"$in": booking_ids}}),
            ("media_assets", {"id": {"$in": proof_media}}),
            ("locations", {"trip_id": {"$in": trip_ids}}),
            ("trip_shares", {"trip_id": {"$in": trip_ids}}),
            ("notification_tasks", {"booking_id": {"$in": booking_ids}}),
            ("messages", {"conversation_id": {"$in": conv_ids}}),
            ("conversations", {"id": {"$in": conv_ids}}),
            ("lead_activities", {"lead_id": {"$in": lead_ids}}),
            ("notification_tasks", {"lead_id": {"$in": lead_ids}}),
            # Jejak lintas-modul dari SETIAP dokumen uji: entri Audit Log, event otomasi,
            # notifikasi, dan outbox konversi iklan yang menunjuk dokumen itu. Tanpa ini Audit
            # Log & dasbor pemasaran melaporkan aktivitas yang entitasnya sudah tak ada.
            ("audit_logs", {"entity_id": {"$in": all_ids}}),
            ("events", {"ref_id": {"$in": all_ids}}),
            ("notification_tasks", {"ref_id": {"$in": all_ids}}),
            ("conversion_events", {"ref_id": {"$in": all_ids}}),
            ("landing_stats", {"page_id": {"$in": all_ids}}),
            # CMS-05/07: token pratinjau & permintaan ulasan yang menunjuk dokumen uji.
            ("content_previews", {"item_id": {"$in": all_ids}}),
            ("review_requests", {"booking_id": {"$in": booking_ids}}),
            # CMS-10/11/12: riwayat versi, baris tempat sampah, & pengalihan URL milik
            # dokumen uji. Tanpa cascade ini editor melihat "riwayat versi" dan "tempat
            # sampah" berisi konten yang tak pernah ada di CMS-nya (kelas BUG-0127/0128).
            ("content_versions", {"item_id": {"$in": all_ids}}),
            ("content_trash", {"item_id": {"$in": all_ids}}),
            ("content_redirects", {"item_id": {"$in": all_ids}}),
        ]
        for col, query in cascade:
            ids = list(query.values())[0].get("$in") or []
            if not ids:
                continue
            removed += db[col].delete_many(query).deleted_count
        # 2) dokumen yang ditandai langsung.
        for col, ids in by_col.items():
            ids = [i for i in ids if i]
            if not ids:
                continue
            removed += db[col].delete_many({"id": {"$in": ids}}).deleted_count
        # 2b) dokumen tanpa konvensi `id` — dihapus lewat `_id` (lihat BUG-0128).
        for col, oids in by_col_oid.items():
            if not oids:
                continue
            removed += db[col].delete_many({"_id": {"$in": oids}}).deleted_count
        # 3) automation_runs yang menunjuk event yang sudah tak ada (yatim akibat langkah 1).
        live_events = {e["id"] for e in db.events.find({}, {"_id": 0, "id": 1})}
        orphan_runs = [r["id"] for r in db.automation_runs.find({}, {"_id": 0, "id": 1,
                                                                     "event_id": 1})
                       if r.get("event_id") and r["event_id"] not in live_events]
        if orphan_runs:
            removed += db.automation_runs.delete_many({"id": {"$in": orphan_runs}}).deleted_count
        # 3b) entri Audit Log yang MENYEBUT dokumen uji di mana pun (snapshot before/after atau
        #     ringkasan) — mis. "Catat pembayaran … untuk booking BK-0015" ketika BK-0015 adalah
        #     pesanan uji. Tanpa ini Audit Log merujuk entitas yang sudah tak ada.
        if all_ids:
            id_set = set(all_ids)
            stale_audit = []
            for a in db.audit_logs.find({}):
                blob = json.dumps(a, default=str)
                if any(i in blob for i in id_set):
                    stale_audit.append(a.get("id"))
            if stale_audit:
                removed += db.audit_logs.delete_many({"id": {"$in": stale_audit}}).deleted_count
        # 3c) pesan WA mock / notifikasi / audit yang MENYEBUT kode pesanan uji (BK-00xx).
        for code in {c for c in codes if c}:
            rx = {"$regex": re.escape(code)}
            removed += db.messages.delete_many({"body": rx}).deleted_count
            removed += db.notification_tasks.delete_many(
                {"$or": [{"title": rx}, {"body": rx}]}).deleted_count
            removed += db.audit_logs.delete_many({"summary": rx}).deleted_count
        # 3d) aset bukti transfer yatim: tidak ada `payment_proofs` yang menunjuknya lagi.
        live_proof_media = {p.get("media_id") for p in db.payment_proofs.find(
            {}, {"_id": 0, "media_id": 1}) if p.get("media_id")}
        orphan_proof_assets = [m["id"] for m in db.media_assets.find(
            {"original_filename": "bukti"}, {"_id": 0, "id": 1})
            if m["id"] not in live_proof_media]
        if orphan_proof_assets:
            removed += db.media_assets.delete_many(
                {"id": {"$in": orphan_proof_assets}}).deleted_count
        # 4) percakapan yang menunjuk customer yang sudah dihapus (yatim di Inbox).
        live_cust = {c["id"] for c in db.customers.find({}, {"_id": 0, "id": 1})}
        orphan_conv = [c["id"] for c in db.conversations.find({}, {"_id": 0, "id": 1,
                                                                   "customer_id": 1})
                       if c.get("customer_id") and c["customer_id"] not in live_cust]
        if orphan_conv:
            removed += db.messages.delete_many(
                {"conversation_id": {"$in": orphan_conv}}).deleted_count
            removed += db.conversations.delete_many({"id": {"$in": orphan_conv}}).deleted_count
    except Exception as exc:  # noqa: BLE001 — bersih-bersih tak boleh menggagalkan uji
        if verbose:
            print(f"  {Y}[WARN]{X} bersih-bersih artefak uji gagal: {exc}")
    finally:
        if client is not None:
            client.close()
    if verbose and removed:
        print(f"    [{G}ok{X}] bersih-bersih: {removed} dokumen artefak uji dihapus "
              f"(ERP tetap bersih)")
    return removed


def purge_guard_bookings(phone_prefix: str = "") -> int:
    """Kompatibilitas: pemanggil lama meminta hapus pesanan uji per prefiks telepon.

    Sekarang mendelegasikan ke `purge_guard_artifacts()` yang membersihkan SELURUH artefak
    beserta side-effect (percakapan, pesan, notifikasi, event, audit, media). Prefiks tetap
    diterima agar tanda tangan lama tak berubah; SSOT penanda ada di `GUARD_MARKERS`.
    """
    _ = phone_prefix  # penanda kini terpusat (lihat GUARD_MARKERS/GUARD_PHONE_PREFIXES)
    return purge_guard_artifacts()


__all__ = ["ROOT", "BACKEND", "FRONTEND", "G", "R", "Y", "C", "B", "X", "Guard",
           "GUARD_MARKERS", "GUARD_PHONE_PREFIXES", "PURGE_COLLECTIONS", "OVERLONG_RULES",
           "mongo_db", "scan_test_pollution", "purge_guard_artifacts", "purge_guard_bookings"]

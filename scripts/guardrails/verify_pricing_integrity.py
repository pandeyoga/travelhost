#!/usr/bin/env python3
"""INV-PRICE-01 — Satu sumber harga: tanpa komponen jarak, DP satu pintu, tampil == tersimpan.

Kelas bug yang dicegah (semuanya PERNAH NYATA di repo ini)
--------------------------------------------------------
1. **Harga digerakkan penggeser jarak.** Total dulu memuat baris "Estimasi BBM (x km)" =
   `fuel_per_km × distance_km`, sementara `distance_km` DIISI PENGUNJUNG di kalkulator publik.
   Artinya tamu ikut menentukan harganya sendiri, dan angka di web tidak pernah sama dengan
   tagihan ops. Komponen itu dibuang; parameter `distance_km` dipertahankan hanya agar klien
   lama tidak pecah — dan penjaga ini memastikan ia benar-benar TIDAK dipakai lagi.
2. **DUA sumber `dp_percent`** (`settings.pricing_rules` untuk web, `settings.pricing_defaults`
   untuk ERP). Pemilik yang mengubah satu saja membuat DP di website berbeda dari DP yang
   ditagih ops — selisih uang yang tidak bisa dijelaskan ke pelanggan. Sekarang seluruh kode
   WAJIB lewat `services.pricing.get_dp_percent`.
3. **Harga yang TAMPIL bukan harga yang TERSIMPAN.** Kartu armada dulu memakai
   `vehicles.price_from` (angka pemasaran) sedangkan tagihan memakai tarif tipe → tamu
   membayar lebih dari yang dilihatnya.

STATIK  : mesin harga tidak boleh menyentuh jarak/BBM; hanya `services/pricing.py` yang boleh
          membaca `dp_percent` dari dokumen `settings`; kartu publik mengambil harga dari mesin.
RUNTIME : `distance_km` diubah drastis → total IDENTIK; rincian tidak memuat baris jarak/BBM;
          `total` = jumlah rincian; `dp_amount` = total × dp_percent; pesanan yang DIBUAT
          menyimpan angka yang SAMA dengan yang ditampilkan; kiriman `total_amount` palsu dari
          klien diabaikan; mengubah `dp_percent` di Pengaturan langsung mengubah DP di web.
"""
import ast
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
from _common import BACKEND, Guard, G, X, purge_guard_bookings  # noqa: E402

BASE = os.environ.get("GUARD_BASE_URL", "http://127.0.0.1:8001") + "/api"
PRICING = BACKEND / "services" / "pricing.py"

# Hanya file ini yang boleh membaca `dp_percent` dari dokumen settings (SATU pintu),
# ditambah router Pengaturan yang MENULIS + memvalidasinya.
DP_SOURCE_ALLOW = {"services/pricing.py", "routers/settings.py"}
# Penyebutan `fuel_per_km` yang SAH tanpa aritmatika (kunci usang yang tetap divalidasi supaya
# nilai basi di database tidak bisa negatif — perilaku itu dijaga INV-SET-01).
FUEL_MENTION_ALLOW = {
    "routers/settings.py": "kunci usang tetap ikut validasi non-negatif (INV-SET-01)",
}
# Aritmatika = tanda komponen jarak/BBM benar-benar dipakai menghitung harga.
DISTANCE_ARITH = re.compile(r"(distance_km|fuel_per_km)\s*[*/]|[*/]\s*(distance_km|fuel_per_km)")
# Modul yang MENENTUKAN harga jual. Di sini `distance_km` dalam perkalian apa pun = pelanggaran.
# (Di luar daftar ini `distance_km` sah: laporan trip/odometer & uang jalan sopir per km memang
# soal jarak — yang dilarang adalah jarak menentukan HARGA PELANGGAN.)
PRICING_SURFACES = {
    "services/pricing.py", "services/booking_search.py", "services/booking_public.py",
    "services/quotations.py", "routers/pricing.py", "routers/public.py",
    "routers/booking_public.py", "routers/quotations.py",
}
# Kata yang menandakan komponen jarak/BBM kembali ke rincian harga pelanggan.
DISTANCE_WORDS = ("bbm", "bahan bakar", "fuel", " km", "kilometer", "jarak")


def req(method, path, token=None, body=None, timeout=30):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return -1, str(e)


def jreq(method, path, token=None, body=None):
    st, txt = req(method, path, token, body)
    try:
        return st, json.loads(txt)
    except Exception:  # noqa: BLE001
        return st, {}


def login():
    st, data = jreq("POST", "/auth/login",
                    body={"email": "owner@demo.local", "password": "demo12345"})
    return data.get("token") if st == 200 else None


# ----------------------------------------------------------------------- STATIK
def _arith_hits(text: str):
    """Baris tempat `distance_km`/`fuel_per_km` benar-benar DIKALIKAN/DIBAGI.

    Dinilai lewat **AST**, bukan regex: percobaan pertama penjaga ini memakai regex dan
    langsung salah tuduh dua kali — pada tanda tangan `def compute_quote(..., distance_km=0)`
    dan pada docstring `distance_km/basis` (garis miring dalam prosa dibaca sebagai
    pembagian). Yang dilarang adalah PERHITUNGAN, jadi yang diperiksa harus pohon sintaks.
    """
    hits = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return hits
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mult, ast.Div)):
            for side in (node.left, node.right):
                blob = ast.unparse(side)
                if "distance_km" in blob or "fuel_per_km" in blob:
                    hits.append((getattr(node, "lineno", 0), ast.unparse(node)[:80]))
                    break
    return hits


def static_checks(g: Guard):
    src = PRICING.read_text(encoding="utf-8", errors="ignore")
    g.bump()
    if "def compute_quote" not in src:
        g.add("services/pricing.py: `compute_quote` hilang — mesin harga tunggal dibongkar.")

    # 1) jarak/BBM tidak boleh dipakai dalam ARITMATIKA mesin harga. Tanda tangan fungsi
    #    (`def compute_quote(..., distance_km=0, ...)`) SENGAJA dibiarkan: parameter itu
    #    dipertahankan agar pemanggil lama tidak pecah, yang dilarang adalah MEMAKAINYA.
    g.bump()
    for lineno, expr in _arith_hits(src):
        g.add(f"services/pricing.py:{lineno}: komponen jarak/BBM dipakai menghitung harga "
              f"→ harga kembali digerakkan input pengunjung: {expr!r}")

    # 2) modul lain sama sekali tidak boleh menghitung harga dari BBM per km.
    for path in sorted(BACKEND.rglob("*.py")):
        rel = str(path.relative_to(BACKEND))
        if rel.startswith("backend_test") or rel == "services/pricing.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        g.bump()
        for lineno, expr in _arith_hits(text):
            if "fuel_per_km" in expr or rel in PRICING_SURFACES:
                g.add(f"{rel}:{lineno}: menghitung dengan jarak/BBM pada permukaan harga "
                      f"→ komponen jarak harus mati (harga = hari × tarif): {expr!r}")
        if "fuel_per_km" in text and rel not in FUEL_MENTION_ALLOW:
            g.add(f"{rel}: menyebut `fuel_per_km` tanpa alasan terdaftar → tambahkan ke "
                  f"FUEL_MENTION_ALLOW beserta alasannya, atau hapus.")

        # 3) SATU sumber dp_percent: dilarang membaca dp_percent dari dokumen settings.
        g.bump()
        if rel not in DP_SOURCE_ALLOW and "dp_percent" in text:
            for lineno, line in enumerate(text.splitlines(), 1):
                if "dp_percent" not in line:
                    continue
                window = "\n".join(text.splitlines()[max(0, lineno - 6):lineno])
                if 'find_one({"key": "pricing' in window:
                    g.add(f"{rel}:{lineno}: membaca `dp_percent` langsung dari dokumen "
                          f"`settings` → sumber DP kedua (pakai "
                          f"`services.pricing.get_dp_percent`).")

    # 4) kartu publik: harga tampil WAJIB berasal dari mesin (bukan angka pemasaran).
    bs = (BACKEND / "services" / "booking_search.py").read_text(encoding="utf-8",
                                                                errors="ignore")
    g.bump()
    if "get_dp_percent" not in bs:
        g.add("services/booking_search.py: tidak memakai `get_dp_percent` → DP kartu/pencarian "
              "bisa berbeda dari DP yang ditagih.")
    g.bump()
    if 'v.get("price_from")' in bs:
        g.add("services/booking_search.py: `price_from` armada dipakai lagi sebagai harga tampil "
              "→ tampil != tersimpan (harga harus dari `resolve_day_rate`).")


# ---------------------------------------------------------------------- RUNTIME
def _window(days_ahead=21, days=2):
    start = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).replace(
        hour=9, minute=0, second=0, microsecond=0)
    return start.isoformat(), (start + timedelta(days=days)).isoformat()


def _search(start_iso, end_iso, extra=None):
    body = {"service": "daily_rental", "start_datetime": start_iso,
            "end_datetime": end_iso, "pax": 2}
    body.update(extra or {})
    return jreq("POST", "/public/booking/search", body=body)


def runtime_checks(g: Guard, tok: str):
    created = []          # (code, token) → dibersihkan di akhir
    restore_dp = None     # nilai dp_percent asli
    try:
        # R1 — kalkulator publik: jarak diubah drastis, total WAJIB identik.
        est = {"vehicle_type": "hiace_premio", "days": 3, "pax": 4}
        st1, a = jreq("POST", "/public/trip-estimate", body={**est, "distance_km": 0})
        st2, b = jreq("POST", "/public/trip-estimate", body={**est, "distance_km": 5000})
        g.bump(2)
        if st1 != 200 or st2 != 200:
            g.add(f"/public/trip-estimate tidak sehat (HTTP {st1}/{st2}) — tak bisa "
                  f"membuktikan jarak diabaikan.")
        else:
            ta, tb = a.get("total"), b.get("total")
            if ta != tb:
                g.add(f"jarak MASIH mempengaruhi harga: distance_km=0 → {ta}, "
                      f"distance_km=5000 → {tb} (pengunjung ikut menentukan harga).")
            else:
                print(f"    [{G}ok{X}] jarak diabaikan: total tetap {ta} "
                      f"pada distance_km 0 vs 5000")
            for row in (a.get("breakdown") or []):
                label = str(row.get("label") or "").lower()
                if any(w in label for w in DISTANCE_WORDS):
                    g.add(f"rincian harga memuat komponen jarak/BBM: {row.get('label')!r}")

        # R2 — pencarian: total = jumlah rincian; dp_amount = total × dp_percent.
        start_iso, end_iso = _window()
        st, res = _search(start_iso, end_iso)
        g.bump()
        if st != 200:
            g.add(f"POST /public/booking/search → HTTP {st} (gagal memverifikasi harga).")
            return
        options = res.get("options") or []
        if not options:
            g.add("tidak ada unit tersedia pada jendela uji → penjaga tak bisa membuktikan "
                  "harga (SKIP = tidak diizinkan; perbaiki data armada/seed).")
            return
        for opt in options:
            q = opt.get("quote") or {}
            rows = q.get("breakdown") or []
            g.bump(3)
            summed = sum(int(r.get("amount") or 0) for r in rows)
            if abs(summed - int(q.get("total") or 0)) > 1000:
                g.add(f"{opt['vehicle']['code']}: total {q.get('total')} != jumlah rincian "
                      f"{summed} → angka yang dilihat tamu tidak bisa "
                      f"dipertanggungjawabkan.")
            expect_dp = round(int(q.get("total") or 0) * int(q.get("dp_percent") or 0) / 100.0)
            if abs(expect_dp - int(q.get("dp_amount") or 0)) > 1000:
                g.add(f"{opt['vehicle']['code']}: dp_amount {q.get('dp_amount')} tidak sesuai "
                      f"{q.get('dp_percent')}% dari total {q.get('total')}.")
            for row in rows:
                label = str(row.get("label") or "").lower()
                if any(w in label for w in DISTANCE_WORDS):
                    g.add(f"{opt['vehicle']['code']}: rincian memuat komponen jarak/BBM "
                          f"({row.get('label')!r}).")
        print(f"    [{G}ok{X}] {len(options)} unit: total = jumlah rincian & DP konsisten")

        # R3 — tampil == tersimpan + kiriman total palsu dari klien DIABAIKAN.
        first = options[0]
        quoted_total = int((first["quote"] or {}).get("total") or 0)
        submit = {
            "service": "daily_rental", "vehicle_id": first["vehicle"]["id"],
            "start_datetime": start_iso, "end_datetime": end_iso, "pax": 2,
            "name": "Penjaga INV-PRICE-01", "phone": "0800000101",
            "marketing_consent": False,
            # angka palsu yang WAJIB diabaikan server:
            "total_amount": 1, "total": 1, "base_price": 1, "dp_amount": 1, "dp_percent": 1,
        }
        st, made = jreq("POST", "/public/booking/submit", body=submit)
        g.bump(2)
        if st != 200 or not made.get("code"):
            g.add(f"POST /public/booking/submit → HTTP {st} ({str(made)[:120]}) — jalur "
                  f"pemesanan tidak bisa diverifikasi.")
        else:
            created.append((made["code"], made.get("token") or ""))
            stored = int(made.get("total_amount") or 0)
            if stored != quoted_total:
                g.add(f"harga TAMPIL {quoted_total} != harga TERSIMPAN {stored} "
                      f"(atau total kiriman klien diterima) pada {made['code']}.")
            else:
                print(f"    [{G}ok{X}] {made['code']}: tersimpan Rp {stored:,} = harga yang "
                      f"ditampilkan; total palsu dari klien diabaikan".replace(",", "."))

        # R4 — SATU sumber DP: ubah di Pengaturan → DP di web ikut berubah.
        st, settings = jreq("GET", "/settings", tok)
        rules = (settings or {}).get("pricing_rules") or {}
        current_dp = int(rules.get("dp_percent") or 30)
        probe_dp = 45 if current_dp != 45 else 35
        restore_dp = current_dp
        st, _ = jreq("PATCH", "/settings", tok,
                     body={"pricing_rules": {**rules, "dp_percent": probe_dp}})
        g.bump()
        if st != 200:
            g.add(f"PATCH /settings dp_percent={probe_dp} → HTTP {st} (tak bisa menguji "
                  f"sumber DP tunggal).")
        else:
            st, res2 = _search(start_iso, end_iso)
            got = int(((res2.get("options") or [{}])[0].get("quote") or {}).get("dp_percent")
                      or 0) if (res2.get("options") or []) else -1
            g.bump()
            if got != probe_dp:
                g.add(f"dp_percent Pengaturan diubah ke {probe_dp} tetapi pencarian publik "
                      f"masih memakai {got} → sumber DP ganda (web vs ERP bisa berbeda).")
            else:
                print(f"    [{G}ok{X}] DP satu pintu: Pengaturan {probe_dp}% → web {got}%")
    finally:
        if restore_dp is not None:
            st, settings = jreq("GET", "/settings", tok)
            rules = (settings or {}).get("pricing_rules") or {}
            jreq("PATCH", "/settings", tok,
                 body={"pricing_rules": {**rules, "dp_percent": restore_dp}})
        for code, token in created:
            jreq("POST", f"/public/booking/{code}/cancel",
                 body={"token": token, "reason": "bersih-bersih guardrail INV-PRICE-01"})
        purged = purge_guard_bookings("08000001")
        if created:
            print(f"    [{G}ok{X}] bersih-bersih: {len(created)} pesanan uji dibatalkan, "
                  f"{purged} dokumen uji dihapus (tabel ops tetap bersih)")


def main() -> int:
    g = Guard("INV-PRICE-01",
              "Harga: tanpa komponen jarak, DP satu sumber, tampil == tersimpan")
    static_checks(g)
    tok = login()
    if not tok:
        g.add("tidak bisa login owner@demo.local — gate runtime WAJIB jalan (SKIP != PASS). "
              "Pastikan backend hidup & data demo ter-seed.")
        return g.finish()
    runtime_checks(g, tok)
    return g.finish()


if __name__ == "__main__":
    sys.exit(main())

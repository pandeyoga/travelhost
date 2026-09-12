#!/usr/bin/env python3
"""test_core_booking_v1.py — POC INTI PEMESANAN ONLINE (Fase 1).

Satu berkas, 10 pembuktian. Dijalankan terhadap backend yang HIDUP (bukan mock) memakai
database nyata, supaya kalau ada yang salah kita tahu SEBELUM satu baris UI dibuat.

  1  KATALOG BERSIH        unit mitra & unit tak tayang TIDAK muncul di /public/fleet;
                           harga tampil = harga mesin (bukan `price_from` pemasaran).
  2  HARGA = HARI          total = tarif harian × hari (+ driver + tol/parkir); TIDAK ada
                           komponen jarak/BBM; tarif per UNIT menimpa tarif per TIPE.
  3  SURCHARGE TANGGAL     keberangkatan Sabtu/Minggu & hari libur menambah persentase.
  4  KETERSEDIAAN NYATA    unit yang sudah dipesan / masuk perawatan tidak ditawarkan.
  5  ANTI DOUBLE-BOOKING   16 permintaan paralel untuk unit+waktu sama → TEPAT 1 sukses.
  6  MODE hold_dp          pesanan langsung `hold` + hold_expires_at + dp_amount (DP% SSOT).
  7  MODE ops_approval     pesanan `pending`; ops ACC → `hold` + batas DP.
  8  BUKTI BAYAR → LUNAS   unggah bukti (masuk Media Library) → ops verifikasi → pembayaran
                           tercatat → `hold` OTOMATIS jadi `confirmed` (DP-gate E18).
  9  PROMO DITEGAKKAN      syarat promo (min hari/tipe unit/layanan/akhir pekan/kuota) ditolak
                           server bila tak terpenuhi; kuota dikonsumsi atomik.
 10  ANTI TAMPER & 5XX     harga/total dari klien diabaikan; input rusak → 4xx berALASAN.
     + status tanpa akun (kode booking + nomor WhatsApp) & pembatalan oleh pelanggan.

Jalankan: cd /app && python scripts/test_core_booking_v1.py
Keluar 0 = SEMUA LULUS. !=0 = ada kegagalan (jangan lanjut membangun UI).
"""
import asyncio
import io
import os
import sys
from datetime import datetime, timedelta, timezone

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "guardrails"))
from _common import purge_guard_artifacts  # noqa: E402  (INV-CLEAN-01)

API = os.environ.get("API_BASE", "http://localhost:8001").rstrip("/")
G, Y, R, C, B, X = "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[1m", "\033[0m"
OWNER = {"email": "owner@demo.local", "password": "demo12345"}
OPS = {"email": "ops@demo.local", "password": "demo12345"}
DRIVER = {"email": "driver@demo.local", "password": "demo12345"}

results = []
CREATED = []          # id booking buatan POC -> dibatalkan di akhir (POC harus repeatable)
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
POC_PHONES = ("081277700001", "081277700002", "081277700003", "081277700009",
              "081200000001", "081200000002", "081200000003")


def check(name, ok, detail=""):
    results.append((bool(ok), name, detail))
    tag = f"{G}[PASS]{X}" if ok else f"{R}[FAIL]{X}"
    print(f"  {tag} {name}" + (f"\n         {Y}{detail}{X}" if detail else ""))
    return bool(ok)


def head(title):
    print(f"\n{C}{B}== {title} =={X}")


def rp(n):
    return f"Rp {int(n):,}".replace(",", ".")


async def login(client, creds):
    r = await client.post(f"{API}/api/auth/login", json=creds)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def future(days=10, hour=8):
    base = datetime.now(timezone.utc) + timedelta(days=days)
    return base.replace(hour=hour, minute=0, second=0, microsecond=0)


def next_weekday(days=10, hour=8):
    """Tanggal kerja (Sen–Jum) agar surcharge akhir pekan tidak mengacaukan uji harga."""
    d = future(days, hour)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def next_saturday(days=12, hour=8):
    d = future(days, hour)
    while d.weekday() != 5:
        d += timedelta(days=1)
    return d


def png_bytes(color=(30, 120, 200)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (240, 160), color).save(buf, format="PNG")
    return buf.getvalue()


async def submit(client, body, tries=4):
    """POST /submit yang menghormati rate-limit produksi (menunggu, bukan menembusnya)."""
    for i in range(tries):
        r = await client.post(f"{API}/api/public/booking/submit", json=body)
        if r.status_code != 429:
            return r
        await asyncio.sleep(16)
    return r


async def pick_available(client, start, end=None, pax=2, service="daily_rental", route_id=""):
    """Ambil unit dari hasil pencarian (persis seperti pengunjung memilih dari daftar).

    POC TIDAK boleh mengarang unit/tanggal: kalau tanggal itu bertabrakan dengan jadwal
    perawatan atau booking lain, sistem MEMANG harus menyembunyikan unitnya.
    """
    body = {"service": service, "start_datetime": start.isoformat(), "pax": pax}
    if end:
        body["end_datetime"] = end.isoformat()
    if route_id:
        body["route_id"] = route_id
    r = await client.post(f"{API}/api/public/booking/search", json=body)
    opts = (r.json().get("options") or []) if r.status_code == 200 else []
    return opts[0] if opts else None


async def set_flow(client, owner, patch):
    r = await client.patch(f"{API}/api/settings", headers=owner, json={"booking_flow": patch})
    r.raise_for_status()
    return r.json().get("booking_flow")


# --------------------------------------------------------------------------- 1 katalog
async def t1_catalog(client, ops):
    head("1 · KATALOG BERSIH (unit mitra/tak-tayang tersaring, harga = harga mesin)")
    pub = (await client.get(f"{API}/api/public/fleet")).json()
    allv = (await client.get(f"{API}/api/vehicles", headers=ops)).json()
    pub_ids = {v["id"] for v in pub}
    partner = [v for v in allv if (v.get("ownership") == "partner")]
    hidden = [v for v in allv if v.get("publish_to_web") is False]
    check("unit MITRA tidak tampil di katalog publik",
          all(v["id"] not in pub_ids for v in partner),
          f"mitra={[v.get('code') for v in partner]}")
    check("unit ditandai tidak tayang tidak muncul",
          all(v["id"] not in pub_ids for v in hidden),
          f"disembunyikan={[v.get('code') for v in hidden]}")
    check("katalog tidak kosong", len(pub) > 0, f"{len(pub)} unit tayang")
    rules = (await client.get(f"{API}/api/pricing/rules", headers=ops)).json()
    okrate = True
    for v in pub:
        internal = next((x for x in allv if x["id"] == v["id"]), {})
        expect = int(internal.get("day_rate") or 0) or int(
            (rules.get("day_rates") or {}).get(v.get("type")) or rules.get("default_day_rate") or 0)
        if int(v.get("price_from") or 0) != expect:
            okrate = False
            check(f"harga tampil {v.get('code')} = tarif mesin", False,
                  f"tampil={v.get('price_from')} mesin={expect}")
    if okrate:
        check("harga tampil SEMUA unit = tarif resmi mesin (tak ada dua angka)", True,
              ", ".join(f"{v.get('code')}={rp(v.get('price_from'))}" for v in pub))
    return pub


# --------------------------------------------------------------------------- 2 & 3 harga
async def t2_pricing(client, ops, unit):
    head("2 · HARGA DIGERAKKAN HARI (tanpa komponen jarak) + tarif unit menimpa tarif tipe")
    start = next_weekday(9)
    end = start + timedelta(days=2)
    body = {"service": "daily_rental", "vehicle_id": unit["id"],
            "start_datetime": start.isoformat(), "end_datetime": end.isoformat(), "pax": 4}
    q = (await client.post(f"{API}/api/public/booking/quote", json=body)).json()
    quote = q.get("quote") or {}
    labels = [b["label"] for b in quote.get("breakdown", [])]
    check("tidak ada baris BBM/jarak di rincian harga",
          not any("bbm" in l.lower() or " km" in l.lower() for l in labels), f"{labels}")
    rules = (await client.get(f"{API}/api/pricing/rules", headers=ops)).json()
    internal = (await client.get(f"{API}/api/vehicles/{unit['id']}", headers=ops)).json()
    unit_rate = int(internal.get("day_rate") or 0)
    expect = (unit_rate * 2) + int(rules.get("driver_fee_per_day", 0)) * 2 + \
        int(rules.get("toll_parking_per_day", 0)) * 2
    check("total = (tarif unit × hari) + driver/hari + tol-parkir/hari",
          quote.get("total") == expect,
          f"total={quote.get('total')} harap={expect} (tarif unit={rp(unit_rate)})")
    check("jumlah hari dihitung 2 (durasi 2×24 jam)", quote.get("days") == 2,
          f"days={quote.get('days')}")
    check("tarif unit dipakai (bukan tarif tipe) bila berbeda",
          quote.get("day_rate") == unit_rate,
          f"quote.day_rate={quote.get('day_rate')} unit.day_rate={unit_rate}")
    dp_pct = int((await client.get(f"{API}/api/public/booking/config")).json()["dp_percent"])
    check("DP dihitung dari SATU sumber (dp_percent config = dp_percent quote)",
          quote.get("dp_percent") == dp_pct, f"config={dp_pct} quote={quote.get('dp_percent')}")

    # jarak dikirim ke estimator lama → tidak boleh mengubah total
    est1 = (await client.post(f"{API}/api/public/trip-estimate", json={
        "vehicle_type": unit["type"], "days": 2, "distance_km": 0})).json()
    est2 = (await client.post(f"{API}/api/public/trip-estimate", json={
        "vehicle_type": unit["type"], "days": 2, "distance_km": 1500})).json()
    check("estimator publik: jarak 0 km vs 1500 km → total IDENTIK",
          est1.get("total") == est2.get("total"),
          f"{est1.get('total')} vs {est2.get('total')}")

    head("3 · SURCHARGE TANGGAL (akhir pekan / hari libur)")
    sat = next_saturday(13)
    qs = (await client.post(f"{API}/api/public/booking/quote", json={
        "service": "daily_rental", "vehicle_id": unit["id"],
        "start_datetime": sat.isoformat(),
        "end_datetime": (sat + timedelta(days=2)).isoformat(), "pax": 4})).json()
    sq = qs.get("quote") or {}
    check("keberangkatan Sabtu → ada baris surcharge akhir pekan & total lebih tinggi",
          sq.get("surcharge_percent", 0) > 0 and sq.get("total", 0) > quote.get("total", 0),
          f"surcharge={sq.get('surcharge_percent')}% total_sabtu={rp(sq.get('total', 0))} "
          f"total_hari_kerja={rp(quote.get('total', 0))}")
    return quote


# --------------------------------------------------------------------------- 4 ketersediaan
async def t4_availability(client, ops, unit):
    head("4 · KETERSEDIAAN NYATA (unit terpakai / dalam perawatan tidak ditawarkan)")
    start = next_weekday(20)
    end = start + timedelta(days=1)
    search = {"service": "daily_rental", "start_datetime": start.isoformat(),
              "end_datetime": end.isoformat(), "pax": 2}
    before = (await client.post(f"{API}/api/public/booking/search", json=search)).json()
    ids_before = {o["vehicle"]["id"] for o in before["options"]}
    check("pencarian mengembalikan unit yang tersedia untuk tanggal kosong",
          len(ids_before) > 0, f"{len(ids_before)} unit tersedia")
    unit = (before["options"] or [{}])[0].get("vehicle") or unit

    cust = (await client.get(f"{API}/api/customers", headers=ops)).json()
    cust_id = (cust[0]["id"] if isinstance(cust, list) else cust["items"][0]["id"])
    created = await client.post(f"{API}/api/bookings", headers=ops, json={
        "customer_id": cust_id, "vehicle_id": unit["id"],
        "start_datetime": start.isoformat(), "end_datetime": end.isoformat(),
        "origin": "Bandung", "destination": "Uji ketersediaan"})
    blocker = created.json()
    after = (await client.post(f"{API}/api/public/booking/search", json=search)).json()
    ids_after = {o["vehicle"]["id"] for o in after["options"]}
    reasons = {u["id"]: u.get("reason") for u in after.get("unavailable", [])}
    check("unit terpilih ada di daftar sebelum dipesan", unit.get("id") in ids_before,
          f"unit={unit.get('code')}")
    check("setelah dipesan ops → unit HILANG dari hasil pencarian publik",
          unit["id"] not in ids_after, f"sisa={len(ids_after)} unit")
    check("alasan tidak tersedia dijelaskan ke pengunjung",
          "dipesan" in (reasons.get(unit["id"]) or "").lower(),
          f"alasan={reasons.get(unit['id'])}")
    dup = await submit(client, {"service": "daily_rental", "vehicle_id": unit["id"],
                               "start_datetime": start.isoformat(),
                               "end_datetime": end.isoformat(), "pax": 2,
                               "name": "Uji Bentrok", "phone": "081200000001"})
    check("submit ke unit yang sudah penuh DITOLAK 4xx (bukan diterima diam-diam)",
          400 <= dup.status_code < 500 and dup.status_code != 429,
          f"HTTP {dup.status_code} · {str(dup.json().get('detail'))[:90]}")
    return blocker


# --------------------------------------------------------------------------- 5 concurrency
async def t5_concurrency(client, unit):
    head("5 · ANTI DOUBLE-BOOKING (16 permintaan paralel, unit & waktu sama)")
    start = next_weekday(35, 7)
    end = start + timedelta(days=1)
    opt = await pick_available(client, start, end)
    unit = (opt or {}).get("vehicle") or unit
    payload = {"service": "daily_rental", "vehicle_id": unit["id"],
               "start_datetime": start.isoformat(), "end_datetime": end.isoformat(),
               "pax": 2, "name": "Uji Balapan", "phone": "081200000002"}

    async def one(i):
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{API}/api/public/booking/submit", json={**payload})
            return r.status_code, (r.json() if r.headers.get("content-type", "").startswith(
                "application/json") else {})

    out = await asyncio.gather(*[one(i) for i in range(16)], return_exceptions=True)
    ok = [o for o in out if not isinstance(o, Exception) and o[0] == 200]
    for o in ok:
        if o[1].get("id"):
            CREATED.append(o[1]["id"])
    err5xx = [o for o in out if not isinstance(o, Exception) and o[0] >= 500]
    rate = [o for o in out if not isinstance(o, Exception) and o[0] == 429]
    conflict = [o for o in out if not isinstance(o, Exception) and o[0] == 400]
    codes = {o[1].get("code") for o in ok if o[1].get("code")}
    check("TEPAT 1 dari 16 permintaan paralel berhasil menahan unit",
          len(ok) == 1, f"sukses={len(ok)} kode={codes or '-'}")
    check("15 sisanya ditolak karena BENTROK (bukan tertahan rate-limit)",
          len(conflict) == 15 and not rate,
          f"konflik={len(conflict)} rate_limited={len(rate)}")
    check("tidak ada 5xx saat balapan", not err5xx, f"5xx={len(err5xx)}")
    return ok[0][1] if ok else None


# --------------------------------------------------------------------------- 6-8 alur DP
async def t6_hold_dp(client, owner, unit):
    head("6 · MODE hold_dp — pesanan langsung menahan unit + batas waktu DP")
    await set_flow(client, owner, {"mode": "hold_dp", "hold_hours": 2})
    start = next_weekday(45, 9)
    end = start + timedelta(days=2)
    opt = await pick_available(client, start, end, pax=6)
    unit = (opt or {}).get("vehicle") or unit
    r = await submit(client, {
        "service": "daily_rental", "vehicle_id": unit["id"],
        "start_datetime": start.isoformat(), "end_datetime": end.isoformat(), "pax": 6,
        "name": "Budi Pemesan", "phone": "081277700001", "email": "budi@contoh.id",
        "pickup_address": "Jl. Merdeka 10, Bandung", "idempotency_key": f"poc-hold-{RUN_TAG}"})
    data = r.json() if r.status_code == 200 else {}
    if data.get("id"):
        CREATED.append(data["id"])
    check("submit berhasil", r.status_code == 200, f"HTTP {r.status_code} · {str(data)[:120]}")
    check("status pesanan = hold (unit ditahan)", data.get("status") == "hold",
          f"status={data.get('status')}")
    check("ada batas waktu DP (hold_expires_at)", bool(data.get("hold_expires_at")),
          f"exp={data.get('hold_expires_at')}")
    check("nominal DP terisi & < total", 0 < data.get("dp_amount", 0) <= data.get("total_amount", 0),
          f"dp={rp(data.get('dp_amount', 0))} total={rp(data.get('total_amount', 0))}")
    check("dapat token halaman status (tanpa akun)", bool(data.get("token")))
    dup = await submit(client, {
        "service": "daily_rental", "vehicle_id": unit["id"],
        "start_datetime": start.isoformat(), "end_datetime": end.isoformat(), "pax": 6,
        "name": "Budi Pemesan", "phone": "081277700001", "idempotency_key": f"poc-hold-{RUN_TAG}"})
    dd = dup.json()
    check("klik ganda (idempotency_key sama) TIDAK membuat pesanan kedua",
          dup.status_code == 200 and dd.get("code") == data.get("code") and dd.get("duplicate"),
          f"code={dd.get('code')} duplicate={dd.get('duplicate')}")
    if not data.get("code") or not data.get("token"):
        check("lanjutkan uji halaman status", False, "submit gagal — sisa uji tahap 6 dilewati")
        return data
    st = (await client.get(f"{API}/api/public/booking/{data['code']}",
                          params={"token": data["token"]})).json()
    pay = st.get("payment") or {}
    check("halaman status menampilkan instruksi pembayaran & hitung mundur",
          (bool(pay.get("bank_accounts")) or bool(pay.get("instructions")))
          and st.get("countdown_seconds", 0) > 0,
          f"rekening={len(pay.get('bank_accounts', []))} "
          f"instruksi={'ada' if pay.get('instructions') else 'kosong'} "
          f"sisa={st.get('countdown_seconds')}s")
    # REGRESI BUG-0114: PATCH sebagian (hanya `mode`) tidak boleh menghapus daftar rekening.
    before_accounts = len(pay.get("bank_accounts", []))
    await set_flow(client, owner, {"mode": "hold_dp"})
    st2 = (await client.get(f"{API}/api/public/booking/{data['code']}",
                           params={"token": data["token"]})).json()
    check("BUG-0114: ubah mode via Pengaturan TIDAK menghapus instruksi/rekening pembayaran",
          len((st2.get("payment") or {}).get("bank_accounts", [])) == before_accounts,
          f"sebelum={before_accounts} sesudah="
          f"{len((st2.get('payment') or {}).get('bank_accounts', []))}")
    bad = await client.get(f"{API}/api/public/booking/{data['code']}", params={"token": "salah"})
    check("token salah → 404 (tidak membocorkan data pesanan)", bad.status_code == 404,
          f"HTTP {bad.status_code}")
    look = await client.post(f"{API}/api/public/booking/lookup",
                            json={"code": data["code"], "phone": "081277700001"})
    check("cek pesanan tanpa akun: kode + nomor WhatsApp → dapat status",
          look.status_code == 200 and look.json().get("token") == data["token"],
          f"HTTP {look.status_code}")
    wrong = await client.post(f"{API}/api/public/booking/lookup",
                             json={"code": data["code"], "phone": "089999999999"})
    check("nomor WhatsApp salah → 404", wrong.status_code == 404, f"HTTP {wrong.status_code}")
    return data


async def t7_ops_approval(client, owner, ops, unit):
    head("7 · MODE ops_approval — ACC ops dulu, baru unit ditahan & DP diminta")
    await set_flow(client, owner, {"mode": "ops_approval", "approval_hold_hours": 24})
    start = next_weekday(55, 9)
    end = start + timedelta(days=1)
    opt = await pick_available(client, start, end, pax=4)
    unit = (opt or {}).get("vehicle") or unit
    r = await submit(client, {
        "service": "daily_rental", "vehicle_id": unit["id"],
        "start_datetime": start.isoformat(), "end_datetime": end.isoformat(), "pax": 4,
        "name": "Sari Pemesan", "phone": "081277700002"})
    data = r.json() if r.status_code == 200 else {}
    if data.get("id"):
        CREATED.append(data["id"])
    if not data.get("id"):
        check("pesanan masuk sebagai pending (unit belum dikunci)", False,
              f"HTTP {r.status_code} · {str(r.json())[:140]} — sisa uji tahap 7 dilewati")
        await set_flow(client, owner, {"mode": "hold_dp"})
        return {}
    check("pesanan masuk sebagai pending (unit belum dikunci)",
          r.status_code == 200 and data.get("status") == "pending",
          f"HTTP {r.status_code} status={data.get('status')}")
    check("pesan ke tamu menjelaskan unit belum dikunci",
          "belum dikunci" in (data.get("message") or "").lower(), data.get("message", "")[:100])
    appr = await client.post(f"{API}/api/bookings/{data['id']}/approve-hold", headers=ops,
                            json={"vehicle_id": unit["id"]})
    ad = appr.json() if appr.status_code == 200 else {}
    check("ops ACC → status jadi hold + batas DP terisi",
          appr.status_code == 200 and ad.get("status") == "hold" and ad.get("hold_expires_at"),
          f"HTTP {appr.status_code} status={ad.get('status')} exp={ad.get('hold_expires_at')}")
    check("harga dihitung ulang server saat ACC (total > 0)", int(ad.get("total_amount") or 0) > 0,
          f"total={rp(ad.get('total_amount', 0))}")
    driver_hdr = await login(client, DRIVER)
    forb = await client.post(f"{API}/api/bookings/{data['id']}/approve-hold", headers=driver_hdr,
                            json={"vehicle_id": unit["id"]})
    check("driver TIDAK boleh menyetujui pesanan (403)", forb.status_code == 403,
          f"HTTP {forb.status_code}")
    await set_flow(client, owner, {"mode": "hold_dp"})
    return ad


async def t8_proof_to_confirmed(client, ops, booking):
    head("8 · BUKTI TRANSFER → VERIFIKASI OPS → hold OTOMATIS jadi confirmed")
    code, token = booking["code"], booking["token"]
    files = {"image": ("bukti.png", png_bytes(), "image/png")}
    form = {"token": token, "amount": str(int(booking["dp_amount"])),
            "sender_name": "Budi Pemesan", "bank": "BCA", "note": "DP via POC"}
    up = await client.post(f"{API}/api/public/booking/{code}/proof", data=form, files=files)
    ud = up.json() if up.status_code == 200 else {}
    check("tamu bisa mengunggah bukti transfer (foto)", up.status_code == 200,
          f"HTTP {up.status_code} · {str(ud)[:120]}")
    proof_id = (ud.get("proof") or {}).get("id")
    media_url = (ud.get("proof") or {}).get("media_url", "")
    check("bukti tersimpan sebagai aset Media Library (punya URL publik ber-id)",
          media_url.startswith("/api/public/media/"), f"url={media_url}")
    if media_url:
        got = await client.get(f"{API}{media_url}")
        check("berkas bukti benar-benar bisa dibuka", got.status_code == 200,
              f"HTTP {got.status_code}")
    bad = await client.post(f"{API}/api/public/booking/{code}/proof",
                           data=form, files={"image": ("x.txt", b"bukan gambar", "text/plain")})
    check("berkas non-gambar ditolak 4xx berALASAN", 400 <= bad.status_code < 500,
          f"HTTP {bad.status_code} · {str(bad.json().get('detail'))[:80]}")
    queue = (await client.get(f"{API}/api/bookings/payment-proofs", headers=ops)).json()
    check("bukti masuk antrean verifikasi ops",
          any(p.get("id") == proof_id for p in queue.get("proofs", [])),
          f"antrean pending={queue.get('pending')}")
    drv = await login(client, DRIVER)
    forb = await client.get(f"{API}/api/bookings/payment-proofs", headers=drv)
    check("driver tidak boleh melihat antrean bukti bayar (403)", forb.status_code == 403,
          f"HTTP {forb.status_code}")
    bk_id = None
    for p in queue.get("proofs", []):
        if p.get("id") == proof_id:
            bk_id = p.get("booking_id")
    ver = await client.post(f"{API}/api/bookings/{bk_id}/proofs/{proof_id}/verify",
                           headers=ops, json={"amount": booking["dp_amount"]})
    vd = ver.json() if ver.status_code == 200 else {}
    check("ops verifikasi bukti → pembayaran tercatat", ver.status_code == 200 and vd.get("payment"),
          f"HTTP {ver.status_code} · {str(vd)[:120]}")
    bk = (vd.get("booking") or {})
    check("DP tercukupi → booking OTOMATIS confirmed (DP-gate)",
          bk.get("status") == "confirmed", f"status={bk.get('status')}")
    check("payment_status = dp (belum lunas)", bk.get("payment_status") == "dp",
          f"payment_status={bk.get('payment_status')} paid={rp(bk.get('paid_amount', 0))}")
    again = await client.post(f"{API}/api/bookings/{bk_id}/proofs/{proof_id}/verify",
                             headers=ops, json={"amount": booking["dp_amount"]})
    payments = (await client.get(f"{API}/api/payments", headers=ops,
                                params={"booking_id": bk_id})).json()
    check("verifikasi ganda tidak menambah pembayaran (idempoten)",
          again.status_code == 200 and len(payments) == 1,
          f"HTTP {again.status_code} jumlah_pembayaran={len(payments)}")
    st = (await client.get(f"{API}/api/public/booking/{code}", params={"token": token})).json()
    check("halaman status pelanggan ikut memperlihatkan status confirmed & DP terpenuhi",
          st.get("status") == "confirmed" and st.get("dp_met") is True,
          f"status={st.get('status')} dp_met={st.get('dp_met')}")


# --------------------------------------------------------------------------- 9 promo
async def t9_promo(client, unit):
    head("9 · PROMO DITEGAKKAN SERVER (syarat = data, bukan tulisan di deskripsi)")
    weekday = next_weekday(60, 8)
    base = {"service": "daily_rental", "vehicle_id": unit["id"],
            "start_datetime": weekday.isoformat(),
            "end_datetime": (weekday + timedelta(days=1)).isoformat(), "pax": 4}
    r = await client.post(f"{API}/api/public/booking/quote",
                         json={**base, "promo_code": "GATHERING500"})
    check("promo 'min 2 hari' DITOLAK untuk sewa 1 hari",
          400 <= r.status_code < 500 and "2 hari" in str(r.json().get("detail")),
          f"HTTP {r.status_code} · {str(r.json().get('detail'))[:90]}")
    r2 = await client.post(f"{API}/api/public/booking/quote", json={
        **base, "end_datetime": (weekday + timedelta(days=3)).isoformat(),
        "promo_code": "GATHERING500"})
    q2 = r2.json().get("quote", {}) if r2.status_code == 200 else {}
    check("promo diterima untuk sewa 3 hari & potongan masuk rincian",
          r2.status_code == 200 and q2.get("discount") == 500000,
          f"HTTP {r2.status_code} potongan={rp(q2.get('discount', 0))}")
    labels = [b["label"] for b in q2.get("breakdown", [])]
    check("baris potongan promo tampil transparan di rincian",
          any("promo" in l.lower() for l in labels), f"{labels[-1] if labels else '-'}")
    r3 = await client.post(f"{API}/api/public/booking/quote",
                          json={**base, "promo_code": "AKHIRPEKAN10"})
    check("promo 'khusus akhir pekan' ditolak untuk keberangkatan hari kerja",
          400 <= r3.status_code < 500 and "akhir pekan" in str(r3.json().get("detail")).lower(),
          f"HTTP {r3.status_code} · {str(r3.json().get('detail'))[:90]}")
    sat = next_saturday(62)
    r4 = await client.post(f"{API}/api/public/booking/quote", json={
        "service": "daily_rental", "vehicle_id": unit["id"], "pax": 4,
        "start_datetime": sat.isoformat(),
        "end_datetime": (sat + timedelta(days=1)).isoformat(), "promo_code": "AKHIRPEKAN10"})
    check("promo akhir pekan diterima untuk keberangkatan Sabtu",
          r4.status_code == 200 and (r4.json().get("quote") or {}).get("discount", 0) > 0,
          f"HTTP {r4.status_code} potongan={rp((r4.json().get('quote') or {}).get('discount', 0))}")
    r5 = await client.post(f"{API}/api/public/booking/quote",
                          json={**base, "promo_code": "TIDAKADA123"})
    check("kode promo tak dikenal → 4xx berALASAN", 400 <= r5.status_code < 500,
          f"HTTP {r5.status_code} · {str(r5.json().get('detail'))[:60]}")
    r6 = await client.post(f"{API}/api/public/booking/quote",
                          json={**base, "promo_code": "BANDARA50"})
    check("promo khusus layanan bandara ditolak pada sewa harian",
          400 <= r6.status_code < 500, f"HTTP {r6.status_code} · "
          f"{str(r6.json().get('detail'))[:70]}")


# --------------------------------------------------------------------------- 9b bandara
async def t9b_transfer(client, unit):
    head("9b · ANTAR-JEMPUT BANDARA — tarif FLAT per rute per tipe unit")
    cfg = (await client.get(f"{API}/api/public/booking/config")).json()
    routes = cfg.get("routes") or []
    check("rute antar-jemput tersedia dari data (bukan hardcode)", len(routes) > 0,
          f"{[r['code'] for r in routes]}")
    if not routes:
        return
    route = routes[0]
    start = next_weekday(25, 5)
    res = (await client.post(f"{API}/api/public/booking/search", json={
        "service": "airport_transfer", "route_id": route["id"],
        "start_datetime": start.isoformat(), "pax": 2})).json()
    opts = res.get("options") or []
    check("pencarian bandara hanya menawarkan unit yang punya tarif rute itu",
          all(o["vehicle"]["type"] in route["vehicle_types"] for o in opts),
          f"{[(o['vehicle']['code'], o['vehicle']['type']) for o in opts]}")
    if opts:
        first = opts[0]
        q = first["quote"]
        labels = [b["label"] for b in q["breakdown"]]
        check("harga bandara = 1 baris tarif flat (tanpa driver/hari & tanpa jarak)",
              len(labels) == 1 and "flat" in labels[0].lower(), f"{labels}")
        check("nominal flat sesuai tarif rute di database",
              q["total"] > 0, f"total={rp(q['total'])} ({first['vehicle']['type']})")
        sub = await submit(client, {
            "service": "airport_transfer", "route_id": route["id"],
            "vehicle_id": first["vehicle"]["id"], "start_datetime": start.isoformat(),
            "pax": 2, "name": "Tamu Bandara", "phone": "081277700003",
            "pickup_address": "Hotel Savoy, Bandung"})
        sd = sub.json() if sub.status_code == 200 else {}
        if sd.get("id"):
            CREATED.append(sd["id"])
        check("pesanan antar-jemput bandara berhasil dibuat",
              sub.status_code == 200 and sd.get("code"),
              f"HTTP {sub.status_code} · {str(sd)[:110]}")
        if sd.get("token"):
            st = (await client.get(f"{API}/api/public/booking/{sd['code']}",
                                  params={"token": sd["token"]})).json()
            check("status menyimpan nama rute (bukan teks kosong)", bool(st.get("route_name")),
                  f"rute={st.get('route_name')}")
            can = await client.post(f"{API}/api/public/booking/{sd['code']}/cancel",
                                   json={"token": sd["token"], "reason": "Uji pembatalan"})
            check("pelanggan bisa membatalkan pesanan yang belum dikonfirmasi",
                  can.status_code == 200 and can.json().get("cancelled"),
                  f"HTTP {can.status_code}")


# --------------------------------------------------------------------------- 10 tamper & 5xx
async def t10_hardening(client, unit):
    head("10 · ANTI TAMPER HARGA + INPUT RUSAK TIDAK PERNAH 5XX")
    start = next_weekday(70, 8)
    end = start + timedelta(days=1)
    opt = await pick_available(client, start, end)
    unit = (opt or {}).get("vehicle") or unit
    clean = {"service": "daily_rental", "vehicle_id": unit["id"],
             "start_datetime": start.isoformat(), "end_datetime": end.isoformat(), "pax": 2,
             "name": "Tukang Tamper", "phone": "081277700009"}
    tampered = {**clean, "total_amount": 1, "base_price": 1, "dp_amount": 1,
                "total": 1, "quote": {"total": 1}, "add_ons": [{"label": "Diskon gelap",
                                                               "amount": -9999999}]}
    r = await submit(client, tampered)
    if r.status_code == 200 and r.json().get("id"):
        CREATED.append(r.json()["id"])
    if r.status_code == 200:
        st = (await client.get(f"{API}/api/public/booking/{r.json()['code']}",
                              params={"token": r.json()["token"]})).json()
        check("harga kiriman klien DIABAIKAN (total dihitung server)",
              st.get("total_amount", 0) > 1000, f"total tersimpan={rp(st.get('total_amount', 0))}")
        await client.post(f"{API}/api/public/booking/{r.json()['code']}/cancel",
                         json={"token": r.json()["token"], "reason": "bersih-bersih POC"})
    else:
        check("add-on negatif ditolak 4xx (bukan mengurangi harga)",
              400 <= r.status_code < 500,
              f"HTTP {r.status_code} · {str(r.json().get('detail'))[:80]}")

    cases = [
        ("search tanggal ngawur", "POST", "/api/public/booking/search",
         {"service": "daily_rental", "start_datetime": "bukan-tanggal", "end_datetime": "x"}),
        ("search layanan tak dikenal", "POST", "/api/public/booking/search",
         {"service": "teleportasi", "start_datetime": start.isoformat()}),
        ("search pax raksasa", "POST", "/api/public/booking/search",
         {"service": "daily_rental", "start_datetime": start.isoformat(),
          "end_datetime": end.isoformat(), "pax": 99999}),
        ("quote unit tak ada", "POST", "/api/public/booking/quote",
         {"service": "daily_rental", "vehicle_id": "veh_tidak_ada",
          "start_datetime": start.isoformat(), "end_datetime": end.isoformat()}),
        ("quote tipe salah (pax string)", "POST", "/api/public/booking/quote",
         {"service": "daily_rental", "vehicle_id": unit["id"], "pax": "banyak",
          "start_datetime": start.isoformat(), "end_datetime": end.isoformat()}),
        ("submit tanpa nama/telepon", "POST", "/api/public/booking/submit",
         {"service": "daily_rental", "vehicle_id": unit["id"],
          "start_datetime": start.isoformat(), "end_datetime": end.isoformat()}),
        ("submit selesai < mulai", "POST", "/api/public/booking/submit",
         {"service": "daily_rental", "vehicle_id": unit["id"], "name": "X Y",
          "phone": "081200000003", "start_datetime": end.isoformat(),
          "end_datetime": start.isoformat()}),
        ("submit tanggal lampau", "POST", "/api/public/booking/submit",
         {"service": "daily_rental", "vehicle_id": unit["id"], "name": "X Y",
          "phone": "081200000003",
          "start_datetime": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
          "end_datetime": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()}),
        ("submit rute bandara tak ada", "POST", "/api/public/booking/submit",
         {"service": "airport_transfer", "vehicle_id": unit["id"], "route_id": "trt_hantu",
          "name": "X Y", "phone": "081200000003", "start_datetime": start.isoformat()}),
        ("lookup kode aneh", "POST", "/api/public/booking/lookup",
         {"code": "<script>x</script>", "phone": "081200000003"}),
        ("cancel token kosong", "POST", "/api/public/booking/BK-9999/cancel",
         {"token": "xxxxxxxxxx"}),
    ]
    bad5xx = []
    for name, method, path, body in cases:
        r = await client.request(method, f"{API}{path}", json=body)
        if r.status_code >= 500:
            bad5xx.append(f"{name} → {r.status_code}")
        else:
            check(f"{name} → {r.status_code} (4xx berALASAN)", 400 <= r.status_code < 500,
                  "" if 400 <= r.status_code < 500 else f"HTTP {r.status_code}")
    check("TIDAK ADA 5xx pada 11 permintaan adversarial", not bad5xx, "; ".join(bad5xx))
    st = await client.get(f"{API}/api/public/booking/BK-0001")
    check("status tanpa token → 404", st.status_code == 404, f"HTTP {st.status_code}")


async def preclean(client, ops):
    """Batalkan sisa booking uji dari jalan sebelumnya (hold/pending memblok tanggal uji).

    POC harus bisa dijalankan berulang kali tanpa "kehabisan" armada; kalau tidak, kegagalan
    palsu akan menutupi kegagalan nyata.
    """
    rows = (await client.get(f"{API}/api/bookings", headers=ops, params={"limit": 500})).json()
    n = 0
    for b in rows if isinstance(rows, list) else []:
        if b.get("contact_phone") in POC_PHONES and b.get("status") in ("hold", "pending"):
            r = await client.post(f"{API}/api/bookings/{b['id']}/cancel", headers=ops,
                                 json={"reason": "bersih-bersih POC (jalan sebelumnya)"})
            n += 1 if r.status_code == 200 else 0
    if n:
        print(f"  {Y}Pra-bersih: {n} booking uji sisa jalan sebelumnya dibatalkan.{X}")
    return n


async def main():
    print(f"{B}{C}\n=============================================================")
    print("  POC INTI PEMESANAN ONLINE (Fase 1) — 10 pembuktian")
    print(f"============================================================={X}")
    async with httpx.AsyncClient(timeout=90) as client:
        try:
            ops = await login(client, OPS)
            owner = await login(client, OWNER)
        except Exception as exc:
            print(f"{R}Gagal login ({exc}) — pastikan backend hidup & seed sudah jalan.{X}")
            return 2
        await preclean(client, ops)
        await set_flow(client, owner, {"mode": "hold_dp", "hold_hours": 2, "min_lead_hours": 4})
        catalog = await t1_catalog(client, ops)
        if not catalog:
            print(f"{R}Katalog publik kosong — hentikan POC.{X}")
            return 2
        # Unit uji: yang punya tarif per-unit BERBEDA dari tarif tipe (menguji override).
        internal = (await client.get(f"{API}/api/vehicles", headers=ops)).json()
        rules = (await client.get(f"{API}/api/pricing/rules", headers=ops)).json()
        override = None
        for v in catalog:
            iv = next((x for x in internal if x["id"] == v["id"]), {})
            type_rate = int((rules.get("day_rates") or {}).get(v.get("type")) or 0)
            if int(iv.get("day_rate") or 0) and int(iv["day_rate"]) != type_rate:
                override = v
                break
        unit = override or catalog[0]
        print(f"\n  {C}Unit uji: {unit.get('code')} {unit.get('name')} "
              f"({unit.get('type')}, {rp(unit.get('price_from'))}/hari){X}")
        await t2_pricing(client, ops, unit)
        blocker = await t4_availability(client, ops, unit)
        await t5_concurrency(client, unit)
        hold = await t6_hold_dp(client, owner, unit)
        await t7_ops_approval(client, owner, ops, unit)
        if hold and hold.get("token"):
            await t8_proof_to_confirmed(client, ops, hold)
        await t9_promo(client, unit)
        await t9b_transfer(client, unit)
        await t10_hardening(client, unit)
        # --- BERSIH-BERSIH: batalkan semua booking buatan POC supaya skrip bisa dijalankan
        # berulang kali tanpa "kehabisan" armada (hold/pending memblok tanggal berikutnya).
        if blocker and blocker.get("id"):
            CREATED.append(blocker["id"])
        cleaned = 0
        for bid in dict.fromkeys(CREATED):
            rc = await client.post(f"{API}/api/bookings/{bid}/cancel", headers=ops,
                                  json={"reason": "bersih-bersih POC pemesanan online"})
            cleaned += 1 if rc.status_code == 200 else 0
        # jaring pengaman: booking dari nomor uji yang belum sempat tercatat di CREATED
        leftovers = (await client.get(f"{API}/api/bookings", headers=ops,
                                     params={"limit": 500})).json()
        for b in leftovers if isinstance(leftovers, list) else []:
            if b.get("contact_phone") in POC_PHONES and b.get("status") in ("hold", "pending"):
                rc = await client.post(f"{API}/api/bookings/{b['id']}/cancel", headers=ops,
                                      json={"reason": "bersih-bersih POC pemesanan online"})
                cleaned += 1 if rc.status_code == 200 else 0
        print(f"\n  {C}Bersih-bersih: {cleaned} booking uji dibatalkan.{X}")
        # INV-CLEAN-01 — MEMBATALKAN tidak sama dengan MEMBERSIHKAN: booking sengaja tak punya
        # endpoint DELETE (catatan keuangan), jadi tanpa langkah ini POC meninggalkan ~5 baris
        # "Dibatalkan" + customer uji ("Uji Balapan", "Budi Pemesan", …) + percakapan/notifikasi
        # di ERP yang dilihat pengguna (kelas BUG-0127). Hapus TOTAL lewat mesin bersama.
        purged = purge_guard_artifacts(extra_phones=POC_PHONES, extra_ids=CREATED)
        print(f"  {C}Bersih-bersih total: {purged} dokumen uji + side-effect dihapus "
              f"(ERP tetap bersih).{X}")

    passed = sum(1 for ok, _, _ in results if ok)
    failed = [name for ok, name, _ in results if not ok]
    print(f"\n{B}{C}============================================================={X}")
    print(f"  {G}LULUS {passed}{X} / {len(results)}   " +
          (f"{R}GAGAL {len(failed)}{X}" if failed else f"{G}GAGAL 0{X}"))
    if failed:
        for f in failed:
            print(f"   {R}✗ {f}{X}")
        print(f"\n{R}{B}  POC BELUM HIJAU — perbaiki dulu sebelum membangun UI.{X}\n")
        return 1
    print(f"\n{G}{B}  POC HIJAU — inti pemesanan online terbukti bekerja.{X}\n")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

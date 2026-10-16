"""Backend tests for document layouts, numbering, invoice config, invoices, receipts, RBAC.
Target features: doc-layouts / doc-assets / numbering / invoice-config / invoices / receipts.
"""
import io
import os
import struct
import zlib
from datetime import datetime, timedelta, timezone

import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    for p in ("/app/frontend/.env",):
        try:
            with open(p) as f:
                for line in f:
                    if line.strip().startswith("REACT_APP_BACKEND_URL="):
                        return line.strip().split("=", 1)[1].strip().rstrip("/")
        except FileNotFoundError:
            pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

CREDS = {
    "owner": ("owner@demo.local", "demo12345"),
    "ops": ("ops@demo.local", "demo12345"),
    "driver": ("driver@demo.local", "demo12345"),
}


def _login(role):
    email, pw = CREDS[role]
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, f"login {role}: {r.status_code} {r.text[:200]}"
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def owner_token():
    return _login("owner")


@pytest.fixture(scope="module")
def ops_token():
    return _login("ops")


@pytest.fixture(scope="module")
def driver_token():
    return _login("driver")


@pytest.fixture(scope="module")
def owner_h(owner_token):
    return {"Authorization": f"Bearer {owner_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def ops_h(ops_token):
    return {"Authorization": f"Bearer {ops_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def driver_h(driver_token):
    return {"Authorization": f"Bearer {driver_token}", "Content-Type": "application/json"}


# ------------------------------------------------------------------ doc-layouts
class TestDocLayouts:
    def test_list_layouts_has_5_targets(self, owner_h):
        r = requests.get(f"{API}/doc-layouts", headers=owner_h, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        codes = {d.get("code") for d in body.get("data", [])}
        for k in ("__default__", "INVOICE_DP", "INVOICE_SETTLEMENT", "INVOICE", "KWITANSI"):
            assert k in codes, f"missing target {k}; got {codes}"
        assert "sections_catalog" in body and isinstance(body["sections_catalog"], list)
        assert "money_rows_catalog" in body and isinstance(body["money_rows_catalog"], dict)

    def test_get_invoice_dp_layout_shape(self, owner_h):
        r = requests.get(f"{API}/doc-layouts/INVOICE_DP", headers=owner_h, timeout=30)
        assert r.status_code == 200
        data = r.json()["data"]
        for key in ("brand", "table", "sections", "money_rows", "signatures", "options"):
            assert key in data, f"missing {key} in layout"

    def test_put_and_get_reflect_and_reset(self, owner_h):
        payload = {"brand": {"accent_color": "#C0271E", "watermark_text": "CONTOH"},
                   "options": {"place": "Bandung"}}
        r = requests.put(f"{API}/doc-layouts/INVOICE_DP", headers=owner_h, json=payload, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["data"].get("overridden") is True
        g = requests.get(f"{API}/doc-layouts/INVOICE_DP", headers=owner_h, timeout=30).json()["data"]
        assert (g.get("brand") or {}).get("accent_color") == "#C0271E"
        assert (g.get("brand") or {}).get("watermark_text") == "CONTOH"
        assert (g.get("options") or {}).get("place") == "Bandung"
        # reset
        d = requests.delete(f"{API}/doc-layouts/INVOICE_DP", headers=owner_h, timeout=30)
        assert d.status_code == 200
        assert d.json()["data"].get("overridden") in (False, None)

    def test_invalid_color_rejected(self, owner_h):
        r = requests.put(f"{API}/doc-layouts/INVOICE_DP", headers=owner_h,
                         json={"brand": {"accent_color": "red"}}, timeout=30)
        assert r.status_code in (400, 422), r.text


class TestDocScript:
    def test_get_script_and_placeholders(self, owner_h):
        r = requests.get(f"{API}/doc-layouts/KWITANSI/script", headers=owner_h, timeout=30)
        assert r.status_code == 200
        data = r.json()["data"]
        assert "content" in data
        assert "placeholders" in data and isinstance(data["placeholders"], list)

    def test_save_valid_script_and_reset(self, owner_h):
        r0 = requests.get(f"{API}/doc-layouts/KWITANSI/script", headers=owner_h, timeout=30).json()["data"]
        # pick a known placeholder from the catalog
        phs = [p.get("token") if isinstance(p, dict) else p for p in r0.get("placeholders", [])]
        assert phs, "no placeholders returned"
        ph = phs[0]
        content = f"Halo {ph} — kwitansi terlampir."
        v0 = int(r0.get("version") or 0)
        r = requests.put(f"{API}/doc-layouts/KWITANSI/script", headers=owner_h,
                         json={"content": content}, timeout=30)
        assert r.status_code == 200, r.text
        out = r.json()["data"]
        assert out.get("customized") is True
        assert int(out.get("version") or 0) > v0
        # reset
        d = requests.delete(f"{API}/doc-layouts/KWITANSI/script", headers=owner_h, timeout=30)
        assert d.status_code == 200
        assert d.json()["data"].get("customized") in (False, None)

    def test_unknown_placeholder_rejected(self, owner_h):
        # Backend uses {{...}} double-brace placeholders; single-brace tokens are ignored.
        r = requests.put(f"{API}/doc-layouts/KWITANSI/script", headers=owner_h,
                         json={"content": "Halo {{foo_unknown_token}}"}, timeout=30)
        assert r.status_code == 400, r.text


class TestPreviewPdf:
    def _assert_pdf(self, r):
        assert r.status_code == 200, r.text[:200]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert len(r.content) > 1024, f"PDF too small: {len(r.content)}"
        assert r.content[:4] == b"%PDF"

    def test_preview_invoice_dp(self, owner_h):
        body = {"brand": {"accent_color": "#0055AA"},
                "script": "Halo {customer_name}\n{tabel_rincian}\n{tabel_biaya}"}
        r = requests.post(f"{API}/doc-layouts/INVOICE_DP/preview", headers=owner_h, json=body, timeout=60)
        self._assert_pdf(r)

    def test_preview_kwitansi(self, owner_h):
        r = requests.post(f"{API}/doc-layouts/KWITANSI/preview", headers=owner_h, json={}, timeout=60)
        self._assert_pdf(r)

    def test_preview_default(self, owner_h):
        r = requests.post(f"{API}/doc-layouts/__default__/preview", headers=owner_h, json={}, timeout=60)
        self._assert_pdf(r)


# ------------------------------------------------------------------ doc-assets
def _make_png_bytes():
    # 1x1 red PNG constructed by hand.
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


class TestDocAssets:
    def test_upload_png_and_use_in_preview(self, owner_token):
        png = _make_png_bytes()
        files = {"file": ("logo.png", png, "image/png")}
        r = requests.post(f"{API}/doc-assets", files=files,
                         headers={"Authorization": f"Bearer {owner_token}"}, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "id" in j and "url" in j
        fid = j["id"]
        # Serve check
        url = f"{BASE_URL}{j['url']}"
        s = requests.get(url, timeout=30)
        assert s.status_code == 200
        assert s.headers.get("content-type", "").startswith("image/")
        # Put layout with logo, then preview
        h = {"Authorization": f"Bearer {owner_token}", "Content-Type": "application/json"}
        pu = requests.put(f"{API}/doc-layouts/INVOICE_DP", headers=h,
                          json={"brand": {"logo_file_id": fid}}, timeout=30)
        assert pu.status_code == 200
        pr = requests.post(f"{API}/doc-layouts/INVOICE_DP/preview", headers=h, json={}, timeout=60)
        assert pr.status_code == 200
        assert pr.content[:4] == b"%PDF"
        # cleanup layout override
        requests.delete(f"{API}/doc-layouts/INVOICE_DP", headers=h, timeout=30)

    def test_non_image_rejected(self, owner_token):
        files = {"file": ("bad.txt", b"hello", "text/plain")}
        r = requests.post(f"{API}/doc-assets", files=files,
                         headers={"Authorization": f"Bearer {owner_token}"}, timeout=30)
        assert r.status_code == 400, r.text


# ------------------------------------------------------------------ numbering
class TestNumbering:
    def test_list_rules(self, owner_h):
        r = requests.get(f"{API}/numbering", headers=owner_h, timeout=30)
        assert r.status_code == 200
        data = r.json()["data"]
        keys = {d.get("key") for d in data}
        for k in ("invoice", "invoice_dp", "invoice_settlement", "receipt"):
            assert k in keys, f"missing rule {k}"
        for d in data:
            assert "preview" in d
            assert "next_seq" in d

    def test_preview_rule(self, owner_h):
        body = {"pattern": "{SEQ}/{PREFIX}/{BOOKING_CODE}/{MM_ROMAN}/{YYYY}", "reset": "monthly",
                "sample": {"booking_code": "BK-TEST"}}
        r = requests.post(f"{API}/numbering/invoice_dp/preview", headers=owner_h, json=body, timeout=30)
        assert r.status_code == 200, r.text
        prev = r.json()["data"]["preview"]
        assert prev and "/" in prev

    def test_save_rule_and_reset(self, owner_h):
        body = {"pattern": "TEST-{YYYY}-{SEQ}", "prefix": "INVDP", "width": 4, "reset": "yearly"}
        r = requests.put(f"{API}/numbering/invoice_dp", headers=owner_h, json=body, timeout=30)
        assert r.status_code == 200, r.text
        out = r.json()["data"]
        assert out.get("overridden") is True
        assert out.get("pattern") == "TEST-{YYYY}-{SEQ}"
        # reset
        d = requests.delete(f"{API}/numbering/invoice_dp", headers=owner_h, timeout=30)
        assert d.status_code == 200

    def test_missing_seq_rejected(self, owner_h):
        r = requests.put(f"{API}/numbering/invoice_dp", headers=owner_h,
                         json={"pattern": "NO-SEQ-{YYYY}"}, timeout=30)
        assert r.status_code == 400, r.text

    def test_unknown_token_rejected(self, owner_h):
        r = requests.put(f"{API}/numbering/invoice_dp", headers=owner_h,
                         json={"pattern": "{SEQ}/{FOO}"}, timeout=30)
        assert r.status_code == 400, r.text


# ------------------------------------------------------------------ invoice-config
class TestInvoiceConfig:
    def test_get_defaults(self, owner_h):
        r = requests.get(f"{API}/invoice-config", headers=owner_h, timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert "dp_percent_default" in j

    def test_put_persists_and_bank_ids(self, owner_h):
        payload = {"dp_percent_default": 40, "dp_due_days": 2,
                   "bank_accounts": [{"bank": "BCA", "account_no": "1234567890", "account_name": "PT Test"}],
                   "payment_terms": "Tes"}
        r = requests.put(f"{API}/invoice-config", headers=owner_h, json=payload, timeout=30)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out.get("dp_percent_default") == 40
        assert out.get("dp_due_days") == 2
        assert out.get("payment_terms") == "Tes"
        banks = out.get("bank_accounts") or []
        assert banks and banks[0].get("id"), "bank account must be assigned id"
        # persist re-read
        g = requests.get(f"{API}/invoice-config", headers=owner_h, timeout=30).json()
        assert (g.get("bank_accounts") or [{}])[0].get("account_no") == "1234567890"


# ------------------------------------------------------------------ invoices e2e
@pytest.fixture(scope="module")
def booking_id(owner_h):
    """Create a fresh booking (iterate vehicles + dates to avoid clash) for invoice tests."""
    cust = requests.get(f"{API}/customers?limit=5", headers=owner_h, timeout=30).json()
    veh = requests.get(f"{API}/vehicles?limit=30", headers=owner_h, timeout=30).json()
    cust = cust if isinstance(cust, list) else cust.get("data") or []
    veh = veh if isinstance(veh, list) else veh.get("data") or []
    if not cust or not veh:
        pytest.skip("no customers/vehicles seed data")
    base = datetime.now(timezone.utc) + timedelta(days=60)
    last_err = None
    for offset in range(0, 200, 3):
        for v in veh:
            start = (base + timedelta(days=offset)).replace(microsecond=0)
            end = start + timedelta(hours=6)
            payload = {
                "customer_id": cust[0]["id"], "vehicle_id": v["id"],
                "start_datetime": start.isoformat().replace("+00:00", "Z"),
                "end_datetime": end.isoformat().replace("+00:00", "Z"),
                "base_price": 1000000, "notes": "TEST_invoice_doc",
            }
            r = requests.post(f"{API}/bookings", headers=owner_h, json=payload, timeout=30)
            if r.status_code in (200, 201):
                b = r.json()
                return b.get("id") or (b.get("data") or {}).get("id")
            last_err = r.text
    pytest.fail(f"could not create fresh booking: {last_err}")


class TestInvoicesE2E:
    def test_quote_dp(self, owner_h, booking_id):
        r = requests.get(f"{API}/invoices/quote", headers=owner_h,
                         params={"booking_id": booking_id, "kind": "dp"}, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        for k in ("subtotal", "dp_percent", "dp_amount", "amount", "due_at", "items"):
            assert k in j, f"missing {k}"

    def test_create_dp_invoice_pdf_and_export(self, owner_h, booking_id):
        r = requests.post(f"{API}/invoices", headers=owner_h,
                          json={"booking_id": booking_id, "kind": "dp", "dp_percent": 30}, timeout=30)
        assert r.status_code == 200, r.text
        inv = r.json()
        assert inv.get("kind") == "dp"
        assert inv.get("status") == "draft"
        assert inv.get("number")
        inv_id = inv["id"]
        # PDF inline
        p = requests.get(f"{API}/invoices/{inv_id}/pdf", headers=owner_h, timeout=60)
        assert p.status_code == 200 and p.content[:4] == b"%PDF"
        # Export attachment PDF
        e1 = requests.get(f"{API}/invoices/{inv_id}/export?format=pdf", headers=owner_h, timeout=60)
        assert e1.status_code == 200
        assert "attachment" in (e1.headers.get("content-disposition") or "")
        # Export XLSX
        e2 = requests.get(f"{API}/invoices/{inv_id}/export?format=excel", headers=owner_h, timeout=60)
        assert e2.status_code == 200
        assert e2.content[:2] == b"PK"  # xlsx = zip
        # keep for later tests
        pytest.dp_invoice_id = inv_id
        pytest.dp_invoice_amount = inv.get("amount")

    def test_settlement_invoice(self, owner_h, booking_id):
        r = requests.post(f"{API}/invoices", headers=owner_h,
                          json={"booking_id": booking_id, "kind": "settlement"}, timeout=30)
        assert r.status_code == 200, r.text
        inv = r.json()
        assert inv.get("kind") == "settlement"
        assert inv.get("amount") > 0
        pytest.settle_invoice_id = inv["id"]

    def test_create_invoice_booking_not_found(self, owner_h):
        r = requests.post(f"{API}/invoices", headers=owner_h,
                          json={"booking_id": "nonexistent-xyz", "kind": "dp"}, timeout=30)
        assert r.status_code == 400

    def test_patch_invoice_status(self, owner_h):
        inv_id = getattr(pytest, "settle_invoice_id", None)
        if not inv_id:
            pytest.skip("no settle invoice")
        r = requests.patch(f"{API}/invoices/{inv_id}", headers=owner_h,
                           json={"status": "void"}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "void"
        # invalid
        r2 = requests.patch(f"{API}/invoices/{inv_id}", headers=owner_h,
                            json={"status": "banana"}, timeout=30)
        assert r2.status_code == 400

    def test_payment_syncs_invoice_status(self, owner_h, booking_id):
        amount = getattr(pytest, "dp_invoice_amount", None)
        if not amount:
            pytest.skip("dp invoice amount unavailable")
        r = requests.post(f"{API}/payments", headers=owner_h,
                          json={"booking_id": booking_id, "amount": amount,
                                "type": "dp", "method": "transfer"}, timeout=30)
        assert r.status_code == 200, r.text
        pay = r.json()
        pytest.payment_id = pay["id"]
        invs = requests.get(f"{API}/invoices", headers=owner_h,
                            params={"booking_id": booking_id}, timeout=30).json()
        dp = [i for i in invs if i.get("kind") == "dp"][0]
        assert dp.get("status") == "paid", f"expected paid, got {dp.get('status')}"

    def test_dp_again_no_remaining_400(self, owner_h, booking_id):
        # DP already fully paid → new DP invoice should 400.
        r = requests.post(f"{API}/invoices", headers=owner_h,
                          json={"booking_id": booking_id, "kind": "dp", "dp_percent": 30}, timeout=30)
        assert r.status_code == 400
        assert "sisa" in (r.text.lower())

    # Receipts kept in the same class so they share the same worker (LoadScope) and can reuse
    # pytest.payment_id set by test_payment_syncs_invoice_status above.
    def test_list_receipts(self, owner_h):
        r = requests.get(f"{API}/receipts", headers=owner_h, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_issue_receipt_idempotent_and_pdf(self, owner_h):
        pay_id = getattr(pytest, "payment_id", None)
        if not pay_id:
            pytest.skip("no payment id")
        r1 = requests.post(f"{API}/payments/{pay_id}/receipt", headers=owner_h, timeout=30)
        assert r1.status_code == 200, r1.text
        no1 = r1.json().get("receipt_no")
        assert no1
        r2 = requests.post(f"{API}/payments/{pay_id}/receipt", headers=owner_h, timeout=30)
        assert r2.status_code == 200
        assert r2.json().get("receipt_no") == no1, "receipt issuance must be idempotent"
        p = requests.get(f"{API}/payments/{pay_id}/receipt/pdf", headers=owner_h, timeout=60)
        assert p.status_code == 200 and p.content[:4] == b"%PDF"
        assert "inline" in (p.headers.get("content-disposition") or "")
        p2 = requests.get(f"{API}/payments/{pay_id}/receipt/pdf?download=true", headers=owner_h, timeout=60)
        assert p2.status_code == 200
        assert "attachment" in (p2.headers.get("content-disposition") or "")


# ------------------------------------------------------------------ receipts (extra)
class TestReceipts:
    def test_list_receipts_ok(self, owner_h):
        r = requests.get(f"{API}/receipts", headers=owner_h, timeout=30)
        assert r.status_code == 200


# ------------------------------------------------------------------ RBAC
class TestRBAC:
    def test_ops_can_read_but_not_write(self, ops_h):
        r = requests.get(f"{API}/doc-layouts", headers=ops_h, timeout=30)
        assert r.status_code == 200
        r2 = requests.get(f"{API}/numbering", headers=ops_h, timeout=30)
        assert r2.status_code == 200
        # writes forbidden
        w1 = requests.put(f"{API}/doc-layouts/INVOICE_DP", headers=ops_h,
                          json={"brand": {"accent_color": "#111111"}}, timeout=30)
        assert w1.status_code == 403, w1.text
        w2 = requests.put(f"{API}/numbering/invoice_dp", headers=ops_h,
                          json={"pattern": "{SEQ}-X"}, timeout=30)
        assert w2.status_code == 403
        w3 = requests.put(f"{API}/invoice-config", headers=ops_h,
                          json={"dp_percent_default": 25}, timeout=30)
        assert w3.status_code == 403

    def test_driver_no_invoices(self, driver_h):
        r = requests.get(f"{API}/invoices", headers=driver_h, timeout=30)
        assert r.status_code == 403

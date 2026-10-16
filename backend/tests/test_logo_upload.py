"""Tests for public logo rendering flow:
   - CMS upload -> /api/uploads/cms -> PUT /api/site/settings -> GET /api/public/company
   - Fallback: brand doc-asset via document_layouts '__default__'
"""
import os
import io
import requests
import pytest
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()
BASE_URL = BASE_URL.rstrip("/")
OWNER_EMAIL = "owner@rahazatrans.test"
OWNER_PASS = "Owner#12345"


def _png_bytes(color=(220, 20, 30)):
    img = Image.new("RGB", (200, 200), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(scope="session")
def token():
    # Try common auth endpoints
    for path, payload in [
        ("/api/auth/login", {"email": OWNER_EMAIL, "password": OWNER_PASS}),
        ("/api/auth/login", {"username": OWNER_EMAIL, "password": OWNER_PASS}),
    ]:
        r = requests.post(f"{BASE_URL}{path}", json=payload, timeout=30)
        if r.status_code == 200:
            data = r.json()
            tok = data.get("access_token") or data.get("token") or (data.get("data") or {}).get("access_token")
            if tok:
                return tok
    pytest.skip(f"Cannot login: {r.status_code} {r.text[:200]}")


@pytest.fixture(scope="session")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_public_company_endpoint_live():
    r = requests.get(f"{BASE_URL}/api/public/company", timeout=15)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), dict)


def test_cms_upload_and_site_settings_save(auth_headers):
    # Upload image via CMS endpoint
    files = {"image": ("testlogo.png", _png_bytes(), "image/png")}
    r = requests.post(f"{BASE_URL}/api/uploads/cms", files=files, headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "url" in data, data
    url = data["url"]
    assert url.startswith("/api/") or url.startswith("http"), url

    # Verify image is served
    img_url = url if url.startswith("http") else f"{BASE_URL}{url}"
    g = requests.get(img_url, timeout=15)
    assert g.status_code == 200, f"logo not served at {img_url}: {g.status_code}"
    assert g.headers.get("content-type", "").startswith("image/"), g.headers

    # Load current site settings
    r = requests.get(f"{BASE_URL}/api/site/settings", headers=auth_headers, timeout=15)
    assert r.status_code == 200, r.text
    current = r.json() or {}

    # PUT logo_url
    current["logo_url"] = url
    r = requests.put(f"{BASE_URL}/api/site/settings", json=current, headers=auth_headers, timeout=15)
    assert r.status_code == 200, r.text

    # Verify /api/public/company returns logo_url
    r = requests.get(f"{BASE_URL}/api/public/company", timeout=15)
    assert r.status_code == 200
    pub = r.json()
    assert pub.get("logo_url") == url, f"expected {url}, got {pub.get('logo_url')}"


def test_clear_logo_falls_back(auth_headers):
    # Clear logo_url
    r = requests.get(f"{BASE_URL}/api/site/settings", headers=auth_headers, timeout=15)
    current = r.json() or {}
    current["logo_url"] = ""
    r = requests.put(f"{BASE_URL}/api/site/settings", json=current, headers=auth_headers, timeout=15)
    assert r.status_code == 200

    r = requests.get(f"{BASE_URL}/api/public/company", timeout=15)
    assert r.status_code == 200
    pub = r.json()
    # Should be empty or absent (no brand asset yet)
    assert not (pub.get("logo_url") or "").strip(), f"expected empty after clear, got {pub.get('logo_url')}"


def test_fallback_from_doc_asset_brand(auth_headers):
    # Upload doc-asset
    files = {"file": ("brandlogo.png", _png_bytes((0, 100, 200)), "image/png")}
    r = requests.post(f"{BASE_URL}/api/doc-assets", files=files, headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    asset = r.json()
    assert "id" in asset and "url" in asset
    fid = asset["id"]

    # Get current __default__ layout
    r = requests.get(f"{BASE_URL}/api/doc-layouts/__default__", headers=auth_headers, timeout=15)
    assert r.status_code == 200, r.text
    layout_resp = r.json().get("data") or {}
    # Save with brand.logo_file_id
    body = {"brand": {"logo_file_id": fid}}
    r = requests.put(f"{BASE_URL}/api/doc-layouts/__default__", json=body, headers=auth_headers, timeout=15)
    assert r.status_code == 200, r.text

    # Ensure logo_url empty in settings
    r = requests.get(f"{BASE_URL}/api/site/settings", headers=auth_headers, timeout=15)
    current = r.json() or {}
    current["logo_url"] = ""
    requests.put(f"{BASE_URL}/api/site/settings", json=current, headers=auth_headers, timeout=15)

    # public/company should now fall back to asset URL
    r = requests.get(f"{BASE_URL}/api/public/company", timeout=15)
    pub = r.json()
    assert (pub.get("logo_url") or "").startswith("/api/uploads/docs/"), f"fallback failed, got: {pub}"

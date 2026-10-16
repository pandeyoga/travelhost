"""Backend tests: Page Builder (site_pages) + Site Settings + RBAC."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://trip-route-buttons.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(email, pwd="demo12345"):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def owner_headers():
    return {"Authorization": f"Bearer {_login('owner@demo.local')}"}


@pytest.fixture(scope="module")
def driver_headers():
    return {"Authorization": f"Bearer {_login('driver@demo.local')}"}


# ---------- Public endpoint ----------
class TestPublicPages:
    def test_public_home_ok(self):
        r = requests.get(f"{API}/public/pages/home", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["slug"] == "home"
        assert isinstance(data["sections"], list)
        # only enabled sections
        for s in data["sections"]:
            assert s.get("enabled") is True

    def test_public_about_ok(self):
        r = requests.get(f"{API}/public/pages/about", timeout=15)
        assert r.status_code == 200

    def test_public_contact_ok(self):
        r = requests.get(f"{API}/public/pages/contact", timeout=15)
        assert r.status_code == 200

    def test_public_unknown_404(self):
        r = requests.get(f"{API}/public/pages/tidak-ada", timeout=15)
        assert r.status_code == 404


# ---------- Auth guards ----------
class TestAuthGuards:
    def test_list_pages_requires_auth(self):
        r = requests.get(f"{API}/site/pages", timeout=15)
        assert r.status_code in (401, 403)

    def test_get_page_requires_auth(self):
        r = requests.get(f"{API}/site/pages/home", timeout=15)
        assert r.status_code in (401, 403)

    def test_put_page_requires_auth(self):
        r = requests.put(f"{API}/site/pages/home", json={"sections": []}, timeout=15)
        assert r.status_code in (401, 403)

    def test_get_settings_requires_auth(self):
        r = requests.get(f"{API}/site/settings", timeout=15)
        assert r.status_code in (401, 403)

    def test_put_settings_requires_auth(self):
        r = requests.put(f"{API}/site/settings", json={"tagline": "x"}, timeout=15)
        assert r.status_code in (401, 403)

    def test_driver_forbidden(self, driver_headers):
        r = requests.get(f"{API}/site/pages", headers=driver_headers, timeout=15)
        assert r.status_code in (401, 403)


# ---------- Owner CRUD ----------
class TestPageBuilder:
    def test_list_pages(self, owner_headers):
        r = requests.get(f"{API}/site/pages", headers=owner_headers, timeout=15)
        assert r.status_code == 200
        pages = r.json()
        slugs = {p["slug"] for p in pages}
        assert {"home", "about", "contact"}.issubset(slugs)

    def test_get_home_page(self, owner_headers):
        r = requests.get(f"{API}/site/pages/home", headers=owner_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["slug"] == "home"
        assert isinstance(data["sections"], list) and len(data["sections"]) > 0
        assert "allowed_types" in data

    def test_put_unknown_slug_404(self, owner_headers):
        r = requests.put(f"{API}/site/pages/xxx", headers=owner_headers,
                         json={"sections": []}, timeout=15)
        assert r.status_code == 404

    def test_put_invalid_type_400(self, owner_headers):
        r = requests.put(f"{API}/site/pages/home", headers=owner_headers,
                         json={"sections": [{"type": "not_a_type", "enabled": True, "data": {}}]},
                         timeout=15)
        assert r.status_code == 400
        assert "tidak dikenal" in r.text.lower() or "tidak dikenal" in r.json().get("detail", "").lower()

    def test_put_all_disabled_400(self, owner_headers):
        # fetch existing sections then disable all
        r = requests.get(f"{API}/site/pages/home", headers=owner_headers, timeout=15)
        assert r.status_code == 200
        sections = [{"id": s["id"], "type": s["type"], "enabled": False, "data": s.get("data", {})}
                    for s in r.json()["sections"]]
        r2 = requests.put(f"{API}/site/pages/home", headers=owner_headers,
                          json={"sections": sections}, timeout=15)
        assert r2.status_code == 400
        assert "minimal satu section" in r2.text.lower()

    def test_put_home_roundtrip_and_public_reflects(self, owner_headers):
        # Get current
        r = requests.get(f"{API}/site/pages/home", headers=owner_headers, timeout=15)
        original = r.json()["sections"]
        # Build payload: override hero title, hide the last section
        modified = []
        for i, s in enumerate(original):
            new_s = {"id": s["id"], "type": s["type"],
                     "enabled": s["enabled"], "data": dict(s.get("data") or {})}
            if s["type"] == "hero":
                new_s["data"]["title"] = "TEST_PB_TITLE_XYZ"
            if i == len(original) - 1:
                new_s["enabled"] = False
                hidden_id = s["id"]
            modified.append(new_s)
        try:
            r2 = requests.put(f"{API}/site/pages/home", headers=owner_headers,
                              json={"sections": modified}, timeout=15)
            assert r2.status_code == 200, r2.text
            # Verify GET persisted
            r3 = requests.get(f"{API}/site/pages/home", headers=owner_headers, timeout=15)
            got = r3.json()["sections"]
            hero = next((x for x in got if x["type"] == "hero"), None)
            assert hero and hero["data"].get("title") == "TEST_PB_TITLE_XYZ"
            assert any(x["id"] == hidden_id and x["enabled"] is False for x in got)
            # Verify public omits disabled
            r4 = requests.get(f"{API}/public/pages/home", timeout=15)
            pub_ids = [x["id"] for x in r4.json()["sections"]]
            assert hidden_id not in pub_ids
            pub_hero = next((x for x in r4.json()["sections"] if x["type"] == "hero"), None)
            assert pub_hero and pub_hero["data"].get("title") == "TEST_PB_TITLE_XYZ"
        finally:
            # Restore
            restore = [{"id": s["id"], "type": s["type"], "enabled": True, "data": s.get("data", {})}
                       for s in original]
            requests.put(f"{API}/site/pages/home", headers=owner_headers,
                         json={"sections": restore}, timeout=15)


# ---------- Site settings ----------
class TestSiteSettings:
    def test_get_and_put_settings(self, owner_headers):
        r = requests.get(f"{API}/site/settings", headers=owner_headers, timeout=15)
        assert r.status_code == 200
        original = r.json()
        orig_tagline = original.get("tagline", "")
        try:
            new_tag = "TEST_TAGLINE_PB_E2E"
            r2 = requests.put(f"{API}/site/settings", headers=owner_headers,
                              json={"tagline": new_tag}, timeout=15)
            assert r2.status_code == 200
            assert r2.json().get("tagline") == new_tag
            r3 = requests.get(f"{API}/site/settings", headers=owner_headers, timeout=15)
            assert r3.json().get("tagline") == new_tag
        finally:
            requests.put(f"{API}/site/settings", headers=owner_headers,
                         json={"tagline": orig_tagline}, timeout=15)

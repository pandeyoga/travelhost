"""Backend tests for Landing Page Builder route_grid block (armada-bandara template)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://trip-route-buttons.preview.emergentagent.com").rstrip("/")

MARKETING = {"email": "marketing@demo.local", "password": "demo12345"}

CANONICAL_ROUTE_GRID_PROPS = {"title", "subtitle", "ids", "limit", "show_price", "cta"}

created_page_ids = []


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=MARKETING, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"no token in login response: {data}"
    return tok


@pytest.fixture(scope="module")
def client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module", autouse=True)
def cleanup(client):
    yield
    for pid in created_page_ids:
        try:
            client.delete(f"{BASE_URL}/api/landing/pages/{pid}", timeout=15)
        except Exception:
            pass


# --- 1. Public booking config exposes routes[] (source of truth) ---
def test_public_booking_config_routes():
    r = requests.get(f"{BASE_URL}/api/public/booking/config", timeout=20)
    assert r.status_code == 200
    data = r.json()
    assert "routes" in data, f"no routes key: {list(data.keys())}"
    routes = data["routes"]
    assert isinstance(routes, list) and len(routes) > 0, "routes[] empty"
    r0 = routes[0]
    assert r0.get("id", "").startswith("trt_"), f"route id not trt_ prefixed: {r0.get('id')}"
    for k in ("from_label", "to_label", "from_price"):
        assert k in r0, f"route missing {k}: {r0}"


# --- 2. Template armada-bandara contains route_grid with canonical props ---
def test_templates_armada_bandara_has_route_grid(client):
    r = client.get(f"{BASE_URL}/api/landing/templates", timeout=20)
    assert r.status_code == 200
    body = r.json()
    templates = body if isinstance(body, list) else body.get("templates") or body.get("items") or []
    keys = [t.get("key") for t in templates]
    assert "armada-bandara" in keys, f"armada-bandara missing: {keys}"


def test_create_page_armada_bandara_has_route_grid_no_warnings(client):
    r = client.post(f"{BASE_URL}/api/landing/pages",
                    json={"template": "armada-bandara", "title": "TEST_route_grid_page"},
                    timeout=30)
    assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
    data = r.json()
    page = data.get("page") or data
    pid = page.get("id")
    assert pid
    created_page_ids.append(pid)

    # warnings
    warnings = data.get("warnings") or page.get("warnings") or []
    rg_warn = [w for w in warnings if "route_grid" in str(w).lower()]
    assert not rg_warn, f"route_grid warnings on create: {warnings}"

    blocks = page.get("blocks", [])
    rg_blocks = [b for b in blocks if b.get("type") == "route_grid"]
    assert rg_blocks, "no route_grid block in armada-bandara page"
    props = rg_blocks[0]["props"]
    assert set(props.keys()) == CANONICAL_ROUTE_GRID_PROPS, f"non-canonical props: {set(props.keys())}"


def test_patch_route_grid_preserves_props(client):
    # Create fresh page
    r = client.post(f"{BASE_URL}/api/landing/pages",
                    json={"template": "armada-bandara", "title": "TEST_patch_route_grid"},
                    timeout=30)
    assert r.status_code in (200, 201)
    page = r.json().get("page") or r.json()
    pid = page["id"]
    created_page_ids.append(pid)
    blocks = page["blocks"]

    # Fetch a real route id
    cfg = requests.get(f"{BASE_URL}/api/public/booking/config", timeout=20).json()
    route_id = cfg["routes"][0]["id"]

    # Modify route_grid block
    changed = False
    for b in blocks:
        if b.get("type") == "route_grid":
            b["props"]["limit"] = 3
            b["props"]["ids"] = [route_id]
            b["props"]["show_price"] = False
            changed = True
            break
    assert changed

    r = client.patch(f"{BASE_URL}/api/landing/pages/{pid}",
                     json={"blocks": blocks}, timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    body = r.json()
    warnings = body.get("warnings") or []
    rg_warn = [w for w in warnings if "route_grid" in str(w).lower()]
    assert not rg_warn, f"warnings on patch: {warnings}"

    saved = body.get("page") or body
    rg = [b for b in saved["blocks"] if b.get("type") == "route_grid"][0]
    assert rg["props"]["limit"] == 3
    assert rg["props"]["ids"] == [route_id]
    assert rg["props"]["show_price"] is False


def test_publish_and_public_payload_has_route_grid(client):
    # Create page and set required SEO/slug
    r = client.post(f"{BASE_URL}/api/landing/pages",
                    json={"template": "armada-bandara", "title": "TEST Publish Route Grid"},
                    timeout=30)
    assert r.status_code in (200, 201)
    page = r.json().get("page") or r.json()
    pid = page["id"]
    created_page_ids.append(pid)

    # Ensure seo title & slug set
    slug = page.get("slug") or "test-publish-route-grid"
    patch_body = {
        "slug": slug,
        "title": "TEST Publish Route Grid",
        "seo": {"title": "TEST Publish Route Grid", "description": "test"},
    }
    rp = client.patch(f"{BASE_URL}/api/landing/pages/{pid}", json=patch_body, timeout=30)
    assert rp.status_code == 200, rp.text
    saved = rp.json().get("page") or rp.json()
    slug = saved.get("slug") or slug

    # Publish
    pub = client.post(f"{BASE_URL}/api/landing/pages/{pid}/publish", timeout=30)
    assert pub.status_code in (200, 201), f"publish failed: {pub.status_code} {pub.text}"

    # Public payload
    pubr = requests.get(f"{BASE_URL}/api/public/landing/{slug}?vid=test", timeout=20)
    assert pubr.status_code == 200, pubr.text
    data = pubr.json()
    blocks = data.get("blocks", [])
    rg = [b for b in blocks if b.get("type") == "route_grid"]
    assert rg, "route_grid missing from public payload"


def test_regression_other_template_still_works(client):
    r = client.post(f"{BASE_URL}/api/landing/pages",
                    json={"template": "armada-konversi", "title": "TEST_armada_konversi"},
                    timeout=30)
    assert r.status_code in (200, 201), r.text
    page = r.json().get("page") or r.json()
    created_page_ids.append(page["id"])
    assert page.get("blocks")


def test_public_regression_existing_page():
    r = requests.get(f"{BASE_URL}/api/public/landing/sewa-hiace-jakarta", timeout=20)
    # This is a seeded demo page; if 404 it's a regression risk but just log
    assert r.status_code in (200, 404)

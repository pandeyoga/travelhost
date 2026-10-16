"""Tests for content import + public/CMS APIs (iteration_7)."""
import os
import re
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"


@pytest.fixture(scope="module")
def owner_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "owner@demo.local", "password": "demo12345"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def owner_client(owner_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {owner_token}", "Content-Type": "application/json"})
    return s


# ---------- Idempotency via DB counts (Mongo) ----------
def test_db_counts_idempotent():
    from pymongo import MongoClient
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    db = MongoClient(mongo_url)[db_name]

    slugs = ["bromo", "yogyakarta", "bandung", "pangandaran"]
    for slug in slugs:
        n = db.destinations.count_documents({"slug": slug, "deleted": {"$ne": True}})
        assert n == 1, f"destination {slug} count={n}"

    for slug in ["home", "destinations", "fleet", "packages", "promo", "blog", "about", "contact", "trip-calculator"]:
        n = db.site_pages.count_documents({"slug": slug, "deleted": {"$ne": True}})
        assert n == 1, f"site_page {slug} count={n}"

    for name in ["Michael & Friends", "Keluarga Hartono", "Ibu Ratna & Rombongan Majelis"]:
        n = db.testimonials.count_documents({"name": name, "deleted": {"$ne": True}})
        assert n == 1, f"testimonial {name} count={n}"

    media_count = db.media_assets.count_documents({
        "import_key": {"$regex": "^content_import:"},
        "deleted": {"$ne": True},
    })
    assert media_count == 47, f"media_assets count={media_count}"


# ---------- Public destinations ----------
def test_public_destinations_list():
    r = requests.get(f"{BASE_URL}/api/public/destinations", timeout=30)
    assert r.status_code == 200
    data = r.json()
    items = data.get("items") if isinstance(data, dict) else data
    assert isinstance(items, list)
    by_slug = {d["slug"]: d for d in items if "slug" in d}
    for slug in ["bromo", "yogyakarta", "bandung", "pangandaran"]:
        assert slug in by_slug, f"missing {slug}"
        d = by_slug[slug]
        assert d.get("popular") is True, f"{slug} not popular"
        hi = d.get("hero_image") or ""
        assert hi.startswith("/api/public/media/"), f"{slug} hero_image={hi}"
        assert isinstance(d.get("gallery"), list) and len(d["gallery"]) == 4, f"{slug} gallery={d.get('gallery')}"
        hl = d.get("highlights") or []
        assert len(hl) >= 1
        for h in hl:
            assert h.get("title") and h.get("desc") and h.get("image"), f"{slug} highlight missing fields: {h}"
        assert len(d.get("itinerary") or []) == 3, f"{slug} itinerary"
        assert len(d.get("faqs") or []) == 3, f"{slug} faqs"
        assert d.get("position") in [1, 2, 3, 4], f"{slug} position={d.get('position')}"

    # bromo/yogya/bandung/pangandaran sort before bali/dieng
    imported_positions = [by_slug[s]["position"] for s in ["bromo", "yogyakarta", "bandung", "pangandaran"]]
    for other in ["bali", "dieng"]:
        if other in by_slug:
            assert by_slug[other]["position"] > max(imported_positions), f"{other} position not after imported"


def test_public_destination_detail_pangandaran():
    r = requests.get(f"{BASE_URL}/api/public/destinations/pangandaran", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["slug"] == "pangandaran"
    assert (d.get("hero_image") or "").startswith("/api/public/media/")
    assert len(d.get("gallery") or []) == 4


def test_hero_image_served():
    r = requests.get(f"{BASE_URL}/api/public/destinations/bromo", timeout=30)
    hero = r.json()["hero_image"]
    r2 = requests.get(f"{BASE_URL}{hero}", timeout=30)
    assert r2.status_code == 200
    assert r2.headers.get("content-type", "").startswith("image/"), r2.headers.get("content-type")


# ---------- Public pages ----------
def test_public_page_home_gallery_and_hero():
    r = requests.get(f"{BASE_URL}/api/public/pages/home", timeout=30)
    assert r.status_code == 200
    data = r.json()
    sections = data.get("sections") or []
    gallery = [s for s in sections if s.get("type") == "gallery" and s.get("enabled", True)]
    assert len(gallery) >= 1, "no gallery section on home"
    items = gallery[0].get("data", {}).get("items") or []
    assert len(items) == 22, f"gallery items={len(items)}"
    for it in items:
        assert "url" in it and "caption" in it, it

    hero = [s for s in sections if s.get("type") == "hero"]
    assert len(hero) >= 1
    hero_data = hero[0].get("data", {})
    assert hero_data.get("title") == "Perjalanan nyaman ke destinasi favorit Jawa", hero_data.get("title")
    assert (hero_data.get("image") or "").startswith("/api/public/media/"), hero_data.get("image")


@pytest.mark.parametrize("slug", ["destinations", "fleet", "about", "contact"])
def test_public_page_hero(slug):
    r = requests.get(f"{BASE_URL}/api/public/pages/{slug}", timeout=30)
    assert r.status_code == 200
    sections = r.json().get("sections") or []
    ph = [s for s in sections if s.get("type") == "page_hero"]
    assert ph, f"no page_hero on {slug}"
    d = ph[0].get("data", {})
    assert d.get("title"), f"{slug} page_hero title empty"
    assert d.get("image"), f"{slug} page_hero image empty"


# ---------- CMS API ----------
def test_cms_home_allowed_types_includes_gallery(owner_client):
    r = owner_client.get(f"{BASE_URL}/api/site/pages/home")
    assert r.status_code == 200, r.text
    data = r.json()
    at = data.get("allowed_types") or []
    assert "gallery" in at, f"allowed_types={at}"


def test_cms_home_roundtrip_preserves_gallery(owner_client):
    r = owner_client.get(f"{BASE_URL}/api/site/pages/home")
    assert r.status_code == 200
    original = r.json()
    sections = original.get("sections") or []
    # capture gallery
    gallery_before = next((s for s in sections if s.get("type") == "gallery"), None)
    assert gallery_before is not None
    items_before = gallery_before["data"].get("items") or []

    # PUT round-trip
    put_body = {"sections": sections}
    r2 = owner_client.put(f"{BASE_URL}/api/site/pages/home", json=put_body)
    assert r2.status_code == 200, r2.text

    r3 = owner_client.get(f"{BASE_URL}/api/site/pages/home")
    sections_after = r3.json().get("sections") or []
    gallery_after = next((s for s in sections_after if s.get("type") == "gallery"), None)
    assert gallery_after is not None
    items_after = gallery_after["data"].get("items") or []
    assert len(items_after) == len(items_before), f"before={len(items_before)} after={len(items_after)}"
    # spot check keys preserved
    for it in items_after:
        assert "url" in it and "caption" in it

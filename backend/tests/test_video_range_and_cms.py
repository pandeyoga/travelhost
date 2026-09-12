"""Backend tests for HTTP Range video streaming + CMS video URL persistence.

Covers iteration 9 asks:
- GET /api/public/media/{id} with Range headers for a video asset (206, Content-Range, 416, etc.)
- Content-Type .mp4 → video/mp4 (not video/x-m4v)
- Image assets still return 200 normally; ?thumb=1 works; ?kind=video ignored
- PUT /api/site/pages/home preserves video URL with ?kind=query in hero & gallery
- PATCH destinations + vehicles preserves video URLs
"""
import os
import io
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://media-upload-dev-1.preview.emergentagent.com").rstrip("/")
EMAIL = "owner@demo.local"
PASSWORD = "demo12345"

TEST_PREFIX = "TEST_range_"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def mp4_asset(headers):
    # Upload random bytes as .mp4 (backend does not validate video content)
    body = os.urandom(4096)
    files = {"file": (f"{TEST_PREFIX}sample.mp4", io.BytesIO(body), "video/mp4")}
    r = requests.post(f"{BASE_URL}/api/media", headers=headers, files=files, timeout=30)
    assert r.status_code in (200, 201), r.text
    data = r.json()
    aid = data.get("id") or data.get("asset", {}).get("id")
    assert aid
    yield {"id": aid, "size": len(body)}
    requests.delete(f"{BASE_URL}/api/media/{aid}", headers=headers, timeout=15)


@pytest.fixture(scope="module")
def png_asset(headers):
    # 1x1 PNG
    png = bytes.fromhex(
        "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
        "890000000D49444154789C6300010000000500010D0A2DB40000000049454E44AE426082"
    )
    files = {"file": (f"{TEST_PREFIX}img.png", io.BytesIO(png), "image/png")}
    r = requests.post(f"{BASE_URL}/api/media", headers=headers, files=files, timeout=30)
    assert r.status_code in (200, 201), r.text
    data = r.json()
    aid = data.get("id") or data.get("asset", {}).get("id")
    yield {"id": aid, "size": len(png)}
    requests.delete(f"{BASE_URL}/api/media/{aid}", headers=headers, timeout=15)


# ─────────────────────── Range streaming ───────────────────────
class TestVideoRange:
    def test_full_get_returns_200_with_accept_ranges(self, mp4_asset):
        r = requests.get(f"{BASE_URL}/api/public/media/{mp4_asset['id']}", timeout=15)
        assert r.status_code == 200, r.text[:200]
        assert r.headers.get("Accept-Ranges") == "bytes"
        assert r.headers.get("Content-Type") == "video/mp4"
        assert int(r.headers.get("Content-Length", "0")) == mp4_asset["size"]

    def test_range_prefix_returns_206(self, mp4_asset):
        r = requests.get(f"{BASE_URL}/api/public/media/{mp4_asset['id']}",
                         headers={"Range": "bytes=0-99"}, timeout=15)
        assert r.status_code == 206
        assert r.headers.get("Content-Range") == f"bytes 0-99/{mp4_asset['size']}"
        assert int(r.headers.get("Content-Length", "0")) == 100
        assert len(r.content) == 100

    def test_range_suffix_last_1000(self, mp4_asset):
        size = mp4_asset["size"]
        r = requests.get(f"{BASE_URL}/api/public/media/{mp4_asset['id']}",
                         headers={"Range": f"bytes={size-1000}-"}, timeout=15)
        assert r.status_code == 206
        assert r.headers.get("Content-Range") == f"bytes {size-1000}-{size-1}/{size}"
        assert len(r.content) == 1000

    def test_range_out_of_bounds_416(self, mp4_asset):
        size = mp4_asset["size"]
        r = requests.get(f"{BASE_URL}/api/public/media/{mp4_asset['id']}",
                         headers={"Range": f"bytes={size+1}-"}, timeout=15)
        assert r.status_code == 416
        assert r.headers.get("Content-Range") == f"bytes */{size}"

    def test_kind_query_ignored(self, mp4_asset):
        r = requests.get(f"{BASE_URL}/api/public/media/{mp4_asset['id']}?kind=video", timeout=15)
        assert r.status_code == 200
        assert r.headers.get("Content-Type") == "video/mp4"


class TestImageRegression:
    def test_image_returns_200(self, png_asset):
        r = requests.get(f"{BASE_URL}/api/public/media/{png_asset['id']}", timeout=15)
        assert r.status_code == 200
        assert r.headers.get("Content-Type", "").startswith("image/")

    def test_image_thumb(self, png_asset):
        r = requests.get(f"{BASE_URL}/api/public/media/{png_asset['id']}?thumb=1", timeout=15)
        # thumb may or may not be generated; either 200 or fallback to original 200
        assert r.status_code == 200


# ─────────────────────── CMS page persistence ───────────────────────
class TestCMSHomePage:
    def test_home_page_saves_video_urls(self, headers, mp4_asset):
        video_url = f"/api/public/media/{mp4_asset['id']}?kind=video"
        # First GET current page
        r = requests.get(f"{BASE_URL}/api/site/pages/home", headers=headers, timeout=15)
        assert r.status_code == 200
        current = r.json() or {}
        # Merge into blocks structure keeping shape flexible
        payload = dict(current)
        # Ensure we send a shape site accepts
        payload_hero_gallery = {
            "hero": {"image": video_url},
            "gallery": {"items": [{"url": video_url, "caption": "TEST_video"},
                                  {"url": "https://images.unsplash.com/photo-1", "caption": "img"}]},
        }
        # Try flat first
        r = requests.put(f"{BASE_URL}/api/site/pages/home", headers=headers,
                         json={**payload, **payload_hero_gallery}, timeout=15)
        assert r.status_code in (200, 204), r.text[:300]

        # Verify public read
        r = requests.get(f"{BASE_URL}/api/public/pages/home", timeout=15)
        assert r.status_code == 200
        txt = r.text
        assert "kind=video" in txt, "Video URL query string not preserved in public page payload"


class TestCMSDestination:
    def test_destination_saves_video_hero_and_gallery(self, headers, mp4_asset):
        # Find any destination via CMS
        r = requests.get(f"{BASE_URL}/api/content/destinations", headers=headers, timeout=15)
        assert r.status_code == 200
        payload = r.json()
        rows = payload.get("items") if isinstance(payload, dict) else payload
        assert rows, "no destinations to test"
        d = rows[0]
        did = d["id"]
        video_url = f"/api/public/media/{mp4_asset['id']}?kind=video"
        gallery = [video_url, "https://images.unsplash.com/photo-1537996194471-e657df975ab4?w=800"]
        r = requests.put(f"{BASE_URL}/api/content/destinations/{did}", headers=headers,
                         json={**d, "hero_image": video_url, "gallery": gallery}, timeout=15)
        assert r.status_code in (200, 204), f"put failed: {r.status_code} {r.text[:200]}"
        # Verify via public endpoint using slug
        slug = d.get("slug")
        if slug:
            r = requests.get(f"{BASE_URL}/api/public/destinations/{slug}", timeout=15)
            assert r.status_code == 200
            body = r.json()
            assert "kind=video" in (body.get("hero_image") or ""), body.get("hero_image")
            assert any("kind=video" in u for u in (body.get("gallery") or []))


class TestCMSVehicle:
    def test_vehicle_saves_video_in_photos(self, headers, mp4_asset):
        r = requests.get(f"{BASE_URL}/api/vehicles", headers=headers, timeout=15)
        if r.status_code != 200:
            pytest.skip("vehicles endpoint not available")
        rows = r.json()
        if not rows:
            pytest.skip("no vehicles seeded")
        v = rows[0]
        vid = v["id"]
        video_url = f"/api/public/media/{mp4_asset['id']}?kind=video"
        photos = [video_url, "https://images.unsplash.com/photo-1537996194471-e657df975ab4?w=800"]
        gallery = [{"url": video_url, "caption": "v"}, {"url": photos[1], "caption": "i"}]
        r = requests.patch(f"{BASE_URL}/api/vehicles/{vid}", headers=headers,
                           json={"photos": photos, "gallery": gallery}, timeout=15)
        assert r.status_code in (200, 204), r.text[:200]
        r = requests.get(f"{BASE_URL}/api/public/fleet/{vid}", timeout=15)
        if r.status_code == 200:
            body = r.json()
            combined = (body.get("photos") or []) + (body.get("gallery") or [])
            assert any("kind=video" in str(u) for u in combined)

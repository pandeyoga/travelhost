"""Backend tests for Media Library video upload fix (BUG: .mov not selectable).

Covers:
- POST /api/media accepts .mov with application/octet-stream (MIME inferred from ext)
- POST /api/media accepts .webm with empty content-type and .mp4 with video/mp4
- POST /api/media rejects .avi with HTTP 400 and Indonesian error message
- POST /api/media/{id}/replace accepts .mov as application/octet-stream
- GET /api/media?kind=video lists uploaded videos
- GET /api/public/media/{id} returns bytes with correct content type
"""
import io
import os
import pytest
import requests

def _load_base_url():
    url = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not url:
        try:
            with open("/app/frontend/.env", "r") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
        except OSError:
            pass
    return url.rstrip("/")

BASE_URL = _load_base_url()
EMAIL = "owner@demo.local"
PASSWORD = "demo12345"

# Minimal valid-ish MP4 header (ftyp box) so anything reading magic doesn't crash;
# our backend does not decode video content, just validates MIME + size.
FAKE_MP4 = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41" + b"\x00" * 64
FAKE_MOV = b"\x00\x00\x00\x14ftypqt  \x00\x00\x02\x00qt  " + b"\x00" * 64
FAKE_WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64  # EBML header
FAKE_PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 200)
FAKE_AVI = b"RIFF\x00\x00\x00\x00AVI " + b"\x00" * 64


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": EMAIL, "password": PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    assert tok, f"no token in login response: {data}"
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


created_ids = []


@pytest.fixture(scope="module", autouse=True)
def cleanup(headers):
    yield
    for mid in created_ids:
        try:
            requests.delete(f"{BASE_URL}/api/media/{mid}", headers=headers, timeout=10)
        except Exception:
            pass


def _upload(headers, filename, content, content_type):
    files = {"file": (filename, io.BytesIO(content), content_type)}
    return requests.post(f"{BASE_URL}/api/media", headers=headers, files=files, timeout=30)


# ---- Test: .mov with application/octet-stream (main bug scenario)
def test_upload_mov_as_octet_stream(headers):
    r = _upload(headers, "TEST_clip.mov", FAKE_MOV, "application/octet-stream")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kind"] == "video"
    assert data["content_type"] == "video/quicktime"
    created_ids.append(data["id"])


# ---- Test: .webm with empty content-type
def test_upload_webm_empty_ct(headers):
    files = {"file": ("TEST_clip.webm", io.BytesIO(FAKE_WEBM), "")}
    r = requests.post(f"{BASE_URL}/api/media", headers=headers, files=files, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kind"] == "video"
    assert data["content_type"] in ("video/webm", "application/octet-stream") or "webm" in data["content_type"]
    # The saved content type must be one classify() accepts
    assert data["content_type"] == "video/webm"
    created_ids.append(data["id"])


# ---- Test: .mp4 with video/mp4
def test_upload_mp4(headers):
    r = _upload(headers, "TEST_clip.mp4", FAKE_MP4, "video/mp4")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kind"] == "video"
    assert data["content_type"] == "video/mp4"
    created_ids.append(data["id"])


# ---- Test: .avi -> rejected 400 with Indonesian error
def test_upload_avi_rejected(headers):
    r = _upload(headers, "TEST_clip.avi", FAKE_AVI, "video/x-msvideo")
    assert r.status_code == 400
    detail = r.json().get("detail", "")
    assert "tidak didukung" in detail.lower() or "tidak didukung" in detail


# ---- Test: replace with .mov as application/octet-stream
def test_replace_with_mov_octet_stream(headers):
    # Ensure we have a video asset to replace
    if not created_ids:
        pytest.skip("no created video asset")
    mid = created_ids[0]
    files = {"file": ("TEST_replacement.mov", io.BytesIO(FAKE_MOV), "application/octet-stream")}
    r = requests.post(f"{BASE_URL}/api/media/{mid}/replace",
                      headers=headers, files=files, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["content_type"] == "video/quicktime"


# ---- Test: list ?kind=video contains our uploads
def test_list_kind_video(headers):
    r = requests.get(f"{BASE_URL}/api/media?kind=video&limit=200",
                     headers=headers, timeout=20)
    assert r.status_code == 200
    items = r.json().get("items") or r.json().get("assets") or []
    ids = {i.get("id") for i in items}
    for mid in created_ids:
        assert mid in ids, f"uploaded video {mid} not in list"


# ---- Test: public GET returns bytes + correct content type
def test_public_read(headers):
    if not created_ids:
        pytest.skip("no created video asset")
    mid = created_ids[-1]  # freshest
    r = requests.get(f"{BASE_URL}/api/public/media/{mid}", timeout=20)
    assert r.status_code == 200, r.text
    ct = r.headers.get("Content-Type", "")
    assert ct.startswith("video/"), f"expected video content-type, got {ct}"
    assert len(r.content) > 0


# ---- Regression: .png still works
def test_upload_png_regression(headers):
    r = _upload(headers, "TEST_pixel.png", FAKE_PNG, "image/png")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kind"] == "image"
    created_ids.append(data["id"])

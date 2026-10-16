"""backend_test_media_unified.py — Test Media Library unification (FASE 3).

Tests:
1. RBAC: ops_admin & marketing_admin can access /api/media/*, driver gets 403
2. Upload via CMS appears in Media Library (unification)
3. Folder operations (create, update, delete → assets move to parent)
4. Replace file increments version
5. Import legacy assets (idempotent)
6. BUG-0113 regression: wrong types return 4xx not 500
7. Public media URLs work
"""
import io
import sys
import requests
from datetime import datetime

BASE_URL = "https://trip-route-buttons.preview.emergentagent.com"

class MediaLibraryTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tokens = {}
        self.test_assets = []
        self.test_folders = []

    def log(self, msg):
        print(f"  {msg}")

    def test(self, name, condition, details=""):
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            print(f"✅ {name}")
            if details:
                self.log(details)
        else:
            print(f"❌ {name}")
            if details:
                self.log(f"FAIL: {details}")
        return condition

    def login(self, email, password="demo12345"):
        """Login and store token."""
        try:
            resp = requests.post(f"{BASE_URL}/api/auth/login",
                                json={"email": email, "password": password},
                                timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                self.tokens[email] = data.get("token")
                self.log(f"Logged in as {email}")
                return True
            else:
                self.log(f"Login failed for {email}: {resp.status_code}")
                return False
        except Exception as e:
            self.log(f"Login error for {email}: {e}")
            return False

    def headers(self, email):
        """Get auth headers for user."""
        token = self.tokens.get(email)
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    def test_rbac_media_access(self):
        """Test RBAC: ops_admin & marketing_admin can access, driver cannot."""
        print("\n🔐 Testing RBAC for Media Library...")
        
        # ops_admin should have access
        resp = requests.get(f"{BASE_URL}/api/media",
                           headers=self.headers("ops@demo.local"),
                           timeout=10)
        self.test("ops_admin can access GET /api/media",
                 resp.status_code == 200,
                 f"Status: {resp.status_code}")

        # marketing_admin should have access
        resp = requests.get(f"{BASE_URL}/api/media",
                           headers=self.headers("marketing@demo.local"),
                           timeout=10)
        self.test("marketing_admin can access GET /api/media",
                 resp.status_code == 200,
                 f"Status: {resp.status_code}")

        # driver should be blocked (403)
        resp = requests.get(f"{BASE_URL}/api/media",
                           headers=self.headers("driver@demo.local"),
                           timeout=10)
        self.test("driver blocked from GET /api/media (403)",
                 resp.status_code == 403,
                 f"Status: {resp.status_code} (expected 403)")

        # Test other media endpoints for driver
        endpoints = [
            "/api/media/folders",
            "/api/media/health",
        ]
        for endpoint in endpoints:
            resp = requests.get(f"{BASE_URL}{endpoint}",
                               headers=self.headers("driver@demo.local"),
                               timeout=10)
            self.test(f"driver blocked from GET {endpoint}",
                     resp.status_code == 403,
                     f"Status: {resp.status_code}")

    def test_cms_upload_appears_in_library(self):
        """Test US1: Upload via CMS appears in Media Library."""
        print("\n📤 Testing CMS upload appears in Media Library...")
        
        # Create a small test image (1x1 PNG)
        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        
        # Upload via CMS endpoint
        files = {'file': ('test_cms_upload.png', io.BytesIO(png_data), 'image/png')}
        resp = requests.post(f"{BASE_URL}/api/uploads/cms",
                            files=files,
                            headers=self.headers("ops@demo.local"),
                            timeout=10)
        
        if not self.test("Upload via POST /api/uploads/cms succeeds",
                        resp.status_code == 200,
                        f"Status: {resp.status_code}"):
            return
        
        upload_data = resp.json()
        self.log(f"Uploaded: {upload_data.get('url')}")
        
        # Now check if it appears in Media Library
        resp = requests.get(f"{BASE_URL}/api/media?q=test_cms_upload",
                           headers=self.headers("ops@demo.local"),
                           timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            assets = data.get("assets", [])
            found = any("test_cms_upload" in a.get("original_filename", "") for a in assets)
            self.test("CMS upload appears in Media Library",
                     found,
                     f"Found {len(assets)} assets, CMS upload present: {found}")
            if found:
                # Store asset ID for cleanup
                for a in assets:
                    if "test_cms_upload" in a.get("original_filename", ""):
                        self.test_assets.append(a.get("id"))
        else:
            self.test("CMS upload appears in Media Library",
                     False,
                     f"Failed to query media library: {resp.status_code}")

    def test_folder_operations(self):
        """Test US3: Folder operations (create, delete → assets move to parent)."""
        print("\n📁 Testing folder operations...")
        
        # Create parent folder
        resp = requests.post(f"{BASE_URL}/api/media/folders",
                            json={"name": "Test Parent Folder"},
                            headers=self.headers("ops@demo.local"),
                            timeout=10)
        
        if not self.test("Create parent folder",
                        resp.status_code == 200,
                        f"Status: {resp.status_code}"):
            return
        
        parent_folder = resp.json()
        parent_id = parent_folder.get("id")
        self.test_folders.append(parent_id)
        self.log(f"Created parent folder: {parent_id}")
        
        # Create child folder
        resp = requests.post(f"{BASE_URL}/api/media/folders",
                            json={"name": "Test Child Folder", "parent_id": parent_id},
                            headers=self.headers("ops@demo.local"),
                            timeout=10)
        
        if not self.test("Create child folder",
                        resp.status_code == 200,
                        f"Status: {resp.status_code}"):
            return
        
        child_folder = resp.json()
        child_id = child_folder.get("id")
        self.test_folders.append(child_id)
        self.log(f"Created child folder: {child_id}")
        
        # Upload an asset to child folder
        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        files = {'file': ('test_folder_asset.png', io.BytesIO(png_data), 'image/png')}
        data = {'folder_id': child_id}
        resp = requests.post(f"{BASE_URL}/api/media",
                            files=files,
                            data=data,
                            headers=self.headers("ops@demo.local"),
                            timeout=10)
        
        if not self.test("Upload asset to child folder",
                        resp.status_code == 200,
                        f"Status: {resp.status_code}"):
            return
        
        asset = resp.json()
        asset_id = asset.get("id")
        self.test_assets.append(asset_id)
        self.log(f"Uploaded asset to child folder: {asset_id}")
        
        # Verify asset is in child folder
        self.test("Asset folder_id matches child folder",
                 asset.get("folder_id") == child_id,
                 f"folder_id: {asset.get('folder_id')}")
        
        # Delete child folder
        resp = requests.delete(f"{BASE_URL}/api/media/folders/{child_id}",
                              headers=self.headers("ops@demo.local"),
                              timeout=10)
        
        if not self.test("Delete child folder",
                        resp.status_code == 200,
                        f"Status: {resp.status_code}"):
            return
        
        delete_result = resp.json()
        self.log(f"Deleted folder, moved {delete_result.get('moved_assets')} assets")
        
        # Verify asset moved to parent folder (not deleted)
        resp = requests.get(f"{BASE_URL}/api/media/{asset_id}",
                           headers=self.headers("ops@demo.local"),
                           timeout=10)
        
        if resp.status_code == 200:
            updated_asset = resp.json()
            self.test("Asset moved to parent folder (not deleted)",
                     updated_asset.get("folder_id") == parent_id,
                     f"Asset folder_id: {updated_asset.get('folder_id')}, parent: {parent_id}")
        else:
            self.test("Asset still exists after folder deletion",
                     False,
                     f"Asset not found: {resp.status_code}")

    def test_replace_file_version(self):
        """Test US4: Replace file increments version."""
        print("\n🔄 Testing replace file increments version...")
        
        # Upload initial asset
        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        files = {'file': ('test_version.png', io.BytesIO(png_data), 'image/png')}
        resp = requests.post(f"{BASE_URL}/api/media",
                            files=files,
                            headers=self.headers("ops@demo.local"),
                            timeout=10)
        
        if not self.test("Upload initial asset",
                        resp.status_code == 200,
                        f"Status: {resp.status_code}"):
            return
        
        asset = resp.json()
        asset_id = asset.get("id")
        initial_version = asset.get("version", 1)
        self.test_assets.append(asset_id)
        self.log(f"Initial version: {initial_version}")
        
        # Replace file
        files = {'file': ('test_version_v2.png', io.BytesIO(png_data), 'image/png')}
        resp = requests.post(f"{BASE_URL}/api/media/{asset_id}/replace",
                            files=files,
                            headers=self.headers("ops@demo.local"),
                            timeout=10)
        
        if not self.test("Replace file succeeds",
                        resp.status_code == 200,
                        f"Status: {resp.status_code}"):
            return
        
        updated_asset = resp.json()
        new_version = updated_asset.get("version", 1)
        self.test("Version incremented after replace",
                 new_version > initial_version,
                 f"Old version: {initial_version}, new version: {new_version}")

    def test_bug_0113_regression(self):
        """Test BUG-0113: Wrong types should return 4xx not 500."""
        print("\n🐛 Testing BUG-0113 regression (wrong types → 4xx not 500)...")
        
        # Upload a test asset first
        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        files = {'file': ('test_bug.png', io.BytesIO(png_data), 'image/png')}
        resp = requests.post(f"{BASE_URL}/api/media",
                            files=files,
                            headers=self.headers("ops@demo.local"),
                            timeout=10)
        
        if resp.status_code != 200:
            self.log(f"Failed to upload test asset: {resp.status_code}")
            return
        
        asset = resp.json()
        asset_id = asset.get("id")
        self.test_assets.append(asset_id)
        
        # Test 1: PATCH with folder_id as integer (should be 4xx not 500)
        resp = requests.patch(f"{BASE_URL}/api/media/{asset_id}",
                             json={"folder_id": 12345},  # integer instead of string
                             headers=self.headers("ops@demo.local"),
                             timeout=10)
        
        self.test("PATCH with folder_id as integer returns 4xx (not 500)",
                 400 <= resp.status_code < 500,
                 f"Status: {resp.status_code} (expected 4xx)")
        
        # Test 2: PATCH with alt as object (should be 4xx not 500)
        resp = requests.patch(f"{BASE_URL}/api/media/{asset_id}",
                             json={"alt": {"x": [1, 2]}},  # object instead of string
                             headers=self.headers("ops@demo.local"),
                             timeout=10)
        
        self.test("PATCH with alt as object returns 4xx (not 500)",
                 400 <= resp.status_code < 500,
                 f"Status: {resp.status_code} (expected 4xx)")
        
        # Test 3: POST bulk-move with ids as string (should be 4xx not 500)
        resp = requests.post(f"{BASE_URL}/api/media/bulk-move",
                            json={"ids": "not-a-list", "folder_id": ""},
                            headers=self.headers("ops@demo.local"),
                            timeout=10)
        
        self.test("POST bulk-move with ids as string returns 4xx (not 500)",
                 400 <= resp.status_code < 500,
                 f"Status: {resp.status_code} (expected 4xx)")

    def test_public_media_urls(self):
        """Test that public media URLs work without auth."""
        print("\n🌐 Testing public media URLs...")
        
        # Upload an asset
        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        files = {'file': ('test_public.png', io.BytesIO(png_data), 'image/png')}
        resp = requests.post(f"{BASE_URL}/api/media",
                            files=files,
                            headers=self.headers("ops@demo.local"),
                            timeout=10)
        
        if resp.status_code != 200:
            self.log(f"Failed to upload test asset: {resp.status_code}")
            return
        
        asset = resp.json()
        asset_id = asset.get("id")
        public_url = asset.get("url")
        self.test_assets.append(asset_id)
        
        self.log(f"Public URL: {public_url}")
        
        # Test public URL without auth
        resp = requests.get(f"{BASE_URL}{public_url}", timeout=10)
        self.test("Public media URL accessible without auth",
                 resp.status_code == 200,
                 f"Status: {resp.status_code}")
        
        # Verify it's actually an image
        self.test("Public URL returns image content",
                 resp.headers.get("content-type", "").startswith("image/"),
                 f"Content-Type: {resp.headers.get('content-type')}")

    def test_import_legacy_idempotent(self):
        """Test US7: Import legacy assets is idempotent."""
        print("\n📥 Testing import legacy assets (idempotent)...")
        
        # First import
        resp = requests.post(f"{BASE_URL}/api/media/import-legacy",
                            headers=self.headers("ops@demo.local"),
                            timeout=15)
        
        if not self.test("First import-legacy call succeeds",
                        resp.status_code == 200,
                        f"Status: {resp.status_code}"):
            return
        
        first_result = resp.json()
        first_imported = first_result.get("imported", 0)
        self.log(f"First import: {first_imported} assets imported, {first_result.get('skipped', 0)} skipped")
        
        # Second import (should be idempotent)
        resp = requests.post(f"{BASE_URL}/api/media/import-legacy",
                            headers=self.headers("ops@demo.local"),
                            timeout=15)
        
        if not self.test("Second import-legacy call succeeds",
                        resp.status_code == 200,
                        f"Status: {resp.status_code}"):
            return
        
        second_result = resp.json()
        second_imported = second_result.get("imported", 0)
        self.log(f"Second import: {second_imported} assets imported, {second_result.get('skipped', 0)} skipped")
        
        self.test("Second import is idempotent (imported=0)",
                 second_imported == 0,
                 f"Second import imported {second_imported} assets (expected 0)")

    def cleanup(self):
        """Clean up test assets and folders."""
        print("\n🧹 Cleaning up test data...")
        
        # Delete test assets
        if self.test_assets:
            resp = requests.post(f"{BASE_URL}/api/media/bulk-delete",
                                json={"ids": self.test_assets},
                                headers=self.headers("ops@demo.local"),
                                timeout=10)
            if resp.status_code == 200:
                self.log(f"Deleted {len(self.test_assets)} test assets")
        
        # Delete test folders
        for folder_id in self.test_folders:
            resp = requests.delete(f"{BASE_URL}/api/media/folders/{folder_id}",
                                  headers=self.headers("ops@demo.local"),
                                  timeout=10)
            if resp.status_code == 200:
                self.log(f"Deleted folder {folder_id}")

    def run_all_tests(self):
        print("=" * 70)
        print("🧪 Media Library Backend Tests (FASE 3)")
        print("=" * 70)
        
        # Login all users
        print("\n🔑 Logging in test users...")
        if not self.login("ops@demo.local"):
            print("❌ Failed to login ops@demo.local - aborting tests")
            return 1
        if not self.login("marketing@demo.local"):
            print("❌ Failed to login marketing@demo.local - aborting tests")
            return 1
        if not self.login("driver@demo.local"):
            print("❌ Failed to login driver@demo.local - aborting tests")
            return 1
        
        # Run tests
        try:
            self.test_rbac_media_access()
            self.test_cms_upload_appears_in_library()
            self.test_folder_operations()
            self.test_replace_file_version()
            self.test_bug_0113_regression()
            self.test_public_media_urls()
            self.test_import_legacy_idempotent()
        finally:
            self.cleanup()
        
        # Summary
        print("\n" + "=" * 70)
        print(f"📊 Results: {self.tests_passed}/{self.tests_run} tests passed")
        print("=" * 70)
        
        return 0 if self.tests_passed == self.tests_run else 1


if __name__ == "__main__":
    tester = MediaLibraryTester()
    sys.exit(tester.run_all_tests())

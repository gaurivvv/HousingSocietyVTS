"""Tests verifying offline static assets, CORS, and production settings."""

import os
from pathlib import Path
from django.conf import settings
from django.test import SimpleTestCase


class OfflineStaticAssetsTests(SimpleTestCase):
    def test_local_vendor_assets_exist(self):
        """All required local vendor CSS, JS, and font files exist on disk."""
        static_dir = Path(settings.BASE_DIR) / "static"
        required_files = [
            static_dir / "vendor/bootstrap/css/bootstrap.min.css",
            static_dir / "vendor/bootstrap/js/bootstrap.bundle.min.js",
            static_dir / "vendor/bootstrap-icons/bootstrap-icons.min.css",
            static_dir / "vendor/bootstrap-icons/fonts/bootstrap-icons.woff2",
            static_dir / "vendor/bootstrap-icons/fonts/bootstrap-icons.woff",
        ]
        for file_path in required_files:
            self.assertTrue(file_path.exists(), f"Missing offline asset: {file_path}")
            self.assertGreater(file_path.stat().st_size, 1000, f"Asset too small: {file_path}")

    def test_base_template_has_no_cdn_references(self):
        """base.html has zero external CDN links."""
        base_html = Path(settings.BASE_DIR) / "templates/base.html"
        content = base_html.read_text(encoding="utf-8")
        self.assertNotIn("cdn.jsdelivr.net", content)
        self.assertNotIn("http://", content)
        self.assertNotIn("https://", content)


class DeploymentConfigurationTests(SimpleTestCase):
    def test_static_root_configured(self):
        """STATIC_ROOT is defined for collectstatic in production."""
        self.assertTrue(hasattr(settings, "STATIC_ROOT"))
        self.assertEqual(settings.STATIC_ROOT, settings.BASE_DIR / "staticfiles")

    def test_debug_and_allowed_hosts_configured(self):
        """Settings can configure DEBUG and ALLOWED_HOSTS dynamically."""
        self.assertIsInstance(settings.DEBUG, bool)
        self.assertIsInstance(settings.ALLOWED_HOSTS, list)

    def test_cors_middleware_headers(self):
        """OPTIONS preflight and API endpoints include permissive CORS headers."""
        response = self.client.options("/api/v1/ping/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Access-Control-Allow-Origin"], "*")
        self.assertIn("POST", response["Access-Control-Allow-Methods"])

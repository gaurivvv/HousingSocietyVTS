"""Unit tests for tracking/anpr_service.py."""

from unittest.mock import MagicMock, patch
from django.test import TestCase

from tracking.anpr_service import get_anpr_executable, get_cli_script, run_anpr


class ANPRServiceTests(TestCase):
    def test_environment_paths_configured(self):
        """Service locates the python executable or handles absence gracefully."""
        exe = get_anpr_executable()
        script = get_cli_script()
        # In this workspace, both exist in C:\\Users\\gauri\\Projects\\anpr-lab
        self.assertTrue(exe is None or exe.exists())
        self.assertTrue(script is None or script.exists())

    def test_run_anpr_missing_image_path(self):
        """run_anpr handles nonexistent file gracefully."""
        res = run_anpr("non_existent_image_12345.jpg")
        self.assertFalse(res["success"])
        self.assertIn("not found", res["error"])

    @patch("subprocess.run")
    def test_run_anpr_mock_success(self, mock_subproc):
        """run_anpr parses JSON output correctly from subprocess."""
        mock_proc = MagicMock()
        mock_proc.stdout = 'UserWarning: some warning\n{"success": true, "candidate_plate": "MH12KL4567", "vehicle_type": "car", "plate_detected": true}\n'
        mock_subproc.return_value = mock_proc

        res = run_anpr(b"fake_image_bytes")
        self.assertTrue(res["success"])
        self.assertEqual(res["candidate_plate"], "MH12KL4567")
        self.assertEqual(res["vehicle_type"], "car")

    @patch("subprocess.run")
    def test_run_anpr_mock_timeout(self, mock_subproc):
        """run_anpr handles subprocess timeout safely without crashing."""
        import subprocess
        mock_subproc.side_effect = subprocess.TimeoutExpired(cmd=["python"], timeout=30)

        res = run_anpr(b"fake_image_bytes")
        self.assertFalse(res["success"])
        self.assertIn("timed out", res["error"])

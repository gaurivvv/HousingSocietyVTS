"""ANPR Service Integration for Housing Society VTS.

Connects the Django gate management workflow with the AI/ML ANPR pipeline
in anpr-lab.

Design Principle:
- ANPR provides a CANDIDATE plate recommendation to assist the guard.
- Predictions are NEVER automatically saved to the database.
- A human guard must visually review, correct if needed, and confirm the movement.
"""

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Default locations for anpr-lab environment and scripts
DEFAULT_LAB_DIR = Path(r"C:\Users\gauri\Projects\anpr-lab")
DEFAULT_PYTHON_EXE = DEFAULT_LAB_DIR / ".venv" / "Scripts" / "python.exe"
DEFAULT_CLI_SCRIPT = DEFAULT_LAB_DIR / "scripts" / "run_anpr_cli.py"


def get_anpr_executable():
    """Retrieve path to anpr-lab Python interpreter."""
    env_path = os.getenv("ANPR_PYTHON_PATH")
    if env_path and Path(env_path).exists():
        return Path(env_path)
    if DEFAULT_PYTHON_EXE.exists():
        return DEFAULT_PYTHON_EXE
    return None


def get_cli_script():
    """Retrieve path to anpr CLI script."""
    env_path = os.getenv("ANPR_CLI_SCRIPT")
    if env_path and Path(env_path).exists():
        return Path(env_path)
    if DEFAULT_CLI_SCRIPT.exists():
        return DEFAULT_CLI_SCRIPT
    return None


def run_anpr(image_input):
    """Run ANPR pipeline on an image file path or file-like object / bytes.

    Returns:
        dict containing:
            success (bool)
            candidate_plate (str)
            raw_text (str)
            vehicle_detected (bool)
            vehicle_type (str or None)
            plate_detected (bool)
            plate_confidence (float)
            ocr_confidence (float)
            format_status (str)
            corrections (list)
            uncertain (bool)
            error (str or None)
    """
    python_exe = get_anpr_executable()
    cli_script = get_cli_script()

    if not python_exe or not cli_script:
        return {
            "success": False,
            "error": "ANPR pipeline environment not configured or unavailable.",
            "candidate_plate": "",
            "vehicle_detected": False,
            "plate_detected": False,
        }

    temp_file = None
    try:
        # If input is bytes or an uploaded file object
        if hasattr(image_input, "read"):
            temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            image_input.seek(0)
            temp_file.write(image_input.read())
            temp_file.flush()
            temp_file.close()
            target_path = temp_file.name
        elif isinstance(image_input, (bytes, bytearray)):
            temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            temp_file.write(image_input)
            temp_file.flush()
            temp_file.close()
            target_path = temp_file.name
        elif isinstance(image_input, (str, Path)):
            target_path = str(image_input)
            if not Path(target_path).exists():
                return {
                    "success": False,
                    "error": f"Image file not found: {target_path}",
                    "candidate_plate": "",
                }
        else:
            return {
                "success": False,
                "error": "Unsupported image input type.",
                "candidate_plate": "",
            }

        # Run CLI in anpr-lab virtual environment
        proc = subprocess.run(
            [str(python_exe), str(cli_script), target_path],
            capture_output=True,
            text=True,
            timeout=30,
        )

        stdout = proc.stdout.strip()
        if not stdout:
            err = proc.stderr.strip() if proc.stderr else "Unknown ANPR inference error"
            logger.error("ANPR execution produced no output: %s", err)
            return {
                "success": False,
                "error": f"ANPR execution error: {err}",
                "candidate_plate": "",
            }

        # Find the JSON line in stdout (in case libraries wrote messages above)
        parsed_result = None
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    parsed_result = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue

        if not parsed_result:
            return {
                "success": False,
                "error": f"Could not parse ANPR output: {stdout[:200]}",
                "candidate_plate": "",
            }

        return parsed_result

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "ANPR pipeline execution timed out (30s limit).",
            "candidate_plate": "",
        }
    except Exception as exc:
        logger.exception("Unexpected error in run_anpr: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "candidate_plate": "",
        }
    finally:
        if temp_file and Path(temp_file.name).exists():
            try:
                os.remove(temp_file.name)
            except OSError:
                pass

"""Regression tests for the pipeline's validation and file-integrity gates."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPOSITORY = Path(__file__).resolve().parents[1]
CHECKER = REPOSITORY / "scripts/check_pipeline.py"
RUNNER = REPOSITORY / "scripts/run_pipeline.sh"


class TestPipelineChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="processiq-checks-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "data/interim").mkdir(parents=True)
        (self.root / "data/processed").mkdir(parents=True)

    def write_json(self, relative_path, value):
        (self.root / relative_path).write_text(
            json.dumps(value), encoding="utf-8"
        )

    def run_check(self, check):
        return subprocess.run(
            [sys.executable, str(CHECKER), check, "--root", str(self.root)],
            capture_output=True, text=True, check=False,
        )

    def valid_status(self):
        return {
            "structural_integrity_passed": True,
            "count_reconciliation_passed": True,
            "timestamp_scope_review_required": True,
            "duration_metrics_ready": False,
        }

    def make_dashboard(self):
        outputs = {}
        for name, data in {
            "dashboard_cases": b"case_id\ncase_1\n",
            "dashboard_kpis": b"metric,value\ncases,1\n",
        }.items():
            relative_path = f"data/processed/{name}.csv"
            (self.root / relative_path).write_bytes(data)
            outputs[name] = {
                "path": relative_path,
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        manifest = {"generated_outputs": outputs}
        self.write_json("data/interim/dashboard_manifest.json", manifest)
        return manifest

    def test_timestamp_warnings_do_not_block_valid_structure(self):
        self.write_json(
            "data/interim/data_quality_report.json",
            {"status": self.valid_status()},
        )
        result = self.run_check("validation")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_failed_or_missing_flags_are_rejected(self):
        for key in ("structural_integrity_passed", "count_reconciliation_passed"):
            for value in (False, None, "true", 1, "MISSING"):
                with self.subTest(key=key, value=value):
                    status = self.valid_status()
                    if value == "MISSING":
                        del status[key]
                    else:
                        status[key] = value
                    self.write_json("data/interim/data_quality_report.json", {"status": status})
                    result = self.run_check("validation")
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(key, result.stderr)

    def test_malformed_validation_report_is_rejected(self):
        path = self.root / "data/interim/data_quality_report.json"
        for content in ("{broken", "[]", '{"status":null}'):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                self.assertEqual(self.run_check("validation").returncode, 1)

    def test_missing_reports_are_rejected(self):
        for check in ("validation", "dashboard"):
            with self.subTest(check=check):
                self.assertEqual(self.run_check(check).returncode, 1)

    def test_matching_dashboard_files_pass(self):
        self.make_dashboard()
        result = self.run_check("dashboard")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("Checksum verified:"), 2)

    def test_same_size_data_change_is_detected(self):
        self.make_dashboard()
        (self.root / "data/processed/dashboard_cases.csv").write_bytes(b"case_id\ncase_2\n")
        result = self.run_check("dashboard")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Checksum mismatch", result.stderr)

    def test_wrong_size_and_missing_files_are_detected(self):
        self.make_dashboard()
        path = self.root / "data/processed/dashboard_cases.csv"
        path.write_bytes(b"wrong size")
        result = self.run_check("dashboard")
        self.assertEqual(result.returncode, 1)
        self.assertIn("File size mismatch", result.stderr)
        path.unlink()
        self.assertEqual(self.run_check("dashboard").returncode, 1)

    def test_missing_or_redirected_manifest_entries_are_rejected(self):
        for alteration in ("missing", "redirected"):
            with self.subTest(alteration=alteration):
                manifest = self.make_dashboard()
                if alteration == "missing":
                    del manifest["generated_outputs"]["dashboard_cases"]
                else:
                    manifest["generated_outputs"]["dashboard_cases"]["path"] = "wrong.csv"
                self.write_json("data/interim/dashboard_manifest.json", manifest)
                self.assertEqual(self.run_check("dashboard").returncode, 1)

    @unittest.skipUnless(shutil.which("bash"), "Bash is required for the runner test")
    def test_runner_stops_before_transform_when_validation_fails(self):
        # Stub only the upstream validator; execute the real runner and gate.
        scripts = self.root / "scripts"
        scripts.mkdir()
        shutil.copy2(RUNNER, scripts / "run_pipeline.sh")
        shutil.copy2(CHECKER, scripts / "check_pipeline.py")
        (self.root / "pyproject.toml").write_text("", encoding="utf-8")
        package = self.root / "processiq"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "validate_data.py").write_text(
            'print("Stub validator returned a failed report.")\n', encoding="utf-8"
        )
        (package / "transform_data.py").write_text(
            'from pathlib import Path\nPath("transform_ran").touch()\n', encoding="utf-8"
        )
        status = self.valid_status()
        status["structural_integrity_passed"] = False
        self.write_json("data/interim/data_quality_report.json", {"status": status})
        result = subprocess.run(
            ["bash", str(scripts / "run_pipeline.sh"), "fast"],
            cwd=self.root,
            env={**os.environ, "PYTHON_COMMAND": sys.executable, "PYTHONPATH": str(self.root)},
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Enforce validation checks", result.stdout)
        self.assertIn("Validation gate failed", result.stderr)
        self.assertNotIn("[Build analytical tables]", result.stdout)
        self.assertFalse((self.root / "transform_ran").exists())


if __name__ == "__main__":
    unittest.main()

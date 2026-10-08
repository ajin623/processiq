"""Enforce validation flags and verify dashboard file hashes using the standard library."""

import argparse
import hashlib
import json
from pathlib import Path
import sys


def read_object(path: Path) -> dict:
    """Read a JSON object, rejecting other top-level types."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def check_validation(root: Path) -> None:
    """Require structural integrity and count reconciliation; allow scope warnings."""
    report = read_object(root / "data/interim/data_quality_report.json")
    status = report["status"]
    if not isinstance(status, dict):
        raise ValueError("Validation status must be a JSON object")

    required = (
        "structural_integrity_passed",
        "count_reconciliation_passed",
    )
    failed = [name for name in required if status.get(name) is not True]
    if failed:
        raise ValueError("Validation gate failed: " + ", ".join(failed))

    print("Structural integrity and count reconciliation passed.")


def check_dashboard(root: Path) -> None:
    """Verify both dashboard CSVs against their recorded size and SHA-256."""
    manifest = read_object(root / "data/interim/dashboard_manifest.json")
    expected_paths = {
        "dashboard_cases": "data/processed/dashboard_cases.csv",
        "dashboard_kpis": "data/processed/dashboard_kpis.csv",
    }

    for name, expected_path in expected_paths.items():
        entry = manifest["generated_outputs"][name]
        if entry["path"] != expected_path:
            raise ValueError(f"Unexpected manifest path for {name}")

        path = root / expected_path
        if path.stat().st_size != entry["size_bytes"]:
            raise ValueError(f"File size mismatch: {expected_path}")

        with path.open("rb") as stream:
            actual_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual_hash != entry["sha256"]:
            raise ValueError(f"Checksum mismatch: {expected_path}")

        print(f"Checksum verified: {expected_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=("validation", "dashboard"))
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root; defaults to this script's parent repository.",
    )
    arguments = parser.parse_args()
    try:
        if arguments.check == "validation":
            check_validation(arguments.root)
        else:
            check_dashboard(arguments.root)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

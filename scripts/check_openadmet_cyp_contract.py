"""Fail-closed drift check for the frozen OpenADMET TRACE R0 receipts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

DEFAULT_CONTRACT_DIR = (
    Path(__file__).resolve().parents[1] / "benchmarks" / "openadmet_cyp_2026"
)
SOURCES = ("dataset", "tutorial", "space")
JSON = dict[str, Any]


def _object(value: Any, label: str) -> JSON:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return cast(JSON, value)


def _text(value: JSON, key: str, label: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ValueError(f"{label}.{key} must be a non-empty string")
    return item


def _integer(value: JSON, key: str, label: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int):
        raise ValueError(f"{label}.{key} must be an integer")
    return item


def _strings(value: JSON, key: str, label: str) -> list[str]:
    item = value.get(key)
    if not isinstance(item, list) or not all(isinstance(part, str) for part in item):
        raise ValueError(f"{label}.{key} must be a string array")
    return cast(list[str], item)


def _load(path: Path, label: str) -> JSON:
    try:
        return _object(
            json.loads(path.read_text(encoding="utf-8")), f"{label} contract"
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label} contract JSON: {exc}") from exc


def _git_revision(root: Path, name: str, errors: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        errors.append(f"{name} revision unavailable")
        return None
    revision = result.stdout.strip()
    if result.returncode or not revision:
        errors.append(f"{name} revision unavailable")
        return None
    return revision


def _source_file(
    root: Path, name: str, entry: JSON, errors: list[str], counts: dict[str, int]
) -> None:
    relative = _text(entry, "path", f"source {name} file")
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(f"source {name} file.path must stay below its source root")
    label = f"{name}:{relative}"
    expected_size = _integer(entry, "size_bytes", label)
    expected_hash = _text(entry, "sha256", label)
    counts["selected_files"] += 1
    csv_file = relative_path.suffix.lower() == ".csv"
    if csv_file:
        counts["csv_files"] += 1
        expected_header = _strings(entry, "header", label)
        expected_rows = _integer(entry, "rows", label)
    path = root / relative_path
    try:
        if not path.is_file():
            errors.append(f"{label} missing")
            return
        data = path.read_bytes()
    except OSError:
        errors.append(f"{label} unreadable")
        return
    if len(data) != expected_size:
        errors.append(f"{label} size drift")
    if hashlib.sha256(data).hexdigest() != expected_hash:
        errors.append(f"{label} SHA-256 drift")
    if csv_file:
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.reader(handle)
                header = next(reader, None)
                rows = sum(1 for _ in reader)
        except (OSError, UnicodeError, csv.Error):
            errors.append(f"{label} CSV parse drift")
        else:
            if header != expected_header:
                errors.append(f"{label} CSV header drift")
            if rows != expected_rows:
                errors.append(f"{label} CSV row count drift")


def _html(
    sources: JSON, name: str, path: Path, errors: list[str], counts: dict[str, int]
) -> None:
    receipt = _object(sources.get(name), f"source_receipts.sources.{name}")
    size = _integer(receipt, "retrieved_size_bytes", f"source {name}")
    digest = _text(receipt, "retrieved_sha256", f"source {name}")
    counts["html_files"] += 1
    label = f"{name}_html"
    try:
        if not path.is_file():
            errors.append(f"{label} missing")
            return
        data = path.read_bytes()
    except OSError:
        errors.append(f"{label} unreadable")
        return
    if len(data) != size:
        errors.append(f"{label} size drift")
    if hashlib.sha256(data).hexdigest() != digest:
        errors.append(f"{label} SHA-256 drift")


def _contract_check(
    errors: list[str], counts: dict[str, int], label: str, passed: bool
) -> None:
    counts["contract_checks"] += 1
    errors.extend([f"internal contract mismatch: {label}"] if not passed else [])


def _internal(
    receipts: JSON,
    challenge: JSON,
    submission: JSON,
    errors: list[str],
    counts: dict[str, int],
) -> None:
    public = _object(challenge.get("public_submission"), "challenge.public_submission")
    shared = _object(submission.get("shared"), "submission.shared")
    rows = _integer(
        _object(public.get("row_count"), "challenge row_count"),
        "value",
        "challenge row_count",
    )
    _contract_check(
        errors,
        counts,
        "row count",
        rows == _integer(shared, "rows", "submission.shared"),
    )
    direct = _object(public.get("direct_columns"), "challenge direct_columns")
    submitted_direct = _object(
        submission.get("direct_inhibition"), "submission.direct_inhibition"
    )
    _contract_check(
        errors,
        counts,
        "direct ordered columns",
        _strings(direct, "ordered", "challenge direct_columns")
        == _strings(
            submitted_direct, "required_columns_ordered", "submission.direct_inhibition"
        ),
    )
    tdi = _object(public.get("tdi_columns"), "challenge tdi_columns")
    submitted_tdi = _object(submission.get("tdi"), "submission.tdi")
    challenge_names = _strings(tdi, "ordered", "challenge tdi_columns")
    submission_names = _strings(
        submitted_tdi, "required_column_names", "submission.tdi"
    )
    _contract_check(
        errors,
        counts,
        "TDI required column names",
        sorted(challenge_names) == sorted(submission_names)
        and len(set(submission_names)) == len(submission_names),
    )
    sources = _object(receipts.get("sources"), "source_receipts.sources")
    tutorial = _object(
        _object(sources.get("tutorial"), "source tutorial").get("schema_observations"),
        "source tutorial observations",
    )
    space = _object(
        _object(sources.get("space"), "source space").get("schema_observations"),
        "source space observations",
    )
    observed_tutorial = _strings(
        tutorial, "tdi_value_column_order", "source tutorial observations"
    )
    observed_space = _strings(
        space, "tdi_value_column_order", "source space observations"
    )
    identifiers = _strings(shared, "identifier_columns", "submission.shared")
    submission_space = _strings(submitted_tdi, "space_observed_order", "submission.tdi")
    submission_tutorial = _strings(
        submitted_tdi, "tutorial_observed_order", "submission.tdi"
    )
    order_ok = (
        submission_space == identifiers + observed_space
        and submission_tutorial == identifiers + observed_tutorial
        and submission_space != submission_tutorial
        and challenge_names in (submission_space, submission_tutorial)
        and sorted(submission_space) == sorted(submission_names)
        and sorted(submission_tutorial) == sorted(submission_names)
        and _text(tdi, "order_status", "challenge tdi").startswith("unresolved")
        and _text(submitted_tdi, "order_status", "submission.tdi").startswith(
            "unresolved"
        )
    )
    _contract_check(errors, counts, "TDI observed order discrepancy", order_ok)
    type_ok = (
        _text(direct, "encoding", "challenge direct_columns").startswith("numeric")
        and _text(tdi, "encoding", "challenge tdi_columns").startswith("boolean")
        and _text(submitted_direct, "prediction_type", "submission.direct_inhibition")
        == "numeric"
        and _text(submitted_tdi, "prediction_type", "submission.tdi") == "boolean"
    )
    _contract_check(errors, counts, "prediction types", type_ok)


def check(args: argparse.Namespace, contract_dir: Path) -> JSON:
    receipts = _load(contract_dir / "source_receipts.json", "source_receipts")
    challenge = _load(contract_dir / "challenge_contract.json", "challenge")
    submission = _load(contract_dir / "submission_contract.json", "submission")
    errors: list[str] = []
    counts = {
        "source_roots": 0,
        "selected_files": 0,
        "csv_files": 0,
        "html_files": 0,
        "contract_checks": 0,
        "errors": 0,
    }
    revisions: dict[str, str] = {}
    sources = _object(receipts.get("sources"), "source_receipts.sources")
    for name in SOURCES:
        source = _object(sources.get(name), f"source_receipts.sources.{name}")
        revision = _text(source, "revision", f"source {name}")
        entries = source.get("files")
        if not isinstance(entries, list):
            raise ValueError(f"source {name}.files must be an array")
        counts["source_roots"] += 1
        root = cast(Path, getattr(args, f"{name}_root"))
        actual = _git_revision(root, name, errors)
        if actual == revision:
            revisions[name] = actual
        elif actual is not None:
            errors.append(f"{name} revision drift: expected {revision}, got {actual}")
        for index, raw in enumerate(entries):
            _source_file(
                root,
                name,
                _object(raw, f"source {name}.files[{index}]"),
                errors,
                counts,
            )
    _html(sources, "announcement", args.announcement_html, errors, counts)
    _html(sources, "launch_post", args.launch_post_html, errors, counts)
    _internal(receipts, challenge, submission, errors, counts)
    errors = sorted(errors)
    counts["errors"] = len(errors)
    return {
        "schema_version": "cypshift.openadmet_cyp_2026.contract_checker.v1",
        "status": "pass" if not errors else "fail",
        "counts": counts,
        "verified_revisions": dict(sorted(revisions.items())),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset-root", "tutorial-root", "space-root"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--announcement-html", type=Path, required=True)
    parser.add_argument("--launch-post-html", type=Path, required=True)
    parser.add_argument("--contract-dir", type=Path, default=DEFAULT_CONTRACT_DIR)
    args = parser.parse_args()
    try:
        result = check(args, args.contract_dir.resolve())
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())

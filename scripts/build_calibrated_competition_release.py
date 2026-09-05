#!/usr/bin/env python3
"""Build an immutable interim direct challenger from evaluated OOF calibration.

No training targets, portal state or model fits are accessed. The frozen legacy
full-training predictions are transformed only by the supplied evaluated recipe.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from refresh_competition_sources import refresh

from cypshift.competition_submission import DIRECT_COLUMNS, validate_submission

ROOT = Path(__file__).resolve().parents[1]
BASELINE_SHA256 = "9d3ed5ff2ba08233caf99e46d4a0e69e59ab35a337521258a92ad21488db504b"
TEST_SHA256 = "a342f8444a8dcb531ca12f3685293f0bd6c36ae9073f491e44a9bc1cc4b741f9"


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _nonfinite(value: str) -> None:
    raise ValueError(f"Nonfinite JSON value: {value}")


def _json(raw: bytes) -> dict[str, Any]:
    value = json.loads(raw, parse_constant=_nonfinite)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def _private_destination(output: Path) -> Path:
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(
            "Release destination already exists; never overwrite a release"
        )
    resolved = output.resolve()
    if (
        ROOT == resolved
        or ROOT in resolved.parents
        or any((parent / ".git").exists() for parent in (resolved, *resolved.parents))
    ):
        raise ValueError("Release destination must stay outside Git")
    return resolved


def _finite_metric(value: Any, *, nonnegative: bool = False) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Evaluated metric must be a finite number")
    if nonnegative and value < 0:
        raise ValueError("Error metric cannot be negative")
    return float(value)


def _validate_evidence(
    result: dict[str, Any], names: list[str], groups: list[str]
) -> None:
    """Check evidence consistency without reopening targets or trusting a stale flag."""
    summaries = []
    populations = []
    for key in ("baseline", "candidate_scores"):
        scores = result.get(key)
        if not isinstance(scores, dict):
            raise ValueError(f"Missing evaluated evidence: {key}")
        if scores.get("bootstrap_samples") != 1000 or scores.get("bootstrap_seed") != 0:
            raise ValueError("Evidence does not use the frozen public bootstrap")
        primary = _finite_metric(
            scores.get("macro_bootstrap_mean_st_rae"), nonnegative=True
        )
        component = _finite_metric(scores.get("macro_component_mae"), nonnegative=True)
        endpoints = scores.get("endpoints")
        if not isinstance(endpoints, dict):
            raise ValueError("Missing endpoint evidence")
        endpoint_primary, endpoint_component, population = [], [], []
        for column in DIRECT_COLUMNS:
            endpoint = endpoints.get(column.split("_")[0])
            if not isinstance(endpoint, dict):
                raise ValueError("Missing endpoint evidence")
            rows, families = endpoint.get("rows"), endpoint.get("groups")
            if (
                type(rows) is not int
                or type(families) is not int
                or not 1 <= families <= min(rows, len(set(groups)))
                or not 2 <= rows <= len(names)
            ):
                raise ValueError("Invalid endpoint evaluation population")
            population.append((rows, families))
            endpoint_primary.append(
                _finite_metric(endpoint.get("bootstrap_mean_st_rae"), nonnegative=True)
            )
            endpoint_component.append(
                _finite_metric(endpoint.get("component_mae"), nonnegative=True)
            )
        if not math.isclose(
            primary, sum(endpoint_primary) / 4, rel_tol=1e-10, abs_tol=1e-12
        ) or not math.isclose(
            component, sum(endpoint_component) / 4, rel_tol=1e-10, abs_tol=1e-12
        ):
            raise ValueError("Macro evidence disagrees with endpoint evidence")
        summaries.append((primary, component))
        populations.append(population)
    if populations[0] != populations[1]:
        raise ValueError("Baseline and candidate evaluation populations differ")
    baseline, candidate = summaries
    if not (candidate[0] < baseline[0] or candidate[1] < baseline[1]):
        raise ValueError("Interim eligibility contradicts evaluated metrics")
    paired = result.get("paired_family")
    if not isinstance(paired, dict):
        raise ValueError("Missing paired family evidence")
    if (
        paired.get("samples") != 2000
        or paired.get("seed") != 20260906
        or paired.get("families") != len(set(groups))
    ):
        raise ValueError("Paired bootstrap contract or population differs")
    lower = _finite_metric(paired.get("lower_95"))
    upper = _finite_metric(paired.get("upper_95"))
    _finite_metric(paired.get("candidate_minus_baseline_mean"))
    if lower > upper:
        raise ValueError("Reversed paired family confidence interval")


def _validated_experiment(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[tuple[float, float]], dict[str, str]]:
    raw_result = (root / "result.json").read_bytes()
    result = _json(raw_result)
    if (
        result.get("status") != "complete"
        or result.get("candidate") != "maplight-inner-oof-affine"
        or result.get("decision", {}).get("release_eligible_on_paired_metrics")
        is not True
        or result.get("reserved_numeric_targets_opened") != 0
    ):
        raise ValueError("Experiment is not a complete eligible interim challenger")
    experiment_raw = (root / "experiment.json").read_bytes()
    oof_raw = (root / "oof.npz").read_bytes()
    if (
        _digest(experiment_raw) != result["experiment_sha256"]
        or _digest(oof_raw) != result["oof_sha256"]
    ):
        raise ValueError("Experiment or OOF receipt differs")
    experiment = _json(experiment_raw)
    names = experiment.get("molecule_ids")
    groups = experiment.get("groups")
    if (
        not isinstance(names, list)
        or not names
        or not all(isinstance(name, str) and name for name in names)
        or len(set(names)) != len(names)
        or not isinstance(groups, list)
        or len(groups) != len(names)
        or not all(isinstance(group, str) and group for group in groups)
    ):
        raise ValueError("Experiment development population is invalid")
    pairs = result.get("deployment_calibration")
    if not isinstance(pairs, list) or len(pairs) != 4:
        raise ValueError("Calibration must contain four slope/intercept pairs")
    calibration = []
    for pair in pairs:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(type(value) in (int, float) for value in pair)
        ):
            raise ValueError("Invalid calibration pair")
        slope, intercept = map(float, pair)
        if (
            not math.isfinite(slope)
            or not math.isfinite(intercept)
            or not 0.8 <= slope <= 1.2
            or not -0.25 <= intercept <= 0.25
        ):
            raise ValueError("Calibration exceeds the frozen bounds")
        calibration.append((slope, intercept))
    if all(pair == (1.0, 0.0) for pair in calibration):
        raise ValueError("Identity calibration is not an additional entry")
    _validate_evidence(result, names, groups)
    return (
        result,
        experiment,
        calibration,
        {
            "result.json": _digest(raw_result),
            "experiment.json": _digest(experiment_raw),
            "oof.npz": _digest(oof_raw),
        },
    )


def _publish_readonly(path: Path, raw: bytes) -> None:
    temporary = path.with_name("." + path.name + ".partial")
    with temporary.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.chmod(0o444)
    os.link(
        temporary, path
    )  # Atomic visibility; an existing final file is never replaced.
    temporary.unlink()


def build_release(
    experiment_root: Path, test_csv: Path, baseline_csv: Path, output: Path
) -> dict[str, Any]:
    output = _private_destination(output)
    result, experiment, calibration, hashes = _validated_experiment(experiment_root)
    baseline_raw, test_raw = baseline_csv.read_bytes(), test_csv.read_bytes()
    if _digest(baseline_raw) != BASELINE_SHA256:
        raise ValueError("Accepted full-training baseline receipt differs")
    validate_submission(
        test_raw, baseline_raw, "direct", expected_test_sha256=TEST_SHA256
    )
    rows = list(csv.reader(io.StringIO(baseline_raw.decode("utf-8"))))
    changed = False
    for row in rows[1:]:
        for column, (slope, intercept) in enumerate(calibration, 2):
            before = float(row[column])
            after = slope * before + intercept
            changed |= after != before
            row[column] = format(after, ".17g")
    if not changed:
        raise ValueError("Calibration produces no new numerical predictions")
    stream = io.StringIO()
    csv.writer(stream, lineterminator="\n").writerows(rows)
    submission_raw = stream.getvalue().encode("utf-8")
    receipt = validate_submission(
        test_raw, submission_raw, "direct", expected_test_sha256=TEST_SHA256
    )
    sources = refresh()
    manifest = {
        "schema": "cypshift.phase3.calibrated_direct_release.v1",
        "status": "ready_for_manual_submission",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "track": "direct",
        "candidate": result["candidate"],
        "interim_challenger": True,
        "final_recommendation": False,
        "submitted": False,
        "current_recommendation": "authenticated fixed MapLight baseline",
        "deployment_calibration": dict(zip(DIRECT_COLUMNS, calibration, strict=True)),
        "baseline_full_training_molecules": 4905,
        "calibration_development_molecules": len(experiment["molecule_ids"]),
        "calibration_development_families": len(set(experiment["groups"])),
        "design_limitation": (
            "Calibration was fitted to development-only out-of-fold predictions "
            "(original development partition: 3908 molecules before any family "
            "quarantine) and transferred to an authenticated baseline trained on "
            "all 4905 official molecules. This training-size transfer is not itself "
            "evaluated by nested OOF. Reserved targets were not opened for calibration "
            "or selection; this is not a final promoted model."
        ),
        "manual_submission_note": (
            "The latest valid entry replaces the previous direct entry; honor the "
            "12-hour per-track interval. Readiness is not proof of submission."
        ),
        "baseline_scores": result["baseline"],
        "candidate_scores": result["candidate_scores"],
        "paired_family": result["paired_family"],
        "decision": result["decision"],
        "input_hashes": {
            **hashes,
            "baseline_submission.csv": BASELINE_SHA256,
            "blinded_test.csv": TEST_SHA256,
        },
        "implementation_hashes": {
            "release_builder": _digest(Path(__file__).read_bytes()),
            "public_source_refresher": _digest(
                Path(__file__).with_name("refresh_competition_sources.py").read_bytes()
            ),
            "submission_validator": _digest(
                (ROOT / "src/cypshift/competition_submission.py").read_bytes()
            ),
        },
        "experiment_implementation": experiment.get("implementation", {}),
        "source_refresh": sources,
        "validation": asdict(receipt),
        "output_hashes": {"submission.csv": _digest(submission_raw)},
    }
    manifest_raw = (
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(
        mode=0o700
    )  # Reserve this attempt atomically, never reuse an old root.
    _publish_readonly(output / "submission.csv", submission_raw)
    # Manifest is the completion marker: a failed partial root is never handed off.
    _publish_readonly(output / "manifest.json", manifest_raw)
    output.chmod(0o555)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True, type=Path)
    parser.add_argument("--test-csv", required=True, type=Path)
    parser.add_argument("--baseline-csv", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = build_release(
        args.experiment, args.test_csv, args.baseline_csv, args.output
    )
    print(
        json.dumps(
            {
                "submission": str(args.output.resolve() / "submission.csv"),
                "submission_sha256": manifest["output_hashes"]["submission.csv"],
                "status": manifest["status"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

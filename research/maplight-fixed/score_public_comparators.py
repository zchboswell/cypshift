"""Score both frozen MapLight public comparator families exactly once."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(__file__).resolve()
PREDICTION_ROOTS = {
    3: ROOT / "artifacts/benchmarks/maplight-public-predictions-v1-attempt-3",
    4: ROOT / "artifacts/benchmarks/maplight-public-predictions-v1-attempt-4",
}
PREDICTION_MANIFEST_SHA256 = {
    3: "014ebbead0020d76a8143d96e86b5ba6c5109e964ae1bf0a0bd8c21fc7f152ef",
    4: "e8e65e7d0a9143d5cd9a46748f93f84ecbbfd0ae501294027b7e0e8f55917728",
}
PREDICTION_SOURCE_REVISION = "d1c68bf91dae9f5e7029e3af94935a6bc13d519c"
PREDICTION_IMPLEMENTATION_SHA256 = (
    "5bfdd7d6af26f51e878548848f2b0ed77972698c0701bdadae36d5a4699601a0"
)
PUBLIC_ROWS_SHA256 = "5b892811c6615ee040d777c854505d635d713586b3461d9b0faa488535e514d2"
MEASUREMENTS_PATH = (
    ROOT / "artifacts/benchmarks/tdc-source-freeze-v2/canonical/measurements.csv"
)
MEASUREMENTS_SHA256 = "6d9e50bf114256d72ef9efcbeeed31af80aaedc2e7a7676be4d21a094525c53b"
BUDGET_PATH = ROOT / "benchmarks/phase_0_75_evaluation_budget.json"
BUDGET_SHA256 = "fa5463b7fcc5aabecf786f42757f60ba6509aa3ce144c6a2ab4a8c1883408750"
OUTPUT_ROOT = ROOT / "artifacts/benchmarks/maplight-public-scorecard-v1"
BLOCKER_ROOT = ROOT / "artifacts/blockers/maplight-public-scorecard-v1-blocker"

TASKS = ("cyp2c9_veith", "cyp2d6_veith", "cyp3a4_veith")
TASK_ROWS = {"cyp2c9_veith": 2419, "cyp2d6_veith": 2626, "cyp3a4_veith": 2467}
MEASUREMENT_ROWS = 37550
FAMILIES = ("maplight_fixed", "maplight_gin")
PREDICTION_COLUMNS = tuple(f"prediction_seed_{seed}" for seed in range(1, 6)) + (
    "prediction_probability_mean",
)
IDENTITY_COLUMNS = (
    "task",
    "molecule_id",
    "source_row",
    "raw_structure_sha256",
    "standardized_structure_sha256",
)
PREDICTION_FILE_COLUMNS = IDENTITY_COLUMNS + PREDICTION_COLUMNS
EXPECTED_PREDICTION_FILES = {
    "avalon_count.npy",
    "erg.npy",
    "gin.npy",
    "gin_worker_receipt.json",
    "morgan_count.npy",
    "prediction_manifest.json",
    "public_rows.csv",
    "rdkit_descriptors.npy",
    *(f"{family}__{task}.csv" for family in FAMILIES for task in TASKS),
}
PUBLIC_ROW_COLUMNS = (
    "task",
    "molecule_id",
    "source_row",
    "raw_structure",
    "raw_structure_sha256",
    "standardized_structure",
    "standardized_structure_sha256",
    "standardization_version",
)
MEASUREMENT_COLUMNS = (
    "measurement_id",
    "molecule_id",
    "endpoint",
    "isoform",
    "nadph_condition",
    "probe",
    "readout",
    "value",
    "lower_bound",
    "upper_bound",
    "censoring",
    "unit",
    "quality",
    "source",
    "provenance",
)
ISOFORM_BY_TASK = {
    "cyp2c9_veith": "CYP2C9",
    "cyp2d6_veith": "CYP2D6",
    "cyp3a4_veith": "CYP3A4",
}
ANCHORS = {
    "maplight_fixed": {
        "cyp2c9_veith": (0.783, 0.002),
        "cyp2d6_veith": (0.723, 0.003),
        "cyp3a4_veith": (0.881, 0.001),
    },
    "maplight_gin": {
        "cyp2c9_veith": (0.859, 0.001),
        "cyp2d6_veith": (0.790, 0.001),
        "cyp3a4_veith": (0.916, 0.000),
    },
}
METRIC_COLUMNS = (
    "family",
    "task",
    "prediction_column",
    "statistic",
    "auprc",
    "auprc_rounded_3",
)
SCORECARD_COLUMNS = (
    "family",
    "task",
    "seed_metric_mean",
    "seed_metric_std_population",
    "probability_mean_auprc",
    "published_mean",
    "published_std",
    "mean_minus_published",
    "reproduction_status",
)
CLAIM = (
    "Bounded public-benchmark confirmation on an already-observed TDC public test; "
    "not blind external validation, challenge evidence, or authority for repair."
)


class PublicScoringError(RuntimeError):
    """Fail-closed public comparator scoring error."""


class ForensicGateTriggered(PublicScoringError):
    """Stop immediately when a completed public AUPRC reaches 0.95."""

    def __init__(self, family: str, task: str, column: str, score: float) -> None:
        self.family = family
        self.task = task
        self.column = column
        self.score = score
        super().__init__(f"0.95 forensic gate: {family}/{task}/{column}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PublicScoringError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"JSON root differs: {path}")
    return cast(dict[str, Any], value)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _read_csv(path: Path, columns: Sequence[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _require(
            tuple(reader.fieldnames or ()) == tuple(columns), f"columns differ: {path}"
        )
        rows = [dict(row) for row in reader]
    _require(all(None not in row for row in rows), f"row width differs: {path}")
    return rows


def _write_csv(
    path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, object]]
) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _git(arguments: Sequence[str]) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _clean_revision() -> str:
    _require(not _git(("status", "--porcelain", "--untracked-files=all")), "dirty tree")
    revision = _git(("rev-parse", "HEAD"))
    identity = _git(
        ("show", "-s", "--format=%G?%x00%an%x00%ae%x00%cn%x00%ce", revision)
    ).split("\0")
    _require(
        identity
        == [
            "G",
            "zchboswell",
            "261114960+zchboswell@users.noreply.github.com",
            "zchboswell",
            "261114960+zchboswell@users.noreply.github.com",
        ],
        "signature or authorship differs",
    )
    blob = subprocess.run(
        ["git", "show", f"{revision}:{SCRIPT_PATH.relative_to(ROOT).as_posix()}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    _require(hashlib.sha256(blob).hexdigest() == _sha256(SCRIPT_PATH), "script differs")
    return revision


def _readonly(path: Path) -> bool:
    return not bool(
        os.stat(path).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    )


def _make_readonly(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)


def _remove(root: Path) -> None:
    if root.exists():
        for path in root.rglob("*"):
            path.chmod(0o755 if path.is_dir() else 0o644)
        root.chmod(0o755)
        shutil.rmtree(root)


def _verify_prediction_roots() -> tuple[list[dict[str, str]], dict[str, str]]:
    _require(_sha256(BUDGET_PATH) == BUDGET_SHA256, "evaluation budget differs")
    payload_hashes: dict[int, dict[str, str]] = {}
    manifests: dict[int, dict[str, Any]] = {}
    for attempt, root in PREDICTION_ROOTS.items():
        _require(root.is_dir() and _readonly(root), "prediction root differs")
        _require(
            {path.name for path in root.iterdir()} == EXPECTED_PREDICTION_FILES,
            "prediction file set differs",
        )
        _require(
            all(path.is_file() and _readonly(path) for path in root.iterdir()),
            "prediction file mode differs",
        )
        manifest_path = root / "prediction_manifest.json"
        _require(
            _sha256(manifest_path) == PREDICTION_MANIFEST_SHA256[attempt],
            "prediction manifest differs",
        )
        manifest = _json(manifest_path)
        _require(
            manifest["source_revision"] == PREDICTION_SOURCE_REVISION,
            "prediction source differs",
        )
        _require(
            manifest["implementation_sha256"] == PREDICTION_IMPLEMENTATION_SHA256,
            "prediction implementation differs",
        )
        accounting = manifest["accounting"]
        _require(
            accounting["public_test_labels_parsed"] == 0
            and accounting["metric_evaluations"] == 0
            and accounting["canonical_family_task_artifacts"] == 6
            and accounting["public_test_family_task_slots_consumed"] == 6,
            "prediction chronology differs",
        )
        payload_hashes[attempt] = {
            path.name: _sha256(path)
            for path in sorted(root.iterdir())
            if path.name != "prediction_manifest.json"
        }
        manifests[attempt] = manifest
    _require(payload_hashes[3] == payload_hashes[4], "prediction repeat differs")
    _require(
        manifests[3]["accounting"]["additional_family_task_slots_consumed_this_attempt"]
        == 6
        and manifests[4]["accounting"][
            "additional_family_task_slots_consumed_this_attempt"
        ]
        == 0,
        "prediction slot accounting differs",
    )
    root = PREDICTION_ROOTS[3]
    public_rows = _read_csv(root / "public_rows.csv", PUBLIC_ROW_COLUMNS)
    _require(len(public_rows) == 7512, "public row population differs")
    _require(
        _sha256(root / "public_rows.csv") == PUBLIC_ROWS_SHA256, "public rows differ"
    )
    identities = {
        (row["task"], row["molecule_id"], row["source_row"]) for row in public_rows
    }
    _require(len(identities) == len(public_rows), "public identity duplicates")
    predictions: dict[str, str] = {}
    for family in FAMILIES:
        for task in TASKS:
            name = f"{family}__{task}.csv"
            rows = _read_csv(root / name, PREDICTION_FILE_COLUMNS)
            expected = [row for row in public_rows if row["task"] == task]
            _require(
                len(rows) == TASK_ROWS[task] == len(expected), "task population differs"
            )
            _require(
                [tuple(row[column] for column in IDENTITY_COLUMNS) for row in rows]
                == [
                    (
                        row["task"],
                        row["molecule_id"],
                        row["source_row"],
                        row["raw_structure_sha256"],
                        row["standardized_structure_sha256"],
                    )
                    for row in expected
                ],
                "prediction row alignment differs",
            )
            values = np.asarray(
                [[float(row[column]) for column in PREDICTION_COLUMNS] for row in rows],
                dtype=np.float64,
            )
            _require(
                np.isfinite(values).all() and ((0 <= values) & (values <= 1)).all(),
                "prediction range differs",
            )
            _require(
                np.array_equal(
                    values[:, -1], np.mean(values[:, :5], axis=1, dtype=np.float64)
                ),
                "prediction mean differs",
            )
            predictions[name] = payload_hashes[3][name]
    return public_rows, predictions


def _load_public_targets(
    public_rows: Sequence[Mapping[str, str]], accounting: dict[str, int]
) -> tuple[dict[str, int], int]:
    _require(_sha256(MEASUREMENTS_PATH) == MEASUREMENTS_SHA256, "measurements differ")
    _require(_readonly(MEASUREMENTS_PATH), "measurement source is writable")
    expected = {row["molecule_id"]: row["task"] for row in public_rows}
    _require(len(expected) == len(public_rows), "public molecule identities differ")
    targets: dict[str, int] = {}
    traversed = 0
    with MEASUREMENTS_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        _require(
            tuple(next(reader)) == MEASUREMENT_COLUMNS, "measurement columns differ"
        )
        molecule_index = MEASUREMENT_COLUMNS.index("molecule_id")
        endpoint_index = MEASUREMENT_COLUMNS.index("endpoint")
        isoform_index = MEASUREMENT_COLUMNS.index("isoform")
        readout_index = MEASUREMENT_COLUMNS.index("readout")
        value_index = MEASUREMENT_COLUMNS.index("value")
        for fields in reader:
            traversed += 1
            accounting["measurement_rows_traversed"] += 1
            _require(
                len(fields) == len(MEASUREMENT_COLUMNS), "measurement row width differs"
            )
            molecule_id = fields[molecule_index]
            task = expected.get(molecule_id)
            if task is None:
                continue
            _require(molecule_id not in targets, "public measurement duplicate")
            _require(
                fields[endpoint_index] == "binary_inhibition_veith"
                and fields[isoform_index] == ISOFORM_BY_TASK[task]
                and fields[readout_index] == "binary_label",
                "public measurement semantics differ",
            )
            value = float(fields[value_index])
            accounting["public_test_labels_parsed"] += 1
            _require(value in (0.0, 1.0), "public label polarity differs")
            targets[molecule_id] = int(value)
    _require(traversed == MEASUREMENT_ROWS, "measurement population differs")
    _require(set(targets) == set(expected), "public target identity set differs")
    return targets, traversed


def _reproduction_status(delta: float) -> str:
    difference = abs(delta)
    if difference <= 0.005:
        return "reproduced_within_0.005"
    if difference <= 0.010:
        return "outside_preferred_tolerance_0.005_to_0.010"
    return "reproduction_blocker_over_0.010"


def _average_precision() -> Callable[[np.ndarray, np.ndarray], float]:
    module = __import__("sklearn.metrics", fromlist=["average_precision_score"])
    return cast(
        Callable[[np.ndarray, np.ndarray], float], module.average_precision_score
    )


def _seed_summary(values: Sequence[float]) -> tuple[float, float]:
    _require(len(values) == 5, "seed metric count differs")
    rounded = np.asarray([round(value, 3) for value in values], dtype=np.float64)
    return (
        round(float(np.mean(rounded, dtype=np.float64)), 3),
        round(float(np.std(rounded, ddof=0, dtype=np.float64)), 3),
    )


def _score(
    targets: Mapping[str, int], accounting: dict[str, int]
) -> tuple[list[dict[str, object]], list[dict[str, object]], float]:
    average_precision_score = _average_precision()
    metric_rows: list[dict[str, object]] = []
    scorecard: list[dict[str, object]] = []
    maximum = 0.0
    root = PREDICTION_ROOTS[3]
    for family in FAMILIES:
        for task in TASKS:
            rows = _read_csv(root / f"{family}__{task}.csv", PREDICTION_FILE_COLUMNS)
            y = np.asarray([targets[row["molecule_id"]] for row in rows], dtype=np.int8)
            _require(set(y.tolist()) == {0, 1}, "public class support differs")
            values: dict[str, float] = {}
            for column in PREDICTION_COLUMNS:
                probability = np.asarray(
                    [float(row[column]) for row in rows], dtype=np.float64
                )
                score = float(average_precision_score(y, probability))
                accounting["public_test_primary_metric_evaluations"] += 1
                _require(np.isfinite(score) and 0 <= score <= 1, "public AUPRC differs")
                if score >= 0.95:
                    raise ForensicGateTriggered(family, task, column, score)
                maximum = max(maximum, score)
                values[column] = score
                metric_rows.append(
                    {
                        "family": family,
                        "task": task,
                        "prediction_column": column,
                        "statistic": "seed_metric"
                        if column != "prediction_probability_mean"
                        else "local_probability_mean",
                        "auprc": repr(score),
                        "auprc_rounded_3": repr(round(score, 3)),
                    }
                )
            seed_mean, seed_std = _seed_summary(
                [values[f"prediction_seed_{seed}"] for seed in range(1, 6)]
            )
            published_mean, published_std = ANCHORS[family][task]
            delta = seed_mean - published_mean
            scorecard.append(
                {
                    "family": family,
                    "task": task,
                    "seed_metric_mean": repr(seed_mean),
                    "seed_metric_std_population": repr(seed_std),
                    "probability_mean_auprc": repr(
                        values["prediction_probability_mean"]
                    ),
                    "published_mean": repr(published_mean),
                    "published_std": repr(published_std),
                    "mean_minus_published": repr(delta),
                    "reproduction_status": _reproduction_status(delta),
                }
            )
    _require(len(metric_rows) == 36 and len(scorecard) == 6, "metric budget differs")
    return metric_rows, scorecard, maximum


def run_scoring() -> Path:
    _require(
        not OUTPUT_ROOT.exists() and not BLOCKER_ROOT.exists(), "score output exists"
    )
    revision: str | None = None
    accounting = {
        "measurement_rows_traversed": 0,
        "public_test_labels_parsed": 0,
        "public_test_primary_metric_evaluations": 0,
    }
    staging: Path | None = None
    start = time.perf_counter()
    try:
        revision = _clean_revision()
        public_rows, prediction_hashes = _verify_prediction_roots()
        targets, measurements_traversed = _load_public_targets(public_rows, accounting)
        _require(
            accounting["public_test_labels_parsed"] == len(targets),
            "public label accounting differs",
        )
        metric_rows, scorecard, maximum = _score(targets, accounting)
        _require(
            accounting["public_test_primary_metric_evaluations"] == len(metric_rows),
            "public metric accounting differs",
        )
        staging = Path(
            tempfile.mkdtemp(
                prefix=".maplight-public-scorecard-", dir=OUTPUT_ROOT.parent
            )
        )
        _write_csv(staging / "metric_rows.csv", METRIC_COLUMNS, metric_rows)
        _write_csv(staging / "public_scorecard.csv", SCORECARD_COLUMNS, scorecard)
        _require(
            len(_read_csv(staging / "metric_rows.csv", METRIC_COLUMNS)) == 36,
            "retained metric rows differ",
        )
        _require(
            len(_read_csv(staging / "public_scorecard.csv", SCORECARD_COLUMNS)) == 6,
            "retained scorecard rows differ",
        )
        manifest = {
            "schema_version": "cypshift.maplight_public_scorecard.v1",
            "source_revision": revision,
            "implementation_sha256": _sha256(SCRIPT_PATH),
            "inputs": {
                "prediction_source_revision": PREDICTION_SOURCE_REVISION,
                "prediction_manifests": PREDICTION_MANIFEST_SHA256,
                "prediction_payloads": prediction_hashes,
                "public_rows_sha256": PUBLIC_ROWS_SHA256,
                "measurements_sha256": MEASUREMENTS_SHA256,
                "evaluation_budget_sha256": BUDGET_SHA256,
            },
            "outputs": {
                "metric_rows.csv": _sha256(staging / "metric_rows.csv"),
                "public_scorecard.csv": _sha256(staging / "public_scorecard.csv"),
            },
            "accounting": {
                "measurement_rows_traversed": measurements_traversed,
                "public_test_labels_parsed": accounting["public_test_labels_parsed"],
                "public_test_primary_metric_evaluations": accounting[
                    "public_test_primary_metric_evaluations"
                ],
                "public_test_diagnostic_metric_evaluations": 0,
                "public_test_family_task_slots_consumed": 6,
                "third_family_task_slots_consumed": 0,
                "model_fits": 0,
                "predictions_generated": 0,
                "challenge_assumptions_added": 0,
            },
            "maximum_auprc": maximum,
            "forensic_gate_triggered": maximum >= 0.95,
            "runtime_seconds": time.perf_counter() - start,
            "claim_boundary": CLAIM,
        }
        (staging / "score_manifest.json").write_bytes(_json_bytes(manifest))
        _require(
            _sha256(MEASUREMENTS_PATH) == MEASUREMENTS_SHA256,
            "measurements changed during scoring",
        )
        _require(_clean_revision() == revision, "source changed during scoring")
        _make_readonly(staging)
        staging.rename(OUTPUT_ROOT)
        return OUTPUT_ROOT
    except Exception as error:
        if staging is not None:
            _remove(staging)
        BLOCKER_ROOT.mkdir(parents=True, exist_ok=False)
        failure: dict[str, object] = {
            "kind": type(error).__name__,
            "message": str(error),
        }
        if isinstance(error, ForensicGateTriggered):
            failure["forensic_gate"] = {
                "family": error.family,
                "task": error.task,
                "prediction_column": error.column,
                "auprc": error.score,
            }
        receipt = {
            "schema_version": "cypshift.maplight_public_scoring_failure.v1",
            "source_revision": revision,
            "implementation_sha256": _sha256(SCRIPT_PATH),
            "prediction_manifests": PREDICTION_MANIFEST_SHA256,
            "measurements_sha256": MEASUREMENTS_SHA256,
            "failure": failure,
            "accounting": {
                "measurement_rows_traversed": accounting["measurement_rows_traversed"],
                "public_test_labels_parsed": accounting["public_test_labels_parsed"],
                "public_test_primary_metric_evaluations": accounting[
                    "public_test_primary_metric_evaluations"
                ],
                "public_test_diagnostic_metric_evaluations": 0,
                "model_fits": 0,
                "predictions_generated": 0,
                "challenge_assumptions_added": 0,
            },
            "claim_boundary": CLAIM,
        }
        (BLOCKER_ROOT / "failure_receipt.json").write_bytes(_json_bytes(receipt))
        _make_readonly(BLOCKER_ROOT)
        raise


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--score", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments(argv)
    _require(args.score, "--score is required")
    print(run_scoring())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

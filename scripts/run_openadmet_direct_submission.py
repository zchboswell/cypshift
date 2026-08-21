#!/usr/bin/env python3
"""Build one frozen full-train fixed-MapLight direct submission."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import math
import platform
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNNER = Path(__file__).resolve()
CONTRACT = (
    ROOT / "benchmarks/openadmet_cyp_2026/direct_maplight_deployment_contract.json"
)
RESEARCH_ROOT = ROOT / "research/maplight-fixed"
FEATURE_KERNEL = RESEARCH_ROOT / "maplight_fixed_features.py"
PARAMETER_SOURCE = RESEARCH_ROOT / "r3b_cell_io.py"
VALIDATOR = ROOT / "scripts/validate_openadmet_direct_submission.py"
SCHEMA = "cypshift.openadmet_cyp_2026.direct_maplight_deployment.v1"
ENDPOINTS = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
FEATURE_ROW_COLUMNS = (
    "molecule_id",
    "raw_structure_sha256",
    "standardized_structure_hash",
    "similarity_component_hash",
)
TEST_CHEMISTRY_COLUMNS = ("row_index", "raw_smiles", "raw_structure_sha256")
FeatureProcess = Callable[[Path, Path, Mapping[str, Any], str], None]
ModelFactory = Callable[[Mapping[str, Any]], Any]


class DirectDeploymentError(RuntimeError):
    """A deployment input, fit, or publication gate failed."""


@dataclass(frozen=True, slots=True)
class DirectDeploymentResult:
    output_root: Path
    submission_sha256: str
    manifest_sha256: str


@dataclass(frozen=True, slots=True)
class DirectAcceptanceResult:
    accepted_root: Path
    submission_sha256: str
    manifest_sha256: str


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DirectDeploymentError(message)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    )


def _file(path: Path, label: str, digest: str | None = None) -> bytes:
    _require(path.is_file() and not path.is_symlink(), f"{label} is not regular")
    _require(
        not any(parent.is_symlink() for parent in path.absolute().parents),
        f"{label} has a symlinked ancestor",
    )
    data = path.read_bytes()
    _require(digest is None or _sha(data) == digest, f"{label} receipt differs")
    return data


def _json(data: bytes, label: str) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in items:
            _require(key not in value, f"{label} has a duplicate key")
            value[key] = item
        return value

    try:
        value = json.loads(data.decode(), object_pairs_hook=pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DirectDeploymentError(f"{label} is invalid JSON") from exc
    _require(isinstance(value, dict), f"{label} root differs")
    return cast(dict[str, Any], value)


def _rows(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    try:
        reader = csv.DictReader(io.StringIO(data.decode(), newline=""), strict=True)
        _require(
            tuple(reader.fieldnames or ()) == tuple(columns), f"{label} schema differs"
        )
        raw = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise DirectDeploymentError(f"{label} is invalid CSV") from exc
    _require(
        all(None not in row and None not in row.values() for row in raw),
        f"{label} row differs",
    )
    return [{str(key): str(value) for key, value in row.items()} for row in raw]


def _module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise DirectDeploymentError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_contract(expected_sha: str) -> tuple[dict[str, Any], str, ModuleType]:
    raw = _file(CONTRACT, "deployment contract", expected_sha)
    contract = _json(raw, "deployment contract")
    _require(contract.get("schema_version") == SCHEMA, "deployment schema differs")
    implementation = contract["implementation"]
    receipts = (
        (RUNNER, implementation["runner_sha256"], "runner"),
        (VALIDATOR, implementation["validator_sha256"], "validator"),
        (
            PARAMETER_SOURCE,
            implementation["parameter_source_sha256"],
            "parameter source",
        ),
        (
            FEATURE_KERNEL,
            contract["features"]["kernel"]["sha256"],
            "feature kernel",
        ),
        (
            ROOT / contract["runtime"]["lock_path"],
            contract["runtime"]["lock_sha256"],
            "runtime lock",
        ),
    )
    for path, digest, label in receipts:
        _file(path, label, str(digest))
    for receipt in contract["parents"].values():
        _file(ROOT / receipt["path"], "parent contract", receipt["sha256"])
    helper = _module(PARAMETER_SOURCE, "direct_maplight_runtime_helper")
    _require(
        helper.CATBOOST_ARGS == contract["model"]["constructor_arguments"],
        "model arguments differ",
    )
    return contract, _sha(raw), helper


def _runtime(contract: Mapping[str, Any]) -> dict[str, str]:
    expected = contract["runtime"]
    observed = {
        "python": platform.python_version(),
        "platform": platform.system(),
        "machine": platform.machine(),
        **{name: importlib.metadata.version(name) for name in expected["packages"]},
    }
    required = {
        "python": expected["python"],
        "platform": expected["platform"],
        "machine": expected["machine"],
        **expected["packages"],
    }
    _require(observed == required, "locked MapLight runtime differs")
    return {str(key): str(value) for key, value in observed.items()}


def _outside_git(path: Path, label: str) -> None:
    resolved, repository = path.resolve(strict=False), ROOT.resolve()
    _require(
        resolved != repository and repository not in resolved.parents,
        f"{label} must remain outside Git",
    )


def _accepted_root(contract: Mapping[str, Any]) -> Path:
    submission = contract.get("submission")
    _require(isinstance(submission, Mapping), "submission contract differs")
    submission_map = cast(Mapping[str, Any], submission)
    accepted = submission_map.get("accepted_path")
    _require(
        isinstance(accepted, str)
        and Path(accepted).is_absolute()
        and Path(accepted).name == "submission.csv"
        and Path(accepted).parent.name == "accepted"
        and submission_map.get("terminal_files") == ["submission.csv", "manifest.json"],
        "accepted destination semantics differ",
    )
    return Path(cast(str, accepted)).parent


def _training_features(
    root: Path, contract: Mapping[str, Any], helper: ModuleType, synthetic: bool
) -> tuple[list[dict[str, str]], np.ndarray[Any, Any]]:
    frozen = contract["features"]["training_root"]
    _, rows, arrays, _ = helper._load_feature_root(
        root, frozen["manifest_sha256"], synthetic=synthetic
    )
    blocks = [arrays[name] for name, _, _ in contract["features"]["ordered_blocks"]]
    matrix = np.ascontiguousarray(np.concatenate(blocks, axis=1), dtype=np.float64)
    _require(
        matrix.shape == (frozen["rows"], contract["features"]["columns"]),
        "training feature matrix differs",
    )
    return rows, matrix


def _targets(
    path: Path,
    feature_rows: Sequence[Mapping[str, str]],
    contract: Mapping[str, Any],
    production: bool,
) -> dict[str, tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]]:
    spec = contract["training"]
    data = _file(
        path,
        "direct observations",
        spec["observations_sha256"] if production else None,
    )
    rows = _rows(data, spec["observation_columns"], "direct observations")
    _require(len(rows) == spec["observation_rows"], "observation count differs")
    by_id = {row["molecule_id"]: index for index, row in enumerate(feature_rows)}
    raw_hash = {row["molecule_id"]: row["raw_structure_sha256"] for row in feature_rows}
    points: dict[str, dict[int, float]] = {endpoint: {} for endpoint in ENDPOINTS}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        molecule, endpoint = row["molecule_id"], row["endpoint"]
        key = (molecule, endpoint)
        _require(
            molecule in by_id
            and endpoint in ENDPOINTS
            and key not in seen
            and row["source_file"] == spec["source_file"]
            and row["source_sha256"] == spec["source_sha256"]
            and row["raw_structure_sha256"] == raw_hash[molecule]
            and _sha(row["raw_smiles"].encode()) == raw_hash[molecule],
            "observation identity differs",
        )
        seen.add(key)
        _require(
            row["point_eligible"] in ("true", "false"),
            "point eligibility differs",
        )
        if row["point_eligible"] == "true":
            try:
                point = float(row["point"])
            except ValueError as exc:
                raise DirectDeploymentError("eligible point is nonnumeric") from exc
            _require(
                math.isfinite(point) and row["point"] == format(point, ".17g"),
                "eligible point differs",
            )
            points[endpoint][by_id[molecule]] = point
        else:
            _require(row["point"] == "", "ineligible point is populated")
    _require(len(seen) == len(feature_rows) * 4, "observation coverage differs")
    _require(
        {key: len(value) for key, value in points.items()} == spec["eligible_points"],
        "endpoint counts differ",
    )
    return {
        endpoint: (
            np.asarray(sorted(points[endpoint])),
            np.asarray(
                [points[endpoint][index] for index in sorted(points[endpoint])],
                dtype=np.float64,
            ),
        )
        for endpoint in ENDPOINTS
    }


def _test_rows(
    path: Path, contract: Mapping[str, Any], production: bool
) -> tuple[bytes, list[dict[str, str]]]:
    spec = contract["test"]
    data = _file(path, "blinded test", spec["source_sha256"] if production else None)
    rows = _rows(data, spec["columns"], "blinded test")
    names = [row["Molecule_Name"] for row in rows]
    _require(
        len(rows) == spec["rows"]
        and len(names) == len(set(names))
        and all(name and row["SMILES"] for name, row in zip(names, rows, strict=True)),
        "blinded-test identity differs",
    )
    return data, rows


def _project_test(
    root: Path,
    rows: Sequence[Mapping[str, str]],
    contract: Mapping[str, Any],
    contract_sha: str,
    helper: ModuleType,
) -> None:
    root.mkdir()
    projected = [
        {
            "row_index": index,
            "raw_smiles": row["SMILES"],
            "raw_structure_sha256": _sha(row["SMILES"].encode()),
        }
        for index, row in enumerate(rows)
    ]
    csv_data = helper._csv_bytes(TEST_CHEMISTRY_COLUMNS, projected)
    (root / "test_chemistry.csv").write_bytes(csv_data)
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.direct_test_chemistry.v1",
        "contract_sha256": contract_sha,
        "test_source_sha256": contract["test"]["source_sha256"],
        "rows": len(rows),
        "csv_sha256": _sha(csv_data),
        "accounting": {
            "raw_smiles": len(rows),
            "targets": 0,
            "relationships": 0,
        },
    }
    (root / "manifest.json").write_bytes(helper._json_bytes(manifest))
    helper._readonly_tree(root)


def _feature_worker(
    projection: Path,
    output: Path,
    contract: Mapping[str, Any],
    contract_sha: str,
    helper: ModuleType,
) -> None:
    helper._require_readonly_root(projection, "test chemistry projection differs")
    manifest, manifest_raw = helper._read_json(projection / "manifest.json")
    _require(
        manifest.get("schema_version")
        == "cypshift.openadmet_cyp_2026.direct_test_chemistry.v1"
        and manifest.get("contract_sha256") == contract_sha,
        "test chemistry manifest differs",
    )
    data = _file(
        projection / "test_chemistry.csv",
        "test chemistry",
        manifest["csv_sha256"],
    )
    rows = _rows(data, TEST_CHEMISTRY_COLUMNS, "test chemistry")
    _require(
        [row["row_index"] for row in rows]
        == [str(index) for index in range(contract["test"]["rows"])],
        "test chemistry order differs",
    )
    features = _module(FEATURE_KERNEL, "direct_maplight_feature_kernel")
    _require(
        features.DESCRIPTOR_NAMES_SHA256
        == contract["features"]["kernel"]["descriptor_order_sha256"],
        "descriptor order differs",
    )
    arrays, _ = features.featurize_raw_structures_upstream_int8(
        tuple(row["raw_smiles"] for row in rows),
        tuple(row["raw_structure_sha256"] for row in rows),
        nonfinite_policy="allow_gasteiger_charge_nan",
    )
    matrix = arrays.maplight_fixed()
    output.mkdir()
    try:
        features.write_npy_v1(output / "maplight_fixed.npy", matrix)
        receipt = {
            "schema_version": "cypshift.openadmet_cyp_2026.direct_test_features.v1",
            "contract_sha256": contract_sha,
            "projection_manifest_sha256": _sha(manifest_raw),
            "feature_kernel_sha256": contract["features"]["kernel"]["sha256"],
            "matrix_sha256": _sha((output / "maplight_fixed.npy").read_bytes()),
            "shape": list(matrix.shape),
            "dtype": "<f8",
            "accounting": {
                "raw_smiles": len(rows),
                "feature_blocks": 4,
                "targets": 0,
                "fits": 0,
                "relationships": 0,
            },
        }
        (output / "manifest.json").write_bytes(helper._json_bytes(receipt))
        helper._readonly_tree(output)
    except Exception:
        helper._cleanup_tree(output)
        raise


def _spawn_features(
    projection: Path, output: Path, _contract: Mapping[str, Any], contract_sha: str
) -> None:
    command = [
        sys.executable,
        str(RUNNER),
        "test-features",
        "--projection-root",
        str(projection),
        "--output-root",
        str(output),
        "--expected-contract-sha256",
        contract_sha,
    ]
    environment = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONHASHSEED": "0",
    }
    completed = subprocess.run(
        command, check=False, capture_output=True, text=True, env=environment
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()[-2000:]
        raise DirectDeploymentError(f"test feature worker failed: {detail}")


def _test_features(
    root: Path,
    contract: Mapping[str, Any],
    contract_sha: str,
    helper: ModuleType,
) -> tuple[np.ndarray[Any, Any], str]:
    helper._require_readonly_root(root, "test feature root differs")
    manifest, raw = helper._read_json(root / "manifest.json")
    _require(
        manifest.get("schema_version")
        == "cypshift.openadmet_cyp_2026.direct_test_features.v1"
        and manifest.get("contract_sha256") == contract_sha
        and manifest.get("shape")
        == [contract["test"]["rows"], contract["features"]["columns"]],
        "test feature manifest differs",
    )
    payload = _file(
        root / "maplight_fixed.npy",
        "test feature matrix",
        manifest["matrix_sha256"],
    )
    matrix = np.load(io.BytesIO(payload), allow_pickle=False)
    _require(matrix.ndim == 2, "test feature matrix differs")
    allowed_nan = np.zeros(matrix.shape[1], dtype=np.bool_)
    allowed_nan[[2363 + index for index in (39, 41, 43, 45)]] = True
    _require(
        matrix.shape == tuple(manifest["shape"])
        and matrix.dtype == np.dtype("<f8")
        and matrix.flags.c_contiguous
        and not np.isinf(matrix).any(),
        "test feature matrix differs",
    )
    _require(
        not np.logical_and(np.isnan(matrix), ~allowed_nan[np.newaxis, :]).any(),
        "test feature matrix contains an uncontracted NaN",
    )
    return matrix, _sha(raw)


def _catboost(arguments: Mapping[str, Any]) -> Any:
    try:
        from catboost import CatBoostRegressor  # type: ignore[import-not-found]
    except ImportError as exc:
        raise DirectDeploymentError("CatBoost 1.2.1 is unavailable") from exc
    return CatBoostRegressor(**dict(arguments))


def _validate(
    test: bytes,
    submission: bytes,
    contract: Mapping[str, Any],
    production: bool,
) -> Any:
    validator = _module(VALIDATOR, "direct_submission_validator")
    try:
        return validator.validate_submission_bytes(
            test, submission, contract, verify_test_receipt=production
        )
    except validator.DirectSubmissionError as exc:
        raise DirectDeploymentError(str(exc)) from exc


def _rehearsal_bytes(
    root: Path,
    test_raw: bytes,
    contract: Mapping[str, Any],
    contract_sha: str,
    runtime: Mapping[str, str],
    helper: ModuleType,
) -> tuple[bytes, bytes]:
    helper._require_readonly_root(root, "rehearsal terminal differs")
    terminal_files = contract["submission"]["terminal_files"]
    _require(
        sorted(path.name for path in root.iterdir()) == sorted(terminal_files)
        and all(path.is_file() and not path.is_symlink() for path in root.iterdir()),
        "rehearsal terminal file set differs",
    )
    submission = _file(root / "submission.csv", "rehearsal submission")
    manifest_raw = _file(root / "manifest.json", "rehearsal manifest")
    manifest = _json(manifest_raw, "rehearsal manifest")
    checked = _validate(test_raw, submission, contract, True)
    inputs = manifest.get("inputs")
    _require(isinstance(inputs, Mapping), "rehearsal manifest inputs differ")
    test_feature_sha = cast(Mapping[str, Any], inputs).get(
        "test_feature_manifest_sha256"
    )
    _require(_is_sha(test_feature_sha), "test feature receipt differs")
    expected_parameter_sha = contract["parents"]["oracle_parameter_record"][
        "resolved_parameter_sha256"
    ]
    expected = {
        "schema_version": "cypshift.openadmet_cyp_2026.direct_maplight_submission.v1",
        "contract_sha256": contract_sha,
        "system_id": contract["model"]["system_id"],
        "inputs": {
            "direct_observations_sha256": contract["training"]["observations_sha256"],
            "training_feature_manifest_sha256": contract["features"]["training_root"][
                "manifest_sha256"
            ],
            "test_source_sha256": contract["test"]["source_sha256"],
            "test_feature_manifest_sha256": test_feature_sha,
        },
        "runtime": dict(runtime),
        "resolved_parameter_sha256": {
            endpoint: expected_parameter_sha for endpoint in ENDPOINTS
        },
        "training_rows": contract["training"]["eligible_points"],
        "submission": {
            "path": "submission.csv",
            "sha256": checked.submission_sha256,
            "rows": contract["submission"]["rows"],
            "finite_predictions": contract["submission"]["finite_predictions"],
            "columns": contract["submission"]["columns"],
        },
        "accounting": contract["accounting"],
        "claim_boundary": contract["claim_boundary"],
    }
    _require(manifest == expected, "rehearsal manifest differs")
    return submission, manifest_raw


def accept_rehearsals(
    *,
    first_root: Path,
    second_root: Path,
    test_csv: Path,
    contract: Mapping[str, Any],
    contract_sha256: str,
    runtime: Mapping[str, str],
    helper: ModuleType,
) -> DirectAcceptanceResult:
    """Publish only after two distinct authenticated rehearsal roots agree."""

    accepted_root = _accepted_root(contract)
    for path, label in (
        (first_root, "first rehearsal"),
        (second_root, "second rehearsal"),
        (test_csv, "test"),
        (accepted_root, "accepted output"),
    ):
        _outside_git(path, label)
    _require(
        first_root.resolve() != second_root.resolve(),
        "two distinct rehearsal roots are required",
    )
    test_raw = _file(test_csv, "blinded test", str(contract["test"]["source_sha256"]))
    first = _rehearsal_bytes(
        first_root, test_raw, contract, contract_sha256, runtime, helper
    )
    second = _rehearsal_bytes(
        second_root, test_raw, contract, contract_sha256, runtime, helper
    )
    _require(first == second, "rehearsal terminals are not byte-identical")
    _require(
        not accepted_root.exists()
        and not accepted_root.is_symlink()
        and accepted_root.parent.is_dir()
        and not accepted_root.parent.is_symlink()
        and not any(parent.is_symlink() for parent in accepted_root.absolute().parents),
        "accepted destination already exists or is invalid",
    )
    staging = Path(
        tempfile.mkdtemp(prefix=".direct-maplight-accept-", dir=accepted_root.parent)
    )
    try:
        (staging / "submission.csv").write_bytes(first[0])
        (staging / "manifest.json").write_bytes(first[1])
        helper._readonly_tree(staging)
        helper._promote_noreplace(staging, accepted_root)
    except Exception:
        helper._cleanup_tree(staging)
        raise
    return DirectAcceptanceResult(
        accepted_root=accepted_root,
        submission_sha256=_sha(first[0]),
        manifest_sha256=_sha(first[1]),
    )


def run_submission(
    *,
    direct_observations: Path,
    training_feature_root: Path,
    test_csv: Path,
    output_root: Path,
    contract: Mapping[str, Any],
    contract_sha256: str,
    runtime: Mapping[str, str],
    helper: ModuleType,
    feature_process: FeatureProcess = _spawn_features,
    model_factory: ModelFactory = _catboost,
    production: bool = True,
) -> DirectDeploymentResult:
    """Fit exactly four accepted MapLight models and publish predictions only."""

    if production:
        _require(
            output_root.resolve(strict=False)
            != _accepted_root(contract).resolve(strict=False),
            "accepted destination requires two-root acceptance",
        )
    _require(
        not output_root.exists()
        and not output_root.is_symlink()
        and output_root.parent.is_dir()
        and not output_root.parent.is_symlink(),
        "output path differs",
    )
    feature_rows, X_train = _training_features(
        training_feature_root, contract, helper, not production
    )
    targets = _targets(direct_observations, feature_rows, contract, production)
    test_raw, test_rows = _test_rows(test_csv, contract, production)
    _require(
        not (
            {row["molecule_id"] for row in feature_rows}
            & {row["Molecule_Name"] for row in test_rows}
        ),
        "training/test identity overlap",
    )
    private = Path(
        tempfile.mkdtemp(prefix=".direct-maplight-private-", dir=output_root.parent)
    )
    terminal = Path(
        tempfile.mkdtemp(prefix=".direct-maplight-terminal-", dir=output_root.parent)
    )
    try:
        projection, test_root = (
            private / "test-chemistry",
            private / "test-features",
        )
        _project_test(projection, test_rows, contract, contract_sha256, helper)
        feature_process(projection, test_root, contract, contract_sha256)
        X_test, test_manifest_sha = _test_features(
            test_root, contract, contract_sha256, helper
        )
        predictions: dict[str, np.ndarray[Any, Any]] = {}
        resolved: dict[str, str] = {}
        arguments = contract["model"]["constructor_arguments"]
        expected_parameters = contract["parents"]["oracle_parameter_record"][
            "resolved_parameter_sha256"
        ]
        for endpoint in ENDPOINTS:
            train_index, y = targets[endpoint]
            model = model_factory(arguments)
            model.fit(X_train[train_index], y)
            values = np.asarray(model.predict(X_test), dtype=np.float64)
            _require(
                values.shape == (750,) and bool(np.isfinite(values).all()),
                f"{endpoint} predictions differ",
            )
            digest = _sha(
                helper._json_bytes(cast(Mapping[str, Any], model.get_all_params()))
            )
            _require(
                not production or digest == expected_parameters,
                f"{endpoint} parameters differ",
            )
            predictions[endpoint], resolved[endpoint] = values, digest
            del model
        output_rows: list[dict[str, object]] = []
        for row_index, row in enumerate(test_rows):
            item: dict[str, object] = {
                "SMILES": row["SMILES"],
                "Molecule_Name": row["Molecule_Name"],
            }
            item.update(
                {
                    f"{endpoint}_pIC50_direct_inhibition": format(
                        float(predictions[endpoint][row_index]), ".17g"
                    )
                    for endpoint in ENDPOINTS
                }
            )
            output_rows.append(item)
        submission = helper._csv_bytes(contract["submission"]["columns"], output_rows)
        checked = _validate(test_raw, submission, contract, production)
        _require(
            checked.rows == 750
            and checked.finite_predictions == 3000
            and len(resolved) == 4,
            "operation counts differ",
        )
        manifest = {
            "schema_version": (
                "cypshift.openadmet_cyp_2026.direct_maplight_submission.v1"
            ),
            "contract_sha256": contract_sha256,
            "system_id": contract["model"]["system_id"],
            "inputs": {
                "direct_observations_sha256": contract["training"][
                    "observations_sha256"
                ],
                "training_feature_manifest_sha256": contract["features"][
                    "training_root"
                ]["manifest_sha256"],
                "test_source_sha256": contract["test"]["source_sha256"],
                "test_feature_manifest_sha256": test_manifest_sha,
            },
            "runtime": dict(runtime),
            "resolved_parameter_sha256": resolved,
            "training_rows": contract["training"]["eligible_points"],
            "submission": {
                "path": "submission.csv",
                "sha256": checked.submission_sha256,
                "rows": 750,
                "finite_predictions": 3000,
                "columns": contract["submission"]["columns"],
            },
            "accounting": contract["accounting"],
            "claim_boundary": contract["claim_boundary"],
        }
        (terminal / "submission.csv").write_bytes(submission)
        manifest_raw = helper._json_bytes(manifest)
        (terminal / "manifest.json").write_bytes(manifest_raw)
        helper._readonly_tree(terminal)
        helper._cleanup_tree(private)
        helper._promote_noreplace(terminal, output_root)
        return DirectDeploymentResult(
            output_root, checked.submission_sha256, _sha(manifest_raw)
        )
    except Exception:
        helper._cleanup_tree(private)
        helper._cleanup_tree(terminal)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    for flag in (
        "direct-observations",
        "training-feature-root",
        "test-csv",
        "output-root",
    ):
        run.add_argument(f"--{flag}", type=Path, required=True)
    run.add_argument("--expected-contract-sha256", required=True)
    accept = commands.add_parser("accept")
    for flag in ("first-root", "second-root", "test-csv"):
        accept.add_argument(f"--{flag}", type=Path, required=True)
    accept.add_argument("--expected-contract-sha256", required=True)
    worker = commands.add_parser("test-features", help=argparse.SUPPRESS)
    worker.add_argument("--projection-root", type=Path, required=True)
    worker.add_argument("--output-root", type=Path, required=True)
    worker.add_argument("--expected-contract-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        contract, contract_sha, helper = _load_contract(args.expected_contract_sha256)
        runtime = _runtime(contract)
        if args.command == "test-features":
            _outside_git(args.projection_root, "test chemistry projection")
            _outside_git(args.output_root, "test feature output")
            _feature_worker(
                args.projection_root,
                args.output_root,
                contract,
                contract_sha,
                helper,
            )
            return 0
        if args.command == "accept":
            acceptance = accept_rehearsals(
                first_root=args.first_root,
                second_root=args.second_root,
                test_csv=args.test_csv,
                contract=contract,
                contract_sha256=contract_sha,
                runtime=runtime,
                helper=helper,
            )
            print(
                json.dumps(
                    {
                        "accepted_root": str(acceptance.accepted_root),
                        "manifest_sha256": acceptance.manifest_sha256,
                        "submission_sha256": acceptance.submission_sha256,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            return 0
        for path, label in (
            (args.direct_observations, "observations"),
            (args.training_feature_root, "features"),
            (args.test_csv, "test"),
            (args.output_root, "output"),
        ):
            _outside_git(path, label)
        result = run_submission(
            direct_observations=args.direct_observations,
            training_feature_root=args.training_feature_root,
            test_csv=args.test_csv,
            output_root=args.output_root,
            contract=contract,
            contract_sha256=contract_sha,
            runtime=runtime,
            helper=helper,
        )
        print(
            json.dumps(
                {
                    "manifest_sha256": result.manifest_sha256,
                    "output_root": str(result.output_root),
                    "submission_sha256": result.submission_sha256,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except DirectDeploymentError as exc:
        print(f"direct MapLight deployment failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Receipt-bound MapLight-only OOF runner for OpenADMET Global-v2.

The model capability contains label-free features/folds and one training-only
target file per cell.  The scorer capability contains truth but is unavailable
to this model stage.  Predictions are atomically frozen before the scorer can
derive residuals, q90 bands, or component diagnostics.
"""

from __future__ import annotations

import csv
import ctypes
import errno
import hashlib
import importlib.metadata
import io
import json
import math
import os
import platform
import shutil
import sys
import tempfile
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

import numpy as np

ROOT: Final = Path(__file__).resolve().parents[2]
SCRIPT: Final = Path(__file__).resolve()
CONTRACT: Final = (
    ROOT / "benchmarks/openadmet_cyp_2026/global_v2_maplight_reproduction_contract.json"
)
CONTRACT_SHA256: Final = (
    "7983e767dcc53d75c3a1816cf2a6528980c300b700bc339575cfb8a0faca344b"
)
LOCK: Final = SCRIPT.with_name("uv.lock")
LOCK_SHA256: Final = "99e72821b69d9bb943a6e32adc7e0dec0e46c6d32df090241d4fb9296a4195d8"
PARAMETER_SHA256: Final = (
    "c56235a54a883a9a4488f1c8779f9013dae777af0f99cd92c9da1c4f51e61757"
)
SYSTEM_ID: Final = "TRACE-G0-MAPL-FIXED"
ENDPOINTS: Final = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
REPEATS: Final = range(3)
OUTER_FOLDS: Final = range(5)
INNER_FOLDS: Final = range(4)
MAP_ARRAYS: Final = (
    ("maplight_morgan_count.npy", 1024, np.dtype("int8")),
    ("maplight_avalon_count.npy", 1024, np.dtype("int8")),
    ("maplight_erg.npy", 315, np.dtype("<f8")),
    ("maplight_rdkit_descriptors.npy", 200, np.dtype("<f8")),
)
CATBOOST_ARGUMENTS: Final = {
    "loss_function": "MAE",
    "random_strength": 2,
    "random_seed": 1,
    "task_type": "CPU",
    "thread_count": 16,
    "verbose": 0,
    "allow_writing_files": False,
}
FEATURE_COLUMNS: Final = ("molecule_id", "similarity_component_hash")
FOLD_COLUMNS: Final = (
    "molecule_id",
    "similarity_component_hash",
    "repeat",
    "outer_fold",
    "outer_validation_fold",
    "inner_fold",
)
TARGET_COLUMNS: Final = ("molecule_id", "point")
TRUTH_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "point",
)
OUTER_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "repeat",
    "outer_fold",
    "system_id",
    "prediction",
    "model_id",
    "split_id",
)
INNER_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "repeat",
    "outer_fold",
    "inner_fold",
    "system_id",
    "prediction",
    "model_id",
    "split_id",
)
RESIDUAL_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "repeat",
    "outer_fold",
    "prediction",
    "point",
    "residual",
    "prediction_receipt",
)
UNCERTAINTY_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "repeat",
    "outer_fold",
    "prediction",
    "q90",
    "lower",
    "upper",
    "inner_residual_receipt",
)
METRIC_COLUMNS: Final = (
    "endpoint",
    "repeat",
    "outer_fold",
    "scored_molecules",
    "scored_components",
    "component_macro_mae",
)
DENIED_AUTHORITY: Final = {
    "official_target_access": False,
    "official_feature_access": False,
    "official_model_fitting": False,
    "official_prediction_generation": False,
    "official_metric_evaluation": False,
    "confirmatory_truth_access": False,
    "external_record_acquisition": False,
    "blinded_test_access": False,
    "tdi_access": False,
    "submission_generation": False,
    "leaderboard_observation": False,
    "live_upload": False,
}

Predictor = Callable[
    [np.ndarray[Any, Any], np.ndarray[Any, Any], np.ndarray[Any, Any]],
    tuple[np.ndarray[Any, Any], str],
]


class GlobalV2MapLightError(RuntimeError):
    """A receipt, cross-fit, runtime, or publication invariant failed."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: object) -> bytes:
    try:
        text = json.dumps(
            value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise GlobalV2MapLightError("noncanonical JSON value") from exc
    return (text + "\n").encode("utf-8")


def csv_bytes(columns: Sequence[str], rows: Iterable[Mapping[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=list(columns), lineterminator="\n", extrasaction="raise"
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GlobalV2MapLightError(message)


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    )


def _regular(path: Path, label: str) -> Path:
    _require(path.is_file() and not path.is_symlink(), f"{label} is not regular")
    return path


def _readonly_root(path: Path, label: str) -> Path:
    _require(path.is_dir() and not path.is_symlink(), f"{label} is not a directory")
    _require(not bool(path.stat().st_mode & 0o222), f"{label} is writable")
    for child in path.rglob("*"):
        _require(not child.is_symlink(), f"{label} contains a symlink")
        _require(not bool(child.stat().st_mode & 0o222), f"{label} is writable")
    return path


def _destination(path: Path) -> None:
    _require(".." not in path.parts, "destination contains parent traversal")
    _require(not path.exists() and not path.is_symlink(), "destination exists")
    _require(
        not any(parent.is_symlink() for parent in path.parents),
        "destination has a symlinked parent",
    )


def _readonly(root: Path) -> None:
    for child in sorted(
        root.rglob("*"), key=lambda item: len(item.parts), reverse=True
    ):
        os.chmod(child, 0o555 if child.is_dir() else 0o444, follow_symlinks=False)
    os.chmod(root, 0o555, follow_symlinks=False)


def _cleanup(root: Path) -> None:
    if not root.exists() or root.is_symlink():
        return
    for child in sorted(
        root.rglob("*"), key=lambda item: len(item.parts), reverse=True
    ):
        try:
            os.chmod(child, 0o755 if child.is_dir() else 0o644)
        except OSError:
            pass
    os.chmod(root, 0o755)
    shutil.rmtree(root)


def _rename_noreplace(source: Path, destination: Path) -> None:
    _require(sys.platform == "linux", "renameat2 is unavailable")
    libc = ctypes.CDLL(None, use_errno=True)
    rename_function = getattr(libc, "renameat2", None)
    if rename_function is None:
        raise GlobalV2MapLightError("renameat2 is unavailable")
    rename = cast(Any, rename_function)
    rename.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        observed = ctypes.get_errno()
        message = (
            "destination appeared"
            if observed == errno.EEXIST
            else os.strerror(observed)
        )
        raise GlobalV2MapLightError(message)
    _require(destination.is_dir() and not source.exists(), "promotion failed")


def publish_files(destination: Path, files: Mapping[str, bytes]) -> Path:
    """Atomically publish one immutable, non-overwriting evidence root."""

    _destination(destination)
    names = [Path(name) for name in files]
    _require(len(names) == len(set(names)), "duplicate publication path")
    _require(
        all(
            not name.is_absolute() and ".." not in name.parts and name.name
            for name in names
        ),
        "invalid publication path",
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".g2-maplight-", dir=destination.parent))
    try:
        for name, value in files.items():
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        _readonly(staging)
        _rename_noreplace(staging, destination)
    except Exception:
        _cleanup(staging)
        raise
    return destination


def _load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = _regular(path, path.name).read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise GlobalV2MapLightError(f"{path.name} is not JSON") from exc
    _require(isinstance(value, dict), f"{path.name} is not an object")
    return cast(dict[str, Any], value), raw


def _read_csv(path: Path, columns: Sequence[str]) -> list[dict[str, str]]:
    raw = _regular(path, path.name).read_bytes()
    try:
        stream = io.StringIO(raw.decode("utf-8"), newline="")
    except UnicodeError as exc:
        raise GlobalV2MapLightError(f"{path.name} is not UTF-8") from exc
    reader = csv.DictReader(stream)
    _require(reader.fieldnames == list(columns), f"{path.name} columns differ")
    rows = list(reader)
    _require(all(None not in row for row in rows), f"{path.name} row width differs")
    return rows


def _canonical_float(value: str, label: str) -> float:
    try:
        observed = float(value)
    except ValueError as exc:
        raise GlobalV2MapLightError(f"{label} is not numeric") from exc
    _require(
        math.isfinite(observed) and value == format(observed, ".17g"),
        f"{label} is nonfinite or noncanonical",
    )
    return observed


def _verify_runtime() -> dict[str, str]:
    _require(
        sha256_path(_regular(CONTRACT, "G2-2A contract")) == CONTRACT_SHA256,
        "contract receipt differs",
    )
    _require(
        sha256_path(_regular(LOCK, "research lock")) == LOCK_SHA256,
        "research lock receipt differs",
    )
    observed = {
        "platform": f"{platform.system()} {platform.machine()} CPU",
        "python": platform.python_version(),
        "numpy": importlib.metadata.version("numpy"),
        "catboost": importlib.metadata.version("catboost"),
    }
    _require(
        observed
        == {
            "platform": "Linux x86_64 CPU",
            "python": "3.10.13",
            "numpy": "1.25.2",
            "catboost": "1.2.1",
        },
        f"locked runtime differs: {observed}",
    )
    return observed


def _load_capability(
    root: Path,
) -> tuple[
    dict[str, Any],
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, np.ndarray[Any, Any]],
]:
    _readonly_root(root, "model capability")
    manifest, _raw = _load_json(root / "manifest.json")
    _require(
        manifest.get("schema_version")
        == "cypshift.openadmet_cyp_2026.global_v2_maplight_model_capability.v1"
        and manifest.get("contract_sha256") == CONTRACT_SHA256
        and manifest.get("synthetic") is True,
        "model capability identity differs",
    )
    _require(
        manifest.get("authority") == DENIED_AUTHORITY, "capability authority differs"
    )
    features = _read_csv(root / "feature_rows.csv", FEATURE_COLUMNS)
    folds = _read_csv(root / "folds.csv", FOLD_COLUMNS)
    _require(
        sha256_path(root / "feature_rows.csv") == manifest.get("feature_rows_sha256")
        and sha256_path(root / "folds.csv") == manifest.get("folds_sha256"),
        "feature or fold receipt differs",
    )
    target_paths = sorted((root / "targets").rglob("*.csv"))
    _require(len(target_paths) == 300, "target capability file count differs")
    target_material = "".join(
        f"{path.relative_to(root).as_posix()}|{sha256_path(path)}\n"
        for path in target_paths
    ).encode("utf-8")
    _require(
        sha256_bytes(target_material) == manifest.get("target_tree_sha256"),
        "training target tree receipt differs",
    )
    _require(bool(features), "feature population is empty")
    feature_ids = [row["molecule_id"] for row in features]
    _require(feature_ids == sorted(set(feature_ids)), "feature identities differ")
    components = {
        row["molecule_id"]: row["similarity_component_hash"] for row in features
    }
    _require(
        all(_is_sha(value) for value in components.values()), "component hash differs"
    )
    expected_fold_rows = len(features) * 3 * 5
    _require(len(folds) == expected_fold_rows, "fold row count differs")
    seen: set[tuple[str, int, int]] = set()
    for row in folds:
        molecule = row["molecule_id"]
        _require(
            components.get(molecule) == row["similarity_component_hash"],
            "fold component differs",
        )
        repeat = int(row["repeat"])
        outer = int(row["outer_fold"])
        scope = int(row["outer_validation_fold"])
        _require(
            repeat in REPEATS and outer in OUTER_FOLDS and scope in OUTER_FOLDS,
            "fold context differs",
        )
        key = molecule, repeat, scope
        _require(key not in seen, "duplicate fold scope")
        seen.add(key)
        if outer == scope:
            _require(row["inner_fold"] == "", "outer validation has inner assignment")
        else:
            _require(int(row["inner_fold"]) in INNER_FOLDS, "inner assignment differs")
    for repeat in REPEATS:
        by_component: dict[str, set[int]] = defaultdict(set)
        for row in folds:
            if int(row["repeat"]) == repeat:
                by_component[row["similarity_component_hash"]].add(
                    int(row["outer_fold"])
                )
        _require(
            all(len(values) == 1 for values in by_component.values()),
            "component crosses an outer fold",
        )
        for outer in OUTER_FOLDS:
            inner_by_component: dict[str, set[int]] = defaultdict(set)
            for row in folds:
                if (
                    int(row["repeat"]) == repeat
                    and int(row["outer_validation_fold"]) == outer
                    and int(row["outer_fold"]) != outer
                ):
                    inner_by_component[row["similarity_component_hash"]].add(
                        int(row["inner_fold"])
                    )
            _require(
                bool(inner_by_component)
                and all(len(values) == 1 for values in inner_by_component.values()),
                "component crosses an inner fold",
            )
    arrays: dict[str, np.ndarray[Any, Any]] = {}
    _require(isinstance(manifest.get("arrays"), Mapping), "array receipts differ")
    receipts = cast(Mapping[str, Mapping[str, object]], manifest["arrays"])
    for name, width, dtype in MAP_ARRAYS:
        path = root / name
        _require(
            sha256_path(path) == receipts[name]["sha256"], f"{name} receipt differs"
        )
        array = np.load(path, allow_pickle=False)
        _require(
            array.shape == (len(features), width)
            and array.dtype == dtype
            and array.flags.c_contiguous,
            f"{name} layout differs",
        )
        if dtype.kind == "f":
            _require(np.isfinite(array).all(), f"{name} contains nonfinite values")
        arrays[name] = array
    return manifest, features, folds, arrays


def _matrix(
    arrays: Mapping[str, np.ndarray[Any, Any]], indices: Sequence[int]
) -> np.ndarray[Any, Any]:
    return cast(
        np.ndarray[Any, Any],
        np.ascontiguousarray(
            np.concatenate(
                [arrays[name][list(indices)] for name, _, _ in MAP_ARRAYS], axis=1
            )
        ),
    )


def _catboost_predict(
    training: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    prediction: np.ndarray[Any, Any],
) -> tuple[np.ndarray[Any, Any], str]:
    try:
        from catboost import CatBoostRegressor  # type: ignore[import-not-found]
    except ImportError as exc:
        raise GlobalV2MapLightError("CatBoost 1.2.1 is unavailable") from exc
    model = CatBoostRegressor(**CATBOOST_ARGUMENTS)
    model.fit(training, targets)
    resolved = cast(dict[str, Any], model.get_all_params())
    resolved_sha = sha256_bytes(json_bytes(resolved))
    _require(resolved_sha == PARAMETER_SHA256, "resolved CatBoost parameters differ")
    output = np.asarray(model.predict(prediction), dtype=np.float64)
    _require(
        output.shape == (len(prediction),) and np.isfinite(output).all(),
        "prediction differs",
    )
    return output, resolved_sha


def _scope_rows(
    folds: Sequence[Mapping[str, str]], repeat: int, outer: int
) -> dict[str, Mapping[str, str]]:
    rows = {
        row["molecule_id"]: row
        for row in folds
        if int(row["repeat"]) == repeat and int(row["outer_validation_fold"]) == outer
    }
    _require(bool(rows), "fold scope is empty")
    return rows


def _cell_target_path(
    root: Path,
    stage: str,
    endpoint: str,
    repeat: int,
    outer: int,
    inner: int | None,
) -> Path:
    relative = (
        Path("targets") / stage / endpoint / f"repeat-{repeat}" / f"outer-{outer}"
    )
    return root / relative / ("targets.csv" if inner is None else f"inner-{inner}.csv")


def _cell_ids(
    scope: Mapping[str, Mapping[str, str]], stage: str, outer: int, inner: int | None
) -> tuple[list[str], list[str]]:
    if stage == "outer":
        training = sorted(
            molecule
            for molecule, row in scope.items()
            if int(row["outer_fold"]) != outer
        )
        prediction = sorted(
            molecule
            for molecule, row in scope.items()
            if int(row["outer_fold"]) == outer
        )
    else:
        _require(inner is not None, "inner fold is absent")
        training = sorted(
            molecule
            for molecule, row in scope.items()
            if int(row["outer_fold"]) != outer and int(row["inner_fold"]) != inner
        )
        prediction = sorted(
            molecule
            for molecule, row in scope.items()
            if int(row["outer_fold"]) != outer and int(row["inner_fold"]) == inner
        )
    _require(bool(training) and bool(prediction), "cell support is empty")
    return training, prediction


def _identifier(*values: object) -> str:
    return sha256_bytes("|".join(map(str, values)).encode("utf-8"))


def _run_predictions(
    *,
    model_capability_root: Path,
    output_root: Path,
    predictor: Predictor,
    runtime: Mapping[str, str],
) -> Path:
    manifest, features, folds, arrays = _load_capability(model_capability_root)
    index = {row["molecule_id"]: position for position, row in enumerate(features)}
    component = {
        row["molecule_id"]: row["similarity_component_hash"] for row in features
    }
    outer_rows: list[dict[str, object]] = []
    inner_rows: list[dict[str, object]] = []
    parameter_hashes: set[str] = set()
    training_values_opened = 0
    for stage in ("outer", "inner"):
        for endpoint in ENDPOINTS:
            for repeat in REPEATS:
                for outer in OUTER_FOLDS:
                    scope = _scope_rows(folds, repeat, outer)
                    inner_values: Iterable[int | None] = (
                        (None,) if stage == "outer" else INNER_FOLDS
                    )
                    for inner in inner_values:
                        training_ids, prediction_ids = _cell_ids(
                            scope, stage, outer, inner
                        )
                        targets = _read_csv(
                            _cell_target_path(
                                model_capability_root,
                                stage,
                                endpoint,
                                repeat,
                                outer,
                                inner,
                            ),
                            TARGET_COLUMNS,
                        )
                        target_ids = [row["molecule_id"] for row in targets]
                        _require(
                            target_ids == training_ids,
                            "training-only target identity differs",
                        )
                        y: np.ndarray[Any, Any] = np.asarray(
                            [
                                _canonical_float(row["point"], "training point")
                                for row in targets
                            ],
                            dtype=np.float64,
                        )
                        training_values_opened += len(y)
                        predicted, parameter_sha = predictor(
                            _matrix(arrays, [index[value] for value in training_ids]),
                            y,
                            _matrix(arrays, [index[value] for value in prediction_ids]),
                        )
                        parameter_hashes.add(parameter_sha)
                        model_id = _identifier(
                            CONTRACT_SHA256,
                            SYSTEM_ID,
                            endpoint,
                            repeat,
                            outer,
                            "none" if inner is None else inner,
                        )
                        split_id = _identifier(
                            manifest["folds_sha256"],
                            repeat,
                            outer,
                            "none" if inner is None else inner,
                        )
                        for molecule, value in zip(
                            prediction_ids, predicted, strict=True
                        ):
                            row: dict[str, object] = {
                                "molecule_id": molecule,
                                "endpoint": endpoint,
                                "similarity_component_hash": component[molecule],
                                "repeat": repeat,
                                "outer_fold": outer,
                                "system_id": SYSTEM_ID,
                                "prediction": format(float(value), ".17g"),
                                "model_id": model_id,
                                "split_id": split_id,
                            }
                            if inner is None:
                                outer_rows.append(row)
                            else:
                                row["inner_fold"] = inner
                                inner_rows.append(row)
    _require(parameter_hashes == {PARAMETER_SHA256}, "parameter receipts differ")
    outer_rows.sort(key=lambda row: tuple(row[name] for name in OUTER_COLUMNS[:5]))
    inner_rows.sort(key=lambda row: tuple(row[name] for name in INNER_COLUMNS[:6]))
    expected_outer = len(features) * 4 * 3
    expected_inner = len(features) * 4 * 3 * 4
    _require(len(outer_rows) == expected_outer, "outer prediction count differs")
    _require(len(inner_rows) == expected_inner, "inner prediction count differs")
    outer_csv = csv_bytes(OUTER_COLUMNS, outer_rows)
    inner_csv = csv_bytes(INNER_COLUMNS, inner_rows)
    source_sha = sha256_path(SCRIPT)
    result = {
        "schema_version": "cypshift.openadmet_cyp_2026.global_v2_maplight_prediction_manifest.v1",
        "status": "G2_2B_SYNTHETIC_PREDICTIONS_FROZEN",
        "contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": source_sha,
        "model_capability_manifest_sha256": sha256_path(
            model_capability_root / "manifest.json"
        ),
        "runtime": dict(runtime),
        "resolved_parameter_sha256": PARAMETER_SHA256,
        "counts": {
            "molecules": len(features),
            "outer_maplight_fits": 60,
            "inner_maplight_fits": 240,
            "outer_prediction_rows": len(outer_rows),
            "inner_prediction_rows": len(inner_rows),
        },
        "output_receipts": {
            "development_outer_oof.csv": sha256_bytes(outer_csv),
            "development_inner_oof.csv": sha256_bytes(inner_csv),
        },
        "accounting": {
            "model_training_target_values_opened": training_values_opened,
            "outer_truth_values_opened_by_model": 0,
            "inner_truth_values_opened_by_model": 0,
            "maplight_model_fits": 300,
            "prediction_rows": len(outer_rows) + len(inner_rows),
            "official_target_values_opened": 0,
            "official_features_opened": 0,
            "official_model_fits": 0,
            "official_predictions_generated": 0,
            "official_metric_evaluations": 0,
            "confirmatory_truth_values_opened": 0,
            "historical_r3c_row_level_artifacts_opened": 0,
            "blinded_test_files_opened": 0,
            "tdi_files_opened": 0,
            "submissions_created": 0,
            "leaderboard_observations": 0,
        },
        "authority": dict(DENIED_AUTHORITY),
    }
    return publish_files(
        output_root,
        {
            "development_outer_oof.csv": outer_csv,
            "development_inner_oof.csv": inner_csv,
            "manifest.json": json_bytes(result),
        },
    )


def run_predictions(*, model_capability_root: Path, output_root: Path) -> Path:
    """Run all 300 real fixed-MapLight cells and freeze their OOF predictions."""

    return _run_predictions(
        model_capability_root=model_capability_root,
        output_root=output_root,
        predictor=_catboost_predict,
        runtime=_verify_runtime(),
    )


def _weighted_q90(rows: Sequence[tuple[float, str, str]]) -> float:
    _require(bool(rows), "q90 residual population is empty")
    counts: dict[str, int] = defaultdict(int)
    for value, component, _molecule in rows:
        _require(math.isfinite(value) and value >= 0.0, "q90 residual is invalid")
        counts[component] += 1
    ordered = sorted(rows, key=lambda row: (row[0], row[1], row[2]))
    total_components = len(counts)
    cumulative = 0.0
    for value, component, _molecule in ordered:
        cumulative += 1.0 / counts[component] / total_components
        if cumulative >= 0.90:
            return value
    return ordered[-1][0]


def _prediction_rows(
    root: Path,
) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    _readonly_root(root, "prediction root")
    manifest, _raw = _load_json(root / "manifest.json")
    _require(
        manifest.get("schema_version")
        == "cypshift.openadmet_cyp_2026.global_v2_maplight_prediction_manifest.v1"
        and manifest.get("contract_sha256") == CONTRACT_SHA256
        and manifest.get("status") == "G2_2B_SYNTHETIC_PREDICTIONS_FROZEN",
        "prediction manifest differs",
    )
    outer = _read_csv(root / "development_outer_oof.csv", OUTER_COLUMNS)
    inner = _read_csv(root / "development_inner_oof.csv", INNER_COLUMNS)
    receipts = manifest["output_receipts"]
    _require(
        sha256_path(root / "development_outer_oof.csv")
        == receipts["development_outer_oof.csv"]
        and sha256_path(root / "development_inner_oof.csv")
        == receipts["development_inner_oof.csv"],
        "prediction receipt differs",
    )
    return manifest, outer, inner


def _truth(
    root: Path,
) -> tuple[dict[str, Any], dict[tuple[str, str], tuple[str, float]]]:
    _readonly_root(root, "scorer capability")
    manifest, _raw = _load_json(root / "manifest.json")
    _require(
        manifest.get("schema_version")
        == "cypshift.openadmet_cyp_2026.global_v2_maplight_scorer_capability.v1"
        and manifest.get("contract_sha256") == CONTRACT_SHA256
        and manifest.get("synthetic") is True
        and manifest.get("authority") == DENIED_AUTHORITY,
        "scorer capability differs",
    )
    rows = _read_csv(root / "truth.csv", TRUTH_COLUMNS)
    values: dict[tuple[str, str], tuple[str, float]] = {}
    for row in rows:
        key = row["molecule_id"], row["endpoint"]
        _require(
            key not in values and row["endpoint"] in ENDPOINTS, "truth identity differs"
        )
        values[key] = (
            row["similarity_component_hash"],
            _canonical_float(row["point"], "truth point"),
        )
    _require(
        sha256_path(root / "truth.csv") == manifest["truth_sha256"],
        "truth receipt differs",
    )
    return manifest, values


def score_predictions(
    *, prediction_root: Path, scorer_capability_root: Path, output_root: Path
) -> Path:
    """Open synthetic truth only after prediction freeze and publish diagnostics."""

    prediction_manifest, outer, inner = _prediction_rows(prediction_root)
    scorer_manifest, truth = _truth(scorer_capability_root)
    _require(
        scorer_manifest["model_capability_manifest_sha256"]
        == prediction_manifest["model_capability_manifest_sha256"],
        "prediction/scorer capability binding differs",
    )
    outer_receipt = prediction_manifest["output_receipts"]["development_outer_oof.csv"]
    residual_rows: list[dict[str, object]] = []
    by_context: dict[tuple[str, int, int], list[dict[str, object]]] = defaultdict(list)
    for row in outer:
        key = row["molecule_id"], row["endpoint"]
        _require(key in truth, "outer truth identity is absent")
        component, point = truth[key]
        _require(
            component == row["similarity_component_hash"],
            "outer truth component differs",
        )
        prediction = _canonical_float(row["prediction"], "outer prediction")
        residual = prediction - point
        record: dict[str, object] = {
            "molecule_id": row["molecule_id"],
            "endpoint": row["endpoint"],
            "similarity_component_hash": component,
            "repeat": int(row["repeat"]),
            "outer_fold": int(row["outer_fold"]),
            "prediction": row["prediction"],
            "point": format(point, ".17g"),
            "residual": format(residual, ".17g"),
            "prediction_receipt": outer_receipt,
        }
        residual_rows.append(record)
        by_context[
            (row["endpoint"], int(row["repeat"]), int(row["outer_fold"]))
        ].append(record)
    inner_contexts: dict[tuple[str, int, int], list[tuple[float, str, str]]] = (
        defaultdict(list)
    )
    for row in inner:
        key = row["molecule_id"], row["endpoint"]
        _require(key in truth, "inner truth identity is absent")
        component, point = truth[key]
        _require(
            component == row["similarity_component_hash"],
            "inner truth component differs",
        )
        prediction = _canonical_float(row["prediction"], "inner prediction")
        inner_contexts[
            (row["endpoint"], int(row["repeat"]), int(row["outer_fold"]))
        ].append((abs(prediction - point), component, row["molecule_id"]))
    uncertainty_rows: list[dict[str, object]] = []
    metric_rows: list[dict[str, object]] = []
    for context in sorted(by_context):
        eligible = inner_contexts[context]
        q90 = _weighted_q90(eligible)
        inner_receipt = sha256_bytes(
            csv_bytes(
                ("absolute_residual", "similarity_component_hash", "molecule_id"),
                (
                    {
                        "absolute_residual": format(value, ".17g"),
                        "similarity_component_hash": component,
                        "molecule_id": molecule,
                    }
                    for value, component, molecule in sorted(
                        eligible, key=lambda item: (item[0], item[1], item[2])
                    )
                ),
            )
        )
        component_errors: dict[str, list[float]] = defaultdict(list)
        for outer_record in by_context[context]:
            prediction = _canonical_float(
                str(outer_record["prediction"]), "outer prediction"
            )
            point = _canonical_float(str(outer_record["point"]), "outer point")
            component_errors[str(outer_record["similarity_component_hash"])].append(
                abs(prediction - point)
            )
            uncertainty_rows.append(
                {
                    "molecule_id": outer_record["molecule_id"],
                    "endpoint": outer_record["endpoint"],
                    "similarity_component_hash": outer_record[
                        "similarity_component_hash"
                    ],
                    "repeat": outer_record["repeat"],
                    "outer_fold": outer_record["outer_fold"],
                    "prediction": outer_record["prediction"],
                    "q90": format(q90, ".17g"),
                    "lower": format(prediction - q90, ".17g"),
                    "upper": format(prediction + q90, ".17g"),
                    "inner_residual_receipt": inner_receipt,
                }
            )
        component_mae = math.fsum(
            math.fsum(values) / len(values) for values in component_errors.values()
        ) / len(component_errors)
        metric_rows.append(
            {
                "endpoint": context[0],
                "repeat": context[1],
                "outer_fold": context[2],
                "scored_molecules": sum(map(len, component_errors.values())),
                "scored_components": len(component_errors),
                "component_macro_mae": format(component_mae, ".17g"),
            }
        )
    residual_rows.sort(
        key=lambda row: tuple(row[name] for name in RESIDUAL_COLUMNS[:5])
    )
    uncertainty_rows.sort(
        key=lambda row: tuple(row[name] for name in UNCERTAINTY_COLUMNS[:5])
    )
    residual_csv = csv_bytes(RESIDUAL_COLUMNS, residual_rows)
    uncertainty_csv = csv_bytes(UNCERTAINTY_COLUMNS, uncertainty_rows)
    metrics_csv = csv_bytes(METRIC_COLUMNS, metric_rows)
    outer_bytes = (prediction_root / "development_outer_oof.csv").read_bytes()
    inner_bytes = (prediction_root / "development_inner_oof.csv").read_bytes()
    outputs: dict[str, bytes] = {
        "development_outer_oof.csv": outer_bytes,
        "development_inner_oof.csv": inner_bytes,
        "development_residuals.csv": residual_csv,
        "development_uncertainty.csv": uncertainty_csv,
        "development_component_metrics.csv": metrics_csv,
    }
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.global_v2_maplight_terminal.v1",
        "status": "G2_2B_SYNTHETIC_RUNNER_COMPLETE",
        "contract_sha256": CONTRACT_SHA256,
        "source_receipts": {
            "runner_source_sha256": sha256_path(SCRIPT),
            "model_capability_manifest_sha256": prediction_manifest[
                "model_capability_manifest_sha256"
            ],
            "scorer_capability_manifest_sha256": sha256_path(
                scorer_capability_root / "manifest.json"
            ),
        },
        "implementation_receipts": {
            "resolved_parameter_sha256": PARAMETER_SHA256,
            "research_uv_lock_sha256": LOCK_SHA256,
        },
        "runtime": prediction_manifest["runtime"],
        "counts": {
            **prediction_manifest["counts"],
            "residual_rows": len(residual_rows),
            "uncertainty_rows": len(uncertainty_rows),
            "component_metric_rows": len(metric_rows),
            "q90_contexts": len(inner_contexts),
        },
        "output_receipts": {
            name: sha256_bytes(value) for name, value in outputs.items()
        },
        "determinism": {
            "canonical_input_order": True,
            "duration_excluded": True,
            "retry": False,
            "resume": False,
            "overwrite": False,
        },
        "accounting": {
            **prediction_manifest["accounting"],
            "scorer_truth_values_opened_after_prediction_freeze": len(truth),
            "residual_values_computed": len(residual_rows) + len(inner),
            "q90_contexts_computed": len(inner_contexts),
            "component_metric_rows_computed": len(metric_rows),
            "tutorial_ma_st_rae_calls": 0,
        },
        "authority": dict(DENIED_AUTHORITY),
    }
    return publish_files(
        output_root, {**outputs, "manifest.json": json_bytes(manifest)}
    )


def relative_byte_map(root: Path) -> dict[str, str]:
    """Return the deterministic relative file-to-SHA map for a sealed root."""

    _readonly_root(root, "evidence root")
    return {
        path.relative_to(root).as_posix(): sha256_path(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }

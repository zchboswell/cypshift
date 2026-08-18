#!/usr/bin/env python3
"""Run the bounded, synthetic R3B V5 end-to-end acceptance replay.

The projector/preflight runtime is Python 3.12.3.  The model-cell and scorer
runtime is the locked research Python 3.10 environment.  This script creates
only private temporary fixture data and never opens official challenge files.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
import platform
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).resolve()
RESEARCH_PY = SCRIPT.parent / ".venv/bin/python"
ENDPOINTS = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
MOLECULE_COUNT = 50
RESEARCH_LOCK_SHA256 = (
    "99e72821b69d9bb943a6e32adc7e0dec0e46c6d32df090241d4fb9296a4195d8"
)
MODEL_RUNTIME = {
    "platform": "Linux x86_64 CPU",
    "python_version": "3.10.13",
    "uv_lock_sha256": RESEARCH_LOCK_SHA256,
    "numpy_version": "1.25.2",
    "catboost_version": "1.2.1",
}
TERMINAL_STATIC_RUNTIME = {
    "platform": "Linux x86_64 CPU",
    "python_version": "3.10.13",
    "numpy_version": "1.25.2",
    "catboost_version": "1.2.1",
    "cpu_only": True,
    "max_threads": 16,
    "gpu_fits": 0,
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _csv_bytes(columns: Sequence[str], rows: Iterable[Mapping[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row[column] for column in columns})
    return stream.getvalue().encode("utf-8")


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _locked_model_runtime() -> dict[str, object]:
    """Fail closed on the complete frozen research runtime before any fit."""
    contract_path = (
        ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract_v4.json"
    )
    lock_path = SCRIPT.parent / "uv.lock"
    if (
        not contract_path.is_file()
        or contract_path.is_symlink()
        or not lock_path.is_file()
        or lock_path.is_symlink()
    ):
        raise RuntimeError("locked runtime receipt input is not a regular file")
    contract = json.loads(contract_path.read_text())
    contracted = contract["runtime_and_models"]["model_and_scorer"]
    if contracted != MODEL_RUNTIME:
        raise RuntimeError("contracted model runtime differs")
    observed: dict[str, object] = {
        "platform": f"{platform.system()} {platform.machine()} CPU",
        "python_version": platform.python_version(),
        "uv_lock_sha256": _sha(lock_path.read_bytes()),
        "numpy_version": importlib.metadata.version("numpy"),
        "catboost_version": importlib.metadata.version("catboost"),
    }
    if observed != MODEL_RUNTIME:
        raise RuntimeError(f"model runtime differs: {observed}")
    return observed


def _readonly_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)


def _writable_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts)):
        path.chmod(0o755 if path.is_dir() else 0o644)
    root.chmod(0o755)


def _fixture_inputs(root: Path) -> tuple[Path, Path, dict[str, int], dict[str, str]]:
    root.mkdir(parents=True, exist_ok=True)
    observation_columns = (
        "observation_id",
        "molecule_id",
        "source_row_id",
        "source_file",
        "source_row",
        "source_sha256",
        "endpoint",
        "raw_smiles",
        "raw_point",
        "raw_low",
        "raw_high",
        "raw_std",
        "point",
        "low",
        "high",
        "std",
        "raw_structure_sha256",
        "standardized_structure_hash",
        "similarity_component_hash",
        "scaffold_group_hash",
        "value_state",
        "point_eligible",
        "anchor_eligible",
    )
    fold_columns = (
        "molecule_id",
        "similarity_component_hash",
        "repeat",
        "seed",
        "outer_fold",
        "outer_validation_fold",
        "inner_fold",
    )
    observations: list[dict[str, object]] = []
    folds: list[dict[str, object]] = []
    for index in range(MOLECULE_COUNT):
        molecule = f"synthetic-molecule-{index:03d}"
        component = _sha(f"component-{index}".encode())
        for endpoint in ENDPOINTS:
            observations.append(
                {
                    "observation_id": _sha(f"{molecule}|{endpoint}".encode()),
                    "molecule_id": molecule,
                    "source_row_id": f"synthetic-row-{index:03d}",
                    "source_file": "synthetic.csv",
                    "source_row": index + 1,
                    "source_sha256": _sha(b"synthetic-source"),
                    "endpoint": endpoint,
                    "raw_smiles": f"C{index + 1}",
                    "raw_point": format(index / 10.0, ".17g"),
                    "raw_low": "",
                    "raw_high": "",
                    "raw_std": "",
                    "value_state": "complete",
                    "point_eligible": "true",
                    # A continuous maplight-only signal makes the comparator
                    # contrast useful while remaining entirely synthetic.
                    "point": format(index / 10.0, ".17g"),
                    "low": "",
                    "high": "",
                    "std": "",
                    "raw_structure_sha256": _sha(f"raw-{index}".encode()),
                    "standardized_structure_hash": _sha(
                        f"standardized-{index}".encode()
                    ),
                    "similarity_component_hash": component,
                    "scaffold_group_hash": _sha(f"scaffold-{index}".encode()),
                    "anchor_eligible": "true",
                }
            )
        assignment = index % 5
        for repeat in range(3):
            for validation in range(5):
                folds.append(
                    {
                        "molecule_id": molecule,
                        "similarity_component_hash": component,
                        "repeat": repeat,
                        "seed": 20260810 + repeat,
                        "outer_fold": assignment,
                        "outer_validation_fold": validation,
                        "inner_fold": "" if assignment == validation else index % 4,
                    }
                )
    direct_data = _csv_bytes(observation_columns, observations)
    fold_data = _csv_bytes(fold_columns, folds)
    direct = root / "direct_observations.csv"
    group_folds = root / "group_folds.csv"
    direct.write_bytes(direct_data)
    group_folds.write_bytes(fold_data)
    counts = {
        "direct_rows": len(observations),
        "fold_rows": len(folds),
        "eligible": len(observations),
        "ineligible": 0,
        "complete": len(observations),
        "partial": 0,
        "missing": 0,
        "orphan_auxiliary": 0,
        "outer_target_files": 60,
        "inner_target_files": 240,
        "outer_target_rows": 2_400,
        "inner_target_rows": 7_200,
        "outer_truth_rows": 600,
        "inner_truth_rows": 2_400,
        "outer_truth_eligible": 600,
        "inner_truth_eligible": 2_400,
    }
    receipts = {
        "direct_observations_sha256": _sha(direct_data),
        "group_folds_sha256": _sha(fold_data),
    }
    return direct, group_folds, counts, receipts


def _feature_root(root: Path) -> str:
    """Write a strict fixed-width synthetic feature root and return its SHA."""
    root.mkdir(parents=True, exist_ok=True)
    feature_columns = (
        "molecule_id",
        "raw_structure_sha256",
        "standardized_structure_hash",
        "similarity_component_hash",
    )
    rows = []
    components = []
    for index in range(MOLECULE_COUNT):
        molecule = f"synthetic-molecule-{index:03d}"
        component = _sha(f"component-{index}".encode())
        components.append(component)
        rows.append(
            {
                "molecule_id": molecule,
                "raw_structure_sha256": _sha(f"raw-{index}".encode()),
                "standardized_structure_hash": _sha(f"standardized-{index}".encode()),
                "similarity_component_hash": component,
            }
        )
    row_data = _csv_bytes(feature_columns, rows)
    (root / "feature_rows.csv").write_bytes(row_data)
    arrays: dict[str, np.ndarray[Any, Any]] = {
        "morgan_binary": np.zeros((MOLECULE_COUNT, 4096), dtype=np.uint8),
        "maplight_morgan_count": np.zeros((MOLECULE_COUNT, 1024), dtype=np.int8),
        "maplight_avalon_count": np.zeros((MOLECULE_COUNT, 1024), dtype=np.int8),
        "maplight_erg": np.zeros((MOLECULE_COUNT, 315), dtype="<f8"),
        "maplight_rdkit_descriptors": np.zeros((MOLECULE_COUNT, 200), dtype="<f8"),
    }
    for index in range(MOLECULE_COUNT):
        # A disjoint one-hot identity makes the Morgan controls valid but
        # deliberately non-transferable across held-out components.
        arrays["morgan_binary"][index, index] = 1
        arrays["maplight_morgan_count"][index, 0] = index
    array_records: dict[str, dict[str, object]] = {}
    for name, array in arrays.items():
        path = root / f"{name}.npy"
        with path.open("wb") as handle:
            np.save(handle, np.ascontiguousarray(array), allow_pickle=False)
        array_records[name] = {
            "path": path.name,
            "shape": list(array.shape),
            "dtype": array.dtype.str if array.dtype.kind == "f" else str(array.dtype),
            "npy_version": "1.0",
            "c_contiguous": True,
            "npy_sha256": _sha(path.read_bytes()),
        }
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3a_feature_manifest.v1",
        "rows": {
            "path": "feature_rows.csv",
            "columns": list(feature_columns),
            "rows": len(rows),
            "sha256": _sha(row_data),
        },
        "arrays": array_records,
        "synthetic_component_count": len(set(components)),
    }
    manifest_data = _json_bytes(manifest)
    (root / "feature_manifest.json").write_bytes(manifest_data)
    _readonly_tree(root)
    return _sha(manifest_data)


def _project_and_preflight(root: Path) -> dict[str, str]:
    if sys.version_info[:3] != (3, 12, 3):
        raise RuntimeError("projection phase must run under Python 3.12.3")
    sys.path.insert(0, str(ROOT / "src"))
    from cypshift.openadmet_global_io import (  # noqa: PLC0415
        PREFLIGHT_SOURCE_FILES,
        PROJECTION_SOURCE_FILES,
        _runtime_gate,
    )
    from cypshift.openadmet_global_projection import (  # noqa: PLC0415
        preflight_openadmet_global_targets,
        project_openadmet_global_targets,
    )

    direct, folds, counts, receipts = _fixture_inputs(root / "inputs")
    feature_sha = _feature_root(root / "features")
    projection_source_sha = _runtime_gate(PROJECTION_SOURCE_FILES)
    projection = project_openadmet_global_targets(
        direct,
        folds,
        root / "projection",
        expected_input_receipts=receipts,
        expected_counts=counts,
        expected_projector_source_sha256=projection_source_sha,
    )
    preflight_source_sha = _runtime_gate(PREFLIGHT_SOURCE_FILES)
    preflight_path = root / "preflight.json"
    preflight = preflight_openadmet_global_targets(
        projection.output_directory,
        expected_model_public_manifest_sha256=projection.model_public_manifest_sha256,
        expected_private_audit_sha256=projection.private_audit_sha256,
        expected_preflight_source_sha256=preflight_source_sha,
        output_path=preflight_path,
    )
    if preflight.receipt["passed"] is not True:
        raise RuntimeError(
            f"synthetic preflight unexpectedly failed: {preflight.receipt}"
        )
    return {
        "projection": str(projection.output_directory),
        "model_public": str(projection.model_public_root),
        "sealed": str(projection.scorer_sealed_root),
        "public_manifest_sha256": projection.model_public_manifest_sha256,
        "sealed_manifest_sha256": projection.sealed_truth_manifest_sha256,
        "private_audit_sha256": projection.private_audit_sha256,
        "preflight": str(preflight_path),
        "preflight_sha256": _sha(preflight_path.read_bytes()),
        "feature_root": str(root / "features"),
        "feature_manifest_sha256": feature_sha,
    }


def _load_production_modules() -> tuple[Any, Any]:
    cells = _load_module("r3b_acceptance_cells", SCRIPT.parent / "run_r3b_cells.py")
    scorer = _load_module(
        "r3b_acceptance_scoring", SCRIPT.parent / "run_r3b_scoring.py"
    )
    return cells, scorer


def _run_one_cell(
    state: Mapping[str, str],
    *,
    stage: str,
    endpoint: str,
    repeat: int,
    outer: int,
    inner: int | None,
    output_root: Path,
    token: Path | None,
) -> dict[str, object]:
    runtime = _locked_model_runtime()
    cells = _load_module(
        "r3b_acceptance_single_cell", SCRIPT.parent / "run_r3b_cells.py"
    )
    cells.run_cell(
        stage=stage,
        endpoint=endpoint,
        repeat=repeat,
        outer_fold=outer,
        inner_fold=inner,
        feature_root=Path(state["feature_root"]),
        feature_manifest_sha256=state["feature_manifest_sha256"],
        model_public_root=Path(state["model_public"]),
        model_public_manifest_sha256=state["public_manifest_sha256"],
        preflight_receipt=Path(state["preflight"]),
        preflight_receipt_sha256=state["preflight_sha256"],
        output_root=output_root,
        inner_selection_token=token,
        synthetic=True,
    )
    receipt = json.loads((output_root / "cell_receipt.json").read_text())
    return {
        "pid": os.getpid(),
        "output_root": str(output_root),
        "model_fits": receipt["counts"]["model_fits"],
        "runtime": runtime,
    }


def _spawn_cell(
    state_path: Path,
    *,
    stage: str,
    endpoint: str,
    repeat: int,
    outer: int,
    inner: int | None,
    output_root: Path,
    token: Path | None = None,
) -> dict[str, Any]:
    command = [
        str(RESEARCH_PY),
        str(SCRIPT),
        "--cell",
        str(state_path),
        stage,
        endpoint,
        str(repeat),
        str(outer),
        "none" if inner is None else str(inner),
        str(output_root),
        "none" if token is None else str(token),
    ]
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"{stage} cell failed for {endpoint}/{repeat}/{outer}/{inner}:\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
    result = json.loads(completed.stdout)
    if (
        result.get("output_root") != str(output_root)
        or result.get("runtime") != MODEL_RUNTIME
        or type(result.get("pid")) is not int
        or result["pid"] == os.getpid()
    ):
        raise RuntimeError("cell subprocess proof differs")
    return result


def _model_fit_count(cell_roots: Sequence[Path], expected: int) -> int:
    observed = 0
    for root in cell_roots:
        receipt = json.loads((root / "cell_receipt.json").read_text())
        value = receipt["counts"]["model_fits"]
        if type(value) is not int or value < 0:
            raise RuntimeError("cell model-fit count differs")
        observed += value
    if observed != expected:
        raise RuntimeError(f"model-fit total differs: {observed} != {expected}")
    return observed


def _run_models(
    state: Mapping[str, str], state_path: Path, run_root: Path
) -> dict[str, Any]:
    runtime = _locked_model_runtime()
    model_public = Path(state["model_public"])
    sealed = Path(state["sealed"])
    preflight = Path(state["preflight"])
    outer_cells: list[Path] = []
    cell_pids: list[int] = []
    for endpoint in ENDPOINTS:
        for repeat in range(3):
            for outer in range(5):
                output = (
                    run_root
                    / "outer-cells"
                    / endpoint
                    / f"repeat-{repeat}"
                    / f"outer-{outer}"
                )
                result = _spawn_cell(
                    state_path,
                    stage="outer",
                    endpoint=endpoint,
                    repeat=repeat,
                    outer=outer,
                    inner=None,
                    output_root=output,
                )
                outer_cells.append(output)
                cell_pids.append(result["pid"])
    outer_fits = _model_fit_count(outer_cells, 120)
    cells, scorer = _load_production_modules()
    outer_freeze = cells.freeze_outer(
        cell_roots=outer_cells,
        output_root=run_root / "outer-freeze",
        model_public_root=model_public,
        model_public_manifest_sha256=state["public_manifest_sha256"],
        preflight_receipt=preflight,
        preflight_receipt_sha256=state["preflight_sha256"],
        feature_manifest_sha256=state["feature_manifest_sha256"],
        synthetic=True,
    )
    outer_manifest_sha = _sha(
        (outer_freeze / "global_oof_freeze_manifest.json").read_bytes()
    )
    outer_stage = scorer.score_outer(
        outer_root=outer_freeze,
        sealed_root=sealed,
        stage_root=run_root / "outer-stage",
        outer_manifest_sha256=outer_manifest_sha,
        sealed_manifest_sha256=state["sealed_manifest_sha256"],
        preflight_receipt=preflight,
        preflight_receipt_sha256=state["preflight_sha256"],
        synthetic=True,
    )
    if outer_stage.status != "PASS":
        raise RuntimeError(f"synthetic outer scorer did not pass: {outer_stage.status}")
    token = outer_stage.root / "inner_selection_token.json"
    inner_cells: list[Path] = []
    for endpoint in ENDPOINTS:
        for repeat in range(3):
            for outer in range(5):
                for inner in range(4):
                    output = (
                        run_root
                        / "inner-cells"
                        / endpoint
                        / f"repeat-{repeat}"
                        / f"outer-{outer}"
                        / f"inner-{inner}"
                    )
                    result = _spawn_cell(
                        state_path,
                        stage="inner",
                        endpoint=endpoint,
                        repeat=repeat,
                        outer=outer,
                        inner=inner,
                        output_root=output,
                        token=token,
                    )
                    inner_cells.append(output)
                    cell_pids.append(result["pid"])
    inner_fits = _model_fit_count(inner_cells, 240)
    inner_freeze = cells.freeze_inner(
        cell_roots=inner_cells,
        output_root=run_root / "inner-freeze",
        model_public_root=model_public,
        model_public_manifest_sha256=state["public_manifest_sha256"],
        preflight_receipt=preflight,
        preflight_receipt_sha256=state["preflight_sha256"],
        feature_manifest_sha256=state["feature_manifest_sha256"],
        inner_selection_token=token,
        synthetic=True,
    )
    inner_manifest_sha = _sha(
        (inner_freeze / "global_inner_oof_freeze_manifest.json").read_bytes()
    )
    terminal = scorer.score_final(
        outer_stage_root=outer_stage.root,
        inner_root=inner_freeze,
        sealed_root=sealed,
        output_root=run_root / "terminal",
        inner_manifest_sha256=inner_manifest_sha,
        sealed_manifest_sha256=state["sealed_manifest_sha256"],
        synthetic=True,
    )
    result = json.loads((terminal / "global_result.json").read_text())
    if result.get("status") != "GLOBAL_EXPERT_FROZEN":
        raise RuntimeError(f"synthetic terminal status differs: {result.get('status')}")
    _normalized_terminal(terminal)
    if len(cell_pids) != 300 or len(set(cell_pids)) != 300:
        raise RuntimeError("fresh-process-per-cell proof differs")
    return {
        "outer_freeze": str(outer_freeze),
        "outer_stage": str(outer_stage.root),
        "inner_freeze": str(inner_freeze),
        "terminal": str(terminal),
        "status": result["status"],
        "outer_cells": len(outer_cells),
        "inner_cells": len(inner_cells),
        "cell_processes": len(cell_pids),
        "unique_cell_pids": len(set(cell_pids)),
        "outer_model_fits": outer_fits,
        "inner_model_fits": inner_fits,
        "total_model_fits": outer_fits + inner_fits,
        "runtime": runtime,
    }


def _file_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _normalized_terminal(root: Path) -> dict[str, Any]:
    manifest = json.loads((root / "manifest.json").read_text())
    runtime = manifest.pop("runtime")
    if set(runtime) != {
        "platform",
        "python_version",
        "numpy_version",
        "catboost_version",
        "cpu_only",
        "max_threads",
        "gpu_fits",
        "runtime_seconds",
        "peak_rss_gib",
    }:
        raise RuntimeError("terminal runtime schema differs")
    if not (
        isinstance(runtime["runtime_seconds"], (int, float))
        and isinstance(runtime["peak_rss_gib"], (int, float))
        and runtime["runtime_seconds"] >= 0
        and runtime["peak_rss_gib"] >= 0
    ):
        raise RuntimeError("terminal runtime measurements differ")
    static_runtime = {key: runtime[key] for key in TERMINAL_STATIC_RUNTIME}
    if static_runtime != TERMINAL_STATIC_RUNTIME:
        raise RuntimeError(f"terminal static runtime differs: {static_runtime}")
    manifest["runtime_normalized_fields"] = {
        key: runtime[key]
        for key in (
            "platform",
            "python_version",
            "numpy_version",
            "catboost_version",
            "cpu_only",
            "max_threads",
            "gpu_fits",
        )
    }
    manifest["runtime_measurement_fields"] = ("runtime_seconds", "peak_rss_gib")
    return manifest


def _compare_runs(first: Mapping[str, Any], second: Mapping[str, Any]) -> None:
    for key in ("outer_freeze", "outer_stage", "inner_freeze"):
        left, right = _file_bytes(Path(first[key])), _file_bytes(Path(second[key]))
        if left != right:
            differing = sorted(set(left) | set(right))
            differing = [
                name for name in differing if left.get(name) != right.get(name)
            ]
            raise RuntimeError(f"non-deterministic {key} artifacts: {differing[:5]}")
    left_terminal = _file_bytes(Path(first["terminal"]))
    right_terminal = _file_bytes(Path(second["terminal"]))
    for name in set(left_terminal) | set(right_terminal):
        if name == "manifest.json":
            continue
        if left_terminal.get(name) != right_terminal.get(name):
            raise RuntimeError(f"non-deterministic terminal artifact: {name}")
    if _normalized_terminal(Path(first["terminal"])) != _normalized_terminal(
        Path(second["terminal"])
    ):
        raise RuntimeError(
            "terminal artifacts differ after explicit runtime normalization"
        )


def _compare_projection_roots(
    first: Mapping[str, str], second: Mapping[str, str]
) -> None:
    for key in ("projection", "preflight", "feature_root"):
        left_path, right_path = Path(first[key]), Path(second[key])
        if left_path.is_file() and right_path.is_file():
            if left_path.read_bytes() != right_path.read_bytes():
                raise RuntimeError(f"non-deterministic {key} bytes")
            continue
        left, right = _file_bytes(left_path), _file_bytes(right_path)
        if left != right:
            raise RuntimeError(f"non-deterministic {key} artifacts")


def _run_child(state_path: Path, run_root: Path) -> dict[str, Any]:
    state = json.loads(state_path.read_text())
    return _run_models(state, state_path, run_root)


def main() -> int:
    if sys.version_info[:3] != (3, 12, 3):
        raise SystemExit("Run this acceptance script with Python 3.12.3.")
    if not RESEARCH_PY.is_file():
        raise SystemExit(f"missing locked research interpreter: {RESEARCH_PY}")
    with tempfile.TemporaryDirectory(prefix="cypshift-r3b-v5-acceptance-") as temp:
        root = Path(temp)
        first_root = root / "run-1"
        second_root = root / "run-2"
        first_root.mkdir()
        second_root.mkdir()
        first_state = _project_and_preflight(first_root)
        second_state = _project_and_preflight(second_root)
        for key in (
            "public_manifest_sha256",
            "sealed_manifest_sha256",
            "private_audit_sha256",
            "preflight_sha256",
            "feature_manifest_sha256",
        ):
            if first_state[key] != second_state[key]:
                raise RuntimeError(f"non-deterministic projection receipt: {key}")
        _compare_projection_roots(first_state, second_state)
        model_results: list[dict[str, Any]] = []
        for index, run_root in enumerate((first_root, second_root), 1):
            state = dict(first_state)
            state["projection"] = str(run_root / "projection")
            state["model_public"] = str(run_root / "projection/model-public")
            state["sealed"] = str(run_root / "projection/scorer-sealed")
            state["preflight"] = str(run_root / "preflight.json")
            state["feature_root"] = str(run_root / "features")
            state_path = root / f"state-{index}.json"
            state_path.write_bytes(_json_bytes(state))
            command = [
                str(RESEARCH_PY),
                str(SCRIPT),
                "--child",
                str(state_path),
                str(run_root),
            ]
            completed = subprocess.run(
                command, check=False, text=True, capture_output=True
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    f"model phase {index} failed:\nstdout={completed.stdout}\nstderr={completed.stderr}"
                )
            model_results.append(json.loads(completed.stdout))
        if sum(result["total_model_fits"] for result in model_results) != 720 or any(
            result["runtime"] != MODEL_RUNTIME for result in model_results
        ):
            raise RuntimeError("two-root fit or runtime proof differs")
        _compare_runs(model_results[0], model_results[1])
        print(
            json.dumps(
                {
                    "status": "R3B_GLOBAL_RUNNER_SYNTHETIC_ACCEPTED_V5",
                    "runs": model_results,
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    if "--cell" in sys.argv:
        offset = sys.argv.index("--cell")
        cell_state_path = Path(sys.argv[offset + 1])
        cell_state = json.loads(cell_state_path.read_text())
        cell_stage = sys.argv[offset + 2]
        cell_endpoint = sys.argv[offset + 3]
        cell_repeat = int(sys.argv[offset + 4])
        cell_outer = int(sys.argv[offset + 5])
        cell_inner_text = sys.argv[offset + 6]
        cell_output = Path(sys.argv[offset + 7])
        cell_token_text = sys.argv[offset + 8]
        print(
            json.dumps(
                _run_one_cell(
                    cell_state,
                    stage=cell_stage,
                    endpoint=cell_endpoint,
                    repeat=cell_repeat,
                    outer=cell_outer,
                    inner=None if cell_inner_text == "none" else int(cell_inner_text),
                    output_root=cell_output,
                    token=None if cell_token_text == "none" else Path(cell_token_text),
                ),
                sort_keys=True,
            )
        )
    elif "--child" in sys.argv:
        state_path = Path(sys.argv[sys.argv.index("--child") + 1])
        run_root = Path(sys.argv[sys.argv.index("--child") + 2])
        print(json.dumps(_run_child(state_path, run_root), sort_keys=True))
    else:
        raise SystemExit(main())

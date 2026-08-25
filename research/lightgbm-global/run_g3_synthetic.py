#!/usr/bin/env python3
"""Run the bounded and one-shot formal EXP-G3 synthetic acceptance."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import resource
import shutil
import subprocess
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Final, cast

import g3_runner as g3
import numpy as np

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
PROJECT: Final = SCRIPT.parent
TEST_PATH: Final = (
    ROOT / "tests" / "test_openadmet_global_v2_g3_synthetic_implementation.py"
)
DEFAULT_PARENT: Final = Path("/tmp/cypshift-g3-synthetic-v1")
DEFAULT_ROOT_A: Final = DEFAULT_PARENT / "g3-synthetic-attempt-1-root-a"
DEFAULT_ROOT_B: Final = DEFAULT_PARENT / "g3-synthetic-attempt-1-root-b"
DEFAULT_RECEIPT: Final = DEFAULT_PARENT / "g3-synthetic-attempt-1-receipt"
DEFAULT_CACHE: Final = DEFAULT_PARENT / "g3-synthetic-attempt-1-cache"
EXPECTED_VERSIONS: Final = {
    "lightgbm": "4.7.0",
    "numpy": "2.5.2",
    "rdkit": "2026.3.5",
    "scipy": "1.18.0",
}
FORMAL_ENVIRONMENT: Final = {
    "PYTHONHASHSEED": "0",
    "OMP_NUM_THREADS": "16",
    "OMP_DYNAMIC": "FALSE",
    "MKL_NUM_THREADS": "16",
    "MKL_DYNAMIC": "FALSE",
    "OPENBLAS_NUM_THREADS": "16",
    "NUMEXPR_NUM_THREADS": "16",
    "UV_OFFLINE": "1",
}


def directory_bytes(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def source_bindings() -> dict[str, str]:
    paths = {
        "g3_synthetic_contract_sha256": g3.CONTRACT_PATH,
        "g3_single_expert_contract_sha256": g3.PARENT_PATH,
        "research_python_pin_sha256": PROJECT / ".python-version",
        "research_pyproject_sha256": PROJECT / "pyproject.toml",
        "research_uv_lock_sha256": PROJECT / "uv.lock",
        "g3_runner_sha256": g3.SCRIPT,
        "g3_synthetic_driver_sha256": SCRIPT,
        "focused_test_sha256": TEST_PATH,
    }
    return {name: g3.sha256_path(path) for name, path in paths.items()}


def environment_receipt() -> dict[str, object]:
    versions = {name: importlib.metadata.version(name) for name in EXPECTED_VERSIONS}
    g3.require(versions == EXPECTED_VERSIONS, "formal package versions differ")
    g3.require(sys.version_info[:3] == (3, 12, 3), "formal Python version differs")
    return {
        "python": ".".join(str(value) for value in sys.version_info[:3]),
        "packages": versions,
        "executable": str(Path(sys.executable).resolve()),
        "source_bindings": source_bindings(),
    }


def run_bounded_smoke(*, output_path: Path, reverse: bool) -> Path:
    """Run one non-authoritative tiny 16-round, one-thread API smoke."""

    import lightgbm as lgb

    g3.require(
        not output_path.exists() and not output_path.is_symlink(), "smoke output exists"
    )
    matrix = g3.build_feature_matrix(np.arange(64), reverse_physical=reverse)
    target = 4.0 + 0.01 * matrix[:48, :16].sum(axis=1)
    parameters = g3.model_parameters()
    parameters["num_threads"] = 1
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        booster = lgb.train(
            parameters,
            lgb.Dataset(matrix[:48], label=target),
            num_boost_round=16,
        )
        predictions = np.asarray(booster.predict(matrix[48:]), dtype=np.float64)
    g3.require(not caught, "bounded smoke emitted a warning")
    g3.require(
        predictions.shape == (16,) and np.isfinite(predictions).all(),
        "bounded smoke predictions differ",
    )
    resolved = {
        name: value.item() if isinstance(value, np.generic) else value
        for name, value in booster.params.items()
        if name in parameters
    }
    g3.require(resolved == parameters, "bounded smoke resolved parameters differ")
    g3.require(booster.current_iteration() == 16, "bounded smoke tree count differs")
    resolved_receipt = {"num_boost_round": 16, "parameters": resolved}
    receipt = {
        "schema_version": "cypshift.openadmet_cyp_2026.g3_bounded_smoke.v1",
        "contract_sha256": g3.CONTRACT_SHA256,
        "reverse_physical_order": reverse,
        "rows": 64,
        "columns": g3.FEATURE_WIDTH,
        "training_rows": 48,
        "prediction_rows": 16,
        "num_boost_round": 16,
        "num_threads": 1,
        "finite_predictions": 16,
        "resolved_parameter_sha256": g3.sha256_bytes(g3.json_bytes(resolved_receipt)),
        "prediction_sha256": g3.sha256_bytes(g3.little_f8_bytes(predictions)),
        "resource_timing_authority": False,
        "model_quality_authority": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(g3.json_bytes(receipt))
    return output_path


def run_fit_child(*, matrix_root: Path, endpoint: str, output_path: Path) -> None:
    g3.require(endpoint in g3.ENDPOINTS, "probe endpoint differs")
    g3.require(
        not output_path.exists() and not output_path.is_symlink(), "fit output exists"
    )
    train = np.load(matrix_root / "train.npy", mmap_mode="r")
    predict = np.load(matrix_root / "predict.npy", mmap_mode="r")
    targets = np.load(matrix_root / "targets.npy", mmap_mode="r")
    endpoint_index = g3.ENDPOINTS.index(endpoint)
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    predictions, resolved = g3.fit_exact_lightgbm(
        train, targets[:, endpoint_index], predict
    )
    wall = time.perf_counter() - start_wall
    cpu = time.process_time() - start_cpu
    usage = resource.getrusage(resource.RUSAGE_SELF)
    resolved_sha = g3.sha256_bytes(g3.json_bytes(resolved))
    result = {
        "schema_version": "cypshift.openadmet_cyp_2026.g3_probe_fit_private.v1",
        "endpoint": endpoint,
        "resolved_parameter_sha256": resolved_sha,
        "resolved_parameters": resolved,
        "predictions": [format(float(value), ".17g") for value in predictions],
        "prediction_sha256": g3.sha256_bytes(g3.little_f8_bytes(predictions)),
        "wall_seconds": wall,
        "cpu_seconds": cpu,
        "peak_rss_kib": int(usage.ru_maxrss),
        "python_warnings": 0,
        "fallbacks": 0,
        "gpu_hours": 0,
    }
    output_path.write_bytes(g3.json_bytes(result))


def _write_root_files(root: Path, files: dict[str, bytes]) -> None:
    root.mkdir(parents=True)
    for name in g3.TERMINAL_NAMES:
        (root / name).write_bytes(files[name])


def run_formal_root(
    *,
    root: Path,
    reverse: bool,
    environment_bytes: int,
    cache_bytes: int,
) -> tuple[Path, Path]:
    """Run one exact root and return its scientific and private receipt roots."""

    private = root.with_name(f".{root.name}-private")
    g3.require(
        not root.exists() and not root.is_symlink(), "formal scientific root exists"
    )
    g3.require(
        not private.exists() and not private.is_symlink(), "formal private root exists"
    )
    private.mkdir(parents=True)
    matrix_root = private / "matrix"
    matrix_root.mkdir()
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    model_double = g3.model_double_files(reverse_execution_order=reverse)
    train, predict, targets = g3.probe_matrix(reverse_physical=reverse)
    np.save(matrix_root / "train.npy", train, allow_pickle=False)
    np.save(matrix_root / "predict.npy", predict, allow_pickle=False)
    np.save(matrix_root / "targets.npy", targets, allow_pickle=False)
    del train, predict, targets
    endpoints = list(g3.ENDPOINTS)
    if reverse:
        endpoints.reverse()
    child_results: list[dict[str, Any]] = []
    for endpoint in endpoints:
        output_path = private / f"fit-{endpoint}.json"
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "fit-child",
                "--matrix-root",
                str(matrix_root),
                "--endpoint",
                endpoint,
                "--output",
                str(output_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=dict(os.environ),
        )
        g3.require(
            completed.returncode == 0,
            f"probe child failed for {endpoint}: {completed.stderr[-1000:]}",
        )
        g3.require(
            not completed.stderr.strip(), f"probe child stderr differs for {endpoint}"
        )
        child_results.append(cast(dict[str, Any], json.loads(output_path.read_text())))
    resolved_hashes = {str(row["resolved_parameter_sha256"]) for row in child_results}
    g3.require(len(resolved_hashes) == 1, "within-root resolved parameters differ")
    parameter_rows: list[dict[str, object]] = []
    prediction_rows: list[dict[str, object]] = []
    for child in child_results:
        endpoint = str(child["endpoint"])
        parameter_rows.append(
            {
                "endpoint": endpoint,
                "resolved_parameter_sha256": child["resolved_parameter_sha256"],
                "num_boost_round": g3.NUM_BOOST_ROUND,
                "training_rows": g3.PROBE_TRAIN_ROWS,
                "prediction_rows": g3.PROBE_PREDICT_ROWS,
                "columns": g3.FEATURE_WIDTH,
            }
        )
        prediction_rows.extend(
            {
                "endpoint": endpoint,
                "row_index": g3.PROBE_TRAIN_ROWS + offset,
                "prediction": value,
            }
            for offset, value in enumerate(child["predictions"])
        )
    files = g3.complete_terminal_files(
        model_double=model_double,
        probe_parameter_rows=parameter_rows,
        probe_prediction_rows=prediction_rows,
    )
    _write_root_files(root, files)
    total_wall = time.perf_counter() - start_wall
    total_cpu = (
        time.process_time()
        - start_cpu
        + sum(float(row["cpu_seconds"]) for row in child_results)
    )
    parent_rss_kib = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    maximum_rss_kib = max(
        parent_rss_kib, *(int(row["peak_rss_kib"]) for row in child_results)
    )
    source_bytes = directory_bytes(ROOT)
    work_bytes = directory_bytes(root) + directory_bytes(private)
    storage_bytes = (
        environment_bytes
        + cache_bytes
        + source_bytes
        + work_bytes
        + maximum_rss_kib * 1024
    )
    observation = {
        "schema_version": "cypshift.openadmet_cyp_2026.g3_resource_observations.v1",
        "contract_sha256": g3.CONTRACT_SHA256,
        "reverse_physical_order": reverse,
        "root_total_wall_seconds": total_wall,
        "root_total_cpu_seconds": total_cpu,
        "nonfit_wall_seconds_for_projection": total_wall,
        "nonfit_cpu_seconds_for_projection": total_cpu,
        "maximum_individual_fit_wall_seconds": max(
            float(row["wall_seconds"]) for row in child_results
        ),
        "maximum_individual_fit_cpu_seconds": max(
            float(row["cpu_seconds"]) for row in child_results
        ),
        "maximum_peak_rss_kib": maximum_rss_kib,
        "simultaneous_restricted_storage_bytes": storage_bytes,
        "environment_bytes": environment_bytes,
        "cache_bytes": cache_bytes,
        "source_bytes": source_bytes,
        "work_bytes": work_bytes,
        "fits_completed": len(child_results),
        "predictions_completed": sum(len(row["predictions"]) for row in child_results),
        "python_warnings": sum(int(row["python_warnings"]) for row in child_results),
        "fallbacks": sum(int(row["fallbacks"]) for row in child_results),
        "nonzero_exits": 0,
        "gpu_hours": 0,
        "projection_conservatism": "Full root wall/CPU is added as non-fit overhead; exact probe fit time is not subtracted.",
    }
    (private / "resource_observations.json").write_bytes(g3.json_bytes(observation))
    shutil.rmtree(matrix_root)
    for output_path in private.glob("fit-*.json"):
        output_path.unlink()
    return root, private


def deterministic_receipts(root: Path) -> dict[str, str]:
    return {name: g3.sha256_path(root / name) for name in g3.TERMINAL_NAMES}


def project_resources(private_a: Path, private_b: Path) -> dict[str, object]:
    observations = [
        cast(
            dict[str, Any],
            json.loads((root / "resource_observations.json").read_text()),
        )
        for root in (private_a, private_b)
    ]
    maximum_fit_wall = max(
        float(row["maximum_individual_fit_wall_seconds"]) for row in observations
    )
    maximum_fit_cpu = max(
        float(row["maximum_individual_fit_cpu_seconds"]) for row in observations
    )
    nonfit_wall = max(
        float(row["nonfit_wall_seconds_for_projection"]) for row in observations
    )
    nonfit_cpu = max(
        float(row["nonfit_cpu_seconds_for_projection"]) for row in observations
    )
    projected_wall_hours = (60 * maximum_fit_wall + nonfit_wall) / 3600
    projected_cpu_hours = (60 * maximum_fit_cpu + nonfit_cpu) / 3600
    storage_gb = (
        max(int(row["simultaneous_restricted_storage_bytes"]) for row in observations)
        / 1_000_000_000
    )
    rss_gib = (
        max(int(row["maximum_peak_rss_kib"]) for row in observations) * 1024 / (1024**3)
    )
    gpu_hours = max(int(row["gpu_hours"]) for row in observations)
    gates = {
        "cpu_core_hours": projected_cpu_hours <= 128,
        "wall_hours": projected_wall_hours <= 19.2,
        "restricted_storage_gb": storage_gb <= 25.6,
        "peak_rss_gib": rss_gib <= 19.2,
        "gpu_hours": gpu_hours == 0,
        "warnings": sum(int(row["python_warnings"]) for row in observations) == 0,
        "fallbacks": sum(int(row["fallbacks"]) for row in observations) == 0,
        "nonzero_exits": sum(int(row["nonzero_exits"]) for row in observations) == 0,
    }
    return {
        "schema_version": "cypshift.openadmet_cyp_2026.g3_resource_projection.v1",
        "scientific_fits": 60,
        "worse_root_maximum_fit_wall_seconds": maximum_fit_wall,
        "worse_root_maximum_fit_cpu_seconds": maximum_fit_cpu,
        "worse_root_nonfit_wall_seconds": nonfit_wall,
        "worse_root_nonfit_cpu_seconds": nonfit_cpu,
        "projected_wall_hours": projected_wall_hours,
        "projected_cpu_core_hours": projected_cpu_hours,
        "restricted_storage_gb": storage_gb,
        "peak_rss_gib": rss_gib,
        "gpu_hours": gpu_hours,
        "maximums": {
            "projected_wall_hours": 19.2,
            "projected_cpu_core_hours": 128,
            "restricted_storage_gb": 25.6,
            "peak_rss_gib": 19.2,
            "gpu_hours": 0,
        },
        "gates": gates,
        "accepted": all(gates.values()),
    }


def _network_isolated() -> bool:
    routes = Path("/proc/net/route").read_text().splitlines()[1:]
    return not any(line.split()[0] != "lo" for line in routes if line.split())


def consume_formal(*, cache_root: Path) -> Path:
    """Consume the one formal attempt, publish aggregate evidence, and clean."""

    for path, expected_name in (
        (DEFAULT_ROOT_A, "g3-synthetic-attempt-1-root-a"),
        (DEFAULT_ROOT_B, "g3-synthetic-attempt-1-root-b"),
        (DEFAULT_RECEIPT, "g3-synthetic-attempt-1-receipt"),
        (cache_root, "g3-synthetic-attempt-1-cache"),
    ):
        g3.require(path.name == expected_name, f"unsafe formal path: {path}")
    for path in (DEFAULT_ROOT_A, DEFAULT_ROOT_B, DEFAULT_RECEIPT):
        g3.require(
            not path.exists() and not path.is_symlink(), f"formal path exists: {path}"
        )
    g3.require(
        cache_root.exists() and cache_root.is_dir() and not cache_root.is_symlink(),
        "dedicated cache differs",
    )
    g3.require(
        all(
            os.environ.get(name) == value for name, value in FORMAL_ENVIRONMENT.items()
        ),
        "formal environment differs",
    )
    g3.require(_network_isolated(), "formal network namespace is not isolated")
    environment = environment_receipt()
    environment_root = PROJECT / ".venv"
    g3.require(
        environment_root.exists() and not environment_root.is_symlink(),
        "isolated environment differs",
    )
    DEFAULT_RECEIPT.mkdir(parents=True)
    attempt = {
        "schema_version": "cypshift.openadmet_cyp_2026.g3_formal_attempt_consumption.v1",
        "attempt_id": "EXP-G3-SYNTHETIC-ATTEMPT-1",
        "contract_sha256": g3.CONTRACT_SHA256,
        "source_bindings": source_bindings(),
        "consumed": True,
    }
    (DEFAULT_RECEIPT / "attempt_consumption.json").write_bytes(g3.json_bytes(attempt))
    status = "G2_6S_G3_SYNTHETIC_REJECTED"
    private_a = DEFAULT_ROOT_A.with_name(f".{DEFAULT_ROOT_A.name}-private")
    private_b = DEFAULT_ROOT_B.with_name(f".{DEFAULT_ROOT_B.name}-private")
    try:
        environment_bytes = directory_bytes(environment_root)
        cache_bytes = directory_bytes(cache_root)
        run_formal_root(
            root=DEFAULT_ROOT_A,
            reverse=False,
            environment_bytes=environment_bytes,
            cache_bytes=cache_bytes,
        )
        run_formal_root(
            root=DEFAULT_ROOT_B,
            reverse=True,
            environment_bytes=environment_bytes,
            cache_bytes=cache_bytes,
        )
        receipts_a = deterministic_receipts(DEFAULT_ROOT_A)
        receipts_b = deterministic_receipts(DEFAULT_ROOT_B)
        g3.require(
            receipts_a == receipts_b, "cross-root deterministic terminal differs"
        )
        manifest = cast(
            dict[str, Any],
            json.loads((DEFAULT_ROOT_A / g3.TERMINAL_NAMES[-1]).read_text()),
        )
        projection = project_resources(private_a, private_b)
        status = (
            "G2_6S_G3_SYNTHETIC_ACCEPTED"
            if projection["accepted"]
            else "G2_6S_G3_RESOURCE_REJECTED"
        )
        result = {
            "schema_version": "cypshift.openadmet_cyp_2026.g3_synthetic_acceptance.v1",
            "recorded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": status,
            "experiment_id": "EXP-G3",
            "attempt_id": attempt["attempt_id"],
            "contract_sha256": g3.CONTRACT_SHA256,
            "parent_contract_sha256": g3.PARENT_SHA256,
            "source_bindings": source_bindings(),
            "environment": environment,
            "deterministic_terminal_receipts": receipts_a,
            "deterministic_tree_sha256": manifest["deterministic_tree_sha256"],
            "cross_root_byte_identical": True,
            "mechanics": {
                "roots_completed": 2,
                "model_double_fits": 120,
                "model_double_outer_predictions": 1920,
                "real_lightgbm_fits": 8,
                "real_lightgbm_predictions": 6304,
                "resolved_parameter_hashes": 1,
                "component_crossings": 0,
                "confirmatory_truth_values_parsed": 0,
                "warnings": 0,
                "fallbacks": 0,
                "nonzero_exits": 0,
            },
            "resource_projection": projection,
            "accounting": {name: 0 for name in g3.OFFICIAL_ZERO_FIELDS},
            "scientific_interpretation": "Synthetic mechanics and resources only; no model-quality interpretation.",
        }
        (DEFAULT_RECEIPT / "result.json").write_bytes(g3.json_bytes(result))
    except Exception as error:
        failure = {
            "schema_version": "cypshift.openadmet_cyp_2026.g3_synthetic_failure.v1",
            "status": status,
            "error_type": type(error).__name__,
            "error": str(error),
            "contract_sha256": g3.CONTRACT_SHA256,
            "accounting": {name: 0 for name in g3.OFFICIAL_ZERO_FIELDS},
        }
        (DEFAULT_RECEIPT / "failure.json").write_bytes(g3.json_bytes(failure))
        raise
    finally:
        for path in (DEFAULT_ROOT_A, DEFAULT_ROOT_B, private_a, private_b):
            if path.exists() and not path.is_symlink():
                shutil.rmtree(path)
        if cache_root.exists() and not cache_root.is_symlink():
            shutil.rmtree(cache_root)
        cleanup = {
            "root_a_absent": not DEFAULT_ROOT_A.exists(),
            "root_b_absent": not DEFAULT_ROOT_B.exists(),
            "private_root_a_absent": not private_a.exists(),
            "private_root_b_absent": not private_b.exists(),
            "dedicated_cache_absent": not cache_root.exists(),
        }
        (DEFAULT_RECEIPT / "cleanup.json").write_bytes(g3.json_bytes(cleanup))
        g3.require(all(cleanup.values()), "formal cleanup differs")
    return DEFAULT_RECEIPT


def launch_formal(*, cache_root: Path) -> None:
    if os.environ.get("CYPSHIFT_G3_NETWORK_ISOLATED") != "1":
        environment = dict(os.environ)
        environment.update(FORMAL_ENVIRONMENT)
        environment["CYPSHIFT_G3_NETWORK_ISOLATED"] = "1"
        arguments = [
            "unshare",
            "--user",
            "--map-root-user",
            "--net",
            sys.executable,
            str(SCRIPT),
            "formal",
            "--cache-root",
            str(cache_root),
        ]
        os.execvpe("unshare", arguments, environment)
    consume_formal(cache_root=cache_root)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    model_double = subparsers.add_parser("model-double")
    model_double.add_argument("--output-root", type=Path, required=True)
    model_double.add_argument("--reverse", action="store_true")
    smoke = subparsers.add_parser("smoke")
    smoke.add_argument("--output", type=Path, required=True)
    smoke.add_argument("--reverse", action="store_true")
    child = subparsers.add_parser("fit-child")
    child.add_argument("--matrix-root", type=Path, required=True)
    child.add_argument("--endpoint", required=True)
    child.add_argument("--output", type=Path, required=True)
    formal = subparsers.add_parser("formal")
    formal.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args()
    if args.command == "model-double":
        output = cast(Path, args.output_root)
        g3.require(
            not output.exists() and not output.is_symlink(), "model-double root exists"
        )
        files = g3.model_double_files(reverse_execution_order=bool(args.reverse))
        output.mkdir(parents=True)
        for name, value in files.items():
            (output / name).write_bytes(value)
    elif args.command == "smoke":
        run_bounded_smoke(output_path=args.output, reverse=bool(args.reverse))
    elif args.command == "fit-child":
        run_fit_child(
            matrix_root=args.matrix_root,
            endpoint=args.endpoint,
            output_path=args.output,
        )
    else:
        launch_formal(cache_root=args.cache_root)


if __name__ == "__main__":
    main()

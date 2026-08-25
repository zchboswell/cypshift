#!/usr/bin/env python3
"""Build EXP-M1 synthetic mechanics receipts and bounded API smokes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import resource
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from multiprocessing import get_context
from pathlib import Path
from typing import Any, Final, cast

import m1_runner as m1
import numpy as np

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
sys.path.insert(0, str(ROOT / "src"))
PROBE_FIELDS: Final = (
    "batch_index",
    "slot_index",
    "pid",
    "probe_label",
    "architecture_class",
    "loss_id",
    "model_seed",
    "child_wall_seconds",
    "child_cpu_seconds",
    "peak_rss_kib",
    "parameter_sha256",
    "prediction_sha256",
    "prediction_rows",
    "prediction_columns",
)


def component_pool() -> tuple[list[str], list[str]]:
    development: list[str] = []
    confirmatory: list[str] = []
    counter = 0
    while len(development) < 40 or len(confirmatory) < 10:
        component = hashlib.sha256(
            f"cypshift-m1-synthetic-component-v1|{counter}".encode()
        ).hexdigest()
        material = f"openadmet-global-v2-confirmatory-v1|20260824|{component}"
        value = int.from_bytes(hashlib.sha256(material.encode()).digest()[:8], "big")
        target = confirmatory if value % 5 == 0 else development
        limit = 10 if target is confirmatory else 40
        if len(target) < limit:
            target.append(component)
        counter += 1
    return development, confirmatory


def build_fixture(*, reverse: bool) -> dict[str, Any]:
    """Create the exact 100-molecule family, structure, fold, and mask fixture."""

    from cypshift.chemistry import standardize_molecule
    from cypshift.schema import MoleculeInput, MoleculeStatus

    development, confirmatory = component_pool()
    components = development + confirmatory
    molecules: list[dict[str, object]] = []
    truth: list[dict[str, object]] = []
    for index in range(100):
        molecule_id = f"m1-synthetic-{index:03d}"
        smiles = "C" * (index + 1)
        record = standardize_molecule(
            MoleculeInput(molecule_id, smiles, "smiles", "g2-4b-synthetic", "{}")
        )
        m1.require(
            record.status is MoleculeStatus.ACCEPTED, "synthetic structure rejected"
        )
        m1.require(
            record.standardized_structure == smiles, "synthetic standardization differs"
        )
        component = components[index // 2]
        partition = "development" if component in development else "confirmatory"
        molecules.append(
            {
                "molecule_id": molecule_id,
                "component": component,
                "partition": partition,
                "standardized_smiles": smiles,
                "standardized_structure_hash": hashlib.sha256(
                    smiles.encode()
                ).hexdigest(),
            }
        )
        if partition == "development":
            development_index = index
            for endpoint_index, endpoint in enumerate(m1.ENDPOINTS):
                finite = (development_index + endpoint_index) % 5 != 0
                interval = finite and (development_index + 2 * endpoint_index) % 4 != 0
                point = (
                    4.0
                    + 0.025 * development_index
                    + 0.2 * endpoint_index
                    + 0.05 * ((7 * development_index + endpoint_index) % 5)
                )
                std_finite = (
                    interval and (development_index + 3 * endpoint_index) % 3 != 0
                )
                truth.append(
                    {
                        "molecule_id": molecule_id,
                        "component": component,
                        "endpoint": endpoint,
                        "central": point if finite else None,
                        "lower": point - (0.15 + 0.01 * endpoint_index)
                        if interval
                        else None,
                        "upper": point + (0.15 + 0.01 * endpoint_index)
                        if interval
                        else None,
                        "std": 0.05 + 0.005 * endpoint_index if std_finite else None,
                    }
                )
    folds: list[dict[str, object]] = []
    molecules_by_component: dict[str, list[str]] = {}
    for row in molecules:
        if row["partition"] == "development":
            molecules_by_component.setdefault(cast(str, row["component"]), []).append(
                cast(str, row["molecule_id"])
            )
    for repeat_seed in m1.REPEAT_SEEDS:
        outer_order = sorted(
            development,
            key=lambda component: hashlib.sha256(
                f"{repeat_seed}|OUTER|{component}".encode()
            ).hexdigest(),
        )
        outer_by_component = {
            component: rank % 5 for rank, component in enumerate(outer_order)
        }
        for outer_fold in m1.OUTER_FOLDS:
            training = [
                component
                for component in development
                if outer_by_component[component] != outer_fold
            ]
            inner_order = sorted(
                training,
                key=lambda component: hashlib.sha256(
                    f"{repeat_seed}|{outer_fold}|INNER|{component}".encode()
                ).hexdigest(),
            )
            inner_by_component = {
                component: rank % 4 for rank, component in enumerate(inner_order)
            }
            for component in development:
                for molecule_id in molecules_by_component[component]:
                    folds.append(
                        {
                            "molecule_id": molecule_id,
                            "component": component,
                            "repeat_seed": repeat_seed,
                            "outer_fold": outer_fold,
                            "is_outer_validation": outer_by_component[component]
                            == outer_fold,
                            "inner_fold": inner_by_component.get(component),
                        }
                    )
    if reverse:
        molecules.reverse()
        truth.reverse()
        folds.reverse()
    return {"molecules": molecules, "development_truth": truth, "folds": folds}


def fixture_receipt(fixture: dict[str, Any]) -> dict[str, object]:
    molecules = fixture["molecules"]
    truth = fixture["development_truth"]
    folds = fixture["folds"]
    counts_by_endpoint: dict[str, dict[str, int]] = {}
    for endpoint in m1.ENDPOINTS:
        rows = [row for row in truth if row["endpoint"] == endpoint]
        counts_by_endpoint[endpoint] = {
            "finite_central": sum(row["central"] is not None for row in rows),
            "interval_eligible": sum(
                row["lower"] is not None and row["upper"] is not None for row in rows
            ),
            "point_only": sum(
                row["central"] is not None and row["lower"] is None for row in rows
            ),
            "missing_central": sum(row["central"] is None for row in rows),
        }
    canonical = {
        "molecules": sorted(molecules, key=lambda row: str(row["molecule_id"])),
        "development_truth": sorted(
            truth, key=lambda row: (str(row["molecule_id"]), str(row["endpoint"]))
        ),
        "folds": sorted(
            folds,
            key=lambda row: (
                int(row["repeat_seed"]),
                int(row["outer_fold"]),
                str(row["molecule_id"]),
            ),
        ),
    }
    return {
        "schema_version": "cypshift.openadmet_cyp_2026.m1_fixture_receipt.v1",
        "contract_sha256": m1.CONTRACT_SHA256,
        "molecules": len(molecules),
        "development_molecules": sum(
            row["partition"] == "development" for row in molecules
        ),
        "confirmatory_molecules": sum(
            row["partition"] == "confirmatory" for row in molecules
        ),
        "development_truth_rows": len(truth),
        "confirmatory_truth_values_parsed": 0,
        "fold_rows": len(folds),
        "counts_by_endpoint": counts_by_endpoint,
        "canonical_fixture_sha256": m1.sha256_bytes(m1.json_bytes(canonical)),
    }


def publish_model_double(*, output_root: Path, reverse: bool) -> Path:
    m1.require(
        not output_root.exists() and not output_root.is_symlink(), "output root exists"
    )
    fixture = build_fixture(reverse=reverse)
    files = m1.model_double_files(reverse_execution_order=reverse)
    files["fixture_receipt.json"] = m1.json_bytes(fixture_receipt(fixture))
    output_root.mkdir(parents=True)
    for name, value in files.items():
        (output_root / name).write_bytes(value)
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.m1_model_double_root.v1",
        "contract_sha256": m1.CONTRACT_SHA256,
        "files": {name: m1.sha256_path(output_root / name) for name in sorted(files)},
        "accounting": {name: 0 for name in m1.OFFICIAL_ZERO_FIELDS},
        "scientific_interpretation": "Synthetic mechanics only; no model-quality interpretation.",
    }
    (output_root / "manifest.json").write_bytes(m1.json_bytes(manifest))
    return output_root


def _smoke_data() -> tuple[np.ndarray[Any, Any], ...]:
    rng = np.random.Generator(np.random.PCG64(20260830))
    raw = rng.normal(size=(80, m1.FEATURE_WIDTH)).astype(np.float64)
    raw[:, : m1.MORGAN_WIDTH] = rng.integers(
        0, 5, size=(80, m1.MORGAN_WIDTH), dtype=np.int32
    )
    raw[::7, m1.MORGAN_WIDTH + 3] = np.nan
    transformed, _receipt = m1.preprocess_features(raw, np.arange(64))
    central = np.empty((64, 4), dtype=np.float32)
    for endpoint in range(4):
        central[:, endpoint] = 4.0 + transformed[:64, endpoint] * 0.1 + endpoint * 0.2
    lower = central - 0.15
    upper = central + 0.15
    central[::11, 0] = np.nan
    lower[::13, 1] = np.nan
    upper[::13, 1] = np.nan
    return transformed[:64], central, lower, upper, transformed[64:]


def run_bounded_smokes(*, output_path: Path) -> Path:
    """Run exactly four authorized API smokes; never use their timing as evidence."""

    m1.require(
        not output_path.exists() and not output_path.is_symlink(), "smoke output exists"
    )
    environment = {
        "PYTHONHASHSEED": "0",
        "OMP_NUM_THREADS": "4",
        "OMP_DYNAMIC": "FALSE",
        "MKL_NUM_THREADS": "4",
        "MKL_DYNAMIC": "FALSE",
        "OPENBLAS_NUM_THREADS": "4",
        "NUMEXPR_NUM_THREADS": "4",
    }
    for name, value in environment.items():
        os.environ[name] = value
    m1.configure_torch_runtime(threads=4, interop_threads=1)
    train_x, central, lower, upper, predict_x = _smoke_data()
    identities = [
        m1.FitIdentity(
            "OUTER", "SHARED", 20260810, 0, None, "CENTRAL_MAE", 20260824, None
        ),
        m1.FitIdentity(
            "OUTER", "PERMUTED", 20260810, 0, None, "INTERVAL_DEAD_ZONE", 20260824, None
        ),
        m1.FitIdentity(
            "OUTER", "INDEPENDENT", 20260810, 0, None, "CENTRAL_MAE", 20260824, "CYP1A2"
        ),
        m1.FitIdentity(
            "OUTER",
            "INDEPENDENT",
            20260810,
            0,
            None,
            "INTERVAL_DEAD_ZONE",
            20260824,
            "CYP2C9",
        ),
    ]
    results = []
    for identity in identities:
        result = m1.fit_torch_model(
            identity=identity,
            train_features=train_x,
            train_central=central,
            train_lower=lower,
            train_upper=upper,
            prediction_features=predict_x,
            epochs=3,
        )
        results.append(
            {
                "identity": cast(dict[str, object], m1.asdict(identity)),
                **m1.asdict(result),
            }
        )
    receipt = {
        "schema_version": "cypshift.openadmet_cyp_2026.m1_bounded_smoke_receipt.v1",
        "contract_sha256": m1.CONTRACT_SHA256,
        "runner_sha256": m1.sha256_path(m1.SCRIPT),
        "driver_sha256": m1.sha256_path(SCRIPT),
        "fits": len(results),
        "maximum_training_rows": 64,
        "epochs_per_fit": 3,
        "maximum_concurrent_fits": 1,
        "resource_timing_authority": False,
        "scientific_interpretation": "API correctness only; no resource or model-quality interpretation.",
        "results": results,
        "accounting": {name: 0 for name in m1.OFFICIAL_ZERO_FIELDS},
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(m1.json_bytes(receipt))
    return output_path


def probe_identities() -> list[list[tuple[str, m1.FitIdentity]]]:
    """Return the four exact four-worker batches frozen by D-103."""

    def shared(system: m1.SystemId, loss: m1.LossId, seed: int) -> m1.FitIdentity:
        return m1.FitIdentity("OUTER", system, 20260810, 0, None, loss, seed, None)

    def independent(loss: m1.LossId, seed: int) -> m1.FitIdentity:
        return m1.FitIdentity(
            "OUTER",
            "INDEPENDENT",
            20260810,
            0,
            None,
            loss,
            seed,
            "CYP1A2",
        )

    return [
        [
            ("shared CENTRAL seed 20260824", shared("SHARED", "CENTRAL_MAE", 20260824)),
            ("shared CENTRAL seed 20260825", shared("SHARED", "CENTRAL_MAE", 20260825)),
            (
                "shared INTERVAL seed 20260824",
                shared("SHARED", "INTERVAL_DEAD_ZONE", 20260824),
            ),
            (
                "shared INTERVAL seed 20260825",
                shared("SHARED", "INTERVAL_DEAD_ZONE", 20260825),
            ),
        ],
        [
            ("shared CENTRAL seed 20260826", shared("SHARED", "CENTRAL_MAE", 20260826)),
            (
                "shared INTERVAL seed 20260826",
                shared("SHARED", "INTERVAL_DEAD_ZONE", 20260826),
            ),
            (
                "permuted CENTRAL seed 20260824",
                shared("PERMUTED", "CENTRAL_MAE", 20260824),
            ),
            (
                "permuted INTERVAL seed 20260824",
                shared("PERMUTED", "INTERVAL_DEAD_ZONE", 20260824),
            ),
        ],
        [
            ("independent CENTRAL seed 20260824", independent("CENTRAL_MAE", 20260824)),
            ("independent CENTRAL seed 20260825", independent("CENTRAL_MAE", 20260825)),
            (
                "independent INTERVAL seed 20260824",
                independent("INTERVAL_DEAD_ZONE", 20260824),
            ),
            (
                "independent INTERVAL seed 20260825",
                independent("INTERVAL_DEAD_ZONE", 20260825),
            ),
        ],
        [
            ("independent CENTRAL seed 20260826", independent("CENTRAL_MAE", 20260826)),
            (
                "independent INTERVAL seed 20260826",
                independent("INTERVAL_DEAD_ZONE", 20260826),
            ),
            (
                "independent CENTRAL seed 20260824 resource-repeat-1",
                independent("CENTRAL_MAE", 20260824),
            ),
            (
                "independent INTERVAL seed 20260824 resource-repeat-1",
                independent("INTERVAL_DEAD_ZONE", 20260824),
            ),
        ],
    ]


def _formal_matrices(root: Path) -> tuple[m1.PreprocessingReceipt, float, float]:
    before_wall = time.perf_counter_ns()
    before_cpu = time.process_time_ns()
    rng = np.random.Generator(np.random.PCG64(20260830))
    rows = 3908 + 997
    raw = np.empty((rows, m1.FEATURE_WIDTH), dtype=np.float32)
    raw[:, : m1.MORGAN_WIDTH] = rng.integers(
        0, 8, size=(rows, m1.MORGAN_WIDTH), dtype=np.int32
    )
    raw[:, m1.MORGAN_WIDTH :] = rng.normal(size=(rows, m1.DESCRIPTOR_WIDTH)).astype(
        np.float32
    )
    descriptor = raw[:, m1.MORGAN_WIDTH :]
    descriptor[::31, 0] = np.nan
    descriptor[::47, 1] = np.inf
    transformed, receipt = m1.preprocess_features(raw, np.arange(3908))
    central = np.empty((3908, 4), dtype=np.float32)
    for endpoint in range(4):
        central[:, endpoint] = (
            4.0
            + 0.05 * transformed[:3908, endpoint]
            + 0.03 * transformed[:3908, 2048 + endpoint]
            + 0.2 * endpoint
        )
    lower = central - np.asarray([0.15, 0.16, 0.17, 0.18], dtype=np.float32)
    upper = central + np.asarray([0.15, 0.16, 0.17, 0.18], dtype=np.float32)
    for endpoint in range(4):
        central[(np.arange(3908) + endpoint) % 5 == 0, endpoint] = np.nan
        interval_missing = (np.arange(3908) + 2 * endpoint) % 4 == 0
        lower[interval_missing, endpoint] = np.nan
        upper[interval_missing, endpoint] = np.nan
    arrays = {
        "train_features.npy": transformed[:3908],
        "prediction_features.npy": transformed[3908:],
        "central.npy": central,
        "lower.npy": lower,
        "upper.npy": upper,
    }
    root.mkdir(parents=True)
    for name, array in arrays.items():
        np.save(root / name, array, allow_pickle=False)
    wall = (time.perf_counter_ns() - before_wall) / 1e9
    cpu = (time.process_time_ns() - before_cpu) / 1e9
    return receipt, wall, cpu


def _probe_child(
    label: str,
    identity: m1.FitIdentity,
    matrix_root: str,
    affinity: tuple[int, ...],
    batch_index: int,
    slot_index: int,
) -> dict[str, object]:
    os.sched_setaffinity(0, affinity)
    os.environ.update(
        {
            "PYTHONHASHSEED": "0",
            "OMP_NUM_THREADS": "4",
            "OMP_DYNAMIC": "FALSE",
            "MKL_NUM_THREADS": "4",
            "MKL_DYNAMIC": "FALSE",
            "OPENBLAS_NUM_THREADS": "4",
            "NUMEXPR_NUM_THREADS": "4",
        }
    )
    m1.configure_torch_runtime(threads=4, interop_threads=1)
    root = Path(matrix_root)
    train_features = np.load(root / "train_features.npy", mmap_mode="r")
    prediction_features = np.load(root / "prediction_features.npy", mmap_mode="r")
    central = np.load(root / "central.npy", mmap_mode="r")
    lower = np.load(root / "lower.npy", mmap_mode="r")
    upper = np.load(root / "upper.npy", mmap_mode="r")
    before_wall = time.perf_counter_ns()
    result = m1.fit_torch_model(
        identity=identity,
        train_features=train_features,
        train_central=central,
        train_lower=lower,
        train_upper=upper,
        prediction_features=prediction_features,
        epochs=300,
    )
    after_usage = resource.getrusage(resource.RUSAGE_SELF)
    child_cpu = after_usage.ru_utime + after_usage.ru_stime
    return {
        "batch_index": batch_index,
        "slot_index": slot_index,
        "pid": os.getpid(),
        "probe_label": label,
        "architecture_class": (
            "independent" if identity.system == "INDEPENDENT" else "shared_or_permuted"
        ),
        "loss_id": identity.loss_id,
        "model_seed": identity.model_seed,
        "child_wall_seconds": (time.perf_counter_ns() - before_wall) / 1e9,
        "child_cpu_seconds": child_cpu,
        "peak_rss_kib": after_usage.ru_maxrss,
        "parameter_sha256": result.parameter_sha256,
        "prediction_sha256": result.prediction_sha256,
        "prediction_rows": result.prediction_rows,
        "prediction_columns": result.prediction_columns,
    }


def _directory_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def run_formal_probe_root(
    *, root: Path, reverse: bool, environment_bytes: int, cache_bytes: int
) -> Path:
    """Run one full formal root. Caller must consume a reviewed claim first."""

    m1.require(not root.exists() and not root.is_symlink(), "formal root exists")
    root_start_wall = time.perf_counter_ns()
    root_start_cpu = time.process_time_ns()
    private = root.with_name(f".{root.name}-private")
    m1.require(
        not private.exists() and not private.is_symlink(), "private formal root exists"
    )
    private.mkdir(parents=True)
    scientific = m1.model_double_files(reverse_execution_order=reverse)
    fixture = build_fixture(reverse=reverse)
    scientific["fixture_receipt.json"] = m1.json_bytes(fixture_receipt(fixture))
    matrix_root = private / "matrices"
    preprocessing, preprocessing_wall, preprocessing_cpu = _formal_matrices(matrix_root)
    batches = probe_identities()
    if reverse:
        batches = [list(reversed(batch)) for batch in reversed(batches)]
    rows: list[dict[str, object]] = []
    batch_walls: list[dict[str, object]] = []
    context = get_context("spawn")
    slots = ((0, 1, 2, 3), (4, 5, 6, 7), (8, 9, 10, 11), (12, 13, 14, 15))
    for execution_index, batch in enumerate(batches):
        scientific_batch_index = 3 - execution_index if reverse else execution_index
        start = time.perf_counter_ns()
        with ProcessPoolExecutor(max_workers=4, mp_context=context) as executor:
            futures = [
                executor.submit(
                    _probe_child,
                    label,
                    identity,
                    str(matrix_root),
                    slots[slot],
                    scientific_batch_index,
                    slot,
                )
                for slot, (label, identity) in enumerate(batch)
            ]
            batch_rows = [future.result() for future in futures]
        m1.require(
            len({int(row["pid"]) for row in batch_rows}) == 4,
            "probe batch did not use four distinct workers",
        )
        wall = (time.perf_counter_ns() - start) / 1e9
        batch_walls.append(
            {
                "batch_index": scientific_batch_index,
                "architecture_class": (
                    "shared_or_permuted"
                    if scientific_batch_index < 2
                    else "independent"
                ),
                "wall_seconds": wall,
            }
        )
        rows.extend(batch_rows)
    rows.sort(key=lambda row: str(row["probe_label"]))
    batch_walls.sort(key=lambda row: int(row["batch_index"]))
    total_wall = (time.perf_counter_ns() - root_start_wall) / 1e9
    total_cpu = (time.process_time_ns() - root_start_cpu) / 1e9 + sum(
        float(row["child_cpu_seconds"]) for row in rows
    )
    fixed_wrapper_wall_seconds = 60.0
    fixed_wrapper_cpu_seconds = 240.0
    nonfit_wall = fixed_wrapper_wall_seconds + max(
        0.0,
        total_wall
        - preprocessing_wall
        - sum(float(row["wall_seconds"]) for row in batch_walls),
    )
    nonfit_cpu = fixed_wrapper_cpu_seconds + max(
        0.0,
        total_cpu
        - preprocessing_cpu
        - sum(float(row["child_cpu_seconds"]) for row in rows),
    )
    scientific["runtime_probe_receipts.csv"] = m1.csv_bytes(PROBE_FIELDS, rows)
    scientific["resource_observations.json"] = m1.json_bytes(
        {
            "preprocessing": asdict(preprocessing),
            "preprocessing_wall_seconds": preprocessing_wall,
            "preprocessing_cpu_seconds": preprocessing_cpu,
            "batch_walls": batch_walls,
            "nonfit_nonpreprocessing_wall_seconds": nonfit_wall,
            "nonfit_nonpreprocessing_cpu_seconds": nonfit_cpu,
            "total_wall_seconds": total_wall,
            "total_cpu_seconds": total_cpu,
            "environment_bytes": environment_bytes,
            "cache_bytes": cache_bytes,
            "work_bytes": _directory_bytes(private)
            + sum(len(value) for value in scientific.values())
            + 1_000_000,
            "fixed_wrapper_wall_seconds": fixed_wrapper_wall_seconds,
            "fixed_wrapper_cpu_seconds": fixed_wrapper_cpu_seconds,
            "maximum_simultaneous_child_rss_kib": max(
                sum(
                    int(row["peak_rss_kib"])
                    for row in rows
                    if int(row["batch_index"]) == batch_index
                )
                for batch_index in range(4)
            ),
            "gpu_hours": 0,
        }
    )
    root.mkdir(parents=True)
    for name, value in scientific.items():
        (root / name).write_bytes(value)
    shutil.rmtree(private)
    m1.require(not private.exists(), "formal private cleanup differs")
    return root


def _read_probe_rows(root: Path) -> list[dict[str, str]]:
    return list(
        csv.DictReader(
            io.StringIO(
                (root / "runtime_probe_receipts.csv").read_text(encoding="utf-8"),
                newline="",
            )
        )
    )


def project_resources(root_a: Path, root_b: Path) -> dict[str, object]:
    """Apply the exact conservative worse-root formulas after exact replay."""

    observations = [
        cast(
            dict[str, Any],
            json.loads(
                (root / "resource_observations.json").read_text(encoding="utf-8")
            ),
        )
        for root in (root_a, root_b)
    ]
    rows = [_read_probe_rows(root) for root in (root_a, root_b)]
    for name in (
        "feature_preprocessing_receipt.json",
        "model_double_fit_receipts.csv",
        "loss_selection_receipts.csv",
        "prediction_receipts.json",
        "fixture_receipt.json",
    ):
        m1.require(
            (root_a / name).read_bytes() == (root_b / name).read_bytes(),
            f"cross-root {name} differs",
        )
    canonical_a = {
        row["probe_label"]: (
            row["parameter_sha256"],
            row["prediction_sha256"],
            row["loss_id"],
            row["model_seed"],
            row["prediction_rows"],
            row["prediction_columns"],
        )
        for row in rows[0]
    }
    canonical_b = {
        row["probe_label"]: (
            row["parameter_sha256"],
            row["prediction_sha256"],
            row["loss_id"],
            row["model_seed"],
            row["prediction_rows"],
            row["prediction_columns"],
        )
        for row in rows[1]
    }
    m1.require(canonical_a == canonical_b, "cross-root runtime identity differs")
    for root_rows in rows:
        by_label = {row["probe_label"]: row for row in root_rows}
        for loss in ("CENTRAL", "INTERVAL"):
            first = by_label[f"independent {loss} seed 20260824"]
            repeat = by_label[f"independent {loss} seed 20260824 resource-repeat-1"]
            m1.require(
                (first["parameter_sha256"], first["prediction_sha256"])
                == (repeat["parameter_sha256"], repeat["prediction_sha256"]),
                "within-root resource repeat differs",
            )
    shared_batch_wall = max(
        float(batch["wall_seconds"])
        for observation in observations
        for batch in observation["batch_walls"]
        if batch["architecture_class"] == "shared_or_permuted"
    )
    independent_batch_wall = max(
        float(batch["wall_seconds"])
        for observation in observations
        for batch in observation["batch_walls"]
        if batch["architecture_class"] == "independent"
    )
    shared_child_cpu = max(
        float(row["child_cpu_seconds"])
        for root_rows in rows
        for row in root_rows
        if row["architecture_class"] == "shared_or_permuted"
    )
    independent_child_cpu = max(
        float(row["child_cpu_seconds"])
        for root_rows in rows
        for row in root_rows
        if row["architecture_class"] == "independent"
    )
    projected_wall = (
        158 * shared_batch_wall
        + 450 * independent_batch_wall
        + 75 * max(float(value["preprocessing_wall_seconds"]) for value in observations)
        + max(
            float(value["nonfit_nonpreprocessing_wall_seconds"])
            for value in observations
        )
    ) / 3600.0
    projected_cpu = (
        630 * shared_child_cpu
        + 1800 * independent_child_cpu
        + 75 * max(float(value["preprocessing_cpu_seconds"]) for value in observations)
        + max(
            float(value["nonfit_nonpreprocessing_cpu_seconds"])
            for value in observations
        )
    ) / 3600.0
    prediction_upper_bound = (2813760 + 937920 + 562752 + 187584) * 512
    projected_storage = (
        max(
            int(value["environment_bytes"])
            + int(value["cache_bytes"])
            + int(value["work_bytes"])
            for value in observations
        )
        + prediction_upper_bound
    ) / 1_000_000_000
    peak_rss = (
        max(int(value["maximum_simultaneous_child_rss_kib"]) for value in observations)
        / 1024**2
    )
    gates = {
        "cpu": projected_cpu <= 240.0,
        "gpu": all(int(value["gpu_hours"]) == 0 for value in observations),
        "wall": projected_wall <= 38.4,
        "storage": projected_storage <= 64.0,
        "rss": peak_rss <= 24.0,
    }
    return {
        "schema_version": "cypshift.openadmet_cyp_2026.m1_resource_projection.v1",
        "contract_sha256": m1.CONTRACT_SHA256,
        "projected_cpu_core_hours": projected_cpu,
        "projected_gpu_hours": 0,
        "projected_wall_hours": projected_wall,
        "projected_restricted_storage_gb": projected_storage,
        "projected_peak_rss_gib": peak_rss,
        "gates": gates,
        "accepted": all(gates.values()),
    }


def load_formal_claim(path: Path) -> dict[str, Any]:
    """Authenticate the future reviewed single-use source-binding claim."""

    claim = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    m1.require(
        claim["schema_version"]
        == "cypshift.openadmet_cyp_2026.m1_formal_attempt_claim.v1",
        "formal claim schema differs",
    )
    m1.require(claim["contract_sha256"] == m1.CONTRACT_SHA256, "claim contract differs")
    m1.require(claim["maximum_attempts"] == 1, "claim attempt count differs")
    m1.require(claim["consumed"] is False, "tracked claim is not unconsumed")
    bindings = claim["source_bindings"]
    expected = {
        "research_pyproject_sha256": m1.sha256_path(SCRIPT.parent / "pyproject.toml"),
        "research_python_pin_sha256": m1.sha256_path(SCRIPT.parent / ".python-version"),
        "research_uv_lock_sha256": m1.sha256_path(SCRIPT.parent / "uv.lock"),
        "m1_runner_sha256": m1.sha256_path(m1.SCRIPT),
        "m1_synthetic_driver_sha256": m1.sha256_path(SCRIPT),
        "focused_test_sha256": m1.sha256_path(
            ROOT / "tests" / "test_openadmet_global_v2_m1_synthetic_implementation.py"
        ),
    }
    m1.require(bindings == expected, "formal claim source binding differs")
    for name in (
        "root_a",
        "root_b",
        "receipt_root",
        "environment_root",
        "cache_root",
    ):
        value = Path(claim["paths"][name])
        m1.require(value.is_absolute(), f"claim {name} is not absolute")
    return claim


def consume_formal_claim(*, claim_path: Path) -> Path:
    """Consume one claim, run both roots sequentially, publish, and clean."""

    claim = load_formal_claim(claim_path)
    paths = {name: Path(value) for name, value in claim["paths"].items()}
    root_a = paths["root_a"]
    root_b = paths["root_b"]
    receipt_root = paths["receipt_root"]
    environment_root = paths["environment_root"]
    cache_root = paths["cache_root"]
    expected_names = {
        "root_a": "g2-4c-m1-synthetic-attempt-1-root-a",
        "root_b": "g2-4c-m1-synthetic-attempt-1-root-b",
        "receipt_root": "g2-4c-m1-synthetic-attempt-1-receipt",
        "cache_root": "g2-4c-m1-synthetic-attempt-1-cache",
    }
    for name, expected_name in expected_names.items():
        m1.require(paths[name].name == expected_name, f"unsafe claimed {name} name")
    for root in (root_a, root_b, receipt_root):
        m1.require(
            not root.exists() and not root.is_symlink(), f"claimed root exists: {root}"
        )
    m1.require(
        environment_root.resolve(strict=True)
        == (SCRIPT.parent / ".venv").resolve(strict=True),
        "environment root differs",
    )
    m1.require(not environment_root.is_symlink(), "environment root is symlink")
    m1.require(
        cache_root.exists() and cache_root.is_dir() and not cache_root.is_symlink(),
        "dedicated cache root absent or unsafe",
    )
    expected_environment = {
        "PYTHONHASHSEED": "0",
        "OMP_NUM_THREADS": "4",
        "OMP_DYNAMIC": "FALSE",
        "MKL_NUM_THREADS": "4",
        "MKL_DYNAMIC": "FALSE",
        "OPENBLAS_NUM_THREADS": "4",
        "NUMEXPR_NUM_THREADS": "4",
    }
    m1.require(
        all(
            os.environ.get(name) == value
            for name, value in expected_environment.items()
        ),
        "formal environment differs",
    )
    routes = Path("/proc/net/route").read_text(encoding="utf-8").splitlines()[1:]
    m1.require(
        not any(line.split()[0] != "lo" for line in routes if line.split()),
        "formal network namespace is not isolated",
    )
    receipt_root.mkdir(parents=True)
    consumption = {
        "schema_version": "cypshift.openadmet_cyp_2026.m1_claim_consumption.v1",
        "claim_sha256": m1.sha256_path(claim_path),
        "contract_sha256": m1.CONTRACT_SHA256,
        "attempt_id": claim["attempt_id"],
        "consumed": True,
    }
    (receipt_root / "claim_consumption.json").write_bytes(m1.json_bytes(consumption))
    environment_bytes = _directory_bytes(environment_root)
    cache_bytes = _directory_bytes(cache_root)
    status = "G2_4B_M1_SYNTHETIC_FAILED"
    try:
        run_formal_probe_root(
            root=root_a,
            reverse=False,
            environment_bytes=environment_bytes,
            cache_bytes=cache_bytes,
        )
        run_formal_probe_root(
            root=root_b,
            reverse=True,
            environment_bytes=environment_bytes,
            cache_bytes=cache_bytes,
        )
        projection = project_resources(root_a, root_b)
        status = (
            "G2_4B_M1_SYNTHETIC_ACCEPTED"
            if projection["accepted"]
            else "G2_4_M1_RESOURCE_REJECTED"
        )
        (receipt_root / "resource_projection.json").write_bytes(
            m1.json_bytes(projection)
        )
        root_receipts = {}
        for label, root in (("root_a", root_a), ("root_b", root_b)):
            root_receipts[label] = {
                name: m1.sha256_path(path)
                for path in sorted(root.iterdir())
                if path.is_file()
                for name in (path.name,)
            }
            shutil.copy2(
                root / "resource_observations.json",
                receipt_root / f"{label}_resource_observations.json",
            )
        result = {
            "schema_version": "cypshift.openadmet_cyp_2026.m1_synthetic_result.v1",
            "status": status,
            "claim_sha256": m1.sha256_path(claim_path),
            "contract_sha256": m1.CONTRACT_SHA256,
            "source_bindings": claim["source_bindings"],
            "root_receipts": root_receipts,
            "projection": projection,
            "accounting": {name: 0 for name in m1.OFFICIAL_ZERO_FIELDS},
            "scientific_interpretation": "Synthetic mechanics and resources only; no model-quality interpretation.",
        }
        (receipt_root / "result.json").write_bytes(m1.json_bytes(result))
    except Exception as error:
        failure = {
            "schema_version": "cypshift.openadmet_cyp_2026.m1_synthetic_failure.v1",
            "status": status,
            "claim_sha256": m1.sha256_path(claim_path),
            "error_type": type(error).__name__,
            "error": str(error),
            "accounting": {name: 0 for name in m1.OFFICIAL_ZERO_FIELDS},
        }
        (receipt_root / "failure.json").write_bytes(m1.json_bytes(failure))
        raise
    finally:
        private_roots = (
            root_a.with_name(f".{root_a.name}-private"),
            root_b.with_name(f".{root_b.name}-private"),
        )
        for root in (root_a, root_b, *private_roots):
            if root.exists() and not root.is_symlink():
                shutil.rmtree(root)
        if cache_root.exists() and not cache_root.is_symlink():
            shutil.rmtree(cache_root)
        cleanup = {
            "root_a_absent": not root_a.exists(),
            "root_b_absent": not root_b.exists(),
            "private_roots_absent": not any(root.exists() for root in private_roots),
            "cache_root_absent": not cache_root.exists(),
        }
        (receipt_root / "cleanup.json").write_bytes(m1.json_bytes(cleanup))
        m1.require(all(cleanup.values()), "formal cleanup differs")
    return receipt_root


def launch_formal(*, claim_path: Path) -> None:
    """Re-exec the formal attempt inside a fresh user/network namespace."""

    if os.environ.get("CYPSHIFT_M1_NETWORK_ISOLATED") != "1":
        environment = dict(os.environ)
        environment["CYPSHIFT_M1_NETWORK_ISOLATED"] = "1"
        arguments = [
            "unshare",
            "--user",
            "--map-root-user",
            "--net",
            sys.executable,
            str(SCRIPT),
            "formal",
            "--claim",
            str(claim_path),
        ]
        os.execvpe("unshare", arguments, environment)
    consume_formal_claim(claim_path=claim_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    model_double = subparsers.add_parser("model-double")
    model_double.add_argument("--output-root", type=Path, required=True)
    model_double.add_argument("--reverse", action="store_true")
    smoke = subparsers.add_parser("smoke")
    smoke.add_argument("--output", type=Path, required=True)
    formal = subparsers.add_parser("formal")
    formal.add_argument("--claim", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "model-double":
        publish_model_double(output_root=args.output_root, reverse=args.reverse)
    elif args.command == "smoke":
        run_bounded_smokes(output_path=args.output)
    else:
        launch_formal(claim_path=args.claim)


if __name__ == "__main__":
    main()

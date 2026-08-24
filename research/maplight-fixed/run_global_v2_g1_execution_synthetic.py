#!/usr/bin/env python3
"""Accept the sparse, official-shaped G2-3C compiler and wrapper twice."""

from __future__ import annotations

import argparse
import io
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

import global_v2_g1_execution_compiler as compiler
import global_v2_g1_execution_wrapper as wrapper
import global_v2_g1_runner as g1
import global_v2_maplight_runner as base
import numpy as np

SCRIPT: Final = Path(__file__).resolve()
MOLECULES: Final = 400
COMPONENTS: Final = 200


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise wrapper.G1ExecutionWrapperError(message)


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _npy_bytes(array: np.ndarray[Any, Any]) -> bytes:
    stream = io.BytesIO()
    np.lib.format.write_array(
        stream,
        np.ascontiguousarray(array),
        version=(1, 0),
        allow_pickle=False,
    )
    return stream.getvalue()


def _fixture(
    *, reverse: bool
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, bytes],
]:
    features: list[dict[str, object]] = []
    folds: list[dict[str, object]] = []
    direct: list[dict[str, object]] = []
    rng = np.random.default_rng(20260824)
    arrays: dict[str, np.ndarray[Any, Any]] = {
        "maplight_morgan_count.npy": rng.integers(
            -2, 8, size=(MOLECULES, 1024), dtype=np.int8
        ),
        "maplight_avalon_count.npy": rng.integers(
            -2, 6, size=(MOLECULES, 1024), dtype=np.int8
        ),
        "maplight_erg.npy": rng.normal(size=(MOLECULES, 315)).astype("<f8"),
        "maplight_rdkit_descriptors.npy": rng.normal(size=(MOLECULES, 200)).astype(
            "<f8"
        ),
    }
    for index in range(MOLECULES):
        molecule = f"g2-3c-synthetic-{index:03d}"
        component_index = index // 2
        component = _digest(f"g2-3c-component-{component_index:03d}")
        raw_hash = _digest(f"raw-{molecule}")
        standardized_hash = _digest(f"standardized-{molecule}")
        features.append(
            {
                "molecule_id": molecule,
                "raw_structure_sha256": raw_hash,
                "standardized_structure_hash": standardized_hash,
                "similarity_component_hash": component,
            }
        )
        arrays["maplight_morgan_count.npy"][index, 0] = index % 8
        for repeat in base.REPEATS:
            assigned_outer = (component_index + repeat) % 5
            for context in base.OUTER_FOLDS:
                folds.append(
                    {
                        "molecule_id": molecule,
                        "similarity_component_hash": component,
                        "repeat": repeat,
                        "seed": compiler.SEEDS[repeat],
                        "outer_fold": assigned_outer,
                        "outer_validation_fold": context,
                        "inner_fold": (
                            ""
                            if assigned_outer == context
                            else (component_index + repeat + context) % 4
                        ),
                    }
                )
        confirmatory = compiler._is_confirmatory(component)
        for endpoint_index, endpoint in enumerate(base.ENDPOINTS):
            point_eligible = (index + endpoint_index) % 5 != 0
            tutorial_eligible = point_eligible and (index + endpoint_index) % 7 != 0
            has_std = tutorial_eligible and (index + endpoint_index) % 2 == 0
            point = format(5.0 + endpoint_index * 0.25 + (index % 17) * 0.01, ".17g")
            low = format(float(point) - 0.005, ".17g") if tutorial_eligible else ""
            high = format(float(point) + 0.005, ".17g") if tutorial_eligible else ""
            std = "0.050000000000000003" if has_std else ""
            if not point_eligible:
                point = ""
            if confirmatory:
                point = "CONFIRMATORY_SENTINEL_MUST_REMAIN_OPAQUE"
                low = high = std = "CONFIRMATORY_SENTINEL_MUST_REMAIN_OPAQUE"
            state = (
                "missing"
                if not point_eligible
                else "complete"
                if tutorial_eligible and has_std
                else "partial"
            )
            direct.append(
                {
                    "observation_id": _digest(f"observation|{molecule}|{endpoint}"),
                    "molecule_id": molecule,
                    "source_row_id": f"source-{index:03d}",
                    "source_file": "synthetic_direct.csv",
                    "source_row": index + 2,
                    "source_sha256": _digest("synthetic-direct-source"),
                    "endpoint": endpoint,
                    "raw_smiles": f"C{'C' * (index % 5)}N",
                    "raw_point": point,
                    "raw_low": low,
                    "raw_high": high,
                    "raw_std": std,
                    "point": point,
                    "low": low,
                    "high": high,
                    "std": std,
                    "raw_structure_sha256": raw_hash,
                    "standardized_structure_hash": standardized_hash,
                    "similarity_component_hash": component,
                    "scaffold_group_hash": _digest(f"scaffold-{component_index:03d}"),
                    "value_state": state,
                    "point_eligible": "true" if point_eligible else "false",
                    "anchor_eligible": "true" if state == "complete" else "false",
                }
            )
    if reverse:
        order = np.arange(MOLECULES - 1, -1, -1)
        features.reverse()
        folds.reverse()
        direct.reverse()
        arrays = {name: value[order] for name, value in arrays.items()}
    return (
        features,
        folds,
        direct,
        {name: _npy_bytes(value) for name, value in arrays.items()},
    )


def publish_source(
    *, root: Path, reverse: bool
) -> tuple[Path, list[dict[str, object]], list[dict[str, object]]]:
    """Publish one immutable sparse official-shaped parent root."""

    features, folds, direct, arrays = _fixture(reverse=reverse)
    files = {
        "feature_rows.csv": base.csv_bytes(compiler.SOURCE_FEATURE_COLUMNS, features),
        "group_folds.csv": base.csv_bytes(compiler.SOURCE_FOLD_COLUMNS, folds),
        "direct_observations.csv": base.csv_bytes(compiler.DIRECT_COLUMNS, direct),
        **arrays,
    }
    feature_components = {str(row["similarity_component_hash"]) for row in features}
    confirmatory_components = {
        component
        for component in feature_components
        if compiler._is_confirmatory(component)
    }
    confirmatory_molecules = sum(
        str(row["similarity_component_hash"]) in confirmatory_components
        for row in features
    )
    manifest = {
        "schema_version": compiler.SOURCE_SCHEMA,
        "synthetic": True,
        "semantic_source_id": "g2-2c-official-shaped-synthetic-v1",
        "reverse_physical_order": reverse,
        "source_receipts": {
            name: base.sha256_bytes(value) for name, value in files.items()
        },
        "label_free_counts": {
            "all_molecules": MOLECULES,
            "all_components": COMPONENTS,
            "development_molecules": MOLECULES - confirmatory_molecules,
            "development_components": COMPONENTS - len(confirmatory_components),
            "confirmatory_molecules": confirmatory_molecules,
            "confirmatory_components": len(confirmatory_components),
        },
        "authority": dict(base.DENIED_AUTHORITY),
    }
    published = cast(
        Path,
        base.publish_files(root, {**files, "manifest.json": base.json_bytes(manifest)}),
    )
    return published, features, folds


def publish_baseline(
    *, root: Path, features: list[dict[str, object]], folds: list[dict[str, object]]
) -> Path:
    """Publish a deterministic fixed-baseline-shaped synthetic terminal."""

    fold_index = {
        (
            str(row["molecule_id"]),
            int(row["repeat"]),
            int(row["outer_validation_fold"]),
        ): int(row["outer_fold"])
        for row in folds
    }
    rows: list[dict[str, object]] = []
    for feature in features:
        molecule = str(feature["molecule_id"])
        component = str(feature["similarity_component_hash"])
        if compiler._is_confirmatory(component):
            continue
        index = int(molecule.rsplit("-", 1)[1])
        for endpoint_index, endpoint in enumerate(base.ENDPOINTS):
            for repeat in base.REPEATS:
                outer = fold_index[molecule, repeat, 0]
                prediction = 5.4 + endpoint_index * 0.25 + (index % 17) * 0.01
                rows.append(
                    {
                        "molecule_id": molecule,
                        "endpoint": endpoint,
                        "similarity_component_hash": component,
                        "repeat": repeat,
                        "outer_fold": outer,
                        "system_id": "SYNTHETIC-FIXED-BASELINE",
                        "prediction": format(prediction, ".17g"),
                        "model_id": _digest(
                            f"baseline-model|{endpoint}|{repeat}|{outer}"
                        ),
                        "split_id": _digest(f"baseline-split|{repeat}|{outer}"),
                    }
                )
    rows.sort(key=lambda row: tuple(row[name] for name in base.OUTER_COLUMNS[:5]))
    return cast(
        Path,
        base.publish_files(
            root,
            {
                "development_outer_oof.csv": base.csv_bytes(base.OUTER_COLUMNS, rows),
                "manifest.json": base.json_bytes({"synthetic": True}),
            },
        ),
    )


def run_replay(
    *, source_root: Path, baseline_root: Path, replay_root: Path
) -> tuple[Path, list[dict[str, object]]]:
    """Compile and execute one full-topology synthetic replay, then clean it."""

    _require(not replay_root.exists() and not replay_root.is_symlink(), "replay exists")
    private = replay_root.with_name(f".{replay_root.name}-private")
    _require(not private.exists() and not private.is_symlink(), "private replay exists")
    private.mkdir(parents=True)
    try:
        model, selector, scorer, preflight = compiler.compile_capabilities(
            source_root=source_root,
            baseline_terminal_root=baseline_root,
            output_root=private / "capabilities",
            expected_compiler_sha256=base.sha256_path(compiler.SCRIPT),
        )
        _require(preflight["status"] == "G2_3C_PREFLIGHT_PASS", "preflight differs")
        probes = wrapper.run_runtime_probes(model_capability_root=model)
        terminal = wrapper.run_compiled_replay(
            model_capability_root=model,
            selector_capability_root=selector,
            scorer_capability_root=scorer,
            work_root=private / "execution",
            predictor=wrapper.deterministic_test_predictor,
        )
        files = {
            path.relative_to(terminal).as_posix(): path.read_bytes()
            for path in terminal.rglob("*")
            if path.is_file()
        }
        published = cast(Path, base.publish_files(replay_root, files))
    finally:
        base._cleanup(private)
    _require(not private.exists(), "private replay cleanup differs")
    return published, probes


def accept_replays(
    *,
    terminal_a: Path,
    terminal_b: Path,
    probes_a: list[dict[str, object]],
    probes_b: list[dict[str, object]],
    output_root: Path,
) -> Path:
    """Require exact two-root evidence and publish one acceptance receipt."""

    _require(
        terminal_a.resolve(strict=True) != terminal_b.resolve(strict=True),
        "terminal roots are not distinct",
    )
    maps = [base.relative_byte_map(root) for root in (terminal_a, terminal_b)]
    _require(maps[0] == maps[1], "terminal byte maps differ")
    _require(probes_a == probes_b and len(probes_a) == 14, "runtime probes differ")
    manifest, _raw = base._load_json(terminal_a / "manifest.json")
    accounting = manifest.get("accounting")
    counts = manifest.get("counts")
    _require(
        manifest.get("status") == "G2_3C_OFFICIAL_SHAPED_SYNTHETIC_REPLAY_COMPLETE"
        and manifest.get("synthetic") is True
        and manifest.get("execution_contract_sha256")
        == compiler.EXECUTION_CONTRACT_SHA256
        and isinstance(accounting, dict)
        and isinstance(counts, dict)
        and counts.get("inner_catboost_fits") == 8640
        and counts.get("outer_catboost_fits") == 180
        and counts.get("tutorial_metric_calls") == 888
        and accounting.get("synthetic_model_fits") == 8820
        and accounting.get("synthetic_tutorial_ma_st_rae_calls") == 888
        and all(accounting.get(name) == 0 for name in wrapper.FORBIDDEN_COUNTERS)
        and manifest.get("authority") == wrapper._authority(True, "terminal"),
        "synthetic terminal evidence differs",
    )
    combined = base.sha256_bytes(
        "".join(f"{name}|{value}\n" for name, value in sorted(maps[0].items())).encode(
            "utf-8"
        )
    )
    acceptance = {
        "schema_version": (
            "cypshift.openadmet_cyp_2026.global_v2_g1_execution_synthetic_acceptance.v1"
        ),
        "status": "G2_3C_OFFICIAL_SHAPED_SYNTHETIC_ACCEPTED",
        "execution_contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
        "compiler_source_sha256": base.sha256_path(compiler.SCRIPT),
        "execution_wrapper_source_sha256": base.sha256_path(wrapper.SCRIPT),
        "acceptance_source_sha256": base.sha256_path(SCRIPT),
        "accepted_g1_runner_source_sha256": base.sha256_path(g1.SCRIPT),
        "runtime_lock_sha256": base.sha256_path(g1.LOCK),
        "roots": 2,
        "second_source_physical_order_reversed": True,
        "relative_byte_maps_identical": True,
        "files_compared": len(maps[0]),
        "combined_terminal_tree_sha256": combined,
        "runtime_probe_fits_per_root": 14,
        "runtime_probe_receipt_sha256": base.sha256_bytes(base.json_bytes(probes_a)),
        "counts_per_replay": counts,
        "full_topology_model_fits_per_replay": 8820,
        "full_topology_model_fits_total": 17640,
        "real_runtime_probe_fits_total": 28,
        "resource_bounds": {
            "maximum_concurrent_catboost_fits": 1,
            "thread_count_per_fit": 16,
            "maximum_wall_seconds": wrapper.MAXIMUM_WALL_SECONDS,
            "maximum_cpu_core_hours": wrapper.MAXIMUM_CPU_CORE_HOURS,
            "maximum_restricted_storage_bytes": (
                wrapper.MAXIMUM_RESTRICTED_STORAGE_BYTES
            ),
            "retry": False,
            "resume": False,
            "move": False,
            "overwrite": False,
        },
        "sparse_point_and_tutorial_masks_distinct": True,
        "private_roots_retained": 0,
        "accounting_per_replay": accounting,
        "authority": dict(g1.DENIED_AUTHORITY),
        "scientific_interpretation": (
            "Official-shaped sparse synthetic mechanics only; no diagnostic value "
            "may select or rank a model."
        ),
        "next_gate": (
            "Review and integrate these exact implementation receipts before "
            "deriving the private consumed claim or opening any official input."
        ),
    }
    return cast(
        Path,
        base.publish_files(
            output_root, {"acceptance.json": base.json_bytes(acceptance)}
        ),
    )


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-a", type=Path, required=True)
    parser.add_argument("--root-b", type=Path, required=True)
    parser.add_argument("--acceptance-root", type=Path, required=True)
    args = parser.parse_args()
    source_a, features_a, folds_a = publish_source(
        root=args.root_a.with_name(args.root_a.name + "-source"), reverse=False
    )
    source_b, features_b, folds_b = publish_source(
        root=args.root_b.with_name(args.root_b.name + "-source"), reverse=True
    )
    baseline_a = publish_baseline(
        root=args.root_a.with_name(args.root_a.name + "-baseline"),
        features=features_a,
        folds=folds_a,
    )
    baseline_b = publish_baseline(
        root=args.root_b.with_name(args.root_b.name + "-baseline"),
        features=features_b,
        folds=folds_b,
    )
    terminal_a, probes_a = run_replay(
        source_root=source_a, baseline_root=baseline_a, replay_root=args.root_a
    )
    terminal_b, probes_b = run_replay(
        source_root=source_b, baseline_root=baseline_b, replay_root=args.root_b
    )
    accept_replays(
        terminal_a=terminal_a,
        terminal_b=terminal_b,
        probes_a=probes_a,
        probes_b=probes_b,
        output_root=args.acceptance_root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

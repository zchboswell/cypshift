#!/usr/bin/env python3
"""Accept the G2-2C compiler and wrapper on sparse official-shaped synthesis."""

from __future__ import annotations

import argparse
import io
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

import global_v2_maplight_execution_compiler as compiler
import global_v2_maplight_execution_wrapper as wrapper
import global_v2_maplight_runner as runner
import numpy as np

SCRIPT: Final = Path(__file__).resolve()
MOLECULES: Final = 400
COMPONENTS: Final = 200


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise wrapper.MapLightExecutionWrapperError(message)


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
    for index in range(MOLECULES):
        molecule = f"g2-2c-synthetic-{index:03d}"
        component_index = index // 2
        component = _digest(f"g2-2c-component-{component_index:03d}")
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
        for repeat in runner.REPEATS:
            assigned_outer = (component_index + repeat) % 5
            for context in runner.OUTER_FOLDS:
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
        for endpoint_index, endpoint in enumerate(runner.ENDPOINTS):
            eligible = (index + endpoint_index) % 5 != 0
            point: object = format(
                5.0 + endpoint_index * 0.25 + (index % 17) * 0.01, ".17g"
            )
            if confirmatory:
                point = "CONFIRMATORY_SENTINEL_MUST_REMAIN_OPAQUE"
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
                    "raw_point": point if eligible else "",
                    "raw_low": "",
                    "raw_high": "",
                    "raw_std": "",
                    "point": point if eligible else "",
                    "low": "",
                    "high": "",
                    "std": "",
                    "raw_structure_sha256": raw_hash,
                    "standardized_structure_hash": standardized_hash,
                    "similarity_component_hash": component,
                    "scaffold_group_hash": _digest(f"scaffold-{component_index:03d}"),
                    "value_state": "complete" if eligible else "missing",
                    "point_eligible": "true" if eligible else "false",
                    "anchor_eligible": "true" if eligible else "false",
                }
            )
    rng = np.random.default_rng(20260824)
    array_values: dict[str, np.ndarray[Any, Any]] = {
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
    if reverse:
        order = np.arange(MOLECULES - 1, -1, -1)
        features.reverse()
        folds.reverse()
        direct.reverse()
        array_values = {name: value[order] for name, value in array_values.items()}
    return (
        features,
        folds,
        direct,
        {name: _npy_bytes(value) for name, value in array_values.items()},
    )


def publish_source(*, root: Path, reverse: bool) -> Path:
    """Publish one immutable official-shaped synthetic parent root."""

    features, folds, direct, arrays = _fixture(reverse=reverse)
    files = {
        "feature_rows.csv": runner.csv_bytes(compiler.SOURCE_FEATURE_COLUMNS, features),
        "group_folds.csv": runner.csv_bytes(compiler.SOURCE_FOLD_COLUMNS, folds),
        "direct_observations.csv": runner.csv_bytes(compiler.DIRECT_COLUMNS, direct),
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
            name: runner.sha256_bytes(value) for name, value in files.items()
        },
        "label_free_counts": {
            "all_molecules": MOLECULES,
            "all_components": COMPONENTS,
            "development_molecules": MOLECULES - confirmatory_molecules,
            "development_components": COMPONENTS - len(confirmatory_components),
            "confirmatory_molecules": confirmatory_molecules,
            "confirmatory_components": len(confirmatory_components),
        },
        "authority": dict(runner.DENIED_AUTHORITY),
    }
    return cast(
        Path,
        runner.publish_files(
            root, {**files, "manifest.json": runner.json_bytes(manifest)}
        ),
    )


def run_replay(*, source_root: Path, replay_root: Path, compiler_sha256: str) -> Path:
    """Compile, run 300 real fits, score sparse truth, and clean private state."""

    _require(not replay_root.exists(), "replay root exists")
    replay_root.mkdir(parents=True)
    private = replay_root / "private"
    predictions = replay_root / "predictions"
    terminal = replay_root / "terminal"
    try:
        model, scorer, _preflight = compiler.compile_capabilities(
            source_root=source_root,
            output_root=private,
            expected_compiler_sha256=compiler_sha256,
        )
        wrapper.run_predictions(model_capability_root=model, output_root=predictions)
        wrapper.score_predictions(
            prediction_root=predictions,
            scorer_capability_root=scorer,
            output_root=terminal,
        )
    finally:
        runner._cleanup(private)
        runner._cleanup(predictions)
    _require(
        {path.name for path in replay_root.iterdir()} == {"terminal"},
        "private cleanup differs",
    )
    return terminal


def accept_replays(*, terminal_a: Path, terminal_b: Path, output_root: Path) -> Path:
    """Require byte-identical sparse terminals and publish acceptance."""

    _require(
        terminal_a.resolve(strict=True) != terminal_b.resolve(strict=True),
        "execution replay roots are not distinct",
    )
    maps = [runner.relative_byte_map(root) for root in (terminal_a, terminal_b)]
    _require(maps[0] == maps[1], "execution replay byte maps differ")
    manifest, _raw = runner._load_json(terminal_a / "manifest.json")
    _require(
        manifest.get("status") == "G2_2C_OFFICIAL_SHAPED_SYNTHETIC_REPLAY_COMPLETE"
        and manifest.get("synthetic") is True,
        "synthetic terminal identity differs",
    )
    _require(
        manifest.get("execution_contract_sha256") == compiler.EXECUTION_CONTRACT_SHA256
        and manifest.get("implementation_receipts")
        == {
            "accepted_runner_source_sha256": runner.sha256_path(runner.SCRIPT),
            "compiler_source_sha256": runner.sha256_path(compiler.SCRIPT),
            "execution_wrapper_source_sha256": runner.sha256_path(wrapper.SCRIPT),
            "resolved_parameter_sha256": runner.PARAMETER_SHA256,
            "research_uv_lock_sha256": runner.LOCK_SHA256,
        }
        and manifest.get("runtime")
        == {
            "catboost": "1.2.1",
            "numpy": "1.25.2",
            "platform": "Linux x86_64 CPU",
            "python": "3.10.13",
        }
        and manifest.get("counts")
        == {
            "component_metric_rows": 60,
            "finite_truth_rows": 1043,
            "inner_maplight_fits": 240,
            "inner_prediction_rows": 15648,
            "molecules": 326,
            "outer_maplight_fits": 60,
            "outer_prediction_rows": 3912,
            "q90_contexts": 60,
            "residual_rows": 3129,
            "uncertainty_rows": 3129,
        }
        and manifest.get("authority") == runner.DENIED_AUTHORITY,
        "synthetic implementation binding differs",
    )
    source_receipts = manifest.get("source_receipts")
    _require(
        isinstance(source_receipts, Mapping)
        and set(source_receipts)
        == {
            "model_capability_manifest_sha256",
            "scorer_capability_manifest_sha256",
        }
        and all(compiler._is_sha(value) for value in source_receipts.values()),
        "synthetic source lineage differs",
    )
    accounting = manifest["accounting"]
    forbidden = (
        "official_target_values_opened",
        "official_features_opened",
        "official_model_fits",
        "official_predictions_generated",
        "official_metric_evaluations",
        "official_residual_values_computed",
        "official_diagnostics_computed",
        "confirmatory_truth_values_opened",
        "historical_r3c_row_level_artifacts_opened",
        "blinded_test_files_opened",
        "tdi_files_opened",
        "submissions_created",
        "leaderboard_observations",
        "tutorial_ma_st_rae_calls",
        "external_records_acquired",
        "live_uploads",
    )
    _require(all(accounting[name] == 0 for name in forbidden), "forbidden accounting")
    _require(
        accounting.get("maplight_model_fits") == 300,
        "synthetic fit accounting differs",
    )
    combined = runner.sha256_bytes(
        "".join(f"{name}|{value}\n" for name, value in sorted(maps[0].items())).encode(
            "utf-8"
        )
    )
    receipt = {
        "schema_version": (
            "cypshift.openadmet_cyp_2026.global_v2_maplight_execution_synthetic_acceptance.v1"
        ),
        "status": "G2_2C_OFFICIAL_SHAPED_SYNTHETIC_ACCEPTED",
        "execution_contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
        "compiler_source_sha256": runner.sha256_path(compiler.SCRIPT),
        "execution_wrapper_source_sha256": runner.sha256_path(wrapper.SCRIPT),
        "acceptance_source_sha256": runner.sha256_path(SCRIPT),
        "accepted_runner_source_sha256": runner.sha256_path(runner.SCRIPT),
        "roots": 2,
        "second_source_physical_order_reversed": True,
        "relative_byte_maps_identical": True,
        "files_compared": len(maps[0]),
        "combined_terminal_tree_sha256": combined,
        "counts_per_replay": manifest["counts"],
        "maplight_fits_total": manifest["accounting"]["maplight_model_fits"] * 2,
        "sparse_truth": True,
        "private_roots_retained": 0,
        "accounting_per_replay": accounting,
        "authority": dict(runner.DENIED_AUTHORITY),
        "scientific_interpretation": (
            "Official-shaped sparse synthetic mechanics only; no diagnostic value "
            "may select or rank a model."
        ),
        "next_gate": (
            "Review and integrate these exact implementation hashes before deriving "
            "the private consumed claim or opening any official input."
        ),
    }
    return cast(
        Path,
        runner.publish_files(
            output_root, {"acceptance.json": runner.json_bytes(receipt)}
        ),
    )


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-a", type=Path, required=True)
    parser.add_argument("--root-b", type=Path, required=True)
    parser.add_argument("--acceptance-root", type=Path, required=True)
    args = parser.parse_args()
    compiler_sha = runner.sha256_path(compiler.SCRIPT)
    source_a = publish_source(
        root=args.root_a.with_name(args.root_a.name + "-source"), reverse=False
    )
    source_b = publish_source(
        root=args.root_b.with_name(args.root_b.name + "-source"), reverse=True
    )
    terminal_a = run_replay(
        source_root=source_a, replay_root=args.root_a, compiler_sha256=compiler_sha
    )
    terminal_b = run_replay(
        source_root=source_b, replay_root=args.root_b, compiler_sha256=compiler_sha
    )
    accept_replays(
        terminal_a=terminal_a,
        terminal_b=terminal_b,
        output_root=args.acceptance_root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

#!/usr/bin/env python3
"""Accept the EXP-G3 official-shaped compiler and wrapper on two fresh roots."""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import sys
from pathlib import Path
from typing import Any, Final, cast

import g3_execution_compiler as compiler
import g3_execution_wrapper as wrapper
import g3_runner as g3
import numpy as np

sys.path.insert(0, str(g3.ROOT / "src"))
from cypshift.chemistry import standardize_molecule  # noqa: E402
from cypshift.schema import MoleculeInput, MoleculeStatus  # noqa: E402

SCRIPT: Final = Path(__file__).resolve()
NETWORK_ENV: Final = "CYPSHIFT_G3_EXECUTION_NETWORK_ISOLATED"
MOLECULES: Final = 1200
COMPONENTS: Final = 600
DEVELOPMENT_MOLECULES: Final = 960
DEVELOPMENT_COMPONENTS: Final = 480
CONFIRMATORY_MOLECULES: Final = 240
CONFIRMATORY_COMPONENTS: Final = 120


def require(condition: bool, message: str) -> None:
    if not condition:
        raise wrapper.G3ExecutionWrapperError(message)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def component_pool() -> tuple[list[str], list[str]]:
    development: list[str] = []
    confirmatory: list[str] = []
    counter = 0
    while (
        len(development) < DEVELOPMENT_COMPONENTS
        or len(confirmatory) < CONFIRMATORY_COMPONENTS
    ):
        component = digest(f"g3-execution-synthetic-component-v1|{counter}")
        target = confirmatory if compiler.is_confirmatory(component) else development
        limit = (
            CONFIRMATORY_COMPONENTS
            if target is confirmatory
            else DEVELOPMENT_COMPONENTS
        )
        if len(target) < limit:
            target.append(component)
        counter += 1
    return development, confirmatory


def synthetic_smiles(index: int) -> str:
    """Return one of 1,200 distinct modest-size accepted structures."""

    alkyl = "C" * (index % 40 + 1)
    alkoxy = "C" * (index // 40 + 1)
    return f"c1c({alkyl})c(O{alkoxy})c(N)cc1"


def _npy_bytes(array: np.ndarray[Any, Any]) -> bytes:
    stream = io.BytesIO()
    np.lib.format.write_array(
        stream, np.ascontiguousarray(array), version=(1, 0), allow_pickle=False
    )
    return stream.getvalue()


def fixture(
    *, reverse: bool
) -> tuple[
    list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], bytes
]:
    development, confirmatory = component_pool()
    components = development + confirmatory
    confirmatory_set = set(confirmatory)
    features: list[dict[str, object]] = []
    folds: list[dict[str, object]] = []
    direct: list[dict[str, object]] = []
    rng = np.random.Generator(np.random.PCG64(20260830))
    descriptors = rng.normal(size=(MOLECULES, g3.DESCRIPTOR_WIDTH)).astype("<f8")
    descriptors[
        (np.arange(MOLECULES)[:, None] + np.arange(g3.DESCRIPTOR_WIDTH)[None, :]) % 97
        == 0
    ] = np.nan
    for index in range(MOLECULES):
        molecule = f"g3-execution-synthetic-{index:04d}"
        component_index = index // 2
        component = components[component_index]
        smiles = synthetic_smiles(index)
        raw_hash = digest(smiles)
        standardized = standardize_molecule(
            MoleculeInput(molecule, smiles, "smiles", "g3-synthetic", "{}")
        )
        require(
            standardized.status is MoleculeStatus.ACCEPTED
            and standardized.standardized_structure is not None
            and standardized.standardized_structure_hash is not None,
            "synthetic standardization differs",
        )
        standardized_hash = cast(str, standardized.standardized_structure_hash)
        features.append(
            {
                "molecule_id": molecule,
                "raw_structure_sha256": raw_hash,
                "standardized_structure_hash": standardized_hash,
                "similarity_component_hash": component,
            }
        )
        descriptors[index, 0] = 5.0 + (index % 23) * 0.02
        for repeat, repeat_seed in enumerate(g3.REPEAT_SEEDS):
            assigned = (component_index + repeat) % 5
            for context in g3.OUTER_FOLDS:
                folds.append(
                    {
                        "molecule_id": molecule,
                        "similarity_component_hash": component,
                        "repeat": repeat,
                        "seed": repeat_seed,
                        "outer_fold": assigned,
                        "outer_validation_fold": context,
                        "inner_fold": ""
                        if assigned == context
                        else (component_index + context) % 4,
                    }
                )
        confirmatory_molecule = component in confirmatory_set
        for endpoint_index, endpoint in enumerate(g3.ENDPOINTS):
            point_eligible = (index + endpoint_index) % 5 != 0
            tutorial_eligible = point_eligible and (index + endpoint_index) % 7 != 0
            point_value = descriptors[index, 0] + endpoint_index * 0.25
            point = format(point_value, ".17g") if point_eligible else ""
            low = format(point_value - 0.01, ".17g") if tutorial_eligible else ""
            high = format(point_value + 0.01, ".17g") if tutorial_eligible else ""
            std = "0.050000000000000003" if tutorial_eligible else ""
            if confirmatory_molecule:
                point = low = high = std = "CONFIRMATORY_SENTINEL_MUST_REMAIN_OPAQUE"
            state = (
                "missing"
                if not point_eligible
                else "complete"
                if tutorial_eligible
                else "partial"
            )
            direct.append(
                {
                    "observation_id": digest(f"observation|{molecule}|{endpoint}"),
                    "molecule_id": molecule,
                    "source_row_id": f"source-{index:04d}",
                    "source_file": "synthetic_direct.csv",
                    "source_row": index * 4 + endpoint_index + 2,
                    "source_sha256": digest("g3-synthetic-direct-source"),
                    "endpoint": endpoint,
                    "raw_smiles": smiles,
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
                    "scaffold_group_hash": digest(
                        f"synthetic-scaffold|{component_index}"
                    ),
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
        descriptors = np.ascontiguousarray(descriptors[order])
    return features, folds, direct, _npy_bytes(descriptors)


def publish_source(
    *, root: Path, reverse: bool
) -> tuple[Path, list[dict[str, object]], list[dict[str, object]]]:
    features, folds, direct, descriptors = fixture(reverse=reverse)
    files = {
        "feature_rows.csv": g3.csv_bytes(compiler.SOURCE_FEATURE_COLUMNS, features),
        "group_folds.csv": g3.csv_bytes(compiler.SOURCE_FOLD_COLUMNS, folds),
        "direct_observations.csv": g3.csv_bytes(compiler.DIRECT_COLUMNS, direct),
        "maplight_rdkit_descriptors.npy": descriptors,
    }
    manifest = {
        "schema_version": compiler.SOURCE_SCHEMA,
        "synthetic": True,
        "semantic_source_id": compiler.SYNTHETIC_SOURCE_ID,
        "reverse_physical_order": reverse,
        "source_receipts": {
            name: g3.sha256_bytes(value) for name, value in files.items()
        },
        "label_free_counts": {
            "all_molecules": MOLECULES,
            "all_components": COMPONENTS,
            "development_molecules": DEVELOPMENT_MOLECULES,
            "development_components": DEVELOPMENT_COMPONENTS,
            "confirmatory_molecules": CONFIRMATORY_MOLECULES,
            "confirmatory_components": CONFIRMATORY_COMPONENTS,
        },
        "authority": compiler._source_authority(True),
    }
    return (
        compiler._publish_files(
            root, {**files, "manifest.json": g3.json_bytes(manifest)}
        ),
        features,
        folds,
    )


def publish_baseline(
    *, root: Path, features: list[dict[str, object]], folds: list[dict[str, object]]
) -> tuple[Path, dict[str, str]]:
    assigned = {
        (str(row["molecule_id"]), int(row["repeat"])): int(row["outer_fold"])
        for row in folds
        if int(row["outer_validation_fold"]) == 0
    }
    rows: list[dict[str, object]] = []
    for feature in features:
        molecule = str(feature["molecule_id"])
        component = str(feature["similarity_component_hash"])
        if compiler.is_confirmatory(component):
            continue
        index = int(molecule.rsplit("-", 1)[1])
        base = 5.0 + (index % 23) * 0.02
        for endpoint_index, endpoint in enumerate(g3.ENDPOINTS):
            for repeat in range(3):
                outer = assigned[molecule, repeat]
                rows.append(
                    {
                        "molecule_id": molecule,
                        "endpoint": endpoint,
                        "similarity_component_hash": component,
                        "repeat": repeat,
                        "outer_fold": outer,
                        "system_id": "SYNTHETIC-FIXED-MAPL",
                        "prediction": format(
                            base + endpoint_index * 0.25 + 0.4, ".17g"
                        ),
                        "model_id": digest(
                            f"baseline-model|{endpoint}|{repeat}|{outer}"
                        ),
                        "split_id": digest(f"baseline-split|{repeat}|{outer}"),
                    }
                )
    rows.sort(
        key=lambda row: tuple(str(row[name]) for name in compiler.BASELINE_COLUMNS[:5])
    )
    prediction_bytes = g3.csv_bytes(compiler.BASELINE_COLUMNS, rows)
    manifest_bytes = g3.json_bytes(
        {
            "schema_version": "cypshift.openadmet_cyp_2026.g3_synthetic_baseline.v1",
            "synthetic": True,
            "rows": len(rows),
        }
    )
    published = compiler._publish_files(
        root,
        {
            "development_outer_oof.csv": prediction_bytes,
            "manifest.json": manifest_bytes,
        },
    )
    return published, {
        "baseline_manifest_sha256": g3.sha256_bytes(manifest_bytes),
        "baseline_outer_oof_sha256": g3.sha256_bytes(prediction_bytes),
    }


def run_replay(
    *,
    source_root: Path,
    baseline_root: Path,
    baseline_receipts: dict[str, str],
    replay_root: Path,
) -> Path:
    require(
        not replay_root.exists() and not replay_root.is_symlink(), "replay root exists"
    )
    private = replay_root.with_name(f".{replay_root.name}-private")
    require(
        not private.exists() and not private.is_symlink(), "private replay root exists"
    )
    private.mkdir(parents=True)
    try:
        model, scorer, preflight = compiler.compile_capabilities(
            source_root=source_root,
            baseline_terminal_root=baseline_root,
            output_root=private / "capabilities",
            expected_compiler_sha256=g3.sha256_path(compiler.SCRIPT),
            mode="synthetic",
            synthetic_baseline_receipts=baseline_receipts,
        )
        require(
            preflight["status"] == "G2_6T_G3_PREFLIGHT_PASS",
            "synthetic preflight differs",
        )
        terminal = wrapper.run_compiled_replay(
            model_capability_root=model,
            scorer_capability_root=scorer,
            baseline_terminal_root=baseline_root,
            work_root=private / "execution",
            predictor=wrapper.deterministic_test_predictor,
        )
        files = {
            path.relative_to(terminal).as_posix(): path.read_bytes()
            for path in terminal.rglob("*")
            if path.is_file()
        }
        published = compiler._publish_files(replay_root, files)
    finally:
        compiler._cleanup(private)
    require(not private.exists(), "private replay cleanup differs")
    return published


def relative_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): g3.sha256_path(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def accept(
    *,
    root_a: Path,
    root_b: Path,
    control_a: dict[str, object],
    control_b: dict[str, object],
    output_root: Path,
) -> Path:
    maps = [relative_map(root) for root in (root_a, root_b)]
    require(
        maps[0] == maps[1] and set(maps[0]) == set(wrapper.TERMINAL_NAMES),
        "terminal maps differ",
    )
    require(control_a == control_b, "runtime controls differ")
    manifest = compiler._load_json(root_a / "manifest.json")
    result = compiler._load_json(root_a / "g3_result.json")
    accounting = manifest.get("accounting")
    counts = manifest.get("counts")
    require(
        manifest.get("status") == "G2_6T_G3_OFFICIAL_SHAPED_SYNTHETIC_REPLAY_COMPLETE"
        and manifest.get("synthetic") is True
        and isinstance(accounting, dict)
        and isinstance(counts, dict)
        and counts.get("model_fits") == 60
        and counts.get("candidate_outer_prediction_rows") == 11520
        and counts.get("baseline_outer_prediction_rows") == 11520
        and counts.get("tutorial_metric_calls") == 24
        and counts.get("bootstrap_accepted_replicates") == 2000
        and accounting.get("synthetic_model_fits") == 60
        and accounting.get("synthetic_predictions") == 11520
        and all(accounting.get(name) == 0 for name in wrapper.FORBIDDEN_COUNTERS)
        and result.get("all_promotion_gates_pass") is True
        and all(result.get("promotion_gates", {}).values()),
        "synthetic acceptance evidence differs",
    )
    tree_sha = g3.sha256_bytes(
        "".join(f"{name}|{value}\n" for name, value in sorted(maps[0].items())).encode()
    )
    acceptance = {
        "schema_version": "cypshift.openadmet_cyp_2026.global_v2_g3_execution_synthetic_acceptance.v1",
        "status": "G2_6T_G3_OFFICIAL_SHAPED_SYNTHETIC_ACCEPTED",
        "execution_contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
        "tracked_claim_sha256": compiler.TRACKED_CLAIM_SHA256,
        "official_compiler_source_sha256": g3.sha256_path(compiler.SCRIPT),
        "execution_wrapper_source_sha256": g3.sha256_path(wrapper.SCRIPT),
        "official_shaped_synthetic_driver_source_sha256": g3.sha256_path(SCRIPT),
        "accepted_g3_runner_source_sha256": g3.sha256_path(g3.SCRIPT),
        "research_lock_sha256": g3.sha256_path(
            g3.ROOT / "research" / "lightgbm-global" / "uv.lock"
        ),
        "roots": 2,
        "second_root_physical_order_reversed": True,
        "terminal_files_compared": len(maps[0]),
        "relative_terminal_maps_byte_identical": True,
        "terminal_tree_sha256": tree_sha,
        "runtime_controls": 2,
        "runtime_control_receipt_sha256": g3.sha256_bytes(g3.json_bytes(control_a)),
        "runtime_control_fits_total": 2,
        "runtime_control_predictions_total": 1576,
        "network_namespace_isolated": os.environ.get(NETWORK_ENV) == "1",
        "population_per_root": {
            "all_molecules": MOLECULES,
            "all_components": COMPONENTS,
            "development_molecules": DEVELOPMENT_MOLECULES,
            "development_components": DEVELOPMENT_COMPONENTS,
            "confirmatory_molecules": CONFIRMATORY_MOLECULES,
            "confirmatory_components": CONFIRMATORY_COMPONENTS,
        },
        "counts_per_root": counts,
        "accounting_per_root": accounting,
        "synthetic_promotion_gates_all_pass": True,
        "private_roots_retained": 0,
        "claim_consumptions": 0,
        "official_operations": 0,
        "model_quality_authority": False,
        "next_gate": "Review and integrate these exact hashes before deriving and atomically consuming the sole private official-development claim.",
    }
    return compiler._publish_files(
        output_root, {"acceptance.json": g3.json_bytes(acceptance)}
    )


def run_formal(*, parent: Path) -> Path:
    require(os.environ.get(NETWORK_ENV) == "1", "formal network namespace differs")
    root_a = parent / "g3-execution-synthetic-root-a"
    root_b = parent / "g3-execution-synthetic-root-b"
    source_a = parent / "g3-execution-synthetic-source-a"
    source_b = parent / "g3-execution-synthetic-source-b"
    baseline_a = parent / "g3-execution-synthetic-baseline-a"
    baseline_b = parent / "g3-execution-synthetic-baseline-b"
    acceptance_root = parent / "g3-execution-synthetic-acceptance"
    require(not parent.exists() and not parent.is_symlink(), "formal parent exists")
    parent.mkdir(parents=True)
    try:
        published_source_a, features_a, folds_a = publish_source(
            root=source_a, reverse=False
        )
        published_source_b, features_b, folds_b = publish_source(
            root=source_b, reverse=True
        )
        published_baseline_a, receipts_a = publish_baseline(
            root=baseline_a, features=features_a, folds=folds_a
        )
        published_baseline_b, receipts_b = publish_baseline(
            root=baseline_b, features=features_b, folds=folds_b
        )
        terminal_a = run_replay(
            source_root=published_source_a,
            baseline_root=published_baseline_a,
            baseline_receipts=receipts_a,
            replay_root=root_a,
        )
        control_a = wrapper.run_runtime_control()
        terminal_b = run_replay(
            source_root=published_source_b,
            baseline_root=published_baseline_b,
            baseline_receipts=receipts_b,
            replay_root=root_b,
        )
        control_b = wrapper.run_runtime_control()
        accepted = accept(
            root_a=terminal_a,
            root_b=terminal_b,
            control_a=control_a,
            control_b=control_b,
            output_root=acceptance_root,
        )
        receipt = (accepted / "acceptance.json").read_bytes()
    finally:
        for path in (
            root_a,
            root_b,
            source_a,
            source_b,
            baseline_a,
            baseline_b,
            acceptance_root,
        ):
            compiler._cleanup(path)
    require(
        all(
            not path.exists()
            for path in (
                root_a,
                root_b,
                source_a,
                source_b,
                baseline_a,
                baseline_b,
                acceptance_root,
            )
        ),
        "formal cleanup differs",
    )
    output = parent / "acceptance.json"
    output.write_bytes(receipt)
    return output


def launch_formal(*, parent: Path) -> Path:
    if os.environ.get(NETWORK_ENV) != "1":
        environment = dict(os.environ)
        environment[NETWORK_ENV] = "1"
        arguments = [
            "unshare",
            "--user",
            "--map-root-user",
            "--net",
            sys.executable,
            str(SCRIPT),
            "--parent",
            str(parent),
        ]
        os.execvpe("unshare", arguments, environment)
    return run_formal(parent=parent)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, required=True)
    args = parser.parse_args()
    print(launch_formal(parent=args.parent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build, replay, and accept the exact two-root G2-7B synthetic gate."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, cast

import global_v2_maplight_robustness_runner as robust
import global_v2_maplight_runner as base

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
FOCUSED_TEST: Final = (
    ROOT / "tests/test_openadmet_global_v2_maplight_robustness_synthetic.py"
)
COMPONENTS: Final = 600
DEVELOPMENT_COMPONENTS: Final = 480
MOLECULES_PER_COMPONENT: Final = 2
MOLECULES: Final = COMPONENTS * MOLECULES_PER_COMPONENT

ProbeRunner = Callable[..., tuple[Path, dict[str, Any]]]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise robust.RobustnessSyntheticError(message)


def _digest(*values: object) -> str:
    return robust._digest(*values)


def _candidate_metric(
    *,
    tutorial_improvement: float,
    component_improvement: float,
    component_delta: float,
    spread: float,
    favorable_cells: int,
    endpoint_harm: float,
    tutorial_primary: float,
    component_macro_mae: float,
) -> dict[str, object]:
    return {
        "tutorial_relative_improvement": tutorial_improvement,
        "component_mae_improvement": component_improvement,
        "component_delta": component_delta,
        "component_delta_spread": spread,
        "paired_upper_95": None,
        "favorable_cells": favorable_cells,
        "maximum_endpoint_harm": endpoint_harm,
        "tutorial_primary": tutorial_primary,
        "component_macro_mae": component_macro_mae,
    }


def _scorer_profiles() -> dict[str, object]:
    full_metrics = {
        robust.DROP_CANDIDATES[0]: _candidate_metric(
            tutorial_improvement=0.005,
            component_improvement=0.002,
            component_delta=-0.002,
            spread=0.0005,
            favorable_cells=10,
            endpoint_harm=0.001,
            tutorial_primary=0.590,
            component_macro_mae=0.581,
        ),
        robust.DROP_CANDIDATES[1]: _candidate_metric(
            tutorial_improvement=-0.002,
            component_improvement=-0.001,
            component_delta=0.001,
            spread=0.0005,
            favorable_cells=6,
            endpoint_harm=0.002,
            tutorial_primary=0.596,
            component_macro_mae=0.585,
        ),
        robust.DROP_CANDIDATES[2]: _candidate_metric(
            tutorial_improvement=0.012,
            component_improvement=0.006,
            component_delta=-0.006,
            spread=0.0005,
            favorable_cells=10,
            endpoint_harm=0.006,
            tutorial_primary=0.586,
            component_macro_mae=0.578,
        ),
        robust.DROP_CANDIDATES[3]: _candidate_metric(
            tutorial_improvement=0.012,
            component_improvement=0.006,
            component_delta=-0.006,
            spread=0.0005,
            favorable_cells=7,
            endpoint_harm=0.001,
            tutorial_primary=0.586,
            component_macro_mae=0.578,
        ),
    }
    deletion_metrics = {
        robust.DROP_CANDIDATES[0]: _candidate_metric(
            tutorial_improvement=0.020,
            component_improvement=0.010,
            component_delta=-0.010,
            spread=0.001,
            favorable_cells=12,
            endpoint_harm=0.001,
            tutorial_primary=0.575,
            component_macro_mae=0.574,
        ),
        robust.DROP_CANDIDATES[1]: _candidate_metric(
            tutorial_improvement=0.004,
            component_improvement=0.002,
            component_delta=-0.002,
            spread=0.001,
            favorable_cells=10,
            endpoint_harm=0.001,
            tutorial_primary=0.590,
            component_macro_mae=0.582,
        ),
        robust.DROP_CANDIDATES[2]: _candidate_metric(
            tutorial_improvement=0.012,
            component_improvement=0.006,
            component_delta=-0.006,
            spread=0.001,
            favorable_cells=7,
            endpoint_harm=0.001,
            tutorial_primary=0.585,
            component_macro_mae=0.578,
        ),
        robust.DROP_CANDIDATES[3]: _candidate_metric(
            tutorial_improvement=0.012,
            component_improvement=0.006,
            component_delta=-0.006,
            spread=0.001,
            favorable_cells=10,
            endpoint_harm=0.006,
            tutorial_primary=0.585,
            component_macro_mae=0.578,
        ),
    }
    return {
        "schema_version": robust.SCORE_SCHEMA,
        "profiles": {
            "FULL_RETAINED": {
                "expected_selected_candidate": robust.FULL,
                "candidate_metrics": full_metrics,
            },
            "DROP_MORGAN_SELECTED": {
                "expected_selected_candidate": robust.DROP_CANDIDATES[0],
                "candidate_metrics": deletion_metrics,
            },
        },
        "source_values": ["cyp-challenge-TRAIN_inhibition.csv"],
        "confirmatory_truth_values": 0,
        "scientific_interpretation": "Engineered scorer profiles only.",
    }


def _component_members(component: int) -> list[str]:
    return [f"g2-7b-synthetic-{component * 2 + offset:04d}" for offset in range(2)]


def _overlay_rows(
    molecules: list[dict[str, object]], *, overlay_id: str
) -> list[dict[str, object]]:
    specification = {
        "THRESHOLD_0_55": (4, 20),
        "THRESHOLD_0_50": (8, 40),
        "TAUTOMER_MERGED": (6, 24),
    }
    touching, merged = specification[overlay_id]
    component_group: dict[int, str] = {}
    for component in range(COMPONENTS):
        if component < touching:
            component_group[component] = _digest(overlay_id, "confirmatory-touch", component)
        elif component < touching + merged:
            pair_start = touching + ((component - touching) // 2) * 2
            component_group[component] = _digest(overlay_id, "merged", pair_start)
        else:
            component_group[component] = _digest(overlay_id, "single", component)
    for component in range(touching):
        component_group[DEVELOPMENT_COMPONENTS + component] = component_group[component]

    group_order: dict[str, int] = {}
    for component in range(COMPONENTS):
        group_order.setdefault(component_group[component], component)
    rows = []
    for molecule in molecules:
        component = int(molecule["source_index"]) // 2
        development_touch = component < touching
        excluded = molecule["partition"] == "development" and development_touch
        group = component_group[component]
        rows.append(
            {
                "molecule_id": molecule["molecule_id"],
                "overlay_id": overlay_id,
                "active_component_hash": "" if excluded else group,
                "excluded_confirmatory_touch": "true" if excluded else "false",
                "fold_r0": "" if excluded else group_order[group] % 5,
                "fold_r1": "" if excluded else (group_order[group] + 1) % 5,
                "fold_r2": "" if excluded else (group_order[group] + 2) % 5,
            }
        )
    return rows


def _fixture(
    *, reverse: bool
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    molecules = []
    folds = []
    for index in range(MOLECULES):
        component = index // 2
        molecule = f"g2-7b-synthetic-{index:04d}"
        partition = "development" if component < DEVELOPMENT_COMPONENTS else "confirmatory"
        molecules.append(
            {
                "molecule_id": molecule,
                "source_index": index,
                "primary_component_hash": _digest("primary", component),
                "partition": partition,
                "standardized_structure_hash": _digest("structure", index // 4),
                "source_file": "cyp-challenge-TRAIN_inhibition.csv",
            }
        )
        for repeat in robust.REPEATS:
            folds.append(
                {
                    "molecule_id": molecule,
                    "repeat": repeat,
                    "primary_fold": (component + repeat) % 5,
                }
            )
    overlays = [
        row
        for overlay in robust.OVERLAYS
        for row in _overlay_rows(molecules, overlay_id=overlay)
    ]
    truth = []
    for profile_index, profile in enumerate(robust.PROFILES):
        for molecule in molecules:
            if molecule["partition"] != "development":
                continue
            source_index = int(molecule["source_index"])
            for endpoint_index, endpoint in enumerate(robust.ENDPOINTS):
                point = (
                    4.0
                    + (source_index % 37) * 0.05
                    + endpoint_index * 0.25
                    + profile_index * 0.01
                )
                truth.append(
                    {
                        "profile": profile,
                        "molecule_id": molecule["molecule_id"],
                        "endpoint": endpoint,
                        "point": format(point, ".17g"),
                        "low": format(point - 0.05, ".17g"),
                        "high": format(point + 0.05, ".17g"),
                    }
                )
    if reverse:
        molecules.reverse()
        folds.reverse()
        overlays.reverse()
        truth.reverse()
    return molecules, folds, overlays, truth


def publish_source(*, root: Path, reverse: bool) -> Path:
    """Publish one authenticated family-bearing G2-7B synthetic source."""

    molecules, folds, overlays, truth = _fixture(reverse=reverse)
    feature_manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.maplight_robustness_feature_manifest.v1",
        "columns": 2563,
        "blocks": [list(value) for value in robust.FEATURE_BLOCKS],
        "views": {key: list(value) for key, value in robust.FEATURE_VIEWS.items()},
        "widths": robust.FEATURE_WIDTHS,
        "dtype": "float32",
        "descriptor_nan_mask": "deterministic-declared",
        "drop_rule": "ordered zero-copy block exclusion",
    }
    files = {
        "molecules.csv": base.csv_bytes(robust.MOLECULE_COLUMNS, molecules),
        "folds.csv": base.csv_bytes(robust.FOLD_COLUMNS, folds),
        "overlays.csv": base.csv_bytes(robust.OVERLAY_COLUMNS, overlays),
        "feature_manifest.json": base.json_bytes(feature_manifest),
        "scorer_profiles.json": base.json_bytes(_scorer_profiles()),
        "scorer_truth.csv": base.csv_bytes(robust.TRUTH_COLUMNS, truth),
    }
    manifest = {
        "schema_version": robust.SOURCE_SCHEMA,
        "synthetic": True,
        "semantic_source_id": "g2-7b-maplight-robustness-synthetic-v1",
        "physical_source_order": "reverse" if reverse else "canonical",
        "counts": {
            "molecules": 1200,
            "components": 600,
            "development_molecules": 960,
            "confirmatory_molecules": 240,
            "confirmatory_truth_values": 0,
            "fold_rows": 3600,
            "overlay_rows": 3600,
            "scorer_truth_rows": 7680,
        },
        "source_receipts": {name: base.sha256_bytes(value) for name, value in files.items()},
        "scientific_interpretation": "Synthetic mechanics source only.",
        "authority": {name: False for name in robust.OFFICIAL_ZERO_FIELDS},
    }
    return cast(Path, base.publish_files(root, {**files, "manifest.json": base.json_bytes(manifest)}))


def run_replay(
    *,
    source_root: Path,
    replay_root: Path,
    reverse_execution_order: bool,
    probe_runner: ProbeRunner = robust.run_runtime_probes,
    allow_test_double: bool = False,
) -> tuple[Path, dict[str, Any]]:
    """Run one fresh replay, clean private state, and publish one terminal."""

    _require(not replay_root.exists() and not replay_root.is_symlink(), "replay root exists")
    private = replay_root.with_name(f".{replay_root.name}-private")
    _require(not private.exists() and not private.is_symlink(), "private replay root exists")
    private.mkdir(parents=True)
    try:
        source_manifest = json.loads((source_root / "manifest.json").read_text(encoding="utf-8"))
        model, scorer = robust.compile_capabilities(
            source_root=source_root,
            output_root=private / "capabilities",
            expected_runner_sha256=base.sha256_path(robust.SCRIPT),
        )
        model_double = robust.run_model_double(
            model_capability_root=model,
            output_root=private / "model-double",
            reverse_execution_order=reverse_execution_order,
        )
        scored = robust.score_and_select(
            model_double_root=model_double,
            scorer_capability_root=scorer,
            output_root=private / "scored",
        )
        probes, probe_timing = probe_runner(
            output_root=private / "probes",
            reverse_execution_order=reverse_execution_order,
        )
        traversal = robust.traverse_full_size_resource(
            reverse_execution_order=reverse_execution_order
        )
        files = robust.terminal_files(
            source_manifest=source_manifest,
            model_double_root=model_double,
            scored_root=scored,
            probe_root=probes,
            resource_traversal=traversal,
            allow_test_double=allow_test_double,
        )
        observed_private_bytes = robust.directory_bytes(private)
        projected_row_level_bytes = 797232 * 256
        projected_feature_bytes = 4905 * 2563 * 4
        restricted_bytes = (
            observed_private_bytes + projected_row_level_bytes + projected_feature_bytes
        )
    except Exception:
        base._cleanup(private)
        raise
    base._cleanup(private)
    _require(not private.exists(), "private replay cleanup differs")
    terminal = base.publish_files(replay_root, files)
    return terminal, {
        "probe_timing": probe_timing,
        "traversal": traversal,
        "restricted_bytes": restricted_bytes,
        "private_roots_retained": 0,
    }


def _tree_sha(value: dict[str, str]) -> str:
    return base.sha256_bytes(base.json_bytes(value))


def accept_replays(
    *,
    terminal_a: Path,
    terminal_b: Path,
    resource_a: dict[str, Any],
    resource_b: dict[str, Any],
    output_root: Path,
    focused_tests_passed: int,
) -> Path:
    """Require exact two-root evidence and publish one aggregate acceptance."""

    _require(terminal_a.resolve(strict=True) != terminal_b.resolve(strict=True), "terminal roots are not distinct")
    maps = [robust.relative_byte_map(root) for root in (terminal_a, terminal_b)]
    _require(maps[0] == maps[1], "G2-7B terminal byte maps differ")
    manifests = [
        json.loads((root / robust.TERMINAL_FILES[-1]).read_text(encoding="utf-8"))
        for root in (terminal_a, terminal_b)
    ]
    _require(manifests[0] == manifests[1], "G2-7B terminal manifests differ")
    manifest = manifests[0]
    _require(
        manifest["status"] == "G2_7B_MAPLIGHT_ROBUSTNESS_SYNTHETIC_ACCEPTED"
        and manifest["counts"]["model_double_invocations"] == 1740
        and manifest["counts"]["model_double_prediction_rows"] == 333216
        and manifest["counts"]["real_catboost_fits"] == 13
        and manifest["private_roots_retained"] == 0,
        "G2-7B terminal identity differs",
    )
    _require(
        not manifests[0]["runtime_probe_test_double"]
        and not manifests[1]["runtime_probe_test_double"],
        "test-double terminal cannot be accepted",
    )
    worse_probe = {
        "maximum_fit_wall_seconds": max(
            resource_a["probe_timing"]["maximum_fit_wall_seconds"],
            resource_b["probe_timing"]["maximum_fit_wall_seconds"],
        ),
        "maximum_fit_cpu_seconds": max(
            resource_a["probe_timing"]["maximum_fit_cpu_seconds"],
            resource_b["probe_timing"]["maximum_fit_cpu_seconds"],
        ),
        "peak_rss_kib": max(
            resource_a["probe_timing"]["peak_rss_kib"],
            resource_b["probe_timing"]["peak_rss_kib"],
        ),
    }
    worse_traversal = {
        "nonfit_wall_seconds": max(
            resource_a["traversal"]["nonfit_wall_seconds"],
            resource_b["traversal"]["nonfit_wall_seconds"],
        ),
        "nonfit_cpu_seconds": max(
            resource_a["traversal"]["nonfit_cpu_seconds"],
            resource_b["traversal"]["nonfit_cpu_seconds"],
        ),
        "peak_rss_kib": max(
            resource_a["traversal"]["peak_rss_kib"],
            resource_b["traversal"]["peak_rss_kib"],
        ),
    }
    projection = robust.resource_projection(
        probe_timing=worse_probe,
        traversal=worse_traversal,
        restricted_bytes=max(resource_a["restricted_bytes"], resource_b["restricted_bytes"]),
    )
    _require(projection["all_gates_pass"], "G2-7B resource projection failed")
    accounting = manifest["accounting"]
    _require(all(accounting[name] == 0 for name in robust.OFFICIAL_ZERO_FIELDS), "forbidden accounting differs")
    receipt = {
        "schema_version": (
            "cypshift.openadmet_cyp_2026."
            "global_v2_maplight_robustness_synthetic_acceptance.v1"
        ),
        "status": "G2_7B_MAPLIGHT_ROBUSTNESS_SYNTHETIC_ACCEPTED",
        "recorded_at_utc": "2026-08-25T16:47:26Z",
        "contract_sha256": robust.CONTRACT_SHA256,
        "base_commit": "d19f6efcb04ec25240be60671344fd967aca49fd",
        "implementation_receipts": {
            "runner_source_sha256": base.sha256_path(robust.SCRIPT),
            "driver_source_sha256": base.sha256_path(SCRIPT),
            "focused_test_source_sha256": base.sha256_path(FOCUSED_TEST),
        },
        "roots": 2,
        "relative_terminal_maps_identical": True,
        "terminal_tree_sha256": _tree_sha(maps[0]),
        "terminal_files": 8,
        "model_double_invocations_total": 3480,
        "model_double_prediction_rows_total": 666432,
        "real_catboost_fits_total": 26,
        "real_catboost_prediction_rows_total": 20488,
        "full_size_prediction_identities_per_root": 797232,
        "selection_tokens_total": 4,
        "selected_profile_oracles": {
            "FULL_RETAINED": robust.FULL,
            "DROP_MORGAN_SELECTED": robust.DROP_CANDIDATES[0],
        },
        "resource_projection": projection,
        "focused_tests_passed": focused_tests_passed,
        "cleanup": {
            "private_roots_retained": 0,
            "model_binaries_retained": 0,
            "row_level_predictions_retained": 0,
        },
        "accounting_per_replay": accounting,
        "scientific_interpretation": (
            "Synthetic mechanics, runtime compatibility, and resource evidence only; "
            "no synthetic value can select or rank an official model."
        ),
        "next_gate": (
            "After reviewed signed integration and green post-main CI, freeze a separate "
            "single-use official development execution contract and unusable claim before "
            "opening any official byte."
        ),
    }
    return cast(
        Path,
        base.publish_files(output_root, {"acceptance.json": base.json_bytes(receipt)}),
    )


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-a", type=Path, required=True)
    parser.add_argument("--root-b", type=Path, required=True)
    parser.add_argument("--acceptance-root", type=Path, required=True)
    parser.add_argument("--focused-tests-passed", type=int, required=True)
    args = parser.parse_args()
    sources = [
        publish_source(root=args.root_a.with_name(f"{args.root_a.name}-source"), reverse=False),
        publish_source(root=args.root_b.with_name(f"{args.root_b.name}-source"), reverse=True),
    ]
    terminal_a, resource_a = run_replay(
        source_root=sources[0],
        replay_root=args.root_a,
        reverse_execution_order=False,
    )
    terminal_b, resource_b = run_replay(
        source_root=sources[1],
        replay_root=args.root_b,
        reverse_execution_order=True,
    )
    accept_replays(
        terminal_a=terminal_a,
        terminal_b=terminal_b,
        resource_a=resource_a,
        resource_b=resource_b,
        output_root=args.acceptance_root,
        focused_tests_passed=args.focused_tests_passed,
    )
    for root in (*sources, terminal_a, terminal_b):
        base._cleanup(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

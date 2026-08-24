#!/usr/bin/env python3
"""Build, replay, and accept the two exact G2-3B synthetic roots."""

from __future__ import annotations

import argparse
import io
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

import global_v2_g1_runner as g1
import global_v2_maplight_runner as base
import numpy as np

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
MOLECULES: Final = 80
COMPONENTS: Final = 40


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise g1.G1SyntheticError(message)


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _npy_bytes(array: np.ndarray[Any, Any]) -> bytes:
    stream = io.BytesIO()
    np.lib.format.write_array(
        stream,
        np.ascontiguousarray(array, dtype="<f4"),
        version=(1, 0),
        allow_pickle=False,
    )
    return stream.getvalue()


def _fixture(
    *, reverse: bool
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[str, bytes]]:
    features: list[dict[str, object]] = []
    folds: list[dict[str, object]] = []
    truth: list[dict[str, object]] = []
    matrix = np.zeros((MOLECULES, g1.FEATURE_WIDTH), dtype="<f4")
    for index in range(MOLECULES):
        molecule = f"g2-3b-synthetic-{index:03d}"
        component_index = index // 2
        component = _digest(f"g2-3b-component-{component_index:03d}")
        latent = 4.0 + (index % 16) * 0.125
        matrix[index, 0] = latent
        matrix[index, 1024] = float(index % 7)
        matrix[index, 2048] = float((index % 5) - 2) * 0.25
        matrix[index, 2363] = float(component_index % 11) * 0.125
        features.append(
            {
                "molecule_id": molecule,
                "similarity_component_hash": component,
            }
        )
        for repeat in g1.REPEATS:
            assigned_outer = (component_index + repeat) % 5
            for outer_context in g1.OUTER_FOLDS:
                folds.append(
                    {
                        "molecule_id": molecule,
                        "similarity_component_hash": component,
                        "repeat": repeat,
                        "outer_fold": assigned_outer,
                        "outer_validation_fold": outer_context,
                        "inner_fold": (
                            ""
                            if assigned_outer == outer_context
                            else (component_index + repeat + outer_context) % 4
                        ),
                    }
                )
        for endpoint_index, endpoint in enumerate(g1.ENDPOINTS):
            missing = (index + endpoint_index * 7) % 19 == 0
            point = latent + endpoint_index * 0.5
            truth.append(
                {
                    "molecule_id": molecule,
                    "endpoint": endpoint,
                    "similarity_component_hash": component,
                    "availability": "missing" if missing else "complete",
                    "point": "" if missing else format(point, ".17g"),
                    "low": "" if missing else format(point - 0.03125, ".17g"),
                    "high": "" if missing else format(point + 0.03125, ".17g"),
                }
            )
    arrays: dict[str, np.ndarray[Any, Any]] = {}
    start = 0
    for name, width in g1.FEATURE_WIDTHS:
        arrays[name] = matrix[:, start : start + width]
        start += width
    _require(start == g1.FEATURE_WIDTH, "fixture feature partition differs")
    if reverse:
        order = np.arange(MOLECULES - 1, -1, -1)
        features.reverse()
        folds.reverse()
        truth.reverse()
        arrays = {name: value[order] for name, value in arrays.items()}
    return features, folds, truth, {name: _npy_bytes(value) for name, value in arrays.items()}


def publish_source(*, root: Path, reverse: bool) -> Path:
    """Publish one authenticated family-bearing G2-3B synthetic fixture."""

    features, folds, truth, arrays = _fixture(reverse=reverse)
    files = {
        "feature_rows.csv": base.csv_bytes(g1.FEATURE_COLUMNS, features),
        "folds.csv": base.csv_bytes(g1.FOLD_COLUMNS, folds),
        "truth.csv": base.csv_bytes(g1.TRUTH_COLUMNS, truth),
        **arrays,
    }
    selection_oracles = [
        {
            "endpoint": endpoint,
            "repeat": repeat,
            "outer_fold": outer,
            "configuration_id": g1.expected_outer_configuration(endpoint, repeat, outer),
        }
        for endpoint in g1.ENDPOINTS
        for repeat in g1.REPEATS
        for outer in g1.OUTER_FOLDS
    ]
    manifest = {
        "schema_version": g1.SOURCE_SCHEMA,
        "synthetic": True,
        "semantic_source_id": "g2-3b-exp-g1-synthetic-v1",
        "physical_source_order": "reverse" if reverse else "canonical",
        "source_receipts": {name: base.sha256_bytes(value) for name, value in files.items()},
        "feature_order": [f"{name}:{width}" for name, width in g1.FEATURE_WIDTHS],
        "counts": {
            "molecules": MOLECULES,
            "components": COMPONENTS,
            "molecules_per_component": 2,
            "feature_columns": g1.FEATURE_WIDTH,
            "fold_rows": MOLECULES * 3 * 5,
            "truth_rows": MOLECULES * 4,
        },
        "selection_oracles": selection_oracles,
        "future_endpoint_oracles": {endpoint: "G1-C01" for endpoint in g1.ENDPOINTS},
        "scientific_interpretation": "Synthetic mechanics fixture only.",
        "authority": g1._stage_authority("source"),
    }
    return cast(Path, base.publish_files(root, {**files, "manifest.json": base.json_bytes(manifest)}))


def run_replay(
    *,
    source_root: Path,
    replay_root: Path,
    reverse_execution_order: bool,
    probe_runner: g1.ProbeRunner = g1.run_runtime_probes,
    allow_test_double: bool = False,
) -> Path:
    """Run one fresh replay, destroy private roots, then publish one terminal."""

    _require(not replay_root.exists() and not replay_root.is_symlink(), "replay root exists")
    private = replay_root.with_name(f".{replay_root.name}-private")
    _require(not private.exists() and not private.is_symlink(), "private replay root exists")
    private.mkdir(parents=True)
    try:
        model, selector, scorer = g1.compile_capabilities(
            source_root=source_root,
            output_root=private / "capabilities",
            expected_runner_sha256=base.sha256_path(g1.SCRIPT),
        )
        inner_raw = g1.run_inner_models(
            model_capability_root=model,
            output_root=private / "inner-raw",
            reverse_execution_order=reverse_execution_order,
        )
        inner_frozen = g1.freeze_inner_predictions(
            raw_root=inner_raw, output_root=private / "inner-frozen"
        )
        selections = g1.select_inner_configurations(
            frozen_root=inner_frozen,
            selector_capability_root=selector,
            output_root=private / "selections",
        )
        outer_raw = g1.run_outer_models(
            model_capability_root=model,
            selection_root=selections,
            output_root=private / "outer-raw",
            reverse_execution_order=reverse_execution_order,
        )
        outer_frozen = g1.freeze_outer_predictions(
            raw_root=outer_raw,
            selection_root=selections,
            output_root=private / "outer-frozen",
        )
        scored = g1.score_outer_predictions(
            outer_frozen_root=outer_frozen,
            scorer_capability_root=scorer,
            output_root=private / "scored",
        )
        future = g1.freeze_future_configurations(
            selection_root=selections,
            selector_capability_root=selector,
            scored_root=scored,
            output_root=private / "future",
        )
        probes = probe_runner(
            model_capability_root=model,
            output_root=private / "runtime-probes",
        )
        files = g1.terminal_files(
            selection_root=selections,
            scored_root=scored,
            future_root=future,
            probe_root=probes,
            allow_test_double=allow_test_double,
        )
    except Exception:
        base._cleanup(private)
        raise
    base._cleanup(private)
    _require(not private.exists(), "private replay cleanup differs")
    return cast(Path, base.publish_files(replay_root, files))


def accept_replays(
    *,
    terminal_a: Path,
    terminal_b: Path,
    output_root: Path,
    focused_tests_passed: int,
) -> Path:
    """Require exact two-root evidence and publish one aggregate acceptance."""

    _require(
        terminal_a.resolve(strict=True) != terminal_b.resolve(strict=True),
        "replay roots are not distinct",
    )
    maps = [g1.relative_byte_map(root) for root in (terminal_a, terminal_b)]
    _require(maps[0] == maps[1], "G2-3B terminal byte maps differ")
    manifests = [_json_terminal(root) for root in (terminal_a, terminal_b)]
    _require(manifests[0] == manifests[1], "G2-3B terminal manifests differ")
    manifest = manifests[0]
    _require(
        manifest.get("status") == "G2_3B_EXP_G1_SYNTHETIC_ACCEPTED"
        and manifest.get("contract_sha256") == g1.CONTRACT_SHA256
        and manifest.get("counts", {}).get("model_double_invocations") == 8820
        and manifest.get("counts", {}).get("real_catboost_fits") == 14
        and manifest.get("private_roots_retained") == 0,
        "G2-3B terminal acceptance identity differs",
    )
    _require(manifest.get("runtime_probe_test_double") is False, "test-double terminal cannot be accepted")
    accounting = manifest["accounting"]
    _require(
        accounting["synthetic_model_double_invocations"] == 8820
        and accounting["synthetic_catboost_fits"] == 14
        and accounting["synthetic_tutorial_metric_evaluations"] == 888
        and all(accounting[name] == 0 for name in g1.OFFICIAL_ZERO_FIELDS),
        "G2-3B terminal accounting differs",
    )
    test_source = ROOT / "tests/test_openadmet_global_v2_g1_synthetic.py"
    _require(test_source.is_file() and focused_tests_passed >= 14, "focused adversarial evidence differs")
    combined = base.sha256_bytes(
        "".join(f"{name}|{value}\n" for name, value in sorted(maps[0].items())).encode("utf-8")
    )
    receipt = {
        "schema_version": "cypshift.openadmet_cyp_2026.global_v2_g1_synthetic_acceptance.v1",
        "status": "G2_3B_EXP_G1_SYNTHETIC_ACCEPTED",
        "contract_sha256": g1.CONTRACT_SHA256,
        "parent_sha256": g1.PARENT_SHA256,
        "implementation_receipts": {
            "g1_runner_source_sha256": base.sha256_path(g1.SCRIPT),
            "synthetic_driver_source_sha256": base.sha256_path(SCRIPT),
            "focused_test_source_sha256": base.sha256_path(test_source),
            "accepted_maplight_runner_source_sha256": base.sha256_path(base.SCRIPT),
            "tutorial_metric_source_sha256": base.sha256_path(g1.METRIC_SOURCE),
            "research_uv_lock_sha256": base.sha256_path(g1.LOCK),
        },
        "roots": 2,
        "second_source_physical_order_reversed": True,
        "second_model_execution_order_reversed": True,
        "relative_terminal_maps_identical": True,
        "files_compared": len(maps[0]),
        "combined_terminal_tree_sha256": combined,
        "terminal_manifest_sha256": base.sha256_path(terminal_a / "manifest.json"),
        "counts_per_replay": manifest["counts"],
        "model_double_invocations_total": 17640,
        "real_catboost_fits_total": 28,
        "focused_tests_passed": focused_tests_passed,
        "all_fourteen_adversarial_classes_required": True,
        "private_roots_retained": 0,
        "accounting_per_replay": accounting,
        "authority": dict(g1.DENIED_AUTHORITY),
        "scientific_interpretation": "Synthetic mechanics and locked-runtime compatibility only; no synthetic value may select or rank a model.",
        "full_repository_ci_required_after_integration": True,
        "next_gate": "Review and integrate these exact hashes and require green post-main CI before drafting G2-3C.",
    }
    return cast(Path, base.publish_files(output_root, {"acceptance.json": base.json_bytes(receipt)}))


def _json_terminal(root: Path) -> dict[str, Any]:
    value, _raw = base._load_json(root / "manifest.json")
    return value


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-a", type=Path, required=True)
    parser.add_argument("--root-b", type=Path, required=True)
    parser.add_argument("--acceptance-root", type=Path, required=True)
    parser.add_argument("--focused-tests-passed", type=int, required=True)
    args = parser.parse_args()
    source_a = publish_source(
        root=args.root_a.with_name(f"{args.root_a.name}-source"), reverse=False
    )
    source_b = publish_source(
        root=args.root_b.with_name(f"{args.root_b.name}-source"), reverse=True
    )
    terminal_a = run_replay(
        source_root=source_a,
        replay_root=args.root_a,
        reverse_execution_order=False,
    )
    terminal_b = run_replay(
        source_root=source_b,
        replay_root=args.root_b,
        reverse_execution_order=True,
    )
    accept_replays(
        terminal_a=terminal_a,
        terminal_b=terminal_b,
        output_root=args.acceptance_root,
        focused_tests_passed=args.focused_tests_passed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

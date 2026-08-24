#!/usr/bin/env python3
"""Build and accept two synthetic Global-v2 MapLight replay roots."""

from __future__ import annotations

import argparse
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

import global_v2_maplight_runner as runner
import numpy as np

SCRIPT: Final = Path(__file__).resolve()
MOLECULES: Final = 200


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise runner.GlobalV2MapLightError(message)


def _npy_bytes(array: np.ndarray[Any, Any]) -> bytes:
    stream = io.BytesIO()
    np.save(stream, np.ascontiguousarray(array), allow_pickle=False)
    return stream.getvalue()


def _fixture_rows(
    reverse: bool,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    features: list[dict[str, object]] = []
    folds: list[dict[str, object]] = []
    truth: list[dict[str, object]] = []
    source_order = range(MOLECULES - 1, -1, -1) if reverse else range(MOLECULES)
    for index in source_order:
        molecule = f"synthetic-maplight-{index:03d}"
        component_index = index // 2
        component = runner.sha256_bytes(
            f"synthetic-component-{component_index:03d}".encode()
        )
        features.append(
            {
                "molecule_id": molecule,
                "similarity_component_hash": component,
            }
        )
        for endpoint_index, endpoint in enumerate(runner.ENDPOINTS):
            point = (
                4.0 + 0.08 * index + 0.15 * endpoint_index + ((index % 3) - 1) * 0.01
            )
            truth.append(
                {
                    "molecule_id": molecule,
                    "endpoint": endpoint,
                    "similarity_component_hash": component,
                    "point": format(point, ".17g"),
                }
            )
        for repeat in runner.REPEATS:
            outer_fold = (component_index + repeat) % 5
            for outer_context in runner.OUTER_FOLDS:
                folds.append(
                    {
                        "molecule_id": molecule,
                        "similarity_component_hash": component,
                        "repeat": repeat,
                        "outer_fold": outer_fold,
                        "outer_validation_fold": outer_context,
                        "inner_fold": (
                            ""
                            if outer_fold == outer_context
                            else (component_index + repeat + outer_context) % 4
                        ),
                    }
                )
    return features, folds, truth


def _arrays() -> dict[str, bytes]:
    morgan: np.ndarray[Any, Any] = np.zeros((MOLECULES, 1024), dtype=np.int8)
    avalon: np.ndarray[Any, Any] = np.zeros((MOLECULES, 1024), dtype=np.int8)
    erg: np.ndarray[Any, Any] = np.zeros((MOLECULES, 315), dtype="<f8")
    descriptors: np.ndarray[Any, Any] = np.zeros((MOLECULES, 200), dtype="<f8")
    for index in range(MOLECULES):
        morgan[index, 0] = index % 101
        morgan[index, 1 + index] = 1
        avalon[index, index % 7] = 1 + index % 3
        erg[index, 0] = index / 20.0
        erg[index, 1] = (index % 5) / 5.0
        descriptors[index, 0] = float(index)
        descriptors[index, 1] = float(index * index) / 400.0
    return {
        "maplight_morgan_count.npy": _npy_bytes(morgan),
        "maplight_avalon_count.npy": _npy_bytes(avalon),
        "maplight_erg.npy": _npy_bytes(erg),
        "maplight_rdkit_descriptors.npy": _npy_bytes(descriptors),
    }


def _fold_scope(
    folds: Sequence[Mapping[str, object]], repeat: int, outer: int
) -> dict[str, Mapping[str, object]]:
    return {
        str(row["molecule_id"]): row
        for row in folds
        if int(str(row["repeat"])) == repeat
        and int(str(row["outer_validation_fold"])) == outer
    }


def _training_ids(
    scope: Mapping[str, Mapping[str, object]],
    stage: str,
    outer: int,
    inner: int | None,
) -> list[str]:
    if stage == "outer":
        return sorted(
            molecule
            for molecule, row in scope.items()
            if int(str(row["outer_fold"])) != outer
        )
    _require(inner is not None, "inner context is absent")
    return sorted(
        molecule
        for molecule, row in scope.items()
        if int(str(row["outer_fold"])) != outer and int(str(row["inner_fold"])) != inner
    )


def compile_capabilities(
    *, root: Path, reverse: bool, expected_compiler_sha256: str
) -> tuple[Path, Path]:
    """Publish disjoint training-only model and truth-only scorer roots."""

    _require(
        runner.sha256_path(SCRIPT) == expected_compiler_sha256,
        "compiler source receipt differs",
    )
    _require(not root.exists() and not root.is_symlink(), "replay root exists")
    root.mkdir(parents=True)
    features, folds, truth = _fixture_rows(reverse)
    features.sort(key=lambda row: str(row["molecule_id"]))
    folds.sort(
        key=lambda row: (
            str(row["molecule_id"]),
            int(str(row["repeat"])),
            int(str(row["outer_validation_fold"])),
        )
    )
    truth.sort(key=lambda row: (str(row["molecule_id"]), str(row["endpoint"])))
    feature_bytes = runner.csv_bytes(runner.FEATURE_COLUMNS, features)
    fold_bytes = runner.csv_bytes(runner.FOLD_COLUMNS, folds)
    truth_bytes = runner.csv_bytes(runner.TRUTH_COLUMNS, truth)
    array_files = _arrays()
    values = {
        (str(row["molecule_id"]), str(row["endpoint"])): str(row["point"])
        for row in truth
    }
    model_files: dict[str, bytes] = {
        "feature_rows.csv": feature_bytes,
        "folds.csv": fold_bytes,
        **array_files,
    }
    target_rows = 0
    for stage in ("outer", "inner"):
        for endpoint in runner.ENDPOINTS:
            for repeat in runner.REPEATS:
                for outer in runner.OUTER_FOLDS:
                    scope = _fold_scope(folds, repeat, outer)
                    inner_values = (
                        (None,) if stage == "outer" else tuple(runner.INNER_FOLDS)
                    )
                    for inner in inner_values:
                        identities = _training_ids(scope, stage, outer, inner)
                        rows = [
                            {
                                "molecule_id": molecule,
                                "point": values[(molecule, endpoint)],
                            }
                            for molecule in identities
                        ]
                        target_rows += len(rows)
                        path = (
                            Path("targets")
                            / stage
                            / endpoint
                            / f"repeat-{repeat}"
                            / f"outer-{outer}"
                            / ("targets.csv" if inner is None else f"inner-{inner}.csv")
                        )
                        model_files[path.as_posix()] = runner.csv_bytes(
                            runner.TARGET_COLUMNS, rows
                        )
    arrays = {
        name: {"sha256": runner.sha256_bytes(value), "bytes": len(value)}
        for name, value in array_files.items()
    }
    target_material = "".join(
        f"{name}|{runner.sha256_bytes(value)}\n"
        for name, value in sorted(model_files.items())
        if name.startswith("targets/")
    ).encode("utf-8")
    model_manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.global_v2_maplight_model_capability.v1",
        "contract_sha256": runner.CONTRACT_SHA256,
        "compiler_source_sha256": expected_compiler_sha256,
        "synthetic": True,
        "molecules": MOLECULES,
        "components": MOLECULES // 2,
        "feature_rows_sha256": runner.sha256_bytes(feature_bytes),
        "folds_sha256": runner.sha256_bytes(fold_bytes),
        "target_tree_sha256": runner.sha256_bytes(target_material),
        "arrays": arrays,
        "target_capabilities": {
            "files": 300,
            "training_rows": target_rows,
            "outer_validation_truth_rows": 0,
            "inner_validation_truth_rows": 0,
        },
        "authority": dict(runner.DENIED_AUTHORITY),
    }
    model_files["manifest.json"] = runner.json_bytes(model_manifest)
    model_root = runner.publish_files(root / "model-capability", model_files)
    model_manifest_sha = runner.sha256_path(model_root / "manifest.json")
    scorer_manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.global_v2_maplight_scorer_capability.v1",
        "contract_sha256": runner.CONTRACT_SHA256,
        "compiler_source_sha256": expected_compiler_sha256,
        "model_capability_manifest_sha256": model_manifest_sha,
        "synthetic": True,
        "truth_sha256": runner.sha256_bytes(truth_bytes),
        "truth_rows": len(truth),
        "model_training_files": 0,
        "feature_arrays": 0,
        "authority": dict(runner.DENIED_AUTHORITY),
    }
    scorer_root = runner.publish_files(
        root / "scorer-capability",
        {"truth.csv": truth_bytes, "manifest.json": runner.json_bytes(scorer_manifest)},
    )
    return model_root, scorer_root


def run_replay(
    *,
    root: Path,
    reverse: bool,
    expected_compiler_sha256: str,
    expected_runner_sha256: str,
) -> Path:
    """Run one fresh synthetic compilation, 300-fit prediction, and score path."""

    _require(
        runner.sha256_path(runner.SCRIPT) == expected_runner_sha256,
        "runner source receipt differs",
    )
    model_root, scorer_root = compile_capabilities(
        root=root,
        reverse=reverse,
        expected_compiler_sha256=expected_compiler_sha256,
    )
    prediction_root = runner.run_predictions(
        model_capability_root=model_root,
        output_root=root / "predictions",
    )
    return runner.score_predictions(
        prediction_root=prediction_root,
        scorer_capability_root=scorer_root,
        output_root=root / "terminal",
    )


def _tree_maps(root: Path) -> dict[str, dict[str, str]]:
    return {
        name: runner.relative_byte_map(root / name)
        for name in ("model-capability", "scorer-capability", "predictions", "terminal")
    }


def accept_replays(
    *,
    root_a: Path,
    root_b: Path,
    output_root: Path,
    expected_compiler_sha256: str,
    expected_runner_sha256: str,
) -> Path:
    """Accept only two byte-identical fresh replay trees."""

    _require(root_a.resolve() != root_b.resolve(), "replay roots are not distinct")
    _require(
        runner.sha256_path(SCRIPT) == expected_compiler_sha256,
        "compiler source receipt differs",
    )
    _require(
        runner.sha256_path(runner.SCRIPT) == expected_runner_sha256,
        "runner source receipt differs",
    )
    maps_a = _tree_maps(root_a)
    maps_b = _tree_maps(root_b)
    _require(maps_a == maps_b, "synthetic replay byte maps differ")
    terminal, _raw = runner._load_json(root_a / "terminal" / "manifest.json")
    _require(
        terminal["status"] == "G2_2B_SYNTHETIC_RUNNER_COMPLETE",
        "terminal status differs",
    )
    forbidden = {
        name: value
        for name, value in terminal["accounting"].items()
        if name
        in {
            "official_target_values_opened",
            "official_features_opened",
            "official_model_fits",
            "official_predictions_generated",
            "official_metric_evaluations",
            "confirmatory_truth_values_opened",
            "historical_r3c_row_level_artifacts_opened",
            "blinded_test_files_opened",
            "tdi_files_opened",
            "submissions_created",
            "leaderboard_observations",
            "tutorial_ma_st_rae_calls",
        }
    }
    _require(
        bool(forbidden) and all(value == 0 for value in forbidden.values()),
        "forbidden operation occurred",
    )
    canonical_map = runner.json_bytes(maps_a)
    receipt = {
        "schema_version": "cypshift.openadmet_cyp_2026.global_v2_maplight_synthetic_acceptance.v1",
        "status": "G2_2B_SYNTHETIC_RUNNER_ACCEPTED",
        "contract_sha256": runner.CONTRACT_SHA256,
        "compiler_source_sha256": expected_compiler_sha256,
        "runner_source_sha256": expected_runner_sha256,
        "research_uv_lock_sha256": runner.LOCK_SHA256,
        "resolved_parameter_sha256": runner.PARAMETER_SHA256,
        "roots": 2,
        "second_source_order_reversed": True,
        "relative_byte_maps_identical": True,
        "combined_tree_sha256": runner.sha256_bytes(canonical_map),
        "files_compared": sum(len(value) for value in maps_a.values()),
        "counts": terminal["counts"],
        "accounting": terminal["accounting"],
        "authority": dict(runner.DENIED_AUTHORITY),
        "scientific_interpretation": "Synthetic mechanics only; no synthetic diagnostic value may select or rank a model.",
        "next_gate": "Freeze a distinct additive G2-2C development-only execution contract and unconsumed claim before opening any official input.",
    }
    return runner.publish_files(
        output_root, {"acceptance.json": runner.json_bytes(receipt)}
    )


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    replay = subparsers.add_parser("replay")
    replay.add_argument("--root", type=Path, required=True)
    replay.add_argument("--reverse", action="store_true")
    replay.add_argument("--expected-compiler-sha256", required=True)
    replay.add_argument("--expected-runner-sha256", required=True)
    accept = subparsers.add_parser("accept")
    accept.add_argument("--root-a", type=Path, required=True)
    accept.add_argument("--root-b", type=Path, required=True)
    accept.add_argument("--output-root", type=Path, required=True)
    accept.add_argument("--expected-compiler-sha256", required=True)
    accept.add_argument("--expected-runner-sha256", required=True)
    args = parser.parse_args(argv)
    if args.command == "replay":
        run_replay(
            root=args.root,
            reverse=args.reverse,
            expected_compiler_sha256=args.expected_compiler_sha256,
            expected_runner_sha256=args.expected_runner_sha256,
        )
    else:
        accept_replays(
            root_a=args.root_a,
            root_b=args.root_b,
            output_root=args.output_root,
            expected_compiler_sha256=args.expected_compiler_sha256,
            expected_runner_sha256=args.expected_runner_sha256,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

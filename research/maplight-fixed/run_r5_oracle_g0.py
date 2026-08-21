#!/usr/bin/env python3
"""Run one receipt-bound TRACE G0 oracle episode in a fresh locked process."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn, cast

import numpy as np

_IO_SPEC = importlib.util.spec_from_file_location(
    "r5_oracle_g0_io", Path(__file__).with_name("r5_oracle_g0_io.py")
)
assert _IO_SPEC is not None and _IO_SPEC.loader is not None
bound = importlib.util.module_from_spec(_IO_SPEC)
sys.modules[_IO_SPEC.name] = bound
_IO_SPEC.loader.exec_module(bound)

G0Error = bound.G0Error
CONTRACT_SHA256 = bound.CONTRACT_SHA256
PARENT_CONTRACT_SHA256 = bound.PARENT_CONTRACT_SHA256
RESOLVED_CONTRACT_SHA256 = (
    "9143ecd1b24d1d9a97b1e5821e2b953f4cfffcec1cc39de3a8c49b81a4f58a50"
)
CONTRACT_ID = "R5-CYP3A4-ORACLE-V1"
MODEL_ID = bound.MODEL_ID
MAP_ARRAYS = bound.MAP_ARRAYS

MOLECULE_COLUMNS = (
    "molecule_id",
    "raw_smiles",
    "raw_structure_sha256",
    "standardized_smiles",
    "standardized_structure_hash",
    "similarity_component_hash",
)
FOLD_COLUMNS = (
    "molecule_id",
    "similarity_component_hash",
    "repeat",
    "seed",
    "outer_fold",
    "outer_validation_fold",
    "inner_fold",
)
PUBLIC_COLUMNS = (
    "episode_id",
    "episode_policy_id",
    "repeat",
    "outer_fold",
    "outer_group_id",
    "anchor_molecule_id",
    "query_molecule_id",
    "query_rank",
)
POINT_COLUMNS = ("molecule_id", "component_id", "point", "sample_weight")
ANCHOR_COLUMNS = (
    "episode_id",
    "anchor_molecule_id",
    "anchor_point_available",
    "anchor_point",
)
FRAGMENT_COLUMNS = (
    "molecule_id",
    "endpoint",
    "component_id",
    "repeat",
    "outer_fold",
    "inner_fold",
    "scope",
    "system_id",
    "prediction",
    "applicability_score",
    "model_id",
    "feature_spec_id",
    "split_id",
)
CATBOOST_ARGS = {
    "loss_function": "MAE",
    "random_strength": 2,
    "random_seed": 1,
    "task_type": "CPU",
    "thread_count": 16,
    "verbose": 0,
    "allow_writing_files": False,
}
FEATURE_SPEC_ID = "maplight-fixed-stage-a-v1"


def _source_bundle_receipt() -> tuple[str, dict[str, str]]:
    paths = [Path(__file__), Path(__file__).with_name("r5_oracle_g0_io.py")]
    receipts = {
        path.relative_to(bound.ROOT).as_posix(): cast(str, bound.sha(path.read_bytes()))
        for path in sorted(
            paths, key=lambda item: item.relative_to(bound.ROOT).as_posix()
        )
    }
    payload = "".join(
        f"{name}|{digest}\n" for name, digest in receipts.items()
    ).encode()
    return cast(str, bound.sha(payload)), receipts


def _source_bundle_sha() -> str:
    return _source_bundle_receipt()[0]


def _int(value: object, label: str, low: int, high: int) -> int:
    try:
        parsed = int(cast(str | int, value))
    except (TypeError, ValueError) as exc:
        raise G0Error(f"{label} differs") from exc
    bound.require(str(parsed) == str(value), f"{label} is noncanonical")
    bound.require(low <= parsed <= high, f"{label} differs")
    return parsed


def _finite(value: str, label: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise G0Error(f"{label} differs") from exc
    bound.require(math.isfinite(parsed), f"{label} is nonfinite")
    return parsed


def _receipt_columns(
    manifest: Mapping[str, Any], name: str, columns: Sequence[str]
) -> None:
    record = cast(Mapping[str, Any], manifest["output_receipts"])[name]
    bound.require(record["columns"] == list(columns), f"column receipt differs: {name}")


def _feature_arrays(
    loaded: Mapping[str, bytes], molecule_count: int
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    arrays: list[np.ndarray[Any, Any]] = []
    for name, width, dtype in MAP_ARRAYS:
        array = bound.npy(loaded[name], molecule_count, width, dtype, name)
        if name == "maplight_rdkit_descriptors.npy":
            bound.require(not np.isinf(array).any(), "descriptor contains infinity")
            allowed = np.zeros(width, dtype=bool)
            allowed[[39, 41, 43, 45]] = True
            bound.require(
                not np.isnan(array[:, ~allowed]).any(), "descriptor NaN mask differs"
            )
        else:
            bound.require(
                np.isfinite(array).all(), f"feature contains nonfinite: {name}"
            )
        arrays.append(array)
    morgan = bound.npy(
        loaded[bound.MORGAN_FILE[0]],
        molecule_count,
        bound.MORGAN_FILE[1],
        bound.MORGAN_FILE[2],
        bound.MORGAN_FILE[0],
    )
    bound.require(np.logical_or(morgan == 0, morgan == 1).all(), "Morgan is not binary")
    features = np.ascontiguousarray(np.concatenate(arrays, axis=1))
    bound.require(features.shape == (molecule_count, 2563), "MapLight width differs")
    return cast(np.ndarray[Any, Any], features), morgan


def _fit_predict(
    X: np.ndarray[Any, Any], y: np.ndarray[Any, Any], query: np.ndarray[Any, Any]
) -> tuple[np.ndarray[Any, Any], dict[str, Any]]:
    try:
        from catboost import CatBoostRegressor  # type: ignore[import-not-found]
    except ImportError as exc:
        raise G0Error("CatBoost 1.2.1 is unavailable") from exc
    model = CatBoostRegressor(**CATBOOST_ARGS)
    model.fit(X, y)
    params = cast(dict[str, Any], model.get_all_params())
    bound.require(
        params == bound.ACCEPTED_PARAMETERS, "resolved CatBoost parameters differ"
    )
    bound.require(
        bound.sha(bound.json_bytes(params)) == bound.PARAMETER_SHA256,
        "resolved CatBoost parameter receipt differs",
    )
    prediction = np.asarray(model.predict(query), dtype=np.float64)
    bound.require(
        prediction.shape == (len(query),) and np.isfinite(prediction).all(),
        "CatBoost predictions differ",
    )
    return prediction, params


def _fold_slice(
    rows: Sequence[Mapping[str, str]], repeat: int, current_outer: int
) -> dict[str, Mapping[str, str]]:
    selected = [
        row
        for row in rows
        if _int(row["repeat"], "fold repeat", 0, 2) == repeat
        and _int(row["outer_validation_fold"], "current outer fold", 0, 4)
        == current_outer
    ]
    result = {row["molecule_id"]: row for row in selected}
    bound.require(len(result) == len(selected) and bool(result), "fold slice differs")
    return result


def _is_training(
    row: Mapping[str, str], stage: str, current_outer: int, inner: int | None
) -> bool:
    assigned_outer = _int(row["outer_fold"], "assigned outer fold", 0, 4)
    if assigned_outer == current_outer:
        return False
    if stage == "outer":
        return True
    bound.require(inner is not None, "inner scope differs")
    return _int(row["inner_fold"], "assigned inner fold", 0, 3) != inner


def _tanimoto(a: np.ndarray[Any, Any], b: np.ndarray[Any, Any]) -> float:
    intersection = int(np.logical_and(a, b).sum())
    union = int(np.logical_or(a, b).sum())
    return 1.0 if union == 0 else float(intersection) / float(union)


def _identity(value: object) -> str:
    return hashlib.sha256(bound.json_bytes(value)).hexdigest()


def _compact_identity(value: object) -> str:
    data = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _validate_episode_policy(
    stage: object, queries: Sequence[Mapping[str, str]]
) -> None:
    policies = {row["episode_policy_id"] for row in queries}
    allowed = (
        {"selected_anchor", "deterministic_random_anchor_stress"}
        if stage == "outer"
        else {"selected_anchor"}
    )
    bound.require(len(policies) == 1 and policies <= allowed, "episode policy differs")


def run_g0(
    *,
    model_public_root: Path,
    model_public_manifest_sha256: str,
    episode_target_root: Path,
    episode_target_manifest_sha256: str,
    expected_source_bundle_sha256: str,
    expected_episode_view_builder_source_sha256: str,
    expected_source_cell_target_manifest_sha256: str,
    output_root: Path,
) -> Path:
    """Consume exactly one model-public and one episode-target capability."""

    locked_runtime = bound.runtime()
    bound.validate_parameter_source()
    observed_source_bundle_sha, source_file_receipts = _source_bundle_receipt()
    bound.require(
        bound.is_sha(expected_source_bundle_sha256)
        and expected_source_bundle_sha256 == observed_source_bundle_sha,
        "G0 source bundle receipt differs",
    )
    model_data, model_manifest = bound.load_model(
        model_public_root, model_public_manifest_sha256
    )
    episode_data, episode_manifest = bound.load_episode(
        episode_target_root,
        episode_target_manifest_sha256,
        model_public_manifest_sha256,
        model_manifest,
        expected_episode_view_builder_source_sha256,
        expected_source_cell_target_manifest_sha256,
    )
    _receipt_columns(model_manifest, "molecules.csv", MOLECULE_COLUMNS)
    _receipt_columns(model_manifest, "folds.csv", FOLD_COLUMNS)
    _receipt_columns(model_manifest, "public_episode_queries.csv", PUBLIC_COLUMNS)
    _receipt_columns(episode_manifest, "training_points.csv", POINT_COLUMNS)
    _receipt_columns(episode_manifest, "episode_anchor_context.csv", ANCHOR_COLUMNS)

    molecules = bound.csv_rows(
        model_data["molecules.csv"], MOLECULE_COLUMNS, "molecules"
    )
    folds = bound.csv_rows(model_data["folds.csv"], FOLD_COLUMNS, "folds")
    public = bound.csv_rows(
        model_data["public_episode_queries.csv"], PUBLIC_COLUMNS, "public queries"
    )
    points = bound.csv_rows(
        episode_data["training_points.csv"], POINT_COLUMNS, "training points"
    )
    anchors = bound.csv_rows(
        episode_data["episode_anchor_context.csv"], ANCHOR_COLUMNS, "anchor context"
    )
    ids = [row["molecule_id"] for row in molecules]
    bound.require(ids == sorted(set(ids)) and ids, "molecule order differs")
    molecule_by_id = {row["molecule_id"]: row for row in molecules}
    for row in molecules:
        bound.require(
            bound.is_sha(row["raw_structure_sha256"])
            and bound.is_sha(row["standardized_structure_hash"])
            and bool(row["similarity_component_hash"]),
            "molecule identity differs",
        )

    scope = cast(Mapping[str, Any], episode_manifest["scope"])
    stage = scope["stage"]
    bound.require(stage in {"outer", "inner"}, "episode stage differs")
    repeat = _int(scope["repeat"], "episode repeat", 0, 2)
    current_outer = _int(
        scope["current_outer_validation_fold"], "current outer validation fold", 0, 4
    )
    episode_outer = _int(scope["episode_outer_fold"], "episode outer fold", 0, 4)
    inner_value = scope["inner_fold"]
    if stage == "outer":
        bound.require(
            inner_value == "" and current_outer == episode_outer, "outer scope differs"
        )
        inner: int | None = None
    else:
        inner = _int(inner_value, "episode inner fold", 0, 3)
        bound.require(current_outer != episode_outer, "inner scope pairing differs")
    fold_by_id = _fold_slice(folds, repeat, current_outer)
    bound.require(set(fold_by_id) == set(ids), "fold/molecule identity differs")
    for molecule_id, fold in fold_by_id.items():
        bound.require(
            fold["similarity_component_hash"]
            == molecule_by_id[molecule_id]["similarity_component_hash"],
            "fold component differs",
        )

    episode = cast(Mapping[str, Any], episode_manifest["episode"])
    episode_id = episode["episode_id"]
    bound.require(bound.is_sha(episode_id), "episode identity differs")
    anchor_id = episode["anchor_molecule_id"]
    queries = [row for row in public if row["episode_id"] == episode_id]
    queries.sort(key=lambda row: _int(row["query_rank"], "query rank", 1, 10**9))
    bound.require(
        len(queries) == episode["query_rows"]
        and bound.sha(bound.csv_bytes(PUBLIC_COLUMNS, queries))
        == episode["query_rows_sha256"],
        "fixed episode query superset differs",
    )
    bound.require(
        [int(row["query_rank"]) for row in queries] == list(range(1, len(queries) + 1)),
        "query ranks differ",
    )
    _validate_episode_policy(stage, queries)
    heldout_component = molecule_by_id[anchor_id]["similarity_component_hash"]
    query_ids: list[str] = []
    for row in queries:
        query_id = row["query_molecule_id"]
        bound.require(
            row["repeat"] == str(repeat)
            and row["outer_fold"] == str(episode_outer)
            and row["anchor_molecule_id"] == anchor_id
            and row["outer_group_id"] == heldout_component
            and query_id in molecule_by_id
            and molecule_by_id[query_id]["similarity_component_hash"]
            == heldout_component,
            "public episode scope differs",
        )
        query_fold = fold_by_id[query_id]
        bound.require(
            _int(query_fold["outer_fold"], "query outer fold", 0, 4) == episode_outer
            and (
                stage == "outer"
                or _int(query_fold["inner_fold"], "query inner fold", 0, 3) == inner
            ),
            "query fold exposure differs",
        )
        query_ids.append(query_id)
    bound.require(len(set(query_ids)) == len(query_ids), "duplicate episode query")

    bound.require(len(anchors) == 1, "episode must expose exactly one anchor row")
    anchor = anchors[0]
    anchor_fold = fold_by_id.get(anchor_id)
    bound.require(
        anchor["episode_id"] == episode_id
        and anchor["anchor_molecule_id"] == anchor_id
        and anchor_id in molecule_by_id
        and anchor_fold is not None
        and _int(anchor_fold["outer_fold"], "anchor outer fold", 0, 4) == episode_outer
        and (
            stage == "outer"
            or _int(anchor_fold["inner_fold"], "anchor inner fold", 0, 3) == inner
        ),
        "anchor exposure differs",
    )
    available_token = anchor["anchor_point_available"]
    bound.require(available_token in {"true", "false"}, "anchor availability differs")
    anchor_available = available_token == "true"
    if anchor_available:
        anchor_point = _finite(anchor["anchor_point"], "anchor point")
    else:
        bound.require(anchor["anchor_point"] == "", "unavailable anchor is nonempty")
        anchor_point = None
    bound.require(anchor_id not in query_ids, "anchor appears in query superset")

    point_by_id: dict[str, float] = {}
    for row in points:
        molecule_id = row["molecule_id"]
        bound.require(
            molecule_id in molecule_by_id
            and molecule_id not in point_by_id
            and molecule_id != anchor_id
            and molecule_id not in query_ids
            and row["component_id"]
            == molecule_by_id[molecule_id]["similarity_component_hash"]
            and row["component_id"] != heldout_component
            and row["sample_weight"] == "1.0"
            and _is_training(
                fold_by_id[molecule_id], cast(str, stage), current_outer, inner
            ),
            "current-training point differs",
        )
        point_by_id[molecule_id] = _finite(row["point"], "training point")
    expected_accounting = dict.fromkeys(bound.ACCOUNTING_FIELDS, 0)
    expected_accounting["direct_target_values_parsed"] = len(points) + int(
        anchor_available
    )
    expected_accounting["anchor_labels_exposed_to_models"] = int(anchor_available)
    bound.require(
        episode_manifest["operation_accounting"] == expected_accounting,
        "episode target accounting differs",
    )
    train_ids = sorted(point_by_id)
    bound.require(bool(train_ids), "current-training population is empty")
    features, morgan = _feature_arrays(model_data, len(molecules))
    row_index = {molecule_id: index for index, molecule_id in enumerate(ids)}
    fit_ids = [*train_ids, *([anchor_id] if anchor_available else [])]
    X = features[[row_index[molecule_id] for molecule_id in fit_ids]]
    fit_values = [point_by_id[molecule_id] for molecule_id in train_ids]
    if anchor_point is not None:
        fit_values.append(anchor_point)
    y = np.asarray(fit_values)
    query_index = [row_index[molecule_id] for molecule_id in query_ids]
    prediction, resolved = _fit_predict(X, y, features[query_index])
    applicability = [
        max(
            _tanimoto(morgan[row_index[molecule_id]], morgan[row_index[train]])
            for train in fit_ids
        )
        for molecule_id in query_ids
    ]
    scope_name = f"openadmet-oracle-{stage}-v1"
    candidate_id = _compact_identity([CONTRACT_ID, "G0", None, None])
    cell_id = _compact_identity(
        [
            CONTRACT_ID,
            stage,
            repeat,
            current_outer,
            -1 if inner is None else inner,
            "G0",
            candidate_id,
            episode_id,
        ]
    )
    causal = {
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "model_public_manifest_sha256": model_public_manifest_sha256,
        "episode_target_manifest_sha256": episode_target_manifest_sha256,
        "r3c_parameter_source": bound.R3C_PARAMETER_SOURCE,
        "scope": dict(scope),
    }
    split_id = _identity({"kind": "oracle-episode-split", **causal})
    model_instance_id = _identity({"kind": "oracle-g0-model", **causal})
    fragment_rows = [
        {
            "molecule_id": molecule_id,
            "endpoint": "CYP3A4",
            "component_id": heldout_component,
            "repeat": repeat,
            "outer_fold": episode_outer,
            "inner_fold": "" if inner is None else inner,
            "scope": scope_name,
            "system_id": MODEL_ID,
            "prediction": format(float(value), ".17g"),
            "applicability_score": format(score, ".17g"),
            "model_id": model_instance_id,
            "feature_spec_id": FEATURE_SPEC_ID,
            "split_id": split_id,
        }
        for molecule_id, value, score in zip(
            query_ids, prediction, applicability, strict=True
        )
    ]
    fragment = bound.csv_bytes(FRAGMENT_COLUMNS, fragment_rows)
    operation = dict(expected_accounting)
    operation["maplight_model_fits"] = 1
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.r5c_g0_prediction_fragment.v1",
        "status": "R5_ORACLE_G0_EPISODE_COMPLETE",
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "parent_contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": source_file_receipts[
            Path(__file__).relative_to(bound.ROOT).as_posix()
        ],
        "g0_source_bundle_sha256": observed_source_bundle_sha,
        "g0_source_file_receipts": source_file_receipts,
        "model_public_manifest_sha256": model_public_manifest_sha256,
        "episode_target_manifest_sha256": episode_target_manifest_sha256,
        "trusted_episode_parent_receipts": {
            "episode_view_builder_source_sha256": (
                expected_episode_view_builder_source_sha256
            ),
            "source_cell_target_manifest_sha256": (
                expected_source_cell_target_manifest_sha256
            ),
        },
        "source_bundle_binding": model_manifest["source_bundle_binding"],
        "scope": dict(scope),
        "episode": dict(episode),
        "system_id": "G0",
        "source_system_id": MODEL_ID,
        "candidate_id": candidate_id,
        "cell_id": cell_id,
        "public_query_receipt_sha256": episode["query_rows_sha256"],
        "runtime": locked_runtime,
        "r3c_parameter_source": bound.R3C_PARAMETER_SOURCE,
        "resolved_catboost_parameters": resolved,
        "counts": {
            "current_training_points": len(points),
            "anchor_rows": int(anchor_available),
            "fit_rows": len(fit_ids),
            "query_rows": len(query_ids),
        },
        "operation_accounting": operation,
        "prediction_fragment": {
            "sha256": bound.sha(fragment),
            "bytes": len(fragment),
            "rows": len(fragment_rows),
            "columns": list(FRAGMENT_COLUMNS),
        },
        "authority": dict(bound.DENIED_AUTHORITY),
    }
    return cast(Path, bound.publish(output_root, fragment, manifest))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-public-root", type=Path, required=True)
    parser.add_argument("--model-public-manifest-sha256", required=True)
    parser.add_argument("--episode-target-root", type=Path, required=True)
    parser.add_argument("--episode-target-manifest-sha256", required=True)
    parser.add_argument("--expected-source-bundle-sha256", required=True)
    parser.add_argument("--expected-episode-view-builder-source-sha256", required=True)
    parser.add_argument("--expected-source-cell-target-manifest-sha256", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def _fail(message: str) -> NoReturn:
    print(f"G0_ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def main() -> None:
    args = _parser().parse_args()
    try:
        run_g0(
            model_public_root=args.model_public_root,
            model_public_manifest_sha256=args.model_public_manifest_sha256,
            episode_target_root=args.episode_target_root,
            episode_target_manifest_sha256=args.episode_target_manifest_sha256,
            expected_source_bundle_sha256=args.expected_source_bundle_sha256,
            expected_episode_view_builder_source_sha256=(
                args.expected_episode_view_builder_source_sha256
            ),
            expected_source_cell_target_manifest_sha256=(
                args.expected_source_cell_target_manifest_sha256
            ),
            output_root=args.output_root,
        )
    except (G0Error, OSError) as exc:
        _fail(str(exc))


if __name__ == "__main__":
    main()

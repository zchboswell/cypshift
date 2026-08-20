"""Synthetic least-privilege projections for the frozen TRACE oracle contract.

This is a strict capability splitter for a prebuilt synthetic source bundle.
It deliberately does not compile trusted R2/R3/R4 sources or run a model.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Final

from cypshift.openadmet_oracle_validation import (
    ANCHOR_CONTEXT_COLUMNS,
    CLIFF_COLUMNS,
    FEATURE_FILES,
    G0_SYSTEM_ID,
    GLOBAL_CONTEXT_COLUMNS,
    INNER_OOF_INPUT,
    OUTER_OOF_INPUT,
    PUBLIC_QUERY_COLUMNS,
    SCOPE_COLUMNS,
    SOURCE_COLUMNS,
    TRAINING_PAIR_COLUMNS,
    TRAINING_POINT_COLUMNS,
    OpenADMETOracleProjectionError,
    Scope,
    ValidatedOracleSources,
    csv_rows,
    output_columns,
    scope,
    validate_oracle_sources,
)
from cypshift.openadmet_transformation_compiler import PAIR_COLUMNS
from cypshift.openadmet_transformation_io import (
    STRUCTURE_COLUMNS,
    canonical_csv_bytes,
    canonical_json_bytes,
    strict_json_object,
)
from cypshift.openadmet_transformation_projection import (
    FOLD_PROJECTION_COLUMNS,
    _cleanup_stage,
    _readonly_tree,
    _rename_noreplace,
    _safe_output_parent,
    _write_new,
)
from cypshift.openadmet_transformation_serialization import EPISODE_COLUMNS

CONTRACT_SHA256: Final = (
    "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
)
PARENT_CONTRACT_SHA256: Final = (
    "c1d7a66c4f479339b30c2006e4250381cb213d665d4902c71d4c4edbd347e8bf"
)
SCHEMA_VERSION: Final = "cypshift.openadmet_cyp_2026.oracle_projection.v1"

PUBLIC_FILES: Final = (
    "manifest.json",
    "molecules.csv",
    "folds.csv",
    "public_episode_queries.csv",
    "transformation_pairs.csv",
    "episode_transformations.csv",
    *FEATURE_FILES,
)
CELL_FILES: Final = (
    "manifest.json",
    "training_points.csv",
    "training_pairs.csv",
    "episode_anchor_contexts.csv",
)
C3_FILES: Final = (
    "manifest.json",
    "training_pairs.csv",
    "global_anchor_contexts.csv",
)
SCORER_FILES: Final = (
    "manifest.json",
    "episode_truth.csv",
    "activity_cliffs.csv",
)
SOURCE_FILES: Final = (
    "molecules.csv",
    "folds.csv",
    "public_episode_queries.csv",
    "transformation_pairs.csv",
    "episode_transformations.csv",
    *FEATURE_FILES,
    "training_points.csv",
    "training_pairs.csv",
    "episode_anchor_contexts.csv",
    "global_anchor_contexts.csv",
    "episode_truth.csv",
    "activity_cliffs.csv",
)

FORBIDDEN_PUBLIC_FIELDS: Final = (
    "selector_cyp_truth",
    "query_truth",
    "query_availability",
    "anchor_value",
    "target",
    "loss",
    "score",
)
ACCOUNTING_FIELDS: Final = (
    "direct_target_values_parsed",
    "anchor_labels_exposed_to_models",
    "query_truth_values_opened_by_scorers",
    "maplight_model_fits",
    "ridge_model_fits",
    "hierarchy_fits",
    "predictions_frozen",
    "internal_absolute_error_evaluations",
    "blinded_test_files_opened",
    "tdi_files_opened",
    "official_metric_calls",
    "submissions_created",
    "transductive_relationships",
    "inferred_anchor_candidate_pools",
)
DENIED_AUTHORITY: Final = {
    "oracle_evidence": False,
    "inferred_anchor_contract": False,
    "model_fits": False,
    "predictions": False,
    "internal_metrics": False,
    "official_st_rae": False,
    "test_access": False,
    "tdi": False,
    "submission": False,
    "transduction": False,
}
ROOT_ACCOUNTING: Final = {
    "root_families": 4,
    "model_public_roots": 1,
    "cell_target_roots": 75,
    "c3_target_roots": 75,
    "sealed_scorer_roots": 75,
    "total_capability_roots": 226,
}
SOURCE_MANIFEST_SCHEMA: Final = "cypshift.openadmet_cyp_2026.oracle_source_bundle.v1"
SOURCE_MANIFEST_FIELDS: Final = {
    "schema_version",
    "contract_sha256",
    "parent_receipts",
    "input_receipts",
    "source_receipts",
    "output_receipts",
    "columns",
    "counts",
    "operation_accounting",
    "authority",
}
SOURCE_PARENT_FILES: Final = (
    "direct_observations.csv",
    "group_folds.csv",
    "campaign_episodes_public.csv",
    "campaign_episodes_truth.csv",
    "episode_label_masks.csv",
    "feature_manifest.json",
    "feature_rows.csv",
    *FEATURE_FILES,
    "global_oof_predictions.csv",
    "global_inner_oof_predictions.csv",
    "transformation_pairs.csv",
    "episode_transformations.csv",
    "transformation_coverage.json",
)


@dataclass(frozen=True, slots=True)
class OracleProjectionResult:
    """All atomically published synthetic capability roots."""

    output_directory: Path
    model_public_root: Path
    cell_target_root: Path
    c3_target_root: Path
    sealed_scorer_root: Path
    manifest_paths: tuple[Path, ...]


def project_openadmet_oracle_inputs(
    source_directory: Path,
    output_directory: Path,
    *,
    expected_receipts: Mapping[str, str],
) -> OracleProjectionResult:
    """Validate one synthetic bundle and publish exact disjoint views once."""

    _reject_symlink_ancestry(source_directory, "source path")
    _reject_symlink_ancestry(output_directory, "output path")
    if output_directory.exists() or output_directory.is_symlink():
        raise OpenADMETOracleProjectionError("output path already exists")
    loaded, receipts, source_binding = _read_sources(
        source_directory, expected_receipts
    )
    parent_receipts = _object(
        source_binding["parent_receipts"], "source parent receipts"
    )
    validated = validate_oracle_sources(
        loaded,
        oof_receipts={
            OUTER_OOF_INPUT: _string_value(
                parent_receipts.get(OUTER_OOF_INPUT), "outer OOF parent receipt"
            ),
            INNER_OOF_INPUT: _string_value(
                parent_receipts.get(INNER_OOF_INPUT), "inner OOF parent receipt"
            ),
        },
    )
    for name, source_rows in validated.rows.items():
        receipts[name]["rows"] = len(source_rows)
        receipts[name]["columns"] = list(SOURCE_COLUMNS[name])
    payloads = _build_payloads(loaded, validated, receipts, source_binding)
    stage = Path(
        tempfile.mkdtemp(
            prefix=".r5b-projection-", dir=_safe_output_parent(output_directory)
        )
    )
    try:
        for relative, data in payloads.items():
            (stage / relative.parent).mkdir(parents=True, exist_ok=True)
            _write_new(stage / relative, data)
        _verify_stage(stage, payloads)
        _readonly_tree(stage)
        if output_directory.exists() or output_directory.is_symlink():
            raise OpenADMETOracleProjectionError("output path already exists")
        _rename_noreplace(stage, output_directory)
    except Exception:
        _cleanup_stage(stage)
        raise
    manifests = tuple(
        sorted(
            output_directory / relative
            for relative in payloads
            if relative.name == "manifest.json"
        )
    )
    return OracleProjectionResult(
        output_directory=output_directory,
        model_public_root=output_directory / "model-public",
        cell_target_root=output_directory / "cell-target",
        c3_target_root=output_directory / "c3-target",
        sealed_scorer_root=output_directory / "sealed-scorer",
        manifest_paths=manifests,
    )


def _read_sources(
    directory: Path, expected: Mapping[str, str]
) -> tuple[dict[str, bytes], dict[str, dict[str, Any]], dict[str, Any]]:
    if not directory.is_dir() or directory.is_symlink():
        raise OpenADMETOracleProjectionError("source directory is not regular")
    expected_names = set(SOURCE_FILES) | {"manifest.json"}
    if set(expected) != expected_names:
        raise OpenADMETOracleProjectionError("source receipt set differs")
    if {entry.name for entry in directory.iterdir()} != expected_names:
        raise OpenADMETOracleProjectionError("source file set differs")
    manifest_path = directory / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise OpenADMETOracleProjectionError("source manifest is not regular")
    manifest_data = manifest_path.read_bytes()
    manifest_receipt = expected["manifest.json"]
    _require_digest(manifest_receipt, "source manifest receipt")
    if sha256(manifest_data).hexdigest() != manifest_receipt:
        raise OpenADMETOracleProjectionError("source manifest SHA-256 mismatch")
    manifest = _validate_source_manifest(manifest_data, expected)
    loaded: dict[str, bytes] = {}
    receipts: dict[str, dict[str, Any]] = {}
    for name in SOURCE_FILES:
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise OpenADMETOracleProjectionError(f"source file is not regular: {name}")
        receipt = expected[name]
        _require_digest(receipt, f"source receipt: {name}")
        data = path.read_bytes()
        if sha256(data).hexdigest() != receipt:
            raise OpenADMETOracleProjectionError(f"source SHA-256 mismatch: {name}")
        loaded[name] = data
        receipts[name] = {"sha256": receipt, "bytes": len(data)}
    _validate_manifest_leaf_receipts(manifest, loaded, expected)
    binding = {
        "manifest_receipt": {
            "sha256": manifest_receipt,
            "bytes": len(manifest_data),
        },
        "schema_version": manifest["schema_version"],
        "contract_sha256": manifest["contract_sha256"],
        "parent_receipts": manifest["parent_receipts"],
        "input_receipts": manifest["input_receipts"],
        "source_receipts": manifest["source_receipts"],
    }
    return loaded, receipts, binding


def _validate_source_manifest(
    data: bytes, expected: Mapping[str, str]
) -> dict[str, Any]:
    manifest: dict[str, Any] = strict_json_object(data, "source bundle manifest")
    if canonical_json_bytes(manifest) != data:
        raise OpenADMETOracleProjectionError("source manifest is not canonical")
    if set(manifest) != SOURCE_MANIFEST_FIELDS:
        raise OpenADMETOracleProjectionError("source manifest fields differ")
    if manifest.get("schema_version") != SOURCE_MANIFEST_SCHEMA:
        raise OpenADMETOracleProjectionError("source manifest schema differs")
    if manifest.get("contract_sha256") != CONTRACT_SHA256:
        raise OpenADMETOracleProjectionError("source manifest contract differs")
    authority = _object(manifest.get("authority"), "source authority")
    if authority != DENIED_AUTHORITY:
        raise OpenADMETOracleProjectionError("source authority differs")
    accounting = _object(manifest.get("operation_accounting"), "source accounting")
    if set(accounting) != set(ACCOUNTING_FIELDS) or any(
        not _is_nonnegative_integer(value) for value in accounting.values()
    ):
        raise OpenADMETOracleProjectionError("source accounting shape differs")
    for name in (
        "blinded_test_files_opened",
        "tdi_files_opened",
        "official_metric_calls",
        "submissions_created",
        "transductive_relationships",
        "inferred_anchor_candidate_pools",
    ):
        if accounting[name] != 0:
            raise OpenADMETOracleProjectionError("source forbidden accounting differs")
    columns = _object(manifest.get("columns"), "source columns")
    if columns != {name: list(value) for name, value in SOURCE_COLUMNS.items()}:
        raise OpenADMETOracleProjectionError("source manifest columns differ")
    counts = _object(manifest.get("counts"), "source counts")
    if set(counts) != {
        "molecules",
        "direct_rows",
        "fold_rows",
        "selected_public_rows",
        "stress_public_rows",
    } or any(not _is_nonnegative_integer(value) for value in counts.values()):
        raise OpenADMETOracleProjectionError("source manifest counts differ")
    parent = _object(manifest.get("parent_receipts"), "source parent receipts")
    inputs = _object(manifest.get("input_receipts"), "source input receipts")
    sources = _object(manifest.get("source_receipts"), "source receipts")
    if (
        set(parent) != set(SOURCE_PARENT_FILES)
        or set(inputs) != set(SOURCE_PARENT_FILES)
        or inputs != sources
    ):
        raise OpenADMETOracleProjectionError("source parent binding differs")
    for name, value in parent.items():
        if not isinstance(value, str):
            raise OpenADMETOracleProjectionError("source parent receipt differs")
        _require_digest(value, f"source parent receipt: {name}")
        record = _object(inputs[name], f"source input receipt: {name}")
        if (
            set(record) != {"sha256", "bytes"}
            or record["sha256"] != value
            or not _is_nonnegative_integer(record["bytes"])
        ):
            raise OpenADMETOracleProjectionError("source input binding differs")
    outputs = _object(manifest.get("output_receipts"), "source outputs")
    if set(outputs) != set(SOURCE_FILES):
        raise OpenADMETOracleProjectionError("source output receipt set differs")
    for name in SOURCE_FILES:
        record = _object(outputs[name], f"source output receipt: {name}")
        if record.get("sha256") != expected[name]:
            raise OpenADMETOracleProjectionError("source output SHA binding differs")
    return manifest


def _validate_manifest_leaf_receipts(
    manifest: Mapping[str, Any],
    loaded: Mapping[str, bytes],
    expected: Mapping[str, str],
) -> None:
    outputs = _object(manifest["output_receipts"], "source outputs")
    for name in SOURCE_FILES:
        data = loaded[name]
        record = _object(outputs[name], f"source output receipt: {name}")
        columns = list(SOURCE_COLUMNS[name]) if name.endswith(".csv") else []
        rows = data.count(b"\n") - 1 if name.endswith(".csv") else 0
        if set(record) != {"sha256", "bytes", "rows", "columns"} or record != {
            "sha256": expected[name],
            "bytes": len(data),
            "rows": rows,
            "columns": columns,
        }:
            raise OpenADMETOracleProjectionError(
                f"source output receipt metadata differs: {name}"
            )


def _build_payloads(
    loaded: Mapping[str, bytes],
    validated: ValidatedOracleSources,
    source_receipts: Mapping[str, Mapping[str, Any]],
    source_binding: Mapping[str, Any],
) -> dict[Path, bytes]:
    rows = validated.rows
    public_rows = sorted(
        validated.public.values(),
        key=lambda row: (row["episode_id"], int(row["query_rank"])),
    )
    model_data = {
        "molecules.csv": canonical_csv_bytes(
            STRUCTURE_COLUMNS, list(validated.molecules.values())
        ),
        "folds.csv": canonical_csv_bytes(
            FOLD_PROJECTION_COLUMNS,
            sorted(
                rows["folds.csv"],
                key=lambda row: (
                    row["molecule_id"],
                    int(row["repeat"]),
                    int(row["outer_validation_fold"]),
                ),
            ),
        ),
        "public_episode_queries.csv": canonical_csv_bytes(
            PUBLIC_QUERY_COLUMNS, public_rows
        ),
        "transformation_pairs.csv": canonical_csv_bytes(
            PAIR_COLUMNS,
            sorted(
                rows["transformation_pairs.csv"],
                key=lambda row: row["transformation_pair_id"],
            ),
        ),
        "episode_transformations.csv": canonical_csv_bytes(
            EPISODE_COLUMNS,
            sorted(
                rows["episode_transformations.csv"],
                key=lambda row: (row["episode_id"], int(row["query_rank"])),
            ),
        ),
        **{name: loaded[name] for name in FEATURE_FILES},
    }
    process_accounting = _process_accounting(rows)
    payloads = _root_payloads(
        Path("model-public"),
        model_data,
        "all",
        source_receipts,
        set(model_data),
        _zero_accounting(),
        process_accounting,
        source_binding,
    )
    for cell_scope in validated.scopes:
        label = _scope_label(cell_scope)
        scoped = {
            name: [
                {key: value for key, value in row.items() if key not in SCOPE_COLUMNS}
                for row in rows[name]
                if scope(row) == cell_scope
            ]
            for name in (
                "training_points.csv",
                "training_pairs.csv",
                "episode_anchor_contexts.csv",
                "global_anchor_contexts.csv",
                "episode_truth.csv",
                "activity_cliffs.csv",
            )
        }
        cell_data = {
            "training_points.csv": _scoped_csv(
                "training_points.csv", scoped["training_points.csv"]
            ),
            "training_pairs.csv": _scoped_csv(
                "training_pairs.csv", scoped["training_pairs.csv"]
            ),
            "episode_anchor_contexts.csv": _scoped_csv(
                "episode_anchor_contexts.csv", scoped["episode_anchor_contexts.csv"]
            ),
        }
        c3_data = {
            "training_pairs.csv": cell_data["training_pairs.csv"],
            "global_anchor_contexts.csv": _scoped_csv(
                "global_anchor_contexts.csv", scoped["global_anchor_contexts.csv"]
            ),
        }
        scorer_data = {
            "episode_truth.csv": _scoped_csv(
                "episode_truth.csv", scoped["episode_truth.csv"]
            ),
            "activity_cliffs.csv": _scoped_csv(
                "activity_cliffs.csv", scoped["activity_cliffs.csv"]
            ),
        }
        cell_accounting = _zero_accounting()
        cell_accounting["direct_target_values_parsed"] = len(
            scoped["training_points.csv"]
        ) + len(scoped["training_pairs.csv"])
        cell_accounting["anchor_labels_exposed_to_models"] = sum(
            row["anchor_point_available"] == "true"
            for row in scoped["episode_anchor_contexts.csv"]
        )
        c3_accounting = _zero_accounting()
        c3_accounting["direct_target_values_parsed"] = len(scoped["training_pairs.csv"])
        scorer_accounting = _zero_accounting()
        scorer_accounting["query_truth_values_opened_by_scorers"] = sum(
            row["query_point_available"] == "true"
            for row in scoped["episode_truth.csv"]
        )
        root_specs = (
            (
                Path("cell-target") / label,
                cell_data,
                {
                    "molecules.csv",
                    "folds.csv",
                    "public_episode_queries.csv",
                    "transformation_pairs.csv",
                    "training_points.csv",
                    "training_pairs.csv",
                    "episode_anchor_contexts.csv",
                },
                cell_accounting,
            ),
            (
                Path("c3-target") / label,
                c3_data,
                {
                    "molecules.csv",
                    "folds.csv",
                    "public_episode_queries.csv",
                    "transformation_pairs.csv",
                    "training_pairs.csv",
                    "global_anchor_contexts.csv",
                },
                c3_accounting,
            ),
            (
                Path("sealed-scorer") / label,
                scorer_data,
                {
                    "molecules.csv",
                    "folds.csv",
                    "public_episode_queries.csv",
                    "episode_truth.csv",
                    "activity_cliffs.csv",
                },
                scorer_accounting,
            ),
        )
        for root, data, source_names, accounting in root_specs:
            payloads.update(
                _root_payloads(
                    root,
                    data,
                    _scope_object(cell_scope),
                    source_receipts,
                    source_names,
                    accounting,
                    process_accounting,
                    source_binding,
                )
            )
    return payloads


def _scoped_csv(name: str, rows: Sequence[Mapping[str, str]]) -> bytes:
    key_functions: dict[str, Callable[[Mapping[str, str]], tuple[str, ...]]] = {
        "training_points.csv": lambda row: (row["molecule_id"],),
        "training_pairs.csv": lambda row: (row["pair_id"], row["direction_id"]),
        "episode_anchor_contexts.csv": lambda row: (row["episode_id"],),
        "global_anchor_contexts.csv": lambda row: (row["episode_id"],),
        "episode_truth.csv": lambda row: (
            row["episode_id"],
            row["query_molecule_id"],
        ),
        "activity_cliffs.csv": lambda row: (
            row["episode_id"],
            row["query_molecule_id"],
        ),
    }
    payload: bytes = canonical_csv_bytes(
        output_columns(name), sorted(rows, key=key_functions[name])
    )
    return payload


def _root_payloads(
    root: Path,
    data: Mapping[str, bytes],
    cell_scope: str | Mapping[str, Any],
    source_receipts: Mapping[str, Mapping[str, Any]],
    source_names: set[str],
    operation_accounting: Mapping[str, int],
    projector_accounting: Mapping[str, int],
    source_binding: Mapping[str, Any],
) -> dict[Path, bytes]:
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "R5_ORACLE_SYNTHETIC_CAPABILITY_PROJECTION",
        "contract_sha256": CONTRACT_SHA256,
        "parent_contract_sha256": PARENT_CONTRACT_SHA256,
        "root": root.parts[0],
        "fixed_oof_system_id": G0_SYSTEM_ID,
        "current_cell_scope": cell_scope,
        "capability_root_accounting": dict(ROOT_ACCOUNTING),
        "accounting_scope": "values present in this capability root",
        "operation_accounting": dict(operation_accounting),
        "projector_operation_accounting": dict(projector_accounting),
        "output_receipts": _receipts_for(data),
        "source_receipts": {
            name: dict(source_receipts[name]) for name in sorted(source_names)
        },
        "source_bundle_binding": dict(source_binding),
        "authority": dict(DENIED_AUTHORITY),
        "forbidden_fields": (
            list(FORBIDDEN_PUBLIC_FIELDS) if root.parts[0] == "model-public" else []
        ),
    }
    return {
        **{root / name: value for name, value in data.items()},
        root / "manifest.json": canonical_json_bytes(manifest),
    }


def _receipts_for(data: Mapping[str, bytes]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, value in sorted(data.items()):
        receipt: dict[str, Any] = {
            "sha256": sha256(value).hexdigest(),
            "bytes": len(value),
        }
        if name.endswith(".csv"):
            receipt["rows"] = value.count(b"\n") - 1
            receipt["columns"] = list(output_columns(name))
        result[name] = receipt
    return result


def _process_accounting(
    rows: Mapping[str, Sequence[Mapping[str, str]]],
) -> dict[str, int]:
    result = _zero_accounting()
    result["direct_target_values_parsed"] = len(rows["training_points.csv"]) + len(
        rows["training_pairs.csv"]
    )
    result["anchor_labels_exposed_to_models"] = sum(
        row["anchor_point_available"] == "true"
        for row in rows["episode_anchor_contexts.csv"]
    )
    result["query_truth_values_opened_by_scorers"] = sum(
        row["query_point_available"] == "true" for row in rows["episode_truth.csv"]
    )
    return result


def _zero_accounting() -> dict[str, int]:
    return dict.fromkeys(ACCOUNTING_FIELDS, 0)


def _verify_stage(stage: Path, expected: Mapping[Path, bytes]) -> None:
    observed = {
        path.relative_to(stage): path.read_bytes()
        for path in stage.rglob("*")
        if path.is_file()
    }
    if observed != dict(expected):
        raise OpenADMETOracleProjectionError("staged output differs")
    expected_directories = {
        parent
        for relative in expected
        for parent in relative.parents
        if parent != Path(".")
    }
    observed_directories = {
        path.relative_to(stage) for path in stage.rglob("*") if path.is_dir()
    }
    if observed_directories != expected_directories:
        raise OpenADMETOracleProjectionError("staged directory set differs")
    for relative, data in observed.items():
        if relative.name == "manifest.json":
            parsed = strict_json_object(data, "staged manifest")
            if canonical_json_bytes(parsed) != data:
                raise OpenADMETOracleProjectionError("manifest is not canonical")
        elif relative.suffix == ".csv":
            csv_rows(data, output_columns(relative.name), str(relative))


def _scope_label(cell_scope: Scope) -> Path:
    stage, repeat, outer, inner = cell_scope
    path = Path(stage) / f"repeat-{repeat}" / f"outer-{outer}"
    return path if inner is None else path / f"inner-{inner}"


def _scope_object(cell_scope: Scope) -> dict[str, int | str]:
    stage, repeat, outer, inner = cell_scope
    return {
        "stage": stage,
        "repeat": repeat,
        "outer_fold": outer,
        "inner_fold": "" if inner is None else inner,
    }


def _require_digest(value: str, label: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise OpenADMETOracleProjectionError(f"{label} is not SHA-256")


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise OpenADMETOracleProjectionError(f"{label} is not an object")
    return value


def _is_nonnegative_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _string_value(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise OpenADMETOracleProjectionError(f"{label} is not text")
    return value


def _reject_symlink_ancestry(path: Path, label: str) -> None:
    if ".." in path.parts:
        raise OpenADMETOracleProjectionError(f"{label} contains path traversal")
    if any(candidate.is_symlink() for candidate in (path, *path.parents)):
        raise OpenADMETOracleProjectionError(f"{label} contains a symlink")


__all__ = [
    "ANCHOR_CONTEXT_COLUMNS",
    "CELL_FILES",
    "C3_FILES",
    "CLIFF_COLUMNS",
    "CONTRACT_SHA256",
    "GLOBAL_CONTEXT_COLUMNS",
    "OpenADMETOracleProjectionError",
    "OracleProjectionResult",
    "PUBLIC_FILES",
    "PUBLIC_QUERY_COLUMNS",
    "SCORER_FILES",
    "SOURCE_COLUMNS",
    "SOURCE_FILES",
    "TRAINING_PAIR_COLUMNS",
    "TRAINING_POINT_COLUMNS",
    "project_openadmet_oracle_inputs",
]

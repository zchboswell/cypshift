"""Build one receipt-bound, least-privilege R5C G0 episode view.

The adapter authenticates one model-public/cell-target capability pair, selects
one public episode, and publishes only the training points plus its one anchor
context.  It never reads a scorer root, derives labels, or writes an existing
output.  The resulting three-file root is consumed by the locked G0 runner.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Final

from cypshift.openadmet_oracle_cell_io import (
    OpenADMETOracleCellIOError,
    load_oracle_cell_capability,
)
from cypshift.openadmet_oracle_cell_validation import (
    OracleCellCapability,
    OracleCellTargetCapability,
    Scope,
)
from cypshift.openadmet_oracle_private_io import (
    OraclePrivateIOError,
    publish_readonly_tree,
    read_stable_file,
)
from cypshift.openadmet_oracle_projection import DENIED_AUTHORITY
from cypshift.openadmet_oracle_validation import (
    PUBLIC_QUERY_COLUMNS,
    TRAINING_POINT_COLUMNS,
)
from cypshift.openadmet_transformation_io import (
    canonical_csv_bytes,
    canonical_json_bytes,
)

CONTRACT_SHA256: Final = (
    "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
)
PARENT_CONTRACT_SHA256: Final = (
    "c1d7a66c4f479339b30c2006e4250381cb213d665d4902c71d4c4edbd347e8bf"
)
MODEL_ID: Final = "TRACE-G0-MAPL-FIXED"
ANCHOR_COLUMNS: Final = (
    "episode_id",
    "anchor_molecule_id",
    "anchor_point_available",
    "anchor_point",
)
EPISODE_FILES: Final = (
    "manifest.json",
    "training_points.csv",
    "episode_anchor_context.csv",
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
R3C_TERMINAL_MANIFEST_SHA256: Final = (
    "a2029e12231a22415900c55303ec5413b395aedc15d565ef7b4e650196b3277c"
)
PARAMETER_SHA256: Final = (
    "c56235a54a883a9a4488f1c8779f9013dae777af0f99cd92c9da1c4f51e61757"
)
PARAMETER_RECORD_SHA256: Final = (
    "0c912e0d06d0d24d58bdc0529d6b14d1706d6a933445885be881f95ba3678cb9"
)
ACCEPTED_PARAMETERS: Final = {
    "auto_class_weights": "None",
    "bayesian_matrix_reg": 0.10000000149011612,
    "best_model_min_trees": 1,
    "boost_from_average": True,
    "boosting_type": "Plain",
    "bootstrap_type": "MVS",
    "border_count": 254,
    "classes_count": 0,
    "depth": 6,
    "eval_fraction": 0,
    "eval_metric": "MAE",
    "feature_border_type": "GreedyLogSum",
    "force_unit_auto_pair_weights": False,
    "grow_policy": "SymmetricTree",
    "iterations": 1000,
    "l2_leaf_reg": 3,
    "leaf_estimation_backtracking": "AnyImprovement",
    "leaf_estimation_iterations": 1,
    "leaf_estimation_method": "Exact",
    "learning_rate": 0.029999999329447743,
    "loss_function": "MAE",
    "max_leaves": 64,
    "min_data_in_leaf": 1,
    "model_shrink_mode": "Constant",
    "model_shrink_rate": 0,
    "model_size_reg": 0.5,
    "nan_mode": "Min",
    "penalties_coefficient": 1,
    "pool_metainfo_options": {"tags": {}},
    "posterior_sampling": False,
    "random_score_type": "NormalWithModelSizeDecrease",
    "random_seed": 1,
    "random_strength": 2,
    "rsm": 1,
    "sampling_frequency": "PerTree",
    "score_function": "Cosine",
    "sparse_features_conflict_fraction": 0,
    "subsample": 0.800000011920929,
    "task_type": "CPU",
    "use_best_model": False,
}
R3C_PARAMETER_SOURCE: Final = {
    "r3c_terminal_manifest_sha256": R3C_TERMINAL_MANIFEST_SHA256,
    "parameter_record_sha256": PARAMETER_RECORD_SHA256,
    "parameter_record": {
        "canonical_get_all_params_json": ACCEPTED_PARAMETERS,
        "canonical_get_all_params_sha256": PARAMETER_SHA256,
        "system_id": MODEL_ID,
    },
}


class OracleG0ViewError(ValueError):
    """A requested episode view cannot satisfy the locked G0 contract."""


@dataclass(frozen=True, slots=True)
class G0EpisodeViewResult:
    """Receipt and identity of one atomically published episode view."""

    output_root: Path
    manifest_sha256: str
    episode_id: str
    model_public_manifest_sha256: str
    source_cell_target_manifest_sha256: str


def view_builder_source_sha256() -> str:
    """Return the exact source receipt bound into every published view."""

    try:
        return sha256(read_stable_file(Path(__file__).resolve())).hexdigest()
    except OraclePrivateIOError as exc:
        raise OracleG0ViewError(str(exc)) from exc


def build_g0_episode_view(
    *,
    model_public_root: Path,
    model_public_manifest_sha256: str,
    cell_target_root: Path,
    cell_target_manifest_sha256: str,
    scope: Scope,
    episode_id: str,
    output_root: Path,
) -> G0EpisodeViewResult:
    """Authenticate inputs and atomically publish exactly one episode view."""

    if (
        not isinstance(episode_id, str)
        or len(episode_id) != 64
        or any(char not in "0123456789abcdef" for char in episode_id)
    ):
        raise OracleG0ViewError("episode identity differs")
    capability = _load_capability(
        model_public_root,
        model_public_manifest_sha256,
        cell_target_root,
        cell_target_manifest_sha256,
        scope,
    )
    model = capability.model_public
    target = capability.target
    if not isinstance(target, OracleCellTargetCapability):
        raise OracleG0ViewError("G0 requires a measured cell target")
    public = tuple(model.queries_by_episode.get(episode_id, ()))
    if not public:
        raise OracleG0ViewError("episode is absent from authenticated public queries")
    public = tuple(
        sorted(public, key=lambda row: _int(row["query_rank"], "query rank"))
    )
    anchor_id, episode_outer = _validate_public(public, episode_id, scope)
    context = _select_anchor_context(
        target.episode_anchor_contexts, episode_id, anchor_id
    )
    points = _normalize_points(target.training_points)
    point_bytes = canonical_csv_bytes(TRAINING_POINT_COLUMNS, points)
    anchor_row = {name: context[name] for name in ANCHOR_COLUMNS}
    anchor_bytes = canonical_csv_bytes(ANCHOR_COLUMNS, (anchor_row,))
    source_sha = view_builder_source_sha256()
    scope_record = _scope_record(scope, episode_outer)
    manifest = _manifest(
        model.manifest,
        model.manifest_sha256,
        target.manifest_sha256,
        source_sha,
        scope_record,
        episode_id,
        anchor_id,
        public,
        point_bytes,
        anchor_bytes,
        context["anchor_point_available"] == "true",
    )
    payloads = {
        "training_points.csv": point_bytes,
        "episode_anchor_context.csv": anchor_bytes,
        "manifest.json": canonical_json_bytes(manifest),
    }
    published = _publish(output_root, payloads)
    return G0EpisodeViewResult(
        published,
        sha256(payloads["manifest.json"]).hexdigest(),
        episode_id,
        model.manifest_sha256,
        target.manifest_sha256,
    )


def _load_capability(
    model_root: Path,
    model_sha: str,
    target_root: Path,
    target_sha: str,
    scope: Scope,
) -> OracleCellCapability:
    try:
        return load_oracle_cell_capability(
            model_root,
            target_root,
            expected_model_manifest_sha256=model_sha,
            expected_target_manifest_sha256=target_sha,
            system_id="G0",
            target_kind="cell-target",
            expected_scope=scope,
        )
    except OpenADMETOracleCellIOError as exc:
        raise OracleG0ViewError(str(exc)) from exc


def _validate_public(
    rows: Sequence[Mapping[str, str]], episode_id: str, scope: Scope
) -> tuple[str, int]:
    stage, repeat, outer, _inner = scope
    if len({row["anchor_molecule_id"] for row in rows}) != 1:
        raise OracleG0ViewError("episode anchor identity differs")
    anchor = rows[0]["anchor_molecule_id"]
    episode_outer_values = {
        _int(row["outer_fold"], "episode outer fold") for row in rows
    }
    if len(episode_outer_values) != 1:
        raise OracleG0ViewError("episode outer fold differs")
    episode_outer = next(iter(episode_outer_values))
    expected_ranks = list(range(1, len(rows) + 1))
    if [_int(row["query_rank"], "query rank") for row in rows] != expected_ranks:
        raise OracleG0ViewError("episode query ranks differ")
    for row in rows:
        if (
            row["episode_id"] != episode_id
            or _int(row["repeat"], "episode repeat") != repeat
            or _int(row["outer_fold"], "episode outer fold") != episode_outer
            or row["anchor_molecule_id"] == row["query_molecule_id"]
            or not row["outer_group_id"]
        ):
            raise OracleG0ViewError("episode public scope differs")
    if stage == "outer" and episode_outer != outer:
        raise OracleG0ViewError("outer episode scope differs")
    if stage == "inner" and episode_outer == outer:
        raise OracleG0ViewError("inner episode scope differs")
    return anchor, episode_outer


def _select_anchor_context(
    rows: Sequence[Mapping[str, str]], episode_id: str, anchor_id: str
) -> Mapping[str, str]:
    matches = [row for row in rows if row["episode_id"] == episode_id]
    if len(matches) != 1:
        raise OracleG0ViewError("episode anchor context cardinality differs")
    context = matches[0]
    if context["anchor_molecule_id"] != anchor_id:
        raise OracleG0ViewError("episode anchor context differs")
    if context["anchor_point_available"] not in {"true", "false"}:
        raise OracleG0ViewError("anchor capability token differs")
    return context


def _normalize_points(
    rows: Sequence[Mapping[str, str]],
) -> tuple[Mapping[str, str], ...]:
    normalized: list[Mapping[str, str]] = []
    for row in sorted(rows, key=lambda item: item["molecule_id"]):
        if row["sample_weight"] not in {"1", "1.0", "1.00"}:
            raise OracleG0ViewError("G0 training point weight differs")
        normalized.append({**row, "sample_weight": "1.0"})
    return tuple(normalized)


def _scope_record(scope: Scope, episode_outer: int) -> dict[str, int | str]:
    stage, repeat, outer, inner = scope
    return {
        "stage": stage,
        "repeat": repeat,
        "current_outer_validation_fold": outer,
        "inner_fold": "" if inner is None else inner,
        "episode_outer_fold": episode_outer,
    }


def _manifest(
    model: Mapping[str, Any],
    model_sha: str,
    target_sha: str,
    source_sha: str,
    scope: Mapping[str, int | str],
    episode_id: str,
    anchor_id: str,
    public: Sequence[Mapping[str, str]],
    point_bytes: bytes,
    anchor_bytes: bytes,
    anchor_available: bool,
) -> dict[str, Any]:
    query_bytes = canonical_csv_bytes(PUBLIC_QUERY_COLUMNS, public)
    accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    accounting["direct_target_values_parsed"] = (
        point_bytes.count(b"\n") - 1 + int(anchor_available)
    )
    accounting["anchor_labels_exposed_to_models"] = int(anchor_available)
    return {
        "schema_version": "cypshift.openadmet_cyp_2026.r5c_g0_episode_view.v1",
        "status": "R5_ORACLE_EPISODE_TARGET_VIEW",
        "contract_sha256": CONTRACT_SHA256,
        "parent_contract_sha256": PARENT_CONTRACT_SHA256,
        "root": "episode-target",
        "view_builder_source_sha256": source_sha,
        "model_public_manifest_sha256": model_sha,
        "source_cell_target_manifest_sha256": target_sha,
        "source_bundle_binding": _plain(model["source_bundle_binding"]),
        "scope": dict(scope),
        "episode": {
            "episode_id": episode_id,
            "anchor_molecule_id": anchor_id,
            "query_rows": len(public),
            "query_rows_sha256": sha256(query_bytes).hexdigest(),
        },
        "r3c_parameter_source": _plain(R3C_PARAMETER_SOURCE),
        "output_receipts": {
            "episode_anchor_context.csv": _receipt(anchor_bytes, ANCHOR_COLUMNS),
            "training_points.csv": _receipt(point_bytes, TRAINING_POINT_COLUMNS),
        },
        "operation_accounting": accounting,
        "authority": dict(DENIED_AUTHORITY),
    }


def _receipt(data: bytes, columns: Sequence[str]) -> dict[str, Any]:
    return {
        "sha256": sha256(data).hexdigest(),
        "bytes": len(data),
        "rows": data.count(b"\n") - 1,
        "columns": list(columns),
    }


def _int(value: str, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise OracleG0ViewError(f"{label} differs") from exc
    if str(parsed) != value:
        raise OracleG0ViewError(f"{label} is noncanonical")
    return parsed


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _publish(output_root: Path, payloads: Mapping[str, bytes]) -> Path:
    try:
        publish_readonly_tree(output_root, payloads)
    except OraclePrivateIOError as exc:
        message = str(exc)
        if "already exists" in message:
            message = f"output overwrite rejected: {message}"
        raise OracleG0ViewError(message) from exc
    return output_root


__all__ = [
    "EPISODE_FILES",
    "G0EpisodeViewResult",
    "OracleG0ViewError",
    "build_g0_episode_view",
    "view_builder_source_sha256",
]

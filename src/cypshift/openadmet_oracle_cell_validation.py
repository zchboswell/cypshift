"""Scientific validation and immutable types for isolated R5C model cells.

This module operates only on bytes already authenticated by the descriptor-
based security layer. It reuses the accepted R5B chemistry, fold, geometry,
target, and OOF predicates rather than maintaining a second scientific grammar.
"""

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, TypeAlias, cast

from cypshift import openadmet_oracle_validation as accepted
from cypshift.openadmet_oracle_geometry_validation import (
    OracleGeometryValidationError,
    validate_geometry,
)
from cypshift.openadmet_oracle_validation import (
    ANCHOR_CONTEXT_COLUMNS,
    FEATURE_FILES,
    GLOBAL_CONTEXT_COLUMNS,
    INNER_OOF_INPUT,
    OUTER_OOF_INPUT,
    PUBLIC_QUERY_COLUMNS,
    TRAINING_PAIR_COLUMNS,
    TRAINING_POINT_COLUMNS,
)
from cypshift.openadmet_transformation_compiler import PAIR_COLUMNS
from cypshift.openadmet_transformation_io import (
    STRUCTURE_COLUMNS,
    canonical_csv_bytes,
)
from cypshift.openadmet_transformation_projection import FOLD_PROJECTION_COLUMNS
from cypshift.openadmet_transformation_serialization import EPISODE_COLUMNS

FrozenRow: TypeAlias = Mapping[str, str]
Scope: TypeAlias = tuple[Literal["outer", "inner"], int, int, int | None]


class OpenADMETOracleCellValidationError(ValueError):
    """Authenticated model-cell bytes violate the frozen scientific contract."""


@dataclass(frozen=True, slots=True)
class AuthenticatedRoot:
    """One descriptor-loaded capability root after manifest authentication."""

    kind: str
    manifest: Mapping[str, Any]
    manifest_sha256: str
    files: Mapping[str, bytes]


@dataclass(frozen=True, slots=True)
class OracleModelPublicCapability:
    """Immutable structural, fold, episode, geometry, and feature capability."""

    manifest: Mapping[str, Any]
    manifest_sha256: str
    molecules: tuple[FrozenRow, ...]
    molecule_index: Mapping[str, int]
    folds: tuple[FrozenRow, ...]
    fold_index: Mapping[tuple[str, int, int], FrozenRow]
    public_queries: tuple[FrozenRow, ...]
    queries_by_episode: Mapping[str, tuple[FrozenRow, ...]]
    transformation_pairs: tuple[FrozenRow, ...]
    pair_index: Mapping[str, FrozenRow]
    episode_transformations: tuple[FrozenRow, ...]
    episode_index: Mapping[tuple[str, int], FrozenRow]
    features: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class OracleCellTargetCapability:
    """Measured-anchor target view for one exact cell scope."""

    manifest: Mapping[str, Any]
    manifest_sha256: str
    scope: Scope
    training_points: tuple[FrozenRow, ...]
    training_pairs: tuple[FrozenRow, ...]
    episode_anchor_contexts: tuple[FrozenRow, ...]

    @property
    def kind(self) -> Literal["cell-target"]:
        return "cell-target"


@dataclass(frozen=True, slots=True)
class OracleC3TargetCapability:
    """Pure-OOF C3 view; measured point capability is absent by construction."""

    manifest: Mapping[str, Any]
    manifest_sha256: str
    scope: Scope
    training_pairs: tuple[FrozenRow, ...]
    global_anchor_contexts: tuple[FrozenRow, ...]

    @property
    def kind(self) -> Literal["c3-target"]:
        return "c3-target"


OracleTargetCapability: TypeAlias = (
    OracleCellTargetCapability | OracleC3TargetCapability
)


@dataclass(frozen=True, slots=True)
class OracleCellCapability:
    """One system-bound model-public and target capability pair."""

    system_id: str
    model_public: OracleModelPublicCapability
    target: OracleTargetCapability


def validate_cell_capabilities(
    model_root: AuthenticatedRoot,
    target_root: AuthenticatedRoot,
    *,
    system_id: str,
    scope: Scope,
) -> OracleCellCapability:
    """Apply the accepted scientific predicates to authenticated root bytes."""

    model = _validate_model_public(model_root)
    target = _validate_target(target_root, model, scope)
    _validate_accounting(model_root, target_root, target)
    return OracleCellCapability(system_id, model, target)


def _validate_model_public(root: AuthenticatedRoot) -> OracleModelPublicCapability:
    rows = {
        "molecules.csv": _csv(root, "molecules.csv", STRUCTURE_COLUMNS),
        "folds.csv": _csv(root, "folds.csv", FOLD_PROJECTION_COLUMNS),
        "public_episode_queries.csv": _csv(
            root, "public_episode_queries.csv", PUBLIC_QUERY_COLUMNS
        ),
        "transformation_pairs.csv": _csv(
            root, "transformation_pairs.csv", PAIR_COLUMNS
        ),
        "episode_transformations.csv": _csv(
            root, "episode_transformations.csv", EPISODE_COLUMNS
        ),
    }
    try:
        molecules_by_id = accepted._validate_molecules(  # noqa: SLF001
            rows["molecules.csv"]
        )
        accepted._validate_arrays(  # noqa: SLF001
            root.files, tuple(molecules_by_id)
        )
        folds_by_key = accepted._validate_folds(  # noqa: SLF001
            rows["folds.csv"], molecules_by_id
        )
        public = accepted._validate_public(  # noqa: SLF001
            rows["public_episode_queries.csv"], molecules_by_id, folds_by_key
        )
        geometry = validate_geometry(rows, molecules_by_id, public)
    except (
        accepted.OpenADMETOracleProjectionError,
        OracleGeometryValidationError,
    ) as exc:
        raise OpenADMETOracleCellValidationError(str(exc)) from exc
    features = _feature_arrays(root.files)
    molecules = rows["molecules.csv"]
    molecule_index = MappingProxyType(
        {row["molecule_id"]: index for index, row in enumerate(molecules)}
    )
    queries_by_episode: dict[str, list[FrozenRow]] = {}
    for row in rows["public_episode_queries.csv"]:
        queries_by_episode.setdefault(row["episode_id"], []).append(row)
    episode_index = MappingProxyType(
        {
            (row["episode_id"], int(row["query_rank"])): row
            for row in rows["episode_transformations.csv"]
        }
    )
    return OracleModelPublicCapability(
        root.manifest,
        root.manifest_sha256,
        molecules,
        molecule_index,
        rows["folds.csv"],
        MappingProxyType(dict(folds_by_key)),
        rows["public_episode_queries.csv"],
        MappingProxyType(
            {key: tuple(value) for key, value in queries_by_episode.items()}
        ),
        rows["transformation_pairs.csv"],
        MappingProxyType(dict(geometry)),
        rows["episode_transformations.csv"],
        episode_index,
        features,
    )


def _validate_target(
    root: AuthenticatedRoot,
    model: OracleModelPublicCapability,
    scope: Scope,
) -> OracleTargetCapability:
    pairs = _csv(root, "training_pairs.csv", TRAINING_PAIR_COLUMNS)
    points: tuple[FrozenRow, ...] = ()
    if root.kind == "cell-target":
        points = _csv(root, "training_points.csv", TRAINING_POINT_COLUMNS)
        contexts = _csv(root, "episode_anchor_contexts.csv", ANCHOR_CONTEXT_COLUMNS)
        measured = True
    else:
        contexts = _csv(root, "global_anchor_contexts.csv", GLOBAL_CONTEXT_COLUMNS)
        measured = False
    scoped_pairs = _with_scope(pairs, scope)
    scoped_points = _with_scope(points, scope)
    scoped_contexts = _with_scope(contexts, scope)
    molecules = {row["molecule_id"]: row for row in model.molecules}
    public = {
        (row["episode_id"], row["query_molecule_id"]): row
        for row in model.public_queries
    }
    oof_receipts = _oof_receipts(model.manifest)
    try:
        accepted._validate_training_points(  # noqa: SLF001
            scoped_points, molecules, model.fold_index
        )
        accepted._validate_training_pairs(  # noqa: SLF001
            scoped_pairs, molecules, model.fold_index, model.pair_index
        )
        context_index = accepted._validate_context_rows(  # noqa: SLF001
            scoped_contexts,
            public,
            model.fold_index,
            molecules,
            oof_receipts,
            measured=measured,
        )
    except accepted.OpenADMETOracleProjectionError as exc:
        raise OpenADMETOracleCellValidationError(str(exc)) from exc
    expected = _expected_contexts(scope, public, model.fold_index, molecules)
    actual = {episode for cell, episode in context_index if cell == scope}
    if actual != expected or len(context_index) != len(expected):
        raise OpenADMETOracleCellValidationError("cell context superset differs")
    if root.kind == "cell-target":
        return OracleCellTargetCapability(
            root.manifest,
            root.manifest_sha256,
            scope,
            points,
            pairs,
            contexts,
        )
    return OracleC3TargetCapability(
        root.manifest, root.manifest_sha256, scope, pairs, contexts
    )


def _expected_contexts(
    scope: Scope,
    public: Mapping[tuple[str, str], Mapping[str, str]],
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
    molecules: Mapping[str, Mapping[str, str]],
) -> set[str]:
    episodes: dict[str, Mapping[str, str]] = {}
    for (episode, _query), row in public.items():
        episodes.setdefault(episode, row)
    try:
        return {
            episode
            for episode, row in episodes.items()
            if accepted._scope_matches_episode(  # noqa: SLF001
                scope, row, folds, molecules
            )
        }
    except accepted.OpenADMETOracleProjectionError as exc:
        raise OpenADMETOracleCellValidationError(str(exc)) from exc


def _oof_receipts(manifest: Mapping[str, Any]) -> dict[str, str]:
    binding = cast(Mapping[str, Any], manifest["source_bundle_binding"])
    parents = cast(Mapping[str, str], binding["parent_receipts"])
    return {
        OUTER_OOF_INPUT: parents[OUTER_OOF_INPUT],
        INNER_OOF_INPUT: parents[INNER_OOF_INPUT],
    }


def _validate_accounting(
    model_root: AuthenticatedRoot,
    target_root: AuthenticatedRoot,
    target: OracleTargetCapability,
) -> None:
    model_accounting = cast(
        Mapping[str, int], model_root.manifest["operation_accounting"]
    )
    if any(model_accounting.values()):
        raise OpenADMETOracleCellValidationError("model-public accounting is nonzero")
    expected = dict.fromkeys(model_accounting, 0)
    expected["direct_target_values_parsed"] = len(target.training_pairs)
    if isinstance(target, OracleCellTargetCapability):
        expected["direct_target_values_parsed"] += len(target.training_points)
        expected["anchor_labels_exposed_to_models"] = sum(
            row["anchor_point_available"] == "true"
            for row in target.episode_anchor_contexts
        )
    if target_root.manifest["operation_accounting"] != expected:
        raise OpenADMETOracleCellValidationError("target operation accounting differs")


def _csv(
    root: AuthenticatedRoot, name: str, columns: Sequence[str]
) -> tuple[FrozenRow, ...]:
    try:
        rows = accepted.csv_rows(root.files[name], columns, name)
    except accepted.OpenADMETOracleProjectionError as exc:
        raise OpenADMETOracleCellValidationError(str(exc)) from exc
    if canonical_csv_bytes(columns, rows) != root.files[name]:
        raise OpenADMETOracleCellValidationError(f"{name} is not canonical")
    return tuple(MappingProxyType(dict(row)) for row in rows)


def _with_scope(rows: Sequence[FrozenRow], scope: Scope) -> list[dict[str, str]]:
    stage, repeat, outer, inner = scope
    prefix = {
        "stage": stage,
        "repeat": str(repeat),
        "outer_fold": str(outer),
        "inner_fold": "" if inner is None else str(inner),
    }
    return [{**prefix, **row} for row in rows]


def _feature_arrays(files: Mapping[str, bytes]) -> Mapping[str, Any]:
    from importlib import import_module

    np: Any = import_module("numpy")
    arrays: dict[str, Any] = {}
    for name in FEATURE_FILES:
        stream = io.BytesIO(files[name])
        loaded = np.load(stream, allow_pickle=False)
        array = np.frombuffer(loaded.tobytes(order="C"), dtype=loaded.dtype).reshape(
            loaded.shape
        )
        arrays[name] = array
    return MappingProxyType(arrays)


__all__ = [
    "AuthenticatedRoot",
    "OpenADMETOracleCellValidationError",
    "OracleC3TargetCapability",
    "OracleCellCapability",
    "OracleCellTargetCapability",
    "OracleModelPublicCapability",
    "Scope",
    "validate_cell_capabilities",
]

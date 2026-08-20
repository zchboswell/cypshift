"""Strict synthetic source validation for the R5 TRACE capability splitter.

This module validates a prebuilt synthetic bundle.  It does not compile trusted
R2/R3/R4 artifacts; that source compiler remains a separate milestone.
"""

from __future__ import annotations

import csv
import io
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from hashlib import sha256
from importlib import import_module
from typing import Final

from cypshift.openadmet_oracle_geometry_validation import (
    OracleGeometryValidationError,
    validate_geometry,
)
from cypshift.openadmet_transformation_compiler import PAIR_COLUMNS
from cypshift.openadmet_transformation_io import STRUCTURE_COLUMNS
from cypshift.openadmet_transformation_projection import FOLD_PROJECTION_COLUMNS
from cypshift.openadmet_transformation_serialization import EPISODE_COLUMNS
from cypshift.openadmet_transformation_support import VALID_STATUSES

PUBLIC_QUERY_COLUMNS: Final = (
    "episode_id",
    "episode_policy_id",
    "repeat",
    "outer_fold",
    "outer_group_id",
    "anchor_molecule_id",
    "query_molecule_id",
    "query_rank",
)
TRAINING_POINT_COLUMNS: Final = (
    "molecule_id",
    "component_id",
    "point",
    "sample_weight",
)
TRAINING_PAIR_COLUMNS: Final = (
    "pair_id",
    "direction_id",
    "anchor_molecule_id",
    "analog_molecule_id",
    "component_id",
    "delta",
    "sample_weight",
)
ANCHOR_CONTEXT_COLUMNS: Final = (
    "episode_id",
    "anchor_molecule_id",
    "anchor_point",
    "anchor_point_available",
    "anchor_global_oof_prediction",
    "anchor_global_oof_source_scope",
    "anchor_global_oof_model_id",
    "anchor_global_oof_receipt_sha256",
)
GLOBAL_CONTEXT_COLUMNS: Final = (
    "episode_id",
    "anchor_molecule_id",
    "anchor_global_oof_prediction",
    "anchor_global_oof_source_scope",
    "anchor_global_oof_model_id",
    "anchor_global_oof_receipt_sha256",
)
TRUTH_COLUMNS: Final = (
    "episode_id",
    "query_molecule_id",
    "selector_cyp_truth",
    "query_point",
    "query_point_available",
)
CLIFF_COLUMNS: Final = ("episode_id", "query_molecule_id", "activity_cliff")
SCOPE_COLUMNS: Final = ("stage", "repeat", "outer_fold", "inner_fold")

FEATURE_FILES: Final = (
    "maplight_morgan_count.npy",
    "maplight_avalon_count.npy",
    "maplight_erg.npy",
    "maplight_rdkit_descriptors.npy",
    "morgan_binary.npy",
)
FEATURE_SPECS: Final = {
    "maplight_morgan_count.npy": (1024, "int8"),
    "maplight_avalon_count.npy": (1024, "int8"),
    "maplight_erg.npy": (315, "<f8"),
    "maplight_rdkit_descriptors.npy": (200, "<f8"),
    "morgan_binary.npy": (4096, "uint8"),
}
SOURCE_COLUMNS: Final = {
    "molecules.csv": STRUCTURE_COLUMNS,
    "folds.csv": FOLD_PROJECTION_COLUMNS,
    "public_episode_queries.csv": PUBLIC_QUERY_COLUMNS,
    "transformation_pairs.csv": PAIR_COLUMNS,
    "episode_transformations.csv": EPISODE_COLUMNS,
    "training_points.csv": SCOPE_COLUMNS + TRAINING_POINT_COLUMNS,
    "training_pairs.csv": SCOPE_COLUMNS + TRAINING_PAIR_COLUMNS,
    "episode_anchor_contexts.csv": SCOPE_COLUMNS + ANCHOR_CONTEXT_COLUMNS,
    "global_anchor_contexts.csv": SCOPE_COLUMNS + GLOBAL_CONTEXT_COLUMNS,
    "episode_truth.csv": SCOPE_COLUMNS + TRUTH_COLUMNS,
    "activity_cliffs.csv": SCOPE_COLUMNS + CLIFF_COLUMNS,
}

SEEDS: Final = (20260810, 20260811, 20260812)
G0_SYSTEM_ID: Final = "TRACE-G0-MAPL-FIXED"
OUTER_OOF_SCOPE: Final = "openadmet-direct-outer-v1"
INNER_OOF_SCOPE: Final = "openadmet-direct-inner-v1|outer={outer}"
OUTER_OOF_INPUT: Final = "global_oof_predictions.csv"
INNER_OOF_INPUT: Final = "global_inner_oof_predictions.csv"

Scope = tuple[str, int, int, int | None]
PublicKey = tuple[str, str]


class OpenADMETOracleProjectionError(ValueError):
    """A receipt, schema, membership, or capability invariant failed."""


@dataclass(frozen=True, slots=True)
class ValidatedOracleSources:
    """Receipt-checked rows after all synthetic splitter invariants pass."""

    rows: dict[str, list[dict[str, str]]]
    molecules: dict[str, Mapping[str, str]]
    folds: dict[tuple[str, int, int], Mapping[str, str]]
    public: dict[PublicKey, Mapping[str, str]]
    pairs: dict[str, Mapping[str, str]]
    scopes: tuple[Scope, ...]


def validate_oracle_sources(
    loaded: Mapping[str, bytes], *, oof_receipts: Mapping[str, str]
) -> ValidatedOracleSources:
    """Parse and validate an already receipt-matched synthetic source bundle."""

    rows = {
        name: csv_rows(loaded[name], columns, name)
        for name, columns in SOURCE_COLUMNS.items()
    }
    molecules = _validate_molecules(rows["molecules.csv"])
    _validate_arrays(loaded, tuple(molecules))
    folds = _validate_folds(rows["folds.csv"], molecules)
    public = _validate_public(rows["public_episode_queries.csv"], molecules, folds)
    try:
        pairs = validate_geometry(rows, molecules, public)
    except OracleGeometryValidationError as exc:
        raise OpenADMETOracleProjectionError(str(exc)) from exc
    cell_scopes = scopes()
    if set(oof_receipts) != {OUTER_OOF_INPUT, INNER_OOF_INPUT}:
        raise OpenADMETOracleProjectionError("OOF parent receipt set differs")
    for name, value in oof_receipts.items():
        digest(value, f"OOF parent receipt: {name}")
    _validate_targets(rows, molecules, folds, public, pairs, cell_scopes, oof_receipts)
    return ValidatedOracleSources(rows, molecules, folds, public, pairs, cell_scopes)


def csv_rows(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    """Parse exact UTF-8 RFC4180 bytes with a fixed header."""

    if b"\r" in data or not data.endswith(b"\n"):
        raise OpenADMETOracleProjectionError(f"{label} line endings differ")
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True)
        if next(reader, None) != list(columns):
            raise OpenADMETOracleProjectionError(f"{label} header differs")
        rows: list[dict[str, str]] = []
        for values in reader:
            if len(values) != len(columns):
                raise OpenADMETOracleProjectionError(f"{label} field count differs")
            rows.append(dict(zip(columns, values, strict=True)))
        return rows
    except (UnicodeError, csv.Error) as exc:
        raise OpenADMETOracleProjectionError(f"cannot parse {label}") from exc


def scopes() -> tuple[Scope, ...]:
    """Return the exact 15 outer and 60 nested inner cell scopes."""

    outer: list[Scope] = [
        ("outer", repeat, fold, None) for repeat in range(3) for fold in range(5)
    ]
    inner: list[Scope] = [
        ("inner", repeat, fold, inner_fold)
        for repeat in range(3)
        for fold in range(5)
        for inner_fold in range(4)
    ]
    return tuple(outer + inner)


def scope(row: Mapping[str, str]) -> Scope:
    """Parse one canonical source-cell scope."""

    stage = row["stage"]
    if stage not in {"outer", "inner"}:
        raise OpenADMETOracleProjectionError("stage differs")
    repeat = canonical_int(row["repeat"], "repeat")
    outer = canonical_int(row["outer_fold"], "outer fold")
    if stage == "outer":
        if row["inner_fold"] != "":
            raise OpenADMETOracleProjectionError("outer scope contains inner fold")
        inner: int | None = None
    else:
        inner = canonical_int(row["inner_fold"], "inner fold")
    if repeat not in range(3) or outer not in range(5):
        raise OpenADMETOracleProjectionError("scope differs")
    if inner is not None and inner not in range(4):
        raise OpenADMETOracleProjectionError("scope differs")
    return stage, repeat, outer, inner


def output_columns(name: str) -> tuple[str, ...]:
    """Return one exact published CSV schema."""

    schemas = {
        "molecules.csv": STRUCTURE_COLUMNS,
        "folds.csv": FOLD_PROJECTION_COLUMNS,
        "public_episode_queries.csv": PUBLIC_QUERY_COLUMNS,
        "transformation_pairs.csv": PAIR_COLUMNS,
        "episode_transformations.csv": EPISODE_COLUMNS,
        "training_points.csv": TRAINING_POINT_COLUMNS,
        "training_pairs.csv": TRAINING_PAIR_COLUMNS,
        "episode_anchor_contexts.csv": ANCHOR_CONTEXT_COLUMNS,
        "global_anchor_contexts.csv": GLOBAL_CONTEXT_COLUMNS,
        "episode_truth.csv": TRUTH_COLUMNS,
        "activity_cliffs.csv": CLIFF_COLUMNS,
    }
    schema: tuple[str, ...] = schemas[name]
    return schema


def canonical_int(value: str, label: str) -> int:
    """Parse an unsigned canonical decimal integer."""

    try:
        if not value or str(int(value)) != value:
            raise ValueError
        result = int(value)
    except ValueError as exc:
        raise OpenADMETOracleProjectionError(
            f"{label} is not canonical integer"
        ) from exc
    if result < 0:
        raise OpenADMETOracleProjectionError(f"{label} is negative")
    return result


def finite(value: str, label: str) -> float:
    """Parse one finite numeric field."""

    try:
        result = float(value)
    except ValueError as exc:
        raise OpenADMETOracleProjectionError(f"{label} is not finite") from exc
    if value == "" or not math.isfinite(result):
        raise OpenADMETOracleProjectionError(f"{label} is not finite")
    return result


def digest(value: str, label: str) -> None:
    """Require lowercase SHA-256 text."""

    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise OpenADMETOracleProjectionError(f"{label} is not SHA-256")


def _validate_molecules(
    rows: Sequence[Mapping[str, str]],
) -> dict[str, Mapping[str, str]]:
    if not rows:
        raise OpenADMETOracleProjectionError("molecules are empty")
    identifiers = [row["molecule_id"] for row in rows]
    if identifiers != sorted(identifiers) or len(set(identifiers)) != len(rows):
        raise OpenADMETOracleProjectionError(
            "molecules are not unique canonical feature-row order"
        )
    result: dict[str, Mapping[str, str]] = {}
    structure_components: dict[str, str] = {}
    for row in rows:
        molecule = row["molecule_id"]
        if not molecule:
            raise OpenADMETOracleProjectionError("empty molecule identity")
        for text_key, hash_key in (
            ("raw_smiles", "raw_structure_sha256"),
            ("standardized_smiles", "standardized_structure_hash"),
        ):
            expected = _sha(row[text_key].encode())
            if expected != row[hash_key]:
                raise OpenADMETOracleProjectionError("structure receipt differs")
        standardized_hash = row["standardized_structure_hash"]
        component = row["similarity_component_hash"]
        digest(component, "component")
        if (
            standardized_hash in structure_components
            and structure_components[standardized_hash] != component
        ):
            raise OpenADMETOracleProjectionError(
                "exact duplicate structure crosses a component"
            )
        structure_components[standardized_hash] = component
        result[molecule] = row
    return result


def _validate_arrays(
    loaded: Mapping[str, bytes], molecule_order: tuple[str, ...]
) -> None:
    numpy = import_module("numpy")
    row_count = len(molecule_order)
    for name in FEATURE_FILES:
        stream = io.BytesIO(loaded[name])
        try:
            version = numpy.lib.format.read_magic(stream)
            stream.seek(0)
            array = numpy.load(stream, allow_pickle=False)
        except (OSError, ValueError) as exc:
            raise OpenADMETOracleProjectionError(f"invalid NPY array: {name}") from exc
        width, dtype = FEATURE_SPECS[name]
        if stream.read() != b"":
            raise OpenADMETOracleProjectionError(f"trailing NPY bytes: {name}")
        if (
            version != (1, 0)
            or array.shape != (row_count, width)
            or array.dtype != numpy.dtype(dtype)
        ):
            raise OpenADMETOracleProjectionError(f"feature shape/dtype differs: {name}")
        if not array.flags.c_contiguous:
            raise OpenADMETOracleProjectionError(f"feature is not C-contiguous: {name}")
        if name != "maplight_rdkit_descriptors.npy" and not bool(
            numpy.isfinite(array).all()
        ):
            raise OpenADMETOracleProjectionError(f"feature is nonfinite: {name}")
        if name == "maplight_rdkit_descriptors.npy":
            if bool(numpy.isinf(array).any()):
                raise OpenADMETOracleProjectionError("descriptor contains infinity")
            allowed = numpy.zeros(width, dtype=bool)
            allowed[[39, 41, 43, 45]] = True
            if bool(numpy.isnan(array[:, ~allowed]).any()):
                raise OpenADMETOracleProjectionError("descriptor NaN mask differs")
        if name == "morgan_binary.npy" and not bool(
            numpy.logical_or(array == 0, array == 1).all()
        ):
            raise OpenADMETOracleProjectionError("Morgan feature is not binary")


def _validate_folds(
    rows: Sequence[Mapping[str, str]],
    molecules: Mapping[str, Mapping[str, str]],
) -> dict[tuple[str, int, int], Mapping[str, str]]:
    expected_keys = {
        (molecule, repeat, validation)
        for molecule in molecules
        for repeat in range(3)
        for validation in range(5)
    }
    if len(rows) != len(expected_keys):
        raise OpenADMETOracleProjectionError("fold cardinality differs")
    result: dict[tuple[str, int, int], Mapping[str, str]] = {}
    outer_by_component: dict[tuple[str, int], int] = {}
    inner_by_component: dict[tuple[str, int, int], str] = {}
    for row in rows:
        molecule = row["molecule_id"]
        if molecule not in molecules:
            raise OpenADMETOracleProjectionError("fold contains unknown molecule")
        component = molecules[molecule]["similarity_component_hash"]
        if row["similarity_component_hash"] != component:
            raise OpenADMETOracleProjectionError("fold molecule/component mismatch")
        repeat = canonical_int(row["repeat"], "repeat")
        seed = canonical_int(row["seed"], "seed")
        outer = canonical_int(row["outer_fold"], "outer fold")
        validation = canonical_int(row["outer_validation_fold"], "validation fold")
        if (
            repeat not in range(3)
            or seed != SEEDS[repeat]
            or outer not in range(5)
            or validation not in range(5)
        ):
            raise OpenADMETOracleProjectionError("fold value differs")
        key = molecule, repeat, validation
        if key in result:
            raise OpenADMETOracleProjectionError("duplicate fold row")
        inner = row["inner_fold"]
        if (outer == validation) != (inner == ""):
            raise OpenADMETOracleProjectionError("inner-fold holdout mismatch")
        if inner and canonical_int(inner, "inner fold") not in range(4):
            raise OpenADMETOracleProjectionError("inner fold differs")
        outer_key = component, repeat
        if outer_key in outer_by_component and outer_by_component[outer_key] != outer:
            raise OpenADMETOracleProjectionError("component crosses outer fold")
        outer_by_component[outer_key] = outer
        inner_key = component, repeat, validation
        if inner_key in inner_by_component and inner_by_component[inner_key] != inner:
            raise OpenADMETOracleProjectionError("component crosses inner fold")
        inner_by_component[inner_key] = inner
        result[key] = row
    if set(result) != expected_keys:
        raise OpenADMETOracleProjectionError("fold identity coverage differs")
    return result


def _validate_public(
    rows: Sequence[Mapping[str, str]],
    molecules: Mapping[str, Mapping[str, str]],
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
) -> dict[PublicKey, Mapping[str, str]]:
    result: dict[PublicKey, Mapping[str, str]] = {}
    episodes: dict[str, Mapping[str, str]] = {}
    ranks: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        if row["episode_policy_id"] not in {
            "selected_anchor",
            "deterministic_random_anchor_stress",
        }:
            raise OpenADMETOracleProjectionError("episode policy differs")
        episode = row["episode_id"]
        anchor = row["anchor_molecule_id"]
        query = row["query_molecule_id"]
        key = episode, query
        if (
            not episode
            or key in result
            or anchor not in molecules
            or query not in molecules
            or anchor == query
        ):
            raise OpenADMETOracleProjectionError("public episode identity differs")
        digest(episode, "episode ID")
        repeat = canonical_int(row["repeat"], "episode repeat")
        outer = canonical_int(row["outer_fold"], "episode outer fold")
        rank = canonical_int(row["query_rank"], "query rank")
        if repeat not in range(3) or outer not in range(5) or rank < 1:
            raise OpenADMETOracleProjectionError("episode scope differs")
        component = row["outer_group_id"]
        if (
            component != molecules[anchor]["similarity_component_hash"]
            or component != molecules[query]["similarity_component_hash"]
        ):
            raise OpenADMETOracleProjectionError("episode component differs")
        fold = folds[(anchor, repeat, outer)]
        if canonical_int(fold["outer_fold"], "assigned outer fold") != outer:
            raise OpenADMETOracleProjectionError("episode fold assignment differs")
        prior = episodes.get(episode)
        metadata = (
            "anchor_molecule_id",
            "repeat",
            "outer_fold",
            "outer_group_id",
            "episode_policy_id",
        )
        if prior is not None and tuple(prior[item] for item in metadata) != tuple(
            row[item] for item in metadata
        ):
            raise OpenADMETOracleProjectionError("expanded episode metadata differs")
        if rank in ranks[episode]:
            raise OpenADMETOracleProjectionError("duplicate episode query rank")
        ranks[episode].add(rank)
        episodes[episode] = row
        result[key] = row
    if not result:
        raise OpenADMETOracleProjectionError("public episode set is empty")
    for episode, episode_ranks in ranks.items():
        if episode_ranks != set(range(1, len(episode_ranks) + 1)):
            raise OpenADMETOracleProjectionError(
                f"episode query ranks are not contiguous: {episode}"
            )
    return result


def _validate_targets(
    rows: Mapping[str, Sequence[Mapping[str, str]]],
    molecules: Mapping[str, Mapping[str, str]],
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
    public: Mapping[PublicKey, Mapping[str, str]],
    pairs: Mapping[str, Mapping[str, str]],
    cell_scopes: Sequence[Scope],
    oof_receipts: Mapping[str, str],
) -> None:
    expected_scopes = set(cell_scopes)
    private_names = (
        "training_points.csv",
        "training_pairs.csv",
        "episode_anchor_contexts.csv",
        "global_anchor_contexts.csv",
        "episode_truth.csv",
        "activity_cliffs.csv",
    )
    for name in private_names:
        if any(scope(row) not in expected_scopes for row in rows[name]):
            raise OpenADMETOracleProjectionError(f"{name} scope differs")
    _validate_training_points(rows["training_points.csv"], molecules, folds)
    _validate_training_pairs(rows["training_pairs.csv"], molecules, folds, pairs)
    _validate_contexts_and_truth(
        rows, molecules, folds, public, cell_scopes, oof_receipts
    )


def _validate_training_points(
    rows: Sequence[Mapping[str, str]],
    molecules: Mapping[str, Mapping[str, str]],
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
) -> None:
    seen: set[tuple[Scope, str]] = set()
    for row in rows:
        cell = scope(row)
        molecule = row["molecule_id"]
        if molecule not in molecules or not _training_member(molecule, cell, folds):
            raise OpenADMETOracleProjectionError("training point crosses fold boundary")
        if row["component_id"] != molecules[molecule]["similarity_component_hash"]:
            raise OpenADMETOracleProjectionError("training point component differs")
        finite(row["point"], "training point")
        if finite(row["sample_weight"], "point sample weight") <= 0.0:
            raise OpenADMETOracleProjectionError("point sample weight is not positive")
        key = cell, molecule
        if key in seen:
            raise OpenADMETOracleProjectionError("duplicate training point")
        seen.add(key)


def _validate_training_pairs(
    rows: Sequence[Mapping[str, str]],
    molecules: Mapping[str, Mapping[str, str]],
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
    geometry: Mapping[str, Mapping[str, str]],
) -> None:
    grouped: dict[tuple[Scope, str], list[Mapping[str, str]]] = defaultdict(list)
    seen: set[tuple[Scope, str, str]] = set()
    for row in rows:
        cell = scope(row)
        pair_id = row["pair_id"]
        pair = geometry.get(pair_id)
        if (
            pair is None
            or pair["local_pair"] != "true"
            or pair["extraction_status"] not in VALID_STATUSES
        ):
            raise OpenADMETOracleProjectionError("training pair lacks valid R4 linkage")
        anchor = row["anchor_molecule_id"]
        analog = row["analog_molecule_id"]
        if (
            anchor not in molecules
            or analog not in molecules
            or anchor == analog
            or not _training_member(anchor, cell, folds)
            or not _training_member(analog, cell, folds)
        ):
            raise OpenADMETOracleProjectionError("training pair crosses fold boundary")
        if row["component_id"] != pair["similarity_component_hash"]:
            raise OpenADMETOracleProjectionError("training pair component differs")
        forward = (
            anchor == pair["left_molecule_id"] and analog == pair["right_molecule_id"]
        )
        reverse = (
            anchor == pair["right_molecule_id"] and analog == pair["left_molecule_id"]
        )
        expected_direction = (
            pair["a_to_b_direction_id" if forward else "b_to_a_direction_id"]
            if forward or reverse
            else ""
        )
        if not expected_direction or row["direction_id"] != expected_direction:
            raise OpenADMETOracleProjectionError("training pair direction differs")
        finite(row["delta"], "training delta")
        weight = _fraction(row["sample_weight"], "pair sample weight")
        if weight <= 0:
            raise OpenADMETOracleProjectionError("pair sample weight is not positive")
        identity = cell, pair_id, row["direction_id"]
        if identity in seen:
            raise OpenADMETOracleProjectionError("duplicate training pair direction")
        seen.add(identity)
        grouped[(cell, pair_id)].append(row)
    component_pairs: dict[tuple[Scope, str], set[str]] = defaultdict(set)
    for (cell, pair_id), directions in grouped.items():
        if len(directions) != 2:
            raise OpenADMETOracleProjectionError("training pair lacks two directions")
        first, second = directions
        if (
            first["anchor_molecule_id"] != second["analog_molecule_id"]
            or first["analog_molecule_id"] != second["anchor_molecule_id"]
            or _decimal(first["delta"], "training delta")
            != -_decimal(second["delta"], "training delta")
        ):
            raise OpenADMETOracleProjectionError("training pair is not antisymmetric")
        component = first["component_id"]
        component_pairs[(cell, component)].add(pair_id)
    for (cell, _pair_id), directions in grouped.items():
        component = directions[0]["component_id"]
        pair_count = len(component_pairs[(cell, component)])
        expected = Fraction(1, 2 * pair_count)
        if any(
            _fraction(row["sample_weight"], "pair sample weight") != expected
            for row in directions
        ):
            raise OpenADMETOracleProjectionError("pair sample weight differs")


def _validate_contexts_and_truth(
    rows: Mapping[str, Sequence[Mapping[str, str]]],
    molecules: Mapping[str, Mapping[str, str]],
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
    public: Mapping[PublicKey, Mapping[str, str]],
    cell_scopes: Sequence[Scope],
    oof_receipts: Mapping[str, str],
) -> None:
    expected_episodes: dict[Scope, set[str]] = {cell: set() for cell in cell_scopes}
    expected_queries: dict[Scope, set[PublicKey]] = {
        cell: set() for cell in cell_scopes
    }
    for (episode_id, query_id), episode in public.items():
        repeat = canonical_int(episode["repeat"], "episode repeat")
        anchor = episode["anchor_molecule_id"]
        selected = episode["episode_policy_id"] == "selected_anchor"
        for cell in cell_scopes:
            if cell[1] != repeat:
                continue
            fold = folds[(anchor, repeat, cell[2])]
            assigned_outer = canonical_int(fold["outer_fold"], "assigned outer fold")
            include = (
                cell[0] == "outer"
                and assigned_outer == cell[2]
                and canonical_int(episode["outer_fold"], "episode outer fold")
                == cell[2]
            ) or (
                selected
                and cell[0] == "inner"
                and assigned_outer != cell[2]
                and canonical_int(episode["outer_fold"], "episode outer fold")
                == assigned_outer
                and fold["inner_fold"] != ""
                and canonical_int(fold["inner_fold"], "assigned inner fold") == cell[3]
            )
            if include:
                expected_episodes[cell].add(episode_id)
                expected_queries[cell].add((episode_id, query_id))

    measured = _validate_context_rows(
        rows["episode_anchor_contexts.csv"],
        public,
        folds,
        molecules,
        oof_receipts,
        measured=True,
    )
    global_only = _validate_context_rows(
        rows["global_anchor_contexts.csv"],
        public,
        folds,
        molecules,
        oof_receipts,
        measured=False,
    )
    if measured.keys() != global_only.keys():
        raise OpenADMETOracleProjectionError("C3/measured context membership differs")
    for key in measured:
        left = measured[key]
        right = global_only[key]
        for name in GLOBAL_CONTEXT_COLUMNS:
            if left[name] != right[name]:
                raise OpenADMETOracleProjectionError("C3 OOF context differs")

    truth = _validate_query_rows(
        rows["episode_truth.csv"], public, folds, molecules, truth=True
    )
    cliffs = _validate_query_rows(
        rows["activity_cliffs.csv"], public, folds, molecules, truth=False
    )
    actual_episodes = {
        cell: {episode for scope_key, episode in measured if scope_key == cell}
        for cell in cell_scopes
    }
    actual_truth = {
        cell: {
            (episode, query) for scope_key, episode, query in truth if scope_key == cell
        }
        for cell in cell_scopes
    }
    actual_cliffs = {
        cell: {
            (episode, query)
            for scope_key, episode, query in cliffs
            if scope_key == cell
        }
        for cell in cell_scopes
    }
    if actual_episodes != expected_episodes:
        raise OpenADMETOracleProjectionError("primary context superset differs")
    if actual_truth != expected_queries or actual_cliffs != expected_queries:
        raise OpenADMETOracleProjectionError("primary scorer superset differs")


def _validate_context_rows(
    rows: Sequence[Mapping[str, str]],
    public: Mapping[PublicKey, Mapping[str, str]],
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
    molecules: Mapping[str, Mapping[str, str]],
    oof_receipts: Mapping[str, str],
    *,
    measured: bool,
) -> dict[tuple[Scope, str], Mapping[str, str]]:
    output: dict[tuple[Scope, str], Mapping[str, str]] = {}
    model_by_scope: dict[Scope, str] = {}
    for row in rows:
        cell = scope(row)
        episode = _episode_by_id(public, row["episode_id"])
        key = cell, row["episode_id"]
        if (
            key in output
            or episode is None
            or not _scope_matches_episode(cell, episode, folds, molecules)
            or episode["anchor_molecule_id"] != row["anchor_molecule_id"]
        ):
            raise OpenADMETOracleProjectionError("anchor context differs")
        if measured:
            available = row["anchor_point_available"]
            if available not in {"true", "false"}:
                raise OpenADMETOracleProjectionError("anchor availability differs")
            if available == "true":
                finite(row["anchor_point"], "anchor point")
            elif row["anchor_point"] != "":
                raise OpenADMETOracleProjectionError("unavailable anchor point differs")
        model_id = _validate_oof(row, cell, oof_receipts)
        if cell in model_by_scope and model_by_scope[cell] != model_id:
            raise OpenADMETOracleProjectionError("OOF model ID changes within scope")
        model_by_scope[cell] = model_id
        output[key] = row
    return output


def _validate_query_rows(
    rows: Sequence[Mapping[str, str]],
    public: Mapping[PublicKey, Mapping[str, str]],
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
    molecules: Mapping[str, Mapping[str, str]],
    *,
    truth: bool,
) -> dict[tuple[Scope, str, str], Mapping[str, str]]:
    output: dict[tuple[Scope, str, str], Mapping[str, str]] = {}
    for row in rows:
        cell = scope(row)
        public_key = row["episode_id"], row["query_molecule_id"]
        episode = public.get(public_key)
        key = cell, *public_key
        if (
            key in output
            or episode is None
            or not _scope_matches_episode(cell, episode, folds, molecules)
        ):
            raise OpenADMETOracleProjectionError("sealed query membership differs")
        if truth:
            available = row["query_point_available"]
            if available not in {"true", "false"}:
                raise OpenADMETOracleProjectionError("query availability differs")
            if available == "true":
                finite(row["query_point"], "query point")
            elif row["query_point"] != "":
                raise OpenADMETOracleProjectionError("unavailable query point differs")
        elif row["activity_cliff"] not in {"true", "false"}:
            raise OpenADMETOracleProjectionError("activity cliff differs")
        output[key] = row
    return output


def _validate_oof(
    row: Mapping[str, str], cell: Scope, oof_receipts: Mapping[str, str]
) -> str:
    expected_scope = (
        OUTER_OOF_SCOPE if cell[0] == "outer" else INNER_OOF_SCOPE.format(outer=cell[2])
    )
    expected_receipt = oof_receipts[
        OUTER_OOF_INPUT if cell[0] == "outer" else INNER_OOF_INPUT
    ]
    if (
        row["anchor_global_oof_source_scope"] != expected_scope
        or row["anchor_global_oof_receipt_sha256"] != expected_receipt
    ):
        raise OpenADMETOracleProjectionError("OOF source identity differs")
    model_id = row["anchor_global_oof_model_id"]
    digest(model_id, "OOF model ID")
    finite(row["anchor_global_oof_prediction"], "OOF prediction")
    return model_id


def _scope_matches_episode(
    cell: Scope,
    episode: Mapping[str, str],
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
    molecules: Mapping[str, Mapping[str, str]],
) -> bool:
    if cell[1] != canonical_int(episode["repeat"], "episode repeat"):
        return False
    anchor = episode["anchor_molecule_id"]
    fold = folds.get((anchor, cell[1], cell[2]))
    if (
        fold is None
        or molecules[anchor]["similarity_component_hash"] != episode["outer_group_id"]
    ):
        return False
    assigned_outer = canonical_int(fold["outer_fold"], "assigned outer fold")
    episode_outer = canonical_int(episode["outer_fold"], "episode outer fold")
    if cell[0] == "outer":
        return assigned_outer == cell[2] and episode_outer == cell[2]
    if episode["episode_policy_id"] != "selected_anchor":
        return False
    return (
        assigned_outer != cell[2]
        and episode_outer == assigned_outer
        and cell[3] is not None
        and fold["inner_fold"] != ""
        and canonical_int(fold["inner_fold"], "assigned inner fold") == cell[3]
    )


def _training_member(
    molecule: str,
    cell: Scope,
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
) -> bool:
    fold = folds.get((molecule, cell[1], cell[2]))
    if fold is None:
        raise OpenADMETOracleProjectionError("missing fold context")
    if canonical_int(fold["outer_fold"], "assigned outer fold") == cell[2]:
        return False
    return (
        cell[0] == "outer"
        or canonical_int(fold["inner_fold"], "assigned inner fold") != cell[3]
    )


def _episode_by_id(
    public: Mapping[PublicKey, Mapping[str, str]], episode_id: str
) -> Mapping[str, str] | None:
    for (episode, _), row in public.items():
        if episode == episode_id:
            return row
    return None


def _fraction(value: str, label: str) -> Fraction:
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise OpenADMETOracleProjectionError(f"{label} differs") from exc
    return result


def _decimal(value: str, label: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise OpenADMETOracleProjectionError(f"{label} differs") from exc
    if not result.is_finite():
        raise OpenADMETOracleProjectionError(f"{label} is not finite")
    return result


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


__all__ = [
    "ANCHOR_CONTEXT_COLUMNS",
    "CLIFF_COLUMNS",
    "FEATURE_FILES",
    "GLOBAL_CONTEXT_COLUMNS",
    "OpenADMETOracleProjectionError",
    "PUBLIC_QUERY_COLUMNS",
    "SOURCE_COLUMNS",
    "SCOPE_COLUMNS",
    "TRAINING_PAIR_COLUMNS",
    "TRAINING_POINT_COLUMNS",
    "TRUTH_COLUMNS",
    "ValidatedOracleSources",
    "csv_rows",
    "output_columns",
    "scope",
    "scopes",
    "validate_oracle_sources",
]

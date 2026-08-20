"""Receipt-safe R4 projection loading before transformation compilation.

This module deliberately stops at the least-privilege projection boundary.  It
revalidates the accepted six-file projection, reconstructs audited molecule
records, and returns immutable structural/state/fold/episode records.  Pair
extraction, coverage arithmetic, and publication are separate milestones.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from cypshift.chemistry import standardize_molecule
from cypshift.openadmet_transformation_io import (
    DIRECT_PROJECTION_COLUMNS,
    ENDPOINTS,
    MASK_PROJECTION_COLUMNS,
    NO_AUTHORITY,
    NO_TARGET_ACCOUNTING,
    PUBLIC_EPISODE_COLUMNS,
    STRUCTURE_COLUMNS,
    VALUE_STATES,
    canonical_csv_bytes,
    canonical_json_bytes,
    strict_json_cell,
    strict_json_object,
)
from cypshift.openadmet_transformation_projection import (
    EXPECTED_CANDIDATE_POOL,
    EXPECTED_POLICIES,
    EXPECTED_PROTOCOL,
    EXPECTED_SEEDS,
    FOLD_PROJECTION_COLUMNS,
    OUTPUT_FILES,
    PROJECTION_SCHEMA_VERSION,
)
from cypshift.schema import MoleculeInput, MoleculeRecord, MoleculeStatus

CONTRACT_SHA256 = "63d12cb376760c65eabd3d94d3f3939b0591e4019e1332075df0a4c10a4b4954"
PROJECTION_STATUS = "R4_TRANSFORMATION_PROJECTION_SYNTHETIC_ONLY"
CSV_COLUMNS = {
    "direct_projection.csv": DIRECT_PROJECTION_COLUMNS,
    "fold_projection.csv": FOLD_PROJECTION_COLUMNS,
    "mask_projection.csv": MASK_PROJECTION_COLUMNS,
    "public_projection.csv": PUBLIC_EPISODE_COLUMNS,
    "structure_projection.csv": STRUCTURE_COLUMNS,
}
COUNT_KEYS = {
    "direct_projection.csv": "direct_observations",
    "fold_projection.csv": "group_folds",
    "mask_projection.csv": "masks",
    "public_projection.csv": "public_episodes",
    "structure_projection.csv": "structure",
}
SOURCE_NAMES = {
    "direct_observations.csv",
    "group_folds.csv",
    "masks.csv",
    "public_episodes.csv",
    "structure.csv",
}
SOURCE_COUNT_KEYS = {
    "direct_observations.csv": "direct_observations",
    "group_folds.csv": "group_folds",
    "masks.csv": "masks",
    "public_episodes.csv": "public_episodes",
    "structure.csv": "structure",
}
FORBIDDEN_FIELDS = (
    "raw_point",
    "raw_low",
    "raw_high",
    "raw_std",
    "point",
    "low",
    "high",
    "std",
    "point_eligible",
    "anchor_eligible",
    "anchor_observation_references",
    "anchor_value_availability_mask",
    "selector",
    "prediction",
    "metric",
)
K = TypeVar("K")
V = TypeVar("V")


class OpenADMETTransformationCoverageError(ValueError):
    """A projection receipt, schema, identity, or firewall invariant failed."""


@dataclass(frozen=True, slots=True)
class ProjectionFileReceipt:
    """One immutable consumed-file receipt."""

    name: str
    sha256: str
    bytes: int
    rows: int | None
    columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProjectionSourceReceipt:
    """One immutable upstream source receipt copied by the projector."""

    name: str
    sha256: str
    bytes: int
    rows: int


@dataclass(frozen=True, slots=True)
class ProjectionMolecule:
    """An audited molecule and its frozen reconstructed-family proxy."""

    molecule: MoleculeRecord
    raw_structure_sha256: str
    similarity_component_hash: str


@dataclass(frozen=True, slots=True)
class DirectAvailability:
    """One label-safe direct endpoint state; no magnitude is present."""

    observation_id: str
    molecule_id: str
    endpoint: str
    value_state: str


@dataclass(frozen=True, slots=True)
class ProjectionFold:
    """One molecule row in one repeated outer-validation scope."""

    molecule_id: str
    similarity_component_hash: str
    repeat: int
    seed: int
    outer_fold: int
    outer_validation_fold: int
    inner_fold: int | None


@dataclass(frozen=True, slots=True)
class ProjectionEpisode:
    """One expanded public anchor-to-query structural episode row."""

    episode_id: str
    protocol: str
    repeat: int
    outer_fold: int
    outer_group_id: str
    query_molecule_id: str
    query_rank: int
    anchor_molecule_id: str
    candidate_pool_id: str
    episode_policy_id: str


@dataclass(frozen=True, slots=True)
class ProjectionBundle:
    """Fully revalidated, immutable inputs for later coverage compilation."""

    input_receipts: tuple[ProjectionFileReceipt, ...]
    source_receipts: tuple[ProjectionSourceReceipt, ...]
    molecules: tuple[ProjectionMolecule, ...]
    direct_availability: tuple[DirectAvailability, ...]
    folds: tuple[ProjectionFold, ...]
    episodes: tuple[ProjectionEpisode, ...]


def load_transformation_projection(directory: Path) -> ProjectionBundle:
    """Load one exact six-file projection once and revalidate every safe join."""

    files = _read_projection_files(directory)
    digests = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    manifest = _manifest(files["manifest.json"])
    _precheck_receipts(manifest, files, digests)
    rows = {
        name: _csv_rows(files[name], columns, name)
        for name, columns in CSV_COLUMNS.items()
    }
    input_receipts, source_receipts = _validate_manifest(manifest, files, digests, rows)
    molecules = _molecules(rows["structure_projection.csv"])
    by_id = {item.molecule.molecule_id: item for item in molecules}
    direct = _direct(rows["direct_projection.csv"], by_id)
    folds = _folds(rows["fold_projection.csv"], by_id)
    episodes = _episodes(
        rows["public_projection.csv"],
        rows["mask_projection.csv"],
        by_id,
        folds,
    )
    return ProjectionBundle(
        input_receipts=input_receipts,
        source_receipts=source_receipts,
        molecules=molecules,
        direct_availability=direct,
        folds=folds,
        episodes=episodes,
    )


def _read_projection_files(directory: Path) -> dict[str, bytes]:
    if (
        ".." in directory.parts
        or any(path.is_symlink() for path in (directory, *directory.parents))
        or not directory.is_dir()
    ):
        raise OpenADMETTransformationCoverageError(
            "projection directory must be a real directory"
        )
    expected = set(OUTPUT_FILES)
    observed = {entry.name for entry in directory.iterdir()}
    if observed != expected:
        raise OpenADMETTransformationCoverageError("projection file set differs")
    output: dict[str, bytes] = {}
    for name in OUTPUT_FILES:
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise OpenADMETTransformationCoverageError(
                f"projection file is not regular: {name}"
            )
        output[name] = path.read_bytes()
    return output


def _manifest(data: bytes) -> dict[str, Any]:
    try:
        value = strict_json_object(data, "projection manifest")
    except ValueError as exc:
        raise OpenADMETTransformationCoverageError(str(exc)) from exc
    if canonical_json_bytes(value) != data:
        raise OpenADMETTransformationCoverageError(
            "projection manifest is not canonical"
        )
    expected_keys = {
        "schema_version",
        "status",
        "source_receipts",
        "output_receipts",
        "counts",
        "accounting",
        "authority",
        "forbidden_fields",
    }
    if set(value) != expected_keys:
        raise OpenADMETTransformationCoverageError("projection manifest schema differs")
    if value["schema_version"] != PROJECTION_SCHEMA_VERSION:
        raise OpenADMETTransformationCoverageError("projection schema version differs")
    if value["status"] != PROJECTION_STATUS:
        raise OpenADMETTransformationCoverageError("projection status differs")
    if not _exact_typed_map(value["accounting"], NO_TARGET_ACCOUNTING):
        raise OpenADMETTransformationCoverageError("projection accounting differs")
    if not _exact_typed_map(
        value["authority"], {"status": PROJECTION_STATUS, **NO_AUTHORITY}
    ):
        raise OpenADMETTransformationCoverageError("projection authority differs")
    if value["forbidden_fields"] != list(FORBIDDEN_FIELDS):
        raise OpenADMETTransformationCoverageError("projection forbidden fields differ")
    return value


def _csv_rows(
    data: bytes, columns: tuple[str, ...], label: str
) -> tuple[dict[str, str], ...]:
    try:
        text = data.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        if reader.fieldnames != list(columns):
            raise OpenADMETTransformationCoverageError(f"{label} columns differ")
        rows: list[dict[str, str]] = []
        for raw in reader:
            if set(raw) != set(columns) or any(value is None for value in raw.values()):
                raise OpenADMETTransformationCoverageError(f"{label} row width differs")
            rows.append({column: raw[column] for column in columns})
    except (UnicodeDecodeError, csv.Error) as exc:
        raise OpenADMETTransformationCoverageError(f"invalid CSV: {label}") from exc
    if canonical_csv_bytes(columns, rows) != data:
        raise OpenADMETTransformationCoverageError(f"{label} is not canonical")
    return tuple(rows)


def _precheck_receipts(
    manifest: dict[str, Any], files: dict[str, bytes], digests: dict[str, str]
) -> None:
    """Verify every declared input receipt before parsing any CSV payload."""

    counts = manifest["counts"]
    if (
        not isinstance(counts, dict)
        or set(counts) != set(COUNT_KEYS.values())
        or any(not _nonnegative_int(value) for value in counts.values())
    ):
        raise OpenADMETTransformationCoverageError("projection counts schema differs")
    output_receipts = manifest["output_receipts"]
    if not isinstance(output_receipts, dict) or set(output_receipts) != set(
        CSV_COLUMNS
    ):
        raise OpenADMETTransformationCoverageError("projection output receipts differ")
    for name, columns in CSV_COLUMNS.items():
        receipt = output_receipts[name]
        if (
            not isinstance(receipt, dict)
            or set(receipt) != {"sha256", "bytes", "rows", "columns"}
            or not _sha256(receipt["sha256"])
            or not _nonnegative_int(receipt["bytes"], positive=True)
            or not _nonnegative_int(receipt["rows"])
            or receipt["columns"] != list(columns)
            or receipt["sha256"] != digests[name]
            or receipt["bytes"] != len(files[name])
        ):
            raise OpenADMETTransformationCoverageError(
                f"pre-parse receipt differs: {name}"
            )
    source_receipts = manifest["source_receipts"]
    if not isinstance(source_receipts, dict) or set(source_receipts) != SOURCE_NAMES:
        raise OpenADMETTransformationCoverageError("projection source receipts differ")
    for name, receipt in source_receipts.items():
        if (
            not isinstance(receipt, dict)
            or set(receipt) != {"sha256", "bytes", "rows"}
            or not _sha256(receipt["sha256"])
            or not _nonnegative_int(receipt["bytes"], positive=True)
            or not _nonnegative_int(receipt["rows"])
            or receipt["rows"] != counts[SOURCE_COUNT_KEYS[name]]
        ):
            raise OpenADMETTransformationCoverageError(
                f"source receipt value differs: {name}"
            )


def _validate_manifest(
    manifest: dict[str, Any],
    files: dict[str, bytes],
    digests: dict[str, str],
    rows: dict[str, tuple[dict[str, str], ...]],
) -> tuple[tuple[ProjectionFileReceipt, ...], tuple[ProjectionSourceReceipt, ...]]:
    counts = manifest["counts"]
    if (
        not isinstance(counts, dict)
        or set(counts) != set(COUNT_KEYS.values())
        or any(not _nonnegative_int(value) for value in counts.values())
    ):
        raise OpenADMETTransformationCoverageError("projection counts schema differs")
    output_receipts = manifest["output_receipts"]
    if not isinstance(output_receipts, dict) or set(output_receipts) != set(
        CSV_COLUMNS
    ):
        raise OpenADMETTransformationCoverageError("projection output receipts differ")
    consumed: list[ProjectionFileReceipt] = []
    for name in sorted(CSV_COLUMNS):
        receipt = output_receipts[name]
        columns = CSV_COLUMNS[name]
        if not isinstance(receipt, dict) or set(receipt) != {
            "sha256",
            "bytes",
            "rows",
            "columns",
        }:
            raise OpenADMETTransformationCoverageError(
                f"receipt schema differs: {name}"
            )
        if (
            not _sha256(receipt["sha256"])
            or not _nonnegative_int(receipt["bytes"], positive=True)
            or not _nonnegative_int(receipt["rows"])
            or not isinstance(receipt["columns"], list)
            or any(not isinstance(column, str) for column in receipt["columns"])
        ):
            raise OpenADMETTransformationCoverageError(f"receipt value differs: {name}")
        row_count = len(rows[name])
        digest = digests[name]
        size = len(files[name])
        expected = {
            "sha256": digest,
            "bytes": size,
            "rows": row_count,
            "columns": list(columns),
        }
        if receipt != expected or counts[COUNT_KEYS[name]] != row_count:
            raise OpenADMETTransformationCoverageError(f"receipt/count differs: {name}")
        consumed.append(ProjectionFileReceipt(name, digest, size, row_count, columns))
    consumed.append(
        ProjectionFileReceipt(
            "manifest.json",
            digests["manifest.json"],
            len(files["manifest.json"]),
            None,
            (),
        )
    )
    source_receipts = manifest["source_receipts"]
    if not isinstance(source_receipts, dict) or set(source_receipts) != SOURCE_NAMES:
        raise OpenADMETTransformationCoverageError("projection source receipts differ")
    upstream: list[ProjectionSourceReceipt] = []
    for name in sorted(SOURCE_NAMES):
        receipt = source_receipts[name]
        if not isinstance(receipt, dict) or set(receipt) != {"sha256", "bytes", "rows"}:
            raise OpenADMETTransformationCoverageError(
                f"source receipt schema differs: {name}"
            )
        digest = receipt["sha256"]
        size = receipt["bytes"]
        row_count = receipt["rows"]
        if (
            not _sha256(digest)
            or not _nonnegative_int(size, positive=True)
            or not _nonnegative_int(row_count)
        ):
            raise OpenADMETTransformationCoverageError(
                f"source receipt value differs: {name}"
            )
        upstream.append(ProjectionSourceReceipt(name, digest, size, row_count))
    return tuple(consumed), tuple(upstream)


def _molecules(rows: tuple[dict[str, str], ...]) -> tuple[ProjectionMolecule, ...]:
    output: list[ProjectionMolecule] = []
    seen_ids: set[str] = set()
    id_by_hash: dict[str, str] = {}
    for row in rows:
        molecule_id = _text(row["molecule_id"], "molecule ID")
        if molecule_id in seen_ids:
            raise OpenADMETTransformationCoverageError("duplicate molecule ID")
        seen_ids.add(molecule_id)
        raw_smiles = row["raw_smiles"]
        raw_hash = row["raw_structure_sha256"]
        structure_hash = row["standardized_structure_hash"]
        component = row["similarity_component_hash"]
        if not all(_sha256(value) for value in (raw_hash, structure_hash, component)):
            raise OpenADMETTransformationCoverageError("invalid structure receipt")
        if hashlib.sha256(raw_smiles.encode("utf-8")).hexdigest() != raw_hash:
            raise OpenADMETTransformationCoverageError("raw structure hash differs")
        molecule = standardize_molecule(
            MoleculeInput(
                molecule_id=molecule_id,
                structure=raw_smiles,
                structure_format="smiles",
                source="openadmet_r4_projection",
                provenance=f"projection:{molecule_id}",
            )
        )
        if (
            molecule.status is not MoleculeStatus.ACCEPTED
            or molecule.standardized_structure != row["standardized_smiles"]
            or molecule.standardized_structure_hash != structure_hash
        ):
            raise OpenADMETTransformationCoverageError("standardized structure differs")
        prior = id_by_hash.setdefault(structure_hash, molecule_id)
        if prior != molecule_id:
            raise OpenADMETTransformationCoverageError(
                "distinct molecule IDs share a standardized structure hash"
            )
        output.append(ProjectionMolecule(molecule, raw_hash, component))
    if not output:
        raise OpenADMETTransformationCoverageError("structure projection is empty")
    return tuple(sorted(output, key=lambda item: item.molecule.molecule_id))


def _direct(
    rows: tuple[dict[str, str], ...],
    molecules: dict[str, ProjectionMolecule],
) -> tuple[DirectAvailability, ...]:
    output: list[DirectAvailability] = []
    seen: set[tuple[str, str]] = set()
    observations: set[str] = set()
    for row in rows:
        molecule_id = _text(row["molecule_id"], "direct molecule ID")
        endpoint = row["endpoint"]
        observation_id = row["observation_id"]
        state = row["value_state"]
        if molecule_id not in molecules or endpoint not in ENDPOINTS:
            raise OpenADMETTransformationCoverageError("direct membership differs")
        molecule = molecules[molecule_id]
        if (
            row["raw_structure_sha256"] != molecule.raw_structure_sha256
            or row["standardized_structure_hash"]
            != molecule.molecule.standardized_structure_hash
            or row["similarity_component_hash"] != molecule.similarity_component_hash
        ):
            raise OpenADMETTransformationCoverageError("direct structure join differs")
        if not _sha256(observation_id) or state not in VALUE_STATES:
            raise OpenADMETTransformationCoverageError("direct state differs")
        if observation_id in observations or (molecule_id, endpoint) in seen:
            raise OpenADMETTransformationCoverageError("duplicate direct observation")
        observations.add(observation_id)
        seen.add((molecule_id, endpoint))
        output.append(DirectAvailability(observation_id, molecule_id, endpoint, state))
    expected = {
        (molecule_id, endpoint) for molecule_id in molecules for endpoint in ENDPOINTS
    }
    if seen != expected:
        raise OpenADMETTransformationCoverageError("direct endpoint matrix differs")
    return tuple(sorted(output, key=lambda row: (row.molecule_id, row.endpoint)))


def _folds(
    rows: tuple[dict[str, str], ...],
    molecules: dict[str, ProjectionMolecule],
) -> tuple[ProjectionFold, ...]:
    output: list[ProjectionFold] = []
    seen: set[tuple[str, int, int]] = set()
    outer_by_group: dict[tuple[str, int], int] = {}
    inner_by_group: dict[tuple[str, int, int], int | None] = {}
    for row in rows:
        molecule_id = _text(row["molecule_id"], "fold molecule ID")
        if molecule_id not in molecules:
            raise OpenADMETTransformationCoverageError("fold membership differs")
        molecule = molecules[molecule_id]
        component = row["similarity_component_hash"]
        repeat = _int(row["repeat"], "repeat", 0, 2)
        seed = _int(row["seed"], "seed", 20260810, 20260812)
        outer = _int(row["outer_fold"], "outer fold", 0, 4)
        validation = _int(row["outer_validation_fold"], "validation fold", 0, 4)
        inner = _optional_int(row["inner_fold"], "inner fold", 0, 3)
        if (
            seed != EXPECTED_SEEDS[repeat]
            or component != molecule.similarity_component_hash
        ):
            raise OpenADMETTransformationCoverageError("fold component/seed differs")
        if (validation == outer) != (inner is None):
            raise OpenADMETTransformationCoverageError("fold inner sentinel differs")
        key = (molecule_id, repeat, validation)
        if key in seen:
            raise OpenADMETTransformationCoverageError("duplicate fold row")
        seen.add(key)
        _same(outer_by_group, (component, repeat), outer, "component outer fold")
        _same(
            inner_by_group,
            (component, repeat, validation),
            inner,
            "component inner fold",
        )
        output.append(
            ProjectionFold(
                molecule_id, component, repeat, seed, outer, validation, inner
            )
        )
    expected = {
        (molecule_id, repeat, validation)
        for molecule_id in molecules
        for repeat in range(3)
        for validation in range(5)
    }
    if seen != expected:
        raise OpenADMETTransformationCoverageError("fold matrix differs")
    return tuple(
        sorted(
            output,
            key=lambda row: (row.molecule_id, row.repeat, row.outer_validation_fold),
        )
    )


def _episodes(
    public_rows: tuple[dict[str, str], ...],
    mask_rows: tuple[dict[str, str], ...],
    molecules: dict[str, ProjectionMolecule],
    folds: tuple[ProjectionFold, ...],
) -> tuple[ProjectionEpisode, ...]:
    if not public_rows or not mask_rows:
        raise OpenADMETTransformationCoverageError("episode projection is empty")
    masks: dict[str, str] = {}
    for row in mask_rows:
        episode_id = row["episode_id"]
        anchor = _text(row["anchor_molecule_id_truth"], "anchor molecule ID")
        if not _sha256(episode_id) or episode_id in masks:
            raise OpenADMETTransformationCoverageError("mask episode identity differs")
        masks[episode_id] = anchor
    fold_outer = {(row.molecule_id, row.repeat): row.outer_fold for row in folds}
    output: list[ProjectionEpisode] = []
    seen: set[str] = set()
    for row in public_rows:
        episode_id = row["episode_id"]
        if not _sha256(episode_id) or episode_id in seen or episode_id not in masks:
            raise OpenADMETTransformationCoverageError(
                "public episode identity differs"
            )
        seen.add(episode_id)
        repeat = _int(row["repeat"], "episode repeat", 0, 2)
        outer = _int(row["outer_fold"], "episode outer fold", 0, 4)
        group = row["outer_group_id"]
        anchor = masks[episode_id]
        if row["protocol"] != EXPECTED_PROTOCOL:
            raise OpenADMETTransformationCoverageError("episode protocol differs")
        if row["candidate_pool_id"] != EXPECTED_CANDIDATE_POOL:
            raise OpenADMETTransformationCoverageError("candidate pool differs")
        if row["episode_policy_id"] not in EXPECTED_POLICIES:
            raise OpenADMETTransformationCoverageError("episode policy differs")
        if (
            anchor not in molecules
            or molecules[anchor].similarity_component_hash != group
        ):
            raise OpenADMETTransformationCoverageError("anchor component differs")
        if fold_outer[(anchor, repeat)] != outer:
            raise OpenADMETTransformationCoverageError("anchor fold differs")
        queries = _query_ids(row["query_molecule_ids"])
        if anchor in queries:
            raise OpenADMETTransformationCoverageError("anchor appears among queries")
        for rank, query in enumerate(queries, start=1):
            if (
                query not in molecules
                or molecules[query].similarity_component_hash != group
            ):
                raise OpenADMETTransformationCoverageError("query component differs")
            if fold_outer[(query, repeat)] != outer:
                raise OpenADMETTransformationCoverageError("query fold differs")
            output.append(
                ProjectionEpisode(
                    episode_id,
                    row["protocol"],
                    repeat,
                    outer,
                    group,
                    query,
                    rank,
                    anchor,
                    row["candidate_pool_id"],
                    row["episode_policy_id"],
                )
            )
    if seen != set(masks):
        raise OpenADMETTransformationCoverageError("public/mask membership differs")
    if not output:
        raise OpenADMETTransformationCoverageError("expanded episodes are empty")
    return tuple(sorted(output, key=lambda row: (row.episode_id, row.query_rank)))


def _query_ids(value: str) -> tuple[str, ...]:
    try:
        parsed = strict_json_cell(value, "query molecule IDs")
    except ValueError as exc:
        raise OpenADMETTransformationCoverageError(str(exc)) from exc
    if (
        not isinstance(parsed, list)
        or not parsed
        or len(parsed) > 10
        or any(not isinstance(item, str) or not item for item in parsed)
        or len(set(parsed)) != len(parsed)
        or json.dumps(parsed, ensure_ascii=False, separators=(",", ":")) != value
    ):
        raise OpenADMETTransformationCoverageError("query molecule IDs differ")
    return tuple(parsed)


def _same(mapping: dict[K, V], key: K, value: V, label: str) -> None:
    prior = mapping.setdefault(key, value)
    if prior != value:
        raise OpenADMETTransformationCoverageError(f"{label} differs")


def _text(value: str, label: str) -> str:
    if not value or value != value.strip():
        raise OpenADMETTransformationCoverageError(f"invalid {label}")
    return value


def _sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _nonnegative_int(value: Any, *, positive: bool = False) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= (1 if positive else 0)
    )


def _exact_typed_map(value: Any, expected: dict[str, Any]) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == set(expected)
        and all(
            type(value[key]) is type(expected_value) and value[key] == expected_value
            for key, expected_value in expected.items()
        )
    )


def _int(value: str, label: str, low: int, high: int) -> int:
    if (
        not value
        or not value.isascii()
        or not value.isdecimal()
        or (value != "0" and value.startswith("0"))
    ):
        raise OpenADMETTransformationCoverageError(f"invalid {label}")
    parsed = int(value)
    if parsed < low or parsed > high:
        raise OpenADMETTransformationCoverageError(f"invalid {label}")
    return parsed


def _optional_int(value: str, label: str, low: int, high: int) -> int | None:
    return None if value == "" else _int(value, label, low, high)


__all__ = [
    "CONTRACT_SHA256",
    "DirectAvailability",
    "OpenADMETTransformationCoverageError",
    "ProjectionBundle",
    "ProjectionEpisode",
    "ProjectionFileReceipt",
    "ProjectionFold",
    "ProjectionMolecule",
    "ProjectionSourceReceipt",
    "load_transformation_projection",
]

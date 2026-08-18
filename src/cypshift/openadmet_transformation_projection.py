"""Synthetic-only R4 source projection and join firewall.

The returned projection contains structural identity, direct availability state,
fold metadata, public episode membership, and the mask anchor identity prefix.
It has no target magnitudes, eligibility booleans, selector facts, test rows,
or model-facing authority.  Transformation extraction is intentionally outside
this vertical slice.
"""

from __future__ import annotations

import csv
import ctypes
import errno
import io
import json
import os
import platform
import shutil
import tempfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from cypshift.openadmet_transformation_io import (
    DIRECT_PROJECTION_COLUMNS,
    ENDPOINTS,
    MASK_PROJECTION_COLUMNS,
    NO_AUTHORITY,
    NO_TARGET_ACCOUNTING,
    PUBLIC_EPISODE_COLUMNS,
    STRUCTURE_COLUMNS,
    VALUE_STATES,
    OpenADMETTransformationIOError,
    TransformationSourcePaths,
    TransformationSources,
    canonical_csv_bytes,
    canonical_json_bytes,
    read_r4_sources,
    strict_json_cell,
    strict_json_object,
)

PROJECTION_SCHEMA_VERSION = "cypshift.openadmet_cyp_2026.transformation_projection.v1"
OUTPUT_FILES = (
    "direct_projection.csv",
    "fold_projection.csv",
    "public_projection.csv",
    "mask_projection.csv",
    "structure_projection.csv",
    "manifest.json",
)
FOLD_PROJECTION_COLUMNS = (
    "molecule_id",
    "similarity_component_hash",
    "repeat",
    "seed",
    "outer_fold",
    "outer_validation_fold",
    "inner_fold",
)
EXPECTED_CANDIDATE_POOL = "DEFERRED_NO_INFERRED_POOL_V1"
EXPECTED_PROTOCOL = "ANCHOR_EXPANSION_HOLDOUT"
EXPECTED_POLICIES = {"selected_anchor", "deterministic_random_anchor_stress"}
EXPECTED_SEEDS = (20260810, 20260811, 20260812)


class OpenADMETTransformationProjectionError(OpenADMETTransformationIOError):
    """A cross-file identity, fold, or safe-publication invariant failed."""


@dataclass(frozen=True, slots=True)
class TransformationProjectionResult:
    """Published synthetic R4 projection and deterministic byte receipts."""

    output_directory: Path
    manifest_path: Path
    rows: Mapping[str, int]


def validate_r4_joins(sources: TransformationSources) -> None:
    """Validate all synthetic cross-file joins without opening hidden fields."""

    structures = _validate_structures(sources.structure)
    direct = _validate_direct(sources.direct, structures)
    fold_index = _validate_folds(sources.folds, structures)
    public = _validate_public(sources.public, structures, fold_index)
    _validate_masks(sources.masks, public, structures, fold_index)
    if set(direct) != set(structures):
        raise OpenADMETTransformationProjectionError(
            "direct/structure molecule membership mismatch"
        )


def project_openadmet_transformation_inputs(
    *,
    direct_observations_path: Path,
    group_folds_path: Path,
    public_episodes_path: Path | None = None,
    masks_path: Path | None = None,
    structure_path: Path | None = None,
    output_directory: Path,
    expected_receipts: Mapping[str, str | Mapping[str, Any]],
    expected_counts: Mapping[str, int] | None = None,
    campaign_episodes_path: Path | None = None,
    episode_label_masks_path: Path | None = None,
    feature_input_path: Path | None = None,
) -> TransformationProjectionResult:
    """Build and atomically publish the synthetic R4 least-privilege view."""

    if public_episodes_path is None:
        public_episodes_path = campaign_episodes_path
    if masks_path is None:
        masks_path = episode_label_masks_path
    if structure_path is None:
        structure_path = feature_input_path
    if public_episodes_path is None or masks_path is None or structure_path is None:
        raise OpenADMETTransformationProjectionError(
            "public, mask, and structure source paths are required"
        )
    _check_destination(output_directory)
    paths = TransformationSourcePaths(
        direct_observations=direct_observations_path,
        group_folds=group_folds_path,
        public_episodes=public_episodes_path,
        masks=masks_path,
        structure=structure_path,
    )
    try:
        sources = read_r4_sources(
            paths, expected_receipts, expected_counts=expected_counts
        )
    except OpenADMETTransformationIOError as exc:
        if isinstance(exc, OpenADMETTransformationProjectionError):
            raise
        raise OpenADMETTransformationProjectionError(str(exc)) from exc
    try:
        validate_r4_joins(sources)
    except OpenADMETTransformationIOError as exc:
        if isinstance(exc, OpenADMETTransformationProjectionError):
            raise
        raise OpenADMETTransformationProjectionError(str(exc)) from exc
    output_data = _output_bytes(sources)
    manifest = _manifest(sources, output_data)
    output_data["manifest.json"] = canonical_json_bytes(manifest)

    parent = _safe_output_parent(output_directory)
    stage: Path | None = None
    try:
        stage = Path(tempfile.mkdtemp(prefix=".r4-projection-", dir=parent))
        for name in OUTPUT_FILES:
            _write_new(stage / name, output_data[name])
        _verify_staged_outputs(stage, output_data, manifest)
        _readonly_tree(stage)
        _check_destination(output_directory)
        _rename_noreplace(stage, output_directory)
        stage = None
    except Exception:
        _cleanup_stage(stage)
        raise
    return TransformationProjectionResult(
        output_directory,
        output_directory / "manifest.json",
        {
            "direct": len(sources.direct),
            "folds": len(sources.folds),
            "public": len(sources.public),
            "masks": len(sources.masks),
            "structure": len(sources.structure),
        },
    )


def _output_bytes(sources: TransformationSources) -> dict[str, bytes]:
    direct = sorted(sources.direct, key=lambda row: row["observation_id"])
    folds = sorted(
        sources.folds,
        key=lambda row: (
            row["molecule_id"],
            _int(row["repeat"], "repeat"),
            _int(row["outer_validation_fold"], "outer_validation_fold"),
            _int(row["outer_fold"], "outer_fold"),
            _int(row["seed"], "seed"),
            _inner_sort(row["inner_fold"]),
            row["similarity_component_hash"],
        ),
    )
    public = []
    for row in sorted(sources.public, key=lambda item: item["episode_id"]):
        output = dict(row)
        queries = _query_ids(row["query_molecule_ids"], "query molecule IDs")
        output["query_molecule_ids"] = json.dumps(
            queries, ensure_ascii=False, separators=(",", ":")
        )
        public.append(output)
    masks = sorted(sources.masks, key=lambda row: row["episode_id"])
    structures = sorted(sources.structure, key=lambda row: row["molecule_id"])
    return {
        "direct_projection.csv": canonical_csv_bytes(DIRECT_PROJECTION_COLUMNS, direct),
        "fold_projection.csv": canonical_csv_bytes(FOLD_PROJECTION_COLUMNS, folds),
        "public_projection.csv": canonical_csv_bytes(PUBLIC_EPISODE_COLUMNS, public),
        "mask_projection.csv": canonical_csv_bytes(MASK_PROJECTION_COLUMNS, masks),
        "structure_projection.csv": canonical_csv_bytes(STRUCTURE_COLUMNS, structures),
    }


def _manifest(
    sources: TransformationSources, output_data: Mapping[str, bytes]
) -> dict[str, Any]:
    return {
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "status": "R4_TRANSFORMATION_PROJECTION_SYNTHETIC_ONLY",
        "source_receipts": sources.source_receipts,
        "output_receipts": _output_receipts(output_data),
        "counts": {
            "direct_observations": len(sources.direct),
            "group_folds": len(sources.folds),
            "public_episodes": len(sources.public),
            "masks": len(sources.masks),
            "structure": len(sources.structure),
        },
        "accounting": dict(NO_TARGET_ACCOUNTING),
        "authority": {
            "status": "R4_TRANSFORMATION_PROJECTION_SYNTHETIC_ONLY",
            **NO_AUTHORITY,
        },
        "forbidden_fields": [
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
        ],
    }


def _output_receipts(output_data: Mapping[str, bytes]) -> dict[str, dict[str, Any]]:
    schemas: dict[str, tuple[str, ...]] = {
        "direct_projection.csv": DIRECT_PROJECTION_COLUMNS,
        "fold_projection.csv": FOLD_PROJECTION_COLUMNS,
        "public_projection.csv": PUBLIC_EPISODE_COLUMNS,
        "mask_projection.csv": MASK_PROJECTION_COLUMNS,
        "structure_projection.csv": STRUCTURE_COLUMNS,
    }
    receipts: dict[str, dict[str, Any]] = {}
    for name, data in sorted(output_data.items()):
        if name == "manifest.json":
            continue
        columns = schemas[name]
        rows = _csv_row_count(data, columns, name)
        receipts[name] = {
            "sha256": sha256(data).hexdigest(),
            "bytes": len(data),
            "rows": rows,
            "columns": list(columns),
        }
    return receipts


def _verify_staged_outputs(
    stage: Path, output_data: Mapping[str, bytes], manifest: Mapping[str, Any]
) -> None:
    if {path.name for path in stage.iterdir()} != set(OUTPUT_FILES):
        raise OpenADMETTransformationProjectionError("staged output file set mismatch")
    receipts = manifest.get("output_receipts")
    if not isinstance(receipts, dict) or receipts != _output_receipts(output_data):
        raise OpenADMETTransformationProjectionError("output receipt mismatch")
    for name, expected in sorted(output_data.items()):
        actual = (stage / name).read_bytes()
        if actual != expected:
            raise OpenADMETTransformationProjectionError(
                f"staged {name} bytes differ before publication"
            )
        if name == "manifest.json":
            parsed = strict_json_object(actual, "staged manifest")
            if parsed != dict(manifest):
                raise OpenADMETTransformationProjectionError("staged manifest mismatch")
        else:
            columns = tuple(_output_receipts(output_data)[name]["columns"])
            _csv_row_count(actual, columns, f"staged {name}")


def _csv_row_count(data: bytes, columns: Sequence[str], label: str) -> int:
    if not data.endswith(b"\n") or b"\r" in data:
        raise OpenADMETTransformationProjectionError(f"{label} line-ending mismatch")
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True)
        if next(reader, None) != list(columns):
            raise OpenADMETTransformationProjectionError(f"{label} header mismatch")
        count = 0
        for values in reader:
            if len(values) != len(columns):
                raise OpenADMETTransformationProjectionError(
                    f"{label} field-count mismatch"
                )
            count += 1
        return count
    except (UnicodeError, csv.Error) as exc:
        raise OpenADMETTransformationProjectionError(f"cannot parse {label}") from exc


def _validate_structures(
    rows: Sequence[Mapping[str, str]],
) -> dict[str, dict[str, str]]:
    by_id: dict[str, dict[str, str]] = {}
    by_hash: dict[str, str] = {}
    for row in rows:
        molecule_id = _required(row, "molecule_id")
        if molecule_id in by_id:
            raise OpenADMETTransformationProjectionError(
                "duplicate structure molecule_id"
            )
        raw_smiles = _required(row, "raw_smiles")
        standardized = _required(row, "standardized_smiles")
        raw_hash = _digest(row, "raw_structure_sha256")
        standardized_hash = _digest(row, "standardized_structure_hash")
        _sha_id(
            _required(row, "similarity_component_hash"), "similarity_component_hash"
        )
        if raw_hash != sha256(raw_smiles.encode("utf-8")).hexdigest():
            raise OpenADMETTransformationProjectionError("raw structure hash mismatch")
        if standardized_hash != sha256(standardized.encode("utf-8")).hexdigest():
            raise OpenADMETTransformationProjectionError(
                "standardized structure hash mismatch"
            )
        prior = by_hash.get(standardized_hash)
        if prior is not None and prior != molecule_id:
            raise OpenADMETTransformationProjectionError(
                "distinct molecule identities share standardized structure hash"
            )
        by_hash[standardized_hash] = molecule_id
        by_id[molecule_id] = dict(row)
    if not by_id:
        raise OpenADMETTransformationProjectionError("structure projection is empty")
    return by_id


def _validate_direct(
    rows: Sequence[Mapping[str, str]], structures: Mapping[str, Mapping[str, str]]
) -> dict[str, set[str]]:
    seen_observations: set[str] = set()
    endpoints_by_molecule: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        observation_id = _required(row, "observation_id")
        _sha_id(observation_id, "observation_id")
        if observation_id in seen_observations:
            raise OpenADMETTransformationProjectionError("duplicate observation_id")
        seen_observations.add(observation_id)
        molecule_id = _required(row, "molecule_id")
        structure = structures.get(molecule_id)
        if structure is None:
            raise OpenADMETTransformationProjectionError(
                "direct molecule missing from structure projection"
            )
        endpoint = _required(row, "endpoint")
        if endpoint not in ENDPOINTS or endpoint in endpoints_by_molecule[molecule_id]:
            raise OpenADMETTransformationProjectionError(
                "direct endpoint identity mismatch"
            )
        endpoints_by_molecule[molecule_id].add(endpoint)
        if _digest(row, "raw_structure_sha256") != structure["raw_structure_sha256"]:
            raise OpenADMETTransformationProjectionError(
                "direct raw structure join mismatch"
            )
        if (
            _digest(row, "standardized_structure_hash")
            != structure["standardized_structure_hash"]
        ):
            raise OpenADMETTransformationProjectionError(
                "direct standardized structure join mismatch"
            )
        _sha_id(row["similarity_component_hash"], "similarity_component_hash")
        if row["similarity_component_hash"] != structure["similarity_component_hash"]:
            raise OpenADMETTransformationProjectionError(
                "direct component join mismatch"
            )
        if row["value_state"] not in VALUE_STATES:
            raise OpenADMETTransformationProjectionError("direct value state mismatch")
    for molecule_id, endpoints in endpoints_by_molecule.items():
        if endpoints != set(ENDPOINTS):
            raise OpenADMETTransformationProjectionError(
                f"direct endpoint cardinality mismatch for {molecule_id}"
            )
    return endpoints_by_molecule


def _validate_folds(
    rows: Sequence[Mapping[str, str]], structures: Mapping[str, Mapping[str, str]]
) -> dict[tuple[str, int, int], int]:
    seen: set[tuple[str, str, str, str, str]] = set()
    by_molecule: dict[str, set[tuple[int, int]]] = defaultdict(set)
    component_by_repeat: dict[tuple[str, int], str] = {}
    outer_by_component_repeat: dict[tuple[str, int], int] = {}
    inner_by_component_repeat_validation: dict[tuple[str, int, int], int | str] = {}
    seen_cells: set[tuple[str, int, int]] = set()
    fold_index: dict[tuple[str, int, int], int] = {}
    for row in rows:
        molecule_id = _required(row, "molecule_id")
        structure = structures.get(molecule_id)
        if structure is None:
            raise OpenADMETTransformationProjectionError(
                "fold molecule missing from structure"
            )
        if row["similarity_component_hash"] != structure["similarity_component_hash"]:
            raise OpenADMETTransformationProjectionError("fold component join mismatch")
        repeat = _int(row["repeat"], "repeat")
        outer = _int(row["outer_fold"], "outer_fold")
        validation = _int(row["outer_validation_fold"], "outer_validation_fold")
        if (
            repeat not in range(3)
            or outer not in range(5)
            or validation not in range(5)
        ):
            raise OpenADMETTransformationProjectionError("fold index out of range")
        if _int(row["seed"], "seed") != EXPECTED_SEEDS[repeat]:
            raise OpenADMETTransformationProjectionError("fold seed mismatch")
        inner = _int_or_blank(row["inner_fold"], "inner_fold")
        if outer == validation:
            if inner != "":
                raise OpenADMETTransformationProjectionError(
                    "held-out fold must have blank inner fold"
                )
        elif not isinstance(inner, int) or inner not in range(4):
            raise OpenADMETTransformationProjectionError(
                "training fold must have inner fold in 0..3"
            )
        component = structure["similarity_component_hash"]
        _sha_id(component, "fold similarity_component_hash")
        prior_component = component_by_repeat.get((molecule_id, repeat))
        if prior_component is not None and prior_component != component:
            raise OpenADMETTransformationProjectionError("fold component instability")
        component_by_repeat[(molecule_id, repeat)] = component
        component_key = (component, repeat)
        prior_outer = outer_by_component_repeat.get(component_key)
        if prior_outer is not None and prior_outer != outer:
            raise OpenADMETTransformationProjectionError(
                "component fold assignment instability"
            )
        outer_by_component_repeat[component_key] = outer
        inner_key = (component, repeat, validation)
        prior_inner = inner_by_component_repeat_validation.get(inner_key)
        if prior_inner is not None and prior_inner != inner:
            raise OpenADMETTransformationProjectionError(
                "component inner-fold assignment instability"
            )
        inner_by_component_repeat_validation[inner_key] = inner
        cell_key = (molecule_id, repeat, validation)
        if cell_key in seen_cells:
            raise OpenADMETTransformationProjectionError("duplicate fold matrix cell")
        seen_cells.add(cell_key)
        fold_index[cell_key] = outer
        by_molecule[molecule_id].add((repeat, validation))
        key = (molecule_id, str(repeat), str(outer), str(validation), str(inner))
        if key in seen:
            raise OpenADMETTransformationProjectionError("duplicate fold row")
        seen.add(key)
    if not rows:
        raise OpenADMETTransformationProjectionError("fold projection is empty")
    expected_matrix = {
        (repeat, validation) for repeat in range(3) for validation in range(5)
    }
    if set(by_molecule) != set(structures) or any(
        cells != expected_matrix for cells in by_molecule.values()
    ):
        raise OpenADMETTransformationProjectionError(
            "fold matrix/molecule membership mismatch"
        )
    return fold_index


def _validate_public(
    rows: Sequence[Mapping[str, str]],
    structures: Mapping[str, Mapping[str, str]],
    fold_index: Mapping[tuple[str, int, int], int],
) -> dict[str, dict[str, str]]:
    by_episode: dict[str, dict[str, str]] = {}
    for row in rows:
        episode_id = _required(row, "episode_id")
        _sha_id(episode_id, "episode_id")
        if episode_id in by_episode:
            raise OpenADMETTransformationProjectionError("duplicate public episode_id")
        if row["protocol"] != EXPECTED_PROTOCOL:
            raise OpenADMETTransformationProjectionError("public protocol mismatch")
        repeat = _int(row["repeat"], "repeat")
        outer_fold = _int(row["outer_fold"], "outer_fold")
        if repeat not in range(3) or outer_fold not in range(5):
            raise OpenADMETTransformationProjectionError(
                "public fold index out of range"
            )
        outer_group = _required(row, "outer_group_id")
        _sha_id(outer_group, "outer_group_id")
        queries = _query_ids(row["query_molecule_ids"], "query molecule IDs")
        if not queries:
            raise OpenADMETTransformationProjectionError("public query list is empty")
        if any(query not in structures for query in queries):
            raise OpenADMETTransformationProjectionError(
                "public query missing from structure"
            )
        if row["candidate_pool_id"] != EXPECTED_CANDIDATE_POOL:
            raise OpenADMETTransformationProjectionError(
                "public candidate pool mismatch"
            )
        if row["episode_policy_id"] not in EXPECTED_POLICIES:
            raise OpenADMETTransformationProjectionError(
                "public episode policy mismatch"
            )
        canonical_queries = json.dumps(
            queries, ensure_ascii=False, separators=(",", ":")
        )
        if row["query_molecule_ids"] != canonical_queries:
            raise OpenADMETTransformationProjectionError(
                "public query JSON is not canonical"
            )
        components = {
            structures[query]["similarity_component_hash"] for query in queries
        }
        if components != {outer_group}:
            raise OpenADMETTransformationProjectionError(
                "public query/component join mismatch"
            )
        for query in queries:
            if fold_index.get((query, repeat, outer_fold)) != outer_fold:
                raise OpenADMETTransformationProjectionError(
                    "public query/component fold assignment mismatch"
                )
        by_episode[episode_id] = dict(row)
    if not by_episode:
        raise OpenADMETTransformationProjectionError("public projection is empty")
    return by_episode


def _validate_masks(
    rows: Sequence[Mapping[str, str]],
    public: Mapping[str, Mapping[str, str]],
    structures: Mapping[str, Mapping[str, str]],
    fold_index: Mapping[tuple[str, int, int], int],
) -> None:
    seen: set[str] = set()
    for row in rows:
        episode_id = _required(row, "episode_id")
        if episode_id in seen or episode_id not in public:
            raise OpenADMETTransformationProjectionError(
                "mask/public episode join mismatch"
            )
        seen.add(episode_id)
        anchor = _required(row, "anchor_molecule_id_truth")
        structure = structures.get(anchor)
        if structure is None:
            raise OpenADMETTransformationProjectionError(
                "mask anchor missing from structure"
            )
        public_row = public[episode_id]
        queries = _query_ids(public_row["query_molecule_ids"], "query molecule IDs")
        if anchor in queries:
            raise OpenADMETTransformationProjectionError(
                "mask anchor occurs in query list"
            )
        if structure["similarity_component_hash"] != public_row["outer_group_id"]:
            raise OpenADMETTransformationProjectionError(
                "mask anchor/component join mismatch"
            )
        repeat = _int(public_row["repeat"], "repeat")
        outer_fold = _int(public_row["outer_fold"], "outer_fold")
        if fold_index.get((anchor, repeat, outer_fold)) != outer_fold:
            raise OpenADMETTransformationProjectionError(
                "mask anchor/component fold assignment mismatch"
            )
    if set(public) != seen:
        raise OpenADMETTransformationProjectionError(
            "public/mask episode membership mismatch"
        )


def _query_ids(value: str, label: str) -> list[str]:
    parsed = strict_json_cell(value, label)
    if not isinstance(parsed, list) or any(
        not isinstance(item, str) or not item for item in parsed
    ):
        raise OpenADMETTransformationProjectionError(
            f"{label} must be a non-empty string list"
        )
    if len(parsed) != len(set(parsed)):
        raise OpenADMETTransformationProjectionError(f"{label} contains duplicates")
    return list(parsed)


def _check_destination(path: Path) -> None:
    if ".." in path.parts:
        raise OpenADMETTransformationProjectionError("output path contains traversal")
    if path.exists() or path.is_symlink():
        raise OpenADMETTransformationProjectionError(
            "output path already exists; refusing overwrite"
        )
    _safe_output_parent(path)


def _safe_output_parent(path: Path) -> Path:
    parent = path.parent
    if ".." in parent.parts:
        raise OpenADMETTransformationProjectionError("output parent contains traversal")
    current = parent
    while True:
        if current.is_symlink():
            raise OpenADMETTransformationProjectionError(
                "output parent contains symlink"
            )
        if current == current.parent:
            break
        current = current.parent
    parent.mkdir(parents=True, exist_ok=True)
    return parent


def _write_new(path: Path, data: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise OpenADMETTransformationProjectionError("staged output overwrite")
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise OpenADMETTransformationProjectionError(f"cannot write {path}") from exc


def _readonly_tree(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            raise OpenADMETTransformationProjectionError(
                "staged output contains symlink"
            )
        if path.is_file():
            path.chmod(0o444)
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_dir():
            path.chmod(0o555)
    root.chmod(0o555)


def _rename_noreplace(source: Path, destination: Path) -> None:
    if platform.system() != "Linux" or os.name != "posix":
        raise OpenADMETTransformationProjectionError("atomic no-replace requires Linux")
    try:
        renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
    except (AttributeError, OSError) as exc:
        raise OpenADMETTransformationProjectionError("renameat2 unavailable") from exc
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        -100,
        os.fsencode(os.path.abspath(source)),
        -100,
        os.fsencode(os.path.abspath(destination)),
        1,
    )
    if result != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise OpenADMETTransformationProjectionError(
                "output path already exists; refusing overwrite"
            )
        raise OpenADMETTransformationProjectionError(
            f"atomic promotion failed: {os.strerror(error)}"
        )


def _cleanup_stage(stage: Path | None) -> None:
    if stage is None or not stage.exists():
        return
    try:
        stage.chmod(0o755)
    except OSError as exc:
        raise OpenADMETTransformationProjectionError(
            "cannot make staging root writable for cleanup"
        ) from exc
    for path in sorted(
        stage.rglob("*"), key=lambda item: len(item.parts), reverse=True
    ):
        try:
            if path.is_file():
                path.chmod(0o644)
            elif path.is_dir():
                path.chmod(0o755)
        except OSError:
            pass
    try:
        shutil.rmtree(stage)
    except OSError as exc:
        raise OpenADMETTransformationProjectionError("staging cleanup failed") from exc
    if stage.exists():
        raise OpenADMETTransformationProjectionError("staging cleanup incomplete")


def _required(row: Mapping[str, str], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise OpenADMETTransformationProjectionError(f"{key} must be non-empty")
    return value


def _digest(row: Mapping[str, str], key: str) -> str:
    value = _required(row, key)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise OpenADMETTransformationProjectionError(f"{key} must be lowercase SHA-256")
    return value


def _sha_id(value: str, label: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise OpenADMETTransformationProjectionError(
            f"{label} must be lowercase SHA-256"
        )
    return value


def _int(value: str, label: str) -> int:
    if not value or not value.isdigit() or (len(value) > 1 and value.startswith("0")):
        raise OpenADMETTransformationProjectionError(f"{label} must be an integer")
    return int(value)


def _int_or_blank(value: str, label: str) -> int | str:
    if value == "":
        return ""
    return _int(value, label)


def _inner_sort(value: str) -> int:
    result = _int_or_blank(value, "inner_fold")
    if isinstance(result, str):
        return -1
    return result


__all__ = [
    "FOLD_PROJECTION_COLUMNS",
    "OUTPUT_FILES",
    "PROJECTION_SCHEMA_VERSION",
    "OpenADMETTransformationProjectionError",
    "TransformationProjectionResult",
    "project_openadmet_transformation_inputs",
    "validate_r4_joins",
]

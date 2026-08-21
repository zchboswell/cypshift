"""Label-safe preflight evidence compiler for the R5C oracle run.

The compiler authenticates the accepted R5B source bundle and derives only
hashed identities, fold coordinates, state flags, and structural-control
availability.  Numeric target strings remain opaque and are never converted.
"""

from __future__ import annotations

import io
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Final

import numpy as np

from cypshift.chemistry import audit_molecules
from cypshift.openadmet_oracle_controls import (
    ControlMolecule,
    ControlQuery,
    valid_on_demand_anchors,
)
from cypshift.openadmet_oracle_inner_io import EXPECTED_RUNTIME
from cypshift.openadmet_oracle_private_io import (
    OraclePrivateIOError,
    publish_readonly_tree,
    read_exact_root,
)
from cypshift.openadmet_oracle_projection import (
    DENIED_AUTHORITY,
    SOURCE_FILES,
    _validate_manifest_leaf_receipts,
    _validate_source_manifest,
)
from cypshift.openadmet_oracle_sealed import RESOLVED_CONTRACT_SHA256
from cypshift.openadmet_oracle_terminal_receipts import (
    SUPPORT_EVIDENCE_SCHEMA,
    SUPPORT_EVIDENCE_STATUS,
    receipt_source_bundle_sha256,
)
from cypshift.openadmet_oracle_validation import SOURCE_COLUMNS, csv_rows
from cypshift.openadmet_transformations import extract_transformation_pair
from cypshift.schema import MoleculeInput, MoleculeRecord

ROOT: Final = Path(__file__).resolve().parents[2]
VALID_STATUSES: Final = frozenset({"VALID_SINGLE", "VALID_DOUBLE"})


class OracleSupportError(ValueError):
    """Support evidence could not be derived at the label-safe boundary."""


@dataclass(frozen=True, slots=True)
class SupportSourceInput:
    """An independently receipt-bound accepted source bundle."""

    root: Path
    expected_receipts: Mapping[str, str]


def compile_support_evidence(source: SupportSourceInput, output_root: Path) -> str:
    """Derive and atomically publish the exact label-safe support evidence."""

    loaded = _load_source(source)
    rows = {
        name: csv_rows(loaded[name], SOURCE_COLUMNS[name], name)
        for name in SOURCE_COLUMNS
    }
    primary, selected = _primary_rows(rows)
    outer_training, inner_training = _training_rows(rows["training_pairs.csv"])
    controls = _control_rows(loaded, rows, selected)
    evidence = {
        "primary_rows": primary,
        "outer_training_rows": outer_training,
        "inner_training_rows": inner_training,
        "control_local_rows": controls,
    }
    evidence_data = _compact(evidence)
    source_sha256 = receipt_source_bundle_sha256()
    manifest = {
        "schema_version": SUPPORT_EVIDENCE_SCHEMA,
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "status": SUPPORT_EVIDENCE_STATUS,
        "source_sha256": source_sha256,
        "runtime": EXPECTED_RUNTIME,
        "output_receipts": {
            "evidence.json": {
                "relative_path": "evidence.json",
                "sha256": sha256(evidence_data).hexdigest(),
                "bytes": len(evidence_data),
            }
        },
        "operation_accounting": _zero_accounting(),
        "authority": DENIED_AUTHORITY,
    }
    manifest_data = _compact(manifest)
    try:
        publish_readonly_tree(
            output_root,
            {"manifest.json": manifest_data, "evidence.json": evidence_data},
        )
    except OraclePrivateIOError as exc:
        raise OracleSupportError(str(exc)) from exc
    return sha256(manifest_data).hexdigest()


def _load_source(source: SupportSourceInput) -> dict[str, bytes]:
    names = (*SOURCE_FILES, "manifest.json")
    expected = dict(source.expected_receipts)
    if set(expected) != set(names):
        raise OracleSupportError("source receipt set differs")
    try:
        payloads = read_exact_root(source.root, names)
    except OraclePrivateIOError as exc:
        raise OracleSupportError(str(exc)) from exc
    for name, data in payloads.items():
        digest = expected[name]
        _digest(digest, f"source receipt: {name}")
        if sha256(data).hexdigest() != digest:
            raise OracleSupportError(f"source receipt differs: {name}")
    try:
        manifest = _validate_source_manifest(payloads["manifest.json"], expected)
        leaves = {name: payloads[name] for name in SOURCE_FILES}
        _validate_manifest_leaf_receipts(manifest, leaves, expected)
    except ValueError as exc:
        raise OracleSupportError(str(exc)) from exc
    return {name: payloads[name] for name in SOURCE_FILES}


def _primary_rows(
    rows: Mapping[str, Sequence[Mapping[str, str]]],
) -> tuple[list[dict[str, Any]], tuple[Mapping[str, str], ...]]:
    public = rows["public_episode_queries.csv"]
    truth = {
        (
            *_scoped_episode(row),
            row["query_molecule_id"],
        ): row
        for row in rows["episode_truth.csv"]
        if row["stage"] == "outer"
    }
    anchors = {
        _scoped_episode(row): row
        for row in rows["episode_anchor_contexts.csv"]
        if row["stage"] == "outer"
    }
    geometry = {
        (row["episode_id"], row["query_molecule_id"], row["query_rank"]): row
        for row in rows["episode_transformations.csv"]
    }
    selected: list[Mapping[str, str]] = []
    output: list[dict[str, Any]] = []
    for row in public:
        if row["episode_policy_id"] != "selected_anchor":
            continue
        scope = (int(row["repeat"]), int(row["outer_fold"]), row["episode_id"])
        truth_row = truth.get((*scope, row["query_molecule_id"]))
        anchor_row = anchors.get(scope)
        geometry_row = geometry.get(
            (row["episode_id"], row["query_molecule_id"], row["query_rank"])
        )
        if truth_row is None or anchor_row is None or geometry_row is None:
            raise OracleSupportError("primary support join differs")
        if (
            truth_row["query_molecule_id"] == row["query_molecule_id"]
            and truth_row["selector_cyp_truth"] == "CYP3A4"
            and truth_row["query_point_available"] == "true"
            and anchor_row["anchor_molecule_id"] == row["anchor_molecule_id"]
            and anchor_row["anchor_point_available"] == "true"
            and geometry_row["extraction_status"] in VALID_STATUSES
        ):
            base_id = _base_episode_query_id(row)
            output.append(
                {
                    "base_episode_query_id": base_id,
                    "component_id": row["outer_group_id"],
                    "repeat": int(row["repeat"]),
                    "outer_fold": int(row["outer_fold"]),
                }
            )
            selected.append(row)
    return _sorted_unique(output), tuple(selected)


def _training_rows(
    rows: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    outer: list[dict[str, Any]] = []
    inner: list[dict[str, Any]] = []
    for row in rows:
        record: dict[str, Any] = {
            "component_id": row["component_id"],
            "unordered_pair_id": row["pair_id"],
            "repeat": int(row["repeat"]),
            "outer_fold": int(row["outer_fold"]),
        }
        if row["stage"] == "outer":
            outer.append(record)
        else:
            record["inner_fold"] = int(row["inner_fold"])
            inner.append(record)
    return _sorted_unique(outer), _sorted_unique(inner)


def _control_rows(
    loaded: Mapping[str, bytes],
    rows: Mapping[str, Sequence[Mapping[str, str]]],
    selected: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    molecules = _records(rows["molecules.csv"])
    bits = _morgan_bits(loaded["morgan_binary.npy"], tuple(molecules))
    point_rows: dict[tuple[int, int], list[Mapping[str, str]]] = {}
    for row in rows["training_points.csv"]:
        if row["stage"] == "outer":
            point_rows.setdefault(
                (int(row["repeat"]), int(row["outer_fold"])), []
            ).append(row)
    output: list[dict[str, Any]] = []
    for row in selected:
        scope = (int(row["repeat"]), int(row["outer_fold"]))
        candidates = tuple(
            ControlMolecule(
                molecules[item["molecule_id"]],
                item["component_id"],
                0.0,
                bits[item["molecule_id"]],
            )
            for item in point_rows.get(scope, ())
        )
        query = ControlQuery(
            row["episode_id"],
            molecules[row["query_molecule_id"]],
            row["outer_group_id"],
            bits[row["query_molecule_id"]],
        )
        valid = valid_on_demand_anchors(
            query, candidates, extractor=extract_transformation_pair
        )
        if valid:
            base_id = _base_episode_query_id(row)
            for system_id in ("F0", "F1"):
                output.append(
                    {
                        "system_id": system_id,
                        "base_episode_query_id": base_id,
                        "component_id": row["outer_group_id"],
                    }
                )
    return _sorted_unique(output)


def _records(rows: Sequence[Mapping[str, str]]) -> dict[str, MoleculeRecord]:
    records = audit_molecules(
        [
            MoleculeInput(row["molecule_id"], row["raw_smiles"], "smiles", "r5c", "r5c")
            for row in rows
        ]
    )
    result = {record.molecule_id: record for record in records}
    if set(result) != {row["molecule_id"] for row in rows}:
        raise OracleSupportError("audited molecule identity differs")
    for row in rows:
        record = result[row["molecule_id"]]
        if (
            record.standardized_structure != row["standardized_smiles"]
            or record.standardized_structure_hash != row["standardized_structure_hash"]
        ):
            raise OracleSupportError("audited chemistry differs")
    return result


def _morgan_bits(
    data: bytes, molecule_ids: tuple[str, ...]
) -> dict[str, tuple[int, ...]]:
    try:
        array = np.load(io.BytesIO(data), allow_pickle=False)
    except (ValueError, OSError) as exc:
        raise OracleSupportError("Morgan array differs") from exc
    if array.shape != (len(molecule_ids), 4096) or array.dtype != np.dtype("uint8"):
        raise OracleSupportError("Morgan array shape differs")
    return {
        molecule_id: tuple(int(value) for value in array[index])
        for index, molecule_id in enumerate(molecule_ids)
    }


def _scoped_episode(row: Mapping[str, str]) -> tuple[int, int, str]:
    return int(row["repeat"]), int(row["outer_fold"]), row["episode_id"]


def _base_episode_query_id(row: Mapping[str, str]) -> str:
    return sha256(
        _compact(
            [
                row["outer_group_id"],
                row["anchor_molecule_id"],
                row["query_molecule_id"],
                int(row["query_rank"]),
            ]
        )
    ).hexdigest()


def _sorted_unique(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    keyed = {tuple(row.items()): row for row in rows}
    return [keyed[key] for key in sorted(keyed)]


def _zero_accounting() -> dict[str, int]:
    from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS

    return dict.fromkeys(ACCOUNTING_FIELDS, 0)


def _digest(value: str, label: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise OracleSupportError(f"{label} differs")


def _compact(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


__all__ = [
    "OracleSupportError",
    "SupportSourceInput",
    "compile_support_evidence",
]

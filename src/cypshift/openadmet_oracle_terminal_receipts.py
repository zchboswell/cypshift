"""Closed producers for label-safe support and DAG-accounting receipts."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

from cypshift.openadmet_oracle_inner_io import EXPECTED_RUNTIME
from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS
from cypshift.openadmet_oracle_private_io import (
    OraclePrivateIOError,
    open_directory_no_symlinks,
    publish_readonly_tree,
    read_exact_root,
    read_regular_at,
    read_stable_file,
    remove_private_root,
)
from cypshift.openadmet_oracle_projection import DENIED_AUTHORITY
from cypshift.openadmet_oracle_sealed import RESOLVED_CONTRACT_SHA256
from cypshift.openadmet_transformation_io import strict_json_object

ROOT: Final = Path(__file__).resolve().parents[2]
SUPPORT_SCHEMA: Final = "cypshift.openadmet_cyp_2026.r5c_oracle_prefit_support.v1"
ACCOUNTING_SCHEMA: Final = "cypshift.openadmet_cyp_2026.r5c_oracle_dag_accounting.v1"
SUPPORT_STATUS: Final = "R5_ORACLE_PREFLIGHT_SUPPORT_COMPLETE"
ACCOUNTING_STATUS: Final = "R5_ORACLE_DAG_ACCOUNTING_COMPLETE"
SUPPORT_EVIDENCE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.r5c_oracle_prefit_support_evidence.v1"
)
SUPPORT_EVIDENCE_STATUS: Final = "R5_ORACLE_PREFLIGHT_SUPPORT_EVIDENCE_COMPLETE"
SUPPORT_AUTHORITY: Final = {**DENIED_AUTHORITY, "oracle_evidence": True}
RECEIPT_SOURCE_FILES: Final = (
    "src/cypshift/openadmet_oracle_pair_cell_io.py",
    "src/cypshift/openadmet_oracle_private_io.py",
    "src/cypshift/openadmet_oracle_terminal_receipts.py",
    "src/cypshift/openadmet_transformation_support.py",
    "src/cypshift/openadmet_oracle_validation.py",
)


class OracleTerminalReceiptError(ValueError):
    """A support/accounting receipt cannot be produced exactly."""


@dataclass(frozen=True, slots=True)
class SupportEvidenceInput:
    root: Path
    expected_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class ChildManifestInput:
    label: str
    root: Path
    expected_manifest_sha256: str


def receipt_source_bundle_sha256() -> str:
    receipts = {
        name: sha256(read_stable_file(ROOT / name)).hexdigest()
        for name in RECEIPT_SOURCE_FILES
    }
    material = "".join(f"{name}|{receipts[name]}\n" for name in sorted(receipts))
    return sha256(material.encode()).hexdigest()


def publish_support_receipt(
    output_root: Path,
    *,
    evidence: SupportEvidenceInput,
) -> str:
    evidence_manifest_sha256, rows = _load_support_evidence(evidence)
    support, criteria = _derive_support(rows)
    support_status = "SUPPORTED" if all(criteria.values()) else "UNDERPOWERED"
    source = receipt_source_bundle_sha256()
    record = {
        "schema_version": SUPPORT_SCHEMA,
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "status": SUPPORT_STATUS,
        "support_status": support_status,
        "support": dict(support),
        "criteria": dict(criteria),
        "parent_receipts": {
            "support_evidence_manifest_sha256": evidence_manifest_sha256
        },
        "source_sha256": source,
        "runtime": EXPECTED_RUNTIME,
        "operation_accounting": dict.fromkeys(ACCOUNTING_FIELDS, 0),
        "authority": SUPPORT_AUTHORITY,
    }
    data = _compact(record)
    remove_private_root(evidence.root)
    publish_readonly_tree(output_root, {"support.json": data})
    return sha256(data).hexdigest()


def publish_accounting_receipt(
    output_root: Path,
    children: Sequence[ChildManifestInput],
) -> str:
    ordered = tuple(children)
    if (
        not ordered
        or tuple(sorted(item.label for item in ordered))
        != tuple(item.label for item in ordered)
        or len({item.label for item in ordered}) != len(ordered)
    ):
        raise OracleTerminalReceiptError("accounting child order differs")
    total = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    records: list[dict[str, Any]] = []
    for child in ordered:
        _label(child.label)
        _digest(child.expected_manifest_sha256)
        delta = _load_child_accounting(child)
        for name in ACCOUNTING_FIELDS:
            total[name] += delta[name]
        records.append(
            {
                "label": child.label,
                "sha256": child.expected_manifest_sha256,
                "operation_accounting": delta,
            }
        )
    record = {
        "schema_version": ACCOUNTING_SCHEMA,
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "status": ACCOUNTING_STATUS,
        "children": records,
        "source_sha256": receipt_source_bundle_sha256(),
        "runtime": EXPECTED_RUNTIME,
        "operation_accounting": total,
        "authority": DENIED_AUTHORITY,
    }
    data = _compact(record)
    publish_readonly_tree(output_root, {"accounting.json": data})
    return sha256(data).hexdigest()


def load_child_manifest_accounting(source: ChildManifestInput) -> dict[str, int]:
    """Reopen one independently receipt-bound child and derive its exact delta."""

    _label(source.label)
    _digest(source.expected_manifest_sha256)
    return _load_child_accounting(source)


def _load_support_evidence(
    source: SupportEvidenceInput,
) -> tuple[str, Mapping[str, Any]]:
    _digest(source.expected_manifest_sha256)
    try:
        payloads = read_exact_root(source.root, ("manifest.json", "evidence.json"))
    except OraclePrivateIOError as exc:
        raise OracleTerminalReceiptError(str(exc)) from exc
    manifest_data = payloads["manifest.json"]
    evidence_data = payloads["evidence.json"]
    if sha256(manifest_data).hexdigest() != source.expected_manifest_sha256:
        raise OracleTerminalReceiptError("support evidence manifest receipt differs")
    manifest = _canonical(manifest_data, "support evidence manifest")
    evidence = _canonical(evidence_data, "support evidence")
    expected_manifest = {
        "schema_version": SUPPORT_EVIDENCE_SCHEMA,
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "status": SUPPORT_EVIDENCE_STATUS,
        "source_sha256": receipt_source_bundle_sha256(),
        "runtime": EXPECTED_RUNTIME,
        "output_receipts": {
            "evidence.json": {
                "relative_path": "evidence.json",
                "sha256": sha256(evidence_data).hexdigest(),
                "bytes": len(evidence_data),
            }
        },
        "operation_accounting": dict.fromkeys(ACCOUNTING_FIELDS, 0),
        "authority": DENIED_AUTHORITY,
    }
    if manifest != expected_manifest:
        raise OracleTerminalReceiptError("support evidence binding differs")
    return source.expected_manifest_sha256, evidence


def _derive_support(
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, bool]]:
    fields = {
        "primary_rows",
        "outer_training_rows",
        "inner_training_rows",
        "control_local_rows",
    }
    if set(evidence) != fields:
        raise OracleTerminalReceiptError("support evidence fields differ")
    primary = _records(
        evidence["primary_rows"],
        ("base_episode_query_id", "component_id", "repeat", "outer_fold"),
    )
    outer_training = _records(
        evidence["outer_training_rows"],
        ("component_id", "unordered_pair_id", "repeat", "outer_fold"),
    )
    inner_training = _records(
        evidence["inner_training_rows"],
        (
            "component_id",
            "unordered_pair_id",
            "repeat",
            "outer_fold",
            "inner_fold",
        ),
    )
    controls = _records(
        evidence["control_local_rows"],
        ("system_id", "base_episode_query_id", "component_id"),
    )
    outer_keys = [(repeat, outer) for repeat in range(3) for outer in range(5)]
    inner_keys = [(*key, inner) for key in outer_keys for inner in range(4)]
    outer_cells = {
        f"repeat-{repeat}/outer-{outer}": _counts(
            primary,
            scope=(repeat, outer),
            scope_fields=("repeat", "outer_fold"),
            family="component_id",
            item="base_episode_query_id",
        )
        for repeat, outer in outer_keys
    }
    outer_training_counts = {
        f"repeat-{repeat}/outer-{outer}": _counts(
            outer_training,
            scope=(repeat, outer),
            scope_fields=("repeat", "outer_fold"),
            family="component_id",
            item="unordered_pair_id",
        )
        for repeat, outer in outer_keys
    }
    inner_training_counts = {
        f"repeat-{repeat}/outer-{outer}/inner-{inner}": _counts(
            inner_training,
            scope=(repeat, outer, inner),
            scope_fields=("repeat", "outer_fold", "inner_fold"),
            family="component_id",
            item="unordered_pair_id",
        )
        for repeat, outer, inner in inner_keys
    }
    control_counts = {
        system: _counts(
            controls,
            scope=(system,),
            scope_fields=("system_id",),
            family="component_id",
            item="base_episode_query_id",
        )
        for system in ("F0", "F1")
    }
    if {row["system_id"] for row in controls} != {"F0", "F1"}:
        raise OracleTerminalReceiptError("support control system differs")
    support: dict[str, Any] = {
        "unique_primary_components": len({row["component_id"] for row in primary}),
        "unique_primary_episode_query_pairs": len(
            {row["base_episode_query_id"] for row in primary}
        ),
        "outer_cell_support": outer_cells,
        "outer_training_support": outer_training_counts,
        "inner_training_support": inner_training_counts,
        "control_local_support": control_counts,
    }
    criteria = {
        "unique_primary_components_min_50": support["unique_primary_components"] >= 50,
        "unique_primary_episode_query_pairs_min_100": support[
            "unique_primary_episode_query_pairs"
        ]
        >= 100,
        "all_outer_cells_min_5_components_10_rows": all(
            row["families"] >= 5 and row["rows_or_pairs"] >= 10
            for row in outer_cells.values()
        ),
        "all_outer_training_min_50_families_200_pairs": all(
            row["families"] >= 50 and row["rows_or_pairs"] >= 200
            for row in outer_training_counts.values()
        ),
        "all_inner_training_min_40_families_150_pairs": all(
            row["families"] >= 40 and row["rows_or_pairs"] >= 150
            for row in inner_training_counts.values()
        ),
        "F0_min_30_families_50_rows": control_counts["F0"]["families"] >= 30
        and control_counts["F0"]["rows_or_pairs"] >= 50,
        "F1_min_30_families_50_rows": control_counts["F1"]["families"] >= 30
        and control_counts["F1"]["rows_or_pairs"] >= 50,
    }
    return support, criteria


def _records(value: Any, fields: tuple[str, ...]) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        raise OracleTerminalReceiptError("support evidence rows differ")
    result: list[dict[str, Any]] = []
    identities: list[tuple[Any, ...]] = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) != set(fields):
            raise OracleTerminalReceiptError("support evidence row differs")
        row = dict(item)
        for name in fields:
            observed = row[name]
            if name in {"repeat", "outer_fold", "inner_fold"}:
                limit = 3 if name == "repeat" else 5 if name == "outer_fold" else 4
                if type(observed) is not int or observed not in range(limit):
                    raise OracleTerminalReceiptError("support evidence scope differs")
            elif name == "system_id":
                if observed not in {"F0", "F1"}:
                    raise OracleTerminalReceiptError("support evidence system differs")
            else:
                _digest(observed)
        identity = tuple(row[name] for name in fields)
        identities.append(identity)
        result.append(row)
    if (
        not result
        or identities != sorted(identities)
        or len(set(identities)) != len(identities)
    ):
        raise OracleTerminalReceiptError("support evidence order differs")
    return tuple(result)


def _counts(
    rows: Sequence[Mapping[str, Any]],
    *,
    scope: tuple[Any, ...],
    scope_fields: tuple[str, ...],
    family: str,
    item: str,
) -> dict[str, int]:
    selected = tuple(
        row for row in rows if tuple(row[name] for name in scope_fields) == scope
    )
    return {
        "families": len({row[family] for row in selected}),
        "rows_or_pairs": len({row[item] for row in selected}),
    }


def _load_child_accounting(source: ChildManifestInput) -> dict[str, int]:
    root_fd = open_directory_no_symlinks(source.root)
    try:
        if os.fstat(root_fd).st_mode & 0o222:
            raise OracleTerminalReceiptError("accounting child root is writable")
        data = read_regular_at(root_fd, "manifest.json")
    except OraclePrivateIOError as exc:
        raise OracleTerminalReceiptError(str(exc)) from exc
    finally:
        os.close(root_fd)
    if sha256(data).hexdigest() != source.expected_manifest_sha256:
        raise OracleTerminalReceiptError("accounting child manifest receipt differs")
    manifest = _canonical(data, "accounting child manifest")
    if manifest.get("contract_sha256") != RESOLVED_CONTRACT_SHA256:
        raise OracleTerminalReceiptError("accounting child contract differs")
    accounting = manifest.get("operation_accounting")
    if not isinstance(accounting, Mapping):
        raise OracleTerminalReceiptError("accounting child accounting differs")
    return _accounting(accounting)


def _canonical(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = strict_json_object(data, label)
    except ValueError as exc:
        raise OracleTerminalReceiptError(str(exc)) from exc
    if data != _compact(value):
        raise OracleTerminalReceiptError(f"{label} is not canonical")
    return cast(dict[str, Any], value)


def _accounting(value: Mapping[str, int]) -> dict[str, int]:
    result = dict(value)
    if (
        set(result) != set(ACCOUNTING_FIELDS)
        or any(type(item) is not int or item < 0 for item in result.values())
        or any(result[name] for name in ACCOUNTING_FIELDS[8:])
    ):
        raise OracleTerminalReceiptError("child accounting differs")
    return result


def _label(value: str) -> None:
    if not value or any(not (char.isalnum() or char in "_.-") for char in value):
        raise OracleTerminalReceiptError("accounting child label differs")


def _digest(value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise OracleTerminalReceiptError("accounting child digest differs")


def _compact(value: Mapping[str, Any]) -> bytes:
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
    "ACCOUNTING_SCHEMA",
    "ACCOUNTING_STATUS",
    "ChildManifestInput",
    "OracleTerminalReceiptError",
    "RECEIPT_SOURCE_FILES",
    "SUPPORT_AUTHORITY",
    "SUPPORT_EVIDENCE_SCHEMA",
    "SUPPORT_EVIDENCE_STATUS",
    "SUPPORT_SCHEMA",
    "SUPPORT_STATUS",
    "SupportEvidenceInput",
    "publish_accounting_receipt",
    "publish_support_receipt",
    "load_child_manifest_accounting",
    "receipt_source_bundle_sha256",
]

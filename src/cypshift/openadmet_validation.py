"""Receipt-bound OpenADMET direct observations and label-free component folds."""

from __future__ import annotations

import csv
import io
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from rdkit import rdBase

from cypshift.audit import MOLECULE_INPUT_COLUMNS
from cypshift.chemistry import STANDARDIZATION_VERSION
from cypshift.openadmet_cyp import (
    OPENADMET_ADAPTER_SCHEMA_VERSION,
    SOURCE_ROW_COLUMNS,
)
from cypshift.openadmet_topology import (
    MOLECULE_AUDIT_COLUMNS,
    TOPOLOGY_COLUMNS,
    TOPOLOGY_SCHEMA_VERSION,
)
from cypshift.openadmet_validation_contract import (
    CONTRACT_SCHEMA_VERSION,
    DIRECT_SOURCE_FILE,
    ENDPOINTS,
    FOLD_POLICY_ID,
    INNER_SCOPE,
    OUTER_SCOPE,
    SEEDS,
    ValidationContractError,
    verify_r2a_contract,
)

R2A_SCHEMA_VERSION = "cypshift.openadmet_cyp_2026.validation_inputs.v1"
OBSERVATION_COLUMNS = (
    "observation_id",
    "molecule_id",
    "source_row_id",
    "source_file",
    "source_row",
    "source_sha256",
    "endpoint",
    "raw_smiles",
    "raw_point",
    "raw_low",
    "raw_high",
    "raw_std",
    "point",
    "low",
    "high",
    "std",
    "raw_structure_sha256",
    "standardized_structure_hash",
    "similarity_component_hash",
    "scaffold_group_hash",
    "value_state",
    "point_eligible",
    "anchor_eligible",
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


class OpenADMETValidationError(ValueError):
    """Unsafe or inconsistent R2A input."""


@dataclass(frozen=True, slots=True)
class ValidationInputResult:
    """Paths and counts for one completed R2A build."""

    observations_path: Path
    folds_path: Path
    manifest_path: Path
    observation_count: int
    molecule_count: int


def build_openadmet_validation_inputs(
    *,
    validation_contract_path: Path,
    direct_source_path: Path,
    r1_directory: Path,
    topology_directory: Path,
    output_directory: Path,
    source_revision: str,
) -> ValidationInputResult:
    """Build direct observations and label-independent component folds."""

    if output_directory.exists():
        raise OpenADMETValidationError(
            f"output path already exists: {output_directory}; refusing overwrite"
        )
    if not source_revision:
        raise OpenADMETValidationError("source_revision must not be empty")
    contract_data = _bytes(validation_contract_path, "validation contract")
    contract = _json_data(contract_data, "validation contract")
    try:
        verify_r2a_contract(contract, source_revision)
    except ValidationContractError as exc:
        raise OpenADMETValidationError(str(exc)) from exc
    if direct_source_path.name != DIRECT_SOURCE_FILE:
        raise OpenADMETValidationError("direct source filename mismatch")

    direct_receipt = _mapping(_mapping(contract, "input_chain"), "direct_source")
    direct_data = _bytes(direct_source_path, DIRECT_SOURCE_FILE)
    _match_hash(direct_data, _digest(direct_receipt, "sha256"), DIRECT_SOURCE_FILE)
    expected_direct_rows = _integer(direct_receipt, "rows")

    r1_manifest_path = r1_directory / "manifest.json"
    molecules_path = r1_directory / "molecules_input.csv"
    source_rows_path = r1_directory / "source_rows.csv"
    r1_receipt = _mapping(_mapping(contract, "input_chain"), "r1_source_row_adapter")
    r1_manifest_data = _bytes(r1_manifest_path, "R1 manifest")
    molecules_data = _bytes(molecules_path, "molecules_input.csv")
    source_rows_data = _bytes(source_rows_path, "source_rows.csv")
    _match_hash(r1_manifest_data, _digest(r1_receipt, "manifest_sha256"), "R1 manifest")
    _match_hash(
        molecules_data, _digest(r1_receipt, "molecules_sha256"), "molecules_input.csv"
    )
    _match_hash(
        source_rows_data, _digest(r1_receipt, "source_rows_sha256"), "source_rows.csv"
    )
    r1_manifest = _json_data(r1_manifest_data, "R1 manifest")
    if r1_manifest.get("schema_version") != OPENADMET_ADAPTER_SCHEMA_VERSION:
        raise OpenADMETValidationError("R1 manifest schema mismatch")
    if r1_manifest.get("source_revision") != source_revision:
        raise OpenADMETValidationError("R1 source revision mismatch")
    source_files = r1_manifest.get("source_files")
    if not isinstance(source_files, list):
        raise OpenADMETValidationError("R1 source file receipts are missing")
    direct_parent = next(
        (
            item
            for item in source_files
            if isinstance(item, dict) and item.get("path") == DIRECT_SOURCE_FILE
        ),
        None,
    )
    if not isinstance(direct_parent, dict):
        raise OpenADMETValidationError("R1 direct source receipt is missing")
    if (
        _digest(direct_parent, "sha256") != sha256(direct_data).hexdigest()
        or _integer(direct_parent, "rows") != expected_direct_rows
    ):
        raise OpenADMETValidationError("R1 direct source receipt mismatch")
    _verify_parent_output(
        r1_manifest,
        molecules_data,
        "molecules_input.csv",
        _digest(r1_receipt, "molecules_sha256"),
    )
    _verify_parent_output(
        r1_manifest,
        source_rows_data,
        "source_rows.csv",
        _digest(r1_receipt, "source_rows_sha256"),
    )

    topology_manifest_path = topology_directory / "topology_manifest.json"
    molecule_audit_path = topology_directory / "molecule_audit.csv"
    topology_path = topology_directory / "training_topology.csv"
    topology_receipt = _mapping(_mapping(contract, "input_chain"), "r1_topology")
    topology_manifest_data = _bytes(topology_manifest_path, "topology manifest")
    molecule_audit_data = _bytes(molecule_audit_path, "molecule_audit.csv")
    topology_data = _bytes(topology_path, "training_topology.csv")
    _match_hash(
        topology_manifest_data,
        _digest(topology_receipt, "manifest_sha256"),
        "topology manifest",
    )
    _match_hash(
        molecule_audit_data,
        _digest(topology_receipt, "molecule_audit_sha256"),
        "molecule_audit.csv",
    )
    _match_hash(
        topology_data,
        _digest(topology_receipt, "training_topology_sha256"),
        "training_topology.csv",
    )
    topology_manifest = _json_data(topology_manifest_data, "topology manifest")
    if topology_manifest.get("schema_version") != TOPOLOGY_SCHEMA_VERSION:
        raise OpenADMETValidationError("topology manifest schema mismatch")
    if topology_manifest.get("source_revision") != source_revision:
        raise OpenADMETValidationError("topology source revision mismatch")
    if _mapping(topology_manifest, "downstream_modeling").get("blocked") is not False:
        raise OpenADMETValidationError("topology blocks downstream validation")
    topology_inputs = _mapping(topology_manifest, "inputs")
    if (
        topology_inputs.get("r1_manifest_sha256")
        != sha256(r1_manifest_data).hexdigest()
    ):
        raise OpenADMETValidationError("topology/R1 manifest receipt mismatch")
    if (
        _mapping(topology_inputs, "molecules_input.csv").get("sha256")
        != sha256(molecules_data).hexdigest()
    ):
        raise OpenADMETValidationError("topology/R1 molecule receipt mismatch")
    if (
        _mapping(topology_inputs, "source_rows.csv").get("sha256")
        != sha256(source_rows_data).hexdigest()
    ):
        raise OpenADMETValidationError("topology/R1 source-row receipt mismatch")
    _verify_parent_output(
        topology_manifest,
        molecule_audit_data,
        "molecule_audit.csv",
        _digest(topology_receipt, "molecule_audit_sha256"),
    )
    _verify_parent_output(
        topology_manifest,
        topology_data,
        "training_topology.csv",
        _digest(topology_receipt, "training_topology_sha256"),
    )

    direct_rows = _csv(direct_data, _direct_header(), DIRECT_SOURCE_FILE)
    if len(direct_rows) != expected_direct_rows:
        raise OpenADMETValidationError("direct source row-count mismatch")
    molecules = _indexed_rows(
        _csv(molecules_data, MOLECULE_INPUT_COLUMNS, "molecules_input.csv"),
        "molecule_id",
        "molecules_input.csv",
    )
    source_rows = _direct_source_rows(source_rows_data)
    if len(source_rows) != len(direct_rows):
        raise OpenADMETValidationError("direct source-row receipt count mismatch")
    audits = _indexed_rows(
        _csv(molecule_audit_data, MOLECULE_AUDIT_COLUMNS, "molecule_audit.csv"),
        "molecule_id",
        "molecule_audit.csv",
    )
    topology = _indexed_rows(
        _csv(topology_data, TOPOLOGY_COLUMNS, "training_topology.csv"),
        "molecule_id",
        "training_topology.csv",
    )
    observations, direct_molecules = _observations(
        direct_rows,
        direct_data,
        source_revision,
        molecules,
        source_rows,
        audits,
        topology,
    )
    folds = _fold_rows(direct_molecules, topology)
    observation_bytes = _csv_bytes(OBSERVATION_COLUMNS, observations)
    fold_bytes = _csv_bytes(FOLD_COLUMNS, folds)
    states = Counter(row["value_state"] for row in observations)
    manifest = {
        "schema_version": R2A_SCHEMA_VERSION,
        "validation_contract": {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "sha256": sha256(contract_data).hexdigest(),
        },
        "source_revision": source_revision,
        "environment": {
            "rdkit_version": rdBase.rdkitVersion,
            "standardization_version": STANDARDIZATION_VERSION,
        },
        "inputs": {
            DIRECT_SOURCE_FILE: {
                "sha256": sha256(direct_data).hexdigest(),
                "rows": len(direct_rows),
            },
            "r1_manifest.json": {"sha256": sha256(r1_manifest_data).hexdigest()},
            "molecules_input.csv": {"sha256": sha256(molecules_data).hexdigest()},
            "source_rows.csv": {
                "sha256": sha256(source_rows_data).hexdigest(),
                "source_values_parsed": False,
            },
            "topology_manifest.json": {
                "sha256": sha256(topology_manifest_data).hexdigest()
            },
            "molecule_audit.csv": {"sha256": sha256(molecule_audit_data).hexdigest()},
            "training_topology.csv": {"sha256": sha256(topology_data).hexdigest()},
        },
        "policies": {
            "fold_policy_id": FOLD_POLICY_ID,
            "outer_scope": OUTER_SCOPE,
            "inner_scope": INNER_SCOPE,
            "seeds": list(SEEDS),
        },
        "counts": {
            "direct_source_rows": len(direct_rows),
            "direct_observations": len(observations),
            "direct_molecules": len(direct_molecules),
            "group_fold_rows": len(folds),
            "states": dict(sorted(states.items())),
        },
        "outputs": {
            "direct_observations.csv": {
                "sha256": sha256(observation_bytes).hexdigest(),
                "rows": len(observations),
            },
            "group_folds.csv": {
                "sha256": sha256(fold_bytes).hexdigest(),
                "rows": len(folds),
            },
        },
        "authority": {
            "validation": False,
            "fold_assignments": False,
            "episodes": False,
            "topology_viability": False,
            "models": False,
            "metrics": False,
            "tdi": False,
            "predictions": False,
            "submissions": False,
            "transduction": False,
        },
        "accounting": {
            "tdi_files_opened": 0,
            "blinded_test_files_opened": 0,
            "source_values_parsed": 0,
            "model_fits": 0,
            "predictions": 0,
            "metric_evaluations": 0,
            "submissions": 0,
        },
        "deterministic": True,
    }
    manifest_bytes = _json_bytes(manifest)
    output_directory.mkdir(parents=True)
    observation_path = output_directory / "direct_observations.csv"
    folds_path = output_directory / "group_folds.csv"
    manifest_path = output_directory / "manifest.json"
    _write(observation_path, observation_bytes)
    _write(folds_path, fold_bytes)
    _write(manifest_path, manifest_bytes)
    return ValidationInputResult(
        observation_path,
        folds_path,
        manifest_path,
        len(observations),
        len(direct_molecules),
    )


def _direct_header() -> tuple[str, ...]:
    return (
        "Molecule_Name",
        "SMILES",
        *(f"{endpoint}_pIC50_direct_inhibition" for endpoint in ENDPOINTS),
        *(f"{endpoint}_pIC50_direct_inhibition_conf_high" for endpoint in ENDPOINTS),
        *(f"{endpoint}_pIC50_direct_inhibition_conf_low" for endpoint in ENDPOINTS),
        *(f"{endpoint}_pIC50_direct_inhibition_std" for endpoint in ENDPOINTS),
    )


def _direct_source_rows(data: bytes) -> dict[str, dict[str, str]]:
    rows = _csv(data, SOURCE_ROW_COLUMNS, "source_rows.csv")
    selected = [row for row in rows if row["source_file"] == DIRECT_SOURCE_FILE]
    return _indexed_rows(selected, "source_row_id", "direct source-row receipts")


def _observations(
    rows: Sequence[Mapping[str, str]],
    direct_data: bytes,
    revision: str,
    molecules: Mapping[str, Mapping[str, str]],
    source_rows: Mapping[str, Mapping[str, str]],
    audits: Mapping[str, Mapping[str, str]],
    topology: Mapping[str, Mapping[str, str]],
) -> tuple[list[dict[str, str]], set[str]]:
    source_hash = sha256(direct_data).hexdigest()
    output: list[dict[str, str]] = []
    direct_molecules: set[str] = set()
    for source_row, row in enumerate(rows, start=2):
        molecule_id = row["Molecule_Name"]
        smiles = row["SMILES"]
        receipt_id = f"{DIRECT_SOURCE_FILE}:{source_row}"
        receipt = source_rows.get(receipt_id)
        molecule = molecules.get(molecule_id)
        audit = audits.get(molecule_id)
        group = topology.get(molecule_id)
        if receipt is None or molecule is None or audit is None or group is None:
            raise OpenADMETValidationError(f"missing identity receipt for {receipt_id}")
        if (
            receipt["Molecule_Name"] != molecule_id
            or receipt["SMILES"] != smiles
            or receipt["source_row"] != str(source_row)
            or molecule["structure"] != smiles
            or audit["raw_structure"] != smiles
            or audit["partition"] != "train"
            or audit["status"] != "accepted"
            or audit["standardization_version"] != STANDARDIZATION_VERSION
            or audit["raw_structure_sha256"] != sha256(smiles.encode()).hexdigest()
            or audit["standardized_structure_hash"]
            != group["standardized_structure_hash"]
            or receipt["partition"] != "train"
            or receipt["modality"] != "direct_inhibition"
        ):
            raise OpenADMETValidationError(
                f"identity or topology mismatch for {receipt_id}"
            )
        for key in (
            "standardized_structure_hash",
            "similarity_component_hash",
            "scaffold_group_hash",
        ):
            _require_digest_text(group[key], f"{key} for {molecule_id}")
        provenance = _json_text(molecule["provenance"], f"provenance for {molecule_id}")
        occurrences = provenance.get("occurrences")
        if not isinstance(occurrences, list) or not any(
            isinstance(item, dict)
            and item.get("source_file") == DIRECT_SOURCE_FILE
            and item.get("source_row") == source_row
            and item.get("source_sha256") == source_hash
            for item in occurrences
        ):
            raise OpenADMETValidationError(f"provenance mismatch for {receipt_id}")
        direct_molecules.add(molecule_id)
        for endpoint in ENDPOINTS:
            raw = {
                "point": row[f"{endpoint}_pIC50_direct_inhibition"],
                "high": row[f"{endpoint}_pIC50_direct_inhibition_conf_high"],
                "low": row[f"{endpoint}_pIC50_direct_inhibition_conf_low"],
                "std": row[f"{endpoint}_pIC50_direct_inhibition_std"],
            }
            parsed, state = _measurement(raw, receipt_id, endpoint)
            observation_id = sha256(
                f"{revision}|{DIRECT_SOURCE_FILE}|{source_row}|{endpoint}".encode()
            ).hexdigest()
            output.append(
                {
                    "observation_id": observation_id,
                    "molecule_id": molecule_id,
                    "source_row_id": receipt_id,
                    "source_file": DIRECT_SOURCE_FILE,
                    "source_row": str(source_row),
                    "source_sha256": source_hash,
                    "endpoint": endpoint,
                    "raw_smiles": smiles,
                    "raw_point": raw["point"],
                    "raw_low": raw["low"],
                    "raw_high": raw["high"],
                    "raw_std": raw["std"],
                    "point": parsed["point"],
                    "low": parsed["low"],
                    "high": parsed["high"],
                    "std": parsed["std"],
                    "raw_structure_sha256": audit["raw_structure_sha256"],
                    "standardized_structure_hash": group["standardized_structure_hash"],
                    "similarity_component_hash": group["similarity_component_hash"],
                    "scaffold_group_hash": group["scaffold_group_hash"],
                    "value_state": state,
                    "point_eligible": _boolean(bool(parsed["point"])),
                    "anchor_eligible": _boolean(state == "complete"),
                }
            )
    return output, direct_molecules


def _measurement(
    raw: Mapping[str, str], receipt_id: str, endpoint: str
) -> tuple[dict[str, str], str]:
    parsed: dict[str, str] = {}
    numbers: dict[str, float | None] = {}
    for name in ("point", "low", "high", "std"):
        text = raw[name]
        if text == "":
            numbers[name] = None
            parsed[name] = ""
            continue
        try:
            value = float(text)
        except ValueError as exc:
            raise OpenADMETValidationError(
                f"invalid {name} for {receipt_id} {endpoint}"
            ) from exc
        if not math.isfinite(value):
            raise OpenADMETValidationError(
                f"non-finite {name} for {receipt_id} {endpoint}"
            )
        numbers[name] = value
        parsed[name] = format(value, ".17g")
    point, low, high, std = (numbers[name] for name in ("point", "low", "high", "std"))
    if std is not None and std < 0:
        raise OpenADMETValidationError(f"negative std for {receipt_id} {endpoint}")
    if low is not None and high is not None and low > high:
        raise OpenADMETValidationError(f"reversed bounds for {receipt_id} {endpoint}")
    if point is not None and low is not None and low > point:
        raise OpenADMETValidationError(
            f"low bound excludes point for {receipt_id} {endpoint}"
        )
    if point is not None and high is not None and point > high:
        raise OpenADMETValidationError(
            f"high bound excludes point for {receipt_id} {endpoint}"
        )
    if all(numbers[name] is None for name in numbers):
        state = "missing"
    elif point is None:
        state = "orphan_auxiliary"
    elif all(numbers[name] is not None for name in numbers):
        state = "complete"
    else:
        state = "partial"
    return parsed, state


def _fold_rows(
    molecule_ids: set[str], topology: Mapping[str, Mapping[str, str]]
) -> list[dict[str, str]]:
    members: dict[str, list[str]] = defaultdict(list)
    for molecule_id in sorted(molecule_ids):
        group = topology[molecule_id]["similarity_component_hash"]
        members[group].append(molecule_id)
    weights = {group: len(values) for group, values in members.items()}
    rows: list[dict[str, str]] = []
    for repeat, seed in enumerate(SEEDS):
        outer = _balanced_folds(weights, seed, OUTER_SCOPE, 5)
        for validation_fold in range(5):
            training_weights = {
                group: weight
                for group, weight in weights.items()
                if outer[group] != validation_fold
            }
            inner = _balanced_folds(
                training_weights,
                seed,
                INNER_SCOPE.replace("<outer_fold>", str(validation_fold)),
                4,
            )
            for molecule_id in sorted(molecule_ids):
                group = topology[molecule_id]["similarity_component_hash"]
                rows.append(
                    {
                        "molecule_id": molecule_id,
                        "similarity_component_hash": group,
                        "repeat": str(repeat),
                        "seed": str(seed),
                        "outer_fold": str(outer[group]),
                        "outer_validation_fold": str(validation_fold),
                        "inner_fold": ""
                        if outer[group] == validation_fold
                        else str(inner[group]),
                    }
                )
    return rows


def _balanced_folds(
    weights: Mapping[str, int], seed: int, scope: str, fold_count: int
) -> dict[str, int]:
    ordered = sorted(
        weights,
        key=lambda group: (
            -weights[group],
            sha256(f"{seed}|{scope}|group-order-v1|{group}".encode()).hexdigest(),
            group,
        ),
    )
    counts = [0] * fold_count
    result: dict[str, int] = {}
    for group in ordered:
        fold = min(
            range(fold_count),
            key=lambda candidate: (
                counts[candidate],
                sha256(
                    f"{seed}|{scope}|fold-tie-v1|{group}|{candidate}".encode()
                ).hexdigest(),
                candidate,
            ),
        )
        result[group] = fold
        counts[fold] += weights[group]
    return result


def _verify_parent_output(
    manifest: Mapping[str, Any], data: bytes, name: str, contract_hash: str
) -> None:
    outputs = _mapping(manifest, "outputs")
    receipt = _mapping(outputs, name)
    manifest_hash = _digest(receipt, "sha256")
    if manifest_hash != contract_hash:
        raise OpenADMETValidationError(f"{name} contract/manifest hash mismatch")
    _match_hash(data, contract_hash, name)


def _require_digest_text(value: str, label: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise OpenADMETValidationError(f"{label} must be a SHA-256 digest")


def _match_hash(data: bytes, expected: str, label: str) -> None:
    if sha256(data).hexdigest() != expected:
        raise OpenADMETValidationError(f"{label} SHA-256 mismatch")


def _indexed_rows(
    rows: Sequence[dict[str, str]], key: str, label: str
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        identity = row[key]
        if not identity or identity in result:
            raise OpenADMETValidationError(f"empty or duplicate identity in {label}")
        result[identity] = row
    return result


def _csv(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""))
        header = next(reader, None)
        if header != list(columns):
            raise OpenADMETValidationError(f"{label} header mismatch")
        rows: list[dict[str, str]] = []
        for values in reader:
            if len(values) != len(columns):
                raise OpenADMETValidationError(f"{label} field-count mismatch")
            rows.append(dict(zip(columns, values, strict=True)))
        return rows
    except (UnicodeError, csv.Error) as exc:
        raise OpenADMETValidationError(f"cannot parse {label}: {exc}") from exc


def _mapping(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise OpenADMETValidationError(f"{key} must be an object")
    return cast(dict[str, Any], item)


def _digest(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if (
        not isinstance(item, str)
        or len(item) != 64
        or any(char not in "0123456789abcdef" for char in item)
    ):
        raise OpenADMETValidationError(f"{key} must be a SHA-256 digest")
    return item


def _integer(value: Mapping[str, Any], key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int) or item < 0:
        raise OpenADMETValidationError(f"{key} must be a nonnegative integer")
    return item


def _json_data(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OpenADMETValidationError(f"cannot parse {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise OpenADMETValidationError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _json_text(value: str, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise OpenADMETValidationError(f"cannot parse {label}") from exc
    if not isinstance(parsed, dict):
        raise OpenADMETValidationError(f"{label} must be an object")
    return cast(dict[str, Any], parsed)


def _bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise OpenADMETValidationError(f"cannot read {label}: {exc}") from exc


def _csv_bytes(columns: Sequence[str], rows: Sequence[Mapping[str, str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _boolean(value: bool) -> str:
    return "true" if value else "false"


def _write(path: Path, content: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise OpenADMETValidationError(f"refusing to overwrite {path}") from exc


__all__ = [
    "FOLD_COLUMNS",
    "OBSERVATION_COLUMNS",
    "OpenADMETValidationError",
    "ValidationInputResult",
    "build_openadmet_validation_inputs",
]

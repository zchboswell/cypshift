"""Minimal, leakage-safe construction of the frozen TDC-CYP shadow split."""

from __future__ import annotations

import csv
import io
import json
import resource
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from typing import Any

from rdkit import Chem, DataStructs, rdBase
from rdkit.Chem import rdFingerprintGenerator
from rdkit.Chem.Scaffolds import MurckoScaffold
from rdkit.ML.Cluster import Butina

SHADOW_CONTRACT_SCHEMA = "cypshift.tdc_cyp_shadow_contract.v1"
SHADOW_IMPLEMENTATION_CONTRACT_SCHEMA = (
    "cypshift.tdc_cyp_shadow_implementation_contract.v1"
)
SHADOW_INPUT_SCHEMA = "cypshift.tdc_cyp_shadow_input.v1"
SHADOW_ASSIGNMENT_SCHEMA = "cypshift.tdc_cyp_shadow_assignment.v1"
SHADOW_MANIFEST_SCHEMA = "cypshift.tdc_cyp_shadow_manifest.v1"
INPUT_COLUMNS = (
    "task",
    "molecule_id",
    "source_row",
    "raw_structure",
    "raw_structure_sha256",
    "standardized_structure",
    "standardized_structure_hash",
    "standardization_version",
)
SHADOW_COLUMNS = (
    "task",
    "molecule_id",
    "source_row",
    "raw_structure",
    "raw_structure_sha256",
    "standardized_structure",
    "standardized_structure_hash",
    "scaffold_group_hash",
    "community_group_hash",
    "scaffold_repeat_0_outer_fold",
    "scaffold_repeat_0_inner_fold",
    "scaffold_repeat_1_outer_fold",
    "scaffold_repeat_1_inner_fold",
    "scaffold_repeat_2_outer_fold",
    "scaffold_repeat_2_inner_fold",
    "community_repeat_0_outer_fold",
    "community_repeat_0_inner_fold",
    "community_repeat_1_outer_fold",
    "community_repeat_1_inner_fold",
    "community_repeat_2_outer_fold",
    "community_repeat_2_inner_fold",
)
_SOURCE = "src/cypshift/shadow.py"
_SPLIT_COLUMNS = ("molecule_id", "task", "partition", "source_row")
_CANONICAL_COLUMNS = (
    "molecule_id",
    "raw_structure",
    "structure_format",
    "standardized_structure",
    "standardized_structure_hash",
    "status",
    "stereochemistry_status",
    "input_fragments",
    "standardization_changed",
    "duplicate_of",
    "warnings",
    "standardization_version",
    "source",
    "provenance",
)


class ShadowContractError(ValueError):
    """Raised when a shadow artifact would violate the frozen contract."""


@dataclass(frozen=True, slots=True)
class ShadowInputResult:
    rows_path: Path
    manifest_path: Path
    row_count: int
    unique_structure_count: int


@dataclass(frozen=True, slots=True)
class ShadowAssignmentResult:
    rows_path: Path
    receipt_path: Path
    row_count: int
    scaffold_group_count: int
    community_group_count: int


@dataclass(frozen=True, slots=True)
class ShadowSummaryResult:
    manifest_path: Path
    row_count: int
    label_count: int


def prepare_shadow_input(
    contract_path: Path,
    implementation_contract_path: Path,
    adapter_manifest_path: Path,
    official_split_path: Path,
    canonical_molecules_path: Path,
    canonical_audit_path: Path,
    output_directory: Path,
    *,
    source_revision: str,
) -> ShadowInputResult:
    """Project exact train_val identities without retaining provenance or labels."""

    _require_new(output_directory)
    revision = _revision(source_revision)
    contract = _contract(contract_path)
    implementation = _implementation_contract(
        implementation_contract_path, contract_path
    )
    source_contracts = _obj(contract, "source_contracts")
    frozen_sources = _obj(source_contracts, "trusted_input_projection_sources")
    supplied = {
        "adapter_manifest": adapter_manifest_path,
        "official_split": official_split_path,
        "canonical_molecules": canonical_molecules_path,
        "canonical_audit": canonical_audit_path,
    }
    inputs: dict[str, dict[str, str]] = {}
    for name, path in supplied.items():
        source = _obj(frozen_sources, name)
        expected = _sha(_text(source, "sha256"), name)
        actual = _file_hash(path)
        if actual != expected:
            raise ShadowContractError(
                f"{name} hash mismatch: expected {expected}, got {actual}"
            )
        inputs[name] = {
            "path": _text(source, "expected_local_path"),
            "sha256": actual,
        }

    tasks = _tasks(contract)
    selected: dict[str, dict[str, str]] = {}
    seen: set[str] = set()
    for row in _read_csv(
        official_split_path,
        _SPLIT_COLUMNS,
        exact_header=_SPLIT_COLUMNS,
    ):
        molecule_id = _row_value(row, "molecule_id", official_split_path)
        if molecule_id in seen:
            raise ShadowContractError(f"duplicate split identity: {molecule_id}")
        seen.add(molecule_id)
        task = _row_value(row, "task", official_split_path)
        partition = _row_value(row, "partition", official_split_path)
        if task not in tasks or partition not in {"train_val", "test"}:
            raise ShadowContractError(f"unexpected split row for {molecule_id}")
        source_row = _positive_int(row["source_row"], "source_row")
        if partition == "train_val":
            selected[molecule_id] = {
                "task": task,
                "molecule_id": molecule_id,
                "source_row": str(source_row),
            }

    projected_molecule_columns = (
        "molecule_id",
        "raw_structure",
        "standardized_structure",
        "standardized_structure_hash",
        "status",
        "standardization_version",
    )
    molecules: dict[str, dict[str, str]] = {}
    canonical_ids: set[str] = set()
    standardization = _text(_obj(contract, "environment"), "standardization_version")
    # This trusted step selects named columns only. It never requests provenance.
    for row in _read_csv(
        canonical_molecules_path,
        projected_molecule_columns,
        exact_header=_CANONICAL_COLUMNS,
    ):
        molecule_id = _row_value(row, "molecule_id", canonical_molecules_path)
        if molecule_id in canonical_ids:
            raise ShadowContractError(f"duplicate canonical identity: {molecule_id}")
        canonical_ids.add(molecule_id)
        if molecule_id not in selected:
            continue
        raw = _row_value(
            row, "raw_structure", canonical_molecules_path, strip=False
        )
        structure = _row_value(
            row, "standardized_structure", canonical_molecules_path
        )
        structure_hash = _sha(
            row["standardized_structure_hash"], f"structure {molecule_id}"
        )
        if row["status"] != "accepted":
            raise ShadowContractError(f"non-accepted molecule: {molecule_id}")
        if row["standardization_version"] != standardization:
            raise ShadowContractError(
                f"standardization version mismatch for {molecule_id}"
            )
        if sha256(structure.encode()).hexdigest() != structure_hash:
            raise ShadowContractError(f"structure hash mismatch for {molecule_id}")
        molecules[molecule_id] = {
            "raw_structure": raw,
            "standardized_structure": structure,
            "standardized_structure_hash": structure_hash,
            "standardization_version": standardization,
        }
    if canonical_ids != seen:
        missing_canonical = sorted(seen - canonical_ids)
        extra_canonical = sorted(canonical_ids - seen)
        detail = missing_canonical[0] if missing_canonical else extra_canonical[0]
        raise ShadowContractError(
            f"complete split/canonical identity sets differ: {detail}"
        )
    missing = sorted(set(selected) - set(molecules))
    if missing:
        raise ShadowContractError(f"missing canonical molecule: {missing[0]}")

    rows = []
    for molecule_id, split in selected.items():
        molecule = molecules[molecule_id]
        raw = molecule["raw_structure"]
        rows.append(
            {
                **split,
                "raw_structure": raw,
                "raw_structure_sha256": sha256(raw.encode()).hexdigest(),
                "standardized_structure": molecule["standardized_structure"],
                "standardized_structure_hash": molecule[
                    "standardized_structure_hash"
                ],
                "standardization_version": standardization,
            }
        )
    rows.sort(key=_row_key)
    population = _population(rows, tasks)
    _check_population(contract, population)
    raw_counts = _obj(
        _obj(implementation, "trusted_projection"), "raw_count_definitions"
    )
    for name in ("unique_raw_structures", "unique_standardized_hash_raw_pairs"):
        if population[name] != _int(raw_counts, f"expected_{name}"):
            raise ShadowContractError(f"{name} differs from implementation contract")
    input_rows_contract = _obj(_obj(contract, "input_projection_contract"), "rows")
    if tuple(_text_list(input_rows_contract, "columns")) != INPUT_COLUMNS:
        raise ShadowContractError("input column contract differs from implementation")

    row_bytes = _csv_bytes(INPUT_COLUMNS, rows)
    manifest = {
        "schema_version": SHADOW_INPUT_SCHEMA,
        "contract": {
            "path": _logical_contract_path(contract_path),
            "sha256": _file_hash(contract_path),
        },
        "implementation_contract": _contract_receipt(
            implementation_contract_path
        ),
        "preparation_source": _source_receipt(revision),
        "inputs": inputs,
        "population": population,
        "target_columns": 0,
        "provenance_columns": 0,
        "public_test_rows": 0,
        "output": {
            "path": "shadow_input_rows.csv",
            "sha256": sha256(row_bytes).hexdigest(),
        },
        "deterministic": True,
    }
    output_directory.mkdir(parents=True)
    rows_path = output_directory / "shadow_input_rows.csv"
    manifest_path = output_directory / "shadow_input_manifest.json"
    _write(rows_path, row_bytes)
    _write(manifest_path, _json_bytes(manifest))
    return ShadowInputResult(
        rows_path,
        manifest_path,
        len(rows),
        _int(population, "unique_standardized_structures"),
    )


def assign_shadow_rows(
    contract_path: Path,
    implementation_contract_path: Path,
    input_rows_path: Path,
    input_manifest_path: Path,
    lock_path: Path,
    output_directory: Path,
    *,
    source_revision: str,
) -> ShadowAssignmentResult:
    """Assign folds using only the stripped projection, contract, and lock."""

    _require_new(output_directory)
    revision = _revision(source_revision)
    contract = _contract(contract_path)
    implementation = _implementation_contract(
        implementation_contract_path, contract_path
    )
    contract_hash = _file_hash(contract_path)
    implementation_hash = _file_hash(implementation_contract_path)
    environment = _check_environment(contract, implementation, lock_path)
    input_manifest = _read_json(input_manifest_path)
    if input_manifest.get("schema_version") != SHADOW_INPUT_SCHEMA:
        raise ShadowContractError("unsupported shadow input manifest")
    if _obj(input_manifest, "contract").get("sha256") != contract_hash:
        raise ShadowContractError("input manifest uses another contract")
    if (
        _obj(input_manifest, "implementation_contract").get("sha256")
        != implementation_hash
    ):
        raise ShadowContractError("input manifest uses another implementation contract")
    preparation_source = _obj(input_manifest, "preparation_source")
    if (
        preparation_source.get("revision") != revision
        or preparation_source.get("sha256") != _file_hash(Path(__file__))
    ):
        raise ShadowContractError("input preparation and assignment source differ")
    if _obj(input_manifest, "output").get("path") != "shadow_input_rows.csv":
        raise ShadowContractError("input manifest names an unexpected row artifact")
    rows_hash = _file_hash(input_rows_path)
    if _obj(input_manifest, "output").get("sha256") != rows_hash:
        raise ShadowContractError("input rows do not match their manifest")
    rows = _read_csv(input_rows_path, INPUT_COLUMNS, exact_header=INPUT_COLUMNS)
    tasks = _tasks(contract)
    _check_projection_rows(contract, rows, tasks)
    start = time.perf_counter()

    structure_by_hash: dict[str, str] = {}
    for row in rows:
        key = row["standardized_structure_hash"]
        prior = structure_by_hash.setdefault(key, row["standardized_structure"])
        if prior != row["standardized_structure"]:
            raise ShadowContractError(f"hash maps to multiple structures: {key}")
    ordered_hashes = sorted(structure_by_hash)
    molecules: dict[str, Chem.Mol] = {}
    scaffolds: dict[str, str] = {}
    with rdBase.BlockLogs():
        for key in ordered_hashes:
            molecule = Chem.MolFromSmiles(structure_by_hash[key])
            if molecule is None:
                raise ShadowContractError(f"cannot parse structure: {key}")
            molecules[key] = molecule
            scaffold = MurckoScaffold.MurckoScaffoldSmiles(  # type: ignore[no-untyped-call]
                mol=molecule, includeChirality=False
            )
            material = (
                f"bemis_murcko_scaffold:{scaffold}"
                if scaffold
                else f"acyclic_exact_structure:{structure_by_hash[key]}"
            )
            scaffolds[key] = sha256(material.encode()).hexdigest()
    expected_scaffolds = _int(_obj(contract, "population"), "global_scaffold_groups")
    if len(set(scaffolds.values())) != expected_scaffolds:
        raise ShadowContractError("scaffold count differs from frozen population")
    communities, distance_count = _communities(contract, ordered_hashes, molecules)

    groups = {"scaffold": scaffolds, "community": communities}
    folds: dict[tuple[str, int], dict[str, int]] = {}
    for protocol, node_groups in groups.items():
        weights = Counter(
            node_groups[row["standardized_structure_hash"]] for row in rows
        )
        for repeat, seed in _repeats(contract):
            folds[(protocol, repeat)] = _folds(weights, seed, protocol)

    output_rows: list[dict[str, str]] = []
    for row in rows:
        key = row["standardized_structure_hash"]
        output = {name: row[name] for name in INPUT_COLUMNS[:-1]}
        output["scaffold_group_hash"] = scaffolds[key]
        output["community_group_hash"] = communities[key]
        for protocol, node_groups in groups.items():
            group = node_groups[key]
            for repeat, _ in _repeats(contract):
                outer = folds[(protocol, repeat)][group]
                output[f"{protocol}_repeat_{repeat}_outer_fold"] = str(outer)
                output[f"{protocol}_repeat_{repeat}_inner_fold"] = (
                    "" if outer == 0 else str(outer - 1)
                )
        output_rows.append(output)
    output_rows.sort(key=_row_key)
    declared = _text_list(
        _obj(_obj(contract, "output_contract"), "shadow_rows"), "columns"
    )
    if tuple(declared) != SHADOW_COLUMNS:
        raise ShadowContractError("output column contract differs from implementation")
    _check_shadow_rows(contract, output_rows)

    elapsed = time.perf_counter() - start
    peak = _peak_rss_gib()
    _check_cap(contract, elapsed, peak)
    row_bytes = _csv_bytes(SHADOW_COLUMNS, output_rows)
    receipt = {
        "schema_version": SHADOW_ASSIGNMENT_SCHEMA,
        "contract": {
            "path": _logical_contract_path(contract_path),
            "sha256": contract_hash,
        },
        "implementation_contract": _contract_receipt(
            implementation_contract_path
        ),
        "implementation_source": _source_receipt(revision),
        "environment": environment,
        "inputs": {
            "shadow_input_rows.csv": rows_hash,
            "shadow_input_manifest.json": _file_hash(input_manifest_path),
        },
        "population": _population(rows, tasks),
        "groups": {
            "scaffold": len(set(scaffolds.values())),
            "community": len(set(communities.values())),
        },
        "community_distance_count": distance_count,
        "community_distance_dtype": "numpy.float64",
        "runtime_seconds": elapsed,
        "peak_rss_gib": peak,
        "outputs": {"shadow_rows.csv": sha256(row_bytes).hexdigest()},
        "accounting": _zero_assignment_accounting(),
    }
    output_directory.mkdir(parents=True)
    rows_path = output_directory / "shadow_rows.csv"
    receipt_path = output_directory / "shadow_assignment_receipt.json"
    _write(rows_path, row_bytes)
    _write(receipt_path, _json_bytes(receipt))
    return ShadowAssignmentResult(
        rows_path,
        receipt_path,
        len(output_rows),
        len(set(scaffolds.values())),
        len(set(communities.values())),
    )


def summarize_shadow_rows(
    contract_path: Path,
    implementation_contract_path: Path,
    shadow_rows_path: Path,
    assignment_receipt_path: Path,
    train_val_measurements_path: Path,
    measurement_parent_manifest_path: Path,
    *,
    source_revision: str,
) -> ShadowSummaryResult:
    """Join the sole train-only label projection after assignment is hashed."""

    revision = _revision(source_revision)
    manifest_path = shadow_rows_path.parent / "shadow_manifest.json"
    if manifest_path.exists():
        raise ShadowContractError(f"refusing to overwrite {manifest_path}")
    contract = _contract(contract_path)
    _implementation_contract(implementation_contract_path, contract_path)
    contract_hash = _file_hash(contract_path)
    implementation_hash = _file_hash(implementation_contract_path)
    receipt = _read_json(assignment_receipt_path)
    if receipt.get("schema_version") != SHADOW_ASSIGNMENT_SCHEMA:
        raise ShadowContractError("unsupported assignment receipt")
    if _obj(receipt, "contract").get("sha256") != contract_hash:
        raise ShadowContractError("assignment receipt uses another contract")
    if (
        _obj(receipt, "implementation_contract").get("sha256")
        != implementation_hash
    ):
        raise ShadowContractError("assignment uses another implementation contract")
    source = _obj(receipt, "implementation_source")
    if (
        source.get("revision") != revision
        or source.get("sha256") != _file_hash(Path(__file__))
    ):
        raise ShadowContractError("assignment and summary source differ")
    shadow_hash = _file_hash(shadow_rows_path)
    if _obj(receipt, "outputs").get("shadow_rows.csv") != shadow_hash:
        raise ShadowContractError("shadow rows do not match assignment receipt")

    measurement_contract = _obj(
        _obj(contract, "source_contracts"),
        "train_val_measurements_for_post_assignment_summary_only",
    )
    measurement_hash = _file_hash(train_val_measurements_path)
    if measurement_hash != _sha(
        _text(measurement_contract, "sha256"), "train_val measurements"
    ):
        raise ShadowContractError("train_val measurement hash mismatch")
    parent_hash = _file_hash(measurement_parent_manifest_path)
    parent_contract = _obj(measurement_contract, "parent_manifest")
    if parent_hash != _sha(_text(parent_contract, "sha256"), "parent manifest"):
        raise ShadowContractError("measurement parent manifest hash mismatch")
    parent = _read_json(measurement_parent_manifest_path)
    if _obj(parent, "outputs").get("tdc/measurements.csv") != measurement_hash:
        raise ShadowContractError("parent manifest does not bind measurements")

    rows = _read_csv(shadow_rows_path, SHADOW_COLUMNS, exact_header=SHADOW_COLUMNS)
    _check_shadow_rows(contract, rows)
    shadow_ids = [row["molecule_id"] for row in rows]
    if len(shadow_ids) != len(set(shadow_ids)):
        raise ShadowContractError("duplicate shadow identity")
    # Identity validation is a complete first pass. Values are not selected yet.
    identity_rows = _read_csv(train_val_measurements_path, ("molecule_id",))
    measurement_ids = [row["molecule_id"] for row in identity_rows]
    if len(measurement_ids) != len(set(measurement_ids)):
        raise ShadowContractError("duplicate measurement identity")
    unknown = sorted(set(measurement_ids) - set(shadow_ids))
    missing = sorted(set(shadow_ids) - set(measurement_ids))
    if unknown:
        raise ShadowContractError(
            f"measurement identity absent from frozen shadow rows: {unknown[0]}"
        )
    if missing:
        raise ShadowContractError(f"shadow identity lacks measurement: {missing[0]}")
    if len(measurement_ids) != _int(measurement_contract, "rows"):
        raise ShadowContractError("measurement row count differs from contract")

    labels: dict[str, int] = {}
    for row in _read_csv(train_val_measurements_path, ("molecule_id", "value")):
        molecule_id = row["molecule_id"]
        try:
            value = float(row["value"])
        except ValueError as exc:
            raise ShadowContractError(
                f"non-numeric shadow label for {molecule_id}"
            ) from exc
        if value not in {0.0, 1.0}:
            raise ShadowContractError(f"non-binary shadow label for {molecule_id}")
        labels[molecule_id] = int(value)

    summaries = _label_summaries(contract, rows, labels)
    duplicate_counts = _duplicate_counts(rows, labels)
    population_contract = _obj(contract, "population")
    for name, actual in duplicate_counts.items():
        if actual != _int(population_contract, name):
            raise ShadowContractError(f"{name} differs from frozen population")
    outputs = {
        "shadow_assignment_receipt.json": _file_hash(assignment_receipt_path),
        "shadow_rows.csv": shadow_hash,
    }
    material = "\n".join(
        f"{name}={digest}" for name, digest in sorted(outputs.items())
    )
    manifest = {
        "schema_version": SHADOW_MANIFEST_SCHEMA,
        "benchmark_id": _text(contract, "benchmark_id"),
        "contract": {
            "path": _logical_contract_path(contract_path),
            "sha256": contract_hash,
        },
        "implementation_contract": _contract_receipt(
            implementation_contract_path
        ),
        "implementation_source": _source_receipt(revision),
        "assignment_inputs": _obj(receipt, "inputs"),
        "summary_inputs": {
            "train_val_measurements.csv": measurement_hash,
            "measurement_parent_manifest.json": parent_hash,
        },
        "environment": _obj(receipt, "environment"),
        "population": _obj(receipt, "population"),
        "groups": _obj(receipt, "groups"),
        "duplicate_and_conflicting_labels": duplicate_counts,
        "validation": summaries,
        "runtime_seconds": receipt.get("runtime_seconds"),
        "peak_rss_gib": receipt.get("peak_rss_gib"),
        "outputs": outputs,
        "aggregate_recipe": (
            "SHA-256 of UTF-8 path=sha256 lines sorted by path and joined "
            "with newline characters, without a trailing newline"
        ),
        "aggregate_sha256": sha256(material.encode()).hexdigest(),
        "accounting": {
            "train_val_labels_parsed": len(labels),
            "public_test_labels_parsed": 0,
            "feature_matrices_generated": 0,
            "model_fits": 0,
            "predictions": 0,
            "metric_evaluations": 0,
        },
        "deterministic_assignments": True,
    }
    _write(manifest_path, _json_bytes(manifest))
    return ShadowSummaryResult(manifest_path, len(rows), len(labels))


def _communities(
    contract: Mapping[str, Any],
    ordered_hashes: Sequence[str],
    molecules: Mapping[str, Chem.Mol],
) -> tuple[dict[str, str], int]:
    community = _obj(_obj(contract, "protocols"), "community")
    fingerprint = _obj(community, "fingerprint")
    if fingerprint.get("includeChirality") is not True:
        raise ShadowContractError("community chirality must be true")
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=_int(fingerprint, "radius"),
        fpSize=_int(fingerprint, "fpSize"),
        includeChirality=True,
    )
    fps = [generator.GetFingerprint(molecules[key]) for key in ordered_hashes]
    count = len(fps) * (len(fps) - 1) // 2
    if count != _int(community, "pair_distances"):
        raise ShadowContractError("community pair count differs from contract")
    numpy = import_module("numpy")
    distances = numpy.empty(count, dtype=numpy.float64)
    offset = 0
    for index in range(1, len(fps)):
        similarities = DataStructs.BulkTanimotoSimilarity(fps[index], fps[:index])
        distances[offset : offset + index] = 1.0 - numpy.asarray(
            similarities, dtype=numpy.float64
        )
        offset += index
    if offset != count or not distances.flags.c_contiguous:
        raise ShadowContractError("distance vector is not exact contiguous float64")
    clusters = Butina.ClusterData(  # type: ignore[no-untyped-call]
        distances,
        len(fps),
        _number(community, "distance_cutoff"),
        isDistData=True,
        reordering=True,
    )
    result: dict[str, str] = {}
    for cluster in clusters:
        members = sorted(ordered_hashes[index] for index in cluster)
        group = sha256(("community-v1|" + "|".join(members)).encode()).hexdigest()
        for member in members:
            if member in result:
                raise ShadowContractError("community node assigned twice")
            result[member] = group
    if set(result) != set(ordered_hashes):
        raise ShadowContractError("community assignment is incomplete")
    return result, count


def _folds(weights: Mapping[str, int], seed: int, protocol: str) -> dict[str, int]:
    groups = sorted(
        weights,
        key=lambda group: (
            -weights[group],
            sha256(
                f"{seed}|{protocol}|group-order-v1|{group}".encode()
            ).hexdigest(),
            group,
        ),
    )
    counts = [0] * 5
    assignment: dict[str, int] = {}
    for group in groups:
        fold = min(
            range(5),
            key=lambda candidate: (
                counts[candidate],
                sha256(
                    f"{seed}|{protocol}|fold-tie-v1|{group}|{candidate}".encode()
                ).hexdigest(),
                candidate,
            ),
        )
        assignment[group] = fold
        counts[fold] += weights[group]
    return assignment


def _check_projection_rows(
    contract: Mapping[str, Any], rows: Sequence[Mapping[str, str]], tasks: Sequence[str]
) -> None:
    if list(rows) != sorted(rows, key=_row_key):
        raise ShadowContractError("shadow input rows are not in frozen order")
    seen: set[str] = set()
    version = _text(_obj(contract, "environment"), "standardization_version")
    for row in rows:
        molecule_id = _row_value(row, "molecule_id", Path("shadow_input_rows.csv"))
        if molecule_id in seen:
            raise ShadowContractError(f"duplicate input identity: {molecule_id}")
        seen.add(molecule_id)
        if row["task"] not in tasks or row["standardization_version"] != version:
            raise ShadowContractError(f"invalid input row: {molecule_id}")
        _positive_int(row["source_row"], "source_row")
        _check_structure_hashes(row)
    _check_population(contract, _population(rows, tasks))


def _check_shadow_rows(
    contract: Mapping[str, Any], rows: Sequence[Mapping[str, str]]
) -> None:
    tasks = _tasks(contract)
    if list(rows) != sorted(rows, key=_row_key):
        raise ShadowContractError("shadow rows are not in frozen order")
    _check_population(contract, _population(rows, tasks))
    by_node: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    seen: set[str] = set()
    for row in rows:
        molecule_id = row["molecule_id"]
        if molecule_id in seen:
            raise ShadowContractError(f"duplicate shadow identity: {molecule_id}")
        seen.add(molecule_id)
        if row["task"] not in tasks:
            raise ShadowContractError(f"unexpected shadow task: {row['task']}")
        _positive_int(row["source_row"], "source_row")
        _check_structure_hashes(row)
        by_node[row["standardized_structure_hash"]].append(row)
    for node, node_rows in by_node.items():
        for protocol in ("scaffold", "community"):
            group_column = f"{protocol}_group_hash"
            if len({row[group_column] for row in node_rows}) != 1:
                raise ShadowContractError(f"{protocol} group varies for node {node}")
            for repeat, _ in _repeats(contract):
                outer_column = f"{protocol}_repeat_{repeat}_outer_fold"
                inner_column = f"{protocol}_repeat_{repeat}_inner_fold"
                outer = {row[outer_column] for row in node_rows}
                inner = {row[inner_column] for row in node_rows}
                if len(outer) != 1 or len(inner) != 1:
                    raise ShadowContractError(f"fold varies for node {node}")
                outer_value = next(iter(outer))
                if outer_value not in {"0", "1", "2", "3", "4"}:
                    raise ShadowContractError("outer fold outside 0 through 4")
                expected_inner = (
                    "" if outer_value == "0" else str(int(outer_value) - 1)
                )
                if next(iter(inner)) != expected_inner:
                    raise ShadowContractError("invalid inner-fold sentinel or mapping")
    for protocol in ("scaffold", "community"):
        for repeat, _ in _repeats(contract):
            groups: dict[str, set[str]] = defaultdict(set)
            for row in rows:
                groups[row[f"{protocol}_group_hash"]].add(
                    row[f"{protocol}_repeat_{repeat}_outer_fold"]
                )
            if any(len(folds) != 1 for folds in groups.values()):
                raise ShadowContractError(f"{protocol} group crosses a fold")


def _label_summaries(
    contract: Mapping[str, Any],
    rows: Sequence[Mapping[str, str]],
    labels: Mapping[str, int],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for task in _tasks(contract):
        task_rows = [row for row in rows if row["task"] == task]
        result[task] = {}
        for protocol in ("scaffold", "community"):
            result[task][protocol] = {}
            group_column = f"{protocol}_group_hash"
            for repeat, _ in _repeats(contract):
                outer_column = f"{protocol}_repeat_{repeat}_outer_fold"
                inner_column = f"{protocol}_repeat_{repeat}_inner_fold"
                outer = [
                    _class_summary(
                        [row for row in task_rows if row[outer_column] == str(fold)],
                        labels,
                        group_column,
                        fold,
                    )
                    for fold in range(5)
                ]
                outer_train_rows = [
                    row for row in task_rows if row[outer_column] != "0"
                ]
                outer_train = _class_summary(
                    outer_train_rows, labels, group_column, "training"
                )
                inner = [
                    _class_summary(
                        [
                            row
                            for row in outer_train_rows
                            if row[inner_column] == str(fold)
                        ],
                        labels,
                        group_column,
                        fold,
                    )
                    for fold in range(4)
                ]
                inner_train = [
                    _class_summary(
                        [
                            row
                            for row in outer_train_rows
                            if row[inner_column] != str(fold)
                        ],
                        labels,
                        group_column,
                        fold,
                    )
                    for fold in range(4)
                ]
                checked = [outer[0], outer_train, *inner, *inner_train]
                if any(
                    item["positive"] == 0 or item["negative"] == 0
                    for item in checked
                ):
                    raise ShadowContractError(
                        f"degenerate class support for {task}/{protocol}/{repeat}"
                    )
                result[task][protocol][str(repeat)] = {
                    "outer_folds": outer,
                    "outer_training": outer_train,
                    "inner_folds": inner,
                    "inner_training_by_validation_fold": inner_train,
                }
    return result


def _class_summary(
    rows: Sequence[Mapping[str, str]],
    labels: Mapping[str, int],
    group_column: str,
    fold: int | str,
) -> dict[str, Any]:
    positive = sum(labels[row["molecule_id"]] for row in rows)
    return {
        "fold": fold,
        "rows": len(rows),
        "groups": len({row[group_column] for row in rows}),
        "positive": positive,
        "negative": len(rows) - positive,
        "prevalence": positive / len(rows) if rows else None,
    }


def _duplicate_counts(
    rows: Sequence[Mapping[str, str]], labels: Mapping[str, int]
) -> dict[str, int]:
    cells: dict[tuple[str, str], list[int]] = defaultdict(list)
    for row in rows:
        cells[(row["task"], row["standardized_structure_hash"])].append(
            labels[row["molecule_id"]]
        )
    conflicts = {key for key, values in cells.items() if len(set(values)) > 1}
    return {
        "structure_task_cells": len(cells),
        "structure_task_cells_with_duplicate_rows": sum(
            len(values) > 1 for values in cells.values()
        ),
        "duplicate_excess_source_rows": sum(
            len(values) - 1 for values in cells.values()
        ),
        "structure_task_cells_with_conflicting_labels": len(conflicts),
        "unique_structures_in_conflicting_label_cells": len(
            {structure for _, structure in conflicts}
        ),
    }


def _population(
    rows: Sequence[Mapping[str, str]], tasks: Sequence[str]
) -> dict[str, Any]:
    tasks_by_hash: dict[str, set[str]] = defaultdict(set)
    raw_by_hash: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        key = row["standardized_structure_hash"]
        tasks_by_hash[key].add(row["task"])
        raw_by_hash[key].add(row["raw_structure"])
    membership = Counter(len(value) for value in tasks_by_hash.values())
    multiple_raw = [value for value in raw_by_hash.values() if len(value) > 1]
    return {
        "source_rows": len(rows),
        "unique_raw_structures": len(
            {row["raw_structure"] for row in rows}
        ),
        "unique_standardized_hash_raw_pairs": len(
            {
                (row["standardized_structure_hash"], row["raw_structure"])
                for row in rows
            }
        ),
        "task_rows": {task: sum(row["task"] == task for row in rows) for task in tasks},
        "unique_standardized_structures": len(tasks_by_hash),
        "task_unique_standardized_structures": {
            task: len(
                {
                    row["standardized_structure_hash"]
                    for row in rows
                    if row["task"] == task
                }
            )
            for task in tasks
        },
        "task_membership_by_unique_structure": {
            "one_task": membership[1],
            "two_tasks": membership[2],
            "three_tasks": membership[3],
        },
        "standardized_hashes_with_multiple_distinct_raw_smiles": len(multiple_raw),
        "excess_distinct_raw_smiles_for_those_hashes": sum(
            len(value) - 1 for value in multiple_raw
        ),
        "maximum_raw_smiles_per_standardized_hash": max(
            (len(value) for value in raw_by_hash.values()), default=0
        ),
    }


def _check_population(contract: Mapping[str, Any], actual: Mapping[str, Any]) -> None:
    expected = _obj(contract, "population")
    names = (
        "source_rows",
        "task_rows",
        "unique_standardized_structures",
        "task_unique_standardized_structures",
        "task_membership_by_unique_structure",
        "standardized_hashes_with_multiple_distinct_raw_smiles",
        "excess_distinct_raw_smiles_for_those_hashes",
        "maximum_raw_smiles_per_standardized_hash",
    )
    for name in names:
        if actual[name] != expected.get(name):
            raise ShadowContractError(f"{name} differs from frozen population")


def _check_structure_hashes(row: Mapping[str, str]) -> None:
    molecule_id = row["molecule_id"]
    if sha256(row["raw_structure"].encode()).hexdigest() != row[
        "raw_structure_sha256"
    ]:
        raise ShadowContractError(f"raw structure hash mismatch for {molecule_id}")
    if sha256(row["standardized_structure"].encode()).hexdigest() != row[
        "standardized_structure_hash"
    ]:
        raise ShadowContractError(f"structure hash mismatch for {molecule_id}")


def _check_environment(
    contract: Mapping[str, Any],
    implementation: Mapping[str, Any],
    lock_path: Path,
) -> dict[str, str]:
    environment = _obj(contract, "environment")
    required = _obj(implementation, "assignment_environment")
    lock_hash = _file_hash(lock_path)
    if lock_hash != _sha(_text(environment, "lock_sha256"), "environment lock"):
        raise ShadowContractError("environment lock hash mismatch")
    if lock_hash != _sha(_text(required, "lock_sha256"), "implementation lock"):
        raise ShadowContractError("parent and implementation locks differ")
    expected_python = _text(required, "python")
    actual_python = f"{sys.version_info.major}.{sys.version_info.minor}"
    numpy = import_module("numpy")
    numpy_version = getattr(numpy, "__version__", None)
    if expected_python != actual_python:
        raise ShadowContractError(
            f"Python version mismatch: expected {expected_python}, got {actual_python}"
        )
    expected_rdkit = _text(required, "rdkit")
    if expected_rdkit != _text(environment, "rdkit_version"):
        raise ShadowContractError("parent and implementation RDKit versions differ")
    if rdBase.rdkitVersion != expected_rdkit:
        raise ShadowContractError("RDKit version mismatch")
    expected_numpy = _text(required, "numpy")
    if expected_numpy != _text(environment, "numpy_version_on_python_3_11"):
        raise ShadowContractError("parent and implementation NumPy versions differ")
    if numpy_version != expected_numpy:
        raise ShadowContractError("NumPy version mismatch")
    return {
        "lock_path": _text(environment, "lock_path"),
        "lock_sha256": lock_hash,
        "python": f"{actual_python}.{sys.version_info.micro}",
        "rdkit": rdBase.rdkitVersion,
        "numpy": str(numpy_version),
    }


def _check_cap(contract: Mapping[str, Any], elapsed: float, peak: float) -> None:
    cap = _obj(_obj(_obj(contract, "protocols"), "community"), "resource_cap")
    if elapsed > 60 * _number(cap, "runtime_minutes"):
        raise ShadowContractError("community clustering exceeded runtime cap")
    if peak > _number(cap, "peak_rss_gib"):
        raise ShadowContractError("community clustering exceeded peak RSS cap")


def _peak_rss_gib() -> float:
    peak = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return peak / (1024**3 if sys.platform == "darwin" else 1024**2)


def _tasks(contract: Mapping[str, Any]) -> tuple[str, ...]:
    tasks = _obj(contract, "population").get("tasks")
    if not isinstance(tasks, list) or not all(isinstance(task, str) for task in tasks):
        raise ShadowContractError("contract tasks must be a text list")
    return tuple(tasks)


def _repeats(contract: Mapping[str, Any]) -> tuple[tuple[int, int], ...]:
    value = contract.get("repeats")
    if not isinstance(value, list):
        raise ShadowContractError("contract repeats must be a list")
    parsed: list[tuple[int, int]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ShadowContractError("repeat must be an object")
        parsed.append((_int(item, "repeat"), _int(item, "seed")))
    if [repeat for repeat, _ in parsed] != [0, 1, 2]:
        raise ShadowContractError("repeats must be exactly 0, 1, and 2")
    return tuple(parsed)


def _zero_assignment_accounting() -> dict[str, int]:
    return {
        "target_values_used_for_assignment": 0,
        "public_test_rows_emitted": 0,
        "public_test_labels_parsed": 0,
        "feature_matrices_generated": 0,
        "model_fits": 0,
        "predictions": 0,
        "metric_evaluations": 0,
    }


def _source_receipt(revision: str) -> dict[str, str]:
    return {"path": _SOURCE, "revision": revision, "sha256": _file_hash(Path(__file__))}


def _contract_receipt(path: Path) -> dict[str, str]:
    return {"path": _logical_contract_path(path), "sha256": _file_hash(path)}


def _contract(path: Path) -> dict[str, Any]:
    contract = _read_json(path)
    if contract.get("schema_version") != SHADOW_CONTRACT_SCHEMA:
        raise ShadowContractError("unsupported shadow contract schema")
    return contract


def _implementation_contract(path: Path, parent_path: Path) -> dict[str, Any]:
    contract = _read_json(path)
    if contract.get("schema_version") != SHADOW_IMPLEMENTATION_CONTRACT_SCHEMA:
        raise ShadowContractError("unsupported shadow implementation contract schema")
    parent = _obj(contract, "parent_contract")
    if parent.get("sha256") != _file_hash(parent_path):
        raise ShadowContractError("implementation contract binds another parent")
    return contract


def _read_json(path: Path) -> dict[str, Any]:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ShadowContractError(f"duplicate JSON key {key!r} in {path}")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ShadowContractError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ShadowContractError(f"JSON root is not an object: {path}")
    return value


def _read_csv(
    path: Path,
    columns: Sequence[str],
    *,
    exact_header: Sequence[str] | None = None,
) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            header = next(reader)
            if len(header) != len(set(header)):
                raise ShadowContractError(f"duplicate CSV column in {path}")
            if exact_header is not None and tuple(header) != tuple(exact_header):
                raise ShadowContractError(f"unexpected CSV columns in {path}")
            if any(column not in header for column in columns):
                raise ShadowContractError(f"missing CSV column in {path}")
            indexes = {column: header.index(column) for column in columns}
            rows = []
            for line, values in enumerate(reader, start=2):
                if len(values) != len(header):
                    raise ShadowContractError(f"malformed CSV row {line} in {path}")
                rows.append({name: values[index] for name, index in indexes.items()})
            return rows
    except StopIteration as exc:
        raise ShadowContractError(f"empty CSV: {path}") from exc
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ShadowContractError(f"cannot read CSV {path}: {exc}") from exc


def _row_value(
    row: Mapping[str, str], key: str, path: Path, *, strip: bool = True
) -> str:
    value = row.get(key)
    if not isinstance(value, str):
        raise ShadowContractError(f"missing {key} in {path}")
    checked = value.strip() if strip else value
    if not checked:
        raise ShadowContractError(f"empty {key} in {path}")
    return checked


def _row_key(row: Mapping[str, str]) -> tuple[str, int, str]:
    return row["task"], int(row["source_row"]), row["molecule_id"]


def _obj(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise ShadowContractError(f"field {key!r} must be an object")
    return dict(item)


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ShadowContractError(f"field {key!r} must be non-empty text")
    return item


def _text_list(value: Mapping[str, Any], key: str) -> list[str]:
    item = value.get(key)
    if not isinstance(item, list) or not all(isinstance(part, str) for part in item):
        raise ShadowContractError(f"field {key!r} must be a text list")
    return item


def _int(value: Mapping[str, Any], key: str) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool):
        raise ShadowContractError(f"field {key!r} must be an integer")
    return item


def _number(value: Mapping[str, Any], key: str) -> float:
    item = value.get(key)
    if not isinstance(item, (int, float)) or isinstance(item, bool):
        raise ShadowContractError(f"field {key!r} must be numeric")
    return float(item)


def _positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ShadowContractError(f"{name} is not an integer") from exc
    if parsed < 1 or str(parsed) != value:
        raise ShadowContractError(f"{name} must be canonical positive decimal text")
    return parsed


def _nonempty(value: str, name: str) -> str:
    checked = value.strip()
    if not checked:
        raise ShadowContractError(f"{name} must be non-empty")
    return checked


def _revision(value: str) -> str:
    checked = _nonempty(value, "source revision")
    if len(checked) != 40 or any(
        character not in "0123456789abcdef" for character in checked
    ):
        raise ShadowContractError("source revision must be a full lowercase Git SHA")
    return checked


def _logical_contract_path(path: Path) -> str:
    if path.name in {
        "tdc_cyp_shadow_v1_contract.json",
        "tdc_cyp_shadow_v1_implementation_contract.json",
    }:
        return f"benchmarks/{path.name}"
    return path.name


def _sha(value: str, name: str) -> str:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ShadowContractError(f"invalid SHA-256 for {name}")
    return value


def _file_hash(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise ShadowContractError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _csv_bytes(columns: Sequence[str], rows: Sequence[Mapping[str, str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer, fieldnames=columns, extrasaction="raise", lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _require_new(path: Path) -> None:
    if path.exists():
        raise ShadowContractError(
            f"output path already exists: {path}. Shadow artifacts are immutable."
        )


def _write(path: Path, content: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(content)
    except OSError as exc:
        raise ShadowContractError(f"cannot write {path}: {exc}") from exc


__all__ = [
    "INPUT_COLUMNS",
    "SHADOW_ASSIGNMENT_SCHEMA",
    "SHADOW_COLUMNS",
    "SHADOW_CONTRACT_SCHEMA",
    "SHADOW_INPUT_SCHEMA",
    "SHADOW_IMPLEMENTATION_CONTRACT_SCHEMA",
    "SHADOW_MANIFEST_SCHEMA",
    "ShadowAssignmentResult",
    "ShadowContractError",
    "ShadowInputResult",
    "ShadowSummaryResult",
    "assign_shadow_rows",
    "prepare_shadow_input",
    "summarize_shadow_rows",
]

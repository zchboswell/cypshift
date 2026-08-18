"""Label-free OpenADMET topology audit; components are not family labels."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from rdkit import Chem, DataStructs, rdBase
from rdkit.Chem import rdFingerprintGenerator

from cypshift.audit import MOLECULE_INPUT_COLUMNS, MOLECULE_OUTPUT_COLUMNS
from cypshift.chemistry import STANDARDIZATION_VERSION, audit_molecules
from cypshift.openadmet_cyp import (
    OPENADMET_ADAPTER_SCHEMA_VERSION,
    OPENADMET_DATASET_ID,
    OPENADMET_SOURCE_FILES,
)
from cypshift.schema import MoleculeInput, MoleculeRecord, MoleculeStatus

MurckoScaffold = import_module("rdkit.Chem.Scaffolds.MurckoScaffold")

TOPOLOGY_SCHEMA_VERSION = "cypshift.openadmet_cyp_2026.topology_audit.v1"
TOPOLOGY_COLUMNS = (
    "molecule_id",
    "standardized_structure_hash",
    "similarity_component_hash",
    "scaffold_group_hash",
)
MOLECULE_AUDIT_COLUMNS = (
    "molecule_id",
    "partition",
    *MOLECULE_OUTPUT_COLUMNS[1:],
    "raw_structure_sha256",
)
TEST_SOURCE_FILE = "cyp-challenge-TEST-BLINDED.csv"
DIRECT_SOURCE_FILE = "cyp-challenge-TRAIN_inhibition.csv"
MORGAN_RADIUS = 2
MORGAN_FP_SIZE = 4096
MORGAN_INCLUDE_CHIRALITY = True
SIMILARITY_THRESHOLD = 0.60
_SIMILARITY_SPEC = (
    "morgan_ecfp4_radius=2;fp_size=4096;include_chirality=true;"
    "tanimoto_inclusive_threshold=0.60"
)


class OpenADMETTopologyError(ValueError):
    """Unsafe topology audit input."""


@dataclass(frozen=True, slots=True)
class TopologyAuditResult:
    molecule_audit_path: Path
    training_topology_path: Path
    manifest_path: Path
    training_molecules: int
    topology_rows: int
    similarity_components: int
    scaffold_groups: int


def audit_openadmet_topology(
    input_directory: Path, output_directory: Path
) -> TopologyAuditResult:
    """Audit R1 training topology without parsing source-row values."""

    if output_directory.exists():
        raise OpenADMETTopologyError(
            f"output path already exists: {output_directory}; refusing overwrite"
        )
    manifest_path = input_directory / "manifest.json"
    molecules_path = input_directory / "molecules_input.csv"
    source_rows_path = input_directory / "source_rows.csv"
    manifest = _verify_r1_input(manifest_path, molecules_path, source_rows_path)
    molecule_inputs = _read_molecule_inputs(molecules_path, manifest)
    partitions = {
        molecule.molecule_id: _partition_from_provenance(molecule.provenance)
        for molecule in molecule_inputs
    }
    records = audit_molecules(
        sorted(molecule_inputs, key=lambda molecule: molecule.molecule_id)
    )
    if len(records) != len(molecule_inputs):
        raise OpenADMETTopologyError("chemistry audit changed molecule identity count")
    if {record.molecule_id for record in records} != set(partitions):
        raise OpenADMETTopologyError("chemistry audit identity set changed")
    for record in records:
        if record.standardization_version != STANDARDIZATION_VERSION:
            raise OpenADMETTopologyError(
                f"unexpected standardization version for {record.molecule_id}"
            )

    train_records = [
        record for record in records if partitions[record.molecule_id] == "train"
    ]
    test_records = [
        record for record in records if partitions[record.molecule_id] == "test"
    ]
    train_accepted = [
        record for record in train_records if record.status is MoleculeStatus.ACCEPTED
    ]
    test_accepted = [
        record for record in test_records if record.status is MoleculeStatus.ACCEPTED
    ]
    train_structures = _unique_structures(train_accepted)
    test_hashes = {
        cast(str, record.standardized_structure_hash) for record in test_accepted
    }
    train_hashes = set(train_structures)
    overlap_hashes = sorted(train_hashes & test_hashes)

    scaffolds = _scaffold_groups(train_structures)
    components, pair_count, edge_count, scaffold_crossing = _similarity_groups(
        train_structures, scaffolds
    )
    topology_rows = _topology_rows(train_accepted, components, scaffolds)
    molecule_rows = _molecule_audit_rows(records, partitions)
    molecule_bytes = _csv_bytes(MOLECULE_AUDIT_COLUMNS, molecule_rows)
    topology_bytes = _csv_bytes(TOPOLOGY_COLUMNS, topology_rows)
    manifest_value = _build_manifest(
        input_manifest_path=manifest_path,
        molecules_path=molecules_path,
        source_rows_path=source_rows_path,
        source_manifest=manifest,
        records=records,
        partitions=partitions,
        train_accepted=train_accepted,
        test_accepted=test_accepted,
        train_structures=train_structures,
        components=components,
        scaffolds=scaffolds,
        overlap_hashes=overlap_hashes,
        pair_count=pair_count,
        edge_count=edge_count,
        scaffold_crossing=scaffold_crossing,
        molecule_rows=molecule_rows,
        topology_rows=topology_rows,
        molecule_bytes=molecule_bytes,
        topology_bytes=topology_bytes,
    )
    manifest_bytes = (
        json.dumps(manifest_value, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

    output_directory.mkdir(parents=True)
    molecule_audit_path = output_directory / "molecule_audit.csv"
    training_topology_path = output_directory / "training_topology.csv"
    output_manifest_path = output_directory / "topology_manifest.json"
    _write_new(molecule_audit_path, molecule_bytes)
    _write_new(training_topology_path, topology_bytes)
    _write_new(output_manifest_path, manifest_bytes)
    return TopologyAuditResult(
        molecule_audit_path=molecule_audit_path,
        training_topology_path=training_topology_path,
        manifest_path=output_manifest_path,
        training_molecules=len(train_records),
        topology_rows=len(topology_rows),
        similarity_components=len(set(components.values())),
        scaffold_groups=len(set(scaffolds.values())),
    )


def _verify_r1_input(
    manifest_path: Path, molecules_path: Path, source_rows_path: Path
) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != OPENADMET_ADAPTER_SCHEMA_VERSION:
        raise OpenADMETTopologyError("unsupported R1 adapter manifest schema")
    if manifest.get("dataset_id") != OPENADMET_DATASET_ID:
        raise OpenADMETTopologyError("R1 adapter dataset identity mismatch")
    source_revision = manifest.get("source_revision")
    if not isinstance(source_revision, str) or not source_revision:
        raise OpenADMETTopologyError("R1 source revision must be non-empty")
    if manifest.get("deterministic") is not True:
        raise OpenADMETTopologyError("R1 manifest must declare deterministic output")
    source_files = manifest.get("source_files")
    if (
        not isinstance(source_files, list)
        or tuple(_text(item, "path", "R1 source file") for item in source_files)
        != OPENADMET_SOURCE_FILES
    ):
        raise OpenADMETTopologyError("R1 source file receipt list is invalid")
    for item in source_files:
        _digest(item, "sha256", "R1 source file")
        _nonnegative_int(item, "rows", "R1 source file")
        headers = item.get("header")
        if (
            not isinstance(headers, list)
            or not headers
            or not all(isinstance(value, str) for value in headers)
        ):
            raise OpenADMETTopologyError("R1 source file header receipt is invalid")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict) or set(outputs) != {
        "molecules_input.csv",
        "source_rows.csv",
    }:
        raise OpenADMETTopologyError("R1 output receipt names are invalid")
    for name, path in (
        ("molecules_input.csv", molecules_path),
        ("source_rows.csv", source_rows_path),
    ):
        item = outputs.get(name)
        if not isinstance(item, dict):
            raise OpenADMETTopologyError(f"missing R1 output receipt: {name}")
        expected_hash = _digest(item, "sha256", f"R1 output {name}")
        expected_rows = _nonnegative_int(item, "rows", f"R1 output {name}")
        data = _read_bytes(path, name)
        actual_hash = sha256(data).hexdigest()
        if actual_hash != expected_hash:
            raise OpenADMETTopologyError(
                f"R1 output hash mismatch for {name}: expected {expected_hash}, "
                f"got {actual_hash}"
            )
        actual_rows = _line_count(data, name)
        if actual_rows != expected_rows:
            raise OpenADMETTopologyError(
                f"R1 output row count mismatch for {name}: expected "
                f"{expected_rows}, got {actual_rows}"
            )
    counts = manifest.get("counts")
    if not isinstance(counts, dict):
        raise OpenADMETTopologyError("R1 counts must be an object")
    if counts.get("molecules") != outputs["molecules_input.csv"]["rows"]:
        raise OpenADMETTopologyError("R1 molecule count receipt mismatch")
    if counts.get("source_rows") != outputs["source_rows.csv"]["rows"]:
        raise OpenADMETTopologyError("R1 source-row count receipt mismatch")
    return manifest


def _read_molecule_inputs(
    path: Path, manifest: Mapping[str, Any]
) -> list[MoleculeInput]:
    expected_rows = cast(Mapping[str, Any], manifest["outputs"])["molecules_input.csv"][
        "rows"
    ]
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != MOLECULE_INPUT_COLUMNS:
                raise OpenADMETTopologyError(
                    "molecules_input.csv columns do not match R1 adapter"
                )
            rows: list[MoleculeInput] = []
            for line_number, row in enumerate(reader, start=2):
                if None in row or any(value is None for value in row.values()):
                    raise OpenADMETTopologyError(
                        f"molecules_input.csv row {line_number} has wrong field count"
                    )
                try:
                    rows.append(MoleculeInput.from_mapping(cast(dict[str, str], row)))
                except ValueError as exc:
                    raise OpenADMETTopologyError(
                        f"invalid molecule input row {line_number}: {exc}"
                    ) from exc
    except OSError as exc:
        raise OpenADMETTopologyError(f"cannot read {path}: {exc}") from exc
    if len(rows) != expected_rows:
        raise OpenADMETTopologyError(
            f"molecules_input.csv row count changed: expected {expected_rows}, "
            f"got {len(rows)}"
        )
    identifiers = [row.molecule_id for row in rows]
    if len(set(identifiers)) != len(identifiers):
        raise OpenADMETTopologyError(
            "molecules_input.csv contains duplicate identities"
        )
    return rows


def _partition_from_provenance(provenance: str) -> str:
    try:
        value = json.loads(provenance)
    except (TypeError, json.JSONDecodeError) as exc:
        raise OpenADMETTopologyError("malformed molecule provenance") from exc
    if not isinstance(value, dict) or not isinstance(value.get("occurrences"), list):
        raise OpenADMETTopologyError("molecule provenance occurrences are malformed")
    occurrences = value["occurrences"]
    if not occurrences:
        raise OpenADMETTopologyError("molecule provenance has no occurrences")
    source_files: set[str] = set()
    for occurrence in occurrences:
        if not isinstance(occurrence, dict):
            raise OpenADMETTopologyError("molecule provenance occurrence is malformed")
        source_file = occurrence.get("source_file")
        if (
            not isinstance(source_file, str)
            or source_file not in OPENADMET_SOURCE_FILES
        ):
            raise OpenADMETTopologyError(
                "molecule provenance has an unknown source filename"
            )
        source_files.add(source_file)
    if TEST_SOURCE_FILE in source_files and len(source_files) == 1:
        return "test"
    if TEST_SOURCE_FILE not in source_files and source_files:
        return "train"
    raise OpenADMETTopologyError(
        "molecule provenance ambiguously mixes blinded and training sources"
    )


def _unique_structures(records: Sequence[MoleculeRecord]) -> dict[str, str]:
    structures: dict[str, str] = {}
    for record in records:
        structure_hash = record.standardized_structure_hash
        structure = record.standardized_structure
        if structure_hash is None or structure is None:
            raise OpenADMETTopologyError(
                f"accepted molecule lacks standardized data: {record.molecule_id}"
            )
        previous = structures.setdefault(structure_hash, structure)
        if previous != structure:
            raise OpenADMETTopologyError(
                f"standardized hash maps to multiple structures: {structure_hash}"
            )
    return structures


def _scaffold_groups(structures: Mapping[str, str]) -> dict[str, str]:
    groups: dict[str, str] = {}
    with rdBase.BlockLogs():
        for structure_hash in sorted(structures):
            molecule = Chem.MolFromSmiles(structures[structure_hash])
            if molecule is None:
                raise OpenADMETTopologyError(
                    f"cannot parse accepted standardized structure: {structure_hash}"
                )
            scaffold = MurckoScaffold.MurckoScaffoldSmiles(
                mol=molecule, includeChirality=False
            )
            material = (
                f"bemis_murcko_scaffold:{scaffold}"
                if scaffold
                else f"acyclic_exact_structure:{structures[structure_hash]}"
            )
            groups[structure_hash] = _digest_text(material)
    return groups


def _similarity_groups(
    structures: Mapping[str, str], scaffolds: Mapping[str, str]
) -> tuple[dict[str, str], int, int, int]:
    ordered_hashes = sorted(structures)
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=MORGAN_RADIUS,
        fpSize=MORGAN_FP_SIZE,
        includeChirality=MORGAN_INCLUDE_CHIRALITY,
    )
    fingerprints = []
    with rdBase.BlockLogs():
        for structure_hash in ordered_hashes:
            molecule = Chem.MolFromSmiles(structures[structure_hash])
            if molecule is None:
                raise OpenADMETTopologyError(
                    f"cannot fingerprint accepted standardized structure: "
                    f"{structure_hash}"
                )
            fingerprints.append(generator.GetFingerprint(molecule))

    parent = list(range(len(ordered_hashes)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    edge_count = 0
    scaffold_crossing = 0
    pair_count = len(ordered_hashes) * (len(ordered_hashes) - 1) // 2
    for index, fingerprint in enumerate(fingerprints[:-1]):
        similarities = DataStructs.BulkTanimotoSimilarity(
            fingerprint, fingerprints[index + 1 :]
        )
        if len(similarities) != len(fingerprints) - index - 1:
            raise OpenADMETTopologyError("BulkTanimotoSimilarity returned wrong length")
        for offset, similarity in enumerate(similarities, start=index + 1):
            if similarity >= SIMILARITY_THRESHOLD:
                edge_count += 1
                if (
                    scaffolds[ordered_hashes[index]]
                    != scaffolds[ordered_hashes[offset]]
                ):
                    scaffold_crossing += 1
                union(index, offset)

    members: dict[int, list[str]] = defaultdict(list)
    for index, structure_hash in enumerate(ordered_hashes):
        members[find(index)].append(structure_hash)
    components: dict[str, str] = {}
    for hashes in members.values():
        hashes.sort()
        component_hash = _digest_text(_SIMILARITY_SPEC + "\n" + "\n".join(hashes))
        for structure_hash in hashes:
            components[structure_hash] = component_hash
    if len(components) != len(ordered_hashes):
        raise OpenADMETTopologyError("similarity component assignment is incomplete")
    return components, pair_count, edge_count, scaffold_crossing


def _topology_rows(
    records: Sequence[MoleculeRecord],
    components: Mapping[str, str],
    scaffolds: Mapping[str, str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for record in records:
        structure_hash = cast(str, record.standardized_structure_hash)
        rows.append(
            {
                "molecule_id": record.molecule_id,
                "standardized_structure_hash": structure_hash,
                "similarity_component_hash": components[structure_hash],
                "scaffold_group_hash": scaffolds[structure_hash],
            }
        )
    rows.sort(key=lambda row: row["molecule_id"])
    return rows


def _molecule_audit_rows(
    records: Sequence[MoleculeRecord], partitions: Mapping[str, str]
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for record in records:
        values = record.to_dict()
        row = {
            "molecule_id": record.molecule_id,
            "partition": partitions[record.molecule_id],
            **{
                column: _csv_value(values[column]) for column in MOLECULE_OUTPUT_COLUMNS
            },
            "raw_structure_sha256": _digest_text(record.raw_structure),
        }
        rows.append(row)
    rows.sort(key=lambda row: row["molecule_id"])
    return rows


def _build_manifest(
    *,
    input_manifest_path: Path,
    molecules_path: Path,
    source_rows_path: Path,
    source_manifest: Mapping[str, Any],
    records: Sequence[MoleculeRecord],
    partitions: Mapping[str, str],
    train_accepted: Sequence[MoleculeRecord],
    test_accepted: Sequence[MoleculeRecord],
    train_structures: Mapping[str, str],
    components: Mapping[str, str],
    scaffolds: Mapping[str, str],
    overlap_hashes: Sequence[str],
    pair_count: int,
    edge_count: int,
    scaffold_crossing: int,
    molecule_rows: Sequence[Mapping[str, str]],
    topology_rows: Sequence[Mapping[str, str]],
    molecule_bytes: bytes,
    topology_bytes: bytes,
) -> dict[str, Any]:
    warning_counts = Counter(w for record in records for w in record.warnings)
    test_hashes = {
        cast(str, record.standardized_structure_hash) for record in test_accepted
    }
    raw_unique_count = len({record.raw_structure for record in records})
    standardized_unique_count = len(set(train_structures) | test_hashes)
    source_membership_counts: Counter[str] = Counter(
        file
        for record in records
        for file in {
            item["source_file"] for item in json.loads(record.provenance)["occurrences"]
        }
    )
    accepted_train_groups = _identity_groups(train_accepted, components)
    accepted_scaffold_groups = _identity_groups(train_accepted, scaffolds)
    component_stats = _group_stats(accepted_train_groups)
    scaffold_stats = _group_stats(accepted_scaffold_groups)
    direct_counts: Counter[str] = Counter()
    for record in train_accepted:
        if _has_direct_source(record.provenance):
            structure_hash = cast(str, record.standardized_structure_hash)
            direct_counts[components[structure_hash]] += 1
    direct_upper_bound = sum(count >= 2 for count in direct_counts.values())
    quarantined_test = sum(
        partitions[record.molecule_id] == "test"
        and record.status is MoleculeStatus.QUARANTINED
        for record in records
    )
    blocked_reasons: list[str] = []
    if overlap_hashes:
        blocked_reasons.append("standardized_train_test_overlap")
    if quarantined_test:
        blocked_reasons.append("test_molecule_quarantine")
    return {
        "schema_version": TOPOLOGY_SCHEMA_VERSION,
        "source_revision": source_manifest["source_revision"],
        "rdkit_version": rdBase.rdkitVersion,
        "standardization_version": STANDARDIZATION_VERSION,
        "inputs": {
            "r1_manifest_sha256": _file_hash(input_manifest_path),
            "molecules_input.csv": {
                "sha256": _file_hash(molecules_path),
                "rows": len(molecule_rows),
            },
            "source_rows.csv": {
                "sha256": _file_hash(source_rows_path),
                "rows": source_manifest["outputs"]["source_rows.csv"]["rows"],
                "parsed": False,
            },
        },
        "counts": {
            "molecules_total": len(records),
            "train_molecules": sum(
                partitions[record.molecule_id] == "train" for record in records
            ),
            "test_molecules": sum(
                partitions[record.molecule_id] == "test" for record in records
            ),
            "accepted_train_molecules": len(train_accepted),
            "accepted_test_molecules": len(test_accepted),
            "quarantined_train_molecules": sum(
                record.status is MoleculeStatus.QUARANTINED
                and partitions[record.molecule_id] == "train"
                for record in records
            ),
            "quarantined_test_molecules": quarantined_test,
            "standardized_train_unique_structures": len(train_structures),
            "standardized_test_unique_structures": len(test_hashes),
            "raw_structure_unique_count": raw_unique_count,
            "standardized_structure_unique_count": standardized_unique_count,
            "source_file_membership_unique_molecules": dict(
                sorted(source_membership_counts.items())
            ),
            "topology_rows": len(topology_rows),
        },
        "audit_counts": {
            "standardization_changes": sum(
                record.standardization_changed for record in records
            ),
            "standardized_duplicates": sum(
                record.duplicate_of is not None for record in records
            ),
            "quarantined": sum(
                record.status is MoleculeStatus.QUARANTINED for record in records
            ),
            "warning_counts": dict(sorted(warning_counts.items())),
        },
        "exact_standardized_train_test_overlap": {
            "count": len(overlap_hashes),
            "hashes": list(overlap_hashes),
        },
        "similarity": {
            "specification": _SIMILARITY_SPEC,
            "pair_count": pair_count,
            "qualifying_edge_count": edge_count,
            "component_count": len(set(components.values())),
            "component_crossing_edge_count": 0,
            "groups": component_stats,
            "direct_source_membership_upper_bound": {
                "source_file": DIRECT_SOURCE_FILE,
                "components_with_at_least_two_molecule_identities": direct_upper_bound,
                "viability_status": (
                    "CANDIDATE_TOPOLOGY_SUPPORTED_FOR_VIABILITY_AUDIT"
                    if direct_upper_bound >= 5
                    else "TOPOLOGY_UNDERPOWERED"
                ),
                "interpretation": (
                    "upper bound for a viability audit only; not endpoint "
                    "eligibility, family validation, or a family label"
                ),
            },
        },
        "scaffold": {
            "specification": (
                "Bemis-Murcko scaffold without chirality; acyclic fallback is "
                "the exact standardized structure"
            ),
            "group_count": len(set(scaffolds.values())),
            "groups": scaffold_stats,
            "similarity_edges_crossing_scaffold_groups": scaffold_crossing,
        },
        "outputs": {
            "molecule_audit.csv": {
                "sha256": sha256(molecule_bytes).hexdigest(),
                "rows": len(molecule_rows),
            },
            "training_topology.csv": {
                "sha256": sha256(topology_bytes).hexdigest(),
                "rows": len(topology_rows),
            },
        },
        "downstream_modeling": {
            "blocked": bool(blocked_reasons),
            "reasons": blocked_reasons,
        },
        "scope": {
            "family_semantics_authority": False,
            "split_authority": False,
            "episode_authority": False,
            "label_authority": False,
            "metric_authority": False,
            "model_authority": False,
            "tdi_authority": False,
            "transductive_authority": False,
            "submission_authority": False,
        },
        "deterministic": True,
    }


def _identity_groups(
    records: Sequence[MoleculeRecord], group_by_hash: Mapping[str, str]
) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for record in records:
        structure_hash = cast(str, record.standardized_structure_hash)
        groups[group_by_hash[structure_hash]].append(record.molecule_id)
    for members in groups.values():
        members.sort()
    return dict(groups)


def _group_stats(groups: Mapping[str, Sequence[str]]) -> dict[str, Any]:
    sizes = sorted(len(members) for members in groups.values())
    total = sum(sizes)
    multi_members = sum(size for size in sizes if size >= 2)
    buckets = {
        "1": sum(size == 1 for size in sizes),
        "2-4": sum(2 <= size <= 4 for size in sizes),
        "5-9": sum(5 <= size <= 9 for size in sizes),
        "10+": sum(size >= 10 for size in sizes),
    }
    return {
        "group_count": len(sizes),
        "member_count": total,
        "size_min": min(sizes) if sizes else 0,
        "size_max": max(sizes) if sizes else 0,
        "largest_group_share": (max(sizes) / total) if sizes else 0.0,
        "size_buckets": buckets,
        "multi_member_group_count": sum(size >= 2 for size in sizes),
        "multi_member_molecule_count": multi_members,
        "multi_member_coverage": (multi_members / total) if total else 0.0,
    }


def _has_direct_source(provenance: str) -> bool:
    value = json.loads(provenance)
    occurrences = value["occurrences"]
    return any(
        isinstance(item, dict) and item.get("source_file") == DIRECT_SOURCE_FILE
        for item in occurrences
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OpenADMETTopologyError(f"cannot read manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise OpenADMETTopologyError("manifest must be an object")
    return cast(dict[str, Any], value)


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise OpenADMETTopologyError(f"cannot read {label}: {exc}") from exc


def _line_count(data: bytes, label: str) -> int:
    if not data:
        raise OpenADMETTopologyError(f"{label} is empty")
    lines = data.splitlines()
    if not lines:
        raise OpenADMETTopologyError(f"{label} has no lines")
    return len(lines) - 1


def _file_hash(path: Path) -> str:
    return sha256(_read_bytes(path, path.name)).hexdigest()


def _text(value: Any, key: str, label: str) -> str:
    if (
        not isinstance(value, dict)
        or not isinstance(value.get(key), str)
        or not value[key]
    ):
        raise OpenADMETTopologyError(f"{label}.{key} must be non-empty text")
    return cast(str, value[key])


def _digest(value: Any, key: str, label: str) -> str:
    item = _text(value, key, label).lower()
    if len(item) != 64 or any(char not in "0123456789abcdef" for char in item):
        raise OpenADMETTopologyError(f"{label}.{key} must be a SHA-256 digest")
    return item


def _nonnegative_int(value: Any, key: str, label: str) -> int:
    item = value.get(key) if isinstance(value, dict) else None
    if isinstance(item, bool) or not isinstance(item, int) or item < 0:
        raise OpenADMETTopologyError(f"{label}.{key} must be a non-negative integer")
    return item


def _digest_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, tuple)):
        return json.dumps(value, separators=(",", ":"))
    return str(value)


def _csv_bytes(columns: Sequence[str], rows: Sequence[Mapping[str, str]]) -> bytes:
    import io

    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode("utf-8")


def _write_new(path: Path, data: bytes) -> None:
    path.write_bytes(data)

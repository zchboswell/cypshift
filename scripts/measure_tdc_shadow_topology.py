#!/usr/bin/env python3
"""Measure the frozen TDC CYP shadow topology without changing assignments."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import rdkit
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

ROOT = Path(__file__).resolve().parents[1]
SHADOW_ROOT = ROOT / "artifacts/benchmarks/tdc-cyp-shadow-v1"
SHADOW_ROWS = SHADOW_ROOT / "shadow_rows.csv"
SHADOW_MANIFEST = SHADOW_ROOT / "shadow_manifest.json"
SHADOW_CONTRACT = ROOT / "benchmarks/tdc_cyp_shadow_v1_contract.json"
OUTPUT_ROOT = ROOT / "artifacts/benchmarks/tdc-cyp-shadow-topology-v1"

EXPECTED_ROWS_SHA256 = (
    "b633af0cbd5aa98a03ae77eb3e021eb32b441ae8133e24a2c9eb85394e41bc5f"
)
EXPECTED_MANIFEST_SHA256 = (
    "3eb972713d88e08420134e7776755d4e62510a5250edf99edc2021272c112656"
)
EXPECTED_CONTRACT_SHA256 = (
    "9f0909dbc96672f49f9e7d0a9f802c268d33c3174470e08dc4a3f1846bf3cf0b"
)
EXPECTED_PYTHON = "3.11.14"
EXPECTED_RDKIT = "2026.03.5"
EXPECTED_NUMPY = "2.4.6"
TASKS = ("cyp2c9_veith", "cyp2d6_veith", "cyp3a4_veith")
PROTOCOLS = ("scaffold", "community")
REPEATS = (0, 1, 2)
THRESHOLDS = (0.60, 0.70, 0.80, 0.90)

ROW_COLUMNS = (
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

TOPOLOGY_COLUMNS = (
    "task",
    "protocol",
    "repeat",
    "standardized_structure_hash",
    "group_hash",
    "validation_source_rows",
    "max_train_tanimoto",
    "training_neighbor_at_or_above_0_60",
    "training_neighbor_at_or_above_0_70",
    "training_neighbor_at_or_above_0_80",
    "training_neighbor_at_or_above_0_90",
)

SUMMARY_COLUMNS = (
    "task",
    "protocol",
    "repeat",
    "training_source_rows",
    "training_structures",
    "validation_source_rows",
    "validation_structures",
    "exact_raw_crossing_forms",
    "standardized_crossing_structures",
    "prevalence",
    "max_similarity_minimum",
    "max_similarity_median",
    "max_similarity_mean",
    "max_similarity_maximum",
    "neighbors_at_or_above_0_60",
    "proportion_at_or_above_0_60",
    "neighbors_at_or_above_0_70",
    "proportion_at_or_above_0_70",
    "neighbors_at_or_above_0_80",
    "proportion_at_or_above_0_80",
    "neighbors_at_or_above_0_90",
    "proportion_at_or_above_0_90",
)

GROUP_COLUMNS = (
    "protocol",
    "group_hash",
    "source_rows",
    "unique_standardized_structures",
    "task_count",
)


class TopologyError(RuntimeError):
    """Raised when a frozen topology invariant fails."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TopologyError(message)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    _require(isinstance(value, dict), f"{path.name} must contain an object")
    return cast(dict[str, Any], value)


def _clean_revision() -> str:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    _require(not status.strip(), "tracked worktree must be clean")
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _require(len(revision) == 40, "source revision must be a full Git SHA")
    return revision


def _read_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _require(
            tuple(reader.fieldnames or ()) == ROW_COLUMNS, "shadow row schema drift"
        )
        for row in reader:
            _require(None not in row, "shadow row has an extra field")
            _require(
                all(value is not None for value in row.values()), "shadow row is short"
            )
            rows.append({key: str(value) for key, value in row.items()})
    _require(len(rows) == 30_038, "shadow row count drift")
    _require(
        len({row["molecule_id"] for row in rows}) == len(rows),
        "shadow molecule identities are not unique",
    )
    _require({row["task"] for row in rows} == set(TASKS), "shadow task set drift")
    return rows


def _verify_inputs() -> tuple[dict[str, Any], list[dict[str, str]], str]:
    _require(_sha256(SHADOW_ROWS) == EXPECTED_ROWS_SHA256, "shadow rows hash drift")
    _require(
        _sha256(SHADOW_MANIFEST) == EXPECTED_MANIFEST_SHA256,
        "shadow manifest hash drift",
    )
    _require(
        _sha256(SHADOW_CONTRACT) == EXPECTED_CONTRACT_SHA256,
        "shadow contract hash drift",
    )
    _require(platform.python_version() == EXPECTED_PYTHON, "Python version drift")
    _require(rdkit.__version__ == EXPECTED_RDKIT, "RDKit version drift")
    _require(np.__version__ == EXPECTED_NUMPY, "NumPy version drift")

    manifest = _load_json(SHADOW_MANIFEST)
    _require(
        manifest["outputs"]["shadow_rows.csv"] == EXPECTED_ROWS_SHA256,
        "manifest does not bind shadow rows",
    )
    _require(
        manifest["contract"]["sha256"] == EXPECTED_CONTRACT_SHA256,
        "manifest does not bind shadow contract",
    )
    _require(manifest["accounting"]["public_test_labels_parsed"] == 0, "public labels")
    rows = _read_rows(SHADOW_ROWS)
    return manifest, rows, _clean_revision()


def _unique_structures(
    rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, str], dict[str, set[str]]]:
    structures: dict[str, str] = {}
    raw_by_hash: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        structure_hash = row["standardized_structure_hash"]
        structure = row["standardized_structure"]
        _require(
            hashlib.sha256(row["raw_structure"].encode("utf-8")).hexdigest()
            == row["raw_structure_sha256"],
            "raw structure hash mismatch",
        )
        _require(
            hashlib.sha256(structure.encode("utf-8")).hexdigest() == structure_hash,
            "standardized structure hash mismatch",
        )
        previous = structures.setdefault(structure_hash, structure)
        _require(
            previous == structure, "one hash maps to multiple standardized structures"
        )
        raw_by_hash[structure_hash].add(row["raw_structure"])
    return structures, raw_by_hash


def _verify_group_assignments(rows: Sequence[Mapping[str, str]]) -> None:
    for protocol in PROTOCOLS:
        group_column = f"{protocol}_group_hash"
        for repeat in REPEATS:
            folds: dict[str, set[int]] = defaultdict(set)
            for row in rows:
                folds[row[group_column]].add(_fold(row, protocol, repeat))
            _require(
                all(len(values) == 1 for values in folds.values()),
                f"{protocol} group crosses repeat {repeat} folds",
            )


def _fingerprints(structures: Mapping[str, str]) -> dict[str, Any]:
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=2,
        fpSize=2048,
        includeChirality=True,
        countSimulation=False,
    )
    fingerprints: dict[str, Any] = {}
    for structure_hash in sorted(structures):
        molecule = Chem.MolFromSmiles(structures[structure_hash])
        _require(
            molecule is not None and molecule.GetNumAtoms() > 0,
            "structure parse failure",
        )
        fingerprints[structure_hash] = generator.GetFingerprint(molecule)
    return fingerprints


def _fold(row: Mapping[str, str], protocol: str, repeat: int) -> int:
    return int(row[f"{protocol}_repeat_{repeat}_outer_fold"])


def _format_float(value: float) -> str:
    return format(value, ".17g")


def _manifest_outer_record(
    manifest: Mapping[str, Any], task: str, protocol: str, repeat: int
) -> Mapping[str, Any]:
    records = manifest["validation"][task][protocol][str(repeat)]["outer_folds"]
    return next(item for item in records if item["fold"] == 0)


def measure_topology(
    rows: Sequence[Mapping[str, str]],
    manifest: Mapping[str, Any],
) -> tuple[list[dict[str, object]], list[dict[str, object]], int]:
    structures, _ = _unique_structures(rows)
    _verify_group_assignments(rows)
    fingerprints = _fingerprints(structures)
    topology: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    comparisons = 0

    for task in TASKS:
        task_rows = [row for row in rows if row["task"] == task]
        for protocol in PROTOCOLS:
            group_column = f"{protocol}_group_hash"
            for repeat in REPEATS:
                training_rows = [
                    row for row in task_rows if _fold(row, protocol, repeat) != 0
                ]
                validation_rows = [
                    row for row in task_rows if _fold(row, protocol, repeat) == 0
                ]
                training_hashes = sorted(
                    {row["standardized_structure_hash"] for row in training_rows}
                )
                validation_hashes = sorted(
                    {row["standardized_structure_hash"] for row in validation_rows}
                )
                crossing = set(training_hashes) & set(validation_hashes)
                raw_crossing = {row["raw_structure"] for row in training_rows} & {
                    row["raw_structure"] for row in validation_rows
                }
                _require(not crossing, "standardized duplicate crosses outer boundary")
                _require(not raw_crossing, "exact raw structure crosses outer boundary")
                training_fingerprints = [fingerprints[key] for key in training_hashes]
                max_similarities: list[float] = []
                counts = {threshold: 0 for threshold in THRESHOLDS}

                for structure_hash in validation_hashes:
                    similarities = DataStructs.BulkTanimotoSimilarity(
                        fingerprints[structure_hash], training_fingerprints
                    )
                    _require(
                        bool(similarities), "outer training structure set is empty"
                    )
                    maximum = float(max(similarities))
                    max_similarities.append(maximum)
                    comparisons += len(training_fingerprints)
                    source_rows = sum(
                        row["standardized_structure_hash"] == structure_hash
                        for row in validation_rows
                    )
                    group_hashes = {
                        row[group_column]
                        for row in validation_rows
                        if row["standardized_structure_hash"] == structure_hash
                    }
                    _require(
                        len(group_hashes) == 1, "validation structure crosses groups"
                    )
                    record: dict[str, object] = {
                        "task": task,
                        "protocol": protocol,
                        "repeat": repeat,
                        "standardized_structure_hash": structure_hash,
                        "group_hash": next(iter(group_hashes)),
                        "validation_source_rows": source_rows,
                        "max_train_tanimoto": _format_float(maximum),
                    }
                    for threshold in THRESHOLDS:
                        supported = maximum >= threshold
                        counts[threshold] += int(supported)
                        record[
                            f"training_neighbor_at_or_above_{threshold:.2f}".replace(
                                ".", "_"
                            )
                        ] = int(supported)
                    topology.append(record)

                validation_count = len(validation_hashes)
                frozen_outer = _manifest_outer_record(manifest, task, protocol, repeat)
                _require(
                    int(frozen_outer["rows"]) == len(validation_rows),
                    "validation row count differs from frozen summary",
                )
                summary: dict[str, object] = {
                    "task": task,
                    "protocol": protocol,
                    "repeat": repeat,
                    "training_source_rows": len(training_rows),
                    "training_structures": len(training_hashes),
                    "validation_source_rows": len(validation_rows),
                    "validation_structures": validation_count,
                    "exact_raw_crossing_forms": len(raw_crossing),
                    "standardized_crossing_structures": len(crossing),
                    "prevalence": _format_float(float(frozen_outer["prevalence"])),
                    "max_similarity_minimum": _format_float(min(max_similarities)),
                    "max_similarity_median": _format_float(
                        float(statistics.median(max_similarities))
                    ),
                    "max_similarity_mean": _format_float(
                        float(statistics.fmean(max_similarities))
                    ),
                    "max_similarity_maximum": _format_float(max(max_similarities)),
                }
                for threshold in THRESHOLDS:
                    suffix = f"{threshold:.2f}".replace(".", "_")
                    summary[f"neighbors_at_or_above_{suffix}"] = counts[threshold]
                    summary[f"proportion_at_or_above_{suffix}"] = _format_float(
                        counts[threshold] / validation_count
                    )
                summaries.append(summary)
    return topology, summaries, comparisons


def group_sizes(rows: Sequence[Mapping[str, str]]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for protocol in PROTOCOLS:
        groups: dict[str, list[Mapping[str, str]]] = defaultdict(list)
        for row in rows:
            groups[row[f"{protocol}_group_hash"]].append(row)
        for group_hash in sorted(groups):
            members = groups[group_hash]
            records.append(
                {
                    "protocol": protocol,
                    "group_hash": group_hash,
                    "source_rows": len(members),
                    "unique_standardized_structures": len(
                        {row["standardized_structure_hash"] for row in members}
                    ),
                    "task_count": len({row["task"] for row in members}),
                }
            )
    return records


def _write_csv(
    path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, object]]
) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _summary_payload(
    rows: Sequence[Mapping[str, str]],
    manifest: Mapping[str, Any],
    topology: Sequence[Mapping[str, object]],
    summaries: Sequence[Mapping[str, object]],
    groups: Sequence[Mapping[str, object]],
    comparisons: int,
    revision: str,
) -> dict[str, Any]:
    structures, raw_by_hash = _unique_structures(rows)
    duplicate_cells = sum(count > 1 for count in _cell_counts(rows).values())
    collision_counts = [
        len(values) for values in raw_by_hash.values() if len(values) > 1
    ]
    frozen = manifest["duplicate_and_conflicting_labels"]
    frozen_population = manifest["population"]
    frozen_groups = manifest["groups"]
    _require(
        duplicate_cells == frozen["structure_task_cells_with_duplicate_rows"],
        "duplicate count drift",
    )
    _require(
        len(collision_counts)
        == frozen_population["standardized_hashes_with_multiple_distinct_raw_smiles"],
        "raw-SMILES collision count drift",
    )
    _require(
        sum(count - 1 for count in collision_counts)
        == frozen_population["excess_distinct_raw_smiles_for_those_hashes"],
        "raw-SMILES excess count drift",
    )
    _require(
        max(collision_counts)
        == frozen_population["maximum_raw_smiles_per_standardized_hash"],
        "raw-SMILES maximum multiplicity drift",
    )
    scaffold_groups = sum(record["protocol"] == "scaffold" for record in groups)
    community_groups = sum(record["protocol"] == "community" for record in groups)
    _require(scaffold_groups == frozen_groups["scaffold"], "scaffold group count drift")
    _require(
        community_groups == frozen_groups["community"], "community group count drift"
    )
    output = {
        "schema_version": "cypshift.tdc_cyp_shadow_topology.v1",
        "benchmark_id": "TDC-CYP-shadow-v1",
        "source_revision": revision,
        "inputs": {
            "shadow_rows.csv": EXPECTED_ROWS_SHA256,
            "shadow_manifest.json": EXPECTED_MANIFEST_SHA256,
            "tdc_cyp_shadow_v1_contract.json": EXPECTED_CONTRACT_SHA256,
        },
        "fingerprint": {
            "kind": "binary_bit_vector",
            "radius": 2,
            "dimensions": 2048,
            "include_chirality": True,
        },
        "environment": {
            "python": platform.python_version(),
            "rdkit": rdkit.__version__,
            "numpy": np.__version__,
            "machine": platform.machine(),
            "system": platform.system(),
        },
        "population": {
            "source_rows": len(rows),
            "unique_standardized_structures": len(structures),
            "standardized_hashes_with_multiple_distinct_raw_smiles": len(
                collision_counts
            ),
            "excess_distinct_raw_smiles_for_those_hashes": sum(
                count - 1 for count in collision_counts
            ),
            "maximum_raw_smiles_per_standardized_hash": max(collision_counts),
            "structure_task_cells_with_duplicate_rows": duplicate_cells,
            "structure_task_cells_with_conflicting_labels": frozen[
                "structure_task_cells_with_conflicting_labels"
            ],
        },
        "topology": {
            "task_protocol_repeat_cells": len(summaries),
            "validation_structure_records": len(topology),
            "tanimoto_pair_comparisons": comparisons,
            "scaffold_group_records": scaffold_groups,
            "community_group_records": community_groups,
        },
        "sensitivity_population_contract": {
            "official_row_weighted": "Use validation_source_rows as row multiplicity.",
            "unique_structure_task_cell": "Use each topology row once.",
            "conflict_isolated": (
                "Identify conflicting cells only after predictions are hashed and the "
                "receipt-bound scoring targets are opened; this topology process parses no label."
            ),
            "low_neighbor": "Select max_train_tanimoto below 0.60.",
            "group_influence": "Join the protocol-specific group_hash and remove one group at a time.",
        },
        "accounting": {
            "train_val_labels_parsed": 0,
            "public_test_rows_parsed": 0,
            "public_test_labels_parsed": 0,
            "feature_matrices_generated": 0,
            "model_fits": 0,
            "predictions": 0,
            "metric_evaluations": 0,
        },
    }
    return output


def _cell_counts(rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        counts[(row["task"], row["standardized_structure_hash"])] += 1
    return counts


def run() -> Path:
    _require(not OUTPUT_ROOT.exists(), f"output already exists: {OUTPUT_ROOT}")
    manifest, rows, revision = _verify_inputs()
    topology, summaries, comparisons = measure_topology(rows, manifest)
    groups = group_sizes(rows)

    OUTPUT_ROOT.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=".tdc-cyp-shadow-topology-v1-", dir=OUTPUT_ROOT.parent)
    )
    try:
        _write_csv(staging / "validation_topology.csv", TOPOLOGY_COLUMNS, topology)
        _write_csv(staging / "summary.csv", SUMMARY_COLUMNS, summaries)
        _write_csv(staging / "group_sizes.csv", GROUP_COLUMNS, groups)
        output_manifest = _summary_payload(
            rows, manifest, topology, summaries, groups, comparisons, revision
        )
        output_manifest["outputs"] = {
            path.name: _sha256(path)
            for path in sorted(staging.iterdir(), key=lambda item: item.name)
        }
        (staging / "topology_manifest.json").write_bytes(
            _canonical_json(output_manifest)
        )
        for path in staging.iterdir():
            os.chmod(path, 0o444)
        os.chmod(staging, 0o555)
        staging.rename(OUTPUT_ROOT)
    except BaseException:
        os.chmod(staging, 0o755)
        for path in staging.iterdir():
            os.chmod(path, 0o644)
        shutil.rmtree(staging)
        raise
    return OUTPUT_ROOT


def main() -> int:
    try:
        output = run()
    except (OSError, subprocess.CalledProcessError, TopologyError) as error:
        print(f"shadow topology failed: {error}", file=sys.stderr)
        return 1
    print(output.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

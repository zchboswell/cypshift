"""Receipt-bound Phase 3 development data with label-safe family exclusion."""

from __future__ import annotations

import csv
import io
import json
import os
import platform
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from rdkit import Chem, rdBase
from rdkit.Chem.MolStandardize import rdMolStandardize

ENDPOINTS = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
ARRAYS = (
    ("maplight_morgan_count", 1024, "int8"),
    ("maplight_avalon_count", 1024, "int8"),
    ("maplight_erg", 315, "float64"),
    ("maplight_rdkit_descriptors", 200, "float64"),
)


@dataclass(frozen=True)
class LabelFreeMolecule:
    molecule_id: str
    name: str
    source_row_id: str
    raw_smiles: str
    raw_structure_sha256: str
    standardized_structure_hash: str
    primary_group: str
    connectivity_key: str
    tautomer_key: str
    group: str
    reserved: bool
    quarantined: bool


@dataclass(frozen=True)
class DevelopmentData:
    names: tuple[str, ...]
    molecule_ids: tuple[str, ...]
    raw_smiles: tuple[str, ...]
    groups: tuple[str, ...]
    point: NDArray[np.float64]
    low: NDArray[np.float64]
    high: NDArray[np.float64]
    training_mask: NDArray[np.bool_]
    metric_mask: NDArray[np.bool_]
    legacy_features: NDArray[np.float64]
    all_rows: tuple[LabelFreeMolecule, ...]
    receipts: dict[str, str]
    report: dict[str, Any]


def is_reserved(component: str) -> bool:
    material = "openadmet-global-v2-confirmatory-v1|20260824|" + component
    return int.from_bytes(sha256(material.encode()).digest()[:8], "big") % 5 == 0


def _prefix(line: bytes, count: int) -> list[str]:
    """Decode only identity/structure fields; never decode a target suffix."""
    quoted = False
    index = 0
    fields = 0
    while index < len(line):
        byte = line[index]
        if byte == 34:
            if quoted and index + 1 < len(line) and line[index + 1] == 34:
                index += 2
                continue
            quoted = not quoted
        elif byte == 44 and not quoted:
            fields += 1
            if fields == count:
                return next(csv.reader([line[:index].decode("utf-8")]))
        index += 1
    raise ValueError("Incomplete observation identity prefix")


def _identity_keys(smiles: str) -> tuple[str, str, str]:
    with rdBase.BlockLogs():
        molecule = Chem.MolFromSmiles(smiles)
        if molecule is None:
            raise ValueError("Invalid accepted raw structure")
        molecule = rdMolStandardize.FragmentParent(rdMolStandardize.Cleanup(molecule))
        standardized = Chem.MolToSmiles(molecule, isomericSmiles=True)
        # Remove stereo explicitly, preserving isotope identity in canonical SMILES.
        Chem.RemoveStereochemistry(molecule)
        connectivity = Chem.MolToSmiles(molecule, isomericSmiles=True)
        tautomer = rdMolStandardize.TautomerEnumerator().Canonicalize(molecule)
        Chem.RemoveStereochemistry(tautomer)
        canonical = Chem.MolToSmiles(tautomer, isomericSmiles=True)
    return tuple(
        sha256(value.encode()).hexdigest()
        for value in (standardized, connectivity, canonical)
    )  # type: ignore[return-value]


def _union_groups(keys: Sequence[Sequence[str]]) -> list[str]:
    parent = list(range(len(keys)))

    def find(index: int) -> int:
        while index != parent[index]:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    seen: dict[tuple[int, str], int] = {}
    for index, row in enumerate(keys):
        for column, value in enumerate(row):
            prior = seen.setdefault((column, value), index)
            parent[find(index)] = find(prior)
    members: dict[int, list[str]] = {}
    for index, row in enumerate(keys):
        members.setdefault(find(index), []).append("|".join(row))
    digest = {
        root: sha256(
            ("phase3-family-v1\n" + "\n".join(sorted(set(rows)))).encode()
        ).hexdigest()
        for root, rows in members.items()
    }
    return [digest[find(index)] for index in range(len(keys))]


def compile_development(
    source_root: Path,
    receipts: Mapping[str, str],
    *,
    expected_reserved_count: int | None = 997,
) -> DevelopmentData:
    """Authenticate historical inputs; exclude reserved unions before target parsing.

    `receipts` is the public claim's `official_input_receipts` mapping, used only
    as immutable evidence, not as historical execution authorization.
    """
    files = {
        f"{name}.csv": f"{name}_sha256"
        for name in ("feature_rows", "direct_observations", "group_folds")
    }
    files.update({f"{name}.npy": f"{name}_sha256" for name, _, _ in ARRAYS})
    loaded: dict[str, bytes] = {}
    observed: dict[str, str] = {}
    for name, key in files.items():
        data = (source_root / name).read_bytes()
        digest = sha256(data).hexdigest()
        if digest != receipts[key]:
            raise ValueError(f"Source receipt differs: {name}")
        loaded[name], observed[name] = data, digest
    features = list(csv.DictReader(io.StringIO(loaded["feature_rows.csv"].decode())))
    ids = [row["molecule_id"] for row in features]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("Feature identities are empty or duplicated")
    raw = loaded["direct_observations.csv"]
    if b"\r" in raw:
        raise ValueError("Observation serialization contains CR")
    lines = raw.splitlines()
    header = next(csv.reader([lines[0].decode()]))
    if header[:8] != [
        "observation_id",
        "molecule_id",
        "source_row_id",
        "source_file",
        "source_row",
        "source_sha256",
        "endpoint",
        "raw_smiles",
    ]:
        raise ValueError("Observation identity columns differ")
    prefixes: dict[str, list[str]] = {}
    for line in lines[1:]:
        prefix = _prefix(line, 8)
        prior = prefixes.setdefault(prefix[1], prefix)
        if prior[2:6] != prefix[2:6] or prior[7] != prefix[7]:
            raise ValueError("Molecule source identity differs across endpoints")
    if set(prefixes) != set(ids):
        raise ValueError("Observation and feature identities differ")
    identity = [_identity_keys(prefixes[molecule][7]) for molecule in ids]
    for row, keys in zip(features, identity, strict=True):
        if (
            keys[0] != row["standardized_structure_hash"]
            or sha256(prefixes[row["molecule_id"]][7].encode()).hexdigest()
            != row["raw_structure_sha256"]
        ):
            raise ValueError("Accepted structure identity differs in this runtime")
    groups = _union_groups(
        [
            (row["similarity_component_hash"], *keys)
            for row, keys in zip(features, identity, strict=True)
        ]
    )
    reserved = [is_reserved(row["similarity_component_hash"]) for row in features]
    if expected_reserved_count is not None and sum(reserved) != expected_reserved_count:
        raise ValueError("Original reserved membership count differs")
    reserved_groups = {
        group for group, held in zip(groups, reserved, strict=True) if held
    }
    quarantine = [
        not held and group in reserved_groups
        for held, group in zip(reserved, groups, strict=True)
    ]
    all_rows = tuple(
        LabelFreeMolecule(
            molecule,
            molecule,
            prefixes[molecule][2],
            prefixes[molecule][7],
            features[i]["raw_structure_sha256"],
            identity[i][0],
            features[i]["similarity_component_hash"],
            identity[i][1],
            identity[i][2],
            groups[i],
            reserved[i],
            quarantine[i],
        )
        for i, molecule in enumerate(ids)
    )
    take = [i for i in range(len(ids)) if not reserved[i] and not quarantine[i]]
    selected = [all_rows[i] for i in take]
    positions = {row.molecule_id: index for index, row in enumerate(selected)}
    point, low, high = (np.full((len(take), 4), np.nan) for _ in range(3))
    train = np.zeros((len(take), 4), dtype=bool)
    seen_targets: set[tuple[str, str]] = set()
    for line in lines[1:]:
        molecule = _prefix(line, 2)[1]
        if molecule not in positions:
            continue  # No excluded target bytes are decoded or converted.
        row = dict(zip(header, next(csv.reader([line.decode()])), strict=True))
        key = molecule, row["endpoint"]
        if key in seen_targets or key[1] not in ENDPOINTS:
            raise ValueError("Duplicate or unknown development endpoint")
        seen_targets.add(key)
        i, j = positions[molecule], ENDPOINTS.index(key[1])
        for field, array in (("point", point), ("low", low), ("high", high)):
            if row[field] != "":
                value = float(row[field])
                if not np.isfinite(value):
                    raise ValueError("Nonfinite development measurement")
                array[i, j] = value
        if (
            np.isfinite(low[i, j])
            and np.isfinite(high[i, j])
            and low[i, j] > high[i, j]
        ):
            raise ValueError("Reversed development bounds")
        if np.isfinite(point[i, j]) and (
            low[i, j] > point[i, j] or high[i, j] < point[i, j]
        ):
            raise ValueError("Development bounds exclude point")
        train[i, j] = (
            row["point_eligible"] == "true" and row["value_state"] == "complete"
        )
        if train[i, j] and not np.isfinite(point[i, j]):
            raise ValueError("Eligible training point missing")
    if len(seen_targets) != len(take) * 4:
        raise ValueError("Development endpoint coverage incomplete")
    blocks = []
    for name, width, dtype in ARRAYS:
        array = np.load(io.BytesIO(loaded[f"{name}.npy"]), allow_pickle=False)
        if array.shape != (len(ids), width) or array.dtype != np.dtype(dtype):
            raise ValueError(f"Feature layout differs: {name}")
        blocks.append(array[take])
    matrix = np.ascontiguousarray(np.concatenate(blocks, axis=1), dtype=np.float64)
    permitted_nan = np.zeros(2563, dtype=bool)
    permitted_nan[[2363 + index for index in (39, 41, 43, 45)]] = True
    if np.isinf(matrix).any() or (np.isnan(matrix) & ~permitted_nan).any():
        raise ValueError("Unexpected nonfinite feature")
    metric_mask = np.isfinite(point)
    report = {
        "all_molecules": len(ids),
        "original_reserved_molecules": sum(reserved),
        "quarantined_development_molecules": sum(quarantine),
        "development_molecules": len(take),
        "development_families": len(set(row.group for row in selected)),
        "reserved_target_values_parsed": 0,
        "training_targets": train.sum(axis=0).tolist(),
        "metric_targets": metric_mask.sum(axis=0).tolist(),
        "metric_targets_without_training_eligibility": (metric_mask & ~train)
        .sum(axis=0)
        .tolist(),
        "metric_targets_missing_bounds": (
            metric_mask & (~np.isfinite(low) | ~np.isfinite(high))
        )
        .sum(axis=0)
        .tolist(),
    }
    return DevelopmentData(
        tuple(row.name for row in selected),
        tuple(row.molecule_id for row in selected),
        tuple(row.raw_smiles for row in selected),
        tuple(row.group for row in selected),
        point,
        low,
        high,
        train,
        metric_mask,
        matrix,
        all_rows,
        observed,
        report,
    )


def balanced_group_folds(
    groups: Sequence[str],
    training_mask: NDArray[np.bool_],
    folds: int,
    seed: int,
) -> NDArray[np.int64]:
    """Greedily balance per-task eligible counts and molecule counts by family."""
    if training_mask.shape != (len(groups), 4) or folds < 2:
        raise ValueError("Fold input shape or count differs")
    unique = sorted(set(groups))
    if len(unique) < folds:
        raise ValueError("Too few families for requested folds")
    members = {group: np.flatnonzero(np.asarray(groups) == group) for group in unique}
    counts = {
        group: np.append(training_mask[indices].sum(axis=0), len(indices)).astype(float)
        for group, indices in members.items()
    }
    total = np.sum(list(counts.values()), axis=0)
    scale = np.maximum(total / folds, 1)
    rng = np.random.default_rng(seed)
    tie = dict(zip(unique, rng.random(len(unique)), strict=True))
    order = sorted(
        unique, key=lambda group: (-float(np.max(counts[group] / scale)), tie[group])
    )
    loads = np.zeros((folds, 5))
    assignments = np.empty(len(groups), dtype=np.int64)
    fold_order = rng.permutation(folds)
    for group in order:
        costs = [
            float(
                np.sum(
                    ((loads[fold] + counts[group]) / scale) ** 2
                    - (loads[fold] / scale) ** 2
                )
            )
            for fold in fold_order
        ]
        fold = int(fold_order[int(np.argmin(costs))])
        assignments[members[group]] = fold
        loads[fold] += counts[group]
    return assignments


def balanced_nested_folds(
    groups: Sequence[str],
    training_mask: NDArray[np.bool_],
    seed: int = 20260905,
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    outer = balanced_group_folds(groups, training_mask, 5, seed)
    inner = np.full((5, len(groups)), -1, dtype=np.int64)
    for fold in range(5):
        take = np.flatnonzero(outer != fold)
        inner[fold, take] = balanced_group_folds(
            [groups[i] for i in take], training_mask[take], 3, seed + fold + 1
        )
    return outer, inner


def publish_development(
    source_root: Path,
    receipts: Mapping[str, str],
    output: Path,
    *,
    expected_reserved_count: int | None = 997,
) -> DevelopmentData:
    """Compile in the source chemistry runtime and publish a private data bridge.

    The locked model runtime loads these already authenticated identities without
    re-standardizing chemistry. Only retained development target arrays are saved.
    """
    if output.exists():
        raise FileExistsError(output)
    compiled = compile_development(
        source_root, receipts, expected_reserved_count=expected_reserved_count
    )
    metadata = {
        key: getattr(compiled, key)
        for key in (
            "names",
            "molecule_ids",
            "raw_smiles",
            "groups",
            "receipts",
            "report",
        )
    }
    metadata["all_rows"] = [asdict(row) for row in compiled.all_rows]
    metadata_raw = (
        json.dumps(metadata, sort_keys=True, allow_nan=False) + "\n"
    ).encode()
    stream = io.BytesIO()
    np.savez_compressed(
        stream,
        **{
            key: getattr(compiled, key)
            for key in (
                "point",
                "low",
                "high",
                "training_mask",
                "metric_mask",
                "legacy_features",
            )
        },
    )
    files = {"metadata.json": metadata_raw, "arrays.npz": stream.getvalue()}
    manifest = {
        "schema": "cypshift.phase3.development_bundle.v1",
        "compiler_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "rdkit": rdBase.rdkitVersion,
        },
        "input_receipts": dict(receipts),
        "files": {name: sha256(raw).hexdigest() for name, raw in files.items()},
    }
    files["manifest.json"] = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        for name, raw in files.items():
            (temporary / name).write_bytes(raw)
        # Validate the complete published representation before making it visible.
        load_development(temporary)
        if output.exists():
            raise FileExistsError(output)
        os.rename(temporary, output)
        for name in files:
            (output / name).chmod(0o444)
        output.chmod(0o555)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return compiled


def load_development(bundle: Path) -> DevelopmentData:
    """Load a complete bridge without repeating source chemistry or target intake."""
    expected = {"manifest.json", "metadata.json", "arrays.npz"}
    if {path.name for path in bundle.iterdir()} != expected:
        raise ValueError("Development bundle incomplete or contains unexpected files")
    manifest = json.loads((bundle / "manifest.json").read_bytes())
    if (
        manifest.get("schema") != "cypshift.phase3.development_bundle.v1"
        or manifest.get("compiler_sha256")
        != sha256(Path(__file__).read_bytes()).hexdigest()
    ):
        raise ValueError("Development bundle compiler identity differs")
    if set(manifest.get("files", {})) != expected - {"manifest.json"}:
        raise ValueError("Development bundle receipts incomplete")
    loaded = {}
    for name, digest in manifest["files"].items():
        raw = (bundle / name).read_bytes()
        if sha256(raw).hexdigest() != digest:
            raise ValueError(f"Development bundle receipt differs: {name}")
        loaded[name] = raw
    metadata = json.loads(loaded["metadata.json"])
    with np.load(io.BytesIO(loaded["arrays.npz"]), allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    count = len(metadata["names"])
    specifications = {
        name: ((count, 4), np.dtype("float64")) for name in ("point", "low", "high")
    }
    specifications.update(
        {
            name: ((count, 4), np.dtype("bool"))
            for name in ("training_mask", "metric_mask")
        }
    )
    specifications["legacy_features"] = ((count, 2563), np.dtype("float64"))
    if set(arrays) != set(specifications) or any(
        arrays[name].shape != shape or arrays[name].dtype != dtype
        for name, (shape, dtype) in specifications.items()
    ):
        raise ValueError("Development bundle array layout differs")
    all_rows = tuple(LabelFreeMolecule(**row) for row in metadata["all_rows"])
    retained = tuple(
        row for row in all_rows if not row.reserved and not row.quarantined
    )
    for key, attribute in (
        ("names", "name"),
        ("molecule_ids", "molecule_id"),
        ("raw_smiles", "raw_smiles"),
        ("groups", "group"),
    ):
        if tuple(metadata[key]) != tuple(getattr(row, attribute) for row in retained):
            raise ValueError("Development bundle retained identities differ")
    if (
        not np.array_equal(arrays["metric_mask"], np.isfinite(arrays["point"]))
        or (arrays["training_mask"] & ~arrays["metric_mask"]).any()
    ):
        raise ValueError("Development bundle target masks differ")
    for name, digest in metadata["receipts"].items():
        if digest != manifest["input_receipts"].get(f"{Path(name).stem}_sha256"):
            raise ValueError("Development bundle source receipts differ")
    return DevelopmentData(
        tuple(metadata["names"]),
        tuple(metadata["molecule_ids"]),
        tuple(metadata["raw_smiles"]),
        tuple(metadata["groups"]),
        arrays["point"],
        arrays["low"],
        arrays["high"],
        arrays["training_mask"],
        arrays["metric_mask"],
        arrays["legacy_features"],
        all_rows,
        metadata["receipts"],
        metadata["report"],
    )

#!/usr/bin/env python3
"""Compile least-privilege EXP-G3 development capabilities.

The compiler authenticates label-free identities and folds before decoding any
numeric target.  It reconstructs the frozen Morgan-count block from accepted
standardized structures, preserves the accepted descriptor block byte-for-byte
at the value level, and publishes disjoint model and scorer capabilities.
"""

from __future__ import annotations

import csv
import ctypes
import errno
import hashlib
import io
import math
import os
import shutil
import stat
import sys
import tempfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

import g3_runner as g3
import numpy as np
from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from cypshift.chemistry import standardize_molecule  # noqa: E402
from cypshift.schema import MoleculeInput, MoleculeStatus  # noqa: E402

BENCHMARK: Final = ROOT / "benchmarks" / "openadmet_cyp_2026"
EXECUTION_CONTRACT: Final = BENCHMARK / "global_v2_g3_execution_contract.json"
TRACKED_CLAIM: Final = BENCHMARK / "global_v2_g3_execution_claim.json"
EXECUTION_CONTRACT_SHA256: Final = (
    "be9dccf0e1c83aa626550bcabd14dceb12e5f466306f82af7a211b7a28f87e57"
)
TRACKED_CLAIM_SHA256: Final = (
    "71fc023160b5d9da6c620f246ff134ea2e790159bfb675aac33aa4a6c3025f9b"
)
OFFICIAL_SOURCE_ROOT: Final = Path(
    "/home/zbos/cypshift-private/openadmet-2026/g2-2c-maplight-development-source-v1"
)
OFFICIAL_BASELINE_ROOT: Final = Path(
    "/home/zbos/cypshift-private/openadmet-2026/"
    "g2-2c-maplight-development-attempt-1/terminal"
)
OFFICIAL_WRAPPER: Final = SCRIPT.with_name("g3_execution_wrapper.py")
OFFICIAL_SYNTHETIC_DRIVER: Final = SCRIPT.with_name("run_g3_execution_synthetic.py")
TRACKED_ACCEPTANCE: Final = (
    BENCHMARK / "global_v2_g3_execution_synthetic_acceptance.json"
)

SOURCE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_execution_source.v1"
)
MODEL_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g3_execution_model_capability.v1"
)
SCORER_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g3_execution_scorer_capability.v1"
)
PREFLIGHT_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g3_execution_preflight.v1"
)
SYNTHETIC_SOURCE_ID: Final = "g2-6t-g3-official-shaped-synthetic-v1"

SOURCE_FEATURE_COLUMNS: Final = (
    "molecule_id",
    "raw_structure_sha256",
    "standardized_structure_hash",
    "similarity_component_hash",
)
SOURCE_FOLD_COLUMNS: Final = (
    "molecule_id",
    "similarity_component_hash",
    "repeat",
    "seed",
    "outer_fold",
    "outer_validation_fold",
    "inner_fold",
)
DIRECT_COLUMNS: Final = (
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
SOURCE_FILES: Final = (
    "direct_observations.csv",
    "group_folds.csv",
    "feature_rows.csv",
    "maplight_rdkit_descriptors.npy",
)
SOURCE_RECEIPT_KEYS: Final = {
    "direct_observations.csv": "direct_observations_sha256",
    "group_folds.csv": "group_folds_sha256",
    "feature_rows.csv": "feature_rows_sha256",
    "maplight_rdkit_descriptors.npy": "maplight_rdkit_descriptors_sha256",
}
OFFICIAL_PARENT_RECEIPT_KEYS: Final = {
    "r2b_manifest_sha256": "r2b_manifest_sha256",
    "r3a_feature_manifest_sha256": "r3a_feature_manifest_sha256",
}
OFFICIAL_LABEL_FREE_COUNTS: Final = {
    "all_molecules": 4905,
    "all_components": 4553,
    "development_molecules": 3908,
    "development_components": 3640,
    "confirmatory_molecules": 997,
    "confirmatory_components": 913,
}
SYNTHETIC_LABEL_FREE_COUNTS: Final = {
    "all_molecules": 1200,
    "all_components": 600,
    "development_molecules": 960,
    "development_components": 480,
    "confirmatory_molecules": 240,
    "confirmatory_components": 120,
}
FEATURE_COLUMNS: Final = ("molecule_id", "similarity_component_hash")
FOLD_COLUMNS: Final = (
    "molecule_id",
    "similarity_component_hash",
    "repeat_seed",
    "outer_fold",
)
TARGET_COLUMNS: Final = ("molecule_id", "point")
TRUTH_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "repeat_seed",
    "outer_fold",
    "point_eligible",
    "tutorial_eligible",
    "point",
    "low",
    "high",
)
BASELINE_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "repeat",
    "outer_fold",
    "system_id",
    "prediction",
    "model_id",
    "split_id",
)
MINIMA: Final = {
    "development_finite_targets_per_endpoint": 750,
    "outer_training_targets_per_endpoint_repeat_fold": 400,
    "outer_validation_targets_per_endpoint_repeat_fold": 75,
}
FUTURE_FIELDS: Final = (
    "future_official_compiler_source_sha256",
    "future_execution_wrapper_source_sha256",
    "future_official_shaped_synthetic_driver_source_sha256",
    "future_official_shaped_synthetic_acceptance_sha256",
)


class G3ExecutionCompilerError(RuntimeError):
    """An EXP-G3 source, chemistry, split, or capability invariant failed."""


class G3ExecutionUnderpowered(G3ExecutionCompilerError):
    """The frozen official support gate failed before any model fit."""

    def __init__(self, preflight: Mapping[str, object]) -> None:
        super().__init__("EXP-G3 development support is underpowered")
        self.preflight = dict(preflight)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise G3ExecutionCompilerError(message)


def _is_sha(value: object, length: int = 64) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json_loads(path.read_bytes())
    except (OSError, ValueError) as error:
        raise G3ExecutionCompilerError(f"invalid JSON: {path.name}") from error
    require(isinstance(value, dict), f"JSON object differs: {path.name}")
    return cast(dict[str, Any], value)


def json_loads(data: bytes) -> object:
    import json

    return json.loads(data.decode("utf-8"))


def _regular(path: Path, label: str) -> Path:
    require(
        path.exists() and path.is_file() and not path.is_symlink(), f"{label} differs"
    )
    require(stat.S_IMODE(path.stat().st_mode) & 0o222 == 0, f"{label} is writable")
    return path


def _readonly_root(path: Path, label: str) -> Path:
    require(
        path.exists() and path.is_dir() and not path.is_symlink(), f"{label} differs"
    )
    require(path.resolve(strict=True) == path, f"{label} is not canonical")
    require(stat.S_IMODE(path.stat().st_mode) & 0o222 == 0, f"{label} is writable")
    return path


def _cleanup(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    for item in sorted(path.rglob("*"), reverse=True):
        if not item.is_symlink():
            item.chmod(0o755 if item.is_dir() else 0o644)
    path.chmod(0o755)
    shutil.rmtree(path)


def _rename_noreplace(source: Path, destination: Path) -> None:
    require(sys.platform == "linux", "renameat2 is unavailable")
    libc = ctypes.CDLL(None, use_errno=True)
    rename_function = getattr(libc, "renameat2", None)
    require(rename_function is not None, "renameat2 is unavailable")
    rename = cast(Any, rename_function)
    rename.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        observed = ctypes.get_errno()
        message = (
            "publication destination appeared"
            if observed == errno.EEXIST
            else os.strerror(observed)
        )
        raise G3ExecutionCompilerError(message)
    require(
        destination.is_dir() and not source.exists(), "publication promotion failed"
    )


def _publish_files(root: Path, files: Mapping[str, bytes]) -> Path:
    require(not root.exists() and not root.is_symlink(), f"publication exists: {root}")
    root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".g3-execution-", dir=root.parent))
    try:
        for name, data in sorted(files.items()):
            relative = Path(name)
            require(
                not relative.is_absolute() and ".." not in relative.parts,
                "publication path escapes",
            )
            path = staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for path in sorted(staging.rglob("*"), reverse=True):
            path.chmod(0o555 if path.is_dir() else 0o444)
        staging.chmod(0o555)
        _rename_noreplace(staging, root)
        return root
    except BaseException:
        _cleanup(staging)
        raise


def _csv_rows(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8"), newline=""))
        require(
            tuple(reader.fieldnames or ()) == tuple(columns), f"{label} columns differ"
        )
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as error:
        raise G3ExecutionCompilerError(f"{label} decoding differs") from error
    require(bool(rows) and all(None not in row for row in rows), f"{label} rows differ")
    return rows


def _canonical_float(value: str, label: str) -> float:
    try:
        result = float(value)
    except ValueError as error:
        raise G3ExecutionCompilerError(f"{label} is not numeric") from error
    require(
        math.isfinite(result) and value == format(result, ".17g"),
        f"{label} is nonfinite or noncanonical",
    )
    return result


def is_confirmatory(component_hash: str) -> bool:
    require(_is_sha(component_hash), "component hash differs")
    material = f"openadmet-global-v2-confirmatory-v1|20260824|{component_hash}"
    value = int.from_bytes(hashlib.sha256(material.encode()).digest()[:8], "big")
    return value % 5 == 0


def _authority(synthetic: bool, stage: str) -> dict[str, bool]:
    require(stage in {"model", "scorer"}, "capability stage differs")
    authority = {
        name: False
        for name in (
            "official_target_access",
            "official_feature_access",
            "official_baseline_prediction_access",
            "official_model_fitting",
            "official_prediction_generation",
            "development_metric_evaluation",
            "official_metric_evaluation",
            "confirmatory_truth_access",
            "historical_row_level_access",
            "blinded_test_access",
            "tdi_access",
            "external_record_acquisition",
            "submission_generation",
            "leaderboard_selection",
            "live_upload",
        )
    }
    if not synthetic:
        if stage == "model":
            authority["official_target_access"] = True
            authority["official_feature_access"] = True
            authority["official_model_fitting"] = True
            authority["official_prediction_generation"] = True
        else:
            authority["official_baseline_prediction_access"] = True
            authority["development_metric_evaluation"] = True
    return authority


def _source_authority(synthetic: bool) -> dict[str, bool]:
    authority = _authority(True, "model")
    if not synthetic:
        authority["official_target_access"] = True
        authority["official_feature_access"] = True
    return authority


def _future_bindings() -> dict[str, str]:
    return {
        FUTURE_FIELDS[0]: g3.sha256_path(SCRIPT),
        FUTURE_FIELDS[1]: g3.sha256_path(OFFICIAL_WRAPPER),
        FUTURE_FIELDS[2]: g3.sha256_path(OFFICIAL_SYNTHETIC_DRIVER),
        FUTURE_FIELDS[3]: g3.sha256_path(TRACKED_ACCEPTANCE),
    }


def validate_consumed_claim(claim: Mapping[str, Any]) -> dict[str, str]:
    """Require the one exact private derivative of the immutable template."""

    require(
        g3.sha256_path(TRACKED_CLAIM) == TRACKED_CLAIM_SHA256, "tracked claim differs"
    )
    template = _load_json(TRACKED_CLAIM)
    expected = dict(template)
    expected.update(_future_bindings())
    require(
        dict(claim) == expected, "consumed claim is not the exact frozen derivative"
    )
    receipts = claim.get("official_input_receipts")
    require(isinstance(receipts, Mapping), "official claim receipts differ")
    return {
        str(name): str(value)
        for name, value in cast(Mapping[str, object], receipts).items()
    }


def _source_bytes(
    *,
    root: Path,
    manifest: Mapping[str, Any],
    synthetic: bool,
    receipts: Mapping[str, str],
) -> dict[str, bytes]:
    source_receipts = manifest.get("source_receipts")
    require(isinstance(source_receipts, Mapping), "source receipts differ")
    values = cast(Mapping[str, object], source_receipts)
    if synthetic:
        observed = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
        require(
            observed == {"manifest.json", *SOURCE_FILES},
            "synthetic source file set differs",
        )
        require(
            set(values) == set(SOURCE_FILES), "synthetic source receipt set differs"
        )
    loaded: dict[str, bytes] = {}
    for name in SOURCE_FILES:
        data = _regular(root / name, f"source {name}").read_bytes()
        require(
            g3.sha256_bytes(data) == values.get(name), f"source receipt differs: {name}"
        )
        if not synthetic:
            require(
                g3.sha256_bytes(data) == receipts[SOURCE_RECEIPT_KEYS[name]],
                f"official source receipt differs: {name}",
            )
        loaded[name] = data
    return loaded


def _validate_source_manifest(
    *, manifest: Mapping[str, Any], synthetic: bool, receipts: Mapping[str, str]
) -> None:
    expected_counts = (
        SYNTHETIC_LABEL_FREE_COUNTS if synthetic else OFFICIAL_LABEL_FREE_COUNTS
    )
    require(
        manifest.get("schema_version") == SOURCE_SCHEMA
        and manifest.get("synthetic") is synthetic
        and manifest.get("authority") == _source_authority(synthetic)
        and manifest.get("label_free_counts") == expected_counts,
        "source manifest identity differs",
    )
    source_receipts = manifest.get("source_receipts")
    require(
        isinstance(source_receipts, Mapping)
        and set(source_receipts) == set(SOURCE_FILES),
        "source manifest leaf receipts differ",
    )
    if synthetic:
        require(
            manifest.get("semantic_source_id") == SYNTHETIC_SOURCE_ID
            and "parent_receipts" not in manifest,
            "synthetic source identity differs",
        )
        return
    parent_receipts = manifest.get("parent_receipts")
    require(
        manifest.get("semantic_source_id") == receipts["dataset_revision"]
        and isinstance(parent_receipts, Mapping)
        and set(parent_receipts) == set(OFFICIAL_PARENT_RECEIPT_KEYS)
        and all(
            parent_receipts.get(name) == receipts[key]
            for name, key in OFFICIAL_PARENT_RECEIPT_KEYS.items()
        )
        and all(
            source_receipts.get(name) == receipts[key]
            for name, key in SOURCE_RECEIPT_KEYS.items()
        ),
        "official source lineage differs",
    )


def _features(
    data: bytes,
) -> tuple[list[dict[str, str]], set[str], set[str], list[int], dict[str, str]]:
    rows = _csv_rows(data, SOURCE_FEATURE_COLUMNS, "feature rows")
    identities = [row["molecule_id"] for row in rows]
    require(len(identities) == len(set(identities)), "feature identities differ")
    development: set[str] = set()
    confirmatory: set[str] = set()
    selected: list[tuple[str, int, dict[str, str]]] = []
    all_components: dict[str, str] = {}
    for index, row in enumerate(rows):
        molecule = row["molecule_id"]
        component = row["similarity_component_hash"]
        require(
            bool(molecule)
            and _is_sha(row["raw_structure_sha256"])
            and _is_sha(row["standardized_structure_hash"])
            and _is_sha(component),
            "feature identity receipt differs",
        )
        all_components[molecule] = component
        if is_confirmatory(component):
            confirmatory.add(molecule)
        else:
            development.add(molecule)
            selected.append((molecule, index, row))
    require(
        development and confirmatory and not development & confirmatory,
        "partition differs",
    )
    selected.sort(key=lambda item: item[0])
    output = [
        {
            "molecule_id": molecule,
            "similarity_component_hash": row["similarity_component_hash"],
            "standardized_structure_hash": row["standardized_structure_hash"],
        }
        for molecule, _index, row in selected
    ]
    return (
        output,
        development,
        confirmatory,
        [item[1] for item in selected],
        all_components,
    )


def _folds(
    data: bytes, development: set[str], components: Mapping[str, str]
) -> list[dict[str, object]]:
    rows = _csv_rows(data, SOURCE_FOLD_COLUMNS, "group folds")
    contexts: dict[tuple[str, int], set[tuple[int, int]]] = defaultdict(set)
    for row in rows:
        molecule = row["molecule_id"]
        if molecule not in development:
            continue
        try:
            repeat = int(row["repeat"])
            seed = int(row["seed"])
            outer = int(row["outer_fold"])
            context = int(row["outer_validation_fold"])
        except ValueError as error:
            raise G3ExecutionCompilerError("fold integer differs") from error
        require(
            repeat in range(3)
            and seed == g3.REPEAT_SEEDS[repeat]
            and outer in g3.OUTER_FOLDS
            and context in g3.OUTER_FOLDS
            and row["similarity_component_hash"] == components[molecule],
            "fold identity differs",
        )
        contexts[molecule, repeat].add((context, outer))
    require(
        len(contexts) == len(development) * 3, "development fold scope count differs"
    )
    output: list[dict[str, object]] = []
    for (molecule, repeat), values in sorted(contexts.items()):
        require(
            {item[0] for item in values} == set(g3.OUTER_FOLDS), "outer contexts differ"
        )
        assigned = {item[1] for item in values}
        require(len(assigned) == 1, "outer assignment changes by context")
        output.append(
            {
                "molecule_id": molecule,
                "similarity_component_hash": components[molecule],
                "repeat_seed": g3.REPEAT_SEEDS[repeat],
                "outer_fold": assigned.pop(),
            }
        )
    require(len(output) == len(development) * 3, "collapsed fold topology differs")
    for repeat_seed in g3.REPEAT_SEEDS:
        by_component: dict[str, set[int]] = defaultdict(set)
        for row in output:
            if row["repeat_seed"] == repeat_seed:
                by_component[str(row["similarity_component_hash"])].add(
                    int(row["outer_fold"])
                )
        require(
            all(len(values) == 1 for values in by_component.values()),
            "component crossed a fold",
        )
    return output


def _direct_prefix(line: bytes) -> tuple[str, str]:
    prefix = line.split(b",", 2)
    require(
        len(prefix) == 3 and b'"' not in prefix[0] + prefix[1], "direct prefix differs"
    )
    try:
        return prefix[0].decode(), prefix[1].decode()
    except UnicodeDecodeError as error:
        raise G3ExecutionCompilerError("direct identity is not UTF-8") from error


def _truth_and_structures(
    data: bytes,
    development: set[str],
    confirmatory: set[str],
    feature_rows: Sequence[Mapping[str, str]],
    components: Mapping[str, str],
) -> tuple[dict[tuple[str, str], dict[str, str]], dict[str, str], dict[str, int]]:
    require(b"\r" not in data, "direct observations contain CR bytes")
    lines = data.splitlines(keepends=True)
    require(
        bool(lines) and lines[0] == (",".join(DIRECT_COLUMNS) + "\n").encode(),
        "direct columns differ",
    )
    expected_hash = {
        row["molecule_id"]: row["standardized_structure_hash"] for row in feature_rows
    }
    truth: dict[tuple[str, str], dict[str, str]] = {}
    raw_by_molecule: dict[str, set[str]] = defaultdict(set)
    opaque = 0
    finite = 0
    tutorial = 0
    for physical in lines[1:]:
        require(physical.endswith(b"\n"), "direct row lacks final LF")
        observation, molecule = _direct_prefix(physical[:-1])
        require(bool(observation), "observation identity is empty")
        if molecule in confirmatory:
            opaque += 1
            continue
        require(molecule in development, "direct molecule is absent from features")
        try:
            values = next(csv.reader([physical[:-1].decode()]))
        except (UnicodeDecodeError, csv.Error) as error:
            raise G3ExecutionCompilerError(
                "development direct row cannot be decoded"
            ) from error
        require(len(values) == len(DIRECT_COLUMNS), "development direct width differs")
        row = dict(zip(DIRECT_COLUMNS, values, strict=True))
        endpoint = row["endpoint"]
        key = molecule, endpoint
        require(
            endpoint in g3.ENDPOINTS and key not in truth,
            "development endpoint key differs",
        )
        require(
            row["observation_id"] == observation
            and row["similarity_component_hash"] == components[molecule]
            and row["standardized_structure_hash"] == expected_hash[molecule],
            "development direct identity differs",
        )
        require(
            hashlib.sha256(row["raw_smiles"].encode()).hexdigest()
            == row["raw_structure_sha256"],
            "development raw structure receipt differs",
        )
        raw_by_molecule[molecule].add(row["raw_smiles"])
        present = {name: bool(row[name]) for name in ("point", "low", "high", "std")}
        numeric = {
            name: _canonical_float(row[name], f"development {name}")
            if present[name]
            else None
            for name in present
        }
        state = (
            "missing"
            if not any(present.values())
            else "orphan_auxiliary"
            if not present["point"]
            else "complete"
            if all(present.values())
            else "partial"
        )
        require(
            row["value_state"] == state
            and row["point_eligible"] == ("true" if present["point"] else "false")
            and row["anchor_eligible"] == ("true" if state == "complete" else "false"),
            "development availability state differs",
        )
        point, low, high, std = (
            numeric[name] for name in ("point", "low", "high", "std")
        )
        require(
            (std is None or std >= 0)
            and (low is None or high is None or low <= high)
            and (point is None or low is None or low <= point)
            and (point is None or high is None or point <= high),
            "development bounds differ",
        )
        point_eligible = point is not None
        tutorial_eligible = point is not None and low is not None and high is not None
        finite += int(point_eligible)
        tutorial += int(tutorial_eligible)
        truth[key] = {
            "molecule_id": molecule,
            "endpoint": endpoint,
            "similarity_component_hash": components[molecule],
            "point_eligible": "true" if point_eligible else "false",
            "tutorial_eligible": "true" if tutorial_eligible else "false",
            "point": row["point"],
            "low": row["low"],
            "high": row["high"],
        }
    require(
        len(truth) == len(development) * len(g3.ENDPOINTS),
        "development coverage differs",
    )
    require(
        opaque == len(confirmatory) * len(g3.ENDPOINTS), "confirmatory opacity differs"
    )
    structures: dict[str, str] = {}
    for molecule in sorted(development):
        canonical: set[str] = set()
        require(bool(raw_by_molecule[molecule]), "development raw structure is absent")
        for raw in sorted(raw_by_molecule[molecule]):
            record = standardize_molecule(
                MoleculeInput(molecule, raw, "smiles", "g3", "{}")
            )
            require(
                record.status is MoleculeStatus.ACCEPTED
                and record.standardized_structure is not None
                and record.standardized_structure_hash == expected_hash[molecule],
                "development standardization receipt differs",
            )
            canonical.add(record.standardized_structure)
        require(len(canonical) == 1, "development raw structures do not converge")
        structures[molecule] = canonical.pop()
    return (
        truth,
        structures,
        {
            "development_rows_decoded": len(truth),
            "development_finite_targets": finite,
            "development_tutorial_eligible_rows": tutorial,
            "confirmatory_rows_kept_opaque": opaque,
            "confirmatory_target_values_parsed": 0,
        },
    )


def _feature_matrix(
    *,
    structures: Mapping[str, str],
    descriptors: bytes,
    selected_indices: Sequence[int],
    total_rows: int,
) -> tuple[np.ndarray[Any, Any], dict[str, object]]:
    try:
        descriptor = np.load(io.BytesIO(descriptors), allow_pickle=False)
    except (ValueError, OSError) as error:
        raise G3ExecutionCompilerError("descriptor array cannot be loaded") from error
    require(
        descriptor.shape == (total_rows, g3.DESCRIPTOR_WIDTH)
        and descriptor.dtype == np.dtype("float64")
        and descriptor.flags.c_contiguous
        and not np.isinf(descriptor).any(),
        "descriptor array differs",
    )
    selected = np.ascontiguousarray(
        descriptor[list(selected_indices)], dtype=np.float64
    )
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=2,
        fpSize=g3.MORGAN_WIDTH,
        countSimulation=False,
        includeChirality=True,
        useBondTypes=True,
        includeRedundantEnvironments=False,
    )
    morgan = np.zeros((len(structures), g3.MORGAN_WIDTH), dtype=np.int32)
    for index, molecule_id in enumerate(sorted(structures)):
        molecule = Chem.MolFromSmiles(structures[molecule_id])
        require(
            molecule is not None, "accepted standardized structure cannot be parsed"
        )
        counts = generator.GetCountFingerprint(molecule).GetNonzeroElements()
        for column, value in counts.items():
            require(
                0 <= column < g3.MORGAN_WIDTH and int(value) == value and value >= 0,
                "Morgan count differs",
            )
            morgan[index, column] = int(value)
    matrix = np.ascontiguousarray(
        np.concatenate((morgan, selected), axis=1), dtype=np.float64
    )
    require(
        matrix.shape == (len(structures), g3.FEATURE_WIDTH)
        and matrix.flags.c_contiguous
        and not np.isinf(matrix).any()
        and np.isfinite(matrix[:, : g3.MORGAN_WIDTH]).all()
        and (matrix[:, : g3.MORGAN_WIDTH] >= 0).all()
        and np.equal(
            matrix[:, : g3.MORGAN_WIDTH], np.floor(matrix[:, : g3.MORGAN_WIDTH])
        ).all(),
        "compiled feature matrix differs",
    )
    return matrix, {
        "rows": matrix.shape[0],
        "columns": matrix.shape[1],
        "morgan_columns": g3.MORGAN_WIDTH,
        "descriptor_columns": g3.DESCRIPTOR_WIDTH,
        "descriptor_nan_values": int(np.isnan(selected).sum()),
        "infinite_values": int(np.isinf(matrix).sum()),
        "matrix_value_bytes_sha256": g3.sha256_bytes(g3.little_f8_bytes(matrix)),
    }


def _npy_bytes(array: np.ndarray[Any, Any]) -> bytes:
    stream = io.BytesIO()
    np.lib.format.write_array(
        stream, np.ascontiguousarray(array), version=(1, 0), allow_pickle=False
    )
    return stream.getvalue()


def _tutorial_denominator(rows: Sequence[Mapping[str, str]]) -> float:
    require(bool(rows), "tutorial support is empty")
    points = [_canonical_float(row["point"], "tutorial point") for row in rows]
    mean = math.fsum(points) / len(points)
    value = math.fsum(
        max(mean - _canonical_float(row["high"], "tutorial high"), 0)
        + max(_canonical_float(row["low"], "tutorial low") - mean, 0)
        for row in rows
    )
    require(math.isfinite(value), "tutorial denominator is nonfinite")
    return value


def _preflight(
    truth: Mapping[tuple[str, str], Mapping[str, str]],
    folds: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    assigned = {
        (str(row["molecule_id"]), int(row["repeat_seed"])): int(row["outer_fold"])
        for row in folds
    }
    failures: list[str] = []
    finite_counts: dict[str, int] = {}
    training_counts: dict[str, int] = {}
    validation_counts: dict[str, int] = {}
    denominators: dict[str, float] = {}
    for endpoint in g3.ENDPOINTS:
        finite_ids = sorted(
            molecule
            for (molecule, observed), row in truth.items()
            if observed == endpoint and row["point_eligible"] == "true"
        )
        tutorial_rows = [
            row
            for (_molecule, observed), row in truth.items()
            if observed == endpoint and row["tutorial_eligible"] == "true"
        ]
        finite_counts[endpoint] = len(finite_ids)
        if len(finite_ids) < MINIMA["development_finite_targets_per_endpoint"]:
            failures.append(f"finite:{endpoint}:{len(finite_ids)}")
        for repeat_seed in g3.REPEAT_SEEDS:
            denominator = _tutorial_denominator(tutorial_rows)
            denominators[f"{endpoint}|{repeat_seed}"] = denominator
            if denominator <= 0:
                failures.append(f"tutorial:{endpoint}|{repeat_seed}:{denominator}")
            for outer in g3.OUTER_FOLDS:
                validation = sum(
                    assigned[molecule, repeat_seed] == outer for molecule in finite_ids
                )
                training = len(finite_ids) - validation
                key = f"{endpoint}|{repeat_seed}|{outer}"
                validation_counts[key] = validation
                training_counts[key] = training
                if (
                    validation
                    < MINIMA["outer_validation_targets_per_endpoint_repeat_fold"]
                ):
                    failures.append(f"validation:{key}:{validation}")
                if training < MINIMA["outer_training_targets_per_endpoint_repeat_fold"]:
                    failures.append(f"training:{key}:{training}")
    return {
        "schema_version": PREFLIGHT_SCHEMA,
        "status": "G2_6T_G3_PREFLIGHT_PASS"
        if not failures
        else "G2_6R_G3_UNDERPOWERED",
        "minimum_support": dict(MINIMA),
        "finite_targets_per_endpoint": finite_counts,
        "outer_training_targets": training_counts,
        "outer_validation_targets": validation_counts,
        "tutorial_denominators": denominators,
        "failures": failures,
    }


def _baseline_metadata(
    *, synthetic: bool, receipts: Mapping[str, str]
) -> dict[str, object]:
    require(
        _is_sha(receipts.get("baseline_manifest_sha256"))
        and _is_sha(receipts.get("baseline_outer_oof_sha256")),
        "baseline receipt metadata differs",
    )
    return {
        "synthetic": synthetic,
        "manifest_sha256": receipts["baseline_manifest_sha256"],
        "outer_oof_sha256": receipts["baseline_outer_oof_sha256"],
        "opened_before_prediction_freeze": False,
    }


def compile_capabilities(
    *,
    source_root: Path,
    baseline_terminal_root: Path,
    output_root: Path,
    expected_compiler_sha256: str,
    mode: str = "synthetic",
    consumed_claim_path: Path | None = None,
    synthetic_baseline_receipts: Mapping[str, str] | None = None,
) -> tuple[Path, Path, dict[str, object]]:
    """Compile one source into disjoint model and delayed scorer roots."""

    require(
        g3.sha256_path(SCRIPT) == expected_compiler_sha256, "compiler source differs"
    )
    require(
        g3.sha256_path(EXECUTION_CONTRACT) == EXECUTION_CONTRACT_SHA256,
        "execution contract differs",
    )
    require(
        g3.sha256_path(TRACKED_CLAIM) == TRACKED_CLAIM_SHA256, "execution claim differs"
    )
    require(mode in {"synthetic", "official"}, "compiler mode differs")
    synthetic = mode == "synthetic"
    receipts: dict[str, str] = {}
    if synthetic:
        require(consumed_claim_path is None, "synthetic compiler received a claim")
        require(
            synthetic_baseline_receipts is not None,
            "synthetic baseline receipt metadata is absent",
        )
        assert synthetic_baseline_receipts is not None
        receipts.update(synthetic_baseline_receipts)
    else:
        require(
            consumed_claim_path is not None and synthetic_baseline_receipts is None,
            "official claim or baseline metadata differs",
        )
        assert consumed_claim_path is not None
        receipts = validate_consumed_claim(_load_json(consumed_claim_path))
        require(source_root == OFFICIAL_SOURCE_ROOT, "official source root differs")
        require(
            baseline_terminal_root == OFFICIAL_BASELINE_ROOT,
            "official baseline root differs",
        )
    _readonly_root(source_root, "execution source")
    manifest = _load_json(_regular(source_root / "manifest.json", "source manifest"))
    _validate_source_manifest(manifest=manifest, synthetic=synthetic, receipts=receipts)
    source = _source_bytes(
        root=source_root, manifest=manifest, synthetic=synthetic, receipts=receipts
    )
    feature_rows, development, confirmatory, selected_indices, all_components = (
        _features(source["feature_rows.csv"])
    )
    expected_counts = (
        SYNTHETIC_LABEL_FREE_COUNTS if synthetic else OFFICIAL_LABEL_FREE_COUNTS
    )
    require(
        len(development) == expected_counts["development_molecules"]
        and len(confirmatory) == expected_counts["confirmatory_molecules"]
        and len(set(all_components.values())) == expected_counts["all_components"]
        and len({row["similarity_component_hash"] for row in feature_rows})
        == expected_counts["development_components"],
        "compiled population differs",
    )
    components = {
        row["molecule_id"]: row["similarity_component_hash"] for row in feature_rows
    }
    folds = _folds(source["group_folds.csv"], development, components)
    truth, structures, target_accounting = _truth_and_structures(
        source["direct_observations.csv"],
        development,
        confirmatory,
        feature_rows,
        components,
    )
    matrix, matrix_receipt = _feature_matrix(
        structures=structures,
        descriptors=source["maplight_rdkit_descriptors.npy"],
        selected_indices=selected_indices,
        total_rows=len(development) + len(confirmatory),
    )
    preflight = _preflight(truth, folds)
    preflight["accounting"] = {
        **target_accounting,
        "official_source_rows_opened": 0
        if synthetic
        else len(development) + len(confirmatory),
        "official_model_fits": 0,
        "official_predictions_generated": 0,
        "development_metric_evaluations": 0,
        "official_metric_evaluations": 0,
        "claim_consumptions": 0 if synthetic else 1,
    }
    if preflight["status"] != "G2_6T_G3_PREFLIGHT_PASS":
        raise G3ExecutionUnderpowered(preflight)
    require(
        not output_root.exists() and not output_root.is_symlink(),
        "capability output exists",
    )

    feature_public = [
        {
            "molecule_id": row["molecule_id"],
            "similarity_component_hash": row["similarity_component_hash"],
        }
        for row in feature_rows
    ]
    feature_bytes = g3.csv_bytes(FEATURE_COLUMNS, feature_public)
    fold_bytes = g3.csv_bytes(FOLD_COLUMNS, folds)
    matrix_bytes = _npy_bytes(matrix)
    fold_index = {
        (str(row["molecule_id"]), int(row["repeat_seed"])): int(row["outer_fold"])
        for row in folds
    }
    target_files: dict[str, bytes] = {}
    target_receipts: dict[str, str] = {}
    target_rows = 0
    for repeat_seed in g3.REPEAT_SEEDS:
        for outer in g3.OUTER_FOLDS:
            for endpoint in g3.ENDPOINTS:
                rows = [
                    {
                        "molecule_id": molecule,
                        "point": truth[molecule, endpoint]["point"],
                    }
                    for molecule in sorted(development)
                    if fold_index[molecule, repeat_seed] != outer
                    and truth[molecule, endpoint]["point_eligible"] == "true"
                ]
                name = f"targets/{repeat_seed}/outer-{outer}/{endpoint}.csv"
                payload = g3.csv_bytes(TARGET_COLUMNS, rows)
                target_files[name] = payload
                target_receipts[name] = g3.sha256_bytes(payload)
                target_rows += len(rows)
    require(len(target_files) == 60, "target capability count differs")
    common_accounting = {
        **target_accounting,
        "official_model_fits": 0,
        "official_predictions_generated": 0,
        "development_metric_evaluations": 0,
        "official_metric_evaluations": 0,
        "confirmatory_truth_values_opened": 0,
        "historical_r3c_row_level_artifacts_opened": 0,
        "blinded_test_files_opened": 0,
        "tdi_files_opened": 0,
        "external_records_acquired": 0,
        "submissions_created": 0,
        "leaderboard_observations_used_for_selection": 0,
        "live_uploads": 0,
    }
    model_manifest = {
        "schema_version": MODEL_SCHEMA,
        "execution_contract_sha256": EXECUTION_CONTRACT_SHA256,
        "tracked_claim_sha256": TRACKED_CLAIM_SHA256,
        "accepted_g3_runner_sha256": g3.sha256_path(g3.SCRIPT),
        "compiler_source_sha256": expected_compiler_sha256,
        "synthetic": synthetic,
        "semantic_source_id": manifest["semantic_source_id"],
        "molecules": len(development),
        "components": len(set(components.values())),
        "confirmatory_molecules_excluded": len(confirmatory),
        "feature_rows_sha256": g3.sha256_bytes(feature_bytes),
        "folds_sha256": g3.sha256_bytes(fold_bytes),
        "feature_array_sha256": g3.sha256_bytes(matrix_bytes),
        "feature_matrix_receipt": matrix_receipt,
        "target_receipts": target_receipts,
        "target_capabilities": {
            "files": 60,
            "training_rows": target_rows,
            "validation_truth_rows": 0,
        },
        "preflight": preflight,
        "accounting": common_accounting,
        "authority": _authority(synthetic, "model"),
    }
    expanded_truth: list[dict[str, object]] = []
    for molecule in sorted(development):
        for endpoint in g3.ENDPOINTS:
            for repeat_seed in g3.REPEAT_SEEDS:
                expanded_truth.append(
                    {
                        **truth[molecule, endpoint],
                        "repeat_seed": repeat_seed,
                        "outer_fold": fold_index[molecule, repeat_seed],
                    }
                )
    expanded_truth.sort(
        key=lambda row: tuple(str(row[name]) for name in TRUTH_COLUMNS[:5])
    )
    truth_bytes = g3.csv_bytes(TRUTH_COLUMNS, expanded_truth)
    if not synthetic:
        require(
            baseline_terminal_root == OFFICIAL_BASELINE_ROOT,
            "official baseline root differs",
        )
    baseline = _baseline_metadata(synthetic=synthetic, receipts=receipts)
    scorer_manifest = {
        "schema_version": SCORER_SCHEMA,
        "execution_contract_sha256": EXECUTION_CONTRACT_SHA256,
        "tracked_claim_sha256": TRACKED_CLAIM_SHA256,
        "accepted_g3_runner_sha256": g3.sha256_path(g3.SCRIPT),
        "compiler_source_sha256": expected_compiler_sha256,
        "synthetic": synthetic,
        "semantic_source_id": manifest["semantic_source_id"],
        "model_capability_manifest_sha256": g3.sha256_bytes(
            g3.json_bytes(model_manifest)
        ),
        "outer_truth_sha256": g3.sha256_bytes(truth_bytes),
        "outer_truth_rows": len(expanded_truth),
        "baseline": baseline,
        "model_training_files": 0,
        "feature_arrays": 0,
        "accounting": common_accounting,
        "authority": _authority(synthetic, "scorer"),
    }
    try:
        output_root.mkdir(parents=True)
        model_root = _publish_files(
            output_root / "model-capability",
            {
                "feature_rows.csv": feature_bytes,
                "folds.csv": fold_bytes,
                "features.npy": matrix_bytes,
                **target_files,
                "manifest.json": g3.json_bytes(model_manifest),
            },
        )
        scorer_root = _publish_files(
            output_root / "scorer-capability",
            {
                "outer_truth.csv": truth_bytes,
                "manifest.json": g3.json_bytes(scorer_manifest),
            },
        )
        _publish_files(
            output_root / "preflight", {"preflight.json": g3.json_bytes(preflight)}
        )
        return model_root, scorer_root, preflight
    except BaseException:
        _cleanup(output_root)
        raise


require(
    g3.sha256_path(EXECUTION_CONTRACT) == EXECUTION_CONTRACT_SHA256,
    "execution contract differs",
)
require(g3.sha256_path(TRACKED_CLAIM) == TRACKED_CLAIM_SHA256, "tracked claim differs")


__all__ = [
    "BASELINE_COLUMNS",
    "DIRECT_COLUMNS",
    "EXECUTION_CONTRACT_SHA256",
    "FEATURE_COLUMNS",
    "FOLD_COLUMNS",
    "G3ExecutionCompilerError",
    "G3ExecutionUnderpowered",
    "MODEL_SCHEMA",
    "PREFLIGHT_SCHEMA",
    "SCORER_SCHEMA",
    "SOURCE_FEATURE_COLUMNS",
    "SOURCE_FILES",
    "SOURCE_FOLD_COLUMNS",
    "SOURCE_SCHEMA",
    "SYNTHETIC_SOURCE_ID",
    "TARGET_COLUMNS",
    "TRACKED_CLAIM_SHA256",
    "TRUTH_COLUMNS",
    "compile_capabilities",
    "is_confirmatory",
    "validate_consumed_claim",
]

#!/usr/bin/env python3
"""Build the receipt-bound, label-free R3A MapLight feature root.
The process boundary in the v3 experiment contract is deliberately narrow:
this runner can open only the projected chemistry CSV, its manifest, and the
pinned method files.  The standardized Morgan payload is supplied by the
core-chemistry worker through a separately receipt-bound manifest. It is never
recomputed with this (RDKit 2023) environment and consequently cannot be
mistaken for the D-032 (RDKit 2026) representation.
"""
from __future__ import annotations

import argparse
import csv
import ctypes
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import types
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

features: Any = None
ROOT = Path(__file__).resolve().parents[2]
GLOBAL_CONTRACT_PATH = ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract.json"
SOURCE_CONTRACT_PATH = ROOT / "benchmarks/maplight_source_contract.json"
STAGE_A_CONTRACT_PATH = ROOT / "benchmarks/maplight_fixed_stage_a_contract.json"
INT8_CONTRACT_PATH = ROOT / "benchmarks/maplight_fixed_int8_compat_contract.json"
NAN_CONTRACT_PATH = ROOT / "benchmarks/maplight_fixed_nan_compat_contract.json"
MAPLIGHT_LOCK_PATH = Path(__file__).with_name("uv.lock")
MAPLIGHT_PROJECT_PATH = Path(__file__).with_name("pyproject.toml")
PYTHON_PIN_PATH = Path(__file__).with_name(".python-version")
FEATURE_MODULE_PATH = Path(__file__).with_name("maplight_fixed_features.py")
FIXTURE_PATH = ROOT / "benchmarks/fixtures/maplight_fixed_parity_v1.csv"
CORE_MORGAN_WORKER_PATH = ROOT / "scripts/build_openadmet_core_morgan.py"
MAPLIGHT_SOURCE_ROOT = ROOT / "data/external/maplight_tdc/c249378c63232354d17083c83fe94fe728960a27"
MAPLIGHT_SOURCE_PATH = MAPLIGHT_SOURCE_ROOT / "maplight.py"
INPUT_COLUMNS = (
    "molecule_id",
    "raw_smiles",
    "raw_structure_sha256",
    "standardized_smiles",
    "standardized_structure_hash",
    "similarity_component_hash",
)
OUTPUT_COLUMNS = (
    "molecule_id",
    "raw_structure_sha256",
    "standardized_structure_hash",
    "similarity_component_hash",
)
ARRAY_SPECS: dict[str, tuple[tuple[int, int], np.dtype[Any], str]] = {
    "morgan_binary": ((-1, 4096), np.dtype("u1"), "standardized_smiles"),
    "maplight_morgan_count": ((-1, 1024), np.dtype("i1"), "raw_smiles"),
    "maplight_avalon_count": ((-1, 1024), np.dtype("i1"), "raw_smiles"),
    "maplight_erg": ((-1, 315), np.dtype("<f8"), "raw_smiles"),
    "maplight_rdkit_descriptors": ((-1, 200), np.dtype("<f8"), "raw_smiles"),
}
ARRAY_DTYPE_STR = {
    "morgan_binary": "uint8",
    "maplight_morgan_count": "int8",
    "maplight_avalon_count": "int8",
    "maplight_erg": "<f8",
    "maplight_rdkit_descriptors": "<f8",
}
ALLOWED_NAN_COLUMNS = (39, 41, 43, 45)
ALLOWED_NAN_NAMES = (
    "MaxAbsPartialCharge",
    "MaxPartialCharge",
    "MinAbsPartialCharge",
    "MinPartialCharge",
)
CONTRACT_FILES = {
    "global_experiment_contract": GLOBAL_CONTRACT_PATH,
    "maplight_source_contract": SOURCE_CONTRACT_PATH,
    "maplight_stage_a_contract": STAGE_A_CONTRACT_PATH,
    "maplight_int8_contract": INT8_CONTRACT_PATH,
    "maplight_nan_contract": NAN_CONTRACT_PATH,
    "maplight_uv_lock": MAPLIGHT_LOCK_PATH,
    "maplight_project": MAPLIGHT_PROJECT_PATH,
    "python_pin": PYTHON_PIN_PATH,
    "feature_module": FEATURE_MODULE_PATH,
    "core_morgan_worker": CORE_MORGAN_WORKER_PATH,
    "maplight_source": MAPLIGHT_SOURCE_PATH,
}
GLOBAL_CONTRACT_SHA256 = "d728684cc3794bbe01ea44342202944a378968f097cb8f5490852b63721a6285"
PINNED_FILE_SHA256 = {
    "global_experiment_contract": GLOBAL_CONTRACT_SHA256,
    "maplight_source_contract": "a2a608e327cd7adc5e54f24edbcb41007ef03313c26db582f37c9d85836b23a8",
    "maplight_stage_a_contract": "e20985ecabb1aa9ceaeddc3f81ad15dc60b194e250e28de934c12a6bfb10f710",
    "maplight_int8_contract": "ace395a195016854f81c96777921a2fad4c2f638927d2ad15c452b5ecd915ea8",
    "maplight_nan_contract": "52f01f93470cfe461e7ee9fed0ff3a06d7362aceaef343da0c5840d2a74bea09",
    "maplight_uv_lock": "99e72821b69d9bb943a6e32adc7e0dec0e46c6d32df090241d4fb9296a4195d8",
    "maplight_project": "20addcbfa3d7dbfa5d3a9f24f3090c22f11b556166213b2649c6c55e58556234",
    "python_pin": "3817f125779f46c574b17c4adbdd0975ef8c32ae92509fed295212797d314d6a",
    "feature_module": "ac3d7bb88eaf1ed9da2e7ca6c3e042f57afa74344ca7094bcb72bfa7e4ebb35a",
    "core_morgan_worker": "c77b82456edd51596f297311adeaf4157e36bda1b08f202459e7de990599fe68",
    "maplight_source": "6dcb40fa43d39221259e03406f34be554fc138782c099894004549f7a8c24863",
    "fixture": "70ae570bbdbb5c8a225cfd20ab72f0d8f8b43dc1a3a6b2d3356bc52f4f4a513c",
}
SCIENTIFIC_ZEROS = {
    "target_values_parsed": 0,
    "target_values_retained": 0,
    "blinded_test_rows_opened": 0,
    "model_fits": 0,
    "predictions": 0,
    "metric_evaluations": 0,
    "tdi_rows_opened": 0,
    "submission_rows_opened": 0,
    "transductive_operations": 0,
}
class R3AFeatureError(RuntimeError):
    """Receipt-safe error raised before any partial output is promoted."""
    def __init__(self, message: str, *, stage: str = "preflight", field: str | None = None) -> None:
        super().__init__(message)
        self.stage = stage
        self.field = field
def _require(condition: bool, message: str, **detail: Any) -> None:
    if not condition:
        error = R3AFeatureError(message, stage=detail.get("stage", "preflight"), field=detail.get("field"))
        raise error
def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
def _load_json_bytes(path: Path, expected_sha256: str | None = None) -> tuple[dict[str, Any], bytes]:
    _require(path.is_file() and not path.is_symlink(), f"missing regular file: {path}")
    value_bytes = path.read_bytes()
    if expected_sha256 is not None:
        _require(_sha256_bytes(value_bytes) == expected_sha256, f"pinned bytes differ: {path.name}", stage="receipt")
    try:
        value = json.loads(value_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise R3AFeatureError(f"invalid JSON: {path.name}") from error
    _require(isinstance(value, dict), f"JSON is not an object: {path.name}")
    return cast(dict[str, Any], value), value_bytes
def _json_object_bytes(value_bytes: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(value_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise R3AFeatureError(f"invalid JSON: {label}") from error
    _require(isinstance(value, dict), f"JSON is not an object: {label}")
    return cast(dict[str, Any], value)
def _load_features(source_bytes: bytes) -> Any:
    global features
    module = types.ModuleType("maplight_fixed_features")
    sys.modules[module.__name__] = module
    exec(compile(source_bytes, str(FEATURE_MODULE_PATH), "exec"), module.__dict__)
    features = module
    return features
def _normalize_version(value: str) -> str:
    # The 2023 wheel metadata reports 2023.03.3 while the frozen contract
    # names the same release 2023.3.3.
    pieces = value.split(".")
    if len(pieces) == 3 and pieces[0] == "2023":
        return ".".join((pieces[0], str(int(pieces[1])), pieces[2]))
    return value
def _normalize_package(value: str) -> str:
    return value.lower().replace("_", "-").replace(".", "-")
def _verify_environment(contract: Mapping[str, Any]) -> dict[str, Any]:
    _require(platform.system() == "Linux", "R3A requires Linux", stage="environment")
    _require(platform.machine().lower() in {"x86_64", "amd64"}, "R3A requires Linux x86_64", stage="environment")
    _require(sys.version_info[:3] == (3, 10, 13), "Python version differs", stage="environment")
    installed = {
        _normalize_package(str(distribution.metadata["Name"])): distribution.version
        for distribution in importlib.metadata.distributions()
        if distribution.metadata["Name"]
    }
    expected_packages = {
        _normalize_package(name.rsplit("@", 1)[0])
        for name in contract["compatible_environment"]["resolved_package_licenses"]
    }
    _require(set(installed) == expected_packages, "installed package set differs from the frozen lock", stage="environment")
    versions: dict[str, str] = {}
    for package, expected in contract["compatible_environment"]["direct_packages"].items():
        observed = _normalize_version(installed[_normalize_package(package)])
        _require(observed == _normalize_version(expected), f"{package} version differs", stage="environment")
        versions[package] = observed
    executable = Path(sys.executable).resolve()
    _require(executable.is_file(), "Python executable is missing", stage="environment")
    try:
        uv_version = subprocess.run(["uv", "--version"], check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise R3AFeatureError("uv version is unavailable", stage="environment") from error
    return {
        "python": platform.python_version(),
        "packages": versions,
        "python_executable_sha256": _sha256_bytes(executable.read_bytes()),
        "uv_version": uv_version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "cpu_count": os.cpu_count(),
        "system": "Linux x86_64 CPU",
        "cpu_only": True,
    }
def _verify_contracts() -> dict[str, Any]:
    raw: dict[str, bytes] = {}
    hashes: dict[str, str] = {}
    for name, path in CONTRACT_FILES.items():
        _require(path.is_file() and not path.is_symlink(), f"missing pinned file: {name}")
        data = path.read_bytes()
        raw[name] = data
        hashes[name] = _sha256_bytes(data)
        _require(hashes[name] == PINNED_FILE_SHA256[name], f"pinned bytes differ: {name}", stage="receipt")
    runner_bytes = Path(__file__).read_bytes()
    hashes["runner_source"] = _sha256_bytes(runner_bytes)
    global_contract = _json_object_bytes(raw["global_experiment_contract"], "global contract")
    _require(global_contract.get("schema_version") == "cypshift.openadmet_cyp_2026.global_experiment_contract.v3", "global contract identity differs")
    _require(global_contract.get("gate") == "R3_GLOBAL_EXPERIMENT_CONTRACT_V3_FROZEN", "global contract gate differs")
    _require(global_contract.get("status") == "contract_only_not_implemented", "global contract status differs")
    output = global_contract["r3a_feature_root"]
    _require(output["feature_rows"] == {"path": "feature_rows.csv", "columns": list(OUTPUT_COLUMNS), "rows": 4905}, "feature-row contract differs")
    declared_arrays = output["arrays"]
    _require(isinstance(declared_arrays, list) and len(declared_arrays) == len(ARRAY_SPECS), "array contract schema differs")
    for name, (shape, _dtype, chemistry) in ARRAY_SPECS.items():
        declared = next((item for item in declared_arrays if isinstance(item, dict) and item.get("path") == f"{name}.npy"), None)
        _require(isinstance(declared, dict), f"array contract differs: {name}")
        declared_record = cast(dict[str, Any], declared)
        _require(declared_record.get("chemistry") == chemistry and declared_record.get("shape") == [4905, shape[1]] and declared_record.get("dtype") == ARRAY_DTYPE_STR[name], f"array contract differs: {name}")
    stage_contract = _json_object_bytes(raw["maplight_stage_a_contract"], "Stage A contract")
    source_contract = _json_object_bytes(raw["maplight_source_contract"], "MapLight source contract")
    _require(hashes["maplight_source"] == source_contract["repository"]["files"]["maplight.py"]["sha256"], "pinned MapLight source hash differs")
    expected = global_contract["inputs"]["maplight_method"]
    for key, name in (("source_contract_sha256", "maplight_source_contract"), ("stage_a_contract_sha256", "maplight_stage_a_contract"), ("signed_int8_contract_sha256", "maplight_int8_contract"), ("nan_contract_sha256", "maplight_nan_contract"), ("uv_lock_sha256", "maplight_uv_lock")):
        _require(hashes[name] == expected[key], f"pinned method hash differs: {name}")
    environment = stage_contract["compatible_environment"]
    for key, name in (("project_path", "maplight_project"), ("lock_path", "maplight_uv_lock"), ("python_version_path", "python_pin")):
        _require(ROOT / environment[key] == CONTRACT_FILES[name], f"pinned environment path differs: {name}")
        _require(hashes[name] == environment[key.replace("_path", "_sha256")], f"pinned environment hash differs: {name}")
    source_root = ROOT / stage_contract["frozen_sources"]["maplight_repository"]["stable_ignored_root"]
    _require(source_root == MAPLIGHT_SOURCE_ROOT, "pinned MapLight source root differs")
    source_files: dict[str, bytes] = {}
    for name, expected_hash in stage_contract["frozen_sources"]["maplight_repository"]["files"].items():
        path = source_root / name
        _require(path.is_file() and not path.is_symlink(), f"missing pinned source: {name}")
        _require(path.stat().st_mode & 0o222 == 0, f"pinned source is writable: {name}")
        data = path.read_bytes()
        source_files[name] = data
        _require(_sha256_bytes(data) == expected_hash, f"pinned source bytes differ: {name}", stage="receipt")
    fixture_bytes = FIXTURE_PATH.read_bytes()
    _require(_sha256_bytes(fixture_bytes) == PINNED_FILE_SHA256["fixture"], "parity fixture bytes differ", stage="receipt")
    kernel_bytes = raw["feature_module"]
    _load_features(kernel_bytes)
    return {"global": global_contract, "stage_a": stage_contract, "source": source_contract, "hashes": hashes, "raw": raw, "source_files": source_files, "fixture": fixture_bytes, "kernel": kernel_bytes}
def _manifest_required(manifest: Mapping[str, Any], contract: Mapping[str, Any] | None = None, *, allow_synthetic: bool = False) -> None:
    required = {
        "schema_version", "contract_sha256", "direct_observations_sha256", "group_folds_sha256",
        "training_topology_sha256", "projector_source_sha256", "standardizer_source_sha256",
        "core_uv_lock_sha256", "core_python_version", "core_rdkit_version", "standardization_policy_id",
        "feature_input_sha256", "feature_input_columns", "feature_input_rows", "raw_structure_hash_formula",
        "standardized_structure_hash_formula", "accounting", "authority",
    }
    _require(set(manifest) == required, "feature-input manifest schema differs")
    _require(manifest["schema_version"] == "cypshift.openadmet_cyp_2026.feature_input.v1", "feature-input manifest version differs")
    contract = contract or {"inputs": {"direct_observations": {"sha256": "00b1ac95cc73dda2699f2f05bc33200d1119a197d7a92ae900cde78d722f00b7"}, "group_folds": {"sha256": "91678d68b2f9ac3913f6b679dd284f82ba2a040d803de83655bf89906f31f774"}, "training_topology": {"sha256": "710978431402dbb737244bf01a9f4d9e4e398181400627db680a4f12d06d3b8a"}, "core_chemistry": {"standardizer_source_sha256": "21d8df35f001c790290d3ef2c836c9f459015b5db0f48c8f6e44436f9181103a", "uv_lock_sha256": "33d9382256de7992ce9ff7a7edc125d4771546a25ef3be5f1160627846d2c9b6", "python_version": "3.12.3", "rdkit_version": "2026.03.5", "standardization_policy_id": "rdkit-cleanup-fragment-parent-v1"}}, "r3a_chemistry_projection": {"accounting": {"direct_observation_records_scanned": 19620, "decoded_prefix_fields": 156960, "opaque_suffixes_discarded": 19620, "target_values_parsed": 0, "target_values_retained": 0, "blinded_test_rows_opened": 0}}}
    _require(manifest["contract_sha256"] == GLOBAL_CONTRACT_SHA256, "feature-input global contract hash differs")
    inputs = contract["inputs"]
    expected_receipts = {
        "direct_observations_sha256": inputs["direct_observations"]["sha256"],
        "group_folds_sha256": inputs["group_folds"]["sha256"],
        "training_topology_sha256": inputs["training_topology"]["sha256"],
        "standardizer_source_sha256": inputs["core_chemistry"]["standardizer_source_sha256"],
        "core_uv_lock_sha256": inputs["core_chemistry"]["uv_lock_sha256"],
        "core_python_version": inputs["core_chemistry"]["python_version"],
        "core_rdkit_version": inputs["core_chemistry"]["rdkit_version"],
        "standardization_policy_id": inputs["core_chemistry"]["standardization_policy_id"],
    }
    _require(all(manifest[key] == value for key, value in expected_receipts.items()), "feature-input contract receipt differs")
    _require(len(manifest["projector_source_sha256"]) == 64 and manifest["projector_source_sha256"] == manifest["projector_source_sha256"].lower() and all(char in "0123456789abcdef" for char in manifest["projector_source_sha256"]), "projector source receipt differs")
    _require(manifest["feature_input_columns"] == list(INPUT_COLUMNS), "feature-input columns differ")
    _require(manifest["raw_structure_hash_formula"] == "lowercase SHA256 hex of the exact raw_smiles UTF-8 bytes", "raw hash formula differs")
    _require(manifest["standardized_structure_hash_formula"] == "lowercase SHA256 hex of the exact standardized_smiles UTF-8 bytes", "standardized hash formula differs")
    _require(manifest["standardization_policy_id"] == "rdkit-cleanup-fragment-parent-v1", "standardization policy differs")
    authority = manifest["authority"]
    _require(authority == {key: False for key in ("targets", "features", "models", "predictions", "metrics", "fold_assignments", "submissions")}, "feature-input authority differs")
    accounting = manifest["accounting"]
    _require(isinstance(accounting, dict), "feature-input accounting is not an object")
    expected_accounting = contract["r3a_chemistry_projection"]["accounting"]
    _require(set(accounting) == set(expected_accounting), "feature-input accounting schema differs")
    for key, expected in expected_accounting.items():
        value = accounting[key]
        _require(type(value) is int and value >= 0, f"feature-input accounting is invalid: {key}")
        if key not in ("direct_observation_records_scanned", "decoded_prefix_fields", "opaque_suffixes_discarded") or not allow_synthetic:
            _require(value == expected, f"feature-input scientific accounting differs: {key}")
def _read_feature_input(manifest_path: Path, input_path: Path, expected_manifest_sha256: str, expected_rows: int | None = None, *, contract: Mapping[str, Any] | None = None, allow_synthetic: bool = False) -> tuple[dict[str, Any], bytes, list[dict[str, str]], dict[str, str]]:
    _require(len(expected_manifest_sha256) == 64 and expected_manifest_sha256 == expected_manifest_sha256.lower(), "expected manifest SHA is invalid")
    manifest, manifest_bytes = _load_json_bytes(manifest_path, expected_manifest_sha256)
    _require(manifest_bytes == _json_bytes(manifest), "feature-input manifest serialization differs", stage="input_receipt")
    _manifest_required(manifest, contract, allow_synthetic=allow_synthetic)
    _require(input_path.is_file() and not input_path.is_symlink(), "missing feature-input CSV", stage="input_receipt")
    input_bytes = input_path.read_bytes()
    _require(_sha256_bytes(input_bytes) == manifest["feature_input_sha256"], "feature-input CSV SHA differs", stage="input_receipt")
    _require(input_bytes.endswith(b"\n") and b"\r" not in input_bytes, "feature-input CSV line endings differ", stage="input_receipt")
    try:
        text = input_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise R3AFeatureError("feature-input CSV is not UTF-8", stage="input_parse") from error
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = tuple(next(reader))
    except StopIteration as error:
        raise R3AFeatureError("feature-input CSV is empty", stage="input_parse") from error
    _require(header == INPUT_COLUMNS, "feature-input CSV schema differs", stage="input_parse")
    try:
        parsed_values = list(reader)
    except csv.Error as error:
        raise R3AFeatureError("feature-input CSV syntax differs", stage="input_parse") from error
    rows: list[dict[str, str]] = []
    for _row_index, values in enumerate(parsed_values):
        _require(len(values) == len(INPUT_COLUMNS), "feature-input CSV row width differs", stage="input_parse")
        row = dict(zip(INPUT_COLUMNS, values, strict=True))
        for field in INPUT_COLUMNS:
            _require(row[field] != "", f"empty feature-input field: {field}", stage="input_parse")
        _require(len(row["molecule_id"]) <= 256, "molecule_id is too long", stage="input_parse")
        _require(row["raw_structure_sha256"] == _sha256_bytes(row["raw_smiles"].encode("utf-8")), "raw structure hash differs", stage="input_parse")
        _require(row["standardized_structure_hash"] == _sha256_bytes(row["standardized_smiles"].encode("utf-8")), "standardized structure hash differs", stage="input_parse")
        for field in ("raw_structure_sha256", "standardized_structure_hash", "similarity_component_hash"):
            _require(len(row[field]) == 64 and row[field] == row[field].lower() and all(c in "0123456789abcdef" for c in row[field]), f"invalid hash: {field}", stage="input_parse")
        rows.append(row)
    _require(type(manifest["feature_input_rows"]) is int and manifest["feature_input_rows"] == len(rows), "feature-input row count differs", stage="input_parse")
    if expected_rows is not None:
        _require(len(rows) == expected_rows, f"feature-input must contain {expected_rows} rows", stage="input_parse")
    _require(rows == sorted(rows, key=lambda item: item["molecule_id"]), "feature-input molecule order differs", stage="input_parse")
    _require(len({row["molecule_id"] for row in rows}) == len(rows), "feature-input molecule IDs are not unique", stage="input_parse")
    return manifest, input_bytes, rows, {"manifest": _sha256_bytes(manifest_bytes), "feature_input": _sha256_bytes(input_bytes)}
def _load_npy_bytes(payload: bytes, *, shape: tuple[int, int], dtype: np.dtype[Any], name: str) -> NDArray[Any]:
    try:
        with io.BytesIO(payload) as handle:
            magic = np.lib.format.read_magic(handle)
            _require(magic == (1, 0), f"{name} is not NPY v1.0", stage="array_validation")
        array = np.load(io.BytesIO(payload), allow_pickle=False)
    except (ValueError, EOFError, OSError) as error:
        raise R3AFeatureError(f"invalid NPY payload: {name}", stage="array_validation") from error
    _require(array.shape == shape, f"{name} shape differs", stage="array_validation")
    _require(array.dtype == dtype, f"{name} dtype differs", stage="array_validation")
    _require(array.flags.c_contiguous, f"{name} is not C-contiguous", stage="array_validation")
    return cast(NDArray[Any], array)
def _load_core_reference(
    manifest_path: Path,
    expected_manifest_sha256: str,
    input_hashes: Mapping[str, str],
    contract: Mapping[str, Any],
    rows: int,
    expected_worker_sha256: str,
) -> tuple[NDArray[np.uint8], dict[str, Any]]:
    _require(len(expected_manifest_sha256) == 64 and expected_manifest_sha256 == expected_manifest_sha256.lower(), "expected core manifest SHA is invalid", stage="core_reference")
    manifest, manifest_bytes = _load_json_bytes(manifest_path, expected_manifest_sha256)
    _require(manifest_bytes == _json_bytes(manifest), "core manifest serialization differs", stage="core_reference")
    required = {"schema_version", "contract_sha256", "feature_input_manifest_sha256", "feature_input_sha256", "worker_source_sha256", "standardizer_source_sha256", "core_uv_lock_sha256", "core_python_version", "core_rdkit_version", "standardization_policy_id", "generator_policy", "array", "accounting", "authority"}
    _require(set(manifest) == required, "core manifest schema differs", stage="core_reference")
    _require(manifest["schema_version"] == "cypshift.openadmet_cyp_2026.core_morgan.v1", "core manifest version differs", stage="core_reference")
    _require(manifest["contract_sha256"] == GLOBAL_CONTRACT_SHA256, "core manifest contract differs", stage="core_reference")
    _require(manifest["feature_input_manifest_sha256"] == input_hashes["manifest"], "core manifest projection manifest differs", stage="core_reference")
    _require(manifest["feature_input_sha256"] == input_hashes["feature_input"], "core manifest projection CSV differs", stage="core_reference")
    core = contract["inputs"]["core_chemistry"]
    _require(manifest["standardizer_source_sha256"] == core["standardizer_source_sha256"] and manifest["core_uv_lock_sha256"] == core["uv_lock_sha256"] and manifest["core_python_version"] == core["python_version"] and manifest["core_rdkit_version"] == core["rdkit_version"] and manifest["standardization_policy_id"] == "rdkit-cleanup-fragment-parent-v1", "core environment receipt differs", stage="core_reference")
    _require(manifest["worker_source_sha256"] == expected_worker_sha256, "core worker source differs", stage="core_reference")
    array_record = manifest["array"]
    _require(set(array_record) == {"path", "shape", "dtype", "npy_version", "c_contiguous", "npy_sha256", "element_sha256"}, "core array receipt schema differs", stage="core_reference")
    _require(array_record["path"] == "morgan_binary.npy", "core array path differs", stage="core_reference")
    _require(array_record["shape"] == [rows, 4096] and array_record["dtype"] == "uint8" and array_record["npy_version"] == "1.0" and array_record["c_contiguous"] is True, "core array declaration differs", stage="core_reference")
    generator = manifest["generator_policy"]
    _require(set(generator) == {"id", "algorithm", "radius", "fp_size", "include_chirality", "input", "binary"}, "core generator schema differs", stage="core_reference")
    _require(generator == {"id": "d032-morgan-ecfp4-chiral-binary-4096-v1", "algorithm": "rdkit.Chem.rdFingerprintGenerator.GetMorganGenerator", "radius": 2, "fp_size": 4096, "include_chirality": True, "input": "standardized_smiles", "binary": True}, "core Morgan policy differs", stage="core_reference")
    _require(set(manifest["accounting"]) == {"feature_input_rows_parsed", "standardized_structures_parsed", "target_values_parsed", "target_values_retained", "blinded_test_rows_opened", "model_fits", "predictions", "metric_evaluations"}, "core accounting schema differs", stage="core_reference")
    _require(manifest["accounting"]["feature_input_rows_parsed"] == rows and manifest["accounting"]["standardized_structures_parsed"] == rows and all(type(manifest["accounting"][key]) is int and manifest["accounting"][key] == 0 for key in ("target_values_parsed", "target_values_retained", "blinded_test_rows_opened", "model_fits", "predictions", "metric_evaluations")), "core scientific accounting differs", stage="core_reference")
    expected_authority = {key: False for key in ("targets", "features", "models", "predictions", "metrics", "fold_assignments", "submissions", "tdi", "test", "transduction")}
    _require(manifest["authority"] == expected_authority, "core authority differs", stage="core_reference")
    array_path = manifest_path.parent / array_record["path"]
    _require(array_path.is_file() and not array_path.is_symlink(), "core NPY is missing", stage="core_reference")
    payload = array_path.read_bytes()
    _require(_sha256_bytes(payload) == array_record["npy_sha256"], "core NPY SHA differs", stage="core_reference")
    array = _load_npy_bytes(payload, shape=(rows, 4096), dtype=np.dtype("u1"), name="morgan_binary")
    _require(bool(np.logical_or(array == 0, array == 1).all()), "core Morgan is not binary", stage="core_reference")
    _require(hashlib.sha256(array.tobytes(order="C")).hexdigest() == array_record["element_sha256"], "core Morgan element bytes differ", stage="core_reference")
    return array, {"manifest_path": manifest_path.name, "manifest_sha256": expected_manifest_sha256, "array": dict(array_record), "generator_policy": dict(generator), "worker_source_sha256": manifest["worker_source_sha256"]}
def _import_module_bytes(source_bytes: bytes, name: str) -> Any:
    module = types.ModuleType(name)
    exec(compile(source_bytes, str(MAPLIGHT_SOURCE_PATH), "exec"), module.__dict__)
    return module
def _fixture_rows(payload: bytes, contract: Mapping[str, Any]) -> list[dict[str, str]]:
    expected_sha = contract["parity_fixture"]["sha256"]
    _require(_sha256_bytes(payload) == expected_sha, "parity fixture SHA differs", stage="compatibility")
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8"), newline=""))
    rows = [{str(k): str(v) for k, v in row.items()} for row in reader]
    _require(tuple(reader.fieldnames or ()) == ("fixture_id", "pandas_index", "raw_smiles"), "parity fixture schema differs", stage="compatibility")
    _require(len(rows) == 8 and [int(row["pandas_index"]) for row in rows] == [13, 2, 21, 5, 8, 3, 34, 1], "parity fixture rows differ", stage="compatibility")
    return rows
def _array_equal(left: NDArray[Any], right: NDArray[Any], name: str) -> None:
    _require(left.shape == right.shape and left.dtype == right.dtype, f"fixture {name} shape/dtype differs", stage="compatibility")
    _require(bool(np.array_equal(left, right, equal_nan=True)), f"fixture {name} values differ", stage="compatibility")
    _require(hashlib.sha256(left.tobytes(order="C")).hexdigest() == hashlib.sha256(right.tobytes(order="C")).hexdigest(), f"fixture {name} bytes differ", stage="compatibility")
def _catboost_probe() -> dict[str, Any]:
    from catboost import CatBoostRegressor
    X = np.array([[0.0, np.nan], [1.0, 0.0], [2.0, np.nan], [3.0, 1.0]], dtype="<f8")
    y = np.array([0.0, 1.0, 0.5, 1.5], dtype="<f8")
    model = CatBoostRegressor(loss_function="MAE", random_strength=2, random_seed=1, task_type="CPU", thread_count=1, verbose=0, allow_writing_files=False)
    model.fit(X, y)
    predictions = np.asarray(model.predict(X))
    params = model.get_all_params()
    _require(str(params.get("nan_mode")) == "Min", "CatBoost resolved nan_mode differs", stage="compatibility")
    _require(bool(np.isfinite(predictions).all()), "CatBoost NaN probe predictions are non-finite", stage="compatibility")
    return {"synthetic_rows": 4, "fit_operations": 1, "predictions_finite": True, "resolved_nan_mode": "Min", "task_type": "CPU"}
def run_linux_compatibility(verified: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Run fixture parity and the label-free CatBoost NaN capability probe."""
    pinned = dict(verified or _verify_contracts())
    environment = _verify_environment(pinned["stage_a"])
    contract_hashes = pinned["hashes"]
    rows = _fixture_rows(pinned["fixture"], pinned["stage_a"])
    raw = tuple(row["raw_smiles"] for row in rows)
    raw_hashes = tuple(_sha256_bytes(value.encode("utf-8")) for value in raw)
    local, _ = features.featurize_raw_structures_upstream_int8(raw, raw_hashes, nonfinite_policy="allow_gasteiger_charge_nan")
    pandas = importlib.import_module("pandas")
    source = _import_module_bytes(pinned["source_files"]["maplight.py"], "r3a_pinned_maplight")
    from rdkit import Chem
    _require(tuple(source.get_chosen_descriptors()) == tuple(features.descriptor_names()), "fixture descriptor order differs", stage="compatibility")
    series = pandas.Series(raw, index=[int(row["pandas_index"]) for row in rows], dtype=object)
    molecules = series.apply(Chem.MolFromSmiles)
    upstream = {
        "maplight_morgan_count": source.get_morgan_fingerprints(molecules),
        "maplight_avalon_count": source.get_avalon_fingerprints(molecules),
        "maplight_erg": source.get_erg_fingerprints(molecules),
        "maplight_rdkit_descriptors": source.get_rdkit_features(molecules),
    }
    local_arrays = {
        "maplight_morgan_count": local.morgan_count,
        "maplight_avalon_count": local.avalon_count,
        "maplight_erg": local.erg,
        "maplight_rdkit_descriptors": local.rdkit_descriptors,
    }
    for name in upstream:
        _array_equal(local_arrays[name], upstream[name], name)
    boundaries = {str(value): features.signed_int8_count_witness(value) for value in (127, 128, 144)}
    _require(boundaries == {"127": 127, "128": -128, "144": -112}, "signed-int8 witness differs", stage="compatibility")
    probe = _catboost_probe()
    return {
        "schema_version": "cypshift.openadmet_cyp_2026.r3a_linux_compatibility.v1",
        "environment": environment,
        "contracts": contract_hashes,
        "fixture": {"rows": 8, "raw_structure_sha256": list(raw_hashes), "blocks": list(upstream)},
        "upstream_vs_local": {name: {"equal": True, "element_sha256": hashlib.sha256(local_arrays[name].tobytes(order="C")).hexdigest()} for name in upstream},
        "signed_int8_witnesses": boundaries,
        "descriptor_order": {"names": list(features.descriptor_names()), "sha256": features.DESCRIPTOR_NAMES_SHA256},
        "catboost_nan_probe": probe,
        "accounting": {"fixture_rows_parsed": 8, "fixture_block_comparisons": 4, "boundary_conversions": 3, "synthetic_catboost_fits": 1, **SCIENTIFIC_ZEROS},
        "claim_boundary": "Linux method compatibility only; no real chemistry, target, model, prediction, metric, TDI, test, or transductive operation.",
    }
def _array_record(name: str, path: Path, array: NDArray[Any], *, allowed_nan: Sequence[int] = ()) -> dict[str, Any]:
    _require(name in ARRAY_SPECS, f"unknown array: {name}", stage="array_validation")
    expected_shape, expected_dtype, chemistry = ARRAY_SPECS[name]
    _require(path.name == f"{name}.npy", f"array path differs: {name}", stage="array_validation")
    _require(array.ndim == 2 and array.shape[1] == expected_shape[1], f"array dimensions differ: {name}", stage="array_validation")
    _require(array.dtype == expected_dtype and array.flags.c_contiguous, f"array dtype/order differs: {name}", stage="array_validation")
    expected_nan = tuple(ALLOWED_NAN_COLUMNS) if name == "maplight_rdkit_descriptors" else ()
    _require(tuple(allowed_nan) == expected_nan, f"array NaN policy differs: {name}", stage="array_validation")
    payload = path.read_bytes()
    retained = _load_npy_bytes(payload, shape=(array.shape[0], expected_shape[1]), dtype=expected_dtype, name=path.name)
    _require(bool(np.array_equal(retained, array, equal_nan=True)), f"retained array differs: {path.name}", stage="array_validation")
    infinity = np.isinf(retained)
    _require(not bool(infinity.any()), f"array contains infinity: {path.name}", stage="array_validation")
    nan = np.isnan(retained)
    allowed = np.zeros(retained.shape[1], dtype=bool)
    allowed[list(allowed_nan)] = True
    _require(not bool(np.logical_and(nan, ~allowed[np.newaxis, :]).any()), f"array contains disallowed NaN: {path.name}", stage="array_validation")
    return {
        "path": path.name,
        "chemistry": chemistry,
        "shape": list(retained.shape),
        "dtype": ARRAY_DTYPE_STR[name],
        "c_contiguous": True,
        "npy_version": "1.0",
        "npy_sha256": _sha256_bytes(payload),
        "element_sha256": hashlib.sha256(retained.tobytes(order="C")).hexdigest(),
        "nonfinite_count": int(nan.sum()),
        "npy_size_bytes": len(payload),
    }
def _write_rows(rows: Sequence[Mapping[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row[key] for key in OUTPUT_COLUMNS})
    return stream.getvalue().encode("utf-8")
def _nan_record(array: NDArray[np.float64]) -> dict[str, Any]:
    mask = np.isnan(array)
    bad = np.argwhere(np.logical_and(mask, ~np.isin(np.arange(array.shape[1]), ALLOWED_NAN_COLUMNS)[np.newaxis, :]))
    _require(not bool(np.isinf(array).any()), "descriptor infinity found", stage="array_validation")
    _require(len(bad) == 0, "descriptor NaN outside permitted columns", stage="array_validation")
    return {
        "allowed_descriptor_indices": list(ALLOWED_NAN_COLUMNS),
        "allowed_descriptor_names": list(ALLOWED_NAN_NAMES),
        "mask_sha256": hashlib.sha256(mask.astype(np.uint8, copy=False).tobytes(order="C")).hexdigest(),
        "nan_cells": int(mask.sum()),
        "nan_cells_by_column": {str(index): int(mask[:, index].sum()) for index in ALLOWED_NAN_COLUMNS},
        "positive_infinity_cells": int(np.isposinf(array).sum()),
        "negative_infinity_cells": int(np.isneginf(array).sum()),
    }
def _manifest(
    build_id: int,
    rows: Sequence[Mapping[str, str]],
    input_manifest: Mapping[str, Any],
    input_hashes: Mapping[str, str],
    core_reference: Mapping[str, Any],
    contracts: Mapping[str, str],
    compatibility_sha256: str,
    arrays: Mapping[str, Mapping[str, Any]],
    nan: Mapping[str, Any],
    signed_stats: Mapping[str, Any],
    environment: Mapping[str, Any],
    runtime_seconds: float,
    peak_rss_gib: float,
    pinned: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "cypshift.openadmet_cyp_2026.r3a_feature_manifest.v1",
        "experiment": "R3A_LABEL_FREE_OPENADMET_MAPLIGHT_FEATURES",
        "build_id": build_id,
        "contracts": dict(contracts),
        "projection_receipts": {
            "feature_input_manifest_sha256": input_hashes["manifest"],
            "feature_input_sha256": input_hashes["feature_input"],
            "direct_observations_sha256": input_manifest["direct_observations_sha256"],
            "group_folds_sha256": input_manifest["group_folds_sha256"],
            "training_topology_sha256": input_manifest["training_topology_sha256"],
            "projector_source_sha256": input_manifest["projector_source_sha256"],
            "standardizer_source_sha256": input_manifest["standardizer_source_sha256"],
            "core_uv_lock_sha256": input_manifest["core_uv_lock_sha256"],
            "core_morgan_manifest_sha256": core_reference["manifest_sha256"],
        },
        "rows": {
            "path": "feature_rows.csv",
            "columns": list(OUTPUT_COLUMNS),
            "rows": len(rows),
            "sha256": input_hashes.get("feature_rows"),
        },
        "arrays": dict(arrays),
        "payload_hashes": {
            "feature_rows.csv": input_hashes.get("feature_rows"),
            **{record["path"]: record["npy_sha256"] for record in arrays.values()},
        },
        "core_morgan_reference": dict(core_reference),
        "descriptor_order": {"names": list(features.descriptor_names()), "sha256": features.DESCRIPTOR_NAMES_SHA256},
        "nan_policy": dict(nan),
        "signed_int8_stats": {name: asdict(value) for name, value in signed_stats.items()},
        "environment": dict(environment),
        "runtime_seconds": runtime_seconds,
        "peak_rss_gib": peak_rss_gib,
        "linux_compatibility_receipt": {"path": "linux_compatibility_receipt.json", "sha256": compatibility_sha256},
        "accounting": {"feature_rows_parsed": len(rows), "feature_rows_generated": len(rows), "maplight_block_operations": 4, "synthetic_catboost_fits": 1, "scientific_zeros": dict(SCIENTIFIC_ZEROS)},
        "authority": {key: False for key in ("targets", "features", "models", "predictions", "metrics", "fold_assignments", "submissions", "tdi", "test", "transduction")},
        "claim_boundary": "Label-free Linux feature construction and method compatibility only; no scientific fit, prediction, score, TDI, test, submission, or transductive authority.",
        "implementation": {
            "runner_source_sha256": pinned["hashes"]["runner_source"],
            "feature_kernel_sha256": pinned["hashes"]["feature_module"],
            "maplight_source_sha256": pinned["hashes"]["maplight_source"],
            "maplight_project_sha256": pinned["hashes"]["maplight_project"],
            "maplight_lock_sha256": pinned["hashes"]["maplight_uv_lock"],
            "python_pin_sha256": pinned["hashes"]["python_pin"],
        },
    }
def _validate_replay(prior: Path, current: Path) -> None:
    names = ("feature_rows.csv", "linux_compatibility_receipt.json", "morgan_binary.npy", "maplight_morgan_count.npy", "maplight_avalon_count.npy", "maplight_erg.npy", "maplight_rdkit_descriptors.npy")
    for name in names:
        _require((prior / name).read_bytes() == (current / name).read_bytes(), f"replay payload differs: {name}", stage="replay")
    first, _ = _load_json_bytes(prior / "feature_manifest.json")
    second, _ = _load_json_bytes(current / "feature_manifest.json")
    _require(first["build_id"] != second["build_id"], "replay build IDs are not distinct", stage="replay")
    ignored = {"build_id", "runtime_seconds", "peak_rss_gib"}
    first_semantic = {key: value for key, value in first.items() if key not in ignored}
    second_semantic = {key: value for key, value in second.items() if key not in ignored}
    _require(first_semantic == second_semantic, "replay semantic manifest differs", stage="replay")
def build_r3a_features(
    *,
    build_id: int,
    output_root: Path,
    manifest_path: Path,
    input_path: Path,
    expected_manifest_sha256: str,
    core_manifest_path: Path,
    expected_core_manifest_sha256: str,
    expected_rows: int = 4905,
    allow_synthetic: bool = False,
    prior_root: Path | None = None,
) -> Path:
    """Build one root; every output is promoted atomically and never overwritten."""
    _require(build_id in (1, 2), "build_id must be 1 or 2")
    _require(expected_rows == 4905 or allow_synthetic, "non-production row count requires explicit synthetic mode")
    _require(not output_root.exists() and not output_root.is_symlink(), "output root already exists")
    if build_id == 2:
        _require(prior_root is not None and prior_root.is_dir(), "build 2 requires build 1 root")
    started = time.perf_counter()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".r3a-features-", dir=str(output_root.parent)))
    try:
        pinned = _verify_contracts()
        environment = _verify_environment(pinned["stage_a"])
        contracts = pinned["hashes"]
        compatibility = run_linux_compatibility(pinned)
        compatibility_bytes = _json_bytes(compatibility)
        (staging / "linux_compatibility_receipt.json").write_bytes(compatibility_bytes)
        input_manifest, _, rows, input_hashes = _read_feature_input(manifest_path, input_path, expected_manifest_sha256, expected_rows, contract=pinned["global"], allow_synthetic=allow_synthetic)
        _require(input_manifest["contract_sha256"] == contracts["global_experiment_contract"], "feature-input global contract hash differs")
        core_morgan, core_reference = _load_core_reference(core_manifest_path, expected_core_manifest_sha256, input_hashes, pinned["global"], len(rows), pinned["hashes"]["core_morgan_worker"])
        raw = tuple(row["raw_smiles"] for row in rows)
        raw_hashes = tuple(row["raw_structure_sha256"] for row in rows)
        local, signed_stats = features.featurize_raw_structures_upstream_int8(raw, raw_hashes, nonfinite_policy="allow_gasteiger_charge_nan")
        arrays_data: dict[str, NDArray[Any]] = {
            "morgan_binary": np.ascontiguousarray(core_morgan, dtype=np.dtype("u1")),
            "maplight_morgan_count": np.ascontiguousarray(local.morgan_count, dtype=np.dtype("i1")),
            "maplight_avalon_count": np.ascontiguousarray(local.avalon_count, dtype=np.dtype("i1")),
            "maplight_erg": np.ascontiguousarray(local.erg, dtype=np.dtype("<f8")),
            "maplight_rdkit_descriptors": np.ascontiguousarray(local.rdkit_descriptors, dtype=np.dtype("<f8")),
        }
        row_bytes = _write_rows(rows)
        (staging / "feature_rows.csv").write_bytes(row_bytes)
        input_hashes = {**input_hashes, "feature_rows": _sha256_bytes(row_bytes)}
        arrays: dict[str, dict[str, Any]] = {}
        for name, array in arrays_data.items():
            path = staging / f"{name}.npy"
            features.write_npy_v1(path, array)
            arrays[name] = _array_record(name, path, array, allowed_nan=ALLOWED_NAN_COLUMNS if name == "maplight_rdkit_descriptors" else ())
        nan = _nan_record(arrays_data["maplight_rdkit_descriptors"])
        elapsed = time.perf_counter() - started
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**2)
        _require(elapsed <= 3600 and peak <= 8, "R3A resource limit exceeded", stage="resource")
        (staging / "feature_manifest.json").write_bytes(_json_bytes(_manifest(build_id, rows, input_manifest, input_hashes, core_reference, contracts, _sha256_bytes(compatibility_bytes), arrays, nan, signed_stats, environment, elapsed, peak, pinned)))
        if prior_root is not None:
            _validate_replay(prior_root, staging)
        expected_files = {"feature_rows.csv", "linux_compatibility_receipt.json", "feature_manifest.json", *(f"{name}.npy" for name in arrays_data)}
        _require({path.name for path in staging.iterdir()} == expected_files, "feature output file set differs")
        for path in staging.iterdir():
            os.chmod(path, 0o444)
        os.chmod(staging, 0o555)
        _promote_noreplace(staging, output_root)
        return output_root
    except Exception:
        _make_writable(staging)
        shutil.rmtree(staging, ignore_errors=True)
        raise
def _make_writable(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink():
        return
    if path.is_dir():
        path.chmod(0o755)
        for child in path.iterdir():
            _make_writable(child)
    else:
        path.chmod(0o644)
def _promote_noreplace(staging: Path, destination: Path) -> None:
    """Promote a complete root with Linux renameat2(RENAME_NOREPLACE) only."""
    _require(platform.system() == "Linux", "atomic promotion requires Linux", stage="promotion")
    _require(not destination.exists() and not destination.is_symlink(), "output root appeared before promotion", stage="promotion")
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
    except (AttributeError, OSError) as error:
        raise R3AFeatureError("renameat2 is unavailable; refusing non-atomic fallback", stage="promotion") from error
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    result = renameat2(-100, os.fsencode(staging), -100, os.fsencode(destination), 1)
    if result != 0:
        error_number = ctypes.get_errno()
        raise R3AFeatureError(f"atomic no-replace promotion failed: {os.strerror(error_number)}", stage="promotion")
def _cli_build(arguments: argparse.Namespace) -> int:
    build_r3a_features(
        build_id=arguments.build_id,
        output_root=Path(arguments.output_root),
        manifest_path=Path(arguments.manifest),
        input_path=Path(arguments.input),
        expected_manifest_sha256=arguments.expected_manifest_sha256,
        core_manifest_path=Path(arguments.core_manifest),
        expected_core_manifest_sha256=arguments.expected_core_manifest_sha256,
        prior_root=Path(arguments.prior_root) if arguments.prior_root else None,
    )
    return 0
def _cli_replay(arguments: argparse.Namespace) -> int:
    common = [
        sys.executable, str(Path(__file__).resolve()), "build",
        "--manifest", arguments.manifest, "--input", arguments.input,
        "--expected-manifest-sha256", arguments.expected_manifest_sha256,
        "--core-manifest", arguments.core_manifest,
        "--expected-core-manifest-sha256", arguments.expected_core_manifest_sha256,
    ]
    subprocess.run([*common, "--build-id", "1", "--output-root", arguments.build1], check=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    subprocess.run([*common, "--build-id", "2", "--output-root", arguments.build2, "--prior-root", arguments.build1], check=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    _validate_replay(Path(arguments.build1), Path(arguments.build2))
    return 0
def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "replay"):
        command = sub.add_parser(name)
        command.add_argument("--manifest", required=True)
        command.add_argument("--input", required=True)
        command.add_argument("--expected-manifest-sha256", required=True)
        command.add_argument("--core-manifest", required=True)
        command.add_argument("--expected-core-manifest-sha256", required=True)
        if name == "build":
            command.add_argument("--build-id", type=int, required=True)
            command.add_argument("--output-root", required=True)
            command.add_argument("--prior-root")
        else:
            command.add_argument("--build1", required=True)
            command.add_argument("--build2", required=True)
    return parser
if __name__ == "__main__":  # pragma: no cover - CLI exercised in the research env
    args = _parser().parse_args()
    raise SystemExit(_cli_build(args) if args.command == "build" else _cli_replay(args))

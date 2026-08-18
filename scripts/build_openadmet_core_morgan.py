#!/usr/bin/env python3
"""Build the receipt-bound D-032 standardized Morgan core array."""

from __future__ import annotations

import argparse
import csv
import ctypes
import errno
import io
import json
import os
import platform
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from rdkit import Chem, rdBase
from rdkit.Chem import rdFingerprintGenerator

ROOT = Path(__file__).resolve().parents[1]
GLOBAL_CONTRACT_PATH = ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract.json"
STANDARDIZER_PATH = ROOT / "src/cypshift/chemistry.py"
CORE_UV_LOCK_PATH = ROOT / "uv.lock"
GLOBAL_CONTRACT_SHA256 = (
    "d728684cc3794bbe01ea44342202944a378968f097cb8f5490852b63721a6285"
)
CORE_MORGAN_SCHEMA_VERSION = "cypshift.openadmet_cyp_2026.core_morgan.v1"
FEATURE_INPUT_SCHEMA_VERSION = "cypshift.openadmet_cyp_2026.feature_input.v1"
FEATURE_INPUT_COLUMNS = (
    "molecule_id",
    "raw_smiles",
    "raw_structure_sha256",
    "standardized_smiles",
    "standardized_structure_hash",
    "similarity_component_hash",
)
EXPECTED_ROWS = 4905
MORGAN_BITS = 4096
MORGAN_RADIUS = 2
STANDARDIZATION_POLICY_ID = "rdkit-cleanup-fragment-parent-v1"
GENERATOR_POLICY_ID = "d032-morgan-ecfp4-chiral-binary-4096-v1"
AUTHORITY = {
    "targets": False,
    "features": False,
    "models": False,
    "predictions": False,
    "metrics": False,
    "fold_assignments": False,
    "submissions": False,
    "tdi": False,
    "test": False,
    "transduction": False,
}


class CoreMorganError(ValueError):
    """Raised when the receipt-bound D-032 worker fails closed."""


@dataclass(frozen=True, slots=True)
class CoreMorganResult:
    """Paths and count from one completed core Morgan build."""

    array_path: Path
    manifest_path: Path
    row_count: int


def build_openadmet_core_morgan(
    *,
    manifest_path: Path,
    input_path: Path,
    expected_manifest_sha256: str,
    output_directory: Path,
    expected_rows: int = EXPECTED_ROWS,
) -> CoreMorganResult:
    """Build a C-contiguous NPY v1.0 uint8 Morgan array.

    ``expected_rows`` is intentionally a Python-only fixture hook.  The CLI
    does not expose it, so a production invocation remains pinned to 4,905.
    """

    if _destination_occupied(output_directory):
        raise CoreMorganError(
            f"output path already exists: {output_directory}; refusing overwrite"
        )
    if (
        isinstance(expected_rows, bool)
        or not isinstance(expected_rows, int)
        or expected_rows < 0
    ):
        raise CoreMorganError("expected_rows must be a nonnegative integer")
    _digest_text(expected_manifest_sha256, "expected projection manifest SHA-256")

    worker_data = _read_regular(Path(__file__), "core Morgan worker source")
    worker_hash = sha256(worker_data).hexdigest()
    contract_data = _read_regular(GLOBAL_CONTRACT_PATH, "global contract")
    _match_hash(contract_data, GLOBAL_CONTRACT_SHA256, "global contract")
    contract = _json_object(contract_data, "global contract")
    _verify_contract(contract)

    manifest_data = _read_regular(manifest_path, "feature-input manifest")
    _match_hash(
        manifest_data,
        expected_manifest_sha256,
        "feature-input manifest",
    )
    manifest = _json_object(manifest_data, "feature-input manifest")
    if _json_bytes(manifest) != manifest_data:
        raise CoreMorganError("feature-input manifest serialization differs")
    _verify_projection_manifest(manifest, contract, expected_rows)

    core = _object(_object(contract, "inputs"), "core_chemistry")
    standardizer_data = _read_regular(STANDARDIZER_PATH, "standardizer source")
    lock_data = _read_regular(CORE_UV_LOCK_PATH, "core uv lock")
    standardizer_hash = sha256(standardizer_data).hexdigest()
    lock_hash = sha256(lock_data).hexdigest()
    if standardizer_hash != _digest(core, "standardizer_source_sha256"):
        raise CoreMorganError("standardizer source hash mismatch")
    if lock_hash != _digest(core, "uv_lock_sha256"):
        raise CoreMorganError("core uv.lock hash mismatch")
    if manifest["standardizer_source_sha256"] != standardizer_hash:
        raise CoreMorganError("projection standardizer receipt mismatch")
    if manifest["core_uv_lock_sha256"] != lock_hash:
        raise CoreMorganError("projection core uv.lock receipt mismatch")
    _verify_runtime(core, manifest)

    input_data = _read_regular(input_path, "feature-input CSV")
    if not input_data.endswith(b"\n") or b"\r" in input_data:
        raise CoreMorganError("feature-input CSV line endings differ")
    _match_hash(input_data, _digest(manifest, "feature_input_sha256"), "feature-input CSV")
    rows = _parse_feature_input(input_data, expected_rows)

    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=MORGAN_RADIUS,
        fpSize=MORGAN_BITS,
        includeChirality=True,
    )
    payload, element_hash = _morgan_payload(rows, generator)
    npy_payload = _npy_v1(payload, expected_rows, MORGAN_BITS)
    npy_hash = sha256(npy_payload).hexdigest()
    output_manifest = {
        "schema_version": CORE_MORGAN_SCHEMA_VERSION,
        "contract_sha256": GLOBAL_CONTRACT_SHA256,
        "feature_input_manifest_sha256": expected_manifest_sha256,
        "feature_input_sha256": _digest(manifest, "feature_input_sha256"),
        "worker_source_sha256": worker_hash,
        "standardizer_source_sha256": standardizer_hash,
        "core_uv_lock_sha256": lock_hash,
        "core_python_version": platform.python_version(),
        "core_rdkit_version": rdBase.rdkitVersion,
        "standardization_policy_id": STANDARDIZATION_POLICY_ID,
        "generator_policy": {
            "id": GENERATOR_POLICY_ID,
            "algorithm": "rdkit.Chem.rdFingerprintGenerator.GetMorganGenerator",
            "radius": MORGAN_RADIUS,
            "fp_size": MORGAN_BITS,
            "include_chirality": True,
            "input": "standardized_smiles",
            "binary": True,
        },
        "array": {
            "path": "morgan_binary.npy",
            "shape": [expected_rows, MORGAN_BITS],
            "dtype": "uint8",
            "npy_version": "1.0",
            "c_contiguous": True,
            "npy_sha256": npy_hash,
            "element_sha256": element_hash,
        },
        "accounting": {
            "feature_input_rows_parsed": expected_rows,
            "standardized_structures_parsed": expected_rows,
            "target_values_parsed": 0,
            "target_values_retained": 0,
            "blinded_test_rows_opened": 0,
            "model_fits": 0,
            "predictions": 0,
            "metric_evaluations": 0,
        },
        "authority": dict(AUTHORITY),
    }
    manifest_payload = _json_bytes(output_manifest)
    _atomic_output(output_directory, npy_payload, manifest_payload)
    return CoreMorganResult(
        output_directory / "morgan_binary.npy",
        output_directory / "core_morgan_manifest.json",
        expected_rows,
    )


def _verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("schema_version") != (
        "cypshift.openadmet_cyp_2026.global_experiment_contract.v3"
    ):
        raise CoreMorganError("global contract schema mismatch")
    core = _object(_object(contract, "inputs"), "core_chemistry")
    if _text(core, "standardization_policy_id") != STANDARDIZATION_POLICY_ID:
        raise CoreMorganError("contract standardization policy mismatch")
    projection = _object(contract, "r3a_chemistry_projection")
    manifest_spec = _object(projection, "manifest")
    if manifest_spec.get("schema_version") != FEATURE_INPUT_SCHEMA_VERSION:
        raise CoreMorganError("contract projection schema mismatch")
    root = _object(contract, "r3a_feature_root")
    arrays = root.get("arrays")
    if not isinstance(arrays, list) or not arrays:
        raise CoreMorganError("contract Morgan array specification missing")
    morgan = arrays[0]
    if not isinstance(morgan, dict) or morgan.get("path") != "morgan_binary.npy":
        raise CoreMorganError("contract Morgan array path mismatch")
    if morgan.get("shape") != [EXPECTED_ROWS, MORGAN_BITS] or morgan.get("dtype") != "uint8":
        raise CoreMorganError("contract Morgan array shape or dtype mismatch")
    systems = _object(contract, "systems").get("systems")
    if not isinstance(systems, list):
        raise CoreMorganError("contract Morgan system specification missing")
    morgan_system = next(
        (
            item
            for item in systems
            if isinstance(item, dict) and item.get("id") == "TRACE-C1-MORGAN-CATBOOST"
        ),
        None,
    )
    if not isinstance(morgan_system, dict) or morgan_system.get("feature_spec_id") != GENERATOR_POLICY_ID:
        raise CoreMorganError("contract Morgan generator policy mismatch")


def _verify_projection_manifest(
    manifest: Mapping[str, Any],
    contract: Mapping[str, Any],
    expected_rows: int,
) -> None:
    required = {
        "schema_version",
        "contract_sha256",
        "direct_observations_sha256",
        "group_folds_sha256",
        "training_topology_sha256",
        "projector_source_sha256",
        "standardizer_source_sha256",
        "core_uv_lock_sha256",
        "core_python_version",
        "core_rdkit_version",
        "standardization_policy_id",
        "feature_input_sha256",
        "feature_input_columns",
        "feature_input_rows",
        "raw_structure_hash_formula",
        "standardized_structure_hash_formula",
        "accounting",
        "authority",
    }
    if set(manifest) != required:
        raise CoreMorganError("feature-input manifest schema differs")
    if manifest["schema_version"] != FEATURE_INPUT_SCHEMA_VERSION:
        raise CoreMorganError("feature-input manifest version differs")
    if manifest["contract_sha256"] != GLOBAL_CONTRACT_SHA256:
        raise CoreMorganError("feature-input global contract hash differs")
    if manifest["feature_input_columns"] != list(FEATURE_INPUT_COLUMNS):
        raise CoreMorganError("feature-input columns differ")
    if manifest["feature_input_rows"] != expected_rows:
        raise CoreMorganError("feature-input row count differs")
    if manifest["standardization_policy_id"] != STANDARDIZATION_POLICY_ID:
        raise CoreMorganError("feature-input standardization policy differs")
    projection = _object(contract, "r3a_chemistry_projection")
    projection_inputs = _object(projection, "inputs")
    contract_inputs = _object(contract, "inputs")
    for field, contract_key in (
        ("direct_observations_sha256", "direct_observations"),
        ("group_folds_sha256", "group_folds"),
        ("training_topology_sha256", "training_topology"),
    ):
        expected = _digest(projection_inputs, field)
        top_level = _digest(_object(contract_inputs, contract_key), "sha256")
        if expected != top_level or manifest[field] != expected:
            raise CoreMorganError(f"feature-input {field} receipt differs")
    core = _object(contract_inputs, "core_chemistry")
    for field, core_key in (
        ("standardizer_source_sha256", "standardizer_source_sha256"),
        ("core_uv_lock_sha256", "uv_lock_sha256"),
        ("core_python_version", "python_version"),
        ("core_rdkit_version", "rdkit_version"),
    ):
        if manifest[field] != _text(core, core_key):
            raise CoreMorganError(f"feature-input {field} receipt differs")
    formulas = _object(projection, "manifest").get("hash_formulas")
    if not isinstance(formulas, dict):
        raise CoreMorganError("contract hash formulas are missing")
    for field, formula_key in (
        ("raw_structure_hash_formula", "raw_structure_sha256"),
        ("standardized_structure_hash_formula", "standardized_structure_hash"),
    ):
        expected_formula = formulas.get(formula_key)
        if not isinstance(expected_formula, str) or manifest[field] != expected_formula:
            raise CoreMorganError(f"feature-input {field} differs")
    for key in (
        "contract_sha256",
        "direct_observations_sha256",
        "group_folds_sha256",
        "training_topology_sha256",
        "projector_source_sha256",
        "standardizer_source_sha256",
        "core_uv_lock_sha256",
        "feature_input_sha256",
    ):
        _digest_text(str(manifest[key]), key)
    accounting = _object(manifest, "accounting")
    frozen_accounting = _object(projection, "accounting")
    if set(accounting) != set(frozen_accounting):
        raise CoreMorganError("feature-input accounting schema differs")
    for key, value in accounting.items():
        if type(value) is not int or value < 0:
            raise CoreMorganError(f"feature-input accounting type differs: {key}")
    for key in ("target_values_parsed", "target_values_retained", "blinded_test_rows_opened"):
        if accounting[key] != 0:
            raise CoreMorganError(f"feature-input accounting differs: {key}")
    if expected_rows == EXPECTED_ROWS and accounting != frozen_accounting:
        raise CoreMorganError("feature-input accounting differs from v3 contract")
    authority = manifest.get("authority")
    expected_authority = _object(_object(projection, "manifest"), "authority")
    if authority != expected_authority:
        raise CoreMorganError("feature-input authority differs")


def _verify_runtime(core: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
    python_version = platform.python_version()
    rdkit_version = rdBase.rdkitVersion
    if python_version != _text(core, "python_version"):
        raise CoreMorganError("core Python version mismatch")
    if rdkit_version != _text(core, "rdkit_version"):
        raise CoreMorganError("core RDKit version mismatch")
    if manifest["core_python_version"] != python_version:
        raise CoreMorganError("projection Python receipt mismatch")
    if manifest["core_rdkit_version"] != rdkit_version:
        raise CoreMorganError("projection RDKit receipt mismatch")


def _parse_feature_input(data: bytes, expected_rows: int) -> list[dict[str, str]]:
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True)
        if next(reader, None) != list(FEATURE_INPUT_COLUMNS):
            raise CoreMorganError("feature-input CSV schema differs")
        rows: list[dict[str, str]] = []
        for values in reader:
            if len(values) != len(FEATURE_INPUT_COLUMNS):
                raise CoreMorganError("feature-input CSV field count differs")
            row = dict(zip(FEATURE_INPUT_COLUMNS, values, strict=True))
            if any(not row[field] for field in FEATURE_INPUT_COLUMNS):
                raise CoreMorganError("feature-input CSV contains an empty field")
            if row["standardized_structure_hash"] != sha256(
                row["standardized_smiles"].encode("utf-8")
            ).hexdigest():
                raise CoreMorganError("standardized structure hash differs")
            if row["raw_structure_sha256"] != sha256(
                row["raw_smiles"].encode("utf-8")
            ).hexdigest():
                raise CoreMorganError("raw structure hash differs")
            _digest_text(row["standardized_structure_hash"], "standardized_structure_hash")
            _digest_text(row["raw_structure_sha256"], "raw_structure_sha256")
            _digest_text(row["similarity_component_hash"], "similarity_component_hash")
            rows.append(row)
    except (UnicodeError, csv.Error) as exc:
        raise CoreMorganError("cannot parse feature-input CSV") from exc
    if len(rows) != expected_rows:
        raise CoreMorganError("feature-input CSV row count differs")
    if [row["molecule_id"] for row in rows] != sorted(row["molecule_id"] for row in rows):
        raise CoreMorganError("feature-input molecule order differs")
    if len({row["molecule_id"] for row in rows}) != expected_rows:
        raise CoreMorganError("feature-input molecule IDs are not unique")
    return rows


def _morgan_payload(
    rows: Sequence[Mapping[str, str]], generator: Any
) -> tuple[bytes, str]:
    payload = bytearray()
    for row in rows:
        molecule = Chem.MolFromSmiles(row["standardized_smiles"])
        if molecule is None:
            raise CoreMorganError("standardized SMILES cannot be parsed")
        fingerprint = generator.GetFingerprint(molecule)
        payload.extend(1 if fingerprint.GetBit(index) else 0 for index in range(MORGAN_BITS))
    element_hash = sha256(payload).hexdigest()
    return bytes(payload), element_hash


def _npy_v1(payload: bytes, rows: int, columns: int) -> bytes:
    header = f"{{'descr': '|u1', 'fortran_order': False, 'shape': ({rows}, {columns}), }}"
    header_bytes = header.encode("latin1")
    while (10 + len(header_bytes) + 1) % 16:
        header_bytes += b" "
    header_bytes += b"\n"
    if len(header_bytes) > 65535:
        raise CoreMorganError("NPY v1 header is too large")
    return b"\x93NUMPY\x01\x00" + len(header_bytes).to_bytes(2, "little") + header_bytes + payload


def _atomic_output(output: Path, array_data: bytes, manifest_data: bytes) -> None:
    staging: Path | None = None
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".core-morgan-", dir=output.parent))
        _write_new(staging / "morgan_binary.npy", array_data)
        _write_new(staging / "core_morgan_manifest.json", manifest_data)
        (staging / "morgan_binary.npy").chmod(0o444)
        (staging / "core_morgan_manifest.json").chmod(0o444)
        if _destination_occupied(output):
            raise CoreMorganError(f"output path already exists: {output}; refusing overwrite")
        staging.chmod(0o555)
        _rename_noreplace(staging, output)
        staging = None
    except Exception:
        if staging is not None:
            _make_writable(staging)
            shutil.rmtree(staging, ignore_errors=True)
        raise


def _make_writable(path: Path) -> None:
    if path.is_dir():
        path.chmod(0o755)
        for child in path.iterdir():
            _make_writable(child)
    else:
        path.chmod(0o644)


def _destination_occupied(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _rename_noreplace(source: Path, destination: Path) -> None:
    if platform.system() != "Linux" or os.name != "posix":
        raise CoreMorganError("atomic no-replace promotion requires Linux renameat2")
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
    except (AttributeError, OSError) as exc:
        raise CoreMorganError(
            "renameat2 is unavailable; refusing non-atomic promotion"
        ) from exc
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
        error_number = ctypes.get_errno()
        if error_number == errno.EEXIST:
            raise CoreMorganError(
                f"output path already exists: {destination}; refusing overwrite"
            )
        raise CoreMorganError(
            f"renameat2 no-replace promotion failed: {os.strerror(error_number)}"
        )


def _read_regular(path: Path, label: str) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise CoreMorganError(f"missing regular file: {label}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CoreMorganError(f"cannot read {label}") from exc


def _write_new(path: Path, data: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(data)
    except OSError as exc:
        raise CoreMorganError(f"cannot write {path}") from exc


def _match_hash(data: bytes, expected: str, label: str) -> None:
    if sha256(data).hexdigest() != expected:
        raise CoreMorganError(f"{label} SHA-256 mismatch")


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _json_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CoreMorganError(f"cannot parse {label}") from exc
    if not isinstance(value, dict):
        raise CoreMorganError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _object(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise CoreMorganError(f"{key} must be an object")
    return cast(dict[str, Any], item)


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise CoreMorganError(f"{key} must be non-empty text")
    return item


def _digest(value: Mapping[str, Any], key: str) -> str:
    item = _text(value, key)
    _digest_text(item, key)
    return item


def _digest_text(value: str, label: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise CoreMorganError(f"{label} must be lowercase SHA-256")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = build_openadmet_core_morgan(
            manifest_path=args.manifest,
            input_path=args.input,
            expected_manifest_sha256=args.expected_manifest_sha256,
            output_directory=args.out,
        )
    except CoreMorganError as exc:
        parser.error(str(exc))
    print(f"Core Morgan build complete: {result.row_count} rows; outputs: {result.array_path.parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

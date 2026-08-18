from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_openadmet_core_morgan.py"
SPEC = importlib.util.spec_from_file_location("core_morgan_worker_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
worker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = worker
SPEC.loader.exec_module(worker)


@pytest.fixture(autouse=True)
def _frozen_core_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise worker logic under its contract runtime in matrix CI.

    The actual pinned Python/RDKit environment is checked separately; ordinary
    CI deliberately spans the package's supported Python versions.
    """

    contract = json.loads(worker.GLOBAL_CONTRACT_PATH.read_text())
    core = contract["inputs"]["core_chemistry"]
    monkeypatch.setattr(worker.platform, "python_version", lambda: core["python_version"])
    monkeypatch.setattr(worker.rdBase, "rdkitVersion", core["rdkit_version"])


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _csv_bytes(rows: list[dict[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=worker.FEATURE_INPUT_COLUMNS, lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def _rows() -> list[dict[str, str]]:
    values = [("mol-a", "CCO"), ("mol-b", "c1ccccc1")]
    rows: list[dict[str, str]] = []
    for molecule_id, standardized in values:
        rows.append(
            {
                "molecule_id": molecule_id,
                "raw_smiles": standardized,
                "raw_structure_sha256": _sha(standardized.encode()),
                "standardized_smiles": standardized,
                "standardized_structure_hash": _sha(standardized.encode()),
                "similarity_component_hash": _sha(
                    ("component-" + molecule_id).encode()
                ),
            }
        )
    return rows


def _fixture(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    input_path = root / "feature_input.csv"
    input_data = _csv_bytes(_rows())
    input_path.write_bytes(input_data)
    standardizer_hash = _sha(worker.STANDARDIZER_PATH.read_bytes())
    lock_hash = _sha(worker.CORE_UV_LOCK_PATH.read_bytes())
    contract_data = worker.GLOBAL_CONTRACT_PATH.read_bytes()
    contract_hash = _sha(contract_data)
    contract = json.loads(contract_data)
    projection = contract["r3a_chemistry_projection"]
    core = contract["inputs"]["core_chemistry"]
    projection_inputs = projection["inputs"]
    formulas = projection["manifest"]["hash_formulas"]
    manifest: dict[str, Any] = {
        "schema_version": worker.FEATURE_INPUT_SCHEMA_VERSION,
        "contract_sha256": contract_hash,
        "direct_observations_sha256": projection_inputs["direct_observations_sha256"],
        "group_folds_sha256": projection_inputs["group_folds_sha256"],
        "training_topology_sha256": projection_inputs["training_topology_sha256"],
        "projector_source_sha256": _sha(
            (ROOT / "src/cypshift/openadmet_features.py").read_bytes()
        ),
        "standardizer_source_sha256": standardizer_hash,
        "core_uv_lock_sha256": lock_hash,
        "core_python_version": core["python_version"],
        "core_rdkit_version": core["rdkit_version"],
        "standardization_policy_id": worker.STANDARDIZATION_POLICY_ID,
        "feature_input_sha256": _sha(input_data),
        "feature_input_columns": list(worker.FEATURE_INPUT_COLUMNS),
        "feature_input_rows": 2,
        "raw_structure_hash_formula": formulas["raw_structure_sha256"],
        "standardized_structure_hash_formula": formulas["standardized_structure_hash"],
        "accounting": {
            "direct_observation_records_scanned": 0,
            "decoded_prefix_fields": 0,
            "opaque_suffixes_discarded": 0,
            "target_values_parsed": 0,
            "target_values_retained": 0,
            "blinded_test_rows_opened": 0,
        },
        "authority": {
            **projection["manifest"]["authority"],
        },
    }
    manifest_path = root / "feature_input_manifest.json"
    manifest_path.write_bytes(worker._json_bytes(manifest))
    return manifest_path, input_path


def _build(paths: tuple[Path, Path], output: Path) -> worker.CoreMorganResult:
    manifest_path, input_path = paths
    return worker.build_openadmet_core_morgan(
        manifest_path=manifest_path,
        input_path=input_path,
        expected_manifest_sha256=_sha(manifest_path.read_bytes()),
        output_directory=output,
        expected_rows=2,
    )


def test_manifest_receipt_is_verified_before_json_parse(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    expected = _sha(paths[0].read_bytes())
    paths[0].write_bytes(b"{not-json")
    with pytest.raises(worker.CoreMorganError, match="SHA-256 mismatch"):
        worker.build_openadmet_core_morgan(
            manifest_path=paths[0],
            input_path=paths[1],
            expected_manifest_sha256=expected,
            output_directory=tmp_path / "out",
            expected_rows=2,
        )


def test_csv_hash_and_policy_drift_fail_closed(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    paths[1].write_bytes(paths[1].read_bytes().replace(b"CCO", b"CCC", 1))
    with pytest.raises(worker.CoreMorganError, match="CSV SHA-256 mismatch"):
        _build(paths, tmp_path / "csv-drift")

    paths = _fixture(tmp_path / "policy")
    manifest = json.loads(paths[0].read_text())
    manifest["standardization_policy_id"] = "wrong-policy"
    paths[0].write_bytes(worker._json_bytes(manifest))
    with pytest.raises(worker.CoreMorganError, match="standardization policy"):
        _build(paths, tmp_path / "policy-drift")

    paths = _fixture(tmp_path / "structure")
    manifest = json.loads(paths[0].read_text())
    rows = _rows()
    rows[0]["standardized_structure_hash"] = _sha(b"wrong")
    input_data = _csv_bytes(rows)
    paths[1].write_bytes(input_data)
    manifest["feature_input_sha256"] = _sha(input_data)
    paths[0].write_bytes(worker._json_bytes(manifest))
    with pytest.raises(worker.CoreMorganError, match="standardized structure hash"):
        _build(paths, tmp_path / "structure-drift")


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("direct_observations_sha256", "direct_observations_sha256 receipt differs"),
        ("group_folds_sha256", "group_folds_sha256 receipt differs"),
        ("training_topology_sha256", "training_topology_sha256 receipt differs"),
        ("raw_structure_hash_formula", "raw_structure_hash_formula differs"),
        ("standardized_structure_hash_formula", "standardized_structure_hash_formula differs"),
        ("authority", "feature-input authority differs"),
        ("accounting", "feature-input accounting differs"),
    ],
)
def test_projection_receipt_policy_accounting_and_authority_drift(
    tmp_path: Path, field: str, message: str
) -> None:
    paths = _fixture(tmp_path / field)
    manifest = json.loads(paths[0].read_text())
    if field == "authority":
        manifest[field]["targets"] = True
    elif field == "accounting":
        manifest[field]["target_values_parsed"] = 1
    elif field.endswith("formula"):
        manifest[field] = "wrong-formula"
    else:
        manifest[field] = "0" * 64
    paths[0].write_bytes(worker._json_bytes(manifest))
    with pytest.raises(worker.CoreMorganError, match=message):
        _build(paths, tmp_path / f"{field}-out")


@pytest.mark.parametrize("mutation", ["extra", "missing", "boolean"])
def test_synthetic_accounting_schema_and_types_fail_closed(
    tmp_path: Path, mutation: str
) -> None:
    paths = _fixture(tmp_path / mutation)
    manifest = json.loads(paths[0].read_text())
    accounting = manifest["accounting"]
    if mutation == "extra":
        accounting["unexpected"] = 0
    elif mutation == "missing":
        del accounting["decoded_prefix_fields"]
    else:
        accounting["decoded_prefix_fields"] = False
    paths[0].write_bytes(worker._json_bytes(manifest))
    with pytest.raises(worker.CoreMorganError, match="accounting (schema|type) differs"):
        _build(paths, tmp_path / f"{mutation}-out")


@pytest.mark.parametrize(
    "field",
    [
        "standardizer_source_sha256",
        "core_uv_lock_sha256",
        "core_python_version",
        "core_rdkit_version",
    ],
)
def test_projection_core_runtime_receipt_drift_fails_closed(
    tmp_path: Path, field: str
) -> None:
    paths = _fixture(tmp_path / field)
    manifest = json.loads(paths[0].read_text())
    manifest[field] = "0" * 64 if field.endswith("sha256") else "0.0.0"
    paths[0].write_bytes(worker._json_bytes(manifest))
    with pytest.raises(worker.CoreMorganError, match="receipt differs"):
        _build(paths, tmp_path / f"{field}-out")


def test_worker_runtime_drift_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _fixture(tmp_path)
    monkeypatch.setattr(worker.platform, "python_version", lambda: "0.0.0")
    with pytest.raises(worker.CoreMorganError, match="core Python version mismatch"):
        _build(paths, tmp_path / "runtime-drift")


def test_array_exactness_npy_v1_and_read_only_outputs(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    result = _build(paths, tmp_path / "out")
    payload = result.array_path.read_bytes()
    assert payload[:8] == b"\x93NUMPY\x01\x00"
    array = np.load(io.BytesIO(payload), allow_pickle=False)
    assert array.shape == (2, 4096)
    assert array.dtype == np.dtype("u1")
    assert array.flags.c_contiguous
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=2, fpSize=4096, includeChirality=True
    )
    expected = np.zeros((2, 4096), dtype=np.uint8)
    for row_index, row in enumerate(_rows()):
        molecule = Chem.MolFromSmiles(row["standardized_smiles"])
        assert molecule is not None
        fingerprint = generator.GetFingerprint(molecule)
        for bit in range(4096):
            expected[row_index, bit] = fingerprint.GetBit(bit)
    assert np.array_equal(array, expected)
    assert result.array_path.stat().st_mode & 0o222 == 0
    assert result.manifest_path.stat().st_mode & 0o222 == 0
    assert result.array_path.parent.stat().st_mode & 0o222 == 0
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["array"]["npy_sha256"] == _sha(payload)
    assert manifest["array"]["element_sha256"] == _sha(expected.tobytes())
    assert all(value == 0 for key, value in manifest["accounting"].items() if key not in {"feature_input_rows_parsed", "standardized_structures_parsed"})


def test_determinism_and_atomic_cleanup_no_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _fixture(tmp_path)
    first = _build(paths, tmp_path / "first")
    second = _build(paths, tmp_path / "second")
    assert first.array_path.read_bytes() == second.array_path.read_bytes()
    assert first.manifest_path.read_bytes() == second.manifest_path.read_bytes()
    original_write = worker._write_new
    calls = 0

    def fail_second(path: Path, data: bytes) -> None:
        nonlocal calls
        calls += 1
        original_write(path, data)
        if calls == 2:
            raise RuntimeError("synthetic write failure")

    monkeypatch.setattr(worker, "_write_new", fail_second)
    with pytest.raises(RuntimeError, match="synthetic write failure"):
        _build(paths, tmp_path / "failed")
    assert not (tmp_path / "failed").exists()
    assert not list(tmp_path.glob(".core-morgan-*"))
    with pytest.raises(worker.CoreMorganError, match="refusing overwrite"):
        _build(paths, tmp_path / "first")


def test_atomic_promotion_rejects_dangling_symlink_and_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _fixture(tmp_path / "symlink")
    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "missing", target_is_directory=True)
    with pytest.raises(worker.CoreMorganError, match="refusing overwrite"):
        _build(paths, dangling)
    assert dangling.is_symlink()

    race_paths = _fixture(tmp_path / "race")
    destination = tmp_path / "race-out"
    original_rename = worker._rename_noreplace

    def create_destination(source: Path, target: Path) -> None:
        target.mkdir()
        original_rename(source, target)

    monkeypatch.setattr(worker, "_rename_noreplace", create_destination)
    with pytest.raises(worker.CoreMorganError, match="refusing overwrite"):
        _build(race_paths, destination)
    assert destination.is_dir()
    assert not list(destination.iterdir())

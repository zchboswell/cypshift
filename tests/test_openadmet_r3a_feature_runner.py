"""Synthetic-only acceptance tests for the bounded R3A feature process."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import importlib.util
import json
import platform
import sys
from pathlib import Path
from typing import Any

import pytest

np = pytest.importorskip("numpy")

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "research/maplight-fixed/run_r3a_features.py"
RESEARCH_ROOT = RUNNER_PATH.parent
if str(RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCH_ROOT))
spec = importlib.util.spec_from_file_location("r3a_feature_runner_test", RUNNER_PATH)
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _input_rows() -> list[dict[str, str]]:
    with (ROOT / "benchmarks/fixtures/maplight_fixed_parity_v1.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        source_rows = list(csv.DictReader(handle))[:2]
    rows: list[dict[str, str]] = []
    for source in source_rows:
        raw = str(source["raw_smiles"])
        molecule_id = f"synthetic-{source['fixture_id']}"
        rows.append(
            {
                "molecule_id": molecule_id,
                "raw_smiles": raw,
                "raw_structure_sha256": _sha256(raw.encode()),
                "standardized_smiles": raw,
                "standardized_structure_hash": _sha256(raw.encode()),
                "similarity_component_hash": _sha256(("component-" + molecule_id).encode()),
            }
        )
    return sorted(rows, key=lambda row: row["molecule_id"])


def _write_input(root: Path, *, extra_column: bool = False) -> tuple[Path, Path, str]:
    root.mkdir(parents=True, exist_ok=True)
    rows = _input_rows()
    columns = list(runner.INPUT_COLUMNS)
    if extra_column:
        columns.append("unexpected")
        for row in rows:
            row["unexpected"] = "no"
    input_path = root / "feature_input.csv"
    with input_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    input_bytes = input_path.read_bytes()
    contract_sha = _sha256(
        (ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract.json").read_bytes()
    )
    manifest: dict[str, Any] = {
        "schema_version": "cypshift.openadmet_cyp_2026.feature_input.v1",
        "contract_sha256": contract_sha,
        "direct_observations_sha256": "00b1ac95cc73dda2699f2f05bc33200d1119a197d7a92ae900cde78d722f00b7",
        "group_folds_sha256": "91678d68b2f9ac3913f6b679dd284f82ba2a040d803de83655bf89906f31f774",
        "training_topology_sha256": "710978431402dbb737244bf01a9f4d9e4e398181400627db680a4f12d06d3b8a",
        "projector_source_sha256": _sha256((ROOT / "src/cypshift/openadmet_features.py").read_bytes()),
        "standardizer_source_sha256": "21d8df35f001c790290d3ef2c836c9f459015b5db0f48c8f6e44436f9181103a",
        "core_uv_lock_sha256": "33d9382256de7992ce9ff7a7edc125d4771546a25ef3be5f1160627846d2c9b6",
        "core_python_version": "3.12.3",
        "core_rdkit_version": "2026.03.5",
        "standardization_policy_id": "rdkit-cleanup-fragment-parent-v1",
        "feature_input_sha256": _sha256(input_bytes),
        "feature_input_columns": list(runner.INPUT_COLUMNS),
        "feature_input_rows": len(rows),
        "raw_structure_hash_formula": "lowercase SHA256 hex of the exact raw_smiles UTF-8 bytes",
        "standardized_structure_hash_formula": "lowercase SHA256 hex of the exact standardized_smiles UTF-8 bytes",
        "accounting": {
            "direct_observation_records_scanned": 19620,
            "decoded_prefix_fields": 156960,
            "opaque_suffixes_discarded": 19620,
            "target_values_parsed": 0,
            "target_values_retained": 0,
            "blinded_test_rows_opened": 0,
        },
        "authority": {
            "targets": False,
            "features": False,
            "models": False,
            "predictions": False,
            "metrics": False,
            "fold_assignments": False,
            "submissions": False,
        },
    }
    manifest_path = root / "feature_input_manifest.json"
    manifest_bytes = runner._json_bytes(manifest)
    manifest_path.write_bytes(manifest_bytes)
    return manifest_path, input_path, _sha256(manifest_bytes)


def _write_core(root: Path, rows: int, feature_manifest_sha: str, feature_input_sha: str) -> tuple[Path, str]:
    path = root / "morgan_binary.npy"
    array = np.zeros((rows, 4096), dtype=np.uint8)
    with path.open("wb") as handle:
        np.lib.format.write_array(handle, array, version=(1, 0), allow_pickle=False)
    payload = path.read_bytes()
    global_sha = _sha256((ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract.json").read_bytes())
    manifest: dict[str, Any] = {
        "schema_version": "cypshift.openadmet_cyp_2026.core_morgan.v1",
        "contract_sha256": global_sha,
        "feature_input_manifest_sha256": feature_manifest_sha,
        "feature_input_sha256": feature_input_sha,
        "array": {
            "path": "morgan_binary.npy",
            "npy_sha256": _sha256(payload),
            "element_sha256": _sha256(array.tobytes(order="C")),
            "shape": [rows, 4096],
            "dtype": "uint8",
            "npy_version": "1.0",
            "c_contiguous": True,
        },
        "worker_source_sha256": runner.PINNED_FILE_SHA256["core_morgan_worker"],
        "standardizer_source_sha256": "21d8df35f001c790290d3ef2c836c9f459015b5db0f48c8f6e44436f9181103a",
        "core_uv_lock_sha256": "33d9382256de7992ce9ff7a7edc125d4771546a25ef3be5f1160627846d2c9b6",
        "core_python_version": "3.12.3",
        "core_rdkit_version": "2026.03.5",
        "standardization_policy_id": "rdkit-cleanup-fragment-parent-v1",
        "generator_policy": {
            "id": "d032-morgan-ecfp4-chiral-binary-4096-v1",
            "algorithm": "rdkit.Chem.rdFingerprintGenerator.GetMorganGenerator",
            "radius": 2,
            "fp_size": 4096,
            "include_chirality": True,
            "input": "standardized_smiles",
            "binary": True,
        },
        "accounting": {
            "feature_input_rows_parsed": rows,
            "standardized_structures_parsed": rows,
            "target_values_parsed": 0,
            "target_values_retained": 0,
            "blinded_test_rows_opened": 0,
            "model_fits": 0,
            "predictions": 0,
            "metric_evaluations": 0,
        },
        "authority": {key: False for key in ("targets", "features", "models", "predictions", "metrics", "fold_assignments", "submissions", "tdi", "test", "transduction")},
    }
    manifest_path = root / "core_morgan_manifest.json"
    manifest_path.write_bytes(runner._json_bytes(manifest))
    return manifest_path, _sha256(manifest_path.read_bytes())


def _skip_unless_pinned_environment() -> None:
    if sys.version_info[:3] != (3, 10, 13):
        pytest.skip("Linux MapLight compatibility requires the pinned research Python")
    expected = {"catboost": "1.2.1", "numpy": "1.25.2", "pandas": "2.0.3", "rdkit": "2023.3.3", "scikit-learn": "1.3.0", "scipy": "1.11.2"}
    for package, version in expected.items():
        try:
            observed = runner._normalize_version(importlib.metadata.version(package))
        except importlib.metadata.PackageNotFoundError:
            pytest.skip("pinned research dependencies are unavailable")
        if observed != runner._normalize_version(version):
            pytest.skip("Linux MapLight compatibility requires the pinned research dependencies")
    installed = {
        runner._normalize_package(str(distribution.metadata["Name"]))
        for distribution in importlib.metadata.distributions()
        if distribution.metadata["Name"]
    }
    expected_set = {
        runner._normalize_package(name.rsplit("@", 1)[0])
        for name in runner._verify_contracts()["stage_a"]["compatible_environment"]["resolved_package_licenses"]
    }
    if installed != expected_set:
        pytest.skip("Linux MapLight compatibility requires the exact frozen package set")


def test_input_receipt_is_verified_before_csv_parse(tmp_path: Path) -> None:
    manifest, input_path, manifest_sha = _write_input(tmp_path)
    with pytest.raises(runner.R3AFeatureError, match="manifest SHA|pinned bytes"):
        runner._read_feature_input(manifest, input_path, "f" * 64)
    extra_manifest, extra_input, extra_sha = _write_input(tmp_path / "extra", extra_column=True)
    with pytest.raises(runner.R3AFeatureError, match="CSV schema"):
        runner._read_feature_input(extra_manifest, extra_input, extra_sha)
    assert manifest_sha == _sha256(manifest.read_bytes())


@pytest.mark.parametrize(
    ("field", "drift_value"),
    (
        ("group_folds_sha256", "f" * 64),
        ("standardizer_source_sha256", "f" * 64),
        ("core_python_version", "3.12.2"),
        ("standardization_policy_id", "drifted-policy"),
        ("raw_structure_hash_formula", "not-the-frozen-formula"),
    ),
)
def test_input_receipt_rejects_v3_contract_drift(
    tmp_path: Path, field: str, drift_value: str
) -> None:
    manifest, input_path, _ = _write_input(tmp_path)
    value = json.loads(manifest.read_text())
    value[field] = drift_value
    manifest.write_bytes(runner._json_bytes(value))
    with pytest.raises(runner.R3AFeatureError, match="differs"):
        runner._read_feature_input(manifest, input_path, _sha256(manifest.read_bytes()))


def test_array_record_uses_contract_dimensions_and_dtype(tmp_path: Path) -> None:
    path = tmp_path / "morgan_binary.npy"
    array = np.zeros((2, 4096), dtype=np.uint8)
    with path.open("wb") as handle:
        np.lib.format.write_array(handle, array, version=(1, 0), allow_pickle=False)
    record = runner._array_record("morgan_binary", path, array)
    assert record["dtype"] == "uint8"
    assert record["shape"] == [2, 4096]
    with pytest.raises(runner.R3AFeatureError, match="dtype"):
        runner._array_record("morgan_binary", path, np.zeros((2, 4096), dtype=np.int8))


@pytest.mark.skipif(platform.system() != "Linux", reason="renameat2 promotion is Linux-only")
def test_atomic_promotion_rejects_dangling_symlink_and_late_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dangling_stage = tmp_path / "stage-dangling"
    dangling_stage.mkdir()
    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "missing-target", target_is_directory=True)
    with pytest.raises(runner.R3AFeatureError, match="output root appeared"):
        runner._promote_noreplace(dangling_stage, dangling)
    stage = tmp_path / "stage"
    stage.mkdir()
    destination = tmp_path / "destination"
    original = runner._promote_noreplace

    def create_destination_before_syscall(source: Path, target: Path) -> None:
        target.mkdir()
        original(source, target)

    monkeypatch.setattr(runner, "_promote_noreplace", create_destination_before_syscall)
    with pytest.raises(runner.R3AFeatureError, match="output root appeared"):
        runner._promote_noreplace(stage, destination)
    assert stage.is_dir()


def test_core_reference_is_required_for_standardized_morgan(tmp_path: Path) -> None:
    _skip_unless_pinned_environment()
    manifest, input_path, manifest_sha = _write_input(tmp_path)
    with pytest.raises(runner.R3AFeatureError, match="core|regular file"):
        runner.build_r3a_features(
            build_id=1,
            output_root=tmp_path / "build",
            manifest_path=manifest,
            input_path=input_path,
            expected_manifest_sha256=manifest_sha,
            core_manifest_path=tmp_path / "not-generated-by-maplight.json",
            expected_core_manifest_sha256="a" * 64,
            expected_rows=2,
            allow_synthetic=True,
        )


def test_fixture_parity_signed_boundaries_and_nan_probe_are_label_free() -> None:
    _skip_unless_pinned_environment()
    receipt = runner.run_linux_compatibility()
    assert receipt["signed_int8_witnesses"] == {"127": 127, "128": -128, "144": -112}
    assert all(value["equal"] for value in receipt["upstream_vs_local"].values())
    assert receipt["catboost_nan_probe"]["resolved_nan_mode"] == "Min"
    assert all(receipt["accounting"][key] == 0 for key in runner.SCIENTIFIC_ZEROS)


def test_two_synthetic_builds_have_byte_identical_payloads(tmp_path: Path) -> None:
    _skip_unless_pinned_environment()
    manifest, input_path, manifest_sha = _write_input(tmp_path)
    core_path, core_sha = _write_core(tmp_path, 2, manifest_sha, _sha256(input_path.read_bytes()))
    first = runner.build_r3a_features(
        build_id=1,
        output_root=tmp_path / "build-1",
        manifest_path=manifest,
        input_path=input_path,
        expected_manifest_sha256=manifest_sha,
        core_manifest_path=core_path,
        expected_core_manifest_sha256=core_sha,
        expected_rows=2,
        allow_synthetic=True,
    )
    second = runner.build_r3a_features(
        build_id=2,
        output_root=tmp_path / "build-2",
        manifest_path=manifest,
        input_path=input_path,
        expected_manifest_sha256=manifest_sha,
        core_manifest_path=core_path,
        expected_core_manifest_sha256=core_sha,
        expected_rows=2,
        allow_synthetic=True,
        prior_root=first,
    )
    names = (
        "feature_rows.csv",
        "morgan_binary.npy",
        "maplight_morgan_count.npy",
        "maplight_avalon_count.npy",
        "maplight_erg.npy",
        "maplight_rdkit_descriptors.npy",
    )
    for name in names:
        assert (first / name).read_bytes() == (second / name).read_bytes()
    first_manifest = json.loads((first / "feature_manifest.json").read_text())
    second_manifest = json.loads((second / "feature_manifest.json").read_text())
    assert first_manifest["build_id"] == 1
    assert second_manifest["build_id"] == 2
    assert first_manifest["arrays"] == second_manifest["arrays"]
    assert first_manifest["authority"]["targets"] is False
    assert first_manifest["accounting"]["scientific_zeros"] == runner.SCIENTIFIC_ZEROS
    descriptors = np.load(first / "maplight_rdkit_descriptors.npy", allow_pickle=False)
    assert descriptors.shape == (2, 200)
    assert np.isinf(descriptors).sum() == 0
    assert set(np.argwhere(np.isnan(descriptors))[:, 1].tolist()).issubset(set(runner.ALLOWED_NAN_COLUMNS))

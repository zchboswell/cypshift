from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "benchmarks/maplight_fixed_int8_compat_contract.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contract() -> dict[str, Any]:
    value = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_compatibility_contract_preserves_safe_failure_and_exact_inputs() -> None:
    contract = _contract()

    assert contract["schema_version"] == (
        "cypshift.maplight_fixed_int8_compat_contract.v1"
    )
    assert contract["status"] == "pre_result_frozen"
    assert contract["authorization"]["does_not_repair_or_replace_safe_experiment"]

    for record in contract["parents"].values():
        assert _sha256(ROOT / record["path"]) == record["sha256"]
    for name in ("shadow_rows", "shadow_manifest"):
        record = contract["frozen_inputs"][name]
        assert _sha256(ROOT / record["path"]) == record["sha256"]

    environment = contract["frozen_inputs"]["environment"]
    assert (
        _sha256(ROOT / "research/maplight-fixed/pyproject.toml")
        == environment["project_sha256"]
    )
    assert (
        _sha256(ROOT / "research/maplight-fixed/uv.lock") == environment["lock_sha256"]
    )
    assert (
        _sha256(ROOT / "research/maplight-fixed/.python-version")
        == environment["python_pin_sha256"]
    )


def test_compatibility_contract_has_one_scientific_change_and_two_builds() -> None:
    contract = _contract()
    change = contract["sole_scientific_change"]

    assert change["blocks"] == ["morgan_count", "avalon_count"]
    assert "zero-length" in change["conversion"]
    assert "Do not impose an upper count bound" in change["preconversion_validation"]
    assert change["required_witness"]["expected_int8_value_at_bin_1"] == -112

    assert contract["execution"]["build_ids"] == [1, 2]
    assert len(contract["execution"]["output_roots"]) == 2
    assert len(contract["execution"]["failure_roots"]) == 2
    assert contract["execution"]["success_files_per_root"] == [
        "feature_rows.csv",
        "binary_morgan.npy",
        "morgan_count.npy",
        "avalon_count.npy",
        "erg.npy",
        "rdkit_descriptors.npy",
        "feature_manifest.json",
    ]
    assert contract["unchanged_rules"]["persisted_dimensions"] == {
        "binary_morgan": 2048,
        "morgan_count": 1024,
        "avalon_count": 1024,
        "erg": 315,
        "rdkit_descriptors": 200,
        "maplight_fixed_derived": 2563,
    }


def test_compatibility_contract_is_scientifically_zero_before_execution() -> None:
    accounting = _contract()["accounting_before_execution"]

    assert set(accounting) == {
        "compatibility_feature_builds",
        "persisted_block_arrays",
        "target_values_parsed",
        "model_fits",
        "predictions",
        "metric_evaluations",
        "public_test_rows_used",
        "public_test_labels_parsed",
        "public_test_family_task_slots_consumed",
        "gin_weight_bytes_downloaded",
        "challenge_assumptions_added",
    }
    assert all(type(value) is int and value == 0 for value in accounting.values())
    assert "model fitting" in _contract()["firewall"]["forbidden"]
    assert "public-test rows or labels" in _contract()["firewall"]["forbidden"]

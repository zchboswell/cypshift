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
    safe_blocker = json.loads(
        (
            ROOT / "benchmarks/receipts/maplight_fixed_stage_a_feature_blocker.json"
        ).read_text(encoding="utf-8")
    )

    assert contract["schema_version"] == (
        "cypshift.maplight_fixed_int8_compat_contract.v1"
    )
    assert contract["status"] == "pre_result_frozen"
    assert contract["authorization"]["does_not_repair_or_replace_safe_experiment"]

    for name in ("safe_stage_a_contract", "safe_blocker_record"):
        record = contract["parents"][name]
        assert _sha256(ROOT / record["path"]) == record["sha256"]
    assert (
        contract["parents"]["safe_blocker_artifact"] == safe_blocker["failure_receipt"]
    )
    assert (
        contract["parents"]["parity_receipt"]["sha256"]
        == safe_blocker["inputs"]["parity_receipt_sha256"]
    )
    assert (
        contract["frozen_inputs"]["shadow_rows"]["sha256"]
        == safe_blocker["inputs"]["shadow_rows_sha256"]
    )
    assert (
        contract["frozen_inputs"]["shadow_manifest"]["sha256"]
        == safe_blocker["inputs"]["shadow_manifest_sha256"]
    )

    for record in (
        contract["parents"]["safe_blocker_artifact"],
        contract["parents"]["parity_receipt"],
        contract["frozen_inputs"]["shadow_rows"],
        contract["frozen_inputs"]["shadow_manifest"],
    ):
        path = ROOT / record["path"]
        if path.exists():
            assert _sha256(path) == record["sha256"]

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
    assert contract["inheritance"]["model_authority"].startswith(
        "The compatible roots may feed only the already frozen Stage A"
    )
    assert set(contract["inheritance"]["overrides"]) == {
        "/feature_contract/count_safety",
        "/parity_fixture/required_comparisons/5",
        "/parity_fixture/adversarial_tests/3",
        "/stop_rules/5",
    }
    assert [
        row["expected_converted_int8"]
        for row in contract["compatibility_parity"]["count_boundaries"]
    ] == [127, -128, -112]
    assert contract["compatibility_parity"]["required_before_real_rows"] is True
    assert contract["compatibility_parity"]["success_accounting"] == {
        "upstream_fixture_processes_attempted": 1,
        "upstream_fixture_processes_completed": 1,
        "compatible_fixture_processes_attempted": 2,
        "compatible_fixture_processes_completed": 2,
        "boundary_conversions_attempted": 9,
        "boundary_conversions_completed": 9,
        "fixture_arrays_generated": 17,
        "fixture_row_loads": 24,
        "retained_arrays": 6,
        "real_feature_rows_parsed": 0,
        "target_values_parsed": 0,
        "model_fits": 0,
        "predictions": 0,
        "metric_evaluations": 0,
        "public_test_rows_used": 0,
        "public_test_labels_parsed": 0,
        "public_test_family_task_slots_consumed": 0,
        "gin_weight_bytes_downloaded": 0,
        "challenge_assumptions_added": 0,
    }

    assert contract["execution"]["build_ids"] == [1, 2]
    assert contract["execution"]["fresh_process_per_build"] is True
    assert contract["execution"]["copy_or_reuse_build_1_arrays_forbidden"] is True
    assert "process-local" in contract["execution"]["cache_scope"]
    assert (
        "Before build 2 resolves shadow rows"
        in contract["execution"]["build_2_precondition"]
    )
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
    assert contract["artifact_schemas"]["success_manifest"][
        "per_build_accounting_fields"
    ]
    assert contract["artifact_schemas"]["success_manifest"]["build_2_cumulative_fields"]
    assert contract["artifact_schemas"]["success_manifest"][
        "build_1_expected_accounting"
    ] == {
        "attempted_feature_builds": 1,
        "completed_feature_builds": 1,
        "source_rows_parsed": 30038,
        "exact_raw_featurizations": 15399,
        "persisted_block_arrays": 5,
    }
    assert contract["artifact_schemas"]["success_manifest"][
        "build_2_expected_cumulative_accounting"
    ] == {
        "attempted_feature_builds": 2,
        "completed_feature_builds": 2,
        "source_rows_parsed": 60076,
        "exact_raw_featurizations": 30798,
        "persisted_block_arrays": 10,
    }
    assert (
        "Remove every partial staging root"
        in contract["artifact_schemas"]["failure_receipt"]["rules"]
    )
    assert contract["firewall"]["scope"].endswith("feature builds only.")
    assert "model_cell_process" in contract["firewall"]["downstream_handoff"]


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

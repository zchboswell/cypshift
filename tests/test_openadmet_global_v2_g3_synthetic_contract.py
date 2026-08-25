from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT = BENCHMARK / "global_v2_g3_synthetic_contract.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_g3_synthetic_contract_binds_accepted_parents() -> None:
    contract = _read(CONTRACT)
    assert contract["status"] == "G2_6S_EXP_G3_SYNTHETIC_CONTRACT_FROZEN"
    assert contract["experiment_id"] == "EXP-G3"
    assert contract["base_commit"] == "8977404620b125bae2ea1b3e9cf4ded807784d4b"
    assert list(contract["parents"]) == [
        "g3_single_expert_contract",
        "global_v2_synthetic_firewall_acceptance",
        "fixed_maplight_reproduction",
    ]
    for parent in contract["parents"].values():
        path = BENCHMARK / parent["path"]
        assert path.is_file()
        assert _sha256(path) == parent["sha256"]


def test_g3_runtime_is_exact_but_uncreated_at_contract_freeze() -> None:
    contract = _read(CONTRACT)
    runtime = contract["runtime_contract"]
    assert runtime["platform"].startswith("Linux x86_64 CPU on AMD Ryzen 9 7950X")
    assert runtime["python"] == "3.12.3"
    assert runtime["numpy"] == "2.5.2"
    assert runtime["scipy"] == "1.18.0"
    assert runtime["rdkit"] == "2026.03.5"
    assert runtime["lightgbm"] == "4.7.0"
    assert runtime["lightgbm_manylinux_wheel_sha256"] == (
        "d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7"
    )
    assert runtime["parent_uv_lock_sha256"] == _sha256(ROOT / "uv.lock")
    assert runtime["isolated_project_path"] == "research/lightgbm-global"
    assert runtime["future_isolated_pyproject_sha256"] is None
    assert runtime["future_isolated_uv_lock_sha256"] is None

    accounting = contract["current_milestone_accounting"]
    assert accounting["runtime_environments_created"] == 0
    assert accounting["dependency_changes"] == 0
    assert accounting["implementation_files_created"] == 0


def test_g3_mechanics_fixture_preserves_family_and_feature_shape() -> None:
    contract = _read(CONTRACT)
    fixture = contract["synthetic_mechanics_fixture"]
    assert fixture["molecules"] == 100
    assert fixture["components"] == 50
    assert fixture["molecules_per_component"] == 2
    assert fixture["development_components"] == 40
    assert fixture["development_molecules"] == 80
    assert fixture["confirmatory_components"] == 10
    assert fixture["confirmatory_molecules"] == 20
    assert fixture["targets"]["exact_finite_central_per_endpoint"] == 64
    assert fixture["targets"]["exact_missing_central_per_endpoint"] == 16

    features = fixture["features"]
    assert features["columns"] == 2248
    assert features["morgan_columns"] == 2048
    assert features["descriptor_columns"] == 200
    assert "Preserve descriptor NaN" in features["order_and_missing_rule"]
    assert "Add no" in contract["occam_boundary"]
    assert "imputation" in contract["occam_boundary"]

    variants = fixture["physical_order_variants"]
    assert variants["root_a"].startswith("canonical input row")
    assert variants["root_b"].startswith("reverse every physical input row")


def test_g3_model_double_exhausts_exact_topology_before_truth() -> None:
    contract = _read(CONTRACT)
    double = contract["model_double_contract"]
    assert double["exact_fit_identities_per_root"] == 3 * 5 * 4
    assert double["exact_fit_identities_across_roots"] == 2 * 3 * 5 * 4
    assert double["outer_prediction_rows_per_root"] == 3 * 80 * 4
    assert "disjoint" in double["family_gate"]
    assert "validation truth" in double["capability_gate"]
    assert "All sixty" in double["truth_freeze_gate"]


def test_g3_exact_probe_is_full_width_and_bounded() -> None:
    contract = _read(CONTRACT)
    probe = contract["exact_lightgbm_probe"]
    assert probe["rows_per_root"] == 3908
    assert probe["columns"] == 2248
    assert probe["training_rows"] == 3120
    assert probe["prediction_rows"] == 788
    assert probe["training_rows"] + probe["prediction_rows"] == probe["rows_per_root"]
    assert probe["probe_endpoints"] == ["CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4"]
    assert probe["fits_per_root"] == 4
    assert probe["fits_across_roots"] == 8
    assert probe["predictions_per_root"] == 4 * 788
    assert "num_boost_round=1500" in probe["model_api"]
    assert "exactly between roots" in probe["prediction_gate"]

    boundary = contract["implementation_boundary"]
    assert "at most two pre-formal tiny LightGBM API smokes" in boundary[
        "allowed_after_integration"
    ]
    assert "at most 64 rows" in boundary["tiny_smoke_limit"]
    assert "16 boosting rounds" in boundary["tiny_smoke_limit"]


def test_g3_deterministic_terminals_separate_timing() -> None:
    contract = _read(CONTRACT)
    terminal = contract["deterministic_terminal_contract"]
    assert terminal["relative_files"] == [
        "g3_synthetic_feature_receipt.json",
        "g3_synthetic_fit_identity_receipts.csv",
        "g3_synthetic_outer_predictions.csv",
        "g3_synthetic_metrics.json",
        "g3_probe_parameter_receipts.csv",
        "g3_probe_predictions.csv",
        "g3_synthetic_terminal_manifest.json",
    ]
    assert "all seven relative files" in terminal["comparison"]
    assert "outside the deterministic seven-file map" in terminal["timing_boundary"]
    assert "Track only one aggregate" in terminal["publication"]


def test_g3_resource_projection_is_conservative_and_conjunctive() -> None:
    contract = _read(CONTRACT)
    parent = _read(BENCHMARK / "global_v2_g3_single_expert_contract.json")
    ceiling = parent["resource_ceiling"]
    projection = contract["resource_projection"]
    assert projection["scientific_fits"] == 60
    assert projection["wall_formula"].startswith(
        "60 * worse_root_max_exact_fit_wall_seconds"
    )
    assert projection["cpu_formula"].startswith(
        "60 * worse_root_max_exact_fit_cpu_seconds"
    )
    assert "maximum individual exact fit" in projection["wall_formula"]
    assert "maximum individual exact fit" in projection["cpu_formula"]
    assert projection["maximum_projected_cpu_core_hours"] == pytest.approx(
        0.8 * ceiling["cpu_core_hours"]
    )
    assert projection["maximum_projected_wall_hours"] == pytest.approx(
        0.8 * ceiling["maximum_wall_hours"]
    )
    assert projection["maximum_projected_restricted_storage_gb"] == pytest.approx(
        0.8 * ceiling["restricted_storage_gb"]
    )
    assert projection["maximum_peak_rss_gib"] == pytest.approx(
        0.8 * ceiling["maximum_peak_rss_gib"]
    )
    assert projection["maximum_projected_gpu_hours"] == 0
    assert "Every gate is conjunctive" in projection["logic"]
    for forbidden_repair in (
        "alternate thread count",
        "sparse input",
        "optimization",
        "smaller probe",
        "reduced tree count",
        "retry",
    ):
        assert forbidden_repair in projection["logic"]


def test_g3_synthetic_acceptance_counts_and_boundaries_are_exact() -> None:
    contract = _read(CONTRACT)
    mechanics = contract["acceptance"]["mechanics"]
    joined = " ".join(mechanics)
    assert "120 complete model-double fit identities" in joined
    assert "1,920 complete model-double outer prediction rows" in joined
    assert "eight exact LightGBM fits" in joined
    assert "6,304 finite probe predictions" in joined
    assert "all five 20%-margin resource gates pass" in joined
    assert "mechanics only" in contract["acceptance"]["scientific_boundary"]
    assert "later separately reviewed single-use" in contract["acceptance"]["pass"]
    assert "permanently close EXP-G3" in contract["acceptance"]["miss"]


def test_g3_contract_opens_no_runtime_execution_or_claim_capability() -> None:
    contract = _read(CONTRACT)
    accounting = contract["current_milestone_accounting"]
    assert accounting["contracts_created"] == 1
    assert all(value == 0 for key, value in accounting.items() if key != "contracts_created")

    authority = contract["current_authority"]
    assert authority["contract_and_static_tests"] is True
    assert all(value is False for key, value in authority.items() if key != "contract_and_static_tests")
    assert "Do not open an official input" in contract["next_gate"]
    assert "create an execution claim" in contract["next_gate"]


def test_g3_synthetic_contract_contains_no_private_submission_fields() -> None:
    text = CONTRACT.read_text(encoding="utf-8").lower()
    forbidden = ("submission_name", "leaderboard_score", "leaderboard_rank")
    assert all(value not in text for value in forbidden)

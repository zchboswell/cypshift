from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
BENCHMARK_ROOT = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT_PATH = BENCHMARK_ROOT / "global_v2_maplight_reproduction_contract.json"
CONTRACT_SHA256 = "7983e767dcc53d75c3a1816cf2a6528980c300b700bc339575cfb8a0faca344b"


def _load(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_maplight_contract_identity_and_current_authority() -> None:
    contract = _load()
    assert _sha256(CONTRACT_PATH) == CONTRACT_SHA256
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v2_maplight_reproduction_contract.v1"
    )
    assert contract["gate"] == "G2_2A_MAPLIGHT_REPRODUCTION_CONTRACT_FROZEN"
    assert contract["status"] == "contract_only_no_official_execution_authority"
    assert contract["base_commit"] == "df9ec9c4f418eb8677cb474d3ad4ec7e49395d3c"

    authority = contract["current_authority"]
    assert authority["contract_and_static_tests"]
    assert authority["synthetic_runner_implementation"]
    assert not any(
        value
        for name, value in authority.items()
        if name not in {"contract_and_static_tests", "synthetic_runner_implementation"}
    )


def test_maplight_contract_parent_and_current_source_receipts() -> None:
    contract = _load()
    for receipt in contract["parents"].values():
        path = BENCHMARK_ROOT / receipt["path"]
        assert path.is_file()
        assert _sha256(path) == receipt["sha256"]

    implementations = contract["implementation_receipts"]
    assert (
        _sha256(ROOT / "src/cypshift/openadmet_global_v2_metric.py")
        == (implementations["accepted_g2_1_metric_source_sha256"])
    )
    assert (
        _sha256(ROOT / "src/cypshift/openadmet_global_v2_firewall.py")
        == (implementations["accepted_g2_1_firewall_source_sha256"])
    )
    assert implementations["historical_r3c_runner_sha256"] == (
        "436c95a808733d7144604fdd6d733cc1edba6320072f201374a6d331afa3eb8d"
    )


def test_historical_r3c_is_aggregate_authentication_not_a_rerun_target() -> None:
    contract = _load()
    historical = contract["historical_r3c_reference"]
    assert historical["terminal_manifest_sha256"] == (
        "a2029e12231a22415900c55303ec5413b395aedc15d565ef7b4e650196b3277c"
    )
    assert historical["global_result_sha256"] == (
        "d9aff555db3c985ca834a11f5d1f198a9c8c5bafcaced6e7719a88bab09c2f94"
    )
    assert historical["population"] == {
        "molecules": 4905,
        "components": 4553,
        "endpoint_cells": 19620,
        "complete_targets": 6525,
    }
    assert historical["maplight_component_macro_mae"] == {
        "CYP1A2": 0.6573103822118366,
        "CYP2C9": 0.4746750811243161,
        "CYP2D6": 0.583529663910722,
        "CYP3A4": 0.5686966679930828,
        "macro": 0.5710529488099894,
    }
    assert "Never read or compare historical row-level" in historical["use"]

    resolution = contract["sealed_holdout_resolution"]
    assert "Do not rerun the full R3C population" in resolution["decision"]
    assert "execute official MapLight only on development" in resolution["decision"]
    assert "must never be required to equal" in resolution["comparison_boundary"]
    assert resolution["confirmatory_truth_reads_before_g2_8"] == 0


def test_fixed_maplight_recipe_and_runtime_are_exact() -> None:
    contract = _load()
    recipe = contract["fixed_maplight"]
    assert recipe["system_id"] == "TRACE-G0-MAPL-FIXED"
    assert recipe["feature_order"] == [
        "maplight_morgan_count:1024",
        "maplight_avalon_count:1024",
        "maplight_erg:315",
        "maplight_rdkit_descriptors:200",
    ]
    assert recipe["feature_columns"] == 2563
    assert recipe["constructor_arguments"] == {
        "loss_function": "MAE",
        "random_strength": 2,
        "random_seed": 1,
        "task_type": "CPU",
        "thread_count": 16,
        "verbose": 0,
        "allow_writing_files": False,
    }
    assert recipe["omitted_arguments"] == [
        "eval_set",
        "early_stopping_rounds",
        "use_best_model",
        "iterations",
        "nan_mode",
    ]
    assert recipe["resolved_parameter_sha256"] == (
        "c56235a54a883a9a4488f1c8779f9013dae777af0f99cd92c9da1c4f51e61757"
    )
    assert contract["runtime"]["maplight"] == {
        "platform": "Linux x86_64 CPU",
        "python": "3.10.13",
        "numpy": "1.25.2",
        "catboost": "1.2.1",
        "uv_lock_sha256": (
            "99e72821b69d9bb943a6e32adc7e0dec0e46c6d32df090241d4fb9296a4195d8"
        ),
    }


def test_development_partition_and_cross_fit_accounting_are_frozen() -> None:
    contract = _load()
    expected = contract["official_population"]["expected_label_free"]
    assert expected == {
        "all_molecules": 4905,
        "all_components": 4553,
        "development_molecules": 3908,
        "development_components": 3640,
        "confirmatory_molecules": 997,
        "confirmatory_components": 913,
    }
    assert (
        expected["development_molecules"] + expected["confirmatory_molecules"]
        == (expected["all_molecules"])
    )
    assert (
        expected["development_components"] + expected["confirmatory_components"]
        == (expected["all_components"])
    )

    cross_fit = contract["cross_fitting"]
    assert (
        cross_fit["repeats"],
        cross_fit["outer_folds"],
        cross_fit["inner_folds"],
    ) == (
        3,
        5,
        4,
    )
    assert cross_fit["outer_maplight_fits_per_replay"] == 4 * 3 * 5
    assert cross_fit["inner_maplight_fits_per_replay"] == 4 * 3 * 5 * 4
    assert cross_fit["total_maplight_fits_per_replay"] == 300
    assert cross_fit["expected_label_free_outer_prediction_rows_per_replay"] == (
        3908 * 4 * 3
    )
    assert cross_fit["expected_label_free_inner_prediction_rows_per_replay"] == (
        3908 * 4 * 3 * 4
    )
    assert contract["official_population"]["preflight_minima"] == {
        "development_finite_targets_per_endpoint": 750,
        "outer_validation_targets_per_endpoint_repeat_fold": 75,
        "inner_training_targets_per_endpoint_repeat_outer_inner": 400,
    }


def test_residual_uncertainty_and_output_schemas_are_cross_fitted() -> None:
    contract = _load()
    cross_fit = contract["cross_fitting"]
    assert "prediction minus central truth" in cross_fit["residual_rule"]
    uncertainty = cross_fit["uncertainty"]
    assert "absolute residuals" in uncertainty["method"]
    assert "No outer residual" in uncertainty["grouping"]
    assert "weight 1/n" in uncertainty["component_equal_weighting"]
    assert "at least 0.90" in uncertainty["weighted_order_statistic"]
    assert "Do not interpolate" in uncertainty["weighted_order_statistic"]
    assert "without pooling or repair" in uncertainty["failure"]

    schemas = contract["output_schemas"]
    assert schemas["development_outer_oof.csv"][:5] == [
        "molecule_id",
        "endpoint",
        "similarity_component_hash",
        "repeat",
        "outer_fold",
    ]
    assert "inner_fold" in schemas["development_inner_oof.csv"]
    assert "prediction_receipt" in schemas["development_residuals.csv"]
    assert "inner_residual_receipt" in schemas["development_uncertainty.csv"]
    assert contract["metric_boundary"]["tutorial_ma_st_rae_calls"] == 0
    assert contract["metric_boundary"]["official_metric_calls"] == 0
    assert "selects no model" in contract["metric_boundary"]["selection"]


def test_attempt_resource_and_future_execution_boundaries_are_bounded() -> None:
    contract = _load()
    attempts = contract["attempts_and_determinism"]
    assert attempts["g2_2b_synthetic_roots"] == 2
    assert attempts["g2_2c_official_development_replays"] == 2
    assert not attempts["retry"]
    assert not attempts["resume"]
    assert not attempts["overwrite"]
    assert contract["resource_ceiling"] == {
        "cpu_core_hours": 200,
        "gpu_hours": 0,
        "restricted_storage_gb": 80,
        "maximum_wall_hours": 12,
    }
    future = contract["future_g2_2c_boundary"]
    assert len(future["requires"]) == 3
    assert "confirmatory truth" in future["must_never_open"]
    assert contract["next_gate"].startswith(
        "Implement and adversarially accept G2-2B on synthetic data only."
    )

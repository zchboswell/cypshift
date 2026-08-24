from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
RECEIPT_PATH = (
    ROOT
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "global_v2_maplight_official_reproduction.json"
)
RECEIPT_SHA256 = "767750305a36eb7e9a850c221c67534534ddac85a6125683192266651f7a4482"


def _load() -> dict[str, Any]:
    value = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_official_reproduction_receipt_is_exact_and_terminal() -> None:
    receipt = _load()
    assert hashlib.sha256(RECEIPT_PATH.read_bytes()).hexdigest() == RECEIPT_SHA256
    assert receipt["status"] == "G2_2_MAPLIGHT_REPRODUCED"
    assert receipt["receipts"]["attempt_receipt_sha256"] == (
        "5f27085420107786143125a37536bf43d809879d11537e94719af59ce0f2b936"
    )
    assert receipt["receipts"]["consumed_claim_sha256"] == (
        "6d215b0587c9a4539223254d23f1215f8ef165dcbe13bdb803489e3270a71e43"
    )
    assert receipt["receipts"]["terminal_manifest_sha256"] == (
        "62c88f7d1213ead4fd297f1a44905e71638e704765f9abc206dd12d152bf77fe"
    )
    assert receipt["determinism"] == {
        "files_compared": 6,
        "overwrite": False,
        "relative_byte_maps_identical": True,
        "replays_completed": 2,
        "resume": False,
        "retry": False,
    }


def test_official_reproduction_receipt_preserves_scientific_firewall() -> None:
    receipt = _load()
    accounting = receipt["accounting"]
    for field in (
        "blinded_test_files_opened",
        "confirmatory_truth_values_opened",
        "external_records_acquired",
        "historical_r3c_row_level_artifacts_opened",
        "inner_truth_values_opened_by_model",
        "leaderboard_observations",
        "live_uploads",
        "official_metric_evaluations",
        "outer_truth_values_opened_by_model",
        "submissions_created",
        "tdi_files_opened",
        "tutorial_ma_st_rae_calls",
    ):
        assert accounting[field] == 0

    assert receipt["authority"] == {
        "confirmatory_truth_access": False,
        "development_feature_access": True,
        "development_model_fitting": True,
        "development_prediction_generation": True,
        "development_residual_or_diagnostic_computation": True,
        "development_target_access": True,
        "external_record_acquisition": False,
        "official_metric_evaluation": False,
        "submission_generation": False,
        "test_or_tdi_access": False,
    }


def test_official_reproduction_receipt_freezes_baseline_and_counts() -> None:
    receipt = _load()
    counts = receipt["counts_per_replay"]
    assert counts["molecules"] == 3908
    assert counts["finite_truth_rows"] == 5197
    assert counts["outer_maplight_fits"] == 60
    assert counts["inner_maplight_fits"] == 240
    assert counts["outer_predictions"] == 46896
    assert counts["inner_predictions"] == 187584
    assert counts["q90_contexts"] == 60
    assert counts["residual_rows"] == counts["uncertainty_rows"] == 15591

    metrics = receipt["development_component_macro_mae"]
    assert metrics["endpoint_macro_mean"] == 0.5837812652150708
    assert metrics["CYP1A2"]["mean"] == 0.667333406753392
    assert metrics["CYP2C9"]["mean"] == 0.4899744448552545
    assert metrics["CYP2D6"]["mean"] == 0.5985509824172084
    assert metrics["CYP3A4"]["mean"] == 0.5792662268344283
    repeat_means = receipt["repeat_component_macro_mae"]
    assert max(repeat_means.values()) - min(repeat_means.values()) < 0.0006


def test_tracked_receipt_contains_aggregates_not_private_rows() -> None:
    receipt = _load()
    encoded = json.dumps(receipt, sort_keys=True)
    for forbidden in (
        "molecule_id",
        "component_id",
        "raw_smiles",
        "standardized_smiles",
        "y_true",
        "y_pred",
    ):
        assert forbidden not in encoded

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
CONTRACT_PATH = (
    ROOT / "benchmarks" / "openadmet_cyp_2026" / "global_v2_experiment_contract.json"
)
AUDIT_REDACTION_PATH = (
    ROOT
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "global_v2_audit_privacy_redaction.json"
)
CONTRACT_SHA256 = "612b8cea20cba8fb5d209fdd2d92a42feb652477c358f92ed710449d091e5c0d"
AUDIT_REDACTION_SHA256 = (
    "8a7384050d6068fc63c5da1f842f0984145b1fd633fdc1aee0463884a7a23798"
)


def _load(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_global_v2_contract_identity_and_denied_execution_authority() -> None:
    contract = _load()
    assert _sha256(CONTRACT_PATH) == CONTRACT_SHA256
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v2_experiment_contract.v1"
    )
    assert contract["freeze_date"] == "2026-08-24"
    assert contract["gate"] == "G2_0_GLOBAL_V2_CONTRACT_FROZEN"
    assert contract["status"] == "contract_only_no_execution_authority"
    assert contract["base_commit"] == ("249be023a7b7b12c2e3fedae6c6368be7f254ccc")
    assert contract["governing_decisions"] == ["D-084", "D-085", "D-086"]

    assert contract["authority"] == {
        "public_source_refresh": True,
        "contract_and_hypothesis_registry": True,
        "confirmatory_partition_formula": True,
        "metric_specification": True,
        "target_access": False,
        "feature_generation": False,
        "model_fitting": False,
        "prediction_generation": False,
        "metric_evaluation": False,
        "external_record_acquisition": False,
        "blinded_test_access": False,
        "transductive_relationships": False,
        "tdi_access": False,
        "submission_generation": False,
        "leaderboard_observation_for_selection": False,
        "live_upload": False,
    }


def test_global_v2_parent_receipts_match_tracked_bytes() -> None:
    inputs = _load()["inputs"]
    for name in (
        "challenge_contract",
        "source_receipts",
        "validation_contract",
        "global_v1_contract",
        "global_v1_runner_overlay",
    ):
        receipt = inputs[name]
        path = ROOT / receipt["path"]
        assert path.is_file()
        assert _sha256(path) == receipt["sha256"]

    redaction = _load(AUDIT_REDACTION_PATH)
    original = inputs["strategy_audit"]
    public_copy = redaction["public_copy"]
    assert _sha256(AUDIT_REDACTION_PATH) == AUDIT_REDACTION_SHA256
    assert redaction["original_import_receipt"]["sha256"] == original["sha256"]
    assert public_copy["path"] == original["path"]
    assert _sha256(ROOT / public_copy["path"]) == public_copy["sha256"]
    assert redaction["privacy_boundary"]["scientific_meaning_changed"] is False

    accepted = inputs["accepted_artifacts"]
    assert accepted == {
        "r2b_manifest_sha256": (
            "08dcf61cded99fae046bff49b57b0c4a12082cd8714c779ac44a351bf1a0c8c8"
        ),
        "direct_observations_sha256": (
            "00b1ac95cc73dda2699f2f05bc33200d1119a197d7a92ae900cde78d722f00b7"
        ),
        "group_folds_sha256": (
            "91678d68b2f9ac3913f6b679dd284f82ba2a040d803de83655bf89906f31f774"
        ),
        "training_topology_sha256": (
            "710978431402dbb737244bf01a9f4d9e4e398181400627db680a4f12d06d3b8a"
        ),
        "r3a_feature_manifest_sha256": (
            "32a950959ceca0641b56518e2059069a275ced64cf399d095aa5bce522c8026b"
        ),
        "r3c_terminal_manifest_sha256": (
            "a2029e12231a22415900c55303ec5413b395aedc15d565ef7b4e650196b3277c"
        ),
        "r3c_global_result_sha256": (
            "d9aff555db3c985ca834a11f5d1f198a9c8c5bafcaced6e7719a88bab09c2f94"
        ),
    }


def test_public_refresh_freezes_changed_tutorial_without_claiming_backend_parity() -> (
    None
):
    refresh = _load()["public_source_refresh"]
    assert refresh["dataset"]["head_revision"] == (
        "85f8b358d0a2056a98b990dd75d3b3ec9247862b"
    )
    assert refresh["space"]["head_revision"] == (
        "13c5057b37d1e72b3f036dd0d59718b1823f8fdd"
    )
    tutorial = refresh["tutorial"]
    assert tutorial["r0_revision"] == ("9d4925eb4a0fb914256da1b27d110593bcbe3cf0")
    assert tutorial["head_revision"] == ("858ae63ce79934113bccdb7fc65467de5f7b1935")
    assert set(tutorial["selected_files"]) == {
        "README.md",
        "evaluation/config.py",
        "evaluation/custom_scoring_functions.py",
        "evaluation/evaluate_predictions.py",
        "evaluation/utils.py",
        "validation/activity_validation.py",
        "validation/tdi_validation.py",
    }
    assert (
        tutorial["selected_files"]["validation/activity_validation.py"]["sha256"]
        == "276a53d7f22ff973aaf567e64d977202995e91ba3cef2bbdc4de71c13bdebcb2"
    )
    assert "No upload-automation permission" in refresh["refresh_result"]
    assert "transductive permission" in refresh["refresh_result"]

    primary = _load()["metrics"]["primary"]
    assert primary["id"] == "TUTORIAL_MA_ST_RAE_858AE63_V1"
    assert primary["direction"] == "lower_is_better"
    assert primary["macro"] == (
        "Plain arithmetic mean of the four endpoint ST-RAE values."
    )
    assert (
        "live-backend byte and behavior parity remain unverified"
        in primary["name_boundary"]
    )
    assert "do not call" in primary["name_boundary"]


def test_confirmatory_partition_is_label_free_fixed_and_single_use() -> None:
    partition = _load()["confirmatory_partition"]
    assert partition["seed"] == 20260824
    assert partition["expected_label_free_counts"] == {
        "all_components": 4553,
        "all_molecules": 4905,
        "confirmatory_components": 913,
        "confirmatory_molecules": 997,
        "development_components": 3640,
        "development_molecules": 3908,
    }
    assert partition["maximum_confirmatory_scores"] == 1
    assert (
        "Target availability and magnitude cannot affect membership"
        in partition["label_independence"]
    )
    assert "Never rebalance, reseed" in partition["development_folds"]["rule"]
    assert "Do not move a component" in partition["minimum_failure"]

    def is_confirmatory(component_hash: str) -> bool:
        material = (
            "openadmet-global-v2-confirmatory-v1|20260824|" + component_hash
        ).encode()
        return int.from_bytes(hashlib.sha256(material).digest()[:8], "big") % 5 == 0

    witnesses = [
        hashlib.sha256(f"component-{index}".encode()).hexdigest() for index in range(20)
    ]
    first = [is_confirmatory(value) for value in witnesses]
    second = [is_confirmatory(value) for value in reversed(witnesses)]
    assert first == list(reversed(second))
    assert any(first)
    assert not all(first)


def test_g1_grid_and_nested_fit_budget_are_frozen() -> None:
    g1 = _load()["experiments"]["EXP-G1"]
    assert g1["model_seeds"] == [20260824, 20260825, 20260826]
    configurations = g1["configurations"]
    assert len(configurations) == 12
    assert [item["configuration_id"] for item in configurations] == [
        f"G1-C{index:02d}" for index in range(12)
    ]
    assert len({json.dumps(item, sort_keys=True) for item in configurations}) == 12
    for item in configurations:
        assert item["iterations"] > 0
        assert item["learning_rate"] > 0
        assert item["depth"] in {6, 8, 10}
        if item["bootstrap_type"] == "Bernoulli":
            assert item["subsample"] == 0.8
            assert "bagging_temperature" not in item
        else:
            assert item["bootstrap_type"] == "Bayesian"
            assert item["bagging_temperature"] == 1.0
            assert "subsample" not in item

    expected_inner_fits = 12 * 3 * 4 * (4 * 3 * 5)
    expected_outer_candidate_fits = 3 * (4 * 3 * 5)
    expected_baseline_fits = 4 * 3 * 5
    assert g1["maximum_model_fits"] == (
        expected_inner_fits + expected_outer_candidate_fits + expected_baseline_fits
    )
    assert "inner OOF" in g1["selection"]
    assert "Within each outer cell and endpoint" in g1["selection"]
    assert "endpoint tutorial ST-RAE" in g1["selection"]
    assert "one configuration per endpoint" in g1["confirmatory_recipe"]
    assert "before confirmatory truth opens" in g1["confirmatory_recipe"]
    assert g1["acceptance"] == {
        "minimum_relative_primary_improvement": 0.03,
        "minimum_absolute_component_mae_improvement": 0.015,
        "paired_component_mae_upper_95_below_zero": True,
        "maximum_endpoint_mae_degradation": 0.015,
        "minimum_favorable_outer_cells": 8,
        "total_outer_cells": 15,
    }


def test_experiment_ladder_has_predeclared_falsifiers_and_ablation_gates() -> None:
    experiments = _load()["experiments"]
    assert list(experiments) == ["EXP-G1", "EXP-G2", "EXP-M1", "EXP-X1", "EXP-T2"]
    for experiment in experiments.values():
        assert experiment["hypothesis"]
        assert experiment["targeted_failure"]
        assert experiment["simplest_falsifier"]
        assert experiment["acceptance"]
        assert experiment["resource_ceiling"]

    g2 = experiments["EXP-G2"]
    assert [expert["id"] for expert in g2["experts"]] == [
        "G2-E00",
        "G2-E01",
        "G2-E02",
        "G2-E03",
        "G2-E04",
    ]
    assert [stacker["id"] for stacker in g2["stackers"]] == ["G2-S00", "G2-S01"]
    assert "inner OOF" in g2["selection"]
    assert "For each endpoint" in g2["selection"]
    assert "endpoint tutorial ST-RAE" in g2["selection"]
    assert "at most four experts" in g2["selection"]
    assert "one constituent set and stacker per endpoint" in g2["confirmatory_recipe"]
    assert g2["acceptance"]["every_retained_expert_requires_positive_drop_one_ablation"]

    m1 = experiments["EXP-M1"]
    assert m1["shared_model"]["masked_endpoints"] == 4
    assert "not authorized initially" in m1["chemprop_boundary"]
    assert m1["acceptance"]["shared_model_must_beat_independent_control"]
    assert m1["acceptance"]["permuted_control_must_not_reproduce_gain"]

    x1 = experiments["EXP-X1"]
    assert len(x1["candidate_sources"]) == 3
    assert len(x1["child_contract_required_before_acquisition"]) == 8
    assert "Never use blinded-test relationships" in x1["fold_exclusion"]

    t2 = experiments["EXP-T2"]
    assert "positive improvement-versus-coverage" in t2["activation"]
    assert "maximum local weight 0.25" in t2["requirements"]
    assert "no R5D row-level loss input" in t2["requirements"]
    assert t2["acceptance"]["maximum_activity_cliff_mae_degradation"] == 0.01


def test_global_resource_and_submission_boundaries_stay_closed() -> None:
    contract = _load()
    ceilings = contract["resource_ceiling"]
    assert ceilings == {
        "total_cpu_core_hours": 15000,
        "total_gpu_hours": 400,
        "maximum_restricted_storage_gb": 300,
        "policy": (
            "Each child contract sets a no-larger ceiling. Exhaustive architecture "
            "search and post-outcome grid expansion are forbidden."
        ),
    }
    experiments = contract["experiments"].values()
    assert (
        sum(item["resource_ceiling"]["cpu_core_hours"] for item in experiments) <= 15000
    )
    assert sum(item["resource_ceiling"]["gpu_hours"] for item in experiments) <= 400
    assert (
        max(item["resource_ceiling"]["restricted_storage_gb"] for item in experiments)
        <= 300
    )

    forbidden = "\n".join(contract["forbidden"])
    for phrase in (
        "opening numeric targets",
        "leaderboard results",
        "rerunning R5D",
        "submission generation or upload",
        "research dependencies",
        "generic orchestration infrastructure",
    ):
        assert phrase in forbidden

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["dependencies"] == ["rdkit>=2026.3.4,<2027"]

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "maplight-fixed"
REJECTION = (
    ROOT
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "global_v2_g1_resource_feasibility_rejection.json"
)
REJECTION_SHA256 = "675858301f65920e0accbd493cc9211c5edb0a017ed70f4674ec8b5cf41a9be4"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))


def _module(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, RESEARCH / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


resource = _module(
    "global_v2_g1_resource_feasibility",
    "global_v2_g1_resource_feasibility.py",
)
driver = _module(
    "run_global_v2_g1_resource_feasibility",
    "run_global_v2_g1_resource_feasibility.py",
)


def _probe_row() -> dict[str, object]:
    return {
        "configuration_id": "G1-C00",
        "model_seed": 20260824,
        "resolved_parameter_sha256": "a" * 64,
        "prediction_float64_sha256": "b" * 64,
        "training_rows": 48,
        "prediction_rows": 8,
        "finite_predictions": True,
    }


def test_resource_source_binds_the_integrated_contract_and_probe_topology() -> None:
    contract = resource._static_contract()
    assert resource.base.sha256_path(resource.CONTRACT) == resource.CONTRACT_SHA256
    assert contract["single_optimization"]["optimization_id"] == (
        "FOLD_LOCAL_QUANTIZED_POOL_REUSE_V1"
    )
    assert len(resource.PROBE_IDENTITIES) == 14
    assert resource.PROBE_IDENTITIES[:12] == tuple(
        (configuration, 20260824) for configuration in resource.g1.CONFIGURATION_IDS
    )
    assert resource.PROBE_IDENTITIES[-2:] == (
        ("G1-C00", 20260825),
        ("G1-C00", 20260826),
    )


def test_cache_identity_binds_every_ordered_array_and_model_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(resource.wrapper, "_runtime_identity", lambda: {"runtime": "x"})
    training = np.arange(24, dtype=np.float32).reshape(6, 4)
    targets = np.arange(6, dtype=np.float64)
    prediction = np.arange(12, dtype=np.float32).reshape(3, 4)

    def receipt(
        train: np.ndarray,
        target: np.ndarray,
        predict: np.ndarray,
        manifest: str = "a" * 64,
    ) -> str:
        return resource.cache_identity(
            training=train,
            targets=target,
            prediction=predict,
            model_manifest_sha256=manifest,
        )

    original = receipt(training, targets, prediction)
    changed_training = training.copy()
    changed_training[0, 0] += 1
    changed_targets = targets.copy()
    changed_targets[0] += 1
    changed_prediction = prediction.copy()
    changed_prediction[0, 0] += 1
    assert (
        len(
            {
                original,
                receipt(changed_training, targets, prediction),
                receipt(training[::-1], targets[::-1], prediction),
                receipt(training, changed_targets, prediction),
                receipt(training, targets, changed_prediction),
                receipt(training, targets, prediction[::-1]),
                receipt(training, targets, prediction, "b" * 64),
            }
        )
        == 7
    )


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("configuration_id", "G1-C01"),
        ("model_seed", 20260825),
        ("resolved_parameter_sha256", "c" * 64),
        ("prediction_float64_sha256", "d" * 64),
        ("training_rows", 49),
        ("prediction_rows", 9),
        ("finite_predictions", False),
    ],
)
def test_exact_equivalence_rejects_every_identity_or_prediction_change(
    field: str, replacement: object
) -> None:
    reference = _probe_row()
    changed = dict(reference)
    changed[field] = replacement
    with pytest.raises(resource.G1ResourceFeasibilityError, match=field):
        resource._assert_equivalent(changed, reference)


def test_prediction_receipt_is_exact_float64_bytes() -> None:
    values = np.asarray([1.0, 2.0], dtype=np.float64)
    changed = values.copy()
    changed[0] = np.nextafter(changed[0], np.inf)
    assert resource._prediction_receipt(values) != resource._prediction_receipt(changed)
    assert resource._prediction_receipt(values) == resource.base.sha256_bytes(
        values.astype("<f8").tobytes()
    )


def test_optimized_mode_requires_complete_raw_reference_before_model_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(resource.wrapper, "_runtime_identity", lambda: {"runtime": "x"})
    with pytest.raises(
        resource.G1ResourceFeasibilityError,
        match="optimized mode requires a complete raw reference",
    ):
        resource.run_probe_mode(
            model_capability_root=tmp_path / "unopened-model-root",
            mode="fold_local_quantized_pool_reuse",
            output_root=tmp_path / "output",
            reference_path=None,
        )


def test_reference_requires_exact_raw_complete_schema(tmp_path: Path) -> None:
    reference = tmp_path / "reference.json"
    reference.write_text(
        json.dumps(
            {
                "schema_version": resource.PROBE_SCHEMA,
                "mode": "fold_local_quantized_pool_reuse",
                "status": "G2_3D_PROBE_MODE_COMPLETE",
                "probe_rows": [_probe_row()] * 14,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        resource.G1ResourceFeasibilityError, match="reference probe identity"
    ):
        resource._reference_index(reference)


def test_full_design_projection_is_exact_and_rejects_nonpositive_input() -> None:
    projection = driver.project_full_design(wall_seconds=14.0, cpu_seconds=28.0)
    assert projection == {
        "wall_hours": 8820.0 / 3600.0,
        "cpu_core_hours": 2.0 * 8820.0 / 3600.0,
    }
    with pytest.raises(driver.G1ResourceDriverError, match="nonpositive"):
        driver.project_full_design(wall_seconds=0.0, cpu_seconds=1.0)


def test_cross_mode_equivalence_uses_exact_probe_rows(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    value = {"probe_rows": [_probe_row()] * 14}
    first.write_bytes(resource.base.json_bytes(value))
    second.write_bytes(resource.base.json_bytes(value))
    driver._assert_all_receipts_equivalent([first, second])
    changed = dict(_probe_row())
    changed["prediction_float64_sha256"] = "f" * 64
    second.chmod(0o644)
    second.write_bytes(resource.base.json_bytes({"probe_rows": [changed] * 14}))
    with pytest.raises(driver.G1ResourceDriverError, match="cross-mode"):
        driver._assert_all_receipts_equivalent([first, second])


def test_fail_fast_receipt_is_finite_and_accounts_partial_fit(tmp_path: Path) -> None:
    receipt_root = tmp_path / "receipt"
    driver._publish_receipt(
        receipt_root=receipt_root,
        status="G2_3D_EXP_G1_RESOURCE_EQUIVALENCE_REJECTED",
        decision="reject_exp_g1_unconsumed",
        modes={},
        failure="exact prediction differs",
        work_tree_bytes=123,
        partial_fits=1,
        partial_predictions=8,
    )
    receipt = json.loads((receipt_root / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["optimized_acceptance"] == {
        "worst_projected_wall_hours": None,
        "maximum_projected_wall_hours": 96.0,
        "wall_pass": False,
        "worst_projected_cpu_core_hours": None,
        "maximum_projected_cpu_core_hours": 960.0,
        "cpu_pass": False,
        "required_margin_fraction": 0.2,
        "worst_root_rule": True,
    }
    assert receipt["completed_real_catboost_fits"] == 1
    assert receipt["accounting"]["synthetic_predictions_generated"] == 8
    assert receipt["accounting"]["claim_consumptions"] == 0
    assert "Infinity" not in (receipt_root / "receipt.json").read_text(encoding="utf-8")


def test_tracked_resource_rejection_has_exact_identity_and_sources() -> None:
    receipt = json.loads(REJECTION.read_text(encoding="utf-8"))
    assert resource.base.sha256_path(REJECTION) == REJECTION_SHA256
    assert receipt["schema_version"] == driver.RECEIPT_SCHEMA
    assert receipt["status"] == "G2_3D_EXP_G1_RESOURCE_INFEASIBLE"
    assert receipt["decision"] == "reject_exp_g1_unconsumed"
    assert receipt["contract_sha256"] == resource.CONTRACT_SHA256
    assert receipt["implementation_receipts"] == {
        "accepted_synthetic_driver_source_sha256": resource.base.sha256_path(
            driver.synthetic.SCRIPT
        ),
        "accepted_wrapper_source_sha256": resource.base.sha256_path(
            resource.wrapper.SCRIPT
        ),
        "compiler_source_sha256": resource.base.sha256_path(driver.compiler.SCRIPT),
        "optimized_predictor_source_sha256": resource.base.sha256_path(resource.SCRIPT),
        "research_lock_sha256": resource.base.sha256_path(resource.g1.LOCK),
        "resource_driver_source_sha256": resource.base.sha256_path(driver.SCRIPT),
    }


def test_tracked_resource_rejection_proves_exactness_and_failed_both_ceilings() -> None:
    receipt = json.loads(REJECTION.read_text(encoding="utf-8"))
    assert receipt["exact_prediction_equivalence"] is True
    assert receipt["prediction_tolerance"] == 0.0
    assert receipt["completed_real_catboost_fits"] == 56
    assert receipt["maximum_real_catboost_fits"] == 56
    assert receipt["completed_modes"] == [
        "root_a_optimized",
        "root_a_reference",
        "root_b_optimized",
        "root_b_reference",
    ]
    optimized = receipt["optimized_acceptance"]
    assert optimized["worst_root_rule"] is True
    assert optimized["required_margin_fraction"] == 0.2
    assert optimized["worst_projected_wall_hours"] == pytest.approx(125.49688939812499)
    assert optimized["maximum_projected_wall_hours"] == 96.0
    assert optimized["wall_pass"] is False
    assert optimized["worst_projected_cpu_core_hours"] == pytest.approx(
        1680.5188842749994
    )
    assert optimized["maximum_projected_cpu_core_hours"] == 960.0
    assert optimized["cpu_pass"] is False


def test_tracked_mode_projections_recompute_and_forbidden_accounting_is_zero() -> None:
    receipt = json.loads(REJECTION.read_text(encoding="utf-8"))
    for telemetry in receipt["mode_telemetry"].values():
        assert telemetry["projection"] == pytest.approx(
            driver.project_full_design(
                wall_seconds=telemetry["wall_seconds"],
                cpu_seconds=telemetry["cpu_seconds"],
            )
        )
        assert telemetry["peak_rss_kb"] <= 1_500_000
    accounting = receipt["accounting"]
    assert accounting["synthetic_catboost_fits"] == 56
    assert accounting["synthetic_predictions_generated"] == 3584
    assert accounting["synthetic_source_rows_opened"] == 800
    assert all(
        accounting[name] == 0
        for name in (
            "claim_consumptions",
            "official_target_values_opened",
            "official_features_opened",
            "official_model_fits",
            "official_predictions_generated",
            "development_metric_evaluations",
            "confirmatory_truth_values_opened",
            "historical_r3c_row_level_artifacts_opened",
            "blinded_test_files_opened",
            "tdi_files_opened",
            "external_records_acquired",
            "submissions_created",
            "official_metric_evaluations",
            "leaderboard_observations",
            "live_uploads",
        )
    )
    assert not any(receipt["authority"].values())
    assert receipt["failure"] is None

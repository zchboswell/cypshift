#!/usr/bin/env python3
"""Execute the one-shot paired synthetic EXP-G1 resource falsifier."""

from __future__ import annotations

import argparse
import resource as posix_resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Final, cast

import global_v2_g1_execution_compiler as compiler
import global_v2_g1_resource_feasibility as feasibility
import global_v2_maplight_runner as base
import run_global_v2_g1_execution_synthetic as synthetic

SCRIPT: Final = Path(__file__).resolve()
RECEIPT_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_g1_resource_feasibility_receipt.v1"
)
FIT_PROJECTION_FACTOR: Final = 8820.0 / 14.0
MAXIMUM_PROJECTED_WALL_HOURS: Final = 96.0
MAXIMUM_PROJECTED_CPU_CORE_HOURS: Final = 960.0
MAXIMUM_PROBE_WALL_SECONDS: Final = 3.0 * 60.0 * 60.0


class G1ResourceDriverError(RuntimeError):
    """Raised when the paired resource falsifier fails closed."""

    def __init__(
        self,
        message: str,
        *,
        completed_fits: int = 0,
        prediction_values: int = 0,
    ) -> None:
        super().__init__(message)
        self.completed_fits = completed_fits
        self.prediction_values = prediction_values


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise G1ResourceDriverError(message)


def project_full_design(*, wall_seconds: float, cpu_seconds: float) -> dict[str, float]:
    """Linearly project one complete 14-fit mode to the frozen 8,820 fits."""

    _require(
        wall_seconds > 0.0 and cpu_seconds > 0.0,
        "resource measurement is nonpositive",
    )
    return {
        "wall_hours": wall_seconds * FIT_PROJECTION_FACTOR / 3600.0,
        "cpu_core_hours": cpu_seconds * FIT_PROJECTION_FACTOR / 3600.0,
    }


def _children_usage() -> tuple[float, int]:
    usage = posix_resource.getrusage(posix_resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime, int(usage.ru_maxrss)


def _run_mode(
    *,
    mode: str,
    model_root: Path,
    output_root: Path,
    reference_path: Path | None,
) -> dict[str, object]:
    command = [
        sys.executable,
        str(feasibility.SCRIPT),
        "--model-capability-root",
        str(model_root),
        "--mode",
        mode,
        "--output-root",
        str(output_root),
    ]
    if reference_path is not None:
        command.extend(("--reference", str(reference_path)))
    cpu_before, _rss_before = _children_usage()
    started = time.monotonic_ns()
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=MAXIMUM_PROBE_WALL_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise G1ResourceDriverError(f"probe mode timed out: {mode}") from error
    wall_seconds = (time.monotonic_ns() - started) / 1_000_000_000.0
    cpu_after, peak_rss_kb = _children_usage()
    cpu_seconds = cpu_after - cpu_before
    if completed.returncode != 0:
        failure_path = output_root / "failure.json"
        failed_fits = 0
        failed_predictions = 0
        receipt_diagnostic: str | None = None
        if failure_path.is_file() and not failure_path.is_symlink():
            failure_receipt, _raw = base._load_json(failure_path)
            failed_fits = int(failure_receipt["completed_real_catboost_fits"])
            failed_predictions = int(failure_receipt["synthetic_predictions_generated"])
            receipt_diagnostic = str(failure_receipt["failure"])
        diagnostic = (completed.stderr or completed.stdout).strip().splitlines()
        tail = receipt_diagnostic or (
            diagnostic[-1] if diagnostic else "no child diagnostic"
        )
        raise G1ResourceDriverError(
            f"probe mode failed: {mode}: {tail[:500]}",
            completed_fits=failed_fits,
            prediction_values=failed_predictions,
        )
    _require(not completed.stdout.strip(), "probe child stdout differs")
    _require(not completed.stderr.strip(), "probe child stderr differs")
    probe_path = output_root / "probe.json"
    probe, _raw = base._load_json(probe_path)
    _require(
        probe.get("status") == "G2_3D_PROBE_MODE_COMPLETE"
        and probe.get("mode") == mode
        and probe.get("counts", {}).get("real_catboost_fits") == 14,
        "completed probe receipt differs",
    )
    return {
        "mode": mode,
        "probe_sha256": base.sha256_path(probe_path),
        "wall_seconds": wall_seconds,
        "cpu_seconds": cpu_seconds,
        "peak_rss_kb": peak_rss_kb,
        "projection": project_full_design(
            wall_seconds=wall_seconds, cpu_seconds=cpu_seconds
        ),
    }


def _compile_root(*, root: Path, reverse: bool) -> Path:
    source, features, folds = synthetic.publish_source(
        root=root / "source", reverse=reverse
    )
    baseline = synthetic.publish_baseline(
        root=root / "baseline", features=features, folds=folds
    )
    model, _selector, _scorer, preflight = compiler.compile_capabilities(
        source_root=source,
        baseline_terminal_root=baseline,
        output_root=root / "capabilities",
        expected_compiler_sha256=base.sha256_path(compiler.SCRIPT),
    )
    _require(preflight["status"] == "G2_3C_PREFLIGHT_PASS", "preflight differs")
    return model


def _probe_rows(path: Path) -> list[dict[str, Any]]:
    value, _raw = base._load_json(path)
    rows = value.get("probe_rows")
    _require(isinstance(rows, list) and len(rows) == 14, "probe rows differ")
    return cast(list[dict[str, Any]], rows)


def _assert_all_receipts_equivalent(paths: list[Path]) -> None:
    reference = _probe_rows(paths[0])
    for path in paths[1:]:
        _require(_probe_rows(path) == reference, "cross-mode probe receipts differ")


def _tree_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _accounting(*, fits: int, predictions: int) -> dict[str, int]:
    return {
        "synthetic_source_rows_opened": 2 * synthetic.MOLECULES,
        "synthetic_catboost_fits": fits,
        "synthetic_predictions_generated": predictions,
        "official_target_values_opened": 0,
        "official_features_opened": 0,
        "official_model_fits": 0,
        "official_predictions_generated": 0,
        "development_metric_evaluations": 0,
        "confirmatory_truth_values_opened": 0,
        "historical_r3c_row_level_artifacts_opened": 0,
        "blinded_test_files_opened": 0,
        "tdi_files_opened": 0,
        "external_records_acquired": 0,
        "submissions_created": 0,
        "official_metric_evaluations": 0,
        "leaderboard_observations": 0,
        "live_uploads": 0,
        "claim_consumptions": 0,
    }


def _publish_receipt(
    *,
    receipt_root: Path,
    status: str,
    decision: str,
    modes: dict[str, dict[str, object]],
    failure: str | None,
    work_tree_bytes: int,
    partial_fits: int,
    partial_predictions: int,
) -> Path:
    optimized = [value for key, value in modes.items() if key.endswith("optimized")]
    reference = [value for key, value in modes.items() if key.endswith("reference")]
    worst_optimized_wall = (
        max(
            cast(dict[str, float], value["projection"])["wall_hours"]
            for value in optimized
        )
        if optimized
        else None
    )
    worst_optimized_cpu = (
        max(
            cast(dict[str, float], value["projection"])["cpu_core_hours"]
            for value in optimized
        )
        if optimized
        else None
    )
    fits = len(modes) * 14 + partial_fits
    predictions = partial_predictions
    for value in modes.values():
        probe_path = cast(Path, value["probe_path"])
        probe, _raw = base._load_json(probe_path)
        predictions += int(probe["counts"]["prediction_values"])
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "status": status,
        "decision": decision,
        "contract_sha256": feasibility.CONTRACT_SHA256,
        "optimization_id": feasibility.OPTIMIZATION_ID,
        "implementation_receipts": {
            "optimized_predictor_source_sha256": base.sha256_path(feasibility.SCRIPT),
            "resource_driver_source_sha256": base.sha256_path(SCRIPT),
            "compiler_source_sha256": base.sha256_path(compiler.SCRIPT),
            "accepted_wrapper_source_sha256": base.sha256_path(wrapper_path()),
            "accepted_synthetic_driver_source_sha256": base.sha256_path(
                synthetic.SCRIPT
            ),
            "research_lock_sha256": base.sha256_path(feasibility.g1.LOCK),
        },
        "roots": 2,
        "second_source_physical_order_reversed": True,
        "mode_order": {
            "root_a": ["reference", "optimized"],
            "root_b": ["optimized", "reference"],
        },
        "completed_modes": sorted(modes),
        "maximum_real_catboost_fits": 56,
        "completed_real_catboost_fits": fits,
        "exact_prediction_equivalence": status
        != "G2_3D_EXP_G1_RESOURCE_EQUIVALENCE_REJECTED",
        "prediction_tolerance": 0.0,
        "mode_telemetry": {
            key: {name: item for name, item in value.items() if name != "probe_path"}
            for key, value in sorted(modes.items())
        },
        "reference_context": {
            "worst_projected_wall_hours": max(
                (
                    cast(dict[str, float], value["projection"])["wall_hours"]
                    for value in reference
                ),
                default=None,
            ),
            "worst_projected_cpu_core_hours": max(
                (
                    cast(dict[str, float], value["projection"])["cpu_core_hours"]
                    for value in reference
                ),
                default=None,
            ),
        },
        "optimized_acceptance": {
            "worst_projected_wall_hours": worst_optimized_wall,
            "maximum_projected_wall_hours": MAXIMUM_PROJECTED_WALL_HOURS,
            "wall_pass": worst_optimized_wall is not None
            and worst_optimized_wall <= MAXIMUM_PROJECTED_WALL_HOURS,
            "worst_projected_cpu_core_hours": worst_optimized_cpu,
            "maximum_projected_cpu_core_hours": MAXIMUM_PROJECTED_CPU_CORE_HOURS,
            "cpu_pass": worst_optimized_cpu is not None
            and worst_optimized_cpu <= MAXIMUM_PROJECTED_CPU_CORE_HOURS,
            "required_margin_fraction": 0.2,
            "worst_root_rule": True,
        },
        "restricted_work_tree_bytes": work_tree_bytes,
        "failure": failure,
        "accounting": _accounting(fits=fits, predictions=predictions),
        "authority": dict(feasibility.g1.DENIED_AUTHORITY),
        "scientific_interpretation": (
            "Synthetic implementation-equivalence and resource evidence only; no "
            "diagnostic may rank a model."
        ),
    }
    return cast(
        Path,
        base.publish_files(receipt_root, {"receipt.json": base.json_bytes(receipt)}),
    )


def wrapper_path() -> Path:
    """Return the accepted wrapper path without importing a second module name."""

    return feasibility.wrapper.SCRIPT


def run_falsifier(*, work_root: Path, receipt_root: Path) -> Path:
    """Execute the paired roots once and publish one accepted or rejected receipt."""

    feasibility._static_contract()
    _require(
        not work_root.exists()
        and not work_root.is_symlink()
        and not receipt_root.exists()
        and not receipt_root.is_symlink(),
        "resource falsifier root exists",
    )
    work_root.mkdir(parents=True)
    modes: dict[str, dict[str, object]] = {}
    failure: str | None = None
    status = "G2_3D_EXP_G1_RESOURCE_EQUIVALENCE_REJECTED"
    decision = "reject_exp_g1_unconsumed"
    work_tree_bytes = 0
    partial_fits = 0
    partial_predictions = 0
    try:
        model_a = _compile_root(root=work_root / "root-a", reverse=False)
        model_b = _compile_root(root=work_root / "root-b", reverse=True)
        mode_specs = (
            ("root_a_reference", "accepted_raw_array_reference", model_a, None),
            (
                "root_a_optimized",
                "fold_local_quantized_pool_reuse",
                model_a,
                work_root / "root-a-reference" / "probe.json",
            ),
            (
                "root_b_optimized",
                "fold_local_quantized_pool_reuse",
                model_b,
                work_root / "root-a-reference" / "probe.json",
            ),
            (
                "root_b_reference",
                "accepted_raw_array_reference",
                model_b,
                work_root / "root-a-reference" / "probe.json",
            ),
        )
        output_names = {
            "root_a_reference": "root-a-reference",
            "root_a_optimized": "root-a-optimized",
            "root_b_optimized": "root-b-optimized",
            "root_b_reference": "root-b-reference",
        }
        for key, mode, model, reference in mode_specs:
            output = work_root / output_names[key]
            telemetry = _run_mode(
                mode=mode,
                model_root=model,
                output_root=output,
                reference_path=reference,
            )
            telemetry["probe_path"] = output / "probe.json"
            modes[key] = telemetry
        _assert_all_receipts_equivalent(
            [cast(Path, value["probe_path"]) for value in modes.values()]
        )
        worst_wall = max(
            cast(dict[str, float], modes[key]["projection"])["wall_hours"]
            for key in ("root_a_optimized", "root_b_optimized")
        )
        worst_cpu = max(
            cast(dict[str, float], modes[key]["projection"])["cpu_core_hours"]
            for key in ("root_a_optimized", "root_b_optimized")
        )
        if (
            worst_wall <= MAXIMUM_PROJECTED_WALL_HOURS
            and worst_cpu <= MAXIMUM_PROJECTED_CPU_CORE_HOURS
        ):
            status = "G2_3D_EXP_G1_RESOURCE_FEASIBLE"
            decision = "permit_review_of_exact_optimized_bytes_before_claim"
        else:
            status = "G2_3D_EXP_G1_RESOURCE_INFEASIBLE"
        work_tree_bytes = _tree_bytes(work_root)
    except BaseException as error:
        failure = f"{type(error).__name__}: {error}"
        if isinstance(error, G1ResourceDriverError):
            partial_fits = error.completed_fits
            partial_predictions = error.prediction_values
        work_tree_bytes = _tree_bytes(work_root)
    try:
        return _publish_receipt(
            receipt_root=receipt_root,
            status=status,
            decision=decision,
            modes=modes,
            failure=failure,
            work_tree_bytes=work_tree_bytes,
            partial_fits=partial_fits,
            partial_predictions=partial_predictions,
        )
    finally:
        base._cleanup(work_root)
        _require(not work_root.exists(), "resource work root cleanup differs")


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--receipt-root", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_falsifier(work_root=args.work_root, receipt_root=args.receipt_root)
    result, _raw = base._load_json(receipt / "receipt.json")
    return 0 if result["status"] == "G2_3D_EXP_G1_RESOURCE_FEASIBLE" else 2


if __name__ == "__main__":
    raise SystemExit(_main())

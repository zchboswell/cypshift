from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "benchmarks" / "PHASE_0_5_REPORT.md"
RECEIPT = ROOT / "benchmarks" / "receipts" / "phase_0_5_report.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _score_row(
    rows: list[dict[str, Any]], task: str, population: str
) -> dict[str, Any]:
    matches = [
        row
        for row in rows
        if row["task"] == task and row["population"] == population
    ]
    assert len(matches) == 1
    return matches[0]


def test_report_is_bound_to_tracked_aggregate_evidence() -> None:
    receipt = _load_json(RECEIPT)

    assert receipt["schema_version"] == "cypshift.phase_0_5_report_receipt.v2"
    assert receipt["report"]["path"] == "benchmarks/PHASE_0_5_REPORT.md"
    assert receipt["report"]["sha256"] == _sha256(REPORT)

    for tracked in receipt["tracked_inputs"].values():
        path = ROOT / tracked["path"]
        assert path.is_file()
        assert tracked["sha256"] == _sha256(path)

    assert receipt["evidence_boundaries"] == {
        "heldout_evaluations_added": 0,
        "heldout_labels_parsed": 0,
        "model_fits": 0,
        "raw_rows_tracked": 0,
        "report_figures": 0,
        "score_changes": 0,
    }

    forbidden_row_keys = {
        "molecule_id",
        "prediction",
        "raw_structure",
        "standardized_structure",
        "target",
    }
    serialized = json.dumps(receipt["report_inputs"], sort_keys=True)
    for key in forbidden_row_keys:
        assert f'"{key}"' not in serialized


def test_report_tables_match_machine_readable_receipts() -> None:
    receipt = _load_json(RECEIPT)
    report = REPORT.read_text(encoding="utf-8")
    inputs = receipt["report_inputs"]

    for track in inputs["assay_tracks"]:
        row = (
            f'| {track["track"]} | {track["endpoint"]} | '
            f'{track["primary_metric"]} | {track["assay_warning"]} |'
        )
        assert row in report

    scorecard = inputs["scorecard"]
    assert len(scorecard) == 7
    assert {
        (row["task"], row["population"]) for row in scorecard
    } == {
        ("cyp3a4_active_preincubation_pIC50", "outer_validation"),
        ("cyp2c9_veith", "official"),
        ("cyp2c9_veith", "strict"),
        ("cyp2d6_veith", "official"),
        ("cyp2d6_veith", "strict"),
        ("cyp3a4_veith", "official"),
        ("cyp3a4_veith", "strict"),
    }

    octant = _score_row(
        scorecard, "cyp3a4_active_preincubation_pIC50", "outer_validation"
    )
    assert (
        f'| Octant CYP3A4 outer | {octant["rows"]:,} | MAE | '
        f'{octant["primary_value"]:.4f} | not available | not comparable |'
    ) in report
    assert (
        f'median absolute error {octant["median_absolute_error"]:.4f}, '
        f'RMSE {octant["rmse"]:.4f}, Spearman\n'
        f'correlation {octant["spearman"]:.4f}, interval-aware MAE '
        f'{octant["interval_aware_mae"]:.4f}, and potent-subset MAE '
        f'{octant["potent_mae"]:.4f} on\n{octant["potent_count"]} potent compounds'
    ) in report

    display = {
        "cyp2c9_veith": "CYP2C9",
        "cyp2d6_veith": "CYP2D6",
        "cyp3a4_veith": "CYP3A4",
    }
    for task, name in display.items():
        official = _score_row(scorecard, task, "official")
        strict = _score_row(scorecard, task, "strict")
        assert (
            f'| TDC {name} official | {official["rows"]:,} | AUPRC | '
            f'{official["primary_value"]:.4f} | '
            f'{official["chemprop_rdkit"]:.4f} | '
            f'{official["delta_vs_chemprop_rdkit"]:.4f} |'
        ) in report
        assert (
            f'| {name} | {official["primary_value"]:.6f} | '
            f'{strict["primary_value"]:.6f} | '
            f'{strict["overlap_rows_removed"]} |'
        ) in report
        assert (
            f'| {name} official | {official["auroc"]:.4f} | '
            f'{official["mcc"]:.4f} | {official["brier"]:.4f} | '
            f'{official["ece_10_equal_width"]:.4f} |'
        ) in report

    for row in inputs["component_disposition"]:
        assert (
            f'| {row["component"]} | {row["outcome"]} | '
            f'{row["disposition"]} |'
        ) in report


def test_report_links_and_negative_results_match_tracked_receipts() -> None:
    report = REPORT.read_text(encoding="utf-8")
    series = _load_json(
        ROOT / "benchmarks" / "receipts" / "series_residual_v1_rejection.json"
    )
    chemeleon = _load_json(
        ROOT / "benchmarks" / "receipts" / "chemeleon_attempt_v1_failure.json"
    )

    task_names = {
        "cyp3a4_active_preincubation_pIC50": "Octant CYP3A4 MAE",
        "cyp2c9_veith": "TDC CYP2C9 AUPRC",
        "cyp2d6_veith": "TDC CYP2D6 AUPRC",
        "cyp3a4_veith": "TDC CYP3A4 AUPRC",
    }
    for task in series["tasks"]:
        assert (
            f'| {task_names[task["task"]]} | {task["full_gain"]:.6f} | '
            f'{task["supported_gain"]:.6f} | '
            f'[{task["supported_lower_95"]:.6f}, '
            f'{task["supported_upper_95"]:.6f}] | '
            f'{task["positive_folds"]}/4 |'
        ) in report

    overlap = chemeleon["overlap"]["task_counts"]
    assert (
        f'Exact benchmark-structure overlaps were {overlap["cyp2c9_veith"]} '
        f'CYP2C9, {overlap["cyp2d6_veith"]} CYP2D6, '
        f'{overlap["cyp3a4_veith"]} TDC CYP3A4, and\n'
        f'{overlap["cyp3a4_active_preincubation_pIC50"]} Octant rows.'
    ) in report
    assert chemeleon["failure"]["exception_type"] == "ImportError"
    assert chemeleon["failure"]["exception_message"] == (
        "cannot import name 'DocumentModifiedShape' from 'botocore.docs.utils'"
    )
    assert "`DocumentModifiedShape`" in report


def test_report_data_and_reproduction_counts_match_receipt() -> None:
    receipt = _load_json(RECEIPT)
    report = REPORT.read_text(encoding="utf-8")
    inputs = receipt["report_inputs"]
    octant = inputs["data_cards"]["octant"]
    tdc = inputs["data_cards"]["tdc"]
    random = inputs["validation"]["random_optimism"]
    reproduction = inputs["reproduction"]

    assert (
        f'{octant["molecule_rows"]:,} molecule rows, '
        f'{octant["numeric_measurements"]:,} numeric pIC50 measurements,\n'
        f'  and {octant["missing_measurements"]} explicit missing-pIC50 omissions'
    ) in report
    assert (
        f'{tdc["accepted_rows"]:,} accepted rows across the three required tasks'
    ) in report
    assert (
        f'{tdc["train_val_rows"]:,} `train_val` rows and '
        f'{tdc["public_test_rows"]:,} public-test rows'
    ) in report
    assert (
        f'Octant MAE optimism was {random["octant_mae_min"]:.4f} to '
        f'{random["octant_mae_max"]:.4f}. TDC AUPRC optimism was '
        f'{random["tdc_auprc_min"]:.4f}\n'
        f'to {random["tdc_auprc_max"]:.4f}.'
    ) in report
    assert (
        f'reproduced {reproduction["empty_root_files"]} of '
        f'{reproduction["empty_root_files"]} files'
    ) in report
    assert reproduction["empty_root_aggregate_sha256"][:8] in report
    assert reproduction["validation_aggregate_sha256"][:8] in report

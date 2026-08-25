from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
RECEIPT_PATH = BENCHMARK / "global_v2_x1_prefreeze_preview_rejection.json"
RECEIPT_SHA256 = "6f0f063c09174ed10b2fa6c93d851efd66f4d7ff68602ff7a7ea8608876a5efc"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_x1_prefreeze_rejection_has_exact_identity_and_parents() -> None:
    receipt = _load(RECEIPT_PATH)
    assert _sha256(RECEIPT_PATH) == RECEIPT_SHA256
    assert receipt["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v2_x1_prefreeze_preview_rejection.v1"
    )
    assert receipt["gate"] == "G2_5_PREFREEZE_SOURCE_PREVIEW_REJECTED"
    assert receipt["status"] == "rejected_non_scientific_boundary_incident"
    assert receipt["base_commit"] == "a3e272d5c2a4ceda483cb5d20bafdae898c8c83d"
    for parent in receipt["parents"].values():
        path = BENCHMARK / parent["path"]
        assert path.is_file()
        assert _sha256(path) == parent["sha256"]


def test_x1_prefreeze_rejection_fails_positive_preview_closed() -> None:
    receipt = _load(RECEIPT_PATH)
    incident = receipt["incident"]
    decision = receipt["boundary_decision"]
    assert incident["minimum_external_record_rows_exposed"] == 45
    assert incident["exact_external_record_rows_exposed"] is None
    assert incident["public_record_values_retained_here"] == 0
    assert decision["required_precontract_external_records_opened"] == 0
    assert decision["observed_positive_external_record_exposure"]
    assert not decision["preflight_pass"]
    assert "cannot become" in decision["decision"]
    assert "no model-quality" in decision["scientific_scope"]


def test_x1_prefreeze_rejection_contains_no_external_row_value() -> None:
    text = RECEIPT_PATH.read_text(encoding="utf-8")
    assert "OCNT-" not in text
    containment = _load(RECEIPT_PATH)["containment"]
    assert containment["external_dataset_files_downloaded"] == 0
    assert containment["external_dataset_bytes_written_locally"] == 0
    assert containment["external_record_values_copied_to_repo_or_artifact"] == 0
    assert containment["external_record_values_used_for_decision_or_modeling"] == 0
    assert not containment["local_cleanup_required"]
    assert "Do not reopen" in containment["rule"]


def test_x1_prefreeze_rejection_opens_no_scientific_authority() -> None:
    receipt = _load(RECEIPT_PATH)
    accounting = receipt["current_milestone_accounting"]
    assert accounting["external_record_preview_rendered"]
    assert accounting["minimum_external_records_opened"] == 45
    assert accounting["external_files_downloaded"] == 0
    assert accounting["external_records_used_for_science"] == 0
    assert all(
        value == 0
        for name, value in accounting.items()
        if name not in {"external_record_preview_rendered", "minimum_external_records_opened"}
    )
    authority = receipt["current_authority"]
    assert authority["incident_receipt_and_static_tests"]
    assert not any(
        value
        for name, value in authority.items()
        if name != "incident_receipt_and_static_tests"
    )
    assert "separate metadata-only" in receipt["next_gate"]
    assert "zero additional external records" in receipt["next_gate"]
    assert "open zero official input" in receipt["next_gate"]

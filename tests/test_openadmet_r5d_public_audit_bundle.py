from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from cypshift.openadmet_oracle_terminal import validate_terminal_payloads

ROOT = (
    Path(__file__).parents[1]
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "r5d_training_validation_audit"
)
TERMINAL = ROOT / "terminal"
ROOT_FILES = {
    "README.md",
    "SHA256SUMS",
    "attempt_claim.json",
    "official_attempt_receipt.json",
    "terminal",
}
TERMINAL_FILES = {
    "manifest.json",
    "oracle_ablation_scorecard.csv",
    "oracle_bootstrap_summary.csv",
    "oracle_cell_metrics.csv",
    "oracle_influence_checks.csv",
    "oracle_inner_selection.csv",
    "oracle_result.json",
    "oracle_scored_rows.csv",
}
EXPECTED_PROCESS_COUNTS = {
    "accounting": 1,
    "cleanup": 1,
    "episodes": 75,
    "freezer": 1,
    "g0": 3366,
    "inner": 1,
    "migrate": 75,
    "outer": 1,
    "pair-inner": 960,
    "pair-outer": 120,
    "pair-outer-shared": 15,
    "project": 1,
    "source": 1,
    "support": 1,
    "view": 3366,
}
FORBIDDEN_COUNTERS = {
    "blinded_test_files_opened",
    "inferred_anchor_candidate_pools",
    "official_metric_calls",
    "submissions_created",
    "tdi_files_opened",
    "transductive_relationships",
}
FORBIDDEN_RAW_COLUMNS = {
    "prediction",
    "predicted_value",
    "raw_prediction",
    "smiles",
    "target",
    "target_value",
    "true_value",
    "truth",
}


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_public_training_validation_bundle_is_exact_and_self_validating() -> None:
    assert {path.name for path in ROOT.iterdir()} == ROOT_FILES
    assert {path.name for path in TERMINAL.iterdir()} == TERMINAL_FILES
    claim = _object(ROOT / "attempt_claim.json")
    receipt = _object(ROOT / "official_attempt_receipt.json")
    manifest = _object(TERMINAL / "manifest.json")

    assert claim["schema_version"] == (
        "cypshift.openadmet_cyp_2026.r5d_official_attempt_claim.v1"
    )
    assert receipt["schema_version"] == (
        "cypshift.openadmet_cyp_2026.r5d_official_attempt_receipt.v1"
    )
    assert receipt["claim_sha256"] == _sha256(ROOT / "attempt_claim.json")
    assert receipt["status"] == manifest["status"] == "R5_ORACLE_NO_SIGNAL"
    assert receipt["source_revision"] == ("85f8b358d0a2056a98b990dd75d3b3ec9247862b")

    for name, digest in receipt["terminal_receipts"].items():
        path = TERMINAL / name
        assert digest == _sha256(path)

    recorded_hashes = {}
    for line in (ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        digest, relative_path = line.split("  ", maxsplit=1)
        recorded_hashes[relative_path] = digest
    expected_hashed_paths = {
        "attempt_claim.json",
        "official_attempt_receipt.json",
        *(f"terminal/{name}" for name in TERMINAL_FILES),
    }
    assert set(recorded_hashes) == expected_hashed_paths
    for relative_path, digest in recorded_hashes.items():
        assert _sha256(ROOT / relative_path) == digest

    processes = receipt["processes"]
    assert len(processes) == 7985
    assert [record["index"] for record in processes] == list(range(7985))
    assert all(record["pid"] > 0 for record in processes)
    assert all(record["returncode"] == 0 for record in processes)
    assert Counter(record["verb"] for record in processes) == EXPECTED_PROCESS_COUNTS

    expected_authority = {
        "inferred_anchor_contract": False,
        "internal_metrics": True,
        "model_fits": False,
        "official_st_rae": False,
        "oracle_evidence": True,
        "predictions": False,
        "submission": False,
        "tdi": False,
        "test_access": False,
        "transduction": False,
    }
    assert receipt["authority"] == manifest["authority"] == expected_authority
    assert all(receipt["operation_accounting"][key] == 0 for key in FORBIDDEN_COUNTERS)
    assert receipt["operation_accounting"] == manifest["operation_accounting"]
    assert not any("test" in name.lower() for name in receipt["source_receipts"])

    for path in TERMINAL.glob("*.csv"):
        with path.open(newline="", encoding="utf-8") as handle:
            columns = next(csv.reader(handle))
        assert FORBIDDEN_RAW_COLUMNS.isdisjoint(name.lower() for name in columns)

    payloads = {name: (TERMINAL / name).read_bytes() for name in TERMINAL_FILES}
    validate_terminal_payloads(payloads, receipt["status"])

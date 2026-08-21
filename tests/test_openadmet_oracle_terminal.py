from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from test_openadmet_oracle_g0 import LOCKED_PYTHON
from test_openadmet_oracle_g0 import _argv as locked_g0_argv
from test_openadmet_oracle_g0 import _fixture as locked_g0_fixture

from cypshift.openadmet_oracle_freezer_io import SYSTEMS
from cypshift.openadmet_oracle_inner import SELECTION_COLUMNS
from cypshift.openadmet_oracle_inner_io import EXPECTED_RUNTIME, LEARNED_SYSTEMS
from cypshift.openadmet_oracle_outer import _score, _serialize
from cypshift.openadmet_oracle_pair_cell import candidate_id
from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS
from cypshift.openadmet_oracle_private_io import publish_readonly_tree
from cypshift.openadmet_oracle_projection import DENIED_AUTHORITY
from cypshift.openadmet_oracle_scoring import (
    EXPECTED_GRIDS,
    PredictionRow,
    PublicQuery,
    SealedTruth,
)
from cypshift.openadmet_oracle_sealed import RESOLVED_CONTRACT_SHA256
from cypshift.openadmet_oracle_terminal import (
    CELL_COLUMNS,
    FailureRecord,
    OracleTerminalError,
    _csv_rows,
    _receipt,
    _validate_terminal,
    publish_failed_terminal,
    publish_underpowered_terminal,
)
from cypshift.openadmet_oracle_terminal_cleanup import (
    CleanupCapability,
    CleanupInput,
    publish_cleanup_receipt,
)
from cypshift.openadmet_oracle_terminal_io import (
    AggregateAccountingInput,
    LoadedAggregateAccounting,
    LoadedFreeze,
    LoadedInnerSelection,
    LoadedSupport,
    OracleTerminalIOError,
    SupportInput,
    failure_source_bundle_sha256,
    load_aggregate_accounting,
    load_support,
    terminal_source_bundle_sha256,
)
from cypshift.openadmet_oracle_terminal_receipts import (
    SUPPORT_EVIDENCE_SCHEMA,
    SUPPORT_EVIDENCE_STATUS,
    ChildManifestInput,
    OracleTerminalReceiptError,
    SupportEvidenceInput,
    load_child_manifest_accounting,
    publish_accounting_receipt,
    publish_support_receipt,
    receipt_source_bundle_sha256,
)
from cypshift.openadmet_transformation_io import canonical_csv_bytes

pytestmark = pytest.mark.skipif(
    sys.version_info[:3] != (3, 12, 3)
    or platform.system() != "Linux"
    or platform.machine() != "x86_64",
    reason="requires the exact R5C root runtime",
)


def _compact(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _support_evidence_root(root: Path, *, supported: bool) -> SupportEvidenceInput:
    primary = [
        {
            "base_episode_query_id": _sha(f"base-{repeat}-{outer}-{index}".encode()),
            "component_id": _sha(
                (
                    f"component-{repeat}-{outer}-{index}"
                    if supported
                    else f"component-{index % 49}"
                ).encode()
            ),
            "repeat": repeat,
            "outer_fold": outer,
        }
        for repeat in range(3)
        for outer in range(5)
        for index in range(10)
    ]
    outer_training = [
        {
            "component_id": _sha(f"outer-family-{index % 50}".encode()),
            "unordered_pair_id": _sha(f"outer-pair-{repeat}-{outer}-{index}".encode()),
            "repeat": repeat,
            "outer_fold": outer,
        }
        for repeat in range(3)
        for outer in range(5)
        for index in range(200)
    ]
    inner_training = [
        {
            "component_id": _sha(f"inner-family-{index % 40}".encode()),
            "unordered_pair_id": _sha(
                f"inner-pair-{repeat}-{outer}-{inner}-{index}".encode()
            ),
            "repeat": repeat,
            "outer_fold": outer,
            "inner_fold": inner,
        }
        for repeat in range(3)
        for outer in range(5)
        for inner in range(4)
        for index in range(150)
    ]
    controls = [
        {
            "system_id": system,
            "base_episode_query_id": _sha(f"control-base-{index}".encode()),
            "component_id": _sha(f"control-component-{index}".encode()),
        }
        for system in ("F0", "F1")
        for index in range(150)
    ]
    arrays = (primary, outer_training, inner_training, controls)
    for rows in arrays:
        rows.sort(key=lambda row: tuple(row.values()))
    evidence = {
        "primary_rows": primary,
        "outer_training_rows": outer_training,
        "inner_training_rows": inner_training,
        "control_local_rows": controls,
    }
    evidence_data = _compact(evidence)
    manifest = {
        "schema_version": SUPPORT_EVIDENCE_SCHEMA,
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "status": SUPPORT_EVIDENCE_STATUS,
        "source_sha256": receipt_source_bundle_sha256(),
        "runtime": EXPECTED_RUNTIME,
        "output_receipts": {
            "evidence.json": {
                "relative_path": "evidence.json",
                "sha256": _sha(evidence_data),
                "bytes": len(evidence_data),
            }
        },
        "operation_accounting": dict.fromkeys(ACCOUNTING_FIELDS, 0),
        "authority": DENIED_AUTHORITY,
    }
    manifest_data = _compact(manifest)
    publish_readonly_tree(
        root, {"manifest.json": manifest_data, "evidence.json": evidence_data}
    )
    return SupportEvidenceInput(root, _sha(manifest_data))


def _support_facts(*, supported: bool) -> tuple[dict[str, object], dict[str, bool]]:
    outer = {
        f"repeat-{repeat}/outer-{outer}": {"families": 10, "rows_or_pairs": 10}
        for repeat in range(3)
        for outer in range(5)
    }
    outer_training = {key: {"families": 50, "rows_or_pairs": 200} for key in outer}
    inner_training = {
        f"repeat-{repeat}/outer-{outer}/inner-{inner}": {
            "families": 40,
            "rows_or_pairs": 150,
        }
        for repeat in range(3)
        for outer in range(5)
        for inner in range(4)
    }
    support: dict[str, object] = {
        "unique_primary_components": 150 if supported else 49,
        "unique_primary_episode_query_pairs": 150,
        "outer_cell_support": outer,
        "outer_training_support": outer_training,
        "inner_training_support": inner_training,
        "control_local_support": {
            "F0": {"families": 150, "rows_or_pairs": 150},
            "F1": {"families": 150, "rows_or_pairs": 150},
        },
    }
    criteria = {
        "unique_primary_components_min_50": supported,
        "unique_primary_episode_query_pairs_min_100": True,
        "all_outer_cells_min_5_components_10_rows": True,
        "all_outer_training_min_50_families_200_pairs": True,
        "all_inner_training_min_40_families_150_pairs": True,
        "F0_min_30_families_50_rows": True,
        "F1_min_30_families_50_rows": True,
    }
    return support, criteria


def _support_root(root: Path, *, supported: bool) -> SupportInput:
    evidence = _support_evidence_root(
        root.parent / f"{root.name}-evidence", supported=supported
    )
    receipt = publish_support_receipt(
        root,
        evidence=evidence,
    )
    assert not evidence.root.exists()
    return SupportInput(root, receipt)


def _accounting_root(root: Path) -> AggregateAccountingInput:
    first = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    first["direct_target_values_parsed"] = 10
    second = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    second["predictions_frozen"] = 1800
    child_inputs = (
        _child_manifest(root.parent / "a-child-root", "a-child", first),
        _child_manifest(root.parent / "z-child-root", "z-child", second),
    )
    children = tuple(
        (item.label, item.expected_manifest_sha256) for item in child_inputs
    )
    receipt = publish_accounting_receipt(
        root,
        child_inputs,
    )
    return AggregateAccountingInput(root, receipt, children, child_inputs)


def _child_manifest(
    root: Path, label: str, accounting: dict[str, int]
) -> ChildManifestInput:
    data = _compact(
        {
            "contract_sha256": RESOLVED_CONTRACT_SHA256,
            "operation_accounting": accounting,
        }
    )
    publish_readonly_tree(root, {"manifest.json": data})
    return ChildManifestInput(label, root, _sha(data))


@pytest.mark.skipif(
    not LOCKED_PYTHON.is_file(), reason="locked research runtime unavailable"
)
def test_accounting_child_accepts_only_exact_locked_g0_json(tmp_path: Path) -> None:
    locked_root = tmp_path / "locked"
    locked_root.mkdir()
    model, model_sha, episode, episode_sha = locked_g0_fixture(locked_root)
    output = tmp_path / "g0"
    completed = subprocess.run(
        locked_g0_argv(model, model_sha, episode, episode_sha, output),
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
        env={"PATH": os.environ.get("PATH", "")},
    )
    assert completed.returncode == 0, completed.stderr
    manifest_data = (output / "manifest.json").read_bytes()
    child = ChildManifestInput("locked-g0", output, _sha(manifest_data))
    accounting = load_child_manifest_accounting(child)
    assert accounting["maplight_model_fits"] == 1

    manifest = json.loads(manifest_data)
    compact = _compact(manifest)
    compact_root = tmp_path / "compact-g0"
    publish_readonly_tree(compact_root, {"manifest.json": compact})
    with pytest.raises(OracleTerminalReceiptError, match="not canonical"):
        load_child_manifest_accounting(
            ChildManifestInput("compact-g0", compact_root, _sha(compact))
        )

    non_g0 = {
        "schema_version": "cypshift.test.non_g0.v1",
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "operation_accounting": dict.fromkeys(ACCOUNTING_FIELDS, 0),
    }
    pretty = (json.dumps(non_g0, indent=2, sort_keys=True) + "\n").encode()
    pretty_root = tmp_path / "pretty-non-g0"
    publish_readonly_tree(pretty_root, {"manifest.json": pretty})
    with pytest.raises(OracleTerminalReceiptError, match="not canonical"):
        load_child_manifest_accounting(
            ChildManifestInput("pretty-non-g0", pretty_root, _sha(pretty))
        )

    noncanonical = manifest_data + b"\n"
    noncanonical_root = tmp_path / "noncanonical-g0"
    publish_readonly_tree(noncanonical_root, {"manifest.json": noncanonical})
    with pytest.raises(OracleTerminalReceiptError, match="not canonical"):
        load_child_manifest_accounting(
            ChildManifestInput("noncanonical-g0", noncanonical_root, _sha(noncanonical))
        )


def _cleanup_input(
    root: Path, capabilities: tuple[CleanupCapability, ...]
) -> CleanupInput:
    receipt = publish_cleanup_receipt(root, capabilities)
    return CleanupInput(root, receipt, capabilities)


def test_support_and_accounting_are_exact_authenticated_inputs(tmp_path: Path) -> None:
    support_input = _support_root(tmp_path / "support", supported=True)
    loaded = load_support(support_input)
    assert loaded.status == "SUPPORTED"
    accounting_input = _accounting_root(tmp_path / "accounting")
    accounting = load_aggregate_accounting(accounting_input)
    assert accounting.operation_accounting["predictions_frozen"] == 1800

    with pytest.raises(OracleTerminalIOError, match="support receipt"):
        load_support(replace(support_input, expected_sha256="0" * 64))
    with pytest.raises(OracleTerminalIOError, match="child"):
        load_aggregate_accounting(
            replace(
                accounting_input,
                expected_child_manifest_receipts=tuple(
                    reversed(accounting_input.expected_child_manifest_receipts)
                ),
            )
        )
    alias = tmp_path / "support-alias"
    alias.symlink_to(support_input.root, target_is_directory=True)
    with pytest.raises(OracleTerminalIOError, match="private ancestry"):
        load_support(replace(support_input, root=alias))


def test_underpowered_and_failed_terminals_have_exact_status_file_sets(
    tmp_path: Path,
) -> None:
    support = _support_root(tmp_path / "support", supported=False)
    underpowered_cleanup = _cleanup_input(
        tmp_path / "underpowered-cleanup",
        (
            CleanupCapability(
                "prefit-support",
                support.root,
                "support.json",
                support.expected_sha256,
            ),
        ),
    )
    source = terminal_source_bundle_sha256()
    failure_source = failure_source_bundle_sha256()
    underpowered = tmp_path / "underpowered"
    publish_underpowered_terminal(
        support,
        underpowered,
        expected_source_sha256=source,
        cleanup_input=underpowered_cleanup,
    )
    assert {path.name for path in underpowered.iterdir()} == {
        "manifest.json",
        "oracle_result.json",
    }
    result = json.loads((underpowered / "oracle_result.json").read_bytes())
    assert result["status"] == "R5_ORACLE_UNDERPOWERED"
    assert not any(result["operation_accounting"].values())

    failed = tmp_path / "failed"
    failed_cleanup = _cleanup_input(tmp_path / "failed-cleanup", ())
    publish_failed_terminal(
        FailureRecord(
            "pre_gate",
            "RECEIPT",
            "authenticated input receipt differs",
            {"support_sha256": support.expected_sha256},
            dict.fromkeys(ACCOUNTING_FIELDS, 0),
        ),
        failed,
        expected_source_sha256=failure_source,
        cleanup_input=failed_cleanup,
    )
    assert [path.name for path in failed.iterdir()] == ["failure.json"]
    assert json.loads((failed / "failure.json").read_bytes())["authority"] == {
        "inferred_anchor_contract": False,
        "internal_metrics": False,
        "model_fits": False,
        "official_st_rae": False,
        "oracle_evidence": False,
        "predictions": False,
        "submission": False,
        "tdi": False,
        "test_access": False,
        "transduction": False,
    }
    late_private = tmp_path / "late-private"
    late_data = _compact({"private": True})
    publish_readonly_tree(late_private, {"manifest.json": late_data})
    late_digest = _sha(late_data)
    late_capabilities = (
        CleanupCapability("late-private", late_private, "manifest.json", late_digest),
    )
    late_cleanup = _cleanup_input(tmp_path / "late-cleanup", late_capabilities)
    late_failed = tmp_path / "late-failed"
    publish_failed_terminal(
        FailureRecord(
            "outer_score",
            "ARITHMETIC",
            "outer arithmetic differs",
            {"late-private": late_digest},
            dict.fromkeys(ACCOUNTING_FIELDS, 0),
        ),
        late_failed,
        expected_source_sha256=failure_source,
        cleanup_input=late_cleanup,
    )
    assert not late_private.exists()
    assert not late_cleanup.root.exists()
    assert (
        json.loads((late_failed / "failure.json").read_bytes())["verified_receipts"][
            "cleanup_manifest_sha256"
        ]
        == late_cleanup.expected_sha256
    )
    with pytest.raises(OracleTerminalError, match="already exists"):
        replay_cleanup = _cleanup_input(tmp_path / "failed-cleanup-replay", ())
        publish_failed_terminal(
            FailureRecord(
                "pre_gate",
                "RECEIPT",
                "authenticated input receipt differs",
                {},
                dict.fromkeys(ACCOUNTING_FIELDS, 0),
            ),
            failed,
            expected_source_sha256=failure_source,
            cleanup_input=replay_cleanup,
        )


def _pure_inputs(stress_prediction: float = 3.0):
    truths: list[SealedTruth] = []
    by_system: dict[str, list[PredictionRow]] = {system: [] for system in SYSTEMS}
    primary_prediction = {
        "G0": 2.0,
        "C0": 1.9,
        "C1": 1.8,
        "C2": 1.7,
        "C3": 1.6,
        "T0": 1.2,
        "F0": 1.5,
        "F1": 1.4,
        "F2": 1.7,
        "A0": 1.8,
        "A1": 1.7,
        "A2": 1.6,
    }
    for repeat in range(3):
        for outer in range(5):
            for index in range(10):
                public = PublicQuery(
                    _sha(f"selected-{repeat}-{outer}-{index}".encode()),
                    f"query-{repeat}-{outer}-{index}",
                    1,
                    "selected_anchor",
                    repeat,
                    outer,
                    _sha(f"component-{repeat}-{outer}-{index}".encode()),
                )
                truth = SealedTruth(public, "CYP3A4", 1.0, True, True, True)
                truths.append(truth)
                for system in SYSTEMS:
                    local = system in {"C0", "C1", "F0", "F1"}
                    by_system[system].append(
                        PredictionRow(
                            public,
                            system,
                            primary_prediction[system],
                            local,
                            system if local else "G0",
                            "VALID_SINGLE",
                            0.8,
                            5,
                            6,
                            True,
                        )
                    )
            stress_public = PublicQuery(
                _sha(f"stress-{repeat}-{outer}".encode()),
                f"stress-query-{repeat}-{outer}",
                1,
                "deterministic_random_anchor_stress",
                repeat,
                outer,
                _sha(f"stress-component-{repeat}-{outer}".encode()),
            )
            truths.append(SealedTruth(stress_public, "CYP3A4", 1.0, True, True, True))
            for system in SYSTEMS:
                by_system[system].append(
                    PredictionRow(
                        stress_public,
                        system,
                        stress_prediction,
                        system in {"C0", "C1", "F0", "F1"},
                        system,
                        "VALID_SINGLE",
                        0.8,
                        5,
                        6,
                        True,
                    )
                )
    return tuple(truths), {name: tuple(rows) for name, rows in by_system.items()}


def test_outer_science_passes_and_stress_is_diagnostic_only() -> None:
    truths, predictions = _pure_inputs()
    first = _score(truths, predictions)
    changed_truths, changed_predictions = _pure_inputs(99.0)
    second = _score(changed_truths, changed_predictions)
    assert first.status == second.status == "R5_ORACLE_SIGNAL_PASS"
    assert first.primary_rows == second.primary_rows
    assert first.bootstrap == second.bootstrap
    assert first.influence == second.influence
    assert first.safety == second.safety
    assert first.stress_rows != second.stress_rows
    assert first.stress != second.stress

    no_signal_predictions = dict(predictions)
    no_signal_predictions["T0"] = tuple(
        replace(row, prediction=2.0) for row in predictions["T0"]
    )
    assert _score(truths, no_signal_predictions).status == "R5_ORACLE_NO_SIGNAL"

    no_stress_truth = tuple(
        replace(row, query_point=None, query_point_available=False)
        if row.public.episode_policy_id == "deterministic_random_anchor_stress"
        else row
        for row in truths
    )
    no_stress = _score(no_stress_truth, predictions)
    assert no_stress.status == first.status
    assert no_stress.primary_rows == first.primary_rows
    assert no_stress.bootstrap == first.bootstrap
    assert no_stress.safety == first.safety
    assert no_stress.stress_rows == ()
    assert all(
        value == {"status": "EMPTY", "scored_rows": 0}
        for value in no_stress.stress.values()
    )


def _selection_data() -> tuple[bytes, tuple[dict[str, str], ...]]:
    rows: list[dict[str, str]] = []
    for system in LEARNED_SYSTEMS:
        configurations = sorted(
            EXPECTED_GRIDS[system],
            key=lambda item: (
                float("-inf") if item[0] is None else item[0],
                float("-inf") if item[1] is None else item[1],
            ),
        )
        selected = configurations[-1]
        for repeat in range(3):
            for outer in range(5):
                for alpha, lambda_value in configurations:
                    rows.append(
                        {
                            "system_id": system,
                            "repeat": str(repeat),
                            "outer_fold": str(outer),
                            "candidate_id": candidate_id(system, alpha, lambda_value),
                            "alpha": ("" if alpha is None else format(alpha, ".17g")),
                            "lambda": (
                                ""
                                if lambda_value is None
                                else format(lambda_value, ".17g")
                            ),
                            "inner_scored_rows": "100",
                            "inner_scored_components": "50",
                            "inner_component_macro_mae": "1",
                            "selected": (
                                "true" if (alpha, lambda_value) == selected else "false"
                            ),
                        }
                    )
    data = canonical_csv_bytes(SELECTION_COLUMNS, rows)
    return data, tuple(rows)


def test_full_terminal_is_exact_deterministic_and_value_private(tmp_path: Path) -> None:
    truths, predictions = _pure_inputs()
    evidence = _score(truths, predictions)
    selection_data, selection_rows = _selection_data()
    freeze_accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    freeze_accounting["predictions_frozen"] = 1980
    freeze = LoadedFreeze(
        "1" * 64,
        {
            "contract_sha256": RESOLVED_CONTRACT_SHA256,
            "input_receipts": {
                "eligibility_manifests": {
                    f"repeat-{repeat}/outer-{outer}": _sha(
                        f"sealed-{repeat}-{outer}".encode()
                    )
                    for repeat in range(3)
                    for outer in range(5)
                }
            },
            "operation_accounting": freeze_accounting,
        },
        {},
        (),
    )
    inner = LoadedInnerSelection("2" * 64, {}, selection_rows, selection_data)
    support_facts, support_criteria = _support_facts(supported=True)
    support = LoadedSupport(
        "3" * 64,
        "SUPPORTED",
        support_facts,
        support_criteria,
    )
    child_receipts = tuple(
        (f"outer-sealed-{index:02d}", _sha(f"sealed-{index}".encode()))
        for index in range(15)
    )
    aggregate_accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    aggregate_accounting["direct_target_values_parsed"] = 1000
    aggregate_accounting["predictions_frozen"] = 1980
    aggregate = LoadedAggregateAccounting(
        "4" * 64,
        child_receipts,
        aggregate_accounting,
    )
    source = terminal_source_bundle_sha256()
    payloads = _serialize(
        freeze,
        inner,
        support,
        aggregate,
        evidence,
        len(truths),
        source,
        EXPECTED_RUNTIME,
        "5" * 64,
    )
    replay_payloads = _serialize(
        freeze,
        inner,
        support,
        aggregate,
        evidence,
        len(truths),
        source,
        EXPECTED_RUNTIME,
        "5" * 64,
    )
    _validate_terminal(payloads, evidence.status)
    assert payloads == replay_payloads
    assert set(payloads) == {
        "manifest.json",
        "oracle_inner_selection.csv",
        "oracle_scored_rows.csv",
        "oracle_cell_metrics.csv",
        "oracle_bootstrap_summary.csv",
        "oracle_influence_checks.csv",
        "oracle_ablation_scorecard.csv",
        "oracle_result.json",
    }
    scored = payloads["oracle_scored_rows.csv"].decode()
    assert "query_point" not in scored
    assert "anchor_point" not in scored
    assert ",prediction," not in scored.splitlines()[0]
    poisoned = {**payloads, "evil.txt": b"not terminal evidence\n"}
    with pytest.raises(OracleTerminalError, match="file set"):
        _validate_terminal(poisoned, evidence.status)

    forged = dict(payloads)
    cell_rows = _csv_rows(forged["oracle_cell_metrics.csv"], CELL_COLUMNS, "cells")
    cell_rows[0]["contrast_vs_T0"] = "99"
    cell_data = canonical_csv_bytes(CELL_COLUMNS, cell_rows)
    manifest = json.loads(forged["manifest.json"])
    manifest["output_receipts"]["oracle_cell_metrics.csv"] = _receipt(
        "oracle_cell_metrics.csv", cell_data, CELL_COLUMNS
    )
    forged["oracle_cell_metrics.csv"] = cell_data
    forged["manifest.json"] = _compact(manifest)
    with pytest.raises(OracleTerminalError, match="cell metric evidence"):
        _validate_terminal(forged, evidence.status)

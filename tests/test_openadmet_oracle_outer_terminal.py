from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from test_openadmet_oracle_terminal import (
    _child_manifest,
    _compact,
    _pure_inputs,
    _selection_data,
    _sha,
    _support_root,
)

from cypshift.openadmet_oracle_freezer_io import (
    FREEZE_SCHEMA,
    FREEZE_STATUS,
    PAIR_SYSTEMS,
    SYSTEMS,
    TOKEN_SYSTEMS,
    freezer_source_bundle_sha256,
    g0_source_bundle_sha256,
    pair_runner_source_bundle_sha256,
)
from cypshift.openadmet_oracle_inner import (
    EXPECTED_SELECTION_ROWS,
    SELECTION_COLUMNS,
    SELECTION_SCHEMA_VERSION,
)
from cypshift.openadmet_oracle_inner_io import (
    EXPECTED_RUNTIME,
    candidate_runner_source_bundle_sha256,
    scorer_source_bundle_sha256,
)
from cypshift.openadmet_oracle_outer import (
    OracleOuterScorerError,
    OuterScorerInputs,
    _child_receipts,
    _required_cleanup,
    score_outer_terminal,
)
from cypshift.openadmet_oracle_pair_cell import FRAGMENT_COLUMNS, candidate_id
from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS
from cypshift.openadmet_oracle_private_io import publish_readonly_tree
from cypshift.openadmet_oracle_projection import (
    DENIED_AUTHORITY,
    SOURCE_PARENT_FILES,
)
from cypshift.openadmet_oracle_sealed import (
    ELIGIBILITY_COLUMNS,
    RESOLVED_CONTRACT_SHA256,
    SEALED_SCHEMA_VERSION,
    SEALED_STATUS,
    V2_CONTRACT_SHA256,
)
from cypshift.openadmet_oracle_terminal_cleanup import (
    CleanupCapability,
    CleanupInput,
    publish_cleanup_receipt,
)
from cypshift.openadmet_oracle_terminal_io import (
    AggregateAccountingInput,
    FreezeInput,
    InnerSelectionInput,
    SealedOuterInput,
    load_freeze,
    load_inner_selection,
    load_sealed_outer,
    terminal_source_bundle_sha256,
)
from cypshift.openadmet_oracle_terminal_receipts import (
    ChildManifestInput,
    publish_accounting_receipt,
)
from cypshift.openadmet_oracle_validation import CLIFF_COLUMNS, TRUTH_COLUMNS
from cypshift.openadmet_transformation_io import canonical_csv_bytes


def _source_binding() -> dict[str, Any]:
    parents = {name: _sha(name.encode()) for name in SOURCE_PARENT_FILES}
    receipts = {
        name: {"sha256": digest, "bytes": len(name)} for name, digest in parents.items()
    }
    return {
        "manifest_receipt": {"sha256": "a" * 64, "bytes": 100},
        "schema_version": "cypshift.openadmet_cyp_2026.oracle_source_bundle.v1",
        "contract_sha256": V2_CONTRACT_SHA256,
        "parent_receipts": parents,
        "input_receipts": receipts,
        "source_receipts": receipts,
    }


def _receipt(name: str, data: bytes, columns: tuple[str, ...]) -> dict[str, Any]:
    return {
        "relative_path": name,
        "sha256": _sha(data),
        "bytes": len(data),
        "rows": data.count(b"\n") - 1,
        "columns": list(columns),
    }


def _sealed_roots(
    root: Path,
    source_binding: dict[str, Any],
    truths: tuple[Any, ...],
) -> tuple[tuple[SealedOuterInput, ...], dict[str, str]]:
    root.mkdir()
    inputs: list[SealedOuterInput] = []
    receipts: dict[str, str] = {}
    for repeat in range(3):
        for outer in range(5):
            scoped = sorted(
                (
                    row
                    for row in truths
                    if row.public.repeat == repeat and row.public.outer_fold == outer
                ),
                key=lambda row: (row.public.episode_id, row.public.query_rank),
            )
            truth_rows = [
                {
                    "episode_id": row.public.episode_id,
                    "query_molecule_id": row.public.query_molecule_id,
                    "selector_cyp_truth": row.selector_cyp_truth,
                    "query_point": format(row.query_point, ".17g"),
                    "query_point_available": "true",
                }
                for row in scoped
            ]
            cliff_rows = [
                {
                    "episode_id": row.public.episode_id,
                    "query_molecule_id": row.public.query_molecule_id,
                    "activity_cliff": "true",
                }
                for row in scoped
            ]
            eligibility_rows = [
                {
                    "episode_id": row.public.episode_id,
                    "query_molecule_id": row.public.query_molecule_id,
                    "query_rank": str(row.public.query_rank),
                    "complete_anchor": "true",
                    "valid_true_transformation": "true",
                    "true_extraction_status": "VALID_SINGLE",
                }
                for row in scoped
            ]
            truth = canonical_csv_bytes(TRUTH_COLUMNS, truth_rows)
            cliffs = canonical_csv_bytes(CLIFF_COLUMNS, cliff_rows)
            eligibility = canonical_csv_bytes(ELIGIBILITY_COLUMNS, eligibility_rows)
            scope = {
                "stage": "outer",
                "repeat": repeat,
                "outer_fold": outer,
                "inner_fold": "",
            }
            accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
            accounting["query_truth_values_opened_by_scorers"] = len(scoped)
            truth_receipt = _receipt("episode_truth.csv", truth, TRUTH_COLUMNS)
            truth_receipt.pop("relative_path")
            cliff_receipt = _receipt("activity_cliffs.csv", cliffs, CLIFF_COLUMNS)
            cliff_receipt.pop("relative_path")
            manifest = {
                "schema_version": SEALED_SCHEMA_VERSION,
                "status": SEALED_STATUS,
                "contract_sha256": RESOLVED_CONTRACT_SHA256,
                "parent_contract_sha256": V2_CONTRACT_SHA256,
                "root": "sealed-scorer",
                "current_cell_scope": scope,
                "parent_receipts": {
                    "v2_sealed_manifest_sha256": "1" * 64,
                    "v2_source_manifest_sha256": source_binding["manifest_receipt"][
                        "sha256"
                    ],
                },
                "input_receipts": {
                    "v2_sealed_manifest.json": {
                        "sha256": "1" * 64,
                        "bytes": 100,
                    },
                    "v2_source_manifest.json": {
                        "sha256": source_binding["manifest_receipt"]["sha256"],
                        "bytes": 100,
                    },
                    "episode_truth.csv": truth_receipt,
                    "activity_cliffs.csv": cliff_receipt,
                },
                "output_receipts": {
                    "episode_truth.csv": truth_receipt,
                    "activity_cliffs.csv": cliff_receipt,
                    "sealed_episode_eligibility.csv": {
                        **_receipt(
                            "sealed_episode_eligibility.csv",
                            eligibility,
                            ELIGIBILITY_COLUMNS,
                        ),
                        "scope": scope,
                    },
                },
                "source_bundle_binding": source_binding,
                "operation_accounting": accounting,
                "authority": DENIED_AUTHORITY,
            }
            data = _compact(manifest)
            cell_root = root / f"sealed-{repeat}-{outer}"
            publish_readonly_tree(
                cell_root,
                {
                    "manifest.json": data,
                    "episode_truth.csv": truth,
                    "activity_cliffs.csv": cliffs,
                    "sealed_episode_eligibility.csv": eligibility,
                },
            )
            inputs.append(SealedOuterInput(repeat, outer, cell_root, _sha(data)))
            receipts[f"repeat-{repeat}/outer-{outer}"] = _sha(data)
    return tuple(inputs), receipts


def _freeze_root(
    root: Path,
    source_binding: dict[str, Any],
    truths: tuple[Any, ...],
    predictions: dict[str, tuple[Any, ...]],
    eligibility_receipts: dict[str, str],
    selection_rows: tuple[dict[str, str], ...],
    accounting_child_sha256: str,
) -> tuple[FreezeInput, dict[str, str]]:
    selected = {
        (row["system_id"], int(row["repeat"]), int(row["outer_fold"])): row[
            "candidate_id"
        ]
        for row in selection_rows
        if row["selected"] == "true"
    }
    token_receipts = {
        f"repeat-{repeat}/outer-{outer}/{system}": _sha(
            f"token-{system}-{repeat}-{outer}".encode()
        )
        for repeat in range(3)
        for outer in range(5)
        for system in TOKEN_SYSTEMS
    }
    payloads: dict[str, bytes] = {}
    for system in SYSTEMS:
        rows: list[dict[str, str]] = []
        for prediction in predictions[system]:
            public = prediction.public
            candidate = selected.get(
                (system, public.repeat, public.outer_fold),
                candidate_id(system, None, None),
            )
            local = system != "G0"
            source = (
                "G0"
                if system == "G0"
                else system
                if system in {"C0", "C1", "F0", "F1"}
                else "LOCAL"
            )
            rows.append(
                {
                    "episode_id": public.episode_id,
                    "query_molecule_id": public.query_molecule_id,
                    "query_rank": str(public.query_rank),
                    "episode_policy_id": public.episode_policy_id,
                    "repeat": str(public.repeat),
                    "outer_fold": str(public.outer_fold),
                    "inner_fold": "",
                    "component_id": public.component_id,
                    "system_id": system,
                    "candidate_id": candidate,
                    "prediction": format(prediction.prediction, ".17g"),
                    "local_available": "true" if local else "false",
                    "prediction_source": source,
                    "extraction_status": "VALID_SINGLE",
                    "similarity": "0.80000000000000004",
                    "exact_support_components": "5",
                    "class_support_components": "6",
                }
            )
        rows.sort(
            key=lambda row: (
                int(row["repeat"]),
                int(row["outer_fold"]),
                row["episode_id"],
                int(row["query_rank"]),
            )
        )
        payloads[f"{system}.csv"] = canonical_csv_bytes(FRAGMENT_COLUMNS, rows)
    eligibility_rows = [
        {
            "episode_id": row.public.episode_id,
            "query_molecule_id": row.public.query_molecule_id,
            "query_rank": str(row.public.query_rank),
            "complete_anchor": "true",
            "valid_true_transformation": "true",
            "true_extraction_status": "VALID_SINGLE",
        }
        for row in sorted(
            truths,
            key=lambda row: (
                row.public.repeat,
                row.public.outer_fold,
                row.public.episode_id,
                row.public.query_rank,
            ),
        )
    ]
    payloads["merged_eligibility.csv"] = canonical_csv_bytes(
        ELIGIBILITY_COLUMNS, eligibility_rows
    )
    pair_receipts = {
        f"repeat-{repeat}/outer-{outer}/{system}": accounting_child_sha256
        for repeat in range(3)
        for outer in range(5)
        for system in PAIR_SYSTEMS
    }
    g0_receipts = {
        f"repeat-{repeat}/outer-{outer}/0000": accounting_child_sha256
        for repeat in range(3)
        for outer in range(5)
    }
    accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    prediction_count = sum(len(rows) for rows in predictions.values())
    accounting["predictions_frozen"] = prediction_count
    outputs = {
        name: _receipt(
            name,
            data,
            ELIGIBILITY_COLUMNS
            if name == "merged_eligibility.csv"
            else FRAGMENT_COLUMNS,
        )
        for name, data in payloads.items()
    }
    manifest = {
        "schema_version": FREEZE_SCHEMA,
        "status": FREEZE_STATUS,
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "scope": {"stage": "outer", "repeats": 3, "outer_folds": 5, "contexts": 15},
        "parent_receipts": {
            "model_public_manifest_sha256": "e" * 64,
            "source_bundle_binding": source_binding,
        },
        "input_receipts": {
            "selection_tokens": token_receipts,
            "pair_fragments": pair_receipts,
            "g0_fragments": g0_receipts,
            "eligibility_manifests": eligibility_receipts,
        },
        "source_receipts": {
            "freezer_source_sha256": freezer_source_bundle_sha256(),
            "pair_runner_source_sha256": pair_runner_source_bundle_sha256(),
            "g0_source_bundle_sha256": g0_source_bundle_sha256(),
        },
        "runtime": EXPECTED_RUNTIME,
        "counts": {
            "contexts": 15,
            "systems": 12,
            "selection_tokens": 90,
            "pair_fragments": 165,
            "g0_fragments": 15,
            "prediction_rows": prediction_count,
            "eligibility_rows": len(eligibility_rows),
        },
        "output_receipts": outputs,
        "operation_accounting": accounting,
        "authority": DENIED_AUTHORITY,
    }
    manifest_data = _compact(manifest)
    publish_readonly_tree(root, {"manifest.json": manifest_data, **payloads})
    return FreezeInput(root, _sha(manifest_data)), token_receipts


def _inner_root(
    root: Path,
    selection_data: bytes,
    selection_rows: tuple[dict[str, str], ...],
    token_receipts: dict[str, str],
    accounting_child_sha256: str,
) -> InnerSelectionInput:
    payloads: dict[str, bytes] = {"oracle_inner_selection.csv": selection_data}
    for index in range(EXPECTED_SELECTION_ROWS):
        payloads[f"merged/{index:03d}/prediction_fragment.csv"] = canonical_csv_bytes(
            FRAGMENT_COLUMNS, []
        )
    selected_rows = [row for row in selection_rows if row["selected"] == "true"]
    for index, row in enumerate(selected_rows):
        payloads[f"pre-token/{index:03d}/selection.json"] = _compact(
            {
                "candidate_id": row["candidate_id"],
                "selected_alpha": None if not row["alpha"] else float(row["alpha"]),
                "selected_lambda": (
                    None if not row["lambda"] else float(row["lambda"])
                ),
            }
        )
    outputs = {
        name: {
            "relative_path": name,
            "sha256": _sha(data),
            "bytes": len(data),
            **(
                {
                    "rows": data.count(b"\n") - 1,
                    "columns": list(
                        SELECTION_COLUMNS
                        if name == "oracle_inner_selection.csv"
                        else FRAGMENT_COLUMNS
                    ),
                }
                if name.endswith(".csv")
                else {}
            ),
        }
        for name, data in payloads.items()
    }
    accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    accounting["query_truth_values_opened_by_scorers"] = 960
    accounting["internal_absolute_error_evaluations"] = 960
    inner_tokens = {
        f"{system}/repeat-{repeat}/outer-{outer}": token_receipts[
            f"repeat-{repeat}/outer-{outer}/{system}"
        ]
        for system in TOKEN_SYSTEMS
        for repeat in range(3)
        for outer in range(5)
    }
    manifest = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "status": "R5_ORACLE_INNER_SELECTION_COMPLETE",
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "scope": {"stage": "inner", "repeats": 3, "outer_folds": 5, "inner_folds": 4},
        "counts": {
            "candidate_fragments": 960,
            "merged_candidate_fragments": 240,
            "sealed_roots": 60,
            "selection_rows": 240,
            "selection_tokens": 90,
        },
        "input_receipts": {
            "candidate_manifests": {
                f"candidate-{index:03d}": accounting_child_sha256
                for index in range(960)
            },
            "sealed_manifests": {
                f"sealed-{index:02d}": accounting_child_sha256 for index in range(60)
            },
        },
        "output_receipts": outputs,
        "token_receipts": inner_tokens,
        "scorer_source_sha256": scorer_source_bundle_sha256(),
        "candidate_source_sha256": candidate_runner_source_bundle_sha256(),
        "runtime": EXPECTED_RUNTIME,
        "operation_accounting": accounting,
        "authority": DENIED_AUTHORITY,
    }
    manifest_data = _compact(manifest)
    publish_readonly_tree(root, {"manifest.json": manifest_data, **payloads})
    return InnerSelectionInput(root, _sha(manifest_data))


def _accounting_root(
    root: Path,
    freeze: FreezeInput,
    inner: InnerSelectionInput,
    sealed: tuple[SealedOuterInput, ...],
    generic_child: ChildManifestInput,
) -> AggregateAccountingInput:
    loaded_freeze = load_freeze(freeze)
    loaded_inner = load_inner_selection(inner)
    loaded_sealed = load_sealed_outer(sealed)
    children = _child_receipts(loaded_freeze, loaded_inner, loaded_sealed)
    roots_by_receipt = {
        freeze.expected_manifest_sha256: freeze.root,
        inner.expected_manifest_sha256: inner.root,
        generic_child.expected_manifest_sha256: generic_child.root,
        **{item.expected_manifest_sha256: item.root for item in sealed},
    }
    child_inputs = tuple(
        ChildManifestInput(label, roots_by_receipt[digest], digest)
        for label, digest in children
    )
    receipt = publish_accounting_receipt(root, child_inputs)
    return AggregateAccountingInput(root, receipt, children, child_inputs)


def test_authenticated_outer_roots_publish_exact_terminal(tmp_path: Path) -> None:
    truths, predictions = _pure_inputs()
    selection_data, selection_rows = _selection_data()
    source_binding = _source_binding()
    sealed, eligibility_receipts = _sealed_roots(
        tmp_path / "sealed", source_binding, truths
    )
    generic_child = _child_manifest(
        tmp_path / "generic-accounting-child",
        "generic",
        dict.fromkeys(ACCOUNTING_FIELDS, 0),
    )
    freeze, tokens = _freeze_root(
        tmp_path / "freeze",
        source_binding,
        truths,
        predictions,
        eligibility_receipts,
        selection_rows,
        generic_child.expected_manifest_sha256,
    )
    inner = _inner_root(
        tmp_path / "inner",
        selection_data,
        selection_rows,
        tokens,
        generic_child.expected_manifest_sha256,
    )
    support = _support_root(tmp_path / "support", supported=True)
    accounting = _accounting_root(
        tmp_path / "accounting", freeze, inner, sealed, generic_child
    )
    provisional = OuterScorerInputs(
        freeze,
        inner,
        sealed,
        support,
        accounting,
        CleanupInput(tmp_path / "unused", "0" * 64, ()),
    )
    cleanup_capabilities = _required_cleanup(provisional)
    cleanup_root = tmp_path / "cleanup"
    cleanup_receipt = publish_cleanup_receipt(cleanup_root, cleanup_capabilities)
    cleanup = CleanupInput(cleanup_root, cleanup_receipt, cleanup_capabilities)
    cleanup_roots = (
        *(item.root for item in cleanup_capabilities),
        cleanup.root,
    )
    unrelated_root = tmp_path / "unrelated-private"
    unrelated_data = _compact({"purpose": "must-not-delete"})
    publish_readonly_tree(unrelated_root, {"manifest.json": unrelated_data})
    extra_capability = CleanupCapability(
        "unrelated-private",
        unrelated_root,
        "manifest.json",
        _sha(unrelated_data),
    )
    extra_capabilities = tuple(
        sorted((*cleanup_capabilities, extra_capability), key=lambda item: item.label)
    )
    extra_cleanup_root = tmp_path / "extra-cleanup"
    extra_cleanup = CleanupInput(
        extra_cleanup_root,
        publish_cleanup_receipt(extra_cleanup_root, extra_capabilities),
        extra_capabilities,
    )
    with pytest.raises(OracleOuterScorerError, match="cleanup set"):
        score_outer_terminal(
            OuterScorerInputs(
                freeze,
                inner,
                sealed,
                support,
                accounting,
                extra_cleanup,
            ),
            tmp_path / "extra-cleanup-terminal",
            expected_source_sha256=terminal_source_bundle_sha256(),
        )
    assert unrelated_root.exists()
    assert extra_cleanup_root.exists()
    poisoned_sealed = (
        replace(sealed[0], expected_manifest_sha256="0" * 64),
        *sealed[1:],
    )
    poisoned_output = tmp_path / "poisoned-terminal"
    with pytest.raises(OracleOuterScorerError, match="sealed manifest receipt"):
        score_outer_terminal(
            OuterScorerInputs(
                freeze,
                inner,
                poisoned_sealed,
                support,
                accounting,
                cleanup,
            ),
            poisoned_output,
            expected_source_sha256=terminal_source_bundle_sha256(),
        )
    assert not poisoned_output.exists()
    assert all(root.exists() for root in cleanup_roots)
    output = tmp_path / "terminal"
    score_outer_terminal(
        OuterScorerInputs(
            freeze,
            inner,
            sealed,
            support,
            accounting,
            cleanup,
        ),
        output,
        expected_source_sha256=terminal_source_bundle_sha256(),
    )
    assert all(not root.exists() for root in cleanup_roots)
    result = json.loads((output / "oracle_result.json").read_bytes())
    assert result["status"] == "R5_ORACLE_SIGNAL_PASS"
    assert result["operation_accounting"]["predictions_frozen"] == 1980
    assert (
        result["operation_accounting"]["query_truth_values_opened_by_scorers"] == 1125
    )
    assert result["operation_accounting"]["internal_absolute_error_evaluations"] == 3090

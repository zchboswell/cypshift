from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from test_openadmet_oracle_pair_runner import g0, runner
from test_openadmet_oracle_projection import _fixture, _rewrite_csv

import cypshift.openadmet_oracle_inner_io as inner_io
from cypshift.openadmet_oracle_cell_io import (
    OracleCellCapability,
    OracleCellTargetCapability,
    load_oracle_cell_capability,
)
from cypshift.openadmet_oracle_inner import (
    EXPECTED_SELECTION_ROWS,
    EXPECTED_TOKENS,
    LEARNED_SYSTEMS,
    CandidateFragmentInput,
    OracleInnerSelectionError,
    SealedInnerInput,
    TokenOutputRoot,
    publish_inner_selection,
)
from cypshift.openadmet_oracle_inner_io import (
    D070_RUNNER_SOURCE_FILES,
    EXPECTED_RUNTIME,
    SCORER_SOURCE_FILES,
    OracleInnerIOError,
    candidate_runner_source_bundle_sha256,
    load_candidate,
    scorer_source_bundle_sha256,
    validate_execution,
)
from cypshift.openadmet_oracle_pair_cell import (
    FRAGMENT_COLUMNS,
    candidate_id,
    cell_id,
    fragment_id,
)
from cypshift.openadmet_oracle_pair_cell_io import (
    ACCOUNTING_FIELDS,
    LEGACY_G0_COLUMNS,
    load_selection_token,
)
from cypshift.openadmet_oracle_projection import (
    DENIED_AUTHORITY,
    SOURCE_PARENT_FILES,
    project_openadmet_oracle_inputs,
)
from cypshift.openadmet_oracle_scoring import EXPECTED_GRIDS
from cypshift.openadmet_oracle_sealed import (
    ELIGIBILITY_COLUMNS,
    RESOLVED_CONTRACT_SHA256,
    SEALED_FILES,
    SEALED_SCHEMA_VERSION,
    SEALED_STATUS,
    OracleSealedCapabilityError,
    load_v3_sealed_scorer,
    migrate_v3_sealed_scorer,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def _trusted_expected_accounting(
    capability: OracleCellCapability, system: str
) -> dict[str, int]:
    """Replay exact counts from the already authenticated raw target view."""

    accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    pair_rows = len(capability.target.training_pairs)
    if hasattr(capability.target, "training_points"):
        point_rows = len(capability.target.training_points)
        contexts = capability.target.episode_anchor_contexts
        available = sum(row["anchor_point_available"] == "true" for row in contexts)
        accounting["direct_target_values_parsed"] = point_rows + pair_rows + available
        accounting["anchor_labels_exposed_to_models"] = available
    else:
        accounting["direct_target_values_parsed"] = pair_rows
    accounting["ridge_model_fits"] = int(system in {"C2", "C3", "T0", "A2"})
    accounting["hierarchy_fits"] = int(system in {"C3", "T0", "A0", "A1"})
    return accounting


def _csv(columns: tuple[str, ...], rows: list[dict[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=list(columns), lineterminator="\n", extrasaction="raise"
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def _readonly(root: Path) -> None:
    for path in root.rglob("*"):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)


def _receipt(data: bytes, columns: tuple[str, ...]) -> dict[str, Any]:
    return {
        "sha256": _sha(data),
        "bytes": len(data),
        "rows": data.count(b"\n") - 1,
        "columns": list(columns),
    }


def test_v3_sealed_migration_adds_exact_trusted_eligibility(tmp_path: Path) -> None:
    source, receipts = _fixture(tmp_path / "fixture")
    projection = project_openadmet_oracle_inputs(
        source, tmp_path / "projection", expected_receipts=receipts
    )
    _readonly(source)
    public = list(
        csv.DictReader(io.StringIO((source / "public_episode_queries.csv").read_text()))
    )
    geometry = {
        (row["episode_id"], row["query_molecule_id"], row["query_rank"]): row
        for row in csv.DictReader(
            io.StringIO((source / "episode_transformations.csv").read_text())
        )
    }
    cases = (
        (("inner", 0, 1, 2), "inner/repeat-0/outer-1/inner-2"),
        (("outer", 0, 1, None), "outer/repeat-0/outer-1"),
    )
    outputs: list[tuple[tuple[str, int, int, int | None], Path]] = []
    for index, (scope, relative) in enumerate(cases):
        v2 = projection.sealed_scorer_root / relative
        output = tmp_path / f"sealed-v3-{index}"
        migrate_v3_sealed_scorer(
            v2,
            source,
            output,
            expected_v2_manifest_sha256=_sha((v2 / "manifest.json").read_bytes()),
            expected_source_manifest_sha256=receipts["manifest.json"],
            expected_scope=scope,  # type: ignore[arg-type]
        )
        manifest_sha = _sha((output / "manifest.json").read_bytes())
        loaded = load_v3_sealed_scorer(
            output,
            expected_manifest_sha256=manifest_sha,
            expected_scope=scope,  # type: ignore[arg-type]
        )
        assert set(path.name for path in output.iterdir()) == set(SEALED_FILES)
        assert loaded.manifest["contract_sha256"] == RESOLVED_CONTRACT_SHA256
        assert loaded.manifest["parent_receipts"] == {
            "v2_sealed_manifest_sha256": _sha((v2 / "manifest.json").read_bytes()),
            "v2_source_manifest_sha256": receipts["manifest.json"],
        }
        assert len(loaded.eligibility_rows) == len(loaded.truth_rows)
        for row in loaded.eligibility_rows:
            true_geometry = geometry[
                (row["episode_id"], row["query_molecule_id"], row["query_rank"])
            ]
            assert row["true_extraction_status"] == true_geometry["extraction_status"]
            assert (row["valid_true_transformation"] == "true") == (
                true_geometry["extraction_status"] in {"VALID_SINGLE", "VALID_DOUBLE"}
            )
        assert all(not path.stat().st_mode & 0o222 for path in output.iterdir())
        outputs.append((scope, output))
    inner_ids = {
        row["episode_id"]
        for row in load_v3_sealed_scorer(
            outputs[0][1],
            expected_manifest_sha256=_sha(
                (outputs[0][1] / "manifest.json").read_bytes()
            ),
            expected_scope=outputs[0][0],  # type: ignore[arg-type]
        ).eligibility_rows
    }
    policies = {row["episode_id"]: row["episode_policy_id"] for row in public}
    assert {policies[episode] for episode in inner_ids} == {"selected_anchor"}
    outer_ids = {
        row["episode_id"]
        for row in load_v3_sealed_scorer(
            outputs[1][1],
            expected_manifest_sha256=_sha(
                (outputs[1][1] / "manifest.json").read_bytes()
            ),
            expected_scope=outputs[1][0],  # type: ignore[arg-type]
        ).eligibility_rows
    }
    assert {policies[episode] for episode in outer_ids} == {
        "selected_anchor",
        "deterministic_random_anchor_stress",
    }
    with pytest.raises(OracleSealedCapabilityError, match="manifest receipt"):
        load_v3_sealed_scorer(
            outputs[0][1],
            expected_manifest_sha256="0" * 64,
            expected_scope=outputs[0][0],  # type: ignore[arg-type]
        )


def _sealed_root(root: Path, repeat: int, outer: int, inner: int) -> SealedInnerInput:
    root.mkdir(parents=True)
    episode = _sha(f"episode-{repeat}-{outer}-{inner}".encode())
    query = f"query-{repeat}-{outer}-{inner}"
    truth_columns = (
        "episode_id",
        "query_molecule_id",
        "selector_cyp_truth",
        "query_point",
        "query_point_available",
    )
    cliff_columns = ("episode_id", "query_molecule_id", "activity_cliff")
    truth = _csv(
        truth_columns,
        [
            {
                "episode_id": episode,
                "query_molecule_id": query,
                "selector_cyp_truth": "CYP3A4",
                "query_point": "0",
                "query_point_available": "true",
            }
        ],
    )
    cliffs = _csv(
        cliff_columns,
        [
            {
                "episode_id": episode,
                "query_molecule_id": query,
                "activity_cliff": "false",
            }
        ],
    )
    eligibility = _csv(
        ELIGIBILITY_COLUMNS,
        [
            {
                "episode_id": episode,
                "query_molecule_id": query,
                "query_rank": "1",
                "complete_anchor": "true",
                "valid_true_transformation": "true",
                "true_extraction_status": "VALID_SINGLE",
            }
        ],
    )
    scope = {
        "stage": "inner",
        "repeat": repeat,
        "outer_fold": outer,
        "inner_fold": inner,
    }
    outputs = {
        "episode_truth.csv": _receipt(truth, truth_columns),
        "activity_cliffs.csv": _receipt(cliffs, cliff_columns),
        "sealed_episode_eligibility.csv": {
            **_receipt(eligibility, ELIGIBILITY_COLUMNS),
            "relative_path": "sealed_episode_eligibility.csv",
            "scope": scope,
        },
    }
    accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    accounting["query_truth_values_opened_by_scorers"] = 1
    manifest = {
        "schema_version": SEALED_SCHEMA_VERSION,
        "status": SEALED_STATUS,
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "parent_contract_sha256": (
            "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
        ),
        "root": "sealed-scorer",
        "current_cell_scope": scope,
        "parent_receipts": {
            "v2_sealed_manifest_sha256": "1" * 64,
            "v2_source_manifest_sha256": "2" * 64,
        },
        "input_receipts": {
            "v2_sealed_manifest.json": {"sha256": "1" * 64, "bytes": 1},
            "v2_source_manifest.json": {"sha256": "2" * 64, "bytes": 1},
            "episode_truth.csv": _receipt(truth, truth_columns),
            "activity_cliffs.csv": _receipt(cliffs, cliff_columns),
        },
        "output_receipts": outputs,
        "source_bundle_binding": {"manifest_receipt": {"sha256": "2" * 64}},
        "operation_accounting": accounting,
        "authority": dict(DENIED_AUTHORITY),
    }
    payloads = {
        "episode_truth.csv": truth,
        "activity_cliffs.csv": cliffs,
        "sealed_episode_eligibility.csv": eligibility,
        "manifest.json": _compact(manifest),
    }
    for name, data in payloads.items():
        (root / name).write_bytes(data)
    _readonly(root)
    return SealedInnerInput(repeat, outer, inner, root, _sha(payloads["manifest.json"]))


def _candidate_root(
    root: Path,
    system: str,
    repeat: int,
    outer: int,
    inner: int,
    alpha: float | None,
    lambda_value: float | None,
    *,
    policy: str = "selected_anchor",
) -> CandidateFragmentInput:
    root.mkdir(parents=True)
    candidate = candidate_id(system, alpha, lambda_value)
    scoped_cell = cell_id(
        "inner",
        repeat,
        outer,
        inner,
        system,
        candidate,
        "all",
        alpha=alpha,
        lambda_=lambda_value,
    )
    episode = _sha(f"episode-{repeat}-{outer}-{inner}".encode())
    row = {
        "episode_id": episode,
        "query_molecule_id": f"query-{repeat}-{outer}-{inner}",
        "query_rank": "1",
        "episode_policy_id": policy,
        "repeat": str(repeat),
        "outer_fold": str(outer),
        "inner_fold": str(inner),
        "component_id": _sha(f"component-{repeat}-{outer}-{inner}".encode()),
        "system_id": system,
        "candidate_id": candidate,
        "prediction": "1",
        "local_available": "true",
        "prediction_source": "LOCAL",
        "extraction_status": "VALID_SINGLE",
        "similarity": "0.8",
        "exact_support_components": "1",
        "class_support_components": "1",
    }
    fragment = _csv(FRAGMENT_COLUMNS, [row])
    accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    accounting["direct_target_values_parsed"] = 10
    accounting["anchor_labels_exposed_to_models"] = 0 if system == "C3" else 1
    accounting["ridge_model_fits"] = int(system in {"C2", "C3", "T0", "A2"})
    accounting["hierarchy_fits"] = int(system in {"C3", "T0", "A0", "A1"})
    runner_source = candidate_runner_source_bundle_sha256()
    source_parents = {name: "8" * 64 for name in SOURCE_PARENT_FILES}
    source_records = {
        name: {"sha256": digest, "bytes": 1} for name, digest in source_parents.items()
    }
    source_binding = {
        "manifest_receipt": {"sha256": "4" * 64, "bytes": 1},
        "schema_version": "cypshift.openadmet_cyp_2026.oracle_source_bundle.v1",
        "contract_sha256": (
            "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
        ),
        "parent_receipts": source_parents,
        "input_receipts": source_records,
        "source_receipts": source_records,
    }
    manifest = {
        "schema_version": (
            "cypshift.openadmet_cyp_2026.r5c_private_prediction_fragment.v1"
        ),
        "status": "R5_ORACLE_PAIR_CELL_COMPLETE",
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "runner_source_sha256": runner_source,
        "scope": {
            "stage": "inner",
            "repeat": repeat,
            "outer_fold": outer,
            "inner_fold": inner,
        },
        "system_id": system,
        "candidate_id": candidate,
        "cell_id": scoped_cell,
        "fragment_id": fragment_id(
            "inner",
            repeat,
            outer,
            inner,
            system,
            candidate,
            "all",
            scoped_cell,
        ),
        "capability_binding": {
            "model_public_manifest_sha256": "5" * 64,
            "target_manifest_sha256": "6" * 64,
            "target_kind": "c3-target" if system == "C3" else "cell-target",
            "g0_manifest_sha256": "7" * 64,
            "system_id": system,
            "source_bundle_binding": source_binding,
            "selection_token": None,
        },
        "g0_bindings": [
            {
                "binding_sha256": "9" * 64,
                "g0_manifest_sha256": "7" * 64,
                "g0_prediction_fragment_sha256": "a" * 64,
                "episode_id": episode,
                "episode_target_manifest_sha256": "b" * 64,
                "r3c_parameter_record_sha256": "c" * 64,
                "g0_source_bundle_sha256": "d" * 64,
            }
        ],
        "runtime": dict(EXPECTED_RUNTIME),
        "operation_accounting": accounting,
        "prediction_fragment": {
            "path": "prediction_fragment.csv",
            "sha256": _sha(fragment),
            "bytes": len(fragment),
            "rows": 1,
            "columns": list(FRAGMENT_COLUMNS),
        },
        "authority": dict(DENIED_AUTHORITY),
    }
    manifest_bytes = _compact(manifest)
    (root / "prediction_fragment.csv").write_bytes(fragment)
    (root / "manifest.json").write_bytes(manifest_bytes)
    _readonly(root)
    return CandidateFragmentInput(
        system,
        repeat,
        outer,
        inner,
        alpha,
        lambda_value,
        root,
        _sha(manifest_bytes),
        accounting,
    )


def _selection_inputs(
    tmp_path: Path,
) -> tuple[list[CandidateFragmentInput], list[SealedInnerInput]]:
    candidates: list[CandidateFragmentInput] = []
    sealed: list[SealedInnerInput] = []
    for repeat in range(3):
        for outer in range(5):
            for inner in range(4):
                sealed.append(
                    _sealed_root(
                        tmp_path
                        / f"sealed/repeat-{repeat}/outer-{outer}/inner-{inner}",
                        repeat,
                        outer,
                        inner,
                    )
                )
                for system in LEARNED_SYSTEMS:
                    for alpha, lambda_value in EXPECTED_GRIDS[system]:
                        candidates.append(
                            _candidate_root(
                                tmp_path
                                / "candidate"
                                / system
                                / f"repeat-{repeat}"
                                / f"outer-{outer}"
                                / f"inner-{inner}"
                                / f"a-{alpha}-l-{lambda_value}",
                                system,
                                repeat,
                                outer,
                                inner,
                                alpha,
                                lambda_value,
                            )
                        )
    return candidates, sealed


def _inner_g0_roots(
    root: Path,
    capability: OracleCellCapability,
    model_sha: str,
    measured_target_sha: str,
    *,
    outer: int,
    inner: int,
) -> tuple[list[Path], list[str]]:
    assert isinstance(capability.target, OracleCellTargetCapability)
    episode_ids = {
        row["episode_id"] for row in capability.target.episode_anchor_contexts
    }
    public = [
        row
        for row in capability.model_public.public_queries
        if row["episode_id"] in episode_ids
    ]
    contexts = {
        row["episode_id"]: row for row in capability.target.episode_anchor_contexts
    }
    source_sha, source_receipts = runner._file_bundle(runner.G0_SOURCE_FILES)
    model_manifest = json.loads(
        json.dumps(capability.model_public.manifest, default=dict)
    )
    roots: list[Path] = []
    receipts: list[str] = []
    for index, episode_id in enumerate(sorted(episode_ids)):
        public_rows = sorted(
            (row for row in public if row["episode_id"] == episode_id),
            key=lambda row: int(row["query_rank"]),
        )
        rows = [
            {
                "molecule_id": row["query_molecule_id"],
                "endpoint": "CYP3A4",
                "component_id": row["outer_group_id"],
                "repeat": "0",
                "outer_fold": row["outer_fold"],
                "inner_fold": str(inner),
                "scope": "openadmet-oracle-inner-v1",
                "system_id": "TRACE-G0-MAPL-FIXED",
                "prediction": "0",
                "applicability_score": "0",
                "model_id": "1" * 64,
                "feature_spec_id": "maplight-fixed-stage-a-v1",
                "split_id": "2" * 64,
            }
            for row in public_rows
        ]
        fragment = _csv(LEGACY_G0_COLUMNS, rows)
        context = contexts[episode_id]
        anchor_rows = int(context["anchor_point_available"] == "true")
        training_rows = len(capability.target.training_points)
        accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
        accounting["direct_target_values_parsed"] = training_rows + anchor_rows
        accounting["anchor_labels_exposed_to_models"] = anchor_rows
        accounting["maplight_model_fits"] = 1
        candidate = candidate_id("G0", None, None)
        scoped_cell = cell_id("inner", 0, outer, inner, "G0", candidate, episode_id)
        episode = {
            "episode_id": episode_id,
            "anchor_molecule_id": public_rows[0]["anchor_molecule_id"],
            "query_rows": len(public_rows),
            "query_rows_sha256": runner._public_receipt(public_rows),
        }
        manifest = {
            "schema_version": "cypshift.openadmet_cyp_2026.r5c_g0_prediction_fragment.v1",
            "status": "R5_ORACLE_G0_EPISODE_COMPLETE",
            "contract_sha256": RESOLVED_CONTRACT_SHA256,
            "parent_contract_sha256": runner.G0_PARENT_CONTRACT_SHA256,
            "runner_source_sha256": source_receipts[
                "research/maplight-fixed/run_r5_oracle_g0.py"
            ],
            "g0_source_bundle_sha256": source_sha,
            "g0_source_file_receipts": source_receipts,
            "model_public_manifest_sha256": model_sha,
            "episode_target_manifest_sha256": _sha(f"target-{episode_id}".encode()),
            "trusted_episode_parent_receipts": {
                "episode_view_builder_source_sha256": "4" * 64,
                "source_cell_target_manifest_sha256": measured_target_sha,
            },
            "source_bundle_binding": model_manifest["source_bundle_binding"],
            "scope": {
                "stage": "inner",
                "repeat": 0,
                "current_outer_validation_fold": outer,
                "inner_fold": inner,
                "episode_outer_fold": int(public_rows[0]["outer_fold"]),
            },
            "episode": episode,
            "system_id": "G0",
            "source_system_id": "TRACE-G0-MAPL-FIXED",
            "candidate_id": candidate,
            "cell_id": scoped_cell,
            "public_query_receipt_sha256": episode["query_rows_sha256"],
            "runtime": {
                "platform": "Linux x86_64 CPU",
                "python_version": "3.10.13",
                "numpy_version": "1.25.2",
                "catboost_version": "1.2.1",
                "uv_lock_sha256": "99e72821b69d9bb943a6e32adc7e0dec0e46c6d32df090241d4fb9296a4195d8",
                "cpu_only": True,
                "max_threads": 16,
            },
            "r3c_parameter_source": g0.bound.R3C_PARAMETER_SOURCE,
            "resolved_catboost_parameters": g0.bound.ACCEPTED_PARAMETERS,
            "counts": {
                "current_training_points": training_rows,
                "anchor_rows": anchor_rows,
                "fit_rows": training_rows + anchor_rows,
                "query_rows": len(rows),
            },
            "operation_accounting": accounting,
            "prediction_fragment": {
                "sha256": _sha(fragment),
                "bytes": len(fragment),
                "rows": len(rows),
                "columns": list(LEGACY_G0_COLUMNS),
            },
            "authority": g0.bound.DENIED_AUTHORITY,
        }
        output = root / f"episode-{index}"
        output.mkdir(parents=True)
        (output / "prediction_fragment.csv").write_bytes(fragment)
        manifest_bytes = g0.bound.json_bytes(manifest)
        (output / "manifest.json").write_bytes(manifest_bytes)
        _readonly(output)
        roots.append(output)
        receipts.append(_sha(manifest_bytes))
    return roots, receipts


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _token_outputs(root: Path) -> list[TokenOutputRoot]:
    outputs: list[TokenOutputRoot] = []
    for system in LEARNED_SYSTEMS:
        for repeat in range(3):
            for outer in range(5):
                parent = root / f"{system}-repeat-{repeat}-outer-{outer}"
                parent.mkdir(parents=True)
                outputs.append(TokenOutputRoot(system, repeat, outer, parent / "token"))
    return outputs


def _publish(
    candidates: list[CandidateFragmentInput],
    sealed: list[SealedInnerInput],
    evidence: Path,
    token_base: Path,
):
    return publish_inner_selection(
        candidates,
        sealed,
        evidence,
        _token_outputs(token_base),
        expected_scorer_source_sha256=scorer_source_bundle_sha256(),
        expected_candidate_source_sha256=candidate_runner_source_bundle_sha256(),
    )


def test_inner_scorer_exact_cardinality_ties_tokens_and_poison(tmp_path: Path) -> None:
    candidates, sealed = _selection_inputs(tmp_path / "inputs")
    first = _publish(
        list(reversed(candidates)),
        list(reversed(sealed)),
        tmp_path / "selection-1",
        tmp_path / "token-parents-1",
    )
    second = _publish(
        candidates,
        sealed,
        tmp_path / "selection-2",
        tmp_path / "token-parents-2",
    )
    assert first.selection_rows == second.selection_rows == EXPECTED_SELECTION_ROWS
    assert first.token_count == second.token_count == EXPECTED_TOKENS
    assert _tree_bytes(first.output_root) == _tree_bytes(second.output_root)
    evidence_manifest = json.loads((first.output_root / "manifest.json").read_bytes())
    assert evidence_manifest["scorer_source_sha256"] == scorer_source_bundle_sha256()
    assert evidence_manifest["candidate_source_sha256"] == (
        candidate_runner_source_bundle_sha256()
    )
    assert evidence_manifest["runtime"] == EXPECTED_RUNTIME
    with (first.output_root / "oracle_inner_selection.csv").open(newline="") as handle:
        selection = list(csv.DictReader(handle))
    assert len(selection) == 16 * 15
    assert sum(row["selected"] == "true" for row in selection) == 6 * 15
    chosen = {
        (row["system_id"], row["alpha"], row["lambda"])
        for row in selection
        if row["selected"] == "true"
    }
    assert chosen == {
        ("C2", "10", ""),
        ("C3", "10", "10"),
        ("T0", "10", "10"),
        ("A0", "", "10"),
        ("A1", "", "10"),
        ("A2", "10", ""),
    }
    forbidden = {
        "score",
        "loss",
        "rank",
        "metric",
        "query_truth",
        "component_loss",
        "bootstrap",
        "influence",
    }
    token_paths = sorted(item.root / "selection_token.json" for item in first.tokens)
    assert len(token_paths) == 90
    for path in token_paths:
        token = json.loads(path.read_bytes())
        assert set(token) == {
            "schema_version",
            "contract_sha256",
            "system_id",
            "repeat",
            "outer_fold",
            "candidate_id",
            "alpha",
            "lambda",
            "candidate_receipt_sha256",
            "scorer_receipt_sha256",
        }
        assert not forbidden & set(token)
        assert token["contract_sha256"] == RESOLVED_CONTRACT_SHA256
        loaded_token = load_selection_token(
            path.parent,
            expected_sha256=_sha(path.read_bytes()),
            requested_system_id=token["system_id"],
            repeat=token["repeat"],
            outer_fold=token["outer_fold"],
            alpha=token["alpha"],
            lambda_=token["lambda"],
        )
        assert loaded_token.candidate_id == token["candidate_id"]
        alpha_path = (
            "null" if token["alpha"] is None else format(token["alpha"], ".17g")
        )
        lambda_path = (
            "null" if token["lambda"] is None else format(token["lambda"], ".17g")
        )
        merged = (
            first.output_root
            / "merged-candidates"
            / token["system_id"]
            / f"repeat-{token['repeat']}"
            / f"outer-{token['outer_fold']}"
            / f"alpha-{alpha_path}"
            / f"lambda-{lambda_path}"
            / "prediction_fragment.csv"
        )
        assert token["candidate_receipt_sha256"] == _sha(merged.read_bytes())
        pretoken = (
            first.output_root
            / "pre-token"
            / token["system_id"]
            / f"repeat-{token['repeat']}"
            / f"outer-{token['outer_fold']}"
            / "selection.json"
        )
        artifact = json.loads(pretoken.read_bytes())
        assert set(artifact) == {
            "candidate_id",
            "selected_alpha",
            "selected_lambda",
        }
        assert token["scorer_receipt_sha256"] == _sha(pretoken.read_bytes())
        assert not path.stat().st_mode & 0o222
        assert not path.parent.stat().st_mode & 0o222
        assert {item.name for item in path.parent.iterdir()} == {"selection_token.json"}
        assert {item.name for item in path.parent.parent.iterdir()} == {"token"}
        assert not any(
            forbidden_name in relative.name
            for relative in path.parent.parent.rglob("*")
            for forbidden_name in (
                "selection.csv",
                "prediction_fragment.csv",
                "selection.json",
            )
        )
    first_token_root = first.tokens[0].root
    token_link = tmp_path / "token-ancestor-link"
    token_link.symlink_to(first_token_root.parent, target_is_directory=True)
    token_data = (first_token_root / "selection_token.json").read_bytes()
    token = json.loads(token_data)
    with pytest.raises(ValueError, match="ancestry"):
        load_selection_token(
            token_link / first_token_root.name,
            expected_sha256=_sha(token_data),
            requested_system_id=token["system_id"],
            repeat=token["repeat"],
            outer_fold=token["outer_fold"],
            alpha=token["alpha"],
            lambda_=token["lambda"],
        )
    with pytest.raises(OracleInnerSelectionError, match="cardinality"):
        _publish(
            candidates[:-1],
            sealed,
            tmp_path / "missing-grid",
            tmp_path / "missing-grid-tokens",
        )
    poisoned_receipt = list(candidates)
    first_input = next(
        item
        for item in poisoned_receipt
        if (
            item.system_id,
            item.repeat,
            item.outer_fold,
            item.inner_fold,
            item.alpha,
            item.lambda_value,
        )
        == ("C2", 0, 0, 0, 1.0, None)
    )
    poisoned_receipt[poisoned_receipt.index(first_input)] = replace(
        first_input, expected_manifest_sha256="0" * 64
    )
    with pytest.raises(OracleInnerSelectionError, match="manifest receipt"):
        _publish(
            poisoned_receipt,
            sealed,
            tmp_path / "receipt-poison",
            tmp_path / "receipt-poison-tokens",
        )
    stress = _candidate_root(
        tmp_path / "stress-poison-root",
        "C2",
        0,
        0,
        0,
        1.0,
        None,
        policy="deterministic_random_anchor_stress",
    )
    poisoned_stress = list(candidates)
    poisoned_stress[poisoned_stress.index(first_input)] = stress
    with pytest.raises(OracleInnerSelectionError, match="row binding"):
        _publish(
            poisoned_stress,
            sealed,
            tmp_path / "stress-poison",
            tmp_path / "stress-poison-tokens",
        )


def test_execution_candidate_and_filesystem_poison_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scorer_source = scorer_source_bundle_sha256()
    runner_source = candidate_runner_source_bundle_sha256()
    with pytest.raises(OracleInnerSelectionError, match="scorer source bundle"):
        publish_inner_selection(
            (),
            (),
            tmp_path / "never-opened",
            (),
            expected_scorer_source_sha256="0" * 64,
            expected_candidate_source_sha256=runner_source,
        )
    with pytest.raises(OracleInnerSelectionError, match="D-070 source bundle"):
        publish_inner_selection(
            (),
            (),
            tmp_path / "candidate-source-never-opened",
            (),
            expected_scorer_source_sha256=scorer_source,
            expected_candidate_source_sha256="0" * 64,
        )
    stable_read = inner_io.read_stable_file
    for name in SCORER_SOURCE_FILES:
        source_path = inner_io.ROOT / name
        with monkeypatch.context() as source_patch:
            source_patch.setattr(
                inner_io,
                "read_stable_file",
                lambda path, target=source_path: (
                    stable_read(path) + b"source-mutation"
                    if path == target
                    else stable_read(path)
                ),
            )
            with pytest.raises(OracleInnerIOError, match="scorer source bundle"):
                validate_execution(
                    expected_scorer_source_sha256=scorer_source,
                    expected_candidate_source_sha256=runner_source,
                )
    for name in D070_RUNNER_SOURCE_FILES:
        source_path = inner_io.ROOT / name
        with monkeypatch.context() as source_patch:
            source_patch.setattr(
                inner_io,
                "read_stable_file",
                lambda path, target=source_path: (
                    stable_read(path) + b"source-mutation"
                    if path == target
                    else stable_read(path)
                ),
            )
            mutated_scorer_source = scorer_source_bundle_sha256()
            with pytest.raises(OracleInnerIOError, match="D-070 source bundle"):
                validate_execution(
                    expected_scorer_source_sha256=mutated_scorer_source,
                    expected_candidate_source_sha256=runner_source,
                )
    candidate = _candidate_root(tmp_path / "candidate", "C3", 0, 0, 0, 1.0, 2.0)
    loaded = load_candidate(candidate, expected_runner_source_sha256=runner_source)
    assert loaded.manifest["runtime"] == EXPECTED_RUNTIME
    for field, value, message in (
        ("runtime", {**EXPECTED_RUNTIME, "python_version": "0"}, "D-070 binding"),
        (
            "operation_accounting",
            dict.fromkeys(ACCOUNTING_FIELDS, 0),
            "accounting fields",
        ),
    ):
        manifest_path = candidate.root / "manifest.json"
        candidate.root.chmod(0o755)
        manifest_path.chmod(0o644)
        manifest = json.loads(manifest_path.read_bytes())
        manifest[field] = value
        poisoned = _compact(manifest)
        manifest_path.write_bytes(poisoned)
        manifest_path.chmod(0o444)
        candidate.root.chmod(0o555)
        poisoned_input = replace(candidate, expected_manifest_sha256=_sha(poisoned))
        with pytest.raises(OracleInnerIOError, match=message):
            load_candidate(poisoned_input, expected_runner_source_sha256=runner_source)
        candidate = _candidate_root(
            tmp_path / f"candidate-{field}", "C3", 0, 0, 0, 1.0, 2.0
        )
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    candidate = _candidate_root(real_parent / "candidate", "C3", 0, 0, 0, 1.0, 2.0)
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    linked_root = linked_parent / "candidate"
    linked_input = replace(candidate, root=linked_root)
    with pytest.raises(OracleInnerIOError, match="ancestry"):
        load_candidate(linked_input, expected_runner_source_sha256=runner_source)
    safe = _candidate_root(tmp_path / "fd-safe", "C2", 0, 0, 0, 1.0, None)
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda _path: (_ for _ in ()).throw(AssertionError("path read")),
    )
    monkeypatch.setattr(
        Path,
        "iterdir",
        lambda _path: (_ for _ in ()).throw(AssertionError("path list")),
    )
    monkeypatch.setattr(
        Path, "stat", lambda _path: (_ for _ in ()).throw(AssertionError("path stat"))
    )
    assert (
        load_candidate(safe, expected_runner_source_sha256=runner_source).source == safe
    )


def test_token_roots_are_independent_and_output_ancestry_is_authenticated(
    tmp_path: Path,
) -> None:
    outputs = _token_outputs(tmp_path / "token-parents")
    shared = list(outputs)
    shared[1] = replace(shared[1], root=shared[0].root.parent / "other-token")
    with pytest.raises(OracleInnerSelectionError, match="isolation"):
        publish_inner_selection(
            (),
            (),
            tmp_path / "evidence",
            shared,
            expected_scorer_source_sha256=scorer_source_bundle_sha256(),
            expected_candidate_source_sha256=candidate_runner_source_bundle_sha256(),
        )
    real_parent = tmp_path / "real-output-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-output-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(OracleInnerSelectionError, match="ancestry"):
        publish_inner_selection(
            (),
            (),
            linked_parent / "evidence",
            _token_outputs(tmp_path / "other-token-parents"),
            expected_scorer_source_sha256=scorer_source_bundle_sha256(),
            expected_candidate_source_sha256=candidate_runner_source_bundle_sha256(),
        )


def test_candidate_accounting_is_exact_for_every_learned_system(
    tmp_path: Path,
) -> None:
    coordinates = {
        "C2": (1.0, None),
        "C3": (1.0, 2.0),
        "T0": (1.0, 2.0),
        "A0": (None, 2.0),
        "A1": (None, 2.0),
        "A2": (1.0, None),
    }
    runner_source = candidate_runner_source_bundle_sha256()
    for system, (alpha, lambda_value) in coordinates.items():
        for field in (
            "direct_target_values_parsed",
            "anchor_labels_exposed_to_models",
        ):
            for delta in (-1, 1):
                candidate = _candidate_root(
                    tmp_path / f"{system}-{field}-{delta}",
                    system,
                    0,
                    0,
                    0,
                    alpha,
                    lambda_value,
                )
                manifest_path = candidate.root / "manifest.json"
                candidate.root.chmod(0o755)
                manifest_path.chmod(0o644)
                manifest = json.loads(manifest_path.read_bytes())
                manifest["operation_accounting"][field] += delta
                poisoned = _compact(manifest)
                manifest_path.write_bytes(poisoned)
                manifest_path.chmod(0o444)
                candidate.root.chmod(0o555)
                with pytest.raises(OracleInnerIOError, match="accounting fields"):
                    load_candidate(
                        replace(
                            candidate,
                            expected_manifest_sha256=_sha(poisoned),
                        ),
                        expected_runner_source_sha256=runner_source,
                    )


def test_sealed_accounting_and_symlink_ancestry_are_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "sealed-parent"
    parent.mkdir()
    sealed_input = _sealed_root(parent / "sealed", 0, 0, 0)
    loaded = load_v3_sealed_scorer(
        sealed_input.root,
        expected_manifest_sha256=sealed_input.expected_manifest_sha256,
        expected_scope=("inner", 0, 0, 0),
    )
    expected = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    expected["query_truth_values_opened_by_scorers"] = 1
    assert loaded.manifest["operation_accounting"] == expected
    link = tmp_path / "sealed-link"
    link.symlink_to(parent, target_is_directory=True)
    with pytest.raises(OracleSealedCapabilityError, match="ancestry"):
        load_v3_sealed_scorer(
            link / "sealed",
            expected_manifest_sha256=sealed_input.expected_manifest_sha256,
            expected_scope=("inner", 0, 0, 0),
        )
    with monkeypatch.context() as path_poison:
        path_poison.setattr(
            Path,
            "read_bytes",
            lambda _path: (_ for _ in ()).throw(AssertionError("path read")),
        )
        path_poison.setattr(
            Path,
            "iterdir",
            lambda _path: (_ for _ in ()).throw(AssertionError("path list")),
        )
        path_poison.setattr(
            Path,
            "stat",
            lambda _path: (_ for _ in ()).throw(AssertionError("path stat")),
        )
        assert load_v3_sealed_scorer(
            sealed_input.root,
            expected_manifest_sha256=sealed_input.expected_manifest_sha256,
            expected_scope=("inner", 0, 0, 0),
        ).query_points


def test_actual_authenticated_d070_fragments_cover_every_learned_system(
    tmp_path: Path,
) -> None:
    source, receipts = _fixture(tmp_path / "fixture")
    for name in ("training_points.csv", "training_pairs.csv"):
        _rewrite_csv(
            source,
            receipts,
            name,
            lambda rows: rows.extend(
                {
                    **row,
                    "stage": "inner",
                    "outer_fold": "2",
                    "inner_fold": "0",
                }
                for row in list(rows)
                if row["stage"] == "outer" and row["outer_fold"] == "1"
            ),
        )
    projection = project_openadmet_oracle_inputs(
        source, tmp_path / "projection", expected_receipts=receipts
    )
    model_root = projection.model_public_root
    measured_root = projection.cell_target_root / "inner/repeat-0/outer-2/inner-0"
    c3_root = projection.c3_target_root / "inner/repeat-0/outer-2/inner-0"
    model_sha = _sha((model_root / "manifest.json").read_bytes())
    measured_sha = _sha((measured_root / "manifest.json").read_bytes())
    measured = load_oracle_cell_capability(
        model_root,
        measured_root,
        expected_model_manifest_sha256=model_sha,
        expected_target_manifest_sha256=measured_sha,
        system_id="C2",
        target_kind="cell-target",
        expected_scope=("inner", 0, 2, 0),
    )
    c3 = load_oracle_cell_capability(
        model_root,
        c3_root,
        expected_model_manifest_sha256=model_sha,
        expected_target_manifest_sha256=_sha((c3_root / "manifest.json").read_bytes()),
        system_id="C3",
        target_kind="c3-target",
        expected_scope=("inner", 0, 2, 0),
    )
    g0_roots, g0_receipts = _inner_g0_roots(
        tmp_path / "g0",
        measured,
        model_sha,
        measured_sha,
        outer=2,
        inner=0,
    )
    coordinates = {
        "C2": (1.0, None),
        "C3": (1.0, 2.0),
        "T0": (1.0, 2.0),
        "A0": (None, 2.0),
        "A1": (None, 2.0),
        "A2": (1.0, None),
    }
    runner_source = runner._source_bundle_sha()
    assert runner_source == candidate_runner_source_bundle_sha256()
    for system, (alpha, lambda_value) in coordinates.items():
        target_root = c3_root if system == "C3" else measured_root
        target_sha = _sha((target_root / "manifest.json").read_bytes())
        output = runner.run(
            model_public_root=model_root,
            target_root=target_root,
            model_manifest_sha256=model_sha,
            target_manifest_sha256=target_sha,
            target_kind="c3-target" if system == "C3" else "cell-target",
            system_id=system,
            alpha=alpha,
            lambda_=lambda_value,
            g0_root=g0_roots,
            g0_manifest_sha256=g0_receipts,
            output_root=tmp_path / f"actual-{system}",
            expected_source_bundle_sha256=runner_source,
            stage="inner",
            repeat=0,
            outer_fold=2,
            inner_fold=0,
            expected_g0_source_cell_target_manifest_sha256=(
                measured_sha if system == "C3" else None
            ),
        )
        source_input = CandidateFragmentInput(
            system,
            0,
            2,
            0,
            alpha,
            lambda_value,
            output,
            _sha((output / "manifest.json").read_bytes()),
            _trusted_expected_accounting(c3 if system == "C3" else measured, system),
        )
        loaded = load_candidate(
            source_input, expected_runner_source_sha256=runner_source
        )
        assert loaded.rows
        assert {
            (row["repeat"], row["outer_fold"], row["inner_fold"]) for row in loaded.rows
        } == {("0", "2", "0")}
        assert loaded.manifest["capability_binding"]["target_kind"] == (
            "c3-target" if system == "C3" else "cell-target"
        )

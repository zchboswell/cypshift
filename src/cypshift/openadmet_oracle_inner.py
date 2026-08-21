"""Authenticated four-fold inner scoring and score-free R5C token publication."""

from __future__ import annotations

import csv
import io
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

from cypshift.openadmet_oracle_inner_io import (
    LEARNED_SYSTEMS,
    CandidateFragmentInput,
    LoadedCandidate,
    OracleInnerIOError,
    _load_candidate_after_source_gate,
    validate_execution,
    validate_expected_accounting,
)
from cypshift.openadmet_oracle_pair_cell import FRAGMENT_COLUMNS
from cypshift.openadmet_oracle_pair_cell_io import (
    ACCOUNTING_FIELDS,
    load_selection_token,
)
from cypshift.openadmet_oracle_private_io import (
    OraclePrivateIOError,
    publish_readonly_tree,
    remove_private_root,
    validate_isolated_output_root,
    validate_output_root,
)
from cypshift.openadmet_oracle_scoring import (
    EXPECTED_GRIDS,
    PRIMARY_POPULATION,
    InnerCandidate,
    PredictionRow,
    PublicQuery,
    ScoredRow,
    SealedTruth,
    aggregate_metrics,
    score_predictions,
    select_inner_candidates,
)
from cypshift.openadmet_oracle_sealed import (
    RESOLVED_CONTRACT_SHA256,
    SealedScorerCapability,
    load_v3_sealed_scorer,
)
from cypshift.openadmet_transformation_io import strict_json_object

SYSTEM_ORDER: Final = {system: index for index, system in enumerate(LEARNED_SYSTEMS)}
SELECTION_COLUMNS: Final = (
    "system_id",
    "repeat",
    "outer_fold",
    "candidate_id",
    "alpha",
    "lambda",
    "inner_scored_rows",
    "inner_scored_components",
    "inner_component_macro_mae",
    "selected",
)
TOKEN_SCHEMA_VERSION: Final = (
    "cypshift.openadmet_cyp_2026.r5c_score_free_selection_token.v1"
)
SELECTION_SCHEMA_VERSION: Final = "cypshift.openadmet_cyp_2026.r5c_inner_selection.v1"
EXPECTED_SELECTION_ROWS: Final = 240
EXPECTED_TOKENS: Final = 90


class OracleInnerSelectionError(ValueError):
    """An inner fragment, sealed truth, selection, or token invariant failed."""


@dataclass(frozen=True, slots=True)
class SealedInnerInput:
    """One independently receipt-bound V3 sealed inner root."""

    repeat: int
    outer_fold: int
    inner_fold: int
    root: Path
    expected_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class InnerSelectionResult:
    """One atomic 15-context selection/token package."""

    output_root: Path
    manifest_sha256: str
    selection_rows: int
    token_count: int
    tokens: tuple[TokenPublication, ...]


@dataclass(frozen=True, slots=True)
class TokenOutputRoot:
    """One explicit independent score-free capability destination."""

    system_id: str
    repeat: int
    outer_fold: int
    root: Path


@dataclass(frozen=True, slots=True)
class TokenPublication:
    """One independently promoted one-file token capability."""

    system_id: str
    repeat: int
    outer_fold: int
    root: Path
    sha256: str


def publish_inner_selection(
    candidate_inputs: Sequence[CandidateFragmentInput],
    sealed_inputs: Sequence[SealedInnerInput],
    output_root: Path,
    token_output_roots: Sequence[TokenOutputRoot],
    *,
    expected_scorer_source_sha256: str,
    expected_candidate_source_sha256: str,
) -> InnerSelectionResult:
    """Score all 960 inner fragments once and publish 240 rows plus 90 tokens."""

    try:
        scorer_source, candidate_source, scorer_runtime = validate_execution(
            expected_scorer_source_sha256=expected_scorer_source_sha256,
            expected_candidate_source_sha256=expected_candidate_source_sha256,
        )
    except OracleInnerIOError as exc:
        raise OracleInnerSelectionError(str(exc)) from exc
    token_outputs = _token_output_index(token_output_roots)
    _preflight_outputs(output_root, token_outputs)
    candidates = _candidate_index(candidate_inputs)
    sealed = _sealed_index(sealed_inputs)
    selection_records: list[InnerCandidate] = []
    merged_receipts: dict[tuple[str, int, int, float | None, float | None], str] = {}
    merged_payloads: dict[str, bytes] = {}
    candidate_manifest_receipts: dict[str, str] = {}
    sealed_manifest_receipts: dict[str, str] = {}
    truth_open_count = 0
    evaluation_count = 0
    for repeat in range(3):
        for outer in range(5):
            sealed_cells = tuple(
                load_v3_sealed_scorer(
                    sealed[(repeat, outer, inner)].root,
                    expected_manifest_sha256=sealed[
                        (repeat, outer, inner)
                    ].expected_manifest_sha256,
                    expected_scope=("inner", repeat, outer, inner),
                )
                for inner in range(4)
            )
            for sealed_cell in sealed_cells:
                sealed_manifest_receipts[
                    _scope_label(repeat, outer, sealed_cell.scope[3])
                ] = sealed_cell.manifest_sha256
                truth_open_count += sum(
                    point is not None for _, _, point in sealed_cell.query_points
                )
            baseline_metadata: dict[int, tuple[tuple[str, ...], ...]] = {}
            for system in LEARNED_SYSTEMS:
                for alpha, lambda_value in _ordered_grid(system):
                    loaded = tuple(
                        _load_candidate(
                            candidates[
                                (system, repeat, outer, inner, alpha, lambda_value)
                            ],
                            expected_runner_source_sha256=candidate_source,
                        )
                        for inner in range(4)
                    )
                    for loaded_fragment in loaded:
                        label = _candidate_input_label(loaded_fragment.source)
                        candidate_manifest_receipts[label] = (
                            loaded_fragment.source.expected_manifest_sha256
                        )
                    merged = _merged_fragment(loaded)
                    merged_receipts[(system, repeat, outer, alpha, lambda_value)] = (
                        sha256(merged).hexdigest()
                    )
                    merged_payloads[
                        _merged_candidate_path(
                            system, repeat, outer, alpha, lambda_value
                        )
                    ] = merged
                    scored: list[ScoredRow] = []
                    for inner, (fragment, sealed_cell) in enumerate(
                        zip(loaded, sealed_cells, strict=True)
                    ):
                        predictions, truths, metadata = _scoring_rows(
                            fragment, sealed_cell
                        )
                        prior = baseline_metadata.get(inner)
                        if prior is None:
                            baseline_metadata[inner] = metadata
                        elif prior != metadata:
                            raise OracleInnerSelectionError(
                                "candidate public metadata differs"
                            )
                        try:
                            scored.extend(
                                score_predictions(
                                    predictions,
                                    truths,
                                    system_id=system,
                                    population_id=PRIMARY_POPULATION,
                                )
                            )
                        except ValueError as exc:
                            raise OracleInnerSelectionError(str(exc)) from exc
                    try:
                        metrics = aggregate_metrics(scored)
                    except ValueError as exc:
                        raise OracleInnerSelectionError(str(exc)) from exc
                    evaluation_count += metrics.scored_rows
                    selection_records.append(
                        InnerCandidate(
                            system,
                            repeat,
                            outer,
                            loaded[0].manifest["candidate_id"],
                            alpha,
                            lambda_value,
                            metrics.component_macro_mae,
                            metrics.scored_rows,
                            metrics.scored_components,
                        )
                    )
    if len(selection_records) != EXPECTED_SELECTION_ROWS:
        raise OracleInnerSelectionError("inner selection row cardinality differs")
    try:
        selected = select_inner_candidates(selection_records)
    except ValueError as exc:
        raise OracleInnerSelectionError(str(exc)) from exc
    if len(selected) != EXPECTED_TOKENS:
        raise OracleInnerSelectionError("selection token cardinality differs")
    selected_ids = {
        (item.system_id, item.repeat, item.outer_fold): item.candidate_id
        for item in selected
    }
    selection_rows = [
        {
            "system_id": item.system_id,
            "repeat": str(item.repeat),
            "outer_fold": str(item.outer_fold),
            "candidate_id": item.candidate_id,
            "alpha": _number(item.alpha),
            "lambda": _number(item.lambda_value),
            "inner_scored_rows": str(item.inner_scored_rows),
            "inner_scored_components": str(item.inner_scored_components),
            "inner_component_macro_mae": format(item.inner_component_macro_mae, ".17g"),
            "selected": (
                "true"
                if selected_ids[(item.system_id, item.repeat, item.outer_fold)]
                == item.candidate_id
                else "false"
            ),
        }
        for item in sorted(selection_records, key=_selection_sort_key)
    ]
    selection_bytes = _csv_bytes(SELECTION_COLUMNS, selection_rows)
    payloads: dict[str, bytes] = {
        "oracle_inner_selection.csv": selection_bytes,
        **merged_payloads,
    }
    token_payloads: dict[tuple[str, int, int], bytes] = {}
    for selected_candidate in selected:
        prefix = _token_prefix(
            selected_candidate.system_id,
            selected_candidate.repeat,
            selected_candidate.outer_fold,
        )
        artifact = _compact_json_bytes(
            {
                "candidate_id": selected_candidate.candidate_id,
                "selected_alpha": selected_candidate.alpha,
                "selected_lambda": selected_candidate.lambda_value,
            }
        )
        scorer_receipt = sha256(artifact).hexdigest()
        candidate_receipt = merged_receipts[
            (
                selected_candidate.system_id,
                selected_candidate.repeat,
                selected_candidate.outer_fold,
                selected_candidate.alpha,
                selected_candidate.lambda_value,
            )
        ]
        token = _compact_json_bytes(
            {
                "schema_version": TOKEN_SCHEMA_VERSION,
                "contract_sha256": RESOLVED_CONTRACT_SHA256,
                "system_id": selected_candidate.system_id,
                "repeat": selected_candidate.repeat,
                "outer_fold": selected_candidate.outer_fold,
                "candidate_id": selected_candidate.candidate_id,
                "alpha": selected_candidate.alpha,
                "lambda": selected_candidate.lambda_value,
                "candidate_receipt_sha256": candidate_receipt,
                "scorer_receipt_sha256": scorer_receipt,
            }
        )
        payloads[f"pre-token/{prefix}/selection.json"] = artifact
        token_payloads[
            (
                selected_candidate.system_id,
                selected_candidate.repeat,
                selected_candidate.outer_fold,
            )
        ] = token
    accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    accounting["query_truth_values_opened_by_scorers"] = truth_open_count
    accounting["internal_absolute_error_evaluations"] = evaluation_count
    output_receipts = {
        name: _receipt(name, data) for name, data in sorted(payloads.items())
    }
    manifest = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "status": "R5_ORACLE_INNER_SELECTION_COMPLETE",
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "scope": {"stage": "inner", "repeats": 3, "outer_folds": 5, "inner_folds": 4},
        "counts": {
            "candidate_fragments": len(candidate_inputs),
            "merged_candidate_fragments": len(merged_payloads),
            "sealed_roots": len(sealed_inputs),
            "selection_rows": len(selection_rows),
            "selection_tokens": len(selected),
        },
        "input_receipts": {
            "candidate_manifests": dict(sorted(candidate_manifest_receipts.items())),
            "sealed_manifests": dict(sorted(sealed_manifest_receipts.items())),
        },
        "output_receipts": output_receipts,
        "token_receipts": {
            _scope_label_token(*key): sha256(data).hexdigest()
            for key, data in sorted(token_payloads.items())
        },
        "scorer_source_sha256": scorer_source,
        "candidate_source_sha256": candidate_source,
        "runtime": dict(scorer_runtime),
        "operation_accounting": accounting,
        "authority": {
            "oracle_evidence": False,
            "inferred_anchor_contract": False,
            "model_fits": False,
            "predictions": False,
            "internal_metrics": False,
            "official_st_rae": False,
            "test_access": False,
            "tdi": False,
            "submission": False,
            "transduction": False,
        },
    }
    manifest_bytes = _compact_json_bytes(manifest)
    payloads["manifest.json"] = manifest_bytes
    _publish_outputs(output_root, payloads, token_outputs, token_payloads)
    publications = tuple(
        TokenPublication(*key, token_outputs[key], sha256(data).hexdigest())
        for key, data in sorted(token_payloads.items())
    )
    return InnerSelectionResult(
        output_root,
        sha256(manifest_bytes).hexdigest(),
        len(selection_rows),
        len(selected),
        publications,
    )


def _candidate_index(
    inputs: Sequence[CandidateFragmentInput],
) -> dict[
    tuple[str, int, int, int, float | None, float | None], CandidateFragmentInput
]:
    expected = (
        3 * 5 * 4 * sum(len(EXPECTED_GRIDS[system]) for system in LEARNED_SYSTEMS)
    )
    if len(inputs) != expected:
        raise OracleInnerSelectionError("candidate input cardinality differs")
    result: dict[
        tuple[str, int, int, int, float | None, float | None], CandidateFragmentInput
    ] = {}
    for item in inputs:
        _digest(item.expected_manifest_sha256, "candidate manifest")
        if item.system_id not in LEARNED_SYSTEMS:
            raise OracleInnerSelectionError("candidate input grid differs")
        try:
            validate_expected_accounting(
                item.expected_operation_accounting, item.system_id
            )
        except OracleInnerIOError as exc:
            raise OracleInnerSelectionError(str(exc)) from exc
        key = (
            item.system_id,
            item.repeat,
            item.outer_fold,
            item.inner_fold,
            item.alpha,
            item.lambda_value,
        )
        if (
            (item.alpha, item.lambda_value) not in EXPECTED_GRIDS[item.system_id]
            or item.repeat not in range(3)
            or item.outer_fold not in range(5)
            or item.inner_fold not in range(4)
            or key in result
        ):
            raise OracleInnerSelectionError("candidate input grid differs")
        result[key] = item
    return result


def _sealed_index(
    inputs: Sequence[SealedInnerInput],
) -> dict[tuple[int, int, int], SealedInnerInput]:
    if len(inputs) != 60:
        raise OracleInnerSelectionError("sealed input cardinality differs")
    result: dict[tuple[int, int, int], SealedInnerInput] = {}
    for item in inputs:
        _digest(item.expected_manifest_sha256, "sealed manifest")
        key = item.repeat, item.outer_fold, item.inner_fold
        if (
            item.repeat not in range(3)
            or item.outer_fold not in range(5)
            or item.inner_fold not in range(4)
            or key in result
        ):
            raise OracleInnerSelectionError("sealed input scope differs")
        result[key] = item
    return result


def _load_candidate(
    source: CandidateFragmentInput, *, expected_runner_source_sha256: str
) -> LoadedCandidate:
    try:
        return _load_candidate_after_source_gate(
            source, expected_runner_source_sha256=expected_runner_source_sha256
        )
    except OracleInnerIOError as exc:
        raise OracleInnerSelectionError(str(exc)) from exc


def _scoring_rows(
    fragment: LoadedCandidate, sealed: SealedScorerCapability
) -> tuple[
    tuple[PredictionRow, ...], tuple[SealedTruth, ...], tuple[tuple[str, ...], ...]
]:
    truth = {
        (row["episode_id"], row["query_molecule_id"]): row for row in sealed.truth_rows
    }
    cliffs = {
        (row["episode_id"], row["query_molecule_id"]): row for row in sealed.cliff_rows
    }
    eligibility = {
        (row["episode_id"], row["query_molecule_id"], row["query_rank"]): row
        for row in sealed.eligibility_rows
    }
    query_points = {
        (episode_id, query_id): point
        for episode_id, query_id, point in sealed.query_points
    }
    predictions: list[PredictionRow] = []
    truths: list[SealedTruth] = []
    metadata: list[tuple[str, ...]] = []
    for row in fragment.rows:
        rank = _canonical_int(row["query_rank"], "query rank")
        key2 = row["episode_id"], row["query_molecule_id"]
        key3 = *key2, row["query_rank"]
        truth_row = truth.get(key2)
        cliff_row = cliffs.get(key2)
        eligibility_row = eligibility.get(key3)
        if truth_row is None or cliff_row is None or eligibility_row is None:
            raise OracleInnerSelectionError("candidate/sealed join differs")
        if row["extraction_status"] != eligibility_row["true_extraction_status"]:
            raise OracleInnerSelectionError("candidate true geometry metadata differs")
        public = PublicQuery(
            row["episode_id"],
            row["query_molecule_id"],
            rank,
            row["episode_policy_id"],
            _canonical_int(row["repeat"], "repeat"),
            _canonical_int(row["outer_fold"], "episode outer fold"),
            row["component_id"],
        )
        query_available = _boolean(
            truth_row["query_point_available"], "query availability"
        )
        point = query_points[key2]
        if query_available != (point is not None):
            raise OracleInnerSelectionError("sealed query point availability differs")
        if not query_available and truth_row["query_point"]:
            raise OracleInnerSelectionError("unavailable truth exposes query point")
        sealed_truth = SealedTruth(
            public,
            truth_row["selector_cyp_truth"],
            point,
            query_available,
            _boolean(
                eligibility_row["valid_true_transformation"],
                "true-transformation eligibility",
            ),
            _boolean(eligibility_row["complete_anchor"], "anchor completion"),
        )
        predictions.append(
            PredictionRow(
                public,
                fragment.source.system_id,
                _finite(row["prediction"], "candidate prediction", canonical=True),
                _boolean(row["local_available"], "local availability"),
                row["prediction_source"],
                row["extraction_status"],
                None
                if row["similarity"] == ""
                else _finite(row["similarity"], "similarity"),
                _canonical_int(row["exact_support_components"], "exact support"),
                _canonical_int(row["class_support_components"], "class support"),
                _boolean(cliff_row["activity_cliff"], "activity cliff"),
            )
        )
        truths.append(sealed_truth)
        metadata.append(
            (
                row["episode_id"],
                row["query_molecule_id"],
                row["query_rank"],
                row["episode_policy_id"],
                row["repeat"],
                row["outer_fold"],
                row["inner_fold"],
                row["component_id"],
                row["extraction_status"],
                row["similarity"],
                row["exact_support_components"],
                row["class_support_components"],
            )
        )
    if len(predictions) != len(truth) or len(predictions) != len(eligibility):
        raise OracleInnerSelectionError("candidate sealed superset differs")
    return tuple(predictions), tuple(truths), tuple(metadata)


def _merged_fragment(fragments: Sequence[LoadedCandidate]) -> bytes:
    rows = [dict(row) for fragment in fragments for row in fragment.rows]
    keys = [
        (row["episode_id"], row["query_molecule_id"], row["query_rank"]) for row in rows
    ]
    if len(keys) != len(set(keys)):
        raise OracleInnerSelectionError("merged candidate key is duplicated")
    rows.sort(key=lambda row: (row["episode_id"], int(row["query_rank"])))
    return _csv_bytes(FRAGMENT_COLUMNS, rows)


def _ordered_grid(system: str) -> tuple[tuple[float | None, float | None], ...]:
    return tuple(
        sorted(
            EXPECTED_GRIDS[system],
            key=lambda item: (
                float("-inf") if item[0] is None else item[0],
                float("-inf") if item[1] is None else item[1],
            ),
        )
    )


def _token_output_index(
    outputs: Sequence[TokenOutputRoot],
) -> dict[tuple[str, int, int], Path]:
    if len(outputs) != EXPECTED_TOKENS:
        raise OracleInnerSelectionError("token output cardinality differs")
    result: dict[tuple[str, int, int], Path] = {}
    parents: set[Path] = set()
    roots: set[Path] = set()
    for item in outputs:
        key = item.system_id, item.repeat, item.outer_fold
        root = item.root.absolute()
        parent = root.parent
        if (
            item.system_id not in LEARNED_SYSTEMS
            or item.repeat not in range(3)
            or item.outer_fold not in range(5)
            or key in result
            or root in roots
            or parent in parents
            or ".." in item.root.parts
        ):
            raise OracleInnerSelectionError("token output isolation differs")
        result[key] = item.root
        roots.add(root)
        parents.add(parent)
    return result


def _preflight_outputs(
    evidence_root: Path, token_outputs: Mapping[tuple[str, int, int], Path]
) -> None:
    try:
        validate_output_root(evidence_root)
        evidence = evidence_root.absolute()
        for root in token_outputs.values():
            absolute = root.absolute()
            if (
                evidence == absolute
                or evidence in absolute.parents
                or absolute in evidence.parents
            ):
                raise OracleInnerSelectionError("token/evidence ancestry overlaps")
            validate_isolated_output_root(root)
    except OraclePrivateIOError as exc:
        raise OracleInnerSelectionError(str(exc)) from exc


def _publish_outputs(
    evidence_root: Path,
    evidence_payloads: Mapping[str, bytes],
    token_outputs: Mapping[tuple[str, int, int], Path],
    token_payloads: Mapping[tuple[str, int, int], bytes],
) -> None:
    _validate_staged_selection(evidence_payloads, token_payloads)
    published: list[Path] = []
    try:
        publish_readonly_tree(evidence_root, evidence_payloads)
        published.append(evidence_root)
        for key, data in sorted(token_payloads.items()):
            root = token_outputs[key]
            publish_readonly_tree(
                root, {"selection_token.json": data}, isolated_parent=True
            )
            published.append(root)
            token = _canonical_object(data, "selection token")
            load_selection_token(
                root,
                expected_sha256=sha256(data).hexdigest(),
                requested_system_id=key[0],
                repeat=key[1],
                outer_fold=key[2],
                alpha=cast(float | None, token["alpha"]),
                lambda_=cast(float | None, token["lambda"]),
            )
    except (OraclePrivateIOError, ValueError) as exc:
        for root in reversed(published):
            try:
                remove_private_root(root)
            except OraclePrivateIOError:
                pass
        raise OracleInnerSelectionError(str(exc)) from exc


def _validate_staged_selection(
    payloads: Mapping[str, bytes],
    token_payloads: Mapping[tuple[str, int, int], bytes],
) -> None:
    manifest = _canonical_object(payloads["manifest.json"], "selection manifest")
    expected_fields = {
        "schema_version",
        "status",
        "contract_sha256",
        "scope",
        "counts",
        "input_receipts",
        "output_receipts",
        "token_receipts",
        "scorer_source_sha256",
        "candidate_source_sha256",
        "runtime",
        "operation_accounting",
        "authority",
    }
    if (
        set(manifest) != expected_fields
        or manifest.get("schema_version") != SELECTION_SCHEMA_VERSION
        or manifest.get("status") != "R5_ORACLE_INNER_SELECTION_COMPLETE"
        or manifest.get("contract_sha256") != RESOLVED_CONTRACT_SHA256
        or manifest.get("counts")
        != {
            "candidate_fragments": 960,
            "merged_candidate_fragments": EXPECTED_SELECTION_ROWS,
            "sealed_roots": 60,
            "selection_rows": EXPECTED_SELECTION_ROWS,
            "selection_tokens": EXPECTED_TOKENS,
        }
    ):
        raise OracleInnerSelectionError("staged selection manifest differs")
    outputs = _object(manifest.get("output_receipts"), "selection outputs")
    expected_outputs = {
        name: _receipt(name, data)
        for name, data in payloads.items()
        if name != "manifest.json"
    }
    if outputs != dict(sorted(expected_outputs.items())):
        raise OracleInnerSelectionError("staged selection receipts differ")
    expected_tokens = {
        _scope_label_token(*key): sha256(data).hexdigest()
        for key, data in sorted(token_payloads.items())
    }
    if manifest.get("token_receipts") != expected_tokens:
        raise OracleInnerSelectionError("staged token receipts differ")
    _digest(manifest.get("scorer_source_sha256"), "scorer source")
    _digest(manifest.get("candidate_source_sha256"), "candidate source")
    rows = _csv_rows(
        payloads["oracle_inner_selection.csv"],
        SELECTION_COLUMNS,
        "inner selection",
    )
    if (
        len(rows) != EXPECTED_SELECTION_ROWS
        or sum(row["selected"] == "true" for row in rows) != EXPECTED_TOKENS
    ):
        raise OracleInnerSelectionError("staged selection cardinality differs")
    for row in rows:
        if (
            row["system_id"] not in LEARNED_SYSTEMS
            or row["selected"] not in {"true", "false"}
            or _canonical_int(row["repeat"], "selection repeat") not in range(3)
            or _canonical_int(row["outer_fold"], "selection outer fold") not in range(5)
        ):
            raise OracleInnerSelectionError("staged selection row differs")
        _finite(
            row["inner_component_macro_mae"], "inner selection metric", canonical=True
        )
    if len(token_payloads) != EXPECTED_TOKENS:
        raise OracleInnerSelectionError("staged token count differs")
    for key, token_data in sorted(token_payloads.items()):
        token = _canonical_object(token_data, "selection token")
        fields = {
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
        if (
            set(token) != fields
            or token.get("schema_version") != TOKEN_SCHEMA_VERSION
            or token.get("contract_sha256") != RESOLVED_CONTRACT_SHA256
            or token.get("system_id") not in LEARNED_SYSTEMS
            or type(token.get("repeat")) is not int
            or token["repeat"] not in range(3)
            or type(token.get("outer_fold")) is not int
            or token["outer_fold"] not in range(5)
        ):
            raise OracleInnerSelectionError("staged token fields differ")
        system = cast(str, token["system_id"])
        repeat = cast(int, token["repeat"])
        outer = cast(int, token["outer_fold"])
        alpha = cast(float | None, token["alpha"])
        lambda_value = cast(float | None, token["lambda"])
        if key != (system, repeat, outer):
            raise OracleInnerSelectionError("staged token scope differs")
        pretoken_path = (
            f"pre-token/{_token_prefix(system, repeat, outer)}/selection.json"
        )
        pretoken_data = payloads[pretoken_path]
        artifact = _canonical_object(pretoken_data, "pre-token selection")
        if (
            artifact
            != {
                "candidate_id": token["candidate_id"],
                "selected_alpha": alpha,
                "selected_lambda": lambda_value,
            }
            or token["scorer_receipt_sha256"] != sha256(pretoken_data).hexdigest()
        ):
            raise OracleInnerSelectionError("staged pre-token binding differs")
        merged_path = _merged_candidate_path(system, repeat, outer, alpha, lambda_value)
        if (
            token["candidate_receipt_sha256"]
            != sha256(payloads[merged_path]).hexdigest()
        ):
            raise OracleInnerSelectionError("staged candidate receipt differs")


def _selection_sort_key(item: InnerCandidate) -> tuple[int, int, int, float, float]:
    return (
        SYSTEM_ORDER[item.system_id],
        item.repeat,
        item.outer_fold,
        float("-inf") if item.alpha is None else item.alpha,
        float("-inf") if item.lambda_value is None else item.lambda_value,
    )


def _candidate_input_label(item: CandidateFragmentInput) -> str:
    return (
        f"{item.system_id}/repeat-{item.repeat}/outer-{item.outer_fold}/"
        f"inner-{item.inner_fold}/alpha-{_number(item.alpha) or 'null'}/"
        f"lambda-{_number(item.lambda_value) or 'null'}"
    )


def _scope_label(repeat: int, outer: int, inner: int | None) -> str:
    if inner is None:
        raise OracleInnerSelectionError("sealed inner scope lacks fold")
    return f"repeat-{repeat}/outer-{outer}/inner-{inner}"


def _scope_label_token(system: str, repeat: int, outer: int) -> str:
    return f"{system}/repeat-{repeat}/outer-{outer}"


def _token_prefix(system: str, repeat: int, outer: int) -> str:
    return f"{system}/repeat-{repeat}/outer-{outer}"


def _merged_candidate_path(
    system: str,
    repeat: int,
    outer: int,
    alpha: float | None,
    lambda_value: float | None,
) -> str:
    return (
        f"merged-candidates/{_token_prefix(system, repeat, outer)}/"
        f"alpha-{_number(alpha) or 'null'}/lambda-{_number(lambda_value) or 'null'}/"
        "prediction_fragment.csv"
    )


def _number(value: float | None) -> str:
    return "" if value is None else format(value, ".17g")


def _csv_bytes(columns: Sequence[str], rows: Sequence[Mapping[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=list(columns), lineterminator="\n", extrasaction="raise"
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def _csv_rows(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    if not data.endswith(b"\n") or b"\r" in data:
        raise OracleInnerSelectionError(f"{label} line endings differ")
    try:
        reader = csv.reader(io.StringIO(data.decode(), newline=""), strict=True)
        if next(reader, None) != list(columns):
            raise OracleInnerSelectionError(f"{label} columns differ")
        return [dict(zip(columns, values, strict=True)) for values in reader]
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        raise OracleInnerSelectionError(f"{label} is invalid") from exc


def _receipt(name: str, data: bytes) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "relative_path": name,
        "sha256": sha256(data).hexdigest(),
        "bytes": len(data),
    }
    if name.endswith(".csv"):
        receipt["rows"] = data.count(b"\n") - 1
        receipt["columns"] = list(
            SELECTION_COLUMNS
            if name == "oracle_inner_selection.csv"
            else FRAGMENT_COLUMNS
        )
    return receipt


def _canonical_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = strict_json_object(data, label)
    except ValueError as exc:
        raise OracleInnerSelectionError(str(exc)) from exc
    if _compact_json_bytes(value) != data:
        raise OracleInnerSelectionError(f"{label} is not canonical")
    return value


def _compact_json_bytes(value: Mapping[str, Any]) -> bytes:
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


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OracleInnerSelectionError(f"{label} is not an object")
    return cast(dict[str, Any], value)


def _boolean(value: str, label: str) -> bool:
    if value not in {"true", "false"}:
        raise OracleInnerSelectionError(f"{label} differs")
    return value == "true"


def _canonical_int(value: str, label: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise OracleInnerSelectionError(f"{label} differs") from exc
    if result < 0 or str(result) != value:
        raise OracleInnerSelectionError(f"{label} differs")
    return result


def _finite(value: str, label: str, *, canonical: bool = False) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise OracleInnerSelectionError(f"{label} is not finite") from exc
    if (
        not value
        or not math.isfinite(result)
        or (canonical and format(result, ".17g") != value)
    ):
        raise OracleInnerSelectionError(f"{label} is not finite")
    return result


def _digest(value: Any, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise OracleInnerSelectionError(f"{label} is not SHA-256")


__all__ = [
    "EXPECTED_SELECTION_ROWS",
    "EXPECTED_TOKENS",
    "LEARNED_SYSTEMS",
    "SELECTION_COLUMNS",
    "CandidateFragmentInput",
    "InnerSelectionResult",
    "OracleInnerSelectionError",
    "SealedInnerInput",
    "TokenOutputRoot",
    "TokenPublication",
    "publish_inner_selection",
]

"""Fixed-verb subprocess boundary for the synthetic R5C state machine.

The root coordinator passes one immutable JSON capability containing paths,
receipts, and coordinates only.  Numeric targets and scores are opened solely
inside the existing trusted stage implementation selected by the verb.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

from cypshift.openadmet_oracle_cell_io import load_oracle_cell_capability
from cypshift.openadmet_oracle_cell_validation import OracleCellTargetCapability
from cypshift.openadmet_oracle_freezer import (
    OuterContextInput,
    freeze_outer_predictions,
)
from cypshift.openadmet_oracle_freezer_g0 import G0Input
from cypshift.openadmet_oracle_freezer_io import (
    EligibilityInput,
    FragmentInput,
    TokenInput,
)
from cypshift.openadmet_oracle_g0_view import build_g0_episode_view
from cypshift.openadmet_oracle_inner import (
    SealedInnerInput,
    TokenOutputRoot,
    publish_inner_selection,
)
from cypshift.openadmet_oracle_inner_io import CandidateFragmentInput
from cypshift.openadmet_oracle_outer import (
    OuterScorerInputs,
    _child_receipts,
    score_outer_terminal,
)
from cypshift.openadmet_oracle_private_io import (
    publish_readonly_tree,
    read_exact_root,
    read_stable_file,
)
from cypshift.openadmet_oracle_projection import project_openadmet_oracle_inputs
from cypshift.openadmet_oracle_runner_cleanup import purge_prefit_private_tree
from cypshift.openadmet_oracle_sealed import migrate_v3_sealed_scorer
from cypshift.openadmet_oracle_source import (
    INPUT_FILES,
    compile_openadmet_oracle_source,
)
from cypshift.openadmet_oracle_support import (
    SupportSourceInput,
    compile_support_evidence,
)
from cypshift.openadmet_oracle_terminal import (
    FailureRecord,
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
    FreezeInput,
    InnerSelectionInput,
    SealedOuterInput,
    SupportInput,
    load_freeze,
    load_inner_selection,
    load_sealed_outer,
)
from cypshift.openadmet_oracle_terminal_receipts import (
    ChildManifestInput,
    SupportEvidenceInput,
    publish_accounting_receipt,
    publish_support_receipt,
)
from cypshift.openadmet_transformation_io import strict_json_object

ROOT: Final = Path(__file__).resolve().parents[2]
SCHEMA: Final = "cypshift.openadmet_cyp_2026.r5c_worker_control.v1"
RESULT_SCHEMA: Final = "cypshift.openadmet_cyp_2026.r5c_worker_result.v1"
VERBS: Final = frozenset(
    {
        "source",
        "project",
        "support",
        "episodes",
        "view",
        "migrate",
        "inner",
        "freezer",
        "accounting",
        "cleanup",
        "outer",
        "underpowered",
        "failed",
        "purge",
    }
)


class OracleWorkerError(ValueError):
    """A worker command or path-only capability differs."""


def worker_source_sha256() -> str:
    return sha256(read_stable_file(Path(__file__).resolve())).hexdigest()


def run_worker(verb: str, control_root: Path) -> None:
    """Execute exactly one fixed stage from one immutable control root."""

    if verb not in VERBS:
        raise OracleWorkerError("worker verb differs")
    payloads = read_exact_root(control_root, ("control.json",))
    control = strict_json_object(payloads["control.json"], "worker control")
    if _compact(control) != payloads["control.json"]:
        raise OracleWorkerError("worker control is not canonical")
    if set(control) != {
        "schema_version",
        "verb",
        "worker_sha256",
        "result_root",
        "payload",
    }:
        raise OracleWorkerError("worker control fields differ")
    if control["schema_version"] != SCHEMA or control["verb"] != verb:
        raise OracleWorkerError("worker control binding differs")
    expected_worker = _string(control["worker_sha256"], "worker SHA")
    if expected_worker != worker_source_sha256():
        raise OracleWorkerError("worker source differs")
    result_root = _path(control["result_root"], "result root")
    payload = _mapping(control["payload"], "worker payload")
    result = _DISPATCH[verb](payload)
    result_data = _compact(
        {
            "schema_version": RESULT_SCHEMA,
            "verb": verb,
            "worker_sha256": expected_worker,
            "result": result,
        }
    )
    publish_readonly_tree(result_root, {"result.json": result_data})


def _source(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(payload, ("source_paths", "expected_receipts", "output_root"))
    path_values = _path_mapping(payload["source_paths"], "source paths")
    if set(path_values) != set(INPUT_FILES):
        raise OracleWorkerError("source path set differs")
    paths = {name: path_values[name] for name in INPUT_FILES}
    receipts = _string_mapping(payload["expected_receipts"], "source receipts")
    result = compile_openadmet_oracle_source(
        paths, _path(payload["output_root"], "output root"), expected_receipts=receipts
    )
    outputs = {
        name: _string(record["sha256"], f"source output: {name}")
        for name, record in result.output_receipts.items()
    }
    outputs["manifest.json"] = result.manifest_sha256
    return {"root": str(result.output_directory), "receipts": outputs}


def _project(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(payload, ("source_root", "expected_receipts", "output_root"))
    output = _path(payload["output_root"], "output root")
    result = project_openadmet_oracle_inputs(
        _path(payload["source_root"], "source root"),
        output,
        expected_receipts=_string_mapping(
            payload["expected_receipts"], "source receipts"
        ),
    )
    manifests = {
        str(path.relative_to(output).parent): sha256(read_stable_file(path)).hexdigest()
        for path in result.manifest_paths
    }
    return {"root": str(output), "manifests": manifests}


def _support(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(
        payload, ("source_root", "expected_receipts", "evidence_root", "support_root")
    )
    evidence_root = _path(payload["evidence_root"], "evidence root")
    source = SupportSourceInput(
        _path(payload["source_root"], "source root"),
        _string_mapping(payload["expected_receipts"], "source receipts"),
    )
    evidence_sha = compile_support_evidence(source, evidence_root)
    support_root = _path(payload["support_root"], "support root")
    support_sha = publish_support_receipt(
        support_root, evidence=SupportEvidenceInput(evidence_root, evidence_sha)
    )
    support = strict_json_object(
        read_exact_root(support_root, ("support.json",))["support.json"],
        "support receipt",
    )
    return {
        "root": str(support_root),
        "sha256": support_sha,
        "support_status": _string(support["support_status"], "support status"),
    }


def _episodes(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(
        payload,
        (
            "model_root",
            "model_manifest_sha256",
            "target_root",
            "target_manifest_sha256",
            "scope",
        ),
    )
    scope = _scope(payload["scope"])
    capability = load_oracle_cell_capability(
        _path(payload["model_root"], "model root"),
        _path(payload["target_root"], "target root"),
        expected_model_manifest_sha256=_digest(
            payload["model_manifest_sha256"], "model manifest"
        ),
        expected_target_manifest_sha256=_digest(
            payload["target_manifest_sha256"], "target manifest"
        ),
        expected_scope=scope,
        system_id="G0",
    )
    if not isinstance(capability.target, OracleCellTargetCapability):
        raise OracleWorkerError("G0 episode target kind differs")
    episode_ids = tuple(
        sorted({row["episode_id"] for row in capability.target.episode_anchor_contexts})
    )
    if not episode_ids:
        raise OracleWorkerError("G0 episode set is empty")
    return {"episode_ids": list(episode_ids)}


def _view(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(
        payload,
        (
            "model_root",
            "model_manifest_sha256",
            "target_root",
            "target_manifest_sha256",
            "scope",
            "episode_id",
            "output_root",
        ),
    )
    result = build_g0_episode_view(
        model_public_root=_path(payload["model_root"], "model root"),
        model_public_manifest_sha256=_digest(
            payload["model_manifest_sha256"], "model manifest"
        ),
        cell_target_root=_path(payload["target_root"], "target root"),
        cell_target_manifest_sha256=_digest(
            payload["target_manifest_sha256"], "target manifest"
        ),
        scope=_scope(payload["scope"]),
        episode_id=_string(payload["episode_id"], "episode identity"),
        output_root=_path(payload["output_root"], "output root"),
    )
    return {
        "root": str(result.output_root),
        "manifest_sha256": result.manifest_sha256,
        "episode_id": result.episode_id,
        "model_manifest_sha256": result.model_public_manifest_sha256,
        "target_manifest_sha256": result.source_cell_target_manifest_sha256,
    }


def _migrate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(
        payload,
        (
            "v2_root",
            "source_root",
            "output_root",
            "v2_manifest_sha256",
            "source_manifest_sha256",
            "scope",
        ),
    )
    scope = _scope(payload["scope"])
    manifest = migrate_v3_sealed_scorer(
        _path(payload["v2_root"], "v2 root"),
        _path(payload["source_root"], "source root"),
        _path(payload["output_root"], "output root"),
        expected_v2_manifest_sha256=_digest(
            payload["v2_manifest_sha256"], "v2 manifest"
        ),
        expected_source_manifest_sha256=_digest(
            payload["source_manifest_sha256"], "source manifest"
        ),
        expected_scope=scope,
    )
    manifest_data = read_stable_file(manifest)
    manifest_record = strict_json_object(manifest_data, "sealed manifest")
    return {
        "root": str(manifest.parent),
        "manifest_sha256": sha256(manifest_data).hexdigest(),
        "operation_accounting": _accounting_vector(
            manifest_record["operation_accounting"]
        ),
    }


def _inner(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(
        payload,
        (
            "candidates",
            "sealed",
            "output_root",
            "token_roots",
            "scorer_source_sha256",
            "candidate_source_sha256",
        ),
    )
    candidates = tuple(
        _candidate(item) for item in _sequence(payload["candidates"], "candidates")
    )
    sealed = tuple(
        _sealed_inner(item) for item in _sequence(payload["sealed"], "sealed")
    )
    tokens = tuple(
        _token_output(item) for item in _sequence(payload["token_roots"], "tokens")
    )
    result = publish_inner_selection(
        candidates,
        sealed,
        _path(payload["output_root"], "output root"),
        tokens,
        expected_scorer_source_sha256=_digest(
            payload["scorer_source_sha256"], "scorer source"
        ),
        expected_candidate_source_sha256=_digest(
            payload["candidate_source_sha256"], "candidate source"
        ),
    )
    token_results = []
    for item in result.tokens:
        token = strict_json_object(
            read_exact_root(item.root, ("selection_token.json",))[
                "selection_token.json"
            ],
            "selection token",
        )
        token_results.append(
            {
                "system_id": item.system_id,
                "repeat": item.repeat,
                "outer_fold": item.outer_fold,
                "root": str(item.root),
                "sha256": item.sha256,
                "candidate_id": _string(token["candidate_id"], "candidate ID"),
                "alpha": token["alpha"],
                "lambda": token["lambda"],
                "candidate_receipt_sha256": _digest(
                    token["candidate_receipt_sha256"], "candidate receipt"
                ),
            }
        )
    return {
        "root": str(result.output_root),
        "manifest_sha256": result.manifest_sha256,
        "selection_rows": result.selection_rows,
        "tokens": token_results,
    }


def _freezer(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(
        payload,
        (
            "contexts",
            "output_root",
            "freezer_source_sha256",
            "pair_source_sha256",
            "g0_source_sha256",
        ),
    )
    contexts = tuple(
        _outer_context(item) for item in _sequence(payload["contexts"], "contexts")
    )
    result = freeze_outer_predictions(
        contexts,
        _path(payload["output_root"], "output root"),
        expected_freezer_source_sha256=_digest(
            payload["freezer_source_sha256"], "freezer source"
        ),
        expected_pair_runner_source_sha256=_digest(
            payload["pair_source_sha256"], "pair source"
        ),
        expected_g0_source_sha256=_digest(payload["g0_source_sha256"], "G0 source"),
    )
    return {
        "root": str(result.output_root),
        "manifest_sha256": result.manifest_sha256,
        "prediction_rows": result.prediction_rows,
        "eligibility_rows": result.eligibility_rows,
    }


def _accounting(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(
        payload,
        (
            "output_root",
            "freeze",
            "inner_selection",
            "sealed_outer",
            "available_children",
        ),
    )
    freeze_row = _mapping(payload["freeze"], "freeze")
    inner_row = _mapping(payload["inner_selection"], "inner selection")
    _keys(freeze_row, ("root", "manifest_sha256"))
    _keys(inner_row, ("root", "manifest_sha256"))
    freeze = FreezeInput(
        _path(freeze_row["root"], "freeze root"),
        _digest(freeze_row["manifest_sha256"], "freeze manifest"),
    )
    inner = InnerSelectionInput(
        _path(inner_row["root"], "inner root"),
        _digest(inner_row["manifest_sha256"], "inner manifest"),
    )
    sealed = tuple(
        _sealed_outer(item)
        for item in _sequence(payload["sealed_outer"], "sealed outer")
    )
    expected = _child_receipts(
        load_freeze(freeze), load_inner_selection(inner), load_sealed_outer(sealed)
    )
    available = tuple(
        _child_manifest(item)
        for item in _sequence(payload["available_children"], "available children")
    )
    by_receipt = {item.expected_manifest_sha256: item for item in available}
    if len(by_receipt) != len(available):
        raise OracleWorkerError("available child receipt duplicates")
    if set(by_receipt) != {digest for _label, digest in expected}:
        raise OracleWorkerError("available child capability set differs")
    children = tuple(
        ChildManifestInput(label, by_receipt[digest].root, digest)
        for label, digest in expected
        if digest in by_receipt
    )
    if (
        tuple((item.label, item.expected_manifest_sha256) for item in children)
        != expected
    ):
        raise OracleWorkerError("accounting child capability set differs")
    root = _path(payload["output_root"], "output root")
    receipt = publish_accounting_receipt(root, children)
    return {
        "root": str(root),
        "sha256": receipt,
        "children": [
            {
                "label": item.label,
                "root": str(item.root),
                "manifest_sha256": item.expected_manifest_sha256,
            }
            for item in children
        ],
    }


def _cleanup(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(payload, ("output_root", "capabilities"))
    capabilities = tuple(
        _cleanup_capability(item)
        for item in _sequence(payload["capabilities"], "cleanup capabilities")
    )
    root = _path(payload["output_root"], "output root")
    receipt = publish_cleanup_receipt(root, capabilities)
    return {"root": str(root), "sha256": receipt}


def _outer(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(payload, ("inputs", "output_root", "source_sha256"))
    result = score_outer_terminal(
        _outer_inputs(_mapping(payload["inputs"], "outer inputs")),
        _path(payload["output_root"], "output root"),
        expected_source_sha256=_digest(payload["source_sha256"], "terminal source"),
    )
    return {"root": str(result)}


def _underpowered(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(payload, ("support", "cleanup", "output_root", "source_sha256"))
    result = publish_underpowered_terminal(
        _support_input(payload["support"]),
        _path(payload["output_root"], "output root"),
        expected_source_sha256=_digest(payload["source_sha256"], "terminal source"),
        cleanup_input=_cleanup_input(payload["cleanup"]),
    )
    return {"root": str(result)}


def _failed(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(payload, ("record", "cleanup", "output_root", "source_sha256"))
    record = _mapping(payload["record"], "failure record")
    _keys(
        record,
        (
            "stage",
            "failure_code",
            "reason",
            "verified_receipts",
            "operation_accounting",
        ),
    )
    result = publish_failed_terminal(
        FailureRecord(
            _string(record["stage"], "failure stage"),
            _string(record["failure_code"], "failure code"),
            _string(record["reason"], "failure reason"),
            _string_mapping(record["verified_receipts"], "verified receipts"),
            _accounting_vector(record["operation_accounting"]),
        ),
        _path(payload["output_root"], "output root"),
        expected_source_sha256=_digest(payload["source_sha256"], "terminal source"),
        cleanup_input=_cleanup_input(payload["cleanup"]),
    )
    return {"root": str(result)}


def _purge(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(payload, ("private_root", "witness_root"))
    witness = _path(payload["witness_root"], "witness root")
    receipt = purge_prefit_private_tree(
        _path(payload["private_root"], "private root"), witness
    )
    return {"root": str(witness), "sha256": receipt}


def _candidate(value: Any) -> CandidateFragmentInput:
    row = _mapping(value, "candidate")
    _keys(
        row,
        (
            "system_id",
            "repeat",
            "outer_fold",
            "inner_fold",
            "alpha",
            "lambda",
            "root",
            "manifest_sha256",
            "operation_accounting",
        ),
    )
    return CandidateFragmentInput(
        _string(row["system_id"], "system"),
        _integer(row["repeat"], "repeat"),
        _integer(row["outer_fold"], "outer"),
        _integer(row["inner_fold"], "inner"),
        _optional_float(row["alpha"], "alpha"),
        _optional_float(row["lambda"], "lambda"),
        _path(row["root"], "candidate root"),
        _digest(row["manifest_sha256"], "candidate manifest"),
        _accounting_vector(row["operation_accounting"]),
    )


def _sealed_inner(value: Any) -> SealedInnerInput:
    row = _mapping(value, "sealed inner")
    _keys(row, ("repeat", "outer_fold", "inner_fold", "root", "manifest_sha256"))
    return SealedInnerInput(
        _integer(row["repeat"], "repeat"),
        _integer(row["outer_fold"], "outer"),
        _integer(row["inner_fold"], "inner"),
        _path(row["root"], "sealed root"),
        _digest(row["manifest_sha256"], "sealed manifest"),
    )


def _token_output(value: Any) -> TokenOutputRoot:
    row = _mapping(value, "token output")
    _keys(row, ("system_id", "repeat", "outer_fold", "root"))
    return TokenOutputRoot(
        _string(row["system_id"], "system"),
        _integer(row["repeat"], "repeat"),
        _integer(row["outer_fold"], "outer"),
        _path(row["root"], "token root"),
    )


def _outer_context(value: Any) -> OuterContextInput:
    row = _mapping(value, "outer context")
    _keys(row, ("repeat", "outer_fold", "tokens", "fragments", "g0", "eligibility"))
    return OuterContextInput(
        _integer(row["repeat"], "repeat"),
        _integer(row["outer_fold"], "outer"),
        tuple(_token_input(item) for item in _sequence(row["tokens"], "tokens")),
        tuple(
            _fragment_input(item) for item in _sequence(row["fragments"], "fragments")
        ),
        _g0_input(row["g0"]),
        _eligibility_input(row["eligibility"]),
    )


def _token_input(value: Any) -> TokenInput:
    row = _mapping(value, "token input")
    _keys(
        row, ("system_id", "repeat", "outer_fold", "alpha", "lambda", "root", "sha256")
    )
    return TokenInput(
        _string(row["system_id"], "system"),
        _integer(row["repeat"], "repeat"),
        _integer(row["outer_fold"], "outer"),
        _optional_float(row["alpha"], "alpha"),
        _optional_float(row["lambda"], "lambda"),
        _path(row["root"], "token root"),
        _digest(row["sha256"], "token SHA"),
    )


def _fragment_input(value: Any) -> FragmentInput:
    row = _mapping(value, "fragment input")
    _keys(
        row,
        (
            "system_id",
            "repeat",
            "outer_fold",
            "root",
            "manifest_sha256",
            "operation_accounting",
        ),
    )
    return FragmentInput(
        _string(row["system_id"], "system"),
        _integer(row["repeat"], "repeat"),
        _integer(row["outer_fold"], "outer"),
        _path(row["root"], "fragment root"),
        _digest(row["manifest_sha256"], "fragment manifest"),
        _accounting_vector(row["operation_accounting"]),
    )


def _g0_input(value: Any) -> G0Input:
    row = _mapping(value, "G0 input")
    _keys(row, ("repeat", "outer_fold", "roots", "manifest_sha256"))
    return G0Input(
        _integer(row["repeat"], "repeat"),
        _integer(row["outer_fold"], "outer"),
        tuple(_path(item, "G0 root") for item in _sequence(row["roots"], "G0 roots")),
        tuple(
            _digest(item, "G0 manifest")
            for item in _sequence(row["manifest_sha256"], "G0 manifests")
        ),
    )


def _eligibility_input(value: Any) -> EligibilityInput:
    row = _mapping(value, "eligibility input")
    _keys(
        row, ("repeat", "outer_fold", "root", "manifest_sha256", "operation_accounting")
    )
    return EligibilityInput(
        _integer(row["repeat"], "repeat"),
        _integer(row["outer_fold"], "outer"),
        _path(row["root"], "eligibility root"),
        _digest(row["manifest_sha256"], "eligibility manifest"),
        _accounting_vector(row["operation_accounting"]),
    )


def _outer_inputs(row: Mapping[str, Any]) -> OuterScorerInputs:
    _keys(
        row,
        (
            "freeze",
            "inner_selection",
            "sealed_outer",
            "support",
            "aggregate_accounting",
            "cleanup",
        ),
    )
    freeze = _mapping(row["freeze"], "freeze")
    inner = _mapping(row["inner_selection"], "inner selection")
    _keys(freeze, ("root", "manifest_sha256"))
    _keys(inner, ("root", "manifest_sha256"))
    return OuterScorerInputs(
        FreezeInput(
            _path(freeze["root"], "freeze root"),
            _digest(freeze["manifest_sha256"], "freeze manifest"),
        ),
        InnerSelectionInput(
            _path(inner["root"], "inner root"),
            _digest(inner["manifest_sha256"], "inner manifest"),
        ),
        tuple(
            _sealed_outer(item)
            for item in _sequence(row["sealed_outer"], "sealed outer")
        ),
        _support_input(row["support"]),
        _aggregate_input(row["aggregate_accounting"]),
        _cleanup_input(row["cleanup"]),
    )


def _sealed_outer(value: Any) -> SealedOuterInput:
    row = _mapping(value, "sealed outer")
    _keys(row, ("repeat", "outer_fold", "root", "manifest_sha256"))
    return SealedOuterInput(
        _integer(row["repeat"], "repeat"),
        _integer(row["outer_fold"], "outer"),
        _path(row["root"], "sealed root"),
        _digest(row["manifest_sha256"], "sealed manifest"),
    )


def _support_input(value: Any) -> SupportInput:
    row = _mapping(value, "support input")
    _keys(row, ("root", "sha256"))
    return SupportInput(
        _path(row["root"], "support root"), _digest(row["sha256"], "support SHA")
    )


def _aggregate_input(value: Any) -> AggregateAccountingInput:
    row = _mapping(value, "aggregate input")
    _keys(row, ("root", "sha256", "child_receipts", "child_manifests"))
    receipts = tuple(
        (_string(item[0], "child label"), _digest(item[1], "child SHA"))
        for item in _pairs(row["child_receipts"], "child receipts")
    )
    return AggregateAccountingInput(
        _path(row["root"], "accounting root"),
        _digest(row["sha256"], "accounting SHA"),
        receipts,
        tuple(
            _child_manifest(item)
            for item in _sequence(row["child_manifests"], "child manifests")
        ),
    )


def _child_manifest(value: Any) -> ChildManifestInput:
    row = _mapping(value, "child manifest")
    _keys(row, ("label", "root", "manifest_sha256"))
    return ChildManifestInput(
        _string(row["label"], "child label"),
        _path(row["root"], "child root"),
        _digest(row["manifest_sha256"], "child manifest"),
    )


def _cleanup_input(value: Any) -> CleanupInput:
    row = _mapping(value, "cleanup input")
    _keys(row, ("root", "sha256", "capabilities"))
    return CleanupInput(
        _path(row["root"], "cleanup root"),
        _digest(row["sha256"], "cleanup SHA"),
        tuple(
            _cleanup_capability(item)
            for item in _sequence(row["capabilities"], "cleanup capabilities")
        ),
    )


def _cleanup_capability(value: Any) -> CleanupCapability:
    row = _mapping(value, "cleanup capability")
    _keys(row, ("label", "root", "relative_path", "sha256"))
    return CleanupCapability(
        _string(row["label"], "cleanup label"),
        _path(row["root"], "cleanup root"),
        _string(row["relative_path"], "cleanup relative path"),
        _digest(row["sha256"], "cleanup SHA"),
    )


def _accounting_vector(value: Any) -> dict[str, int]:
    from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS

    row = _mapping(value, "operation accounting")
    if set(row) != set(ACCOUNTING_FIELDS) or any(
        type(item) is not int or item < 0 for item in row.values()
    ):
        raise OracleWorkerError("operation accounting differs")
    return cast(dict[str, int], dict(row))


def _path_mapping(value: Any, label: str) -> dict[str, Path]:
    return {name: _path(item, label) for name, item in _mapping(value, label).items()}


def _scope(value: Any) -> tuple[str, int, int, int | None]:
    row = _mapping(value, "scope")
    _keys(row, ("stage", "repeat", "outer_fold", "inner_fold"))
    stage = _string(row["stage"], "stage")
    if stage not in {"inner", "outer"}:
        raise OracleWorkerError("scope stage differs")
    inner = row["inner_fold"]
    return (
        stage,
        _integer(row["repeat"], "repeat"),
        _integer(row["outer_fold"], "outer fold"),
        None if inner is None else _integer(inner, "inner fold"),
    )


def _string_mapping(value: Any, label: str) -> dict[str, str]:
    return {name: _string(item, label) for name, item in _mapping(value, label).items()}


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise OracleWorkerError(f"{label} differs")
    return cast(Mapping[str, Any], value)


def _sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise OracleWorkerError(f"{label} differs")
    return cast(Sequence[Any], value)


def _pairs(value: Any, label: str) -> Sequence[Sequence[Any]]:
    rows = _sequence(value, label)
    if any(not isinstance(row, list) or len(row) != 2 for row in rows):
        raise OracleWorkerError(f"{label} differs")
    return cast(Sequence[Sequence[Any]], rows)


def _keys(value: Mapping[str, Any], expected: Sequence[str]) -> None:
    if set(value) != set(expected):
        raise OracleWorkerError("worker payload fields differ")


def _path(value: Any, label: str) -> Path:
    text = _string(value, label)
    path = Path(text)
    if not path.is_absolute() or ".." in path.parts:
        raise OracleWorkerError(f"{label} differs")
    return path


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise OracleWorkerError(f"{label} differs")
    return value


def _integer(value: Any, label: str) -> int:
    if type(value) is not int:
        raise OracleWorkerError(f"{label} differs")
    return value


def _optional_float(value: Any, label: str) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float):
        raise OracleWorkerError(f"{label} differs")
    return float(value)


def _digest(value: Any, label: str) -> str:
    text = _string(value, label)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise OracleWorkerError(f"{label} differs")
    return text


def _compact(value: Any) -> bytes:
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


_DISPATCH = {
    "source": _source,
    "project": _project,
    "support": _support,
    "episodes": _episodes,
    "view": _view,
    "migrate": _migrate,
    "inner": _inner,
    "freezer": _freezer,
    "accounting": _accounting,
    "cleanup": _cleanup,
    "outer": _outer,
    "underpowered": _underpowered,
    "failed": _failed,
    "purge": _purge,
}


def main() -> None:
    if len(sys.argv) != 3:
        raise OracleWorkerError("worker argv differs")
    run_worker(sys.argv[1], Path(sys.argv[2]))


if __name__ == "__main__":
    main()


__all__ = [
    "OracleWorkerError",
    "RESULT_SCHEMA",
    "SCHEMA",
    "VERBS",
    "run_worker",
    "worker_source_sha256",
]

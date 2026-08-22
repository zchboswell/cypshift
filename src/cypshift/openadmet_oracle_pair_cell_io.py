"""Authenticated G0 transport and atomic publication for R5C pair cells."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import stat
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, Literal, cast

from cypshift.openadmet_oracle_cell_io import load_oracle_cell_capability
from cypshift.openadmet_oracle_cell_validation import (
    OracleCellCapability,
    OracleCellTargetCapability,
)
from cypshift.openadmet_oracle_pair_cell import (
    FRAGMENT_COLUMNS,
    PairCellResult,
    candidate_id,
    cell_id,
    fragment_id,
)

CONTRACT_SHA256: Final = (
    "9143ecd1b24d1d9a97b1e5821e2b953f4cfffcec1cc39de3a8c49b81a4f58a50"
)
G0_COLUMNS: Final = FRAGMENT_COLUMNS
LEGACY_G0_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "component_id",
    "repeat",
    "outer_fold",
    "inner_fold",
    "scope",
    "system_id",
    "prediction",
    "applicability_score",
    "model_id",
    "feature_spec_id",
    "split_id",
)
OUTPUT_FILES: Final = ("manifest.json", "prediction_fragment.csv")
TOKEN_FILE: Final = "selection_token.json"
ACCOUNTING_FIELDS: Final = (
    "direct_target_values_parsed",
    "anchor_labels_exposed_to_models",
    "query_truth_values_opened_by_scorers",
    "maplight_model_fits",
    "ridge_model_fits",
    "hierarchy_fits",
    "predictions_frozen",
    "internal_absolute_error_evaluations",
    "blinded_test_files_opened",
    "tdi_files_opened",
    "official_metric_calls",
    "submissions_created",
    "transductive_relationships",
    "inferred_anchor_candidate_pools",
)


class OraclePairCellIOError(ValueError):
    """An input fragment, receipt, or publication invariant failed."""


@dataclass(frozen=True, slots=True)
class G0FragmentRoot:
    """One authenticated G0 fragment plus its private manifest metadata."""

    manifest_sha256: str
    manifest: Mapping[str, Any]
    rows: tuple[Mapping[str, str], ...]
    legacy: bool


@dataclass(frozen=True, slots=True)
class SelectionToken:
    """One authenticated score-free outer candidate-selection token."""

    sha256: str
    system_id: str
    repeat: int
    outer_fold: int
    candidate_id: str
    alpha: float | None
    lambda_: float | None
    candidate_receipt_sha256: str
    scorer_receipt_sha256: str


def load_selection_token(
    root: Path,
    *,
    expected_sha256: str,
    requested_system_id: str,
    repeat: int,
    outer_fold: int,
    alpha: float | None,
    lambda_: float | None,
) -> SelectionToken:
    """Authenticate one canonical token root before an outer learned fit."""

    _digest(expected_sha256, "selection token")
    expected_system = (
        "T0" if requested_system_id in {"F0", "F1", "F2"} else requested_system_id
    )
    if expected_system not in {"C2", "C3", "T0", "A0", "A1", "A2"}:
        raise OraclePairCellIOError("selection-token system differs")
    fd = _open_root(root)
    try:
        if set(os.listdir(fd)) != {TOKEN_FILE}:
            raise OraclePairCellIOError("selection-token file set differs")
        if os.fstat(fd).st_mode & 0o222:
            raise OraclePairCellIOError("selection-token root is writable")
        token_info = os.stat(TOKEN_FILE, dir_fd=fd, follow_symlinks=False)
        if not stat.S_ISREG(token_info.st_mode) or token_info.st_mode & 0o222:
            raise OraclePairCellIOError("selection-token file mode differs")
        data = _read_at(fd, TOKEN_FILE)
        if sha256(data).hexdigest() != expected_sha256:
            raise OraclePairCellIOError("selection-token receipt differs")
        token = _json(data, "selection token")
    finally:
        os.close(fd)
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
    if set(token) != fields:
        raise OraclePairCellIOError("selection-token fields differ")
    expected_candidate = candidate_id(expected_system, alpha, lambda_)
    if (
        token["schema_version"]
        != "cypshift.openadmet_cyp_2026.r5c_score_free_selection_token.v1"
        or token["contract_sha256"] != CONTRACT_SHA256
        or token["system_id"] != expected_system
        or type(token["repeat"]) is not int
        or token["repeat"] != repeat
        or type(token["outer_fold"]) is not int
        or token["outer_fold"] != outer_fold
        or token["candidate_id"] != expected_candidate
        or token["alpha"] != alpha
        or token["lambda"] != lambda_
    ):
        raise OraclePairCellIOError("selection-token binding differs")
    _digest(token["candidate_receipt_sha256"], "selected candidate receipt")
    _digest(token["scorer_receipt_sha256"], "selection scorer receipt")
    return SelectionToken(
        expected_sha256,
        expected_system,
        repeat,
        outer_fold,
        expected_candidate,
        alpha,
        lambda_,
        token["candidate_receipt_sha256"],
        token["scorer_receipt_sha256"],
    )


def load_g0_predictions(
    root: Path | Sequence[Path],
    *,
    expected_manifest_sha256: str | Sequence[str],
    scope: tuple[Literal["inner", "outer"], int, int, int | None],
    public_queries: Sequence[Mapping[str, str]],
) -> dict[tuple[str, str, int], float]:
    """Load exactly one authenticated G0 fragment and return query-keyed values."""

    return load_g0_fragments(
        root,
        expected_manifest_sha256=expected_manifest_sha256,
        scope=scope,
        public_queries=public_queries,
    )[0]


def load_g0_fragments(
    root: Path | Sequence[Path],
    *,
    expected_manifest_sha256: str | Sequence[str],
    scope: tuple[Literal["inner", "outer"], int, int, int | None],
    public_queries: Sequence[Mapping[str, str]],
) -> tuple[dict[tuple[str, str, int], float], tuple[G0FragmentRoot, ...]]:
    """Load authenticated G0 fragments and return both values and manifests."""

    _validate_scope(scope)
    roots = (root,) if isinstance(root, Path) else tuple(root)
    receipts = (
        (expected_manifest_sha256,)
        if isinstance(expected_manifest_sha256, str)
        else tuple(expected_manifest_sha256)
    )
    if len(roots) != len(receipts) or not roots:
        raise OraclePairCellIOError("G0 root/receipt cardinality differs")
    loaded = tuple(
        _load_g0_root(path, digest, scope)
        for path, digest in zip(roots, receipts, strict=True)
    )
    expected = {
        (row["episode_id"], row["query_molecule_id"], int(row["query_rank"])): row
        for row in public_queries
    }
    if len(expected) != len(public_queries):
        raise OraclePairCellIOError("public query keys are duplicated")
    values: dict[tuple[str, str, int], float] = {}
    for loaded_root in loaded:
        manifest = loaded_root.manifest
        rows = loaded_root.rows
        if loaded_root.legacy:
            for row in rows:
                episode_id = str(manifest["episode"]["episode_id"])
                candidates = [
                    key
                    for key in expected
                    if key[0] == episode_id and key[1] == row["molecule_id"]
                ]
                if len(candidates) != 1:
                    raise OraclePairCellIOError(
                        "legacy G0 episode/query identity differs"
                    )
                key = candidates[0]
                value_text = row["prediction"]
                system = row["system_id"]

                if system != "TRACE-G0-MAPL-FIXED":
                    raise OraclePairCellIOError("legacy G0 source metadata differs")
                value = _finite(value_text, "legacy G0 prediction")
                if format(value, ".17g") != value_text:
                    raise OraclePairCellIOError(
                        "legacy G0 prediction serialization differs"
                    )
                if key in values:
                    raise OraclePairCellIOError("legacy G0 query is duplicated")
                values[key] = value
        else:
            for row in rows:
                key = (
                    row["episode_id"],
                    row["query_molecule_id"],
                    int(row["query_rank"]),
                )
                public = expected.get(key)
                if public is None:
                    raise OraclePairCellIOError("G0 query population differs")
                if row["episode_policy_id"] != public["episode_policy_id"]:
                    raise OraclePairCellIOError("G0 public query identity differs")
                if (
                    row["repeat"] != public["repeat"]
                    or row["outer_fold"] != public["outer_fold"]
                ):
                    raise OraclePairCellIOError("G0 public scope differs")
                if row["component_id"] != public["outer_group_id"]:
                    raise OraclePairCellIOError("G0 component identity differs")
                expected_inner = "" if scope[3] is None else str(scope[3])
                if row["inner_fold"] != expected_inner or row["system_id"] != "G0":
                    raise OraclePairCellIOError("G0 scope/source metadata differs")
                if (
                    row["prediction_source"] != "G0"
                    or row["local_available"] != "false"
                ):
                    raise OraclePairCellIOError("G0 source metadata differs")
                value = _finite(row["prediction"], "G0 prediction")
                if format(value, ".17g") != row["prediction"]:
                    raise OraclePairCellIOError("G0 prediction serialization differs")
                if key in values:
                    raise OraclePairCellIOError("G0 query is duplicated")
                values[key] = value
    if set(values) != set(expected):
        raise OraclePairCellIOError("G0 query population differs")
    return values, loaded


def _load_g0_root(
    root: Path,
    expected_manifest_sha256: str,
    scope: tuple[Literal["inner", "outer"], int, int, int | None],
) -> G0FragmentRoot:
    _digest(expected_manifest_sha256, "expected G0 manifest")
    _validate_scope(scope)
    fd = _open_root(root)
    try:
        if set(os.listdir(fd)) != set(OUTPUT_FILES):
            raise OraclePairCellIOError("G0 output file set differs")
        manifest_data = _read_at(fd, "manifest.json")
        if sha256(manifest_data).hexdigest() != expected_manifest_sha256:
            raise OraclePairCellIOError("G0 manifest receipt differs")
        try:
            manifest = json.loads(manifest_data.decode())
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OraclePairCellIOError("G0 manifest is invalid") from exc
        if not isinstance(manifest, dict):
            raise OraclePairCellIOError("G0 manifest is not an object")
        schema = manifest.get("schema_version")
        receipt_hint = manifest.get("prediction_fragment")
        legacy = (
            schema == "cypshift.openadmet_cyp_2026.r5c_g0_prediction_fragment.v1"
            and isinstance(receipt_hint, Mapping)
            and receipt_hint.get("columns") == list(LEGACY_G0_COLUMNS)
        )
        if not legacy:
            _validate_manifest(manifest, scope)
        else:
            _validate_legacy_manifest(manifest, scope)
        fragment = _read_at(fd, "prediction_fragment.csv")
        receipt = manifest.get("prediction_fragment")
        columns = LEGACY_G0_COLUMNS if legacy else G0_COLUMNS
        if (
            not isinstance(receipt, Mapping)
            or receipt.get("sha256") != sha256(fragment).hexdigest()
            or receipt.get("bytes") != len(fragment)
            or receipt.get("rows") != fragment.count(b"\n") - 1
            or receipt.get("columns") != list(columns)
        ):
            raise OraclePairCellIOError("G0 fragment receipt differs")
    finally:
        os.close(fd)
    return G0FragmentRoot(
        expected_manifest_sha256,
        manifest,
        tuple(_rows(fragment, columns)),
        legacy,
    )


def publish_authenticated_pair_cell(
    output_root: Path,
    result: PairCellResult,
    *,
    model_public_root: Path,
    target_root: Path,
    expected_model_manifest_sha256: str,
    expected_target_manifest_sha256: str,
    target_kind: Literal["cell-target", "c3-target"],
    expected_scope: tuple[Literal["inner", "outer"], int, int, int | None],
    g0_root: Path | Sequence[Path],
    expected_g0_manifest_sha256: str | Sequence[str],
    runner_source_sha256: str,
    runtime: Mapping[str, Any],
    selection_token_root: Path | None = None,
    expected_selection_token_sha256: str | None = None,
    selected_alpha: float | None = None,
    selected_lambda: float | None = None,
) -> Path:
    """Reopen every raw authority root, derive bindings, and publish immediately."""

    capability = load_oracle_cell_capability(
        model_public_root,
        target_root,
        expected_model_manifest_sha256=expected_model_manifest_sha256,
        expected_target_manifest_sha256=expected_target_manifest_sha256,
        system_id=result.system_id,
        target_kind=target_kind,
        expected_scope=expected_scope,
    )
    episode_ids = {
        row["episode_id"]
        for row in (
            capability.target.episode_anchor_contexts
            if isinstance(capability.target, OracleCellTargetCapability)
            else capability.target.global_anchor_contexts
        )
    }
    public = [
        row
        for row in capability.model_public.public_queries
        if row["episode_id"] in episode_ids
    ]
    _g0, fragments = load_g0_fragments(
        g0_root,
        expected_manifest_sha256=expected_g0_manifest_sha256,
        scope=expected_scope,
        public_queries=public,
    )
    bindings = _derive_g0_binding_records(
        fragments,
        model_manifest_sha256=expected_model_manifest_sha256,
        scope=expected_scope,
    )
    learned = result.system_id in {
        "C2",
        "C3",
        "T0",
        "F0",
        "F1",
        "F2",
        "A0",
        "A1",
        "A2",
    }
    token: SelectionToken | None = None
    if expected_scope[0] == "outer" and learned:
        if selection_token_root is None or expected_selection_token_sha256 is None:
            raise OraclePairCellIOError(
                "outer learned publication lacks selection token"
            )
        token = load_selection_token(
            selection_token_root,
            expected_sha256=expected_selection_token_sha256,
            requested_system_id=result.system_id,
            repeat=expected_scope[1],
            outer_fold=expected_scope[2],
            alpha=selected_alpha,
            lambda_=selected_lambda,
        )
        _validate_selection_token_object(token)
    elif (
        selection_token_root is not None or expected_selection_token_sha256 is not None
    ):
        raise OraclePairCellIOError("selection token is forbidden for this publication")
    return _publish_loaded_pair_cell(
        output_root,
        result,
        capability=capability,
        fragments=fragments,
        g0_bindings=bindings,
        runner_source_sha256=runner_source_sha256,
        runtime=runtime,
        token=token,
    )


def _publish_loaded_pair_cell(
    output_root: Path,
    result: PairCellResult,
    *,
    capability: OracleCellCapability,
    fragments: Sequence[G0FragmentRoot],
    g0_bindings: Sequence[Mapping[str, Any]],
    runner_source_sha256: str,
    runtime: Mapping[str, Any],
    token: SelectionToken | None,
) -> Path:
    """Verify all frozen identities and provenance, then publish atomically."""

    target = capability.target
    scope = target.scope
    _validate_scope(scope)
    model_public_manifest_sha256 = capability.model_public.manifest_sha256
    target_manifest_sha256 = target.manifest_sha256
    _digest(model_public_manifest_sha256, "model-public manifest")
    _digest(target_manifest_sha256, "target manifest")
    _digest(runner_source_sha256, "pair runner source bundle")
    if not fragments:
        raise OraclePairCellIOError("G0 manifest binding is empty")
    g0_manifest_sha256 = tuple(fragment.manifest_sha256 for fragment in fragments)
    for receipt in g0_manifest_sha256:
        _digest(receipt, "G0 manifest")
    source_bundle_binding = capability.model_public.manifest.get(
        "source_bundle_binding"
    )
    if not isinstance(source_bundle_binding, Mapping):
        raise OraclePairCellIOError("source-bundle binding differs")
    _validate_source_bundle_binding(source_bundle_binding)
    if not runtime:
        raise OraclePairCellIOError("pair runtime binding is empty")
    target_kind = target.kind
    if result.system_id == "C3" and target_kind != "c3-target":
        raise OraclePairCellIOError("C3 target kind differs")
    if result.system_id != "C3" and target_kind != "cell-target":
        raise OraclePairCellIOError("measured target kind differs")
    if capability.system_id != result.system_id and not (
        capability.system_id == "T0" and result.system_id in {"F0", "F1"}
    ):
        raise OraclePairCellIOError("pair capability system differs")
    _validate_g0_publication_material(result, fragments, g0_bindings)
    if token is not None:
        _digest(token.sha256, "selection token")
        expected_token_system = (
            "T0" if result.system_id in {"F0", "F1", "F2"} else result.system_id
        )
        if (
            scope[0] != "outer"
            or token.system_id != expected_token_system
            or token.repeat != scope[1]
            or token.outer_fold != scope[2]
            or token.candidate_id
            != candidate_id(token.system_id, token.alpha, token.lambda_)
        ):
            raise OraclePairCellIOError("selection-token publication binding differs")
        if result.system_id in {"C2", "C3", "T0", "A0", "A1", "A2"} and (
            token.alpha != result.alpha
            or token.lambda_ != result.lambda_
            or token.candidate_id != result.candidate_id
        ):
            raise OraclePairCellIOError("selected candidate differs from pair result")
        if result.system_id == "F2" and (
            token.alpha != result.alpha
            or token.lambda_ != result.lambda_
            or result.selection_token_sha256 != token.sha256
        ):
            raise OraclePairCellIOError("F2 token reuse differs")
        if result.system_id in {"F0", "F1"} and (
            result.selection_token_sha256 != token.sha256
        ):
            raise OraclePairCellIOError("control token reuse differs")
    elif scope[0] == "outer" and result.system_id in {
        "C2",
        "C3",
        "T0",
        "F0",
        "F1",
        "F2",
        "A0",
        "A1",
        "A2",
    }:
        raise OraclePairCellIOError("outer learned publication lacks selection token")
    expected_candidate = candidate_id(
        result.system_id,
        result.alpha,
        result.lambda_,
        selection_token_sha256=result.selection_token_sha256,
        upstream_candidate_receipt_sha256=result.upstream_candidate_receipt_sha256,
    )
    if result.candidate_id != expected_candidate:
        raise OraclePairCellIOError("pair candidate identity differs")
    stage, repeat, outer, inner = scope
    expected_cell = cell_id(
        stage,
        repeat,
        outer,
        inner,
        result.system_id,
        expected_candidate,
        "all",
        alpha=result.alpha,
        lambda_=result.lambda_,
        selection_token_sha256=result.selection_token_sha256,
        upstream_candidate_receipt_sha256=result.upstream_candidate_receipt_sha256,
    )
    if result.cell_id != expected_cell:
        raise OraclePairCellIOError("pair cell identity differs")
    expected_fragment = fragment_id(
        stage,
        repeat,
        outer,
        inner,
        result.system_id,
        expected_candidate,
        "all",
        expected_cell,
        selection_token_sha256=result.selection_token_sha256,
        upstream_candidate_receipt_sha256=result.upstream_candidate_receipt_sha256,
    )
    if result.fragment_id != expected_fragment:
        raise OraclePairCellIOError("pair fragment identity differs")
    expected_accounting = _expected_pair_accounting(
        result.system_id,
        len(target.training_points)
        if isinstance(target, OracleCellTargetCapability)
        else 0,
        len(target.training_pairs),
        sum(
            row["anchor_point_available"] == "true"
            for row in target.episode_anchor_contexts
        )
        if isinstance(target, OracleCellTargetCapability)
        else 0,
    )
    if dict(result.accounting) != expected_accounting:
        raise OraclePairCellIOError("pair system accounting differs")
    token_binding: dict[str, Any] | None = None
    if token is not None:
        token_binding = {
            "sha256": token.sha256,
            "system_id": token.system_id,
            "candidate_id": token.candidate_id,
            "candidate_receipt_sha256": token.candidate_receipt_sha256,
            "scorer_receipt_sha256": token.scorer_receipt_sha256,
        }
    g0_receipts: str | list[str]
    if len(g0_manifest_sha256) == 1:
        g0_receipts = g0_manifest_sha256[0]
    else:
        g0_receipts = list(g0_manifest_sha256)
    return publish_pair_cell(
        output_root,
        result,
        scope={
            "stage": stage,
            "repeat": repeat,
            "outer_fold": outer,
            "inner_fold": "" if inner is None else inner,
        },
        capability_binding={
            "model_public_manifest_sha256": model_public_manifest_sha256,
            "target_manifest_sha256": target_manifest_sha256,
            "target_kind": target_kind,
            "g0_manifest_sha256": g0_receipts,
            "system_id": result.system_id,
            "source_bundle_binding": source_bundle_binding,
            "selection_token": token_binding,
        },
        runner_source_sha256=runner_source_sha256,
        g0_bindings=g0_bindings,
        runtime=runtime,
    )


def publish_pair_cell(
    output_root: Path,
    result: PairCellResult,
    *,
    scope: Mapping[str, Any],
    capability_binding: Mapping[str, Any],
    runner_source_sha256: str | None = None,
    g0_bindings: Sequence[Mapping[str, Any]] | None = None,
    runtime: Mapping[str, Any] | None = None,
) -> Path:
    """Publish exactly two read-only files using no-replace atomic promotion."""

    normalized_scope = _validate_scope_mapping(scope)
    observed_rows = _rows(result.fragment)
    if tuple(observed_rows) != result.rows:
        raise OraclePairCellIOError("pair result bytes and rows differ")
    if not observed_rows:
        raise OraclePairCellIOError("pair fragment is empty")
    _validate_pair_rows(observed_rows)
    _validate_pair_accounting(result.accounting)
    system_id = observed_rows[0]["system_id"]
    if any(row["system_id"] != system_id for row in observed_rows):
        raise OraclePairCellIOError("pair system identity differs")
    _digest(result.candidate_id, "pair candidate")
    _digest(result.fragment_id, "pair fragment")
    bound_system = capability_binding.get("system_id")
    if bound_system is not None and bound_system != system_id:
        raise OraclePairCellIOError("pair capability system differs")
    if any(row["candidate_id"] != result.candidate_id for row in observed_rows):
        raise OraclePairCellIOError("pair candidate identity differs")
    expected_inner = normalized_scope["inner_fold"]
    if any(
        row["repeat"] != str(normalized_scope["repeat"])
        or row["outer_fold"] != str(normalized_scope["outer_fold"])
        or row["inner_fold"] != ("" if expected_inner is None else str(expected_inner))
        for row in observed_rows
    ):
        raise OraclePairCellIOError("pair scope differs")
    keys = [
        (row["episode_id"], row["query_molecule_id"], row["query_rank"])
        for row in observed_rows
    ]
    if len(keys) != len(set(keys)):
        raise OraclePairCellIOError("pair prediction keys are duplicated")
    if output_root.exists() or output_root.is_symlink():
        raise OraclePairCellIOError("pair output already exists")
    parent = output_root.parent
    if ".." in parent.parts or any(
        path.is_symlink() for path in (parent, *parent.parents)
    ):
        raise OraclePairCellIOError("pair output ancestry differs")
    parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".r5c-pair-", dir=parent))
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.r5c_private_prediction_fragment.v1",
        "status": "R5_ORACLE_PAIR_CELL_COMPLETE",
        "contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": _optional_digest(
            runner_source_sha256, "pair runner source"
        ),
        "scope": {
            "stage": normalized_scope["stage"],
            "repeat": normalized_scope["repeat"],
            "outer_fold": normalized_scope["outer_fold"],
            "inner_fold": "" if expected_inner is None else expected_inner,
        },
        "system_id": result.rows[0]["system_id"] if result.rows else "",
        "candidate_id": result.candidate_id,
        "cell_id": result.cell_id,
        "fragment_id": result.fragment_id,
        "capability_binding": _plain_json(capability_binding),
        "g0_bindings": _g0_binding_records(g0_bindings or ()),
        "runtime": _plain_json(runtime or {}),
        "operation_accounting": dict(result.accounting),
        "prediction_fragment": {
            "path": "prediction_fragment.csv",
            "sha256": sha256(result.fragment).hexdigest(),
            "bytes": len(result.fragment),
            "rows": len(result.rows),
            "columns": list(FRAGMENT_COLUMNS),
        },
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
    payloads = {
        "prediction_fragment.csv": result.fragment,
        "manifest.json": _json_bytes(manifest),
    }
    try:
        for name, data in payloads.items():
            with (stage / name).open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            (stage / name).chmod(0o444)
        stage.chmod(0o555)
        directory_fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        _reopen_output(stage, payloads)
        _rename_noreplace(stage, output_root)
        try:
            parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
        except OSError:
            # Promotion is already complete. Parent durability is best-effort
            # and cannot retroactively invalidate immutable published bytes.
            pass
    except Exception:
        if stage.exists():
            for path in stage.iterdir():
                path.chmod(0o644)
            stage.chmod(0o755)
            for path in stage.iterdir():
                path.unlink()
            stage.rmdir()
        raise
    return output_root


def _rows(data: bytes, columns: Sequence[str] = G0_COLUMNS) -> list[dict[str, str]]:
    if not data.endswith(b"\n") or b"\r" in data:
        raise OraclePairCellIOError("G0 CSV line endings differ")
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True)
        if next(reader, None) != list(columns):
            raise OraclePairCellIOError("G0 columns differ")
        rows = [dict(zip(columns, values, strict=True)) for values in reader]
    except (UnicodeDecodeError, csv.Error) as exc:
        raise OraclePairCellIOError("G0 CSV is invalid") from exc
    if "episode_id" in columns:
        try:
            ordered = sorted(
                rows, key=lambda row: (row["episode_id"], int(row["query_rank"]))
            )
        except (KeyError, ValueError) as exc:
            raise OraclePairCellIOError("G0 query rank differs") from exc
        if rows != ordered:
            raise OraclePairCellIOError("G0 row order differs")
    return rows


def _validate_pair_rows(rows: Sequence[Mapping[str, str]]) -> None:
    systems = {"C0", "C1", "C2", "C3", "T0", "F0", "F1", "F2", "A0", "A1", "A2"}
    sources = {"G0", "LOCAL", "C0", "C1", "F0", "F1"}
    for row in rows:
        system = row["system_id"]
        source = row["prediction_source"]
        if system not in systems or source not in sources:
            raise OraclePairCellIOError("pair source vocabulary differs")
        _digest(row["candidate_id"], "pair candidate")
        value = _finite(row["prediction"], "pair prediction")
        if format(value, ".17g") != row["prediction"]:
            raise OraclePairCellIOError("pair prediction serialization differs")
        local = row["local_available"]
        if local not in {"true", "false"}:
            raise OraclePairCellIOError("pair local-availability token differs")
        if (local == "false") != (source == "G0"):
            raise OraclePairCellIOError("pair fallback source differs")
        if local == "true" and source not in {"LOCAL", "C0", "C1", "F0", "F1"}:
            raise OraclePairCellIOError("pair local source differs")
        for name in ("exact_support_components", "class_support_components"):
            try:
                support = int(row[name])
            except (KeyError, ValueError) as exc:
                raise OraclePairCellIOError("pair support count differs") from exc
            if support < 0 or str(support) != row[name]:
                raise OraclePairCellIOError("pair support count differs")


def _validate_pair_accounting(value: Mapping[str, int]) -> None:
    if set(value) != set(ACCOUNTING_FIELDS) or any(
        type(item) is not int or item < 0 for item in value.values()
    ):
        raise OraclePairCellIOError("pair accounting differs")
    if value["predictions_frozen"] != 0 or any(
        value[name] for name in ACCOUNTING_FIELDS[8:]
    ):
        raise OraclePairCellIOError("pair accounting grants forbidden operation")


def _expected_pair_accounting(
    system_id: str, point_rows: int, pair_rows: int, anchor_rows: int
) -> dict[str, int]:
    if any(
        type(value) is not int or value < 0
        for value in (point_rows, pair_rows, anchor_rows)
    ):
        raise OraclePairCellIOError("pair accounting source counts differ")
    expected = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    if system_id == "C0":
        expected["direct_target_values_parsed"] = anchor_rows
    elif system_id == "C1":
        expected["direct_target_values_parsed"] = point_rows + anchor_rows
    elif system_id == "C3":
        expected["direct_target_values_parsed"] = pair_rows
    elif system_id in {"F0", "F1"}:
        pass
    else:
        expected["direct_target_values_parsed"] = point_rows + pair_rows + anchor_rows
    if system_id not in {"F0", "F1", "C3"}:
        expected["anchor_labels_exposed_to_models"] = anchor_rows
    if system_id in {"C2", "A2", "C3", "T0", "F2"}:
        expected["ridge_model_fits"] = 1
    if system_id in {"A0", "A1", "C3", "T0", "F2"}:
        expected["hierarchy_fits"] = 1
    return expected


def _validate_manifest(
    manifest: Mapping[str, Any], scope: tuple[str, int, int, int | None]
) -> None:
    if (
        manifest.get("schema_version")
        != "cypshift.openadmet_cyp_2026.r5c_g0_prediction_fragment.v1"
    ):
        raise OraclePairCellIOError("G0 schema differs")
    if manifest.get("status") not in {
        "R5_ORACLE_G0_EPISODE_COMPLETE",
        "R5_ORACLE_PAIR_CELL_COMPLETE",
    }:
        raise OraclePairCellIOError("G0 status differs")
    if manifest.get("contract_sha256") != CONTRACT_SHA256:
        raise OraclePairCellIOError("G0 contract differs")
    _digest(manifest.get("candidate_id"), "G0 candidate")
    accounting = manifest.get("operation_accounting")
    if (
        not isinstance(accounting, Mapping)
        or set(accounting) != set(ACCOUNTING_FIELDS)
        or any(type(value) is not int or value < 0 for value in accounting.values())
    ):
        raise OraclePairCellIOError("G0 accounting differs")
    if any(accounting[name] for name in ACCOUNTING_FIELDS[8:]):
        raise OraclePairCellIOError("G0 forbidden operation")
    scope_value = manifest.get("scope")
    if not isinstance(scope_value, Mapping):
        raise OraclePairCellIOError("G0 scope differs")
    stage, repeat, outer, inner = scope
    expected = {
        "stage": stage,
        "repeat": repeat,
        "outer_fold": outer,
        "inner_fold": "" if inner is None else inner,
    }
    if dict(scope_value) != expected:
        raise OraclePairCellIOError("G0 scope differs")


def _validate_legacy_manifest(
    manifest: Mapping[str, Any],
    scope: tuple[str, int, int, int | None],
) -> None:
    if manifest.get("status") != "R5_ORACLE_G0_EPISODE_COMPLETE":
        raise OraclePairCellIOError("legacy G0 status differs")
    if manifest.get("contract_sha256") not in {
        CONTRACT_SHA256,
        "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623",
    }:
        raise OraclePairCellIOError("legacy G0 contract differs")
    candidate = manifest.get("candidate_id")
    if candidate is not None:
        _digest(candidate, "legacy G0 candidate")
    scope_value = manifest.get("scope")
    if not isinstance(scope_value, Mapping):
        raise OraclePairCellIOError("legacy G0 scope differs")
    stage, repeat, outer, inner = scope
    try:
        observed_repeat = int(scope_value.get("repeat", -1))
    except (TypeError, ValueError) as exc:
        raise OraclePairCellIOError("legacy G0 scope differs") from exc
    if scope_value.get("stage") != stage or observed_repeat != repeat:
        raise OraclePairCellIOError("legacy G0 scope differs")
    current_outer = scope_value.get(
        "current_outer_validation_fold", scope_value.get("outer_fold")
    )
    try:
        observed_outer = int(current_outer)
    except (TypeError, ValueError) as exc:
        raise OraclePairCellIOError("legacy G0 current outer scope differs") from exc
    if observed_outer != outer:
        raise OraclePairCellIOError("legacy G0 current outer scope differs")
    episode_outer_value = scope_value.get("episode_outer_fold")
    inner_value = scope_value.get("inner_fold")
    if not isinstance(episode_outer_value, (str, int)):
        raise OraclePairCellIOError("legacy G0 episode outer scope differs")
    try:
        episode_outer = int(episode_outer_value)
    except (TypeError, ValueError) as exc:
        raise OraclePairCellIOError("legacy G0 episode outer scope differs") from exc
    if stage == "outer":
        if episode_outer != outer or inner_value != "":
            raise OraclePairCellIOError("legacy G0 outer scope differs")
    elif episode_outer == outer or inner_value != inner:
        raise OraclePairCellIOError("legacy G0 inner scope differs")
    episode = manifest.get("episode")
    if not isinstance(episode, Mapping) or not isinstance(
        episode.get("episode_id"), str
    ):
        raise OraclePairCellIOError("legacy G0 episode identity differs")
    accounting = manifest.get("operation_accounting")
    if not isinstance(accounting, Mapping) or any(
        type(value) is not int or value < 0 for value in accounting.values()
    ):
        raise OraclePairCellIOError("legacy G0 accounting differs")
    if any(accounting.get(name, 0) for name in ACCOUNTING_FIELDS[8:]):
        raise OraclePairCellIOError("legacy G0 forbidden operation")


def _validate_scope(
    scope: tuple[Literal["inner", "outer"], int, int, int | None],
) -> None:
    stage, repeat, outer, inner = scope
    if (
        stage not in {"inner", "outer"}
        or type(repeat) is not int
        or repeat not in range(3)
        or type(outer) is not int
        or outer not in range(5)
        or (stage == "outer" and inner is not None)
        or (stage == "inner" and (type(inner) is not int or inner not in range(4)))
    ):
        raise OraclePairCellIOError("scope differs")


def _validate_scope_mapping(scope: Mapping[str, Any]) -> dict[str, Any]:
    if set(scope) != {"stage", "repeat", "outer_fold", "inner_fold"}:
        raise OraclePairCellIOError("scope differs")
    stage = scope["stage"]
    repeat = scope["repeat"]
    outer = scope["outer_fold"]
    inner_value = scope["inner_fold"]
    if stage == "outer":
        inner: int | None = None if inner_value == "" else inner_value
    elif stage == "inner":
        inner = inner_value
    else:
        inner = None
    _validate_scope((stage, repeat, outer, inner))
    return {"stage": stage, "repeat": repeat, "outer_fold": outer, "inner_fold": inner}


def _open_root(path: Path) -> int:
    if ".." in path.parts:
        raise OraclePairCellIOError("G0 root path differs")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        fd = os.open("/" if path.is_absolute() else ".", flags)
    except OSError as exc:
        raise OraclePairCellIOError("cannot open G0 ancestry") from exc
    try:
        for part in path.parts:
            if part in {"/", ".", ""}:
                continue
            try:
                next_fd = os.open(part, flags, dir_fd=fd)
            except OSError as exc:
                raise OraclePairCellIOError("cannot open G0 ancestry") from exc
            os.close(fd)
            fd = next_fd
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OraclePairCellIOError("G0 root is not a directory")
        return fd
    except Exception:
        os.close(fd)
        raise


def _read_at(root_fd: int, name: str) -> bytes:
    try:
        fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=root_fd)
    except OSError as exc:
        raise OraclePairCellIOError(f"cannot open G0 file: {name}") from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise OraclePairCellIOError(f"G0 file is not regular: {name}")
        chunks: list[bytes] = []
        while block := os.read(fd, 1024 * 1024):
            chunks.append(block)
        result = b"".join(chunks)
        after = os.fstat(fd)
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if before_identity != after_identity or len(result) != before.st_size:
            raise OraclePairCellIOError(f"G0 file changed: {name}")
        return result
    finally:
        os.close(fd)


def _rename_noreplace(source: Path, destination: Path) -> None:
    import ctypes
    import errno

    libc = ctypes.CDLL(None, use_errno=True)
    function = getattr(libc, "renameat2", None)
    if function is None:
        raise OraclePairCellIOError("renameat2 unavailable")
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    function.restype = ctypes.c_int
    if function(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        raise OraclePairCellIOError(
            "pair output exists" if error == errno.EEXIST else os.strerror(error)
        )


def _reopen_output(root: Path, payloads: Mapping[str, bytes]) -> None:
    fd = _open_root(root)
    try:
        if set(os.listdir(fd)) != set(payloads):
            raise OraclePairCellIOError("published pair file set differs")
        for name, expected in payloads.items():
            if _read_at(fd, name) != expected:
                raise OraclePairCellIOError(f"published pair bytes differ: {name}")
    finally:
        os.close(fd)


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        + b"\n"
    )


def _json(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OraclePairCellIOError(f"{label} is invalid") from exc
    if not isinstance(value, dict) or _json_bytes(value) != data:
        raise OraclePairCellIOError(f"{label} is not canonical")
    return value


def _g0_binding_records(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for record in records:
        binding = dict(record)
        required = {
            "binding_sha256",
            "g0_manifest_sha256",
            "g0_prediction_fragment_sha256",
            "episode_id",
            "episode_target_manifest_sha256",
            "r3c_parameter_record_sha256",
            "g0_source_bundle_sha256",
        }
        if set(binding) != required:
            raise OraclePairCellIOError("G0 binding fields differ")
        for key in required - {"episode_id"}:
            _digest(binding[key], f"G0 binding {key}")
        if not isinstance(binding["episode_id"], str) or not binding["episode_id"]:
            raise OraclePairCellIOError("G0 binding episode identity differs")
        normalized.append(binding)
    return normalized


def _derive_g0_binding_records(
    fragments: Sequence[G0FragmentRoot],
    *,
    model_manifest_sha256: str,
    scope: tuple[Literal["inner", "outer"], int, int, int | None],
) -> tuple[dict[str, Any], ...]:
    stage, repeat, outer, inner = scope
    records: list[dict[str, Any]] = []
    for fragment in fragments:
        manifest = fragment.manifest
        episode = manifest.get("episode")
        prediction = manifest.get("prediction_fragment")
        parameter = manifest.get("r3c_parameter_source")
        if not all(
            isinstance(value, Mapping) for value in (episode, prediction, parameter)
        ):
            raise OraclePairCellIOError("G0 binding source metadata differs")
        episode_map = cast(Mapping[str, Any], episode)
        prediction_map = cast(Mapping[str, Any], prediction)
        parameter_map = cast(Mapping[str, Any], parameter)
        episode_id = episode_map.get("episode_id")
        episode_target = manifest.get("episode_target_manifest_sha256")
        parameter_receipt = parameter_map.get("parameter_record_sha256")
        source_bundle = manifest.get("g0_source_bundle_sha256")
        fragment_receipt = prediction_map.get("sha256")
        g0_cell_id = manifest.get("cell_id")
        for value, label in (
            (episode_id, "G0 episode identity"),
            (episode_target, "G0 episode target"),
            (parameter_receipt, "G0 parameter record"),
            (source_bundle, "G0 source bundle"),
            (fragment_receipt, "G0 prediction fragment"),
            (g0_cell_id, "G0 cell identity"),
        ):
            _digest(value, label)
        binding_sha256 = sha256(
            json.dumps(
                [
                    CONTRACT_SHA256,
                    model_manifest_sha256,
                    episode_target,
                    stage,
                    repeat,
                    outer,
                    -1 if inner is None else inner,
                    episode_id,
                    g0_cell_id,
                    parameter_receipt,
                    source_bundle,
                ],
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        records.append(
            {
                "binding_sha256": binding_sha256,
                "g0_manifest_sha256": fragment.manifest_sha256,
                "g0_prediction_fragment_sha256": fragment_receipt,
                "episode_id": episode_id,
                "episode_target_manifest_sha256": episode_target,
                "r3c_parameter_record_sha256": parameter_receipt,
                "g0_source_bundle_sha256": source_bundle,
            }
        )
    return tuple(records)


def _validate_selection_token_object(token: SelectionToken | None) -> None:
    if token is None:
        return
    payload = {
        "schema_version": "cypshift.openadmet_cyp_2026.r5c_score_free_selection_token.v1",
        "contract_sha256": CONTRACT_SHA256,
        "system_id": token.system_id,
        "repeat": token.repeat,
        "outer_fold": token.outer_fold,
        "candidate_id": token.candidate_id,
        "alpha": token.alpha,
        "lambda": token.lambda_,
        "candidate_receipt_sha256": token.candidate_receipt_sha256,
        "scorer_receipt_sha256": token.scorer_receipt_sha256,
    }
    if sha256(_json_bytes(payload)).hexdigest() != token.sha256:
        raise OraclePairCellIOError("selection-token object receipt differs")


def _validate_g0_publication_material(
    result: PairCellResult,
    fragments: Sequence[G0FragmentRoot],
    bindings: Sequence[Mapping[str, Any]],
) -> None:
    fragment_episodes = _validate_g0_fragment_binding_tuple(fragments, bindings)
    result_episodes = {row["episode_id"] for row in result.rows}
    if set(fragment_episodes) != result_episodes:
        raise OraclePairCellIOError("G0 publication episode set differs")


def _validate_g0_fragment_binding_tuple(
    fragments: Sequence[G0FragmentRoot],
    bindings: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    normalized = _g0_binding_records(bindings)
    if len(fragments) != len(normalized):
        raise OraclePairCellIOError("G0 publication tuple length differs")
    fragment_episodes: list[str] = []
    for fragment, binding in zip(fragments, normalized, strict=True):
        episode = fragment.manifest.get("episode")
        if not isinstance(episode, Mapping):
            raise OraclePairCellIOError("G0 publication episode differs")
        episode_id = episode.get("episode_id")
        if (
            not isinstance(episode_id, str)
            or not episode_id
            or binding["episode_id"] != episode_id
            or binding["g0_manifest_sha256"] != fragment.manifest_sha256
        ):
            raise OraclePairCellIOError("G0 publication binding differs")
        fragment_episodes.append(episode_id)
    if len(fragment_episodes) != len(set(fragment_episodes)):
        raise OraclePairCellIOError("G0 publication episode set differs")
    return tuple(fragment_episodes)


def _validate_source_bundle_binding(binding: Mapping[str, Any]) -> None:
    required = {
        "manifest_receipt",
        "schema_version",
        "contract_sha256",
        "parent_receipts",
        "input_receipts",
        "source_receipts",
    }
    if set(binding) != required or binding.get("contract_sha256") != (
        "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
    ):
        raise OraclePairCellIOError("source-bundle binding fields differ")
    manifest = binding.get("manifest_receipt")
    if (
        not isinstance(manifest, Mapping)
        or set(manifest) != {"sha256", "bytes"}
        or type(manifest.get("bytes")) is not int
        or manifest["bytes"] < 1
    ):
        raise OraclePairCellIOError("source manifest receipt differs")
    _digest(manifest.get("sha256"), "source manifest")
    parents = binding.get("parent_receipts")
    inputs = binding.get("input_receipts")
    sources = binding.get("source_receipts")
    if not all(
        isinstance(value, Mapping) and value for value in (parents, inputs, sources)
    ):
        raise OraclePairCellIOError("source-bundle receipts differ")
    for name, receipt in cast(Mapping[str, Any], parents).items():
        if not isinstance(name, str) or not name:
            raise OraclePairCellIOError("source parent name differs")
        _digest(receipt, f"source parent: {name}")
    for label, receipts in (("input", inputs), ("source", sources)):
        for name, receipt in cast(Mapping[str, Any], receipts).items():
            if (
                not isinstance(name, str)
                or not name
                or not isinstance(receipt, Mapping)
                or set(receipt) != {"sha256", "bytes"}
                or type(receipt.get("bytes")) is not int
                or receipt["bytes"] < 1
            ):
                raise OraclePairCellIOError(f"{label} receipt differs")
            _digest(receipt.get("sha256"), f"{label} receipt: {name}")
    required_geometry = {
        "campaign_episodes_public.csv",
        "feature_rows.csv",
        "transformation_pairs.csv",
        "episode_transformations.csv",
    }
    bound_names = set(cast(Mapping[str, Any], sources)) | set(
        cast(Mapping[str, Any], inputs)
    )
    if not required_geometry <= bound_names:
        raise OraclePairCellIOError("public/geometry source binding differs")


def _plain_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    return value


def _digest(value: object, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise OraclePairCellIOError(f"{label} is not SHA-256")


def _optional_digest(value: str | None, label: str) -> str:
    if value is None:
        return ""
    _digest(value, label)
    return value


def _finite(value: str, label: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise OraclePairCellIOError(f"{label} is not finite") from exc
    if not math.isfinite(result):
        raise OraclePairCellIOError(f"{label} is not finite")
    return result


__all__ = [
    "ACCOUNTING_FIELDS",
    "CONTRACT_SHA256",
    "G0FragmentRoot",
    "OraclePairCellIOError",
    "SelectionToken",
    "TOKEN_FILE",
    "load_g0_fragments",
    "load_g0_predictions",
    "load_selection_token",
    "publish_authenticated_pair_cell",
    "publish_pair_cell",
]

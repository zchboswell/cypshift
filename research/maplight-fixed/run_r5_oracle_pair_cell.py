#!/usr/bin/env python3
"""Run one receipt-bound R5C pair system cell in a fresh root process."""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import io
import json
import math
import platform
import sys
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, cast

from cypshift.openadmet_oracle_cell_io import (
    OracleC3TargetCapability,
    OracleCellTargetCapability,
    load_oracle_cell_capability,
)
from cypshift.openadmet_oracle_pair_cell import (
    candidate_id,
    cell_id,
    run_pair_cell,
    run_shared_outer_t0,
)
from cypshift.openadmet_oracle_pair_cell_io import (
    ACCOUNTING_FIELDS,
    CONTRACT_SHA256,
    G0FragmentRoot,
    SelectionToken,
    load_g0_fragments,
    load_selection_token,
    publish_authenticated_pair_cell,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILES = (
    Path(__file__),
    ROOT / "src/cypshift/audit.py",
    ROOT / "src/cypshift/chemistry.py",
    ROOT / "src/cypshift/openadmet_cyp.py",
    ROOT / "src/cypshift/openadmet_oracle_cell_io.py",
    ROOT / "src/cypshift/openadmet_oracle_cell_validation.py",
    ROOT / "src/cypshift/openadmet_oracle_controls.py",
    ROOT / "src/cypshift/openadmet_oracle_geometry_validation.py",
    ROOT / "src/cypshift/openadmet_oracle_models.py",
    ROOT / "src/cypshift/openadmet_oracle_pair_cell.py",
    ROOT / "src/cypshift/openadmet_oracle_pair_cell_io.py",
    ROOT / "src/cypshift/openadmet_oracle_projection.py",
    ROOT / "src/cypshift/openadmet_oracle_validation.py",
    ROOT / "src/cypshift/openadmet_topology.py",
    ROOT / "src/cypshift/openadmet_transformation_compiler.py",
    ROOT / "src/cypshift/openadmet_transformation_coverage.py",
    ROOT / "src/cypshift/openadmet_transformation_io.py",
    ROOT / "src/cypshift/openadmet_transformations.py",
    ROOT / "src/cypshift/openadmet_transformation_mmp.py",
    ROOT / "src/cypshift/openadmet_transformation_projection.py",
    ROOT / "src/cypshift/openadmet_transformation_serialization.py",
    ROOT / "src/cypshift/openadmet_transformation_stereo.py",
    ROOT / "src/cypshift/openadmet_transformation_support.py",
    ROOT / "src/cypshift/openadmet_transformation_types.py",
    ROOT / "src/cypshift/openadmet_validation.py",
    ROOT / "src/cypshift/openadmet_validation_contract.py",
    ROOT / "src/cypshift/schema.py",
)
ROOT_LOCK = ROOT / "uv.lock"
ROOT_LOCK_SHA256 = "33d9382256de7992ce9ff7a7edc125d4771546a25ef3be5f1160627846d2c9b6"
OUTER_LEARNED = frozenset({"C2", "C3", "T0", "F2", "A0", "A1", "A2"})
G0_PARAMETER_RECORD_SHA256 = (
    "0c912e0d06d0d24d58bdc0529d6b14d1706d6a933445885be881f95ba3678cb9"
)
G0_PARAMETER_SHA256 = "c56235a54a883a9a4488f1c8779f9013dae777af0f99cd92c9da1c4f51e61757"
G0_PARENT_CONTRACT_SHA256 = (
    "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
)
G0_SOURCE_FILES = (
    ROOT / "research/maplight-fixed/r5_oracle_g0_io.py",
    ROOT / "research/maplight-fixed/run_r5_oracle_g0.py",
)
G0_PUBLIC_COLUMNS = (
    "episode_id",
    "episode_policy_id",
    "repeat",
    "outer_fold",
    "outer_group_id",
    "anchor_molecule_id",
    "query_molecule_id",
    "query_rank",
)


class PairCellRunnerError(RuntimeError):
    """A pair-cell receipt, provenance, or runtime invariant failed."""


def _compact_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def _source_bundle_sha() -> str:
    return sha256(
        "".join(
            f"{path.relative_to(ROOT).as_posix()}|"
            f"{sha256(path.read_bytes()).hexdigest()}\n"
            for path in sorted(SOURCE_FILES, key=lambda item: item.relative_to(ROOT))
        ).encode("utf-8")
    ).hexdigest()


def _file_bundle(paths: Sequence[Path]) -> tuple[str, dict[str, str]]:
    receipts = {
        path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix())
    }
    payload = "".join(f"{name}|{digest}\n" for name, digest in receipts.items())
    return sha256(payload.encode()).hexdigest(), receipts


def _public_receipt(rows: Sequence[Mapping[str, str]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=list(G0_PUBLIC_COLUMNS),
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    writer.writerows(rows)
    return sha256(stream.getvalue().encode()).hexdigest()


def _runtime() -> dict[str, str]:
    runtime = {
        "platform": f"{platform.system()} {platform.machine()} CPU",
        "python_version": platform.python_version(),
        "numpy_version": importlib.metadata.version("numpy"),
        "sklearn_version": importlib.metadata.version("scikit-learn"),
        "rdkit_version": importlib.metadata.version("rdkit"),
        "uv_lock_sha256": sha256(ROOT_LOCK.read_bytes()).hexdigest(),
    }
    expected = {
        "platform": "Linux x86_64 CPU",
        "python_version": "3.12.3",
        "numpy_version": "2.5.2",
        "sklearn_version": "1.9.0",
        "rdkit_version": "2026.3.5",
        "uv_lock_sha256": ROOT_LOCK_SHA256,
    }
    if runtime != expected:
        raise PairCellRunnerError(f"pair runner runtime differs: {runtime}")
    return runtime


def _digest(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise PairCellRunnerError(f"{label} differs")
    return value


def _validate_source_bundle(expected_source_bundle_sha256: str) -> str:
    observed = _source_bundle_sha()
    if _digest(expected_source_bundle_sha256, "pair runner source bundle receipt") != (
        observed
    ):
        raise PairCellRunnerError("pair runner source bundle receipt differs")
    return observed


def _episode_ids(
    capability_target: OracleCellTargetCapability | OracleC3TargetCapability,
) -> set[str]:
    if isinstance(capability_target, OracleCellTargetCapability):
        return {row["episode_id"] for row in capability_target.episode_anchor_contexts}
    return {row["episode_id"] for row in capability_target.global_anchor_contexts}


def _g0_binding_records(
    fragments: Sequence[G0FragmentRoot],
    *,
    model_manifest_sha256: str,
    stage: Literal["inner", "outer"],
    repeat: int,
    outer_fold: int,
    inner_fold: int | None,
    source_cell_target_manifest_sha256: str,
    public_queries: Sequence[dict[str, str] | Mapping[str, str]],
) -> list[dict[str, str]]:
    expected_public = {
        (row["episode_id"], row["query_molecule_id"]): row for row in public_queries
    }
    g0_source_sha, g0_source_receipts = _file_bundle(G0_SOURCE_FILES)
    records: list[dict[str, str]] = []
    for fragment in fragments:
        if not fragment.legacy:
            raise PairCellRunnerError("G0 must use the locked 13-column fragment")
        manifest = fragment.manifest
        _validate_locked_g0_manifest(
            fragment,
            model_manifest_sha256=model_manifest_sha256,
            source_cell_target_manifest_sha256=source_cell_target_manifest_sha256,
            stage=stage,
            repeat=repeat,
            outer_fold=outer_fold,
            inner_fold=inner_fold,
            public_queries=expected_public,
            g0_source_sha256=g0_source_sha,
            g0_source_receipts=g0_source_receipts,
        )
        if manifest.get("model_public_manifest_sha256") != model_manifest_sha256:
            raise PairCellRunnerError("G0 model-public manifest differs")
        episode = cast(dict[str, object], manifest.get("episode"))
        prediction_fragment = cast(
            dict[str, object], manifest.get("prediction_fragment")
        )
        parameter_source = cast(dict[str, object], manifest.get("r3c_parameter_source"))
        episode_id = _digest(episode.get("episode_id"), "G0 episode identity")
        episode_target_manifest_sha256 = _digest(
            manifest.get("episode_target_manifest_sha256"),
            "G0 episode-target manifest",
        )
        parameter_record_sha256 = _digest(
            parameter_source.get("parameter_record_sha256"),
            "G0 parameter record",
        )
        g0_source_bundle_sha256 = _digest(
            manifest.get("g0_source_bundle_sha256"), "G0 source bundle"
        )
        fragment_sha256 = _digest(
            prediction_fragment.get("sha256"), "G0 prediction fragment receipt"
        )
        g0_cell_id = _digest(manifest.get("cell_id"), "G0 cell identity")
        binding_sha256 = sha256(
            _compact_json(
                [
                    CONTRACT_SHA256,
                    model_manifest_sha256,
                    episode_target_manifest_sha256,
                    stage,
                    repeat,
                    outer_fold,
                    -1 if inner_fold is None else inner_fold,
                    episode_id,
                    g0_cell_id,
                    parameter_record_sha256,
                    g0_source_bundle_sha256,
                ]
            )
        ).hexdigest()
        records.append(
            {
                "binding_sha256": binding_sha256,
                "g0_manifest_sha256": fragment.manifest_sha256,
                "g0_prediction_fragment_sha256": fragment_sha256,
                "episode_id": episode_id,
                "episode_target_manifest_sha256": episode_target_manifest_sha256,
                "r3c_parameter_record_sha256": parameter_record_sha256,
                "g0_source_bundle_sha256": g0_source_bundle_sha256,
            }
        )
    return records


def _validate_locked_g0_manifest(
    fragment: G0FragmentRoot,
    *,
    model_manifest_sha256: str,
    source_cell_target_manifest_sha256: str,
    stage: Literal["inner", "outer"],
    repeat: int,
    outer_fold: int,
    inner_fold: int | None,
    public_queries: dict[tuple[str, str], Mapping[str, str]],
    g0_source_sha256: str,
    g0_source_receipts: Mapping[str, str],
) -> None:
    manifest = fragment.manifest
    episode = manifest.get("episode")
    if not isinstance(episode, dict):
        raise PairCellRunnerError("G0 episode metadata differs")
    episode_id = str(episode.get("episode_id", ""))
    rows = tuple(fragment.rows)
    public = {key: row for key, row in public_queries.items() if key[0] == episode_id}
    if not public or len(rows) != len(public):
        raise PairCellRunnerError("G0 public query population differs")
    public_rows = sorted(public.values(), key=lambda row: int(row["query_rank"]))
    candidate = candidate_id("G0", None, None)
    expected_cell = cell_id(
        stage, repeat, outer_fold, inner_fold, "G0", candidate, episode_id
    )
    trusted = manifest.get("trusted_episode_parent_receipts")
    parameter = manifest.get("r3c_parameter_source")
    counts = manifest.get("counts")
    accounting = manifest.get("operation_accounting")
    if not all(
        isinstance(value, dict) for value in (trusted, parameter, counts, accounting)
    ):
        raise PairCellRunnerError("G0 manifest metadata differs")
    trusted_map = cast(dict[str, Any], trusted)
    parameter_map = cast(dict[str, Any], parameter)
    counts_map = cast(dict[str, Any], counts)
    accounting_map = cast(dict[str, Any], accounting)
    source_cell = _digest(
        trusted_map.get("source_cell_target_manifest_sha256"),
        "G0 source cell target",
    )
    if source_cell != source_cell_target_manifest_sha256:
        raise PairCellRunnerError(
            f"G0 source cell target parent differs: {source_cell} != "
            f"{source_cell_target_manifest_sha256}"
        )
    expected_scope = {
        "stage": stage,
        "repeat": repeat,
        "current_outer_validation_fold": outer_fold,
        "inner_fold": "" if inner_fold is None else inner_fold,
        "episode_outer_fold": int(next(iter(public.values()))["outer_fold"]),
    }
    expected_runtime = {
        "platform": "Linux x86_64 CPU",
        "python_version": "3.10.13",
        "numpy_version": "1.25.2",
        "catboost_version": "1.2.1",
        "uv_lock_sha256": "99e72821b69d9bb943a6e32adc7e0dec0e46c6d32df090241d4fb9296a4195d8",
        "cpu_only": True,
        "max_threads": 16,
    }
    if (
        manifest.get("contract_sha256") != CONTRACT_SHA256
        or manifest.get("parent_contract_sha256") != G0_PARENT_CONTRACT_SHA256
        or manifest.get("model_public_manifest_sha256") != model_manifest_sha256
        or manifest.get("g0_source_bundle_sha256") != g0_source_sha256
        or manifest.get("g0_source_file_receipts") != dict(g0_source_receipts)
        or manifest.get("scope") != expected_scope
        or manifest.get("system_id") != "G0"
        or manifest.get("source_system_id") != "TRACE-G0-MAPL-FIXED"
        or manifest.get("candidate_id") != candidate
        or manifest.get("cell_id") != expected_cell
        or manifest.get("runtime") != expected_runtime
        or parameter_map.get("parameter_record_sha256") != G0_PARAMETER_RECORD_SHA256
        or manifest.get("public_query_receipt_sha256")
        != episode.get("query_rows_sha256")
        or episode.get("query_rows_sha256") != _public_receipt(public_rows)
        or episode.get("query_rows") != len(public_rows)
    ):
        raise PairCellRunnerError("G0 manifest binding differs")
    resolved = manifest.get("resolved_catboost_parameters")
    resolved_bytes = (
        json.dumps(resolved, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    if sha256(resolved_bytes).hexdigest() != G0_PARAMETER_SHA256:
        raise PairCellRunnerError("G0 resolved parameter receipt differs")
    anchor_rows = counts_map.get("anchor_rows")
    training_rows = counts_map.get("current_training_points")
    expected_accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    if type(anchor_rows) is int and type(training_rows) is int:
        expected_accounting["direct_target_values_parsed"] = training_rows + anchor_rows
        expected_accounting["anchor_labels_exposed_to_models"] = anchor_rows
        expected_accounting["maplight_model_fits"] = 1
    if (
        anchor_rows not in {0, 1}
        or type(training_rows) is not int
        or training_rows < 1
        or counts_map.get("fit_rows") != training_rows + anchor_rows
        or counts_map.get("query_rows") != len(rows)
        or accounting_map != expected_accounting
    ):
        raise PairCellRunnerError("G0 operation accounting differs")
    model_ids = {row["model_id"] for row in rows}
    split_ids = {row["split_id"] for row in rows}
    if len(model_ids) != 1 or len(split_ids) != 1:
        raise PairCellRunnerError("G0 model/split identity differs")
    for row in rows:
        key = (episode_id, row["molecule_id"])
        expected = public.get(key)
        if expected is None:
            raise PairCellRunnerError("G0 query identity differs")
        expected_inner = "" if inner_fold is None else str(inner_fold)
        if (
            row["endpoint"] != "CYP3A4"
            or row["component_id"] != expected["outer_group_id"]
            or row["repeat"] != str(repeat)
            or row["outer_fold"] != expected["outer_fold"]
            or row["inner_fold"] != expected_inner
            or row["scope"] != f"openadmet-oracle-{stage}-v1"
            or row["system_id"] != "TRACE-G0-MAPL-FIXED"
            or row["feature_spec_id"] != "maplight-fixed-stage-a-v1"
        ):
            raise PairCellRunnerError("G0 row provenance differs")
        for name in ("model_id", "split_id"):
            _digest(row[name], f"G0 {name}")
        for name in ("prediction", "applicability_score"):
            value = float(row[name])
            if not math.isfinite(value) or format(value, ".17g") != row[name]:
                raise PairCellRunnerError(f"G0 {name} differs")


def run(
    *,
    model_public_root: Path,
    target_root: Path,
    model_manifest_sha256: str,
    target_manifest_sha256: str,
    target_kind: Literal["cell-target", "c3-target"],
    system_id: str,
    alpha: float | None,
    lambda_: float | None,
    g0_root: Path | Sequence[Path],
    g0_manifest_sha256: str | Sequence[str],
    output_root: Path,
    expected_source_bundle_sha256: str,
    stage: Literal["inner", "outer"],
    repeat: int,
    outer_fold: int,
    inner_fold: int | None,
    selection_token_root: Path | None = None,
    selection_token_sha256: str | None = None,
    upstream_candidate_receipt_sha256: str | None = None,
    expected_g0_source_cell_target_manifest_sha256: str | None = None,
) -> Path:
    runner_source_sha256 = _validate_source_bundle(expected_source_bundle_sha256)
    locked_runtime = _runtime()
    scope = (stage, repeat, outer_fold, inner_fold)
    if target_kind == "c3-target":
        if expected_g0_source_cell_target_manifest_sha256 is None:
            raise PairCellRunnerError("C3 requires its measured source-cell parent")
        g0_source_cell_target_sha256 = _digest(
            expected_g0_source_cell_target_manifest_sha256,
            "C3 measured source-cell parent",
        )
    else:
        if expected_g0_source_cell_target_manifest_sha256 is not None:
            raise PairCellRunnerError("measured source-cell parent argument differs")
        g0_source_cell_target_sha256 = target_manifest_sha256
    if system_id in {"F0", "F1"}:
        raise PairCellRunnerError("F0/F1 require the shared outer T0 command")
    if system_id == "F2" and stage != "outer":
        raise PairCellRunnerError("F2 is outer-only")
    token: SelectionToken | None = None
    if stage == "outer" and system_id in OUTER_LEARNED:
        if selection_token_root is None or selection_token_sha256 is None:
            raise PairCellRunnerError("outer learned system requires a selection token")
        token = load_selection_token(
            selection_token_root,
            expected_sha256=selection_token_sha256,
            requested_system_id=system_id,
            repeat=repeat,
            outer_fold=outer_fold,
            alpha=alpha,
            lambda_=lambda_,
        )
    elif selection_token_root is not None or selection_token_sha256 is not None:
        raise PairCellRunnerError("selection token is forbidden for this cell")
    capability = load_oracle_cell_capability(
        model_public_root,
        target_root,
        expected_model_manifest_sha256=model_manifest_sha256,
        expected_target_manifest_sha256=target_manifest_sha256,
        system_id=system_id,
        target_kind=target_kind,
        expected_scope=scope,
    )
    episode_ids = _episode_ids(capability.target)
    public = [
        row
        for row in capability.model_public.public_queries
        if row["episode_id"] in episode_ids
    ]
    g0, g0_fragments = load_g0_fragments(
        g0_root,
        expected_manifest_sha256=g0_manifest_sha256,
        scope=scope,
        public_queries=public,
    )
    _g0_binding_records(
        g0_fragments,
        model_manifest_sha256=model_manifest_sha256,
        stage=stage,
        repeat=repeat,
        outer_fold=outer_fold,
        inner_fold=inner_fold,
        source_cell_target_manifest_sha256=g0_source_cell_target_sha256,
        public_queries=public,
    )
    result = run_pair_cell(
        capability,
        system_id=system_id,
        alpha=alpha,
        lambda_=lambda_,
        g0_predictions=g0,
        selection_token_sha256=(token.sha256 if system_id == "F2" and token else None),
        upstream_candidate_receipt_sha256=upstream_candidate_receipt_sha256,
    )
    return publish_authenticated_pair_cell(
        output_root,
        result,
        model_public_root=model_public_root,
        target_root=target_root,
        expected_model_manifest_sha256=model_manifest_sha256,
        expected_target_manifest_sha256=target_manifest_sha256,
        target_kind=target_kind,
        expected_scope=scope,
        g0_root=g0_root,
        expected_g0_manifest_sha256=g0_manifest_sha256,
        runner_source_sha256=runner_source_sha256,
        runtime=locked_runtime,
        selection_token_root=selection_token_root,
        expected_selection_token_sha256=selection_token_sha256,
        selected_alpha=alpha,
        selected_lambda=lambda_,
    )


def run_shared_t0(
    *,
    model_public_root: Path,
    target_root: Path,
    model_manifest_sha256: str,
    target_manifest_sha256: str,
    alpha: float,
    lambda_: float,
    g0_root: Path | Sequence[Path],
    g0_manifest_sha256: str | Sequence[str],
    t0_output_root: Path,
    f0_output_root: Path,
    f1_output_root: Path,
    expected_source_bundle_sha256: str,
    repeat: int,
    outer_fold: int,
    selection_token_root: Path,
    selection_token_sha256: str,
) -> tuple[Path, Path, Path]:
    """Fit one outer T0 process and publish T0/F0/F1 without reparsing target."""

    runner_source_sha256 = _validate_source_bundle(expected_source_bundle_sha256)
    locked_runtime = _runtime()
    token = load_selection_token(
        selection_token_root,
        expected_sha256=selection_token_sha256,
        requested_system_id="T0",
        repeat=repeat,
        outer_fold=outer_fold,
        alpha=alpha,
        lambda_=lambda_,
    )
    scope: tuple[Literal["outer"], int, int, None] = (
        "outer",
        repeat,
        outer_fold,
        None,
    )
    capability = load_oracle_cell_capability(
        model_public_root,
        target_root,
        expected_model_manifest_sha256=model_manifest_sha256,
        expected_target_manifest_sha256=target_manifest_sha256,
        system_id="T0",
        target_kind="cell-target",
        expected_scope=scope,
    )
    episode_ids = _episode_ids(capability.target)
    public = [
        row
        for row in capability.model_public.public_queries
        if row["episode_id"] in episode_ids
    ]
    g0, fragments = load_g0_fragments(
        g0_root,
        expected_manifest_sha256=g0_manifest_sha256,
        scope=scope,
        public_queries=public,
    )
    _g0_binding_records(
        fragments,
        model_manifest_sha256=model_manifest_sha256,
        stage="outer",
        repeat=repeat,
        outer_fold=outer_fold,
        inner_fold=None,
        source_cell_target_manifest_sha256=target_manifest_sha256,
        public_queries=public,
    )
    results = run_shared_outer_t0(
        capability,
        alpha=alpha,
        lambda_=lambda_,
        selection_token_sha256=token.sha256,
        g0_predictions=g0,
    )
    outputs: list[Path] = []
    for result, output_root in zip(
        results, (t0_output_root, f0_output_root, f1_output_root), strict=True
    ):
        outputs.append(
            publish_authenticated_pair_cell(
                output_root,
                result,
                model_public_root=model_public_root,
                target_root=target_root,
                expected_model_manifest_sha256=model_manifest_sha256,
                expected_target_manifest_sha256=target_manifest_sha256,
                target_kind="cell-target",
                expected_scope=scope,
                g0_root=g0_root,
                expected_g0_manifest_sha256=g0_manifest_sha256,
                runner_source_sha256=runner_source_sha256,
                runtime=locked_runtime,
                selection_token_root=selection_token_root,
                expected_selection_token_sha256=selection_token_sha256,
                selected_alpha=alpha,
                selected_lambda=lambda_,
            )
        )
    return outputs[0], outputs[1], outputs[2]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-public-root", type=Path, required=True)
    parser.add_argument("--target-root", type=Path, required=True)
    parser.add_argument("--model-manifest-sha256", required=True)
    parser.add_argument("--target-manifest-sha256", required=True)
    parser.add_argument(
        "--target-kind", choices=("cell-target", "c3-target"), required=True
    )
    parser.add_argument("--stage", choices=("inner", "outer"), required=True)
    parser.add_argument("--repeat", type=int, required=True)
    parser.add_argument("--outer-fold", type=int, required=True)
    parser.add_argument("--inner-fold", type=int)
    parser.add_argument("--system-id", required=True)
    parser.add_argument("--alpha", type=float)
    parser.add_argument("--lambda", dest="lambda_", type=float)
    parser.add_argument("--g0-root", type=Path, action="append", required=True)
    parser.add_argument("--g0-manifest-sha256", action="append", required=True)
    parser.add_argument("--expected-source-bundle-sha256", required=True)
    parser.add_argument("--selection-token-root", type=Path)
    parser.add_argument("--selection-token-sha256")
    parser.add_argument("--upstream-candidate-receipt-sha256")
    parser.add_argument("--expected-g0-source-cell-target-manifest-sha256")
    parser.add_argument("--shared-outer-t0", action="store_true")
    parser.add_argument("--f0-output-root", type=Path)
    parser.add_argument("--f1-output-root", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def _fail(message: str) -> None:
    print(f"PAIR_CELL_ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def main() -> None:
    args = _parser().parse_args()
    try:
        if args.shared_outer_t0:
            if (
                args.stage != "outer"
                or args.system_id != "T0"
                or args.inner_fold is not None
                or args.selection_token_root is None
                or args.selection_token_sha256 is None
                or args.f0_output_root is None
                or args.f1_output_root is None
                or args.alpha is None
                or args.lambda_ is None
            ):
                raise PairCellRunnerError("shared outer T0 arguments differ")
            run_shared_t0(
                model_public_root=args.model_public_root,
                target_root=args.target_root,
                model_manifest_sha256=args.model_manifest_sha256,
                target_manifest_sha256=args.target_manifest_sha256,
                alpha=args.alpha,
                lambda_=args.lambda_,
                g0_root=args.g0_root,
                g0_manifest_sha256=args.g0_manifest_sha256,
                t0_output_root=args.output_root,
                f0_output_root=args.f0_output_root,
                f1_output_root=args.f1_output_root,
                expected_source_bundle_sha256=args.expected_source_bundle_sha256,
                repeat=args.repeat,
                outer_fold=args.outer_fold,
                selection_token_root=args.selection_token_root,
                selection_token_sha256=args.selection_token_sha256,
            )
            return
        run(
            model_public_root=args.model_public_root,
            target_root=args.target_root,
            model_manifest_sha256=args.model_manifest_sha256,
            target_manifest_sha256=args.target_manifest_sha256,
            target_kind=cast(Literal["cell-target", "c3-target"], args.target_kind),
            system_id=args.system_id,
            alpha=args.alpha,
            lambda_=args.lambda_,
            g0_root=args.g0_root,
            g0_manifest_sha256=args.g0_manifest_sha256,
            output_root=args.output_root,
            expected_source_bundle_sha256=args.expected_source_bundle_sha256,
            stage=cast(Literal["inner", "outer"], args.stage),
            repeat=args.repeat,
            outer_fold=args.outer_fold,
            inner_fold=args.inner_fold,
            selection_token_root=args.selection_token_root,
            selection_token_sha256=args.selection_token_sha256,
            upstream_candidate_receipt_sha256=args.upstream_candidate_receipt_sha256,
            expected_g0_source_cell_target_manifest_sha256=(
                args.expected_g0_source_cell_target_manifest_sha256
            ),
        )
    except (OSError, ValueError) as exc:
        _fail(str(exc))


if __name__ == "__main__":
    main()

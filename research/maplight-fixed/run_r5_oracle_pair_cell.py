#!/usr/bin/env python3
"""Run one receipt-bound R5C pair system cell in a fresh root process."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, cast

from cypshift.openadmet_oracle_cell_io import (
    load_oracle_cell_capability,
)
from cypshift.openadmet_oracle_pair_cell import (
    run_pair_cell,
)
from cypshift.openadmet_oracle_pair_cell_io import (
    load_g0_predictions,
    publish_pair_cell,
)


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
    stage: Literal["inner", "outer"],
    repeat: int,
    outer_fold: int,
    inner_fold: int | None,
    selection_token_sha256: str | None = None,
    upstream_candidate_receipt_sha256: str | None = None,
) -> Path:
    scope = (stage, repeat, outer_fold, inner_fold)
    capability = load_oracle_cell_capability(
        model_public_root,
        target_root,
        expected_model_manifest_sha256=model_manifest_sha256,
        expected_target_manifest_sha256=target_manifest_sha256,
        system_id=system_id,
        target_kind=target_kind,
        expected_scope=scope,
    )
    episode_ids = {
        row["episode_id"]
        for row in (
            capability.target.episode_anchor_contexts
            if hasattr(capability.target, "episode_anchor_contexts")
            else capability.target.global_anchor_contexts
        )
    }
    public = [
        row
        for row in capability.model_public.public_queries
        if row["episode_id"] in episode_ids
    ]
    g0 = load_g0_predictions(
        g0_root,
        expected_manifest_sha256=g0_manifest_sha256,
        scope=scope,
        public_queries=public,
    )
    result = run_pair_cell(
        capability,
        system_id=system_id,
        alpha=alpha,
        lambda_=lambda_,
        g0_predictions=g0,
        selection_token_sha256=selection_token_sha256,
        upstream_candidate_receipt_sha256=upstream_candidate_receipt_sha256,
    )
    return publish_pair_cell(
        output_root,
        result,
        scope={
            "stage": scope[0],
            "repeat": scope[1],
            "outer_fold": scope[2],
            "inner_fold": "" if scope[3] is None else scope[3],
        },
        capability_binding={
            "model_public_manifest_sha256": model_manifest_sha256,
            "target_manifest_sha256": target_manifest_sha256,
            "g0_manifest_sha256": g0_manifest_sha256,
            "system_id": capability.system_id,
            "source_bundle_binding": capability.model_public.manifest[
                "source_bundle_binding"
            ],
        },
    )


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
    parser.add_argument("--selection-token-sha256")
    parser.add_argument("--upstream-candidate-receipt-sha256")
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
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
        stage=cast(Literal["inner", "outer"], args.stage),
        repeat=args.repeat,
        outer_fold=args.outer_fold,
        inner_fold=args.inner_fold,
        selection_token_sha256=args.selection_token_sha256,
        upstream_candidate_receipt_sha256=args.upstream_candidate_receipt_sha256,
    )


if __name__ == "__main__":
    main()

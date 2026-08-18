#!/usr/bin/env python3
"""R3B v4 staged scorer facade and production CLI.

Input receipt/schema validation lives in :mod:`r3b_scoring_artifacts`, scoring
math in :mod:`r3b_scoring_math`, and terminal publication in
:mod:`r3b_scoring_terminal`.  This facade deliberately re-exports the private
fixture helpers used by the synthetic acceptance tests.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parent
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

from r3b_scoring_artifacts import (  # noqa: E402
    ENDPOINTS,
    MAPLIGHT,
    PRED_COLS,
    SYSTEMS,
    TRUTH_COLS,
    V3_SHA256,
    V4_SHA256,
    V5_SHA256,
    OuterStage,
    R3BScoringError,
    _forbidden,
    _freezer_source_sha,
    _load_freeze,
    _load_truth,
    _truth_index,
)
from r3b_scoring_math import _bootstrap, _q90_completion  # noqa: E402
from r3b_scoring_terminal import (  # noqa: E402
    publish_failure,
    publish_no_advantage,
    run_final,
    run_outer,
    score_final,
    score_outer,
)

_PUBLIC_REEXPORTS = (
    ENDPOINTS,
    MAPLIGHT,
    PRED_COLS,
    SYSTEMS,
    TRUTH_COLS,
    V3_SHA256,
    V4_SHA256,
    V5_SHA256,
    R3BScoringError,
    _forbidden,
    _freezer_source_sha,
    _load_freeze,
    _load_truth,
    _truth_index,
    _bootstrap,
    _q90_completion,
    OuterStage,
    publish_failure,
    publish_no_advantage,
    run_final,
    run_outer,
    score_final,
    score_outer,
)


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="stage", required=True)
    outer = sub.add_parser("outer")
    outer.add_argument("--outer-root", type=Path, required=True)
    outer.add_argument("--sealed-root", type=Path, required=True)
    outer.add_argument("--stage-root", type=Path, required=True)
    outer.add_argument("--output-root", type=Path, required=True)
    outer.add_argument("--outer-manifest-sha256", required=True)
    outer.add_argument("--sealed-manifest-sha256", required=True)
    outer.add_argument("--preflight-receipt", type=Path, required=True)
    outer.add_argument("--preflight-receipt-sha256", required=True)
    final = sub.add_parser("final")
    final.add_argument("--outer-stage-root", type=Path, required=True)
    final.add_argument("--inner-root", type=Path, required=True)
    final.add_argument("--sealed-root", type=Path, required=True)
    final.add_argument("--output-root", type=Path, required=True)
    final.add_argument("--inner-manifest-sha256", required=True)
    final.add_argument("--sealed-manifest-sha256", required=True)
    args = parser.parse_args()
    try:
        if args.stage == "outer":
            result = run_outer(
                outer_root=args.outer_root,
                sealed_root=args.sealed_root,
                stage_root=args.stage_root,
                output_root=args.output_root,
                outer_manifest_sha256=args.outer_manifest_sha256,
                sealed_manifest_sha256=args.sealed_manifest_sha256,
                preflight_receipt=args.preflight_receipt,
                preflight_receipt_sha256=args.preflight_receipt_sha256,
            )
        else:
            result = run_final(
                outer_stage_root=args.outer_stage_root,
                inner_root=args.inner_root,
                sealed_root=args.sealed_root,
                output_root=args.output_root,
                inner_manifest_sha256=args.inner_manifest_sha256,
                sealed_manifest_sha256=args.sealed_manifest_sha256,
            )
    except R3BScoringError as error:
        print(f"R3B scoring rejected: {error}", file=sys.stderr)
        return 2
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

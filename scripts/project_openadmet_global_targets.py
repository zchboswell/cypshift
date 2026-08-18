#!/usr/bin/env python3
"""Build and preflight the synthetic-safe R3B V5 target projection."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from cypshift.openadmet_global_projection import (
    OpenADMETGlobalPreflightError,
    OpenADMETGlobalProjectionError,
    preflight_openadmet_global_targets,
    project_openadmet_global_targets,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct-observations", required=True, type=Path)
    parser.add_argument("--group-folds", required=True, type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--projector-source-sha256")
    parser.add_argument("--preflight-source-sha256")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="also write preflight_receipt.json (no fixture relaxation is exposed)",
    )
    args = parser.parse_args()
    kwargs: dict[str, Any] = {"contract_path": args.contract} if args.contract else {}
    if args.projector_source_sha256:
        kwargs["expected_projector_source_sha256"] = args.projector_source_sha256
    try:
        result = project_openadmet_global_targets(
            args.direct_observations,
            args.group_folds,
            args.out,
            **kwargs,
        )
        if args.preflight:
            preflight_kwargs = {"contract_path": args.contract} if args.contract else {}
            preflight = preflight_openadmet_global_targets(
                args.out,
                **preflight_kwargs,
                expected_preflight_source_sha256=args.preflight_source_sha256,
                expected_model_public_manifest_sha256=result.model_public_manifest_sha256,
                expected_private_audit_sha256=result.private_audit_sha256,
                output_path=args.out.parent / f"{args.out.name}.preflight.json",
            )
            state = "passed" if preflight.receipt["passed"] else "underpowered"
            print(f"R3B target projection and preflight complete ({state}): {args.out}")
        else:
            print(f"R3B target projection complete: {args.out}")
    except (
        OpenADMETGlobalProjectionError,
        OpenADMETGlobalPreflightError,
        OSError,
    ) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

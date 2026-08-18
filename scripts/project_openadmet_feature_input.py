#!/usr/bin/env python3
"""Build the receipt-bound, label-free R3A chemistry projection."""

from __future__ import annotations

import argparse
from pathlib import Path

from cypshift.openadmet_features import (
    OpenADMETFeatureProjectionError,
    project_openadmet_feature_input,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct-observations", required=True, type=Path)
    parser.add_argument("--group-folds", required=True, type=Path)
    parser.add_argument("--training-topology", required=True, type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    kwargs = {"contract_path": args.contract} if args.contract else {}
    try:
        result = project_openadmet_feature_input(
            args.direct_observations,
            args.group_folds,
            args.training_topology,
            args.out,
            **kwargs,
        )
    except (OpenADMETFeatureProjectionError, OSError) as exc:
        parser.error(str(exc))
    print(
        "R3A feature input projection complete: "
        f"{result.molecule_count} molecules; outputs: {result.feature_input_path.parent}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

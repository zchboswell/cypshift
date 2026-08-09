"""Score the frozen retained mean on the declared held-out populations."""

from __future__ import annotations

import argparse
from pathlib import Path

from cypshift.native_combinations import run_retained_mean_scoring


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--octant-canonical", type=Path, required=True)
    parser.add_argument("--tdc-canonical", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--combinations", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--public-sources", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--attempt", type=int, required=True)
    args = parser.parse_args()
    result = run_retained_mean_scoring(
        args.octant_canonical,
        args.tdc_canonical,
        args.validation,
        args.combinations,
        args.predictions,
        args.public_sources,
        args.out,
        source_revision=args.source_revision,
        attempt=args.attempt,
    )
    print(
        f"Retained-mean scoring complete: {result.tdc_evaluations} TDC "
        f"public-test and strict-companion evaluations; "
        f"{result.octant_evaluations} Octant outer evaluation. "
        f"Outputs: {args.out}"
    )


if __name__ == "__main__":
    main()

"""Score one frozen held-out prediction receipt exactly once."""

from __future__ import annotations

import argparse
from pathlib import Path

from cypshift.native_evaluation import run_heldout_scoring


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--octant-canonical", type=Path, required=True)
    parser.add_argument("--tdc-canonical", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--public-sources", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--attempt", type=int, required=True)
    args = parser.parse_args()
    result = run_heldout_scoring(
        args.octant_canonical, args.tdc_canonical, args.validation,
        args.selection, args.predictions, args.public_sources, args.out,
        attempt=args.attempt,
    )
    print(
        f"Held-out scoring complete: {result.tdc_evaluations} TDC public-test "
        f"and {result.octant_evaluations} Octant outer evaluations. "
        f"Outputs: {args.out}"
    )


if __name__ == "__main__":
    main()

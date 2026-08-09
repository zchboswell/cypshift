"""Freeze the Phase 0.5 native ladder using grouped inner validation only."""

from __future__ import annotations

import argparse
from pathlib import Path

from cypshift.native_selection import run_native_selection


def main() -> None:
    """Run the declared four-family ladder without held-out evaluation."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--octant-canonical", type=Path, required=True)
    parser.add_argument("--tdc-canonical", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run_native_selection(
        args.octant_canonical,
        args.tdc_canonical,
        args.validation,
        args.out,
    )
    print(
        "Native train/validation selection complete: "
        f"{result.row_count} retained OOF predictions from "
        f"{result.model_fit_count} grouped fits; zero public-test and Octant "
        f"outer evaluations. Outputs: {args.out}"
    )


if __name__ == "__main__":
    main()

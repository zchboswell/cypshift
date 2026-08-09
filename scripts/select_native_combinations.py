"""Run frozen OOF-only native combinations and random-optimism analysis."""

from __future__ import annotations

import argparse
from pathlib import Path

from cypshift.native_combinations import run_native_combinations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prediction-inputs", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    result = run_native_combinations(
        args.prediction_inputs,
        args.selection,
        args.out,
        source_revision=args.source_revision,
    )
    print(
        f"Native combinations complete: {result.combination_rows} OOF candidate "
        f"rows from {result.model_fits} nested/random fits; zero held-out labels "
        f"parsed and zero held-out evaluations. Outputs: {args.out}"
    )


if __name__ == "__main__":
    main()

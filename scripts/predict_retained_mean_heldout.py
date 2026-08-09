"""Apply the frozen retained mean to label-free held-out base predictions."""

from __future__ import annotations

import argparse
from pathlib import Path

from cypshift.native_combinations import run_retained_mean_prediction


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combinations", type=Path, required=True)
    parser.add_argument("--base-predictions", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    result = run_retained_mean_prediction(
        args.combinations,
        args.base_predictions,
        args.out,
        source_revision=args.source_revision,
    )
    print(
        f"Retained-mean prediction complete: {result.prediction_rows} rows; "
        f"zero fits, zero held-out labels parsed, and zero evaluations. "
        f"Outputs: {args.out}"
    )


if __name__ == "__main__":
    main()

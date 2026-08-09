"""Prepare a label-absent, receipt-bound view for held-out prediction."""

from __future__ import annotations

import argparse
from pathlib import Path

from cypshift.native_evaluation import prepare_prediction_inputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--octant-canonical", type=Path, required=True)
    parser.add_argument("--tdc-canonical", type=Path, required=True)
    parser.add_argument("--tdc-official-split", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = prepare_prediction_inputs(
        args.octant_canonical,
        args.tdc_canonical,
        args.tdc_official_split,
        args.validation,
        args.out,
    )
    print(
        f"Prediction input view complete: {result.training_measurement_rows} "
        f"training measurements and {result.heldout_structures} held-out "
        f"structures; zero held-out measurements materialized. Outputs: {args.out}"
    )


if __name__ == "__main__":
    main()

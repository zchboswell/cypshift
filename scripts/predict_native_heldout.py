"""Generate frozen held-out predictions without reading held-out labels."""

from __future__ import annotations

import argparse
from pathlib import Path

from cypshift.native_evaluation import run_heldout_prediction


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--octant-canonical", type=Path, required=True)
    parser.add_argument("--tdc-canonical", type=Path, required=True)
    parser.add_argument("--tdc-official-split", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run_heldout_prediction(
        args.octant_canonical,
        args.tdc_canonical,
        args.tdc_official_split,
        args.validation,
        args.selection,
        args.out,
    )
    print(
        f"Frozen held-out predictions complete: {result.prediction_rows} rows "
        f"from {result.model_fits} fits; zero held-out labels parsed and zero "
        f"evaluations. Outputs: {args.out}"
    )


if __name__ == "__main__":
    main()

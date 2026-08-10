"""Run the single reviewed grouped-OOF series-residual experiment."""

from __future__ import annotations

import argparse
from pathlib import Path

from cypshift.series_residual import run_series_residual


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combinations", type=Path, required=True)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    result = run_series_residual(
        args.combinations,
        args.research,
        args.contract,
        args.out,
        source_revision=args.source_revision,
    )
    decision = "retain" if result.retained else "reject"
    print(
        f"Series-residual OOF test complete: {result.rows} rows, zero fits, "
        f"zero held-out labels or evaluations; decision={decision}. "
        f"Outputs: {args.out}"
    )


if __name__ == "__main__":
    main()

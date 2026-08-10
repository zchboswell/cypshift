"""Validate TDC-CYP-shadow-v1 with the frozen train-only labels."""

from __future__ import annotations

import argparse
from pathlib import Path

from cypshift.shadow import summarize_shadow_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--implementation-contract", type=Path, required=True)
    parser.add_argument("--shadow-rows", type=Path, required=True)
    parser.add_argument("--assignment-receipt", type=Path, required=True)
    parser.add_argument("--train-val-measurements", type=Path, required=True)
    parser.add_argument("--measurement-parent-manifest", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    result = summarize_shadow_rows(
        args.contract,
        args.implementation_contract,
        args.shadow_rows,
        args.assignment_receipt,
        args.train_val_measurements,
        args.measurement_parent_manifest,
        source_revision=args.source_revision,
    )
    print(
        f"Shadow validation complete: {result.row_count} rows and "
        f"{result.label_count} train-only labels; zero public-test labels."
    )


if __name__ == "__main__":
    main()

"""Freeze grouped Octant validation and audit official TDC split leakage."""

from __future__ import annotations

import argparse
from pathlib import Path

from cypshift.validation import (
    audit_tdc_official_splits,
    freeze_octant_grouped_split,
)


def main() -> None:
    """Create immutable public-validation artifacts without evaluating models."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--octant-canonical", type=Path, required=True)
    parser.add_argument("--tdc-canonical", type=Path, required=True)
    parser.add_argument("--tdc-official-split", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260809)
    args = parser.parse_args()
    if args.out.exists():
        parser.error(f"output path already exists: {args.out}")

    octant = freeze_octant_grouped_split(
        args.octant_canonical,
        args.out / "octant",
        seed=args.seed,
    )
    tdc = audit_tdc_official_splits(
        args.tdc_canonical,
        args.tdc_official_split,
        args.out / "tdc",
    )
    print(
        "Public validation freeze complete: "
        f"{octant.row_count} Octant rows in {octant.group_count} groups; "
        f"{tdc.exclusion_count} TDC public-test rows flagged for the strict "
        f"companion analysis. Outputs: {args.out}"
    )


if __name__ == "__main__":
    main()

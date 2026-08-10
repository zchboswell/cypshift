"""Generate label-free global assignments for TDC-CYP-shadow-v1."""

from __future__ import annotations

import argparse
from pathlib import Path

from cypshift.shadow import assign_shadow_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--implementation-contract", type=Path, required=True)
    parser.add_argument("--input-rows", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = assign_shadow_rows(
        args.contract,
        args.implementation_contract,
        args.input_rows,
        args.input_manifest,
        args.lock,
        args.out,
        source_revision=args.source_revision,
    )
    print(
        f"Shadow assignment complete: {result.row_count} rows, "
        f"{result.scaffold_group_count} scaffold groups, and "
        f"{result.community_group_count} chemistry communities; zero labels used."
    )


if __name__ == "__main__":
    main()

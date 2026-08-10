"""Prepare the stripped train-only input for TDC-CYP-shadow-v1."""

from __future__ import annotations

import argparse
from pathlib import Path

from cypshift.shadow import prepare_shadow_input


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--implementation-contract", type=Path, required=True)
    parser.add_argument("--adapter-manifest", type=Path, required=True)
    parser.add_argument("--official-split", type=Path, required=True)
    parser.add_argument("--canonical-molecules", type=Path, required=True)
    parser.add_argument("--canonical-audit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = prepare_shadow_input(
        args.contract,
        args.implementation_contract,
        args.adapter_manifest,
        args.official_split,
        args.canonical_molecules,
        args.canonical_audit,
        args.out,
    )
    print(
        f"Shadow input complete: {result.row_count} rows and "
        f"{result.unique_structure_count} standardized structures; "
        "zero targets or public-test rows."
    )


if __name__ == "__main__":
    main()

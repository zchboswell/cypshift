"""Prepare the receipt-bound OpenADMET CYP source-row artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cypshift.openadmet_cyp import (
    DEFAULT_RECEIPTS_PATH,
    OpenADMETDataError,
    prepare_openadmet_cyp,
)


def main() -> int:
    """Validate the frozen CSVs and write a new source-only output directory."""

    parser = argparse.ArgumentParser(
        description="Prepare receipt-bound OpenADMET CYP source-row artifacts."
    )
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-directory", "--out", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument(
        "--receipts-path",
        "--receipts",
        type=Path,
        default=DEFAULT_RECEIPTS_PATH,
    )
    args = parser.parse_args()
    try:
        result = prepare_openadmet_cyp(
            args.dataset_root,
            args.output_directory,
            source_revision=args.source_revision,
            receipts_path=args.receipts_path,
        )
    except OpenADMETDataError as exc:
        print(f"OpenADMET preparation failed: {exc}", file=sys.stderr)
        return 2
    print(
        "OpenADMET preparation complete: "
        f"{result.source_row_count} source rows, "
        f"{result.molecule_count} molecules; outputs: {result.manifest_path.parent}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

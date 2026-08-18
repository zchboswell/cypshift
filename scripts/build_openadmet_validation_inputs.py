"""Build receipt-bound OpenADMET R2A observations and component folds."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cypshift.openadmet_validation import (
    OpenADMETValidationError,
    build_openadmet_validation_inputs,
)


def main() -> int:
    """Run one non-overwriting R2A build."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-contract", type=Path, required=True)
    parser.add_argument("--direct-source", type=Path, required=True)
    parser.add_argument("--r1-directory", type=Path, required=True)
    parser.add_argument("--topology-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    try:
        result = build_openadmet_validation_inputs(
            validation_contract_path=args.validation_contract,
            direct_source_path=args.direct_source,
            r1_directory=args.r1_directory,
            topology_directory=args.topology_directory,
            output_directory=args.output_directory,
            source_revision=args.source_revision,
        )
    except OpenADMETValidationError as exc:
        print(f"OpenADMET R2A build failed: {exc}", file=sys.stderr)
        return 2
    print(
        "OpenADMET R2A build complete: "
        f"{result.observation_count} observations, "
        f"{result.molecule_count} molecules; outputs: {result.manifest_path.parent}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

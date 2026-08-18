"""Build receipt-bound OpenADMET R2B episodes, masks, and viability artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cypshift.openadmet_campaign import (
    OpenADMETCampaignError,
    build_openadmet_campaign_artifacts,
)


def main() -> int:
    """Run one non-overwriting R2B artifact build."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-contract", type=Path, required=True)
    parser.add_argument("--r2a-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    try:
        result = build_openadmet_campaign_artifacts(
            validation_contract_path=args.validation_contract,
            r2a_directory=args.r2a_directory,
            output_directory=args.output_directory,
            source_revision=args.source_revision,
        )
    except OpenADMETCampaignError as exc:
        print(f"OpenADMET R2B build failed: {exc}", file=sys.stderr)
        return 2
    print(
        "OpenADMET R2B build complete: "
        f"{result.episode_count} episodes, "
        f"{result.expanded_query_count} expanded queries; "
        f"outputs: {result.output_directory}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

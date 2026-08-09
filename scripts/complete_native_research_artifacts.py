"""Complete the first scorecard and OOF research-artifact contracts."""

from __future__ import annotations

import argparse
from pathlib import Path

from cypshift.research_artifacts import (
    complete_first_scorecard,
    complete_oof_research_artifact,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--predictions-v2", type=Path, required=True)
    parser.add_argument("--scores-v1", type=Path, required=True)
    parser.add_argument("--octant-canonical", type=Path, required=True)
    parser.add_argument("--tdc-canonical", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--public-sources", type=Path, required=True)
    parser.add_argument("--oof-out", type=Path, required=True)
    parser.add_argument("--scorecard-out", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--selection-runtime-seconds", type=float, required=True)
    parser.add_argument("--prediction-runtime-seconds", type=float, required=True)
    parser.add_argument("--scoring-runtime-seconds", type=float, required=True)
    parser.add_argument("--hardware", required=True)
    args = parser.parse_args()
    oof_manifest = complete_oof_research_artifact(
        args.selection,
        args.octant_canonical,
        args.tdc_canonical,
        args.validation,
        args.oof_out,
        source_revision=args.source_revision,
    )
    scorecard_manifest = complete_first_scorecard(
        args.scores_v1,
        args.predictions_v2,
        args.selection,
        args.validation,
        args.public_sources,
        args.scorecard_out,
        source_revision=args.source_revision,
        selection_runtime_seconds=args.selection_runtime_seconds,
        prediction_runtime_seconds=args.prediction_runtime_seconds,
        scoring_runtime_seconds=args.scoring_runtime_seconds,
        hardware=args.hardware,
    )
    print(
        "Research-artifact completion passed without changing point scores. "
        f"OOF receipt: {oof_manifest}; scorecard receipt: {scorecard_manifest}"
    )


if __name__ == "__main__":
    main()

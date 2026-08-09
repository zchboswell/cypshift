"""Complete the canonical retained-mean scorecard from frozen scored outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from cypshift.research_artifacts import complete_retained_mean_scorecard


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--public-sources", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--selection-runtime-seconds", type=float, required=True)
    parser.add_argument("--prediction-runtime-seconds", type=float, required=True)
    parser.add_argument("--scoring-runtime-seconds", type=float, required=True)
    parser.add_argument("--hardware", required=True)
    args = parser.parse_args()
    manifest = complete_retained_mean_scorecard(
        args.scores,
        args.validation,
        args.public_sources,
        args.out,
        source_revision=args.source_revision,
        selection_runtime_seconds=args.selection_runtime_seconds,
        prediction_runtime_seconds=args.prediction_runtime_seconds,
        scoring_runtime_seconds=args.scoring_runtime_seconds,
        hardware=args.hardware,
    )
    print(f"Retained-mean scorecard complete: {manifest}")


if __name__ == "__main__":
    main()

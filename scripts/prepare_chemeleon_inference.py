"""Prepare the stripped label-free input for the CheMeleon reference."""

from __future__ import annotations

import argparse
from pathlib import Path

from cypshift.chemeleon import prepare_chemeleon_inference_input


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prediction-inputs", type=Path, required=True)
    parser.add_argument("--population-keys", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    manifest = prepare_chemeleon_inference_input(
        args.prediction_inputs,
        args.population_keys,
        args.contract,
        args.out,
        source_revision=args.source_revision,
    )
    print(f"CheMeleon input prepared: {manifest}")


if __name__ == "__main__":
    main()

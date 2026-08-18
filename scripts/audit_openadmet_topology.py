"""Audit candidate OpenADMET training topology from R1 artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cypshift.openadmet_topology import (
    OpenADMETTopologyError,
    audit_openadmet_topology,
)


def main() -> int:
    """Run one non-overwriting, label-free topology audit."""

    parser = argparse.ArgumentParser(
        description="Audit label-free OpenADMET training topology."
    )
    parser.add_argument("--input-directory", "--input", type=Path, required=True)
    parser.add_argument("--output-directory", "--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit_openadmet_topology(args.input_directory, args.output_directory)
    except OpenADMETTopologyError as exc:
        print(f"OpenADMET topology audit failed: {exc}", file=sys.stderr)
        return 2
    print(
        "OpenADMET topology audit complete: "
        f"{result.training_molecules} training molecules, "
        f"{result.similarity_components} similarity components, "
        f"{result.scaffold_groups} scaffold groups; "
        f"outputs: {result.manifest_path.parent}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

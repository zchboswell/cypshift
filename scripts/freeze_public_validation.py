"""Freeze grouped Octant validation and audit official TDC split leakage."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
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
    parser.add_argument("--tdc-adapter-manifest", type=Path, required=True)
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
        args.tdc_adapter_manifest,
        args.out / "tdc",
        seed=args.seed,
    )
    output_paths = {
        "octant/octant_grouped_split.csv": octant.split_path,
        "octant/split_manifest.json": octant.manifest_path,
        "tdc/strict_test_exclusions.csv": tdc.exclusions_path,
        "tdc/tdc_split_audit.json": tdc.report_path,
        "tdc/tdc_inner_folds.csv": tdc.inner_folds_path,
    }
    output_hashes = {
        name: _file_hash(path) for name, path in sorted(output_paths.items())
    }
    aggregate_material = "\n".join(
        f"{name}={output_hashes[name]}" for name in sorted(output_hashes)
    )
    receipt = {
        "schema_version": "cypshift.public_validation_freeze.v1",
        "seed": args.seed,
        "outputs": output_hashes,
        "aggregate_recipe": (
            "SHA-256 of UTF-8 path=sha256 lines sorted by path and joined "
            "with newline characters, without a trailing newline"
        ),
        "aggregate_sha256": sha256(aggregate_material.encode()).hexdigest(),
        "model_fits": 0,
        "public_test_evaluations": 0,
    }
    (args.out / "public_validation_manifest.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "Public validation freeze complete: "
        f"{octant.row_count} Octant rows in {octant.group_count} groups; "
        f"{tdc.inner_fold_row_count} TDC train_val rows in grouped inner folds; "
        f"{tdc.exclusion_count} TDC public-test rows flagged for the strict "
        f"companion analysis. Outputs: {args.out}"
    )


def _file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    main()

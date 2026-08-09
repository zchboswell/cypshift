"""Rebuild the required public-data and validation freeze from an empty root."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path


def main() -> None:
    """Run the concrete Phase 0.5 data-foundation scripts in frozen order."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "benchmarks"
        / "public_sources.json",
    )
    args = parser.parse_args()
    if args.out.exists():
        parser.error(f"output path already exists: {args.out}")

    scripts = Path(__file__).resolve().parent
    raw = args.out / "raw"
    octant = args.out / "octant"
    tdc = args.out / "tdc"
    validation = args.out / "validation"
    octant_revision = _octant_revision(args.manifest)
    commands = [
        [
            sys.executable,
            str(scripts / "fetch_required_benchmarks.py"),
            "--out",
            str(raw),
            "--manifest",
            str(args.manifest),
        ],
        [
            sys.executable,
            str(scripts / "prepare_octant_benchmark.py"),
            "--source",
            str(raw / "octant_cyp" / octant_revision / "inhibition.tsv"),
            "--out",
            str(octant),
            "--manifest",
            str(args.manifest),
        ],
        [
            sys.executable,
            str(scripts / "prepare_tdc_benchmark.py"),
            "--archive",
            str(raw / "tdc_admet" / "admet_group.zip"),
            "--out",
            str(tdc),
            "--manifest",
            str(args.manifest),
        ],
        [
            sys.executable,
            str(scripts / "freeze_public_validation.py"),
            "--octant-canonical",
            str(octant / "canonical"),
            "--tdc-canonical",
            str(tdc / "canonical"),
            "--tdc-official-split",
            str(tdc / "adapter" / "official_split.csv"),
            "--tdc-adapter-manifest",
            str(tdc / "adapter" / "adapter_manifest.json"),
            "--out",
            str(validation),
        ],
    ]
    for command in commands:
        subprocess.run(command, check=True)

    artifacts = {
        "raw/source_receipt.json": raw / "source_receipt.json",
        "octant/adapter/adapter_manifest.json": (
            octant / "adapter" / "adapter_manifest.json"
        ),
        "octant/canonical/audit.json": octant / "canonical" / "audit.json",
        "tdc/adapter/adapter_manifest.json": (
            tdc / "adapter" / "adapter_manifest.json"
        ),
        "tdc/canonical/audit.json": tdc / "canonical" / "audit.json",
        "validation/public_validation_manifest.json": (
            validation / "public_validation_manifest.json"
        ),
    }
    hashes = {name: _file_hash(path) for name, path in sorted(artifacts.items())}
    aggregate_material = "\n".join(
        f"{name}={hashes[name]}" for name in sorted(hashes)
    )
    receipt = {
        "schema_version": "cypshift.public_data_reproduction.v1",
        "artifact_hashes": hashes,
        "aggregate_recipe": (
            "SHA-256 of UTF-8 path=sha256 lines sorted by path and joined "
            "with newline characters, without a trailing newline"
        ),
        "aggregate_sha256": sha256(aggregate_material.encode()).hexdigest(),
        "model_fits": 0,
        "public_test_evaluations": 0,
    }
    with (args.out / "reproduction_receipt.json").open(
        "x", encoding="utf-8"
    ) as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"Public-data freeze reproduced from an empty root: {args.out}")


def _file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _octant_revision(path: Path) -> str:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        revision = manifest["sources"]["octant_cyp"]["revision"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise SystemExit(f"cannot read Octant revision from {path}: {exc}") from exc
    if not isinstance(revision, str) or not revision:
        raise SystemExit("Octant revision must be nonempty text")
    return revision


if __name__ == "__main__":
    main()

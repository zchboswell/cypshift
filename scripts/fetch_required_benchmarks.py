"""Fetch the two required Phase 0.5 public inputs into a verified clean cache."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import urllib.error
import urllib.request
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[1] / "benchmarks" / "public_sources.json"
)


def main() -> None:
    """Download only Octant inhibition.tsv and the frozen TDC archive."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    if args.out.exists():
        parser.error(f"output path already exists: {args.out}")

    manifest = _read_manifest(args.manifest)
    octant = _mapping(_mapping(manifest, "sources"), "octant_cyp")
    tdc = _mapping(_mapping(manifest, "sources"), "tdc_admet")
    revision = _text(octant, "revision")
    inhibition = next(
        (
            entry
            for entry in _objects(octant, "files")
            if entry.get("path") == "inhibition.tsv"
        ),
        None,
    )
    if inhibition is None:
        parser.error("public source manifest has no Octant inhibition.tsv")
    archive = _mapping(tdc, "archive")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{args.out.name}-", dir=args.out.parent
    ) as temporary_name:
        temporary_root = Path(temporary_name)
        receipts = []
        receipts.append(
            _fetch(
                _text(inhibition, "url"),
                temporary_root / "octant_cyp" / revision / "inhibition.tsv",
                root=temporary_root,
                expected_size=_integer(inhibition, "size_bytes"),
                expected_hash=_digest(inhibition, "sha256"),
            )
        )
        archive_name = _text(archive, "path")
        receipts.append(
            _fetch(
                _text(archive, "url"),
                temporary_root / "tdc_admet" / archive_name,
                root=temporary_root,
                expected_size=_integer(archive, "size_bytes"),
                expected_hash=_digest(archive, "sha256"),
            )
        )
        receipt = {
            "schema_version": "cypshift.required_public_downloads.v1",
            "source_manifest_sha256": _file_hash(args.manifest),
            "files": receipts,
            "verified": True,
        }
        (temporary_root / "source_receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_root, args.out)
    print(f"Verified 2 required public inputs in {args.out}")


def _fetch(
    url: str,
    path: Path,
    *,
    root: Path,
    expected_size: int,
    expected_hash: str,
) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = sha256()
    size = 0
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "cypshift-public-benchmark/0.2"}
        )
        with urllib.request.urlopen(request, timeout=60) as response, path.open(
            "xb"
        ) as handle:
            for block in iter(lambda: response.read(1024 * 1024), b""):
                handle.write(block)
                digest.update(block)
                size += len(block)
    except (OSError, urllib.error.URLError) as exc:
        raise SystemExit(f"cannot download {url}: {exc}") from exc
    actual_hash = digest.hexdigest()
    if size != expected_size:
        raise SystemExit(
            f"size mismatch for {url}: expected {expected_size}, got {size}"
        )
    if actual_hash != expected_hash:
        raise SystemExit(
            f"hash mismatch for {url}: expected {expected_hash}, got {actual_hash}"
        )
    return {
        "path": str(path.relative_to(root)),
        "sha256": actual_hash,
        "size_bytes": size,
        "url": url,
    }


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read public source manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("public source manifest must be an object")
    if value.get("schema_version") != "cypshift.public_sources.v1":
        raise SystemExit("unsupported public source manifest schema")
    return cast(dict[str, Any], value)


def _mapping(value: dict[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise SystemExit(f"public source manifest {key!r} must be an object")
    return cast(dict[str, Any], item)


def _objects(value: dict[str, Any], key: str) -> list[dict[str, Any]]:
    item = value.get(key)
    if not isinstance(item, list) or not all(isinstance(entry, dict) for entry in item):
        raise SystemExit(f"public source manifest {key!r} must be an object array")
    return cast(list[dict[str, Any]], item)


def _text(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise SystemExit(f"public source manifest {key!r} must be nonempty text")
    return item.strip()


def _integer(value: dict[str, Any], key: str) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool) or item < 0:
        raise SystemExit(
            f"public source manifest {key!r} must be a nonnegative integer"
        )
    return item


def _digest(value: dict[str, Any], key: str) -> str:
    digest = _text(value, key).lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise SystemExit(f"public source manifest {key!r} must be a SHA-256")
    return digest


def _file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    main()

"""Opaque-byte cleanup witness for failed synthetic R5C prefit runs."""

from __future__ import annotations

import json
import os
import stat
from hashlib import sha256
from pathlib import Path
from typing import Any, Final

from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS
from cypshift.openadmet_oracle_private_io import (
    publish_readonly_tree,
    read_stable_file,
    remove_private_root,
)
from cypshift.openadmet_oracle_projection import DENIED_AUTHORITY
from cypshift.openadmet_oracle_sealed import RESOLVED_CONTRACT_SHA256

SCHEMA: Final = "cypshift.openadmet_cyp_2026.r5c_prefit_cleanup_witness.v1"


def purge_prefit_private_tree(private_root: Path, witness_root: Path) -> str:
    """Hash opaque private bytes, remove the exact tree, and publish a witness."""

    if witness_root != private_root / "failure-witness":
        raise ValueError("failure witness path differs")
    inventory = _inventory(private_root)
    material = "".join(f"{name}|{digest}\n" for name, digest in inventory)
    remove_private_root(private_root)
    private_root.mkdir(mode=0o700)
    source_sha = sha256(read_stable_file(Path(__file__).resolve())).hexdigest()
    data = _compact(
        {
            "schema_version": SCHEMA,
            "contract_sha256": RESOLVED_CONTRACT_SHA256,
            "removed_files": len(inventory),
            "inventory_sha256": sha256(material.encode()).hexdigest(),
            "source_sha256": source_sha,
            "operation_accounting": dict.fromkeys(ACCOUNTING_FIELDS, 0),
            "authority": DENIED_AUTHORITY,
        }
    )
    publish_readonly_tree(witness_root, {"manifest.json": data})
    return sha256(data).hexdigest()


def _inventory(root: Path) -> tuple[tuple[str, str], ...]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("private failure root differs")
    result: list[tuple[str, str]] = []
    for directory, directories, files, _fd in os.fwalk(root, follow_symlinks=False):
        base = Path(directory)
        for name in (*directories, *files):
            mode = os.lstat(base / name).st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ValueError("private failure tree entry differs")
        for name in files:
            path = base / name
            relative = path.relative_to(root).as_posix()
            result.append((relative, sha256(read_stable_file(path)).hexdigest()))
    return tuple(sorted(result))


def _compact(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


__all__ = ["SCHEMA", "purge_prefit_private_tree"]

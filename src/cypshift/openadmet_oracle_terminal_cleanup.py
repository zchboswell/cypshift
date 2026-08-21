"""Authenticated exact cleanup capabilities for R5C terminal publication."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Final

from cypshift.openadmet_oracle_inner_io import EXPECTED_RUNTIME
from cypshift.openadmet_oracle_private_io import (
    OraclePrivateIOError,
    publish_readonly_tree,
    read_exact_root,
    read_stable_file,
)
from cypshift.openadmet_oracle_projection import DENIED_AUTHORITY
from cypshift.openadmet_oracle_sealed import RESOLVED_CONTRACT_SHA256

ROOT: Final = Path(__file__).resolve().parents[2]
CLEANUP_SCHEMA: Final = "cypshift.openadmet_cyp_2026.r5c_terminal_cleanup.v1"
CLEANUP_STATUS: Final = "R5_ORACLE_CLEANUP_SET_COMPLETE"
CLEANUP_SOURCE_FILES: Final = (
    "src/cypshift/openadmet_oracle_private_io.py",
    "src/cypshift/openadmet_oracle_terminal_cleanup.py",
)


class OracleTerminalCleanupError(ValueError):
    """A cleanup capability or exact private-root set differs."""


@dataclass(frozen=True, slots=True)
class CleanupCapability:
    label: str
    root: Path
    relative_path: str
    expected_sha256: str


@dataclass(frozen=True, slots=True)
class CleanupInput:
    root: Path
    expected_sha256: str
    capabilities: tuple[CleanupCapability, ...]


@dataclass(frozen=True, slots=True)
class LoadedCleanup:
    sha256: str
    capabilities: tuple[CleanupCapability, ...]


def cleanup_source_bundle_sha256() -> str:
    material = "".join(
        f"{name}|{sha256(read_stable_file(ROOT / name)).hexdigest()}\n"
        for name in sorted(CLEANUP_SOURCE_FILES)
    )
    return sha256(material.encode()).hexdigest()


def publish_cleanup_receipt(
    output_root: Path, capabilities: tuple[CleanupCapability, ...]
) -> str:
    entries = _validated_entries(capabilities)
    _disjoint(output_root, capabilities)
    record = {
        "schema_version": CLEANUP_SCHEMA,
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "status": CLEANUP_STATUS,
        "capabilities": entries,
        "source_sha256": cleanup_source_bundle_sha256(),
        "runtime": EXPECTED_RUNTIME,
        "authority": DENIED_AUTHORITY,
    }
    data = _compact(record)
    publish_readonly_tree(output_root, {"cleanup.json": data})
    return sha256(data).hexdigest()


def load_cleanup(source: CleanupInput) -> LoadedCleanup:
    _digest(source.expected_sha256)
    expected = _validated_entries(source.capabilities)
    _disjoint(source.root, source.capabilities)
    try:
        data = read_exact_root(source.root, ("cleanup.json",))["cleanup.json"]
    except OraclePrivateIOError as exc:
        raise OracleTerminalCleanupError(str(exc)) from exc
    if sha256(data).hexdigest() != source.expected_sha256:
        raise OracleTerminalCleanupError("cleanup receipt differs")
    record = _canonical(data)
    if (
        set(record)
        != {
            "schema_version",
            "contract_sha256",
            "status",
            "capabilities",
            "source_sha256",
            "runtime",
            "authority",
        }
        or record.get("schema_version") != CLEANUP_SCHEMA
        or record.get("contract_sha256") != RESOLVED_CONTRACT_SHA256
        or record.get("status") != CLEANUP_STATUS
        or record.get("capabilities") != expected
        or record.get("source_sha256") != cleanup_source_bundle_sha256()
        or record.get("runtime") != EXPECTED_RUNTIME
        or record.get("authority") != DENIED_AUTHORITY
    ):
        raise OracleTerminalCleanupError("cleanup binding differs")
    return LoadedCleanup(source.expected_sha256, source.capabilities)


def _validated_entries(
    capabilities: tuple[CleanupCapability, ...],
) -> list[dict[str, str]]:
    labels = tuple(item.label for item in capabilities)
    roots = tuple(item.root.resolve(strict=True) for item in capabilities)
    if labels != tuple(sorted(labels)) or len(set(labels)) != len(labels):
        raise OracleTerminalCleanupError("cleanup capability order differs")
    if len(set(roots)) != len(roots):
        raise OracleTerminalCleanupError("cleanup capability roots overlap")
    entries: list[dict[str, str]] = []
    for item in capabilities:
        if (
            not item.label
            or any(not (char.isalnum() or char in "_.-") for char in item.label)
            or not item.relative_path
            or "/" in item.relative_path
            or "\\" in item.relative_path
        ):
            raise OracleTerminalCleanupError("cleanup capability label differs")
        _digest(item.expected_sha256)
        try:
            observed = sha256(
                read_stable_file(item.root / item.relative_path)
            ).hexdigest()
        except OraclePrivateIOError as exc:
            raise OracleTerminalCleanupError(str(exc)) from exc
        if observed != item.expected_sha256:
            raise OracleTerminalCleanupError("cleanup capability receipt differs")
        entries.append(
            {
                "label": item.label,
                "relative_path": item.relative_path,
                "sha256": item.expected_sha256,
            }
        )
    return entries


def _disjoint(cleanup_root: Path, capabilities: tuple[CleanupCapability, ...]) -> None:
    paths = (cleanup_root.absolute(), *(item.root.absolute() for item in capabilities))
    if any(
        left == right or left in right.parents or right in left.parents
        for index, left in enumerate(paths)
        for right in paths[index + 1 :]
    ):
        raise OracleTerminalCleanupError("cleanup capability paths overlap")


def _digest(value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise OracleTerminalCleanupError("cleanup digest differs")


def _canonical(data: bytes) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OracleTerminalCleanupError("cleanup JSON differs") from exc
    if not isinstance(value, dict) or _compact(value) != data:
        raise OracleTerminalCleanupError("cleanup JSON differs")
    return value


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


__all__ = [
    "CleanupCapability",
    "CleanupInput",
    "LoadedCleanup",
    "OracleTerminalCleanupError",
    "cleanup_source_bundle_sha256",
    "load_cleanup",
    "publish_cleanup_receipt",
]

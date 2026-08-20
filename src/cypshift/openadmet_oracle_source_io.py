"""Receipt and publication helpers for the synthetic R5B source compiler."""

from __future__ import annotations

import csv
import ctypes
import errno
import io
import json
import math
import os
import platform
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast


class OpenADMETOracleSourceIOError(ValueError):
    """A source byte, parser, or publication invariant failed."""


def csv_rows(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    if b"\r" in data or not data.endswith(b"\n"):
        raise OpenADMETOracleSourceIOError(f"{label} line endings differ")
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True)
        if next(reader, None) != list(columns):
            raise OpenADMETOracleSourceIOError(f"{label} columns differ")
        rows: list[dict[str, str]] = []
        for values in reader:
            if len(values) != len(columns):
                raise OpenADMETOracleSourceIOError(f"{label} field count differs")
            rows.append(dict(zip(columns, values, strict=True)))
        return rows
    except (UnicodeError, csv.Error) as exc:
        raise OpenADMETOracleSourceIOError(f"cannot parse {label}") from exc


def json_object(data: bytes, label: str) -> dict[str, Any]:
    value = json_value(data.decode("utf-8"), label)
    if not isinstance(value, dict):
        raise OpenADMETOracleSourceIOError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def json_value(value: str, label: str) -> Any:
    try:
        parsed = json.loads(value, object_pairs_hook=_reject_json_pairs(label))
    except OpenADMETOracleSourceIOError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OpenADMETOracleSourceIOError(f"cannot parse {label}") from exc
    return parsed


def json_list(value: str, label: str) -> list[str]:
    parsed = json_value(value, label)
    if (
        not isinstance(parsed, list)
        or not parsed
        or not all(isinstance(item, str) and item for item in parsed)
        or len(parsed) != len(set(parsed))
    ):
        raise OpenADMETOracleSourceIOError(f"invalid {label}")
    return cast(list[str], parsed)


def json_object_cell(value: str, label: str) -> dict[str, Any]:
    parsed = json_value(value, label)
    if not isinstance(parsed, dict):
        raise OpenADMETOracleSourceIOError(f"{label} must be an object")
    return cast(dict[str, Any], parsed)


def mapping(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise OpenADMETOracleSourceIOError(f"{key} must be an object")
    return cast(dict[str, Any], item)


def canonical_int(value: str, label: str) -> int:
    try:
        if not value or str(int(value)) != value:
            raise ValueError
        return int(value)
    except ValueError as exc:
        raise OpenADMETOracleSourceIOError(f"{label} is not canonical integer") from exc


def finite(value: str, label: str) -> None:
    try:
        if not value or not math.isfinite(float(value)):
            raise ValueError
    except ValueError as exc:
        raise OpenADMETOracleSourceIOError(f"{label} is not finite") from exc


def sha_digest(value: str, label: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise OpenADMETOracleSourceIOError(f"{label} is not lowercase SHA-256")


def publish(output_directory: Path, outputs: Mapping[str, bytes]) -> None:
    parent = output_directory.parent
    _reject_symlink_ancestry(output_directory, "output path")
    parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".r5b-source-", dir=parent))
    try:
        for name, data in outputs.items():
            path = stage / name
            if path.exists() or path.is_symlink():
                raise OpenADMETOracleSourceIOError("duplicate staged output")
            with path.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            path.chmod(0o444)
        stage.chmod(0o555)
        _verify_staged_outputs(stage, outputs)
        if output_directory.exists() or output_directory.is_symlink():
            raise OpenADMETOracleSourceIOError("output path appeared")
        rename_noreplace(stage, output_directory)
        stage = Path()
    except Exception:
        if stage != Path():
            cleanup(stage)
        raise


def rename_noreplace(source: Path, destination: Path) -> None:
    if platform.system() != "Linux" or os.name != "posix":
        raise OpenADMETOracleSourceIOError("atomic no-replace promotion requires Linux")
    try:
        function = ctypes.CDLL(None, use_errno=True).renameat2
    except (AttributeError, OSError) as exc:
        raise OpenADMETOracleSourceIOError("renameat2 unavailable") from exc
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    function.restype = ctypes.c_int
    if (
        function(
            -100,
            os.fsencode(os.path.abspath(source)),
            -100,
            os.fsencode(os.path.abspath(destination)),
            1,
        )
        != 0
    ):
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise OpenADMETOracleSourceIOError("output path appeared")
        raise OpenADMETOracleSourceIOError(os.strerror(error))


def cleanup(path: Path) -> None:
    if not path.exists():
        return
    try:
        path.chmod(0o755)
    except OSError:
        pass
    for item in sorted(path.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        try:
            if item.is_file():
                item.chmod(0o644)
            elif item.is_dir():
                item.chmod(0o755)
        except OSError:
            pass
    shutil.rmtree(path, ignore_errors=True)


def safe_source_path(path: Path, label: str) -> Path:
    """Reject traversal, symlink ancestry, and non-regular source files."""

    _reject_symlink_ancestry(path, label)
    if not path.is_file():
        raise OpenADMETOracleSourceIOError(f"{label} must be a regular file")
    return path


def _reject_symlink_ancestry(path: Path, label: str) -> None:
    if ".." in path.parts:
        raise OpenADMETOracleSourceIOError(f"{label} contains path traversal")
    if any(candidate.is_symlink() for candidate in (path, *path.parents)):
        raise OpenADMETOracleSourceIOError(f"{label} contains a symlink")


def _verify_staged_outputs(stage: Path, outputs: Mapping[str, bytes]) -> None:
    if stage.is_symlink() or not stage.is_dir():
        raise OpenADMETOracleSourceIOError("staged root differs")
    entries = {entry.name for entry in stage.iterdir()}
    if entries != set(outputs):
        raise OpenADMETOracleSourceIOError("staged output set differs")
    for name, expected in outputs.items():
        path = stage / name
        if path.is_symlink() or not path.is_file() or path.read_bytes() != expected:
            raise OpenADMETOracleSourceIOError(f"staged output differs: {name}")


def _reject_json_pairs(label: str) -> Any:
    def reject(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise OpenADMETOracleSourceIOError(f"duplicate JSON key in {label}")
            result[key] = item
        return result

    return reject


__all__ = [
    "OpenADMETOracleSourceIOError",
    "canonical_int",
    "cleanup",
    "csv_rows",
    "finite",
    "json_list",
    "json_object_cell",
    "json_object",
    "json_value",
    "mapping",
    "publish",
    "rename_noreplace",
    "safe_source_path",
    "sha_digest",
]

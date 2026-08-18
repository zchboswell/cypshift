"""Atomic read-only publication helpers for the R3B scorer."""

from __future__ import annotations

import ctypes
import errno
import os
import shutil
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

from r3b_scoring_artifacts import R3BScoringError, _rel, _require


def _rename_noreplace(source: Path, destination: Path) -> None:
    _require(source.is_dir() and not source.is_symlink(), "staging root differs")
    _require(
        not destination.exists() and not destination.is_symlink(),
        "destination appeared",
    )
    if sys.platform != "linux":
        raise R3BScoringError("renameat2 unavailable")
    libc = ctypes.CDLL(None, use_errno=True)
    function = getattr(libc, "renameat2", None)
    if function is None:
        raise R3BScoringError("renameat2 unavailable")
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    function.restype = ctypes.c_int
    result = function(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    if result != 0:
        error = ctypes.get_errno()
        raise R3BScoringError(
            "destination appeared" if error == errno.EEXIST else os.strerror(error)
        )
    _require(destination.is_dir() and not source.exists(), "promotion did not complete")


def _cleanup(root: Path) -> None:
    if not root.exists() or root.is_symlink():
        return
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        try:
            os.chmod(path, 0o755 if path.is_dir() else 0o644, follow_symlinks=False)
        except OSError:
            pass
    try:
        os.chmod(root, 0o755, follow_symlinks=False)
    except OSError:
        pass
    shutil.rmtree(root)


def _readonly(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        os.chmod(path, 0o555 if path.is_dir() else 0o444, follow_symlinks=False)
    os.chmod(root, 0o555, follow_symlinks=False)


def _fsync(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
        elif path.is_dir():
            fd = os.open(path, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    fd = os.open(root, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _publish(destination: Path, files: Mapping[str, bytes]) -> Path:
    _require(
        not destination.exists() and not destination.is_symlink(),
        "output destination exists",
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    relative_names = [_rel(name).as_posix() for name in files]
    _require(
        len(relative_names) == len(set(relative_names)),
        "duplicate publication path",
    )
    staging = Path(
        tempfile.mkdtemp(prefix=".r3b-terminal-", dir=str(destination.parent))
    )
    try:
        for name, data in files.items():
            path = staging / _rel(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        _readonly(staging)
        _fsync(staging)
        _rename_noreplace(staging, destination)
        _fsync_directory(destination.parent)
    except Exception:
        _cleanup(staging)
        raise
    return destination


def _private_stage(destination: Path, files: Mapping[str, bytes]) -> Path:
    _require(
        not destination.exists() and not destination.is_symlink(),
        "private stage exists",
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    relative_names = [_rel(name).as_posix() for name in files]
    _require(
        len(relative_names) == len(set(relative_names)),
        "duplicate staging path",
    )
    staging = Path(tempfile.mkdtemp(prefix=".r3b-stage-", dir=str(destination.parent)))
    try:
        for name, data in files.items():
            path = staging / _rel(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        _readonly(staging)
        _fsync(staging)
        _rename_noreplace(staging, destination)
        _fsync_directory(destination.parent)
    except Exception:
        _cleanup(staging)
        raise
    return destination

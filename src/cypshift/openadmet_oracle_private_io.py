"""Descriptor-relative private-root I/O for R5C scorer capabilities."""

from __future__ import annotations

import ctypes
import errno
import os
import secrets
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath


class OraclePrivateIOError(ValueError):
    """A private capability crossed the accepted filesystem boundary."""


def read_exact_root(root: Path, names: Sequence[str]) -> dict[str, bytes]:
    """Open one immutable flat root once and read exact regular leaves by FD."""

    expected = _flat_names(names)
    root_fd = open_directory_no_symlinks(root)
    try:
        if os.fstat(root_fd).st_mode & 0o222:
            raise OraclePrivateIOError("private root is writable")
        if set(os.listdir(root_fd)) != expected:
            raise OraclePrivateIOError("private root file set differs")
        return {name: read_regular_at(root_fd, name) for name in names}
    finally:
        os.close(root_fd)


def open_directory_no_symlinks(path: Path) -> int:
    """Walk every path component with O_NOFOLLOW and return its directory FD."""

    if ".." in path.parts:
        raise OraclePrivateIOError("private path contains traversal")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        fd = os.open("/" if path.is_absolute() else ".", flags)
    except OSError as exc:
        raise OraclePrivateIOError("cannot open private ancestry") from exc
    try:
        for part in path.parts:
            if part in {"/", ".", ""}:
                continue
            try:
                next_fd = os.open(part, flags, dir_fd=fd)
            except OSError as exc:
                raise OraclePrivateIOError("cannot open private ancestry") from exc
            os.close(fd)
            fd = next_fd
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OraclePrivateIOError("private root is not a directory")
        return fd
    except Exception:
        os.close(fd)
        raise


def read_regular_at(root_fd: int, name: str) -> bytes:
    """Read one immutable regular leaf through an already authenticated root FD."""

    return _read_regular_at(root_fd, name, require_readonly=True)


def read_stable_file(path: Path) -> bytes:
    """Read one source/runtime file through authenticated ancestry exactly once."""

    if _valid_part(path.name) is None:
        raise OraclePrivateIOError("source filename differs")
    parent_fd = open_directory_no_symlinks(path.parent)
    try:
        return _read_regular_at(parent_fd, path.name, require_readonly=False)
    finally:
        os.close(parent_fd)


def _read_regular_at(root_fd: int, name: str, *, require_readonly: bool) -> bytes:

    if not name or "/" in name or name in {".", ".."}:
        raise OraclePrivateIOError("private filename differs")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        fd = os.open(name, flags, dir_fd=root_fd)
    except OSError as exc:
        raise OraclePrivateIOError(f"cannot open private leaf: {name}") from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or (
            require_readonly and before.st_mode & 0o222
        ):
            raise OraclePrivateIOError(f"private leaf mode differs: {name}")
        chunks: list[bytes] = []
        while block := os.read(fd, 1024 * 1024):
            chunks.append(block)
        data = b"".join(chunks)
        after = os.fstat(fd)
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if before_identity != after_identity or len(data) != before.st_size:
            raise OraclePrivateIOError(f"private leaf changed: {name}")
        return data
    finally:
        os.close(fd)


def validate_output_root(output_root: Path) -> None:
    """Authenticate an existing output parent and require an absent simple leaf."""

    _leaf_name(output_root)
    parent_fd = open_directory_no_symlinks(output_root.parent)
    try:
        try:
            os.stat(output_root.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return
        raise OraclePrivateIOError("private output already exists")
    finally:
        os.close(parent_fd)


def validate_isolated_output_root(output_root: Path) -> None:
    """Require an empty authenticated parent for one independently handed root."""

    _leaf_name(output_root)
    parent_fd = open_directory_no_symlinks(output_root.parent)
    try:
        if os.listdir(parent_fd):
            raise OraclePrivateIOError("private capability parent is not isolated")
    finally:
        os.close(parent_fd)


def publish_readonly_tree(
    output_root: Path,
    payloads: Mapping[str, bytes],
    *,
    isolated_parent: bool = False,
) -> None:
    """Stage, FD-verify, and rename-noreplace one immutable private tree."""

    destination = _leaf_name(output_root)
    paths = _payload_paths(payloads)
    parent_fd = open_directory_no_symlinks(output_root.parent)
    stage_name = f".r5c-private-{secrets.token_hex(12)}"
    stage_created = False
    try:
        if isolated_parent and os.listdir(parent_fd):
            raise OraclePrivateIOError("private capability parent is not isolated")
        try:
            os.stat(destination, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise OraclePrivateIOError("private output already exists")
        os.mkdir(stage_name, 0o700, dir_fd=parent_fd)
        stage_created = True
        stage_fd = os.open(
            stage_name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        try:
            directories: set[tuple[str, ...]] = set()
            for relative, parts in paths.items():
                directory_fd = _ensure_directories(stage_fd, parts[:-1], directories)
                try:
                    _write_readonly(directory_fd, parts[-1], payloads[relative])
                finally:
                    if directory_fd != stage_fd:
                        os.close(directory_fd)
            observed = {
                relative: _read_relative(stage_fd, parts)
                for relative, parts in paths.items()
            }
            if observed != dict(payloads):
                raise OraclePrivateIOError("staged private bytes differ")
            for parts in sorted(directories, key=len, reverse=True):
                directory_fd = _open_relative_directory(stage_fd, parts)
                try:
                    os.fchmod(directory_fd, 0o555)
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            os.fchmod(stage_fd, 0o555)
            os.fsync(stage_fd)
        finally:
            os.close(stage_fd)
        _rename_noreplace(parent_fd, stage_name, destination)
        stage_created = False
        os.fsync(parent_fd)
    finally:
        if stage_created:
            _remove_tree_at(parent_fd, stage_name)
        os.close(parent_fd)


def remove_private_root(root: Path) -> None:
    """Remove one newly published private root through its authenticated parent."""

    name = _leaf_name(root)
    parent_fd = open_directory_no_symlinks(root.parent)
    try:
        _remove_tree_at(parent_fd, name)
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def _flat_names(names: Sequence[str]) -> set[str]:
    result = set(names)
    if len(result) != len(names) or any(_valid_part(name) is None for name in names):
        raise OraclePrivateIOError("private root filenames differ")
    return result


def _leaf_name(path: Path) -> str:
    if _valid_part(path.name) is None or path.parent == path:
        raise OraclePrivateIOError("private output path differs")
    return path.name


def _valid_part(value: str) -> str | None:
    return value if value and value not in {".", ".."} and "/" not in value else None


def _payload_paths(payloads: Mapping[str, bytes]) -> dict[str, tuple[str, ...]]:
    if not payloads:
        raise OraclePrivateIOError("private payload is empty")
    result: dict[str, tuple[str, ...]] = {}
    for relative, data in payloads.items():
        path = PurePosixPath(relative)
        parts = path.parts
        if (
            path.is_absolute()
            or not parts
            or any(_valid_part(part) is None for part in parts)
            or not isinstance(data, bytes)
        ):
            raise OraclePrivateIOError("private payload path differs")
        result[relative] = parts
    part_values = tuple(result.values())
    if len(set(part_values)) != len(part_values) or any(
        left == right[: len(left)]
        for left in part_values
        for right in part_values
        if left != right
    ):
        raise OraclePrivateIOError("private payload paths overlap")
    return result


def _ensure_directories(
    root_fd: int, parts: tuple[str, ...], created: set[tuple[str, ...]]
) -> int:
    current_fd = os.dup(root_fd)
    walked: list[str] = []
    try:
        for part in parts:
            walked.append(part)
            try:
                next_fd = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=current_fd,
                )
            except FileNotFoundError:
                os.mkdir(part, 0o700, dir_fd=current_fd)
                created.add(tuple(walked))
                next_fd = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=current_fd,
                )
            os.close(current_fd)
            current_fd = next_fd
        if not parts:
            os.close(current_fd)
            return root_fd
        return current_fd
    except Exception:
        os.close(current_fd)
        raise


def _write_readonly(directory_fd: int, name: str, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
    fd = os.open(name, flags, 0o600, dir_fd=directory_fd)
    try:
        view = memoryview(data)
        written = 0
        while written < len(view):
            written += os.write(fd, view[written:])
        os.fsync(fd)
        os.fchmod(fd, 0o444)
    finally:
        os.close(fd)


def _open_relative_directory(root_fd: int, parts: tuple[str, ...]) -> int:
    current_fd = os.dup(root_fd)
    try:
        for part in parts:
            next_fd = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except Exception:
        os.close(current_fd)
        raise


def _read_relative(root_fd: int, parts: tuple[str, ...]) -> bytes:
    directory_fd = _open_relative_directory(root_fd, parts[:-1])
    try:
        return read_regular_at(directory_fd, parts[-1])
    finally:
        os.close(directory_fd)


def _rename_noreplace(parent_fd: int, source: str, destination: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = libc.renameat2
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    if (
        renameat2(
            parent_fd,
            os.fsencode(source),
            parent_fd,
            os.fsencode(destination),
            1,
        )
        != 0
    ):
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise OraclePrivateIOError("private output already exists")
        raise OraclePrivateIOError("private no-replace promotion failed") from OSError(
            error, os.strerror(error)
        )


def _remove_tree_at(parent_fd: int, name: str) -> None:
    try:
        child_fd = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
    except FileNotFoundError:
        return
    try:
        os.fchmod(child_fd, 0o700)
        for child in os.listdir(child_fd):
            info = os.stat(child, dir_fd=child_fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                _remove_tree_at(child_fd, child)
            else:
                os.unlink(child, dir_fd=child_fd)
    finally:
        os.close(child_fd)
    os.rmdir(name, dir_fd=parent_fd)


__all__ = [
    "OraclePrivateIOError",
    "open_directory_no_symlinks",
    "publish_readonly_tree",
    "read_exact_root",
    "read_regular_at",
    "read_stable_file",
    "remove_private_root",
    "validate_isolated_output_root",
    "validate_output_root",
]

#!/usr/bin/env python3
"""Run one fresh synthetic R5C oracle state machine from a path-only config."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from typing import Any, cast

SCHEMA = "cypshift.openadmet_cyp_2026.r5c_synthetic_run_config.v1"
ROOT = Path(__file__).resolve().parents[1]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-runner-sha256", required=True)
    return parser


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError(f"{label} differs")
    return value


def _commit_oid(value: Any) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError("commit OID differs")
    return value


def _read_stable(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("run config file differs")
        data = bytearray()
        while block := os.read(fd, 1 << 20):
            data.extend(block)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise ValueError("run config changed while reading")
        return bytes(data)
    finally:
        os.close(fd)


def _path(value: Any, label: str) -> Path:
    if not isinstance(value, str):
        raise ValueError(f"{label} differs")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} differs")
    return path


def main() -> None:
    args = _parser().parse_args()
    observed = sha256(_read_stable(Path(__file__).resolve())).hexdigest()
    if _digest(args.expected_runner_sha256, "runner source") != observed:
        raise ValueError("runner source differs")
    source_root = (ROOT / "src").resolve()
    hostile = {
        str(Path(item).resolve())
        for item in os.environ.get("PYTHONPATH", "").split(os.pathsep)
        if item
    }
    sys.path[:] = [
        item
        for item in sys.path
        if not item or str(Path(item).resolve()) not in hostile
    ]
    sys.path.insert(0, str(source_root))
    os.environ["PYTHONPATH"] = str(source_root)
    os.environ["PYTHONNOUSERSITE"] = "1"
    runner = import_module("cypshift.openadmet_oracle_runner")
    transformation_io = import_module("cypshift.openadmet_transformation_io")
    for module in (runner, transformation_io):
        module_path = Path(cast(str, module.__file__)).resolve()
        if not module_path.is_relative_to(source_root):
            raise ValueError("repository module import root differs")

    data = _read_stable(args.config)
    config = transformation_io.strict_json_object(data, "R5C run config")
    canonical = (
        json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()
    if data != canonical or set(config) != {
        "schema_version",
        "source_paths",
        "source_receipts",
        "private_root",
        "terminal_root",
        "commit_oid",
        "expected_terminal_source_sha256",
        "expected_failure_source_sha256",
    }:
        raise ValueError("run config differs")
    paths = cast(dict[str, Any], config["source_paths"])
    receipts = cast(dict[str, Any], config["source_receipts"])
    result = runner.run_synthetic_oracle(
        runner.SyntheticRunInput(
            {
                name: _path(value, f"source path: {name}")
                for name, value in paths.items()
            },
            {
                name: _digest(value, f"source receipt: {name}")
                for name, value in receipts.items()
            },
            _path(config["private_root"], "private root"),
            _path(config["terminal_root"], "terminal root"),
            _commit_oid(config["commit_oid"]),
            _digest(config["expected_terminal_source_sha256"], "terminal source"),
            _digest(config["expected_failure_source_sha256"], "failure source"),
        )
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "terminal_root": str(result.terminal_root),
                "processes": [
                    {
                        "index": item.index,
                        "verb": item.verb,
                        "pid": item.pid,
                        "returncode": item.returncode,
                    }
                    for item in result.processes
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()

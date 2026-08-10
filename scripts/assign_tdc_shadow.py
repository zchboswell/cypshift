"""Generate label-free global assignments for TDC-CYP-shadow-v1."""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from cypshift.shadow import (
    ShadowContractError,
    ShadowResourceLimitError,
    assign_shadow_rows,
    clean_source_revision,
    write_assignment_failure_receipt,
)
from cypshift.shadow_watchdog import (
    FailureKind,
    supervise_assignment,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_RESOURCE_LIMIT_EXIT = 75
_RESOURCE_FAILURES = {
    "runtime_limit_exceeded",
    "peak_rss_limit_exceeded",
}


@dataclass(frozen=True, slots=True)
class _WorkerFailure:
    failure_kind: FailureKind
    elapsed_seconds: float
    peak_rss_gib: float | None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--implementation-contract", type=Path, required=True)
    parser.add_argument("--input-rows", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--worker-source-revision",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--worker-resource-status",
        type=Path,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    if args.worker_source_revision is None:
        if args.worker_resource_status is not None:
            raise ShadowContractError("resource status is worker-only")
        _run_supervised(
            args.contract,
            args.implementation_contract,
            args.input_rows,
            args.input_manifest,
            args.lock,
            args.out,
        )
        return

    _run_worker(
        args.contract,
        args.implementation_contract,
        args.input_rows,
        args.input_manifest,
        args.lock,
        args.out,
        args.worker_source_revision,
        args.worker_resource_status,
    )


def _run_supervised(
    contract_path: Path,
    implementation_contract_path: Path,
    input_rows_path: Path,
    input_manifest_path: Path,
    lock_path: Path,
    output_directory: Path,
) -> None:
    revision = clean_source_revision(_REPOSITORY_ROOT)
    if output_directory.exists():
        raise ShadowContractError(
            f"output path already exists: {output_directory}. "
            "Shadow artifacts are immutable."
        )
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    failure: _WorkerFailure | None = None

    prefix = f".{output_directory.name}.shadow-assignment-"
    with tempfile.TemporaryDirectory(
        prefix=prefix, dir=output_directory.parent
    ) as temporary:
        temporary_root = Path(temporary)
        staged_output = temporary_root / "assignment"
        worker_status = temporary_root / "resource_failure.json"
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--contract",
            str(contract_path),
            "--implementation-contract",
            str(implementation_contract_path),
            "--input-rows",
            str(input_rows_path),
            "--input-manifest",
            str(input_manifest_path),
            "--lock",
            str(lock_path),
            "--out",
            str(staged_output),
            "--worker-source-revision",
            revision,
            "--worker-resource-status",
            str(worker_status),
        ]
        outcome = supervise_assignment(command)
        if outcome.failure_kind is not None:
            failure = _WorkerFailure(
                outcome.failure_kind,
                outcome.elapsed_seconds,
                outcome.peak_rss_gib,
            )
        elif outcome.returncode == _RESOURCE_LIMIT_EXIT:
            failure = _read_worker_failure(worker_status)
        elif outcome.returncode != 0:
            raise SystemExit(outcome.returncode if outcome.returncode > 0 else 1)
        elif worker_status.exists():
            raise ShadowContractError("successful worker wrote a failure status")
        elif clean_source_revision(_REPOSITORY_ROOT) != revision:
            raise ShadowContractError("source revision changed during assignment")
        elif not staged_output.is_dir():
            raise ShadowContractError("successful worker produced no assignment")
        else:
            staged_output.rename(output_directory)
            return

    if failure is None:
        raise ShadowContractError("resource failure was not preserved")
    receipt = write_assignment_failure_receipt(
        contract_path,
        implementation_contract_path,
        input_rows_path,
        input_manifest_path,
        lock_path,
        output_directory,
        source_revision=revision,
        failure_kind=failure.failure_kind,
        elapsed_seconds=failure.elapsed_seconds,
        peak_rss_gib=failure.peak_rss_gib,
    )
    print(
        f"Shadow assignment blocked: {failure.failure_kind}; receipt: {receipt}",
        file=sys.stderr,
    )
    raise SystemExit(1)


def _run_worker(
    contract_path: Path,
    implementation_contract_path: Path,
    input_rows_path: Path,
    input_manifest_path: Path,
    lock_path: Path,
    output_directory: Path,
    worker_revision: str,
    worker_status: Path | None,
) -> None:
    if worker_status is None or worker_status.parent != output_directory.parent:
        raise ShadowContractError("worker resource status must share the staging root")
    revision = clean_source_revision(_REPOSITORY_ROOT)
    if worker_revision != revision:
        raise ShadowContractError("worker revision differs from clean Git HEAD")
    try:
        result = assign_shadow_rows(
            contract_path,
            implementation_contract_path,
            input_rows_path,
            input_manifest_path,
            lock_path,
            output_directory,
            source_revision=revision,
        )
    except ShadowResourceLimitError as exc:
        _write_worker_failure(worker_status, exc)
        raise SystemExit(_RESOURCE_LIMIT_EXIT) from exc
    print(
        f"Shadow assignment complete: {result.row_count} rows, "
        f"{result.scaffold_group_count} scaffold groups, and "
        f"{result.community_group_count} chemistry communities; zero labels used."
    )


def _write_worker_failure(path: Path, error: ShadowResourceLimitError) -> None:
    if error.failure_kind not in _RESOURCE_FAILURES:
        raise ShadowContractError("worker returned an unknown resource failure")
    value = {
        "failure_kind": error.failure_kind,
        "elapsed_seconds": error.elapsed_seconds,
        "peak_rss_gib": error.peak_rss_gib,
    }
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True)
            handle.write("\n")
    except OSError as exc:
        raise ShadowContractError(
            f"cannot preserve worker resource status: {exc}"
        ) from exc


def _read_worker_failure(path: Path) -> _WorkerFailure:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ShadowContractError("worker resource status is unavailable") from exc
    if not isinstance(value, dict) or set(value) != {
        "failure_kind",
        "elapsed_seconds",
        "peak_rss_gib",
    }:
        raise ShadowContractError("worker resource status has unexpected fields")
    failure_kind = value.get("failure_kind")
    elapsed = value.get("elapsed_seconds")
    peak = value.get("peak_rss_gib")
    if failure_kind not in _RESOURCE_FAILURES:
        raise ShadowContractError("worker returned an unknown resource failure")
    if (
        not isinstance(elapsed, (int, float))
        or isinstance(elapsed, bool)
        or not math.isfinite(float(elapsed))
        or float(elapsed) < 0
    ):
        raise ShadowContractError("worker elapsed time is invalid")
    if (
        not isinstance(peak, (int, float))
        or isinstance(peak, bool)
        or not math.isfinite(float(peak))
        or float(peak) < 0
    ):
        raise ShadowContractError("worker peak RSS is invalid")
    return _WorkerFailure(
        cast(FailureKind, failure_kind),
        float(elapsed),
        float(peak),
    )


if __name__ == "__main__":
    main()

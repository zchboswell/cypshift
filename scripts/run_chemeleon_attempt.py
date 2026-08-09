"""Run the single frozen, label-free CheMeleon prediction attempt."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any

from cypshift.chemeleon import CHEMELEON_INPUT_COLUMNS, CheMeleonInputError
from cypshift.chemeleon_attempt import (
    audit_training_overlap,
    canonicalize_predictions,
    docker_prediction_command,
    require_docker_ready,
    require_identical_predictions,
    resolve_prediction_column,
    validate_task_mapping,
    verify_model_files,
)

ATTEMPT_SCHEMA_VERSION = "cypshift.chemeleon_attempt.v1"
AGGREGATE_RECIPE = (
    "SHA-256 of UTF-8 path=sha256 lines sorted by path and joined with newline "
    "characters, without a trailing newline"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error(f"output path already exists: {args.out}")
    validate_task_mapping(args.input, args.contract)
    require_docker_ready()

    contract = _read_json(args.contract)
    attempt = _mapping(contract, "attempt")
    runtime_limit = _integer(attempt, "runtime_limit_minutes") * 60.0
    disk_limit = _integer(attempt, "temporary_disk_limit_gib") * 1024**3
    if shutil.disk_usage(args.out.parent).free < disk_limit:
        parser.error("free disk is below the frozen CheMeleon attempt limit")
    start = time.monotonic()
    deadline = start + runtime_limit
    step = "initialize"
    args.out.mkdir(parents=True)
    try:
        step = "download_model"
        source_root = args.out / "source"
        _download_model(contract, args.contract, source_root, deadline=deadline)
        verified = verify_model_files(source_root, args.contract)
        _require_disk_limit(args.out, disk_limit)

        step = "audit_overlap"
        overlap_root = args.out / "overlap"
        audit_training_overlap(
            args.input,
            source_root,
            args.contract,
            overlap_root,
            source_revision=args.source_revision,
        )

        image = _text(_mapping(contract, "execution_environment"), "image")
        step = "pull_environment"
        _run_logged(
            ["docker", "pull", "--platform", "linux/amd64", image],
            args.out / "docker_pull.log",
            timeout=_remaining(start, runtime_limit),
        )
        _require_disk_limit(
            args.out, disk_limit, image_size=_docker_image_size(image)
        )

        model_directory = source_root / "anvil_training"
        step = "smoke_probe"
        smoke_input = args.out / "smoke_input.csv"
        _write_smoke_input(args.input, smoke_input)
        smoke_root = args.out / "smoke"
        smoke_root.mkdir()
        smoke_raw = smoke_root / "raw_predictions.csv"
        _run_logged(
            docker_prediction_command(
                image=image,
                input_path=smoke_input,
                model_directory=model_directory,
                output_directory=smoke_root,
                output_name=smoke_raw.name,
            ),
            smoke_root / "container.log",
            timeout=_remaining(start, runtime_limit),
        )
        _validate_smoke(smoke_input, smoke_raw, contract)

        canonical_paths: list[Path] = []
        run_manifests: list[Path] = []
        run_runtimes: list[float] = []
        for run_number in (1, 2):
            step = f"full_inference_{run_number}"
            run_root = args.out / f"run{run_number}"
            run_root.mkdir()
            raw_path = run_root / "raw_predictions.csv"
            run_start = time.monotonic()
            _run_logged(
                docker_prediction_command(
                    image=image,
                    input_path=args.input,
                    model_directory=model_directory,
                    output_directory=run_root,
                    output_name=raw_path.name,
                ),
                run_root / "container.log",
                timeout=_remaining(start, runtime_limit),
            )
            run_runtime = time.monotonic() - run_start
            canonical_root = run_root / "canonical"
            manifest_path = canonicalize_predictions(
                args.input,
                raw_path,
                overlap_root,
                args.contract,
                canonical_root,
                source_revision=args.source_revision,
                runtime_seconds=run_runtime,
            )
            canonical_paths.append(canonical_root / "chemeleon_predictions.csv")
            run_manifests.append(manifest_path)
            run_runtimes.append(run_runtime)
            _require_disk_limit(
                args.out, disk_limit, image_size=_docker_image_size(image)
            )

        step = "repeat_check"
        require_identical_predictions(canonical_paths[0], canonical_paths[1])
        total_runtime = time.monotonic() - start
        if total_runtime > runtime_limit:
            raise CheMeleonInputError("CheMeleon attempt exceeded runtime limit")

        step = "write_receipt"
        retained = [
            source_root / "source_receipt.json",
            overlap_root / "chemeleon_training_overlap.csv",
            overlap_root / "chemeleon_overlap_manifest.json",
            smoke_input,
            smoke_raw,
            args.out / "docker_pull.log",
            smoke_root / "container.log",
            args.out / "run1" / "raw_predictions.csv",
            args.out / "run1" / "container.log",
            args.out / "run2" / "raw_predictions.csv",
            args.out / "run2" / "container.log",
            *canonical_paths,
            *run_manifests,
        ]
        outputs = {
            str(path.relative_to(args.out)): _file_hash(path) for path in retained
        }
        _write_json(
            args.out / "chemeleon_attempt_manifest.json",
            {
                "schema_version": ATTEMPT_SCHEMA_VERSION,
                "status": "complete",
                "source_revision": args.source_revision,
                "contract_sha256": _file_hash(args.contract),
                "input_sha256": _file_hash(args.input),
                "image": image,
                "verified_model_files": verified,
                "smoke_rows": 4,
                "full_inference_runs": 2,
                "full_prediction_rows_per_run": 7724,
                "canonical_repeat_byte_identical": True,
                "canonical_prediction_sha256": _file_hash(canonical_paths[0]),
                "run_runtime_seconds": run_runtimes,
                "total_runtime_seconds": total_runtime,
                "runtime_limit_seconds": runtime_limit,
                "temporary_disk_limit_bytes": disk_limit,
                "heldout_labels_parsed": 0,
                "model_fits": 0,
                "model_evaluations": 0,
                "outputs": outputs,
                "aggregate_recipe": AGGREGATE_RECIPE,
                "aggregate_sha256": _hash_mapping(outputs),
            },
        )
    except Exception as exc:
        retained_files = {
            str(path.relative_to(args.out)): _file_hash(path)
            for path in sorted(args.out.rglob("*"))
            if path.is_file() and path.name != "chemeleon_attempt_failure.json"
        }
        _write_json(
            args.out / "chemeleon_attempt_failure.json",
            {
                "schema_version": ATTEMPT_SCHEMA_VERSION,
                "status": "failed",
                "failed_step": step,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "source_revision": args.source_revision,
                "contract_sha256": _file_hash(args.contract),
                "input_sha256": _file_hash(args.input),
                "elapsed_seconds": time.monotonic() - start,
                "heldout_labels_parsed": 0,
                "model_evaluations": 0,
                "retained_files": retained_files,
                "retained_files_aggregate_sha256": _hash_mapping(retained_files),
            },
        )
        raise
    print(f"CheMeleon attempt complete: {args.out}")


def _download_model(
    contract: Mapping[str, Any],
    contract_path: Path,
    output: Path,
    *,
    deadline: float,
) -> None:
    model = _mapping(contract, "model")
    model_id = _text(model, "id")
    revision = _text(model, "revision")
    required = _mapping(model, "required_files")
    with tempfile.TemporaryDirectory(
        prefix=f".{output.name}-", dir=output.parent
    ) as temporary_name:
        temporary = Path(temporary_name)
        files: dict[str, str] = {}
        for name, expected in sorted(required.items()):
            if not isinstance(name, str) or not isinstance(expected, str):
                raise CheMeleonInputError("invalid required model file entry")
            destination = temporary / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            quoted_name = urllib.parse.quote(name, safe="/")
            url = (
                f"https://huggingface.co/{model_id}/resolve/{revision}/"
                f"{quoted_name}?download=true"
            )
            digest = sha256()
            try:
                request = urllib.request.Request(
                    url, headers={"User-Agent": "cypshift-chemeleon/0.2"}
                )
                with urllib.request.urlopen(request, timeout=120) as response:
                    with destination.open("xb") as handle:
                        for block in iter(lambda: response.read(1024 * 1024), b""):
                            if time.monotonic() > deadline:
                                raise CheMeleonInputError(
                                    "CheMeleon attempt exceeded runtime limit"
                                )
                            handle.write(block)
                            digest.update(block)
            except (OSError, urllib.error.URLError) as exc:
                raise CheMeleonInputError(f"cannot download {name}: {exc}") from exc
            if digest.hexdigest() != expected:
                raise CheMeleonInputError(f"download hash mismatch: {name}")
            files[name] = expected
        _write_json(
            temporary / "source_receipt.json",
            {
                "schema_version": "cypshift.chemeleon_source.v1",
                "model_id": model_id,
                "revision": revision,
                "contract_sha256": _file_hash(contract_path),
                "files": files,
            },
        )
        os.replace(temporary, output)


def _write_smoke_input(source: Path, destination: Path) -> None:
    rows = _read_csv(source)
    first_by_task: dict[str, dict[str, str]] = {}
    for row in rows:
        first_by_task.setdefault(row["task"], row)
    if len(first_by_task) != 4:
        raise CheMeleonInputError("smoke probe requires exactly four tasks")
    _write_csv(destination, CHEMELEON_INPUT_COLUMNS, list(first_by_task.values()))


def _validate_smoke(
    input_path: Path, prediction_path: Path, contract: Mapping[str, Any]
) -> None:
    inputs = _read_csv(input_path)
    outputs = _read_csv(prediction_path)
    if len(inputs) != 4 or len(outputs) != 4:
        raise CheMeleonInputError("smoke prediction row count mismatch")
    task_mapping = _mapping(contract, "task_mapping")
    for source, output in zip(inputs, outputs, strict=True):
        for field in CHEMELEON_INPUT_COLUMNS:
            if output.get(field) != source[field]:
                raise CheMeleonInputError("smoke prediction alignment mismatch")
        target = _text(_mapping(task_mapping, source["task"]), "model_output")
        column = resolve_prediction_column(output, target)
        try:
            prediction = float(output[column])
        except (KeyError, ValueError) as exc:
            raise CheMeleonInputError("smoke prediction is missing or invalid") from exc
        if not math.isfinite(prediction):
            raise CheMeleonInputError("smoke prediction is not finite")


def _run_logged(command: Sequence[str], log_path: Path, *, timeout: float) -> None:
    result = subprocess.run(
        list(command), capture_output=True, text=True, timeout=timeout, check=False
    )
    log_path.write_text(
        f"returncode={result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise CheMeleonInputError(f"command failed: {command[0]} {command[1]}")


def _remaining(start: float, limit: float) -> float:
    remaining = limit - (time.monotonic() - start)
    if remaining <= 0:
        raise CheMeleonInputError("CheMeleon attempt exceeded runtime limit")
    return remaining


def _docker_image_size(image: str) -> int:
    result = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Size}}", image],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise CheMeleonInputError("cannot inspect pinned Docker image size")
    try:
        return int(result.stdout.strip())
    except ValueError as exc:
        raise CheMeleonInputError("Docker image size is not an integer") from exc


def _require_disk_limit(root: Path, limit: int, *, image_size: int = 0) -> None:
    file_bytes = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
    if file_bytes + image_size > limit:
        raise CheMeleonInputError("CheMeleon attempt exceeded temporary disk limit")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = tuple(reader.fieldnames or ())
        missing = [field for field in CHEMELEON_INPUT_COLUMNS if field not in fields]
        if missing:
            raise CheMeleonInputError(f"missing input columns: {missing}")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise CheMeleonInputError("malformed CSV row width")
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CheMeleonInputError(f"{path} must contain an object")
    return value


def _mapping(value: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    result = value.get(field)
    if not isinstance(result, dict):
        raise CheMeleonInputError(f"contract requires object field {field!r}")
    return result


def _text(value: Mapping[str, Any], field: str) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result:
        raise CheMeleonInputError(f"contract requires text field {field!r}")
    return result


def _integer(value: Mapping[str, Any], field: str) -> int:
    result = value.get(field)
    if not isinstance(result, int) or isinstance(result, bool) or result < 0:
        raise CheMeleonInputError(f"contract requires integer field {field!r}")
    return result


def _write_csv(
    path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, str]]
) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _hash_mapping(values: Mapping[str, str]) -> str:
    material = "\n".join(f"{name}={values[name]}" for name in sorted(values))
    return sha256(material.encode()).hexdigest()


if __name__ == "__main__":
    main()

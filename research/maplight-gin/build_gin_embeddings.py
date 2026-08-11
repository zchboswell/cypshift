"""Freeze and reproduce the one MapLight GIN representation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPOSITORY_ROOT / "benchmarks/maplight_gin_contract.json"
IMPLEMENTATION_PATH = Path(__file__).resolve()
FEATURE_ROW_COLUMNS = (
    "task",
    "molecule_id",
    "source_row",
    "raw_structure_sha256",
    "standardized_structure_hash",
)
SHADOW_REQUIRED_COLUMNS = (
    "task",
    "molecule_id",
    "source_row",
    "raw_structure",
    "raw_structure_sha256",
    "standardized_structure_hash",
)
SCIENTIFIC_ZERO_KEYS = (
    "target_values_parsed",
    "model_fits",
    "predictions",
    "metric_evaluations",
    "public_test_rows_used",
    "public_test_labels_parsed",
    "public_test_family_task_slots_consumed",
    "challenge_assumptions_added",
)


class GinReproductionError(RuntimeError):
    """Raised when a frozen GIN reproduction invariant fails."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    def reject(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise GinReproductionError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GinReproductionError(f"cannot read JSON: {path}") from exc
    if not isinstance(value, dict):
        raise GinReproductionError(f"JSON root is not an object: {path}")
    return value


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GinReproductionError(message)


def _clean_revision() -> str:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise GinReproductionError("cannot verify Git revision") from exc
    _require(
        len(revision) == 40 and revision == revision.lower(), "invalid Git revision"
    )
    _require(not status, "tracked or non-ignored untracked worktree changes exist")
    return revision


def _contract() -> dict[str, Any]:
    contract = _load_json(CONTRACT_PATH)
    _require(
        contract.get("schema_version") == "cypshift.maplight_gin_contract.v3",
        "unexpected contract schema",
    )
    return contract


def _resolve(relative: str) -> Path:
    path = (REPOSITORY_ROOT / relative).resolve()
    _require(
        path == REPOSITORY_ROOT or REPOSITORY_ROOT in path.parents,
        "path escapes repository",
    )
    return path


def _verify_file(relative: str, expected_sha256: str) -> Path:
    path = _resolve(relative)
    _require(path.is_file(), f"required file missing: {relative}")
    _require(_sha256(path) == expected_sha256, f"hash mismatch: {relative}")
    return path


def _verify_inputs(contract: dict[str, Any]) -> dict[str, Path]:
    parents = contract["parents"]
    result = {
        name: _verify_file(record["path"], record["sha256"])
        for name, record in parents.items()
    }
    source = contract["source"]
    source_root = _resolve(source["root"])
    _require(source_root.is_dir(), "MapLight source root missing")
    _require(
        not (source_root.stat().st_mode & 0o222), "MapLight source root is writable"
    )
    source_file = source_root / "maplight_gnn.py"
    _require(
        _sha256(source_file) == source["maplight_gnn_sha256"], "MapLight source drift"
    )
    _verify_file(
        contract["environment"]["project_path"],
        contract["environment"]["project_sha256"],
    )
    _verify_file(
        contract["environment"]["lock_path"], contract["environment"]["lock_sha256"]
    )
    _verify_file(
        contract["environment"]["python_version_path"],
        contract["environment"]["python_version_sha256"],
    )
    result["source_root"] = source_root
    return result


def _verify_environment(contract: dict[str, Any]) -> dict[str, str]:
    env = contract["environment"]
    observed_python = ".".join(str(part) for part in sys.version_info[:3])
    _require(observed_python == env["python"], "Python version drift")
    _require(
        platform.system() == "Darwin" and platform.machine() == "arm64",
        "platform drift",
    )
    observed: dict[str, str] = {}
    for name, expected in env["required_versions"].items():
        distribution = "scikit-learn" if name == "scikit-learn" else name
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError as exc:
            raise GinReproductionError(f"missing distribution: {distribution}") from exc
        _require(version == expected, f"version drift: {distribution}")
        observed[name] = version
    os.environ["DGLBACKEND"] = "pytorch"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    return observed


def _output_root(contract: dict[str, Any], operation: str, attempt: int | None) -> Path:
    outputs = contract["outputs"]
    if operation == "weight":
        return _resolve(outputs["weight_root"])
    if operation == "parity":
        return _resolve(outputs["parity_root"])
    _require(operation == "build" and attempt in (1, 2), "invalid build attempt")
    return _resolve(outputs[f"build_{attempt}_root"])


def _make_staging(output: Path) -> Path:
    _require(not output.exists(), f"output already exists: {output}")
    blocker = output.with_name(output.name + "-blocker")
    _require(not blocker.exists(), f"blocker already exists: {blocker}")
    output.parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))


def _promote(staging: Path, output: Path) -> None:
    for path in staging.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
        elif path.is_dir():
            path.chmod(0o555)
    staging.chmod(0o555)
    staging.rename(output)


def _write_failure(
    contract: dict[str, Any],
    output: Path,
    operation: str,
    attempt: int | None,
    revision: str | None,
    exc: BaseException,
    accounting: dict[str, int],
) -> None:
    blocker = output.with_name(output.name + "-blocker")
    if output.exists() or blocker.exists():
        return
    blocker.mkdir(parents=True)
    receipt = {
        "schema_version": "cypshift.maplight_gin_failure.v1",
        "operation": operation,
        "attempt": attempt,
        "contract_sha256": _sha256(CONTRACT_PATH),
        "source_revision": revision,
        "implementation_sha256": _sha256(IMPLEMENTATION_PATH),
        "failure": {
            "exception_class": type(exc).__name__,
            "message": str(exc)[:500],
        },
        "accounting": accounting,
        "claim_boundary": "No predictive or public-test claim is supported by this failure.",
    }
    receipt_path = blocker / "failure_receipt.json"
    receipt_path.write_bytes(_json_bytes(receipt))
    receipt_path.chmod(0o444)
    blocker.chmod(0o555)


def _download(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "cypshift-reproduction/1"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        return response.read()


def _freeze_weight(contract: dict[str, Any], output: Path, revision: str) -> None:
    staging = _make_staging(output)
    try:
        weight = contract["weight"]
        metadata_bytes = _download(weight["metadata_url"])
        model_bytes = _download(weight["model_url"])
        _require(
            len(metadata_bytes) == weight["metadata_size_bytes"],
            "metadata size mismatch",
        )
        _require(
            _bytes_sha256(metadata_bytes) == weight["metadata_sha256"],
            "metadata hash mismatch",
        )
        _require(len(model_bytes) == weight["model_size_bytes"], "model size mismatch")
        _require(
            _bytes_sha256(model_bytes) == weight["model_sha256"], "model hash mismatch"
        )
        metadata = json.loads(metadata_bytes)
        _require(
            metadata.get("sha256sum") == weight["model_sha256"],
            "metadata model hash mismatch",
        )
        artifact = (
            staging
            / weight["store_group"]
            / weight["name"]
            / str(weight["store_version"])
        )
        artifact.mkdir(parents=True)
        (artifact / "metadata.json").write_bytes(metadata_bytes)
        (artifact / "model.save").write_bytes(model_bytes)
        receipt = {
            "schema_version": "cypshift.maplight_gin_weight.v1",
            "contract_sha256": _sha256(CONTRACT_PATH),
            "source_revision": revision,
            "implementation_sha256": _sha256(IMPLEMENTATION_PATH),
            "name": weight["name"],
            "metadata": {
                "path": f"{weight['store_group']}/{weight['name']}/{weight['store_version']}/metadata.json",
                "size_bytes": len(metadata_bytes),
                "sha256": _bytes_sha256(metadata_bytes),
            },
            "model": {
                "path": f"{weight['store_group']}/{weight['name']}/{weight['store_version']}/model.save",
                "size_bytes": len(model_bytes),
                "sha256": _bytes_sha256(model_bytes),
                "loaded": False,
            },
            "redistributed": False,
            "eligibility": contract["rights_and_provenance"],
            "accounting": {
                "weight_files_downloaded": 1,
                "weight_bytes_persisted": len(model_bytes),
                **{key: 0 for key in SCIENTIFIC_ZERO_KEYS},
            },
        }
        (staging / "weight_receipt.json").write_bytes(_json_bytes(receipt))
        _promote(staging, output)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _write_npy(path: Path, array: Any) -> None:
    import numpy as np

    with path.open("wb") as handle:
        np.lib.format.write_array(
            handle, np.asarray(array), version=(1, 0), allow_pickle=False
        )


def _load_npy(path: Path, rows: int) -> Any:
    import numpy as np

    with path.open("rb") as handle:
        version = np.lib.format.read_magic(handle)
    _require(version == (1, 0), f"NPY version drift: {path}")
    array = np.load(path, allow_pickle=False)
    _require(array.shape == (rows, 300), f"embedding shape mismatch: {path}")
    _require(array.dtype == np.float64, f"embedding dtype mismatch: {path}")
    _require(array.flags.c_contiguous, f"embedding is not C contiguous: {path}")
    _require(bool(np.isfinite(array).all()), f"non-finite embedding: {path}")
    return array


def _verify_weight(contract: dict[str, Any], weight_root: Path) -> dict[str, Any]:
    receipt_path = weight_root / "weight_receipt.json"
    receipt = _load_json(receipt_path)
    _require(
        receipt.get("schema_version") == "cypshift.maplight_gin_weight.v1",
        "weight receipt schema",
    )
    weight = contract["weight"]
    _require(
        _sha256(receipt_path) == weight["frozen_receipt_sha256"], "weight receipt drift"
    )
    _require(
        receipt.get("contract_sha256") == weight["origin_contract_sha256"],
        "weight origin contract drift",
    )
    artifact = (
        weight_root
        / weight["store_group"]
        / weight["name"]
        / str(weight["store_version"])
    )
    _require(
        _sha256(artifact / "metadata.json") == weight["metadata_sha256"],
        "metadata drift",
    )
    _require(_sha256(artifact / "model.save") == weight["model_sha256"], "model drift")
    return receipt


def _fixture_rows(path: Path) -> tuple[list[str], list[int]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _require(
            reader.fieldnames == ["fixture_id", "pandas_index", "raw_smiles"],
            "fixture schema drift",
        )
        rows = list(reader)
    return [row["raw_smiles"] for row in rows], [
        int(row["pandas_index"]) for row in rows
    ]


def _embed(
    raw_smiles: list[str], pandas_indices: list[int] | None, source_root: Path | None
) -> Any:
    import numpy as np
    import pandas as pd
    import torch
    from rdkit import Chem

    torch.set_num_threads(1)
    torch.manual_seed(20260815)
    torch.use_deterministic_algorithms(True)
    molecules = pd.Series(raw_smiles, index=pandas_indices).apply(Chem.MolFromSmiles)
    _require(not molecules.isna().any(), "RDKit failed to parse a GIN input")
    if source_root is not None:
        source_path = source_root / "maplight_gnn.py"
        spec = importlib.util.spec_from_file_location(
            "frozen_maplight_gnn", source_path
        )
        _require(
            spec is not None and spec.loader is not None, "cannot load MapLight source"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        values = module.get_gin_supervised_masking(molecules)
    else:
        from molfeat.trans.pretrained import PretrainedDGLTransformer

        transformer = PretrainedDGLTransformer(
            kind="gin_supervised_masking", dtype=float
        )
        values = transformer(molecules)
    array = np.ascontiguousarray(values, dtype=np.float64)
    _require(array.shape == (len(raw_smiles), 300), "GIN returned the wrong shape")
    _require(bool(np.isfinite(array).all()), "GIN returned a non-finite value")
    return array


def _worker(args: argparse.Namespace) -> int:
    contract = _contract()
    inputs = _verify_inputs(contract)
    _verify_environment(contract)
    weight_root = Path(args.weight_root).resolve()
    _verify_weight(contract, weight_root)
    os.environ["MOLFEAT_MODEL_STORE_BUCKET"] = str(weight_root)
    raw_smiles, indices = _fixture_rows(inputs["fixture"])
    source_root = inputs["source_root"] if args.worker_kind == "upstream" else None
    array = _embed(raw_smiles, indices, source_root)
    output = Path(args.worker_output).resolve()
    output.mkdir(parents=True)
    _write_npy(output / "gin.npy", array)
    receipt = {
        "worker": args.worker_kind,
        "rows": len(raw_smiles),
        "shape": list(array.shape),
        "dtype": str(array.dtype),
        "element_sha256": _bytes_sha256(array.tobytes(order="C")),
        "npy_sha256": _sha256(output / "gin.npy"),
    }
    (output / "worker_receipt.json").write_bytes(_json_bytes(receipt))
    return 0


def _parity(contract: dict[str, Any], output: Path, revision: str) -> None:
    weight_root = _output_root(contract, "weight", None)
    weight_receipt = _verify_weight(contract, weight_root)
    staging = _make_staging(output)
    work = Path(tempfile.mkdtemp(prefix=".gin-parity-workers-", dir=output.parent))
    started = time.monotonic()
    try:
        arrays: dict[str, Any] = {}
        records: dict[str, Any] = {}
        for name in ("upstream", "local_a", "local_b"):
            worker_output = work / name
            command = [
                sys.executable,
                str(IMPLEMENTATION_PATH),
                "--worker-kind",
                "upstream" if name == "upstream" else "local",
                "--worker-output",
                str(worker_output),
                "--weight-root",
                str(weight_root),
            ]
            subprocess.run(command, cwd=REPOSITORY_ROOT, check=True, timeout=600)
            arrays[name] = _load_npy(
                worker_output / "gin.npy", contract["parents"]["fixture"]["rows"]
            )
            records[name] = _load_json(worker_output / "worker_receipt.json")
        import numpy as np

        _require(
            np.array_equal(arrays["upstream"], arrays["local_a"]),
            "upstream/local parity mismatch",
        )
        _require(
            np.array_equal(arrays["local_a"], arrays["local_b"]),
            "local repeat mismatch",
        )
        _write_npy(staging / "gin.npy", arrays["local_a"])
        retained = _load_npy(
            staging / "gin.npy", contract["parents"]["fixture"]["rows"]
        )
        receipt = {
            "schema_version": "cypshift.maplight_gin_parity.v1",
            "contract_sha256": _sha256(CONTRACT_PATH),
            "source_revision": revision,
            "implementation_sha256": _sha256(IMPLEMENTATION_PATH),
            "weight_receipt_sha256": _sha256(weight_root / "weight_receipt.json"),
            "weight_sha256": weight_receipt["model"]["sha256"],
            "workers": records,
            "retained": {
                "path": "gin.npy",
                "shape": list(retained.shape),
                "dtype": str(retained.dtype),
                "element_sha256": _bytes_sha256(retained.tobytes(order="C")),
                "npy_sha256": _sha256(staging / "gin.npy"),
            },
            "runtime_seconds": time.monotonic() - started,
            "accounting": {
                "fixture_processes_completed": 3,
                "fixture_rows_loaded": 24,
                "embedding_arrays_generated": 3,
                "retained_arrays": 1,
                **{key: 0 for key in SCIENTIFIC_ZERO_KEYS},
            },
            "claim_boundary": "Synthetic exact-array parity only; no real-row or predictive claim.",
        }
        (staging / "parity_receipt.json").write_bytes(_json_bytes(receipt))
        shutil.rmtree(work)
        _promote(staging, output)
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return fieldnames, rows


def _real_rows(
    inputs: dict[str, Path],
) -> tuple[bytes, list[dict[str, str]], list[str], list[str]]:
    feature_bytes = inputs["fixed_feature_rows"].read_bytes()
    feature_fields, feature_rows = _read_csv(inputs["fixed_feature_rows"])
    _require(feature_fields == list(FEATURE_ROW_COLUMNS), "feature-row schema drift")
    shadow_fields, shadow_rows = _read_csv(inputs["shadow_rows"])
    _require(
        all(column in shadow_fields for column in SHADOW_REQUIRED_COLUMNS),
        "shadow schema drift",
    )
    _require(len(feature_rows) == len(shadow_rows) == 30038, "real row count drift")
    shadow_by_id = {row["molecule_id"]: row for row in shadow_rows}
    _require(len(shadow_by_id) == len(shadow_rows), "duplicate shadow molecule ID")
    raw_by_hash: dict[str, str] = {}
    row_raw_hashes: list[str] = []
    for feature_row in feature_rows:
        shadow = shadow_by_id.get(feature_row["molecule_id"])
        _require(shadow is not None, "feature/shadow identity mismatch")
        for key in (
            "task",
            "source_row",
            "raw_structure_sha256",
            "standardized_structure_hash",
        ):
            _require(feature_row[key] == shadow[key], f"feature/shadow {key} mismatch")
        raw = shadow["raw_structure"]
        raw_hash = feature_row["raw_structure_sha256"]
        _require(
            _bytes_sha256(raw.encode("utf-8")) == raw_hash,
            "raw structure hash mismatch",
        )
        prior = raw_by_hash.setdefault(raw_hash, raw)
        _require(prior == raw, "raw SHA collision")
        row_raw_hashes.append(raw_hash)
    unique_hashes = sorted(raw_by_hash)
    _require(len(unique_hashes) == 15399, "unique exact-raw count drift")
    return (
        feature_bytes,
        feature_rows,
        [raw_by_hash[key] for key in unique_hashes],
        row_raw_hashes,
    )


def _verify_parity(contract: dict[str, Any]) -> dict[str, Any]:
    root = _output_root(contract, "parity", None)
    receipt = _load_json(root / "parity_receipt.json")
    _require(
        receipt.get("schema_version") == "cypshift.maplight_gin_parity.v1",
        "parity schema",
    )
    _require(
        receipt.get("contract_sha256") == _sha256(CONTRACT_PATH),
        "parity contract drift",
    )
    _load_npy(root / "gin.npy", 8)
    _require(
        receipt["retained"]["npy_sha256"] == _sha256(root / "gin.npy"),
        "parity NPY drift",
    )
    return receipt


def _verify_build(contract: dict[str, Any], root: Path) -> dict[str, Any]:
    manifest = _load_json(root / "gin_manifest.json")
    _require(
        manifest.get("schema_version") == "cypshift.maplight_gin_features.v1",
        "build schema",
    )
    _require(
        manifest.get("contract_sha256") == _sha256(CONTRACT_PATH),
        "build contract drift",
    )
    _require(
        _sha256(root / "feature_rows.csv")
        == contract["parents"]["fixed_feature_rows"]["sha256"],
        "build row drift",
    )
    _load_npy(root / "gin.npy", 30038)
    _require(
        manifest["gin"]["npy_sha256"] == _sha256(root / "gin.npy"), "build NPY drift"
    )
    return manifest


def _multi_raw_audit(
    feature_rows: list[dict[str, str]], embeddings: Any
) -> dict[str, Any]:
    import numpy as np

    groups: dict[str, dict[str, Any]] = {}
    for index, feature_row in enumerate(feature_rows):
        standard_hash = feature_row["standardized_structure_hash"]
        raw_hash = feature_row["raw_structure_sha256"]
        groups.setdefault(standard_hash, {}).setdefault(raw_hash, embeddings[index])
    audited: list[dict[str, Any]] = []
    exact_equal = 0
    global_max = 0.0
    for standard_hash, raw_map in sorted(groups.items()):
        if len(raw_map) < 2:
            continue
        vectors = list(raw_map.values())
        reference = vectors[0]
        maximum = max(
            float(np.max(np.abs(reference - vector))) for vector in vectors[1:]
        )
        equal = all(np.array_equal(reference, vector) for vector in vectors[1:])
        exact_equal += int(equal)
        global_max = max(global_max, maximum)
        audited.append(
            {
                "standardized_structure_hash": standard_hash,
                "raw_forms": len(raw_map),
                "exactly_equal": equal,
                "maximum_absolute_difference": maximum,
            }
        )
    _require(len(audited) == 41, "multi-raw group count drift")
    return {
        "groups": 41,
        "exactly_equal_groups": exact_equal,
        "maximum_absolute_difference": global_max,
        "records": audited,
    }


def _build(
    contract: dict[str, Any],
    inputs: dict[str, Path],
    output: Path,
    revision: str,
    attempt: int,
) -> None:
    weight_root = _output_root(contract, "weight", None)
    _verify_parity(contract)
    _verify_weight(contract, weight_root)
    if attempt == 2:
        prior_root = _output_root(contract, "build", 1)
        _verify_build(contract, prior_root)
        _require(
            not prior_root.with_name(prior_root.name + "-blocker").exists(),
            "build 1 blocker exists",
        )
    feature_bytes, feature_rows, unique_raw, row_hashes = _real_rows(inputs)
    os.environ["MOLFEAT_MODEL_STORE_BUCKET"] = str(weight_root)
    started = time.monotonic()
    unique_embeddings = _embed(unique_raw, None, None)
    import numpy as np

    unique_hashes = sorted(set(row_hashes))
    index_by_hash = {raw_hash: index for index, raw_hash in enumerate(unique_hashes)}
    expanded = np.ascontiguousarray(
        np.stack(
            [unique_embeddings[index_by_hash[raw_hash]] for raw_hash in row_hashes]
        ),
        dtype=np.float64,
    )
    _require(expanded.shape == (30038, 300), "expanded GIN shape mismatch")
    audit = _multi_raw_audit(feature_rows, expanded)
    staging = _make_staging(output)
    try:
        (staging / "feature_rows.csv").write_bytes(feature_bytes)
        _write_npy(staging / "gin.npy", expanded)
        retained = _load_npy(staging / "gin.npy", 30038)
        runtime = time.monotonic() - started
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**3)
        _require(
            runtime <= contract["resource_limits"]["wall_seconds_per_operation"],
            "runtime cap exceeded",
        )
        _require(
            peak_rss <= contract["resource_limits"]["peak_rss_gib"], "RSS cap exceeded"
        )
        manifest = {
            "schema_version": "cypshift.maplight_gin_features.v1",
            "attempt": attempt,
            "contract_sha256": _sha256(CONTRACT_PATH),
            "source_revision": revision,
            "implementation_sha256": _sha256(IMPLEMENTATION_PATH),
            "weight_receipt_sha256": _sha256(weight_root / "weight_receipt.json"),
            "parity_receipt_sha256": _sha256(
                _output_root(contract, "parity", None) / "parity_receipt.json"
            ),
            "fixed_feature_manifest_sha256": contract["parents"][
                "fixed_feature_manifest"
            ]["sha256"],
            "rows": {
                "path": "feature_rows.csv",
                "rows": 30038,
                "unique_exact_raw_structures": 15399,
                "sha256": _sha256(staging / "feature_rows.csv"),
            },
            "gin": {
                "path": "gin.npy",
                "shape": list(retained.shape),
                "dtype": str(retained.dtype),
                "element_sha256": _bytes_sha256(retained.tobytes(order="C")),
                "npy_sha256": _sha256(staging / "gin.npy"),
                "nonfinite_values": int(
                    retained.size - np.count_nonzero(np.isfinite(retained))
                ),
            },
            "multi_raw_audit": audit,
            "environment": _verify_environment(contract),
            "runtime_seconds": runtime,
            "peak_rss_gib": peak_rss,
            "accounting": {
                "feature_builds_attempted": 1,
                "feature_builds_completed": 1,
                "source_rows_parsed": 30038,
                "exact_raw_featurizations": 15399,
                "embedding_arrays_persisted": 1,
                **{key: 0 for key in SCIENTIFIC_ZERO_KEYS},
            },
            "claim_boundary": "Label-free pretrained-transfer features only; no predictive, clean-zero-shot, public-test, or challenge claim.",
        }
        (staging / "gin_manifest.json").write_bytes(_json_bytes(manifest))
        _clean_revision()
        _verify_weight(contract, weight_root)
        _verify_parity(contract)
        if attempt == 2:
            prior_root = _output_root(contract, "build", 1)
            _require(
                (prior_root / "feature_rows.csv").read_bytes()
                == (staging / "feature_rows.csv").read_bytes(),
                "feature-row repeat mismatch",
            )
            _require(
                (prior_root / "gin.npy").read_bytes()
                == (staging / "gin.npy").read_bytes(),
                "GIN repeat mismatch",
            )
        _promote(staging, output)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _run(operation: str, attempt: int | None) -> int:
    contract = _contract()
    output = _output_root(contract, operation, attempt)
    revision: str | None = None
    accounting = {key: 0 for key in SCIENTIFIC_ZERO_KEYS}
    try:
        revision = _clean_revision()
        inputs = _verify_inputs(contract)
        _verify_environment(contract)
        seconds = int(contract["resource_limits"]["wall_seconds_per_operation"])
        signal.signal(
            signal.SIGALRM,
            lambda _signum, _frame: (_ for _ in ()).throw(
                TimeoutError("wall-time cap exceeded")
            ),
        )
        signal.alarm(seconds)
        if operation == "weight":
            _freeze_weight(contract, output, revision)
        elif operation == "parity":
            _parity(contract, output, revision)
        else:
            _build(contract, inputs, output, revision, int(attempt))
        signal.alarm(0)
        return 0
    except BaseException as exc:
        signal.alarm(0)
        _write_failure(contract, output, operation, attempt, revision, exc, accounting)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", nargs="?", choices=("weight", "parity", "build"))
    parser.add_argument("--attempt", type=int, choices=(1, 2))
    parser.add_argument(
        "--worker-kind", choices=("upstream", "local"), help=argparse.SUPPRESS
    )
    parser.add_argument("--worker-output", help=argparse.SUPPRESS)
    parser.add_argument("--weight-root", help=argparse.SUPPRESS)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.worker_kind:
        return _worker(args)
    _require(args.operation is not None, "operation is required")
    _require(
        (args.operation == "build") == (args.attempt is not None),
        "--attempt is required only for build",
    )
    return _run(args.operation, args.attempt)


if __name__ == "__main__":
    raise SystemExit(main())

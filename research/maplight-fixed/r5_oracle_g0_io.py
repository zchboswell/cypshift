"""Receipt, capability, runtime, and publication boundary for R5C G0."""

from __future__ import annotations

import csv
import ctypes
import errno
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import shutil
import stat
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
LOCK = SCRIPT_DIR / "uv.lock"
CONTRACT = ROOT / "benchmarks/openadmet_cyp_2026/oracle_experiment_contract_v2.json"
CONTRACT_SHA256: Final = (
    "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
)
PARENT_CONTRACT_SHA256: Final = (
    "c1d7a66c4f479339b30c2006e4250381cb213d665d4902c71d4c4edbd347e8bf"
)
LOCK_SHA256: Final = "99e72821b69d9bb943a6e32adc7e0dec0e46c6d32df090241d4fb9296a4195d8"
R3C_TERMINAL_MANIFEST_SHA256: Final = (
    "a2029e12231a22415900c55303ec5413b395aedc15d565ef7b4e650196b3277c"
)
PARAMETER_SHA256: Final = (
    "c56235a54a883a9a4488f1c8779f9013dae777af0f99cd92c9da1c4f51e61757"
)
PARAMETER_RECORD_SHA256: Final = (
    "0c912e0d06d0d24d58bdc0529d6b14d1706d6a933445885be881f95ba3678cb9"
)
MODEL_ID: Final = "TRACE-G0-MAPL-FIXED"
SYSTEM_ID: Final = "G0"

MAP_ARRAYS: Final = (
    ("maplight_morgan_count.npy", 1024, "int8"),
    ("maplight_avalon_count.npy", 1024, "int8"),
    ("maplight_erg.npy", 315, "<f8"),
    ("maplight_rdkit_descriptors.npy", 200, "<f8"),
)
MORGAN_FILE: Final = ("morgan_binary.npy", 4096, "uint8")
MODEL_FILES: Final = (
    "manifest.json",
    "molecules.csv",
    "folds.csv",
    "public_episode_queries.csv",
    "transformation_pairs.csv",
    "episode_transformations.csv",
    *(name for name, _, _ in MAP_ARRAYS),
    MORGAN_FILE[0],
)
EPISODE_FILES: Final = (
    "manifest.json",
    "training_points.csv",
    "episode_anchor_context.csv",
)
ACCOUNTING_FIELDS: Final = (
    "direct_target_values_parsed",
    "anchor_labels_exposed_to_models",
    "query_truth_values_opened_by_scorers",
    "maplight_model_fits",
    "ridge_model_fits",
    "hierarchy_fits",
    "predictions_frozen",
    "internal_absolute_error_evaluations",
    "blinded_test_files_opened",
    "tdi_files_opened",
    "official_metric_calls",
    "submissions_created",
    "transductive_relationships",
    "inferred_anchor_candidate_pools",
)
DENIED_AUTHORITY: Final = {
    "oracle_evidence": False,
    "inferred_anchor_contract": False,
    "model_fits": False,
    "predictions": False,
    "internal_metrics": False,
    "official_st_rae": False,
    "test_access": False,
    "tdi": False,
    "submission": False,
    "transduction": False,
}
FORBIDDEN_PUBLIC_FIELDS: Final = [
    "selector_cyp_truth",
    "query_truth",
    "query_availability",
    "anchor_value",
    "target",
    "loss",
    "score",
]
ROOT_ACCOUNTING: Final = {
    "root_families": 4,
    "model_public_roots": 1,
    "cell_target_roots": 75,
    "c3_target_roots": 75,
    "sealed_scorer_roots": 75,
    "total_capability_roots": 226,
}
MODEL_MANIFEST_FIELDS: Final = {
    "schema_version",
    "status",
    "contract_sha256",
    "parent_contract_sha256",
    "root",
    "fixed_oof_system_id",
    "current_cell_scope",
    "capability_root_accounting",
    "accounting_scope",
    "operation_accounting",
    "projector_operation_accounting",
    "output_receipts",
    "source_receipts",
    "source_bundle_binding",
    "authority",
    "forbidden_fields",
}
EPISODE_MANIFEST_FIELDS: Final = {
    "schema_version",
    "status",
    "contract_sha256",
    "parent_contract_sha256",
    "root",
    "view_builder_source_sha256",
    "model_public_manifest_sha256",
    "source_cell_target_manifest_sha256",
    "source_bundle_binding",
    "scope",
    "episode",
    "r3c_parameter_source",
    "output_receipts",
    "operation_accounting",
    "authority",
}
SCOPE_FIELDS: Final = {
    "stage",
    "repeat",
    "current_outer_validation_fold",
    "inner_fold",
    "episode_outer_fold",
}

ACCEPTED_PARAMETERS: Final[dict[str, Any]] = {
    "auto_class_weights": "None",
    "bayesian_matrix_reg": 0.10000000149011612,
    "best_model_min_trees": 1,
    "boost_from_average": True,
    "boosting_type": "Plain",
    "bootstrap_type": "MVS",
    "border_count": 254,
    "classes_count": 0,
    "depth": 6,
    "eval_fraction": 0,
    "eval_metric": "MAE",
    "feature_border_type": "GreedyLogSum",
    "force_unit_auto_pair_weights": False,
    "grow_policy": "SymmetricTree",
    "iterations": 1000,
    "l2_leaf_reg": 3,
    "leaf_estimation_backtracking": "AnyImprovement",
    "leaf_estimation_iterations": 1,
    "leaf_estimation_method": "Exact",
    "learning_rate": 0.029999999329447743,
    "loss_function": "MAE",
    "max_leaves": 64,
    "min_data_in_leaf": 1,
    "model_shrink_mode": "Constant",
    "model_shrink_rate": 0,
    "model_size_reg": 0.5,
    "nan_mode": "Min",
    "penalties_coefficient": 1,
    "pool_metainfo_options": {"tags": {}},
    "posterior_sampling": False,
    "random_score_type": "NormalWithModelSizeDecrease",
    "random_seed": 1,
    "random_strength": 2,
    "rsm": 1,
    "sampling_frequency": "PerTree",
    "score_function": "Cosine",
    "sparse_features_conflict_fraction": 0,
    "subsample": 0.800000011920929,
    "task_type": "CPU",
    "use_best_model": False,
}
ACCEPTED_PARAMETER_RECORD: Final = {
    "canonical_get_all_params_json": ACCEPTED_PARAMETERS,
    "canonical_get_all_params_sha256": PARAMETER_SHA256,
    "system_id": MODEL_ID,
}
R3C_PARAMETER_SOURCE: Final = {
    "r3c_terminal_manifest_sha256": R3C_TERMINAL_MANIFEST_SHA256,
    "parameter_record_sha256": PARAMETER_RECORD_SHA256,
    "parameter_record": ACCEPTED_PARAMETER_RECORD,
}


class G0Error(RuntimeError):
    """A G0 receipt, capability, runtime, or publication invariant failed."""


def require(ok: bool, message: str) -> None:
    if not ok:
        raise G0Error(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def json_object(data: bytes, label: str) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, f"duplicate JSON key: {label}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(value)

    try:
        value = json.loads(
            data.decode(), object_pairs_hook=pairs, parse_constant=reject_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise G0Error(f"invalid JSON: {label}") from exc
    require(
        isinstance(value, dict) and json_bytes(value) == data,
        f"noncanonical JSON: {label}",
    )
    return cast(dict[str, Any], value)


def csv_rows(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    require(
        data.endswith(b"\n") and b"\r" not in data,
        f"CSV line endings differ: {label}",
    )
    try:
        reader = csv.reader(io.StringIO(data.decode(), newline=""), strict=True)
        require(
            tuple(next(reader, ())) == tuple(columns), f"CSV columns differ: {label}"
        )
        rows = [dict(zip(columns, values, strict=True)) for values in reader]
    except (UnicodeDecodeError, csv.Error) as exc:
        raise G0Error(f"invalid CSV: {label}") from exc
    return rows


def csv_bytes(columns: Sequence[str], rows: Sequence[Mapping[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=list(columns), lineterminator="\n", extrasaction="raise"
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def accounting(value: object, label: str) -> dict[str, int]:
    require(
        isinstance(value, Mapping) and set(value) == set(ACCOUNTING_FIELDS),
        f"{label} differs",
    )
    result = dict(cast(Mapping[str, int], value))
    require(
        all(type(item) is int and item >= 0 for item in result.values()),
        f"{label} differs",
    )
    require(
        all(result[name] == 0 for name in ACCOUNTING_FIELDS[8:]),
        f"{label} forbidden operation",
    )
    return result


def validate_parameter_source() -> None:
    require(
        sha(json_bytes(ACCEPTED_PARAMETERS)) == PARAMETER_SHA256,
        "accepted parameter hash differs",
    )
    require(
        sha(json_bytes(ACCEPTED_PARAMETER_RECORD)) == PARAMETER_RECORD_SHA256,
        "accepted parameter record differs",
    )


def runtime() -> dict[str, object]:
    require(
        CONTRACT.is_file()
        and not CONTRACT.is_symlink()
        and sha(CONTRACT.read_bytes()) == CONTRACT_SHA256,
        "oracle contract receipt differs",
    )
    require(LOCK.is_file() and not LOCK.is_symlink(), "research lock differs")
    observed: dict[str, object] = {
        "platform": f"{platform.system()} {platform.machine()} CPU",
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "catboost_version": importlib.metadata.version("catboost"),
        "uv_lock_sha256": sha(LOCK.read_bytes()),
        "cpu_only": True,
        "max_threads": 16,
    }
    expected = {
        "platform": "Linux x86_64 CPU",
        "python_version": "3.10.13",
        "numpy_version": "1.25.2",
        "catboost_version": "1.2.1",
        "uv_lock_sha256": LOCK_SHA256,
        "cpu_only": True,
        "max_threads": 16,
    }
    require(observed == expected, f"locked runtime differs: {observed}")
    return observed


def _safe_ancestry(path: Path, label: str) -> None:
    current = path
    while current != current.parent:
        require(not current.is_symlink(), f"{label} ancestry contains symlink")
        current = current.parent


def _open_root(root: Path, expected: set[str], label: str) -> int:
    _safe_ancestry(root, label)
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(root, flags)
    except OSError as exc:
        raise G0Error(f"cannot open {label} root") from exc
    info = os.fstat(descriptor)
    try:
        require(
            stat.S_ISDIR(info.st_mode) and not info.st_mode & 0o222,
            f"{label} root differs",
        )
        require(set(os.listdir(descriptor)) == expected, f"{label} file set differs")
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


def _read_at(root_fd: int, name: str, label: str, *, readonly: bool = True) -> bytes:
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(name, flags, dir_fd=root_fd)
    except OSError as exc:
        raise G0Error(f"cannot open {label}") from exc
    try:
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode), f"{label} is not regular")
        if readonly:
            require(not info.st_mode & 0o222, f"{label} is writable")
        blocks: list[bytes] = []
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            blocks.append(block)
        data = b"".join(blocks)
        require(len(data) == info.st_size, f"{label} changed during read")
        return data
    finally:
        os.close(descriptor)


def _receipt(manifest: Mapping[str, Any], name: str, data: bytes) -> None:
    receipts = manifest.get("output_receipts")
    require(
        isinstance(receipts, Mapping) and name in receipts,
        f"missing receipt: {name}",
    )
    record = cast(Mapping[str, Any], receipts)[name]
    require(isinstance(record, Mapping), f"receipt differs: {name}")
    fields = {"sha256", "bytes"} | (
        {"rows", "columns"} if name.endswith(".csv") else set()
    )
    require(
        set(record) == fields
        and record["sha256"] == sha(data)
        and record["bytes"] == len(data),
        f"receipt differs: {name}",
    )
    if name.endswith(".csv"):
        require(
            record["rows"] == data.count(b"\n") - 1,
            f"row receipt differs: {name}",
        )


def _digest_map(value: object, label: str) -> dict[str, str]:
    require(isinstance(value, Mapping) and bool(value), f"{label} differs")
    result = dict(cast(Mapping[str, str], value))
    require(
        all(
            isinstance(name, str) and name and is_sha(digest)
            for name, digest in result.items()
        ),
        f"{label} differs",
    )
    return result


def _receipt_map(value: object, label: str) -> dict[str, dict[str, object]]:
    require(isinstance(value, Mapping) and bool(value), f"{label} differs")
    result: dict[str, dict[str, object]] = {}
    for name, value_record in cast(Mapping[str, object], value).items():
        require(
            isinstance(name, str)
            and bool(name)
            and isinstance(value_record, Mapping)
            and set(value_record) == {"sha256", "bytes"}
            and is_sha(value_record["sha256"])
            and type(value_record["bytes"]) is int
            and value_record["bytes"] >= 0,
            f"{label} differs",
        )
        result[name] = dict(cast(Mapping[str, object], value_record))
    return result


def _validate_source_binding(value: object) -> None:
    require(isinstance(value, Mapping), "source bundle binding differs")
    binding = cast(Mapping[str, Any], value)
    require(
        set(binding)
        == {
            "manifest_receipt",
            "schema_version",
            "contract_sha256",
            "parent_receipts",
            "input_receipts",
            "source_receipts",
        },
        "source bundle binding fields differ",
    )
    receipt = binding["manifest_receipt"]
    require(
        isinstance(receipt, Mapping)
        and set(receipt) == {"sha256", "bytes"}
        and is_sha(receipt["sha256"])
        and type(receipt["bytes"]) is int
        and receipt["bytes"] > 0,
        "source manifest receipt differs",
    )
    require(
        binding["schema_version"]
        == "cypshift.openadmet_cyp_2026.oracle_source_bundle.v1"
        and binding["contract_sha256"] == CONTRACT_SHA256,
        "source bundle contract differs",
    )
    parents = _digest_map(binding["parent_receipts"], "source parent receipts")
    inputs = _receipt_map(binding["input_receipts"], "source input receipts")
    sources = _receipt_map(binding["source_receipts"], "source receipts")
    require(inputs == sources, "source input/source receipt binding differs")
    require(
        set(parents) == set(inputs)
        and all(inputs[name]["sha256"] == digest for name, digest in parents.items()),
        "source parent/input receipt binding differs",
    )


def _validate_model_manifest(manifest: Mapping[str, Any]) -> None:
    require(set(manifest) == MODEL_MANIFEST_FIELDS, "model manifest fields differ")
    require(
        manifest.get("schema_version")
        == "cypshift.openadmet_cyp_2026.oracle_projection.v1"
        and manifest.get("status") == "R5_ORACLE_SYNTHETIC_CAPABILITY_PROJECTION",
        "model schema/status differs",
    )
    require(
        manifest.get("contract_sha256") == CONTRACT_SHA256
        and manifest.get("parent_contract_sha256") == PARENT_CONTRACT_SHA256,
        "model contract differs",
    )
    require(
        manifest.get("root") == "model-public"
        and manifest.get("current_cell_scope") == "all"
        and manifest.get("fixed_oof_system_id") == MODEL_ID,
        "model root differs",
    )
    require(
        manifest.get("capability_root_accounting") == ROOT_ACCOUNTING
        and manifest.get("accounting_scope")
        == "values present in this capability root",
        "model accounting scope differs",
    )
    require(
        accounting(manifest.get("operation_accounting"), "model accounting")
        == dict.fromkeys(ACCOUNTING_FIELDS, 0),
        "model target access differs",
    )
    accounting(manifest.get("projector_operation_accounting"), "projector accounting")
    require(manifest.get("authority") == DENIED_AUTHORITY, "model authority differs")
    _validate_source_binding(manifest.get("source_bundle_binding"))
    require(
        manifest.get("forbidden_fields") == FORBIDDEN_PUBLIC_FIELDS,
        "model forbidden fields differ",
    )
    source_receipts = manifest.get("source_receipts")
    require(
        isinstance(source_receipts, Mapping)
        and bool(source_receipts)
        and all(
            isinstance(record, Mapping)
            and set(record) >= {"sha256", "bytes"}
            and is_sha(record["sha256"])
            and type(record["bytes"]) is int
            and record["bytes"] >= 0
            for record in source_receipts.values()
        ),
        "model source receipts differ",
    )
    receipts = manifest.get("output_receipts")
    require(
        isinstance(receipts, Mapping)
        and set(receipts) == set(MODEL_FILES) - {"manifest.json"},
        "model receipt set differs",
    )


def load_model(
    root: Path, expected_manifest_sha: str
) -> tuple[dict[str, bytes], dict[str, Any]]:
    require(is_sha(expected_manifest_sha), "model manifest digest differs")
    root_fd = _open_root(root, set(MODEL_FILES), "model-public")
    try:
        manifest_data = _read_at(root_fd, "manifest.json", "model manifest")
        require(
            sha(manifest_data) == expected_manifest_sha,
            "model manifest receipt differs",
        )
        manifest = json_object(manifest_data, "model manifest")
        _validate_model_manifest(manifest)
        loaded: dict[str, bytes] = {}
        for name in MODEL_FILES[1:]:
            data = _read_at(root_fd, name, f"model {name}")
            _receipt(manifest, name, data)
            loaded[name] = data
    finally:
        os.close(root_fd)
    return loaded, manifest


def _validate_episode_manifest(
    manifest: Mapping[str, Any],
    model_sha: str,
    model: Mapping[str, Any],
    expected_view_builder_sha: str,
    expected_source_cell_sha: str,
) -> None:
    require(
        set(manifest) == EPISODE_MANIFEST_FIELDS,
        "episode manifest fields differ",
    )
    require(
        manifest.get("schema_version")
        == "cypshift.openadmet_cyp_2026.r5c_g0_episode_view.v1"
        and manifest.get("status") == "R5_ORACLE_EPISODE_TARGET_VIEW",
        "episode schema/status differs",
    )
    require(
        manifest.get("contract_sha256") == CONTRACT_SHA256
        and manifest.get("parent_contract_sha256") == PARENT_CONTRACT_SHA256,
        "episode contract differs",
    )
    require(
        manifest.get("root") == "episode-target"
        and manifest.get("view_builder_source_sha256") == expected_view_builder_sha,
        "episode root differs",
    )
    require(
        manifest.get("model_public_manifest_sha256") == model_sha
        and manifest.get("source_cell_target_manifest_sha256")
        == expected_source_cell_sha,
        "episode root pairing differs",
    )
    require(
        manifest.get("source_bundle_binding") == model.get("source_bundle_binding"),
        "source bundle pairing differs",
    )
    require(
        manifest.get("r3c_parameter_source") == R3C_PARAMETER_SOURCE,
        "R3C parameter source differs",
    )
    require(
        manifest.get("authority") == DENIED_AUTHORITY,
        "episode authority differs",
    )
    values = accounting(manifest.get("operation_accounting"), "episode accounting")
    require(
        values["anchor_labels_exposed_to_models"] == 1
        and all(values[name] == 0 for name in ACCOUNTING_FIELDS[2:]),
        "episode pre-fit accounting differs",
    )
    scope = manifest.get("scope")
    require(
        isinstance(scope, Mapping) and set(scope) == SCOPE_FIELDS,
        "episode scope differs",
    )
    episode = manifest.get("episode")
    require(
        isinstance(episode, Mapping)
        and set(episode)
        == {"episode_id", "anchor_molecule_id", "query_rows", "query_rows_sha256"},
        "episode identity differs",
    )
    episode_map = cast(Mapping[str, Any], episode)
    require(
        type(episode_map["query_rows"]) is int
        and episode_map["query_rows"] > 0
        and is_sha(episode_map["query_rows_sha256"]),
        "episode query receipt differs",
    )
    receipts = manifest.get("output_receipts")
    require(
        isinstance(receipts, Mapping)
        and set(receipts) == set(EPISODE_FILES) - {"manifest.json"},
        "episode receipt set differs",
    )


def load_episode(
    root: Path,
    expected_manifest_sha: str,
    model_sha: str,
    model_manifest: Mapping[str, Any],
    expected_view_builder_sha: str,
    expected_source_cell_sha: str,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    require(is_sha(expected_manifest_sha), "episode manifest digest differs")
    require(
        is_sha(expected_view_builder_sha) and is_sha(expected_source_cell_sha),
        "trusted episode parent receipt differs",
    )
    root_fd = _open_root(root, set(EPISODE_FILES), "episode-target")
    try:
        manifest_data = _read_at(root_fd, "manifest.json", "episode manifest")
        require(
            sha(manifest_data) == expected_manifest_sha,
            "episode manifest receipt differs",
        )
        manifest = json_object(manifest_data, "episode manifest")
        _validate_episode_manifest(
            manifest,
            model_sha,
            model_manifest,
            expected_view_builder_sha,
            expected_source_cell_sha,
        )
        loaded: dict[str, bytes] = {}
        for name in EPISODE_FILES[1:]:
            data = _read_at(root_fd, name, f"episode {name}")
            _receipt(manifest, name, data)
            loaded[name] = data
    finally:
        os.close(root_fd)
    return loaded, manifest


def npy(
    data: bytes, rows: int, width: int, dtype: str, label: str
) -> np.ndarray[Any, Any]:
    require(data.startswith(b"\x93NUMPY\x01\x00"), f"NPY version differs: {label}")
    stream = io.BytesIO(data)
    try:
        array = np.load(stream, allow_pickle=False)
    except (ValueError, OSError) as exc:
        raise G0Error(f"invalid NPY: {label}") from exc
    require(stream.tell() == len(data), f"trailing NPY bytes: {label}")
    require(
        array.shape == (rows, width)
        and array.dtype == np.dtype(dtype)
        and array.flags.c_contiguous,
        f"NPY schema differs: {label}",
    )
    canonical = io.BytesIO()
    np.save(canonical, array, allow_pickle=False)
    require(canonical.getvalue() == data, f"noncanonical NPY: {label}")
    array.flags.writeable = False
    return cast(np.ndarray[Any, Any], array)


def publish(output_root: Path, fragment: bytes, manifest: Mapping[str, Any]) -> Path:
    require(not output_root.exists() and not output_root.is_symlink(), "output exists")
    _safe_ancestry(output_root.parent, "output")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    _safe_ancestry(output_root.parent, "output")
    stage = Path(tempfile.mkdtemp(prefix=".r5c-g0-", dir=str(output_root.parent)))
    payloads = {
        "prediction_fragment.csv": fragment,
        "manifest.json": json_bytes(manifest),
    }
    try:
        for name, data in payloads.items():
            with (stage / name).open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        for path in stage.iterdir():
            path.chmod(0o444)
            descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        stage.chmod(0o555)
        directory_fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        _verify_published_tree(stage, payloads, "staged")
        _rename_noreplace(stage, output_root)
        require(
            not stage.exists() and output_root.is_dir(), "promotion did not complete"
        )
        _verify_published_tree(output_root, payloads, "published")
        parent_fd = os.open(
            output_root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except Exception:
        if stage.exists():
            for path in stage.iterdir():
                path.chmod(0o644)
            stage.chmod(0o755)
            shutil.rmtree(stage)
        raise
    return output_root


def _verify_published_tree(
    root: Path, payloads: Mapping[str, bytes], label: str
) -> None:
    root_fd = _open_root(root, set(payloads), label)
    try:
        require(
            stat.S_IMODE(os.fstat(root_fd).st_mode) == 0o555, f"{label} mode differs"
        )
        for name, expected in payloads.items():
            info = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            require(
                stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o444,
                f"{label} file mode differs: {name}",
            )
            require(
                _read_at(root_fd, name, f"{label} {name}") == expected,
                f"{label} reopen differs: {name}",
            )
    finally:
        os.close(root_fd)


def _rename_noreplace(source: Path, destination: Path) -> None:
    require(source.is_dir() and not source.is_symlink(), "staging root differs")
    require(
        not destination.exists() and not destination.is_symlink(),
        "output exists",
    )
    libc = ctypes.CDLL(None, use_errno=True)
    function = getattr(libc, "renameat2", None)
    if function is None:
        raise G0Error("renameat2 unavailable")
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
        raise G0Error("output exists" if error == errno.EEXIST else os.strerror(error))
    require(destination.is_dir() and not source.exists(), "promotion did not complete")

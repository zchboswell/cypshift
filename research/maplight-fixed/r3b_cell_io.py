from __future__ import annotations

import csv
import ctypes
import errno
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import shutil
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn, cast

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
V5 = ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract_v5.json"
V4 = ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract_v4.json"
V3 = ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract.json"
V5_SHA256 = "596d9a246b130c00f07abfcaf73b369038b874ce556be5e6354df10e1d5ad6e2"
V4_SHA256 = "a37a316ceab297deb89d4458169d38d1c73d2edb39ab96ea4c77459a56b01254"
V3_SHA256 = "d728684cc3794bbe01ea44342202944a378968f097cb8f5490852b63721a6285"
GROUP_FOLDS_SHA256 = "91678d68b2f9ac3913f6b679dd284f82ba2a040d803de83655bf89906f31f774"
V5_SCHEMA = "cypshift.openadmet_cyp_2026.global_experiment_contract.v5"
V4_SCHEMA = "cypshift.openadmet_cyp_2026.global_experiment_contract.v4"
ENDPOINTS = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
OUTER_SYSTEMS = (
    "TRACE-C0-ENDPOINT-MEDIAN",
    "TRACE-C1-MORGAN-CATBOOST",
    "TRACE-G0-MAPL-FIXED",
    "TRACE-C2-MORGAN-1NN",
)
MAPLIGHT = "TRACE-G0-MAPL-FIXED"
OUTER_SCOPE = "openadmet-direct-outer-v1"
FRAGMENT_COLUMNS = (
    "molecule_id",
    "endpoint",
    "component_id",
    "repeat",
    "outer_fold",
    "inner_fold",
    "scope",
    "system_id",
    "prediction",
    "applicability_score",
    "model_id",
    "feature_spec_id",
    "split_id",
)
MODEL_ROWS_COLUMNS = (
    "molecule_id",
    "similarity_component_hash",
    "repeat",
    "seed",
    "outer_fold",
    "outer_validation_fold",
    "inner_fold",
)
CATBOOST_ARGS = {
    "loss_function": "MAE",
    "random_strength": 2,
    "random_seed": 1,
    "task_type": "CPU",
    "thread_count": 16,
    "verbose": 0,
    "allow_writing_files": False,
}
FEATURE_SPECS = {
    OUTER_SYSTEMS[0]: "no-molecular-features-v1",
    OUTER_SYSTEMS[1]: "d032-morgan-ecfp4-chiral-binary-4096-v1",
    MAPLIGHT: "maplight-fixed-stage-a-v1",
    OUTER_SYSTEMS[3]: "d032-morgan-ecfp4-chiral-binary-4096-v1",
}
ARRAYS = (
    "morgan_binary",
    "maplight_morgan_count",
    "maplight_avalon_count",
    "maplight_erg",
    "maplight_rdkit_descriptors",
)
MAP_ARRAYS = ARRAYS[1:]
PUBLIC_FIELDS = frozenset(
    "schema_version contract_sha256 parent_contract_sha256 "
    "projector_source_sha256 model_rows outer_target_receipts "
    "inner_target_receipts accounting authority".split()
)
MODEL_RECORD_FIELDS = frozenset("path sha256 bytes rows columns schema_version".split())
TARGET_RECEIPT_FIELDS = frozenset(
    "stage cell_id endpoint repeat outer_fold inner_fold relative_path sha256 "
    "rows identity_sha256".split()
)
TARGET_CONTEXTS = {
    ("outer", endpoint, repeat, outer, None)
    for endpoint in ENDPOINTS
    for repeat in range(3)
    for outer in range(5)
} | {
    ("inner", endpoint, repeat, outer, inner)
    for endpoint in ENDPOINTS
    for repeat in range(3)
    for outer in range(5)
    for inner in range(4)
}
PUBLIC_ACCOUNTING = frozenset("truth_paths truth_hashes scores metrics".split())
PUBLIC_ACCOUNTING_VALUES = dict.fromkeys(PUBLIC_ACCOUNTING, 0)
FORBIDDEN_PUBLIC = ("truth", "sealed", "private_audit", "score", "metric")
PUBLIC_SCHEMAS = frozenset(
    "cypshift.openadmet_cyp_2026.r3b_model_public.v1 "
    "cypshift.openadmet_cyp_2026.r3b_model_public.v5".split()
)
FEATURE_DTYPES = {
    "morgan_binary": np.dtype("uint8"),
    "maplight_morgan_count": np.dtype("int8"),
    "maplight_avalon_count": np.dtype("int8"),
    "maplight_erg": np.dtype("<f8"),
    "maplight_rdkit_descriptors": np.dtype("<f8"),
}
FEATURE_WIDTHS = {
    "morgan_binary": 4096,
    "maplight_morgan_count": 1024,
    "maplight_avalon_count": 1024,
    "maplight_erg": 315,
    "maplight_rdkit_descriptors": 200,
}
FEATURE_DTYPE_STR = {
    "morgan_binary": "uint8",
    "maplight_morgan_count": "int8",
    "maplight_avalon_count": "int8",
    "maplight_erg": "<f8",
    "maplight_rdkit_descriptors": "<f8",
}
FEATURE_COLUMNS = (
    "molecule_id",
    "raw_structure_sha256",
    "standardized_structure_hash",
    "similarity_component_hash",
)
INHERITED_AUTHORITY = {
    "global_surrogate_validation": False,
    "global_model": False,
    "internal_surrogate_metrics": False,
    "global_oof_predictions": False,
    "inner_oof_predictions": False,
    "parent_state_completion": False,
    "official_st_rae": False,
    "validation_frozen": False,
    "fold_assignments": True,
    "episodes": True,
    "episode_labels": True,
    "topology_viability": True,
    "submissions": False,
    "tdi": False,
    "transduction": False,
    "anchor_expansion": False,
    "transformations": False,
}


class R3BError(RuntimeError):
    pass


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise R3BError(message)


def _require_exact_mapping(
    value: object, expected: Mapping[str, Any], message: str
) -> None:
    _require(isinstance(value, Mapping), message)
    observed_map = cast(Mapping[str, Any], value)
    _require(set(observed_map) == set(expected), message)
    for key, expected_value in expected.items():
        observed = observed_map[key]
        if isinstance(expected_value, Mapping):
            _require_exact_mapping(observed, expected_value, message)
        elif isinstance(expected_value, list):
            _require(type(observed) is list, message)
            _require(len(observed) == len(expected_value), message)
            for actual_item, expected_item in zip(
                observed, expected_value, strict=True
            ):
                _require(
                    type(actual_item) is type(expected_item)
                    and actual_item == expected_item,
                    message,
                )
        else:
            _require(
                type(observed) is type(expected_value) and observed == expected_value,
                message,
            )


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value == value.lower()
        and all(char in "0123456789abcdef" for char in value)
    )


def _canonical_float(
    value: str, name: str, lo: float | None = None, hi: float | None = None
) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise R3BError(f"{name} is not numeric") from exc
    _require(
        math.isfinite(result)
        and (lo is None or result >= lo)
        and (hi is None or result <= hi)
        and value == format(result, ".17g"),
        f"{name} is nonfinite or noncanonical",
    )
    return result


def _require_readonly_root(root: Path, message: str) -> None:
    _require(
        root.is_dir()
        and not root.is_symlink()
        and not bool(root.stat().st_mode & 0o222)
        and not any(
            path.is_symlink() or bool(path.stat().st_mode & 0o222)
            for path in root.rglob("*")
        ),
        message,
    )


def _json_bytes(value: object) -> bytes:
    try:
        text = json.dumps(
            value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise R3BError("nonstandard JSON value") from exc
    return (text + "\n").encode("utf-8")


def _read_json(
    path: Path, expected_sha256: str | None = None
) -> tuple[dict[str, Any], bytes]:
    ancestor = path
    while ancestor != ancestor.parent:
        _require(not ancestor.is_symlink(), "ancestor symlink is forbidden")
        ancestor = ancestor.parent
    _require(path.is_file() and not path.is_symlink(), f"missing regular JSON: {path}")
    raw = path.read_bytes()
    if expected_sha256 is not None:
        _require(
            _sha256_bytes(raw) == expected_sha256, f"JSON receipt differs: {path.name}"
        )

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            _require(key not in value, f"duplicate JSON key: {key}")
            value[key] = item
        return value

    def reject_constant(value: str) -> NoReturn:
        raise R3BError(f"nonstandard JSON constant: {value}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise R3BError(f"invalid JSON: {path.name}") from exc
    _require(isinstance(value, dict), f"JSON root differs: {path.name}")
    return cast(dict[str, Any], value), raw


def _csv_bytes(columns: Sequence[str], rows: Iterable[Mapping[str, object]]) -> bytes:
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row[key] for key in columns})
    return stream.getvalue().encode("utf-8")


def _read_csv_bytes(
    raw: bytes, columns: Sequence[str], label: str
) -> list[dict[str, str]]:
    _require(raw.endswith(b"\n") and b"\r" not in raw, f"{label} line endings differ")
    import io

    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""))
        _require(
            tuple(reader.fieldnames or ()) == tuple(columns), f"{label} columns differ"
        )
        raw_rows = list(reader)
        _require(
            all(None not in row and None not in row.values() for row in raw_rows),
            f"{label} malformed row",
        )
        rows = [{str(k): str(v) for k, v in row.items()} for row in raw_rows]
    except (UnicodeDecodeError, csv.Error) as exc:
        raise R3BError(f"invalid CSV: {label}") from exc
    return rows


def _safe_rel(path: str) -> Path:
    rel = Path(path)
    _require(
        not rel.is_absolute() and ".." not in rel.parts and str(rel) != ".",
        "unsafe relative path",
    )
    return rel


def _rooted_path(root: Path, relative: str, *, regular: bool = True) -> Path:
    _require(root.is_dir() and not root.is_symlink(), "root is invalid")
    ancestor = root
    while ancestor != ancestor.parent:
        _require(not ancestor.is_symlink(), "ancestor symlink is forbidden")
        ancestor = ancestor.parent
    rel = _safe_rel(relative)
    current = root
    for part in rel.parts:
        current /= part
        _require(not current.is_symlink(), "ancestor symlink is forbidden")
    resolved_root = root.resolve()
    resolved = current.resolve(strict=False)
    _require(
        os.path.commonpath((str(resolved_root), str(resolved))) == str(resolved_root),
        "path escapes root",
    )
    if regular:
        _require(current.is_file(), "path is not a regular file")
    return current


def _readonly_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)


def _fsync_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts)):
        if path.is_file():
            fd = os.open(path, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
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


def _fsync_parent(path: Path) -> None:
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _cleanup_tree(root: Path) -> None:
    if not root.exists() or root.is_symlink():
        return
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts)):
        path.chmod(0o755 if path.is_dir() else 0o644)
    root.chmod(0o755)
    shutil.rmtree(root)


def _promote_noreplace(source: Path, destination: Path) -> None:
    _require(source.is_dir() and not source.is_symlink(), "staging root is invalid")
    _require(
        not destination.exists() and not destination.is_symlink(),
        "output root appeared",
    )
    if sys.platform != "linux":
        raise R3BError("renameat2 unavailable")
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise R3BError("renameat2 unavailable")
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    rc = renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    if rc != 0:
        err = ctypes.get_errno()
        raise R3BError(
            "output root appeared"
            if err == errno.EEXIST
            else f"renameat2 failed: {os.strerror(err)}"
        )
    _require(destination.is_dir() and not source.exists(), "promotion did not complete")


def _contract_receipts(
    *,
    synthetic: bool = False,
    v5_path: Path = V5,
    v4_path: Path = V4,
    v3_path: Path = V3,
) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    if v5_path.resolve() == V5.resolve():
        active, active_bytes = _read_json(v5_path, V5_SHA256)
        _require(active.get("schema_version") == V5_SCHEMA, "v5 schema differs")
        _require(
            active.get("parent", {}).get("sha256") == V4_SHA256,
            "v5 parent receipt differs",
        )
        parent, parent_bytes = _read_json(v4_path, V4_SHA256)
        _require(parent.get("schema_version") == V4_SCHEMA, "v4 schema differs")
        v3, v3_bytes = _read_json(v3_path, V3_SHA256)
        _require(v3.get("schema_version", "").endswith(".v3"), "v3 schema differs")
        _require(
            parent.get("parent", {}).get("sha256") == _sha256_bytes(v3_bytes),
            "v4 parent receipt differs",
        )
        return active, parent, _sha256_bytes(active_bytes), _sha256_bytes(parent_bytes)
    active, active_bytes = _read_json(v5_path, V4_SHA256)
    v3, v3_bytes = _read_json(v3_path, V3_SHA256)
    _require(active.get("schema_version") == V4_SCHEMA, "v4 schema differs")
    _require(v3.get("schema_version", "").endswith(".v3"), "v3 schema differs")
    _require(
        active.get("parent", {}).get("sha256") == _sha256_bytes(v3_bytes),
        "parent contract receipt differs",
    )
    return active, v3, _sha256_bytes(active_bytes), _sha256_bytes(v3_bytes)


def _cell_material(
    contract_sha: str,
    stage: str,
    endpoint: str,
    repeat: int,
    outer: int,
    inner: int | None,
    scope: str,
) -> str:
    return "|".join(
        (
            contract_sha,
            stage,
            endpoint,
            str(repeat),
            str(outer),
            "none" if inner is None else str(inner),
            scope,
        )
    )


def _cell_id(
    contract_sha: str,
    stage: str,
    endpoint: str,
    repeat: int,
    outer: int,
    inner: int | None,
    scope: str,
) -> str:
    return _sha256_bytes(
        _cell_material(
            contract_sha, stage, endpoint, repeat, outer, inner, scope
        ).encode()
    )


def _model_id(
    contract_sha: str,
    system: str,
    endpoint: str,
    repeat: int,
    outer: int,
    inner: int | None,
    scope: str,
) -> str:
    return _sha256_bytes(
        "|".join(
            (
                contract_sha,
                system,
                endpoint,
                str(repeat),
                str(outer),
                "none" if inner is None else str(inner),
                scope,
            )
        ).encode()
    )


def _split_id(
    group_sha: str, repeat: int, outer: int, inner: int | None, scope: str
) -> str:
    return _sha256_bytes(
        "|".join(
            (
                group_sha,
                str(repeat),
                str(outer),
                "none" if inner is None else str(inner),
                scope,
            )
        ).encode()
    )


def _parse_int(
    value: str, name: str, lo: int | None = None, hi: int | None = None
) -> int:
    _require(type(value) is str, f"{name} is not an unsigned integer")
    _require(
        value == "0"
        or value != ""
        and value[0] != "0"
        and all("0" <= char <= "9" for char in value),
        f"{name} is not an unsigned integer",
    )
    result = int(value)
    _require(lo is None or result >= lo, f"{name} is out of range")
    _require(hi is None or result <= hi, f"{name} is out of range")
    return result


def _load_feature_root(
    root: Path, expected_manifest_sha: str, *, synthetic: bool = False
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, np.ndarray[Any, Any]], str]:
    _require(_is_sha(expected_manifest_sha), "feature manifest SHA differs")
    _require_readonly_root(root, "feature root is writable or contains a symlink")
    manifest, _ = _read_json(
        _rooted_path(root, "feature_manifest.json"), expected_manifest_sha
    )
    _require(
        manifest.get("schema_version")
        == "cypshift.openadmet_cyp_2026.r3a_feature_manifest.v1",
        "feature manifest schema differs",
    )
    rows_path = _rooted_path(root, "feature_rows.csv")
    rows_raw = rows_path.read_bytes()
    declared = manifest.get("rows", {})
    _require(
        isinstance(declared, dict)
        and set(declared) == {"path", "columns", "rows", "sha256"}
        and declared["path"] == "feature_rows.csv"
        and declared["columns"] == list(FEATURE_COLUMNS),
        "feature row receipt schema differs",
    )
    _require(
        _sha256_bytes(rows_raw) == declared.get("sha256"),
        "feature rows receipt differs",
    )
    rows = _read_csv_bytes(rows_raw, FEATURE_COLUMNS, "feature rows")
    _require(
        type(declared["rows"]) is int and len(rows) == declared["rows"],
        "feature row count differs",
    )
    ids = [row["molecule_id"] for row in rows]
    _require(len(ids) == len(set(ids)), "feature molecule IDs differ")
    arrays: dict[str, np.ndarray[Any, Any]] = {}
    records = cast(Mapping[str, Any], manifest.get("arrays", {}))
    _require(
        isinstance(records, Mapping) and set(records) == set(ARRAYS),
        "feature array set differs",
    )
    for name in ARRAYS:
        path = _rooted_path(root, f"{name}.npy")
        record = records.get(name)
        _require(
            isinstance(record, Mapping),
            f"feature receipt schema differs: {name}",
        )
        payload = path.read_bytes()
        record_map = cast(Mapping[str, Any], record)
        _require(
            {
                "path",
                "shape",
                "dtype",
                "npy_version",
                "c_contiguous",
                "npy_sha256",
            }
            <= set(record_map),
            f"feature receipt schema differs: {name}",
        )
        _require(
            record_map["path"] == f"{name}.npy"
            and isinstance(record_map["shape"], list)
            and len(record_map["shape"]) == 2
            and all(type(value) is int and value >= 0 for value in record_map["shape"])
            and record_map["shape"] == [len(rows), FEATURE_WIDTHS[name]]
            and record_map["dtype"] == FEATURE_DTYPE_STR[name]
            and record_map["npy_version"] == "1.0"
            and record_map["c_contiguous"] is True
            and payload.startswith(b"\x93NUMPY\x01\x00")
            and _sha256_bytes(payload) == record_map["npy_sha256"],
            f"feature payload receipt differs: {name}",
        )
        arr = np.load(__import__("io").BytesIO(payload), allow_pickle=False)
        _require(
            arr.shape == (len(rows), FEATURE_WIDTHS[name]) and arr.flags.c_contiguous,
            f"feature shape differs: {name}",
        )
        expected_dtype = FEATURE_DTYPES[name]
        _require(arr.dtype == expected_dtype, f"feature dtype differs: {name}")
        _require(np.isfinite(arr).all(), f"feature nonfinite values: {name}")
        arrays[name] = arr
    return manifest, rows, arrays, expected_manifest_sha


def _load_public(
    root: Path,
    expected_manifest_sha: str,
    *,
    synthetic: bool = False,
    verify_target_payloads: bool = True,
    require_readonly: bool = False,
) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, Any]], str]:
    _require(_is_sha(expected_manifest_sha), "model-public manifest SHA differs")
    _require_readonly_root(root, "model-public root is writable or contains a symlink")
    manifest, raw = _read_json(
        _rooted_path(root, "model_public_manifest.json"), expected_manifest_sha
    )
    _require(
        manifest.get("schema_version") in PUBLIC_SCHEMAS, "model-public schema differs"
    )
    if manifest.get("contract_sha256") == V5_SHA256:
        _require(
            manifest["schema_version"]
            == "cypshift.openadmet_cyp_2026.r3b_model_public.v5",
            "model-public v5 schema differs",
        )

    def forbidden(value: object) -> bool:
        if isinstance(value, Mapping):
            return any(
                any(bad in token for bad in FORBIDDEN_PUBLIC)
                or isinstance(child, str)
                and any(bad in child.lower() for bad in FORBIDDEN_PUBLIC)
                or forbidden(child)
                for key, child in value.items()
                for token in (str(key).lower().replace("-", "_"),)
            )
        elif isinstance(value, list):
            return any(forbidden(item) for item in value)
        return False

    public_data = {
        key: value
        for key, value in manifest.items()
        if key not in ("accounting", "authority")
    }
    _require(not forbidden(public_data), "forbidden model-public metadata")
    _require(
        set(manifest) == PUBLIC_FIELDS,
        "model-public fields differ",
    )
    _require_exact_mapping(
        manifest.get("authority"), INHERITED_AUTHORITY, "model-public authority differs"
    )
    _require(
        _is_sha(manifest["projector_source_sha256"]), "projector source receipt differs"
    )
    _require_exact_mapping(
        manifest.get("accounting"),
        PUBLIC_ACCOUNTING_VALUES,
        "model-public accounting differs",
    )
    model_record = cast(dict[str, Any], manifest.get("model_rows", {}))
    _require(
        set(model_record) == MODEL_RECORD_FIELDS,
        "model rows receipt schema differs",
    )
    model_path = _rooted_path(root, str(model_record.get("path", "model_rows.csv")))
    model_raw = model_path.read_bytes()
    _require(
        _sha256_bytes(model_raw) == model_record.get("sha256")
        and type(model_record.get("bytes")) is int
        and model_record["bytes"] >= 0
        and len(model_raw) == model_record.get("bytes")
        and model_record.get("columns") == list(MODEL_ROWS_COLUMNS)
        and model_record.get("schema_version") == ""
        and (
            synthetic
            or manifest.get("contract_sha256") not in (V4_SHA256, V5_SHA256)
            or model_record["sha256"] == GROUP_FOLDS_SHA256
        ),
        "model rows receipt differs",
    )
    model_rows = _read_csv_bytes(model_raw, MODEL_ROWS_COLUMNS, "model rows")
    _require(
        type(model_record.get("rows")) is int
        and model_record["rows"] >= 0
        and len(model_rows) == model_record["rows"],
        "model row count differs",
    )
    if not synthetic:
        _require(len(model_rows) == 73575, "production model row count differs")
    fold_index = _build_fold_index(model_rows)
    target_receipts: list[dict[str, Any]] = []
    for key in ("outer_target_receipts", "inner_target_receipts"):
        value = manifest.get(key, [])
        _require(isinstance(value, list), f"{key} schema differs")
        target_receipts += cast(list[dict[str, Any]], value)
    _require(len(target_receipts) == 300, "target receipt cardinality differs")
    public_sha = _sha256_bytes(raw)
    _validate_target_receipts(
        root,
        target_receipts,
        manifest.get("contract_sha256"),
        open_payload=verify_target_payloads,
    )
    _FOLD_INDEX_CACHE[public_sha] = fold_index
    return manifest, model_rows, target_receipts, public_sha


_FOLD_INDEX_CACHE: dict[str, dict[str, Any]] = {}


def _validate_target_receipts(
    root: Path,
    receipts: Sequence[Mapping[str, Any]],
    contract_sha: object,
    *,
    open_payload: bool = True,
) -> None:
    seen: set[tuple[str, str, int, int, int | None]] = set()
    paths: list[tuple[Path, str]] = []
    for receipt in receipts:
        _require(set(receipt) == TARGET_RECEIPT_FIELDS, "target receipt schema differs")
        stage = str(receipt["stage"])
        endpoint = str(receipt["endpoint"])
        repeat = _parse_int(str(receipt["repeat"]), "target repeat", 0, 2)
        outer = _parse_int(str(receipt["outer_fold"]), "target outer fold", 0, 4)
        value = receipt["inner_fold"]
        inner = (
            None
            if stage == "outer"
            else _parse_int(str(value), "target inner fold", 0, 3)
        )
        _require(
            stage in ("outer", "inner") and endpoint in ENDPOINTS,
            "target context differs",
        )
        if stage == "outer":
            _require(value in (None, "", "none"), "outer target inner fold differs")
        scope = (
            OUTER_SCOPE
            if stage == "outer"
            else f"openadmet-direct-inner-v1|outer={outer}"
        )
        expected_path = (
            f"outer_targets/{endpoint}/repeat-{repeat}/outer-{outer}.csv"
            if stage == "outer"
            else (
                f"inner_targets/{endpoint}/repeat-{repeat}/outer-{outer}/"
                f"inner-{inner}.csv"
            )
        )
        _require(
            receipt["relative_path"] == expected_path,
            "target path schema differs",
        )
        expected = _cell_id(
            str(contract_sha), stage, endpoint, repeat, outer, inner, scope
        )
        _require(receipt["cell_id"] == expected, "target cell identity differs")
        key = (stage, endpoint, repeat, outer, inner)
        _require(key not in seen, "duplicate target receipt context")
        seen.add(key)
        path = _rooted_path(root, str(receipt["relative_path"]))
        _require(
            all(_is_sha(receipt[name]) for name in ("sha256", "identity_sha256")),
            "target receipt hash differs",
        )
        _require(
            type(receipt["rows"]) is int and receipt["rows"] >= 0,
            "target row count differs",
        )
        paths.append((path, str(receipt["sha256"])))
    _require(seen == TARGET_CONTEXTS, "target receipt contexts differ")
    if open_payload:
        for path, expected in paths:
            _require(_sha256(path) == expected, "target payload receipt differs")


def _build_fold_index(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    by_key: dict[tuple[str, int, int], dict[str, str]] = {}
    by_context: dict[tuple[int, int], list[dict[str, str]]] = {}
    components: dict[str, str] = {}
    assignments: dict[tuple[str, int], str] = {}
    inner_assignments: dict[tuple[str, int, int], str] = {}
    contexts: dict[tuple[str, int], set[int]] = {}
    for source in rows:
        row = dict(source)
        molecule = row["molecule_id"]
        repeat = _parse_int(row["repeat"], "repeat", 0, 2)
        outer = _parse_int(row["outer_fold"], "outer_fold", 0, 4)
        validation = _parse_int(
            row["outer_validation_fold"], "outer_validation_fold", 0, 4
        )
        _require(row["seed"] == str(20260810 + repeat), "fold seed differs")
        component = row["similarity_component_hash"]
        _require(
            molecule != ""
            and _is_sha(component)
            and components.setdefault(molecule, component) == component,
            "component drift",
        )
        assignment_key = (component, repeat)
        _require(
            assignments.setdefault(assignment_key, row["outer_fold"])
            == row["outer_fold"],
            "component outer assignment differs",
        )
        blank = row["inner_fold"] == ""
        _require(blank == (outer == validation), "inner blank semantics differ")
        if not blank:
            _parse_int(row["inner_fold"], "inner_fold", 0, 3)
            inner_key = (component, repeat, validation)
            _require(
                inner_assignments.setdefault(inner_key, row["inner_fold"])
                == row["inner_fold"],
                "component inner assignment differs",
            )
        lookup_key = (molecule, repeat, validation)
        _require(lookup_key not in by_key, "duplicate fold lookup key")
        by_key[lookup_key] = row
        contexts.setdefault((molecule, repeat), set()).add(validation)
        by_context.setdefault((repeat, validation), []).append(row)
    _require(
        all(len(value) == 5 for value in contexts.values()),
        "fold context completeness differs",
    )
    _require(
        all(
            {repeat for mol, repeat in contexts if mol == molecule} == {0, 1, 2}
            for molecule, _ in contexts
        ),
        "fold repeat contexts differ",
    )
    _require(
        len(by_key) == len({key[0] for key in contexts}) * 15,
        "fold repeat population differs",
    )
    return {"by_key": by_key, "by_context": by_context}


def _fold_index(public_sha: str) -> dict[str, Any]:
    _require(public_sha in _FOLD_INDEX_CACHE, "fold lookup index missing")
    return _FOLD_INDEX_CACHE[public_sha]


def _context_rows(
    index: Mapping[str, Any], repeat: int, outer: int
) -> list[dict[str, str]]:
    rows = index["by_context"].get((repeat, outer), [])
    _require(rows, "fold context missing")
    return list(rows)


def _verify_runtime(contract: Mapping[str, Any], *, synthetic: bool) -> None:
    if synthetic:
        return
    _require(
        platform.system() == "Linux"
        and platform.machine().lower() in ("x86_64", "amd64"),
        "model runtime platform differs",
    )
    _require(sys.version_info[:3] == (3, 10, 13), "model runtime Python differs")
    expected = cast(
        Mapping[str, Any], contract["runtime_and_models"]["model_and_scorer"]
    )
    _require(np.__version__ == expected["numpy_version"], "model runtime NumPy differs")
    try:
        observed_catboost = importlib.metadata.version("catboost")
    except importlib.metadata.PackageNotFoundError as exc:
        raise R3BError("model runtime CatBoost is unavailable") from exc
    _require(
        observed_catboost == expected["catboost_version"],
        "model runtime CatBoost differs",
    )
    lock = Path(__file__).with_name("uv.lock")
    _require(
        _sha256(lock) == expected["uv_lock_sha256"],
        "model runtime lock receipt differs",
    )

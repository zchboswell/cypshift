"""Authenticated G0 transport and atomic publication for R5C pair cells."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import stat
import tempfile
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, Literal

from cypshift.openadmet_oracle_pair_cell import (
    FRAGMENT_COLUMNS,
    PairCellResult,
)

CONTRACT_SHA256: Final = (
    "9143ecd1b24d1d9a97b1e5821e2b953f4cfffcec1cc39de3a8c49b81a4f58a50"
)
G0_COLUMNS: Final = FRAGMENT_COLUMNS
LEGACY_G0_COLUMNS: Final = (
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
OUTPUT_FILES: Final = ("manifest.json", "prediction_fragment.csv")
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


class OraclePairCellIOError(ValueError):
    """An input fragment, receipt, or publication invariant failed."""


def load_g0_predictions(
    root: Path | Sequence[Path],
    *,
    expected_manifest_sha256: str | Sequence[str],
    scope: tuple[Literal["inner", "outer"], int, int, int | None],
    public_queries: Sequence[Mapping[str, str]],
) -> dict[tuple[str, str, int], float]:
    """Load exactly one authenticated G0 fragment and return query-keyed values."""

    _validate_scope(scope)
    roots = (root,) if isinstance(root, Path) else tuple(root)
    receipts = (
        (expected_manifest_sha256,)
        if isinstance(expected_manifest_sha256, str)
        else tuple(expected_manifest_sha256)
    )
    if len(roots) != len(receipts) or not roots:
        raise OraclePairCellIOError("G0 root/receipt cardinality differs")
    loaded = [
        _load_g0_root(path, digest, scope)
        for path, digest in zip(roots, receipts, strict=True)
    ]
    expected = {
        (row["episode_id"], row["query_molecule_id"], int(row["query_rank"])): row
        for row in public_queries
    }
    if len(expected) != len(public_queries):
        raise OraclePairCellIOError("public query keys are duplicated")
    values: dict[tuple[str, str, int], float] = {}
    for manifest, rows, legacy in loaded:
        if legacy:
            for row in rows:
                episode_id = str(manifest["episode"]["episode_id"])
                candidates = [
                    key
                    for key in expected
                    if key[0] == episode_id and key[1] == row["molecule_id"]
                ]
                if len(candidates) != 1:
                    raise OraclePairCellIOError(
                        "legacy G0 episode/query identity differs"
                    )
                key = candidates[0]
                value_text = row["prediction"]
                system = row["system_id"]

                if system != "TRACE-G0-MAPL-FIXED":
                    raise OraclePairCellIOError("legacy G0 source metadata differs")
                value = _finite(value_text, "legacy G0 prediction")
                if format(value, ".17g") != value_text:
                    raise OraclePairCellIOError(
                        "legacy G0 prediction serialization differs"
                    )
                if key in values:
                    raise OraclePairCellIOError("legacy G0 query is duplicated")
                values[key] = value
        else:
            for row in rows:
                key = (
                    row["episode_id"],
                    row["query_molecule_id"],
                    int(row["query_rank"]),
                )
                public = expected.get(key)
                if public is None:
                    raise OraclePairCellIOError("G0 query population differs")
                if row["episode_policy_id"] != public["episode_policy_id"]:
                    raise OraclePairCellIOError("G0 public query identity differs")
                if (
                    row["repeat"] != public["repeat"]
                    or row["outer_fold"] != public["outer_fold"]
                ):
                    raise OraclePairCellIOError("G0 public scope differs")
                if row["component_id"] != public["outer_group_id"]:
                    raise OraclePairCellIOError("G0 component identity differs")
                expected_inner = "" if scope[3] is None else str(scope[3])
                if row["inner_fold"] != expected_inner or row["system_id"] != "G0":
                    raise OraclePairCellIOError("G0 scope/source metadata differs")
                if (
                    row["prediction_source"] != "G0"
                    or row["local_available"] != "false"
                ):
                    raise OraclePairCellIOError("G0 source metadata differs")
                value = _finite(row["prediction"], "G0 prediction")
                if format(value, ".17g") != row["prediction"]:
                    raise OraclePairCellIOError("G0 prediction serialization differs")
                if key in values:
                    raise OraclePairCellIOError("G0 query is duplicated")
                values[key] = value
    if set(values) != set(expected):
        raise OraclePairCellIOError("G0 query population differs")
    return values


def _load_g0_root(
    root: Path,
    expected_manifest_sha256: str,
    scope: tuple[Literal["inner", "outer"], int, int, int | None],
) -> tuple[dict[str, Any], list[dict[str, str]], bool]:
    _digest(expected_manifest_sha256, "expected G0 manifest")
    _validate_scope(scope)
    fd = _open_root(root)
    try:
        if set(os.listdir(fd)) != set(OUTPUT_FILES):
            raise OraclePairCellIOError("G0 output file set differs")
        manifest_data = _read_at(fd, "manifest.json")
        if sha256(manifest_data).hexdigest() != expected_manifest_sha256:
            raise OraclePairCellIOError("G0 manifest receipt differs")
        try:
            manifest = json.loads(manifest_data.decode())
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OraclePairCellIOError("G0 manifest is invalid") from exc
        if not isinstance(manifest, dict):
            raise OraclePairCellIOError("G0 manifest is not an object")
        schema = manifest.get("schema_version")
        receipt_hint = manifest.get("prediction_fragment")
        legacy = (
            schema == "cypshift.openadmet_cyp_2026.r5c_g0_prediction_fragment.v1"
            and isinstance(receipt_hint, Mapping)
            and receipt_hint.get("columns") == list(LEGACY_G0_COLUMNS)
        )
        if not legacy:
            _validate_manifest(manifest, scope)
        else:
            _validate_legacy_manifest(manifest, scope)
        fragment = _read_at(fd, "prediction_fragment.csv")
        receipt = manifest.get("prediction_fragment")
        columns = LEGACY_G0_COLUMNS if legacy else G0_COLUMNS
        if (
            not isinstance(receipt, Mapping)
            or receipt.get("sha256") != sha256(fragment).hexdigest()
            or receipt.get("bytes") != len(fragment)
            or receipt.get("rows") != fragment.count(b"\n") - 1
            or receipt.get("columns") != list(columns)
        ):
            raise OraclePairCellIOError("G0 fragment receipt differs")
    finally:
        os.close(fd)
    return manifest, _rows(fragment, columns), legacy


def publish_pair_cell(
    output_root: Path,
    result: PairCellResult,
    *,
    scope: Mapping[str, Any],
    capability_binding: Mapping[str, Any],
    runtime: Mapping[str, Any] | None = None,
) -> Path:
    """Publish exactly two read-only files using no-replace atomic promotion."""

    normalized_scope = _validate_scope_mapping(scope)
    observed_rows = _rows(result.fragment)
    if tuple(observed_rows) != result.rows:
        raise OraclePairCellIOError("pair result bytes and rows differ")
    if not observed_rows:
        raise OraclePairCellIOError("pair fragment is empty")
    _validate_pair_rows(observed_rows)
    system_id = observed_rows[0]["system_id"]
    if any(row["system_id"] != system_id for row in observed_rows):
        raise OraclePairCellIOError("pair system identity differs")
    _digest(result.candidate_id, "pair candidate")
    _digest(result.fragment_id, "pair fragment")
    bound_system = capability_binding.get("system_id")
    if bound_system is not None and bound_system != system_id:
        raise OraclePairCellIOError("pair capability system differs")
    if any(row["candidate_id"] != result.candidate_id for row in observed_rows):
        raise OraclePairCellIOError("pair candidate identity differs")
    expected_inner = normalized_scope["inner_fold"]
    if any(
        row["repeat"] != str(normalized_scope["repeat"])
        or row["outer_fold"] != str(normalized_scope["outer_fold"])
        or row["inner_fold"] != ("" if expected_inner is None else str(expected_inner))
        for row in observed_rows
    ):
        raise OraclePairCellIOError("pair scope differs")
    keys = [
        (row["episode_id"], row["query_molecule_id"], row["query_rank"])
        for row in observed_rows
    ]
    if len(keys) != len(set(keys)):
        raise OraclePairCellIOError("pair prediction keys are duplicated")
    if output_root.exists() or output_root.is_symlink():
        raise OraclePairCellIOError("pair output already exists")
    parent = output_root.parent
    if ".." in parent.parts or any(
        path.is_symlink() for path in (parent, *parent.parents)
    ):
        raise OraclePairCellIOError("pair output ancestry differs")
    parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".r5c-pair-", dir=parent))
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.r5c_private_prediction_fragment.v1",
        "status": "R5_ORACLE_PAIR_CELL_COMPLETE",
        "contract_sha256": CONTRACT_SHA256,
        "scope": {
            "stage": normalized_scope["stage"],
            "repeat": normalized_scope["repeat"],
            "outer_fold": normalized_scope["outer_fold"],
            "inner_fold": "" if expected_inner is None else expected_inner,
        },
        "system_id": result.rows[0]["system_id"] if result.rows else "",
        "candidate_id": result.candidate_id,
        "fragment_id": result.fragment_id,
        "capability_binding": dict(capability_binding),
        "runtime": dict(runtime or {}),
        "operation_accounting": dict(result.accounting),
        "prediction_fragment": {
            "path": "prediction_fragment.csv",
            "sha256": sha256(result.fragment).hexdigest(),
            "bytes": len(result.fragment),
            "rows": len(result.rows),
            "columns": list(FRAGMENT_COLUMNS),
        },
        "authority": {
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
        },
    }
    payloads = {
        "prediction_fragment.csv": result.fragment,
        "manifest.json": _json_bytes(manifest),
    }
    try:
        for name, data in payloads.items():
            with (stage / name).open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            (stage / name).chmod(0o444)
        stage.chmod(0o555)
        directory_fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        _rename_noreplace(stage, output_root)
        _reopen_output(output_root, payloads)
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except Exception:
        if stage.exists():
            for path in stage.iterdir():
                path.chmod(0o644)
            stage.chmod(0o755)
            for path in stage.iterdir():
                path.unlink()
            stage.rmdir()
        raise
    return output_root


def _rows(data: bytes, columns: Sequence[str] = G0_COLUMNS) -> list[dict[str, str]]:
    if not data.endswith(b"\n") or b"\r" in data:
        raise OraclePairCellIOError("G0 CSV line endings differ")
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True)
        if next(reader, None) != list(columns):
            raise OraclePairCellIOError("G0 columns differ")
        rows = [dict(zip(columns, values, strict=True)) for values in reader]
    except (UnicodeDecodeError, csv.Error) as exc:
        raise OraclePairCellIOError("G0 CSV is invalid") from exc
    if "episode_id" in columns:
        try:
            ordered = sorted(
                rows, key=lambda row: (row["episode_id"], int(row["query_rank"]))
            )
        except (KeyError, ValueError) as exc:
            raise OraclePairCellIOError("G0 query rank differs") from exc
        if rows != ordered:
            raise OraclePairCellIOError("G0 row order differs")
    return rows


def _validate_pair_rows(rows: Sequence[Mapping[str, str]]) -> None:
    systems = {"C0", "C1", "C2", "C3", "T0", "F0", "F1", "F2", "A0", "A1", "A2"}
    sources = {"G0", "LOCAL", "C0", "C1", "F0", "F1"}
    for row in rows:
        system = row["system_id"]
        source = row["prediction_source"]
        if system not in systems or source not in sources:
            raise OraclePairCellIOError("pair source vocabulary differs")
        _digest(row["candidate_id"], "pair candidate")
        value = _finite(row["prediction"], "pair prediction")
        if format(value, ".17g") != row["prediction"]:
            raise OraclePairCellIOError("pair prediction serialization differs")
        local = row["local_available"]
        if local not in {"true", "false"}:
            raise OraclePairCellIOError("pair local-availability token differs")
        if (local == "false") != (source == "G0"):
            raise OraclePairCellIOError("pair fallback source differs")
        if local == "true" and source not in {"LOCAL", "C0", "C1", "F0", "F1"}:
            raise OraclePairCellIOError("pair local source differs")
        for name in ("exact_support_components", "class_support_components"):
            try:
                support = int(row[name])
            except (KeyError, ValueError) as exc:
                raise OraclePairCellIOError("pair support count differs") from exc
            if support < 0 or str(support) != row[name]:
                raise OraclePairCellIOError("pair support count differs")


def _validate_manifest(
    manifest: Mapping[str, Any], scope: tuple[str, int, int, int | None]
) -> None:
    if (
        manifest.get("schema_version")
        != "cypshift.openadmet_cyp_2026.r5c_g0_prediction_fragment.v1"
    ):
        raise OraclePairCellIOError("G0 schema differs")
    if manifest.get("status") not in {
        "R5_ORACLE_G0_EPISODE_COMPLETE",
        "R5_ORACLE_PAIR_CELL_COMPLETE",
    }:
        raise OraclePairCellIOError("G0 status differs")
    if manifest.get("contract_sha256") != CONTRACT_SHA256:
        raise OraclePairCellIOError("G0 contract differs")
    _digest(manifest.get("candidate_id"), "G0 candidate")
    accounting = manifest.get("operation_accounting")
    if (
        not isinstance(accounting, Mapping)
        or set(accounting) != set(ACCOUNTING_FIELDS)
        or any(type(value) is not int or value < 0 for value in accounting.values())
    ):
        raise OraclePairCellIOError("G0 accounting differs")
    if any(accounting[name] for name in ACCOUNTING_FIELDS[8:]):
        raise OraclePairCellIOError("G0 forbidden operation")
    scope_value = manifest.get("scope")
    if not isinstance(scope_value, Mapping):
        raise OraclePairCellIOError("G0 scope differs")
    stage, repeat, outer, inner = scope
    expected = {
        "stage": stage,
        "repeat": repeat,
        "outer_fold": outer,
        "inner_fold": "" if inner is None else inner,
    }
    if dict(scope_value) != expected:
        raise OraclePairCellIOError("G0 scope differs")


def _validate_legacy_manifest(
    manifest: Mapping[str, Any],
    scope: tuple[str, int, int, int | None],
) -> None:
    if manifest.get("status") != "R5_ORACLE_G0_EPISODE_COMPLETE":
        raise OraclePairCellIOError("legacy G0 status differs")
    if manifest.get("contract_sha256") not in {
        CONTRACT_SHA256,
        "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623",
    }:
        raise OraclePairCellIOError("legacy G0 contract differs")
    candidate = manifest.get("candidate_id")
    if candidate is not None:
        _digest(candidate, "legacy G0 candidate")
    scope_value = manifest.get("scope")
    if not isinstance(scope_value, Mapping):
        raise OraclePairCellIOError("legacy G0 scope differs")
    stage, repeat, outer, inner = scope
    try:
        observed_repeat = int(scope_value.get("repeat", -1))
    except (TypeError, ValueError) as exc:
        raise OraclePairCellIOError("legacy G0 scope differs") from exc
    if scope_value.get("stage") != stage or observed_repeat != repeat:
        raise OraclePairCellIOError("legacy G0 scope differs")
    episode_outer = scope_value.get("episode_outer_fold", scope_value.get("outer_fold"))
    try:
        observed_outer = int(episode_outer)
    except (TypeError, ValueError) as exc:
        raise OraclePairCellIOError("legacy G0 outer scope differs") from exc
    if observed_outer != outer:
        raise OraclePairCellIOError("legacy G0 outer scope differs")
    episode = manifest.get("episode")
    if not isinstance(episode, Mapping) or not isinstance(
        episode.get("episode_id"), str
    ):
        raise OraclePairCellIOError("legacy G0 episode identity differs")
    accounting = manifest.get("operation_accounting")
    if not isinstance(accounting, Mapping) or any(
        type(value) is not int or value < 0 for value in accounting.values()
    ):
        raise OraclePairCellIOError("legacy G0 accounting differs")
    if any(accounting.get(name, 0) for name in ACCOUNTING_FIELDS[8:]):
        raise OraclePairCellIOError("legacy G0 forbidden operation")


def _validate_scope(
    scope: tuple[Literal["inner", "outer"], int, int, int | None],
) -> None:
    stage, repeat, outer, inner = scope
    if (
        stage not in {"inner", "outer"}
        or type(repeat) is not int
        or repeat not in range(3)
        or type(outer) is not int
        or outer not in range(5)
        or (stage == "outer" and inner is not None)
        or (stage == "inner" and (type(inner) is not int or inner not in range(4)))
    ):
        raise OraclePairCellIOError("scope differs")


def _validate_scope_mapping(scope: Mapping[str, Any]) -> dict[str, Any]:
    if set(scope) != {"stage", "repeat", "outer_fold", "inner_fold"}:
        raise OraclePairCellIOError("scope differs")
    stage = scope["stage"]
    repeat = scope["repeat"]
    outer = scope["outer_fold"]
    inner_value = scope["inner_fold"]
    if stage == "outer":
        inner: int | None = None if inner_value == "" else inner_value
    elif stage == "inner":
        inner = inner_value
    else:
        inner = None
    _validate_scope((stage, repeat, outer, inner))
    return {"stage": stage, "repeat": repeat, "outer_fold": outer, "inner_fold": inner}


def _open_root(path: Path) -> int:
    if ".." in path.parts or path.is_symlink():
        raise OraclePairCellIOError("G0 root path differs")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise OraclePairCellIOError("cannot open G0 root") from exc
    if not stat.S_ISDIR(os.fstat(fd).st_mode):
        os.close(fd)
        raise OraclePairCellIOError("G0 root is not a directory")
    return fd


def _read_at(root_fd: int, name: str) -> bytes:
    try:
        fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=root_fd)
    except OSError as exc:
        raise OraclePairCellIOError(f"cannot open G0 file: {name}") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise OraclePairCellIOError(f"G0 file is not regular: {name}")
        chunks: list[bytes] = []
        while block := os.read(fd, 1024 * 1024):
            chunks.append(block)
        result = b"".join(chunks)
        if len(result) != info.st_size:
            raise OraclePairCellIOError(f"G0 file changed: {name}")
        return result
    finally:
        os.close(fd)


def _rename_noreplace(source: Path, destination: Path) -> None:
    import ctypes
    import errno

    libc = ctypes.CDLL(None, use_errno=True)
    function = getattr(libc, "renameat2", None)
    if function is None:
        raise OraclePairCellIOError("renameat2 unavailable")
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    function.restype = ctypes.c_int
    if function(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        raise OraclePairCellIOError(
            "pair output exists" if error == errno.EEXIST else os.strerror(error)
        )


def _reopen_output(root: Path, payloads: Mapping[str, bytes]) -> None:
    fd = _open_root(root)
    try:
        if set(os.listdir(fd)) != set(payloads):
            raise OraclePairCellIOError("published pair file set differs")
        for name, expected in payloads.items():
            if _read_at(fd, name) != expected:
                raise OraclePairCellIOError(f"published pair bytes differ: {name}")
    finally:
        os.close(fd)


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        + b"\n"
    )


def _json(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OraclePairCellIOError(f"{label} is invalid") from exc
    if not isinstance(value, dict) or _json_bytes(value) != data:
        raise OraclePairCellIOError(f"{label} is not canonical")
    return value


def _digest(value: object, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise OraclePairCellIOError(f"{label} is not SHA-256")


def _finite(value: str, label: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise OraclePairCellIOError(f"{label} is not finite") from exc
    if not math.isfinite(result):
        raise OraclePairCellIOError(f"{label} is not finite")
    return result


__all__ = [
    "ACCOUNTING_FIELDS",
    "CONTRACT_SHA256",
    "OraclePairCellIOError",
    "load_g0_predictions",
    "publish_pair_cell",
]

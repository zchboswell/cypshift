"""Descriptor-authenticated capability loading for isolated R5C model cells."""

from __future__ import annotations

import os
import stat
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Literal, cast

from cypshift.openadmet_oracle_cell_validation import (
    AuthenticatedRoot,
    OpenADMETOracleCellValidationError,
    OracleC3TargetCapability,
    OracleCellCapability,
    OracleCellTargetCapability,
    OracleModelPublicCapability,
    Scope,
    validate_cell_capabilities,
)
from cypshift.openadmet_oracle_projection import (
    C3_FILES,
    CELL_FILES,
    CONTRACT_SHA256,
    FORBIDDEN_PUBLIC_FIELDS,
    PARENT_CONTRACT_SHA256,
    PUBLIC_FILES,
    ROOT_ACCOUNTING,
    SCHEMA_VERSION,
    SOURCE_PARENT_FILES,
)
from cypshift.openadmet_oracle_validation import (
    G0_SYSTEM_ID,
    SOURCE_COLUMNS,
    output_columns,
)
from cypshift.openadmet_transformation_io import (
    canonical_json_bytes,
    strict_json_object,
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
MANIFEST_FIELDS: Final = {
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
SOURCE_BUNDLE_SCHEMA: Final = "cypshift.openadmet_cyp_2026.oracle_source_bundle.v1"
MODEL_FILES: Final = tuple(name for name in PUBLIC_FILES if name != "manifest.json")
CELL_FILES_NO_MANIFEST: Final = tuple(
    name for name in CELL_FILES if name != "manifest.json"
)
C3_FILES_NO_MANIFEST: Final = tuple(
    name for name in C3_FILES if name != "manifest.json"
)
SOURCE_NAMES: Final = {
    "model-public": frozenset(MODEL_FILES),
    "cell-target": frozenset(
        {
            "molecules.csv",
            "folds.csv",
            "public_episode_queries.csv",
            "transformation_pairs.csv",
            "training_points.csv",
            "training_pairs.csv",
            "episode_anchor_contexts.csv",
        }
    ),
    "c3-target": frozenset(
        {
            "molecules.csv",
            "folds.csv",
            "public_episode_queries.csv",
            "transformation_pairs.csv",
            "training_pairs.csv",
            "global_anchor_contexts.csv",
        }
    ),
}
CELL_SYSTEMS: Final = frozenset(
    {"G0", "C0", "C1", "C2", "T0", "F0", "F1", "F2", "A0", "A1", "A2"}
)


class OpenADMETOracleCellIOError(ValueError):
    """A descriptor, manifest, receipt, or capability binding failed."""


OracleCellIOError = OpenADMETOracleCellIOError


def load_oracle_cell_capability(
    model_public_root: Path,
    target_root: Path,
    *,
    expected_model_manifest_sha256: str,
    expected_target_manifest_sha256: str,
    system_id: str,
    target_kind: Literal["cell-target", "c3-target"],
    expected_scope: Scope,
) -> OracleCellCapability:
    """Load one externally bound model/target pair for one requested system."""

    _validate_request(system_id, target_kind, expected_scope)
    model = _load_root(
        model_public_root,
        "model-public",
        MODEL_FILES,
        expected_model_manifest_sha256,
        "all",
    )
    target_files = (
        CELL_FILES_NO_MANIFEST if target_kind == "cell-target" else C3_FILES_NO_MANIFEST
    )
    target = _load_root(
        target_root,
        target_kind,
        target_files,
        expected_target_manifest_sha256,
        _scope_object(expected_scope),
    )
    _validate_pairing(model, target)
    if target_kind == "c3-target":
        _reject_c3_measured_material(target)
    try:
        return validate_cell_capabilities(
            model, target, system_id=system_id, scope=expected_scope
        )
    except OpenADMETOracleCellValidationError as exc:
        raise OpenADMETOracleCellIOError(str(exc)) from exc


def _validate_request(system_id: str, target_kind: str, scope: Scope) -> None:
    expected_kind = "c3-target" if system_id == "C3" else "cell-target"
    if system_id not in CELL_SYSTEMS | {"C3"}:
        raise OpenADMETOracleCellIOError("requested system is not an R5 cell system")
    if target_kind != expected_kind:
        raise OpenADMETOracleCellIOError("requested system/target capability differs")
    stage, repeat, outer, inner = scope
    if (
        stage not in {"outer", "inner"}
        or repeat not in range(3)
        or outer not in range(5)
        or (stage == "outer" and inner is not None)
        or (stage == "inner" and inner not in range(4))
    ):
        raise OpenADMETOracleCellIOError("requested scope differs")


def _load_root(
    root: Path,
    kind: str,
    leaf_names: Sequence[str],
    expected_manifest_sha256: str,
    expected_scope: str | Mapping[str, Any],
) -> AuthenticatedRoot:
    _require_digest(expected_manifest_sha256, "expected manifest")
    _validate_root_path(root, kind, expected_scope)
    root_fd = _open_directory_no_symlinks(root)
    try:
        expected_names = {"manifest.json", *leaf_names}
        if set(os.listdir(root_fd)) != expected_names:
            raise OpenADMETOracleCellIOError("capability root file set differs")
        manifest_data = _read_regular(root_fd, "manifest.json")
        manifest_digest = sha256(manifest_data).hexdigest()
        if manifest_digest != expected_manifest_sha256:
            raise OpenADMETOracleCellIOError("out-of-band manifest receipt differs")
        manifest = _json(manifest_data, "root manifest")
        _validate_manifest(manifest, kind, leaf_names, expected_scope)
        receipts = _object(manifest["output_receipts"], "output receipts")
        loaded: dict[str, bytes] = {}
        for name in leaf_names:
            data = _read_regular(root_fd, name)
            receipt = _object(receipts[name], f"receipt {name}")
            if sha256(data).hexdigest() != receipt["sha256"]:
                raise OpenADMETOracleCellIOError(f"receipt differs: {name}")
            if receipt["bytes"] != len(data):
                raise OpenADMETOracleCellIOError(f"byte count differs: {name}")
            if name.endswith(".csv") and receipt["rows"] != data.count(b"\n") - 1:
                raise OpenADMETOracleCellIOError(f"row count differs: {name}")
            loaded[name] = data
    finally:
        os.close(root_fd)
    return AuthenticatedRoot(
        kind,
        _freeze(manifest),
        manifest_digest,
        MappingProxyType(loaded),
    )


def _validate_manifest(
    manifest: Mapping[str, Any],
    kind: str,
    leaf_names: Sequence[str],
    expected_scope: str | Mapping[str, Any],
) -> None:
    expected_scalars = {
        "schema_version": SCHEMA_VERSION,
        "status": "R5_ORACLE_SYNTHETIC_CAPABILITY_PROJECTION",
        "contract_sha256": CONTRACT_SHA256,
        "parent_contract_sha256": PARENT_CONTRACT_SHA256,
        "root": kind,
        "fixed_oof_system_id": G0_SYSTEM_ID,
        "current_cell_scope": expected_scope,
        "capability_root_accounting": ROOT_ACCOUNTING,
        "accounting_scope": "values present in this capability root",
        "authority": DENIED_AUTHORITY,
        "forbidden_fields": (
            list(FORBIDDEN_PUBLIC_FIELDS) if kind == "model-public" else []
        ),
    }
    if set(manifest) != MANIFEST_FIELDS or any(
        manifest.get(key) != value for key, value in expected_scalars.items()
    ):
        raise OpenADMETOracleCellIOError("root manifest contract differs")
    for key in ("operation_accounting", "projector_operation_accounting"):
        _validate_accounting(manifest.get(key), key)
    receipts = _object(manifest["output_receipts"], "output receipts")
    if set(receipts) != set(leaf_names):
        raise OpenADMETOracleCellIOError("output receipt set differs")
    for name in leaf_names:
        _validate_receipt(receipts[name], name, output=True)
    sources = _object(manifest["source_receipts"], "source receipts")
    if set(sources) != SOURCE_NAMES[kind]:
        raise OpenADMETOracleCellIOError("source receipt set differs")
    for name, value in sources.items():
        _validate_receipt(value, name, output=False)
    if kind == "model-public" and any(
        receipts[name] != sources[name] for name in leaf_names if name.endswith(".npy")
    ):
        raise OpenADMETOracleCellIOError("model-public feature/source binding differs")
    _validate_source_binding(manifest["source_bundle_binding"])


def _validate_accounting(value: Any, label: str) -> None:
    accounting = _object(value, label)
    if set(accounting) != set(ACCOUNTING_FIELDS) or any(
        not _nonnegative_int(item) for item in accounting.values()
    ):
        raise OpenADMETOracleCellIOError(f"{label} differs")
    if any(accounting[name] for name in ACCOUNTING_FIELDS[8:]):
        raise OpenADMETOracleCellIOError(f"{label} grants forbidden capability")


def _validate_receipt(value: Any, name: str, *, output: bool) -> None:
    receipt = _object(value, f"receipt {name}")
    expected = {"sha256", "bytes"}
    if name.endswith(".csv"):
        expected |= {"rows", "columns"}
    if set(receipt) != expected or not _nonnegative_int(receipt.get("bytes")):
        raise OpenADMETOracleCellIOError(f"receipt metadata differs: {name}")
    _require_digest(receipt.get("sha256"), f"receipt {name}")
    if name.endswith(".csv"):
        columns = output_columns(name) if output else SOURCE_COLUMNS[name]
        if not _nonnegative_int(receipt.get("rows")) or receipt.get("columns") != list(
            columns
        ):
            raise OpenADMETOracleCellIOError(f"receipt columns differ: {name}")


def _validate_source_binding(value: Any) -> None:
    binding = _object(value, "source bundle binding")
    if set(binding) != {
        "manifest_receipt",
        "schema_version",
        "contract_sha256",
        "parent_receipts",
        "input_receipts",
        "source_receipts",
    }:
        raise OpenADMETOracleCellIOError("source bundle binding fields differ")
    if (
        binding["schema_version"] != SOURCE_BUNDLE_SCHEMA
        or binding["contract_sha256"] != CONTRACT_SHA256
    ):
        raise OpenADMETOracleCellIOError("source bundle binding contract differs")
    manifest_receipt = _object(binding["manifest_receipt"], "source manifest receipt")
    if set(manifest_receipt) != {"sha256", "bytes"}:
        raise OpenADMETOracleCellIOError("source manifest receipt fields differ")
    _require_digest(manifest_receipt.get("sha256"), "source manifest receipt")
    if not _nonnegative_int(manifest_receipt.get("bytes")):
        raise OpenADMETOracleCellIOError("source manifest receipt bytes differ")
    parents = _object(binding["parent_receipts"], "parent receipts")
    inputs = _object(binding["input_receipts"], "input receipts")
    sources = _object(binding["source_receipts"], "bound source receipts")
    if set(parents) != set(SOURCE_PARENT_FILES) or set(inputs) != set(parents):
        raise OpenADMETOracleCellIOError("source parent receipt set differs")
    if inputs != sources:
        raise OpenADMETOracleCellIOError("source input/output binding differs")
    for name in SOURCE_PARENT_FILES:
        _require_digest(parents[name], f"parent receipt {name}")
        record = _object(inputs[name], f"input receipt {name}")
        if (
            set(record) != {"sha256", "bytes"}
            or record.get("sha256") != parents[name]
            or not _nonnegative_int(record.get("bytes"))
        ):
            raise OpenADMETOracleCellIOError(f"source input receipt differs: {name}")


def _validate_pairing(model: AuthenticatedRoot, target: AuthenticatedRoot) -> None:
    for key in (
        "contract_sha256",
        "parent_contract_sha256",
        "fixed_oof_system_id",
        "capability_root_accounting",
        "projector_operation_accounting",
        "source_bundle_binding",
    ):
        if model.manifest[key] != target.manifest[key]:
            raise OpenADMETOracleCellIOError(f"model/target {key} differs")
    model_sources = cast(Mapping[str, Any], model.manifest["source_receipts"])
    target_sources = cast(Mapping[str, Any], target.manifest["source_receipts"])
    for name in set(model_sources) & set(target_sources):
        if model_sources[name] != target_sources[name]:
            raise OpenADMETOracleCellIOError(f"model/target source differs: {name}")


def _reject_c3_measured_material(root: AuthenticatedRoot) -> None:
    forbidden = (b"anchor_point", b"anchor_point_available", b"training_points.csv")
    if any(token in data for data in root.files.values() for token in forbidden):
        raise OpenADMETOracleCellIOError("C3 target contains measured-point material")


def _validate_root_path(
    root: Path, kind: str, expected_scope: str | Mapping[str, Any]
) -> None:
    parts = root.parts
    if ".." in parts:
        raise OpenADMETOracleCellIOError("capability path contains traversal")
    if kind == "model-public":
        if root.name != "model-public":
            raise OpenADMETOracleCellIOError("model-public path differs")
        return
    scope = cast(Mapping[str, Any], expected_scope)
    repeat = f"repeat-{scope['repeat']}"
    outer = f"outer-{scope['outer_fold']}"
    expected_tail: tuple[str, ...]
    if scope["stage"] == "outer":
        expected_tail = (kind, "outer", repeat, outer)
    else:
        expected_tail = (
            kind,
            "inner",
            repeat,
            outer,
            f"inner-{scope['inner_fold']}",
        )
    if tuple(parts[-len(expected_tail) :]) != expected_tail:
        raise OpenADMETOracleCellIOError("target path scope differs")


def _open_directory_no_symlinks(path: Path) -> int:
    if ".." in path.parts:
        raise OpenADMETOracleCellIOError("capability path contains traversal")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        fd = os.open("/" if path.is_absolute() else ".", flags)
    except OSError as exc:
        raise OpenADMETOracleCellIOError("cannot open capability ancestry") from exc
    try:
        for part in path.parts:
            if part in {"/", ".", ""}:
                continue
            try:
                next_fd = os.open(part, flags, dir_fd=fd)
            except OSError as exc:
                raise OpenADMETOracleCellIOError(
                    "cannot open capability ancestry"
                ) from exc
            os.close(fd)
            fd = next_fd
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OpenADMETOracleCellIOError("capability root is not a directory")
        return fd
    except Exception:
        os.close(fd)
        raise


def _read_regular(root_fd: int, name: str) -> bytes:
    if not name or "/" in name or name in {".", ".."}:
        raise OpenADMETOracleCellIOError("capability filename differs")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        fd = os.open(name, flags, dir_fd=root_fd)
    except OSError as exc:
        raise OpenADMETOracleCellIOError(f"cannot open regular file: {name}") from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise OpenADMETOracleCellIOError(f"capability leaf is not regular: {name}")
        data = _read_fd_bytes(fd)
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
            raise OpenADMETOracleCellIOError(
                f"capability leaf changed while read: {name}"
            )
        return data
    finally:
        os.close(fd)


def _read_fd_bytes(fd: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _scope_object(scope: Scope) -> dict[str, int | str]:
    stage, repeat, outer, inner = scope
    return {
        "stage": stage,
        "repeat": repeat,
        "outer_fold": outer,
        "inner_fold": "" if inner is None else inner,
    }


def _json(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = strict_json_object(data, label)
    except ValueError as exc:
        raise OpenADMETOracleCellIOError(str(exc)) from exc
    if canonical_json_bytes(value) != data:
        raise OpenADMETOracleCellIOError(f"{label} is not canonical")
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OpenADMETOracleCellIOError(f"{label} is not an object")
    return cast(dict[str, Any], value)


def _require_digest(value: Any, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise OpenADMETOracleCellIOError(f"{label} is not SHA-256")


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


__all__ = [
    "OpenADMETOracleCellIOError",
    "OracleC3TargetCapability",
    "OracleCellCapability",
    "OracleCellIOError",
    "OracleCellTargetCapability",
    "OracleModelPublicCapability",
    "Scope",
    "load_oracle_cell_capability",
]

"""Shared receipt, CSV, JSON, and safe-publication helpers for R3B projection."""

from __future__ import annotations

import csv
import ctypes
import errno
import io
import json
import math
import os
import platform
import shutil
import sys
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any, cast


class OpenADMETGlobalProjectionError(ValueError):
    """A receipt, schema, membership, or publication invariant failed."""


PROJECTION_SOURCE_FILES = (
    "src/cypshift/openadmet_global_io.py",
    "src/cypshift/openadmet_global_projection.py",
)
PREFLIGHT_SOURCE_FILES = (
    "src/cypshift/openadmet_global_io.py",
    "src/cypshift/openadmet_global_preflight.py",
)
UV_LOCK_SHA256 = "33d9382256de7992ce9ff7a7edc125d4771546a25ef3be5f1160627846d2c9b6"


def _source_bundle_sha256(relative_paths: Sequence[str]) -> str:
    root = Path(__file__).resolve().parents[2]
    material: list[str] = []
    for relative in sorted(relative_paths):
        path = root / relative
        data = _read_regular(path, f"source bundle file {relative}")
        material.append(f"{relative}|{sha256(data).hexdigest()}")
    return sha256(("\n".join(material) + "\n").encode()).hexdigest()


def _runtime_gate(relative_paths: Sequence[str]) -> str:
    if sys.version_info[:3] != (3, 12, 3):
        raise OpenADMETGlobalProjectionError("projector requires Python 3.12.3")
    root = Path(__file__).resolve().parents[2]
    lock = _read_regular(root / "uv.lock", "root uv.lock")
    if sha256(lock).hexdigest() != UV_LOCK_SHA256:
        raise OpenADMETGlobalProjectionError("root uv.lock receipt mismatch")
    return _source_bundle_sha256(relative_paths)


def _digest(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str):
        raise OpenADMETGlobalProjectionError(f"{key} must be SHA-256")
    _digest_text(item, key)
    return item


def _digest_match(data: bytes, expected: str, label: str) -> None:
    _digest_text(expected, label)
    if sha256(data).hexdigest() != expected:
        raise OpenADMETGlobalProjectionError(f"{label} SHA-256 mismatch")


def _digest_text(value: str, label: str) -> None:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise OpenADMETGlobalProjectionError(f"{label} must be lowercase SHA-256")


def _parse_csv(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    if b"\r" in data or not data.endswith(b"\n"):
        raise OpenADMETGlobalProjectionError(f"{label} has invalid line endings")
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True)
        if next(reader, None) != list(columns):
            raise OpenADMETGlobalProjectionError(f"{label} header mismatch")
        rows = []
        for values in reader:
            if len(values) != len(columns):
                raise OpenADMETGlobalProjectionError(f"{label} field-count mismatch")
            rows.append(dict(zip(columns, values, strict=True)))
        return rows
    except (UnicodeError, csv.Error) as exc:
        raise OpenADMETGlobalProjectionError(f"cannot parse {label}") from exc


def _csv_bytes(columns: Sequence[str], rows: Sequence[Mapping[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=list(columns), lineterminator="\n", extrasaction="raise"
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _json_object(data: bytes, label: str) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise OpenADMETGlobalProjectionError(
                    f"duplicate JSON key in {label}: {key}"
                )
            result[key] = value
        return result

    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except OpenADMETGlobalProjectionError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OpenADMETGlobalProjectionError(f"cannot parse {label}") from exc
    if not isinstance(value, dict):
        raise OpenADMETGlobalProjectionError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _object(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise OpenADMETGlobalProjectionError(f"{key} must be an object")
    return cast(dict[str, Any], item)


def _read_regular(path: Path, label: str) -> bytes:
    if any(candidate.is_symlink() for candidate in (path, *path.parents)):
        raise OpenADMETGlobalProjectionError(
            f"{label} must be a regular non-symlink file"
        )
    if not path.is_file():
        raise OpenADMETGlobalProjectionError(
            f"{label} must be a regular non-symlink file"
        )
    try:
        return path.read_bytes()
    except OSError as exc:
        raise OpenADMETGlobalProjectionError(f"cannot read {label}: {exc}") from exc


def _resolve_parent(base: Path, relative: str) -> Path:
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise OpenADMETGlobalProjectionError(
            "parent contract path escapes contract root"
        )
    if relative.startswith("benchmarks/"):
        root = Path(__file__).resolve().parents[2]
        return root / relative_path
    return base.parent / relative_path


def _occupied(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _new_file(path: Path, data: bytes) -> None:
    current = path.parent
    while current != current.parent:
        if current.is_symlink():
            raise OpenADMETGlobalProjectionError("output path contains symlink")
        current = current.parent
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.exists():
        raise OpenADMETGlobalProjectionError("staged output path already exists")
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise OpenADMETGlobalProjectionError(f"cannot write {path}: {exc}") from exc


def _readonly_tree(path: Path) -> None:
    for child in path.rglob("*"):
        if child.is_symlink():
            raise OpenADMETGlobalProjectionError("staged output contains symlink")
        if child.is_file():
            child.chmod(0o444)
    for child in sorted(
        path.rglob("*"), key=lambda item: len(item.parts), reverse=True
    ):
        if child.is_dir():
            child.chmod(0o555)
    path.chmod(0o555)


def _rename_noreplace(source: Path, destination: Path) -> None:
    if platform.system() != "Linux" or os.name != "posix":
        raise OpenADMETGlobalProjectionError(
            "atomic no-replace promotion requires Linux renameat2"
        )
    try:
        renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
    except (AttributeError, OSError) as exc:
        raise OpenADMETGlobalProjectionError("renameat2 unavailable") from exc
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        -100,
        os.fsencode(os.path.abspath(source)),
        -100,
        os.fsencode(os.path.abspath(destination)),
        1,
    )
    if result != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise OpenADMETGlobalProjectionError(
                "output path already exists; refusing overwrite"
            )
        raise OpenADMETGlobalProjectionError(
            f"atomic promotion failed: {os.strerror(error)}"
        )


def _cleanup_stage(stage: Path | None) -> None:
    if stage is None or not stage.exists():
        return
    for path in sorted(
        stage.rglob("*"), key=lambda item: len(item.parts), reverse=True
    ):
        try:
            if path.is_file():
                path.chmod(0o644)
            elif path.is_dir():
                path.chmod(0o755)
        except OSError:
            pass
    shutil.rmtree(stage, ignore_errors=True)


def _file_receipt(
    path: str,
    data: bytes,
    rows: Sequence[Mapping[str, str]],
    columns: Sequence[str],
    eligible_rows: int | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": path,
        "sha256": sha256(data).hexdigest(),
        "bytes": len(data),
        "rows": len(rows),
        "columns": list(columns),
        "schema_version": "",
    }
    if eligible_rows is not None:
        result["eligible_rows"] = eligible_rows
    return result


def _target_receipt(
    stage: str,
    endpoint: str,
    repeat: int,
    outer: int,
    inner: int | None,
    relative: Path,
    data: bytes,
    rows: Sequence[Mapping[str, str]],
    contract_sha: str,
) -> dict[str, Any]:
    identity_rows = [
        {"observation_id": row["observation_id"], "molecule_id": row["molecule_id"]}
        for row in rows
    ]
    identity = _csv_bytes(("observation_id", "molecule_id"), identity_rows)
    token = "none" if inner is None else str(inner)
    scope = _scope(stage, outer)
    material = "|".join(
        (contract_sha, stage, endpoint, str(repeat), str(outer), token, scope)
    )
    return {
        "stage": stage,
        "cell_id": sha256(material.encode()).hexdigest(),
        "endpoint": endpoint,
        "repeat": repeat,
        "outer_fold": outer,
        "inner_fold": "" if inner is None else inner,
        "relative_path": relative.as_posix(),
        "sha256": sha256(data).hexdigest(),
        "rows": len(rows),
        "identity_sha256": sha256(identity).hexdigest(),
    }


def _target_path(
    stage: str, endpoint: str, repeat: int, outer: int, inner: int | None
) -> Path:
    if stage == "outer":
        return (
            Path("outer_targets") / endpoint / f"repeat-{repeat}" / f"outer-{outer}.csv"
        )
    return (
        Path("inner_targets")
        / endpoint
        / f"repeat-{repeat}"
        / f"outer-{outer}"
        / f"inner-{inner}.csv"
    )


def _scope(stage: str, outer: int) -> str:
    return (
        "openadmet-direct-outer-v1"
        if stage == "outer"
        else f"openadmet-direct-inner-v1|outer={outer}"
    )


def _truth_eligible(row: Mapping[str, str]) -> int:
    if row["value_state"] != "complete" or row["point_eligible"] != "true":
        return 0
    try:
        return int(math.isfinite(float(row["point"])))
    except ValueError:
        return 0


def _outer_truth_key(row: Mapping[str, str]) -> tuple[str, int, int, str]:
    return (
        row["endpoint"],
        int(row["repeat"]),
        int(row["outer_fold"]),
        row["molecule_id"],
    )


def _inner_truth_key(row: Mapping[str, str]) -> tuple[str, int, int, int, str]:
    return (
        row["endpoint"],
        int(row["repeat"]),
        int(row["outer_fold"]),
        int(row["inner_fold"]),
        row["molecule_id"],
    )


def _lookup_fold(
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
    molecule: str,
    repeat: int,
    context: int,
) -> Mapping[str, str]:
    try:
        return folds[(molecule, repeat, context)]
    except KeyError as exc:
        raise OpenADMETGlobalProjectionError("missing indexed fold context") from exc


def _canonical_uint(row: Mapping[str, str], key: str, upper: int) -> int:
    value = row.get(key, "")
    if (
        not value
        or not value.isascii()
        or not value.isdecimal()
        or (len(value) > 1 and value.startswith("0"))
    ):
        raise OpenADMETGlobalProjectionError(f"invalid canonical fold integer: {key}")
    parsed = int(value)
    if parsed not in range(upper):
        raise OpenADMETGlobalProjectionError(f"fold integer out of range: {key}")
    return parsed


def _validate_fold_index(
    rows: Sequence[Mapping[str, str]],
    direct_rows: int,
    fold_rows: int,
    seeds: Sequence[int],
) -> dict[tuple[str, int, int], dict[str, str]]:
    molecule_count = direct_rows // 4
    if direct_rows % 4 or len(rows) != fold_rows or len(rows) != molecule_count * 15:
        raise OpenADMETGlobalProjectionError("group_folds row count mismatch")
    result: dict[tuple[str, int, int], dict[str, str]] = {}
    molecule_components: dict[str, str] = {}
    outer_assignments: dict[tuple[str, int], int] = {}
    component_outer: dict[tuple[str, int], int] = {}
    component_inner: dict[tuple[str, int, int], str] = {}
    contexts: dict[tuple[str, int], set[int]] = {}
    for row in rows:
        molecule = row.get("molecule_id", "")
        component = row.get("similarity_component_hash", "")
        if not molecule:
            raise OpenADMETGlobalProjectionError("empty fold molecule")
        _digest_text(component, "fold component")
        if (
            molecule in molecule_components
            and molecule_components[molecule] != component
        ):
            raise OpenADMETGlobalProjectionError("molecule component hash drift")
        molecule_components[molecule] = component
        repeat = _canonical_uint(row, "repeat", len(seeds))
        outer = _canonical_uint(row, "outer_fold", 5)
        validation = _canonical_uint(row, "outer_validation_fold", 5)
        if row.get("seed") != str(seeds[repeat]):
            raise OpenADMETGlobalProjectionError("fold policy mismatch")
        inner = row.get("inner_fold", "")
        if outer == validation:
            if inner != "":
                raise OpenADMETGlobalProjectionError(
                    "heldout molecule has nonblank inner fold"
                )
        else:
            if inner == "":
                raise OpenADMETGlobalProjectionError(
                    "outer-training molecule has blank inner fold"
                )
            _canonical_uint({"inner_fold": inner}, "inner_fold", 4)
        assignment_key = (molecule, repeat)
        if (
            assignment_key in outer_assignments
            and outer_assignments[assignment_key] != outer
        ):
            raise OpenADMETGlobalProjectionError("molecule outer assignment drift")
        outer_assignments[assignment_key] = outer
        component_key = (component, repeat)
        if component_key in component_outer and component_outer[component_key] != outer:
            raise OpenADMETGlobalProjectionError("component outer assignment drift")
        component_outer[component_key] = outer
        if outer != validation:
            inner_key = (component, repeat, validation)
            if inner_key in component_inner and component_inner[inner_key] != inner:
                raise OpenADMETGlobalProjectionError("component inner assignment drift")
            component_inner[inner_key] = inner
        lookup_key = (molecule, repeat, validation)
        if lookup_key in result:
            raise OpenADMETGlobalProjectionError("duplicate fold lookup key")
        result[lookup_key] = dict(row)
        contexts.setdefault(assignment_key, set()).add(validation)
    if len(molecule_components) != molecule_count or any(
        seen != set(range(5)) for seen in contexts.values()
    ):
        raise OpenADMETGlobalProjectionError("fold context coverage mismatch")
    return result


def _verify_projection_counts(
    contract: Mapping[str, Any],
    counts: Mapping[str, int],
    override: Mapping[str, int] | None,
) -> None:
    expected = (
        override
        or _object(_object(contract, "amendments"), "eligibility_counts")["production"]
    )
    if not isinstance(expected, Mapping) or any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in expected.values()
    ):
        raise OpenADMETGlobalProjectionError("expected count types mismatch")
    for key in (
        "outer_target_files",
        "inner_target_files",
        "outer_target_rows",
        "inner_target_rows",
        "outer_truth_rows",
        "inner_truth_rows",
        "outer_truth_eligible",
        "inner_truth_eligible",
    ):
        if key in expected and int(expected[key]) != counts[key]:
            raise OpenADMETGlobalProjectionError(f"projected count mismatch: {key}")


def _verify_count_equations(counts: Mapping[str, int]) -> None:
    if any(value < 0 for value in counts.values()):
        raise OpenADMETGlobalProjectionError("negative eligibility count")
    if counts["ineligible"] != counts["direct_rows"] - counts["eligible"]:
        raise OpenADMETGlobalProjectionError("eligibility count equation mismatch")
    if (
        counts["complete"]
        + counts["partial"]
        + counts["missing"]
        + counts["orphan_auxiliary"]
        != counts["direct_rows"]
    ):
        raise OpenADMETGlobalProjectionError("state count equation mismatch")
    if counts["eligible"] > counts["complete"]:
        raise OpenADMETGlobalProjectionError("eligible state equation mismatch")
    if counts["outer_truth_eligible"] > counts["outer_truth_rows"]:
        raise OpenADMETGlobalProjectionError("outer truth equation mismatch")
    if counts["inner_truth_eligible"] > counts["inner_truth_rows"]:
        raise OpenADMETGlobalProjectionError("inner truth equation mismatch")


def _verify_staged_projection(
    stage: Path,
    contract_sha: str,
    direct_rows: int,
    folds_data: bytes,
    expected_model_manifest_data: bytes,
    expected_sealed_manifest_data: bytes,
    expected_audit_data: bytes,
    outer: Mapping[Any, Sequence[Mapping[str, str]]],
    inner: Mapping[Any, Sequence[Mapping[str, str]]],
    outer_truth: Sequence[Mapping[str, str]],
    inner_truth: Sequence[Mapping[str, str]],
    model_columns: Sequence[str],
    target_columns: Sequence[str],
    truth_columns: Sequence[str],
) -> None:
    public = stage / "model-public"
    sealed = stage / "scorer-sealed"
    model_path = public / "model_public_manifest.json"
    sealed_path = sealed / "sealed_truth_manifest.json"
    audit_path = stage / "private_projection_audit.json"
    model_data = _read_regular(model_path, "staged model manifest")
    sealed_data = _read_regular(sealed_path, "staged sealed manifest")
    audit_data = _read_regular(audit_path, "staged projection audit")
    if (
        model_data != expected_model_manifest_data
        or sealed_data != expected_sealed_manifest_data
        or audit_data != expected_audit_data
    ):
        raise OpenADMETGlobalProjectionError(
            "staged manifest or audit bytes changed before promotion"
        )
    model_manifest = _json_object(model_data, "staged model manifest")
    sealed_manifest = _json_object(sealed_data, "staged sealed manifest")
    audit = _json_object(audit_data, "staged projection audit")
    if set(model_manifest) != {
        "schema_version",
        "contract_sha256",
        "parent_contract_sha256",
        "projector_source_sha256",
        "model_rows",
        "outer_target_receipts",
        "inner_target_receipts",
        "accounting",
        "authority",
    }:
        raise OpenADMETGlobalProjectionError("staged model manifest schema mismatch")
    if set(sealed_manifest) != {
        "schema_version",
        "contract_sha256",
        "parent_contract_sha256",
        "projector_source_sha256",
        "outer_truth",
        "inner_truth",
        "accounting",
        "authority",
    }:
        raise OpenADMETGlobalProjectionError("staged sealed manifest schema mismatch")
    if set(audit) != {
        "schema_version",
        "contract_sha256",
        "parent_contract_sha256",
        "input_receipts",
        "model_public_manifest_sha256",
        "sealed_truth_manifest_sha256",
        "eligibility_counts",
        "projector_source_sha256",
        "accounting",
        "authority",
    }:
        raise OpenADMETGlobalProjectionError("staged audit schema mismatch")
    for artifact in (model_manifest, sealed_manifest, audit):
        if artifact.get("contract_sha256") != contract_sha:
            raise OpenADMETGlobalProjectionError("staged contract receipt mismatch")
    if model_manifest.get("accounting") != {
        "truth_paths": 0,
        "truth_hashes": 0,
        "scores": 0,
        "metrics": 0,
    }:
        raise OpenADMETGlobalProjectionError("staged public accounting mismatch")
    if sealed_manifest.get("accounting") != {
        "sealed_truth_files_written": 2,
        "outer_truth_rows": len(outer_truth),
        "inner_truth_rows": len(inner_truth),
        "truth_metadata_public": 0,
        "tdi_files_opened": 0,
        "blinded_test_rows_opened": 0,
        "episode_or_anchor_files_opened": 0,
        "transductive_operations": 0,
    }:
        raise OpenADMETGlobalProjectionError("staged sealed accounting mismatch")
    audit_accounting = _object(audit, "accounting")
    if audit_accounting != {
        "outer_target_files_written": 60,
        "inner_target_files_written": 240,
        "sealed_truth_files_written": 2,
        "direct_observation_rows_parsed": direct_rows,
        "target_rows_written": sum(len(rows) for rows in outer.values())
        + sum(len(rows) for rows in inner.values()),
        "truth_rows_written": len(outer_truth) + len(inner_truth),
        "tdi_files_opened": 0,
        "blinded_test_rows_opened": 0,
        "episode_or_anchor_files_opened": 0,
        "transductive_operations": 0,
    }:
        raise OpenADMETGlobalProjectionError("staged projector accounting mismatch")
    model_rows = _object(model_manifest, "model_rows")
    model_payload = _read_regular(public / "model_rows.csv", "staged model rows")
    if (
        model_payload != folds_data
        or model_rows.get("sha256") != sha256(model_payload).hexdigest()
    ):
        raise OpenADMETGlobalProjectionError("staged model rows receipt mismatch")
    if model_rows.get("rows") != len(
        _parse_csv(model_payload, model_columns, "staged model rows")
    ):
        raise OpenADMETGlobalProjectionError("staged model rows count mismatch")
    pending: list[
        tuple[Path, bytes, Sequence[Mapping[str, str]], Mapping[str, Any]]
    ] = []
    for stage_name, cells, field, expected_count in (
        ("outer", outer, "outer_target_receipts", 60),
        ("inner", inner, "inner_target_receipts", 240),
    ):
        receipts = _object_list(model_manifest, field)
        if len(receipts) != expected_count or len(cells) != expected_count:
            raise OpenADMETGlobalProjectionError("staged target receipt count mismatch")
        for key, rows in sorted(cells.items(), key=lambda item: item[0]):
            endpoint, repeat, outer_fold, inner_fold = key
            path = (
                stage
                / "model-public"
                / _target_path(stage_name, endpoint, repeat, outer_fold, inner_fold)
            )
            data = _read_regular(path, f"staged {stage_name} target")
            expected_receipt = _target_receipt(
                stage_name,
                endpoint,
                repeat,
                outer_fold,
                inner_fold,
                path.relative_to(public),
                data,
                rows,
                contract_sha,
            )
            receipt = next(
                (
                    item
                    for item in receipts
                    if item.get("cell_id") == expected_receipt["cell_id"]
                ),
                None,
            )
            if receipt != expected_receipt:
                raise OpenADMETGlobalProjectionError("staged target receipt mismatch")
            pending.append((path, data, rows, receipt))
    for path, data, expected_rows, target_receipt in pending:
        parsed = _parse_csv(data, target_columns, path.as_posix())
        if (
            parsed != [dict(row) for row in expected_rows]
            or len(parsed) != target_receipt["rows"]
        ):
            raise OpenADMETGlobalProjectionError("staged target membership mismatch")
    for name, rows, field in (
        ("sealed_outer_truth.csv", outer_truth, "outer_truth"),
        ("sealed_inner_truth.csv", inner_truth, "inner_truth"),
    ):
        path = sealed / name
        data = _read_regular(path, f"staged {field}")
        parsed = _parse_csv(data, truth_columns, f"staged {field}")
        if parsed != [dict(row) for row in rows]:
            raise OpenADMETGlobalProjectionError("staged truth membership mismatch")
        truth_receipt = _object(sealed_manifest, field)
        expected = _file_receipt(
            name,
            data,
            rows,
            truth_columns,
            sum(_truth_eligible(row) for row in rows),
        )
        if truth_receipt != expected:
            raise OpenADMETGlobalProjectionError("staged truth receipt mismatch")
    if audit.get("model_public_manifest_sha256") != sha256(model_data).hexdigest():
        raise OpenADMETGlobalProjectionError("staged audit model digest mismatch")
    if audit.get("sealed_truth_manifest_sha256") != sha256(sealed_data).hexdigest():
        raise OpenADMETGlobalProjectionError("staged audit sealed digest mismatch")
    if (
        len(list((public / "outer_targets").rglob("*.csv"))) != 60
        or len(list((public / "inner_targets").rglob("*.csv"))) != 240
    ):
        raise OpenADMETGlobalProjectionError("staged target path count mismatch")


def _object_list(value: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    item = value.get(key)
    if not isinstance(item, list) or not all(isinstance(row, dict) for row in item):
        raise OpenADMETGlobalProjectionError(f"{key} must be an object array")
    return cast(list[dict[str, Any]], item)


__all__ = ["OpenADMETGlobalProjectionError"]

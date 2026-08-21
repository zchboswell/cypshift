"""Locked episode-level G0 authentication for the private R5C outer freezer."""

from __future__ import annotations

import csv
import io
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

from cypshift.openadmet_oracle_pair_cell import candidate_id, cell_id
from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS
from cypshift.openadmet_oracle_private_io import (
    OraclePrivateIOError,
    read_exact_root,
    read_stable_file,
)
from cypshift.openadmet_oracle_projection import DENIED_AUTHORITY, SOURCE_PARENT_FILES
from cypshift.openadmet_oracle_sealed import RESOLVED_CONTRACT_SHA256
from cypshift.openadmet_transformation_io import strict_json_object

ROOT: Final = Path(__file__).resolve().parents[2]
G0_SOURCE_FILES: Final = (
    "research/maplight-fixed/r5_oracle_g0_io.py",
    "research/maplight-fixed/run_r5_oracle_g0.py",
)
G0_RUNTIME: Final = {
    "platform": "Linux x86_64 CPU",
    "python_version": "3.10.13",
    "numpy_version": "1.25.2",
    "catboost_version": "1.2.1",
    "uv_lock_sha256": (
        "99e72821b69d9bb943a6e32adc7e0dec0e46c6d32df090241d4fb9296a4195d8"
    ),
    "cpu_only": True,
    "max_threads": 16,
}
G0_PARAMETER_SHA256: Final = (
    "c56235a54a883a9a4488f1c8779f9013dae777af0f99cd92c9da1c4f51e61757"
)
G0_PARAMETER_RECORD_SHA256: Final = (
    "0c912e0d06d0d24d58bdc0529d6b14d1706d6a933445885be881f95ba3678cb9"
)
G0_PARENT_CONTRACT_SHA256: Final = (
    "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
)
G0_COLUMNS: Final = (
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


class OracleOuterG0Error(ValueError):
    """A locked G0 receipt, runtime, source, or row differs."""


@dataclass(frozen=True, slots=True)
class G0Input:
    """All locked episode-level G0 roots for one outer context."""

    repeat: int
    outer_fold: int
    roots: tuple[Path, ...]
    expected_manifest_sha256: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LoadedG0:
    manifest_sha256: str
    manifest: Mapping[str, Any]
    rows: tuple[Mapping[str, str], ...]
    fragment_sha256: str


def load_g0_roots(
    source: G0Input,
    *,
    expected_g0_source_sha256: str,
    public_rows: Sequence[Mapping[str, str]],
) -> tuple[LoadedG0, ...]:
    """Authenticate all locked G0 roots and their exact public superset."""

    if len(source.roots) != len(source.expected_manifest_sha256) or not source.roots:
        raise OracleOuterG0Error("G0 input cardinality differs")
    public = {
        (row["episode_id"], row["query_molecule_id"], row["query_rank"]): row
        for row in public_rows
    }
    if len(public) != len(public_rows):
        raise OracleOuterG0Error("public G0 keys are duplicated")
    loaded: list[LoadedG0] = []
    observed: set[tuple[str, str, str]] = set()
    for root, receipt in zip(
        source.roots, source.expected_manifest_sha256, strict=True
    ):
        item = _load_g0_root(
            root,
            receipt,
            repeat=source.repeat,
            outer_fold=source.outer_fold,
            expected_g0_source_sha256=expected_g0_source_sha256,
        )
        episode = cast(
            str, _object(item.manifest["episode"], "G0 episode")["episode_id"]
        )
        expected_episode = [
            (key, row) for key, row in public.items() if key[0] == episode
        ]
        if len(expected_episode) != len(item.rows):
            raise OracleOuterG0Error("G0 public population differs")
        for row, (key, public_row) in zip(item.rows, expected_episode, strict=True):
            if (
                row["molecule_id"] != key[1]
                or row["component_id"] != public_row["component_id"]
                or key in observed
            ):
                raise OracleOuterG0Error("G0 public population differs")
            observed.add(key)
        loaded.append(item)
    if observed != set(public):
        raise OracleOuterG0Error("G0 public population differs")
    return tuple(loaded)


def _load_g0_root(
    root: Path,
    expected_manifest_sha256: str,
    *,
    repeat: int,
    outer_fold: int,
    expected_g0_source_sha256: str,
) -> LoadedG0:
    _digest(expected_manifest_sha256, "G0 manifest")
    try:
        data = read_exact_root(root, ("manifest.json", "prediction_fragment.csv"))
    except OraclePrivateIOError as exc:
        raise OracleOuterG0Error(str(exc)) from exc
    manifest_data = data["manifest.json"]
    fragment = data["prediction_fragment.csv"]
    if sha256(manifest_data).hexdigest() != expected_manifest_sha256:
        raise OracleOuterG0Error("G0 manifest receipt differs")
    manifest = _canonical_object(manifest_data, "G0 manifest")
    _validate_g0_manifest(
        manifest,
        repeat=repeat,
        outer_fold=outer_fold,
        expected_g0_source_sha256=expected_g0_source_sha256,
        fragment=fragment,
    )
    rows = tuple(_csv_rows(fragment, G0_COLUMNS, "G0 fragment"))
    for row in rows:
        if (
            row["endpoint"] != "CYP3A4"
            or row["repeat"] != str(repeat)
            or row["outer_fold"] != str(outer_fold)
            or row["inner_fold"] != ""
            or row["scope"] != "openadmet-oracle-outer-v1"
            or row["system_id"] != "TRACE-G0-MAPL-FIXED"
            or row["feature_spec_id"] != "maplight-fixed-stage-a-v1"
        ):
            raise OracleOuterG0Error("G0 fragment binding differs")
        if not row["molecule_id"]:
            raise OracleOuterG0Error("G0 molecule identity differs")
        for name in ("component_id", "model_id", "split_id"):
            _digest(row[name], f"G0 {name}")
        for name in ("prediction", "applicability_score"):
            value = _finite(row[name], f"G0 {name}")
            if format(value, ".17g") != row[name]:
                raise OracleOuterG0Error(f"G0 {name} serialization differs")
    return LoadedG0(
        expected_manifest_sha256,
        manifest,
        rows,
        sha256(fragment).hexdigest(),
    )


def _validate_g0_manifest(
    manifest: Mapping[str, Any],
    *,
    repeat: int,
    outer_fold: int,
    expected_g0_source_sha256: str,
    fragment: bytes,
) -> None:
    expected_fields = {
        "schema_version",
        "status",
        "contract_sha256",
        "parent_contract_sha256",
        "runner_source_sha256",
        "g0_source_bundle_sha256",
        "g0_source_file_receipts",
        "model_public_manifest_sha256",
        "episode_target_manifest_sha256",
        "trusted_episode_parent_receipts",
        "source_bundle_binding",
        "scope",
        "episode",
        "system_id",
        "source_system_id",
        "candidate_id",
        "cell_id",
        "public_query_receipt_sha256",
        "runtime",
        "r3c_parameter_source",
        "resolved_catboost_parameters",
        "counts",
        "operation_accounting",
        "prediction_fragment",
        "authority",
    }
    if (
        set(manifest) != expected_fields
        or manifest.get("schema_version")
        != "cypshift.openadmet_cyp_2026.r5c_g0_prediction_fragment.v1"
        or manifest.get("status") != "R5_ORACLE_G0_EPISODE_COMPLETE"
        or manifest.get("contract_sha256") != RESOLVED_CONTRACT_SHA256
        or manifest.get("parent_contract_sha256") != G0_PARENT_CONTRACT_SHA256
        or manifest.get("g0_source_bundle_sha256") != expected_g0_source_sha256
        or manifest.get("runtime") != G0_RUNTIME
        or manifest.get("system_id") != "G0"
        or manifest.get("source_system_id") != "TRACE-G0-MAPL-FIXED"
        or manifest.get("authority") != DENIED_AUTHORITY
    ):
        raise OracleOuterG0Error("G0 manifest binding differs")
    source_receipts = _object(manifest.get("g0_source_file_receipts"), "G0 sources")
    actual_receipts = {
        name: sha256(read_stable_file(ROOT / name)).hexdigest()
        for name in G0_SOURCE_FILES
    }
    if (
        source_receipts != actual_receipts
        or manifest.get("runner_source_sha256") != actual_receipts[G0_SOURCE_FILES[1]]
    ):
        raise OracleOuterG0Error("G0 source receipts differ")
    for name in (
        "model_public_manifest_sha256",
        "episode_target_manifest_sha256",
        "public_query_receipt_sha256",
    ):
        _digest(manifest.get(name), f"G0 {name}")
    trusted = _object(manifest.get("trusted_episode_parent_receipts"), "G0 parents")
    if set(trusted) != {
        "episode_view_builder_source_sha256",
        "source_cell_target_manifest_sha256",
    }:
        raise OracleOuterG0Error("G0 trusted parents differ")
    for value in trusted.values():
        _digest(value, "G0 trusted parent")
    _validate_source_binding(
        _object(manifest.get("source_bundle_binding"), "G0 source binding")
    )
    scope = _object(manifest.get("scope"), "G0 scope")
    if scope != {
        "stage": "outer",
        "repeat": repeat,
        "current_outer_validation_fold": outer_fold,
        "inner_fold": "",
        "episode_outer_fold": outer_fold,
    }:
        raise OracleOuterG0Error("G0 scope differs")
    episode = _object(manifest.get("episode"), "G0 episode")
    episode_id = episode.get("episode_id")
    _digest(episode_id, "G0 episode")
    candidate = candidate_id("G0", None, None)
    expected_cell = cell_id(
        "outer", repeat, outer_fold, None, "G0", candidate, cast(str, episode_id)
    )
    if (
        manifest.get("candidate_id") != candidate
        or manifest.get("cell_id") != expected_cell
    ):
        raise OracleOuterG0Error("G0 identity differs")
    counts = _object(manifest.get("counts"), "G0 counts")
    if set(counts) != {
        "current_training_points",
        "anchor_rows",
        "fit_rows",
        "query_rows",
    } or any(type(value) is not int or value < 0 for value in counts.values()):
        raise OracleOuterG0Error("G0 counts differ")
    if (
        counts["anchor_rows"] not in {0, 1}
        or counts["fit_rows"]
        != counts["current_training_points"] + counts["anchor_rows"]
        or counts["query_rows"] != fragment.count(b"\n") - 1
    ):
        raise OracleOuterG0Error("G0 counts differ")
    accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    accounting["direct_target_values_parsed"] = counts["fit_rows"]
    accounting["anchor_labels_exposed_to_models"] = counts["anchor_rows"]
    accounting["maplight_model_fits"] = 1
    if manifest.get("operation_accounting") != accounting:
        raise OracleOuterG0Error("G0 accounting differs")
    receipt = _object(manifest.get("prediction_fragment"), "G0 fragment receipt")
    if receipt != {
        "sha256": sha256(fragment).hexdigest(),
        "bytes": len(fragment),
        "rows": counts["query_rows"],
        "columns": list(G0_COLUMNS),
    }:
        raise OracleOuterG0Error("G0 fragment receipt differs")
    _validate_g0_parameters(manifest)


def _validate_g0_parameters(manifest: Mapping[str, Any]) -> None:
    source = _object(manifest.get("r3c_parameter_source"), "G0 parameters")
    if set(source) != {
        "r3c_terminal_manifest_sha256",
        "parameter_record_sha256",
        "parameter_record",
    }:
        raise OracleOuterG0Error("G0 parameter source differs")
    _digest(source["r3c_terminal_manifest_sha256"], "G0 terminal")
    record = _object(source.get("parameter_record"), "G0 parameter record")
    if (
        source.get("parameter_record_sha256") != G0_PARAMETER_RECORD_SHA256
        or set(record)
        != {
            "canonical_get_all_params_json",
            "canonical_get_all_params_sha256",
            "system_id",
        }
        or record.get("canonical_get_all_params_sha256") != G0_PARAMETER_SHA256
        or record.get("system_id") != "TRACE-G0-MAPL-FIXED"
        or manifest.get("resolved_catboost_parameters")
        != record.get("canonical_get_all_params_json")
        or sha256(_pretty_json(record)).hexdigest() != G0_PARAMETER_RECORD_SHA256
        or sha256(_pretty_json(record["canonical_get_all_params_json"])).hexdigest()
        != G0_PARAMETER_SHA256
    ):
        raise OracleOuterG0Error("G0 parameter source differs")


def _validate_source_binding(binding: Mapping[str, Any]) -> None:
    if (
        set(binding)
        != {
            "manifest_receipt",
            "schema_version",
            "contract_sha256",
            "parent_receipts",
            "input_receipts",
            "source_receipts",
        }
        or binding.get("schema_version")
        != "cypshift.openadmet_cyp_2026.oracle_source_bundle.v1"
        or binding.get("contract_sha256") != G0_PARENT_CONTRACT_SHA256
    ):
        raise OracleOuterG0Error("source binding fields differ")
    manifest = _object(binding.get("manifest_receipt"), "source manifest")
    if set(manifest) != {"sha256", "bytes"}:
        raise OracleOuterG0Error("source manifest receipt differs")
    _digest(manifest.get("sha256"), "source manifest")
    if type(manifest.get("bytes")) is not int or manifest["bytes"] < 0:
        raise OracleOuterG0Error("source manifest receipt differs")
    parents = _object(binding.get("parent_receipts"), "source parents")
    inputs = _object(binding.get("input_receipts"), "source inputs")
    sources = _object(binding.get("source_receipts"), "source receipts")
    if (
        set(parents) != set(SOURCE_PARENT_FILES)
        or set(inputs) != set(parents)
        or inputs != sources
    ):
        raise OracleOuterG0Error("source binding receipts differ")
    for name in SOURCE_PARENT_FILES:
        _digest(parents[name], f"source parent: {name}")
        record = _object(inputs[name], f"source input: {name}")
        if (
            set(record) != {"sha256", "bytes"}
            or record.get("sha256") != parents[name]
            or type(record.get("bytes")) is not int
            or record["bytes"] < 0
        ):
            raise OracleOuterG0Error("source input receipt differs")


def _csv_rows(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    if not data.endswith(b"\n") or b"\r" in data:
        raise OracleOuterG0Error(f"{label} line endings differ")
    try:
        reader = csv.reader(io.StringIO(data.decode(), newline=""), strict=True)
        if next(reader, None) != list(columns):
            raise OracleOuterG0Error(f"{label} columns differ")
        return [dict(zip(columns, values, strict=True)) for values in reader]
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        raise OracleOuterG0Error(f"{label} is invalid") from exc


def _canonical_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = strict_json_object(data, label)
    except ValueError as exc:
        raise OracleOuterG0Error(str(exc)) from exc
    if data != _pretty_json(value):
        raise OracleOuterG0Error(f"{label} is not canonical")
    return value


def _pretty_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode()


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OracleOuterG0Error(f"{label} is not an object")
    return dict(cast(Mapping[str, Any], value))


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise OracleOuterG0Error(f"{label} is not SHA-256")
    return value


def _finite(value: str, label: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise OracleOuterG0Error(f"{label} is not finite") from exc
    if not math.isfinite(result):
        raise OracleOuterG0Error(f"{label} is not finite")
    return result


__all__ = [
    "G0_SOURCE_FILES",
    "G0Input",
    "LoadedG0",
    "OracleOuterG0Error",
    "load_g0_roots",
]

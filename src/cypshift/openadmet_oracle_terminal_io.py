"""Authenticated private inputs for R5C outer scoring and terminal publication."""

from __future__ import annotations

import csv
import importlib.metadata
import io
import json
import math
import os
import platform
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

from cypshift.openadmet_oracle_freezer_io import FREEZER_SOURCE_FILES, SYSTEMS
from cypshift.openadmet_oracle_freezer_publish import (
    EXPECTED_FILES as FREEZE_FILES,
)
from cypshift.openadmet_oracle_freezer_publish import (
    _validate_payloads as _validate_freeze,
)
from cypshift.openadmet_oracle_inner import (
    EXPECTED_SELECTION_ROWS,
    EXPECTED_TOKENS,
    SELECTION_COLUMNS,
    SELECTION_SCHEMA_VERSION,
)
from cypshift.openadmet_oracle_inner_io import (
    EXPECTED_RUNTIME,
    LEARNED_SYSTEMS,
    candidate_runner_source_bundle_sha256,
    scorer_source_bundle_sha256,
)
from cypshift.openadmet_oracle_pair_cell import FRAGMENT_COLUMNS
from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS
from cypshift.openadmet_oracle_private_io import (
    OraclePrivateIOError,
    open_directory_no_symlinks,
    read_exact_root,
    read_stable_file,
)
from cypshift.openadmet_oracle_projection import DENIED_AUTHORITY
from cypshift.openadmet_oracle_scoring import EXPECTED_GRIDS, InnerCandidate
from cypshift.openadmet_oracle_sealed import (
    RESOLVED_CONTRACT_SHA256,
    SealedScorerCapability,
    load_v3_sealed_scorer,
)
from cypshift.openadmet_oracle_terminal_receipts import (
    ACCOUNTING_SCHEMA,
    ACCOUNTING_STATUS,
    SUPPORT_AUTHORITY,
    SUPPORT_SCHEMA,
    SUPPORT_STATUS,
    ChildManifestInput,
    load_child_manifest_accounting,
    receipt_source_bundle_sha256,
)
from cypshift.openadmet_transformation_io import strict_json_object

ROOT: Final = Path(__file__).resolve().parents[2]
CONTRACT_RECEIPTS: Final = {
    "benchmarks/openadmet_cyp_2026/oracle_experiment_contract_v1.json": (
        "c1d7a66c4f479339b30c2006e4250381cb213d665d4902c71d4c4edbd347e8bf"
    ),
    "benchmarks/openadmet_cyp_2026/oracle_experiment_contract_v2.json": (
        "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
    ),
    "benchmarks/openadmet_cyp_2026/oracle_experiment_contract_v3.json": (
        "275f1425d1a93805cb7d5b7dc1b63c67d6f02476eab9f77798cac6cc625a3d55"
    ),
}
TERMINAL_SOURCE_FILES: Final = tuple(
    sorted(
        {
            *FREEZER_SOURCE_FILES,
            "src/cypshift/openadmet_oracle_outer.py",
            "src/cypshift/openadmet_oracle_g0_view.py",
            "src/cypshift/openadmet_oracle_inner.py",
            "src/cypshift/openadmet_oracle_runner.py",
            "src/cypshift/openadmet_oracle_runner_commands.py",
            "src/cypshift/openadmet_oracle_runner_cleanup.py",
            "src/cypshift/openadmet_oracle_runner_full.py",
            "src/cypshift/openadmet_oracle_scoring.py",
            "src/cypshift/openadmet_oracle_source.py",
            "src/cypshift/openadmet_oracle_source_io.py",
            "src/cypshift/openadmet_oracle_support.py",
            "src/cypshift/openadmet_oracle_statistics.py",
            "src/cypshift/openadmet_oracle_terminal.py",
            "src/cypshift/openadmet_oracle_terminal_cleanup.py",
            "src/cypshift/openadmet_oracle_terminal_io.py",
            "src/cypshift/openadmet_oracle_terminal_receipts.py",
            "src/cypshift/openadmet_oracle_terminal_validation.py",
            "src/cypshift/openadmet_oracle_worker.py",
            "scripts/run_openadmet_r5c.py",
        }
    )
)
FAILURE_SOURCE_FILES: Final = (
    "scripts/run_openadmet_r5c.py",
    "src/cypshift/openadmet_oracle_pair_cell_io.py",
    "src/cypshift/openadmet_oracle_private_io.py",
    "src/cypshift/openadmet_oracle_projection.py",
    "src/cypshift/openadmet_oracle_runner.py",
    "src/cypshift/openadmet_oracle_runner_cleanup.py",
    "src/cypshift/openadmet_oracle_sealed.py",
    "src/cypshift/openadmet_oracle_terminal.py",
    "src/cypshift/openadmet_oracle_terminal_cleanup.py",
    "src/cypshift/openadmet_oracle_terminal_io.py",
    "src/cypshift/openadmet_oracle_worker.py",
    "src/cypshift/openadmet_transformation_io.py",
)


class OracleTerminalIOError(ValueError):
    """A private scorer input, source, runtime, or receipt differs."""


@dataclass(frozen=True, slots=True)
class FreezeInput:
    root: Path
    expected_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class InnerSelectionInput:
    root: Path
    expected_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class SealedOuterInput:
    repeat: int
    outer_fold: int
    root: Path
    expected_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class SupportInput:
    root: Path
    expected_sha256: str


@dataclass(frozen=True, slots=True)
class AggregateAccountingInput:
    root: Path
    expected_sha256: str
    expected_child_manifest_receipts: tuple[tuple[str, str], ...]
    child_manifests: tuple[ChildManifestInput, ...]


@dataclass(frozen=True, slots=True)
class LoadedFreeze:
    manifest_sha256: str
    manifest: Mapping[str, Any]
    predictions: Mapping[str, tuple[Mapping[str, str], ...]]
    eligibility: tuple[Mapping[str, str], ...]


@dataclass(frozen=True, slots=True)
class LoadedInnerSelection:
    manifest_sha256: str
    manifest: Mapping[str, Any]
    rows: tuple[Mapping[str, str], ...]
    data: bytes


@dataclass(frozen=True, slots=True)
class LoadedSupport:
    sha256: str
    status: str
    support: Mapping[str, Any]
    criteria: Mapping[str, bool]


@dataclass(frozen=True, slots=True)
class LoadedAggregateAccounting:
    sha256: str
    child_manifest_receipts: tuple[tuple[str, str], ...]
    operation_accounting: Mapping[str, int]


def terminal_source_bundle_sha256() -> str:
    receipts = {
        name: sha256(read_stable_file(ROOT / name)).hexdigest()
        for name in TERMINAL_SOURCE_FILES
    }
    material = "".join(f"{name}|{receipts[name]}\n" for name in sorted(receipts))
    return sha256(material.encode()).hexdigest()


def failure_source_bundle_sha256() -> str:
    receipts = {
        name: sha256(read_stable_file(ROOT / name)).hexdigest()
        for name in FAILURE_SOURCE_FILES
    }
    material = "".join(f"{name}|{receipts[name]}\n" for name in sorted(receipts))
    return sha256(material.encode()).hexdigest()


def validate_failure_execution(
    expected_source_sha256: str,
) -> tuple[str, Mapping[str, str]]:
    _digest(expected_source_sha256, "failure publisher source")
    observed = failure_source_bundle_sha256()
    if observed != expected_source_sha256:
        raise OracleTerminalIOError("failure publisher source bundle differs")
    runtime = {
        "platform": f"{platform.system()} {platform.machine()} CPU",
        "python_version": platform.python_version(),
        "numpy_version": importlib.metadata.version("numpy"),
        "sklearn_version": importlib.metadata.version("scikit-learn"),
        "rdkit_version": importlib.metadata.version("rdkit"),
        "uv_lock_sha256": sha256(read_stable_file(ROOT / "uv.lock")).hexdigest(),
    }
    if runtime != EXPECTED_RUNTIME:
        raise OracleTerminalIOError("failure publisher runtime differs")
    return observed, runtime


def validate_execution(expected_source_sha256: str) -> tuple[str, Mapping[str, str]]:
    _digest(expected_source_sha256, "terminal source")
    if any(
        sha256(read_stable_file(ROOT / name)).hexdigest() != expected
        for name, expected in CONTRACT_RECEIPTS.items()
    ):
        raise OracleTerminalIOError("oracle contract receipt differs")
    observed = terminal_source_bundle_sha256()
    if observed != expected_source_sha256:
        raise OracleTerminalIOError("terminal source bundle differs")
    runtime = {
        "platform": f"{platform.system()} {platform.machine()} CPU",
        "python_version": platform.python_version(),
        "numpy_version": importlib.metadata.version("numpy"),
        "sklearn_version": importlib.metadata.version("scikit-learn"),
        "rdkit_version": importlib.metadata.version("rdkit"),
        "uv_lock_sha256": sha256(read_stable_file(ROOT / "uv.lock")).hexdigest(),
    }
    if runtime != EXPECTED_RUNTIME:
        raise OracleTerminalIOError("terminal runtime differs")
    return observed, runtime


def load_freeze(source: FreezeInput) -> LoadedFreeze:
    _digest(source.expected_manifest_sha256, "freeze manifest")
    try:
        payloads = read_exact_root(source.root, tuple(sorted(FREEZE_FILES)))
        _validate_freeze(payloads)
    except (OraclePrivateIOError, ValueError) as exc:
        raise OracleTerminalIOError(str(exc)) from exc
    manifest_data = payloads["manifest.json"]
    if sha256(manifest_data).hexdigest() != source.expected_manifest_sha256:
        raise OracleTerminalIOError("freeze manifest receipt differs")
    manifest = _canonical_object(manifest_data, "freeze manifest")
    predictions = {
        system: tuple(
            _csv_rows(payloads[f"{system}.csv"], FRAGMENT_COLUMNS, f"freeze {system}")
        )
        for system in SYSTEMS
    }
    from cypshift.openadmet_oracle_sealed import ELIGIBILITY_COLUMNS

    eligibility = tuple(
        _csv_rows(
            payloads["merged_eligibility.csv"],
            ELIGIBILITY_COLUMNS,
            "freeze eligibility",
        )
    )
    return LoadedFreeze(
        source.expected_manifest_sha256, manifest, predictions, eligibility
    )


def load_inner_selection(source: InnerSelectionInput) -> LoadedInnerSelection:
    _digest(source.expected_manifest_sha256, "inner selection manifest")
    root_fd = open_directory_no_symlinks(source.root)
    try:
        if os.fstat(root_fd).st_mode & 0o222:
            raise OracleTerminalIOError("inner selection root is writable")
        payloads = _walk_payloads(root_fd)
        manifest_data = payloads["manifest.json"]
        selection_data = payloads["oracle_inner_selection.csv"]
    except OraclePrivateIOError as exc:
        raise OracleTerminalIOError(str(exc)) from exc
    finally:
        os.close(root_fd)
    if sha256(manifest_data).hexdigest() != source.expected_manifest_sha256:
        raise OracleTerminalIOError("inner selection manifest receipt differs")
    manifest = _canonical_object(manifest_data, "inner selection manifest")
    _validate_inner_manifest(manifest, payloads, selection_data)
    rows = tuple(_csv_rows(selection_data, SELECTION_COLUMNS, "inner selection"))
    _validate_selection_rows(rows)
    return LoadedInnerSelection(
        source.expected_manifest_sha256, manifest, rows, selection_data
    )


def load_sealed_outer(
    inputs: Sequence[SealedOuterInput],
) -> tuple[SealedScorerCapability, ...]:
    if len(inputs) != 15:
        raise OracleTerminalIOError("outer sealed cardinality differs")
    index: dict[tuple[int, int], SealedOuterInput] = {}
    for item in inputs:
        key = item.repeat, item.outer_fold
        if (
            item.repeat not in range(3)
            or item.outer_fold not in range(5)
            or key in index
        ):
            raise OracleTerminalIOError("outer sealed scope differs")
        index[key] = item
    expected = {(repeat, outer) for repeat in range(3) for outer in range(5)}
    if set(index) != expected:
        raise OracleTerminalIOError("outer sealed grid differs")
    result: list[SealedScorerCapability] = []
    for repeat, outer in sorted(index):
        item = index[(repeat, outer)]
        try:
            loaded = load_v3_sealed_scorer(
                item.root,
                expected_manifest_sha256=item.expected_manifest_sha256,
                expected_scope=("outer", repeat, outer, None),
            )
        except ValueError as exc:
            raise OracleTerminalIOError(str(exc)) from exc
        result.append(loaded)
    return tuple(result)


def load_support(source: SupportInput) -> LoadedSupport:
    _digest(source.expected_sha256, "support receipt")
    try:
        data = read_exact_root(source.root, ("support.json",))["support.json"]
    except OraclePrivateIOError as exc:
        raise OracleTerminalIOError(str(exc)) from exc
    if sha256(data).hexdigest() != source.expected_sha256:
        raise OracleTerminalIOError("support receipt differs")
    record = _canonical_object(data, "prefit support")
    fields = {
        "schema_version",
        "contract_sha256",
        "status",
        "support_status",
        "support",
        "criteria",
        "parent_receipts",
        "source_sha256",
        "runtime",
        "operation_accounting",
        "authority",
    }
    status = record.get("support_status")
    if (
        set(record) != fields
        or record.get("schema_version") != SUPPORT_SCHEMA
        or record.get("contract_sha256") != RESOLVED_CONTRACT_SHA256
        or record.get("status") != SUPPORT_STATUS
        or status not in {"SUPPORTED", "UNDERPOWERED"}
        or record.get("source_sha256") != receipt_source_bundle_sha256()
        or record.get("runtime") != EXPECTED_RUNTIME
        or record.get("operation_accounting") != dict.fromkeys(ACCOUNTING_FIELDS, 0)
        or record.get("authority") != SUPPORT_AUTHORITY
    ):
        raise OracleTerminalIOError("support binding differs")
    parents = _object(record.get("parent_receipts"), "support parents")
    if set(parents) != {"support_evidence_manifest_sha256"}:
        raise OracleTerminalIOError("support parent differs")
    _digest(parents["support_evidence_manifest_sha256"], "support evidence parent")
    support = _object(record.get("support"), "support facts")
    criteria_raw = _object(record.get("criteria"), "support criteria")
    _validate_support_facts(support, criteria_raw, cast(str, status))
    return LoadedSupport(
        source.expected_sha256,
        cast(str, status),
        support,
        cast(Mapping[str, bool], criteria_raw),
    )


def load_aggregate_accounting(
    source: AggregateAccountingInput,
) -> LoadedAggregateAccounting:
    _digest(source.expected_sha256, "aggregate accounting receipt")
    expected_children = source.expected_child_manifest_receipts
    if (
        tuple(
            (item.label, item.expected_manifest_sha256)
            for item in source.child_manifests
        )
        != expected_children
    ):
        raise OracleTerminalIOError("accounting child capabilities differ")
    if (
        not expected_children
        or len(expected_children) != len(set(expected_children))
        or tuple(sorted(expected_children)) != expected_children
    ):
        raise OracleTerminalIOError("expected accounting child order differs")
    for label, digest in expected_children:
        if not label or "/" in label or "\\" in label:
            raise OracleTerminalIOError("accounting child label differs")
        _digest(digest, "accounting child receipt")
    try:
        data = read_exact_root(source.root, ("accounting.json",))["accounting.json"]
    except OraclePrivateIOError as exc:
        raise OracleTerminalIOError(str(exc)) from exc
    if sha256(data).hexdigest() != source.expected_sha256:
        raise OracleTerminalIOError("aggregate accounting receipt differs")
    record = _canonical_object(data, "aggregate accounting")
    fields = {
        "schema_version",
        "contract_sha256",
        "status",
        "children",
        "source_sha256",
        "runtime",
        "operation_accounting",
        "authority",
    }
    children = record.get("children")
    if (
        set(record) != fields
        or record.get("schema_version") != ACCOUNTING_SCHEMA
        or record.get("contract_sha256") != RESOLVED_CONTRACT_SHA256
        or record.get("status") != ACCOUNTING_STATUS
        or record.get("source_sha256") != receipt_source_bundle_sha256()
        or record.get("runtime") != EXPECTED_RUNTIME
        or record.get("authority") != DENIED_AUTHORITY
    ):
        raise OracleTerminalIOError("aggregate accounting binding differs")
    if not isinstance(children, list) or len(children) != len(expected_children):
        raise OracleTerminalIOError("aggregate accounting children differ")
    total = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    for child, expected, capability in zip(
        children, expected_children, source.child_manifests, strict=True
    ):
        item = _object(child, "aggregate accounting child")
        if (
            set(item) != {"label", "sha256", "operation_accounting"}
            or (
                item.get("label"),
                item.get("sha256"),
            )
            != expected
        ):
            raise OracleTerminalIOError("aggregate accounting child differs")
        delta = _accounting(item.get("operation_accounting"))
        try:
            observed_delta = load_child_manifest_accounting(capability)
        except ValueError as exc:
            raise OracleTerminalIOError(str(exc)) from exc
        if delta != observed_delta:
            raise OracleTerminalIOError("aggregate accounting child delta differs")
        for name in ACCOUNTING_FIELDS:
            total[name] += delta[name]
    accounting = _accounting(record.get("operation_accounting"))
    if accounting != total:
        raise OracleTerminalIOError("aggregate accounting arithmetic differs")
    if accounting["predictions_frozen"] <= 0:
        raise OracleTerminalIOError("aggregate accounting lacks frozen predictions")
    return LoadedAggregateAccounting(
        source.expected_sha256,
        expected_children,
        accounting,
    )


def _validate_support_facts(
    support: Mapping[str, Any], criteria: Mapping[str, Any], status: str
) -> None:
    expected_support = {
        "unique_primary_components",
        "unique_primary_episode_query_pairs",
        "outer_cell_support",
        "outer_training_support",
        "inner_training_support",
        "control_local_support",
    }
    expected_criteria = {
        "unique_primary_components_min_50",
        "unique_primary_episode_query_pairs_min_100",
        "all_outer_cells_min_5_components_10_rows",
        "all_outer_training_min_50_families_200_pairs",
        "all_inner_training_min_40_families_150_pairs",
        "F0_min_30_families_50_rows",
        "F1_min_30_families_50_rows",
    }
    if set(support) != expected_support or set(criteria) != expected_criteria:
        raise OracleTerminalIOError("support fact schema differs")
    for name in (
        "unique_primary_components",
        "unique_primary_episode_query_pairs",
    ):
        if type(support[name]) is not int or support[name] < 0:
            raise OracleTerminalIOError("support count differs")
    outer_keys = {
        f"repeat-{repeat}/outer-{outer}" for repeat in range(3) for outer in range(5)
    }
    inner_keys = {
        f"repeat-{repeat}/outer-{outer}/inner-{inner}"
        for repeat in range(3)
        for outer in range(5)
        for inner in range(4)
    }
    outer_cells = _support_cells(support["outer_cell_support"], outer_keys)
    outer_training = _support_cells(support["outer_training_support"], outer_keys)
    inner_training = _support_cells(support["inner_training_support"], inner_keys)
    controls = _object(support["control_local_support"], "control local support")
    if set(controls) != {"F0", "F1"}:
        raise OracleTerminalIOError("control support differs")
    control_counts = {
        name: _support_count_record(value) for name, value in controls.items()
    }
    if any(type(value) is not bool for value in criteria.values()):
        raise OracleTerminalIOError("support criteria type differs")
    expected_values = {
        "unique_primary_components_min_50": support["unique_primary_components"] >= 50,
        "unique_primary_episode_query_pairs_min_100": support[
            "unique_primary_episode_query_pairs"
        ]
        >= 100,
        "all_outer_cells_min_5_components_10_rows": all(
            item["families"] >= 5 and item["rows_or_pairs"] >= 10
            for item in outer_cells.values()
        ),
        "all_outer_training_min_50_families_200_pairs": all(
            item["families"] >= 50 and item["rows_or_pairs"] >= 200
            for item in outer_training.values()
        ),
        "all_inner_training_min_40_families_150_pairs": all(
            item["families"] >= 40 and item["rows_or_pairs"] >= 150
            for item in inner_training.values()
        ),
        "F0_min_30_families_50_rows": control_counts["F0"]["families"] >= 30
        and control_counts["F0"]["rows_or_pairs"] >= 50,
        "F1_min_30_families_50_rows": control_counts["F1"]["families"] >= 30
        and control_counts["F1"]["rows_or_pairs"] >= 50,
    }
    if dict(criteria) != expected_values:
        raise OracleTerminalIOError("support criteria arithmetic differs")
    expected_status = "SUPPORTED" if all(criteria.values()) else "UNDERPOWERED"
    if status != expected_status:
        raise OracleTerminalIOError("support status differs")


def _support_cells(value: Any, expected: set[str]) -> dict[str, dict[str, int]]:
    cells = _object(value, "support cells")
    if set(cells) != expected:
        raise OracleTerminalIOError("support cell cardinality differs")
    result: dict[str, dict[str, int]] = {}
    for key, record in cells.items():
        if not key or not isinstance(key, str):
            raise OracleTerminalIOError("support cell key differs")
        result[key] = _support_count_record(record)
    return result


def _support_count_record(value: Any) -> dict[str, int]:
    record = _object(value, "support count record")
    if set(record) != {"families", "rows_or_pairs"} or any(
        type(count) is not int or count < 0 for count in record.values()
    ):
        raise OracleTerminalIOError("support count record differs")
    return cast(dict[str, int], record)


def _accounting(value: Any) -> dict[str, int]:
    result = _object(value, "aggregate accounting counts")
    if (
        set(result) != set(ACCOUNTING_FIELDS)
        or any(type(item) is not int or item < 0 for item in result.values())
        or any(result[name] for name in ACCOUNTING_FIELDS[8:])
    ):
        raise OracleTerminalIOError("aggregate accounting counts differ")
    return cast(dict[str, int], result)


def _validate_inner_manifest(
    manifest: Mapping[str, Any], payloads: Mapping[str, bytes], selection: bytes
) -> None:
    fields = {
        "schema_version",
        "status",
        "contract_sha256",
        "scope",
        "counts",
        "input_receipts",
        "output_receipts",
        "token_receipts",
        "scorer_source_sha256",
        "candidate_source_sha256",
        "runtime",
        "operation_accounting",
        "authority",
    }
    if (
        set(manifest) != fields
        or manifest.get("schema_version") != SELECTION_SCHEMA_VERSION
        or manifest.get("status") != "R5_ORACLE_INNER_SELECTION_COMPLETE"
        or manifest.get("contract_sha256") != RESOLVED_CONTRACT_SHA256
        or manifest.get("scope")
        != {"stage": "inner", "repeats": 3, "outer_folds": 5, "inner_folds": 4}
        or manifest.get("counts")
        != {
            "candidate_fragments": 960,
            "merged_candidate_fragments": EXPECTED_SELECTION_ROWS,
            "sealed_roots": 60,
            "selection_rows": EXPECTED_SELECTION_ROWS,
            "selection_tokens": EXPECTED_TOKENS,
        }
        or manifest.get("scorer_source_sha256") != scorer_source_bundle_sha256()
        or manifest.get("candidate_source_sha256")
        != candidate_runner_source_bundle_sha256()
        or manifest.get("runtime") != EXPECTED_RUNTIME
        or manifest.get("authority") != DENIED_AUTHORITY
    ):
        raise OracleTerminalIOError("inner selection manifest binding differs")
    outputs = _object(manifest.get("output_receipts"), "inner selection outputs")
    if set(payloads) != {"manifest.json", *outputs}:
        raise OracleTerminalIOError("inner selection file set differs")
    selection_receipt = _object(
        outputs.get("oracle_inner_selection.csv"), "inner selection receipt"
    )
    if selection_receipt != {
        "relative_path": "oracle_inner_selection.csv",
        "sha256": sha256(selection).hexdigest(),
        "bytes": len(selection),
        "rows": EXPECTED_SELECTION_ROWS,
        "columns": list(SELECTION_COLUMNS),
    }:
        raise OracleTerminalIOError("inner selection receipt differs")
    for name, value in outputs.items():
        record = _object(value, f"inner output: {name}")
        data = payloads[name]
        if (
            record.get("relative_path") != name
            or record.get("sha256") != sha256(data).hexdigest()
            or record.get("bytes") != len(data)
        ):
            raise OracleTerminalIOError("inner output path differs")
        _digest(record.get("sha256"), "inner output receipt")
        if type(record.get("bytes")) is not int or record["bytes"] < 1:
            raise OracleTerminalIOError("inner output receipt differs")
    tokens = _object(manifest.get("token_receipts"), "inner tokens")
    if len(tokens) != EXPECTED_TOKENS:
        raise OracleTerminalIOError("inner token receipts differ")
    for value in tokens.values():
        _digest(value, "inner token receipt")
    accounting = _object(manifest.get("operation_accounting"), "inner accounting")
    if (
        set(accounting) != set(ACCOUNTING_FIELDS)
        or any(type(value) is not int or value < 0 for value in accounting.values())
        or any(accounting[name] for name in ACCOUNTING_FIELDS[8:])
        or accounting["predictions_frozen"] != 0
    ):
        raise OracleTerminalIOError("inner accounting differs")


def _validate_selection_rows(rows: Sequence[Mapping[str, str]]) -> None:
    if len(rows) != EXPECTED_SELECTION_ROWS:
        raise OracleTerminalIOError("inner selection row count differs")
    records: list[InnerCandidate] = []
    observed_order: list[tuple[int, int, int, float, float]] = []
    system_order = {system: index for index, system in enumerate(LEARNED_SYSTEMS)}
    selected: set[tuple[str, int, int, str]] = set()
    for row in rows:
        system = row["system_id"]
        if system not in LEARNED_SYSTEMS:
            raise OracleTerminalIOError("inner selection system differs")
        repeat = _canonical_int(row["repeat"], "selection repeat")
        outer = _canonical_int(row["outer_fold"], "selection outer")
        alpha = _optional_float(row["alpha"], "selection alpha")
        lambda_value = _optional_float(row["lambda"], "selection lambda")
        scored_rows = _canonical_int(
            row["inner_scored_rows"], "selection scored rows", minimum=1
        )
        components = _canonical_int(
            row["inner_scored_components"], "selection components", minimum=1
        )
        metric = _finite(row["inner_component_macro_mae"], "selection metric")
        _digest(row["candidate_id"], "selection candidate")
        if (
            repeat not in range(3)
            or outer not in range(5)
            or (alpha, lambda_value) not in EXPECTED_GRIDS[system]
            or row["selected"] not in {"true", "false"}
        ):
            raise OracleTerminalIOError("inner selection row differs")
        records.append(
            InnerCandidate(
                system,
                repeat,
                outer,
                row["candidate_id"],
                alpha,
                lambda_value,
                metric,
                scored_rows,
                components,
            )
        )
        observed_order.append(
            (
                system_order[system],
                repeat,
                outer,
                float("-inf") if alpha is None else alpha,
                float("-inf") if lambda_value is None else lambda_value,
            )
        )
        if row["selected"] == "true":
            selected.add((system, repeat, outer, row["candidate_id"]))
    from cypshift.openadmet_oracle_scoring import select_inner_candidates

    expected_selected = {
        (item.system_id, item.repeat, item.outer_fold, item.candidate_id)
        for item in select_inner_candidates(records)
    }
    if observed_order != sorted(observed_order) or selected != expected_selected:
        raise OracleTerminalIOError("inner selection decision differs")


def _walk_payloads(root_fd: int, prefix: tuple[str, ...] = ()) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for name in sorted(os.listdir(root_fd)):
        if not name or "/" in name or name in {".", ".."}:
            raise OracleTerminalIOError("inner selection path differs")
        relative = "/".join((*prefix, name))
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        try:
            opened = os.open(name, flags, dir_fd=root_fd)
        except OSError as exc:
            raise OracleTerminalIOError("inner selection path cannot open") from exc
        try:
            info = os.fstat(opened)
            if info.st_mode & 0o222:
                raise OracleTerminalIOError("inner selection path is writable")
            if stat.S_ISREG(info.st_mode):
                result[relative] = _read_opened(opened, info, relative)
            elif stat.S_ISDIR(info.st_mode):
                result.update(_walk_payloads(opened, (*prefix, name)))
            else:
                raise OracleTerminalIOError("inner selection path type differs")
        finally:
            if opened >= 0:
                os.close(opened)
    return result


def _read_opened(fd: int, before: os.stat_result, label: str) -> bytes:
    chunks: list[bytes] = []
    while block := os.read(fd, 1024 * 1024):
        chunks.append(block)
    data = b"".join(chunks)
    after = os.fstat(fd)

    def identity(item: os.stat_result) -> tuple[int, int, int, int, int]:
        return (
            item.st_dev,
            item.st_ino,
            item.st_size,
            item.st_mtime_ns,
            item.st_ctime_ns,
        )

    if identity(before) != identity(after) or len(data) != before.st_size:
        raise OracleTerminalIOError(f"inner selection leaf changed: {label}")
    return data


def _csv_rows(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    if not data.endswith(b"\n") or b"\r" in data:
        raise OracleTerminalIOError(f"{label} line endings differ")
    try:
        reader = csv.reader(io.StringIO(data.decode(), newline=""), strict=True)
        if next(reader, None) != list(columns):
            raise OracleTerminalIOError(f"{label} columns differ")
        return [dict(zip(columns, values, strict=True)) for values in reader]
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        raise OracleTerminalIOError(f"{label} is invalid") from exc


def _canonical_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = strict_json_object(data, label)
    except ValueError as exc:
        raise OracleTerminalIOError(str(exc)) from exc
    if data != _compact_json(value):
        raise OracleTerminalIOError(f"{label} is not canonical")
    return cast(dict[str, Any], value)


def _compact_json(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OracleTerminalIOError(f"{label} is not an object")
    return dict(cast(Mapping[str, Any], value))


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise OracleTerminalIOError(f"{label} is not SHA-256")
    return value


def _canonical_int(value: str, label: str, *, minimum: int = 0) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise OracleTerminalIOError(f"{label} differs") from exc
    if str(result) != value or result < minimum:
        raise OracleTerminalIOError(f"{label} differs")
    return result


def _optional_float(value: str, label: str) -> float | None:
    return None if value == "" else _finite(value, label)


def _finite(value: str, label: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise OracleTerminalIOError(f"{label} is not finite") from exc
    if not math.isfinite(result) or format(result, ".17g") != value:
        raise OracleTerminalIOError(f"{label} is not canonical finite")
    return result


__all__ = [
    "ACCOUNTING_SCHEMA",
    "ACCOUNTING_STATUS",
    "AggregateAccountingInput",
    "FreezeInput",
    "FAILURE_SOURCE_FILES",
    "InnerSelectionInput",
    "LoadedFreeze",
    "LoadedInnerSelection",
    "LoadedAggregateAccounting",
    "LoadedSupport",
    "OracleTerminalIOError",
    "SealedOuterInput",
    "SUPPORT_AUTHORITY",
    "SUPPORT_SCHEMA",
    "SUPPORT_STATUS",
    "SupportInput",
    "TERMINAL_SOURCE_FILES",
    "load_freeze",
    "load_inner_selection",
    "load_aggregate_accounting",
    "load_support",
    "load_sealed_outer",
    "failure_source_bundle_sha256",
    "terminal_source_bundle_sha256",
    "validate_failure_execution",
    "validate_execution",
]

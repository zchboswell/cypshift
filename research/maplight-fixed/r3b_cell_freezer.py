#!/usr/bin/env python3
from __future__ import annotations

import math
import re
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

_io = sys.modules["r3b_cell_io"]
FRAGMENT_COLUMNS = _io.FRAGMENT_COLUMNS
ENDPOINTS = _io.ENDPOINTS
FEATURE_SPECS = _io.FEATURE_SPECS
INHERITED_AUTHORITY = _io.INHERITED_AUTHORITY
MAPLIGHT = _io.MAPLIGHT
OUTER_SCOPE = _io.OUTER_SCOPE
OUTER_SYSTEMS = _io.OUTER_SYSTEMS
R3BError = _io.R3BError
V3 = _io.V3
V4 = _io.V4
V5 = _io.V5
GROUP_FOLDS_SHA256 = cast(str, _io.GROUP_FOLDS_SHA256)
_cell_id = _io._cell_id
_canonical_float = _io._canonical_float
_contract_receipts = _io._contract_receipts
_csv_bytes = _io._csv_bytes
_json_bytes = _io._json_bytes
_is_sha = _io._is_sha
_load_public = _io._load_public
_fold_index = _io._fold_index
_model_id = _io._model_id
_promote_noreplace = _io._promote_noreplace
_parse_int = _io._parse_int
_read_json = _io._read_json
_read_csv_bytes = _io._read_csv_bytes
_require_readonly_root = _io._require_readonly_root
_readonly_tree = _io._readonly_tree
_fsync_tree = _io._fsync_tree
_fsync_parent = _io._fsync_parent
_cleanup_tree = _io._cleanup_tree
_require = _io._require
_require_exact_mapping = _io._require_exact_mapping
_rooted_path = _io._rooted_path
_safe_rel = _io._safe_rel
_sha256 = _io._sha256
_sha256_bytes = _io._sha256_bytes
_split_id = _io._split_id
_validate_preflight = _io._validate_preflight
_TARGET_RECEIPT_FIELDS = _io.TARGET_RECEIPT_FIELDS
_CELL_RECEIPT_FIELDS = frozenset(
    "schema_version contract_sha256 stage cell_id runner_source_sha256 "
    "preflight_receipt_sha256 model_public_manifest_sha256 target_receipt "
    "feature_receipts inner_selection_token_sha256 system_ids "
    "resolved_catboost_parameters prediction_fragment counts accounting "
    "authority".split()
)
_CELL_ACCOUNTING = {
    "target_files_opened": 1,
    **dict.fromkeys(
        "truth_files_opened private_audit_files_opened other_target_files_opened "
        "feature_arrays_opened score_files_opened tdi_files_opened "
        "blinded_test_files_opened episode_or_anchor_files_opened "
        "submission_files_opened transductive_operations".split(),
        0,
    ),
}
_FREEZER_ACCOUNTING = {
    "cell_fragments_opened": 0,
    **dict.fromkeys(
        "target_files_opened truth_files_opened private_audit_files_opened "
        "score_files_opened tdi_files_opened blinded_test_files_opened "
        "episode_or_anchor_files_opened submission_files_opened "
        "transductive_operations".split(),
        0,
    ),
}
_PARAM_FIELDS = frozenset(
    "system_id canonical_get_all_params_json canonical_get_all_params_sha256".split()
)
_COUNT_FIELDS = frozenset(
    "training_targets prediction_molecules prediction_rows model_fits".split()
)


def _source_bundle_sha(paths: Sequence[Path]) -> str:
    root = _io.ROOT
    return cast(
        str,
        _sha256_bytes(
            "".join(
                f"{path.relative_to(root).as_posix()}|{_sha256(path)}\n"
                for path in sorted(paths, key=lambda item: str(item.relative_to(root)))
            ).encode("utf-8")
        ),
    )


def _group_sha(public: Mapping[str, Any], *, synthetic: bool = False) -> str:
    model_record = public.get("model_rows")
    if not synthetic:
        _require(
            isinstance(model_record, Mapping)
            and model_record.get("sha256") == GROUP_FOLDS_SHA256,
            "model rows are not the accepted group-fold bytes",
        )
    values = [public] + [
        public.get(key) for key in ("input_receipts", "projection_receipts", "receipts")
    ]
    for value in values:
        if isinstance(value, Mapping) and "group_folds_sha256" in value:
            _require(
                value["group_folds_sha256"] == GROUP_FOLDS_SHA256,
                "group-fold receipt differs",
            )
            return GROUP_FOLDS_SHA256
    return GROUP_FOLDS_SHA256


def _contains_token(text: str, token: str) -> bool:
    camel_separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    token_separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", token)
    words = re.findall(r"[a-z0-9]+", camel_separated.lower())
    wanted = re.findall(r"[a-z0-9]+", token_separated.lower())
    return bool(wanted) and any(
        words[index : index + len(wanted)] == wanted
        for index in range(len(words) - len(wanted) + 1)
    )


def _contains_forbidden(value: object, tokens: tuple[str, ...]) -> bool:
    if isinstance(value, Mapping):
        return any(
            (
                str(key).lower().replace("-", "_")
                not in {
                    "eval_metric",
                    "random_score_type",
                    "score_function",
                }
                and any(_contains_token(str(key), token) for token in tokens)
            )
            or _contains_forbidden(child, tokens)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden(child, tokens) for child in value)
    if isinstance(value, str):
        return any(_contains_token(value, token) for token in tokens)
    return False


def _validate_parameters(value: object, stage: str) -> list[dict[str, Any]]:
    expected = (
        ("TRACE-C1-MORGAN-CATBOOST", "TRACE-G0-MAPL-FIXED")
        if stage == "outer"
        else ("TRACE-G0-MAPL-FIXED",)
    )
    _require(isinstance(value, list), "resolved CatBoost parameters differ")
    records = cast(list[dict[str, Any]], value)
    _require(len(records) == len(expected), "resolved CatBoost parameter count differs")
    for record, system in zip(records, expected, strict=True):
        _require(
            set(record) == _PARAM_FIELDS and record["system_id"] == system,
            "resolved CatBoost parameter schema differs",
        )
        params = record["canonical_get_all_params_json"]
        digest = record["canonical_get_all_params_sha256"]
        _require(
            isinstance(params, Mapping),
            "resolved CatBoost parameters are not an object",
        )
        _require(
            not _contains_forbidden(
                params, ("score", "truth", "private_audit", "sealed")
            ),
            "resolved CatBoost parameters leak forbidden metadata",
        )
        _require(
            isinstance(digest, str) and _sha256_bytes(_json_bytes(params)) == digest,
            "resolved CatBoost parameter hash differs",
        )
    return records


def _validate_readonly_root(root: Path) -> None:
    _require_readonly_root(root, "cell tree is writable or contains a symlink")


def _load_fragment(root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    _validate_readonly_root(root)
    receipt, raw = _read_json(_rooted_path(root, "cell_receipt.json"))
    _require(
        receipt.get("schema_version")
        in {
            "cypshift.openadmet_cyp_2026.r3b_cell.v1",
            "cypshift.openadmet_cyp_2026.r3b_cell.v5",
        },
        "cell receipt schema differs",
    )
    if receipt.get("contract_sha256") == _io.V5_SHA256:
        _require(
            receipt["schema_version"] == "cypshift.openadmet_cyp_2026.r3b_cell.v5",
            "cell v5 schema differs",
        )
    frag = cast(dict[str, Any], receipt.get("prediction_fragment", {}))
    _require(set(frag) == _io.MODEL_RECORD_FIELDS, "fragment receipt schema differs")
    _require(
        frag["path"] == "prediction_fragment.csv"
        and frag["columns"] == list(FRAGMENT_COLUMNS)
        and frag["schema_version"] == "",
        "fragment receipt columns differ",
    )
    _require(
        type(frag["bytes"]) is int
        and frag["bytes"] >= 0
        and type(frag["rows"]) is int
        and frag["rows"] >= 0,
        "fragment receipt counts differ",
    )
    path = _rooted_path(root, str(frag["path"]))
    payload = path.read_bytes()
    _require(
        _sha256_bytes(payload) == frag["sha256"] and len(payload) == frag["bytes"],
        "cell fragment receipt differs",
    )
    rows = _read_csv_bytes(payload, FRAGMENT_COLUMNS, "prediction fragment")
    _require(len(rows) == frag["rows"], "cell fragment row count differs")
    metadata = {
        key: value
        for key, value in receipt.items()
        if key not in ("accounting", "authority", "prediction_fragment")
    }
    _require(
        not _contains_forbidden(
            metadata, ("truth", "score", "metric", "target_values", "private_audit")
        ),
        "forbidden cell receipt metadata",
    )
    _require(set(receipt) == _CELL_RECEIPT_FIELDS, "cell receipt fields differ")
    _require_exact_mapping(
        receipt.get("authority"), INHERITED_AUTHORITY, "cell authority differs"
    )
    feature_receipts = receipt["feature_receipts"]
    _require(
        isinstance(feature_receipts, Mapping)
        and set(feature_receipts) == {"feature_manifest_sha256"}
        and _is_sha(feature_receipts["feature_manifest_sha256"]),
        "feature receipt schema differs",
    )
    target = receipt["target_receipt"]
    _require(
        isinstance(target, Mapping) and set(target) == _TARGET_RECEIPT_FIELDS,
        "target receipt schema differs",
    )
    _require(
        target["cell_id"] == receipt.get("cell_id"),
        "target receipt cell identity differs",
    )
    stage = str(receipt["stage"])
    _require(
        stage in ("outer", "inner") and target["stage"] == stage,
        "target receipt context differs",
    )
    _context_from_receipt(receipt, str(receipt["contract_sha256"]), stage)
    _require(
        type(target["rows"]) is int and target["rows"] >= 0,
        "target receipt row count differs",
    )
    _require(
        all(_is_sha(target[key]) for key in ("sha256", "identity_sha256")),
        "target receipt hash differs",
    )
    _require(raw == _json_bytes(receipt), "cell receipt serialization differs")
    if receipt["schema_version"].endswith(".v5"):
        _require(
            receipt["runner_source_sha256"]
            == _source_bundle_sha(
                [
                    Path(__file__).with_name("run_r3b_cells.py"),
                    Path(__file__),
                    Path(__file__).with_name("r3b_cell_io.py"),
                ]
            ),
            "cell runner source receipt differs",
        )
        _require_exact_mapping(
            receipt["accounting"],
            _CELL_ACCOUNTING | {"feature_arrays_opened": 5},
            "cell accounting differs",
        )
        _validate_parameters(
            receipt["resolved_catboost_parameters"], str(receipt["stage"])
        )
        counts = receipt["counts"]
        _require(
            isinstance(counts, Mapping)
            and set(counts) == _COUNT_FIELDS
            and all(type(counts[name]) is int and counts[name] >= 0 for name in counts)
            and counts["training_targets"] > 0
            and counts["prediction_rows"] == len(rows)
            and counts["prediction_rows"]
            == counts["prediction_molecules"] * len(receipt["system_ids"])
            and counts["model_fits"] == (2 if receipt["stage"] == "outer" else 1),
            "cell counts differ",
        )
    return receipt, rows


def _context_from_receipt(
    receipt: Mapping[str, Any], contract_sha: str, stage: str
) -> tuple[str, int, int, int | None, str]:
    target = cast(Mapping[str, Any], receipt.get("target_receipt", {}))
    endpoint = str(target.get("endpoint", ""))
    repeat = _parse_int(str(target.get("repeat", "")), "target repeat", 0, 2)
    outer = _parse_int(str(target.get("outer_fold", "")), "target outer fold", 0, 4)
    inner_value = target.get("inner_fold")
    inner = (
        None
        if stage == "outer" or inner_value in (None, "", "none")
        else _parse_int(str(inner_value), "target inner fold", 0, 3)
    )
    scope = (
        OUTER_SCOPE if stage == "outer" else f"openadmet-direct-inner-v1|outer={outer}"
    )
    _require(
        endpoint in ENDPOINTS and 0 <= repeat < 3 and 0 <= outer < 5,
        "cell context is invalid",
    )
    if stage == "inner":
        _require(inner is not None and 0 <= inner < 4, "inner cell context is invalid")
    expected = _cell_id(contract_sha, stage, endpoint, repeat, outer, inner, scope)
    _require(receipt.get("cell_id") == expected, "cell identity differs")
    expected_path = (
        f"outer_targets/{endpoint}/repeat-{repeat}/outer-{outer}.csv"
        if stage == "outer"
        else f"inner_targets/{endpoint}/repeat-{repeat}/outer-{outer}/inner-{inner}.csv"
    )
    _require(target.get("relative_path") == expected_path, "target path schema differs")
    return endpoint, repeat, outer, inner, scope


def _validate_fragment_rows(
    rows: Sequence[Mapping[str, str]],
    receipt: Mapping[str, Any],
    stage: str,
    contract_sha: str,
    group_sha: str,
    model_rows: Sequence[Mapping[str, str]],
    token_sha: str = "",
    fold_index: Mapping[str, Any] | None = None,
) -> None:
    endpoint, repeat, outer, inner, scope = _context_from_receipt(
        receipt, contract_sha, stage
    )
    systems = OUTER_SYSTEMS if stage == "outer" else (MAPLIGHT,)
    _require(tuple(receipt.get("system_ids", ())) == systems, "cell system IDs differ")
    rank = {name: i for i, name in enumerate(OUTER_SYSTEMS)}
    _require(
        list(rows)
        == sorted(
            rows,
            key=lambda row: (
                rank[row["system_id"]],
                row["endpoint"],
                _parse_int(row["repeat"], "fragment repeat", 0, 2),
                _parse_int(row["outer_fold"], "fragment outer fold", 0, 4),
                -1
                if row["inner_fold"] == ""
                else _parse_int(row["inner_fold"], "fragment inner fold", 0, 3),
                row["molecule_id"],
            ),
        ),
        "fragment row order differs",
    )
    _require(
        receipt.get("inner_selection_token_sha256", "") == token_sha,
        "cell token receipt differs",
    )
    context_rows = (
        fold_index["by_context"].get((repeat, outer), [])
        if fold_index is not None
        else [
            r
            for r in model_rows
            if int(r["repeat"]) == repeat and int(r["outer_validation_fold"]) == outer
        ]
    )
    if stage == "outer":
        expected_ids = {
            r["molecule_id"] for r in context_rows if int(r["outer_fold"]) == outer
        }
    else:
        expected_ids = {
            r["molecule_id"]
            for r in context_rows
            if int(r["outer_fold"]) != outer
            and r["inner_fold"] != ""
            and int(r["inner_fold"]) == inner
        }
    component = {r["molecule_id"]: r["similarity_component_hash"] for r in context_rows}
    applicability: dict[str, str] = {}
    key_fields = (
        ("molecule_id", "endpoint", "repeat", "outer_fold", "system_id")
        if stage == "outer"
        else (
            "molecule_id",
            "endpoint",
            "repeat",
            "outer_fold",
            "inner_fold",
            "system_id",
        )
    )
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        row_repeat = _parse_int(row["repeat"], "fragment repeat", 0, 2)
        row_outer = _parse_int(row["outer_fold"], "fragment outer fold", 0, 4)
        row_inner = (
            ""
            if row["inner_fold"] == ""
            else str(_parse_int(row["inner_fold"], "fragment inner fold", 0, 3))
        )
        _require(
            row["endpoint"] == endpoint
            and row_repeat == repeat
            and row_outer == outer
            and row_inner == ("" if inner is None else str(inner))
            and row["scope"] == scope,
            "fragment context differs",
        )
        _require(
            row["system_id"] in systems and row["molecule_id"] in expected_ids,
            "fragment membership differs",
        )
        _require(
            row["component_id"] == component.get(row["molecule_id"]),
            "component mapping differs",
        )
        _canonical_float(row["prediction"], "prediction")
        _canonical_float(row["applicability_score"], "applicability", 0.0, 1.0)
        _require(
            applicability.setdefault(row["molecule_id"], row["applicability_score"])
            == row["applicability_score"],
            "applicability differs across systems",
        )
        key = tuple(row[x] for x in key_fields)
        _require(key not in seen, "duplicate prediction key")
        seen.add(key)
        _require(
            row["model_id"]
            == _model_id(
                contract_sha, row["system_id"], endpoint, repeat, outer, inner, scope
            ),
            "model ID differs",
        )
        _require(
            row["feature_spec_id"] == FEATURE_SPECS[row["system_id"]],
            "feature specification differs",
        )
        _require(
            row["split_id"] == _split_id(group_sha, repeat, outer, inner, scope),
            "split ID differs",
        )
    _require(
        len(rows) == len(expected_ids) * len(systems), "fragment population differs"
    )


def _freeze(
    *,
    stage: str,
    cell_roots: Sequence[Path],
    output_root: Path,
    model_public_root: Path,
    model_public_manifest_sha256: str,
    preflight_receipt: Path,
    feature_manifest_sha256: str,
    inner_selection_token: Path | None = None,
    preflight_receipt_sha256: str | None = None,
    synthetic: bool = False,
    contract_path: Path = V5,
    parent_contract_path: Path = V4,
) -> Path:
    _require(stage in ("outer", "inner"), "freeze stage differs")
    _require(
        not output_root.exists() and not output_root.is_symlink(),
        "freeze output exists",
    )
    freezer_source_sha = _source_bundle_sha(
        [Path(__file__), Path(__file__).with_name("r3b_cell_io.py")]
    )
    _active_contract, parent_contract, contract_sha, parent_sha = _contract_receipts(
        synthetic=synthetic,
        v5_path=contract_path,
        v4_path=V4,
        v3_path=V3 if contract_path.resolve() == V5.resolve() else parent_contract_path,
    )
    if not synthetic:
        _require(
            feature_manifest_sha256
            == parent_contract["accepted_r3a_feature_root"]["manifest_sha256"],
            "accepted R3A feature manifest differs",
        )
    _validate_preflight(
        preflight_receipt,
        contract_sha,
        model_public_manifest_sha256,
        preflight_receipt_sha256,
    )
    _public, model_rows, _receipts, public_sha = _load_public(
        model_public_root,
        model_public_manifest_sha256,
        synthetic=synthetic,
        verify_target_payloads=False,
        require_readonly=True,
    )
    _require(
        _public.get("contract_sha256") == contract_sha
        and _public.get("parent_contract_sha256") == parent_sha,
        "model-public contract binding differs",
    )
    index = _fold_index(public_sha)
    token_sha = ""
    if stage == "inner":
        _require(inner_selection_token is not None, "inner token is required")
        token, token_raw = _read_json(inner_selection_token)
        _require(
            token.get("schema_version")
            == "cypshift.openadmet_cyp_2026.r3b_inner_selection_token.v1"
            and token.get("contract_sha256") == contract_sha
            and token.get("selected_system_id") == MAPLIGHT
            and token.get("outer_outcome") == "PASS",
            "inner selection token differs",
        )
        _require_exact_mapping(
            token.get("authority"),
            INHERITED_AUTHORITY,
            "inner selection authority differs",
        )
        _require(
            not _contains_forbidden(
                {key: value for key, value in token.items() if key != "authority"},
                ("score", "metric", "comparison", "influence", "target"),
            ),
            "inner selection token leaks score",
        )
        _require(
            set(token)
            == {
                "schema_version",
                "contract_sha256",
                "token_writer_source_sha256",
                "outer_assessment_sha256",
                "selected_system_id",
                "outer_outcome",
                "authority",
            },
            "inner selection token fields differ",
        )
        for field in ("token_writer_source_sha256", "outer_assessment_sha256"):
            _require(_is_sha(token[field]), "inner selection token receipt differs")
        token_sha = _sha256_bytes(token_raw)
    expected = 60 if stage == "outer" else 240
    _require(len(cell_roots) == expected, "cell set count differs")
    loaded = [_load_fragment(root) for root in cell_roots]
    loaded.sort(key=lambda item: str(item[0].get("cell_id", "")))
    seen: set[tuple[str, ...]] = set()
    all_rows: list[dict[str, str]] = []
    cell_receipts: list[str] = []
    contexts: set[tuple[str, int, int, int | None]] = set()
    inner_prediction_ids: dict[tuple[str, int, int, int], set[str]] = {}
    aggregate_params: list[dict[str, Any]] | None = None
    group_sha = _group_sha(_public, synthetic=synthetic)
    row_key_fields = (
        ("molecule_id", "endpoint", "repeat", "outer_fold", "system_id")
        if stage == "outer"
        else (
            "molecule_id",
            "endpoint",
            "repeat",
            "outer_fold",
            "inner_fold",
            "system_id",
        )
    )
    expected_preflight_sha = _sha256(preflight_receipt)
    for receipt, rows in loaded:
        endpoint, repeat, outer, inner, _scope = _context_from_receipt(
            receipt, contract_sha, stage
        )
        context = (endpoint, repeat, outer, inner)
        _require(context not in contexts, "duplicate cell context")
        contexts.add(context)
        _require(
            receipt.get("model_public_manifest_sha256") == public_sha
            and receipt.get("preflight_receipt_sha256") == expected_preflight_sha,
            "cell input receipt differs",
        )
        feature_receipts = cast(Mapping[str, Any], receipt.get("feature_receipts", {}))
        _require(
            feature_receipts.get("feature_manifest_sha256") == feature_manifest_sha256,
            "cell feature receipt differs",
        )
        if receipt["schema_version"].endswith(".v5"):
            parameters = _validate_parameters(
                receipt["resolved_catboost_parameters"], stage
            )
            if aggregate_params is None:
                aggregate_params = parameters
            else:
                _require(
                    parameters == aggregate_params, "resolved CatBoost parameters drift"
                )
        _validate_fragment_rows(
            rows,
            receipt,
            stage,
            contract_sha,
            group_sha,
            model_rows,
            token_sha,
            index,
        )
        if stage == "inner":
            inner_prediction_ids[(endpoint, repeat, outer, cast(int, inner))] = {
                row["molecule_id"] for row in rows
            }
        cell_receipts.append(_sha256_bytes(_json_bytes(receipt)))
        for row in rows:
            key = tuple(row[k] for k in row_key_fields)
            _require(key not in seen, "duplicate prediction key")
            seen.add(key)
            all_rows.append(row)
    expected_contexts = {
        (endpoint, repeat, outer, None if stage == "outer" else inner)
        for endpoint in ENDPOINTS
        for repeat in range(3)
        for outer in range(5)
        for inner in ((None,) if stage == "outer" else range(4))
    }
    _require(contexts == expected_contexts, "cell set differs")
    if stage == "inner":
        for endpoint in ENDPOINTS:
            for repeat in range(3):
                for outer in range(5):
                    structural = {
                        row["molecule_id"]
                        for row in index["by_context"].get((repeat, outer), [])
                        if int(row["outer_fold"]) != outer and row["inner_fold"] != ""
                    }
                    parts = [
                        inner_prediction_ids[(endpoint, repeat, outer, fold)]
                        for fold in range(4)
                    ]
                    _require(
                        len(set().union(*parts)) == len(structural)
                        and sum(map(len, parts)) == len(structural),
                        "inner prediction partition differs",
                    )
    rank = {name: i for i, name in enumerate(OUTER_SYSTEMS)}
    all_rows.sort(
        key=lambda r: (
            rank[r["system_id"]],
            r["endpoint"],
            int(r["repeat"]),
            int(r["outer_fold"]),
            -1 if r["inner_fold"] == "" else int(r["inner_fold"]),
            r["molecule_id"],
        )
    )
    expected_rows = len(all_rows)
    if not synthetic:
        _require(expected_rows == 235440, "production prediction row count differs")
    if aggregate_params is None:
        aggregate_params = []
    out_name = (
        "global_oof_predictions.csv"
        if stage == "outer"
        else "global_inner_oof_predictions.csv"
    )
    manifest_name = (
        "global_oof_freeze_manifest.json"
        if stage == "outer"
        else "global_inner_oof_freeze_manifest.json"
    )
    payload = _csv_bytes(FRAGMENT_COLUMNS, all_rows)
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3b_outer_freeze.v2"
        if stage == "outer"
        else "cypshift.openadmet_cyp_2026.r3b_inner_freeze.v2",
        "contract_sha256": contract_sha,
        "freezer_source_sha256": freezer_source_sha,
        "preflight_receipt_sha256": _sha256(preflight_receipt),
        "model_public_manifest_sha256": public_sha,
        "feature_manifest_sha256": feature_manifest_sha256,
        "cell_receipts": sorted(cell_receipts),
        "prediction_artifact": {
            "path": out_name,
            "sha256": _sha256_bytes(payload),
            "bytes": len(payload),
            "rows": expected_rows,
            "eligible_rows": expected_rows,
            "columns": list(FRAGMENT_COLUMNS),
            "schema_version": "",
        },
        "counts": {
            "cell_receipts": expected,
            "prediction_rows": expected_rows,
            "systems": 4 if stage == "outer" else 1,
        },
        "resolved_catboost_parameters": aggregate_params,
        "accounting": _FREEZER_ACCOUNTING | {"cell_fragments_opened": expected},
        "authority": dict(INHERITED_AUTHORITY),
    }
    if stage == "inner":
        manifest["inner_selection_token_sha256"] = token_sha
    _require(
        not output_root.exists() and not output_root.is_symlink(),
        "freeze output exists",
    )
    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".r3b-freeze-", dir=str(output_root.parent)))
    try:
        (staging / out_name).write_bytes(payload)
        (staging / manifest_name).write_bytes(_json_bytes(manifest))
        _readonly_tree(staging)
        _fsync_tree(staging)
        _promote_noreplace(staging, output_root)
        _fsync_parent(output_root)
    except Exception:
        if staging.exists():
            _cleanup_tree(staging)
        raise
    return output_root


def freeze_outer(**kwargs: Any) -> Path:
    return _freeze(stage="outer", **kwargs)


def freeze_inner(**kwargs: Any) -> Path:
    return _freeze(stage="inner", **kwargs)


def _verify_target(
    public_root: Path,
    receipt: Mapping[str, Any],
    endpoint: str,
    stage: str,
    repeat: int,
    outer: int,
    inner: int | None,
    model_rows: Sequence[Mapping[str, str]],
    group_sha: str,
    cell: str,
    contract_sha: str,
    fold_index: Mapping[str, Any] | None = None,
) -> list[dict[str, str]]:
    _require(
        set(receipt) == _TARGET_RECEIPT_FIELDS,
        "target receipt schema differs",
    )
    _require(
        receipt.get("stage") == stage
        and receipt.get("endpoint") == endpoint
        and _parse_int(str(receipt.get("repeat", "")), "target repeat", 0, 2) == repeat
        and _parse_int(str(receipt.get("outer_fold", "")), "target outer fold", 0, 4)
        == outer,
        "target receipt context differs",
    )
    if stage == "outer":
        _require(
            receipt.get("inner_fold") in (None, "", "none"),
            "outer target inner fold differs",
        )
    else:
        _require(
            _parse_int(str(receipt.get("inner_fold", "")), "target inner fold", 0, 3)
            == inner,
            "inner target context differs",
        )
    target_scope = (
        OUTER_SCOPE if stage == "outer" else f"openadmet-direct-inner-v1|outer={outer}"
    )
    target_id = _cell_id(
        contract_sha, stage, endpoint, repeat, outer, inner, target_scope
    )
    _require(
        receipt.get("cell_id") == target_id and cell == target_id,
        "target cell identity differs",
    )
    expected_path = (
        f"outer_targets/{endpoint}/repeat-{repeat}/outer-{outer}.csv"
        if stage == "outer"
        else f"inner_targets/{endpoint}/repeat-{repeat}/outer-{outer}/inner-{inner}.csv"
    )
    _require(
        receipt.get("relative_path") == expected_path, "target path schema differs"
    )
    rel = _safe_rel(str(receipt.get("relative_path", receipt.get("path", ""))))
    target_path = _rooted_path(public_root, str(rel))
    raw = target_path.read_bytes()
    _require(
        _sha256_bytes(raw) == receipt.get("sha256") and len(raw) >= 1,
        "target payload receipt differs",
    )
    rows = _read_csv_bytes(raw, ("observation_id", "molecule_id", "point"), "target")
    _require(
        rows
        == sorted(rows, key=lambda row: (row["molecule_id"], row["observation_id"])),
        "target row order differs",
    )
    _require(
        type(receipt.get("rows")) is int and len(rows) == receipt["rows"],
        "target row count differs",
    )
    identity = _csv_bytes(("observation_id", "molecule_id"), rows)
    _require(
        _sha256_bytes(identity) == receipt.get("identity_sha256"),
        "target identity receipt differs",
    )
    _require(
        len({r["observation_id"] for r in rows}) == len(rows)
        and len({r["molecule_id"] for r in rows}) == len(rows),
        "duplicate target key",
    )
    for row in rows:
        try:
            point = float(row["point"])
        except ValueError as exc:
            raise R3BError("target point is not finite") from exc
        _require(math.isfinite(point), "target point is not finite")
        candidates = (
            fold_index["by_context"].get((repeat, outer), [])
            if fold_index is not None
            else [
                model
                for model in model_rows
                if int(model["repeat"]) == repeat
                and int(model["outer_validation_fold"]) == outer
            ]
        )
        candidates = (m for m in candidates if m["molecule_id"] == row["molecule_id"])
        if stage == "outer":
            ok = any(int(m["outer_fold"]) != outer for m in candidates)
        else:
            ok = any(
                int(m["outer_fold"]) != outer
                and m["inner_fold"] not in ("", "none")
                and int(m["inner_fold"]) != inner
                for m in candidates
            )
        _require(ok, "target molecule crosses structural split")
    return cast(list[dict[str, str]], rows)

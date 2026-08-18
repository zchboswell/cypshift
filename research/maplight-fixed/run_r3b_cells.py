from __future__ import annotations

import argparse
import importlib.util
import math
import shutil
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np

_io_spec = importlib.util.spec_from_file_location(
    "r3b_cell_io", Path(__file__).with_name("r3b_cell_io.py")
)
assert _io_spec is not None and _io_spec.loader is not None
_io = importlib.util.module_from_spec(_io_spec)
sys.modules[_io_spec.name] = _io
_io_spec.loader.exec_module(_io)

ARRAYS = _io.ARRAYS
CATBOOST_ARGS = _io.CATBOOST_ARGS
ENDPOINTS = _io.ENDPOINTS
FEATURE_SPECS = _io.FEATURE_SPECS
FRAGMENT_COLUMNS = _io.FRAGMENT_COLUMNS
INHERITED_AUTHORITY = _io.INHERITED_AUTHORITY
MAPLIGHT = _io.MAPLIGHT
MAP_ARRAYS = _io.MAP_ARRAYS
MODEL_ROWS_COLUMNS = _io.MODEL_ROWS_COLUMNS
OUTER_SCOPE = _io.OUTER_SCOPE
OUTER_SYSTEMS = _io.OUTER_SYSTEMS
R3BError = _io.R3BError
V5 = _io.V5
V5_SHA256 = _io.V5_SHA256
V3 = _io.V3
V3_SHA256 = _io.V3_SHA256
V4 = _io.V4
V4_SHA256 = _io.V4_SHA256
GROUP_FOLDS_SHA256 = _io.GROUP_FOLDS_SHA256
_cell_id = _io._cell_id
_contract_receipts = _io._contract_receipts
_csv_bytes = _io._csv_bytes
_json_bytes = _io._json_bytes
_is_sha = _io._is_sha
_load_feature_root = _io._load_feature_root
_load_public = _io._load_public
_model_id = _io._model_id
_parse_int = _io._parse_int
_promote_noreplace = _io._promote_noreplace
_read_json = _io._read_json
_read_csv_bytes, _rooted_path = _io._read_csv_bytes, _io._rooted_path
_readonly_tree = _io._readonly_tree
_require = _io._require
_require_exact_mapping = _io._require_exact_mapping
_sha256 = _io._sha256
_sha256_bytes = _io._sha256_bytes
_split_id = _io._split_id
_verify_runtime = _io._verify_runtime
_fold_index = _io._fold_index
_context_rows = _io._context_rows
_build_fold_index = _io._build_fold_index

_PREFLIGHT_FIELDS = frozenset(
    "schema_version contract_sha256 model_public_manifest_sha256 "
    "private_projection_audit_sha256 checks passed failure_reasons accounting "
    "authority".split()
)
_PREFLIGHT_CHECKS = frozenset(
    "outer_score_support_cells outer_training_populations "
    "inner_training_populations q90_residual_eligibility_populations".split()
)
_TRAIN_FIELDS = frozenset(
    "stage endpoint repeat outer_fold inner_fold eligible_targets "
    "minimum_eligible_targets passes".split()
)
_PREFLIGHT_SPECS = {
    "outer_score_support_cells": (
        frozenset(
            "endpoint repeat outer_fold component_count minimum_components "
            "passes".split()
        ),
        60,
    ),
    "outer_training_populations": (_TRAIN_FIELDS, 60),
    "inner_training_populations": (_TRAIN_FIELDS, 240),
    "q90_residual_eligibility_populations": (
        frozenset(
            "endpoint repeat outer_fold eligible_residuals "
            "minimum_eligible_targets passes".split()
        ),
        60,
    ),
}
_PREFLIGHT_REASONS = {
    "outer_score_support_cells": "OUTER_COMPONENT_SUPPORT",
    "outer_training_populations": "OUTER_TRAINING_EMPTY",
    "inner_training_populations": "INNER_TRAINING_EMPTY",
    "q90_residual_eligibility_populations": "Q90_RESIDUAL_ELIGIBILITY_EMPTY",
}
_PREFLIGHT_ACCOUNTING = {
    "preflight_target_files_opened": 300,
    **dict.fromkeys(
        "outer_model_target_files_opened inner_model_target_files_opened "
        "sealed_truth_files_opened outer_model_fits inner_model_fits "
        "prediction_rows provisional_metric_rows tdi_files_opened "
        "blinded_test_files_opened episode_or_anchor_files_opened "
        "official_metric_calls submission_rows_opened leaderboard_submissions "
        "transductive_operations gpu_fits".split(),
        0,
    ),
}


def _preflight_key(name: str, record: Mapping[str, Any]) -> tuple[object, ...]:
    endpoint = str(record["endpoint"])
    repeat = _parse_int(str(record["repeat"]), "preflight repeat", 0, 2)
    outer = _parse_int(str(record["outer_fold"]), "preflight outer fold", 0, 4)
    _require(endpoint in ENDPOINTS, f"preflight {name} endpoint differs")
    if name == "inner_training_populations":
        _require(record["stage"] == "inner", f"preflight {name} stage differs")
        return (
            endpoint,
            repeat,
            outer,
            _parse_int(str(record["inner_fold"]), "preflight inner fold", 0, 3),
        )
    if name == "outer_training_populations":
        _require(
            record["stage"] == "outer" and record["inner_fold"] in (None, "", "none"),
            f"preflight {name} context differs",
        )
    return endpoint, repeat, outer


def _validate_preflight(
    path: Path,
    contract_sha: str,
    public_sha: str,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    receipt, _raw = _read_json(path, expected_sha256)
    _require(set(receipt) == _PREFLIGHT_FIELDS, "preflight fields differ")
    _require(
        receipt["schema_version"]
        in {
            "cypshift.openadmet_cyp_2026.r3b_preflight.v1",
            "cypshift.openadmet_cyp_2026.r3b_preflight.v5",
        }
        and receipt["contract_sha256"] == contract_sha
        and receipt["model_public_manifest_sha256"] == public_sha,
        "preflight receipt differs",
    )
    _require_exact_mapping(
        receipt["authority"], INHERITED_AUTHORITY, "preflight authority differs"
    )
    if contract_sha == V5_SHA256:
        _require(
            receipt["schema_version"] == "cypshift.openadmet_cyp_2026.r3b_preflight.v5",
            "preflight v5 schema differs",
        )
    audit_sha = receipt["private_projection_audit_sha256"]
    _require(_is_sha(audit_sha), "preflight audit receipt differs")
    checks = receipt["checks"]
    _require(
        isinstance(checks, Mapping) and set(checks) == _PREFLIGHT_CHECKS,
        "preflight checks differ",
    )
    ordered_contexts = [
        (endpoint, repeat, outer)
        for endpoint in ENDPOINTS
        for repeat in range(3)
        for outer in range(5)
    ]
    for name, (record_fields, count) in _PREFLIGHT_SPECS.items():
        records = checks[name]
        _require(
            isinstance(records, list) and len(records) == count,
            f"preflight {name} count differs",
        )
        seen: set[tuple[object, ...]] = set()
        for record in records:
            _require(
                isinstance(record, Mapping) and set(record) == record_fields,
                f"preflight {name} schema differs",
            )
            key = _preflight_key(name, cast(Mapping[str, Any], record))
            _require(key not in seen, f"preflight {name} duplicate context")
            seen.add(key)
            minimum_name = (
                "minimum_components"
                if name == "outer_score_support_cells"
                else "minimum_eligible_targets"
            )
            minimum = 10 if name == "outer_score_support_cells" else 1
            _require(
                type(record[minimum_name]) is int and record[minimum_name] == minimum,
                f"preflight {name} minimum differs",
            )
            measure_name = {
                "outer_score_support_cells": "component_count",
                "q90_residual_eligibility_populations": "eligible_residuals",
            }.get(name, "eligible_targets")
            _require(
                type(record[measure_name]) is int
                and record[measure_name] >= 0
                and type(record["passes"]) is bool
                and record["passes"] is (record[measure_name] >= minimum),
                f"preflight {name} values differ",
            )
        expected_order = (
            ordered_contexts
            if name != "inner_training_populations"
            else [
                (*context, inner) for context in ordered_contexts for inner in range(4)
            ]
        )
        _require(
            seen == set(expected_order)
            and [
                _preflight_key(name, cast(Mapping[str, Any], item)) for item in records
            ]
            == expected_order,
            f"preflight {name} contexts or order differs",
        )
    expected_reasons = []
    for name in _PREFLIGHT_SPECS:
        if any(not item["passes"] for item in checks[name]):
            expected_reasons.append(_PREFLIGHT_REASONS[name])
    outer_training = {
        _preflight_key("outer_training_populations", record): record["eligible_targets"]
        for record in cast(
            list[Mapping[str, Any]], checks["outer_training_populations"]
        )
    }
    for record in cast(
        list[Mapping[str, Any]], checks["q90_residual_eligibility_populations"]
    ):
        _require(
            record["eligible_residuals"]
            == outer_training[
                _preflight_key("q90_residual_eligibility_populations", record)
            ],
            "preflight q90 arithmetic differs",
        )
    _require(
        receipt["failure_reasons"] == expected_reasons,
        "preflight failure reasons differ",
    )
    _require(
        receipt["passed"] is True and not expected_reasons, "preflight did not pass"
    )
    _require_exact_mapping(
        receipt["accounting"], _PREFLIGHT_ACCOUNTING, "preflight accounting differs"
    )
    return cast(dict[str, Any], receipt)


_io._validate_preflight = _validate_preflight  # type: ignore[attr-defined]

_freezer_spec = importlib.util.spec_from_file_location(
    "r3b_cell_freezer", Path(__file__).with_name("r3b_cell_freezer.py")
)
assert _freezer_spec is not None and _freezer_spec.loader is not None
_freezer = importlib.util.module_from_spec(_freezer_spec)
sys.modules[_freezer_spec.name] = _freezer
_freezer_spec.loader.exec_module(_freezer)
_context_from_receipt = _freezer._context_from_receipt
_freeze = _freezer._freeze
_load_fragment = _freezer._load_fragment
_validate_fragment_rows = _freezer._validate_fragment_rows
_verify_target = _freezer._verify_target
freeze_inner = _freezer.freeze_inner
_group_sha = _freezer._group_sha
_source_bundle_sha = _freezer._source_bundle_sha
_contains_forbidden = _freezer._contains_forbidden
freeze_outer = _freezer.freeze_outer


def _feature_matrix(
    arrays: Mapping[str, np.ndarray[Any, Any]], system: str, indices: Sequence[int]
) -> np.ndarray[Any, Any]:
    if system in (OUTER_SYSTEMS[0],):
        return np.empty((len(indices), 0), dtype=np.float64)
    if system in (OUTER_SYSTEMS[1], OUTER_SYSTEMS[3]):
        return cast(
            np.ndarray[Any, Any],
            np.asarray(arrays["morgan_binary"][list(indices)], dtype=np.float64),
        )
    return cast(
        np.ndarray[Any, Any],
        np.ascontiguousarray(
            np.concatenate([arrays[name][list(indices)] for name in MAP_ARRAYS], axis=1)
        ),
    )


def _median(values: Sequence[float]) -> float:
    ordered = sorted(float(v) for v in values)
    _require(
        bool(ordered) and all(math.isfinite(v) for v in ordered),
        "median population invalid",
    )
    mid = len(ordered) // 2
    return (
        ordered[mid]
        if len(ordered) % 2
        else math.fsum(ordered[mid - 1 : mid + 1]) / 2.0
    )


def _tanimoto(a: np.ndarray[Any, Any], b: np.ndarray[Any, Any]) -> float:
    aa = np.asarray(a, dtype=np.uint8)
    bb = np.asarray(b, dtype=np.uint8)
    _require(aa.shape == bb.shape, "Morgan shape differs")
    intersection = int(np.logical_and(aa != 0, bb != 0).sum())
    union = int(np.logical_or(aa != 0, bb != 0).sum())
    if union == 0:
        return 1.0
    return float(intersection) / float(union)


def _catboost_predict(
    X: np.ndarray[Any, Any], y: np.ndarray[Any, Any], X_pred: np.ndarray[Any, Any]
) -> tuple[np.ndarray[Any, Any], dict[str, Any]]:
    try:
        from catboost import CatBoostRegressor  # type: ignore[import-not-found]
    except ImportError as exc:
        raise R3BError("CatBoost 1.2.1 is unavailable") from exc
    model = CatBoostRegressor(**CATBOOST_ARGS)
    model.fit(X, y)
    prediction = np.asarray(model.predict(X_pred), dtype=np.float64)
    _require(
        prediction.ndim == 1 and np.isfinite(prediction).all(),
        "CatBoost predictions are invalid",
    )
    params = cast(dict[str, Any], model.get_all_params())
    return prediction, params


def run_cell(
    *,
    stage: str,
    endpoint: str,
    repeat: int,
    outer_fold: int,
    inner_fold: int | None,
    feature_root: Path,
    feature_manifest_sha256: str,
    model_public_root: Path,
    model_public_manifest_sha256: str,
    preflight_receipt: Path,
    output_root: Path,
    inner_selection_token: Path | None = None,
    preflight_receipt_sha256: str | None = None,
    synthetic: bool = False,
    contract_path: Path = V5,
    parent_contract_path: Path = V4,
) -> Path:
    """Run exactly one outer or inner model cell in the current fresh process."""
    _require(
        stage in ("outer", "inner") and endpoint in ENDPOINTS, "cell context differs"
    )
    _require(0 <= repeat < 3 and 0 <= outer_fold < 5, "cell context differs")
    if stage == "inner":
        _require(
            inner_fold is not None and 0 <= inner_fold < 4, "inner cell context differs"
        )
    else:
        _require(inner_fold is None, "outer cell inner fold must be empty")
    _active_contract, parent_contract, contract_sha, _parent_sha = _contract_receipts(
        synthetic=synthetic,
        v5_path=contract_path,
        v4_path=V4,
        v3_path=V3 if contract_path.resolve() == V5.resolve() else parent_contract_path,
    )
    _verify_runtime(parent_contract, synthetic=synthetic)
    runner_source_sha = _source_bundle_sha(
        [
            Path(__file__),
            Path(__file__).with_name("r3b_cell_io.py"),
            Path(__file__).with_name("r3b_cell_freezer.py"),
        ]
    )
    scope = (
        OUTER_SCOPE
        if stage == "outer"
        else f"openadmet-direct-inner-v1|outer={outer_fold}"
    )
    cell = _cell_id(
        contract_sha, stage, endpoint, repeat, outer_fold, inner_fold, scope
    )
    _validate_preflight(
        preflight_receipt,
        contract_sha,
        model_public_manifest_sha256,
        preflight_receipt_sha256,
    )
    token_sha = ""
    if stage == "inner":
        _require(inner_selection_token is not None, "inner selection token is required")
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
    accepted = cast(Mapping[str, Any], parent_contract["accepted_r3a_feature_root"])
    _require(
        synthetic or feature_manifest_sha256 == accepted["manifest_sha256"],
        "accepted feature manifest differs",
    )
    _feature_manifest, feature_rows, arrays, feature_sha = _load_feature_root(
        feature_root, feature_manifest_sha256, synthetic=synthetic
    )
    if not synthetic:
        rows_receipt = cast(Mapping[str, Any], accepted["feature_rows"])
        _require(
            _feature_manifest["rows"]["sha256"] == rows_receipt["sha256"],
            "accepted feature rows differ",
        )
        records = cast(Mapping[str, Any], _feature_manifest["arrays"])
        for path, digest in cast(Mapping[str, str], accepted["arrays"]).items():
            record = records.get(Path(path).stem, records.get(path))
            _require(
                isinstance(record, Mapping) and record.get("npy_sha256") == digest,
                f"accepted feature array differs: {path}",
            )
    public, model_rows, receipts, public_sha = _load_public(
        model_public_root,
        model_public_manifest_sha256,
        synthetic=synthetic,
        verify_target_payloads=False,
    )
    _require(
        public.get("contract_sha256") == contract_sha
        and public.get("parent_contract_sha256") == _parent_sha,
        "model-public contract binding differs",
    )
    _require(
        {r["molecule_id"]: r["similarity_component_hash"] for r in feature_rows}
        == {r["molecule_id"]: r["similarity_component_hash"] for r in model_rows},
        "feature/fold component mapping differs",
    )
    index = _fold_index(public_sha)
    receipt = next(
        (
            x
            for x in receipts
            if x.get("stage") == stage
            and x.get("endpoint") == endpoint
            and int(x.get("repeat", -1)) == repeat
            and int(x.get("outer_fold", -1)) == outer_fold
            and (stage == "outer" or int(x.get("inner_fold", -1)) == inner_fold)
        ),
        None,
    )
    _require(isinstance(receipt, dict), "cell target receipt missing")
    targets = _verify_target(
        model_public_root,
        receipt,
        endpoint,
        stage,
        repeat,
        outer_fold,
        inner_fold,
        model_rows,
        _group_sha(public, synthetic=synthetic),
        cell,
        contract_sha,
        index,
    )
    by_id = {r["molecule_id"]: i for i, r in enumerate(feature_rows)}
    model = [
        r for r in _context_rows(index, repeat, outer_fold) if r["molecule_id"] in by_id
    ]
    train_ids: set[str]
    pred_ids: set[str]
    if stage == "outer":
        train_ids = {
            r["molecule_id"] for r in model if int(r["outer_fold"]) != outer_fold
        }
        pred_ids = {
            r["molecule_id"] for r in model if int(r["outer_fold"]) == outer_fold
        }
    else:
        train_ids = {
            r["molecule_id"]
            for r in model
            if int(r["outer_fold"]) != outer_fold
            and r["inner_fold"] not in ("", "none")
            and int(r["inner_fold"]) != inner_fold
        }
        pred_ids = {
            r["molecule_id"]
            for r in model
            if int(r["outer_fold"]) != outer_fold
            and r["inner_fold"] not in ("", "none")
            and int(r["inner_fold"]) == inner_fold
        }
        structural = {
            r["molecule_id"] for r in model if int(r["outer_fold"]) != outer_fold
        }
        _require(
            all(
                r["inner_fold"] in ("0", "1", "2", "3")
                for r in model
                if r["molecule_id"] in structural
            ),
            "inner structural partition differs",
        )
        partitions = [
            {
                r["molecule_id"]
                for r in model
                if int(r["outer_fold"]) != outer_fold and r["inner_fold"] == str(fold)
            }
            for fold in range(4)
        ]
        _require(
            len(set().union(*partitions)) == len(structural)
            and sum(map(len, partitions)) == len(structural),
            "inner structural partition differs",
        )
        _require(
            pred_ids <= structural, "inner prediction crosses outer training boundary"
        )
    target_by_id = {r["molecule_id"]: float(r["point"]) for r in targets}
    train_ids &= set(target_by_id)
    _require(train_ids and pred_ids, "cell training or prediction population is empty")
    train_order = sorted(train_ids)
    pred_order = sorted(pred_ids)
    train_idx = [by_id[x] for x in train_order]
    pred_idx = [by_id[x] for x in pred_order]
    y: np.ndarray[Any, Any] = np.asarray(
        [target_by_id[x] for x in train_order], dtype=np.float64
    )
    _require(np.isfinite(y).all(), "cell training target is nonfinite")
    predictions: dict[str, np.ndarray[Any, Any]] = {}
    params: list[dict[str, Any]] = []
    for system in (MAPLIGHT,) if stage == "inner" else OUTER_SYSTEMS:
        if system == OUTER_SYSTEMS[0]:
            value = _median(y.tolist())
            predictions[system] = np.full(len(pred_order), value, dtype=np.float64)
        elif system == OUTER_SYSTEMS[3]:
            train_morgan = arrays["morgan_binary"][train_idx]
            pred_morgan = arrays["morgan_binary"][pred_idx]
            values = []
            for row in pred_morgan:
                sims = [_tanimoto(row, base) for base in train_morgan]
                best = max(sims)
                tie = [i for i, score in enumerate(sims) if score == best]
                values.append(y[min(tie)])
            predictions[system] = np.asarray(values, dtype=np.float64)
        else:
            pred, resolved = _catboost_predict(
                _feature_matrix(arrays, system, train_idx),
                y,
                _feature_matrix(arrays, system, pred_idx),
            )
            predictions[system] = pred
            params.append(
                {
                    "system_id": system,
                    "canonical_get_all_params_json": resolved,
                    "canonical_get_all_params_sha256": _sha256_bytes(
                        _json_bytes(resolved)
                    ),
                }
            )
    rows: list[dict[str, object]] = []
    group_sha = _group_sha(public, synthetic=synthetic)
    split = _split_id(group_sha, repeat, outer_fold, inner_fold, scope)
    component = {r["molecule_id"]: r["similarity_component_hash"] for r in model}
    applicability = {
        molecule: max(
            _tanimoto(
                arrays["morgan_binary"][by_id[molecule]], arrays["morgan_binary"][i]
            )
            for i in train_idx
        )
        for molecule in pred_order
    }
    for system in (MAPLIGHT,) if stage == "inner" else OUTER_SYSTEMS:
        for molecule, pred in zip(pred_order, predictions[system], strict=True):
            rows.append(
                {
                    "molecule_id": molecule,
                    "endpoint": endpoint,
                    "component_id": component[molecule],
                    "repeat": repeat,
                    "outer_fold": outer_fold,
                    "inner_fold": "" if inner_fold is None else inner_fold,
                    "scope": scope,
                    "system_id": system,
                    "prediction": format(float(pred), ".17g"),
                    "applicability_score": format(applicability[molecule], ".17g"),
                    "model_id": _model_id(
                        contract_sha,
                        system,
                        endpoint,
                        repeat,
                        outer_fold,
                        inner_fold,
                        scope,
                    ),
                    "feature_spec_id": FEATURE_SPECS[system],
                    "split_id": split,
                }
            )
    system_rank = {name: i for i, name in enumerate(OUTER_SYSTEMS)}
    rows.sort(
        key=lambda r: (
            system_rank[str(r["system_id"])],
            str(r["endpoint"]),
            int(str(r["repeat"])),
            int(str(r["outer_fold"])),
            -1 if r["inner_fold"] == "" else int(str(r["inner_fold"])),
            str(r["molecule_id"]),
        )
    )
    fragment = _csv_bytes(FRAGMENT_COLUMNS, rows)
    _require(
        not output_root.exists() and not output_root.is_symlink(), "cell output exists"
    )
    output_root.parent.mkdir(parents=True, exist_ok=True)
    stage_root = Path(
        tempfile.mkdtemp(prefix=".r3b-cell-", dir=str(output_root.parent))
    )
    try:
        (stage_root / "prediction_fragment.csv").write_bytes(fragment)
        cell_receipt = {
            "schema_version": (
                "cypshift.openadmet_cyp_2026.r3b_cell.v5"
                if contract_sha == V5_SHA256
                else "cypshift.openadmet_cyp_2026.r3b_cell.v1"
            ),
            "contract_sha256": contract_sha,
            "stage": stage,
            "cell_id": cell,
            "runner_source_sha256": runner_source_sha,
            "preflight_receipt_sha256": _sha256(preflight_receipt),
            "model_public_manifest_sha256": public_sha,
            "target_receipt": receipt,
            "feature_receipts": {"feature_manifest_sha256": feature_sha},
            "inner_selection_token_sha256": token_sha,
            "system_ids": list(OUTER_SYSTEMS if stage == "outer" else (MAPLIGHT,)),
            "resolved_catboost_parameters": params,
            "prediction_fragment": {
                "path": "prediction_fragment.csv",
                "sha256": _sha256_bytes(fragment),
                "bytes": len(fragment),
                "rows": len(rows),
                "columns": list(FRAGMENT_COLUMNS),
                "schema_version": "",
            },
            "counts": {
                "training_targets": len(train_order),
                "prediction_molecules": len(pred_order),
                "prediction_rows": len(rows),
                "model_fits": 2 if stage == "outer" else 1,
            },
            "accounting": {
                "target_files_opened": 1,
                "truth_files_opened": 0,
                "private_audit_files_opened": 0,
                "other_target_files_opened": 0,
                "feature_arrays_opened": 5,
                "score_files_opened": 0,
                "tdi_files_opened": 0,
                "blinded_test_files_opened": 0,
                "episode_or_anchor_files_opened": 0,
                "submission_files_opened": 0,
                "transductive_operations": 0,
            },
            "authority": dict(INHERITED_AUTHORITY),
        }
        (stage_root / "cell_receipt.json").write_bytes(_json_bytes(cell_receipt))
        _readonly_tree(stage_root)
        _promote_noreplace(stage_root, output_root)
    except Exception:
        if stage_root.exists():
            for p in stage_root.rglob("*"):
                p.chmod(0o644)
            stage_root.chmod(0o755)
            shutil.rmtree(stage_root)
        raise
    return output_root


def _run_cell(**kwargs: Any) -> Path:
    if "allow_synthetic" in kwargs:
        kwargs["synthetic"] = bool(kwargs.pop("allow_synthetic"))
    return run_cell(**kwargs)


def run_outer_cell(**kwargs: Any) -> Path:
    kwargs["stage"] = "outer"
    return run_cell(**kwargs)


def run_inner_cell(**kwargs: Any) -> Path:
    kwargs["stage"] = "inner"
    return run_cell(**kwargs)


run_model_cell = run_cell


def _freeze_outer(**kwargs: Any) -> Path:
    if "allow_synthetic" in kwargs:
        kwargs["synthetic"] = bool(kwargs.pop("allow_synthetic"))
    return cast(Path, freeze_outer(**kwargs))


def _freeze_inner(**kwargs: Any) -> Path:
    if "allow_synthetic" in kwargs:
        kwargs["synthetic"] = bool(kwargs.pop("allow_synthetic"))
    return cast(Path, freeze_inner(**kwargs))


freeze_outer_predictions = freeze_outer
freeze_inner_predictions = freeze_inner


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    cell = sub.add_parser("cell")
    cell.add_argument("--stage", choices=("outer", "inner"), required=True)
    cell.add_argument("--endpoint", choices=ENDPOINTS, required=True)
    cell.add_argument("--repeat", type=int, required=True)
    cell.add_argument("--outer-fold", type=int, required=True)
    cell.add_argument("--inner-fold", type=int)
    cell.add_argument("--feature-root", type=Path, required=True)
    cell.add_argument("--feature-manifest-sha256", required=True)
    cell.add_argument("--model-public-root", type=Path, required=True)
    cell.add_argument("--model-public-manifest-sha256", required=True)
    cell.add_argument("--preflight-receipt", type=Path, required=True)
    cell.add_argument("--output-root", type=Path, required=True)
    cell.add_argument("--inner-selection-token", type=Path)
    for name, stage in (("freeze-outer", "outer"), ("freeze-inner", "inner")):
        p = sub.add_parser(name)
        p.add_argument("--cell-root", type=Path, action="append", required=True)
        p.add_argument("--output-root", type=Path, required=True)
        p.add_argument("--model-public-root", type=Path, required=True)
        p.add_argument("--model-public-manifest-sha256", required=True)
        p.add_argument("--preflight-receipt", type=Path, required=True)
        p.add_argument("--feature-manifest-sha256", required=True)
        p.add_argument("--inner-selection-token", type=Path, required=stage == "inner")
    args = parser.parse_args()
    if args.command == "cell":
        run_cell(
            stage=args.stage,
            endpoint=args.endpoint,
            repeat=args.repeat,
            outer_fold=args.outer_fold,
            inner_fold=args.inner_fold,
            feature_root=args.feature_root,
            feature_manifest_sha256=args.feature_manifest_sha256,
            model_public_root=args.model_public_root,
            model_public_manifest_sha256=args.model_public_manifest_sha256,
            preflight_receipt=args.preflight_receipt,
            output_root=args.output_root,
            inner_selection_token=args.inner_selection_token,
        )
    elif args.command == "freeze-outer":
        freeze_outer(
            cell_roots=args.cell_root,
            output_root=args.output_root,
            model_public_root=args.model_public_root,
            model_public_manifest_sha256=args.model_public_manifest_sha256,
            preflight_receipt=args.preflight_receipt,
            feature_manifest_sha256=args.feature_manifest_sha256,
        )
    else:
        freeze_inner(
            cell_roots=args.cell_root,
            output_root=args.output_root,
            model_public_root=args.model_public_root,
            model_public_manifest_sha256=args.model_public_manifest_sha256,
            preflight_receipt=args.preflight_receipt,
            feature_manifest_sha256=args.feature_manifest_sha256,
            inner_selection_token=args.inner_selection_token,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

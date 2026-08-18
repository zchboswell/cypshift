"""R3B staged terminal publication and causal scoring state machine."""

from __future__ import annotations

import importlib.metadata
import platform
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, TypeVar, cast

from r3b_scoring_artifacts import (
    MAPLIGHT,
    PREFLIGHT_SOURCE_SHA256,
    PROJECTOR_SOURCE_SHA256,
    RESEARCH_UV_LOCK_SHA256,
    V5_SHA256,
    OuterStage,
    R3BScoringError,
    R3BStageFailure,
    R3BUnderpowered,
    _authority,
    _cell_runner_source_sha,
    _contracts,
    _forbidden,
    _freezer_source_sha,
    _is_sha,
    _json,
    _json_bytes,
    _load_freeze,
    _load_truth,
    _loads_unique,
    _read,
    _require,
    _sha,
    _truth_index,
    _verified,
)
from r3b_scoring_manifest import _scorer_bundle_sha, _terminal_files
from r3b_scoring_math import _outer_metrics, _q90_completion
from r3b_scoring_preflight import _validate_preflight
from r3b_scoring_publish import _private_stage, _publish


def _runtime_gate(
    synthetic: bool, expected_source_bundle_sha256: str | None = None
) -> None:
    observed_source_sha = _scorer_bundle_sha()
    _require(bool(observed_source_sha), "scorer source bundle unavailable")
    if not (synthetic and expected_source_bundle_sha256 is None):
        _require(
            _is_sha(expected_source_bundle_sha256),
            "scorer source receipt is required",
        )
        _require(
            expected_source_bundle_sha256 == observed_source_sha,
            "scorer source receipt differs",
        )
    if synthetic:
        return
    lock = Path(__file__).with_name("uv.lock")
    _require(
        lock.is_file() and not lock.is_symlink(), "research uv.lock is unavailable"
    )
    _require(
        _sha(lock.read_bytes()) == RESEARCH_UV_LOCK_SHA256,
        "research uv.lock receipt differs",
    )
    _require(
        platform.system() == "Linux"
        and platform.machine() == "x86_64"
        and platform.python_version() == "3.10.13",
        "scorer runtime differs",
    )
    try:
        numpy_version = importlib.metadata.version("numpy")
        catboost_version = importlib.metadata.version("catboost")
    except importlib.metadata.PackageNotFoundError as exc:
        raise R3BScoringError("scorer runtime packages differ") from exc
    _require(
        numpy_version == "1.25.2" and catboost_version == "1.2.1",
        "scorer runtime packages differ",
    )


_SOURCE_KEYS = (
    "projector",
    "preflight",
    "cell_runner",
    "freezer",
    "outer_scorer",
    "token_writer",
    "final_scorer",
    "terminal_writer",
)
_T = TypeVar("_T")


def _source_receipts(synthetic: bool) -> dict[str, str]:
    values = {key: "" for key in _SOURCE_KEYS}
    if not synthetic:
        values["projector"] = PROJECTOR_SOURCE_SHA256
        values["preflight"] = PREFLIGHT_SOURCE_SHA256
    return values


def _record_source(receipts: dict[str, str], stage: str) -> None:
    if stage == "preflight":
        receipts["preflight"] = PREFLIGHT_SOURCE_SHA256
    elif stage in {"outer_freeze", "inner_freeze"}:
        receipts["freezer"] = _freezer_source_sha()
        receipts["cell_runner"] = _cell_runner_source_sha()
    elif stage == "outer_score":
        receipts["outer_scorer"] = _scorer_bundle_sha()
    elif stage == "inner_token":
        receipts["token_writer"] = _scorer_bundle_sha()
    elif stage == "final_score":
        receipts["final_scorer"] = _scorer_bundle_sha()
    elif stage == "terminal_publish":
        receipts["terminal_writer"] = _scorer_bundle_sha()


def _record_contract_inputs(
    receipts: dict[str, str], contract: Mapping[str, Any]
) -> None:
    inputs = cast(Mapping[str, Any], contract["target_projection"]["inputs"])
    for key in ("direct_observations_sha256", "group_folds_sha256"):
        value = inputs.get(key)
        _require(isinstance(value, str) and len(value) == 64, f"{key} receipt differs")
        receipts[key] = cast(str, value)


def _stage_call(
    stage: str,
    operation: Callable[[], _T],
    verified: Mapping[str, str],
    source_receipts: Mapping[str, str],
    accounting: Mapping[str, int],
) -> _T:
    try:
        return operation()
    except (R3BUnderpowered, R3BStageFailure):
        raise
    except Exception as error:
        raise R3BStageFailure(
            str(error), stage, verified, source_receipts, accounting
        ) from error


def _validate_assessment(
    assessment: Mapping[str, Any],
    contract_sha: str,
    outcome: str,
    synthetic: bool,
) -> None:
    _require(
        set(assessment)
        == {
            "schema_version",
            "contract_sha256",
            "outer_freeze_manifest_sha256",
            "sealed_outer_truth_manifest_sha256",
            "cell_metrics_sha256",
            "bootstrap_summary_sha256",
            "endpoint_loss_checks_sha256",
            "influence_checks_sha256",
            "predesignated_system_id",
            "support_pass",
            "criteria",
            "counts",
            "outcome",
            "accounting",
            "authority",
        },
        "outer assessment fields differ",
    )
    _require(
        assessment.get("schema_version")
        == "cypshift.openadmet_cyp_2026.r3b_outer_assessment.v1"
        and assessment.get("contract_sha256") == contract_sha
        and assessment.get("predesignated_system_id") == MAPLIGHT
        and assessment.get("support_pass") is True
        and assessment.get("outcome") == outcome,
        "outer assessment differs",
    )
    _require(
        set(cast(Mapping[str, Any], assessment["criteria"]))
        == {
            "morgan_lower_positive",
            "median_lower_positive",
            "one_nn_lower_positive",
            "median_positive_fold_cells",
            "one_nn_positive_fold_cells",
            "endpoint_loss_pass",
            "influence_pass",
            "outer_predictions_complete",
        },
        "outer assessment criteria differ",
    )
    _require(
        set(cast(Mapping[str, Any], assessment["counts"]))
        == {
            "cell_metric_rows",
            "bootstrap_summary_rows",
            "endpoint_loss_rows",
            "influence_rows",
            "accepted_replicates",
            "attempts",
            "positive_median_fold_cells",
            "positive_one_nn_fold_cells",
        },
        "outer assessment counts differ",
    )
    _require(
        set(cast(Mapping[str, Any], assessment["accounting"]))
        == {
            "prediction_files_opened",
            "sealed_truth_files_opened",
            "target_files_opened",
            "tdi_files_opened",
            "blinded_test_rows_opened",
            "episode_or_anchor_files_opened",
            "submission_files_opened",
            "transductive_operations",
        },
        "outer assessment accounting differs",
    )
    _require(
        assessment["authority"]
        == _authority(
            _contracts(contract_sha)[0],
            "INHERITED_ONLY" if synthetic else "GLOBAL_NO_ADVANTAGE",
        ),
        "outer assessment authority differs",
    )


def _validated_private_receipts(
    root: Path,
    contract: Mapping[str, Any],
    contract_sha: str,
    synthetic: bool,
) -> dict[str, str]:
    private, _private_data = _json(
        root / "outer_verified_input_receipts.json",
        None,
        "outer verified receipts",
    )
    _require(
        set(private) == {"schema_version", "verified_input_receipts", "authority"}
        and private["schema_version"]
        == "cypshift.openadmet_cyp_2026.r3b_private_receipts.v1"
        and private["authority"] == _authority(contract, "INHERITED_ONLY"),
        "outer verified receipts differ",
    )
    carried = private["verified_input_receipts"]
    _require(isinstance(carried, Mapping), "outer verified receipts differ")
    carried_map = cast(Mapping[object, object], carried)
    _require(
        all(
            type(key) is str and type(value) is str
            for key, value in carried_map.items()
        ),
        "outer verified receipts differ",
    )
    result = cast(dict[str, str], dict(carried_map))
    _require(set(result) == set(_verified()), "outer verified receipts differ")
    for key, value in result.items():
        _require(
            type(value) is str
            and (
                value == ""
                or synthetic
                or (len(value) == 64 and value == value.lower())
            ),
            f"{key} receipt differs",
        )
    preflight_sha = result["preflight_receipt_sha256"]
    _require(bool(preflight_sha), "preflight receipt is unavailable")
    preflight, _preflight_data = _json(
        root / "preflight_receipt.json", preflight_sha, "preflight receipt"
    )
    _validate_preflight(preflight, contract, contract_sha, synthetic)
    _require(
        result["model_public_manifest_sha256"]
        == str(preflight["model_public_manifest_sha256"])
        and result["private_projection_audit_sha256"]
        == str(preflight["private_projection_audit_sha256"]),
        "preflight source receipts differ",
    )
    return result


def score_outer(
    *,
    outer_root: Path,
    sealed_root: Path,
    stage_root: Path,
    outer_manifest_sha256: str,
    sealed_manifest_sha256: str,
    expected_contract_sha256: str = V5_SHA256,
    preflight_receipt: Path | None = None,
    preflight_receipt_sha256: str | None = None,
    synthetic: bool = False,
    expected_source_bundle_sha256: str | None = None,
) -> OuterStage:
    """Verify and score outer predictions; emit an unpublished token on PASS."""
    verified = _verified()
    source_receipts = _source_receipts(synthetic)
    contract, _v3, contract_sha, parent_sha = _stage_call(
        "preflight",
        lambda: _contracts(expected_contract_sha256),
        verified,
        source_receipts,
        {},
    )
    _record_source(source_receipts, "preflight")
    _record_contract_inputs(verified, contract)
    _stage_call(
        "preflight",
        lambda: _runtime_gate(synthetic, expected_source_bundle_sha256),
        verified,
        source_receipts,
        {},
    )
    verified["parent_contract_sha256"] = parent_sha
    if preflight_receipt is None or preflight_receipt_sha256 is None:
        raise R3BStageFailure(
            "validated preflight receipt is required",
            "preflight",
            verified,
            source_receipts,
        )
    preflight, preflight_data = _stage_call(
        "preflight",
        lambda: _json(preflight_receipt, preflight_receipt_sha256, "preflight receipt"),
        verified,
        source_receipts,
        {},
    )
    _stage_call(
        "preflight",
        lambda: _validate_preflight(preflight, contract, contract_sha, synthetic),
        verified,
        source_receipts,
        {},
    )
    preflight_sha = _sha(preflight_data)
    verified["preflight_receipt_sha256"] = preflight_sha
    verified["model_public_manifest_sha256"] = str(
        preflight["model_public_manifest_sha256"]
    )
    verified["private_projection_audit_sha256"] = str(
        preflight["private_projection_audit_sha256"]
    )
    if preflight.get("passed") is not True:
        raise R3BUnderpowered(
            "preflight support failure", preflight_receipt, preflight_sha
        )
    accounting = {
        str(key): 0
        for key in cast(
            Mapping[str, Any], contract["terminal_objects"]["accounting_fields"]
        )
    }
    accounting["preflight_target_files_opened"] = 300
    _record_source(source_receipts, "outer_freeze")
    rows, _outer_manifest_data, outer_manifest_sha, outer_csv_sha = _stage_call(
        "outer_freeze",
        lambda: _load_freeze(
            outer_root, outer_manifest_sha256, "outer", contract_sha, synthetic
        ),
        verified,
        source_receipts,
        accounting,
    )
    accounting["outer_model_target_files_opened"] = 60
    outer_manifest = cast(
        dict[str, Any],
        _stage_call(
            "outer_freeze",
            lambda: _loads_unique(_outer_manifest_data, "outer freeze manifest"),
            verified,
            source_receipts,
            accounting,
        ),
    )
    preflight_model_public = verified["model_public_manifest_sha256"]

    def validate_outer_links() -> None:
        verified["model_public_manifest_sha256"] = str(
            outer_manifest.get("model_public_manifest_sha256", "")
        )
        verified["r3a_feature_manifest_sha256"] = str(
            outer_manifest.get("feature_manifest_sha256", "")
        )
        _require(
            outer_manifest.get("preflight_receipt_sha256")
            == verified["preflight_receipt_sha256"],
            "outer preflight receipt differs",
        )
        _require(
            outer_manifest.get("model_public_manifest_sha256")
            == preflight_model_public,
            "outer model-public receipt differs",
        )

    _stage_call(
        "outer_freeze",
        validate_outer_links,
        verified,
        source_receipts,
        accounting,
    )
    _record_source(source_receipts, "outer_score")
    truth_rows, _unused, _truth_manifest_data, truth_manifest_sha = _stage_call(
        "outer_score",
        lambda: _load_truth(
            sealed_root,
            sealed_manifest_sha256,
            contract_sha,
            parent_sha,
            False,
            synthetic,
        ),
        verified,
        source_receipts,
        accounting,
    )
    accounting["sealed_truth_files_opened"] = 1
    verified["sealed_truth_manifest_sha256"] = truth_manifest_sha
    truth = _truth_index(truth_rows, False)
    assessment, artifacts, outcome = _stage_call(
        "outer_score",
        lambda: _outer_metrics(rows, truth, synthetic),
        verified,
        source_receipts,
        accounting,
    )
    assessment["contract_sha256"] = contract_sha
    assessment["outer_freeze_manifest_sha256"] = outer_manifest_sha
    assessment["sealed_outer_truth_manifest_sha256"] = truth_manifest_sha
    receipt_names = {
        "global_cell_metrics.csv": "cell_metrics_sha256",
        "global_bootstrap_summary.csv": "bootstrap_summary_sha256",
        "global_endpoint_loss_checks.csv": "endpoint_loss_checks_sha256",
        "global_influence_checks.csv": "influence_checks_sha256",
    }
    for name, field in receipt_names.items():
        assessment[field] = _sha(artifacts[name])
    assessment["accounting"] = {
        "prediction_files_opened": 1,
        "sealed_truth_files_opened": 1,
        "target_files_opened": 0,
        "tdi_files_opened": 0,
        "blinded_test_rows_opened": 0,
        "episode_or_anchor_files_opened": 0,
        "submission_files_opened": 0,
        "transductive_operations": 0,
    }
    assessment["authority"] = _authority(
        contract, "INHERITED_ONLY" if synthetic else "GLOBAL_NO_ADVANTAGE"
    )
    assessment_data = _json_bytes(assessment)
    artifacts["global_outer_assessment.json"] = assessment_data
    token_data = b""
    if outcome == "PASS":
        token = {
            "schema_version": "cypshift.openadmet_cyp_2026.r3b_inner_selection_token.v1",
            "contract_sha256": contract_sha,
            "token_writer_source_sha256": _scorer_bundle_sha(),
            "outer_assessment_sha256": _sha(assessment_data),
            "selected_system_id": MAPLIGHT,
            "outer_outcome": "PASS",
            "authority": _authority(contract, "INHERITED_ONLY"),
        }
        token_data = _json_bytes(token)
        artifacts["inner_selection_token.json"] = token_data
    artifacts["global_oof_predictions.csv"] = _stage_call(
        "outer_score",
        lambda: _read(
            outer_root / "global_oof_predictions.csv",
            outer_csv_sha,
            "outer predictions",
        ),
        verified,
        source_receipts,
        accounting,
    )
    artifacts["global_oof_freeze_manifest.json"] = _stage_call(
        "outer_freeze",
        lambda: _read(
            outer_root / "global_oof_freeze_manifest.json",
            outer_manifest_sha,
            "outer freeze manifest",
        ),
        verified,
        source_receipts,
        accounting,
    )
    artifacts["outer_verified_input_receipts.json"] = _json_bytes(
        {
            "schema_version": "cypshift.openadmet_cyp_2026.r3b_private_receipts.v1",
            "verified_input_receipts": verified,
            "authority": _authority(contract, "INHERITED_ONLY"),
        }
    )
    if preflight_receipt is not None:
        artifacts["preflight_receipt.json"] = preflight_data
    _record_source(source_receipts, "terminal_publish")
    root = _stage_call(
        "terminal_publish",
        lambda: _private_stage(stage_root, artifacts),
        verified,
        source_receipts,
        accounting,
    )
    return OuterStage(
        root,
        "PASS" if outcome == "PASS" else "GLOBAL_NO_ADVANTAGE",
        _sha(assessment_data),
        _sha(token_data) if token_data else "",
        verified,
        dict(source_receipts),
        dict(accounting),
    )


def score_final(
    *,
    outer_stage_root: Path,
    inner_root: Path,
    sealed_root: Path,
    output_root: Path,
    inner_manifest_sha256: str,
    sealed_manifest_sha256: str,
    expected_contract_sha256: str = V5_SHA256,
    synthetic: bool = False,
    expected_source_bundle_sha256: str | None = None,
) -> Path:
    """Consume the prior PASS stage/token, then publish one terminal result."""
    _require(
        not output_root.exists() and not output_root.is_symlink(),
        "output destination exists",
    )
    verified = _verified()
    source_receipts = _source_receipts(synthetic)
    _record_source(source_receipts, "final_score")
    contract, _v3, contract_sha, parent_sha = _stage_call(
        "final_score",
        lambda: _contracts(expected_contract_sha256),
        verified,
        source_receipts,
        {},
    )
    _stage_call(
        "final_score",
        lambda: _runtime_gate(synthetic, expected_source_bundle_sha256),
        verified,
        source_receipts,
        {},
    )
    _record_contract_inputs(verified, contract)
    accounting = {
        str(key): 0
        for key in cast(
            Mapping[str, Any], contract["terminal_objects"]["accounting_fields"]
        )
    }
    accounting["preflight_target_files_opened"] = 300
    assessment, assessment_data = _stage_call(
        "inner_token",
        lambda: _json(
            outer_stage_root / "global_outer_assessment.json",
            None,
            "outer assessment",
        ),
        verified,
        source_receipts,
        accounting,
    )
    assessment_sha = _sha(assessment_data)
    _stage_call(
        "inner_token",
        lambda: _validate_assessment(assessment, contract_sha, "PASS", synthetic),
        verified,
        source_receipts,
        accounting,
    )
    _record_source(source_receipts, "inner_token")
    source_receipts["outer_scorer"] = _scorer_bundle_sha()
    token, token_data = _stage_call(
        "inner_token",
        lambda: _json(
            outer_stage_root / "inner_selection_token.json",
            None,
            "inner selection token",
        ),
        verified,
        source_receipts,
        accounting,
    )

    def validate_token() -> None:
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
        _require(
            token.get("schema_version")
            == "cypshift.openadmet_cyp_2026.r3b_inner_selection_token.v1"
            and token.get("contract_sha256") == contract_sha
            and token.get("outer_assessment_sha256") == assessment_sha
            and token.get("selected_system_id") == MAPLIGHT
            and token.get("outer_outcome") == "PASS"
            and token.get("authority") == _authority(contract, "INHERITED_ONLY")
            and not _forbidden(token),
            "inner selection token differs",
        )
        _require(
            isinstance(token.get("token_writer_source_sha256"), str)
            and (synthetic or len(str(token["token_writer_source_sha256"])) == 64),
            "inner token source receipt differs",
        )
        if not synthetic:
            _require(
                token["token_writer_source_sha256"] == _scorer_bundle_sha(),
                "inner token writer differs",
            )

    _stage_call("inner_token", validate_token, verified, source_receipts, accounting)
    _record_source(source_receipts, "outer_freeze")
    outer_rows, outer_manifest_data, _outer_manifest_sha, outer_csv_sha = _stage_call(
        "outer_freeze",
        lambda: _load_freeze(
            outer_stage_root,
            str(assessment.get("outer_freeze_manifest_sha256", "")),
            "outer",
            contract_sha,
            synthetic,
        ),
        verified,
        source_receipts,
        accounting,
    )
    accounting["outer_model_target_files_opened"] = 60
    outer_data = _stage_call(
        "outer_freeze",
        lambda: _read(
            outer_stage_root / "global_oof_predictions.csv",
            outer_csv_sha,
            "outer predictions",
        ),
        verified,
        source_receipts,
        accounting,
    )
    _record_source(source_receipts, "preflight")
    carried_receipts = _stage_call(
        "preflight",
        lambda: _validated_private_receipts(
            outer_stage_root, contract, contract_sha, synthetic
        ),
        verified,
        source_receipts,
        accounting,
    )
    for key, value in carried_receipts.items():
        if value:
            verified[key] = value
    _record_source(source_receipts, "inner_freeze")
    inner_rows, inner_manifest_data, inner_manifest_sha, inner_csv_sha = _stage_call(
        "inner_freeze",
        lambda: _load_freeze(
            inner_root, inner_manifest_sha256, "inner", contract_sha, synthetic
        ),
        verified,
        source_receipts,
        accounting,
    )
    accounting["inner_model_target_files_opened"] = 240
    outer_truth_rows, inner_truth_rows, _sealed_manifest_data, sealed_manifest_sha = (
        _stage_call(
            "final_score",
            lambda: _load_truth(
                sealed_root,
                sealed_manifest_sha256,
                contract_sha,
                parent_sha,
                True,
                synthetic,
            ),
            verified,
            source_receipts,
            accounting,
        )
    )
    accounting["sealed_truth_files_opened"] = 3
    outer_truth, inner_truth = (
        _truth_index(outer_truth_rows, False),
        _truth_index(inner_truth_rows, True),
    )
    _stage_call(
        "final_score",
        lambda: _require(
            sealed_manifest_sha == assessment.get("sealed_outer_truth_manifest_sha256"),
            "sealed outer truth receipt differs",
        ),
        verified,
        source_receipts,
        accounting,
    )
    completion, completion_counts = _stage_call(
        "final_score",
        lambda: _q90_completion(
            outer_rows, inner_rows, outer_truth, inner_truth, _sha(outer_data)
        ),
        verified,
        source_receipts,
        accounting,
    )
    outer_manifest = cast(
        dict[str, Any],
        _stage_call(
            "outer_freeze",
            lambda: _loads_unique(outer_manifest_data, "outer freeze manifest"),
            verified,
            source_receipts,
            accounting,
        ),
    )
    inner_manifest = cast(
        dict[str, Any],
        _stage_call(
            "inner_freeze",
            lambda: _loads_unique(inner_manifest_data, "inner freeze manifest"),
            verified,
            source_receipts,
            accounting,
        ),
    )

    def validate_inner_link() -> None:
        _require(
            carried_receipts["parent_contract_sha256"] == parent_sha
            and carried_receipts["preflight_receipt_sha256"]
            == outer_manifest.get("preflight_receipt_sha256")
            and carried_receipts["model_public_manifest_sha256"]
            == outer_manifest.get("model_public_manifest_sha256")
            and carried_receipts["r3a_feature_manifest_sha256"]
            == outer_manifest.get("feature_manifest_sha256")
            and carried_receipts["sealed_truth_manifest_sha256"] == sealed_manifest_sha,
            "private receipt accumulation differs",
        )
        _require(
            inner_manifest.get("preflight_receipt_sha256")
            == outer_manifest.get("preflight_receipt_sha256"),
            "inner preflight receipt differs",
        )
        _require(
            inner_manifest.get("model_public_manifest_sha256")
            == outer_manifest.get("model_public_manifest_sha256")
            and inner_manifest.get("feature_manifest_sha256")
            == outer_manifest.get("feature_manifest_sha256"),
            "inner source receipt differs",
        )
        _require(
            inner_manifest.get("inner_selection_token_sha256") == _sha(token_data),
            "inner token receipt differs",
        )

    _stage_call(
        "inner_freeze",
        validate_inner_link,
        verified,
        source_receipts,
        accounting,
    )
    verified.update(
        {
            "parent_contract_sha256": parent_sha,
            "sealed_truth_manifest_sha256": sealed_manifest_sha,
            "model_public_manifest_sha256": str(
                outer_manifest.get("model_public_manifest_sha256", "")
            ),
            "r3a_feature_manifest_sha256": str(
                outer_manifest.get("feature_manifest_sha256", "")
            ),
            "preflight_receipt_sha256": str(
                outer_manifest.get("preflight_receipt_sha256", "")
            ),
        }
    )
    for key, value in carried_receipts.items():
        if value:
            verified[key] = value
    inner_data = _stage_call(
        "final_score",
        lambda: _read(
            inner_root / "global_inner_oof_predictions.csv",
            inner_csv_sha,
            "inner predictions",
        ),
        verified,
        source_receipts,
        accounting,
    )
    source = {
        "global_oof_predictions.csv": outer_data,
        "global_oof_freeze_manifest.json": outer_manifest_data,
        "global_inner_oof_predictions.csv": inner_data,
        "global_inner_oof_freeze_manifest.json": inner_manifest_data,
    }
    score_names = {
        "global_cell_metrics.csv": "cell_metrics_sha256",
        "global_bootstrap_summary.csv": "bootstrap_summary_sha256",
        "global_endpoint_loss_checks.csv": "endpoint_loss_checks_sha256",
        "global_influence_checks.csv": "influence_checks_sha256",
        "global_outer_assessment.json": assessment_sha,
    }
    score: dict[str, bytes] = {}

    def load_score(name: str, receipt_name: str) -> bytes:
        data = _read(outer_stage_root / name, None, name)
        expected_receipt = (
            assessment_sha
            if name == "global_outer_assessment.json"
            else assessment.get(receipt_name)
        )
        _require(_sha(data) == expected_receipt, f"{name} receipt differs")
        return data

    def score_loader(name: str, receipt_name: str) -> Callable[[], bytes]:
        def load() -> bytes:
            return load_score(name, receipt_name)

        return load

    for name, receipt_name in score_names.items():
        data = _stage_call(
            "final_score",
            score_loader(name, receipt_name),
            verified,
            source_receipts,
            accounting,
        )
        score[name] = data
    score["inner_selection_token.json"] = token_data
    _record_source(source_receipts, "terminal_publish")
    files = _stage_call(
        "terminal_publish",
        lambda: _terminal_files(
            contract,
            contract_sha,
            parent_sha,
            "GLOBAL_EXPERT_FROZEN",
            verified,
            source,
            score,
            completion,
            completion_counts,
            synthetic,
            source_receipts,
        ),
        verified,
        source_receipts,
        accounting,
    )
    return cast(
        Path,
        _stage_call(
            "terminal_publish",
            lambda: _publish(output_root, files),
            verified,
            source_receipts,
            accounting,
        ),
    )


def publish_no_advantage(
    *,
    outer_stage_root: Path,
    output_root: Path,
    expected_contract_sha256: str = V5_SHA256,
    synthetic: bool = False,
    source_receipts: Mapping[str, str] | None = None,
    expected_source_bundle_sha256: str | None = None,
) -> Path:
    """Promote the outer evidence after a clean fixed-MapLight failure."""
    _require(
        not output_root.exists() and not output_root.is_symlink(),
        "output destination exists",
    )
    contract, _v3, contract_sha, parent_sha = _contracts(expected_contract_sha256)
    _runtime_gate(synthetic, expected_source_bundle_sha256)
    assessment, assessment_data = _json(
        outer_stage_root / "global_outer_assessment.json", None, "outer assessment"
    )
    _validate_assessment(assessment, contract_sha, "NO_ADVANTAGE", synthetic)
    outer_manifest_sha = str(assessment.get("outer_freeze_manifest_sha256", ""))
    rows, manifest_data, manifest_sha, csv_sha = _load_freeze(
        outer_stage_root, outer_manifest_sha, "outer", contract_sha, synthetic
    )
    del rows
    _require(
        manifest_sha == outer_manifest_sha,
        "outer freeze receipt differs",
    )
    prediction_data = _read(
        outer_stage_root / "global_oof_predictions.csv", csv_sha, "outer predictions"
    )
    artifact_names = {
        "global_cell_metrics.csv": "cell_metrics_sha256",
        "global_bootstrap_summary.csv": "bootstrap_summary_sha256",
        "global_endpoint_loss_checks.csv": "endpoint_loss_checks_sha256",
        "global_influence_checks.csv": "influence_checks_sha256",
    }
    score = {
        name: _read(outer_stage_root / name, str(assessment.get(receipt)), name)
        for name, receipt in artifact_names.items()
    }
    score["global_outer_assessment.json"] = assessment_data
    manifest = cast(
        dict[str, Any], _loads_unique(manifest_data, "outer freeze manifest")
    )
    carried_receipts = _validated_private_receipts(
        outer_stage_root, contract, contract_sha, synthetic
    )
    if source_receipts is None:
        source_receipts = _source_receipts(synthetic)
        _record_source(source_receipts, "outer_freeze")
        _record_source(source_receipts, "outer_score")
        _record_source(source_receipts, "terminal_publish")
    _require(
        carried_receipts["parent_contract_sha256"] == parent_sha
        and carried_receipts["preflight_receipt_sha256"]
        == manifest.get("preflight_receipt_sha256")
        and carried_receipts["model_public_manifest_sha256"]
        == manifest.get("model_public_manifest_sha256")
        and carried_receipts["r3a_feature_manifest_sha256"]
        == manifest.get("feature_manifest_sha256")
        and carried_receipts["sealed_truth_manifest_sha256"]
        == assessment.get("sealed_outer_truth_manifest_sha256"),
        "private receipt accumulation differs",
    )
    verified = _verified()
    verified.update(
        {
            "parent_contract_sha256": parent_sha,
            "model_public_manifest_sha256": str(
                manifest.get("model_public_manifest_sha256", "")
            ),
            "r3a_feature_manifest_sha256": str(
                manifest.get("feature_manifest_sha256", "")
            ),
            "preflight_receipt_sha256": str(
                manifest.get("preflight_receipt_sha256", "")
            ),
            "sealed_truth_manifest_sha256": str(
                assessment.get("sealed_outer_truth_manifest_sha256", "")
            ),
        }
    )
    for key, value in carried_receipts.items():
        if value:
            verified[key] = value
    source = {
        "global_oof_predictions.csv": prediction_data,
        "global_oof_freeze_manifest.json": manifest_data,
    }
    files = _terminal_files(
        contract,
        contract_sha,
        parent_sha,
        "GLOBAL_NO_ADVANTAGE",
        verified,
        source,
        score,
        {},
        {
            "outer_rows": 0,
            "final_rows": 0,
            "measured_point": 0,
            "global_oof_completed": 0,
            "unavailable": 0,
        },
        synthetic,
        source_receipts,
    )
    return cast(Path, _publish(output_root, files))


def publish_failure(
    *,
    output_root: Path,
    error: Exception,
    stage: str,
    verified: Mapping[str, str] | None = None,
    source_receipts: Mapping[str, str] | None = None,
    accounting: Mapping[str, int] | None = None,
    expected_contract_sha256: str = V5_SHA256,
) -> Path:
    """Publish exactly one failure receipt when a clean stage cannot continue."""
    _require(
        stage
        in {
            "projection",
            "preflight",
            "outer_model",
            "outer_freeze",
            "outer_score",
            "inner_token",
            "inner_model",
            "inner_freeze",
            "final_score",
            "terminal_publish",
        },
        "failure stage differs",
    )
    contract, _v3, contract_sha, parent_sha = _contracts(expected_contract_sha256)
    fields = cast(Mapping[str, Any], contract["terminal_objects"]["accounting_fields"])
    receipt_values = _verified()
    receipt_values["parent_contract_sha256"] = parent_sha
    for key, value in (verified or {}).items():
        if key in receipt_values and value:
            receipt_values[key] = value
    source_values = {key: "" for key in _SOURCE_KEYS}
    for key, value in (source_receipts or {}).items():
        if key in source_values and value:
            source_values[key] = value
    terminal_writer = _scorer_bundle_sha()
    _require(bool(terminal_writer), "terminal writer source unavailable")
    source_values["terminal_writer"] = terminal_writer
    accounting_values = {key: 0 for key in fields}
    for acct_key, acct_value in (accounting or {}).items():
        if (
            acct_key in accounting_values
            and type(acct_value) is int
            and acct_value >= 0
        ):
            accounting_values[acct_key] = acct_value
    receipt = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3b_failure.v1",
        "contract_sha256": contract_sha,
        "parent_contract_sha256": parent_sha,
        "verified_input_receipts": receipt_values,
        "implementation_source_receipts": source_values,
        "stage": stage,
        "error_class": type(error).__name__,
        "failed_receipt_or_invariant": str(error),
        "partial_outputs_published": False,
        "accounting": accounting_values,
        "authority": _authority(contract, "INHERITED_ONLY"),
    }
    _require(
        set(receipt)
        == {
            "schema_version",
            "contract_sha256",
            "parent_contract_sha256",
            "verified_input_receipts",
            "implementation_source_receipts",
            "stage",
            "error_class",
            "failed_receipt_or_invariant",
            "partial_outputs_published",
            "accounting",
            "authority",
        },
        "failure receipt fields differ",
    )
    return cast(
        Path, _publish(output_root, {"failure_receipt.json": _json_bytes(receipt)})
    )


def publish_underpowered(
    *,
    output_root: Path,
    preflight_receipt: Path,
    preflight_receipt_sha256: str,
    expected_contract_sha256: str = V5_SHA256,
    synthetic: bool = False,
    expected_source_bundle_sha256: str | None = None,
) -> Path:
    """Publish only the two exact clean-preflight sentinel files."""
    contract, _v3, contract_sha, parent_sha = _contracts(expected_contract_sha256)
    _runtime_gate(synthetic, expected_source_bundle_sha256)
    preflight, preflight_data = _json(
        preflight_receipt, preflight_receipt_sha256, "preflight receipt"
    )
    _validate_preflight(preflight, contract, contract_sha, synthetic)
    _require(preflight.get("passed") is False, "underpowered preflight passed")
    receipts = _verified()
    receipts["parent_contract_sha256"] = parent_sha
    _record_contract_inputs(receipts, contract)
    receipts["preflight_receipt_sha256"] = _sha(preflight_data)
    receipts["model_public_manifest_sha256"] = str(
        preflight["model_public_manifest_sha256"]
    )
    receipts["private_projection_audit_sha256"] = str(
        preflight["private_projection_audit_sha256"]
    )
    source_receipts = _source_receipts(synthetic)
    _record_source(source_receipts, "terminal_publish")
    files = _terminal_files(
        contract,
        contract_sha,
        parent_sha,
        "GLOBAL_UNDERPOWERED",
        receipts,
        {},
        {},
        {},
        {
            "outer_rows": 0,
            "final_rows": 0,
            "measured_point": 0,
            "global_oof_completed": 0,
            "unavailable": 0,
        },
        synthetic,
        source_receipts,
    )
    return cast(Path, _publish(output_root, files))


def run_outer(
    *,
    outer_root: Path,
    sealed_root: Path,
    output_root: Path,
    outer_manifest_sha256: str,
    sealed_manifest_sha256: str,
    stage_root: Path,
    expected_contract_sha256: str = V5_SHA256,
    preflight_receipt: Path | None = None,
    preflight_receipt_sha256: str | None = None,
    synthetic: bool = False,
    expected_source_bundle_sha256: str | None = None,
) -> Path:
    """Run the outer stage and publish only outcomes known without inner fits."""
    _require(
        not output_root.exists() and not output_root.is_symlink(),
        "output destination exists",
    )
    failed_stage = "outer_score"
    try:
        stage = score_outer(
            outer_root=outer_root,
            sealed_root=sealed_root,
            stage_root=stage_root,
            outer_manifest_sha256=outer_manifest_sha256,
            sealed_manifest_sha256=sealed_manifest_sha256,
            expected_contract_sha256=expected_contract_sha256,
            preflight_receipt=preflight_receipt,
            preflight_receipt_sha256=preflight_receipt_sha256,
            synthetic=synthetic,
            expected_source_bundle_sha256=expected_source_bundle_sha256,
        )
        if stage.status == "GLOBAL_NO_ADVANTAGE":
            source_receipts = dict(stage.source_receipts)
            _record_source(source_receipts, "terminal_publish")
            return _stage_call(
                "terminal_publish",
                lambda: publish_no_advantage(
                    outer_stage_root=stage.root,
                    output_root=output_root,
                    expected_contract_sha256=expected_contract_sha256,
                    synthetic=synthetic,
                    source_receipts=source_receipts,
                    expected_source_bundle_sha256=expected_source_bundle_sha256,
                ),
                stage.verified_receipts,
                source_receipts,
                stage.accounting,
            )
        return stage.root
    except R3BUnderpowered as error:
        return publish_underpowered(
            output_root=output_root,
            preflight_receipt=error.preflight_receipt,
            preflight_receipt_sha256=error.preflight_receipt_sha256,
            expected_contract_sha256=expected_contract_sha256,
            synthetic=synthetic,
            expected_source_bundle_sha256=expected_source_bundle_sha256,
        )
    except Exception as error:
        return publish_failure(
            output_root=output_root,
            error=error,
            stage=error.stage if isinstance(error, R3BStageFailure) else failed_stage,
            verified=(
                error.verified_receipts if isinstance(error, R3BStageFailure) else None
            ),
            source_receipts=(
                error.source_receipts if isinstance(error, R3BStageFailure) else None
            ),
            accounting=(
                error.accounting if isinstance(error, R3BStageFailure) else None
            ),
            expected_contract_sha256=expected_contract_sha256,
        )


def run_final(
    *,
    outer_stage_root: Path,
    inner_root: Path,
    sealed_root: Path,
    output_root: Path,
    inner_manifest_sha256: str,
    sealed_manifest_sha256: str,
    expected_contract_sha256: str = V5_SHA256,
    synthetic: bool = False,
    expected_source_bundle_sha256: str | None = None,
) -> Path:
    """Consume the causal outer token and publish success or a failure receipt."""
    try:
        return score_final(
            outer_stage_root=outer_stage_root,
            inner_root=inner_root,
            sealed_root=sealed_root,
            output_root=output_root,
            inner_manifest_sha256=inner_manifest_sha256,
            sealed_manifest_sha256=sealed_manifest_sha256,
            expected_contract_sha256=expected_contract_sha256,
            synthetic=synthetic,
            expected_source_bundle_sha256=expected_source_bundle_sha256,
        )
    except Exception as error:
        return publish_failure(
            output_root=output_root,
            error=error,
            stage=error.stage if isinstance(error, R3BStageFailure) else "final_score",
            verified=(
                error.verified_receipts if isinstance(error, R3BStageFailure) else None
            ),
            source_receipts=(
                error.source_receipts if isinstance(error, R3BStageFailure) else None
            ),
            accounting=(
                error.accounting if isinstance(error, R3BStageFailure) else None
            ),
            expected_contract_sha256=expected_contract_sha256,
        )

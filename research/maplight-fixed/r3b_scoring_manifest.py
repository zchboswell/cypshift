"""Receipt-bound terminal manifest construction for R3B."""

from __future__ import annotations

import csv
import io
import platform
import resource
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import numpy as np
from r3b_scoring_artifacts import (
    MAPLIGHT,
    PREFLIGHT_SOURCE_SHA256,
    PROJECTOR_SOURCE_SHA256,
    SYSTEMS,
    _authority,
    _cell_runner_source_sha,
    _freezer_source_sha,
    _is_sha,
    _json_bytes,
    _loads_unique,
    _require,
    _sha,
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
_VERIFIED_KEYS = (
    "parent_contract_sha256",
    "direct_observations_sha256",
    "group_folds_sha256",
    "r3a_feature_manifest_sha256",
    "model_public_manifest_sha256",
    "sealed_truth_manifest_sha256",
    "private_projection_audit_sha256",
    "preflight_receipt_sha256",
)
_DIRECT_OBSERVATIONS_SHA256 = (
    "00b1ac95cc73dda2699f2f05bc33200d1119a197d7a92ae900cde78d722f00b7"
)
_GROUP_FOLDS_SHA256 = "91678d68b2f9ac3913f6b679dd284f82ba2a040d803de83655bf89906f31f774"


def _validate_verified_receipts(
    values: Mapping[str, str], *, status: str, synthetic: bool
) -> dict[str, str]:
    _require(tuple(values) == _VERIFIED_KEYS, "verified input receipt order differs")
    result = dict(values)
    for key, value in result.items():
        _require(
            isinstance(value, str) and (value == "" or _is_sha(value)),
            f"{key} input receipt differs",
        )
    if synthetic:
        return result
    _require(
        result["direct_observations_sha256"] == _DIRECT_OBSERVATIONS_SHA256
        and result["group_folds_sha256"] == _GROUP_FOLDS_SHA256,
        "frozen v3 input receipt provenance differs",
    )
    required = {
        "parent_contract_sha256",
        "direct_observations_sha256",
        "group_folds_sha256",
    }
    if status != "GLOBAL_UNDERPOWERED":
        required.update(
            {
                "r3a_feature_manifest_sha256",
                "model_public_manifest_sha256",
                "sealed_truth_manifest_sha256",
                "private_projection_audit_sha256",
                "preflight_receipt_sha256",
            }
        )
    _require(all(result[key] for key in required), "verified input receipt missing")
    return result


def _validate_source_receipts(
    values: Mapping[str, str], *, status: str, synthetic: bool
) -> dict[str, str]:
    _require(
        tuple(values) == _SOURCE_KEYS, "implementation source receipt order differs"
    )
    result = dict(values)
    for key, value in result.items():
        _require(
            isinstance(value, str) and (value == "" or _is_sha(value)),
            f"{key} source receipt differs",
        )
    if synthetic:
        return result
    scorer_sha = _scorer_bundle_sha()
    _require(
        result["projector"] == PROJECTOR_SOURCE_SHA256
        and result["preflight"] == PREFLIGHT_SOURCE_SHA256
        and result["terminal_writer"] == scorer_sha,
        "accepted source receipt provenance differs",
    )
    required = {"projector", "preflight", "terminal_writer"}
    if status != "GLOBAL_UNDERPOWERED":
        required.update(("cell_runner", "freezer", "outer_scorer"))
    if status == "GLOBAL_EXPERT_FROZEN":
        required.update(("token_writer", "final_scorer"))
    _require(
        all(result[key] for key in required), "implementation source receipt missing"
    )
    if status != "GLOBAL_UNDERPOWERED":
        _require(
            result["cell_runner"] == _cell_runner_source_sha()
            and result["freezer"] == _freezer_source_sha()
            and result["outer_scorer"] == scorer_sha,
            "accepted model source receipt provenance differs",
        )
    if status == "GLOBAL_EXPERT_FROZEN":
        _require(
            result["token_writer"] == scorer_sha
            and result["final_scorer"] == scorer_sha,
            "accepted final source receipt provenance differs",
        )
    return result


def _bundle_sha(paths: tuple[str, ...]) -> str:
    root = Path(__file__).resolve().parents[2]
    entries: list[str] = []
    for relative in paths:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            return ""
        entries.append(f"{relative}|{_sha(path.read_bytes())}")
    material = "\n".join(sorted(entries)) + "\n"
    return _sha(material.encode("utf-8"))


SCORER_SOURCE_BUNDLE = (
    "research/maplight-fixed/run_r3b_scoring.py",
    "research/maplight-fixed/r3b_scoring_artifacts.py",
    "research/maplight-fixed/r3b_scoring_math.py",
    "research/maplight-fixed/r3b_scoring_manifest.py",
    "research/maplight-fixed/r3b_scoring_preflight.py",
    "research/maplight-fixed/r3b_scoring_publish.py",
    "research/maplight-fixed/r3b_scoring_terminal.py",
)


def _scorer_bundle_sha() -> str:
    return _bundle_sha(SCORER_SOURCE_BUNDLE)


_PROCESS_START = time.monotonic()


def _output_receipts(files: Mapping[str, bytes]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for name, data in sorted(files.items()):
        if name.endswith(".csv"):
            stream = io.StringIO(data.decode("utf-8"))
            reader = csv.reader(stream)
            columns = next(reader)
            rows = list(reader)
            schema = ""
        else:
            columns, rows = [], []
            parsed = _loads_unique(data, f"output {name}")
            schema = (
                str(parsed.get("schema_version", ""))
                if isinstance(parsed, dict)
                else ""
            )
        result[name] = {
            "path": name,
            "sha256": _sha(data),
            "bytes": len(data),
            "rows": len(rows),
            "columns": columns,
            "schema_version": schema,
        }
    return result


def _terminal_files(
    contract: Mapping[str, Any],
    contract_sha: str,
    parent_sha: str,
    status: str,
    verified: Mapping[str, str],
    source: Mapping[str, bytes],
    score: Mapping[str, bytes],
    completion: Mapping[str, bytes],
    completion_counts: Mapping[str, int],
    synthetic: bool,
    implementation_source_receipts: Mapping[str, str] | None = None,
) -> dict[str, bytes]:
    verified = _validate_verified_receipts(verified, status=status, synthetic=synthetic)
    files = dict(source)
    files.update(score)
    files.update(completion)
    if status == "GLOBAL_NO_ADVANTAGE":
        for name in (
            "inner_selection_token.json",
            "global_inner_oof_predictions.csv",
            "global_inner_oof_freeze_manifest.json",
            "global_uncertainty_calibration.csv",
            "parent_state_completion_outer_training.csv",
            "parent_state_completion_final.csv",
        ):
            files.pop(name, None)
    counts = cast(dict[str, Any], contract["terminal_objects"]["status_counts"][status])
    authority_status = (
        "INHERITED_ONLY" if synthetic or status == "GLOBAL_UNDERPOWERED" else status
    )
    uncertainty = {"contexts": 0, "within_frozen_range": 0, "diagnostic_only": 0}
    calibration = completion.get("global_uncertainty_calibration.csv")
    if calibration is not None:
        calibration_rows = csv.DictReader(io.StringIO(calibration.decode("utf-8")))
        statuses = [str(row.get("status", "")) for row in calibration_rows]
        uncertainty = {
            "contexts": len(statuses),
            "within_frozen_range": statuses.count("UNCERTAINTY_WITHIN_FROZEN_RANGE"),
            "diagnostic_only": statuses.count("UNCERTAINTY_DIAGNOSTIC_ONLY"),
        }
    if status == "GLOBAL_EXPERT_FROZEN":
        _require(
            uncertainty["contexts"] == 60
            and uncertainty["within_frozen_range"] + uncertainty["diagnostic_only"]
            == 60,
            "expert uncertainty counts differ",
        )
    else:
        _require(
            uncertainty
            == {"contexts": 0, "within_frozen_range": 0, "diagnostic_only": 0},
            "terminal uncertainty counts differ",
        )
    accounting = dict(
        cast(
            Mapping[str, Any], contract["terminal_objects"]["status_accounting"][status]
        )
    )
    accounting["preflight_target_files_opened"] = 300
    _require(
        set(completion_counts)
        == {
            "outer_rows",
            "final_rows",
            "measured_point",
            "global_oof_completed",
            "unavailable",
        },
        "completion count fields differ",
    )
    _require(
        all(type(value) is int and value >= 0 for value in completion_counts.values()),
        "completion count values differ",
    )
    if not synthetic:
        if status == "GLOBAL_EXPERT_FROZEN":
            _require(
                dict(completion_counts)
                == {
                    "outer_rows": 235440,
                    "final_rows": 19620,
                    "measured_point": 84825,
                    "global_oof_completed": 170235,
                    "unavailable": 0,
                },
                "expert completion counts differ",
            )
        else:
            _require(
                dict(completion_counts)
                == {
                    "outer_rows": 0,
                    "final_rows": 0,
                    "measured_point": 0,
                    "global_oof_completed": 0,
                    "unavailable": 0,
                },
                "terminal completion counts differ",
            )
    result = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3b_global_result.v1",
        "contract_sha256": contract_sha,
        "parent_contract_sha256": parent_sha,
        "predesignated_system_id": MAPLIGHT,
        "verified_input_receipts": dict(verified),
        "receipts": {
            "outer_freeze_manifest_sha256": _sha(
                files["global_oof_freeze_manifest.json"]
            )
            if "global_oof_freeze_manifest.json" in files
            else "",
            "outer_assessment_sha256": _sha(files["global_outer_assessment.json"])
            if "global_outer_assessment.json" in files
            else "",
            "inner_selection_token_sha256": _sha(files["inner_selection_token.json"])
            if "inner_selection_token.json" in files
            else "",
            "inner_freeze_manifest_sha256": _sha(
                files["global_inner_oof_freeze_manifest.json"]
            )
            if "global_inner_oof_freeze_manifest.json" in files
            else "",
        },
        "criteria": {
            "preflight_pass": status != "GLOBAL_UNDERPOWERED",
            "outer_pass": status == "GLOBAL_EXPERT_FROZEN",
            "inner_complete": status == "GLOBAL_EXPERT_FROZEN",
            "completion_complete": status == "GLOBAL_EXPERT_FROZEN",
        },
        "counts": counts,
        "completion_counts": dict(completion_counts),
        "uncertainty_counts": uncertainty,
        "status": status,
        "accounting": accounting,
        "authority": _authority(contract, authority_status),
    }
    files["global_result.json"] = _json_bytes(result)
    _require(
        set(result)
        == {
            "schema_version",
            "contract_sha256",
            "parent_contract_sha256",
            "predesignated_system_id",
            "verified_input_receipts",
            "receipts",
            "criteria",
            "counts",
            "completion_counts",
            "uncertainty_counts",
            "status",
            "accounting",
            "authority",
        },
        "global result fields differ",
    )
    if implementation_source_receipts is None:
        implementation = {key: "" for key in _SOURCE_KEYS}
        scorer_bundle_sha = _scorer_bundle_sha()
        implementation["preflight"] = scorer_bundle_sha
        implementation["terminal_writer"] = scorer_bundle_sha
    else:
        implementation = _validate_source_receipts(
            implementation_source_receipts, status=status, synthetic=synthetic
        )
    accepted = cast(dict[str, Any], contract["accepted_r3a_feature_root"])
    try:
        catboost_module = __import__("catboost")
        catboost_version = str(getattr(catboost_module, "__version__", ""))
    except ImportError:
        catboost_version = ""
    observed_runtime = {
        "platform": f"{platform.system()} {platform.machine()} CPU",
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "catboost_version": catboost_version,
        "cpu_only": True,
        "max_threads": 16,
        "gpu_fits": 0,
        "runtime_seconds": round(max(0.0, time.monotonic() - _PROCESS_START), 6),
        "peak_rss_gib": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**2), 6
        ),
    }
    _require(
        set(observed_runtime)
        == {
            "platform",
            "python_version",
            "numpy_version",
            "catboost_version",
            "cpu_only",
            "max_threads",
            "gpu_fits",
            "runtime_seconds",
            "peak_rss_gib",
        },
        "runtime fields differ",
    )
    _require(
        cast(float, observed_runtime["runtime_seconds"]) >= 0
        and cast(float, observed_runtime["peak_rss_gib"]) >= 0,
        "runtime measurements differ",
    )
    if not synthetic:
        _require(
            observed_runtime["platform"] == "Linux x86_64 CPU"
            and observed_runtime["python_version"] == "3.10.13"
            and observed_runtime["numpy_version"] == "1.25.2"
            and observed_runtime["catboost_version"] == "1.2.1",
            "runtime receipt differs",
        )
    resolved: dict[str, dict[str, Any]] = {}
    for manifest_name in (
        "global_oof_freeze_manifest.json",
        "global_inner_oof_freeze_manifest.json",
    ):
        if manifest_name in source:
            manifest_value = _loads_unique(source[manifest_name], manifest_name)
            _require(isinstance(manifest_value, Mapping), "freeze manifest differs")
            manifest_mapping = cast(Mapping[str, Any], manifest_value)
            parameters = manifest_mapping.get("resolved_catboost_parameters")
            _require(isinstance(parameters, list), "resolved parameters differ")
            for parameter in cast(list[object], parameters):
                _require(isinstance(parameter, Mapping), "resolved parameter differs")
                record = cast(Mapping[str, Any], parameter)
                _require(
                    set(record)
                    == {
                        "system_id",
                        "canonical_get_all_params_json",
                        "canonical_get_all_params_sha256",
                    },
                    "resolved parameter fields differ",
                )
                system_id = str(record["system_id"])
                canonical = record["canonical_get_all_params_json"]
                digest = record["canonical_get_all_params_sha256"]
                _require(isinstance(canonical, Mapping), "resolved parameters differ")
                _require(
                    isinstance(digest, str) and _sha(_json_bytes(canonical)) == digest,
                    "resolved parameter hash differs",
                )
                normalized = dict(record)
                if system_id in resolved:
                    _require(
                        resolved[system_id] == normalized, "parameter receipt differs"
                    )
                resolved[system_id] = normalized
    expected_systems = (
        set()
        if status == "GLOBAL_UNDERPOWERED"
        else {
            SYSTEMS[1],
            MAPLIGHT,
        }
    )
    _require(set(resolved) == expected_systems, "terminal parameter set differs")
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3b_terminal_manifest.v1",
        "contract_sha256": contract_sha,
        "parent_contract_sha256": parent_sha,
        "verified_input_receipts": dict(verified),
        "implementation_source_receipts": implementation,
        "runtime": observed_runtime,
        "accepted_r3a_receipts": {
            "canonical_build": accepted["canonical_build"],
            "manifest_schema_version": accepted["manifest_schema_version"],
            "manifest_sha256": accepted["manifest_sha256"],
            "feature_rows_sha256": accepted["feature_rows"]["sha256"],
            "array_sha256": accepted["arrays"],
        },
        "output_receipts": _output_receipts(
            {name: data for name, data in files.items() if name != "manifest.json"}
        ),
        "resolved_catboost_parameters": resolved,
        "seeds": {
            "fold_seeds": [20260810, 20260811, 20260812],
            "catboost_random_seed": 1,
            "bootstrap_seed": 20260819,
        },
        "counts": counts,
        "completion_counts": dict(completion_counts),
        "uncertainty_counts": uncertainty,
        "status": status,
        "accounting": accounting,
        "authority": _authority(contract, authority_status),
    }
    _require(
        set(manifest)
        == {
            "schema_version",
            "contract_sha256",
            "parent_contract_sha256",
            "verified_input_receipts",
            "implementation_source_receipts",
            "runtime",
            "accepted_r3a_receipts",
            "output_receipts",
            "resolved_catboost_parameters",
            "seeds",
            "counts",
            "completion_counts",
            "uncertainty_counts",
            "status",
            "accounting",
            "authority",
        },
        "terminal manifest fields differ",
    )
    files["manifest.json"] = _json_bytes(manifest)
    publication = cast(Mapping[str, Any], contract["publication"])
    terminal_sets = cast(Mapping[str, Any], publication["terminal_output_sets"])
    expected = set(cast(list[str], terminal_sets[status]))
    _require(set(files) == expected, "terminal output set differs")
    return files

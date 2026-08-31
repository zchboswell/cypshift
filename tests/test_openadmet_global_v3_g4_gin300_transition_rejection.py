from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn, cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
RECORD = (
    ROOT
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "global_v3_g4_gin300_transition_rejection.json"
)

RECORD_SHA256 = "10a7f783d73ae60c6da479ffbd8cd3e3443b3f8dace88e177fd9c17c44e1331c"
RECORD_SIZE_BYTES = 14_871
RECORD_LINES_LF = 276
D148_COMMIT = "f0f3b6f9380eebef0b03d87f29eb659ffc84f8d5"

TOP_LEVEL_KEYS = (
    "schema_version",
    "recorded_at_utc",
    "status",
    "gate",
    "record_id",
    "experiment_id",
    "decision",
    "terminal",
    "immutable_d148_parent",
    "rejected_transition_evidence",
    "rejected_evidence_publication_boundary",
    "ordinary_public_validation_accounting",
    "fixed_g4_preclaim_accounting",
    "terminal_effect",
    "baseline_pivot",
    "d149_terminal_package",
    "invalidation",
    "next_gate",
)

D148_FILES = (
    {
        "path": (
            "benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_capability_contract.json"
        ),
        "sha256": "df8796575c3d6093dd4038f4268417a979b8edca14245a7acff26e3db18eaa44",
        "size_bytes": 184_100,
        "lines_lf": 1_687,
    },
    {
        "path": (
            "benchmarks/openadmet_cyp_2026/"
            "global_v3_g4_gin300_linux_x86_64_runtime_manifest.json"
        ),
        "sha256": "67b58fc5eb9d1d3c0652bad9fa85eb1e688ed4bfb93d9ee107cad4db3e0ace01",
        "size_bytes": 166_425,
        "lines_lf": 4_008,
    },
    {
        "path": (
            "benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_third_party_notices.md"
        ),
        "sha256": "b76b026a7ed61c0c33cc9f78d66ca235e01e9d2c504126238e0f6e0f58e18deb",
        "size_bytes": 12_456,
        "lines_lf": 241,
    },
    {
        "path": "tests/test_openadmet_global_v3_g4_gin300_capability_contract.py",
        "sha256": "d9318267ff607703b9d957fc2fa13b79af61740b486471ab0556c06f3205bb12",
        "size_bytes": 97_426,
        "lines_lf": 2_509,
    },
)

REJECTED_TRANSITION_EVIDENCE = (
    {
        "role": "transition_contract_candidate",
        "sha256": "2c11b90d08038a05efd01bd40cb92ac79bc74544cc67807d2dd9b09111fa94af",
        "size_bytes": 72_296,
        "lines_lf": 582,
        "blockers": [
            (
                "Approved ordinary-public-root-project CI created an ephemeral project "
                "wheel, temporary venv, public fixture roots, train/predict/report "
                "outputs, and 42 explicit public predictions, while this candidate's "
                "unscoped accounting asserted zero runtime, wheel, scientific-package, "
                "root, and prediction activity."
            ),
            (
                "Its unscoped prospective, prohibition, invalidation, and next-gate "
                "language therefore treated permitted public repository validation as "
                "fixed G4 execution and could self-invalidate."
            ),
        ],
        "authority": "rejected_hash_identity_only",
    },
    {
        "role": "transition_static_test_candidate",
        "sha256": "0c685112421929b715912450e8eeb0e8e7ae5534806c19a7bee8fac6ecdada2d",
        "size_bytes": 67_654,
        "lines_lf": 1_905,
        "focused_test_cases_passed": 3,
        "mutation_cases_passed": 93,
        "blockers": [
            (
                "The test bound the factually false 2c11 accounting candidate and "
                "therefore could not establish a truthful transition contract."
            ),
            (
                "Focused structural and mutation success did not authenticate the "
                "already-observed ordinary public CI activity and granted no "
                "implementation, scientific, claim, result, or integration authority."
            ),
        ],
        "authority": "rejected_hash_identity_only",
    },
    {
        "role": "transition_accounting_repair_candidate",
        "sha256": "1def7c6c31a84508e8d50f67a817ff486c30fad3f502dbefcc094e7b6ea7615f",
        "size_bytes": 79_319,
        "lines_lf": 646,
        "blockers": [
            (
                "The future D150 zero-execution boundary remained unscoped and would "
                "forbid the temporary public synthetic fixtures and ordinary "
                "repository-safe CI that D150 static validation required."
            ),
            (
                "Its invalidation rule treated suite-internal temporary public roots, "
                "train calls, and predictions whose aggregate totals were intentionally "
                "uninstrumented as forbidden extra standalone smoke activity."
            ),
            (
                "Its allowed-validation rule asserted zero network and download for the "
                "entire public CI class even though first-suite network and download "
                "transaction totals were not instrumented or retained; only UV_OFFLINE "
                "and no observed download were established for the explicit "
                "build/install smoke."
            ),
        ],
        "authority": "rejected_hash_identity_only",
    },
)

FUTURE_IMPLEMENTATION_PATHS = (
    "research/maplight-gin-openadmet/.python-version",
    "research/maplight-gin-openadmet/pyproject.toml",
    "research/maplight-gin-openadmet/uv.lock",
    "research/maplight-gin-openadmet/build_global_v3_g4_gin300_capability.py",
    "research/maplight-gin-openadmet/run_global_v3_g4_gin300_capability.py",
    "tests/test_openadmet_global_v3_g4_gin300_capability.py",
    "tests/test_openadmet_global_v3_g4_gin300_capability_result.py",
)

FIXED_G4_ZERO_KEYS = (
    "restricted_roots_created_or_opened",
    "future_implementation_paths_created",
    "isolated_runtime_environments_created",
    "runtime_wheels_downloaded_or_installed",
    "checkpoint_or_model_bodies_fetched_or_opened",
    "checkpoint_tensors_deserialized_or_executed",
    "isolated_scientific_packages_imported",
    "parity_processes_executed",
    "graphs_built",
    "embeddings_generated",
    "synthetic_roots_built",
    "model_fits",
    "predictions",
    "official_inputs_opened",
    "official_target_values_opened",
    "private_scientific_rows_opened",
    "metrics",
    "bootstrap_replicates",
    "selection_tokens",
    "contenders_locked",
    "confirmatory_truth_values_opened",
    "blinded_test_rows_opened",
    "tdi_rows_opened",
    "validator_calls",
    "leaderboard_observations_used_for_selection",
    "systemd_units_created",
    "delegated_cgroups_created",
    "claims_created",
    "claims_consumed",
    "result_files_created",
    "submission_rows_generated",
    "portal_credentials_opened",
    "live_uploads",
    "gpu_hours",
)

D149_PATHS = (
    "benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_transition_rejection.json",
    "tests/test_openadmet_global_v3_g4_gin300_transition_rejection.py",
    "benchmarks/openadmet_cyp_2026/README.md",
    "docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md",
    "docs/phases/README.md",
    "docs/strategy/DECISIONS.md",
    "docs/strategy/NEXT_ORCHESTRATOR_PROMPT.md",
    "docs/strategy/PROJECT_STATE.md",
    "runs/experiment_ledger.csv",
)

INVALIDATION = (
    "Invalidate this terminal receipt if any rejected candidate or quarantine "
    "location is published; any fixed G4 restricted root, implementation path, "
    "runtime, checkpoint/model body, scientific object, claim, result, unit, cgroup, "
    "metric, submission row, credential, or upload is created or opened; ordinary "
    "public validation uncertainty is rewritten as zero; MapLight is called "
    "G4-selected or robustness-accepted; G2-8 is reopened; the accepted direct "
    "candidate hashes change; submission preparation or upload is authorized without "
    "a separate prospective baseline contract; any private path appears; or this D149 "
    "terminal package changes, adds, stages, or commits any additional path outside "
    "its exact nine-path allowlist. Preexisting repository paths untouched by this "
    "D149 package do not trigger this clause."
)

NEXT_GATE = (
    "Close and integrate this exact D149 terminal rejection package. There is no G4 "
    "retry, repair, implementation, claim, result, or execution gate. Any submission "
    "preparation must begin with a separately reviewed prospective fixed-MapLight "
    "baseline contract that reauthenticates the accepted direct candidate hashes "
    "without opening private portal evidence or granting upload authority here."
)

BASELINE_INTERPRETATION = (
    "The fixed MapLight baseline is retained because it is the strongest previously "
    "validated internal system, not because G4 selected it or because G2-7G accepted "
    "its robustness. The direct candidate hashes are an immutable existing handoff "
    "identity, not a new model-quality or portal claim."
)


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    raise ValueError(f"non-finite JSON constant: {value}")


def _strict_int(value: str) -> int:
    if value == "-0":
        raise ValueError("negative zero")
    return int(value)


def _strict_float(value: str) -> float:
    parsed = float(value)
    if value.startswith("-") and parsed == 0.0:
        raise ValueError("negative zero")
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number: {value}")
    return parsed


def _strict_load(raw: bytes) -> dict[str, Any]:
    assert not raw.startswith(b"\xef\xbb\xbf")
    value = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_reject_duplicates,
        parse_int=_strict_int,
        parse_float=_strict_float,
        parse_constant=_reject_constant,
    )
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8")
        + b"\n"
    )


def _mapping(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    assert all(isinstance(key, str) for key in value)
    return cast(dict[str, Any], value)


def _sequence(value: object) -> list[Any]:
    assert isinstance(value, list)
    return cast(list[Any], value)


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [string for item in value.values() for string in _strings(item)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [string for item in value for string in _strings(item)]
    return []


def _assert_contains(value: object, *fragments: str) -> None:
    assert isinstance(value, str)
    for fragment in fragments:
        assert fragment in value


def _replace_at_path(
    value: dict[str, Any], path: tuple[str | int, ...], replacement: Any
) -> None:
    cursor: Any = value
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = replacement


def _without_fragment(
    value: dict[str, Any], path: tuple[str | int, ...], fragment: str
) -> str:
    cursor: Any = value
    for key in path:
        cursor = cursor[key]
    assert isinstance(cursor, str)
    assert cursor.count(fragment) == 1
    return cursor.replace(fragment, "", 1)


def _validate_path_publication(record: dict[str, Any]) -> None:
    published_paths = {
        *(
            _mapping(item)["path"]
            for item in _sequence(record["immutable_d148_parent"]["files"])
        ),
        *_sequence(
            record["fixed_g4_preclaim_accounting"]["future_implementation_paths"]
        ),
        record["baseline_pivot"]["accepted_direct_candidate"]["public_handoff_path"],
        *_sequence(record["d149_terminal_package"]["exact_paths"]),
        record["ordinary_public_validation_accounting"]["typing_cache_observation"][
            "preexisting_ignored_repository_cache_entry"
        ],
    }
    expected_paths = {
        *(item["path"] for item in D148_FILES),
        *FUTURE_IMPLEMENTATION_PATHS,
        "benchmarks/openadmet_cyp_2026/DIRECT_BASELINE_HANDOFF.md",
        *D149_PATHS,
        ".mypy_cache/3.12/cache.3.db",
    }
    assert published_paths == expected_paths
    sensitive_components = {
        "private",
        "tmp",
        "temp",
        "temporary",
        "quarantine",
        "archive",
        "science",
        "source",
    }
    for path_text in published_paths:
        path = PurePosixPath(str(path_text))
        assert not path.is_absolute()
        assert ".." not in path.parts
        assert not sensitive_components.intersection(
            part.casefold() for part in path.parts
        )

    forbidden_path_patterns = (
        re.compile(r"(^|[\s`'\"])/(?:home|tmp|private|var/tmp)/"),
        re.compile(r"(?:^|[/\\])\.\.(?:[/\\]|$)"),
        re.compile(
            r"(?<![A-Za-z0-9_.-])(?:private|tmp|temp|temporary|quarantine|archive|science|source)(?:[/\\])",
            re.IGNORECASE,
        ),
        re.compile(r"^[A-Za-z]:[\\/]"),
        re.compile(r"file://", re.IGNORECASE),
    )
    for value in _strings(record):
        assert not value.startswith(("/", "~", "\\"))
        assert all(pattern.search(value) is None for pattern in forbidden_path_patterns)


def _validate_record(record: dict[str, Any]) -> None:
    assert tuple(record) == TOP_LEVEL_KEYS
    assert record["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v3_g4_gin300_transition_rejection.v1"
    )
    assert record["recorded_at_utc"] == "2026-08-31T01:03:38Z"
    assert record["status"] == "G3_2_EXP_G4_GIN300_PRECLAIM_CLOSED"
    assert record["gate"] == record["status"]
    assert record["record_id"] == "GLOBAL_V3_G4_GIN300_TRANSITION_REJECTION"
    assert record["experiment_id"] == "EXP-G4-GIN300"
    assert record["decision"] == (
        "reject_transition_close_g4_preclaim_and_pivot_to_fixed_maplight"
    )
    assert record["terminal"] is True

    parent = _mapping(record["immutable_d148_parent"])
    assert tuple(parent) == ("integrated_commit", "files", "preservation")
    assert parent["integrated_commit"] == D148_COMMIT
    parent_files = tuple(_mapping(item) for item in _sequence(parent["files"]))
    assert parent_files == D148_FILES
    for expected in D148_FILES:
        path = ROOT / expected["path"]
        assert path.is_file()
        assert not path.is_symlink()
        raw = path.read_bytes()
        assert len(raw) == expected["size_bytes"]
        assert raw.count(b"\n") == expected["lines_lf"]
        assert hashlib.sha256(raw).hexdigest() == expected["sha256"]
    _assert_contains(
        parent["preservation"],
        "exact integrated prospective capability record",
        "never consumed",
        "no authority to repair, retry, or reinterpret G4",
    )

    rejected = tuple(
        _mapping(item) for item in _sequence(record["rejected_transition_evidence"])
    )
    assert rejected == REJECTED_TRANSITION_EVIDENCE
    assert tuple(item["role"] for item in rejected) == (
        "transition_contract_candidate",
        "transition_static_test_candidate",
        "transition_accounting_repair_candidate",
    )
    assert all(item["authority"] == "rejected_hash_identity_only" for item in rejected)

    publication = _mapping(record["rejected_evidence_publication_boundary"])
    assert tuple(publication) == (
        "candidate_and_test_hashes_and_stats_published",
        "rejected_candidate_bytes_published",
        "quarantine_or_archive_paths_published",
        "quarantine_or_archive_bytes_published",
        "rejected_narrative_patch_identity_published",
        "rule",
    )
    assert publication["candidate_and_test_hashes_and_stats_published"] == 3
    for key in (
        "rejected_candidate_bytes_published",
        "quarantine_or_archive_paths_published",
        "quarantine_or_archive_bytes_published",
        "rejected_narrative_patch_identity_published",
    ):
        assert publication[key] == 0
    _assert_contains(
        publication["rule"],
        "not public evidence",
        "Only the three candidate/test hashes, byte and LF counts, and blocker facts",
    )

    public = _mapping(record["ordinary_public_validation_accounting"])
    assert tuple(public) == (
        "authority",
        "offline_public_project_build",
        "offline_public_project_install",
        "explicit_public_audit_train_predict_report_smoke",
        "typing_cache_observation",
        "first_full_repository_safe_suite",
        "cleanup",
        "uncertainty_rule",
    )
    _assert_contains(
        public["authority"],
        "already-tracked public root project",
        "not D150 implementation execution",
        "D151 restricted capability science",
        "submission authority",
    )

    build = _mapping(public["offline_public_project_build"])
    assert tuple(build) == (
        "invocations",
        "uv_offline_configured",
        "raw_network_transaction_exact_total_retained",
        "raw_network_response_bytes_exact_total_retained",
        "download_observed",
        "uv_internal_isolated_build_environment_or_cache_object_exact_total_retained",
        "uv_internal_isolated_build_environment_or_cache_bytes_exact_total_retained",
        "artifacts",
    )
    assert build["invocations"] == 1
    assert build["uv_offline_configured"] is True
    assert build["download_observed"] is False
    for key in (
        "raw_network_transaction_exact_total_retained",
        "raw_network_response_bytes_exact_total_retained",
        "uv_internal_isolated_build_environment_or_cache_object_exact_total_retained",
        "uv_internal_isolated_build_environment_or_cache_bytes_exact_total_retained",
    ):
        assert build[key] is False
    assert _sequence(build["artifacts"]) == [
        {
            "kind": "sdist",
            "sha256": "5ab8819134b0e9dc9dbde1dc9120138b01f7de2c4b8816873829755a65903026",
            "size_bytes": 338_214,
            "hash_authority": "incidental_non_authoritative",
        },
        {
            "kind": "wheel",
            "sha256": "525924df7092529bd12f7fda111a0444ee900ab4db657dfdc33ce2593a88f594",
            "size_bytes": 406_405,
            "hash_authority": "incidental_non_authoritative",
        },
    ]

    install = _mapping(public["offline_public_project_install"])
    assert tuple(install) == (
        "fresh_explicit_temporary_virtual_environments",
        "python_version",
        "uv_offline_configured",
        "raw_network_transaction_exact_total_retained",
        "raw_network_response_bytes_exact_total_retained",
        "download_observed",
        "cached_distributions_installed",
        "cached_distribution_count",
        "global_cache_read_mutation_and_atime_operation_exact_totals_retained",
    )
    assert install["fresh_explicit_temporary_virtual_environments"] == 1
    assert install["python_version"] == "3.12.3"
    assert install["uv_offline_configured"] is True
    assert install["download_observed"] is False
    assert install["raw_network_transaction_exact_total_retained"] is False
    assert install["raw_network_response_bytes_exact_total_retained"] is False
    assert tuple(_sequence(install["cached_distributions_installed"])) == (
        "cypshift==0.2.0.dev0",
        "numpy==2.5.2",
        "pillow==12.3.0",
        "rdkit==2026.3.5",
    )
    assert install["cached_distribution_count"] == 4
    assert (
        install["global_cache_read_mutation_and_atime_operation_exact_totals_retained"]
        is False
    )

    smoke = _mapping(public["explicit_public_audit_train_predict_report_smoke"])
    assert tuple(smoke) == (
        "preliminary_path_exists_failures_before_reported_work",
        "successful_root_count",
        "per_root",
        "successful_audit_invocations",
        "train_invocations",
        "predict_invocations",
        "report_invocations",
        "predictions_total",
        "root_outputs_byte_identical",
        "internal_fit_metric_and_import_event_exact_totals_retained",
    )
    assert smoke["preliminary_path_exists_failures_before_reported_work"] == 1
    assert smoke["successful_root_count"] == 2
    assert _mapping(smoke["per_root"]) == {
        "files": 9,
        "bytes": 36_758,
        "accepted": 7,
        "quarantined": 1,
        "warnings": 7,
        "supported": 3,
        "unsupported": 1,
        "predictions": 21,
    }
    for key in (
        "successful_audit_invocations",
        "train_invocations",
        "predict_invocations",
        "report_invocations",
    ):
        assert smoke[key] == 2
    assert smoke["predictions_total"] == 42
    assert smoke["root_outputs_byte_identical"] is True
    assert smoke["internal_fit_metric_and_import_event_exact_totals_retained"] is False

    cache = _mapping(public["typing_cache_observation"])
    assert cache == {
        "preexisting_ignored_repository_cache_entry": ".mypy_cache/3.12/cache.3.db",
        "observed_birth_date": "2026-08-17",
        "observed_modification_time_text": "2026-08-30 20:40:36",
        "exact_mutating_operation_retained": False,
        "interpretation": (
            "The ignored cache entry predated D149 and was observed modified during "
            "validation, but the exact operation was not instrumented and is not "
            "guessed. It is not a new task-owned explicit artifact and grants no "
            "authority."
        ),
        "authoritative_rerun_used_task_temporary_cache": True,
        "authoritative_task_temporary_cache_deleted_and_absent": True,
    }

    suite = _mapping(public["first_full_repository_safe_suite"])
    assert suite == {
        "passed": 1_452,
        "skipped": 14,
        "failed": 0,
        "pytest_seconds": 358.81,
        "wall_seconds": 359.31,
        "maximum_resident_set_kib": 900_212,
        "network_transaction_exact_total": "unknown_not_instrumented",
        "network_response_bytes_exact_total": "unknown_not_instrumented",
        "download_exact_total": "unknown_not_instrumented",
        "public_package_import_scientific_mechanics_and_cache_operation_exact_totals_retained": False,
        "authority": "superseded_validation_observation_not_scientific_evidence",
    }

    cleanup = _mapping(public["cleanup"])
    assert cleanup == {
        "explicit_task_temporary_build_roots_deleted_and_absent": True,
        "explicit_task_temporary_virtual_environment_deleted_and_absent": True,
        "explicit_task_temporary_public_smoke_roots_deleted_and_absent": True,
        "new_task_owned_explicit_persistent_public_validation_artifacts_created": 0,
    }
    _assert_contains(
        public["uncertainty_rule"],
        "stated as unknown or not retained",
        "never guessed or presented as zero",
    )

    fixed = _mapping(record["fixed_g4_preclaim_accounting"])
    assert tuple(fixed) == (
        "restricted_root_count",
        "restricted_roots_created_or_opened",
        "future_implementation_path_count",
        "future_implementation_paths",
        "future_implementation_paths_created",
        "isolated_runtime_environments_created",
        "runtime_wheels_downloaded_or_installed",
        "checkpoint_or_model_bodies_fetched_or_opened",
        "checkpoint_tensors_deserialized_or_executed",
        "isolated_scientific_packages_imported",
        "parity_processes_executed",
        "graphs_built",
        "embeddings_generated",
        "synthetic_roots_built",
        "model_fits",
        "predictions",
        "official_inputs_opened",
        "official_target_values_opened",
        "private_scientific_rows_opened",
        "metrics",
        "bootstrap_replicates",
        "selection_tokens",
        "contenders_locked",
        "confirmatory_truth_values_opened",
        "blinded_test_rows_opened",
        "tdi_rows_opened",
        "validator_calls",
        "leaderboard_observations_used_for_selection",
        "systemd_units_created",
        "delegated_cgroups_created",
        "claims_created",
        "claims_consumed",
        "result_files_created",
        "submission_rows_generated",
        "portal_credentials_opened",
        "live_uploads",
        "gpu_hours",
    )
    assert fixed["restricted_root_count"] == 7
    assert fixed["future_implementation_path_count"] == 7
    assert tuple(_sequence(fixed["future_implementation_paths"])) == (
        FUTURE_IMPLEMENTATION_PATHS
    )
    assert tuple(key for key in fixed if key in FIXED_G4_ZERO_KEYS) == (
        FIXED_G4_ZERO_KEYS
    )
    assert all(fixed[key] == 0 for key in FIXED_G4_ZERO_KEYS)

    terminal = _mapping(record["terminal_effect"])
    assert tuple(terminal) == (
        "g4_closed_preclaim",
        "claim_created",
        "claim_consumed",
        "retry_or_resume_authorized",
        "replacement_g4_transition_authorized",
        "d150_implementation_authorized",
        "d151_execution_authorized",
        "g4_result_authorized",
        "reversal_condition",
    )
    assert terminal["g4_closed_preclaim"] is True
    for key in (
        "claim_created",
        "claim_consumed",
        "retry_or_resume_authorized",
        "replacement_g4_transition_authorized",
        "d150_implementation_authorized",
        "d151_execution_authorized",
        "g4_result_authorized",
    ):
        assert terminal[key] is False
    _assert_contains(
        terminal["reversal_condition"],
        "None inside EXP-G4-GIN300",
        "separately named prospective contract",
        "may not repair, retry, or inherit unearned authority from G4",
    )

    pivot = _mapping(record["baseline_pivot"])
    assert tuple(pivot) == (
        "route",
        "basis",
        "internal_development_component_macro_mae",
        "selected_by_g4",
        "robustness_accepted",
        "g2_8_status",
        "accepted_direct_candidate",
        "interpretation",
        "submission_preparation_requires_separate_prospective_baseline_contract",
        "upload_authority_granted",
        "portal_status_or_result_claimed",
    )
    assert pivot["route"] == "fixed_maplight"
    assert pivot["basis"] == "strongest_previously_validated_internal_baseline"
    assert pivot["internal_development_component_macro_mae"] == 0.5837812652150708
    assert pivot["selected_by_g4"] is False
    assert pivot["robustness_accepted"] is False
    assert pivot["g2_8_status"] == "CLOSED"
    assert _mapping(pivot["accepted_direct_candidate"]) == {
        "submission_sha256": (
            "9d3ed5ff2ba08233caf99e46d4a0e69e59ab35a337521258a92ad21488db504b"
        ),
        "manifest_sha256": (
            "96ee587c4483b3ebab274b071c0c8108e35e0abc3bc2434ac0a5f0661dcb63d6"
        ),
        "public_handoff_path": (
            "benchmarks/openadmet_cyp_2026/DIRECT_BASELINE_HANDOFF.md"
        ),
        "bytes_may_be_reserialized": False,
    }
    assert pivot["interpretation"] == BASELINE_INTERPRETATION
    _assert_contains(
        BASELINE_INTERPRETATION,
        "strongest previously validated internal system",
        "not because G4 selected it",
        "or because G2-7G accepted its robustness",
        "not a new model-quality or portal claim",
    )
    assert (
        pivot["submission_preparation_requires_separate_prospective_baseline_contract"]
        is True
    )
    assert pivot["upload_authority_granted"] is False
    assert pivot["portal_status_or_result_claimed"] is False

    package = _mapping(record["d149_terminal_package"])
    assert tuple(package) == (
        "exact_path_count",
        "exact_paths",
        "record_paths",
        "test_paths",
        "narrative_paths",
        "ledger_paths",
        "transition_contract_paths",
        "integration_gate",
    )
    assert package["exact_path_count"] == 9
    assert tuple(_sequence(package["exact_paths"])) == D149_PATHS
    assert (
        package["record_paths"],
        package["test_paths"],
        package["narrative_paths"],
        package["ledger_paths"],
        package["transition_contract_paths"],
    ) == (1, 1, 6, 1, 0)
    _assert_contains(
        package["integration_gate"],
        "Only this exact terminal rejection package",
        "SSH-signed once by zchboswell",
        "fast-forward without rewrite",
        "No rejected transition candidate, implementation byte, claim, result, or private path",
    )

    assert record["invalidation"] == INVALIDATION
    _assert_contains(
        INVALIDATION,
        "ordinary public validation uncertainty is rewritten as zero",
        "MapLight is called G4-selected or robustness-accepted",
        "G2-8 is reopened",
        "accepted direct candidate hashes change",
        "upload is authorized without a separate prospective baseline contract",
        "any private path appears",
        "outside its exact nine-path allowlist",
        "Preexisting repository paths untouched by this D149 package do not trigger",
    )
    assert record["next_gate"] == NEXT_GATE
    assert "G4 selected MapLight" not in NEXT_GATE
    assert "MapLight robustness is accepted" not in NEXT_GATE
    assert "Upload is authorized" not in NEXT_GATE
    _assert_contains(
        NEXT_GATE,
        "There is no G4 retry, repair, implementation, claim, result, or execution gate",
        "separately reviewed prospective fixed-MapLight baseline contract",
        "without opening private portal evidence or granting upload authority here",
    )
    _validate_path_publication(record)


def test_transition_rejection_is_strict_canonical_exact_and_terminal() -> None:
    raw = RECORD.read_bytes()
    record = _strict_load(raw)
    assert raw == _canonical_bytes(record)
    assert len(raw) == RECORD_SIZE_BYTES
    assert raw.count(b"\n") == RECORD_LINES_LF
    assert b"\r" not in raw
    assert hashlib.sha256(raw).hexdigest() == RECORD_SHA256
    _validate_record(record)


def test_strict_loader_rejects_duplicate_nonfinite_negative_zero_and_junk() -> None:
    with pytest.raises(ValueError, match="duplicate JSON key"):
        _strict_load(b'{"value":1,"value":2}')
    for raw in (b'{"value":NaN}', b'{"value":Infinity}', b'{"value":-Infinity}'):
        with pytest.raises(ValueError, match="non-finite JSON constant"):
            _strict_load(raw)
    for raw in (b'{"value":-0}', b'{"value":-0.0}', b'{"value":-0e0}'):
        with pytest.raises(ValueError, match="negative zero"):
            _strict_load(raw)
    with pytest.raises((AssertionError, json.JSONDecodeError)):
        _strict_load(b'\xef\xbb\xbf{"value":0}')
    with pytest.raises(json.JSONDecodeError):
        _strict_load(b'{"value":0} trailing')


def test_transition_rejection_publishes_no_private_or_temporary_path() -> None:
    record = _strict_load(RECORD.read_bytes())
    _validate_path_publication(record)


def test_transition_rejection_mutations_fail_closed() -> None:
    record = _strict_load(RECORD.read_bytes())
    _validate_record(record)
    mutations: list[tuple[str, tuple[str | int, ...], Any]] = [
        ("schema", ("schema_version",), "wrong.v1"),
        ("status", ("status",), "G3_2_EXP_G4_GIN300_CAPABILITY_ACCEPTED"),
        ("terminal", ("terminal",), False),
        (
            "D148 commit",
            ("immutable_d148_parent", "integrated_commit"),
            "0" * 40,
        ),
        (
            "D148 contract hash",
            ("immutable_d148_parent", "files", 0, "sha256"),
            "0" * 64,
        ),
        (
            "D148 test LF count",
            ("immutable_d148_parent", "files", 3, "lines_lf"),
            2_508,
        ),
        (
            "rejected transition hash",
            ("rejected_transition_evidence", 0, "sha256"),
            "0" * 64,
        ),
        (
            "rejected static-test mutation count",
            ("rejected_transition_evidence", 1, "mutation_cases_passed"),
            92,
        ),
        (
            "rejected repair hash",
            ("rejected_transition_evidence", 2, "sha256"),
            "0" * 64,
        ),
        (
            "rejected authority",
            ("rejected_transition_evidence", 2, "authority"),
            "accepted",
        ),
        (
            "rejected bytes unpublished",
            (
                "rejected_evidence_publication_boundary",
                "rejected_candidate_bytes_published",
            ),
            1,
        ),
        (
            "offline configured",
            (
                "ordinary_public_validation_accounting",
                "offline_public_project_build",
                "uv_offline_configured",
            ),
            False,
        ),
        (
            "network total uncertainty",
            (
                "ordinary_public_validation_accounting",
                "offline_public_project_build",
                "raw_network_transaction_exact_total_retained",
            ),
            True,
        ),
        (
            "incidental wheel hash authority",
            (
                "ordinary_public_validation_accounting",
                "offline_public_project_build",
                "artifacts",
                1,
                "hash_authority",
            ),
            "authoritative",
        ),
        (
            "cached install count",
            (
                "ordinary_public_validation_accounting",
                "offline_public_project_install",
                "cached_distribution_count",
            ),
            5,
        ),
        (
            "public predictions",
            (
                "ordinary_public_validation_accounting",
                "explicit_public_audit_train_predict_report_smoke",
                "predictions_total",
            ),
            0,
        ),
        (
            "public roots identity",
            (
                "ordinary_public_validation_accounting",
                "explicit_public_audit_train_predict_report_smoke",
                "root_outputs_byte_identical",
            ),
            False,
        ),
        (
            "preexisting mypy cache",
            (
                "ordinary_public_validation_accounting",
                "typing_cache_observation",
                "preexisting_ignored_repository_cache_entry",
            ),
            ".mypy_cache/new.db",
        ),
        (
            "mypy operation unknown",
            (
                "ordinary_public_validation_accounting",
                "typing_cache_observation",
                "exact_mutating_operation_retained",
            ),
            True,
        ),
        (
            "suite passed",
            (
                "ordinary_public_validation_accounting",
                "first_full_repository_safe_suite",
                "passed",
            ),
            1_451,
        ),
        (
            "suite network unknown",
            (
                "ordinary_public_validation_accounting",
                "first_full_repository_safe_suite",
                "network_transaction_exact_total",
            ),
            0,
        ),
        (
            "cleanup persistence",
            (
                "ordinary_public_validation_accounting",
                "cleanup",
                "new_task_owned_explicit_persistent_public_validation_artifacts_created",
            ),
            1,
        ),
        (
            "restricted root opened",
            ("fixed_g4_preclaim_accounting", "restricted_roots_created_or_opened"),
            1,
        ),
        (
            "G4 prediction",
            ("fixed_g4_preclaim_accounting", "predictions"),
            1,
        ),
        (
            "claim consumed",
            ("fixed_g4_preclaim_accounting", "claims_consumed"),
            1,
        ),
        (
            "upload",
            ("fixed_g4_preclaim_accounting", "live_uploads"),
            1,
        ),
        (
            "retry",
            ("terminal_effect", "retry_or_resume_authorized"),
            True,
        ),
        (
            "D150 authorized",
            ("terminal_effect", "d150_implementation_authorized"),
            True,
        ),
        (
            "MapLight MAE",
            ("baseline_pivot", "internal_development_component_macro_mae"),
            0.5837812652150709,
        ),
        ("MapLight selected by G4", ("baseline_pivot", "selected_by_g4"), True),
        (
            "MapLight robustness accepted",
            ("baseline_pivot", "robustness_accepted"),
            True,
        ),
        ("G2-8 reopened", ("baseline_pivot", "g2_8_status"), "OPEN"),
        (
            "submission hash",
            (
                "baseline_pivot",
                "accepted_direct_candidate",
                "submission_sha256",
            ),
            "0" * 64,
        ),
        (
            "manifest hash",
            ("baseline_pivot", "accepted_direct_candidate", "manifest_sha256"),
            "0" * 64,
        ),
        (
            "upload authority",
            ("baseline_pivot", "upload_authority_granted"),
            True,
        ),
        (
            "portal claim",
            ("baseline_pivot", "portal_status_or_result_claimed"),
            True,
        ),
        (
            "prospective baseline contract exact boolean",
            (
                "baseline_pivot",
                "submission_preparation_requires_separate_prospective_baseline_contract",
            ),
            1,
        ),
        (
            "next gate contradictory upload authorization",
            ("next_gate",),
            NEXT_GATE + " Upload is authorized.",
        ),
        (
            "next gate contradictory G4 selection",
            ("next_gate",),
            NEXT_GATE + " G4 selected MapLight.",
        ),
        (
            "next gate contradictory robustness acceptance",
            ("next_gate",),
            NEXT_GATE + " MapLight robustness is accepted.",
        ),
        (
            "baseline interpretation contradictory G4 selection",
            ("baseline_pivot", "interpretation"),
            BASELINE_INTERPRETATION + " G4 selected MapLight.",
        ),
        (
            "baseline interpretation contradictory robustness acceptance",
            ("baseline_pivot", "interpretation"),
            BASELINE_INTERPRETATION + " G2-7G robustness was accepted.",
        ),
        (
            "package path count",
            ("d149_terminal_package", "exact_path_count"),
            10,
        ),
        (
            "package path",
            ("d149_terminal_package", "exact_paths", 1),
            "tests/other.py",
        ),
        *(
            (
                f"relative {component} path leak",
                ("ordinary_public_validation_accounting", "authority"),
                str(record["ordinary_public_validation_accounting"]["authority"])
                + f" {component}/data.csv",
            )
            for component in (
                "private",
                "tmp",
                "temp",
                "temporary",
                "quarantine",
                "archive",
                "science",
                "source",
            )
        ),
    ]
    fragment_mutations: list[tuple[str, tuple[str | int, ...], str]] = [
        (
            "ordinary CI is not D150",
            ("ordinary_public_validation_accounting", "authority"),
            "not D150 implementation execution",
        ),
        (
            "cache mutation uninstrumented",
            (
                "ordinary_public_validation_accounting",
                "typing_cache_observation",
                "interpretation",
            ),
            "exact operation was not instrumented and is not guessed",
        ),
        (
            "unknowns never zeroed",
            ("ordinary_public_validation_accounting", "uncertainty_rule"),
            "never guessed or presented as zero",
        ),
        (
            "no G4 reversal",
            ("terminal_effect", "reversal_condition"),
            "None inside EXP-G4-GIN300",
        ),
        (
            "MapLight not G4 selected",
            ("baseline_pivot", "interpretation"),
            "not because G4 selected it",
        ),
        (
            "MapLight not robustness evidence",
            ("baseline_pivot", "interpretation"),
            "or because G2-7G accepted its robustness",
        ),
        (
            "rejected candidate publication invalidates",
            ("invalidation",),
            "any rejected candidate or quarantine location is published",
        ),
        (
            "fixed G4 root invalidates",
            ("invalidation",),
            "fixed G4 restricted root,",
        ),
        (
            "implementation path invalidates",
            ("invalidation",),
            "implementation path,",
        ),
        ("runtime invalidates", ("invalidation",), "runtime,"),
        (
            "checkpoint or model body invalidates",
            ("invalidation",),
            "checkpoint/model body,",
        ),
        (
            "scientific object invalidates",
            ("invalidation",),
            "scientific object,",
        ),
        ("claim invalidates", ("invalidation",), "claim,"),
        ("result invalidates", ("invalidation",), "result,"),
        ("unit invalidates", ("invalidation",), "unit,"),
        ("cgroup invalidates", ("invalidation",), "cgroup,"),
        ("metric invalidates", ("invalidation",), "metric,"),
        (
            "submission row invalidates",
            ("invalidation",),
            "submission row,",
        ),
        ("credential invalidates", ("invalidation",), "credential,"),
        (
            "upload invalidates",
            ("invalidation",),
            "or upload is created or opened",
        ),
        (
            "outside-path invalidation",
            ("invalidation",),
            "outside its exact nine-path allowlist",
        ),
        (
            "preexisting paths do not invalidate",
            ("invalidation",),
            "Preexisting repository paths untouched by this D149 package do not trigger",
        ),
        (
            "no G4 retry gate",
            ("next_gate",),
            "There is no G4 retry, repair, implementation, claim, result, or execution gate",
        ),
        (
            "separate baseline contract",
            ("next_gate",),
            "separately reviewed prospective fixed-MapLight baseline contract",
        ),
    ]
    mutations.extend(
        (label, path, _without_fragment(record, path, fragment))
        for label, path, fragment in fragment_mutations
    )

    for label, path, replacement in mutations:
        mutation = copy.deepcopy(record)
        _replace_at_path(mutation, path, replacement)
        try:
            _validate_record(mutation)
        except AssertionError:
            continue
        pytest.fail(f"mutation did not fail closed: {label} at {path!r}")

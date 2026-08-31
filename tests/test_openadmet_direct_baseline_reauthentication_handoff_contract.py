from __future__ import annotations

import ast
import copy
import csv
import hashlib
import io
import json
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn, cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "direct_baseline_reauthentication_handoff_contract.json"
)
LEDGER = ROOT / "runs" / "experiment_ledger.csv"

# Freeze these three constants only after the canonical contract bytes stabilize.
CONTRACT_SHA256 = "589facbbe8b51aeee00abdcba756c9119262572954854f438c549cab7ff98fcd"
CONTRACT_SIZE_BYTES = 22_489
CONTRACT_LINES_LF = 431

D149_COMMIT = "0bf9b253002399a61e3d8d4e37e1a957ebd198ec"
D149_RECORD = {
    "path": (
        "benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_transition_rejection.json"
    ),
    "sha256": "10a7f783d73ae60c6da479ffbd8cd3e3443b3f8dace88e177fd9c17c44e1331c",
    "size_bytes": 14_871,
    "lines_lf": 276,
}
D149_TEST = {
    "path": "tests/test_openadmet_global_v3_g4_gin300_transition_rejection.py",
    "sha256": "f033a7577dca4eafd3cec979938292fcb0d7b6ef80f0e86d6134fc8d9f4d944f",
    "size_bytes": 43_378,
    "lines_lf": 1_226,
}
D149_LEDGER_PARENT = {
    "path": "runs/experiment_ledger.csv",
    "sha256": "515801a45120ea07fada9b3193a4f10614074b77674d0f3b0ea0c01dabaa26fa",
    "size_bytes": 437_803,
    "lines_lf": 200,
}
PUBLIC_HANDOFF = {
    "path": "benchmarks/openadmet_cyp_2026/DIRECT_BASELINE_HANDOFF.md",
    "sha256": "6a9402ca3fdf02dbcad079cba82162132e5b149f6adf69f80ea05d177e1ecec4",
    "size_bytes": 2_919,
    "lines_lf": 55,
}
PUBLIC_REQUIREMENT_RECEIPTS = (
    {
        "path": "benchmarks/openadmet_cyp_2026/source_receipts.json",
        "sha256": "764e59d37cc12993babce64208117d47612a1551bdcf30d1a22d10eb60636974",
        "size_bytes": 10_485,
        "lines_lf": 123,
    },
    {
        "path": "benchmarks/openadmet_cyp_2026/challenge_contract.json",
        "sha256": "344d3414d03bb98e57def998e80ab4cf315c1bebe7c01cb9d7c1c32ba3cd6123",
        "size_bytes": 7_889,
        "lines_lf": 123,
    },
    {
        "path": "benchmarks/openadmet_cyp_2026/submission_contract.json",
        "sha256": "4be9933cd5e9404603d8971e49847bb240eff99f09874696c769a4fafd0d9a3c",
        "size_bytes": 2_378,
        "lines_lf": 49,
    },
)
DIRECT_DEPLOYMENT_CONTRACT = {
    "path": "benchmarks/openadmet_cyp_2026/direct_maplight_deployment_contract.json",
    "sha256": "918fc1358e3394f32cd21b2f57b283f584e97242068fa0dc60448babc3963960",
    "size_bytes": 8_266,
    "lines_lf": 189,
}
MAPLIGHT_REPRODUCTION = {
    "path": (
        "benchmarks/openadmet_cyp_2026/global_v2_maplight_official_reproduction.json"
    ),
    "sha256": "767750305a36eb7e9a850c221c67534534ddac85a6125683192266651f7a4482",
    "size_bytes": 5_001,
    "lines_lf": 122,
}
GLOBAL_V2_EXPERIMENT_CONTRACT = {
    "path": "benchmarks/openadmet_cyp_2026/global_v2_experiment_contract.json",
    "sha256": "612b8cea20cba8fb5d209fdd2d92a42feb652477c358f92ed710449d091e5c0d",
    "size_bytes": 31_142,
    "lines_lf": 346,
}
SUBMISSION_SHA256 = "9d3ed5ff2ba08233caf99e46d4a0e69e59ab35a337521258a92ad21488db504b"
MANIFEST_SHA256 = "96ee587c4483b3ebab274b071c0c8108e35e0abc3bc2434ac0a5f0661dcb63d6"
MAPLIGHT_DEVELOPMENT_COMPONENT_MACRO_MAE = 0.5837812652150708
TUTORIAL_COMMIT = "858ae63ce79934113bccdb7fc65467de5f7b1935"
VALIDATOR_SHA256 = "276a53d7f22ff973aaf567e64d977202995e91ba3cef2bbdc4de71c13bdebcb2"
BLINDED_TEST_REVISION = "85f8b358d0a2056a98b990dd75d3b3ec9247862b"
BLINDED_TEST_CSV_SHA256 = (
    "a342f8444a8dcb531ca12f3685293f0bd6c36ae9073f491e44a9bc1cc4b741f9"
)

TOP_LEVEL_KEYS = (
    "schema_version",
    "recorded_at_utc",
    "status",
    "gate",
    "record_id",
    "contract_only",
    "purpose",
    "immutable_d149_parent",
    "immutable_public_evidence",
    "current_candidate_state",
    "current_authority",
    "contract_milestone_accounting",
    "future_single_use_read_only_reauthentication",
    "future_status_taxonomy",
    "exact_package_scope",
    "invalidation",
    "competitive_backout",
    "next_gate",
)

LEDGER_ROWS = (
    {
        "physical_line": 120,
        "experiment_id": "trace-direct-maplight-deployment-synthetic",
        "sha256": "58626ea76a52e1c746c9991a21f32e8d3928cd47f021a35087ecd157423c4025",
        "size_bytes_including_lf": 2_263,
        "fields": 18,
    },
    {
        "physical_line": 121,
        "experiment_id": "trace-direct-maplight-official-candidate",
        "sha256": "e7b2502ff1d82b893e9b3ba06d49eba37f35720b0cd9c977a412350bd52d3d67",
        "size_bytes_including_lf": 1_945,
        "fields": 18,
    },
    {
        "physical_line": 126,
        "experiment_id": "direct-maplight-competition-validator",
        "sha256": "d0273042efb653b5fc3604f69944ff8a6b19ffdef582d3fcedff47f35c01ffeb",
        "size_bytes_including_lf": 1_245,
        "fields": 18,
    },
    {
        "physical_line": 141,
        "experiment_id": "global-v2-g2-2c-official-reproduced",
        "sha256": "2b1e3f9742396d500b8697f4f37a0cbd9dc72e5b5f47779b7a5aa1f89773d0e6",
        "size_bytes_including_lf": 2_123,
        "fields": 18,
    },
    {
        "physical_line": 200,
        "experiment_id": "global-v3-g3-2-exp-g4-gin300-transition-rejected",
        "sha256": "0bd57d22c25b5162ca811e0dde542c4a45abee27d4f21662bd2c21c1a2992baf",
        "size_bytes_including_lf": 5_950,
        "fields": 18,
    },
)

D150_PATHS = (
    (
        "benchmarks/openadmet_cyp_2026/"
        "direct_baseline_reauthentication_handoff_contract.json"
    ),
    "tests/test_openadmet_direct_baseline_reauthentication_handoff_contract.py",
    "benchmarks/openadmet_cyp_2026/README.md",
    "docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md",
    "docs/phases/README.md",
    "docs/strategy/DECISIONS.md",
    "docs/strategy/NEXT_ORCHESTRATOR_PROMPT.md",
    "docs/strategy/PROJECT_STATE.md",
    "runs/experiment_ledger.csv",
)

SCHEMA = (
    "cypshift.openadmet_cyp_2026.direct_baseline_reauthentication_handoff_contract.v1"
)
STATUS = "DIRECT_BASELINE_REAUTHENTICATION_HANDOFF_CONTRACT_FROZEN"
FUTURE_SUCCESS = "DIRECT_BASELINE_REAUTHENTICATED_READ_ONLY"
FUTURE_FAILURE = "DIRECT_BASELINE_REAUTHENTICATION_FAILED_CLOSED"
ROUTE_WITHDRAWN = "DIRECT_BASELINE_ROUTE_WITHDRAWN"
MUTATION_CASES = 196


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


def _assert_bool(value: object, expected: bool) -> None:
    assert type(value) is bool
    assert value is expected


def _assert_zero(value: object) -> None:
    assert type(value) is int
    assert value == 0


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


def _assert_mutations_fail_closed(
    contract: dict[str, Any],
    validator: Any,
    mutations: Sequence[tuple[str, tuple[str | int, ...], Any]],
) -> None:
    seen_labels: set[str] = set()
    for label, path, replacement in mutations:
        assert label not in seen_labels
        seen_labels.add(label)
        mutation = copy.deepcopy(contract)
        _replace_at_path(mutation, path, replacement)
        try:
            validator(mutation)
        except AssertionError:
            continue
        pytest.fail(f"mutation did not fail closed: {label} at {path!r}")


def _ledger_physical_lines() -> list[bytes]:
    raw = LEDGER.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw
    assert raw.endswith(b"\n")
    return raw.splitlines(keepends=True)


def _assert_public_path(path_text: object) -> None:
    assert isinstance(path_text, str)
    path = PurePosixPath(path_text)
    assert path_text == path.as_posix()
    assert not path.is_absolute()
    assert path_text not in ("", ".")
    assert ".." not in path.parts
    assert "\\" not in path_text


def _validate_ledger_rows(bound_rows: object) -> None:
    rows = tuple(_mapping(row) for row in _sequence(bound_rows))
    assert rows == LEDGER_ROWS
    assert all(
        tuple(row)
        == (
            "physical_line",
            "experiment_id",
            "sha256",
            "size_bytes_including_lf",
            "fields",
        )
        for row in rows
    )
    assert len({row["physical_line"] for row in rows}) == len(rows) == 5
    assert len({row["experiment_id"] for row in rows}) == len(rows)
    assert all(row["physical_line"] != 128 for row in rows)

    physical_lines = _ledger_physical_lines()
    assert len(physical_lines) >= 200
    for expected in rows:
        raw = physical_lines[expected["physical_line"] - 1]
        assert len(raw) == expected["size_bytes_including_lf"]
        assert raw.endswith(b"\n") and raw.count(b"\n") == 1
        assert hashlib.sha256(raw).hexdigest() == expected["sha256"]
        decoded = next(csv.reader(io.StringIO(raw.decode("utf-8"), newline="")))
        assert len(decoded) == expected["fields"] == 18
        assert decoded[0] == expected["experiment_id"]
        assert "\n" not in decoded[0] and "\r" not in decoded[0]


def _validate_no_sensitive_path_publication(contract: dict[str, Any]) -> None:
    public_paths = {
        D149_RECORD["path"],
        PUBLIC_HANDOFF["path"],
        *D150_PATHS,
    }
    for path_text in public_paths:
        _assert_public_path(path_text)

    forbidden_path_patterns = (
        # Reject path-like absolute tokens after any punctuation boundary, not
        # only after whitespace. This deliberately catches forms such as
        # ``locator=/...`` while avoiding ordinary prose that contains a slash.
        re.compile(r"(?:^|[\s=`'\":,(])/(?!/)[^\s`'\",)]+"),
        re.compile(r"\.\.[/\\]"),
        re.compile(r"(?:^|[^A-Za-z0-9])[A-Za-z]:[\\/]"),
        re.compile(r"file:(?:[/\\]+)", re.IGNORECASE),
        re.compile(r"~[/\\]"),
        re.compile(r"\\\\[^\s\\]+[\\/]"),
    )
    for value in _strings(contract):
        assert not value.startswith(("/", "~", "\\"))
        assert all(pattern.search(value) is None for pattern in forbidden_path_patterns)


def _assert_public_receipt(expected: Mapping[str, Any]) -> None:
    assert tuple(expected) == ("path", "sha256", "size_bytes", "lines_lf")
    _assert_public_path(expected["path"])
    path = ROOT / str(expected["path"])
    assert path.is_file()
    assert not path.is_symlink()
    raw = path.read_bytes()
    assert len(raw) == expected["size_bytes"]
    assert raw.count(b"\n") == expected["lines_lf"]
    assert b"\r" not in raw
    assert hashlib.sha256(raw).hexdigest() == expected["sha256"]


def _assert_ledger_parent_prefix(expected: Mapping[str, Any]) -> None:
    assert dict(expected) == D149_LEDGER_PARENT
    lines = _ledger_physical_lines()
    assert len(lines) >= expected["lines_lf"]
    raw = b"".join(lines[: int(expected["lines_lf"])])
    assert len(raw) == expected["size_bytes"]
    assert raw.count(b"\n") == expected["lines_lf"]
    assert hashlib.sha256(raw).hexdigest() == expected["sha256"]


def _validate_contract(contract: dict[str, Any]) -> None:
    assert tuple(contract) == TOP_LEVEL_KEYS
    assert contract["schema_version"] == SCHEMA
    assert contract["recorded_at_utc"] == "2026-08-31T02:14:49Z"
    assert contract["status"] == STATUS
    assert contract["gate"] == STATUS
    assert contract["record_id"] == "DIRECT_BASELINE_REAUTHENTICATION_HANDOFF_CONTRACT"
    _assert_bool(contract["contract_only"], True)
    assert contract["purpose"] == (
        "Freeze one future single-use read-only byte reauthentication of the "
        "historically accepted fixed-MapLight direct candidate. This milestone "
        "opens no private candidate byte, invokes no validator, accesses no portal "
        "or credential, performs no upload, and grants no upload authority."
    )
    _assert_contains(
        contract["purpose"],
        "one future single-use read-only byte reauthentication",
        "opens no private candidate byte",
        "invokes no validator",
        "accesses no portal or credential",
        "performs no upload",
        "grants no upload authority",
    )

    parent = _mapping(contract["immutable_d149_parent"])
    assert tuple(parent) == (
        "integrated_commit",
        "integration_proof",
        "transition_rejection",
        "transition_rejection_test",
        "experiment_ledger_parent",
        "preservation",
    )
    assert parent["integrated_commit"] == D149_COMMIT
    integration = _mapping(parent["integration_proof"])
    assert tuple(integration) == (
        "pull_request",
        "exact_head_pull_request_ci_run",
        "exact_sha_post_main_ci_run",
        "pull_request_ci_green",
        "post_main_ci_green",
        "integration_method",
    )
    assert type(integration["pull_request"]) is int
    assert integration["pull_request"] == 186
    assert type(integration["exact_head_pull_request_ci_run"]) is int
    assert integration["exact_head_pull_request_ci_run"] == 33_348_758_894
    assert type(integration["exact_sha_post_main_ci_run"]) is int
    assert integration["exact_sha_post_main_ci_run"] == 33_349_365_347
    _assert_bool(integration["pull_request_ci_green"], True)
    _assert_bool(integration["post_main_ci_green"], True)
    assert integration["integration_method"] == (
        "local_fast_forward_only_without_commit_rewrite"
    )
    rejection = _mapping(parent["transition_rejection"])
    assert tuple(rejection) == (
        "path",
        "sha256",
        "size_bytes",
        "lines_lf",
        "status",
    )
    assert {key: rejection[key] for key in D149_RECORD} == D149_RECORD
    assert rejection["status"] == "G3_2_EXP_G4_GIN300_PRECLAIM_CLOSED"
    _assert_public_receipt(D149_RECORD)
    rejection_test = _mapping(parent["transition_rejection_test"])
    assert rejection_test == D149_TEST
    assert tuple(rejection_test) == ("path", "sha256", "size_bytes", "lines_lf")
    _assert_public_receipt(D149_TEST)
    ledger_parent = _mapping(parent["experiment_ledger_parent"])
    assert ledger_parent == D149_LEDGER_PARENT
    assert tuple(ledger_parent) == ("path", "sha256", "size_bytes", "lines_lf")
    _assert_ledger_parent_prefix(ledger_parent)
    _assert_contains(
        parent["preservation"],
        "D149 remains terminal immutable history",
        "G4 stays closed preclaim",
        "no retry, repair, replacement, implementation, claim, result, or successor correction",
    )
    assert parent["preservation"] == (
        "D149 remains terminal immutable history. G4 stays closed preclaim with "
        "no retry, repair, replacement, implementation, claim, result, or "
        "successor correction."
    )

    evidence = _mapping(contract["immutable_public_evidence"])
    assert tuple(evidence) == (
        "tracked_handoff",
        "latest_tracked_public_requirement_snapshot",
        "global_v2_experiment_contract",
        "historical_candidate_identity",
        "direct_deployment_contract",
        "fixed_maplight_internal_development_evidence",
        "exact_ledger_rows",
        "precedence",
    )
    handoff = _mapping(evidence["tracked_handoff"])
    assert tuple(handoff) == (
        "path",
        "sha256",
        "size_bytes",
        "lines_lf",
        "historical_candidate_locator",
        "historical_root_mode",
        "historical_file_mode",
    )
    assert {key: handoff[key] for key in PUBLIC_HANDOFF} == PUBLIC_HANDOFF
    assert handoff["historical_candidate_locator"] == (
        "not_republished_resolve_privately_from_authenticated_tracked_handoff"
    )
    assert handoff["historical_root_mode"] == "0555"
    assert handoff["historical_file_mode"] == "0444"
    _assert_public_receipt(PUBLIC_HANDOFF)

    snapshot = _mapping(evidence["latest_tracked_public_requirement_snapshot"])
    assert tuple(snapshot) == (
        "as_of_utc",
        "live_public_rule_refresh_performed",
        "live_current_rules_claimed",
        "repository_heads",
        "tracked_files",
        "direct_requirements",
        "interpretation",
    )
    assert snapshot["as_of_utc"] == "2026-08-24T04:21:32Z"
    _assert_bool(snapshot["live_public_rule_refresh_performed"], False)
    _assert_bool(snapshot["live_current_rules_claimed"], False)
    heads = _mapping(snapshot["repository_heads"])
    assert tuple(heads) == ("dataset", "space", "tutorial")
    assert heads == {
        "dataset": BLINDED_TEST_REVISION,
        "space": "13c5057b37d1e72b3f036dd0d59718b1823f8fdd",
        "tutorial": TUTORIAL_COMMIT,
    }
    requirement_basis = tuple(
        _mapping(receipt) for receipt in _sequence(snapshot["tracked_files"])
    )
    assert requirement_basis == PUBLIC_REQUIREMENT_RECEIPTS
    for receipt in requirement_basis:
        assert tuple(receipt) == ("path", "sha256", "size_bytes", "lines_lf")
        _assert_public_receipt(receipt)

    requirements = _mapping(snapshot["direct_requirements"])
    assert tuple(requirements) == (
        "rows",
        "required_columns_ordered",
        "prediction_type",
        "finite_values_required",
        "live_backend_parity",
        "row_order",
        "duplicate_identifier_behavior",
        "extra_columns",
    )
    assert type(requirements["rows"]) is int and requirements["rows"] == 750
    assert tuple(_sequence(requirements["required_columns_ordered"])) == (
        "SMILES",
        "Molecule_Name",
        "CYP1A2_pIC50_direct_inhibition",
        "CYP2C9_pIC50_direct_inhibition",
        "CYP2D6_pIC50_direct_inhibition",
        "CYP3A4_pIC50_direct_inhibition",
    )
    assert requirements["prediction_type"] == "numeric"
    _assert_bool(requirements["finite_values_required"], True)
    assert requirements["live_backend_parity"] == "unresolved"
    assert requirements["row_order"] == "unresolved"
    assert requirements["duplicate_identifier_behavior"] == "unresolved"
    assert requirements["extra_columns"] == "unresolved"
    _assert_contains(
        snapshot["interpretation"],
        "latest tracked snapshot bound before D150",
        "not a live rules refresh",
        "current portal/backend behavior",
    )
    assert snapshot["interpretation"] == (
        "This is the latest tracked snapshot bound before D150, not a live rules "
        "refresh or claim about current portal/backend behavior."
    )

    global_contract = _mapping(evidence["global_v2_experiment_contract"])
    assert global_contract == GLOBAL_V2_EXPERIMENT_CONTRACT
    assert tuple(global_contract) == ("path", "sha256", "size_bytes", "lines_lf")
    _assert_public_receipt(GLOBAL_V2_EXPERIMENT_CONTRACT)

    candidate = _mapping(evidence["historical_candidate_identity"])
    assert tuple(candidate) == (
        "system_id",
        "submission_filename",
        "submission_sha256",
        "manifest_filename",
        "manifest_sha256",
        "rows",
        "finite_predictions",
        "bytes_may_be_reserialized",
        "historical_validator",
    )
    assert candidate["system_id"] == "TRACE-G0-MAPL-FIXED"
    assert candidate["submission_filename"] == "submission.csv"
    assert candidate["submission_sha256"] == SUBMISSION_SHA256
    assert candidate["manifest_filename"] == "manifest.json"
    assert candidate["manifest_sha256"] == MANIFEST_SHA256
    assert type(candidate["rows"]) is int and candidate["rows"] == 750
    assert (
        type(candidate["finite_predictions"]) is int
        and candidate["finite_predictions"] == 3_000
    )
    _assert_bool(candidate["bytes_may_be_reserialized"], False)
    historical_validator = _mapping(candidate["historical_validator"])
    assert tuple(historical_validator) == (
        "tutorial_commit",
        "validator_sha256",
        "official_blinded_test_revision",
        "official_blinded_test_sha256",
        "valid",
        "errors",
        "authority",
    )
    assert historical_validator["tutorial_commit"] == TUTORIAL_COMMIT
    assert historical_validator["validator_sha256"] == VALIDATOR_SHA256
    assert historical_validator["official_blinded_test_revision"] == (
        BLINDED_TEST_REVISION
    )
    assert historical_validator["official_blinded_test_sha256"] == (
        BLINDED_TEST_CSV_SHA256
    )
    _assert_bool(historical_validator["valid"], True)
    _assert_zero(historical_validator["errors"])
    assert historical_validator["authority"] == (
        "historical_public_receipt_only_not_a_current_validator_call_or_live_backend_claim"
    )

    deployment = _mapping(evidence["direct_deployment_contract"])
    assert deployment == DIRECT_DEPLOYMENT_CONTRACT
    assert tuple(deployment) == ("path", "sha256", "size_bytes", "lines_lf")
    _assert_public_receipt(DIRECT_DEPLOYMENT_CONTRACT)
    maplight = _mapping(evidence["fixed_maplight_internal_development_evidence"])
    assert tuple(maplight) == (
        "path",
        "sha256",
        "size_bytes",
        "lines_lf",
        "status",
        "component_macro_mae",
        "interpretation",
    )
    assert {key: maplight[key] for key in MAPLIGHT_REPRODUCTION} == (
        MAPLIGHT_REPRODUCTION
    )
    _assert_public_receipt(MAPLIGHT_REPRODUCTION)
    assert maplight["status"] == "G2_2_MAPLIGHT_REPRODUCED"
    assert maplight["component_macro_mae"] == MAPLIGHT_DEVELOPMENT_COMPONENT_MACRO_MAE
    _assert_contains(
        maplight["interpretation"],
        "Prior family-safe internal development evidence only",
        "not an official challenge metric",
        "leaderboard score",
        "reselection",
        "G4 selection",
        "G2-7G robustness acceptance",
    )
    assert maplight["interpretation"] == (
        "Prior family-safe internal development evidence only; not an official "
        "challenge metric, leaderboard score, reselection, G4 selection, or "
        "G2-7G robustness acceptance."
    )
    _validate_ledger_rows(evidence["exact_ledger_rows"])
    _assert_contains(
        evidence["precedence"],
        "immutable evidence, not current operational authority",
        "D149 and this later contract control current action",
    )
    assert evidence["precedence"] == (
        "Historical D075, D076, validator, and handoff statements are immutable "
        "evidence, not current operational authority. D149 and this later "
        "contract control current action."
    )

    state = _mapping(contract["current_candidate_state"])
    assert tuple(state) == (
        "candidate_existence",
        "root_type_and_mode",
        "root_entry_set",
        "submission_existence",
        "submission_bytes",
        "submission_sha256",
        "manifest_existence",
        "manifest_bytes",
        "manifest_sha256",
        "current_validator_result",
        "current_live_backend_parity",
        "current_portal_state",
        "current_leaderboard_state",
        "reauthenticated",
        "upload_ready",
        "selected_by_g4",
        "robustness_accepted_by_g2_7g",
        "g2_8_status",
    )
    for key in (
        "candidate_existence",
        "root_type_and_mode",
        "root_entry_set",
        "submission_existence",
        "submission_bytes",
        "submission_sha256",
        "manifest_existence",
        "manifest_bytes",
        "manifest_sha256",
        "current_portal_state",
        "current_leaderboard_state",
    ):
        assert state[key] == "unknown_unopened"
    assert state["current_validator_result"] == "unknown_not_invoked"
    assert state["current_live_backend_parity"] == "unknown_unresolved"
    for key in (
        "reauthenticated",
        "upload_ready",
        "selected_by_g4",
        "robustness_accepted_by_g2_7g",
    ):
        _assert_bool(state[key], False)
    assert state["g2_8_status"] == "CLOSED"

    authority = _mapping(contract["current_authority"])
    assert tuple(authority) == (
        "read_private_candidate_now",
        "resolve_private_candidate_locator_now",
        "invoke_candidate_or_official_competition_validator_now",
        "open_official_data_now",
        "generate_or_regenerate_submission",
        "copy_or_reserialize_candidate",
        "open_portal_or_credentials",
        "observe_leaderboard",
        "upload",
        "upload_authority",
        "future_single_use_read_only_reauthentication_after_all_prerequisites",
        "future_result_is_separate_milestone",
    )
    for key in tuple(authority)[:10]:
        _assert_bool(authority[key], False)
    for key in tuple(authority)[10:]:
        _assert_bool(authority[key], True)

    accounting = _mapping(contract["contract_milestone_accounting"])
    assert tuple(accounting) == (
        "scope",
        "tracked_public_handoff_locator_reference_read_and_bound",
        "private_candidate_filesystem_locator_resolution_or_access_attempts",
        "private_candidate_roots_opened",
        "private_candidate_directory_entries_read",
        "private_candidate_files_opened",
        "private_candidate_bytes_read",
        "private_candidate_hashes_computed",
        "candidate_or_official_competition_validator_calls",
        "private_candidate_validator_calls",
        "official_dataset_files_opened",
        "official_rows_opened",
        "official_target_values_opened",
        "official_metric_calls",
        "model_fits",
        "predictions_generated",
        "submission_rows_generated",
        "candidate_copies_or_reserializations",
        "portal_credentials_opened",
        "portal_pages_opened",
        "leaderboard_observations",
        "uploads",
        "future_reauthentication_attempts_consumed",
        "public_repository_validation_validator_import_cache_network_and_internal_totals_retained",
        "public_repository_validation_rule",
    )
    _assert_contains(
        accounting["scope"],
        "D150 contract-milestone candidate/private/official/portal operations only",
        "Ordinary tracked-public repository reads and validation are not candidate execution",
    )
    assert accounting["scope"] == (
        "D150 contract-milestone candidate/private/official/portal operations "
        "only. Ordinary tracked-public repository reads and validation are not "
        "candidate execution."
    )
    _assert_bool(
        accounting["tracked_public_handoff_locator_reference_read_and_bound"], True
    )
    for key in tuple(accounting)[2:23]:
        _assert_zero(accounting[key])
    _assert_bool(
        accounting[
            "public_repository_validation_validator_import_cache_network_and_internal_totals_retained"
        ],
        False,
    )
    _assert_contains(
        accounting["public_repository_validation_rule"],
        "Uninstrumented public-CI validator, network, cache, import, fit, metric, and suite-internal operation totals remain unknown",
        "not guessed as zero",
        "do not alter the scoped candidate/private zeros",
    )
    assert accounting["public_repository_validation_rule"] == (
        "Uninstrumented public-CI validator, network, cache, import, fit, metric, "
        "and suite-internal operation totals remain unknown, are not guessed as "
        "zero, and do not alter the scoped candidate/private zeros."
    )

    future = _mapping(contract["future_single_use_read_only_reauthentication"])
    assert tuple(future) == (
        "activation_state",
        "prerequisites_satisfied_by_this_contract",
        "prerequisites",
        "attempt",
        "locator_resolution",
        "filesystem_preflight",
        "files",
        "byte_hash_protocol",
        "cleanup_and_publication",
        "forbidden_operations",
        "success_effect",
        "failure_effect",
    )
    assert future["activation_state"] == (
        "blocked_pending_review_signed_integration_and_post_main_ci"
    )
    _assert_bool(future["prerequisites_satisfied_by_this_contract"], False)

    prerequisites = _mapping(future["prerequisites"])
    assert tuple(prerequisites) == (
        "semantics",
        "contract_reviewed_and_integrated_as_one_ssh_signed_zchboswell_commit",
        "exact_head_pull_request_checks_green",
        "local_fast_forward_only_integration_without_commit_rewrite",
        "exact_sha_post_main_ci_green",
        "worktree_clean_and_parent_evidence_exact",
        "private_candidate_contact_before_prerequisites",
    )
    _assert_contains(
        prerequisites["semantics"],
        "Every true value below is a future mandatory condition",
        "not a claim that this unintegrated contract already satisfies it",
    )
    assert prerequisites["semantics"] == (
        "Every true value below is a future mandatory condition, not a claim "
        "that this unintegrated contract already satisfies it."
    )
    for key in tuple(prerequisites)[1:6]:
        _assert_bool(prerequisites[key], True)
    _assert_bool(prerequisites["private_candidate_contact_before_prerequisites"], False)

    attempt = _mapping(future["attempt"])
    assert tuple(attempt) == (
        "maximum_invocations",
        "invocations_consumed_by_this_contract",
        "retry",
        "resume",
        "repair",
        "replacement",
        "copy_to_fresh_root",
        "second_attempt_if_ambiguous",
        "any_started_private_locator_resolution_consumes_invocation",
        "result_must_be_separate_immutable_milestone",
    )
    assert type(attempt["maximum_invocations"]) is int
    assert attempt["maximum_invocations"] == 1
    _assert_zero(attempt["invocations_consumed_by_this_contract"])
    for key in (
        "retry",
        "resume",
        "repair",
        "replacement",
        "copy_to_fresh_root",
        "second_attempt_if_ambiguous",
    ):
        _assert_bool(attempt[key], False)
    _assert_bool(
        attempt["any_started_private_locator_resolution_consumes_invocation"], True
    )
    _assert_bool(attempt["result_must_be_separate_immutable_milestone"], True)

    locator = _mapping(future["locator_resolution"])
    assert tuple(locator) == (
        "sole_source_path",
        "sole_source_sha256",
        "expected_exact_locator",
        "resolve_only_after_authenticating_exact_tracked_handoff_bytes",
        "private_filesystem_locator_resolution_count",
        "alternate_locator_or_search",
        "environment_variable_or_glob_locator",
        "portal_or_credential_locator",
    )
    assert locator["sole_source_path"] == PUBLIC_HANDOFF["path"]
    assert locator["sole_source_sha256"] == PUBLIC_HANDOFF["sha256"]
    assert locator["expected_exact_locator"] == (
        "unique_Accepted_root_value_resolved_privately_from_authenticated_tracked_handoff_not_republished"
    )
    _assert_bool(
        locator["resolve_only_after_authenticating_exact_tracked_handoff_bytes"], True
    )
    assert type(locator["private_filesystem_locator_resolution_count"]) is int
    assert locator["private_filesystem_locator_resolution_count"] == 1
    for key in (
        "alternate_locator_or_search",
        "environment_variable_or_glob_locator",
        "portal_or_credential_locator",
    ):
        _assert_bool(locator[key], False)

    filesystem = _mapping(future["filesystem_preflight"])
    assert tuple(filesystem) == (
        "successful_root_open_count_on_success",
        "root_open_attempts_maximum",
        "successful_root_enumeration_count_on_success",
        "root_enumeration_attempts_maximum",
        "root_must_be_real_directory_not_symlink",
        "directory_fd_identity_must_match_privately_extracted_locator",
        "separate_realpath_call_required",
        "root_mode_exact",
        "exact_sorted_entries",
        "extra_or_missing_entry_fails_closed",
        "stop_immediately_after_first_defect_with_zero_later_operations",
        "nofollow_root_and_files",
        "path_traversal_or_recursive_search",
    )
    for key in (
        "successful_root_open_count_on_success",
        "root_open_attempts_maximum",
        "successful_root_enumeration_count_on_success",
        "root_enumeration_attempts_maximum",
    ):
        assert type(filesystem[key]) is int
        assert filesystem[key] == 1
    _assert_bool(filesystem["root_must_be_real_directory_not_symlink"], True)
    _assert_bool(
        filesystem["directory_fd_identity_must_match_privately_extracted_locator"],
        True,
    )
    _assert_bool(filesystem["separate_realpath_call_required"], False)
    assert filesystem["root_mode_exact"] == "0555"
    assert tuple(_sequence(filesystem["exact_sorted_entries"])) == (
        "manifest.json",
        "submission.csv",
    )
    _assert_bool(filesystem["extra_or_missing_entry_fails_closed"], True)
    _assert_bool(
        filesystem["stop_immediately_after_first_defect_with_zero_later_operations"],
        True,
    )
    _assert_bool(filesystem["nofollow_root_and_files"], True)
    _assert_bool(filesystem["path_traversal_or_recursive_search"], False)

    files = tuple(_mapping(item) for item in _sequence(future["files"]))
    assert len(files) == 2
    assert all(
        tuple(item)
        == (
            "name",
            "expected_sha256",
            "type",
            "mode_exact",
            "maximum_open_count",
            "parse_or_deserialize",
        )
        for item in files
    )
    assert files[0]["name"] == "manifest.json"
    assert files[0]["expected_sha256"] == MANIFEST_SHA256
    assert files[1]["name"] == "submission.csv"
    assert files[1]["expected_sha256"] == SUBMISSION_SHA256
    for item in files:
        assert item["type"] == "regular_file_not_symlink"
        assert item["mode_exact"] == "0444"
        assert type(item["maximum_open_count"]) is int
        assert item["maximum_open_count"] == 1
        _assert_bool(item["parse_or_deserialize"], False)

    protocol = _mapping(future["byte_hash_protocol"])
    assert tuple(protocol) == (
        "open_flags",
        "whole_file_bytes_read_into_memory_only",
        "candidate_files_opened_exactly_once_each_on_success",
        "candidate_file_open_attempts_maximum_each",
        "stable_fstat_before_and_after_read_required",
        "stable_fstat_fields",
        "sha256_computed_in_memory",
        "expected_hashes_required_exactly",
        "candidate_bytes_written_or_retained",
        "temporary_files_or_copies",
        "csv_parse",
        "json_parse",
        "candidate_or_official_competition_validator_call",
        "private_candidate_validator_call",
        "official_data_open",
        "network_or_portal_access",
        "upload",
    )
    assert protocol["open_flags"] == (
        "read_only_and_nofollow_relative_to_authenticated_root_directory"
    )
    for key in (
        "whole_file_bytes_read_into_memory_only",
        "candidate_files_opened_exactly_once_each_on_success",
        "stable_fstat_before_and_after_read_required",
        "sha256_computed_in_memory",
        "expected_hashes_required_exactly",
    ):
        _assert_bool(protocol[key], True)
    assert type(protocol["candidate_file_open_attempts_maximum_each"]) is int
    assert protocol["candidate_file_open_attempts_maximum_each"] == 1
    assert tuple(_sequence(protocol["stable_fstat_fields"])) == (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_nlink",
        "st_uid",
        "st_gid",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    for key in (
        "candidate_bytes_written_or_retained",
        "temporary_files_or_copies",
        "csv_parse",
        "json_parse",
        "candidate_or_official_competition_validator_call",
        "private_candidate_validator_call",
        "official_data_open",
        "network_or_portal_access",
        "upload",
    ):
        _assert_bool(protocol[key], False)

    cleanup = _mapping(future["cleanup_and_publication"])
    assert tuple(cleanup) == (
        "close_root_and_file_descriptors_before_result",
        "discard_all_in_memory_candidate_bytes_before_result",
        "retain_or_publish_private_locator_path_or_candidate_bytes",
        "retain_or_publish_private_stat_metadata",
        "retain_only_expected_public_hashes_and_aggregate_outcome_accounting",
        "cleanup_must_complete_before_result_publication",
        "result_path",
        "result_schema_version",
        "result_publication_count_maximum",
        "safe_success_or_safe_classified_failure_publication_count",
        "result_publication_no_replace",
        "result_is_not_part_of_this_contract_package",
        "crash_ambiguous_cleanup_or_publication_failure_may_leave_result_absent",
        "crash_ambiguous_cleanup_or_publication_failure_effect",
        "external_handoff_rule",
    )
    for key in (
        "close_root_and_file_descriptors_before_result",
        "discard_all_in_memory_candidate_bytes_before_result",
        "retain_only_expected_public_hashes_and_aggregate_outcome_accounting",
        "cleanup_must_complete_before_result_publication",
        "result_publication_no_replace",
        "result_is_not_part_of_this_contract_package",
        "crash_ambiguous_cleanup_or_publication_failure_may_leave_result_absent",
    ):
        _assert_bool(cleanup[key], True)
    for key in (
        "retain_or_publish_private_locator_path_or_candidate_bytes",
        "retain_or_publish_private_stat_metadata",
    ):
        _assert_bool(cleanup[key], False)
    assert cleanup["result_path"] == (
        "benchmarks/openadmet_cyp_2026/direct_baseline_reauthentication_result.json"
    )
    _assert_public_path(cleanup["result_path"])
    assert cleanup["result_schema_version"] == (
        "cypshift.openadmet_cyp_2026.direct_baseline_reauthentication_result.v1"
    )
    for key in (
        "result_publication_count_maximum",
        "safe_success_or_safe_classified_failure_publication_count",
    ):
        assert type(cleanup[key]) is int
        assert cleanup[key] == 1
    _assert_contains(
        cleanup["crash_ambiguous_cleanup_or_publication_failure_effect"],
        FUTURE_FAILURE,
        ROUTE_WITHDRAWN,
    )
    assert cleanup["crash_ambiguous_cleanup_or_publication_failure_effect"] == (
        "DIRECT_BASELINE_REAUTHENTICATION_FAILED_CLOSED_and_"
        "DIRECT_BASELINE_ROUTE_WITHDRAWN"
    )
    _assert_contains(
        cleanup["external_handoff_rule"],
        "durable evidence shows the private invocation began",
        "no-replace result is absent or cannot be authenticated",
        "invocation as consumed",
        "route as withdrawn",
        "Do not rerun, repair, replace, or publish a fabricated success",
    )
    assert cleanup["external_handoff_rule"] == (
        "If durable evidence shows the private invocation began but the no-replace "
        "result is absent or cannot be authenticated, treat the invocation as "
        "consumed and the route as withdrawn. Do not rerun, repair, replace, or "
        "publish a fabricated success."
    )

    assert tuple(_sequence(future["forbidden_operations"])) == (
        "candidate generation or regeneration",
        (
            "candidate copy, move, chmod, chown, touch, repair, replacement, "
            "reserialization, parsing, or validation"
        ),
        "official dataset, label, feature, structure, row, metric, or scoring access",
        (
            "model fit, prediction, calibration, clipping, ensemble, selection, "
            "or transduction"
        ),
        "portal, browser, credential, leaderboard, network, or upload access",
        (
            "retry, resume, alternate locator, recursive search, second attempt, "
            "or post-failure remedy"
        ),
    )

    success = _mapping(future["success_effect"])
    assert tuple(success) == (
        "required_result_status",
        "route_state",
        "candidate_bytes_authenticated",
        "candidate_selected_or_robustness_accepted",
        "g2_8_reopened",
        "validator_current",
        "upload_ready_claimed",
        "upload_authority",
        "next_action",
    )
    assert success["required_result_status"] == FUTURE_SUCCESS
    assert success["route_state"] == "DIRECT_BASELINE_ROUTE_REAUTHENTICATED"
    _assert_bool(success["candidate_bytes_authenticated"], True)
    for key in (
        "candidate_selected_or_robustness_accepted",
        "g2_8_reopened",
        "validator_current",
        "upload_ready_claimed",
        "upload_authority",
    ):
        _assert_bool(success[key], False)
    _assert_contains(
        success["next_action"],
        "Stop",
        "Preserve the read-only result",
        "later separate human-authorized operation",
    )
    assert success["next_action"] == (
        "Stop. Preserve the read-only result. Any upload remains a later separate "
        "human-authorized operation."
    )

    failure = _mapping(future["failure_effect"])
    assert tuple(failure) == (
        "safe_classified_failure_result_status",
        "ambiguous_or_absent_result_effective_status",
        "route_state",
        "triggers",
        "invocation_consumed",
        "retry_or_remedy",
        "candidate_upload_ready",
        "upload_authority",
        "competition_backout",
    )
    assert failure["safe_classified_failure_result_status"] == FUTURE_FAILURE
    assert failure["ambiguous_or_absent_result_effective_status"] == FUTURE_FAILURE
    assert failure["route_state"] == ROUTE_WITHDRAWN
    triggers = tuple(_sequence(failure["triggers"]))
    assert len(triggers) == 4
    _assert_contains(
        triggers[0],
        "missing",
        "unreadable",
        "ambiguous",
        "symlinked",
        "non-regular",
        "mode-drifted",
        "extra-entry",
        "unstable",
    )
    assert triggers[0] == (
        "missing, unreadable, ambiguous, symlinked, non-regular, mode-drifted, "
        "extra-entry, or unstable root or file"
    )
    assert triggers[1] == "submission or manifest SHA-256 mismatch"
    assert triggers[2] == (
        "tracked handoff or bound latest-tracked public requirement snapshot identity mismatch"
    )
    _assert_contains(
        triggers[3],
        "any forbidden operation",
        "accounting uncertainty inside the private attempt",
        "cleanup defect",
        "need for retry, repair, replacement, alternate locator, validator, official data, portal, credential, or upload access",
    )
    assert triggers[3] == (
        "any forbidden operation, accounting uncertainty inside the private "
        "attempt, cleanup defect, or need for retry, repair, replacement, "
        "alternate locator, validator, official data, portal, credential, or "
        "upload access"
    )
    _assert_bool(failure["invocation_consumed"], True)
    for key in ("retry_or_remedy", "candidate_upload_ready", "upload_authority"):
        _assert_bool(failure[key], False)
    _assert_contains(
        failure["competition_backout"],
        "Withdraw the direct-baseline route",
        "Do not upload, regenerate, or substitute a candidate",
    )
    assert failure["competition_backout"] == (
        "Withdraw the direct-baseline route. Do not upload, regenerate, or "
        "substitute a candidate under this contract."
    )

    taxonomy = _mapping(contract["future_status_taxonomy"])
    assert tuple(taxonomy) == (
        "contract_status",
        "sole_success_status",
        "sole_failure_status",
        "failure_route_state",
        "success_and_failure_are_terminal_for_the_single_invocation",
        "ambiguous_or_second_attempt_needed_is_failure",
        "started_invocation_with_absent_or_unauthentic_result_is_consumed_and_withdrawn",
        "all_success_failure_and_absent_result_states_preserve_upload_authority_false",
    )
    assert taxonomy["contract_status"] == STATUS
    assert taxonomy["sole_success_status"] == FUTURE_SUCCESS
    assert taxonomy["sole_failure_status"] == FUTURE_FAILURE
    assert taxonomy["failure_route_state"] == ROUTE_WITHDRAWN
    for key in tuple(taxonomy)[4:]:
        _assert_bool(taxonomy[key], True)

    package = _mapping(contract["exact_package_scope"])
    assert tuple(package) == (
        "exact_path_count",
        "exact_paths",
        "contract_paths",
        "test_paths",
        "narrative_paths",
        "ledger_paths",
        "implementation_paths",
        "result_paths",
        "private_paths",
    )
    assert type(package["exact_path_count"]) is int
    assert package["exact_path_count"] == 9
    assert tuple(_sequence(package["exact_paths"])) == D150_PATHS
    assert type(package["contract_paths"]) is int and package["contract_paths"] == 1
    assert type(package["test_paths"]) is int and package["test_paths"] == 1
    assert type(package["narrative_paths"]) is int and package["narrative_paths"] == 6
    assert type(package["ledger_paths"]) is int and package["ledger_paths"] == 1
    for key in ("implementation_paths", "result_paths", "private_paths"):
        _assert_zero(package[key])
    for path_text in D150_PATHS:
        _assert_public_path(path_text)

    _assert_contains(
        contract["invalidation"],
        "D149 parent, tracked handoff, latest-tracked public requirement snapshot, historical candidate, MapLight development, or exact ledger-row identity drifts",
        "current private candidate filesystem locator is resolved or candidate byte is opened",
        "candidate, private, or official-competition validator, official-data, metric, portal, credential, leaderboard, or upload operation occurs",
        "current existence or upload readiness is claimed",
        "MapLight is called G4-selected or G2-7G robustness-accepted",
        "G2-8 or G4 is reopened",
        "changed-path set differs in any way from the exact nine-path allowlist",
        "any required path absent or any outside path present",
        "public-CI suite-internal synthetic validator imports or calls and other unknown totals are incorrectly treated as scoped candidate operations or guessed as zero",
        "parsing, copying, reserialization, retry, repair, replacement, alternate search, more than one file open each, private locator/stat publication, a separate realpath resolution, or publication before cleanup",
        "failure does not withdraw the route",
    )
    assert contract["invalidation"] == (
        "Invalidate and do not integrate this contract package if the D149 parent, "
        "tracked handoff, latest-tracked public requirement snapshot, historical "
        "candidate, MapLight development, or exact ledger-row identity drifts; any "
        "current private candidate filesystem locator is resolved or candidate byte "
        "is opened; any candidate, private, or official-competition validator, "
        "official-data, metric, portal, credential, leaderboard, or upload operation "
        "occurs; current existence or upload readiness is claimed; MapLight is called "
        "G4-selected or G2-7G robustness-accepted; G2-8 or G4 is reopened; the "
        "changed-path set differs in any way from the exact nine-path allowlist, "
        "including any required path absent or any outside path present; public-CI "
        "suite-internal synthetic validator imports or calls and other unknown totals "
        "are incorrectly treated as scoped candidate operations or guessed as zero; "
        "the one-use future protocol permits parsing, copying, reserialization, "
        "retry, repair, replacement, alternate search, more than one file open each, "
        "private locator/stat publication, a separate realpath resolution, or "
        "publication before cleanup; or failure does not withdraw the route."
    )

    backout = _mapping(contract["competitive_backout"])
    assert tuple(backout) == (
        "continue_now",
        "continue_after_success",
        "back_out_after_failure_or_ambiguity",
        "g4_terminal",
        "g2_8_status",
        "alternate_model_or_candidate_authorized",
    )
    _assert_contains(
        backout["continue_now"],
        "historically accepted candidate remains the strongest defensible direct route",
        "no current-byte or upload-readiness claim",
    )
    assert backout["continue_now"] == (
        "Freeze this contract because the historically accepted candidate remains "
        "the strongest defensible direct route, while making no current-byte or "
        "upload-readiness claim."
    )
    _assert_contains(
        backout["continue_after_success"],
        "separate exact read-only success",
        "later explicit human upload authorization",
        "does not itself authorize upload",
    )
    assert backout["continue_after_success"] == (
        "A separate exact read-only success may preserve the route for later "
        "explicit human upload authorization; it does not itself authorize upload."
    )
    _assert_contains(
        backout["back_out_after_failure_or_ambiguity"],
        ROUTE_WITHDRAWN,
        "without retry, regeneration, substitution, validator rescue, portal access, or upload",
    )
    assert backout["back_out_after_failure_or_ambiguity"] == (
        "Set DIRECT_BASELINE_ROUTE_WITHDRAWN and stop the direct submission route "
        "without retry, regeneration, substitution, validator rescue, portal "
        "access, or upload."
    )
    _assert_bool(backout["g4_terminal"], True)
    assert backout["g2_8_status"] == "CLOSED"
    _assert_bool(backout["alternate_model_or_candidate_authorized"], False)

    _assert_contains(
        contract["next_gate"],
        "exact nine-path contract-only package",
        "one SSH-signed zchboswell commit",
        "exact-head green pull-request checks",
        "local fast-forward-only integration without rewrite",
        "green exact-SHA post-main CI",
        "at most one separately recorded read-only hash reauthentication exactly as frozen",
        FUTURE_SUCCESS,
        "no upload authority",
        FUTURE_FAILURE,
        ROUTE_WITHDRAWN,
    )
    assert contract["next_gate"] == (
        "Review only this exact nine-path contract-only package. After one "
        "SSH-signed zchboswell commit, exact-head green pull-request checks, local "
        "fast-forward-only integration without rewrite, and green exact-SHA "
        "post-main CI, execute at most one separately recorded read-only hash "
        "reauthentication exactly as frozen. Success stops at "
        "DIRECT_BASELINE_REAUTHENTICATED_READ_ONLY with no upload authority. Any "
        "failure, ambiguity, or need for another attempt records "
        "DIRECT_BASELINE_REAUTHENTICATION_FAILED_CLOSED and "
        "DIRECT_BASELINE_ROUTE_WITHDRAWN."
    )
    _validate_no_sensitive_path_publication(contract)


def test_static_audit_source_has_no_execution_or_external_io_capability() -> None:
    source_path = Path(__file__).resolve()
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=source_path.as_posix(), feature_version=(3, 10))

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module is not None
            imports.add(node.module)

    assert imports == {
        "__future__",
        "ast",
        "collections.abc",
        "copy",
        "csv",
        "hashlib",
        "io",
        "json",
        "math",
        "pathlib",
        "pytest",
        "re",
        "typing",
    }
    assert imports.isdisjoint(
        {
            "catboost",
            "importlib",
            "numpy",
            "os",
            "pandas",
            "rdkit",
            "requests",
            "shutil",
            "socket",
            "subprocess",
            "sys",
            "torch",
            "urllib",
        }
    )
    forbidden_name_calls = {
        "compile",
        "eval",
        "exec",
        "open",
        "__import__",
    }
    forbidden_attribute_calls = {
        "system",
        "popen",
        "run",
        "Popen",
        "urlopen",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_name_calls
        elif isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_attribute_calls

    forbidden_source_fragments = (
        "run_global_v2_" + "maplight",
        "global_v2_" + "maplight_runner",
        "validate_activity_" + "submission",
        "cypshift" + "-private",
        "/" + "home/",
        "portal." + "openadmet",
        "api." + "openadmet",
    )
    assert all(fragment not in source for fragment in forbidden_source_fragments)


def test_contract_is_strict_canonical_exact_and_contract_only() -> None:
    raw = CONTRACT.read_bytes()
    contract = _strict_load(raw)
    assert raw == _canonical_bytes(contract)
    assert len(raw) == CONTRACT_SIZE_BYTES
    assert raw.count(b"\n") == CONTRACT_LINES_LF
    assert b"\r" not in raw
    assert hashlib.sha256(raw).hexdigest() == CONTRACT_SHA256
    _validate_contract(contract)


def test_exact_public_ledger_lineage_and_parent_files_are_immutable() -> None:
    _validate_ledger_rows([dict(row) for row in LEDGER_ROWS])
    _assert_public_receipt(D149_RECORD)
    _assert_public_receipt(PUBLIC_HANDOFF)


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


def test_contract_mutations_fail_closed() -> None:
    contract = _strict_load(CONTRACT.read_bytes())
    _validate_contract(contract)
    mutations: list[tuple[str, tuple[str | int, ...], Any]] = [
        ("schema drift", ("schema_version",), "wrong.v1"),
        ("status drift", ("status",), FUTURE_SUCCESS),
        ("gate drift", ("gate",), FUTURE_SUCCESS),
        ("record id drift", ("record_id",), "OTHER"),
        ("truthy nonbool contract only", ("contract_only",), 1),
        (
            "purpose grants upload",
            ("purpose",),
            str(contract["purpose"]) + " Upload is authorized.",
        ),
        (
            "D149 commit drift",
            ("immutable_d149_parent", "integrated_commit"),
            "0" * 40,
        ),
        (
            "D149 PR drift",
            ("immutable_d149_parent", "integration_proof", "pull_request"),
            185,
        ),
        (
            "D149 PR CI drift",
            (
                "immutable_d149_parent",
                "integration_proof",
                "exact_head_pull_request_ci_run",
            ),
            0,
        ),
        (
            "D149 post-main CI drift",
            (
                "immutable_d149_parent",
                "integration_proof",
                "exact_sha_post_main_ci_run",
            ),
            0,
        ),
        (
            "truthy nonbool CI green",
            ("immutable_d149_parent", "integration_proof", "post_main_ci_green"),
            1,
        ),
        (
            "rewrite integration",
            ("immutable_d149_parent", "integration_proof", "integration_method"),
            "hosted_rebase",
        ),
        (
            "D149 rejection hash drift",
            ("immutable_d149_parent", "transition_rejection", "sha256"),
            "0" * 64,
        ),
        (
            "D149 test hash drift",
            ("immutable_d149_parent", "transition_rejection_test", "sha256"),
            "0" * 64,
        ),
        (
            "D149 ledger parent drift",
            ("immutable_d149_parent", "experiment_ledger_parent", "sha256"),
            "0" * 64,
        ),
        (
            "tracked handoff hash drift",
            ("immutable_public_evidence", "tracked_handoff", "sha256"),
            "0" * 64,
        ),
        (
            "private locator publication",
            (
                "immutable_public_evidence",
                "tracked_handoff",
                "historical_candidate_locator",
            ),
            "/" + "home/example/private/candidate",
        ),
        (
            "live refresh overclaim",
            (
                "immutable_public_evidence",
                "latest_tracked_public_requirement_snapshot",
                "live_public_rule_refresh_performed",
            ),
            True,
        ),
        (
            "live current rules overclaim",
            (
                "immutable_public_evidence",
                "latest_tracked_public_requirement_snapshot",
                "live_current_rules_claimed",
            ),
            True,
        ),
        (
            "dataset head drift",
            (
                "immutable_public_evidence",
                "latest_tracked_public_requirement_snapshot",
                "repository_heads",
                "dataset",
            ),
            "0" * 40,
        ),
        (
            "public requirement hash drift",
            (
                "immutable_public_evidence",
                "latest_tracked_public_requirement_snapshot",
                "tracked_files",
                0,
                "sha256",
            ),
            "0" * 64,
        ),
        (
            "unresolved row order guessed",
            (
                "immutable_public_evidence",
                "latest_tracked_public_requirement_snapshot",
                "direct_requirements",
                "row_order",
            ),
            "required",
        ),
        (
            "truthy nonbool rows",
            (
                "immutable_public_evidence",
                "latest_tracked_public_requirement_snapshot",
                "direct_requirements",
                "rows",
            ),
            True,
        ),
        (
            "global-v2 contract drift",
            ("immutable_public_evidence", "global_v2_experiment_contract", "sha256"),
            "0" * 64,
        ),
        (
            "submission hash drift",
            (
                "immutable_public_evidence",
                "historical_candidate_identity",
                "submission_sha256",
            ),
            "0" * 64,
        ),
        (
            "manifest hash drift",
            (
                "immutable_public_evidence",
                "historical_candidate_identity",
                "manifest_sha256",
            ),
            "0" * 64,
        ),
        (
            "reserialization allowed",
            (
                "immutable_public_evidence",
                "historical_candidate_identity",
                "bytes_may_be_reserialized",
            ),
            True,
        ),
        (
            "historical validator made current",
            (
                "immutable_public_evidence",
                "historical_candidate_identity",
                "historical_validator",
                "authority",
            ),
            "current_validator_authority",
        ),
        (
            "historical validator truthy nonbool errors",
            (
                "immutable_public_evidence",
                "historical_candidate_identity",
                "historical_validator",
                "errors",
            ),
            False,
        ),
        (
            "MapLight MAE drift",
            (
                "immutable_public_evidence",
                "fixed_maplight_internal_development_evidence",
                "component_macro_mae",
            ),
            0.58,
        ),
        (
            "ledger wrong row substitution",
            ("immutable_public_evidence", "exact_ledger_rows", 2, "physical_line"),
            128,
        ),
        (
            "ledger row hash drift",
            ("immutable_public_evidence", "exact_ledger_rows", 4, "sha256"),
            "0" * 64,
        ),
        (
            "prerequisite activation early",
            ("future_single_use_read_only_reauthentication", "activation_state"),
            "active",
        ),
        (
            "prerequisites falsely satisfied",
            (
                "future_single_use_read_only_reauthentication",
                "prerequisites_satisfied_by_this_contract",
            ),
            True,
        ),
        (
            "maximum invocations two",
            (
                "future_single_use_read_only_reauthentication",
                "attempt",
                "maximum_invocations",
            ),
            2,
        ),
        (
            "truthy nonbool maximum invocations",
            (
                "future_single_use_read_only_reauthentication",
                "attempt",
                "maximum_invocations",
            ),
            True,
        ),
        (
            "retry authorized",
            ("future_single_use_read_only_reauthentication", "attempt", "retry"),
            True,
        ),
        (
            "resume authorized",
            ("future_single_use_read_only_reauthentication", "attempt", "resume"),
            True,
        ),
        (
            "repair authorized",
            ("future_single_use_read_only_reauthentication", "attempt", "repair"),
            True,
        ),
        (
            "replacement authorized",
            (
                "future_single_use_read_only_reauthentication",
                "attempt",
                "replacement",
            ),
            True,
        ),
        (
            "second ambiguous attempt",
            (
                "future_single_use_read_only_reauthentication",
                "attempt",
                "second_attempt_if_ambiguous",
            ),
            True,
        ),
        (
            "started locator does not consume",
            (
                "future_single_use_read_only_reauthentication",
                "attempt",
                "any_started_private_locator_resolution_consumes_invocation",
            ),
            False,
        ),
        (
            "locator resolves before handoff auth",
            (
                "future_single_use_read_only_reauthentication",
                "locator_resolution",
                "resolve_only_after_authenticating_exact_tracked_handoff_bytes",
            ),
            False,
        ),
        (
            "locator resolution twice",
            (
                "future_single_use_read_only_reauthentication",
                "locator_resolution",
                "private_filesystem_locator_resolution_count",
            ),
            2,
        ),
        (
            "alternate locator search",
            (
                "future_single_use_read_only_reauthentication",
                "locator_resolution",
                "alternate_locator_or_search",
            ),
            True,
        ),
        (
            "environment glob locator",
            (
                "future_single_use_read_only_reauthentication",
                "locator_resolution",
                "environment_variable_or_glob_locator",
            ),
            True,
        ),
        (
            "root open attempt two",
            (
                "future_single_use_read_only_reauthentication",
                "filesystem_preflight",
                "root_open_attempts_maximum",
            ),
            2,
        ),
        (
            "success open conflated with zero",
            (
                "future_single_use_read_only_reauthentication",
                "filesystem_preflight",
                "successful_root_open_count_on_success",
            ),
            0,
        ),
        (
            "realpath call enabled",
            (
                "future_single_use_read_only_reauthentication",
                "filesystem_preflight",
                "separate_realpath_call_required",
            ),
            True,
        ),
        (
            "later operations after defect",
            (
                "future_single_use_read_only_reauthentication",
                "filesystem_preflight",
                "stop_immediately_after_first_defect_with_zero_later_operations",
            ),
            False,
        ),
        (
            "recursive path search",
            (
                "future_single_use_read_only_reauthentication",
                "filesystem_preflight",
                "path_traversal_or_recursive_search",
            ),
            True,
        ),
        (
            "file parse enabled",
            (
                "future_single_use_read_only_reauthentication",
                "files",
                0,
                "parse_or_deserialize",
            ),
            True,
        ),
        (
            "file open twice",
            (
                "future_single_use_read_only_reauthentication",
                "files",
                1,
                "maximum_open_count",
            ),
            2,
        ),
        (
            "candidate open attempts twice",
            (
                "future_single_use_read_only_reauthentication",
                "byte_hash_protocol",
                "candidate_file_open_attempts_maximum_each",
            ),
            2,
        ),
        (
            "CSV parse enabled",
            (
                "future_single_use_read_only_reauthentication",
                "byte_hash_protocol",
                "csv_parse",
            ),
            True,
        ),
        (
            "JSON parse enabled",
            (
                "future_single_use_read_only_reauthentication",
                "byte_hash_protocol",
                "json_parse",
            ),
            True,
        ),
        (
            "competition validator enabled",
            (
                "future_single_use_read_only_reauthentication",
                "byte_hash_protocol",
                "candidate_or_official_competition_validator_call",
            ),
            True,
        ),
        (
            "private validator enabled",
            (
                "future_single_use_read_only_reauthentication",
                "byte_hash_protocol",
                "private_candidate_validator_call",
            ),
            True,
        ),
        (
            "candidate bytes retained",
            (
                "future_single_use_read_only_reauthentication",
                "byte_hash_protocol",
                "candidate_bytes_written_or_retained",
            ),
            True,
        ),
        (
            "network enabled",
            (
                "future_single_use_read_only_reauthentication",
                "byte_hash_protocol",
                "network_or_portal_access",
            ),
            True,
        ),
        (
            "upload enabled",
            (
                "future_single_use_read_only_reauthentication",
                "byte_hash_protocol",
                "upload",
            ),
            True,
        ),
        (
            "descriptors left open",
            (
                "future_single_use_read_only_reauthentication",
                "cleanup_and_publication",
                "close_root_and_file_descriptors_before_result",
            ),
            False,
        ),
        (
            "private stat publication",
            (
                "future_single_use_read_only_reauthentication",
                "cleanup_and_publication",
                "retain_or_publish_private_stat_metadata",
            ),
            True,
        ),
        (
            "result publication twice",
            (
                "future_single_use_read_only_reauthentication",
                "cleanup_and_publication",
                "result_publication_count_maximum",
            ),
            2,
        ),
        (
            "result replace allowed",
            (
                "future_single_use_read_only_reauthentication",
                "cleanup_and_publication",
                "result_publication_no_replace",
            ),
            False,
        ),
        (
            "ambiguous crash claims result mandatory",
            (
                "future_single_use_read_only_reauthentication",
                "cleanup_and_publication",
                "crash_ambiguous_cleanup_or_publication_failure_may_leave_result_absent",
            ),
            False,
        ),
        (
            "success grants selection",
            (
                "future_single_use_read_only_reauthentication",
                "success_effect",
                "candidate_selected_or_robustness_accepted",
            ),
            True,
        ),
        (
            "success reopens G2-8",
            (
                "future_single_use_read_only_reauthentication",
                "success_effect",
                "g2_8_reopened",
            ),
            True,
        ),
        (
            "success grants upload authority",
            (
                "future_single_use_read_only_reauthentication",
                "success_effect",
                "upload_authority",
            ),
            True,
        ),
        (
            "failure status drift",
            (
                "future_single_use_read_only_reauthentication",
                "failure_effect",
                "safe_classified_failure_result_status",
            ),
            FUTURE_SUCCESS,
        ),
        (
            "absent result effective success",
            (
                "future_single_use_read_only_reauthentication",
                "failure_effect",
                "ambiguous_or_absent_result_effective_status",
            ),
            FUTURE_SUCCESS,
        ),
        (
            "failure permits remedy",
            (
                "future_single_use_read_only_reauthentication",
                "failure_effect",
                "retry_or_remedy",
            ),
            True,
        ),
        (
            "failure upload authority",
            (
                "future_single_use_read_only_reauthentication",
                "failure_effect",
                "upload_authority",
            ),
            True,
        ),
        (
            "taxonomy ambiguous is not failure",
            ("future_status_taxonomy", "ambiguous_or_second_attempt_needed_is_failure"),
            False,
        ),
        (
            "taxonomy absent result not consumed",
            (
                "future_status_taxonomy",
                "started_invocation_with_absent_or_unauthentic_result_is_consumed_and_withdrawn",
            ),
            False,
        ),
        (
            "package path count",
            ("exact_package_scope", "exact_path_count"),
            10,
        ),
        (
            "outside package path",
            ("exact_package_scope", "exact_paths", 1),
            "research/unauthorized_runner.py",
        ),
        (
            "result in contract package",
            ("exact_package_scope", "result_paths"),
            1,
        ),
        (
            "alternate model authorized",
            ("competitive_backout", "alternate_model_or_candidate_authorized"),
            True,
        ),
        (
            "G4 not terminal",
            ("competitive_backout", "g4_terminal"),
            False,
        ),
        (
            "G2-8 reopened",
            ("competitive_backout", "g2_8_status"),
            "OPEN",
        ),
        (
            "relative traversal publication",
            ("immutable_public_evidence", "precedence"),
            str(contract["immutable_public_evidence"]["precedence"])
            + " ../private/result.json",
        ),
        (
            "punctuation absolute private path publication",
            ("immutable_public_evidence", "precedence"),
            str(contract["immutable_public_evidence"]["precedence"])
            + " locator="
            + "/"
            + "home/zbos/private",
        ),
        (
            "punctuation relative traversal publication",
            ("immutable_public_evidence", "precedence"),
            str(contract["immutable_public_evidence"]["precedence"])
            + " locator=../private",
        ),
        (
            "punctuation tilde path publication",
            ("immutable_public_evidence", "precedence"),
            str(contract["immutable_public_evidence"]["precedence"])
            + " locator=~/private",
        ),
        (
            "punctuation file URI publication",
            ("immutable_public_evidence", "precedence"),
            str(contract["immutable_public_evidence"]["precedence"])
            + " locator=file:"
            + "/"
            + "home/zbos/private",
        ),
        (
            "success action upload contradiction",
            (
                "future_single_use_read_only_reauthentication",
                "success_effect",
                "next_action",
            ),
            str(
                contract["future_single_use_read_only_reauthentication"][
                    "success_effect"
                ]["next_action"]
            )
            + " Upload is authorized now.",
        ),
        (
            "snapshot live-current contradiction",
            (
                "immutable_public_evidence",
                "latest_tracked_public_requirement_snapshot",
                "interpretation",
            ),
            str(
                contract["immutable_public_evidence"][
                    "latest_tracked_public_requirement_snapshot"
                ]["interpretation"]
            )
            + " This is a live current rules refresh.",
        ),
        (
            "MapLight authority contradiction",
            (
                "immutable_public_evidence",
                "fixed_maplight_internal_development_evidence",
                "interpretation",
            ),
            str(
                contract["immutable_public_evidence"][
                    "fixed_maplight_internal_development_evidence"
                ]["interpretation"]
            )
            + " It is an official leaderboard score and G2-7G selected.",
        ),
        (
            "absent-result retry contradiction",
            (
                "future_single_use_read_only_reauthentication",
                "cleanup_and_publication",
                "external_handoff_rule",
            ),
            str(
                contract["future_single_use_read_only_reauthentication"][
                    "cleanup_and_publication"
                ]["external_handoff_rule"]
            )
            + " Rerun is allowed.",
        ),
        (
            "current-byte upload-ready contradiction",
            ("competitive_backout", "continue_now"),
            str(contract["competitive_backout"]["continue_now"])
            + " Current candidate bytes verified and upload-ready.",
        ),
        (
            "parent preservation reopen contradiction",
            ("immutable_d149_parent", "preservation"),
            str(contract["immutable_d149_parent"]["preservation"]) + " G4 is reopened.",
        ),
        (
            "public accounting zero contradiction",
            ("contract_milestone_accounting", "public_repository_validation_rule"),
            str(
                contract["contract_milestone_accounting"][
                    "public_repository_validation_rule"
                ]
            )
            + " All totals are zero.",
        ),
        (
            "failure trigger retry contradiction",
            (
                "future_single_use_read_only_reauthentication",
                "failure_effect",
                "triggers",
                3,
            ),
            str(
                contract["future_single_use_read_only_reauthentication"][
                    "failure_effect"
                ]["triggers"][3]
            )
            + " Retry is allowed.",
        ),
        (
            "next gate upload contradiction",
            ("next_gate",),
            str(contract["next_gate"]) + " Upload is allowed.",
        ),
    ]

    state = _mapping(contract["current_candidate_state"])
    for key in tuple(state)[:13]:
        mutations.append(
            (
                f"current state overclaim {key}",
                ("current_candidate_state", key),
                "known_current",
            )
        )
    for key in (
        "reauthenticated",
        "upload_ready",
        "selected_by_g4",
        "robustness_accepted_by_g2_7g",
    ):
        mutations.append(
            (
                f"current authority inversion {key}",
                ("current_candidate_state", key),
                True,
            )
        )

    authority = _mapping(contract["current_authority"])
    for key in tuple(authority)[:10]:
        mutations.append(
            (f"current authority enabled {key}", ("current_authority", key), True)
        )
    for key in tuple(authority)[10:]:
        mutations.append(
            (f"future boundary removed {key}", ("current_authority", key), False)
        )

    accounting = _mapping(contract["contract_milestone_accounting"])
    mutations.append(
        (
            "tracked public handoff not bound",
            (
                "contract_milestone_accounting",
                "tracked_public_handoff_locator_reference_read_and_bound",
            ),
            False,
        )
    )
    for key in tuple(accounting)[2:23]:
        mutations.append(
            (
                f"nonzero scoped accounting {key}",
                ("contract_milestone_accounting", key),
                1,
            )
        )
    mutations.append(
        (
            "public CI unknowns falsely retained",
            (
                "contract_milestone_accounting",
                "public_repository_validation_validator_import_cache_network_and_internal_totals_retained",
            ),
            True,
        )
    )

    prerequisites = _mapping(
        contract["future_single_use_read_only_reauthentication"]["prerequisites"]
    )
    for key in tuple(prerequisites)[1:6]:
        mutations.append(
            (
                f"future prerequisite removed {key}",
                ("future_single_use_read_only_reauthentication", "prerequisites", key),
                False,
            )
        )
    mutations.append(
        (
            "private contact before prerequisites",
            (
                "future_single_use_read_only_reauthentication",
                "prerequisites",
                "private_candidate_contact_before_prerequisites",
            ),
            True,
        )
    )

    for index, row in enumerate(LEDGER_ROWS):
        mutations.append(
            (
                f"ledger identity drift {row['experiment_id']}",
                ("immutable_public_evidence", "exact_ledger_rows", index, "sha256"),
                "f" * 64,
            )
        )
    for index in range(6):
        mutations.append(
            (
                f"forbidden operation removed {index}",
                (
                    "future_single_use_read_only_reauthentication",
                    "forbidden_operations",
                    index,
                ),
                "",
            )
        )

    fragment_mutations: list[tuple[str, tuple[str | int, ...], str]] = [
        (
            "scope qualification",
            ("contract_milestone_accounting", "scope"),
            "D150 contract-milestone candidate/private/official/portal operations only",
        ),
        (
            "public CI unknown not zero",
            ("contract_milestone_accounting", "public_repository_validation_rule"),
            "not guessed as zero",
        ),
        (
            "prerequisite semantics future only",
            (
                "future_single_use_read_only_reauthentication",
                "prerequisites",
                "semantics",
            ),
            "not a claim that this unintegrated contract already satisfies it",
        ),
        (
            "absent result consumes invocation",
            (
                "future_single_use_read_only_reauthentication",
                "cleanup_and_publication",
                "external_handoff_rule",
            ),
            "invocation as consumed",
        ),
        (
            "absent result withdraws route",
            (
                "future_single_use_read_only_reauthentication",
                "cleanup_and_publication",
                "external_handoff_rule",
            ),
            "route as withdrawn",
        ),
        (
            "no rerun after absent result",
            (
                "future_single_use_read_only_reauthentication",
                "cleanup_and_publication",
                "external_handoff_rule",
            ),
            "Do not rerun, repair, replace, or publish a fabricated success",
        ),
        (
            "failure trigger missing",
            (
                "future_single_use_read_only_reauthentication",
                "failure_effect",
                "triggers",
                0,
            ),
            "missing",
        ),
        (
            "failure trigger unreadable",
            (
                "future_single_use_read_only_reauthentication",
                "failure_effect",
                "triggers",
                0,
            ),
            "unreadable",
        ),
        (
            "failure trigger ambiguous",
            (
                "future_single_use_read_only_reauthentication",
                "failure_effect",
                "triggers",
                0,
            ),
            "ambiguous",
        ),
        (
            "failure trigger hash drift",
            (
                "future_single_use_read_only_reauthentication",
                "failure_effect",
                "triggers",
                1,
            ),
            "SHA-256 mismatch",
        ),
        (
            "failure trigger snapshot drift",
            (
                "future_single_use_read_only_reauthentication",
                "failure_effect",
                "triggers",
                2,
            ),
            "latest-tracked public requirement snapshot identity mismatch",
        ),
        (
            "failure trigger accounting uncertainty",
            (
                "future_single_use_read_only_reauthentication",
                "failure_effect",
                "triggers",
                3,
            ),
            "accounting uncertainty inside the private attempt",
        ),
        (
            "failure trigger cleanup",
            (
                "future_single_use_read_only_reauthentication",
                "failure_effect",
                "triggers",
                3,
            ),
            "cleanup defect",
        ),
        (
            "failure trigger retry need",
            (
                "future_single_use_read_only_reauthentication",
                "failure_effect",
                "triggers",
                3,
            ),
            "need for retry, repair, replacement, alternate locator, validator, official data, portal, credential, or upload access",
        ),
        (
            "backout no retry",
            ("competitive_backout", "back_out_after_failure_or_ambiguity"),
            "without retry",
        ),
        (
            "backout no regeneration",
            ("competitive_backout", "back_out_after_failure_or_ambiguity"),
            "regeneration",
        ),
        (
            "backout no substitution",
            ("competitive_backout", "back_out_after_failure_or_ambiguity"),
            "substitution",
        ),
        (
            "backout no validator rescue",
            ("competitive_backout", "back_out_after_failure_or_ambiguity"),
            "validator rescue",
        ),
        (
            "backout no portal",
            ("competitive_backout", "back_out_after_failure_or_ambiguity"),
            "portal access",
        ),
        (
            "backout no upload",
            ("competitive_backout", "back_out_after_failure_or_ambiguity"),
            "or upload",
        ),
        (
            "invalidation exact allowlist",
            ("invalidation",),
            "exact nine-path allowlist",
        ),
        (
            "invalidation required path",
            ("invalidation",),
            "any required path absent",
        ),
        (
            "invalidation outside path",
            ("invalidation",),
            "any outside path present",
        ),
        (
            "invalidation no parse",
            ("invalidation",),
            "parsing",
        ),
        (
            "invalidation no private publication",
            ("invalidation",),
            "private locator/stat publication",
        ),
        (
            "invalidation cleanup chronology",
            ("invalidation",),
            "publication before cleanup",
        ),
        (
            "invalidation failure withdraws",
            ("invalidation",),
            "failure does not withdraw the route",
        ),
        (
            "next gate one attempt",
            ("next_gate",),
            "at most one separately recorded read-only hash reauthentication exactly as frozen",
        ),
        (
            "next gate success no upload",
            ("next_gate",),
            "no upload authority",
        ),
        (
            "next gate failure status",
            ("next_gate",),
            FUTURE_FAILURE,
        ),
        (
            "next gate withdrawn",
            ("next_gate",),
            ROUTE_WITHDRAWN,
        ),
    ]
    mutations.extend(
        (label, path, _without_fragment(contract, path, fragment))
        for label, path, fragment in fragment_mutations
    )

    # Structural changes exercise exact key order and unknown-field rejection.
    reversed_parent = dict(
        reversed(list(_mapping(contract["immutable_d149_parent"]).items()))
    )
    mutations.append(
        ("nested key order drift", ("immutable_d149_parent",), reversed_parent)
    )
    _assert_mutations_fail_closed(contract, _validate_contract, mutations)
    assert len(mutations) == MUTATION_CASES

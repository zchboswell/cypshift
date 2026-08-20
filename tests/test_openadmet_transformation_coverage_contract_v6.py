from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V5_PATH = (
    ROOT
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "transformation_coverage_contract_v5.json"
)
V6_PATH = (
    ROOT
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "transformation_coverage_contract_v6.json"
)
V5_SHA256 = "63d12cb376760c65eabd3d94d3f3939b0591e4019e1332075df0a4c10a4b4954"
TARGET_POINTER = (
    "/outputs/schemas/transformation_coverage.json/section_schemas/"
    "valid_changed_heavy_atom_fraction_distribution"
)


def _strict_object(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate key: {key}")
            value[key] = item
        return value

    loaded = json.loads(path.read_bytes(), object_pairs_hook=reject_duplicates)
    assert isinstance(loaded, dict)
    return loaded


def _resolve_pointer(root: dict[str, Any], pointer: str) -> dict[str, Any]:
    assert pointer.startswith("/")
    value: Any = root
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        assert isinstance(value, dict)
        assert token in value
        value = value[token]
    assert isinstance(value, dict)
    return value


def _effective_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    parent = _strict_object(V5_PATH)
    overlay = _strict_object(V6_PATH)
    effective = copy.deepcopy(parent)
    for operation in overlay["resolution"]["operations"]:
        assert operation["op"] == "add_absent_object_member"
        assert operation["parent_object_pointer"] == TARGET_POINTER
        target = _resolve_pointer(effective, operation["parent_object_pointer"])
        member = operation["member"]
        assert member not in target
        target[member] = operation["value"]
    return overlay, effective


def test_v6_binds_exact_parent_and_two_additions_only() -> None:
    overlay, effective = _effective_contract()
    assert hashlib.sha256(V5_PATH.read_bytes()).hexdigest() == V5_SHA256
    assert overlay["parent"] == {
        "path": "benchmarks/openadmet_cyp_2026/transformation_coverage_contract_v5.json",
        "schema_version": "cypshift.openadmet_cyp_2026.transformation_coverage_contract.v5",
        "gate": "R4_TRANSFORMATION_COVERAGE_CONTRACT_FROZEN",
        "sha256": V5_SHA256,
    }
    assert len(overlay["resolution"]["operations"]) == 2
    parent = _strict_object(V5_PATH)
    target = _resolve_pointer(effective, TARGET_POINTER)
    parent_target = _resolve_pointer(parent, TARGET_POINTER)
    assert set(target) - set(parent_target) == {"population", "count_invariant"}
    for key in parent_target:
        assert target[key] == parent_target[key]


def test_v6_freezes_union_distribution_and_count_invariant() -> None:
    _, effective = _effective_contract()
    target = _resolve_pointer(effective, TARGET_POINTER)
    assert target["population"] == (
        "All valid union structural pair rows, with each transformation_pair_id "
        "counted exactly once regardless of local/episode overlap, endpoint "
        "eligibility, direction, or episode repetition."
    )
    assert target["count_invariant"] == "count equals counts.union.valid_rows exactly."
    assert effective["outputs"]["schemas"]["transformation_pairs.csv"][
        "schema_version"
    ].endswith(".v5")


def test_v6_preserves_science_and_denies_execution_authority() -> None:
    overlay, _ = _effective_contract()
    assert overlay["unchanged"] == {
        "extraction_spec_receipt": "59e3bd3390658bab854be52f88ef7de0164aae6e99ad48b0b0feb04c68669950",
        "chemistry": True,
        "populations_other_than_the_clarified_distribution": True,
        "support_thresholds": True,
        "output_files_columns_and_statuses": True,
        "label_safe_firewall": True,
        "runtime_and_publication_rules": True,
        "authority": True,
    }
    assert overlay["authority"]["contract_only"] is True
    assert all(
        value is False
        for key, value in overlay["authority"].items()
        if key != "contract_only"
    )

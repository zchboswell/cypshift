from __future__ import annotations

import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parents[1]
PATH = ROOT / "benchmarks/openadmet_cyp_2026/transformation_coverage_contract_v5.json"
PARENT = ROOT / "benchmarks/openadmet_cyp_2026/transformation_coverage_contract_v4.json"
V4_SHA256 = "cacd1f77215e36a17f03553680d71263425638c290a39d33c397e43b2c35550f"
V5_SHA256 = "63d12cb376760c65eabd3d94d3f3939b0591e4019e1332075df0a4c10a4b4954"
EXTRACTION_SHA256 = "59e3bd3390658bab854be52f88ef7de0164aae6e99ad48b0b0feb04c68669950"


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AssertionError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes(), object_pairs_hook=_unique)
    assert isinstance(value, dict)
    return value


def _extraction_receipt(contract: dict[str, Any]) -> str:
    extraction = contract["extraction"]
    receipt = extraction["extraction_spec_receipt"]
    material = {"extraction_spec_id": extraction["extraction_spec_id"]}
    material.update({key: extraction[key] for key in receipt["receipt_subtrees"]})
    encoded = json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _validate_distribution(value: dict[str, Any], schema: dict[str, Any]) -> None:
    assert set(value) == set(schema["keys"])
    if value["count"] == 0:
        if value != schema["zero_valid_sentinel"]:
            raise ValueError("zero-valid sentinel mismatch")
        return
    if value["count"] < 0 or value["unique_rationals"] <= 0:
        raise ValueError("invalid positive distribution counts")
    rationals = [Fraction(key) for key in value["histogram"]]
    if value["unique_rationals"] != len(rationals):
        raise ValueError("unique rational count mismatch")
    if sum(value["histogram"].values()) != value["count"]:
        raise ValueError("histogram count mismatch")
    if any(value[key] is None for key in ("min", "median", "max")):
        raise ValueError("positive distribution has null extrema")
    expanded = sorted(
        rational
        for key, count in value["histogram"].items()
        for rational in [Fraction(key)] * count
    )
    midpoint = (expanded[(len(expanded) - 1) // 2] + expanded[len(expanded) // 2]) / 2
    expected = {
        "min": expanded[0],
        "median": midpoint,
        "max": expanded[-1],
    }
    for key, rational in expected.items():
        if value[key] != f"{rational.numerator}/{rational.denominator}":
            raise ValueError(f"numeric {key} mismatch")


def test_v5_parent_hash_versions_and_extraction_receipt_are_exact() -> None:
    parent = _load(PARENT)
    contract = _load(PATH)
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == V4_SHA256
    assert hashlib.sha256(PATH.read_bytes()).hexdigest() == V5_SHA256
    assert contract["parent"] == {
        "path": "benchmarks/openadmet_cyp_2026/transformation_coverage_contract_v4.json",
        "schema_version": (
            "cypshift.openadmet_cyp_2026.transformation_coverage_contract.v4"
        ),
        "sha256": V4_SHA256,
        "immutable": True,
    }
    assert contract["schema_version"].endswith(".v5")
    assert all(
        schema["schema_version"].endswith(".v5")
        for schema in contract["outputs"]["schemas"].values()
    )
    assert contract["extraction"] == parent["extraction"]
    assert _extraction_receipt(contract) == EXTRACTION_SHA256
    assert contract["extraction"]["extraction_spec_receipt"]["sha256"] == (
        EXTRACTION_SHA256
    )


def test_v5_changes_only_the_two_repairs_and_version_metadata() -> None:
    parent = _load(PARENT)
    normalized = copy.deepcopy(_load(PATH))
    normalized["schema_version"] = parent["schema_version"]
    normalized["base_commit"] = parent["base_commit"]
    normalized["purpose"] = parent["purpose"]
    normalized["parent"] = parent["parent"]
    normalized["inheritance"] = parent["inheritance"]

    publication = normalized["outputs"]["publication"]
    parent_publication = parent["outputs"]["publication"]
    publication.pop("runtime_and_checkout_preflight")
    publication["failure_receipt_eligibility"] = parent_publication[
        "failure_receipt_eligibility"
    ]
    for name, schema in normalized["outputs"]["schemas"].items():
        schema["schema_version"] = parent["outputs"]["schemas"][name]["schema_version"]
    normalized["outputs"]["schemas"]["transformation_coverage.json"]["section_schemas"][
        "valid_changed_heavy_atom_fraction_distribution"
    ] = parent["outputs"]["schemas"]["transformation_coverage.json"]["section_schemas"][
        "valid_changed_heavy_atom_fraction_distribution"
    ]
    normalized["failure_policy"] = parent["failure_policy"]
    assert normalized == parent


def test_zero_valid_distribution_has_one_exact_executable_sentinel() -> None:
    schema = _load(PATH)["outputs"]["schemas"]["transformation_coverage.json"][
        "section_schemas"
    ]["valid_changed_heavy_atom_fraction_distribution"]
    sentinel = {
        "count": 0,
        "unique_rationals": 0,
        "min": None,
        "median": None,
        "max": None,
        "histogram": {},
    }
    assert schema["zero_valid_sentinel"] == sentinel
    _validate_distribution(sentinel, schema)
    with pytest.raises(ValueError, match="sentinel"):
        _validate_distribution({**sentinel, "median": "0/1"}, schema)
    positive = {
        "count": 3,
        "unique_rationals": 2,
        "min": "1/4",
        "median": "1/2",
        "max": "1/2",
        "histogram": {"1/4": 1, "1/2": 2},
    }
    _validate_distribution(positive, schema)
    with pytest.raises(ValueError, match="null extrema"):
        _validate_distribution({**positive, "min": None}, schema)


def test_histogram_serializes_lexically_but_is_evaluated_numerically() -> None:
    contract = _load(PATH)
    schema = contract["outputs"]["schemas"]["transformation_coverage.json"][
        "section_schemas"
    ]["valid_changed_heavy_atom_fraction_distribution"]
    distribution = {
        "count": 2,
        "unique_rationals": 2,
        "min": "2/3",
        "median": "26/33",
        "max": "10/11",
        "histogram": {"2/3": 1, "10/11": 1},
    }
    encoded = json.dumps(distribution, sort_keys=True, separators=(",", ":"))
    assert encoded.index('"10/11"') < encoded.index('"2/3"')
    assert Fraction("2/3") < Fraction("10/11")
    _validate_distribution(json.loads(encoded), schema)
    assert "lexicographic" in schema["histogram_serialization"]
    assert "no numerical ordering meaning" in schema["histogram_serialization"]
    assert "numerically" in schema["positive_case"]


def test_runtime_refusal_precedes_inputs_and_p1_is_post_gate_only() -> None:
    contract = _load(PATH)
    publication = contract["outputs"]["publication"]
    preflight = publication["runtime_and_checkout_preflight"]
    assert "Before opening any official coverage source" in preflight["order"]
    assert "create no private stage" in preflight["mismatch"]
    assert "publish no success or failure terminal" in preflight["mismatch"]
    assert (
        "only after runtime_and_checkout_preflight has passed"
        in publication["failure_receipt_eligibility"]
    )

    policy = contract["failure_policy"]
    assert (
        "runtime or dirty-checkout mismatch" in policy["pre_input_no_terminal_refusal"]
    )
    assert (
        "runtime or dependency mismatch" not in policy["terminal_integrity_conditions"]
    )
    assert "runtime or dependency mismatch" not in policy["terminal_condition_aliases"]
    post_gate = "post-gate reproducibility, seed, hash, or configuration defect"
    assert policy["terminal_condition_aliases"][post_gate] == "P1"
    assert any(
        row
        == {
            "condition": post_gate,
            "code": "P1",
            "status": "R4_TRANSFORMATION_COVERAGE_FAILED",
        }
        for row in policy["terminal_condition_code_map"]
    )
    assert (
        "after the accepted runtime and clean-checkout gate"
        in policy["code_mapping"]["P1"]["meaning"]
    )
    failure_runtime = contract["outputs"]["schemas"]["failure_receipt.json"]["runtime"]
    success_runtime = contract["outputs"]["schemas"]["manifest.json"]["runtime"]
    for key in (
        "fields_exact",
        "field_types",
        "required_values",
        "code_commit_rule",
        "additional_fields",
    ):
        assert failure_runtime[key] == success_runtime[key]


def test_duplicate_keys_fail_at_every_depth() -> None:
    with pytest.raises(AssertionError, match="duplicate JSON key"):
        json.loads('{"outer":{"x":1,"x":2}}', object_pairs_hook=_unique)

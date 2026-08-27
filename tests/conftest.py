from __future__ import annotations

import pytest

_PRE_ACCEPTANCE_STATE_NODE = (
    "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py::"
    "test_formal_acceptance_is_fixed_unrun_and_has_zero_authority"
)
_PRE_D140_ORCHESTRATION_STATE_NODES = {
    (
        "tests/test_openadmet_global_v2_maplight_robustness_execution_"
        "acceptance_v2.py::test_acceptance_binds_exact_contract_and_integrated_"
        "implementation"
    ): (
        "historical D-136 live-driver binding; D-140 historical/"
        "composite-lineage test owns current-state validation"
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_execution_"
        "acceptance_v2.py::test_provenance_bridge_retires_only_the_obsolete_pre_"
        "acceptance_state"
    ): (
        "historical D-136 live-hook/driver binding; D-140 two-order composite "
        "test owns current-state validation"
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_execution_"
        "acceptance_v2.py::test_claim_derivation_is_read_only_and_fills_exactly_"
        "five_receipts"
    ): (
        "historical D-136 pre-composite claim derivation; D-140 five-field "
        "derivation test owns current-state validation"
    ),
}
_PRE_D141_ORCHESTRATION_SOURCE_SHAPE_NODES = {
    (
        "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_"
        "v2.py::test_exact_fit_topology_and_conditional_stage_c_are_unchanged"
    ): (
        "historical D-134 child terminal-shape assertion; D-141 corrected child "
        "cleanup/staging test owns current-state validation"
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_"
        "v2.py::test_supervisor_starts_before_claim_consumption_and_official_"
        "access"
    ): (
        "historical D-134 parent terminal-shape assertion; D-141 supervised "
        "common-seal test owns current-state validation"
    ),
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Retire only exact historical nodes whose replacement evidence is frozen."""

    for item in items:
        if item.nodeid == _PRE_ACCEPTANCE_STATE_NODE:
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        "historical D-134 pre-acceptance state assertion; "
                        "D-135 receipt audits now own current-state validation"
                    )
                )
            )
        reason = _PRE_D140_ORCHESTRATION_STATE_NODES.get(item.nodeid)
        if reason is not None:
            item.add_marker(pytest.mark.skip(reason=reason))
        reason = _PRE_D141_ORCHESTRATION_SOURCE_SHAPE_NODES.get(item.nodeid)
        if reason is not None:
            item.add_marker(pytest.mark.skip(reason=reason))

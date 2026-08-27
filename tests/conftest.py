from __future__ import annotations

import pytest

_PRE_ACCEPTANCE_STATE_NODE = (
    "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py::"
    "test_formal_acceptance_is_fixed_unrun_and_has_zero_authority"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Retire the acceptance-bound snapshot's obsolete pre-run state check."""

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

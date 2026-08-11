from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/measure_tdc_shadow_topology.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("measure_tdc_shadow_topology", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    structure: str,
    source_row: int,
    fold: int,
    *,
    molecule_id: str | None = None,
) -> dict[str, str]:
    structure_hash = hashlib.sha256(structure.encode("utf-8")).hexdigest()
    row = {
        "task": "task",
        "molecule_id": molecule_id or f"molecule-{source_row}",
        "source_row": str(source_row),
        "raw_structure": structure,
        "raw_structure_sha256": structure_hash,
        "standardized_structure": structure,
        "standardized_structure_hash": structure_hash,
        "scaffold_group_hash": f"scaffold-{source_row}",
        "community_group_hash": f"community-{source_row}",
    }
    for protocol in ("scaffold", "community"):
        for repeat in range(3):
            outer_fold = fold if repeat == 0 else (source_row + repeat) % 5
            row[f"{protocol}_repeat_{repeat}_outer_fold"] = str(outer_fold)
            row[f"{protocol}_repeat_{repeat}_inner_fold"] = (
                "" if outer_fold == 0 else str(outer_fold - 1)
            )
    return row


def _manifest(validation_rows: int) -> dict[str, object]:
    return {
        "validation": {
            "task": {
                "scaffold": {
                    "0": {
                        "outer_folds": [
                            {
                                "fold": 0,
                                "rows": validation_rows,
                                "prevalence": 0.5,
                            }
                        ]
                    }
                }
            }
        }
    }


def test_measure_topology_records_every_validation_structure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "TASKS", ("task",))
    monkeypatch.setattr(module, "PROTOCOLS", ("scaffold",))
    monkeypatch.setattr(module, "REPEATS", (0,))
    rows = [_row("CCO", 1, 1), _row("CCN", 2, 2), _row("CCCC", 3, 0)]

    topology, summaries, comparisons = module.measure_topology(rows, _manifest(1))

    assert len(topology) == 1
    assert (
        topology[0]["standardized_structure_hash"]
        == hashlib.sha256(b"CCCC").hexdigest()
    )
    assert topology[0]["validation_source_rows"] == 1
    assert 0.0 <= float(topology[0]["max_train_tanimoto"]) <= 1.0
    assert len(summaries) == 1
    assert summaries[0]["training_structures"] == 2
    assert summaries[0]["validation_structures"] == 1
    assert summaries[0]["standardized_crossing_structures"] == 0
    assert comparisons == 2


def test_measure_topology_rejects_duplicate_crossing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "TASKS", ("task",))
    monkeypatch.setattr(module, "PROTOCOLS", ("scaffold",))
    monkeypatch.setattr(module, "REPEATS", (0,))
    rows = [
        _row("CCO", 1, 1),
        _row("CCO", 2, 0, molecule_id="duplicate"),
    ]

    with pytest.raises(module.TopologyError, match="duplicate crosses"):
        module.measure_topology(rows, _manifest(1))


def test_group_sizes_are_global_and_task_aware() -> None:
    module = _load_module()
    first = _row("CCO", 1, 1)
    second = _row("CCN", 2, 2)
    second["task"] = "second-task"
    second["scaffold_group_hash"] = first["scaffold_group_hash"]

    groups = module.group_sizes([first, second])
    shared = next(
        record
        for record in groups
        if record["protocol"] == "scaffold"
        and record["group_hash"] == first["scaffold_group_hash"]
    )
    assert shared == {
        "protocol": "scaffold",
        "group_hash": first["scaffold_group_hash"],
        "source_rows": 2,
        "unique_standardized_structures": 2,
        "task_count": 2,
    }

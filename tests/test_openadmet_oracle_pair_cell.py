from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest
from test_openadmet_oracle_projection import _fixture

from cypshift.openadmet_oracle_cell_io import (
    OracleC3TargetCapability,
    OracleCellCapability,
    OracleCellTargetCapability,
    load_oracle_cell_capability,
)
from cypshift.openadmet_oracle_pair_cell import (
    FRAGMENT_COLUMNS,
    OraclePairCellError,
    candidate_id,
    run_pair_cell,
    run_shared_outer_t0,
)
from cypshift.openadmet_oracle_pair_cell_io import (
    CONTRACT_SHA256,
    load_g0_predictions,
    publish_pair_cell,
)
from cypshift.openadmet_oracle_projection import project_openadmet_oracle_inputs
from cypshift.openadmet_transformation_io import canonical_json_bytes


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _capability(
    tmp_path: Path, *, c3: bool = False, system_id: str | None = None
) -> tuple[OracleCellCapability, dict[tuple[str, str, int], float]]:
    source, receipts = _fixture(tmp_path / "fixture")
    projection = project_openadmet_oracle_inputs(
        source, tmp_path / "projection", expected_receipts=receipts
    )
    target_root = (projection.c3_target_root if c3 else projection.cell_target_root) / (
        "outer/repeat-0/outer-1"
    )
    scope_value = json.loads((target_root / "manifest.json").read_bytes())[
        "current_cell_scope"
    ]
    scope = (
        scope_value["stage"],
        int(scope_value["repeat"]),
        int(scope_value["outer_fold"]),
        None,
    )
    capability = load_oracle_cell_capability(
        projection.model_public_root,
        target_root,
        expected_model_manifest_sha256=_sha(
            projection.model_public_root / "manifest.json"
        ),
        expected_target_manifest_sha256=_sha(target_root / "manifest.json"),
        system_id=system_id or ("C3" if c3 else "C0"),
        target_kind="c3-target" if c3 else "cell-target",
        expected_scope=cast(Any, scope),
    )
    if c3:
        assert isinstance(capability.target, OracleC3TargetCapability)
        episodes = {
            row["episode_id"] for row in capability.target.global_anchor_contexts
        }
    else:
        assert isinstance(capability.target, OracleCellTargetCapability)
        episodes = {
            row["episode_id"] for row in capability.target.episode_anchor_contexts
        }
    g0 = {
        (row["episode_id"], row["query_molecule_id"], int(row["query_rank"])): 0.0
        for row in capability.model_public.public_queries
        if row["episode_id"] in episodes
    }
    return capability, g0


def _t0_capability(
    tmp_path: Path,
) -> tuple[OracleCellCapability, dict[tuple[str, str, int], float]]:
    source, receipts = _fixture(tmp_path / "fixture")
    projection = project_openadmet_oracle_inputs(
        source, tmp_path / "projection", expected_receipts=receipts
    )
    target_root = projection.cell_target_root / "outer/repeat-0/outer-1"
    training_path = target_root / "training_points.csv"
    target_root.chmod(0o755)
    training_path.chmod(0o644)
    rows = training_path.read_text().splitlines()
    assert len(rows) == 2
    point = rows[1].split(",")
    rows.append(",".join(["train2", point[1], "3", "1"]))
    training_bytes = ("\n".join(rows) + "\n").encode()
    training_path.write_bytes(training_bytes)
    manifest_path = target_root / "manifest.json"
    manifest_path.chmod(0o644)
    manifest = json.loads(manifest_path.read_bytes())
    manifest["output_receipts"]["training_points.csv"] = {
        "sha256": hashlib.sha256(training_bytes).hexdigest(),
        "bytes": len(training_bytes),
        "rows": len(rows) - 1,
        "columns": list(
            (
                "molecule_id",
                "component_id",
                "point",
                "sample_weight",
            )
        ),
    }
    manifest["operation_accounting"]["direct_target_values_parsed"] += 1
    manifest_bytes = canonical_json_bytes(manifest)
    manifest_path.write_bytes(manifest_bytes)
    training_path.chmod(0o444)
    manifest_path.chmod(0o444)
    target_root.chmod(0o555)
    scope_value = json.loads(manifest_bytes)["current_cell_scope"]
    scope = (
        scope_value["stage"],
        int(scope_value["repeat"]),
        int(scope_value["outer_fold"]),
        None,
    )
    capability = load_oracle_cell_capability(
        projection.model_public_root,
        target_root,
        expected_model_manifest_sha256=_sha(
            projection.model_public_root / "manifest.json"
        ),
        expected_target_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        system_id="T0",
        target_kind="cell-target",
        expected_scope=cast(Any, scope),
    )
    assert isinstance(capability.target, OracleCellTargetCapability)
    episodes = {row["episode_id"] for row in capability.target.episode_anchor_contexts}
    g0 = {
        (row["episode_id"], row["query_molecule_id"], int(row["query_rank"])): 0.0
        for row in capability.model_public.public_queries
        if row["episode_id"] in episodes
    }
    return capability, g0


def test_c0_and_c1_emit_complete_ordered_fragments(tmp_path: Path) -> None:
    capability, g0 = _capability(tmp_path)
    for system in ("C0", "C1"):
        if system == "C1":
            capability, g0 = _capability(tmp_path / "c1", system_id="C1")
        result = run_pair_cell(
            capability,
            system_id=system,
            alpha=None,
            lambda_=None,
            g0_predictions=g0,
        )
        assert result.fragment.startswith((",".join(FRAGMENT_COLUMNS) + "\n").encode())
        assert [
            (row["episode_id"], int(row["query_rank"])) for row in result.rows
        ] == sorted((row["episode_id"], int(row["query_rank"])) for row in result.rows)
        assert all(row["candidate_id"] == result.candidate_id for row in result.rows)
        assert all(
            row["prediction_source"] in {"C0", "C1", "G0"} for row in result.rows
        )
        assert result.accounting["predictions_frozen"] == 0


def test_c3_uses_only_pure_oof_anchor_context(tmp_path: Path) -> None:
    capability, g0 = _capability(tmp_path, c3=True)
    result = run_pair_cell(
        capability,
        system_id="C3",
        alpha=1.0,
        lambda_=2.0,
        g0_predictions=g0,
    )
    assert result.rows
    assert all(row["system_id"] == "C3" for row in result.rows)
    assert result.accounting["anchor_labels_exposed_to_models"] == 0
    assert result.accounting["direct_target_values_parsed"] == 2


def test_c3_requires_c3_target_and_f2_requires_selection_token(tmp_path: Path) -> None:
    capability, g0 = _capability(tmp_path)
    with pytest.raises(OraclePairCellError, match="capability system"):
        run_pair_cell(
            capability,
            system_id="C3",
            alpha=1.0,
            lambda_=2.0,
            g0_predictions=g0,
        )
    with pytest.raises(OraclePairCellError, match="capability system"):
        run_pair_cell(
            capability,
            system_id="F2",
            alpha=1.0,
            lambda_=2.0,
            g0_predictions=g0,
        )


def test_shared_outer_t0_owns_target_and_fit_accounting_once(tmp_path: Path) -> None:
    capability, g0 = _t0_capability(tmp_path)
    t0, f0, f1 = run_shared_outer_t0(
        capability,
        alpha=1.0,
        lambda_=2.0,
        selection_token_sha256="a" * 64,
        g0_predictions=g0,
    )
    assert t0.rows and f0.rows and f1.rows
    assert t0.candidate_id != f0.candidate_id != f1.candidate_id
    assert t0.fragment_id != f0.fragment_id != f1.fragment_id
    assert t0.accounting["direct_target_values_parsed"] > 0
    assert t0.accounting["anchor_labels_exposed_to_models"] > 0
    for control in (f0, f1):
        assert control.accounting["direct_target_values_parsed"] == 0
        assert control.accounting["anchor_labels_exposed_to_models"] == 0
        assert control.accounting["ridge_model_fits"] == 0
        assert control.accounting["hierarchy_fits"] == 0
    assert {
        (row["episode_id"], row["query_molecule_id"], row["query_rank"])
        for row in t0.rows
    } == {
        (row["episode_id"], row["query_molecule_id"], row["query_rank"])
        for row in f0.rows
    } == {
        (row["episode_id"], row["query_molecule_id"], row["query_rank"])
        for row in f1.rows
    }


def test_g0_loader_and_atomic_pair_publication(tmp_path: Path) -> None:
    capability, g0 = _capability(tmp_path)
    result = run_pair_cell(
        capability,
        system_id="C0",
        alpha=None,
        lambda_=None,
        g0_predictions=g0,
    )
    g0_rows = [
        {
            **row,
            "system_id": "G0",
            "prediction_source": "G0",
            "local_available": "false",
            "prediction": format(
                g0[
                    (
                        row["episode_id"],
                        row["query_molecule_id"],
                        int(row["query_rank"]),
                    )
                ],
                ".17g",
            ),
        }
        for row in result.rows
    ]
    import csv
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=list(FRAGMENT_COLUMNS), lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(g0_rows)
    fragment = stream.getvalue().encode()
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.r5c_g0_prediction_fragment.v1",
        "status": "R5_ORACLE_G0_EPISODE_COMPLETE",
        "contract_sha256": CONTRACT_SHA256,
        "scope": {"stage": "outer", "repeat": 0, "outer_fold": 1, "inner_fold": ""},
        "candidate_id": candidate_id("G0", None, None),
        "episode": {"episode_id": g0_rows[0]["episode_id"]},
        "operation_accounting": {
            name: 0
            for name in (
                "direct_target_values_parsed",
                "anchor_labels_exposed_to_models",
                "query_truth_values_opened_by_scorers",
                "maplight_model_fits",
                "ridge_model_fits",
                "hierarchy_fits",
                "predictions_frozen",
                "internal_absolute_error_evaluations",
                "blinded_test_files_opened",
                "tdi_files_opened",
                "official_metric_calls",
                "submissions_created",
                "transductive_relationships",
                "inferred_anchor_candidate_pools",
            )
        },
        "prediction_fragment": {
            "sha256": hashlib.sha256(fragment).hexdigest(),
            "bytes": len(fragment),
            "rows": len(g0_rows),
            "columns": list(FRAGMENT_COLUMNS),
        },
    }
    g0_root = tmp_path / "g0"
    g0_root.mkdir()
    (g0_root / "prediction_fragment.csv").write_bytes(fragment)
    (g0_root / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    public = [
        row
        for row in capability.model_public.public_queries
        if row["episode_id"]
        in {x["episode_id"] for x in capability.target.episode_anchor_contexts}
    ]
    loaded = load_g0_predictions(
        g0_root,
        expected_manifest_sha256=_sha(g0_root / "manifest.json"),
        scope=("outer", 0, 1, None),
        public_queries=public,
    )
    assert loaded == g0
    output = publish_pair_cell(
        tmp_path / "pair-output",
        result,
        scope={"stage": "outer", "repeat": 0, "outer_fold": 1, "inner_fold": ""},
        capability_binding={"target": "synthetic"},
    )
    assert sorted(path.name for path in output.iterdir()) == [
        "manifest.json",
        "prediction_fragment.csv",
    ]

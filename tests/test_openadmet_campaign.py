from __future__ import annotations

import csv
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest
from test_openadmet_validation import _build, _chain

from cypshift.openadmet_campaign import (
    _base_episodes,
    _Inputs,
    _Molecule,
    build_openadmet_campaign_artifacts,
)
from cypshift.openadmet_campaign_io import (
    csv_bytes,
    load_oracle_episode,
    validate_generated_projections,
)
from cypshift.openadmet_validation_contract import (
    ENDPOINTS,
    MASK_COLUMNS,
    PUBLIC_EPISODE_COLUMNS,
    SEEDS,
    TRUTH_COLUMNS,
)
from cypshift.openadmet_viability import DirectPair


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _synthetic_chain(root: Path) -> dict[str, Any]:
    chain = _chain(root / "chain")
    seed_r2a = _build(chain, root / "r2a-seed")
    folds = _rows(seed_r2a.folds_path)
    observations = _rows(seed_r2a.observations_path)
    component = next(
        row["similarity_component_hash"]
        for row in observations
        if row["molecule_id"] == "direct-0"
    )
    outer = {
        int(row["repeat"]): int(row["outer_fold"])
        for row in folds
        if row["molecule_id"] == "direct-0"
    }
    cells = []
    for repeat, seed in enumerate(SEEDS):
        for outer_fold in range(5):
            count = int(outer[repeat] == outer_fold)
            cells.append(
                {
                    "repeat": repeat,
                    "seed": seed,
                    "outer_fold": outer_fold,
                    "component_count": count,
                    "pair_count": count,
                    "meets_minimum": False,
                }
            )
    zero_cells = [
        {
            "repeat": repeat,
            "seed": seed,
            "outer_fold": outer_fold,
            "component_count": 0,
            "pair_count": 0,
            "meets_minimum": False,
        }
        for repeat, seed in enumerate(SEEDS)
        for outer_fold in range(5)
    ]
    contract_path = chain["validation_contract_path"]
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["topology_viability"]["source_revision"] = chain["source_revision"]
    receipts = contract["topology_viability"]["input_receipts"]
    receipts["direct_source"] = contract["input_chain"]["direct_source"]
    receipts["r1_source_row_adapter"] = contract["input_chain"]["r1_source_row_adapter"]
    receipts["r1_topology"] = {
        key: contract["input_chain"]["r1_topology"][key]
        for key in (
            "manifest_sha256",
            "molecule_audit_sha256",
            "training_topology_sha256",
        )
    }
    receipts["r2a_validation_inputs"].update(
        {
            "direct_observations.csv": {
                "sha256": _digest(seed_r2a.observations_path),
                "rows": len(observations),
            },
            "group_folds.csv": {
                "sha256": _digest(seed_r2a.folds_path),
                "rows": len(folds),
            },
        }
    )
    underpowered = {
        "eligible_components": 0,
        "eligible_pairs": 0,
        "fold_support_cells": zero_cells,
        "status": "LOCAL_UNDERPOWERED",
        "fusion_weight": 0.0,
    }
    endpoint_map = {
        endpoint: json.loads(json.dumps(underpowered)) for endpoint in ENDPOINTS
    }
    endpoint_map["CYP1A2"] = {
        "eligible_components": 1,
        "eligible_pairs": 1,
        "fold_support_cells": cells,
        "status": "LOCAL_UNDERPOWERED",
        "fusion_weight": 0.0,
    }
    contract["topology_viability"]["endpoint_map"] = endpoint_map
    contract["topology_viability"]["activity_cliff_counts"] = {
        endpoint: {"pairs": 0, "components": 0} for endpoint in ENDPOINTS
    }
    episode_diagnostics = {
        "primary_base": {"selected_episodes": 3, "queries": 3},
        "stress_base": {"selected_episodes": 3, "queries": 3},
        "expanded_artifact_rows_each": 18,
        "total_expanded_queries": 18,
        "anchor_observation_references": 72,
        "query_observation_references": 72,
        "primary_anchor_inference": "3/3",
        "stress_anchor_inference": "3/3",
    }
    contract["topology_viability"]["episode_diagnostics"] = episode_diagnostics
    contract["campaign_episodes"]["preliminary_diagnostics"] = {
        "CYP1A2": {
            "selected_episodes": 1,
            "queries": 1,
            "selector_labeled_query_cells": 1,
        },
        "CYP2C9": {
            "selected_episodes": 1,
            "queries": 1,
            "selector_labeled_query_cells": 1,
        },
        "CYP3A4": {
            "selected_episodes": 1,
            "queries": 1,
            "selector_labeled_query_cells": 0,
        },
        "interpretation": "Counts are contract diagnostics, not prediction evidence.",
    }
    contract["campaign_episodes"]["official_diagnostics"] = {
        "primary_base": episode_diagnostics["primary_base"],
        "stress_base": episode_diagnostics["stress_base"],
        "repeat_expansion": {
            "repeats": 3,
            "expanded_artifact_rows_each": 18,
            "total_expanded_queries": 18,
            "anchor_observation_references": 72,
            "query_observation_references": 72,
        },
        "identity_inference_diagnostic": {
            "primary_selected_episodes_with_anchor_inference": "3/3",
            "stress_selected_episodes_with_anchor_inference": "3/3",
            "interpretation": "Public membership can permit identity inference; this is acknowledged and is not a secrecy or prediction-evidence claim.",
        },
    }
    contract["acceptance"]["r2b_success"]["exact_artifact_counts"] = {
        "campaign_episodes_public_rows": 18,
        "campaign_episodes_truth_rows": 18,
        "episode_label_masks_rows": 18,
        "unique_episode_ids": 18,
        "expanded_queries": 18,
        "anchor_observation_references": 72,
        "query_observation_references": 72,
    }
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    final_r2a = _build(chain, root / "r2a")
    assert (
        _digest(final_r2a.observations_path)
        == receipts["r2a_validation_inputs"]["direct_observations.csv"]["sha256"]
    )
    return chain | {"r2a": final_r2a.manifest_path.parent, "component": component}


def _run(chain: dict[str, Any], output: Path) -> Any:
    return build_openadmet_campaign_artifacts(
        validation_contract_path=chain["validation_contract_path"],
        r2a_directory=chain["r2a"],
        output_directory=output,
        source_revision=chain["source_revision"],
    )


def test_r2b_build_is_deterministic_receipt_bound_and_firewalled(
    tmp_path: Path,
) -> None:
    chain = _synthetic_chain(tmp_path)
    first = _run(chain, tmp_path / "first")
    second = _run(chain, tmp_path / "second")
    names = (
        "direct_observations.csv",
        "group_folds.csv",
        "campaign_episodes_public.csv",
        "campaign_episodes_truth.csv",
        "episode_label_masks.csv",
        "topology_viability.json",
        "manifest.json",
    )
    assert all(
        (first.output_directory / name).read_bytes()
        == (second.output_directory / name).read_bytes()
        for name in names
    )
    assert (first.output_directory / "direct_observations.csv").read_bytes() == (
        chain["r2a"] / "direct_observations.csv"
    ).read_bytes()
    public = _rows(first.output_directory / "campaign_episodes_public.csv")
    truth = _rows(first.output_directory / "campaign_episodes_truth.csv")
    masks = _rows(first.output_directory / "episode_label_masks.csv")
    assert len(public) == len(truth) == len(masks) == 18
    assert [row["episode_id"] for row in public] == sorted(
        row["episode_id"] for row in public
    )
    assert (
        [row["episode_id"] for row in public]
        == [row["episode_id"] for row in truth]
        == [row["episode_id"] for row in masks]
    )
    assert set(public[0]) == {
        "episode_id",
        "protocol",
        "repeat",
        "outer_fold",
        "outer_group_id",
        "query_molecule_ids",
        "candidate_pool_id",
        "episode_policy_id",
    }
    assert not ({"selector_cyp_truth", "anchor_molecule_id_truth"} & set(public[0]))
    assert {row["episode_policy_id"] for row in public} == {
        "selected_anchor",
        "deterministic_random_anchor_stress",
    }
    joined = {row["episode_id"]: row for row in truth}
    by_cell: dict[tuple[str, str, str], dict[str, tuple[str, str]]] = {}
    for row in public:
        truth_row = joined[row["episode_id"]]
        cell = (
            row["repeat"],
            row["outer_group_id"],
            truth_row["selector_cyp_truth"],
        )
        by_cell.setdefault(cell, {})[row["episode_policy_id"]] = (
            row["episode_id"],
            truth_row["anchor_molecule_id_truth"],
        )
    identical_anchor_cells = 0
    for policies in by_cell.values():
        selected = policies["selected_anchor"]
        stress = policies["deterministic_random_anchor_stress"]
        assert selected[0] != stress[0]
        identical_anchor_cells += selected[1] == stress[1]
    assert identical_anchor_cells > 0
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["authority"]["episodes"] is True
    assert manifest["authority"]["validation"] is False
    assert all(value == 0 for value in manifest["accounting"].values())
    assert manifest["policies"]["outer_scope"] == "openadmet-direct-outer-v1"
    assert (
        manifest["policies"]["inner_scope"]
        == "openadmet-direct-inner-v1|outer=<outer_fold>"
    )


def test_oracle_loader_has_no_truth_input_and_resolves_exact_anchor(
    tmp_path: Path,
) -> None:
    chain = _synthetic_chain(tmp_path)
    result = _run(chain, tmp_path / "output")
    public = _rows(result.output_directory / "campaign_episodes_public.csv")
    assert "truth" not in inspect.signature(load_oracle_episode).parameters
    episode = load_oracle_episode(
        manifest_path=result.output_directory / "manifest.json",
        public_episodes_path=result.output_directory / "campaign_episodes_public.csv",
        label_masks_path=result.output_directory / "episode_label_masks.csv",
        observations_path=result.output_directory / "direct_observations.csv",
        episode_id=public[0]["episode_id"],
    )
    assert len(episode.anchor_observations) == 4
    assert {row["endpoint"] for row in episode.anchor_observations} == set(ENDPOINTS)
    assert all(
        row["molecule_id"] == episode.anchor_molecule_id
        for row in episode.anchor_observations
    )
    assert "selector_cyp_truth" not in episode.public

    mixed_masks = result.output_directory / "mixed_masks.csv"
    mask_rows = _rows(result.output_directory / "episode_label_masks.csv")
    observation_rows = _rows(result.output_directory / "direct_observations.csv")
    target = next(
        row
        for row in observation_rows
        if row["similarity_component_hash"] != episode.public["outer_group_id"]
        and row["endpoint"] == "CYP1A2"
    )
    references = json.loads(mask_rows[0]["anchor_observation_references"])
    references["CYP1A2"] = target["observation_id"]
    mask_rows[0]["anchor_observation_references"] = json.dumps(
        references, sort_keys=True, separators=(",", ":")
    )
    with mixed_masks.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=mask_rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(mask_rows)
    with pytest.raises(ValueError, match="manifest receipt mismatch"):
        load_oracle_episode(
            manifest_path=result.output_directory / "manifest.json",
            public_episodes_path=result.output_directory
            / "campaign_episodes_public.csv",
            label_masks_path=mixed_masks,
            observations_path=result.output_directory / "direct_observations.csv",
            episode_id=public[0]["episode_id"],
        )

    foreign_id = target["molecule_id"]
    foreign_rows = {
        row["endpoint"]: row
        for row in observation_rows
        if row["molecule_id"] == foreign_id
    }
    mask_rows[0]["anchor_molecule_id_truth"] = foreign_id
    mask_rows[0]["anchor_observation_references"] = json.dumps(
        {endpoint: foreign_rows[endpoint]["observation_id"] for endpoint in ENDPOINTS},
        sort_keys=True,
        separators=(",", ":"),
    )
    mask_rows[0]["anchor_value_availability_mask"] = json.dumps(
        {
            endpoint: {
                field: bool(foreign_rows[endpoint][field])
                for field in ("point", "low", "high", "std")
            }
            for endpoint in ENDPOINTS
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    forged_masks = result.output_directory / "forged_masks.csv"
    with forged_masks.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=mask_rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(mask_rows)
    forged_manifest = result.output_directory / "forged_manifest.json"
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    manifest["outputs"]["episode_label_masks.csv"].update(
        {
            "sha256": _digest(forged_masks),
            "rows": len(mask_rows),
        }
    )
    forged_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="anchor observation reference mismatch"):
        load_oracle_episode(
            manifest_path=forged_manifest,
            public_episodes_path=result.output_directory
            / "campaign_episodes_public.csv",
            label_masks_path=forged_masks,
            observations_path=result.output_directory / "direct_observations.csv",
            episode_id=public[0]["episode_id"],
        )


def _logic_inputs(query_points: list[str]) -> _Inputs:
    molecule_ids = [
        "anchor-wide",
        "anchor-narrow",
        *(f"query-{i:02d}" for i in range(12)),
        "remote",
    ]
    component = "a" * 64
    observations: dict[str, dict[str, dict[str, str]]] = {}
    molecules = {}
    for index, molecule_id in enumerate(molecule_ids):
        observations[molecule_id] = {}
        for endpoint in ENDPOINTS:
            point = "5" if molecule_id.startswith("anchor") else "4"
            if molecule_id.startswith("query") and endpoint == "CYP2D6":
                point = query_points[index - 2]
            low, high = ("4", "6") if molecule_id == "anchor-wide" else ("4.8", "5.2")
            observations[molecule_id][endpoint] = {
                "value_state": "complete",
                "point": point,
                "low": low,
                "high": high,
                "std": "0.1",
                "observation_id": hashlib.sha256(
                    f"{molecule_id}|{endpoint}".encode()
                ).hexdigest(),
            }
        molecules[molecule_id] = _Molecule(molecule_id, "CC", "CC", "b" * 64, component)
    pairs = tuple(
        DirectPair("anchor-narrow", f"query-{index:02d}", component, 0.99 - index / 100)
        for index in range(12)
    ) + (DirectPair("anchor-wide", "query-00", component, 0.7),)
    outer = {(component, repeat): repeat for repeat in range(3)}
    return _Inputs(
        observations,
        molecules,
        {component: tuple(molecule_ids)},
        outer,
        pairs,
    )


def test_anchor_ties_query_rank_cap_and_nonanchor_magnitude_invariance() -> None:
    first = _base_episodes(_logic_inputs([str(3 + i / 10) for i in range(12)]))
    second = _base_episodes(_logic_inputs([str(8 - i / 10) for i in range(12)]))
    primary_first = [item for item in first if item.policy == "selected_anchor"]
    primary_second = [item for item in second if item.policy == "selected_anchor"]
    assert all(item.anchor == "anchor-narrow" for item in primary_first)
    assert all(len(item.queries) == 10 for item in primary_first)
    assert primary_first[0].queries == tuple(
        f"query-{index:02d}" for index in range(10)
    )
    assert [item.queries for item in primary_first] == [
        item.queries for item in primary_second
    ]
    assert all("remote" not in item.queries for item in primary_first)


def test_projection_validator_rejects_truth_mask_and_noncanonical_cells(
    tmp_path: Path,
) -> None:
    chain = _synthetic_chain(tmp_path)
    result = _run(chain, tmp_path / "output")
    public = _rows(result.output_directory / "campaign_episodes_public.csv")
    truth = _rows(result.output_directory / "campaign_episodes_truth.csv")
    masks = _rows(result.output_directory / "episode_label_masks.csv")
    observation_rows = _rows(result.output_directory / "direct_observations.csv")
    observations: dict[str, dict[str, dict[str, str]]] = {}
    members: dict[str, set[str]] = {}
    for row in observation_rows:
        observations.setdefault(row["molecule_id"], {})[row["endpoint"]] = row
        members.setdefault(row["similarity_component_hash"], set()).add(
            row["molecule_id"]
        )
    outer_folds = {
        (row["similarity_component_hash"], int(row["repeat"])): int(row["outer_fold"])
        for row in _rows(result.output_directory / "group_folds.csv")
    }

    def validate(
        public_rows: list[dict[str, str]],
        truth_rows: list[dict[str, str]],
        mask_rows: list[dict[str, str]],
    ) -> None:
        validate_generated_projections(
            csv_bytes(PUBLIC_EPISODE_COLUMNS, public_rows),
            csv_bytes(TRUTH_COLUMNS, truth_rows),
            csv_bytes(MASK_COLUMNS, mask_rows),
            observations,
            {key: tuple(sorted(value)) for key, value in members.items()},
            outer_folds,
            chain["source_revision"],
        )

    bad_truth = json.loads(json.dumps(truth))
    references = json.loads(bad_truth[0]["query_truth_references"])
    references[0]["CYP1A2"] = "0" * 64
    bad_truth[0]["query_truth_references"] = json.dumps(
        references, sort_keys=True, separators=(",", ":")
    )
    with pytest.raises(ValueError, match="query reference defect"):
        validate(public, bad_truth, masks)

    bad_masks = json.loads(json.dumps(masks))
    anchor_references = json.loads(bad_masks[0]["anchor_observation_references"])
    anchor_references["CYP1A2"] = "0" * 64
    bad_masks[0]["anchor_observation_references"] = json.dumps(
        anchor_references, sort_keys=True, separators=(",", ":")
    )
    with pytest.raises(ValueError, match="anchor reference defect"):
        validate(public, truth, bad_masks)

    bad_public = json.loads(json.dumps(public))
    bad_public[0]["query_molecule_ids"] = " " + bad_public[0]["query_molecule_ids"]
    with pytest.raises(ValueError, match="not canonical"):
        validate(bad_public, truth, masks)


def test_receipt_and_policy_drift_fail_before_output(tmp_path: Path) -> None:
    chain = _synthetic_chain(tmp_path)
    observations = chain["r2a"] / "direct_observations.csv"
    observations.write_bytes(
        observations.read_bytes().replace(b"direct-0", b"direct-X", 1)
    )
    output = tmp_path / "drift"
    with pytest.raises(ValueError, match="receipt mismatch"):
        _run(chain, output)
    assert not output.exists()
    contract_path = chain["validation_contract_path"]
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["campaign_episodes"]["query_rule"]["cap"] = 11
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    with pytest.raises(ValueError, match="query policy drift"):
        _run(chain, tmp_path / "policy")
    assert not (tmp_path / "policy").exists()

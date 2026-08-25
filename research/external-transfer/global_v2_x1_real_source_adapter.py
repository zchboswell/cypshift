#!/usr/bin/env python3
"""Receipt-bound real-source adapter for the EXP-X1 support compilation.

This module is deliberately additive.  It reuses the accepted G2-5B ChEMBL
compiler, chemistry standardizer, and union graph, while replacing only the
synthetic challenge-input boundary with the accepted R2B identity projection.
Target-bearing direct-observation suffixes are discarded without decoding.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

from rdkit import rdBase

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import global_v2_x1_compiler as base  # noqa: E402

from cypshift import openadmet_features as features  # noqa: E402
from cypshift.chemistry import STANDARDIZATION_VERSION  # noqa: E402
from cypshift.openadmet_campaign_io import R2B_SCHEMA_VERSION  # noqa: E402
from cypshift.openadmet_global_v2_firewall import (  # noqa: E402
    is_confirmatory_component,
)
from cypshift.openadmet_validation import FOLD_COLUMNS as R2B_FOLD_COLUMNS  # noqa: E402
from cypshift.openadmet_validation_contract import (  # noqa: E402
    DIRECT_SOURCE_FILE,
    SEEDS,
)

CLAIM: Final = (
    ROOT
    / "benchmarks/openadmet_cyp_2026/global_v2_x1_acquisition_claim.json"
)
CLAIM_SHA256: Final = (
    "f1bea8327896c0eb01a2a13032af265f1ed0b42d280109acdf10262ae1ba5c60"
)
TERMINAL_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_x1_adapter_terminal.v1"
)
SYNTHETIC_STATUS: Final = "G2_5D_X1_OFFICIAL_SHAPED_SYNTHETIC_ACCEPTED"
OFFICIAL_ACCEPTED_STATUS: Final = "G2_5C_X1_SUPPORT_ACCEPTED"
OFFICIAL_REJECTED_STATUS: Final = "G2_5C_X1_SUPPORT_REJECTED"

R2B_FILES: Final = frozenset(
    {
        "direct_observations.csv",
        "group_folds.csv",
        "campaign_episodes_public.csv",
        "campaign_episodes_truth.csv",
        "episode_label_masks.csv",
        "topology_viability.json",
        "manifest.json",
    }
)
DIRECT_NAME: Final = "direct_observations.csv"
FOLDS_NAME: Final = "group_folds.csv"
ENDPOINTS: Final = frozenset(base.ENDPOINTS)
OFFICIAL_COUNTS: Final = {
    "direct_observations": 19_620,
    "group_fold_rows": 73_575,
    "molecules": 4_905,
}
ADAPTER_TERMINAL_NAMES: Final = (
    "x1_adapter_filter_counts.json",
    "x1_adapter_chemistry_counts.json",
    "x1_adapter_union_counts.json",
    "x1_adapter_cell_support.csv",
    "x1_adapter_support_decisions.json",
    "x1_adapter_result.json",
    "manifest.json",
)


class X1AdapterError(base.X1SyntheticError):
    """A receipt, identity projection, fold, or publication invariant failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X1AdapterError(message)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{label} is not an object")
    return cast(Mapping[str, Any], value)


def _integer(value: object, label: str) -> int:
    _require(type(value) is int, f"{label} is not an integer")
    return cast(int, value)


def _index(value: str, size: int, label: str) -> int:
    _require(value.isdigit(), f"{label} is not an integer")
    result = int(value)
    _require(0 <= result < size, f"{label} is out of range")
    return result


def _digest(value: str, label: str) -> str:
    _require(
        len(value) == 64 and all(character in "0123456789abcdef" for character in value),
        f"{label} is not a SHA-256 digest",
    )
    return value


def _read_regular_bytes(path: Path, label: str) -> bytes:
    base._regular_readonly(path, label)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise X1AdapterError(f"cannot read {label}: {exc}") from exc


def _json_bytes(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=base._json_pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise X1AdapterError(f"cannot parse {label}") from exc
    _require(isinstance(value, dict), f"{label} root is not an object")
    return cast(dict[str, Any], value)


def tracked_claim() -> dict[str, Any]:
    """Authenticate and return the immutable unconsumed tracked claim."""

    _require(base.sha256_path(CLAIM) == CLAIM_SHA256, "tracked acquisition claim differs")
    claim = base.read_json(CLAIM)
    future = _mapping(claim.get("future_consumption_bindings"), "future bindings")
    _require(
        claim.get("status")
        == "immutable_unconsumed_claim_adapter_acceptance_required"
        and claim.get("consumed") is False
        and claim.get("maximum_consumptions") == 1
        and set(future)
        == {
            "real_source_adapter_sha256",
            "acquisition_wrapper_sha256",
            "official_shaped_synthetic_driver_sha256",
            "official_shaped_synthetic_acceptance_sha256",
            "adapter_acceptance_receipt_sha256",
        }
        and all(value is None for value in future.values()),
        "tracked acquisition claim state differs",
    )
    return claim


def validate_consumed_claim(claim: Mapping[str, Any]) -> None:
    """Reject any private claim that changes more than the frozen state fields."""

    tracked = tracked_claim()
    for key, value in tracked.items():
        if key not in {"status", "consumed", "future_consumption_bindings"}:
            _require(claim.get(key) == value, f"consumed claim field differs: {key}")
    future = _mapping(claim.get("future_consumption_bindings"), "consumed bindings")
    _require(
        claim.get("status") == "immutable_consumed_claim_adapter_accepted"
        and claim.get("consumed") is True
        and set(future)
        == {
            "real_source_adapter_sha256",
            "acquisition_wrapper_sha256",
            "official_shaped_synthetic_driver_sha256",
            "official_shaped_synthetic_acceptance_sha256",
            "adapter_acceptance_receipt_sha256",
        }
        and future.get("real_source_adapter_sha256") == base.sha256_path(SCRIPT)
        and all(
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
            for value in future.values()
        ),
        "consumed claim implementation binding differs",
    )


def _authenticate_r2b(
    source_root: Path,
    *,
    synthetic: bool,
    claim: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], bytes, bytes, dict[str, int]]:
    base._readonly_root(source_root, "R2B source root")
    _require(
        {item.name for item in source_root.iterdir()} == R2B_FILES,
        "R2B source file set differs",
    )
    manifest_data = _read_regular_bytes(source_root / "manifest.json", "R2B manifest")
    direct_data = _read_regular_bytes(source_root / DIRECT_NAME, "direct observations")
    fold_data = _read_regular_bytes(source_root / FOLDS_NAME, "group folds")
    manifest = _json_bytes(manifest_data, "R2B manifest")
    _require(
        manifest.get("schema_version") == R2B_SCHEMA_VERSION
        and manifest.get("deterministic") is True,
        "R2B manifest identity differs",
    )
    counts_value = _mapping(manifest.get("counts"), "R2B counts")
    outputs = _mapping(manifest.get("outputs"), "R2B outputs")
    direct_receipt = _mapping(outputs.get(DIRECT_NAME), "direct output receipt")
    fold_receipt = _mapping(outputs.get(FOLDS_NAME), "fold output receipt")
    counts = {
        "direct_observations": _integer(
            counts_value.get("direct_observations"), "direct observation count"
        ),
        "group_fold_rows": _integer(
            counts_value.get("group_fold_rows"), "group fold count"
        ),
    }
    _require(
        direct_receipt.get("sha256") == base.sha256_bytes(direct_data)
        and direct_receipt.get("rows") == counts["direct_observations"]
        and fold_receipt.get("sha256") == base.sha256_bytes(fold_data)
        and fold_receipt.get("rows") == counts["group_fold_rows"],
        "R2B manifest receipt differs",
    )
    if synthetic:
        _require(claim is None, "synthetic R2B source received a claim")
        revision = manifest.get("source_revision")
        _require(
            isinstance(revision, str) and revision.startswith("synthetic-x1-"),
            "synthetic R2B revision differs",
        )
        _require(
            counts["direct_observations"] % len(ENDPOINTS) == 0,
            "synthetic direct count is not endpoint-aligned",
        )
        counts["molecules"] = counts["direct_observations"] // len(ENDPOINTS)
    else:
        _require(claim is not None, "official R2B source has no consumed claim")
        official_claim = cast(Mapping[str, Any], claim)
        challenge = _mapping(
            official_claim.get("challenge_source"), "claim challenge source"
        )
        _require(
            source_root.resolve(strict=True) == Path(cast(str, challenge["root"]))
            and base.sha256_bytes(manifest_data) == challenge.get("r2b_manifest_sha256")
            and base.sha256_bytes(direct_data)
            == challenge.get("direct_observations_sha256")
            and base.sha256_bytes(fold_data) == challenge.get("group_folds_sha256")
            and manifest.get("source_revision") == challenge.get("dataset_revision")
            and challenge.get("exact_training_structures") == OFFICIAL_COUNTS["molecules"],
            "official R2B claim receipt differs",
        )
        counts["molecules"] = OFFICIAL_COUNTS["molecules"]
        _require(counts == OFFICIAL_COUNTS, "official R2B cardinality differs")
    return manifest, direct_data, fold_data, counts


def _direct_identities(
    data: bytes, expected_rows: int, expected_molecules: int
) -> dict[str, dict[str, str]]:
    try:
        rows = features._parse_direct_prefix(data, expected_rows)
    except features.OpenADMETFeatureProjectionError as exc:
        raise X1AdapterError(str(exc)) from exc
    by_molecule: dict[str, dict[str, str]] = {}
    endpoint_sets: dict[str, set[str]] = defaultdict(set)
    observation_ids: set[str] = set()
    for row in rows:
        observation_id = row["observation_id"]
        molecule_id = row["molecule_id"]
        endpoint = row["endpoint"]
        _digest(observation_id, "observation identity")
        _require(observation_id not in observation_ids, "duplicate observation identity")
        observation_ids.add(observation_id)
        _require(molecule_id != "", "empty molecule identity")
        _require(endpoint in ENDPOINTS, "unexpected direct endpoint")
        _require(row["source_file"] == DIRECT_SOURCE_FILE, "direct source filename differs")
        _require(row["source_row"].isdigit() and int(row["source_row"]) > 0, "direct source row differs")
        _require(
            row["source_row_id"] == f"{DIRECT_SOURCE_FILE}:{row['source_row']}",
            "direct source-row identity differs",
        )
        _digest(row["source_sha256"], "direct source receipt")
        _require(row["raw_smiles"] != "", "empty challenge structure")
        existing = by_molecule.setdefault(molecule_id, dict(row))
        _require(
            all(
                existing[key] == row[key]
                for key in (
                    "molecule_id",
                    "source_row_id",
                    "source_file",
                    "source_row",
                    "source_sha256",
                    "raw_smiles",
                )
            ),
            "direct identity drift across endpoints",
        )
        _require(endpoint not in endpoint_sets[molecule_id], "duplicate endpoint for molecule")
        endpoint_sets[molecule_id].add(endpoint)
    _require(len(by_molecule) == expected_molecules, "challenge molecule count differs")
    _require(
        all(values == ENDPOINTS for values in endpoint_sets.values()),
        "endpoint cardinality differs",
    )
    return by_molecule


def _fold_rows(data: bytes, expected_rows: int) -> list[dict[str, str]]:
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True)
        header = next(reader, None)
        _require(header == list(R2B_FOLD_COLUMNS), "group fold header differs")
        rows: list[dict[str, str]] = []
        for values in reader:
            _require(len(values) == len(R2B_FOLD_COLUMNS), "group fold field count differs")
            rows.append(dict(zip(R2B_FOLD_COLUMNS, values, strict=True)))
    except (UnicodeError, csv.Error) as exc:
        raise X1AdapterError("cannot parse group folds") from exc
    _require(len(rows) == expected_rows, "group fold row count differs")
    return rows


def _validate_folds(
    rows: Sequence[Mapping[str, str]], direct: Mapping[str, Mapping[str, str]]
) -> tuple[list[dict[str, str]], dict[str, str]]:
    components: dict[str, str] = {}
    seen: set[tuple[str, int, int]] = set()
    converted: list[dict[str, str]] = []
    for row in rows:
        molecule_id = row["molecule_id"]
        _require(molecule_id in direct, "fold contains a non-challenge molecule")
        component = _digest(row["similarity_component_hash"], "fold component")
        previous = components.setdefault(molecule_id, component)
        _require(previous == component, "fold component drift")
        repeat = _index(row["repeat"], len(SEEDS), "fold repeat")
        _require(row["seed"] == str(SEEDS[repeat]), "fold seed differs")
        assigned_outer = _index(row["outer_fold"], 5, "assigned outer fold")
        outer_context = _index(
            row["outer_validation_fold"], 5, "outer validation fold"
        )
        key = (molecule_id, repeat, outer_context)
        _require(key not in seen, "duplicate molecule/repeat/outer fold row")
        seen.add(key)
        if assigned_outer == outer_context:
            _require(row["inner_fold"] == "", "outer validation row has an inner fold")
        else:
            _index(row["inner_fold"], 4, "inner fold")
        converted.append(
            {
                "molecule_id": molecule_id,
                "repeat": str(repeat),
                "outer_context": str(outer_context),
                "assigned_outer": str(assigned_outer),
                "inner_fold": row["inner_fold"],
            }
        )
    expected_keys = {
        (molecule_id, repeat, outer)
        for molecule_id in direct
        for repeat in base.REPEATS
        for outer in base.OUTER_FOLDS
    }
    _require(seen == expected_keys, "fold molecule/repeat/outer coverage differs")
    _require(set(components) == set(direct), "fold molecule identity differs")

    component_members: dict[str, set[str]] = defaultdict(set)
    for molecule_id, component in components.items():
        component_members[component].add(molecule_id)
    index = {
        (row["molecule_id"], int(row["repeat"]), int(row["outer_context"])): row
        for row in converted
    }
    for component, members in component_members.items():
        _require(bool(members), f"empty component {component}")
        for repeat in base.REPEATS:
            assigned = {
                int(index[(member, repeat, outer)]["assigned_outer"])
                for member in members
                for outer in base.OUTER_FOLDS
            }
            _require(len(assigned) == 1, "component crosses an outer boundary")
            assigned_outer = next(iter(assigned))
            for outer in base.OUTER_FOLDS:
                inner = {
                    index[(member, repeat, outer)]["inner_fold"] for member in members
                }
                if outer == assigned_outer:
                    _require(inner == {""}, "held-out component has an inner assignment")
                else:
                    _require(len(inner) == 1 and "" not in inner, "component crosses an inner boundary")
    converted.sort(
        key=lambda row: (
            row["molecule_id"],
            int(row["repeat"]),
            int(row["outer_context"]),
        )
    )
    return converted, components


def challenge_inputs(
    source_root: Path,
    *,
    synthetic: bool,
    claim: Mapping[str, Any] | None = None,
) -> tuple[list[base.StructureIdentity], list[dict[str, str]], dict[str, Any]]:
    """Project only receipt-bound challenge identities, structures, and folds."""

    manifest, direct_data, fold_data, counts = _authenticate_r2b(
        source_root, synthetic=synthetic, claim=claim
    )
    direct = _direct_identities(
        direct_data, counts["direct_observations"], counts["molecules"]
    )
    folds, components = _validate_folds(
        _fold_rows(fold_data, counts["group_fold_rows"]), direct
    )
    identities: list[base.StructureIdentity] = []
    for molecule_id in sorted(direct):
        component = components[molecule_id]
        identity = base._structure_identity(
            "challenge",
            molecule_id,
            direct[molecule_id]["raw_smiles"],
            component,
            is_confirmatory_component(component),
        )
        _require(identity is not None, "challenge structure was quarantined")
        identities.append(cast(base.StructureIdentity, identity))
    component_counts = Counter(cast(str, item.challenge_component) for item in identities)
    metadata = {
        "source_revision": manifest["source_revision"],
        "direct_observation_records_scanned": counts["direct_observations"],
        "decoded_prefix_fields": counts["direct_observations"] * 8,
        "opaque_suffixes_discarded": counts["direct_observations"],
        "challenge_molecules": len(identities),
        "challenge_components": len(component_counts),
        "confirmatory_molecules": sum(item.confirmatory for item in identities),
        "confirmatory_components": len(
            {item.challenge_component for item in identities if item.confirmatory}
        ),
        "target_values_parsed": 0,
        "target_values_retained": 0,
    }
    return identities, folds, metadata


def compile_source(
    *,
    database_path: Path,
    challenge_root: Path,
    private_root: Path,
    synthetic: bool,
    consumed_claim: Mapping[str, Any] | None = None,
) -> tuple[base.Compilation, dict[str, Any]]:
    """Compile ChEMBL support using the accepted G2-5B scientific machinery."""

    base.static_contract()
    _require(
        not private_root.exists() and not private_root.is_symlink(),
        "private root exists",
    )
    if synthetic:
        _require(consumed_claim is None, "synthetic compilation received a claim")
    else:
        _require(consumed_claim is not None, "official compilation has no consumed claim")
        validate_consumed_claim(cast(Mapping[str, Any], consumed_claim))
    rows = base.read_sqlite_rows(database_path)
    eligible, external, filter_counts = base.filter_rows(rows)
    challenge, folds, projection = challenge_inputs(
        challenge_root, synthetic=synthetic, claim=consumed_claim
    )
    component_by_hash, forbidden, union_counts, node_bytes, edge_bytes = base.build_union(
        external, challenge
    )
    support, safe_identities, decisions = base.support_rows(
        eligible,
        external,
        challenge,
        folds,
        component_by_hash,
        forbidden,
    )
    raw_bytes = base._raw_jsonl(rows)
    challenge_bytes = base.csv_bytes(
        base.CHALLENGE_COLUMNS,
        [
            {
                "molecule_id": item.source_id,
                "raw_smiles": item.raw_smiles,
                "challenge_component": cast(str, item.challenge_component),
                "confirmatory": "1" if item.confirmatory else "0",
            }
            for item in challenge
        ],
    )
    fold_bytes = base.csv_bytes(base.FOLD_COLUMNS, folds)
    logical_source = base.sha256_bytes(
        base.json_bytes(
            {
                "semantic_source_id": "chembl-37-plus-r2b-identity-projection-v1",
                "raw_source_rows_sha256": base.sha256_bytes(raw_bytes),
                "challenge_rows_sha256": base.sha256_bytes(challenge_bytes),
                "fold_rows_sha256": base.sha256_bytes(fold_bytes),
            }
        )
    )
    chemistry_counts = {
        "eligible_external_compounds": len(external),
        "eligible_external_standardized_structures": len(
            {item.structure_hash for item in external}
        ),
        "challenge_molecules": len(challenge),
        "challenge_components": len({item.challenge_component for item in challenge}),
        "standardization_version": STANDARDIZATION_VERSION,
        "rdkit_version": rdBase.rdkitVersion,
        "equivalence_policy": "rdkit-standard-inchi-connectivity-block-v1",
    }
    safe_columns = (
        "scope",
        "endpoint",
        "repeat",
        "outer_fold",
        "inner_fold",
        "standardized_structure_hash",
        "union_component_hash",
    )
    private_files = {
        "raw_source_rows.jsonl": raw_bytes,
        "eligible_activities.csv": base.csv_bytes(base.ELIGIBLE_COLUMNS, eligible),
        "external_identities.csv": base.csv_bytes(
            base.IDENTITY_COLUMNS, base._identity_rows(external)
        ),
        "union_nodes.csv": node_bytes,
        "union_edges.csv": edge_bytes,
        "cell_safe_external_identities.csv": base.csv_bytes(
            safe_columns, safe_identities
        ),
    }
    base.publish_files(private_root, private_files)
    compilation = base.Compilation(
        raw_rows=tuple(dict(row) for row in rows),
        eligible_rows=tuple(eligible),
        external_identities=tuple(external),
        challenge_identities=tuple(challenge),
        folds=tuple(folds),
        filter_counts=filter_counts,
        chemistry_counts=chemistry_counts,
        union_counts=union_counts,
        support_rows=tuple(support),
        support_decisions=decisions,
        logical_source_sha256=logical_source,
        component_by_hash=component_by_hash,
        global_forbidden_hashes=forbidden,
        private_files=private_files,
    )
    return compilation, projection


def terminal_files(
    compilation: base.Compilation,
    projection: Mapping[str, Any],
    *,
    synthetic: bool,
    consumed_claim_sha256: str | None = None,
) -> dict[str, bytes]:
    """Return aggregate-only terminal bytes; never publish restricted rows."""

    _require(
        (synthetic and consumed_claim_sha256 is None)
        or (not synthetic and consumed_claim_sha256 is not None),
        "terminal claim identity differs",
    )
    filter_bytes = base.json_bytes(compilation.filter_counts)
    chemistry_bytes = base.json_bytes(compilation.chemistry_counts)
    union_bytes = base.json_bytes(compilation.union_counts)
    support_bytes = base.csv_bytes(base.SUPPORT_COLUMNS, compilation.support_rows)
    decision_value = dict(compilation.support_decisions)
    decision_value["scientific_interpretation"] = (
        "Official-shaped synthetic support mechanics only."
        if synthetic
        else "Aggregate ChEMBL support feasibility; no model-quality evidence."
    )
    decisions_bytes = base.json_bytes(decision_value)
    status = (
        SYNTHETIC_STATUS
        if synthetic
        else (
            OFFICIAL_ACCEPTED_STATUS
            if compilation.support_decisions["official_thresholds"]["pass"]
            else OFFICIAL_REJECTED_STATUS
        )
    )
    counts = {
        "activity_rows": compilation.filter_counts["joined_rows"],
        "eligible_activity_rows": compilation.filter_counts["eligible_rows"],
        "ineligible_activity_rows": compilation.filter_counts["ineligible_rows"],
        "external_compounds": compilation.chemistry_counts[
            "eligible_external_compounds"
        ],
        "challenge_molecules": projection["challenge_molecules"],
        "challenge_components": projection["challenge_components"],
        "global_forbidden_structures": compilation.union_counts[
            "global_forbidden_structures"
        ],
        "union_nodes": compilation.union_counts["union_unique_structure_nodes"],
        "union_components": compilation.union_counts["union_components"],
        "outer_endpoint_cells": sum(
            row["scope"] == "OUTER" for row in compilation.support_rows
        ),
        "inner_endpoint_cells": sum(
            row["scope"] == "INNER" for row in compilation.support_rows
        ),
        "confirmatory_endpoint_cells": sum(
            row["scope"] == "CONFIRMATORY" for row in compilation.support_rows
        ),
    }
    accounting = {
        "synthetic_sqlite_files_created": 1 if synthetic else 0,
        "synthetic_activity_rows_opened": (
            compilation.filter_counts["joined_rows"] if synthetic else 0
        ),
        "synthetic_union_comparisons": (
            compilation.union_counts["pairwise_similarity_comparisons"] if synthetic else 0
        ),
        "external_activity_rows_opened": (
            0 if synthetic else compilation.filter_counts["joined_rows"]
        ),
        "official_training_structures_opened": (
            0 if synthetic else projection["challenge_molecules"]
        ),
        "decoded_direct_prefix_fields": projection["decoded_prefix_fields"],
        "opaque_direct_suffixes_discarded": projection["opaque_suffixes_discarded"],
        "target_values_parsed": 0,
        "target_values_retained": 0,
        **{name: 0 for name in base.OFFICIAL_ZERO_FIELDS},
    }
    if not synthetic:
        accounting.update(
            {
                "new_external_records_opened": compilation.filter_counts[
                    "joined_rows"
                ],
                "external_dataset_files_downloaded": 1,
                "official_structures_opened": projection["challenge_molecules"],
                "execution_claims_created_or_consumed": 1,
            }
        )
    result = {
        "schema_version": "cypshift.openadmet_cyp_2026.global_v2_x1_adapter_result.v1",
        "status": status,
        "synthetic": synthetic,
        "accepted_compiler_sha256": base.sha256_path(base.SCRIPT),
        "logical_source_sha256": compilation.logical_source_sha256,
        "consumed_claim_sha256": consumed_claim_sha256,
        "counts": counts,
        "miniature_support_pass": compilation.support_decisions[
            "miniature_thresholds"
        ]["pass"],
        "official_support_pass": compilation.support_decisions["official_thresholds"][
            "pass"
        ],
        "scientific_interpretation": decision_value["scientific_interpretation"],
    }
    files = {
        "x1_adapter_filter_counts.json": filter_bytes,
        "x1_adapter_chemistry_counts.json": chemistry_bytes,
        "x1_adapter_union_counts.json": union_bytes,
        "x1_adapter_cell_support.csv": support_bytes,
        "x1_adapter_support_decisions.json": decisions_bytes,
        "x1_adapter_result.json": base.json_bytes(result),
    }
    manifest = {
        "schema_version": TERMINAL_SCHEMA,
        "status": status,
        "synthetic": synthetic,
        "accepted_compiler_sha256": base.sha256_path(base.SCRIPT),
        "adapter_source_sha256": base.sha256_path(SCRIPT),
        "claim_template_sha256": CLAIM_SHA256,
        "consumed_claim_sha256": consumed_claim_sha256,
        "logical_source_sha256": compilation.logical_source_sha256,
        "counts": counts,
        "projection": dict(projection),
        "accounting": accounting,
        "authority": {
            "synthetic_adapter_mechanics": synthetic,
            "external_record_acquisition": not synthetic,
            "official_identity_inputs": not synthetic,
            "official_target_values": False,
            "official_features": False,
            "model_fitting": False,
            "prediction_generation": False,
            "metric_evaluation": False,
            "confirmatory_truth": False,
            "blinded_test": False,
            "submission": False,
            "leaderboard_selection": False,
            "upload": False,
        },
        "outputs": {name: base.sha256_bytes(value) for name, value in sorted(files.items())},
        "private_files_retained": 0,
        "deterministic": True,
    }
    files["manifest.json"] = base.json_bytes(manifest)
    _require(tuple(sorted(files)) == tuple(sorted(ADAPTER_TERMINAL_NAMES)), "terminal file set differs")
    return files


def run_replay(
    *,
    database_path: Path,
    challenge_root: Path,
    replay_root: Path,
    synthetic: bool,
    consumed_claim: Mapping[str, Any] | None = None,
    consumed_claim_sha256: str | None = None,
) -> Path:
    _require(not replay_root.exists() and not replay_root.is_symlink(), "replay root exists")
    private = replay_root.with_name(f".{replay_root.name}-private")
    _require(not private.exists() and not private.is_symlink(), "private replay root exists")
    try:
        compilation, projection = compile_source(
            database_path=database_path,
            challenge_root=challenge_root,
            private_root=private,
            synthetic=synthetic,
            consumed_claim=consumed_claim,
        )
        files = terminal_files(
            compilation,
            projection,
            synthetic=synthetic,
            consumed_claim_sha256=consumed_claim_sha256,
        )
    except BaseException:
        base.cleanup(private)
        raise
    base.cleanup(private)
    _require(not private.exists(), "private replay cleanup differs")
    return base.publish_files(replay_root, files)


__all__ = [
    "ADAPTER_TERMINAL_NAMES",
    "CLAIM",
    "CLAIM_SHA256",
    "OFFICIAL_COUNTS",
    "R2B_FILES",
    "SCRIPT",
    "SYNTHETIC_STATUS",
    "X1AdapterError",
    "challenge_inputs",
    "compile_source",
    "run_replay",
    "terminal_files",
    "tracked_claim",
    "validate_consumed_claim",
]

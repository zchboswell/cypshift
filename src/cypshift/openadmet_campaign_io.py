"""Narrow serialization and projection boundary for OpenADMET R2B."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from rdkit import rdBase

from cypshift.chemistry import STANDARDIZATION_VERSION
from cypshift.openadmet_validation import (
    FOLD_COLUMNS,
    OBSERVATION_COLUMNS,
    R2A_SCHEMA_VERSION,
)
from cypshift.openadmet_validation_contract import (
    CANDIDATE_POOL_ID,
    CONTRACT_SCHEMA_VERSION,
    ENDPOINTS,
    EPISODE_ID_POLICY_ID,
    FOLD_POLICY_ID,
    INNER_SCOPE,
    JSON_CELL_POLICY_ID,
    MASK_COLUMNS,
    OUTER_SCOPE,
    PROTOCOL,
    PUBLIC_EPISODE_COLUMNS,
    SEEDS,
    SELECTED_ANCHOR_POLICY,
    SELECTOR_ENDPOINTS,
    STRESS_ANCHOR_POLICY,
    TRUTH_COLUMNS,
)
from cypshift.openadmet_viability import TOPOLOGY_VIABILITY_SCHEMA_VERSION

R2B_SCHEMA_VERSION = "cypshift.openadmet_cyp_2026.validation_artifacts.v1"


class CampaignIOError(ValueError):
    """An R2B byte stream or restricted projection is invalid."""


@dataclass(frozen=True, slots=True)
class OracleEpisode:
    """Exactly one public episode and its four permitted anchor observations."""

    public: dict[str, str]
    anchor_molecule_id: str
    anchor_observations: tuple[dict[str, str], ...]
    anchor_value_availability_mask: dict[str, Any]


def build_manifest(
    *,
    schema_version: str,
    contract: Mapping[str, Any],
    contract_hash: str,
    source_revision: str,
    r2a_hashes: Mapping[str, str],
    outputs: Mapping[str, bytes],
    observation_count: int,
    fold_count: int,
    public_rows: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    """Build the combined deterministic manifest for all six payloads."""

    expanded_queries = sum(
        len(json_list(row["query_molecule_ids"], "query molecule IDs"))
        for row in public_rows
    )
    output_receipts: dict[str, Any] = {}
    for name, data in outputs.items():
        receipt: dict[str, Any] = {"sha256": sha256(data).hexdigest()}
        if name.endswith(".csv"):
            receipt["rows"] = csv_row_count(data)
        else:
            receipt["schema_version"] = TOPOLOGY_VIABILITY_SCHEMA_VERSION
        output_receipts[name] = receipt
    return {
        "schema_version": schema_version,
        "source_revision": source_revision,
        "validation_contract": {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "sha256": contract_hash,
        },
        "inputs": {
            "r2a_manifest.json": {"sha256": r2a_hashes["manifest.json"]},
            "direct_observations.csv": {
                "sha256": r2a_hashes["direct_observations.csv"],
                "rows": observation_count,
            },
            "group_folds.csv": {
                "sha256": r2a_hashes["group_folds.csv"],
                "rows": fold_count,
            },
        },
        "schemas": {
            "direct_observations.csv": list(OBSERVATION_COLUMNS),
            "group_folds.csv": list(FOLD_COLUMNS),
            "campaign_episodes_public.csv": list(PUBLIC_EPISODE_COLUMNS),
            "campaign_episodes_truth.csv": list(TRUTH_COLUMNS),
            "episode_label_masks.csv": list(MASK_COLUMNS),
            "topology_viability.json": TOPOLOGY_VIABILITY_SCHEMA_VERSION,
        },
        "policies": {
            "fold_policy_id": FOLD_POLICY_ID,
            "outer_scope": OUTER_SCOPE,
            "inner_scope": INNER_SCOPE,
            "episode_id_policy_id": EPISODE_ID_POLICY_ID,
            "json_cell_policy_id": JSON_CELL_POLICY_ID,
            "protocol": PROTOCOL,
            "candidate_pool_id": CANDIDATE_POOL_ID,
            "seeds": list(SEEDS),
        },
        "counts": {
            "direct_observations": observation_count,
            "group_fold_rows": fold_count,
            "episode_rows": len(public_rows),
            "expanded_queries": expanded_queries,
        },
        "outputs": output_receipts,
        "accounting": _mapping(
            _mapping(_mapping(contract, "acceptance"), "r2b_success"), "accounting"
        ),
        "authority": _mapping(contract, "authority_after_successful_r2b"),
        "deterministic": True,
    }


def load_oracle_episode(
    *,
    manifest_path: Path,
    public_episodes_path: Path,
    label_masks_path: Path,
    observations_path: Path,
    episode_id: str,
) -> OracleEpisode:
    """Resolve one runner projection without accepting any truth-artifact path."""

    manifest_bytes = read_bytes(manifest_path, "campaign manifest")
    streams = {
        "public": read_bytes(public_episodes_path, "public episodes"),
        "masks": read_bytes(label_masks_path, "episode label masks"),
        "observations": read_bytes(observations_path, "direct observations"),
    }
    manifest = json_data(manifest_bytes, "campaign manifest")
    if (
        manifest.get("schema_version") != R2B_SCHEMA_VERSION
        or manifest.get("deterministic") is not True
    ):
        raise CampaignIOError("campaign manifest identity mismatch")
    output_receipts = _mapping(manifest, "outputs")
    for key, name in (
        ("public", "campaign_episodes_public.csv"),
        ("masks", "episode_label_masks.csv"),
        ("observations", "direct_observations.csv"),
    ):
        receipt = _mapping(output_receipts, name)
        if (
            receipt.get("sha256") != sha256(streams[key]).hexdigest()
            or receipt.get("rows") != csv_row_count(streams[key])
        ):
            raise CampaignIOError(f"campaign manifest receipt mismatch for {name}")
    public_rows = csv_rows(streams["public"], PUBLIC_EPISODE_COLUMNS, "public episodes")
    mask_rows = csv_rows(streams["masks"], MASK_COLUMNS, "episode label masks")
    observation_rows = csv_rows(
        streams["observations"], OBSERVATION_COLUMNS, "direct observations"
    )
    public = _one(public_rows, episode_id, "public episode")
    mask = _one(mask_rows, episode_id, "episode label mask")
    queries = json_list(public["query_molecule_ids"], "public query IDs")
    if (
        not is_digest(public["episode_id"])
        or not is_digest(public["outer_group_id"])
        or public["protocol"] != PROTOCOL
        or public["repeat"] not in {"0", "1", "2"}
        or public["outer_fold"] not in {"0", "1", "2", "3", "4"}
        or public["candidate_pool_id"] != CANDIDATE_POOL_ID
        or public["episode_policy_id"]
        not in {SELECTED_ANCHOR_POLICY, STRESS_ANCHOR_POLICY}
        or not queries
        or not all(isinstance(value, str) and value for value in queries)
        or len(queries) != len(set(cast(list[str], queries)))
        or public["query_molecule_ids"] != compact_json(queries)
    ):
        raise CampaignIOError("public episode semantic-schema mismatch")
    references = json_object(mask["anchor_observation_references"], "anchor references")
    availability = json_object(
        mask["anchor_value_availability_mask"], "anchor availability"
    )
    if set(references) != set(ENDPOINTS) or set(availability) != set(ENDPOINTS):
        raise CampaignIOError("anchor projection endpoint schema mismatch")
    by_id = {row["observation_id"]: row for row in observation_rows}
    if len(by_id) != len(observation_rows):
        raise CampaignIOError("duplicate direct-observation identity")
    anchor = mask["anchor_molecule_id_truth"]
    if not anchor or anchor in queries:
        raise CampaignIOError("anchor identity projection mismatch")
    if mask["anchor_observation_references"] != compact_json(references) or mask[
        "anchor_value_availability_mask"
    ] != compact_json(availability):
        raise CampaignIOError("anchor projection JSON is not canonical")
    resolved: list[dict[str, str]] = []
    for endpoint in ENDPOINTS:
        reference = references[endpoint]
        if not isinstance(reference, str) or reference not in by_id:
            raise CampaignIOError("unknown anchor observation reference")
        row = by_id[reference]
        if (
            row["molecule_id"] != anchor
            or row["endpoint"] != endpoint
            or row["similarity_component_hash"] != public["outer_group_id"]
        ):
            raise CampaignIOError("anchor observation reference mismatch")
        endpoint_mask = availability[endpoint]
        if not isinstance(endpoint_mask, dict) or endpoint_mask != {
            field: bool(row[field]) for field in ("point", "low", "high", "std")
        }:
            raise CampaignIOError("anchor availability mask mismatch")
        resolved.append(row)
    return OracleEpisode(public, anchor, tuple(resolved), availability)


def verify_r2a_receipts(
    *,
    contract: Mapping[str, Any],
    contract_hash: str,
    source_revision: str,
    manifest: Mapping[str, Any],
    hashes: Mapping[str, str],
    data: Mapping[str, bytes],
) -> None:
    """Bind the four load-once R2B inputs to the contract and R2A manifest."""

    if manifest.get("schema_version") != R2A_SCHEMA_VERSION:
        raise CampaignIOError("R2A manifest schema mismatch")
    if manifest.get("source_revision") != source_revision:
        raise CampaignIOError("R2A source revision mismatch")
    contract_receipt = _mapping(manifest, "validation_contract")
    if (
        contract_receipt.get("schema_version") != CONTRACT_SCHEMA_VERSION
        or contract_receipt.get("sha256") != contract_hash
    ):
        raise CampaignIOError("R2A validation-contract receipt mismatch")
    outputs = _mapping(manifest, "outputs")
    chain = _mapping(contract, "input_chain")
    viability_receipts = _mapping(
        _mapping(contract, "topology_viability"), "input_receipts"
    )
    r2a_receipts = _mapping(viability_receipts, "r2a_validation_inputs")
    if r2a_receipts.get("schema_version") != R2A_SCHEMA_VERSION:
        raise CampaignIOError("R2B R2A input schema mismatch")
    for name in ("direct_observations.csv", "group_folds.csv"):
        manifest_receipt = _mapping(outputs, name)
        contract_receipt = _mapping(r2a_receipts, name)
        actual_rows = csv_row_count(data[name])
        if (
            manifest_receipt.get("sha256") != hashes[name]
            or manifest_receipt.get("rows") != actual_rows
            or contract_receipt.get("sha256") != hashes[name]
            or contract_receipt.get("rows") != actual_rows
        ):
            raise CampaignIOError(f"{name} receipt mismatch")
    authority = _mapping(manifest, "authority")
    if any(value is not False for value in authority.values()):
        raise CampaignIOError("R2A authority must remain denied")
    accounting = _mapping(manifest, "accounting")
    for key in (
        "tdi_files_opened",
        "blinded_test_files_opened",
        "model_fits",
        "predictions",
        "metric_evaluations",
        "submissions",
    ):
        if accounting.get(key) != 0:
            raise CampaignIOError("R2A forbidden-operation accounting drift")
    if accounting.get("source_values_parsed") != 0:
        raise CampaignIOError("R2A source-value accounting drift")
    if manifest.get("deterministic") is not True:
        raise CampaignIOError("R2A determinism receipt mismatch")
    policies = _mapping(manifest, "policies")
    if policies != {
        "fold_policy_id": FOLD_POLICY_ID,
        "outer_scope": OUTER_SCOPE,
        "inner_scope": INNER_SCOPE,
        "seeds": list(SEEDS),
    }:
        raise CampaignIOError("R2A fold policy receipt mismatch")
    environment = _mapping(manifest, "environment")
    if environment != {
        "rdkit_version": rdBase.rdkitVersion,
        "standardization_version": STANDARDIZATION_VERSION,
    }:
        raise CampaignIOError("R2A chemistry environment receipt mismatch")
    inputs = _mapping(manifest, "inputs")
    direct = _mapping(chain, "direct_source")
    if _mapping(inputs, cast(str, direct["path"])).get("sha256") != direct.get(
        "sha256"
    ):
        raise CampaignIOError("R2A direct-source receipt mismatch")
    r1 = _mapping(chain, "r1_source_row_adapter")
    topology = _mapping(chain, "r1_topology")
    expected_inputs = {
        "r1_manifest.json": r1["manifest_sha256"],
        "molecules_input.csv": r1["molecules_sha256"],
        "source_rows.csv": r1["source_rows_sha256"],
        "topology_manifest.json": topology["manifest_sha256"],
        "molecule_audit.csv": topology["molecule_audit_sha256"],
        "training_topology.csv": topology["training_topology_sha256"],
    }
    if any(
        _mapping(inputs, name).get("sha256") != digest
        for name, digest in expected_inputs.items()
    ):
        raise CampaignIOError("R2A parent input receipt mismatch")
    if _mapping(inputs, "source_rows.csv").get("source_values_parsed") is not False:
        raise CampaignIOError("R2A source-row parse authority mismatch")
    counts = _mapping(manifest, "counts")
    row_contract = _mapping(_mapping(contract, "direct_compiler"), "row_contract")
    direct_rows = direct["rows"]
    direct_molecules = row_contract["source_identities"]
    states = _mapping(counts, "states")
    if (
        counts.get("direct_source_rows") != direct_rows
        or counts.get("direct_observations") != row_contract["expected_rows"]
        or counts.get("direct_molecules") != direct_molecules
        or counts.get("group_fold_rows") != direct_molecules * len(SEEDS) * 5
        or not all(isinstance(value, int) and value >= 0 for value in states.values())
        or sum(cast(int, value) for value in states.values())
        != row_contract["expected_rows"]
    ):
        raise CampaignIOError("R2A count receipt mismatch")
    if _mapping(viability_receipts, "direct_source") != direct:
        raise CampaignIOError("topology-viability direct receipt drift")
    if _mapping(viability_receipts, "r1_source_row_adapter") != r1:
        raise CampaignIOError("topology-viability R1 receipt drift")
    expected_topology = {
        key: topology[key]
        for key in (
            "manifest_sha256",
            "molecule_audit_sha256",
            "training_topology_sha256",
        )
    }
    if _mapping(viability_receipts, "r1_topology") != expected_topology:
        raise CampaignIOError("topology-viability topology receipt drift")


def validate_generated_projections(
    public_bytes: bytes,
    truth_bytes: bytes,
    mask_bytes: bytes,
    observations: Mapping[str, Mapping[str, Mapping[str, str]]],
    component_members: Mapping[str, tuple[str, ...]],
    outer_folds: Mapping[tuple[str, int], int],
    source_revision: str,
) -> None:
    """Validate exact projection schemas and joins before any file is written."""

    from cypshift.openadmet_validation_contract import TRUTH_COLUMNS

    public = csv_rows(public_bytes, PUBLIC_EPISODE_COLUMNS, "public episodes")
    truth = csv_rows(truth_bytes, TRUTH_COLUMNS, "episode truth")
    masks = csv_rows(mask_bytes, MASK_COLUMNS, "episode masks")
    public_ids = [row["episode_id"] for row in public]
    if public_ids != [row["episode_id"] for row in truth] or public_ids != [
        row["episode_id"] for row in masks
    ]:
        raise CampaignIOError("generated projection join mismatch")
    for public_row, truth_row, mask_row in zip(public, truth, masks, strict=True):
        if (
            not is_digest(public_row["episode_id"])
            or not is_digest(public_row["outer_group_id"])
            or public_row["protocol"] != PROTOCOL
            or public_row["candidate_pool_id"] != CANDIDATE_POOL_ID
            or public_row["episode_policy_id"]
            not in {SELECTED_ANCHOR_POLICY, STRESS_ANCHOR_POLICY}
            or public_row["repeat"] not in {"0", "1", "2"}
            or public_row["outer_fold"] not in {"0", "1", "2", "3", "4"}
        ):
            raise CampaignIOError("generated public semantic-schema defect")
        queries = json_list(public_row["query_molecule_ids"], "public query IDs")
        references = json_list(truth_row["query_truth_references"], "query references")
        availability = json_list(
            truth_row["query_truth_availability_masks"], "query availability"
        )
        if (
            not queries
            or not all(isinstance(value, str) and value for value in queries)
            or len(queries) != len(set(cast(list[str], queries)))
            or len(queries) != len(references)
            or len(queries) != len(availability)
        ):
            raise CampaignIOError("generated query array alignment defect")
        anchor = mask_row["anchor_molecule_id_truth"]
        selector = truth_row["selector_cyp_truth"]
        if (
            selector not in SELECTOR_ENDPOINTS
            or anchor != truth_row["anchor_molecule_id_truth"]
            or anchor in queries
        ):
            raise CampaignIOError("generated anchor projection defect")
        component = public_row["outer_group_id"]
        repeat = int(public_row["repeat"])
        members = set(component_members.get(component, ()))
        if (
            anchor not in members
            or not set(cast(list[str], queries)) <= members
            or outer_folds.get((component, repeat)) != int(public_row["outer_fold"])
        ):
            raise CampaignIOError("generated query membership defect")
        expected_id = sha256(
            "|".join(
                (
                    source_revision,
                    PROTOCOL,
                    str(repeat),
                    component,
                    selector,
                    public_row["episode_policy_id"],
                )
            ).encode()
        ).hexdigest()
        if public_row["episode_id"] != expected_id:
            raise CampaignIOError("generated episode ID defect")
        for cell, parsed in (
            (public_row["query_molecule_ids"], queries),
            (truth_row["query_truth_references"], references),
            (truth_row["query_truth_availability_masks"], availability),
        ):
            if cell != compact_json(parsed):
                raise CampaignIOError("generated JSON cell is not canonical")
        for query, references_item, availability_item in zip(
            cast(list[str], queries), references, availability, strict=True
        ):
            expected_query_references = {
                endpoint: observations[query][endpoint]["observation_id"]
                for endpoint in ENDPOINTS
            }
            expected_query_availability = {
                endpoint: {
                    field: bool(observations[query][endpoint][field])
                    for field in ("point", "low", "high", "std")
                }
                for endpoint in ENDPOINTS
            }
            if references_item != expected_query_references:
                raise CampaignIOError("generated query reference defect")
            if availability_item != expected_query_availability:
                raise CampaignIOError("generated query availability defect")
        expected_references = {
            endpoint: observations[anchor][endpoint]["observation_id"]
            for endpoint in ENDPOINTS
        }
        expected_availability = {
            endpoint: {
                field: bool(observations[anchor][endpoint][field])
                for field in ("point", "low", "high", "std")
            }
            for endpoint in ENDPOINTS
        }
        parsed_references = json_object(
            mask_row["anchor_observation_references"], "anchor references"
        )
        parsed_availability = json_object(
            mask_row["anchor_value_availability_mask"], "anchor availability"
        )
        if mask_row["anchor_observation_references"] != compact_json(
            parsed_references
        ) or mask_row["anchor_value_availability_mask"] != compact_json(
            parsed_availability
        ):
            raise CampaignIOError("generated anchor JSON cell is not canonical")
        if parsed_references != expected_references:
            raise CampaignIOError("generated anchor reference defect")
        if parsed_availability != expected_availability:
            raise CampaignIOError("generated anchor availability defect")


def read_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CampaignIOError(f"cannot read {label}: {exc}") from exc


def json_data(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CampaignIOError(f"cannot parse {label}") from exc
    if not isinstance(value, dict):
        raise CampaignIOError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def csv_rows(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""))
        header = next(reader, None)
        if header != list(columns):
            raise CampaignIOError(f"{label} header mismatch")
        rows = []
        for values in reader:
            if len(values) != len(columns):
                raise CampaignIOError(f"{label} field-count mismatch")
            rows.append(dict(zip(columns, values, strict=True)))
        return rows
    except (UnicodeError, csv.Error) as exc:
        raise CampaignIOError(f"cannot parse {label}") from exc


def csv_row_count(data: bytes) -> int:
    try:
        return max(sum(1 for _ in csv.reader(io.StringIO(data.decode("utf-8")))) - 1, 0)
    except (UnicodeError, csv.Error) as exc:
        raise CampaignIOError("cannot count CSV rows") from exc


def csv_bytes(columns: Sequence[str], rows: Sequence[Mapping[str, str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def compact_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def json_list(value: str, label: str) -> list[Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise CampaignIOError(f"cannot parse {label}") from exc
    if not isinstance(parsed, list):
        raise CampaignIOError(f"{label} must be an array")
    return parsed


def json_object(value: str, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise CampaignIOError(f"cannot parse {label}") from exc
    if not isinstance(parsed, dict):
        raise CampaignIOError(f"{label} must be an object")
    return cast(dict[str, Any], parsed)


def is_digest(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def write_new(path: Path, content: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise CampaignIOError(f"refusing to overwrite {path}") from exc


def sha_receipt(data: bytes) -> dict[str, str]:
    return {"sha256": sha256(data).hexdigest()}


def _mapping(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise CampaignIOError(f"{key} must be an object")
    return cast(dict[str, Any], item)


def _one(rows: Sequence[dict[str, str]], episode_id: str, label: str) -> dict[str, str]:
    selected = [row for row in rows if row["episode_id"] == episode_id]
    if len(selected) != 1:
        raise CampaignIOError(f"{label} must have exactly one matching row")
    return selected[0]


__all__ = [
    "CampaignIOError",
    "OracleEpisode",
    "R2B_SCHEMA_VERSION",
    "bool_text",
    "build_manifest",
    "compact_json",
    "csv_bytes",
    "csv_row_count",
    "csv_rows",
    "is_digest",
    "json_bytes",
    "json_data",
    "json_list",
    "json_object",
    "load_oracle_episode",
    "read_bytes",
    "validate_generated_projections",
    "verify_r2a_receipts",
    "write_new",
]

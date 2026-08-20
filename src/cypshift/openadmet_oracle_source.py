"""Trusted synthetic parent-artifact compiler for the R5B TRACE boundary.

The compiler is intentionally a small, private bridge between the accepted R2,
R3A, R3C, and R4 artifacts and :mod:`openadmet_oracle_projection`.  It reads a
test-sized analogue of those artifacts once, authenticates every byte before
decoding any field, and emits the canonical source files consumed by the
capability splitter.  It never discovers files, opens challenge test/TDI
inputs, fits a model, or computes a score.
"""

from __future__ import annotations

import io
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import numpy as np

from cypshift.openadmet_oracle_projection import (
    PUBLIC_QUERY_COLUMNS,
    SOURCE_COLUMNS,
    SOURCE_FILES,
)
from cypshift.openadmet_oracle_source_io import (
    OpenADMETOracleSourceIOError,
    canonical_int,
    csv_rows,
    finite,
    json_list,
    json_object,
    json_object_cell,
    json_value,
    mapping,
    publish,
    safe_source_path,
    sha_digest,
)
from cypshift.openadmet_transformation_compiler import PAIR_COLUMNS
from cypshift.openadmet_transformation_io import (
    STRUCTURE_COLUMNS,
    canonical_csv_bytes,
    canonical_json_bytes,
)
from cypshift.openadmet_transformation_serialization import EPISODE_COLUMNS
from cypshift.openadmet_validation import FOLD_COLUMNS, OBSERVATION_COLUMNS
from cypshift.openadmet_validation_contract import (
    ENDPOINTS,
    MASK_COLUMNS,
    PUBLIC_EPISODE_COLUMNS,
    TRUTH_COLUMNS,
)

PARENT_CONTRACT_SHA256 = (
    "c1d7a66c4f479339b30c2006e4250381cb213d665d4902c71d4c4edbd347e8bf"
)
CONTRACT_SHA256 = "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
SCHEMA_VERSION = "cypshift.openadmet_cyp_2026.oracle_source_bundle.v1"
G0_SYSTEM_ID = "TRACE-G0-MAPL-FIXED"
VALID_EXTRACTIONS = frozenset({"VALID_SINGLE", "VALID_DOUBLE", "VALID_STEREO"})
STAGES = ("outer", "inner")
REPEATS = range(3)
OUTER_FOLDS = range(5)
INNER_FOLDS = range(4)

FEATURE_FILES = (
    "maplight_morgan_count.npy",
    "maplight_avalon_count.npy",
    "maplight_erg.npy",
    "maplight_rdkit_descriptors.npy",
    "morgan_binary.npy",
)
INPUT_FILES = (
    "direct_observations.csv",
    "group_folds.csv",
    "campaign_episodes_public.csv",
    "campaign_episodes_truth.csv",
    "episode_label_masks.csv",
    "feature_manifest.json",
    "feature_rows.csv",
    *FEATURE_FILES,
    "global_oof_predictions.csv",
    "global_inner_oof_predictions.csv",
    "transformation_pairs.csv",
    "episode_transformations.csv",
    "transformation_coverage.json",
)
OOF_COLUMNS = (
    "molecule_id",
    "endpoint",
    "component_id",
    "repeat",
    "outer_fold",
    "inner_fold",
    "scope",
    "system_id",
    "prediction",
    "applicability_score",
    "model_id",
    "feature_spec_id",
    "split_id",
)
FEATURE_ROW_COLUMNS = (
    "molecule_id",
    "raw_structure_sha256",
    "standardized_structure_hash",
    "similarity_component_hash",
)
SOURCE_ACCOUNTING = (
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
DENIED_AUTHORITY = {
    "oracle_evidence": False,
    "inferred_anchor_contract": False,
    "model_fits": False,
    "predictions": False,
    "internal_metrics": False,
    "official_st_rae": False,
    "test_access": False,
    "tdi": False,
    "submission": False,
    "transduction": False,
}


class OpenADMETOracleSourceError(OpenADMETOracleSourceIOError):
    """Raised when an authenticated parent artifact cannot be compiled."""


@dataclass(frozen=True, slots=True)
class OracleSourceResult:
    """Published source bundle and its exact manifest receipt."""

    output_directory: Path
    manifest_path: Path
    manifest_sha256: str
    output_receipts: Mapping[str, Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class _Scope:
    stage: str
    repeat: int
    outer: int
    inner: int | None


def compile_openadmet_oracle_source(
    source_paths: Mapping[str, Path],
    output_directory: Path,
    *,
    expected_receipts: Mapping[str, str],
    contract_sha256: str = CONTRACT_SHA256,
) -> OracleSourceResult:
    """Compile one receipt-bound synthetic R5B source bundle.

    ``source_paths`` must name exactly :data:`INPUT_FILES`.  The input files
    are all read once into immutable byte buffers; every expected digest is
    checked before any CSV, JSON, or NPY parser runs.  A caller cannot point
    this function at official data accidentally because it has no discovery
    mode and rejects unknown source names.
    """

    if output_directory.exists() or output_directory.is_symlink():
        raise OpenADMETOracleSourceError("output path already exists")
    if contract_sha256 != CONTRACT_SHA256:
        raise OpenADMETOracleSourceError("oracle contract receipt differs")
    if tuple(source_paths) != INPUT_FILES or set(expected_receipts) != set(INPUT_FILES):
        raise OpenADMETOracleSourceError("source file set differs")
    loaded = _load_once(source_paths, expected_receipts)
    parsed = _parse_parent_artifacts(loaded, expected_receipts, contract_sha256)
    outputs, accounting = _compile_outputs(parsed, loaded, expected_receipts)
    manifest = _build_manifest(
        contract_sha256,
        expected_receipts,
        loaded,
        outputs,
        accounting,
        parsed["counts"],
    )
    manifest_data = canonical_json_bytes(manifest)
    all_outputs = dict(outputs)
    all_outputs["manifest.json"] = manifest_data
    try:
        publish(output_directory, all_outputs)
    except OpenADMETOracleSourceIOError as exc:
        raise OpenADMETOracleSourceError(str(exc)) from exc
    receipts = cast(dict[str, Mapping[str, Any]], manifest["output_receipts"])
    return OracleSourceResult(
        output_directory,
        output_directory / "manifest.json",
        sha256(manifest_data).hexdigest(),
        receipts,
    )


def build_openadmet_oracle_source(*args: Any, **kwargs: Any) -> OracleSourceResult:
    """Compatibility spelling for callers that use ``build`` terminology."""

    return compile_openadmet_oracle_source(*args, **kwargs)


def _load_once(
    paths: Mapping[str, Path], expected: Mapping[str, str]
) -> dict[str, bytes]:
    loaded: dict[str, bytes] = {}
    for name in INPUT_FILES:
        try:
            path = safe_source_path(paths[name], name)
        except OpenADMETOracleSourceIOError as exc:
            raise OpenADMETOracleSourceError(str(exc)) from exc
        data = path.read_bytes()
        digest = expected[name]
        sha_digest(digest, name)
        if sha256(data).hexdigest() != digest:
            raise OpenADMETOracleSourceError(f"source receipt mismatch: {name}")
        loaded[name] = data
    return loaded


def _parse_parent_artifacts(
    loaded: Mapping[str, bytes], expected: Mapping[str, str], contract_sha256: str
) -> dict[str, Any]:
    direct = csv_rows(loaded["direct_observations.csv"], OBSERVATION_COLUMNS, "direct")
    folds = csv_rows(loaded["group_folds.csv"], FOLD_COLUMNS, "folds")
    public = csv_rows(
        loaded["campaign_episodes_public.csv"], PUBLIC_EPISODE_COLUMNS, "public"
    )
    truth = csv_rows(loaded["campaign_episodes_truth.csv"], TRUTH_COLUMNS, "truth")
    masks = csv_rows(loaded["episode_label_masks.csv"], MASK_COLUMNS, "masks")
    feature_manifest = json_object(loaded["feature_manifest.json"], "feature manifest")
    feature_rows = csv_rows(
        loaded["feature_rows.csv"], FEATURE_ROW_COLUMNS, "feature rows"
    )
    arrays = _validate_features(loaded, feature_manifest, feature_rows)
    outer_oof = csv_rows(loaded["global_oof_predictions.csv"], OOF_COLUMNS, "outer OOF")
    inner_oof = csv_rows(
        loaded["global_inner_oof_predictions.csv"], OOF_COLUMNS, "inner OOF"
    )
    pairs = csv_rows(
        loaded["transformation_pairs.csv"], PAIR_COLUMNS, "transformation pairs"
    )
    episodes = csv_rows(
        loaded["episode_transformations.csv"],
        EPISODE_COLUMNS,
        "episode transformations",
    )
    coverage = json_object(loaded["transformation_coverage.json"], "coverage")
    molecules, direct_by_molecule = _molecule_index(direct, feature_rows)
    fold_index = _fold_index(folds, molecules)
    public_rows = _expanded_public(
        public, truth, masks, molecules, fold_index, direct_by_molecule
    )
    episode_geometry = _geometry_index(episodes, public_rows, pairs, coverage)
    oof = _oof_index(outer_oof, inner_oof, molecules)
    counts = {
        "molecules": len(molecules),
        "direct_rows": len(direct),
        "fold_rows": len(folds),
        "selected_public_rows": sum(
            row["episode_policy_id"] == "selected_anchor" for row in public_rows
        ),
        "stress_public_rows": sum(
            row["episode_policy_id"] == "deterministic_random_anchor_stress"
            for row in public_rows
        ),
    }
    if contract_sha256 not in {PARENT_CONTRACT_SHA256, CONTRACT_SHA256}:
        sha_digest(contract_sha256, "contract")
    return {
        "molecules": molecules,
        "direct": direct_by_molecule,
        "folds": fold_index,
        "public": public_rows,
        "geometry": episode_geometry,
        "pairs": pairs,
        "oof": oof,
        "arrays": arrays,
        "counts": counts,
        "contract_sha256": contract_sha256,
        "direct_values": _numeric_values(direct),
    }


def _molecule_index(
    direct_rows: Sequence[Mapping[str, str]],
    feature_rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, dict[str, str]]]]:
    by_molecule: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    metadata: dict[str, tuple[str, str, str, str]] = {}
    for row in direct_rows:
        molecule, endpoint = row["molecule_id"], row["endpoint"]
        if endpoint not in ENDPOINTS or endpoint in by_molecule[molecule]:
            raise OpenADMETOracleSourceError("direct identity differs")
        if row["source_file"] != "cyp-challenge-TRAIN_inhibition.csv":
            raise OpenADMETOracleSourceError("direct source file differs")
        if (
            sha256(row["raw_smiles"].encode()).hexdigest()
            != row["raw_structure_sha256"]
        ):
            raise OpenADMETOracleSourceError("raw structure receipt differs")
        item = (
            row["raw_smiles"],
            row["standardized_structure_hash"],
            row["similarity_component_hash"],
            row["scaffold_group_hash"],
        )
        if molecule in metadata and metadata[molecule] != item:
            raise OpenADMETOracleSourceError("direct molecule metadata differs")
        metadata[molecule] = item
        by_molecule[molecule][endpoint] = dict(row)
    if not by_molecule or any(
        set(values) != set(ENDPOINTS) for values in by_molecule.values()
    ):
        raise OpenADMETOracleSourceError("direct endpoint coverage differs")
    features = {row["molecule_id"]: row for row in feature_rows}
    if set(features) != set(by_molecule):
        raise OpenADMETOracleSourceError("feature/direct molecule set differs")
    molecules: dict[str, dict[str, str]] = {}
    for molecule in sorted(by_molecule):
        raw, standard_hash, component, _scaffold = metadata[molecule]
        feature = features[molecule]
        if feature["raw_structure_sha256"] != sha256(raw.encode()).hexdigest():
            raise OpenADMETOracleSourceError("feature raw structure receipt differs")
        if feature["standardized_structure_hash"] != standard_hash:
            raise OpenADMETOracleSourceError(
                "feature standard structure receipt differs"
            )
        if feature["similarity_component_hash"] != component:
            raise OpenADMETOracleSourceError("feature component receipt differs")
        standardized = _standardized_smiles(raw, standard_hash)
        molecules[molecule] = {
            "molecule_id": molecule,
            "raw_smiles": raw,
            "raw_structure_sha256": feature["raw_structure_sha256"],
            "standardized_smiles": standardized,
            "standardized_structure_hash": standard_hash,
            "similarity_component_hash": component,
        }
    return molecules, {key: dict(value) for key, value in by_molecule.items()}


def _standardized_smiles(raw: str, expected_hash: str) -> str:
    # The accepted R3A standardizer is the same deterministic core used by R2.
    from cypshift.chemistry import standardize_molecule
    from cypshift.schema import MoleculeInput, MoleculeStatus

    record = standardize_molecule(
        MoleculeInput("synthetic-r5b", raw, "smiles", "openadmet-r5b", "{}")
    )
    if (
        record.status is not MoleculeStatus.ACCEPTED
        or record.standardized_structure is None
    ):
        raise OpenADMETOracleSourceError("standardization rejected molecule")
    if record.standardized_structure_hash != expected_hash:
        raise OpenADMETOracleSourceError("standardized structure receipt differs")
    standardized_structure: str = record.standardized_structure
    return standardized_structure


def _fold_index(
    rows: Sequence[Mapping[str, str]], molecules: Mapping[str, Mapping[str, str]]
) -> dict[tuple[str, int, int], Mapping[str, str]]:
    index: dict[tuple[str, int, int], Mapping[str, str]] = {}
    for row in rows:
        molecule = row["molecule_id"]
        if molecule not in molecules:
            raise OpenADMETOracleSourceError("fold molecule is unknown")
        repeat, validation = (
            canonical_int(row["repeat"], "repeat"),
            canonical_int(row["outer_validation_fold"], "validation fold"),
        )
        outer = canonical_int(row["outer_fold"], "outer fold")
        if (
            repeat not in REPEATS
            or validation not in OUTER_FOLDS
            or outer not in OUTER_FOLDS
        ):
            raise OpenADMETOracleSourceError("fold scope differs")
        if (
            row["similarity_component_hash"]
            != molecules[molecule]["similarity_component_hash"]
        ):
            raise OpenADMETOracleSourceError("fold component differs")
        if outer == validation and row["inner_fold"] != "":
            raise OpenADMETOracleSourceError("outer heldout fold has inner assignment")
        if (
            outer != validation
            and canonical_int(row["inner_fold"], "inner fold") not in INNER_FOLDS
        ):
            raise OpenADMETOracleSourceError("inner fold differs")
        key = (molecule, repeat, validation)
        if key in index:
            raise OpenADMETOracleSourceError("duplicate fold row")
        index[key] = row
    expected = len(molecules) * 3 * 5
    if len(index) != expected:
        raise OpenADMETOracleSourceError("fold cardinality differs")
    return index


def _expanded_public(
    public: Sequence[Mapping[str, str]],
    truth: Sequence[Mapping[str, str]],
    masks: Sequence[Mapping[str, str]],
    molecules: Mapping[str, Mapping[str, str]],
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
    direct: Mapping[str, Mapping[str, Mapping[str, str]]],
) -> list[dict[str, str]]:
    truths = {row["episode_id"]: row for row in truth}
    mask_by_id = {row["episode_id"]: row for row in masks}
    if len(truths) != len(truth) or len(mask_by_id) != len(masks):
        raise OpenADMETOracleSourceError("episode identity duplicates")
    output: list[dict[str, str]] = []
    for row in public:
        episode = row["episode_id"]
        if episode in {item["episode_id"] for item in output}:
            raise OpenADMETOracleSourceError("duplicate public episode")
        if episode not in truths or episode not in mask_by_id:
            raise OpenADMETOracleSourceError("episode truth/mask join differs")
        queries = json_list(row["query_molecule_ids"], "query IDs")
        truth_row = truths[episode]
        mask = mask_by_id[episode]
        anchor = mask["anchor_molecule_id_truth"]
        if not anchor or anchor in queries or anchor not in molecules:
            raise OpenADMETOracleSourceError("anchor identity differs")
        repeat, outer = (
            canonical_int(row["repeat"], "episode repeat"),
            canonical_int(row["outer_fold"], "episode outer"),
        )
        if repeat not in REPEATS or outer not in OUTER_FOLDS:
            raise OpenADMETOracleSourceError("episode scope differs")
        component = row["outer_group_id"]
        if molecules[anchor]["similarity_component_hash"] != component:
            raise OpenADMETOracleSourceError("episode anchor component differs")
        if any(
            query not in molecules
            or molecules[query]["similarity_component_hash"] != component
            for query in queries
        ):
            raise OpenADMETOracleSourceError("episode query component differs")
        if (
            truth_row["anchor_molecule_id_truth"] != anchor
            or truth_row["selector_cyp_truth"] not in ENDPOINTS
        ):
            raise OpenADMETOracleSourceError("episode truth identity differs")
        anchor_refs = json_object_cell(
            mask["anchor_observation_references"], "anchor references"
        )
        anchor_availability = json_object_cell(
            mask["anchor_value_availability_mask"], "anchor availability"
        )
        _validate_observation_projection(
            anchor, anchor_refs, anchor_availability, direct
        )
        query_refs = json_value(truth_row["query_truth_references"], "query references")
        query_availability = json_value(
            truth_row["query_truth_availability_masks"], "query availability"
        )
        if (
            not isinstance(query_refs, list)
            or not isinstance(query_availability, list)
            or len(query_refs) != len(queries)
            or len(query_availability) != len(queries)
        ):
            raise OpenADMETOracleSourceError("query projection cardinality differs")
        assigned = canonical_int(
            folds[(anchor, repeat, outer)]["outer_fold"], "anchor assignment"
        )
        if assigned != outer:
            raise OpenADMETOracleSourceError("episode anchor is not held out")
        for rank, query in enumerate(queries, 1):
            refs = query_refs[rank - 1]
            available = query_availability[rank - 1]
            if not isinstance(refs, dict) or not isinstance(available, dict):
                raise OpenADMETOracleSourceError("query projection object differs")
            _validate_observation_projection(query, refs, available, direct)
            output.append(
                {
                    "episode_id": episode,
                    "episode_policy_id": row["episode_policy_id"],
                    "repeat": str(repeat),
                    "outer_fold": str(outer),
                    "outer_group_id": component,
                    "anchor_molecule_id": anchor,
                    "query_molecule_id": query,
                    "query_rank": str(rank),
                    "_selector_cyp_truth": truths[episode]["selector_cyp_truth"],
                }
            )
    return sorted(
        output, key=lambda item: (item["episode_id"], int(item["query_rank"]))
    )


def _geometry_index(
    episodes: Sequence[Mapping[str, str]],
    public: Sequence[Mapping[str, str]],
    pairs: Sequence[Mapping[str, str]],
    coverage: Mapping[str, Any],
) -> dict[tuple[str, int], Mapping[str, str]]:
    if coverage.get("status") != "R4_TRANSFORMATION_COVERAGE_SUPPORTED":
        raise OpenADMETOracleSourceError("R4 coverage is not supported")
    pair_index = {row["transformation_pair_id"]: row for row in pairs}
    if len(pair_index) != len(pairs):
        raise OpenADMETOracleSourceError("transformation pair identity duplicates")
    public_by_key = {(row["episode_id"], int(row["query_rank"])): row for row in public}
    public_keys = set(public_by_key)
    output: dict[tuple[str, int], Mapping[str, Any]] = {}
    for row in episodes:
        key = (row["episode_id"], canonical_int(row["query_rank"], "query rank"))
        if key in output or key not in public_keys:
            raise OpenADMETOracleSourceError("episode geometry join differs")
        pair = pair_index.get(row["transformation_pair_id"])
        if pair is None:
            raise OpenADMETOracleSourceError("episode pair is unknown")
        finite(pair["similarity"], "pair similarity")
        if not 0.0 <= float(pair["similarity"]) <= 1.0:
            raise OpenADMETOracleSourceError("pair similarity differs")
        public_row = public_by_key[key]
        if any(
            row[field] != public_row[field]
            for field in (
                "episode_policy_id",
                "repeat",
                "outer_fold",
                "outer_group_id",
                "query_molecule_id",
            )
        ) or row["anchor_molecule_id"] not in {
            pair["left_molecule_id"],
            pair["right_molecule_id"],
        }:
            raise OpenADMETOracleSourceError("episode geometry identity differs")
        if pair["similarity_component_hash"] != public_row["outer_group_id"]:
            raise OpenADMETOracleSourceError("episode pair component differs")
        expected_direction = (
            pair["a_to_b_direction_id"]
            if row["anchor_molecule_id"] == pair["left_molecule_id"]
            else pair["b_to_a_direction_id"]
        )
        if row["direction_id"] != expected_direction:
            raise OpenADMETOracleSourceError("episode direction differs")
        if row["extraction_status"] in VALID_EXTRACTIONS:
            if not row["direction_id"] or not row["transformation_class_id"]:
                raise OpenADMETOracleSourceError("valid transformation fields missing")
        output[key] = {**row, "_pair": pair_index[row["transformation_pair_id"]]}
    if set(output) != public_keys:
        raise OpenADMETOracleSourceError("episode geometry coverage differs")
    return output


def _validate_observation_projection(
    molecule: str,
    references: Mapping[str, Any],
    availability: Mapping[str, Any],
    direct: Mapping[str, Mapping[str, Mapping[str, str]]],
) -> None:
    if set(references) != set(ENDPOINTS) or set(availability) != set(ENDPOINTS):
        raise OpenADMETOracleSourceError("observation projection endpoints differ")
    for endpoint in ENDPOINTS:
        row = direct[molecule][endpoint]
        if references[endpoint] != row["observation_id"]:
            raise OpenADMETOracleSourceError("observation reference differs")
        value = availability[endpoint]
        if not isinstance(value, dict) or value != _availability(row):
            raise OpenADMETOracleSourceError("observation availability differs")


def _availability(row: Mapping[str, str]) -> dict[str, bool]:
    return {field: bool(row[field]) for field in ("point", "low", "high", "std")}


def _oof_index(
    outer: Sequence[Mapping[str, str]],
    inner: Sequence[Mapping[str, str]],
    molecules: Mapping[str, Mapping[str, str]],
) -> dict[tuple[str, int, int, int | None], Mapping[str, str]]:
    output: dict[tuple[str, int, int, int | None], Mapping[str, str]] = {}
    for rows, stage in ((outer, "outer"), (inner, "inner")):
        for row in rows:
            if row["system_id"] != G0_SYSTEM_ID or row["endpoint"] != "CYP3A4":
                continue
            molecule, repeat, fold = (
                row["molecule_id"],
                canonical_int(row["repeat"], "OOF repeat"),
                canonical_int(row["outer_fold"], "OOF outer"),
            )
            if (
                molecule not in molecules
                or repeat not in REPEATS
                or fold not in OUTER_FOLDS
            ):
                raise OpenADMETOracleSourceError("OOF identity differs")
            if stage == "outer":
                if (
                    row["inner_fold"] != ""
                    or row["scope"] != "openadmet-direct-outer-v1"
                ):
                    raise OpenADMETOracleSourceError("outer OOF scope differs")
                key: tuple[str, int, int, int | None] = (molecule, repeat, fold, None)
            else:
                inner_fold = canonical_int(row["inner_fold"], "OOF inner")
                if (
                    inner_fold not in INNER_FOLDS
                    or row["scope"] != f"openadmet-direct-inner-v1|outer={fold}"
                ):
                    raise OpenADMETOracleSourceError("inner OOF scope differs")
                key = (molecule, repeat, fold, inner_fold)
            if key in output:
                raise OpenADMETOracleSourceError("duplicate G0 OOF row")
            finite(row["prediction"], "OOF prediction")
            if row["component_id"] != molecules[molecule]["similarity_component_hash"]:
                raise OpenADMETOracleSourceError("OOF component differs")
            output[key] = row
    return output


def _validate_features(
    loaded: Mapping[str, bytes],
    manifest: Mapping[str, Any],
    feature_rows: Sequence[Mapping[str, str]],
) -> dict[str, bytes]:
    if (
        manifest.get("schema_version")
        != "cypshift.openadmet_cyp_2026.r3a_feature_manifest.v1"
    ):
        raise OpenADMETOracleSourceError("R3A feature manifest schema differs")
    required = {"schema_version", "rows", "arrays", "accounting", "authority"}
    if not required <= set(manifest):
        raise OpenADMETOracleSourceError("R3A feature manifest fields differ")
    authority = mapping(manifest, "authority")
    if any(value is not False for value in authority.values()):
        raise OpenADMETOracleSourceError("R3A feature authority differs")
    row_receipt = mapping(manifest, "rows")
    if row_receipt.get("path") != "feature_rows.csv" or row_receipt.get(
        "columns"
    ) != list(FEATURE_ROW_COLUMNS):
        raise OpenADMETOracleSourceError("feature-row manifest differs")
    if row_receipt.get("sha256") != sha256(
        loaded["feature_rows.csv"]
    ).hexdigest() or row_receipt.get("rows") != len(feature_rows):
        raise OpenADMETOracleSourceError("feature-row receipt differs")
    ids = [row["molecule_id"] for row in feature_rows]
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        raise OpenADMETOracleSourceError("feature-row order differs")
    records = mapping(manifest, "arrays")
    arrays: dict[str, bytes] = {}
    expected = {
        "morgan_binary": (np.dtype("uint8"), 4096),
        "maplight_morgan_count": (np.dtype("int8"), 1024),
        "maplight_avalon_count": (np.dtype("int8"), 1024),
        "maplight_erg": (np.dtype("<f8"), 315),
        "maplight_rdkit_descriptors": (np.dtype("<f8"), 200),
    }
    if set(records) != set(expected):
        raise OpenADMETOracleSourceError("feature array set differs")
    for name in FEATURE_FILES:
        stem = Path(name).stem
        record = mapping(records, stem)
        data = loaded[name]
        if (
            record.get("path") != name
            or record.get("npy_sha256") != sha256(data).hexdigest()
        ):
            raise OpenADMETOracleSourceError(f"feature receipt differs: {name}")
        dtype, width = expected[stem]
        try:
            version = np.lib.format.read_magic(io.BytesIO(data))
            array = np.load(io.BytesIO(data), allow_pickle=False)
        except (ValueError, OSError) as exc:
            raise OpenADMETOracleSourceError(f"invalid NPY payload: {name}") from exc
        if (
            version != (1, 0)
            or array.shape != (len(feature_rows), width)
            or array.dtype != dtype
            or not array.flags.c_contiguous
        ):
            raise OpenADMETOracleSourceError(
                f"feature shape/dtype/order differs: {name}"
            )
        if stem != "maplight_rdkit_descriptors" and not bool(np.isfinite(array).all()):
            raise OpenADMETOracleSourceError(
                f"feature contains nonfinite values: {name}"
            )
        if stem == "maplight_rdkit_descriptors" and bool(np.isinf(array).any()):
            raise OpenADMETOracleSourceError(f"descriptor contains infinity: {name}")
        if stem == "maplight_rdkit_descriptors":
            allowed: np.ndarray[Any, Any] = np.zeros(width, dtype=bool)
            allowed[[39, 41, 43, 45]] = True
            if bool(np.isnan(array[:, ~allowed]).any()):
                raise OpenADMETOracleSourceError("descriptor NaN mask differs")
        arrays[name] = data
    return arrays


def _compile_outputs(
    parsed: Mapping[str, Any], loaded: Mapping[str, bytes], expected: Mapping[str, str]
) -> tuple[dict[str, bytes], dict[str, int]]:
    molecules = parsed["molecules"]
    folds = parsed["folds"]
    public = parsed["public"]
    direct = parsed["direct"]
    geometry = parsed["geometry"]
    oof = parsed["oof"]
    outputs: dict[str, bytes] = {
        "molecules.csv": canonical_csv_bytes(
            STRUCTURE_COLUMNS, list(molecules.values())
        ),
        "folds.csv": canonical_csv_bytes(FOLD_COLUMNS, _fold_rows(folds)),
        "public_episode_queries.csv": canonical_csv_bytes(
            PUBLIC_QUERY_COLUMNS,
            [
                {key: value for key, value in row.items() if not key.startswith("_")}
                for row in public
            ],
        ),
        "transformation_pairs.csv": loaded["transformation_pairs.csv"],
        "episode_transformations.csv": loaded["episode_transformations.csv"],
    }
    for name in FEATURE_FILES:
        outputs[name] = loaded[name]
    points, pairs = _training_rows(direct, molecules, folds, parsed["pairs"])
    anchor, global_context, truth, cliffs = _episode_rows(
        public,
        direct,
        folds,
        geometry,
        oof,
        expected["global_oof_predictions.csv"],
        expected["global_inner_oof_predictions.csv"],
    )
    outputs["training_points.csv"] = canonical_csv_bytes(
        SOURCE_COLUMNS["training_points.csv"], points
    )
    outputs["training_pairs.csv"] = canonical_csv_bytes(
        SOURCE_COLUMNS["training_pairs.csv"], pairs
    )
    outputs["episode_anchor_contexts.csv"] = canonical_csv_bytes(
        SOURCE_COLUMNS["episode_anchor_contexts.csv"], anchor
    )
    outputs["global_anchor_contexts.csv"] = canonical_csv_bytes(
        SOURCE_COLUMNS["global_anchor_contexts.csv"], global_context
    )
    outputs["episode_truth.csv"] = canonical_csv_bytes(
        SOURCE_COLUMNS["episode_truth.csv"], truth
    )
    outputs["activity_cliffs.csv"] = canonical_csv_bytes(
        SOURCE_COLUMNS["activity_cliffs.csv"], cliffs
    )
    if tuple(outputs) != SOURCE_FILES:
        raise OpenADMETOracleSourceError("source output file order differs")
    accounting = {key: 0 for key in SOURCE_ACCOUNTING}
    accounting["direct_target_values_parsed"] = parsed["direct_values"]
    accounting["anchor_labels_exposed_to_models"] = sum(
        row["anchor_point_available"] == "true" for row in anchor
    )
    return outputs, accounting


def _fold_rows(
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
) -> list[Mapping[str, str]]:
    return sorted(
        folds.values(),
        key=lambda row: (
            row["molecule_id"],
            int(row["repeat"]),
            int(row["outer_validation_fold"]),
        ),
    )


def _training_rows(
    direct: Mapping[str, Mapping[str, Mapping[str, str]]],
    molecules: Mapping[str, Mapping[str, str]],
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
    pair_rows: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    points: list[dict[str, str]] = []
    pairs: list[dict[str, str]] = []
    for scope in _scopes():
        train = {
            molecule for molecule in molecules if _in_training(molecule, scope, folds)
        }
        point_rows = [
            {
                "stage": scope.stage,
                "repeat": str(scope.repeat),
                "outer_fold": str(scope.outer),
                "inner_fold": "" if scope.inner is None else str(scope.inner),
                "molecule_id": molecule,
                "component_id": molecules[molecule]["similarity_component_hash"],
                "point": direct[molecule]["CYP3A4"]["point"],
                "sample_weight": "1.0",
            }
            for molecule in sorted(train)
            if _complete_point(direct[molecule]["CYP3A4"])
        ]
        points.extend(point_rows)
        eligible: dict[str, list[Mapping[str, str]]] = defaultdict(list)
        for pair in pair_rows:
            left, right = pair["left_molecule_id"], pair["right_molecule_id"]
            if (
                pair["local_pair"] == "true"
                and pair["extraction_status"] in VALID_EXTRACTIONS
                and left in train
                and right in train
                and _complete_point(direct[left]["CYP3A4"])
                and _complete_point(direct[right]["CYP3A4"])
            ):
                eligible[molecules[left]["similarity_component_hash"]].append(pair)
        for component, rows in sorted(eligible.items()):
            weight = f"1/{2 * len(rows)}"
            for pair in sorted(rows, key=lambda row: row["transformation_pair_id"]):
                left, right = pair["left_molecule_id"], pair["right_molecule_id"]
                left_point, right_point = (
                    float(direct[left]["CYP3A4"]["point"]),
                    float(direct[right]["CYP3A4"]["point"]),
                )
                pairs.extend(
                    _pair_output(
                        scope,
                        pair,
                        left,
                        right,
                        right_point - left_point,
                        weight,
                        component,
                    )
                )
    return points, pairs


def _scopes() -> tuple[_Scope, ...]:
    return tuple(
        [
            _Scope("outer", repeat, outer, None)
            for repeat in REPEATS
            for outer in OUTER_FOLDS
        ]
        + [
            _Scope("inner", repeat, outer, inner)
            for repeat in REPEATS
            for outer in OUTER_FOLDS
            for inner in INNER_FOLDS
        ]
    )


def _pair_output(
    scope: _Scope,
    pair: Mapping[str, str],
    left: str,
    right: str,
    delta: float,
    weight: str,
    component: str,
) -> list[dict[str, str]]:
    prefix = {
        "stage": scope.stage,
        "repeat": str(scope.repeat),
        "outer_fold": str(scope.outer),
        "inner_fold": "" if scope.inner is None else str(scope.inner),
    }
    return [
        {
            **prefix,
            "pair_id": pair["transformation_pair_id"],
            "direction_id": pair["a_to_b_direction_id"],
            "anchor_molecule_id": left,
            "analog_molecule_id": right,
            "component_id": component,
            "delta": format(delta, ".17g"),
            "sample_weight": weight,
        },
        {
            **prefix,
            "pair_id": pair["transformation_pair_id"],
            "direction_id": pair["b_to_a_direction_id"],
            "anchor_molecule_id": right,
            "analog_molecule_id": left,
            "component_id": component,
            "delta": format(-delta, ".17g"),
            "sample_weight": weight,
        },
    ]


def _episode_rows(
    public: Sequence[Mapping[str, str]],
    direct: Mapping[str, Mapping[str, Mapping[str, str]]],
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
    geometry: Mapping[tuple[str, int], Mapping[str, str]],
    oof: Mapping[tuple[str, int, int, int | None], Mapping[str, str]],
    outer_receipt: str,
    inner_receipt: str,
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    anchor_rows: list[dict[str, str]] = []
    global_rows: list[dict[str, str]] = []
    truth_rows: list[dict[str, str]] = []
    cliff_rows: list[dict[str, str]] = []
    for episode in public:
        policy = episode["episode_policy_id"]
        repeat, assigned_outer = int(episode["repeat"]), int(episode["outer_fold"])
        if policy == "deterministic_random_anchor_stress":
            scopes: tuple[_Scope, ...] = (
                _Scope("outer", repeat, assigned_outer, None),
            )
        else:
            scopes = tuple(
                scope
                for scope in _scopes()
                if _episode_in_scope(
                    episode["anchor_molecule_id"], repeat, assigned_outer, scope, folds
                )
            )
        for scope in scopes:
            key = (episode["anchor_molecule_id"], repeat, scope.outer, scope.inner)
            global_prediction = oof.get(key)
            if global_prediction is None:
                raise OpenADMETOracleSourceError("C3 G0 OOF join is missing")
            source = outer_receipt if scope.inner is None else inner_receipt
            base = {
                "stage": scope.stage,
                "repeat": str(scope.repeat),
                "outer_fold": str(scope.outer),
                "inner_fold": "" if scope.inner is None else str(scope.inner),
                "episode_id": episode["episode_id"],
                "anchor_molecule_id": episode["anchor_molecule_id"],
                "anchor_global_oof_prediction": global_prediction["prediction"],
                "anchor_global_oof_source_scope": global_prediction["scope"],
                "anchor_global_oof_model_id": global_prediction["model_id"],
                "anchor_global_oof_receipt_sha256": source,
            }
            global_rows.append(base)
            anchor = dict(base)
            point = direct[episode["anchor_molecule_id"]]["CYP3A4"]
            anchor["anchor_point_available"] = (
                "true" if _complete_point(point) else "false"
            )
            anchor["anchor_point"] = point["point"] if _complete_point(point) else ""
            anchor_rows.append(anchor)
            query = episode["query_molecule_id"]
            selector = str(episode.get("_selector_cyp_truth", "CYP3A4"))
            if selector not in ENDPOINTS:
                raise OpenADMETOracleSourceError("selector endpoint differs")
            query_point = direct[query][selector]
            available = _complete_point(query_point)
            truth_rows.append(
                {
                    "stage": scope.stage,
                    "repeat": str(scope.repeat),
                    "outer_fold": str(scope.outer),
                    "inner_fold": "" if scope.inner is None else str(scope.inner),
                    "episode_id": episode["episode_id"],
                    "query_molecule_id": query,
                    "selector_cyp_truth": selector,
                    "query_point": query_point["point"] if available else "",
                    "query_point_available": "true" if available else "false",
                }
            )
            anchor_point = direct[episode["anchor_molecule_id"]]["CYP3A4"]
            episode_geometry = geometry[
                (episode["episode_id"], int(episode["query_rank"]))
            ]
            pair_geometry = cast(Mapping[str, str], episode_geometry["_pair"])
            cliff = (
                float(pair_geometry["similarity"]) >= 0.60
                and _is_cliff(anchor_point, query_point)
                if _complete_point(anchor_point) and available
                else False
            )
            cliff_rows.append(
                {
                    "stage": scope.stage,
                    "repeat": str(scope.repeat),
                    "outer_fold": str(scope.outer),
                    "inner_fold": "" if scope.inner is None else str(scope.inner),
                    "episode_id": episode["episode_id"],
                    "query_molecule_id": query,
                    "activity_cliff": "true" if cliff else "false",
                }
            )
    return anchor_rows, global_rows, truth_rows, cliff_rows


def _episode_in_scope(
    anchor: str,
    repeat: int,
    episode_outer: int,
    scope: _Scope,
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
) -> bool:
    if scope.repeat != repeat:
        return False
    fold = folds[(anchor, repeat, scope.outer)]
    assigned = int(fold["outer_fold"])
    if scope.inner is None:
        return assigned == scope.outer == episode_outer
    return (
        assigned != scope.outer
        and episode_outer == assigned
        and fold["inner_fold"] == str(scope.inner)
    )


def _in_training(
    molecule: str,
    scope: _Scope,
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
) -> bool:
    row = folds[(molecule, scope.repeat, scope.outer)]
    if int(row["outer_fold"]) == scope.outer:
        return False
    return scope.inner is None or row["inner_fold"] != str(scope.inner)


def _is_cliff(left: Mapping[str, str], right: Mapping[str, str]) -> bool:
    try:
        lp, rp = float(left["point"]), float(right["point"])
        lh, rh = float(left["high"]), float(right["high"])
        ll, rl = float(left["low"]), float(right["low"])
    except (KeyError, ValueError) as exc:
        raise OpenADMETOracleSourceError("cliff fields are invalid") from exc
    return abs(lp - rp) >= 1.0 and (lh < rl or rh < ll)


def _complete_point(row: Mapping[str, str]) -> bool:
    if row.get("value_state") != "complete" or not row.get("point"):
        return False
    try:
        return math.isfinite(float(row["point"]))
    except ValueError:
        return False


def _numeric_values(rows: Sequence[Mapping[str, str]]) -> int:
    count = 0
    for row in rows:
        for field in ("point", "low", "high", "std"):
            if row[field]:
                finite(row[field], field)
                count += 1
    return count


def _build_manifest(
    contract_sha256: str,
    expected: Mapping[str, str],
    loaded: Mapping[str, bytes],
    outputs: Mapping[str, bytes],
    accounting: Mapping[str, int],
    counts: Mapping[str, int],
) -> dict[str, Any]:
    output_receipts: dict[str, dict[str, Any]] = {}
    for name, data in outputs.items():
        output_receipts[name] = {
            "sha256": sha256(data).hexdigest(),
            "bytes": len(data),
            "rows": data.count(b"\n") - 1 if name.endswith(".csv") else 0,
            "columns": list(SOURCE_COLUMNS.get(name, ())),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": contract_sha256,
        "parent_receipts": dict(sorted(expected.items())),
        "input_receipts": {
            name: {"sha256": expected[name], "bytes": len(loaded[name])}
            for name in INPUT_FILES
        },
        "source_receipts": {
            name: {"sha256": expected[name], "bytes": len(loaded[name])}
            for name in INPUT_FILES
        },
        "output_receipts": output_receipts,
        "columns": {name: list(columns) for name, columns in SOURCE_COLUMNS.items()},
        "counts": dict(counts),
        "operation_accounting": dict(accounting),
        "authority": dict(DENIED_AUTHORITY),
    }


__all__ = [
    "CONTRACT_SHA256",
    "G0_SYSTEM_ID",
    "INPUT_FILES",
    "OpenADMETOracleSourceError",
    "OracleSourceResult",
    "build_openadmet_oracle_source",
    "compile_openadmet_oracle_source",
]

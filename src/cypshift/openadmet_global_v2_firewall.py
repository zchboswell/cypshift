"""Synthetic-only capability firewall for the OpenADMET Global-v2 program."""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

from cypshift.openadmet_global_v2_metric import (
    ENDPOINTS,
    METRIC_ID,
    PredictionRow,
    TruthRow,
    tutorial_macro_st_rae,
)
from cypshift.openadmet_oracle_private_io import (
    publish_readonly_tree,
    read_exact_root,
    read_stable_file,
)
from cypshift.openadmet_transformation_io import (
    canonical_csv_bytes,
    canonical_json_bytes,
    strict_json_object,
)

CONTRACT_SHA256: Final = (
    "be583b5b25a9dacbdc28224e24d2bb5a4e13e036835f6fd712996999de4541c8"
)
PARENT_CONTRACT_SHA256: Final = (
    "612b8cea20cba8fb5d209fdd2d92a42feb652477c358f92ed710449d091e5c0d"
)
CONTRACT_PATH: Final = (
    Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "global_v2_synthetic_firewall_contract.json"
)
SOURCE_SCHEMA: Final = "cypshift.openadmet_cyp_2026.global_v2_synthetic_source.v1"
COMPILATION_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_synthetic_compilation.v1"
)
DEVELOPMENT_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_development_capability.v1"
)
PREDICTOR_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_confirmatory_predictor_capability.v1"
)
SCORER_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_confirmatory_scorer_capability.v1"
)
CANDIDATE_SCHEMA: Final = "cypshift.openadmet_cyp_2026.global_v2_synthetic_candidate.v1"
PREDICTION_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_synthetic_prediction.v1"
)
SCORE_SCHEMA: Final = "cypshift.openadmet_cyp_2026.global_v2_synthetic_score.v1"
IDENTITY_COLUMNS: Final = ("molecule_id", "similarity_component_hash")
TARGET_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "availability",
    "point",
    "low",
    "high",
)
TRUTH_COLUMNS: Final = ("molecule_id", "endpoint", "point", "low", "high")
PREDICTION_COLUMNS: Final = ("molecule_id", "endpoint", "prediction")
FORBIDDEN_ACCOUNTING_FIELDS: Final = (
    "official_target_values_opened",
    "official_features_generated",
    "official_model_fits",
    "official_predictions_generated",
    "official_metric_evaluations",
    "external_records_acquired",
    "blinded_test_files_opened",
    "blinded_test_relationships",
    "tdi_files_opened",
    "submissions_created",
    "leaderboard_observations",
)


class GlobalV2FirewallError(ValueError):
    """A synthetic receipt, capability, or publication invariant failed."""


@dataclass(frozen=True, slots=True)
class IdentityRow:
    molecule_id: str
    similarity_component_hash: str


@dataclass(frozen=True, slots=True)
class SyntheticTargetRow:
    molecule_id: str
    endpoint: str
    availability: str
    point: float | None
    low: float | None
    high: float | None


@dataclass(frozen=True, slots=True)
class CompilationResult:
    root: Path
    manifest_sha256: str
    development_manifest_sha256: str
    predictor_manifest_sha256: str
    scorer_manifest_sha256: str
    development_molecules: int
    confirmatory_molecules: int


@dataclass(frozen=True, slots=True)
class DevelopmentCapability:
    root: Path
    manifest_sha256: str
    compilation_id: str
    identities: tuple[IdentityRow, ...]
    targets: tuple[SyntheticTargetRow, ...]


@dataclass(frozen=True, slots=True)
class ConfirmatoryPredictorCapability:
    root: Path
    manifest_sha256: str
    compilation_id: str
    identities: tuple[IdentityRow, ...]


@dataclass(frozen=True, slots=True)
class ConfirmatoryScorerCapability:
    root: Path
    manifest_sha256: str
    compilation_id: str
    truth: tuple[TruthRow, ...]


@dataclass(frozen=True, slots=True)
class FrozenCandidateCapability:
    root: Path
    manifest_sha256: str
    compilation_id: str
    endpoint_means: tuple[tuple[str, float], ...]


@dataclass(frozen=True, slots=True)
class ConfirmatoryPredictionCapability:
    root: Path
    manifest_sha256: str
    compilation_id: str
    predictions: tuple[PredictionRow, ...]


@dataclass(frozen=True, slots=True)
class SyntheticScoreResult:
    root: Path
    manifest_sha256: str
    metric_value: float


def is_confirmatory_component(component_hash: str) -> bool:
    """Apply the frozen label-free component assignment exactly."""

    _digest(component_hash, "similarity component hash")
    material = (
        "openadmet-global-v2-confirmatory-v1|20260824|" + component_hash
    ).encode("utf-8")
    return int.from_bytes(sha256(material).digest()[:8], "big") % 5 == 0


def publish_synthetic_source(
    identities: Sequence[IdentityRow],
    targets: Sequence[SyntheticTargetRow],
    output_root: Path,
    *,
    fixture_id: str,
) -> str:
    """Publish one canonical source that is mechanically synthetic-only."""

    _verify_contract()
    if not fixture_id.startswith("synthetic-global-v2-"):
        raise GlobalV2FirewallError("synthetic fixture identifier differs")
    identity_rows = _validate_identities(identities)
    target_rows = _validate_targets(targets, identity_rows)
    identity_data = canonical_csv_bytes(
        IDENTITY_COLUMNS, [_identity_value(row) for row in identity_rows]
    )
    target_data = canonical_csv_bytes(
        TARGET_COLUMNS, [_target_value(row) for row in target_rows]
    )
    manifest = {
        "schema_version": SOURCE_SCHEMA,
        "status": "SYNTHETIC_SOURCE_FROZEN",
        "contract_sha256": CONTRACT_SHA256,
        "fixture_id": fixture_id,
        "synthetic_only": True,
        "receipts": {
            "identities.csv": _receipt(
                identity_data, IDENTITY_COLUMNS, len(identity_rows)
            ),
            "targets.csv": _receipt(target_data, TARGET_COLUMNS, len(target_rows)),
        },
        "counts": {
            "molecules": len(identity_rows),
            "components": len({row.similarity_component_hash for row in identity_rows}),
            "target_rows": len(target_rows),
            "complete_targets": sum(
                row.availability == "complete" for row in target_rows
            ),
            "missing_targets": sum(
                row.availability == "missing" for row in target_rows
            ),
        },
        "forbidden_accounting": _zero_accounting(),
    }
    manifest_data = canonical_json_bytes(manifest)
    publish_readonly_tree(
        output_root,
        {
            "identities.csv": identity_data,
            "targets.csv": target_data,
            "manifest.json": manifest_data,
        },
    )
    return sha256(manifest_data).hexdigest()


def compile_synthetic_capabilities(
    source_root: Path,
    output_root: Path,
    *,
    expected_source_manifest_sha256: str,
) -> CompilationResult:
    """Split a verified synthetic source into three disjoint immutable roots."""

    _verify_contract()
    _digest(expected_source_manifest_sha256, "synthetic source manifest")
    source = read_exact_root(
        source_root, ("identities.csv", "targets.csv", "manifest.json")
    )
    if sha256(source["manifest.json"]).hexdigest() != expected_source_manifest_sha256:
        raise GlobalV2FirewallError("synthetic source manifest receipt differs")
    manifest = strict_json_object(source["manifest.json"], "synthetic source manifest")
    if canonical_json_bytes(manifest) != source["manifest.json"]:
        raise GlobalV2FirewallError("synthetic source manifest is not canonical")
    _validate_source_manifest(manifest, source)
    identities = _parse_identities(source["identities.csv"])
    targets = _parse_targets(source["targets.csv"], identities)
    _validate_exact_receipt(
        manifest,
        "identities.csv",
        source["identities.csv"],
        IDENTITY_COLUMNS,
        len(identities),
    )
    _validate_exact_receipt(
        manifest,
        "targets.csv",
        source["targets.csv"],
        TARGET_COLUMNS,
        len(targets),
    )
    expected_source_counts = {
        "molecules": len(identities),
        "components": len({row.similarity_component_hash for row in identities}),
        "target_rows": len(targets),
        "complete_targets": sum(row.availability == "complete" for row in targets),
        "missing_targets": sum(row.availability == "missing" for row in targets),
    }
    if manifest.get("counts") != expected_source_counts:
        raise GlobalV2FirewallError("synthetic source counts differ")

    development = tuple(
        row
        for row in identities
        if not is_confirmatory_component(row.similarity_component_hash)
    )
    confirmatory = tuple(
        row
        for row in identities
        if is_confirmatory_component(row.similarity_component_hash)
    )
    if not development or not confirmatory:
        raise GlobalV2FirewallError(
            "synthetic fixture does not exercise both partitions"
        )
    development_ids = {row.molecule_id for row in development}
    confirmatory_ids = {row.molecule_id for row in confirmatory}
    if development_ids & confirmatory_ids or development_ids | confirmatory_ids != {
        row.molecule_id for row in identities
    }:
        raise GlobalV2FirewallError(
            "synthetic partition is not disjoint and exhaustive"
        )

    development_targets = tuple(
        row for row in targets if row.molecule_id in development_ids
    )
    confirmatory_truth = tuple(
        TruthRow(
            row.molecule_id,
            row.endpoint,
            cast(float, row.point),
            cast(float, row.low),
            cast(float, row.high),
        )
        for row in targets
        if row.molecule_id in confirmatory_ids and row.availability == "complete"
    )
    compilation_id = sha256(
        f"{CONTRACT_SHA256}|{expected_source_manifest_sha256}".encode()
    ).hexdigest()
    source_hashes = _implementation_hashes()

    development_identity_data = canonical_csv_bytes(
        IDENTITY_COLUMNS, [_identity_value(row) for row in development]
    )
    development_target_data = canonical_csv_bytes(
        TARGET_COLUMNS, [_target_value(row) for row in development_targets]
    )
    predictor_identity_data = canonical_csv_bytes(
        IDENTITY_COLUMNS, [_identity_value(row) for row in confirmatory]
    )
    truth_data = canonical_csv_bytes(
        TRUTH_COLUMNS, [_truth_value(row) for row in confirmatory_truth]
    )
    common = {
        "contract_sha256": CONTRACT_SHA256,
        "source_manifest_sha256": expected_source_manifest_sha256,
        "compilation_id": compilation_id,
        "implementation_sha256": source_hashes,
        "forbidden_accounting": _zero_accounting(),
    }
    development_manifest = {
        "schema_version": DEVELOPMENT_SCHEMA,
        "status": "SYNTHETIC_DEVELOPMENT_CAPABILITY_FROZEN",
        **common,
        "receipts": {
            "identities.csv": _receipt(
                development_identity_data, IDENTITY_COLUMNS, len(development)
            ),
            "targets.csv": _receipt(
                development_target_data, TARGET_COLUMNS, len(development_targets)
            ),
        },
    }
    predictor_manifest = {
        "schema_version": PREDICTOR_SCHEMA,
        "status": "SYNTHETIC_CONFIRMATORY_PREDICTOR_CAPABILITY_FROZEN",
        **common,
        "receipts": {
            "identities.csv": _receipt(
                predictor_identity_data, IDENTITY_COLUMNS, len(confirmatory)
            )
        },
    }
    scorer_manifest = {
        "schema_version": SCORER_SCHEMA,
        "status": "SYNTHETIC_CONFIRMATORY_SCORER_CAPABILITY_FROZEN",
        **common,
        "maximum_scores": 1,
        "receipts": {
            "truth.csv": _receipt(truth_data, TRUTH_COLUMNS, len(confirmatory_truth))
        },
    }
    development_manifest_data = canonical_json_bytes(development_manifest)
    predictor_manifest_data = canonical_json_bytes(predictor_manifest)
    scorer_manifest_data = canonical_json_bytes(scorer_manifest)
    root_manifest = {
        "schema_version": COMPILATION_SCHEMA,
        "status": "G2_1_SYNTHETIC_CAPABILITIES_COMPILED",
        **common,
        "partition": {
            "development_molecules": len(development),
            "development_components": len(
                {row.similarity_component_hash for row in development}
            ),
            "confirmatory_molecules": len(confirmatory),
            "confirmatory_components": len(
                {row.similarity_component_hash for row in confirmatory}
            ),
            "intersection_molecules": 0,
            "intersection_components": 0,
        },
        "capability_manifest_sha256": {
            "development": sha256(development_manifest_data).hexdigest(),
            "confirmatory_predictor": sha256(predictor_manifest_data).hexdigest(),
            "confirmatory_scorer": sha256(scorer_manifest_data).hexdigest(),
        },
    }
    root_manifest_data = canonical_json_bytes(root_manifest)
    publish_readonly_tree(
        output_root,
        {
            "development/identities.csv": development_identity_data,
            "development/targets.csv": development_target_data,
            "development/manifest.json": development_manifest_data,
            "confirmatory-predictor/identities.csv": predictor_identity_data,
            "confirmatory-predictor/manifest.json": predictor_manifest_data,
            "confirmatory-scorer/truth.csv": truth_data,
            "confirmatory-scorer/manifest.json": scorer_manifest_data,
            "manifest.json": root_manifest_data,
        },
    )
    return CompilationResult(
        output_root,
        sha256(root_manifest_data).hexdigest(),
        sha256(development_manifest_data).hexdigest(),
        sha256(predictor_manifest_data).hexdigest(),
        sha256(scorer_manifest_data).hexdigest(),
        len(development),
        len(confirmatory),
    )


def load_development_capability(
    root: Path, *, expected_manifest_sha256: str
) -> DevelopmentCapability:
    """Authenticate and load only the development capability root."""

    files, manifest = _load_capability_root(
        root,
        ("identities.csv", "targets.csv", "manifest.json"),
        expected_manifest_sha256,
        DEVELOPMENT_SCHEMA,
    )
    identities = _parse_identities(files["identities.csv"])
    targets = _parse_targets(files["targets.csv"], identities)
    _validate_exact_receipt(
        manifest,
        "identities.csv",
        files["identities.csv"],
        IDENTITY_COLUMNS,
        len(identities),
    )
    _validate_exact_receipt(
        manifest,
        "targets.csv",
        files["targets.csv"],
        TARGET_COLUMNS,
        len(targets),
    )
    return DevelopmentCapability(
        root,
        expected_manifest_sha256,
        _manifest_digest(manifest, "compilation_id"),
        identities,
        targets,
    )


def load_confirmatory_predictor_capability(
    root: Path, *, expected_manifest_sha256: str
) -> ConfirmatoryPredictorCapability:
    """Authenticate a label-free confirmatory predictor root."""

    files, manifest = _load_capability_root(
        root,
        ("identities.csv", "manifest.json"),
        expected_manifest_sha256,
        PREDICTOR_SCHEMA,
    )
    identities = _parse_identities(files["identities.csv"])
    _validate_exact_receipt(
        manifest,
        "identities.csv",
        files["identities.csv"],
        IDENTITY_COLUMNS,
        len(identities),
    )
    return ConfirmatoryPredictorCapability(
        root,
        expected_manifest_sha256,
        _manifest_digest(manifest, "compilation_id"),
        identities,
    )


def load_confirmatory_scorer_capability(
    root: Path, *, expected_manifest_sha256: str
) -> ConfirmatoryScorerCapability:
    """Authenticate a truth-only confirmatory scorer root."""

    files, manifest = _load_capability_root(
        root,
        ("truth.csv", "manifest.json"),
        expected_manifest_sha256,
        SCORER_SCHEMA,
    )
    if manifest.get("maximum_scores") != 1:
        raise GlobalV2FirewallError("confirmatory score ceiling differs")
    truth = _parse_truth(files["truth.csv"])
    _validate_exact_receipt(
        manifest, "truth.csv", files["truth.csv"], TRUTH_COLUMNS, len(truth)
    )
    return ConfirmatoryScorerCapability(
        root,
        expected_manifest_sha256,
        _manifest_digest(manifest, "compilation_id"),
        truth,
    )


def fit_synthetic_endpoint_means(
    development: DevelopmentCapability, output_root: Path
) -> str:
    """Fit the deterministic synthetic control using development targets only."""

    if not isinstance(development, DevelopmentCapability):
        raise GlobalV2FirewallError("candidate fitter requires development capability")
    means: dict[str, float] = {}
    for endpoint in ENDPOINTS:
        values = [
            cast(float, row.point)
            for row in development.targets
            if row.endpoint == endpoint and row.availability == "complete"
        ]
        if not values:
            raise GlobalV2FirewallError(
                f"synthetic development endpoint has no complete target: {endpoint}"
            )
        means[endpoint] = math.fsum(values) / len(values)
    candidate_data = canonical_json_bytes(
        {"model": "endpoint_arithmetic_mean", "endpoint_means": means}
    )
    manifest_data = canonical_json_bytes(
        {
            "schema_version": CANDIDATE_SCHEMA,
            "status": "SYNTHETIC_CANDIDATE_FROZEN",
            "contract_sha256": CONTRACT_SHA256,
            "compilation_id": development.compilation_id,
            "development_manifest_sha256": development.manifest_sha256,
            "candidate_sha256": sha256(candidate_data).hexdigest(),
            "synthetic_model_fits": len(ENDPOINTS),
            "forbidden_accounting": _zero_accounting(),
        }
    )
    publish_readonly_tree(
        output_root, {"candidate.json": candidate_data, "manifest.json": manifest_data}
    )
    return sha256(manifest_data).hexdigest()


def load_frozen_candidate(
    root: Path, *, expected_manifest_sha256: str
) -> FrozenCandidateCapability:
    """Authenticate one frozen deterministic synthetic candidate."""

    files, manifest = _load_capability_root(
        root,
        ("candidate.json", "manifest.json"),
        expected_manifest_sha256,
        CANDIDATE_SCHEMA,
    )
    if sha256(files["candidate.json"]).hexdigest() != manifest.get("candidate_sha256"):
        raise GlobalV2FirewallError("candidate receipt differs")
    candidate = strict_json_object(files["candidate.json"], "synthetic candidate")
    if canonical_json_bytes(candidate) != files["candidate.json"]:
        raise GlobalV2FirewallError("synthetic candidate is not canonical")
    raw_means = candidate.get("endpoint_means")
    if candidate.get("model") != "endpoint_arithmetic_mean" or not isinstance(
        raw_means, dict
    ):
        raise GlobalV2FirewallError("synthetic candidate fields differ")
    means = tuple(
        (endpoint, _finite(raw_means.get(endpoint), endpoint)) for endpoint in ENDPOINTS
    )
    if set(raw_means) != set(ENDPOINTS):
        raise GlobalV2FirewallError("synthetic candidate endpoint set differs")
    return FrozenCandidateCapability(
        root,
        expected_manifest_sha256,
        _manifest_digest(manifest, "compilation_id"),
        means,
    )


def predict_synthetic_confirmatory(
    candidate: FrozenCandidateCapability,
    predictor: ConfirmatoryPredictorCapability,
    output_root: Path,
) -> str:
    """Predict from a frozen candidate and label-free confirmatory identities."""

    if not isinstance(candidate, FrozenCandidateCapability) or not isinstance(
        predictor, ConfirmatoryPredictorCapability
    ):
        raise GlobalV2FirewallError(
            "confirmatory prediction requires candidate and predictor capabilities"
        )
    if candidate.compilation_id != predictor.compilation_id:
        raise GlobalV2FirewallError("candidate and predictor compilation differ")
    means = dict(candidate.endpoint_means)
    predictions = tuple(
        PredictionRow(identity.molecule_id, endpoint, means[endpoint])
        for identity in predictor.identities
        for endpoint in ENDPOINTS
    )
    prediction_data = canonical_csv_bytes(
        PREDICTION_COLUMNS, [_prediction_value(row) for row in predictions]
    )
    manifest_data = canonical_json_bytes(
        {
            "schema_version": PREDICTION_SCHEMA,
            "status": "SYNTHETIC_CONFIRMATORY_PREDICTION_FROZEN",
            "contract_sha256": CONTRACT_SHA256,
            "compilation_id": predictor.compilation_id,
            "candidate_manifest_sha256": candidate.manifest_sha256,
            "predictor_manifest_sha256": predictor.manifest_sha256,
            "prediction_receipt": _receipt(
                prediction_data, PREDICTION_COLUMNS, len(predictions)
            ),
            "synthetic_predictions_generated": len(predictions),
            "forbidden_accounting": _zero_accounting(),
        }
    )
    publish_readonly_tree(
        output_root,
        {"predictions.csv": prediction_data, "manifest.json": manifest_data},
    )
    return sha256(manifest_data).hexdigest()


def load_confirmatory_prediction(
    root: Path, *, expected_manifest_sha256: str
) -> ConfirmatoryPredictionCapability:
    """Authenticate one frozen synthetic confirmatory prediction."""

    files, manifest = _load_capability_root(
        root,
        ("predictions.csv", "manifest.json"),
        expected_manifest_sha256,
        PREDICTION_SCHEMA,
    )
    predictions = _parse_predictions(files["predictions.csv"])
    if manifest.get("prediction_receipt") != _receipt(
        files["predictions.csv"], PREDICTION_COLUMNS, len(predictions)
    ):
        raise GlobalV2FirewallError("prediction receipt differs")
    return ConfirmatoryPredictionCapability(
        root,
        expected_manifest_sha256,
        _manifest_digest(manifest, "compilation_id"),
        predictions,
    )


def score_synthetic_confirmatory(
    prediction: ConfirmatoryPredictionCapability,
    scorer: ConfirmatoryScorerCapability,
    output_root: Path,
) -> SyntheticScoreResult:
    """Open sealed synthetic truth once and publish aggregate-only metric evidence."""

    if not isinstance(prediction, ConfirmatoryPredictionCapability) or not isinstance(
        scorer, ConfirmatoryScorerCapability
    ):
        raise GlobalV2FirewallError(
            "confirmatory scorer requires prediction and sealed truth capabilities"
        )
    if prediction.compilation_id != scorer.compilation_id:
        raise GlobalV2FirewallError("prediction and truth compilation differ")
    score = tutorial_macro_st_rae(scorer.truth, prediction.predictions)
    endpoint_values = {
        item.endpoint: {
            "eligible_rows": item.eligible_rows,
            "numerator": item.numerator,
            "denominator": item.denominator,
            "value": item.value,
        }
        for item in score.endpoint_scores
    }
    score_data = canonical_json_bytes(
        {
            "metric_id": METRIC_ID,
            "metric_value": score.value,
            "endpoint_values": endpoint_values,
        }
    )
    manifest_data = canonical_json_bytes(
        {
            "schema_version": SCORE_SCHEMA,
            "status": "G2_1_SYNTHETIC_CONFIRMATORY_SCORED",
            "contract_sha256": CONTRACT_SHA256,
            "compilation_id": scorer.compilation_id,
            "prediction_manifest_sha256": prediction.manifest_sha256,
            "scorer_manifest_sha256": scorer.manifest_sha256,
            "score_sha256": sha256(score_data).hexdigest(),
            "synthetic_metric_evaluations": 1,
            "official_score": False,
            "forbidden_accounting": _zero_accounting(),
        }
    )
    publish_readonly_tree(
        output_root, {"score.json": score_data, "manifest.json": manifest_data}
    )
    return SyntheticScoreResult(
        output_root, sha256(manifest_data).hexdigest(), score.value
    )


def _verify_contract() -> None:
    contract_data = read_stable_file(CONTRACT_PATH)
    if sha256(contract_data).hexdigest() != CONTRACT_SHA256:
        raise GlobalV2FirewallError("synthetic firewall contract receipt differs")
    contract = strict_json_object(contract_data, "synthetic firewall contract")
    if contract.get("schema_version") != (
        "cypshift.openadmet_cyp_2026.global_v2_synthetic_firewall_contract.v1"
    ):
        raise GlobalV2FirewallError("synthetic firewall contract schema differs")
    parent = contract.get("parent")
    if not isinstance(parent, dict) or parent.get("sha256") != PARENT_CONTRACT_SHA256:
        raise GlobalV2FirewallError("Global-v2 parent contract receipt differs")
    parent_path = CONTRACT_PATH.parent / str(parent.get("path", ""))
    if sha256(read_stable_file(parent_path)).hexdigest() != PARENT_CONTRACT_SHA256:
        raise GlobalV2FirewallError("Global-v2 parent contract bytes differ")
    authority = contract.get("authority")
    if not isinstance(authority, dict):
        raise GlobalV2FirewallError("synthetic firewall authority differs")
    if any(
        authority.get(name) is not False
        for name in (
            "official_target_access",
            "official_feature_generation",
            "official_model_fitting",
            "official_prediction_generation",
            "official_metric_evaluation",
            "external_record_acquisition",
            "blinded_test_access",
            "transductive_relationships",
            "tdi_access",
            "submission_generation",
            "leaderboard_observation",
            "live_upload",
        )
    ):
        raise GlobalV2FirewallError("official authority is not closed")


def _validate_source_manifest(
    manifest: Mapping[str, Any], files: Mapping[str, bytes]
) -> None:
    if (
        manifest.get("schema_version") != SOURCE_SCHEMA
        or manifest.get("status") != "SYNTHETIC_SOURCE_FROZEN"
        or manifest.get("synthetic_only") is not True
        or manifest.get("contract_sha256") != CONTRACT_SHA256
        or not str(manifest.get("fixture_id", "")).startswith("synthetic-global-v2-")
    ):
        raise GlobalV2FirewallError("synthetic source identity differs")
    _validate_receipt_bytes(manifest, "identities.csv", files["identities.csv"])
    _validate_receipt_bytes(manifest, "targets.csv", files["targets.csv"])
    _validate_zero_accounting(manifest)


def _load_capability_root(
    root: Path,
    names: Sequence[str],
    expected_manifest_sha256: str,
    schema: str,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    _verify_contract()
    _digest(expected_manifest_sha256, "capability manifest")
    files = read_exact_root(root, names)
    if sha256(files["manifest.json"]).hexdigest() != expected_manifest_sha256:
        raise GlobalV2FirewallError("capability manifest receipt differs")
    manifest = strict_json_object(files["manifest.json"], "capability manifest")
    if canonical_json_bytes(manifest) != files["manifest.json"]:
        raise GlobalV2FirewallError("capability manifest is not canonical")
    if (
        manifest.get("schema_version") != schema
        or manifest.get("contract_sha256") != CONTRACT_SHA256
    ):
        raise GlobalV2FirewallError("capability manifest identity differs")
    _manifest_digest(manifest, "compilation_id")
    _validate_zero_accounting(manifest)
    return files, manifest


def _validate_identities(rows: Sequence[IdentityRow]) -> tuple[IdentityRow, ...]:
    result: dict[str, IdentityRow] = {}
    for row in rows:
        if not isinstance(row, IdentityRow):
            raise GlobalV2FirewallError("identity row type differs")
        if not row.molecule_id.startswith("synthetic-mol-"):
            raise GlobalV2FirewallError("non-synthetic molecule identifier rejected")
        _digest(row.similarity_component_hash, "similarity component hash")
        if row.molecule_id in result:
            raise GlobalV2FirewallError("molecule identity is duplicated")
        result[row.molecule_id] = row
    if not result:
        raise GlobalV2FirewallError("synthetic identity population is empty")
    return tuple(result[key] for key in sorted(result))


def _validate_targets(
    rows: Sequence[SyntheticTargetRow], identities: Sequence[IdentityRow]
) -> tuple[SyntheticTargetRow, ...]:
    identity_ids = {row.molecule_id for row in identities}
    result: dict[tuple[str, str], SyntheticTargetRow] = {}
    for row in rows:
        if not isinstance(row, SyntheticTargetRow):
            raise GlobalV2FirewallError("synthetic target row type differs")
        if row.molecule_id not in identity_ids or row.endpoint not in ENDPOINTS:
            raise GlobalV2FirewallError("synthetic target key differs")
        values = (row.point, row.low, row.high)
        if row.availability == "complete":
            if any(value is None or not math.isfinite(value) for value in values):
                raise GlobalV2FirewallError("complete synthetic target is not finite")
            point, low, high = cast(tuple[float, float, float], values)
            if low > point or point > high:
                raise GlobalV2FirewallError("synthetic target bounds differ")
        elif row.availability == "missing":
            if any(value is not None for value in values):
                raise GlobalV2FirewallError("missing synthetic target exposes a value")
        else:
            raise GlobalV2FirewallError("synthetic availability state differs")
        key = (row.molecule_id, row.endpoint)
        if key in result:
            raise GlobalV2FirewallError("synthetic target key is duplicated")
        result[key] = row
    expected = {
        (molecule, endpoint) for molecule in identity_ids for endpoint in ENDPOINTS
    }
    if set(result) != expected:
        raise GlobalV2FirewallError("synthetic target matrix is incomplete")
    return tuple(result[key] for key in sorted(result))


def _parse_identities(data: bytes) -> tuple[IdentityRow, ...]:
    rows = _csv_rows(data, IDENTITY_COLUMNS, "synthetic identities")
    return _validate_identities(
        tuple(
            IdentityRow(row["molecule_id"], row["similarity_component_hash"])
            for row in rows
        )
    )


def _parse_targets(
    data: bytes, identities: Sequence[IdentityRow]
) -> tuple[SyntheticTargetRow, ...]:
    rows = _csv_rows(data, TARGET_COLUMNS, "synthetic targets")
    return _validate_targets(
        tuple(
            SyntheticTargetRow(
                row["molecule_id"],
                row["endpoint"],
                row["availability"],
                _optional_float(row["point"], "point"),
                _optional_float(row["low"], "low"),
                _optional_float(row["high"], "high"),
            )
            for row in rows
        ),
        identities,
    )


def _parse_truth(data: bytes) -> tuple[TruthRow, ...]:
    rows = _csv_rows(data, TRUTH_COLUMNS, "synthetic truth")
    result = tuple(
        TruthRow(
            row["molecule_id"],
            row["endpoint"],
            _required_float(row["point"], "point"),
            _required_float(row["low"], "low"),
            _required_float(row["high"], "high"),
        )
        for row in rows
    )
    for row in result:
        if not row.molecule_id.startswith("synthetic-mol-"):
            raise GlobalV2FirewallError("non-synthetic truth identifier rejected")
        if row.endpoint not in ENDPOINTS or row.low > row.point or row.point > row.high:
            raise GlobalV2FirewallError("synthetic truth fields differ")
    if len({(row.molecule_id, row.endpoint) for row in result}) != len(result):
        raise GlobalV2FirewallError("synthetic truth key is duplicated")
    return result


def _parse_predictions(data: bytes) -> tuple[PredictionRow, ...]:
    rows = _csv_rows(data, PREDICTION_COLUMNS, "synthetic predictions")
    result = tuple(
        PredictionRow(
            row["molecule_id"],
            row["endpoint"],
            _required_float(row["prediction"], "prediction"),
        )
        for row in rows
    )
    if any(
        not row.molecule_id.startswith("synthetic-mol-")
        or row.endpoint not in ENDPOINTS
        for row in result
    ):
        raise GlobalV2FirewallError("synthetic prediction key differs")
    if len({(row.molecule_id, row.endpoint) for row in result}) != len(result):
        raise GlobalV2FirewallError("synthetic prediction key is duplicated")
    return result


def _csv_rows(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GlobalV2FirewallError(f"{label} is not UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames != list(columns):
        raise GlobalV2FirewallError(f"{label} columns differ")
    rows: list[dict[str, str]] = []
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise GlobalV2FirewallError(f"{label} row width differs")
        rows.append(cast(dict[str, str], row))
    if canonical_csv_bytes(columns, rows) != data:
        raise GlobalV2FirewallError(f"{label} is not canonical")
    return rows


def _identity_value(row: IdentityRow) -> dict[str, str]:
    return {
        "molecule_id": row.molecule_id,
        "similarity_component_hash": row.similarity_component_hash,
    }


def _target_value(row: SyntheticTargetRow) -> dict[str, str]:
    return {
        "molecule_id": row.molecule_id,
        "endpoint": row.endpoint,
        "availability": row.availability,
        "point": "" if row.point is None else repr(row.point),
        "low": "" if row.low is None else repr(row.low),
        "high": "" if row.high is None else repr(row.high),
    }


def _truth_value(row: TruthRow) -> dict[str, str]:
    return {
        "molecule_id": row.molecule_id,
        "endpoint": row.endpoint,
        "point": repr(row.point),
        "low": repr(row.low),
        "high": repr(row.high),
    }


def _prediction_value(row: PredictionRow) -> dict[str, str]:
    return {
        "molecule_id": row.molecule_id,
        "endpoint": row.endpoint,
        "prediction": repr(row.prediction),
    }


def _receipt(data: bytes, columns: Sequence[str], rows: int) -> dict[str, Any]:
    return {
        "sha256": sha256(data).hexdigest(),
        "size_bytes": len(data),
        "rows": rows,
        "columns": list(columns),
    }


def _validate_receipt_bytes(
    manifest: Mapping[str, Any], name: str, data: bytes
) -> None:
    receipts = manifest.get("receipts")
    if not isinstance(receipts, dict) or name not in receipts:
        raise GlobalV2FirewallError(f"capability receipt is missing: {name}")
    _validate_single_receipt(receipts[name], data, name)


def _validate_exact_receipt(
    manifest: Mapping[str, Any],
    name: str,
    data: bytes,
    columns: Sequence[str],
    rows: int,
) -> None:
    receipts = manifest.get("receipts")
    if not isinstance(receipts, dict) or receipts.get(name) != _receipt(
        data, columns, rows
    ):
        raise GlobalV2FirewallError(f"{name} receipt differs")


def _validate_single_receipt(value: Any, data: bytes, label: str) -> None:
    if not isinstance(value, dict) or value.get("sha256") != sha256(data).hexdigest():
        raise GlobalV2FirewallError(f"{label} receipt differs")
    if value.get("size_bytes") != len(data):
        raise GlobalV2FirewallError(f"{label} size receipt differs")


def _manifest_digest(manifest: Mapping[str, Any], name: str) -> str:
    value = manifest.get(name)
    if not isinstance(value, str):
        raise GlobalV2FirewallError(f"manifest digest differs: {name}")
    _digest(value, name)
    return value


def _digest(value: str, label: str) -> None:
    if len(value) != 64:
        raise GlobalV2FirewallError(f"{label} is not SHA-256")
    try:
        bytes.fromhex(value)
    except ValueError as exc:
        raise GlobalV2FirewallError(f"{label} is not SHA-256") from exc


def _optional_float(value: str, label: str) -> float | None:
    return None if value == "" else _required_float(value, label)


def _required_float(value: str, label: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise GlobalV2FirewallError(f"{label} is not numeric") from exc
    if not math.isfinite(result):
        raise GlobalV2FirewallError(f"{label} is not finite")
    return result


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GlobalV2FirewallError(f"{label} is not finite")
    result = float(value)
    if not math.isfinite(result):
        raise GlobalV2FirewallError(f"{label} is not finite")
    return result


def _zero_accounting() -> dict[str, int]:
    return dict.fromkeys(FORBIDDEN_ACCOUNTING_FIELDS, 0)


def _validate_zero_accounting(manifest: Mapping[str, Any]) -> None:
    if manifest.get("forbidden_accounting") != _zero_accounting():
        raise GlobalV2FirewallError("forbidden-operation accounting differs")


def _implementation_hashes() -> dict[str, str]:
    metric_path = Path(__file__).with_name("openadmet_global_v2_metric.py")
    return {
        "firewall": sha256(read_stable_file(Path(__file__))).hexdigest(),
        "metric": sha256(read_stable_file(metric_path)).hexdigest(),
    }


__all__ = [
    "CONTRACT_SHA256",
    "ConfirmatoryPredictionCapability",
    "ConfirmatoryPredictorCapability",
    "ConfirmatoryScorerCapability",
    "DevelopmentCapability",
    "FrozenCandidateCapability",
    "GlobalV2FirewallError",
    "IdentityRow",
    "SyntheticScoreResult",
    "SyntheticTargetRow",
    "compile_synthetic_capabilities",
    "fit_synthetic_endpoint_means",
    "is_confirmatory_component",
    "load_confirmatory_prediction",
    "load_confirmatory_predictor_capability",
    "load_confirmatory_scorer_capability",
    "load_development_capability",
    "load_frozen_candidate",
    "predict_synthetic_confirmatory",
    "publish_synthetic_source",
    "score_synthetic_confirmatory",
]

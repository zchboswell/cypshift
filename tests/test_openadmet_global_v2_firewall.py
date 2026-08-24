from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

from cypshift.openadmet_global_v2_firewall import (
    CONTRACT_SHA256,
    GlobalV2FirewallError,
    IdentityRow,
    SyntheticTargetRow,
    compile_synthetic_capabilities,
    fit_synthetic_endpoint_means,
    is_confirmatory_component,
    load_confirmatory_prediction,
    load_confirmatory_predictor_capability,
    load_confirmatory_scorer_capability,
    load_development_capability,
    load_frozen_candidate,
    predict_synthetic_confirmatory,
    publish_synthetic_source,
    score_synthetic_confirmatory,
)
from cypshift.openadmet_global_v2_metric import ENDPOINTS
from cypshift.openadmet_oracle_private_io import OraclePrivateIOError

ROOT = Path(__file__).parents[1]
CONTRACT_PATH = (
    ROOT
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "global_v2_synthetic_firewall_contract.json"
)
ACCEPTANCE_PATH = (
    ROOT
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "global_v2_synthetic_firewall_acceptance.json"
)


def _fixture() -> tuple[list[IdentityRow], list[SyntheticTargetRow]]:
    identities: list[IdentityRow] = []
    targets: list[SyntheticTargetRow] = []
    for index in range(36):
        molecule = f"synthetic-mol-{index:03}"
        component = hashlib.sha256(f"component-{index}".encode()).hexdigest()
        identities.append(IdentityRow(molecule, component))
        for endpoint_index, endpoint in enumerate(ENDPOINTS):
            point = 2.0 + index / 5.0 + endpoint_index / 10.0
            missing = index % 13 == 0 and endpoint == "CYP2D6"
            targets.append(
                SyntheticTargetRow(
                    molecule,
                    endpoint,
                    "missing" if missing else "complete",
                    None if missing else point,
                    None if missing else point - 0.25,
                    None if missing else point + 0.25,
                )
            )
    assert (
        sum(
            is_confirmatory_component(row.similarity_component_hash)
            for row in identities
        )
        >= 3
    )
    assert (
        sum(
            not is_confirmatory_component(row.similarity_component_hash)
            for row in identities
        )
        >= 3
    )
    return identities, targets


def _file_map(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _source(
    root: Path,
    *,
    fixture_id: str = "synthetic-global-v2-firewall-v1",
    reverse: bool = False,
) -> str:
    identities, targets = _fixture()
    if reverse:
        identities.reverse()
        targets.reverse()
    return publish_synthetic_source(identities, targets, root, fixture_id=fixture_id)


def _compile(source: Path, output: Path, receipt: str) -> Any:
    return compile_synthetic_capabilities(
        source, output, expected_source_manifest_sha256=receipt
    )


def test_child_contract_is_exact_synthetic_only_and_parent_bound() -> None:
    data = CONTRACT_PATH.read_bytes()
    assert hashlib.sha256(data).hexdigest() == CONTRACT_SHA256
    contract = json.loads(data)
    assert contract["parent"]["sha256"] == (
        "612b8cea20cba8fb5d209fdd2d92a42feb652477c358f92ed710449d091e5c0d"
    )
    parent_path = CONTRACT_PATH.parent / contract["parent"]["path"]
    assert (
        hashlib.sha256(parent_path.read_bytes()).hexdigest()
        == contract["parent"]["sha256"]
    )
    assert contract["status"] == "synthetic_only_no_official_execution_authority"
    assert contract["acceptance"]["synthetic_roots_required"] == 2
    assert contract["metric"]["parity_fixtures"]["macro_value"] == 0.6875
    authority = contract["authority"]
    assert all(
        authority[name] is False
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
    )


def test_acceptance_receipt_binds_sources_replay_and_zero_official_operations() -> None:
    acceptance = json.loads(ACCEPTANCE_PATH.read_text())
    assert acceptance["gate"] == "G2_1_SYNTHETIC_FIREWALL_ACCEPTED"
    assert acceptance["implementation_contract"]["sha256"] == CONTRACT_SHA256
    for relative, expected in acceptance["implementation_sources"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    for relative, expected in acceptance["test_sources"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    replay = acceptance["two_fresh_replays"]
    assert replay["roots"] == 2
    assert replay["relative_file_maps_byte_identical"] is True
    assert acceptance["metric_parity"]["pinned_tutorial_fixtures_pass"] is True
    assert acceptance["adversarial_evidence"]["focused_tests_failed"] == 0
    assert set(acceptance["forbidden_accounting"].values()) == {0}


def test_two_fresh_roots_and_permuted_inputs_replay_byte_identically(
    tmp_path: Path,
) -> None:
    first_source = tmp_path / "source-a"
    second_source = tmp_path / "source-b"
    first_receipt = _source(first_source)
    second_receipt = _source(second_source, reverse=True)
    assert first_receipt == second_receipt
    assert _file_map(first_source) == _file_map(second_source)

    first = _compile(first_source, tmp_path / "compiled-a", first_receipt)
    second = _compile(second_source, tmp_path / "compiled-b", second_receipt)
    assert first.manifest_sha256 == second.manifest_sha256
    assert _file_map(first.root) == _file_map(second.root)
    assert set(_file_map(first.root)) == {
        "confirmatory-predictor/identities.csv",
        "confirmatory-predictor/manifest.json",
        "confirmatory-scorer/manifest.json",
        "confirmatory-scorer/truth.csv",
        "development/identities.csv",
        "development/manifest.json",
        "development/targets.csv",
        "manifest.json",
    }


def test_partition_is_label_free_disjoint_and_capabilities_are_minimal(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    receipt = _source(source)
    result = _compile(source, tmp_path / "compiled", receipt)
    development = load_development_capability(
        result.root / "development",
        expected_manifest_sha256=result.development_manifest_sha256,
    )
    predictor = load_confirmatory_predictor_capability(
        result.root / "confirmatory-predictor",
        expected_manifest_sha256=result.predictor_manifest_sha256,
    )
    scorer = load_confirmatory_scorer_capability(
        result.root / "confirmatory-scorer",
        expected_manifest_sha256=result.scorer_manifest_sha256,
    )
    development_ids = {row.molecule_id for row in development.identities}
    confirmatory_ids = {row.molecule_id for row in predictor.identities}
    assert development_ids.isdisjoint(confirmatory_ids)
    assert len(development_ids) == result.development_molecules
    assert len(confirmatory_ids) == result.confirmatory_molecules
    assert all(
        not is_confirmatory_component(row.similarity_component_hash)
        for row in development.identities
    )
    assert all(
        is_confirmatory_component(row.similarity_component_hash)
        for row in predictor.identities
    )
    assert {row.molecule_id for row in development.targets} == development_ids
    assert {row.molecule_id for row in scorer.truth} <= confirmatory_ids

    predictor_files = _file_map(result.root / "confirmatory-predictor")
    assert set(predictor_files) == {"identities.csv", "manifest.json"}
    assert predictor_files["identities.csv"].splitlines()[0] == (
        b"molecule_id,similarity_component_hash"
    )
    predictor_manifest = json.loads(predictor_files["manifest.json"])
    assert set(predictor_manifest["receipts"]) == {"identities.csv"}
    assert set(predictor_manifest["forbidden_accounting"].values()) == {0}


def test_target_values_and_availability_cannot_change_partition_membership(
    tmp_path: Path,
) -> None:
    identities, targets = _fixture()
    source_a = tmp_path / "source-a"
    receipt_a = publish_synthetic_source(
        identities,
        targets,
        source_a,
        fixture_id="synthetic-global-v2-target-independence-a",
    )
    changed = [
        SyntheticTargetRow(
            row.molecule_id,
            row.endpoint,
            "complete",
            101.0 + index,
            100.0 + index,
            102.0 + index,
        )
        for index, row in enumerate(targets)
    ]
    source_b = tmp_path / "source-b"
    receipt_b = publish_synthetic_source(
        identities,
        changed,
        source_b,
        fixture_id="synthetic-global-v2-target-independence-b",
    )
    first = _compile(source_a, tmp_path / "compiled-a", receipt_a)
    second = _compile(source_b, tmp_path / "compiled-b", receipt_b)
    assert (first.root / "confirmatory-predictor" / "identities.csv").read_bytes() == (
        second.root / "confirmatory-predictor" / "identities.csv"
    ).read_bytes()
    assert (first.root / "development" / "identities.csv").read_bytes() == (
        second.root / "development" / "identities.csv"
    ).read_bytes()


def test_synthetic_stage_interfaces_freeze_predict_and_score_once(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    receipt = _source(source)
    compiled = _compile(source, tmp_path / "compiled", receipt)
    development = load_development_capability(
        compiled.root / "development",
        expected_manifest_sha256=compiled.development_manifest_sha256,
    )
    predictor = load_confirmatory_predictor_capability(
        compiled.root / "confirmatory-predictor",
        expected_manifest_sha256=compiled.predictor_manifest_sha256,
    )
    scorer = load_confirmatory_scorer_capability(
        compiled.root / "confirmatory-scorer",
        expected_manifest_sha256=compiled.scorer_manifest_sha256,
    )
    candidate_manifest = fit_synthetic_endpoint_means(
        development, tmp_path / "candidate"
    )
    candidate = load_frozen_candidate(
        tmp_path / "candidate", expected_manifest_sha256=candidate_manifest
    )
    prediction_manifest = predict_synthetic_confirmatory(
        candidate, predictor, tmp_path / "prediction"
    )
    prediction = load_confirmatory_prediction(
        tmp_path / "prediction", expected_manifest_sha256=prediction_manifest
    )
    result = score_synthetic_confirmatory(prediction, scorer, tmp_path / "score")
    assert result.metric_value >= 0.0
    score = json.loads((result.root / "score.json").read_text())
    assert score["metric_id"] == "TUTORIAL_MA_ST_RAE_858AE63_V1"
    assert set(score["endpoint_values"]) == set(ENDPOINTS)
    assert not any("molecule" in key for key in score)
    manifest = json.loads((result.root / "manifest.json").read_text())
    assert manifest["official_score"] is False
    assert set(manifest["forbidden_accounting"].values()) == {0}
    with pytest.raises(OraclePrivateIOError, match="already exists"):
        score_synthetic_confirmatory(prediction, scorer, tmp_path / "score")


def test_stage_outputs_replay_byte_identically(tmp_path: Path) -> None:
    outputs: list[dict[str, dict[str, bytes]]] = []
    for suffix in ("a", "b"):
        parent = tmp_path / suffix
        parent.mkdir()
        source = parent / "source"
        receipt = _source(source)
        compiled = _compile(source, parent / "compiled", receipt)
        development = load_development_capability(
            compiled.root / "development",
            expected_manifest_sha256=compiled.development_manifest_sha256,
        )
        predictor = load_confirmatory_predictor_capability(
            compiled.root / "confirmatory-predictor",
            expected_manifest_sha256=compiled.predictor_manifest_sha256,
        )
        scorer = load_confirmatory_scorer_capability(
            compiled.root / "confirmatory-scorer",
            expected_manifest_sha256=compiled.scorer_manifest_sha256,
        )
        candidate_sha = fit_synthetic_endpoint_means(development, parent / "candidate")
        candidate = load_frozen_candidate(
            parent / "candidate", expected_manifest_sha256=candidate_sha
        )
        prediction_sha = predict_synthetic_confirmatory(
            candidate, predictor, parent / "prediction"
        )
        prediction = load_confirmatory_prediction(
            parent / "prediction", expected_manifest_sha256=prediction_sha
        )
        score_synthetic_confirmatory(prediction, scorer, parent / "score")
        outputs.append(
            {
                name: _file_map(parent / name)
                for name in ("source", "compiled", "candidate", "prediction", "score")
            }
        )
    assert outputs[0] == outputs[1]


def test_capability_types_and_cross_compilation_bindings_fail_closed(
    tmp_path: Path,
) -> None:
    source_a = tmp_path / "source-a"
    receipt_a = _source(source_a, fixture_id="synthetic-global-v2-binding-a")
    first = _compile(source_a, tmp_path / "compiled-a", receipt_a)
    development = load_development_capability(
        first.root / "development",
        expected_manifest_sha256=first.development_manifest_sha256,
    )
    scorer = load_confirmatory_scorer_capability(
        first.root / "confirmatory-scorer",
        expected_manifest_sha256=first.scorer_manifest_sha256,
    )
    candidate_sha = fit_synthetic_endpoint_means(development, tmp_path / "candidate")
    candidate = load_frozen_candidate(
        tmp_path / "candidate", expected_manifest_sha256=candidate_sha
    )

    with pytest.raises(GlobalV2FirewallError, match="requires development"):
        fit_synthetic_endpoint_means(cast(Any, scorer), tmp_path / "bad-candidate")

    source_b = tmp_path / "source-b"
    receipt_b = _source(source_b, fixture_id="synthetic-global-v2-binding-b")
    second = _compile(source_b, tmp_path / "compiled-b", receipt_b)
    predictor_b = load_confirmatory_predictor_capability(
        second.root / "confirmatory-predictor",
        expected_manifest_sha256=second.predictor_manifest_sha256,
    )
    with pytest.raises(GlobalV2FirewallError, match="compilation differ"):
        predict_synthetic_confirmatory(
            candidate, predictor_b, tmp_path / "bad-prediction"
        )

    development_b = load_development_capability(
        second.root / "development",
        expected_manifest_sha256=second.development_manifest_sha256,
    )
    candidate_b_sha = fit_synthetic_endpoint_means(
        development_b, tmp_path / "candidate-b"
    )
    candidate_b = load_frozen_candidate(
        tmp_path / "candidate-b", expected_manifest_sha256=candidate_b_sha
    )
    prediction_b_sha = predict_synthetic_confirmatory(
        candidate_b, predictor_b, tmp_path / "prediction-b"
    )
    prediction_b = load_confirmatory_prediction(
        tmp_path / "prediction-b", expected_manifest_sha256=prediction_b_sha
    )
    with pytest.raises(GlobalV2FirewallError, match="prediction and truth"):
        score_synthetic_confirmatory(prediction_b, scorer, tmp_path / "mixed-score")

    with pytest.raises(GlobalV2FirewallError, match="requires prediction"):
        score_synthetic_confirmatory(
            cast(Any, candidate), scorer, tmp_path / "bad-score"
        )


def test_wrong_receipt_non_synthetic_rows_symlink_traversal_and_overwrite_reject(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    receipt = _source(source)
    with pytest.raises(GlobalV2FirewallError, match="manifest receipt differs"):
        _compile(source, tmp_path / "wrong-receipt", "0" * 64)
    with pytest.raises(GlobalV2FirewallError, match="non-synthetic"):
        publish_synthetic_source(
            [IdentityRow("official-mol-1", "1" * 64)],
            [],
            tmp_path / "official",
            fixture_id="synthetic-global-v2-invalid",
        )
    link = tmp_path / "source-link"
    link.symlink_to(source, target_is_directory=True)
    with pytest.raises(OraclePrivateIOError, match="ancestry"):
        _compile(link, tmp_path / "symlink-output", receipt)
    with pytest.raises(OraclePrivateIOError, match="traversal"):
        _compile(source, tmp_path / "nested" / ".." / "bad", receipt)
    _compile(source, tmp_path / "compiled", receipt)
    with pytest.raises(OraclePrivateIOError, match="already exists"):
        _compile(source, tmp_path / "compiled", receipt)


def test_invalid_hash_nonfinite_missing_value_and_bounds_reject(tmp_path: Path) -> None:
    identities, targets = _fixture()
    with pytest.raises(GlobalV2FirewallError, match="not SHA-256"):
        publish_synthetic_source(
            [IdentityRow("synthetic-mol-bad", "not-a-hash")],
            [],
            tmp_path / "bad-hash",
            fixture_id="synthetic-global-v2-bad-hash",
        )
    cases = [
        SyntheticTargetRow(
            targets[0].molecule_id,
            targets[0].endpoint,
            "complete",
            float("nan"),
            1.0,
            2.0,
        ),
        SyntheticTargetRow(
            targets[0].molecule_id,
            targets[0].endpoint,
            "missing",
            1.0,
            None,
            None,
        ),
        SyntheticTargetRow(
            targets[0].molecule_id,
            targets[0].endpoint,
            "complete",
            2.0,
            3.0,
            4.0,
        ),
    ]
    messages = ("not finite", "exposes a value", "bounds differ")
    for index, (replacement, message) in enumerate(zip(cases, messages, strict=True)):
        changed = [replacement, *targets[1:]]
        with pytest.raises(GlobalV2FirewallError, match=message):
            publish_synthetic_source(
                identities,
                changed,
                tmp_path / f"invalid-{index}",
                fixture_id=f"synthetic-global-v2-invalid-{index}",
            )


def test_duplicate_identity_and_target_keys_reject(tmp_path: Path) -> None:
    identities, targets = _fixture()
    with pytest.raises(GlobalV2FirewallError, match="identity is duplicated"):
        publish_synthetic_source(
            [*identities, identities[0]],
            targets,
            tmp_path / "duplicate-identity",
            fixture_id="synthetic-global-v2-duplicate-identity",
        )
    with pytest.raises(GlobalV2FirewallError, match="target key is duplicated"):
        publish_synthetic_source(
            identities,
            [*targets, targets[0]],
            tmp_path / "duplicate-target",
            fixture_id="synthetic-global-v2-duplicate-target",
        )

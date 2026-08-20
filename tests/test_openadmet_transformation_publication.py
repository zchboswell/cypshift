from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import replace
from pathlib import Path

import pytest

import cypshift.openadmet_transformation_publication as publication
from cypshift.chemistry import standardize_molecule
from cypshift.openadmet_transformation_compiler import (
    CompiledEpisodeDirection,
    CompiledTransformationPair,
    TransformationGeometry,
)
from cypshift.openadmet_transformation_coverage import (
    DirectAvailability,
    OpenADMETTransformationCoverageError,
    ProjectionBundle,
    ProjectionEpisode,
    ProjectionFileReceipt,
    ProjectionFold,
    ProjectionMolecule,
    ProjectionSourceReceipt,
)
from cypshift.openadmet_transformation_io import (
    DIRECT_PROJECTION_COLUMNS,
    ENDPOINTS,
    MASK_PROJECTION_COLUMNS,
    PUBLIC_EPISODE_COLUMNS,
    STRUCTURE_COLUMNS,
)
from cypshift.openadmet_transformation_projection import FOLD_PROJECTION_COLUMNS
from cypshift.openadmet_transformation_publication import (
    SUCCESS_FILES,
    publish_transformation_coverage,
    publish_transformation_failure,
)
from cypshift.openadmet_transformation_support import (
    TransformationSupport,
    compile_transformation_support,
)
from cypshift.openadmet_transformations import extract_transformation_pair
from cypshift.schema import MoleculeInput, MoleculeRecord


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _runtime() -> dict[str, object]:
    return {
        "python_version": "3.12.3",
        "rdkit_version": "2026.03.5",
        "platform": "Linux x86_64 CPU",
        "device": "CPU",
        "seed": 0,
        "code_commit": "a" * 40,
    }


def _record(molecule_id: str, smiles: str) -> MoleculeRecord:
    return standardize_molecule(
        MoleculeInput(molecule_id, smiles, "smiles", "synthetic", "fixture")
    )


def _pair(
    component: str,
    left_id: str,
    left_smiles: str,
    right_id: str,
    right_smiles: str,
) -> tuple[CompiledTransformationPair, tuple[MoleculeRecord, MoleculeRecord]]:
    left = _record(left_id, left_smiles)
    right = _record(right_id, right_smiles)
    return (
        CompiledTransformationPair(
            extract_transformation_pair(left, right), component, True, True
        ),
        (left, right),
    )


def _receipts() -> tuple[
    tuple[ProjectionFileReceipt, ...], tuple[ProjectionSourceReceipt, ...]
]:
    columns = {
        "direct_projection.csv": DIRECT_PROJECTION_COLUMNS,
        "fold_projection.csv": FOLD_PROJECTION_COLUMNS,
        "mask_projection.csv": MASK_PROJECTION_COLUMNS,
        "public_projection.csv": PUBLIC_EPISODE_COLUMNS,
        "structure_projection.csv": STRUCTURE_COLUMNS,
    }
    inputs = tuple(
        ProjectionFileReceipt(
            name, hashlib.sha256(name.encode()).hexdigest(), 1, 0, value
        )
        for name, value in sorted(columns.items())
    ) + (ProjectionFileReceipt("manifest.json", "f" * 64, 1, None, ()),)
    sources = tuple(
        ProjectionSourceReceipt(name, hashlib.sha256(name.encode()).hexdigest(), 1, 0)
        for name in sorted(
            {
                "direct_observations.csv",
                "group_folds.csv",
                "masks.csv",
                "public_episodes.csv",
                "structure.csv",
            }
        )
    )
    return inputs, sources


def _science() -> tuple[
    ProjectionBundle, TransformationGeometry, TransformationSupport
]:
    valid, valid_records = _pair(_digest("family-valid"), "left", "CCO", "right", "CCN")
    invalid, invalid_records = _pair(
        _digest("family-invalid"), "bad-left", "CCO", "bad-right", "c1ccccc1"
    )
    records = [
        *((record, valid.similarity_component_hash, 0) for record in valid_records),
        *((record, invalid.similarity_component_hash, 1) for record in invalid_records),
    ]
    molecules = tuple(
        ProjectionMolecule(record, _digest(record.raw_structure), component)
        for record, component, _ in records
    )
    direct = tuple(
        DirectAvailability(
            _digest(f"obs:{record.molecule_id}:{endpoint}"),
            record.molecule_id,
            endpoint,
            "complete",
        )
        for record, _, _ in records
        for endpoint in ENDPOINTS
    )
    folds = tuple(
        ProjectionFold(
            record.molecule_id,
            component,
            repeat,
            20260810 + repeat,
            outer,
            validation,
            None if validation == outer else 0,
        )
        for record, component, outer in records
        for repeat in range(3)
        for validation in range(5)
    )

    def episode(
        pair: CompiledTransformationPair, name: str, policy: str
    ) -> tuple[ProjectionEpisode, CompiledEpisodeDirection]:
        direction = pair.result.a_to_b
        row = ProjectionEpisode(
            _digest(name),
            "ANCHOR_EXPANSION_HOLDOUT",
            0,
            0,
            pair.similarity_component_hash,
            direction.analog_molecule_id,
            1,
            direction.anchor_molecule_id,
            "DEFERRED_NO_INFERRED_POOL_V1",
            policy,
        )
        return row, CompiledEpisodeDirection(row, pair, direction)

    selected, selected_geometry = episode(valid, "selected", "selected_anchor")
    stress, stress_geometry = episode(
        invalid, "stress", "deterministic_random_anchor_stress"
    )
    inputs, sources = _receipts()
    bundle = ProjectionBundle(
        inputs, sources, molecules, direct, folds, (selected, stress)
    )
    geometry = TransformationGeometry(
        (invalid, valid), (stress_geometry, selected_geometry), b"untrusted-cache"
    )
    return bundle, geometry, compile_transformation_support(bundle, geometry)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _publish(tmp_path: Path, name: str = "terminal"):
    bundle, geometry, support = _science()
    return publish_transformation_coverage(
        destination=tmp_path / name,
        bundle=bundle,
        geometry=geometry,
        support=support,
        runtime=_runtime(),
        expected_episode_rows=2,
    )


def test_success_terminal_is_exact_read_only_and_receipt_bound(tmp_path: Path) -> None:
    result = _publish(tmp_path)
    destination = result.output_directory
    assert result.status == "R4_TRANSFORMATION_COVERAGE_UNDERPOWERED"
    assert {path.name for path in destination.iterdir()} == set(SUCCESS_FILES)
    assert _mode(destination) == 0o555
    assert all(_mode(path) == 0o444 for path in destination.iterdir())
    manifest_data = result.manifest_path.read_bytes()
    manifest = json.loads(manifest_data)
    assert manifest["status"] == result.status
    assert set(manifest["output_receipts"]) == {
        "transformation_pairs.csv",
        "episode_transformations.csv",
        "transformation_coverage.json",
    }
    for name, receipt in manifest["output_receipts"].items():
        data = (destination / name).read_bytes()
        assert receipt["sha256"] == hashlib.sha256(data).hexdigest()
        assert receipt["bytes"] == len(data)


def test_two_success_terminals_are_byte_identical(tmp_path: Path) -> None:
    _publish(tmp_path, "first")
    _publish(tmp_path, "second")
    assert {
        path.name: path.read_bytes() for path in (tmp_path / "first").iterdir()
    } == {path.name: path.read_bytes() for path in (tmp_path / "second").iterdir()}


def test_supported_authority_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, geometry, support = _science()
    supported = replace(
        support,
        status="R4_TRANSFORMATION_COVERAGE_SUPPORTED",
        local_cyp3a4_state=replace(
            support.local_cyp3a4_state,
            status="LOCAL_SUPPORTED",
            meets_gate=True,
        ),
        selected_anchor_structural_coverage=replace(
            support.selected_anchor_structural_coverage,
            status="SUPPORTED",
            meets_gate=True,
        ),
    )
    monkeypatch.setattr(
        publication,
        "compile_transformation_support",
        lambda _bundle, _geometry: supported,
    )
    result = publish_transformation_coverage(
        destination=tmp_path / "supported",
        bundle=bundle,
        geometry=geometry,
        support=supported,
        runtime=_runtime(),
        expected_episode_rows=2,
    )
    manifest = json.loads(result.manifest_path.read_bytes())
    assert result.status == "R4_TRANSFORMATION_COVERAGE_SUPPORTED"
    assert manifest["authority"]["oracle_contract_freeze"] is True


def test_fabricated_support_is_rejected(tmp_path: Path) -> None:
    bundle, geometry, support = _science()
    fabricated = replace(support, status="R4_TRANSFORMATION_COVERAGE_SUPPORTED")
    with pytest.raises(OpenADMETTransformationCoverageError, match="support facts"):
        publish_transformation_coverage(
            destination=tmp_path / "fabricated",
            bundle=bundle,
            geometry=geometry,
            support=fabricated,
            runtime=_runtime(),
            expected_episode_rows=2,
        )


def test_failure_terminal_has_only_sorted_codes_and_zero_authority(
    tmp_path: Path,
) -> None:
    result = publish_transformation_failure(
        destination=tmp_path / "failure",
        terminal_codes=("P6", "C1", "P6"),
        runtime=_runtime(),
    )
    receipt = json.loads(result.manifest_path.read_bytes())
    assert [path.name for path in result.output_directory.iterdir()] == [
        "failure_receipt.json"
    ]
    assert receipt["terminal_integrity_failure_codes"] == ["C1", "P6"]
    assert not any(
        value for key, value in receipt["authority"].items() if key != "status"
    )
    assert _mode(result.output_directory) == 0o555


def test_forged_input_receipt_is_rejected(tmp_path: Path) -> None:
    bundle, geometry, support = _science()
    forged = replace(
        bundle,
        input_receipts=(
            replace(bundle.input_receipts[0], sha256="bad", bytes=-1),
            *bundle.input_receipts[1:],
        ),
    )
    with pytest.raises(OpenADMETTransformationCoverageError, match="receipt value"):
        publish_transformation_coverage(
            destination=tmp_path / "terminal",
            bundle=forged,
            geometry=geometry,
            support=support,
            runtime=_runtime(),
            expected_episode_rows=2,
        )
    assert not (tmp_path / "terminal").exists()


def test_existing_destination_and_bad_runtime_publish_nothing(tmp_path: Path) -> None:
    destination = tmp_path / "terminal"
    destination.write_bytes(b"preserve")
    bundle, geometry, support = _science()
    with pytest.raises(Exception, match="already exists"):
        publish_transformation_coverage(
            destination=destination,
            bundle=bundle,
            geometry=geometry,
            support=support,
            runtime=_runtime(),
            expected_episode_rows=2,
        )
    assert destination.read_bytes() == b"preserve"
    with pytest.raises(OpenADMETTransformationCoverageError, match="runtime value"):
        publish_transformation_failure(
            destination=tmp_path / "bad-runtime",
            terminal_codes=("P1",),
            runtime={**_runtime(), "seed": False},
        )


def test_late_stage_mutation_is_rejected_and_cleaned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = publication._write_new

    def mutate(path: Path, data: bytes) -> None:
        original(path, data)
        if path.name == "manifest.json":
            episode = path.parent / "episode_transformations.csv"
            episode.chmod(0o644)
            episode.write_bytes(episode.read_bytes() + b"late")

    monkeypatch.setattr(publication, "_write_new", mutate)
    with pytest.raises(OpenADMETTransformationCoverageError, match="payload differs"):
        _publish(tmp_path)
    assert not (tmp_path / "terminal").exists()
    assert not list(tmp_path.glob(".r4-coverage-*"))


def test_failure_extra_file_is_rejected_and_cleaned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = publication._write_new

    def add_extra(path: Path, data: bytes) -> None:
        original(path, data)
        if path.name == "failure_receipt.json":
            (path.parent / "extra.bin").write_bytes(b"forbidden")

    monkeypatch.setattr(publication, "_write_new", add_extra)
    with pytest.raises(OpenADMETTransformationCoverageError, match="file set"):
        publish_transformation_failure(
            destination=tmp_path / "failure",
            terminal_codes=("P6",),
            runtime=_runtime(),
        )
    assert not (tmp_path / "failure").exists()
    assert not list(tmp_path.glob(".r4-coverage-failure-*"))


def test_final_rename_race_preserves_competitor_and_cleans_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "terminal"

    def race(_stage: Path, output: Path) -> None:
        output.mkdir()
        (output / "competitor").write_bytes(b"preserve")
        raise OpenADMETTransformationCoverageError("output path already exists")

    monkeypatch.setattr(publication, "_rename_noreplace", race)
    with pytest.raises(OpenADMETTransformationCoverageError, match="already exists"):
        _publish(tmp_path)
    assert (destination / "competitor").read_bytes() == b"preserve"
    assert not list(tmp_path.glob(".r4-coverage-*"))


def test_official_episode_cardinality_is_rechecked(tmp_path: Path) -> None:
    bundle, geometry, support = _science()
    with pytest.raises(OpenADMETTransformationCoverageError, match="rows differ"):
        publish_transformation_coverage(
            destination=tmp_path / "terminal",
            bundle=bundle,
            geometry=geometry,
            support=support,
            runtime=_runtime(),
        )

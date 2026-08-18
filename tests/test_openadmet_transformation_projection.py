from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import cypshift.openadmet_transformation_projection as projection_module
from cypshift.openadmet_transformation_io import (
    OBSERVATION_COLUMNS,
    TransformationSourcePaths,
    canonical_csv_bytes,
)
from cypshift.openadmet_transformation_projection import (
    OUTPUT_FILES,
    OpenADMETTransformationProjectionError,
    project_openadmet_transformation_inputs,
)
from cypshift.openadmet_validation import FOLD_COLUMNS
from cypshift.openadmet_validation_contract import MASK_COLUMNS, PUBLIC_EPISODE_COLUMNS


def _csv(columns: tuple[str, ...], rows: list[dict[str, str]]) -> bytes:
    return canonical_csv_bytes(columns, rows)


def _fixture(tmp_path: Path) -> tuple[TransformationSourcePaths, dict[str, str]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    molecules = {
        "anchor": "CCO",
        "query": "CCN",
        "other": "CCC",
        "foreign": "C=O",
    }
    component_hash = hashlib.sha256(b"component-a").hexdigest()
    foreign_component_hash = hashlib.sha256(b"component-b").hexdigest()
    structures: list[dict[str, str]] = []
    for molecule_id, smiles in molecules.items():
        standardized = smiles
        structures.append(
            {
                "molecule_id": molecule_id,
                "raw_smiles": smiles,
                "raw_structure_sha256": hashlib.sha256(smiles.encode()).hexdigest(),
                "standardized_smiles": standardized,
                "standardized_structure_hash": hashlib.sha256(
                    standardized.encode()
                ).hexdigest(),
                "similarity_component_hash": (
                    foreign_component_hash
                    if molecule_id == "foreign"
                    else component_hash
                ),
            }
        )
    structure_by_id = {row["molecule_id"]: row for row in structures}
    direct: list[dict[str, str]] = []
    for molecule_id in molecules:
        for endpoint_index, endpoint in enumerate(
            ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
        ):
            direct.append(
                {
                    "observation_id": hashlib.sha256(
                        f"obs-{molecule_id}-{endpoint_index}".encode()
                    ).hexdigest(),
                    "molecule_id": molecule_id,
                    "source_row_id": f"source:{molecule_id}",
                    "source_file": "source.csv",
                    "source_row": str(endpoint_index + 1),
                    "source_sha256": "0" * 64,
                    "endpoint": endpoint,
                    "raw_smiles": molecules[molecule_id],
                    "raw_point": '"POISON,target,span"',
                    "raw_low": "POISON",
                    "raw_high": "POISON",
                    "raw_std": "POISON",
                    "point": "POISON",
                    "low": "POISON",
                    "high": "POISON",
                    "std": "POISON",
                    "raw_structure_sha256": structure_by_id[molecule_id][
                        "raw_structure_sha256"
                    ],
                    "standardized_structure_hash": structure_by_id[molecule_id][
                        "standardized_structure_hash"
                    ],
                    "similarity_component_hash": structure_by_id[molecule_id][
                        "similarity_component_hash"
                    ],
                    "scaffold_group_hash": "0" * 64,
                    "value_state": "complete",
                    "point_eligible": "POISON",
                    "anchor_eligible": "POISON",
                }
            )
    folds = [
        {
            "molecule_id": molecule_id,
            "similarity_component_hash": structure_by_id[molecule_id][
                "similarity_component_hash"
            ],
            "repeat": str(repeat),
            "seed": str(20260810 + repeat),
            "outer_fold": "1" if molecule_id == "foreign" else "0",
            "outer_validation_fold": str(validation),
            "inner_fold": (
                "" if validation == (1 if molecule_id == "foreign" else 0) else "0"
            ),
        }
        for molecule_id in molecules
        for repeat in range(3)
        for validation in range(5)
    ]
    episode = {
        "episode_id": hashlib.sha256(b"episode-a").hexdigest(),
        "protocol": "ANCHOR_EXPANSION_HOLDOUT",
        "repeat": "0",
        "outer_fold": "0",
        "outer_group_id": component_hash,
        "query_molecule_ids": '["query"]',
        "candidate_pool_id": "DEFERRED_NO_INFERRED_POOL_V1",
        "episode_policy_id": "selected_anchor",
    }
    mask = {
        "episode_id": episode["episode_id"],
        "anchor_molecule_id_truth": "anchor",
        "anchor_observation_references": '"POISON,forbidden,suffix"',
        "anchor_value_availability_mask": "POISON",
    }
    values = {
        "direct_observations.csv": _csv(OBSERVATION_COLUMNS, direct),
        "group_folds.csv": _csv(FOLD_COLUMNS, folds),
        "public_episodes.csv": _csv(PUBLIC_EPISODE_COLUMNS, [episode]),
        "masks.csv": _csv(MASK_COLUMNS, [mask]),
        "structure.csv": _csv(
            (
                "molecule_id",
                "raw_smiles",
                "raw_structure_sha256",
                "standardized_smiles",
                "standardized_structure_hash",
                "similarity_component_hash",
            ),
            structures,
        ),
    }
    paths = TransformationSourcePaths(*(tmp_path / name for name in values))
    for (_, path), data in zip(paths.items(), values.values(), strict=True):
        path.write_bytes(data)
    receipts = {name: hashlib.sha256(data).hexdigest() for name, data in values.items()}
    return paths, receipts


def _expect_rejection(
    paths: TransformationSourcePaths,
    receipts: dict[str, str],
    output_directory: Path,
) -> None:
    with pytest.raises(OpenADMETTransformationProjectionError):
        project_openadmet_transformation_inputs(
            direct_observations_path=paths.direct_observations,
            group_folds_path=paths.group_folds,
            public_episodes_path=paths.public_episodes,
            masks_path=paths.masks,
            structure_path=paths.structure,
            output_directory=output_directory,
            expected_receipts=receipts,
        )
    assert not output_directory.exists()


def _replace_source(
    path: Path,
    receipts: dict[str, str],
    old: bytes,
    new: bytes,
    *,
    count: int = 1,
) -> None:
    data = path.read_bytes().replace(old, new, count)
    path.write_bytes(data)
    receipts[path.name] = hashlib.sha256(data).hexdigest()


def test_projection_is_receipt_bound_and_poison_free(tmp_path: Path) -> None:
    paths, receipts = _fixture(tmp_path)
    result = project_openadmet_transformation_inputs(
        direct_observations_path=paths.direct_observations,
        group_folds_path=paths.group_folds,
        public_episodes_path=paths.public_episodes,
        masks_path=paths.masks,
        structure_path=paths.structure,
        output_directory=tmp_path / "out",
        expected_receipts=receipts,
    )
    assert result.rows == {
        "direct": 16,
        "folds": 60,
        "public": 1,
        "masks": 1,
        "structure": 4,
    }
    assert (result.output_directory / "direct_projection.csv").read_bytes().find(
        b"POISON"
    ) == -1
    assert (result.output_directory / "mask_projection.csv").read_bytes().find(
        b"POISON"
    ) == -1
    manifest = json.loads(result.manifest_path.read_bytes())
    assert manifest["accounting"]["numeric_target_magnitudes_parsed"] == 0
    assert manifest["authority"] == {
        "status": "R4_TRANSFORMATION_PROJECTION_SYNTHETIC_ONLY",
        "coverage_artifacts": False,
        "label_derivation": False,
        "geometry_coverage": False,
        "oracle_contract_freeze": False,
        "model_fits": False,
        "predictions": False,
        "metrics": False,
        "official_st_rae": False,
        "test_access": False,
        "tdi": False,
        "submissions": False,
        "transduction": False,
    }
    for name, receipt in manifest["output_receipts"].items():
        data = (result.output_directory / name).read_bytes()
        assert receipt["sha256"] == hashlib.sha256(data).hexdigest()
        assert isinstance(receipt["rows"], int)
        assert receipt["columns"]


def test_invalid_utf8_in_opaque_suffix_is_never_decoded(tmp_path: Path) -> None:
    paths, receipts = _fixture(tmp_path)
    direct_data = paths.direct_observations.read_bytes()
    paths.direct_observations.write_bytes(direct_data.replace(b"POISON", b"\xff", 1))
    receipts["direct_observations.csv"] = hashlib.sha256(
        paths.direct_observations.read_bytes()
    ).hexdigest()
    mask_data = paths.masks.read_bytes()
    paths.masks.write_bytes(mask_data.replace(b"POISON", b"\xfe", 1))
    receipts["masks.csv"] = hashlib.sha256(paths.masks.read_bytes()).hexdigest()
    result = project_openadmet_transformation_inputs(
        direct_observations_path=paths.direct_observations,
        group_folds_path=paths.group_folds,
        public_episodes_path=paths.public_episodes,
        masks_path=paths.masks,
        structure_path=paths.structure,
        output_directory=tmp_path / "opaque",
        expected_receipts=receipts,
    )
    assert result.output_directory.exists()
    assert (
        b"\xff" not in (result.output_directory / "direct_projection.csv").read_bytes()
    )
    assert b"\xfe" not in (result.output_directory / "mask_projection.csv").read_bytes()


def _replace_mask_suffix(
    paths: TransformationSourcePaths,
    receipts: dict[str, str],
    suffix: bytes,
) -> None:
    data = paths.masks.read_bytes()
    header, row = data.split(b"\n", 1)
    row = row.split(b"\n", 1)[0]
    prefix = b",".join(row.split(b",")[:2])
    updated = header + b"\n" + prefix + b"," + suffix + b"\n"
    paths.masks.write_bytes(updated)
    receipts["masks.csv"] = hashlib.sha256(updated).hexdigest()


@pytest.mark.parametrize(
    "suffix",
    [b'"x"', b'"x","y","z"', b'a,b,"x"oops,y'],
)
def test_mask_opaque_tail_rejects_truncation_extra_fields_and_bad_quotes(
    tmp_path: Path, suffix: bytes
) -> None:
    paths, receipts = _fixture(tmp_path)
    _replace_mask_suffix(paths, receipts, suffix)
    with pytest.raises(OpenADMETTransformationProjectionError):
        project_openadmet_transformation_inputs(
            direct_observations_path=paths.direct_observations,
            group_folds_path=paths.group_folds,
            public_episodes_path=paths.public_episodes,
            masks_path=paths.masks,
            structure_path=paths.structure,
            output_directory=tmp_path / "bad-mask",
            expected_receipts=receipts,
        )
    assert not (tmp_path / "bad-mask").exists()


def test_mask_opaque_tail_accepts_quoted_commas_and_newlines(tmp_path: Path) -> None:
    paths, receipts = _fixture(tmp_path)
    _replace_mask_suffix(paths, receipts, b'"a,b","c\nd"')
    result = project_openadmet_transformation_inputs(
        direct_observations_path=paths.direct_observations,
        group_folds_path=paths.group_folds,
        public_episodes_path=paths.public_episodes,
        masks_path=paths.masks,
        structure_path=paths.structure,
        output_directory=tmp_path / "quoted-mask",
        expected_receipts=receipts,
    )
    assert result.output_directory.exists()


def test_source_row_permutations_have_canonical_projected_bytes(tmp_path: Path) -> None:
    first_paths, first_receipts = _fixture(tmp_path / "first")
    second_paths, second_receipts = _fixture(tmp_path / "second")
    for _, path in second_paths.items():
        data = path.read_bytes()
        lines = data.splitlines(keepends=True)
        path.write_bytes(lines[0] + b"".join(reversed(lines[1:])))
        second_receipts[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()

    first = project_openadmet_transformation_inputs(
        direct_observations_path=first_paths.direct_observations,
        group_folds_path=first_paths.group_folds,
        public_episodes_path=first_paths.public_episodes,
        masks_path=first_paths.masks,
        structure_path=first_paths.structure,
        output_directory=tmp_path / "first-output",
        expected_receipts=first_receipts,
    )
    second = project_openadmet_transformation_inputs(
        direct_observations_path=second_paths.direct_observations,
        group_folds_path=second_paths.group_folds,
        public_episodes_path=second_paths.public_episodes,
        masks_path=second_paths.masks,
        structure_path=second_paths.structure,
        output_directory=tmp_path / "second-output",
        expected_receipts=second_receipts,
    )
    csv_outputs = [name for name in OUTPUT_FILES if name.endswith(".csv")]
    assert all(
        (first.output_directory / name).read_bytes()
        == (second.output_directory / name).read_bytes()
        for name in csv_outputs
    )


@pytest.mark.parametrize("mutation", ["endpoint", "cardinality", "component"])
def test_direct_join_mutations_fail_closed(tmp_path: Path, mutation: str) -> None:
    paths, receipts = _fixture(tmp_path)
    if mutation == "endpoint":
        _replace_source(paths.direct_observations, receipts, b"CYP1A2", b"CYP9A9")
    elif mutation == "cardinality":
        data = paths.direct_observations.read_bytes()
        lines = data.splitlines(keepends=True)
        data = b"".join([lines[0], *lines[1:-1]])
        paths.direct_observations.write_bytes(data)
        receipts["direct_observations.csv"] = hashlib.sha256(data).hexdigest()
    else:
        _replace_source(
            paths.direct_observations,
            receipts,
            hashlib.sha256(b"component-a").hexdigest().encode(),
            hashlib.sha256(b"component-b").hexdigest().encode(),
        )
    _expect_rejection(paths, receipts, tmp_path / f"bad-direct-{mutation}")


@pytest.mark.parametrize("mutation", ["matrix", "component", "inner"])
def test_fold_join_mutations_fail_closed(tmp_path: Path, mutation: str) -> None:
    paths, receipts = _fixture(tmp_path)
    if mutation == "matrix":
        data = paths.group_folds.read_bytes()
        lines = data.splitlines(keepends=True)
        data = b"".join([lines[0], *lines[1:-1]])
        paths.group_folds.write_bytes(data)
        receipts["group_folds.csv"] = hashlib.sha256(data).hexdigest()
    elif mutation == "component":
        _replace_source(
            paths.group_folds,
            receipts,
            hashlib.sha256(b"component-a").hexdigest().encode(),
            hashlib.sha256(b"component-b").hexdigest().encode(),
        )
    else:
        _replace_source(
            paths.group_folds,
            receipts,
            b",20260810,0,1,0\n",
            b",20260810,0,1,1\n",
        )
    _expect_rejection(paths, receipts, tmp_path / f"bad-fold-{mutation}")


@pytest.mark.parametrize("mutation", ["query", "component", "fold", "policy"])
def test_public_join_mutations_fail_closed(tmp_path: Path, mutation: str) -> None:
    paths, receipts = _fixture(tmp_path)
    if mutation == "query":
        _replace_source(paths.public_episodes, receipts, b"query", b"foreign")
    elif mutation == "component":
        _replace_source(
            paths.public_episodes,
            receipts,
            hashlib.sha256(b"component-a").hexdigest().encode(),
            hashlib.sha256(b"component-b").hexdigest().encode(),
        )
    elif mutation == "fold":
        component_hash = hashlib.sha256(b"component-a").hexdigest().encode()
        _replace_source(
            paths.public_episodes,
            receipts,
            b",0," + component_hash,
            b",1," + component_hash,
        )
    else:
        _replace_source(
            paths.public_episodes, receipts, b"selected_anchor", b"bad_policy"
        )
    _expect_rejection(paths, receipts, tmp_path / f"bad-public-{mutation}")


@pytest.mark.parametrize("mutation", ["membership", "disjoint", "component", "fold"])
def test_mask_join_mutations_fail_closed(tmp_path: Path, mutation: str) -> None:
    paths, receipts = _fixture(tmp_path)
    if mutation == "membership":
        _replace_source(
            paths.masks,
            receipts,
            hashlib.sha256(b"episode-a").hexdigest().encode(),
            hashlib.sha256(b"episode-b").hexdigest().encode(),
        )
    elif mutation == "disjoint":
        _replace_source(paths.masks, receipts, b"anchor", b"query")
    elif mutation == "component":
        _replace_source(paths.masks, receipts, b"anchor", b"foreign")
    else:
        # The mask's fold assignment is coupled to its public episode cell.
        component_hash = hashlib.sha256(b"component-a").hexdigest().encode()
        _replace_source(
            paths.public_episodes,
            receipts,
            b",0," + component_hash,
            b",1," + component_hash,
        )
    _expect_rejection(paths, receipts, tmp_path / f"bad-mask-{mutation}")


@pytest.mark.parametrize("bad_value", ["00", "-0", "+0", " 0"])
def test_noncanonical_fold_repeat_is_rejected(tmp_path: Path, bad_value: str) -> None:
    paths, receipts = _fixture(tmp_path)
    data = paths.group_folds.read_bytes().replace(
        b",0,20260810,0,0,",
        f",{bad_value},20260810,0,0,".encode(),
        1,
    )
    paths.group_folds.write_bytes(data)
    receipts["group_folds.csv"] = hashlib.sha256(data).hexdigest()
    with pytest.raises(OpenADMETTransformationProjectionError, match="integer"):
        project_openadmet_transformation_inputs(
            direct_observations_path=paths.direct_observations,
            group_folds_path=paths.group_folds,
            public_episodes_path=paths.public_episodes,
            masks_path=paths.masks,
            structure_path=paths.structure,
            output_directory=tmp_path / "bad-fold-repeat",
            expected_receipts=receipts,
        )


@pytest.mark.parametrize("bad_value", ["00", "-0", "+0", " 0"])
def test_noncanonical_public_repeat_is_rejected(tmp_path: Path, bad_value: str) -> None:
    paths, receipts = _fixture(tmp_path)
    data = paths.public_episodes.read_bytes().replace(
        b",0,0,",
        f",{bad_value},0,".encode(),
        1,
    )
    paths.public_episodes.write_bytes(data)
    receipts["public_episodes.csv"] = hashlib.sha256(data).hexdigest()
    with pytest.raises(OpenADMETTransformationProjectionError, match="integer"):
        project_openadmet_transformation_inputs(
            direct_observations_path=paths.direct_observations,
            group_folds_path=paths.group_folds,
            public_episodes_path=paths.public_episodes,
            masks_path=paths.masks,
            structure_path=paths.structure,
            output_directory=tmp_path / "bad-public-repeat",
            expected_receipts=receipts,
        )


def test_invalid_receipt_metadata_precedes_malformed_source_parse(
    tmp_path: Path,
) -> None:
    paths, receipts = _fixture(tmp_path)
    malformed = b"not,the,contracted,header\n"
    paths.direct_observations.write_bytes(malformed)
    expected_receipts: dict[str, str | dict[str, object]] = dict(receipts)
    expected_receipts["direct_observations.csv"] = {
        "sha256": hashlib.sha256(malformed).hexdigest(),
        "rows": "bad",
    }
    with pytest.raises(
        OpenADMETTransformationProjectionError, match="invalid row receipt"
    ):
        project_openadmet_transformation_inputs(
            direct_observations_path=paths.direct_observations,
            group_folds_path=paths.group_folds,
            public_episodes_path=paths.public_episodes,
            masks_path=paths.masks,
            structure_path=paths.structure,
            output_directory=tmp_path / "bad-receipt-metadata",
            expected_receipts=expected_receipts,
        )
    assert not (tmp_path / "bad-receipt-metadata").exists()


def test_drift_and_duplicate_json_fail_before_publication(tmp_path: Path) -> None:
    paths, receipts = _fixture(tmp_path)
    altered = paths.public_episodes.read_bytes().replace(b"query", b"other")
    paths.public_episodes.write_bytes(altered)
    with pytest.raises(
        OpenADMETTransformationProjectionError, match="SHA-256 mismatch"
    ):
        project_openadmet_transformation_inputs(
            direct_observations_path=paths.direct_observations,
            group_folds_path=paths.group_folds,
            public_episodes_path=paths.public_episodes,
            masks_path=paths.masks,
            structure_path=paths.structure,
            output_directory=tmp_path / "drift",
            expected_receipts=receipts,
        )
    assert not (tmp_path / "drift").exists()
    with pytest.raises(
        OpenADMETTransformationProjectionError, match="duplicate receipt"
    ):
        project_openadmet_transformation_inputs(
            direct_observations_path=paths.direct_observations,
            group_folds_path=paths.group_folds,
            public_episodes_path=paths.public_episodes,
            masks_path=paths.masks,
            structure_path=paths.structure,
            output_directory=tmp_path / "receipt-alias-collision",
            expected_receipts={
                **receipts,
                "direct": receipts["direct_observations.csv"],
            },
        )


def test_duplicate_json_key_fails_after_receipt_update(tmp_path: Path) -> None:
    paths, receipts = _fixture(tmp_path)
    episode = {
        "episode_id": hashlib.sha256(b"episode-a").hexdigest(),
        "protocol": "ANCHOR_EXPANSION_HOLDOUT",
        "repeat": "0",
        "outer_fold": "0",
        "outer_group_id": hashlib.sha256(b"component-a").hexdigest(),
        "query_molecule_ids": '[{"query":1,"query":2}]',
        "candidate_pool_id": "DEFERRED_NO_INFERRED_POOL_V1",
        "episode_policy_id": "selected_anchor",
    }
    data = _csv(PUBLIC_EPISODE_COLUMNS, [episode])
    paths.public_episodes.write_bytes(data)
    receipts["public_episodes.csv"] = hashlib.sha256(data).hexdigest()
    with pytest.raises(
        OpenADMETTransformationProjectionError, match="duplicate JSON key"
    ):
        project_openadmet_transformation_inputs(
            direct_observations_path=paths.direct_observations,
            group_folds_path=paths.group_folds,
            public_episodes_path=paths.public_episodes,
            masks_path=paths.masks,
            structure_path=paths.structure,
            output_directory=tmp_path / "duplicate-json",
            expected_receipts=receipts,
        )
    assert not (tmp_path / "duplicate-json").exists()


def test_symlink_and_overwrite_are_rejected(tmp_path: Path) -> None:
    paths, receipts = _fixture(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(paths.structure)
    with pytest.raises(OpenADMETTransformationProjectionError, match="symlink"):
        project_openadmet_transformation_inputs(
            direct_observations_path=paths.direct_observations,
            group_folds_path=paths.group_folds,
            public_episodes_path=paths.public_episodes,
            masks_path=paths.masks,
            structure_path=link,
            output_directory=tmp_path / "out",
            expected_receipts=receipts,
        )
    with pytest.raises(OpenADMETTransformationProjectionError, match="already exists"):
        project_openadmet_transformation_inputs(
            direct_observations_path=paths.direct_observations,
            group_folds_path=paths.group_folds,
            public_episodes_path=paths.public_episodes,
            masks_path=paths.masks,
            structure_path=paths.structure,
            output_directory=target,
            expected_receipts=receipts,
        )


def test_publication_file_set_and_modes_are_exact(tmp_path: Path) -> None:
    paths, receipts = _fixture(tmp_path)
    result = project_openadmet_transformation_inputs(
        direct_observations_path=paths.direct_observations,
        group_folds_path=paths.group_folds,
        public_episodes_path=paths.public_episodes,
        masks_path=paths.masks,
        structure_path=paths.structure,
        output_directory=tmp_path / "modes",
        expected_receipts=receipts,
    )
    output = result.output_directory
    assert {item.name for item in output.iterdir()} == set(OUTPUT_FILES)
    assert output.stat().st_mode & 0o777 == 0o555
    assert all((output / name).stat().st_mode & 0o777 == 0o444 for name in OUTPUT_FILES)


def test_output_parent_and_broken_destination_symlinks_are_rejected(
    tmp_path: Path,
) -> None:
    paths, receipts = _fixture(tmp_path)
    target = tmp_path / "real-parent"
    target.mkdir()
    parent_link = tmp_path / "parent-link"
    parent_link.symlink_to(target, target_is_directory=True)
    _expect_rejection(paths, receipts, parent_link / "out")

    broken = tmp_path / "broken-output"
    broken.symlink_to(tmp_path / "does-not-exist")
    _expect_rejection(paths, receipts, broken)


def test_mid_stage_failure_cleans_private_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, receipts = _fixture(tmp_path)

    def fail_stage(*_: object) -> None:
        raise OpenADMETTransformationProjectionError("injected stage failure")

    monkeypatch.setattr(projection_module, "_verify_staged_outputs", fail_stage)
    with pytest.raises(OpenADMETTransformationProjectionError, match="injected"):
        project_openadmet_transformation_inputs(
            direct_observations_path=paths.direct_observations,
            group_folds_path=paths.group_folds,
            public_episodes_path=paths.public_episodes,
            masks_path=paths.masks,
            structure_path=paths.structure,
            output_directory=tmp_path / "mid-stage",
            expected_receipts=receipts,
        )
    assert not list(tmp_path.glob(".r4-projection-*"))


def test_no_replace_race_preserves_intruder_and_cleans_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, receipts = _fixture(tmp_path)
    destination = tmp_path / "race-output"

    def race(_: Path, destination_path: Path) -> None:
        destination_path.mkdir()
        (destination_path / "intruder").write_text("preserve")
        raise OpenADMETTransformationProjectionError("destination race")

    monkeypatch.setattr(projection_module, "_rename_noreplace", race)
    with pytest.raises(OpenADMETTransformationProjectionError, match="race"):
        project_openadmet_transformation_inputs(
            direct_observations_path=paths.direct_observations,
            group_folds_path=paths.group_folds,
            public_episodes_path=paths.public_episodes,
            masks_path=paths.masks,
            structure_path=paths.structure,
            output_directory=destination,
            expected_receipts=receipts,
        )
    assert (destination / "intruder").read_text() == "preserve"
    assert not list(tmp_path.glob(".r4-projection-*"))

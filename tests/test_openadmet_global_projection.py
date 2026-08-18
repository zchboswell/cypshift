from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest

import cypshift.openadmet_global_projection as projection_module
from cypshift.openadmet_global_io import (
    PREFLIGHT_SOURCE_FILES,
    PROJECTION_SOURCE_FILES,
    _json_object,
    _runtime_gate,
)
from cypshift.openadmet_global_projection import (
    OpenADMETGlobalPreflightError,
    OpenADMETGlobalProjectionError,
    preflight_openadmet_global_targets,
    project_openadmet_global_targets,
)
from cypshift.openadmet_validation import FOLD_COLUMNS, OBSERVATION_COLUMNS

pytestmark = pytest.mark.skipif(
    sys.version_info[:3] != (3, 12, 3),
    reason="R3B projection runtime is frozen to Python 3.12.3",
)

ENDPOINTS = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")


def _csv_bytes(columns: tuple[str, ...], rows: list[dict[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def _fixture(root: Path, molecule_count: int = 12) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    molecules = [f"mol-{index:03}" for index in range(molecule_count)]
    direct: list[dict[str, str]] = []
    folds: list[dict[str, str]] = []
    for index, molecule in enumerate(molecules):
        for endpoint in ENDPOINTS:
            row = {column: "" for column in OBSERVATION_COLUMNS}
            row.update(
                observation_id=hashlib.sha256(
                    f"{molecule}|{endpoint}".encode()
                ).hexdigest(),
                molecule_id=molecule,
                endpoint=endpoint,
                point="5.0",
                value_state="complete",
                point_eligible="true",
            )
            direct.append(row)
        for repeat in range(3):
            assignment = index % 5
            for validation in range(5):
                folds.append(
                    {
                        "molecule_id": molecule,
                        "similarity_component_hash": hashlib.sha256(
                            f"component-{index}".encode()
                        ).hexdigest(),
                        "repeat": str(repeat),
                        "seed": str(20260810 + repeat),
                        "outer_fold": str(assignment),
                        "outer_validation_fold": str(validation),
                        "inner_fold": ""
                        if assignment == validation
                        else str(index % 4),
                    }
                )
    direct_data = _csv_bytes(OBSERVATION_COLUMNS, direct)
    fold_data = _csv_bytes(FOLD_COLUMNS, folds)
    direct_path = root / "direct_observations.csv"
    folds_path = root / "group_folds.csv"
    direct_path.write_bytes(direct_data)
    folds_path.write_bytes(fold_data)
    counts = {
        "direct_rows": len(direct),
        "fold_rows": len(folds),
        "eligible": len(direct),
        "ineligible": 0,
        "complete": len(direct),
        "partial": 0,
        "missing": 0,
        "orphan_auxiliary": 0,
    }
    return {
        "direct": direct_path,
        "folds": folds_path,
        "receipts": {
            "direct_observations_sha256": hashlib.sha256(direct_data).hexdigest(),
            "group_folds_sha256": hashlib.sha256(fold_data).hexdigest(),
        },
        "counts": counts,
    }


def _project(paths: dict[str, Any], output: Path) -> Any:
    return project_openadmet_global_targets(
        paths["direct"],
        paths["folds"],
        output,
        expected_input_receipts=paths["receipts"],
        expected_counts=paths["counts"],
    )


def _one_molecule_counts(paths: dict[str, Any]) -> dict[str, int]:
    return {
        **paths["counts"],
        "outer_target_files": 60,
        "inner_target_files": 240,
        "outer_target_rows": 48,
        "inner_target_rows": 144,
        "outer_truth_rows": 12,
        "inner_truth_rows": 48,
        "outer_truth_eligible": 12,
        "inner_truth_eligible": 48,
    }


def test_projection_uses_assigned_outer_and_scoped_inner_membership(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    result = _project(paths, tmp_path / "projection")
    outer = list(
        csv.DictReader(
            (
                result.model_public_root / "outer_targets/CYP1A2/repeat-0/outer-0.csv"
            ).open()
        )
    )
    assert len(outer) == 9
    assert all(int(row["molecule_id"].split("-")[1]) % 5 != 0 for row in outer)
    sealed_outer = list(
        csv.DictReader((result.scorer_sealed_root / "sealed_outer_truth.csv").open())
    )
    sealed_inner = list(
        csv.DictReader((result.scorer_sealed_root / "sealed_inner_truth.csv").open())
    )
    assert len(sealed_outer) == 144
    assert len(sealed_inner) == 576
    assert {row["scope"] for row in sealed_outer} == {"openadmet-direct-outer-v1"}
    assert {row["scope"] for row in sealed_inner} == {
        f"openadmet-direct-inner-v1|outer={outer_fold}" for outer_fold in range(5)
    }
    audit = json.loads(result.private_audit.read_text())
    assert audit["eligibility_counts"]["outer_target_rows"] == 576
    assert audit["eligibility_counts"]["inner_target_rows"] == 1728


def test_public_manifest_has_no_sealed_receipt_and_preflight_is_exact(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path, molecule_count=50)
    result = _project(paths, tmp_path / "projection")
    public = json.loads(result.model_public_manifest.read_text())
    assert "sealed_truth_manifest_sha256" not in public
    assert public["accounting"] == {
        "truth_paths": 0,
        "truth_hashes": 0,
        "scores": 0,
        "metrics": 0,
    }
    preflight = preflight_openadmet_global_targets(
        result.output_directory,
        expected_model_public_manifest_sha256=result.model_public_manifest_sha256,
        expected_private_audit_sha256=result.private_audit_sha256,
    )
    assert preflight.receipt["passed"] is True
    assert preflight.receipt["failure_reasons"] == []
    assert len(preflight.receipt["checks"]["outer_score_support_cells"]) == 60
    for record in preflight.receipt["checks"]["q90_residual_eligibility_populations"]:
        outer = (
            result.model_public_root
            / "outer_targets"
            / record["endpoint"]
            / f"repeat-{record['repeat']}"
            / f"outer-{record['outer_fold']}.csv"
        )
        assert record["eligible_residuals"] == sum(
            1 for _ in csv.DictReader(outer.open())
        )
    receipt_path = tmp_path / "preflight.json"
    preflight_openadmet_global_targets(
        result.output_directory, output_path=receipt_path
    )
    assert receipt_path.stat().st_mode & 0o777 == 0o444
    with pytest.raises(OpenADMETGlobalPreflightError, match="already exists"):
        preflight_openadmet_global_targets(
            result.output_directory, output_path=receipt_path
        )


def test_receipt_before_parse_determinism_and_no_overwrite(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    paths["direct"].write_bytes(b"not,csv\n")
    with pytest.raises(OpenADMETGlobalProjectionError, match="SHA-256 mismatch"):
        _project(paths, tmp_path / "rejected")
    paths = _fixture(tmp_path / "fresh")
    first = _project(paths, tmp_path / "first")
    second = _project(paths, tmp_path / "second")
    assert first.private_audit.read_bytes() == second.private_audit.read_bytes()
    assert (
        first.model_public_manifest.read_bytes()
        == second.model_public_manifest.read_bytes()
    )
    with pytest.raises(OpenADMETGlobalProjectionError, match="refusing overwrite"):
        _project(paths, tmp_path / "first")


def test_one_molecule_emits_header_only_cells_then_fails_preflight(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path, molecule_count=1)
    result = project_openadmet_global_targets(
        paths["direct"],
        paths["folds"],
        tmp_path / "projection",
        expected_input_receipts=paths["receipts"],
        expected_counts=_one_molecule_counts(paths),
    )
    outer_paths = list((result.model_public_root / "outer_targets").rglob("*.csv"))
    inner_paths = list((result.model_public_root / "inner_targets").rglob("*.csv"))
    assert len(outer_paths) == 60
    assert len(inner_paths) == 240
    assert sum(1 for path in outer_paths if path.stat().st_size > 40) == 48
    assert sum(1 for path in inner_paths if path.stat().st_size > 40) == 144
    preflight = preflight_openadmet_global_targets(result.output_directory)
    assert preflight.receipt["passed"] is False
    assert set(preflight.receipt["failure_reasons"]) == {
        "OUTER_COMPONENT_SUPPORT",
        "OUTER_TRAINING_EMPTY",
        "INNER_TRAINING_EMPTY",
        "Q90_RESIDUAL_ELIGIBILITY_EMPTY",
    }
    assert all(
        value == 0
        for key, value in preflight.receipt["accounting"].items()
        if key != "preflight_target_files_opened"
    )
    assert preflight.receipt["accounting"]["preflight_target_files_opened"] == 300


def test_symlink_and_csv_width_controls_are_rejected(tmp_path: Path) -> None:
    paths = _fixture(tmp_path / "symlink")
    symlink = tmp_path / "direct-link.csv"
    symlink.symlink_to(paths["direct"])
    with pytest.raises(OpenADMETGlobalProjectionError, match="symlink"):
        project_openadmet_global_targets(
            symlink,
            paths["folds"],
            tmp_path / "symlink-output",
            expected_input_receipts=paths["receipts"],
            expected_counts=paths["counts"],
        )

    paths = _fixture(tmp_path / "width")
    malformed = paths["direct"].read_bytes() + b"too,few,fields\n"
    paths["direct"].write_bytes(malformed)
    paths["receipts"]["direct_observations_sha256"] = hashlib.sha256(
        malformed
    ).hexdigest()
    with pytest.raises(OpenADMETGlobalProjectionError, match="field-count"):
        _project(paths, tmp_path / "width-output")


def test_duplicate_json_and_public_truth_metadata_are_rejected(
    tmp_path: Path,
) -> None:
    with pytest.raises(OpenADMETGlobalProjectionError, match="duplicate JSON key"):
        _json_object(b'{"x": 1, "x": 2}', "fixture")

    paths = _fixture(tmp_path / "leakage", molecule_count=12)
    result = _project(paths, tmp_path / "leakage-output")
    manifest_path = result.model_public_manifest
    manifest_path.chmod(0o644)
    manifest = json.loads(manifest_path.read_text())
    manifest["outer_target_receipts"][0]["truth_sha256"] = "0" * 64
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    )
    with pytest.raises(
        OpenADMETGlobalPreflightError, match="forbidden public metadata"
    ):
        preflight_openadmet_global_targets(result.output_directory)


def test_inner_truth_keeps_ineligible_structural_rows(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, molecule_count=12)
    rows = list(csv.DictReader(paths["direct"].open()))
    rows[0]["value_state"] = "missing"
    rows[0]["point_eligible"] = "false"
    data = _csv_bytes(OBSERVATION_COLUMNS, rows)
    paths["direct"].write_bytes(data)
    paths["receipts"]["direct_observations_sha256"] = hashlib.sha256(data).hexdigest()
    paths["counts"].update(
        eligible=len(rows) - 1,
        ineligible=1,
        complete=len(rows) - 1,
        missing=1,
    )
    result = _project(paths, tmp_path / "projection")
    audit = json.loads(result.private_audit.read_text())
    assert audit["eligibility_counts"]["inner_truth_rows"] == 576
    assert audit["eligibility_counts"]["inner_truth_eligible"] == 564


def test_projection_source_acceptance_gate_is_before_inputs(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    source_sha = _runtime_gate(PROJECTION_SOURCE_FILES)
    result = project_openadmet_global_targets(
        paths["direct"],
        paths["folds"],
        tmp_path / "accepted",
        expected_input_receipts=paths["receipts"],
        expected_counts=paths["counts"],
        expected_projector_source_sha256=source_sha,
    )
    assert result.output_directory.exists()
    preflight_openadmet_global_targets(
        result.output_directory,
        expected_preflight_source_sha256=_runtime_gate(PREFLIGHT_SOURCE_FILES),
    )
    paths = _fixture(tmp_path / "rejected")
    paths["direct"].write_bytes(b"not,csv\n")
    with pytest.raises(OpenADMETGlobalProjectionError, match="acceptance"):
        project_openadmet_global_targets(
            paths["direct"],
            paths["folds"],
            tmp_path / "rejected-output",
            expected_projector_source_sha256="0" * 64,
        )


def test_fold_index_rejects_noncanonical_integer_and_component_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path / "canonical")
    rows = list(csv.DictReader(paths["folds"].open()))
    rows[0]["repeat"] = "00"
    data = _csv_bytes(FOLD_COLUMNS, rows)
    paths["folds"].write_bytes(data)
    paths["receipts"]["group_folds_sha256"] = hashlib.sha256(data).hexdigest()
    with pytest.raises(OpenADMETGlobalProjectionError, match="canonical"):
        _project(paths, tmp_path / "canonical-output")

    paths = _fixture(tmp_path / "component")
    rows = list(csv.DictReader(paths["folds"].open()))
    rows[1]["similarity_component_hash"] = hashlib.sha256(b"drift").hexdigest()
    data = _csv_bytes(FOLD_COLUMNS, rows)
    paths["folds"].write_bytes(data)
    paths["receipts"]["group_folds_sha256"] = hashlib.sha256(data).hexdigest()
    with pytest.raises(OpenADMETGlobalProjectionError, match="component"):
        _project(paths, tmp_path / "component-output")


def test_staged_authority_mutation_fails_byte_identity_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = projection_module._verify_staged_projection

    def tamper(*args: Any, **kwargs: Any) -> None:
        stage = args[0]
        manifest_path = stage / "model-public" / "model_public_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["authority"]["fold_assignments"] = not manifest["authority"][
            "fold_assignments"
        ]
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        original(*args, **kwargs)

    monkeypatch.setattr(projection_module, "_verify_staged_projection", tamper)
    paths = _fixture(tmp_path)
    with pytest.raises(
        OpenADMETGlobalProjectionError, match="bytes changed before promotion"
    ):
        _project(paths, tmp_path / "mutated")
    assert not (tmp_path / "mutated").exists()

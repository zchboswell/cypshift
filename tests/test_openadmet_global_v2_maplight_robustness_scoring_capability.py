from __future__ import annotations

import ast
import csv
import importlib
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "maplight-fixed"
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
sys.path.insert(0, str(RESEARCH))
maplight = importlib.import_module("global_v2_maplight_runner")
accepted = importlib.import_module("global_v2_maplight_execution_compiler")
compiler = importlib.import_module("global_v2_maplight_robustness_execution_compiler")
scoring = importlib.import_module("global_v2_maplight_robustness_scoring_compiler")
no_fit_driver = importlib.import_module(
    "run_global_v2_maplight_robustness_no_fit_acceptance"
)
driver = importlib.import_module(
    "run_global_v2_maplight_robustness_scoring_capability_acceptance"
)
REJECTION = (
    BENCHMARK / "global_v2_maplight_robustness_scoring_capability_rejection.json"
)


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _tree_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): maplight.sha256_path(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture(scope="module")
def compiled(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    root = tmp_path_factory.mktemp("g2-7e-scoring")
    model_source = no_fit_driver.publish_source(
        root=root / "model-source", reverse=False
    )
    model, scorer, preflight = compiler.compile_capabilities(
        source_root=model_source,
        output_root=root / "d126-capabilities",
        mode="synthetic",
        expected_compiler_sha256=maplight.sha256_path(compiler.SCRIPT),
    )
    direct_source = driver.publish_scoring_source(
        root=root / "scoring-source", reverse=False
    )
    capability = scoring.compile_scoring_capability(
        direct_source_root=direct_source,
        model_capability_root=model,
        scorer_capability_root=scorer,
        output_root=root / "scoring-capability",
        mode="synthetic",
        expected_compiler_sha256=maplight.sha256_path(scoring.SCRIPT),
    )
    return root, model, scorer, direct_source, capability, preflight


def _mutated_source(
    *,
    source: Path,
    destination: Path,
    development_ids: set[str],
    mutate: Callable[[dict[str, str]], None],
) -> Path:
    raw = (source / "direct_observations.csv").read_bytes()
    lines = raw.splitlines(keepends=True)
    changed = False
    for index, physical in enumerate(lines[1:], start=1):
        _observation, molecule = scoring._direct_prefix(physical[:-1])
        if molecule not in development_ids:
            continue
        row = dict(
            zip(
                accepted.DIRECT_COLUMNS,
                next(csv.reader([physical[:-1].decode("utf-8")])),
                strict=True,
            )
        )
        mutate(row)
        lines[index] = maplight.csv_bytes(accepted.DIRECT_COLUMNS, [row]).split(
            b"\n", 1
        )[1]
        changed = True
        break
    assert changed
    mutated = b"".join(lines)
    manifest = compiler._load_json(source / "manifest.json")
    manifest["direct_observations_sha256"] = maplight.sha256_bytes(mutated)
    return cast(
        Path,
        maplight.publish_files(
            destination,
            {
                "direct_observations.csv": mutated,
                "manifest.json": maplight.json_bytes(manifest),
            },
        ),
    )


def test_static_boundary_binds_d128_and_bars_d127_claim() -> None:
    parents = scoring.authenticate_static_boundary()
    assert parents == {
        "scoring_contract_sha256": scoring.CONTRACT_SHA256,
        "d127_claim_sha256": scoring.D127_CLAIM_SHA256,
        "d126_acceptance_sha256": scoring.D126_ACCEPTANCE_SHA256,
        "d126_compiler_sha256": maplight.sha256_path(compiler.SCRIPT),
    }
    claim = compiler._load_json(scoring.D127_CLAIM)
    assert claim["consumptions"] == 0
    assert claim["usable"] is False
    rejected_modules = {
        "global_v2_maplight_robustness_runner",
        "run_global_v2_maplight_robustness_synthetic",
    }
    for path in (scoring.SCRIPT, driver.SCRIPT):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert imports.isdisjoint(rejected_modules)


def test_official_shaped_scoring_source_keeps_confirmatory_suffixes_opaque() -> None:
    raw = driver.direct_observation_bytes(reverse=False)
    lines = raw.splitlines()
    assert len(lines) == 4801
    assert lines[0] == ",".join(accepted.DIRECT_COLUMNS).encode()
    decoded = 0
    opaque = 0
    for line in lines[1:]:
        _observation, molecule = scoring._direct_prefix(line)
        if int(molecule.rsplit("-", 1)[1]) >= 960:
            with pytest.raises(UnicodeDecodeError):
                line.decode("utf-8")
            opaque += 1
        else:
            row = next(csv.reader([line.decode("utf-8")]))
            assert len(row) == 23
            decoded += 1
    assert decoded == 3840
    assert opaque == 960


def test_compiler_publishes_only_exact_scoring_fields(compiled) -> None:  # type: ignore[no-untyped-def]
    _root, _model, _scorer, _source, capability, preflight = compiled
    assert preflight["status"] == "G2_7C_NO_FIT_PREFLIGHT_PASS"
    assert {path.name for path in capability.iterdir()} == {
        "manifest.json",
        "scoring_truth.csv",
    }
    manifest = compiler._load_json(capability / "manifest.json")
    rows = maplight._read_csv(capability / "scoring_truth.csv", scoring.OUTPUT_COLUMNS)
    assert len(rows) == 3840
    assert manifest["counts"] == {
        "all_endpoint_rows": 4800,
        "development_rows_decoded": 3840,
        "finite_development_point_rows_emitted": 3840,
        "tutorial_eligible_rows": 768,
        "confirmatory_rows_prefix_checked_suffix_opaque": 960,
        "confirmatory_value_fields_decoded": 0,
    }
    assert manifest["source_file_values"] == [scoring.DIRECT_SOURCE_FILE]
    assert manifest["model_capability_fields"] == 0
    assert manifest["feature_arrays"] == 0
    assert manifest["training_target_files"] == 0
    assert manifest["real_catboost_fits"] == 0
    assert manifest["development_metric_evaluations"] == 0
    assert manifest["model_quality_authority"] is False
    assert manifest["claim_authority"] is False


def test_opposite_physical_orders_compile_byte_identically(compiled, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    _root, model, scorer, _source, capability, _preflight = compiled
    reverse = driver.publish_scoring_source(root=tmp_path / "reverse", reverse=True)
    reverse_capability = scoring.compile_scoring_capability(
        direct_source_root=reverse,
        model_capability_root=model,
        scorer_capability_root=scorer,
        output_root=tmp_path / "reverse-capability",
        mode="synthetic",
        expected_compiler_sha256=maplight.sha256_path(scoring.SCRIPT),
    )
    assert _tree_map(capability) == _tree_map(reverse_capability)


def test_source_or_point_drift_fails_closed(compiled, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    _root, model, scorer, source, _capability, _preflight = compiled
    ids = set(scoring._model_identities(model, synthetic=True)[1])
    bad_source = _mutated_source(
        source=source,
        destination=tmp_path / "bad-source",
        development_ids=ids,
        mutate=lambda row: row.__setitem__("source_file", "invented-assay.csv"),
    )
    with pytest.raises(
        scoring.RobustnessScoringCompilerError,
        match="accepted source provenance differs",
    ):
        scoring.compile_scoring_capability(
            direct_source_root=bad_source,
            model_capability_root=model,
            scorer_capability_root=scorer,
            output_root=tmp_path / "must-not-publish-source",
            mode="synthetic",
            expected_compiler_sha256=maplight.sha256_path(scoring.SCRIPT),
        )
    bad_point = _mutated_source(
        source=source,
        destination=tmp_path / "bad-point",
        development_ids=ids,
        mutate=lambda row: row.__setitem__(
            "point", format(float(row["point"]) + 1.0, ".17g")
        ),
    )
    with pytest.raises(
        scoring.RobustnessScoringCompilerError,
        match="reported point differs",
    ):
        scoring.compile_scoring_capability(
            direct_source_root=bad_point,
            model_capability_root=model,
            scorer_capability_root=scorer,
            output_root=tmp_path / "must-not-publish-point",
            mode="synthetic",
            expected_compiler_sha256=maplight.sha256_path(scoring.SCRIPT),
        )


def test_structure_component_or_bound_drift_fails_closed(compiled, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    _root, model, scorer, source, _capability, _preflight = compiled
    ids = set(scoring._model_identities(model, synthetic=True)[1])

    def bad_bounds(row: dict[str, str]) -> None:
        row["low"] = str(float(row["point"]) + 1.0)
        row["high"] = str(float(row["point"]) + 2.0)

    cases: tuple[tuple[str, Callable[[dict[str, str]], None], str], ...] = (
        (
            "structure",
            lambda row: row.__setitem__("standardized_structure_hash", "f" * 64),
            "development direct identity differs",
        ),
        (
            "component",
            lambda row: row.__setitem__("similarity_component_hash", "f" * 64),
            "development direct identity differs",
        ),
        (
            "bounds",
            bad_bounds,
            "reported bounds do not contain point",
        ),
    )
    for label, mutation, message in cases:
        mutated = _mutated_source(
            source=source,
            destination=tmp_path / f"bad-{label}",
            development_ids=ids,
            mutate=mutation,
        )
        with pytest.raises(scoring.RobustnessScoringCompilerError, match=message):
            scoring.compile_scoring_capability(
                direct_source_root=mutated,
                model_capability_root=model,
                scorer_capability_root=scorer,
                output_root=tmp_path / f"must-not-publish-{label}",
                mode="synthetic",
                expected_compiler_sha256=maplight.sha256_path(scoring.SCRIPT),
            )


def test_wrong_receipt_symlink_overwrite_and_official_mode_fail_closed(
    compiled: Any, tmp_path: Path
) -> None:
    _root, model, scorer, source, _capability, _preflight = compiled
    with pytest.raises(
        scoring.RobustnessScoringCompilerError,
        match="scoring compiler source differs",
    ):
        scoring.compile_scoring_capability(
            direct_source_root=source,
            model_capability_root=model,
            scorer_capability_root=scorer,
            output_root=tmp_path / "wrong-receipt",
            mode="synthetic",
            expected_compiler_sha256="0" * 64,
        )
    symlink = tmp_path / "source-link"
    symlink.symlink_to(source, target_is_directory=True)
    with pytest.raises(Exception, match="not a directory|symlink"):
        scoring.compile_scoring_capability(
            direct_source_root=symlink,
            model_capability_root=model,
            scorer_capability_root=scorer,
            output_root=tmp_path / "symlink-output",
            mode="synthetic",
            expected_compiler_sha256=maplight.sha256_path(scoring.SCRIPT),
        )
    with pytest.raises(Exception, match="destination exists"):
        scoring.compile_scoring_capability(
            direct_source_root=source,
            model_capability_root=model,
            scorer_capability_root=scorer,
            output_root=tmp_path,
            mode="synthetic",
            expected_compiler_sha256=maplight.sha256_path(scoring.SCRIPT),
        )
    with pytest.raises(
        scoring.RobustnessScoringCompilerError,
        match="corrected official authorization is absent",
    ):
        scoring.compile_scoring_capability(
            direct_source_root=source,
            model_capability_root=model,
            scorer_capability_root=scorer,
            output_root=tmp_path / "official-output",
            mode="official",
            expected_compiler_sha256=maplight.sha256_path(scoring.SCRIPT),
        )


def test_rejection_preserves_exact_attempt_and_determinism_evidence() -> None:
    rejection = _load(REJECTION)
    assert rejection["status"] == (
        "G2_7E_MAPLIGHT_ROBUSTNESS_SCORING_CAPABILITY_REJECTED"
    )
    assert rejection["scoring_capability_contract_sha256"] == scoring.CONTRACT_SHA256
    assert rejection["attempt_accounting"] == {
        "authorized_attempts": 1,
        "attempts_consumed": 1,
        "attempts_remaining": 0,
        "roots_compiled": 2,
        "retained_synthetic_files_before_cleanup": 530,
        "retained_synthetic_bytes_before_cleanup": 52814752,
        "acceptance_published": False,
    }
    observation = rejection["determinism_observation"]
    assert observation["capability_maps_identical"] is True
    assert observation["accepted_as_scientific_evidence"] is False
    assert rejection["implementation_receipts_at_failure"] == {
        "scoring_compiler_source_sha256": (
            "6f15205fccb4a7c2e1cc2c7244e31acf15d7fd34b285c85145bfde551da6f492"
        ),
        "acceptance_driver_source_sha256": (
            "5d2a6df1d6b55da936ed75049f9271eeb011b4536a7590b1398d94f86ce4e782"
        ),
        "focused_tests_sha256": (
            "aec564d1ed17891528ee997f09f03f7d6161ba980a57293ade8a32641fc7daa9"
        ),
    }


def test_rejected_attempt_is_clean_and_cannot_be_reused(tmp_path: Path) -> None:
    rejection = _load(REJECTION)
    cleanup = rejection["cleanup"]
    assert cleanup["synthetic_work_root_present_after_cleanup"] is False
    assert cleanup["temporary_quarantine_parent_present_after_cleanup"] is False
    assert cleanup["private_roots_retained"] == 0
    assert rejection["operation_accounting"]["real_catboost_fits"] == 0
    assert all(value is False for value in rejection["authority"].values())
    assert not Path("/tmp/cypshift-g2-7e-scoring-capability-attempt-1").exists()
    assert not Path("/tmp/cypshift-g2-7e-rejected").exists()
    with pytest.raises(
        driver.ScoringCapabilityAcceptanceError,
        match="terminally consumed",
    ):
        driver.run_formal_acceptance(
            work_root=tmp_path / "must-not-exist",
            output_path=tmp_path / "must-not-publish.json",
        )
    assert not (tmp_path / "must-not-exist").exists()
    assert not (tmp_path / "must-not-publish.json").exists()


def test_public_rejection_contains_no_private_portal_result_fields() -> None:
    text = REJECTION.read_text(encoding="utf-8").lower()
    for forbidden in (
        "submission_name",
        "leaderboard_score",
        "leaderboard_rank",
        "remote_submission_id",
    ):
        assert forbidden not in text

from __future__ import annotations

import ast
import importlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "maplight-fixed"
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
sys.path.insert(0, str(RESEARCH))
maplight = importlib.import_module("global_v2_maplight_runner")
capability_compiler = importlib.import_module(
    "global_v2_maplight_robustness_execution_compiler"
)
scoring = importlib.import_module("global_v2_maplight_robustness_scoring_compiler")
no_fit_driver = importlib.import_module(
    "run_global_v2_maplight_robustness_no_fit_acceptance"
)
driver = importlib.import_module(
    "run_global_v2_maplight_robustness_scoring_capability_acceptance_v2"
)
CONTRACT = (
    BENCHMARK
    / "global_v2_maplight_robustness_scoring_capability_reacceptance_contract.json"
)


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_static_boundary_binds_d130_d129_and_unchanged_compiler() -> None:
    driver._authenticate_static_boundary()
    contract = _load(CONTRACT)
    assert maplight.sha256_path(CONTRACT) == driver.CONTRACT_SHA256
    assert maplight.sha256_path(driver.D129_REJECTION) == driver.D129_REJECTION_SHA256
    assert maplight.sha256_path(scoring.SCRIPT) == driver.SCORING_COMPILER_SHA256
    assert maplight.sha256_path(driver.OLD_DRIVER) == driver.OLD_DRIVER_SHA256
    assert contract["reused_scientific_primitive"]["sha256"] == (
        driver.SCORING_COMPILER_SHA256
    )


def test_new_driver_does_not_import_or_reactivate_old_driver() -> None:
    tree = ast.parse(driver.SCRIPT.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert (
        "run_global_v2_maplight_robustness_scoring_capability_acceptance"
        not in imports
    )
    old_text = driver.OLD_DRIVER.read_text(encoding="utf-8")
    assert "terminally consumed" in old_text


def test_fixed_root_is_deep_absent_and_preflight_is_noop() -> None:
    assert driver.FIXED_PARENT_ROOT == Path("/tmp/cypshift-g2-7f")
    assert driver.FIXED_WORK_ROOT == (
        Path("/tmp/cypshift-g2-7f/scoring-capability-attempt-1")
    )
    assert len(driver.FIXED_WORK_ROOT.parts) >= 4
    assert not driver.FIXED_PARENT_ROOT.exists()
    assert not driver.FIXED_WORK_ROOT.exists()
    assert not driver.ACCEPTANCE.exists()
    assert not driver.REJECTION.exists()
    driver._preflight()
    assert not driver.FIXED_PARENT_ROOT.exists()
    assert not driver.FIXED_WORK_ROOT.exists()


def test_shallow_cleanup_path_fails_without_creating_it() -> None:
    shallow = Path("/tmp/cypshift-g2-7f-shallow-test")
    assert not shallow.exists()
    with pytest.raises(no_fit_driver.NoFitAcceptanceError, match="unsafe"):
        driver._validate_cleanup_path(shallow)
    assert not shallow.exists()


def test_driver_accepts_no_root_or_output_override(capsys: pytest.CaptureFixture[str]) -> None:
    assert driver._main(["--work-root", "/tmp/alternate"]) == 2
    assert "accepts no root or output arguments" in capsys.readouterr().err
    assert not driver.FIXED_PARENT_ROOT.exists()
    assert not driver.FIXED_WORK_ROOT.exists()


def test_formal_chronology_preflights_before_creation_and_cleans_before_publish() -> None:
    source = inspect.getsource(driver.run_formal_attempt)
    assert source.index("_preflight()") < source.index("_create_work_root()")
    assert source.index("_create_work_root()") < source.index("_execute_two_roots()")
    assert source.index("_cleanup_work_root()") < source.index("_publish_terminal")
    assert source.index("creation_started = True") < source.index("_create_work_root()")


def test_preflight_failure_cannot_trigger_cleanup_of_an_unowned_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    def reject() -> None:
        events.append("preflight")
        raise driver.ScoringCapabilityReacceptanceError("expected preflight failure")

    def forbidden() -> None:
        events.append("forbidden")
        raise AssertionError("post-preflight mutation was reached")

    def publish(path: Path, terminal: dict[str, Any]) -> Path:
        events.append("publish")
        assert terminal["status"] == (
            "G2_7F_MAPLIGHT_ROBUSTNESS_SCORING_CAPABILITY_REJECTED"
        )
        return path

    monkeypatch.setattr(driver, "_preflight", reject)
    monkeypatch.setattr(driver, "_create_work_root", forbidden)
    monkeypatch.setattr(driver, "_cleanup_work_root", forbidden)
    monkeypatch.setattr(driver, "_publish_terminal", publish)
    terminal, success = driver.run_formal_attempt()
    assert terminal == driver.REJECTION
    assert success is False
    assert events == ["preflight", "publish"]


def test_fixture_preserves_counts_order_and_confirmatory_opacity() -> None:
    canonical = driver.direct_observation_bytes(reverse=False)
    reversed_rows = driver.direct_observation_bytes(reverse=True)
    canonical_lines = canonical.splitlines()
    reversed_lines = reversed_rows.splitlines()
    assert len(canonical_lines) == len(reversed_lines) == 4801
    assert canonical_lines[0] == reversed_lines[0]
    assert sorted(canonical_lines[1:]) == sorted(reversed_lines[1:])
    assert canonical_lines[1:] != reversed_lines[1:]
    opaque = 0
    for line in canonical_lines[1:]:
        _observation, molecule = scoring._direct_prefix(line)
        if int(molecule.rsplit("-", 1)[1]) >= 960:
            with pytest.raises(UnicodeDecodeError):
                line.decode("utf-8")
            opaque += 1
    assert opaque == 960


def test_v2_fixture_compiles_exact_minimal_capability(tmp_path: Path) -> None:
    model_source = no_fit_driver.publish_source(
        root=tmp_path / "model-source", reverse=False
    )
    model, scorer, preflight = capability_compiler.compile_capabilities(
        source_root=model_source,
        output_root=tmp_path / "d126-capabilities",
        mode="synthetic",
        expected_compiler_sha256=maplight.sha256_path(capability_compiler.SCRIPT),
    )
    direct_source = driver._publish_scoring_source(
        root=tmp_path / "scoring-source", reverse=False
    )
    capability = scoring.compile_scoring_capability(
        direct_source_root=direct_source,
        model_capability_root=model,
        scorer_capability_root=scorer,
        output_root=tmp_path / "scoring-capability",
        mode="synthetic",
        expected_compiler_sha256=driver.SCORING_COMPILER_SHA256,
    )
    assert preflight["status"] == "G2_7C_NO_FIT_PREFLIGHT_PASS"
    assert {path.name for path in capability.iterdir()} == {
        "manifest.json",
        "scoring_truth.csv",
    }
    manifest = capability_compiler._load_json(capability / "manifest.json")
    assert manifest["counts"] == {
        "all_endpoint_rows": 4800,
        "development_rows_decoded": 3840,
        "finite_development_point_rows_emitted": 3840,
        "tutorial_eligible_rows": 768,
        "confirmatory_rows_prefix_checked_suffix_opaque": 960,
        "confirmatory_value_fields_decoded": 0,
    }
    assert manifest["source_file_values"] == [scoring.DIRECT_SOURCE_FILE]
    assert manifest["real_catboost_fits"] == 0
    assert manifest["development_metric_evaluations"] == 0
    assert manifest["model_quality_authority"] is False
    assert manifest["claim_authority"] is False


def test_success_schema_keeps_zero_authority_and_exact_counts() -> None:
    terminal = driver._success_terminal(
        {
            "roots": [{"name": "root-a"}, {"name": "root-b"}],
            "scoring_capability_files_compared": 2,
            "scoring_capability_maps_byte_identical": True,
        }
    )
    assert terminal["status"] == (
        "G2_7F_MAPLIGHT_ROBUSTNESS_SCORING_CAPABILITY_ACCEPTED"
    )
    assert terminal["synthetic_endpoint_rows_opened"] == 9600
    assert terminal["synthetic_development_rows_decoded"] == 7680
    assert terminal["synthetic_scoring_rows_emitted"] == 7680
    assert terminal["confirmatory_rows_prefix_checked_suffix_opaque"] == 1920
    assert terminal["confirmatory_value_fields_decoded"] == 0
    assert terminal["real_catboost_fits"] == 0
    assert terminal["development_metric_evaluations"] == 0
    assert terminal["official_operations"] == 0
    assert terminal["claims_created"] == terminal["claims_consumed"] == 0
    assert terminal["model_quality_authority"] is False
    assert terminal["claim_authority"] is False


def test_formal_terminals_do_not_exist_before_integrated_attempt() -> None:
    assert not driver.ACCEPTANCE.exists()
    assert not driver.REJECTION.exists()
    assert not driver.FIXED_PARENT_ROOT.exists()
    assert not driver.FIXED_WORK_ROOT.exists()


def test_public_sources_contain_no_private_portal_result_fields() -> None:
    text = driver.SCRIPT.read_text(encoding="utf-8").lower()
    for forbidden in (
        "submission_name",
        "leaderboard_score",
        "leaderboard_rank",
        "remote_submission_id",
    ):
        assert forbidden not in text

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from cypshift.openadmet_transformation_publication import (
    TransformationPublicationResult,
)
from cypshift.openadmet_transformation_types import TransformationIntegrityError


def _runner() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "run_openadmet_r4_coverage.py"
    spec = importlib.util.spec_from_file_location("run_openadmet_r4_coverage", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _runtime() -> dict[str, object]:
    return {
        "python_version": "3.12.3",
        "rdkit_version": "2026.03.5",
        "platform": "Linux x86_64 CPU",
        "device": "CPU",
        "seed": 0,
        "code_commit": "a" * 40,
    }


def test_pre_input_refusal_opens_no_official_input_or_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _runner()
    calls: list[str] = []

    def refuse(_destination: Path, _receipt: str) -> dict[str, object]:
        calls.append("preflight")
        raise runner.R4RunnerError("refused")

    monkeypatch.setattr(runner, "_pre_input_gate", refuse)
    monkeypatch.setattr(
        runner,
        "_authenticate_official_inputs",
        lambda *_args: calls.append("official-read"),
    )
    with pytest.raises(runner.R4RunnerError, match="refused"):
        runner.run_official_r4(
            r2b_root=tmp_path / "r2b",
            r3a_root=tmp_path / "r3a",
            terminal_output=tmp_path / "terminal",
            expected_runner_sha256="a" * 64,
        )
    assert calls == ["preflight"]
    assert not list(tmp_path.glob(".r4-official-*"))
    assert not (tmp_path / "terminal").exists()


def test_success_path_is_causal_and_cleans_private_before_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _runner()
    calls: list[str] = []
    terminal = tmp_path / "terminal"
    paths = runner.OfficialPaths(*(tmp_path / str(name) for name in range(6)))
    bundle = SimpleNamespace(
        molecules=[None] * 4905,
        direct_availability=[None] * 19620,
        folds=[None] * 73575,
        episodes=[None] * 1818,
        input_receipts=[None] * 6,
        source_receipts=[None] * 5,
    )
    geometry = SimpleNamespace(episodes=[None] * 1818)
    support = object()
    serialization = SimpleNamespace(
        episode_transformations_csv=b"header\n" + b"row\n" * 1818
    )

    monkeypatch.setattr(runner, "_pre_input_gate", lambda *_args: _runtime())
    monkeypatch.setattr(runner, "_authenticate_official_inputs", lambda *_args: paths)

    def project(**kwargs: Any) -> None:
        calls.append("project")
        kwargs["output_directory"].mkdir()

    monkeypatch.setattr(runner, "project_openadmet_transformation_inputs", project)
    monkeypatch.setattr(
        runner,
        "load_transformation_projection",
        lambda _path: calls.append("consume") or bundle,
    )
    monkeypatch.setattr(
        runner,
        "compile_transformation_geometry",
        lambda _bundle: calls.append("geometry") or geometry,
    )
    monkeypatch.setattr(
        runner,
        "compile_transformation_support",
        lambda *_args: calls.append("support") or support,
    )
    monkeypatch.setattr(
        runner,
        "serialize_transformation_results",
        lambda *_args: calls.append("serialize") or serialization,
    )
    monkeypatch.setattr(
        runner, "_post_input_gate", lambda *_args: calls.append("post-gate")
    )

    def publish(**_kwargs: Any) -> TransformationPublicationResult:
        calls.append("publish")
        assert not list(tmp_path.glob(".r4-official-*"))
        return TransformationPublicationResult(
            terminal,
            "R4_TRANSFORMATION_COVERAGE_UNDERPOWERED",
            terminal / "manifest.json",
        )

    monkeypatch.setattr(runner, "publish_transformation_coverage", publish)
    result = runner.run_official_r4(
        r2b_root=tmp_path / "r2b",
        r3a_root=tmp_path / "r3a",
        terminal_output=terminal,
        expected_runner_sha256="a" * 64,
    )
    assert result.status == "R4_TRANSFORMATION_COVERAGE_UNDERPOWERED"
    assert calls == [
        "project",
        "consume",
        "geometry",
        "support",
        "serialize",
        "post-gate",
        "publish",
    ]


def test_post_gate_geometry_failure_publishes_only_v4_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _runner()
    terminal = tmp_path / "terminal"
    paths = runner.OfficialPaths(*(tmp_path / str(name) for name in range(6)))
    bundle = SimpleNamespace(
        molecules=[None] * 4905,
        direct_availability=[None] * 19620,
        folds=[None] * 73575,
        episodes=[None] * 1818,
        input_receipts=[None] * 6,
        source_receipts=[None] * 5,
    )
    observed: dict[str, Any] = {}
    monkeypatch.setattr(runner, "_pre_input_gate", lambda *_args: _runtime())
    monkeypatch.setattr(runner, "_authenticate_official_inputs", lambda *_args: paths)
    monkeypatch.setattr(
        runner,
        "project_openadmet_transformation_inputs",
        lambda **kwargs: kwargs["output_directory"].mkdir(),
    )
    monkeypatch.setattr(runner, "load_transformation_projection", lambda _path: bundle)
    monkeypatch.setattr(runner, "_post_input_gate", lambda *_args: None)
    monkeypatch.setattr(
        runner,
        "compile_transformation_geometry",
        lambda _bundle: (_ for _ in ()).throw(ValueError("defect")),
    )

    def publish_failure(**kwargs: Any) -> TransformationPublicationResult:
        observed.update(kwargs)
        assert not list(tmp_path.glob(".r4-official-*"))
        return TransformationPublicationResult(
            terminal,
            "R4_TRANSFORMATION_COVERAGE_FAILED",
            terminal / "failure_receipt.json",
        )

    monkeypatch.setattr(runner, "publish_transformation_failure", publish_failure)
    result = runner.run_official_r4(
        r2b_root=tmp_path / "r2b",
        r3a_root=tmp_path / "r3a",
        terminal_output=terminal,
        expected_runner_sha256="a" * 64,
    )
    assert result.status == "R4_TRANSFORMATION_COVERAGE_FAILED"
    assert observed["terminal_codes"] == ["V4"]


def test_cleanup_failure_refuses_every_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _runner()
    terminal = tmp_path / "terminal"
    paths = runner.OfficialPaths(*(tmp_path / str(name) for name in range(6)))
    bundle = SimpleNamespace(
        molecules=[None] * 4905,
        direct_availability=[None] * 19620,
        folds=[None] * 73575,
        episodes=[None] * 1818,
        input_receipts=[None] * 6,
        source_receipts=[None] * 5,
    )
    monkeypatch.setattr(runner, "_pre_input_gate", lambda *_args: _runtime())
    monkeypatch.setattr(runner, "_authenticate_official_inputs", lambda *_args: paths)
    monkeypatch.setattr(
        runner,
        "project_openadmet_transformation_inputs",
        lambda **kwargs: kwargs["output_directory"].mkdir(),
    )
    monkeypatch.setattr(runner, "load_transformation_projection", lambda _path: bundle)
    monkeypatch.setattr(
        runner,
        "compile_transformation_geometry",
        lambda _bundle: (_ for _ in ()).throw(ValueError("defect")),
    )
    monkeypatch.setattr(
        runner,
        "_remove_private",
        lambda _root: (_ for _ in ()).throw(OSError("cannot clean")),
    )
    monkeypatch.setattr(
        runner,
        "publish_transformation_failure",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("published")),
    )
    with pytest.raises(runner.R4RunnerError, match="refusing terminal"):
        runner.run_official_r4(
            r2b_root=tmp_path / "r2b",
            r3a_root=tmp_path / "r3a",
            terminal_output=terminal,
            expected_runner_sha256="a" * 64,
        )
    assert not terminal.exists()


def test_failure_code_mapping_preserves_all_terminal_codes() -> None:
    runner = _runner()
    defect = TransformationIntegrityError(("C1", "P6", "S2"))
    assert runner._failure_codes("geometry", defect) == {"C1", "P6"}
    assert runner._failure_codes("post_gate", ValueError()) == {"P1"}


def test_repository_receipt_mismatch_is_pre_input_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _runner()
    monkeypatch.setattr(runner, "_destination_preflight", lambda _path: None)
    monkeypatch.setattr(runner, "_runtime_preflight", lambda: None)
    monkeypatch.setattr(runner, "_renameat2_preflight", lambda: None)
    monkeypatch.setattr(runner, "_git_head_clean", lambda: "a" * 40)
    monkeypatch.setattr(runner, "_file_sha256", lambda _path: "0" * 64)
    with pytest.raises(runner.R4RunnerError, match="repository receipt differs"):
        runner._pre_input_gate(tmp_path / "terminal", "b" * 64)
    assert not (tmp_path / "terminal").exists()


def test_manifest_hash_is_checked_before_json_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _runner()
    path = tmp_path / "manifest.json"
    path.write_bytes(b'{"schema_version":"wrong"}\n')
    monkeypatch.setattr(
        runner,
        "strict_json_object",
        lambda *_args: (_ for _ in ()).throw(AssertionError("parsed early")),
    )
    with pytest.raises(runner.R4RunnerError, match="receipt differs"):
        runner._fixed_json(path, "f" * 64, "manifest")


def test_destination_must_be_fresh_and_outside_git(tmp_path: Path) -> None:
    runner = _runner()
    runner._destination_preflight(tmp_path / "fresh")
    existing = tmp_path / "existing"
    existing.write_bytes(b"keep")
    with pytest.raises(runner.R4RunnerError, match="not fresh"):
        runner._destination_preflight(existing)
    with pytest.raises(runner.R4RunnerError, match="outside Git"):
        runner._destination_preflight(runner.REPOSITORY_ROOT / "terminal")


def test_fixed_official_receipts_and_cli_surface() -> None:
    runner = _runner()
    assert runner.EXPECTED_COUNTS == {
        "direct_observations": 19620,
        "group_folds": 73575,
        "public_episodes": 1122,
        "masks": 1122,
        "structure": 4905,
    }
    parser = runner._parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--synthetic"])
    assert set(runner.EXPECTED_SOURCE_RECEIPTS) == {
        "direct_observations.csv",
        "group_folds.csv",
        "public_episodes.csv",
        "masks.csv",
        "structure.csv",
    }

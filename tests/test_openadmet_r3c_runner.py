"""Synthetic orchestration tests for the production-only R3C wrapper."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_openadmet_r3c.py"
spec = importlib.util.spec_from_file_location("r3c_runner_test", SCRIPT)
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


def _fixture_root(tmp_path: Path) -> tuple[Path, Path, Path]:
    direct = tmp_path / "direct.csv"
    folds = tmp_path / "folds.csv"
    feature = tmp_path / "features"
    direct.write_text("synthetic\n", encoding="utf-8")
    folds.write_text("synthetic\n", encoding="utf-8")
    feature.mkdir()
    return direct, folds, feature


def _terminal(root: Path, status: str) -> None:
    root.mkdir(parents=True)
    if status == "GLOBAL_FAILED":
        names = runner.TERMINAL_FILES[status]
        (root / "failure_receipt.json").write_text("{}\n", encoding="utf-8")
    else:
        (root / "global_result.json").write_text(
            json.dumps({"status": status}) + "\n", encoding="utf-8"
        )
        names = runner.TERMINAL_FILES[status]
    for name in names:
        path = root / name
        if not path.exists():
            path.write_bytes(b"synthetic\n")
    for path in root.iterdir():
        path.chmod(0o444)
    root.chmod(0o555)


def _mock_promotion(monkeypatch: pytest.MonkeyPatch) -> None:
    def promote(staged: Path, destination: Path) -> None:
        staged.parent.chmod(0o755)
        staged.rename(destination)

    monkeypatch.setattr(runner, "_promote_terminal", promote)


def _module(monkeypatch: pytest.MonkeyPatch, *, passed: bool) -> None:
    @dataclass(frozen=True)
    class Projection:
        model_public_root: Path
        scorer_sealed_root: Path
        model_public_manifest_sha256: str = "a" * 64
        sealed_truth_manifest_sha256: str = "b" * 64
        private_audit_sha256: str = "c" * 64

    def project(_direct: Path, _folds: Path, output: Path, **_: Any) -> Projection:
        public = output / "model-public"
        sealed = output / "scorer-sealed"
        public.mkdir(parents=True)
        sealed.mkdir()
        (public / "model_public_manifest.json").write_bytes(b"public\n")
        (public / "model_rows.csv").write_bytes(b"model\n")
        for endpoint in runner.ENDPOINTS:
            for repeat in range(3):
                for outer in range(5):
                    outer_target = (
                        public
                        / f"outer_targets/{endpoint}/repeat-{repeat}/outer-{outer}.csv"
                    )
                    outer_target.parent.mkdir(parents=True, exist_ok=True)
                    outer_target.write_bytes(b"target\n")
                    for inner in range(4):
                        inner_target = (
                            public
                            / f"inner_targets/{endpoint}/repeat-{repeat}/outer-{outer}/"
                            f"inner-{inner}.csv"
                        )
                        inner_target.parent.mkdir(parents=True, exist_ok=True)
                        inner_target.write_bytes(b"target\n")
        (sealed / "sealed_truth_manifest.json").write_bytes(b"sealed\n")
        return Projection(public, sealed)

    def preflight(_projection: Path, *, output_path: Path, **_: Any) -> Any:
        receipt = {"passed": passed}
        output_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
        return types.SimpleNamespace(receipt=receipt)

    fake = types.ModuleType("cypshift.openadmet_global_projection")
    fake.project_openadmet_global_targets = project  # type: ignore[attr-defined]
    fake.preflight_openadmet_global_targets = preflight  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cypshift.openadmet_global_projection", fake)


def test_destinations_reject_existing_symlink_and_nesting(tmp_path: Path) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(runner.R3CRunnerError, match="already exists"):
        runner._validate_destinations(existing, tmp_path / "terminal")
    nested = tmp_path / "private"
    with pytest.raises(runner.R3CRunnerError, match="nested"):
        runner._validate_destinations(nested, nested / "terminal")
    with pytest.raises(runner.R3CRunnerError, match="parent traversal"):
        runner._validate_destinations(
            tmp_path / "alias/../private",
            tmp_path / "private/terminal",
        )
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "missing", target_is_directory=True)
    with pytest.raises(runner.R3CRunnerError, match="already exists"):
        runner._validate_destinations(link, tmp_path / "terminal")


def test_cell_plan_is_single_context_and_has_no_escape_flags() -> None:
    command = runner._cell_command(
        stage="inner",
        endpoint="CYP3A4",
        repeat=1,
        outer=2,
        inner=3,
        feature_root=Path("features"),
        feature_manifest_sha256="a" * 64,
        public_root=Path("public"),
        public_manifest_sha256="b" * 64,
        preflight=Path("preflight.json"),
        output=Path("cell"),
        token=Path("token"),
    )
    assert command[:3] == [str(runner.RESEARCH_PYTHON), str(runner.CELL_RUNNER), "cell"]
    assert command.count("--stage") == 1
    assert "--synthetic" not in command
    assert "--resume" not in command
    assert command[command.index("--inner-fold") + 1] == "3"
    assert command[command.index("--expected-source-bundle-sha256") + 1] == (
        runner.CELL_SOURCE_SHA256
    )


def test_public_views_expose_only_selected_target_and_cleanup_preserves_source_mode(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "model_public_manifest.json").write_bytes(b"manifest\n")
    (source / "model_rows.csv").write_bytes(b"rows\n")
    selected = source / "outer_targets/CYP3A4/repeat-0/outer-0.csv"
    selected.parent.mkdir(parents=True)
    selected.write_bytes(b"selected\n")
    unselected = source / "outer_targets/CYP3A4/repeat-0/outer-1.csv"
    unselected.write_bytes(b"unselected\n")
    for path in source.rglob("*"):
        path.chmod(0o555 if path.is_dir() else 0o444)
    source.chmod(0o555)
    private = tmp_path / "private"
    view = runner._public_view(
        source,
        private / "view",
        "outer_targets/CYP3A4/repeat-0/outer-0.csv",
    )
    assert (view / selected.relative_to(source)).is_file()
    assert not (view / unselected.relative_to(source)).exists()
    assert not any(path.stat().st_mode & 0o222 for path in view.rglob("*"))
    runner._cleanup_private(private)
    assert source.is_dir()
    assert all(not (path.stat().st_mode & 0o222) for path in source.rglob("*"))


def test_terminal_promotion_uses_staged_destination_and_research_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], str]] = []

    def fake(command: list[str], stage: str) -> None:
        calls.append((command, stage))

    monkeypatch.setattr(runner, "_subprocess", fake)
    runner._promote_terminal(Path("staged"), Path("terminal"))
    assert len(calls) == 1
    command, stage = calls[0]
    assert stage == "terminal promotion"
    assert command[:2] == [str(runner.RESEARCH_PYTHON), "-c"]
    assert command[3:] == ["staged", "terminal", str(runner.RESEARCH_ROOT)]


def test_gate_runs_before_official_input_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _direct, _folds, feature = _fixture_root(tmp_path)
    called: list[str] = []
    monkeypatch.setattr(
        runner,
        "_gate_runtime_and_sources",
        lambda *_: (_ for _ in ()).throw(runner.R3CRunnerError("gate")),
    )
    monkeypatch.setattr(runner, "_input_gate", lambda *_: called.append("input"))
    with pytest.raises(runner.R3CRunnerError, match="gate"):
        runner.run_experiment(
            direct_observations=tmp_path / "unopened-direct.csv",
            group_folds=tmp_path / "unopened-folds.csv",
            feature_root=feature,
            private_run_root=tmp_path / "private",
            terminal_output=tmp_path / "terminal",
            expected_runner_sha256="a" * 64,
        )
    assert called == []


def test_underpowered_publishes_two_files_and_runs_zero_cells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    direct, folds, feature = _fixture_root(tmp_path)
    _module(monkeypatch, passed=False)
    _mock_promotion(monkeypatch)
    monkeypatch.setattr(runner, "_gate_runtime_and_sources", lambda *_: None)
    calls: list[list[str]] = []

    def fake(command: list[str], _stage: str) -> None:
        calls.append(command)
        if str(runner.SCORER) in command:
            _terminal(
                Path(command[command.index("--output-root") + 1]), "GLOBAL_UNDERPOWERED"
            )

    monkeypatch.setattr(runner, "_subprocess", fake)
    result = runner.run_experiment(
        direct_observations=direct,
        group_folds=folds,
        feature_root=feature,
        private_run_root=tmp_path / "private",
        terminal_output=tmp_path / "terminal",
        expected_runner_sha256="a" * 64,
    )
    assert result.status == "GLOBAL_UNDERPOWERED"
    assert len(calls) == 1
    assert not (tmp_path / "private").exists()
    assert set(path.name for path in (tmp_path / "terminal").iterdir()) == {
        "global_result.json",
        "manifest.json",
    }


def test_outer_no_advantage_stops_before_inner_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    direct, folds, feature = _fixture_root(tmp_path)
    _module(monkeypatch, passed=True)
    _mock_promotion(monkeypatch)
    monkeypatch.setattr(runner, "_gate_runtime_and_sources", lambda *_: None)
    calls: list[list[str]] = []

    def fake(command: list[str], _stage: str) -> None:
        calls.append(command)
        if str(runner.CELL_RUNNER) in command and "cell" in command:
            Path(command[command.index("--output-root") + 1]).mkdir(parents=True)
        elif "freeze-outer" in command:
            output = Path(command[command.index("--output-root") + 1])
            output.mkdir(parents=True)
            (output / "global_oof_freeze_manifest.json").write_bytes(b"freeze\n")
        elif str(runner.SCORER) in command:
            _terminal(
                Path(command[command.index("--output-root") + 1]), "GLOBAL_NO_ADVANTAGE"
            )

    monkeypatch.setattr(runner, "_subprocess", fake)
    result = runner.run_experiment(
        direct_observations=direct,
        group_folds=folds,
        feature_root=feature,
        private_run_root=tmp_path / "private",
        terminal_output=tmp_path / "terminal",
        expected_runner_sha256="a" * 64,
    )
    assert result.status == "GLOBAL_NO_ADVANTAGE"
    assert (
        sum(
            1
            for command in calls
            if str(runner.CELL_RUNNER) in command and "cell" in command
        )
        == 60
    )
    assert not any("inner-fold" in command for command in calls)
    assert not (tmp_path / "private").exists()


def test_expert_plan_is_outer_freeze_score_inner_freeze_final(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    direct, folds, feature = _fixture_root(tmp_path)
    _module(monkeypatch, passed=True)
    _mock_promotion(monkeypatch)
    monkeypatch.setattr(runner, "_gate_runtime_and_sources", lambda *_: None)
    calls: list[list[str]] = []

    def fake(command: list[str], _stage: str) -> None:
        calls.append(command)
        if str(runner.CELL_RUNNER) in command and "cell" in command:
            output = Path(command[command.index("--output-root") + 1])
            output.mkdir(parents=True)
        elif "freeze-outer" in command or "freeze-inner" in command:
            output = Path(command[command.index("--output-root") + 1])
            output.mkdir(parents=True)
            name = (
                "global_oof_freeze_manifest.json"
                if "freeze-outer" in command
                else "global_inner_oof_freeze_manifest.json"
            )
            (output / name).write_bytes(b"freeze\n")
        elif str(runner.SCORER) in command:
            output = Path(command[command.index("--output-root") + 1])
            if "outer" in command[command.index(str(runner.SCORER)) + 1 :]:
                stage = Path(command[command.index("--stage-root") + 1])
                stage.mkdir(parents=True)
                (stage / "inner_selection_token.json").write_bytes(b"token\n")
                return
            _terminal(output, "GLOBAL_EXPERT_FROZEN")

    monkeypatch.setattr(runner, "_subprocess", fake)
    result = runner.run_experiment(
        direct_observations=direct,
        group_folds=folds,
        feature_root=feature,
        private_run_root=tmp_path / "private",
        terminal_output=tmp_path / "terminal",
        expected_runner_sha256="a" * 64,
    )
    assert result.status == "GLOBAL_EXPERT_FROZEN"
    cells = [
        command
        for command in calls
        if str(runner.CELL_RUNNER) in command and "cell" in command
    ]
    assert len(cells) == 300
    assert sum("--inner-fold" in command for command in cells) == 240
    stages = [
        command[2]
        for command in calls
        if len(command) > 2
        and (
            command[2] in {"freeze-outer", "freeze-inner"}
            or str(runner.SCORER) in command
        )
    ]
    assert stages == ["freeze-outer", "outer", "freeze-inner", "final"]
    assert not (tmp_path / "private").exists()


def test_post_start_failure_publishes_failure_and_cleans_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    direct, folds, feature = _fixture_root(tmp_path)
    _module(monkeypatch, passed=True)
    _mock_promotion(monkeypatch)
    monkeypatch.setattr(runner, "_gate_runtime_and_sources", lambda *_: None)
    monkeypatch.setattr(
        runner,
        "_subprocess",
        lambda *_: (_ for _ in ()).throw(runner.R3CRunnerError("cell failed")),
    )
    published: list[tuple[Path, str]] = []

    def publish(output: Path, stage: str, _message: str) -> None:
        published.append((output, stage))
        _terminal(output, "GLOBAL_FAILED")

    monkeypatch.setattr(runner, "_publish_failure", publish)
    with pytest.raises(runner.R3CRunnerError, match="cell failed"):
        runner.run_experiment(
            direct_observations=direct,
            group_folds=folds,
            feature_root=feature,
            private_run_root=tmp_path / "private",
            terminal_output=tmp_path / "terminal",
            expected_runner_sha256="a" * 64,
        )
    assert published == [(tmp_path / ".terminal.r3c-staged", "outer_model")]
    assert (tmp_path / "terminal/failure_receipt.json").is_file()
    assert not (tmp_path / "private").exists()


@pytest.mark.parametrize(
    ("missing_stage", "expected_stage"),
    (("outer", "outer_freeze"), ("inner", "inner_freeze")),
)
def test_missing_freeze_manifest_keeps_freeze_failure_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing_stage: str,
    expected_stage: str,
) -> None:
    direct, folds, feature = _fixture_root(tmp_path)
    _module(monkeypatch, passed=True)
    _mock_promotion(monkeypatch)
    monkeypatch.setattr(runner, "_gate_runtime_and_sources", lambda *_: None)

    def fake(command: list[str], _stage: str) -> None:
        output = Path(command[command.index("--output-root") + 1])
        if str(runner.CELL_RUNNER) in command and "cell" in command:
            output.mkdir(parents=True)
        elif "freeze-outer" in command:
            output.mkdir(parents=True)
            if missing_stage != "outer":
                (output / "global_oof_freeze_manifest.json").write_bytes(b"freeze\n")
        elif "freeze-inner" in command:
            output.mkdir(parents=True)
        elif str(runner.SCORER) in command:
            stage = Path(command[command.index("--stage-root") + 1])
            stage.mkdir(parents=True)
            (stage / "inner_selection_token.json").write_bytes(b"token\n")

    monkeypatch.setattr(runner, "_subprocess", fake)
    published: list[str] = []

    def publish(output: Path, stage: str, _message: str) -> None:
        published.append(stage)
        _terminal(output, "GLOBAL_FAILED")

    monkeypatch.setattr(runner, "_publish_failure", publish)
    with pytest.raises(runner.R3CRunnerError):
        runner.run_experiment(
            direct_observations=direct,
            group_folds=folds,
            feature_root=feature,
            private_run_root=tmp_path / "private",
            terminal_output=tmp_path / "terminal",
            expected_runner_sha256="a" * 64,
        )
    assert published == [expected_stage]


def test_recovery_failure_is_not_silently_swallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    direct, folds, feature = _fixture_root(tmp_path)
    _module(monkeypatch, passed=True)
    monkeypatch.setattr(runner, "_gate_runtime_and_sources", lambda *_: None)
    monkeypatch.setattr(
        runner,
        "_subprocess",
        lambda *_: (_ for _ in ()).throw(runner.R3CRunnerError("cell failed")),
    )
    monkeypatch.setattr(
        runner,
        "_publish_failure",
        lambda *_: (_ for _ in ()).throw(RuntimeError("publish failed")),
    )
    with pytest.raises(runner.R3CRunnerError, match="failure publication failed"):
        runner.run_experiment(
            direct_observations=direct,
            group_folds=folds,
            feature_root=feature,
            private_run_root=tmp_path / "private",
            terminal_output=tmp_path / "terminal",
            expected_runner_sha256="a" * 64,
        )

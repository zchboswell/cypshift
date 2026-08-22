from __future__ import annotations

import json
import os
import platform
import stat
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest
from r5c_supported_fixture import supported_fixture
from test_openadmet_oracle_projection import _fixture as _projection_fixture
from test_openadmet_oracle_source import _fixture

from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS
from cypshift.openadmet_oracle_private_io import publish_readonly_tree
from cypshift.openadmet_oracle_projection import project_openadmet_oracle_inputs
from cypshift.openadmet_oracle_runner import (
    OracleProcessFailure,
    SyntheticRunInput,
    _Coordinator,
    _model_subprocess_environment,
    _publish_late_failure,
    run_synthetic_oracle,
)
from cypshift.openadmet_oracle_runner_commands import (
    PAIR_PYTHON,
    PAIR_SCRIPT,
    PairTask,
    g0_command,
    inner_pair_tasks,
    outer_pair_tasks,
    pair_command,
)
from cypshift.openadmet_oracle_sealed import SEALED_FILES
from cypshift.openadmet_oracle_source import compile_openadmet_oracle_source
from cypshift.openadmet_oracle_terminal_io import (
    TERMINAL_SOURCE_FILES,
    failure_source_bundle_sha256,
    terminal_source_bundle_sha256,
)
from cypshift.openadmet_oracle_validation import (
    CLIFF_COLUMNS,
    PUBLIC_QUERY_COLUMNS,
    csv_rows,
)
from cypshift.openadmet_oracle_worker import VERBS

pytestmark = pytest.mark.skipif(
    sys.version_info[:3] != (3, 12, 3)
    or platform.system() != "Linux"
    or platform.machine() != "x86_64",
    reason="requires the exact R5C root runtime",
)

TEST_COMMIT_OID = "1" * 40
ROOT = Path(__file__).resolve().parents[1]


def _input(
    source_paths: dict[str, Path],
    receipts: dict[str, str],
    private: Path,
    terminal: Path,
    commit_oid: str = TEST_COMMIT_OID,
) -> SyntheticRunInput:
    return SyntheticRunInput(
        source_paths,
        receipts,
        private,
        terminal,
        commit_oid,
        terminal_source_bundle_sha256(),
        failure_source_bundle_sha256(),
    )


def _entry_config(tmp_path: Path) -> dict[str, object]:
    paths, receipts = _fixture(tmp_path / "entry-inputs")
    commit_oid = subprocess.run(
        ("git", "rev-parse", "--verify", "HEAD"),
        cwd=ROOT,
        env={"PATH": os.defpath, "LANG": "C", "LC_ALL": "C"},
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {
        "commit_oid": commit_oid,
        "expected_failure_source_sha256": failure_source_bundle_sha256(),
        "expected_terminal_source_sha256": terminal_source_bundle_sha256(),
        "private_root": str(tmp_path / "entry-private"),
        "schema_version": "cypshift.openadmet_cyp_2026.r5c_synthetic_run_config.v1",
        "source_paths": {name: str(path) for name, path in paths.items()},
        "source_receipts": receipts,
        "terminal_root": str(tmp_path / "entry-terminal"),
    }


def _run_entry(
    tmp_path: Path,
    config: dict[str, object],
    *,
    python: Path = PAIR_PYTHON,
    environment: dict[str, str] | None = None,
    runner_sha256: str | None = None,
) -> subprocess.CompletedProcess[str]:
    config_path = tmp_path / "entry-config.json"
    config_path.write_text(
        json.dumps(config, sort_keys=True, separators=(",", ":")) + "\n"
    )
    script = ROOT / "scripts/run_openadmet_r5c.py"
    return subprocess.run(
        (
            str(python),
            str(script),
            "--config",
            str(config_path),
            "--expected-runner-sha256",
            runner_sha256 or sha256(script.read_bytes()).hexdigest(),
        ),
        cwd=ROOT,
        env=environment
        or {
            "PATH": os.defpath,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        },
        check=False,
        capture_output=True,
        text=True,
    )


def _assert_bootstrap_failure(
    tmp_path: Path, completed: subprocess.CompletedProcess[str]
) -> None:
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout.splitlines()[0])
    assert result["status"] == "R5_ORACLE_FAILED"
    assert result["processes"] == []
    terminal = tmp_path / "entry-terminal"
    failure_path = terminal / "failure.json"
    failure = json.loads(failure_path.read_text())
    assert failure["stage"] == "pre_gate"
    assert failure["operation_accounting"] == dict.fromkeys(
        failure["operation_accounting"], 0
    )
    assert (
        failure_path.read_bytes()
        == (json.dumps(failure, sort_keys=True, separators=(",", ":")) + "\n").encode()
    )
    assert stat.S_IMODE(terminal.stat().st_mode) == 0o555
    assert stat.S_IMODE(failure_path.stat().st_mode) == 0o444
    assert not (tmp_path / "entry-private").exists()
    assert not tuple(tmp_path.glob(".r5c-bootstrap-*"))


def test_exact_pair_process_topology() -> None:
    assert "cliff-witness" not in VERBS
    inner = inner_pair_tasks()
    assert len(inner) == 960
    assert sum(item.system_id == "C3" for item in inner) == 240
    selected = {
        (system, repeat, outer): (
            (None, 2.0) if system in {"A0", "A1"} else (1.0, None)
        )
        for system in ("C2", "C3", "T0", "A0", "A1", "A2")
        for repeat in range(3)
        for outer in range(5)
    }
    selected.update(
        {
            (system, repeat, outer): (1.0, 2.0)
            for system in ("C3", "T0")
            for repeat in range(3)
            for outer in range(5)
        }
    )
    outer = outer_pair_tasks(selected)
    assert len(outer) == 135
    assert sum(item.shared_outer_t0 for item in outer) == 15
    assert sum(3 if item.shared_outer_t0 else 1 for item in outer) == 165
    assert 3 + 75 + 75 + 390 + 390 + len(inner) + 1 + len(outer) + 4 == 2033


def test_terminal_source_closure_binds_direct_runner_stages() -> None:
    required = {
        "scripts/run_openadmet_r5c.py",
        "src/cypshift/openadmet_oracle_inner.py",
        "src/cypshift/openadmet_oracle_source.py",
        "src/cypshift/openadmet_oracle_source_io.py",
        "src/cypshift/openadmet_oracle_worker.py",
    }
    assert required.issubset(TERMINAL_SOURCE_FILES)


def test_real_worker_migrate_returns_exact_sealed_root(tmp_path: Path) -> None:
    source, receipts = _projection_fixture(tmp_path / "fixture")
    projection = project_openadmet_oracle_inputs(
        source, tmp_path / "projection", expected_receipts=receipts
    )
    for path in source.iterdir():
        path.chmod(0o444)
    source.chmod(0o555)
    v2 = projection.sealed_scorer_root / "inner/repeat-0/outer-0/inner-0"
    output = tmp_path / "private/sealed-v3/inner/repeat-0/outer-0/inner-0"
    output.parent.mkdir(parents=True)
    meta = tmp_path / "control"
    meta.mkdir()
    coordinator = _Coordinator(tmp_path / "private", meta)
    result = coordinator.worker(
        "migrate",
        {
            "v2_root": str(v2),
            "source_root": str(source),
            "output_root": str(output),
            "v2_manifest_sha256": sha256(
                (v2 / "manifest.json").read_bytes()
            ).hexdigest(),
            "source_manifest_sha256": receipts["manifest.json"],
            "scope": {
                "stage": "inner",
                "repeat": 0,
                "outer_fold": 0,
                "inner_fold": 0,
            },
        },
    )
    assert result["root"] == str(output)
    assert set(path.name for path in output.iterdir()) == set(SEALED_FILES)
    assert (
        result["manifest_sha256"]
        == sha256((output / "manifest.json").read_bytes()).hexdigest()
    )


def test_real_worker_episodes_enumerates_only_cell_target(tmp_path: Path) -> None:
    source, receipts = _projection_fixture(tmp_path / "fixture")
    projection = project_openadmet_oracle_inputs(
        source, tmp_path / "projection", expected_receipts=receipts
    )
    for path in source.iterdir():
        path.chmod(0o444)
    source.chmod(0o555)
    relative = Path("inner/repeat-0/outer-0/inner-0")
    target = projection.cell_target_root / relative
    c3_target = projection.c3_target_root / relative
    model = projection.model_public_root
    meta = tmp_path / "control"
    meta.mkdir()
    coordinator = _Coordinator(tmp_path / "private", meta)
    payload = {
        "model_root": str(model),
        "model_manifest_sha256": sha256(
            (model / "manifest.json").read_bytes()
        ).hexdigest(),
        "target_root": str(target),
        "target_manifest_sha256": sha256(
            (target / "manifest.json").read_bytes()
        ).hexdigest(),
        "scope": {
            "stage": "inner",
            "repeat": 0,
            "outer_fold": 0,
            "inner_fold": 0,
        },
    }
    result = coordinator.worker("episodes", payload)
    expected = sorted(
        {
            row.split(",", 1)[0]
            for row in (target / "episode_anchor_contexts.csv")
            .read_text(encoding="utf-8")
            .splitlines()[1:]
        }
    )
    assert result == {"episode_ids": expected}
    with pytest.raises(OracleProcessFailure):
        coordinator.worker(
            "episodes",
            {
                **payload,
                "target_root": str(c3_target),
                "target_manifest_sha256": sha256(
                    (c3_target / "manifest.json").read_bytes()
                ).hexdigest(),
            },
        )
    assert [record.returncode for record in coordinator.processes] == [0, 1]


def test_supported_fixture_projects_nonempty_primary_outer_cliffs(
    tmp_path: Path,
) -> None:
    inputs, input_receipts = supported_fixture(tmp_path / "inputs")
    source = compile_openadmet_oracle_source(
        inputs,
        tmp_path / "source",
        expected_receipts=input_receipts,
    )
    source_receipts = {
        name: record["sha256"] for name, record in source.output_receipts.items()
    }
    source_receipts["manifest.json"] = source.manifest_sha256
    projection = project_openadmet_oracle_inputs(
        source.output_directory,
        tmp_path / "projection",
        expected_receipts=source_receipts,
    )
    public_rows = csv_rows(
        (projection.model_public_root / "public_episode_queries.csv").read_bytes(),
        PUBLIC_QUERY_COLUMNS,
        "test public queries",
    )
    public = {(row["episode_id"], row["query_molecule_id"]): row for row in public_rows}
    primary_cliffs = 0
    for repeat in range(3):
        for outer in range(5):
            rows = csv_rows(
                (
                    projection.sealed_scorer_root
                    / f"outer/repeat-{repeat}/outer-{outer}/activity_cliffs.csv"
                ).read_bytes(),
                CLIFF_COLUMNS,
                "test outer cliffs",
            )
            primary_cliffs += sum(
                row["activity_cliff"] == "true"
                and public[(row["episode_id"], row["query_molecule_id"])][
                    "episode_policy_id"
                ]
                == "selected_anchor"
                for row in rows
            )
    assert primary_cliffs > 0


def test_argv_capabilities_are_stage_minimal(tmp_path: Path) -> None:
    digest = "a" * 64
    g0 = g0_command(
        model_root=tmp_path / "model",
        model_manifest_sha256=digest,
        view_root=tmp_path / "view",
        view_manifest_sha256=digest,
        g0_source_sha256=digest,
        view_source_sha256=digest,
        target_manifest_sha256=digest,
        output_root=tmp_path / "g0",
    )
    joined = " ".join(g0)
    assert "sealed-scorer" not in joined
    assert "episode_truth.csv" not in joined
    assert "activity_cliffs.csv" not in joined
    inner = pair_command(
        PairTask("inner", 0, 0, 0, "C2", 1.0, None),
        model_root=tmp_path / "model",
        model_manifest_sha256=digest,
        target_root=tmp_path / "target",
        target_manifest_sha256=digest,
        g0_roots=(tmp_path / "g0",),
        g0_manifest_sha256=(digest,),
        source_sha256=digest,
        output_root=tmp_path / "fragment",
    )
    assert "--selection-token-root" not in inner
    assert inner[inner.index("--target-kind") + 1] == "cell-target"
    assert "--upstream-candidate-receipt-sha256" not in inner
    assert "--expected-g0-source-cell-target-manifest-sha256" not in inner
    c3 = pair_command(
        PairTask("inner", 0, 0, 0, "C3", 1.0, 2.0),
        model_root=tmp_path / "model",
        model_manifest_sha256=digest,
        target_root=tmp_path / "target",
        target_manifest_sha256=digest,
        g0_roots=(tmp_path / "g0",),
        g0_manifest_sha256=(digest,),
        source_sha256=digest,
        output_root=tmp_path / "fragment-c3",
        measured_parent_sha256=digest,
    )
    assert c3[c3.index("--target-kind") + 1] == "c3-target"
    with pytest.raises(ValueError, match="shared T0"):
        pair_command(
            PairTask("outer", 0, 0, None, "T0", 1.0, 2.0, True),
            model_root=tmp_path / "model",
            model_manifest_sha256=digest,
            target_root=tmp_path / "target",
            target_manifest_sha256=digest,
            g0_roots=(tmp_path / "g0",),
            g0_manifest_sha256=(digest,),
            source_sha256=digest,
            output_root=tmp_path / "fragment",
        )


def test_pair_runner_fresh_root_runtime_import_and_argparse() -> None:
    completed = subprocess.run(
        (str(PAIR_PYTHON), str(PAIR_SCRIPT), "--help"),
        cwd=PAIR_SCRIPT.parents[2],
        env=_model_subprocess_environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--target-kind {cell-target,c3-target}" in completed.stdout
    assert completed.args[0] == str(PAIR_PYTHON)


def test_generated_pair_argv_reaches_runner_after_argparse(tmp_path: Path) -> None:
    digest = "a" * 64
    command = pair_command(
        PairTask("inner", 0, 0, 0, "C2", 1.0, None),
        model_root=tmp_path / "model",
        model_manifest_sha256=digest,
        target_root=tmp_path / "target",
        target_manifest_sha256=digest,
        g0_roots=(tmp_path / "g0",),
        g0_manifest_sha256=(digest,),
        source_sha256=digest,
        output_root=tmp_path / "fragment",
    )
    completed = subprocess.run(
        command,
        cwd=PAIR_SCRIPT.parents[2],
        env=_model_subprocess_environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert "pair runner source bundle receipt differs" in completed.stderr
    assert "required: --target-kind" not in completed.stderr


def test_entry_bootstrap_publishes_failed_on_actual_runtime_drift(
    tmp_path: Path,
) -> None:
    config = _entry_config(tmp_path)
    fake = tmp_path / "fake-distributions"
    for distribution, version in (
        ("numpy", "2.5.2"),
        ("scikit_learn", "1.9.0"),
        ("rdkit", "2026.3.5"),
    ):
        metadata = fake / f"{distribution}-{version}.dist-info/METADATA"
        metadata.parent.mkdir(parents=True)
        metadata.write_text(
            f"Metadata-Version: 2.1\nName: {distribution}\nVersion: {version}\n"
        )
    config_path = tmp_path / "entry-config.json"
    config_path.write_text(
        json.dumps(config, sort_keys=True, separators=(",", ":")) + "\n"
    )
    script = ROOT / "scripts/run_openadmet_r5c.py"
    probe = """
import importlib.metadata, importlib.util, json, os, pathlib, sys
fake = pathlib.Path(os.environ["PYTHONPATH"]).resolve()
script = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("r5c_entry", script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.argv = [str(script), "--config", sys.argv[2], "--expected-runner-sha256", sys.argv[3]]
module.main()
try:
    version = importlib.metadata.version("numpy")
except importlib.metadata.PackageNotFoundError:
    version = "ABSENT"
print(json.dumps({"fake_on_sys_path": str(fake) in sys.path, "numpy": version}, sort_keys=True))
"""
    completed = subprocess.run(
        (
            "/usr/bin/python3",
            "-c",
            probe,
            str(script),
            str(config_path),
            sha256(script.read_bytes()).hexdigest(),
        ),
        cwd=ROOT,
        env={
            "PATH": os.defpath,
            "PYTHONPATH": str(fake),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        },
        check=False,
        capture_output=True,
        text=True,
    )
    _assert_bootstrap_failure(tmp_path, completed)
    probe_result = json.loads(completed.stdout.splitlines()[1])
    assert probe_result == {"fake_on_sys_path": False, "numpy": "ABSENT"}


def test_entry_bootstrap_publishes_failed_on_failure_source_drift(
    tmp_path: Path,
) -> None:
    config = _entry_config(tmp_path)
    config["expected_failure_source_sha256"] = "0" * 64
    completed = _run_entry(tmp_path, config)
    _assert_bootstrap_failure(tmp_path, completed)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("schema_version", "wrong-schema"),
        ("source_paths", []),
        ("source_receipts", {"unexpected": "0" * 64}),
    ),
)
def test_entry_bootstrap_publishes_failed_on_invalid_config_shape(
    tmp_path: Path, field: str, value: object
) -> None:
    config = _entry_config(tmp_path)
    config[field] = value
    completed = _run_entry(tmp_path, config)
    _assert_bootstrap_failure(tmp_path, completed)


def test_entry_checkout_ignores_hostile_git_environment(tmp_path: Path) -> None:
    config = _entry_config(tmp_path)
    config["commit_oid"] = "0" * 40
    hostile = tmp_path / "hostile-bin"
    hostile.mkdir()
    marker = tmp_path / "fake-git-ran"
    fake_git = hostile / "git"
    fake_git.write_text(f"#!/bin/sh\ntouch {marker}\nexit 0\n")
    fake_git.chmod(0o755)
    environment = {
        "PATH": str(hostile),
        "GIT_DIR": str(tmp_path / "hostile-git-dir"),
        "GIT_WORK_TREE": str(tmp_path),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    completed = _run_entry(tmp_path, config, environment=environment)
    _assert_bootstrap_failure(tmp_path, completed)
    assert not marker.exists()


def test_entry_bad_self_hash_refuses_without_terminal(tmp_path: Path) -> None:
    config = _entry_config(tmp_path)
    completed = _run_entry(tmp_path, config, runner_sha256="0" * 64)
    assert completed.returncode != 0
    assert not (tmp_path / "entry-terminal").exists()
    assert not (tmp_path / "entry-private").exists()


def test_entry_script_rejects_hostile_pythonpath_and_uses_repo_modules(
    tmp_path: Path,
) -> None:
    hostile = tmp_path / "hostile"
    package = hostile / "cypshift"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("raise RuntimeError('hostile import')\n")
    private = tmp_path / "entry-private"
    terminal = tmp_path / "entry-terminal"
    config = {
        "commit_oid": "0" * 40,
        "expected_failure_source_sha256": failure_source_bundle_sha256(),
        "expected_terminal_source_sha256": terminal_source_bundle_sha256(),
        "private_root": str(private),
        "schema_version": "cypshift.openadmet_cyp_2026.r5c_synthetic_run_config.v1",
        "source_paths": {},
        "source_receipts": {},
        "terminal_root": str(terminal),
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(config, sort_keys=True, separators=(",", ":")) + "\n"
    )
    script = ROOT / "scripts/run_openadmet_r5c.py"
    completed = subprocess.run(
        (
            str(PAIR_PYTHON),
            str(script),
            "--config",
            str(config_path),
            "--expected-runner-sha256",
            sha256(script.read_bytes()).hexdigest(),
        ),
        cwd=ROOT,
        env={
            "PATH": os.defpath,
            "PYTHONPATH": str(hostile),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        },
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "R5_ORACLE_FAILED"
    assert not private.exists()
    assert (terminal / "failure.json").is_file()


def test_fresh_underpowered_state_machine_is_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "cypshift.openadmet_oracle_runner._validate_checkout", lambda _oid: None
    )
    terminals: list[bytes] = []
    for run in range(2):
        source_paths, receipts = _fixture(tmp_path / f"inputs-{run}")
        terminal = tmp_path / f"terminal-{run}"
        result = run_synthetic_oracle(
            _input(source_paths, receipts, tmp_path / f"private-{run}", terminal)
        )
        assert result.status == "R5_ORACLE_UNDERPOWERED"
        assert [item.verb for item in result.processes] == [
            "source",
            "project",
            "support",
            "cleanup",
            "underpowered",
        ]
        assert all(item.pid > 0 and item.returncode == 0 for item in result.processes)
        terminals.append(
            b"".join(
                path.name.encode() + b"\0" + path.read_bytes()
                for path in sorted(terminal.iterdir())
            )
        )
    assert terminals[0] == terminals[1]


def test_prefit_process_failure_purges_private_tree_and_publishes_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "cypshift.openadmet_oracle_runner._validate_checkout", lambda _oid: None
    )
    source_paths, receipts = _fixture(tmp_path / "inputs-failed")
    receipts["training_pairs.csv"] = "0" * 64
    private = tmp_path / "private-failed"
    terminal = tmp_path / "terminal-failed"
    result = run_synthetic_oracle(_input(source_paths, receipts, private, terminal))
    assert result.status == "R5_ORACLE_FAILED"
    assert [item.verb for item in result.processes] == [
        "source",
        "purge",
        "cleanup",
        "failed",
    ]
    failure = json.loads((terminal / "failure.json").read_text())
    assert failure["stage"] == "projection"
    assert failure["failure_code"] == "PROCESS"
    assert not private.exists()


def test_pregate_commit_failure_opens_no_source_and_publishes_failed(
    tmp_path: Path,
) -> None:
    source_paths, receipts = _fixture(tmp_path / "inputs-pregate")
    terminal = tmp_path / "terminal-pregate"
    result = run_synthetic_oracle(
        _input(
            source_paths,
            receipts,
            tmp_path / "private-pregate",
            terminal,
            "0" * 40,
        )
    )
    assert result.status == "R5_ORACLE_FAILED"
    assert [item.verb for item in result.processes] == ["cleanup", "failed"]
    failure = json.loads((terminal / "failure.json").read_text())
    assert failure["stage"] == "pre_gate"
    assert failure["operation_accounting"] == dict.fromkeys(
        failure["operation_accounting"], 0
    )


def test_pregate_terminal_source_drift_uses_trusted_failure_publisher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_paths, receipts = _fixture(tmp_path / "inputs-source-drift")
    config = _input(
        source_paths,
        receipts,
        tmp_path / "private-source-drift",
        tmp_path / "terminal-source-drift",
    )
    monkeypatch.setattr(
        "cypshift.openadmet_oracle_runner._validate_checkout", lambda _oid: None
    )
    monkeypatch.setattr(
        "cypshift.openadmet_oracle_runner.terminal_source_bundle_sha256",
        lambda: "0" * 64,
    )
    result = run_synthetic_oracle(config)
    assert result.status == "R5_ORACLE_FAILED"
    assert [item.verb for item in result.processes] == ["cleanup", "failed"]
    assert not config.private_root.exists()
    assert (config.terminal_root / "failure.json").is_file()


def test_stale_control_is_purged_and_one_pregate_failure_is_published(
    tmp_path: Path,
) -> None:
    source_paths, receipts = _fixture(tmp_path / "inputs-stale-control")
    private = tmp_path / "private-stale-control"
    terminal = tmp_path / "terminal-stale-control"
    stale = tmp_path / f".{private.name}-control"
    stale.mkdir()
    (stale / "opaque.bin").write_bytes(b"stale-private-control")
    config = _input(source_paths, receipts, private, terminal)
    result = run_synthetic_oracle(config)
    assert result.status == "R5_ORACLE_FAILED"
    assert [item.verb for item in result.processes] == [
        "purge",
        "cleanup",
        "failed",
    ]
    assert not private.exists()
    assert not stale.exists()
    assert not (tmp_path / f".{terminal.name}-failure-control").exists()
    failure = json.loads((terminal / "failure.json").read_text())
    assert "stale-control-cleanup-witness" in failure["verified_receipts"]


@pytest.mark.parametrize(
    ("stage", "child"),
    (
        ("inner_models", "pair-inner"),
        ("outer_models", "pair-outer"),
        ("outer_score", "outer"),
    ),
)
def test_late_child_crash_counts_only_verified_complete_manifests(
    tmp_path: Path, stage: str, child: str
) -> None:
    private = tmp_path / f"private-{stage}"
    meta = tmp_path / f".{private.name}-control"
    private.mkdir()
    meta.mkdir()
    coordinator = _Coordinator(private, meta)
    coordinator.stage = stage
    accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    accounting["direct_target_values_parsed"] = 7
    manifest_data = (
        json.dumps(
            {"operation_accounting": accounting},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    complete = private / "complete-child"
    publish_readonly_tree(complete, {"manifest.json": manifest_data})
    complete_receipt = coordinator.register_manifest("complete-child", complete)[
        "manifest_sha256"
    ]
    opaque = private / "failed-child-private"
    publish_readonly_tree(opaque, {"target.bin": b"opaque-target-bytes"})
    terminal = tmp_path / f"terminal-{stage}"
    result = _publish_late_failure(
        _input({}, {}, private, terminal),
        coordinator,
        OracleProcessFailure(child, 9),
    )
    assert result.status == "R5_ORACLE_FAILED"
    failure = json.loads((terminal / "failure.json").read_text())
    assert failure["reason"] == f"{stage} {child} returncode 9"
    assert failure["verified_receipts"]["complete-child"] == complete_receipt
    assert failure["operation_accounting"]["direct_target_values_parsed"] == 7
    assert not any(private.iterdir())

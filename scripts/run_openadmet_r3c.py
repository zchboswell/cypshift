#!/usr/bin/env python3
"""Run the single frozen OpenADMET R3C global experiment.

The parent process performs only the receipt/runtime gates and target
projection.  Every model cell, freezer, and scorer runs sequentially in the
accepted locked research interpreter.  This wrapper exposes no synthetic,
resume, tuning, or concurrency escape hatch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
CONTRACT = ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract_v5.json"
V4_CONTRACT = ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract_v4.json"
V3_CONTRACT = ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract.json"
UV_LOCK = ROOT / "uv.lock"
RESEARCH_ROOT = ROOT / "research/maplight-fixed"
RESEARCH_PYTHON = RESEARCH_ROOT / ".venv/bin/python"
RESEARCH_UV_LOCK = RESEARCH_ROOT / "uv.lock"
CELL_RUNNER = RESEARCH_ROOT / "run_r3b_cells.py"
SCORER = RESEARCH_ROOT / "run_r3b_scoring.py"
RUNNER = Path(__file__).resolve()

V5_SHA256 = "596d9a246b130c00f07abfcaf73b369038b874ce556be5e6354df10e1d5ad6e2"
V4_SHA256 = "a37a316ceab297deb89d4458169d38d1c73d2edb39ab96ea4c77459a56b01254"
V3_SHA256 = "d728684cc3794bbe01ea44342202944a378968f097cb8f5490852b63721a6285"
UV_LOCK_SHA256 = "33d9382256de7992ce9ff7a7edc125d4771546a25ef3be5f1160627846d2c9b6"
RESEARCH_UV_LOCK_SHA256 = (
    "99e72821b69d9bb943a6e32adc7e0dec0e46c6d32df090241d4fb9296a4195d8"
)
PROJECTOR_SOURCE_SHA256 = (
    "455397869774d104144f0ca09c063f6c915046b4458da35040bf2c0dfaebfc18"
)
PREFLIGHT_SOURCE_SHA256 = (
    "4ac5c35a293a6a0ec32426a602c0a55e5fab31155205bbff44b80b58c7cc35df"
)
R3A_FEATURE_MANIFEST_SHA256 = (
    "32a950959ceca0641b56518e2059069a275ced64cf399d095aa5bce522c8026b"
)
CELL_SOURCE_FILES = (
    "research/maplight-fixed/run_r3b_cells.py",
    "research/maplight-fixed/r3b_cell_io.py",
    "research/maplight-fixed/r3b_cell_freezer.py",
)
FREEZER_SOURCE_FILES = (
    "research/maplight-fixed/r3b_cell_freezer.py",
    "research/maplight-fixed/r3b_cell_io.py",
)
SCORER_SOURCE_FILES = (
    "research/maplight-fixed/run_r3b_scoring.py",
    "research/maplight-fixed/r3b_scoring_artifacts.py",
    "research/maplight-fixed/r3b_scoring_math.py",
    "research/maplight-fixed/r3b_scoring_manifest.py",
    "research/maplight-fixed/r3b_scoring_preflight.py",
    "research/maplight-fixed/r3b_scoring_publish.py",
    "research/maplight-fixed/r3b_scoring_terminal.py",
)
# Refreshed and frozen after the final component repair replay.
CELL_SOURCE_SHA256 = "9934e267b09df763fb45071884415b5c8f6eeb10189edc30e862bc758c45a053"
FREEZER_SOURCE_SHA256 = (
    "535e84951279894f0c8245112a95218e67d8059fc6f6b88aea1372d18323e6bc"
)
SCORER_SOURCE_SHA256 = (
    "2a3dec027efe46e0e6439a0280ce1df9182fe1a063d25143f7bd331b2d1ea8ac"
)
ENDPOINTS = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
TERMINAL_FILES = {
    "GLOBAL_FAILED": frozenset({"failure_receipt.json"}),
    "GLOBAL_UNDERPOWERED": frozenset({"global_result.json", "manifest.json"}),
    "GLOBAL_NO_ADVANTAGE": frozenset(
        {
            "global_oof_predictions.csv",
            "global_oof_freeze_manifest.json",
            "global_cell_metrics.csv",
            "global_bootstrap_summary.csv",
            "global_endpoint_loss_checks.csv",
            "global_influence_checks.csv",
            "global_outer_assessment.json",
            "global_result.json",
            "manifest.json",
        }
    ),
    "GLOBAL_EXPERT_FROZEN": frozenset(
        {
            "global_oof_predictions.csv",
            "global_oof_freeze_manifest.json",
            "global_cell_metrics.csv",
            "global_bootstrap_summary.csv",
            "global_endpoint_loss_checks.csv",
            "global_influence_checks.csv",
            "global_outer_assessment.json",
            "inner_selection_token.json",
            "global_inner_oof_predictions.csv",
            "global_inner_oof_freeze_manifest.json",
            "global_uncertainty_calibration.csv",
            "parent_state_completion_outer_training.csv",
            "parent_state_completion_final.csv",
            "global_result.json",
            "manifest.json",
        }
    ),
}


class R3CRunnerError(RuntimeError):
    """A gate, orchestration, or publication invariant failed."""


@dataclass(frozen=True, slots=True)
class R3CResult:
    status: str
    terminal_output: Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_sha(value: str, label: str) -> None:
    if (
        len(value) != 64
        or value != value.lower()
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise R3CRunnerError(f"{label} must be lowercase SHA-256")


def _regular(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise R3CRunnerError(f"{label} must be a regular non-symlink file")
    return path


def _directory(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise R3CRunnerError(f"{label} must be a regular non-symlink directory")
    return path


def _interpreter(path: Path) -> Path:
    if not path.is_file() or not path.exists():
        raise R3CRunnerError("locked research interpreter is unavailable")
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise R3CRunnerError("locked research interpreter target is unavailable")
    return path


def _destination(path: Path, label: str) -> None:
    if ".." in path.parts:
        raise R3CRunnerError(f"{label} may not contain parent traversal")
    if path.is_symlink() or path.exists():
        raise R3CRunnerError(f"{label} already exists")
    if any(parent.is_symlink() for parent in path.parents):
        raise R3CRunnerError(f"{label} has a symlinked parent")


def _validate_destinations(private: Path, terminal: Path) -> None:
    staged = _terminal_stage(terminal)
    _destination(private, "private run root")
    _destination(terminal, "terminal output")
    _destination(staged, "terminal staging root")
    resolved = tuple(path.resolve(strict=False) for path in (private, terminal, staged))
    for index, left in enumerate(resolved):
        for right in resolved[index + 1 :]:
            if left == right or left in right.parents or right in left.parents:
                raise R3CRunnerError("private and terminal roots may not be nested")


def _terminal_stage(terminal: Path) -> Path:
    return terminal.with_name(f".{terminal.name}.r3c-staged")


def _source_bundle_sha(paths: Sequence[str]) -> str:
    material = "".join(
        f"{relative}|{_sha256(ROOT / relative)}\n" for relative in sorted(paths)
    )
    return _sha256_bytes(material.encode("utf-8"))


def _gate_runtime_and_sources(expected_runner_sha256: str, feature_root: Path) -> None:
    if sys.version_info[:3] != (3, 12, 3):
        raise R3CRunnerError("R3C parent requires Python 3.12.3")
    _require_sha(expected_runner_sha256, "expected runner SHA-256")
    if _sha256(RUNNER) != expected_runner_sha256:
        raise R3CRunnerError("runner self-hash acceptance receipt mismatch")
    if _sha256(_regular(UV_LOCK, "root uv.lock")) != UV_LOCK_SHA256:
        raise R3CRunnerError("root uv.lock receipt mismatch")
    if (
        _sha256(_regular(RESEARCH_UV_LOCK, "research uv.lock"))
        != RESEARCH_UV_LOCK_SHA256
    ):
        raise R3CRunnerError("research uv.lock receipt mismatch")
    runtime = _subprocess(
        [
            str(RESEARCH_PYTHON),
            "-c",
            "import importlib.metadata, platform, sys; "
            "print(f'{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}|"
            "{platform.system()}|{platform.machine()}|"
            '{importlib.metadata.version("numpy")}|'
            '{importlib.metadata.version("catboost")}\')',
        ],
        "research runtime gate",
    )
    if runtime.stdout.strip() != "3.10.13|Linux|x86_64|1.25.2|1.2.1":
        raise R3CRunnerError("locked research runtime differs")
    for path, expected, label in (
        (CONTRACT, V5_SHA256, "V5 contract"),
        (V4_CONTRACT, V4_SHA256, "V4 contract"),
        (V3_CONTRACT, V3_SHA256, "V3 contract"),
    ):
        if _sha256(_regular(path, label)) != expected:
            raise R3CRunnerError(f"{label} receipt mismatch")
    if (
        _source_bundle_sha(
            (
                "src/cypshift/openadmet_global_io.py",
                "src/cypshift/openadmet_global_projection.py",
            )
        )
        != PROJECTOR_SOURCE_SHA256
    ):
        raise R3CRunnerError("projector source bundle receipt mismatch")
    if (
        _source_bundle_sha(
            (
                "src/cypshift/openadmet_global_io.py",
                "src/cypshift/openadmet_global_preflight.py",
            )
        )
        != PREFLIGHT_SOURCE_SHA256
    ):
        raise R3CRunnerError("preflight source bundle receipt mismatch")
    feature_manifest = _regular(
        feature_root / "feature_manifest.json", "R3A feature manifest"
    )
    if _sha256(feature_manifest) != R3A_FEATURE_MANIFEST_SHA256:
        raise R3CRunnerError("accepted R3A feature manifest receipt mismatch")
    try:
        manifest = json.loads(feature_manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise R3CRunnerError("R3A feature manifest is not valid JSON") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version")
        != "cypshift.openadmet_cyp_2026.r3a_feature_manifest.v1"
    ):
        raise R3CRunnerError("R3A feature manifest schema differs")
    _interpreter(RESEARCH_PYTHON)
    _regular(CELL_RUNNER, "R3B cell runner")
    _regular(SCORER, "R3B scorer")
    for paths, expected, label in (
        (CELL_SOURCE_FILES, CELL_SOURCE_SHA256, "cell runner source bundle"),
        (FREEZER_SOURCE_FILES, FREEZER_SOURCE_SHA256, "freezer source bundle"),
        (SCORER_SOURCE_FILES, SCORER_SOURCE_SHA256, "scorer source bundle"),
    ):
        if _source_bundle_sha(paths) != expected:
            raise R3CRunnerError(f"{label} receipt mismatch")


def _input_gate(path: Path, label: str) -> None:
    _regular(path, label)


def _subprocess(command: Sequence[str], stage: str) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            list(command), check=False, capture_output=True, text=True
        )
    except OSError as exc:
        raise R3CRunnerError(f"{stage} subprocess could not start: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[-2000:]
        raise R3CRunnerError(f"{stage} subprocess failed: {detail}")
    return completed


def _cell_command(
    *,
    stage: str,
    endpoint: str,
    repeat: int,
    outer: int,
    inner: int | None,
    feature_root: Path,
    feature_manifest_sha256: str,
    public_root: Path,
    public_manifest_sha256: str,
    preflight: Path,
    output: Path,
    token: Path | None = None,
) -> list[str]:
    command = [
        str(RESEARCH_PYTHON),
        str(CELL_RUNNER),
        "cell",
        "--stage",
        stage,
        "--endpoint",
        endpoint,
        "--repeat",
        str(repeat),
        "--outer-fold",
        str(outer),
        "--feature-root",
        str(feature_root),
        "--feature-manifest-sha256",
        feature_manifest_sha256,
        "--model-public-root",
        str(public_root),
        "--model-public-manifest-sha256",
        public_manifest_sha256,
        "--preflight-receipt",
        str(preflight),
        "--output-root",
        str(output),
        "--expected-source-bundle-sha256",
        CELL_SOURCE_SHA256,
    ]
    if inner is not None:
        command.extend(("--inner-fold", str(inner)))
    if token is not None:
        command.extend(("--inner-selection-token", str(token)))
    return command


def _freeze_command(
    *,
    stage: str,
    cell_roots: Sequence[Path],
    output: Path,
    public_root: Path,
    public_manifest_sha256: str,
    preflight: Path,
    feature_manifest_sha256: str,
    token: Path | None = None,
) -> list[str]:
    command = [str(RESEARCH_PYTHON), str(CELL_RUNNER), f"freeze-{stage}"]
    for root in cell_roots:
        command.extend(("--cell-root", str(root)))
    command.extend(
        (
            "--output-root",
            str(output),
            "--model-public-root",
            str(public_root),
            "--model-public-manifest-sha256",
            public_manifest_sha256,
            "--preflight-receipt",
            str(preflight),
            "--feature-manifest-sha256",
            feature_manifest_sha256,
            "--expected-source-bundle-sha256",
            FREEZER_SOURCE_SHA256,
        )
    )
    if token is not None:
        command.extend(("--inner-selection-token", str(token)))
    return command


def _score_outer_command(
    *,
    outer_root: Path,
    sealed_root: Path,
    stage_root: Path,
    output: Path,
    outer_manifest_sha256: str,
    sealed_manifest_sha256: str,
    preflight: Path,
    preflight_sha256: str,
) -> list[str]:
    return [
        str(RESEARCH_PYTHON),
        str(SCORER),
        "outer",
        "--outer-root",
        str(outer_root),
        "--sealed-root",
        str(sealed_root),
        "--stage-root",
        str(stage_root),
        "--output-root",
        str(output),
        "--outer-manifest-sha256",
        outer_manifest_sha256,
        "--sealed-manifest-sha256",
        sealed_manifest_sha256,
        "--preflight-receipt",
        str(preflight),
        "--preflight-receipt-sha256",
        preflight_sha256,
        "--expected-source-bundle-sha256",
        SCORER_SOURCE_SHA256,
    ]


def _score_final_command(
    *,
    outer_stage: Path,
    inner_root: Path,
    sealed_root: Path,
    output: Path,
    inner_manifest_sha256: str,
    sealed_manifest_sha256: str,
) -> list[str]:
    return [
        str(RESEARCH_PYTHON),
        str(SCORER),
        "final",
        "--outer-stage-root",
        str(outer_stage),
        "--inner-root",
        str(inner_root),
        "--sealed-root",
        str(sealed_root),
        "--output-root",
        str(output),
        "--inner-manifest-sha256",
        inner_manifest_sha256,
        "--sealed-manifest-sha256",
        sealed_manifest_sha256,
        "--expected-source-bundle-sha256",
        SCORER_SOURCE_SHA256,
    ]


def _status(terminal: Path) -> str:
    result = terminal / "global_result.json"
    if result.is_file():
        value = json.loads(result.read_text(encoding="utf-8"))
        status = value.get("status")
        if not isinstance(status, str):
            raise R3CRunnerError("terminal status is not a string")
    elif (terminal / "failure_receipt.json").is_file():
        status = "GLOBAL_FAILED"
    else:
        raise R3CRunnerError("terminal status file is missing")
    if status not in TERMINAL_FILES:
        raise R3CRunnerError(f"unknown terminal status: {status}")
    observed = frozenset(
        path.relative_to(terminal).as_posix()
        for path in terminal.rglob("*")
        if path.is_file()
    )
    if observed != TERMINAL_FILES[status]:
        raise R3CRunnerError(f"{status} terminal file set differs")
    return status


def _cleanup_private(root: Path) -> None:
    if not root.exists():
        return
    if root.is_symlink() or not root.is_dir():
        raise R3CRunnerError("private run root became unsafe during cleanup")
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_symlink():
            raise R3CRunnerError("private run root contains a symlink")
        if path.is_dir():
            try:
                path.chmod(0o755)
            except OSError as exc:
                raise R3CRunnerError(
                    f"private cleanup permission failure: {exc}"
                ) from exc
    root.chmod(0o755)
    shutil.rmtree(root)


def _safe_relative(value: str) -> Path:
    path = Path(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        raise R3CRunnerError("public-view target path is unsafe")
    return path


def _link_file(source: Path, destination: Path) -> None:
    _regular(source, "public-view source")
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.link(source, destination, follow_symlinks=False)


def _seal_view(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_symlink():
            raise R3CRunnerError("public view contains a symlink")
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)


def _public_view(source: Path, destination: Path, target: str | None) -> Path:
    if destination.exists() or destination.is_symlink():
        raise R3CRunnerError("public view destination exists")
    destination.mkdir(parents=True)
    _link_file(
        source / "model_public_manifest.json",
        destination / "model_public_manifest.json",
    )
    _link_file(source / "model_rows.csv", destination / "model_rows.csv")
    if target is not None:
        relative = _safe_relative(target)
        _link_file(source / relative, destination / relative)
    _seal_view(destination)
    return destination


def _target_relative(
    stage: str, endpoint: str, repeat: int, outer: int, inner: int | None
) -> str:
    if stage == "outer":
        return f"outer_targets/{endpoint}/repeat-{repeat}/outer-{outer}.csv"
    if inner is None:
        raise R3CRunnerError("inner target requires an inner fold")
    return f"inner_targets/{endpoint}/repeat-{repeat}/outer-{outer}/inner-{inner}.csv"


def _validate_readonly_terminal(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise R3CRunnerError("terminal root differs")
    if root.stat().st_mode & 0o222:
        raise R3CRunnerError("terminal root is writable")
    for path in root.rglob("*"):
        if path.is_symlink() or path.stat().st_mode & 0o222:
            raise R3CRunnerError("terminal contains a symlink or writable entry")


def _promote_terminal(staged: Path, destination: Path) -> None:
    code = (
        "import sys; from pathlib import Path; "
        "sys.path.insert(0, sys.argv[3]); "
        "from r3b_scoring_publish import _rename_noreplace; "
        "_rename_noreplace(Path(sys.argv[1]), Path(sys.argv[2]))"
    )
    _subprocess(
        [
            str(RESEARCH_PYTHON),
            "-c",
            code,
            str(staged),
            str(destination),
            str(RESEARCH_ROOT),
        ],
        "terminal promotion",
    )


def _finalize_terminal(private: Path, staged: Path, destination: Path) -> str:
    status = _status(staged)
    _validate_readonly_terminal(staged)
    _cleanup_private(private)
    _promote_terminal(staged, destination)
    if _status(destination) != status:
        raise R3CRunnerError("promoted terminal status differs")
    _validate_readonly_terminal(destination)
    return status


def _publish_failure(terminal: Path, stage: str, message: str) -> None:
    code = (
        "import sys; "
        "sys.path.insert(0, sys.argv[4]); "
        "from pathlib import Path; "
        "from r3b_scoring_terminal import publish_failure; "
        "publish_failure(output_root=Path(sys.argv[1]), "
        "error=RuntimeError(sys.argv[3]), stage=sys.argv[2])"
    )
    _subprocess(
        [
            str(RESEARCH_PYTHON),
            "-c",
            code,
            str(terminal),
            stage,
            message,
            str(RESEARCH_ROOT),
        ],
        "failure publication",
    )


def _read_projection_result(result: Any) -> tuple[Path, Path, str, str, str]:
    return (
        Path(result.model_public_root),
        Path(result.scorer_sealed_root),
        str(result.model_public_manifest_sha256),
        str(result.sealed_truth_manifest_sha256),
        str(result.private_audit_sha256),
    )


def run_experiment(
    *,
    direct_observations: Path,
    group_folds: Path,
    feature_root: Path,
    private_run_root: Path,
    terminal_output: Path,
    expected_runner_sha256: str,
) -> R3CResult:
    """Run R3C and return the exact published terminal status."""
    _validate_destinations(private_run_root, terminal_output)
    _directory(feature_root, "R3A feature root")
    _gate_runtime_and_sources(expected_runner_sha256, feature_root)
    _input_gate(direct_observations, "direct observations")
    _input_gate(group_folds, "group folds")
    private_run_root.mkdir(parents=True)
    projection = private_run_root / "projection"
    preflight = private_run_root / "preflight_receipt.json"
    staged_terminal = _terminal_stage(terminal_output)
    current_stage = "projection"
    try:
        sys.path.insert(0, str(SRC))
        from cypshift.openadmet_global_projection import (  # type: ignore[import-untyped]  # noqa: PLC0415
            preflight_openadmet_global_targets,
            project_openadmet_global_targets,
        )

        projected = project_openadmet_global_targets(
            direct_observations,
            group_folds,
            projection,
            expected_projector_source_sha256=PROJECTOR_SOURCE_SHA256,
        )
        current_stage = "preflight"
        preflight_result = preflight_openadmet_global_targets(
            projection,
            expected_model_public_manifest_sha256=projected.model_public_manifest_sha256,
            expected_private_audit_sha256=projected.private_audit_sha256,
            expected_preflight_source_sha256=PREFLIGHT_SOURCE_SHA256,
            output_path=preflight,
        )
        public_root, sealed_root, public_sha, sealed_sha, _audit_sha = (
            _read_projection_result(projected)
        )
        preflight_sha = _sha256(preflight)
        if not preflight_result.receipt["passed"]:
            _subprocess(
                _score_outer_command(
                    outer_root=private_run_root / "unused-outer",
                    sealed_root=sealed_root,
                    stage_root=private_run_root / "unused-stage",
                    output=staged_terminal,
                    outer_manifest_sha256="0" * 64,
                    sealed_manifest_sha256=sealed_sha,
                    preflight=preflight,
                    preflight_sha256=preflight_sha,
                ),
                "underpowered terminal publication",
            )
            status = _finalize_terminal(
                private_run_root, staged_terminal, terminal_output
            )
            return R3CResult(status, terminal_output)

        outer_cells: list[Path] = []
        current_stage = "outer_model"
        for endpoint in ENDPOINTS:
            for repeat in range(3):
                for outer in range(5):
                    cell = (
                        private_run_root
                        / "outer-cells"
                        / endpoint
                        / f"repeat-{repeat}"
                        / f"outer-{outer}"
                    )
                    view = _public_view(
                        public_root,
                        private_run_root
                        / "outer-views"
                        / endpoint
                        / f"repeat-{repeat}"
                        / f"outer-{outer}",
                        _target_relative("outer", endpoint, repeat, outer, None),
                    )
                    outer_cells.append(cell)
                    _subprocess(
                        _cell_command(
                            stage="outer",
                            endpoint=endpoint,
                            repeat=repeat,
                            outer=outer,
                            inner=None,
                            feature_root=feature_root,
                            feature_manifest_sha256=R3A_FEATURE_MANIFEST_SHA256,
                            public_root=view,
                            public_manifest_sha256=public_sha,
                            preflight=preflight,
                            output=cell,
                        ),
                        f"outer cell {endpoint}/{repeat}/{outer}",
                    )
        outer_freeze = private_run_root / "outer-freeze"
        freezer_view = _public_view(
            public_root, private_run_root / "freezer-view", None
        )
        current_stage = "outer_freeze"
        _subprocess(
            _freeze_command(
                stage="outer",
                cell_roots=outer_cells,
                output=outer_freeze,
                public_root=freezer_view,
                public_manifest_sha256=public_sha,
                preflight=preflight,
                feature_manifest_sha256=R3A_FEATURE_MANIFEST_SHA256,
            ),
            "outer freeze",
        )
        outer_manifest = outer_freeze / "global_oof_freeze_manifest.json"
        outer_manifest_sha = _sha256(outer_manifest)
        outer_stage = private_run_root / "outer-stage"
        current_stage = "outer_score"
        _subprocess(
            _score_outer_command(
                outer_root=outer_freeze,
                sealed_root=sealed_root,
                stage_root=outer_stage,
                output=staged_terminal,
                outer_manifest_sha256=outer_manifest_sha,
                sealed_manifest_sha256=sealed_sha,
                preflight=preflight,
                preflight_sha256=preflight_sha,
            ),
            "outer score",
        )
        if staged_terminal.exists():
            status = _finalize_terminal(
                private_run_root, staged_terminal, terminal_output
            )
            return R3CResult(status, terminal_output)

        token = outer_stage / "inner_selection_token.json"
        if not token.is_file():
            raise R3CRunnerError("outer PASS did not publish the causal inner token")
        inner_cells: list[Path] = []
        current_stage = "inner_model"
        for endpoint in ENDPOINTS:
            for repeat in range(3):
                for outer in range(5):
                    for inner in range(4):
                        cell = (
                            private_run_root
                            / "inner-cells"
                            / endpoint
                            / f"repeat-{repeat}"
                            / f"outer-{outer}"
                            / f"inner-{inner}"
                        )
                        view = _public_view(
                            public_root,
                            private_run_root
                            / "inner-views"
                            / endpoint
                            / f"repeat-{repeat}"
                            / f"outer-{outer}"
                            / f"inner-{inner}",
                            _target_relative("inner", endpoint, repeat, outer, inner),
                        )
                        inner_cells.append(cell)
                        _subprocess(
                            _cell_command(
                                stage="inner",
                                endpoint=endpoint,
                                repeat=repeat,
                                outer=outer,
                                inner=inner,
                                feature_root=feature_root,
                                feature_manifest_sha256=R3A_FEATURE_MANIFEST_SHA256,
                                public_root=view,
                                public_manifest_sha256=public_sha,
                                preflight=preflight,
                                output=cell,
                                token=token,
                            ),
                            f"inner cell {endpoint}/{repeat}/{outer}/{inner}",
                        )
        inner_freeze = private_run_root / "inner-freeze"
        current_stage = "inner_freeze"
        _subprocess(
            _freeze_command(
                stage="inner",
                cell_roots=inner_cells,
                output=inner_freeze,
                public_root=freezer_view,
                public_manifest_sha256=public_sha,
                preflight=preflight,
                feature_manifest_sha256=R3A_FEATURE_MANIFEST_SHA256,
                token=token,
            ),
            "inner freeze",
        )
        inner_manifest = inner_freeze / "global_inner_oof_freeze_manifest.json"
        inner_manifest_sha = _sha256(inner_manifest)
        current_stage = "final_score"
        _subprocess(
            _score_final_command(
                outer_stage=outer_stage,
                inner_root=inner_freeze,
                sealed_root=sealed_root,
                output=staged_terminal,
                inner_manifest_sha256=inner_manifest_sha,
                sealed_manifest_sha256=sealed_sha,
            ),
            "final score",
        )
        status = _finalize_terminal(private_run_root, staged_terminal, terminal_output)
        return R3CResult(status, terminal_output)
    except Exception as exc:
        recovery_failure: tuple[str, Exception] | None = None
        if not terminal_output.exists() and not staged_terminal.exists():
            try:
                _publish_failure(staged_terminal, current_stage, str(exc))
            except Exception as publish_exc:
                recovery_failure = ("failure publication", publish_exc)
        if staged_terminal.exists() and not terminal_output.exists():
            try:
                _finalize_terminal(private_run_root, staged_terminal, terminal_output)
            except Exception as finalize_exc:
                recovery_failure = ("terminal finalization", finalize_exc)
        elif private_run_root.exists():
            try:
                _cleanup_private(private_run_root)
            except Exception as cleanup_exc:
                recovery_failure = ("private cleanup", cleanup_exc)
        if recovery_failure is not None:
            label, failure = recovery_failure
            if isinstance(failure, R3CRunnerError):
                raise failure from exc
            raise R3CRunnerError(f"{label} failed: {failure}") from failure
        if isinstance(exc, R3CRunnerError):
            raise
        raise R3CRunnerError(str(exc)) from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct-observations", type=Path, required=True)
    parser.add_argument("--group-folds", type=Path, required=True)
    parser.add_argument("--feature-root", type=Path, required=True)
    parser.add_argument("--private-run-root", type=Path, required=True)
    parser.add_argument("--terminal-output", type=Path, required=True)
    parser.add_argument("--expected-runner-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = run_experiment(
            direct_observations=args.direct_observations,
            group_folds=args.group_folds,
            feature_root=args.feature_root,
            private_run_root=args.private_run_root,
            terminal_output=args.terminal_output,
            expected_runner_sha256=args.expected_runner_sha256,
        )
    except R3CRunnerError as exc:
        parser.error(str(exc))
    print(result.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

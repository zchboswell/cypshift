"""Exact process topology and argv builders for the thin R5C coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cypshift.openadmet_oracle_scoring import EXPECTED_GRIDS

ROOT: Final = Path(__file__).resolve().parents[2]
G0_LOCKED_PYTHON: Final = ROOT / "research/maplight-fixed/.venv/bin/python"
PAIR_PYTHON: Final = ROOT / ".venv/bin/python"
G0_SCRIPT: Final = ROOT / "research/maplight-fixed/run_r5_oracle_g0.py"
PAIR_SCRIPT: Final = ROOT / "research/maplight-fixed/run_r5_oracle_pair_cell.py"


@dataclass(frozen=True, slots=True)
class PairTask:
    stage: str
    repeat: int
    outer_fold: int
    inner_fold: int | None
    system_id: str
    alpha: float | None
    lambda_value: float | None
    shared_outer_t0: bool = False


def inner_pair_tasks() -> tuple[PairTask, ...]:
    tasks = tuple(
        PairTask("inner", repeat, outer, inner, system, alpha, lambda_value)
        for repeat in range(3)
        for outer in range(5)
        for inner in range(4)
        for system in ("C2", "C3", "T0", "A0", "A1", "A2")
        for alpha, lambda_value in sorted(
            EXPECTED_GRIDS[system],
            key=lambda item: (
                -1.0 if item[0] is None else item[0],
                -1.0 if item[1] is None else item[1],
            ),
        )
    )
    if len(tasks) != 960:
        raise ValueError("inner process topology differs")
    return tasks


def outer_pair_tasks(
    selected: dict[tuple[str, int, int], tuple[float | None, float | None]],
) -> tuple[PairTask, ...]:
    expected = {
        (system, repeat, outer)
        for system in ("C2", "C3", "T0", "A0", "A1", "A2")
        for repeat in range(3)
        for outer in range(5)
    }
    if set(selected) != expected:
        raise ValueError("outer selection topology differs")
    if any(value not in EXPECTED_GRIDS[key[0]] for key, value in selected.items()):
        raise ValueError("outer selected grid coordinate differs")
    tasks: list[PairTask] = []
    for repeat in range(3):
        for outer in range(5):
            tasks.extend(
                (
                    PairTask("outer", repeat, outer, None, "C0", None, None),
                    PairTask("outer", repeat, outer, None, "C1", None, None),
                )
            )
            for system in ("C2", "C3", "A0", "A1", "A2"):
                alpha, lambda_value = selected[(system, repeat, outer)]
                tasks.append(
                    PairTask(
                        "outer",
                        repeat,
                        outer,
                        None,
                        system,
                        alpha,
                        lambda_value,
                    )
                )
            alpha, lambda_value = selected[("T0", repeat, outer)]
            tasks.extend(
                (
                    PairTask(
                        "outer",
                        repeat,
                        outer,
                        None,
                        "T0",
                        alpha,
                        lambda_value,
                        True,
                    ),
                    PairTask(
                        "outer",
                        repeat,
                        outer,
                        None,
                        "F2",
                        alpha,
                        lambda_value,
                    ),
                )
            )
    result = tuple(tasks)
    if len(result) != 135:
        raise ValueError("outer process topology differs")
    return result


def g0_command(
    *,
    model_root: Path,
    model_manifest_sha256: str,
    view_root: Path,
    view_manifest_sha256: str,
    g0_source_sha256: str,
    view_source_sha256: str,
    target_manifest_sha256: str,
    output_root: Path,
) -> tuple[str, ...]:
    return (
        str(G0_LOCKED_PYTHON),
        str(G0_SCRIPT),
        "--model-public-root",
        str(model_root),
        "--model-public-manifest-sha256",
        model_manifest_sha256,
        "--episode-target-root",
        str(view_root),
        "--episode-target-manifest-sha256",
        view_manifest_sha256,
        "--expected-source-bundle-sha256",
        g0_source_sha256,
        "--expected-episode-view-builder-source-sha256",
        view_source_sha256,
        "--expected-source-cell-target-manifest-sha256",
        target_manifest_sha256,
        "--output-root",
        str(output_root),
    )


def pair_command(
    task: PairTask,
    *,
    model_root: Path,
    model_manifest_sha256: str,
    target_root: Path,
    target_manifest_sha256: str,
    g0_roots: tuple[Path, ...],
    g0_manifest_sha256: tuple[str, ...],
    source_sha256: str,
    output_root: Path,
    token_root: Path | None = None,
    token_sha256: str | None = None,
    upstream_candidate_sha256: str | None = None,
    measured_parent_sha256: str | None = None,
    f0_output_root: Path | None = None,
    f1_output_root: Path | None = None,
) -> tuple[str, ...]:
    if len(g0_roots) != len(g0_manifest_sha256) or not g0_roots:
        raise ValueError("G0 argv cardinality differs")
    args = [
        str(PAIR_PYTHON),
        str(PAIR_SCRIPT),
        "--model-public-root",
        str(model_root),
        "--target-root",
        str(target_root),
        "--model-manifest-sha256",
        model_manifest_sha256,
        "--target-manifest-sha256",
        target_manifest_sha256,
        "--target-kind",
        "c3-target" if task.system_id == "C3" else "cell-target",
        "--stage",
        task.stage,
        "--repeat",
        str(task.repeat),
        "--outer-fold",
        str(task.outer_fold),
        "--system-id",
        task.system_id,
        "--expected-source-bundle-sha256",
        source_sha256,
        "--output-root",
        str(output_root),
    ]
    if task.inner_fold is not None:
        args.extend(("--inner-fold", str(task.inner_fold)))
    if task.alpha is not None:
        args.extend(("--alpha", format(task.alpha, ".17g")))
    if task.lambda_value is not None:
        args.extend(("--lambda", format(task.lambda_value, ".17g")))
    for root, receipt in zip(g0_roots, g0_manifest_sha256, strict=True):
        args.extend(("--g0-root", str(root), "--g0-manifest-sha256", receipt))
    if token_root is not None and token_sha256 is not None:
        args.extend(
            (
                "--selection-token-root",
                str(token_root),
                "--selection-token-sha256",
                token_sha256,
            )
        )
    elif token_root is not None or token_sha256 is not None:
        raise ValueError("selection token argv differs")
    if upstream_candidate_sha256 is not None:
        args.extend(("--upstream-candidate-receipt-sha256", upstream_candidate_sha256))
    if measured_parent_sha256 is not None:
        args.extend(
            (
                "--expected-g0-source-cell-target-manifest-sha256",
                measured_parent_sha256,
            )
        )
    if task.shared_outer_t0:
        if f0_output_root is None or f1_output_root is None:
            raise ValueError("shared T0 output argv differs")
        args.extend(
            (
                "--shared-outer-t0",
                "--f0-output-root",
                str(f0_output_root),
                "--f1-output-root",
                str(f1_output_root),
            )
        )
    elif f0_output_root is not None or f1_output_root is not None:
        raise ValueError("non-shared control output argv differs")
    return tuple(args)


__all__ = [
    "G0_SCRIPT",
    "G0_LOCKED_PYTHON",
    "PAIR_PYTHON",
    "PAIR_SCRIPT",
    "PairTask",
    "g0_command",
    "inner_pair_tasks",
    "outer_pair_tasks",
    "pair_command",
]

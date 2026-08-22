"""Supported-path mechanics for the thin synthetic R5C coordinator."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

from cypshift.openadmet_oracle_freezer_io import (
    freezer_source_bundle_sha256,
    g0_source_bundle_sha256,
    pair_runner_source_bundle_sha256,
)
from cypshift.openadmet_oracle_g0_view import view_builder_source_sha256
from cypshift.openadmet_oracle_inner_io import (
    candidate_runner_source_bundle_sha256,
    scorer_source_bundle_sha256,
)
from cypshift.openadmet_oracle_private_io import (
    read_stable_file,
    remove_private_root,
)
from cypshift.openadmet_oracle_runner_commands import (
    g0_command,
    inner_pair_tasks,
    outer_pair_tasks,
    pair_command,
)
from cypshift.openadmet_transformation_io import strict_json_object


class _Coordinator(Protocol):
    stage: str

    def worker(self, verb: str, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def command(self, verb: str, command: tuple[str, ...]) -> None: ...

    def register_manifest(self, label: str, root: Path) -> dict[str, Any]: ...


def run_supported(
    *,
    coordinator: _Coordinator,
    private_root: Path,
    terminal_root: Path,
    source_root: Path,
    source_receipts: Mapping[str, str],
    projection_root: Path,
    projection_manifests: Mapping[str, str],
    support_root: Path,
    support_sha256: str,
    terminal_source_sha256: str,
) -> str:
    """Execute every supported-path stage once and return the terminal status."""

    model_root = projection_root / "model-public"
    model_sha = _receipt(projection_manifests, "model-public")
    coordinator.stage = "inner_models"
    sealed_inner, sealed_outer = _migrate_sealed(
        coordinator,
        private_root,
        source_root,
        _receipt(source_receipts, "manifest.json"),
        projection_root,
        projection_manifests,
    )
    g0 = _run_g0_cells(
        coordinator,
        private_root,
        projection_root,
        projection_manifests,
        model_root,
        model_sha,
    )
    candidates = _run_inner_candidates(
        coordinator,
        private_root,
        projection_root,
        projection_manifests,
        model_root,
        model_sha,
        g0,
    )
    coordinator.stage = "inner_score"
    inner, tokens = _select_inner(coordinator, private_root, candidates, sealed_inner)
    coordinator.stage = "outer_models"
    outer_fragments = _run_outer_cells(
        coordinator,
        private_root,
        projection_root,
        projection_manifests,
        model_root,
        model_sha,
        g0,
        tokens,
    )
    coordinator.stage = "prediction_freeze"
    freeze = _freeze(
        coordinator,
        private_root,
        outer_fragments,
        g0,
        tokens,
        sealed_outer,
    )
    _remove_token_capabilities(tokens)
    available = [*candidates, *outer_fragments.values()]
    for roots in g0.values():
        available.extend(roots)
    available.extend((inner, freeze))
    coordinator.stage = "terminal_publish"
    accounting = coordinator.worker(
        "accounting",
        {
            "output_root": str(private_root / "accounting"),
            "freeze": _root_manifest(freeze),
            "inner_selection": _root_manifest(inner),
            "sealed_outer": [_sealed_input(item) for item in sealed_outer],
            "available_children": [
                {
                    "label": f"available-{index:05d}",
                    "root": str(_path(item, "root")),
                    "manifest_sha256": _digest(item, "manifest_sha256"),
                }
                for index, item in enumerate(available)
            ],
        },
    )
    _remove_roots(sealed_inner)
    remove_private_root(projection_root)
    remove_private_root(source_root)
    children = _records(accounting, "children")
    cleanup_capabilities = _cleanup_capabilities(
        freeze,
        inner,
        sealed_outer,
        support_root,
        support_sha256,
        accounting,
        children,
    )
    cleanup = coordinator.worker(
        "cleanup",
        {
            "output_root": str(private_root / "cleanup"),
            "capabilities": cleanup_capabilities,
        },
    )
    coordinator.stage = "outer_score"
    coordinator.worker(
        "outer",
        {
            "inputs": {
                "freeze": _root_manifest(freeze),
                "inner_selection": _root_manifest(inner),
                "sealed_outer": [_sealed_input(item) for item in sealed_outer],
                "support": {"root": str(support_root), "sha256": support_sha256},
                "aggregate_accounting": {
                    "root": str(_path(accounting, "root")),
                    "sha256": _digest(accounting, "sha256"),
                    "child_receipts": [
                        [
                            _string(item, "label"),
                            _digest(item, "manifest_sha256"),
                        ]
                        for item in children
                    ],
                    "child_manifests": children,
                },
                "cleanup": {
                    "root": str(_path(cleanup, "root")),
                    "sha256": _digest(cleanup, "sha256"),
                    "capabilities": cleanup_capabilities,
                },
            },
            "output_root": str(terminal_root),
            "source_sha256": terminal_source_sha256,
        },
    )
    _prune_empty(private_root)
    status = _terminal_status(terminal_root)
    if status not in {"R5_ORACLE_NO_SIGNAL", "R5_ORACLE_SIGNAL_PASS"}:
        raise ValueError("supported terminal status differs")
    return status


def _migrate_sealed(
    coordinator: _Coordinator,
    private_root: Path,
    source_root: Path,
    source_sha: str,
    projection_root: Path,
    manifests: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    inner: list[dict[str, Any]] = []
    outer: list[dict[str, Any]] = []
    for stage in ("inner", "outer"):
        for repeat in range(3):
            for fold in range(5):
                inner_values = range(4) if stage == "inner" else (None,)
                for inner_fold in inner_values:
                    relative = _scope_relative(stage, repeat, fold, inner_fold)
                    scope = _scope_record(stage, repeat, fold, inner_fold)
                    output_root = private_root / "sealed-v3" / relative
                    output_root.parent.mkdir(parents=True, exist_ok=True)
                    result = coordinator.worker(
                        "migrate",
                        {
                            "v2_root": str(
                                projection_root / "sealed-scorer" / relative
                            ),
                            "source_root": str(source_root),
                            "output_root": str(output_root),
                            "v2_manifest_sha256": _receipt(
                                manifests, f"sealed-scorer/{relative}"
                            ),
                            "source_manifest_sha256": source_sha,
                            "scope": scope,
                        },
                    )
                    record = {**scope, **dict(result)}
                    (inner if stage == "inner" else outer).append(record)
    if len(inner) != 60 or len(outer) != 15:
        raise ValueError("sealed migration cardinality differs")
    return inner, outer


def _run_g0_cells(
    coordinator: _Coordinator,
    private_root: Path,
    projection_root: Path,
    manifests: Mapping[str, str],
    model_root: Path,
    model_sha: str,
) -> dict[tuple[str, int, int, int | None], list[dict[str, Any]]]:
    output: dict[tuple[str, int, int, int | None], list[dict[str, Any]]] = {}
    for stage in ("inner", "outer"):
        for repeat in range(3):
            for outer in range(5):
                inner_values = range(4) if stage == "inner" else (None,)
                for inner_fold in inner_values:
                    key = (stage, repeat, outer, inner_fold)
                    relative = _scope_relative(stage, repeat, outer, inner_fold)
                    target_root = projection_root / "cell-target" / relative
                    target_sha = _receipt(manifests, f"cell-target/{relative}")
                    scope = _scope_record(stage, repeat, outer, inner_fold)
                    episode_result = coordinator.worker(
                        "episodes",
                        {
                            "model_root": str(model_root),
                            "model_manifest_sha256": model_sha,
                            "target_root": str(target_root),
                            "target_manifest_sha256": target_sha,
                            "scope": scope,
                        },
                    )
                    episode_ids = _strings(episode_result, "episode_ids")
                    roots: list[dict[str, Any]] = []
                    for index, episode_id in enumerate(episode_ids):
                        stem = f"{stage}-{repeat}-{outer}-{inner_fold}-{index:04d}"
                        view_root = private_root / "g0-view" / stem
                        view_root.parent.mkdir(parents=True, exist_ok=True)
                        view = coordinator.worker(
                            "view",
                            {
                                "model_root": str(model_root),
                                "model_manifest_sha256": model_sha,
                                "target_root": str(target_root),
                                "target_manifest_sha256": target_sha,
                                "scope": scope,
                                "episode_id": episode_id,
                                "output_root": str(view_root),
                            },
                        )
                        g0_root = private_root / "g0" / stem
                        g0_root.parent.mkdir(parents=True, exist_ok=True)
                        coordinator.command(
                            "g0",
                            g0_command(
                                model_root=model_root,
                                model_manifest_sha256=model_sha,
                                view_root=_path(view, "root"),
                                view_manifest_sha256=_digest(view, "manifest_sha256"),
                                g0_source_sha256=g0_source_bundle_sha256(),
                                view_source_sha256=view_builder_source_sha256(),
                                target_manifest_sha256=target_sha,
                                output_root=g0_root,
                            ),
                        )
                        roots.append(
                            coordinator.register_manifest(f"g0-{stem}", g0_root)
                        )
                        remove_private_root(_path(view, "root"))
                    if not roots:
                        raise ValueError("G0 episode cardinality differs")
                    output[key] = roots
    if len(output) != 75:
        raise ValueError("G0 cell cardinality differs")
    _prune_empty(private_root / "g0-view")
    return output


def _run_inner_candidates(
    coordinator: _Coordinator,
    private_root: Path,
    projection_root: Path,
    manifests: Mapping[str, str],
    model_root: Path,
    model_sha: str,
    g0: Mapping[tuple[str, int, int, int | None], Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, task in enumerate(inner_pair_tasks()):
        relative = _scope_relative(
            task.stage, task.repeat, task.outer_fold, task.inner_fold
        )
        target_family = "c3-target" if task.system_id == "C3" else "cell-target"
        target_root = projection_root / target_family / relative
        target_sha = _receipt(manifests, f"{target_family}/{relative}")
        source_parent = _receipt(manifests, f"cell-target/{relative}")
        roots = g0[(task.stage, task.repeat, task.outer_fold, task.inner_fold)]
        output_root = private_root / "inner-candidates" / f"candidate-{index:04d}"
        output_root.parent.mkdir(parents=True, exist_ok=True)
        coordinator.command(
            "pair-inner",
            pair_command(
                task,
                model_root=model_root,
                model_manifest_sha256=model_sha,
                target_root=target_root,
                target_manifest_sha256=target_sha,
                g0_roots=tuple(_path(item, "root") for item in roots),
                g0_manifest_sha256=tuple(
                    _digest(item, "manifest_sha256") for item in roots
                ),
                source_sha256=candidate_runner_source_bundle_sha256(),
                output_root=output_root,
                measured_parent_sha256=(
                    source_parent if task.system_id == "C3" else None
                ),
            ),
        )
        record = coordinator.register_manifest(
            f"inner-candidate-{index:04d}", output_root
        )
        record.update(
            {
                "system_id": task.system_id,
                "repeat": task.repeat,
                "outer_fold": task.outer_fold,
                "inner_fold": task.inner_fold,
                "alpha": task.alpha,
                "lambda": task.lambda_value,
            }
        )
        output.append(record)
    if len(output) != 960:
        raise ValueError("inner candidate cardinality differs")
    return output


def _select_inner(
    coordinator: _Coordinator,
    private_root: Path,
    candidates: Sequence[Mapping[str, Any]],
    sealed_inner: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    token_roots: list[dict[str, Any]] = []
    for system in ("C2", "C3", "T0", "A0", "A1", "A2"):
        for repeat in range(3):
            for outer in range(5):
                parent = private_root / "tokens" / f"{system}-{repeat}-{outer}"
                parent.mkdir(parents=True)
                token_roots.append(
                    {
                        "system_id": system,
                        "repeat": repeat,
                        "outer_fold": outer,
                        "root": str(parent / "capability"),
                    }
                )
    result = coordinator.worker(
        "inner",
        {
            "candidates": [
                {
                    "system_id": _string(item, "system_id"),
                    "repeat": _integer(item, "repeat"),
                    "outer_fold": _integer(item, "outer_fold"),
                    "inner_fold": _integer(item, "inner_fold"),
                    "alpha": item["alpha"],
                    "lambda": item["lambda"],
                    "root": str(_path(item, "root")),
                    "manifest_sha256": _digest(item, "manifest_sha256"),
                    "operation_accounting": _accounting(item),
                }
                for item in candidates
            ],
            "sealed": [
                {
                    "repeat": _integer(item, "repeat"),
                    "outer_fold": _integer(item, "outer_fold"),
                    "inner_fold": _integer(item, "inner_fold"),
                    "root": str(_path(item, "root")),
                    "manifest_sha256": _digest(item, "manifest_sha256"),
                }
                for item in sealed_inner
            ],
            "output_root": str(private_root / "inner-selection"),
            "token_roots": token_roots,
            "scorer_source_sha256": scorer_source_bundle_sha256(),
            "candidate_source_sha256": candidate_runner_source_bundle_sha256(),
        },
    )
    completed = coordinator.register_manifest("inner-selection", _path(result, "root"))
    result = {**dict(result), **completed}
    tokens = _records(result, "tokens")
    if result.get("selection_rows") != 240 or len(tokens) != 90:
        raise ValueError("inner selection cardinality differs")
    return dict(result), tokens


def _run_outer_cells(
    coordinator: _Coordinator,
    private_root: Path,
    projection_root: Path,
    manifests: Mapping[str, str],
    model_root: Path,
    model_sha: str,
    g0: Mapping[tuple[str, int, int, int | None], Sequence[Mapping[str, Any]]],
    tokens: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, int, int], dict[str, Any]]:
    token_index = {
        (
            _string(item, "system_id"),
            _integer(item, "repeat"),
            _integer(item, "outer_fold"),
        ): item
        for item in tokens
    }
    selected = {
        key: (_optional_number(item.get("alpha")), _optional_number(item.get("lambda")))
        for key, item in token_index.items()
    }
    tasks = outer_pair_tasks(selected)
    output: dict[tuple[str, int, int], dict[str, Any]] = {}
    for index, task in enumerate(tasks):
        relative = _scope_relative("outer", task.repeat, task.outer_fold, None)
        target_family = "c3-target" if task.system_id == "C3" else "cell-target"
        target_root = projection_root / target_family / relative
        target_sha = _receipt(manifests, f"{target_family}/{relative}")
        source_parent = _receipt(manifests, f"cell-target/{relative}")
        roots = g0[("outer", task.repeat, task.outer_fold, None)]
        token_system = "T0" if task.system_id == "F2" else task.system_id
        token = token_index.get((token_system, task.repeat, task.outer_fold))
        base = private_root / "outer-fragments" / f"fragment-{index:03d}"
        base.parent.mkdir(parents=True, exist_ok=True)
        f0_root = base.with_name(base.name + "-f0") if task.shared_outer_t0 else None
        f1_root = base.with_name(base.name + "-f1") if task.shared_outer_t0 else None
        coordinator.command(
            "pair-outer-shared" if task.shared_outer_t0 else "pair-outer",
            pair_command(
                task,
                model_root=model_root,
                model_manifest_sha256=model_sha,
                target_root=target_root,
                target_manifest_sha256=target_sha,
                g0_roots=tuple(_path(item, "root") for item in roots),
                g0_manifest_sha256=tuple(
                    _digest(item, "manifest_sha256") for item in roots
                ),
                source_sha256=candidate_runner_source_bundle_sha256(),
                output_root=base,
                token_root=(None if token is None else _path(token, "root")),
                token_sha256=(None if token is None else _digest(token, "sha256")),
                measured_parent_sha256=(
                    source_parent if task.system_id == "C3" else None
                ),
                f0_output_root=f0_root,
                f1_output_root=f1_root,
            ),
        )
        output[(task.system_id, task.repeat, task.outer_fold)] = (
            coordinator.register_manifest(
                f"outer-{task.system_id}-{task.repeat}-{task.outer_fold}", base
            )
        )
        if task.shared_outer_t0:
            assert f0_root is not None and f1_root is not None
            output[("F0", task.repeat, task.outer_fold)] = (
                coordinator.register_manifest(
                    f"outer-F0-{task.repeat}-{task.outer_fold}", f0_root
                )
            )
            output[("F1", task.repeat, task.outer_fold)] = (
                coordinator.register_manifest(
                    f"outer-F1-{task.repeat}-{task.outer_fold}", f1_root
                )
            )
    if len(output) != 165:
        raise ValueError("outer fragment cardinality differs")
    return output


def _freeze(
    coordinator: _Coordinator,
    private_root: Path,
    fragments: Mapping[tuple[str, int, int], Mapping[str, Any]],
    g0: Mapping[tuple[str, int, int, int | None], Sequence[Mapping[str, Any]]],
    tokens: Sequence[Mapping[str, Any]],
    sealed_outer: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    token_index = {
        (
            _string(item, "system_id"),
            _integer(item, "repeat"),
            _integer(item, "outer_fold"),
        ): item
        for item in tokens
    }
    sealed_index = {
        (_integer(item, "repeat"), _integer(item, "outer_fold")): item
        for item in sealed_outer
    }
    contexts = []
    for repeat in range(3):
        for outer in range(5):
            contexts.append(
                {
                    "repeat": repeat,
                    "outer_fold": outer,
                    "tokens": [
                        {
                            "system_id": system,
                            "repeat": repeat,
                            "outer_fold": outer,
                            "alpha": token_index[(system, repeat, outer)]["alpha"],
                            "lambda": token_index[(system, repeat, outer)]["lambda"],
                            "root": str(
                                _path(token_index[(system, repeat, outer)], "root")
                            ),
                            "sha256": _digest(
                                token_index[(system, repeat, outer)], "sha256"
                            ),
                        }
                        for system in ("C2", "C3", "T0", "A0", "A1", "A2")
                    ],
                    "fragments": [
                        {
                            "system_id": system,
                            "repeat": repeat,
                            "outer_fold": outer,
                            "root": str(
                                _path(fragments[(system, repeat, outer)], "root")
                            ),
                            "manifest_sha256": _digest(
                                fragments[(system, repeat, outer)], "manifest_sha256"
                            ),
                            "operation_accounting": _accounting(
                                fragments[(system, repeat, outer)]
                            ),
                        }
                        for system in (
                            "C0",
                            "C1",
                            "C2",
                            "C3",
                            "T0",
                            "F0",
                            "F1",
                            "F2",
                            "A0",
                            "A1",
                            "A2",
                        )
                    ],
                    "g0": {
                        "repeat": repeat,
                        "outer_fold": outer,
                        "roots": [
                            str(_path(item, "root"))
                            for item in g0[("outer", repeat, outer, None)]
                        ],
                        "manifest_sha256": [
                            _digest(item, "manifest_sha256")
                            for item in g0[("outer", repeat, outer, None)]
                        ],
                    },
                    "eligibility": {
                        "repeat": repeat,
                        "outer_fold": outer,
                        "root": str(_path(sealed_index[(repeat, outer)], "root")),
                        "manifest_sha256": _digest(
                            sealed_index[(repeat, outer)], "manifest_sha256"
                        ),
                        "operation_accounting": _accounting(
                            sealed_index[(repeat, outer)]
                        ),
                    },
                }
            )
    result = coordinator.worker(
        "freezer",
        {
            "contexts": contexts,
            "output_root": str(private_root / "outer-freeze"),
            "freezer_source_sha256": freezer_source_bundle_sha256(),
            "pair_source_sha256": pair_runner_source_bundle_sha256(),
            "g0_source_sha256": g0_source_bundle_sha256(),
        },
    )
    completed = coordinator.register_manifest("outer-freeze", _path(result, "root"))
    result = {**dict(result), **completed}
    if result.get("prediction_rows") != result.get("eligibility_rows", -1) * 12:
        raise ValueError("freeze row accounting differs")
    return dict(result)


def _cleanup_capabilities(
    freeze: Mapping[str, Any],
    inner: Mapping[str, Any],
    sealed_outer: Sequence[Mapping[str, Any]],
    support_root: Path,
    support_sha: str,
    accounting: Mapping[str, Any],
    children: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    result = [
        _cleanup(
            "aggregate-accounting",
            _path(accounting, "root"),
            "accounting.json",
            _digest(accounting, "sha256"),
        ),
        _cleanup(
            "inner-selection",
            _path(inner, "root"),
            "manifest.json",
            _digest(inner, "manifest_sha256"),
        ),
        _cleanup(
            "outer-freeze",
            _path(freeze, "root"),
            "manifest.json",
            _digest(freeze, "manifest_sha256"),
        ),
        _cleanup("prefit-support", support_root, "support.json", support_sha),
    ]
    result.extend(
        _cleanup(
            f"sealed-repeat-{_integer(item, 'repeat')}-fold-{_integer(item, 'outer_fold')}",
            _path(item, "root"),
            "manifest.json",
            _digest(item, "manifest_sha256"),
        )
        for item in sealed_outer
    )
    retained = {_path_from_cleanup(item) for item in result}
    for item in children:
        root = _path(item, "root")
        if root.absolute() in retained:
            continue
        result.append(
            _cleanup(
                f"accounting-child-{_string(item, 'label')}",
                root,
                "manifest.json",
                _digest(item, "manifest_sha256"),
            )
        )
        retained.add(root.absolute())
    result.sort(key=lambda item: cast(str, item["label"]))
    return result


def _remove_token_capabilities(tokens: Sequence[Mapping[str, Any]]) -> None:
    parents: set[Path] = set()
    for item in tokens:
        root = _path(item, "root")
        parents.add(root.parent)
        remove_private_root(root)
    for parent in sorted(parents, reverse=True):
        parent.rmdir()


def _remove_roots(rows: Sequence[Mapping[str, Any]]) -> None:
    for row in rows:
        remove_private_root(_path(row, "root"))


def _prune_empty(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(
        (item for item in root.rglob("*") if item.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        if not any(path.iterdir()):
            path.rmdir()


def _terminal_status(root: Path) -> str:
    manifest = strict_json_object(
        read_stable_file(root / "manifest.json"), "terminal manifest"
    )
    return _string(manifest, "status")


def _scope_relative(stage: str, repeat: int, outer: int, inner: int | None) -> str:
    base = f"{stage}/repeat-{repeat}/outer-{outer}"
    return base if inner is None else f"{base}/inner-{inner}"


def _scope_record(
    stage: str, repeat: int, outer: int, inner: int | None
) -> dict[str, Any]:
    return {"stage": stage, "repeat": repeat, "outer_fold": outer, "inner_fold": inner}


def _sealed_input(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "repeat": _integer(item, "repeat"),
        "outer_fold": _integer(item, "outer_fold"),
        "root": str(_path(item, "root")),
        "manifest_sha256": _digest(item, "manifest_sha256"),
    }


def _root_manifest(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "root": str(_path(item, "root")),
        "manifest_sha256": _digest(item, "manifest_sha256"),
    }


def _cleanup(label: str, root: Path, relative: str, digest: str) -> dict[str, Any]:
    return {
        "label": label,
        "root": str(root),
        "relative_path": relative,
        "sha256": digest,
    }


def _path_from_cleanup(item: Mapping[str, Any]) -> Path:
    return Path(cast(str, item["root"])).absolute()


def _receipt(values: Mapping[str, str], name: str) -> str:
    value = values.get(name)
    if value is None or len(value) != 64:
        raise ValueError(f"runner receipt differs: {name}")
    return value


def _records(value: Mapping[str, Any], name: str) -> list[dict[str, Any]]:
    item = value.get(name)
    if not isinstance(item, list) or any(not isinstance(row, Mapping) for row in item):
        raise ValueError(f"runner records differ: {name}")
    return [dict(cast(Mapping[str, Any], row)) for row in item]


def _strings(value: Mapping[str, Any], name: str) -> tuple[str, ...]:
    item = value.get(name)
    if (
        not isinstance(item, list)
        or not item
        or any(not isinstance(row, str) or not row for row in item)
    ):
        raise ValueError(f"runner strings differ: {name}")
    return tuple(cast(list[str], item))


def _path(value: Mapping[str, Any], name: str) -> Path:
    item = value.get(name)
    if not isinstance(item, str):
        raise ValueError(f"runner path differs: {name}")
    return Path(item)


def _digest(value: Mapping[str, Any], name: str) -> str:
    item = _string(value, name)
    if len(item) != 64 or any(char not in "0123456789abcdef" for char in item):
        raise ValueError(f"runner digest differs: {name}")
    return item


def _string(value: Mapping[str, Any], name: str) -> str:
    item = value.get(name)
    if not isinstance(item, str) or not item:
        raise ValueError(f"runner string differs: {name}")
    return item


def _integer(value: Mapping[str, Any], name: str) -> int:
    item = value.get(name)
    if type(item) is not int:
        raise ValueError(f"runner integer differs: {name}")
    return item


def _optional_number(value: Any) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float):
        raise ValueError("runner selected coordinate differs")
    return float(value)


def _accounting(value: Mapping[str, Any]) -> dict[str, int]:
    item = value.get("operation_accounting")
    if not isinstance(item, Mapping):
        raise ValueError("runner accounting differs")
    return cast(dict[str, int], dict(item))


__all__ = ["run_supported"]

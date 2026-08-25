#!/usr/bin/env python3
"""No-fit and future single-use execution wrapper for G2-7C robustness."""

from __future__ import annotations

import csv
import io
import os
import shutil
import signal
import sys
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Final

import global_v2_maplight_resource_supervisor as supervisor
import global_v2_maplight_robustness_execution_compiler as compiler
import global_v2_maplight_runner as maplight
import numpy as np

SCRIPT: Final = Path(__file__).resolve()
FEATURE_VIEWS: Final = {
    "G2-7-M0-FULL": tuple(item[0] for item in compiler.FEATURE_FILES),
    "G2-7-M1-DROP-MORGAN": tuple(
        item[0] for item in compiler.FEATURE_FILES if "morgan" not in item[0]
    ),
    "G2-7-M2-DROP-AVALON": tuple(
        item[0] for item in compiler.FEATURE_FILES if "avalon" not in item[0]
    ),
    "G2-7-M3-DROP-ERG": tuple(
        item[0] for item in compiler.FEATURE_FILES if "erg" not in item[0]
    ),
    "G2-7-M4-DROP-DESCRIPTORS": tuple(
        item[0] for item in compiler.FEATURE_FILES if "descriptors" not in item[0]
    ),
}
FEATURE_COLUMNS: Final = {
    candidate: sum(
        columns
        for name, columns, _dtype in compiler.FEATURE_FILES
        if name in feature_names
    )
    for candidate, feature_names in FEATURE_VIEWS.items()
}
EXPECTED_FEATURE_COLUMNS: Final = {
    "G2-7-M0-FULL": 2563,
    "G2-7-M1-DROP-MORGAN": 1539,
    "G2-7-M2-DROP-AVALON": 1539,
    "G2-7-M3-DROP-ERG": 2248,
    "G2-7-M4-DROP-DESCRIPTORS": 2363,
}
TERMINAL_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_no_fit_terminal.v1"
)
TERMINAL_FILES: Final = (
    "capability_summary.json",
    "chronology.json",
    "identity_summary.json",
    "manifest.json",
)
OFFICIAL_FIT_COUNTS: Final = {
    "full_retained": {"stage_a": 540, "stage_b": 180, "stage_c": 0, "total": 720},
    "deletion_selected": {
        "stage_a": 540,
        "stage_b": 180,
        "stage_c": 300,
        "total": 1020,
    },
}
OFFICIAL_PREDICTION_COUNTS: Final = {
    "full_retained": {
        "stage_a": 422064,
        "stage_b": 140688,
        "stage_c": 0,
        "minimum_total": 562752,
        "maximum_total": 562752,
    },
    "deletion_selected": {
        "stage_a": 422064,
        "stage_b": 140688,
        "stage_c": 234480,
        "minimum_total": 797232,
        "maximum_total": 797232,
    },
}

Checkpoint = Callable[[str], None]


class RobustnessExecutionWrapperError(RuntimeError):
    """A capability, identity, chronology, cleanup, or terminal check failed."""


@dataclass(frozen=True)
class FitIdentity:
    stage: str
    candidate_id: str
    random_seed: int
    group_id: str
    endpoint: str
    repeat: int
    outer_fold: int

    @property
    def token(self) -> str:
        return "|".join(str(value) for value in asdict(self).values())


class LocalCheckpointRecorder:
    """Mechanics-only checkpoint recorder with no resource authority."""

    def __init__(self) -> None:
        self.labels: list[str] = []

    def __call__(self, label: str) -> None:
        _require(
            label.startswith(("before:", "after:", "stage:")),
            "checkpoint label differs",
        )
        self.labels.append(label)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RobustnessExecutionWrapperError(message)


def _safe_cleanup(root: Path) -> None:
    resolved = root.resolve(strict=False)
    _require(
        root.is_absolute()
        and ".." not in root.parts
        and resolved not in {Path("/"), Path.home()}
        and len(resolved.parts) >= 4,
        "cleanup root is unsafe",
    )
    if not resolved.exists():
        return
    _require(resolved.is_dir() and not resolved.is_symlink(), "cleanup root differs")
    for path in sorted(
        resolved.rglob("*"), key=lambda item: len(item.parts), reverse=True
    ):
        _require(not path.is_symlink(), "cleanup root contains a symlink")
        try:
            os.chmod(path, 0o755 if path.is_dir() else 0o600)
        except OSError:
            pass
    os.chmod(resolved, 0o700)
    shutil.rmtree(resolved)


def _read_manifest(root: Path, schema: str, label: str) -> dict[str, Any]:
    maplight._readonly_root(root, label)
    manifest = compiler._load_json(root / "manifest.json")
    _require(
        manifest.get("schema_version") == schema
        and manifest.get("synthetic") is True
        and manifest.get("bounded_contract_sha256") == compiler.BOUNDED_CONTRACT_SHA256
        and manifest.get("parent_contract_sha256") == compiler.PARENT_CONTRACT_SHA256
        and manifest.get("compiler_source_sha256")
        == maplight.sha256_path(compiler.SCRIPT)
        and manifest.get("accounting") == compiler._zero_accounting(),
        f"{label} identity differs",
    )
    return manifest


def _load_model_capability(
    root: Path,
) -> tuple[
    dict[str, Any],
    list[dict[str, str]],
    dict[tuple[str, int, str], tuple[str, str, int]],
]:
    manifest = _read_manifest(root, compiler.MODEL_SCHEMA, "model capability")
    folds = maplight._read_csv(root / "folds.csv", compiler.CAPABILITY_FOLD_COLUMNS)
    _require(
        maplight.sha256_path(root / "folds.csv") == manifest.get("folds_sha256"),
        "fold receipt differs",
    )
    fold_map: dict[tuple[str, int, str], tuple[str, str, int]] = {}
    for row in folds:
        key = row["molecule_id"], int(row["repeat"]), row["group_id"]
        value = (
            row["standardized_structure_hash"],
            row["component_hash"],
            int(row["outer_fold"]),
        )
        _require(
            key not in fold_map
            and row["group_id"] in compiler.GROUPS
            and int(row["repeat"]) in compiler.REPEATS
            and int(row["outer_fold"]) in compiler.OUTER_FOLDS
            and compiler._is_sha(row["standardized_structure_hash"])
            and compiler._is_sha(row["component_hash"]),
            "active fold identity differs",
        )
        fold_map[key] = value
    _require(bool(fold_map), "active folds are empty")

    feature_receipts = manifest.get("feature_receipts")
    _require(isinstance(feature_receipts, Mapping), "feature receipts differ")
    molecules = manifest.get("molecules")
    _require(isinstance(molecules, int) and molecules > 0, "model population differs")
    for name, columns, dtype in compiler.FEATURE_FILES:
        path = maplight._regular(root / name, f"feature {name}")
        _require(
            maplight.sha256_path(path) == feature_receipts.get(name),
            "feature receipt differs",
        )
        array = np.load(path, allow_pickle=False, mmap_mode="r")
        _require(
            array.shape == (molecules, columns) and array.dtype == dtype,
            f"feature shape differs: {name}",
        )
    _require(FEATURE_COLUMNS == EXPECTED_FEATURE_COLUMNS, "feature views differ")
    return manifest, folds, fold_map


def _fit_identities(stage: str, selected: str | None = None) -> list[FitIdentity]:
    identities: list[FitIdentity] = []
    if stage == "stage_a":
        forms = [
            (candidate, 1, "PRIMARY_D032")
            for candidate in compiler.CANDIDATES
            if candidate != "G2-7-M0-FULL"
        ]
        forms.extend(
            ("G2-7-M0-FULL", seed, "PRIMARY_D032")
            for seed in compiler.SEED_PERTURBATIONS
        )
    elif stage == "stage_b":
        _require(selected in compiler.CANDIDATES, "stage-B selection differs")
        assert selected is not None
        forms = [(selected, 1, group) for group in compiler.GROUPS[1:]]
    elif stage == "stage_c":
        _require(
            selected in compiler.CANDIDATES[1:],
            "stage-C requires one selected deletion",
        )
        assert selected is not None
        forms = [
            (selected, seed, "PRIMARY_D032") for seed in compiler.SEED_PERTURBATIONS
        ]
    else:
        raise RobustnessExecutionWrapperError("stage identity differs")
    for candidate, seed, group in forms:
        for endpoint in compiler.ENDPOINTS:
            for repeat in compiler.REPEATS:
                for fold in compiler.OUTER_FOLDS:
                    identities.append(
                        FitIdentity(
                            stage=stage,
                            candidate_id=candidate,
                            random_seed=seed,
                            group_id=group,
                            endpoint=endpoint,
                            repeat=repeat,
                            outer_fold=fold,
                        )
                    )
    return identities


def _target_path(model_root: Path, identity: FitIdentity) -> Path:
    return (
        model_root
        / "targets"
        / identity.group_id
        / f"r{identity.repeat}"
        / f"f{identity.outer_fold}"
        / f"{identity.endpoint}.csv"
    )


def _execute_stage(
    *,
    stage: str,
    identities: Sequence[FitIdentity],
    model_root: Path,
    model_manifest: Mapping[str, Any],
    fold_map: Mapping[tuple[str, int, str], tuple[str, str, int]],
    work_root: Path,
    checkpoint: Checkpoint,
) -> dict[str, Any]:
    checkpoint(f"before:{stage}")
    target_receipts = model_manifest.get("target_capabilities")
    _require(isinstance(target_receipts, Mapping), "target capability receipts differ")
    digest = sha256()
    predictions = 0
    feature_view_counts: dict[str, int] = defaultdict(int)
    for identity in identities:
        checkpoint(f"before:fit:{identity.token}")
        relative = _target_path(model_root, identity).relative_to(model_root).as_posix()
        target_path = maplight._regular(
            model_root / relative, "training target capability"
        )
        target_raw = target_path.read_bytes()
        _require(
            maplight.sha256_bytes(target_raw) == target_receipts.get(relative),
            "training target capability receipt differs",
        )
        training = list(
            csv.DictReader(io.StringIO(target_raw.decode("utf-8"), newline=""))
        )
        _require(
            bool(training)
            and list(training[0]) == list(maplight.TARGET_COLUMNS)
            and all(None not in row for row in training),
            "training target capability differs",
        )
        validation = sorted(
            molecule
            for molecule, repeat, group in fold_map
            if repeat == identity.repeat
            and group == identity.group_id
            and fold_map[(molecule, repeat, group)][2] == identity.outer_fold
        )
        training_ids = {row["molecule_id"] for row in training}
        _require(
            bool(validation)
            and not training_ids.intersection(validation)
            and all(
                key in fold_map and fold_map[key][2] != identity.outer_fold
                for key in (
                    (molecule, identity.repeat, identity.group_id)
                    for molecule in training_ids
                )
            ),
            "training/validation molecule boundary differs",
        )
        train_components = {
            fold_map[(molecule, identity.repeat, identity.group_id)][1]
            for molecule in training_ids
        }
        validation_components = {
            fold_map[(molecule, identity.repeat, identity.group_id)][1]
            for molecule in validation
        }
        train_structures = {
            fold_map[(molecule, identity.repeat, identity.group_id)][0]
            for molecule in training_ids
        }
        validation_structures = {
            fold_map[(molecule, identity.repeat, identity.group_id)][0]
            for molecule in validation
        }
        _require(
            train_components.isdisjoint(validation_components),
            "active component crosses a fit",
        )
        _require(
            train_structures.isdisjoint(validation_structures),
            "exact duplicate crosses a fit",
        )
        _require(
            identity.candidate_id in FEATURE_VIEWS
            and FEATURE_COLUMNS[identity.candidate_id]
            == EXPECTED_FEATURE_COLUMNS[identity.candidate_id],
            "fit feature view differs",
        )
        digest.update(identity.token.encode())
        digest.update(maplight.sha256_bytes(target_raw).encode())
        for molecule in validation:
            digest.update(
                sha256(
                    f"g2-7c-model-double-v1|{identity.token}|{molecule}".encode()
                ).digest()
            )
        predictions += len(validation)
        feature_view_counts[identity.candidate_id] += 1
        checkpoint(f"after:fit:{identity.token}")

    freeze = {
        "schema_version": (
            "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_prediction_freeze.v1"
        ),
        "stage": stage,
        "model_double_invocations": len(identities),
        "prediction_identities": predictions,
        "aggregate_prediction_receipt": digest.hexdigest(),
        "feature_view_fit_counts": dict(sorted(feature_view_counts.items())),
        "row_level_values_retained": 0,
        "real_model_fits": 0,
    }
    frozen = maplight.publish_files(
        work_root / f"{stage}-freeze", {"manifest.json": maplight.json_bytes(freeze)}
    )
    _require(frozen.is_dir(), "stage freeze publication failed")
    checkpoint(f"after:{stage}")
    return freeze


def _open_stage_scorer(
    *, scorer_root: Path, scorer_manifest: Mapping[str, Any], stage: str
) -> tuple[int, str]:
    receipts = scorer_manifest.get("truth_receipts")
    _require(isinstance(receipts, Mapping), "scorer truth receipts differ")
    path = maplight._regular(
        scorer_root / f"{stage}_truth.csv", f"{stage} scorer truth"
    )
    raw = path.read_bytes()
    _require(
        maplight.sha256_bytes(raw) == receipts.get(stage), "stage truth receipt differs"
    )
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"), newline="")))
    _require(
        len(rows) == scorer_manifest.get("truth_rows")
        and all(None not in row for row in rows)
        and all(row["endpoint"] in compiler.ENDPOINTS for row in rows),
        "stage truth identity differs",
    )
    # Point strings stay opaque: this gate validates capability chronology and
    # row identity but performs no numeric parse or metric operation.
    identity_receipt = maplight.sha256_bytes(
        maplight.json_bytes(
            sorted((row["molecule_id"], row["endpoint"]) for row in rows)
        )
    )
    return len(rows), identity_receipt


def _selection_after_stage_a(*, scorer_root: Path, profile: str) -> str:
    _require(
        profile in {"full_retained", "deletion_selected"}, "selection profile differs"
    )
    oracles = compiler._load_json(scorer_root / "selection_oracles.json")
    selected = oracles.get(profile)
    _require(selected in compiler.CANDIDATES, "selection oracle differs")
    assert isinstance(selected, str)
    return selected


def _terminal_files(
    *,
    selection_profile: str,
    selected_candidate: str,
    stages: Mapping[str, Mapping[str, Any]],
    truth_opens: Mapping[str, Mapping[str, Any]],
    checkpoint_labels: Sequence[str],
) -> dict[str, bytes]:
    counts = {
        stage: int(values["model_double_invocations"])
        for stage, values in stages.items()
    }
    predictions = {
        stage: int(values["prediction_identities"]) for stage, values in stages.items()
    }
    total_fits = sum(counts.values())
    _require(
        total_fits == OFFICIAL_FIT_COUNTS[selection_profile]["total"],
        "fit topology differs",
    )
    identity_summary = {
        "selection_profile": selection_profile,
        "selected_candidate": selected_candidate,
        "synthetic_model_double_invocations": counts,
        "synthetic_prediction_identities": predictions,
        "official_future_fit_identities": OFFICIAL_FIT_COUNTS[selection_profile],
        "official_future_prediction_identities": OFFICIAL_PREDICTION_COUNTS[
            selection_profile
        ],
        "selection_tokens": 1,
        "runner_ups": 0,
        "deployable_clips": 0,
        "retained_model_binaries": 0,
    }
    chronology = {
        "stage_order": list(stages),
        "prediction_freezes_before_matching_truth": True,
        "selection_after_complete_stage_a_freeze": True,
        "stage_truth_capabilities_opened": truth_opens,
        "numeric_truth_values_parsed": 0,
        "development_metric_evaluations": 0,
        "warnings_observed": 0,
        "fallbacks_observed": 0,
        "checkpoint_labels_sha256": maplight.sha256_bytes(
            maplight.json_bytes(list(checkpoint_labels))
        ),
        "checkpoints_acknowledged": len(checkpoint_labels),
    }
    capability = {
        "candidates": list(compiler.CANDIDATES),
        "seed_perturbations": list(compiler.SEED_PERTURBATIONS),
        "group_perturbations": list(compiler.GROUPS[1:]),
        "feature_columns": EXPECTED_FEATURE_COLUMNS,
        "family_boundaries_checked": [
            "molecule",
            "exact_duplicate",
            "PRIMARY_D032",
            "THRESHOLD_0_55",
            "THRESHOLD_0_50",
            "TAUTOMER_MERGED",
            "confirmatory_touch_exclusion",
        ],
        "real_catboost_fits": 0,
        "resource_projections": 0,
        "accounting": compiler._zero_accounting(),
    }
    manifest = {
        "schema_version": TERMINAL_SCHEMA,
        "status": "G2_7C_NO_FIT_MECHANICS_PASS",
        "bounded_contract_sha256": compiler.BOUNDED_CONTRACT_SHA256,
        "parent_contract_sha256": compiler.PARENT_CONTRACT_SHA256,
        "compiler_source_sha256": maplight.sha256_path(compiler.SCRIPT),
        "wrapper_source_sha256": maplight.sha256_path(SCRIPT),
        "selection_profile": selection_profile,
        "selected_candidate": selected_candidate,
        "model_double_invocations": total_fits,
        "real_catboost_fits": 0,
        "development_metric_evaluations": 0,
        "warnings_observed": 0,
        "fallbacks_observed": 0,
        "confirmatory_target_values_parsed": 0,
        "row_level_values_retained": 0,
        "cleanup_complete": True,
        "model_quality_authority": False,
        "claim_authority": False,
        "accounting": compiler._zero_accounting(),
    }
    return {
        "capability_summary.json": maplight.json_bytes(capability),
        "chronology.json": maplight.json_bytes(chronology),
        "identity_summary.json": maplight.json_bytes(identity_summary),
        "manifest.json": maplight.json_bytes(manifest),
    }


def run_no_fit_replay(
    *,
    model_capability_root: Path,
    scorer_capability_root: Path,
    work_root: Path,
    output_root: Path,
    selection_profile: str,
    checkpoint: Checkpoint = supervisor.resource_checkpoint,
) -> Path:
    """Exercise one exact conditional identity path with a model double."""

    _require(
        not work_root.exists() and not output_root.exists(), "execution root exists"
    )
    model_manifest, _fold_rows, fold_map = _load_model_capability(model_capability_root)
    work_root.mkdir(parents=True)
    stages: dict[str, Mapping[str, Any]] = {}
    truth_opens: dict[str, Mapping[str, Any]] = {}
    recorder = checkpoint if isinstance(checkpoint, LocalCheckpointRecorder) else None
    try:
        stage_a = _execute_stage(
            stage="stage_a",
            identities=_fit_identities("stage_a"),
            model_root=model_capability_root,
            model_manifest=model_manifest,
            fold_map=fold_map,
            work_root=work_root,
            checkpoint=checkpoint,
        )
        stages["stage_a"] = stage_a
        scorer_manifest = _read_manifest(
            scorer_capability_root, compiler.SCORER_SCHEMA, "stage-A scorer capability"
        )
        truth_count, truth_receipt = _open_stage_scorer(
            scorer_root=scorer_capability_root,
            scorer_manifest=scorer_manifest,
            stage="stage_a",
        )
        truth_opens["stage_a"] = {
            "identity_rows": truth_count,
            "identity_receipt": truth_receipt,
        }
        selected = _selection_after_stage_a(
            scorer_root=scorer_capability_root, profile=selection_profile
        )
        stage_b = _execute_stage(
            stage="stage_b",
            identities=_fit_identities("stage_b", selected),
            model_root=model_capability_root,
            model_manifest=model_manifest,
            fold_map=fold_map,
            work_root=work_root,
            checkpoint=checkpoint,
        )
        stages["stage_b"] = stage_b
        truth_count, truth_receipt = _open_stage_scorer(
            scorer_root=scorer_capability_root,
            scorer_manifest=scorer_manifest,
            stage="stage_b",
        )
        truth_opens["stage_b"] = {
            "identity_rows": truth_count,
            "identity_receipt": truth_receipt,
        }
        if selected != "G2-7-M0-FULL":
            stage_c = _execute_stage(
                stage="stage_c",
                identities=_fit_identities("stage_c", selected),
                model_root=model_capability_root,
                model_manifest=model_manifest,
                fold_map=fold_map,
                work_root=work_root,
                checkpoint=checkpoint,
            )
            stages["stage_c"] = stage_c
            truth_count, truth_receipt = _open_stage_scorer(
                scorer_root=scorer_capability_root,
                scorer_manifest=scorer_manifest,
                stage="stage_c",
            )
            truth_opens["stage_c"] = {
                "identity_rows": truth_count,
                "identity_receipt": truth_receipt,
            }
        labels = recorder.labels if recorder is not None else []
        terminal_files = _terminal_files(
            selection_profile=selection_profile,
            selected_candidate=selected,
            stages=stages,
            truth_opens=truth_opens,
            checkpoint_labels=labels,
        )
    finally:
        _safe_cleanup(work_root)
    _require(not work_root.exists(), "work cleanup is incomplete")
    return maplight.publish_files(output_root, terminal_files)


def _helper_command(source: str) -> list[str]:
    prefix = (
        "import importlib.util,pathlib,sys;"
        f"p=pathlib.Path({str(supervisor.SCRIPT)!r});"
        "s=importlib.util.spec_from_file_location('g2sup',p);"
        "m=importlib.util.module_from_spec(s);sys.modules['g2sup']=m;"
        "s.loader.exec_module(m);"
    )
    return [sys.executable, "-c", prefix + source]


def exercise_supervisor_acceptance(*, work_root: Path) -> dict[str, Any]:
    """Prove success and each fail-stop class without a model fit."""

    _require(not work_root.exists(), "supervisor acceptance root exists")
    work_root.mkdir(parents=True)
    generous = supervisor.ResourceLimits(
        wall_seconds=5.0,
        cpu_seconds=5.0,
        storage_bytes=20_000_000,
        rss_bytes=1_000_000_000,
    )
    success = supervisor.run_supervised(
        _helper_command(
            "import os,socket;"
            "assert all(os.environ.get(n,'')=='' for n in m.GPU_ENVIRONMENT_NAMES);"
            "assert not any(pathlib.Path('/dev').glob('nvidia*'));"
            "assert not pathlib.Path('/dev/dri').exists();"
            "assert socket.if_nameindex()==[(1,'lo')];"
            "m.resource_checkpoint('stage:success')"
        ),
        restricted_root=work_root / "success" / "restricted",
        limits=generous,
        poll_interval_seconds=0.02,
    )
    scenarios = {
        "wall": (
            "import time;m.resource_checkpoint('before:wall');time.sleep(2)",
            supervisor.ResourceLimits(0.12, 5, 20_000_000, 1_000_000_000),
        ),
        "cpu": (
            "m.resource_checkpoint('before:cpu');x=0\nwhile True:x+=1",
            supervisor.ResourceLimits(5, 0.12, 20_000_000, 1_000_000_000),
        ),
        "storage": (
            "m.resource_checkpoint('before:storage');"
            f"open(os.environ[{supervisor.CHECKPOINT_ENV!r}].rsplit('/',1)[0]+'/large','wb').write(b'x'*2000000);"
            "import time;time.sleep(1)",
            supervisor.ResourceLimits(5, 5, 100_000, 1_000_000_000),
        ),
        "warning": (
            "m.resource_checkpoint('before:warning');"
            "print('synthetic warning',file=sys.stderr)",
            generous,
        ),
        "signal": (
            f"import os,signal;m.resource_checkpoint('before:signal');os.kill(os.getpid(),{signal.SIGTERM})",
            generous,
        ),
        "detached": (
            "import os,time;m.resource_checkpoint('before:detached');"
            "pid=os.fork();"
            "(os.setsid(),time.sleep(2)) if pid==0 else time.sleep(2)",
            generous,
        ),
        "nonzero": (
            "m.resource_checkpoint('before:nonzero');sys.exit(7)",
            generous,
        ),
        "missing_checkpoint": ("pass", generous),
    }
    own = supervisor._process_stat(os.getpid())
    _require(own is not None, "supervisor parent process is unobservable")
    scenarios["rss"] = (
        "import time;m.resource_checkpoint('before:rss');"
        "x=bytearray(80000000);time.sleep(1)",
        supervisor.ResourceLimits(5, 5, 20_000_000, own.rss_bytes + 50_000_000),
    )
    rejected: dict[str, bool] = {}
    for name, (source, limits) in scenarios.items():
        try:
            supervisor.run_supervised(
                _helper_command(source),
                restricted_root=work_root / name / "restricted",
                limits=limits,
                poll_interval_seconds=0.02,
            )
        except supervisor.ResourceSupervisorError:
            rejected[name] = True
        else:
            rejected[name] = False
    publication_parent = work_root / "publication"
    publication_parent.mkdir()
    partial_publication = publication_parent / "terminal"
    partial_source = (
        f"import os,time;os.mkdir({str(partial_publication)!r});"
        f"open({str(partial_publication / 'partial')!r},'wb').write(b'partial');"
        "m.resource_checkpoint('before:partial-publication');time.sleep(2)"
    )
    try:
        supervisor.run_supervised(
            _helper_command(partial_source),
            restricted_root=work_root / "partial-publication" / "restricted",
            limits=supervisor.ResourceLimits(0.12, 5, 20_000_000, 1_000_000_000),
            poll_interval_seconds=0.02,
            writable_publication_parent=publication_parent,
            publication_root=partial_publication,
        )
    except supervisor.ResourceSupervisorError:
        rejected["partial_publication"] = not partial_publication.exists()
    else:
        rejected["partial_publication"] = False
    _require(all(rejected.values()), "supervisor did not reject every fault")
    _safe_cleanup(work_root)
    return {
        "success": asdict(success),
        "fail_stop_scenarios": rejected,
        "restricted_roots_retained": 0,
        "real_catboost_fits": 0,
        "resource_projection_authority": False,
    }

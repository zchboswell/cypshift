"""Locked-runtime and episode-capability tests for R5C TRACE G0."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import numpy as np
import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "research/maplight-fixed/run_r5_oracle_g0.py"
LOCKED_PYTHON = ROOT / "research/maplight-fixed/.venv/bin/python"
VIEW_BUILDER_SHA = "4" * 64
SOURCE_CELL_SHA = "5" * 64
spec = importlib.util.spec_from_file_location("r5_g0", SCRIPT)
assert spec is not None and spec.loader is not None
g0 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = g0
spec.loader.exec_module(g0)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def _csv(columns: tuple[str, ...], rows: Sequence[Mapping[str, object]]) -> bytes:
    return cast(bytes, g0.bound.csv_bytes(columns, rows))


def _npy(array: np.ndarray[Any, Any]) -> bytes:
    stream = io.BytesIO()
    np.save(stream, array, allow_pickle=False)
    return stream.getvalue()


def _receipt(
    name: str, data: bytes, columns: tuple[str, ...] | None = None
) -> dict[str, object]:
    result: dict[str, object] = {"sha256": _sha(data), "bytes": len(data)}
    if name.endswith(".csv"):
        assert columns is not None
        result.update(rows=data.count(b"\n") - 1, columns=list(columns))
    return result


def _binding() -> dict[str, object]:
    parents = {"direct_observations.csv": "1" * 64}
    inputs = {
        "direct_observations.csv": {
            "sha256": parents["direct_observations.csv"],
            "bytes": 456,
        }
    }
    return {
        "manifest_receipt": {"sha256": "3" * 64, "bytes": 123},
        "schema_version": "cypshift.openadmet_cyp_2026.oracle_source_bundle.v1",
        "contract_sha256": g0.CONTRACT_SHA256,
        "parent_receipts": parents,
        "input_receipts": inputs,
        "source_receipts": dict(inputs),
    }


def _readonly(root: Path) -> None:
    for path in root.iterdir():
        path.chmod(0o444)
    root.chmod(0o555)


def _fixture(tmp_path: Path) -> tuple[Path, str, Path, str]:
    model = tmp_path / "model-public"
    episode_root = tmp_path / "episode-target"
    model.mkdir()
    episode_root.mkdir()
    train_ids = [f"train{i:03d}" for i in range(100)]
    ids = sorted(["anchor", "query", *train_ids])
    molecules = [
        {
            "molecule_id": molecule_id,
            "raw_smiles": "CC",
            "raw_structure_sha256": _sha(f"raw-{molecule_id}".encode()),
            "standardized_smiles": "CC",
            "standardized_structure_hash": _sha(f"std-{molecule_id}".encode()),
            "similarity_component_hash": (
                "heldout"
                if molecule_id in {"anchor", "query"}
                else f"train-{molecule_id}"
            ),
        }
        for molecule_id in ids
    ]
    folds: list[dict[str, object]] = []
    for molecule in molecules:
        assigned = 4 if molecule["molecule_id"] in {"anchor", "query"} else 0
        for repeat in range(3):
            for current_outer in range(5):
                folds.append(
                    {
                        "molecule_id": molecule["molecule_id"],
                        "similarity_component_hash": molecule[
                            "similarity_component_hash"
                        ],
                        "repeat": repeat,
                        "seed": 20260810 + repeat,
                        "outer_fold": assigned,
                        "outer_validation_fold": current_outer,
                        "inner_fold": "" if assigned == current_outer else 1,
                    }
                )
    public = [
        {
            "episode_id": "episode-1",
            "episode_policy_id": "selected_anchor",
            "repeat": 0,
            "outer_fold": 4,
            "outer_group_id": "heldout",
            "anchor_molecule_id": "anchor",
            "query_molecule_id": "query",
            "query_rank": 1,
        }
    ]
    rng = np.random.default_rng(20260820)
    row_count = len(ids)
    model_files: dict[str, bytes] = {
        "molecules.csv": _csv(g0.MOLECULE_COLUMNS, molecules),
        "folds.csv": _csv(g0.FOLD_COLUMNS, folds),
        "public_episode_queries.csv": _csv(g0.PUBLIC_COLUMNS, public),
        "transformation_pairs.csv": b"placeholder\n",
        "episode_transformations.csv": b"placeholder\n",
        "maplight_morgan_count.npy": _npy(
            rng.integers(0, 4, (row_count, 1024), dtype=np.int8)
        ),
        "maplight_avalon_count.npy": _npy(
            rng.integers(0, 2, (row_count, 1024), dtype=np.int8)
        ),
        "maplight_erg.npy": _npy(rng.normal(size=(row_count, 315)).astype("<f8")),
        "maplight_rdkit_descriptors.npy": _npy(
            rng.normal(size=(row_count, 200)).astype("<f8")
        ),
        "morgan_binary.npy": _npy(
            rng.integers(0, 2, (row_count, 4096), dtype=np.uint8)
        ),
    }
    model_columns = {
        "molecules.csv": g0.MOLECULE_COLUMNS,
        "folds.csv": g0.FOLD_COLUMNS,
        "public_episode_queries.csv": g0.PUBLIC_COLUMNS,
        "transformation_pairs.csv": ("placeholder",),
        "episode_transformations.csv": ("placeholder",),
    }
    for name, data in model_files.items():
        (model / name).write_bytes(data)
    zero = dict.fromkeys(g0.bound.ACCOUNTING_FIELDS, 0)
    binding = _binding()
    model_manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.oracle_projection.v1",
        "status": "R5_ORACLE_SYNTHETIC_CAPABILITY_PROJECTION",
        "contract_sha256": g0.CONTRACT_SHA256,
        "parent_contract_sha256": g0.PARENT_CONTRACT_SHA256,
        "root": "model-public",
        "fixed_oof_system_id": g0.MODEL_ID,
        "current_cell_scope": "all",
        "capability_root_accounting": g0.bound.ROOT_ACCOUNTING,
        "accounting_scope": "values present in this capability root",
        "operation_accounting": zero,
        "projector_operation_accounting": zero,
        "output_receipts": {
            name: _receipt(name, data, model_columns.get(name))
            for name, data in model_files.items()
        },
        "source_receipts": {
            name: {"sha256": _sha(data), "bytes": len(data)}
            for name, data in model_files.items()
        },
        "source_bundle_binding": binding,
        "authority": g0.bound.DENIED_AUTHORITY,
        "forbidden_fields": g0.bound.FORBIDDEN_PUBLIC_FIELDS,
    }
    model_manifest_data = _json(model_manifest)
    (model / "manifest.json").write_bytes(model_manifest_data)

    points = [
        {
            "molecule_id": molecule_id,
            "component_id": f"train-{molecule_id}",
            "point": format(1.0 + index / 50.0, ".17g"),
            "sample_weight": "1.0",
        }
        for index, molecule_id in enumerate(train_ids)
    ]
    anchors = [
        {
            "episode_id": "episode-1",
            "anchor_molecule_id": "anchor",
            "anchor_point": "2.75",
        }
    ]
    episode_files = {
        "training_points.csv": _csv(g0.POINT_COLUMNS, points),
        "episode_anchor_context.csv": _csv(g0.ANCHOR_COLUMNS, anchors),
    }
    for name, data in episode_files.items():
        (episode_root / name).write_bytes(data)
    operation = dict(zero)
    operation["direct_target_values_parsed"] = 101
    operation["anchor_labels_exposed_to_models"] = 1
    episode_manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.r5c_g0_episode_view.v1",
        "status": "R5_ORACLE_EPISODE_TARGET_VIEW",
        "contract_sha256": g0.CONTRACT_SHA256,
        "parent_contract_sha256": g0.PARENT_CONTRACT_SHA256,
        "root": "episode-target",
        "view_builder_source_sha256": VIEW_BUILDER_SHA,
        "model_public_manifest_sha256": _sha(model_manifest_data),
        "source_cell_target_manifest_sha256": SOURCE_CELL_SHA,
        "source_bundle_binding": binding,
        "scope": {
            "stage": "outer",
            "repeat": 0,
            "current_outer_validation_fold": 4,
            "inner_fold": "",
            "episode_outer_fold": 4,
        },
        "episode": {
            "episode_id": "episode-1",
            "anchor_molecule_id": "anchor",
            "query_rows": 1,
            "query_rows_sha256": _sha(_csv(g0.PUBLIC_COLUMNS, public)),
        },
        "r3c_parameter_source": g0.bound.R3C_PARAMETER_SOURCE,
        "output_receipts": {
            name: _receipt(
                name,
                data,
                (
                    g0.POINT_COLUMNS
                    if name == "training_points.csv"
                    else g0.ANCHOR_COLUMNS
                ),
            )
            for name, data in episode_files.items()
        },
        "operation_accounting": operation,
        "authority": g0.bound.DENIED_AUTHORITY,
    }
    episode_manifest_data = _json(episode_manifest)
    (episode_root / "manifest.json").write_bytes(episode_manifest_data)
    _readonly(model)
    _readonly(episode_root)
    return model, _sha(model_manifest_data), episode_root, _sha(episode_manifest_data)


def _argv(
    model: Path, model_sha: str, episode: Path, episode_sha: str, output: Path
) -> list[str]:
    return [
        str(LOCKED_PYTHON),
        str(SCRIPT),
        "--model-public-root",
        str(model),
        "--model-public-manifest-sha256",
        model_sha,
        "--episode-target-root",
        str(episode),
        "--episode-target-manifest-sha256",
        episode_sha,
        "--expected-source-bundle-sha256",
        g0._source_bundle_sha(),
        "--expected-episode-view-builder-source-sha256",
        VIEW_BUILDER_SHA,
        "--expected-source-cell-target-manifest-sha256",
        SOURCE_CELL_SHA,
        "--output-root",
        str(output),
    ]


@pytest.mark.skipif(
    not LOCKED_PYTHON.is_file(), reason="locked research runtime unavailable"
)
def test_actual_locked_catboost_replay_is_byte_stable(tmp_path: Path) -> None:
    model, model_sha, episode, episode_sha = _fixture(tmp_path)
    first, second = tmp_path / "out-1", tmp_path / "out-2"
    for output in (first, second):
        result = subprocess.run(
            _argv(model, model_sha, episode, episode_sha, output),
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
            env={"PATH": os.environ.get("PATH", "")},
        )
        assert result.returncode == 0, result.stderr
    assert (first / "manifest.json").read_bytes() == (
        second / "manifest.json"
    ).read_bytes()
    assert (first / "prediction_fragment.csv").read_bytes() == (
        second / "prediction_fragment.csv"
    ).read_bytes()
    receipt = json.loads((first / "manifest.json").read_bytes())
    assert receipt["status"] == "R5_ORACLE_G0_EPISODE_COMPLETE"
    assert receipt["g0_source_bundle_sha256"] == g0._source_bundle_sha()
    assert receipt["trusted_episode_parent_receipts"] == {
        "episode_view_builder_source_sha256": VIEW_BUILDER_SHA,
        "source_cell_target_manifest_sha256": SOURCE_CELL_SHA,
    }
    assert receipt["counts"] == {
        "current_training_points": 100,
        "anchor_rows": 1,
        "fit_rows": 101,
        "query_rows": 1,
    }
    assert (
        _sha(_json(receipt["resolved_catboost_parameters"]))
        == g0.bound.PARAMETER_SHA256
    )
    assert all(not path.stat().st_mode & 0o222 for path in first.iterdir())


def test_fit_boundary_and_episode_row_exposure_are_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, model_sha, episode, episode_sha = _fixture(tmp_path)
    calls: dict[str, Any] = {}

    class FakeModel:
        def __init__(self, **kwargs: Any) -> None:
            calls["constructor"] = kwargs

        def fit(self, X: Any, y: Any, *args: Any, **kwargs: Any) -> None:
            calls["fit"] = (np.asarray(X), np.asarray(y), args, kwargs)

        def get_all_params(self) -> dict[str, Any]:
            return dict(g0.bound.ACCEPTED_PARAMETERS)

        def predict(self, X: Any) -> np.ndarray[Any, Any]:
            return np.full(len(X), 2.5)

    fake = ModuleType("catboost")
    fake.CatBoostRegressor = FakeModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "catboost", fake)
    monkeypatch.setattr(g0.bound, "runtime", lambda: {"platform": "Linux x86_64 CPU"})
    g0.run_g0(
        model_public_root=model,
        model_public_manifest_sha256=model_sha,
        episode_target_root=episode,
        episode_target_manifest_sha256=episode_sha,
        expected_source_bundle_sha256=g0._source_bundle_sha(),
        expected_episode_view_builder_source_sha256=VIEW_BUILDER_SHA,
        expected_source_cell_target_manifest_sha256=SOURCE_CELL_SHA,
        output_root=tmp_path / "out",
    )
    X, y, args, kwargs = calls["fit"]
    assert calls["constructor"] == g0.CATBOOST_ARGS
    assert args == () and kwargs == {}
    assert X.shape == (101, 2563)
    assert y.shape == (101,) and y[-1] == 2.75
    assert set(y[:-1]) == {1.0 + index / 50.0 for index in range(100)}


def test_extra_file_symlink_and_no_overwrite_fail_closed(tmp_path: Path) -> None:
    model, model_sha, episode, episode_sha = _fixture(tmp_path)
    model.chmod(0o755)
    (model / "sealed-scorer").write_bytes(b"forbidden")
    (model / "sealed-scorer").chmod(0o444)
    model.chmod(0o555)
    with pytest.raises(g0.G0Error, match="model-public file set differs"):
        g0.bound.load_model(model, model_sha)
    model.chmod(0o755)
    (model / "sealed-scorer").unlink()
    model.chmod(0o555)
    link = tmp_path / "episode-link"
    link.symlink_to(episode, target_is_directory=True)
    model_manifest = g0.bound.load_model(model, model_sha)[1]
    with pytest.raises(g0.G0Error, match="ancestry contains symlink"):
        g0.bound.load_episode(
            link,
            episode_sha,
            model_sha,
            model_manifest,
            VIEW_BUILDER_SHA,
            SOURCE_CELL_SHA,
        )
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(g0.G0Error, match="output exists"):
        g0.bound.publish(existing, b"x", {})


def test_second_anchor_context_cannot_reach_fit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, model_sha, episode, _ = _fixture(tmp_path)
    episode.chmod(0o755)
    anchor_path = episode / "episode_anchor_context.csv"
    anchor_path.chmod(0o644)
    anchor_data = _csv(
        g0.ANCHOR_COLUMNS,
        [
            {
                "episode_id": "episode-1",
                "anchor_molecule_id": "anchor",
                "anchor_point": "2.75",
            },
            {
                "episode_id": "sibling-episode",
                "anchor_molecule_id": "query",
                "anchor_point": "9",
            },
        ],
    )
    anchor_path.write_bytes(anchor_data)
    manifest_path = episode / "manifest.json"
    manifest_path.chmod(0o644)
    manifest = json.loads(manifest_path.read_bytes())
    manifest["output_receipts"]["episode_anchor_context.csv"] = _receipt(
        "episode_anchor_context.csv", anchor_data, g0.ANCHOR_COLUMNS
    )
    manifest_data = _json(manifest)
    manifest_path.write_bytes(manifest_data)
    _readonly(episode)
    monkeypatch.setattr(g0.bound, "runtime", lambda: {})
    monkeypatch.setattr(
        g0,
        "_fit_predict",
        lambda *_: pytest.fail("fit crossed the one-anchor capability firewall"),
    )
    with pytest.raises(g0.G0Error, match="exactly one anchor"):
        g0.run_g0(
            model_public_root=model,
            model_public_manifest_sha256=model_sha,
            episode_target_root=episode,
            episode_target_manifest_sha256=_sha(manifest_data),
            expected_source_bundle_sha256=g0._source_bundle_sha(),
            expected_episode_view_builder_source_sha256=VIEW_BUILDER_SHA,
            expected_source_cell_target_manifest_sha256=SOURCE_CELL_SHA,
            output_root=tmp_path / "out",
        )


def test_feature_nan_and_binary_firewalls(tmp_path: Path) -> None:
    model, _, _, _ = _fixture(tmp_path)
    loaded = {name: (model / name).read_bytes() for name in g0.bound.MODEL_FILES[1:]}
    descriptor = np.load(
        io.BytesIO(loaded["maplight_rdkit_descriptors.npy"]), allow_pickle=False
    )
    descriptor[0, 0] = np.nan
    loaded["maplight_rdkit_descriptors.npy"] = _npy(descriptor)
    with pytest.raises(g0.G0Error, match="descriptor NaN mask differs"):
        g0._feature_arrays(loaded, 102)
    descriptor[0, 0] = 0.0
    loaded["maplight_rdkit_descriptors.npy"] = _npy(descriptor)
    morgan = np.zeros((102, 4096), dtype=np.uint8)
    morgan[0, 0] = 2
    loaded["morgan_binary.npy"] = _npy(morgan)
    with pytest.raises(g0.G0Error, match="Morgan is not binary"):
        g0._feature_arrays(loaded, 102)


def test_manifest_digest_is_checked_before_episode_target_parse(
    tmp_path: Path,
) -> None:
    model, model_sha, episode, episode_sha = _fixture(tmp_path)
    model_manifest = g0.bound.load_model(model, model_sha)[1]
    with pytest.raises(g0.G0Error, match="episode manifest receipt differs"):
        g0.bound.load_episode(
            episode,
            "f" * 64,
            model_sha,
            model_manifest,
            VIEW_BUILDER_SHA,
            SOURCE_CELL_SHA,
        )
    assert episode_sha != "f" * 64


def test_parameter_source_hashes_are_exact() -> None:
    g0.bound.validate_parameter_source()
    assert (
        _sha(_json(g0.bound.ACCEPTED_PARAMETER_RECORD))
        == g0.bound.PARAMETER_RECORD_SHA256
    )
    assert _sha(_json(g0.bound.ACCEPTED_PARAMETERS)) == g0.bound.PARAMETER_SHA256


def test_episode_policy_is_stage_exact_and_rejects_mixed() -> None:
    selected = [{"episode_policy_id": "selected_anchor"}]
    stress = [{"episode_policy_id": "deterministic_random_anchor_stress"}]
    g0._validate_episode_policy("outer", selected)
    g0._validate_episode_policy("outer", stress)
    g0._validate_episode_policy("inner", selected)
    for stage, rows in (
        ("inner", stress),
        ("outer", [{"episode_policy_id": "unknown"}]),
        ("outer", [*selected, *stress]),
    ):
        with pytest.raises(g0.G0Error, match="episode policy differs"):
            g0._validate_episode_policy(stage, rows)


def test_source_bundle_poison_fails_before_capability_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(g0.bound, "runtime", lambda: {})
    monkeypatch.setattr(
        g0.bound,
        "load_model",
        lambda *_: pytest.fail("model capability opened before source causality"),
    )
    with pytest.raises(g0.G0Error, match="G0 source bundle receipt differs"):
        g0.run_g0(
            model_public_root=tmp_path / "model",
            model_public_manifest_sha256="1" * 64,
            episode_target_root=tmp_path / "episode",
            episode_target_manifest_sha256="2" * 64,
            expected_source_bundle_sha256="0" * 64,
            expected_episode_view_builder_source_sha256=VIEW_BUILDER_SHA,
            expected_source_cell_target_manifest_sha256=SOURCE_CELL_SHA,
            output_root=tmp_path / "out",
        )


@pytest.mark.parametrize(
    ("view_sha", "cell_sha"),
    [("0" * 64, SOURCE_CELL_SHA), (VIEW_BUILDER_SHA, "0" * 64)],
)
def test_parent_causality_poison_fails_before_target_payload_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    view_sha: str,
    cell_sha: str,
) -> None:
    model, model_sha, episode, episode_sha = _fixture(tmp_path)
    model_manifest = g0.bound.load_model(model, model_sha)[1]
    opened: list[str] = []
    original = g0.bound._read_at

    def observed_read(root_fd: int, name: str, label: str, **kwargs: Any) -> bytes:
        opened.append(name)
        return cast(bytes, original(root_fd, name, label, **kwargs))

    monkeypatch.setattr(g0.bound, "_read_at", observed_read)
    with pytest.raises(g0.G0Error, match="episode root|root pairing"):
        g0.bound.load_episode(
            episode,
            episode_sha,
            model_sha,
            model_manifest,
            view_sha,
            cell_sha,
        )
    assert opened == ["manifest.json"]


def test_publication_reopens_readonly_stage_and_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: list[tuple[str, int, tuple[int, ...]]] = []
    fsynced: list[str] = []
    original = g0.bound._verify_published_tree
    original_fsync = g0.bound.os.fsync

    def verify(root: Path, payloads: Mapping[str, bytes], label: str) -> None:
        observed.append(
            (
                label,
                stat.S_IMODE(root.stat().st_mode),
                tuple(
                    sorted(stat.S_IMODE(path.stat().st_mode) for path in root.iterdir())
                ),
            )
        )
        original(root, payloads, label)

    monkeypatch.setattr(g0.bound, "_verify_published_tree", verify)

    def fsync(descriptor: int) -> None:
        fsynced.append(os.readlink(f"/proc/self/fd/{descriptor}"))
        original_fsync(descriptor)

    monkeypatch.setattr(g0.bound.os, "fsync", fsync)
    output = g0.bound.publish(tmp_path / "published", b"fragment\n", {"a": 1})
    assert observed == [
        ("staged", 0o555, (0o444, 0o444)),
        ("published", 0o555, (0o444, 0o444)),
    ]
    assert output.is_dir() and not any(tmp_path.glob(".r5c-g0-*"))
    assert fsynced[-1] == str(tmp_path)


def test_compiler_projection_model_manifest_is_g0_compatible(tmp_path: Path) -> None:
    from cypshift.openadmet_oracle_projection import (  # type: ignore[import-untyped]
        project_openadmet_oracle_inputs,
    )
    from cypshift.openadmet_oracle_source import (  # type: ignore[import-untyped]
        SOURCE_FILES,
        compile_openadmet_oracle_source,
    )

    source_test_path = ROOT / "tests/test_openadmet_oracle_source.py"
    source_spec = importlib.util.spec_from_file_location(
        "g0_source_fixture", source_test_path
    )
    assert source_spec is not None and source_spec.loader is not None
    source_fixture = importlib.util.module_from_spec(source_spec)
    source_spec.loader.exec_module(source_fixture)
    paths, receipts = source_fixture._fixture(tmp_path / "parents")
    source = compile_openadmet_oracle_source(
        paths, tmp_path / "source", expected_receipts=receipts
    )
    expected = {
        name: str(source.output_receipts[name]["sha256"]) for name in SOURCE_FILES
    }
    expected["manifest.json"] = source.manifest_sha256
    projection = project_openadmet_oracle_inputs(
        source.output_directory,
        tmp_path / "projection",
        expected_receipts=expected,
    )
    manifest_data = (projection.model_public_root / "manifest.json").read_bytes()
    _, manifest = g0.bound.load_model(projection.model_public_root, _sha(manifest_data))
    binding = manifest["source_bundle_binding"]
    assert binding["input_receipts"] == binding["source_receipts"]
    assert all(
        set(record) == {"sha256", "bytes"}
        for record in binding["input_receipts"].values()
    )

"""Receipt and publication tests for the locked G0 episode-view adapter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from test_openadmet_oracle_g0 import g0
from test_openadmet_oracle_projection import (
    FEATURE_SPECS,
    _fixture,
    _rewrite_csv,
    _rewrite_npy,
)

from cypshift.openadmet_oracle_g0_view import (
    build_g0_episode_view,
    view_builder_source_sha256,
)
from cypshift.openadmet_oracle_projection import project_openadmet_oracle_inputs


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _material(
    tmp_path: Path, *, unavailable_anchor: bool = False
) -> tuple[Path, str, Path, str, str]:
    source, receipts = _fixture(tmp_path / "source-fixture")
    rng = np.random.default_rng(20260820)
    for name, (width, dtype) in FEATURE_SPECS.items():
        if name == "maplight_morgan_count.npy":
            values = rng.integers(0, 4, (6, width), dtype=np.int8)
        elif name == "maplight_avalon_count.npy":
            values = rng.integers(0, 2, (6, width), dtype=np.int8)
        elif name == "morgan_binary.npy":
            values = rng.integers(0, 2, (6, width), dtype=np.uint8)
        else:
            values = rng.normal(size=(6, width)).astype(np.dtype(dtype))
        _rewrite_npy(source, receipts, name, values)
    if unavailable_anchor:

        def hide_anchor(rows: list[dict[str, str]]) -> None:
            for row in rows:
                if row["episode_id"] == hashlib.sha256(b"selected-a").hexdigest():
                    row["anchor_point_available"] = "false"
                    row["anchor_point"] = ""

        _rewrite_csv(source, receipts, "episode_anchor_contexts.csv", hide_anchor)
    projection = project_openadmet_oracle_inputs(
        source, tmp_path / "projection", expected_receipts=receipts
    )
    model = projection.model_public_root
    target = projection.cell_target_root / "outer/repeat-0/outer-1"
    model_sha = _sha((model / "manifest.json").read_bytes())
    target_sha = _sha((target / "manifest.json").read_bytes())
    episode_id = hashlib.sha256(b"selected-a").hexdigest()
    return model, model_sha, target, target_sha, episode_id


def _build(tmp_path: Path, output_name: str) -> tuple[Path, str, Path, str, str]:
    model, model_sha, target, target_sha, episode_id = _material(tmp_path)
    output = tmp_path / output_name
    result = build_g0_episode_view(
        model_public_root=model,
        model_public_manifest_sha256=model_sha,
        cell_target_root=target,
        cell_target_manifest_sha256=target_sha,
        scope=("outer", 0, 1, None),
        episode_id=episode_id,
        output_root=output,
    )
    assert result.output_root == output
    assert result.manifest_sha256 == _sha((output / "manifest.json").read_bytes())
    return model, model_sha, target, target_sha, episode_id


def test_episode_view_is_exact_and_byte_deterministic(tmp_path: Path) -> None:
    first_inputs = _build(tmp_path / "first", "view")
    _build(tmp_path / "second", "view")
    first = tmp_path / "first" / "view"
    second = tmp_path / "second" / "view"
    assert {path.name for path in first.iterdir()} == {
        "manifest.json",
        "training_points.csv",
        "episode_anchor_context.csv",
    }
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {
        path.name: path.read_bytes() for path in second.iterdir()
    }
    model, model_sha, target, target_sha, episode_id = first_inputs
    _, model_manifest = g0.bound.load_model(model, model_sha)
    loaded, manifest = g0.bound.load_episode(
        first,
        _sha((first / "manifest.json").read_bytes()),
        model_sha,
        model_manifest,
        view_builder_source_sha256(),
        target_sha,
    )
    assert manifest["episode"]["episode_id"] == episode_id
    assert manifest["operation_accounting"]["anchor_labels_exposed_to_models"] == 1
    assert loaded["episode_anchor_context.csv"].count(b"\n") == 2
    assert not any(path.stat().st_mode & 0o222 for path in first.iterdir())
    assert target.is_dir()


def test_episode_view_rejects_unknown_episode_and_overwrite(tmp_path: Path) -> None:
    model, model_sha, target, target_sha, _ = _material(tmp_path)
    with pytest.raises(ValueError, match="absent"):
        build_g0_episode_view(
            model_public_root=model,
            model_public_manifest_sha256=model_sha,
            cell_target_root=target,
            cell_target_manifest_sha256=target_sha,
            scope=("outer", 0, 1, None),
            episode_id="f" * 64,
            output_root=tmp_path / "view",
        )
    output = tmp_path / "view"
    _build(tmp_path / "valid", "view")
    output.mkdir()
    with pytest.raises(ValueError, match="overwrite"):
        build_g0_episode_view(
            model_public_root=model,
            model_public_manifest_sha256=model_sha,
            cell_target_root=target,
            cell_target_manifest_sha256=target_sha,
            scope=("outer", 0, 1, None),
            episode_id=hashlib.sha256(b"selected-a").hexdigest(),
            output_root=output,
        )


def test_episode_view_can_expose_no_anchor_label(tmp_path: Path) -> None:
    model, model_sha, target, target_sha, episode_id = _material(
        tmp_path, unavailable_anchor=True
    )
    output = tmp_path / "view"
    result = build_g0_episode_view(
        model_public_root=model,
        model_public_manifest_sha256=model_sha,
        cell_target_root=target,
        cell_target_manifest_sha256=target_sha,
        scope=("outer", 0, 1, None),
        episode_id=episode_id,
        output_root=output,
    )
    manifest = json.loads((result.output_root / "manifest.json").read_bytes())
    assert manifest["operation_accounting"]["anchor_labels_exposed_to_models"] == 0
    assert manifest["operation_accounting"]["direct_target_values_parsed"] == 1
    assert ",false,\n" in (output / "episode_anchor_context.csv").read_text()

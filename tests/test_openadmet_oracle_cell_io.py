from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from test_openadmet_oracle_projection import _fixture

from cypshift import openadmet_oracle_cell_io as cell_io
from cypshift import openadmet_oracle_validation as accepted
from cypshift.openadmet_oracle_cell_io import (
    OpenADMETOracleCellIOError,
    Scope,
    load_oracle_cell_capability,
)
from cypshift.openadmet_oracle_projection import project_openadmet_oracle_inputs
from cypshift.openadmet_transformation_io import (
    canonical_csv_bytes,
    canonical_json_bytes,
)


def _roots(tmp_path: Path) -> tuple[Path, Path, Path]:
    source, receipts = _fixture(tmp_path / "fixture")
    result = project_openadmet_oracle_inputs(
        source, tmp_path / "projection", expected_receipts=receipts
    )
    return result.model_public_root, result.cell_target_root, result.c3_target_root


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scope(root: Path) -> Scope:
    manifest = json.loads((root / "manifest.json").read_bytes())
    value = manifest["current_cell_scope"]
    inner = None if value["inner_fold"] == "" else int(value["inner_fold"])
    return cast(Scope, (value["stage"], value["repeat"], value["outer_fold"], inner))


def _load(model: Path, target: Path, *, c3: bool = False) -> Any:
    return load_oracle_cell_capability(
        model,
        target,
        expected_model_manifest_sha256=_sha(model / "manifest.json"),
        expected_target_manifest_sha256=_sha(target / "manifest.json"),
        system_id="C3" if c3 else "C2",
        target_kind="c3-target" if c3 else "cell-target",
        expected_scope=_scope(target),
    )


def _mutable_root(source: Path, destination: Path) -> Path:
    shutil.copytree(source, destination)
    destination.chmod(0o755)
    for path in destination.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    return destination


def _target_copy(source: Path, parent: Path) -> Path:
    scope = _scope(source)
    stage, repeat, outer, inner = scope
    destination = parent / source.parts[-(4 if stage == "outer" else 5)] / stage
    destination = destination / f"repeat-{repeat}" / f"outer-{outer}"
    if inner is not None:
        destination /= f"inner-{inner}"
    return _mutable_root(source, destination)


def _rewrite_manifest(root: Path, change: Callable[[dict[str, Any]], None]) -> None:
    path = root / "manifest.json"
    manifest = json.loads(path.read_bytes())
    change(manifest)
    path.write_bytes(canonical_json_bytes(manifest))


def _rewrite_csv(
    root: Path,
    name: str,
    rows: list[dict[str, str]],
    *,
    update_accounting: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    columns = accepted.output_columns(name)
    payload = canonical_csv_bytes(columns, rows)
    (root / name).write_bytes(payload)

    def update(manifest: dict[str, Any]) -> None:
        manifest["output_receipts"][name] = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "rows": len(rows),
            "columns": list(columns),
        }
        if update_accounting is not None:
            update_accounting(manifest)

    _rewrite_manifest(root, update)


def _rows(root: Path, name: str) -> list[dict[str, str]]:
    return accepted.csv_rows(
        (root / name).read_bytes(), accepted.output_columns(name), name
    )


def test_all_75_measured_and_75_c3_roots_replay(tmp_path: Path) -> None:
    model, measured_root, c3_root = _roots(tmp_path)
    measured = sorted(path.parent for path in measured_root.rglob("manifest.json"))
    pure = sorted(path.parent for path in c3_root.rglob("manifest.json"))
    assert len(measured) == len(pure) == 75
    for target in measured:
        capability = _load(model, target)
        assert capability.target.kind == "cell-target"
    for target in pure:
        capability = _load(model, target, c3=True)
        assert capability.target.kind == "c3-target"
        assert not hasattr(capability.target, "training_points")
        assert not hasattr(capability.target, "episode_anchor_contexts")


def test_out_of_band_receipts_precede_manifest_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, measured, _ = _roots(tmp_path)
    target = measured / "outer/repeat-0/outer-1"

    def parsed_too_early(*_args: object, **_kwargs: object) -> Any:
        raise AssertionError("manifest parsed before receipt")

    monkeypatch.setattr(cell_io, "strict_json_object", parsed_too_early)
    with pytest.raises(OpenADMETOracleCellIOError, match="out-of-band"):
        load_oracle_cell_capability(
            model,
            target,
            expected_model_manifest_sha256="0" * 64,
            expected_target_manifest_sha256=_sha(target / "manifest.json"),
            system_id="C2",
            target_kind="cell-target",
            expected_scope=("outer", 0, 1, None),
        )


@pytest.mark.parametrize(
    ("system", "kind", "scope", "match"),
    [
        ("C3", "cell-target", ("outer", 0, 1, None), "system/target"),
        ("C2", "c3-target", ("outer", 0, 1, None), "system/target"),
        ("UNKNOWN", "cell-target", ("outer", 0, 1, None), "not an R5"),
        ("C2", "cell-target", ("inner", 0, 1, None), "scope"),
    ],
)
def test_system_kind_and_scope_are_bound_before_exposure(
    tmp_path: Path, system: str, kind: str, scope: Scope, match: str
) -> None:
    model, measured, c3 = _roots(tmp_path)
    target = (measured if kind == "cell-target" else c3) / "outer/repeat-0/outer-1"
    with pytest.raises(OpenADMETOracleCellIOError, match=match):
        load_oracle_cell_capability(
            model,
            target,
            expected_model_manifest_sha256=_sha(model / "manifest.json"),
            expected_target_manifest_sha256=_sha(target / "manifest.json"),
            system_id=system,
            target_kind=cast(Any, kind),
            expected_scope=scope,
        )


def test_wrong_pairing_and_accounting_fail_closed(tmp_path: Path) -> None:
    model, measured, _ = _roots(tmp_path)
    source = measured / "outer/repeat-0/outer-1"
    target = _target_copy(source, tmp_path / "bad-pair")
    _rewrite_manifest(
        target,
        lambda manifest: manifest["source_bundle_binding"][
            "manifest_receipt"
        ].__setitem__("sha256", hashlib.sha256(b"other source").hexdigest()),
    )
    with pytest.raises(OpenADMETOracleCellIOError, match="source_bundle_binding"):
        _load(model, target)

    target = _target_copy(source, tmp_path / "bad-accounting")
    _rewrite_manifest(
        target,
        lambda manifest: manifest["operation_accounting"].__setitem__(
            "direct_target_values_parsed", 99
        ),
    )
    with pytest.raises(OpenADMETOracleCellIOError, match="operation accounting"):
        _load(model, target)


@pytest.mark.parametrize("witness", ["sha", "bytes", "columns", "header", "scope"])
def test_manifest_and_csv_mutations_fail_closed(tmp_path: Path, witness: str) -> None:
    model, measured, _ = _roots(tmp_path)
    source = measured / "outer/repeat-0/outer-1"
    target = _target_copy(source, tmp_path / witness)
    if witness == "header":
        path = target / "training_points.csv"
        payload = path.read_bytes().replace(b"molecule_id,", b"molecule_idx,", 1)
        path.write_bytes(payload)

        def change(manifest: dict[str, Any]) -> None:
            manifest["output_receipts"]["training_points.csv"].update(
                {"sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
            )

    elif witness == "scope":

        def change(manifest: dict[str, Any]) -> None:
            manifest["current_cell_scope"]["outer_fold"] = 2

    else:

        def change(manifest: dict[str, Any]) -> None:
            receipt = manifest["output_receipts"]["training_points.csv"]
            if witness == "sha":
                receipt["sha256"] = "0" * 64
            elif witness == "bytes":
                receipt["bytes"] += 1
            else:
                receipt["columns"][0] = "molecule_idx"

    _rewrite_manifest(target, change)
    with pytest.raises(OpenADMETOracleCellIOError):
        load_oracle_cell_capability(
            model,
            target,
            expected_model_manifest_sha256=_sha(model / "manifest.json"),
            expected_target_manifest_sha256=_sha(target / "manifest.json"),
            system_id="C2",
            target_kind="cell-target",
            expected_scope=("outer", 0, 1, None),
        )


@pytest.mark.parametrize("witness", ["extra", "missing"])
def test_exact_file_set_fails_closed(tmp_path: Path, witness: str) -> None:
    model, measured, _ = _roots(tmp_path)
    target = _target_copy(measured / "outer/repeat-0/outer-1", tmp_path / witness)
    if witness == "extra":
        (target / "extra.csv").write_bytes(b"forbidden\n")
    else:
        (target / "training_pairs.csv").unlink()
    with pytest.raises(OpenADMETOracleCellIOError, match="file set"):
        _load(model, target)


def test_npy_alignment_is_bound_to_authenticated_source(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    model, measured, _ = _roots(tmp_path)
    mutable_model = _mutable_root(model, tmp_path / "model-public")
    name = "maplight_rdkit_descriptors.npy"
    array = np.load(mutable_model / name, allow_pickle=False)
    array[0, 0] += 1.0
    stream = io.BytesIO()
    np.save(stream, array, allow_pickle=False)
    payload = stream.getvalue()
    assert hashlib.sha256(payload).hexdigest() != _sha(mutable_model / name)
    (mutable_model / name).write_bytes(payload)

    def change(manifest: dict[str, Any]) -> None:
        manifest["output_receipts"][name].update(
            {"sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
        )

    _rewrite_manifest(mutable_model, change)
    with pytest.raises(OpenADMETOracleCellIOError, match="feature/source binding"):
        _load(mutable_model, measured / "outer/repeat-0/outer-1")


def test_c3_forbidden_measured_material_scan(tmp_path: Path) -> None:
    model, _, c3 = _roots(tmp_path)
    target = _target_copy(c3 / "outer/repeat-0/outer-1", tmp_path / "c3")
    rows = _rows(target, "training_pairs.csv")
    rows[0]["pair_id"] = "anchor_point"
    _rewrite_csv(target, "training_pairs.csv", rows)
    with pytest.raises(OpenADMETOracleCellIOError, match="measured-point"):
        _load(model, target, c3=True)


@pytest.mark.parametrize("witness", ["assigned_outer", "stress", "inner_fold"])
def test_inner_context_scope_witnesses_fail_closed(
    tmp_path: Path, witness: str
) -> None:
    model, measured, _ = _roots(tmp_path)
    if witness == "inner_fold":
        source = measured / "inner/repeat-0/outer-0/inner-1"
        target = _target_copy(source, tmp_path / witness)
        donor = measured / "inner/repeat-0/outer-0/inner-0"
        rows = _rows(donor, "episode_anchor_contexts.csv")

        def accounting(manifest: dict[str, Any]) -> None:
            manifest["operation_accounting"]["anchor_labels_exposed_to_models"] = 1

    else:
        source = measured / "inner/repeat-0/outer-0/inner-0"
        target = _target_copy(source, tmp_path / witness)
        donor = (
            measured / "inner/repeat-0/outer-1/inner-2"
            if witness == "assigned_outer"
            else measured / "outer/repeat-0/outer-1"
        )
        donor_rows = _rows(donor, "episode_anchor_contexts.csv")
        rows = [
            row
            for row in donor_rows
            if witness != "stress"
            or any(
                query["episode_id"] == row["episode_id"]
                and query["episode_policy_id"] == "deterministic_random_anchor_stress"
                for query in _rows(model, "public_episode_queries.csv")
            )
        ][:1]
        accounting = None
    _rewrite_csv(
        target,
        "episode_anchor_contexts.csv",
        rows,
        update_accounting=accounting,
    )
    with pytest.raises(OpenADMETOracleCellIOError, match="context|anchor"):
        _load(model, target)


@pytest.mark.parametrize("witness", ["one_direction", "antisymmetry", "weight", "link"])
def test_training_pair_contract_witnesses_fail_closed(
    tmp_path: Path, witness: str
) -> None:
    model, measured, _ = _roots(tmp_path)
    source = measured / "outer/repeat-0/outer-1"
    target = _target_copy(source, tmp_path / witness)
    rows = _rows(target, "training_pairs.csv")
    if witness == "one_direction":
        rows.pop()
    elif witness == "antisymmetry":
        rows[1]["delta"] = "-2"
    elif witness == "weight":
        rows[0]["sample_weight"] = "1/3"
    else:
        rows[0]["pair_id"] = "0" * 64

    def accounting(manifest: dict[str, Any]) -> None:
        points = manifest["output_receipts"]["training_points.csv"]["rows"]
        manifest["operation_accounting"]["direct_target_values_parsed"] = points + len(
            rows
        )

    _rewrite_csv(target, "training_pairs.csv", rows, update_accounting=accounting)
    with pytest.raises(OpenADMETOracleCellIOError, match="pair|direction"):
        _load(model, target)


def test_episode_grammar_and_oof_identity_fail_closed(tmp_path: Path) -> None:
    model, measured, _ = _roots(tmp_path)
    mutable_model = _mutable_root(model, tmp_path / "model-public")
    geometry = _rows(mutable_model, "episode_transformations.csv")
    geometry[0]["exact_transformation_id"] = "0" * 64
    _rewrite_csv(mutable_model, "episode_transformations.csv", geometry)
    payload = (mutable_model / "episode_transformations.csv").read_bytes()

    def bind_source(manifest: dict[str, Any]) -> None:
        manifest["source_receipts"]["episode_transformations.csv"].update(
            {"sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
        )

    _rewrite_manifest(mutable_model, bind_source)
    target = measured / "outer/repeat-0/outer-1"
    with pytest.raises(OpenADMETOracleCellIOError, match="grammar"):
        _load(mutable_model, target)

    target = _target_copy(target, tmp_path / "oof")
    contexts = _rows(target, "episode_anchor_contexts.csv")
    contexts[0]["anchor_global_oof_receipt_sha256"] = "0" * 64
    _rewrite_csv(target, "episode_anchor_contexts.csv", contexts)
    with pytest.raises(OpenADMETOracleCellIOError, match="OOF source identity"):
        _load(model, target)


def test_symlink_ancestry_leaf_and_toctou_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, measured, _ = _roots(tmp_path)
    target = measured / "outer/repeat-0/outer-1"
    alias_parent = tmp_path / "alias"
    alias_parent.symlink_to(model.parent, target_is_directory=True)
    alias = alias_parent / "model-public"
    with pytest.raises(OpenADMETOracleCellIOError, match="ancestry"):
        load_oracle_cell_capability(
            alias,
            target,
            expected_model_manifest_sha256=_sha(model / "manifest.json"),
            expected_target_manifest_sha256=_sha(target / "manifest.json"),
            system_id="C2",
            target_kind="cell-target",
            expected_scope=("outer", 0, 1, None),
        )

    linked_model = _mutable_root(model, tmp_path / "linked" / "model-public")
    real = tmp_path / "folds-real.csv"
    real.write_bytes((linked_model / "folds.csv").read_bytes())
    (linked_model / "folds.csv").unlink()
    (linked_model / "folds.csv").symlink_to(real)
    with pytest.raises(OpenADMETOracleCellIOError, match="open regular"):
        _load(linked_model, target)

    mutable_target = _target_copy(target, tmp_path / "toctou")
    watched = mutable_target / "training_pairs.csv"
    original = cell_io._read_fd_bytes  # noqa: SLF001
    changed = False

    def mutate_during_read(fd: int) -> bytes:
        nonlocal changed
        data = original(fd)
        if not changed and os.readlink(f"/proc/self/fd/{fd}") == str(watched):
            with watched.open("ab") as handle:
                handle.write(b"x")
            changed = True
        return data

    monkeypatch.setattr(cell_io, "_read_fd_bytes", mutate_during_read)
    with pytest.raises(OpenADMETOracleCellIOError, match="changed while read"):
        _load(model, mutable_target)


def test_each_leaf_is_loaded_once_and_replay_is_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, measured, _ = _roots(tmp_path)
    target = measured / "outer/repeat-0/outer-1"
    original = cell_io._read_regular  # noqa: SLF001
    calls: list[str] = []

    def counted(root_fd: int, name: str) -> bytes:
        calls.append(name)
        return original(root_fd, name)

    monkeypatch.setattr(cell_io, "_read_regular", counted)
    first = _load(model, target)
    expected = len(cell_io.MODEL_FILES) + len(cell_io.CELL_FILES_NO_MANIFEST) + 2
    assert len(calls) == expected
    assert calls.count("manifest.json") == 2
    monkeypatch.setattr(cell_io, "_read_regular", original)
    second = _load(model, target)
    assert first.system_id == second.system_id
    assert first.model_public.manifest_sha256 == second.model_public.manifest_sha256
    assert first.target == second.target
    assert first.model_public.molecules == second.model_public.molecules
    for name, array in first.model_public.features.items():
        other = second.model_public.features[name]
        assert array.shape == other.shape
        assert array.dtype == other.dtype
        assert array.tobytes() == other.tobytes()
        with pytest.raises(ValueError):
            array.setflags(write=True)

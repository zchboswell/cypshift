from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import os
import platform
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from test_openadmet_oracle_g0 import (
    _argv as locked_g0_argv,
)
from test_openadmet_oracle_g0 import (
    _fixture as locked_g0_fixture,
)
from test_openadmet_oracle_projection import _fixture

import cypshift.openadmet_oracle_pair_cell_io as pair_io
from cypshift.openadmet_oracle_cell_io import (
    OracleCellCapability,
    OracleCellTargetCapability,
    load_oracle_cell_capability,
)
from cypshift.openadmet_oracle_pair_cell import (
    candidate_id,
    cell_id,
    run_pair_cell,
)
from cypshift.openadmet_oracle_projection import project_openadmet_oracle_inputs
from cypshift.openadmet_transformation_io import (
    canonical_csv_bytes,
    canonical_json_bytes,
)

pytestmark = pytest.mark.skipif(
    sys.version_info[:3] != (3, 12, 3)
    or platform.system() != "Linux"
    or platform.machine() != "x86_64",
    reason="requires the exact R5C root runtime",
)

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "research/maplight-fixed/run_r5_oracle_pair_cell.py"
spec = importlib.util.spec_from_file_location("r5_pair_runner", SCRIPT)
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)
G0_SCRIPT = ROOT / "research/maplight-fixed/run_r5_oracle_g0.py"
LOCKED_G0_PYTHON = ROOT / "research/maplight-fixed/.venv/bin/python"
g0_spec = importlib.util.spec_from_file_location("r5_g0_pair_fixture", G0_SCRIPT)
assert g0_spec is not None and g0_spec.loader is not None
g0 = importlib.util.module_from_spec(g0_spec)
sys.modules[g0_spec.name] = g0
g0_spec.loader.exec_module(g0)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _token_root(
    tmp_path: Path,
    *,
    system_id: str,
    alpha: float | None,
    lambda_: float | None,
) -> tuple[Path, str]:
    root = tmp_path / f"token-{system_id}"
    root.mkdir()
    token = {
        "schema_version": "cypshift.openadmet_cyp_2026.r5c_score_free_selection_token.v1",
        "contract_sha256": pair_io.CONTRACT_SHA256,
        "system_id": system_id,
        "repeat": 0,
        "outer_fold": 1,
        "candidate_id": candidate_id(system_id, alpha, lambda_),
        "alpha": alpha,
        "lambda": lambda_,
        "candidate_receipt_sha256": "a" * 64,
        "scorer_receipt_sha256": "b" * 64,
    }
    data = (
        json.dumps(
            token,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    path = root / pair_io.TOKEN_FILE
    path.write_bytes(data)
    path.chmod(0o444)
    root.chmod(0o555)
    return root, hashlib.sha256(data).hexdigest()


def _capability(tmp_path: Path) -> tuple[OracleCellCapability, Path, Path, str, str]:
    source, receipts = _fixture(tmp_path / "fixture")
    projection = project_openadmet_oracle_inputs(
        source, tmp_path / "projection", expected_receipts=receipts
    )
    target_root = projection.cell_target_root / "outer/repeat-0/outer-1"
    scope_value = json.loads((target_root / "manifest.json").read_bytes())[
        "current_cell_scope"
    ]
    scope = (
        scope_value["stage"],
        int(scope_value["repeat"]),
        int(scope_value["outer_fold"]),
        None,
    )
    capability = load_oracle_cell_capability(
        projection.model_public_root,
        target_root,
        expected_model_manifest_sha256=_sha(
            projection.model_public_root / "manifest.json"
        ),
        expected_target_manifest_sha256=_sha(target_root / "manifest.json"),
        system_id="C0",
        target_kind="cell-target",
        expected_scope=cast(Any, scope),
    )
    assert isinstance(capability.target, OracleCellTargetCapability)
    return (
        capability,
        projection.model_public_root,
        target_root,
        _sha(projection.model_public_root / "manifest.json"),
        _sha(target_root / "manifest.json"),
    )


def _g0_roots(
    tmp_path: Path,
    capability: OracleCellCapability,
    model_sha: str,
    target_sha: str,
) -> tuple[list[Path], list[str]]:
    assert isinstance(capability.target, OracleCellTargetCapability)
    episode_ids = {
        row["episode_id"] for row in capability.target.episode_anchor_contexts
    }
    public = [
        row
        for row in capability.model_public.public_queries
        if row["episode_id"] in episode_ids
    ]
    groups: dict[str, list[dict[str, str]]] = {}
    for row in public:
        groups.setdefault(row["episode_id"], []).append(
            {
                "molecule_id": row["query_molecule_id"],
                "endpoint": "CYP3A4",
                "component_id": row["outer_group_id"],
                "repeat": row["repeat"],
                "outer_fold": row["outer_fold"],
                "inner_fold": "",
                "scope": "openadmet-oracle-outer-v1",
                "system_id": "TRACE-G0-MAPL-FIXED",
                "prediction": "0",
                "applicability_score": "0",
                "model_id": "1" * 64,
                "feature_spec_id": "maplight-fixed-stage-a-v1",
                "split_id": "2" * 64,
            }
        )
    roots: list[Path] = []
    receipts: list[str] = []
    source_sha, source_receipts = runner._file_bundle(runner.G0_SOURCE_FILES)
    model_manifest = json.loads(
        json.dumps(capability.model_public.manifest, default=dict)
    )
    contexts = {
        row["episode_id"]: row for row in capability.target.episode_anchor_contexts
    }
    for index, (episode_id, rows) in enumerate(sorted(groups.items())):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(
            stream, fieldnames=list(pair_io.LEGACY_G0_COLUMNS), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
        fragment = stream.getvalue().encode()
        root = tmp_path / f"g0-{index}"
        root.mkdir()
        (root / "prediction_fragment.csv").write_bytes(fragment)
        public_rows = sorted(
            (row for row in public if row["episode_id"] == episode_id),
            key=lambda row: int(row["query_rank"]),
        )
        candidate = candidate_id("G0", None, None)
        episode_cell = cell_id("outer", 0, 1, None, "G0", candidate, episode_id)
        context = contexts[episode_id]
        anchor_rows = int(context["anchor_point_available"] == "true")
        training_rows = len(capability.target.training_points)
        operation = dict.fromkeys(pair_io.ACCOUNTING_FIELDS, 0)
        operation["direct_target_values_parsed"] = training_rows + anchor_rows
        operation["anchor_labels_exposed_to_models"] = anchor_rows
        operation["maplight_model_fits"] = 1
        episode = {
            "episode_id": episode_id,
            "anchor_molecule_id": public_rows[0]["anchor_molecule_id"],
            "query_rows": len(public_rows),
            "query_rows_sha256": runner._public_receipt(public_rows),
        }
        manifest = {
            "schema_version": "cypshift.openadmet_cyp_2026.r5c_g0_prediction_fragment.v1",
            "status": "R5_ORACLE_G0_EPISODE_COMPLETE",
            "contract_sha256": pair_io.CONTRACT_SHA256,
            "parent_contract_sha256": runner.G0_PARENT_CONTRACT_SHA256,
            "runner_source_sha256": source_receipts[
                "research/maplight-fixed/run_r5_oracle_g0.py"
            ],
            "g0_source_bundle_sha256": source_sha,
            "g0_source_file_receipts": source_receipts,
            "model_public_manifest_sha256": model_sha,
            "episode_target_manifest_sha256": hashlib.sha256(
                f"episode-target-{episode_id}".encode()
            ).hexdigest(),
            "trusted_episode_parent_receipts": {
                "episode_view_builder_source_sha256": "4" * 64,
                "source_cell_target_manifest_sha256": target_sha,
            },
            "source_bundle_binding": model_manifest["source_bundle_binding"],
            "scope": {
                "stage": "outer",
                "repeat": 0,
                "current_outer_validation_fold": 1,
                "inner_fold": "",
                "episode_outer_fold": int(public_rows[0]["outer_fold"]),
            },
            "episode": episode,
            "system_id": "G0",
            "source_system_id": "TRACE-G0-MAPL-FIXED",
            "candidate_id": candidate,
            "cell_id": episode_cell,
            "public_query_receipt_sha256": episode["query_rows_sha256"],
            "runtime": {
                "platform": "Linux x86_64 CPU",
                "python_version": "3.10.13",
                "numpy_version": "1.25.2",
                "catboost_version": "1.2.1",
                "uv_lock_sha256": "99e72821b69d9bb943a6e32adc7e0dec0e46c6d32df090241d4fb9296a4195d8",
                "cpu_only": True,
                "max_threads": 16,
            },
            "r3c_parameter_source": g0.bound.R3C_PARAMETER_SOURCE,
            "resolved_catboost_parameters": g0.bound.ACCEPTED_PARAMETERS,
            "counts": {
                "current_training_points": training_rows,
                "anchor_rows": anchor_rows,
                "fit_rows": training_rows + anchor_rows,
                "query_rows": len(rows),
            },
            "operation_accounting": operation,
            "prediction_fragment": {
                "sha256": hashlib.sha256(fragment).hexdigest(),
                "bytes": len(fragment),
                "rows": len(rows),
                "columns": list(pair_io.LEGACY_G0_COLUMNS),
            },
            "authority": g0.bound.DENIED_AUTHORITY,
        }
        manifest_bytes = g0.bound.json_bytes(manifest)
        (root / "manifest.json").write_bytes(manifest_bytes)
        for path in root.iterdir():
            path.chmod(0o444)
        root.chmod(0o555)
        roots.append(root)
        receipts.append(hashlib.sha256(manifest_bytes).hexdigest())
    return roots, receipts


def _c0_publication_material(tmp_path: Path) -> dict[str, Any]:
    capability, model_root, target_root, model_sha, target_sha = _capability(tmp_path)
    roots, receipts = _g0_roots(tmp_path, capability, model_sha, target_sha)
    assert isinstance(capability.target, OracleCellTargetCapability)
    episodes = {row["episode_id"] for row in capability.target.episode_anchor_contexts}
    public = [
        row
        for row in capability.model_public.public_queries
        if row["episode_id"] in episodes
    ]
    predictions, fragments = pair_io.load_g0_fragments(
        roots,
        expected_manifest_sha256=receipts,
        scope=("outer", 0, 1, None),
        public_queries=public,
    )
    result = run_pair_cell(
        capability,
        system_id="C0",
        alpha=None,
        lambda_=None,
        g0_predictions=predictions,
    )
    return {
        "capability": capability,
        "model_root": model_root,
        "target_root": target_root,
        "model_sha": model_sha,
        "target_sha": target_sha,
        "g0_roots": roots,
        "g0_receipts": receipts,
        "g0_fragments": fragments,
        "result": result,
    }


def _legacy_g0_predictions(
    capability: OracleCellCapability,
    fragments: tuple[pair_io.G0FragmentRoot, ...],
) -> dict[tuple[str, str, int], float]:
    predictions: dict[tuple[str, str, int], float] = {}
    for fragment in fragments:
        episode = cast(dict[str, Any], fragment.manifest["episode"])["episode_id"]
        by_molecule = {row["molecule_id"]: row for row in fragment.rows}
        for public in capability.model_public.public_queries:
            if public["episode_id"] == episode:
                predictions[
                    (
                        episode,
                        public["query_molecule_id"],
                        int(public["query_rank"]),
                    )
                ] = float(by_molecule[public["query_molecule_id"]]["prediction"])
    return predictions


def test_runner_publishes_source_runtime_and_g0_bindings(tmp_path: Path) -> None:
    capability, model_root, target_root, model_sha, target_sha = _capability(tmp_path)
    roots, receipts = _g0_roots(tmp_path, capability, model_sha, target_sha)
    output = runner.run(
        model_public_root=model_root,
        target_root=target_root,
        model_manifest_sha256=model_sha,
        target_manifest_sha256=target_sha,
        target_kind="cell-target",
        system_id="C0",
        alpha=None,
        lambda_=None,
        g0_root=roots,
        g0_manifest_sha256=receipts,
        output_root=tmp_path / "pair-output",
        expected_source_bundle_sha256=runner._source_bundle_sha(),
        stage="outer",
        repeat=0,
        outer_fold=1,
        inner_fold=None,
    )
    manifest = json.loads((output / "manifest.json").read_bytes())
    assert manifest["runner_source_sha256"] == runner._source_bundle_sha()
    assert manifest["runtime"]["python_version"]
    assert manifest["runtime"]["platform"].endswith("CPU")
    bindings = manifest["g0_bindings"]
    assert len(bindings) == len(roots)
    assert {record["g0_manifest_sha256"] for record in bindings} == set(receipts)
    assert all(len(record["binding_sha256"]) == 64 for record in bindings)


@pytest.mark.parametrize("forgery", ["unrelated", "zero-direct"])
def test_authenticated_publisher_rejects_forged_system_accounting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forgery: str
) -> None:
    capability, model_root, target_root, model_sha, target_sha = _capability(tmp_path)
    roots, receipts = _g0_roots(tmp_path, capability, model_sha, target_sha)
    original = runner.run_pair_cell

    def forged(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        accounting = dict(result.accounting)
        if forgery == "unrelated":
            accounting["query_truth_values_opened_by_scorers"] = 1
        else:
            accounting["direct_target_values_parsed"] = 0
        return replace(result, accounting=accounting)

    monkeypatch.setattr(runner, "run_pair_cell", forged)
    with pytest.raises(pair_io.OraclePairCellIOError, match="accounting"):
        runner.run(
            model_public_root=model_root,
            target_root=target_root,
            model_manifest_sha256=model_sha,
            target_manifest_sha256=target_sha,
            target_kind="cell-target",
            system_id="C0",
            alpha=None,
            lambda_=None,
            g0_root=roots,
            g0_manifest_sha256=receipts,
            output_root=tmp_path / f"forged-{forgery}",
            expected_source_bundle_sha256=runner._source_bundle_sha(),
            stage="outer",
            repeat=0,
            outer_fold=1,
            inner_fold=None,
        )


@pytest.mark.parametrize("forgery", ["unrelated", "zero-direct"])
def test_locked_g0_validation_rejects_forged_accounting(
    tmp_path: Path, forgery: str
) -> None:
    capability, model_root, target_root, model_sha, target_sha = _capability(tmp_path)
    roots, receipts = _g0_roots(tmp_path, capability, model_sha, target_sha)
    root = roots[0]
    root.chmod(0o755)
    manifest_path = root / "manifest.json"
    manifest_path.chmod(0o644)
    manifest = json.loads(manifest_path.read_bytes())
    if forgery == "unrelated":
        manifest["operation_accounting"]["query_truth_values_opened_by_scorers"] = 1
    else:
        manifest["operation_accounting"]["direct_target_values_parsed"] = 0
    manifest_bytes = g0.bound.json_bytes(manifest)
    manifest_path.write_bytes(manifest_bytes)
    manifest_path.chmod(0o444)
    root.chmod(0o555)
    receipts[0] = hashlib.sha256(manifest_bytes).hexdigest()
    with pytest.raises(runner.PairCellRunnerError, match="accounting"):
        runner.run(
            model_public_root=model_root,
            target_root=target_root,
            model_manifest_sha256=model_sha,
            target_manifest_sha256=target_sha,
            target_kind="cell-target",
            system_id="C0",
            alpha=None,
            lambda_=None,
            g0_root=roots,
            g0_manifest_sha256=receipts,
            output_root=tmp_path / f"g0-forged-{forgery}",
            expected_source_bundle_sha256=runner._source_bundle_sha(),
            stage="outer",
            repeat=0,
            outer_fold=1,
            inner_fold=None,
        )


def test_direct_publisher_rejects_caller_forged_zero_capability_counts(
    tmp_path: Path,
) -> None:
    material = _c0_publication_material(tmp_path)
    result = material["result"]
    accounting = dict(result.accounting)
    accounting["direct_target_values_parsed"] = 0
    forged = replace(result, accounting=accounting)
    assert not hasattr(pair_io, "PairPublicationRecord")
    assert not hasattr(pair_io, "_authenticated_pair_publication_record")
    with pytest.raises(pair_io.OraclePairCellIOError, match="accounting"):
        pair_io.publish_authenticated_pair_cell(
            tmp_path / "forged-zero-counts",
            forged,
            model_public_root=material["model_root"],
            target_root=material["target_root"],
            expected_model_manifest_sha256=material["model_sha"],
            expected_target_manifest_sha256=material["target_sha"],
            target_kind="cell-target",
            expected_scope=("outer", 0, 1, None),
            g0_root=material["g0_roots"],
            expected_g0_manifest_sha256=material["g0_receipts"],
            runner_source_sha256=runner._source_bundle_sha(),
            runtime=runner._runtime(),
        )


@pytest.mark.parametrize("poison", ["episode", "manifest"])
def test_direct_publisher_rejects_unrelated_g0_binding_material(
    tmp_path: Path, poison: str
) -> None:
    material = _c0_publication_material(tmp_path)
    receipts = list(material["g0_receipts"])
    if poison == "manifest":
        receipts[0] = "f" * 64
    else:
        root = material["g0_roots"][0]
        root.chmod(0o755)
        manifest_path = root / "manifest.json"
        manifest_path.chmod(0o644)
        manifest = json.loads(manifest_path.read_bytes())
        manifest["episode"]["episode_id"] = "f" * 64
        manifest_bytes = g0.bound.json_bytes(manifest)
        manifest_path.write_bytes(manifest_bytes)
        manifest_path.chmod(0o444)
        root.chmod(0o555)
        receipts[0] = hashlib.sha256(manifest_bytes).hexdigest()
    with pytest.raises(ValueError, match="G0"):
        pair_io.publish_authenticated_pair_cell(
            tmp_path / f"unrelated-g0-{poison}",
            material["result"],
            model_public_root=material["model_root"],
            target_root=material["target_root"],
            expected_model_manifest_sha256=material["model_sha"],
            expected_target_manifest_sha256=material["target_sha"],
            target_kind="cell-target",
            expected_scope=("outer", 0, 1, None),
            g0_root=material["g0_roots"],
            expected_g0_manifest_sha256=receipts,
            runner_source_sha256=runner._source_bundle_sha(),
            runtime=runner._runtime(),
        )


@pytest.mark.parametrize("poison", ["sha256", "candidate_id", "alpha", "lambda_"])
def test_direct_publisher_rejects_forged_t0_token_fields(
    tmp_path: Path, poison: str
) -> None:
    material = _c0_publication_material(tmp_path)
    capability = material["capability"]
    t0_capability = replace(capability, system_id="T0")
    token_root, token_sha = _token_root(
        tmp_path, system_id="T0", alpha=1.0, lambda_=2.0
    )
    token = pair_io.load_selection_token(
        token_root,
        expected_sha256=token_sha,
        requested_system_id="T0",
        repeat=0,
        outer_fold=1,
        alpha=1.0,
        lambda_=2.0,
    )
    predictions = _legacy_g0_predictions(t0_capability, material["g0_fragments"])
    result = runner.run_shared_outer_t0(
        t0_capability,
        alpha=1.0,
        lambda_=2.0,
        selection_token_sha256=token.sha256,
        g0_predictions=predictions,
    )[0]
    forged_values: dict[str, Any] = {
        "sha256": "f" * 64,
        "candidate_id": "e" * 64,
        "alpha": 10.0,
        "lambda_": 4.0,
    }
    token_root.chmod(0o755)
    token_path = token_root / pair_io.TOKEN_FILE
    token_path.chmod(0o644)
    token_payload = json.loads(token_path.read_bytes())
    token_payload[poison if poison != "lambda_" else "lambda"] = forged_values[poison]
    forged_bytes = (
        json.dumps(
            token_payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    token_path.write_bytes(forged_bytes)
    token_path.chmod(0o444)
    token_root.chmod(0o555)
    with pytest.raises(pair_io.OraclePairCellIOError, match="token receipt"):
        pair_io.publish_authenticated_pair_cell(
            tmp_path / f"forged-token-{poison}",
            result,
            model_public_root=material["model_root"],
            target_root=material["target_root"],
            expected_model_manifest_sha256=material["model_sha"],
            expected_target_manifest_sha256=material["target_sha"],
            target_kind="cell-target",
            expected_scope=("outer", 0, 1, None),
            g0_root=material["g0_roots"],
            expected_g0_manifest_sha256=material["g0_receipts"],
            runner_source_sha256=runner._source_bundle_sha(),
            runtime=runner._runtime(),
            selection_token_root=token_root,
            expected_selection_token_sha256=token_sha,
            selected_alpha=1.0,
            selected_lambda=2.0,
        )


@pytest.mark.skipif(
    not LOCKED_G0_PYTHON.is_file(), reason="locked research runtime unavailable"
)
def test_actual_locked_g0_output_feeds_pair_publication(tmp_path: Path) -> None:
    locked_root = tmp_path / "locked"
    locked_root.mkdir()
    model, model_sha, episode, episode_sha = locked_g0_fixture(locked_root)
    locked_output = tmp_path / "locked-g0-output"
    completed = subprocess.run(
        locked_g0_argv(model, model_sha, episode, episode_sha, locked_output),
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
        env={"PATH": os.environ.get("PATH", "")},
    )
    assert completed.returncode == 0, completed.stderr
    with (model / "public_episode_queries.csv").open(newline="") as handle:
        public = list(csv.DictReader(handle))
    _actual, fragments = pair_io.load_g0_fragments(
        locked_output,
        expected_manifest_sha256=_sha(locked_output / "manifest.json"),
        scope=("outer", 0, 1, None),
        public_queries=public,
    )
    bindings = runner._g0_binding_records(
        fragments,
        model_manifest_sha256=model_sha,
        stage="outer",
        repeat=0,
        outer_fold=1,
        inner_fold=None,
        source_cell_target_manifest_sha256="5" * 64,
        public_queries=public,
    )
    assert len(bindings) == 1
    capability, model_root, target_root, pair_model_sha, _target_sha = _capability(
        tmp_path / "pair"
    )
    assert isinstance(capability.target, OracleCellTargetCapability)
    actual_episode_id = public[0]["episode_id"]
    contexts = [dict(row) for row in capability.target.episode_anchor_contexts]
    selected_contexts = [
        row for row in contexts if row["episode_id"] == actual_episode_id
    ]
    assert len(selected_contexts) == 1
    selected_contexts[0]["anchor_point_available"] = "false"
    selected_contexts[0]["anchor_point"] = ""
    target_root.chmod(0o755)
    context_path = target_root / "episode_anchor_contexts.csv"
    manifest_path = target_root / "manifest.json"
    context_path.chmod(0o644)
    manifest_path.chmod(0o644)
    target_manifest = json.loads(manifest_path.read_bytes())
    columns = tuple(
        target_manifest["output_receipts"]["episode_anchor_contexts.csv"]["columns"]
    )
    context_bytes = canonical_csv_bytes(columns, contexts)
    context_path.write_bytes(context_bytes)
    target_manifest["output_receipts"]["episode_anchor_contexts.csv"] = {
        "sha256": hashlib.sha256(context_bytes).hexdigest(),
        "bytes": len(context_bytes),
        "rows": len(contexts),
        "columns": list(columns),
    }
    target_manifest["operation_accounting"]["anchor_labels_exposed_to_models"] = 1
    target_manifest_bytes = canonical_json_bytes(target_manifest)
    manifest_path.write_bytes(target_manifest_bytes)
    context_path.chmod(0o444)
    manifest_path.chmod(0o444)
    target_root.chmod(0o555)
    pair_target_sha = hashlib.sha256(target_manifest_bytes).hexdigest()
    capability = load_oracle_cell_capability(
        model_root,
        target_root,
        expected_model_manifest_sha256=pair_model_sha,
        expected_target_manifest_sha256=pair_target_sha,
        system_id="C0",
        target_kind="cell-target",
        expected_scope=("outer", 0, 1, None),
    )
    supplemental_root = tmp_path / "supplemental"
    supplemental_root.mkdir()
    supplemental_roots, supplemental_receipts = _g0_roots(
        supplemental_root, capability, pair_model_sha, pair_target_sha
    )
    combined_roots: list[Path] = []
    combined_receipts: list[str] = []
    for root, receipt in zip(supplemental_roots, supplemental_receipts, strict=True):
        manifest = json.loads((root / "manifest.json").read_bytes())
        if manifest["episode"]["episode_id"] == actual_episode_id:
            combined_roots.append(locked_output)
            combined_receipts.append(_sha(locked_output / "manifest.json"))
        else:
            combined_roots.append(root)
            combined_receipts.append(receipt)
    scoped_episodes = {
        row["episode_id"] for row in capability.target.episode_anchor_contexts
    }
    pair_public = [
        row
        for row in capability.model_public.public_queries
        if row["episode_id"] in scoped_episodes
    ]
    combined_predictions, _combined_fragments = pair_io.load_g0_fragments(
        combined_roots,
        expected_manifest_sha256=combined_receipts,
        scope=("outer", 0, 1, None),
        public_queries=pair_public,
    )
    result = run_pair_cell(
        capability,
        system_id="C0",
        alpha=None,
        lambda_=None,
        g0_predictions=combined_predictions,
    )
    output = pair_io.publish_authenticated_pair_cell(
        tmp_path / "actual-pair-output",
        result,
        model_public_root=model_root,
        target_root=target_root,
        expected_model_manifest_sha256=pair_model_sha,
        expected_target_manifest_sha256=pair_target_sha,
        target_kind="cell-target",
        expected_scope=("outer", 0, 1, None),
        g0_root=combined_roots,
        expected_g0_manifest_sha256=combined_receipts,
        runner_source_sha256=runner._source_bundle_sha(),
        runtime=runner._runtime(),
    )
    assert (output / "prediction_fragment.csv").is_file()
    assert any(
        row["prediction_source"] == "G0"
        and float(row["prediction"])
        == combined_predictions[
            (row["episode_id"], row["query_molecule_id"], int(row["query_rank"]))
        ]
        for row in result.rows
    )


def test_runner_rejects_source_bundle_drift_before_capability_open(
    tmp_path: Path,
) -> None:
    capability, model_root, target_root, model_sha, target_sha = _capability(tmp_path)
    roots, receipts = _g0_roots(tmp_path, capability, model_sha, target_sha)
    with pytest.raises(
        runner.PairCellRunnerError, match="pair runner source bundle receipt differs"
    ):
        runner.run(
            model_public_root=model_root,
            target_root=target_root,
            model_manifest_sha256=model_sha,
            target_manifest_sha256=target_sha,
            target_kind="cell-target",
            system_id="C0",
            alpha=None,
            lambda_=None,
            g0_root=roots,
            g0_manifest_sha256=receipts,
            output_root=tmp_path / "pair-output",
            expected_source_bundle_sha256="0" * 64,
            stage="outer",
            repeat=0,
            outer_fold=1,
            inner_fold=None,
        )


def test_transitive_scientific_source_mutation_changes_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = runner._source_bundle_sha()
    witness = runner.ROOT / "src/cypshift/chemistry.py"
    original = Path.read_bytes

    def mutated(path: Path) -> bytes:
        data = original(path)
        return data + b"\n" if path == witness else data

    monkeypatch.setattr(Path, "read_bytes", mutated)
    assert runner._source_bundle_sha() != before


def test_selection_token_stage_and_system_matrix(tmp_path: Path) -> None:
    t0_root, t0_sha = _token_root(tmp_path, system_id="T0", alpha=1.0, lambda_=2.0)
    token = pair_io.load_selection_token(
        t0_root,
        expected_sha256=t0_sha,
        requested_system_id="F2",
        repeat=0,
        outer_fold=1,
        alpha=1.0,
        lambda_=2.0,
    )
    assert token.system_id == "T0" and token.sha256 == t0_sha
    with pytest.raises(pair_io.OraclePairCellIOError, match="binding"):
        pair_io.load_selection_token(
            t0_root,
            expected_sha256=t0_sha,
            requested_system_id="C2",
            repeat=0,
            outer_fold=1,
            alpha=1.0,
            lambda_=None,
        )
    with pytest.raises(runner.PairCellRunnerError, match="F2 is outer-only"):
        runner.run(
            model_public_root=tmp_path / "unopened-model",
            target_root=tmp_path / "unopened-target",
            model_manifest_sha256="1" * 64,
            target_manifest_sha256="2" * 64,
            target_kind="cell-target",
            system_id="F2",
            alpha=1.0,
            lambda_=2.0,
            g0_root=tmp_path / "unopened-g0",
            g0_manifest_sha256="3" * 64,
            output_root=tmp_path / "unopened-output",
            expected_source_bundle_sha256=runner._source_bundle_sha(),
            stage="inner",
            repeat=0,
            outer_fold=1,
            inner_fold=0,
        )


def test_c3_requires_explicit_measured_source_cell_parent(tmp_path: Path) -> None:
    with pytest.raises(runner.PairCellRunnerError, match="measured source-cell parent"):
        runner.run(
            model_public_root=tmp_path / "unopened-model",
            target_root=tmp_path / "unopened-target",
            model_manifest_sha256="1" * 64,
            target_manifest_sha256="2" * 64,
            target_kind="c3-target",
            system_id="C3",
            alpha=1.0,
            lambda_=2.0,
            g0_root=tmp_path / "unopened-g0",
            g0_manifest_sha256="3" * 64,
            output_root=tmp_path / "unopened-output",
            expected_source_bundle_sha256=runner._source_bundle_sha(),
            stage="outer",
            repeat=0,
            outer_fold=1,
            inner_fold=None,
        )


def test_shared_outer_t0_cli_path_publishes_three_fragments(tmp_path: Path) -> None:
    capability, model_root, target_root, model_sha, target_sha = _capability(tmp_path)
    roots, receipts = _g0_roots(tmp_path, capability, model_sha, target_sha)
    token_root, token_sha = _token_root(
        tmp_path, system_id="T0", alpha=1.0, lambda_=2.0
    )
    outputs = runner.run_shared_t0(
        model_public_root=model_root,
        target_root=target_root,
        model_manifest_sha256=model_sha,
        target_manifest_sha256=target_sha,
        alpha=1.0,
        lambda_=2.0,
        g0_root=roots,
        g0_manifest_sha256=receipts,
        t0_output_root=tmp_path / "t0-output",
        f0_output_root=tmp_path / "f0-output",
        f1_output_root=tmp_path / "f1-output",
        expected_source_bundle_sha256=runner._source_bundle_sha(),
        repeat=0,
        outer_fold=1,
        selection_token_root=token_root,
        selection_token_sha256=token_sha,
    )
    manifests = [json.loads((root / "manifest.json").read_bytes()) for root in outputs]
    assert [item["system_id"] for item in manifests] == ["T0", "F0", "F1"]
    assert manifests[0]["operation_accounting"]["ridge_model_fits"] == 1
    for control in manifests[1:]:
        assert control["operation_accounting"]["direct_target_values_parsed"] == 0
        assert control["operation_accounting"]["ridge_model_fits"] == 0

from __future__ import annotations

import importlib
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parents[1]
RESEARCH = ROOT / "research" / "maplight-fixed"
sys.path.insert(0, str(RESEARCH))
base = importlib.import_module("global_v2_maplight_runner")
g1 = importlib.import_module("global_v2_g1_runner")
synthetic = importlib.import_module("run_global_v2_g1_synthetic")


@contextmanager
def _writable(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts)):
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    os.chmod(root, 0o755)
    yield root


def _reseal(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        os.chmod(path, 0o555 if path.is_dir() else 0o444)
    os.chmod(root, 0o555)


def _rewrite_source(root: Path, name: str, value: bytes) -> None:
    with _writable(root):
        (root / name).write_bytes(value)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        manifest["source_receipts"][name] = base.sha256_bytes(value)
        (root / "manifest.json").write_bytes(base.json_bytes(manifest))
    _reseal(root)


def _compile(tmp_path: Path, *, reverse: bool = False) -> tuple[Path, Path, Path]:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=reverse)
    return g1.compile_capabilities(
        source_root=source,
        output_root=tmp_path / "capabilities",
        expected_runner_sha256=base.sha256_path(g1.SCRIPT),
    )


@pytest.fixture(scope="module")
def fake_replays(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("g1-fake-replays")
    terminals: list[Path] = []
    for name, reverse in (("a", False), ("b", True)):
        source = synthetic.publish_source(root=root / f"{name}-source", reverse=reverse)
        terminals.append(
            synthetic.run_replay(
                source_root=source,
                replay_root=root / name,
                reverse_execution_order=reverse,
                probe_runner=g1.publish_fake_runtime_probes,
                allow_test_double=True,
            )
        )
    return terminals[0], terminals[1]


def _valid_seed_rows(*, stage: str = "inner") -> list[dict[str, str]]:
    common = {
        "molecule_id": "molecule",
        "endpoint": "CYP1A2",
        "similarity_component_hash": "1" * 64,
        "repeat": "0",
        "outer_fold": "0",
        "configuration_id": "G1-C00",
        "prediction": "4",
        "contract_sha256": g1.CONTRACT_SHA256,
        "canonical_source_sha256": "2" * 64,
        "feature_rows_sha256": "3" * 64,
        "folds_sha256": "4" * 64,
        "target_receipt_sha256": "5" * 64,
        "split_id": "",
        "model_id": "",
    }
    if stage == "inner":
        common["inner_fold"] = "0"
    else:
        common["selection_token_sha256"] = "6" * 64
    rows = []
    for seed in g1.MODEL_SEEDS:
        row = {**common, "model_seed": str(seed)}
        if stage == "inner":
            row["model_id"] = g1._sha_text(
                g1.CONTRACT_SHA256,
                row["canonical_source_sha256"],
                "inner",
                row["endpoint"],
                row["repeat"],
                row["outer_fold"],
                row["inner_fold"],
                row["configuration_id"],
                row["model_seed"],
                row["target_receipt_sha256"],
            )
            row["split_id"] = g1._sha_text(
                row["folds_sha256"], row["repeat"], row["outer_fold"], row["inner_fold"]
            )
        else:
            row["model_id"] = g1._sha_text(
                g1.CONTRACT_SHA256,
                row["canonical_source_sha256"],
                "outer",
                row["endpoint"],
                row["repeat"],
                row["outer_fold"],
                row["configuration_id"],
                row["model_seed"],
                row["selection_token_sha256"],
                row["target_receipt_sha256"],
            )
            row["split_id"] = g1._sha_text(
                row["folds_sha256"], row["repeat"], row["outer_fold"], "outer"
            )
        rows.append(row)
    return rows


def test_implementation_binds_exact_contract_parent_metric_lock_and_screen() -> None:
    contract, parent = g1._static_contract()
    assert contract["gate"] == "G2_3B_EXP_G1_SYNTHETIC_IMPLEMENTATION_CONTRACT_FROZEN"
    assert base.sha256_path(g1.SCRIPT) != "0" * 64
    assert base.sha256_path(g1.PARENT) == g1.PARENT_SHA256
    assert base.sha256_path(g1.METRIC_SOURCE) == g1.METRIC_SOURCE_SHA256
    assert base.sha256_path(g1.LOCK) == g1.LOCK_SHA256
    assert [item["configuration_id"] for item in parent["screen"]["configurations"]] == list(g1.CONFIGURATION_IDS)
    assert parent["screen"]["model_seeds"] == list(g1.MODEL_SEEDS)
    assert g1._probe_identities() == [
        *((configuration, 20260824) for configuration in g1.CONFIGURATION_IDS),
        ("G1-C00", 20260825),
        ("G1-C00", 20260826),
    ]


def test_fixture_has_exact_family_shape_missingness_and_predeclared_oracles(tmp_path: Path) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["counts"] == {
        "molecules": 80,
        "components": 40,
        "molecules_per_component": 2,
        "feature_columns": 2563,
        "fold_rows": 1200,
        "truth_rows": 320,
    }
    assert len(manifest["selection_oracles"]) == 60
    assert len({row["configuration_id"] for row in manifest["selection_oracles"]}) == 3
    assert manifest["selection_oracles"][0]["configuration_id"] == "G1-C00"
    assert set(manifest["future_endpoint_oracles"].values()) == {"G1-C01"}
    truth = base._read_csv(source / "truth.csv", g1.TRUTH_COLUMNS)
    assert any(row["availability"] == "missing" for row in truth)
    assert all(
        row["point"] == row["low"] == row["high"] == ""
        for row in truth
        if row["availability"] == "missing"
    )


def test_compiler_capabilities_are_disjoint_family_safe_and_least_privilege(tmp_path: Path) -> None:
    model, selector, scorer = _compile(tmp_path)
    assert not any(path.name in {"truth.csv", "outer_truth.csv"} for path in model.rglob("*"))
    assert {path.name for path in selector.iterdir()} == {"inner_validation_truth.csv", "manifest.json"}
    assert {path.name for path in scorer.iterdir()} == {"outer_truth.csv", "baseline_predictions.csv", "manifest.json"}
    model_manifest = json.loads((model / "manifest.json").read_text(encoding="utf-8"))
    selector_manifest = json.loads((selector / "manifest.json").read_text(encoding="utf-8"))
    scorer_manifest = json.loads((scorer / "manifest.json").read_text(encoding="utf-8"))
    assert model_manifest["counts"] == {"molecules": 80, "components": 40, "target_files": 300}
    assert len(list((model / "targets").rglob("*.csv"))) == 300
    assert model_manifest["authority"]["synthetic_model_double_execution"]
    assert not selector_manifest["authority"]["synthetic_model_double_execution"]
    assert selector_manifest["authority"]["synthetic_inner_selection"]
    assert scorer_manifest["authority"]["synthetic_outer_scoring"]
    for manifest in (model_manifest, selector_manifest, scorer_manifest):
        assert not any(manifest["authority"][name] for name in g1.DENIED_AUTHORITY)


def test_two_full_topology_replays_are_byte_identical_and_mechanics_only(
    fake_replays: tuple[Path, Path],
) -> None:
    terminal_a, terminal_b = fake_replays
    assert g1.relative_byte_map(terminal_a) == g1.relative_byte_map(terminal_b)
    manifest = json.loads((terminal_a / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "G2_3B_EXP_G1_SYNTHETIC_ACCEPTED"
    assert manifest["counts"]["model_double_invocations"] == 8820
    assert manifest["counts"]["inner_model_double_invocations"] == 8640
    assert manifest["counts"]["outer_model_double_invocations"] == 180
    assert manifest["counts"]["inner_raw_prediction_rows"] == 138240
    assert manifest["counts"]["inner_frozen_prediction_rows"] == 46080
    assert manifest["counts"]["complete_selection_projection_rows"] == 11520
    assert manifest["counts"]["real_catboost_fits"] == 14
    assert manifest["runtime_probe_test_double"] is True
    assert all(manifest["accounting"][name] == 0 for name in g1.OFFICIAL_ZERO_FIELDS)
    result = json.loads((terminal_a / "g1_synthetic_result.json").read_text(encoding="utf-8"))
    assert "select or rank" in result["scientific_interpretation"]
    assert result["expected_inner_selections_match"]
    assert result["expected_future_endpoint_tokens_match"]


def test_cross_root_capability_mix_is_rejected(tmp_path: Path) -> None:
    compiled = []
    for name, reverse in (("a", False), ("b", True)):
        source = synthetic.publish_source(root=tmp_path / f"{name}-source", reverse=reverse)
        compiled.append(
            g1.compile_capabilities(
                source_root=source,
                output_root=tmp_path / f"{name}-capabilities",
                expected_runner_sha256=base.sha256_path(g1.SCRIPT),
            )
        )
    inner_raw = g1.run_inner_models(
        model_capability_root=compiled[0][0], output_root=tmp_path / "inner-raw"
    )
    frozen = g1.freeze_inner_predictions(raw_root=inner_raw, output_root=tmp_path / "frozen")
    with pytest.raises(g1.G1SyntheticError, match="root instance"):
        g1.select_inner_configurations(
            frozen_root=frozen,
            selector_capability_root=compiled[1][1],
            output_root=tmp_path / "mixed",
        )


def test_outer_family_crossing_fails_before_model_stage(tmp_path: Path) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)
    rows = base._read_csv(source / "folds.csv", g1.FOLD_COLUMNS)
    first = rows[0]
    peer_molecule = next(
        row["molecule_id"]
        for row in rows
        if row["similarity_component_hash"] == first["similarity_component_hash"]
        and row["molecule_id"] != first["molecule_id"]
    )
    changed_outer = (int(first["outer_fold"]) + 1) % 5
    for row in rows:
        if row["molecule_id"] == peer_molecule and row["repeat"] == first["repeat"]:
            row["outer_fold"] = str(changed_outer)
            context = int(row["outer_validation_fold"])
            row["inner_fold"] = "" if context == changed_outer else str(context % 4)
    _rewrite_source(source, "folds.csv", base.csv_bytes(g1.FOLD_COLUMNS, rows))
    with pytest.raises(g1.G1SyntheticError, match="outer boundary"):
        g1.compile_capabilities(
            source_root=source,
            output_root=tmp_path / "compiled",
            expected_runner_sha256=base.sha256_path(g1.SCRIPT),
        )


def test_scoped_inner_family_crossing_fails_before_model_stage(tmp_path: Path) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)
    rows = base._read_csv(source / "folds.csv", g1.FOLD_COLUMNS)
    first = next(row for row in rows if row["inner_fold"] != "")
    peer = next(
        row
        for row in rows
        if row["similarity_component_hash"] == first["similarity_component_hash"]
        and row["molecule_id"] != first["molecule_id"]
        and row["repeat"] == first["repeat"]
        and row["outer_validation_fold"] == first["outer_validation_fold"]
    )
    peer["inner_fold"] = str((int(peer["inner_fold"]) + 1) % 4)
    _rewrite_source(source, "folds.csv", base.csv_bytes(g1.FOLD_COLUMNS, rows))
    with pytest.raises(g1.G1SyntheticError, match="inner boundary"):
        g1.compile_capabilities(
            source_root=source,
            output_root=tmp_path / "compiled",
            expected_runner_sha256=base.sha256_path(g1.SCRIPT),
        )


def test_wrong_feature_order_and_width_fail_closed(tmp_path: Path) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)
    first = (source / "maplight_morgan_count.npy").read_bytes()
    second = (source / "maplight_avalon_count.npy").read_bytes()
    _rewrite_source(source, "maplight_morgan_count.npy", second)
    _rewrite_source(source, "maplight_avalon_count.npy", first)
    with pytest.raises(g1.G1SyntheticError, match="feature-order sentinels"):
        g1.compile_capabilities(
            source_root=source,
            output_root=tmp_path / "compiled",
            expected_runner_sha256=base.sha256_path(g1.SCRIPT),
        )


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda rows: rows[:2], "cardinality"),
        (lambda rows: [rows[0], rows[0], rows[2]], "seed set"),
        (lambda rows: [*rows, rows[0]], "cardinality"),
        (lambda rows: [{**rows[0], "model_seed": "7"}, *rows[1:]], "seed set"),
    ],
)
def test_missing_duplicate_extra_and_wrong_seed_fail(
    mutation: Any, match: str
) -> None:
    with pytest.raises(g1.G1SyntheticError, match=match):
        g1._validated_seed_mean(mutation(_valid_seed_rows()), stage="inner")


def test_prediction_identity_forgery_and_nonfinite_value_fail() -> None:
    forged = _valid_seed_rows(stage="outer")
    forged[1]["model_id"] = "0" * 64
    with pytest.raises(g1.G1SyntheticError, match="forged"):
        g1._validated_seed_mean(forged, stage="outer")
    nonfinite = _valid_seed_rows()
    nonfinite[1]["prediction"] = "nan"
    with pytest.raises(g1.G1SyntheticError, match="nonfinite"):
        g1._validated_seed_mean(nonfinite, stage="inner")
    wrong_configuration = _valid_seed_rows()
    for row in wrong_configuration:
        row["configuration_id"] = "G1-C12"
    with pytest.raises(g1.G1SyntheticError, match="configuration"):
        g1._validated_seed_mean(wrong_configuration, stage="inner")


def test_selector_cannot_consume_outer_truth_capability(tmp_path: Path) -> None:
    model, _selector, scorer = _compile(tmp_path)
    inner_raw = g1.run_inner_models(model_capability_root=model, output_root=tmp_path / "raw")
    frozen = g1.freeze_inner_predictions(raw_root=inner_raw, output_root=tmp_path / "frozen")
    with pytest.raises(g1.G1SyntheticError, match="selector capability"):
        g1.select_inner_configurations(
            frozen_root=frozen,
            selector_capability_root=scorer,
            output_root=tmp_path / "selected",
        )
    with pytest.raises(g1.G1SyntheticError, match="model capability"):
        g1._load_model_capability(scorer)


def test_nonpositive_tutorial_denominator_and_nonfinite_bootstrap_fail() -> None:
    truth = [
        {
            "molecule_id": "a",
            "endpoint": "CYP1A2",
            "similarity_component_hash": "1" * 64,
            "availability": "complete",
            "point": "4",
            "low": "3",
            "high": "5",
        },
        {
            "molecule_id": "b",
            "endpoint": "CYP1A2",
            "similarity_component_hash": "2" * 64,
            "availability": "complete",
            "point": "4",
            "low": "3",
            "high": "5",
        },
    ]
    with pytest.raises(Exception, match="denominator"):
        g1._tutorial_score(truth, {"a": 4.0, "b": 4.0}, "CYP1A2")
    with pytest.raises(g1.G1SyntheticError, match="quantile"):
        g1._quantile([0.0, float("nan")], 0.5)


def test_partial_probe_set_and_test_double_acceptance_fail(
    fake_replays: tuple[Path, Path], tmp_path: Path
) -> None:
    with pytest.raises(g1.G1SyntheticError, match="test-double terminal"):
        synthetic.accept_replays(
            terminal_a=fake_replays[0],
            terminal_b=fake_replays[1],
            output_root=tmp_path / "acceptance",
            focused_tests_passed=14,
        )
    probes = json.loads(
        (fake_replays[0] / "g1_synthetic_runtime_probes.json").read_text(
            encoding="utf-8"
        )
    )
    with pytest.raises(g1.G1SyntheticError, match="row count"):
        g1._validate_probe_rows(base.json_bytes(probes[:-1]))
    probes[0]["resolved_parameter_sha256"] = "wrong"
    with pytest.raises(g1.G1SyntheticError, match="evidence"):
        g1._validate_probe_rows(base.json_bytes(probes))


def test_nonfinite_source_truth_and_runtime_drift_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)
    rows = base._read_csv(source / "truth.csv", g1.TRUTH_COLUMNS)
    first = next(row for row in rows if row["availability"] == "complete")
    first["point"] = "nan"
    _rewrite_source(source, "truth.csv", base.csv_bytes(g1.TRUTH_COLUMNS, rows))
    with pytest.raises(g1.G1SyntheticError, match="nonfinite"):
        g1.compile_capabilities(
            source_root=source,
            output_root=tmp_path / "compiled",
            expected_runner_sha256=base.sha256_path(g1.SCRIPT),
        )
    monkeypatch.setattr(g1.importlib.metadata, "version", lambda _name: "0.0.0")
    with pytest.raises(g1.G1SyntheticError, match="runtime differs"):
        g1._runtime_identity()


def test_wrong_runner_receipt_writable_source_and_second_publication_fail(tmp_path: Path) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)
    with pytest.raises(g1.G1SyntheticError, match="runner source"):
        g1.compile_capabilities(
            source_root=source,
            output_root=tmp_path / "wrong-runner",
            expected_runner_sha256="0" * 64,
        )
    os.chmod(source, 0o755)
    with pytest.raises(base.GlobalV2MapLightError, match="writable"):
        g1.compile_capabilities(
            source_root=source,
            output_root=tmp_path / "writable",
            expected_runner_sha256=base.sha256_path(g1.SCRIPT),
        )
    _reseal(source)
    with pytest.raises(base.GlobalV2MapLightError, match="destination exists"):
        synthetic.publish_source(root=source, reverse=False)


def test_replay_retry_resume_and_overwrite_are_rejected(
    fake_replays: tuple[Path, Path], tmp_path: Path
) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)
    with pytest.raises(g1.G1SyntheticError, match="replay root exists"):
        synthetic.run_replay(
            source_root=source,
            replay_root=fake_replays[0],
            reverse_execution_order=False,
            probe_runner=g1.publish_fake_runtime_probes,
            allow_test_double=True,
        )


def test_symlink_source_and_parent_traversal_fail(tmp_path: Path) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)
    with _writable(source):
        target = source / "truth.csv"
        backup = source / "truth-real.csv"
        target.rename(backup)
        target.symlink_to(backup.name)
    _reseal(source)
    with pytest.raises(base.GlobalV2MapLightError, match="symlink"):
        g1.compile_capabilities(
            source_root=source,
            output_root=tmp_path / "compiled",
            expected_runner_sha256=base.sha256_path(g1.SCRIPT),
        )
    with pytest.raises(base.GlobalV2MapLightError, match="parent traversal"):
        base.publish_files(Path("..") / "forbidden-g1-output", {"x": b"x"})


def test_injected_failure_cleans_private_state_and_publishes_no_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)

    def fail(**_kwargs: object) -> Path:
        raise g1.G1SyntheticError("injected stage failure")

    monkeypatch.setattr(g1, "run_inner_models", fail)
    terminal = tmp_path / "terminal"
    with pytest.raises(g1.G1SyntheticError, match="injected"):
        synthetic.run_replay(
            source_root=source,
            replay_root=terminal,
            reverse_execution_order=False,
            probe_runner=g1.publish_fake_runtime_probes,
            allow_test_double=True,
        )
    assert not terminal.exists()
    assert not terminal.with_name(".terminal-private").exists()


def test_real_probe_source_preserves_exact_parent_constructor_without_fast_mode() -> None:
    source = g1.SCRIPT.read_text(encoding="utf-8")
    assert "configurations[configuration_id]" in source
    assert '"random_seed": seed' in source
    assert "model.get_params() == constructor" in source
    assert "model.fit(training, y)" in source
    assert "get_all_params" in source
    assert "fast_mode" not in source


def test_terminal_has_exact_seven_files_and_zero_forbidden_counters(
    fake_replays: tuple[Path, Path],
) -> None:
    terminal = fake_replays[0]
    assert {path.name for path in terminal.iterdir()} == {
        "g1_synthetic_selection_summary.csv",
        "g1_synthetic_outer_cell_metrics.csv",
        "g1_synthetic_endpoint_metrics.csv",
        "g1_synthetic_bootstrap_summary.json",
        "g1_synthetic_runtime_probes.json",
        "g1_synthetic_result.json",
        "manifest.json",
    }
    manifest = json.loads((terminal / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["private_roots_retained"] == 0
    assert manifest["accounting"]["synthetic_tutorial_metric_evaluations"] == 888
    assert all(manifest["accounting"][name] == 0 for name in g1.OFFICIAL_ZERO_FIELDS)

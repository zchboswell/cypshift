"""Synthetic qualification, family, final-fit and actual CSV boundaries."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np
import pytest


@pytest.fixture
def production(monkeypatch: pytest.MonkeyPatch) -> Any:
    root = Path(__file__).resolve().parents[1] / "research/maplight-fixed"
    monkeypatch.syspath_prepend(str(root))
    before = {
        name: value
        for name, value in sys.modules.items()
        if name.startswith("competition_")
    }
    stub = types.ModuleType("catboost")
    stub.CatBoostRegressor = object
    stub.CatBoostClassifier = object
    monkeypatch.setitem(sys.modules, "catboost", stub)
    spec = importlib.util.spec_from_file_location(
        "tdi_production_fixture", root / "competition_tdi_production.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        yield module
    finally:
        for name in list(sys.modules):
            if name.startswith("competition_") and name not in before:
                sys.modules.pop(name, None)
        sys.modules.update(before)


def data_fixture(n: int = 100) -> tuple[Any, np.ndarray]:
    labels = np.column_stack((np.arange(n) % 2, 1 - np.arange(n) % 2)).astype(float)
    mask = np.ones_like(labels, dtype=bool)
    mask[0, 0] = False
    labels[0, 0] = 999  # Poison outside the eligible training/metric population.
    bits = np.zeros((n, 4096), dtype=np.uint8)
    bits[:, 0] = np.arange(n) % 2
    bits[:, 1] = 1 - bits[:, 0]
    return types.SimpleNamespace(
        names=tuple(f"n{i}" for i in range(n)),
        molecule_ids=tuple(f"i{i}" for i in range(n)),
        groups=tuple(f"g{i // 2}" for i in range(n)),
        labels=labels,
        mask=mask,
        original_direct_training_mask=np.ones((n, 4), dtype=bool),
    ), bits


@pytest.mark.parametrize("procedure,expected", [("logistic", 6), ("selected", 12)])
def test_production_selection_fit_counts_and_family_exclusion(
    production: Any, tmp_path: Path, procedure: str, expected: int
) -> None:
    data, bits = data_fixture()
    calls = []

    def fit(**kw: Any) -> Any:
        train, predict = kw["train"], kw["predict"]
        assert not set(data.groups[i] for i in train) & set(
            data.groups[i] for i in predict
        )
        assert data.mask[train, kw["endpoint"]].all()
        assert set(data.labels[train, kw["endpoint"]]) == {0, 1}
        calls.append(kw)
        return bits[predict, kw["endpoint"]] * 0.8 + 0.1, {"synthetic": len(calls)}

    result = production.selection(data, bits, tmp_path, procedure, fit)
    assert len(calls) == expected
    assert len(result["endpoints"]) == 2
    assert all(item["learner"] == "logistic" for item in result["endpoints"])
    assert (
        len(result["fit_receipts"]) + 2
        == production.PRODUCTION["maximum_fits"][procedure]
    )
    with pytest.raises(FileExistsError):
        production.selection(data, bits, tmp_path, procedure, fit)


def test_unsupported_production_population_stops_before_any_fit(
    production: Any, tmp_path: Path
) -> None:
    data, bits = data_fixture()
    data.labels[:, 0] = 0

    def fit(**_: Any) -> Any:
        pytest.fail("Unsupported class population entered fitting")

    with pytest.raises(ValueError, match="support failed before fitting"):
        production.selection(data, bits, tmp_path, "selected", fit)


def test_final_logistic_uses_only_observed_rows_and_retains_reload(
    production: Any, tmp_path: Path
) -> None:
    data, bits = data_fixture(32)

    class Budget:
        @contextmanager
        def fit(self, _: Path) -> Any:
            yield

    receipt = production.fit_final(
        tmp_path, bits, data, 0, "logistic", {"fixture": True}, Budget()
    )
    final = production.authenticated_json(Path(receipt["path"]), receipt["sha256"])
    assert 0 not in final["inputs"]["training_indices"]
    assert len(final["inputs"]["training_indices"]) == 31
    assert final["maximum_reload_absolute_error"] == 0
    model = production.runner.load_model(final["checkpoint"], "logistic")
    probability = production.runner.positive_probability(
        model, production.runner.model_inputs(bits, np.arange(32), "logistic")
    )
    assert probability.shape == (32,) and np.isfinite(probability).all()
    checkpoint = Path(final["checkpoint"]["path"])
    checkpoint.write_bytes(checkpoint.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="before loading"):
        production.runner.load_model(final["checkpoint"], "logistic")


def test_csv_preserves_quoted_identity_order_and_rejects_forced_variation(
    production: Any,
) -> None:
    raw = b'Molecule_Name,SMILES\nsecond,"C,C"\nfirst,N\n'
    classes = np.array([[1, 0], [0, 1]], dtype=np.int8)
    result = production.serialize_csv(raw, classes, production.runner.digest(raw), 2)
    assert (
        result
        == b'SMILES,Molecule_Name,CYP2D6_is_TDI,CYP3A4_is_TDI\n"C,C",second,1,0\nN,first,0,1\n'
    )
    for invalid in (
        np.zeros((2, 2)),
        np.full((2, 2), np.nan),
        np.array([[0, 0.5], [1, 1]]),
    ):
        with pytest.raises(ValueError, match="binary and nonconstant"):
            production.serialize_csv(raw, invalid, production.runner.digest(raw), 2)
    with pytest.raises(ValueError, match="source receipt"):
        production.serialize_csv(raw + b"x", classes, production.runner.digest(raw), 2)


def test_core_validator_subprocess_checks_actual_750_csv_bytes(
    production: Any, tmp_path: Path
) -> None:
    raw = ("SMILES,Molecule_Name\n" + "".join(f"C,s{i}\n" for i in range(750))).encode()
    test = tmp_path / "test.csv"
    test.write_bytes(raw)
    classes = np.column_stack((np.arange(750) % 2, 1 - np.arange(750) % 2))
    (tmp_path / "submission.csv").write_bytes(
        production.serialize_csv(raw, classes, production.runner.digest(raw))
    )
    receipt = production.core_validate(
        Path(sys.executable), test, tmp_path, production.runner.digest(raw)
    )
    assert receipt["rows"] == 750 and receipt["predictions"] == 1500
    assert receipt["positive_counts"] == {"CYP2D6_is_TDI": 375, "CYP3A4_is_TDI": 375}


def seal(production: Any, path: Path, value: Any) -> str:
    path.write_bytes(production.runner.canonical(value))
    return production.runner.file_hash(path)


def qualification_fixture(
    production: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, Any, Path, str]:
    data, _ = data_fixture()
    recipe = json.loads(production.runner.RECIPE.read_bytes())
    evidence = {
        "selected_qualifies_this_seed": False,
        "logistic_qualifies_this_seed": True,
        "repeat2_required": True,
    }
    monkeypatch.setattr(production.runner, "seed_evidence", lambda *_: dict(evidence))
    audit = {
        "schema": "cypshift.phase3.tdi_audit.v1",
        "status": "complete",
        "independent_artifact_audit_passed": True,
        "production_eligible": True,
        "reserved_numeric_targets_opened": 0,
        "recipe_sha256": production.runner.file_hash(production.runner.RECIPE),
        "data_manifest_sha256": recipe["data_manifest_sha256"],
        "tdi_manifest_sha256": recipe["tdi_bundle_manifest_sha256"],
        "recommended_procedure": "logistic",
        "repeats": [],
    }
    for seed in (20260905, 20260906):
        directory = tmp_path / str(seed)
        directory.mkdir()
        experiment = {
            "recipe_sha256": audit["recipe_sha256"],
            "data_manifest_sha256": audit["data_manifest_sha256"],
            "tdi_manifest_sha256": audit["tdi_manifest_sha256"],
            "runtime": recipe["runtime"],
            "execution_git_commit": "a" * 40,
            **{
                key: list(getattr(data, key))
                for key in ("names", "molecule_ids", "groups")
            },
        }
        exphash = seal(production, directory / "experiment.json", experiment)
        outer, inner = production.runner.balanced_nested_folds(
            data.groups, data.original_direct_training_mask, seed
        )
        result = {
            "seed": seed,
            "status": "complete",
            "completed_fits": 80,
            "reserved_numeric_targets_opened": 0,
            "experiment_sha256": exphash,
            **{
                key: list(getattr(data, key))
                for key in ("names", "molecule_ids", "groups")
            },
            "outer_fold": outer.tolist(),
            "inner_fold": inner.tolist(),
            "classes": {
                name: production.runner.array_receipt(
                    directory / f"{name}.npy", np.zeros((100, 2), dtype=np.int8)
                )
                for name in ("logistic", "catboost", "selected")
            },
            **evidence,
        }
        reshash = seal(production, directory / "result.json", result)
        checked = {
            "schema": "cypshift.private.tdi_independent_audit.v1",
            "status": "passed",
            "fits": 0,
            "reserved_numeric_targets_opened": 0,
            "seed": seed,
            "script_sha256": production.AUDIT_SCRIPT_SHA256,
            "plan_sha256": production.AUDIT_PLAN_SHA256,
            "result_sha256": reshash,
            "experiment_sha256": exphash,
            "execution_commit": "a" * 40,
            "recipe_sha256": audit["recipe_sha256"],
            "data_manifest_sha256": audit["data_manifest_sha256"],
            "tdi_bundle_manifest_sha256": audit["tdi_manifest_sha256"],
            "independently_replayed_estimators": 80,
            "threshold_cells_verified": 20,
            "evidence": evidence,
        }
        checkhash = seal(production, directory / "audit.json", checked)
        audit["repeats"].append(
            {
                "seed": seed,
                "result": {"path": str(directory / "result.json"), "sha256": reshash},
                "experiment_sha256": exphash,
                "audit": {"path": str(directory / "audit.json"), "sha256": checkhash},
            }
        )
    path = tmp_path / "qualification.json"
    return data, recipe, path, seal(production, path, audit)


def test_qualification_requires_both_independent_audits_and_matching_recomputed_decision(
    production: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data, recipe, path, sha = qualification_fixture(production, tmp_path, monkeypatch)
    assert production.authorize(path, sha, data, recipe)[0] == "logistic"
    audit = json.loads(path.read_bytes())
    audit["recommended_procedure"] = "selected"
    with pytest.raises(ValueError, match="matching useful"):
        production.authorize(path, seal(production, path, audit), data, recipe)
    audit["recommended_procedure"] = "logistic"
    checked_path = Path(audit["repeats"][1]["audit"]["path"])
    checked = json.loads(checked_path.read_bytes())
    checked["independently_replayed_estimators"] = 79
    audit["repeats"][1]["audit"]["sha256"] = seal(production, checked_path, checked)
    with pytest.raises(ValueError, match="Independent replay audit"):
        production.authorize(path, seal(production, path, audit), data, recipe)
    audit["repeats"].pop()
    with pytest.raises(ValueError, match="Both independently audited"):
        production.authorize(path, seal(production, path, audit), data, recipe)


def test_alternate_root_and_unqualified_authority_never_read_test(
    production: Any, tmp_path: Path
) -> None:
    missing_test = tmp_path / "MUST_NOT_BE_READ"
    with pytest.raises(ValueError, match="shared private"):
        production.produce(
            tmp_path / "data",
            tmp_path / "tdi",
            tmp_path / "audit",
            "a" * 64,
            missing_test,
            Path(sys.executable),
            tmp_path / "other" / "run",
        )
    data, _ = data_fixture()
    path = tmp_path / "audit.json"
    sha = seal(production, path, {"status": "failed"})
    with pytest.raises(ValueError, match="authority is incomplete"):
        production.authorize(
            path, sha, data, json.loads(production.runner.RECIPE.read_bytes())
        )
    assert not missing_test.exists()


def test_failed_authority_precedes_features_fits_and_test_reads_in_real_driver(
    production: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data, _ = data_fixture()
    compiled, tdi = tmp_path / "development", tmp_path / "tdi"
    compiled.mkdir()
    tdi.mkdir()
    (compiled / "manifest.json").write_bytes(b"synthetic development")
    (tdi / "manifest.json").write_bytes(b"synthetic tdi")
    recipe = json.loads(production.runner.RECIPE.read_bytes())
    recipe["data_manifest_sha256"] = production.runner.file_hash(
        compiled / "manifest.json"
    )
    recipe["tdi_bundle_manifest_sha256"] = production.runner.file_hash(
        tdi / "manifest.json"
    )
    recipe_path = tmp_path / "recipe.json"
    seal(production, recipe_path, recipe)
    monkeypatch.setattr(production.runner, "RECIPE", recipe_path)
    monkeypatch.setattr(production.runner, "resource_receipt", lambda: {})
    monkeypatch.setattr(production.runner, "freeze_interrupted_fits", lambda _: None)
    monkeypatch.setattr(
        production.runner,
        "source_identity",
        lambda _: {"execution_git_commit": "a" * 40},
    )
    monkeypatch.setattr(
        production.subprocess,
        "check_output",
        lambda args, **_: (production.ROOT / args[-1].split(":", 1)[1]).read_bytes(),
    )
    monkeypatch.setattr(production, "load_tdi_development", lambda *_: data)
    monkeypatch.setattr(
        production,
        "featurize_binary_morgan",
        lambda *_: pytest.fail("Features before authorization"),
    )
    finished = []

    class Budget:
        def __init__(self, *_: Any) -> None:
            pass

        def limit(self) -> None:
            pass

        def remaining(self) -> tuple[float, float]:
            return 30, 30

        def finish(self, status: str) -> None:
            finished.append(status)

    monkeypatch.setattr(production, "ProductionBudget", Budget)
    audit = tmp_path / "bad-audit.json"
    sha = seal(production, audit, {"status": "failed"})
    output = tmp_path / "run"
    with pytest.raises(ValueError, match="authority is incomplete"):
        production.produce(
            compiled,
            tdi,
            audit,
            sha,
            tmp_path / "MUST_NOT_BE_READ",
            Path(sys.executable),
            output,
        )
    assert finished == ["failed"]
    assert not (output / "fits").exists()
    assert not (output / "submission.csv").exists()
    assert (
        json.loads((output / "failure.json").read_bytes())["submission_ready"] is False
    )
    with (tmp_path / "compute.lock").open("a+") as lock:
        production.fcntl.flock(
            lock, production.fcntl.LOCK_EX | production.fcntl.LOCK_NB
        )


def test_constant_logistic_oof_cannot_deploy_diagnostic_threshold(
    production: Any, tmp_path: Path
) -> None:
    data, bits = data_fixture()
    calls = []

    def fit(**kwargs: Any) -> Any:
        calls.append(kwargs)
        return np.full(len(kwargs["predict"]), 0.5), {"synthetic": len(calls)}

    with pytest.raises(ValueError, match="cannot select a nonconstant threshold"):
        production.selection(data, bits, tmp_path, "logistic", fit)
    assert len(calls) == 3
    assert not (tmp_path / "selection.json").exists()

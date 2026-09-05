"""Release safety tests, independent of the exhaustive CSV validator tests."""

from __future__ import annotations

import csv
import hashlib
import importlib
import io
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


@pytest.fixture
def release(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return importlib.import_module("build_calibrated_competition_release")


def _experiment(root: Path) -> dict[str, Any]:
    root.mkdir()
    experiment = json.dumps(
        {"molecule_ids": ["a", "b"], "groups": ["g1", "g2"]}
    ).encode()
    oof = b"synthetic receipt witness; release builder never parses target arrays"
    (root / "experiment.json").write_bytes(experiment)
    (root / "oof.npz").write_bytes(oof)

    def score(primary: float) -> dict[str, Any]:
        return {
            "macro_bootstrap_mean_st_rae": primary,
            "macro_component_mae": 0.5,
            "bootstrap_samples": 1000,
            "bootstrap_seed": 0,
            "endpoints": {
                endpoint: {
                    "rows": 2,
                    "groups": 2,
                    "bootstrap_mean_st_rae": primary,
                    "component_mae": 0.5,
                }
                for endpoint in ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
            },
        }

    result = {
        "status": "complete",
        "candidate": "maplight-inner-oof-affine",
        "decision": {"release_eligible_on_paired_metrics": True},
        "reserved_numeric_targets_opened": 0,
        "experiment_sha256": hashlib.sha256(experiment).hexdigest(),
        "oof_sha256": hashlib.sha256(oof).hexdigest(),
        "deployment_calibration": [[1.0, 0.1]] * 4,
        "baseline": score(1.0),
        "candidate_scores": score(0.99),
        "paired_family": {
            "lower_95": -0.02,
            "upper_95": 0.01,
            "candidate_minus_baseline_mean": -0.01,
            "samples": 2000,
            "seed": 20260906,
            "families": 2,
        },
    }
    (root / "result.json").write_text(json.dumps(result))
    return result


@pytest.mark.parametrize("failure", ["ineligible", "tampered_oof", "identity"])
def test_bad_evidence_cannot_access_predictions_or_publish(
    tmp_path: Path, release: ModuleType, failure: str
) -> None:
    experiment = tmp_path / "experiment"
    result = _experiment(experiment)
    if failure == "ineligible":
        result["decision"]["release_eligible_on_paired_metrics"] = False
    elif failure == "tampered_oof":
        (experiment / "oof.npz").write_bytes(b"changed")
    else:
        result["deployment_calibration"] = [[1.0, 0.0]] * 4
    (experiment / "result.json").write_text(json.dumps(result))
    output = tmp_path / "release"
    # Missing prediction paths deliberately prove evidence rejection happens first.
    with pytest.raises(ValueError):
        release.build_release(
            experiment, tmp_path / "missing-test", tmp_path / "missing-baseline", output
        )
    assert not output.exists()


@pytest.mark.parametrize(
    "failure", ["dominated", "reversed_interval", "nonfinite_interval"]
)
def test_stale_eligibility_and_malformed_uncertainty_cannot_publish(
    tmp_path: Path, release: ModuleType, failure: str
) -> None:
    experiment = tmp_path / "experiment"
    result = _experiment(experiment)
    if failure == "dominated":
        result["candidate_scores"]["macro_bootstrap_mean_st_rae"] = 1.1
        result["candidate_scores"]["macro_component_mae"] = 0.6
        for endpoint in result["candidate_scores"]["endpoints"].values():
            endpoint["bootstrap_mean_st_rae"] = 1.1
            endpoint["component_mae"] = 0.6
    elif failure == "reversed_interval":
        result["paired_family"]["lower_95"] = 0.02
    else:
        result["paired_family"]["upper_95"] = "not a metric"
    (experiment / "result.json").write_text(json.dumps(result))
    output = tmp_path / "release"
    with pytest.raises(ValueError, match="contradicts|interval|finite"):
        release.build_release(
            experiment, tmp_path / "missing-test", tmp_path / "missing-baseline", output
        )
    assert not output.exists()


def test_reject_git_destinations_and_existing_release_without_mutation(
    tmp_path: Path, release: ModuleType
) -> None:
    repository = tmp_path / "repo"
    (repository / ".git").mkdir(parents=True)
    with pytest.raises(ValueError, match="outside Git"):
        release.build_release(tmp_path, tmp_path, tmp_path, repository / "release")
    existing = tmp_path / "accepted"
    existing.mkdir()
    sentinel = existing / "manifest.json"
    sentinel.write_bytes(b"accepted immutable evidence")
    with pytest.raises(ValueError, match="already exists"):
        release.build_release(tmp_path, tmp_path, tmp_path, existing)
    assert sentinel.read_bytes() == b"accepted immutable evidence"


def test_release_is_authenticated_readonly_and_explicitly_interim(
    tmp_path: Path, release: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    experiment = tmp_path / "experiment"
    _experiment(experiment)
    test_stream, baseline_stream = io.StringIO(), io.StringIO()
    test_writer, baseline_writer = csv.writer(test_stream), csv.writer(baseline_stream)
    test_writer.writerow(["SMILES", "Molecule_Name"])
    baseline_writer.writerow(["SMILES", "Molecule_Name", *release.DIRECT_COLUMNS])
    for i in range(750):
        identity = ["CCO", f"fixture-{i}"]
        test_writer.writerow(identity)
        baseline_writer.writerow([*identity, *([3 + i / 750] * 4)])
    test, baseline = tmp_path / "test.csv", tmp_path / "baseline.csv"
    test.write_bytes(test_stream.getvalue().encode())
    baseline.write_bytes(baseline_stream.getvalue().encode())
    before = baseline.read_bytes()
    monkeypatch.setattr(
        release, "TEST_SHA256", hashlib.sha256(test.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(release, "BASELINE_SHA256", hashlib.sha256(before).hexdigest())
    monkeypatch.setattr(
        release, "refresh", lambda: {"scope": "synthetic public refresh"}
    )
    output = tmp_path / "accepted"
    manifest = release.build_release(experiment, test, baseline, output)
    assert manifest["interim_challenger"] is True
    assert manifest["final_recommendation"] is False
    assert manifest["calibration_development_molecules"] == 2
    assert manifest["validation"]["rows"] == 750
    assert baseline.read_bytes() == before
    assert (
        hashlib.sha256((output / "submission.csv").read_bytes()).hexdigest()
        == manifest["output_hashes"]["submission.csv"]
    )
    assert output.stat().st_mode & 0o222 == 0
    for name in ("submission.csv", "manifest.json"):
        assert (output / name).stat().st_mode & 0o222 == 0
    assert not list(output.glob("*.partial"))

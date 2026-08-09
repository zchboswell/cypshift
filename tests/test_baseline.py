from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from cypshift.audit import run_audit
from cypshift.baseline import BaselineError, predict_baseline, train_baseline
from cypshift.cli import main

FIXTURE = Path(__file__).parents[1] / "examples" / "synthetic"


def audited_fixture(root: Path) -> Path:
    output = root / "run"
    run_audit(FIXTURE / "molecules.csv", FIXTURE / "measurements.csv", output)
    return output


def test_fixture_split_is_deterministic_and_duplicate_safe(tmp_path: Path) -> None:
    first = audited_fixture(tmp_path / "first")
    second = audited_fixture(tmp_path / "second")

    first_result = train_baseline(first, first)
    second_result = train_baseline(second, second)

    assert first_result.model_path.read_bytes() == second_result.model_path.read_bytes()
    assert first_result.split_path.read_bytes() == second_result.split_path.read_bytes()
    with first_result.split_path.open(encoding="utf-8", newline="") as file:
        partitions = {
            row["molecule_id"]: row["partition"] for row in csv.DictReader(file)
        }
    assert partitions["syn-001"] == partitions["syn-002"]
    assert partitions["syn-006"] == "excluded"
    assert {"train", "validation", "excluded"} == set(partitions.values())


def test_model_uses_only_uncensored_training_measurements(tmp_path: Path) -> None:
    run = audited_fixture(tmp_path)

    result = train_baseline(run, run)

    assert result.model["method"] == "endpoint_context_median"
    assert result.model["fit_summary"] == {
        "contexts": 3,
        "measurements_not_used": 8,
        "measurements_used": 3,
    }
    assert result.model["resolved_configuration"]["split_scope"] == (
        "synthetic_fixture_pipeline_test_only"
    )


def test_prediction_artifacts_and_manifest_are_reproducible(tmp_path: Path) -> None:
    first = audited_fixture(tmp_path / "first")
    second = audited_fixture(tmp_path / "second")
    train_baseline(first, first)
    train_baseline(second, second)

    first_result = predict_baseline(
        first, first / "model.json", first / "split.csv", first
    )
    predict_baseline(
        second, second / "model.json", second / "split.csv", second
    )

    assert first_result.prediction_count == 21
    for name in ("predictions.csv", "prediction_cards.jsonl", "run_manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()

    manifest = json.loads(first_result.manifest_path.read_text(encoding="utf-8"))
    prediction_hash = hashlib.sha256(
        first_result.predictions_path.read_bytes()
    ).hexdigest()
    assert manifest["output_hashes"]["predictions.csv"] == prediction_hash
    assert manifest["resolved_configuration"]["llm_adjudication_used"] is False
    assert manifest["summary"] == {
        "contexts": 3,
        "molecules": 7,
        "predictions": 21,
        "quarantined_molecules_excluded": 1,
    }


def test_train_and_predict_refuse_overwrite(tmp_path: Path) -> None:
    run = audited_fixture(tmp_path)
    train_baseline(run, run)

    with pytest.raises(BaselineError, match="refusing to overwrite"):
        train_baseline(run, run)

    predict_baseline(run, run / "model.json", run / "split.csv", run)
    with pytest.raises(BaselineError, match="refusing to overwrite"):
        predict_baseline(run, run / "model.json", run / "split.csv", run)


def test_predict_rejects_split_not_bound_to_model(tmp_path: Path) -> None:
    run = audited_fixture(tmp_path)
    train_baseline(run, run)
    split_path = run / "split.csv"
    split_path.write_text(
        split_path.read_text(encoding="utf-8").replace(
            ",validation,", ",train,", 1
        ),
        encoding="utf-8",
    )

    with pytest.raises(BaselineError, match="split.csv hash"):
        predict_baseline(run, run / "model.json", split_path, run)


def test_train_and_predict_cli_smoke(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = audited_fixture(tmp_path)

    train_status = main(["train", "--data", str(run), "--out", str(run)])
    train_message = capsys.readouterr().out
    predict_status = main(
        [
            "predict",
            "--data",
            str(run),
            "--model",
            str(run / "model.json"),
            "--out",
            str(run),
        ]
    )
    predict_message = capsys.readouterr().out

    assert train_status == 0
    assert "3 endpoint contexts" in train_message
    assert predict_status == 0
    assert "21 predictions" in predict_message

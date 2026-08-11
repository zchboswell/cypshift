from __future__ import annotations

from pathlib import Path

import pytest

from cypshift.audit import run_audit
from cypshift.baseline import predict_baseline, train_baseline
from cypshift.cli import main
from cypshift.report import ReportError, generate_report, render_report

FIXTURE = Path(__file__).parents[1] / "examples" / "synthetic"


def completed_run(root: Path) -> Path:
    run = root / "run"
    run_audit(FIXTURE / "molecules.csv", FIXTURE / "measurements.csv", run)
    train_baseline(run, run)
    predict_baseline(run, run / "model.json", run / "split.csv", run)
    return run


def test_report_is_deterministic_and_states_limitations(tmp_path: Path) -> None:
    first = completed_run(tmp_path / "first")
    second = completed_run(tmp_path / "second")

    first_report = generate_report(first, first)
    second_report = generate_report(second, second)

    assert first_report.read_bytes() == second_report.read_bytes()
    content = first_report.read_text(encoding="utf-8")
    assert "CYP prediction run report" in content
    assert "not evidence of biological performance" in content
    assert "endpoint_context_median" in content
    assert "no_uncensored_numeric_training_measurement" in content
    assert "Unsupported model contexts" in content
    assert "All listed artifacts were hash-verified" in content
    assert "The endpoint-context median is not a competitive model" in content


def test_report_refuses_stale_or_modified_artifacts(tmp_path: Path) -> None:
    run = completed_run(tmp_path)
    predictions = run / "predictions.csv"
    predictions.write_text(
        predictions.read_text(encoding="utf-8") + "modified\n",
        encoding="utf-8",
    )

    with pytest.raises(ReportError, match="artifact hash mismatch"):
        generate_report(run, run)


def test_report_refuses_overwrite(tmp_path: Path) -> None:
    run = completed_run(tmp_path)
    generate_report(run, run)

    with pytest.raises(ReportError, match="refusing to overwrite"):
        generate_report(run, run)


def test_report_escapes_untrusted_artifact_text() -> None:
    audit = {
        "summary": {"warning_counts": {"<script>": 1}},
        "issues": [
            {
                "molecule_id": "<script>alert(1)</script>",
                "status": "quarantined",
                "warnings": ["invalid_structure"],
            }
        ],
        "assay_context_counts": [],
    }
    model = {
        "method": "median",
        "fit_summary": {},
        "unsupported_contexts": [],
    }
    manifest = {
        "resolved_configuration": {},
        "summary": {},
        "software": {},
        "input_hashes": {},
        "output_hashes": {},
    }

    content = render_report(audit, model, manifest)

    assert "<script>alert(1)</script>" not in content
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in content


def test_report_cli_and_four_command_contract(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = completed_run(tmp_path)

    status = main(["report", "--run", str(run), "--out", str(run)])

    assert status == 0
    assert f"Report complete: {run / 'report.html'}" in capsys.readouterr().out

    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    help_text = capsys.readouterr().out
    for command in ("audit", "train", "predict", "report"):
        assert command in help_text

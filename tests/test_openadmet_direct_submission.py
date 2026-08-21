"""Synthetic-only tests for the pre-TRACE fixed-MapLight deployment."""

from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT / "benchmarks/openadmet_cyp_2026/direct_maplight_deployment_contract.json"
)
RUNNER = ROOT / "scripts/run_openadmet_direct_submission.py"
VALIDATOR = ROOT / "scripts/validate_openadmet_direct_submission.py"
EXPECTED_CONTRACT_SHA256 = (
    "918fc1358e3394f32cd21b2f57b283f584e97242068fa0dc60448babc3963960"
)


def _module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _module(RUNNER, "test_direct_maplight_runner")
validator = _module(VALIDATOR, "test_direct_submission_validator")
helper = _module(
    ROOT / "research/maplight-fixed/r3b_cell_io.py",
    "test_direct_maplight_runtime_helper",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _contract() -> dict[str, Any]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _write_npy(path: Path, array: np.ndarray[Any, Any]) -> str:
    with path.open("wb") as handle:
        np.lib.format.write_array(handle, array, version=(1, 0), allow_pickle=False)
    return _sha(path.read_bytes())


def _feature_root(root: Path, contract: dict[str, Any], molecules: int) -> None:
    root.mkdir()
    rows = []
    for index in range(molecules):
        molecule = f"TRAIN-{index:03d}"
        smiles = "C" * (index % 3 + 1)
        rows.append(
            {
                "molecule_id": molecule,
                "raw_structure_sha256": _sha(smiles.encode()),
                "standardized_structure_hash": _sha(smiles.encode()),
                "similarity_component_hash": _sha(f"component-{index}".encode()),
            }
        )
    rows_raw = helper._csv_bytes(runner.FEATURE_ROW_COLUMNS, rows)
    (root / "feature_rows.csv").write_bytes(rows_raw)
    specifications = {
        "morgan_binary": (4096, np.dtype("uint8")),
        "maplight_morgan_count": (1024, np.dtype("int8")),
        "maplight_avalon_count": (1024, np.dtype("int8")),
        "maplight_erg": (315, np.dtype("<f8")),
        "maplight_rdkit_descriptors": (200, np.dtype("<f8")),
    }
    arrays: dict[str, dict[str, object]] = {}
    for name, (width, dtype) in specifications.items():
        values = np.zeros((molecules, width), dtype=dtype)
        if name == "maplight_morgan_count":
            values[:, 0] = np.arange(molecules, dtype=dtype)
        digest = _write_npy(root / f"{name}.npy", values)
        arrays[name] = {
            "path": f"{name}.npy",
            "shape": [molecules, width],
            "dtype": helper.FEATURE_DTYPE_STR[name],
            "npy_version": "1.0",
            "c_contiguous": True,
            "npy_sha256": digest,
        }
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3a_feature_manifest.v1",
        "rows": {
            "path": "feature_rows.csv",
            "columns": list(runner.FEATURE_ROW_COLUMNS),
            "rows": molecules,
            "sha256": _sha(rows_raw),
        },
        "arrays": arrays,
    }
    manifest_raw = helper._json_bytes(manifest)
    (root / "feature_manifest.json").write_bytes(manifest_raw)
    contract["features"]["training_root"].update(
        {
            "manifest_sha256": _sha(manifest_raw),
            "feature_rows_sha256": _sha(rows_raw),
            "rows": molecules,
        }
    )
    helper._readonly_tree(root)


def _observations(path: Path, contract: dict[str, Any], molecules: int) -> None:
    rows: list[dict[str, str]] = []
    source_sha = "a" * 64
    contract["training"]["source_sha256"] = source_sha
    contract["training"]["observation_rows"] = molecules * 4
    contract["training"]["eligible_points"] = {
        endpoint: molecules for endpoint in runner.ENDPOINTS
    }
    for index in range(molecules):
        molecule = f"TRAIN-{index:03d}"
        smiles = "C" * (index % 3 + 1)
        raw_hash = _sha(smiles.encode())
        for endpoint_index, endpoint in enumerate(runner.ENDPOINTS):
            point = format(4.0 + endpoint_index + index / 10, ".17g")
            row = dict.fromkeys(contract["training"]["observation_columns"], "")
            row.update(
                {
                    "observation_id": _sha(f"{molecule}|{endpoint}".encode()),
                    "molecule_id": molecule,
                    "source_row_id": f"fixture:{index + 2}",
                    "source_file": contract["training"]["source_file"],
                    "source_row": str(index + 2),
                    "source_sha256": source_sha,
                    "endpoint": endpoint,
                    "raw_smiles": smiles,
                    "raw_point": point,
                    "point": point,
                    "raw_structure_sha256": raw_hash,
                    "value_state": "partial",
                    "point_eligible": "true",
                    "anchor_eligible": "false",
                }
            )
            rows.append(row)
    path.write_bytes(
        helper._csv_bytes(contract["training"]["observation_columns"], rows[::-1])
    )


def _test_csv(path: Path, contract: dict[str, Any]) -> bytes:
    rows = [
        {"Molecule_Name": f"TEST-{index:04d}", "SMILES": "N" * (index % 3 + 1)}
        for index in range(750)
    ]
    raw = helper._csv_bytes(contract["test"]["columns"], rows)
    contract["test"]["source_sha256"] = _sha(raw)
    path.write_bytes(raw)
    return raw


class _Model:
    def __init__(self, fits: list[int]) -> None:
        self._fits = fits
        self._mean = 0.0

    def fit(self, X: np.ndarray[Any, Any], y: np.ndarray[Any, Any]) -> None:
        assert X.shape[0] == len(y)
        assert np.array_equal(X[:, 0], np.arange(len(y)))
        self._fits.append(len(y))
        self._mean = float(np.mean(y))

    def predict(self, X: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
        return self._mean + np.arange(len(X), dtype=np.float64) / 10000

    def get_all_params(self) -> dict[str, object]:
        return {"synthetic": True}


def _fake_feature_process(
    seen_headers: list[list[str]], helper_module: ModuleType
) -> runner.FeatureProcess:
    def build(
        projection: Path,
        output: Path,
        contract: dict[str, Any],
        contract_sha: str,
    ) -> None:
        with (projection / "test_chemistry.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            reader = csv.reader(handle)
            header = next(reader)
            assert len(list(reader)) == 750
        seen_headers.append(header)
        assert header == list(runner.TEST_CHEMISTRY_COLUMNS)
        assert not any("target" in name or "CYP" in name for name in header)
        output.mkdir()
        matrix = np.zeros((750, 2563), dtype="<f8")
        matrix[:, 0] = np.arange(750)
        digest = _write_npy(output / "maplight_fixed.npy", matrix)
        manifest = {
            "schema_version": "cypshift.openadmet_cyp_2026.direct_test_features.v1",
            "contract_sha256": contract_sha,
            "projection_manifest_sha256": _sha(
                (projection / "manifest.json").read_bytes()
            ),
            "feature_kernel_sha256": contract["features"]["kernel"]["sha256"],
            "matrix_sha256": digest,
            "shape": [750, 2563],
            "dtype": "<f8",
            "accounting": {
                "raw_smiles": 750,
                "feature_blocks": 4,
                "targets": 0,
                "fits": 0,
                "relationships": 0,
            },
        }
        (output / "manifest.json").write_bytes(helper_module._json_bytes(manifest))
        helper_module._readonly_tree(output)

    return build


def _fixture(tmp_path: Path) -> tuple[dict[str, Any], Path, Path, Path]:
    contract = copy.deepcopy(_contract())
    observations = tmp_path / "direct_observations.csv"
    test = tmp_path / "test.csv"
    features = tmp_path / "features"
    _feature_root(features, contract, 8)
    _observations(observations, contract, 8)
    _test_csv(test, contract)
    contract["parents"]["oracle_parameter_record"]["resolved_parameter_sha256"] = _sha(
        helper._json_bytes({"synthetic": True})
    )
    return contract, observations, features, test


def _rehearsals(
    tmp_path: Path,
) -> tuple[dict[str, Any], Path, dict[str, str], list[Path]]:
    contract, observations, features, test = _fixture(tmp_path)
    contract["submission"]["accepted_path"] = str(
        tmp_path / "accepted" / "submission.csv"
    )
    runtime = {"synthetic": "true"}
    outputs = [tmp_path / "run-a", tmp_path / "run-b"]
    fits: list[int] = []
    for output in outputs:
        runner.run_submission(
            direct_observations=observations,
            training_feature_root=features,
            test_csv=test,
            output_root=output,
            contract=contract,
            contract_sha256="b" * 64,
            runtime=runtime,
            helper=helper,
            feature_process=_fake_feature_process([], helper),
            model_factory=lambda _arguments: _Model(fits),
            production=False,
        )
    return contract, test, runtime, outputs


def test_contract_freezes_only_the_validated_global_reference() -> None:
    contract = _contract()
    assert _sha(CONTRACT.read_bytes()) == EXPECTED_CONTRACT_SHA256
    source = json.loads(
        (ROOT / contract["parents"]["source_receipts"]["path"]).read_text()
    )
    dataset = source["sources"]["dataset"]
    files = {item["path"]: item for item in dataset["files"]}
    assert (
        dataset["revision"]
        == contract["parents"]["source_receipts"]["dataset_revision"]
    )
    assert (
        files[contract["training"]["source_file"]]["sha256"]
        == contract["training"]["source_sha256"]
    )
    assert (
        files[contract["test"]["source_file"]]["sha256"]
        == contract["test"]["source_sha256"]
    )
    submission = json.loads(
        (ROOT / contract["parents"]["submission_contract"]["path"]).read_text()
    )
    assert (
        submission["direct_inhibition"]["required_columns_ordered"]
        == contract["submission"]["columns"]
    )
    global_contract = json.loads(
        (ROOT / contract["parents"]["global_experiment_contract"]["path"]).read_text()
    )
    assert (
        global_contract["inputs"]["direct_observations"]["sha256"]
        == contract["training"]["observations_sha256"]
    )
    global_system = next(
        item
        for item in global_contract["systems"]["systems"]
        if item["id"] == "TRACE-G0-MAPL-FIXED"
    )
    assert (
        global_system["constructor_arguments"]
        == contract["model"]["constructor_arguments"]
    )
    runner_contract = json.loads(
        (ROOT / contract["parents"]["global_runner_contract"]["path"]).read_text()
    )
    accepted = runner_contract["accepted_r3a_feature_root"]
    assert (
        accepted["manifest_sha256"]
        == contract["features"]["training_root"]["manifest_sha256"]
    )
    oracle = json.loads(
        (ROOT / contract["parents"]["oracle_parameter_record"]["path"]).read_text()
    )
    assert (
        oracle["global_model"]["resolved_parameter_sha256"]
        == contract["parents"]["oracle_parameter_record"]["resolved_parameter_sha256"]
    )
    assert contract["training"]["eligible_points"] == {
        "CYP1A2": 1412,
        "CYP2C9": 1285,
        "CYP2D6": 1493,
        "CYP3A4": 2335,
    }
    assert sum(contract["training"]["eligible_points"].values()) == 6525
    assert [block[1] for block in contract["features"]["ordered_blocks"]] == [
        1024,
        1024,
        315,
        200,
    ]
    assert contract["model"]["constructor_arguments"] == helper.CATBOOST_ARGS
    assert contract["model"]["fits"] == 4
    assert contract["submission"]["rows"] == 750
    assert contract["submission"]["finite_predictions"] == 3000
    assert contract["submission"]["accepted_path"] == (
        "/home/zbos/cypshift-private/openadmet-2026/submissions/"
        "direct-maplight-v1/accepted/submission.csv"
    )
    assert contract["submission"]["terminal_files"] == [
        "submission.csv",
        "manifest.json",
    ]
    assert "two distinct" in contract["submission"]["two_root_rule"]
    assert "no-replace acceptance command" in contract["submission"]["acceptance_rule"]
    assert contract["model"]["serialized_models"] == 0
    assert contract["accounting"]["official_metric_calls"] == 0
    assert contract["accounting"]["transductive_operations"] == 0
    assert (
        _sha((ROOT / contract["features"]["kernel"]["path"]).read_bytes())
        == contract["features"]["kernel"]["sha256"]
    )
    assert _sha(RUNNER.read_bytes()) == contract["implementation"]["runner_sha256"]
    assert (
        _sha(VALIDATOR.read_bytes()) == contract["implementation"]["validator_sha256"]
    )
    for receipt in contract["parents"].values():
        assert _sha((ROOT / receipt["path"]).read_bytes()) == receipt["sha256"]


def test_synthetic_two_root_run_is_exact_and_feature_worker_is_label_blind(
    tmp_path: Path,
) -> None:
    contract, observations, features, test = _fixture(tmp_path)
    accepted = tmp_path / "accepted"
    contract["submission"]["accepted_path"] = str(accepted / "submission.csv")
    runtime = {"synthetic": "true"}
    fits: list[int] = []
    headers: list[list[str]] = []
    factory = lambda _arguments: _Model(fits)  # noqa: E731
    process = _fake_feature_process(headers, helper)
    outputs = [tmp_path / "run-a", tmp_path / "run-b"]
    for output in outputs:
        result = runner.run_submission(
            direct_observations=observations,
            training_feature_root=features,
            test_csv=test,
            output_root=output,
            contract=contract,
            contract_sha256="b" * 64,
            runtime=runtime,
            helper=helper,
            feature_process=process,
            model_factory=factory,
            production=False,
        )
        assert result.output_root == output
        assert {path.name for path in output.iterdir()} == {
            "manifest.json",
            "submission.csv",
        }
        assert not output.stat().st_mode & 0o222
        assert not any(path.stat().st_mode & 0o222 for path in output.iterdir())
    assert fits == [8] * 8
    assert headers == [list(runner.TEST_CHEMISTRY_COLUMNS)] * 2
    for name in ("manifest.json", "submission.csv"):
        assert (outputs[0] / name).read_bytes() == (outputs[1] / name).read_bytes()
    acceptance = runner.accept_rehearsals(
        first_root=outputs[0],
        second_root=outputs[1],
        test_csv=test,
        contract=contract,
        contract_sha256="b" * 64,
        runtime=runtime,
        helper=helper,
    )
    assert acceptance.accepted_root == accepted
    assert {path.name for path in accepted.iterdir()} == {
        "manifest.json",
        "submission.csv",
    }
    assert not accepted.stat().st_mode & 0o222
    for name in ("manifest.json", "submission.csv"):
        assert (accepted / name).read_bytes() == (outputs[0] / name).read_bytes()
    assert not list(tmp_path.glob(".direct-maplight-*"))
    result = validator.validate_submission_bytes(
        test.read_bytes(),
        (outputs[0] / "submission.csv").read_bytes(),
        contract,
        verify_test_receipt=False,
    )
    assert (result.rows, result.finite_predictions) == (750, 3000)
    assert not list(outputs[0].glob("*.cbm"))


def test_production_run_cannot_publish_one_root_as_accepted(tmp_path: Path) -> None:
    contract = _contract()
    accepted = tmp_path / "accepted"
    contract["submission"]["accepted_path"] = str(accepted / "submission.csv")
    with pytest.raises(
        runner.DirectDeploymentError,
        match="accepted destination requires two-root acceptance",
    ):
        runner.run_submission(
            direct_observations=tmp_path / "missing-observations.csv",
            training_feature_root=tmp_path / "missing-features",
            test_csv=tmp_path / "missing-test.csv",
            output_root=accepted,
            contract=contract,
            contract_sha256="b" * 64,
            runtime={},
            helper=helper,
            production=True,
        )


def test_acceptance_rejects_one_root_presented_twice(tmp_path: Path) -> None:
    contract, test, runtime, outputs = _rehearsals(tmp_path)
    with pytest.raises(
        runner.DirectDeploymentError, match="two distinct rehearsal roots"
    ):
        runner.accept_rehearsals(
            first_root=outputs[0],
            second_root=outputs[0],
            test_csv=test,
            contract=contract,
            contract_sha256="b" * 64,
            runtime=runtime,
            helper=helper,
        )
    assert not (tmp_path / "accepted").exists()


def test_acceptance_rejects_individually_valid_byte_mismatch(tmp_path: Path) -> None:
    contract, test, runtime, outputs = _rehearsals(tmp_path)
    changed = outputs[1]
    changed.chmod(0o755)
    for path in changed.iterdir():
        path.chmod(0o644)
    submission_rows = runner._rows(
        (changed / "submission.csv").read_bytes(),
        contract["submission"]["columns"],
        "fixture submission",
    )
    prediction = contract["submission"]["columns"][2]
    submission_rows[0][prediction] = format(
        float(submission_rows[0][prediction]) + 0.25, ".17g"
    )
    submission = helper._csv_bytes(contract["submission"]["columns"], submission_rows)
    manifest = json.loads((changed / "manifest.json").read_text())
    manifest["submission"]["sha256"] = _sha(submission)
    (changed / "submission.csv").write_bytes(submission)
    (changed / "manifest.json").write_bytes(helper._json_bytes(manifest))
    helper._readonly_tree(changed)
    with pytest.raises(runner.DirectDeploymentError, match="not byte-identical"):
        runner.accept_rehearsals(
            first_root=outputs[0],
            second_root=outputs[1],
            test_csv=test,
            contract=contract,
            contract_sha256="b" * 64,
            runtime=runtime,
            helper=helper,
        )
    assert not (tmp_path / "accepted").exists()


def test_acceptance_never_replaces_existing_destination(tmp_path: Path) -> None:
    contract, test, runtime, outputs = _rehearsals(tmp_path)
    accepted = tmp_path / "accepted"
    accepted.mkdir()
    sentinel = accepted / "submission.csv"
    sentinel.write_bytes(b"do-not-replace\n")
    with pytest.raises(
        runner.DirectDeploymentError, match="accepted destination already exists"
    ):
        runner.accept_rehearsals(
            first_root=outputs[0],
            second_root=outputs[1],
            test_csv=test,
            contract=contract,
            contract_sha256="b" * 64,
            runtime=runtime,
            helper=helper,
        )
    assert sentinel.read_bytes() == b"do-not-replace\n"


def test_target_count_drift_stops_before_fit_or_private_output(tmp_path: Path) -> None:
    contract, observations, features, test = _fixture(tmp_path)
    rows = runner._rows(
        observations.read_bytes(),
        contract["training"]["observation_columns"],
        "fixture observations",
    )
    rows[0]["point_eligible"] = "false"
    rows[0]["point"] = ""
    observations.write_bytes(
        helper._csv_bytes(contract["training"]["observation_columns"], rows)
    )
    fits: list[int] = []
    with pytest.raises(runner.DirectDeploymentError, match="endpoint counts"):
        runner.run_submission(
            direct_observations=observations,
            training_feature_root=features,
            test_csv=test,
            output_root=tmp_path / "rejected",
            contract=contract,
            contract_sha256="b" * 64,
            runtime={"synthetic": "true"},
            helper=helper,
            feature_process=_fake_feature_process([], helper),
            model_factory=lambda _arguments: _Model(fits),
            production=False,
        )
    assert fits == []
    assert not (tmp_path / "rejected").exists()
    assert not list(tmp_path.glob(".direct-maplight-*"))


@pytest.mark.parametrize("defect", ["order", "nonfinite", "extra_column"])
def test_validator_rejects_submission_defects(tmp_path: Path, defect: str) -> None:
    contract = _contract()
    test = _test_csv(tmp_path / "test.csv", contract)
    columns = list(contract["submission"]["columns"])
    rows = []
    for index in range(750):
        row = {
            "SMILES": "N" * (index % 3 + 1),
            "Molecule_Name": f"TEST-{index:04d}",
            **{name: "5" for name in columns[2:]},
        }
        rows.append(row)
    if defect == "order":
        rows[0], rows[1] = rows[1], rows[0]
    elif defect == "nonfinite":
        rows[0][columns[2]] = "nan"
    else:
        columns.append("extra")
        for row in rows:
            row["extra"] = "no"
    submission = helper._csv_bytes(columns, rows)
    with pytest.raises(validator.DirectSubmissionError):
        validator.validate_submission_bytes(
            test, submission, contract, verify_test_receipt=False
        )

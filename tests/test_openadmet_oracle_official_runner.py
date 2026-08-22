from __future__ import annotations

import importlib.util
import json
import platform
import stat
import sys
from hashlib import sha256
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest
from test_openadmet_oracle_source import _fixture as source_fixture

from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS
from cypshift.openadmet_oracle_private_io import publish_readonly_tree
from cypshift.openadmet_oracle_runner import (
    OfficialRunInput,
    OfficialRunResult,
    run_official_oracle,
)
from cypshift.openadmet_oracle_terminal_io import (
    failure_source_bundle_sha256,
    terminal_source_bundle_sha256,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_openadmet_r5d.py"


def _load_entry() -> ModuleType:
    spec = importlib.util.spec_from_file_location("r5d_entry_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _compact(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def _parent(
    root: Path,
    manifest_name: str,
    schema: str,
    *,
    status: str | None = None,
    revision: str | None = None,
) -> tuple[str, dict[str, object]]:
    root.mkdir()
    manifest: dict[str, object] = {"schema_version": schema}
    if status is not None:
        manifest["status"] = status
    if revision is not None:
        manifest["source_revision"] = revision
    data = _compact(manifest)
    (root / manifest_name).write_bytes(data)
    return sha256(data).hexdigest(), manifest


def _fixture(tmp_path: Path) -> tuple[Path, dict[str, object], Path]:
    revision = "8" * 40
    roots = {name: tmp_path / name for name in ("r2b", "r3a", "r3c", "r4")}
    receipts: dict[str, str] = {}
    receipts["r2b"], _ = _parent(
        roots["r2b"],
        "manifest.json",
        "cypshift.openadmet_cyp_2026.validation_artifacts.v1",
        revision=revision,
    )
    receipts["r3a"], _ = _parent(
        roots["r3a"],
        "feature_manifest.json",
        "cypshift.openadmet_cyp_2026.r3a_feature_manifest.v1",
    )
    receipts["r3c"], _ = _parent(
        roots["r3c"],
        "manifest.json",
        "cypshift.openadmet_cyp_2026.r3b_terminal_manifest.v1",
        status="GLOBAL_EXPERT_FROZEN",
    )
    receipts["r4"], _ = _parent(
        roots["r4"],
        "manifest.json",
        "cypshift.openadmet_cyp_2026.transformation_coverage_manifest.v5",
        status="R4_TRANSFORMATION_COVERAGE_SUPPORTED",
    )
    source_data = b"opaque-official-source-bytes\n"
    source = roots["r2b"] / "direct_observations.csv"
    source.write_bytes(source_data)
    for root in roots.values():
        for path in root.iterdir():
            path.chmod(0o444)
        root.chmod(0o555)
    attempt_root = tmp_path / "official-attempt"
    contract = {
        "schema_version": (
            "cypshift.openadmet_cyp_2026.oracle_official_execution_contract.v1"
        ),
        "contract_id": "R5D-CYP3A4-OFFICIAL-ATTEMPT-V1",
        "resolved_oracle_contract_sha256": (
            "9143ecd1b24d1d9a97b1e5821e2b953f4cfffcec1cc39de3a8c49b81a4f58a50"
        ),
        "official_source_revision": revision,
        "parents": {
            "r2b": {
                "manifest_name": "manifest.json",
                "manifest_schema": (
                    "cypshift.openadmet_cyp_2026.validation_artifacts.v1"
                ),
                "manifest_sha256": receipts["r2b"],
            },
            "r3a": {
                "manifest_name": "feature_manifest.json",
                "manifest_schema": (
                    "cypshift.openadmet_cyp_2026.r3a_feature_manifest.v1"
                ),
                "manifest_sha256": receipts["r3a"],
            },
            "r3c": {
                "manifest_name": "manifest.json",
                "manifest_schema": (
                    "cypshift.openadmet_cyp_2026.r3b_terminal_manifest.v1"
                ),
                "manifest_sha256": receipts["r3c"],
                "required_status": "GLOBAL_EXPERT_FROZEN",
            },
            "r4": {
                "manifest_name": "manifest.json",
                "manifest_schema": (
                    "cypshift.openadmet_cyp_2026.transformation_coverage_manifest.v5"
                ),
                "manifest_sha256": receipts["r4"],
                "required_status": "R4_TRANSFORMATION_COVERAGE_SUPPORTED",
            },
        },
        "source_bundle": {
            "direct_observations.csv": {
                "parent": "r2b",
                "relative_path": "direct_observations.csv",
                "sha256": sha256(source_data).hexdigest(),
            }
        },
        "source_order": ["direct_observations.csv"],
        "execution": {
            "attempt_id": "r5d-cyp3a4-official-attempt-1",
            "artifact_root": str(attempt_root),
            "supported_topology": {"total_child_processes": 0, "verbs": {}},
            "underpowered_topology": {"total_child_processes": 0, "verbs": {}},
        },
        "attempt_envelope": {
            "fields": [
                "schema_version",
                "contract_sha256",
                "resolved_oracle_contract_sha256",
                "attempt_id",
                "status",
                "source_revision",
                "commit_oid",
                "config_sha256",
                "claim_sha256",
                "wrapper_source_sha256",
                "terminal_source_sha256",
                "failure_source_sha256",
                "parent_receipts",
                "source_receipts",
                "terminal_receipts",
                "processes",
                "operation_accounting",
                "authority",
            ]
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_bytes(_compact(contract))
    config: dict[str, object] = {
        "schema_version": "cypshift.openadmet_cyp_2026.r5d_official_run_config.v1",
        "r2b_root": str(roots["r2b"]),
        "r3a_root": str(roots["r3a"]),
        "r3c_root": str(roots["r3c"]),
        "r4_root": str(roots["r4"]),
        "commit_oid": "1" * 40,
        "expected_terminal_source_sha256": terminal_source_bundle_sha256(),
        "expected_failure_source_sha256": failure_source_bundle_sha256(),
    }
    return contract_path, config, attempt_root


def _failure_payload() -> bytes:
    return _compact(
        {
            "schema_version": "cypshift.openadmet_cyp_2026.r5c_oracle_failure.v1",
            "contract_sha256": (
                "9143ecd1b24d1d9a97b1e5821e2b953f4cfffcec1cc39de3a8c49b81a4f58a50"
            ),
            "stage": "projection",
            "failure_code": "PROCESS",
            "reason": "official synthetic boundary witness",
            "verified_receipts": {},
            "operation_accounting": dict.fromkeys(ACCOUNTING_FIELDS, 0),
            "authority": {
                "oracle_evidence": False,
                "inferred_anchor_contract": False,
                "model_fits": False,
                "predictions": False,
                "internal_metrics": False,
                "official_st_rae": False,
                "test_access": False,
                "tdi": False,
                "submission": False,
                "transduction": False,
            },
        }
    )


def _run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mutate_source: bool = False,
) -> tuple[ModuleType, Path, dict[str, object]]:
    module = _load_entry()
    contract_path, config, attempt_root = _fixture(tmp_path)
    if mutate_source:
        source = Path(cast(str, config["r2b_root"])) / "direct_observations.csv"
        source.chmod(0o644)
        source.write_bytes(b"drifted-source\n")
        source.chmod(0o444)
    config_path = tmp_path / "config.json"
    config_path.write_bytes(_compact(config))
    monkeypatch.setattr(module, "CONTRACT_PATH", contract_path)
    monkeypatch.setattr(
        module, "CONTRACT_SHA256", sha256(contract_path.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(module, "_runtime_gate", lambda: None)
    monkeypatch.setattr(module, "_checkout_gate", lambda _oid: None)

    def fake_run(value: object) -> OfficialRunResult:
        terminal = cast(Any, value).terminal_root
        publish_readonly_tree(terminal, {"failure.json": _failure_payload()})
        return OfficialRunResult(terminal, "R5_ORACLE_FAILED", ())

    monkeypatch.setattr(
        "cypshift.openadmet_oracle_runner.run_official_oracle", fake_run
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--config",
            str(config_path),
            "--expected-wrapper-sha256",
            sha256(SCRIPT.read_bytes()).hexdigest(),
        ],
    )
    return module, attempt_root, config


def test_official_wrapper_claims_once_and_publishes_bound_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module, attempt_root, _config = _run(tmp_path, monkeypatch)
    module.main()
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "R5_ORACLE_FAILED"
    assert set(path.name for path in attempt_root.iterdir()) == {
        "attempt_claim.json",
        "receipt",
        "terminal",
    }
    receipt = json.loads(
        (attempt_root / "receipt/official_attempt_receipt.json").read_text()
    )
    assert (
        receipt["claim_sha256"]
        == sha256((attempt_root / "attempt_claim.json").read_bytes()).hexdigest()
    )
    assert receipt["status"] == "R5_ORACLE_FAILED"
    assert receipt["processes"] == []
    assert not (attempt_root.stat().st_mode & stat.S_IWUSR)
    with pytest.raises(ValueError, match="already been consumed"):
        module.main()


def test_official_wrapper_binds_the_frozen_contract_bytes() -> None:
    module = _load_entry()
    contract = ROOT / (
        "benchmarks/openadmet_cyp_2026/oracle_official_execution_contract_v1.json"
    )
    assert module.CONTRACT_PATH == contract
    assert module.CONTRACT_SHA256 == sha256(contract.read_bytes()).hexdigest()


def test_official_wrapper_rejects_leaf_drift_before_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, attempt_root, _config = _run(tmp_path, monkeypatch, mutate_source=True)
    with pytest.raises(ValueError, match="source leaf receipt"):
        module.main()
    assert not attempt_root.exists()


@pytest.mark.skipif(
    sys.version_info[:3] != (3, 12, 3)
    or platform.system() != "Linux"
    or platform.machine() != "x86_64",
    reason="requires the exact R5D root runtime",
)
def test_official_runner_uses_the_accepted_underpowered_state_machine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_paths, source_receipts = source_fixture(tmp_path / "inputs")
    monkeypatch.setattr(
        "cypshift.openadmet_oracle_runner._validate_checkout", lambda _oid: None
    )
    monkeypatch.setattr(
        "cypshift.openadmet_oracle_runner._validate_runtime", lambda: None
    )
    result = run_official_oracle(
        OfficialRunInput(
            source_paths,
            source_receipts,
            tmp_path / "private",
            tmp_path / "terminal",
            "1" * 40,
            terminal_source_bundle_sha256(),
            failure_source_bundle_sha256(),
        )
    )
    assert result.status == "R5_ORACLE_UNDERPOWERED"
    assert [item.verb for item in result.processes] == [
        "source",
        "project",
        "support",
        "cleanup",
        "underpowered",
    ]
    assert all(item.pid > 0 and item.returncode == 0 for item in result.processes)

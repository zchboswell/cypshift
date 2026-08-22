from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_openadmet_oracle_source import _fixture

from cypshift.openadmet_oracle_source import compile_openadmet_oracle_source
from cypshift.openadmet_oracle_support import (
    OracleSupportError,
    SupportSourceInput,
    compile_support_evidence,
)
from cypshift.openadmet_oracle_terminal_receipts import (
    SupportEvidenceInput,
    publish_support_receipt,
)


def _source(tmp_path: Path) -> SupportSourceInput:
    paths, receipts = _fixture(tmp_path / "inputs")
    result = compile_openadmet_oracle_source(
        paths, tmp_path / "source", expected_receipts=receipts
    )
    expected = {
        name: record["sha256"] for name, record in result.output_receipts.items()
    }
    expected["manifest.json"] = result.manifest_sha256
    return SupportSourceInput(result.output_directory, expected)


def test_support_compiler_feeds_closed_underpowered_receipt(tmp_path: Path) -> None:
    source = _source(tmp_path)
    evidence_root = tmp_path / "evidence"
    evidence_sha = compile_support_evidence(source, evidence_root)
    evidence = json.loads((evidence_root / "evidence.json").read_text())
    assert len(evidence["primary_rows"]) == 1
    assert not evidence["control_local_rows"]
    receipt_root = tmp_path / "support"
    publish_support_receipt(
        receipt_root,
        evidence=SupportEvidenceInput(evidence_root, evidence_sha),
    )
    assert not evidence_root.exists()
    support = json.loads((receipt_root / "support.json").read_text())
    assert support["support_status"] == "UNDERPOWERED"
    assert support["operation_accounting"] == dict.fromkeys(
        support["operation_accounting"], 0
    )


def test_support_compiler_rejects_independent_receipt_poison(tmp_path: Path) -> None:
    source = _source(tmp_path)
    poisoned = dict(source.expected_receipts)
    poisoned["training_pairs.csv"] = "0" * 64
    with pytest.raises(OracleSupportError, match="source receipt differs"):
        compile_support_evidence(
            SupportSourceInput(source.root, poisoned), tmp_path / "evidence"
        )

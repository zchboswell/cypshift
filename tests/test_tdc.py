from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from cypshift.audit import run_audit
from cypshift.tdc import TDC_TASKS, TdcDataError, prepare_tdc_admet


def _member_bytes(task: str, partition: str) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer, fieldnames=("Drug_ID", "Drug", "Y"), lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(
        [
            {
                "Drug_ID": f"{task}-{partition}-negative",
                "Drug": " CCO ",
                "Y": "0",
            },
            {
                "Drug_ID": f"{task}-{partition}-positive",
                "Drug": "c1ccccc1",
                "Y": "1",
            },
        ]
    )
    return buffer.getvalue().encode()


def _archive(path: Path) -> tuple[str, dict[str, Any]]:
    contracts: dict[str, Any] = {}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for task in TDC_TASKS:
            contracts[task] = {}
            for partition in ("train_val", "test"):
                member_path = f"admet_group/{task}/{partition}.csv"
                content = _member_bytes(task, partition)
                archive.writestr(member_path, content)
                contracts[task][partition] = {
                    "path": member_path,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "rows": 2,
                    "negative": 1,
                    "positive": 1,
                }
    return hashlib.sha256(path.read_bytes()).hexdigest(), contracts


def test_tdc_adapter_preserves_official_partitions_and_context(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "admet_group.zip"
    archive_hash, contracts = _archive(archive)

    result = prepare_tdc_admet(
        archive,
        tmp_path / "adapter",
        expected_archive_sha256=archive_hash,
        task_contracts=contracts,
    )
    canonical = run_audit(
        result.molecules_path,
        result.measurements_path,
        tmp_path / "canonical",
    )

    with result.molecules_path.open(encoding="utf-8", newline="") as handle:
        molecule_rows = list(csv.DictReader(handle))
    with result.measurements_path.open(encoding="utf-8", newline="") as handle:
        measurement_rows = list(csv.DictReader(handle))
    with result.split_path.open(encoding="utf-8", newline="") as handle:
        split_rows = list(csv.DictReader(handle))
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert result.row_count == 12
    assert molecule_rows[0]["structure"] == " CCO "
    assert measurement_rows[0]["endpoint"] == "binary_inhibition_veith"
    assert measurement_rows[0]["nadph_condition"] == "not_reported"
    assert measurement_rows[0]["probe"] == "not_reported"
    assert measurement_rows[0]["readout"] == "binary_label"
    assert {row["partition"] for row in split_rows} == {"train_val", "test"}
    assert manifest["selection_policy"].endswith(
        "are ingested for alignment but are not scored by this adapter."
    )
    assert manifest["tasks"]["cyp2c9_veith"]["test"]["positive"] == 1
    assert canonical.report["summary"]["molecules_accepted"] == 12
    assert canonical.molecules[0].raw_structure == " CCO "


def test_tdc_adapter_rejects_archive_and_member_hash_mismatch(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "admet_group.zip"
    archive_hash, contracts = _archive(archive)

    with pytest.raises(TdcDataError, match="source hash mismatch"):
        prepare_tdc_admet(
            archive,
            tmp_path / "bad-archive",
            expected_archive_sha256="0" * 64,
            task_contracts=contracts,
        )

    contracts["cyp2c9_veith"]["test"]["sha256"] = "0" * 64
    with pytest.raises(TdcDataError, match="member hash mismatch"):
        prepare_tdc_admet(
            archive,
            tmp_path / "bad-member",
            expected_archive_sha256=archive_hash,
            task_contracts=contracts,
        )


def test_tdc_adapter_rejects_schema_label_count_and_overwrite(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "admet_group.zip"
    archive_hash, contracts = _archive(archive)

    contracts["cyp2d6_veith"]["train_val"]["positive"] = 2
    with pytest.raises(TdcDataError, match="label-count mismatch"):
        prepare_tdc_admet(
            archive,
            tmp_path / "bad-count",
            expected_archive_sha256=archive_hash,
            task_contracts=contracts,
        )

    output = tmp_path / "adapter"
    output.mkdir()
    with pytest.raises(TdcDataError, match="output path already exists"):
        prepare_tdc_admet(
            archive,
            output,
            expected_archive_sha256=archive_hash,
            task_contracts=contracts,
        )


def test_tdc_adapter_rejects_nonbinary_label(tmp_path: Path) -> None:
    archive = tmp_path / "admet_group.zip"
    archive_hash, contracts = _archive(archive)
    member_path = contracts["cyp3a4_veith"]["test"]["path"]
    bad_content = _member_bytes("cyp3a4_veith", "test").replace(b",1\n", b",2\n")
    replacement = tmp_path / "replacement.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(
        replacement, "w", compression=zipfile.ZIP_DEFLATED
    ) as target:
        for name in source.namelist():
            target.writestr(name, bad_content if name == member_path else source.read(name))
    contracts["cyp3a4_veith"]["test"]["sha256"] = hashlib.sha256(
        bad_content
    ).hexdigest()
    replacement_hash = hashlib.sha256(replacement.read_bytes()).hexdigest()

    with pytest.raises(TdcDataError, match="non-binary"):
        prepare_tdc_admet(
            replacement,
            tmp_path / "adapter",
            expected_archive_sha256=replacement_hash,
            task_contracts=contracts,
        )

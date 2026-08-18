from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from cypshift.openadmet_cyp import (
    OPENADMET_SOURCE_FILES,
    OpenADMETDataError,
    prepare_openadmet_cyp,
)

ROOT = Path(__file__).parents[1]
RECEIPTS = ROOT / "benchmarks" / "openadmet_cyp_2026" / "source_receipts.json"


def _fixture(tmp_path: Path, *, overlap: bool = False) -> dict[str, Any]:
    receipts = json.loads(RECEIPTS.read_text(encoding="utf-8"))
    receipts = copy.deepcopy(receipts)
    revision = "synthetic-openadmet-revision"
    receipts["sources"]["dataset"]["revision"] = revision
    root = tmp_path / "dataset"
    root.mkdir()
    specs = {
        OPENADMET_SOURCE_FILES[0]: [
            ["shared" if overlap else "test-1", "CCO"],
            ["test-2", "CCN"],
        ],
        OPENADMET_SOURCE_FILES[1]: [
            ["shared" if overlap else "train-1", "CCO" if overlap else "CCC"]
        ],
        OPENADMET_SOURCE_FILES[2]: [["train-2", "CNC"]],
        OPENADMET_SOURCE_FILES[3]: [["train-3", "COC"]],
        OPENADMET_SOURCE_FILES[4]: [
            ["train-4", "c1ccccc1"],
            ["train-4", "c1ccccc1"],
        ],
    }
    dataset_files = receipts["sources"]["dataset"]["files"]
    for entry in dataset_files:
        filename = entry["path"]
        header = entry["header"]
        rows = []
        for values in specs[filename]:
            row = [""] * len(header)
            row[:2] = values
            if filename == OPENADMET_SOURCE_FILES[2]:
                row[2:4] = ["False", "True"]
            if filename == OPENADMET_SOURCE_FILES[4]:
                row[2] = "batch-1"
                row[3] = "CYP3A4"
                row[4] = ""
                row[5] = "0.0001"
                row[6] = ""
            rows.append(row)
        path = root / filename
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(rows)
        data = path.read_bytes()
        entry.update(
            {
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "rows": len(rows),
            }
        )
    receipts_path = tmp_path / "source_receipts.json"
    receipts_path.write_text(json.dumps(receipts), encoding="utf-8")
    return {"root": root, "receipts": receipts_path, "revision": revision}


def _prepare(fixture: dict[str, Any], output: Path) -> Any:
    return prepare_openadmet_cyp(
        fixture["root"],
        output,
        source_revision=fixture["revision"],
        receipts_path=fixture["receipts"],
    )


def test_exact_pass_is_deterministic_and_lossless(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    first = _prepare(fixture, tmp_path / "first")
    second = _prepare(fixture, tmp_path / "second")

    for name in ("molecules_input.csv", "source_rows.csv", "manifest.json"):
        assert (first.manifest_path.parent / name).read_bytes() == (
            second.manifest_path.parent / name
        ).read_bytes()
    assert first.source_row_count == 7
    assert first.molecule_count == 6
    with first.source_rows_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["partition"] for row in rows] == [
        "test",
        "test",
        "train",
        "train",
        "train",
        "train",
        "train",
    ]
    assert rows[3]["source_values"]
    values = json.loads(rows[3]["source_values"])
    assert values["CYP2D6_is_TDI"] == "False"
    assert values["CYP3A4_is_TDI"] == "True"
    with first.molecules_path.open(encoding="utf-8", newline="") as handle:
        molecules = list(csv.DictReader(handle))
    assert [row["molecule_id"] for row in molecules] == [
        "test-1",
        "test-2",
        "train-1",
        "train-2",
        "train-3",
        "train-4",
    ]
    provenance = json.loads(molecules[-1]["provenance"])
    assert len(provenance["occurrences"]) == 2
    assert provenance["occurrences"][0]["source_row"] == 2


def test_output_refusal_and_no_partial_output(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    output = tmp_path / "output"
    _prepare(fixture, output)
    with pytest.raises(OpenADMETDataError, match="output path already exists"):
        _prepare(fixture, output)


@pytest.mark.parametrize("drift", ["hash", "header", "rows", "revision"])
def test_receipt_drift_fails_closed(tmp_path: Path, drift: str) -> None:
    fixture = _fixture(tmp_path)
    if drift == "revision":
        with pytest.raises(OpenADMETDataError, match="source revision mismatch"):
            prepare_openadmet_cyp(
                fixture["root"],
                tmp_path / "output",
                source_revision="wrong-revision",
                receipts_path=fixture["receipts"],
            )
        return
    filename = OPENADMET_SOURCE_FILES[1]
    path = fixture["root"] / filename
    data = path.read_bytes().replace(b"train-1", b"train-X")
    if drift == "header":
        data = data.replace(b"Molecule_Name", b"Wrong_Name", 1)
    if drift == "rows":
        header = next(
            item
            for item in json.loads(RECEIPTS.read_text(encoding="utf-8"))["sources"][
                "dataset"
            ]["files"]
            if item["path"] == filename
        )["header"]
        data += (
            ",".join(["train-extra", "CCC"] + [""] * (len(header) - 2)) + "\n"
        ).encode()
    path.write_bytes(data)
    receipts = json.loads(fixture["receipts"].read_text(encoding="utf-8"))
    entry = next(
        item
        for item in receipts["sources"]["dataset"]["files"]
        if item["path"] == filename
    )
    if drift != "hash":
        entry["sha256"] = hashlib.sha256(data).hexdigest()
        entry["size_bytes"] = len(data)
    fixture["receipts"].write_text(json.dumps(receipts), encoding="utf-8")
    pattern = {
        "hash": "SHA-256 mismatch",
        "header": "header mismatch",
        "rows": "row count mismatch",
    }[drift]
    with pytest.raises(OpenADMETDataError, match=pattern):
        _prepare(fixture, tmp_path / "output")


def test_conflicting_smiles_fail_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    filename = OPENADMET_SOURCE_FILES[2]
    path = fixture["root"] / filename
    data = path.read_text(encoding="utf-8").replace("train-2,CNC", "train-1,CNN")
    path.write_text(data, encoding="utf-8")
    receipts = json.loads(fixture["receipts"].read_text(encoding="utf-8"))
    entry = next(
        item
        for item in receipts["sources"]["dataset"]["files"]
        if item["path"] == filename
    )
    new_data = path.read_bytes()
    entry.update(
        {"sha256": hashlib.sha256(new_data).hexdigest(), "size_bytes": len(new_data)}
    )
    fixture["receipts"].write_text(json.dumps(receipts), encoding="utf-8")
    with pytest.raises(OpenADMETDataError, match="conflicting exact SMILES"):
        _prepare(fixture, tmp_path / "output")


def test_blinded_training_name_overlap_fails_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, overlap=True)
    with pytest.raises(OpenADMETDataError, match="overlap training"):
        _prepare(fixture, tmp_path / "output")

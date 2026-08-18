from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

CONTRACT_DIR = Path(__file__).parents[1] / "benchmarks" / "openadmet_cyp_2026"


def load(name: str) -> dict[str, object]:
    with (CONTRACT_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def test_contracts_are_json_and_internal_consistent() -> None:
    receipts, contract, submission = (
        load(name)
        for name in (
            "source_receipts.json",
            "challenge_contract.json",
            "submission_contract.json",
        )
    )
    assert set(receipts["status_values"]) == {
        "verified", "organizer_confirmed", "provisional", "unresolved", "not_applicable"
    }
    assert contract["source_receipts"].endswith("source_receipts.json")
    assert contract["public_submission"]["direct_columns"]["ordered"] == submission[
        "direct_inhibition"
    ]["required_columns_ordered"]
    assert set(contract["public_submission"]["tdi_columns"]["ordered"]) == set(
        submission["tdi"]["required_column_names"]
    )
    assert contract["public_submission"]["tdi_columns"]["order_status"].startswith(
        "unresolved"
    )
    assert contract["metrics"]["direct"]["implementation"] == "unresolved"
    assert contract["leaderboard_and_rules"]["transductive_test_test_permissions"][
        "status"
    ] == "unresolved"
    assert contract["validation_protocols"]["TDI_TRACE"]["status"] == "not_applicable"


def test_dataset_receipts_have_exact_csv_essentials() -> None:
    files = load("source_receipts.json")["sources"]["dataset"]["files"]
    assert {entry["path"] for entry in files} == {
        "cyp-challenge-TEST-BLINDED.csv",
        "cyp-challenge-TRAIN_Emax.csv",
        "cyp-challenge-TRAIN_TDI.csv",
        "cyp-challenge-TRAIN_inhibition.csv",
        "cyp-challenge-single-concentration-TRAIN.csv",
    }
    for entry in files:
        assert len(entry["sha256"]) == 64
        assert entry["size_bytes"] > 0 and entry["rows"] > 0
        assert entry["header"][:2] == ["Molecule_Name", "SMILES"]
        assert len(entry["header"]) == len(set(entry["header"]))


def test_submission_schema_is_exact_by_name_and_type() -> None:
    submission = load("submission_contract.json")
    assert submission["shared"]["rows"] == 750
    assert submission["direct_inhibition"]["required_columns_ordered"] == [
        "SMILES",
        "Molecule_Name",
        "CYP1A2_pIC50_direct_inhibition",
        "CYP2C9_pIC50_direct_inhibition",
        "CYP2D6_pIC50_direct_inhibition",
        "CYP3A4_pIC50_direct_inhibition",
    ]
    assert set(submission["tdi"]["required_column_names"]) == {
        "SMILES",
        "Molecule_Name",
        "CYP2D6_is_TDI",
        "CYP3A4_is_TDI",
    }
    assert submission["tdi"]["order_status"].startswith("unresolved")


def test_external_receipts_if_read_only_clones_are_available() -> None:
    sources = load("source_receipts.json")["sources"]
    roots = {
        name: Path(f"/tmp/cypshift-plan.IVtGAq/{name}")
        for name in ("dataset", "tutorial", "space")
    }
    if not all(root.is_dir() for root in roots.values()):
        pytest.skip("authoritative source clones are absent")
    for name, root in roots.items():
        revision = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], check=True,
            capture_output=True, text=True
        ).stdout.strip()
        assert revision == sources[name]["revision"]
        for entry in sources[name]["files"]:
            path, data = root / entry["path"], (root / entry["path"]).read_bytes()
            assert path.is_file() and len(data) == entry["size_bytes"]
            assert hashlib.sha256(data).hexdigest() == entry["sha256"]
            if path.suffix == ".csv":
                with path.open(newline="", encoding="utf-8") as handle:
                    rows = list(csv.reader(handle))
                assert rows[0] == entry["header"] and len(rows) - 1 == entry["rows"]

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parents[1]
CONTRACTS = ROOT / "benchmarks" / "openadmet_cyp_2026"
SCRIPT = ROOT / "scripts" / "check_openadmet_cyp_contract.py"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _fixture(tmp_path: Path) -> dict[str, Path]:
    contract_dir = tmp_path / "contracts"
    contract_dir.mkdir()
    receipts: dict[str, Any] = json.loads(
        (CONTRACTS / "source_receipts.json").read_text(encoding="utf-8")
    )
    roots: dict[str, Path] = {}
    source_files = {
        "dataset": ("sample.csv", b"a,b\n1,2\n3,4\n"),
        "tutorial": ("README.md", b"tutorial\n"),
        "space": ("README.md", b"space\n"),
    }
    for name, (relative, data) in source_files.items():
        root = tmp_path / name
        root.mkdir()
        _git(root, "init", "-q")
        _git(root, "config", "user.email", "test@example.invalid")
        _git(root, "config", "user.name", "Synthetic Test")
        (root / relative).write_bytes(data)
        _git(root, "add", relative)
        _git(root, "commit", "-qm", "fixture")
        roots[name] = root
        source = receipts["sources"][name]
        entry: dict[str, Any] = {
            "path": relative,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        if relative.endswith(".csv"):
            entry.update({"rows": 2, "header": ["a", "b"]})
        source["revision"] = _git(root, "rev-parse", "HEAD")
        source["files"] = [entry]
    blogs = {
        "announcement": tmp_path / "announcement.html",
        "launch_post": tmp_path / "launch.html",
    }
    for name, path in blogs.items():
        data = f"<{name}/>\n".encode()
        path.write_bytes(data)
        receipt = receipts["sources"][name]
        receipt["retrieved_size_bytes"] = len(data)
        receipt["retrieved_sha256"] = hashlib.sha256(data).hexdigest()
    challenge = json.loads(
        (CONTRACTS / "challenge_contract.json").read_text(encoding="utf-8")
    )
    submission = json.loads(
        (CONTRACTS / "submission_contract.json").read_text(encoding="utf-8")
    )
    for name, value in (
        ("source_receipts.json", receipts),
        ("challenge_contract.json", challenge),
        ("submission_contract.json", submission),
    ):
        (contract_dir / name).write_text(
            json.dumps(copy.deepcopy(value)), encoding="utf-8"
        )
    return {"contracts": contract_dir, **roots, **blogs}


def _run(fixture: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCRIPT),
        "--dataset-root",
        str(fixture["dataset"]),
        "--tutorial-root",
        str(fixture["tutorial"]),
        "--space-root",
        str(fixture["space"]),
        "--announcement-html",
        str(fixture["announcement"]),
        "--launch-post-html",
        str(fixture["launch_post"]),
        "--contract-dir",
        str(fixture["contracts"]),
    ]
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _result(run: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert len(run.stdout.splitlines()) == 1
    return json.loads(run.stdout)


def test_checker_passes_exact_synthetic_receipts(tmp_path: Path) -> None:
    run = _run(_fixture(tmp_path))
    assert run.returncode == 0
    result = _result(run)
    assert result["status"] == "pass"
    assert result["counts"]["errors"] == 0
    assert set(result["verified_revisions"]) == {"dataset", "tutorial", "space"}


@pytest.mark.parametrize(
    ("kind", "mutate", "needle"),
    [
        (
            "hash",
            lambda f: f["dataset"].joinpath("sample.csv").write_text("a,b\n1,9\n3,4\n"),
            "SHA-256 drift",
        ),
        (
            "header",
            lambda f: f["dataset"].joinpath("sample.csv").write_text("x,b\n1,2\n3,4\n"),
            "CSV header drift",
        ),
        (
            "rows",
            lambda f: (
                f["dataset"].joinpath("sample.csv").write_text("a,b\n1,2\n3,4\n5,6\n")
            ),
            "CSV row count drift",
        ),
        (
            "prose",
            lambda f: f["announcement"].write_bytes(b"changed\n"),
            "announcement_html SHA-256 drift",
        ),
    ],
)
def test_checker_fails_byte_or_csv_drift(
    tmp_path: Path, kind: str, mutate: Any, needle: str
) -> None:
    fixture = _fixture(tmp_path)
    mutate(fixture)
    run = _run(fixture)
    assert run.returncode == 1, kind
    assert any(needle in error for error in _result(run)["errors"])


def test_checker_fails_revision_drift(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    (fixture["dataset"] / "new.txt").write_text("drift\n", encoding="utf-8")
    _git(fixture["dataset"], "add", "new.txt")
    _git(fixture["dataset"], "commit", "-qm", "drift")
    run = _run(fixture)
    assert run.returncode == 1
    assert any("dataset revision drift" in error for error in _result(run)["errors"])


def test_checker_fails_internal_submission_mismatch(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    path = fixture["contracts"] / "submission_contract.json"
    submission = json.loads(path.read_text(encoding="utf-8"))
    submission["direct_inhibition"]["required_columns_ordered"][0] = "wrong"
    path.write_text(json.dumps(submission), encoding="utf-8")
    run = _run(fixture)
    assert run.returncode == 1
    assert (
        "internal contract mismatch: direct ordered columns" in _result(run)["errors"]
    )

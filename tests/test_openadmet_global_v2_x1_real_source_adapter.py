from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tarfile
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parents[1]
RESEARCH = ROOT / "research/external-transfer"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import global_v2_x1_acquisition_wrapper as wrapper  # noqa: E402
import global_v2_x1_compiler as compiler  # noqa: E402
import global_v2_x1_real_source_adapter as adapter  # noqa: E402
import run_global_v2_x1_official_shaped_synthetic as driver  # noqa: E402

from cypshift.openadmet_validation import (  # noqa: E402
    FOLD_COLUMNS,
    OBSERVATION_COLUMNS,
)


@pytest.fixture(scope="module")
def accepted_fixture(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    root = tmp_path_factory.mktemp("x1-real-adapter")
    terminals: list[Path] = []
    physical: list[dict[str, str]] = []
    sources: list[Path] = []
    for label, reverse in (("a", False), ("b", True)):
        source = root / f"source-{label}"
        source.mkdir()
        terminal = root / f"terminal-{label}"
        sources.append(source)
        terminals.append(terminal)
        physical.append(driver.run_one(source, terminal, reverse=reverse))
    yield {
        "root": root,
        "sources": sources,
        "terminals": terminals,
        "physical": physical,
    }
    compiler.cleanup(root)


def _mutable_r2b(source: Path, destination: Path) -> Path:
    shutil.copytree(source / "r2b", destination)
    compiler.make_writable(destination)
    return destination


def _refresh_receipt(root: Path, name: str) -> None:
    manifest_path = root / "manifest.json"
    manifest = compiler.read_json(manifest_path)
    manifest["outputs"][name]["sha256"] = compiler.sha256_path(root / name)
    manifest_path.write_bytes(compiler.json_bytes(manifest))
    compiler.seal_tree(root)


def _archive(path: Path, members: list[tarfile.TarInfo], payload: bytes = b"sqlite") -> str:
    with tarfile.open(path, "w:gz") as archive:
        for member in members:
            stream = io.BytesIO(payload) if member.isreg() else None
            archive.addfile(member, stream)
    digest = compiler.sha256_path(path)
    os.chmod(path, 0o444)
    return digest


def _regular_member(name: str, size: int = 6) -> tarfile.TarInfo:
    member = tarfile.TarInfo(name)
    member.size = size
    member.mode = 0o444
    return member


def test_official_shaped_fixture_has_exact_identity_projection_shape() -> None:
    direct = driver.direct_rows()
    folds = driver.group_fold_rows()
    assert len(direct) == 160
    assert len({row["molecule_id"] for row in direct}) == 40
    assert all(
        {row["endpoint"] for row in direct if row["molecule_id"] == molecule_id}
        == set(compiler.ENDPOINTS)
        for molecule_id in {row["molecule_id"] for row in direct}
    )
    assert len(folds) == 600
    assert len({row["similarity_component_hash"] for row in folds}) == 20


def test_two_physical_roots_have_identical_logical_and_terminal_bytes(
    accepted_fixture: Mapping[str, Any],
) -> None:
    physical = accepted_fixture["physical"]
    assert physical[0]["database_sha256"] != physical[1]["database_sha256"]
    assert physical[0]["r2b_manifest_sha256"] != physical[1]["r2b_manifest_sha256"]
    maps = [
        compiler.relative_byte_map(path) for path in accepted_fixture["terminals"]
    ]
    assert maps[0] == maps[1]
    manifest = compiler.read_json(accepted_fixture["terminals"][0] / "manifest.json")
    assert manifest["status"] == adapter.SYNTHETIC_STATUS
    assert manifest["projection"] == {
        "source_revision": driver.SOURCE_REVISION,
        "direct_observation_records_scanned": 160,
        "decoded_prefix_fields": 1280,
        "opaque_suffixes_discarded": 160,
        "challenge_molecules": 40,
        "challenge_components": 20,
        "confirmatory_molecules": 8,
        "confirmatory_components": 4,
        "target_values_parsed": 0,
        "target_values_retained": 0,
    }
    assert manifest["accounting"]["official_model_fits"] == 0
    assert manifest["accounting"]["official_predictions_generated"] == 0
    assert manifest["accounting"]["live_uploads"] == 0


def test_target_suffix_is_never_decoded_or_result_affecting(
    accepted_fixture: Mapping[str, Any], tmp_path: Path
) -> None:
    source = accepted_fixture["sources"][0]
    r2b = _mutable_r2b(source, tmp_path / "r2b")
    direct_path = r2b / "direct_observations.csv"
    data = direct_path.read_bytes()
    marker = b",5.01,"
    assert marker in data
    direct_path.write_bytes(data.replace(marker, b",\xff,", 1))
    _refresh_receipt(r2b, "direct_observations.csv")
    terminal = adapter.run_replay(
        database_path=source / "extracted/chembl_37.db",
        challenge_root=r2b,
        replay_root=tmp_path / "terminal",
        synthetic=True,
    )
    assert compiler.relative_byte_map(terminal) == compiler.relative_byte_map(
        accepted_fixture["terminals"][0]
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate-endpoint", "duplicate endpoint"),
        ("raw-drift", "identity drift"),
        ("source-row", "source-row identity"),
    ],
)
def test_direct_prefix_identity_adversaries_fail_closed(
    accepted_fixture: Mapping[str, Any],
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    source = accepted_fixture["sources"][0]
    r2b = _mutable_r2b(source, tmp_path / mutation)
    rows = driver.direct_rows()
    selected = [row for row in rows if row["molecule_id"] == rows[0]["molecule_id"]]
    assert len(selected) == 4
    if mutation == "duplicate-endpoint":
        selected[-1]["endpoint"] = selected[0]["endpoint"]
    elif mutation == "raw-drift":
        selected[-1]["raw_smiles"] = "CC"
    else:
        selected[-1]["source_row_id"] = "wrong:1"
    (r2b / "direct_observations.csv").write_bytes(
        compiler.csv_bytes(OBSERVATION_COLUMNS, rows)
    )
    _refresh_receipt(r2b, "direct_observations.csv")
    with pytest.raises(adapter.X1AdapterError, match=message):
        adapter.challenge_inputs(r2b, synthetic=True)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("seed", "fold seed differs"),
        ("duplicate", "duplicate molecule/repeat/outer"),
        ("outer-cross", "component crosses an outer boundary"),
        ("inner-cross", "component crosses an inner boundary"),
    ],
)
def test_fold_identity_and_family_adversaries_fail_closed(
    accepted_fixture: Mapping[str, Any],
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    source = accepted_fixture["sources"][0]
    r2b = _mutable_r2b(source, tmp_path / mutation)
    rows = driver.group_fold_rows()
    if mutation == "seed":
        rows[0]["seed"] = "1"
    elif mutation == "duplicate":
        rows[-1] = dict(rows[0])
    elif mutation == "outer-cross":
        molecule = rows[0]["molecule_id"]
        for row in rows:
            if row["molecule_id"] == molecule and row["repeat"] == "0":
                row["outer_fold"] = "1"
                row["inner_fold"] = "" if row["outer_validation_fold"] == "1" else "0"
    else:
        component = rows[0]["similarity_component_hash"]
        matching = [
            row
            for row in rows
            if row["similarity_component_hash"] == component
            and row["repeat"] == "0"
            and row["outer_validation_fold"] == "1"
        ]
        assert len(matching) == 2 and matching[0]["inner_fold"] != ""
        matching[0]["inner_fold"] = str((int(matching[0]["inner_fold"]) + 1) % 4)
    (r2b / "group_folds.csv").write_bytes(compiler.csv_bytes(FOLD_COLUMNS, rows))
    _refresh_receipt(r2b, "group_folds.csv")
    with pytest.raises(adapter.X1AdapterError, match=message):
        adapter.challenge_inputs(r2b, synthetic=True)


def test_r2b_receipt_writable_symlink_and_file_set_fail_closed(
    accepted_fixture: Mapping[str, Any], tmp_path: Path
) -> None:
    source = accepted_fixture["sources"][0]
    writable = _mutable_r2b(source, tmp_path / "writable")
    with pytest.raises(compiler.X1SyntheticError, match="R2B source root is writable"):
        adapter.challenge_inputs(writable, synthetic=True)

    receipt = _mutable_r2b(source, tmp_path / "receipt")
    direct = receipt / "direct_observations.csv"
    direct.write_bytes(direct.read_bytes() + b"\n")
    compiler.seal_tree(receipt)
    with pytest.raises(adapter.X1AdapterError, match="manifest receipt differs"):
        adapter.challenge_inputs(receipt, synthetic=True)

    extra = _mutable_r2b(source, tmp_path / "extra")
    (extra / "unexpected.txt").write_text("synthetic", encoding="utf-8")
    compiler.seal_tree(extra)
    with pytest.raises(adapter.X1AdapterError, match="file set differs"):
        adapter.challenge_inputs(extra, synthetic=True)


def test_archive_checksum_is_verified_before_listing(tmp_path: Path) -> None:
    archive = tmp_path / "not-a-tar.gz"
    archive.write_bytes(b"not a tar archive")
    os.chmod(archive, 0o444)
    with pytest.raises(wrapper.X1AcquisitionError, match="checksum differs before listing"):
        wrapper.secure_extract_database(
            archive_path=archive,
            extract_root=tmp_path / "extract",
            expected_archive_sha256="0" * 64,
        )
    assert not (tmp_path / "extract").exists()


@pytest.mark.parametrize("case", ["traversal", "symlink", "duplicate", "multiple-db"])
def test_archive_member_adversaries_fail_closed(tmp_path: Path, case: str) -> None:
    archive = tmp_path / f"{case}.tar.gz"
    if case == "traversal":
        members = [_regular_member("../chembl_37.db")]
    elif case == "symlink":
        link = tarfile.TarInfo("chembl_37.db")
        link.type = tarfile.SYMTYPE
        link.linkname = "/outside"
        members = [link]
    elif case == "duplicate":
        members = [_regular_member("chembl_37.db"), _regular_member("chembl_37.db")]
    else:
        members = [
            _regular_member("a/chembl_37.db"),
            _regular_member("b/chembl_37.db"),
        ]
    digest = _archive(archive, members)
    with pytest.raises(wrapper.X1AcquisitionError):
        wrapper.secure_extract_database(
            archive_path=archive,
            extract_root=tmp_path / "extract",
            expected_archive_sha256=digest,
        )
    assert not (tmp_path / "extract").exists()


def test_archive_extracts_exact_database_bytes_and_seals_tree(tmp_path: Path) -> None:
    archive = tmp_path / "source.tar.gz"
    digest = _archive(archive, [_regular_member("nested/chembl_37.db")])
    database, receipt = wrapper.secure_extract_database(
        archive_path=archive,
        extract_root=tmp_path / "extract",
        expected_archive_sha256=digest,
    )
    assert database.read_bytes() == b"sqlite"
    assert receipt["database_bytes"] == 6
    assert not database.stat().st_mode & 0o222
    assert not database.parent.stat().st_mode & 0o222


def test_download_uses_one_exact_get_without_range_or_redirect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = b"synthetic archive bytes"
    calls: list[tuple[str, str, Mapping[str, str]]] = []

    class Response:
        status = 200

        def getheader(self, name: str) -> str | None:
            return "identity" if name == "Content-Encoding" else None

        def read(self, _size: int) -> bytes:
            value, self.remaining = self.remaining, b""
            return value

        remaining = payload

    class Connection:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            assert (host, port, timeout) == ("example.test", 443, 300)

        def request(self, method: str, path: str, headers: Mapping[str, str]) -> None:
            calls.append((method, path, headers))

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            pass

    monkeypatch.setattr(wrapper.http.client, "HTTPSConnection", Connection)
    destination = tmp_path / "archive.tar.gz"
    size = wrapper.download_once(
        url="https://example.test/exact/archive.tar.gz",
        destination=destination,
        expected_sha256=compiler.sha256_bytes(payload),
    )
    assert size == len(payload) and destination.read_bytes() == payload
    assert len(calls) == 1 and calls[0][:2] == (
        "GET",
        "/exact/archive.tar.gz",
    )
    assert "Range" not in calls[0][2]
    assert not destination.stat().st_mode & 0o222


def test_acceptance_binds_all_sources_and_derives_exact_consumed_claim(
    accepted_fixture: Mapping[str, Any], tmp_path: Path
) -> None:
    files = driver.acceptance_files(
        terminals=accepted_fixture["terminals"],
        physical=accepted_fixture["physical"],
        focused_tests_passed=18,
    )
    acceptance = tmp_path / driver.ACCEPTANCE_NAME
    acceptance.write_bytes(files[driver.ACCEPTANCE_NAME])
    consumed = wrapper.derive_consumed_claim(acceptance_path=acceptance)
    bindings = consumed["future_consumption_bindings"]
    assert consumed["status"] == wrapper.CONSUMED_STATUS
    assert consumed["consumed"] is True
    assert bindings == {
        "real_source_adapter_sha256": compiler.sha256_path(adapter.SCRIPT),
        "acquisition_wrapper_sha256": compiler.sha256_path(wrapper.SCRIPT),
        "official_shaped_synthetic_driver_sha256": compiler.sha256_path(driver.SCRIPT),
        "official_shaped_synthetic_acceptance_sha256": compiler.sha256_path(acceptance),
        "adapter_acceptance_receipt_sha256": compiler.sha256_path(acceptance),
    }
    adapter.validate_consumed_claim(consumed)
    tampered = dict(consumed)
    tampered["resource_falsifier"] = {
        **consumed["resource_falsifier"],
        "cpu_core_hours": 641,
    }
    with pytest.raises(adapter.X1AdapterError, match="resource_falsifier"):
        adapter.validate_consumed_claim(tampered)


def test_official_terminal_accounting_reports_acquisition_and_claim(
    accepted_fixture: Mapping[str, Any], tmp_path: Path
) -> None:
    source = accepted_fixture["sources"][0]
    private = tmp_path / "private"
    compilation, projection = adapter.compile_source(
        database_path=source / "extracted/chembl_37.db",
        challenge_root=source / "r2b",
        private_root=private,
        synthetic=True,
    )
    files = adapter.terminal_files(
        compilation,
        projection,
        synthetic=False,
        consumed_claim_sha256="0" * 64,
    )
    manifest = json.loads(files["manifest.json"])
    accounting = manifest["accounting"]
    assert accounting["new_external_records_opened"] == 336
    assert accounting["external_dataset_files_downloaded"] == 1
    assert accounting["official_structures_opened"] == 40
    assert accounting["execution_claims_created_or_consumed"] == 1
    assert accounting["official_target_values_opened"] == 0
    assert accounting["official_model_fits"] == 0
    compiler.cleanup(private)


def test_failed_replay_cleans_private_and_publishes_no_terminal(
    accepted_fixture: Mapping[str, Any], tmp_path: Path
) -> None:
    source = accepted_fixture["sources"][0]
    r2b = _mutable_r2b(source, tmp_path / "bad-r2b")
    rows = driver.group_fold_rows()
    rows[0]["seed"] = "0"
    (r2b / "group_folds.csv").write_bytes(compiler.csv_bytes(FOLD_COLUMNS, rows))
    _refresh_receipt(r2b, "group_folds.csv")
    terminal = tmp_path / "failed-terminal"
    with pytest.raises(adapter.X1AdapterError, match="fold seed differs"):
        adapter.run_replay(
            database_path=source / "extracted/chembl_37.db",
            challenge_root=r2b,
            replay_root=terminal,
            synthetic=True,
        )
    assert not terminal.exists()
    assert not terminal.with_name(f".{terminal.name}-private").exists()


def test_tracked_claim_remains_unconsumed_and_has_zero_operation_accounting() -> None:
    claim = adapter.tracked_claim()
    assert claim["consumed"] is False
    assert all(value is None for value in claim["future_consumption_bindings"].values())
    accounting = claim["current_milestone_accounting"]
    assert accounting["acquisition_claims_consumed"] == 0
    assert accounting["external_dataset_files_downloaded"] == 0
    assert accounting["official_model_fits"] == 0
    assert accounting["live_uploads"] == 0

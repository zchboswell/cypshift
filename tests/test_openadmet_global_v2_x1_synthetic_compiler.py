from __future__ import annotations

import csv
import io
import json
import shutil
import sqlite3
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parents[1]
RESEARCH = ROOT / "research/external-transfer"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import global_v2_x1_compiler as compiler  # noqa: E402
import run_global_v2_x1_synthetic as driver  # noqa: E402


@pytest.fixture(scope="module")
def accepted_fixture(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    base = tmp_path_factory.mktemp("x1-synthetic-accepted")
    source_a = driver.publish_source(base / "source-a", reverse=False)
    terminal_a = compiler.run_replay(source_a, base / "terminal-a")
    source_b = driver.publish_source(base / "source-b", reverse=True)
    terminal_b = compiler.run_replay(source_b, base / "terminal-b")
    private = base / "private-inspection"
    compilation = compiler.compile_source(source_a, private)
    yield {
        "base": base,
        "source_a": source_a,
        "source_b": source_b,
        "terminal_a": terminal_a,
        "terminal_b": terminal_b,
        "private": private,
        "compilation": compilation,
    }
    compiler.cleanup(base)


def _csv_from_bytes(value: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(value.decode("utf-8"))))


def _mutable_source(source: Path, destination: Path) -> Path:
    shutil.copytree(source, destination)
    compiler.make_writable(destination)
    return destination


def _refresh_source_receipt(source: Path) -> None:
    manifest_path = source / compiler.SOURCE_MANIFEST_NAME
    manifest = compiler.read_json(manifest_path)
    for name in (
        compiler.DATABASE_NAME,
        compiler.CHALLENGE_NAME,
        compiler.FOLDS_NAME,
    ):
        manifest["source_receipts"][name] = compiler.sha256_path(source / name)
    manifest_path.write_bytes(compiler.json_bytes(manifest))
    compiler.seal_tree(source)


def _mutate_database(source: Path, sql: str) -> None:
    database = source / compiler.DATABASE_NAME
    connection = sqlite3.connect(database)
    try:
        connection.executescript(sql)
        connection.commit()
    finally:
        connection.close()
    _refresh_source_receipt(source)


def test_fixture_has_exact_contract_shape() -> None:
    assert len(driver.challenge_rows()) == 40
    assert len(driver.fold_rows()) == 600
    assert len(driver.external_smiles()) == 80
    rows = driver.table_rows()
    assert {name: len(value) for name, value in rows.items()} == {
        "source": 1,
        "docs": 1,
        "target_dictionary": 5,
        "assays": 7,
        "molecule_dictionary": 84,
        "compound_structures": 84,
        "activities": 336,
    }


def test_opposite_physical_order_is_logically_and_terminally_identical(
    accepted_fixture: Mapping[str, Any],
) -> None:
    source_a = accepted_fixture["source_a"]
    source_b = accepted_fixture["source_b"]
    assert compiler.sha256_path(source_a / compiler.DATABASE_NAME) != compiler.sha256_path(
        source_b / compiler.DATABASE_NAME
    )
    assert compiler.relative_byte_map(
        accepted_fixture["terminal_a"]
    ) == compiler.relative_byte_map(accepted_fixture["terminal_b"])
    manifest_a = compiler.read_json(accepted_fixture["terminal_a"] / "manifest.json")
    manifest_b = compiler.read_json(accepted_fixture["terminal_b"] / "manifest.json")
    assert manifest_a["logical_source_sha256"] == manifest_b["logical_source_sha256"]


def test_filter_preserves_all_rows_and_assigns_one_ordered_state(
    accepted_fixture: Mapping[str, Any],
) -> None:
    compilation = accepted_fixture["compilation"]
    counts = compilation.filter_counts
    assert counts["joined_rows"] == 336
    assert counts["eligible_rows"] == 320
    assert counts["ineligible_rows"] == 16
    assert sum(counts["reason_counts"].values()) == 16
    assert all(counts["reason_counts"][reason] >= 1 for reason in compiler.FILTER_REASONS)
    assert counts["eligible_rows_by_endpoint"] == {
        endpoint: 80 for endpoint in compiler.ENDPOINTS
    }
    assert sum(
        value
        for endpoint in counts["reason_counts_by_endpoint"].values()
        for value in endpoint.values()
    ) == 16
    raw_lines = compilation.private_files["raw_source_rows.jsonl"].splitlines()
    assert len(raw_lines) == 336
    first = json.loads(raw_lines[0])
    assert set(first) == set(compiler.RAW_COLUMNS)
    assert {value["type"] for value in first.values()} <= {
        "null",
        "integer",
        "real",
        "text",
    }


def test_filter_order_and_type_strictness_are_exact(
    accepted_fixture: Mapping[str, Any],
) -> None:
    compilation = accepted_fixture["compilation"]
    assert compilation.filter_counts["reason_counts"] == {
        "TARGET_NOT_SELECTED": 1,
        "STANDARD_TYPE_NOT_IC50": 1,
        "STANDARD_RELATION_NOT_EXACT": 1,
        "STANDARD_UNITS_NOT_NM": 1,
        "STANDARD_VALUE_NOT_FINITE_POSITIVE": 2,
        "PCHEMBL_NOT_FINITE": 2,
        "PCHEMBL_RECOMPUTE_MISMATCH": 1,
        "STANDARD_FLAG_NOT_ONE": 1,
        "POTENTIAL_DUPLICATE_NOT_ZERO": 1,
        "DATA_VALIDITY_COMMENT_PRESENT": 1,
        "ASSAY_CONFIDENCE_BELOW_NINE": 1,
        "ASSAY_ORGANISM_EXPLICITLY_NONHUMAN": 1,
        "STRUCTURE_MISSING_OR_QUARANTINED": 2,
    }


def test_source_supplied_chemistry_identity_is_never_trusted(
    accepted_fixture: Mapping[str, Any],
) -> None:
    compilation = accepted_fixture["compilation"]
    assert len(compilation.external_identities) == 80
    assert all(
        not item.equivalence_key.startswith("SOURCE")
        and len(item.equivalence_key) == 14
        for item in compilation.external_identities
    )
    assert all(len(item.structure_hash) == 64 for item in compilation.external_identities)


def test_union_is_exhaustive_transitive_and_keeps_forbidden_ghosts(
    accepted_fixture: Mapping[str, Any],
) -> None:
    compilation = accepted_fixture["compilation"]
    assert compilation.union_counts == {
        "union_unique_structure_nodes": 110,
        "pairwise_similarity_comparisons": 5995,
        "qualifying_similarity_edges": 157,
        "d032_similarity_components": 40,
        "equivalence_spanning_edges": 10,
        "union_components": 40,
        "global_exact_forbidden_structures": 10,
        "global_equivalent_forbidden_structures": 10,
        "global_forbidden_structures": 20,
    }
    nodes = _csv_from_bytes(compilation.private_files["union_nodes.csv"])
    edges = _csv_from_bytes(compilation.private_files["union_edges.csv"])
    assert sum(row["globally_forbidden_external"] == "1" for row in nodes) == 20
    assert sum(row["source_membership"] == "challenge+external" for row in nodes) == 10
    assert sum(row["edge_kind"] == "INCHI_CONNECTIVITY" for row in edges) == 10
    assert sum(row["edge_kind"] == "D032_SIMILARITY" for row in edges) == 157

    identities = {item.source_id: item for item in compilation.external_identities}
    challenge = {item.source_id: item for item in compilation.challenge_identities}
    component = compilation.component_by_hash
    assert component[challenge["x1-challenge-00-0"].structure_hash] == component[
        identities["CHEMBL_SYNTH_0002"].structure_hash
    ]
    assert component[identities["CHEMBL_SYNTH_0002"].structure_hash] == component[
        identities["CHEMBL_SYNTH_0003"].structure_hash
    ]


def test_support_counts_unique_structures_and_union_components(
    accepted_fixture: Mapping[str, Any],
) -> None:
    compilation = accepted_fixture["compilation"]
    support = {
        (row["scope"], row["safe_molecules"], row["safe_components"])
        for row in compilation.support_rows
    }
    assert support == {
        ("OUTER", "52", "36"),
        ("INNER", "44", "32"),
        ("CONFIRMATORY", "52", "36"),
    }
    assert len(compilation.support_rows) == 304
    assert compilation.support_decisions["novel_molecules_by_endpoint"] == {
        endpoint: 60 for endpoint in compiler.ENDPOINTS
    }
    assert compilation.support_decisions["miniature_thresholds"]["pass"] is True
    assert compilation.support_decisions["official_thresholds"]["pass"] is False


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("DROP TABLE source;", "required SQLite table missing"),
        (
            "UPDATE target_dictionary SET tax_id = 10090 WHERE tid = 1;",
            "selected target metadata differs",
        ),
        (
            "DELETE FROM molecule_dictionary WHERE molregno = 1;",
            "joined source row count differs",
        ),
        (
            "ALTER TABLE source RENAME TO source_old;"
            "CREATE TABLE source (src_id INTEGER, src_description TEXT PRIMARY KEY);"
            "INSERT INTO source SELECT * FROM source_old; DROP TABLE source_old;",
            "primary join identity differs: source",
        ),
        (
            "ALTER TABLE activities DROP COLUMN activity_comment;",
            "required SQLite column missing: activities",
        ),
    ],
)
def test_schema_target_join_and_primary_identity_fail_closed(
    accepted_fixture: Mapping[str, Any],
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    source = _mutable_source(accepted_fixture["source_a"], tmp_path / "source")
    _mutate_database(source, mutation)
    with pytest.raises(compiler.X1SyntheticError, match=message):
        compiler.compile_source(source, tmp_path / "private")


def test_writable_symlink_wal_and_hardlink_inputs_fail_closed(
    accepted_fixture: Mapping[str, Any], tmp_path: Path
) -> None:
    source = _mutable_source(accepted_fixture["source_a"], tmp_path / "writable")
    with pytest.raises(compiler.X1SyntheticError, match="source root is writable"):
        compiler.compile_source(source, tmp_path / "private-writable")

    symlink = tmp_path / "source-link"
    symlink.symlink_to(accepted_fixture["source_a"], target_is_directory=True)
    with pytest.raises(compiler.X1SyntheticError, match="source root is not a directory"):
        compiler.compile_source(symlink, tmp_path / "private-link")

    wal_source = _mutable_source(accepted_fixture["source_a"], tmp_path / "wal")
    companion = Path(f"{wal_source / compiler.DATABASE_NAME}-wal")
    companion.write_bytes(b"synthetic companion")
    compiler.seal_tree(wal_source)
    with pytest.raises(compiler.X1SyntheticError, match="source root file set differs"):
        compiler.compile_source(wal_source, tmp_path / "private-wal")

    hard_source = _mutable_source(accepted_fixture["source_a"], tmp_path / "hard")
    database = hard_source / compiler.DATABASE_NAME
    (tmp_path / "hardlink-copy.sqlite3").hardlink_to(database)
    compiler.seal_tree(hard_source)
    with pytest.raises(compiler.X1SyntheticError, match="hard-link count differs"):
        compiler.compile_source(hard_source, tmp_path / "private-hard")


def test_corrupt_authenticated_database_fails_integrity_or_open(
    accepted_fixture: Mapping[str, Any], tmp_path: Path
) -> None:
    source = _mutable_source(accepted_fixture["source_a"], tmp_path / "source")
    database = source / compiler.DATABASE_NAME
    value = bytearray(database.read_bytes())
    value[len(value) // 2 : len(value) // 2 + 32] = b"X" * 32
    database.write_bytes(value)
    _refresh_source_receipt(source)
    with pytest.raises(compiler.X1SyntheticError):
        compiler.compile_source(source, tmp_path / "private")


def test_query_is_explicit_complete_ordered_and_nonaggregating() -> None:
    query = compiler.SOURCE_QUERY.upper()
    assert "SELECT *" not in query
    assert "ROWID" not in query
    assert "GROUP BY" not in query
    assert "COUNT(" not in query
    assert (
        "ORDER BY T.TARGET_CHEMBL_ID, A.ACTIVITY_ID, A.ASSAY_ID, "
        "A.MOLREGNO, M.CHEMBL_ID"
    ) in " ".join(query.split())
    assert tuple(item.split(" AS ")[-1].strip() for item in query.splitlines() if " AS " in item and item.strip().startswith("A."))[:1] == ("ACTIVITY_ID,",)


def test_inclusive_exact_threshold_edge_is_retained() -> None:
    challenge = compiler._structure_identity(
        "challenge",
        "threshold-challenge",
        "CCCCCc1ccccc1",
        "threshold-component",
    )
    external = compiler._structure_identity(
        "external", "threshold-external", "CCCCCc1ccncc1"
    )
    assert challenge is not None and external is not None
    components, forbidden, counts, _, edge_bytes = compiler.build_union(
        [external], [challenge]
    )
    assert forbidden == frozenset()
    assert counts["pairwise_similarity_comparisons"] == 1
    assert counts["qualifying_similarity_edges"] == 1
    assert counts["union_components"] == 1
    assert components[challenge.structure_hash] == components[external.structure_hash]
    edges = _csv_from_bytes(edge_bytes)
    assert [row["edge_kind"] for row in edges] == ["D032_SIMILARITY"]


def test_fold_missing_duplicate_cross_family_and_inner_imbalance_fail_closed(
    accepted_fixture: Mapping[str, Any], tmp_path: Path
) -> None:
    original = compiler.read_csv(
        accepted_fixture["source_a"] / compiler.FOLDS_NAME,
        compiler.FOLD_COLUMNS,
    )

    missing = _mutable_source(accepted_fixture["source_a"], tmp_path / "missing")
    (missing / compiler.FOLDS_NAME).write_bytes(
        compiler.csv_bytes(compiler.FOLD_COLUMNS, original[:-1])
    )
    _refresh_source_receipt(missing)
    with pytest.raises(compiler.X1SyntheticError, match="fold row count differs"):
        compiler.compile_source(missing, tmp_path / "private-missing")

    duplicate = _mutable_source(accepted_fixture["source_a"], tmp_path / "duplicate")
    duplicate_rows = [dict(row) for row in original]
    duplicate_rows[-1] = dict(duplicate_rows[0])
    (duplicate / compiler.FOLDS_NAME).write_bytes(
        compiler.csv_bytes(compiler.FOLD_COLUMNS, duplicate_rows)
    )
    _refresh_source_receipt(duplicate)
    with pytest.raises(compiler.X1SyntheticError, match="duplicate fold identity"):
        compiler.compile_source(duplicate, tmp_path / "private-duplicate")

    crossing = _mutable_source(accepted_fixture["source_a"], tmp_path / "crossing")
    crossing_rows = [dict(row) for row in original]
    for row in crossing_rows:
        if row["molecule_id"] == "x1-challenge-00-0" and row["repeat"] == "0":
            row["assigned_outer"] = "1"
            row["inner_fold"] = "" if row["outer_context"] == "1" else "0"
    (crossing / compiler.FOLDS_NAME).write_bytes(
        compiler.csv_bytes(compiler.FOLD_COLUMNS, crossing_rows)
    )
    _refresh_source_receipt(crossing)
    with pytest.raises(compiler.X1SyntheticError, match="component crosses outer boundary"):
        compiler.compile_source(crossing, tmp_path / "private-crossing")

    imbalance = _mutable_source(accepted_fixture["source_a"], tmp_path / "imbalance")
    imbalance_rows = [dict(row) for row in original]
    selected = [
        row
        for row in imbalance_rows
        if row["molecule_id"].startswith("x1-challenge-01-")
        and row["repeat"] == "0"
        and row["outer_context"] == "0"
    ]
    assert len(selected) == 2 and selected[0]["inner_fold"] == selected[1]["inner_fold"]
    replacement = str((int(selected[0]["inner_fold"]) + 1) % 4)
    for row in selected:
        row["inner_fold"] = replacement
    (imbalance / compiler.FOLDS_NAME).write_bytes(
        compiler.csv_bytes(compiler.FOLD_COLUMNS, imbalance_rows)
    )
    _refresh_source_receipt(imbalance)
    with pytest.raises(compiler.X1SyntheticError, match="inner component balance differs"):
        compiler.compile_source(imbalance, tmp_path / "private-imbalance")


def test_no_replace_traversal_and_failure_cleanup(
    accepted_fixture: Mapping[str, Any], tmp_path: Path
) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(compiler.X1SyntheticError, match="destination exists"):
        compiler.publish_files(existing, {"result.json": b"{}\n"})
    with pytest.raises(compiler.X1SyntheticError, match="unsafe output name"):
        compiler.publish_files(tmp_path / "traversal", {"../outside": b"no"})
    assert not (tmp_path / "traversal").exists()

    source = _mutable_source(accepted_fixture["source_a"], tmp_path / "bad-source")
    _mutate_database(source, "DROP TABLE activities;")
    replay = tmp_path / "failed-terminal"
    with pytest.raises(compiler.X1SyntheticError):
        compiler.run_replay(source, replay)
    assert not replay.exists()
    assert not replay.with_name(f".{replay.name}-private").exists()


def test_acceptance_binds_sources_code_tests_and_zero_authority(
    accepted_fixture: Mapping[str, Any], tmp_path: Path
) -> None:
    files = compiler.acceptance_files(
        accepted_fixture["terminal_a"],
        accepted_fixture["terminal_b"],
        accepted_fixture["source_a"],
        accepted_fixture["source_b"],
        16,
        driver.SCRIPT,
        driver.FOCUSED_TESTS,
    )
    assert set(files) == {driver.ACCEPTANCE_NAME}
    value = json.loads(files[driver.ACCEPTANCE_NAME])
    assert value["source_bindings"]["compiler_sha256"] == compiler.sha256_path(
        compiler.SCRIPT
    )
    assert value["source_bindings"]["synthetic_driver_sha256"] == compiler.sha256_path(
        driver.SCRIPT
    )
    assert value["source_bindings"]["focused_tests_sha256"] == compiler.sha256_path(
        driver.FOCUSED_TESTS
    )
    assert value["private_roots_retained"] == 0
    assert all(value["accounting"][name] == 0 for name in compiler.OFFICIAL_ZERO_FIELDS)


def test_formal_driver_cleans_work_and_publishes_one_immutable_receipt(
    tmp_path: Path,
) -> None:
    work = tmp_path / "formal-work"
    acceptance = tmp_path / "acceptance"
    receipt = driver.run_formal(work, acceptance, focused_tests_passed=16)
    assert receipt == acceptance / driver.ACCEPTANCE_NAME
    assert receipt.is_file()
    assert not work.exists()
    assert not bool(acceptance.stat().st_mode & 0o222)
    with pytest.raises(compiler.X1SyntheticError, match="acceptance root exists"):
        driver.run_formal(work, acceptance, focused_tests_passed=16)


def test_implementation_contains_no_model_metric_submission_or_network_operation() -> None:
    sources = compiler.SCRIPT.read_text(encoding="utf-8") + driver.SCRIPT.read_text(
        encoding="utf-8"
    )
    forbidden = (
        "requests.",
        "urllib.request",
        "subprocess",
        "CatBoost",
        "torch.",
        "sklearn",
        "official_metric(",
        "upload(",
    )
    assert all(token not in sources for token in forbidden)
    assert all(name in compiler.OFFICIAL_ZERO_FIELDS for name in compiler.OFFICIAL_ZERO_FIELDS)

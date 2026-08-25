#!/usr/bin/env python3
"""Create, replay, and accept the two-root synthetic EXP-X1 compiler probe."""

from __future__ import annotations

import argparse
import csv
import io
import sqlite3
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Final

from rdkit import Chem

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))

import global_v2_x1_compiler as compiler  # noqa: E402

FOCUSED_TESTS: Final = (
    ROOT / "tests/test_openadmet_global_v2_x1_synthetic_compiler.py"
)
ACCEPTANCE_NAME: Final = "global_v2_x1_synthetic_compiler_acceptance.json"
SEED: Final = 20260831

REGULAR_CORES: Final = (
    "c1ccncc1",
    "c1ccsc1",
    "c1ccoc1",
    "c1ncc[nH]1",
    "c1nccs1",
    "c1ncco1",
    "C1CCNCC1",
    "C1COCCN1",
    "c1ccc2[nH]ccc2c1",
    "c1ccc2ncccc2c1",
    "C1C2CC3CC1CC(C2)C3",
    "c1nnc[nH]1",
    "c1cn[nH]c1",
    "c1nnn[nH]1",
    "c1ccc2occc2c1",
    "c1ccc2sccc2c1",
    "c1ccc2[nH]ncc2c1",
    "c1ccc2ncsc2c1",
    "C1CSCS1",
)

UNRELATED: Final = (
    "CCO",
    "CCN",
    "CC(=O)O",
    "CC(N)=O",
    "CC#N",
    "COC",
    "CNC",
    "CN(C)C",
    "CS(C)(=O)=O",
    "CP(C)(C)=O",
    "C[Si](C)(C)C",
    "C1CC1",
    "C1CO1",
    "C1COC1",
    "C1CN1",
    "C1CNC1",
    "c1ccccc1",
    "c1ccncc1",
    "c1ccsc1",
    "c1ccoc1",
)

TABLE_DDL: Final = {
    "source": """
        CREATE TABLE source (
          src_id INTEGER PRIMARY KEY,
          src_description TEXT
        )
    """,
    "docs": """
        CREATE TABLE docs (
          doc_id INTEGER PRIMARY KEY,
          chembl_id TEXT,
          year INTEGER,
          doi TEXT,
          src_id INTEGER NOT NULL
        )
    """,
    "target_dictionary": """
        CREATE TABLE target_dictionary (
          tid INTEGER PRIMARY KEY,
          target_chembl_id TEXT,
          pref_name TEXT,
          organism TEXT,
          tax_id INTEGER,
          target_type TEXT
        )
    """,
    "assays": """
        CREATE TABLE assays (
          assay_id INTEGER PRIMARY KEY,
          assay_chembl_id TEXT,
          assay_type TEXT,
          assay_organism TEXT,
          assay_tax_id INTEGER,
          description TEXT,
          confidence_score INTEGER,
          doc_id INTEGER NOT NULL,
          tid INTEGER NOT NULL
        )
    """,
    "molecule_dictionary": """
        CREATE TABLE molecule_dictionary (
          molregno INTEGER PRIMARY KEY,
          chembl_id TEXT
        )
    """,
    "compound_structures": """
        CREATE TABLE compound_structures (
          molregno INTEGER PRIMARY KEY,
          canonical_smiles TEXT,
          standard_inchi TEXT,
          standard_inchi_key TEXT
        )
    """,
    "activities": """
        CREATE TABLE activities (
          activity_id INTEGER PRIMARY KEY,
          assay_id INTEGER NOT NULL,
          molregno INTEGER NOT NULL,
          standard_type TEXT,
          standard_relation TEXT,
          standard_value,
          standard_units TEXT,
          pchembl_value,
          standard_flag INTEGER,
          potential_duplicate INTEGER,
          data_validity_comment TEXT,
          activity_comment TEXT
        )
    """,
}

TABLE_COLUMNS: Final = {
    "source": ("src_id", "src_description"),
    "docs": ("doc_id", "chembl_id", "year", "doi", "src_id"),
    "target_dictionary": (
        "tid",
        "target_chembl_id",
        "pref_name",
        "organism",
        "tax_id",
        "target_type",
    ),
    "assays": (
        "assay_id",
        "assay_chembl_id",
        "assay_type",
        "assay_organism",
        "assay_tax_id",
        "description",
        "confidence_score",
        "doc_id",
        "tid",
    ),
    "molecule_dictionary": ("molregno", "chembl_id"),
    "compound_structures": (
        "molregno",
        "canonical_smiles",
        "standard_inchi",
        "standard_inchi_key",
    ),
    "activities": (
        "activity_id",
        "assay_id",
        "molregno",
        "standard_type",
        "standard_relation",
        "standard_value",
        "standard_units",
        "pchembl_value",
        "standard_flag",
        "potential_duplicate",
        "data_validity_comment",
        "activity_comment",
    ),
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise compiler.X1SyntheticError(message)


def _isotope_variant(smiles: str) -> str:
    molecule = Chem.MolFromSmiles(smiles)
    _require(molecule is not None, "isotope source is invalid")
    molecule.GetAtomWithIdx(0).SetIsotope(13)
    value = Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True)
    _require(value != smiles, "isotope variant did not change")
    return value


def challenge_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    pairs = [("Cc1ccc(N)cc1", "Cc1ccc(C)cc1")]
    pairs.extend((f"CCC{core}", f"CCCC{core}") for core in REGULAR_CORES)
    for component_index, pair in enumerate(pairs):
        for molecule_index, smiles in enumerate(pair):
            rows.append(
                {
                    "molecule_id": (
                        f"x1-challenge-{component_index:02d}-{molecule_index}"
                    ),
                    "raw_smiles": smiles,
                    "challenge_component": f"x1-component-{component_index:02d}",
                    "confirmatory": "1" if component_index < 4 else "0",
                }
            )
    _require(len(rows) == 40, "challenge fixture count differs")
    return rows


def fold_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    challenge = challenge_rows()
    for repeat in compiler.REPEATS:
        assigned_by_component = {
            component: (index + repeat) % 5
            for index, component in enumerate(
                sorted({row["challenge_component"] for row in challenge})
            )
        }
        for outer in compiler.OUTER_FOLDS:
            training_components = [
                component
                for component in sorted(assigned_by_component)
                if assigned_by_component[component] != outer
            ]
            inner_by_component = {
                component: index % 4
                for index, component in enumerate(training_components)
            }
            for row in challenge:
                component = row["challenge_component"]
                assigned = assigned_by_component[component]
                rows.append(
                    {
                        "molecule_id": row["molecule_id"],
                        "repeat": str(repeat),
                        "outer_context": str(outer),
                        "assigned_outer": str(assigned),
                        "inner_fold": (
                            "" if assigned == outer else str(inner_by_component[component])
                        ),
                    }
                )
    _require(len(rows) == 600, "fold fixture count differs")
    return rows


def external_smiles() -> list[str]:
    challenge = challenge_rows()
    first_by_component = {
        row["challenge_component"]: row["raw_smiles"]
        for row in challenge
        if row["molecule_id"].endswith("-0")
    }
    values: list[str] = []
    for index in range(20):
        base = first_by_component[f"x1-component-{index:02d}"]
        forbidden = base if index % 2 == 0 else _isotope_variant(base)
        if index == 0:
            direct = "Cc1ccc(F)cc1"
            chain = "Fc1ccc(F)cc1"
        else:
            core = REGULAR_CORES[index - 1]
            direct = f"CCCCC{core}"
            chain = f"CCCCCC{core}"
        values.extend((forbidden, direct, chain, UNRELATED[index]))
    _require(len(values) == 80 and len(set(values)) == 80, "external fixture differs")
    return values


def _base_activity(activity_id: int, assay_id: int, molregno: int) -> dict[str, object]:
    standard = float(10 ** (2 + (molregno % 4)))
    return {
        "activity_id": activity_id,
        "assay_id": assay_id,
        "molregno": molregno,
        "standard_type": "IC50",
        "standard_relation": "=",
        "standard_value": standard,
        "standard_units": "nM",
        "pchembl_value": 9.0 - __import__("math").log10(standard),
        "standard_flag": 1,
        "potential_duplicate": 0,
        "data_validity_comment": None,
        "activity_comment": f"synthetic activity {activity_id}",
    }


def table_rows() -> dict[str, list[tuple[object, ...]]]:
    endpoints = list(compiler.ENDPOINTS)
    targets: list[tuple[object, ...]] = []
    assays: list[tuple[object, ...]] = []
    for index, endpoint in enumerate(endpoints, start=1):
        target = compiler.ENDPOINT_TARGETS[endpoint]
        targets.append(
            (index, target, f"Synthetic {endpoint}", "Homo sapiens", 9606, "SINGLE PROTEIN")
        )
        organism: str | None = None if index == 1 else "Homo sapiens"
        tax_id: int | None = None if index == 1 else 9606
        assays.append(
            (
                index,
                f"CHEMBL_SYNTH_ASSAY_{index}",
                "B",
                organism,
                tax_id,
                f"Synthetic exact {endpoint} assay",
                9,
                1,
                index,
            )
        )
    targets.append((5, "CHEMBL_SYNTH_OTHER", "Other target", "Homo sapiens", 9606, "SINGLE PROTEIN"))
    assays.extend(
        [
            (5, "CHEMBL_SYNTH_WRONG_TARGET", "B", "Homo sapiens", 9606, "Wrong target", 9, 1, 5),
            (6, "CHEMBL_SYNTH_LOW_CONF", "B", "Homo sapiens", 9606, "Low confidence", 8, 1, 1),
            (7, "CHEMBL_SYNTH_NONHUMAN", "B", "Mus musculus", 10090, "Nonhuman", 9, 1, 1),
        ]
    )

    smiles = external_smiles() + [None, "not-a-smiles", "Cl", "Br"]
    molecules = [(index, f"CHEMBL_SYNTH_{index:04d}") for index in range(1, 85)]
    structures = [
        (
            index,
            value,
            None if value is None else f"source-inchi-must-not-be-trusted-{index}",
            None if value is None else f"SOURCEKEYMUSTNOT{index:04d}",
        )
        for index, value in enumerate(smiles, start=1)
    ]

    activities: list[dict[str, object]] = []
    activity_id = 1
    for molregno in range(1, 81):
        for assay_id in range(1, 5):
            activities.append(_base_activity(activity_id, assay_id, molregno))
            activity_id += 1

    adversaries: list[dict[str, object]] = []
    for offset in range(16):
        adversaries.append(_base_activity(activity_id + offset, 1, 83 + offset % 2))
    adversaries[0].update(assay_id=5, standard_type="Ki")
    adversaries[1]["standard_type"] = "Ki"
    adversaries[2]["standard_relation"] = ">"
    adversaries[3]["standard_units"] = "uM"
    adversaries[4]["standard_value"] = 0.0
    adversaries[5]["pchembl_value"] = None
    adversaries[6]["pchembl_value"] = 1.0
    adversaries[7]["standard_flag"] = 0
    adversaries[8]["potential_duplicate"] = 1
    adversaries[9]["data_validity_comment"] = "Synthetic warning"
    adversaries[10]["assay_id"] = 6
    adversaries[11]["assay_id"] = 7
    adversaries[12]["molregno"] = 81
    adversaries[13]["molregno"] = 82
    adversaries[14]["standard_value"] = "100"
    adversaries[15]["pchembl_value"] = float("inf")
    activities.extend(adversaries)
    _require(activity_id + 16 == 337 and len(activities) == 336, "activity fixture differs")

    return {
        "source": [(1, "Synthetic ChEMBL 37 source")],
        "docs": [(1, "CHEMBL_SYNTH_DOC", 2026, "10.0/synthetic", 1)],
        "target_dictionary": targets,
        "assays": assays,
        "molecule_dictionary": molecules,
        "compound_structures": structures,
        "activities": [tuple(row[name] for name in TABLE_COLUMNS["activities"]) for row in activities],
    }


def _csv_payload(
    columns: Sequence[str], rows: Iterable[Mapping[str, object]]
) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_sqlite(path: Path, reverse: bool) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA page_size=4096")
        connection.execute("PRAGMA journal_mode=DELETE")
        rows_by_table = table_rows()
        table_order = list(TABLE_DDL)
        if reverse:
            table_order.reverse()
        for table in table_order:
            connection.execute(TABLE_DDL[table])
        insertion_order = list(TABLE_DDL)
        if reverse:
            insertion_order.reverse()
        for table in insertion_order:
            rows = list(rows_by_table[table])
            rows.sort(key=lambda row: int(row[0]), reverse=reverse)
            placeholders = ", ".join("?" for _ in TABLE_COLUMNS[table])
            quoted = ", ".join(f'"{name}"' for name in TABLE_COLUMNS[table])
            connection.executemany(
                f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})', rows
            )
        connection.execute(f"PRAGMA user_version={SEED % 2_147_483_647}")
        connection.commit()
        _require(
            connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)],
            "created SQLite integrity differs",
        )
    finally:
        connection.close()


def publish_source(root: Path, reverse: bool) -> Path:
    _require(not root.exists() and not root.is_symlink(), "source root exists")
    root.mkdir(parents=True)
    try:
        database = root / compiler.DATABASE_NAME
        _write_sqlite(database, reverse)
        challenge = sorted(challenge_rows(), key=lambda row: row["molecule_id"], reverse=reverse)
        folds = sorted(
            fold_rows(),
            key=lambda row: (
                row["molecule_id"],
                int(row["repeat"]),
                int(row["outer_context"]),
            ),
            reverse=reverse,
        )
        (root / compiler.CHALLENGE_NAME).write_bytes(
            _csv_payload(compiler.CHALLENGE_COLUMNS, challenge)
        )
        (root / compiler.FOLDS_NAME).write_bytes(
            _csv_payload(compiler.FOLD_COLUMNS, folds)
        )
        receipts = {
            name: compiler.sha256_path(root / name)
            for name in (
                compiler.DATABASE_NAME,
                compiler.CHALLENGE_NAME,
                compiler.FOLDS_NAME,
            )
        }
        manifest = {
            "schema_version": compiler.SOURCE_SCHEMA,
            "synthetic": True,
            "seed": SEED,
            "semantic_source_id": "global-v2-x1-synthetic-fixture-v1",
            "physical_order": "reverse" if reverse else "canonical",
            "source_receipts": receipts,
            "counts": {
                "sqlite_tables": 7,
                "external_compounds": 84,
                "activity_rows": 336,
                "challenge_molecules": 40,
                "fold_rows": 600,
            },
            "authority": {
                "synthetic_only": True,
                "external_records": False,
                "official_inputs": False,
                "model_fitting": False,
                "submission": False,
            },
        }
        (root / compiler.SOURCE_MANIFEST_NAME).write_bytes(compiler.json_bytes(manifest))
        compiler.seal_tree(root)
    except Exception:
        compiler.cleanup(root)
        raise
    return root


def run_formal(work_root: Path, acceptance_root: Path, focused_tests_passed: int) -> Path:
    _require(focused_tests_passed > 0, "focused test count must be positive")
    _require(not work_root.exists() and not work_root.is_symlink(), "work root exists")
    _require(
        not acceptance_root.exists() and not acceptance_root.is_symlink(),
        "acceptance root exists",
    )
    work_root.mkdir(parents=True)
    source_a = work_root / "source-a"
    source_b = work_root / "source-b"
    terminal_a = work_root / "terminal-a"
    terminal_b = work_root / "terminal-b"
    try:
        publish_source(source_a, reverse=False)
        compiler.run_replay(source_a, terminal_a)
        publish_source(source_b, reverse=True)
        compiler.run_replay(source_b, terminal_b)
        files = compiler.acceptance_files(
            terminal_a,
            terminal_b,
            source_a,
            source_b,
            focused_tests_passed,
            SCRIPT,
            FOCUSED_TESTS,
        )
        compiler.publish_files(acceptance_root, files)
    finally:
        compiler.cleanup(work_root)
    _require(not work_root.exists(), "formal work root cleanup differs")
    return acceptance_root / ACCEPTANCE_NAME


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", required=True, type=Path)
    parser.add_argument("--acceptance-root", required=True, type=Path)
    parser.add_argument("--focused-tests-passed", required=True, type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = run_formal(
        args.work_root.resolve(),
        args.acceptance_root.resolve(),
        args.focused_tests_passed,
    )
    print(receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

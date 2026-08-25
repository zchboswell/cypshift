#!/usr/bin/env python3
"""Synthetic-only G2-5B ChEMBL compiler and union-family firewall."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import shutil
import sqlite3
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast
from urllib.parse import quote

from rdkit import Chem, DataStructs, rdBase
from rdkit.Chem import inchi, rdFingerprintGenerator

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from cypshift import openadmet_topology as topology  # noqa: E402
from cypshift.chemistry import (  # noqa: E402
    STANDARDIZATION_VERSION,
    standardize_molecule,
)
from cypshift.schema import MoleculeInput, MoleculeStatus  # noqa: E402

CONTRACT: Final = (
    ROOT
    / "benchmarks/openadmet_cyp_2026/"
    "global_v2_x1_synthetic_compiler_contract.json"
)
CONTRACT_SHA256: Final = (
    "db36935e2fb7478f8e038f094a11bcdd47ed8574541b50b2a27170170eba3442"
)
PARENT: Final = (
    ROOT / "benchmarks/openadmet_cyp_2026/global_v2_x1_provenance_contract.json"
)
PARENT_SHA256: Final = (
    "a51f81a411e35e6514cbf2739a382b63b6c4db2e379e18004907a8e590a21c1d"
)
CHEMISTRY_SOURCE: Final = ROOT / "src/cypshift/chemistry.py"
TOPOLOGY_SOURCE: Final = ROOT / "src/cypshift/openadmet_topology.py"
LOCK: Final = ROOT / "uv.lock"

SOURCE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_x1_synthetic_source.v1"
)
TERMINAL_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_x1_synthetic_terminal.v1"
)
ACCEPTANCE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_x1_synthetic_acceptance.v1"
)
SUCCESS_STATUS: Final = "G2_5B_EXP_X1_SYNTHETIC_COMPILER_ACCEPTED"

DATABASE_NAME: Final = "chembl_37_synthetic.sqlite3"
CHALLENGE_NAME: Final = "challenge_structures.csv"
FOLDS_NAME: Final = "challenge_folds.csv"
SOURCE_MANIFEST_NAME: Final = "manifest.json"

ENDPOINT_TARGETS: Final = {
    "CYP1A2": "CHEMBL3356",
    "CYP2C9": "CHEMBL3397",
    "CYP2D6": "CHEMBL289",
    "CYP3A4": "CHEMBL340",
}
TARGET_ENDPOINTS: Final = {target: endpoint for endpoint, target in ENDPOINT_TARGETS.items()}
ENDPOINTS: Final = tuple(ENDPOINT_TARGETS)
REPEATS: Final = tuple(range(3))
OUTER_FOLDS: Final = tuple(range(5))
INNER_FOLDS: Final = tuple(range(4))

FILTER_REASONS: Final = (
    "TARGET_NOT_SELECTED",
    "STANDARD_TYPE_NOT_IC50",
    "STANDARD_RELATION_NOT_EXACT",
    "STANDARD_UNITS_NOT_NM",
    "STANDARD_VALUE_NOT_FINITE_POSITIVE",
    "PCHEMBL_NOT_FINITE",
    "PCHEMBL_RECOMPUTE_MISMATCH",
    "STANDARD_FLAG_NOT_ONE",
    "POTENTIAL_DUPLICATE_NOT_ZERO",
    "DATA_VALIDITY_COMMENT_PRESENT",
    "ASSAY_CONFIDENCE_BELOW_NINE",
    "ASSAY_ORGANISM_EXPLICITLY_NONHUMAN",
    "STRUCTURE_MISSING_OR_QUARANTINED",
)

REQUIRED_TABLES: Final = {
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
    "target_dictionary": (
        "tid",
        "target_chembl_id",
        "pref_name",
        "organism",
        "tax_id",
        "target_type",
    ),
    "molecule_dictionary": ("molregno", "chembl_id"),
    "compound_structures": (
        "molregno",
        "canonical_smiles",
        "standard_inchi",
        "standard_inchi_key",
    ),
    "docs": ("doc_id", "chembl_id", "year", "doi", "src_id"),
    "source": ("src_id", "src_description"),
}

RAW_COLUMNS: Final = (
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
    "assay_chembl_id",
    "assay_type",
    "assay_organism",
    "assay_tax_id",
    "assay_description",
    "confidence_score",
    "target_chembl_id",
    "target_pref_name",
    "target_organism",
    "target_tax_id",
    "target_type",
    "molecule_chembl_id",
    "canonical_smiles",
    "standard_inchi",
    "standard_inchi_key",
    "doc_chembl_id",
    "doc_year",
    "doc_doi",
    "src_id",
    "src_description",
)

ELIGIBLE_COLUMNS: Final = (
    "activity_id",
    "endpoint",
    "molregno",
    "molecule_chembl_id",
    "standardized_smiles",
    "standardized_structure_hash",
    "equivalence_key",
    "derived_pic50",
    "pchembl_value",
    "assay_chembl_id",
    "doc_chembl_id",
)
IDENTITY_COLUMNS: Final = (
    "source_kind",
    "source_id",
    "raw_smiles",
    "standardized_smiles",
    "standardized_structure_hash",
    "equivalence_key",
    "challenge_component",
    "confirmatory",
)
CHALLENGE_COLUMNS: Final = (
    "molecule_id",
    "raw_smiles",
    "challenge_component",
    "confirmatory",
)
FOLD_COLUMNS: Final = (
    "molecule_id",
    "repeat",
    "outer_context",
    "assigned_outer",
    "inner_fold",
)
SUPPORT_COLUMNS: Final = (
    "scope",
    "endpoint",
    "repeat",
    "outer_fold",
    "inner_fold",
    "safe_molecules",
    "safe_components",
    "safe_activity_rows",
)

TERMINAL_NAMES: Final = (
    "x1_synthetic_filter_counts.json",
    "x1_synthetic_chemistry_counts.json",
    "x1_synthetic_union_counts.json",
    "x1_synthetic_cell_support.csv",
    "x1_synthetic_support_decisions.json",
    "x1_synthetic_result.json",
    "manifest.json",
)
PRIVATE_NAMES: Final = (
    "raw_source_rows.jsonl",
    "eligible_activities.csv",
    "external_identities.csv",
    "union_nodes.csv",
    "union_edges.csv",
    "cell_safe_external_identities.csv",
)

COMPONENT_SPEC: Final = (
    "x1_union_component_v1|rdkit-cleanup-fragment-parent-v1|"
    "rdkit-standard-inchi-connectivity-block-v1|"
    "morgan_ecfp4_radius=2;fp_size=4096;include_chirality=true;"
    "tanimoto_inclusive_threshold=0.60"
)

OFFICIAL_ZERO_FIELDS: Final = (
    "new_external_records_opened",
    "external_dataset_files_downloaded",
    "official_target_values_opened",
    "official_features_opened",
    "official_structures_opened",
    "official_model_fits",
    "official_predictions_generated",
    "development_metric_evaluations",
    "confirmatory_truth_values_opened",
    "historical_row_level_artifacts_opened",
    "blinded_test_rows_opened",
    "tdi_rows_opened",
    "submission_rows_generated",
    "official_metric_calls",
    "leaderboard_observations_used_for_selection",
    "live_uploads",
    "execution_claims_created_or_consumed",
)


class X1SyntheticError(RuntimeError):
    """A source, filter, topology, support, or publication invariant failed."""


@dataclass(frozen=True, slots=True)
class StructureIdentity:
    source_kind: str
    source_id: str
    raw_smiles: str
    standardized_smiles: str
    structure_hash: str
    equivalence_key: str
    challenge_component: str | None
    confirmatory: bool


@dataclass(frozen=True, slots=True)
class Compilation:
    raw_rows: tuple[dict[str, Any], ...]
    eligible_rows: tuple[dict[str, str], ...]
    external_identities: tuple[StructureIdentity, ...]
    challenge_identities: tuple[StructureIdentity, ...]
    folds: tuple[dict[str, str], ...]
    filter_counts: dict[str, Any]
    chemistry_counts: dict[str, Any]
    union_counts: dict[str, Any]
    support_rows: tuple[dict[str, str], ...]
    support_decisions: dict[str, Any]
    logical_source_sha256: str
    component_by_hash: dict[str, str]
    global_forbidden_hashes: frozenset[str]
    private_files: dict[str, bytes]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X1SyntheticError(message)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise X1SyntheticError(f"cannot hash {path}: {exc}") from exc


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def json_bytes(value: object) -> bytes:
    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise X1SyntheticError("noncanonical JSON value") from exc
    return (serialized + "\n").encode("utf-8")


def csv_bytes(
    columns: Sequence[str], rows: Iterable[Mapping[str, object]]
) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=list(columns),
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise X1SyntheticError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_json_pairs
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise X1SyntheticError(f"cannot read JSON {path}: {exc}") from exc
    _require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def read_csv(path: Path, columns: Sequence[str]) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            _require(tuple(reader.fieldnames or ()) == tuple(columns), f"{path.name} columns differ")
            rows: list[dict[str, str]] = []
            for line, row in enumerate(reader, start=2):
                _require(None not in row, f"{path.name} row {line} has extra fields")
                _require(
                    all(value is not None for value in row.values()),
                    f"{path.name} row {line} has missing fields",
                )
                rows.append(cast(dict[str, str], row))
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise X1SyntheticError(f"cannot read CSV {path}: {exc}") from exc
    return rows


def _regular_readonly(path: Path, label: str) -> Path:
    _require(path.is_file() and not path.is_symlink(), f"{label} is not regular")
    mode = path.stat().st_mode
    _require(not bool(mode & 0o222), f"{label} is writable")
    _require(path.stat().st_nlink == 1, f"{label} hard-link count differs")
    return path


def _readonly_root(path: Path, label: str) -> Path:
    _require(path.is_dir() and not path.is_symlink(), f"{label} is not a directory")
    _require(not bool(path.stat().st_mode & 0o222), f"{label} is writable")
    for child in path.rglob("*"):
        _require(not child.is_symlink(), f"{label} contains a symlink")
    return path


def seal_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        os.chmod(path, 0o555 if path.is_dir() else 0o444)
    os.chmod(root, 0o555)


def make_writable(root: Path) -> None:
    if not root.exists() or root.is_symlink():
        return
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts)):
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    os.chmod(root, 0o755)


def cleanup(root: Path) -> None:
    if not root.exists() and not root.is_symlink():
        return
    _require(not root.is_symlink(), "cleanup root is a symlink")
    make_writable(root)
    shutil.rmtree(root)


def publish_files(destination: Path, files: Mapping[str, bytes]) -> Path:
    _require(not destination.exists() and not destination.is_symlink(), "destination exists")
    _require(bool(files), "publication is empty")
    destination.mkdir(parents=True)
    try:
        for name in sorted(files):
            _require(Path(name).name == name and name not in {".", ".."}, "unsafe output name")
            path = destination / name
            with path.open("xb") as handle:
                handle.write(files[name])
                handle.flush()
                os.fsync(handle.fileno())
        seal_tree(destination)
    except Exception:
        cleanup(destination)
        raise
    return destination


def relative_byte_map(root: Path) -> dict[str, str]:
    _readonly_root(root, "terminal root")
    values: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            values[path.relative_to(root).as_posix()] = sha256_path(path)
    return values


def static_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    _require(sha256_path(CONTRACT) == CONTRACT_SHA256, "G2-5B contract hash differs")
    _require(sha256_path(PARENT) == PARENT_SHA256, "G2-5A parent hash differs")
    contract = read_json(CONTRACT)
    parent = read_json(PARENT)
    _require(contract.get("parent", {}).get("sha256") == PARENT_SHA256, "parent binding differs")
    _require(STANDARDIZATION_VERSION == "rdkit-cleanup-fragment-parent-v1", "standardization differs")
    _require(rdBase.rdkitVersion == "2026.03.5", "RDKit runtime differs")
    _require(
        topology.MORGAN_RADIUS == 2
        and topology.MORGAN_FP_SIZE == 4096
        and topology.MORGAN_INCLUDE_CHIRALITY is True
        and topology.SIMILARITY_THRESHOLD == 0.60,
        "D-032 similarity runtime differs",
    )
    return contract, parent


def _typed_raw(value: object) -> dict[str, object]:
    if value is None:
        return {"type": "null", "value": None}
    if type(value) is int:
        return {"type": "integer", "value": value}
    if type(value) is float:
        if math.isnan(cast(float, value)):
            text = "NaN"
        elif math.isinf(cast(float, value)):
            text = "Infinity" if cast(float, value) > 0 else "-Infinity"
        else:
            text = format(cast(float, value), ".17g")
        return {"type": "real", "value": text}
    if type(value) is str:
        return {"type": "text", "value": value}
    raise X1SyntheticError(f"unsupported SQLite value type: {type(value).__name__}")


def _raw_jsonl(rows: Sequence[Mapping[str, Any]]) -> bytes:
    lines = []
    for row in rows:
        value = {name: _typed_raw(row[name]) for name in RAW_COLUMNS}
        lines.append(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _source_manifest(source_root: Path) -> dict[str, Any]:
    _readonly_root(source_root, "source root")
    expected = {DATABASE_NAME, CHALLENGE_NAME, FOLDS_NAME, SOURCE_MANIFEST_NAME}
    names = {path.name for path in source_root.iterdir()}
    _require(names == expected, "source root file set differs")
    manifest_path = _regular_readonly(source_root / SOURCE_MANIFEST_NAME, "source manifest")
    manifest = read_json(manifest_path)
    _require(manifest.get("schema_version") == SOURCE_SCHEMA, "source schema differs")
    _require(manifest.get("synthetic") is True, "source is not synthetic")
    receipts = manifest.get("source_receipts")
    _require(isinstance(receipts, dict) and set(receipts) == expected - {SOURCE_MANIFEST_NAME}, "source receipts differ")
    for name in sorted(receipts):
        path = _regular_readonly(source_root / name, f"source {name}")
        _require(sha256_path(path) == receipts[name], f"source hash differs: {name}")
    return manifest


def _schema_preflight(connection: sqlite3.Connection) -> None:
    table_rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    available = {cast(str, row[0]) for row in table_rows}
    _require(set(REQUIRED_TABLES) <= available, "required SQLite table missing")
    for table, required in REQUIRED_TABLES.items():
        columns = {
            cast(str, row[1]): cast(int, row[5])
            for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        }
        _require(set(required) <= set(columns), f"required SQLite column missing: {table}")
        primary = [name for name, position in columns.items() if position]
        _require(
            primary == [required[0]] and columns[required[0]] == 1,
            f"primary join identity differs: {table}",
        )
    targets = connection.execute(
        "SELECT target_chembl_id, organism, tax_id, target_type "
        "FROM target_dictionary WHERE target_chembl_id IN (?, ?, ?, ?) "
        "ORDER BY target_chembl_id",
        tuple(sorted(TARGET_ENDPOINTS)),
    ).fetchall()
    _require(len(targets) == 4, "selected target metadata cardinality differs")
    _require(
        all(row[1:] == ("Homo sapiens", 9606, "SINGLE PROTEIN") for row in targets),
        "selected target metadata differs",
    )


SOURCE_QUERY: Final = """
SELECT
  a.activity_id AS activity_id,
  a.assay_id AS assay_id,
  a.molregno AS molregno,
  a.standard_type AS standard_type,
  a.standard_relation AS standard_relation,
  a.standard_value AS standard_value,
  a.standard_units AS standard_units,
  a.pchembl_value AS pchembl_value,
  a.standard_flag AS standard_flag,
  a.potential_duplicate AS potential_duplicate,
  a.data_validity_comment AS data_validity_comment,
  a.activity_comment AS activity_comment,
  s.assay_chembl_id AS assay_chembl_id,
  s.assay_type AS assay_type,
  s.assay_organism AS assay_organism,
  s.assay_tax_id AS assay_tax_id,
  s.description AS assay_description,
  s.confidence_score AS confidence_score,
  t.target_chembl_id AS target_chembl_id,
  t.pref_name AS target_pref_name,
  t.organism AS target_organism,
  t.tax_id AS target_tax_id,
  t.target_type AS target_type,
  m.chembl_id AS molecule_chembl_id,
  c.canonical_smiles AS canonical_smiles,
  c.standard_inchi AS standard_inchi,
  c.standard_inchi_key AS standard_inchi_key,
  d.chembl_id AS doc_chembl_id,
  d.year AS doc_year,
  d.doi AS doc_doi,
  z.src_id AS src_id,
  z.src_description AS src_description
FROM activities AS a
JOIN assays AS s ON a.assay_id = s.assay_id
JOIN target_dictionary AS t ON s.tid = t.tid
JOIN molecule_dictionary AS m ON a.molregno = m.molregno
JOIN compound_structures AS c ON a.molregno = c.molregno
JOIN docs AS d ON s.doc_id = d.doc_id
JOIN source AS z ON d.src_id = z.src_id
ORDER BY t.target_chembl_id, a.activity_id, a.assay_id, a.molregno, m.chembl_id
"""


def read_sqlite_rows(path: Path) -> list[dict[str, Any]]:
    _regular_readonly(path, "SQLite source")
    for suffix in ("-wal", "-shm", "-journal"):
        _require(not Path(f"{path}{suffix}").exists(), f"SQLite companion exists: {suffix}")
    uri = f"file:{quote(str(path.resolve(strict=True)))}?mode=ro&immutable=1"
    try:
        connection = sqlite3.connect(uri, uri=True)
        connection.enable_load_extension(False)
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA temp_store=MEMORY")
        integrity = connection.execute("PRAGMA integrity_check").fetchall()
        _require(integrity == [("ok",)], "SQLite integrity check failed")
        databases = connection.execute("PRAGMA database_list").fetchall()
        _require(
            databases[0][1] == "main"
            and all(row[1] in {"main", "temp"} for row in databases)
            and all(row[2] == "" for row in databases if row[1] == "temp"),
            "attached database differs",
        )
        _schema_preflight(connection)
        source_count = cast(int, connection.execute("SELECT COUNT(*) FROM activities").fetchone()[0])
        cursor = connection.execute(SOURCE_QUERY)
        columns = tuple(item[0] for item in cursor.description or ())
        _require(columns == RAW_COLUMNS, "joined source columns differ")
        values = cursor.fetchall()
        _require(len(values) == source_count, "joined source row count differs")
    except (sqlite3.Error, OSError) as exc:
        raise X1SyntheticError(f"SQLite preflight or query failed: {exc}") from exc
    finally:
        if "connection" in locals():
            connection.close()
    rows = [dict(zip(RAW_COLUMNS, values, strict=True)) for values in values]
    activity_ids = [row["activity_id"] for row in rows]
    _require(len(set(activity_ids)) == len(activity_ids), "duplicate joined activity identity")
    return rows


def _structure_identity(source_kind: str, source_id: str, raw_smiles: object, challenge_component: str | None = None, confirmatory: bool = False) -> StructureIdentity | None:
    if not isinstance(raw_smiles, str) or not raw_smiles:
        return None
    record = standardize_molecule(
        MoleculeInput(
            molecule_id=source_id,
            structure=raw_smiles,
            structure_format="smiles",
            source=source_kind,
            provenance=json.dumps({"source_id": source_id}, sort_keys=True),
        )
    )
    if record.status is not MoleculeStatus.ACCEPTED:
        return None
    standardized = cast(str, record.standardized_structure)
    structure_hash = cast(str, record.standardized_structure_hash)
    molecule = Chem.MolFromSmiles(standardized)
    if molecule is None:
        return None
    key = inchi.MolToInchiKey(molecule)
    if len(key) < 15 or not key[:14].isalpha() or key[:14] != key[:14].upper():
        return None
    return StructureIdentity(
        source_kind=source_kind,
        source_id=source_id,
        raw_smiles=raw_smiles,
        standardized_smiles=standardized,
        structure_hash=structure_hash,
        equivalence_key=key[:14],
        challenge_component=challenge_component,
        confirmatory=confirmatory,
    )


def _numeric(value: object) -> float | None:
    if type(value) not in {int, float}:
        return None
    result = float(cast(int | float, value))
    return result if math.isfinite(result) else None


def _filter_reason(row: Mapping[str, Any], identity: StructureIdentity | None) -> tuple[str | None, float | None]:
    if row["target_chembl_id"] not in TARGET_ENDPOINTS:
        return FILTER_REASONS[0], None
    if row["standard_type"] != "IC50":
        return FILTER_REASONS[1], None
    if row["standard_relation"] != "=":
        return FILTER_REASONS[2], None
    if row["standard_units"] != "nM":
        return FILTER_REASONS[3], None
    standard = _numeric(row["standard_value"])
    if standard is None or standard <= 0:
        return FILTER_REASONS[4], None
    pchembl = _numeric(row["pchembl_value"])
    if pchembl is None:
        return FILTER_REASONS[5], None
    derived = 9.0 - math.log10(standard)
    if abs(derived - pchembl) > 0.011:
        return FILTER_REASONS[6], None
    if type(row["standard_flag"]) is not int or row["standard_flag"] != 1:
        return FILTER_REASONS[7], None
    if type(row["potential_duplicate"]) is not int or row["potential_duplicate"] != 0:
        return FILTER_REASONS[8], None
    if row["data_validity_comment"] is not None:
        return FILTER_REASONS[9], None
    confidence = _numeric(row["confidence_score"])
    if confidence is None or confidence < 9:
        return FILTER_REASONS[10], None
    organism = row["assay_organism"]
    tax_id = row["assay_tax_id"]
    if not ((organism is None and tax_id is None) or (organism == "Homo sapiens" and tax_id == 9606)):
        return FILTER_REASONS[11], None
    if identity is None:
        return FILTER_REASONS[12], None
    return None, derived


def filter_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, str]], list[StructureIdentity], dict[str, Any]]:
    cache: dict[int, StructureIdentity | None] = {}
    eligible: list[dict[str, str]] = []
    identities: dict[str, StructureIdentity] = {}
    reason_counts: Counter[str] = Counter()
    reason_endpoint_counts: Counter[tuple[str, str]] = Counter()
    endpoint_counts: Counter[str] = Counter()
    states: list[dict[str, object]] = []
    for row in rows:
        molregno = row["molregno"]
        _require(type(molregno) is int, "molregno type differs")
        if molregno not in cache:
            cache[molregno] = _structure_identity(
                "external",
                cast(str, row["molecule_chembl_id"]),
                row["canonical_smiles"],
            )
        identity = cache[molregno]
        reason, derived = _filter_reason(row, identity)
        if reason is not None:
            reason_counts[reason] += 1
            reason_endpoint_counts[
                (TARGET_ENDPOINTS.get(cast(str, row["target_chembl_id"]), "UNSELECTED"), reason)
            ] += 1
            states.append({"activity_id": row["activity_id"], "state": reason})
            continue
        _require(identity is not None and derived is not None, "eligible identity missing")
        endpoint = TARGET_ENDPOINTS[cast(str, row["target_chembl_id"])]
        eligible_row = {
            "activity_id": str(row["activity_id"]),
            "endpoint": endpoint,
            "molregno": str(molregno),
            "molecule_chembl_id": cast(str, row["molecule_chembl_id"]),
            "standardized_smiles": identity.standardized_smiles,
            "standardized_structure_hash": identity.structure_hash,
            "equivalence_key": identity.equivalence_key,
            "derived_pic50": format(derived, ".17g"),
            "pchembl_value": format(cast(float, _numeric(row["pchembl_value"])), ".17g"),
            "assay_chembl_id": cast(str, row["assay_chembl_id"]),
            "doc_chembl_id": cast(str, row["doc_chembl_id"]),
        }
        eligible.append(eligible_row)
        identities.setdefault(identity.source_id, identity)
        _require(identities[identity.source_id] == identity, "external identity drift")
        endpoint_counts[endpoint] += 1
        states.append({"activity_id": row["activity_id"], "state": "ELIGIBLE"})
    eligible.sort(key=lambda row: (row["endpoint"], int(row["activity_id"])))
    values = sorted(identities.values(), key=lambda item: item.source_id)
    _require(len(states) == len(rows), "filter state accounting differs")
    counts = {
        "joined_rows": len(rows),
        "eligible_rows": len(eligible),
        "ineligible_rows": len(rows) - len(eligible),
        "reason_counts": {reason: reason_counts[reason] for reason in FILTER_REASONS},
        "reason_counts_by_endpoint": {
            endpoint: {
                reason: reason_endpoint_counts[(endpoint, reason)]
                for reason in FILTER_REASONS
            }
            for endpoint in (*ENDPOINTS, "UNSELECTED")
        },
        "eligible_rows_by_endpoint": {endpoint: endpoint_counts[endpoint] for endpoint in ENDPOINTS},
        "state_sha256": sha256_bytes(json_bytes(sorted(states, key=lambda item: cast(int, item["activity_id"])))),
    }
    _require(counts["eligible_rows"] + counts["ineligible_rows"] == counts["joined_rows"], "filter total differs")
    return eligible, values, counts


def _challenge_inputs(source_root: Path) -> tuple[list[StructureIdentity], list[dict[str, str]]]:
    challenge_rows = read_csv(source_root / CHALLENGE_NAME, CHALLENGE_COLUMNS)
    fold_rows = read_csv(source_root / FOLDS_NAME, FOLD_COLUMNS)
    _require(len(challenge_rows) == 40, "challenge molecule count differs")
    identities: list[StructureIdentity] = []
    components: Counter[str] = Counter()
    for row in challenge_rows:
        _require(row["confirmatory"] in {"0", "1"}, "confirmatory marker differs")
        identity = _structure_identity(
            "challenge",
            row["molecule_id"],
            row["raw_smiles"],
            row["challenge_component"],
            row["confirmatory"] == "1",
        )
        _require(identity is not None, "challenge structure quarantined")
        identities.append(identity)
        components[row["challenge_component"]] += 1
    _require(len(components) == 20 and set(components.values()) == {2}, "challenge component shape differs")
    confirmatory_components = {
        cast(str, item.challenge_component) for item in identities if item.confirmatory
    }
    _require(len(confirmatory_components) == 4, "confirmatory component count differs")
    by_molecule = {item.source_id: item for item in identities}
    _require(len(by_molecule) == len(identities), "duplicate challenge identity")
    _require(len(fold_rows) == 40 * 3 * 5, "fold row count differs")
    seen: set[tuple[str, int, int]] = set()
    for row in fold_rows:
        _require(row["molecule_id"] in by_molecule, "fold molecule unknown")
        repeat = _parse_index(row["repeat"], 3, "repeat")
        outer_context = _parse_index(row["outer_context"], 5, "outer context")
        assigned_outer = _parse_index(row["assigned_outer"], 5, "assigned outer")
        key = (row["molecule_id"], repeat, outer_context)
        _require(key not in seen, "duplicate fold identity")
        seen.add(key)
        if assigned_outer == outer_context:
            _require(row["inner_fold"] == "", "outer validation has inner fold")
        else:
            _parse_index(row["inner_fold"], 4, "inner fold")
    _validate_fold_families(identities, fold_rows)
    identities.sort(key=lambda item: item.source_id)
    fold_rows.sort(key=lambda row: (row["molecule_id"], int(row["repeat"]), int(row["outer_context"])))
    return identities, fold_rows


def _parse_index(value: str, size: int, label: str) -> int:
    _require(value.isdigit(), f"{label} is not an integer")
    result = int(value)
    _require(0 <= result < size, f"{label} out of range")
    return result


def _validate_fold_families(identities: Sequence[StructureIdentity], folds: Sequence[Mapping[str, str]]) -> None:
    component_by_molecule = {item.source_id: cast(str, item.challenge_component) for item in identities}
    for repeat in REPEATS:
        assignments: dict[str, set[int]] = defaultdict(set)
        for row in folds:
            if int(row["repeat"]) == repeat:
                assignments[component_by_molecule[row["molecule_id"]]].add(int(row["assigned_outer"]))
        _require(all(len(values) == 1 for values in assignments.values()), "component crosses outer boundary")
        counts = Counter(next(iter(values)) for values in assignments.values())
        _require(counts == Counter({fold: 4 for fold in OUTER_FOLDS}), "outer component balance differs")
        for outer in OUTER_FOLDS:
            inner: dict[str, set[int]] = defaultdict(set)
            for row in folds:
                if int(row["repeat"]) != repeat or int(row["outer_context"]) != outer or row["inner_fold"] == "":
                    continue
                inner[component_by_molecule[row["molecule_id"]]].add(int(row["inner_fold"]))
            _require(len(inner) == 16 and all(len(values) == 1 for values in inner.values()), "component crosses inner boundary")
            inner_counts = Counter(next(iter(values)) for values in inner.values())
            _require(inner_counts == Counter({fold: 4 for fold in INNER_FOLDS}), "inner component balance differs")


def _identity_rows(identities: Sequence[StructureIdentity]) -> list[dict[str, str]]:
    return [
        {
            "source_kind": item.source_kind,
            "source_id": item.source_id,
            "raw_smiles": item.raw_smiles,
            "standardized_smiles": item.standardized_smiles,
            "standardized_structure_hash": item.structure_hash,
            "equivalence_key": item.equivalence_key,
            "challenge_component": item.challenge_component or "",
            "confirmatory": "1" if item.confirmatory else "0",
        }
        for item in sorted(identities, key=lambda value: (value.source_kind, value.source_id))
    ]


def build_union(
    external: Sequence[StructureIdentity], challenge: Sequence[StructureIdentity]
) -> tuple[dict[str, str], frozenset[str], dict[str, Any], bytes, bytes]:
    structure_map: dict[str, str] = {}
    memberships: dict[str, set[str]] = defaultdict(set)
    equivalence_by_hash: dict[str, str] = {}
    for item in [*challenge, *external]:
        previous = structure_map.setdefault(item.structure_hash, item.standardized_smiles)
        _require(previous == item.standardized_smiles, "structure hash collision")
        memberships[item.structure_hash].add(item.source_kind)
        previous_key = equivalence_by_hash.setdefault(item.structure_hash, item.equivalence_key)
        _require(previous_key == item.equivalence_key, "equivalence key drift")
    hashes = sorted(structure_map)
    parent = {value: value for value in hashes}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=topology.MORGAN_RADIUS,
        fpSize=topology.MORGAN_FP_SIZE,
        includeChirality=topology.MORGAN_INCLUDE_CHIRALITY,
    )
    fingerprints = []
    with rdBase.BlockLogs():
        for structure_hash in hashes:
            molecule = Chem.MolFromSmiles(structure_map[structure_hash])
            _require(molecule is not None, "accepted union structure is invalid")
            fingerprints.append(generator.GetFingerprint(molecule))
    pair_count = len(hashes) * (len(hashes) - 1) // 2
    similarity_edges = 0
    edge_rows: list[dict[str, str]] = []
    for index, fingerprint in enumerate(fingerprints[:-1]):
        similarities = DataStructs.BulkTanimotoSimilarity(
            fingerprint, fingerprints[index + 1 :]
        )
        _require(
            len(similarities) == len(fingerprints) - index - 1,
            "similarity result count differs",
        )
        for offset, similarity in enumerate(similarities, start=index + 1):
            if similarity >= topology.SIMILARITY_THRESHOLD:
                similarity_edges += 1
                union(hashes[index], hashes[offset])
                edge_rows.append(
                    {
                        "edge_kind": "D032_SIMILARITY",
                        "left_hash": hashes[index],
                        "right_hash": hashes[offset],
                    }
                )
    similarity_component_count = len({find(value) for value in hashes})
    by_equivalence: dict[str, list[str]] = defaultdict(list)
    for structure_hash, key in equivalence_by_hash.items():
        by_equivalence[key].append(structure_hash)
    equivalence_edges = 0
    for members in by_equivalence.values():
        members.sort()
        for member in members[1:]:
            union(members[0], member)
            equivalence_edges += 1
            edge_rows.append({"edge_kind": "INCHI_CONNECTIVITY", "left_hash": members[0], "right_hash": member})
    grouped: dict[str, list[str]] = defaultdict(list)
    for structure_hash in hashes:
        grouped[find(structure_hash)].append(structure_hash)
    component_by_hash: dict[str, str] = {}
    for members in grouped.values():
        members.sort()
        component = _sha_text(COMPONENT_SPEC + "\n" + "\n".join(members))
        for structure_hash in members:
            component_by_hash[structure_hash] = component
    challenge_hashes = {item.structure_hash for item in challenge}
    challenge_keys = {item.equivalence_key for item in challenge}
    exact = {item.structure_hash for item in external if item.structure_hash in challenge_hashes}
    equivalent = {
        item.structure_hash
        for item in external
        if item.structure_hash not in exact and item.equivalence_key in challenge_keys
    }
    forbidden = frozenset(exact | equivalent)
    challenge_components: dict[str, set[str]] = defaultdict(set)
    for item in challenge:
        challenge_components[cast(str, item.challenge_component)].add(component_by_hash[item.structure_hash])
    _require(all(len(values) == 1 for values in challenge_components.values()), "challenge component is not contained")
    reverse_challenge: dict[str, set[str]] = defaultdict(set)
    for challenge_component, values in challenge_components.items():
        reverse_challenge[next(iter(values))].add(challenge_component)
    _require(all(len(values) == 1 for values in reverse_challenge.values()), "union graph merged challenge components")
    node_rows = [
        {
            "standardized_structure_hash": structure_hash,
            "standardized_smiles": structure_map[structure_hash],
            "equivalence_key": equivalence_by_hash[structure_hash],
            "source_membership": "+".join(sorted(memberships[structure_hash])),
            "union_component_hash": component_by_hash[structure_hash],
            "globally_forbidden_external": "1" if structure_hash in forbidden else "0",
        }
        for structure_hash in hashes
    ]
    edge_rows.sort(key=lambda row: (row["edge_kind"], row["left_hash"], row["right_hash"]))
    counts = {
        "union_unique_structure_nodes": len(hashes),
        "pairwise_similarity_comparisons": pair_count,
        "qualifying_similarity_edges": similarity_edges,
        "d032_similarity_components": similarity_component_count,
        "equivalence_spanning_edges": equivalence_edges,
        "union_components": len(set(component_by_hash.values())),
        "global_exact_forbidden_structures": len(exact),
        "global_equivalent_forbidden_structures": len(equivalent),
        "global_forbidden_structures": len(forbidden),
    }
    node_columns = (
        "standardized_structure_hash",
        "standardized_smiles",
        "equivalence_key",
        "source_membership",
        "union_component_hash",
        "globally_forbidden_external",
    )
    edge_columns = ("edge_kind", "left_hash", "right_hash")
    return component_by_hash, forbidden, counts, csv_bytes(node_columns, node_rows), csv_bytes(edge_columns, edge_rows)


def support_rows(
    eligible: Sequence[Mapping[str, str]],
    external: Sequence[StructureIdentity],
    challenge: Sequence[StructureIdentity],
    folds: Sequence[Mapping[str, str]],
    component_by_hash: Mapping[str, str],
    forbidden: frozenset[str],
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    hashes_by_endpoint: dict[str, set[str]] = defaultdict(set)
    activity_count: Counter[tuple[str, str]] = Counter()
    for row in eligible:
        hashes_by_endpoint[row["endpoint"]].add(row["standardized_structure_hash"])
        activity_count[(row["endpoint"], row["standardized_structure_hash"])] += 1
    external_hashes = {item.structure_hash for item in external}
    novel_by_endpoint = {
        endpoint: hashes_by_endpoint[endpoint] & external_hashes - forbidden
        for endpoint in ENDPOINTS
    }
    fold_index = {
        (row["molecule_id"], int(row["repeat"]), int(row["outer_context"])): row
        for row in folds
    }
    rows: list[dict[str, str]] = []
    safe_identity_rows: list[dict[str, str]] = []

    def add_row(scope: str, endpoint: str, repeat: int | None, outer: int | None, inner: int | None, touched: set[str]) -> None:
        safe = sorted(
            structure_hash
            for structure_hash in novel_by_endpoint[endpoint]
            if component_by_hash[structure_hash] not in touched
        )
        components = {component_by_hash[value] for value in safe}
        activities = sum(activity_count[(endpoint, value)] for value in safe)
        rows.append(
            {
                "scope": scope,
                "endpoint": endpoint,
                "repeat": "" if repeat is None else str(repeat),
                "outer_fold": "" if outer is None else str(outer),
                "inner_fold": "" if inner is None else str(inner),
                "safe_molecules": str(len(safe)),
                "safe_components": str(len(components)),
                "safe_activity_rows": str(activities),
            }
        )
        for structure_hash in safe:
            safe_identity_rows.append(
                {
                    "scope": scope,
                    "endpoint": endpoint,
                    "repeat": "" if repeat is None else str(repeat),
                    "outer_fold": "" if outer is None else str(outer),
                    "inner_fold": "" if inner is None else str(inner),
                    "standardized_structure_hash": structure_hash,
                    "union_component_hash": component_by_hash[structure_hash],
                }
            )

    for repeat in REPEATS:
        for outer in OUTER_FOLDS:
            outer_heldout = {
                component_by_hash[item.structure_hash]
                for item in challenge
                if int(fold_index[(item.source_id, repeat, outer)]["assigned_outer"]) == outer
            }
            for endpoint in ENDPOINTS:
                add_row("OUTER", endpoint, repeat, outer, None, outer_heldout)
            for inner in INNER_FOLDS:
                inner_heldout = {
                    component_by_hash[item.structure_hash]
                    for item in challenge
                    if fold_index[(item.source_id, repeat, outer)]["inner_fold"] == str(inner)
                }
                touched = outer_heldout | inner_heldout
                for endpoint in ENDPOINTS:
                    add_row("INNER", endpoint, repeat, outer, inner, touched)
    confirmatory_touched = {
        component_by_hash[item.structure_hash] for item in challenge if item.confirmatory
    }
    for endpoint in ENDPOINTS:
        add_row("CONFIRMATORY", endpoint, None, None, None, confirmatory_touched)
    rows.sort(key=lambda row: (row["scope"], row["endpoint"], row["repeat"], row["outer_fold"], row["inner_fold"]))
    safe_identity_rows.sort(
        key=lambda row: (
            row["scope"],
            row["endpoint"],
            row["repeat"],
            row["outer_fold"],
            row["inner_fold"],
            row["standardized_structure_hash"],
            row["union_component_hash"],
        )
    )
    outer_rows = [row for row in rows if row["scope"] == "OUTER"]
    miniature_pass = all(len(novel_by_endpoint[endpoint]) >= 50 for endpoint in ENDPOINTS) and all(int(row["safe_components"]) >= 35 for row in outer_rows)
    official_pass = all(len(novel_by_endpoint[endpoint]) >= 1000 for endpoint in ENDPOINTS) and all(int(row["safe_components"]) >= 750 for row in outer_rows)
    decisions = {
        "novel_molecules_by_endpoint": {endpoint: len(novel_by_endpoint[endpoint]) for endpoint in ENDPOINTS},
        "miniature_thresholds": {"minimum_novel_molecules": 50, "minimum_outer_safe_components": 35, "pass": miniature_pass},
        "official_thresholds": {"minimum_novel_molecules": 1000, "minimum_outer_safe_components": 750, "pass": official_pass},
        "scientific_interpretation": "Synthetic support mechanics only; the official support decision is expected to fail.",
    }
    return rows, safe_identity_rows, decisions


def compile_source(source_root: Path, private_root: Path) -> Compilation:
    static_contract()
    _require(not private_root.exists() and not private_root.is_symlink(), "private root exists")
    manifest = _source_manifest(source_root)
    rows = read_sqlite_rows(source_root / DATABASE_NAME)
    eligible, external, filter_counts = filter_rows(rows)
    challenge, folds = _challenge_inputs(source_root)
    component_by_hash, forbidden, union_counts, node_bytes, edge_bytes = build_union(external, challenge)
    support, safe_identities, decisions = support_rows(eligible, external, challenge, folds, component_by_hash, forbidden)
    raw_bytes = _raw_jsonl(rows)
    challenge_bytes = csv_bytes(CHALLENGE_COLUMNS, [
        {
            "molecule_id": item.source_id,
            "raw_smiles": item.raw_smiles,
            "challenge_component": cast(str, item.challenge_component),
            "confirmatory": "1" if item.confirmatory else "0",
        }
        for item in challenge
    ])
    fold_bytes = csv_bytes(FOLD_COLUMNS, folds)
    logical_source = sha256_bytes(
        json_bytes(
            {
                "semantic_source_id": manifest["semantic_source_id"],
                "raw_source_rows_sha256": sha256_bytes(raw_bytes),
                "challenge_rows_sha256": sha256_bytes(challenge_bytes),
                "fold_rows_sha256": sha256_bytes(fold_bytes),
            }
        )
    )
    chemistry_counts = {
        "eligible_external_compounds": len(external),
        "eligible_external_standardized_structures": len({item.structure_hash for item in external}),
        "challenge_molecules": len(challenge),
        "challenge_components": len({item.challenge_component for item in challenge}),
        "standardization_version": STANDARDIZATION_VERSION,
        "rdkit_version": rdBase.rdkitVersion,
        "equivalence_policy": "rdkit-standard-inchi-connectivity-block-v1",
    }
    identity_bytes = csv_bytes(IDENTITY_COLUMNS, _identity_rows(external))
    safe_columns = (
        "scope",
        "endpoint",
        "repeat",
        "outer_fold",
        "inner_fold",
        "standardized_structure_hash",
        "union_component_hash",
    )
    private_files = {
        "raw_source_rows.jsonl": raw_bytes,
        "eligible_activities.csv": csv_bytes(ELIGIBLE_COLUMNS, eligible),
        "external_identities.csv": identity_bytes,
        "union_nodes.csv": node_bytes,
        "union_edges.csv": edge_bytes,
        "cell_safe_external_identities.csv": csv_bytes(safe_columns, safe_identities),
    }
    publish_files(private_root, private_files)
    return Compilation(
        raw_rows=tuple(dict(row) for row in rows),
        eligible_rows=tuple(eligible),
        external_identities=tuple(external),
        challenge_identities=tuple(challenge),
        folds=tuple(folds),
        filter_counts=filter_counts,
        chemistry_counts=chemistry_counts,
        union_counts=union_counts,
        support_rows=tuple(support),
        support_decisions=decisions,
        logical_source_sha256=logical_source,
        component_by_hash=component_by_hash,
        global_forbidden_hashes=forbidden,
        private_files=private_files,
    )


def terminal_files(compilation: Compilation) -> dict[str, bytes]:
    filter_bytes = json_bytes(compilation.filter_counts)
    chemistry_bytes = json_bytes(compilation.chemistry_counts)
    union_bytes = json_bytes(compilation.union_counts)
    support_bytes = csv_bytes(SUPPORT_COLUMNS, compilation.support_rows)
    decisions_bytes = json_bytes(compilation.support_decisions)
    counts = {
        "activity_rows": compilation.filter_counts["joined_rows"],
        "eligible_activity_rows": compilation.filter_counts["eligible_rows"],
        "ineligible_activity_rows": compilation.filter_counts["ineligible_rows"],
        "external_compounds": compilation.chemistry_counts["eligible_external_compounds"],
        "global_forbidden_structures": compilation.union_counts["global_forbidden_structures"],
        "union_nodes": compilation.union_counts["union_unique_structure_nodes"],
        "union_components": compilation.union_counts["union_components"],
        "outer_endpoint_cells": sum(row["scope"] == "OUTER" for row in compilation.support_rows),
        "inner_endpoint_cells": sum(row["scope"] == "INNER" for row in compilation.support_rows),
        "confirmatory_endpoint_cells": sum(row["scope"] == "CONFIRMATORY" for row in compilation.support_rows),
    }
    accounting = {
        "synthetic_sqlite_files_created": 1,
        "synthetic_activity_rows_opened": compilation.filter_counts["joined_rows"],
        "synthetic_union_comparisons": compilation.union_counts["pairwise_similarity_comparisons"],
        "inherited_prefreeze_external_preview_minimum_records": 45,
        **{name: 0 for name in OFFICIAL_ZERO_FIELDS},
    }
    result = {
        "schema_version": "cypshift.openadmet_cyp_2026.global_v2_x1_synthetic_result.v1",
        "status": SUCCESS_STATUS,
        "contract_sha256": CONTRACT_SHA256,
        "logical_source_sha256": compilation.logical_source_sha256,
        "counts": counts,
        "miniature_support_pass": compilation.support_decisions["miniature_thresholds"]["pass"],
        "official_support_pass": compilation.support_decisions["official_thresholds"]["pass"],
        "scientific_interpretation": "Accepted synthetic compiler and leakage mechanics only; no model-quality or acquisition evidence.",
    }
    result_bytes = json_bytes(result)
    files = {
        "x1_synthetic_filter_counts.json": filter_bytes,
        "x1_synthetic_chemistry_counts.json": chemistry_bytes,
        "x1_synthetic_union_counts.json": union_bytes,
        "x1_synthetic_cell_support.csv": support_bytes,
        "x1_synthetic_support_decisions.json": decisions_bytes,
        "x1_synthetic_result.json": result_bytes,
    }
    manifest = {
        "schema_version": TERMINAL_SCHEMA,
        "status": SUCCESS_STATUS,
        "contract_sha256": CONTRACT_SHA256,
        "parent_sha256": PARENT_SHA256,
        "logical_source_sha256": compilation.logical_source_sha256,
        "counts": counts,
        "accounting": accounting,
        "authority": {
            "synthetic_compiler_mechanics": True,
            "external_record_acquisition": False,
            "official_inputs": False,
            "model_fitting": False,
            "prediction_generation": False,
            "metric_evaluation": False,
            "confirmatory_truth": False,
            "blinded_test": False,
            "submission": False,
            "leaderboard_selection": False,
            "upload": False,
            "claim_creation_or_consumption": False,
        },
        "outputs": {name: sha256_bytes(value) for name, value in sorted(files.items())},
        "private_files_retained": 0,
        "deterministic": True,
    }
    files["manifest.json"] = json_bytes(manifest)
    return files


def run_replay(source_root: Path, replay_root: Path) -> Path:
    _require(not replay_root.exists() and not replay_root.is_symlink(), "replay root exists")
    private = replay_root.with_name(f".{replay_root.name}-private")
    _require(not private.exists() and not private.is_symlink(), "private replay root exists")
    try:
        compilation = compile_source(source_root, private)
        files = terminal_files(compilation)
    except Exception:
        cleanup(private)
        raise
    cleanup(private)
    _require(not private.exists(), "private replay cleanup differs")
    return publish_files(replay_root, files)


def acceptance_files(
    terminal_a: Path,
    terminal_b: Path,
    source_a: Path,
    source_b: Path,
    focused_tests_passed: int,
    synthetic_driver: Path,
    focused_tests: Path,
) -> dict[str, bytes]:
    maps = [relative_byte_map(root) for root in (terminal_a, terminal_b)]
    _require(maps[0] == maps[1], "terminal byte maps differ")
    manifests = [read_json(root / "manifest.json") for root in (terminal_a, terminal_b)]
    _require(manifests[0] == manifests[1], "terminal manifests differ")
    manifest = manifests[0]
    _require(manifest.get("status") == SUCCESS_STATUS, "terminal status differs")
    _require(manifest.get("counts") == {
        "activity_rows": 336,
        "eligible_activity_rows": 320,
        "ineligible_activity_rows": 16,
        "external_compounds": 80,
        "global_forbidden_structures": 20,
        "union_nodes": 110,
        "union_components": 40,
        "outer_endpoint_cells": 60,
        "inner_endpoint_cells": 240,
        "confirmatory_endpoint_cells": 4,
    }, "terminal counts differ")
    _require(manifest["accounting"]["synthetic_union_comparisons"] == 5995, "pairwise count differs")
    _require(all(manifest["accounting"][name] == 0 for name in OFFICIAL_ZERO_FIELDS), "official accounting differs")
    source_hashes = [sha256_path(root / DATABASE_NAME) for root in (source_a, source_b)]
    _require(source_hashes[0] != source_hashes[1], "physical SQLite hashes must differ")
    terminal_tree = sha256_bytes(json_bytes(maps[0]))
    aggregate_accounting = {
        "synthetic_sqlite_files_created": 2,
        "synthetic_activity_rows_opened": 672,
        "synthetic_union_comparisons": 11990,
        "inherited_prefreeze_external_preview_minimum_records": 45,
        **{name: 0 for name in OFFICIAL_ZERO_FIELDS},
    }
    value = {
        "schema_version": ACCEPTANCE_SCHEMA,
        "status": SUCCESS_STATUS,
        "contract_sha256": CONTRACT_SHA256,
        "parent_sha256": PARENT_SHA256,
        "base_commit": "1c05dddd4ec7cf4bf3bf844d43e198f1d0fc9764",
        "source_bindings": {
            "compiler_sha256": sha256_path(SCRIPT),
            "synthetic_driver_sha256": sha256_path(synthetic_driver),
            "focused_tests_sha256": sha256_path(focused_tests),
            "chemistry_source_sha256": sha256_path(CHEMISTRY_SOURCE),
            "topology_source_sha256": sha256_path(TOPOLOGY_SOURCE),
            "root_lock_sha256": sha256_path(LOCK),
        },
        "roots": {
            "count": 2,
            "physical_sqlite_sha256": source_hashes,
            "physical_sqlite_hashes_differ": True,
            "logical_source_sha256": manifest["logical_source_sha256"],
            "relative_terminal_maps_byte_identical": True,
            "terminal_tree_sha256": terminal_tree,
        },
        "runtime": {
            "python": sys.version.split()[0],
            "sqlite": sqlite3.sqlite_version,
            "rdkit": rdBase.rdkitVersion,
        },
        "counts": manifest["counts"],
        "filter_counts": read_json(terminal_a / "x1_synthetic_filter_counts.json"),
        "chemistry_counts": read_json(terminal_a / "x1_synthetic_chemistry_counts.json"),
        "union_counts": read_json(terminal_a / "x1_synthetic_union_counts.json"),
        "support_decisions": read_json(terminal_a / "x1_synthetic_support_decisions.json"),
        "focused_tests_passed": focused_tests_passed,
        "adversarial_boundaries_passed": True,
        "accounting": aggregate_accounting,
        "terminal_roots_retained": 0,
        "mutable_source_roots_retained": 0,
        "private_roots_retained": 0,
        "authority": {
            "synthetic_compiler_mechanics": True,
            "external_record_acquisition": False,
            "official_inputs": False,
            "model_fitting": False,
            "prediction_generation": False,
            "metric_evaluation": False,
            "submission": False,
            "leaderboard_selection": False,
            "upload": False,
            "claim_creation_or_consumption": False,
        },
        "decision": "Accept deterministic synthetic compiler and leakage mechanics only. Acquisition remains unauthorized until a separate reviewed single-use claim is integrated.",
        "scientific_interpretation": "No synthetic count or decision is model-quality, external-support, official, confirmatory or leaderboard evidence.",
        "next_gate": "Review and integrate this exact acceptance and require green post-main CI, then freeze a separate single-use acquisition claim before downloading or opening chembl_37 or any official challenge input.",
    }
    return {"global_v2_x1_synthetic_compiler_acceptance.json": json_bytes(value)}

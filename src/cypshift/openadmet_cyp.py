"""Lossless, receipt-bound ingestion for the OpenADMET CYP release.

This module deliberately stops at source rows.  It does not interpret assay
states, derive labels, aggregate observations, assign families, or authorize
metrics or splits.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from cypshift.audit import MOLECULE_INPUT_COLUMNS

OPENADMET_ADAPTER_SCHEMA_VERSION = "cypshift.openadmet_cyp_2026.observation_adapter.v1"
OPENADMET_DATASET_ID = "openadmet/cyp-challenge-train-test"
DEFAULT_RECEIPTS_PATH = (
    Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "source_receipts.json"
)
OPENADMET_SOURCE_FILES = (
    "cyp-challenge-TEST-BLINDED.csv",
    "cyp-challenge-TRAIN_Emax.csv",
    "cyp-challenge-TRAIN_TDI.csv",
    "cyp-challenge-TRAIN_inhibition.csv",
    "cyp-challenge-single-concentration-TRAIN.csv",
)
SOURCE_ROW_COLUMNS = (
    "source_row_id",
    "Molecule_Name",
    "SMILES",
    "source_file",
    "source_row",
    "partition",
    "modality",
    "source_values",
)
_FILE_CONTEXT = {
    "cyp-challenge-TEST-BLINDED.csv": ("test", "blinded_test"),
    "cyp-challenge-TRAIN_Emax.csv": ("train", "emax"),
    "cyp-challenge-TRAIN_TDI.csv": ("train", "tdi"),
    "cyp-challenge-TRAIN_inhibition.csv": ("train", "direct_inhibition"),
    "cyp-challenge-single-concentration-TRAIN.csv": (
        "train",
        "single_concentration",
    ),
}
_UNRESOLVED = (
    "interval terminology and bounds semantics",
    "TDI label derivation and official TDI column order",
    "live scorer masks, denominator, and backend parity",
    "transductive test-test permissions",
)


class OpenADMETDataError(ValueError):
    """Raised when the frozen OpenADMET source cannot be ingested safely."""


@dataclass(frozen=True, slots=True)
class OpenADMETAdapterResult:
    """Paths and counts from one completed source-only preparation."""

    molecules_path: Path
    source_rows_path: Path
    manifest_path: Path
    source_revision: str
    source_row_count: int
    molecule_count: int


def prepare_openadmet_cyp(
    dataset_root: Path,
    output_directory: Path,
    *,
    source_revision: str,
    receipts_path: Path = DEFAULT_RECEIPTS_PATH,
) -> OpenADMETAdapterResult:
    """Prepare deterministic source-row and chemistry-audit input artifacts.

    All receipts and source bytes are validated before the new output directory
    is created.  Every output is derived from the five exact frozen CSV files;
    no numeric or scientific interpretation is performed.
    """

    if output_directory.exists():
        raise OpenADMETDataError(
            f"output path already exists: {output_directory}. "
            "Choose a new directory; the adapter never overwrites artifacts."
        )
    if not source_revision:
        raise OpenADMETDataError("source_revision must not be empty")
    if not dataset_root.is_dir():
        raise OpenADMETDataError(f"dataset root is not a directory: {dataset_root}")

    receipts = _load_json(receipts_path, "source receipts")
    dataset = _object(_object(receipts, "receipts").get("sources"), "sources")
    dataset = _object(dataset.get("dataset"), "sources.dataset")
    receipt_revision = _text(dataset, "revision", "sources.dataset")
    if receipt_revision != source_revision:
        raise OpenADMETDataError(
            "source revision mismatch: expected the pinned receipt revision "
            f"{receipt_revision!r}, got {source_revision!r}"
        )
    entries = dataset.get("files")
    if not isinstance(entries, list):
        raise OpenADMETDataError("sources.dataset.files must be an array")
    if tuple(_entry_path(entry) for entry in entries) != OPENADMET_SOURCE_FILES:
        raise OpenADMETDataError(
            "sources.dataset.files must contain the five frozen CSV files "
            "in their frozen order"
        )

    validated_files: list[tuple[str, str, list[str], list[dict[str, str]]]] = []
    for entry in entries:
        item = _object(entry, "dataset file receipt")
        source_file = _text(item, "path", "dataset file receipt")
        expected_size = _integer(item, "size_bytes", source_file)
        expected_hash = _digest(item, "sha256", source_file)
        expected_rows = _integer(item, "rows", source_file)
        expected_header = _string_list(item, "header", source_file)
        path = dataset_root / source_file
        if not path.is_file():
            raise OpenADMETDataError(f"missing dataset file: {source_file}")
        data = _read_bytes(path, source_file)
        actual_hash = sha256(data).hexdigest()
        if len(data) != expected_size:
            raise OpenADMETDataError(
                f"size mismatch for {source_file}: expected {expected_size}, "
                f"got {len(data)}"
            )
        if actual_hash != expected_hash:
            raise OpenADMETDataError(
                f"SHA-256 mismatch for {source_file}: expected {expected_hash}, "
                f"got {actual_hash}"
            )
        rows = _read_csv(path, expected_header, source_file)
        if len(rows) != expected_rows:
            raise OpenADMETDataError(
                f"row count mismatch for {source_file}: expected {expected_rows}, "
                f"got {len(rows)}"
            )
        validated_files.append((source_file, actual_hash, expected_header, rows))

    molecules: dict[str, dict[str, Any]] = {}
    source_rows: list[dict[str, str]] = []
    test_names: set[str] = set()
    train_names: set[str] = set()
    seen_row_ids: set[str] = set()
    for source_file, source_hash, _header, rows in validated_files:
        partition, modality = _FILE_CONTEXT[source_file]
        for source_row, values in enumerate(rows, start=2):
            name = values["Molecule_Name"]
            smiles = values["SMILES"]
            if not name or not name.strip():
                raise OpenADMETDataError(
                    f"{source_file} row {source_row} has empty Molecule_Name"
                )
            if not smiles or not smiles.strip():
                raise OpenADMETDataError(
                    f"{source_file} row {source_row} has empty SMILES"
                )
            row_id = f"{source_file}:{source_row}"
            if row_id in seen_row_ids:
                raise OpenADMETDataError(f"duplicate source row identity: {row_id}")
            seen_row_ids.add(row_id)
            occurrence = {
                "source_file": source_file,
                "source_row": source_row,
                "source_sha256": source_hash,
            }
            molecule = molecules.get(name)
            if molecule is None:
                molecule = {"structure": smiles, "occurrences": []}
                molecules[name] = molecule
            elif cast(str, molecule["structure"]) != smiles:
                raise OpenADMETDataError(
                    "Molecule_Name maps to conflicting exact SMILES: "
                    f"{name!r} ({source_file} row {source_row})"
                )
            cast(list[dict[str, Any]], molecule["occurrences"]).append(occurrence)
            if partition == "test":
                test_names.add(name)
            else:
                train_names.add(name)
            source_rows.append(
                {
                    "source_row_id": row_id,
                    "Molecule_Name": name,
                    "SMILES": smiles,
                    "source_file": source_file,
                    "source_row": str(source_row),
                    "partition": partition,
                    "modality": modality,
                    "source_values": _compact_json(values),
                }
            )
    overlap = sorted(test_names & train_names)
    if overlap:
        raise OpenADMETDataError(
            "blinded test Molecule_Name values overlap training: " + ", ".join(overlap)
        )

    molecule_rows = [
        {
            "molecule_id": name,
            "structure": cast(str, molecule["structure"]),
            "structure_format": "smiles",
            "source": OPENADMET_DATASET_ID,
            "provenance": _compact_json(
                {
                    "dataset_id": OPENADMET_DATASET_ID,
                    "source_revision": source_revision,
                    "occurrences": molecule["occurrences"],
                }
            ),
        }
        for name, molecule in molecules.items()
    ]
    molecules_bytes = _csv_bytes(MOLECULE_INPUT_COLUMNS, molecule_rows)
    source_rows_bytes = _csv_bytes(SOURCE_ROW_COLUMNS, source_rows)
    manifest = {
        "schema_version": OPENADMET_ADAPTER_SCHEMA_VERSION,
        "dataset_id": OPENADMET_DATASET_ID,
        "source_revision": source_revision,
        "source_files": [
            {"path": name, "sha256": digest, "rows": len(rows), "header": header}
            for name, digest, header, rows in validated_files
        ],
        "counts": {
            "source_rows": len(source_rows),
            "molecules": len(molecule_rows),
        },
        "outputs": {
            "molecules_input.csv": {
                "sha256": sha256(molecules_bytes).hexdigest(),
                "rows": len(molecule_rows),
            },
            "source_rows.csv": {
                "sha256": sha256(source_rows_bytes).hexdigest(),
                "rows": len(source_rows),
            },
        },
        "scope": {
            "source_rows_only": True,
            "metric_authority": False,
            "model_authority": False,
            "aggregation_authority": False,
            "split_authority": False,
            "submission_authority": False,
            "scientific_interpretation": False,
        },
        "unresolved": list(_UNRESOLVED),
        "deterministic": True,
    }
    manifest_bytes = _json_bytes(manifest)

    output_directory.mkdir(parents=True)
    molecules_path = output_directory / "molecules_input.csv"
    source_rows_path = output_directory / "source_rows.csv"
    manifest_path = output_directory / "manifest.json"
    _write_new(molecules_path, molecules_bytes)
    _write_new(source_rows_path, source_rows_bytes)
    _write_new(manifest_path, manifest_bytes)
    return OpenADMETAdapterResult(
        molecules_path=molecules_path,
        source_rows_path=source_rows_path,
        manifest_path=manifest_path,
        source_revision=source_revision,
        source_row_count=len(source_rows),
        molecule_count=len(molecule_rows),
    )


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OpenADMETDataError(f"cannot read {label} {path}: {exc}") from exc
    return _object(value, label)


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OpenADMETDataError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _text(value: Mapping[str, Any], key: str, label: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise OpenADMETDataError(f"{label}.{key} must be non-empty text")
    return item


def _integer(value: Mapping[str, Any], key: str, label: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int) or item < 0:
        raise OpenADMETDataError(f"{label}.{key} must be a non-negative integer")
    return item


def _digest(value: Mapping[str, Any], key: str, label: str) -> str:
    item = _text(value, key, label).lower()
    if len(item) != 64 or any(char not in "0123456789abcdef" for char in item):
        raise OpenADMETDataError(f"{label}.{key} must be a SHA-256 digest")
    return item


def _string_list(value: Mapping[str, Any], key: str, label: str) -> list[str]:
    item = value.get(key)
    if (
        not isinstance(item, list)
        or not item
        or not all(isinstance(part, str) for part in item)
    ):
        raise OpenADMETDataError(f"{label}.{key} must be a non-empty string array")
    return cast(list[str], item)


def _entry_path(value: Any) -> str:
    entry = _object(value, "dataset file receipt")
    path = _text(entry, "path", "dataset file receipt")
    relative = Path(path)
    if relative.is_absolute() or ".." in relative.parts or relative.parts != (path,):
        raise OpenADMETDataError(f"dataset file path must be a plain filename: {path}")
    return path


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise OpenADMETDataError(f"cannot read {label}: {exc}") from exc


def _read_csv(
    path: Path, expected_header: Sequence[str], label: str
) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if header != list(expected_header):
                raise OpenADMETDataError(
                    f"header mismatch for {label}: expected {list(expected_header)!r}, "
                    f"got {header!r}"
                )
            rows: list[dict[str, str]] = []
            for line_number, values in enumerate(reader, start=2):
                if len(values) != len(expected_header):
                    raise OpenADMETDataError(
                        f"field count mismatch for {label} row {line_number}"
                    )
                rows.append(dict(zip(expected_header, values, strict=True)))
            return rows
    except (OSError, UnicodeError, csv.Error) as exc:
        raise OpenADMETDataError(f"cannot parse {label}: {exc}") from exc


def _csv_bytes(columns: Sequence[str], rows: Sequence[Mapping[str, str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _compact_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_new(path: Path, content: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise OpenADMETDataError(f"refusing to overwrite {path}") from exc


__all__ = [
    "DEFAULT_RECEIPTS_PATH",
    "OPENADMET_ADAPTER_SCHEMA_VERSION",
    "OPENADMET_DATASET_ID",
    "OPENADMET_SOURCE_FILES",
    "OpenADMETAdapterResult",
    "OpenADMETDataError",
    "SOURCE_ROW_COLUMNS",
    "prepare_openadmet_cyp",
]

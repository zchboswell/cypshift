"""Least-privilege byte and record handling for the synthetic R4 boundary.

This module intentionally stops before chemistry or transformation extraction.  It
loads each source byte stream once, verifies its receipt before decoding it, and
projects only the fields named by the frozen R4 trusted projections.  In
particular, the direct-observation and mask suffixes are scanned as opaque bytes;
their values are never decoded into Python fields.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from cypshift.openadmet_validation import FOLD_COLUMNS, OBSERVATION_COLUMNS
from cypshift.openadmet_validation_contract import MASK_COLUMNS, PUBLIC_EPISODE_COLUMNS

DIRECT_PROJECTION_COLUMNS = (
    "observation_id",
    "molecule_id",
    "endpoint",
    "raw_structure_sha256",
    "standardized_structure_hash",
    "similarity_component_hash",
    "value_state",
)
DIRECT_SOURCE_INDICES = (0, 1, 6, 16, 17, 18, 20)
MASK_PROJECTION_COLUMNS = ("episode_id", "anchor_molecule_id_truth")
MASK_SOURCE_INDICES = (0, 1)
STRUCTURE_COLUMNS = (
    "molecule_id",
    "raw_smiles",
    "raw_structure_sha256",
    "standardized_smiles",
    "standardized_structure_hash",
    "similarity_component_hash",
)
ENDPOINTS = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
VALUE_STATES = ("complete", "partial", "missing", "orphan_auxiliary")
NO_TARGET_ACCOUNTING = {
    "numeric_target_magnitudes_parsed": 0,
    "numeric_target_magnitudes_retained": 0,
    "tdi_rows_opened": 0,
    "blinded_test_rows_opened": 0,
    "model_fits": 0,
    "predictions_generated": 0,
    "metric_evaluations": 0,
    "official_scorer_calls": 0,
    "leaderboard_submissions": 0,
    "transductive_operations": 0,
}
NO_AUTHORITY = {
    "coverage_artifacts": False,
    "label_derivation": False,
    "geometry_coverage": False,
    "oracle_contract_freeze": False,
    "model_fits": False,
    "predictions": False,
    "metrics": False,
    "official_st_rae": False,
    "test_access": False,
    "tdi": False,
    "submissions": False,
    "transduction": False,
}


class OpenADMETTransformationIOError(ValueError):
    """A receipt, schema, or least-privilege projection invariant failed."""


@dataclass(frozen=True, slots=True)
class TransformationSourcePaths:
    """The five source paths accepted by the synthetic R4 projector."""

    direct_observations: Path
    group_folds: Path
    public_episodes: Path
    masks: Path
    structure: Path

    def items(self) -> tuple[tuple[str, Path], ...]:
        return (
            ("direct_observations.csv", self.direct_observations),
            ("group_folds.csv", self.group_folds),
            ("public_episodes.csv", self.public_episodes),
            ("masks.csv", self.masks),
            ("structure.csv", self.structure),
        )


@dataclass(frozen=True, slots=True)
class TransformationSources:
    """One-load, least-privilege source projections for the R4 extractor."""

    direct: tuple[dict[str, str], ...]
    folds: tuple[dict[str, str], ...]
    public: tuple[dict[str, str], ...]
    masks: tuple[dict[str, str], ...]
    structure: tuple[dict[str, str], ...]
    source_receipts: dict[str, dict[str, Any]]


def read_r4_sources(
    paths: TransformationSourcePaths,
    expected_receipts: Mapping[str, str | Mapping[str, Any]],
    *,
    expected_counts: Mapping[str, int] | None = None,
) -> TransformationSources:
    """Verify and project all synthetic sources, reading every path once.

    ``expected_receipts`` is deliberately required.  A digest is checked on raw
    bytes before a header, JSON cell, or CSV record is decoded.  Receipt keys may
    be the canonical names returned by :meth:`TransformationSourcePaths.items`
    or the short aliases ``direct``, ``folds``, ``public``, ``masks``, and
    ``structure``.
    """

    expected = _normalise_receipts(expected_receipts)
    counts = _normalise_counts(expected_counts)
    loaded: dict[str, bytes] = {}
    for name, path in paths.items():
        data = _read_regular_once(path, name)
        receipt = expected.get(name)
        if receipt is None:
            raise OpenADMETTransformationIOError(f"missing receipt for {name}")
        _digest_match(data, receipt["sha256"], name)
        loaded[name] = data

    # Headers are checked before any data records are yielded.  The direct and
    # mask scanners then retain only their declared prefixes.
    direct = tuple(
        _project_prefix_csv(
            loaded["direct_observations.csv"],
            OBSERVATION_COLUMNS,
            DIRECT_PROJECTION_COLUMNS,
            DIRECT_SOURCE_INDICES,
            "direct observations",
        )
    )
    folds = tuple(_parse_csv(loaded["group_folds.csv"], FOLD_COLUMNS, "group folds"))
    public = tuple(
        _parse_csv(
            loaded["public_episodes.csv"], PUBLIC_EPISODE_COLUMNS, "public episodes"
        )
    )
    masks = tuple(
        _project_prefix_csv(
            loaded["masks.csv"],
            MASK_COLUMNS,
            MASK_PROJECTION_COLUMNS,
            MASK_SOURCE_INDICES,
            "episode masks",
            opaque_tail_start=2,
        )
    )
    structure = tuple(
        _parse_csv(loaded["structure.csv"], STRUCTURE_COLUMNS, "structure")
    )
    observed_counts = {
        "direct_observations": len(direct),
        "group_folds": len(folds),
        "public_episodes": len(public),
        "masks": len(masks),
        "structure": len(structure),
    }
    for name, receipt in expected.items():
        if name not in loaded or "rows" not in receipt:
            continue
        rows = receipt["rows"]
        if isinstance(rows, bool) or not isinstance(rows, int) or rows < 0:
            raise OpenADMETTransformationIOError(f"invalid row receipt for {name}")
        if rows != observed_counts[_receipt_count_key(name)]:
            raise OpenADMETTransformationIOError(f"{name} receipt row-count mismatch")
    for name, expected_count in counts.items():
        if observed_counts[name] != expected_count:
            raise OpenADMETTransformationIOError(f"{name} row-count mismatch")
    source_receipts = {
        name: {
            "sha256": receipt["sha256"],
            "bytes": len(loaded[name]),
            "rows": observed_counts[_receipt_count_key(name)],
        }
        for name, receipt in sorted(expected.items())
        if name in loaded
    }
    return TransformationSources(
        direct, folds, public, masks, structure, source_receipts
    )


def canonical_csv_bytes(
    columns: Sequence[str], rows: Sequence[Mapping[str, str]]
) -> bytes:
    """Serialize UTF-8 RFC4180 CSV with fixed header order and LF endings."""

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


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Serialize a deterministic JSON object with one terminal newline."""

    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def strict_json_object(data: bytes, label: str) -> dict[str, Any]:
    """Decode one JSON object while rejecting duplicate keys at every depth."""

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise OpenADMETTransformationIOError(
                    f"duplicate JSON key in {label}: {key}"
                )
            result[key] = value
        return result

    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except OpenADMETTransformationIOError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OpenADMETTransformationIOError(f"cannot parse {label}") from exc
    if not isinstance(value, dict):
        raise OpenADMETTransformationIOError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def strict_json_cell(value: str, label: str) -> Any:
    """Decode one public JSON cell with the same duplicate-key firewall."""

    try:
        data = value.encode("utf-8")
    except UnicodeError as exc:
        raise OpenADMETTransformationIOError(f"cannot encode {label}") from exc

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise OpenADMETTransformationIOError(
                    f"duplicate JSON key in {label}: {key}"
                )
            result[key] = item
        return result

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except OpenADMETTransformationIOError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OpenADMETTransformationIOError(f"cannot parse {label}") from exc


def safe_source_path(path: Path, label: str) -> Path:
    """Reject traversal, symlink components, and non-regular source files."""

    if ".." in path.parts:
        raise OpenADMETTransformationIOError(f"{label} contains path traversal")
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise OpenADMETTransformationIOError(f"{label} contains a symlink")
    if not path.is_file():
        raise OpenADMETTransformationIOError(f"{label} must be a regular file")
    return path


def _read_regular_once(path: Path, label: str) -> bytes:
    safe_source_path(path, label)
    try:
        with path.open("rb") as handle:
            return handle.read()
    except OSError as exc:
        raise OpenADMETTransformationIOError(f"cannot read {label}") from exc


def _project_prefix_csv(
    data: bytes,
    full_columns: Sequence[str],
    retained_columns: Sequence[str],
    retained_indices: Sequence[int],
    label: str,
    *,
    opaque_tail_start: int | None = None,
) -> list[dict[str, str]]:
    records = _captured_records(
        data,
        len(full_columns),
        set(retained_indices),
        label,
        opaque_tail_start=opaque_tail_start,
    )
    header = next(records, None)
    if header is None or not isinstance(header, tuple):
        raise OpenADMETTransformationIOError(f"{label} header mismatch")
    try:
        decoded_header = tuple(field.decode("utf-8") for field in header)
    except UnicodeError as exc:
        raise OpenADMETTransformationIOError(f"{label} header mismatch") from exc
    if decoded_header != tuple(full_columns):
        raise OpenADMETTransformationIOError(f"{label} header mismatch")
    output: list[dict[str, str]] = []
    for fields in records:
        if not isinstance(fields, dict):
            raise OpenADMETTransformationIOError(f"{label} header repeated")
        selected: dict[str, str] = {}
        for column, index in zip(retained_columns, retained_indices, strict=True):
            try:
                selected[column] = fields[index].decode("utf-8")
            except (IndexError, UnicodeError) as exc:
                raise OpenADMETTransformationIOError(
                    f"cannot decode retained {label} field"
                ) from exc
        output.append(selected)
    return output


def _captured_records(
    data: bytes,
    expected_field_count: int,
    capture_indices: set[int],
    label: str,
    *,
    opaque_tail_start: int | None = None,
) -> Iterator[tuple[bytes, ...] | dict[int, bytes]]:
    """Scan CSV boundaries while buffering only header/retained fields.

    For data records, an unretained field is represented only by a field index
    and a quote-state transition.  Its bytes are never copied into a field
    object.  This is important for direct target/eligibility spans and for the
    mask's opaque suffix, which may contain invalid UTF-8 poison values.
    """

    if not data or not data.endswith(b"\n"):
        raise OpenADMETTransformationIOError(f"{label} must end with LF")
    record_number = 0
    field_index = 0
    field: bytearray | None = bytearray()
    selected: dict[int, bytes] = {}
    header: list[bytes] = []
    in_quotes = False
    field_started = False
    quote_closed = False
    opaque_tail = False
    opaque_field_count = 0
    index = 0
    while index < len(data):
        byte = data[index]
        if opaque_tail:
            # The mask suffix is one opaque byte span.  We count only its two
            # logical boundaries and track RFC4180 quote state; no suffix
            # field bytes are split, copied, or decoded.
            if in_quotes:
                if byte == 34 and index + 1 < len(data) and data[index + 1] == 34:
                    index += 2
                    continue
                if byte == 34:
                    in_quotes = False
                    quote_closed = True
                index += 1
                continue
            if quote_closed and byte not in (44, 10, 13):
                raise OpenADMETTransformationIOError(f"malformed quoted {label} suffix")
            if byte == 34:
                if field_started:
                    raise OpenADMETTransformationIOError(
                        f"malformed quoted {label} suffix"
                    )
                in_quotes = True
                field_started = True
            elif byte == 44:
                opaque_field_count += 1
                if opaque_field_count >= 2:
                    raise OpenADMETTransformationIOError(
                        f"{label} has extra opaque suffix fields"
                    )
                field_started = False
                quote_closed = False
            elif byte == 10:
                opaque_field_count += 1
                if opaque_field_count != 2:
                    raise OpenADMETTransformationIOError(
                        f"{label} opaque suffix field-count mismatch"
                    )
                yield dict(selected)
                record_number += 1
                field_index = 0
                field = _new_capture(record_number, 0, capture_indices)
                selected = {}
                header = []
                field_started = False
                quote_closed = False
                opaque_tail = False
                opaque_field_count = 0
                index += 1
                continue
            elif byte == 13:
                if index + 1 >= len(data) or data[index + 1] != 10:
                    raise OpenADMETTransformationIOError(
                        f"malformed {label} suffix line ending"
                    )
            else:
                field_started = True
            index += 1
            continue
        if in_quotes:
            if byte == 34:
                if index + 1 < len(data) and data[index + 1] == 34:
                    if field is not None:
                        field.append(34)
                    index += 2
                    continue
                in_quotes = False
                quote_closed = True
            else:
                if field is not None:
                    field.append(byte)
            index += 1
            continue
        if quote_closed and byte not in (44, 10, 13):
            raise OpenADMETTransformationIOError(f"malformed quoted {label} record")
        if byte == 34:
            if field_started or field:
                raise OpenADMETTransformationIOError(f"malformed quoted {label} field")
            in_quotes = True
            field_started = True
        elif byte == 44:  # comma
            _finish_field(
                field_index,
                field,
                record_number,
                selected,
                header,
            )
            field_index += 1
            if (
                opaque_tail_start is not None
                and record_number > 0
                and field_index >= opaque_tail_start
            ):
                opaque_tail = True
                field = None
                field_started = False
                quote_closed = False
                opaque_field_count = 0
                index += 1
                continue
            field = _new_capture(record_number, field_index, capture_indices)
            field_started = False
            quote_closed = False
        elif byte == 10:
            if in_quotes:
                raise OpenADMETTransformationIOError(f"unterminated {label} record")
            _finish_field(
                field_index,
                field,
                record_number,
                selected,
                header,
            )
            if field_index + 1 != expected_field_count:
                raise OpenADMETTransformationIOError(f"{label} field-count mismatch")
            if record_number == 0:
                yield tuple(header)
            else:
                yield dict(selected)
            record_number += 1
            field_index = 0
            field = _new_capture(record_number, 0, capture_indices)
            selected = {}
            header = []
            field_started = False
            quote_closed = False
        else:
            if quote_closed:
                raise OpenADMETTransformationIOError(f"malformed quoted {label} record")
            if field is not None:
                field.append(byte)
            field_started = True
        index += 1
    if in_quotes:
        raise OpenADMETTransformationIOError(f"unterminated {label} record")


def _new_capture(
    record_number: int, field_index: int, capture_indices: set[int]
) -> bytearray | None:
    # Header bytes are allowed for exact schema validation; source data bytes
    # are allocated only for retained positions.
    if record_number == 0 or field_index in capture_indices:
        return bytearray()
    return None


def _finish_field(
    field_index: int,
    field: bytearray | None,
    record_number: int,
    selected: dict[int, bytes],
    header: list[bytes],
) -> None:
    if field is None:
        return
    value = bytes(field[:-1]) if field.endswith(b"\r") else bytes(field)
    if record_number == 0:
        header.append(value)
    else:
        selected[field_index] = value


def _parse_csv(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    if not data.endswith(b"\n") or b"\r" in data:
        raise OpenADMETTransformationIOError(f"{label} has invalid line endings")
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True)
        header = next(reader, None)
        if header != list(columns):
            raise OpenADMETTransformationIOError(f"{label} header mismatch")
        rows: list[dict[str, str]] = []
        for values in reader:
            if len(values) != len(columns):
                raise OpenADMETTransformationIOError(f"{label} field-count mismatch")
            rows.append(dict(zip(columns, values, strict=True)))
        return rows
    except (UnicodeError, csv.Error) as exc:
        raise OpenADMETTransformationIOError(f"cannot parse {label}") from exc


def _normalise_receipts(
    values: Mapping[str, str | Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    aliases = {
        "direct": "direct_observations.csv",
        "direct_observations": "direct_observations.csv",
        "folds": "group_folds.csv",
        "group_folds": "group_folds.csv",
        "public": "public_episodes.csv",
        "campaign_episodes_public": "public_episodes.csv",
        "masks": "masks.csv",
        "episode_label_masks": "masks.csv",
        "structure": "structure.csv",
        "feature_input": "structure.csv",
    }
    output: dict[str, dict[str, Any]] = {}
    canonical_names = {
        "direct_observations.csv",
        "group_folds.csv",
        "public_episodes.csv",
        "masks.csv",
        "structure.csv",
    }
    for key, value in values.items():
        name = aliases.get(key, key)
        if name not in canonical_names:
            raise OpenADMETTransformationIOError(f"unknown receipt: {key}")
        if name in output:
            raise OpenADMETTransformationIOError(f"duplicate receipt: {name}")
        if not isinstance(value, (str, Mapping)):
            raise OpenADMETTransformationIOError(f"invalid receipt for {name}")
        digest = value if isinstance(value, str) else value.get("sha256")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise OpenADMETTransformationIOError(f"invalid receipt for {name}")
        receipt = dict(value) if isinstance(value, Mapping) else {"sha256": digest}
        receipt["sha256"] = digest
        if "rows" in receipt:
            rows = receipt["rows"]
            if isinstance(rows, bool) or not isinstance(rows, int) or rows < 0:
                raise OpenADMETTransformationIOError(f"invalid row receipt for {name}")
        output[name] = receipt
    if set(output) != canonical_names:
        missing = sorted(canonical_names - set(output))
        raise OpenADMETTransformationIOError(f"missing receipt: {missing[0]}")
    return output


def _normalise_counts(values: Mapping[str, int] | None) -> dict[str, int]:
    if values is None:
        return {}
    allowed = {
        "direct_observations",
        "group_folds",
        "public_episodes",
        "masks",
        "structure",
    }
    output: dict[str, int] = {}
    for key, value in values.items():
        if (
            key not in allowed
            or isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
        ):
            raise OpenADMETTransformationIOError(f"invalid expected count: {key}")
        output[key] = value
    return output


def _receipt_count_key(name: str) -> str:
    return {
        "direct_observations.csv": "direct_observations",
        "group_folds.csv": "group_folds",
        "public_episodes.csv": "public_episodes",
        "masks.csv": "masks",
        "structure.csv": "structure",
    }[name]


def _digest_match(data: bytes, expected: str, label: str) -> None:
    if sha256(data).hexdigest() != expected:
        raise OpenADMETTransformationIOError(f"{label} SHA-256 mismatch")


__all__ = [
    "DIRECT_PROJECTION_COLUMNS",
    "ENDPOINTS",
    "FOLD_COLUMNS",
    "MASK_PROJECTION_COLUMNS",
    "NO_AUTHORITY",
    "NO_TARGET_ACCOUNTING",
    "OBSERVATION_COLUMNS",
    "OpenADMETTransformationIOError",
    "PUBLIC_EPISODE_COLUMNS",
    "STRUCTURE_COLUMNS",
    "TransformationSourcePaths",
    "TransformationSources",
    "VALUE_STATES",
    "canonical_csv_bytes",
    "canonical_json_bytes",
    "read_r4_sources",
    "safe_source_path",
    "strict_json_cell",
    "strict_json_object",
]

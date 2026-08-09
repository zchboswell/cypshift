"""Canonical internal records for molecules and assay measurements.

These records are deliberately independent of the pre-launch challenge files.
Launch-day adapters may map official fields into this internal representation
without changing the chemistry or measurement truth preserved here.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class RecordError(ValueError):
    """Raised when an input row cannot become a canonical record."""


class MoleculeStatus(StrEnum):
    """Whether a molecule is usable or explicitly quarantined."""

    ACCEPTED = "accepted"
    QUARANTINED = "quarantined"


class StereochemistryStatus(StrEnum):
    """State of potentially stereogenic elements in the supplied structure."""

    NONE = "none"
    SPECIFIED = "specified"
    UNSPECIFIED = "unspecified"
    MIXED = "mixed"


class Censoring(StrEnum):
    """How a measurement relates to its reported numeric bounds."""

    NONE = "none"
    LEFT = "left"
    RIGHT = "right"
    INTERVAL = "interval"


@dataclass(frozen=True, slots=True)
class MoleculeInput:
    """A source molecule before parsing or standardization."""

    molecule_id: str
    structure: str
    structure_format: str
    source: str
    provenance: str

    @classmethod
    def from_mapping(cls, row: Mapping[str, str]) -> MoleculeInput:
        """Validate a mapping produced by a fixture or future data adapter."""

        values = {
            field: _required_text(row, field)
            for field in (
                "molecule_id",
                "structure_format",
                "source",
                "provenance",
            )
        }
        values["structure"] = _required_raw_text(row, "structure")
        if values["structure_format"].lower() != "smiles":
            raise RecordError(
                "structure_format must be 'smiles' in the Phase 0 adapter; "
                f"got {values['structure_format']!r}"
            )
        values["structure_format"] = "smiles"
        return cls(**values)


@dataclass(frozen=True, slots=True)
class MoleculeRecord:
    """An audited molecule with both immutable raw and derived structures."""

    molecule_id: str
    raw_structure: str
    structure_format: str
    standardized_structure: str | None
    standardized_structure_hash: str | None
    status: MoleculeStatus
    stereochemistry_status: StereochemistryStatus
    input_fragments: tuple[str, ...]
    standardization_changed: bool
    duplicate_of: str | None
    warnings: tuple[str, ...]
    standardization_version: str
    source: str
    provenance: str

    @classmethod
    def from_mapping(cls, row: Mapping[str, str]) -> MoleculeRecord:
        """Parse one previously audited canonical molecule row."""

        status_text = _required_text(row, "status")
        stereo_text = _required_text(row, "stereochemistry_status")
        try:
            status = MoleculeStatus(status_text)
            stereochemistry_status = StereochemistryStatus(stereo_text)
        except ValueError as exc:
            raise RecordError("invalid canonical molecule status") from exc

        record = cls(
            molecule_id=_required_text(row, "molecule_id"),
            raw_structure=_required_raw_text(row, "raw_structure"),
            structure_format=_required_text(row, "structure_format"),
            standardized_structure=_optional_text(row, "standardized_structure"),
            standardized_structure_hash=_optional_text(
                row, "standardized_structure_hash"
            ),
            status=status,
            stereochemistry_status=stereochemistry_status,
            input_fragments=_json_string_tuple(row, "input_fragments"),
            standardization_changed=_required_bool(
                row, "standardization_changed"
            ),
            duplicate_of=_optional_text(row, "duplicate_of"),
            warnings=_json_string_tuple(row, "warnings"),
            standardization_version=_required_text(
                row, "standardization_version"
            ),
            source=_required_text(row, "source"),
            provenance=_required_text(row, "provenance"),
        )
        if status is MoleculeStatus.ACCEPTED:
            if (
                record.standardized_structure is None
                or record.standardized_structure_hash is None
            ):
                raise RecordError(
                    "accepted molecule requires standardized structure and hash"
                )
        elif (
            record.standardized_structure is not None
            or record.standardized_structure_hash is not None
        ):
            raise RecordError(
                "quarantined molecule cannot have standardized structure or hash"
            )
        return record

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-compatible representation."""

        return {
            "molecule_id": self.molecule_id,
            "raw_structure": self.raw_structure,
            "structure_format": self.structure_format,
            "standardized_structure": self.standardized_structure,
            "standardized_structure_hash": self.standardized_structure_hash,
            "status": self.status.value,
            "stereochemistry_status": self.stereochemistry_status.value,
            "input_fragments": list(self.input_fragments),
            "standardization_changed": self.standardization_changed,
            "duplicate_of": self.duplicate_of,
            "warnings": list(self.warnings),
            "standardization_version": self.standardization_version,
            "source": self.source,
            "provenance": self.provenance,
        }


@dataclass(frozen=True, slots=True)
class MeasurementRecord:
    """A condition-aware assay measurement with explicit uncertainty."""

    measurement_id: str
    molecule_id: str
    endpoint: str
    isoform: str
    nadph_condition: str
    probe: str
    readout: str
    value: float | None
    lower_bound: float | None
    upper_bound: float | None
    censoring: Censoring
    unit: str
    quality: str
    source: str
    provenance: str

    @classmethod
    def from_mapping(cls, row: Mapping[str, str]) -> MeasurementRecord:
        """Parse and validate one canonical measurement mapping."""

        censoring_text = _required_text(row, "censoring").lower()
        try:
            censoring = Censoring(censoring_text)
        except ValueError as exc:
            allowed = ", ".join(member.value for member in Censoring)
            raise RecordError(
                f"censoring must be one of {allowed}; got {censoring_text!r}"
            ) from exc

        record = cls(
            measurement_id=_required_text(row, "measurement_id"),
            molecule_id=_required_text(row, "molecule_id"),
            endpoint=_required_text(row, "endpoint"),
            isoform=_required_text(row, "isoform"),
            nadph_condition=_required_text(row, "nadph_condition"),
            probe=_required_text(row, "probe"),
            readout=_required_text(row, "readout"),
            value=_optional_float(row, "value"),
            lower_bound=_optional_float(row, "lower_bound"),
            upper_bound=_optional_float(row, "upper_bound"),
            censoring=censoring,
            unit=_required_text(row, "unit"),
            quality=_required_text(row, "quality"),
            source=_required_text(row, "source"),
            provenance=_required_text(row, "provenance"),
        )
        record._validate_numeric_contract()
        return record

    def _validate_numeric_contract(self) -> None:
        if self.lower_bound is not None and self.upper_bound is not None:
            if self.lower_bound > self.upper_bound:
                raise RecordError("lower_bound cannot exceed upper_bound")

        if self.censoring is Censoring.NONE and self.value is None:
            raise RecordError("uncensored measurements require value")
        if self.censoring is Censoring.LEFT and self.upper_bound is None:
            raise RecordError("left-censored measurements require upper_bound")
        if self.censoring is Censoring.RIGHT and self.lower_bound is None:
            raise RecordError("right-censored measurements require lower_bound")
        if self.censoring is Censoring.INTERVAL:
            if self.lower_bound is None or self.upper_bound is None:
                raise RecordError(
                    "interval-censored measurements require both bounds"
                )

        if self.value is not None:
            if self.lower_bound is not None and self.value < self.lower_bound:
                raise RecordError("value cannot be below lower_bound")
            if self.upper_bound is not None and self.value > self.upper_bound:
                raise RecordError("value cannot exceed upper_bound")

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-compatible representation."""

        return {
            "measurement_id": self.measurement_id,
            "molecule_id": self.molecule_id,
            "endpoint": self.endpoint,
            "isoform": self.isoform,
            "nadph_condition": self.nadph_condition,
            "probe": self.probe,
            "readout": self.readout,
            "value": self.value,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "censoring": self.censoring.value,
            "unit": self.unit,
            "quality": self.quality,
            "source": self.source,
            "provenance": self.provenance,
        }


def _required_text(row: Mapping[str, str], field: str) -> str:
    value = row.get(field)
    if value is None or not value.strip():
        raise RecordError(f"{field} is required")
    return value.strip()


def _required_raw_text(row: Mapping[str, str], field: str) -> str:
    value = row.get(field)
    if value is None or not value.strip():
        raise RecordError(f"{field} is required")
    return value


def _optional_float(row: Mapping[str, str], field: str) -> float | None:
    value = row.get(field)
    if value is None or not value.strip():
        return None
    try:
        parsed = float(value)
    except ValueError as exc:
        raise RecordError(f"{field} must be numeric; got {value!r}") from exc
    if not math.isfinite(parsed):
        raise RecordError(f"{field} must be finite; got {value!r}")
    return parsed


def _optional_text(row: Mapping[str, str], field: str) -> str | None:
    value = row.get(field)
    if value is None or not value.strip():
        return None
    return value.strip()


def _required_bool(row: Mapping[str, str], field: str) -> bool:
    value = _required_text(row, field).lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise RecordError(f"{field} must be 'true' or 'false'; got {value!r}")


def _json_string_tuple(row: Mapping[str, str], field: str) -> tuple[str, ...]:
    value = _required_text(row, field)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise RecordError(f"{field} must be a JSON string array") from exc
    if not isinstance(parsed, list) or not all(
        isinstance(item, str) for item in parsed
    ):
        raise RecordError(f"{field} must be a JSON string array")
    return tuple(parsed)

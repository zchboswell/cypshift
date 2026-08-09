from __future__ import annotations

import pytest

from cypshift.schema import (
    Censoring,
    MeasurementRecord,
    MoleculeInput,
    RecordError,
)


def measurement_row(**overrides: str) -> dict[str, str]:
    row = {
        "measurement_id": "measure-001",
        "molecule_id": "molecule-001",
        "endpoint": "direct_inhibition",
        "isoform": "synthetic_isoform_a",
        "nadph_condition": "absent",
        "probe": "synthetic_probe",
        "readout": "p_activity",
        "value": "6.2",
        "lower_bound": "6.0",
        "upper_bound": "6.4",
        "censoring": "none",
        "unit": "synthetic_log_unit",
        "quality": "synthetic_high",
        "source": "cypshift_fixture",
        "provenance": "hand_authored",
    }
    row.update(overrides)
    return row


def test_measurement_preserves_assay_context_and_uncertainty() -> None:
    record = MeasurementRecord.from_mapping(measurement_row())

    assert record.isoform == "synthetic_isoform_a"
    assert record.nadph_condition == "absent"
    assert record.lower_bound == 6.0
    assert record.upper_bound == 6.4
    assert record.censoring is Censoring.NONE


def test_molecule_input_preserves_exact_nonblank_structure_text() -> None:
    record = MoleculeInput.from_mapping(
        {
            "molecule_id": "molecule-001",
            "structure": "  CCO  ",
            "structure_format": "smiles",
            "source": "test",
            "provenance": "hand_authored",
        }
    )

    assert record.structure == "  CCO  "


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"value": ""}, "uncensored measurements require value"),
        (
            {"censoring": "left", "value": "", "upper_bound": ""},
            "left-censored measurements require upper_bound",
        ),
        (
            {"censoring": "interval", "value": "", "lower_bound": ""},
            "interval-censored measurements require both bounds",
        ),
        (
            {"lower_bound": "6.5", "upper_bound": "6.0"},
            "lower_bound cannot exceed upper_bound",
        ),
        ({"value": "NaN"}, "value must be finite"),
        ({"value": "Inf"}, "value must be finite"),
        ({"lower_bound": "-Inf"}, "lower_bound must be finite"),
    ],
)
def test_measurement_rejects_incoherent_numeric_contract(
    overrides: dict[str, str], message: str
) -> None:
    with pytest.raises(RecordError, match=message):
        MeasurementRecord.from_mapping(measurement_row(**overrides))

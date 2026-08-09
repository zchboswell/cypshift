from __future__ import annotations

from cypshift.chemistry import audit_molecules, standardize_molecule
from cypshift.schema import (
    MoleculeInput,
    MoleculeStatus,
    StereochemistryStatus,
)


def molecule(molecule_id: str, structure: str) -> MoleculeInput:
    return MoleculeInput(
        molecule_id=molecule_id,
        structure=structure,
        structure_format="smiles",
        source="test",
        provenance="hand_authored",
    )


def test_invalid_structure_is_explicitly_quarantined() -> None:
    record = standardize_molecule(molecule("invalid", "not-a-smiles"))

    assert record.raw_structure == "not-a-smiles"
    assert record.status is MoleculeStatus.QUARANTINED
    assert record.standardized_structure is None
    assert record.warnings == ("invalid_structure",)


def test_raw_structure_whitespace_is_preserved_and_warned() -> None:
    record = standardize_molecule(molecule("whitespace", "  CCO  "))

    assert record.raw_structure == "  CCO  "
    assert record.standardized_structure == "CCO"
    assert "input_structure_whitespace" in record.warnings


def test_fragment_removal_is_never_silent() -> None:
    record = standardize_molecule(
        molecule("salt", "CC[NH+](C)C.[Cl-]")
    )

    assert record.status is MoleculeStatus.ACCEPTED
    assert record.standardized_structure == "CC[NH+](C)C"
    assert record.input_fragments == ("CC[NH+](C)C", "[Cl-]")
    assert record.standardization_changed
    assert "multiple_fragments_input" in record.warnings
    assert "standardization_changed" in record.warnings


def test_stereochemistry_status_distinguishes_specified_and_unspecified() -> None:
    specified = standardize_molecule(molecule("specified", "C[C@H](O)Cl"))
    unspecified = standardize_molecule(molecule("unspecified", "CC(O)Cl"))

    assert specified.stereochemistry_status is StereochemistryStatus.SPECIFIED
    assert "stereochemistry_unspecified" not in specified.warnings
    assert (
        unspecified.stereochemistry_status
        is StereochemistryStatus.UNSPECIFIED
    )
    assert "stereochemistry_unspecified" in unspecified.warnings


def test_standardized_duplicates_reference_first_input() -> None:
    records = audit_molecules(
        [molecule("first", "CCO"), molecule("second", "OCC")]
    )

    assert records[0].duplicate_of is None
    assert records[1].duplicate_of == "first"
    assert "duplicate_standardized_structure" in records[1].warnings


def test_every_standardization_change_has_a_warning() -> None:
    records = audit_molecules(
        [
            molecule("unchanged", "CCO"),
            molecule("salt", "CCO.[Na+]"),
            molecule("mixture", "CCO.O"),
        ]
    )

    for record in records:
        assert not record.standardization_changed or (
            "standardization_changed" in record.warnings
        )

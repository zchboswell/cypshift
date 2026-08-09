"""Small, explicit molecule standardization used by the Phase 0 audit."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

from rdkit import Chem, rdBase
from rdkit.Chem.MolStandardize import rdMolStandardize

from cypshift.schema import (
    MoleculeInput,
    MoleculeRecord,
    MoleculeStatus,
    StereochemistryStatus,
)

STANDARDIZATION_VERSION = "rdkit-cleanup-fragment-parent-v1"


def audit_molecules(molecules: list[MoleculeInput]) -> list[MoleculeRecord]:
    """Audit molecules and flag the first prior standardized duplicate."""

    records: list[MoleculeRecord] = []
    first_id_by_hash: dict[str, str] = {}
    for molecule in molecules:
        record = standardize_molecule(molecule)
        structure_hash = record.standardized_structure_hash
        if structure_hash is not None and structure_hash in first_id_by_hash:
            record = replace(
                record,
                duplicate_of=first_id_by_hash[structure_hash],
                warnings=(*record.warnings, "duplicate_standardized_structure"),
            )
        elif structure_hash is not None:
            first_id_by_hash[structure_hash] = molecule.molecule_id
        records.append(record)
    return records


def standardize_molecule(molecule: MoleculeInput) -> MoleculeRecord:
    """Parse one SMILES and retain an explicit record of every derived change."""

    parsing_structure = molecule.structure.strip()
    input_warnings = (
        ["input_structure_whitespace"]
        if parsing_structure != molecule.structure
        else []
    )
    with rdBase.BlockLogs():
        parsed: Chem.Mol | None = Chem.MolFromSmiles(parsing_structure)
    if parsed is None:
        return MoleculeRecord(
            molecule_id=molecule.molecule_id,
            raw_structure=molecule.structure,
            structure_format=molecule.structure_format,
            standardized_structure=None,
            standardized_structure_hash=None,
            status=MoleculeStatus.QUARANTINED,
            stereochemistry_status=StereochemistryStatus.NONE,
            input_fragments=(),
            standardization_changed=False,
            duplicate_of=None,
            warnings=(*input_warnings, "invalid_structure"),
            standardization_version=STANDARDIZATION_VERSION,
            source=molecule.source,
            provenance=molecule.provenance,
        )

    fragments = tuple(
        sorted(
            Chem.MolToSmiles(fragment, isomericSmiles=True)
            for fragment in Chem.GetMolFrags(parsed, asMols=True)
        )
    )
    parsed_structure = Chem.MolToSmiles(parsed, isomericSmiles=True)
    stereochemistry_status = _stereochemistry_status(parsed)

    standardized = rdMolStandardize.Cleanup(parsed)
    standardized = rdMolStandardize.FragmentParent(standardized)
    standardized_structure = Chem.MolToSmiles(
        standardized, isomericSmiles=True
    )
    changed = standardized_structure != parsed_structure

    warnings = input_warnings
    if len(fragments) > 1:
        warnings.append("multiple_fragments_input")
    if changed:
        warnings.append("standardization_changed")
    if stereochemistry_status in {
        StereochemistryStatus.UNSPECIFIED,
        StereochemistryStatus.MIXED,
    }:
        warnings.append("stereochemistry_unspecified")

    return MoleculeRecord(
        molecule_id=molecule.molecule_id,
        raw_structure=molecule.structure,
        structure_format=molecule.structure_format,
        standardized_structure=standardized_structure,
        standardized_structure_hash=sha256(
            standardized_structure.encode("utf-8")
        ).hexdigest(),
        status=MoleculeStatus.ACCEPTED,
        stereochemistry_status=stereochemistry_status,
        input_fragments=fragments,
        standardization_changed=changed,
        duplicate_of=None,
        warnings=tuple(warnings),
        standardization_version=STANDARDIZATION_VERSION,
        source=molecule.source,
        provenance=molecule.provenance,
    )


def _stereochemistry_status(molecule: Chem.Mol) -> StereochemistryStatus:
    stereo_elements = Chem.FindPotentialStereo(molecule)
    if not stereo_elements:
        return StereochemistryStatus.NONE

    specified = sum(
        info.specified == Chem.StereoSpecified.Specified for info in stereo_elements
    )
    if specified == len(stereo_elements):
        return StereochemistryStatus.SPECIFIED
    if specified == 0:
        return StereochemistryStatus.UNSPECIFIED
    return StereochemistryStatus.MIXED

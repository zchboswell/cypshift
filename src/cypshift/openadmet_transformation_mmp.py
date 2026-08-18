"""Pure, receipt-bound ordinary R4 transformation extraction.

This module intentionally contains no source projection, coverage arithmetic,
episode logic, or stereo handling.  It accepts two audited ``MoleculeRecord``
objects and deterministically extracts the v3 ordinary single/double-cut MMP
candidate, including exact embedding recovery and virtual-hydrogen views.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, cast

from rdkit import Chem, DataStructs, rdBase
from rdkit.Chem import rdFingerprintGenerator, rdMMPA

from cypshift.chemistry import STANDARDIZATION_VERSION, standardize_molecule
from cypshift.openadmet_transformation_types import (
    EXTRACTION_SPEC_RECEIPT,
    HYDROGEN_SIDE_TOKEN,
    DirectionalTransformation,
    TransformationIntegrityError,
    TransformationPairResult,
    canonical_json,
    sha256_json_array,
)
from cypshift.schema import MoleculeInput, MoleculeRecord, MoleculeStatus

MMP_PATTERN = "[#6+0;!$(*=,#[!#6])]!@!=!#[*]"
MAX_CUT_BONDS = 20
MAX_EMBEDDING_MATCHES = 1_000_000
VALID_STATUSES = {"VALID_SINGLE", "VALID_DOUBLE"}
_WARNING = {
    "C2": ("multiple_fragments_input",),
    "C6": ("standardization_changed",),
    "S2": ("ambiguous_decomposition",),
    "S3": ("inconsistent_direction",),
    "S6": ("unsupported_decomposition",),
}


def _canonical_smiles(mol: Chem.Mol) -> str:
    return Chem.MolToSmiles(
        mol,
        canonical=True,
        isomericSmiles=True,
        kekuleSmiles=False,
        allBondsExplicit=False,
        allHsExplicit=False,
    )


def _parse(smiles: str) -> Chem.Mol | None:
    with rdBase.BlockLogs():
        return Chem.MolFromSmiles(smiles)


def _heavy_count(mol: Chem.Mol) -> int:
    return sum(atom.GetAtomicNum() > 1 for atom in mol.GetAtoms())


def _fragment_heavy_count(smiles: str) -> int:
    mol = _parse(smiles)
    return (
        0
        if mol is None
        else sum(
            atom.GetAtomicNum() > 1
            for atom in mol.GetAtoms()
            if atom.GetAtomicNum() != 0
        )
    )


def _canonical_fragment(smiles: str, mapping: dict[int, int] | None = None) -> str:
    mol = _parse(smiles)
    if mol is None:
        return ""
    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() == 0:
            if mapping is not None:
                atom.SetAtomMapNum(mapping.get(atom.GetAtomMapNum(), 0))
        else:
            atom.SetAtomMapNum(0)
    return _canonical_smiles(mol)


def _split_components(smiles: str) -> tuple[str, ...]:
    mol = _parse(smiles)
    if mol is None:
        return ()
    return tuple(
        _canonical_fragment(_canonical_smiles(fragment))
        for fragment in Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=True)
    )


def _has_only_attachment_maps(mol: Chem.Mol, labels: set[int]) -> bool:
    maps = [atom.GetAtomMapNum() for atom in mol.GetAtoms() if atom.GetAtomicNum() == 0]
    return bool(maps) and set(maps) == labels and len(maps) == len(labels)


def _relabel_fragment(smiles: str, permutation: dict[int, int]) -> str:
    mol = _parse(smiles)
    if mol is None:
        return ""
    for atom in mol.GetAtoms():
        old = atom.GetAtomMapNum()
        atom.SetAtomMapNum(permutation.get(old, 0))
    return _canonical_smiles(mol)


def _hash_material(material: list[Any]) -> str:
    return sha256_json_array(material)


def _rational(numerator: int, denominator: int) -> str:
    value = Fraction(max(0, numerator), max(1, denominator))
    return f"{value.numerator}/{value.denominator}"


def _rational_value(value: str) -> Fraction:
    num, den = value.split("/", 1)
    return Fraction(int(num), int(den))


@dataclass(frozen=True, slots=True)
class _Embedding:
    variable: str
    changed_indices: tuple[int, ...]
    roots: tuple[int, ...]
    env1: tuple[str, ...]
    env2: tuple[str, ...]
    virtual: bool


@dataclass(frozen=True, slots=True)
class _View:
    cut_count: int
    conserved: str
    variable: str
    labels: tuple[int, ...]
    virtual: bool


@dataclass(frozen=True, slots=True)
class _Candidate:
    cut_count: int
    conserved: str
    removed: str
    added: str
    labels: tuple[int, ...]
    left_embedding: _Embedding
    right_embedding: _Embedding
    left_heavy: int
    right_heavy: int
    conserved_heavy: int
    fraction: str
    class_token: str
    material: dict[str, Any]
    material_bytes: bytes


def _swap_embedding_labels(embedding: _Embedding) -> _Embedding:
    return _Embedding(
        _relabel_fragment(embedding.variable, {1: 2, 2: 1}),
        embedding.changed_indices,
        tuple(reversed(embedding.roots)),
        tuple(reversed(embedding.env1)),
        tuple(reversed(embedding.env2)),
        embedding.virtual,
    )


def _normalize_dummy_permutation(candidate: _Candidate) -> _Candidate:
    """Collapse identity/swap encodings of one double-cut decomposition."""

    if candidate.cut_count != 2:
        return candidate
    left = _swap_embedding_labels(candidate.left_embedding)
    right = _swap_embedding_labels(candidate.right_embedding)
    conserved = _relabel_fragment(candidate.conserved, {1: 2, 2: 1})
    removed = _relabel_fragment(candidate.removed, {1: 2, 2: 1})
    added = _relabel_fragment(candidate.added, {1: 2, 2: 1})
    material = _candidate_material(
        2,
        conserved,
        removed,
        added,
        (1, 2),
        left,
        right,
        candidate.fraction,
        candidate.class_token,
    )
    alternate = _Candidate(
        2,
        conserved,
        removed,
        added,
        (1, 2),
        left,
        right,
        candidate.left_heavy,
        candidate.right_heavy,
        candidate.conserved_heavy,
        candidate.fraction,
        candidate.class_token,
        material,
        canonical_json(material),
    )
    return (
        alternate if alternate.material_bytes < candidate.material_bytes else candidate
    )


def _validate_record(record: MoleculeRecord) -> Chem.Mol:
    """Validate an accepted audited record before any chemistry is used."""

    if (
        not isinstance(record, MoleculeRecord)
        or record.status is not MoleculeStatus.ACCEPTED
    ):
        raise TransformationIntegrityError(("P6",))
    if record.structure_format.lower() != "smiles":
        raise TransformationIntegrityError(("P6",))
    if record.standardization_version != STANDARDIZATION_VERSION:
        raise TransformationIntegrityError(("P6",))
    if (
        record.standardized_structure is None
        or record.standardized_structure_hash is None
    ):
        raise TransformationIntegrityError(("P6",))
    raw = _parse(record.raw_structure.strip())
    standardized = _parse(record.standardized_structure)
    if raw is None or standardized is None:
        raise TransformationIntegrityError(("C1",))
    replay = standardize_molecule(
        MoleculeInput(
            record.molecule_id,
            record.raw_structure,
            record.structure_format,
            record.source,
            record.provenance,
        )
    )
    if replay.status is not MoleculeStatus.ACCEPTED:
        raise TransformationIntegrityError(("C1",))
    if (
        replay.standardized_structure != record.standardized_structure
        or replay.standardized_structure_hash != record.standardized_structure_hash
        or replay.standardization_version != record.standardization_version
        or replay.standardization_changed != record.standardization_changed
        or replay.input_fragments != record.input_fragments
    ):
        raise TransformationIntegrityError(("P6",))
    if not record.molecule_id:
        raise TransformationIntegrityError(("P6",))
    expected_hash = hashlib.sha256(
        record.standardized_structure.encode("utf-8")
    ).hexdigest()
    if record.standardized_structure_hash != expected_hash:
        raise TransformationIntegrityError(("P6",))
    if _canonical_smiles(standardized) != record.standardized_structure:
        raise TransformationIntegrityError(("P6",))
    return standardized


def _raw_has_multiple_fragments(record: MoleculeRecord, raw: Chem.Mol) -> bool:
    return len(record.input_fragments) > 1 or len(Chem.GetMolFrags(raw)) > 1


def _environment(mol: Chem.Mol, root: int, radius: int) -> str:
    clone = Chem.Mol(mol)
    for atom in clone.GetAtoms():
        atom.SetAtomMapNum(0)
    clone.GetAtomWithIdx(root).SetAtomMapNum(1)
    bond_ids = sorted(
        Chem.FindAtomEnvironmentOfRadiusN(
            clone, radius, root, useHs=False, enforceSize=False
        )
    )
    atoms = {root}
    for bond_id in bond_ids:
        bond = clone.GetBondWithIdx(bond_id)
        atoms.add(bond.GetBeginAtomIdx())
        atoms.add(bond.GetEndAtomIdx())
    return Chem.MolFragmentToSmiles(
        clone,
        atomsToUse=sorted(atoms),
        bondsToUse=bond_ids,
        rootedAtAtom=root,
        canonical=True,
        isomericSmiles=True,
        kekuleSmiles=False,
        allBondsExplicit=False,
        allHsExplicit=False,
    )


def _constant_query(
    constant: str,
) -> tuple[Chem.Mol, tuple[int, ...], tuple[int, ...]] | None:
    mol = _parse(constant)
    if mol is None:
        return None
    labels: list[int] = []
    old_roots: dict[int, int] = {}
    dummy_indices: list[int] = []
    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() == 0:
            label = atom.GetAtomMapNum()
            if label <= 0 or atom.GetDegree() != 1 or label in old_roots:
                return None
            neighbor = atom.GetNeighbors()[0].GetIdx()
            labels.append(label)
            old_roots[label] = neighbor
            dummy_indices.append(atom.GetIdx())
    labels.sort()
    if labels not in ([1], [1, 2]):
        return None
    rw = Chem.RWMol(mol)
    for idx in sorted(dummy_indices, reverse=True):
        rw.RemoveAtom(idx)
    query = rw.GetMol()
    remap: dict[int, int] = {}
    next_idx = 0
    for old in range(mol.GetNumAtoms()):
        if old not in dummy_indices:
            remap[old] = next_idx
            next_idx += 1
    roots = tuple(remap[old_roots[label]] for label in labels)
    original_h = tuple(
        mol.GetAtomWithIdx(old_roots[label]).GetNumImplicitHs() for label in labels
    )
    for atom in query.GetAtoms():
        atom.SetAtomMapNum(0)
    try:
        Chem.SanitizeMol(query)
    except Exception:
        return None
    for root, hydrogen_count in zip(roots, original_h, strict=True):
        # Removing an attachment dummy increases the root's parsed implicit-H
        # count by one.  Restore the original root H state as an explicit,
        # non-implicit query constraint; all other query atoms retain the
        # exact sanitized state.
        atom = query.GetAtomWithIdx(root)
        atom.SetNoImplicit(True)
        atom.SetNumExplicitHs(hydrogen_count)
    query.UpdatePropertyCache(strict=False)
    return query, roots, tuple(labels)


def _exact_crossing(
    mol: Chem.Mol,
    match: tuple[int, ...],
    roots: tuple[int, ...],
    labels: tuple[int, ...],
) -> tuple[dict[int, tuple[int, int, Chem.Bond]], set[int]] | None:
    mapped = set(match)
    if len(mapped) != len(match):
        return None
    crossings: list[tuple[int, int, Chem.Bond]] = []
    for query_root, label in zip(roots, labels, strict=True):
        target_root = match[query_root]
        for bond in mol.GetAtomWithIdx(target_root).GetBonds():
            other = bond.GetOtherAtomIdx(target_root)
            if other not in mapped:
                crossings.append((label, other, bond))
    for query_idx, target_idx in enumerate(match):
        if query_idx not in roots:
            if any(
                bond.GetOtherAtomIdx(target_idx) not in mapped
                for bond in mol.GetAtomWithIdx(target_idx).GetBonds()
            ):
                return None
    by_label: dict[int, tuple[int, int, Chem.Bond]] = {}
    for label, other, bond in crossings:
        if label in by_label:
            return None
        by_label[label] = (match[roots[labels.index(label)]], other, bond)
    if set(by_label) != set(labels) or len(crossings) != len(labels):
        return None
    return by_label, mapped


def _reconstruct_variable(
    mol: Chem.Mol,
    mapped: set[int],
    crossings: dict[int, tuple[int, int, Chem.Bond]],
) -> str | None:
    """Rebuild the variable side while retaining RDKit stereo annotations.

    A cut can remove one or both stereo reference atoms of a double bond.  In
    the reconstructed fragment those removed roots are represented by the
    attachment dummies, so bond stereo-atom indices must be remapped after all
    dummies and bonds exist.  Bond directions are copied as well: RDKit uses
    the directions on the single bonds adjacent to a double bond to serialize
    its E/Z state.
    """
    unmatched = sorted(set(range(mol.GetNumAtoms())) - mapped)
    rw = Chem.RWMol()
    old_to_new: dict[int, int] = {}
    for old in unmatched:
        atom = Chem.Atom(mol.GetAtomWithIdx(old))
        atom.SetAtomMapNum(0)
        old_to_new[old] = rw.AddAtom(atom)
    pending_bonds: list[tuple[Chem.Bond, Chem.Bond]] = []
    for bond in mol.GetBonds():
        begin, end = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        if begin in old_to_new and end in old_to_new:
            rw.AddBond(old_to_new[begin], old_to_new[end], bond.GetBondType())
            pending_bonds.append(
                (bond, rw.GetBondBetweenAtoms(old_to_new[begin], old_to_new[end]))
            )
    root_to_dummy: dict[int, int] = {}
    for label, (_root, other, bond) in crossings.items():
        dummy = Chem.Atom(0)
        dummy.SetAtomMapNum(label)
        dummy_idx = rw.AddAtom(dummy)
        if other not in old_to_new:
            return None
        rw.AddBond(old_to_new[other], dummy_idx, bond.GetBondType())
        root_to_dummy[_root] = dummy_idx
        pending_bonds.append(
            (bond, rw.GetBondBetweenAtoms(old_to_new[other], dummy_idx))
        )
    for source, target in pending_bonds:
        target.SetBondDir(source.GetBondDir())
        target.SetStereo(source.GetStereo())
        stereo_atoms = tuple(
            old_to_new.get(atom, root_to_dummy.get(atom, -1))
            for atom in source.GetStereoAtoms()
        )
        if source.GetStereo() is not Chem.BondStereo.STEREONONE:
            if len(stereo_atoms) != 2 or any(atom < 0 for atom in stereo_atoms):
                return None
            target.SetStereoAtoms(*stereo_atoms)
    result = rw.GetMol()
    try:
        with rdBase.BlockLogs():
            Chem.SanitizeMol(result)
        return _canonical_smiles(result)
    except Exception:
        return None


def _recover_embeddings(
    mol: Chem.Mol, constant: str, expected_variable: str, *, virtual: bool
) -> tuple[tuple[_Embedding, ...], bool]:
    query_info = _constant_query(constant)
    if query_info is None:
        return (), False
    query, roots, labels = query_info
    matches = mol.GetSubstructMatches(
        query, uniquify=False, useChirality=True, maxMatches=MAX_EMBEDDING_MATCHES
    )
    if len(matches) == MAX_EMBEDDING_MATCHES:
        return (), True
    expected_variable = _canonical_fragment(expected_variable)
    output: list[_Embedding] = []
    for match in matches:
        mapped = set(match)
        variable: str | None
        if virtual:
            if mapped != set(range(mol.GetNumAtoms())) or any(
                mol.GetAtomWithIdx(match[root]).GetNumImplicitHs() < 1 for root in roots
            ):
                continue
            crossings: dict[int, tuple[int, int, Chem.Bond]] = {}
            variable = HYDROGEN_SIDE_TOKEN
        else:
            crossing_info = _exact_crossing(mol, match, roots, labels)
            if crossing_info is None:
                continue
            crossings, mapped = crossing_info
            variable = _reconstruct_variable(mol, mapped, crossings)
            if variable is None or variable != expected_variable:
                continue
        target_roots = tuple(match[root] for root in roots)
        env1 = tuple(_environment(mol, root, 1) for root in target_roots)
        env2 = tuple(_environment(mol, root, 2) for root in target_roots)
        changed = (
            ()
            if virtual
            else tuple(
                idx
                for idx in sorted(set(range(mol.GetNumAtoms())) - mapped)
                if mol.GetAtomWithIdx(idx).GetAtomicNum() > 1
            )
        )
        output.append(_Embedding(variable, changed, target_roots, env1, env2, virtual))
    unique: dict[bytes, _Embedding] = {}
    for item in output:
        unique.setdefault(
            canonical_json(
                {
                    "variable": item.variable,
                    "changed": item.changed_indices,
                    "roots": item.roots,
                    "env1": item.env1,
                    "env2": item.env2,
                }
            ),
            item,
        )
    return tuple(unique.values()), False


def _virtual_constant_views(mol: Chem.Mol) -> tuple[_View, ...]:
    views: list[_View] = []
    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() <= 1 or atom.GetNumImplicitHs() < 1:
            continue
        rw = Chem.RWMol(mol)
        for existing in rw.GetAtoms():
            existing.SetAtomMapNum(0)
        dummy = Chem.Atom(0)
        dummy.SetAtomMapNum(1)
        dummy_idx = rw.AddAtom(dummy)
        rw.AddBond(atom.GetIdx(), dummy_idx, Chem.BondType.SINGLE)
        candidate = rw.GetMol()
        try:
            with rdBase.BlockLogs():
                Chem.SanitizeMol(candidate)
        except Exception:
            continue
        views.append(
            _View(1, _canonical_smiles(candidate), HYDROGEN_SIDE_TOKEN, (1,), True)
        )
    return tuple(views)


def _ordinary_views(mol: Chem.Mol) -> tuple[_View, ...]:
    result: list[_View] = []
    for min_cuts, max_cuts, count in ((1, 1, 1), (2, 2, 2)):
        fragments = rdMMPA.FragmentMol(
            mol,
            min_cuts,
            max_cuts,
            MAX_CUT_BONDS,
            MMP_PATTERN,
            False,
        )
        for core, sidechains in fragments:
            if count == 1:
                components = _split_components(sidechains)
                if len(components) != 2:
                    continue
                if any(
                    not _has_only_attachment_maps(_parse(component) or mol, {1})
                    for component in components
                ):
                    continue
                for constant_idx in (0, 1):
                    result.append(
                        _View(
                            1,
                            components[constant_idx],
                            components[1 - constant_idx],
                            (1,),
                            False,
                        )
                    )
            else:
                variable = _canonical_fragment(core)
                constant = _canonical_fragment(sidechains)
                core_mol, variable_mol = _parse(constant), _parse(variable)
                if (
                    core_mol is None
                    or variable_mol is None
                    or not _has_only_attachment_maps(core_mol, {1, 2})
                    or not _has_only_attachment_maps(variable_mol, {1, 2})
                ):
                    continue
                for permutation in ({1: 1, 2: 2}, {1: 2, 2: 1}):
                    result.append(
                        _View(
                            2,
                            _relabel_fragment(constant, permutation),
                            _relabel_fragment(variable, permutation),
                            (1, 2),
                            False,
                        )
                    )
    return tuple(result)


def _class_token(removed: str, added: str, cut_count: int) -> str:
    removed_heavy = _fragment_heavy_count(removed)
    added_heavy = _fragment_heavy_count(added)
    if cut_count == 2:
        return "double_cut_exchange"
    if removed == HYDROGEN_SIDE_TOKEN and added_heavy > 0:
        return "single_cut_growth"
    if added == HYDROGEN_SIDE_TOKEN and removed_heavy > 0:
        return "single_cut_contraction"
    if removed_heavy > 0 and added_heavy > 0:
        return "single_cut_exchange"
    return "single_cut_exchange"


def _candidate_material(
    cut_count: int,
    conserved: str,
    removed: str,
    added: str,
    labels: tuple[int, ...],
    left: _Embedding,
    right: _Embedding,
    fraction: str,
    class_token: str,
) -> dict[str, Any]:
    return {
        "cut_count": cut_count,
        "conserved_core_smiles": conserved,
        "removed_labeled_fragment": removed,
        "added_labeled_fragment": added,
        "attachment_labels_array": list(labels),
        "left_attachment_environment_radius_1": list(left.env1),
        "right_attachment_environment_radius_1": list(right.env1),
        "left_attachment_environment_radius_2": list(left.env2),
        "right_attachment_environment_radius_2": list(right.env2),
        "left_virtual_h_eligible": left.virtual,
        "right_virtual_h_eligible": right.virtual,
        "changed_left_atom_indices": list(left.changed_indices),
        "changed_right_atom_indices": list(right.changed_indices),
        "changed_heavy_atom_fraction": fraction,
        "stereo": {"changed": False, "elements": []},
        "class": class_token,
    }


def _make_candidate(
    left_mol: Chem.Mol,
    right_mol: Chem.Mol,
    left_view: _View,
    right_view: _View,
) -> tuple[tuple[_Candidate, ...], bool]:
    if (
        left_view.conserved != right_view.conserved
        or left_view.labels != right_view.labels
    ):
        return (), False
    left_embeddings, left_cap = _recover_embeddings(
        left_mol,
        left_view.conserved,
        left_view.variable,
        virtual=left_view.virtual,
    )
    right_embeddings, right_cap = _recover_embeddings(
        right_mol,
        right_view.conserved,
        right_view.variable,
        virtual=right_view.virtual,
    )
    if left_cap or right_cap:
        return (), True
    output: list[_Candidate] = []
    left_heavy = _heavy_count(left_mol)
    right_heavy = _heavy_count(right_mol)
    conserved_heavy = _fragment_heavy_count(left_view.conserved)
    fraction = _rational(
        _fragment_heavy_count(left_view.variable)
        + _fragment_heavy_count(right_view.variable),
        left_heavy + right_heavy,
    )
    class_token = _class_token(
        left_view.variable, right_view.variable, left_view.cut_count
    )
    for left_embedding in left_embeddings:
        for right_embedding in right_embeddings:
            material = _candidate_material(
                left_view.cut_count,
                left_view.conserved,
                left_view.variable,
                right_view.variable,
                left_view.labels,
                left_embedding,
                right_embedding,
                fraction,
                class_token,
            )
            material_bytes = canonical_json(material)
            output.append(
                _normalize_dummy_permutation(
                    _Candidate(
                        left_view.cut_count,
                        left_view.conserved,
                        left_view.variable,
                        right_view.variable,
                        left_view.labels,
                        left_embedding,
                        right_embedding,
                        left_heavy,
                        right_heavy,
                        conserved_heavy,
                        fraction,
                        class_token,
                        material,
                        material_bytes,
                    )
                )
            )
    return tuple(output), False


def _rank_key(candidate: _Candidate) -> tuple[int, int, Fraction, int, int]:
    r1 = sum(
        a == b
        for a, b in zip(
            candidate.left_embedding.env1,
            candidate.right_embedding.env1,
            strict=True,
        )
    )
    r2 = sum(
        a == b
        for a, b in zip(
            candidate.left_embedding.env2,
            candidate.right_embedding.env2,
            strict=True,
        )
    )
    return (
        -candidate.conserved_heavy,
        candidate.cut_count,
        _rational_value(candidate.fraction),
        -r1,
        -r2,
    )


def _empty_direction(
    pair_id: str,
    anchor: MoleculeRecord,
    analog: MoleculeRecord,
    status: str,
    failure: str,
) -> DirectionalTransformation:
    assert anchor.standardized_structure_hash is not None
    assert analog.standardized_structure_hash is not None
    direction_id = _hash_material(
        [
            EXTRACTION_SPEC_RECEIPT,
            pair_id,
            anchor.standardized_structure_hash,
            analog.standardized_structure_hash,
        ]
    )
    return DirectionalTransformation(
        direction_id,
        anchor.molecule_id,
        analog.molecule_id,
        anchor.standardized_structure_hash,
        analog.standardized_structure_hash,
        status,
        failure,
        None,
        "",
        "",
        "",
        (),
        (),
        (),
        (),
        (),
        False,
        False,
        (),
        (),
        None,
        None,
        None,
        "",
        False,
        (),
        "",
        "",
        "",
        "",
        "",
        None,
        "",
        status == "AMBIGUOUS",
        _WARNING.get(failure, ()),
    )


def _direction_from_candidate(
    pair_id: str,
    anchor: MoleculeRecord,
    analog: MoleculeRecord,
    candidate: _Candidate,
) -> DirectionalTransformation:
    assert anchor.standardized_structure_hash is not None
    assert analog.standardized_structure_hash is not None
    exact_id = _hash_material(
        [
            EXTRACTION_SPEC_RECEIPT,
            candidate.removed,
            candidate.added,
            list(candidate.labels),
        ]
    )
    class_id = _hash_material([EXTRACTION_SPEC_RECEIPT, candidate.class_token])
    env1 = _hash_material(
        [
            EXTRACTION_SPEC_RECEIPT,
            exact_id,
            list(candidate.left_embedding.env1),
            list(candidate.right_embedding.env1),
        ]
    )
    env2 = _hash_material(
        [
            EXTRACTION_SPEC_RECEIPT,
            exact_id,
            list(candidate.left_embedding.env2),
            list(candidate.right_embedding.env2),
        ]
    )
    direction_id = _hash_material(
        [
            EXTRACTION_SPEC_RECEIPT,
            pair_id,
            anchor.standardized_structure_hash,
            analog.standardized_structure_hash,
        ]
    )
    undirected = _hash_material(
        [
            EXTRACTION_SPEC_RECEIPT,
            sorted([candidate.removed, candidate.added]),
            len(candidate.labels),
        ]
    )
    return DirectionalTransformation(
        direction_id,
        anchor.molecule_id,
        analog.molecule_id,
        anchor.standardized_structure_hash,
        analog.standardized_structure_hash,
        "VALID_SINGLE" if candidate.cut_count == 1 else "VALID_DOUBLE",
        "",
        candidate.cut_count,
        candidate.conserved,
        candidate.removed,
        candidate.added,
        candidate.labels,
        candidate.left_embedding.env1,
        candidate.right_embedding.env1,
        candidate.left_embedding.env2,
        candidate.right_embedding.env2,
        candidate.left_embedding.virtual,
        candidate.right_embedding.virtual,
        candidate.left_embedding.changed_indices,
        candidate.right_embedding.changed_indices,
        candidate.conserved_heavy,
        candidate.left_heavy,
        candidate.right_heavy,
        candidate.fraction,
        False,
        (),
        exact_id,
        class_id,
        env1,
        env2,
        undirected,
        candidate.material,
        hashlib.sha256(candidate.material_bytes).hexdigest(),
        False,
        (),
    )


def _reverse_candidate(candidate: _Candidate) -> _Candidate:
    class_token = _class_token(candidate.added, candidate.removed, candidate.cut_count)
    material = _candidate_material(
        candidate.cut_count,
        candidate.conserved,
        candidate.added,
        candidate.removed,
        candidate.labels,
        candidate.right_embedding,
        candidate.left_embedding,
        candidate.fraction,
        class_token,
    )
    return _Candidate(
        candidate.cut_count,
        candidate.conserved,
        candidate.added,
        candidate.removed,
        candidate.labels,
        candidate.right_embedding,
        candidate.left_embedding,
        candidate.right_heavy,
        candidate.left_heavy,
        candidate.conserved_heavy,
        candidate.fraction,
        class_token,
        material,
        canonical_json(material),
    )


def _pair_similarity(left: Chem.Mol, right: Chem.Mol) -> float:
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=2, fpSize=4096, includeChirality=True
    )
    return float(
        DataStructs.TanimotoSimilarity(
            generator.GetFingerprint(left), generator.GetFingerprint(right)
        )
    )


def _result_invalid(
    left: MoleculeRecord,
    right: MoleculeRecord,
    pair_id: str,
    similarity: float,
    status: str,
    failure: str,
    *,
    tie_material: tuple[dict[str, Any], ...] = (),
) -> TransformationPairResult:
    a_to_b = _empty_direction(pair_id, left, right, status, failure)
    b_to_a = _empty_direction(pair_id, right, left, status, failure)
    tie_digest = hashlib.sha256(canonical_json(list(tie_material))).hexdigest()
    return TransformationPairResult(
        pair_id,
        left.molecule_id,
        right.molecule_id,
        cast(str, left.standardized_structure_hash),
        cast(str, right.standardized_structure_hash),
        status,
        failure,
        similarity,
        a_to_b,
        b_to_a,
        None,
        "",
        "",
        "",
        (),
        (),
        (),
        (),
        None,
        None,
        (),
        (),
        None,
        None,
        None,
        "",
        None,
        (),
        None,
        "",
        len(tie_material),
        tie_material,
        tie_digest,
        status == "AMBIGUOUS",
        _WARNING.get(failure, ()),
    )


def extract_ordinary_transformation_pair(
    left: MoleculeRecord, right: MoleculeRecord
) -> TransformationPairResult:
    """Extract one canonical ordinary non-stereo MMP pair.

    The input records are ordered by standardized structure hash and molecule
    ID.  The returned pair is structural-only; it does not read assay state or
    any target-bearing field.
    """

    left_mol = _validate_record(left)
    right_mol = _validate_record(right)
    assert left.standardized_structure_hash is not None
    assert right.standardized_structure_hash is not None
    if left.standardized_structure_hash == right.standardized_structure_hash:
        if left.molecule_id != right.molecule_id:
            raise TransformationIntegrityError(("C5",))
        raise TransformationIntegrityError(("P6",))
    if (right.standardized_structure_hash, right.molecule_id) < (
        left.standardized_structure_hash,
        left.molecule_id,
    ):
        left, right = right, left
        left_mol, right_mol = right_mol, left_mol
    pair_id = _hash_material(
        [
            EXTRACTION_SPEC_RECEIPT,
            left.standardized_structure_hash,
            right.standardized_structure_hash,
        ]
    )
    similarity = _pair_similarity(left_mol, right_mol)
    raw_left = _parse(left.raw_structure.strip())
    raw_right = _parse(right.raw_structure.strip())
    assert raw_left is not None and raw_right is not None
    if _raw_has_multiple_fragments(left, raw_left) or _raw_has_multiple_fragments(
        right, raw_right
    ):
        return _result_invalid(
            left, right, pair_id, similarity, "STANDARDIZATION_HAZARD", "C2"
        )
    if left.standardization_changed or right.standardization_changed:
        return _result_invalid(
            left, right, pair_id, similarity, "STANDARDIZATION_HAZARD", "C6"
        )

    views_left = (*_ordinary_views(left_mol), *_virtual_constant_views(left_mol))
    views_right = (*_ordinary_views(right_mol), *_virtual_constant_views(right_mol))
    candidates: list[_Candidate] = []
    capped = False
    for left_view in views_left:
        for right_view in views_right:
            found, did_cap = _make_candidate(left_mol, right_mol, left_view, right_view)
            candidates.extend(found)
            capped = capped or did_cap
    dedup: dict[bytes, _Candidate] = {}
    for candidate in candidates:
        dedup.setdefault(candidate.material_bytes, candidate)
    candidates = list(dedup.values())
    if capped:
        return _result_invalid(left, right, pair_id, similarity, "AMBIGUOUS", "S2")
    if not candidates:
        return _result_invalid(left, right, pair_id, similarity, "UNSUPPORTED", "S6")
    candidates.sort(key=lambda candidate: candidate.material_bytes)
    best_key = min(_rank_key(candidate) for candidate in candidates)
    tied = tuple(
        candidate for candidate in candidates if _rank_key(candidate) == best_key
    )
    tied_material = tuple(
        candidate.material
        for candidate in sorted(tied, key=lambda item: item.material_bytes)
    )
    if len(tied) > 1:
        return _result_invalid(
            left,
            right,
            pair_id,
            similarity,
            "AMBIGUOUS",
            "S2",
            tie_material=tied_material,
        )
    candidate = tied[0]
    left_hash = cast(str, left.standardized_structure_hash)
    right_hash = cast(str, right.standardized_structure_hash)
    reverse = _reverse_candidate(candidate)
    if reverse.material_bytes != canonical_json(reverse.material):
        return _result_invalid(left, right, pair_id, similarity, "AMBIGUOUS", "S3")
    a_to_b = _direction_from_candidate(pair_id, left, right, candidate)
    b_to_a = _direction_from_candidate(pair_id, right, left, reverse)
    if a_to_b.exact_transformation_id == b_to_a.exact_transformation_id and (
        candidate.removed != candidate.added
    ):
        return _result_invalid(left, right, pair_id, similarity, "AMBIGUOUS", "S3")
    return TransformationPairResult(
        pair_id,
        left.molecule_id,
        right.molecule_id,
        left_hash,
        right_hash,
        a_to_b.extraction_status,
        "",
        similarity,
        a_to_b,
        b_to_a,
        candidate.cut_count,
        candidate.conserved,
        candidate.removed,
        candidate.added,
        candidate.left_embedding.env1,
        candidate.right_embedding.env1,
        candidate.left_embedding.env2,
        candidate.right_embedding.env2,
        candidate.left_embedding.virtual,
        candidate.right_embedding.virtual,
        candidate.left_embedding.changed_indices,
        candidate.right_embedding.changed_indices,
        candidate.conserved_heavy,
        candidate.left_heavy,
        candidate.right_heavy,
        candidate.fraction,
        False,
        (),
        candidate.material,
        hashlib.sha256(candidate.material_bytes).hexdigest(),
        1,
        (candidate.material,),
        hashlib.sha256(canonical_json([candidate.material])).hexdigest(),
        False,
        (),
    )


__all__ = [
    "extract_ordinary_transformation_pair",
    "MAX_EMBEDDING_MATCHES",
    "MAX_CUT_BONDS",
    "MMP_PATTERN",
]

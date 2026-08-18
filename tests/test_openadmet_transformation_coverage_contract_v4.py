from __future__ import annotations

import copy
import ctypes
import errno
import hashlib
import json
import os
import platform
import shutil
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest
from rdkit import Chem

ROOT = Path(__file__).parents[1]
PATH = ROOT / "benchmarks/openadmet_cyp_2026/transformation_coverage_contract_v4.json"
PARENT = ROOT / "benchmarks/openadmet_cyp_2026/transformation_coverage_contract_v3.json"
EMPTY_DIGEST = hashlib.sha256(b"[]").hexdigest()


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AssertionError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path = PATH) -> dict[str, Any]:
    value = json.loads(path.read_bytes(), object_pairs_hook=_unique)
    assert isinstance(value, dict)
    return value


def _atom_fixed(atom: Chem.Atom) -> tuple[Any, ...]:
    return (
        atom.GetAtomicNum(),
        atom.GetIsotope(),
        atom.GetFormalCharge(),
        atom.GetNumRadicalElectrons(),
        atom.GetIsAromatic(),
        atom.GetAtomMapNum(),
    )


def _hydrogen_partition(atom: Chem.Atom) -> tuple[int, int, bool]:
    return atom.GetNumExplicitHs(), atom.GetNumImplicitHs(), atom.GetNoImplicit()


def _graph_map(
    source: Chem.Mol,
    target: Chem.Mol,
    mapping: tuple[int, ...],
    *,
    reference_target_tetra: frozenset[int] | None = None,
) -> bool:
    if (
        source.GetNumAtoms() != target.GetNumAtoms()
        or source.GetNumBonds() != target.GetNumBonds()
        or len(mapping) != source.GetNumAtoms()
        or set(mapping) != set(range(target.GetNumAtoms()))
    ):
        return False
    for source_index, target_index in enumerate(mapping):
        source_atom = source.GetAtomWithIdx(source_index)
        target_atom = target.GetAtomWithIdx(target_index)
        if _atom_fixed(source_atom) != _atom_fixed(target_atom):
            return False
        source_h = _hydrogen_partition(source_atom)
        target_h = _hydrogen_partition(target_atom)
        if source_h == target_h:
            continue
        if not (
            reference_target_tetra is not None
            and target_index in reference_target_tetra
            and source_h == (0, 1, False)
            and target_h == (1, 0, True)
            and source_atom.GetTotalNumHs() == target_atom.GetTotalNumHs() == 1
        ):
            return False
    directional = {
        Chem.BondType.DATIVE,
        Chem.BondType.DATIVEL,
        Chem.BondType.DATIVER,
        Chem.BondType.DATIVEONE,
    }
    for source_bond in source.GetBonds():
        target_bond = target.GetBondBetweenAtoms(
            mapping[source_bond.GetBeginAtomIdx()],
            mapping[source_bond.GetEndAtomIdx()],
        )
        if target_bond is None or (
            source_bond.GetBondType(),
            source_bond.GetIsAromatic(),
            source_bond.GetIsConjugated(),
        ) != (
            target_bond.GetBondType(),
            target_bond.GetIsAromatic(),
            target_bond.GetIsConjugated(),
        ):
            return False
        if source_bond.GetBondType() in directional and (
            mapping[source_bond.GetBeginAtomIdx()] != target_bond.GetBeginAtomIdx()
            or mapping[source_bond.GetEndAtomIdx()] != target_bond.GetEndAtomIdx()
        ):
            return False
    return True


def _tetra_centers(molecule: Chem.Mol) -> frozenset[int]:
    return frozenset(
        int(info.centeredOn)
        for info in Chem.FindPotentialStereo(molecule, cleanIt=True, flagPossible=True)
        if info.type == Chem.StereoType.Atom_Tetrahedral
        and info.specified == Chem.StereoSpecified.Specified
    )


def _stereo_preflight_flag(molecule: Chem.Mol, policy: Mapping[str, Any]) -> bool:
    allowed_atoms = set(policy["allowed_atom_chiral_tags"])
    allowed_bonds = set(policy["allowed_bond_stereo_tags"])
    return (
        bool(molecule.GetStereoGroups())
        or any(
            str(atom.GetChiralTag()) not in allowed_atoms
            for atom in molecule.GetAtoms()
        )
        or any(
            str(bond.GetStereo()) not in allowed_bonds for bond in molecule.GetBonds()
        )
    )


def _canonical_nonstereo_graph(molecule: Chem.Mol) -> str:
    clone = Chem.Mol(molecule)
    Chem.RemoveStereochemistry(clone)
    return Chem.MolToSmiles(
        clone,
        canonical=True,
        isomericSmiles=True,
        kekuleSmiles=False,
        allBondsExplicit=False,
        allHsExplicit=False,
    )


def _stereo_precedence(
    left: Chem.Mol, right: Chem.Mol, policy: Mapping[str, Any]
) -> str:
    preflight_flag = _stereo_preflight_flag(left, policy) or _stereo_preflight_flag(
        right, policy
    )
    if _canonical_nonstereo_graph(left) != _canonical_nonstereo_graph(right):
        return "ORDINARY_MMP"
    if preflight_flag:
        return "AMBIGUOUS/C3"
    return "STEREO_ONLY"


def _s2_result(
    contract: Mapping[str, Any], returned_count: int, materials: list[dict[str, Any]]
) -> tuple[int, list[dict[str, Any]], str]:
    cap = contract["extraction"]["candidate_generation"][
        "maximum_constant_embedding_matches"
    ]
    if returned_count == cap:
        encoded = b"[]"
        return 0, [], hashlib.sha256(encoded).hexdigest()
    ordered = sorted(
        materials,
        key=lambda value: json.dumps(
            value, sort_keys=True, separators=(",", ":")
        ).encode(),
    )
    encoded = json.dumps(ordered, sort_keys=True, separators=(",", ":")).encode()
    return len(ordered), ordered, hashlib.sha256(encoded).hexdigest()


def _expand_queries(queries: list[str]) -> list[tuple[int, str]]:
    if not 1 <= len(queries) <= 10 or len(queries) != len(set(queries)):
        raise ValueError("invalid public query array")
    return list(enumerate(queries, start=1))


def _exact_fields(value: Mapping[str, Any], fields: list[str]) -> None:
    if set(value) != set(fields):
        raise ValueError("field set mismatch")


def _validate_hash(value: Any) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError("invalid sha256")


def _validate_base_receipt(receipt: Mapping[str, Any]) -> None:
    if (
        isinstance(receipt["bytes"], bool)
        or not isinstance(receipt["bytes"], int)
        or receipt["bytes"] <= 0
    ):
        raise ValueError("invalid byte count")
    _validate_hash(receipt["sha256"])


def _validate_receipt_maps(
    manifest: Mapping[str, Any], schemas: Mapping[str, Any]
) -> None:
    schema = schemas["manifest.json"]
    runtime_schema = schema["runtime"]
    runtime = manifest["runtime"]
    _exact_fields(runtime, runtime_schema["fields_exact"])
    if {key: runtime[key] for key in runtime_schema["required_values"]} != (
        runtime_schema["required_values"]
    ):
        raise ValueError("runtime value mismatch")
    commit = runtime["code_commit"]
    if (
        not isinstance(commit, str)
        or len(commit) != 40
        or any(char not in "0123456789abcdef" for char in commit)
    ):
        raise ValueError("commit mismatch")

    for map_name in ("input_receipts", "source_receipts", "output_receipts"):
        receipt_schema = schema[map_name]
        receipts = manifest[map_name]
        if list(sorted(receipts)) != receipt_schema["keys_exact_sorted"]:
            raise ValueError(f"{map_name} key mismatch")
    inputs = manifest["input_receipts"]
    for key in schema["input_receipts"]["csv_keys"]:
        receipt = inputs[key]
        _exact_fields(receipt, schema["input_receipts"]["csv_value_fields_exact"])
        _validate_base_receipt(receipt)
        if receipt["columns"] != schema["input_receipts"]["csv_columns_exact"][key]:
            raise ValueError("input columns mismatch")
        if receipt["rows"] != schema["input_receipts"]["csv_rows_exact"][key]:
            raise ValueError("input rows mismatch")
    _exact_fields(
        inputs[schema["input_receipts"]["manifest_key"]],
        schema["input_receipts"]["manifest_value_fields_exact"],
    )
    _validate_base_receipt(inputs["manifest.json"])
    for key, receipt in manifest["source_receipts"].items():
        _exact_fields(receipt, schema["source_receipts"]["value_fields_exact"])
        _validate_base_receipt(receipt)
        if receipt["rows"] != schema["source_receipts"]["rows_exact"][key]:
            raise ValueError("source rows mismatch")
    outputs = manifest["output_receipts"]
    for key in schema["output_receipts"]["csv_keys"]:
        receipt = outputs[key]
        _exact_fields(receipt, schema["output_receipts"]["csv_value_fields_exact"])
        _validate_base_receipt(receipt)
        if receipt["columns"] != schemas[key]["columns"]:
            raise ValueError("output columns mismatch")
        expected_rows = schema["output_receipts"]["csv_rows"][key]
        if isinstance(expected_rows, int) and receipt["rows"] != expected_rows:
            raise ValueError("output rows mismatch")
    _exact_fields(
        outputs[schema["output_receipts"]["json_key"]],
        schema["output_receipts"]["json_value_fields_exact"],
    )
    _validate_base_receipt(outputs[schema["output_receipts"]["json_key"]])


def _trusted_destination(destination: Path) -> bool:
    if ".." in destination.parts or destination.exists() or destination.is_symlink():
        return False
    current = destination.parent
    while current != current.parent:
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            return False
        current = current.parent
    return os.name == "posix" and platform.system() == "Linux"


def _publish_noreplace(
    destination: Path,
    files: Mapping[str, bytes],
    *,
    before_rename: Callable[[], None] | None = None,
) -> bool:
    if not _trusted_destination(destination):
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".r4-v4-test-", dir=destination.parent))
    try:
        for name, data in files.items():
            path = stage / name
            path.write_bytes(data)
            path.chmod(0o444)
        stage.chmod(0o555)
        if before_rename is not None:
            before_rename()
        renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        result = renameat2(
            -100,
            os.fsencode(stage.absolute()),
            -100,
            os.fsencode(destination.absolute()),
            1,
        )
        if result != 0:
            assert ctypes.get_errno() in {errno.EEXIST, errno.ENOTEMPTY}
            return False
        stage = Path()
        return True
    finally:
        if stage != Path() and stage.exists():
            stage.chmod(0o755)
            shutil.rmtree(stage)


def test_v4_is_self_contained_and_binds_exact_immutable_v3() -> None:
    contract = _load()
    assert hashlib.sha256(PATH.read_bytes()).hexdigest() == (
        "cacd1f77215e36a17f03553680d71263425638c290a39d33c397e43b2c35550f"
    )
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == (
        "f5e1862682c1d2a3e34fcf530c9aad42cbd4e4538488eca1a4c5508443f61db5"
    )
    assert contract["parent"] == {
        "path": "benchmarks/openadmet_cyp_2026/transformation_coverage_contract_v3.json",
        "schema_version": (
            "cypshift.openadmet_cyp_2026.transformation_coverage_contract.v3"
        ),
        "sha256": "f5e1862682c1d2a3e34fcf530c9aad42cbd4e4538488eca1a4c5508443f61db5",
        "immutable": True,
    }
    assert contract["inheritance"]["mode"] == "full_self_contained_snapshot"
    assert contract["inheritance"]["recursive_merge"] is False
    assert contract["inheritance"]["parent_runtime_access_required"] is False
    assert "v4 file alone" in contract["inheritance"]["implementation_source"]
    with pytest.raises(AssertionError, match="duplicate JSON key"):
        json.loads('{"x":1,"x":2}', object_pairs_hook=_unique)


def test_receipt_ids_and_all_five_output_schemas_are_v4() -> None:
    contract = _load()
    extraction = contract["extraction"]
    receipt = extraction["extraction_spec_receipt"]
    material = {"extraction_spec_id": extraction["extraction_spec_id"]}
    material.update({key: extraction[key] for key in receipt["receipt_subtrees"]})
    encoded = json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert extraction["extraction_spec_id"] == "cypshift.trace.mmp.v4"
    assert receipt["sha256"] == hashlib.sha256(encoded).hexdigest()
    assert receipt["sha256"] == (
        "59e3bd3390658bab854be52f88ef7de0164aae6e99ad48b0b0feb04c68669950"
    )
    ids = extraction["ids"]
    assert ids["v4_spec_hash"].startswith("The exact extraction")
    assert all(
        value[0] == "v4_spec_hash"
        for key, value in ids.items()
        if key.endswith("_material") and isinstance(value, list)
    )
    for schema in contract["outputs"]["schemas"].values():
        assert schema["schema_version"].endswith(".v4")


def test_tetra_lambda_rho_repair_keeps_phi_atom_maps_and_dative_exact() -> None:
    left = Chem.MolFromSmiles("C[C@H](O)Cl")
    right = Chem.MolFromSmiles("C[C@@H](O)Cl")
    assert left is not None and right is not None
    left_centers, right_centers = _tetra_centers(left), _tetra_centers(right)
    left_no, right_no = Chem.Mol(left), Chem.Mol(right)
    Chem.RemoveStereochemistry(left_no)
    Chem.RemoveStereochemistry(right_no)
    reference_smiles = Chem.MolToSmiles(
        left_no,
        canonical=True,
        isomericSmiles=True,
        kekuleSmiles=False,
        allBondsExplicit=False,
        allHsExplicit=False,
    )
    reference = Chem.MolFromSmiles(reference_smiles)
    assert reference is not None
    phi = right_no.GetSubstructMatches(
        left_no, uniquify=False, useChirality=False, maxMatches=0
    )[0]
    lambda_map = left_no.GetSubstructMatches(
        reference, uniquify=False, useChirality=False, maxMatches=0
    )[0]
    rho = tuple(phi[lambda_map[index]] for index in range(len(lambda_map)))
    assert _graph_map(left_no, right_no, phi)
    assert not _graph_map(reference, left_no, lambda_map)
    assert not _graph_map(reference, right_no, rho)
    assert _graph_map(
        reference, left_no, lambda_map, reference_target_tetra=left_centers
    )
    assert _graph_map(reference, right_no, rho, reference_target_tetra=right_centers)

    mapped_left = Chem.MolFromSmiles("[CH3:1][CH3:2]")
    mapped_right = Chem.MolFromSmiles("[CH3:2][CH3:1]")
    assert mapped_left is not None and mapped_right is not None
    assert not _graph_map(
        mapped_left, mapped_right, (0, 1), reference_target_tetra=frozenset()
    )
    dative = Chem.MolFromSmiles("C[C@H](F)N->N[C@@H](F)C")
    assert dative is not None
    dative_centers = _tetra_centers(dative)
    Chem.RemoveStereochemistry(dative)
    false_map = dative.GetSubstructMatches(
        dative, uniquify=False, useChirality=False, maxMatches=0
    )[1]
    assert not _graph_map(
        dative, dative, false_map, reference_target_tetra=dative_centers
    )


def test_sp1_graph_changing_preflight_delegates_before_c3() -> None:
    contract = _load()
    stereo = contract["extraction"]["fragmentation"]["stereo_policy"]
    preflight = stereo["raw_stereo_preflight"]
    left = Chem.MolFromSmiles("[C@SP1](F)(Cl)(Br)CCO")
    graph_changed = Chem.MolFromSmiles("[C@SP1](F)(Cl)(Br)CCN")
    identical = Chem.MolFromSmiles("[C@SP1](F)(Cl)(Br)CCO")
    assert left is not None and graph_changed is not None and identical is not None
    assert _stereo_preflight_flag(left, preflight)
    assert _canonical_nonstereo_graph(left) != _canonical_nonstereo_graph(graph_changed)
    assert _stereo_precedence(left, graph_changed, preflight) == "ORDINARY_MMP"
    assert _canonical_nonstereo_graph(left) == _canonical_nonstereo_graph(identical)
    assert _stereo_precedence(left, identical, preflight) == "AMBIGUOUS/C3"

    precedence = stereo["precedence"]
    assert "internally" in precedence
    assert "before acting" in precedence
    assert "discard the flags from row-state selection" in precedence
    assert "C3 is not applicable to that graph-changing pair" in precedence
    for predicate in (preflight["enhanced_stereo"], preflight["unsupported_raw_tags"]):
        assert "only for an identical-graph stereo-only pair" in predicate
    assert "graph mismatch delegates" in preflight["molecules"]
    assert (
        "Graph-mismatched pairs instead continue ordinary"
        in stereo["invalid_stereo_row"]
    )
    assert contract["extraction"]["hazards"]["stereochemistry_unspecified_or_mixed"][
        "policy"
    ] == (
        "block stereo-specific record; ordinary non-stereo MMP records remain eligible"
    )


def test_variable_reconstruction_preserves_full_bond_stereo_state() -> None:
    reconstruction = _load()["extraction"]["canonicalization"][
        "constant_embedding_recovery"
    ]["variable_reconstruction"]
    for token in (
        "Bond.GetBondDir()",
        "Bond.GetStereo()",
        "Bond.GetStereoAtoms()",
        "old-to-new atom map",
        "crossing bond",
        "reject the embedding",
    ):
        assert token in reconstruction
    assert "preserve/remap its full bond direction/stereo state" in reconstruction


def test_s2_cap_and_decomposition_tie_have_executable_distinct_sentinels() -> None:
    contract = _load()
    cap = contract["extraction"]["candidate_generation"][
        "maximum_constant_embedding_matches"
    ]
    assert _s2_result(contract, cap, [{"ignored": True}]) == (0, [], EMPTY_DIGEST)
    count, materials, digest = _s2_result(
        contract, 2, [{"fragment": "b"}, {"fragment": "a"}]
    )
    assert count == 2
    assert materials == [{"fragment": "a"}, {"fragment": "b"}]
    assert digest != EMPTY_DIGEST
    tie = contract["extraction"]["canonicalization"]["tie_serialization"]
    assert tie["ambiguous_s2_embedding_cap"]["tie_count"] == "0"
    assert tie["ambiguous_s2_embedding_cap"]["tie_digest"] == EMPTY_DIGEST
    assert tie["ambiguous_s2_decomposition_tie"]["tie_count"] == "integer >=2"
    for name in ("transformation_pairs.csv", "episode_transformations.csv"):
        policy = contract["outputs"]["schemas"][name]["tie_field_policy"]
        assert "constant_embedding_cap" in str(policy)
        assert "decomposition_tie" in str(policy)


def test_query_rank_executes_as_one_based_public_order() -> None:
    contract = _load()
    queries = [f"q{index}" for index in range(10)]
    expanded = _expand_queries(queries)
    assert expanded == [(index + 1, query) for index, query in enumerate(queries)]
    assert [rank for rank, _query in expanded] == contract["trusted_projections"][
        "public_episode_projection"
    ]["query_expansion"]["allowed_rank_values"]
    with pytest.raises(ValueError):
        _expand_queries([])
    with pytest.raises(ValueError):
        _expand_queries([f"q{index}" for index in range(11)])
    assert (
        contract["outputs"]["schemas"]["episode_transformations.csv"]["column_types"][
            "query_rank"
        ]
        == "one_based_query_position_1_to_10"
    )


def _sample_manifest(schemas: Mapping[str, Any]) -> dict[str, Any]:
    schema = schemas["manifest.json"]
    input_schema = schema["input_receipts"]
    inputs = {
        key: {
            "bytes": 1,
            "columns": input_schema["csv_columns_exact"][key],
            "rows": input_schema["csv_rows_exact"][key],
            "sha256": "a" * 64,
        }
        for key in input_schema["csv_keys"]
    }
    inputs["manifest.json"] = {"bytes": 1, "sha256": "b" * 64}
    sources = {
        key: {
            "bytes": 1,
            "rows": schema["source_receipts"]["rows_exact"][key],
            "sha256": "c" * 64,
        }
        for key in schema["source_receipts"]["keys_exact_sorted"]
    }
    outputs = {
        key: {
            "bytes": 1,
            "columns": schemas[key]["columns"],
            "rows": (
                schema["output_receipts"]["csv_rows"][key]
                if isinstance(schema["output_receipts"]["csv_rows"][key], int)
                else 0
            ),
            "sha256": "a" * 64,
        }
        for key in schema["output_receipts"]["csv_keys"]
    }
    outputs["transformation_coverage.json"] = {"bytes": 1, "sha256": "d" * 64}
    return {
        "runtime": {**schema["runtime"]["required_values"], "code_commit": "e" * 40},
        "input_receipts": inputs,
        "source_receipts": sources,
        "output_receipts": outputs,
    }


def test_manifest_provenance_maps_and_runtime_are_exact() -> None:
    schemas = _load()["outputs"]["schemas"]
    manifest = _sample_manifest(schemas)
    _validate_receipt_maps(manifest, schemas)
    assert "manifest.json" not in manifest["output_receipts"]

    poisoned = copy.deepcopy(manifest)
    poisoned["runtime"]["seed"] = "0"
    with pytest.raises(ValueError, match="runtime value"):
        _validate_receipt_maps(poisoned, schemas)
    poisoned = copy.deepcopy(manifest)
    poisoned["input_receipts"]["extra.csv"] = {"sha256": "f" * 64}
    with pytest.raises(ValueError, match="input_receipts key"):
        _validate_receipt_maps(poisoned, schemas)
    poisoned = copy.deepcopy(manifest)
    poisoned["output_receipts"]["manifest.json"] = {"bytes": 1, "sha256": "f" * 64}
    with pytest.raises(ValueError, match="output_receipts key"):
        _validate_receipt_maps(poisoned, schemas)


@pytest.mark.skipif(
    os.name != "posix" or platform.system() != "Linux",
    reason="v4 publication is Linux POSIX only",
)
def test_publication_refusal_preserves_destinations_and_failure_is_fresh_only(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "sentinel"
    sentinel.write_bytes(b"preserve")
    before = (sentinel.read_bytes(), sentinel.stat().st_ino, sentinel.stat().st_mode)
    assert not _publish_noreplace(existing, {"failure_receipt.json": b"bad"})
    after = (sentinel.read_bytes(), sentinel.stat().st_ino, sentinel.stat().st_mode)
    assert after == before

    real_parent = tmp_path / "real"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    assert not _publish_noreplace(
        linked_parent / "terminal", {"failure_receipt.json": b"bad"}
    )
    assert not (real_parent / "terminal").exists()

    raced = tmp_path / "raced"

    def create_race_destination() -> None:
        raced.mkdir()
        (raced / "winner").write_bytes(b"other")

    assert not _publish_noreplace(
        raced, {"manifest.json": b"ours"}, before_rename=create_race_destination
    )
    assert (raced / "winner").read_bytes() == b"other"
    assert not (raced / "manifest.json").exists()

    failure = tmp_path / "fresh-failure"
    assert _publish_noreplace(failure, {"failure_receipt.json": b"failure\n"})
    assert {path.name for path in failure.iterdir()} == {"failure_receipt.json"}
    assert (failure / "failure_receipt.json").read_bytes() == b"failure\n"


def test_science_populations_gates_and_authority_are_unchanged() -> None:
    parent = _load(PARENT)
    child = _load()
    for key in (
        "inputs",
        "scope",
        "populations",
        "support",
        "accounting_zeros",
        "authority",
        "required_outputs_after_implementation",
        "forbidden",
    ):
        assert child[key] == parent[key]
    child_projection = copy.deepcopy(child["trusted_projections"])
    parent_projection = copy.deepcopy(parent["trusted_projections"])
    child_projection["public_episode_projection"].pop("query_expansion")
    assert child_projection == parent_projection
    for key in (
        "execution_boundary",
        "classes",
        "status_values",
        "valid_statuses",
        "excluded_statuses",
        "invariants",
    ):
        assert child["extraction"][key] == parent["extraction"][key]

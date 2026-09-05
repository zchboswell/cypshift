from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from rdkit import Chem
from rdkit.Chem.MolStandardize import rdMolStandardize

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "research/maplight-fixed/competition_data.py"
)
SPEC = importlib.util.spec_from_file_location("competition_data", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
data = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = data
SPEC.loader.exec_module(data)


def _component(reserved: bool, start: int = 0) -> str:
    for i in range(start, start + 100):
        component = hashlib.sha256(str(i).encode()).hexdigest()
        if data.is_reserved(component) == reserved:
            return component
    raise AssertionError("No matching fixture component")


def _csv(rows: list[dict[str, str]]) -> bytes:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def _fixture(root: Path) -> dict[str, str]:
    molecules = [
        ("reserved", "F[C@H](Cl)Br", _component(True)),
        ("related", "F[C@@H](Cl)Br", _component(False)),
        ("development", "CCN", _component(False, 100)),
    ]
    features, observations = [], []
    for name, smiles, component in molecules:
        molecule = Chem.MolFromSmiles(smiles)
        normalized = rdMolStandardize.FragmentParent(rdMolStandardize.Cleanup(molecule))
        structure_hash = hashlib.sha256(
            Chem.MolToSmiles(normalized).encode()
        ).hexdigest()
        features.append(
            {
                "molecule_id": name,
                "raw_structure_sha256": hashlib.sha256(smiles.encode()).hexdigest(),
                "standardized_structure_hash": structure_hash,
                "similarity_component_hash": component,
            }
        )
        for endpoint in data.ENDPOINTS:
            # Both reserve and its newly discovered family neighbor have unusable
            # numeric values: successfully compiling proves exclusion precedes conversion.
            value = "4" if name == "development" else "PRIVATE-NUMERIC-GARBAGE"
            observations.append(
                {
                    "observation_id": f"{name}-{endpoint}",
                    "molecule_id": name,
                    "source_row_id": f"train.csv:{name}",
                    "source_file": "train.csv",
                    "source_row": "2",
                    "source_sha256": "x",
                    "endpoint": endpoint,
                    "raw_smiles": smiles,
                    "point": value,
                    "low": value,
                    "high": value,
                    "std": "",
                    "point_eligible": "true",
                    "value_state": "partial",
                }
            )
    leaves = {
        "feature_rows.csv": _csv(features),
        "direct_observations.csv": _csv(observations),
        "group_folds.csv": b"historical folds are authenticated but not reused\n",
    }
    for name, width, dtype in data.ARRAYS:
        stream = io.BytesIO()
        np.save(stream, np.zeros((3, width), dtype=dtype), allow_pickle=False)
        leaves[f"{name}.npy"] = stream.getvalue()
    receipts = {}
    for name, raw in leaves.items():
        (root / name).write_bytes(raw)
        receipts[f"{Path(name).stem}_sha256"] = hashlib.sha256(raw).hexdigest()
    return receipts


def test_reserved_family_exclusion_precedes_numeric_parsing(tmp_path: Path) -> None:
    receipts = _fixture(tmp_path)
    compiled = data.compile_development(tmp_path, receipts, expected_reserved_count=1)
    assert compiled.names == ("development",)
    assert compiled.report["quarantined_development_molecules"] == 1
    assert compiled.report["reserved_target_values_parsed"] == 0
    rows = {row.name: row for row in compiled.all_rows}
    assert rows["reserved"].primary_group != rows["related"].primary_group
    assert rows["reserved"].group == rows["related"].group
    assert rows["related"].quarantined and not rows["related"].reserved
    assert compiled.metric_mask.all() and not compiled.training_mask.any()
    assert compiled.all_rows[0].source_row_id != compiled.all_rows[0].name


def test_receipt_mismatch_fails_before_decoding(tmp_path: Path) -> None:
    receipts = _fixture(tmp_path)
    (tmp_path / "direct_observations.csv").write_bytes(b"not even CSV")
    with pytest.raises(ValueError, match="Source receipt differs"):
        data.compile_development(tmp_path, receipts, expected_reserved_count=1)


def test_nested_folds_keep_all_tasks_of_a_family_inside_boundaries() -> None:
    groups = tuple(f"family-{i // 3}" for i in range(180))
    mask = np.ones((180, 4), dtype=bool)
    mask[::2, 1] = False
    mask[::3, 2] = False
    outer, inner = data.balanced_nested_folds(groups, mask)
    repeated = data.balanced_nested_folds(groups, mask)
    np.testing.assert_array_equal(outer, repeated[0])
    np.testing.assert_array_equal(inner, repeated[1])
    assert set(outer) == set(range(5))
    group_array = np.asarray(groups)
    for group in set(groups):
        assert len(set(outer[group_array == group])) == 1
    for fold in range(5):
        assert (inner[fold, outer == fold] == -1).all()
        assert set(inner[fold, outer != fold]) == {0, 1, 2}
        for group in set(group_array[outer != fold]):
            assert len(set(inner[fold, group_array == group])) == 1
        assert (mask[outer == fold].sum(axis=0) > 0).all()


def test_tautomer_equivalence_merges_distinct_identity_families() -> None:
    left = data._identity_keys("CC(=O)C")
    right = data._identity_keys("CC(O)=C")
    assert left[0] != right[0]
    assert left[2] == right[2]
    merged = data._union_groups([("first-primary", *left), ("second-primary", *right)])
    assert merged[0] == merged[1]


def test_private_bundle_roundtrip_and_integrity(
    tmp_path: Path, monkeypatch: Any
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    receipts = _fixture(source)
    bundle = tmp_path / "compiled"
    original = data.publish_development(
        source, receipts, bundle, expected_reserved_count=1
    )

    # Model-side loading must not recompute identities in its different RDKit runtime.
    def forbidden(*args: Any) -> None:
        raise AssertionError("Loader attempted source chemistry")

    monkeypatch.setattr(data, "_identity_keys", forbidden)
    restored = data.load_development(bundle)
    assert original.names == restored.names
    assert original.all_rows == restored.all_rows
    np.testing.assert_array_equal(original.point, restored.point)
    np.testing.assert_array_equal(original.legacy_features, restored.legacy_features)
    assert b"PRIVATE-NUMERIC-GARBAGE" not in (bundle / "metadata.json").read_bytes()
    with pytest.raises(FileExistsError):
        data.publish_development(source, receipts, bundle, expected_reserved_count=1)
    bundle.chmod(0o755)
    (bundle / "arrays.npz").chmod(0o644)
    with (bundle / "arrays.npz").open("ab") as handle:
        handle.write(b"damaged checkpoint")
    with pytest.raises(ValueError, match="receipt differs"):
        data.load_development(bundle)
    (bundle / "arrays.npz").unlink()
    with pytest.raises(ValueError, match="incomplete"):
        data.load_development(bundle)

"""Scientific regressions for corrected counts and preserved chemistry."""

from __future__ import annotations

import hashlib
import importlib
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest
from rdkit import Chem, DataStructs
from rdkit.Avalon import pyAvalonTools
from rdkit.Chem import rdMolDescriptors


@pytest.fixture
def features(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[1] / "research/maplight-fixed")
    )
    return importlib.import_module("competition_features")


def test_small_molecules_preserve_every_legacy_feature(features: ModuleType) -> None:
    smiles = ("CCO", "c1ccccc1", "CC(=O)Oc1ccccc1C(=O)O", "CCO")
    hashes = tuple(hashlib.sha256(value.encode()).hexdigest() for value in smiles)
    historical, _ = features.legacy.featurize_raw_structures_upstream_int8(
        smiles, hashes, nonfinite_policy="allow_gasteiger_charge_nan"
    )
    corrected = features.featurize_corrected_counts(smiles)
    np.testing.assert_array_equal(corrected, historical.maplight_fixed())
    assert corrected.dtype == np.float64


def test_real_molecule_counts_above_127_do_not_wrap(features: ModuleType) -> None:
    smiles = "CO" * 140
    molecule = Chem.MolFromSmiles(smiles)
    corrected = features.featurize_corrected_counts([smiles])
    expected = np.zeros(2048, dtype=np.int32)
    for offset, fingerprint in (
        (
            0,
            rdMolDescriptors.GetHashedMorganFingerprint(molecule, nBits=1024, radius=2),
        ),
        (1024, pyAvalonTools.GetAvalonCountFP(molecule, nBits=1024)),
    ):
        for index, count in fingerprint.GetNonzeroElements().items():
            expected[offset + index] = count
    assert np.any(expected[:1024] > 127)
    assert np.any(expected[1024:] > 127)
    np.testing.assert_array_equal(corrected[0, :2048], expected)
    # Merely widening the historical array preserves wrapped negatives; it
    # cannot recover the original nonnegative counts.
    assert np.any(expected.astype(np.int8).astype(np.int32) != expected)
    assert np.all(corrected[0, :2048] >= 0)


def test_count_copy_preserves_int32_limit_and_rejects_overflow(
    features: ModuleType,
) -> None:
    fingerprint = DataStructs.UIntSparseIntVect(4)
    fingerprint[1] = 2**31 - 1
    assert features._count_array(fingerprint, 4)[1] == 2**31 - 1
    oversized = SimpleNamespace(GetNonzeroElements=lambda: {1: 2**31})
    with pytest.raises(features.legacy.MapLightFeatureError):
        features._count_array(oversized, 4)


def test_binary_features_preserve_stereochemistry_and_row_order(
    features: ModuleType,
) -> None:
    bits = features.featurize_binary_morgan(
        ["F[C@H](Cl)Br", "F[C@@H](Cl)Br", "F[C@H](Cl)Br"]
    )
    assert bits.shape == (3, 4096)
    assert set(np.unique(bits)) == {0, 1}
    assert bits.dtype == np.uint8
    assert not np.array_equal(bits[0], bits[1])
    np.testing.assert_array_equal(bits[0], bits[2])


def test_invalid_structure_fails_in_place_without_dropping_rows(
    features: ModuleType,
) -> None:
    for build in (
        features.featurize_corrected_counts,
        features.featurize_binary_morgan,
    ):
        with pytest.raises(features.legacy.MapLightFeatureError) as error:
            build(["CCO", "not a SMILES", "CC"])
        assert error.value.row_index == 1
        assert error.value.block == "raw_structure"

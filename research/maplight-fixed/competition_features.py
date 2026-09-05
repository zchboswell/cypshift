"""Label-free Phase 3 features with nonnegative, non-wrapping counts.

The MapLight column order and fingerprint settings are unchanged. Only the
count representation differs from the historical signed-int8 recipe. Record
the RDKit version alongside cached arrays: descriptor values can vary by version.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import maplight_fixed_features as legacy
import numpy as np
from numpy.typing import NDArray

BINARY_MORGAN_DIMENSIONS = 4096


def _molecules(raw_smiles: Sequence[str]) -> list[Any]:
    if isinstance(raw_smiles, str) or len(raw_smiles) == 0:
        raise legacy.MapLightFeatureError("feature input must be a sequence of SMILES")
    result: list[Any] = []
    for row_index, smiles in enumerate(raw_smiles):
        try:
            result.append(legacy._parse_raw_structure(smiles))
        except legacy.MapLightFeatureError as error:
            raise legacy.MapLightFeatureError(
                "raw structure validation failed",
                block="raw_structure",
                row_index=row_index,
            ) from error
    return result


def _count_array(fingerprint: Any, dimensions: int) -> NDArray[np.int32]:
    """Copy checked sparse counts without passing through an int8 boundary."""
    counts = fingerprint.GetNonzeroElements()
    try:
        legacy._validate_sparse_counts(
            counts, dimensions=dimensions, upper_bound=int(np.iinfo(np.int32).max)
        )
    except legacy.MapLightFeatureError as error:
        raise legacy.MapLightFeatureError(
            "invalid fingerprint index or nonnegative int32 count"
        ) from error
    result = np.zeros(dimensions, dtype=np.int32)
    for index, count in counts.items():
        result[int(index)] = int(count)
    return result


def featurize_corrected_counts(raw_smiles: Sequence[str]) -> NDArray[np.float64]:
    """Return n x 2563 MapLight features, preserving raw SMILES and row order.

    Morgan radius-2/1024 and Avalon/1024 counts use int32 before lossless float64
    concatenation with the original 315 ErG and 200 RDKit descriptors. The four
    historical Gasteiger-charge NaN columns remain allowed; no values are imputed.
    """
    from rdkit.Avalon import pyAvalonTools
    from rdkit.Chem import rdMolDescriptors

    molecules = _molecules(raw_smiles)
    morgan = np.empty((len(molecules), legacy.MORGAN_COUNT_DIMENSIONS), dtype=np.int32)
    avalon = np.empty((len(molecules), legacy.AVALON_COUNT_DIMENSIONS), dtype=np.int32)
    for row_index, molecule in enumerate(molecules):
        for block, destination, fingerprint_for, kwargs in (
            (
                "morgan_count",
                morgan,
                rdMolDescriptors.GetHashedMorganFingerprint,
                {"nBits": legacy.MORGAN_COUNT_DIMENSIONS, "radius": 2},
            ),
            (
                "avalon_count",
                avalon,
                pyAvalonTools.GetAvalonCountFP,
                {"nBits": legacy.AVALON_COUNT_DIMENSIONS},
            ),
        ):
            try:
                destination[row_index] = _count_array(
                    fingerprint_for(molecule, **kwargs), destination.shape[1]
                )
            except Exception as error:
                raise legacy.MapLightFeatureError(
                    "nonnegative count generation failed",
                    block=block,
                    row_index=row_index,
                ) from error
    result = np.ascontiguousarray(
        np.concatenate(
            (
                morgan,
                avalon,
                legacy._erg(molecules),
                legacy._rdkit_descriptors(molecules),
            ),
            axis=1,
        ),
        dtype=np.float64,
    )
    legacy._require_array(
        "maplight_corrected_counts",
        result,
        rows=len(molecules),
        columns=legacy.MAPLIGHT_FIXED_DIMENSIONS,
        dtype=np.dtype(np.float64),
        allowed_nan_columns=legacy.ALLOWED_GASTEIGER_NAN_MAPLIGHT_INDICES,
    )
    return result


def featurize_binary_morgan(raw_smiles: Sequence[str]) -> NDArray[np.uint8]:
    """Return n x 4096 radius-2 binary Morgan bits with chirality enabled."""
    from rdkit import DataStructs
    from rdkit.Chem import rdFingerprintGenerator

    molecules = _molecules(raw_smiles)
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=2,
        fpSize=BINARY_MORGAN_DIMENSIONS,
        includeChirality=True,
        countSimulation=False,
    )
    result = np.zeros((len(molecules), BINARY_MORGAN_DIMENSIONS), dtype=np.uint8)
    for row_index, molecule in enumerate(molecules):
        DataStructs.ConvertToNumpyArray(
            generator.GetFingerprint(molecule), result[row_index]
        )
    return result

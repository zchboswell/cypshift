"""Exact, label-free fixed feature construction for MapLight Stage A.

This module is intentionally independent of the ``cypshift`` package and
imports RDKit only inside feature operations.  It implements one frozen
representation contract; it is not a feature registry.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from importlib import import_module
from numbers import Integral
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

BINARY_MORGAN_DIMENSIONS = 2048
MORGAN_COUNT_DIMENSIONS = 1024
AVALON_COUNT_DIMENSIONS = 1024
ERG_DIMENSIONS = 315
RDKIT_DESCRIPTOR_DIMENSIONS = 200
MAPLIGHT_FIXED_DIMENSIONS = 2563

DESCRIPTOR_NAMES: tuple[str, ...] = (
    "BalabanJ",
    "BertzCT",
    "Chi0",
    "Chi0n",
    "Chi0v",
    "Chi1",
    "Chi1n",
    "Chi1v",
    "Chi2n",
    "Chi2v",
    "Chi3n",
    "Chi3v",
    "Chi4n",
    "Chi4v",
    "EState_VSA1",
    "EState_VSA10",
    "EState_VSA11",
    "EState_VSA2",
    "EState_VSA3",
    "EState_VSA4",
    "EState_VSA5",
    "EState_VSA6",
    "EState_VSA7",
    "EState_VSA8",
    "EState_VSA9",
    "ExactMolWt",
    "FpDensityMorgan1",
    "FpDensityMorgan2",
    "FpDensityMorgan3",
    "FractionCSP3",
    "HallKierAlpha",
    "HeavyAtomCount",
    "HeavyAtomMolWt",
    "Ipc",
    "Kappa1",
    "Kappa2",
    "Kappa3",
    "LabuteASA",
    "MaxAbsEStateIndex",
    "MaxAbsPartialCharge",
    "MaxEStateIndex",
    "MaxPartialCharge",
    "MinAbsEStateIndex",
    "MinAbsPartialCharge",
    "MinEStateIndex",
    "MinPartialCharge",
    "MolLogP",
    "MolMR",
    "MolWt",
    "NHOHCount",
    "NOCount",
    "NumAliphaticCarbocycles",
    "NumAliphaticHeterocycles",
    "NumAliphaticRings",
    "NumAromaticCarbocycles",
    "NumAromaticHeterocycles",
    "NumAromaticRings",
    "NumHAcceptors",
    "NumHDonors",
    "NumHeteroatoms",
    "NumRadicalElectrons",
    "NumRotatableBonds",
    "NumSaturatedCarbocycles",
    "NumSaturatedHeterocycles",
    "NumSaturatedRings",
    "NumValenceElectrons",
    "PEOE_VSA1",
    "PEOE_VSA10",
    "PEOE_VSA11",
    "PEOE_VSA12",
    "PEOE_VSA13",
    "PEOE_VSA14",
    "PEOE_VSA2",
    "PEOE_VSA3",
    "PEOE_VSA4",
    "PEOE_VSA5",
    "PEOE_VSA6",
    "PEOE_VSA7",
    "PEOE_VSA8",
    "PEOE_VSA9",
    "RingCount",
    "SMR_VSA1",
    "SMR_VSA10",
    "SMR_VSA2",
    "SMR_VSA3",
    "SMR_VSA4",
    "SMR_VSA5",
    "SMR_VSA6",
    "SMR_VSA7",
    "SMR_VSA8",
    "SMR_VSA9",
    "SlogP_VSA1",
    "SlogP_VSA10",
    "SlogP_VSA11",
    "SlogP_VSA12",
    "SlogP_VSA2",
    "SlogP_VSA3",
    "SlogP_VSA4",
    "SlogP_VSA5",
    "SlogP_VSA6",
    "SlogP_VSA7",
    "SlogP_VSA8",
    "SlogP_VSA9",
    "TPSA",
    "VSA_EState1",
    "VSA_EState10",
    "VSA_EState2",
    "VSA_EState3",
    "VSA_EState4",
    "VSA_EState5",
    "VSA_EState6",
    "VSA_EState7",
    "VSA_EState8",
    "VSA_EState9",
    "fr_Al_COO",
    "fr_Al_OH",
    "fr_Al_OH_noTert",
    "fr_ArN",
    "fr_Ar_COO",
    "fr_Ar_N",
    "fr_Ar_NH",
    "fr_Ar_OH",
    "fr_COO",
    "fr_COO2",
    "fr_C_O",
    "fr_C_O_noCOO",
    "fr_C_S",
    "fr_HOCCN",
    "fr_Imine",
    "fr_NH0",
    "fr_NH1",
    "fr_NH2",
    "fr_N_O",
    "fr_Ndealkylation1",
    "fr_Ndealkylation2",
    "fr_Nhpyrrole",
    "fr_SH",
    "fr_aldehyde",
    "fr_alkyl_carbamate",
    "fr_alkyl_halide",
    "fr_allylic_oxid",
    "fr_amide",
    "fr_amidine",
    "fr_aniline",
    "fr_aryl_methyl",
    "fr_azide",
    "fr_azo",
    "fr_barbitur",
    "fr_benzene",
    "fr_benzodiazepine",
    "fr_bicyclic",
    "fr_diazo",
    "fr_dihydropyridine",
    "fr_epoxide",
    "fr_ester",
    "fr_ether",
    "fr_furan",
    "fr_guanido",
    "fr_halogen",
    "fr_hdrzine",
    "fr_hdrzone",
    "fr_imidazole",
    "fr_imide",
    "fr_isocyan",
    "fr_isothiocyan",
    "fr_ketone",
    "fr_ketone_Topliss",
    "fr_lactam",
    "fr_lactone",
    "fr_methoxy",
    "fr_morpholine",
    "fr_nitrile",
    "fr_nitro",
    "fr_nitro_arom",
    "fr_nitro_arom_nonortho",
    "fr_nitroso",
    "fr_oxazole",
    "fr_oxime",
    "fr_para_hydroxylation",
    "fr_phenol",
    "fr_phenol_noOrthoHbond",
    "fr_phos_acid",
    "fr_phos_ester",
    "fr_piperdine",
    "fr_piperzine",
    "fr_priamide",
    "fr_prisulfonamd",
    "fr_pyridine",
    "fr_quatN",
    "fr_sulfide",
    "fr_sulfonamd",
    "fr_sulfone",
    "fr_term_acetylene",
    "fr_tetrazole",
    "fr_thiazole",
    "fr_thiocyan",
    "fr_thiophene",
    "fr_unbrch_alkane",
    "fr_urea",
    "qed",
)
DESCRIPTOR_NAMES_SHA256 = (
    "76ed228002c5cd229e4cbd8d62c3b3a49d698425a5216884c5c7b1b337f4293a"
)


class MapLightFeatureError(ValueError):
    """Raised when an input or feature violates the frozen Stage A contract."""

    def __init__(
        self,
        message: str,
        *,
        block: str | None = None,
        row_index: int | None = None,
    ) -> None:
        super().__init__(message)
        self.block = block
        self.row_index = row_index


def _descriptor_names_sha256(names: Sequence[str]) -> str:
    payload = json.dumps(list(names), ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return sha256(payload).hexdigest()


def _verify_descriptor_names() -> None:
    if len(DESCRIPTOR_NAMES) != RDKIT_DESCRIPTOR_DIMENSIONS:
        raise RuntimeError("the frozen RDKit descriptor count is invalid")
    if len(set(DESCRIPTOR_NAMES)) != len(DESCRIPTOR_NAMES):
        raise RuntimeError("the frozen RDKit descriptor names are not unique")
    if _descriptor_names_sha256(DESCRIPTOR_NAMES) != DESCRIPTOR_NAMES_SHA256:
        raise RuntimeError("the frozen RDKit descriptor order hash is invalid")


_verify_descriptor_names()


def _validate_sparse_counts(
    counts: Mapping[object, object],
    dimensions: int | None = None,
    upper_bound: int | None = 127,
) -> int:
    """Validate sparse indices and counts, then return the maximum count."""

    maximum = 0
    for index, value in counts.items():
        if dimensions is not None:
            if isinstance(index, (bool, np.bool_)) or not isinstance(index, Integral):
                raise MapLightFeatureError(
                    "a sparse fingerprint index is not a non-boolean integer"
                )
            if int(index) < 0 or int(index) >= dimensions:
                raise MapLightFeatureError("a sparse fingerprint index is out of range")
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
            raise MapLightFeatureError(
                "a sparse fingerprint count is not a non-boolean integer"
            )
        integer = int(value)
        if integer < 0 or (upper_bound is not None and integer > upper_bound):
            raise MapLightFeatureError(
                "a sparse fingerprint count is outside 0 through 127"
            )
        maximum = max(maximum, integer)
    return maximum


def _parse_raw_structure(raw_structure: str) -> Any:
    """Parse one exact raw SMILES with RDKit defaults and no normalization."""

    if not isinstance(raw_structure, str):
        raise MapLightFeatureError("raw structure must be a string")
    if raw_structure == "":
        raise MapLightFeatureError("raw structure must not be empty")
    chem = import_module("rdkit.Chem")
    try:
        molecule = chem.MolFromSmiles(raw_structure)
    except Exception as error:
        raise MapLightFeatureError("raw structure parsing failed") from error
    if molecule is None:
        raise MapLightFeatureError("raw structure is unparsable")
    if molecule.GetNumAtoms() == 0:
        raise MapLightFeatureError("raw structure produced a zero-atom molecule")
    return molecule


def _count_array(
    fingerprint: Any, dimensions: int, *, upper_bound: int | None
) -> tuple[NDArray[np.int8], int, int]:
    counts = fingerprint.GetNonzeroElements()
    if not isinstance(counts, Mapping):
        raise MapLightFeatureError("sparse fingerprint counts are unavailable")
    maximum = _validate_sparse_counts(counts, dimensions, upper_bound)
    bins_above_127 = sum(int(int(value) > 127) for value in counts.values())
    array: NDArray[np.int8] = np.zeros((0,), dtype=np.int8)
    data_structs = import_module("rdkit.DataStructs")
    data_structs.ConvertToNumpyArray(fingerprint, array)
    if array.shape != (dimensions,) or array.dtype != np.dtype(np.int8):
        raise MapLightFeatureError("sparse fingerprint conversion drifted")
    if not array.flags.c_contiguous:
        raise MapLightFeatureError("sparse fingerprint is not C-contiguous")
    return array, maximum, bins_above_127


def _safe_count_array(fingerprint: Any, dimensions: int) -> NDArray[np.int8]:
    return _count_array(fingerprint, dimensions, upper_bound=127)[0]


def _upstream_count_array(
    fingerprint: Any, dimensions: int
) -> tuple[NDArray[np.int8], int, int]:
    """Apply the pinned upstream signed-int8 conversion without an upper bound."""
    return _count_array(fingerprint, dimensions, upper_bound=None)


def _binary_morgan(molecules: Sequence[Any]) -> NDArray[np.uint8]:
    generator_module = import_module("rdkit.Chem.rdFingerprintGenerator")
    generator = generator_module.GetMorganGenerator(
        radius=2,
        fpSize=BINARY_MORGAN_DIMENSIONS,
        includeChirality=True,
        countSimulation=False,
    )
    data_structs = import_module("rdkit.DataStructs")
    rows: list[NDArray[np.uint8]] = []
    for row_index, molecule in enumerate(molecules):
        try:
            fingerprint = generator.GetFingerprint(molecule)
            row: NDArray[np.uint8] = np.zeros(
                (BINARY_MORGAN_DIMENSIONS,), dtype=np.uint8
            )
            data_structs.ConvertToNumpyArray(fingerprint, row)
        except Exception as error:
            raise MapLightFeatureError(
                "binary Morgan generation failed",
                block="binary_morgan",
                row_index=row_index,
            ) from error
        rows.append(row)
    return np.stack(rows)


def _morgan_counts(molecules: Sequence[Any]) -> NDArray[np.int8]:
    descriptors = import_module("rdkit.Chem.rdMolDescriptors")
    rows: list[NDArray[np.int8]] = []
    for row_index, molecule in enumerate(molecules):
        try:
            fingerprint = descriptors.GetHashedMorganFingerprint(
                molecule, nBits=MORGAN_COUNT_DIMENSIONS, radius=2
            )
            rows.append(_safe_count_array(fingerprint, MORGAN_COUNT_DIMENSIONS))
        except Exception as error:
            raise MapLightFeatureError(
                "Morgan count generation failed",
                block="morgan_count",
                row_index=row_index,
            ) from error
    return np.stack(rows)


def _avalon_counts(molecules: Sequence[Any]) -> NDArray[np.int8]:
    avalon = import_module("rdkit.Avalon.pyAvalonTools")
    rows: list[NDArray[np.int8]] = []
    for row_index, molecule in enumerate(molecules):
        try:
            fingerprint = avalon.GetAvalonCountFP(
                molecule, nBits=AVALON_COUNT_DIMENSIONS
            )
            rows.append(_safe_count_array(fingerprint, AVALON_COUNT_DIMENSIONS))
        except Exception as error:
            raise MapLightFeatureError(
                "Avalon count generation failed",
                block="avalon_count",
                row_index=row_index,
            ) from error
    return np.stack(rows)


@dataclass(frozen=True, slots=True)
class CountOverflowStats:
    """Aggregate evidence for one exact upstream signed-int8 count block."""

    maximum_preconversion_count: int
    unique_raw_rows_with_counts_above_127: int
    bins_above_127: int
    minimum_converted_int8_value: int
    maximum_converted_int8_value: int


def _upstream_count_block(
    molecules: Sequence[Any], *, block: str
) -> tuple[NDArray[np.int8], CountOverflowStats]:
    fingerprint_for: Callable[[Any], Any]
    if block == "morgan_count":
        descriptors = import_module("rdkit.Chem.rdMolDescriptors")
        dimensions = MORGAN_COUNT_DIMENSIONS

        def morgan_fingerprint(molecule: Any) -> Any:
            return descriptors.GetHashedMorganFingerprint(
                molecule, nBits=MORGAN_COUNT_DIMENSIONS, radius=2
            )

        fingerprint_for = morgan_fingerprint

    elif block == "avalon_count":
        avalon = import_module("rdkit.Avalon.pyAvalonTools")
        dimensions = AVALON_COUNT_DIMENSIONS

        def avalon_fingerprint(molecule: Any) -> Any:
            return avalon.GetAvalonCountFP(molecule, nBits=AVALON_COUNT_DIMENSIONS)

        fingerprint_for = avalon_fingerprint

    else:
        raise MapLightFeatureError("unsupported upstream count block")
    rows: list[NDArray[np.int8]] = []
    maximum = 0
    rows_above = 0
    bins_above = 0
    for row_index, molecule in enumerate(molecules):
        try:
            fingerprint = fingerprint_for(molecule)
            row, row_maximum, row_bins_above = _upstream_count_array(
                fingerprint, dimensions
            )
        except Exception as error:
            raise MapLightFeatureError(
                f"{block} generation failed",
                block=block,
                row_index=row_index,
            ) from error
        rows.append(row)
        maximum = max(maximum, row_maximum)
        rows_above += int(row_bins_above > 0)
        bins_above += row_bins_above
    array = np.stack(rows)
    return array, CountOverflowStats(
        maximum_preconversion_count=maximum,
        unique_raw_rows_with_counts_above_127=rows_above,
        bins_above_127=bins_above,
        minimum_converted_int8_value=int(array.min()),
        maximum_converted_int8_value=int(array.max()),
    )


def _erg(molecules: Sequence[Any]) -> NDArray[np.float64]:
    reduced_graphs = import_module("rdkit.Chem.rdReducedGraphs")
    rows: list[Any] = []
    for row_index, molecule in enumerate(molecules):
        try:
            rows.append(reduced_graphs.GetErGFingerprint(molecule))
        except Exception as error:
            raise MapLightFeatureError(
                "ErG generation failed",
                block="erg",
                row_index=row_index,
            ) from error
    return np.stack(rows)


def _rdkit_descriptors(molecules: Sequence[Any]) -> NDArray[np.float64]:
    descriptor_registry = import_module("rdkit.Chem.Descriptors")
    missing = tuple(
        name
        for name in DESCRIPTOR_NAMES
        if not callable(getattr(descriptor_registry, name, None))
    )
    if missing:
        raise MapLightFeatureError(
            "one or more frozen RDKit descriptors are unavailable",
            block="rdkit_descriptors",
        )
    descriptor_module = import_module("rdkit.ML.Descriptors.MoleculeDescriptors")
    try:
        calculator = descriptor_module.MolecularDescriptorCalculator(
            list(DESCRIPTOR_NAMES)
        )
        reported_names = tuple(calculator.GetDescriptorNames())
    except Exception as error:
        raise MapLightFeatureError(
            "RDKit descriptor calculator construction failed",
            block="rdkit_descriptors",
        ) from error
    if reported_names != DESCRIPTOR_NAMES:
        raise MapLightFeatureError(
            "RDKit descriptor names or order drifted",
            block="rdkit_descriptors",
        )
    rows: list[NDArray[Any]] = []
    for row_index, molecule in enumerate(molecules):
        try:
            rows.append(np.array(calculator.CalcDescriptors(molecule)))
        except Exception as error:
            raise MapLightFeatureError(
                "RDKit descriptor generation failed",
                block="rdkit_descriptors",
                row_index=row_index,
            ) from error
    return np.vstack(rows)


def _require_array(
    name: str,
    array: NDArray[Any],
    *,
    rows: int,
    columns: int,
    dtype: np.dtype[Any],
) -> None:
    if not isinstance(array, np.ndarray):
        raise MapLightFeatureError(f"{name} is not a NumPy array", block=name)
    if array.shape != (rows, columns):
        raise MapLightFeatureError(f"{name} shape is invalid", block=name)
    if array.dtype != dtype:
        raise MapLightFeatureError(f"{name} dtype is invalid", block=name)
    if not array.flags.c_contiguous:
        raise MapLightFeatureError(f"{name} is not C-contiguous", block=name)
    if not bool(np.isfinite(array).all()):
        first = np.argwhere(~np.isfinite(array))[0]
        raise MapLightFeatureError(
            f"{name} contains a non-finite value",
            block=name,
            row_index=int(first[0]),
        )


@dataclass(frozen=True, slots=True, eq=False)
class FixedFeatureArrays:
    """Validated immutable arrays for the one frozen Stage A representation."""

    raw_structure_sha256: tuple[str, ...]
    binary_morgan: NDArray[np.uint8]
    morgan_count: NDArray[np.int8]
    avalon_count: NDArray[np.int8]
    erg: NDArray[np.float64]
    rdkit_descriptors: NDArray[np.float64]
    count_policy: str = "safe_nonnegative"

    def __post_init__(self) -> None:
        if not isinstance(self.binary_morgan, np.ndarray):
            raise MapLightFeatureError(
                "binary_morgan is not a NumPy array", block="binary_morgan"
            )
        if self.binary_morgan.ndim != 2:
            raise MapLightFeatureError(
                "binary_morgan shape is invalid", block="binary_morgan"
            )
        rows = self.binary_morgan.shape[0]
        if rows < 1:
            raise MapLightFeatureError("feature arrays must contain a row")
        if len(self.raw_structure_sha256) != rows:
            raise MapLightFeatureError("raw-structure hash count is invalid")
        if any(
            len(value) != 64
            or value != value.lower()
            or any(character not in "0123456789abcdef" for character in value)
            for value in self.raw_structure_sha256
        ):
            raise MapLightFeatureError("a raw-structure hash is invalid")
        specifications = (
            (
                "binary_morgan",
                self.binary_morgan,
                BINARY_MORGAN_DIMENSIONS,
                np.dtype(np.uint8),
            ),
            (
                "morgan_count",
                self.morgan_count,
                MORGAN_COUNT_DIMENSIONS,
                np.dtype(np.int8),
            ),
            (
                "avalon_count",
                self.avalon_count,
                AVALON_COUNT_DIMENSIONS,
                np.dtype(np.int8),
            ),
            ("erg", self.erg, ERG_DIMENSIONS, np.dtype("<f8")),
            (
                "rdkit_descriptors",
                self.rdkit_descriptors,
                RDKIT_DESCRIPTOR_DIMENSIONS,
                np.dtype("<f8"),
            ),
        )
        for name, array, columns, dtype in specifications:
            _require_array(name, array, rows=rows, columns=columns, dtype=dtype)
        is_binary = np.logical_or(self.binary_morgan == 0, self.binary_morgan == 1)
        if not bool(is_binary.all()):
            row_index = int(np.argwhere(~is_binary)[0][0])
            raise MapLightFeatureError(
                "binary Morgan contains a non-binary value",
                block="binary_morgan",
                row_index=row_index,
            )
        if self.count_policy not in {"safe_nonnegative", "upstream_signed_int8"}:
            raise MapLightFeatureError("count policy is invalid")
        if self.count_policy == "safe_nonnegative" and (
            bool((self.morgan_count < 0).any()) or bool((self.avalon_count < 0).any())
        ):
            block = (
                "morgan_count"
                if bool((self.morgan_count < 0).any())
                else "avalon_count"
            )
            values = self.morgan_count if block == "morgan_count" else self.avalon_count
            row_index = int(np.argwhere(values < 0)[0][0])
            raise MapLightFeatureError(
                "a count block contains a negative value",
                block=block,
                row_index=row_index,
            )
        for _, array, _, _ in specifications:
            array.setflags(write=False)

    def maplight_fixed(self) -> NDArray[np.float64]:
        """Return a new immutable complete MapLight matrix in frozen order."""

        result = np.ascontiguousarray(
            np.concatenate(
                (
                    self.morgan_count,
                    self.avalon_count,
                    self.erg,
                    self.rdkit_descriptors,
                ),
                axis=1,
            ),
            dtype=np.dtype("<f8"),
        )
        _require_array(
            "maplight_fixed",
            result,
            rows=len(self.raw_structure_sha256),
            columns=MAPLIGHT_FIXED_DIMENSIONS,
            dtype=np.dtype("<f8"),
        )
        result.setflags(write=False)
        return result


def descriptor_names() -> tuple[str, ...]:
    """Return the exact ordered descriptor names copied from pinned source."""

    return DESCRIPTOR_NAMES


def _validated_molecules(
    raw_structures: tuple[str, ...],
    expected_raw_sha256: tuple[str, ...],
) -> tuple[tuple[str, ...], list[Any]]:
    if len(raw_structures) == 0:
        raise MapLightFeatureError("feature input must contain a row")
    if len(raw_structures) != len(expected_raw_sha256):
        raise MapLightFeatureError("raw structure and hash counts differ")
    observed_raw_sha256: list[str] = []
    for row_index, (raw_structure, expected_hash) in enumerate(
        zip(raw_structures, expected_raw_sha256, strict=True)
    ):
        if not isinstance(raw_structure, str):
            raise MapLightFeatureError(
                "raw structure validation failed",
                block="raw_structure",
                row_index=row_index,
            )
        observed_hash = sha256(raw_structure.encode("utf-8")).hexdigest()
        if observed_hash != expected_hash:
            raise MapLightFeatureError(
                "raw structure hash differs",
                block="raw_structure",
                row_index=row_index,
            )
        observed_raw_sha256.append(observed_hash)
    molecules: list[Any] = []
    for row_index, raw_structure in enumerate(raw_structures):
        try:
            molecules.append(_parse_raw_structure(raw_structure))
        except MapLightFeatureError as error:
            raise MapLightFeatureError(
                "raw structure validation failed",
                block="raw_structure",
                row_index=row_index,
            ) from error
    return tuple(observed_raw_sha256), molecules


def featurize_raw_structures(
    raw_structures: tuple[str, ...],
    expected_raw_sha256: tuple[str, ...],
) -> FixedFeatureArrays:
    """Build all frozen Stage A blocks in exact input order."""

    observed_raw_sha256, molecules = _validated_molecules(
        raw_structures, expected_raw_sha256
    )
    binary_morgan = _binary_morgan(molecules)
    morgan_count = _morgan_counts(molecules)
    avalon_count = _avalon_counts(molecules)
    erg = _erg(molecules)
    rdkit_descriptors = _rdkit_descriptors(molecules)
    return FixedFeatureArrays(
        raw_structure_sha256=observed_raw_sha256,
        binary_morgan=binary_morgan,
        morgan_count=morgan_count,
        avalon_count=avalon_count,
        erg=erg,
        rdkit_descriptors=rdkit_descriptors,
    )


def featurize_raw_structures_upstream_int8(
    raw_structures: tuple[str, ...],
    expected_raw_sha256: tuple[str, ...],
    *,
    block_completed: Callable[[str], None] | None = None,
) -> tuple[FixedFeatureArrays, dict[str, CountOverflowStats]]:
    """Build the same blocks with the pinned upstream signed-int8 count bytes."""

    observed_raw_sha256, molecules = _validated_molecules(
        raw_structures, expected_raw_sha256
    )
    binary_morgan = _binary_morgan(molecules)
    if block_completed is not None:
        block_completed("binary_morgan")
    morgan_count, morgan_stats = _upstream_count_block(molecules, block="morgan_count")
    if block_completed is not None:
        block_completed("morgan_count")
    avalon_count, avalon_stats = _upstream_count_block(molecules, block="avalon_count")
    if block_completed is not None:
        block_completed("avalon_count")
    erg = _erg(molecules)
    if block_completed is not None:
        block_completed("erg")
    rdkit_descriptors = _rdkit_descriptors(molecules)
    if block_completed is not None:
        block_completed("rdkit_descriptors")
    arrays = FixedFeatureArrays(
        raw_structure_sha256=observed_raw_sha256,
        binary_morgan=binary_morgan,
        morgan_count=morgan_count,
        avalon_count=avalon_count,
        erg=erg,
        rdkit_descriptors=rdkit_descriptors,
        count_policy="upstream_signed_int8",
    )
    return arrays, {
        "morgan_count": morgan_stats,
        "avalon_count": avalon_stats,
    }


def signed_int8_count_witness(count: int) -> int:
    """Convert one synthetic sparse count through the compatibility boundary."""

    if type(count) is not int:
        raise MapLightFeatureError("witness count is not a non-boolean integer")
    integer = count
    if integer < 0:
        raise MapLightFeatureError("witness count is negative")
    data_structs = import_module("rdkit.DataStructs")
    fingerprint = data_structs.UIntSparseIntVect(4)
    fingerprint[1] = integer
    array, _, _ = _upstream_count_array(fingerprint, 4)
    return int(array[1])


def write_npy_v1(path: Path, array: NDArray[Any]) -> None:
    """Write one C-contiguous non-pickle NumPy v1.0 file."""

    if not isinstance(array, np.ndarray):
        raise MapLightFeatureError("npy payload is not a NumPy array")
    if array.dtype.hasobject:
        raise MapLightFeatureError("object arrays cannot be serialized")
    if not array.flags.c_contiguous:
        raise MapLightFeatureError("npy payload is not C-contiguous")
    with path.open("xb") as handle:
        np.lib.format.write_array(handle, array, version=(1, 0), allow_pickle=False)

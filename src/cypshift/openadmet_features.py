"""Receipt-bound, chemistry-only R3A OpenADMET feature projection.

The trusted projector is deliberately narrower than the R2A observation
compiler.  It reads the accepted direct-observation bytes, but decodes only
the eight identity/raw-structure fields at the start of each record.  The
target-bearing suffix is never decoded or represented in memory as fields.
"""

from __future__ import annotations

import csv
import ctypes
import errno
import io
import json
import os
import platform
import shutil
import tempfile
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from rdkit import rdBase

from cypshift.chemistry import STANDARDIZATION_VERSION, standardize_molecule
from cypshift.openadmet_topology import TOPOLOGY_COLUMNS
from cypshift.openadmet_validation import FOLD_COLUMNS, OBSERVATION_COLUMNS
from cypshift.schema import MoleculeInput, MoleculeStatus

FEATURE_INPUT_SCHEMA_VERSION = "cypshift.openadmet_cyp_2026.feature_input.v1"
GLOBAL_CONTRACT_SHA256 = (
    "d728684cc3794bbe01ea44342202944a378968f097cb8f5490852b63721a6285"
)
FEATURE_INPUT_COLUMNS = (
    "molecule_id",
    "raw_smiles",
    "raw_structure_sha256",
    "standardized_smiles",
    "standardized_structure_hash",
    "similarity_component_hash",
)
DIRECT_PREFIX_COLUMNS = OBSERVATION_COLUMNS[:8]
DIRECT_SOURCE_FILE = "cyp-challenge-TRAIN_inhibition.csv"
DEFAULT_CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "global_experiment_contract.json"
)
DEFAULT_STANDARDIZER_PATH = Path(__file__).resolve().with_name("chemistry.py")
DEFAULT_UV_LOCK_PATH = Path(__file__).resolve().parents[2] / "uv.lock"


class OpenADMETFeatureProjectionError(ValueError):
    """Raised when a receipt-bound R3A projection cannot be built safely."""


@dataclass(frozen=True, slots=True)
class FeatureProjectionResult:
    """Paths and count from one immutable R3A projection."""

    feature_input_path: Path
    manifest_path: Path
    molecule_count: int


@dataclass(frozen=True, slots=True)
class _Counts:
    molecules: int
    direct_observations: int
    topology_rows: int
    group_fold_rows: int
    ignored_topology_rows: int


def project_openadmet_feature_input(
    direct_observations_path: Path,
    group_folds_path: Path,
    training_topology_path: Path,
    output_directory: Path,
    *,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    expected_contract_sha256: str = GLOBAL_CONTRACT_SHA256,
    standardizer_path: Path = DEFAULT_STANDARDIZER_PATH,
    core_uv_lock_path: Path = DEFAULT_UV_LOCK_PATH,
    expected_counts: Mapping[str, int] | None = None,
) -> FeatureProjectionResult:
    """Project direct raw/standardized chemistry without retaining targets.

    ``expected_counts`` exists solely for small redistributable fixtures.  The
    frozen contract defaults are used when it is omitted; production callers
    must not use it to relax the R3A counts.
    """

    if _destination_occupied(output_directory):
        raise OpenADMETFeatureProjectionError(
            f"output path already exists: {output_directory}; refusing overwrite"
        )
    projector_data = _read_bytes(Path(__file__), "projector source")
    projector_hash = sha256(projector_data).hexdigest()
    contract_data = _read_bytes(contract_path, "global experiment contract")
    _digest_text(expected_contract_sha256, "expected contract SHA-256")
    _match_hash(
        contract_data, expected_contract_sha256, "global experiment contract"
    )
    contract = _json_object(contract_data, "global experiment contract")
    if contract.get("schema_version") != (
        "cypshift.openadmet_cyp_2026.global_experiment_contract.v3"
    ):
        raise OpenADMETFeatureProjectionError("R3 contract schema mismatch")
    projection = _object(contract, "r3a_chemistry_projection")
    if projection.get("manifest", {}).get("schema_version") != FEATURE_INPUT_SCHEMA_VERSION:
        raise OpenADMETFeatureProjectionError("feature-input manifest schema mismatch")
    _verify_contract_projection_policy(contract, projection)
    counts = _expected_counts(contract, projection, expected_counts)

    core, core_evidence = _verify_core_receipts(
        contract, standardizer_path, core_uv_lock_path
    )

    direct_data = _read_bytes(direct_observations_path, "direct_observations.csv")
    folds_data = _read_bytes(group_folds_path, "group_folds.csv")
    topology_data = _read_bytes(training_topology_path, "training_topology.csv")
    expected_hashes = _input_hashes(contract, projection)
    _match_hash(direct_data, expected_hashes["direct_observations"], "direct_observations.csv")
    _match_hash(folds_data, expected_hashes["group_folds"], "group_folds.csv")
    _match_hash(topology_data, expected_hashes["training_topology"], "training_topology.csv")

    direct_rows = _parse_direct_prefix(direct_data, counts.direct_observations)
    topology_rows = _parse_csv(topology_data, TOPOLOGY_COLUMNS, "training_topology.csv")
    fold_rows = _parse_csv(folds_data, FOLD_COLUMNS, "group_folds.csv")
    if len(topology_rows) != counts.topology_rows:
        raise OpenADMETFeatureProjectionError("training_topology.csv row-count mismatch")
    if len(fold_rows) != counts.group_fold_rows:
        raise OpenADMETFeatureProjectionError("group_folds.csv row-count mismatch")

    direct = _validate_direct_rows(direct_rows, counts)
    topology = _validate_topology(topology_rows, direct, counts)
    _validate_folds(fold_rows, direct, topology, counts)
    output_rows = _build_feature_rows(direct, topology)
    if len(output_rows) != counts.molecules:
        raise OpenADMETFeatureProjectionError("feature-input molecule count mismatch")
    feature_data = _csv_bytes(FEATURE_INPUT_COLUMNS, output_rows)

    accounting = _accounting(counts)
    authority = {
        "targets": False,
        "features": False,
        "models": False,
        "predictions": False,
        "metrics": False,
        "fold_assignments": False,
        "submissions": False,
    }
    manifest: dict[str, Any] = {
        "schema_version": FEATURE_INPUT_SCHEMA_VERSION,
        "contract_sha256": sha256(contract_data).hexdigest(),
        "direct_observations_sha256": expected_hashes["direct_observations"],
        "group_folds_sha256": expected_hashes["group_folds"],
        "training_topology_sha256": expected_hashes["training_topology"],
        "projector_source_sha256": projector_hash,
        "standardizer_source_sha256": core_evidence["standardizer_source_sha256"],
        "core_uv_lock_sha256": core_evidence["core_uv_lock_sha256"],
        "core_python_version": core_evidence["core_python_version"],
        "core_rdkit_version": core_evidence["core_rdkit_version"],
        "standardization_policy_id": _text(core, "standardization_policy_id"),
        "feature_input_sha256": sha256(feature_data).hexdigest(),
        "feature_input_columns": list(FEATURE_INPUT_COLUMNS),
        "feature_input_rows": len(output_rows),
        "raw_structure_hash_formula": (
            "lowercase SHA256 hex of the exact raw_smiles UTF-8 bytes"
        ),
        "standardized_structure_hash_formula": (
            "lowercase SHA256 hex of the exact standardized_smiles UTF-8 bytes"
        ),
        "accounting": accounting,
        "authority": authority,
    }
    manifest_data = _json_bytes(manifest)
    staging: Path | None = None
    try:
        output_directory.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(prefix=".r3a-feature-input-", dir=output_directory.parent)
        )
        _write_new(staging / "feature_input.csv", feature_data)
        _write_new(staging / "feature_input_manifest.json", manifest_data)
        (staging / "feature_input.csv").chmod(0o444)
        (staging / "feature_input_manifest.json").chmod(0o444)
        if _destination_occupied(output_directory):
            raise OpenADMETFeatureProjectionError(
                f"output path already exists: {output_directory}; refusing overwrite"
            )
        staging.chmod(0o555)
        _rename_noreplace(staging, output_directory)
        staging = None
    except Exception:
        if staging is not None:
            _make_writable(staging)
            shutil.rmtree(staging, ignore_errors=True)
        raise
    return FeatureProjectionResult(
        output_directory / "feature_input.csv",
        output_directory / "feature_input_manifest.json",
        len(output_rows),
    )


def _verify_contract_projection_policy(
    contract: Mapping[str, Any], projection: Mapping[str, Any]
) -> None:
    prefix = projection.get("direct_observation_prefix")
    if prefix != list(DIRECT_PREFIX_COLUMNS):
        raise OpenADMETFeatureProjectionError("direct-observation prefix schema mismatch")
    output = _object(projection, "output")
    if output.get("columns") != list(FEATURE_INPUT_COLUMNS):
        raise OpenADMETFeatureProjectionError("feature-input output schema mismatch")
    if output.get("serialization") != "RFC4180 CSV with LF line endings and one terminal newline":
        raise OpenADMETFeatureProjectionError("feature-input serialization policy mismatch")
    core = _object(_object(contract, "inputs"), "core_chemistry")
    if _text(core, "standardization_policy_id") != STANDARDIZATION_VERSION:
        raise OpenADMETFeatureProjectionError("standardization policy mismatch")


def _verify_core_receipts(
    contract: Mapping[str, Any], standardizer_path: Path, lock_path: Path
) -> tuple[dict[str, Any], dict[str, str]]:
    """Verify chemistry source and runtime receipts before parsing chemistry."""

    core = _object(_object(contract, "inputs"), "core_chemistry")
    standardizer_hash = _file_hash(standardizer_path, "standardizer source")
    if standardizer_hash != _digest(core, "standardizer_source_sha256"):
        raise OpenADMETFeatureProjectionError("standardizer source hash mismatch")
    lock_hash = _file_hash(lock_path, "core uv lock")
    if lock_hash != _digest(core, "uv_lock_sha256"):
        raise OpenADMETFeatureProjectionError("core uv.lock hash mismatch")
    expected_python = _text(core, "python_version")
    actual_python = platform.python_version()
    if actual_python != expected_python:
        raise OpenADMETFeatureProjectionError(
            f"core Python version mismatch: expected {expected_python}, got {actual_python}"
        )
    expected_rdkit = _text(core, "rdkit_version")
    actual_rdkit = rdBase.rdkitVersion
    if actual_rdkit != expected_rdkit:
        raise OpenADMETFeatureProjectionError(
            f"core RDKit version mismatch: expected {expected_rdkit}, got {actual_rdkit}"
        )
    return core, {
        "standardizer_source_sha256": standardizer_hash,
        "core_uv_lock_sha256": lock_hash,
        "core_python_version": actual_python,
        "core_rdkit_version": actual_rdkit,
    }


def _expected_counts(
    contract: Mapping[str, Any],
    projection: Mapping[str, Any],
    overrides: Mapping[str, int] | None,
) -> _Counts:
    population = _object(_object(contract, "scope"), "population")
    output = _object(projection, "output")
    values = {
        "molecules": _integer(output, "rows"),
        "direct_observations": _integer(population, "molecule_endpoint_cells"),
        "topology_rows": 6147,
        "group_fold_rows": 73575,
        "ignored_topology_rows": 1242,
    }
    configured = projection.get("expected_counts")
    if isinstance(configured, dict):
        for key, value in configured.items():
            if key in values:
                values[key] = _nonnegative_int(value, f"expected_counts.{key}")
    if overrides is not None:
        for key, value in overrides.items():
            if key not in values:
                raise OpenADMETFeatureProjectionError(f"unknown expected count: {key}")
            values[key] = _nonnegative_int(value, f"expected_counts.{key}")
    if values["direct_observations"] != values["molecules"] * 4:
        raise OpenADMETFeatureProjectionError("direct observation count is not four per molecule")
    if "molecules" in population and population["molecules"] != values["molecules"]:
        raise OpenADMETFeatureProjectionError("contract molecule count mismatch")
    if (
        "molecule_endpoint_cells" in population
        and population["molecule_endpoint_cells"] != values["direct_observations"]
    ):
        raise OpenADMETFeatureProjectionError("contract direct-observation count mismatch")
    if values["topology_rows"] - values["molecules"] != values["ignored_topology_rows"]:
        raise OpenADMETFeatureProjectionError("topology ignored-row accounting mismatch")
    return _Counts(**values)


def _input_hashes(
    contract: Mapping[str, Any], projection: Mapping[str, Any]
) -> dict[str, str]:
    values = _object(projection, "inputs")
    top = _object(_object(contract, "inputs"), "direct_observations")
    top_folds = _object(_object(contract, "inputs"), "group_folds")
    top_topology = _object(_object(contract, "inputs"), "training_topology")
    result = {
        "direct_observations": _digest(values, "direct_observations_sha256"),
        "group_folds": _digest(values, "group_folds_sha256"),
        "training_topology": _digest(values, "training_topology_sha256"),
    }
    for key, item in (
        ("direct_observations", top),
        ("group_folds", top_folds),
        ("training_topology", top_topology),
    ):
        if _digest(item, "sha256") != result[key]:
            raise OpenADMETFeatureProjectionError(f"{key} contract receipt disagreement")
    return result


def _parse_direct_prefix(data: bytes, expected_rows: int) -> list[dict[str, str]]:
    records = list(_direct_records(data))
    if not records:
        raise OpenADMETFeatureProjectionError("direct_observations.csv is empty")
    header = _decode_record(records[0], "direct_observations header")
    if header != list(OBSERVATION_COLUMNS):
        raise OpenADMETFeatureProjectionError("direct_observations.csv header mismatch")
    rows: list[dict[str, str]] = []
    for prefix in records[1:]:
        try:
            values = next(csv.reader(io.StringIO(prefix.decode("utf-8"), newline=""), strict=True))
        except (UnicodeError, csv.Error, StopIteration) as exc:
            raise OpenADMETFeatureProjectionError(
                "cannot decode direct-observation prefix"
            ) from exc
        if len(values) != len(DIRECT_PREFIX_COLUMNS):
            raise OpenADMETFeatureProjectionError("direct-observation prefix field-count mismatch")
        rows.append(dict(zip(DIRECT_PREFIX_COLUMNS, values, strict=True)))
    if len(rows) != expected_rows:
        raise OpenADMETFeatureProjectionError("direct_observations.csv row-count mismatch")
    return rows


def _direct_records(data: bytes) -> Iterator[bytes]:
    """Yield header and eight-field prefixes, discarding suffix bytes in place."""

    prefix = bytearray()
    field = 1
    capture = True
    first_record = True
    in_quotes = False
    index = 0
    while index < len(data):
        # Once the eighth delimiter is reached, the remainder is opaque.  In
        # particular, quote and comma bytes there must not affect record
        # boundaries or any decoded representation; the accepted R2A CSV has
        # one physical LF record terminator per observation.
        if not first_record and not capture:
            if data[index] == 10:
                record = bytes(prefix[:-1] if prefix.endswith(b"\r") else prefix)
                yield record
                prefix.clear()
                field = 1
                capture = True
                in_quotes = False
            index += 1
            continue
        byte = data[index]
        if byte == 34:
            if in_quotes and index + 1 < len(data) and data[index + 1] == 34:
                if capture:
                    prefix.extend((34, 34))
                index += 2
                continue
            in_quotes = not in_quotes
        elif byte == 10 and not in_quotes:
            record = bytes(prefix[:-1] if prefix.endswith(b"\r") else prefix)
            yield record
            prefix.clear()
            field = 1
            capture = True
            first_record = False
            in_quotes = False
            index += 1
            continue
        if first_record:
            prefix.append(byte)
        elif capture:
            if byte == 44 and not in_quotes and field == len(DIRECT_PREFIX_COLUMNS):
                capture = False
            else:
                prefix.append(byte)
                if byte == 44 and not in_quotes:
                    field += 1
        index += 1
    if in_quotes:
        raise OpenADMETFeatureProjectionError("unterminated quoted CSV record")
    if prefix:
        record = bytes(prefix[:-1] if prefix.endswith(b"\r") else prefix)
        yield record


def _validate_direct_rows(
    rows: Sequence[Mapping[str, str]], counts: _Counts
) -> dict[str, dict[str, str]]:
    by_molecule: dict[str, dict[str, str]] = {}
    endpoints = {"CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4"}
    observation_ids: set[str] = set()
    for row in rows:
        observation_id = _required(row, "observation_id")
        if observation_id in observation_ids:
            raise OpenADMETFeatureProjectionError("duplicate observation_id")
        observation_ids.add(observation_id)
        molecule_id = _required(row, "molecule_id")
        endpoint = _required(row, "endpoint")
        if endpoint not in endpoints:
            raise OpenADMETFeatureProjectionError("unexpected direct endpoint")
        if row["source_file"] != DIRECT_SOURCE_FILE:
            raise OpenADMETFeatureProjectionError("direct source filename mismatch")
        source_row = _positive_int(row["source_row"], "source_row")
        if row["source_row_id"] != f"{DIRECT_SOURCE_FILE}:{source_row}":
            raise OpenADMETFeatureProjectionError("direct source-row identity mismatch")
        _digest_text(row["source_sha256"], "source_sha256")
        raw_smiles = _required(row, "raw_smiles")
        existing = by_molecule.get(molecule_id)
        if existing is None:
            by_molecule[molecule_id] = dict(row)
        else:
            for key in ("source_row_id", "source_file", "source_row", "source_sha256", "raw_smiles"):
                if existing[key] != row[key]:
                    raise OpenADMETFeatureProjectionError("direct identity drift across endpoints")
            if existing["endpoint"] == endpoint:
                raise OpenADMETFeatureProjectionError("duplicate endpoint for molecule")
        # Keep the endpoint set in a private validation key; it never reaches output.
        current = by_molecule.setdefault(molecule_id, dict(row))
        seen = current.setdefault("__endpoints", "")
        current["__endpoints"] = f"{seen}|{endpoint}"
        if not raw_smiles:
            raise OpenADMETFeatureProjectionError("empty raw_smiles")
    if len(by_molecule) != counts.molecules:
        raise OpenADMETFeatureProjectionError("direct molecule cardinality mismatch")
    for molecule_id, row in by_molecule.items():
        endpoint_blob = row.pop("__endpoints", "")
        seen_endpoints = set(endpoint_blob.split("|")) - {""}
        if seen_endpoints != endpoints:
            raise OpenADMETFeatureProjectionError(f"endpoint cardinality mismatch for {molecule_id}")
    return by_molecule


def _validate_topology(
    rows: Sequence[Mapping[str, str]],
    direct: Mapping[str, Mapping[str, str]],
    counts: _Counts,
) -> dict[str, dict[str, str]]:
    topology: dict[str, dict[str, str]] = {}
    for row in rows:
        molecule_id = _required(row, "molecule_id")
        if molecule_id in topology:
            raise OpenADMETFeatureProjectionError("duplicate topology molecule_id")
        for key in TOPOLOGY_COLUMNS[1:]:
            _digest_text(row[key], f"topology {key}")
        topology[molecule_id] = dict(row)
    direct_ids = set(direct)
    if not direct_ids.issubset(topology):
        raise OpenADMETFeatureProjectionError("direct molecule missing from topology")
    if len(topology) - len(direct_ids) != counts.ignored_topology_rows:
        raise OpenADMETFeatureProjectionError("ignored topology-row accounting mismatch")
    return {molecule_id: topology[molecule_id] for molecule_id in sorted(direct_ids)}


def _validate_folds(
    rows: Sequence[Mapping[str, str]],
    direct: Mapping[str, Mapping[str, str]],
    topology: Mapping[str, Mapping[str, str]],
    counts: _Counts,
) -> None:
    seen: Counter[str] = Counter()
    for row in rows:
        molecule_id = _required(row, "molecule_id")
        if molecule_id not in direct:
            raise OpenADMETFeatureProjectionError("group fold contains non-direct molecule")
        if row["similarity_component_hash"] != topology[molecule_id]["similarity_component_hash"]:
            raise OpenADMETFeatureProjectionError("group fold topology mismatch")
        _digest_text(row["similarity_component_hash"], "group fold component")
        for key in ("repeat", "seed", "outer_fold", "outer_validation_fold"):
            _integer_text(row[key], f"group fold {key}")
        if row["inner_fold"]:
            _integer_text(row["inner_fold"], "group fold inner_fold")
        seen[molecule_id] += 1
    if set(seen) != set(direct) or not seen:
        raise OpenADMETFeatureProjectionError("group fold molecule identity mismatch")
    expected_per_molecule = counts.group_fold_rows // counts.molecules
    if expected_per_molecule * counts.molecules != counts.group_fold_rows:
        raise OpenADMETFeatureProjectionError("group fold cardinality is not molecule-aligned")
    if any(value != expected_per_molecule for value in seen.values()):
        raise OpenADMETFeatureProjectionError("group fold rows per molecule mismatch")


def _build_feature_rows(
    direct: Mapping[str, Mapping[str, str]], topology: Mapping[str, Mapping[str, str]]
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for molecule_id in sorted(direct):
        raw_smiles = direct[molecule_id]["raw_smiles"]
        raw_hash = sha256(raw_smiles.encode("utf-8")).hexdigest()
        record = standardize_molecule(
            MoleculeInput(molecule_id, raw_smiles, "smiles", "r3a", "{}")
        )
        if record.status is not MoleculeStatus.ACCEPTED or record.standardized_structure is None:
            raise OpenADMETFeatureProjectionError(f"chemistry rejected for {molecule_id}")
        standardized = record.standardized_structure
        standardized_hash = sha256(standardized.encode("utf-8")).hexdigest()
        if standardized_hash != topology[molecule_id]["standardized_structure_hash"]:
            raise OpenADMETFeatureProjectionError(f"standardization receipt mismatch for {molecule_id}")
        rows.append(
            {
                "molecule_id": molecule_id,
                "raw_smiles": raw_smiles,
                "raw_structure_sha256": raw_hash,
                "standardized_smiles": standardized,
                "standardized_structure_hash": standardized_hash,
                "similarity_component_hash": topology[molecule_id]["similarity_component_hash"],
            }
        )
    return rows


def _parse_csv(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True)
        header = next(reader, None)
        if header != list(columns):
            raise OpenADMETFeatureProjectionError(f"{label} header mismatch")
        rows: list[dict[str, str]] = []
        for values in reader:
            if len(values) != len(columns):
                raise OpenADMETFeatureProjectionError(f"{label} field-count mismatch")
            rows.append(dict(zip(columns, values, strict=True)))
        return rows
    except (UnicodeError, csv.Error) as exc:
        raise OpenADMETFeatureProjectionError(f"cannot parse {label}") from exc


def _accounting(counts: _Counts) -> dict[str, int]:
    return {
        "direct_observation_records_scanned": counts.direct_observations,
        "decoded_prefix_fields": counts.direct_observations * len(DIRECT_PREFIX_COLUMNS),
        "opaque_suffixes_discarded": counts.direct_observations,
        "target_values_parsed": 0,
        "target_values_retained": 0,
        "blinded_test_rows_opened": 0,
    }


def _csv_bytes(columns: Sequence[str], rows: Sequence[Mapping[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise OpenADMETFeatureProjectionError(f"cannot read {label}: {exc}") from exc


def _file_hash(path: Path, label: str) -> str:
    return sha256(_read_bytes(path, label)).hexdigest()


def _write_new(path: Path, data: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(data)
    except OSError as exc:
        raise OpenADMETFeatureProjectionError(f"cannot write {path}: {exc}") from exc


def _destination_occupied(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _rename_noreplace(source: Path, destination: Path) -> None:
    if platform.system() != "Linux" or os.name != "posix":
        raise OpenADMETFeatureProjectionError(
            "atomic no-replace promotion requires Linux renameat2"
        )
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
    except (AttributeError, OSError) as exc:
        raise OpenADMETFeatureProjectionError(
            "renameat2 is unavailable; refusing non-atomic promotion"
        ) from exc
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
        os.fsencode(os.path.abspath(source)),
        -100,
        os.fsencode(os.path.abspath(destination)),
        1,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        if error_number == errno.EEXIST:
            raise OpenADMETFeatureProjectionError(
                f"output path already exists: {destination}; refusing overwrite"
            )
        raise OpenADMETFeatureProjectionError(
            f"renameat2 no-replace promotion failed: {os.strerror(error_number)}"
        )


def _make_writable(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        path.chmod(0o755)
        for child in path.iterdir():
            _make_writable(child)
    else:
        path.chmod(0o644)


def _match_hash(data: bytes, expected: str, label: str) -> None:
    if sha256(data).hexdigest() != expected:
        raise OpenADMETFeatureProjectionError(f"{label} SHA-256 mismatch")


def _json_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OpenADMETFeatureProjectionError(f"cannot parse {label}") from exc
    if not isinstance(value, dict):
        raise OpenADMETFeatureProjectionError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _decode_record(data: bytes, label: str) -> list[str]:
    try:
        return next(csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True))
    except (UnicodeError, csv.Error, StopIteration) as exc:
        raise OpenADMETFeatureProjectionError(f"cannot parse {label}") from exc


def _object(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise OpenADMETFeatureProjectionError(f"{key} must be an object")
    return cast(dict[str, Any], item)


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise OpenADMETFeatureProjectionError(f"{key} must be non-empty text")
    return item


def _digest(value: Mapping[str, Any], key: str) -> str:
    item = _text(value, key)
    _digest_text(item, key)
    return item


def _digest_text(value: str, label: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise OpenADMETFeatureProjectionError(f"{label} must be lowercase SHA-256")


def _integer(value: Mapping[str, Any], key: str) -> int:
    item = value.get(key)
    return _nonnegative_int(item, key)


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OpenADMETFeatureProjectionError(f"{label} must be a nonnegative integer")
    return value


def _required(row: Mapping[str, str], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise OpenADMETFeatureProjectionError(f"{key} must be non-empty")
    return value


def _positive_int(value: str, label: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise OpenADMETFeatureProjectionError(f"{label} must be an integer") from exc
    if parsed < 1:
        raise OpenADMETFeatureProjectionError(f"{label} must be positive")
    return parsed


def _integer_text(value: str, label: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise OpenADMETFeatureProjectionError(f"{label} must be an integer") from exc


__all__ = [
    "DIRECT_PREFIX_COLUMNS",
    "FEATURE_INPUT_COLUMNS",
    "FEATURE_INPUT_SCHEMA_VERSION",
    "GLOBAL_CONTRACT_SHA256",
    "FeatureProjectionResult",
    "OpenADMETFeatureProjectionError",
    "project_openadmet_feature_input",
]

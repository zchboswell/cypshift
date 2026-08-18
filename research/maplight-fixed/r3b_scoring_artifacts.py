"""R3B immutable input receipts and schemas."""

import csv
import hashlib
import io
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
V5_PATH = ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract_v5.json"
V4_PATH = ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract_v4.json"
V5_SHA256 = "596d9a246b130c00f07abfcaf73b369038b874ce556be5e6354df10e1d5ad6e2"
V4_SHA256 = "a37a316ceab297deb89d4458169d38d1c73d2edb39ab96ea4c77459a56b01254"
V3_SHA256 = "d728684cc3794bbe01ea44342202944a378968f097cb8f5490852b63721a6285"
RESEARCH_UV_LOCK_SHA256 = (
    "99e72821b69d9bb943a6e32adc7e0dec0e46c6d32df090241d4fb9296a4195d8"
)
PROJECTOR_SOURCE_SHA256 = (
    "455397869774d104144f0ca09c063f6c915046b4458da35040bf2c0dfaebfc18"
)
PREFLIGHT_SOURCE_SHA256 = (
    "4ac5c35a293a6a0ec32426a602c0a55e5fab31155205bbff44b80b58c7cc35df"
)
ENDPOINTS = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
SYSTEMS = (
    "TRACE-C0-ENDPOINT-MEDIAN",
    "TRACE-C1-MORGAN-CATBOOST",
    "TRACE-G0-MAPL-FIXED",
    "TRACE-C2-MORGAN-1NN",
)
MAPLIGHT = SYSTEMS[2]
COMPARISONS = (
    ("MORGAN_MINUS_MAPLIGHT", SYSTEMS[1]),
    ("MEDIAN_MINUS_MAPLIGHT", SYSTEMS[0]),
    ("ONE_NN_MINUS_MAPLIGHT", SYSTEMS[3]),
)
PRED_COLS = (
    "molecule_id",
    "endpoint",
    "component_id",
    "repeat",
    "outer_fold",
    "inner_fold",
    "scope",
    "system_id",
    "prediction",
    "applicability_score",
    "model_id",
    "feature_spec_id",
    "split_id",
)
TRUTH_COLS = (
    "observation_id",
    "molecule_id",
    "endpoint",
    "component_id",
    "repeat",
    "outer_fold",
    "inner_fold",
    "scope",
    "value_state",
    "point_eligible",
    "point",
    "low",
    "high",
    "std",
)
CELL_COLS = (
    "system_id",
    "endpoint",
    "repeat",
    "outer_fold",
    "scored_molecules",
    "scored_components",
    "component_macro_mae",
    "molecule_macro_mae",
)
BOOT_COLS = (
    "comparison_id",
    "control_system_id",
    "candidate_system_id",
    "point_delta",
    "lower_95",
    "upper_95",
    "accepted_replicates",
    "attempts",
    "lower_bound_positive",
)
Q90_COLS = (
    "endpoint",
    "repeat",
    "outer_fold",
    "system_id",
    "q90",
    "residual_molecules",
    "residual_components",
    "outer_molecules",
    "outer_components",
    "inclusive_coverage",
    "status",
)
OUTER_COMPLETE_COLS = (
    "molecule_id",
    "endpoint",
    "component_id",
    "repeat",
    "outer_fold",
    "completion_state",
    "value",
    "diagnostic_q90",
    "source_model_id",
)
FINAL_COMPLETE_COLS = (
    "molecule_id",
    "endpoint",
    "component_id",
    "completion_state",
    "value",
    "diagnostic_q90",
    "source_prediction_sha256",
)
RECEIPT_KEYS = (
    "parent_contract_sha256",
    "direct_observations_sha256",
    "group_folds_sha256",
    "r3a_feature_manifest_sha256",
    "model_public_manifest_sha256",
    "sealed_truth_manifest_sha256",
    "private_projection_audit_sha256",
    "preflight_receipt_sha256",
)
AUTHORITY_KEYS = (
    "global_surrogate_validation",
    "global_model",
    "internal_surrogate_metrics",
    "global_oof_predictions",
    "inner_oof_predictions",
    "parent_state_completion",
    "official_st_rae",
    "validation_frozen",
    "fold_assignments",
    "episodes",
    "episode_labels",
    "topology_viability",
    "submissions",
    "tdi",
    "transduction",
    "anchor_expansion",
    "transformations",
)
FREEZER_ACCOUNTING_FIELDS = (
    "cell_fragments_opened",
    "target_files_opened",
    "truth_files_opened",
    "private_audit_files_opened",
    "score_files_opened",
    "tdi_files_opened",
    "blinded_test_files_opened",
    "episode_or_anchor_files_opened",
    "submission_files_opened",
    "transductive_operations",
)


class R3BScoringError(RuntimeError):
    pass


class R3BUnderpowered(R3BScoringError):
    def __init__(
        self,
        message: str,
        preflight_receipt: Path,
        preflight_receipt_sha256: str,
    ) -> None:
        super().__init__(message)
        self.preflight_receipt = preflight_receipt
        self.preflight_receipt_sha256 = preflight_receipt_sha256


class R3BStageFailure(R3BScoringError):
    def __init__(
        self,
        message: str,
        stage: str,
        verified_receipts: Mapping[str, str] | None = None,
        source_receipts: Mapping[str, str] | None = None,
        accounting: Mapping[str, int] | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.verified_receipts = dict(verified_receipts or {})
        self.source_receipts = dict(source_receipts or {})
        self.accounting = dict(accounting or {})


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise R3BScoringError(message)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _freezer_source_sha() -> str:
    paths = (
        ROOT / "research/maplight-fixed/r3b_cell_freezer.py",
        ROOT / "research/maplight-fixed/r3b_cell_io.py",
    )
    entries = [
        f"{path.relative_to(ROOT).as_posix()}|{_sha(path.read_bytes())}"
        for path in paths
    ]
    return _sha(("\n".join(sorted(entries)) + "\n").encode("utf-8"))


def _cell_runner_source_sha() -> str:
    paths = (
        ROOT / "research/maplight-fixed/run_r3b_cells.py",
        ROOT / "research/maplight-fixed/r3b_cell_io.py",
        ROOT / "research/maplight-fixed/r3b_cell_freezer.py",
    )
    entries = [
        f"{path.relative_to(ROOT).as_posix()}|{_sha(path.read_bytes())}"
        for path in paths
    ]
    return _sha(("\n".join(sorted(entries)) + "\n").encode("utf-8"))


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value == value.lower()
        and all(char in "0123456789abcdef" for char in value)
    )


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _loads_unique(data: bytes | str, label: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            _require(key not in result, f"{label} contains duplicate JSON key")
            result[key] = value
        return result

    try:
        return json.loads(data, object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise R3BScoringError(f"{label} is invalid JSON") from exc


def _read(path: Path, expected: str | None, label: str) -> bytes:
    _require(path.is_file() and not path.is_symlink(), f"{label} is not regular")
    data = path.read_bytes()
    if expected is not None:
        _require(_sha(data) == expected, f"{label} receipt differs")
    return data


def _json(path: Path, expected: str | None, label: str) -> tuple[dict[str, Any], bytes]:
    data = _read(path, expected, label)
    value = _loads_unique(data, label)
    _require(isinstance(value, dict), f"{label} root differs")
    return cast(dict[str, Any], value), data


def _csv_bytes(columns: Sequence[str], rows: Iterable[Mapping[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row[column] for column in columns})
    return stream.getvalue().encode("utf-8")


def _csv_rows(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    _require(data.endswith(b"\n") and b"\r" not in data, f"{label} line endings differ")
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8"), newline=""))
        _require(
            tuple(reader.fieldnames or ()) == tuple(columns), f"{label} columns differ"
        )
        rows = [{str(key): str(value) for key, value in row.items()} for row in reader]
    except (UnicodeDecodeError, csv.Error) as exc:
        raise R3BScoringError(f"{label} is invalid CSV") from exc
    _require(all(None not in row for row in rows), f"{label} malformed row")
    return rows


def _uint(value: str, label: str, maximum: int) -> int:
    _require(value.isdigit(), f"{label} is not unsigned")
    result = int(value)
    _require(0 <= result <= maximum, f"{label} out of range")
    return result


def _contracts(
    expected_contract_sha256: str = V5_SHA256,
) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    v5_data = _read(V5_PATH, expected_contract_sha256, "v5 contract")
    v4_data = _read(V4_PATH, V4_SHA256, "v4 contract")
    v5_sha, v4_sha = _sha(v5_data), _sha(v4_data)
    v5, v4 = (
        _loads_unique(v5_data, "v5 contract"),
        _loads_unique(v4_data, "v4 contract"),
    )
    _require(isinstance(v5, dict) and isinstance(v4, dict), "contract roots differ")
    v5d, v4d = cast(dict[str, Any], v5), cast(dict[str, Any], v4)
    _require(
        v5d.get("schema_version", "").endswith(".v5")
        and v4d.get("schema_version", "").endswith(".v4"),
        "contract schema differs",
    )
    _require(
        v5d.get("parent", {}).get("sha256") == v4_sha,
        "parent contract receipt differs",
    )
    effective = dict(v4d)
    effective.update(
        {
            "schema_version": v5d["schema_version"],
            "parent": v5d["parent"],
            "artifact_binding": v5d["artifact_binding"],
            "amendments": v5d["amendments"],
            "synthetic_boundary": v5d["synthetic_boundary"],
        }
    )
    return effective, v4d, v5_sha, v4_sha


def _semantic_tokens(value: str) -> tuple[str, ...]:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return tuple(re.findall(r"[a-z0-9]+", separated.lower()))


def _has_forbidden_token(value: str) -> bool:
    tokens = _semantic_tokens(value)
    if any(token in {"truth", "score", "metric"} for token in tokens):
        return True
    return any(
        tuple(tokens[index : index + 2]) == ("private", "audit")
        for index in range(len(tokens) - 1)
    )


def _forbidden(value: object, parent: str = "") -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key).lower().replace("-", "_")
            if (
                parent == "accounting"
                and name
                in {
                    "truth_paths",
                    "truth_hashes",
                    "scores",
                    "metrics",
                    "truth_files_opened",
                    "private_audit_files_opened",
                    "score_files_opened",
                    "submission_files_opened",
                    "tdi_files_opened",
                    "blinded_test_files_opened",
                    "episode_or_anchor_files_opened",
                    "transductive_operations",
                }
                and child == 0
            ):
                continue
            if name == "authority":
                continue
            if name in {
                "outer_assessment_sha256",
                "selected_system_id",
                "outer_outcome",
                "token_writer_source_sha256",
            }:
                if _forbidden(child, name):
                    return True
                continue
            if name not in {
                "eval_metric",
                "random_score_type",
                "score_function",
            } and _has_forbidden_token(name):
                return True
            if _forbidden(child, name):
                return True
    elif isinstance(value, list):
        return any(_forbidden(item, parent) for item in value)
    elif isinstance(value, str) and parent != "columns":
        return _has_forbidden_token(value)
    return False


def _rel(path: str) -> Path:
    result = Path(path)
    _require(
        bool(not result.is_absolute() and result.parts and ".." not in result.parts),
        "unsafe relative path",
    )
    return result


def _validate_authority(value: object, label: str) -> None:
    _require(isinstance(value, Mapping), f"{label} authority differs")
    authority = cast(Mapping[str, object], value)
    _require(set(authority) == set(AUTHORITY_KEYS), f"{label} authority keys differ")
    _require(
        all(type(authority[key]) is bool for key in AUTHORITY_KEYS),
        f"{label} authority values differ",
    )


def _receipt(value: object, label: str, synthetic: bool) -> None:
    if not isinstance(value, str):
        raise R3BScoringError(f"{label} receipt differs")
    _require(
        synthetic
        or (
            len(value) == 64
            and value == value.lower()
            and all(character in "0123456789abcdef" for character in value)
        ),
        f"{label} receipt differs",
    )


def _resolved_parameters(
    value: object, stage: str, synthetic: bool
) -> list[dict[str, Any]]:
    expected = [SYSTEMS[1], MAPLIGHT] if stage == "outer" else [MAPLIGHT]
    _require(isinstance(value, list), f"{stage} resolved parameters differ")
    records = cast(list[object], value)
    _require(len(records) == len(expected), f"{stage} parameter count differs")
    result: list[dict[str, Any]] = []
    for record, system in zip(records, expected, strict=True):
        _require(isinstance(record, Mapping), f"{stage} parameter record differs")
        item = cast(Mapping[str, object], record)
        _require(
            set(item)
            == {
                "system_id",
                "canonical_get_all_params_json",
                "canonical_get_all_params_sha256",
            },
            f"{stage} parameter fields differ",
        )
        _require(item.get("system_id") == system, f"{stage} parameter order differs")
        canonical = item.get("canonical_get_all_params_json")
        if not isinstance(canonical, Mapping):
            raise R3BScoringError(f"{stage} parameter JSON differs")
        digest = item.get("canonical_get_all_params_sha256")
        _receipt(digest, f"{stage} parameter", synthetic)
        _require(
            _sha(_json_bytes(canonical)) == digest,
            f"{stage} parameter hash differs",
        )
        result.append(dict(item))
    return result


def _load_freeze(
    root: Path, expected: str, stage: str, contract_sha: str, synthetic: bool
) -> tuple[list[dict[str, str]], bytes, str, str]:
    _require(root.is_dir() and not root.is_symlink(), f"{stage} freeze root differs")
    manifest_name = (
        "global_oof_freeze_manifest.json"
        if stage == "outer"
        else "global_inner_oof_freeze_manifest.json"
    )
    csv_name = (
        "global_oof_predictions.csv"
        if stage == "outer"
        else "global_inner_oof_predictions.csv"
    )
    manifest, manifest_data = _json(
        root / manifest_name, expected, f"{stage} freeze manifest"
    )
    schema = (
        "cypshift.openadmet_cyp_2026.r3b_outer_freeze.v2"
        if stage == "outer"
        else "cypshift.openadmet_cyp_2026.r3b_inner_freeze.v2"
    )
    _require(
        manifest.get("schema_version") == schema
        and manifest.get("contract_sha256") == contract_sha,
        f"{stage} freeze receipt differs",
    )
    _require(not _forbidden(manifest), f"{stage} freeze exposes forbidden metadata")
    required = {
        "schema_version",
        "contract_sha256",
        "freezer_source_sha256",
        "preflight_receipt_sha256",
        "model_public_manifest_sha256",
        "feature_manifest_sha256",
        "cell_receipts",
        "prediction_artifact",
        "counts",
        "resolved_catboost_parameters",
        "accounting",
        "authority",
    }
    if stage == "inner":
        required.add("inner_selection_token_sha256")
    _require(set(manifest) == required, f"{stage} freeze fields differ")
    for field in (
        "freezer_source_sha256",
        "preflight_receipt_sha256",
        "model_public_manifest_sha256",
        "feature_manifest_sha256",
    ):
        _receipt(manifest[field], f"{stage} source", synthetic)
    _require(
        manifest["freezer_source_sha256"] == _freezer_source_sha(),
        f"{stage} freezer source differs",
    )
    if stage == "inner":
        _receipt(manifest["inner_selection_token_sha256"], f"{stage} token", synthetic)
    counts = manifest["counts"]
    _require(isinstance(counts, Mapping), f"{stage} freeze counts differ")
    counts = cast(Mapping[str, object], counts)
    _require(
        set(counts) == {"cell_receipts", "prediction_rows", "systems"},
        f"{stage} freeze count fields differ",
    )
    expected_cells = 60 if stage == "outer" else 240
    expected_systems = 4 if stage == "outer" else 1
    _require(
        counts.get("cell_receipts") == expected_cells
        and counts.get("systems") == expected_systems,
        f"{stage} freeze counts differ",
    )
    _require(
        all(type(value) is int and value >= 0 for value in counts.values()),
        f"{stage} freeze counts differ",
    )
    if not synthetic:
        _require(counts.get("prediction_rows") == 235440, f"{stage} row count differs")
    _require(
        isinstance(manifest["cell_receipts"], list)
        and len(cast(Sequence[object], manifest["cell_receipts"])) == expected_cells,
        f"{stage} receipt count differs",
    )
    for receipt in cast(Sequence[object], manifest["cell_receipts"]):
        _receipt(receipt, f"{stage} cell", synthetic)
    _resolved_parameters(manifest["resolved_catboost_parameters"], stage, synthetic)
    accounting = manifest["accounting"]
    _require(isinstance(accounting, Mapping), f"{stage} accounting differs")
    _require(
        set(cast(Mapping[str, object], accounting)) == set(FREEZER_ACCOUNTING_FIELDS),
        f"{stage} accounting fields differ",
    )
    _require(
        all(
            type(value) is int and value >= 0
            for value in cast(Mapping[str, object], accounting).values()
        ),
        f"{stage} accounting values differ",
    )
    values = cast(Mapping[str, object], accounting)
    _require(
        values["cell_fragments_opened"] == (60 if stage == "outer" else 240)
        and all(values[key] == 0 for key in FREEZER_ACCOUNTING_FIELDS[1:]),
        f"{stage} accounting values differ",
    )
    _validate_authority(manifest["authority"], stage)
    expected_authority = _authority(_contracts(contract_sha)[0], "INHERITED_ONLY")
    _require(manifest["authority"] == expected_authority, f"{stage} authority differs")
    artifact = cast(dict[str, Any], manifest.get("prediction_artifact", {}))
    _require(
        set(artifact)
        == {
            "schema_version",
            "path",
            "sha256",
            "rows",
            "eligible_rows",
            "bytes",
            "columns",
        },
        f"{stage} prediction receipt fields differ",
    )
    _require(
        artifact.get("schema_version") == ""
        and artifact.get("path") == csv_name
        and artifact.get("columns") == list(PRED_COLS),
        f"{stage} prediction receipt schema differs",
    )
    _receipt(artifact.get("sha256"), f"{stage} prediction", synthetic)
    _require(
        all(
            type(artifact.get(key)) is int and int(artifact[key]) >= 0
            for key in ("rows", "eligible_rows", "bytes")
        ),
        f"{stage} prediction receipt counts differ",
    )
    data = _read(
        root / _rel(csv_name), str(artifact.get("sha256")), f"{stage} predictions"
    )
    _require(len(data) == artifact["bytes"], f"{stage} prediction byte count differs")
    rows = _csv_rows(data, PRED_COLS, f"{stage} predictions")
    _require(
        len(rows) == int(artifact.get("rows", -1)), f"{stage} prediction count differs"
    )
    _require(
        counts["prediction_rows"] == artifact["rows"] == len(rows),
        f"{stage} prediction count differs",
    )
    wanted = set(SYSTEMS) if stage == "outer" else {MAPLIGHT}
    _require(
        {row["system_id"] for row in rows} == wanted, f"{stage} system set differs"
    )
    seen: set[tuple[str, ...]] = set()
    eligible_rows = 0
    for row in rows:
        _require(row["endpoint"] in ENDPOINTS, "prediction endpoint differs")
        repeat, outer = (
            _uint(row["repeat"], "prediction repeat", 2),
            _uint(row["outer_fold"], "prediction outer fold", 4),
        )
        if stage == "outer":
            _require(row["inner_fold"] in ("", "none"), "outer inner fold differs")
            key: tuple[str, ...] = (
                row["molecule_id"],
                row["endpoint"],
                str(repeat),
                str(outer),
                row["system_id"],
            )
        else:
            inner = _uint(row["inner_fold"], "prediction inner fold", 3)
            key = (
                row["molecule_id"],
                row["endpoint"],
                str(repeat),
                str(outer),
                str(inner),
                row["system_id"],
            )
        _require(key not in seen, "duplicate prediction identity")
        seen.add(key)
        try:
            prediction, applicability = (
                float(row["prediction"]),
                float(row["applicability_score"]),
            )
        except ValueError as exc:
            raise R3BScoringError("prediction is not numeric") from exc
        _require(
            math.isfinite(prediction)
            and math.isfinite(applicability)
            and 0 <= applicability <= 1,
            "prediction is nonfinite",
        )
        eligible_rows += 1
    _require(
        eligible_rows == int(artifact["eligible_rows"]),
        f"{stage} prediction eligible count differs",
    )
    if not synthetic:
        _require(len(rows) == 235440, "production prediction count differs")
    return rows, manifest_data, _sha(manifest_data), _sha(data)


def _load_truth(
    root: Path,
    expected: str,
    contract_sha: str,
    parent_sha: str,
    need_inner: bool,
    synthetic: bool,
) -> tuple[list[dict[str, str]], list[dict[str, str]], bytes, str]:
    _require(root.is_dir() and not root.is_symlink(), "sealed truth root differs")
    manifest, manifest_data = _json(
        root / "sealed_truth_manifest.json", expected, "sealed truth manifest"
    )
    _require(
        manifest.get("schema_version")
        == "cypshift.openadmet_cyp_2026.r3b_sealed_truth.v5"
        and manifest.get("contract_sha256") == contract_sha
        and manifest.get("parent_contract_sha256") == parent_sha,
        "sealed truth receipt differs",
    )
    required = {
        "schema_version",
        "contract_sha256",
        "parent_contract_sha256",
        "projector_source_sha256",
        "outer_truth",
        "inner_truth",
        "accounting",
        "authority",
    }
    _require(set(manifest) == required, "sealed truth fields differ")
    _receipt(manifest["projector_source_sha256"], "sealed truth source", synthetic)
    accounting = manifest["accounting"]
    sealed_fields = (
        "sealed_truth_files_written",
        "outer_truth_rows",
        "inner_truth_rows",
        "truth_metadata_public",
        "tdi_files_opened",
        "blinded_test_rows_opened",
        "episode_or_anchor_files_opened",
        "transductive_operations",
    )
    _require(isinstance(accounting, Mapping), "sealed truth accounting differs")
    _require(
        set(cast(Mapping[str, object], accounting)) == set(sealed_fields),
        "sealed truth accounting fields differ",
    )
    _require(
        all(
            type(value) is int and value >= 0
            for value in cast(Mapping[str, object], accounting).values()
        ),
        "sealed truth accounting values differ",
    )
    _validate_authority(manifest["authority"], "sealed truth")
    _require(
        manifest["authority"]
        == _authority(_contracts(contract_sha)[0], "INHERITED_ONLY"),
        "sealed truth authority differs",
    )
    outer_record = cast(dict[str, Any], manifest.get("outer_truth", {}))
    _validate_truth_record(outer_record, "outer truth")
    outer_data = _read(
        root / _rel(str(outer_record.get("path", "sealed_outer_truth.csv"))),
        str(outer_record.get("sha256")),
        "outer truth",
    )
    if "bytes" in outer_record:
        _require(
            len(outer_data) == outer_record["bytes"], "outer truth byte count differs"
        )
    outer_rows = _csv_rows(outer_data, TRUTH_COLS, "outer truth")
    _require(
        len(outer_rows) == int(outer_record.get("rows", -1)),
        "outer truth count differs",
    )
    _require(
        sum(_eligible(row) for row in outer_rows)
        == int(outer_record.get("eligible_rows", -1)),
        "outer truth eligible count differs",
    )
    if not synthetic:
        _require(
            outer_record.get("path") == "sealed_outer_truth.csv"
            and outer_record.get("rows") == 58860
            and outer_record.get("eligible_rows") == 19575,
            "outer truth receipt fields differ",
        )
    inner_record = cast(dict[str, Any], manifest.get("inner_truth", {}))
    _validate_truth_record(inner_record, "inner truth")
    inner_rows: list[dict[str, str]] = []
    if need_inner:
        inner_data = _read(
            root / _rel(str(inner_record.get("path", "sealed_inner_truth.csv"))),
            str(inner_record.get("sha256")),
            "inner truth",
        )
        if "bytes" in inner_record:
            _require(
                len(inner_data) == inner_record["bytes"],
                "inner truth byte count differs",
            )
        inner_rows = _csv_rows(inner_data, TRUTH_COLS, "inner truth")
        _require(
            len(inner_rows) == int(inner_record.get("rows", -1)),
            "inner truth count differs",
        )
        _require(
            sum(_eligible(row) for row in inner_rows)
            == int(inner_record.get("eligible_rows", -1)),
            "inner truth eligible count differs",
        )
        if not synthetic:
            _require(
                inner_record.get("path") == "sealed_inner_truth.csv"
                and inner_record.get("rows") == 235440
                and inner_record.get("eligible_rows") == 78300,
                "inner truth receipt fields differ",
            )
    values = cast(Mapping[str, object], accounting)
    _require(
        values["sealed_truth_files_written"] == 2
        and values["outer_truth_rows"] == len(outer_rows)
        and values["inner_truth_rows"] == int(inner_record["rows"])
        and values["truth_metadata_public"] == 0
        and all(
            values[key] == 0
            for key in (
                "tdi_files_opened",
                "blinded_test_rows_opened",
                "episode_or_anchor_files_opened",
                "transductive_operations",
            )
        ),
        "sealed truth accounting values differ",
    )
    if not synthetic:
        _require(len(outer_rows) == 58860, "production outer truth count differs")
        if need_inner:
            _require(len(inner_rows) == 235440, "production inner truth count differs")
        _require(
            values["outer_truth_rows"] == 58860
            and values["inner_truth_rows"] == 235440,
            "sealed truth accounting values differ",
        )
    return outer_rows, inner_rows, manifest_data, _sha(manifest_data)


def _validate_truth_record(value: Mapping[str, Any], label: str) -> None:
    """Accept the contract file receipt, retaining old fixture shorthand."""
    minimal = {"path", "sha256", "rows", "eligible_rows"}
    generic = minimal | {"bytes", "columns", "schema_version"}
    _require(
        set(value) == minimal or set(value) == generic,
        f"{label} receipt fields differ",
    )
    _require(
        all(
            type(value[key]) is int and value[key] >= 0
            for key in ("rows", "eligible_rows")
        ),
        f"{label} receipt counts differ",
    )
    if set(value) == generic:
        _require(
            type(value["bytes"]) is int
            and value["bytes"] >= 0
            and value["columns"] == list(TRUTH_COLS)
            and value["schema_version"] == "",
            f"{label} receipt schema differs",
        )


def _eligible(row: Mapping[str, str]) -> bool:
    try:
        return (
            row["point_eligible"] == "true"
            and row["value_state"] == "complete"
            and math.isfinite(float(row["point"]))
        )
    except (KeyError, ValueError):
        return False


def _truth_index(
    rows: Sequence[Mapping[str, str]], inner: bool
) -> dict[tuple[str, ...], dict[str, str]]:
    result: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        key: tuple[str, ...] = (
            row["molecule_id"],
            row["endpoint"],
            row["repeat"],
            row["outer_fold"],
        )
        if inner:
            key += (row["inner_fold"],)
        _require(key not in result, "duplicate truth identity")
        result[key] = dict(row)
    return result


def _authority(contract: Mapping[str, Any], status: str) -> dict[str, bool]:
    return {
        key: bool(value)
        for key, value in cast(Mapping[str, Any], contract["authority"][status]).items()
    }


def _verified() -> dict[str, str]:
    return {key: "" for key in RECEIPT_KEYS}


@dataclass(frozen=True)
class OuterStage:
    root: Path
    status: str
    assessment_sha256: str
    token_sha256: str
    verified_receipts: dict[str, str]
    source_receipts: dict[str, str] = dataclass_field(default_factory=dict)
    accounting: dict[str, int] = dataclass_field(default_factory=dict)

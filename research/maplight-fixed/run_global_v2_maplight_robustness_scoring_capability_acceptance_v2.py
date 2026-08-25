#!/usr/bin/env python3
"""Run the fixed-root G2-7F scorer-capability reacceptance once."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

import global_v2_maplight_execution_compiler as accepted_compiler
import global_v2_maplight_robustness_execution_compiler as capability_compiler
import global_v2_maplight_robustness_scoring_compiler as scoring
import global_v2_maplight_runner as maplight
import run_global_v2_maplight_robustness_no_fit_acceptance as no_fit_driver

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
BENCHMARK: Final = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT: Final = (
    BENCHMARK
    / "global_v2_maplight_robustness_scoring_capability_reacceptance_contract.json"
)
CONTRACT_SHA256: Final = (
    "b414b0cf1c130791a0dc0cf4cf80d8b9ec204d391a43e24b50e0644d9efae698"
)
D129_REJECTION: Final = (
    BENCHMARK / "global_v2_maplight_robustness_scoring_capability_rejection.json"
)
D129_REJECTION_SHA256: Final = (
    "e551c7558d8e71153ccea91f5bbeb8271839da5cfadb83bca88b4e509414848d"
)
OLD_DRIVER: Final = (
    ROOT
    / "research"
    / "maplight-fixed"
    / "run_global_v2_maplight_robustness_scoring_capability_acceptance.py"
)
OLD_DRIVER_SHA256: Final = (
    "3a52a0052ac1a9927d7d48a840c70abeb461e28a6e1705477683928ecad2512f"
)
SCORING_COMPILER_SHA256: Final = (
    "6f15205fccb4a7c2e1cc2c7244e31acf15d7fd34b285c85145bfde551da6f492"
)
FOCUSED_TESTS: Final = (
    ROOT
    / "tests"
    / "test_openadmet_global_v2_maplight_robustness_scoring_capability_reacceptance.py"
)
FIXED_PARENT_ROOT: Final = Path("/tmp/cypshift-g2-7f")
FIXED_WORK_ROOT: Final = FIXED_PARENT_ROOT / "scoring-capability-attempt-1"
OLD_WORK_ROOT: Final = Path("/tmp/cypshift-g2-7e-scoring-capability-attempt-1")
ACCEPTANCE: Final = (
    BENCHMARK / "global_v2_maplight_robustness_scoring_capability_acceptance_v2.json"
)
REJECTION: Final = (
    BENCHMARK
    / "global_v2_maplight_robustness_scoring_capability_reacceptance_rejection.json"
)
ATTEMPT_ID: Final = "G2-7F-SCORING-CAPABILITY-REACCEPTANCE-ATTEMPT-1"
SEMANTIC_SOURCE_ID: Final = sha256(
    b"cypshift-g2-7f-official-shaped-scoring-source-v1"
).hexdigest()


class ScoringCapabilityReacceptanceError(RuntimeError):
    """The fixed-root synthetic acceptance invariant failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ScoringCapabilityReacceptanceError(message)


def _load(path: Path) -> dict[str, Any]:
    return capability_compiler._load_json(path)


def _digest(label: str) -> str:
    return sha256(f"g2-7f-scoring-fixture-v1|{label}".encode()).hexdigest()


def _development_row(
    *,
    molecule: Mapping[str, object],
    endpoint: str,
    endpoint_index: int,
    point: str,
) -> dict[str, object]:
    molecule_id = str(molecule["molecule_id"])
    index = int(molecule_id.rsplit("-", 1)[1])
    pattern = (index + endpoint_index) % 5
    point_value = float(point)
    low = high = ""
    if pattern == 0:
        low = format(point_value - 0.15, ".17g")
        high = format(point_value + 0.15, ".17g")
    elif pattern == 1:
        low = format(point_value - 0.15, ".17g")
    elif pattern == 2:
        high = format(point_value + 0.15, ".17g")
    elif pattern == 4:
        low = "nan"
        high = format(point_value + 0.15, ".17g")
    source_row = index * len(capability_compiler.ENDPOINTS) + endpoint_index + 1
    observation_id = _digest(f"observation|{molecule_id}|{endpoint}")
    return {
        "observation_id": observation_id,
        "molecule_id": molecule_id,
        "source_row_id": f"{scoring.DIRECT_SOURCE_FILE}:{source_row}",
        "source_file": scoring.DIRECT_SOURCE_FILE,
        "source_row": source_row,
        "source_sha256": _digest("source-file"),
        "endpoint": endpoint,
        "raw_smiles": molecule["standardized_smiles"],
        "raw_point": point,
        "raw_low": low,
        "raw_high": high,
        "raw_std": "0.1",
        "point": point,
        "low": low,
        "high": high,
        "std": "0.1",
        "raw_structure_sha256": molecule["standardized_structure_hash"],
        "standardized_structure_hash": molecule["standardized_structure_hash"],
        "similarity_component_hash": molecule["primary_component_hash"],
        "scaffold_group_hash": _digest(f"scaffold|{index // 6}"),
        "value_state": "complete",
        "point_eligible": "true",
        "anchor_eligible": "true",
    }


def direct_observation_bytes(*, reverse: bool) -> bytes:
    """Return the frozen full-width source with opaque confirmatory suffixes."""

    molecules, _folds, targets, _arrays = no_fit_driver.fixture(reverse=False)
    target_map = {
        (str(row["molecule_id"]), str(row["endpoint"])): str(row["point"])
        for row in targets
    }
    records: list[tuple[tuple[str, str], bytes]] = []
    for molecule in molecules:
        molecule_id = str(molecule["molecule_id"])
        for endpoint_index, endpoint in enumerate(capability_compiler.ENDPOINTS):
            key = molecule_id, endpoint
            if int(cast(int, molecule["confirmatory"])) == 1:
                observation_id = _digest(f"observation|{molecule_id}|{endpoint}")
                raw = (
                    f"{observation_id},{molecule_id},".encode()
                    + b"\xff\xfeCONFIRMATORY_SUFFIX_MUST_REMAIN_OPAQUE\n"
                )
            else:
                row = _development_row(
                    molecule=molecule,
                    endpoint=endpoint,
                    endpoint_index=endpoint_index,
                    point=target_map[key],
                )
                raw = maplight.csv_bytes(
                    accepted_compiler.DIRECT_COLUMNS, [row]
                ).split(b"\n", 1)[1]
            records.append((key, raw))
    records.sort(key=lambda item: item[0], reverse=reverse)
    header = (",".join(accepted_compiler.DIRECT_COLUMNS) + "\n").encode()
    return header + b"".join(raw for _key, raw in records)


def _publish_scoring_source(*, root: Path, reverse: bool) -> Path:
    raw = direct_observation_bytes(reverse=reverse)
    manifest = {
        "schema_version": scoring.SYNTHETIC_SOURCE_SCHEMA,
        "synthetic": True,
        "scoring_contract_sha256": scoring.CONTRACT_SHA256,
        "semantic_source_id": SEMANTIC_SOURCE_ID,
        "physical_order_reversed": reverse,
        "population": dict(scoring.SYNTHETIC_POPULATION),
        "direct_observations_sha256": maplight.sha256_bytes(raw),
        "meaning": "G2-7F official-shaped scoring capability mechanics only",
    }
    return cast(
        Path,
        maplight.publish_files(
            root,
            {
                "direct_observations.csv": raw,
                "manifest.json": maplight.json_bytes(manifest),
            },
        ),
    )


def _relative_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): maplight.sha256_path(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _authenticate_static_boundary() -> None:
    _require(maplight.sha256_path(CONTRACT) == CONTRACT_SHA256, "contract differs")
    contract = _load(CONTRACT)
    _require(
        contract.get("gate")
        == "G2_7F_MAPLIGHT_ROBUSTNESS_SCORING_CAPABILITY_REACCEPTANCE_CONTRACT_FROZEN"
        and contract.get("base_commit")
        == "1b8c5f7271f05fb77701695b1b47ad9dc428938c",
        "contract identity differs",
    )
    _require(
        maplight.sha256_path(D129_REJECTION) == D129_REJECTION_SHA256,
        "D-129 rejection differs",
    )
    rejection = _load(D129_REJECTION)
    _require(
        rejection.get("status")
        == "G2_7E_MAPLIGHT_ROBUSTNESS_SCORING_CAPABILITY_REJECTED"
        and rejection.get("attempt_accounting", {}).get("attempts_consumed") == 1
        and rejection.get("attempt_accounting", {}).get("attempts_remaining") == 0
        and rejection.get("cleanup", {}).get(
            "synthetic_work_root_present_after_cleanup"
        )
        is False,
        "D-129 disposition differs",
    )
    _require(
        maplight.sha256_path(scoring.SCRIPT) == SCORING_COMPILER_SHA256,
        "scoring compiler differs",
    )
    _require(maplight.sha256_path(OLD_DRIVER) == OLD_DRIVER_SHA256, "old driver differs")
    _require(
        "the sole D-128 scoring-capability acceptance attempt is terminally consumed"
        in OLD_DRIVER.read_text(encoding="utf-8"),
        "old driver is not hard-disabled",
    )
    scoring.authenticate_static_boundary()


def _validate_cleanup_path(root: Path) -> None:
    """Exercise the accepted predicate on an absent candidate path."""

    _require(not root.exists(), "cleanup preflight root exists")
    no_fit_driver._safe_cleanup(root)
    _require(not root.exists(), "cleanup preflight created a root")


def _preflight() -> None:
    _authenticate_static_boundary()
    _require(Path("/tmp").resolve(strict=True) == Path("/tmp"), "/tmp differs")
    _require(
        FIXED_PARENT_ROOT == Path("/tmp/cypshift-g2-7f")
        and FIXED_WORK_ROOT
        == Path("/tmp/cypshift-g2-7f/scoring-capability-attempt-1")
        and FIXED_WORK_ROOT.is_absolute()
        and ".." not in FIXED_WORK_ROOT.parts
        and FIXED_WORK_ROOT.resolve(strict=False) == FIXED_WORK_ROOT
        and len(FIXED_WORK_ROOT.parts) >= 4,
        "fixed cleanup root differs",
    )
    _require(not FIXED_PARENT_ROOT.exists(), "fixed parent root exists")
    _require(not FIXED_WORK_ROOT.exists(), "fixed work root exists")
    _require(not OLD_WORK_ROOT.exists(), "rejected D-128 work root exists")
    _require(not ACCEPTANCE.exists(), "success terminal exists")
    _require(not REJECTION.exists(), "failure terminal exists")
    _validate_cleanup_path(FIXED_WORK_ROOT)
    _require(
        not FIXED_PARENT_ROOT.exists() and not FIXED_WORK_ROOT.exists(),
        "cleanup preflight changed fixed roots",
    )


def _create_work_root() -> None:
    os.mkdir(FIXED_PARENT_ROOT, mode=0o700)
    os.mkdir(FIXED_WORK_ROOT, mode=0o700)


def _cleanup_work_root() -> None:
    no_fit_driver._safe_cleanup(FIXED_WORK_ROOT)
    if FIXED_PARENT_ROOT.exists():
        _require(
            FIXED_PARENT_ROOT.is_dir()
            and not FIXED_PARENT_ROOT.is_symlink()
            and not any(FIXED_PARENT_ROOT.iterdir()),
            "fixed parent cleanup differs",
        )
        FIXED_PARENT_ROOT.rmdir()
    _require(
        not FIXED_WORK_ROOT.exists() and not FIXED_PARENT_ROOT.exists(),
        "fixed cleanup is incomplete",
    )


def _execute_two_roots() -> dict[str, Any]:
    roots: list[dict[str, Any]] = []
    capability_maps: list[dict[str, str]] = []
    source_manifest_hashes: list[str] = []
    for name, reverse in (("root-a", False), ("root-b", True)):
        root = FIXED_WORK_ROOT / name
        if reverse:
            scoring_source = _publish_scoring_source(
                root=root / "scoring-source", reverse=True
            )
            model_source = no_fit_driver.publish_source(
                root=root / "model-source", reverse=True
            )
        else:
            model_source = no_fit_driver.publish_source(
                root=root / "model-source", reverse=False
            )
            scoring_source = _publish_scoring_source(
                root=root / "scoring-source", reverse=False
            )
        model, scorer, preflight = capability_compiler.compile_capabilities(
            source_root=model_source,
            output_root=root / "d126-capabilities",
            mode="synthetic",
            expected_compiler_sha256=maplight.sha256_path(
                capability_compiler.SCRIPT
            ),
        )
        capability = scoring.compile_scoring_capability(
            direct_source_root=scoring_source,
            model_capability_root=model,
            scorer_capability_root=scorer,
            output_root=root / "scoring-capability",
            mode="synthetic",
            expected_compiler_sha256=SCORING_COMPILER_SHA256,
        )
        manifest = _load(capability / "manifest.json")
        capability_map = _relative_map(capability)
        capability_maps.append(capability_map)
        source_manifest_hashes.append(
            maplight.sha256_path(scoring_source / "manifest.json")
        )
        roots.append(
            {
                "name": name,
                "source_physical_order_reversed": reverse,
                "dependency_safe_launch_order_reversed": reverse,
                "d126_preflight_status": preflight["status"],
                "model_source_manifest_sha256": maplight.sha256_path(
                    model_source / "manifest.json"
                ),
                "scoring_source_manifest_sha256": source_manifest_hashes[-1],
                "scoring_capability_tree_sha256": maplight.sha256_bytes(
                    maplight.json_bytes(capability_map)
                ),
                "counts": manifest["counts"],
                "source_file_values": manifest["source_file_values"],
                "confirmatory_suffixes_opaque": manifest[
                    "confirmatory_suffixes_opaque"
                ],
                "accounting": manifest["accounting"],
            }
        )
    _require(
        source_manifest_hashes[0] != source_manifest_hashes[1],
        "opposite-order source receipts match",
    )
    _require(capability_maps[0] == capability_maps[1], "capability maps differ")
    return {
        "roots": roots,
        "scoring_capability_files_compared": len(capability_maps[0]),
        "scoring_capability_maps_byte_identical": True,
    }


def _success_terminal(evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": (
            "cypshift.openadmet_cyp_2026."
            "global_v2_maplight_robustness_scoring_capability_acceptance.v2"
        ),
        "status": "G2_7F_MAPLIGHT_ROBUSTNESS_SCORING_CAPABILITY_ACCEPTED",
        "attempt_id": ATTEMPT_ID,
        "reacceptance_contract_sha256": CONTRACT_SHA256,
        "d128_scoring_contract_sha256": scoring.CONTRACT_SHA256,
        "d129_rejection_sha256": D129_REJECTION_SHA256,
        "d126_acceptance_sha256": scoring.D126_ACCEPTANCE_SHA256,
        "permanently_unusable_d127_claim_sha256": scoring.D127_CLAIM_SHA256,
        "scoring_compiler_source_sha256": SCORING_COMPILER_SHA256,
        "acceptance_driver_source_sha256": maplight.sha256_path(SCRIPT),
        "focused_tests_sha256": maplight.sha256_path(FOCUSED_TESTS),
        "semantic_source_id": SEMANTIC_SOURCE_ID,
        **dict(evidence),
        "opposite_physical_order": True,
        "opposite_dependency_safe_launch_order": True,
        "synthetic_endpoint_rows_opened": 9600,
        "synthetic_development_rows_decoded": 7680,
        "synthetic_scoring_rows_emitted": 7680,
        "confirmatory_rows_prefix_checked_suffix_opaque": 1920,
        "confirmatory_value_fields_decoded": 0,
        "real_catboost_fits": 0,
        "development_metric_evaluations": 0,
        "official_operations": 0,
        "claims_created": 0,
        "claims_consumed": 0,
        "private_roots_retained": 0,
        "fixed_work_root_present_after_cleanup": False,
        "fixed_parent_root_present_after_cleanup": False,
        "model_quality_authority": False,
        "claim_authority": False,
        "accounting": {
            **scoring._zero_accounting(),
            "synthetic_source_rows_opened": 9600,
            "synthetic_development_rows_decoded": 7680,
            "synthetic_scoring_rows_emitted": 7680,
        },
    }


def _publish_terminal(path: Path, terminal: Mapping[str, Any]) -> Path:
    _require(not ACCEPTANCE.exists() and not REJECTION.exists(), "terminal exists")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(descriptor, "wb", closefd=True) as stream:
        stream.write(maplight.json_bytes(terminal))
        stream.flush()
        os.fsync(stream.fileno())
    return path


def run_formal_attempt() -> tuple[Path, bool]:
    """Execute exactly one fixed-root attempt and publish after complete cleanup."""

    evidence: dict[str, Any] | None = None
    failure: BaseException | None = None
    cleanup_failure: BaseException | None = None
    creation_started = False
    try:
        _preflight()
        creation_started = True
        _create_work_root()
        evidence = _execute_two_roots()
    except BaseException as exc:
        failure = exc
    finally:
        if creation_started:
            try:
                _cleanup_work_root()
            except BaseException as exc:
                cleanup_failure = exc
    if cleanup_failure is not None:
        raise ScoringCapabilityReacceptanceError(
            f"terminal cleanup failed: {type(cleanup_failure).__name__}"
        ) from cleanup_failure
    _require(
        not FIXED_WORK_ROOT.exists() and not FIXED_PARENT_ROOT.exists(),
        "fixed roots remain before terminal publication",
    )
    if failure is not None:
        rejection = {
            "schema_version": (
                "cypshift.openadmet_cyp_2026."
                "global_v2_maplight_robustness_scoring_capability_rejection.v2"
            ),
            "status": "G2_7F_MAPLIGHT_ROBUSTNESS_SCORING_CAPABILITY_REJECTED",
            "attempt_id": ATTEMPT_ID,
            "reacceptance_contract_sha256": CONTRACT_SHA256,
            "failure_type": type(failure).__name__,
            "failure_message": str(failure),
            "scoring_compiler_source_sha256": SCORING_COMPILER_SHA256,
            "acceptance_driver_source_sha256": maplight.sha256_path(SCRIPT),
            "focused_tests_sha256": maplight.sha256_path(FOCUSED_TESTS),
            "cleanup_complete": True,
            "private_roots_retained": 0,
            "real_catboost_fits": 0,
            "development_metric_evaluations": 0,
            "official_operations": 0,
            "claims_created": 0,
            "claims_consumed": 0,
            "model_quality_authority": False,
            "claim_authority": False,
        }
        return _publish_terminal(REJECTION, rejection), False
    _require(evidence is not None, "success evidence is absent")
    return _publish_terminal(ACCEPTANCE, _success_terminal(evidence)), True


def _main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments:
        print("G2-7F accepts no root or output arguments", file=sys.stderr)
        return 2
    try:
        terminal, success = run_formal_attempt()
    except (ScoringCapabilityReacceptanceError, scoring.RobustnessScoringCompilerError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(terminal)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(_main())

#!/usr/bin/env python3
"""Preserve the terminally rejected G2-7E scoring-capability attempt."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

import global_v2_maplight_robustness_execution_compiler as capability_compiler
import global_v2_maplight_robustness_scoring_compiler as scoring
import global_v2_maplight_runner as maplight
import run_global_v2_maplight_robustness_no_fit_acceptance as no_fit_driver

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
BENCHMARK: Final = ROOT / "benchmarks" / "openadmet_cyp_2026"
ACCEPTANCE: Final = (
    BENCHMARK / "global_v2_maplight_robustness_scoring_capability_acceptance.json"
)
REJECTION: Final = (
    BENCHMARK / "global_v2_maplight_robustness_scoring_capability_rejection.json"
)
FOCUSED_TESTS: Final = (
    ROOT
    / "tests"
    / "test_openadmet_global_v2_maplight_robustness_scoring_capability.py"
)
SEMANTIC_SOURCE_ID: Final = sha256(
    b"cypshift-g2-7e-official-shaped-scoring-source-v1"
).hexdigest()


class ScoringCapabilityAcceptanceError(RuntimeError):
    """The single-use synthetic acceptance invariant failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ScoringCapabilityAcceptanceError(message)


def _digest(label: str) -> str:
    return sha256(f"g2-7e-scoring-fixture-v1|{label}".encode()).hexdigest()


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
    """Return a full-width source with undecodable confirmatory suffixes."""

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
                raw = maplight.csv_bytes(accepted_direct_columns(), [row]).split(
                    b"\n", 1
                )[1]
            records.append((key, raw))
    records.sort(key=lambda item: item[0], reverse=reverse)
    header = (",".join(accepted_direct_columns()) + "\n").encode()
    return header + b"".join(raw for _key, raw in records)


def accepted_direct_columns() -> tuple[str, ...]:
    """Return the exact accepted 23-column observation schema."""

    import global_v2_maplight_execution_compiler as accepted_compiler

    return tuple(accepted_compiler.DIRECT_COLUMNS)


def publish_scoring_source(*, root: Path, reverse: bool) -> Path:
    raw = direct_observation_bytes(reverse=reverse)
    manifest = {
        "schema_version": scoring.SYNTHETIC_SOURCE_SCHEMA,
        "synthetic": True,
        "scoring_contract_sha256": scoring.CONTRACT_SHA256,
        "semantic_source_id": SEMANTIC_SOURCE_ID,
        "physical_order_reversed": reverse,
        "population": dict(scoring.SYNTHETIC_POPULATION),
        "direct_observations_sha256": maplight.sha256_bytes(raw),
        "meaning": "official-shaped scoring capability mechanics only",
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


def run_formal_acceptance(*, work_root: Path, output_path: Path) -> Path:
    """Refuse reuse of the consumed D-128 formal attempt."""

    del work_root, output_path
    raise ScoringCapabilityAcceptanceError(
        "the sole D-128 scoring-capability acceptance attempt is terminally consumed"
    )


def _rejected_formal_acceptance(*, work_root: Path, output_path: Path) -> Path:
    """Retain the exact rejected implementation below for historical audit."""

    _require(not work_root.exists(), "formal work root exists")
    _require(not output_path.exists(), "acceptance output exists")
    scoring.authenticate_static_boundary()
    roots: list[dict[str, Any]] = []
    capability_maps: list[dict[str, str]] = []
    source_manifest_hashes: list[str] = []
    try:
        for name, reverse in (("root-a", False), ("root-b", True)):
            root = work_root / name
            if reverse:
                scoring_source = publish_scoring_source(
                    root=root / "scoring-source", reverse=True
                )
                model_source = no_fit_driver.publish_source(
                    root=root / "model-source", reverse=True
                )
            else:
                model_source = no_fit_driver.publish_source(
                    root=root / "model-source", reverse=False
                )
                scoring_source = publish_scoring_source(
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
                expected_compiler_sha256=maplight.sha256_path(scoring.SCRIPT),
            )
            manifest = capability_compiler._load_json(capability / "manifest.json")
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
        _require(
            capability_maps[0] == capability_maps[1],
            "scoring capability maps differ",
        )
        acceptance = {
            "schema_version": (
                "cypshift.openadmet_cyp_2026."
                "global_v2_maplight_robustness_scoring_capability_acceptance.v1"
            ),
            "status": "G2_7E_MAPLIGHT_ROBUSTNESS_SCORING_CAPABILITY_ACCEPTED",
            "scoring_contract_sha256": scoring.CONTRACT_SHA256,
            "d126_acceptance_sha256": scoring.D126_ACCEPTANCE_SHA256,
            "permanently_unusable_d127_claim_sha256": scoring.D127_CLAIM_SHA256,
            "scoring_compiler_source_sha256": maplight.sha256_path(scoring.SCRIPT),
            "acceptance_driver_source_sha256": maplight.sha256_path(SCRIPT),
            "focused_tests_sha256": maplight.sha256_path(FOCUSED_TESTS),
            "semantic_source_id": SEMANTIC_SOURCE_ID,
            "roots": roots,
            "opposite_physical_order": True,
            "opposite_dependency_safe_launch_order": True,
            "scoring_capability_maps_byte_identical": True,
            "scoring_capability_files_compared": len(capability_maps[0]),
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
            "model_quality_authority": False,
            "claim_authority": False,
            "accounting": {
                **scoring._zero_accounting(),
                "synthetic_source_rows_opened": 9600,
                "synthetic_development_rows_decoded": 7680,
                "synthetic_scoring_rows_emitted": 7680,
            },
        }
    finally:
        no_fit_driver._safe_cleanup(work_root)
    _require(not work_root.exists(), "formal work cleanup is incomplete")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(descriptor, "wb", closefd=True) as stream:
        stream.write(maplight.json_bytes(acceptance))
        stream.flush()
        os.fsync(stream.fileno())
    return output_path


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ACCEPTANCE)
    arguments = parser.parse_args(argv)
    try:
        output = run_formal_acceptance(
            work_root=arguments.work_root.resolve(strict=False),
            output_path=arguments.output.resolve(strict=False),
        )
    except (ScoringCapabilityAcceptanceError, scoring.RobustnessScoringCompilerError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

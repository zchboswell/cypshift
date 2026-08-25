#!/usr/bin/env python3
"""Two-root no-fit acceptance for the G2-7C robustness execution path."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any, Final

import global_v2_maplight_robustness_execution_compiler as compiler
import global_v2_maplight_runner as maplight
import numpy as np

SCRIPT: Final = Path(__file__).resolve()
MOLECULES: Final = 1200
PRIMARY_COMPONENTS: Final = 600
DEVELOPMENT_MOLECULES: Final = 960
CONFIRMATORY_MOLECULES: Final = 240
SEMANTIC_SOURCE_ID: Final = sha256(
    b"g2-7c-maplight-robustness-no-fit-official-shaped-v1"
).hexdigest()
FOCUSED_TESTS: Final = (
    compiler.ROOT
    / "tests"
    / "test_openadmet_global_v2_maplight_robustness_bounded_execution.py"
)
PRIOR_CLEANUP_REJECTION: Final = (
    compiler.BENCHMARK
    / "global_v2_maplight_robustness_no_fit_acceptance_rejection.json"
)
PRIOR_CLEANUP_REJECTION_SHA256: Final = (
    "8fb6aba95cae2aa93b1fa78fbdb998bf0b8e7b6f47dda6adfe4c54d2c85d0ce3"
)
PRIOR_AUDIT_REJECTION: Final = (
    compiler.BENCHMARK
    / "global_v2_maplight_robustness_no_fit_acceptance_audit_rejection.json"
)
PRIOR_AUDIT_REJECTION_SHA256: Final = (
    "4e4c45ae722e06806295cf74a8e690e40ac71e6d580223106c8bbd73f563ec28"
)
PRIOR_CI_REJECTION: Final = (
    compiler.BENCHMARK
    / "global_v2_maplight_robustness_no_fit_acceptance_ci_rejection.json"
)
PRIOR_CI_REJECTION_SHA256: Final = (
    "93a8adeb9db9c2bb280d0cce862a7a570009d0dc8096161f195b5c0260e7669e"
)
PRIOR_CI_HOST_REJECTION: Final = (
    compiler.BENCHMARK
    / "global_v2_maplight_robustness_no_fit_acceptance_ci_host_rejection.json"
)
PRIOR_CI_HOST_REJECTION_SHA256: Final = (
    "37429202c0d7622fd51ade26e121c6fce6e6a0647f85ae19e7f06bce99e8f5b1"
)


class NoFitAcceptanceError(RuntimeError):
    """The synthetic source or formal acceptance invariant failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise NoFitAcceptanceError(message)


def _digest(label: str, value: int) -> str:
    return sha256(f"g2-7c-no-fit-v1|{label}|{value:06d}".encode()).hexdigest()


def _component_digest(group_id: str, values: Sequence[str]) -> str:
    material = f"g2-7c-component-v1|{group_id}|" + "|".join(sorted(values))
    return sha256(material.encode()).hexdigest()


def _bit_set(namespace: str, value: int, count: int) -> set[int]:
    pools = {
        "group50": (0, 2048),
        "pair55": (2048, 1024),
        "bridge50": (3072, 512),
        "component": (3584, 512),
    }
    start, width = pools[namespace]
    result: set[int] = set()
    counter = 0
    while len(result) < count:
        digest = sha256(
            f"g2-7c-fingerprint-v1|{namespace}|{value}|{counter}".encode()
        ).digest()
        for offset in range(0, len(digest), 2):
            result.add(
                start + int.from_bytes(digest[offset : offset + 2], "big") % width
            )
            if len(result) == count:
                break
        counter += 1
    return result


def fixture(
    *,
    reverse: bool,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, np.ndarray[Any, Any]],
]:
    """Return one mechanics-only official-shaped source in physical order."""

    molecules: list[dict[str, object]] = []
    primary_folds: list[dict[str, object]] = []
    targets: list[dict[str, object]] = []
    structure_hashes = [_digest("structure", component) for component in range(600)]
    primary_hashes = [_digest("primary", component) for component in range(600)]
    threshold_55_members: dict[int, list[str]] = {}
    threshold_50_members: dict[int, list[str]] = {}
    tautomer_primary_members: dict[int, list[str]] = {}
    for component in range(600):
        threshold_55_members.setdefault((component + 1) // 2, []).append(
            structure_hashes[component]
        )
        threshold_50_members.setdefault((component + 1) // 4, []).append(
            structure_hashes[component]
        )
        tautomer_primary_members.setdefault((component + 1) // 3, []).append(
            primary_hashes[component]
        )
    threshold_55_hashes = {
        group: _component_digest("THRESHOLD_0_55", members)
        for group, members in threshold_55_members.items()
    }
    threshold_50_hashes = {
        group: _component_digest("THRESHOLD_0_50", members)
        for group, members in threshold_50_members.items()
    }
    tautomer_hashes = {
        group: _component_digest("TAUTOMER_MERGED", members)
        for group, members in tautomer_primary_members.items()
    }
    bridge_groups: dict[int, int] = {}
    for group, members in threshold_50_members.items():
        component_ids = sorted(structure_hashes.index(value) for value in members)
        by_pair: dict[int, list[int]] = {}
        for component in component_ids:
            by_pair.setdefault((component + 1) // 2, []).append(component)
        pair_ids = sorted(by_pair)
        for left, right in zip(pair_ids, pair_ids[1:], strict=False):
            bridge_groups[max(by_pair[left])] = group
            bridge_groups[min(by_pair[right])] = group
    component_fingerprints = np.zeros((600, 4096), dtype=np.uint8)
    for component in range(600):
        bits = set()
        bits.update(_bit_set("group50", (component + 1) // 4, 60))
        bits.update(_bit_set("pair55", (component + 1) // 2, 20))
        if component in bridge_groups:
            bits.update(_bit_set("bridge50", bridge_groups[component], 7))
            bits.update(_bit_set("component", component, 13))
        else:
            bits.update(_bit_set("component", component, 20))
        component_fingerprints[component, sorted(bits)] = 1

    for index in range(MOLECULES):
        component = index // 2
        confirmatory = component >= 480
        molecule_id = f"SYN-G2-7C-{index:04d}"
        molecules.append(
            {
                "molecule_id": molecule_id,
                "standardized_structure_hash": structure_hashes[component],
                "standardized_smiles": f"SYNTHETIC_STRUCTURE_{component:04d}",
                "primary_component_hash": primary_hashes[component],
                "threshold_0_55_component_hash": threshold_55_hashes[
                    (component + 1) // 2
                ],
                "threshold_0_50_component_hash": threshold_50_hashes[
                    (component + 1) // 4
                ],
                "tautomer_component_hash": tautomer_hashes[(component + 1) // 3],
                "tautomer_key": _digest("tautomer-key", (component + 1) // 3),
                "confirmatory": int(confirmatory),
            }
        )
        for repeat in compiler.REPEATS:
            primary_folds.append(
                {
                    "molecule_id": molecule_id,
                    "repeat": repeat,
                    "outer_fold": (component + repeat * 2) % 5,
                }
            )
        for endpoint_index, endpoint in enumerate(compiler.ENDPOINTS):
            point: object = "CONFIRMATORY_SENTINEL_MUST_REMAIN_OPAQUE"
            if not confirmatory:
                value = 4.0 + ((component * 17 + endpoint_index * 13) % 200) / 100
                point = format(value, ".17g")
            targets.append(
                {
                    "molecule_id": molecule_id,
                    "endpoint": endpoint,
                    "point": point,
                }
            )

    rows = np.arange(MOLECULES, dtype=np.int64)[:, None]
    arrays: dict[str, np.ndarray[Any, Any]] = {}
    arrays[compiler.OVERLAY_FINGERPRINT_FILE] = np.packbits(
        component_fingerprints[np.arange(MOLECULES) // 2],
        axis=1,
        bitorder="big",
    )
    for offset, (name, columns, dtype) in enumerate(compiler.FEATURE_FILES, start=1):
        column_index = np.arange(columns, dtype=np.int64)[None, :]
        if dtype == np.dtype("int8"):
            array = ((rows * (11 + offset) + column_index * (7 + offset)) % 127) - 63
            arrays[name] = np.asarray(array, dtype=np.int8)
        else:
            array = (
                (rows * (19 + offset) + column_index * (23 + offset)) % 1009
            ) / 1009.0
            arrays[name] = np.asarray(array, dtype=np.float64)

    if reverse:
        molecules.reverse()
        primary_folds.reverse()
        targets.reverse()
        arrays = {
            name: np.ascontiguousarray(array[::-1]) for name, array in arrays.items()
        }
    return molecules, primary_folds, targets, arrays


def publish_source(*, root: Path, reverse: bool) -> Path:
    molecules, primary_folds, targets, arrays = fixture(reverse=reverse)
    files: dict[str, bytes] = {
        "molecules.csv": maplight.csv_bytes(compiler.MOLECULE_COLUMNS, molecules),
        "primary_folds.csv": maplight.csv_bytes(
            compiler.PRIMARY_FOLD_COLUMNS, primary_folds
        ),
        "targets.csv": maplight.csv_bytes(compiler.TARGET_COLUMNS, targets),
    }
    for name, array in arrays.items():
        files[name] = compiler._npy_bytes(array)
    manifest = {
        "schema_version": compiler.SOURCE_SCHEMA,
        "synthetic": True,
        "bounded_contract_sha256": compiler.BOUNDED_CONTRACT_SHA256,
        "parent_contract_sha256": compiler.PARENT_CONTRACT_SHA256,
        "semantic_source_id": SEMANTIC_SOURCE_ID,
        "physical_order_reversed": reverse,
        "population": {
            "all_molecules": MOLECULES,
            "development_molecules": DEVELOPMENT_MOLECULES,
            "confirmatory_molecules": CONFIRMATORY_MOLECULES,
        },
        "source_receipts": {
            name: maplight.sha256_bytes(value) for name, value in files.items()
        },
        "meaning": "official-shaped no-fit mechanics only; no model-quality authority",
    }
    files["manifest.json"] = maplight.json_bytes(manifest)
    return maplight.publish_files(root, files)


def _relative_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): maplight.sha256_path(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _safe_cleanup(root: Path) -> None:
    resolved = root.resolve(strict=False)
    _require(
        root.is_absolute()
        and ".." not in root.parts
        and resolved not in {Path("/"), Path.home()}
        and len(resolved.parts) >= 4,
        "cleanup root is unsafe",
    )
    if not resolved.exists():
        return
    _require(resolved.is_dir() and not resolved.is_symlink(), "cleanup root differs")
    for path in sorted(
        resolved.rglob("*"), key=lambda item: len(item.parts), reverse=True
    ):
        _require(not path.is_symlink(), "cleanup root contains a symlink")
        try:
            os.chmod(path, 0o755 if path.is_dir() else 0o600)
        except OSError:
            pass
    os.chmod(resolved, 0o700)
    shutil.rmtree(resolved)


def run_formal_acceptance(*, work_root: Path, output_path: Path) -> Path:
    """Run a two-root no-fit acceptance after implementation review."""

    # Wrapper and supervisor imports are intentionally local so source-fixture
    # tests cannot accidentally exercise model or process authority.
    import global_v2_maplight_resource_supervisor as supervisor
    import global_v2_maplight_robustness_execution_wrapper as wrapper

    _require(not work_root.exists(), "formal work root exists")
    _require(not output_path.exists(), "acceptance output exists")
    _require(
        maplight.sha256_path(PRIOR_CLEANUP_REJECTION) == PRIOR_CLEANUP_REJECTION_SHA256,
        "prior cleanup rejection receipt differs",
    )
    _require(
        maplight.sha256_path(PRIOR_AUDIT_REJECTION) == PRIOR_AUDIT_REJECTION_SHA256,
        "prior adapter-audit rejection receipt differs",
    )
    _require(
        maplight.sha256_path(PRIOR_CI_REJECTION) == PRIOR_CI_REJECTION_SHA256,
        "prior integration-CI rejection receipt differs",
    )
    _require(
        maplight.sha256_path(PRIOR_CI_HOST_REJECTION)
        == PRIOR_CI_HOST_REJECTION_SHA256,
        "prior integration-CI host rejection receipt differs",
    )
    roots: list[dict[str, Any]] = []
    terminal_maps: list[dict[str, str]] = []
    capability_maps: list[dict[str, str]] = []
    try:
        for name, reverse in (("root-a", False), ("root-b", True)):
            root = work_root / name
            source = publish_source(root=root / "source", reverse=reverse)
            model, scorer, preflight = compiler.compile_capabilities(
                source_root=source,
                output_root=root / "capabilities",
                mode="synthetic",
                expected_compiler_sha256=maplight.sha256_path(compiler.SCRIPT),
            )
            summaries: dict[str, Mapping[str, Any]] = {}
            for profile in ("full_retained", "deletion_selected"):
                terminal = wrapper.run_no_fit_replay(
                    model_capability_root=model,
                    scorer_capability_root=scorer,
                    work_root=root / f"work-{profile}",
                    output_root=root / "terminals" / profile,
                    selection_profile=profile,
                    checkpoint=wrapper.LocalCheckpointRecorder(),
                )
                summaries[profile] = {
                    "manifest": compiler._load_json(terminal / "manifest.json"),
                    "identities": compiler._load_json(
                        terminal / "identity_summary.json"
                    ),
                    "chronology": compiler._load_json(terminal / "chronology.json"),
                }
            terminal_map = _relative_map(root / "terminals")
            capability_map = _relative_map(root / "capabilities")
            terminal_maps.append(terminal_map)
            capability_maps.append(capability_map)
            roots.append(
                {
                    "name": name,
                    "source_physical_order_reversed": reverse,
                    "source_manifest_sha256": maplight.sha256_path(
                        source / "manifest.json"
                    ),
                    "capability_tree_sha256": maplight.sha256_bytes(
                        maplight.json_bytes(capability_map)
                    ),
                    "terminal_tree_sha256": maplight.sha256_bytes(
                        maplight.json_bytes(terminal_map)
                    ),
                    "preflight_status": preflight["status"],
                    "profiles": summaries,
                }
            )

        supervisor_evidence = wrapper.exercise_supervisor_acceptance(
            work_root=work_root / "supervisor"
        )
        _require(capability_maps[0] == capability_maps[1], "capability maps differ")
        _require(terminal_maps[0] == terminal_maps[1], "terminal maps differ")
        synthetic_predictions = sum(
            sum(
                int(value)
                for value in profile["identities"][
                    "synthetic_prediction_identities"
                ].values()
            )
            for root in roots
            for profile in root["profiles"].values()
        )
        checkpoints = sum(
            int(profile["chronology"]["checkpoints_acknowledged"])
            for root in roots
            for profile in root["profiles"].values()
        )
        acceptance = {
            "schema_version": (
                "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_no_fit_acceptance.v1"
            ),
            "status": "G2_7C_MAPLIGHT_ROBUSTNESS_NO_FIT_ACCEPTED",
            "bounded_contract_sha256": compiler.BOUNDED_CONTRACT_SHA256,
            "parent_contract_sha256": compiler.PARENT_CONTRACT_SHA256,
            "prior_cleanup_rejection_sha256": PRIOR_CLEANUP_REJECTION_SHA256,
            "prior_adapter_audit_rejection_sha256": PRIOR_AUDIT_REJECTION_SHA256,
            "prior_integration_ci_rejection_sha256": PRIOR_CI_REJECTION_SHA256,
            "prior_integration_ci_host_rejection_sha256": (
                PRIOR_CI_HOST_REJECTION_SHA256
            ),
            "compiler_source_sha256": maplight.sha256_path(compiler.SCRIPT),
            "wrapper_source_sha256": maplight.sha256_path(wrapper.SCRIPT),
            "supervisor_source_sha256": maplight.sha256_path(supervisor.SCRIPT),
            "acceptance_driver_source_sha256": maplight.sha256_path(SCRIPT),
            "focused_tests_sha256": maplight.sha256_path(FOCUSED_TESTS),
            "roots": roots,
            "opposite_physical_order": True,
            "capability_maps_byte_identical": True,
            "terminal_maps_byte_identical": True,
            "profiles_per_root": ["full_retained", "deletion_selected"],
            "model_double_invocations_total": 3480,
            "synthetic_prediction_identities_total": synthetic_predictions,
            "fit_and_stage_checkpoints_total": checkpoints,
            "capability_files_compared": len(capability_maps[0]),
            "terminal_files_compared": len(terminal_maps[0]),
            "real_catboost_fits": 0,
            "resource_projections": 0,
            "development_metric_evaluations": 0,
            "confirmatory_target_values_parsed": 0,
            "supervisor_evidence": supervisor_evidence,
            "accounting": {
                **compiler._zero_accounting(),
                "synthetic_source_rows_opened": 19_200,
                "synthetic_model_double_invocations": 3_480,
                "synthetic_prediction_identities": synthetic_predictions,
                "synthetic_metric_evaluations": 0,
                "warnings_observed": 0,
                "fallbacks_observed": 0,
            },
            "private_roots_retained": 0,
            "model_quality_authority": False,
            "claim_authority": False,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(maplight.json_bytes(acceptance))
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        _safe_cleanup(work_root)
    return output_path


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    run_formal_acceptance(
        work_root=arguments.work_root.resolve(), output_path=arguments.output.resolve()
    )
    return 0


if __name__ == "__main__":
    sys.exit(_main())

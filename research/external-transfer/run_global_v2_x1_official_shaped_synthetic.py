#!/usr/bin/env python3
"""Accept the EXP-X1 adapter on two official-shaped synthetic source roots."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tarfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import global_v2_x1_acquisition_wrapper as wrapper  # noqa: E402
import global_v2_x1_compiler as base  # noqa: E402
import global_v2_x1_real_source_adapter as adapter  # noqa: E402
import run_global_v2_x1_synthetic as fixture  # noqa: E402

from cypshift.openadmet_campaign_io import R2B_SCHEMA_VERSION  # noqa: E402
from cypshift.openadmet_global_v2_firewall import (  # noqa: E402
    is_confirmatory_component,
)
from cypshift.openadmet_validation import (  # noqa: E402
    FOLD_COLUMNS,
    OBSERVATION_COLUMNS,
)
from cypshift.openadmet_validation_contract import (  # noqa: E402
    DIRECT_SOURCE_FILE,
    SEEDS,
)

FOCUSED_TESTS: Final = wrapper.FOCUSED_TESTS
ACCEPTANCE_NAME: Final = "global_v2_x1_real_source_adapter_acceptance.json"
SOURCE_REVISION: Final = "synthetic-x1-official-shaped-v1"
ARCHIVE_MEMBER: Final = "chembl_37/chembl_37_sqlite/chembl_37.db"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise adapter.X1AdapterError(message)


def _csv_bytes(
    columns: Sequence[str], rows: Iterable[Mapping[str, object]]
) -> bytes:
    return base.csv_bytes(columns, rows)


def _component_labels() -> dict[str, str]:
    positive: list[str] = []
    negative: list[str] = []
    index = 0
    while len(positive) < 4 or len(negative) < 16:
        digest = hashlib.sha256(f"synthetic-x1-r2b-component-{index}".encode()).hexdigest()
        target = positive if is_confirmatory_component(digest) else negative
        if (target is positive and len(positive) < 4) or (
            target is negative and len(negative) < 16
        ):
            target.append(digest)
        index += 1
    selected = [*positive, *negative]
    return {
        f"x1-component-{component:02d}": selected[component]
        for component in range(20)
    }


def direct_rows() -> list[dict[str, str]]:
    labels = _component_labels()
    source_sha = hashlib.sha256(b"synthetic official-shaped direct source").hexdigest()
    rows: list[dict[str, str]] = []
    for source_row, challenge in enumerate(fixture.challenge_rows(), start=1):
        for endpoint in base.ENDPOINTS:
            observation_id = hashlib.sha256(
                f"{SOURCE_REVISION}|{source_row}|{endpoint}".encode()
            ).hexdigest()
            row = {name: "" for name in OBSERVATION_COLUMNS}
            row.update(
                {
                    "observation_id": observation_id,
                    "molecule_id": challenge["molecule_id"],
                    "source_row_id": f"{DIRECT_SOURCE_FILE}:{source_row}",
                    "source_file": DIRECT_SOURCE_FILE,
                    "source_row": str(source_row),
                    "source_sha256": source_sha,
                    "endpoint": endpoint,
                    "raw_smiles": challenge["raw_smiles"],
                    # These suffix fields are intentionally populated but must
                    # remain opaque to the adapter.
                    "raw_point": str(5.0 + source_row / 100),
                    "point": str(5.0 + source_row / 100),
                    "raw_structure_sha256": hashlib.sha256(
                        challenge["raw_smiles"].encode()
                    ).hexdigest(),
                    "standardized_structure_hash": hashlib.sha256(
                        f"untrusted-standardized-{source_row}".encode()
                    ).hexdigest(),
                    "similarity_component_hash": labels[
                        challenge["challenge_component"]
                    ],
                    "scaffold_group_hash": hashlib.sha256(
                        f"untrusted-scaffold-{source_row}".encode()
                    ).hexdigest(),
                    "value_state": "partial",
                    "point_eligible": "true",
                    "anchor_eligible": "false",
                }
            )
            rows.append(row)
    _require(len(rows) == 160, "direct fixture count differs")
    return rows


def group_fold_rows() -> list[dict[str, str]]:
    labels = _component_labels()
    component_by_molecule = {
        row["molecule_id"]: labels[row["challenge_component"]]
        for row in fixture.challenge_rows()
    }
    rows = [
        {
            "molecule_id": row["molecule_id"],
            "similarity_component_hash": component_by_molecule[row["molecule_id"]],
            "repeat": row["repeat"],
            "seed": str(SEEDS[int(row["repeat"])]),
            "outer_fold": row["assigned_outer"],
            "outer_validation_fold": row["outer_context"],
            "inner_fold": row["inner_fold"],
        }
        for row in fixture.fold_rows()
    ]
    _require(len(rows) == 600, "fold fixture count differs")
    return rows


def _placeholder_csv(label: str, reverse: bool) -> bytes:
    values = [f"{label}-a", f"{label}-b"]
    if reverse:
        values.reverse()
    return ("synthetic_placeholder\n" + "\n".join(values) + "\n").encode()


def publish_r2b(root: Path, *, reverse: bool) -> Path:
    _require(not root.exists() and not root.is_symlink(), "R2B fixture root exists")
    root.mkdir(parents=True)
    try:
        direct = sorted(
            direct_rows(),
            key=lambda row: (row["molecule_id"], row["endpoint"]),
            reverse=reverse,
        )
        folds = sorted(
            group_fold_rows(),
            key=lambda row: (
                row["molecule_id"],
                int(row["repeat"]),
                int(row["outer_validation_fold"]),
            ),
            reverse=reverse,
        )
        outputs = {
            "direct_observations.csv": _csv_bytes(OBSERVATION_COLUMNS, direct),
            "group_folds.csv": _csv_bytes(FOLD_COLUMNS, folds),
            "campaign_episodes_public.csv": _placeholder_csv("public", reverse),
            "campaign_episodes_truth.csv": _placeholder_csv("truth", reverse),
            "episode_label_masks.csv": _placeholder_csv("mask", reverse),
            "topology_viability.json": base.json_bytes(
                {
                    "schema_version": "synthetic-topology-viability.v1",
                    "physical_order": "reverse" if reverse else "canonical",
                }
            ),
        }
        for name, data in outputs.items():
            (root / name).write_bytes(data)
        manifest_outputs: dict[str, Any] = {}
        for name, data in outputs.items():
            value: dict[str, Any] = {"sha256": base.sha256_bytes(data)}
            if name.endswith(".csv"):
                value["rows"] = len(data.rstrip(b"\n").split(b"\n")) - 1
            else:
                value["schema_version"] = "synthetic-topology-viability.v1"
            manifest_outputs[name] = value
        manifest = {
            "schema_version": R2B_SCHEMA_VERSION,
            "source_revision": SOURCE_REVISION,
            "validation_contract": {
                "schema_version": "synthetic",
                "sha256": hashlib.sha256(b"synthetic validation contract").hexdigest(),
            },
            "inputs": {},
            "schemas": {
                "direct_observations.csv": list(OBSERVATION_COLUMNS),
                "group_folds.csv": list(FOLD_COLUMNS),
            },
            "policies": {"seeds": list(SEEDS)},
            "counts": {
                "direct_observations": len(direct),
                "group_fold_rows": len(folds),
                "episode_rows": 2,
                "expanded_queries": 0,
            },
            "outputs": manifest_outputs,
            "accounting": {"synthetic": True},
            "authority": {"synthetic_only": True},
            "deterministic": True,
        }
        (root / "manifest.json").write_bytes(base.json_bytes(manifest))
        base.seal_tree(root)
    except BaseException:
        base.cleanup(root)
        raise
    return root


def publish_archive(root: Path, *, reverse: bool) -> tuple[Path, str, str]:
    _require(not root.exists() and not root.is_symlink(), "archive fixture root exists")
    root.mkdir(parents=True)
    database = root / "chembl_37.db"
    fixture._write_sqlite(database, reverse)
    os.chmod(database, 0o444)
    database_hash = base.sha256_path(database)
    archive_path = root / "chembl_37_sqlite.tar.gz"
    with tarfile.open(archive_path, mode="w:gz", format=tarfile.PAX_FORMAT) as archive:
        info = tarfile.TarInfo(ARCHIVE_MEMBER)
        info.size = database.stat().st_size
        info.mode = 0o444
        info.mtime = 0
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""
        with database.open("rb") as stream:
            archive.addfile(info, stream)
    database.unlink()
    archive_hash = base.sha256_path(archive_path)
    os.chmod(archive_path, 0o444)
    os.chmod(root, 0o555)
    return archive_path, archive_hash, database_hash


def run_one(source: Path, terminal: Path, *, reverse: bool) -> dict[str, str]:
    archive_root = source / "archive"
    r2b_root = source / "r2b"
    extract_root = source / "extracted"
    archive_path, archive_hash, database_hash = publish_archive(
        archive_root, reverse=reverse
    )
    publish_r2b(r2b_root, reverse=reverse)
    database, archive_receipt = wrapper.secure_extract_database(
        archive_path=archive_path,
        extract_root=extract_root,
        expected_archive_sha256=archive_hash,
    )
    adapter.run_replay(
        database_path=database,
        challenge_root=r2b_root,
        replay_root=terminal,
        synthetic=True,
    )
    values = {
        "archive_sha256": archive_hash,
        "database_sha256": database_hash,
        "r2b_manifest_sha256": base.sha256_path(r2b_root / "manifest.json"),
        "direct_sha256": base.sha256_path(r2b_root / "direct_observations.csv"),
        "folds_sha256": base.sha256_path(r2b_root / "group_folds.csv"),
        "extracted_database_sha256": cast(str, archive_receipt["database_sha256"]),
    }
    _require(
        values["database_sha256"] == values["extracted_database_sha256"],
        "archive extraction changed database bytes",
    )
    return values


def acceptance_files(
    *,
    terminals: Sequence[Path],
    physical: Sequence[Mapping[str, str]],
    focused_tests_passed: int,
) -> dict[str, bytes]:
    _require(len(terminals) == 2 and len(physical) == 2, "acceptance root count differs")
    maps = [base.relative_byte_map(root) for root in terminals]
    _require(maps[0] == maps[1], "adapter terminal maps differ")
    manifest = base.read_json(terminals[0] / "manifest.json")
    _require(
        manifest.get("status") == adapter.SYNTHETIC_STATUS
        and manifest.get("synthetic") is True
        and manifest.get("counts")
        == {
            "activity_rows": 336,
            "eligible_activity_rows": 320,
            "ineligible_activity_rows": 16,
            "external_compounds": 80,
            "challenge_molecules": 40,
            "challenge_components": 20,
            "global_forbidden_structures": 20,
            "union_nodes": 110,
            "union_components": 40,
            "outer_endpoint_cells": 60,
            "inner_endpoint_cells": 240,
            "confirmatory_endpoint_cells": 4,
        },
        "adapter terminal oracle differs",
    )
    accounting = manifest["accounting"]
    _require(
        accounting["target_values_parsed"] == 0
        and accounting["target_values_retained"] == 0
        and accounting["official_model_fits"] == 0
        and accounting["official_predictions_generated"] == 0
        and accounting["live_uploads"] == 0,
        "adapter accounting differs",
    )
    sqlite_hashes = [item["database_sha256"] for item in physical]
    r2b_hashes = [
        base.sha256_bytes(
            base.json_bytes(
                {
                    "manifest": item["r2b_manifest_sha256"],
                    "direct": item["direct_sha256"],
                    "folds": item["folds_sha256"],
                }
            )
        )
        for item in physical
    ]
    _require(sqlite_hashes[0] != sqlite_hashes[1], "physical SQLite hashes match")
    _require(r2b_hashes[0] != r2b_hashes[1], "physical R2B hashes match")
    value = {
        "schema_version": wrapper.ACCEPTANCE_SCHEMA,
        "status": adapter.SYNTHETIC_STATUS,
        "claim_template_sha256": adapter.CLAIM_SHA256,
        "source_bindings": {
            "accepted_compiler_sha256": base.sha256_path(base.SCRIPT),
            "real_source_adapter_sha256": base.sha256_path(adapter.SCRIPT),
            "acquisition_wrapper_sha256": base.sha256_path(wrapper.SCRIPT),
            "official_shaped_synthetic_driver_sha256": base.sha256_path(SCRIPT),
            "focused_tests_sha256": base.sha256_path(FOCUSED_TESTS),
            "identity_projector_sha256": base.sha256_path(
                ROOT / "src/cypshift/openadmet_features.py"
            ),
            "r2b_schema_source_sha256": base.sha256_path(
                ROOT / "src/cypshift/openadmet_campaign_io.py"
            ),
            "fold_schema_source_sha256": base.sha256_path(
                ROOT / "src/cypshift/openadmet_validation.py"
            ),
            "confirmatory_firewall_sha256": base.sha256_path(
                ROOT / "src/cypshift/openadmet_global_v2_firewall.py"
            ),
            "chemistry_source_sha256": base.sha256_path(base.CHEMISTRY_SOURCE),
            "topology_source_sha256": base.sha256_path(base.TOPOLOGY_SOURCE),
            "root_lock_sha256": base.sha256_path(base.LOCK),
        },
        "roots": 2,
        "physical_sqlite_sha256": sqlite_hashes,
        "physical_sqlite_hashes_differ": True,
        "physical_r2b_tree_sha256": r2b_hashes,
        "physical_r2b_hashes_differ": True,
        "relative_terminal_maps_byte_identical": True,
        "terminal_tree_sha256": base.sha256_bytes(base.json_bytes(maps[0])),
        "files_compared": len(maps[0]),
        "logical_source_sha256": manifest["logical_source_sha256"],
        "counts": manifest["counts"],
        "projection": manifest["projection"],
        "support_decisions": base.read_json(
            terminals[0] / "x1_adapter_support_decisions.json"
        ),
        "focused_tests_passed": focused_tests_passed,
        "adversarial_boundaries_passed": True,
        "accounting": accounting,
        "private_roots_retained": 0,
        "mutable_roots_retained": 0,
        "authority": manifest["authority"],
        "scientific_interpretation": (
            "Synthetic adapter, archive, identity-projection, fold, union, and support "
            "mechanics only; no external-support or model-quality evidence."
        ),
        "next_gate": (
            "Review and integrate this exact acceptance, require green post-main CI, "
            "then derive and consume the frozen private claim exactly once."
        ),
    }
    return {ACCEPTANCE_NAME: base.json_bytes(value)}


def run_formal(work_root: Path, acceptance_root: Path, focused_tests_passed: int) -> Path:
    _require(focused_tests_passed > 0, "focused test count must be positive")
    _require(not work_root.exists() and not work_root.is_symlink(), "work root exists")
    _require(
        not acceptance_root.exists() and not acceptance_root.is_symlink(),
        "acceptance root exists",
    )
    work_root.mkdir(parents=True)
    terminals: list[Path] = []
    physical: list[dict[str, str]] = []
    try:
        for label, reverse in (("a", False), ("b", True)):
            source = work_root / f"source-{label}"
            source.mkdir()
            terminal = work_root / f"terminal-{label}"
            terminals.append(terminal)
            physical.append(run_one(source, terminal, reverse=reverse))
        files = acceptance_files(
            terminals=terminals,
            physical=physical,
            focused_tests_passed=focused_tests_passed,
        )
        base.publish_files(acceptance_root, files)
    finally:
        base.cleanup(work_root)
    _require(not work_root.exists(), "formal work-root cleanup differs")
    return acceptance_root / ACCEPTANCE_NAME


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", required=True, type=Path)
    parser.add_argument("--acceptance-root", required=True, type=Path)
    parser.add_argument("--focused-tests-passed", required=True, type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = run_formal(
        args.work_root.resolve(),
        args.acceptance_root.resolve(),
        args.focused_tests_passed,
    )
    print(receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ACCEPTANCE_NAME",
    "FOCUSED_TESTS",
    "SCRIPT",
    "acceptance_files",
    "direct_rows",
    "group_fold_rows",
    "publish_archive",
    "publish_r2b",
    "run_formal",
    "run_one",
]

from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT = (
    BENCHMARK / "global_v2_maplight_robustness_official_orchestration_seal_erratum.json"
)
CONTRACT_SHA256 = "a3e1bd653f28297357380ad14da3fcd640d89d3476954830c8fd63c2f3faeb33"
D137_CONTRACT = (
    BENCHMARK
    / "global_v2_maplight_robustness_official_orchestration_repair_contract.json"
)
D135_ACCEPTANCE = (
    BENCHMARK / "global_v2_maplight_robustness_execution_acceptance_v2.json"
)
D136_BRIDGE = (
    BENCHMARK / "global_v2_maplight_robustness_focused_test_provenance_bridge.json"
)
TRACKED_CLAIM = BENCHMARK / "global_v2_maplight_robustness_execution_claim_v2.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contract() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(CONTRACT.read_text(encoding="utf-8")))


def _rename_noreplace(source: Path, destination: Path) -> None:
    source_parent = os.open(source.parent, os.O_RDONLY | os.O_DIRECTORY)
    destination_parent = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        result = renameat2(
            source_parent,
            os.fsencode(source.name),
            destination_parent,
            os.fsencode(destination.name),
            1,
        )
        if result:
            observed = ctypes.get_errno()
            raise OSError(observed, os.strerror(observed), destination)
    finally:
        os.close(source_parent)
        os.close(destination_parent)


def _fsync(path: Path, *, directory: bool = False) -> None:
    flags = os.O_RDONLY | (os.O_DIRECTORY if directory else 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def test_erratum_binds_integrated_parent_evidence_and_unchanged_claim() -> None:
    value = _contract()
    parents = value["parents"]
    assert _sha256(CONTRACT) == CONTRACT_SHA256
    assert value["status"] == (
        "G2_7H_MAPLIGHT_ROBUSTNESS_OFFICIAL_ORCHESTRATION_SEAL_ERRATUM_FROZEN"
    )
    assert parents["d137_repair_contract_sha256"] == _sha256(D137_CONTRACT)
    assert parents["d135_science_kernel_acceptance_sha256"] == _sha256(D135_ACCEPTANCE)
    assert parents["d136_provenance_bridge_sha256"] == _sha256(D136_BRIDGE)
    assert parents["tracked_claim_sha256"] == _sha256(TRACKED_CLAIM)
    claim = json.loads(TRACKED_CLAIM.read_text(encoding="utf-8"))
    assert claim["consumptions"] == 0
    assert claim["usable"] is False
    assert sum(key.startswith("future_") and claim[key] is None for key in claim) == 5


def test_corrected_sequence_is_atomic_finally_readonly_and_no_replace(
    tmp_path: Path,
) -> None:
    source_parent = tmp_path / "source-parent"
    destination_parent = tmp_path / "destination-parent"
    source_parent.mkdir()
    destination_parent.mkdir()
    staging = source_parent / "terminal-staging"
    staging.mkdir(mode=0o700)
    leaf = staging / "manifest.json"
    leaf.write_bytes(b"{}\n")
    os.chmod(leaf, 0o444)
    _fsync(leaf)
    _fsync(staging, directory=True)
    source_stat = staging.stat(follow_symlinks=False)
    leaf_stat = leaf.stat(follow_symlinks=False)
    assert stat.S_IMODE(source_stat.st_mode) == 0o700
    assert stat.S_IMODE(leaf_stat.st_mode) == 0o444

    final = destination_parent / "terminal"
    _rename_noreplace(staging, final)
    os.chmod(final, 0o555)
    _fsync(final, directory=True)
    _fsync(source_parent, directory=True)
    _fsync(destination_parent, directory=True)
    final_stat = final.stat(follow_symlinks=False)
    final_leaf_stat = (final / "manifest.json").stat(follow_symlinks=False)
    assert (final_stat.st_dev, final_stat.st_ino) == (
        source_stat.st_dev,
        source_stat.st_ino,
    )
    assert (final_leaf_stat.st_dev, final_leaf_stat.st_ino) == (
        leaf_stat.st_dev,
        leaf_stat.st_ino,
    )
    assert stat.S_IMODE(final_stat.st_mode) == 0o555
    assert stat.S_IMODE(final_leaf_stat.st_mode) == 0o444
    assert (final / "manifest.json").read_bytes() == b"{}\n"

    collision_source = source_parent / "collision-staging"
    collision_source.mkdir(mode=0o700)
    with pytest.raises(OSError) as caught:
        _rename_noreplace(collision_source, final)
    assert caught.value.errno == errno.EEXIST
    assert final.is_dir()
    assert collision_source.is_dir()


def test_erratum_changes_only_seal_order_and_has_zero_scientific_authority() -> None:
    value = _contract()
    unchanged = value["unchanged_d137_invariants"]
    accounting = value["current_milestone_accounting"]
    assert len(value["corrected_sequence"]) == 8
    assert value["security_boundary"] == {
        "final_terminal_read_only": True,
        "staging_root_before_promotion_mode": "0700",
        "staging_leaf_modes_before_promotion": "0444",
        "final_terminal_root_mode": "0555",
        "concurrent_malicious_same_uid_root_substitution_in_scope": False,
        "trusted_child_rule": (
            "Only the accepted trusted child and outer publisher may create the "
            "fixed staging root during supervision. Pre-existing, orphaned, root, "
            "dangling-root, and descendant symlinks are unlinked without following "
            "them; an unrelated sentinel must remain byte-identical."
        ),
        "rationale": value["security_boundary"]["rationale"],
    }
    assert unchanged["science_kernel_bytes"] is True
    assert unchanged["fit_prediction_metric_bootstrap_selection_and_gates"] is True
    assert unchanged["tracked_claim_bytes"] is True
    assert unchanged["retry_resume_move_overwrite_replacement"] is False
    assert accounting["temporary_rename_probes"] == 4
    assert all(
        accounting[name] == 0
        for name in (
            "official_source_or_baseline_bytes_opened",
            "claims_created",
            "claims_consumed",
            "model_double_invocations",
            "real_catboost_fits",
            "predictions_generated",
            "development_metric_evaluations",
            "confirmatory_truth_values_opened",
            "blinded_test_rows_opened",
            "tdi_rows_opened",
            "submission_rows_generated",
            "leaderboard_observations_used_for_selection",
            "live_uploads",
        )
    )
    assert accounting["model_quality_authority"] is False
    assert accounting["official_execution_authority"] is False
    assert accounting["claim_authority"] is False
    assert accounting["repair_contract_erratum_authority"] is True

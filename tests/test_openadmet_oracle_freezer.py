from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from test_openadmet_oracle_pair_runner import g0

import cypshift.openadmet_oracle_freezer_io as freezer_io
import cypshift.openadmet_oracle_freezer_publish as freezer_publish
from cypshift.openadmet_oracle_freezer import (
    OracleOuterFreezerError,
    OuterContextInput,
    freeze_outer_predictions,
)
from cypshift.openadmet_oracle_freezer_g0 import G0_RUNTIME
from cypshift.openadmet_oracle_freezer_io import (
    FREEZE_STATUS,
    FREEZER_SOURCE_FILES,
    PAIR_SYSTEMS,
    SYSTEMS,
    TOKEN_SYSTEMS,
    EligibilityInput,
    FragmentInput,
    G0Input,
    TokenInput,
    freezer_source_bundle_sha256,
    g0_source_bundle_sha256,
    pair_runner_source_bundle_sha256,
)
from cypshift.openadmet_oracle_pair_cell import (
    FRAGMENT_COLUMNS,
    candidate_id,
    cell_id,
    fragment_id,
)
from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS
from cypshift.openadmet_oracle_projection import DENIED_AUTHORITY, SOURCE_PARENT_FILES
from cypshift.openadmet_oracle_sealed import (
    ELIGIBILITY_COLUMNS,
    RESOLVED_CONTRACT_SHA256,
    SEALED_SCHEMA_VERSION,
    SEALED_STATUS,
)
from cypshift.openadmet_oracle_validation import CLIFF_COLUMNS, TRUTH_COLUMNS
from cypshift.openadmet_transformation_io import canonical_csv_bytes


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _compact(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _pretty(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode()


def _csv(columns: tuple[str, ...], rows: list[dict[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=list(columns),
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def _readonly(root: Path) -> None:
    for path in root.iterdir():
        path.chmod(0o444)
    root.chmod(0o555)


def _source_binding() -> dict[str, Any]:
    parents = {name: _sha(name.encode()) for name in SOURCE_PARENT_FILES}
    records = {
        name: {"sha256": digest, "bytes": len(name)} for name, digest in parents.items()
    }
    return {
        "manifest_receipt": {"sha256": "a" * 64, "bytes": 100},
        "schema_version": "cypshift.openadmet_cyp_2026.oracle_source_bundle.v1",
        "contract_sha256": (
            "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
        ),
        "parent_receipts": parents,
        "input_receipts": records,
        "source_receipts": records,
    }


def _token_root(
    root: Path, system: str, repeat: int, outer: int
) -> tuple[TokenInput, dict[str, Any]]:
    coordinates = {
        "C2": (1.0, None),
        "C3": (1.0, 2.0),
        "T0": (1.0, 2.0),
        "A0": (None, 2.0),
        "A1": (None, 2.0),
        "A2": (1.0, None),
    }
    alpha, lambda_value = coordinates[system]
    token = {
        "schema_version": (
            "cypshift.openadmet_cyp_2026.r5c_score_free_selection_token.v1"
        ),
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "system_id": system,
        "repeat": repeat,
        "outer_fold": outer,
        "candidate_id": candidate_id(system, alpha, lambda_value),
        "alpha": alpha,
        "lambda": lambda_value,
        "candidate_receipt_sha256": _sha(
            f"candidate-{system}-{repeat}-{outer}".encode()
        ),
        "scorer_receipt_sha256": _sha(f"scorer-{system}-{repeat}-{outer}".encode()),
    }
    data = _compact(token)
    root.mkdir(parents=True)
    (root / "selection_token.json").write_bytes(data)
    _readonly(root)
    return (
        TokenInput(system, repeat, outer, alpha, lambda_value, root, _sha(data)),
        token,
    )


def _g0_root(
    root: Path,
    *,
    repeat: int,
    outer: int,
    episode: str,
    query: str,
    model_manifest: str,
    source_binding: dict[str, Any],
) -> tuple[Path, str, dict[str, Any]]:
    columns = (
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
    component = _sha(f"component-{repeat}-{outer}".encode())
    fragment = _csv(
        columns,
        [
            {
                "molecule_id": query,
                "endpoint": "CYP3A4",
                "component_id": component,
                "repeat": str(repeat),
                "outer_fold": str(outer),
                "inner_fold": "",
                "scope": "openadmet-oracle-outer-v1",
                "system_id": "TRACE-G0-MAPL-FIXED",
                "prediction": "1",
                "applicability_score": "0.5",
                "model_id": _sha(f"model-{episode}".encode()),
                "feature_spec_id": "maplight-fixed-stage-a-v1",
                "split_id": _sha(f"split-{episode}".encode()),
            }
        ],
    )
    source_receipts = {
        name: _sha((freezer_io.ROOT / name).read_bytes())
        for name in freezer_io.G0_SOURCE_FILES
    }
    target_manifest = _sha(f"target-{episode}".encode())
    candidate = candidate_id("G0", None, None)
    accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    accounting["direct_target_values_parsed"] = 11
    accounting["anchor_labels_exposed_to_models"] = 1
    accounting["maplight_model_fits"] = 1
    manifest = {
        "schema_version": ("cypshift.openadmet_cyp_2026.r5c_g0_prediction_fragment.v1"),
        "status": "R5_ORACLE_G0_EPISODE_COMPLETE",
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "parent_contract_sha256": (
            "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
        ),
        "runner_source_sha256": source_receipts[
            "research/maplight-fixed/run_r5_oracle_g0.py"
        ],
        "g0_source_bundle_sha256": g0_source_bundle_sha256(),
        "g0_source_file_receipts": source_receipts,
        "model_public_manifest_sha256": model_manifest,
        "episode_target_manifest_sha256": target_manifest,
        "trusted_episode_parent_receipts": {
            "episode_view_builder_source_sha256": "b" * 64,
            "source_cell_target_manifest_sha256": "c" * 64,
        },
        "source_bundle_binding": source_binding,
        "scope": {
            "stage": "outer",
            "repeat": repeat,
            "current_outer_validation_fold": outer,
            "inner_fold": "",
            "episode_outer_fold": outer,
        },
        "episode": {"episode_id": episode, "query_rows": 1},
        "system_id": "G0",
        "source_system_id": "TRACE-G0-MAPL-FIXED",
        "candidate_id": candidate,
        "cell_id": cell_id("outer", repeat, outer, None, "G0", candidate, episode),
        "public_query_receipt_sha256": "d" * 64,
        "runtime": dict(G0_RUNTIME),
        "r3c_parameter_source": g0.bound.R3C_PARAMETER_SOURCE,
        "resolved_catboost_parameters": g0.bound.ACCEPTED_PARAMETERS,
        "counts": {
            "current_training_points": 10,
            "anchor_rows": 1,
            "fit_rows": 11,
            "query_rows": 1,
        },
        "operation_accounting": accounting,
        "prediction_fragment": {
            "sha256": _sha(fragment),
            "bytes": len(fragment),
            "rows": 1,
            "columns": list(columns),
        },
        "authority": dict(DENIED_AUTHORITY),
    }
    manifest_bytes = _pretty(manifest)
    root.mkdir(parents=True)
    (root / "manifest.json").write_bytes(manifest_bytes)
    (root / "prediction_fragment.csv").write_bytes(fragment)
    _readonly(root)
    return root, _sha(manifest_bytes), manifest


def _g0_binding(manifest: dict[str, Any], manifest_sha: str) -> dict[str, Any]:
    material = [
        RESOLVED_CONTRACT_SHA256,
        manifest["model_public_manifest_sha256"],
        manifest["episode_target_manifest_sha256"],
        "outer",
        manifest["scope"]["repeat"],
        manifest["scope"]["current_outer_validation_fold"],
        -1,
        manifest["episode"]["episode_id"],
        manifest["cell_id"],
        manifest["r3c_parameter_source"]["parameter_record_sha256"],
        manifest["g0_source_bundle_sha256"],
    ]
    return {
        "binding_sha256": _sha(
            json.dumps(
                material,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode()
        ),
        "g0_manifest_sha256": manifest_sha,
        "g0_prediction_fragment_sha256": manifest["prediction_fragment"]["sha256"],
        "episode_id": manifest["episode"]["episode_id"],
        "episode_target_manifest_sha256": manifest["episode_target_manifest_sha256"],
        "r3c_parameter_record_sha256": manifest["r3c_parameter_source"][
            "parameter_record_sha256"
        ],
        "g0_source_bundle_sha256": manifest["g0_source_bundle_sha256"],
    }


def _accounting(system: str) -> dict[str, int]:
    result = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    if system not in {"F0", "F1", "C3"}:
        result["anchor_labels_exposed_to_models"] = 2
    if system not in {"F0", "F1"}:
        result["direct_target_values_parsed"] = 10 if system == "C3" else 20
    if system in {"C2", "C3", "T0", "F2", "A2"}:
        result["ridge_model_fits"] = 1
    if system in {"C3", "T0", "F2", "A0", "A1"}:
        result["hierarchy_fits"] = 1
    return result


def _fragment_root(
    root: Path,
    *,
    system: str,
    repeat: int,
    outer: int,
    public_rows: list[dict[str, str]],
    token: dict[str, Any] | None,
    token_sha: str | None,
    g0_receipts: tuple[str, ...],
    g0_bindings: list[dict[str, Any]],
    model_manifest: str,
    source_binding: dict[str, Any],
    t0_fragment_sha: str | None,
) -> tuple[FragmentInput, bytes]:
    if system in {"C2", "C3", "T0", "F2", "A0", "A1", "A2"}:
        assert token is not None
        alpha, lambda_value = token["alpha"], token["lambda"]
    else:
        alpha = lambda_value = None
    reused_token_sha = token_sha if system in {"F0", "F1", "F2"} else None
    upstream = t0_fragment_sha if system in {"F0", "F1"} else None
    candidate = candidate_id(
        system,
        alpha,
        lambda_value,
        selection_token_sha256=reused_token_sha,
        upstream_candidate_receipt_sha256=upstream,
    )
    scoped_cell = cell_id(
        "outer",
        repeat,
        outer,
        None,
        system,
        candidate,
        "all",
        alpha=alpha,
        lambda_=lambda_value,
        selection_token_sha256=reused_token_sha,
        upstream_candidate_receipt_sha256=upstream,
    )
    source_token = {"C0": "C0", "C1": "C1", "F0": "F0", "F1": "F1"}.get(system, "LOCAL")
    rows: list[dict[str, str]] = []
    for index, public in enumerate(public_rows):
        local = index == 0
        rows.append(
            {
                **public,
                "system_id": system,
                "candidate_id": candidate,
                "prediction": "2" if local else "1",
                "local_available": "true" if local else "false",
                "prediction_source": source_token if local else "G0",
            }
        )
    fragment = canonical_csv_bytes(FRAGMENT_COLUMNS, rows)
    accounting = _accounting(system)
    expected_g0: str | list[str] = (
        g0_receipts[0] if len(g0_receipts) == 1 else list(g0_receipts)
    )
    token_binding = (
        None
        if token is None
        else {
            "sha256": token_sha,
            "system_id": token["system_id"],
            "candidate_id": token["candidate_id"],
            "candidate_receipt_sha256": token["candidate_receipt_sha256"],
            "scorer_receipt_sha256": token["scorer_receipt_sha256"],
        }
    )
    manifest = {
        "schema_version": (
            "cypshift.openadmet_cyp_2026.r5c_private_prediction_fragment.v1"
        ),
        "status": "R5_ORACLE_PAIR_CELL_COMPLETE",
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "runner_source_sha256": pair_runner_source_bundle_sha256(),
        "scope": {
            "stage": "outer",
            "repeat": repeat,
            "outer_fold": outer,
            "inner_fold": "",
        },
        "system_id": system,
        "candidate_id": candidate,
        "cell_id": scoped_cell,
        "fragment_id": fragment_id(
            "outer",
            repeat,
            outer,
            None,
            system,
            candidate,
            "all",
            scoped_cell,
            selection_token_sha256=reused_token_sha,
            upstream_candidate_receipt_sha256=upstream,
        ),
        "capability_binding": {
            "model_public_manifest_sha256": model_manifest,
            "target_manifest_sha256": _sha(
                f"target-{system}-{repeat}-{outer}".encode()
            ),
            "target_kind": "c3-target" if system == "C3" else "cell-target",
            "g0_manifest_sha256": expected_g0,
            "system_id": system,
            "source_bundle_binding": source_binding,
            "selection_token": token_binding,
        },
        "g0_bindings": g0_bindings,
        "runtime": dict(freezer_io.EXPECTED_RUNTIME),
        "operation_accounting": accounting,
        "prediction_fragment": {
            "path": "prediction_fragment.csv",
            "sha256": _sha(fragment),
            "bytes": len(fragment),
            "rows": len(rows),
            "columns": list(FRAGMENT_COLUMNS),
        },
        "authority": dict(DENIED_AUTHORITY),
    }
    manifest_bytes = _compact(manifest)
    root.mkdir(parents=True)
    (root / "manifest.json").write_bytes(manifest_bytes)
    (root / "prediction_fragment.csv").write_bytes(fragment)
    _readonly(root)
    return (
        FragmentInput(
            system,
            repeat,
            outer,
            root,
            _sha(manifest_bytes),
            accounting,
        ),
        fragment,
    )


def _eligibility_root(
    root: Path,
    *,
    repeat: int,
    outer: int,
    public_rows: list[dict[str, str]],
    source_binding: dict[str, Any],
) -> EligibilityInput:
    rows = [
        {
            "episode_id": row["episode_id"],
            "query_molecule_id": row["query_molecule_id"],
            "query_rank": row["query_rank"],
            "complete_anchor": "true",
            "valid_true_transformation": "true",
            "true_extraction_status": row["extraction_status"],
        }
        for row in public_rows
    ]
    eligibility = canonical_csv_bytes(ELIGIBILITY_COLUMNS, rows)
    truth = b"truth-not-opened\n"
    cliffs = b"cliffs-not-opened\n"
    scope = {
        "stage": "outer",
        "repeat": repeat,
        "outer_fold": outer,
        "inner_fold": "",
    }
    accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    accounting["query_truth_values_opened_by_scorers"] = len(rows)
    truth_receipt = {
        "sha256": _sha(truth),
        "bytes": len(truth),
        "rows": 0,
        "columns": list(TRUTH_COLUMNS),
    }
    cliff_receipt = {
        "sha256": _sha(cliffs),
        "bytes": len(cliffs),
        "rows": 0,
        "columns": list(CLIFF_COLUMNS),
    }
    manifest = {
        "schema_version": SEALED_SCHEMA_VERSION,
        "status": SEALED_STATUS,
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "parent_contract_sha256": (
            "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
        ),
        "root": "sealed-scorer",
        "current_cell_scope": scope,
        "parent_receipts": {
            "v2_sealed_manifest_sha256": "1" * 64,
            "v2_source_manifest_sha256": source_binding["manifest_receipt"]["sha256"],
        },
        "input_receipts": {
            "v2_sealed_manifest.json": {"sha256": "1" * 64, "bytes": 100},
            "v2_source_manifest.json": {
                "sha256": source_binding["manifest_receipt"]["sha256"],
                "bytes": 100,
            },
            "episode_truth.csv": truth_receipt,
            "activity_cliffs.csv": cliff_receipt,
        },
        "output_receipts": {
            "episode_truth.csv": truth_receipt,
            "activity_cliffs.csv": cliff_receipt,
            "sealed_episode_eligibility.csv": {
                "relative_path": "sealed_episode_eligibility.csv",
                "sha256": _sha(eligibility),
                "bytes": len(eligibility),
                "rows": len(rows),
                "columns": list(ELIGIBILITY_COLUMNS),
                "scope": scope,
            },
        },
        "source_bundle_binding": source_binding,
        "operation_accounting": accounting,
        "authority": dict(DENIED_AUTHORITY),
    }
    manifest_bytes = _compact(manifest)
    root.mkdir(parents=True)
    for name, data in {
        "manifest.json": manifest_bytes,
        "episode_truth.csv": truth,
        "activity_cliffs.csv": cliffs,
        "sealed_episode_eligibility.csv": eligibility,
    }.items():
        (root / name).write_bytes(data)
    _readonly(root)
    return EligibilityInput(repeat, outer, root, _sha(manifest_bytes), accounting)


def _context(root: Path, repeat: int, outer: int) -> OuterContextInput:
    source_binding = _source_binding()
    model_manifest = "e" * 64
    token_inputs: list[TokenInput] = []
    token_objects: dict[str, dict[str, Any]] = {}
    token_sha: dict[str, str] = {}
    for system in TOKEN_SYSTEMS:
        source, token = _token_root(root / f"tokens/{system}", system, repeat, outer)
        token_inputs.append(source)
        token_objects[system] = token
        token_sha[system] = source.expected_sha256
    policies = ("selected_anchor", "deterministic_random_anchor_stress")
    public_rows: list[dict[str, str]] = []
    g0_roots: list[Path] = []
    g0_receipts: list[str] = []
    g0_manifests: list[dict[str, Any]] = []
    for rank, policy in enumerate(policies, start=1):
        episode = _sha(f"episode-{repeat}-{outer}-{rank}".encode())
        query = f"query-{repeat}-{outer}-{rank}"
        public_rows.append(
            {
                "episode_id": episode,
                "query_molecule_id": query,
                "query_rank": str(rank),
                "episode_policy_id": policy,
                "repeat": str(repeat),
                "outer_fold": str(outer),
                "inner_fold": "",
                "component_id": _sha(f"component-{repeat}-{outer}".encode()),
                "extraction_status": "VALID_SINGLE",
                "similarity": "0.80000000000000004",
                "exact_support_components": "5",
                "class_support_components": "6",
            }
        )
        g0_root, receipt, manifest = _g0_root(
            root / f"g0/{rank}",
            repeat=repeat,
            outer=outer,
            episode=episode,
            query=query,
            model_manifest=model_manifest,
            source_binding=source_binding,
        )
        g0_roots.append(g0_root)
        g0_receipts.append(receipt)
        g0_manifests.append(manifest)
    public_rows.sort(key=lambda row: (row["episode_id"], int(row["query_rank"])))
    bindings = [
        _g0_binding(manifest, receipt)
        for manifest, receipt in zip(g0_manifests, g0_receipts, strict=True)
    ]
    fragments: list[FragmentInput] = []
    t0_input, t0_bytes = _fragment_root(
        root / "fragments/T0",
        system="T0",
        repeat=repeat,
        outer=outer,
        public_rows=public_rows,
        token=token_objects["T0"],
        token_sha=token_sha["T0"],
        g0_receipts=tuple(g0_receipts),
        g0_bindings=bindings,
        model_manifest=model_manifest,
        source_binding=source_binding,
        t0_fragment_sha=None,
    )
    fragments.append(t0_input)
    t0_sha = _sha(t0_bytes)
    for system in PAIR_SYSTEMS:
        if system == "T0":
            continue
        token_system = "T0" if system in {"F0", "F1", "F2"} else system
        token = token_objects.get(token_system)
        source, _fragment = _fragment_root(
            root / f"fragments/{system}",
            system=system,
            repeat=repeat,
            outer=outer,
            public_rows=public_rows,
            token=token,
            token_sha=token_sha.get(token_system),
            g0_receipts=tuple(g0_receipts),
            g0_bindings=bindings,
            model_manifest=model_manifest,
            source_binding=source_binding,
            t0_fragment_sha=t0_sha,
        )
        fragments.append(source)
    return OuterContextInput(
        repeat,
        outer,
        tuple(token_inputs),
        tuple(fragments),
        G0Input(repeat, outer, tuple(g0_roots), tuple(g0_receipts)),
        _eligibility_root(
            root / "eligibility",
            repeat=repeat,
            outer=outer,
            public_rows=public_rows,
            source_binding=source_binding,
        ),
    )


@pytest.fixture
def contexts(tmp_path: Path) -> tuple[OuterContextInput, ...]:
    return tuple(
        _context(tmp_path / f"inputs/{repeat}-{outer}", repeat, outer)
        for repeat in range(3)
        for outer in range(5)
    )


def _freeze(contexts: tuple[OuterContextInput, ...], output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    return freeze_outer_predictions(
        contexts,
        output,
        expected_freezer_source_sha256=freezer_source_bundle_sha256(),
        expected_pair_runner_source_sha256=pair_runner_source_bundle_sha256(),
        expected_g0_source_sha256=g0_source_bundle_sha256(),
    )


def _tree(root: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in root.iterdir()}


def _rewrite_fragment(source: FragmentInput, poison: str) -> FragmentInput:
    root = source.root
    root.chmod(0o755)
    fragment_path = root / "prediction_fragment.csv"
    manifest_path = root / "manifest.json"
    fragment_path.chmod(0o644)
    manifest_path.chmod(0o644)
    with fragment_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    manifest = json.loads(manifest_path.read_bytes())
    if poison == "nonfinite":
        rows[0]["prediction"] = "nan"
    elif poison == "missing":
        rows.pop()
    elif poison == "duplicate":
        rows.append(dict(rows[-1]))
    elif poison == "extra":
        extra = dict(rows[-1])
        extra.update(
            episode_id="f" * 64,
            query_molecule_id="extra-query",
            query_rank="3",
        )
        rows.append(extra)
    elif poison == "metadata":
        rows[0]["component_id"] = "f" * 64
    elif poison == "fallback":
        fallback = next(row for row in rows if row["local_available"] == "false")
        fallback["prediction"] = "2"
    elif poison == "source":
        rows[0]["prediction_source"] = "C0"
    elif poison == "source-binding":
        manifest["capability_binding"]["source_bundle_binding"]["manifest_receipt"][
            "sha256"
        ] = "b" * 64
    else:  # pragma: no cover - test helper guard
        raise AssertionError(poison)
    fragment = canonical_csv_bytes(FRAGMENT_COLUMNS, rows)
    manifest["prediction_fragment"] = {
        "path": "prediction_fragment.csv",
        "sha256": _sha(fragment),
        "bytes": len(fragment),
        "rows": len(rows),
        "columns": list(FRAGMENT_COLUMNS),
    }
    manifest_bytes = _compact(manifest)
    fragment_path.write_bytes(fragment)
    manifest_path.write_bytes(manifest_bytes)
    _readonly(root)
    return replace(source, expected_manifest_sha256=_sha(manifest_bytes))


def _rewrite_eligibility(source: EligibilityInput, poison: str) -> EligibilityInput:
    root = source.root
    root.chmod(0o755)
    eligibility_path = root / "sealed_episode_eligibility.csv"
    manifest_path = root / "manifest.json"
    eligibility_path.chmod(0o644)
    manifest_path.chmod(0o644)
    with eligibility_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    manifest = json.loads(manifest_path.read_bytes())
    if poison == "missing":
        rows.pop()
    elif poison == "duplicate":
        rows.append(dict(rows[-1]))
    elif poison == "geometry":
        rows[0]["true_extraction_status"] = "INVALID_DISCONNECTED"
        rows[0]["valid_true_transformation"] = "false"
    elif poison == "accounting":
        manifest["operation_accounting"]["query_truth_values_opened_by_scorers"] += 1
    else:  # pragma: no cover - test helper guard
        raise AssertionError(poison)
    eligibility = canonical_csv_bytes(ELIGIBILITY_COLUMNS, rows)
    manifest["output_receipts"]["sealed_episode_eligibility.csv"].update(
        sha256=_sha(eligibility),
        bytes=len(eligibility),
        rows=len(rows),
    )
    manifest_bytes = _compact(manifest)
    eligibility_path.write_bytes(eligibility)
    manifest_path.write_bytes(manifest_bytes)
    _readonly(root)
    return replace(source, expected_manifest_sha256=_sha(manifest_bytes))


def test_outer_freezer_is_deterministic_complete_and_eligibility_only(
    contexts: tuple[OuterContextInput, ...],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []
    original = freezer_io.read_regular_at

    def tracked(fd: int, name: str) -> bytes:
        opened.append(name)
        return original(fd, name)

    monkeypatch.setattr(freezer_io, "read_regular_at", tracked)
    first = _freeze(contexts, tmp_path / "freeze-1")
    second = _freeze(tuple(reversed(contexts)), tmp_path / "freeze-2")
    assert first.prediction_rows == second.prediction_rows == 360
    assert first.eligibility_rows == second.eligibility_rows == 30
    assert _tree(first.output_root) == _tree(second.output_root)
    assert set(_tree(first.output_root)) == {
        "manifest.json",
        "merged_eligibility.csv",
        *(f"{system}.csv" for system in SYSTEMS),
    }
    assert set(opened) == {"manifest.json", "sealed_episode_eligibility.csv"}
    assert "episode_truth.csv" not in opened and "activity_cliffs.csv" not in opened
    manifest = json.loads((first.output_root / "manifest.json").read_bytes())
    assert manifest["status"] == FREEZE_STATUS
    assert manifest["counts"] == {
        "contexts": 15,
        "systems": 12,
        "selection_tokens": 90,
        "pair_fragments": 165,
        "g0_fragments": 30,
        "prediction_rows": 360,
        "eligibility_rows": 30,
    }
    expected_accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    expected_accounting["predictions_frozen"] = 360
    assert manifest["operation_accounting"] == expected_accounting
    frozen_rows: dict[str, list[dict[str, str]]] = {}
    for system in SYSTEMS:
        with (first.output_root / f"{system}.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert len(rows) == 30
        assert {row["episode_policy_id"] for row in rows} == {
            "selected_anchor",
            "deterministic_random_anchor_stress",
        }
        frozen_rows[system] = rows
    metadata_fields = tuple(
        field
        for field in FRAGMENT_COLUMNS
        if field
        not in {
            "system_id",
            "candidate_id",
            "prediction",
            "local_available",
            "prediction_source",
        }
    )
    expected_metadata = [
        tuple(row[field] for field in metadata_fields) for row in frozen_rows["G0"]
    ]
    assert all(
        [tuple(row[field] for field in metadata_fields) for row in frozen_rows[system]]
        == expected_metadata
        for system in SYSTEMS
    )
    assert first.output_root.stat().st_mode & 0o777 == 0o555
    assert all(
        path.stat().st_mode & 0o777 == 0o444 for path in first.output_root.iterdir()
    )


def test_outer_freezer_rejects_scope_receipt_token_and_accounting_poison(
    contexts: tuple[OuterContextInput, ...], tmp_path: Path
) -> None:
    with pytest.raises(OracleOuterFreezerError, match="context cardinality"):
        _freeze(contexts[:-1], tmp_path / "short")
    first = contexts[0]
    bad_token = replace(first.tokens[0], expected_sha256="0" * 64)
    with pytest.raises(OracleOuterFreezerError, match="token receipt"):
        _freeze(
            (replace(first, tokens=(bad_token, *first.tokens[1:])), *contexts[1:]),
            tmp_path / "bad-token",
        )
    bad_fragment = replace(
        first.fragments[0],
        expected_operation_accounting={
            **first.fragments[0].expected_operation_accounting,
            "direct_target_values_parsed": (
                first.fragments[0].expected_operation_accounting[
                    "direct_target_values_parsed"
                ]
                + 1
            ),
        },
    )
    with pytest.raises(OracleOuterFreezerError, match="accounting"):
        _freeze(
            (
                replace(first, fragments=(bad_fragment, *first.fragments[1:])),
                *contexts[1:],
            ),
            tmp_path / "bad-accounting",
        )
    bad_g0 = replace(
        first.g0,
        expected_manifest_sha256=("0" * 64, *first.g0.expected_manifest_sha256[1:]),
    )
    with pytest.raises(OracleOuterFreezerError, match="G0|capability binding"):
        _freeze((replace(first, g0=bad_g0), *contexts[1:]), tmp_path / "bad-g0")
    bad_eligibility = replace(first.eligibility, expected_manifest_sha256="0" * 64)
    with pytest.raises(OracleOuterFreezerError, match="eligibility manifest receipt"):
        _freeze(
            (replace(first, eligibility=bad_eligibility), *contexts[1:]),
            tmp_path / "bad-eligibility",
        )


@pytest.mark.parametrize(
    ("poison", "message"),
    (
        ("nonfinite", "finite"),
        ("missing", "fixed superset"),
        ("duplicate", "duplicated|row binding"),
        ("extra", "public metadata"),
        ("metadata", "public metadata"),
        ("fallback", "fallback prediction"),
        ("source", "prediction source"),
        ("source-binding", "source population|G0 binding"),
    ),
)
def test_outer_freezer_rejects_authenticated_fragment_semantic_poison(
    contexts: tuple[OuterContextInput, ...],
    tmp_path: Path,
    poison: str,
    message: str,
) -> None:
    first = contexts[0]
    index = next(
        index
        for index, source in enumerate(first.fragments)
        if source.system_id == "C2"
    )
    fragments = list(first.fragments)
    fragments[index] = _rewrite_fragment(fragments[index], poison)
    with pytest.raises(OracleOuterFreezerError, match=message):
        _freeze(
            (replace(first, fragments=tuple(fragments)), *contexts[1:]),
            tmp_path / f"fragment-{poison}",
        )


@pytest.mark.parametrize(
    ("poison", "message"),
    (
        ("missing", "population"),
        ("duplicate", "duplicated|row order|row differs"),
        ("geometry", "geometry"),
        ("accounting", "accounting"),
    ),
)
def test_outer_freezer_rejects_authenticated_eligibility_poison(
    contexts: tuple[OuterContextInput, ...],
    tmp_path: Path,
    poison: str,
    message: str,
) -> None:
    first = contexts[0]
    eligibility = _rewrite_eligibility(first.eligibility, poison)
    with pytest.raises(OracleOuterFreezerError, match=message):
        _freeze(
            (replace(first, eligibility=eligibility), *contexts[1:]),
            tmp_path / f"eligibility-{poison}",
        )


def test_outer_freezer_rejects_symlink_source_drift_and_no_replace(
    contexts: tuple[OuterContextInput, ...],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = contexts[0]
    real_parent = first.fragments[0].root.parent
    link = tmp_path / "fragment-link"
    link.symlink_to(real_parent, target_is_directory=True)
    linked = replace(first.fragments[0], root=link / first.fragments[0].root.name)
    with pytest.raises(OracleOuterFreezerError, match="ancestry"):
        _freeze(
            (replace(first, fragments=(linked, *first.fragments[1:])), *contexts[1:]),
            tmp_path / "linked-output",
        )
    real_output_parent = tmp_path / "real-output-parent"
    real_output_parent.mkdir()
    output_parent_link = tmp_path / "output-parent-link"
    output_parent_link.symlink_to(real_output_parent, target_is_directory=True)
    with pytest.raises(OracleOuterFreezerError, match="ancestry"):
        _freeze(contexts, output_parent_link / "freeze")
    expected_source = freezer_source_bundle_sha256()
    stable_read = freezer_io.read_stable_file
    witness = freezer_io.ROOT / FREEZER_SOURCE_FILES[0]
    with monkeypatch.context() as source_patch:
        source_patch.setattr(
            freezer_io,
            "read_stable_file",
            lambda path: (
                stable_read(path) + b"mutation"
                if path == witness
                else stable_read(path)
            ),
        )
        with pytest.raises(OracleOuterFreezerError, match="freezer source bundle"):
            freeze_outer_predictions(
                (),
                tmp_path / "never-opened",
                expected_freezer_source_sha256=expected_source,
                expected_pair_runner_source_sha256=pair_runner_source_bundle_sha256(),
                expected_g0_source_sha256=g0_source_bundle_sha256(),
            )
    output = tmp_path / "one-terminal"
    _freeze(contexts, output)
    with pytest.raises(OracleOuterFreezerError, match="already exists"):
        _freeze(contexts, output)


def test_closed_publisher_rejects_arbitrary_forged_and_incomplete_packages(
    contexts: tuple[OuterContextInput, ...], tmp_path: Path
) -> None:
    assert "publish_freeze" not in freezer_io.__all__
    assert not hasattr(freezer_io, "publish_freeze")
    arbitrary = tmp_path / "arbitrary"
    with pytest.raises(freezer_io.OracleOuterFreezerIOError, match="file set"):
        freezer_publish._publish_validated_freeze(
            arbitrary, {"evil.txt": b"immutable but unauthorized\n"}
        )
    assert not arbitrary.exists()

    valid_root = tmp_path / "valid-package"
    _freeze(contexts, valid_root)
    valid = _tree(valid_root)
    attacks: list[tuple[str, dict[str, bytes], str]] = []
    forged = dict(valid)
    forged_manifest = json.loads(forged["manifest.json"])
    forged_manifest["status"] = "FORGED"
    forged["manifest.json"] = _compact(forged_manifest)
    attacks.append(("forged", forged, "manifest binding"))
    extra = {**valid, "evil.txt": b"extra\n"}
    attacks.append(("extra", extra, "file set"))
    missing = dict(valid)
    missing.pop("A2.csv")
    attacks.append(("missing", missing, "file set"))
    for name, payloads, message in attacks:
        destination = tmp_path / name
        with pytest.raises(freezer_io.OracleOuterFreezerIOError, match=message):
            freezer_publish._publish_validated_freeze(destination, payloads)
        assert not destination.exists()

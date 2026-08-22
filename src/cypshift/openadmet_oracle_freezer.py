"""Authenticated final outer prediction freeze for the R5C oracle experiment."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

from cypshift.openadmet_oracle_freezer_io import (
    FREEZE_SCHEMA,
    FREEZE_STATUS,
    PAIR_SYSTEMS,
    SYSTEMS,
    TOKEN_SYSTEMS,
    EligibilityInput,
    FragmentInput,
    G0Input,
    LoadedFragment,
    LoadedG0,
    OracleOuterFreezerIOError,
    TokenInput,
    load_eligibility,
    load_fragment,
    load_g0_roots,
    load_token,
    validate_execution,
    validate_freeze_output,
)
from cypshift.openadmet_oracle_freezer_publish import _publish_validated_freeze
from cypshift.openadmet_oracle_pair_cell import FRAGMENT_COLUMNS, candidate_id
from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS, SelectionToken
from cypshift.openadmet_oracle_projection import DENIED_AUTHORITY
from cypshift.openadmet_oracle_sealed import (
    ELIGIBILITY_COLUMNS,
    RESOLVED_CONTRACT_SHA256,
)
from cypshift.openadmet_transformation_io import canonical_csv_bytes

PUBLIC_METADATA_FIELDS: Final = (
    "episode_id",
    "query_molecule_id",
    "query_rank",
    "episode_policy_id",
    "repeat",
    "outer_fold",
    "inner_fold",
    "component_id",
    "extraction_status",
    "similarity",
    "exact_support_components",
    "class_support_components",
)


class OracleOuterFreezerError(ValueError):
    """The final outer prediction freeze is incomplete or unauthenticated."""


@dataclass(frozen=True, slots=True)
class OuterContextInput:
    """All immutable inputs for one repeat/outer-fold prediction context."""

    repeat: int
    outer_fold: int
    tokens: tuple[TokenInput, ...]
    fragments: tuple[FragmentInput, ...]
    g0: G0Input
    eligibility: EligibilityInput


@dataclass(frozen=True, slots=True)
class OuterFreezeResult:
    output_root: Path
    manifest_sha256: str
    prediction_rows: int
    eligibility_rows: int


def freeze_outer_predictions(
    contexts: Sequence[OuterContextInput],
    output_root: Path,
    *,
    expected_freezer_source_sha256: str,
    expected_pair_runner_source_sha256: str,
    expected_g0_source_sha256: str,
) -> OuterFreezeResult:
    """Authenticate 15 contexts and atomically freeze the exact outer superset."""

    try:
        freezer_source, pair_source, g0_source, runtime = validate_execution(
            expected_freezer_source_sha256=expected_freezer_source_sha256,
            expected_pair_runner_source_sha256=expected_pair_runner_source_sha256,
            expected_g0_source_sha256=expected_g0_source_sha256,
        )
        validate_freeze_output(output_root)
        context_index = _context_index(contexts)
        system_rows: dict[str, list[Mapping[str, str]]] = {
            system: [] for system in SYSTEMS
        }
        merged_eligibility: list[Mapping[str, str]] = []
        token_receipts: dict[str, str] = {}
        pair_receipts: dict[str, str] = {}
        g0_receipts: dict[str, str] = {}
        eligibility_receipts: dict[str, str] = {}
        source_binding: Mapping[str, Any] | None = None
        model_public_receipt: str | None = None
        all_freeze_keys: set[tuple[str, str, str, str, str]] = set()
        all_eligibility_keys: set[tuple[str, str, str]] = set()
        for repeat in range(3):
            for outer in range(5):
                context = context_index[(repeat, outer)]
                tokens = _load_tokens(context)
                fragments = _load_fragments(
                    context,
                    tokens,
                    pair_source=pair_source,
                )
                base_rows = fragments["T0"].rows
                _validate_identical_superset(fragments, base_rows)
                current_binding = cast(
                    Mapping[str, Any],
                    fragments["T0"].manifest["capability_binding"],
                )["source_bundle_binding"]
                current_model = cast(
                    Mapping[str, Any],
                    fragments["T0"].manifest["capability_binding"],
                )["model_public_manifest_sha256"]
                if source_binding is None:
                    source_binding = cast(Mapping[str, Any], current_binding)
                    model_public_receipt = cast(str, current_model)
                elif (
                    source_binding != current_binding
                    or model_public_receipt != current_model
                ):
                    raise OracleOuterFreezerError("outer source population differs")
                g0_loaded = load_g0_roots(
                    context.g0,
                    expected_g0_source_sha256=g0_source,
                    public_rows=base_rows,
                )
                _validate_g0_bindings(fragments, g0_loaded)
                g0_rows = _normalize_g0_rows(base_rows, g0_loaded)
                _validate_fallback_equality(fragments, g0_rows)
                eligibility = load_eligibility(context.eligibility)
                if eligibility.manifest["source_bundle_binding"] != current_binding:
                    raise OracleOuterFreezerError(
                        "eligibility source population differs"
                    )
                _validate_eligibility_join(base_rows, eligibility.rows)
                for system in PAIR_SYSTEMS:
                    rows = fragments[system].rows
                    _add_freeze_keys(all_freeze_keys, rows)
                    system_rows[system].extend(rows)
                _add_freeze_keys(all_freeze_keys, g0_rows)
                system_rows["G0"].extend(g0_rows)
                for row in eligibility.rows:
                    key = row["episode_id"], row["query_molecule_id"], row["query_rank"]
                    if key in all_eligibility_keys:
                        raise OracleOuterFreezerError(
                            "merged eligibility is duplicated"
                        )
                    all_eligibility_keys.add(key)
                    merged_eligibility.append(row)
                label = _scope_label(repeat, outer)
                for system, token in tokens.items():
                    token_receipts[f"{label}/{system}"] = token.sha256
                for system, loaded in fragments.items():
                    pair_receipts[f"{label}/{system}"] = (
                        loaded.source.expected_manifest_sha256
                    )
                for index, loaded_g0 in enumerate(g0_loaded):
                    g0_receipts[f"{label}/{index:04d}"] = loaded_g0.manifest_sha256
                eligibility_receipts[label] = (
                    context.eligibility.expected_manifest_sha256
                )
        _validate_complete_outputs(system_rows, merged_eligibility)
        payloads = {
            f"{system}.csv": canonical_csv_bytes(FRAGMENT_COLUMNS, system_rows[system])
            for system in SYSTEMS
        }
        payloads["merged_eligibility.csv"] = canonical_csv_bytes(
            ELIGIBILITY_COLUMNS, merged_eligibility
        )
        output_receipts = {
            name: _receipt(
                name,
                data,
                ELIGIBILITY_COLUMNS
                if name == "merged_eligibility.csv"
                else FRAGMENT_COLUMNS,
            )
            for name, data in payloads.items()
        }
        accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
        accounting["predictions_frozen"] = len(all_freeze_keys)
        manifest = {
            "schema_version": FREEZE_SCHEMA,
            "status": FREEZE_STATUS,
            "contract_sha256": RESOLVED_CONTRACT_SHA256,
            "scope": {
                "stage": "outer",
                "repeats": 3,
                "outer_folds": 5,
                "contexts": 15,
            },
            "parent_receipts": {
                "model_public_manifest_sha256": model_public_receipt,
                "source_bundle_binding": source_binding,
            },
            "input_receipts": {
                "selection_tokens": dict(sorted(token_receipts.items())),
                "pair_fragments": dict(sorted(pair_receipts.items())),
                "g0_fragments": dict(sorted(g0_receipts.items())),
                "eligibility_manifests": dict(sorted(eligibility_receipts.items())),
            },
            "source_receipts": {
                "freezer_source_sha256": freezer_source,
                "pair_runner_source_sha256": pair_source,
                "g0_source_bundle_sha256": g0_source,
            },
            "runtime": dict(runtime),
            "counts": {
                "contexts": 15,
                "systems": 12,
                "selection_tokens": len(token_receipts),
                "pair_fragments": len(pair_receipts),
                "g0_fragments": len(g0_receipts),
                "prediction_rows": len(all_freeze_keys),
                "eligibility_rows": len(merged_eligibility),
            },
            "output_receipts": dict(sorted(output_receipts.items())),
            "operation_accounting": accounting,
            "authority": dict(DENIED_AUTHORITY),
        }
        manifest_bytes = _compact_json(manifest)
        payloads["manifest.json"] = manifest_bytes
        _publish_validated_freeze(output_root, payloads)
        return OuterFreezeResult(
            output_root,
            sha256(manifest_bytes).hexdigest(),
            len(all_freeze_keys),
            len(merged_eligibility),
        )
    except OracleOuterFreezerIOError as exc:
        raise OracleOuterFreezerError(str(exc)) from exc


def _context_index(
    contexts: Sequence[OuterContextInput],
) -> dict[tuple[int, int], OuterContextInput]:
    if len(contexts) != 15:
        raise OracleOuterFreezerError("outer context cardinality differs")
    result: dict[tuple[int, int], OuterContextInput] = {}
    for context in contexts:
        key = context.repeat, context.outer_fold
        if (
            context.repeat not in range(3)
            or context.outer_fold not in range(5)
            or key in result
            or (context.g0.repeat, context.g0.outer_fold) != key
            or (context.eligibility.repeat, context.eligibility.outer_fold) != key
        ):
            raise OracleOuterFreezerError("outer context scope differs")
        result[key] = context
    if set(result) != {(repeat, outer) for repeat in range(3) for outer in range(5)}:
        raise OracleOuterFreezerError("outer context grid differs")
    return result


def _load_tokens(context: OuterContextInput) -> dict[str, SelectionToken]:
    if len(context.tokens) != len(TOKEN_SYSTEMS):
        raise OracleOuterFreezerError("outer token cardinality differs")
    result: dict[str, SelectionToken] = {}
    for source in context.tokens:
        if (
            source.system_id not in TOKEN_SYSTEMS
            or source.system_id in result
            or (source.repeat, source.outer_fold)
            != (context.repeat, context.outer_fold)
        ):
            raise OracleOuterFreezerError("outer token scope differs")
        result[source.system_id] = load_token(source)
    if set(result) != set(TOKEN_SYSTEMS):
        raise OracleOuterFreezerError("outer token systems differ")
    return result


def _load_fragments(
    context: OuterContextInput,
    tokens: Mapping[str, SelectionToken],
    *,
    pair_source: str,
) -> dict[str, LoadedFragment]:
    if len(context.fragments) != len(PAIR_SYSTEMS):
        raise OracleOuterFreezerError("outer fragment cardinality differs")
    sources: dict[str, FragmentInput] = {}
    for source in context.fragments:
        if (
            source.system_id not in PAIR_SYSTEMS
            or source.system_id in sources
            or (source.repeat, source.outer_fold)
            != (context.repeat, context.outer_fold)
        ):
            raise OracleOuterFreezerError("outer fragment scope differs")
        sources[source.system_id] = source
    if set(sources) != set(PAIR_SYSTEMS):
        raise OracleOuterFreezerError("outer fragment systems differ")
    receipts = context.g0.expected_manifest_sha256
    loaded: dict[str, LoadedFragment] = {}
    loaded["T0"] = load_fragment(
        sources["T0"],
        token=tokens["T0"],
        expected_pair_source_sha256=pair_source,
        expected_g0_manifest_sha256=receipts,
    )
    t0_fragment_sha = sha256(loaded["T0"].fragment).hexdigest()
    for system in PAIR_SYSTEMS:
        if system == "T0":
            continue
        token = tokens["T0"] if system in {"F0", "F1", "F2"} else tokens.get(system)
        loaded[system] = load_fragment(
            sources[system],
            token=token,
            expected_pair_source_sha256=pair_source,
            expected_g0_manifest_sha256=receipts,
            t0_fragment_sha256=(t0_fragment_sha if system in {"F0", "F1"} else None),
        )
    return loaded


def _validate_identical_superset(
    fragments: Mapping[str, LoadedFragment],
    base_rows: Sequence[Mapping[str, str]],
) -> None:
    base = [tuple(row[field] for field in PUBLIC_METADATA_FIELDS) for row in base_rows]
    if not base:
        raise OracleOuterFreezerError("outer fixed superset is empty")
    for system in PAIR_SYSTEMS:
        observed = [
            tuple(row[field] for field in PUBLIC_METADATA_FIELDS)
            for row in fragments[system].rows
        ]
        if observed != base:
            raise OracleOuterFreezerError("outer public metadata differs")


def _normalize_g0_rows(
    public_rows: Sequence[Mapping[str, str]], loaded: Sequence[LoadedG0]
) -> tuple[Mapping[str, str], ...]:
    values: dict[tuple[str, str], str] = {}
    for item in loaded:
        episode = cast(Mapping[str, Any], item.manifest["episode"])["episode_id"]
        for row in item.rows:
            key = cast(str, episode), row["molecule_id"]
            if key in values:
                raise OracleOuterFreezerError("G0 prediction is duplicated")
            values[key] = row["prediction"]
    candidate = candidate_id("G0", None, None)
    rows: list[Mapping[str, str]] = []
    for public in public_rows:
        value = values.get((public["episode_id"], public["query_molecule_id"]))
        if value is None:
            raise OracleOuterFreezerError("G0 prediction population differs")
        row = dict(public)
        row.update(
            {
                "system_id": "G0",
                "candidate_id": candidate,
                "prediction": value,
                "local_available": "false",
                "prediction_source": "G0",
            }
        )
        rows.append(row)
    return tuple(rows)


def _validate_fallback_equality(
    fragments: Mapping[str, LoadedFragment],
    g0_rows: Sequence[Mapping[str, str]],
) -> None:
    g0 = {
        (row["episode_id"], row["query_molecule_id"], row["query_rank"]): row[
            "prediction"
        ]
        for row in g0_rows
    }
    for fragment in fragments.values():
        for row in fragment.rows:
            if row["prediction_source"] == "G0":
                key = row["episode_id"], row["query_molecule_id"], row["query_rank"]
                if row["prediction"] != g0[key]:
                    raise OracleOuterFreezerError("outer fallback prediction differs")


def _validate_eligibility_join(
    public_rows: Sequence[Mapping[str, str]],
    eligibility_rows: Sequence[Mapping[str, str]],
) -> None:
    public = {
        (row["episode_id"], row["query_molecule_id"], row["query_rank"]): row
        for row in public_rows
    }
    eligibility = {
        (row["episode_id"], row["query_molecule_id"], row["query_rank"]): row
        for row in eligibility_rows
    }
    if len(public) != len(public_rows) or len(eligibility) != len(eligibility_rows):
        raise OracleOuterFreezerError("eligibility join is duplicated")
    if set(public) != set(eligibility):
        raise OracleOuterFreezerError("eligibility population differs")
    if any(
        public[key]["extraction_status"] != eligibility[key]["true_extraction_status"]
        for key in public
    ):
        raise OracleOuterFreezerError("eligibility geometry differs")


def _validate_g0_bindings(
    fragments: Mapping[str, LoadedFragment], g0: Sequence[LoadedG0]
) -> None:
    model_manifest = cast(
        Mapping[str, Any], fragments["T0"].manifest["capability_binding"]
    )["model_public_manifest_sha256"]
    expected = [_g0_binding(item, cast(str, model_manifest)) for item in g0]
    source_binding = cast(
        Mapping[str, Any], fragments["T0"].manifest["capability_binding"]
    )["source_bundle_binding"]
    if any(
        item.manifest["model_public_manifest_sha256"] != model_manifest
        or item.manifest["source_bundle_binding"] != source_binding
        for item in g0
    ):
        raise OracleOuterFreezerError("G0 source population differs")
    for fragment in fragments.values():
        capability = cast(Mapping[str, Any], fragment.manifest["capability_binding"])
        if (
            capability["model_public_manifest_sha256"] != model_manifest
            or capability["source_bundle_binding"] != source_binding
            or fragment.manifest["g0_bindings"] != expected
        ):
            raise OracleOuterFreezerError("outer G0 binding differs")


def _g0_binding(item: LoadedG0, model_manifest: str) -> dict[str, Any]:
    manifest = item.manifest
    episode = cast(Mapping[str, Any], manifest["episode"])["episode_id"]
    scope = cast(Mapping[str, Any], manifest["scope"])
    parameter = cast(Mapping[str, Any], manifest["r3c_parameter_source"])
    material = [
        RESOLVED_CONTRACT_SHA256,
        model_manifest,
        manifest["episode_target_manifest_sha256"],
        "outer",
        scope["repeat"],
        scope["current_outer_validation_fold"],
        -1,
        episode,
        manifest["cell_id"],
        parameter["parameter_record_sha256"],
        manifest["g0_source_bundle_sha256"],
    ]
    binding_sha = sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return {
        "binding_sha256": binding_sha,
        "g0_manifest_sha256": item.manifest_sha256,
        "g0_prediction_fragment_sha256": item.fragment_sha256,
        "episode_id": episode,
        "episode_target_manifest_sha256": manifest["episode_target_manifest_sha256"],
        "r3c_parameter_record_sha256": parameter["parameter_record_sha256"],
        "g0_source_bundle_sha256": manifest["g0_source_bundle_sha256"],
    }


def _add_freeze_keys(
    keys: set[tuple[str, str, str, str, str]],
    rows: Sequence[Mapping[str, str]],
) -> None:
    for row in rows:
        key = (
            row["episode_id"],
            row["query_molecule_id"],
            row["query_rank"],
            row["system_id"],
            row["candidate_id"],
        )
        if key in keys:
            raise OracleOuterFreezerError("frozen prediction key is duplicated")
        keys.add(key)


def _validate_complete_outputs(
    system_rows: Mapping[str, Sequence[Mapping[str, str]]],
    eligibility: Sequence[Mapping[str, str]],
) -> None:
    counts = {system: len(rows) for system, rows in system_rows.items()}
    if set(counts) != set(SYSTEMS) or len(set(counts.values())) != 1:
        raise OracleOuterFreezerError("frozen system row counts differ")
    expected = len(eligibility)
    if not expected or next(iter(counts.values())) != expected:
        raise OracleOuterFreezerError("frozen eligibility row count differs")
    for system, rows in system_rows.items():
        observed = [
            (
                int(row["repeat"]),
                int(row["outer_fold"]),
                row["episode_id"],
                int(row["query_rank"]),
            )
            for row in rows
        ]
        if observed != sorted(observed) or any(
            row["system_id"] != system for row in rows
        ):
            raise OracleOuterFreezerError("frozen system order differs")


def _scope_label(repeat: int, outer: int) -> str:
    return f"repeat-{repeat}/outer-{outer}"


def _receipt(name: str, data: bytes, columns: Sequence[str]) -> dict[str, Any]:
    return {
        "relative_path": name,
        "sha256": sha256(data).hexdigest(),
        "bytes": len(data),
        "rows": data.count(b"\n") - 1,
        "columns": list(columns),
    }


def _compact_json(value: Mapping[str, Any]) -> bytes:
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


__all__ = [
    "OuterContextInput",
    "OuterFreezeResult",
    "OracleOuterFreezerError",
    "freeze_outer_predictions",
]

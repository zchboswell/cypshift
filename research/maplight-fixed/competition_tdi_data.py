"""Published TDI classes for the existing development population, reserve-safe intake."""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import io
import json
import os
import platform
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
from competition_data import _prefix, balanced_nested_folds, load_development
from competition_tdi_metrics import ENDPOINTS

SOURCE_SHA256 = "b458f599a792412292664386e8f18adc5d4a4129d6bd212ae80a60fb9b96bb60"
MAPPING_SHA256 = "e5d6051e7a060a7194e361222814f988dc5d693fe1a6fbbe40a8b969df79dbc8"
DEVELOPMENT_SHA256 = "8fc2a8efbccf8aa185d6959eccd4190181e6eadad675e4e4a3e0a97bd34379bf"
SEEDS = (20260905, 20260906)
RUNTIME = {
    "python": "3.10.13",
    "numpy": "1.25.2",
    "scikit-learn": "1.3.0",
    "scipy": "1.11.2",
    "rdkit": "2023.3.3",
    "catboost": "1.2.1",
}
CLASS_VALUES = {
    "0": 0,
    "0.0": 0,
    "False": 0,
    "false": 0,
    "1": 1,
    "1.0": 1,
    "True": 1,
    "true": 1,
}


@dataclass(frozen=True)
class TDIDevelopment:
    names: tuple[str, ...]
    molecule_ids: tuple[str, ...]
    raw_smiles: tuple[str, ...]
    groups: tuple[str, ...]
    labels: np.ndarray
    mask: np.ndarray
    raw_classes: np.ndarray
    original_direct_training_mask: np.ndarray
    receipts: dict[str, str]
    support: dict[str, Any]


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def _decode_classes(
    raw: bytes, mapping: list[dict[str, str]], development: Any
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Validate ALL identity prefixes before decoding ANY eligible class token."""
    lines = raw.splitlines()
    if _prefix(lines[0], 4) != ["Molecule_Name", "SMILES", *ENDPOINTS]:
        raise ValueError("TDI physical prefix/order differs")
    contexts = {row["Molecule_Name"]: row for row in mapping}
    if len(contexts) != len(mapping) or len(lines) != len(mapping) + 1:
        raise ValueError("TDI mapping/source row count or duplicate differs")
    originals = {row.name: row for row in development.all_rows}
    allowed = {name: i for i, name in enumerate(development.names)}
    if len(allowed) != len(development.names):
        raise ValueError("Duplicate development names")
    seen = set()
    for line in lines[1:]:
        name, smiles = _prefix(line, 2)
        if name not in contexts or name in seen:
            raise ValueError(
                "TDI full source membership/duplicate differs before class decoding"
            )
        seen.add(name)
        context = contexts[name]
        if context["population"] == "original":
            if name not in originals:
                raise ValueError(
                    "TDI original identity absent from authenticated mapping"
                )
            row = originals[name]
            if (
                smiles != row.raw_smiles
                or context["original_group"] != row.group
                or context["original_reserved"] != str(row.reserved).lower()
                or context["original_quarantined"] != str(row.quarantined).lower()
            ):
                raise ValueError("TDI original context differs before class decoding")
        elif context["population"] != "extra" or name in originals:
            raise ValueError("TDI original/extra membership differs")
        if name in allowed:
            index = allowed[name]
            if (
                context["population"] != "original"
                or context["expanded_reserved_connected"] != "false"
                or context["original_reserved"] != "false"
                or context["original_quarantined"] != "false"
                or smiles != development.raw_smiles[index]
                or context["original_group"] != development.groups[index]
            ):
                raise ValueError("TDI allowed development identity/family differs")
    if (
        seen != set(contexts)
        or not set(allowed) <= seen
        or set(originals)
        != {n for n in contexts if contexts[n]["population"] == "original"}
    ):
        raise ValueError("TDI complete source membership differs")
    # Preserve original folds from direct availability; no class-informed fold choice.
    for seed in SEEDS:
        outer, inner = balanced_nested_folds(
            development.groups, development.training_mask, seed
        )
        for name, index in allowed.items():
            context = contexts[name]
            if int(context[f"original_outer_fold_{seed}"]) != outer[index] or any(
                int(context[f"original_inner_fold_{seed}_outer_{fold}"])
                != inner[fold, index]
                for fold in range(5)
            ):
                raise ValueError(
                    "TDI mapping original folds differ before class decoding"
                )
    tokens = [["", ""] for _ in allowed]
    labels = np.zeros((len(allowed), 2), dtype=np.float64)
    mask = np.zeros(labels.shape, dtype=bool)
    for line in lines[1:]:
        name, _ = _prefix(line, 2)
        if name not in allowed:
            continue  # Reserve and all extras discarded before the four-field decoder.
        fields = _prefix(line, 4)
        index = allowed[name]
        tokens[index] = fields[2:]
        for col, token in enumerate(fields[2:]):
            if token == "":
                continue
            if token not in CLASS_VALUES:
                raise ValueError("Unrecognized published TDI class token")
            labels[index, col], mask[index, col] = CLASS_VALUES[token], True
    return labels, mask, np.asarray(tokens, dtype=str)


def support_report(data: TDIDevelopment) -> dict[str, Any]:
    """Both original topologies must support classes before any threshold/model fit."""
    cells, fold_hashes = [], {}
    for seed in SEEDS:
        outer, inner = balanced_nested_folds(
            data.groups, data.original_direct_training_mask, seed
        )
        fold_hashes[str(seed)] = digest(
            canonical({"outer": outer.tolist(), "inner": inner.tolist()})
        )
        for fold in range(5):
            populations = [
                ("outer_train", -1, outer != fold, False),
                ("outer_assessment", -1, outer == fold, True),
            ]
            for stage in range(3):
                populations.extend(
                    [
                        (
                            "inner_train",
                            stage,
                            (outer != fold) & (inner[fold] != stage),
                            False,
                        ),
                        (
                            "inner_assessment",
                            stage,
                            (outer != fold) & (inner[fold] == stage),
                            True,
                        ),
                    ]
                )
            for role, stage, population, assessment in populations:
                for col, endpoint in enumerate(ENDPOINTS):
                    counts, families = {}, {}
                    for value in (0, 1):
                        selected = (
                            population
                            & data.mask[:, col]
                            & (data.labels[:, col] == value)
                        )
                        counts[str(value)] = int(selected.sum())
                        families[str(value)] = len(
                            set(np.asarray(data.groups)[selected])
                        )
                    supported = all(v > 0 for v in counts.values()) and (
                        not assessment or all(v >= 2 for v in families.values())
                    )
                    cells.append(
                        {
                            "seed": seed,
                            "outer": fold,
                            "inner": stage,
                            "population": role,
                            "endpoint": endpoint,
                            "class_rows": counts,
                            "class_families": families,
                            "supported": supported,
                        }
                    )
    return {
        "schema": "cypshift.phase3.tdi_fold_support.v1",
        "supported": all(c["supported"] for c in cells),
        "seeds": list(SEEDS),
        "outer_folds": 5,
        "inner_folds": 3,
        "fold_sha256": fold_hashes,
        "cells": cells,
        "fits": 0,
        "rule": "Both classes in every training/assessment population; >=2 positive and negative families per assessment",
    }


def _from(
    development: Any,
    labels: np.ndarray,
    mask: np.ndarray,
    raw: np.ndarray,
    receipts: dict[str, str],
    support: dict[str, Any],
) -> TDIDevelopment:
    return TDIDevelopment(
        development.names,
        development.molecule_ids,
        development.raw_smiles,
        development.groups,
        labels,
        mask,
        raw,
        development.training_mask,
        receipts,
        support,
    )


def compile_tdi_development(
    compiled: Path, source: Path, mapping: Path, output: Path
) -> dict[str, Any]:
    """Explicitly authorized intake only; immutable private bundle, no fitting."""
    output = output.resolve()
    if output.exists() or any((p / ".git").exists() for p in output.parents):
        raise ValueError("TDI bundle must be a new private directory outside Git")
    runtime = {
        "python": platform.python_version(),
        **{
            name: importlib.metadata.version(name)
            for name in RUNTIME
            if name != "python"
        },
    }
    if runtime != RUNTIME:
        raise ValueError("Use the frozen complete research runtime")
    raw, map_raw = source.read_bytes(), mapping.read_bytes()
    if (
        digest(raw) != SOURCE_SHA256
        or digest(map_raw) != MAPPING_SHA256
        or digest((compiled / "manifest.json").read_bytes()) != DEVELOPMENT_SHA256
    ):
        raise ValueError(
            "TDI source/mapping/development authentication differs before decoding"
        )
    contexts = list(csv.DictReader(io.StringIO(map_raw.decode("utf-8"))))
    if len(contexts) != 6145:
        raise ValueError("TDI full metadata row count differs")
    development = load_development(compiled)
    if len(development.names) != 3908 or len(development.all_rows) != 4905:
        raise ValueError("Original TDI development/reserved population differs")
    labels, mask, raw_classes = _decode_classes(raw, contexts, development)
    receipts = {
        "source_sha256": SOURCE_SHA256,
        "mapping_sha256": MAPPING_SHA256,
        "development_manifest_sha256": DEVELOPMENT_SHA256,
        "intake_implementation_sha256": digest(Path(__file__).read_bytes()),
        "development_implementation_sha256": digest(
            Path(__file__).with_name("competition_data.py").read_bytes()
        ),
    }
    data = _from(development, labels, mask, raw_classes, receipts, {})
    support = support_report(data)
    metadata = {
        "schema": "cypshift.phase3.tdi_development_metadata.v1",
        "names": list(data.names),
        "molecule_ids": list(data.molecule_ids),
        "raw_smiles": list(data.raw_smiles),
        "groups": list(data.groups),
        "receipts": receipts,
        "runtime": runtime,
        "published_endpoints": list(ENDPOINTS),
        "all_source_rows_authenticated_before_class_decoding": 6145,
        "excluded_before_class_decoding": 2237,
        "development_rows": 3908,
        "reserve_class_fields_decoded": 0,
        "extra_class_fields_decoded": 0,
        "other_assay_response_fields_decoded": 0,
        "missing_placeholder": 0,
        "raw_class_tokens_preserved": True,
        "support": support,
    }
    buffer = io.BytesIO()
    np.savez(
        buffer,
        labels=labels,
        mask=mask,
        raw_classes=raw_classes,
        original_direct_training_mask=data.original_direct_training_mask,
    )
    payloads = {"metadata.json": canonical(metadata), "arrays.npz": buffer.getvalue()}
    manifest = {
        "schema": "cypshift.phase3.tdi_development_bundle.v1",
        "receipts": receipts,
        "files": {name: digest(value) for name, value in payloads.items()},
    }
    payloads["manifest.json"] = canonical(manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".tdi-intake-", dir=output.parent))
    try:
        for name, value in payloads.items():
            with (temporary / name).open("xb") as handle:
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
            (temporary / name).chmod(0o444)
        os.rename(temporary, output)
    finally:
        if temporary.exists():
            for path in temporary.iterdir():
                path.unlink()
            temporary.rmdir()
    return {
        "manifest_sha256": digest(payloads["manifest.json"]),
        "support": support,
        "class_counts": {
            endpoint: {
                "positive": int(((labels[:, c] == 1) & mask[:, c]).sum()),
                "negative": int(((labels[:, c] == 0) & mask[:, c]).sum()),
                "missing": int((~mask[:, c]).sum()),
            }
            for c, endpoint in enumerate(ENDPOINTS)
        },
        "reserved_numeric_targets_opened": 0,
        "fits": 0,
    }


def load_tdi_development(compiled: Path, bundle: Path) -> TDIDevelopment:
    manifest_raw = (bundle / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    expected_receipts = {
        "source_sha256": SOURCE_SHA256,
        "mapping_sha256": MAPPING_SHA256,
        "development_manifest_sha256": DEVELOPMENT_SHA256,
        "intake_implementation_sha256": digest(Path(__file__).read_bytes()),
        "development_implementation_sha256": digest(
            Path(__file__).with_name("competition_data.py").read_bytes()
        ),
    }
    if (
        manifest.get("schema") != "cypshift.phase3.tdi_development_bundle.v1"
        or manifest.get("receipts") != expected_receipts
        or set(manifest.get("files", {})) != {"metadata.json", "arrays.npz"}
        or digest((compiled / "manifest.json").read_bytes()) != DEVELOPMENT_SHA256
    ):
        raise ValueError("TDI bundle/development/source identity differs")
    payloads = {name: (bundle / name).read_bytes() for name in manifest["files"]}
    if any(
        digest(value) != manifest["files"][name] for name, value in payloads.items()
    ):
        raise ValueError("TDI bundle payload hash differs")
    metadata = json.loads(payloads["metadata.json"])
    development = load_development(compiled)
    for field in ("names", "molecule_ids", "raw_smiles", "groups"):
        if metadata.get(field) != list(getattr(development, field)):
            raise ValueError("TDI bundle development order/context differs")
    if metadata.get("receipts") != expected_receipts or metadata.get(
        "published_endpoints"
    ) != list(ENDPOINTS):
        raise ValueError("TDI metadata source/endpoint receipt differs")
    with np.load(io.BytesIO(payloads["arrays.npz"]), allow_pickle=False) as archive:
        if set(archive.files) != {
            "labels",
            "mask",
            "raw_classes",
            "original_direct_training_mask",
        }:
            raise ValueError("TDI bundle array set differs")
        labels, mask, raw = (archive[k] for k in ("labels", "mask", "raw_classes"))
        direct = archive["original_direct_training_mask"]
    if (
        labels.shape != (len(development.names), 2)
        or labels.dtype != np.float64
        or mask.shape != labels.shape
        or mask.dtype != bool
        or raw.shape != labels.shape
        or raw.dtype.kind != "U"
        or not np.isfinite(labels).all()
        or not np.isin(labels, [0, 1]).all()
        or not np.array_equal(direct, development.training_mask)
    ):
        raise ValueError("TDI label/mask/direct-fold array differs")
    for index in np.ndindex(raw.shape):
        token = raw[index]
        if (
            bool(mask[index]) != (token != "")
            or (token == "" and labels[index] != 0)
            or (
                token != ""
                and (token not in CLASS_VALUES or labels[index] != CLASS_VALUES[token])
            )
        ):
            raise ValueError("TDI raw class/missingness mapping differs")
    receipts = dict(expected_receipts, bundle_manifest_sha256=digest(manifest_raw))
    data = _from(development, labels, mask, raw, receipts, metadata["support"])
    if support_report(data) != data.support:
        raise ValueError("TDI frozen fold support differs from recomputation")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("compiled", "source", "mapping", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    report = compile_tdi_development(
        args.compiled, args.source, args.mapping, args.output
    )
    print(
        json.dumps(
            {
                "manifest_sha256": report["manifest_sha256"],
                "supported": report["support"]["supported"],
                "class_counts": report["class_counts"],
                "fits": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

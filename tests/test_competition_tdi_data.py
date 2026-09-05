"""Reserve-prefix exclusion and support checks on independent synthetic populations."""

from __future__ import annotations

import csv
import importlib
import io
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest


@pytest.fixture
def intake(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[1] / "research/maplight-fixed")
    )
    return importlib.import_module("competition_tdi_data")


def fixture_population(module: Any) -> tuple[Any, list[dict[str, str]], bytes]:
    n = 80
    names = tuple(f"molecule-{i}" for i in range(n))
    names = ("quoted,name", 'escaped"name', *names[2:])
    groups = tuple(f"family-{i // 2}" for i in range(n))
    all_rows = [
        SimpleNamespace(
            name=name,
            raw_smiles="CC",
            group=groups[i],
            reserved=False,
            quarantined=False,
        )
        for i, name in enumerate(names)
    ]
    all_rows.append(
        SimpleNamespace(
            name="reserved",
            raw_smiles="CO",
            group="reserved-family",
            reserved=True,
            quarantined=False,
        )
    )
    development = SimpleNamespace(
        names=names,
        molecule_ids=tuple(f"id-{i}" for i in range(n)),
        raw_smiles=("CC",) * n,
        groups=groups,
        training_mask=np.ones((n, 4), dtype=bool),
        all_rows=tuple(all_rows),
    )
    contexts = [
        {
            "Molecule_Name": r.name,
            "population": "original",
            "original_group": r.group,
            "original_reserved": str(r.reserved).lower(),
            "original_quarantined": "false",
            "expanded_reserved_connected": str(r.reserved).lower(),
        }
        for r in all_rows
    ]
    for seed in module.SEEDS:
        outer, inner = module.balanced_nested_folds(
            groups, development.training_mask, seed
        )
        for i, row in enumerate(contexts[:n]):
            row[f"original_outer_fold_{seed}"] = str(outer[i])
            for f in range(5):
                row[f"original_inner_fold_{seed}_outer_{f}"] = str(inner[f, i])
    contexts.append({"Molecule_Name": "extra", "population": "extra"})
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["Molecule_Name", "SMILES", *module.ENDPOINTS, "forbidden_assay"])
    for i, name in enumerate(names):
        writer.writerow(
            [
                name,
                "CC",
                "1.0" if i % 2 else "0.0",
                "" if i == 0 else ("True" if i % 2 else "False"),
                "opaque",
            ]
        )
    raw = (
        stream.getvalue().encode()
        + b'reserved,CO,\xff"unterminated suffix\nextra,CN,\xff"unterminated suffix\n'
    )
    return development, contexts, raw


def test_exclusion_before_decoder_preserves_raw_classes_and_masks(
    intake: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    development, contexts, raw = fixture_population(intake)
    original = intake._prefix
    decoded = []

    def spy(line: bytes, count: int) -> list[str]:
        if count == 4:
            decoded.append(original(line, 2)[0])
        return original(line, count)

    monkeypatch.setattr(intake, "_prefix", spy)
    labels, mask, tokens = intake._decode_classes(raw, contexts, development)
    assert "reserved" not in decoded and "extra" not in decoded
    assert tokens[0].tolist() == ["0.0", ""] and tokens[1].tolist() == ["1.0", "True"]
    assert mask[0].tolist() == [True, False] and labels[0].tolist() == [0.0, 0.0]
    assert np.all(labels[1::2] == 1)
    assert np.isfinite(labels).all()


def test_entire_metadata_pass_precedes_first_class_decode(
    intake: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    development, contexts, raw = fixture_population(intake)
    original = intake._prefix
    calls = []

    def spy(line: bytes, count: int) -> list[str]:
        if count == 4 and not line.startswith(b"Molecule_Name,"):
            calls.append(line)
        return original(line, count)

    monkeypatch.setattr(intake, "_prefix", spy)
    raw = raw.replace(b"extra,CN,", b"unknown,CN,")
    with pytest.raises(ValueError, match="before class decoding"):
        intake._decode_classes(raw, contexts, development)
    assert calls == []


def test_support_counts_families_not_repeated_positive_rows(intake: Any) -> None:
    development, contexts, raw = fixture_population(intake)
    labels, mask, tokens = intake._decode_classes(raw, contexts, development)
    data = intake._from(development, labels, mask, tokens, {}, {})
    report = intake.support_report(data)
    assert report["supported"] and len(report["cells"]) == 160
    # Many positive observations from one family cannot satisfy assessment support.
    labels[:, 0] = 0
    labels[:2, 0] = 1
    report = intake.support_report(data)
    assert not report["supported"]
    assert any(
        c["population"].endswith("assessment")
        and c["endpoint"] == intake.ENDPOINTS[0]
        and c["class_families"]["1"] < 2
        for c in report["cells"]
    )


def test_bundle_rehashed_label_token_and_family_order_tampering_rejected(
    intake: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import json

    development, contexts, source = fixture_population(intake)
    labels, mask, tokens = intake._decode_classes(source, contexts, development)
    compiled = tmp_path / "compiled"
    compiled.mkdir()
    (compiled / "manifest.json").write_bytes(b"synthetic compiled manifest")
    monkeypatch.setattr(
        intake,
        "DEVELOPMENT_SHA256",
        intake.digest((compiled / "manifest.json").read_bytes()),
    )
    monkeypatch.setattr(intake, "load_development", lambda _: development)
    receipts = {
        "source_sha256": intake.SOURCE_SHA256,
        "mapping_sha256": intake.MAPPING_SHA256,
        "development_manifest_sha256": intake.DEVELOPMENT_SHA256,
        "intake_implementation_sha256": intake.digest(
            Path(intake.__file__).read_bytes()
        ),
        "development_implementation_sha256": intake.digest(
            Path(intake.__file__).with_name("competition_data.py").read_bytes()
        ),
    }
    data = intake._from(development, labels, mask, tokens, receipts, {})
    metadata = {
        field: list(getattr(data, field))
        for field in ("names", "molecule_ids", "raw_smiles", "groups")
    }
    metadata.update(
        receipts=receipts,
        published_endpoints=list(intake.ENDPOINTS),
        support=intake.support_report(data),
    )
    bundle = tmp_path / "tdi"
    bundle.mkdir()

    def reseal() -> None:
        (bundle / "metadata.json").write_bytes(intake.canonical(metadata))
        np.savez(
            bundle / "arrays.npz",
            labels=labels,
            mask=mask,
            raw_classes=tokens,
            original_direct_training_mask=development.training_mask,
        )
        manifest = {
            "schema": "cypshift.phase3.tdi_development_bundle.v1",
            "receipts": receipts,
            "files": {
                name: intake.digest((bundle / name).read_bytes())
                for name in ("metadata.json", "arrays.npz")
            },
        }
        (bundle / "manifest.json").write_text(json.dumps(manifest))

    reseal()
    loaded = intake.load_tdi_development(compiled, bundle)
    assert loaded.support["supported"] and np.array_equal(loaded.labels, labels)
    labels[0, 0] = 1
    reseal()
    with pytest.raises(ValueError, match="raw class/missingness"):
        intake.load_tdi_development(compiled, bundle)
    labels[0, 0] = 0
    metadata["groups"] = metadata["groups"][::-1]
    reseal()
    with pytest.raises(ValueError, match="order/context"):
        intake.load_tdi_development(compiled, bundle)

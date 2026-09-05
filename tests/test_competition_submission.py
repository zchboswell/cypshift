from __future__ import annotations

import csv
import hashlib
import io

import pytest

from cypshift.competition_submission import (
    DIRECT_COLUMNS,
    IDENTIFIERS,
    TDI_COLUMNS,
    Track,
    validate_submission,
)


def raw(rows: list[list[str]]) -> bytes:
    out = io.StringIO()
    csv.writer(out).writerows(rows)
    return out.getvalue().encode()


def fixture(track: Track = "direct") -> tuple[bytes, list[list[str]]]:
    test = raw([["Molecule_Name", "SMILES"], ["a", "C"], ["b", "CC"]])
    endpoints = DIRECT_COLUMNS if track == "direct" else TDI_COLUMNS
    return test, [
        list(IDENTIFIERS + endpoints),
        ["C", "a"] + ["0"] * len(endpoints),
        ["CC", "b"] + ["1"] * len(endpoints),
    ]


@pytest.mark.parametrize("track", ["direct", "tdi"])
def test_both_tracks_validate_and_bind_receipts(track: Track) -> None:
    test, rows = fixture(track)
    submission = raw(rows)
    receipt = validate_submission(
        test,
        submission,
        track,
        expected_rows=2,
        expected_test_sha256=hashlib.sha256(test).hexdigest(),
    )
    assert receipt.submission_sha256 == hashlib.sha256(submission).hexdigest()
    assert receipt.rows == 2
    if track == "direct":
        assert list(receipt.standard_deviations.values()) == [2**-0.5] * 4
    else:
        assert list(receipt.positive_counts.values()) == [1, 1]


@pytest.mark.parametrize("value", ["", "nan", "inf", "1 ", "oops", "0", "0.001"])
def test_invalid_direct_values_and_low_variation(value: str) -> None:
    test, rows = fixture()
    rows[2][2] = value
    with pytest.raises(ValueError):
        validate_submission(
            test,
            raw(rows),
            "direct",
            expected_rows=2,
            expected_test_sha256=hashlib.sha256(test).hexdigest(),
        )


@pytest.mark.parametrize("value", ["", "NaN", "0.4", "True", "0"])
def test_tdi_requires_binary_and_both_classes(value: str) -> None:
    test, rows = fixture("tdi")
    rows[2][2] = value
    with pytest.raises(ValueError):
        validate_submission(
            test,
            raw(rows),
            "tdi",
            expected_rows=2,
            expected_test_sha256=hashlib.sha256(test).hexdigest(),
        )


@pytest.mark.parametrize(
    "mutation", ["order", "identity", "columns", "duplicate", "receipt"]
)
def test_schema_identity_and_source_rejection(mutation: str) -> None:
    test, rows = fixture()
    digest = hashlib.sha256(test).hexdigest()
    if mutation == "order":
        rows[1:] = reversed(rows[1:])
    elif mutation == "identity":
        rows[1][0] = "CCC"
    elif mutation == "columns":
        rows[0].reverse()
    elif mutation == "duplicate":
        rows[0][2] = rows[0][3]
    else:
        digest = "0" * 64
    with pytest.raises(ValueError):
        validate_submission(
            test, raw(rows), "direct", expected_rows=2, expected_test_sha256=digest
        )

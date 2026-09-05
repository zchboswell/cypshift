#!/usr/bin/env python3
"""Validate a Phase 3 CSV; emit an aggregate receipt without changing the file."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from cypshift.competition_submission import validate_submission


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-csv", required=True, type=Path)
    parser.add_argument("--submission-csv", required=True, type=Path)
    parser.add_argument("--test-sha256", required=True)
    parser.add_argument("--track", choices=("direct", "tdi"), required=True)
    args = parser.parse_args()
    receipt = validate_submission(
        args.test_csv.read_bytes(),
        args.submission_csv.read_bytes(),
        args.track,
        expected_test_sha256=args.test_sha256,
    )
    print(json.dumps(asdict(receipt), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

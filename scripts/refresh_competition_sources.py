#!/usr/bin/env python3
"""Reauthenticate reviewed public source heads and bytes before a release.

Writes a receipt to stdout. A mismatch blocks release until the changed rules
are reviewed; it does not invalidate compatible scientific training checkpoints.
No challenge data, credentials, predictions or portal state are accessed.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "benchmarks/openadmet_cyp_2026/phase3_public_source_receipt.json"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "cypshift-source-check"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def refresh() -> dict[str, Any]:
    reviewed = json.loads(RECEIPT.read_text())
    urls = {
        "space_revision": "https://huggingface.co/api/spaces/openadmet/cyp-challenge",
        "dataset_revision": (
            "https://huggingface.co/api/datasets/openadmet/cyp-challenge-train-test"
        ),
        "tutorial_revision": (
            "https://api.github.com/repos/OpenADMET/CYP-Challenge-Tutorial/commits/main"
        ),
    }
    observed = {key: json.loads(fetch(url))["sha"] for key, url in urls.items()}
    for key, value in observed.items():
        if value != reviewed[key]:
            raise ValueError(
                f"Public source changed; review before release: {key}={value}"
            )
    files = []
    for source in reviewed["files"]:
        raw = fetch(source["url"])
        digest = hashlib.sha256(raw).hexdigest()
        if digest != source["sha256"] or len(raw) != source["bytes"]:
            raise ValueError(f"Public source bytes differ: {source['file']}")
        files.append({"url": source["url"], "sha256": digest, "bytes": len(raw)})
    return {
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "reviewed_receipt_sha256": hashlib.sha256(RECEIPT.read_bytes()).hexdigest(),
        **observed,
        "files": files,
        "scope": "Public heads and bytes only; no live backend or portal verification",
    }


if __name__ == "__main__":
    print(json.dumps(refresh(), indent=2, sort_keys=True))

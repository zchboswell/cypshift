from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS
from cypshift.openadmet_oracle_private_io import (
    publish_readonly_tree,
    remove_private_root,
)
from cypshift.openadmet_oracle_runner_full import run_supported
from cypshift.openadmet_oracle_terminal_io import terminal_source_bundle_sha256


def _compact(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def _manifest(root: Path) -> str:
    data = _compact({"operation_accounting": dict.fromkeys(ACCOUNTING_FIELDS, 0)})
    root.parent.mkdir(parents=True, exist_ok=True)
    publish_readonly_tree(root, {"manifest.json": data})
    return sha256(data).hexdigest()


class _Replay:
    def __init__(self, terminal: Path) -> None:
        self.terminal = terminal
        self.stage = "projection"
        self.workers: Counter[str] = Counter()
        self.commands: Counter[str] = Counter()

    def register_manifest(self, _label: str, root: Path) -> dict[str, Any]:
        data = (root / "manifest.json").read_bytes()
        manifest = json.loads(data)
        return {
            "root": str(root),
            "manifest_sha256": sha256(data).hexdigest(),
            "operation_accounting": manifest["operation_accounting"],
        }

    def worker(self, verb: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.workers[verb] += 1
        if verb == "migrate":
            root = Path(payload["output_root"])
            return {
                "root": str(root),
                "manifest_sha256": _manifest(root),
                "operation_accounting": dict.fromkeys(ACCOUNTING_FIELDS, 0),
            }
        if verb == "episodes":
            return {"episode_ids": ["e" * 64]}
        if verb == "view":
            root = Path(payload["output_root"])
            return {
                "root": str(root),
                "manifest_sha256": _manifest(root),
                "episode_id": payload["episode_id"],
            }
        if verb == "inner":
            root = Path(payload["output_root"])
            manifest = _manifest(root)
            tokens = []
            for item in payload["token_roots"]:
                token_root = Path(item["root"])
                token_data = _compact({"score_free": True})
                publish_readonly_tree(token_root, {"selection_token.json": token_data})
                system = item["system_id"]
                alpha, lambda_value = (
                    (None, 2.0)
                    if system in {"A0", "A1"}
                    else (1.0, 2.0)
                    if system in {"C3", "T0"}
                    else (1.0, None)
                )
                tokens.append(
                    {
                        **item,
                        "sha256": sha256(token_data).hexdigest(),
                        "candidate_id": "c" * 64,
                        "alpha": alpha,
                        "lambda": lambda_value,
                        "candidate_receipt_sha256": "d" * 64,
                    }
                )
            return {
                "root": str(root),
                "manifest_sha256": manifest,
                "selection_rows": 240,
                "tokens": tokens,
            }
        if verb == "freezer":
            root = Path(payload["output_root"])
            return {
                "root": str(root),
                "manifest_sha256": _manifest(root),
                "prediction_rows": 12,
                "eligibility_rows": 1,
            }
        if verb == "accounting":
            root = Path(payload["output_root"])
            data = _compact({"accounting": True})
            publish_readonly_tree(root, {"accounting.json": data})
            children = [
                {
                    "label": f"child-{index:05d}",
                    "root": item["root"],
                    "manifest_sha256": item["manifest_sha256"],
                }
                for index, item in enumerate(payload["available_children"])
            ]
            return {
                "root": str(root),
                "sha256": sha256(data).hexdigest(),
                "children": children,
            }
        if verb == "cleanup":
            root = Path(payload["output_root"])
            data = _compact({"cleanup": True})
            publish_readonly_tree(root, {"cleanup.json": data})
            return {"root": str(root), "sha256": sha256(data).hexdigest()}
        if verb == "outer":
            cleanup = payload["inputs"]["cleanup"]
            for item in cleanup["capabilities"]:
                root = Path(item["root"])
                if root.exists():
                    remove_private_root(root)
            remove_private_root(Path(cleanup["root"]))
            terminal = _compact({"status": "R5_ORACLE_NO_SIGNAL"})
            publish_readonly_tree(self.terminal, {"manifest.json": terminal})
            return {"root": str(self.terminal)}
        raise AssertionError(verb)

    def command(self, verb: str, command: tuple[str, ...]) -> None:
        self.commands[verb] += 1
        output = Path(command[command.index("--output-root") + 1])
        _manifest(output)
        if "--shared-outer-t0" in command:
            _manifest(Path(command[command.index("--f0-output-root") + 1]))
            _manifest(Path(command[command.index("--f1-output-root") + 1]))


def _manifests() -> dict[str, str]:
    digest = "a" * 64
    result = {"model-public": digest}
    for stage in ("inner", "outer"):
        for repeat in range(3):
            for outer in range(5):
                inners = range(4) if stage == "inner" else (None,)
                for inner in inners:
                    suffix = f"{stage}/repeat-{repeat}/outer-{outer}"
                    if inner is not None:
                        suffix += f"/inner-{inner}"
                    for family in ("cell-target", "c3-target", "sealed-scorer"):
                        result[f"{family}/{suffix}"] = digest
    return result


def test_supported_topology_replays_all_exact_stage_cardinalities(
    tmp_path: Path,
) -> None:
    private = tmp_path / "private"
    private.mkdir()
    source = private / "source"
    projection = private / "projection"
    support = private / "support"
    _manifest(source)
    projection.mkdir()
    support_data = _compact({"supported": True})
    publish_readonly_tree(support, {"support.json": support_data})
    terminal = tmp_path / "terminal"
    replay = _Replay(terminal)
    status = run_supported(
        coordinator=replay,
        private_root=private,
        terminal_root=terminal,
        source_root=source,
        source_receipts={"manifest.json": "b" * 64},
        projection_root=projection,
        projection_manifests=_manifests(),
        support_root=support,
        support_sha256=sha256(support_data).hexdigest(),
        terminal_source_sha256=terminal_source_bundle_sha256(),
    )
    assert status == "R5_ORACLE_NO_SIGNAL"
    assert replay.workers["migrate"] == 75
    assert replay.workers["episodes"] == 75
    assert replay.workers["view"] == 75
    assert replay.commands == {
        "g0": 75,
        "pair-inner": 960,
        "pair-outer": 120,
        "pair-outer-shared": 15,
    }
    assert not any(private.iterdir())

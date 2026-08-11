from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")


def test_local_markdown_links_resolve() -> None:
    markdown_files = sorted(ROOT.glob("*.md"))
    for directory in ("benchmarks", "docs", "examples", "research"):
        markdown_files.extend(sorted((ROOT / directory).rglob("*.md")))

    broken: list[str] = []
    for document in markdown_files:
        text = document.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip()
            if target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            path_target = target.split("#", maxsplit=1)[0]
            if not path_target:
                continue
            resolved = (document.parent / path_target).resolve()
            if not resolved.exists():
                broken.append(f"{document.relative_to(ROOT)} -> {path_target}")

    assert broken == []

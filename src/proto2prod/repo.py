"""Read-only view of a source repository for agents.

Skips dependency folders, build output and proto2prod's own test scoring
files, so agents only ever see the app's real source.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

SKIP_DIRS = {
    "node_modules", ".next", ".git", "dist", "build", ".venv", "venv",
    "__pycache__", ".terraform", "coverage", ".turbo",
}
# Scoring keys for example apps must never be visible to the agents.
SKIP_FILES = {"KNOWN_ISSUES.md", "npm-install.log", "install.done"}
SOURCE_SUFFIXES = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".rb", ".go",
    ".java", ".kt", ".prisma", ".json", ".yaml", ".yml", ".toml", ".env",
}


@dataclass(frozen=True)
class SourceFile:
    path: Path  # relative to repo root, forward slashes when printed
    text: str

    @property
    def rel(self) -> str:
        return self.path.as_posix()

    def lines(self) -> list[str]:
        return self.text.splitlines()


class Repo:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        if not self.root.is_dir():
            raise FileNotFoundError(f"repo not found: {root}")

    def exists(self, rel: str) -> bool:
        return (self.root / rel).exists()

    def read(self, rel: str) -> str | None:
        p = self.root / rel
        return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None

    def json(self, rel: str) -> dict | None:
        text = self.read(rel)
        return json.loads(text) if text else None

    def files(self) -> Iterator[SourceFile]:
        for p in sorted(self.root.rglob("*")):
            rel = p.relative_to(self.root)
            if any(part in SKIP_DIRS for part in rel.parts):
                continue
            if not p.is_file() or p.name in SKIP_FILES:
                continue
            if p.suffix not in SOURCE_SUFFIXES and p.name not in {"Dockerfile", "Procfile"}:
                continue
            if p.stat().st_size > 512_000:
                continue
            yield SourceFile(rel, p.read_text(encoding="utf-8", errors="replace"))

    def glob(self, pattern: str) -> list[str]:
        return sorted(
            p.relative_to(self.root).as_posix()
            for p in self.root.glob(pattern)
            if not any(part in SKIP_DIRS for part in p.relative_to(self.root).parts)
        )

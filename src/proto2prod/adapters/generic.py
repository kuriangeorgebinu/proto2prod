"""Generic adapter: any containerizable app.

Used when no specific adapter matches. It gives the app full infrastructure,
CI/CD and review, but no deep refactor; the pull request says so.
"""

from __future__ import annotations

import re
from typing import Any

from ..repo import Repo
from .base import Adapter

LANG_MARKERS = [
    ("requirements.txt", "python"), ("pyproject.toml", "python"), ("Gemfile", "ruby"),
    ("go.mod", "go"), ("pom.xml", "java"), ("build.gradle", "java"), ("package.json", "javascript"),
]


class GenericAdapter(Adapter):
    name = "generic"

    def detect(self, repo: Repo) -> float:
        return 0.1  # always available as a fallback

    def default_port(self) -> int:
        # EXPOSE from the Dockerfile when profile() found one, else 8080.
        return getattr(self, "_port", 8080)

    def profile(self, repo: Repo) -> dict[str, Any]:
        language = next((lang for marker, lang in LANG_MARKERS if repo.exists(marker)), "unknown")
        dockerfiles = repo.glob("**/Dockerfile")
        port = None
        if dockerfiles:
            m = re.search(r"^\s*EXPOSE\s+(\d+)", repo.read(dockerfiles[0]) or "", re.M)
            port = int(m.group(1)) if m else None
        self._port = port or 8080
        return {
            "adapter": self.name,
            "framework": {"name": "unknown"},
            "runtime": {"language": language},
            "container": {"dockerfile": dockerfiles[0], "generated": False} if dockerfiles
                         else {"generated": True},
            "build": {"start": "container default command"},
            "services": [{"name": "web", "kind": "web"}],
            "database": {"engine": "none", "orm": "none", "migrations": "none",
                         "row_level_security": "not-applicable"},
        }

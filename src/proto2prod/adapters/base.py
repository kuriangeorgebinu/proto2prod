"""Stack adapter interface.

An adapter knows one stack: how to recognise it, describe it in an app
profile, containerise it, and which refactor rules apply. Everything after
the analyzer (infra, CI/CD, review, deploy) works on the container and does
not need an adapter.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from ..repo import Repo
from ..scanners import Finding, Rule

ENV_PATTERNS = [
    re.compile(r"process\.env\.([A-Z][A-Z0-9_]*)"),
    re.compile(r"""process\.env\[["']([A-Z][A-Z0-9_]*)["']\]"""),
    re.compile(r"""env\(["']([A-Z][A-Z0-9_]*)["']\)"""),  # prisma, many config files
    re.compile(r"""os\.(?:environ\.get|getenv)\(["']([A-Z][A-Z0-9_]*)["']"""),
    re.compile(r"""os\.environ\[["']([A-Z][A-Z0-9_]*)["']\]"""),
    re.compile(r"""ENV\[["']([A-Z][A-Z0-9_]*)["']\]"""),
]
SECRET_HINTS = ("SECRET", "PASSWORD", "TOKEN", "KEY", "DATABASE_URL", "PRIVATE", "CREDENTIAL", "DSN")
PLATFORM_VARS = {"NODE_ENV", "PORT", "HOSTNAME", "NEXT_RUNTIME", "CI"}


def find_env_vars(repo: Repo) -> list[str]:
    found: set[str] = set()
    for f in repo.files():
        for pattern in ENV_PATTERNS:
            found.update(pattern.findall(f.text))
    return sorted(found - PLATFORM_VARS)


def is_secret(name: str) -> bool:
    return any(hint in name for hint in SECRET_HINTS)


class Adapter(ABC):
    name: str

    @abstractmethod
    def detect(self, repo: Repo) -> float:
        """Confidence 0..1 that this adapter handles the repo."""

    @abstractmethod
    def profile(self, repo: Repo) -> dict[str, Any]:
        """Stack-specific part of the app profile: adapter, framework, runtime,
        container, build, services, database."""

    @abstractmethod
    def default_port(self) -> int: ...

    def extra_rules(self) -> list[Rule]:
        """Stack-specific scanner rules, run in addition to the generic ones."""
        return []

    def repo_findings(self, repo: Repo) -> list[Finding]:
        """Findings about what is missing (no health check, no Dockerfile...)."""
        findings = []
        if not repo.glob("**/Dockerfile"):
            findings.append(Finding("no-dockerfile", "low",
                                    "No Dockerfile; proto2prod will generate one."))
        return findings

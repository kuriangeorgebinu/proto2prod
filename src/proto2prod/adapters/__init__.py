"""Stack adapter registry."""

from __future__ import annotations

from ..repo import Repo
from .base import Adapter
from .generic import GenericAdapter
from .nextjs import NextjsAdapter

ADAPTERS: list[Adapter] = [NextjsAdapter(), GenericAdapter()]

MIN_CONFIDENCE = 0.5


def select_adapter(repo: Repo) -> tuple[Adapter, float]:
    """Pick the most confident adapter; fall back to generic below MIN_CONFIDENCE."""
    scored = sorted(((a.detect(repo), a) for a in ADAPTERS), key=lambda t: t[0], reverse=True)
    confidence, best = scored[0]
    if confidence < MIN_CONFIDENCE:
        return next(a for a in ADAPTERS if a.name == "generic"), confidence
    return best, confidence

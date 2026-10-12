"""Analyzer agent: reads a repo and writes app-profile.yaml + contract.yaml.

Runs before every other agent. Its outputs are validated with contract.py,
so a run cannot continue on a broken contract.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from ..adapters import select_adapter
from ..adapters.base import find_env_vars, is_secret
from ..contract import RunSpec, load_run_spec
from ..repo import Repo
from ..scanners import Finding, scan

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
HARDCODED_NAME = re.compile(r"""\b([A-Za-z_][A-Za-z0-9_]*(?:secret|password|token|key)[A-Za-z0-9_]*)\s*[:=]""", re.I)


def _slug(text: str, limit: int) -> str:
    s = re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-") or "app"
    if not s[0].isalpha():
        s = "app-" + s
    return s[:limit].rstrip("-")


def _env_name(identifier: str) -> str:
    """sessionSecret / SESSION_SECRET / session_secret -> SESSION_SECRET"""
    snake = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", identifier)
    return snake.upper()


def _hardcoded_secret_names(repo: Repo, findings: list[Finding]) -> list[str]:
    """Env var names for secrets that are currently hard-coded, so the
    contract reserves a name the refactor agent must move them to."""
    names: list[str] = []
    for f in findings:
        if f.id != "hardcoded-secret" or not f.file or not f.line:
            continue
        line = (repo.read(f.file) or "").splitlines()[f.line - 1]
        m = HARDCODED_NAME.search(line)
        if m:
            names.append(_env_name(m.group(1)))
    return names


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen, out = set(), []
    for f in findings:
        key = (f.id, f.file, f.line)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return sorted(out, key=lambda f: (SEVERITY_ORDER[f.severity], f.id, f.file or "", f.line or 0))


def _build_env(repo: Repo, profile: dict[str, Any], findings: list[Finding], app: str) -> list[dict[str, Any]]:
    names = set(find_env_vars(repo)) | set(_hardcoded_secret_names(repo, findings))
    if profile["database"]["engine"] != "none":
        names.add("DATABASE_URL")
    env = []
    for name in sorted(names):
        if is_secret(name):
            env.append({"name": name, "secret": True,
                        "secret_id": f"{app}/{name.lower().replace('_', '-')}"})
        else:
            env.append({"name": name, "secret": False})
    if profile["adapter"] == "nextjs":
        env.append({"name": "NODE_ENV", "secret": False, "default": "production"})
    return env


def analyze(
    repo_path: Path,
    run_dir: Path,
    *,
    traffic_tier: str = "standard",
    monthly_budget_usd: float = 200,
    region: str = "ca-central-1",
) -> RunSpec:
    repo = Repo(repo_path)
    adapter, confidence = select_adapter(repo)
    stack = adapter.profile(repo)

    findings = _dedupe(scan(repo, adapter.extra_rules()) + adapter.repo_findings(repo))

    pkg = repo.json("package.json") or {}
    app = _slug(pkg.get("name") or repo.root.name, 30)

    uncertain = []
    if confidence < 0.9:
        uncertain.append(f"Stack detection confidence {confidence:.2f}; using '{adapter.name}' adapter.")
    if adapter.name == "generic":
        uncertain.append("No deep-refactor adapter for this stack; only infra, CI/CD and review will be produced.")
    if stack["database"].get("migrations") == "none" and stack["database"]["engine"] != "none":
        uncertain.append("No migration history found; a baseline migration must be created from the current schema.")

    profile: dict[str, Any] = {
        "version": 1,
        **stack,
        "external_services": [],
        "findings": [f.to_dict() for f in findings],
        "uncertain": uncertain,
        "traffic_tier": traffic_tier,
        "monthly_budget_usd": monthly_budget_usd,
    }

    contract: dict[str, Any] = {
        "version": 1,
        "app": {"name": app, "port": adapter.default_port(), "health_path": "/api/health"},
        "container": {"image_name": app, "tag_scheme": "git-sha"},
        "env": _build_env(repo, profile, findings, app),
        "aws": {"region": region, "name_prefix": _slug(app, 20),
                "tags": {"project": app, "managed-by": "proto2prod"}},
        "environments": [
            {"name": "staging", "branch": "main", "requires_approval": False},
            {"name": "production", "branch": "main", "requires_approval": True},
        ],
    }

    run_dir.mkdir(parents=True, exist_ok=True)
    for name, data in (("app-profile.yaml", profile), ("contract.yaml", contract)):
        (run_dir / name).write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return load_run_spec(run_dir)

"""Load and validate the app profile and shared contract.

Every agent and reviewer calls `load_run_spec()` before doing any work, so a
run with an invalid or missing contract fails fast instead of producing
infrastructure that disagrees with the code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


class ContractError(ValueError):
    """Raised when a profile or contract file is missing or invalid."""


@dataclass(frozen=True)
class RunSpec:
    """The validated inputs shared by every agent in a run."""

    profile: dict[str, Any]
    contract: dict[str, Any]

    def secret_names(self) -> list[str]:
        return [e["name"] for e in self.contract["env"] if e["secret"]]

    def env_names(self) -> list[str]:
        return [e["name"] for e in self.contract["env"]]


def _load_schema(name: str) -> Draft202012Validator:
    path = SCHEMA_DIR / name
    with path.open(encoding="utf-8") as f:
        return Draft202012Validator(json.load(f))


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ContractError(f"{path} not found")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ContractError(f"{path} must contain a mapping at the top level")
    return data


def validate(data: dict[str, Any], schema_name: str, label: str) -> None:
    """Raise ContractError listing every schema violation, not just the first."""
    errors = sorted(_load_schema(schema_name).iter_errors(data), key=lambda e: list(e.path))
    if errors:
        lines = [f"  - {'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors]
        raise ContractError(f"{label} is invalid:\n" + "\n".join(lines))


def check_consistency(profile: dict[str, Any], contract: dict[str, Any]) -> None:
    """Cross-file rules a JSON schema cannot express."""
    names = [e["name"] for e in contract["env"]]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise ContractError(f"contract declares env vars more than once: {', '.join(dupes)}")

    if profile["database"]["engine"] == "postgres" and "DATABASE_URL" not in names:
        raise ContractError("app uses Postgres but contract has no DATABASE_URL entry")

    ci = contract["ci"]
    if ci["provider"] == "github" and ci["host"] != "https://github.com":
        raise ContractError("GitHub projects must use host https://github.com")
    if ci["provider"] == "gitlab" and ci["host"] == "https://github.com":
        raise ContractError("GitLab projects cannot use host https://github.com")

    prod = [e for e in contract["environments"] if e["name"] == "production"]
    if prod and not prod[0]["requires_approval"]:
        raise ContractError("production must require human approval")


def load_run_spec(run_dir: Path) -> RunSpec:
    """Load app-profile.yaml and contract.yaml from a run directory and validate both."""
    profile = _load_yaml(run_dir / "app-profile.yaml")
    contract = _load_yaml(run_dir / "contract.yaml")
    validate(profile, "app-profile.schema.json", "app-profile.yaml")
    validate(contract, "contract.schema.json", "contract.yaml")
    check_consistency(profile, contract)
    return RunSpec(profile=profile, contract=contract)

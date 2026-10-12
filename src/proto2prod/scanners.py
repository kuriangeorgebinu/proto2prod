"""Stack-agnostic, rule-based scanners for production-readiness flaws.

Rules are deliberately simple and explainable: each finding names the rule,
file and line so the refactor agent and the user can act on it. An LLM pass
can add findings later, but these rules run first because they are cheap,
deterministic and testable.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Callable, Iterable

from .repo import Repo, SourceFile

CODE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".rb", ".go", ".java", ".kt"}


@dataclass(frozen=True)
class Finding:
    id: str
    severity: str  # critical | high | medium | low
    summary: str
    file: str | None = None
    line: int | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


Rule = Callable[[SourceFile], Iterable[Finding]]


def _line_rule(rule_id: str, severity: str, summary: str, pattern: str, flags: int = re.I) -> Rule:
    regex = re.compile(pattern, flags)

    def run(f: SourceFile) -> Iterable[Finding]:
        if f.path.suffix not in CODE_SUFFIXES:
            return
        for n, line in enumerate(f.lines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("//", "#", "*")):
                continue
            if regex.search(line):
                yield Finding(rule_id, severity, summary, f.rel, n)

    return run


RULES: list[Rule] = [
    _line_rule(
        "hardcoded-secret", "critical",
        "Secret value hard-coded in source; move it to an environment variable backed by Secrets Manager.",
        r"""(secret|password|passwd|token|api[_-]?key|private[_-]?key)\w*\s*[:=]\s*["'][^"'\s]{8,}["']""",
    ),
    _line_rule(
        "credentials-in-url", "critical",
        "Connection string with an embedded password in source.",
        r"""["'][a-z][a-z0-9+.-]*://[^:/\s"']+:[^@\s"']+@""",
    ),
    _line_rule(
        "logs-sensitive-data", "high",
        "A log statement includes a password or secret.",
        r"""(console\.(log|info|debug|warn)|print|logger\.\w+|log\.\w+)\(.*(password|secret|token)""",
    ),
    _line_rule(
        "plaintext-password-compare", "critical",
        "Password compared in plain text; passwords must be hashed (bcrypt/argon2).",
        r"""\.password\s*(!==|===|!=|==)|(!==|===|!=|==)\s*\w*\.password\b""",
    ),
    _line_rule(
        "client-side-auth", "critical",
        "Authentication decided in the browser (localStorage/sessionStorage); enforce it on the server.",
        r"""(localStorage|sessionStorage)\.getItem\(["'](user|userId|token|auth|session)""",
    ),
    _line_rule(
        "in-memory-sessions", "high",
        "Sessions held in process memory: lost on restart and broken with more than one instance.",
        r"""sessions?\s*=\s*new\s+Map\b|sessions?\s*:\s*dict\s*=|sessions?\s*=\s*\{\s*\}""",
    ),
    _line_rule(
        "client-supplied-user-id", "critical",
        "Server trusts a user id sent by the client (IDOR); derive the user from the session.",
        r"""searchParams\.get\(["']user_?id["']\)|const\s*\{[^}]*\buserId\b[^}]*\}\s*=\s*await\s+req\.json\(\)|request\.(args|json)\.get\(["']user_?id["']\)""",
    ),
    _line_rule(
        "insecure-cookie", "medium",
        "Cookie set without httpOnly/secure/sameSite flags.",
        r"""cookies\.set\(\s*["'][^"']+["']\s*,\s*[^,)]+\)""",
    ),
]


def scan(repo: Repo, extra_rules: Iterable[Rule] = ()) -> list[Finding]:
    rules = [*RULES, *extra_rules]
    findings: list[Finding] = []
    for f in repo.files():
        for rule in rules:
            findings.extend(rule(f))
    return findings

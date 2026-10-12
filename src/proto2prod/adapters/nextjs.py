"""Next.js adapter (MVP deep-refactor stack)."""

from __future__ import annotations

import re
from typing import Any

from ..repo import Repo
from ..scanners import Finding, Rule, _line_rule
from .base import Adapter

LOCKFILES = [("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"), ("package-lock.json", "npm")]


def _clean_version(v: str | None) -> str | None:
    if not v:
        return None
    m = re.search(r"\d+(\.\d+)?", v)
    return m.group(0) if m else None


class NextjsAdapter(Adapter):
    name = "nextjs"

    def detect(self, repo: Repo) -> float:
        pkg = repo.json("package.json") or {}
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        if "next" in deps:
            return 0.95
        if repo.glob("next.config.*"):
            return 0.7
        return 0.0

    def default_port(self) -> int:
        return 3000

    def _package_manager(self, repo: Repo) -> str:
        for lockfile, pm in LOCKFILES:
            if repo.exists(lockfile):
                return pm
        return "npm"


    def _database(self, repo: Repo, deps: dict[str, str]) -> dict[str, Any]:
        schema = repo.read("prisma/schema.prisma") or ""
        if "@prisma/client" in deps or schema:
            m = re.search(r'provider\s*=\s*"(postgresql|mysql|sqlite)"', schema)
            engine = {"postgresql": "postgres", "mysql": "mysql"}.get(m.group(1) if m else "", "postgres")
            migrations = "prisma-migrate" if repo.exists("prisma/migrations") else "none"
            return {"engine": engine, "orm": "prisma", "migrations": migrations,
                    "row_level_security": "not-applicable"}
        if "drizzle-orm" in deps:
            return {"engine": "postgres", "orm": "drizzle",
                    "migrations": "drizzle-kit" if repo.glob("drizzle/**/*.sql") else "none",
                    "row_level_security": "not-applicable"}
        if "@supabase/supabase-js" in deps:
            return {"engine": "postgres", "orm": "supabase-js", "migrations": "supabase",
                    "row_level_security": "unknown"}
        if "pg" in deps or "postgres" in deps:
            return {"engine": "postgres", "orm": "pg", "migrations": "none",
                    "row_level_security": "not-applicable"}
        return {"engine": "none", "orm": "none", "migrations": "none",
                "row_level_security": "not-applicable"}

    def profile(self, repo: Repo) -> dict[str, Any]:
        pkg = repo.json("package.json") or {}
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        scripts = pkg.get("scripts", {})
        pm = self._package_manager(repo)
        run = "npm run" if pm == "npm" else pm
        install = {"npm": "npm ci" if repo.exists("package-lock.json") else "npm install",
                   "pnpm": "pnpm install --frozen-lockfile", "yarn": "yarn install --frozen-lockfile",
                   "bun": "bun install --frozen-lockfile"}[pm]
        build: dict[str, str] = {"install": install, "build": f"{run} build", "start": f"{run} start"}
        if "test" in scripts:
            build["test"] = f"{run} test"
        router = "app" if (repo.exists("src/app") or repo.exists("app")) else "pages"
        dockerfiles = repo.glob("**/Dockerfile")
        return {
            "adapter": self.name,
            "framework": {"name": "nextjs", "version": _clean_version(deps.get("next")) or "unknown",
                          "router": router},
            "runtime": {"language": "typescript" if repo.exists("tsconfig.json") else "javascript",
                        "version": _clean_version(pkg.get("engines", {}).get("node")) or "20",
                        "package_manager": pm},
            "container": {"dockerfile": dockerfiles[0], "generated": False} if dockerfiles
                         else {"generated": True},
            "build": build,
            "services": [{"name": "web", "kind": "web"}],
            "database": self._database(repo, deps),
        }


    def extra_rules(self) -> list[Rule]:
        return [
            _line_rule(
                "db-client-per-request", "high",
                "A new database client is created inside a function, so every request opens new "
                "connections; use one shared client with a connection limit.",
                r"^\s+.*\bnew\s+PrismaClient\(",
                flags=0,
            ),
        ]

    def repo_findings(self, repo: Repo) -> list[Finding]:
        findings = super().repo_findings(repo)
        pkg = repo.json("package.json") or {}
        start = pkg.get("scripts", {}).get("start", "")
        if "db push" in start:
            findings.append(Finding(
                "schema-push-on-start", "medium",
                "`start` runs `prisma db push`: can drop data and races when several containers start; "
                "use versioned migrations run once per deploy.", "package.json"))
        health = [p for p in ("src/app/api/health", "app/api/health", "src/pages/api/health.ts",
                              "pages/api/health.ts", "src/app/health", "app/health") if repo.exists(p)]
        if not health:
            findings.append(Finding("no-health-check", "medium",
                                    "No health-check endpoint for the load balancer (expected /api/health)."))
        if not any(n in (pkg.get("dependencies") or {}) for n in ("zod", "yup", "valibot", "joi")):
            findings.append(Finding("no-input-validation", "medium",
                                    "No request validation library found; API inputs are unchecked."))
        if not any(n in (pkg.get("dependencies") or {}) for n in ("bcrypt", "bcryptjs", "argon2", "@node-rs/argon2")):
            if repo.glob("**/api/**/*login*") or repo.glob("**/api/**/*signup*") or repo.glob("**/api/login/**") or repo.glob("**/api/signup/**"):
                findings.append(Finding("no-password-hashing", "critical",
                                        "App has login/signup but no password-hashing library."))
        return findings

from pathlib import Path

import pytest

from proto2prod.agents.analyzer import analyze

ROOT = Path(__file__).resolve().parents[1]
NOTES_APP = ROOT / "examples" / "notes-app"

# Scoring key: KNOWN_ISSUES.md id -> (rule id, file it must point at or None)
EXPECTED = {
    "P2P-01": ("client-supplied-user-id", "src/app/api/notes/route.ts"),
    "P2P-02": ("client-supplied-user-id", "src/app/api/notes/route.ts"),
    "P2P-03": ("client-side-auth", "src/app/notes/page.tsx"),
    "P2P-04": ("plaintext-password-compare", "src/app/api/login/route.ts"),
    "P2P-05": ("logs-sensitive-data", "src/app/api/signup/route.ts"),
    "P2P-06": ("hardcoded-secret", "src/lib/auth.ts"),
    "P2P-07": ("credentials-in-url", "src/lib/db.ts"),
    "P2P-08": ("in-memory-sessions", "src/lib/auth.ts"),
    "P2P-09": ("db-client-per-request", "src/lib/db.ts"),
    "P2P-10": ("insecure-cookie", None),
    "P2P-11": ("schema-push-on-start", "package.json"),
    "P2P-12": ("no-health-check", None),
    "P2P-13": ("no-input-validation", None),
    "P2P-14": ("no-dockerfile", None),
}


@pytest.fixture(scope="module")
def spec(tmp_path_factory):
    return analyze(NOTES_APP, tmp_path_factory.mktemp("run"))


def test_detects_nextjs_with_prisma_postgres(spec):
    p = spec.profile
    assert p["adapter"] == "nextjs"
    assert p["framework"]["router"] == "app"
    assert p["database"] == {"engine": "postgres", "orm": "prisma", "migrations": "none",
                             "row_level_security": "not-applicable"}
    assert p["container"] == {"generated": True}


@pytest.mark.parametrize("issue", sorted(EXPECTED))
def test_finds_known_issue(spec, issue):
    rule, file = EXPECTED[issue]
    hits = [f for f in spec.profile["findings"] if f["id"] == rule]
    assert hits, f"{issue}: no '{rule}' finding"
    if file:
        assert any(f.get("file") == file for f in hits), f"{issue}: '{rule}' not reported in {file}"


def test_contract_reserves_env_names_for_hardcoded_secrets(spec):
    assert spec.secret_names() == ["DATABASE_URL", "SESSION_SECRET"]


def test_analyzer_never_reads_scoring_key(spec):
    assert not any("KNOWN_ISSUES" in (f.get("file") or "") for f in spec.profile["findings"])


def test_unknown_stack_falls_back_to_generic(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "requirements.txt").write_text("fastapi\n")
    (app / "Dockerfile").write_text("FROM python:3.12-slim\nEXPOSE 8000\nCMD [\"uvicorn\", \"main:app\"]\n")
    (app / "main.py").write_text(
        "import os\nAPI_TOKEN = os.getenv('API_TOKEN')\nprint('ready')\n"
    )
    spec = analyze(app, tmp_path / "run")
    assert spec.profile["adapter"] == "generic"
    assert spec.profile["runtime"]["language"] == "python"
    assert spec.contract["app"]["port"] == 8000
    assert spec.secret_names() == ["API_TOKEN"]
    assert any("only infra" in u for u in spec.profile["uncertain"])

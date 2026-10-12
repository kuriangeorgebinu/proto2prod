import copy
import shutil
from pathlib import Path

import pytest
import yaml

from proto2prod.contract import ContractError, load_run_spec

FIXTURE = Path(__file__).parent / "fixtures" / "valid"


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    for name in ("app-profile.yaml", "contract.yaml"):
        shutil.copy(FIXTURE / name, tmp_path / name)
    return tmp_path


def _edit_contract(run_dir: Path, mutate) -> None:
    path = run_dir / "contract.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_valid_run_spec_loads(run_dir):
    spec = load_run_spec(run_dir)
    assert spec.secret_names() == ["DATABASE_URL", "NEXTAUTH_SECRET"]
    assert "NODE_ENV" in spec.env_names()


def test_secret_without_secret_id_is_rejected(run_dir):
    _edit_contract(run_dir, lambda c: c["env"][0].pop("secret_id"))
    with pytest.raises(ContractError, match="contract.yaml is invalid"):
        load_run_spec(run_dir)


def test_secret_with_default_value_is_rejected(run_dir):
    _edit_contract(run_dir, lambda c: c["env"][0].update(default="postgres://x"))
    with pytest.raises(ContractError):
        load_run_spec(run_dir)


def test_duplicate_env_var_is_rejected(run_dir):
    _edit_contract(run_dir, lambda c: c["env"].append(copy.deepcopy(c["env"][2])))
    with pytest.raises(ContractError, match="more than once: NODE_ENV"):
        load_run_spec(run_dir)


def test_postgres_app_needs_database_url(run_dir):
    _edit_contract(run_dir, lambda c: c["env"].pop(0))
    with pytest.raises(ContractError, match="DATABASE_URL"):
        load_run_spec(run_dir)


def test_production_must_require_approval(run_dir):
    _edit_contract(run_dir, lambda c: c["environments"][1].update(requires_approval=False))
    with pytest.raises(ContractError, match="human approval"):
        load_run_spec(run_dir)


def test_missing_file_is_reported(run_dir):
    (run_dir / "contract.yaml").unlink()
    with pytest.raises(ContractError, match="not found"):
        load_run_spec(run_dir)


def test_github_provider_requires_github_host(run_dir):
    _edit_contract(run_dir, lambda c: c["ci"].update(provider="github"))  # host is gitlab.com
    with pytest.raises(ContractError, match="GitHub projects"):
        load_run_spec(run_dir)


def test_ci_project_must_be_a_path(run_dir):
    _edit_contract(run_dir, lambda c: c["ci"].update(project="notes-app"))
    with pytest.raises(ContractError, match="contract.yaml is invalid"):
        load_run_spec(run_dir)

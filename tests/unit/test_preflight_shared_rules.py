"""커밋 검사와 색인 필터가 같은 비밀값 규칙을 쓴다(QK-SEC-001 FR-009, research R-02)."""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from qello_knowledge.domain.secret_rules import RULES

ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT = ROOT / "scripts" / "preflight.py"
RULES_MODULE = Path("src/qello_knowledge/domain/secret_rules.py")
FAKE_TOKEN = "gh" + "p_" + "A" * 36


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)  # noqa: S603, S607


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-I", "scripts/preflight.py", *args], cwd=repo, text=True, capture_output=True, check=False
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    shutil.copy(PREFLIGHT, tmp_path / "scripts" / "preflight.py")
    (tmp_path / RULES_MODULE).parent.mkdir(parents=True)
    shutil.copy(ROOT / RULES_MODULE, tmp_path / RULES_MODULE)
    _git(tmp_path, "init", "-q")
    return tmp_path


def test_preflight_uses_the_shared_rules():
    spec = importlib.util.spec_from_file_location("preflight_under_test", PREFLIGHT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rules = module.load_rules(staged=False)
    assert [(rule.name, rule.pattern.pattern, rule.pattern.flags) for rule in rules] == [
        (rule.name, rule.pattern.pattern, rule.pattern.flags) for rule in RULES
    ]


def test_preflight_runs_isolated_without_the_package(repo: Path):
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_staged_check_uses_the_rules_in_the_index(repo: Path):
    _git(repo, "add", str(RULES_MODULE))
    # 작업 트리의 규칙에서 github-token 규칙을 빼도, --staged는 index에 있는 규칙으로 검사해야 한다.
    working = repo / RULES_MODULE
    working.write_text(working.read_text(encoding="utf-8").replace('"github-token"', '"github-token-off"'), "utf-8")
    (repo / "sample.md").write_text(f"token: {FAKE_TOKEN}\n", encoding="utf-8")
    _git(repo, "add", "sample.md")
    result = _run(repo, "--staged")
    assert result.returncode == 1
    assert "sample.md:1: github-token" in result.stdout
    assert FAKE_TOKEN not in result.stdout + result.stderr


def test_staged_check_fails_when_rules_are_not_in_the_index(repo: Path):
    (repo / "sample.md").write_text("plain\n", encoding="utf-8")
    _git(repo, "add", "sample.md")
    result = _run(repo, "--staged")
    assert result.returncode == 1
    assert "rules-module-not-staged" in result.stdout


@pytest.mark.parametrize("change", ["side-effect", "deleted", "syntax-error"])
def test_staged_check_never_runs_the_working_tree_rules(repo: Path, change: str):
    _git(repo, "add", str(RULES_MODULE))
    working = repo / RULES_MODULE
    marker = repo / "executed.txt"
    if change == "side-effect":
        working.write_text(working.read_text(encoding="utf-8") + f"\nopen({str(marker)!r}, 'w').close()\n", "utf-8")
    elif change == "deleted":
        working.unlink()
    else:
        working.write_text("def broken(:\n", encoding="utf-8")
    (repo / "sample.md").write_text("plain\n", encoding="utf-8")
    _git(repo, "add", "sample.md")
    result = _run(repo, "--staged")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not marker.exists()

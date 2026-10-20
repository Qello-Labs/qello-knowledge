"""비밀값 검사 오탐 예외 목록(FR-022). 임시 git 저장소에 preflight.py를 복사해 실제로 실행한다."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "scripts" / "preflight.py"
# preflight.py는 규칙을 이 파일에서 경로로 불러온다(QK-SEC-001 R-02).
RULES_MODULE = Path("src/qello_knowledge/domain/secret_rules.py")
# 형식만 맞춘 가짜 토큰. 파일에 그대로 남지 않게 이어 붙인다.
FAKE_TOKEN = "gh" + "p_" + "A" * 36


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    shutil.copy(SOURCE, tmp_path / "scripts" / "preflight.py")
    (tmp_path / RULES_MODULE).parent.mkdir(parents=True)
    shutil.copy(SOURCE.parents[1] / RULES_MODULE, tmp_path / RULES_MODULE)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)  # noqa: S607
    (tmp_path / "sample.md").write_text(f"token: {FAKE_TOKEN}\n", encoding="utf-8")
    return tmp_path


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "scripts/preflight.py"], cwd=repo, text=True, capture_output=True, check=False
    )


def _allow(repo: Path, line: str) -> None:
    (repo / "scripts" / "preflight_allowlist.txt").write_text(f"# 설명\n{line}\n", encoding="utf-8")


def test_finding_without_allowlist_fails_without_value(repo: Path) -> None:
    result = _run(repo)
    assert result.returncode == 1
    assert "sample.md:1: github-token" in result.stdout
    assert FAKE_TOKEN not in result.stdout + result.stderr


def test_allowlisted_finding_with_reason_passes(repo: Path) -> None:
    _allow(repo, "sample.md:github-token # 문서 예시용 가짜 토큰")
    assert _run(repo).returncode == 0


def test_entry_without_reason_fails(repo: Path) -> None:
    _allow(repo, "sample.md:github-token")
    result = _run(repo)
    assert result.returncode == 1
    assert "allowlist-entry-needs-path-rule-and-reason" in result.stdout


def test_entry_for_other_rule_does_not_hide_finding(repo: Path) -> None:
    _allow(repo, "sample.md:slack-token # 다른 규칙")
    assert _run(repo).returncode == 1

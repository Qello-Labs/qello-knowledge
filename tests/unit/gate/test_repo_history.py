"""`GitHistory`(QK-STO-002 research R-09). 임시 git 저장소만 쓴다. 네트워크 0."""

import shutil
import subprocess

import pytest

from qello_knowledge.adapters.git_history import GitHistory

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git 없음")


def _git(root, *args):
    return subprocess.run(  # noqa: S603 - 시험용 임시 저장소의 고정 인자
        [shutil.which("git"), "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "test")
    (root / "README.md").write_text("x\n")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "init")
    _git(root, "switch", "-q", "-c", "feature")
    policy = root / "eval/gate_policies/p/v1.toml"
    policy.parent.mkdir(parents=True)
    policy.write_text("a\n")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "policy")
    feature = _git(root, "rev-parse", "HEAD")
    _git(root, "switch", "-q", "main")
    _git(root, "merge", "-q", "--no-ff", "-m", "merge", "feature")
    merge = _git(root, "rev-parse", "HEAD")
    return root, feature, merge


def test_first_added_commit_is_the_merge_on_first_parent_history(repo):
    root, feature, merge = repo
    history = GitHistory(root)
    assert history.first_added_commit("main", "eval/gate_policies/p/v1.toml") == merge
    assert history.first_added_commit("main", "eval/gate_policies/p/v2.toml") is None
    assert history.file_at("main", "eval/gate_policies/p/v1.toml") == b"a\n"
    assert history.file_at("main", "missing.toml") is None
    assert history.list_paths("main", "eval/gate_policies/p") == ("eval/gate_policies/p/v1.toml",)
    assert history.is_ancestor(merge, merge) and history.is_ancestor(feature, merge)
    assert not history.is_ancestor(merge, feature)
    assert not history.is_ancestor("0" * 40, merge)


def test_head_and_dirty(repo):
    root, _, merge = repo
    history = GitHistory(root)
    assert history.head() == (merge, False)
    (root / "README.md").write_text("changed\n")
    assert history.head() == (merge, True)

"""`qk-dev eval-index prepare --keyword-tokenizer` 인자 검사(QK-EVL-001 contracts/cli.md 5절, tasks T036).

DB에 연결하지 않는 경로만 본다. 설정이 없는 환경에서도 인자 오류가 2로 먼저 나온다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qello_knowledge.devtools import db
from qello_knowledge.devtools.eval_index import eval_db_name, eval_tokenizer_db_name

SHA = "abcdef0123456789" + "0" * 24
BASE = ["eval-index", "prepare", "--rule", "kw-index-baseline-v1", "--commit", SHA]
ALPHA = ["--keyword-tokenizer", "TokenBigramSplitSymbolAlpha"]


def _main(tmp_path: Path, *argv: str) -> int:
    return db.main([*argv, "--env-file", str(tmp_path / "none.env")])


def test_names() -> None:
    assert eval_tokenizer_db_name(SHA) == "qk_eval_baseline_alpha_abcdef012345"
    assert eval_db_name("kw-index-baseline-v1", SHA) == "qk_eval_baseline_abcdef012345"


def test_unknown_tokenizer_is_an_argument_error(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as raised:
        _main(tmp_path, *BASE, "--keyword-tokenizer", "TokenNgram")
    assert raised.value.code == 2


@pytest.mark.parametrize(
    "extra",
    [
        ["--source", "other-docs"],
        ["--from-url-env", "QK_ORIGIN"],
        ["--allow-embed"],
        ["--sources", "elsewhere.toml"],
        ["--reviews", "elsewhere"],
        ["--exceptions", "elsewhere.toml"],
    ],
)
def test_sync_options_are_refused_with_tokenizer(
    tmp_path: Path, extra: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert _main(tmp_path, *BASE, *ALPHA, *extra) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "sync_option_with_tokenizer"


def test_idsplit_rule_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["eval-index", "prepare", "--rule", "kw-index-idsplit-v1", "--commit", SHA, *ALPHA]
    assert _main(tmp_path, *argv) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "tokenizer_needs_baseline_rule"


@pytest.mark.parametrize("commit", ["abc1234", "G" * 40])
def test_commit_must_be_full_sha(tmp_path: Path, commit: str, capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["eval-index", "prepare", "--rule", "kw-index-baseline-v1", "--commit", commit, *ALPHA]
    assert _main(tmp_path, *argv) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "commit_must_be_full_sha"

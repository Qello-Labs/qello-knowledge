"""색인 쪽 키워드 규칙과 청킹 규칙 버전(QK-RET-001 spec SC-010, research R-04·R-05, tasks T035·T039).

기존 `test_version.py`는 바꾸지 않는다.
"""

from __future__ import annotations

import pytest

from qello_knowledge.chunking.version import chunking_version
from qello_knowledge.domain.chunking import ChunkingSettings
from qello_knowledge.domain.keyword_rules import INDEX_BASELINE, INDEX_IDSPLIT, INDEX_KEYWORD_RULES, index_rule_for
from qello_knowledge.sync.keys import index_version_id

BASELINE_CHUNKING = "chk-md-20d966f730bb"
BASELINE_INDEX = "iv-4c0bc4fcc642"


def _index_version(rule: str) -> str:
    return index_version_id("@cf/baai/bge-m3", 1024, chunking_version(ChunkingSettings(keyword_text_rule=rule)))


def test_baseline_values_are_unchanged() -> None:
    assert ChunkingSettings().keyword_text_rule == INDEX_BASELINE
    assert chunking_version(ChunkingSettings()) == BASELINE_CHUNKING
    assert index_version_id("@cf/baai/bge-m3", 1024, BASELINE_CHUNKING) == BASELINE_INDEX


def test_idsplit_changes_chunking_and_index_version() -> None:
    idsplit = chunking_version(ChunkingSettings(keyword_text_rule=INDEX_IDSPLIT))
    assert idsplit != BASELINE_CHUNKING and idsplit.startswith("chk-md-")
    assert _index_version(INDEX_IDSPLIT) != BASELINE_INDEX


def test_unknown_rule_is_rejected() -> None:
    with pytest.raises(ValueError):
        ChunkingSettings(keyword_text_rule="kw-index-v9")


def test_rule_table_matches_computed_versions() -> None:
    assert set(INDEX_KEYWORD_RULES.values()) == {INDEX_BASELINE, INDEX_IDSPLIT}
    for index_version, rule in INDEX_KEYWORD_RULES.items():
        assert _index_version(rule) == index_version
    assert index_rule_for(_index_version(INDEX_IDSPLIT)) == INDEX_IDSPLIT
    assert index_rule_for("iv-unknown") == "unknown" and index_rule_for(None) == "unknown"

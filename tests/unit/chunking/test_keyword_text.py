"""색인 쪽 키워드 검색 텍스트 규칙(QK-RET-001 research R-04, spec FR-018·FR-019, tasks T036)."""

from __future__ import annotations

from qello_knowledge.chunking import chunk_markdown
from qello_knowledge.chunking.header import identifier_parts, search_text
from qello_knowledge.domain.chunking import ChunkingSettings
from qello_knowledge.domain.keyword_rules import INDEX_BASELINE, INDEX_IDSPLIT

DOC = "# 결제\n\n`retryPayment2` 와 HTTPClient, max_retry_count, `/payments/{id}/cancel`, error-codes 를 본다.\n"


def test_baseline_is_byte_identical_to_previous_format() -> None:
    assert search_text("헤더", "본문", INDEX_BASELINE) == "헤더\n\n본문"
    assert search_text("헤더", "본문") == "헤더\n\n본문"


def test_identifier_parts() -> None:
    assert identifier_parts("retryPayment HTTPClient retryPayment2 getURLPath") == (
        "retry", "payment", "http", "client", "2", "get", "url", "path",
    )  # fmt: skip
    assert identifier_parts("max_retry_count /payments/{id}/cancel error-codes v1 plain") == ()
    assert identifier_parts("한국어 문장") == ()


def test_idsplit_appends_parts_and_keeps_original() -> None:
    text = search_text("docs/a.md\n결제 > retryPayment", "본문 HTTPClient", INDEX_IDSPLIT)
    assert text == "docs/a.md\n결제 > retryPayment\n\n본문 HTTPClient\n\nretry payment http client"
    assert search_text("헤더", "식별자 없는 본문", INDEX_IDSPLIT) == "헤더\n\n식별자 없는 본문"


def test_chunker_uses_rule_but_embedding_text_is_unchanged() -> None:
    base = chunk_markdown(DOC, location="docs/a.md", source_title=None, settings=ChunkingSettings())
    split = chunk_markdown(
        DOC, location="docs/a.md", source_title=None, settings=ChunkingSettings(keyword_text_rule=INDEX_IDSPLIT)
    )
    assert [d.embedding_text for d in base.drafts] == [d.embedding_text for d in split.drafts]
    assert [d.chunk.body for d in base.drafts] == [d.chunk.body for d in split.drafts]
    joined = " ".join(d.chunk.search_text for d in split.drafts)
    assert "retryPayment2" in joined and "retry payment 2" in joined and "http client" in joined
    assert all(d.chunk.search_text.startswith(d.search_header) for d in split.drafts)
    assert base.chunking_version != split.chunking_version

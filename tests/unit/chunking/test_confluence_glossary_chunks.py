"""용어집 한 줄이 한 검색 단위가 된다(QK-ING-003 US5, FR-023, SC-006)."""

from qello_knowledge.adapters.atlassian_adf import GLOSSARY_HEADER, convert_adf
from qello_knowledge.chunking.service import chunk_markdown
from qello_knowledge.domain.chunking import ChunkingSettings

ROWS = [
    ("결제 재시도", "실패한 결제를 다시 시도한다.", "retry", "retryPayment"),
    ("정산", "매출을 확정한다.", "settlement", "GET /settlements"),
    ("환불", "결제를 되돌린다.", "refund", "refundPayment"),
    ("등번호", "선수 번호다.", "jersey", "PUT /players/{id}/number"),
    ("하이라이트", "경기 장면 묶음이다.", "highlight", "HighlightService"),
]


def _cell(text, kind="tableCell"):
    return {"type": kind, "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}


def _glossary_doc():
    header = {"type": "tableRow", "content": [_cell(h, "tableHeader") for h in GLOSSARY_HEADER]}
    rows = [{"type": "tableRow", "content": [_cell(v) for v in (*row, "")]} for row in ROWS]
    return {"type": "doc", "version": 1, "content": [{"type": "table", "content": [header, *rows]}]}


def test_each_glossary_row_becomes_one_chunk():
    result = convert_adf(_glossary_doc(), title="용어집", site_host=None, public_link_hosts=(), doc_type="용어집")
    assert result.warnings == ()
    outcome = chunk_markdown(
        result.markdown, location="SCRUM/용어집", source_title="용어집", settings=ChunkingSettings()
    )
    terms = [d for d in outcome.drafts if d.chunk.heading_path and d.chunk.heading_path[-1] in {r[0] for r in ROWS}]
    assert len(terms) == len(ROWS)
    for draft, (term, definition, synonym, identifier) in zip(terms, ROWS, strict=True):
        assert draft.chunk.heading_path[-1] == term
        body = draft.chunk.body
        assert definition in body and synonym in body and identifier in body


def test_other_header_is_not_split():
    doc = _glossary_doc()
    doc["content"][0]["content"][0]["content"][1] = _cell("뜻", "tableHeader")
    result = convert_adf(doc, title="용어집", site_host=None, public_link_hosts=(), doc_type="용어집")
    assert [w.kind.value for w in result.warnings] == ["NOT_GLOSSARY"]
    assert "## 결제 재시도" not in result.markdown

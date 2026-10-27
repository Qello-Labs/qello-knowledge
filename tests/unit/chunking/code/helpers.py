"""코드 청커 기대값 픽스처 도우미(QK-CHK-001 tasks T002).

기대 JSON은 사람이 정한 정답이다. `expected`에 있는 키만 비교하고,
`code`(`locator["code"]`)는 들어 있는 하위 키만 비교한다.
"""

import json
from pathlib import Path

from qello_knowledge.chunking.code.service import chunk_code
from qello_knowledge.domain.chunking import ChunkingSettings, CodeChunkingSettings
from qello_knowledge.domain.keyword_rules import INDEX_BASELINE

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "chunking" / "code"
CHUNK_KEYS = ("ordinal", "lines", "heading_path", "search_header", "search_text", "embedding_text")


def cases():
    for path in sorted(FIXTURES.glob("*.expected.json")):
        stem = path.name.removesuffix(".expected.json")
        (source,) = [p for p in (FIXTURES / f"{stem}.java", FIXTURES / f"{stem}.kt") if p.exists()]
        yield stem, source.read_text(encoding="utf-8"), json.loads(path.read_text(encoding="utf-8"))


def settings_of(case):
    inputs = case["input"]
    settings = ChunkingSettings(keyword_text_rule=inputs.get("keyword_text_rule", INDEX_BASELINE))
    return settings, CodeChunkingSettings(**inputs.get("code_settings", {}))


def run(body, case):
    settings, code = settings_of(case)
    return chunk_code(body, location=case["input"]["location"], settings=settings, code=code)


def actual_chunk(draft):
    return dict(
        ordinal=draft.chunk.ordinal,
        lines=list(draft.chunk.locator["lines"]),
        heading_path=list(draft.chunk.heading_path),
        search_header=draft.search_header,
        search_text=draft.chunk.search_text,
        embedding_text=draft.embedding_text,
        code=dict(draft.chunk.locator["code"]),
    )


def assert_matches(name, result, expected):
    assert result.outcome == expected["outcome"], name
    if "failure" in expected:
        assert result.failure == expected["failure"], name
    if "document_title" in expected:
        assert result.document_title == expected["document_title"], name
    if "warnings" in expected:
        assert [{"kind": w.kind, "line": w.line} for w in result.warnings] == expected["warnings"], name
    oracles = expected.get("chunks", [])
    assert len(result.drafts) == len(oracles), name
    for draft, oracle in zip(result.drafts, oracles, strict=True):
        actual = actual_chunk(draft)
        for key, value in oracle.items():
            if key == "code":
                assert {k: actual["code"][k] for k in value} == value, (name, oracle.get("ordinal"))
            else:
                assert actual[key] == value, (name, oracle.get("ordinal"), key)

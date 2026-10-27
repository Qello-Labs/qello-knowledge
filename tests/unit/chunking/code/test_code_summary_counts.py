"""섞인 결과의 요약 수치가 파일별 결과를 직접 센 값과 같다(QK-CHK-001 spec SC-010, FR-031, tasks T044)."""

from collections import Counter
from statistics import median_low

from qello_knowledge.chunking import chunk_screened
from qello_knowledge.domain.chunking import ChunkingSettings, CodeChunkingSettings
from tests.unit.chunking.code.helpers import cases
from tests.unit.chunking.helpers import screened


def test_summary_matches_direct_counts():
    batch = [
        screened(body, content_format="CODE", location=case["input"]["location"])
        for _, body, case in cases()
        if not case["input"].get("code_settings") and "keyword_text_rule" not in case["input"]
    ]
    batch += [
        screened("# 문서\n\n본문\n", location="docs/a.md"),
        screened("", content_format="CODE", location="a/Empty.kt"),
        screened('class A {\n    String s = "' + "x" * 9000 + '";\n}\n', content_format="CODE", location="a/A.java"),
        screened("x = 1\n", content_format="CODE", location="a/b.py"),
    ]
    result = chunk_screened(batch, ChunkingSettings(), code=CodeChunkingSettings())
    summary = result.summary
    drafts = [d for r in result.results for d in r.drafts]
    tokens = [d.estimated_tokens for d in drafts]
    code = [d for d in drafts if "code" in d.chunk.locator]

    assert dict(summary.by_outcome) == Counter(r.outcome for r in result.results)
    assert set(summary.by_outcome) == {"CHUNKED", "EMPTY", "FAILED", "NOT_MARKDOWN"}
    assert summary.chunk_count == len(drafts)
    assert dict(summary.by_failure) == Counter(r.failure for r in result.results if r.failure)
    assert dict(summary.by_warning) == Counter(w.kind for r in result.results for w in r.warnings)
    assert (summary.tokens_min, summary.tokens_median, summary.tokens_max) == (
        min(tokens),
        median_low(tokens),
        max(tokens),
    )
    assert summary.split_blocks == sum(r.split_blocks for r in result.results)
    assert dict(summary.by_code_kind) == Counter(d.chunk.locator["code"]["chunk_kind"] for d in code)
    assert summary.code_test_chunks == sum(d.chunk.locator["code"]["test_code"] for d in code)

    components = Counter()
    for r in result.results:
        previous = None
        for d in r.drafts:
            meta = d.chunk.locator.get("code")
            key = (d.chunk.heading_path, meta["chunk_kind"], meta["summary"]) if meta else None
            first = key != previous
            previous = key
            if not meta or not first or not meta["component"]:
                continue
            if meta["chunk_kind"] == "TYPE_HEAD" and meta["component"] != "COMPOSABLE":
                components[meta["component"]] += 1
            elif meta["chunk_kind"] in ("METHOD", "TOP_FUNCTION") and meta["component"] == "COMPOSABLE":
                components[meta["component"]] += 1
    assert dict(summary.code_components) == components
    assert components == {"VIEW_MODEL": 1, "FRAGMENT": 1, "COMPOSABLE": 3}  # android_composable 1 + android_preview 2

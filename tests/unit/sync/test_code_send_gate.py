"""코드 청크의 전송 직전 검사(QK-CHK-001 spec SC-009, research R-12, tasks T043). 가짜 제공자, 0 Neurons.

조립은 T027의 `code_harness`를 쓴다(공용 `helpers.py`는 바꾸지 않는다). 빈 임베딩 캐시에서 시작한다.
"""

from qello_knowledge.chunking.code.service import chunk_code
from qello_knowledge.domain.chunking import ChunkingSettings, CodeChunkingSettings
from qello_knowledge.sync.run import SyncOptions, run_sync
from tests.unit.sync.test_code_sync_versions import JAVA, MARKDOWN, code_harness
from tests.unit.synthetic_secrets import SYNTHETIC

KOTLIN = "package a\n\nfun slug(text: String): String {\n    return text.lowercase()\n}\n"


def test_every_code_chunk_passes_the_send_gate():
    code = CodeChunkingSettings()
    docs = {"code-a": ("A.java", JAVA), "code-k": ("Slugs.kt", KOTLIN), "doc-b": ("b.md", MARKDOWN)}
    h = code_harness(docs, code=code)
    result = run_sync(h.targets, h.deps, SyncOptions())
    assert result.sources[0]["counts"] == {"PROCESS": 3}
    drafts = [
        d
        for name, body in (("A.java", JAVA), ("Slugs.kt", KOTLIN))
        for d in chunk_code(body, location=f"src/main/java/a/{name}", settings=ChunkingSettings(), code=code).drafts
    ]
    assert {"TYPE_SUMMARY", "FILE_SUMMARY"} <= {
        d.chunk.locator["code"]["chunk_kind"] for d in drafts
    }  # 요약도 검사한다
    assert all(d.embedding_text in h.sent for d in drafts)
    assert len(h.provider.calls) >= 1


def test_secret_code_file_is_screened_out():
    secret = JAVA.replace("g();", f'String token = "{SYNTHETIC["github-classic"]}";')
    h = code_harness({"code-s": ("Secret.java", secret), "code-a": ("A.java", JAVA)}, code=CodeChunkingSettings())
    run_sync(h.targets, h.deps, SyncOptions())
    assert all(SYNTHETIC["github-classic"] not in text for text in h.sent)
    stored = {doc.source_id: doc for doc in h.store.documents.values()}
    assert "code-a" in stored
    assert not any(SYNTHETIC["github-classic"] in chunk.body for chunks in h.store.chunks.values() for chunk in chunks)

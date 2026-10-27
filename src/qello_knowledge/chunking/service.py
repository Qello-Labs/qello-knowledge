"""외부 호출 없는 순수 청킹과 자료별 실패 격리."""

from collections.abc import Iterable
from dataclasses import fields

from qello_knowledge.chunking.blocks import parse_document
from qello_knowledge.chunking.code.service import chunk_code
from qello_knowledge.chunking.code.version import code_chunking_version
from qello_knowledge.chunking.header import embedding_text, search_header, search_text
from qello_knowledge.chunking.sections import document_title, split_sections
from qello_knowledge.chunking.split import SplitFailure, split_blocks
from qello_knowledge.chunking.version import chunking_version, index_chunking_version, is_code_target
from qello_knowledge.chunking.warnings import structure_warnings
from qello_knowledge.domain.chunking import (
    ChunkDraft,
    ChunkedContent,
    ChunkFailureKind,
    ChunkingResult,
    ChunkingSettings,
    ChunkingSummary,
    ChunkOutcome,
    ChunkOutcomeKind,
    CodeChunkingSettings,
)
from qello_knowledge.domain.embedding import MODELS
from qello_knowledge.domain.security import ScreenedContent
from qello_knowledge.domain.source import ContentFormat
from qello_knowledge.domain.store import ChunkInput
from qello_knowledge.embedding.estimate import estimated_tokens


def _empty(kind, version, failure=None):
    return ChunkOutcome(kind, None, (), (), failure, 0, version)


def chunk_markdown(body: str, *, location: str, source_title: str | None, settings: ChunkingSettings) -> ChunkOutcome:
    version = chunking_version(settings)
    try:
        lines = body.replace("\r\n", "\n").replace("\r", "\n").removeprefix("\ufeff").split("\n")
        if not any(line.strip() for line in lines):
            return _empty(ChunkOutcomeKind.EMPTY, version)
        parsed = parse_document(lines)
        title = document_title(source_title, parsed.front_matter_title, parsed.blocks, location)
        drafts, split_count = [], 0
        for section in split_sections(parsed.blocks):
            header = search_header(location, title, section.heading_path)
            pieces, count = split_blocks(section.blocks, lines, header, settings)
            split_count += count
            for piece in pieces:
                text = "\n".join(lines[piece.start : piece.end])
                emb = embedding_text(header, piece.prefix, text)
                chunk = ChunkInput(
                    len(drafts),
                    {"path": location, "lines": [piece.start + 1, piece.end]},
                    text,
                    search_text(header, text, settings.keyword_text_rule),
                    version,
                    section.heading_path,
                )
                drafts.append(ChunkDraft(chunk, header, emb, estimated_tokens(emb, MODELS[settings.model_version])))
        return ChunkOutcome(
            ChunkOutcomeKind.CHUNKED,
            title,
            tuple(drafts),
            structure_warnings(parsed, lines),
            None,
            split_count,
            version,
        )
    except SplitFailure as exc:
        return _empty(ChunkOutcomeKind.FAILED, version, exc.kind)
    except Exception:
        return _empty(ChunkOutcomeKind.FAILED, version, ChunkFailureKind.PROCESSING_ERROR)


def chunk_screened(
    passed: Iterable[ScreenedContent], settings: ChunkingSettings, *, code: CodeChunkingSettings | None = None
) -> ChunkingResult:
    """Markdown은 그대로 Markdown 청커에, 코드 청킹이 켜져 있으면 `.java`·`.kt` 코드 자료만 코드 청커에 넘긴다."""
    if code is not None and code.model_version != settings.model_version:
        raise ValueError("코드 청킹 모델이 청킹 설정 모델과 다르다")
    version = chunking_version(settings)
    code_version = code_chunking_version(code, settings) if code is not None else None
    results = []
    for screened in passed:
        try:
            content = screened.content
            if content.content_format == ContentFormat.MARKDOWN:
                result = chunk_markdown(
                    content.body,
                    location=content.location,
                    source_title=content.title or screened.item.title,
                    settings=settings,
                )
            elif is_code_target(content, code):
                result = chunk_code(content.body, location=content.location, settings=settings, code=code)
            else:
                result = _empty(ChunkOutcomeKind.NOT_MARKDOWN, version)
        except Exception:
            result = _empty(ChunkOutcomeKind.FAILED, version, ChunkFailureKind.PROCESSING_ERROR)
        values = {f.name: getattr(result, f.name) for f in fields(ChunkOutcome)}
        results.append(ChunkedContent(screened=screened, **values))
    results = tuple(results)
    if not results:
        return ChunkingResult(results, ChunkingSummary.from_results(results))
    summary = ChunkingSummary.from_results(
        results, chunking_version=index_chunking_version(settings, code), code_chunking_version=code_version
    )
    return ChunkingResult(results, summary)

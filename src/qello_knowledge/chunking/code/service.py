"""코드 청킹 진입점(QK-CHK-001 contracts 5절). 외부 호출·저장·로그 출력이 없는 순수 함수다."""

from pathlib import PurePosixPath

from qello_knowledge.chunking.code.header import chunk_texts, search_header
from qello_knowledge.chunking.code.parse import blanked, first_error_line, has_error, parse
from qello_knowledge.chunking.code.split import Sizer, fallback_ranges, split_unit
from qello_knowledge.chunking.code.symbols import root_annotations, stray_root
from qello_knowledge.chunking.code.units import Builder
from qello_knowledge.chunking.code.version import code_chunking_version
from qello_knowledge.chunking.split import SplitFailure
from qello_knowledge.domain.chunking import (
    ChunkDraft,
    ChunkFailureKind,
    ChunkingSettings,
    ChunkOutcome,
    ChunkOutcomeKind,
    CodeChunkingSettings,
    CodeChunkKind,
    StructureWarning,
    StructureWarningKind,
)
from qello_knowledge.domain.embedding import MODELS
from qello_knowledge.domain.store import ChunkInput
from qello_knowledge.embedding.estimate import estimated_tokens

LANGUAGES = {".java": "java", ".kt": "kotlin"}


def _empty(kind, version, failure=None):
    return ChunkOutcome(kind, None, (), (), failure, 0, version)


def chunk_code(body: str, *, location: str, settings: ChunkingSettings, code: CodeChunkingSettings) -> ChunkOutcome:
    version = code_chunking_version(code, settings)
    try:
        text = body.replace("\r\n", "\n").replace("\r", "\n").removeprefix("﻿")
        lines = text.split("\n")
        if not any(line.strip() for line in lines):
            return _empty(ChunkOutcomeKind.EMPTY, version)
        language = LANGUAGES[PurePosixPath(location).suffix]
        src = text.encode("utf-8")
        tree, extra = parse(src, language), ()
        if language == "kotlin" and not has_error(tree):
            # 루트 어노테이션을 식으로 잘못 읽은 곳은 어노테이션을 지운 같은 길이 사본으로 다시 읽는다
            extra = root_annotations(tree, src)
            if extra:
                tree = parse(blanked(src, extra), language)
        stray = stray_root(tree) if language == "kotlin" and not has_error(tree) else None
        model = MODELS[code.model_version]
        sizer = Sizer(lines, model.bytes_per_token_estimate)

        def header_of(unit):
            return search_header(location, language, builder.package, unit.path, unit.kind, unit.meta["display_name"])

        def measure(unit, start, end):
            prefix = "\n".join(line for group in unit.context for line in group)
            return sizer.tokens(header_of(unit), prefix, start, end)

        builder = Builder(tree, src, lines, location, language, measure, code.target_tokens, extra)
        warnings = []
        if has_error(tree) or stray is not None:
            header = search_header(location, language, builder.package, (), CodeChunkKind.FALLBACK)
            units = builder.fallback(fallback_ranges(sizer, header, code.target_tokens))
            line = first_error_line(tree) if stray is None else stray + 1
            warnings.append(StructureWarning(StructureWarningKind.PARSE_FALLBACK, line))
        else:
            units = builder.units()
        drafts, split_count = [], 0
        for unit in units:
            header = header_of(unit)
            if unit.groups:
                rows = [row for group in unit.groups for row in group]
                ends, count = set(), 0
                for group in unit.groups[:-1]:
                    count += len(group)
                    ends.add(count - 1)
                own = Sizer([lines[row] for row in rows], model.bytes_per_token_estimate)
                pieces = split_unit(
                    own, 0, len(rows) - 1, header, unit.context, unit.repeat, ends,
                    limit=code.limit_tokens, target=code.target_tokens,
                )  # fmt: skip
                spans = [(unit.span[0], unit.span[1]) for _ in pieces]
                bodies = ["\n".join(own.lines[p.start : p.end + 1]) for p in pieces]
            else:
                pieces = split_unit(
                    sizer, unit.start, unit.end, header, unit.context, unit.repeat, unit.breaks,
                    limit=code.limit_tokens, target=code.target_tokens,
                )  # fmt: skip
                split_count += len(pieces) > 1
                spans = [(p.start, p.end) for p in pieces]
                bodies = ["\n".join(lines[p.start : p.end + 1]) for p in pieces]
            for piece, (first, last), chunk_body in zip(pieces, spans, bodies, strict=True):
                emb, keyword = chunk_texts(header, piece.context, piece.repeat, chunk_body, settings.keyword_text_rule)
                meta = {**unit.meta, "type_modifiers": list(unit.meta["type_modifiers"])}
                meta["annotations"] = list(unit.meta["annotations"])
                locator = {"path": location, "lines": [first + 1, last + 1], "code": meta}
                chunk = ChunkInput(len(drafts), locator, chunk_body, keyword, version, unit.path)
                drafts.append(ChunkDraft(chunk, header, emb, estimated_tokens(emb, model)))
                if piece.omitted:
                    warnings.append(StructureWarning(StructureWarningKind.CONTEXT_OMITTED, first + 1))
        return ChunkOutcome(
            ChunkOutcomeKind.CHUNKED,
            PurePosixPath(location).name,
            tuple(drafts),
            tuple(sorted(warnings, key=lambda w: (w.line, w.kind))),
            None,
            split_count,
            version,
        )
    except SplitFailure as exc:
        return _empty(ChunkOutcomeKind.FAILED, version, exc.kind)
    except Exception:
        return _empty(ChunkOutcomeKind.FAILED, version, ChunkFailureKind.PROCESSING_ERROR)

"""절 안의 탐욕 쌓기와 큰 블록의 재귀 분할(research R-08)."""

from dataclasses import dataclass, replace

from qello_knowledge.chunking.blocks import Block
from qello_knowledge.chunking.header import embedding_text
from qello_knowledge.domain.chunking import ChunkFailureKind, ChunkingSettings
from qello_knowledge.domain.embedding import MODELS
from qello_knowledge.embedding.estimate import estimated_tokens


class SplitFailure(Exception):
    def __init__(self, kind: ChunkFailureKind):
        self.kind = kind
        super().__init__(kind.value)


@dataclass(frozen=True)
class Piece:
    start: int
    end: int
    prefix: str = ""


def split_blocks(
    blocks: tuple[Block, ...], lines: list[str], header: str, settings: ChunkingSettings
) -> tuple[tuple[Piece, ...], int]:
    model = MODELS[settings.model_version]
    if estimated_tokens(header, model) >= settings.limit_tokens:
        raise SplitFailure(ChunkFailureKind.HEADER_TOO_LONG)

    def trim(start, end, prefix=""):
        while start < end and not lines[start].strip():
            start += 1
        while end > start and not lines[end - 1].strip():
            end -= 1
        return Piece(start, end, prefix)

    def size(piece):
        return estimated_tokens(embedding_text(header, piece.prefix, "\n".join(lines[piece.start : piece.end])), model)

    def divide(block):
        if block.children:
            # 자식 사이의 줄은 다음 자식에, 끝에 남은 줄은 마지막 자식에 붙인다.
            units, cursor = [], block.start
            for i, child in enumerate(block.children):
                end = block.end if i == len(block.children) - 1 else child.end
                units.append(replace(child, start=cursor, end=end))
                cursor = child.end
            return pack(units)
        pieces, start = [], block.start
        while start < block.end:
            prefix = block.prefix if start > block.start else ""
            end = start
            while end < block.end and size(trim(start, end + 1, prefix)) <= settings.limit_tokens:
                end += 1
            if end == start:
                raise SplitFailure(ChunkFailureKind.LINE_TOO_LONG)
            piece = trim(start, end, prefix)
            if piece.start < piece.end:
                pieces.append(piece)
            start = end
        return pieces

    def pack(units):
        result, current = [], None
        for block in units:
            whole = trim(block.start, block.end)
            if size(whole) > settings.limit_tokens:
                if current:
                    result.append(current)
                    current = None
                result.extend(divide(block))
                continue
            candidate = trim(current.start, block.end) if current else whole
            if current and size(candidate) > settings.target_tokens:
                result.append(current)
                current = whole
            else:
                current = candidate
        if current:
            result.append(current)
        return result

    split_count = sum(size(trim(b.start, b.end)) > settings.limit_tokens for b in blocks)
    return tuple(pack(blocks)), split_count

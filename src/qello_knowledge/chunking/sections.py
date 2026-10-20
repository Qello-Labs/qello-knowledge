"""최상위 제목마다 절을 만들며 실제 존재하는 제목만 경로에 남긴다."""

from dataclasses import dataclass
from pathlib import PurePosixPath

from qello_knowledge.chunking.blocks import Block


@dataclass(frozen=True)
class Section:
    heading_path: tuple[str, ...]
    blocks: tuple[Block, ...]


def split_sections(blocks: tuple[Block, ...]) -> tuple[Section, ...]:
    result, current, stack = [], [], []
    for block in blocks:
        if block.kind == "heading":
            if current:
                result.append(Section(tuple(text for _, text in stack), tuple(current)))
            current = []
            while stack and stack[-1][0] >= block.level:
                stack.pop()
            stack.append((block.level, block.text))
        current.append(block)
    if current:
        result.append(Section(tuple(text for _, text in stack), tuple(current)))
    return tuple(result)


def document_title(source_title, front_matter_title, blocks, location) -> str:
    first = next((b.text for b in blocks if b.kind == "heading" and b.level == 1 and b.text.strip()), None)
    return next(
        value.strip()
        for value in (source_title, front_matter_title, first, PurePosixPath(location).name)
        if value and value.strip()
    )

"""상한 초과 나누기·맥락 줄 생략·실패 판정과 대체 청킹 묶음(spec FR-016~019, research R-05·R-07).

크기는 임베딩 입력(검색 헤더 + 맥락 줄 + 반복 줄 + 본문)의 예상 토큰이다(QK-CHK-002와 같은 정의).
"""

import math
from dataclasses import dataclass

from qello_knowledge.chunking.split import SplitFailure
from qello_knowledge.domain.chunking import ChunkFailureKind


class Sizer:
    """줄 목록의 예상 토큰을 누적 바이트로 센다. `embedding_text` 결과의 `estimated_tokens`와 같은 값이다."""

    def __init__(self, lines: list[str], bytes_per_token: float):
        self.lines, self.bytes_per_token = lines, bytes_per_token
        self.offsets = [0]
        for line in lines:
            self.offsets.append(self.offsets[-1] + len(line.encode("utf-8")))

    def blank(self, row: int) -> bool:
        return not self.lines[row].strip()

    def tokens(self, header: str, prefix: str, start: int, end: int) -> int:
        size = len(header.encode("utf-8")) + 2 + (len(prefix.encode("utf-8")) + 1 if prefix else 0)
        return math.ceil((size + self.offsets[end + 1] - self.offsets[start] + end - start) / self.bytes_per_token)


@dataclass(frozen=True)
class Piece:
    start: int
    end: int
    context: tuple[str, ...]  # 붙인 맥락 줄(생략하고 남은 것)
    repeat: tuple[str, ...]  # 뒤 조각에 붙인 반복 줄
    omitted: bool


def split_unit(sizer, start, end, header, contexts, repeat, breaks, *, limit, target) -> list[Piece]:
    """`start`~`end` 줄을 상한 안의 조각으로 나눈다. `contexts`는 맥락 줄 묶음(바깥 형식부터)이다."""
    if math.ceil(len(header.encode("utf-8")) / sizer.bytes_per_token) >= limit:
        raise SplitFailure(ChunkFailureKind.HEADER_TOO_LONG)
    pieces, first = [], start
    while first <= end:
        if sizer.blank(first):
            first += 1
            continue
        kept, omitted = contexts, False
        while True:
            lines = tuple(line for group in kept for line in group)
            repeated = repeat if first > start and (not kept or kept[-1] != repeat) else ()
            prefix = "\n".join([*lines, *repeated])
            if sizer.tokens(header, prefix, first, first) <= limit:
                break
            if not kept:
                raise SplitFailure(ChunkFailureKind.LINE_TOO_LONG)
            kept, omitted = kept[1:], True  # 바깥 형식부터 뺀다(spec FR-018)

        def size(last, prefix=prefix, first=first):
            return sizer.tokens(header, prefix, first, last)

        if size(end) <= limit:
            last = end
        else:
            fit = first
            while fit < end and size(fit + 1) <= limit:
                fit += 1
            # 목표 크기 이하인 마지막 후보, 없으면 목표를 처음 넘는 후보. 후보는 최상위 문장 끝, 없으면 모든 줄이다
            candidates = [row for row in sorted(breaks) if first <= row <= fit] or list(range(first, fit + 1))
            under = [row for row in candidates if size(row) <= target]
            last = under[-1] if under else candidates[0]
        stop = last
        while sizer.blank(stop):
            stop -= 1
        pieces.append(Piece(first, stop, lines, repeated, omitted))
        first = last + 1
    return pieces


def fallback_ranges(sizer, header, target) -> list[tuple[int, int]]:
    """빈 줄로 나뉜 블록을 원문 순서로 쌓아 목표 크기에서 끊는다(spec FR-019). 큰 블록은 `split_unit`이 나눈다."""
    blocks, row = [], 0
    while row < len(sizer.lines):
        if sizer.blank(row):
            row += 1
            continue
        start = row
        while row < len(sizer.lines) and not sizer.blank(row):
            row += 1
        blocks.append((start, row - 1))
    groups = []
    for start, end in blocks:
        if groups and sizer.tokens(header, "", groups[-1][0], end) <= target:
            groups[-1] = (groups[-1][0], end)
        else:
            groups.append((start, end))
    return groups

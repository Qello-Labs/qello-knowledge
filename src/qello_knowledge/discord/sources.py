"""자료원 요약 하나를 Discord 메시지 한도 안에서 표시한다."""

from datetime import timedelta, timezone

from qello_knowledge.discord.notices import RETRIEVAL_NOTICES
from qello_knowledge.discord.render import neutralize
from qello_knowledge.domain.retrieval import RetrievalFailure

KST = timezone(timedelta(hours=9))
KINDS = {"github_repo_files": "저장소 파일", "confluence_pages": "Confluence 페이지"}


def _stamp(value):
    return value.astimezone(KST).strftime("%Y-%m-%d %H:%M KST") if value else "확인 불가"


def render_sources(view):
    if view.index_version is None:
        return RETRIEVAL_NOTICES[RetrievalFailure.NO_ACTIVE_INDEX]
    header = f"자료 기준: 인덱스 {neutralize(view.index_version)} (활성화 {_stamp(view.activated_at)})"
    lines = [
        f"- {neutralize(source.name)} · {neutralize(KINDS.get(source.kind, source.kind))} · "
        f"문서 {source.documents}개 · 마지막 확인 {_stamp(source.last_seen_at)}"
        for source in view.sources
    ]
    used = []
    for index, line in enumerate(lines):
        rest = len(lines) - index - 1
        suffix = [f"(자료원 {rest}개 더 있음)"] if rest else []
        if len("\n".join([header, *used, line, *suffix])) > 2000:
            break
        used.append(line)
    if len(used) < len(lines):
        used.append(f"(자료원 {len(lines) - len(used)}개 더 있음)")
    return "\n".join([header, *used])

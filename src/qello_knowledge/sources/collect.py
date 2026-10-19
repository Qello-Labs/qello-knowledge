"""페이지 순회, 중복 제거와 범위 적용은 자료원과 독립적으로 수행한다."""

from qello_knowledge.domain.scope import in_scope
from qello_knowledge.domain.source import Listing
from qello_knowledge.domain.source_config import SourceConfig
from qello_knowledge.ports.source import SourceAdapter, SourceSession


def list_all(adapter: SourceAdapter, config: SourceConfig, session: SourceSession) -> Listing:
    items = []
    seen = set()
    duplicates = excluded = 0
    cursor = None
    while True:
        page = adapter.list_page(session, config, cursor)
        for item in page.items:
            if item.source_id in seen:
                duplicates += 1
                continue
            seen.add(item.source_id)
            if not in_scope(item.location, config.scope.include, config.scope.exclude):
                excluded += 1
                continue
            items.append(item)
        cursor = page.next_cursor
        if cursor is None:
            return Listing(tuple(items), duplicates, True, excluded)

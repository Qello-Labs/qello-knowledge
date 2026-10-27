"""코드 메타데이터(QK-CHK-001 data-model `locator["code"]`, spec SC-006, US3, tasks T024).

T023 픽스처의 값 비교는 `test_code_expected.py`가 한다. 여기서는 모든 픽스처 결과의 키·형태와 오버로드 구분을 본다.
"""

import json

import pytest

from qello_knowledge.domain.chunking import ChunkOutcomeKind
from tests.unit.chunking.code.helpers import FIXTURES, cases, run
from tests.unit.chunking.code.test_code_expected import CODE_KEYS

CASES = list(cases())


@pytest.mark.parametrize(("name", "body", "case"), CASES, ids=[c[0] for c in CASES])
def test_every_chunk_has_all_keys_as_plain_json(name, body, case):
    result = run(body, case)
    for draft in result.drafts:
        locator = draft.chunk.locator
        assert type(locator) is dict and set(locator) == {"path", "lines", "code"}
        assert type(locator["code"]) is dict and tuple(locator["code"]) == CODE_KEYS
        assert json.loads(json.dumps(locator)) == locator
        code = locator["code"]
        lists, flags = ("type_modifiers", "annotations"), ("test_code", "test_method", "summary")
        assert all(type(code[k]) is str for k in CODE_KEYS if k not in lists + flags)
        assert all(type(code[k]) is list and all(type(v) is str for v in code[k]) for k in lists)
        assert all(type(code[k]) is bool for k in flags)
        assert draft.chunk.heading_path == tuple(draft.chunk.heading_path)


def test_consecutive_overloads_have_different_paths():
    body = (FIXTURES / "java_metadata.java").read_text(encoding="utf-8")
    result = run(body, {"input": {"location": "src/main/java/com/acme/meta/Finder.java"}})
    assert result.outcome == ChunkOutcomeKind.CHUNKED
    finds = [
        d.chunk.heading_path for d in result.drafts if d.chunk.heading_path[-1:] in (("find(Long)",), ("find(String)",))
    ]
    assert finds == [("Finder", "find(Long)"), ("Finder", "find(String)")]


def test_chunks_do_not_share_mutable_metadata():
    body = (FIXTURES / "java_metadata.java").read_text(encoding="utf-8")
    first, second = run(body, {"input": {"location": "src/main/java/com/acme/meta/Finder.java"}}).drafts[1:3]
    first.chunk.locator["code"]["annotations"].append("Changed")
    assert second.chunk.locator["code"]["annotations"] == ["Component"]

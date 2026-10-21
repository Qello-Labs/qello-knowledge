import pytest

from qello_knowledge.chunking import chunk_screened, service
from qello_knowledge.domain.chunking import ChunkingSettings
from tests.unit.chunking.helpers import screened

MARKER = "QK-CHK-002-LEAK-MARKER"


@pytest.mark.parametrize("case", ["success", "empty", "line", "header", "processing", "warning"])
def test_results_and_logs_hide_body(case, monkeypatch, caplog):
    body = "# " + MARKER
    location = "a.md"
    if case == "empty":
        body = " \n\t"
    elif case == "line":
        body = MARKER * 1000
    elif case == "header":
        location = "a" * 10000
    elif case == "processing":

        def broken(*a, **kw):
            raise ValueError(MARKER)

        monkeypatch.setattr(service, "parse_document", broken)
    elif case == "warning":
        body = "```\n" + MARKER
    result = chunk_screened([screened(body, title=MARKER, location=location)], ChunkingSettings())
    expected = {
        "success": "CHUNKED",
        "empty": "EMPTY",
        "line": "FAILED",
        "header": "FAILED",
        "processing": "FAILED",
        "warning": "CHUNKED",
    }
    assert result.results[0].outcome == expected[case]
    assert MARKER not in repr(result)
    assert MARKER not in repr(result.summary)
    assert MARKER not in repr(result.results[0].warnings)
    assert MARKER not in caplog.text

import json
from dataclasses import replace
from pathlib import Path

from qello_knowledge.adapters.fake import FakeSourceAdapter
from qello_knowledge.domain.chunking import ChunkingSettings
from qello_knowledge.domain.security import AccessScope, ScreenedContent
from qello_knowledge.domain.source import SourceResponse
from qello_knowledge.domain.source_config import SourceConfig

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "chunking"


def cases():
    for path in sorted(FIXTURES.glob("*.expected.json")):
        case = json.loads(path.read_text())
        yield (
            path.stem.removesuffix(".expected"),
            path.with_name(path.name.replace(".expected.json", ".md")).read_text(),
            case,
        )


def kwargs(case):
    inputs = dict(case["input"])
    inputs["settings"] = ChunkingSettings(**inputs.get("settings", {}))
    return inputs


def screened(body, *, content_format="MARKDOWN", title=None, item_title=None, location="docs/sample.md", kind="fake"):
    """Create values via the real fake adapter with an in-memory response only."""
    adapter = FakeSourceAdapter()

    class Session:
        def send(self, request):
            data = dict(body=body, content_format=content_format, version="v1", location=location, title=title)
            return SourceResponse(200, {}, json.dumps(data).encode())

    session = Session()
    item = adapter._item(
        session,
        SourceConfig("synthetic", "fake", True),
        dict(
            id="sample",
            version="v1",
            location="listing/location.md",
            title=item_title,
            url="https://example.invalid/synthetic",
            item_type="page",
            access={"visibility": "team"},
        ),
    )
    content = adapter.fetch_content(session, None, item)
    return ScreenedContent(replace(item, source_kind=kind), content, AccessScope.TEAM, "sec-synthetic")

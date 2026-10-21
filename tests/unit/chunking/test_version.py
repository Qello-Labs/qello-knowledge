from dataclasses import replace

import pytest

from qello_knowledge.chunking import version
from qello_knowledge.domain.chunking import ChunkingSettings
from qello_knowledge.domain.embedding import MODELS


def test_first_version():
    assert version.chunking_version(ChunkingSettings()) == "chk-md-20d966f730bb"
    assert version.chunking_version(ChunkingSettings()) == version.chunking_version(ChunkingSettings())


@pytest.mark.parametrize(
    "name",
    [
        "RULES_REVISION",
        "HEADER_FORMAT",
        "SEARCH_TEXT_FORMAT",
        "EMBEDDING_INPUT_FORMAT",
        "PARSER_VERSION",
        "target_tokens",
        "limit_tokens",
        "model_version",
    ],
)
def test_version_materials(monkeypatch, name):
    settings = ChunkingSettings()
    old = version.chunking_version(settings)
    if name == "model_version":
        monkeypatch.setitem(MODELS, "test-model", replace(MODELS[settings.model_version], model_version="test-model"))
        settings = replace(settings, model_version="test-model")
    elif name in ("target_tokens", "limit_tokens"):
        settings = replace(settings, **{name: getattr(settings, name) - 1})
    else:
        monkeypatch.setattr(version, name, "different" if name == "PARSER_VERSION" else 2)
    assert version.chunking_version(settings) != old

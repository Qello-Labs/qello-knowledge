from pathlib import Path

from qello_knowledge.config.example import render

ROOT = Path(__file__).resolve().parents[3]


def test_env_example_matches_registry() -> None:
    saved = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert saved == render(), "레지스트리가 바뀌었다. `uv run python -m qello_knowledge.config.example`로 다시 만든다"

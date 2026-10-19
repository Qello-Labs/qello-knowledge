import pytest

from qello_knowledge.domain.scope import in_scope


@pytest.mark.parametrize(
    ("location", "pattern", "expected"),
    [
        ("docs/a.md", "**/*.md", True),
        ("a.md", "**/*.md", True),
        ("docs/x/y.md", "docs/**", True),
        ("docs/x/y.md", "docs/*", False),
        (".github/a.md", "**/*.md", True),
        ("Docs/A.MD", "**/*.md", False),
    ],
)
def test_full_path_matching(location, pattern, expected):
    assert in_scope(location, (pattern,), ()) is expected


def test_exclusion_wins_overlap():
    assert not in_scope("docs/a.md", ("**/*.md",), ("docs/**",))
    assert not in_scope("a.py", ("**/*.md",), ())


def test_empty_include_rejected():
    with pytest.raises(ValueError):
        in_scope("a.md", (), ())

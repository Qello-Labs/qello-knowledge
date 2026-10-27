"""비활성 코드 자료원 두 개(QK-CHK-001 spec SC-013, FR-032·033·036, research R-13, tasks T039).

저장소의 실제 `config/sources.toml`을 읽는다. 원본 호출이 없다.
"""

import tomllib
from pathlib import Path

from qello_knowledge.sources.config import load_sources
from qello_knowledge.sources.scope_review import load_checked_sources
from qello_knowledge.sync.identity import select_targets
from qello_knowledge.sync.plan import SyncTarget

ROOT = Path(__file__).resolve().parents[3]
SOURCES = ROOT / "config" / "sources.toml"
REVIEWS = ROOT / "config" / "source_reviews"
EXPECTED = {
    "dnd-backend-code": ("dnd-side-project/dnd-15th-2-backend", ["src/main/java/**/*.java"]),
    "dnd-android-code": (
        "dnd-side-project/dnd-15th-2-android",
        [
            "app/src/main/**/*.kt",
            "data/src/main/**/*.kt",
            "domain/src/main/**/*.kt",
            "presentation/src/main/**/*.kt",
        ],
    ),
}


def raw_sources():
    return {row["name"]: row for row in tomllib.loads(SOURCES.read_text(encoding="utf-8"))["source"]}


def test_code_sources_are_registered_disabled():
    rows = raw_sources()
    for name, (repo, include) in EXPECTED.items():
        row = rows[name]
        assert (row["kind"], row["enabled"], row["auth"]) == ("github_repo_files", False, "GITHUB_API_TOKEN")
        assert row["scope"] == {"repo": repo, "ref": "main", "include": include}
        assert "limits" not in row and "retry" not in row


def test_config_check_passes_and_checks_disabled_includes(tmp_path):
    _, issues = load_checked_sources(SOURCES, REVIEWS)
    assert issues == ()
    # 비활성 항목의 include가 정말 되살아나 검사되는지: 알 수 없는 확장자를 넣으면 걸려야 한다
    broken = SOURCES.read_text(encoding="utf-8").replace('"src/main/java/**/*.java"', '"src/main/java/**/*.zzz"')
    path = tmp_path / "sources.toml"
    path.write_text(broken, encoding="utf-8")
    _, issues = load_checked_sources(path, REVIEWS)
    assert [(i.source, i.field, i.code) for i in issues] == [
        ("dnd-backend-code", "scope.include[0]", "UNKNOWN_EXTENSION")
    ]


def test_enabled_copy_has_no_config_errors(tmp_path):
    text = SOURCES.read_text(encoding="utf-8")
    for name in EXPECTED:
        text = text.replace(
            f'name = "{name}"\nkind = "github_repo_files"\nenabled = false',
            f'name = "{name}"\nkind = "github_repo_files"\nenabled = true',
        )
    path = tmp_path / "sources.toml"
    path.write_text(text, encoding="utf-8")
    configs, issues = load_sources(path)
    assert {c.name for c in configs if c.enabled} >= set(EXPECTED)
    assert issues == ()
    _, checked = load_checked_sources(path, REVIEWS)
    assert {(i.source, i.code) for i in checked} == {(name, "REVIEW_MISSING") for name in EXPECTED}


def test_same_repository_sources_do_not_overlap():
    rows = raw_sources()
    pairs = [
        (a, b)
        for a in rows
        for b in rows
        if a < b and rows[a].get("scope", {}).get("repo") == rows[b].get("scope", {}).get("repo")
    ]
    assert pairs == [("dnd-backend-code", "dnd-backend-docs")]

    def extensions(name):
        return {pattern.rsplit(".", 1)[-1] for pattern in rows[name]["scope"]["include"]}

    assert extensions("dnd-backend-code") == {"java"}
    assert not extensions("dnd-backend-code") & extensions("dnd-backend-docs")


def test_backend_docs_scope_matches_its_review():
    docs = raw_sources()["dnd-backend-docs"]["scope"]
    review = tomllib.loads((REVIEWS / "dnd-backend-docs.toml").read_text(encoding="utf-8"))["scope"]
    assert docs == review


def test_disabled_code_sources_are_not_sync_targets():
    configs, _ = load_sources(SOURCES)
    targets = [SyncTarget(c.name, c.kind, config=c) for c in configs]
    assert [t.source_name for t in select_targets(targets, {})] == ["dnd-backend-docs"]

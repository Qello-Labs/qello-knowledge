import re

from qello_knowledge.sync.keys import chunk_input_hash, doc_key, index_version_id, scope_key


def test_input_fingerprint_uses_content_location_and_title_only():
    base = chunk_input_hash("hash", "docs/a.md", "Title")
    assert (
        len(
            {
                base,
                chunk_input_hash("other", "docs/a.md", "Title"),
                chunk_input_hash("hash", "docs/b.md", "Title"),
                chunk_input_hash("hash", "docs/a.md", "Other"),
            }
        )
        == 4
    )
    assert chunk_input_hash("hash", "p", None) == chunk_input_hash("hash", "p", "")
    assert re.fullmatch("[a-f0-9]{64}", base)


def test_doc_key_is_namespaced_and_full_sha256():
    keys = {
        doc_key("name", "kind", "id"),
        doc_key("other", "kind", "id"),
        doc_key("name", "other", "id"),
        doc_key("name", "kind", "other"),
    }
    assert len(keys) == 4
    assert all(re.fullmatch("[a-f0-9]{64}", key) for key in keys)


def test_index_version_matches_approved_first_value_and_each_material_matters():
    args = ["@cf/baai/bge-m3", 1024, "chk-md-20d966f730bb", "meta-v1"]
    assert index_version_id(*args) == "iv-4c0bc4fcc642"
    for i in range(4):
        changed = args.copy()
        changed[i] = str(changed[i]) + "-changed"
        assert index_version_id(*changed) != "iv-4c0bc4fcc642"


def test_github_scope_normalizes_identity_but_not_patterns():
    assert scope_key("github_repo_files", repo="Owner/Repo", ref="Main") == "github_repo_files:owner/repo@main"


def test_scope_key_accepts_the_common_source_scope_value():
    from qello_knowledge.domain.source_config import SourceScope

    scope = SourceScope(("**/*.md",), ("private/**",), (("repo", "Owner/Repo"), ("ref", "Main")))
    assert scope_key("github_repo_files", scope) == "github_repo_files:owner/repo@main"


def test_input_fingerprint_extra_is_optional_and_only_changes_when_given():
    base = chunk_input_hash("hash", "docs/a.md", "Title")
    assert chunk_input_hash("hash", "docs/a.md", "Title", extra=None) == base
    with_extra = chunk_input_hash("hash", "docs/a.md", "Title", extra='{"rules":"adf-md-v1"}')
    assert with_extra != base
    assert with_extra != chunk_input_hash("hash", "docs/a.md", "Title", extra='{"rules":"adf-md-v2"}')
    assert re.fullmatch("[a-f0-9]{64}", with_extra)


def test_confluence_scope_key_uses_space_id():
    from qello_knowledge.domain.source_config import SourceScope

    scope = SourceScope(("**",), (), (("space_id", "12345"), ("space_key", "SCRUM")))
    assert scope_key("confluence_pages", scope) == "confluence_pages:12345"
    renamed = SourceScope(("**",), (), (("space_id", "12345"), ("space_key", "NEW")))
    assert scope_key("confluence_pages", renamed) == "confluence_pages:12345"


def test_confluence_scope_key_requires_space_id():
    import pytest

    from qello_knowledge.domain.source_config import SourceScope

    with pytest.raises(ValueError):
        scope_key("confluence_pages", SourceScope(("**",), (), (("space_id", ""), ("space_key", "SCRUM"))))


def test_metadata_schema_version_combines_code_and_confluence():
    from qello_knowledge.sync.keys import metadata_schema_version

    code = object()
    assert metadata_schema_version() == "meta-v1"
    assert metadata_schema_version(code) == "meta-v2"
    assert metadata_schema_version(None, confluence=False) == "meta-v1"
    assert metadata_schema_version(None, confluence=True) == "meta-v1+cf1"
    assert metadata_schema_version(code, confluence=True) == "meta-v2+cf1"

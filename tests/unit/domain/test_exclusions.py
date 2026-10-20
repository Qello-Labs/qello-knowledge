"""기본 제외 규칙(research R-04, FR-006·008)."""

import pytest

from qello_knowledge.domain.exclusions import CATEGORIES, DEFAULT_EXCLUSIONS, excluded_by, normalize_location


@pytest.mark.parametrize(
    ("location", "category"),
    [
        (".env", "env-file"),
        ("config/.env.production", "env-file"),
        ("deploy/id_rsa", "private-key-file"),
        ("certs/server.pem", "private-key-file"),
        ("secrets/db.txt", "secret-dir"),
        ("infra/terraform.tfstate", "infra-state"),
        ("infra/terraform.tfstate.backup", "infra-state"),
        ("infra/terraform.tfstate.example", "infra-state"),
        ("infra/prod.tfvars", "infra-state"),
        ("infra/.terraform/config.sample", "infra-state"),
        ("web/node_modules/a.md", "build-output"),
        ("app/build/x.md", "build-output"),
        (".git/config", "vcs-internal"),
        (".ENV", "env-file"),
        ("./docs/../.ENV", "env-file"),
        ("../outside.md", "path-invalid"),
        ("/etc/passwd", "path-invalid"),
    ],
)
def test_excluded_locations(location, category):
    assert excluded_by(location) == category


@pytest.mark.parametrize(
    "location",
    [
        ".env.example",
        ".env.sample",
        "config/.env.template",
        "infra/prod.tfvars.example",
        "docs/1.md",
        "docs/building.md",
    ],
)
def test_kept_locations(location):
    assert excluded_by(location) is None


def test_categories_and_normalization():
    assert CATEGORIES == (
        "env-file",
        "private-key-file",
        "secret-dir",
        "infra-state",
        "build-output",
        "vcs-internal",
        "path-invalid",
    )
    assert {e.category for e in DEFAULT_EXCLUSIONS} == set(CATEGORIES) - {"path-invalid"}
    assert normalize_location("./docs//a/../b.md") == "docs/b.md"

"""보안 규칙 버전(FR-022, research R-08). 판정을 바꿀 수 있는 입력 하나만 바뀌어도 버전이 바뀐다."""

import re
from dataclasses import replace

import pytest

from qello_knowledge.domain.exclusions import DEFAULT_EXCLUSIONS, DefaultExclusion
from qello_knowledge.domain.redact import AddressPolicy
from qello_knowledge.domain.secret_rules import RULES, SecretRule
from qello_knowledge.security.exceptions import SecretException
from qello_knowledge.security.kinds import KINDS
from qello_knowledge.security.policy import SecurityPolicy

BASE = SecurityPolicy()
FAKE = KINDS["fake"]


def test_same_policy_same_version():
    assert re.fullmatch(r"sec-[0-9a-f]{12}", BASE.version)
    assert SecurityPolicy().version == BASE.version


@pytest.mark.parametrize(
    "changed",
    [
        SecurityPolicy(rules=(*RULES, SecretRule("extra", re.compile("x{40}")))),
        SecurityPolicy(exclusions=(*DEFAULT_EXCLUSIONS, DefaultExclusion("extra", "**/*.bak"))),
        SecurityPolicy(exceptions=frozenset({SecretException("docs", "a.md", "github-token", "r")})),
        SecurityPolicy(address_policy=AddressPolicy(file_extensions=AddressPolicy().file_extensions | {"adoc2"})),
        SecurityPolicy(address_policy=AddressPolicy(version="address-v99")),
        SecurityPolicy(kinds={**KINDS, "fake": replace(FAKE, rule_name="fake-visibility-v2")}),
        SecurityPolicy(kinds={**KINDS, "fake": replace(FAKE, public_link_hosts=("other.invalid",))}),
        SecurityPolicy(kinds={**KINDS, "fake": replace(FAKE, source_id_is_path=True)}),
    ],
    ids=["rules", "exclusions", "exceptions", "extensions", "address-version", "rule-name", "hosts", "id-is-path"],
)
def test_any_single_change_changes_version(changed):
    assert changed.version != BASE.version

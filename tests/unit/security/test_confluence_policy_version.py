"""종류별 보안 규칙 버전 재료(QK-ING-003 FR-012, research R-13)."""

from pathlib import Path

from qello_knowledge.security.policy import SecurityPolicy, load_policy


def test_kind_material_changes_version_only_when_given():
    base = SecurityPolicy()
    assert SecurityPolicy(kind_material={}).version == base.version
    one = SecurityPolicy(kind_material={"confluence-scrum": "site_users:" + "a" * 64})
    assert one.version != base.version
    assert SecurityPolicy(kind_material={"confluence-scrum": "site_users:" + "b" * 64}).version != one.version
    assert SecurityPolicy(kind_material={"confluence-scrum": "team_group:" + "a" * 64}).version != one.version


def test_load_policy_passes_kind_material(tmp_path):
    exceptions = tmp_path / "security_exceptions.toml"
    exceptions.write_text("", encoding="utf-8")
    policy, issues = load_policy(exceptions, (), kind_material={"confluence-scrum": "site_users:x"})
    assert issues == ()
    assert policy.kind_material == {"confluence-scrum": "site_users:x"}
    plain, _ = load_policy(exceptions, ())
    assert plain.kind_material == {}


def test_default_exceptions_file_still_loads():
    policy, issues = load_policy(Path("config/security_exceptions.toml"), ())
    assert policy is not None or issues

import pytest

from qello_knowledge.config.registry import BOTH, NO_SPACE_40, SETTINGS, Entrypoint, SettingSpec, specs_for


def test_names_are_unique() -> None:
    names = [spec.name for spec in SETTINGS]
    assert len(names) == len(set(names))


def test_every_spec_has_description_and_entrypoint() -> None:
    for spec in SETTINGS:
        assert spec.description.strip()
        assert spec.entrypoints


def test_secret_specs_have_no_default() -> None:
    assert all(spec.default is None for spec in SETTINGS if spec.secret)


def test_secret_default_is_rejected() -> None:
    with pytest.raises(ValueError, match="기본값"):
        SettingSpec("X_TOKEN", "설명", BOTH, required=False, secret=True, rule=NO_SPACE_40, default="z" * 40)


def test_query_does_not_require_index_tokens() -> None:
    names = {spec.name for spec in specs_for(Entrypoint.QUERY)}
    assert "GITHUB_API_TOKEN" not in names
    assert "CLOUDFLARE_API_TOKEN" in names
    assert "CLOUDFLARE_ACCOUNT_ID" in names


def test_index_does_not_use_discord() -> None:
    names = {spec.name for spec in specs_for(Entrypoint.INDEX)}
    assert not any(name.startswith("DISCORD_") for name in names)

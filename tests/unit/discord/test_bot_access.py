import pytest

from qello_knowledge.discord.access import AccessPolicy
from qello_knowledge.discord.interactions import parse
from qello_knowledge.domain.discord import AccessDecision
from tests.unit.discord.bot_builders import CHANNEL, GUILD, ROLE, ask


@pytest.mark.parametrize(
    "changes,decision",
    [
        ({}, AccessDecision.ALLOWED),
        ({"guild": "8" * 18}, AccessDecision.GUILD_OUTSIDE),
        ({"channel": "8" * 18}, AccessDecision.CHANNEL_OUTSIDE),
        ({"channel_type": 10}, AccessDecision.THREAD),
        ({"channel_type": 11}, AccessDecision.THREAD),
        ({"channel_type": 12}, AccessDecision.THREAD),
        ({"guild": None}, AccessDecision.DM),
        ({"channel_type": 15}, AccessDecision.CHANNEL_OUTSIDE),
    ],
)
def test_bot_access_decisions(changes, decision):
    policy = AccessPolicy(GUILD, (CHANNEL,))
    assert policy.check(parse(ask("합성 질문", **changes))) is decision


def test_bot_roles_and_fail_closed_configuration():
    item = parse(ask("합성 질문"))
    assert AccessPolicy(GUILD, (CHANNEL,), (ROLE,)).check(item) is AccessDecision.ROLE_MISSING
    assert (
        AccessPolicy(GUILD, (CHANNEL,), (ROLE,)).check(parse(ask("합성 질문", roles=(ROLE,)))) is AccessDecision.ALLOWED
    )
    assert AccessPolicy(None, (CHANNEL,)).check(item) is AccessDecision.NOT_CONFIGURED
    assert AccessPolicy(GUILD, ()).check(item) is AccessDecision.NOT_CONFIGURED

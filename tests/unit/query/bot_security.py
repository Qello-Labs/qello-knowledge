from qello_knowledge.discord.access import AccessPolicy
from qello_knowledge.indexer.embedding import security_outgoing_check
from qello_knowledge.security.policy import SecurityPolicy
from tests.unit.discord.bot_builders import CHANNEL, GUILD
from tests.unit.query.bot_runtime import bot_runtime


def bot_secured_runtime(*, channels=(CHANNEL,), guild=GUILD, roles=(), **options):
    runtime = bot_runtime(**options)
    policy = AccessPolicy(guild, channels, roles)
    check = security_outgoing_check(SecurityPolicy())
    runtime.app.access_check = policy.check
    runtime.app.outgoing_check = lambda item: not check(item.question or "", None)
    return runtime

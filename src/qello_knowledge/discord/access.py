"""서버 하나·글 채널·선택 역할의 허용 범위. 구성되지 않았으면 닫는다."""

from dataclasses import dataclass

from qello_knowledge.domain.discord import AccessDecision, ChannelKind, Interaction


@dataclass(frozen=True)
class AccessPolicy:
    guild_id: str | None
    channels: tuple[str, ...]
    roles: tuple[str, ...] = ()

    def check(self, interaction: Interaction) -> AccessDecision:
        if not self.guild_id or not self.channels:
            return AccessDecision.NOT_CONFIGURED
        if interaction.channel_kind is ChannelKind.DM:
            return AccessDecision.DM
        if interaction.guild_id != self.guild_id:
            return AccessDecision.GUILD_OUTSIDE
        if interaction.channel_kind is ChannelKind.THREAD:
            return AccessDecision.THREAD
        if interaction.channel_kind is not ChannelKind.TEXT or interaction.channel_id not in self.channels:
            return AccessDecision.CHANNEL_OUTSIDE
        if self.roles and not set(self.roles).intersection(interaction.member_roles):
            return AccessDecision.ROLE_MISSING
        return AccessDecision.ALLOWED

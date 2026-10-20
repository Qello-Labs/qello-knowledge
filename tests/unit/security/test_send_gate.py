"""전송 직전 검사(FR-013, SC-002, SC-009). 출처가 확정된 조각에만 예외를 적용한다."""

import logging

from qello_knowledge.security.exceptions import SecretException
from qello_knowledge.security.send_gate import OutgoingPiece, SendHit, check_outgoing
from tests.unit.security.helpers import team_policy
from tests.unit.synthetic_secrets import SYNTHETIC

TOKEN = SYNTHETIC["github-classic"]
EXCEPTION = SecretException("docs", "docs/a.md", "github-token", "시험")


def _send_if_allowed(pieces, policy, sender):
    check = check_outgoing(pieces, policy)
    if check.allowed:
        sender(pieces)
    return check


def test_secret_piece_blocks_the_whole_request():
    sent = []
    pieces = [OutgoingPiece("clean", ("docs", "docs/b.md")), OutgoingPiece(f"line\n{TOKEN}", ("docs", "docs/c.md"))]
    check = _send_if_allowed(pieces, team_policy(), sent.append)
    assert check.allowed is False and sent == []
    assert check.hits == (SendHit(1, "github-token", 2),)
    assert TOKEN not in repr(check) + repr(pieces)


def test_exception_scope_is_limited_to_its_own_origin():
    policy = team_policy(exceptions=frozenset({EXCEPTION}))
    assert check_outgoing([OutgoingPiece(TOKEN, ("docs", "docs/a.md"))], policy).allowed
    assert not check_outgoing([OutgoingPiece(TOKEN, ("docs2", "docs/a.md"))], policy).allowed
    assert not check_outgoing([OutgoingPiece(TOKEN, None)], policy).allowed


def test_exception_scope_does_not_spread_in_mixed_generation_input():
    policy = team_policy(exceptions=frozenset({EXCEPTION}))
    pieces = [
        OutgoingPiece(TOKEN, ("docs", "docs/a.md")),
        OutgoingPiece("other chunk", ("docs", "docs/b.md")),
        OutgoingPiece(f"question {TOKEN}", None),
    ]
    check = check_outgoing(pieces, policy)
    assert check.allowed is False and check.hits == (SendHit(2, "github-token", 1),)


def test_log_has_no_piece_text(caplog):
    caplog.set_level(logging.INFO, logger="qello_knowledge.security")
    check_outgoing([OutgoingPiece(TOKEN, None)], team_policy())
    assert caplog.records and TOKEN not in caplog.text

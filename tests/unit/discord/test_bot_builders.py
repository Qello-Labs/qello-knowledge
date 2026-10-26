import json

from tests.unit.discord.bot_builders import FakeClock, FakeDiscord, ask, component, other_command, ping, signing_key


def test_bot_builders():
    clock = FakeClock()
    clock.advance(2)
    assert clock.now() == 2
    key = signing_key()
    body = ask("synthetic question", private=True)
    assert len(key.sign(body, "100")["X-Signature-Ed25519"]) == 128
    assert len(key.public_key) == 64
    assert json.loads(body)["data"]["options"][1]["value"] is True
    assert json.loads(ping())["type"] == 1
    assert json.loads(component())["type"] == 3
    assert json.loads(other_command("other"))["data"]["name"] == "other"
    fake = FakeDiscord([(429, {"retry_after": 1}), (204, {})], clock=clock)
    assert fake.request("PATCH", "/test", {}, {}, timeout=3, deadline=5).status == 429
    assert fake.request("POST", "/test", {}, {}, timeout=3, deadline=5).status == 204
    assert [r.method for r in fake.requests] == ["PATCH", "POST"]

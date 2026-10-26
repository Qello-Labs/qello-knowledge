import builtins

import pytest

from qello_knowledge.discord.signature import require_backend, verify
from tests.unit.discord.bot_builders import ask, signing_key


def test_bot_signature_valid_and_boundary():
    key = signing_key()
    body = ask("synthetic question")
    signature = key.sign(body, "1000")["X-Signature-Ed25519"]
    for now in (700, 1000, 1300):
        assert verify(key.public_key, signature, "1000", body, now)
    for now in (699.99, 1300.01):
        assert not verify(key.public_key, signature, "1000", body, now)
    assert not verify(key.public_key, signature, "1001", body, 1000)
    assert not verify(key.public_key, signature, "1000", body + b" ", 1000)
    assert not verify(key.public_key, key.other_key_sign(body, "1000")["X-Signature-Ed25519"], "1000", body, 1000)


@pytest.mark.parametrize(
    "signature,timestamp,public_key",
    [
        (None, "1000", "f" * 64),
        ("f" * 128, None, "f" * 64),
        ("not-hex", "1000", "f" * 64),
        ("f" * 126, "1000", "f" * 64),
        ("f" * 130, "1000", "f" * 64),
        ("f" * 128, "not-time", "f" * 64),
        ("f" * 128, "NaN", "f" * 64),
        ("f" * 128, "1000", "not-key"),
        ("f" * 128, "1000", None),
    ],
)
def test_bot_bad_signature_returns_false(signature, timestamp, public_key):
    assert verify(public_key, signature, timestamp, b"{}", 1000) is False


def test_bot_missing_backend(monkeypatch):
    original = builtins.__import__

    def bot_import(name, *args, **kwargs):
        if name.startswith("cryptography"):
            raise ImportError("synthetic unavailable")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", bot_import)
    with pytest.raises(RuntimeError, match=r"query.*cryptography"):
        require_backend()
    assert not verify("f" * 64, "f" * 128, "1000", b"{}", 1000)

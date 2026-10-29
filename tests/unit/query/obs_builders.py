"""OBS 합성 입력과 실패 주입 포트. 실제 서비스에 연결하지 않는다."""

import json
from threading import Event

from tests.unit.discord.bot_builders import FakeClock, ask

QUESTIONER = "100000000000000001"
RATER = "100000000000000002"
RUN = "q-20261029T010203-1234abcd"


def component(action="up", *, run_id=RUN, user=QUESTIONER, custom_id=None, **options):
    payload = json.loads(ask("합성 질문 1", **options))
    payload["type"] = 3
    payload["member"]["user"] = {"id": user}
    payload["data"] = {
        "component_type": 2,
        "custom_id": custom_id if custom_id is not None else f"qk1:{action}:{run_id}",
    }
    return json.dumps(payload, ensure_ascii=False).encode()


def sources(**options):
    payload = json.loads(ask("합성 질문 1", **options))
    payload["data"] = {"name": "sources"}
    return json.dumps(payload).encode()


class FakeQueryLog:
    def __init__(self, **results):
        self.results = results
        self.calls = []
        self.timeouts = []
        self.closed = False

    def set_deadline(self, deadline, clock):
        self.deadline = deadline

    def set_timeout(self, milliseconds):
        self.timeouts.append(milliseconds)

    def __getattr__(self, name):
        def call(*args):
            self.calls.append((name, args))
            value = self.results.get(name, "stored" if name in {"feedback", "store_question"} else None)
            if isinstance(value, Event):
                value.wait(3)
                return None
            if isinstance(value, Exception):
                raise value
            return value(*args) if callable(value) else value

        return call

    def close(self):
        self.closed = True


__all__ = ["QUESTIONER", "RATER", "RUN", "FakeClock", "FakeQueryLog", "component", "sources"]

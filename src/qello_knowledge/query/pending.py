"""동의 전 질문을 메모리에만 보관한다. 잠금 아래 한 선택만 선점한다."""

from dataclasses import replace
from datetime import UTC, date, datetime
from threading import RLock
from time import monotonic

from qello_knowledge.domain.query_log import PendingQuestion


class PendingQuestions:
    def __init__(
        self,
        *,
        enabled=True,
        retain_until=None,
        seconds=3600,
        maximum=500,
        clock=monotonic,
        today=lambda: datetime.now(UTC).date(),
    ):
        self.enabled = enabled
        self.retain_until = (
            date.fromisoformat(retain_until) if isinstance(retain_until, str) and retain_until else retain_until
        )
        self.seconds, self.maximum, self.clock, self.today = seconds, maximum, clock, today
        self._items = {}
        self._lock = RLock()

    @property
    def accepting(self):
        return bool(self.enabled and self.retain_until is not None and self.retain_until >= self.today())

    def prune(self):
        with self._lock:
            now = self.clock()
            self._items = {k: v for k, v in self._items.items() if self.accepting and v.expires_at > now}

    def __len__(self):
        with self._lock:
            self.prune()
            return len(self._items)

    def put(self, run_id, questioner_id, question, status):
        with self._lock:
            self.prune()
            if not self.accepting or not questioner_id or status not in ("answered", "cannot_confirm"):
                return False
            if run_id in self._items:
                return False
            self._items[run_id] = PendingQuestion(
                run_id, questioner_id, question, "waiting", self.clock() + self.seconds
            )
            while len(self._items) > self.maximum:
                oldest = min(self._items, key=lambda k: self._items[k].expires_at)
                del self._items[oldest]
            return True

    def get(self, run_id):
        with self._lock:
            self.prune()
            return self._items.get(run_id)

    def claim(self, run_id, user):
        with self._lock:
            item = self.get(run_id)
            if item is None or item.questioner_id != user or item.state not in ("waiting", "uncertain"):
                return None
            self._items[run_id] = replace(item, state="claimed")
            return item

    def finish(self, original, *, uncertain=False):
        with self._lock:
            current = self.get(original.run_id)
            if current is None or current.state != "claimed" or current.expires_at != original.expires_at:
                return
            self._items[current.run_id] = replace(
                current, state="uncertain" if uncertain else "chosen", question=original.question if uncertain else None
            )

    def close(self):
        with self._lock:
            self._items.clear()
            self.enabled = False

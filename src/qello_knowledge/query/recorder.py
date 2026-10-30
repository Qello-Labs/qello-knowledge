"""연결·스레드가 분리된 앞 길/뒤 길. 오류 원문은 경계를 넘지 않는다."""

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic


@dataclass(frozen=True)
class RecordResult:
    status: str
    value: object = field(default=None, repr=False)


class _Arguments:
    """취소된 executor 작업이 원문을 붙잡지 않도록 비울 수 있는 인자."""

    def __init__(self, args):
        self._args = args
        self._lock = Lock()

    def take(self):
        with self._lock:
            args, self._args = self._args, ()
            return args

    def clear(self):
        with self._lock:
            self._args = ()


class _Lane:
    def __init__(self, factory, name, clock):
        self.factory, self.clock = factory, clock
        self.executor = ThreadPoolExecutor(1, thread_name_prefix=name)
        self.port = None

    def run(self, method, args, deadline):
        remaining = deadline - self.clock() if deadline is not None else None
        if remaining is not None and remaining <= 0.300000001:
            return RecordResult("timeout")
        try:
            if self.port is None:
                self.port = self.factory()
            remaining = deadline - self.clock() if deadline is not None else None
            if remaining is not None and remaining <= 0.300000001:
                return RecordResult("timeout")
            if remaining is not None:
                self.port.set_deadline(deadline, self.clock)
                self.port.set_timeout(max(100, int(remaining * 1000) - 200))
            value = getattr(self.port, method)(*args.take())
            if deadline is not None and self.clock() >= deadline:
                return RecordResult("timeout")
            return RecordResult("ok", value)
        except Exception as exc:
            return RecordResult("timeout" if getattr(exc, "kind", None) == "timeout" else "failed")

    def submit(self, method, args, deadline=None):
        box = args if isinstance(args, _Arguments) else _Arguments(args)
        return self.executor.submit(self.run, method, box, deadline)

    def close(self):
        self.executor.shutdown(wait=True, cancel_futures=True)
        if self.port is not None:
            self.port.close()


class QueryRecorder:
    def __init__(self, front_factory, back_factory=None, *, record_timeout_ms=1000, clock=monotonic):
        self._clock = clock
        self._front = _Lane(front_factory, "qk-record-front", clock)
        self._back = _Lane(back_factory, "qk-record-back", clock) if back_factory is not None else None
        self._record_timeout = record_timeout_ms / 1000

    @property
    def enabled(self):
        return self._back is not None

    def front(self, method, *args, deadline):
        remaining = deadline - self._clock()
        if remaining <= 0.3:
            return RecordResult("timeout")
        box = _Arguments(args)
        del args
        future = self._front.submit(method, box, deadline)
        try:
            return future.result(timeout=max(0, deadline - self._clock()))
        except FutureTimeout:
            box.clear()
            future.cancel()
            return RecordResult("timeout")
        finally:
            box.clear()

    def insert(self, record, *, wait=True):
        if self._back is None:
            return "off"
        future = self._back.submit("insert", (record,))
        if not wait:
            return "stored" if future.done() and future.result().status == "ok" else "timeout"
        try:
            result = future.result(timeout=self._record_timeout)
            return "stored" if result.status == "ok" else result.status
        except FutureTimeout:
            return "timeout"

    def delivered(self, delivery):
        if self._back is not None:
            self._back.submit("delivered", (delivery,))

    def close(self):
        self._front.close()
        if self._back is not None:
            self._back.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

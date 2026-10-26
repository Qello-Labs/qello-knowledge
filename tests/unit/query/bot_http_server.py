"""운영 서버 생성 경로에 메모리 가짜를 주입하는 루프백 시험 하네스."""

from contextlib import contextmanager
from threading import Thread

from qello_knowledge.query.server import make_server


@contextmanager
def bot_live_server(runtime):
    server = make_server(0, None, app=runtime.app, report=lambda: runtime.report)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        runtime.jobs.close()
        assert not thread.is_alive()

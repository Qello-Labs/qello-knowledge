"""테스트 공통 규칙(research R-07).

- 기본 실행에서는 루프백·유닉스 소켓 밖으로 연결하지 못한다(SC-002).
- `localdb` 테스트는 로컬 DB가 없으면 건너뛴다. `QK_REQUIRE_LOCALDB=1`이면 실패로 바꾼다.
- `external` 테스트는 `-m external`로만 돌고, 필요한 토큰이 없으면 실패한다(FR-016).
"""

from __future__ import annotations

import os
import socket

import pytest

LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex


def _host_of(address: object) -> str | None:
    if isinstance(address, tuple) and address:
        return str(address[0])
    return None  # 유닉스 소켓 경로


def _guard(original):
    def wrapper(self: socket.socket, address, *args, **kwargs):
        host = _host_of(address)
        if host is not None and host not in LOOPBACK:
            raise RuntimeError(f"외부 연결 차단: {host}")
        return original(self, address, *args, **kwargs)

    return wrapper


@pytest.fixture(autouse=True)
def block_external_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("external"):
        return
    monkeypatch.setattr(socket.socket, "connect", _guard(_original_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", _guard(_original_connect_ex))


def local_db_port() -> int:
    raw = os.environ.get("QK_LOCAL_DB_PORT", "").strip()
    return int(raw) if raw.isdigit() else 54322


def _local_db_reachable(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return _original_connect_ex(sock, ("127.0.0.1", port)) == 0


@pytest.fixture(autouse=True)
def require_local_db(request: pytest.FixtureRequest) -> None:
    if not request.node.get_closest_marker("localdb"):
        return
    port = local_db_port()
    if _local_db_reachable(port):
        return
    message = f"로컬 DB(127.0.0.1:{port})에 연결할 수 없다. `uv run qk-dev db up`을 먼저 실행한다"
    if os.environ.get("QK_REQUIRE_LOCALDB") == "1":
        pytest.fail(message)
    pytest.skip(message)


@pytest.fixture
def require_env():
    """`external` 테스트에서 쓴다. 값이 없으면 건너뛰지 않고 실패한다. 값은 출력하지 않는다."""

    def get(name: str) -> str:
        value = os.environ.get(name, "").strip()
        if not value:
            pytest.fail(f"토큰 없음: {name}")
        return value

    return get

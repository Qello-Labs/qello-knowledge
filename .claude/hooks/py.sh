#!/usr/bin/env sh
# 훅용 Python 실행기. Windows의 python3는 Microsoft Store 안내 스텁일 수 있어
# 실제로 실행되는 인터프리터를 고른다. macOS에는 python3만 있는 경우가 많다.
if command -v python3 >/dev/null 2>&1 && python3 -c '' </dev/null >/dev/null 2>&1; then
  exec python3 "$@"
fi
exec python "$@"

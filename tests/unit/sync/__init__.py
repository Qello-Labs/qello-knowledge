"""동기화 시험 패키지. pytest 기본 import 모드의 동명 디렉터리를 함께 찾는다."""

from pathlib import Path

__path__.append(str(Path(__file__).resolve().parents[2] / "localdb" / "sync"))

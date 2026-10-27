"""성능 회귀 감시(QK-CHK-001 spec SC-012, tasks T045). 완료 판정이 아니다.

완료 판정은 대상 저장소 실측(`measurement/measure_code.py --time-chunking`, 사람 단계 H01)으로 한다.
입력은 `random` 없이 만든 합성 파일 1,361개(Java 1,128 + Kotlin 233, research R-02 파일 수)다.
"""

import hashlib
import time

from qello_knowledge.chunking import chunk_screened
from qello_knowledge.domain.chunking import ChunkingSettings, ChunkOutcomeKind, CodeChunkingSettings
from tests.unit.chunking.helpers import screened

JAVA_FILES, KOTLIN_FILES = 1128, 233
INPUT_SHA256 = (
    "4d2c93a888a6ea996a445f22694d721d3b2e0e7fb7843b4f532279c9ba18ec57"  # 2026-10-27 처음 실행에서 계산해 고정
)
INPUT_BYTES = 2_918_175


def java(i):
    fields = "".join(f'    private final String field{f} = "value{i}_{f}";\n' for f in range(3))
    methods = "".join(
        f"    public int method{m}(int input) {{\n"
        + "".join(f"        int step{s} = input * {s} + {i};\n" for s in range(7))
        + "        return input;\n    }\n\n"
        for m in range(6)
    )
    return (
        f"package com.acme.perf{i % 10};\n\nimport java.util.List;\n\npublic class Perf{i} {{\n{fields}\n{methods}}}\n"
    )


def kotlin(i):
    fields = "".join(f'    private val field{f} = "value{i}_{f}"\n' for f in range(3))
    methods = "".join(
        f"    fun method{m}(input: Int): Int {{\n"
        + "".join(f"        val step{s} = input * {s} + {i}\n" for s in range(7))
        + "        return input\n    }\n\n"
        for m in range(6)
    )
    return f"package com.acme.perf{i % 10}\n\nimport kotlin.math.max\n\nclass Perf{i} {{\n{fields}\n{methods}}}\n"


def inputs():
    files = [(f"src/main/java/com/acme/Perf{i}.java", java(i)) for i in range(JAVA_FILES)]
    files += [(f"app/src/main/java/com/acme/Perf{i}.kt", kotlin(i)) for i in range(KOTLIN_FILES)]
    return files


def test_synthetic_input_is_fixed():
    digest = hashlib.sha256()
    for location, body in inputs():
        digest.update(location.encode() + b"\0" + body.encode() + b"\0")
    assert digest.hexdigest() == INPUT_SHA256
    assert sum(len(body.encode()) for _, body in inputs()) == INPUT_BYTES


def test_chunking_1361_files_stays_under_60_seconds():
    batch = [screened(body, content_format="CODE", location=location) for location, body in inputs()]
    started = time.perf_counter()
    result = chunk_screened(batch, ChunkingSettings(), code=CodeChunkingSettings())
    elapsed = time.perf_counter() - started
    assert {r.outcome for r in result.results} == {ChunkOutcomeKind.CHUNKED}
    assert elapsed <= 60, elapsed

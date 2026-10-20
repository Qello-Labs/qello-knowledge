"""시험의 임시 디렉터리에만 합성 확인 기록을 만든다."""

import json
from pathlib import Path

from qello_knowledge.sources.config import load_sources


def write_review(config, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    def q(value):
        return json.dumps(value, ensure_ascii=False)

    lines = [
        f"source = {q(config.name)}",
        "reviewed_on = 2026-10-20",
        'reviewer_role = "시험용 역할"',
        'method = "합성 범위 전체 확인"',
        'result = "개인 정보 없음"',
        "[scope]",
        f"include = {q(config.scope.include)}",
        f"exclude = {q(config.scope.exclude)}",
    ]
    lines.extend(f"{key} = {q(value)}" for key, value in config.scope.extra)
    path = directory / (config.name + ".toml")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def review_args(sources, directory):
    configs, _ = load_sources(Path(sources))
    for config in configs:
        if config.enabled:
            write_review(config, directory)
    return ["--reviews", str(directory)]

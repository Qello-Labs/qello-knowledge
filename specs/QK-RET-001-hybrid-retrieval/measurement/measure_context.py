"""QK-RET-001 plan 측정(research R-08).

대상 저장소 로컬 사본의 한 커밋을 기준선 청커로 나눠 청크 본문의 예상 토큰과 생성 모델 토크나이저 토큰을 비교한다.
집계만 출력하고 원문·경로는 출력하지 않는다. Workers AI 호출은 없다.

실행(저장소 루트):
    uv run --with tokenizers==0.23.3 python specs/QK-RET-001-hybrid-retrieval/measurement/measure_context.py \
        --repo <대상 저장소 로컬 사본> --commit <커밋> --source dnd-backend-docs \
        --blocked docs/superpowers/plans/2026-09-10-codex-agents-token-optimization.md \
        --tokenizer <Qwen/Qwen3-30B-A3B tokenizer.json 경로>

분위수는 정렬한 값의 `index = min(n - 1, floor(n * q))` 원소다(QK-CHK-002 measure_inputs.py와 같다).
"""

import argparse
import hashlib
import json
import math
import statistics
import subprocess
import tomllib
from pathlib import Path

from qello_knowledge.chunking import chunk_markdown
from qello_knowledge.domain.chunking import ChunkingSettings
from qello_knowledge.domain.scope import in_scope

BYTES_PER_TOKEN = 3.5  # embedding/estimate.py와 같은 추정
BUDGET = 2000  # spec FR-016 Context 예산 초기값


def est(text: str) -> int:
    return math.ceil(len(text.encode("utf-8")) / BYTES_PER_TOKEN)


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.floor(len(ordered) * q))]


def summary(values: list[float]) -> dict:
    return {
        "median": round(statistics.median(values), 3),
        "p95": round(quantile(values, 0.95), 3),
        "max": round(max(values), 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--sources", default="config/sources.toml")
    parser.add_argument("--blocked", action="append", default=[])
    parser.add_argument("--tokenizer", required=True)
    args = parser.parse_args()

    config = next(s for s in tomllib.loads(Path(args.sources).read_text())["source"] if s["name"] == args.source)
    include, exclude = tuple(config["scope"]["include"]), tuple(config["scope"]["exclude"])

    def git(*a: str) -> bytes:
        return subprocess.run(["git", "-C", args.repo, *a], check=True, capture_output=True).stdout  # noqa: S603, S607

    paths = [
        p
        for p in git("ls-tree", "-r", "--name-only", args.commit).decode().splitlines()
        if in_scope(p, include, exclude) and p not in args.blocked
    ]
    settings = ChunkingSettings()
    bodies: list[str] = []
    outcomes = {}
    for p in paths:
        text = git("show", f"{args.commit}:{p}").decode("utf-8").replace("\r\n", "\n").removeprefix("﻿")
        outcome = chunk_markdown(text, location=p, source_title=None, settings=settings)
        outcomes[str(outcome.outcome)] = outcomes.get(str(outcome.outcome), 0) + 1
        bodies += [draft.chunk.body for draft in outcome.drafts]

    from tokenizers import Tokenizer

    tokenizer_path = Path(args.tokenizer)
    tok = Tokenizer.from_file(str(tokenizer_path))
    estimates = [est(b) for b in bodies]
    reals = [len(tok.encode(b, add_special_tokens=False).ids) for b in bodies]
    ratios = [r / e for r, e in zip(reals, estimates, strict=True) if e > 0]
    result = {
        "commit": args.commit,
        "files": len(paths),
        "outcomes": dict(sorted(outcomes.items())),
        "chunks": len(bodies),
        "chunking_version": chunk_markdown(
            "# a\n\nb", location="x.md", source_title=None, settings=settings
        ).chunking_version,
        "tokenizer": {
            "file_sha256": hashlib.sha256(tokenizer_path.read_bytes()).hexdigest(),
        },
        "estimated_tokens": {
            **summary([float(e) for e in estimates]),
            "over_budget": sum(e > BUDGET for e in estimates),
            "over_budget_share": round(sum(e > BUDGET for e in estimates) / len(estimates), 4),
        },
        "real_tokens": {**summary([float(r) for r in reals]), "over_budget": sum(r > BUDGET for r in reals)},
        "real_over_est": {**summary(ratios), "aggregate": round(sum(reals) / sum(estimates), 3)},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

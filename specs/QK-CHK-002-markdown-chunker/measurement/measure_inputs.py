"""QK-CHK-002 plan 측정(research R-02·R-03).

대상 저장소 로컬 사본의 한 커밋을 읽어 집계만 출력한다. 원문은 출력하지 않는다.

실행(저장소 루트):
    uv run --with tokenizers==0.23.3 python specs/QK-CHK-002-markdown-chunker/measurement/measure_inputs.py \
        --repo <대상 저장소 로컬 사본> --commit <커밋> --source dnd-backend-docs \
        --blocked docs/superpowers/plans/2026-09-10-codex-agents-token-optimization.md \
        --tokenizer-revision 5617a9f61b028005a4858fdac845db406aefb181

`--tokenizer-revision`을 빼면 실제 토큰 비교(R-03)는 건너뛴다.
`--time-chunking`은 구현된 청커(`chunking.chunk_markdown`)로 SC-011 완료 판정 시간을 잰다(research R-12).
분위수는 정렬한 값의 `index = min(n - 1, floor(n * q))` 원소다.
"""

import argparse
import json
import math
import re
import statistics
import subprocess
import tomllib
from collections import Counter
from pathlib import Path, PurePosixPath

from markdown_it import MarkdownIt

from qello_knowledge.domain.scope import in_scope

BYTES_PER_TOKEN = 3.5  # embedding/estimate.py와 같은 추정
LIMIT = 2800  # research R-03
FENCE_CLOSE = re.compile(r"^[\s>]*(`{3,}|~{3,})\s*$")


def est(text: str) -> int:
    return math.ceil(len(text.encode("utf-8")) / BYTES_PER_TOKEN)


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.floor(len(ordered) * q))]


def heading_text(inline) -> str:
    parts = []
    for child in inline.children or []:
        if child.type in ("text", "code_inline"):
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
        elif child.type == "image":
            parts.append(child.content)
    return " ".join("".join(parts).split())


def front_matter(lines: list[str]) -> tuple[int, str | None]:
    if not lines or lines[0] != "---":
        return 0, None
    for i in range(1, len(lines)):
        if lines[i] in ("---", "..."):
            values = [ln.split(":", 1)[1].strip().strip("'\"") for ln in lines[1:i] if ln.startswith("title:")]
            title = values[0] if values else None
            return i + 1, title or None
    return 0, None


def analyse(path: str, text: str, md: MarkdownIt) -> dict:
    lines = text.split("\n")
    fm_end, fm_title = front_matter(lines)
    parsed = "\n".join([""] * fm_end + lines[fm_end:])
    tokens = md.parse(parsed)
    heads, prefix_of_line = [], {}
    for i, t in enumerate(tokens):
        if t.type == "heading_open" and t.level == 0:
            heads.append((t.map[0], int(t.tag[1]), heading_text(tokens[i + 1])))
        elif t.type == "table_open":
            for ln in range(t.map[0] + 2, t.map[1]):
                prefix_of_line[ln] = "\n".join(lines[t.map[0] : t.map[0] + 2])
        elif t.type == "fence":
            for ln in range(t.map[0] + 1, t.map[1]):
                prefix_of_line[ln] = lines[t.map[0]]
    h1 = next((h[2] for h in heads if h[1] == 1), None)
    title = fm_title or h1 or PurePosixPath(path).name
    worst, stack, head_at = 0, [], {h[0]: h for h in heads}
    for n, line in enumerate(lines):
        if n in head_at:
            _, level, htext = head_at[n]
            stack = [s for s in stack if s[0] < level] + [(level, htext)]
        names = [s[1] for s in stack]
        if names and names[0] == title:
            names = names[1:]
        header = path + "\n" + " > ".join([title, *names])
        prefix = prefix_of_line.get(n)
        candidate = header + "\n\n" + (prefix + "\n" if prefix else "") + line
        if line.strip():
            worst = max(worst, est(candidate))
    return {"bytes": len(text.encode()), "worst_line_with_header": worst}


def time_chunking(paths: list[str], texts: dict[str, str]) -> dict:
    import platform
    import time

    from qello_knowledge.chunking import chunk_markdown
    from qello_knowledge.domain.chunking import ChunkingSettings

    settings = ChunkingSettings()
    started = time.perf_counter()
    outcomes = [chunk_markdown(texts[p], location=p, source_title=None, settings=settings) for p in paths]
    elapsed = time.perf_counter() - started
    return {
        "files": len(paths),
        "total_bytes": sum(len(texts[p].encode()) for p in paths),
        "elapsed_seconds": elapsed,
        "by_outcome": dict(sorted(Counter(str(o.outcome) for o in outcomes).items())),
        "chunk_count": sum(len(o.drafts) for o in outcomes),
        "chunking_version": outcomes[0].chunking_version if outcomes else None,
        "environment": f"{platform.platform()} / Python {platform.python_version()}",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--sources", default="config/sources.toml")
    parser.add_argument("--blocked", action="append", default=[])
    parser.add_argument("--tokenizer-revision")
    parser.add_argument("--time-chunking", action="store_true")
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
    md = MarkdownIt("commonmark").enable("table")
    texts = {p: git("show", f"{args.commit}:{p}").decode("utf-8").replace("\r\n", "\n").removeprefix("﻿") for p in paths}
    docs = [analyse(p, texts[p], md) for p in paths]
    worst = [d["worst_line_with_header"] for d in docs]
    result = {
        "commit": args.commit,
        "files": len(paths),
        "total_bytes": sum(d["bytes"] for d in docs),
        "worst_line_with_header_and_prefix": {"max": max(worst), "p99": quantile(worst, 0.99)},
        "docs_failing_line_too_long_at_limit": sum(w > LIMIT for w in worst),
    }
    if args.tokenizer_revision:
        from tokenizers import Tokenizer

        tok = Tokenizer.from_pretrained("BAAI/bge-m3", revision=args.tokenizer_revision)
        rows = []
        for p in paths:
            text, lines = texts[p], texts[p].split("\n")
            rows.append(("file", len(text.encode()), len(tok.encode(text).ids)))
            for t in md.parse(text):
                if t.level == 0 and t.map and t.nesting in (0, 1) and t.type != "inline":
                    seg = "\n".join(lines[t.map[0] : t.map[1]])
                    if len(seg.encode()) >= 200:
                        kind = {"fence": "code", "code_block": "code", "table_open": "table"}.get(t.type, "prose")
                        rows.append((kind, len(seg.encode()), len(tok.encode(seg).ids)))
        by_kind = {}
        for kind in ("file", "prose", "code", "table"):
            sel = [(b, r) for k, b, r in rows if k == kind]
            ratio = [r / math.ceil(b / BYTES_PER_TOKEN) for b, r in sel]
            by_kind[kind] = {
                "n": len(sel),
                "real_over_est": {
                    "median": round(statistics.median(ratio), 3),
                    "p95": round(quantile(ratio, 0.95), 3),
                    "max": round(max(ratio), 3),
                },
                "min_bytes_per_real_token": round(min(b / r for b, r in sel), 2),
            }
        result["tokens"] = {"tokenizer": f"BAAI/bge-m3@{args.tokenizer_revision}", "by_kind": by_kind}
    if args.time_chunking:
        result["chunking"] = time_chunking(paths, texts)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
